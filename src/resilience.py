"""Resilience patterns: Circuit Breaker, Exponential Backoff with Jitter, Model Fallback Router, and Telemetry.

Protects downstream calls to Vertex AI Gemini / Imagen, Scouting.org pamphlet servers,
and grounded web search against cascading timeouts, HTTP 429 quota exhaustion, and
HTTP 503 service unavailability.
"""

import json
import random
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

from src.config import PROJECT_ROOT, get_model_provider
from src.observability.logging_setup import logger

T = TypeVar("T")


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a call is rejected because the circuit breaker is in the OPEN state."""


class CircuitBreaker:
    """Thread-safe three-state Circuit Breaker (`CLOSED` -> `OPEN` -> `HALF_OPEN`)."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_sec: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_timeout_sec = max(0.05, float(recovery_timeout_sec))
        self._lock = threading.Lock()
        self._state: str = "CLOSED"
        self._failure_count: int = 0
        self._last_failure_ts: float = 0.0
        self._total_short_circuits: int = 0
        self._total_successes: int = 0

    @property
    def state(self) -> str:
        with self._lock:
            self._check_half_open_transition_unlocked()
            return self._state

    def _check_half_open_transition_unlocked(self) -> None:
        if self._state == "OPEN":
            if (time.monotonic() - self._last_failure_ts) >= self.recovery_timeout_sec:
                self._state = "HALF_OPEN"

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = "CLOSED"
            self._total_successes += 1

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_ts = time.monotonic()
            if self._failure_count >= self.failure_threshold or self._state == "HALF_OPEN":
                self._state = "OPEN"

    def allow_execution(self) -> bool:
        with self._lock:
            self._check_half_open_transition_unlocked()
            if self._state == "OPEN":
                self._total_short_circuits += 1
                return False
            return True

    def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        fallback: Optional[Callable[..., T]] = None,
        **kwargs: Any,
    ) -> T:
        """Executes `func(*args, **kwargs)` guarded by the circuit breaker."""
        if not self.allow_execution():
            logger.warning(
                "CircuitBreaker '%s' is OPEN; short-circuiting call",
                self.name,
                extra={"circuit_breaker": self.name, "state": "OPEN"},
            )
            if fallback is not None:
                return fallback(*args, **kwargs)
            raise CircuitBreakerOpenError(
                f"CircuitBreaker '{self.name}' is OPEN after {self._failure_count} consecutive failures."
            )
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure()
            logger.warning(
                "CircuitBreaker '%s' recorded failure (%d/%d): %s",
                self.name,
                self._failure_count,
                self.failure_threshold,
                exc,
            )
            if fallback is not None and self.state == "OPEN":
                return fallback(*args, **kwargs)
            raise

    def reset(self) -> None:
        with self._lock:
            self._state = "CLOSED"
            self._failure_count = 0
            self._last_failure_ts = 0.0

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            self._check_half_open_transition_unlocked()
            return {
                "name": self.name,
                "state": self._state,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_sec": self.recovery_timeout_sec,
                "total_successes": self._total_successes,
                "total_short_circuits": self._total_short_circuits,
            }


def retry_with_exponential_jitter(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    base_delay_sec: float = 0.05,
    max_delay_sec: float = 1.0,
    jitter_max_sec: float = 0.03,
    retryable_exceptions: tuple = (TimeoutError, ConnectionError, RuntimeError),
    **kwargs: Any,
) -> T:
    """Executes `func` with exponential backoff and random jitter on transient errors."""
    last_exc: Optional[Exception] = None
    for attempt in range(1, max(1, max_attempts) + 1):
        try:
            return func(*args, **kwargs)
        except retryable_exceptions as exc:
            last_exc = exc
            if attempt >= max_attempts:
                break
            sleep_sec = min(
                max_delay_sec,
                base_delay_sec * (2 ** (attempt - 1)) + random.uniform(0.0, jitter_max_sec),
            )
            logger.info(
                "Transient error on attempt %d/%d (%s); retrying in %.3fs",
                attempt,
                max_attempts,
                exc,
                sleep_sec,
            )
            time.sleep(sleep_sec)
    assert last_exc is not None
    raise last_exc


class ModelFallbackRouter:
    """Routes LLM tasks across a primary -> secondary -> deterministic fallback chain."""

    def __init__(self, circuit_breaker: Optional[CircuitBreaker] = None) -> None:
        self.circuit_breaker = circuit_breaker or VERTEX_LLM_CIRCUIT_BREAKER

    def execute_with_fallback(
        self,
        agent_role: str,
        model_callable: Callable[[str], T],
        deterministic_fallback: Callable[[], T],
    ) -> Dict[str, Any]:
        """Attempts execution along the model provider's fallback chain, degrading gracefully if needed."""
        provider = get_model_provider()
        chain = provider.get_fallback_chain(agent_role=agent_role)
        errors: List[str] = []

        for model_id in chain:
            if model_id == "deterministic-local-curriculum-engine":
                val = deterministic_fallback()
                return {
                    "result": val,
                    "selected_model": model_id,
                    "degraded": len(errors) > 0,
                    "fallback_errors": errors,
                }
            if not self.circuit_breaker.allow_execution():
                errors.append(f"{model_id}: circuit_breaker_open")
                continue
            try:
                val = retry_with_exponential_jitter(
                    model_callable,
                    model_id,
                    max_attempts=2,
                    base_delay_sec=0.02,
                )
                self.circuit_breaker.record_success()
                return {
                    "result": val,
                    "selected_model": model_id,
                    "degraded": len(errors) > 0,
                    "fallback_errors": errors,
                }
            except Exception as exc:
                self.circuit_breaker.record_failure()
                errors.append(f"{model_id}: {type(exc).__name__}: {exc}")

        val = deterministic_fallback()
        return {
            "result": val,
            "selected_model": "deterministic-local-curriculum-engine",
            "degraded": True,
            "fallback_errors": errors,
        }


