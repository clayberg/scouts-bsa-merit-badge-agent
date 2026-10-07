"""Fault-injection, resilience, zero-trust auth, pre-LLM PII scrubbing, and OpenAPI contract tests."""

import base64
import json
import time
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from src.agents.guardrails import (
    before_model_guardrail_callback,
    get_compliance_audit_events,
)
from src.config import get_model_provider, load_prompt, load_prompt_manifest
from src.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    ModelFallbackRouter,
    retry_with_exponential_jitter,
)
from src.security import TokenBucketRateLimiter
from src.server import app


def test_circuit_breaker_closed_open_half_open_recovery() -> None:
    """Verifies CircuitBreaker trips OPEN after N failures, short-circuits, transitions HALF_OPEN, and recovers."""
    cb = CircuitBreaker(name="test_upstream", failure_threshold=3, recovery_timeout_sec=0.08)
    assert cb.state == "CLOSED"

    def _failing_rpc() -> str:
        raise TimeoutError("503 Service Unavailable from upstream")

    for _ in range(3):
        with pytest.raises(TimeoutError):
            cb.execute(_failing_rpc)

    assert cb.state == "OPEN"

    # While OPEN, calls without fallback raise CircuitBreakerOpenError immediately
    with pytest.raises(CircuitBreakerOpenError):
        cb.execute(_failing_rpc)

    # Calls with fallback return fallback value while OPEN
    fallback_val = cb.execute(_failing_rpc, fallback=lambda: "graceful_fallback_payload")
    assert fallback_val == "graceful_fallback_payload"
    assert cb.snapshot()["total_short_circuits"] >= 2

    # Wait for recovery cooldown -> HALF_OPEN -> CLOSED on next success
    time.sleep(0.10)
    assert cb.state == "HALF_OPEN"
    recovered = cb.execute(lambda: "recovered_ok")
    assert recovered == "recovered_ok"
    assert cb.state == "CLOSED"


def test_retry_with_exponential_jitter_recovers_from_transient_429() -> None:
    """Verifies exponential backoff with jitter retries transient 429/503 errors and succeeds."""
    attempts = {"count": 0}

    def _flaky_vertex_call() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("429 RESOURCE_EXHAUSTED: Quota exceeded")
        return "gemini_response_ok"

    result = retry_with_exponential_jitter(
        _flaky_vertex_call,
        max_attempts=3,
        base_delay_sec=0.01,
        jitter_max_sec=0.005,
    )
    assert result == "gemini_response_ok"
    assert attempts["count"] == 3


def test_model_fallback_router_degrades_gracefully_under_outage() -> None:
    """Verifies ModelFallbackRouter cascades from gemini-2.5-pro -> gemini-2.5-flash -> deterministic engine."""
    cb = CircuitBreaker(name="test_router_cb", failure_threshold=5, recovery_timeout_sec=10.0)
    router = ModelFallbackRouter(circuit_breaker=cb)
    tried_models = []

    def _always_failing_llm(model_id: str) -> str:
        tried_models.append(model_id)
        raise ConnectionError(f"503 Unavailable on {model_id}")

    outcome = router.execute_with_fallback(
        agent_role="planner",
        model_callable=_always_failing_llm,
        deterministic_fallback=lambda: {"storyboard": "deterministic_fallback_ok"},
    )
    assert outcome["degraded"] is True
    assert outcome["selected_model"] == "deterministic-local-curriculum-engine"
    assert outcome["result"]["storyboard"] == "deterministic_fallback_ok"
    assert "gemini-2.5-pro" in tried_models
    assert "gemini-2.5-flash" in tried_models


def test_pre_llm_pii_redaction_and_compliance_audit_trail() -> None:
    """Verifies before_model_guardrail_callback scrubs PII in-place before the LLM sees the prompt."""

    class _DummyLlmRequest:
        def __init__(self, contents: str) -> None:
            self.contents = contents

    req = _DummyLlmRequest(
        "Generate Weather deck for Scoutmaster Bob at bob.counselor@troop19.org or (978) 555-0199."
    )
    block_res = before_model_guardrail_callback(callback_context=None, llm_request=req)
    assert block_res is None
    assert "bob.counselor@troop19.org" not in req.contents
    assert "(978) 555-0199" not in req.contents
    assert "[REDACTED_EMAIL]" in req.contents
    assert "[REDACTED_PHONE]" in req.contents

    audit_events = get_compliance_audit_events(limit=5)
    assert len(audit_events) >= 1
    latest = audit_events[-1]
    assert latest["action"] == "before_model_invocation"
    assert latest["details"]["pii_redacted_pre_llm"] is True


