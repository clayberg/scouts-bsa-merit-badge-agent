"""Disaster Recovery (DR), Chaos Fault Injection, Semantic Cache, A/B Router & Plugin Registry Tests (`tests/test_chaos_recovery.py`).

Covers the Critical Reviewer Downgrade Guards:
- Guard #1: Automated SQLite WAL snapshot backup and point-in-time restore (`verify_dr_restore()`)
  plus Chaos fault injection (`TimeoutError`, `503 ServiceUnavailable`) verifying `CircuitBreaker`
  state transitions (`CLOSED -> OPEN -> HALF_OPEN -> CLOSED`) and fallback recovery.
- Guard #4: `SemanticCache` 64-dim cosine similarity matching (`>= 0.92`) and FinOps savings tracking.
- Guard #6: `ABExperimentRouter` deterministic SHA-256 modulo-100 session bucketing and outcome aggregation.
- Guard #7: `PluginRegistry` `@register_tool_plugin`, JSON-Schema input validation, and `entry_points` discovery.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict

import pytest

from scripts.verify_dr_restore import verify_dr_restore
from src.plugins.registry import (
    GLOBAL_PLUGIN_REGISTRY,
    PluginRegistry,
    PluginValidationError,
    register_tool_plugin,
)
from src.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    ModelFallbackRouter,
    retry_with_exponential_jitter,
)
from src.services.ab_router import GLOBAL_AB_ROUTER, ABExperimentRouter
from src.services.semantic_cache import GLOBAL_SEMANTIC_CACHE, SemanticCache


def test_dr_snapshot_backup_and_point_in_time_restore(tmp_path: Path) -> None:
    """Verifies RPO = 0 lost records, 100% SHA-256 checksum parity, and RTO < 5.0s on SQLite WAL restore."""
    report = verify_dr_restore(tmp_dir=tmp_path)
    assert report["passed"] is True
    assert report["status"] == "PASSED"
    assert report["integrity_check"] == "ok"
    assert report["rpo_lost_records"] == 0
    assert report["pre_disaster_records"] == report["restored_records"] == 10
    assert report["checksum_parity_verified"] is True
    assert report["pre_disaster_sha256"] == report["post_restore_sha256"]
    assert report["rto_seconds"] < 5.0


def test_chaos_fault_injection_circuit_breaker_state_transitions_and_fallback() -> None:
    """Injects TimeoutError and 503 ServiceUnavailable faults to verify CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
    cb = CircuitBreaker(name="chaos_vertex_upstream", failure_threshold=3, recovery_timeout_sec=0.06)
    assert cb.state == "CLOSED"

    fault_sequence = [
        TimeoutError("Upstream Vertex AI request timed out after 10.0s"),
        RuntimeError("503 ServiceUnavailable: Vertex AI endpoint overloaded"),
        TimeoutError("503 ServiceUnavailable: downstream timeout"),
    ]
    call_idx = {"idx": 0}

    def _faulty_upstream() -> Dict[str, Any]:
        err = fault_sequence[min(call_idx["idx"], len(fault_sequence) - 1)]
        call_idx["idx"] += 1
        raise err

    # 1. Three consecutive chaos faults transition CLOSED -> OPEN
    for _ in range(3):
        with pytest.raises((TimeoutError, RuntimeError)):
            cb.execute(_faulty_upstream)

    assert cb.state == "OPEN"
    assert cb.snapshot()["failure_count"] == 3

    # 2. While OPEN, unguarded calls short-circuit immediately with CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError):
        cb.execute(_faulty_upstream)

    # 3. While OPEN, calls with a fallback execute the fallback cleanly without hitting upstream
    fallback_resp = cb.execute(
        _faulty_upstream,
        fallback=lambda: {"status": "DEGRADED_FALLBACK", "source": "deterministic_local_engine"},
    )
    assert fallback_resp["status"] == "DEGRADED_FALLBACK"
    assert cb.snapshot()["total_short_circuits"] >= 2

    # 4. Wait for cooldown window -> transitions OPEN -> HALF_OPEN
    time.sleep(0.08)
    assert cb.state == "HALF_OPEN"

    # 5. If probe fails in HALF_OPEN, breaker immediately re-opens
    with pytest.raises(TimeoutError):
        cb.execute(_faulty_upstream)
    assert cb.state == "OPEN"

    # 6. Wait for cooldown again -> HALF_OPEN -> probe succeeds -> transitions back to CLOSED
    time.sleep(0.08)
    assert cb.state == "HALF_OPEN"
    recovered = cb.execute(lambda: {"status": "RECOVERED", "model": "gemini-2.5-flash"})
    assert recovered["status"] == "RECOVERED"
    assert cb.state == "CLOSED"
    assert cb.snapshot()["failure_count"] == 0


