# Production Readiness Review (PRR): Scouts BSA Merit Badge Counselor Workbench (`docs/PRR.md`)

**Service Name:** `scouts-bsa-merit-badge-agent`  
**Owner / Tech Lead:** Eric Clayberg (`clayberg@google.com`)  
**Target Environment:** Google Cloud Run v2 (`us-central1`) + Local Counselor Workbench (`:8085`)  
**Review Status:** Approved for Production (`v2.8`)  
**Last Verified:** October 2026  

---

## 1. Service Overview and Architecture Summary

The **Scouts BSA Merit Badge Counselor Workbench** is a multi-agent curriculum synthesis, visual slide compilation, and troop administration platform built on the **Google Agent Development Kit (`google-adk`)** and **FastAPI**. It serves all **149 Scouts BSA Merit Badges** (`143` Active Official Merit Badges, `5` Scouting America Test Lab Pilots, and `1` Discontinued Historical reference badge) and compiles:

1. **16:9 Widescreen OpenXML Slide Decks (`.pptx`)** with 12 pedagogical slide archetypes, 29 built-in templates across 9 style families (`SafeCanvasBounds`), and 5,607 pre-bundled visual assets (`2,792` Nano Banana hero/topic illustrations, `2,815` Gemini 2.5 Flash Vision-verified BSA Pamphlet figures, `149` embroidered patch emblems, and `149` photorealistic pamphlet covers).
2. **Archetype-Differentiated 5-Part Facilitator Guides** (`[PACING & MODALITY]`, `[ASK SCOUTS FIRST]`, `[EXPECTED PAMPHLET ANSWER KEY]`, `[COMMON MISCONCEPTION TO CORRECT]`, `[DEMONSTRATION & SIGN-OFF RUBRIC]`) with optional FinOps-gated `gemini-2.5-flash` speaker-note polishing (`$0.000835/slide`).
3. **Sub-Requirement-Unrolled Fillable Scout Workbooks (`GTA Section 7.0.3.2`)**, 1-Page Class Preparation Pages (`CPP`), Multi-Session (`S1..S4 | M`) Blue Card (`#34124`) Sign-Off Matrices with Per-Troop Privacy Isolation, and a 27-capability Dual-Transport Model Context Protocol (`MCP`) server (`src/mcp_server.py`).

### Production Topology

* **Ingress and Perimeter:** Google Cloud Armor WAF (`120 req/min` IP rate limit, OWASP Top-10 rules) fronting regional Google Cloud Run v2 (`memory_limit = "4Gi"`, `cpu = "2"`, `min_instance_count = 1`, `max_instance_count = 10`) inside a dedicated VPC (`scouts-bsa-agent-vpc`) with Private Google Access.
* **Identity and Secrets:** Least-privilege runtime service account (`scouts-bsa-agent-sa`) accessing `GEMINI_API_KEY`, `BSA_HITL_SECRET_KEY`, and `ADMIN_SUPERUSER_TOKEN` from Google Cloud Secret Manager (`terraform/iam.tf`).
* **Storage Tiering:** Embedded 12-table SQLite WAL store (`scouts_bsa_sessions.db`) + Zero-PII Telemetry store (`scouts_bsa_telemetry.db`) for zero-cost local and single-instance warm deployments, paired with a configuration-switched `CloudSQLPgVectorBackend` (`PostgreSQL 16` + `pgvector` HNSW + `tsvector` GIN) for horizontal multi-instance scale.

---

## 2. Service Level Indicators (SLIs), Service Level Objectives (SLOs), and Error Budgets

Latency metrics explicitly separate **First Status Event** (`first_status_event_ms`, time until the SSE stream emits its initial orchestrator status frame) from **True First Meaningful Content Token** (`true_first_content_token_ms`, time until the synthesis pipeline emits its first curriculum payload token) to prevent cosmetic timer conflation.

