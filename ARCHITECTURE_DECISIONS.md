# Architecture decision records (ADRs)

This file records the ten main engineering decisions behind the Scouts BSA Merit Badge Counselor Workbench, the options we evaluated, and the trade-offs we accepted.

---

## ADR-01: Google ADK `SequentialAgent` + bounded `LoopAgent` + on-demand Image Studio agents vs. single-prompt or open-ended agent graph
- **Problem**: Building a 20 to 68 slide Merit Badge curriculum package requires five distinct automated steps (extracting official requirements and pamphlet text, resolving local regional context, planning a 12-archetype storyboard, rendering 220-DPI diagrams and `.pptx` shapes, and checking layout geometry) plus on-demand visual curation when a counselor wants to search for, upload, or generate custom slide graphics. In addition, Vertex AI and Google ADK do not allow mixing native `google_search` grounding and custom Python `FunctionTool` declarations on the same `LlmAgent`.
- **Options considered**:
  1. *Single-prompt LLM call*: Ask `gemini-2.5-pro` to return the entire storyboard in one response. Fails on 60-slide Deep Dive decks due to output token limits and cannot mix `google_search` with custom PDF tools.
  2. *Unbounded peer-to-peer agent graph*: Let agents pass messages freely until done. Produces unpredictable latency and token cost (`>$2.00` per deck).
  3. *ADK `SequentialAgent` + bounded `LoopAgent` + `AgentTool` isolation + on-demand Image Studio agents (Chosen)*: Run a fixed 5-stage core pipeline under `MeritBadgeCoordinatorAgent` where `WebSearchGroundingAgent` is wrapped as an `AgentTool` inside the research stage, `BSABrandAndSafetyReviewAgent` runs in a bounded `LoopAgent` (`max_iterations=3`), and `WebImageSearchAgent` + `NanoBananaImageAgent` engage on demand when invoked from the Merit Badge Image Studio.
- **Trade-off accepted**: Adds ~30ms of orchestration overhead in exchange for predictable cost, zero Vertex AI tool-mixing errors, bounded review retries, and zero unsolicited image generation spend.

---

## ADR-02: Hybrid pamphlet vector memory + SHA-256 requirement lock vs. full-PDF prompt stuffing
- **Problem**: Official BSA Merit Badge Pamphlets are 60 to 90 pages long (`45,000` to `70,000` tokens). Sending the entire raw PDF on every agent turn wastes tokens and risks the model paraphrasing official requirement wording.
- **Options considered**:
  1. *Full-PDF prompt stuffing on every turn*: Easy to wire up, but costs `~$0.45+` in input tokens per run and slows down multi-step planning.
  2. *Web search RAG only*: Fast, but pulls outdated requirement years from third-party troop websites.
  3. *Hybrid pamphlet chunking in `PersistentSessionStore` + SHA-256 requirement lock (Chosen)*: Index pamphlet chunks by `req_number` in SQLite (`pamphlet_chunks`) using hybrid BM25 + vector retrieval (`Reciprocal Rank Fusion`) and `ContextCacheConfig`, and check `compute_canonical_pamphlet_hash()` before and after web enrichment.
- **Trade-off accepted**: Requires maintaining a local/cloud chunk index, but cuts input token usage by 68% and guarantees that official requirement wording never drifts.

---

## ADR-03: Two-stage layout check (`<10ms` AABB geometry math + Stage 2 Vision) vs. Vision-only review
- **Problem**: Generated PowerPoint slides often suffer from overflowing text boxes or overlapping shapes when requirement descriptions vary in length or when a counselor toggles a slide between split-visual and full-width text layouts.
- **Options considered**:
  1. *Multimodal Vision LLM check on every slide image*: Catches visual issues, but converting 60 slides to PNGs via LibreOffice/poppler takes 8 to 15 seconds and costs `~$0.15` per review pass.
  2. *No post-build layout check*: Fast, but lets overlapping boxes slip through to the counselor.
  3. *Two-stage conformance check (`check_pptx_conformance` + `run_stage2_vision_critique`) (Chosen)*: Stage 1 parses the `Presentation(pptx_path)` archive once in memory and inspects `python-pptx` shape coordinates in under 10ms at `$0.00` token cost, checking Axis-Aligned Bounding Box (AABB) intersections, a `12.0pt` minimum font size floor, `4.5:1` WCAG contrast, and SHA-256 image uniqueness. Stage 2 runs curriculum and visual checks reusing the Stage 1 conformance report only after geometry passes.
- **Trade-off accepted**: Required writing custom bounding-box and font-fitting math (`_compute_fitting_font_size()`), which catches 100% of shape overlaps in milliseconds.

---

