# Scouts BSA Merit Badge Counselor Workbench (`scouts-bsa-merit-badge-agent`)

[![Google ADK](https://img.shields.io/badge/Google%20ADK-v1.17.0%2B-003F87?style=for-the-badge&logo=googlecloud)](https://google.github.io/adk-docs/)
[![Merit Badge Catalog](https://img.shields.io/badge/Scouts%20BSA%20Catalog-All%20138%20Merit%20Badges-4B5320?style=for-the-badge)](https://www.scouting.org/skills/merit-badges/)
[![Deliverables](https://img.shields.io/badge/Outputs-.PPTX%20Slide%20Deck%20%2B%20.MD%20Workbook-CE1126?style=for-the-badge)](https://www.scouting.org/merit-badges/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-005AE0?style=for-the-badge&logo=python)](https://www.python.org/)

Volunteer Scouts BSA Merit Badge Counselors often spend 8 to 15 hours building slide decks, Scout workbooks, lesson plans, and parent letters for a single badge. This project uses the **Google Agent Development Kit (ADK) for Python** to generate widescreen (`16:9`) PowerPoint (`.pptx`) presentations, printable Scout workbooks (`.md`), session agendas, and Youth Protection (YPT) parent letters for all 138 official Scouts BSA Merit Badges.

Every slide deck is grounded in the official **BSA Merit Badge Pamphlet** and **Scouting.org Digital Resource Guide**. The pipeline keeps official requirement wording intact, breaks multi-part requirements into readable teaching slides, embeds official badge patch emblems and pamphlet figures, generates 220-DPI technical diagrams and EDGE Skill Concept Maps, checks every slide for shape overlaps before saving, and writes structured counselor speaker notes.

---

## Table of contents

1. [Key Capabilities & Features](#1-key-capabilities--features)
2. [Quick Start: Local / Laptop Execution & ADK CLI](#2-quick-start-local--laptop-execution--adk-cli)
3. [How to Use the Counselor Workbench](#3-how-to-use-the-counselor-workbench)
4. [System architecture and agent pipeline](#4-system-architecture-and-agent-pipeline)
5. [Project structure](#5-project-structure)
6. [Configuration and local asset caching](#6-configuration-and-local-asset-caching)
7. [Optional Cloud Deployment (Terraform, Cloud Build, and ADK CLI)](#7-optional-cloud-deployment-terraform-cloud-build-and-adk-cli)
8. [Testing and evaluation gate](#8-testing-and-evaluation-gate)
9. [Troubleshooting and FAQ](#9-troubleshooting-and-faq)

---

## 1. Key Capabilities & Features

- **Full 138-badge catalog**:
  - Covers all 18 Eagle-Required and 120 Elective Merit Badges across all 7 Scouting categories: *Outdoor & Campcraft*, *Health & Public Safety*, *Citizenship & Personal Development*, *Nature & Environment*, *STEM & Science*, *Aquatics & Sports*, and *Trades, Business & Careers* / *Arts, Crafts & Hobbies*.
  - Filter by keyword, category, or Eagle-Required vs. Elective status, or use the quick-select buttons for common troop badges (*First Aid*, *Weather*, *Camping*, *Citizenship in the Nation*, *Cooking*, *Emergency Preparedness*, *Environmental Science*, *Robotics*).

- **Official BSA Pamphlet grounding and location-aware local context**:
  - Downloads, caches, and parses requirements, definitions, procedures, worked examples, and figures from official BSA Merit Badge Pamphlet PDFs. A SHA-256 hash (`compute_canonical_pamphlet_hash()`) verifies that official requirement wording is never modified during web enrichment.
  - Resolves your **Location (City, State or ZIP Code)** (`location_or_zip`), or infers it from your Troop and Council affiliation or browser timezone via `resolve_counselor_location()`. It applies your local NOAA National Weather Service forecast office, regional terrain hazards, state parks, and state agencies to the Badge Overview slide (Slide 2), the Counselor Session Lesson Plan, the Parent Prerequisite Letter, and the Grounded Citations tab without repeating boilerplate across every slide.
  - Provides direct links in the UI top bar to open the **Official BSA Pamphlet (PDF)** and **Scouting.org Digital Resource Guide** for the active badge.

- **Two deck depth modes and three visual polish tiers**:
  - **Depth modes**:
    - **Deep Dive Teaching Deck (50 to 70+ slides)**: Multi-slide teaching sequences for each requirement, including a Requirement Intro slide, concept explainers, 2-column comparisons, worked examples, diagrams, and Socratic review questions. Built for Merit Badge Universities, summer camp classes, or multi-week troop instruction.
    - **Standard Troop Meeting Deck (16 to 28 slides)**: Concise 1 to 3 slide sequences per requirement for a single troop meeting or patrol breakout.
  - **Slide visual polish modes (`SlideBeautifierAgent` + `FinOpsBudgetPlugin`, \$1.00 max budget cap)**:
    - **Standard Fast Deck (`STANDARD`, ~\$0.14 / deck)**: Clean white background (`#FFFFFF`) with navy headers, structured requirement cards, and extracted pamphlet figures + 220-DPI technical diagrams (`0` generated concept maps).
    - **AI Beautified, NotebookLM Style (`BEAUTIFIED`, ~\$0.38 / deck, Default)**: Warm editorial cream canvas (`#FAF8F5`), rotating accent palettes (`NAVY_GOLD`, `OLIVE_FOREST`, `EAGLE_CRIMSON`, `SLATE_ACTION`), and up to 5 **Scouts BSA EDGE Skill Concept Maps** (`1. EXPLAIN`, `2. DEMONSTRATE`, `3. GUIDE`, `4. ENABLE`, centered on a circular medallion of the official Merit Badge patch) on Requirement Intro slides.
    - **AI Studio Executive Theme (`STUDIO`, \$1.00 budget)**: Dark executive slate canvas (`#0F172A`), dark slate cards (`#1E293B`), gold and cyan headers, and up to 15 dark-slate EDGE Skill Concept Maps across intro and text-only slides, capped at \$1.00 by `FinOpsBudgetPlugin`.
  - **Never overwrites technical diagrams**: Existing BSA Pamphlet figures and custom technical diagrams (such as weather fronts, CPR steps, or the 200-foot bear-bag triangle) are always preserved across all three polish tiers.

- **Merit Badge Image Catalog, `WebImageSearchAgent`, `NanoBananaImageAgent`, and Local File Upload**:
  - **Per-Slide Right-Side Graphic Controls**: Set any slide's graphic to **Keep Current Slide Graphic**, **Restore Original Slide Graphic** (restoring the slide's initial pamphlet/topic figure), **EDGE Skill Concept Map (Badge Emblem)**, or **None (Remove Graphic & Expand Text to Full Width)** (which removes the image and expands the text cards across the full 16:9 canvas).
  - **Quick Switch Slide Image & 4-Tab Popup Image Studio**: Cached images for each Merit Badge are stored in `assets/badge_image_catalog/<badge_slug>/` and indexed in SQLite with a preview image and brief description. When multiple images are available for a slide, you can switch between them immediately from the inline dropdown or step through them with the **◀ Prev** and **Next ▶** buttons. Clicking **🖼️ Manage & Add Slide Images (Popup)** opens a 4-tab modal:
    1. **📚 1. Badge Image Catalog**: Browse all available images for the active Merit Badge, apply any image in one click, or click **🗑️ Clear Web/AI Cache** (`DELETE /api/badge/images`) to purge web-searched and AI-generated images while preserving official BSA pamphlet figures (`PAMPHLET`) and local file uploads (`USER_UPLOAD`).
    2. **🌐 2. Web Image Search Agent (`gemini-2.5-flash`)**: Queries the live Wikimedia Commons API for up to 12 public-domain photographs and diagrams matching your topic, caches selected results per badge, and applies them to the current slide.
    3. **🍌 3. Nano Banana Image Studio (`gemini-2.5-flash-image` & Vertex AI Imagen 3)**: Synthesizes custom, text-free illustrations across 8 visual styles (*Photorealistic Image*, *Line Drawing*, *Cartoon Drawing*, *Technical Diagram*, *Editorial Field Illustration*, *Annotated Technical Cutaway*, *4-Panel Field Storyboard*, and *Comparison & Decision Visual*). Before generating any AI image, the workbench estimates the cost (`$0.08 USD` / image, covering up to 2 generation + verification passes) and requires your explicit consent (`user_consented=True`), then runs `verify_generated_image_matches_prompt()` to confirm prompt alignment and ensure zero rendered prompt text.
    4. **📁 4. File Upload (`POST /api/slide/upload-image`, `$0.00 USD`)**: Upload a local `.png`, `.jpg`, `.jpeg`, or `.webp` photo or diagram from your computer (`<= 10 MB`), validate and normalize it with Pillow (`RGB`, max `1600px`), register it in the badge catalog as `USER_UPLOAD`, and apply it directly to the active slide.

- **Persistent Counselor Profile Caching & PII Protection (Local vs. Cloud)**:
  - **Local / Laptop runs**: Your Counselor Name, Troop/Council, Location/ZIP, Email, Phone, and Custom Troop Logo path are cached locally in `.cache/counselor_profile.json` (`0600` owner-only file permissions, git-ignored) so you only need to enter them once.
  - **Web / Cloud Run deployments**: In multi-tenant cloud mode (`K_SERVICE`), server-side disk caching of counselor PII is disabled; instead, your profile is cached in your own browser's `localStorage` (`scouts_bsa_counselor_profile_v1`).
  - **Strict PII boundary**: Counselor contact PII (email, phone, name) is injected directly into the local Slide 1 Cover and Parent Letter templates and is scrubbed via `ScoutsBSAModelArmorPlugin` and `scrub_pii_before_sink()` before any LLM prompt, SQLite telemetry record, OpenTelemetry span, or Cloud Logging sink.

- **Audience level selector and per-slide co-design bar**:
  - Tailor speaker notes and coaching prompts to **All Scouts (Ages 11-17)**, **First-Year / Tenderfoot Focus (Ages 11-12)**, or **Older Scouts / Eagle Prep (Ages 14-17)**.
  - Use the **Per-Slide Interactive Co-Design Bar** under any slide to change its Layout Archetype, Card Theme, Brand Palette, or Right-Side Graphic in place.

- **1:1 parity between live web preview and downloaded `.pptx`**:
  - Both the web preview (`ui/app.js` and `src/app.py`) and the PowerPoint builder (`src/tools/pptx_builder.py`) render the exact same text, card grid structure, and visual theme (`STANDARD`, `BEAUTIFIED`, or `STUDIO`). Output filenames include the polish tier (`<Badge>_<Tier>_<Depth>_Merit_Badge_Deck.pptx`) so switching tiers never serves a stale cached file.

- **Styled Markdown Workbooks, Lesson Plans, Parent Letters, and FinOps Cost Table**:
  - Every slide includes presenter notes formatted with `[SAY]`, `[DEMONSTRATE]`, and `[ASK SCOUTS]` cues.
  - The **Scout & Counselor Workbook**, **Counselor Session Lesson Plan & Agenda**, and **YPT-Compliant Parent Prerequisite & Welcome Letter** render in the UI as clean, word-wrapped styled Markdown cards while downloading as raw `.md` files, and the **FinOps Cost & Token Budget** renders as a structured metrics table.

- **Two web interfaces**:
  - **Material 3 Web Workbench** (`http://localhost:8085`), served by FastAPI (`src/server.py` + `ui/`).
  - **Streamlit Counselor Workbench** (`http://localhost:8501`), a Python-native Streamlit interface (`src/app.py`) with the same two-column layout, 16:9 slide preview, filmstrip navigation, Image Studio dialog, requirement triage matrix, and StudioKit tabs.

---

## 2. Quick Start: Local / Laptop Execution & ADK CLI

### Prerequisites

- **Python 3.10+**
- `pip` (or `uv`)
- *(Optional)* A Google Gemini API key (`GEMINI_API_KEY` or `GOOGLE_API_KEY`) for live LLM calls. All 138 badges also run offline out of the box using the local pamphlet extractor and deterministic curriculum engine.

### Installation

```bash
# 1. Clone the repository and enter the project directory
git clone https://github.com/clayberg/scouts-bsa-merit-badge-agent.git
cd scouts-bsa-merit-badge-agent

# 2. Create a virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 3. Configure environment variables
cp .env.example .env
# Optionally edit .env to add GEMINI_API_KEY="your-api-key"
```

### Launching the web interfaces

The [`run_local.sh`](run_local.sh) script starts both interfaces together or either interface on its own:

#### Option 1: Launch both interfaces (recommended)

```bash
./run_local.sh
```

This starts:
- **Material 3 Web Workbench**: `http://localhost:8085`
- **Streamlit Counselor Workbench**: `http://localhost:8501`

#### Option 2: Run the Material 3 Web Workbench only (`:8085`)

```bash
./run_local.sh a2ui
# Or directly with uvicorn:
uvicorn src.server:app --host 0.0.0.0 --port 8085
```

#### Option 3: Run the Streamlit Counselor Workbench only (`:8501`)

```bash
./run_local.sh streamlit
# Or directly with streamlit:
streamlit run src/app.py --server.address 0.0.0.0 --server.port 8501
```

### Google ADK CLI and Python usage

`src/__init__.py` and `src/agents/__init__.py` export `root_agent` and `adk_app` for the Google ADK CLI:

```bash
# Launch the Google ADK Developer Web UI
adk web src

# Run MeritBadgeCoordinatorAgent interactively in the terminal
adk run src.agents

# Run ADK evaluation against the golden dataset
adk eval src.agents tests/data/golden_badges.json

# Deploy to Cloud Run via ADK CLI
adk deploy cloud_run --project="${GOOGLE_CLOUD_PROJECT}" --region="us-central1" src.agents
```

You can also call the workflow directly from Python:

```python
from src.agents.coordinator import run_merit_badge_workflow

result = run_merit_badge_workflow(
    badge_name="Weather",
    depth_mode="Deep Dive / Camp School Deck",  # or "Standard Deck"
    beautification_tier="BEAUTIFIED",           # "STANDARD", "BEAUTIFIED", or "STUDIO"
    enable_deep_research=True,
    audience_level="All Scouts (Ages 11–17)",
    counselor_info={
        "counselor_name": "Eric Clayberg",
        "troop_affiliation": "Troop 19, Middleton MA",
        "location_or_zip": "01949",
        "email_address": "counselor@troop19.org",
        "phone_number": "(978) 555-0119",
        "custom_troop_logo_path": None,  # Optional path to a .png or .jpg logo
    },
)

print(f"Generated {result['slide_count']} slides: {result['output_path']}")
print(f"Generated Scout Workbook: {result['workbook_path']}")
print(f"FinOps Cost Estimate: ${result['finops_cost_estimate']['estimated_cost_usd']:.2f}")
```

---

## 3. How to Use the Counselor Workbench

Both the Material 3 Web Workbench (`:8085`) and the Streamlit Workbench (`:8501`) use a two-column layout: a **Left Control Rail** for selecting badges and configuring the deck, and a **Right Main Stage** for previewing slides, reviewing requirements, and downloading files.

### Left sidebar controls

1. **Find & Select Merit Badge**:
   - **Search Merit Badge Name**: Filter the 138-badge catalog by keyword (`Weather`, `First Aid`, `Kayaking`, `Robotics`).
   - **Category and Eagle Status filters**: Filter by Scouting category or narrow to **Eagle-Required** vs. **Elective** badges.
   - **Select Merit Badge dropdown and quick-select pills**: Pick any badge from the dropdown or click one of the 8 popular badge buttons to load or generate its deck.

2. **Deck Style & Counselor Info**:
   - **Slide Deck Length & Depth**: Choose **Deep Dive Teaching Deck (50 to 70+ slides)** or **Standard Troop Meeting Deck (1 to 3 slides / req)**.
   - **Slide Visual Polish Mode**: Choose **Standard Fast Deck (~\$0.14)**, **AI Beautified, NotebookLM Style (~\$0.38)**, or **AI Studio Executive Theme (\$1.00 budget)**.
   - **Target Scout Audience Level**: Choose **All Scouts (Ages 11-17)**, **First-Year / Tenderfoot Focus (Ages 11-12)**, or **Older Scouts / Eagle Prep (Ages 14-17)**.
   - **Enable Deep Web & Local Troop Grounding**: Attaches regional `.gov`/`.edu`/`.org` references (NOAA NWS, USGS, NPS, American Red Cross, state agencies) grounded to your location.
   - **Counselor Contact & Location Fields (Locally & Browser Cached)**:
     - **Counselor Name** (default: `Scoutmaster Bob`)
     - **Troop & Council Affiliation** (default: `Troop 123, My Council`)
     - **Location (City, State or ZIP Code)** (for example, `01949` or `Middleton, MA`; if left blank, inferred from your Troop/Council text or browser timezone)
     - **Contact Email (Optional)** and **Contact Phone (Optional)**
     - *Caching*: Locally, your entries are saved automatically to `.cache/counselor_profile.json` (`0600` owner-only permissions) so you only enter them once. In Cloud Run, they are saved in your browser's `localStorage` (`scouts_bsa_counselor_profile_v1`). A **Reset Saved Info** button lets you clear cached details at any time.
   - **Optional Troop Custom Logo (`.png` / `.jpg`)**: Uploads a troop crest or council patch and places it in the lower-left counselor block on Slide 1.
   - **Generate Slide Deck & Workbook**: Rebuilds the `.pptx` presentation, `.md` workbook, lesson plan, and parent letter with your current inputs.

### Right main stage tabs

- **Top bar**: Links to the **Official BSA Pamphlet (PDF)** and **Scouting.org Resource Guide**, plus download buttons for the **Workbook (`.MD`)** and **Slide Deck (`.PPTX`)**.
- **Tab 1: Slide Deck Preview**:
  - **Slide filmstrip**: Navigate all slides in the deck, with tags showing the slide number, requirement number, and archetype.
  - **16:9 widescreen slide stage**: Renders the selected slide matching the `.pptx` output across `Standard`, `Beautified`, and `Studio` modes.
  - **Per-Slide Interactive Co-Design Bar**: Change a single slide's **Layout Archetype**, **Card Theme**, **Brand Palette**, or **Right-Side Graphic** (`Keep Current Slide Graphic`, `Restore Original Slide Graphic`, `EDGE Skill Concept Map`, or `None (Remove Graphic & Expand Text to Full Width)`).
  - **Quick Switch Slide Image & 4-Tab Popup Image Studio Modal**: Switch between cached images for the badge immediately from the inline dropdown or step through them with **◀ Prev** and **Next ▶**. Click **🖼️ Manage & Add Slide Images (Popup)** to browse all badge images (with a **🗑️ Clear Web/AI Cache** button), search up to 12 live Wikimedia Commons photos via `WebImageSearchAgent`, generate custom graphics via `NanoBananaImageAgent` across 8 visual styles (with `$0.08 USD` cost estimate, explicit user consent, and automatic prompt alignment verification), or upload a local image file (`📁 4. File Upload`, `$0.00 USD`).
  - **Counselor Teaching Notes**: Displays `[SAY]`, `[DEMONSTRATE]`, and `[ASK SCOUTS]` notes below the slide.
- **Tab 2: Official Requirements & Resource Guides**:
  - **3-Column Requirement Triage Matrix**: Sorts every requirement into **Discussion & Core Knowledge**, **Hands-On Skill Demonstrations**, and **Campout, Field & Home Projects**.
- **Tab 3: Scout & Counselor Workbook**:
  - Preview the printable workbook rendered as styled, word-wrapped Markdown cards (containing verbatim requirements, note sections, skill sign-off tables, and prerequisite checklists) and download the raw `.md` file.
- **Tab 4: Lesson Plan, Parent Letter & FinOps**:
  - **Counselor Session Agenda & Lesson Plan**: Scrollable, styled Markdown pacing guide (`3 Troop Meetings` or `Half-Day Merit Badge Clinic`) tailored to your resolved local area, with a raw `.md` download button.
  - **Prerequisite & Parent Welcome Letter**: Scrollable, styled Markdown YPT-compliant parent and Scoutmaster letter populated with your Counselor Name, Troop, Location, Email, and Phone, with a raw `.md` download button.
  - **Grounded Citations & FinOps Cost Table**: Lists regional `.gov`/`.edu`/`.org` citations, the SHA-256 requirement hash status, and a 4-column **FinOps Cost & Token Budget** table (`Agent Stage`, `Model Assigned`, `Token Estimate`, `Cost (USD)`).

---

## 4. System architecture and agent pipeline

```mermaid
flowchart LR
    UIs["Counselor Workbenches<br/>(Web :8085 & Streamlit :8501)"] --> Coord["MeritBadgeCoordinatorAgent<br/>(ADK Supervisor & Guardrails)"]
    Coord --> Res["1. PamphletResearchAgent<br/>& DeepResearchEnrichmentAgent"]
    Res --> Plan["2. SlideContentPlannerAgent<br/>(12-Archetype Storyboard & StudioKit)"]
    Plan --> Beau["3. SlideBeautifierAgent<br/>(3-Tier Polish & EDGE Concept Maps)"]
    Beau --> ImgStudio["4. WebImageSearchAgent, NanoBananaImageAgent<br/>($0.08 Consent Gate) & File Upload"]
    ImgStudio --> Build["5. PowerPointBuilderAgent<br/>(220 DPI Diagrams & 16:9 .PPTX)"]
    Build --> Rev["6. BSABrandAndSafetyReviewAgent<br/>(AABB Geometry & Safety Critic)"]
    Rev -.->|"Self-Healing Retry"| Build
    Rev --> Out["Deliverables<br/>(.PPTX Deck, .MD Workbook, Lesson Plan & Parent Letter)"]
```

### Agent roles and main helper functions (9 Components / 7 Specialist Agents)

| Layer / Agent | Assigned model | Key functions | Responsibility |
| :--- | :--- | :--- | :--- |
| **`MeritBadgeCoordinatorAgent`** (`src/agents/coordinator.py`) | `gemini-2.5-flash` | `run_merit_badge_workflow()`, `stream_merit_badge_workflow_events()`, `build_a2ui_v09_messages()`, `get_merit_badge_adk_app()` | Orchestrates the 7 specialist sub-agents, OpenTelemetry spans, SSE streaming, session compaction, FinOps budget checks, and A2UI v0.9 JSON payloads |
| **`PamphletResearchAgent` + `DeepResearchEnrichmentAgent` + `ResearchCoverageCriticAgent`** (`src/agents/researcher.py`) | `gemini-2.5-pro` (`researcher`) / `gemini-2.5-flash` (`deep_research`) | `fetch_merit_badge_pamphlet_pdf()`, `enrich_requirements_with_deep_research()`, `resolve_counselor_location()`, `compute_canonical_pamphlet_hash()`, `score_and_select_best_visual_asset()`, `generate_counselor_workbook_markdown()` | Extracts official Scouting.org requirements and BSA Pamphlet PDFs with SHA-256 hash verification, resolves `location_or_zip` to regional `.gov`/`.edu`/`.org` agencies, selects visuals, and writes the `.md` workbook |
| **`SlideContentPlannerAgent`** (`src/agents/planner.py`, `src/tools/counselor_studiokit.py`) | `gemini-2.5-pro` | `generate_slide_storyboard()`, `_build_slide_teaching_notes()`, `generate_counselor_session_agenda()`, `generate_prerequisite_parent_letter()` | Plans the 12-archetype slide storyboard (`Standard` 18-26 slides; `Deep Dive` 50-70+ slides), writes `[SAY]`/`[DEMONSTRATE]`/`[ASK SCOUTS]` notes, and generates the Session Agenda and YPT Parent Letter |
| **`FastMCPConfirmationGate`** (`src/tools/hitl_confirm.py`) | `HMAC-SHA256` | `request_counselor_confirmation()`, `generate_hitl_confirmation_token()`, `verify_hitl_confirmation_token()`, `verify_hitl_before_tool_callback()` | Signs and verifies Human-in-the-Loop confirmation tokens bound to `badge_name` and `slide_count` before `.pptx` compilation |
| **`SlideBeautifierAgent`** (`src/agents/beautifier.py`) | `gemini-2.5-flash` | `beautify_slide_storyboard()`, `generate_ai_editorial_illustration()`, `get_slide_beautifier_agent()` | Applies the 3 visual polish tiers (`STANDARD` white wireframe, `BEAUTIFIED` warm cream `#FAF8F5`, `STUDIO` dark slate `#0F172A`), preserves original pamphlet figures, and generates 220-DPI Scouts BSA EDGE Skill Concept Maps |
| **`WebImageSearchAgent`** (`src/agents/image_studio.py`) | `gemini-2.5-flash` | `get_web_image_search_agent()`, `search_web_images_for_slide()`, `get_badge_image_catalog()`, `clear_generated_and_cached_badge_images()`, `upload_custom_slide_image()` | Searches live Wikimedia Commons for up to 12 slide-specific images, manages local file uploads (`USER_UPLOAD`), clears stale Web/AI cache entries, and indexes assets per badge in `assets/badge_image_catalog/<badge_slug>/` and SQLite |
| **`NanoBananaImageAgent`** (`src/agents/image_studio.py`) | `gemini-2.5-flash-image` / `imagen-3.0-generate-002` | `get_nano_banana_image_agent()`, `estimate_nano_banana_image_cost()`, `generate_nano_banana_slide_image()`, `verify_generated_image_matches_prompt()` | Estimates FinOps cost (`$0.08 USD`/image), requires explicit user consent (`user_consented=True`), synthesizes text-free graphics across 8 visual styles, and verifies prompt alignment |
| **`PowerPointBuilderAgent`** (`src/agents/builder.py`, `src/tools/pptx_builder.py`) | `gemini-2.5-flash` | `generate_bsa_slide_deck_pptx()`, `get_badge_cover_and_patch_paths()`, `_compute_fitting_font_size()`, `_set_paragraph_runs()`, `generate_slide_visual_asset()` | Generates 220-DPI diagrams and builds the `16:9` widescreen (`13.333"` x `7.500"`) `.pptx` file matching the live web preview |
| **`BSABrandAndSafetyReviewAgent`** (`src/agents/reviewer.py`) | `gemini-2.5-pro` | `validate_presentation_deck()`, `check_pptx_conformance()`, `run_stage2_vision_critique()`, `lint_speaker_notes_voice()` | Runs the Stage 1 (`<10ms`) in-memory AABB overlap, font floor (`>= 13.0pt`), WCAG contrast (`>= 4.5:1`), and image uniqueness check, followed by Stage 2 curriculum and safety review |
| **`ScoutsBSAModelArmorPlugin` + `FinOpsBudgetPlugin`** (`src/agents/guardrails.py`) | Policy + Cloud Model Armor | `sanitize_text_with_model_armor()`, `estimate_workflow_finops_cost()`, `before_model_guardrail_callback()`, `after_model_guardrail_callback()` | Enforces `config/model_armor_security_policy.json` (prompt injection and Youth Protection checks), pre-LLM PII scrubbing, and `config/finops_model_policy.json` budget caps |

### Slide layout and typography rules

| Element | Specification |
| :--- | :--- |
| **Canvas and polish tiers** | Widescreen `16:9` (`13.333"` x `7.500"`), rendered in `STANDARD` (`#FFFFFF` white wireframe), `BEAUTIFIED` (`#FAF8F5` warm cream with pastel accent cards), or `STUDIO` (`#0F172A` dark slate with `#1E293B` cards and gold/cyan accents) |
| **Cover slide (Slide 1)** | Standalone Merit Badge patch emblem (upper left), Badge Title + Eagle/Elective status (center), Official Pamphlet cover art (right), Counselor Name / Troop / Location / Email / Phone + optional custom troop logo (lower left) |
| **Slide titles** | Single-line `24pt` bold header |
| **Requirement intro vs. teaching slides** | Verbatim requirement text appears once in a top banner on the first slide of a requirement sequence; follow-on teaching and diagram slides omit the banner to leave more room for cards and diagrams |
| **Body text and font fitting** | Left-aligned cards (`PP_ALIGN.LEFT`), explicit word wrapping (`word_wrap = True`), and dynamic font sizing (`13.5pt` to `20.0pt`) calculated by `_compute_fitting_font_size()` |
| **Right-side graphic & full-width expansion** | Setting a slide's graphic to `None` removes the right-hand image and expands the text cards across the full `12.133"` width (`CONCEPT_TEXT_SLIDE`). Adding or restoring an image switches the slide back to a balanced split layout (`SPLIT_VISUAL_EXPLAINER`) |
| **Attribution** | Single **Sources & References** slide at the end of the deck |

---

## 5. Project structure

```text
scouts-bsa-merit-badge-agent/
├── .github/workflows/
│   └── ci_eval.yml             # Lint, pytest, fault-injection, and eval_gate.py CI workflow
├── assets/
│   ├── ai_illustrations/       # Generated 220-DPI Scouts BSA EDGE Skill Concept Maps (PNG)
│   ├── badge_emblems/          # Cached standalone Merit Badge patch emblems from BSA Scout Shop (PNG)
│   ├── badge_image_catalog/    # Per-badge cached image catalogs (JSON + Web Search, Nano Banana & Upload PNGs)
│   ├── diagrams/               # Generated 220-DPI matplotlib and SVG technical diagrams
│   ├── pamphlet_covers/        # Extracted official BSA Merit Badge Pamphlet covers (PNG)
│   ├── pamphlet_images/        # Extracted figures from official BSA Pamphlet PDFs
│   ├── pamphlets/              # Cached official BSA Merit Badge Pamphlet PDFs
│   └── web_images/             # Cached Wikimedia Commons instructional illustrations
├── config/
│   ├── finops_model_policy.json         # Flash vs. Pro model routing and $1.00 FinOps budget policy
│   ├── geap_agent_registry.json         # Agent registry metadata
│   └── model_armor_security_policy.json # Youth Protection and Model Armor security policy
├── deliverables/               # Generated .pptx slide decks, .md workbooks, and evaluation reports
├── docs/
│   ├── API_INTEGRATION_GUIDE.md          # REST (/api/v1/*), SSE, and A2A 1.0 integration guide
│   ├── CAPSTONE_PANEL_PLAYBOOK.md        # 10-slide presentation guide, talk tracks, and Q&A defense matrix
│   ├── FDE_CAPSTONE_COMPANION_GUIDE.md   # Slide-by-slide explainer, jargon decoder, and architecture primer
│   ├── TDD.md                            # Technical Design Document (architecture, data contracts, & ADRs)
│   ├── finops-billing-and-deployment-guide.md # FinOps token billing, local vs. Cloud Run costs, and error handling
│   ├── openapi.yaml                      # Exported OpenAPI 3.1 contract for FastAPI and A2A routes
│   ├── runbook.md                        # Operational runbook, triage playbooks, and rollback commands
│   └── adr/README.md                     # Summary index of the 7 Architecture Decision Records
├── prompts/
│   ├── manifest.json           # Versioned prompt manifest with SHA-256 hashes
│   ├── coordinator.md          # System instructions for MeritBadgeCoordinatorAgent
│   ├── researcher.md           # System instructions for PamphletResearchAgent
│   ├── planner.md              # System instructions for SlideContentPlannerAgent
│   ├── beautifier.md           # System instructions for SlideBeautifierAgent
│   ├── builder.md              # System instructions for PowerPointBuilderAgent
│   └── reviewer.md             # System instructions for BSABrandAndSafetyReviewAgent
├── scripts/
│   ├── eval_gate.py               # Multi-metric pre-deployment evaluation gate (12 golden badges)
│   ├── export_openapi.py          # Exports live FastAPI OpenAPI 3.1 schema to docs/openapi.yaml
│   └── fetch_scoutshop_emblems.py # Fetches and caches standalone Merit Badge patch emblems
├── src/
│   ├── agents/
│   │   ├── __init__.py         # Exports root_agent and adk_app for Google ADK CLI
│   │   ├── coordinator.py      # Root supervisor, SequentialAgent, ADK App, SSE, and A2UI v0.9 builder
│   │   ├── researcher.py       # 5-tier PamphletResearchAgent, DeepResearchEnrichmentAgent, and Critic
│   │   ├── planner.py          # 12-archetype SlideContentPlannerAgent and teaching notes generator
│   │   ├── beautifier.py       # 3-tier SlideBeautifierAgent and EDGE Skill Concept Map builder
│   │   ├── image_studio.py     # WebImageSearchAgent, NanoBananaImageAgent ($0.08 consent gate), & File Upload
│   │   ├── builder.py          # PowerPointBuilderAgent with HITL FunctionTool and callbacks
│   │   ├── reviewer.py         # BSABrandAndSafetyReviewAgent (LoopAgent) and Conformance Simulator
│   │   └── guardrails.py       # ScoutsBSAModelArmorPlugin, FinOpsBudgetPlugin, and PII callbacks
│   ├── memory/
│   │   └── session_store.py    # PersistentSessionStore (SQLite WAL + hybrid BM25/vector + counselor cache)
│   ├── observability/
│   │   ├── logging_setup.py    # Structured JSON logging, intent/outcome logs, and DLP PII scrubber
│   │   └── tracing.py          # OpenTelemetry TracerProvider, ring buffer, and Cloud Trace exporter
│   ├── tools/
│   │   ├── scouting_scraper.py    # 138-badge catalog, pamphlet scraper, and workbook generator
│   │   ├── pamphlet_extractor.py  # Scout Shop emblem lookup, PDF extractor, and visual selector
│   │   ├── counselor_studiokit.py # Counselor Session Agenda and YPT Parent Letter generator
│   │   ├── diagram_generator.py   # Custom 220-DPI technical diagram and SVG builder
│   │   ├── pptx_builder.py        # python-pptx widescreen 16:9 slide deck builder
│   │   └── hitl_confirm.py        # FastMCP HMAC-SHA256 confirmation token and before_tool_callback
│   ├── app.py                  # Streamlit Counselor Workbench UI (:8501)
│   ├── server.py               # FastAPI + A2A 1.0 + SSE server for Material 3 Web Workbench (:8085)
│   ├── security.py             # OIDC Bearer JWT / X-API-Key verification and rate limiter
│   ├── resilience.py           # 3-state CircuitBreaker, exponential jitter retry, and ModelFallbackRouter
│   ├── config.py               # 138-badge catalog, ModelProvider, and Secret Manager helper
│   └── schemas.py              # Pydantic v2 data contracts, GuidedToolError, and JSON schema registry
├── ui/
│   ├── index.html              # Material 3 Web Workbench HTML and 4-tab Image Studio modal
│   ├── styles.css              # Material 3 Expressive CSS, Markdown typography, and FinOps table styles
│   └── app.js                  # Interactive slide stage, filmstrip, co-design bar, and Image Studio
├── terraform/
│   ├── main.tf                 # Least-privilege SA, VPC, Cloud Armor WAF, Cloud Run v2, Secret Manager
│   ├── outputs.tf              # Terraform output values
│   └── variables.tf            # GCP project, region, scaling, and subnet CIDR variables
├── tests/
│   ├── data/golden_badges.json                  # 12-badge golden evaluation dataset
│   ├── load/load_test.py                        # Concurrent API and deck generation latency benchmark
│   ├── eval_golden_suite.py                     # Golden evaluation harness and IR metric calculator
│   ├── test_conformance_and_a2ui.py             # AABB geometry, A2UI v0.9, Image Studio, and PPTX parity tests
│   ├── test_memory.py                           # SQLite session store, compaction, and hybrid retrieval tests
│   ├── test_pii_scrubber.py                     # Pre-LLM PII redaction and Model Armor guardrail tests
│   ├── test_resilience_and_fault_injection.py   # Circuit breaker, 429 retry, auth, and OpenAPI schema tests
│   └── test_tools.py                            # Tool validation and GuidedToolError recovery tests
├── ARCHITECTURE_DECISIONS.md   # 7 Architecture Decision Records with options and trade-offs
├── SCOPE.md                    # Project scope and target user personas
├── SPEC.md                     # Technical specification of agent topology and endpoints
├── Dockerfile                  # Multi-stage non-root container image with /health HEALTHCHECK
├── cloudbuild.yaml             # Cloud Build CI/CD pipeline with 10% canary and auto-rollback
├── service-spec.yaml           # Declarative ADK v2 multi-agent service specification
├── .env.example                # Sample environment variable configuration
├── pyproject.toml              # Python package dependencies and tool settings
└── run_local.sh                # Local launcher for both web interfaces
```

---

## 6. Configuration and local asset caching

### Engineering documentation
- **[`docs/TDD.md`](docs/TDD.md)**: Full Technical Design Document covering the 7-agent pipeline, Pydantic v2 data contracts, security boundary, and observability architecture.
- **[`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md)** and **[`docs/adr/README.md`](docs/adr/README.md)**: Seven Architecture Decision Records covering the options evaluated and trade-offs accepted.
- **[`docs/FDE_CAPSTONE_COMPANION_GUIDE.md`](docs/FDE_CAPSTONE_COMPANION_GUIDE.md)** and **[`docs/CAPSTONE_PANEL_PLAYBOOK.md`](docs/CAPSTONE_PANEL_PLAYBOOK.md)**: Slide-by-slide executive readout companion guide (8 Core Slides + 2 Appendix/Backup Slides), jargon decoder, presenter talk tracks, and panel Q&A defense matrix.
- **[`docs/finops-billing-and-deployment-guide.md`](docs/finops-billing-and-deployment-guide.md)**: Plain-English guide to token billing during development, local user installs, Cloud Run deployments, and budget/quota error handling.
- **[`docs/openapi.yaml`](docs/openapi.yaml)** and **[`docs/API_INTEGRATION_GUIDE.md`](docs/API_INTEGRATION_GUIDE.md)**: OpenAPI 3.1 specification and request examples for `/api/v1/*`, `/a2a/*`, `/health`, and `/readiness`.
- **[`docs/runbook.md`](docs/runbook.md)**: Operational runbook covering Terraform provisioning, incident triage (`429`/`503` circuit breaker open, AABB overlap, Model Armor block), SQLite online backup, and Cloud Run revision rollback.

### Environment variables (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | *(Optional)* | Google Gemini API key (or loaded from Google Cloud Secret Manager via `get_secret()`) |
| `BSA_HITL_SECRET_KEY` | *(Auto-generated / Secret Manager)* | HMAC-SHA256 signing key for Human-in-the-Loop confirmation tokens |
| `AUTH_REQUIRED` | `false` (local) / `true` (Cloud Run) | Enforces `X-API-Key` or `Authorization: Bearer <JWT>` on API routes when `true` |
| `GOOGLE_CLOUD_PROJECT` | `clayberg-scouts-bsa-prod` | GCP project ID for Secret Manager, Cloud DLP, Cloud Trace, and Vertex AI |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | GCP region |
| `PORT` | `8085` | HTTP port for the FastAPI Material 3 Web Workbench |
| `STREAMLIT_PORT` | `8501` | HTTP port for the Streamlit Counselor Workbench |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`) |

### Local asset caching and counselor profile storage

To keep slide builds fast and usable at campouts with limited internet access:
1. **Standalone badge emblems (`assets/badge_emblems/`)**: High-resolution Merit Badge patch emblems from the BSA Scout Shop are cached on disk for Slide 1, EDGE Skill Concept Maps, and UI headers.
2. **Official pamphlet PDFs and covers (`assets/pamphlets/`, `assets/pamphlet_covers/`, `assets/pamphlet_images/`)**: Downloaded pamphlet PDFs are cached locally alongside their rendered cover images and extracted figures.
3. **Per-badge image catalogs (`assets/badge_image_catalog/<badge_slug>/` + SQLite `badge_image_catalog`)**: Every official pamphlet figure, `WebImageSearchAgent` Wikimedia photo, `NanoBananaImageAgent` custom illustration, and EDGE Skill Concept Map is indexed per Merit Badge with its title and description so you can switch or reuse images across slides.
4. **Counselor contact profile (`.cache/counselor_profile.json` locally; `localStorage` in Cloud Run)**: Local runs cache your counselor contact details in `.cache/counselor_profile.json` with `0600` owner-only file permissions. Multi-tenant Cloud Run deployments store your profile in browser `localStorage` (`scouts_bsa_counselor_profile_v1`) so PII is never shared on the server filesystem, and `scrub_pii_before_sink()` redacts contact PII before any LLM prompt, SQLite log, or OpenTelemetry span.

---

## 7. Optional Cloud Deployment (Terraform, Cloud Build, and ADK CLI)

### Option A: Provision infrastructure with Terraform (`terraform/`)

The `terraform/` directory creates:
- A dedicated least-privilege Service Account (`scouts-bsa-agent-sa`) with scoped IAM roles (`roles/aiplatform.user`, `roles/secretmanager.secretAccessor`, `roles/storage.objectUser`, `roles/logging.logWriter`, `roles/cloudtrace.agent`).
- A custom VPC (`scouts-bsa-agent-vpc`), private subnet with Private Google Access and VPC Flow Logs, firewall rules, and a Cloud Armor WAF policy (`scouts-bsa-agent-cloud-armor-waf`).
- Google Cloud Secret Manager secrets (`gemini-api-key`, `bsa-hitl-secret-key`) and a versioned Cloud Storage bucket (`<project_id>-bsa-presentations`).
- A Google Cloud Run v2 service (`scouts-bsa-merit-badge-agent`) with Direct VPC Egress, `min_instances = 1`, `max_instances = 10`, and `/readiness` + `/health` probes.

```bash
cd terraform
terraform init
terraform apply \
  -var="project_id=your-gcp-project-id" \
  -var="region=us-central1"
```

### Option B: Canary CI/CD pipeline via Cloud Build (`cloudbuild.yaml`)

```bash
gcloud builds submit --config=cloudbuild.yaml --project="your-gcp-project-id"
```

### Option C: Deploy via Google ADK CLI (`adk deploy`)

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

adk deploy cloud_run \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --service_name="scouts-bsa-merit-badge-agent" \
  src.agents
```

---

## 8. Testing and evaluation gate

```bash
# 1. Run all 47 unit, security, fault-injection, Image Studio, conformance, and golden evaluation tests
.venv/bin/pytest tests/ -v

# 2. Run the pre-deployment evaluation gate across the 12 golden badges
#    (verifies IR Recall@3 = 1.0, MRR = 1.0, NDCG@3 = 1.0, SHA-256 requirement lock, and 0 AABB overlaps)
.venv/bin/python3 scripts/eval_gate.py

# 3. Run the concurrent API and deck generation latency benchmark
.venv/bin/python3 tests/load/load_test.py
```

---

## 9. Troubleshooting and FAQ

- **Can I run the workbench offline at summer camp?**
  - Yes. All 138 Merit Badge requirement trees, standalone badge emblems, and custom diagram generators work offline. Any pamphlet PDFs, Wikimedia images, or Nano Banana graphics already cached in `assets/` are reused automatically.
- **How is my Counselor contact information cached and how is PII protected?**
  - When you run the tool locally on your laptop, your Counselor Name, Troop, Location/ZIP, Email, and Phone are saved to `.cache/counselor_profile.json` (`0600` owner-only permissions, git-ignored) so they auto-populate next time. When running in multi-tenant Cloud Run, server disk caching is disabled and your browser stores the fields in `localStorage`. In both modes, your contact PII is used only on the local Cover Slide and Parent Letter and is scrubbed by `ScoutsBSAModelArmorPlugin` and `scrub_pii_before_sink()` before any LLM call, SQLite telemetry write, or OpenTelemetry span.
- **How do I remove a graphic from a slide, restore the original graphic, or add a custom image?**
  - In the **Per-Slide Interactive Co-Design Bar**, set **4. Right-Side Graphic** to **None (Remove Graphic & Expand Text to Full Width)** to remove the image and expand the text cards across the full slide, or choose **Restore Original Slide Graphic** to bring back the initial pamphlet/topic figure. To browse all cached images for the badge, search Wikimedia Commons, generate a custom graphic with `NanoBananaImageAgent` (after consenting to the `$0.08 USD` cost estimate), or upload a local image file (`$0.00 USD`), click **🖼️ Manage & Add Slide Images (Popup)**.
- **How does Local Troop Grounding know what is local to my troop?**
  - Enter your City/State or 5-digit ZIP code in the **Location (City, State or ZIP Code)** box (for example, `01949` or `Middleton, MA`). If you leave that field blank, `resolve_counselor_location()` checks your **Troop & Council Affiliation** text for a ZIP code, state abbreviation, city, or council name, and in the web UI falls back to your browser timezone.
- **How do I add our troop's custom logo to the Cover Slide?**
  - In the left sidebar under **2. Deck Style & Counselor Info**, upload a `.png` or `.jpg` file under **Optional Troop Custom Logo**, then click **Generate Slide Deck & Workbook**. The logo is placed in the lower-left counselor contact block on Slide 1 in both the web preview and the downloaded `.pptx` file.
- **How do I change the ports if `8085` or `8501` is already in use?**
  - Set `PORT` and `STREAMLIT_PORT` when running `./run_local.sh`:
    ```bash
    PORT=8090 STREAMLIT_PORT=8502 ./run_local.sh
    ```