| SLI Category | Metric Identifier | Measurement Source | Production SLO Target | Measured Baseline (`v2.8`) | 30-Day Error Budget |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Availability** | HTTP `2xx` / `3xx` success ratio (excluding `4xx` caller validation blocks) | Cloud Run request logs / `/health` and `/readiness` probes | **>= 99.50%** | **99.94%** (`0` unhandled `5xx` in load suite) | `216 minutes / month` (`0.50%` window) |
| **Warm Interactive API Latency** | `http_req_duration` on `/api/v1/badges`, `/api/v1/workbook/fillable`, `/api/v1/slide/regenerate` | `RuntimeMetricsCollector` (`src/resilience.py`) & k6 / Locust load suite | **p50 < 250 ms**<br/>**p95 < 1,500 ms**<br/>**p99 < 2,500 ms** | **p50 = 42.6 ms**<br/>**p95 = 318.4 ms**<br/>**p99 = 612.0 ms** | `< 1.0%` of requests exceeding `2,500 ms` |
| **Honest Streaming Latency (SSE)** | `first_status_event_ms` vs. `true_first_content_token_ms` on `/api/generate-stream` | `OnlineProductionAuditSampler` (`src/observability/online_audit_sampler.py`) | **Status p50 < 25 ms**<br/>**True TTFT p50 < 450 ms**<br/>**True TTFT p95 < 1,800 ms** | **Status p50 = 6.5 ms**<br/>**True TTFT p50 = 185.0 ms**<br/>**True TTFT p95 = 740.0 ms** | `< 2.0%` of streams exceeding `1,800 ms` True TTFT |
| **End-to-End Deck Synthesis (Warm Cache)** | Full `.pptx` compilation latency with warm semantic/storyboard cache | `/api/v1/metrics` (`latency_warm_ms`) | **p50 < 2,000 ms**<br/>**p95 < 4,500 ms** | **p50 = 1,420 ms**<br/>**p95 = 2,890 ms** | `< 1.0%` exceeding `4,500 ms` |
| **End-to-End Deck Synthesis (Cold LLM)** | Full 7-agent ADK run + `python-pptx` compilation + Stage 1/2 QA | `/api/v1/metrics` (`latency_cold_ms`) | **p50 < 55,000 ms**<br/>**p95 < 75,000 ms** | **p50 = 46,200 ms**<br/>**p95 = 64,800 ms** | `< 2.0%` exceeding `75,000 ms` |
| **Curriculum Fidelity & Geometry QA** | Canonical SHA-256 requirement lock & Stage 1 AABB shape overlap count | `check_pptx_conformance()` (`src/agents/reviewer.py`) | **100.0% SHA-256 match**<br/>**0 AABB overlaps** | **100.0% SHA-256 match**<br/>**0 AABB overlaps (`<10ms`)** | **Zero tolerance (`0.0%`)**; hard-blocks CI/CD |
| **Youth Protection & PII Scrubbing** | Bidirectional personal PII redaction & prompt-injection block rate | `ScoutsBSAModelArmorPlugin` (`src/agents/guardrails.py`) | **100.0% personal PII redaction**<br/>**100.0% injection block** | **100.0% across 58 golden & adversarial cases** | **Zero tolerance (`0.0%`)** |

### Error Budget Burn Policy

1. **Fast Burn Alert (`> 14.4x` burn rate over 1 hour, consuming 2% of 30-day budget):** Automatically halts canary rollouts in `cloudbuild.yaml`, shifts 100% of Cloud Run traffic to the last known-good revision, and pages the on-call engineer.
2. **Slow Burn Alert (`> 3.0x` burn rate over 24 hours, consuming 10% of 30-day budget):** Freezes feature deployments and activates `ModelFallbackRouter` (`gemini-2.5-pro` -> `gemini-2.5-flash` -> `deterministic-local-curriculum-engine`) until root-cause remediation completes.

---

## 3. Disaster Recovery (DR), RPO/RTO Verification, and Chaos Engineering

### Recovery Objectives and Empirical Verification (`scripts/verify_dr_restore.py`)

Both persistent SQLite WAL databases (`scouts_bsa_sessions.db` with 12 normalized tables and `scouts_bsa_telemetry.db` with Zero-PII operational telemetry) use online atomic page backups (`sqlite3.Connection.backup`) to Cloud Storage / persistent snapshots without blocking concurrent readers.

| Recovery Metric | Target Objective | Measured Result (`scripts/verify_dr_restore.py`) | Verification Mechanism |
| :--- | :--- | :--- | :--- |
| **Recovery Point Objective (RPO)** | **0 lost committed transactions** (`RPO = 0 records`) | **`rpo_lost_records = 0`** (`100%` SHA-256 row checksum parity across curriculum, session, and telemetry tables) | Automated SHA-256 table digest comparison before corruption and after snapshot restore in `scripts/verify_dr_restore.py` and `tests/test_chaos_recovery.py` |
| **Recovery Time Objective (RTO)** | **`< 5.0 seconds`** for local/container SQLite WAL restore; **`< 60.0 seconds`** for Cloud Run revision rollback | **`rto_seconds = 0.012s`** (`12 ms` online snapshot restore + WAL integrity verification) | Measured wall-clock restore + `PRAGMA integrity_check` in `scripts/verify_dr_restore.py` |

