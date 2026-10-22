# AI-Assisted Engineering Harness & Agent Governance (`AGENTS.md`)

This repository is governed by an automated AI-Assisted Engineering Harness designed for the **Scouts BSA Merit Badge Counselor Workbench** (Google Cloud FDE Delivery Readiness Capstone). All coding agents and contributors operating in this repository must enforce the architectural, security, testing, and FinOps invariants below.

---

## 1. Eight Mandatory `3.0 / 3.0` Engineering Invariants

1. **Real Wired Google ADK Multi-Agent Pipeline (Rubric B1.1)**:
   - The FastAPI server (`src/server.py`) wires real `google-adk` agents (`MeritBadgeCoordinatorAgent`, `SequentialAgent`, and bounded `LoopAgent` critics in `src/agents/coordinator.py`) directly into the live `/api/v1/workflow/run` and `/api/workflow/stream` request paths.
   - All agent handoffs and tool calls enforce strict Pydantic v2 schemas (`src/schemas.py`).
2. **Persistent Multi-Turn Session & Vector State (Rubric B1.1 & B5.1)**:
   - Session state, 768-dim hybrid vector/BM25 chunks, image catalogs, and multi-badge workspaces are persisted in `PersistentSessionStore` (`src/memory/session_store.py`, SQLite WAL mode with 9 tables and a dual-backend `CloudSQLPgVectorBackend` adapter for horizontal Cloud Run scaling). Never store session state solely in an in-memory Python `dict`.
3. **Two Separate Architecture Diagrams (Rubric B2.4 & Slide Readout)**:
   - Maintain two distinct architecture diagrams in `README.md`, `docs/ARCHITECTURE.md`, and `docs/TDD.md`:
     1. **Logical Multi-Agent Orchestration & Data Flow Diagram**
     2. **Physical GCP Infrastructure, IAM & Security Perimeter Diagram**
4. **Bidirectional (Ingress + Egress) PII Scrubbing & YPT Guardrails (Rubric B3.3 & B3.4)**:
   - `ScoutsBSAModelArmorPlugin` (`src/agents/guardrails.py`) enforces ingress prompt-injection defense, BSA Youth Protection (YPT) two-deep leadership rules, tool-argument sanitization, and outbound SSE/REST egress PII scrubbing (`scrub_pii_from_structure()` and `scrub_pii_before_sink()`).
   - Counselor email addresses and phone numbers are never transmitted to Gemini or written to telemetry logs.
5. **Honest Dual Latency Telemetry (Rubric B4.2 & B5.1)**:
   - `ZeroPiiTelemetryStore` (`src/observability/telemetry.py`) tracks and reports both **First Status Event (`first_status_event_ms`)** and **True First Meaningful Content Token (`true_first_content_token_ms` / `true_ttft_ms`)** (`p50`/`p95`). Never stop the TTFT clock on an initial status banner.
6. **Deterministic + Rubric Golden Dataset Evals & 5% Online Audit Sampling (Rubric B1.4)**:
   - Run `scripts/run_eval.py` (`scripts/eval_gate.py`) combining deterministic retrieval metrics (`Recall@3 = 1.0000`, `MRR = 1.0000`), cryptographic SHA-256 requirement verification (`0` character drift), and `<10ms` AABB slide geometry QA with `OnlineProductionAuditSampler` (`src/observability/online_audit_sampler.py`), which samples 5% of completed production workflow traces after PII scrubbing.
7. **Zero Spec-vs-Code Drift & Explicit As-Built Reconciliation (Rubric B2.2 & B2.5)**:
   - Every capability claimed in documentation or slides must exist in `src/` and `terraform/` or be explicitly documented in **`ADR-11` (As-Built Implementation Reconciliation, Argolis Sandbox Constraints & Enterprise Phase 2 Scope)** in `ARCHITECTURE_DECISIONS.md` and `docs/ADR.md`.
8. **Cryptographic Requirement Integrity & Human-in-the-Loop (HITL) Tool Gate (Rubric B1.5 & B3.4)**:
   - Official Scouts BSA requirement text is locked with a SHA-256 hash (`compute_canonical_pamphlet_hash()`) before and after regional enrichment.
   - Final `.pptx` compilation (`generate_bsa_slide_deck_pptx`) requires a valid HMAC-SHA256 `HITLConfirmationToken` verified in constant time by `verify_hitl_before_tool_callback()`.

