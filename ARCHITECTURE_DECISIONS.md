# Architecture Decision Records (`ARCHITECTURE_DECISIONS.md`)

This document records the core architectural decisions behind the **Scouts BSA Merit Badge Counselor Workbench** (`v2.6`). For the complete system design, data contracts, and sequence diagrams, see [`docs/TDD.md`](docs/TDD.md).

---

## ADR-001: Google ADK 8-Agent Hierarchy & Strategic Model Routing

### Context
Generating a 45 to 85+ slide Merit Badge instructional package with a matched Counselor Guide, Scout Workbook, Multi-Format Session Pacing Agenda, and Prerequisite Parent Letter requires distinct capabilities: verbatim PDF/JSON curriculum ingestion, pedagogical structuring (BSA EDGE method: Explain, Demonstrate, Guide, Enable), visual layout synthesis, and geometric quality assurance. Running a single monolithic prompt causes context window dilution, high latency, and inflated token costs.

### Decision
We implemented a hierarchical **Coordinator + 7 Specialist Sub-Agents** topology using the **Google Agent Development Kit (`google-adk`)** (`src/agents/__init__.py`, `src/agents/coordinator.py`):
1. `MeritBadgeCoordinator` (`gemini-2.5-pro`): Root orchestrator managing session state, FinOps budget checks, and self-healing retries.
2. `ResearcherAgent` (`gemini-2.5-flash`): Executes the 5-Tier Deep Research pipeline across all `144` official Merit Badges (`data/merit_badge_requirements/*.json`) and `134` local PDF pamphlets (`pdfs/`).
3. `CurriculumPlannerAgent` (`gemini-2.5-pro`): Performs execution-mode triage (`IN_CLASS_DISCUSSION`, `HANDS_ON_SKILL_STATION`, `PREREQUISITE_CAMPOUT_HOME`) and builds the 12-archetype storyboard and EDGE speaker notes.
4. `SlideGeneratorAgent` (`gemini-2.5-flash`): Renders deterministic `13.333" x 7.5"` widescreen `.pptx` decks (`src/tools/pptx_builder.py`) with 1:1 HTML5 preview parity (`ui/app.js`).
5. `BeautifierAgent` (`gemini-2.5-flash`): Applies the 3 visual polish tiers (`STANDARD`, `BEAUTIFIED`, `STUDIO`), 4 rotating card accent palettes, and pre-cached hero/topic visuals.
6. `WebImageSearchAgent` (`gemini-2.5-flash`): Queries Wikimedia Commons and public educational repositories with local caching (`assets/badge_image_catalog/`).
7. `NanoBananaImageAgent` (`gemini-2.5-flash` + Imagen / Gemini image generation): Generates custom educational illustrations on demand, gated by an explicit `$0.08` USD FinOps user consent check (`src/agents/image_studio.py`).
8. `QualityReviewerAgent` (`gemini-2.5-pro`): Runs the Stage 1 (`<10ms`) deterministic AABB geometry conformance simulator and citation grounding verifier (`src/agents/reviewer.py`).

### Consequences
- Routing 75%+ of high-volume extraction and formatting calls to `gemini-2.5-flash` while reserving `gemini-2.5-pro` for curriculum planning and quality review reduces per-deck LLM token cost by **71%** (`~$0.042` to `$0.14` per deck).

---

## ADR-002: Canonical Pamphlet SHA-256 Lock & Hybrid BM25 + Vector RRF Retrieval

### Context
Scouts BSA Merit Badge counselors must teach the exact, current Scouting America requirements without omitted sub-requirements (`1a..15c`) or hallucinated policy rules. Pure dense vector search often misses exact requirement alphanumeric codes (such as `"Requirement 4b"` or `"Blue Card #34124"`).

### Decision
1. **Complete 144-Badge Structured Corpus & SHA-256 Lock**: All `144` official Merit Badges (`18` Eagle-Required and `126` Electives) are stored in `data/merit_badge_requirements/*.json` with verbatim requirement trees, multi-slide `topic_slides`, and SHA-256 integrity hashes (`compute_canonical_pamphlet_hash` in `src/agents/researcher.py`).
2. **Hybrid RRF Search (`src/memory/session_store.py`)**: `PersistentSessionStore.hybrid_search_pamphlet_rrf_sync` combines **Dense Cosine Similarity** (`text-embedding-004`, 768-dim) with **Okapi BM25 Lexical Scoring** (`k1 = 1.5, b = 0.75`) via **Reciprocal Rank Fusion (`k = 60`)**.

