# Operational runbook: Scouts BSA Merit Badge Counselor Workbench

This runbook covers local setup, Google Cloud deployment via Terraform and Cloud Build, health and readiness checks, incident triage, SQLite backups, and Cloud Run revision rollbacks.

---

## 1. Local operations

### 1.1 Starting the web interfaces
```bash
# Start both the Material 3 Web Workbench (:8085) and Streamlit Workbench (:8501)
./run_local.sh

# Or start only the FastAPI / Material 3 Web Workbench (:8085)
./run_local.sh a2ui

# Or start only the Streamlit Workbench (:8501)
./run_local.sh streamlit
```

### 1.2 Checking health, readiness, and runtime metrics locally
```bash
# 1. Container liveness probe (expects HTTP 200 {"status": "UP"})
curl -fsS http://127.0.0.1:8085/health | jq .

# 2. Deep dependency readiness probe (checks SQLite store, 138-badge catalog, policy JSON files, circuit breakers)
curl -fsS http://127.0.0.1:8085/readiness | jq .

# 3. Runtime telemetry, latency percentiles, and compliance audit events
curl -fsS http://127.0.0.1:8085/api/v1/metrics | jq .
```

---

## 2. Google Cloud provisioning and CI/CD deployment

### 2.1 Step 1: Provision infrastructure with Terraform (`terraform/`)
`terraform/main.tf` creates the service account (`scouts-bsa-agent-sa`), custom VPC (`scouts-bsa-agent-vpc`), private subnet with Private Google Access and flow logs, Cloud Armor WAF policy (`scouts-bsa-agent-cloud-armor-waf`), Secret Manager secrets (`gemini-api-key`, `bsa-hitl-secret-key`), versioned Cloud Storage bucket, and Cloud Run v2 service.

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
`cloudbuild.yaml` runs `ruff check`, `pytest tests/`, and `scripts/eval_gate.py`. If any check fails, the build stops before touching Cloud Run. When all checks pass, it deploys a `canary` revision at `10%` traffic, checks `/readiness`, and promotes the revision to `100%` (or rolls back automatically if the canary probe fails):

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
  - Check current circuit breaker status:
    ```bash
    curl -s http://127.0.0.1:8085/readiness | jq '.checks.circuit_breakers'
    ```
  - If `gemini-2.5-pro` quota is exhausted in `us-central1`, route planner and reviewer calls to Flash via environment variable:
    ```bash
    gcloud run services update scouts-bsa-merit-badge-agent \
      --region=us-central1 \
      --update-env-vars="BSA_PLANNER_MODEL=gemini-2.5-flash"
    ```

### Playbook B: Stage 1 AABB shape overlap or text overflow alert
- **Symptoms**: `check_pptx_conformance()` reports `aabb_overlap_count > 0` or `scripts/eval_gate.py` exits with code `1`.
- **Automatic handling**: `BSABrandAndSafetyReviewAgent` runs in a bounded `LoopAgent` (`max_iterations=3`) that passes overlap coordinates back to `PowerPointBuilderAgent` (`_compute_fitting_font_size()`) to reduce font sizes toward the `13.0pt` floor.
- **Operator steps**:
  - Run the evaluation gate locally to see which badge and slide triggered the geometry issue:
    ```bash
    .venv/bin/python3 scripts/eval_gate.py
    cat deliverables/eval_gate_report.json | jq '.badge_benchmarks[] | select(.aabb_overlap_count > 0)'
    ```

### Playbook C: Model Armor prompt injection or Youth Protection block (`400 Bad Request`)
- **Symptoms**: Caller receives `MODEL_ARMOR_PROMPT_BLOCKED` and `/api/v1/metrics` records `guardrail_status == "BLOCKED"`.
- **Operator steps**:
  - Inspect recent compliance events:
    ```bash
    curl -s http://127.0.0.1:8085/api/v1/metrics | jq '.recent_compliance_audit_events'
    ```
  - Check whether a regex rule in `src/agents/guardrails.py` (`_PROMPT_INJECTION_PATTERNS` or `_UNSAFE_SCOUTING_PATTERNS`) or `config/model_armor_security_policy.json` matched valid curriculum text.

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

### 4.3 Backing up and restoring the SQLite session store
Use SQLite's online `.backup` command to snapshot `.bsa_session_memory.sqlite` without locking active readers:

```bash
# Create online backup
sqlite3 .bsa_session_memory.sqlite ".backup 'deliverables/bsa_session_memory_backup.sqlite'"

# Restore from backup
cp deliverables/bsa_session_memory_backup.sqlite .bsa_session_memory.sqlite
```