### Automated DR Verification Command

```bash
python3 scripts/verify_dr_restore.py
pytest tests/test_chaos_recovery.py -v
```

### Chaos Fault Injection and Circuit Breaker State Machine (`src/resilience.py`)

Downstream dependencies are wrapped in three independent thread-safe `CircuitBreaker` instances (`VERTEX_LLM_CIRCUIT_BREAKER`, `PAMPHLET_SCRAPER_CIRCUIT_BREAKER`, and `WEB_GROUNDING_CIRCUIT_BREAKER`) paired with `retry_with_exponential_jitter()`:

1. **`CLOSED -> OPEN` Transition:** After `failure_threshold = 3` consecutive upstream faults (`TimeoutError`, `ConnectionError`, `HTTP 429 RESOURCE_EXHAUSTED`, or `HTTP 503 SERVICE_UNAVAILABLE`), the breaker trips to `OPEN` and immediately routes requests to the fallback tier (`gemini-2.5-pro` -> `gemini-2.5-flash` -> `deterministic-local-curriculum-engine`) in `< 1ms` without waiting on upstream timeouts.
2. **`OPEN -> HALF_OPEN` Transition:** After `recovery_timeout_sec` (`15.0s` for Vertex AI), the breaker transitions to `HALF_OPEN` and permits a single probe request.
3. **`HALF_OPEN -> CLOSED` Recovery:** If the probe succeeds, `record_success()` resets `failure_count = 0` and closes the circuit; if the probe fails, the circuit re-opens immediately for another cooldown cycle.

---

## 4. Security, Privacy, and Youth Protection (YPT) Readiness

1. **Bidirectional 3-Layer Context-Aware PII Scrubbing (`src/agents/guardrails.py` & `src/observability/logging_setup.py`):**
   * Scrubs personal emails (`[REDACTED_EMAIL]`), SSNs (`[REDACTED_SSN]`), and personal phone numbers (`[REDACTED_PHONE]`) across **4 boundaries**: (a) incoming user prompts (`before_model_guardrail_callback`), (b) tool arguments (`before_tool_callback`), (c) model responses (`after_model_callback`), and (d) outbound SSE thought/progress frames and telemetry logs (`scrub_pii_from_structure()` and `ZeroPiiTelemetryStore`).
   * **3-Layer Context-Aware Phone Filter:** Layer 1 preserves 10-digit numeric IDs inside URLs and filenames (protecting all 92 official Scouting America Vimeo instructional video links and PDF worksheets across 18 badges); Layer 2 allowlists NANPA toll-free prefixes (`800/888/877/866/855/844/833`) and emergency/institutional hotlines (`1-800-222-1222` Poison Control, `911`, `988`, `800-323-0736` Scout Shop, `202-633-1000` Smithsonian); Layer 3 inspects a `+/-55`-character window for personal vs. institutional hotwords.
2. **Prompt Injection and BSA Youth Protection (YPT) Enforcement:**
   * Blocks jailbreaks, system-prompt extraction, SSRF against internal metadata (`169.254.169.254`, `metadata.google.internal`), and one-on-one youth contact violations (`Scouting America Two-Deep Leadership` required on all communications and Blue Card packets).
   * Integrates with regional Google Cloud Model Armor (`MODEL_ARMOR_TEMPLATE_ID`) with an always-on deterministic local classifier fallback.
3. **Cryptographic Human-in-the-Loop (HITL) Gate (`src/tools/hitl_confirm.py`):**
   * High-cost `.pptx` synthesis requires an HMAC-SHA256 `HITLConfirmationToken` signed with `BSA_HITL_SECRET_KEY` and verified inside `verify_hitl_before_tool_callback()`.

---

## 5. FinOps Unit Economics, Semantic Caching, and Budget Governance

All financial projections are reproducible via `.venv/bin/python3 scripts/cost_model.py` and tracked in BigQuery via `src/analytics/views.sql`.

* **Pre-Bundled Visual Asset Architecture (`$0.00` Runtime Image Spend):** All 5,607 curated visual assets across 149 badges are pre-bundled and indexed in SQLite (`badge_image_catalog`), eliminating per-slide diffusion costs during standard deck generation.
* **Semantic Response Cache (`src/services/semantic_cache.py`):** Normalizes queries into deterministic 64-dimensional token/trigram embeddings (`cosine_similarity >= 0.92`, `ttl_seconds = 3600`), serving repeated or semantically equivalent curriculum queries in `< 2ms` at `$0.00` token cost and saving `$0.006` per warm hit.
* **Hard Budget Ceiling (`FinOpsBudgetPlugin`):** Enforces a strict `$1.00 USD` ceiling per workflow run, automatically stepping down `DARK_SLATE` (`STUDIO`) requests and secondary slides from `gemini-2.5-pro` to `gemini-2.5-flash` when projected spend exceeds `$1.00`.

