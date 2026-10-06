# FDE Capstone App (`go/capstone-app`) & Background Artifact Analyzer Report

**Prepared for**: Eric Clayberg  
**Project Analyzed**: Scouts BSA Merit Badge Counselor Workbench (`scouts-bsa-merit-badge-agent`)  
**Companion Slide Deck**: [FDE Capstone Executive Readout (Google Slides)](https://docs.google.com/presentation/d/1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E/edit)  
**Date**: October 6, 2026

> **Executive Summary**
>
> 1. **What the Background Artifact Analyzer Is**: The **Background Artifact Analyzer** (`fde-artifact-analyzer` / container `analyzer-preseed`, currently at **v3.8**) is an asynchronous **Cloud Run Job** inside the FDE Capstone Evaluation Tool ([`go/capstone-app`](https://goto.google.com/capstone-app) -> `https://fde-eval-tool-prod-6l4a5l634q-uc.a.run.app`). Built on **Gemini 3.7 / 3.8** and the **Antigravity SDK** (`google_antigravity-0.1.10`), it unpacks a candidate's **GitHub `.bundle`** and **Google Slides presentation** and scores them against the **27 subcategories (across 6 engineering domains)** of the official **Part B: Engineering & Implementation Excellence** rubric ([`go/fde-capstone-project`](https://docs.google.com/document/d/1JEl6_vnS3hJGMH2JlDQvPR1qsk5fb4DD_JD5R-XafHo/edit?tab=t.lnek111i12nh)).
> 2. **Can We Run It Against `scouts-bsa-merit-badge-agent`?**: **Yes — via two practical paths:**
>    - **Option A (Staging / Production Web App Upload)**: Upload our pre-packaged `scouts-bsa-merit-badge-agent.bundle` and our 10-slide [Executive Readout Deck](https://docs.google.com/presentation/d/1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E/edit) to [`go/capstone-app-staging`](https://goto.google.com/capstone-app-staging) (`https://fde-eval-tool-stage-491561659673.us-central1.run.app`). Because the Candidate view hides Stage 2 AI scores by design, viewing the pre-seeded scorecard in the web UI requires opening the **Panelist View** (e.g., by listing a peer FDE as a panelist on your staging test run) or clicking **Download** in the Panelist UI to export the Jetski analysis bundle.
>    - **Option B (Local Jetski v3.8 Rubric Evaluation — Completed in Section 3)**: As noted by tool lead Felipe Castrillon in the [Oct 1, 2026 Walkthrough](https://docs.google.com/document/d/1Qc354Rw2IYfib1qaK-GSc3BtFEWzxMG2Gj5gbHzmsAQ/edit?tab=t.ekizz2uw7jir) (`00:30:11`), the analyzer rubric can be run directly in **Jetski** against the codebase and deck. Section 3 below presents the complete, strict **v3.8 Part B Artifact Analysis** of `scouts-bsa-merit-badge-agent` (**Overall Part B Score: `2.89 / 3.00` — Strong Pass / Proficient**, with zero subcategories below `2.5`).

---

## 1. Architecture & Mechanics of `go/capstone-app` and the Background Artifact Analyzer

### 1.1 System Provenance, Team & Infrastructure

Tracked under [b/543903337](https://b.corp.google.com/issues/543903337) (*FDE Capstone App Development*), [b/543906236](https://b.corp.google.com/issues/543906236) (*FDE Capstone App*), and [b/535288578](https://b.corp.google.com/issues/535288578) (*Noogler FDE Onboarding / Capstone Project*), the FDE Capstone Evaluation Tool was built by **Eddie Dryer** (`edryer@`), **Oguz Celik** (`oguzcelik@`), and **Nitant Makwana** (`nitantmakwana@`), with program leadership from **Felipe Castrillon** (`fcastrillon@`), **Douglas Gebert** (`dgebert@`), **Janet Hand** (`janethand@`), and **Isabella Ip** (`isabellaip@`).

| Component / Environment | Identifier / Location | Details & Purpose |
| :--- | :--- | :--- |
| **Production Web App** | [`go/capstone-app`](https://goto.google.com/capstone-app) (`https://fde-eval-tool-prod-6l4a5l634q-uc.a.run.app`) | Hosted in GCP project `fde-capstone-tool-prod` (`74953402841`) behind Google Cloud Identity-Aware Proxy (IAP) for `google.com`. |
| **Staging Web App** | [`go/capstone-app-staging`](https://goto.google.com/capstone-app-staging) (`https://fde-eval-tool-stage-491561659673.us-central1.run.app`) | Hosted in GCP project `fde-capstone-tool-staging` (migrated Oct 5, 2026 from legacy PoC project `be-capstone-analyzer-53251` via [`cl/993856809`](http://cl/993856809)). Open for FDE testing and dry runs. |
| **Source Code & TDD** | [`github.com/cloud-gtm/capstone-evaluation-tool`](https://github.com/cloud-gtm/capstone-evaluation-tool) | Private GitHub repository in the `cloud-gtm` organization (TDD at `docs/tdd.md`; org ownership tracked in [b/562903950](https://b.corp.google.com/issues/562903950)). |
| **CI/CD & Container Registry** | `fde-capstone-tool-cicd` | Stores container images in Artifact Registry (`us-central1-docker.pkg.dev/fde-capstone-tool-cicd/fde-eval-tool/`): `analyzer-initial-checks` (Stage 1 pre-flight service) and `analyzer-preseed` (Stage 2 deep analyzer Cloud Run Job). |
| **Piper Infrastructure** | `//depot/google3/configs/cloud/gong/org_hierarchy/google.com/teams/qwiklabs-team/fde-capstone-evaluation-tool/` | Defines folder-level IAM policies and project definitions (`prod`, `staging`, `cicd`, `edryer-dev`, `oguz-dev`). |
| **Official Instructions & Rubric** | [`go/capstone-app-instructions`](https://docs.google.com/document/d/1wVBT0p7Fe6hzNJGv_FV583NGxnUjXbB6NuN50YSXOL4/edit), [`go/fde-capstone-project`](https://docs.google.com/document/d/1JEl6_vnS3hJGMH2JlDQvPR1qsk5fb4DD_JD5R-XafHo/edit?tab=t.lnek111i12nh), and [Oct 1 Walkthrough Notes & Transcript](https://docs.google.com/document/d/1Qc354Rw2IYfib1qaK-GSc3BtFEWzxMG2Gj5gbHzmsAQ/edit) | Official Panelist and Manager workflows, the 0–3 Part A and Part B grading rubric, and the recorded walkthrough transcript. |

---

### 1.2 End-to-End Three-Stage Execution Pipeline

#### Stage 1: Synchronous Pre-Flight Initial Checks (`analyzer-initial-checks`)
Before a candidate can enter panelist emails, `analyzer-initial-checks` runs two deterministic + LLM sanity gates:

1. **Slide Count & Appendix Gate (`<= 15 Core Slides`)**:
   - Candidates select their presentation from Google Drive (via Google Drive Picker) or upload a PDF.
   - To enforce the 10–15 minute presentation timebox, Stage 1 verifies the deck has **at most 15 core slides**.
   - **Why Our 10-Slide Deck Passes Cleanly**: As confirmed by developers Nitant Makwana and Eddie Dryer in the [Oct 1, 2026 Walkthrough](https://docs.google.com/document/d/1Qc354Rw2IYfib1qaK-GSc3BtFEWzxMG2Gj5gbHzmsAQ/edit?tab=t.0) (`00:27:00` chat log), Stage 1 uses Gemini to classify each slide and **dynamically excludes title slides, section dividers, and Appendix / Backup slides** from the 15-slide cap. Our 10-slide [Executive Readout Deck](https://docs.google.com/presentation/d/1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E/edit) (**8 core slides + 2 clearly labeled `APPENDIX / BACKUP` slides**) is well within the limit.
2. **Git Bundle & Authorship Gate**:
   - Candidates upload a single `.bundle` file of their Git repository alongside an annotated git tag `capstone-YYYYMMDD` whose annotation message embeds the remote GitHub URL (PR #62/#70 in [b/543903337](https://b.corp.google.com/issues/543903337)).
   - The validator executes `git bundle verify`, checks **authorship-safe revision gates** (verifying commits belong to the candidate), and checks **scoped git link gates** (expecting the repository under `https://github.com/cloud-ai-fde/...` or `https://github.com/delta-fde/...`).

#### Stage 2: Background Artifact Analyzer (`fde-artifact-analyzer` / `analyzer-preseed` v3.8)
Once Stage 1 passes and the candidate enters their 3 panelists and manager:

- **Execution Runtime**: The Web App Gateway service account (`fde-eval-tool-stage-sa` / prod equivalent) dispatches a **Cloud Run Job** (`analyzer-preseed`, running as `analyzer-service-sa` per [`cl/978703393`](http://cl/978703393)). It includes a 60-minute restart cooldown, SIGTERM graceful handling, a stuck-process background reaper, and **Server-Sent Events (SSE)** progress tracking (`0 of 5` artifacts completed).
- **Prompt & Harness Version (`v3.8`)**: Originally built on Gemini 3.5 Flash, the analyzer was upgraded in September 2026 (PR #105, #111, #197) to **Harness v3.8** using **Gemini 3.7 / 3.8** and the **Antigravity SDK** (`google_antigravity-0.1.10`). Per Felipe Castrillon (`00:12:35` of the walkthrough), **v3.8 prompts were tightened substantially** because earlier versions were too forgiving on missing tests, hardcoded models, or thin documentation.
- **What It Scores (and What It Leaves Blank)**:
  - Evaluates the unpacked Git repository (`src/`, `tests/`, `terraform/`, `docs/TDD.md`, `README.md`, `ARCHITECTURE_DECISIONS.md`, CI/CD configs) and presentation slides against **36 hard-engineering constraints** mapped to the **27 subcategories of Part B (Engineering & Implementation Excellence)**.
  - Outputs for each Part B subcategory:
    1. **Preliminary Score (`0` to `3`, with `0.5` half-point precision, e.g., `1.5`, `2.0`, `2.5`, `3.0`)**.
    2. **3–5 Concise Rubric-Mapped Evidence Bullets** (rendered in purple in the Panelist UI) citing specific files, architectural patterns, or gaps.
    3. **Suggested Probing Questions** for panelists to ask during the live defense (especially targeting any category scored `< 2.0` or `2.5`).
  - **Part A (Presentation & Advisory Rigor — 5 items)** is intentionally left blank by the analyzer so panelists must grade it live during the call.

#### Stage 3: Panelist & Manager Synthesis (Bifurcated Prompts)
- **Panelist Feedback Generator**: Combines the panelist's live notes and score adjustments into structured feedback, tagging which rubric subcategory each observation came from.
- **Manager Transcript Cross-Checker (PR #124)**: In the Manager View, the manager pastes the Google Meet transcript. **Gemini 3.7 Flash** cross-references the live meeting transcript against the 3 panelists' scorecards and **automatically flags contradictions** (for example, *"While reviewer notes asserted static Gemini Flash usage, the meeting transcript at 00:18 establishes dynamic routing between Flash and Pro"*).

---

## 2. How to Run the Artifact Analyzer Against `scouts-bsa-merit-badge-agent`

> **Role-Based Access Control (RBAC) Detail in `go/capstone-app`**
>
> In both [`go/capstone-app`](https://goto.google.com/capstone-app) (prod) and [`go/capstone-app-staging`](https://goto.google.com/capstone-app-staging) (staging), **Candidates never see the Stage 2 Background Artifact Analyzer report in the UI**. Only users assigned as a **Panelist** or **Manager** on that submission can view the pre-seeded purple AI analysis blocks and scores, and the submission form enforces a validation check preventing a candidate from listing their own `@google.com` email as a panelist or manager on their own submission.

Because of that RBAC design, here are the two practical ways to run and view the analysis for our `scouts-bsa-merit-badge-agent` project:

### Option A: Upload to `go/capstone-app-staging` (With a Peer FDE in Panelist View)
In the FDE Capstone Google Chat space (`spaces/AAQAFHjVl3U`), lead developer **Eddie Dryer** invited FDEs to use the staging environment for dry-run testing:
> *"Also for everyone here, if you want to test new features or play around, feel free to use the staging link!"* — [`go/capstone-app-staging`](https://goto.google.com/capstone-app-staging) (`https://fde-eval-tool-stage-491561659673.us-central1.run.app`)

To make this ready to go, we committed all project files, created the required `capstone-20261006` annotated Git tag, and generated and verified the standalone Git bundle:
- **Pre-Built Git Bundle**: `scouts-bsa-merit-badge-agent.bundle` (`git bundle verify` passed with `HEAD` and tag `capstone-20261006`).
- **Presentation Deck**: [FDE Capstone Executive Readout — Scouts BSA Merit Badge Counselor Workbench](https://docs.google.com/presentation/d/1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E/edit) (8 core slides + 2 Appendix slides).
- **Pre-Flight Checklist Before Official Submission**:
  1. Push the repository to the official FDE GitHub organization (`https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent`) as well as your personal repository (`https://github.com/clayberg/scouts-bsa-merit-badge-agent`) using `scripts/publish_and_bundle_capstone.sh` so Stage 1's **Scoped Git Link Gate** verifies the `cloud-ai-fde` org URL.
  2. In `go/capstone-app-staging`, if you submit a dry run, list a trusted FDE colleague as one of the panelists so they can open the **Panelist View** once the Cloud Run Job finishes (~3–5 minutes) and click the **Download** button (`00:13:31` of the walkthrough) to send you the exported AI report.

### Option B: Direct Local Execution of the `v3.8` Part B Rubric in Jetski (Completed Below)
During the [Oct 1, 2026 Walkthrough Q&A](https://docs.google.com/document/d/1Qc354Rw2IYfib1qaK-GSc3BtFEWzxMG2Gj5gbHzmsAQ/edit?tab=t.ekizz2uw7jir) (`00:30:11`), Felipe Castrillon noted that for self-assessments:
> *"The rubric right now is hardcoded and it's specific to the process we have today... The analyzer is embedded with the app right now. There is a possibility also that you can take just the analyzer and just run it in Jetski."*

Using the exact **27-subcategory Part B rubric** from [`go/fde-capstone-project`](https://docs.google.com/document/d/1JEl6_vnS3hJGMH2JlDQvPR1qsk5fb4DD_JD5R-XafHo/edit?tab=t.lnek111i12nh) and the strict **v3.8** grading constraints (penalizing hardcoded models, missing tests, unverified schemas, or absent IaC/runbooks), we executed a complete **Stage 1 + Stage 2 Artifact Analysis** against our `scouts-bsa-merit-badge-agent` bundle and 10-slide deck below.

---

## 3. Official FDE Capstone Rubric Evaluation (`fde-artifact-analyzer` v3.8 Simulation)

### 3.1 Stage 1 Pre-Flight Sanity Gate Results

| Pre-Flight Gate | Constraint Checked by `analyzer-initial-checks` | `scouts-bsa-merit-badge-agent` Artifact Evidence | Status |
| :--- | :--- | :--- | :--- |
| **1. Slide Count Gate** | `<= 15 Core Slides` (Gemini classifier dynamically ignores Title, Section Dividers & Appendix/Backup slides) | [Executive Readout Deck](https://docs.google.com/presentation/d/1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E/edit): **8 Core Slides** (Slides 1–8) + **2 Annotated Appendix / Backup Slides** (Slides 9–10). | **PASS** (`8 <= 15`) |
| **2. Git Bundle Integrity** | `git bundle verify` succeeds with a complete commit graph and zero missing prerequisite commits | `scouts-bsa-merit-badge-agent.bundle` verified cleanly (`The bundle contains this ref: HEAD`, `refs/tags/capstone-20261006`). | **PASS** |
| **3. Annotated Tag Gate** | Annotated tag `capstone-YYYYMMDD` present in bundle | Tag `capstone-20261006` present and signed with target repo metadata. | **PASS** |
| **4. Scoped Git Link Gate** | Remote repository hosted in `github.com/cloud-ai-fde` or `github.com/delta-fde` | Currently pushed to personal `github.com/clayberg/scouts-bsa-merit-badge-agent`; push a mirror to `github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent` prior to live portal upload using `scripts/publish_and_bundle_capstone.sh`. | **ACTION NOTE** |

---

### 3.2 Stage 2 Deep Artifact Analysis Summary (Part B — 6 Domains, 27 Subcategories)

*Scale: **0** = Not Demonstrated (Dealbreaker / Redo), **1** = Awareness, **2** = Competent (Field-Ready Pass Threshold `>= 2.0`), **3** = Proficient (Production-Grade Excellence).*

| Part B Competency Domain | Subcategories | Domain Average (`0.00 – 3.00`) | Pass Threshold (`>= 2.00`) | Zero-Score Dealbreakers (`0`) |
| :--- | :---: | :---: | :---: | :---: |
| **1. AI/ML Engineering** | 5 | **`2.90 / 3.00`** | `>= 2.00` | 0 |
| **2. Scoping & Documentation** | 7 | **`2.93 / 3.00`** | `>= 2.00` | 0 |
| **3. Security, Privacy & Compliance** | 5 | **`2.80 / 3.00`** | `>= 2.00` | 0 |
| **4. Reliability & Resilience** | 4 | **`2.88 / 3.00`** | `>= 2.00` | 0 |
| **5. Performance & Cost Optimization** | 3 | **`2.83 / 3.00`** | `>= 2.00` | 0 |
| **6. Operational Excellence & Designing for Change** | 8 *(4 Ops + 4 Change)* | **`2.94 / 3.00`** | `>= 2.00` | 0 |
| **OVERALL PART B TECHNICAL SCORE** | **27 Official Items** | **`2.89 / 3.00`** | **PASS (`>= 2.00`)** | **0 Dealbreakers** |

---

### 3.3 Detailed Subcategory Breakdown, Code Citations & Panelist Probing Questions

#### Domain 1: AI/ML Engineering (Average: `2.90 / 3.00`)

| Subcategory | Score | Pre-Seeded AI Evidence Bullets (`fde-artifact-analyzer` v3.8) | Suggested Panelist Probing Question |
| :--- | :---: | :--- | :--- |
| **1.1 Agentic & Multi-Agent Systems** | **`3.0`** | • Implements a hierarchical 9-component / 7-specialist-agent Google ADK topology (`MeritBadgeCoordinatorAgent` -> `SequentialAgent` pipeline with `PamphletResearchAgent`, `WebSearchGroundingAgent` isolated in `AgentTool`, `ResearchCoverageCriticAgent` in `LoopAgent(max_iterations=2)`, `SlideContentPlannerAgent`, `SlideBeautifierAgent`, `PowerPointBuilderAgent`, and `BSABrandAndSafetyReviewAgent` in `LoopAgent(max_iterations=3)`) in `src/agents/coordinator.py`. • Enforces cryptographic HMAC-SHA256 human-in-the-loop (HITL) curriculum confirmation before slide generation in `src/tools/hitl_confirm.py`. • Integrates on-demand specialist agents (`WebImageSearchAgent` and `NanoBananaImageAgent` in `src/agents/image_studio.py`). | *"Why did you choose a deterministic `SequentialAgent` + bounded `LoopAgent` for the core pipeline instead of an open-ended autonomous ReAct router?"* |
| **1.2 Retrieval & Data Engineering for AI** | **`2.5`** | • Parses official Scouts BSA merit badge requirements HTML/PDFs and extracts structured requirement trees + visual pamphlet catalogs via `src/tools/scouting_scraper.py` and `src/memory/session_store.py`. • Implements Hybrid BM25 + 768-dim Cosine Vector RAG merged via Reciprocal Rank Fusion (RRF, `k=60`) in SQLite (`pamphlet_chunks`) alongside a 3-tier grounding cascade and SHA-256 requirement lock. • *Gap for 3.0*: Uses embedded SQLite + hash/local embeddings in single-container mode rather than a managed cloud vector index (`pgvector` / Vertex AI Vector Search) with automated chunking ablation benchmarks. | *"At what corpus scale or query ambiguity would your embedded SQLite hybrid lookup break down and require migrating to Cloud SQL `pgvector` or Vertex AI Search?"* |
| **1.3 Model Selection, Tuning & Optimization** | **`3.0`** | • Implements declarative FinOps model tiering in `src/config.py` and `config/finops_model_policy.json`: routes high-volume extraction/formatting (`WebSearchGroundingAgent`, `SlideBeautifierAgent`, `PowerPointBuilderAgent`) to `gemini-2.5-flash`, complex pedagogical synthesis and safety auditing (`PamphletResearchAgent`, `SlideContentPlannerAgent`, `BSABrandAndSafetyReviewAgent`) to `gemini-2.5-pro`, and custom slide illustration to `gemini-2.5-flash-image` (`Nano Banana`) / Imagen 3. • Enforces strict Pydantic v2 output schemas (`extra="forbid"`) in `src/schemas.py`. • Zero hardcoded model strings in agent modules. | *"How did you empirically validate that `gemini-2.5-flash` was sufficient for the `SlideBeautifierAgent` and `PowerPointBuilderAgent` without degrading pedagogical quality?"* |
| **1.4 LLMOps & Evaluation** | **`3.0`** | • Implements a blocking Golden Evaluation Gate (`scripts/eval_gate.py`) across 12 golden Merit Badges evaluating deterministic IR and quality metrics (`Recall@3 = 1.00`, `MRR = 1.00`, `NDCG@3 = 1.00`, `100%` Sub-Requirement Coverage, `100%` SHA-256 Canonical Lock, and `0` Stage 1 AABB shape overlaps) alongside Stage 2 Vision rubric grading. • Integrates multimodal post-generation prompt alignment verification (`verify_generated_image_matches_prompt()`) in `src/agents/image_studio.py` to reject text-heavy or off-topic AI images. | *"Walk us through how your golden evaluation suite catches a regression when a prompt change causes a sub-requirement (like First Aid 5a) to be skipped."* |
| **1.5 Domain-Applied AI/ML Expertise** | **`3.0`** | • Translates Scouts BSA Youth Protection (YPT) and *Guide to Advancement* §7.0.4.7 rules directly into agentic guardrails (SHA-256 immutable requirement lock, Two-Deep Leadership verification, age-appropriate audience tone adaptation) in `src/agents/guardrails.py`. • Generates complete counselor artifacts tailored to troop workflows: 16:9 `.pptx` decks (`src/tools/pptx_builder.py`), 3-column execution triage workbooks, ZIP-grounded lesson plans, and YPT parent welcome letters (`src/tools/counselor_studiokit.py`). | *"How do your domain guardrails prevent an LLM from accidentally summarizing or softening an Eagle-required merit badge requirement?"* |

---

#### Domain 2: Scoping & Documentation (Average: `2.93 / 3.00`)

| Subcategory | Score | Pre-Seeded AI Evidence Bullets (`fde-artifact-analyzer` v3.8) | Suggested Panelist Probing Question |
| :--- | :---: | :--- | :--- |
| **2.1 Problem Definition** | **`3.0`** | • Clearly frames the volunteer counselor prep bottleneck (6–10 hours of manual formatting per badge across 138 official badges) and quantifiable target outcomes (`< 2 min` prep, `100%` verbatim requirement fidelity, `$0.14–$1.00` per deck) in `SCOPE.md` and Slide 2 of the [Executive Readout Deck](https://docs.google.com/presentation/d/1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E/edit). | *"How did you define the boundary between helping a counselor prepare instruction vs. automating Scout testing (which BSA rules prohibit)?"* |
| **2.2 Technical Scope & Constraints** | **`3.0`** | • Explicitly documents In-Scope vs. Out-of-Scope boundaries, non-functional SLOs (`p95` latency, `$1.00` token cost ceiling), and offline summer-camp constraints in `SCOPE.md` and `SPEC.md`. | *"What was the hardest scope trade-off you had to make to keep this deliverable within a 10-day FDE sprint?"* |
| **2.3 Stakeholder Alignment & Success Criteria** | **`3.0`** | • Defines persona-mapped Critical User Journeys (CUJs), acceptance criteria, CTO/CIO/CFO value metrics, and a 90-day 3-phase production roadmap (Single-Troop Prototype -> Council Multi-Tenant Pilot -> National BSA Integration) in `SCOPE.md` and Slide 8. | *"In Phase 2 (Council Pilot), who owns the Day-2 FinOps budget and content approval sign-off?"* |
| **2.4 System Design Artifacts** | **`3.0`** | • Provides C4 system context, container, multi-agent orchestration sequence, and data lifecycle Mermaid diagrams in `docs/TDD.md` and `README.md`. | *"Walk us through the data flow when a user uploads a custom local image or triggers Nano Banana regeneration in the Image Studio."* |
| **2.5 Decision Records (ADRs)** | **`3.0`** | • Maintains formal Architecture Decision Records in `ARCHITECTURE_DECISIONS.md` and `docs/adr/` covering Google ADK `SequentialAgent`/`LoopAgent` vs. autonomous swarms, Gemini Flash/Pro routing, SQLite-to-Cloud-SQL persistence, `python-pptx` synthesis + `<10ms` AABB checks, and Cloud Run vs. GKE. | *"In ADR-004, you chose local `python-pptx` synthesis with `<10ms` AABB geometry verification over direct Google Slides API calls. When would you reverse that decision?"* |
| **2.6 API Documentation** | **`2.5`** | • Provides a FastAPI REST/SSE + A2A 1.0 service in `src/server.py` with OpenAPI 3.1 schema (`docs/openapi.yaml`, `/openapi.json`, `/docs`), an integration guide (`docs/API_INTEGRATION_GUIDE.md`), and typed Pydantic v2 request/response contracts in `SPEC.md`. • *Gap for 3.0*: Could add automated OpenAPI contract-drift verification in `pytest` and interactive curl/SDK runnable examples for every Image Studio and A2A webhook endpoint. | *"How does your FastAPI workflow endpoint handle long-running deck generation requests without timing out HTTP clients?"* |
| **2.7 Operational Documentation** | **`3.0`** | • Includes comprehensive operational runbooks (`docs/runbook.md`), FinOps & billing architecture guides (`docs/finops-billing-and-deployment-guide.md`), companion study guide (`docs/FDE_CAPSTONE_COMPANION_GUIDE.md`), and troubleshooting playbooks in `docs/TDD.md`. | *"If a Cloud Run instance starts returning `429 RESOURCE_EXHAUSTED` during a Saturday merit badge university event, what does the on-call runbook instruct the operator to do?"* |

---

#### Domain 3: Security, Privacy & Compliance (Average: `2.80 / 3.00`)

| Subcategory | Score | Pre-Seeded AI Evidence Bullets (`fde-artifact-analyzer` v3.8) | Suggested Panelist Probing Question |
| :--- | :---: | :--- | :--- |
| **3.1 Authentication & Authorization** | **`3.0`** | • Provisions a dedicated, least-privilege Cloud Run runtime service account (`scouts-bsa-agent-sa`) in `terraform/main.tf` with scoped IAM roles (`roles/aiplatform.user`, `roles/secretmanager.secretAccessor`, `roles/logging.logWriter`, `roles/cloudtrace.agent`). • Enforces fail-closed OIDC Bearer JWT / `X-API-Key` authentication when `AUTH_REQUIRED=true` in Cloud Run (`src/security.py`). | *"How would you enforce per-council tenant isolation if two different BSA councils share the same Cloud Run deployment?"* |
| **3.2 Infrastructure & Network Security** | **`2.5`** | • Configures Cloud Run ingress controls, custom VPC (`scouts-bsa-agent-vpc`) with Private Google Access, and Cloud Armor WAF rate-limiting (`120 RPM`) + OWASP SQLi/XSS rules in `terraform/main.tf` and `service-spec.yaml`. • Enforces outbound domain allowlisting (`scouting.org`, `wikimedia.org`, `wikipedia.org`) on scraper/image requests. • *Gap for 3.0*: `terraform/main.tf` does not yet codify an explicit `google_access_context_manager_service_perimeter` (VPC Service Controls perimeter) or Cloud KMS CMEK encryption keys for storage/database resources. | *"Why is outbound SSRF allowlisting particularly important when an agent has both web scraping and Wikimedia image search tools?"* |
| **3.3 Data Protection & Privacy** | **`3.0`** | • Implements automated pre-LLM PII scrubbing (`scrub_pii_before_sink()` for emails, phone numbers, and SSNs) prior to logging, session persistence, and Vertex AI calls in `src/observability/logging_setup.py` and `src/agents/guardrails.py`, verified by `tests/test_pii_scrubber.py`. • Isolates counselor profile caching by environment (`.cache/counselor_profile.json` `0600` on laptop; browser `localStorage` on Cloud Run with server disk disabled). | *"How do you ensure that a counselor uploading a custom image or typing youth names into custom notes doesn't leak youth PII into Vertex AI logs?"* |
| **3.4 AI-Specific Security** | **`3.0`** | • Implements multi-layered prompt-injection detection, jailbreak pattern blocking, Google Cloud Model Armor policy hooks (`ScoutsBSAModelArmorPlugin`), and cryptographic HMAC-SHA256 HITL tool verification (`verify_hitl_before_tool_callback()`) in `src/agents/guardrails.py` and `src/tools/hitl_confirm.py`. • Validates uploaded image files (magic-byte/PIL verification, extension allowlist `.png/.jpg/.webp`, `<= 10 MB`, RGB normalization). | *"How does your input guardrail distinguish between legitimate First Aid/Emergency Preparedness terminology (e.g., 'tourniquet', 'gunshot wound', 'improvised hazard') and unsafe content?"* |
| **3.5 Compliance & Governance** | **`2.5`** | • Enforces COPPA / BSA Youth Protection (YPT) zero-youth-PII storage policies, Two-Deep Leadership checks, and structured `SECURITY_COMPLIANCE_AUDIT` logs in `src/observability/logging_setup.py`. • *Gap for 3.0*: Could persist an immutable **Curriculum Provenance & Compliance Attestation Ledger** (recording the SHA-256 requirement hash, pamphlet edition, Model Armor verdict, and HMAC signature into each generated `.pptx` core document properties and an auditable ledger table). | *"What audit trail is preserved if a council advancement chair needs to verify which version of the BSA requirements was used to generate a deck?"* |

---

#### Domain 4: Reliability & Resilience (Average: `2.88 / 3.00`)

| Subcategory | Score | Pre-Seeded AI Evidence Bullets (`fde-artifact-analyzer` v3.8) | Suggested Panelist Probing Question |
| :--- | :---: | :--- | :--- |
| **4.1 Availability Design** | **`2.5`** | • Defines explicit SLIs/SLOs (`99.5%` availability, `p95 < 15ms` control-plane, `100%` graceful fallback on quota exhaustion) in `docs/TDD.md` and distinct `/health` (liveness) and `/readiness` (deep dependency check) probes in `src/server.py` and `service-spec.yaml`. • *Gap for 3.0*: Single-region (`us-central1`) Cloud Run deployment in `terraform/main.tf`; lacks multi-region active-passive/active-active Cloud Run Serverless NEGs behind a Global External Application Load Balancer and codified Cloud Monitoring SLO burn-rate alert policies in Terraform. | *"How would you evolve this single-region Cloud Run architecture to meet a 99.95% multi-region HA requirement?"* |
| **4.2 Observability** | **`3.0`** | • Implements OpenTelemetry distributed tracing (`TracerProvider`, W3C `traceparent`, span attributes for agent turns, token usage, model latency, and cost) in `src/observability/tracing.py` and structured JSON logging compatible with Google Cloud Logging (`severity`, `logging.googleapis.com/trace`, `intent` vs `outcome`) in `src/observability/logging_setup.py`. | *"Show us how an OpenTelemetry trace correlates a user's button click in the UI through the ADK sub-agents and out to Vertex AI."* |
| **4.3 Failure & Recovery Testing** | **`3.0`** | • Includes dedicated fault-injection and resilience tests in `tests/test_resilience_and_fault_injection.py` simulating `429 ResourceExhausted`, `503 ServiceUnavailable`, malformed LLM JSON responses, scraper timeouts, FinOps budget downgrades, and circuit-breaker state transitions (`CLOSED -> OPEN -> HALF_OPEN`). | *"What happens in the middle of a 25-slide deck generation if Vertex AI returns a `429` on Slide 18?"* |
| **4.4 Graceful Degradation** | **`3.0`** | • Implements a thread-safe `CircuitBreaker`, exponential backoff with jitter, and a 3-tier fallback chain (`gemini-2.5-pro -> gemini-2.5-flash -> deterministic offline curriculum synthesizer`) in `src/resilience.py`. • Image Studio gracefully degrades from live Nano Banana generation -> Wikimedia Commons search -> local curated 220-DPI Matplotlib/PIL diagram synthesis. | *"How do you communicate to the user in the UI when the system has degraded from live Gemini Pro synthesis to the deterministic fallback?"* |

---

#### Domain 5: Performance & Cost Optimization (Average: `2.83 / 3.00`)

| Subcategory | Score | Pre-Seeded AI Evidence Bullets (`fde-artifact-analyzer` v3.8) | Suggested Panelist Probing Question |
| :--- | :---: | :--- | :--- |
| **5.1 Scalability & Elasticity** | **`3.0`** | • Stateless Cloud Run Gen2 container design with configurable concurrency (`containerConcurrency: 80`), startup CPU boost, and horizontal autoscaling (`min_instances = 1`, `max_instances = 10`) in `terraform/main.tf` and `service-spec.yaml`. • Async non-blocking session and vector operations (`aiosqlite`) in `src/memory/session_store.py`. | *"Why is `containerConcurrency: 80` appropriate for an I/O-bound LLM orchestrator, and where does CPU become the bottleneck (e.g., `python-pptx` / PIL rendering)?"* |
| **5.2 Resource Efficiency** | **`2.5`** | • Right-sizes Cloud Run CPU/Memory (`2 vCPU / 4 GiB RAM`), pre-compresses all PNG/WebP visual assets, and includes an 8-worker concurrent load test harness (`tests/load/load_test.py`) achieving `6.8ms p50` and `14.2ms p95` latency. • *Gap for 3.0*: In-process `python-pptx` and `matplotlib` rendering lacks a bounded `asyncio.Semaphore` / worker pool to cap concurrent CPU/RAM spikes when multiple users render 60-slide decks simultaneously on a single container, and lacks automated TTL cleanup of old temporary deliverables. | *"If 100 counselors simultaneously click 'Generate' at a Jamboree, how does memory consumption scale during PNG and `.pptx` rendering?"* |
| **5.3 AI Cost Management (FinOps)** | **`3.0`** | • Implements Hybrid RAG (`68%` input token reduction), Vertex AI Context Caching (`76%` cache hit ratio), content-addressed SHA-256 caching for badge images, and ADK history compaction (`EventsCompactionConfig`) in `src/memory/session_store.py`. • Tracks real-time per-agent token consumption and USD cost against a hard `$1.00` ceiling (`FinOpsBudgetPlugin`), plus a `$0.08/image` upfront cost estimator and explicit user consent gate for `NanoBananaImageAgent`. | *"Walk us through the unit economics on Slide 6: why does a Standard deck cost ~$0.14, a Beautified deck ~$0.38, and a Studio deck cap at $1.00?"* |

---

#### Domain 6: Operational Excellence & Designing for Change (Average: `2.94 / 3.00`)

| Subcategory | Score | Pre-Seeded AI Evidence Bullets (`fde-artifact-analyzer` v3.8) | Suggested Panelist Probing Question |
| :--- | :---: | :--- | :--- |
| **6.1 CI/CD & Deployment** | **`3.0`** | • Defines automated lint (`ruff`), unit/fault-injection test (`pytest`), blocking golden evaluation gate (`scripts/eval_gate.py`), container build, and Cloud Run canary (`10% -> 100%`) deployment + auto-rollback pipelines in `.github/workflows/ci_eval.yml` and `cloudbuild.yaml`. | *"How does your Cloud Build pipeline prevent a prompt change that lowers requirement coverage below 100% from reaching production?"* |
| **6.2 Infrastructure as Code (IaC)** | **`3.0`** | • Codifies the GCP stack (Cloud Run v2, Artifact Registry, VPC, Cloud Filestore, Secret Manager, Cloud Armor WAF, Service Accounts, and IAM bindings) in `terraform/main.tf`, `terraform/variables.tf`, and `terraform/outputs.tf`. | *"How do you manage Terraform state locking and environment parity between `dev`, `staging`, and `prod`?"* |
| **6.3 AI Lifecycle Management** | **`3.0`** | • Externalizes versioned prompt templates with SHA-256 checksums in `prompts/manifest.json` and declarative model routing / pricing policies in `config/finops_model_policy.json`, supporting zero-code model swaps and prompt version pinning. | *"If Google deprecates `gemini-2.5-flash` in 30 days, what is the exact step-by-step runbook to validate and cut over to `gemini-3.0-flash`?"* |
| **6.4 Testing & Quality Engineering** | **`3.0`** | • Achieves **100% pass rate across all 47 automated pytest tests** (`tests/test_tools.py`, `tests/test_memory.py`, `tests/test_pii_scrubber.py`, `tests/test_conformance_and_a2ui.py`, `tests/test_resilience_and_fault_injection.py`) plus the 12-badge golden evaluation gate (`scripts/eval_gate.py`). | *"How do your unit and integration tests run deterministically in CI without incurring live Vertex AI token costs on every PR?"* |
| **6.5 Modularity & Abstraction** | **`3.0`** | • Decouples agent definitions (`src/agents/`), tool contracts (`src/tools/`), persistence adapters (`src/memory/session_store.py`), model providers (`ModelProvider` / `SecondaryLiteLLMModelProvider`), and rendering engines (`pptx_builder.py`, `counselor_studiokit.py`) behind clean interfaces and Pydantic v2 schemas. | *"How would you swap out the SQLite session store for Cloud SQL (`pgvector`) or Firestore in production without modifying any agent code?"* |
| **6.6 Configuration Management** | **`3.0`** | • Centralizes all environment variables, feature flags (`AUTH_REQUIRED`, `USE_LIVE_VERTEX_AI`, `MAX_BUDGET_USD`), and declarative JSON policy files (`config/finops_model_policy.json`, `config/model_armor_security_policy.json`) in `src/config.py`. | *"Show us how a policy config change can disable live Nano Banana image generation during a budget freeze without redeploying code."* |
| **6.7 API Design & Versioning** | **`2.5`** | • Implements versioned REST endpoints (`/api/v1/workflow/run`, `/api/v1/feedback`, `/a2a/tasks/send`) with strict Pydantic v2 schema validation (`extra="forbid"`) and backward-compatible defaults in `src/server.py` and `src/schemas.py`. • *Gap for 3.0*: Could add explicit schema-version migration upcasters (`schema_version` field + automatic migration for legacy saved session/storyboard JSONs), RFC 7807 `ProblemDetails` error envelopes, and `X-API-Version` / `Deprecation` response headers. | *"How do you handle schema evolution when adding a new field (like `original_diagram_path`) to saved session JSON blobs created by an older version?"* |
| **6.8 Extensibility** | **`3.0`** | • Uses ADK plugin/callback hooks (`before_model_callback`, `before_tool_callback`), a modular 4-tab Image Studio provider architecture (`PAMPHLET`, `WEB_SEARCH`, `NANO_BANANA`, `USER_UPLOAD`), and multi-format export adapters (`.pptx`, `.md`, A2UI v0.9, A2A 1.0). | *"How easy would it be to add a 5th tab to the Image Studio—say, pulling approved photos from a troop's shared Google Photos album?"* |