---

## 2. Externalized Model Routing & Configuration Rules (`config/models.yaml`)

- **Never hardcode model IDs** in agent or tool modules. Always resolve models via `select_model_for_task()` in `src/config.py` backed by `config/models.yaml` and environment variable overrides.
- **Tiered Model Routing**:
  - `gemini-2.5-pro`: Complex multi-requirement curriculum synthesis and 12-archetype pedagogical storyboarding (`PamphletResearchAgent`, `SlideContentPlannerAgent`).
  - `gemini-2.5-flash`: High-throughput regional grounding, visual styling, PowerPoint assembly, and critic verification (`WebSearchGroundingAgent`, `ResearchCoverageCriticAgent`, `SlideBeautifierAgent`, `PowerPointBuilderAgent`, `BSABrandAndSafetyReviewAgent`).
- **FinOps Ceiling**: Enforce `FinOpsBudgetPlugin` (`max_budget_usd = $1.00` hard ceiling) and prefer the `3,917` pre-bundled visual assets (`$0.00` runtime image cost, with automatic on-demand GitHub Raw batch hydration via `src/tools/asset_hydrator.py` if local media is absent).

---

## 3. Pre-Commit Verification & Regression Gates

Before committing code or packaging `repo.bundle`, run:

1. **Test Suite (`77/77` passing tests)**:
   ```bash
   .venv/bin/pytest tests/ -q
   ```
2. **Golden Dataset Evaluation Gate (`Recall@3 = 1.0000`, `0` drift)**:
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

---

## 4. Rubric Item A4 Log: AI Coding Agent Failures Caught by This Harness

| Failure ID | What the Coding Agent Initially Got Wrong | How Our Harness Caught It | Architectural Fix & Permanent Regression Gate |
| :--- | :--- | :--- | :--- |
| **`FM-1`** | **Vertex AI Built-in `GoogleSearchTool` + Custom Function Tool `400 INVALID_ARGUMENT` Conflict**: Early agent code attached `GoogleSearchTool` and custom Python tools on the same `LlmAgent`. | Caught by integration test and live SSE workflow trace inspection. | Isolated `GoogleSearchTool` inside `WebSearchGroundingAgent` wrapped via ADK `AgentTool` (`ADR-01`, `src/agents/researcher.py`), guarded by `tests/test_conformance_and_a2ui.py`. |
| **`FM-2`** | **Dense Slide Text Overflow & Scanned Figure White-Box Clashing on Cream/Dark Themes**: Long multi-part requirements overflowed bottom slide bounds and showed white rectangular backgrounds on `WARM_CREAM` slides. | Caught by Stage 1 deterministic `<10ms` AABB geometry checker (`check_pptx_conformance()`) and Stage 2 visual auditor (`audit_deck_visual_quality()`). | Added proactive line-wrap font scaling (`12.0pt` floor, `_compute_fitting_font_size()`) and alpha corner flood-fill de-boxing (`_strip_white_image_background()` in `src/tools/pptx_builder.py`). |
| **`FM-3`** | **Synthetic Placeholder Badge Emblems Instead of Official Embroidered Patches**: Early asset scripts generated vector circles instead of authentic Scout Shop embroidered patches. | Caught by visual perceptual-hash & pixel audit (`scripts/verify_144_emblems.py`). | Replaced all 144 emblems with verified `400x400` Scout Shop embroidered patch PNGs and locked their SHA-256 inventory in `data/asset_inventory_manifest.json`. |
| **`FM-4`** | **Popup Blocker & Single-Monitor Friction on Dual-Monitor Speaker Teleprompter**: Relying solely on `window.open()` for speaker notes failed when counselors taught from a single laptop screen or strict browser popup settings. | Caught during end-to-end UX rehearsal and Playwright verification. | Built the in-stage **Full-Size Split-Screen Presenter View (`P`)** alongside the synchronized `BroadcastChannel` floating window (`ui/app.js`). |