VERTEX_LLM_CIRCUIT_BREAKER = CircuitBreaker(
    name="vertex_ai_gemini",
    failure_threshold=3,
    recovery_timeout_sec=15.0,
)
PAMPHLET_SCRAPER_CIRCUIT_BREAKER = CircuitBreaker(
    name="scouting_org_pamphlet_scraper",
    failure_threshold=3,
    recovery_timeout_sec=20.0,
)
WEB_GROUNDING_CIRCUIT_BREAKER = CircuitBreaker(
    name="google_search_web_grounding",
    failure_threshold=3,
    recovery_timeout_sec=15.0,
)


class RuntimeMetricsCollector:
    """Collects runtime AI telemetry, latency percentiles, FinOps spend, and HITL Counselor feedback."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latencies_ms: List[float] = []
        self._workflow_runs: int = 0
        self._cache_hits: int = 0
        self._total_tokens: int = 0
        self._total_spend_usd: float = 0.0
        self._feedback_items: List[Dict[str, Any]] = []
        self._feedback_file: Path = PROJECT_ROOT / "deliverables" / "counselor_hitl_feedback.jsonl"

    def record_workflow_run(
        self,
        latency_ms: float,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        cache_hit: bool = False,
    ) -> None:
        with self._lock:
            self._workflow_runs += 1
            if cache_hit:
                self._cache_hits += 1
            self._total_tokens += max(0, int(tokens_used))
            self._total_spend_usd = round(self._total_spend_usd + max(0.0, float(cost_usd)), 4)
            self._latencies_ms.append(max(0.1, float(latency_ms)))
            if len(self._latencies_ms) > 500:
                del self._latencies_ms[:-500]

    def record_counselor_feedback(self, feedback: Dict[str, Any]) -> Dict[str, Any]:
        record = {
            "feedback_id": feedback.get("feedback_id") or f"fb-{int(time.time() * 1000)}",
            "badge_name": str(feedback.get("badge_name", "First Aid")),
            "session_id": str(feedback.get("session_id", "a2ui_workbench_session")),
            "rating": max(1, min(5, int(feedback.get("rating", 5)))),
            "thumbs_up": bool(feedback.get("thumbs_up", True)),
            "requirement_accuracy_verified": bool(feedback.get("requirement_accuracy_verified", True)),
            "comments": str(feedback.get("comments", "")).strip(),
            "timestamp_epoch": round(time.time(), 3),
        }
        with self._lock:
            self._feedback_items.append(record)
            try:
                self._feedback_file.parent.mkdir(parents=True, exist_ok=True)
                with self._feedback_file.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record) + "\n")
            except Exception:
                pass
        return record

    def get_feedback_summary(self) -> Dict[str, Any]:
        with self._lock:
            items = list(self._feedback_items)
        if not items:
            return {
                "total_feedback_count": 0,
                "average_rating": 5.0,
                "thumbs_up_ratio": 1.0,
                "recent_feedback": [],
            }
        avg_rating = round(sum(i["rating"] for i in items) / len(items), 2)
        thumbs_up_ratio = round(sum(1 for i in items if i["thumbs_up"]) / len(items), 3)
        return {
            "total_feedback_count": len(items),
            "average_rating": avg_rating,
            "thumbs_up_ratio": thumbs_up_ratio,
            "recent_feedback": items[-10:],
        }

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            lats = sorted(self._latencies_ms)
            runs = self._workflow_runs
            hits = self._cache_hits
            tokens = self._total_tokens
            spend = self._total_spend_usd

        def _pct(p: float) -> float:
            if not lats:
                return 0.0
            idx = min(len(lats) - 1, max(0, int(round((p / 100.0) * (len(lats) - 1)))))
            return round(lats[idx], 2)

        return {
            "workflow_runs_total": runs,
            "cache_hits_total": hits,
            "cache_hit_ratio": round(hits / runs, 3) if runs > 0 else 0.0,
            "latency_ms": {
                "p50": _pct(50),
                "p95": _pct(95),
                "p99": _pct(99),
            },
            "tokens_consumed_total": tokens,
            "cumulative_spend_usd": spend,
            "circuit_breakers": {
                "vertex_ai_gemini": VERTEX_LLM_CIRCUIT_BREAKER.snapshot(),
                "scouting_org_pamphlet_scraper": PAMPHLET_SCRAPER_CIRCUIT_BREAKER.snapshot(),
                "google_search_web_grounding": WEB_GROUNDING_CIRCUIT_BREAKER.snapshot(),
            },
            "hitl_counselor_feedback": self.get_feedback_summary(),
        }


METRICS_COLLECTOR = RuntimeMetricsCollector()
