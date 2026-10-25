# Operational Runbook: Scouts BSA Merit Badge Counselor Workbench (`docs/RUNBOOK.md`)

This runbook covers local setup, Google Cloud deployment via Terraform and Cloud Build, health and readiness checks, automated deployment smoke testing, Super-User Admin maintenance routes, incident triage playbooks, zero-code model deprecation cutovers, SQLite backups, and Cloud Run revision rollbacks.

---

## 1. Local operations

### 1.1 Starting the Material 3 Counselor Workbench
```bash
# Start the FastAPI / Material 3 Counselor Workbench (:8080 / :8085)
./run_local.sh

# Or start directly via uvicorn:
.venv/bin/uvicorn src.server:app --host 0.0.0.0 --port 8080
```

### 1.2 Checking health, readiness, smoke tests, runtime metrics, and Admin diagnostics locally
```bash
# 1. Container liveness probe (expects HTTP 200 {"status": "UP"})
curl -fsS http://127.0.0.1:8080/health | jq .

# 2. Deep dependency readiness probe (checks 12-table SQLite store, 149-badge catalog, policy JSON files, circuit breakers)
curl -fsS http://127.0.0.1:8080/readiness | jq .

# 3. Automated deployment smoke test suite (/health, /readiness, /api/badges, /api/v1/mcp/manifest, UI root)
.venv/bin/python3 scripts/smoke_test_deployment.py --base-url http://127.0.0.1:8080

# 4. Runtime telemetry, Honest Dual Latency percentiles (first_status_event_ms vs true_first_content_token_ms),
#    5% OnlineProductionAuditSampler summary, and compliance audit events
curl -fsS http://127.0.0.1:8080/api/v1/metrics | jq .
curl -fsS http://127.0.0.1:8080/api/v1/telemetry/latency-breakdown | jq .
curl -fsS http://127.0.0.1:8080/api/v1/eval/online-audit-summary | jq .

# 5. In-App Documentation Viewer catalog (2 User Docs + 10 Engineering Docs)
curl -fsS http://127.0.0.1:8080/api/v1/docs | jq .

# 6. Super-User Admin Console 144-badge asset health matrix and Zero-PII telemetry summary
#    (See docs/ADMIN_GUIDE.md for full UI and API documentation)
curl -fsS http://127.0.0.1:8080/api/v1/admin/diagnostics/assets | jq .
curl -fsS http://127.0.0.1:8080/api/v1/admin/telemetry/summary | jq .

# 7. Admin maintenance: verify/repair 144 pamphlet covers & emblems, purge temp web-search cache,
#    reset circuit breakers, and export a downloadable Zero-PII diagnostic snapshot
curl -fsS -X POST http://127.0.0.1:8080/api/v1/admin/maintenance/repair-covers | jq .
curl -fsS -X POST http://127.0.0.1:8080/api/v1/admin/maintenance/purge-temp-cache | jq .
curl -fsS -X POST http://127.0.0.1:8080/api/v1/admin/circuit-breakers/reset | jq .
curl -fsS http://127.0.0.1:8080/api/v1/admin/maintenance/snapshot -o deliverables/admin_zero_pii_snapshot.json
```

---

## 2. Google Cloud provisioning and CI/CD deployment

### 2.1 Step 1: Provision infrastructure with Terraform (`terraform/`)
`terraform/main.tf` and `terraform/iam.tf` create the dedicated least-privilege service accounts (`scouts-bsa-agent-sa`), IAM bindings, custom VPC (`scouts-bsa-agent-vpc`), private subnet with Private Google Access and flow logs, Cloud Armor WAF policy (`scouts-bsa-agent-cloud-armor-waf`), Secret Manager secrets (`gemini-api-key`, `bsa-hitl-secret-key`), versioned Cloud Storage bucket, and Cloud Run v2 service (`memory_limit = "4Gi"`, `min_instance_count = 1`, `max_instance_count = 10`).

```bash
cd terraform
terraform init
terraform plan -var="project_id=${GOOGLE_CLOUD_PROJECT}" -var="region=us-central1"
terraform apply -var="project_id=${GOOGLE_CLOUD_PROJECT}" -var="region=us-central1"
```