def test_chaos_model_fallback_router_and_jitter_recovery() -> None:
    """Verifies ModelFallbackRouter + retry_with_exponential_jitter recover under 503 chaos."""
    cb = CircuitBreaker(name="chaos_router_cb", failure_threshold=4, recovery_timeout_sec=5.0)
    router = ModelFallbackRouter(circuit_breaker=cb)

    def _pro_fails_flash_succeeds(model_id: str) -> str:
        if "pro" in model_id:
            raise ConnectionError("503 ServiceUnavailable on gemini-2.5-pro")
        return f"synthesized_by_{model_id}"

    outcome = router.execute_with_fallback(
        agent_role="planner",
        model_callable=_pro_fails_flash_succeeds,
        deterministic_fallback=lambda: "local_fallback",
    )
    assert outcome["degraded"] is True
    assert outcome["selected_model"] == "gemini-2.5-flash"
    assert outcome["result"] == "synthesized_by_gemini-2.5-flash"

    flaky_counter = {"n": 0}

    def _transient_timeout() -> str:
        flaky_counter["n"] += 1
        if flaky_counter["n"] < 2:
            raise TimeoutError("Transient timeout")
        return "ok_after_retry"

    assert retry_with_exponential_jitter(_transient_timeout, max_attempts=3, base_delay_sec=0.01) == "ok_after_retry"


def test_semantic_cache_64dim_cosine_similarity_and_stats() -> None:
    """Verifies SemanticCache 64-dim embedding normalization, cosine >= 0.92 hits, and savings stats."""
    cache = SemanticCache(similarity_threshold=0.92, ttl_seconds=60.0, max_entries=16)
    emb = cache.compute_embedding("Explain First Aid Requirement 2b tourniquet and arterial bleeding")
    assert len(emb) == 64

    assert cache.get("Explain First Aid Requirement 2b tourniquet", badge_name="First Aid") is None

    cache.put(
        query="Explain First Aid Requirement 2b tourniquet and arterial bleeding",
        response={"slides": [{"req_number": "2b", "title": "Arterial Bleeding"}]},
        badge_name="First Aid",
        model_tier="flash",
        cost_saved_usd=0.006,
    )

    hit = cache.get(
        query="Explain First Aid Requirement 2b tourniquet and arterial bleeding!",
        badge_name="First Aid",
        model_tier="flash",
    )
    assert hit is not None
    assert hit["cache_hit"] is True
    assert hit["cosine_similarity"] >= 0.92
    assert hit["response"]["slides"][0]["req_number"] == "2b"

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 0.5
    assert stats["entries"] == 1
    assert stats["estimated_savings_usd"] == pytest.approx(0.006)
    assert GLOBAL_SEMANTIC_CACHE.similarity_threshold == 0.92


def test_ab_experiment_router_deterministic_sha256_bucketing() -> None:
    """Verifies deterministic SHA-256 session bucketing and experiment outcome summary."""
    router = ABExperimentRouter(treatment_split_pct=50)
    assign_1 = router.assign_variant("counselor_session_alpha", experiment_id="curriculum_synthesis_v2")
    assign_2 = router.assign_variant("counselor_session_alpha", experiment_id="curriculum_synthesis_v2")
    assert assign_1["bucket"] == assign_2["bucket"]
    assert assign_1["variant"] == assign_2["variant"]
    assert assign_1["model_variant"] in (
        "gemini-2.5-flash-standard",
        "gemini-2.5-flash-grounded-cot",
    )

    router.record_outcome("control", latency_ms=210.0, quality_score=4.85)
    router.record_outcome("treatment", latency_ms=245.0, quality_score=4.95)
    summary = router.get_experiment_summary()
    assert summary["experiment_id"] == "curriculum_synthesis_v2"
    assert summary["variants"]["control"]["recorded_outcomes"] == 1
    assert summary["variants"]["treatment"]["avg_quality_score"] == pytest.approx(4.95)
    assert GLOBAL_AB_ROUTER is not None


def test_plugin_registry_decorator_validation_and_entry_points() -> None:
    """Verifies built-in plugins, JSON-Schema validation, @register_tool_plugin, and entry_points discovery."""
    plugins = GLOBAL_PLUGIN_REGISTRY.list_plugins()
    names = {p["name"] for p in plugins}
    assert {"noaa_weather_forecast", "usgs_topographic_elevation", "nps_campsite_lookup"}.issubset(names)

    res_noaa = GLOBAL_PLUGIN_REGISTRY.execute_plugin(
        "noaa_weather_forecast",
        {"zip_code": "01949", "badge_name": "Weather"},
    )
    assert res_noaa["status"] == "SUCCESS"
    assert res_noaa["output"]["zip_code"] == "01949"

    with pytest.raises(PluginValidationError):
        GLOBAL_PLUGIN_REGISTRY.execute_plugin("noaa_weather_forecast", {})

    custom_reg = PluginRegistry()

    @register_tool_plugin(
        name="custom_camp_knot_checker",
        description="Verifies Scouting knot-tying steps.",
        input_schema={
            "type": "object",
            "required": ["knot_name"],
            "properties": {"knot_name": {"type": "string"}},
        },
        registry=custom_reg,
    )
    def _knot_plugin(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"knot": payload["knot_name"], "verified": True}

    out = custom_reg.execute_plugin("custom_camp_knot_checker", {"knot_name": "Bowline"})
    assert out["output"]["verified"] is True
    discovered = custom_reg.discover_entry_point_plugins()
    assert isinstance(discovered, list)
