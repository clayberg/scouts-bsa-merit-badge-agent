# FDE Capstone Companion Guide: Scouts BSA Merit Badge Counselor Workbench (`v2.6`)

This companion guide provides an engineering walkthrough of the **Scouts BSA Merit Badge Counselor Workbench** across all five AgentOps and Forward Deployed Engineering (FDE) architectural pillars, linking directly to the repository's source modules, automated tests, and operational scripts.

---

## 1. At-a-Glance System Inventory

| Engineering Dimension | Verified Repository Implementation |
| :--- | :--- |
| **Official Merit Badge Catalog** | **All `144` Official Scouts BSA Merit Badges** (`18` Eagle-Required + `126` Electives in `data/merit_badge_requirements/*.json`, plus `2` synthetic test stubs in the catalog selector). |
| **Pre-Cached Multimodal Visuals** | **`2,297` Pre-Generated, Compressed (`<= 1,024px`, 8-bit PNG) Nano Banana Hero & Topic Illustrations** (`assets/ai_illustrations/`) + **`4,317` Extracted & De-Boxed Official Pamphlet Figures** (`assets/pamphlet_images/`) + **`135` Transparent RGBA Badge Emblems** (`assets/badge_emblems/`) + **`134` Official Pamphlet Covers** (`assets/pamphlet_covers/`). |
| **Runtime Visual Cost** | **`$0.00` USD** for all pre-cached `STANDARD`, `BEAUTIFIED`, and `STUDIO` decks across all `144` badges; **`$0.08` USD** explicit FinOps user consent gate (`CONSENT_REQUIRED`) only when a counselor requests a brand-new custom AI image in Tab 3 of the Image Studio. |
| **Multi-Agent Topology (`google-adk`)** | **`MeritBadgeCoordinator`** (`gemini-2.5-pro`) orchestrating **7 Specialist Sub-Agents** (`ResearcherAgent`, `CurriculumPlannerAgent`, `SlideGeneratorAgent`, `BeautifierAgent`, `WebImageSearchAgent`, `NanoBananaImageAgent`, `QualityReviewerAgent`). |
| **Pre-Built & Audited Decks** | **`72` Verified `.pptx` Decks** (`26` Benchmark Badges + `10` Random Electives across *Deep Dive* and *Troop Meeting* modes in `deliverables/benchmark_and_random_samples/`) passing `100%` of Stage 1 (`<10ms`) AABB geometry and citation checks. |
| **Automated Test & Eval Coverage** | **`53` Non-Hollow `pytest` Tests** across 5 test suites + **12-Badge Golden Evaluation Gate** (`scripts/eval_gate.py`) + **6-Act Pre-Flight Live Demo Check** (`scripts/verify_live_demo_readiness.py`). |

---

## 2. Pillar-by-Pillar Codebase Mapping

### Pillar 1: Tool & Interface Design
- **Comprehensive Tool Docstrings &LLM Usage Guidance**: Every tool in `src/tools/scouting_scraper.py`, `src/tools/pamphlet_extractor.py`, `src/tools/diagram_generator.py`, `src/tools/pptx_builder.py`, and `src/mcp_server.py` documents its purpose, parameters, return contract, and recovery behavior.
- **Explicit Pydantic v2 JSON Schemas**: Strict request/response models (`MeritBadgeResearchRequest`, `SlideRegenerateRequest`, `NanoBananaGenerateRequest`, `CounselorFeedbackRequest`, `StudioKitAgendaRequest`) with `Field(...)` constraints and validators.
- **Guided Error Handling**: Structured error envelopes (`status: "ERROR"`, `error_code`, `recovery_suggestion`) enable autonomous agent self-correction without unhandled tracebacks.
- **Standardized Interoperability**:
  - **FastMCP Server (`src/mcp_server.py`)**: Cryptographic HMAC-SHA256 HITL `confirmation_token` verification.
  - **A2A 1.0 Discovery (`GET /.well-known/agent.json`, `POST /a2a/tasks/send`)** & **A2UI v0.9 Envelopes (`beginRendering`, `surfaceUpdate`, `dataModelUpdate`)** in `src/server.py`.

