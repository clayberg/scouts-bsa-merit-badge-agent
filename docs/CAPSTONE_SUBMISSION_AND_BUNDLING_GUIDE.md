# FDE Capstone Option A Submission & Bundling Guide (`v2.6`)

This guide documents the repository verification steps, deliverable inventory, and automated pre-submission checks for the **Scouts BSA Merit Badge Counselor Workbench**.

---

## 1. Repository Deliverable Inventory

| Deliverable Artifact | Repository Path | Verification Status |
| :--- | :--- | :--- |
| **8-Agent Google ADK Pipeline** | `src/agents/` (`coordinator.py`, `researcher.py`, `planner.py`, `curriculum.py`, `beautifier.py`, `image_studio.py`, `reviewer.py`, `guardrails.py`) | Verified (`53` `pytest` tests passing) |
| **Material 3 Counselor Workbench UI & FastAPI Server** | `src/server.py`, `ui/index.html`, `ui/app.js`, `ui/styles.css` | Verified (`1:1` HTML5-to-PPTX parity) |
| **FastMCP Server & Cryptographic HITL Tokens** | `src/mcp_server.py` | Verified (`HMAC-SHA256` token gate) |
| **All 144 Official Merit Badge JSON Catalogs** | `data/merit_badge_requirements/*.json` (`18` Eagle-Required + `126` Electives) | Verified (`100%` sub-requirement & `topic_slides` coverage) |
| **100% Pre-Cached Visual Asset Library** | `assets/ai_illustrations/` (`2,292` 8-bit PNGs), `assets/pamphlet_images/` (`4,316` de-boxed figures), `assets/badge_emblems/` (`135` transparent RGBA patches), `assets/pamphlet_covers/` (`134` covers) | Verified (`$0.00` runtime image cost) |
| **72 Pre-Built & Audited Benchmark Decks** | `deliverables/benchmark_and_random_samples/*.pptx` (`26` Benchmark + `10` Random badges across *Deep Dive* and *Troop Meeting* modes) | Verified (`0` AABB overlaps, `100%` citation coverage) |
| **Flagship Beautified Deep Dive Decks** | `deliverables/Weather_BEAUTIFIED_DeepDive_Merit_Badge_Deck.pptx`, `deliverables/First_Aid_BEAUTIFIED_DeepDive_Merit_Badge_Deck.pptx`, `deliverables/Cooking_BEAUTIFIED_DeepDive_Merit_Badge_Deck.pptx`, `deliverables/Citizenship_in_the_Nation_BEAUTIFIED_DeepDive_Merit_Badge_Deck.pptx` | Verified (High-res diagrams & scene-specific captions) |
| **Terraform Cloud Run & Secret Manager IaC** | `terraform/main.tf`, `terraform/variables.tf`, `Dockerfile`, `cloudbuild.yaml` | Verified (`terraform validate` clean) |
| **Technical & Operational Documentation** | `README.md`, `SPEC.md`, `SCOPE.md`, `ARCHITECTURE_DECISIONS.md`, `docs/USER_GUIDE.md`, `docs/TDD.md`, `docs/API_INTEGRATION_GUIDE.md`, `docs/finops-billing-and-deployment-guide.md`, `docs/runbook.md` | Verified (Updated with live screenshots & zero broken links) |

---

## 2. Automated Pre-Submission Verification Suite

Run the following three commands from the repository root before tagging a release or presenting to the panel:

```bash
# 1. Run Ruff linter across all source, test, and script modules
.venv/bin/ruff check src/ tests/ scripts/

# 2. Run all 53 automated behavioral, conformance, memory, security, and resilience tests
.venv/bin/pytest -q

# 3. Run the <5s 6-Act Pre-Flight Live Demo Readiness Script
.venv/bin/python scripts/verify_live_demo_readiness.py
```

Expected output from `scripts/verify_live_demo_readiness.py`:
- `demo_ready`: `true`
- `act1_pamphlet_sha256_lock.passed`: `true`
- `act1b_hybrid_rrf_retrieval.passed`: `true`
- `act2_image_studio_finops_gate.passed`: `true` (`estimated_cost_usd: 0.08`)
- `act3_guardrail_and_pii_interception.passed`: `true`
- `act4_conformance_and_citation_grounding.passed`: `true` (`citation_coverage_ratio: 1.0`)
- `act4b_circuit_breaker_health.passed`: `true` (`state: "CLOSED"`)
