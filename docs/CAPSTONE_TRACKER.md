# FDE Capstone Project Tracker (`docs/CAPSTONE_TRACKER.md`)

## 1. Resolved Project Variables

| Variable | Value |
| :--- | :--- |
| `YOUR_LDAP` | `clayberg` |
| `PROJECT_SLUG` | `scouts-bsa-merit-badge-agent` |
| `PROJECT_NAME` | `Scouts BSA Merit Badge Counselor Workbench` |
| `CUSTOMER_NAME` | `Scouting America (BSA) Volunteer Merit Badge Counselors & Local Councils` |
| `TARGET_PERSONAS` | `Volunteer Merit Badge Counselors, Summer Camp Directors, Scoutmasters, Youth Advancement Chairs` |
| `USER_GUIDE_DOC_ID` | `1IYMvIW_72EFoA5wr4h1I4mPXyCm0k6RmRbnlv9z5dHo` |
| `ADMIN_GUIDE_DOC_ID` | `1jCQclVI2KnO-qJaRqwRHQkVMJ8CDohWjU8u2JT3CJpU` |
| `TDD_DOC_ID` | `1Bpj41LTlT4MKyLSyxtSOvEtdj2kMHsPBSqL6lqeF_nQ` |
| `API_GUIDE_DOC_ID` | `1kJ2Dr3UeQka89_HV_MyDBPlIHEvj2ZB0Xczo1sQKBDU` |
| `MCP_GUIDE_DOC_ID` | `1LBSU1slmXO4dM7x45vcSSE4-oSbMqPA5UViml8J44BA` |
| `FINOPS_DOC_ID` | `1k8oXmGze3dxOotTvahVEOhQT5qET425wRbmH3mU6miQ` |
| `COMPANION_GUIDE_DOC_ID` | `1a_3TPfgm7U2O5S_f4QR_Aey3ptGnICFdAgvzfF-uXYw` |
| `PANEL_PLAYBOOK_DOC_ID` | `1S80Sja2XTpyHxrSwuaATYaEePbF1PV6CkrCiDbEbiaU` |
| `DEMO_SCRIPT_DOC_ID` | `11cIHKTVLnIlwRcFcVkC4OR1lCnc40bIYr3aOJvXMGvc` |
| `ANALYZER_REPORT_DOC_ID` | `1xTVDg0mWaK8oUhPiVrEjsA0vcOkZj9CKARse0iNFi7M` |
| `BUNDLING_GUIDE_DOC_ID` | `13OQXD6ec260-3bLVRwC2hSiSpLJAURT7vkUVW2DeQF4` |
| `ARGOLIS_PROJECT_ID` | `scouts-bsa-agent-prod` (`us-central1`) |
| `GCP_REGION` | `us-central1` |
| `GITHUB_REPO_URL` | `https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent` |
| `GITHUB_MIRROR_URL` | `https://github.com/clayberg/scouts-bsa-merit-badge-agent` |
| `CLOUD_RUN_URL` | `https://scouts-bsa-merit-badge-agent-qjaneb6heq-uc.a.run.app` (Local Workbench: `http://clayberg.c.googlers.com:8085`) |
| `SLIDE_DECK_ID` | `1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E` (Slide Ops ID: `pres-fc3fc5e36b5b`, 12 Core Slides) |

---

## 2. 20-Step Progress Checklist