### Pillar 2: Context, Memory & Hybrid RAG
- **Canonical Pamphlet SHA-256 Fidelity Lock (`src/agents/researcher.py`)**: `compute_canonical_pamphlet_hash` locks verbatim Scouting America requirements (`1a..15c`) across all `144` Merit Badges so no sub-requirement can be silently altered or dropped.
- **Hybrid Dense + Okapi BM25 Retrieval via RRF (`src/memory/session_store.py`)**: `hybrid_search_pamphlet_rrf_sync` fuses `text-embedding-004` cosine similarity with Okapi BM25 (`k1 = 1.5, b = 0.75`) via Reciprocal Rank Fusion (`k = 60`).
- **Context Compaction & Vertex AI Context Caching**: Sliding-window event compaction (`compact_conversation_history`) and Vertex AI Context Caching (`create_vertex_context_cache_spec`, `75%` input token discount) keep long Deep Dive runs fast and economical.
- **Async & Local Counselor Profile Persistence**: `aiosqlite` WAL session store (`PersistentSessionStore`) paired with local counselor profile caching (`save_local_counselor_profile`, `load_local_counselor_profile`).

### Pillar 3: Orchestration, Guardrails & Visual Co-Design
- **8-Agent ADK Hierarchy & Strategic Model Routing (`src/agents/coordinator.py`)**: Routes high-volume extraction and layout work (`~78%` of calls) to `gemini-2.5-flash` (`~$0.042-$0.14` per deck) while reserving `gemini-2.5-pro` for curriculum planning and quality review.
- **Two-Stage PPTX Conformance Gate (`src/agents/reviewer.py`)**:
  - **Stage 1 (`<10ms` Deterministic Simulator)**: `check_pptx_conformance` verifies `0` AABB shape overlaps, `13.333" x 7.5"` widescreen bounds, and `>= 12pt` font floors.
  - **Stage 2 (Multimodal Vision Critique)**: `inspect_slide_image_with_vision` checks visual balance and contrast on flagged slides, triggering up to `MAX_CONFORMANCE_RETRIES = 2` self-healing passes.
- **High-Resolution Scientific Diagrams & 4-Tab Image Studio (`src/agents/image_studio.py`)**:
  - High-resolution embedded-text diagrams (Hydrologic Cycle, WSR-88D Doppler Radar, Cold/Warm Front cross-sections, 3D Warm Front profile, Sea/Land Breezes, Cloud Classification by Altitude Level, and cropped Earth's 23.5° Axial Tilt & Seasons) with concise, scene-specific captions.
  - Explicit `$0.08` USD FinOps consent gate (`CONSENT_REQUIRED`) on Tab 3 custom AI image generation.

### Pillar 4: Observability, Tracing & Youth Protection (YPT)
- **Dual-Layer Youth Protection PII Scrubbing (`src/pii_scrubber.py`)**: Redacts youth names (`Scout <First> <Last>`), phone numbers, emails, SSNs, and street addresses before any LLM call, SQLite write, or telemetry export.
- **Model Armor Prompt-Injection Defense (`src/agents/guardrails.py`)**: `sanitize_text_with_model_armor` intercepts jailbreak and YPT-bypass payloads on both input and output paths.
- **Structured JSON Logging & OpenTelemetry Tracing (`src/logger.py`, `src/telemetry.py`)**: Captures `intent` vs. `outcome`, token counts, latency, and FinOps cost across every agent span.

### Pillar 5: Infrastructure, Resilience & Continuous Learning Flywheel
- **Stateful Circuit Breaker & Model Fallback (`src/resilience.py`)**: 3-state `CircuitBreaker` (`CLOSED` -> `OPEN` -> `HALF_OPEN`) with exponential backoff and automatic fallback from `gemini-2.5-pro` to `gemini-2.5-flash` or deterministic pre-cached JSON synthesis.
- **Counselor Feedback Flywheel (`POST /api/v1/feedback`)**: Persists counselor ratings to SQLite and automatically promotes verified 4-5 star runs into `tests/data/golden_extensions.json`.
- **Terraform IaC & Secret Manager (`terraform/main.tf`, `src/secrets.py`)**: Provisions Cloud Run, Artifact Registry, least-privilege IAM, and Google Secret Manager bindings.
