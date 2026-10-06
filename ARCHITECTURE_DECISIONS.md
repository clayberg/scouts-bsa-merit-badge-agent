# Architecture decision records (ADRs)

This file records the eight main engineering decisions behind the Scouts BSA Merit Badge Counselor Workbench, the options we evaluated, and the trade-offs we accepted.

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
  3. *Two-stage conformance check (`check_pptx_conformance` + `run_stage2_vision_critique`) (Chosen)*: Stage 1 inspects `python-pptx` shape coordinates in memory in under 10ms at `$0.00` token cost, checking Axis-Aligned Bounding Box (AABB) intersections, a `13.0pt` minimum font size, `4.5:1` WCAG contrast, and SHA-256 image uniqueness. Stage 2 runs curriculum and visual checks only after Stage 1 geometry passes.
- **Trade-off accepted**: Required writing custom bounding-box and font-fitting math (`_compute_fitting_font_size()`), which catches 100% of shape overlaps in milliseconds.

---

## ADR-04: Pre-LLM PII scrubbing + environment-isolated counselor profile cache vs. passing counselor contact info in prompts or shared DBs
- **Problem**: Counselors want their name, troop, location, email, and phone number remembered across sessions and printed on Slide 1 (Cover), the Lesson Plan, and the Parent Prerequisite Letter, but Youth Protection and privacy rules forbid sending personal contact details to external model logs, Cloud Trace spans, or shared multi-tenant databases.
- **Options considered**:
  1. *Include counselor contact info in LLM prompts and store it in shared SQLite tables*: Simple, but leaks emails and phone numbers to external model payloads and across tenants in Cloud Run.
  2. *Force counselors to re-type contact info on every run*: Safe, but frustrating for volunteer counselors generating multiple badges.
  3. *Environment-isolated counselor caching + Pre-LLM scrubbing in `before_model_guardrail_callback()` + local template injection (Chosen)*: On a local laptop, counselor details are cached in a git-ignored `.cache/counselor_profile.json` file with `0600` owner-only permissions. In multi-tenant Cloud Run (`K_SERVICE` / `IS_CLOUD_RUN=true`), server-side disk caching is disabled and contact info is stored only in the counselor's browser `localStorage` (`scouts_bsa_counselor_profile_v1`). During execution, `scrub_pii_before_sink()` redacts emails, phone numbers, and SSNs before Gemini is called and before SQLite/OpenTelemetry writes, while `pptx_builder.py` and `counselor_studiokit.py` inject the contact fields locally into Slide 1 and the Parent Letter.
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

## ADR-06: Three visual polish tiers + EDGE Skill Concept Maps governed by `FinOpsBudgetPlugin` (`$1.00` cap)
- **Problem**: Some counselors want a plain white slide deck for a quick troop meeting (`$0.14`), while others teaching a weekend Merit Badge clinic want warm NotebookLM-style cards (`$0.38`) or a dark executive slate theme (`$1.00`).
- **Options considered**:
  1. *Generate an AI image for every slide in every deck*: A 65-slide Deep Dive deck would exceed `$2.60` and overwrite helpful technical diagrams.
  2. *Plain white slides only*: Cheap, but visually flat for middle-school and high-school Scouts.
  3. *Three selectable tiers (`STANDARD`, `BEAUTIFIED`, `STUDIO`) + EDGE Skill Concept Maps + `FinOpsBudgetPlugin(max_budget_usd=1.00)` (Chosen)*: `STANDARD` uses a clean white wireframe with zero generated concept maps; `BEAUTIFIED` uses a warm cream canvas (`#FAF8F5`) with rotating accent palettes and up to 5 Scouts BSA EDGE Skill Concept Maps on requirement intro slides; `STUDIO` uses a dark slate canvas (`#0F172A`) with up to 15 dark-slate EDGE Skill Concept Maps while never overwriting existing pamphlet figures or technical diagrams.
- **Trade-off accepted**: Preserves all technical diagrams and keeps every run under the `$1.00` budget cap, automatically downgrading `STUDIO` to `BEAUTIFIED` if a custom budget cap is set lower.

---

## ADR-07: Per-badge image catalog caching, original graphic preservation, local file upload, and `$0.08` FinOps consent gate for `NanoBananaImageAgent`
- **Problem**: Counselors need to manage slide visuals (removing a graphic so text expands to full width, restoring a slide's original illustration after experimenting, finding real-world photos via web search, uploading their own local troop photos, or generating custom AI visuals) without losing earlier graphics or incurring unexpected AI image charges.
- **Options considered**:
  1. *Overwrite `diagram_path` in place and generate AI images immediately on dropdown change*: Destroys the slide's original graphic and charges `$0.08/image` without warning the user.
  2. *Static read-only slide graphics*: Prevents unexpected charges, but gives counselors no way to customize visuals or switch between candidate graphics.
  3. *Immutable `original_diagram_path` snapshot + `badge_image_catalog` SQLite/disk cache + local `USER_UPLOAD` + explicit `user_consented=True` FinOps gate on `NanoBananaImageAgent` (Chosen)*: Every slide snapshots its initial graphic (`original_diagram_path`, `original_archetype`) so "Restore Original Slide Graphic" always works in one click. Setting the right-side graphic to `None` clears the graphic and switches `SPLIT_VISUAL_EXPLAINER` to `CONCEPT_TEXT_SLIDE` (`12.133"` full-width text). All images discovered by `WebImageSearchAgent` (up to 12 live Wikimedia Commons photos), uploaded locally via `upload_custom_slide_image()` (`USER_UPLOAD`, `$0.00 USD`), or created by `NanoBananaImageAgent` across 8 visual styles are cached per badge in `assets/badge_image_catalog/<badge_slug>/` and SQLite (`badge_image_catalog`). Counselors can clear web/AI cache entries at any time via `clear_generated_and_cached_badge_images()` without losing pamphlet figures or local uploads, and `NanoBananaImageAgent` displays an upfront `$0.08 USD` cost estimate, requires explicit user consent (`user_consented=True`), and runs `verify_generated_image_matches_prompt()` before returning.
- **Trade-off accepted**: Adds a confirmation step and alignment check for custom AI image generation, ensuring complete cost transparency, prompt accuracy, and reusable per-badge image libraries.

---

## ADR-08: Environment-aware authentication (`AUTH_REQUIRED`) + circuit-breaker model fallback
- **Problem**: The workbench runs both as a local laptop tool (`./run_local.sh`) at summer camp and as a containerized Cloud Run service behind a load balancer.
- **Options considered**:
  1. *Require OIDC JWT headers in all environments*: Breaks local laptop use for volunteer counselors.
  2. *Leave Cloud Run unauthenticated*: Exposes cloud endpoints to quota abuse.
  3. *Environment-aware `verify_caller_auth` (`src/security.py`) + `CircuitBreaker` / `ModelFallbackRouter` (`src/resilience.py`) (Chosen)*: Enforces `X-API-Key` or `Bearer` JWT checks and internal load-balancer ingress in Cloud Run (`AUTH_REQUIRED=true`), while defaulting to `AUTH_REQUIRED=false` on `localhost`. If Vertex AI returns `429` or `503`, `ModelFallbackRouter` falls back from `gemini-2.5-pro` to `gemini-2.5-flash` to the local deterministic curriculum engine.
- **Trade-off accepted**: Requires setting `AUTH_REQUIRED=true` in production (`terraform/main.tf` sets this by default).