### 2.2 Step 2: Populate Secret Manager secrets
Store API keys and HMAC signing secrets in Secret Manager rather than git:

```bash
printf "%s" "${GEMINI_API_KEY}" | gcloud secrets versions add gemini-api-key \
  --project="${GOOGLE_CLOUD_PROJECT}" --data-file=-

openssl rand -hex 32 | gcloud secrets versions add bsa-hitl-secret-key \
  --project="${GOOGLE_CLOUD_PROJECT}" --data-file=-
```

### 2.3 Step 3: Run the Cloud Build canary pipeline (`cloudbuild.yaml`)
`cloudbuild.yaml` runs `ruff check`, `pytest tests/` (`88/88` passing automated tests with `0` warnings), load testing (`tests/load/load_test.py` and `tests/load/locustfile.py`), and the 20-badge golden evaluation suite (`scripts/run_eval.py` and `scripts/eval_gate.py`). If any check fails, the build stops before touching Cloud Run. When all checks pass, it deploys a `canary` revision at `10%` traffic, checks `/readiness`, and promotes the revision to `100%` (or rolls back automatically if the canary probe fails):

```bash
gcloud builds submit --config=cloudbuild.yaml --project="${GOOGLE_CLOUD_PROJECT}"
```

---

## 3. Incident triage playbooks

### Playbook A: Vertex AI `429 RESOURCE_EXHAUSTED` or `503 UNAVAILABLE`
- **Symptoms**: `/api/v1/metrics` shows `circuit_breakers.vertex_ai_gemini.failure_count > 0` or `state == "OPEN"`.
- **Automatic handling**:
  1. `retry_with_exponential_jitter()` (`src/resilience.py`) retries transient errors with exponential backoff and random jitter.
  2. After 3 consecutive failures, `VERTEX_LLM_CIRCUIT_BREAKER` opens for 15 seconds, and `ModelFallbackRouter` steps down from `gemini-2.5-pro` to `gemini-2.5-flash` to `deterministic-local-curriculum-engine`. Requests continue returning valid `.pptx` decks instead of HTTP 500 errors.
- **Operator steps**:
  - Check current circuit breaker status and reset if needed:
    ```bash
    curl -s http://127.0.0.1:8080/readiness | jq '.checks.circuit_breakers'
    curl -s -X POST http://127.0.0.1:8080/api/v1/admin/circuit-breakers/reset | jq .
    ```
  - If `gemini-2.5-pro` quota is exhausted in `us-central1`, route planner and reviewer calls to Flash via environment variable:
    ```bash
    gcloud run services update scouts-bsa-merit-badge-agent \
      --region=us-central1 \
      --update-env-vars="BSA_PLANNER_MODEL=gemini-2.5-flash"
    ```

### Playbook B: Stage 1 AABB shape overlap or text overflow alert
- **Symptoms**: `check_pptx_conformance()` reports `aabb_overlap_count > 0` or `scripts/eval_gate.py` exits with code `1`.
- **Automatic handling**: `BSABrandAndSafetyReviewAgent` runs in a bounded `LoopAgent` (`max_iterations=3`) that passes overlap coordinates back to `PowerPointBuilderAgent` (`_compute_fitting_font_size()`) to reduce font sizes toward the `12.0pt` floor.
- **Operator steps**:
  - Run the evaluation gate locally to see which badge and slide triggered the geometry issue:
    ```bash
    .venv/bin/python3 scripts/run_eval.py
    cat deliverables/eval_gate_report.json | jq '.badge_benchmarks[] | select(.aabb_overlap_count > 0)'
    ```

### Playbook C: Model Armor prompt injection or Youth Protection block (`400 Bad Request`)
- **Symptoms**: Caller receives `MODEL_ARMOR_PROMPT_BLOCKED` and `/api/v1/metrics` records `guardrail_status == "BLOCKED"`.
- **Operator steps**:
  - Inspect recent compliance events:
    ```bash
    curl -s http://127.0.0.1:8080/api/v1/metrics | jq '.recent_compliance_audit_events'
    ```
  - Check whether a regex rule in `src/agents/guardrails.py` (`_PROMPT_INJECTION_PATTERNS` or `_UNSAFE_SCOUTING_PATTERNS`) or `config/model_armor_security_policy.json` matched valid curriculum text.

