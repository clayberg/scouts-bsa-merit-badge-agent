# Operational Runbook, Deployment & Incident Playbook (`docs/RUNBOOK.md`)

> **Complete Super-User & Operations Reference**: For full documentation of the 3-Tab Super-User Admin Console (`Ctrl+Shift+A`), Catalog Studio overrides, and Slide-Swap Friction Leaderboard, see [`docs/ADMIN_GUIDE.md`](ADMIN_GUIDE.md) and [`docs/finops-billing-and-deployment-guide.md`](finops-billing-and-deployment-guide.md).

---

## 1. One-Command Local Startup (`./run_local.sh`)

To start the full Scouts BSA Merit Badge Counselor Workbench locally:

```bash
./run_local.sh
```

Or directly via `uvicorn`:

```bash
.venv/bin/uvicorn src.server:app --host 0.0.0.0 --port 8080
```

- **Local UI Workbench**: `http://localhost:8080` (or `http://clayberg.c.googlers.com:8080`)
- **OpenAPI 3.1 Interactive Docs**: `http://localhost:8080/docs` (`/openapi.json`, `123` paths)
- **Model Context Protocol (MCP) Manifest**: `http://localhost:8080/api/v1/mcp/manifest` (`22` capabilities)

---

## 2. Health, Readiness & Smoke-Test Verification

1. **Liveness Probe (`GET /health` & `GET /api/v1/health`)**:
   ```bash
   curl -s http://localhost:8080/health | jq .
   ```
   Verifies FastAPI event loop responsiveness, schema version (`1.2.0`), and active model routing.
2. **Deep Dependency Readiness Probe (`GET /readiness` & `GET /api/v1/readiness`)**:
   ```bash
   curl -s http://localhost:8080/readiness | jq .
   ```
   Verifies SQLite WAL read/write health (`scouts_bsa_sessions.db` and `scouts_bsa_telemetry.db`), `144`-badge catalog integrity, and `.pptx` template availability.
3. **Automated Deployment Smoke Test Suite**:
   ```bash
   .venv/bin/python3 scripts/smoke_test_deployment.py --base-url http://localhost:8080
   ```

---

## 3. Cloud Run v2 Deployment (`min-instances=1`) & Terraform IaC

### 3.1 Provisioning Infrastructure with Terraform (`terraform/`)

```bash
cd terraform
terraform init
terraform plan -var="project_id=scouts-bsa-agent-prod" -var="region=us-central1"
terraform apply -var="project_id=scouts-bsa-agent-prod" -var="region=us-central1"
```

Provisions:
- **Cloud Run v2 Service (`google_cloud_run_v2_service.workbench`)** with `min_instance_count = 1` (eliminating cold-start stalls during live classroom and panel demos) and `max_instance_count = 10`.
- **Dedicated Least-Privilege Runtime Service Account (`scouts-bsa-agent-sa`)** scoped strictly to `roles/aiplatform.user`, `roles/secretmanager.secretAccessor`, `roles/logging.logWriter`, and `roles/cloudtrace.agent`.
- **Google Cloud Secret Manager** secrets (`BSA_API_KEY`, `BSA_HITL_SECRET_KEY`, `ADMIN_SUPERUSER_TOKEN`).

### 3.2 CI/CD Pipeline (`cloudbuild.yaml`)

Every deployment executes four sequential quality gates before shifting traffic:
1. Static analysis & secret scan (`scripts/repo_audit.sh`)
2. Unit, conformance, security, and fault-injection test suite (`pytest tests/ -q`, `77/77` passing)
3. 12-Badge Golden Dataset Evaluation Gate (`scripts/run_eval.py`, `Recall@3 = 1.0000`, `0` requirement drift)
4. Container build (`Dockerfile`) and canary rollout to Cloud Run v2 (`--min-instances=1`)

---

## 4. Incident Triage & Operational Playbooks

### Playbook A: Vertex AI `429 RESOURCE_EXHAUSTED` or `503 UNAVAILABLE` Burst (Saturday Merit Badge Midway)
- **Automatic Mitigation**: The 3-state circuit breaker (`CLOSED -> OPEN -> HALF_OPEN`) in `src/agents/coordinator.py` and exponential backoff with jitter automatically catch transient `429`/`503` errors, step down from `gemini-2.5-pro` to `gemini-2.5-flash` when needed, or serve pre-verified golden curriculum caches for `0ms` interruption.
- **Operator Action**: Open the **Super-User Admin Console (`Ctrl+Shift+A` -> Tab 2: Live Telemetry & Diagnostics)** to inspect live circuit-breaker state and token burn rate.

### Playbook B: Emergency FinOps Budget Freeze (`$0.00` Live Image Generation Cap)
- **Automatic Mitigation**: `FinOpsBudgetPlugin` (`max_budget_usd = $1.00`) automatically steps down `DARK_SLATE` (`STUDIO`) requests to `WARM_CREAM` (`BEAUTIFIED`) using the `3,917` pre-bundled visual assets (`$0.00` image cost).
- **Operator Action**: Set `DISABLE_LIVE_IMAGE_GENERATION=true` or lower `MAX_WORKFLOW_BUDGET_USD=0.25` in Cloud Run environment variables to disable opt-in `$0.08` Nano Banana studio calls without redeploying code.

### Playbook C: Zero-Code Model Deprecation Cutover (`config/models.yaml`)
1. Update `primary_model` or `fast_model` in `config/models.yaml` (or set `BSA_REASONING_MODEL` / `BSA_FAST_MODEL` env vars).
2. Run `.venv/bin/python3 scripts/run_eval.py` to verify `Recall@3 == 1.0000` and `100%` AABB slide geometry conformance on the new model.
3. Deploy the updated revision with 10% canary traffic on Cloud Run v2 before promoting to 100%.