- [x] **Step 1**: Prerequisites, `cloud-ai-fde` GitHub invite accepted, Argolis Business project & FDE skills verified
- [x] **Step 2**: Read `go/fde-capstone-project` and reviewed peer tips
- [x] **Step 3**: Selected project and defined Scoping (`SCOPE.md`, `SPEC.md`) + Technical Design (`docs/TDD.md`, `docs/ARCHITECTURE.md`)
- [x] **Step 4**: Initialized `docs/CAPSTONE_TRACKER.md` and `AGENTS.md`
- [x] **Step 5**: Completed Duckie research, `3.0 / 3.0` implementation plan & 3-persona adversarial review
- [x] **Step 6**: Built local 7-Agent Google ADK backend, dual architecture diagrams, persistent SQLite/CloudSQL state (12 tables incl. `compliance_attestation_ledger`, `clinic_session_schedules`, `scout_session_attendance_and_partials`, and `counselor_syllabus_bucket_overrides`), 3-layer context-aware bidirectional PII scrubbing, semantic cache (`src/services/semantic_cache.py`), deterministic A/B canary router (`src/services/ab_router.py`), extensible plugin registry (`src/plugins/registry.py`), 20-badge golden evals (`scripts/run_eval.py`) & `pytest` (`220+` passing [`144` unit/integration + `21` golden eval], `0` warnings, `162` OpenAPI paths, `27` MCP capabilities)
- [x] **Step 7**: Built and verified interactive Material 3 Expressive A2UI frontend locally (`./run_local.sh`), including `🧭 Guided Tour ▾` (8 narrated multi-step guided tours with live virtual cursor, spotlight ring, and floating callout), Consolidated M3 Toolbars (`37 -> 14` primary actions across `5` toolbars + single-row Compact Hero Banner), Nano Banana AI Template Studio (`16` photorealistic Scouting washed backdrops + live prompt synthesis + custom photo upload + 3-mode Live 16:9 Preview), and 4-Tab Under-Stage Drawer (`📊 Multi-Agent Workflow Trace & FinOps`)
- [x] **Step 8**: Pushed to `cloud-ai-fde` GitHub, tagged `capstone-20261027` (annotated tag with `Submission URL`), and verified `< 30 MB` `repo.bundle`
- [x] **Step 9**: Created modular Terraform IaC (`terraform/main.tf`, `terraform/iam.tf`, `variables.tf`, `outputs.tf`), `cloudbuild.yaml`, DR verification (`scripts/verify_dr_restore.py`), and smoke tests (`scripts/smoke_test_deployment.py`)
- [x] **Step 10**: Configured Cloud Run v2 topology (`min-instances=1`) and verified health/readiness probes (`/health`, `/readiness`)
- [x] **Step 11**: Verified Executive Readout deck requirements (`12` core slides, strictly `<= 15` core slides)
- [x] **Step 12**: Built 12-slide Executive Readout deck via Slide Ops (`pres-fc3fc5e36b5b`) and synced to Google Slides (`1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E`)
- [x] **Step 13**: Authored humanized speaker script & 5-minute live demo choreography (`docs/CAPSTONE_PANEL_PLAYBOOK.md` & `docs/CAPSTONE_CONVERSATIONAL_PRESENTATION_AND_DEMO_SCRIPT.md`)
- [x] **Step 14**: Authored 56-question persona Q&A bank with code citations (`docs/PERSONAL_TECHNICAL_BRIEFING.md`, `docs/FDE_CAPSTONE_COMPANION_GUIDE.md` & `docs/CAPSTONE_PANEL_PLAYBOOK.md`)
- [x] **Step 15**: Authored "For Your Eyes Only" Personal Technical Briefing & Jargon Decoder (`docs/PERSONAL_TECHNICAL_BRIEFING.md` & `docs/FDE_CAPSTONE_COMPANION_GUIDE.md`)
- [x] **Step 16**: Ran Stage 1 (`capstone_preflight.py --check-claims`) + Stage 2 dry-run analyzer audit (`docs/CAPSTONE_ANALYZER_DRY_RUN_REPORT.md` & `docs/CAPSTONE_ARTIFACT_ANALYZER_REPORT.md`)
- [x] **Step 17**: Remediated all `< 3.0` gaps, added `ADR-11` As-Built Reconciliation & Per-Badge GitHub Asset Hydrator, and verified zero Claims-vs-Code drift
- [ ] **Step 18**: Complete live rehearsal / Mode 7 Mock Panel Simulator session
- [ ] **Step 19**: Confirm 3 panelists, send calendar invite (`>=72h`), and click `Submit Panel` in Stage 3 of `go/capstone-app`
- [ ] **Step 20**: Post-graduation: onboard as a Capstone panelist (`http://go/fde-capstone-find-panelers`)
