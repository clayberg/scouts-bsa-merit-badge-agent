# FDE Capstone Companion Guide: Slide-by-Slide Explainer, End-to-End Architecture Primer & Jargon Decoder

**Prepared for**: Eric Clayberg  
**Companion Slide Deck**: [FDE Capstone Executive Readout (Google Slides)](https://docs.google.com/presentation/d/1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E/edit)  
**Purpose**: This guide is written specifically for you so you can walk into the Capstone review panel knowing every moving part of the **Scouts BSA Merit Badge Counselor Workbench**, from how raw BSA pamphlets and requirements are gathered and indexed, to how SQLite and external APIs interact, to when each of the 7 specialist AI agents engages and consumes tokens, to how every slide in the Executive Readout maps to the capstone grading rubric.

---

## 1. End-to-End Application Deep Dive: From BSA Source Gathering to Final Slide Construction

When a panelist asks, *"Walk me through what actually happens under the hood from the moment you pick a Merit Badge to the moment the `.pptx` downloads,"* here is the complete lifecycle broken into six concrete phases.

### 1.1 How BSA Source Material is Gathered, Indexed, and Cached

Before a counselor ever clicks **Generate**, the workbench relies on three layers of authoritative Scouts BSA source material so the AI never invents requirements or uses outdated wording:

1. **The 138-Badge Canonical Catalog & Requirement Registry (`src/config.py`, `src/tools/scouting_scraper.py`)**:
   - **What is gathered**: Scouts BSA maintains **138 official current Merit Badges** (including Eagle-required badges like *First Aid*, *Cooking*, *Camping*, *Environmental Science*, *Personal Management*, and *Citizenship in Society*, plus electives like *Weather*, *Robotics*, and *Welding*). Note: In our UI dropdown, we also include 2 clearly labeled `(Test Stub)` entries for automated fault-injection tests, bringing the raw selector array to 140 items while the official BSA curriculum count is strictly **138 badges**.
   - **Where it comes from**: Requirement trees (`1`, `2a`, `2b`, `9b(1)`, etc.), official pamphlet URLs (`https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/<Badge>.pdf`), Digital Resource Guide (DRG) links, and official high-resolution Scout Shop merit badge patch emblems (`assets/badge_emblems/<slug>.png`) and pamphlet covers (`assets/pamphlet_covers/<slug>_cover.png`).
   - **Why we lock requirement text with SHA-256 (`compute_canonical_pamphlet_hash()`)**: In Scouts BSA, counselors are strictly forbidden from adding to, deleting from, or rewording official Merit Badge requirements (*Guide to Advancement* §7.0.4.7). As soon as the official requirement tree is loaded for a badge, the app computes a cryptographic **SHA-256 hash** over every requirement number and verbatim requirement string. Later stages (like web search grounding) are only allowed to append *supplementary teaching notes*. After enrichment finishes, the app recomputes the SHA-256 hash of the requirement strings and asserts it is identical to the original hash. If a single character of official requirement wording was altered, the run halts immediately.

2. **Pamphlet PDF Parsing & Hybrid Indexing (`fetch_merit_badge_pamphlet_pdf()`)**:
   - **Gathering & Extraction**: Official BSA Merit Badge Pamphlets are 60-to-90-page multi-column PDFs (`45,000` to `70,000` tokens if dumped raw). We use **PyMuPDF (`fitz`)** to extract text blocks, page numbers, section headings, and embedded technical diagrams/figures, pairing each passage with the specific requirement number (`req_number`) it teaches.
   - **Why we don't stuff the whole PDF into every LLM prompt**: Sending 65,000 tokens of raw pamphlet text to Gemini on every agent turn would cost ~$0.45+ per badge in input tokens alone and cause the model to lose focus on sub-requirements like `4b(2)`.
   - **How Hybrid Indexing works (`PersistentSessionStore` in `src/memory/session_store.py`)**:
     - Each extracted pamphlet section is stored as a chunk in the SQLite `pamphlet_chunks` table with both its raw text and a numeric **768-dimensional vector embedding** (`embedding_json`).
     - When `SlideContentPlannerAgent` plans the slides for Requirement `3a`, it queries the store using **Hybrid Retrieval** combined via **Reciprocal Rank Fusion (RRF, `k = 60`)**:
       - **BM25 Lexical Search (55% weight)**: Matches exact keywords and requirement IDs (`"Req 3a"`, `"tourniquet"`, `"hypothermia"`, `"165 degrees F"`). Vector search alone can blur exact numbers or requirement codes; BM25 guarantees exact matches rank at the top.
       - **Cosine Vector Similarity (45% weight)**: Matches conceptual meaning even when wording differs (e.g., matching a pamphlet paragraph about *"preventing heat exhaustion on summer hikes"* to a requirement about *"hot-weather safety precautions"*).
     - By retrieving only the top matching chunks per requirement and pinning the shared pamphlet system instructions inside Vertex AI's **Context Cache (`ContextCacheConfig`, 1-hour TTL)**, we achieve a **76% token cache hit rate** and cut input token consumption by **68%**.

3. **Per-Badge Visual & Image Catalog Caching (`assets/badge_image_catalog/<badge_slug>/` + SQLite `badge_image_catalog`)**:
   - Every image associated with a badge (whether extracted from the official BSA pamphlet, generated as a 220-DPI technical cutaway or EDGE Skill Concept Map, found on Wikimedia Commons by `WebImageSearchAgent`, custom-generated by `NanoBananaImageAgent`, or uploaded locally by the counselor via `upload_custom_slide_image()`) is saved to disk under `assets/badge_image_catalog/<badge_slug>/` and indexed in the SQLite `badge_image_catalog` table with a SHA-256 content hash (`sha256_hash`).
   - Caching images per merit badge means that once you search for, upload, or generate an illustration for *Cooking* or *First Aid*, it stays in that badge's popup **Image Studio Catalog** permanently so you can reuse it across sessions or switch between multiple candidate images on a slide with zero additional API cost.

---

### 1.2 The Six Runtime Phases: Step-by-Step Execution

Here is the chronological flow when you run the workbench:

#### Phase 0: Counselor Profile Auto-Load & Configuration (`0 Tokens`)
- **What happens**: When you open the Streamlit UI (`src/app.py`) or the Material 3 Web Workbench (`ui/index.html` + `src/server.py`), the app loads your saved **Counselor Profile** (`counselor_name`, `troop_affiliation`, `location_or_zip`, `email_address`, `phone_number`, `custom_troop_logo_path`) so you only have to type your details once.
- **How PII is cached and protected**:
  - **Local Laptop Mode**: Saved in `.cache/counselor_profile.json` with `0600` (owner-read/write-only) file permissions and excluded via `.gitignore`.
  - **Cloud Run / Web Mode**: Stored exclusively in your browser's client-side `localStorage` (`scouts_bsa_counselor_profile_v1`). The server detects multi-tenant Cloud Run (`K_SERVICE` / `IS_CLOUD_RUN=true`) and refuses to write counselor PII to shared server disk.
  - **Strict PII Firewall (`scrub_pii_before_sink()`)**: Your email address and phone number are **never** sent to Gemini, written to SQLite telemetry, or emitted to OpenTelemetry traces. They are held in local memory and injected directly into **Slide 1 (Cover Slide)** and the **Prerequisite & Parent Welcome Letter** during local file assembly.

#### Phase 1: Requirement Extraction, Location Resolution & Deep Research (`Stage 1`)
- **Agents engaged**:
  1. **`PamphletResearchAgent`** (`gemini-2.5-pro`): Calls `fetch_merit_badge_pamphlet_pdf()` to load the official requirement tree (`1a`, `1b`, `2a`, etc.), pamphlet excerpts, and baseline technical diagrams, and locks the requirement text with `compute_canonical_pamphlet_hash()`.
  2. **`WebSearchGroundingAgent`** (`gemini-2.5-flash` wrapped in an ADK `AgentTool` with `GoogleSearchTool`):
     - Calls `resolve_counselor_location()` to turn your ZIP code or town (e.g., `01949` -> `Middleton, MA - Northeast / New England`) into a concrete climate and terrain profile.
     - Calls `enrich_requirements_with_deep_research()` to attach 2026 local hazards, state regulations, and troop field exercises (for example, NWS Boston/Norton office examples and Mount Washington valley wind patterns for *Weather*, or Eastern Equine Encephalitis tick/mosquito protocols and New England backcountry hypothermia steps for *First Aid*).
     - Re-verifies the SHA-256 requirement hash to prove zero official words were changed.
  3. **`ResearchCoverageCriticAgent`** (`gemini-2.5-pro` inside an ADK `LoopAgent`, `max_iterations=2`): Calls `verify_subrequirement_coverage()` to verify that every single sub-requirement (`a`, `b`, `c`, `(1)`, `(2)`) is present before allowing the pipeline to proceed.

#### Phase 2: Multi-Archetype Storyboard & StudioKit Generation (`Stage 2`)
- **Agent engaged**: **`SlideContentPlannerAgent`** (`gemini-2.5-pro`).
- **What happens**:
  - Calls `generate_slide_storyboard()` to map every requirement and sub-requirement onto our **12 pedagogical slide archetypes** (such as `TITLE_HERO`, `SECTION_DIVIDER`, `SPLIT_VISUAL_EXPLAINER`, `CONCEPT_TEXT_SLIDE`, `COMPARISON_TABLE`, `SAFETY_ALERT_CARD`, `PROCESS_STEP_FLOW`, `FIELD_SCENARIO_CHALLENGE`, and `INTERACTIVE_QUIZ_CHECK`).
  - Scales deck size based on your selected **Curriculum Depth**:
    - **Standard Deck (`18-26 slides`)**: Sized for a 60-90 minute troop meeting or Merit Badge clinic.
    - **Deep Dive / Camp School Deck (`50-70+ slides`)**: Gives every leaf sub-requirement (`2a`, `2b`, `2c`) its own dedicated instructional slide, plus hands-on field lab practicums and section review checkpoints.
  - Writes structured **EDGE Method Speaker Notes** (`[SAY]`, `[DEMONSTRATE]`, `[ASK SCOUTS]`) tailored to your selected **Target Scout Audience** (`Tenderfoot / Younger Scouts (Ages 11-13)`, `Older / Eagle-Track Scouts (Ages 14-17)`, or `All Scouts (Ages 11-17)`).
  - Generates the **Printable Scout & Counselor Workbook (`.md`)**, the **Counselor Session Agenda & Lesson Plan (`.md`)** (`generate_counselor_session_agenda()`), and the **Prerequisite & Parent Welcome Letter (`.md`)** (`generate_prerequisite_parent_letter()`).

#### Phase 3: Visual Polish, Theme Application & EDGE Skill Concept Maps (`Stage 3`)
- **Agent engaged**: **`SlideBeautifierAgent`** (`gemini-2.5-flash`).
- **What happens**:
  - Calls `beautify_slide_storyboard()` and applies your chosen **Visual Polish Tier**:
    - **`STANDARD` (`~$0.14`)**: High-contrast white canvas (`#FFFFFF`) with official BSA Navy (`#003F87`) and Gold (`#FDB813`) headers. Zero AI concept map images generated.
    - **`BEAUTIFIED` (`~$0.38`)**: Warm cream editorial canvas (`#FAF8F5`) with rotating accent palettes (`BSA_HERITAGE_NAVY`, `CAMPFIRE_AMBER`, `HIGH_SIERRA_FOREST`, `ARCTIC_SLATE`), rounded cards, and up to **5 custom 220-DPI Scouts BSA EDGE Skill Concept Maps** (`generate_ai_editorial_illustration()`) placed on requirement introduction slides.
    - **`STUDIO` (`~$1.00`)**: Dark executive slate canvas (`#0F172A`) with luminous cyan/gold accents and up to **15 dark-slate 220-DPI EDGE Skill Concept Maps**, while **never overwriting** existing pamphlet figures or technical cutaways (`has_custom_diagram` check).
  - Snapshots every slide's initial graphic into immutable `original_diagram_path`, `original_diagram_url`, `original_visual_caption`, `original_visual_source_label`, and `original_archetype` fields, and seeds the badge's **Image Studio Catalog** (`seed_badge_image_catalog_from_storyboard()`).
  - Checks `FinOpsBudgetPlugin` (`max_budget_usd = $1.00`). If a custom lower budget cap is set, `FinOpsBudgetPlugin` automatically scales back from `STUDIO` to `BEAUTIFIED` before exceeding the cap.

#### Phase 4: Cryptographic Human-in-the-Loop (HITL) Confirmation (`Stage 4`)
- **What happens**: Before running the PowerPoint compilation engine, `request_counselor_confirmation()` generates an **HMAC-SHA256 `HITLConfirmationToken`** signed with `BSA_HITL_SECRET_KEY` over `{badge_name}:{slide_count}:APPROVED`.
- When `PowerPointBuilderAgent` invokes `generate_bsa_slide_deck_pptx()`, the ADK `before_tool_callback` (`verify_hitl_before_tool_callback()`) cryptographically verifies the HMAC signature. An LLM cannot hallucinate or forge a valid signature on its own.

#### Phase 5: Widescreen `16:9` PowerPoint Compilation & Two-Stage Review Loop (`Stage 5`)
- **Agents engaged**:
  1. **`PowerPointBuilderAgent`** (`gemini-2.5-flash`): Calls `generate_bsa_slide_deck_pptx()` (`src/tools/pptx_builder.py`) to assemble the native `13.333" x 7.5"` widescreen `.pptx` presentation (`<Badge>_<Tier>_<Depth>_Merit_Badge_Deck.pptx`).
     - Uses `_compute_fitting_font_size()` to calculate wrapped line counts (`line_spacing = 1.18`, paragraph spacing reserve, `0.86` safety factor) so dense slides automatically scale body fonts between `16.5pt` and `13.0pt` and never bleed outside card borders in `STANDARD`, `BEAUTIFIED`, or `STUDIO` mode.
  2. **`BSABrandAndSafetyReviewAgent`** (`gemini-2.5-pro` inside an ADK `LoopAgent`, `max_iterations=3`):
     - **Stage 1 (`check_pptx_conformance()`, `<10ms`, `$0.00` tokens)**: Inspects every shape in the generated `.pptx` in memory using deterministic geometry math:
       - **Axis-Aligned Bounding Box (AABB) Overlap Check**: Verifies no two content shapes overlap (`overlap_area_sq_in == 0.0`).
       - **Canvas Boundary Check**: Verifies no shape extends past `13.333" x 7.5"`.
       - **Readability Floor Check**: Verifies no body font is smaller than `13.0pt` (`13.0pt` floor for dense tables/cards, `14.0pt` standard body, `22.0pt+` headers).
       - **WCAG 2.1 AA Contrast Check**: Verifies text-to-background luminance contrast is at least `4.5:1` (typically `11.4:1` to `14.8:1`).
       - **SHA-256 Visual Uniqueness Check**: Verifies the same image file isn't duplicated lazily across unrelated slides.
     - **Stage 2 (`validate_presentation_deck()` / `run_stage2_vision_critique()`)**: Checks requirement coverage, Scouts BSA Guide to Safe Scouting alignment, and visual layout quality. If any check fails, the `LoopAgent` feeds the specific slide index and error coordinates back to the builder to fix automatically.

#### Phase 6: Interactive Per-Slide Co-Design & Merit Badge Image Studio (`On-Demand`)
- Once the deck renders in the UI, you can inspect every slide in the **Interactive Slide Preview**, read styled wrapped Markdown in the **Workbook** and **Lesson Plan / Parent Letter / FinOps Table** tabs, or customize individual slides:
  - **Right-Side Graphic Control**:
    - Choosing **`None (Remove Graphic & Expand Text to Full Width)`** removes the image and automatically converts the slide from `SPLIT_VISUAL_EXPLAINER` to `CONCEPT_TEXT_SLIDE` (`12.133"` full-width text card) in both the live preview and the `.pptx`.
    - Choosing **`Restore Original Slide Graphic`** restores the initial picture/diagram (`original_diagram_path`) and original layout archetype (`original_archetype`) in one click.
    - When multiple images are cached for a badge, an **Inline Quick Switch Slide Image** selector (with `◀ Prev` and `Next ▶` buttons) lets you flip between them immediately.
  - **4-Tab Popup Merit Badge Image Studio (`src/agents/image_studio.py`)**:
    - Opens an interactive modal with four tabs for managing slide visuals:
      1. **📚 1. Badge Image Catalog**: Shows all cached images for the current badge (each with a preview, source badge, and description), plus a **🗑️ Clear Web/AI Cache** button (`DELETE /api/badge/images`) that purges web-searched and AI-generated cache items while preserving official pamphlet figures (`PAMPHLET`) and local file uploads (`USER_UPLOAD`).
      2. **🌐 2. Web Image Search Agent (`WebImageSearchAgent`, `gemini-2.5-flash`)**: Queries live Wikimedia Commons for up to 12 public-domain photographs or diagrams matching your topic, caches selected images in `assets/badge_image_catalog/<badge_slug>/` and SQLite, and applies them to the current slide in one click.
      3. **🍌 3. Nano Banana Image Studio (`NanoBananaImageAgent`, `gemini-2.5-flash-image` / Imagen 3)**: First runs `estimate_nano_banana_image_cost()` to show the upfront cost (**`$0.08 USD` per image**, ~`2,580` tokens across generation and verification) and requires you to check the **explicit FinOps consent box (`user_consented=True`)** before generating a custom 220-DPI text-free illustration across 8 visual styles (`Photorealistic Image`, `Line Drawing`, `Cartoon Drawing`, `Technical Diagram`, `Editorial Field Illustration`, `Annotated Technical Cutaway`, `4-Panel Field Storyboard`, or `Comparison & Decision Visual`), verified by `verify_generated_image_matches_prompt()`.
      4. **📁 4. File Upload (`POST /api/slide/upload-image`, `$0.00 USD`)**: Lets you upload a local `.png`, `.jpg`, `.jpeg`, or `.webp` image (`<= 10 MB`) from your computer, normalizes it to RGB PNG (`max 1600px`), registers it as `USER_UPLOAD` in the badge catalog, and applies it to the current slide.

---

## 2. Deep-Dive Technical Questions: SQLite, External APIs, Token Consumption & Agent Engagement

### 2.1 What is the Exact Role of SQLite in the Product?

SQLite (`deliverables/adk_sessions.db`, managed by `PersistentSessionStore` in `src/memory/session_store.py`) is our embedded, zero-ops relational + vector persistence layer. We configure it with **`PRAGMA journal_mode=WAL;` (Write-Ahead Logging)** so concurrent readers and background async writers (`aiosqlite` / thread-pooled sync operations) never lock each other out.

It houses **four specific tables**:

| SQLite Table | What It Stores | Why It Exists in the Architecture |
| :--- | :--- | :--- |
| **`sessions`** | `session_id`, `badge_name`, `state_json` (compacted workflow state, token/cost ledger, active storyboard metadata), `updated_at` | Persists ADK session state across turns and container restarts. Before writing `state_json`, `scrub_pii_before_sink()` redacts any emails, phone numbers, or SSNs so the database stays 100% PII-free. |
| **`pamphlet_chunks`** | `chunk_id` (Primary Key), `badge_name` (Indexed), `req_number`, `chunk_text`, `embedding_json` (768-dim float vector), `created_at` | Powers our **Hybrid RAG Engine**. Instead of paying for an external vector database server (like Pinecone or a permanent $300/mo Vertex AI Vector Search endpoint) for 138 pamphlets, SQLite stores the chunked pamphlet text and embeddings locally/in-container and runs sub-15ms hybrid **BM25 + Cosine Vector** retrieval with **Reciprocal Rank Fusion (RRF)**. |
| **`badge_image_catalog`** | `image_id` (Primary Key), `badge_name` (Indexed), `req_number`, `title`, `description`, `source_type` (`PAMPHLET`, `WEB_SEARCH`, `NANO_BANANA`, `USER_UPLOAD`, `EDGE_CONCEPT_MAP`), `file_path`, `url`, `sha256_hash`, `cost_usd`, `created_at` | Powers the **Merit Badge Image Studio Catalog & Carousel**. Caches every graphic discovered, uploaded, or generated for a badge so counselors can switch between images across slides and sessions without re-downloading or re-paying for AI image generation. |
| **`hitl_feedback`** | `feedback_id`, `session_id`, `badge_name`, `counselor_rating` (`1-5`), `requirement_verified` (`0/1`), `comments` (PII-scrubbed), `created_at` | Stores human counselor quality ratings and requirement accuracy sign-offs submitted via the UI or `/api/v1/feedback` for continuous AgentOps evaluation. |

**Why isn't Counselor Contact Info stored in SQLite?**  
By design! SQLite (`adk_sessions.db`) is an application state and curriculum database that may be inspected for debugging or mounted on a shared Cloud Filestore volume in Cloud Run. Storing counselor personal emails and phone numbers in SQLite would mix PII with telemetry and risk cross-tenant leakage in Cloud Run. Keeping local counselor contact info in `.cache/counselor_profile.json` (`0600` permissions) on a laptop and in client-side `localStorage` on the web cleanly separates personal identity from application telemetry.

---

### 2.2 What is the Role of External APIs?

Every external API in the system has a deterministic local fallback or cache so a counselor at a summer camp with spotty Wi-Fi is never left stranded:

| External API / Service | Where It Is Used | What It Does & How Fallback Works |
| :--- | :--- | :--- |
| **Vertex AI Gemini API (`gemini-2.5-pro` & `gemini-2.5-flash`)** | `src/agents/researcher.py`, `planner.py`, `beautifier.py`, `builder.py`, `reviewer.py`, `image_studio.py` | `gemini-2.5-pro` handles deep curriculum reasoning (extracting requirement trees, planning 12-archetype storyboards, and auditing coverage/safety). `gemini-2.5-flash` handles high-speed grounding, theme assignment, and tool routing. Wrapped in `ModelFallbackRouter` (`Pro -> Flash -> Deterministic Curriculum Engine`) and `CircuitBreaker` (`failure_threshold=3`). |
| **Google Search Grounding (`GoogleSearchTool`)** | `WebSearchGroundingAgent` (`src/agents/researcher.py`) | Queries live regional weather offices, state conservation laws, local troop field venues, and updated 2026 safety advisories based on the counselor's ZIP code. |
| **Gemini 2.5 Flash Image (`Nano Banana`) & Vertex AI Imagen 3** | `NanoBananaImageAgent` (`src/agents/image_studio.py`) & `SlideBeautifierAgent` (`src/agents/beautifier.py`) | Synthesizes custom slide-specific illustrations across 8 visual styles (`Photorealistic Image`, `Line Drawing`, `Cartoon Drawing`, `Technical Diagram`, `Editorial Field Illustration`, `Annotated Technical Cutaway`, `4-Panel Field Storyboard`, `Comparison & Decision Visual`) and 220-DPI Scouts BSA EDGE Skill Concept Maps. Gated by `$0.08/image` upfront cost estimation, explicit user consent (`user_consented=True`), and `verify_generated_image_matches_prompt()`. |
| **Wikimedia Commons REST API (`commons.wikimedia.org/w/api.php`)** | `WebImageSearchAgent` (`src/agents/image_studio.py`) | Searches up to 12 public-domain and Creative Commons educational photographs and diagrams matching a slide's topic, downloads high-res thumbnails into `assets/badge_image_catalog/<badge_slug>/`, and strips HTML metadata into clean descriptions. |
| **Scouting.org Filestore & Scout Shop CDN (`filestore.scouting.org`, `cdn.oud.scouting.org`)** | `src/tools/scouting_scraper.py`, `src/config.py` | Provides official Merit Badge Pamphlet PDFs, Digital Resource Guides (DRGs), cover artwork, and official Merit Badge patch emblems (cached locally under `assets/badge_emblems/` and `assets/pamphlets/`). |
| **Google Cloud DLP & Model Armor (`ScoutsBSAModelArmorPlugin`)** | `src/security.py`, `src/observability/logging_setup.py` | Scans prompts and tool outputs against 12 regex/DLP patterns for prompt injection, Youth Protection (YPT) policy violations, and PII (`EMAIL`, `PHONE_NUMBER`, `US_SSN`) before model invocation or log export. |
| **Google Cloud Trace (OpenTelemetry) & Cloud Logging** | `src/observability/tracing.py`, `src/server.py` | Exports W3C `traceparent` spans (`gen_ai.agent.step`, `gen_ai.tool.call`) and structured JSON logs (`severity`, `logging.googleapis.com/trace`, `intent`, `outcome`). |
| **Google Cloud Secret Manager** | `src/config.py`, `terraform/main.tf` | Injects `BSA_API_KEY` and `BSA_HITL_SECRET_KEY` into the Cloud Run container runtime via least-privilege IAM without hardcoding secrets in code or Docker images. |

---

### 2.3 When Does Each Agent Engage, and When/How Are Tokens Consumed?

A common capstone panel question is: *"Do all 7 agents run on every single click? How do you keep token costs under $0.40 for a Beautified deck?"*

Here is the breakdown of **when each of the 9 agent components (1 root coordinator + 7 specialist sub-agents + HITL gate) engages** and **how many tokens and dollars each step consumes**:

| Step / Action | Agent Engaged | Model Used | When It Engages | Typical Token Consumption | Typical Cost (USD) | Why Token Usage Is Low |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **0. Supervision & Compaction** | `MeritBadgeCoordinatorAgent` | ADK Orchestrator (`EventsCompactionConfig`) | Every pipeline run | `0` direct LLM tokens (manages state & compacts history every 5 turns) | **`$0.000`** | Uses additive sliding-window compaction (`compaction_interval=5, overlap_size=2`) so turn history never balloons. |
| **1a. Pamphlet & Requirement Extraction** | `PamphletResearchAgent` | `gemini-2.5-pro` | Pipeline Stage 1 | ~`6,200` input (`76%` cached) / ~`1,400` output | **`~$0.018`** | Reads hybrid BM25 + vector chunks from SQLite (`pamphlet_chunks`) + Vertex AI Context Cache instead of reading a 70,000-token PDF raw. |
| **1b. Local ZIP & Deep Research Grounding** | `WebSearchGroundingAgent` (`AgentTool`) | `gemini-2.5-flash` + `GoogleSearchTool` | Pipeline Stage 1 (when Deep Research is checked) | ~`3,800` input / ~`1,100` output | **`~$0.004`** | Uses fast, low-cost `gemini-2.5-flash` exclusively for web search synthesis and location resolution. |
| **1c. 100% Sub-Requirement Audit** | `ResearchCoverageCriticAgent` | `gemini-2.5-pro` (`LoopAgent`, max 2) | Pipeline Stage 1 | ~`2,500` input / ~`450` output | **`~$0.008`** | Deterministic set-difference check (`verify_subrequirement_coverage()`) does the heavy lifting; LLM only repairs missing leaf IDs if needed. |
| **2. 12-Archetype Storyboard, Workbook, Lesson Plan & Parent Letter** | `SlideContentPlannerAgent` | `gemini-2.5-pro` | Pipeline Stage 2 | ~`11,400` input (`76%` cached) / ~`6,800` output | **`~$0.082`** | Heavy pedagogical reasoning (mapping all requirements to 12 archetypes + EDGE notes) uses cached pamphlet context (`75%` discount on cached input tokens). |
| **3. Theme Styling & EDGE Skill Concept Maps** | `SlideBeautifierAgent` | `gemini-2.5-flash` + Concept Map Renderer | Pipeline Stage 3 | `STANDARD`: ~`3,200` tokens (`0` AI images)<br>`BEAUTIFIED`: ~`5,500` tokens + up to `5` concept maps<br>`STUDIO`: ~`8,200` tokens + up to `15` concept maps | `STANDARD`: **`~$0.012`**<br>`BEAUTIFIED`: **`~$0.240`**<br>`STUDIO`: **`~$0.860`** | `STANDARD` generates zero AI concept maps; `BEAUTIFIED` caps concept maps at 5 requirement intro slides; `STUDIO` caps at 15 and never overwrites technical diagrams. |
| **4. `.pptx` Compilation** | `PowerPointBuilderAgent` | `gemini-2.5-flash` | Pipeline Stage 5 (after HMAC HITL check) | ~`2,100` input / ~`350` output | **`~$0.002`** | Slide rendering (`python-pptx` shapes, font fitting, speaker notes) runs in compiled Python code. |
| **5. Two-Stage Geometry & Safety Gate** | `BSABrandAndSafetyReviewAgent` | Stage 1: Deterministic Math (`0` tokens)<br>Stage 2: `gemini-2.5-pro` (`LoopAgent`, max 3) | Pipeline Stage 5 | Stage 1: **`0` tokens** (`<10ms`)<br>Stage 2: ~`4,200` input / ~`600` output | **`~$0.016`** | Stage 1 catches 100% of bounding-box overlaps, font-floor violations, and contrast issues at **`$0.00` token cost** before Stage 2 runs. |
| **6a. On-Demand Web Image Search** | `WebImageSearchAgent` | `gemini-2.5-flash` | **On-Demand Only** (when user clicks *Search Web Images* in Image Studio) | ~`1,200` input / ~`300` output | **`~$0.001`** | Never runs during initial deck generation; only engages when the counselor searches for additional slide photos. |
| **6b. On-Demand Custom AI Slide Illustration** | `NanoBananaImageAgent` | `gemini-2.5-flash-image` (`Nano Banana`) / Imagen 3 | **On-Demand Only + User Consent Required** (when user clicks *Generate* in Image Studio) | ~`2,580` image/prompt/verifier tokens per generated graphic | **`$0.080 / image`** | Never runs without first running `estimate_nano_banana_image_cost()` and verifying `user_consented=True`. Runs `verify_generated_image_matches_prompt()` and caches all generated images in SQLite (`badge_image_catalog`) for free reuse. |
| **6c. On-Demand Local File Upload** | Local Pillow Validator (`upload_custom_slide_image`) | Deterministic Python (`0` tokens) | **On-Demand Only** (Tab 4 of Image Studio) | `0` tokens | **`$0.000`** | Validates `.png`/`.jpg`/`.webp` (`<= 10 MB`), normalizes to RGB PNG (`max 1600px`), and registers as `USER_UPLOAD` in `badge_image_catalog`. |

**Key Takeaway on Token & Cost Control**:
- **Zero-Token Operations**: Loading/saving counselor profiles, uploading local image files (`USER_UPLOAD`), switching between cached badge images in the Image Studio carousel, removing a right-side graphic (`None` -> full-width text layout), restoring a slide's original graphic (`Restore Original`), changing a slide's brand palette or card theme, and running Stage 1 AABB geometry checks consume **zero LLM tokens ($0.00)**.
- **Total Pipeline Cost by Tier**:
  - **Standard Tier**: `~$0.14 USD` (~`28k` total tokens, `76%` context cache hit ratio).
  - **Beautified Tier**: `~$0.38 USD` (~`36k` total tokens + up to 5 EDGE Skill Concept Maps).
  - **Studio Tier**: `~$1.00 USD` (hard-capped at `$1.00` by `FinOpsBudgetPlugin`).

---

## 3. Slide-by-Slide Explainer of the "FDE Capstone Executive Readout" Deck (8 Core Slides + 2 Appendix / Backup Slides)

This section walks through all **8 core slides** plus the **2 Appendix / Backup slides (Slides 9 & 10)** of your **[FDE Capstone Executive Readout](https://docs.google.com/presentation/d/1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E/edit)** presentation in the exact order they appear in the deck, including every card on each slide, the underlying code and architecture, and how to answer likely capstone panel questions.

---

### Slide 1: Title & Executive Summary (`Scouts BSA Merit Badge Counselor Workbench`)

#### What is on the slide
- **Subtitle**: *A 9-Component / 7-Specialist-Agent Google ADK Curriculum Engine on Vertex AI & Cloud Run that turns 80-page official BSA pamphlets into grounded 16:9 slide decks, Scout workbooks, and lesson plans in under 2 minutes.*
- **Three KPI Cards**:
  1. **138 Official Badges -> 100% Fidelity**: SHA-256 requirement lock prevents drift across all Eagle and elective badges.
  2. **Counselor Prep Time -> < 2 Minutes**: Replaces 6 to 10 hours of manual weekend slide building per badge.
  3. **Predictable FinOps -> $0.14 - $1.00**: Hard `$1.00` budget cap with `68%` RAG token savings and `<10ms` AABB checks.

#### Technical details & jargon on Slide 1
- **Google ADK (Agent Development Kit)**: Google's open-source Python framework (`google-adk`) for building multi-agent applications on Gemini and Vertex AI. Instead of writing raw prompt loops, ADK gives you structured primitives like `LlmAgent`, `SequentialAgent`, `LoopAgent`, `FunctionTool`, session state compaction, and built-in CLI tools (`adk web`, `adk run`, `adk eval`, `adk deploy`).
- **SHA-256 Requirement Lock**: SHA-256 is a cryptographic hash function (`hashlib.sha256` in Python) that turns any text into a unique 64-character fingerprint. Before running web research, `compute_canonical_pamphlet_hash()` (`src/agents/researcher.py`) hashes the list of `(req_number, req_text)` pairs from the official BSA pamphlet. After enrichment finishes, it hashes them again and asserts `before_hash == after_hash`. If even one comma changed, the check fails.
- **FinOps**: Short for "Cloud Financial Operations". In AI engineering, FinOps means tracking token counts, image generation calls, and dollar cost per request, and enforcing hard budget ceilings (`FinOpsBudgetPlugin`) so an agent loop cannot accidentally run up a `$50` API bill.
- **AABB Checks**: Short for **Axis-Aligned Bounding Box** geometry checks. Every shape on a PowerPoint slide is a rectangle defined by `(left, top, right, bottom)`. Our Stage 1 checker tests every pair of shapes on a slide in `<10ms` to confirm no two rectangles overlap.
- **138 vs. 140 Badges Note**: Scouting America has **138 official Merit Badges**. Our UI dropdown shows 140 entries because it includes 2 clearly labeled `(Test Stub)` synthetic badges used by our automated CI fault-injection tests.

#### Likely panel question on Slide 1
- **Q**: *"Why frame the readout around a CTO, CIO, and CFO panel for Scouting America?"*
- **How to answer**: *"The FDE Capstone rubric asks us to pitch to an executive buyer panel covering architecture (CTO), security/operations (CIO), and unit economics/TCO (CFO). Scouting America's National Council oversees 138 Merit Badges taught by tens of thousands of adult volunteers, so they care about three things: curriculum accuracy and Youth Protection safety, low-maintenance Cloud Run operations, and predictable cost per generated deck."*

---

### Slide 2: Problem Statement & Customer Pain Points (`6 to 10 Hours Unpaid Prep` vs. `< 2 Min, 0% Drift`)

#### What is on the slide
- **Left Card (Status Quo: `6 to 10 Hours Unpaid Prep`)**:
  - **Weekend Bottleneck**: Turning an 80-page BSA pamphlet into clear slides and handouts takes 6 to 10 hours.
  - **Stale Internet Decks**: Hand-me-down decks online often teach outdated requirement years, causing problems at Eagle Boards of Review.
  - **Wall-of-Text Fatigue**: Copy-pasted requirement paragraphs fail to separate classroom discussion from hands-on EDGE skill stations.
- **Right Card (Counselor Workbench: `< 2 Min, 0% Drift`)**:
  - **SHA-256 Requirement Lock**: Verifies 100% verbatim fidelity to official BSA requirement numbers and text.
  - **Local Troop Grounding**: Resolves counselor City/State or ZIP code to local NOAA offices, terrain, and civic agencies.
  - **Classroom vs. Field Triage**: Automatically sorts requirements into Discussion, Hands-On Station, and Home/Campout Prerequisites.

#### Technical details & jargon on Slide 2
- **Requirement Drift**: When Scouting America updates a Merit Badge pamphlet (for example, adding a new first-aid tourniquet sub-requirement or changing a camping night requirement), older slide decks shared on troop websites become out of date. If a Scout completes outdated requirements, their Eagle Scout rank application can be delayed at the council level.
- **BSA EDGE Method**: Scouting's official 4-step teaching method required for youth and adult instruction: **E**xplain, **D**emonstrate, **G**uide, **E**nable.
- **Execution-Mode Triage**: In `src/tools/scouting_scraper.py` and `src/agents/researcher.py`, every requirement is inspected by its action verbs and sorted into one of three buckets:
  1. `IN_CLASS_DISCUSSION` (verbs like *Explain, Discuss, Describe, Tell, Identify*): Taught using the slide deck in the troop meeting room.
  2. `HANDS_ON_SKILL_STATION` (verbs like *Demonstrate, Show, Prepare, Practice*): Practiced physically at patrol tables using the EDGE method.
  3. `PREREQUISITE_CAMPOUT_HOME` (verbs like *Camp, Visit, Keep a 10-day log, Cook on a campout*): Must be done at home or on a troop campout and brought to class for sign-off.

---

### Slide 3: Functional Capabilities & Counselor StudioKit (`4 Deliverable Pillars`)

#### What is on the slide
- **Card 1: Widescreen 16:9 Slide Deck (`.pptx`)**: 12 layout archetypes, 3 visual polish tiers (`Standard`, `Beautified`, `Studio`), proactive font auto-fitting (`13.0pt` floor), and 100% layout and text parity between the live web preview and the downloaded `.pptx` file.
- **Card 2: Printable Scout Workbook & Triage (`.md`)**: Every sub-requirement (`1a..9b`) mapped to pamphlet excerpts, 3-column execution triage, and audience-level tone adaptation (`Tenderfoot 11-12` vs. `Eagle Prep 14-17`), rendered in-app as styled, scrollable Markdown cards.
- **Card 3: ZIP / City Grounded Lesson Plan & Parent Letter**: Resolves counselor location (such as `Middleton, MA 01949`) to the nearest NOAA NWS office, terrain hazards, and state agencies; generates a timed 3-meeting lesson plan and YPT-compliant Parent Prerequisite Letter, rendered in scrollable containers (`680px` height) with a clean 4-column **FinOps Cost & Token Budget** table (`Agent Stage`, `Model Assigned`, `Token Estimate`, `Cost (USD)`).
- **Card 4: Co-Design Bar & 4-Tab Image Studio**: Per-slide controls for archetype, palette, and right-side graphics (`Keep Current`, `Restore Original`, `EDGE Concept Map`, `None` full-width reflow), instant `◀` / `▶` image cycle arrows + immediate dropdown selection, and a 4-tab popup **Merit Badge Image Studio** (`1. Badge Image Catalog` + cache clear, `2. WebImageSearchAgent`, `3. NanoBananaImageAgent` with a `$0.08` FinOps consent gate, and `4. File Upload` at `$0.00`).
- **Bottom Banner**: Dual interfaces (`Material 3 Web Workbench :8085` + `Streamlit Workbench :8501` + `A2A 1.0 /.well-known/agent.json`) with automatic local/browser counselor profile caching.

#### Technical details & jargon on Slide 3
- **How `resolve_counselor_location()` works (`src/agents/researcher.py`)**:
  - When a counselor enters `01949` or `Middleton, MA` in the **Location (City, State or ZIP Code)** box (or writes `Troop 19, Middleton MA` in the troop field), `resolve_counselor_location()` checks for a 5-digit ZIP code, two-letter state code, or city/council name, and in the browser UI falls back to `Intl.DateTimeFormat().resolvedOptions().timeZone`.
  - It maps that location to a regional profile containing the local NOAA National Weather Service Forecast Office (`NOAA NWS Boston/Norton (BOX)`), local weather and terrain hazards (`Coastal Nor'easters, rapid cold-front shifts, winter hypothermia, and woodland Ixodes tick habitats`), local outdoor training sites (`Harold Parker State Forest, Blue Hills Reservation`), and state agencies (`MEMA & DCR State Parks`).
  - Rather than spamming every slide with repeated boilerplate, this regional profile is placed in four high-value places: **Slide 2 (Badge Overview)**, the **Counselor Session Lesson Plan**, the **Parent Prerequisite Letter**, and the **Grounded Citations** tab.
- **100% Preview-to-PPTX Parity & Dynamic Font Auto-Fitting**: Both the browser preview and `pptx_builder.py` render the exact same stacked cards, bold anchor titles, full sentence text, and background colors (`#FFFFFF` for `STANDARD`, `#FAF8F5` warm cream for `BEAUTIFIED`, and `#0F172A` dark slate for `STUDIO`). `_compute_fitting_font_size()` calculates line wrapping and vertical card height before rendering so dense slides (like Cooking or First Aid Slide 3) never bleed outside their boxes.
- **A2A 1.0 (`/.well-known/agent.json`) and A2UI v0.9**:
  - **A2A (Agent-to-Agent Protocol)** is Google's standard for discovering and calling agents over HTTP. Exposing `GET /.well-known/agent.json` (`src/server.py`) publishes an "Agent Card" describing what skills and input/output formats our agent supports so other agents can call `POST /a2a/tasks/send`.
  - **A2UI v0.9 (Agent-to-UI Protocol)** is a JSON message format (`beginRendering`, `surfaceUpdate`, `dataModelUpdate` in `src/schemas.py`) where the backend sends structured UI component state to the frontend instead of plain chat text.

---

### Slide 4: Google ADK Multi-Agent Architecture & Vertex AI Patterns (`5-Stage Pipeline + Image Studio`)

#### What is on the slide
- **Headline**: *9-Component / 7-Specialist-Agent Deterministic Pipeline with Isolated Search Grounding, On-Demand Image Studio & Bounded Critic Loop. Solves Vertex AI's tool-mixing constraint by isolating `GoogleSearchTool` inside an `AgentTool` sub-agent while caching pamphlet vectors and badge images.*
- **5 Pipeline Boxes**:
  1. **1. Coordinator (`SequentialAgent`)**: Compaction (every 5 turns), SQLite + Vector RAG, SSE Event Stream, HITL HMAC Gate.
  2. **2. Research & RAG (`Pamphlet + Web`)**: `PyMuPDF` extraction, SHA-256 hash lock, `AgentTool` isolates `GoogleSearchTool`.
  3. **3. Planner & Kit (`Content Planner`)**: 12 slide archetypes, 3-column execution triage, Lesson Plan & YPT Parent Letter.
  4. **4. Beautifier (`Beautifier + Studio`)**: 3 distinct tiers, FinOps budget cap (`$1.00` maximum), EDGE Skill Concept Maps + `WebImageSearchAgent`, `NanoBananaImageAgent`, & Local File Upload.
  5. **5. Builder & Critic (`LoopAgent`, Max 3x)**: 16:9 `python-pptx`, Stage 1 `<10ms` AABB check, Stage 2 Vision/Safety critic, 0 overlaps verified.

#### Technical details & jargon on Slide 4
- **Why 9 ADK components / 7 specialist agent roles across 5 stages + Image Studio?**:
  1. `MeritBadgeCoordinatorAgent` (`src/agents/coordinator.py`): Root supervisor (`gemini-2.5-flash`).
  2. `PamphletResearchAgent` (`src/agents/researcher.py`): Extracts PDF pamphlet & requirement tree (`gemini-2.5-pro`).
  3. `WebSearchGroundingAgent` / `DeepResearchEnrichmentAgent` (`src/agents/researcher.py`): Regional & web grounding (`gemini-2.5-flash`).
  4. `ResearchCoverageCriticAgent` (`src/agents/researcher.py`): Verifies 100% sub-requirement completeness (`gemini-2.5-pro`).
  5. `SlideContentPlannerAgent` (`src/agents/planner.py`): Maps requirements to 12 slide archetypes + StudioKit (`gemini-2.5-pro`).
  6. `SlideBeautifierAgent` (`src/agents/beautifier.py`): Applies `STANDARD` / `BEAUTIFIED` / `STUDIO` themes, preserves `original_diagram_path`, & synthesizes EDGE Concept Maps (`gemini-2.5-flash`).
  7. `PowerPointBuilderAgent` + `BSABrandAndSafetyReviewAgent` (`src/agents/builder.py`, `src/agents/reviewer.py`): Builds `.pptx` (`gemini-2.5-flash`) and runs 2-stage conformance review (`gemini-2.5-pro`).
  8. **Interactive On-Demand Image Studio Agents (`src/agents/image_studio.py`)**: `WebImageSearchAgent` (queries up to 12 live Wikimedia Commons educational images and caches them per badge), `NanoBananaImageAgent` (estimates `$0.08` cost, enforces explicit `user_consented=True` consent, synthesizes text-free graphics across 8 visual styles, and runs `verify_generated_image_matches_prompt()`), plus `upload_custom_slide_image()` (`$0.00` local file upload).
- **The Vertex AI Tool-Mixing Constraint (and why panelists love this detail)**:
  - In the Vertex AI Gemini API, if you attach Google's built-in `GoogleSearchTool` (search grounding) AND custom Python `FunctionTool`s (like `fetch_merit_badge_pamphlet_pdf`) to the same `LlmAgent`, Vertex AI rejects the request with `400 INVALID_ARGUMENT` unless search is isolated.
  - The official Google ADK design pattern is to put `GoogleSearchTool(bypass_multi_tools_limit=True)` on a dedicated sub-agent (`WebSearchGroundingAgent`) and wrap that sub-agent in `AgentTool(agent=web_search_agent)` (`src/agents/researcher.py`). That way, the parent `PamphletResearchAgent` calls the search sub-agent just like any other Python tool, avoiding any Vertex AI tool-collision error.
- **Session Compaction (`EventsCompactionConfig`)**:
  - We configure ADK's `EventsCompactionConfig(compaction_interval=5, overlap_size=2, compaction_strategy="additive")` (`src/memory/session_store.py`). Every 5 turns, older turns are summarized into a compact state digest while keeping the 2 most recent turns verbatim so context isn't lost.

#### Likely panel question on Slide 4
- **Q**: *"Why use a deterministic `SequentialAgent` + bounded `LoopAgent` instead of letting a single autonomous agent decide what tools to call?"*
- **How to answer**: *"We evaluated three topologies in ADR-01: a single-prompt call, an open-ended autonomous peer graph, and a fixed `SequentialAgent` with bounded `LoopAgent` critics. Every Merit Badge deck has to go through the same five compliance gates: extract the pamphlet, verify 100% sub-requirement coverage, plan the storyboard, build the `.pptx`, and verify zero shape overlaps. Using `SequentialAgent` makes the workflow order deterministic and predictable in cost, while `LoopAgent(max_iterations=3)` gives us self-healing retries on the review step without risking an infinite loop."*

---

### Slide 5: Security, Youth Protection (YPT) & Fault-Tolerant Engineering

#### What is on the slide
- **Card 1: Pre-LLM PII Scrubbing, Model Armor & Profile Isolation**: `before_model_guardrail_callback()` scrubs emails and phone numbers (`[REDACTED_EMAIL]`) before prompts leave for Gemini; contact info is cached locally (`.cache/counselor_profile.json` `0600` on laptop; browser `localStorage` on Cloud Run with server disk disabled) and injected locally onto Slide 1 during `python-pptx` build; Model Armor blocks prompt injection and enforces Two-Deep Leadership.
- **Card 2: Cryptographic HMAC-SHA256 HITL Gate**: `request_counselor_confirmation()` signs `{badge}:{slides}:APPROVED` with `BSA_HITL_SECRET_KEY` via `hmac.compare_digest`, verified in `verify_hitl_before_tool_callback()` before `.pptx` build.
- **Card 3: Circuit Breaker & Model Fallback Cascade**: Thread-safe 3-state `CircuitBreaker` (`CLOSED -> OPEN -> HALF_OPEN`) + exponential jitter retry on HTTP `429`/`503`; cascades `gemini-2.5-pro -> gemini-2.5-flash -> local deterministic curriculum engine` (`0` HTTP 500s).
- **Card 4: Zero-Trust Cloud Run & Terraform IaC**: Dedicated least-privilege Service Account (`scouts-bsa-agent-sa`), custom VPC with Private Google Access, Cloud Armor WAF (`120 RPM`), and `AUTH_REQUIRED=true` in Cloud Run enforcing OIDC Bearer JWT / `X-API-Key`.

#### Technical details & jargon on Slide 5
- **Pre-LLM PII Scrubbing & Counselor Profile Caching (`src/memory/session_store.py`, `src/agents/guardrails.py`)**:
  - A counselor enters their name, troop, location, email, and phone number once so Scouts and parents can see it on Cover Slide 1 and in the Parent Prerequisite Letter.
  - On a local laptop, `save_local_counselor_profile()` caches those fields in `.cache/counselor_profile.json` (`chmod 0600`, git-ignored). On the multi-user Cloud Run web app, server-side file caching is automatically disabled (`is_cloud_multi_user_environment()` checks `K_SERVICE`), and the profile stays strictly in the user's browser `localStorage`.
  - Inside `before_model_guardrail_callback()`, our scrubber (`scrub_pii_before_sink()`) replaces emails and phone numbers with `[REDACTED_EMAIL]` and `[REDACTED_PHONE]` *before* any prompt is sent to Vertex AI, SQLite, or Cloud Trace. Then `src/tools/pptx_builder.py` and `src/tools/counselor_studiokit.py` insert your real contact strings locally when generating the `.pptx` and `.md` files.
- **HMAC-SHA256 HITL (Human-in-the-Loop) Token (`src/tools/hitl_confirm.py`)**:
  - Why not just put `confirmed: bool = True` as a parameter on `generate_bsa_slide_deck_pptx()`? Because an LLM can easily hallucinate `confirmed=True` in its tool call JSON!
  - Instead, `request_counselor_confirmation()` computes a cryptographic HMAC-SHA256 signature using `BSA_HITL_SECRET_KEY`. Before `generate_bsa_slide_deck_pptx()` runs, `verify_hitl_before_tool_callback()` checks that signature via `hmac.compare_digest()`.

---

### Slide 6: FinOps Unit Economics, TCO & Architectural Trade-Offs

#### What is on the slide
- **Headline**: *Predictable `$0.14` to `$1.00` Unit Economics (`~$282/mo` TCO for a 500-Counselor Council). Enforced declaratively by `config/finops_model_policy.json` and `FinOpsBudgetPlugin` with automatic image-cap downgrades and a `$0.08/image` Nano Banana consent gate.*
- **Three Tier Cards**:
  - **Tier 1: Standard Fast (`$0.14 / deck`, `$0.00` on cached rerun)**: `~65k` input / `13.5k` output tokens; uses pamphlet figures + 220-DPI Matplotlib diagrams on a clean white wireframe theme.
  - **Tier 2: AI Beautified (`$0.38 / deck`, `$0.02` on cached rerun)**: Default NotebookLM warm cream canvas (`#FAF8F5`), 4 rotating accent palettes, and up to 5 EDGE Skill Concept Maps on requirement intro slides.
  - **Tier 3: AI Studio (`$1.00` Max Cap)**: Hard ceiling via `FinOpsBudgetPlugin`; dark executive slate (`#0F172A`) theme with gold/cyan accents and up to 15 dark-slate EDGE Skill Concept Maps, plus on-demand `NanoBananaImageAgent` custom graphics (`$0.08/image` with explicit user consent and post-generation prompt alignment verification).
- **Two Trade-Off Callouts**:
  - **Trade-Off 1: Hybrid Vector RAG vs. Full-PDF Stuffing**: Indexing pamphlet chunks in `PersistentSessionStore` cuts input tokens by **68%** vs. stuffing 80-page PDFs into every agent turn.
  - **Trade-Off 2: `<10ms` AABB Geometry Before Vision LLM**: Stage 1 checks `python-pptx` bounding boxes in **3.4ms** at **$0.00** token cost, catching 100% of shape overlaps before Stage 2 Vision.
- **Bottom Banner**: Council-Scale TCO (`500 counselors, 1,500 decks/mo, 70% cache hit`): `~$202` Vertex AI + `~$68` Cloud Run + `~$12` GCS = **`~$282.50/mo` (`$0.19/deck`)**.

#### Technical details & jargon on Slide 6
- **How the `$0.14 / $0.38 / $1.00` numbers are calculated (`estimate_workflow_finops_cost()` in `src/agents/guardrails.py`)**:
  - Vertex AI Gemini 2.5 pricing in `config/finops_model_policy.json` is `$1.25 / 1M` input tokens and `$5.00 / 1M` output tokens for `gemini-2.5-pro`, and `$0.15 / 1M` input tokens and `$0.60 / 1M` output tokens for `gemini-2.5-flash`.
  - In the UI (`Lesson Plan, Parent Letter & FinOps` tab), the **FinOps Cost & Token Budget** is rendered as a clean, scannable **4-column table** (`Agent Stage` | `Model Assigned` | `Token Estimate` | `Cost (USD)`) showing the per-stage breakdown, Beautification Tier, Estimated Total Cost, Maximum Budget Ceiling, Context Cache Hit Ratio (`76%`), and On-Demand AI Image Rate (`$0.0800 / image`).
- **How the `$282.50/month` Council TCO is calculated**:
  - Assume a mid-sized BSA Council with **500 active Merit Badge Counselors** generating **1,500 decks per month** across the council, with a **70% cache hit rate**:
    - Cold builds: `450 decks * $0.38 = $171.00`
    - Warm cached builds: `1,050 decks * $0.03 = $31.50`
    - Total Vertex AI spend: `$202.50/mo` + Cloud Run (`min_instances=1`, `2 vCPU / 4 GiB RAM`): `~$68.00/mo` + Cloud Storage/Secret Manager/Trace: `~$12.00/mo` = **`$282.50/mo`** (**`$0.19` per deck**).

---

### Slide 7: AI-Driven Development Harness, Multi-Metric Eval Gate & Canary CI/CD

#### What is on the slide
- **Card 1: Multi-Metric Eval Gate (`1.00 Recall@3`)**: `scripts/eval_gate.py` verifies `IR Recall@3 = 1.00`, `MRR = 1.00`, `NDCG@3 = 1.00` on pamphlet RAG, `Sub-Requirement Coverage = 100%`, `SHA-256 Canonical Lock = 100%`, and `Stage 1 AABB Overlaps = 0`.
- **Card 2: Canary CI/CD & Rollback (`10% -> 100%`)**: `cloudbuild.yaml` runs `ruff` + `47` pytest tests + blocking `eval_gate.py`, deploys `--tag=canary` at `10%` traffic, checks `/readiness`, and auto-rolls back on error.
- **Card 3: Load & HITL Feedback (`14.2ms p95`)**: Concurrent load test (`8 workers`): `p50 = 6.8ms`, `p95 = 14.2ms`; `POST /api/v1/feedback` logs counselor ratings and requirement sign-offs to JSONL.
- **Bottom Banner**: AI Development Harness combining `AGENTS.md` rules + visual PNG inspection loops (in-the-loop) with `47` `pytest` tests and `eval_gate.py` checks (outside-the-loop).

#### Technical details & jargon on Slide 7
- **The Three Information Retrieval (IR) Metrics (`Recall@3`, `MRR`, `NDCG@3`) in `scripts/eval_gate.py`**:
  1. **`Recall@3` (Recall at 3)**: Did the right pamphlet chunk appear *anywhere* in the top 3 results? (`1.0` if yes, `0.0` if no). Across all 12 golden badges, `Recall@3 = 1.00`.
  2. **`MRR` (Mean Reciprocal Rank)**: How high up did the right chunk appear? (`1/1 = 1.0` if #1, `1/2 = 0.5` if #2). `MRR = 1.00` means the exact matching requirement chunk ranked **#1** on every test query.
  3. **`NDCG@3` (Normalized Discounted Cumulative Gain at 3)**: Rewards placing relevant chunks at the top of the list using a logarithmic discount (`1 / log2(rank + 1)`). `NDCG@3 = 1.00` means ideal ranking order.
- **10% Canary Traffic Split (`cloudbuild.yaml`)**: Deploys with `--no-traffic --tag=canary`, shifts `10%` of live traffic to canary, probes `/readiness` and `/health`, and promotes to `100%` (or rolls back to `0%` on failure).

---

### Slide 8: Prototype vs. Production Honesty & 90-Day National Rollout

#### What is on the slide
- **Headline**: *Scaling from Single-Troop Container to 50,000+ National Council Counselors. Candid boundary analysis of what runs locally today vs. the 90-day architecture for national multi-tenant scale.*
- **4 Columns**:
  1. **Today (Prototype)**: Local SQLite WAL session, vector & badge image catalog store (`.bsa_session_memory.sqlite`: `sessions`, `session_events`, `pamphlet_chunks`, `badge_image_catalog`), in-process worker thread (`1.2s - 3.5s` build), local static asset mounts + API key / OIDC auth.
  2. **Days 1-30 (State & Queue)**: Migrate SQLite to **Cloud SQL for PostgreSQL + `pgvector`**, enforce **Row-Level Security (RLS)** by `council_id`, and offload 60-slide builds to **Cloud Tasks** workers.
  3. **Days 31-60 (SSO & CDN)**: Federate **Cloud IAP** with **`my.scouting.org` OIDC SSO**, verify active Youth Protection Training (YPT) certification on login, and serve decks/figures via **GCS + Cloud CDN**.
  4. **Days 61-90 (National Insights)**: Stream anonymized triage and HITL feedback to **BigQuery** and build **Looker Studio** dashboards for the National Advancement Committee.

#### Why this slide is critical for the Capstone Panel
- Senior FDE evaluators always look for **architectural self-awareness**: knowing the difference between what works great for 1 troop or 1 council (`SQLite` on a local disk or single Cloud Run container) vs. what breaks when 100 Cloud Run instances scale out horizontally for 50,000 counselors across the country.
- By proactively calling out **SQLite's single-node limitation** and showing the migration path to **Cloud SQL for PostgreSQL + `pgvector`** with Postgres Row-Level Security (`council_id`), you preempt the panel's toughest infrastructure question before they even ask it.

---

### Slide 9 (Appendix A - Backup Slide 1 / 2): Co-Design Workbench, Merit Badge Image Studio & Zero-Overflow Layout Engine

#### What is on the slide
- **Eyebrow & Badge**: `APPENDIX A (BACKUP SLIDE) • INTERACTIVE CO-DESIGN, IMAGE STUDIO & LAYOUT ENGINE` (`APPENDIX A • BACKUP 1 / 2`).
- **Headline**: *Co-Design Workbench, Merit Badge Image Studio & Zero-Overflow Layout Engine (Backup Deep-Dive: How counselors customize slide visuals in-place while guaranteeing zero text bleed or bounding-box overlaps).*
- **4 Cards**:
  1. **1. Surgical Co-Design Bar & Quick Image Switcher**: Swap any slide's layout archetype, brand palette, magazine theme, or right-side graphic (`None`, `Restore Original`, or `Custom`) in place; Quick-Switch Image Selector with `◀` `▶` arrow buttons cycles through all cached badge graphics with immediate effect and automatically rebuilds the underlying `.pptx` deck on every edit.
  2. **2. `WebImageSearchAgent` (Wikimedia Commons) & Local File Upload (`$0.00`)**: Queries live Wikimedia Commons (`search_web_images_for_slide`), returning up to `12` real public-domain photos and illustrations; also supports direct local image uploads (`POST /api/slide/upload-image`, `USER_UPLOAD`, `$0.00 USD`) and one-click Web/AI cache clearing (`DELETE /api/badge/images`).
  3. **3. `NanoBananaImageAgent` (8 Styles + `$0.08` Gate + Alignment Verifier)**: Synthesizes pure visual scene illustrations (zero prompt text printed on the image) across 8 illustration styles (`Photorealistic Image`, `Line Drawing`, `Cartoon Drawing`, `Technical Diagram`, `Editorial Field Illustration`, `Annotated Technical Cutaway`, `4-Panel Field Storyboard`, and `Comparison & Decision Visual`); enforces a mandatory FinOps consent gate (`$0.08` / `~2,580` tokens) and runs `verify_generated_image_matches_prompt()` after generation.
  4. **4. Dynamic Font Auto-Fitting (`_compute_fitting_font_size`)**: Adding a right-side hero graphic narrows the text column from `11.73 in` (full width) to `6.55 in` (split visual layout); `_compute_fitting_font_size()` runs a binary search (`13.5pt -> 9.0pt`) with a `0.86` wrapping safety margin before rendering, preventing text bleed on dense slides (such as Cooking & First Aid Slide 3).

#### When to pull up this backup slide during Q&A
- Pull up **Appendix A (Slide 9)** if a panelist asks: *"What happens if a counselor doesn't like one of the slides or graphics?"* or *"How do you keep text from overflowing when an AI hero graphic is added to a dense slide?"*

---

### Slide 10 (Appendix B - Backup Slide 2 / 2): Complete Rubric Evidence Scorecard (`95/95` AgentOps + `100/100` FDE Readiness)

#### What is on the slide
- **Eyebrow & Badge**: `APPENDIX B (BACKUP SLIDE) • 95/95 AGENTOPS MATRIX & 100/100 FDE RUBRIC SCORECARD` (`APPENDIX B • BACKUP 2 / 2`).
- **Headline**: *Complete Rubric Evidence Scorecard: 95 / 95 AgentOps + 100 / 100 FDE Readiness (Backup Reference: Direct mapping of all 19 AgentOps evaluation criteria and 6 FDE readiness dimensions to repository code).*
- **5 Category Columns (`19 Criteria = 95 / 95 Points`)**:
  1. **1. Tool & Interface (`20 / 20 Points`, 4/4 criteria)**: Rich `WHEN TO USE` docstrings, descriptive `snake_case` tools, strict Pydantic (`extra=forbid`), guided recovery error dicts, dual A2A 1.0 + A2UI v0.9 (`src/tools/*.py` & `src/server.py`).
  2. **2. Context & Memory (`20 / 20 Points`, 4/4 criteria)**: XML-tagged system prompts, `EventsCompactionConfig` (`5` turns, overlap `2`), SQLite WAL + hybrid BM25/vector RAG, async `aiosqlite` memory ops, local `.cache` (`0600`) profile (`src/memory/session_store.py`).
  3. **3. Orchestration (`20 / 20 Points`, 4/4 criteria)**: 7 ADK Specialist Sub-Agents, Flash vs. Pro FinOps routing, Model Armor & YPT guardrails, HMAC-SHA256 HITL approval, `$0.08` Image Studio consent (`src/agents/coordinator.py`).
  4. **4. Observability (`20 / 20 Points`, 4/4 criteria)**: Cloud Logging JSON schema, Intent vs. Outcome audit logs, OpenTelemetry trace spans, dual-layer PII scrubbing, 3-state `CircuitBreaker` (`src/observability/tracing.py`).
  5. **5. Infra & CI/CD (`15 / 15 Points`, 3/3 criteria)**: Blocking `eval_gate.py` (`1.00` IR), `47` `pytest` suite (`0` overlaps), Terraform Cloud Run + WAF, Secret Manager CSI mounts, Canary `10% -> 100%` rollback (`cloudbuild.yaml` & `terraform/`).

#### When to pull up this backup slide during Q&A
- Pull up **Appendix B (Slide 10)** if a panelist asks how the project maps to specific grading criteria in the **95-point AgentOps Code Review Matrix** or where to find a specific requirement in the repository.

---

## 4. Expanded Jargon Reference & Self-Contained Technical Primer

This section explains every piece of Google Cloud, AI agent, and software engineering jargon used in the readout, codebase, and panel Q&A in enough depth that you do not need to click external links unless you want extra reading.

---

### 4.1 Agent Frameworks, Protocols & Orchestration

#### **Google ADK (Agent Development Kit)**
- **What it is**: Google's open-source Python and Java framework (`google-adk`) for building production multi-agent applications on Gemini and Vertex AI.
- **How it works under the hood**: Instead of writing raw `while` loops around LLM calls, ADK provides structured agent classes:
  - **`LlmAgent`**: A single specialist agent powered by a Gemini model (`model="gemini-2.5-pro"`), a system instruction (`instruction=...`), and a list of Python functions wrapped as `FunctionTool`s.
  - **`SequentialAgent`**: Runs an ordered list of sub-agents one after another (`Research -> Plan -> Beautify -> Build -> Review`), passing shared state via `InvocationContext.session.state`.
  - **`LoopAgent`**: Repeats a sub-agent (or pair of agents) up to `max_iterations` times until an exit condition or quality check passes. We use two bounded `LoopAgent`s: one around `ResearchCoverageCriticAgent` (`max_iterations=2`) to guarantee 100% sub-requirement extraction, and one around `BSABrandAndSafetyReviewAgent` (`max_iterations=3`) to guarantee zero shape overlaps.
  - **`AgentTool`**: Wraps an entire child `LlmAgent` so a parent agent can call it just like a regular Python function tool.
- **Why we use `AgentTool` for `WebSearchGroundingAgent`**: Vertex AI's Gemini API throws a `400 INVALID_ARGUMENT` error if a single `LlmAgent` tries to register both Google's built-in `google_search` grounding tool (`GoogleSearchTool`) and custom Python `FunctionTool`s at the same time. Wrapping `WebSearchGroundingAgent` (which only has `GoogleSearchTool`) inside an `AgentTool` lets `PamphletResearchAgent` invoke web search cleanly without triggering the Vertex AI tool-mixing restriction.
- **Supplemental link**: [Google ADK Official Documentation](https://google.github.io/adk-docs/)

#### **A2A 1.0 (Agent-to-Agent Protocol)**
- **What it is**: An open interoperability standard introduced by Google Cloud that allows AI agents built by different teams or frameworks to discover each other's capabilities and delegate tasks over standard HTTP/JSON-RPC.
- **How it works in our app (`src/server.py`)**:
  1. **Discovery (`GET /.well-known/agent.json`)**: Returns an **Agent Card** JSON document describing our workbench's name, version (`2.5.0`), supported input/output MIME types (`application/json`, `application/json+a2ui`), and skills (`generate_merit_badge_curriculum`, `audit_pptx_conformance`).
  2. **Task Lifecycle (`POST /a2a/tasks/send`, `GET /a2a/tasks/{task_id}`, `POST /a2a/tasks/{task_id}/cancel`)**: Another agent (for example, a council-wide camp scheduling agent) can send a JSON task request to generate the *Camping* Merit Badge deck and poll or stream its completion status.
- **Supplemental link**: [Google A2A Protocol Specification](https://google.github.io/A2A/)

#### **A2UI v0.9 (Agent-to-User Interface Protocol)**
- **What it is**: A declarative JSON schema (`application/json+a2ui`) where an AI agent returns structured UI component trees (such as `Card`, `Grid`, `Badge`, `Metric`, `Table`, and `ActionButton`) rather than returning a wall of raw Markdown text or forcing the LLM to write brittle HTML/JavaScript.
- **How it works in our app (`src/schemas.py`, `src/tools/pptx_builder.py`)**: Every workflow run returns an `A2UIMessageEnvelope` containing a typed list of visual components (`surface_id`, `components`). Our frontends render these components into native cards and interactive controls. Because the schema is validated by Pydantic v2 before leaving the server, the UI never breaks due to malformed HTML.

#### **Nano Banana (`gemini-2.5-flash-image`) & Vertex AI Imagen 3**
- **What it is**: **"Nano Banana"** is the internal and community nickname for Google's **`gemini-2.5-flash-image`** model: a fast, multimodal Gemini 2.5 Flash variant capable of generating and editing images directly from conversational context alongside **Vertex AI Imagen 3** (`imagen-3.0-generate-002`).
- **How it works in our app (`src/agents/image_studio.py`)**: `NanoBananaImageAgent` crafts a slide-specific visual prompt combining the Merit Badge name, requirement number, slide title, key concepts, and one of 8 visual style presets (`Photorealistic Image`, `Line Drawing`, `Cartoon Drawing`, `Technical Diagram`, `Editorial Field Illustration`, `Annotated Technical Cutaway`, `4-Panel Field Storyboard`, `Comparison & Decision Visual`). Before calling the model, `estimate_nano_banana_image_cost()` calculates the `$0.08 USD` cost (~`2,580` tokens) and enforces an explicit user consent gate (`user_consented=True`), followed by `verify_generated_image_matches_prompt()` to confirm prompt alignment and ensure zero rendered prompt instructions on the image.

---

### 4.2 Context, Memory & Retrieval Terms

#### **Hybrid RAG (BM25 + Cosine Vector Similarity) & Reciprocal Rank Fusion (RRF)**
- **What it is**:
  - **RAG (Retrieval-Augmented Generation)** means fetching relevant passages from an authoritative document before asking the LLM to generate an answer, rather than relying on the LLM's memorized training data.
  - **BM25 (Best Matching 25)** is a classic keyword-ranking algorithm (used by search engines like Elasticsearch) that scores passages based on exact term frequency and inverse document frequency. It excels at finding exact strings like `"Requirement 6b"` or `"165°F"`.
  - **Cosine Vector Similarity** converts text into a list of 768 numbers (an embedding vector) representing semantic meaning and measures the angle between the query vector and each document chunk vector. It excels at matching concepts even when different words are used.
  - **Reciprocal Rank Fusion (RRF)** is a simple mathematical formula that merges the ranked list from BM25 (`r_BM25`) and the ranked list from Vector Search (`r_vec`) into a single combined score without needing complex score calibration:
    `RRF_Score(d) = 0.55 / (k + r_BM25(d)) + 0.45 / (k + r_vec(d))` (where `k = 60`)
- **Why it matters for the panel**: Pure vector search often fails on structured compliance documents because `"Requirement 2a"` and `"Requirement 2b"` have nearly identical semantic embeddings. Hybrid BM25 + Vector with RRF guarantees exact requirement matching *and* rich conceptual recall inside a single SQLite database (`pamphlet_chunks`).
- **Supplemental link**: [Google Cloud: Hybrid Search & Reciprocal Rank Fusion](https://cloud.google.com/vertex-ai/docs/vector-search/about-hybrid-search)

#### **ADK History Compaction (`EventsCompactionConfig`) & Context Caching (`ContextCacheConfig`)**
- **What it is**:
  - **History Compaction**: As a multi-agent workflow executes 15 to 25 tool calls, the conversation history grows rapidly. `EventsCompactionConfig(compaction_interval=5, overlap_size=2, compaction_strategy="additive")` tells ADK to summarize older intermediate tool outputs every 5 turns while keeping the most recent 2 turns verbatim.
  - **Context Caching**: `ContextCacheConfig(ttl_seconds=3600, min_tokens=2048)` tells Vertex AI to keep the static system prompt, the 12 slide archetype definitions, and the Merit Badge pamphlet chunks in high-speed server memory for 1 hour. Subsequent agent calls reference the cached prefix at a **75% token discount** instead of re-uploading and re-tokenizing those tokens.
- **Supplemental link**: [Vertex AI Context Caching](https://cloud.google.com/vertex-ai/generative-ai/docs/context-cache/context-cache-overview)

#### **SQLite WAL Mode (`Write-Ahead Logging`)**
- **What it is**: By default, SQLite locks the entire database file whenever a write occurs. Enabling **`PRAGMA journal_mode=WAL;`** changes SQLite so new writes are appended to a separate `-wal` file first, allowing multiple concurrent readers and async background tasks (`aiosqlite`) to read and write simultaneously without `"database is locked"` errors.
- **Supplemental link**: [SQLite Write-Ahead Logging](https://www.sqlite.org/wal.html)

---

### 4.3 Geometry, Typography & Visual Verification Terms

#### **AABB (Axis-Aligned Bounding Box) Collision Detection**
- **What it is**: Every shape on a PowerPoint slide is a rectangle defined by its top-left corner `(left, top)` and dimensions `(width, height)` in inches (`right = left + width`, `bottom = top + height`). Two rectangles overlap if and only if they overlap on both the horizontal (`X`) and vertical (`Y`) axes:
  `ΔX = min(right_A, right_B) - max(left_A, left_B) > 0` and `ΔY = min(bottom_A, bottom_B) - max(top_A, top_B) > 0`
- **How we use it (`check_pptx_conformance()` in `src/tools/pptx_builder.py`)**: Immediately after `python-pptx` builds a deck, Stage 1 iterates over every non-background shape on every slide and computes `ΔX × ΔY`. If any pair of shapes overlaps by more than `0.01 sq in` (or extends outside the `13.333" x 7.5"` widescreen canvas), Stage 1 flags the exact slide number and shape coordinates in **under 10 milliseconds at $0.00 token cost**.

#### **Proactive Line-Wrapping & Font Auto-Fitting (`_compute_fitting_font_size()`)**
- **What it is**: PowerPoint's built-in "Shrink text on overflow" property only takes effect when a human opens the file in desktop Microsoft PowerPoint and clicks into the text box; it does not protect headless server builds or web previews.
- **How we solved it**: Before writing text into any card on a slide, `_compute_fitting_font_size()` calculates how many characters fit per line at a candidate font size (`width_in * 72 / (font_pt * 0.54)`), sums the wrapped lines across all bullets (including `line_spacing = 1.18` and inter-paragraph gaps), and steps the font size down in `0.5pt` increments from `16.5pt` down to the `13.0pt` readability floor until the total text height fits inside `86%` of the box's vertical height. If a requirement still has extra prose beyond what fits at `13.0pt`, the helper cleanly caps the visible card text and moves the remaining detail into the slide's **EDGE Speaker Notes** (`full_bullet_points`) so nothing ever bleeds outside a box.

#### **WCAG 2.1 AA Contrast Ratio (`4.5:1`)**
- **What it is**: The Web Content Accessibility Guidelines formula comparing the relative luminance (`L₁`, `L₂`) of foreground text against its background fill:
  `Contrast Ratio = (L_lighter + 0.05) / (L_darker + 0.05)`
- **How we use it**: Stage 1 verifies that every slide's body text and card fill achieve at least **`4.5:1`** contrast (our palettes achieve `11.4:1` to `14.8:1`), ensuring slides are easy to read on dim camp dining-hall projectors.

---

### 4.4 Security, Governance, FinOps & Cloud Infrastructure Terms

#### **HMAC-SHA256 HITL Token (`HITLConfirmationToken`)**
- **What it is**: **HMAC (Hash-based Message Authentication Code)** combines a message payload (`"Weather:22:APPROVED"`) with a secret cryptographic key (`BSA_HITL_SECRET_KEY`) using the SHA-256 hash function.
- **Why we use it (`src/tools/hitl_confirm.py`)**: If a tool simply takes a boolean parameter like `user_approved=True`, an LLM can pass `user_approved=True` on its own without waiting for a human. By requiring an HMAC-SHA256 token verified inside ADK's `before_tool_callback` (`verify_hitl_before_tool_callback()`), `generate_bsa_slide_deck_pptx()` mathematically cannot execute unless the confirmation service signed the token.

#### **Google Cloud Model Armor & Cloud DLP (Data Loss Prevention)**
- **What it is**:
  - **Model Armor (`ScoutsBSAModelArmorPlugin`)**: A security layer that inspects incoming prompts and outgoing model responses for prompt-injection attacks (`"Ignore previous instructions..."`), jailbreaks, and policy violations (such as violating Scouts BSA's two-deep leadership / no one-on-one youth contact rule).
  - **Cloud DLP / `scrub_pii_before_sink()`**: Automatically detects and replaces Personally Identifiable Information (emails, phone numbers, Social Security Numbers) with `[REDACTED_EMAIL]`, `[REDACTED_PHONE]`, and `[REDACTED_SSN]` before data is sent to Gemini or written to SQLite/Cloud Trace.
- **Supplemental link**: [Google Cloud Model Armor Overview](https://cloud.google.com/security-command-center/docs/model-armor-overview)

#### **FinOps Budget Plugin (`FinOpsBudgetPlugin`) & Cost Consent Gate**
- **What it is**: **FinOps** (Cloud Financial Operations) is the practice of engineering cost visibility and hard budget controls directly into cloud software.
- **How it works in our app**:
  1. **Pipeline Budget Cap (`FinOpsBudgetPlugin`, `max_budget_usd = $1.00`)**: Tracks cumulative input tokens, cached tokens, output tokens, and generated concept maps across all agent turns. If a run approaches a custom budget limit, it automatically downgrades `STUDIO` tier to `BEAUTIFIED` rather than failing mid-run.
  2. **On-Demand AI Image Consent Gate (`estimate_nano_banana_image_cost()`)**: Whenever a user opens the Merit Badge Image Studio to generate a custom AI graphic via `NanoBananaImageAgent`, the app calculates the upfront cost (`$0.08 USD` per image) and blocks generation (`status="CONSENT_REQUIRED"`) until the user explicitly checks the consent box (`user_consented=True`).

#### **Circuit Breaker & 3-Tier Model Fallback (`src/resilience.py`)**
- **What it is**: A fault-tolerance pattern borrowed from electrical engineering:
  - **`CLOSED` (Normal)**: Requests go to `gemini-2.5-pro`.
  - **`OPEN` (Tripped)**: If `gemini-2.5-pro` returns 3 consecutive errors (`429 Resource Exhausted` or `503 Service Unavailable`), the breaker trips `OPEN` for `30 seconds` and immediately routes requests to `gemini-2.5-flash` (or the local deterministic curriculum engine) without waiting for timeouts.
  - **`HALF_OPEN` (Recovery Probe)**: After `30 seconds`, lets one test request through to `gemini-2.5-pro`; if it succeeds, resets to `CLOSED`.

#### **OpenTelemetry (OTel) & W3C `traceparent`**
- **What it is**: The industry-standard observability framework for distributed tracing. Every HTTP or A2A request receives a globally unique `trace_id` (`00-<trace_id>-<span_id>-01`). As `MeritBadgeCoordinatorAgent` calls sub-agents and tools, child spans (`gen_ai.agent.step`, `gen_ai.tool.call`) attach to that same `trace_id` and export to **Google Cloud Trace**, while structured JSON logs include `logging.googleapis.com/trace` so you can jump from any log line directly to its waterfall trace diagram.
- **Supplemental link**: [Google Cloud Trace & OpenTelemetry](https://cloud.google.com/trace/docs/setup/python-ot)

#### **Distroless Container (`gcr.io/distroless/python3-debian12:nonroot`) & Cloud Run Gen2**
- **What it is**:
  - **Distroless**: A Docker base image maintained by Google that contains *only* Python 3 and our compiled packages: no `bash` shell, no `apt` package manager, and running as an unprivileged user (`uid=65532`). If an attacker ever found a vulnerability, they could not spawn a shell or install malware inside the container.
  - **Cloud Run Gen2**: Google Cloud's serverless container platform with a full Linux execution environment, fast CPU startup boost, and native support for mounting **Cloud Filestore (NFS)** volumes (`/mnt/filestore`) so generated `.pptx` decks, `.md` workbooks, and cached badge images persist across container scaling events.
