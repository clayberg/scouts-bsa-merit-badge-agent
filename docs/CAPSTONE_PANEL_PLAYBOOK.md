# FDE Capstone Panel Playbook & Live Demo Runbook (`v2.6`)

This playbook provides the step-by-step operational checklist, **12-slide Executive Briefing outline**, **6-act live demonstration sequence**, and **technical Q&A defense reference** for presenting the **Scouts BSA Merit Badge Counselor Workbench**.

---

## 1. Pre-Demo Flight Check (`< 30 Seconds`)

Before sharing your screen, run these two commands in the repository root to verify that the local server, SQLite WAL store, circuit breaker, and all 6 live demo acts are healthy:

```bash
# 1. Run the <5s 6-Act Live Demo Readiness Script
.venv/bin/python scripts/verify_live_demo_readiness.py

# 2. Confirm the Workbench server is listening on port 8080 and all 144 official badges are loaded
curl -s http://localhost:8080/api/v1/readiness | jq .
```

Open these browser tabs in order:
1. **Tab 1**: Executive Briefing Slide Deck (`12 Core Slides`).
2. **Tab 2**: Live **Scouts BSA Merit Badge Counselor Workbench** (`http://localhost:8080`) with **Weather** or **First Aid** loaded in **AI Beautified (`BEAUTIFIED`)** mode.
3. **Tab 3**: Exported **Weather** or **First Aid** `.pptx` deck opened in Google Slides (highlighting Slide 14 Hydrologic Cycle, Slide 21 Cold Front, Slide 33 Cloud Classification, and Slide 49 cropped Earth's 23.5° Axial Tilt & Seasons).

---

## 2. 12-Slide Executive Briefing Structure (`10-12 Minutes`)

| Slide | Title | Core Engineering Takeaway |
| :--- | :--- | :--- |
| **`01 / 12`** | **Scouts BSA Merit Badge Counselor Workbench** | Production 8-agent Google ADK workbench covering all **144 official Merit Badges** (`18` Eagle-Required + `126` Electives), **2,297 pre-cached Nano Banana PNGs**, **4,317 de-boxed pamphlet figures**, and **53 automated `pytest` tests**. |
| **`02 / 12`** | **Problem & Customer Empathy: The 12-Hour Prep Tax** | Volunteer counselors spend 8-15 hours turning 80-page PDFs into slides, workbooks, parent letters, and Blue Card trackers while navigating strict Youth Protection (YPT) and curriculum rules. |
| **`03 / 12`** | **System Architecture: 8-Agent Google ADK Hierarchy** | `MeritBadgeCoordinator` (`gemini-2.5-pro`) orchestrating 7 specialist sub-agents with strategic Flash/Pro routing (`~71%` token savings), FastMCP HITL tokens, A2A 1.0, and A2UI v0.9. |
| **`04 / 12`** | **5-Tier Authoritative Research & Hybrid RRF RAG** | Verbatim requirement trees (`1a..15c`) across all `144` badges locked by SHA-256 (`compute_canonical_pamphlet_hash`) + Hybrid Dense Cosine (`text-embedding-004`) and Okapi BM25 (`k1=1.5, b=0.75`) fused via RRF (`k=60`). |
| **`05 / 12`** | **Two-Stage PPTX Conformance & 1:1 Google Slides Parity** | Stage 1 `<10ms` deterministic AABB geometry simulator (`0` overlaps across `72` benchmark decks), `_concise_card_body` character budgets, de-boxed pamphlet figures, high-res embedded-text diagrams, and scene-specific captions. |
| **`06 / 12`** | **Defense-in-Depth Security, YPT PII & Model Armor** | Dual-layer regex + Cloud DLP scrubbing (`[REDACTED_YOUTH_NAME]`, `[REDACTED_PHONE]`, `[REDACTED_EMAIL]`) and Model Armor prompt-injection interception (`allowed=False`) verified by `53` `pytest` tests. |
| **`07 / 12`** | **Production Resilience, Circuit Breakers & Self-Healing** | 3-state `CircuitBreaker` (`CLOSED`/`OPEN`/`HALF_OPEN`), exponential backoff with jitter, automatic Pro-to-Flash model fallback, and up to `MAX_CONFORMANCE_RETRIES = 2` layout self-healing loops. |
| **`08 / 12`** | **FinOps Governance & Pre-Cached Visual Pipeline** | **`$0.00` runtime image cost** on all `144` badges via `2,297` pre-cached 8-bit PNGs (`~$0.04-$0.14` LLM tokens per deck), `$1.00` hard session budget cap, and explicit **`$0.08` USD user consent gate** (`CONSENT_REQUIRED`) for live custom AI images. |
| **`09 / 12`** | **Evaluation Engineering & Continuous Learning Flywheel** | `53` non-hollow `pytest` tests, 12-badge Golden Evaluation Gate (`scripts/eval_gate.py`), `72` audited benchmark decks, and `/api/v1/feedback` auto-promoting 4-5 star counselor sign-offs into `golden_extensions.json`. |
| **`10 / 12`** | **Counselor UX: Co-Design Studio & Field Toolkit** | 16:9 widescreen preview stage, 3 Scout construction animations, Per-Slide Co-Design Bar, 4-Tab Image Studio, Multi-Format Session Pacing Agenda, Parent Letter email/Gmail actions, Quartermaster Gear multiplier, and Blue Card CSV export. |
| **`11 / 12`** | **Live End-to-End Workbench Walkthrough** | Transition slide into the 6-act live browser and CLI demonstration. |
| **`12 / 12`** | **Summary & Engineering Scorecard** | Full-stack readiness summary across all 5 AgentOps pillars (`144` badges, `2,297` pre-cached visuals, `0` AABB overlaps, `0` PII leaks, `53` passing `pytest` tests) and open panel Q&A. |

---

## 3. 6-Act Live Demonstration Runbook (`8-10 Minutes`)

### Act 1: 144-Badge Catalog, Local ZIP Grounding & 1:1 Slide Preview (`2 Min`)
1. In the left sidebar, show the **All 144 Official Merit Badges** catalog and filter by **Eagle-Required (`18`)** or **STEM & Digital** (pointing out *Artificial Intelligence*, *Cybersecurity*, *First Aid*, and *Weather*).
2. Open the **Counselor & Troop Profile** (`Eric Clayberg`, `Troop 19, Middleton MA`, ZIP `01949`) and show Slide 2 (`Curriculum Overview & Triage Matrix`), pointing out how `01949` automatically grounds the deck to **NWS Boston/Norton (`BOX`)** and classifies requirements into **Discussion**, **Hands-On Skill Demonstrations**, and **Field & Home Prerequisites**.
3. Step through Slides 14, 21, 33, and 49 of the **Weather** deck to highlight the high-resolution embedded-text diagrams (Hydrologic Cycle, Cold Front cross-section, Cloud Classification chart, and top-cropped Earth's 23.5° Axial Tilt & Seasons) with clean, scene-specific captions and 1:1 Google Slides import parity.

### Act 2: Per-Slide Co-Design & 4-Tab Image Studio with `$0.08` FinOps Gate (`2 Min`)
1. Below the slide stage, click **Edit Slide Text** in the **Per-Slide Interactive Co-Design Bar**, tweak a bullet point or switch the **Color Palette** (`Forest & Sage` or `Crimson & Ember`), and show the immediate preview update.
2. Click **Open 4-Tab Image Studio**:
   - **Tab 1 (`Cached Library`, `$0.00`)**: Show the pre-cached Nano Banana hero and topic illustrations (`2,297` across all `144` badges) and de-boxed official pamphlet figures (`4,317` figures).
   - **Tab 2 (`Web Image Search`, `$0.00`)**: Run a quick Wikimedia Commons search.
   - **Tab 3 (`Nano Banana AI Generator`, `$0.08` Consent Gate)**: Show the content-aware style selector (*Auto Content-Aware Mix*, *Include Uniformed Scouts*) and click **Generate Custom AI Image** to trigger the explicit **`$0.08` USD FinOps User Consent Dialog** (`CONSENT_REQUIRED`).
   - **Tab 4 (`File Upload`, `$0.00`)**: Show local troop photo upload.

### Act 3: 5-Tab Counselor Toolkit Drawer & Continuous Learning Flywheel (`2 Min`)
1. Click through the **5-Tab Under-Stage Drawer**:
   - **Tab 1 (`Teaching Notes`)**: Show the detailed `[SAY]`, `[DEMONSTRATE]`, and `[ASK SCOUTS]` BSA EDGE scripts.
   - **Tab 2 (`Coverage & QA`)**: Point out the **Stage 1 (`<10ms`) Conformance Passed (`0` AABB overlaps)** badge and submit a **5-Star Counselor Sign-Off** (`POST /api/v1/feedback`) to show automatic promotion into `tests/data/golden_extensions.json`.
   - **Tab 3 (`Teaching Plan & Blue Card`)**: Check off requirements in the **Patrol Blue Card (`#34124`) & Scoutbook Plus Matrix** and click **Export Scoutbook CSV**.
   - **Tab 4 (`StudioKit Docs`)**: Switch the **Session Pacing Selector** from *3 Troop Meetings* to *Summer Camp Week (4x50-Min)*, change the **Quartermaster Gear Multiplier** to `3x (2 Patrols)`, and show the **Prerequisite Parent Letter** with **Draft in Email App** and **Compose in Gmail**.

### Act 4: Live Terminal Verification of Security, Conformance & Resilience (`2 Min`)
Run the pre-flight verification script in the terminal to prove all 6 backend guarantees live in `<5 seconds`:
```bash
.venv/bin/python scripts/verify_live_demo_readiness.py
```
Highlight the JSON output confirming:
- `act1_pamphlet_sha256_lock`: `64`-char SHA-256 lock over verbatim requirements.
- `act1b_hybrid_rrf_retrieval`: Top-1 `[REQ-2b]` match via Hybrid Dense + Okapi BM25 RRF (`k = 60`).
- `act2_image_studio_finops_gate`: `$0.08` USD explicit consent gate active.
- `act3_guardrail_and_pii_interception`: Prompt injection blocked (`allowed: false`) and youth phone/email scrubbed (`[REDACTED_PHONE]`, `[REDACTED_EMAIL]`).
- `act4_conformance_and_citation_grounding`: `0` AABB overlaps and `100%` citation coverage.
- `act4b_circuit_breaker_health`: `VERTEX_LLM_CIRCUIT_BREAKER` in `CLOSED` state.