### Playbook D: Speaker Notes AI Polish FinOps & SQLite cache triage (`POST /api/v1/slide/estimate-polish-cost` & `/polish-notes`)
- **Symptoms**: Clicking `✨ AI Polish Slide` or `✨ Polish Entire Deck` returns `polish_source == "PROCEDURAL_STUDIO_POLISH"` instead of `"GEMINI_FLASH"`, or a counselor reports stale cached speaker notes.
- **Automatic handling**:
  1. Before polishing, `POST /api/v1/slide/estimate-polish-cost` calculates the exact `gemini-2.5-flash` (`thinking_budget=0`) token and USD cost (`$0.000835/slide` uncached; `$0.00` for slides cached in SQLite `polished_speaker_notes`).
  2. `_invoke_gemini_flash_polish_sync()` (`src/server.py`) tries four credential paths in order: Vertex AI ADC (`global` and `us-central1`), Vertex AI Express key (`AQ.*`), standard Gemini API key (`AIza*`), and the Local-to-Cloud-Run Bridge. If all cloud paths are unavailable, `_synthesize_studio_narrative_script()` produces a slide-unique `[SAY]` / `[DEMONSTRATE]` / `[ASK SCOUTS]` script at `$0.00` (`PROCEDURAL_STUDIO_POLISH`).
- **Operator steps**:
  - Check the FinOps polish cost estimate and SQLite cache hit count for a slide:
    ```bash
    curl -s -X POST http://127.0.0.1:8080/api/v1/slide/estimate-polish-cost \
      -H "Content-Type: application/json" \
      -d '{"badge_name": "First Aid", "slide_index": 0, "storyboard_slides": [{"req_number": "1", "title": "First Aid Kit"}]}' | jq .
    ```
  - Force-refresh a slide's polished speaker script bypassing the SQLite cache (`force_refresh: true`):
    ```bash
    curl -s -X POST http://127.0.0.1:8080/api/v1/slide/polish-notes \
      -H "Content-Type: application/json" \
      -d '{"badge_name": "First Aid", "slide_index": 0, "force_refresh": true, "slide_data": {"req_number": "1", "title": "First Aid Kit"}}' | jq '{polish_source, polish_model_label, cache_hit, fallback_reason}'
    ```
  - Inspect cached polished scripts in `scouts_bsa_sessions.db`:
    ```bash
    sqlite3 scouts_bsa_sessions.db "SELECT badge_name, COUNT(*) AS cached_slides FROM polished_speaker_notes GROUP BY badge_name;"
    ```

### Playbook E: Google Slides export diagnostics (`GET /api/v1/slide/export-gslides/account-info` & `POST /api/v1/slide/export-gslides`)
- **Symptoms**: Clicking `🟨 Open in Google Slides` returns `status == "AUTH_GUIDED_IMPORT"` instead of `"SUCCESS"`, or the exported deck is not shared with the counselor's target email address.
- **Automatic handling**:
  - `api_export_slide_deck_to_google_slides()` (`src/server.py`) walks a 4-tier authentication waterfall:
    1. Browser OAuth 2.0 `user_access_token` (`drive.file` scope) via Google Drive v3 Multipart REST upload (`application/vnd.google-apps.presentation`).
    2. `GOOGLE_DRIVE_ACCESS_TOKEN` or Google Application Default Credentials (`GOOGLE_ADC` / `GCLOUD_CLI`).
    3. Workstation `gdrive` CLI (`/google/bin/releases/gemini-agents-gdrive/gdrive mutate upload` + `share --email <share_with_email> --role writer`).
    4. Guided import fallback (`status: "AUTH_GUIDED_IMPORT"`), which returns `pptx_download_url` and opens Google AccountChooser so the counselor can import the `.pptx` in two clicks.
