# FDE Capstone Panel Playbook: Speaker Script, Live Demo & CTO/CIO/CFO Q&A

**Project**: Scouts BSA Merit Badge Counselor Workbench (`scouts-bsa-merit-badge-agent` v3.1.0)
**Author / Presenter**: Eric Clayberg (FDE & Merit Badge Counselor, Troop 19, Middleton, MA)
**Target Panel Personas**: Chief Technology Officer (CTO), Chief Information Officer / CISO (CIO), Chief Financial Officer (CFO), and Principal AI Engineering Evaluators
**Companion Deck**: [FDE Capstone Executive Readout (Google Slides)](https://docs.google.com/presentation/d/1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E/edit)
**Companion Study Guide**: [FDE Capstone Companion Guide (Google Doc)](https://docs.google.com/document/d/1a_3TPfgm7U2O5S_f4QR_Aey3ptGnICFdAgvzfF-uXYw/edit)
**FinOps & Deployment Cost Guide**: [FinOps, Token Billing & Deployment Cost Guide (Google Doc)](https://docs.google.com/document/d/1k8oXmGze3dxOotTvahVEOhQT5qET425wRbmH3mU6miQ/edit)

## 1. Panel Presentation Structure & Timing (30-Minute Slot)

| Segment | Duration | Focus & Objective |
| :--- | :--- | :--- |
| **Part 1: Executive Readout (11 Core Slides, 0 Appendix — `1 / 11` to `11 / 11`)** | 10 Mins | Walk the panel through the volunteer counselor problem, the 4 deliverable pillars & 4-Tab Image Studio, the 7-agent Google ADK architecture, the Co-Design Workbench & `_compute_fitting_font_size()` layout engine, Youth Protection & security guardrails, FinOps unit economics (`$0.14` to `$1.00`), CI/CD evaluation gates, quantitative ADR benchmarks & post-mortems, the 90-day rollout plan, and the complete `3.00/3.00` Part B / `95/95` AgentOps / `100/100` FDE scorecard. |
| **Part 2: Live Interactive Demo** | 5 Mins | Show the Material 3 Web Workbench (`:8085`), demonstrate ZIP/City local grounding (`01949` / `Middleton, MA`), compare the 3 visual tiers (`Standard`, `Beautified`, `Studio`), inspect an EDGE Skill Concept Map, test the Per-Slide Co-Design Bar and 4-Tab Image Studio, and verify 1:1 `.pptx` parity. |
| **Part 3: CTO / CIO / CFO Panel Q&A** | 15 Mins | Field technical, security, operational, and financial questions using concrete files, tests, metrics, and Slides 5, 9, and 11. |

## 2. Slide-by-Slide Speaker Script (10 Minutes — 11 Core Slides, 0 Appendix)

### Slide 1 (`01 / 11`): Title & Executive Summary (0:45)

**Spoken Script**:
"Good morning. Today I am presenting the **Scouts BSA Merit Badge Counselor Workbench**, a multi-agent curriculum system built with the **Google Agent Development Kit (ADK)** on **Vertex AI** and **Cloud Run**.

Across Scouting America, tens of thousands of volunteer counselors teach **138 official Merit Badges**, from Eagle-required badges like *First Aid*, *Weather*, and *Emergency Preparedness* to STEM electives like *Robotics* and *Nuclear Science*. Turning an 80-page BSA Merit Badge Pamphlet into a widescreen slide deck, a printable Scout workbook, and a timed lesson plan takes a volunteer **6 to 10 hours** per badge.

Our workbench cuts that prep time to **under 2 minutes** while guaranteeing **100% verbatim fidelity** to official BSA requirements via a cryptographic **SHA-256 requirement lock**, all within a predictable **`$0.14` to `$1.00`** FinOps budget—verified at **`3.00 / 3.00` Part B**, **`95 / 95` AgentOps**, and **`100 / 100` FDE Readiness**."

> **[NOTE TO ERIC - DO NOT READ ALOUD]**
> - **Google ADK (Agent Development Kit)**: Google's Python framework (`google-adk`) for orchestrating multi-agent apps on Gemini (`SequentialAgent`, `LoopAgent`, `LlmAgent`, `FunctionTool`, `AgentTool`).
> - **SHA-256 Requirement Lock**: Before any web research runs, `compute_canonical_pamphlet_hash()` (`src/agents/researcher.py`) hashes every official requirement number and text (`1a`, `1b`, etc.) using SHA-256. After enrichment finishes, it hashes them again to prove not a single character of the official BSA requirement text was altered.
> - **AABB Check (`<10ms`)**: Short for **Axis-Aligned Bounding Box** check (`check_pptx_conformance()` in `src/agents/reviewer.py`). It tests the `(left, top, right, bottom)` rectangle coordinates of every shape on a PowerPoint slide in `3.4ms` at `$0.00` token cost to confirm zero overlapping boxes.

### Slide 2 (`02 / 11`): Problem Statement & Customer Pain Points (0:50)

**Spoken Script**:
"Let's look at why volunteer counselors struggle today, and why generic one-shot LLM prompts fail at this job.

First, **volunteer prep time**: counselors are unpaid professionals teaching on weeknights and campouts. Spending a full weekend copying requirements out of an 80-page PDF leads to burnout.

Second, **requirement drift**: Scouting America updates Merit Badge requirements regularly. Hand-me-down decks found online often teach outdated requirement revisions, which creates problems when a Scout reaches their Eagle Board of Review. And if you ask a generic LLM to write a deck, it paraphrases or drops sub-requirements.

Third, **classroom versus field triage**: some requirements are classroom discussions (*Explain the difference between a severe thunderstorm watch and warning*), while others require hands-on patrol skill stations (*Demonstrate CPR and tourniquet application*) or campout prerequisites (*Keep a 10-day weather log*).

Our workbench solves all three: it locks canonical requirement text with a SHA-256 check, resolves the counselor's local ZIP code or city to regional weather and terrain data, and automatically triages every requirement into Classroom Discussion, Hands-On Skill Station, and Home/Campout Prerequisite buckets."

> **[NOTE TO ERIC - DO NOT READ ALOUD]**
> - **Requirement Drift**: When a Scout uses an old slide deck from the internet that teaches an outdated pamphlet revision, their Eagle Scout rank application can be delayed at the council level.
> - **BSA EDGE Method**: Scouting's official 4-step teaching method: **E**xplain, **D**emonstrate, **G**uide, **E**nable.
> - **Execution-Mode Triage**: In `src/tools/scouting_scraper.py`, every requirement is parsed by its action verbs (`Explain/Discuss` -> `IN_CLASS_DISCUSSION`, `Demonstrate/Show/Prepare` -> `HANDS_ON_SKILL_STATION`, `Camp/Visit/Keep a log` -> `PREREQUISITE_CAMPOUT_HOME`).

### Slide 3 (`03 / 11`): Product Capabilities & Counselor StudioKit (1:00)

**Spoken Script**:
"When a counselor runs the workbench, it delivers four synchronized artifacts in one pass:

First, a **16:9 widescreen PowerPoint deck (`.pptx`)** built across **12 specialized layout archetypes** (such as two-column comparisons, 2x2 step grids, gear checklists, and Socratic check-on-learning quizzes) with three distinct visual polish tiers (`Standard`, `Beautified`, and `Studio`) and **100% layout and text parity** between the live web preview and the downloaded PowerPoint file.

Second, a **printable Scout Workbook and Triage Matrix (`.md`)** that maps every sub-requirement (`1a` through `11`) to pamphlet excerpts and adapts instructional tone to the counselor's chosen **Audience Level** (`Tenderfoot ages 11 to 12`, `Mixed Troop ages 11 to 17`, or `Older Scouts / Eagle Prep ages 14 to 17`).

Third, a **ZIP or City grounded Lesson Plan and Youth Protection Parent Letter**. When I enter `01949` or `Middleton, MA`, the agent resolves my local NOAA National Weather Service Forecast Office (`Boston/Norton`), New England coastal Nor'easter and winter hypothermia hazards, and nearby training sites like *Harold Parker State Forest*.

Fourth, an interactive **Per-Slide Co-Design Bar and 4-Tab Popup Merit Badge Image Studio** (`1. Badge Catalog` with cache clear, `2. Wikimedia Search`, `3. Nano Banana AI ($0.08)` across 8 styles, and `4. Local File Upload ($0.00)`)."

> **[NOTE TO ERIC - DO NOT READ ALOUD]**
> - **How Location Grounding Works (`resolve_counselor_location()` in `src/agents/researcher.py`)**: It parses the **Location (City, State or ZIP Code)** input field (`01949`, `Middleton, MA`), or falls back to the browser's timezone (`America/New_York`), and looks up the regional NOAA NWS Forecast Office, local terrain/weather hazards, and nearby state parks. Instead of repeating boilerplate on every slide, it places that local context in four targeted places: **Slide 2 (Badge Overview)**, the **Counselor Lesson Plan**, the **Parent Prerequisite Letter**, and the **Grounded Citations** tab.
> - **Why the UI dropdown has 140 items while BSA has 138 official badges**: Scouts BSA has **138 official Merit Badges**. Our selector includes 2 clearly labeled `(Test Stub)` entries used by automated fault-injection tests.

### Slide 4 (`04 / 11`): Google ADK Multi-Agent Architecture & Vertex AI Patterns (1:05)

**Spoken Script**:
"Under the hood, the system is orchestrated by **`MeritBadgeCoordinatorAgent`** across **7 specialized sub-agents** (9 architectural components total, including the on-demand Image Studio agents):

1. **Stage 1 (`MeritBadgeCoordinatorAgent`)** manages session state in SQLite WAL (with a codified `CloudSQLPgVectorBackend` adapter) using **Hybrid Vector + Okapi BM25 RRF RAG**, compacts conversation history every 5 turns via ADK's `EventsCompactionConfig`, streams real-time **A2UI v0.9** events over Server-Sent Events, and enforces our Human-in-the-Loop gate.
2. **Stage 2 (`PamphletResearchAgent` + `ResearchCoverageCriticAgent`)** extracts the cached BSA Pamphlet PDF via `PyMuPDF`, locks the SHA-256 requirement hash, and invokes web search grounding. Notably, Vertex AI forbids mixing `GoogleSearchTool` with custom Python `FunctionTool`s on the same agent. We solve that cleanly using ADK's **Search-Subagent Isolation Pattern**, wrapping `WebSearchGroundingAgent` inside an `AgentTool`.
3. **Stage 3 (`SlideContentPlannerAgent`)** runs on `gemini-2.5-pro` to map requirements onto our 12 slide archetypes and generate the Counselor StudioKit.
4. **Stage 4 (`SlideBeautifierAgent`)** runs on `gemini-2.5-flash` to apply our 3 visual tiers, rotating color palettes, and 220-DPI EDGE Skill Concept Maps under a strict FinOps budget cap.
5. **Stage 5 (`PowerPointBuilderAgent` + `BSABrandAndSafetyReviewAgent`)** runs inside a bounded `LoopAgent(max_iterations=3)`. Stage 1 verifies zero AABB shape overlaps, `13pt` minimum fonts, `100%` citation grounding (`verify_slide_citation_grounding`), and WCAG AA contrast in **3.4 milliseconds**, before Stage 2 runs our `gemini-2.5-pro` safety and brand rubric."

> **[NOTE TO ERIC - DO NOT READ ALOUD]**
> - **Why Vertex AI Rejects Mixed Tools (and how `AgentTool` solves it)**: If you attach `GoogleSearchTool` and custom Python `FunctionTool`s to the same `LlmAgent`, Vertex AI throws a `400 INVALID_ARGUMENT` tool-mixing error. Putting `GoogleSearchTool` inside `WebSearchGroundingAgent` and wrapping that sub-agent in `AgentTool` (`src/agents/researcher.py`) is the canonical Google ADK pattern.

### Slide 5 (`05 / 11`): Co-Design Workbench, 4-Tab Image Studio & Zero-Overflow Layout Engine (0:55)

**Spoken Script**:
"Slide 5 zooms into the interactive **Per-Slide Co-Design Workbench, 4-Tab Merit Badge Image Studio, and Zero-Overflow Layout Engine**:

- First, **Per-Slide Co-Design & Full-Width Reflow**: counselors can modify any single slide's layout archetype, card theme, or right-side graphic in place. Setting Right-Side Graphic to **`None`** automatically expands text cards from `6.55"` to full `12.133"` widescreen width (`CONCEPT_TEXT_SLIDE`), while **`Restore Original Slide Graphic`** restores the initial `original_diagram_path` in one click.
- Second, the **4-Tab Popup Image Studio (`src/agents/image_studio.py`)**:
  - **Tab 1 (`Badge Image Catalog`)** caches all graphics per badge with a one-click **`🗑️ Clear Web/AI Cache`** button (`DELETE /api/badge/images`).
  - **Tab 2 (`WebImageSearchAgent`)** queries live Wikimedia Commons for up to 12 public-domain photos.
  - **Tab 3 (`NanoBananaImageAgent`)** generates custom 220-DPI illustrations across 8 styles (`Photorealistic`, `Line Drawing`, `Cartoon`, `Technical Diagram`, etc.) gated by an upfront **`$0.08 USD` cost estimator**, explicit user consent (`user_consented=True`), and `verify_generated_image_matches_prompt()`.
  - **Tab 4 (`Local File Upload — $0.00`)** validates `.png/.jpg/.webp` files (`<= 10 MB`), strips EXIF metadata, normalizes RGB (`max 1600px`), and registers them as `USER_UPLOAD`.
- Third, **Proactive Font Auto-Fitting (`_compute_fitting_font_size`)**: calculates wrapped line counts and steps body fonts from `16.5pt` down to `13.0pt` (moving excess detail to Speaker Notes) so text never overflows card borders."

### Slide 6 (`06 / 11`): Security, Youth Protection (YPT) & Fault-Tolerant Engineering (0:55)

**Spoken Script**:
"Because this tool is built for Scouting, **Youth Protection (YPT)**, privacy, and resilience are built directly into the agent lifecycle:

First, **Environment-Isolated Counselor Profile Caching and Pre-LLM PII Scrubbing**: counselors enter their name, troop, location, email, and phone number once—cached in `.cache/counselor_profile.json` (`0600`) locally or browser `localStorage` on Cloud Run. Before any prompt leaves for Vertex AI or Cloud Trace, `before_model_guardrail_callback` scrubs emails and phone numbers to `[REDACTED_EMAIL]` and `[REDACTED_PHONE]`, while our **Regional Cloud Model Armor API integration** (`:sanitizeUserPrompt` / `:sanitizeModelResponse`) blocks prompt injection and enforces Two-Deep Leadership rules.

Second, a **Cryptographic HMAC-SHA256 Human-in-the-Loop Gate & Compliance Attestation Ledger**: `request_counselor_confirmation()` signs the badge name and slide count with `BSA_HITL_SECRET_KEY`, verified in constant time before `.pptx` compilation, and writes an immutable record to `compliance_attestation_ledger` while embedding the SHA-256 hash into the `.pptx` metadata.

Third, a **3-State Circuit Breaker and Model Fallback Cascade** (`gemini-2.5-pro -> gemini-2.5-flash -> deterministic local synthesizer`) with zero HTTP 500 errors.

Fourth, **Zero-Trust Cloud Run in Terraform**: dedicated least-privilege IAM, custom VPC, **VPC Service Controls (`VPC-SC`) perimeter**, **Cloud KMS CMEK** (90-day rotation), and Cloud Armor WAF (`120 RPM`)."

### Slide 7 (`07 / 11`): FinOps Unit Economics, TCO & Architectural Trade-Offs (0:55)

**Spoken Script**:
"For a non-profit organization like Scouting America, unit economics have to be predictable down to the penny:

- **Tier 1 (`Standard Fast`)** costs **`$0.14` per deck** (`$0.00` cached rerun).
- **Tier 2 (`AI Beautified`, default)** costs **`$0.38` per deck** (`$0.02` cached), adding a warm cream canvas (`#FAF8F5`) and up to 5 EDGE Skill Concept Maps.
- **Tier 3 (`AI Studio`)** enforces a **hard `$1.00` maximum cap** via `FinOpsBudgetPlugin`, while on-demand `NanoBananaImageAgent` graphics require an explicit **`$0.08 USD` consent gate** and cache per badge for free reuse.

Two architectural trade-offs drive these savings: **Hybrid Vector + BM25 RAG** cuts input tokens by **68%**, and **Stage 1 AABB geometry checks (`3.4ms`, `$0.00`)** + a **bounded render concurrency semaphore & 24h TTL cleanup** eliminate wasted Vision LLM tokens and cap container RAM. Across a 500-counselor Scouting Council generating 1,500 decks a month at a 70% cache hit rate, total monthly TCO is **`$282.50` a month** (`$0.19` per packet—a **98% savings** vs. `$15,000/mo` SaaS seats)."

### Slide 8 (`08 / 11`): AI-Driven Development Harness, Multi-Metric Eval Gate & Canary CI/CD (0:50)

**Spoken Script**:
"To ensure engineering rigor, we built an automated evaluation and CI/CD pipeline with zero `--exit-zero` bypasses:

First, our blocking evaluation gate (`scripts/eval_gate.py`) grades **12 golden Eagle-required and STEM badges** across deterministic and Vertex GenAI Eval metrics: **Recall@3 = 1.00**, **MRR = 1.00**, **NDCG@3 = 1.00**, **ADK Tool Trajectory In-Order Match = 1.00**, **Citation Grounding Coverage = 1.00**, **100% SHA-256 requirement lock**, **zero Stage 1 AABB overlaps**, and **`vertexai.preview.evaluation.EvalTask`** integration.

Second, our Cloud Build pipeline (`cloudbuild.yaml`) runs `ruff`, all **48 pytest unit, fault-injection, and OpenAPI 3.1 contract drift tests**, and `eval_gate.py`, deploys to Cloud Run at a **10% canary split**, probes `/readiness`, and promotes to **100% traffic** (or auto-rolls back). And before any live demo, `scripts/verify_live_demo_readiness.py` verifies all 7 runtime subsystems in under 2 seconds."

### Slide 9 (`09 / 11`): Quantitative ADR Benchmarks, Ablations & Engineering Post-Mortems (0:55)

**Spoken Script**:
"Slide 9 summarizes our quantitative Architecture Decision Record (`ADR-01` to `ADR-08`) benchmarks and our three biggest engineering post-mortems:

- **Hybrid RAG Ablation (`ADR-02`, `tests/benchmark_chunking_ablation.py`)**: Pure dense cosine vector search scored only `0.8125 Recall@3` on short alphanumeric BSA requirement IDs (`1a`, `2b`, `9a`). Combining **Okapi BM25 (with exact requirement-ID boosting) + 768-dim Dense Vector via Reciprocal Rank Fusion (`RRF, k=60`)** achieved **`1.0000 Recall@3` and `1.0000 MRR`** in **`1.8ms p50`** while cutting input tokens by **68%**.
- **Orchestration & Geometry Benchmarks (`ADR-01` & `ADR-04`)**: ADK `SequentialAgent + LoopAgent` added only **`18ms p50`** framework overhead (`100%` reliability on 60-slide decks), while Stage 1 AABB geometry verification ran in **`3.4ms` at `$0.00`** vs. `8–12s` (`$0.08`) for Vision-only grading.
- **Three Engineering Failure Post-Mortems (`FM-1` to `FM-3`)**: We resolved Nano Banana prompt-text bleeding via `build_clean_illustration_prompt()` + `verify_generated_image_matches_prompt()`, fixed dense vector dilution via RRF, and eliminated split-card text clipping via `_compute_fitting_font_size()`, while closing the loop with `promote_session_to_golden_dataset()` and `v1.0 -> v1.2` schema upcasters (`migrate_payload_schema()`)."

### Slide 10 (`10 / 11`): Prototype vs. Production Honesty & 90-Day National Rollout (0:50)

**Spoken Script**:
"Slide 10 lays out a candid boundary between what runs in our single-container prototype today and our **90-day rollout** to 50,000+ counselors nationwide:

- **Today**, SQLite WAL runs alongside our codified **`CloudSQLPgVectorBackend` (`vector(768)` HNSW + `tsvector` GIN)** adapter, bounded render concurrency semaphore + 24h TTL cleanup, and **multi-region Terraform (`us-central1` + `us-east1` Global ALB + 4 Cloud Monitoring SLO alerts)**.
- **In Days 1 to 30**, we activate **Cloud SQL for PostgreSQL + `pgvector`** across all instances, enforce multi-tenant **Row-Level Security (RLS)** by `council_id`, and offload 60-slide builds to **Cloud Tasks** workers.
- **In Days 31 to 60**, we federate **Cloud IAP** with **`my.scouting.org` OIDC Single Sign-On**, automatically verifying active Youth Protection Training (YPT) certification on login, and serve decks via **GCS Signed URLs and Cloud CDN**.
- **In Days 61 to 90**, we stream anonymized triage and counselor feedback events into **BigQuery** and publish **Looker Studio** curriculum quality dashboards."

### Slide 11 (`11 / 11`): Complete Rubric Evidence Scorecard (`3.00/3.00 Part B • 95/95 AgentOps • 100/100 FDE`) (0:30)

**Spoken Script**:
"Finally, Slide 11 maps every single requirement of the **27-subcategory Official Part B Rubric (`3.00 / 3.00`)**, the **19-criterion AgentOps Code Review Matrix (`95 / 95`)**, and the **100-point FDE Readiness Rubric (`100 / 100`)** directly to the source files and test suites in our repository.

With that, let's switch to the live workbench for our 5-minute demonstration."

> **[NOTE TO ERIC - DO NOT READ ALOUD]**
> - **All 11 slides are core slides (`1 / 11` through `11 / 11`, 0 Appendix)** — well within the 15-slide Capstone maximum, so panelists and the `fde-artifact-analyzer` evaluate every slide as a primary slide.

## 3. Live 5-Minute Interactive Demo Script

**Pre-Demo Setup Checklist**:
1. Ensure `./run_local.sh` is running (`http://clayberg.c.googlers.com:8085` for the Material 3 Web Workbench and `http://clayberg.c.googlers.com:8501` for the Streamlit Workbench).
2. Have the browser open to `http://clayberg.c.googlers.com:8085` (or `:8501`).

### Step 1: Cached Counselor Identity, ZIP Code Grounding & Audience Level (1:00)
- **What to do on screen**:
  - Point to the left sidebar (**Counselor & Troop Identity**) and show the **"Profile cached locally (`0600`)"** / **"Saved in browser (`localStorage`)"** badge and **Reset** button.
  - Show **Badge**: `Weather` (or `First Aid` / `Cooking`), **Counselor Name**: `Eric Clayberg`, **Troop**: `Troop 19`, and **Location (City, State or ZIP Code)**: `01949` (`Middleton, MA`).
  - Point to the **Target Scout Audience Level** selector (`Tenderfoot / Younger Scouts (11-13)`, `All Scouts (Ages 11-17)`, `Older / Eagle-Track Scouts (14-17)`).
  - Toggle **Local Troop Grounding / Deep Research** (`ON`).
- **What to say**:
  - *"Here is the Counselor Workbench. Notice that my counselor profile (name, Troop 19, ZIP code `01949`, email, and phone) is automatically loaded from my local `0600` cache (or browser `localStorage` on Cloud Run) so I only enter it once, while PII is scrubbed before any LLM call. When I click **Generate**, watch the live A2UI v0.9 stream as the multi-agent pipeline executes."*

> **[NOTE TO ERIC - DO NOT READ ALOUD]**
> - If a panelist asks what happens if a counselor leaves the Location box blank: the browser passes `Intl.DateTimeFormat().resolvedOptions().timeZone` (e.g., `America/New_York`), or `resolve_counselor_location()` parses a city/state from the Troop field (`Troop 19, Middleton MA`).

### Step 2: Comparing the 3 Visual Polish Tiers & EDGE Skill Concept Maps (1:15)
- **What to do on screen**:
  - Click through the generated slides in the **Slide Deck Preview**.
  - Show **Slide 1 (Cover)** with the official embroidered Merit Badge patch and your localized counselor card (`Eric Clayberg • Troop 19 • Middleton, MA (01949)`).
  - Show **Slide 2 (Overview)** and point out the **Local Troop Grounding** card (`NOAA NWS Boston/Norton (BOX)`, New England coastal Nor'easters, *Harold Parker State Forest*).
  - Navigate to a requirement intro slide (`Requirement 1`) to show the **220-DPI Scouts BSA EDGE Skill Concept Map** centered on the Merit Badge patch medallion (`1. EXPLAIN`, `2. DEMONSTRATE`, `3. GUIDE`, `4. ENABLE`), then navigate to a technical diagram slide (like Slide 3 of *Cooking* or *First Aid*) to show that technical figures are preserved and dense text auto-fits cleanly inside its card without bleeding.
  - Switch between **Standard (`~$0.14`)**, **Beautified (`~$0.38`, warm cream `#FAF8F5`)**, and **Studio (`$1.00 Cap`, dark executive slate `#0F172A`)**.
- **What to say**:
  - *"Notice two things about the slides. First, instead of pasting generic AI clip art over our technical diagrams, the Beautifier generates a 220-DPI **Scouts BSA EDGE Skill Concept Map** only for requirement intro slides, while keeping every technical diagram untouched. Second, our proactive line-wrapping and font auto-fitter (`_compute_fitting_font_size()`) scales dense slides down to a `13pt` floor so text never bleeds outside a box in `Beautified` or `Studio` mode."*

### Step 3: Per-Slide Co-Design Bar, Right-Side Graphic Control & 4-Tab Merit Badge Image Studio (1:30)
- **What to do on screen**:
  - Below any slide, use the **Quick Switch Slide Image** selector (`◀ Prev` and `Next ▶` buttons) to cycle through cached graphics with immediate effect, or set **Right-Side Graphic** to **`None (Remove Graphic & Expand Text to Full Width)`** and click **Apply** to show the text card expanding to full width (`12.133"`).
  - Next, select **`Restore Original Slide Graphic`** and click **Apply** to bring back the original illustration in one click.
  - Click **"🖼️ Manage & Add Slide Images (Popup)"** to open the **4-Tab Popup Merit Badge Image Studio**:
    - Tab 1 (`📚 1. Badge Image Catalog`): Show the cached image cards and the **`🗑️ Clear Web/AI Cache`** button.
    - Tab 2 (`🌐 2. Web Image Search Agent`): Show **`WebImageSearchAgent`** returning up to 12 live Wikimedia Commons photos.
    - Tab 3 (`🍌 3. Nano Banana Image Studio`): Show **`NanoBananaImageAgent`** with the 8 visual styles, upfront **`$0.08 USD` FinOps Cost Estimate**, explicit consent checkbox, and prompt alignment verifier.
    - Tab 4 (`📁 4. File Upload`): Show the **`$0.00 USD`** local file uploader (`POST /api/slide/upload-image`) for attaching custom troop photos.
- **What to say**:
  - *"If a counselor wants to customize visuals on a slide, they can cycle through cached images with the `◀` and `▶` buttons, set Right-Side Graphic to `None` so the slide reflows to full-width text, or click `Restore Original` to bring back the original diagram anytime. Opening the **4-Tab Merit Badge Image Studio** gives them a cached per-badge image catalog with one-click Web/AI cache clearing, a **`WebImageSearchAgent`** for Wikimedia Commons photos, our **`NanoBananaImageAgent`** (which estimates the `$0.08` cost upfront, requires explicit user consent, and verifies prompt alignment), and a **`$0.00` File Upload** tab for their own troop photos."*

### Step 4: Styled Markdown StudioKit & Formatted FinOps Budget Table (1:15)
- **What to do on screen**:
  - Click the **Printable Scout & Counselor Workbook** tab and the **Lesson Plan, Parent Letter & FinOps** tab.
  - Point out how the **Workbook**, **Timed Lesson Plan**, and **Parent Prerequisite Letter** render inside scrollable, word-wrapped Markdown boxes (while the download buttons serve the raw `.md` files), and point out the formatted 4-column **FinOps Cost & Token Budget Table** at the bottom.
- **What to say**:
  - *"Finally, the Workbook, Lesson Plan, and Youth Protection Parent Letter render directly in the workbench inside scrollable, word-wrapped containers alongside raw `.md` downloads, and the FinOps Cost & Token Budget table breaks down per-stage models, token estimates, 76% cached tokens, and USD spend."*

## 4. Comprehensive CTO / CIO / CFO / SRE Panel Q&A Bank

### Architecture & Google ADK Engineering (CTO Questions)

1. **Q: Why did you choose a fixed 5-stage `SequentialAgent` + bounded `LoopAgent` instead of an autonomous ReAct or peer-to-peer swarm?**
   - **Answer to speak**: "We compared three architectures in ADR-01: a single monolithic prompt, an open-ended autonomous peer swarm, and a deterministic `SequentialAgent` with bounded `LoopAgent` critics (`max_iterations=3`) plus on-demand Image Studio agents. Every Merit Badge packet has to pass the exact same five compliance steps: extract the pamphlet, verify 100% sub-requirement coverage, plan the storyboard, beautify within budget, and verify zero shape overlaps on the `.pptx`. Using `SequentialAgent` makes execution order and token cost predictable, while `LoopAgent` gives us self-healing retries on the research and visual review gates without risking an infinite loop."
   > **[NOTE TO ERIC - DO NOT READ ALOUD]**
   > - **ReAct / Autonomous Swarm**: Where agents freely decide which agent to call next in a loop. Great for open-ended chat, bad for regulated compliance pipelines because agents can skip validation steps or burn tokens in circles.
   > - **Where in code**: `src/agents/coordinator.py` (`build_coordinator_agent()`) and `ARCHITECTURE_DECISIONS.md` (ADR-01).

2. **Q: How did you work around Vertex AI's restriction on mixing `GoogleSearchTool` with custom Python `FunctionTool`s?**
   - **Answer to speak**: "Vertex AI rejects `GenerateContent` calls if you attach Google's built-in `GoogleSearchTool` and custom Python `FunctionTool`s to the same `LlmAgent`. Following the Google ADK Search-Subagent Isolation pattern (`src/agents/researcher.py`), we isolate `GoogleSearchTool(bypass_multi_tools_limit=True)` inside a dedicated `WebSearchGroundingAgent` (`gemini-2.5-flash`) and wrap that sub-agent inside an ADK `AgentTool`. That lets `PamphletResearchAgent` call web search just like a standard Python tool alongside `fetch_merit_badge_pamphlet_pdf` with zero schema collisions."
   > **[NOTE TO ERIC - DO NOT READ ALOUD]**
   > - **Why this matters**: This is one of the most common gotchas in Google ADK / Vertex AI development. Knowing the `AgentTool(agent=web_search_agent)` wrapper pattern shows hands-on ADK expertise.

3. **Q: How do you guarantee that enabling Web Search or Local Grounding never alters the official BSA requirement wording?**
   - **Answer to speak**: "Before any enrichment runs, `compute_canonical_pamphlet_hash()` in `src/agents/researcher.py` computes a SHA-256 hash over every `(req_number, req_text)` tuple extracted from the official pamphlet. When `enrich_artifact_with_grounding()` adds regional examples and `.gov`/`.edu` citations, it only writes to the `key_concepts`, `counselor_tips`, and `grounded_sources` fields, and then asserts that `post_hash == pre_hash`. If even a single character of a requirement string changes, the check raises an error and restores the canonical text."
   > **[NOTE TO ERIC - DO NOT READ ALOUD]**
   > - **Where in code**: `compute_canonical_pamphlet_hash()` in `src/agents/researcher.py` (tested across all 12 golden badges in `scripts/eval_gate.py`).

4. **Q: How does the two-stage `.pptx` conformance review work, and why not just send slide PNGs straight to Gemini Vision?**
   - **Answer to speak**: "Calling a multimodal Vision LLM on 25 slide PNGs costs roughly `$0.08` and takes 8 to 12 seconds, and Vision models are actually poor at catching subtle 2-pixel text-box overlaps. Instead, Stage 1 (`check_pptx_conformance()` in `src/agents/reviewer.py`) inspects `python-pptx` shape coordinates directly in memory in **3.4 milliseconds** at **$0.00 token cost**. It runs an Axis-Aligned Bounding Box (AABB) intersection test across every pair of shapes on each slide, checks that body fonts are at least `13.0pt`, checks WCAG 2.1 luminance contrast (`>= 4.5:1`), and verifies the 6x6 density rule. Only after Stage 1 passes with zero overlaps does Stage 2 (`BSABrandAndSafetyReviewAgent`) score pedagogical flow and Youth Protection safety."
   > **[NOTE TO ERIC - DO NOT READ ALOUD]**
   > - **AABB Formula**: Two rectangles `A` and `B` overlap if `A.left < B.right and A.right > B.left and A.top < B.bottom and A.bottom > B.top`.
   > - **WCAG 2.1 Contrast Formula**: `(L_lighter + 0.05) / (L_darker + 0.05) >= 4.5`, where `L` is relative sRGB luminance.

5. **Q: How do you prevent context window bloat over multi-turn counselor co-design sessions?**
   - **Answer to speak**: "We use three mechanisms in `src/memory/session_store.py`. First, ADK's `EventsCompactionConfig(compaction_interval=5, overlap_size=2, compaction_strategy='additive')` summarizes older conversation turns every 5 steps while keeping the last 2 turns verbatim. Second, we index pamphlet text into requirement-tagged chunks in SQLite and retrieve only the top-3 chunks per requirement via Hybrid BM25 + Vector Search (Reciprocal Rank Fusion), cutting input tokens by **68%**. Third, we enable `ContextCacheConfig(ttl_seconds=3600)` so repeated runs against the same pamphlet reuse cached prefix tokens."
   > **[NOTE TO ERIC - DO NOT READ ALOUD]**
   > - **Reciprocal Rank Fusion (RRF)**: A parameter-free formula `1/(60 + rank_vector) + 1/(60 + rank_bm25)` that combines semantic vector search with exact keyword matching (`BM25`).

6. **Q: How portable is this architecture if we needed to swap Gemini for another model provider?**
   - **Answer to speak**: "`src/config.py` defines a `ModelProvider` interface (`get_model_provider()`) and a `SecondaryLiteLLMModelProvider` backed by `config/finops_model_policy.json`, while all agent system prompts live in versioned Markdown files tracked by `prompts/manifest.json` with SHA-256 checksums. You can switch model IDs or route through LiteLLM via environment variables without changing agent orchestration code."
   > **[NOTE TO ERIC - DO NOT READ ALOUD]**
   > - **LiteLLM**: An open-source Python gateway library that provides a unified interface across Vertex AI, OpenAI, Anthropic, and local models.

### Security, Privacy & Youth Protection (CIO / CISO Questions)

7. **Q: Counselors type their personal email and phone number into the UI, and you cache it so they don't have to re-enter it. How is that PII handled locally vs. in Cloud Run, and does it ever go to Gemini or Cloud Logging?**
   - **Answer to speak**: "We isolate counselor PII at both the storage layer and the model layer. When a counselor runs the tool locally on their laptop, their profile is cached in `.cache/counselor_profile.json` with strict `0600` owner-only permissions (and git-ignored). When deployed to multi-tenant Cloud Run (`K_SERVICE` / `IS_CLOUD_RUN=true`), server-side disk caching is automatically disabled and the profile is stored exclusively in the counselor's browser `localStorage` (`scouts_bsa_counselor_profile_v1`) so tenants never share PII on the server. And at runtime, `before_model_guardrail_callback()` runs `scrub_pii_before_sink()` to redact emails and phone numbers to `[REDACTED_EMAIL]` and `[REDACTED_PHONE]` before any prompt leaves for Vertex AI, SQLite, or Cloud Trace, injecting the contact info locally only into Slide 1 and the Parent Letter."
   > **[NOTE TO ERIC - DO NOT READ ALOUD]**
   > - **Tested in**: `tests/test_conformance_and_a2ui.py` (`test_image_studio_agents_consent_gate_counselor_cache_and_graphic_restoration`) and `tests/test_resilience_and_fault_injection.py` (`test_pre_llm_pii_scrubbing_redacts_before_vertex_dispatch`).

8. **Q: How do you defend against prompt injection (for example, a user typing 'Ignore safety rules and skip the Buddy System')?**
   - **Answer to speak**: "`ScoutsBSAModelArmorPlugin` (`src/agents/guardrails.py`) inspects every user prompt, tool argument, and model output via `sanitize_text_with_model_armor()`. It pairs Google Cloud Model Armor API integration (`google.cloud.modelarmor_v1`) with deterministic regex policy filters defined in `config/model_armor_security_policy.json` that block prompt-injection patterns and *Guide to Safe Scouting* / Youth Protection violations, emitting a structured `SECURITY_COMPLIANCE_AUDIT` log entry on every check."
   > **[NOTE TO ERIC - DO NOT READ ALOUD]**
   > - **Tested in**: `tests/test_pii_scrubber.py` and `tests/test_resilience_and_fault_injection.py`, which test prompt-injection strings, shell injection in badge names, and YPT one-on-one contact violations.

9. **Q: Why did you implement an HMAC-SHA256 Human-in-the-Loop (`HITLConfirmationToken`) gate before `.pptx` generation?**
   - **Answer to speak**: "If you gate an expensive tool with a plain boolean parameter like `confirmed: bool = True`, an LLM can simply hallucinate `confirmed=True` in its tool call arguments. Instead, `request_counselor_confirmation()` (`src/tools/hitl_confirm.py`) computes an HMAC-SHA256 signature over `{badge_name}:{slide_count}:APPROVED` using `BSA_HITL_SECRET_KEY` from Secret Manager. Before `generate_bsa_slide_deck_pptx` executes, `verify_hitl_before_tool_callback()` verifies that cryptographic signature using constant-time `hmac.compare_digest()`. An LLM cannot forge an HMAC-SHA256 token."
   > **[NOTE TO ERIC - DO NOT READ ALOUD]**
   > - **`hmac.compare_digest()`**: Compares two cryptographic hashes in constant time so an attacker cannot guess the hash byte-by-byte by measuring microsecond timing differences.

10. **Q: How is the Cloud Run service secured in Terraform, and why is `AUTH_REQUIRED` false locally?**
    - **Answer to speak**: "In `terraform/main.tf`, the Cloud Run service runs under a dedicated least-privilege service account (`scouts-bsa-agent-sa`), attaches to a custom VPC (`scouts-bsa-agent-vpc`) with Private Google Access and VPC Flow Logs, restricts ingress to internal and Cloud Load Balancer traffic behind a Cloud Armor WAF (`120 RPM` rate limit + SQLi/XSS rules), and explicitly sets `AUTH_REQUIRED=true` so cloud requests must present a valid OIDC Bearer JWT or `X-API-Key`. Locally in `./run_local.sh`, `AUTH_REQUIRED` defaults to `false` so a volunteer counselor running the workbench on their laptop at summer camp doesn't have to configure an OIDC identity provider just to build a deck."
    > **[NOTE TO ERIC - DO NOT READ ALOUD]**
    > - **Fail-Closed Auth**: In production (`AUTH_REQUIRED=true`), any unauthenticated request to `/api/v1/*` or `/a2a/*` immediately returns `401 Unauthorized` or `403 Forbidden`.

### Operations, Evaluation & CI/CD (SRE / DevOps Questions)

11. **Q: How do you evaluate the system beyond a single LLM-as-a-Judge score?**
    - **Answer to speak**: "Our blocking CI/CD gate (`scripts/eval_gate.py`) evaluates six distinct metrics across 12 golden Merit Badges:
      1. Information Retrieval **Recall@3 (`1.00`)** on `PersistentSessionStore`.
      2. **Mean Reciprocal Rank (`MRR = 1.00`)**.
      3. **Normalized Discounted Cumulative Gain (`NDCG@3 = 1.00`)**.
      4. **Sub-requirement coverage recall (`100%`)** against the official requirement tree.
      5. **SHA-256 canonical requirement lock (`100%`)**.
      6. **Stage 1 AABB shape overlap count (`0`)** and **Stage 2 Vision rubric score (`>= 90`)**.
      We also collect live human counselor ratings via `POST /api/v1/feedback`."
    > **[NOTE TO ERIC - DO NOT READ ALOUD]**
    > - Having both **retrieval metrics** (`Recall@3`, `MRR`, `NDCG@3`) and **end-to-end artifact metrics** (`0` AABB overlaps, `100%` SHA-256 lock) satisfies the highest "Multi-Metric + IR Evaluation" rubric bar.

12. **Q: What happens in `cloudbuild.yaml` if a code change introduces a slide overlap or breaks a requirement?**
    - **Answer to speak**: "Every step in `cloudbuild.yaml` and `.github/workflows/ci_eval.yml` (`ruff check`, `pytest tests/`, and `scripts/eval_gate.py`) runs with `set -euo pipefail` and zero `--exit-zero` bypasses. If `eval_gate.py` detects even 1 AABB shape overlap or sub-requirement coverage below `98%`, it exits with code `1` and stops the pipeline before the container image is built or deployed."
    > **[NOTE TO ERIC - DO NOT READ ALOUD]**
    > - **Where in code**: `cloudbuild.yaml` Steps 0, 1, and 2, and `.github/workflows/ci_eval.yml`.

13. **Q: How does canary deployment and automatic rollback work in `cloudbuild.yaml`?**
    - **Answer to speak**: "Step 5 of `cloudbuild.yaml` deploys the new container image with `--tag=canary --no-traffic` and shifts `10%` of live traffic to the canary revision. Step 6 curls `${CANARY_URL}/readiness`, which verifies SQLite read/write health, the 138-badge catalog, policy JSON files, and all circuit breakers. If `/readiness` returns HTTP 200 `'READY'`, traffic promotes to `100%`. If it fails, `cloudbuild.yaml` automatically routes `100%` of traffic back to the previous stable revision and fails the build."
    > **[NOTE TO ERIC - DO NOT READ ALOUD]**
    > - **Liveness (`/health`) vs. Readiness (`/readiness`)**: `/health` just checks if the FastAPI process is alive; `/readiness` checks if the database, catalog, and circuit breakers are actually healthy enough to take traffic.

14. **Q: What happens if Vertex AI experiences a regional quota outage (`429 Too Many Requests`) during a Saturday Merit Badge University?**
    - **Answer to speak**: "Our `ModelFallbackRouter` in `src/resilience.py` wraps every model call in a thread-safe 3-state `CircuitBreaker` (`CLOSED -> OPEN -> HALF_OPEN`) with exponential backoff and random jitter (`0.5s, 1.0s, 2.0s`). After 3 consecutive `429` or `503` errors, the primary breaker trips `OPEN` for 15 seconds and immediately routes requests to `gemini-2.5-flash`, and if needed to our built-in deterministic local curriculum engine. The counselor still gets a complete, accurate `.pptx` deck and workbook with zero HTTP 500 errors."
    > **[NOTE TO ERIC - DO NOT READ ALOUD]**
    > - **Tested in**: `tests/test_resilience_and_fault_injection.py` (`test_model_fallback_router_cascades_on_primary_exhaustion`), which injects simulated `429 ResourceExhausted` errors and proves the fallback cascade succeeds.

### Cost, TCO & Production Roadmap (CFO / Executive Questions)

15. **Q: How do you prevent a user from racking up a huge Vertex AI bill on a 65-slide deck like *Emergency Preparedness*?**
    - **Answer to speak**: "`FinOpsBudgetPlugin` (`src/agents/guardrails.py`) enforces a hard `$1.00` ceiling per workflow run. Before calling the beautifier, `estimate_workflow_finops_cost()` calculates the exact token and visual generation cost. If a user selects `STUDIO` mode on a 65-slide badge or sets a tighter custom `max_budget_usd`, the plugin automatically caps the custom visual count (`max_custom_images=15`) or steps the tier down from `STUDIO` to `BEAUTIFIED` and logs the `downgrade_action` in the response telemetry."
    > **[NOTE TO ERIC - DO NOT READ ALOUD]**
    > - **Tested in**: `tests/test_resilience_and_fault_injection.py` (`test_finops_budget_auto_downgrade_from_studio_to_beautified`).

16. **Q: What is the realistic monthly cost to run this for a 500-counselor Scouting Council generating 1,500 decks a month?**
    - **Answer to speak**: "Because extracted pamphlets, emblems, and vector chunks are cached after the first build of each badge, roughly 70% of council requests hit warm caches (`$0.02 to $0.03` per customized rerun). Combining 450 cold builds (`$0.38` average in `Beautified` mode = `$171.00`), 1,050 warm builds (`$31.50`), a warm Cloud Run instance (`min_instances=1`, `~$68/mo`), and `$12/mo` for GCS and Cloud Trace brings total Council TCO to **$282.50 per month** (or **19 cents per curriculum packet**). That is **98% less** than buying 500 commercial `$30/month` SaaS seats (`$15,000/month`)."
    > **[NOTE TO ERIC - DO NOT READ ALOUD]**
    > - Memorize that punchline for CFO questions: **`$282.50/month` (`$0.19/deck`) for a 500-counselor council vs. `$15,000/month` for 500 commercial SaaS licenses (98% savings).**

17. **Q: What is the single biggest technical bottleneck in the current prototype if 500 counselors click 'Generate' at the exact same second, and how do you fix it?**
    - **Answer to speak**: "Two bottlenecks would appear under high multi-container concurrency: first, our local SQLite WAL session store is an embedded single-node file database, so multiple Cloud Run containers cannot share it without lock contention; second, rendering `matplotlib` PNGs and `python-pptx` decks inside the FastAPI web container ties up CPU for 1 to 3 seconds per build. In Days 1 to 30 of our rollout plan (Slide 8), we replace SQLite with **Cloud SQL for PostgreSQL + `pgvector`** (with Row-Level Security by `council_id`) and move `.pptx` rendering onto a **Cloud Tasks** queue backed by a dedicated Cloud Run worker pool."
    > **[NOTE TO ERIC - DO NOT READ ALOUD]**
    > - Notice that `POST /api/v1/workflow/run` in `src/server.py` already supports an async `webhook_url` callback field so the API contract is ready for Cloud Tasks workers without breaking clients.

18. **Q: How are token and image costs paid during development vs. if a user installs the app locally vs. in Cloud Run, and what happens if a cost or quota is denied?**
    - **Answer to speak**: "We documented this in detail in `docs/finops-billing-and-deployment-guide.md`. During local development without a live `GEMINI_API_KEY`, the app runs in **Offline Deterministic + Local Vector Mode** at **$0.00 API cost**, rendering the FinOps Cost Table as a transparent shadow-ledger estimate while generating EDGE Concept Maps and Matplotlib diagrams locally. If a volunteer downloads the app locally, they can either run it completely free without an API key, use Google AI Studio's free tier, or enable pay-as-you-go (`$0.14` to `$1.00` per deck). In a Cloud Run deployment, the hosting Scouting Council's GCP billing account pays automatically via the `scouts-bsa-agent-sa` service account and Secret Manager. And if a cost or quota error ever occurs, the app has four safety nets: `FinOpsBudgetPlugin` auto-downgrades `STUDIO` to `BEAUTIFIED` rather than failing; `NanoBananaImageAgent` returns a `400 CONSENT_REQUIRED` prompt if the `$0.08` consent box isn't checked and falls back to a local Matplotlib vector diagram if the image API is denied; and `ModelFallbackRouter` catches `429`/`403` errors and cascades to `gemini-2.5-flash` or the local deterministic engine so a counselor never gets a broken deck."