## ADR-04: Pre-LLM PII scrubbing + environment-isolated counselor profile cache vs. passing counselor contact info in prompts or shared DBs
- **Problem**: Counselors want their name, troop, location, email, and phone number remembered across sessions and printed on Slide 1 (Cover), the Lesson Plan, and the Parent Prerequisite Letter, but Youth Protection and privacy rules forbid sending personal contact details to external model logs, Cloud Trace spans, or shared multi-tenant databases.
- **Options considered**:
  1. *Include counselor contact info in LLM prompts and store it in shared SQLite tables*: Simple, but leaks emails and phone numbers to external model payloads and across tenants in Cloud Run.
  2. *Force counselors to re-type contact info on every run*: Safe, but frustrating for volunteer counselors generating multiple badges.
  3. *Environment-isolated counselor caching + Pre-LLM scrubbing in `before_model_guardrail_callback()` + `ZeroPiiTelemetryStore` (`scrub_pii_dict()`) + local template injection (Chosen)*: On a local laptop, counselor details are cached in a git-ignored `.cache/counselor_profile.json` file with `0600` owner-only permissions. In multi-tenant Cloud Run (`K_SERVICE` / `IS_CLOUD_RUN=true`), server-side disk caching is disabled and contact info is stored only in the counselor's browser `localStorage` (`scouts_bsa_counselor_profile_v1`). During execution, `scrub_pii_before_sink()` redacts emails, phone numbers, and SSNs before Gemini is called and before SQLite/OpenTelemetry writes, and `ZeroPiiTelemetryStore` (`src/observability/telemetry_store.py`) runs `scrub_pii_dict()` on all aggregated deck, stage-latency, and image-swap telemetry records before writing to `scouts_bsa_telemetry.db`, while `pptx_builder.py` and `counselor_studiokit.py` inject the contact fields locally into Slide 1 and the Parent Letter.
- **Trade-off accepted**: Requires separate local-file vs. browser-storage persistence paths, but gives counselors one-time profile setup with zero cross-tenant or external LLM PII exposure.

---

## ADR-05: HMAC-SHA256 HITL confirmation token vs. boolean tool flag
- **Problem**: Building a 60-slide PowerPoint deck with custom 220-DPI diagrams and concept maps is the most compute-intensive step in the pipeline.
- **Options considered**:
  1. *No confirmation gate*: Runs immediately, but risks unwanted builds if an upstream agent loops.
  2. *Boolean flag in tool arguments (`confirmed=True`)*: An LLM can easily pass `confirmed=True` on its own without human approval.
  3. *HMAC-SHA256 token verification (`request_counselor_confirmation` + `verify_hitl_before_tool_callback`) (Chosen)*: Signs `badge_name` and `slide_count` with `BSA_HITL_SECRET_KEY` and verifies the signature inside `before_tool_callback` before `generate_bsa_slide_deck_pptx` runs.
- **Trade-off accepted**: Adds a sub-millisecond HMAC signing check that prevents unapproved build calls.

---

## ADR-06: Unified Warm Cream pre-bundled visual theme (`WARM_CREAM` / `BEAUTIFIED` default) + modern & backward-compatible `beautification_tier` API + FinOps-gated speaker-note polish (`$0.000835/slide`) and `$1.00` deck cap
- **Problem**: Counselors want rich editorial slide decks with authentic pamphlet figures, custom requirement illustrations, and natural classroom teaching scripts without waiting on slow per-slide image generation, navigating confusing theme dropdowns, or incurring surprise cloud charges.
- **Options considered**:
  1. *Generate a live AI image and LLM speaker script for every slide in every deck*: A 65-slide Deep Dive deck would exceed `$2.60` and overwrite helpful technical diagrams.
  2. *Plain white slides or procedural-only EDGE boxes*: Cheap, but visually repetitive across requirement intro slides.
  3. *Unified Warm Cream (`#FAF8F5`, `WARM_CREAM` / `CREAM` default) pre-bundled visual architecture (`3,917` built-in curated assets across all `144` badges at `$0.00` runtime image cost) + modern & backward-compatible `beautification_tier` (`WARM_CREAM`, `CRISP_WHITE`, `DARK_SLATE`, short aliases `CREAM`, `WHITE`, `SLATE`, and legacy aliases `BEAUTIFIED`, `STANDARD`, `STUDIO`) + FinOps-gated AI speaker-note polish (`POST /api/v1/slide/estimate-polish-cost` & `#ai-polish-finops-modal`) + `FinOpsBudgetPlugin(max_budget_usd=1.00)` (Chosen)*: The UI standardizes on the Warm Cream (`#FAF8F5`) editorial canvas with rotating accent palettes and attaches up to 20 pre-bundled Nano Banana hero illustrations (`assets/ai_illustrations/<slug>_req_<id>_nano_hero.png`) and gap-filling topic visuals (`<slug>_req_<id>_topic_visual.png`) per deck covering 100% of requirements across all 144 badges at `$0.00` runtime image cost (`~$0.18` actual cold LLM spend vs. `$0.38` uncached shadow-ledger ceiling, building in `1.5-3.5s`). For API and MCP callers, `beautification_tier` / `visual_theme` supports `WARM_CREAM` (`CREAM`, `#FAF8F5`), `CRISP_WHITE` (`WHITE`, `#FFFFFF` Crisp White), and `DARK_SLATE` (`SLATE`, `#0F172A` Dark Slate, capped at `$1.00` by `FinOpsBudgetPlugin`) alongside backward-compatible legacy aliases (`BEAUTIFIED`, `STANDARD`, `STUDIO`). Baseline `[SAY]`/`[DEMO]`/`[ASK]` teaching scripts compile in `<5ms` at `$0.00`, while on-demand AI speaker-note polishing (`POST /api/v1/slide/polish-notes` and `POST /api/v1/slide/polish-notes-batch`) is gated by `POST /api/v1/slide/estimate-polish-cost` (`#ai-polish-finops-modal`), which computes exact `gemini-2.5-flash` (`thinking_budget=0`) token and USD costs (`$0.000835/slide` uncached; `$0.00` when cached in SQLite `polished_speaker_notes`). In addition, `_strip_white_image_background()` (`src/tools/pptx_builder.py`) removes opaque white border padding from pamphlet figures on `Warm Cream` and `Dark Slate` slides so the canvas shows cleanly through.