- **Operator steps**:
  - Check workstation/server Google account detection and `gdrive` CLI readiness:
    ```bash
    curl -s http://127.0.0.1:8080/api/v1/slide/export-gslides/account-info | jq .
    ```
  - Test direct Google Slides conversion and sharing from the command line:
    ```bash
    curl -s -X POST http://127.0.0.1:8080/api/v1/slide/export-gslides \
      -H "Content-Type: application/json" \
      -d '{"badge_name": "First Aid", "beautification_tier": "BEAUTIFIED", "share_with_email": "counselor@gmail.com", "use_adc": true}' | jq .
    ```

### Playbook F: Emergency FinOps budget freeze & zero-code model deprecation cutover (`config/models.yaml`)
- **Emergency Live Image Freeze**: `FinOpsBudgetPlugin` (`max_budget_usd = $1.00`) automatically steps down `DARK_SLATE` (`STUDIO`) requests to `WARM_CREAM` (`BEAUTIFIED`) using the `3,917` pre-bundled visual assets (`$0.00` image cost). To freeze opt-in `$0.08` Nano Banana studio calls during a budget freeze without redeploying code, set `DISABLE_LIVE_IMAGE_GENERATION=true` or `MAX_WORKFLOW_BUDGET_USD=0.25` in Cloud Run environment variables.
- **Zero-Code Model Deprecation Cutover**:
  1. Update `primary_model` or `fast_model` in `config/models.yaml` (or set `BSA_REASONING_MODEL` / `BSA_FAST_MODEL` environment variables).
  2. Run `.venv/bin/python3 scripts/run_eval.py` to verify `Recall@3 == 1.0000`, `0` requirement drift, and `100%` AABB slide geometry conformance on the new model.
  3. Deploy the updated revision with 10% canary traffic on Cloud Run v2 before promoting to 100%.

---

## 4. Rollback, secret rotation, and SQLite backup

### 4.1 One-command Cloud Run revision rollback
To shift 100% of traffic back to the previous revision:

```bash
PREV_REVISION=$(gcloud run revisions list \
  --service=scouts-bsa-merit-badge-agent \
  --region=us-central1 \
  --sort-by="~creationTimestamp" \
  --limit=2 \
  --format="value(metadata.name)" | tail -n 1)

gcloud run services update-traffic scouts-bsa-merit-badge-agent \
  --region=us-central1 \
  --to-revisions="${PREV_REVISION}=100"
```

### 4.2 Rotating `GEMINI_API_KEY` or `BSA_HITL_SECRET_KEY`
1. Add a new secret version in Secret Manager:
   ```bash
   openssl rand -hex 32 | gcloud secrets versions add bsa-hitl-secret-key --data-file=-
   ```
2. Trigger a Cloud Run revision update so instances load `versions/latest`:
   ```bash
   gcloud run services update scouts-bsa-merit-badge-agent \
     --region=us-central1 \
     --update-labels="secret-rotated-at=$(date +%s)"
   ```

### 4.3 Backing up and restoring the SQLite session and Zero-PII telemetry stores
Use SQLite's online `.backup` command to snapshot both `scouts_bsa_sessions.db` (all 9 tables: `sessions` / `counselor_sessions`, `events`, `pamphlet_Requirement_chunks` / `pamphlet_vector_memory`, `counselor_feedback` / `hitl_feedback`, `badge_image_catalog`, `polished_speaker_notes`, `counselor_workspaces`, `counselor_favorites`, `user_preferences`, and `compliance_attestation_ledger`) and `scouts_bsa_telemetry.db` (`ZeroPiiTelemetryStore` deck runs, image swaps, stage latencies, and `OnlineProductionAuditSampler` samples) without locking active readers:

```bash
# Create online backups of both SQLite databases
sqlite3 scouts_bsa_sessions.db ".backup 'deliverables/scouts_bsa_sessions_backup.db'"
sqlite3 scouts_bsa_telemetry.db ".backup 'deliverables/scouts_bsa_telemetry_backup.db'"

# Restore from backups
cp deliverables/scouts_bsa_sessions_backup.db scouts_bsa_sessions.db
cp deliverables/scouts_bsa_telemetry_backup.db scouts_bsa_telemetry.db
```