### Consequences
- Exact requirement IDs (`1a`, `2b`, `6c`) rank in the top retrieval slots while preserving semantic matching for conceptual queries.

---

## ADR-003: Two-Stage PPTX Conformance Gate (`<10ms` AABB Simulator + Vision Critique)

### Context
LLM-generated slide decks frequently suffer from overlapping text boxes, overflowing cards when imported into Google Slides, and tiny unreadable fonts. Running multimodal vision inspection on every slide of an 83-slide deck on every pass is slow and expensive.

### Decision
We implemented a **Two-Stage Conformance Gate** (`src/agents/reviewer.py`):
- **Stage 1 (`check_pptx_conformance`, `<10ms`, `$0.00`)**: Parses the generated `.pptx` in memory via `python-pptx`, computes Axis-Aligned Bounding Boxes (AABB) for all slide shapes (ignoring intentional layered card accents `CardAccent_*`), verifies `0` overlaps, checks `13.333" x 7.5"` canvas bounds, enforces a `>= 12pt` body font floor, and checks `_concise_card_body` character budgets (`<= 18` words, `<= 125` chars per card body).
- **Stage 2 (`inspect_slide_image_with_vision`, optional)**: Invokes `gemini-2.5-pro` multimodal vision only on flagged slides or during deep visual audits.

### Consequences
- All `72` pre-built benchmark and sample decks (`deliverables/benchmark_and_random_samples/`) pass with `0` AABB overlaps and clean Google Slides import fidelity.

---

## ADR-004: Pre-Cached Multimodal Visual Asset Pipeline (`2,292` Nano Banana PNGs + `4,316` De-Boxed Figures)

### Context
Generating 20 to 50 custom AI illustrations live during a Merit Badge class prep session would take several minutes and cost `$1.60+` per deck. Conversely, raw XObject images extracted from PDF pamphlets frequently contain baked-in black/blue caption boxes, dithered low-resolution scans, or redundant titles that clash with slide headers.

### Decision
1. **100% Pre-Cached Visual Catalog (`Option 2` Full Visual Pipeline)**:
   - Pre-generated and compressed (`<= 1,024px`, 8-bit PNG) **`2,292` Nano Banana hero and multi-slide topic illustrations** (`assets/ai_illustrations/`) covering every requirement across all `144` official Merit Badges (`$0.00` runtime image cost).
   - Extracted and de-boxed **`4,316` official BSA Pamphlet figures** (`assets/pamphlet_images/`), automatically stripping dark caption bars (`_strip_pamphlet_caption_box` in `src/tools/pptx_builder.py`).
   - Upgraded key scientific and meteorological diagrams with **high-resolution embedded-text diagrams** (Hydrologic Cycle, WSR-88D Doppler Radar, Cold/Warm Front cross-sections, 3D Warm Front side-by-side profile, Sea/Land Breezes, Cloud Classification by Altitude Level, and top-cropped Earth's 23.5° Axial Tilt & Seasons) and replaced generic `"Official BSA Pamphlet"` prefixes with concise, scene-specific captions.
2. **FinOps-Gated On-Demand Studio**: When a counselor wants a custom AI illustration in the **4-Tab Merit Badge Image Studio**, `NanoBananaImageAgent` returns `CONSENT_REQUIRED` until the user explicitly approves the `$0.08` USD FinOps estimate.

### Consequences
- Standard and Deep Dive decks for all `144` badges render immediately at `$0.00` image generation cost while giving counselors full per-slide visual control.

---

## ADR-005: Dual-Layer Youth Protection (YPT) PII Scrubbing & Model Armor Guardrails

### Context
Merit Badge counselors often paste roster notes or emails containing youth names, phone numbers, or troop details. Scouting America Youth Protection guidelines require strict protection of youth data.

### Decision
We implemented a dual-layer security pipeline (`src/pii_scrubber.py`, `src/agents/guardrails.py`):
- **Pre-LLM Input & Post-LLM Output Scrubbing**: Redacts emails, phone numbers, SSNs, street addresses, and `Scout <First> <Last>` patterns before prompts reach Vertex AI or get written to SQLite or OpenTelemetry traces.
- **Model Armor Prompt-Injection Interception**: Blocks jailbreak patterns, system-prompt extraction attempts, and YPT bypass payloads (`allowed = False`).

### Consequences
- Verified `0` PII leaks across all `53` automated `pytest` tests and the 12-badge Golden Evaluation Gate.
