# AI-Assisted Engineering Harness & Agent Governance (`AGENTS.md`)

This repository is governed by an automated AI-Assisted Engineering Harness designed for the **Scouts BSA Merit Badge Counselor Workbench** (Google Cloud FDE Delivery Readiness Capstone). All coding agents and contributors operating in this repository must enforce the architectural, security, testing, and FinOps invariants below.

---

## 1. Eight Mandatory `3.0 / 3.0` Engineering Invariants

1. **Real Wired Google ADK Multi-Agent Pipeline (Rubric B1.1)**:
   - The FastAPI server (`src/server.py`) wires real `google-adk` agents (`MeritBadgeCoordinatorAgent`, `SequentialAgent`, and bounded `LoopAgent` critics in `src/agents/coordinator.py`) directly into the live `/api/v1/workflow/run` and `/api/workflow/stream` request paths.
   - All agent handoffs and tool calls enforce strict Pydantic v2 schemas (`src/schemas.py`).
2. **Persistent Multi-Turn Session & Vector State (Rubric B1.1 & B5.1)**:
   - Session state, 768-dim hybrid vector/BM25 chunks, image catalogs, multi-badge workspaces, and multi-session clinic schedules/attendance are persisted in `PersistentSessionStore` (`src/memory/session_store.py`, SQLite WAL mode with 12 tables and a dual-backend `CloudSQLPgVectorBackend` adapter for horizontal Cloud Run scaling). Never store session state solely in an in-memory Python `dict`.
3. **Two Separate Architecture Diagrams (Rubric B2.4 & Slide Readout)**:
   - Maintain two distinct architecture diagrams in `README.md`, `docs/ARCHITECTURE.md`, and `docs/TDD.md`:
     1. **Logical Multi-Agent Orchestration & Data Flow Diagram**
     2. **Physical GCP Infrastructure, IAM & Security Perimeter Diagram**
4. **Bidirectional (Ingress + Egress) 3-Layer Context-Aware PII Scrubbing & YPT Guardrails (Rubric B3.3 & B3.4)**:
   - `ScoutsBSAModelArmorPlugin` (`src/agents/guardrails.py`) and `src/observability/logging_setup.py` enforce ingress prompt-injection defense, BSA Youth Protection (YPT) two-deep leadership rules, tool-argument sanitization, and outbound SSE/REST egress PII scrubbing (`scrub_pii_from_structure()` and `scrub_pii_before_sink()`).
   - Phone redaction uses a **3-Layer Context-Aware Filter (`v2.2`)**: Layer 1 excludes 10-digit IDs inside URLs/filenames (preserving all 92 official Scouting America Vimeo video links and PDF worksheets across 18 badges); Layer 2 allowlists NANPA toll-free prefixes (`800/888/877/866/855/844/833`) and canonical emergency/institutional hotlines (`1-800-222-1222` Poison Control on First Aid Slide 3, `911`, `988`, `800-323-0736` BSA Scout Shop, `202-633-1000` Smithsonian switchboard); Layer 3 applies a `±55`-character institutional vs. personal hotword window while redacting all personal youth/parent/counselor phone numbers (`[REDACTED_PHONE]`). Counselor email addresses and personal phone numbers are never transmitted to Gemini or written to telemetry logs.
5. **Honest Dual Latency Telemetry (Rubric B4.2 & B5.1)**:
   - `ZeroPiiTelemetryStore` (`src/observability/telemetry.py`) tracks and reports both **First Status Event (`first_status_event_ms`)** and **True First Meaningful Content Token (`true_first_content_token_ms` / `true_ttft_ms`)** (`p50`/`p95`). Never stop the TTFT clock on an initial status banner.
6. **Deterministic + Rubric Golden Dataset Evals & 5% Online Audit Sampling (Rubric B1.4)**:
   - Run `scripts/run_eval.py` (`scripts/eval_gate.py`) combining deterministic retrieval metrics (`Recall@3 = 1.0000`, `MRR = 1.0000`), cryptographic SHA-256 requirement verification (`0` character drift), and `<10ms` AABB slide geometry QA with `OnlineProductionAuditSampler` (`src/observability/online_audit_sampler.py`), which samples 5% of completed production workflow traces after PII scrubbing.