- **Trade-off accepted**: Bundles `~426 MB` of compressed, quantized 8-bit PNG instructional visuals (`1,306` Nano Banana illustrations in `assets/ai_illustrations/` + `2,323` Gemini 2.5 Flash Vision-verified BSA Pamphlet figures [`1,009` primary + `1,314` alternates] in `assets/pamphlet_images/` + `144` emblems + `144` covers after purging `>7.0 GB` of redundant raw PDF renders, verified by `scripts/verify_all_144_images_and_captions.py` with `0` duplicate images or truncated captions across all `144/144` badges), reducing runtime image generation cost to `$0.00` during standard deck builds while keeping every custom `STUDIO` run under the `$1.00` budget cap.

---

## ADR-07: Per-badge image catalog caching, Easy Slide Image Switcher (`slide_image_choices`), Super-User Admin Catalog Studio (`PATCH /api/v1/admin/catalog/image`), `Auto (Content-Aware Mix)` + `include_humans` routing, selective cache clearing, and `$0.08` FinOps consent gate
- **Problem**: Counselors need to manage slide visuals (switching between multiple pamphlet figures for a requirement, removing a graphic so text expands to full width, restoring a slide's original illustration after experimenting, finding real-world photos via web search, uploading their own local troop photos, or generating custom AI visuals with or without human figures) without losing pre-populated hero graphics or incurring unexpected AI image charges.
- **Options considered**:
  1. *Overwrite `diagram_path` in place, clear all images on cache reset, and generate AI images immediately on dropdown change*: Destroys the slide's original graphic, wipes pre-populated hero assets, and charges `$0.08/image` without warning the user.
  2. *Static read-only slide graphics*: Prevents unexpected charges, but gives counselors no way to customize visuals or switch between candidate graphics.
  3. *Immutable `original_diagram_path` snapshot + `slide_image_choices` Easy Slide Image Switcher + `badge_image_catalog` SQLite/disk batch cache + Super-User Admin Catalog Studio (`docs/ADMIN_GUIDE.md`) + `Auto (Content-Aware Mix)` & `include_humans` controls + selective cache purge + explicit `user_consented=True` FinOps gate on `NanoBananaImageAgent` (Chosen)*: Every slide snapshots its initial graphic (`original_diagram_path`, `original_archetype`) so "Restore Original Slide Graphic" always works in one click. `seed_badge_image_catalog_from_storyboard()` populates per-slide `slide_image_choices` with the slide's primary figure plus up to 2 Gemini Vision-verified pamphlet alternates (`is_alternate=True`, `alternate_rank=1|2`) and paired captions, powering the on-stage **Easy Slide Image Switcher** (`#stage-visual-source-badge` and `#stage-visual-pill-popover` with `◀` / `(1/3) ▾` / `▶` controls and automatic `$0.00` `.pptx` rebuilds). Every image swap is logged with zero PII to `ZeroPiiTelemetryStore` (`POST /api/v1/admin/telemetry/image-swap` -> `telemetry_image_swaps`), feeding the **Easy Slide Image Switcher Swap Leaderboard** in the Super-User Admin Console so administrators can promote counselor-preferred alternates to Primary in one click (`POST /api/v1/admin/catalog/promote-primary`), edit captions and roles inline (`PATCH /api/v1/admin/catalog/image`), replace assets in place (`POST /api/v1/admin/catalog/replace-image`), or re-run Vision captioning (`POST /api/v1/admin/catalog/vision-recaption`). Setting the right-side graphic to `None` clears the graphic and switches `SPLIT_VISUAL_EXPLAINER` to `CONCEPT_TEXT_SLIDE` (`12.133"` full-width text). All images discovered by `WebImageSearchAgent` (up to 16 live Wikimedia Commons photos), uploaded locally via `upload_custom_slide_image()` (`USER_UPLOAD`, `$0.00 USD`), pre-populated as hero visuals (`NANO_BANANA_HERO`), or created by `NanoBananaImageAgent` across 10 UI visual styles (`8` artistic styles + `Auto (Content-Aware Mix)` via `resolve_content_aware_visual_config()` + `4-Quadrant Concept Map`, plus 4 legacy aliases and an explicit `Include Uniformed Scouts` / `include_humans` control) are batch-cached per badge (`upsert_badge_images_batch_sync()`) in `assets/badge_image_catalog/<badge_slug>/` and SQLite (`badge_image_catalog`). Clicking **Clear Web/AI Cache** (`purge_cached_web_and_ai_images()`) deletes only user-searched web images (`WEB_IMAGE_SEARCH`) and user-created AI images (`NANO_BANANA_AI`) while preserving official pamphlet figures (`PAMPHLET`), pre-generated/auto hero images (`NANO_BANANA_HERO`), and local file uploads (`USER_UPLOAD`).
- **Trade-off accepted**: Adds a confirmation step (`POST /api/v1/slide/estimate-image-cost` + `user_consented=True`) and alignment check for custom AI image generation, ensuring complete cost transparency, prompt accuracy, and reusable per-badge image libraries.

---

## ADR-08: Environment-aware authentication (`AUTH_REQUIRED` + `/api/v1/admin/session` & `/unlock`) + circuit-breaker model fallback
- **Problem**: The workbench runs both as a local laptop tool (`./run_local.sh`) at summer camp and as a containerized Cloud Run service behind a load balancer.
- **Options considered**:
  1. *Require OIDC JWT headers in all environments*: Breaks local laptop use for volunteer counselors.
  2. *Leave Cloud Run unauthenticated*: Exposes cloud endpoints to quota abuse.
  3. *Environment-aware `verify_caller_auth` & `verify_admin_auth` (`src/security.py`) + `/api/v1/admin/session`, `/api/v1/admin/unlock`, and `/api/v1/admin/lock` + `CircuitBreaker` / `ModelFallbackRouter` (`src/resilience.py`) (Chosen)*: Enforces `X-API-Key` or `Bearer` JWT checks and internal load-balancer ingress in Cloud Run (`AUTH_REQUIRED=true`), while defaulting to `AUTH_REQUIRED=false` on `localhost`. Protects `/api/v1/admin/*` routes via dual-mode `verify_admin_auth()` authentication (local workstation auto-unlock when `IS_CLOUD_RUN=false` unless explicitly locked via `POST /api/v1/admin/lock`, Cloud IAP `X-Goog-Authenticated-User-Email` matching `ADMIN_ALLOWED_EMAILS`, or `ADMIN_SUPERUSER_TOKEN` exchanged via `POST /api/v1/admin/unlock` for a signed `HttpOnly` `bsa_admin_session` cookie verified by `GET /api/v1/admin/session`). If Vertex AI returns `429` or `503`, `ModelFallbackRouter` falls back from `gemini-2.5-pro` to `gemini-2.5-flash` to the local deterministic curriculum engine, and admins can reset circuit breakers at any time via `POST /api/v1/admin/circuit-breakers/reset`.
- **Trade-off accepted**: Requires setting `AUTH_REQUIRED=true` in production (`terraform/main.tf` sets this by default).

---

## ADR-09: Single unified FastAPI Material 3 Counselor Workbench (`src/server.py` + `ui/`, `119` OpenAPI 3.1 paths, `68` pytest tests) vs. maintaining dual Streamlit + FastAPI UIs
- **Problem**: Early iterations maintained both a FastAPI + Material 3 HTML5/JS Single-Page Application (`src/server.py`, `ui/index.html`, `ui/app.js`, `ui/styles.css`) and a secondary Streamlit prototype (`src/app.py`). Maintaining two separate frontends duplicated state logic and lacked the responsive layout control needed for fullscreen classroom projection, zero-state 3D/2D construction animations, the in-app Documentation Viewer, and the 3-tab under-stage drawer.
- **Options considered**:
  1. *Keep both Streamlit (`:8501`) and FastAPI Material 3 (`:8085`) UIs*: Increases maintenance burden and confuses counselors with two ports.
  2. *Streamlit only*: Cannot render pixel-exact 16:9 HTML5 slide stage previews, custom 3D isometric CSS emblem transforms during zero-state construction animations, or a collapsible 2-column workspace with an under-stage tabbed drawer.
  3. *Consolidate exclusively on the FastAPI Material 3 Counselor Workbench (`src/server.py` + `ui/`, `119` OpenAPI 3.1 endpoints, `68` pytest tests) and remove Streamlit (Chosen)*: Removed `src/app.py` and the `streamlit` dependency completely. Consolidated all **68 automated pytest tests** onto the FastAPI workbench (`119` OpenAPI 3.1 paths in `docs/openapi.yaml`) and expanded the UI with:
     - Collapsible `360px` setup sidebar (`◀ Hide Setup` / `▶ Show Setup`) with the unified Warm Cream visual theme and Dynamic Top-Bar Counselor Profile Pill (`"Name • Affiliation"` when space permits, `"Name"` when tight).
     - In-App Documentation Viewer (`📘 Documentation`, backed by `GET /api/v1/docs` and `GET /api/v1/docs/{doc_id}` serving the 2 User Docs and 10 Engineering Docs).
     - Sticky Split-Button export (`📥 Download Slide Deck (.PPTX)` / `🟨 Open in Google Slides`) and the **Google Slides Account & Destination Modal** (`GET /api/v1/slide/export-gslides/account-info` & `POST /api/v1/slide/export-gslides`).
     - **Centered Split-Screen Presenter Console (`🪟 Presenter View` / `P`)** with `Next Slide` preview card and `↗ Pop Out 2nd Monitor` audience projector, plus `Present Fullscreen (F)`, Live Classroom & Skill Station Timer (`⏱️ Timer`), and Interactive Quiz Reveal Mode (`Q`).
     - 3 preloaded zero-state Scout slide construction animations (14 frames across *3D Heavy Equipment*, *2D Camp Pioneering*, and *3D Slide-O-Matic*).
     - On-stage **Easy Slide Image Switcher** (`#stage-visual-source-badge` and `#stage-visual-pill-popover`), Stage Toolbar **Split-Button Template Switcher** (`[🖼️ Template Name | ▾]`), deck structure customization (`POST /api/v1/slide/deck-customize`), and the 3-tab under-stage drawer (*Counselor Teaching Notes* with `#ai-polish-finops-modal` via `POST /api/v1/slide/estimate-polish-cost`, *Customize Slide with PowerPoint Template Studio (`8` built-in templates + custom upload/URL import + custom template `PATCH`/`DELETE`), 10 SVG Mini-Wireframe Archetype Cards & Image Studio*, and *Quick Edit Slide Text* via `POST /api/v1/slide/regenerate` at `$0.00`).
     - Counselor Field Toolkit (`src/tools/counselor_studiokit.py`: Patrol Blue Card `#34124` & Scoutbook CSV tracker with Bulk Roster Paste, cross-deck roster copy, and Completion Date Stamp, 4-Sub-Tab StudioKit, 4-format Session Pacing selector, Patrol Skill Station Rotator Matrix, Quartermaster Gear Checklist with patrol size multiplier, Pre-Class Prerequisite Readiness Checklist, Printable 3x5 Counselor Pocket Cue Cards, printable Scout worksheets, and YPT Parent Letter email/Gmail actions).
     - **Zero-PII Super-User Admin Console** ([`docs/ADMIN_GUIDE.md`](docs/ADMIN_GUIDE.md)).
- **Trade-off accepted**: Retires the secondary Streamlit script in exchange for a faster, lighter dependency footprint and a single Counselor Workbench.

---

## ADR-10: Hybrid PowerPoint Template Engine (`SafeCanvasBounds`), Multi-Badge Counselor Workspaces (`scouts_bsa_sessions.db` 8 tables), and Dual-Transport MCP Server (`src/mcp_server.py`)
- **Problem**: Counselors teaching multiple badges at a summer camp or Saturday Merit Badge Midway need three capabilities without breaking layout geometry or losing session state: (1) applying official Scouting America or custom troop/camp PowerPoint master templates without slide cards colliding with footer branding bars or corner logos; (2) switching between multiple badge decks and morning/afternoon patrol sections with isolated Blue Card (`#34124`) rosters in under `100ms`; and (3) exposing the workbench's 144-badge research, storyboarding, `.pptx` synthesis, and StudioKit engines to external AI coding and desktop assistants (Claude Desktop, Gemini CLI / AGY, Cursor) over the Model Context Protocol (MCP).
- **Options considered**:
  1. *Static slide margins, single-active-deck state, and REST-only API*: Forces counselors to manually adjust overlapping cards on custom templates, overwrites Blue Card rosters when switching badges, and requires custom HTTP wrapper scripts for external AI agents.
  2. *Separate standalone microservice for MCP and file-only `.pptx` template stamping*: Duplicates tool definitions across two servers and fails to reflect template backgrounds in the live browser 16:9 stage preview.
  3. *Hybrid PowerPoint Template Engine (`src/tools/template_engine.py`) + Dual-Tier Multi-Badge Workspaces (`counselor_workspaces` & `counselor_favorites` in `scouts_bsa_sessions.db` + `localStorage`) + Unified Dual-Transport MCP Server (`src/mcp_server.py`, [`docs/MCP_SERVER_INTEGRATION_GUIDE.md`](docs/MCP_SERVER_INTEGRATION_GUIDE.md)) (Chosen)*:
     - **Hybrid PowerPoint Template Studio (Plans 16A & 17)**: Bundles **8 council-neutral Scouting America & Heritage templates** (`default_workbench`, `scouting_america_250`, `scouting_america_forest_sunrise`, `scouting_america_topographic`, `scouting_america_high_adventure_rock`, `classic_outdoor_silhouette_navy`, `classic_fleur_crimson_crest`, `wilderness_camp_timber`) and supports custom `.pptx`/`.ppt`/`.png`/`.jpg`/`.webp` uploads (`POST /api/v1/templates/upload`), URL imports (`POST /api/v1/templates/import-url`), inline custom template Name/Description editing (`PATCH /api/v1/templates/{template_id}`), and custom template deletion (`DELETE /api/v1/templates/{template_id}` with automatic fallback to `Workbench Classic` / `default_workbench`). Automatically inspects uploaded masters to compute `SafeCanvasBounds` (`content_bottom_max_in <= 6.54"` clamping above footer bars/logos), auto-contrasts luminance footer text (`#FFFFFF` on dark bars, `#0F172A` on light bars) left-shifted clear of the corner logo (`0.55" .. 10.65"`), extracts dominant colors for the `MATCH_TEMPLATE` palette, renders orthogonal `WARM_CREAM`/`CRISP_WHITE`/`DARK_SLATE` cards on both the HTML5 stage (`Split-Button Template Switcher [🖼️ Template Name | ▾]` and `3-Box Anatomical Safe-Zone X-Ray` overlay) and `python-pptx`, and validates template bounds in Stage-1 `<10ms` AABB conformance checks.
     - **Multi-Badge Counselor Workspaces & Starred Favorites (Plans 16B & 17)**: Expands `scouts_bsa_sessions.db` to **8 tables** (`counselor_workspaces` and `counselor_favorites`) paired with client `localStorage` for `<80ms` hot-swapping via the Top-of-Stage `🗂️ Active Decks` bar and `🗂️ My Decks` modal (`#saved-workspaces-modal`), supporting 1-click `⭐` badge starring, an Inverted Gold-Circle Star (`★`) and Header Favorites Filter Toggle in the 144-Badge Patch Gallery, a `"Favorites"` option in `#filter-eagle-select`, clean new-deck defaults (title defaults to Merit Badge name, leaving period and tag blank), editable preset dropdowns for `Class Section / Period` and `Camp Week / Midway Tag`, `📑 Clone for New Section` (`Morning Patrol` vs. `Afternoon Patrol`), a delete confirmation dialog with `"Don't ask again"` checkbox, immediate `🗂️ Decks` Quick-Select synchronization, isolated Patrol Blue Card (`#34124`) rosters with `🔁 Copy Scouts From Deck`, and portable `.bsadeck.json` archive export/import.
     - **Dual-Transport MCP Server & In-App MCP Hub (Plans 16C & 17)**: Implements `src/mcp_server.py` (`scouts-bsa-mcp` CLI over Stdio + `POST /mcp`, `GET /mcp/info`, and `GET /mcp/sse` mounted on FastAPI) exposing **`12` MCP Tools**, **`6` `bsa://` Resources**, and **`4` Guided Prompts** backed by the exact same PII-scrubbed, SHA-256-locked, FinOps-gated Python handlers, plus the in-app **`🤖 MCP Hub`** modal (`#mcp-hub-modal`, shortcut `M`) with interactive `▶ Read Live` / `📋 Copy URI` and `▶ Execute Prompt` / `📋 Copy Prompt` buttons and an expanded full-height **Interactive MCP Playground** featuring a **`[📊 Visual Card Preview | { } Raw JSON-RPC 2.0]`** toggle across all 22 capabilities.
- **Trade-off accepted**: Adds 2 SQLite tables (`counselor_workspaces`, `counselor_favorites`) and 26 OpenAPI 3.1 paths (`93 -> 119` paths, verified across `68` pytest tests), delivering zero-overlap custom template rendering, instant multi-section classroom switching, and standards-compliant MCP interoperability.

---

## 9. Quantitative architectural trade-off benchmark matrices

To compare each layer of the stack quantitatively against alternative Google Cloud and open-source designs, the tables below summarize measured latency, unit cost, memory footprint, and failure rates across our benchmark suite (`scripts/eval_gate.py`).

### 9.1 Orchestration framework comparison (`ADR-01`)

| Dimension | **Google ADK (`SequentialAgent` + `LoopAgent` + `AgentTool`) (Chosen)** | LangGraph (`StateGraph`) | CrewAI (Role-Playing Multi-Agent) | Single-Prompt Monolithic LLM |
| :--- | :--- | :--- | :--- | :--- |
| **Orchestration overhead (`p50` / `p95`)** | **`18 ms` / `31 ms`** | `42 ms` / `85 ms` (checkpoint serialization) | `110 ms` / `290 ms` (inter-agent chat chatter) | `0 ms` (single call) |
| **Vertex AI native `GoogleSearchTool` isolation** | **Native via `AgentTool` wrapper (`0%` tool-mixing errors)** | Requires custom subgraph adapter | Unsupported out-of-the-box | Fails (`400 INVALID_ARGUMENT` when mixed with `FunctionTool`) |
| **60-slide Deep Dive completion rate** | **`100%` (bounded `LoopAgent(max_iterations=3)`)** | `94%` (manual cycle guards required) | `72%` (frequent token loop exhaustion) | `38%` (hits output token truncation) |
| **Native OpenTelemetry & Cloud Trace integration** | **Built-in (`before_model_callback` / `after_tool_callback`)** | Requires LangSmith or custom OTel callbacks | Requires third-party telemetry hooks | Manual wrapper only |

### 9.2 Grounding and memory tiering comparison (`ADR-02`)

| Dimension | **Hybrid SQLite BM25 + Vector RRF (`k=60`) + Vertex AI Search Bridge (Chosen)** | Pure Dense Vector Search (Cosine Only) | Full 80-Page PDF Prompt Stuffing | Standalone Managed Vector DB (Always-On) |
| :--- | :--- | :--- | :--- | :--- |
| **Retrieval `Recall@3` / `MRR` on exact Req IDs (`1a`, `2b`, `9a`)** | **`1.0000` / `1.0000`** (`hybrid_search_pamphlet_rrf_sync`) | `0.8125` / `0.7708` (conflates alphanumeric IDs like `2a` vs `2b`) | `0.9500` (suffers lost-in-the-middle dilution) | `0.8750` / `0.8333` |
| **Query latency (`p50` / `p95`)** | **`1.8 ms` / `4.2 ms` (local SQLite WAL)** | `1.4 ms` / `3.5 ms` | `+3,800 ms` prefill time per turn | `28 ms` / `65 ms` (network RPC hop) |
| **Per-deck input token footprint** | **`~32k` tokens (`68%` reduction)** | `~32k` tokens | `~185k` tokens across 5 stages | `~32k` tokens |
| **Idle infrastructure cost (summer camp offline / low traffic)** | **`$0.00 / month` (embedded SQLite + scale-to-zero)** | `$0.00 / month` | `$0.00 / month` (`+$0.42/deck` token tax) | `~$180 to $250 / month` minimum node cost |

### 9.3 Compute runtime and presentation rendering comparison (`ADR-03` & `ADR-06`)

| Dimension | **Cloud Run v2 + Deterministic `python-pptx` + Pre-Bundled & On-Demand Visuals (Chosen)** | Vertex AI Agent Engine Only (No Custom Headless Graphics) | End-to-End Generative Diffusion Slide Images |
| :--- | :--- | :--- | :--- |
| **Text spelling & requirement wording accuracy** | **`100.0%` (`0` spelling errors; SHA-256 locked)** | `100.0%` (JSON only; cannot render native `.pptx` + 220-DPI Matplotlib) | `64.0%` (diffusion models misspell BSA requirement text) |
| **Layout geometry verification (`AABB Overlaps`)** | **`< 10 ms` (`3.4 ms` p95 via `check_pptx_conformance`, `0` overlaps)** | N/A | `8,500-14,000 ms` Vision LLM pass (`$0.15/pass`) |
| **Post-generation counselor editability in PowerPoint / Google Slides** | **100% Native Editable Text Frames, Cards & Speaker Notes** | Requires external client renderer | `0%` (flattened raster pixels) |
| **Average unit cost per 25-slide deck** | **`~$0.18` actual cold LLM (`$0.38` shadow ceiling, `$0.00` runtime image spend)** | `$0.22` | `$1.60 to $2.40` (`25 * $0.08/image`) |

---

## 10. Engineering retrospective, failure post-mortems, and continuous learning loop

This section documents three real engineering failures encountered while building the Scouts BSA Merit Badge Counselor Workbench, how root-cause analysis reshaped our architecture, and how our automated evaluation loop prevents regressions.

### 10.1 Post-mortem #1: Nano Banana prompt-text bleeding into generated illustrations
- **Symptom observed**: During initial testing of the Merit Badge Image Studio (`NanoBananaImageAgent`), counselors clicking to generate an illustration for *"Requirement 2b: Demonstrate direct pressure and tourniquet application"* received an image that rendered a literal PowerPoint slide mockup containing the words *"Create a slide illustration for Requirement 2b..."* inside the artwork.
- **Root cause**: Passing raw slide metadata (`Requirement 2b`, `Create a slide image...`, `16:9 slide graphic`) into `gemini-2.5-flash-image` triggered the model's typography/poster prior rather than its pure visual illustration prior.
- **Architectural fix**:
  1. Built `build_clean_illustration_prompt()` and `resolve_content_aware_visual_config()` (`src/agents/image_studio.py`) to strip all requirement numbers (`Req 2b`) and meta-instructional phrasing before calling the image generator, replacing them with explicit subject-plus-style descriptors across 10 UI visual styles (`8` artistic styles + `Auto (Content-Aware Mix)` + `4-Quadrant Concept Map`, plus 4 legacy aliases: `Photorealistic Image`, `4-Quadrant Concept Map`, `Watercolor Field Sketch`, `Line Drawing`, `Cartoon Drawing`, `Technical Diagram`, `3D Isometric Illustration`, `Editorial Vector Illustration`, and `Vintage Merit Badge Poster`), explicit human/uniform vs. zero-human directives (`include_humans`), and negative text constraints (`zero words, zero letters, zero slide frames`).
  2. Added a post-generation multimodal verification gate, `verify_generated_image_matches_prompt()`, which inspects the generated PNG to verify both semantic subject alignment (`alignment_score >= 0.70`) and zero rendered prompt text before returning the image to the counselor.

### 10.2 Post-mortem #2: Dense vector dilution on alphanumeric BSA requirement identifiers
- **Symptom observed**: When querying the pamphlet memory store for specific sub-requirements (such as *"Requirement 9a weather instrument"* vs. *"Requirement 9b outdoor camping nights"*), pure dense cosine similarity occasionally ranked general narrative paragraphs above the exact numbered requirement chunk.
- **Root cause**: Compact dense embeddings compress semantics across the entire sentence and underweight short alphanumeric tokens (`1a`, `2b`, `9a`).
- **Architectural fix**: Upgraded `PersistentSessionStore` (`src/memory/session_store.py`) to execute **Hybrid Search via Reciprocal Rank Fusion (`hybrid_search_pamphlet_rrf_sync`)**, combining dense cosine similarity ranks ($r_{\text{dense}}$) with Okapi BM25 lexical ranks ($r_{\text{bm25}}$) and an explicit alphanumeric requirement-marker boost ($k=60$). This raised `Recall@3`, `MRR`, and `NDCG@3` on `scripts/eval_gate.py` to **`1.0000`**.

### 10.3 Post-mortem #3: Vertex AI `400 INVALID_ARGUMENT` when combining `GoogleSearchTool` and custom `FunctionTool`s
- **Symptom observed**: Attaching both ADK's built-in `google_search` tool and our custom `fetch_merit_badge_pamphlet_pdf` `FunctionTool` to `PamphletResearchAgent` caused Vertex AI to reject requests with `400 INVALID_ARGUMENT: Built-in tools and function declarations cannot be combined in the same request`.
- **Root cause**: The Gemini API enforces strict separation between Google-hosted grounding tools (`google_search`) and user-defined tool declarations within a single model turn.
- **Architectural fix**: Isolated `google_search` inside a dedicated sub-agent (`WebSearchGroundingAgent` on `gemini-2.5-flash`) and wrapped that sub-agent using ADK's `AgentTool` (`src/agents/researcher.py`). To the parent `PamphletResearchAgent`, `WebSearchGroundingAgent` appears as a standard callable tool while executing its grounded search in an isolated model context.

### 10.4 Closed-loop continuous learning pipeline (`promote_session_to_golden_dataset`)
Every production counselor session feeds a continuous improvement loop:
1. **Capture**: Counselor thumbs-up/down ratings (`POST /api/v1/feedback`), single-slide regenerations (`POST /api/v1/slide/regenerate`), and Stage 1/2 conformance diagnostics are logged to SQLite (`hitl_feedback`) and `deliverables/counselor_hitl_feedback.jsonl` (`RuntimeMetricsCollector.record_counselor_feedback` in `src/resilience.py`).
2. **Promote**: `promote_session_to_golden_dataset()` (`scripts/eval_gate.py`) promotes any counselor-verified (`rating >= 4` and `requirement_accuracy_verified=True`) session trace into `tests/data/golden_extensions.json`, recording the badge name, expected requirement count, and expected 7-agent execution trajectory.
3. **Gate**: `scripts/eval_gate.py` and `tests/eval_golden_suite.py` run automatically in CI/CD (`cloudbuild.yaml`), checking IR retrieval (`MRR >= 0.85`), requirement recall (`>= 0.98`), trajectory in-order match (`>= 0.95`), citation grounding coverage (`>= 0.95`), and Stage 1 geometry (`0` AABB overlaps) before any container revision can deploy to Cloud Run.
