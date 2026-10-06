#!/usr/bin/env python3
"""Concurrent Load & Latency Benchmark Suite (`tests/load/load_test.py`).

Simulates concurrent Counselor Workbench requests against the FastAPI server
endpoints (`/health`, `/readiness`, `/api/v1/badges`, `/api/v1/hitl/confirm`,
and `/api/v1/workflow/run`) using a thread pool, and writes p50 / p95 / p99
latency and throughput telemetry to `deliverables/load_test_report.json`.
"""

import concurrent.futures
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from src.server import app  # noqa: E402


def _percentile(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(round((pct / 100.0) * (len(sorted_vals) - 1)))))
    return round(sorted_vals[idx], 2)


def run_concurrent_load_benchmark(
    total_api_requests: int = 40,
    concurrency: int = 8,
    workflow_runs: int = 4,
) -> Dict[str, Any]:
    """Executes concurrent API and workflow requests and reports p50/p95/p99 latency."""
    client = TestClient(app)
    api_latencies_ms: List[float] = []
    api_errors = 0

    def _single_api_call(i: int) -> float:
        t0 = time.perf_counter()
        if i % 3 == 0:
            r = client.get("/readiness")
        elif i % 3 == 1:
            r = client.get("/api/v1/badges")
        else:
            r = client.post(
                "/api/v1/hitl/confirm",
                json={"badge_name": "Weather", "slide_count": 20, "approved": True},
            )
        if r.status_code != 200:
            raise RuntimeError(f"Unexpected HTTP {r.status_code}")
        return (time.perf_counter() - t0) * 1000.0

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = [pool.submit(_single_api_call, i) for i in range(total_api_requests)]
        for fut in concurrent.futures.as_completed(futs):
            try:
                api_latencies_ms.append(fut.result())
            except Exception:
                api_errors += 1
    api_wall_sec = max(0.001, time.perf_counter() - t_start)

    wf_latencies_ms: List[float] = []
    badges = ["First Aid", "Weather", "Camping", "Citizenship in the Nation"]

    def _single_workflow_call(idx: int) -> float:
        t0 = time.perf_counter()
        b_name = badges[idx % len(badges)]
        r = client.post(
            "/api/v1/workflow/run",
            json={
                "badge_name": b_name,
                "depth_mode": "Standard Deck",
                "beautification_tier": "STANDARD",
                "enable_deep_research": False,
                "session_id": f"load_test_{idx}",
            },
        )
        if r.status_code != 200:
            raise RuntimeError(f"Workflow HTTP {r.status_code}")
        return (time.perf_counter() - t0) * 1000.0

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, workflow_runs)) as pool:
        wf_futs = [pool.submit(_single_workflow_call, i) for i in range(workflow_runs)]
        for fut in concurrent.futures.as_completed(wf_futs):
            wf_latencies_ms.append(fut.result())

    api_sorted = sorted(api_latencies_ms)
    wf_sorted = sorted(wf_latencies_ms)

    report = {
        "status": "PASSED" if api_errors == 0 else "FAILED",
        "concurrency_workers": concurrency,
        "api_control_plane": {
            "total_requests": total_api_requests,
            "error_count": api_errors,
            "throughput_rps": round(total_api_requests / api_wall_sec, 2),
            "p50_ms": _percentile(api_sorted, 50),
            "p95_ms": _percentile(api_sorted, 95),
            "p99_ms": _percentile(api_sorted, 99),
        },
        "workflow_deck_generation": {
            "total_workflows": workflow_runs,
            "p50_ms": _percentile(wf_sorted, 50),
            "p95_ms": _percentile(wf_sorted, 95),
            "p99_ms": _percentile(wf_sorted, 99),
        },
    }

    out_path = PROJECT_ROOT / "deliverables" / "load_test_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    res = run_concurrent_load_benchmark()
    print(json.dumps(res, indent=2))