7. **Zero Spec-vs-Code Drift & Explicit As-Built Reconciliation (Rubric B2.2 & B2.5)**:
   - Every capability claimed in documentation or slides must exist in `src/` and `terraform/` or be explicitly documented in **`ADR-11` (As-Built Implementation Reconciliation, Argolis Sandbox Constraints & Enterprise Phase 2 Scope)** in `ARCHITECTURE_DECISIONS.md` and `docs/ADR.md`.
8. **Cryptographic Requirement Integrity, 5-Part Facilitator Guide, 4-Pillar Workbooks & Human-in-the-Loop (HITL) Tool Gate (Rubric B1.5 & B3.4)**:
   - Official Scouts BSA requirement text across all **149 Merit Badges** (`143` Active Official + `5` Scouting America Test Lab Pilots + `1` Discontinued Historical badge *Citizenship in Society* with red `🚫 Discontinued` indicator) is locked with a SHA-256 hash (`compute_canonical_pamphlet_hash()`) before and after regional enrichment, unrolled across the **4-Pillar Fillable Workbooks (`GTA §7.0.3.2`) & Multi-Page `CPP`** (`0%` dropped requirement text across 13 bespoke graphic organizers), and paired with the **Archetype-Differentiated 5-Part Non-Redundant Facilitator Guide** (`[PACING & MODALITY]`, `[ASK SCOUTS FIRST]`, `[EXPECTED PAMPHLET ANSWER KEY]`, `[COMMON MISCONCEPTION TO CORRECT]`, `[DEMONSTRATION & SIGN-OFF RUBRIC]`) with child-slide sub-requirement scoping (`1a-1d` vs. `1e-1g`, `3a-3q`) and `[✨ AI Polish Slide | ▾]` (`default_presenter_notes`).
   - Final `.pptx` compilation (`generate_bsa_slide_deck_pptx`) requires a valid HMAC-SHA256 `HITLConfirmationToken` verified in constant time by `verify_hitl_before_tool_callback()`.

---

## 2. Externalized Model Routing & Configuration Rules (`config/models.yaml`)

- **Never hardcode model IDs** in agent or tool modules. Always resolve models via `select_model_for_task()` in `src/config.py` backed by `config/models.yaml` and environment variable overrides.
- **Tiered Model Routing**:
  - `gemini-2.5-pro`: Complex multi-requirement curriculum synthesis and 12-archetype pedagogical storyboarding (`PamphletResearchAgent`, `SlideContentPlannerAgent`).
  - `gemini-2.5-flash`: High-throughput regional grounding, visual styling, PowerPoint assembly, and critic verification (`WebSearchGroundingAgent`, `ResearchCoverageCriticAgent`, `SlideBeautifierAgent`, `PowerPointBuilderAgent`, `BSABrandAndSafetyReviewAgent`).
- **FinOps Ceiling**: Enforce `FinOpsBudgetPlugin` (`max_budget_usd = $1.00` hard ceiling) and prefer the `4,124` pre-bundled visual assets across all `149` badges (`$0.00` runtime image cost, with automatic on-demand GitHub Raw batch hydration via `src/tools/asset_hydrator.py` if local media is absent).

---

## 3. Pre-Commit, Repository Sync & GitHub Actions CI Verification Gates

Before committing code, pushing to remotes, or packaging `repo.bundle`, you MUST run all verification checks below. **Whenever you sync (`git push`) the two GitHub repositories (`origin`: `clayberg/scouts-bsa-merit-badge-agent` and `fde`: `cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent`), you MUST check GitHub Actions and fix any lint, test, or workflow errors before finishing your turn.**

0. **Blocking Ruff Static Linter (`0` errors required before push)**:
   ```bash
   .venv/bin/ruff check src/ tests/ scripts/
   ```
1. **Test Suite (`133/133`+ passing unit, security, fault-injection, and golden eval tests)**:
   ```bash
   .venv/bin/pytest tests/ tests/eval_golden_suite.py -q
   ```
2. **Golden Dataset Evaluation Gate (`Recall@3 = 1.0000`, `LLM-as-a-Judge = 4.92/5.0`, `0` drift)**:
   ```bash
   .venv/bin/python3 scripts/run_eval.py
   ```
3. **Executable FinOps Cost Model & Repo Audit**:
   ```bash
   .venv/bin/python3 scripts/cost_model.py
   bash scripts/repo_audit.sh
   ```
