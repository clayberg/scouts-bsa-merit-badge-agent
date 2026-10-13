# Operational Runbook (`docs/runbook.md`)

This runbook covers local and Cloud Run operations, health and readiness verification, cache management, circuit-breaker recovery, and troubleshooting for the **Scouts BSA Merit Badge Counselor Workbench** (`v2.6`).

---

## 1. Service Startup & Health Verification

### Start the Local Workbench Server
```bash
./run_local.sh
# Or directly with the virtual environment:
.venv/bin/uvicorn src.server:app --host 0.0.0.0 --port 8080
```

### Verify Liveness & Deep Subsystem Readiness
```bash
# 1. Fast liveness probe (<5ms)
curl -s http://localhost:8080/api/v1/health | jq .

# 2. Deep readiness probe (verifies SQLite WAL, Circuit Breaker CLOSED, and >= 144 badges loaded)
curl -s http://localhost:8080/api/v1/readiness | jq .

# 3. 6-Act Pre-Flight Live Demo Readiness Check (<5 seconds)
.venv/bin/python scripts/verify_live_demo_readiness.py
```

Expected readiness payload:
```json
{
  "status": "ready",
  "checks": {
    "sqlite_wal_store": true,
    "vertex_circuit_breaker_closed": true,
    "badge_catalog_loaded": true,
    "badge_catalog_count": 146
  }
}
```
*(Note: `badge_catalog_count: 146` reflects all `144` official Scouts BSA Merit Badges plus `2` synthetic test stubs used by the automated conformance test suite).*

---

## 2. Visual Asset & Requirement Catalog Maintenance

### Directory Layout & Pre-Cached Inventory
- `data/merit_badge_requirements/*.json`: **144 official Merit Badge requirement & multi-slide topic catalogs** (plus `_index.json` and `_deck_audit_and_cost_report.json`).
- `assets/ai_illustrations/`: **2,297 pre-generated, compressed (`<= 1,024px`, 8-bit PNG) Nano Banana hero and topic illustrations** across all `144` badges.
- `assets/pamphlet_images/`: **4,317 extracted and de-boxed official BSA Pamphlet figures**.
- `assets/badge_emblems/`: **135 transparent RGBA Merit Badge patch emblems**.
- `assets/pamphlet_covers/`: **134 official BSA Merit Badge pamphlet cover images**.

### Clearing Ephemeral Web / Custom AI Image Caches
If a counselor wants to clear temporary web-search or custom on-demand AI images for a specific badge without touching the `2,297` pre-cached hero/topic PNGs or `USER_UPLOAD` photos:
```bash
curl -X DELETE "http://localhost:8080/api/badge/images?badge_name=First%20Aid"
# Or via the v1 cache maintenance endpoint:
curl -s "http://localhost:8080/api/v1/cache/clear?badge_name=First%20Aid" | jq .
```

### Refreshing Real UI Screenshots for Documentation
If you update the UI layout (`ui/index.html`, `ui/styles.css`, `ui/app.js`) and need to regenerate the 5 documentation screenshots in `docs/images/`:
```bash
.venv/bin/python scripts/capture_real_user_guide_screenshots.py
```

---

## 3. Incident Response & Troubleshooting

### Scenario A: Vertex AI Rate-Limit (`HTTP 429`) or Transient Outage (`HTTP 503`)
- **Automatic Mitigation**: `src/resilience.py` wraps all LLM calls in `retry_with_exponential_backoff` (`base_delay=1.0s`, jitter) and a 3-state `CircuitBreaker` (`CLOSED` -> `OPEN` after 3 consecutive failures -> `HALF_OPEN` after `30s` cooldown). When `OPEN`, `call_with_model_fallback` routes requests to `gemini-2.5-flash` or deterministic pre-cached JSON synthesis so deck generation never crashes.
- **Verification**: Check `curl -s http://localhost:8080/api/v1/readiness` to inspect `vertex_circuit_breaker_closed`.

### Scenario B: Stage 1 PPTX Geometry Conformance Failure (`aabb_overlap_count > 0`)
- **Automatic Mitigation**: `QualityReviewerAgent.check_pptx_conformance` (`src/agents/reviewer.py`) inspects every `.pptx` in `<10ms` and triggers up to `MAX_CONFORMANCE_RETRIES = 2` self-healing passes via `_concise_card_body` character-budget compaction (`<= 18` words, `<= 125` chars per card body).
- **Manual Diagnostic**:
  ```bash
  .venv/bin/python -c '
  from src.agents.reviewer import check_pptx_conformance
  print(check_pptx_conformance("deliverables/Weather_BEAUTIFIED_DeepDive_Merit_Badge_Deck.pptx"))
  '
  ```

### Scenario C: Youth Protection (YPT) PII or Prompt Injection Alert
- **Symptom**: `sanitize_text_with_model_armor` returns `allowed: False` with `PROMPT_INJECTION_OR_JAILBREAK_ATTEMPT`, or `src/pii_scrubber.py` replaces youth contact fields with `[REDACTED_EMAIL]`, `[REDACTED_PHONE]`, or `[REDACTED_YOUTH_NAME]`.
- **Action**: This is expected defense-in-depth behavior. Inspect structured JSON logs (`event_type: "guardrail_interception"`) to confirm zero raw PII was emitted.

---

## 4. Pre-Release & Regression Verification Commands

```bash
# 1. Lint & static analysis
.venv/bin/ruff check src/ tests/ scripts/

# 2. Full 53-test pytest suite (conformance, A2UI, memory, PII scrubber, resilience, tools)
.venv/bin/pytest -q

# 3. 12-Badge Golden Evaluation Gate
.venv/bin/python scripts/eval_gate.py
```
