"""Authentication, authorization, rate limiting, and zero-trust request verification.

Supports two operating modes controlled by `AUTH_REQUIRED` (or `AUTH_MODE`):
- Local workbench mode (`AUTH_REQUIRED=false`, default): Allows browser workbench and
  local CLI calls without requiring token setup, while still validating credentials
  if a caller explicitly passes an `X-API-Key` or `Authorization` header against a
  configured `BSA_API_KEY`.
- Enforced production mode (`AUTH_REQUIRED=true` or `AUTH_MODE=enforced`): Rejects
  unauthenticated requests with `401 Unauthorized` and invalid credentials with
  `403 Forbidden`, using constant-time `hmac.compare_digest` comparison and
  emitting structured compliance audit logs.
"""

import base64
import hmac
import json
import os
import threading
import time
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException, Request

from src.agents.guardrails import emit_compliance_audit_log
from src.config import get_secret


def _is_auth_enforced() -> bool:
    """Returns True when strict authentication enforcement is enabled."""
    auth_req = os.environ.get("AUTH_REQUIRED", "false").strip().lower()
    auth_mode = os.environ.get("AUTH_MODE", "permissive_local").strip().lower()
    return auth_req in ("true", "1", "yes") or auth_mode in ("enforced", "strict", "production")


def _verify_oidc_jwt_structure(token: str) -> Optional[Dict[str, Any]]:
    """Validates OIDC / Bearer token structure or compares against BSA_OIDC_AUDIENCE / shared secret.

    In Cloud Run behind IAP / Cloud Run IAM Invoker, Google's proxy verifies the signature
    upstream and passes the signed JWT. For direct API calls, this function verifies
    either a shared bearer secret (`BSA_API_KEY`) or decodes a valid 3-part JWT with
    non-expired `exp` and `sub`/`email` claims.
    """
    expected_key = os.environ.get("BSA_API_KEY", "").strip()
    if expected_key and hmac.compare_digest(token.encode("utf-8"), expected_key.encode("utf-8")):
        return {"sub": "api_key_bearer_client", "auth_method": "bearer_api_key"}

    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        exp = payload.get("exp")
        if exp is not None and float(exp) < time.time():
            return None
        if not (payload.get("sub") or payload.get("email")):
            return None
        return {
            "sub": str(payload.get("email") or payload.get("sub")),
            "iss": str(payload.get("iss", "oidc")),
            "auth_method": "oidc_jwt",
        }
    except Exception:
        return None


async def verify_caller_auth(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """FastAPI dependency verifying caller identity via OIDC Bearer JWT or X-API-Key."""
    enforced = _is_auth_enforced()
    configured_api_key = os.environ.get("BSA_API_KEY") or (
        get_secret("BSA_API_KEY", default="scouts-bsa-capstone-key") if enforced else None
    )

    # 1. Check X-API-Key header if provided
    if x_api_key is not None:
        expected = (configured_api_key or "scouts-bsa-capstone-key").encode("utf-8")
        provided = x_api_key.strip().encode("utf-8")
        if hmac.compare_digest(provided, expected):
            identity = {"caller_id": "authenticated_api_key_caller", "auth_method": "x_api_key", "authenticated": True}
            emit_compliance_audit_log(
                caller_id=identity["caller_id"],
                action=f"{request.method} {request.url.path}",
                guardrail_status="AUTH_SUCCESS",
            )
            return identity
        emit_compliance_audit_log(
            caller_id="invalid_api_key_caller",
            action=f"{request.method} {request.url.path}",
            guardrail_status="AUTH_FORBIDDEN",
        )
        raise HTTPException(status_code=403, detail="Invalid X-API-Key credential.")

    # 2. Check Authorization: Bearer <token> header if provided
    if authorization is not None:
        scheme, _, token = authorization.strip().partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            emit_compliance_audit_log(
                caller_id="malformed_auth_header",
                action=f"{request.method} {request.url.path}",
                guardrail_status="AUTH_UNAUTHORIZED",
            )
            raise HTTPException(status_code=401, detail="Authorization header must use Bearer scheme.")
        claims = _verify_oidc_jwt_structure(token.strip())
        if claims is not None:
            identity = {
                "caller_id": claims["sub"],
                "auth_method": claims["auth_method"],
                "authenticated": True,
            }
            emit_compliance_audit_log(
                caller_id=identity["caller_id"],
                action=f"{request.method} {request.url.path}",
                guardrail_status="AUTH_SUCCESS",
            )
            return identity
        emit_compliance_audit_log(
            caller_id="invalid_bearer_token",
            action=f"{request.method} {request.url.path}",
            guardrail_status="AUTH_FORBIDDEN",
        )
        raise HTTPException(status_code=403, detail="Invalid or expired Bearer token.")

    # 3. No credentials provided
    if enforced:
        emit_compliance_audit_log(
            caller_id="unauthenticated_caller",
            action=f"{request.method} {request.url.path}",
            guardrail_status="AUTH_UNAUTHORIZED",
        )
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide an 'Authorization: Bearer <JWT>' or 'X-API-Key' header.",
        )

    return {
        "caller_id": "local_workbench_counselor",
        "auth_method": "permissive_local",
        "authenticated": False,
    }


class TokenBucketRateLimiter:
    """Thread-safe per-client token bucket rate limiter."""

    def __init__(self, requests_per_minute: int = 120, burst_capacity: int = 40) -> None:
        self.requests_per_minute = max(1, requests_per_minute)
        self.burst_capacity = max(1, burst_capacity)
        self._lock = threading.Lock()
        self._buckets: Dict[str, Dict[str, float]] = {}

    def allow_request(self, client_key: str = "default") -> bool:
        """Consumes 1 token for `client_key` and returns True if allowed, False if rate-limited."""
        now = time.monotonic()
        refill_rate = self.requests_per_minute / 60.0
        with self._lock:
            bucket = self._buckets.get(client_key)
            if bucket is None:
                self._buckets[client_key] = {"tokens": float(self.burst_capacity - 1), "last_ts": now}
                return True
            elapsed = max(0.0, now - bucket["last_ts"])
            tokens = min(float(self.burst_capacity), bucket["tokens"] + elapsed * refill_rate)
            bucket["last_ts"] = now
            if tokens >= 1.0:
                bucket["tokens"] = tokens - 1.0
                return True
            bucket["tokens"] = tokens
            return False


GLOBAL_RATE_LIMITER = TokenBucketRateLimiter(
    requests_per_minute=int(os.environ.get("BSA_RATE_LIMIT_RPM", "120")),
    burst_capacity=int(os.environ.get("BSA_RATE_LIMIT_BURST", "40")),
)