def test_zero_trust_authentication_and_rate_limiter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies 401/403 enforcement when AUTH_REQUIRED=true and valid X-API-Key / OIDC JWT acceptance."""
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("BSA_API_KEY", "test-capstone-secret-key")
    client = TestClient(app)

    # 1. Missing credentials -> 401 Unauthorized
    r_unauth = client.get("/api/v1/badges")
    assert r_unauth.status_code == 401

    # 2. Invalid X-API-Key -> 403 Forbidden
    r_bad_key = client.get("/api/v1/badges", headers={"X-API-Key": "wrong-key"})
    assert r_bad_key.status_code == 403

    # 3. Valid X-API-Key -> 200 OK
    r_ok_key = client.get("/api/v1/badges", headers={"X-API-Key": "test-capstone-secret-key"})
    assert r_ok_key.status_code == 200
    assert r_ok_key.json()["total_badges"] >= 138

    # 4. Valid OIDC JWT structure -> 200 OK
    header_b64 = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload_b64 = (
        base64.urlsafe_b64encode(
            json.dumps({"sub": "counselor@scouting.org", "exp": time.time() + 3600}).encode()
        )
        .decode()
        .rstrip("=")
    )
    jwt_token = f"{header_b64}.{payload_b64}.sig"
    r_ok_jwt = client.get("/api/v1/badges", headers={"Authorization": f"Bearer {jwt_token}"})
    assert r_ok_jwt.status_code == 200

    # 5. TokenBucketRateLimiter blocks burst overflow
    limiter = TokenBucketRateLimiter(requests_per_minute=60, burst_capacity=3)
    assert limiter.allow_request("client-a") is True
    assert limiter.allow_request("client-a") is True
    assert limiter.allow_request("client-a") is True
    assert limiter.allow_request("client-a") is False


def test_health_readiness_metrics_feedback_and_openapi_contract() -> None:
    """Verifies /health, /readiness, /api/v1/metrics, /api/v1/feedback, prompt manifest, and docs/openapi.yaml."""
    client = TestClient(app)

    h_resp = client.get("/health")
    assert h_resp.status_code == 200
    assert h_resp.json()["status"] == "UP"

    r_resp = client.get("/readiness")
    assert r_resp.status_code == 200
    r_data = r_resp.json()
    assert r_data["status"] == "READY"
    assert r_data["checks"]["session_store"] == "READY"
    assert r_data["checks"]["merit_badge_catalog"] == "READY"

    golden_ext_path = Path(__file__).resolve().parent / "data" / "golden_extensions.json"
    orig_golden_bytes = golden_ext_path.read_bytes() if golden_ext_path.exists() else None
    try:
        fb_post = client.post(
            "/api/v1/feedback",
            json={
                "badge_name": "Weather",
                "session_id": "test_feedback_session",
                "rating": 5,
                "thumbs_up": True,
                "requirement_accuracy_verified": True,
                "comments": "Clear warm vs cold front diagrams for our Troop 19 meeting.",
            },
        )
        assert fb_post.status_code == 200
        assert fb_post.json()["status"] == "RECORDED"
    finally:
        if orig_golden_bytes is not None:
            golden_ext_path.write_bytes(orig_golden_bytes)

    m_resp = client.get("/api/v1/metrics")
    assert m_resp.status_code == 200
    m_data = m_resp.json()
    assert "circuit_breakers" in m_data
    assert m_data["hitl_counselor_feedback"]["total_feedback_count"] >= 1

    # Verify versioned prompt manifest & ModelProvider abstraction
    manifest = load_prompt_manifest()
    assert "coordinator.md" in manifest["prompts"]
    assert "sha256" in manifest["prompts"]["coordinator.md"]
    assert "MeritBadgeCoordinatorAgent" in load_prompt("coordinator.md", variant="control")

    provider = get_model_provider("litellm")
    assert provider.provider_name == "litellm_multi_provider"

    # Verify docs/openapi.yaml exists and is synchronized with live FastAPI routes
    openapi_path = Path(__file__).resolve().parents[1] / "docs" / "openapi.yaml"
    assert openapi_path.exists(), "docs/openapi.yaml must be exported"
    disk_schema = yaml.safe_load(openapi_path.read_text(encoding="utf-8"))
    live_schema = app.openapi()
    assert set(disk_schema["paths"].keys()) == set(live_schema["paths"].keys())
