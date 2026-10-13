# API & Interoperability Integration Guide (`v1.2.0`)

This guide documents the HTTP REST endpoints, **Agent-to-Agent (A2A 1.0)** discovery protocol, **Agent-to-UI (A2UI v0.9)** surface envelopes, and **Model Context Protocol (FastMCP)** tools exposed by `src/server.py` and `src/mcp_server.py`.

---

## 1. API Versioning & Deprecation Policy

- **Versioned Endpoints (`/api/v1/*`)**: All primary endpoints are served under `/api/v1/*` and return the response header `X-API-Version: 1.2.0`.
- **Legacy Alias Routes (`/api/*`)**: Retained for backward compatibility and emit standard RFC 8594 headers (`Deprecation: true`, `Sunset: Wed, 31 Dec 2026 23:59:59 GMT`, `X-API-Version: 1.2.0`).

---

## 2. Core REST Endpoints (`src/server.py`)

### Health & Readiness Probes
- **`GET /health` & `GET /api/v1/health`**:
  - Liveness probe returning `{"status": "ok", "version": "1.2.0"}`.
- **`GET /readiness` & `GET /api/v1/readiness`**:
  - Deep subsystem readiness check verifying SQLite WAL accessibility, Vertex AI circuit breaker state (`CLOSED`), and the full `144`-badge catalog (`catalog_len >= 144`).

### Merit Badge Catalog & Visual Assets
- **`GET /api/v1/badges` (alias: `GET /api/badges`)**:
  - Returns all **144 official Scouts BSA Merit Badges** (`18` Eagle-Required and `126` Electives, plus `2` synthetic test stubs when validation mode is queried), organized across 8 category filters, along with official pamphlet PDF URLs, Scoutbook links, and local pre-cached visual counts.
- **`GET /api/badge/images?badge_name=<Badge>`**:
  - Lists all cached visual assets for the specified badge across `NANO_BANANA_HERO` (`2,297` pre-cached 8-bit PNGs across all `144` badges), `PAMPHLET_FIGURE` (`4,317` de-boxed official figures), `WEB_IMAGE_SEARCH`, `NANO_BANANA_AI`, and `USER_UPLOAD`.
- **`DELETE /api/badge/images?badge_name=<Badge>` & `GET /api/v1/cache/clear?badge_name=<Badge>`**:
  - Purges ephemeral web-search and custom AI-generated images for the badge while preserving pre-cached `NANO_BANANA_HERO`, `PAMPHLET_FIGURE`, and `USER_UPLOAD` assets.

### Multi-Agent Curriculum & Slide Deck Workflow
- **`POST /api/v1/workflow/run` (alias: `POST /api/workflow/run`)**:
  - Executes `run_merit_badge_workflow` across the 8-agent ADK pipeline (`MeritBadgeCoordinator` -> `ResearcherAgent` -> `CurriculumPlannerAgent` -> `BeautifierAgent` -> `SlideGeneratorAgent` -> `QualityReviewerAgent`).
  - **Request Payload**:
    ```json
    {
      "badge_name": "Weather",
      "depth_mode": "Deep Dive / Camp School Deck",
      "beautification_tier": "BEAUTIFIED",
      "enable_deep_research": true,
      "audience_level": "All Scouts (Ages 11-17)",
      "counselor_name": "Eric Clayberg",
      "troop_affiliation": "Troop 19, Middleton MA",
      "location_or_zip": "01949",
      "email_address": "clayberg@gmail.com",
      "phone_number": "(978) 555-0119"
    }
    ```
  - **Response**: Returns `storyboard` (`slides`, `requirements`), `output_path` (`.pptx`), `conformance_report` (`aabb_overlap_count: 0`), `session_agenda`, `prerequisite_parent_letter`, `workbook_markdown`, `counselor_guide_markdown`, `finops_telemetry`, `hitl_confirmation_token`, and `a2ui_messages`.

### Surgical Single-Slide Co-Design & 4-Tab Image Studio
- **`POST /api/slide/regenerate`**:
  - Updates a single slide's layout archetype, card style (`MODERN_CARDS`, `NUMBERED_STEP_CARDS`, `WARNING_CALLOUT`, `CHECKLIST_CARDS`), color palette (`NAVY_GOLD`, `FOREST_SAGE`, `CRIMSON_EMBER`, `SLATE_CYAN`), inline edited title/bullets, or graphic visibility (`keep`, `none`, `restore_original`) and rebuilds the `.pptx` in place.
- **`POST /api/slide/search-web-images`**:
  - Invokes `WebImageSearchAgent` to search Wikimedia Commons for educational diagrams or photographs (`$0.00` USD).
- **`POST /api/slide/estimate-image-cost`**:
  - Pre-flight FinOps estimator for `NanoBananaImageAgent` returning `{"estimated_cost_usd": 0.08, "requires_user_consent": true}`.
- **`POST /api/slide/generate-nano-banana-image`**:
  - Invokes `NanoBananaImageAgent`. Returns `{"status": "CONSENT_REQUIRED"}` if `user_consented` is `false`. When `user_consented` is `true`, generates the custom illustration, runs multimodal prompt-alignment verification (`verify_generated_image_matches_prompt`), and saves the PNG to the badge catalog.
- **`POST /api/slide/upload-image`**:
  - Saves a counselor-uploaded PNG/JPG/WebP image (`USER_UPLOAD`, `$0.00` USD) to the badge catalog.

### StudioKit Session Pacing & Continuous Learning Flywheel
- **`POST /api/studiokit/agenda`**:
  - Dynamically re-paces a badge's requirements across 4 schedules: `3 Troop Meetings (60-Min)`, `Summer Camp Week (4x50-Min Mon-Thu + Fri Sign-Off)`, `Saturday Merit Badge Clinic (3-Hr Block)`, or `Weekend Campout Practicum`.
- **`POST /api/v1/feedback`**:
  - Records counselor star ratings (`1-5`) and requirement accuracy sign-off in SQLite (`counselor_feedback`). Runs rated `>= 4` stars with `requirement_accuracy_verified: true` are automatically promoted into `tests/data/golden_extensions.json`.

---

## 3. Agent-to-Agent (`A2A 1.0`) & Agent-to-UI (`A2UI v0.9`) Protocols

- **Agent Card Discovery (`GET /.well-known/agent.json`)**:
  - Advertises `protocolVersion: "1.0"`, `capabilities.a2uiProtocolVersion: "v0.9"`, input/output schemas, and supported skills across all `144` official Merit Badges.
- **Task Execution (`POST /a2a/tasks/send`)**:
  - Accepts standard A2A task envelopes (`sessionId`, `message.parts`, `metadata`) and returns completed artifacts (`pptx_deck`, `counselor_guide`, `scout_workbook`) plus `a2ui_messages` (`beginRendering`, `surfaceUpdate`, `dataModelUpdate`).

---

## 4. Model Context Protocol (`FastMCP`) Server (`src/mcp_server.py`)

Run `python -m src.mcp_server` to expose the workbench tools over stdio or SSE to any MCP-compatible client:
- `research_merit_badge(badge_name, location_or_zip)`
- `generate_merit_badge_deck(badge_name, depth_mode, beautification_tier, confirmation_token)`
- `audit_pptx_conformance(pptx_path)`
- `issue_hitl_confirmation_token(action_name, badge_name, estimated_cost_usd)`