4. **Submission Bundle Packaging & Stage 1 Pre-Flight Verification (`< 30 MB`)**:
   ```bash
   .venv/bin/python3 scripts/build_submission_bundle.py
   python3 /usr/local/google/home/clayberg/.gemini/config/skills/fde-capstone-coach/scripts/capstone_preflight.py --repo-root . --check-claims
   ```
5. **Post-Push GitHub Actions CI Verification Gate (Mandatory on Every Repo Sync)**:
   - After pushing to `origin` (`https://github.com/clayberg/scouts-bsa-merit-badge-agent`) and `fde` (`https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent`), inspect the live workflow status:
     ```bash
     gh run list --repo clayberg/scouts-bsa-merit-badge-agent --limit 3
     gh run list --repo cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent --limit 3
     ```
   - Wait for the triggered run to complete (`gh run watch <run-id> --repo clayberg/scouts-bsa-merit-badge-agent --exit-status`). If any step fails (`gh run view <run-id> --log-failed`), diagnose and fix the failure, re-push to both remotes, and verify a green `✓` build before concluding the turn.

---

## 4. Rubric Item A4 Log: AI Coding Agent Failures Caught by This Harness

| Failure ID | What the Coding Agent Initially Got Wrong | How Our Harness Caught It | Architectural Fix & Permanent Regression Gate |
| :--- | :--- | :--- | :--- |
| **`FM-1`** | **Vertex AI Built-in `GoogleSearchTool` + Custom Function Tool `400 INVALID_ARGUMENT` Conflict**: Early agent code attached `GoogleSearchTool` and custom Python tools on the same `LlmAgent`. | Caught by integration test and live SSE workflow trace inspection. | Isolated `GoogleSearchTool` inside `WebSearchGroundingAgent` wrapped via ADK `AgentTool` (`ADR-01`, `src/agents/researcher.py`), guarded by `tests/test_conformance_and_a2ui.py`. |
| **`FM-2`** | **Dense Slide Text Overflow & Scanned Figure White-Box Clashing on Cream/Dark Themes**: Long multi-part requirements overflowed bottom slide bounds and showed white rectangular backgrounds on `WARM_CREAM` slides. | Caught by Stage 1 deterministic `<10ms` AABB geometry checker (`check_pptx_conformance()`) and Stage 2 visual auditor (`audit_deck_visual_quality()`). | Added proactive line-wrap font scaling (`12.0pt` floor, `_compute_fitting_font_size()`) and alpha corner flood-fill de-boxing (`_strip_white_image_background()` in `src/tools/pptx_builder.py`). |
| **`FM-3`** | **Synthetic Placeholder Badge Emblems Instead of Official Embroidered Patches**: Early asset scripts generated vector circles instead of authentic Scout Shop embroidered patches. | Caught by visual perceptual-hash & pixel audit (`scripts/verify_144_emblems.py`). | Replaced all 149 emblems (`143` Active Official + `5` Test Lab + `1` Discontinued) with verified `400x400` Scout Shop embroidered patch PNGs and locked their SHA-256 inventory in `data/asset_inventory_manifest.json`. |
| **`FM-4`** | **Popup Blocker & Single-Monitor Friction on Dual-Monitor Speaker Teleprompter**: Relying solely on `window.open()` for speaker notes failed when counselors taught from a single laptop screen or strict browser popup settings. | Caught during end-to-end UX rehearsal and Playwright verification. | Built the in-stage **Full-Size Split-Screen Presenter View (`P`)** alongside the synchronized `BroadcastChannel` floating window (`ui/app.js`). |
| **`FM-5`** | **Test-Suite Catalog Mutation Side-Effect & 5-Part Facilitator Guide Eval Marker Drift**: `seed_badge_image_catalog_from_storyboard` dirtied tracked `catalog.json` files during pytest runs, and `eval_gate.py:302` checked only `[SAY]` (`4.42/5.0` vs. `4.92/5.0`). | Caught by `git status` cleanliness gate and 20-badge `scripts/eval_gate.py` evaluation run. | Added `PYTEST_CURRENT_TEST` write guard in `src/agents/image_studio.py` and updated `scripts/eval_gate.py` (`_evaluate_llm_as_a_judge_rubric`) to recognize `("[PACING & MODALITY]", "[ASK SCOUTS FIRST]", "[SAY]")`. |
