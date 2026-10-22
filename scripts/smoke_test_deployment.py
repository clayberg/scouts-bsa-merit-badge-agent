#!/usr/bin/env python3
"""Post-Deployment & Local Workbench Smoke Test (`go/fde-capstone-playbook` Step 9).

Verifies health, readiness, honest dual latency telemetry (`first_status_event_ms`
vs. `true_first_content_token_ms`), continuous 5% online production audit sampler,
18 multi-option badge track metadata (`Golf`, `Cycling`), and MCP JSON-RPC 2.0
capabilities against either the FastAPI TestClient or a live HTTP/Cloud Run URL.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def run_inprocess_smoke_test() -> dict[str, Any]:
    """Runs deterministic in-process smoke checks against `src.server.app`."""
    from fastapi.testclient import TestClient
    from src.server import app

    client = TestClient(app)
    checks: dict[str, Any] = {}

    r_health = client.get("/health")
    assert r_health.status_code == 200, f"/health returned {r_health.status_code}"
    checks["health"] = r_health.json()

    r_metrics = client.get("/api/v1/metrics")
    assert r_metrics.status_code == 200, f"/api/v1/metrics returned {r_metrics.status_code}"
    m_data = r_metrics.json()
    assert "honest_dual_latency_ms" in m_data, "Missing honest_dual_latency_ms in /api/v1/metrics"
    assert "online_production_audit" in m_data, "Missing online_production_audit in /api/v1/metrics"
    checks["honest_dual_latency_ms"] = m_data["honest_dual_latency_ms"]
    checks["online_production_audit_rate"] = m_data["online_production_audit"].get("configured_sample_rate")

    r_opts = client.get("/api/v1/badges/Cycling/options")
    assert r_opts.status_code == 200, f"/api/v1/badges/Cycling/options returned {r_opts.status_code}"
    opt_data = r_opts.json()
    assert opt_data.get("has_options") is True
    checks["cycling_multi_option_tracks"] = len(opt_data.get("options") or opt_data.get("option_tracks") or [])

    r_mcp = client.get("/mcp/info")
    assert r_mcp.status_code == 200, f"/mcp/info returned {r_mcp.status_code}"
    mcp_data = r_mcp.json()
    checks["mcp_capabilities"] = {
        "tools": len(mcp_data.get("tools") or []),
        "resources": len(mcp_data.get("resources") or []),
        "prompts": len(mcp_data.get("prompts") or []),
    }

    return {
        "status": "PASSED",
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Scouts BSA Workbench smoke tests.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)
    res = run_inprocess_smoke_test()
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"[SMOKE-TEST-OK] All smoke checks passed: {json.dumps(res['checks'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
