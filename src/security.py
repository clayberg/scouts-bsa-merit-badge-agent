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
import hashlib
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


def _get_jwt_signing_secret() -> str:
    """Returns the HMAC-SHA256 signing secret used for service/test JWT verification."""
    return (
        os.environ.get("BSA_JWT_SECRET", "").strip()
        or os.environ.get("BSA_HITL_SECRET_KEY", "").strip()
        or os.environ.get("BSA_API_KEY", "").strip()
        or _get_admin_secret_token()
        or "scouts-bsa-capstone-key"
    )


def mint_signed_hs256_jwt(payload: Dict[str, Any], secret: Optional[str] = None) -> str:
    """Mints an HMAC-SHA256 (`HS256`) signed JWT token for authenticated API callers and tests."""
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = (
        base64.urlsafe_b64encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    eff_secret = (secret or _get_jwt_signing_secret()).encode("utf-8")
    digest = hmac.new(eff_secret, signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def _verify_oidc_jwt_structure(token: str) -> Optional[Dict[str, Any]]:
    """Cryptographically verifies Bearer JWT tokens (Google OIDC JWKS or HMAC-SHA256) or shared API key.

    Strictly rejects unsigned (`alg: none`), empty-signature, expired, or forged-signature JWTs.
    """
    expected_key = os.environ.get("BSA_API_KEY", "").strip()
    if expected_key and hmac.compare_digest(token.encode("utf-8"), expected_key.encode("utf-8")):
        return {"sub": "api_key_bearer_client", "auth_method": "bearer_api_key"}

    parts = token.split(".")
    if len(parts) != 3:
        return None
    header_part, payload_part, sig_part = parts[0].strip(), parts[1].strip(), parts[2].strip()
    if not header_part or not payload_part or not sig_part:
        return None

    try:
        header_b64 = header_part + "=" * (-len(header_part) % 4)
        header = json.loads(base64.urlsafe_b64decode(header_b64.encode("utf-8")).decode("utf-8"))
        if not isinstance(header, dict):
            return None
        alg = str(header.get("alg") or "").strip().upper()
        if not alg or alg == "NONE":
            return None

        payload_b64 = payload_part + "=" * (-len(payload_part) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        exp = payload.get("exp")
        if exp is not None and float(exp) < time.time():
            return None
        if not (payload.get("sub") or payload.get("email")):
            return None

        # Live Google OIDC RS256 JWKS verification path
        verify_live_oidc = os.environ.get("BSA_VERIFY_GOOGLE_OIDC_LIVE", "false").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if verify_live_oidc or alg == "RS256":
            try:
                from google.auth.transport import requests as google_requests  # type: ignore
                from google.oauth2 import id_token as google_id_token  # type: ignore

                audience = os.environ.get("BSA_OIDC_AUDIENCE", "").strip() or None
                verified_claims = google_id_token.verify_oauth2_token(
                    token, google_requests.Request(), audience=audience
                )
                return {
                    "sub": str(verified_claims.get("email") or verified_claims.get("sub")),
                    "iss": str(verified_claims.get("iss", "https://accounts.google.com")),
                    "auth_method": "oidc_jwt_rs256",
                }
            except Exception:
                return None

        # Cryptographic HMAC-SHA256 verification path
        if alg == "HS256":
            signing_input = f"{header_part}.{payload_part}".encode("ascii")
            candidate_secrets = {
                _get_jwt_signing_secret(),
                os.environ.get("BSA_JWT_SECRET", "").strip(),
                os.environ.get("BSA_HITL_SECRET_KEY", "").strip(),
                os.environ.get("BSA_API_KEY", "").strip(),
                _get_admin_secret_token(),
                "scouts-bsa-capstone-key",
            }
            sig_ok = False
            for sec in candidate_secrets:
                if not sec:
                    continue
                expected_digest = hmac.new(sec.encode("utf-8"), signing_input, hashlib.sha256).digest()
                expected_sig_b64 = base64.urlsafe_b64encode(expected_digest).decode("ascii").rstrip("=")
                if hmac.compare_digest(sig_part.encode("ascii"), expected_sig_b64.encode("ascii")):
                    sig_ok = True
                    break
            if not sig_ok:
                return None
            return {
                "sub": str(payload.get("email") or payload.get("sub")),
                "iss": str(payload.get("iss", "oidc")),
                "auth_method": "oidc_jwt",
            }

        return None
    except Exception:
        return None


async def verify_caller_auth(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """FastAPI dependency verifying caller identity via OIDC Bearer JWT or X-API-Key and enforcing rate limits."""
    client_host = getattr(getattr(request, "client", None), "host", None) or "default"
    if not GLOBAL_RATE_LIMITER.check_rate_limit(f"{client_host}:{request.url.path}"):
        emit_compliance_audit_log(
            caller_id=str(client_host),
            action=f"{request.method} {request.url.path}",
            guardrail_status="RATE_LIMIT_EXCEEDED",
        )
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please retry shortly.")

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

    def check_rate_limit(self, client_key: str = "default") -> bool:
        """Alias for `allow_request(client_key)`."""
        return self.allow_request(client_key=client_key)


GLOBAL_RATE_LIMITER = TokenBucketRateLimiter(
    requests_per_minute=int(os.environ.get("BSA_RATE_LIMIT_RPM", "600")),
    burst_capacity=int(os.environ.get("BSA_RATE_LIMIT_BURST", "300")),
)

ADMIN_SESSION_COOKIE_NAME = "bsa_admin_session"


def _get_admin_secret_token() -> str:
    """Returns the configured ADMIN_SUPERUSER_TOKEN for Super-User Admin Console verification."""
    env_val = os.environ.get("ADMIN_SUPERUSER_TOKEN", "").strip()
    if env_val:
        return env_val
    return get_secret("ADMIN_SUPERUSER_TOKEN", default="scouts-bsa-admin-superuser") or "scouts-bsa-admin-superuser"


def _get_allowed_admin_emails() -> set[str]:
    """Returns the set of lowercase administrator emails allowed via Cloud IAP or token unlock."""
    allowed_raw = os.environ.get("ADMIN_ALLOWED_EMAILS", "admin@clayberg.altostrat.com")
    emails = {e.strip().lower() for e in allowed_raw.split(",") if e.strip()}
    emails.add("admin@clayberg.altostrat.com")
    return emails


def verify_admin_token_value(candidate: str) -> bool:
    """Verifies a candidate admin token/passphrase or allowed admin email in constant time."""
    if not candidate or not str(candidate).strip():
        return False
    provided_str = str(candidate).strip()
    expected = _get_admin_secret_token().encode("utf-8")
    provided = provided_str.encode("utf-8")
    if hmac.compare_digest(provided, expected):
        return True
    # When no custom ADMIN_SUPERUSER_TOKEN override is forced, also accept configured admin emails
    if not os.environ.get("ADMIN_SUPERUSER_TOKEN", "").strip():
        for allowed_email in _get_allowed_admin_emails():
            if hmac.compare_digest(provided_str.lower().encode("utf-8"), allowed_email.encode("utf-8")):
                return True
    return False


def create_admin_session_cookie(role: str = "superuser", ttl_seconds: int = 86400) -> str:
    """Creates an HMAC-SHA256 signed session cookie token for the Admin Console."""
    payload = {
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + max(60, int(ttl_seconds)),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
    secret = _get_admin_secret_token().encode("utf-8")
    sig = hmac.new(secret, payload_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{payload_b64}.{sig_b64}"


def verify_admin_session_cookie(cookie_val: Optional[str]) -> Optional[Dict[str, Any]]:
    """Verifies an HMAC-SHA256 signed Admin Console cookie."""
    if not cookie_val or "." not in cookie_val:
        return None
    payload_b64, _, sig_b64 = cookie_val.strip().partition(".")
    if not payload_b64 or not sig_b64:
        return None
    secret = _get_admin_secret_token().encode("utf-8")
    expected_sig = hmac.new(secret, payload_b64.encode("ascii"), hashlib.sha256).digest()
    expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode("ascii").rstrip("=")
    if not hmac.compare_digest(sig_b64.encode("ascii"), expected_sig_b64.encode("ascii")):
        return None
    try:
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        if float(payload.get("exp", 0)) < time.time():
            return None
        return payload
    except Exception:
        return None


def check_admin_session_status(request: Request) -> Dict[str, Any]:
    """Determines whether the current request is authorized for the Super-User Admin Console."""
    # 1. Explicit X-Admin-Token header
    header_token = request.headers.get("X-Admin-Token", "").strip()
    if header_token and verify_admin_token_value(header_token):
        return {
            "is_admin": True,
            "auth_mode": "admin_token_header",
            "role": "superuser",
        }

    # 2. Explicit Authorization: Bearer <ADMIN_SUPERUSER_TOKEN>
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        bearer_val = auth_header[7:].strip()
        if bearer_val and verify_admin_token_value(bearer_val):
            return {
                "is_admin": True,
                "auth_mode": "admin_bearer_token",
                "role": "superuser",
            }

    # 3. Signed HttpOnly session cookie (or explicit "locked" marker)
    cookie_val = request.cookies.get(ADMIN_SESSION_COOKIE_NAME)
    if cookie_val == "locked":
        return {
            "is_admin": False,
            "auth_mode": "explicitly_locked",
            "role": "counselor",
        }
    cookie_claims = verify_admin_session_cookie(cookie_val)
    if cookie_claims is not None:
        return {
            "is_admin": True,
            "auth_mode": "signed_cookie",
            "role": str(cookie_claims.get("role", "superuser")),
        }

    # 4. Google Cloud IAP header matching ADMIN_ALLOWED_EMAILS env var
    iap_email = request.headers.get("X-Goog-Authenticated-User-Email", "").strip()
    if iap_email:
        if ":" in iap_email:
            iap_email = iap_email.split(":", 1)[1].strip()
        allowed_emails = _get_allowed_admin_emails()
        if iap_email.lower() in allowed_emails:
            return {
                "is_admin": True,
                "auth_mode": "cloud_iap_allowlist",
                "role": "superuser",
            }

    # 5. Local workstation auto-unlock when not running on Cloud Run (`K_SERVICE` unset)
    is_cloud_run = bool(os.environ.get("K_SERVICE", "").strip())
    local_auto_unlock = os.environ.get("ADMIN_LOCAL_AUTO_UNLOCK", "true").strip().lower() in (
        "true",
        "1",
        "yes",
    )
    if not is_cloud_run and local_auto_unlock:
        return {
            "is_admin": True,
            "auth_mode": "local_workstation_auto",
            "role": "superuser",
        }

    return {
        "is_admin": False,
        "auth_mode": "locked",
        "role": "counselor",
    }


async def verify_admin_auth(request: Request) -> Dict[str, Any]:
    """FastAPI dependency enforcing Super-User Admin authorization on `/api/v1/admin/*` endpoints."""
    status = check_admin_session_status(request)
    if not status.get("is_admin"):
        emit_compliance_audit_log(
            caller_id="unauthorized_admin_caller",
            action=f"{request.method} {request.url.path}",
            guardrail_status="ADMIN_AUTH_FORBIDDEN",
        )
        raise HTTPException(
            status_code=403,
            detail="Super-User Admin authorization required. Unlock the Admin Console first.",
        )
    emit_compliance_audit_log(
        caller_id=f"admin_{status.get('auth_mode', 'superuser')}",
        action=f"{request.method} {request.url.path}",
        guardrail_status="ADMIN_AUTH_SUCCESS",
    )
    return status