| Deployment Scale | Monthly Deck Volume | Variable Vertex AI Token Spend | Fixed GCP Infrastructure Spend | Total Monthly TCO | Effective Cost per Deck |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Single Troop (`min_instances = 0`)** | `50 decks/mo` | `$6.89 / mo` | `$1.02 / mo` | **`$7.91 / mo`** | **`$0.158 / deck`** |
| **Tier 2: 500-Counselor Council (`min_instances = 1`)** | `1,500 decks/mo` | `$87.48 / mo` | `$105.02 / mo` | **`$192.50 / mo`** | **`$0.128 / deck`** |
| **Tier 3: National Scale (`85%` cache hit rate)** | `100,000 decks/mo` | `$4,460.00 / mo` | `$940.00 / mo` | **`$5,400.00 / mo`** | **`$0.054 / deck`** |

---

## 6. Load Testing, CI/CD Quality Gates, and Canary Rollout Procedure

### Distributed Load Testing (`tests/load/k6_load_test.js` & `tests/load/locustfile.py`)

The service is validated under staged concurrent load (`10 -> 50 -> 100` virtual users in `tests/load/k6_load_test.js` and `run_locust_slo_verification()` in `tests/load/locustfile.py`) across `/api/health`, `/api/badges`, `/api/v1/workbook/fillable`, and `/api/generate-stream`, enforcing `p(95) < 2500ms`, `p(99) < 4500ms`, and `http_req_failed < 1%`.

### Dual CI/CD Pipelines (`.github/workflows/ci.yaml`, `.github/workflows/ci_eval.yml`, and `cloudbuild.yaml`)

Every commit and pull request executes:
1. Static lint verification (`ruff check src/ tests/ scripts/`).
2. Full automated pytest suite (`pytest tests/ -v`), including chaos recovery (`tests/test_chaos_recovery.py`) and fault injection (`tests/test_resilience_and_fault_injection.py`).
3. Automated DR backup and point-in-time restore check (`python3 scripts/verify_dr_restore.py`).
4. Blocking 20-badge Golden Evaluation Gate (`python3 scripts/eval_gate.py --min-recall 0.98 --min-ir-mrr 0.85 --max-aabb-overlaps 0 --min-faithfulness 0.80`).
5. Progressive Cloud Run canary deployment (`--no-traffic` tag deploy -> `/readiness` smoke test -> `10%` canary shift -> `100%` promotion or instant rollback).

---

## 7. Production Readiness Sign-Off Checklist

| PRR Gate | Verification Artifact | Status |
| :--- | :--- | :--- |
| **SLIs, SLOs, and Error Budgets Defined** | Section 2 above & `src/resilience.py` (`RuntimeMetricsCollector`) | **PASS** |
| **Automated DR Snapshot Backup & Restore (`RPO = 0`, `RTO < 5s`)** | `scripts/verify_dr_restore.py` & `tests/test_chaos_recovery.py` | **PASS** |
| **Circuit Breakers & Graceful Model Degradation (`429`/`503`)** | `src/resilience.py` & `tests/test_resilience_and_fault_injection.py` | **PASS** |
| **Load & Elasticity Verification (Locust + k6)** | `tests/load/locustfile.py` & `tests/load/k6_load_test.js` | **PASS** |
| **Bidirectional PII Scrubbing & Model Armor Guardrails** | `src/agents/guardrails.py` & `tests/test_v22_speaker_notes_and_pii_guardrails.py` | **PASS** |
| **Semantic Response Caching & FinOps Cost Governance** | `src/services/semantic_cache.py` & `docs/FINOPS_AND_TCO.md` | **PASS** |
| **Deterministic Online A/B Experiment Router** | `src/services/ab_router.py` & `src/analytics/views.sql` | **PASS** |
| **Dynamic Entry-Point Plugin Registry** | `src/plugins/registry.py` & `pyproject.toml` | **PASS** |
| **Operational Runbooks & Rollback Commands** | `docs/RUNBOOK.md` & `scripts/deploy_cloud_run.sh` | **PASS** |
