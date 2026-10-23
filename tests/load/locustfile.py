#!/usr/bin/env python3
"""Locust & Concurrent Counselor SLO Load Test Suite (`tests/load/locustfile.py`).

Provides both:
1. A native `locust` load-testing user (`MeritBadgeCounselorLoadUser`) simulating
   concurrent Merit Badge Counselors exercising `/health`, `/api/v1/badges`,
   `/api/v1/workflow/run` (`/api/v1/deck/generate`), `/api/v1/slide/regenerate`
   (`/api/v1/co-design/edit-slide`), and `/mcp` JSON-RPC 2.0.
2. A self-contained `run_locust_slo_verification()` harness (invokable without a live
   external Locust cluster) that asserts p95 latency SLOs and zero error rates.
"""

from __future__ import annotations

import concurrent.futures
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from locust import HttpUser, between, task  # type: ignore
except ImportError:  # pragma: no cover - fallback when locust package is not installed in venv

    class HttpUser:  # type: ignore[no-redef]
        wait_time = None
        client: Any = None

    def between(min_wait: float, max_wait: float) -> Any:
        return (min_wait, max_wait)

    def task(weight: int = 1) -> Any:
        def _decorator(fn: Any) -> Any:
            fn._locust_weight = weight
            return fn

        return _decorator


class MeritBadgeCounselorLoadUser(HttpUser):
    """Locust user persona simulating a Merit Badge Counselor preparing a troop clinic."""

    wait_time = between(0.2, 1.0)

    @task(4)
    def check_health_and_readiness(self) -> None:
        self.client.get("/health", name="/health")
        self.client.get("/readiness", name="/readiness")

    @task(3)
    def browse_144_badge_catalog(self) -> None:
        self.client.get("/api/v1/badges", name="/api/v1/badges")

    @task(2)
    def invoke_mcp_jsonrpc(self) -> None:
        self.client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            name="/mcp [tools/list]",
        )

    @task(1)
    def generate_deck_and_co_design_slide(self) -> None:
        self.client.post(
            "/api/v1/workflow/run",
            json={
                "badge_name": "First Aid",
                "depth_mode": "Standard Deck",
                "beautification_tier": "BEAUTIFIED",
                "enable_deep_research": False,
            },
            name="/api/v1/deck/generate",
        )
        self.client.post(
            "/api/v1/slide/regenerate",
            json={
                "badge_name": "First Aid",
                "slide_index": 1,
                "slide_data": {
                    "req_number": "1a",
                    "title": "First Aid Hurry Cases",
                    "archetype": "SPLIT_VISUAL_EXPLAINER",
                    "bullet_points": ["Check scene safety", "Call 911 immediately"],
                },
                "visual_source_mode": "pamphlet",
            },
            name="/api/v1/co-design/edit-slide",
        )


def _percentile(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(round((pct / 100.0) * (len(sorted_vals) - 1)))))
    return round(sorted_vals[idx], 2)


def run_locust_slo_verification(concurrency: int = 8, total_requests: int = 24) -> Dict[str, Any]:
    """Executes the Counselor load mix against FastAPI TestClient and verifies p95 SLO thresholds."""
    from fastapi.testclient import TestClient
    from src.server import app

    client = TestClient(app)
    latencies_ms: List[float] = []
    errors = 0

    def _worker(i: int) -> float:
        t0 = time.perf_counter()
        mod = i % 4
        if mod == 0:
            r = client.get("/health")
        elif mod == 1:
            r = client.get("/api/v1/badges")
        elif mod == 2:
            r = client.post("/mcp", json={"jsonrpc": "2.0", "id": i, "method": "tools/list", "params": {}})
        else:
            r = client.post(
                "/api/v1/hitl/confirm",
                json={"badge_name": "Weather", "slide_count": 20, "approved": True},
            )
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        return (time.perf_counter() - t0) * 1000.0

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = [pool.submit(_worker, i) for i in range(total_requests)]
        for f in concurrent.futures.as_completed(futs):
            try:
                latencies_ms.append(f.result())
            except Exception:
                errors += 1

    sorted_lat = sorted(latencies_ms)
    p95 = _percentile(sorted_lat, 95)
    return {
        "status": "PASSED" if errors == 0 and p95 < 2500.0 else "FAILED",
        "concurrency": concurrency,
        "total_requests": total_requests,
        "errors": errors,
        "p50_ms": _percentile(sorted_lat, 50),
        "p95_ms": p95,
        "p99_ms": _percentile(sorted_lat, 99),
        "slo_p95_target_ms": 2500.0,
    }


if __name__ == "__main__":
    print(json.dumps(run_locust_slo_verification(), indent=2))
