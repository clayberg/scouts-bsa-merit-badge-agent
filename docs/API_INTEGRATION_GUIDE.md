# API and integration guide (`OpenAPI 3.1`, `MCP 2024-11-05`, `A2A 1.0`, and `SSE`)

The FastAPI server (`src/server.py`) serves the Material 3 web workbench (`/`), versioned REST endpoints (`/api/v1/*`), legacy unversioned aliases (`/api/*` with RFC 8594 `Deprecation: true` and `Sunset: 2027-01-01` headers), PowerPoint Template & Custom Slide Theme Engine endpoints (`/api/v1/templates*`), Multi-Badge Saved Deck Workspaces & Starred Favorites endpoints (`/api/v1/workspaces*`, `/api/v1/badges/favorites*`), Official Scouts BSA Workbench Model Context Protocol (`MCP`) endpoints (`POST /mcp`, `GET /mcp/info`, `GET /mcp/sse`, documented in the **[MCP Server Integration Guide](MCP_SERVER_INTEGRATION_GUIDE.md)**), Merit Badge Image Studio endpoints (`/api/v1/badge/images`, `/api/v1/slide/*`), in-app documentation endpoints (`/api/v1/docs`, `/api/v1/docs/{doc_id}`), Super-User Admin Console and Zero-PII Telemetry endpoints (`/api/v1/admin/*`, documented in [`docs/ADMIN_GUIDE.md`](ADMIN_GUIDE.md)), counselor profile persistence (`/api/v1/counselor-profile`), Server-Sent Events (`/api/v1/workflow/stream`), Agent-to-Agent (`A2A 1.0`) task routes (`/a2a/*`), and container health checks (`/health`, `/readiness`).

- **OpenAPI 3.1 schema (`119` paths)**: [`docs/openapi.yaml`](openapi.yaml), exported by `scripts/export_openapi.py` and verified in `tests/test_resilience_and_fault_injection.py` and `tests/test_conformance_and_a2ui.py`.
- **MCP Server Integration Guide (`12` Tools, `6` `bsa://` Resources, `4` Prompts)**: [`docs/MCP_SERVER_INTEGRATION_GUIDE.md`](MCP_SERVER_INTEGRATION_GUIDE.md) (`python -m src.mcp_server` / `scouts-bsa-mcp` stdio CLI + HTTP `/mcp` & `/mcp/sse`).
- **Swagger UI**: `http://localhost:8085/docs`
- **A2A 1.0 Agent Card**: `http://localhost:8085/.well-known/agent.json`

---

## 1. Authentication headers

Authentication is controlled by `AUTH_REQUIRED` (`false` by default on `localhost`; `true` in Cloud Run):
- **API key header**: `X-API-Key: <your-bsa-api-key>`
- **OIDC / Bearer token header**: `Authorization: Bearer <OIDC_JWT>`
- **Super-User Admin session cookie**: `bsa_admin_session` (`HttpOnly`, `SameSite=Lax`, issued by `POST /api/v1/admin/unlock`) or `X-Admin-Token: <ADMIN_SUPERUSER_TOKEN>`

Every HTTP response includes `X-API-Version: 1.2.0`. Calls to unversioned `/api/*` paths also return `Deprecation: true` and `Sunset: 2027-01-01`.

---

## 2. Endpoint summary (`119` OpenAPI 3.1 paths)

All `/api/v1/*` routes below also expose backward-compatible `/api/*` aliases in `docs/openapi.yaml`.

### 2.1 Core workbench, curriculum workflow, templates, workspaces, and documentation endpoints

| Method and path | Purpose | Auth required in prod |
| :--- | :--- | :--- |
| `GET /` | Serves the Material 3 Expressive Counselor Workbench (`ui/index.html`). | No |
| `GET /health`, `GET /api/v1/health` | Container liveness check (`{"status": "UP", "version": "3.1.0"}`). | No (Cloud Run probe) |
| `GET /readiness` | Deep readiness check for SQLite session store, 144-badge catalog, FinOps and Model Armor policy JSON files, and circuit breakers. | No (Cloud Run probe) |
| `GET /api/v1/badges` | Lists all 144 official Scouts BSA Merit Badges with category, Eagle-required status, favorite flag (`is_favorite`), sub-requirement count, and pamphlet/DRG URLs. | Yes |
| `GET /api/v1/badges/favorites` | Lists all Merit Badges starred as favorites (`counselor_favorites` SQLite table). | Yes |
| `POST /api/v1/badges/favorites/toggle` | Toggles `⭐` favorite status (`badge_name`) in `counselor_favorites` and returns the updated favorite list. | Yes |
| `GET /api/v1/templates` | Lists the **17 built-in Scouting America & Heritage PowerPoint templates** (`default_workbench`, `scouting_america_250`, `scouting_america_forest_sunrise`, `scouting_america_topographic`, `scouting_america_high_adventure_rock`, `classic_outdoor_silhouette_navy`, `classic_fleur_crimson_crest`, `wilderness_camp_timber`) plus custom uploaded/URL templates with `SafeCanvasBounds`. | Yes |
| `POST /api/v1/templates/upload` | Uploads a custom `.pptx`, `.ppt`, `.png`, `.jpg`, or `.webp` slide template, extracts dominant brand colors and background artwork, and computes `SafeCanvasBounds` (`content_bottom_max_in <= 6.54"` clamping). | Yes |
| `POST /api/v1/templates/import-url` | Imports a custom PowerPoint or image template from a remote URL and registers it in the template catalog. | Yes |
| `POST /api/v1/templates/apply` | Applies a selected `template_id` (and optional `visual_theme` / `beautification_tier` `WARM_CREAM`, `CRISP_WHITE`, or `DARK_SLATE`, short aliases `CREAM`, `WHITE`, `SLATE`, legacy aliases `BEAUTIFIED`, `STANDARD`, `STUDIO`, and `accent_palette_key` such as `MATCH_TEMPLATE`) to a slide storyboard and rebuilds the `.pptx` deck within `SafeCanvasBounds`. | Yes |
| `PATCH /api/v1/templates/{template_id}` | Updates the display `name` and `description` metadata of a custom user-uploaded or URL-imported template while protecting the 8 built-in templates. | Yes |
| `DELETE /api/v1/templates/{template_id}` | Deletes a custom user-uploaded or URL-imported template while protecting the 8 built-in templates (and reverts the active deck to `Workbench Classic` / `default_workbench` if that template was applied). | Yes |
| `GET /api/v1/workspaces`, `POST /api/v1/workspaces` | Lists all saved counselor deck workspaces (`counselor_workspaces` table in `scouts_bsa_sessions.db`) or saves/updates a workspace (`workspace_title`, `session_label`, `camp_bundle_tag`, `template_id`, `storyboard_slides`, and isolated Patrol Blue Card `#34124` `blue_card_roster`). | Yes |
| `GET /api/v1/workspaces/{workspace_id}`, `PATCH /api/v1/workspaces/{workspace_id}`, `DELETE /api/v1/workspaces/{workspace_id}` | Loads, renames/updates metadata or Blue Card roster on, or deletes a saved Merit Badge deck workspace (`<80ms` hot-swap). | Yes |
| `POST /api/v1/workspaces/{workspace_id}/clone` | Clones a saved deck workspace for a new patrol section (`📑 Clone for New Section`, e.g., Morning vs. Afternoon Patrol) with an optional fresh empty Blue Card roster. | Yes |
| `GET /api/v1/docs` | Lists the allowlisted in-app documentation catalog (`12` docs total: 2 User Docs `user-guide`, `admin-guide`; and 10 Engineering Docs `readme`, `architecture`, `tdd`, `adr`, `finops-guide`, `api-guide`, `mcp-guide`, `data-governance`, `security-compliance`, `runbook`) for the `📘 Documentation` modal. | No |
| `GET /api/v1/docs/{doc_id}` | Returns raw Markdown, title, category (`User Docs` or `Engineering Docs`), and relative repository path for an allowlisted `doc_id` with path-traversal protection. | No |
| `GET /api/v1/counselor-profile` | Loads locally cached counselor info (`.cache/counselor_profile.json` on local runs; returns `storage_mode: "browser_local_storage"` on Cloud Run). | Yes |
| `POST /api/v1/counselor-profile` | Saves counselor info to `.cache/counselor_profile.json` (`0600` owner-only permissions) on local runs. | Yes |
| `DELETE /api/v1/counselor-profile` | Clears locally cached counselor info (`.cache/counselor_profile.json`). | Yes |
| `POST /api/v1/upload-logo` | Uploads a custom Troop or Council logo (`.png`, `.jpg`, `.jpeg` as Base64 data URL), writes it to `assets/custom_logos/`, and returns `logo_path` and `logo_url`. | Yes |
| `POST /api/v1/workflow/run` | Runs the 7-agent pipeline and returns the `.pptx` download URL, `.md` workbook, storyboard, lesson plan, parent letter, resolved location context, per-badge image catalog, and FinOps cost breakdown. | Yes |
| `GET /api/v1/workflow/stream` | Streams real-time Server-Sent Events (`text/event-stream`) as each agent stage finishes. | No (Browser EventSource) |
| `POST /api/v1/studiokit/agenda` | Regenerates the Counselor Session Agenda for a selected schedule format (`3 Troop Meetings (45 min each)`, `Summer Camp Week`, `Saturday Merit Badge Clinic`, or `Weekend Campout Practicum`). | Yes |
| `GET /api/v1/local-grounding/senators`, `POST /api/v1/local-grounding/senators` | Resolves current state U.S. Senators and official contact portals for a counselor's state, city, or ZIP code (with 24-hour cache TTL or `force=true` refresh). | Yes |
| `GET /api/v1/qr.svg` | Generates an ISO/IEC 18004 scannable SVG QR code (`image/svg+xml`) for a target URL (`url`, `size=48..512`), used on the Cover Slide and printable workbooks. | No |
| `POST /api/v1/hitl/confirm` | Validates counselor sign-off and returns an HMAC-SHA256 `confirmation_token`. | Yes |
| `POST /api/v1/feedback` | Records counselor rating (`1-5`), thumbs-up/down, and requirement accuracy sign-off in SQLite (`hitl_feedback`) and `deliverables/counselor_hitl_feedback.jsonl`, and promotes verified `>=4/5` runs to `tests/data/golden_extensions.json`. | Yes |
| `GET /api/v1/feedback` | Returns aggregated counselor feedback statistics and the 25 most recent SQLite feedback records. | Yes |
| `GET /api/v1/metrics` | Returns latency percentiles (`p50`/`p95`/`p99`), token spend, cache hit rate, circuit breaker states, and recent compliance audit events. | Yes |
| `GET /api/v1/prompts/manifest` | Returns the versioned prompt manifest (`prompts/manifest.json`) with SHA-256 content hashes. | Yes |
| `GET /api/v1/cache/clear`, `POST /api/v1/cache/clear` | Clears synthetic pamphlet cover caches and refills official BSA pamphlet covers on demand. | Yes |

### 2.2 Slide customization, AI speaker-note polish, Google Slides export, and Image Studio endpoints

| Method and path | Purpose | Auth required in prod |
| :--- | :--- | :--- |
| `POST /api/v1/slide/regenerate` | Updates a single slide's layout archetype, card theme, color palette, right-side graphic (`keep_current`, `restore_original`, `ai_hero`, `custom_image`, or `none`), or inline text overrides (`title`, `bullet_points`, `visual_caption`, `custom_presenter_notes` at `$0.00 USD`), re-syncs teaching notes, and rebuilds the `.pptx` file. | Yes |
| `POST /api/v1/slide/deck-customize` | Inserts a custom local slide (`insert_custom_slide`), toggles slide visibility (`toggle_hide_slide`), bulk-hides home prerequisite slides (`hide_home_prereq_slides`), or reorders slides (`reorder_slide`), and rebuilds the `.pptx` excluding hidden slides. | Yes |
| `POST /api/v1/slide/estimate-polish-cost` | Calculates exact `gemini-2.5-flash` (`thinking_budget=0`) token and USD cost estimates (`$0.000835/slide` uncached; `$0.00` when cached in SQLite `polished_speaker_notes`) for polishing a single slide vs. the entire deck, powering the `#ai-polish-finops-modal` consent gate. | Yes |
| `POST /api/v1/slide/polish-notes` | Polishes a single slide's `[SAY]` / `[DEMONSTRATE]` / `[ASK SCOUTS]` teaching script via `gemini-2.5-flash` (or the deterministic Studio Narrative Synthesizer offline), caches the result by SHA-256 hash in SQLite (`polished_speaker_notes`), and updates the `.pptx` in place. | Yes |
| `POST /api/v1/slide/polish-notes-batch` | Polishes all visible slides plus the Cover Slide across the deck in parallel (`asyncio.Semaphore(12)`), reuses SQLite cache hits, and performs a single `.pptx` rebuild. | Yes |
| `GET /api/v1/slide/export-gslides/account-info` | Detects the active workstation/server Google account, OAuth 2.0 client ID, and `gdrive` CLI readiness to populate the Google Slides Account & Destination Modal. | Yes |
| `POST /api/v1/slide/export-gslides` | Converts and uploads the active `.pptx` deck into a native Google Slides presentation (`application/vnd.google-apps.presentation`) using a 4-tier auth waterfall (Browser OAuth 2.0 token, `GOOGLE_DRIVE_ACCESS_TOKEN` / ADC, workstation `gdrive` CLI with optional `share_with_email` writer grant, or guided AccountChooser import). | Yes |
| `GET /api/v1/badge/images` | Lists all cached images in the Merit Badge Image Catalog (`badge_image_catalog` SQLite table + `assets/badge_image_catalog/<badge_slug>/`) for a given badge. | Yes |
| `DELETE /api/v1/badge/images` | Purges user-searched web (`WEB_IMAGE_SEARCH`) and user-generated AI (`NANO_BANANA_AI`) cached images for a badge while preserving official `PAMPHLET` figures, pre-bundled hero illustrations (`NANO_BANANA_HERO`), and `USER_UPLOAD` files. | Yes |
| `POST /api/v1/slide/search-web-images` | Invokes `WebImageSearchAgent` (`gemini-2.5-flash`) to search Wikimedia Commons for up to 16 matching visuals, download them, and cache them for the badge. | Yes |
| `POST /api/v1/slide/estimate-image-cost` | Returns a FinOps cost estimate (`$0.08 USD` per image, ~`2,580` tokens) before running `NanoBananaImageAgent`. | Yes |
| `POST /api/v1/slide/generate-nano-banana-image` | Invokes `NanoBananaImageAgent` (`gemini-2.5-flash-image` / Imagen 3) across 10 UI visual styles (including `Auto (Content-Aware Mix)` and `include_humans` control) after verifying `user_consented=True`, checks prompt alignment (`verify_generated_image_matches_prompt()`), and caches the graphic. | Yes |
| `POST /api/v1/slide/upload-image` | Uploads a local `.png`/`.jpg`/`.webp`/`.gif` image (`<= 10 MB`, `$0.00 USD`), normalizes it to RGB PNG (`max 1600px`), and registers it as `USER_UPLOAD` in the badge catalog. | Yes |

### 2.3 Super-User Admin Console, MCP Server, and A2A 1.0 endpoints

| Method and path | Purpose | Auth required in prod |
| :--- | :--- | :--- |
| `GET /mcp/info`, `GET /api/v1/mcp/info` | Returns the Scouts BSA Workbench MCP Server discovery manifest (`12` tools, `6` `bsa://` resources, `4` guided prompts, and ready-to-copy client configs for Claude Desktop, Gemini CLI / AGY, Cursor, and Google ADK). See [`docs/MCP_SERVER_INTEGRATION_GUIDE.md`](MCP_SERVER_INTEGRATION_GUIDE.md). | No |
| `POST /mcp`, `POST /api/v1/mcp` | Executes Model Context Protocol (`2024-11-05`) JSON-RPC 2.0 calls (`initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, `prompts/list`, `prompts/get`). | Yes |
| `GET /mcp/sse`, `GET /api/v1/mcp/sse` | Streams Model Context Protocol Server-Sent Events (`text/event-stream`) for SSE-based MCP clients and IDEs. | No (SSE) |
| `GET /api/v1/admin/session` | Checks whether the current browser session is authorized for the Super-User Admin Console (`is_admin`, `auth_mode`, `role`). | Super-User / Session |
| `POST /api/v1/admin/unlock` | Validates `ADMIN_SUPERUSER_TOKEN` and sets a signed `HttpOnly` session cookie (`bsa_admin_session`, 24h TTL). | Super-User Token |
| `POST /api/v1/admin/lock` | Locks the Super-User Admin Console for the current browser session by setting `bsa_admin_session=locked`. | Super-User / Session |
| `GET /api/v1/admin/catalog/images` | Lists all catalog images, captions, requirement mappings, primary/alternate status (`is_alternate`, `alternate_rank`), and discard flags for any of the 144 Merit Badges, with optional `req_number`, `source_type`, and `role` filters. | Super-User |
| `PATCH /api/v1/admin/catalog/image` | Atomically updates a catalog image's `caption`, `title`, `req_number`, `is_alternate`, `alternate_rank`, or `discard` flag across disk JSON manifests and SQLite. | Super-User |
| `POST /api/v1/admin/catalog/promote-primary` | Promotes an alternate figure (`alternate_rank >= 1`) to Primary Default (`is_alternate=False`, `alternate_rank=0`) for its requirement and demotes the prior primary. | Super-User |
| `POST /api/v1/admin/catalog/vision-recaption`, `POST /api/v1/admin/catalog/recaption-vision` | Runs a single-image `gemini-2.5-flash` Vision pass to generate and persist an updated instructional caption. | Super-User |
| `POST /api/v1/admin/catalog/replace-image` | Replaces a catalog image in place (creating a `.bak.<ts>` backup and quantizing to an 8-bit PNG `<= 800x600`) from a Base64 upload (`image_data_uri`) or live Nano Banana regeneration (`regenerate_nano=true`). | Super-User |
| `GET /api/v1/admin/telemetry/summary` | Returns aggregated zero-PII deck usage, cache hit rate, FinOps spend, bimodal stage latency percentiles, compliance audit events, and the Easy Slide Image Switcher Swap Leaderboard (`ZeroPiiTelemetryStore` in `src/observability/telemetry_store.py`). | Super-User |
| `POST /api/v1/admin/telemetry/image-swap` | Records an anonymous slide visual swap event (`badge_name`, `req_number`, `from_image_id`, `to_image_id`) with zero counselor PII. | Yes |
| `GET /api/v1/admin/diagnostics/assets` | Returns the 144-Badge Asset Health Matrix (`covers_present`, `emblems_present`, `pdfs_indexed_present`, `total_pamphlet_figures`, `total_nano_banana_heroes`), Prompt SHA-256 Manifest, and Zero-PII Guardrail Audit Log. | Super-User |
| `POST /api/v1/admin/circuit-breakers/reset` | Resets all downstream circuit breakers back to `CLOSED`. | Super-User |
| `POST /api/v1/admin/senators/refresh` | Triggers a forced refresh of the 100 U.S. Senators grounding cache (`24h` TTL) or a single state delegation from the Admin Console. | Super-User |
| `POST /api/v1/admin/maintenance/purge-temp-cache` | Purges temporary web-search scratch files (`assets/badge_image_catalog/_web_search_cache/`) while preserving all 3,917 built-in 144-badge assets. | Super-User |
| `POST /api/v1/admin/maintenance/repair-covers` | Verifies and repairs all 144 Merit Badge pamphlet covers and badge emblems on disk. | Super-User |
| `GET /api/v1/admin/maintenance/snapshot` | Exports a downloadable Zero-PII JSON snapshot combining telemetry summary, 144-badge asset diagnostics, prompt SHA-256 hashes, and compliance audit events. | Super-User |
| `GET /.well-known/agent.json` | Returns the A2A 1.0 Agent Card for discovery. | No |
| `POST /a2a/tasks/send` | Executes an A2A 1.0 task and returns `application/json+a2ui` v0.9 surface payloads. | Yes |
| `GET /a2a/tasks/{task_id}`, `POST /a2a/tasks/{task_id}/cancel` | Retrieves status or cancels an in-flight A2A 1.0 task. | Yes |

---

## 3. Sample requests

### 3.1 Generate a Merit Badge deck and workbook (`POST /api/v1/workflow/run`)
```bash
curl -X POST http://localhost:8085/api/v1/workflow/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${BSA_API_KEY}" \
  -d '{
    "badge_name": "Weather",
    "depth_mode": "Standard Deck",
    "beautification_tier": "WARM_CREAM",
    "enable_deep_research": true,
    "audience_level": "All Scouts (Ages 11-17)",
    "counselor_name": "Eric Clayberg",
    "troop_affiliation": "Troop 19, Middleton MA",
    "location_or_zip": "01949",
    "email_address": "clayberg@gmail.com",
    "phone_number": "(978) 555-0119"
  }'
```

### 3.2 Estimate FinOps cost and polish speaker notes (`POST /api/v1/slide/estimate-polish-cost`, `/polish-notes`, `/polish-notes-batch`)
```bash
# Step 1: Estimate Gemini Flash (thinking_budget=0) token & USD cost before polishing
curl -X POST http://localhost:8085/api/v1/slide/estimate-polish-cost \
  -H "Content-Type: application/json" \
  -d '{
    "badge_name": "First Aid",
    "slide_index": 2,
    "audience_level": "All Scouts (Ages 11-17)",
    "storyboard_slides": [
      {"req_number": "1", "title": "First Aid Kit Essentials", "bullet_points": ["Inspect sterile gauze and gloves"]}
    ]
  }'
# Sample response:
# {
#   "status": "SUCCESS",
#   "badge_name": "First Aid",
#   "model_label": "Gemini Flash",
#   "single_slide_cached": false,
#   "single_slide_input_tokens": 450,
#   "single_slide_output_tokens": 280,
#   "single_slide_cost_usd": 0.00084,
#   "total_slides": 2,
#   "cached_slides_count": 0,
#   "uncached_slides_count": 2,
#   "deck_uncached_cost_usd": 0.0017,
#   "deck_full_repolish_cost_usd": 0.0017,
#   "pricing_rate_summary": "$0.30 / 1M input tokens • $2.50 / 1M output tokens (thinking_budget=0)"
# }

# Step 2a: Polish a single slide's [SAY] / [DEMONSTRATE] / [ASK SCOUTS] script
curl -X POST http://localhost:8085/api/v1/slide/polish-notes \
  -H "Content-Type: application/json" \
  -d '{
    "badge_name": "First Aid",
    "slide_index": 0,
    "audience_level": "All Scouts (Ages 11-17)",
    "force_refresh": false,
    "slide_data": {
      "req_number": "1",
      "title": "First Aid Kit Essentials",
      "archetype": "SPLIT_VISUAL_EXPLAINER",
      "bullet_points": ["Personal Kit: Carry adhesive bandages, moleskin, and nitrile gloves."]
    }
  }'

# Step 2b: Polish the entire deck in parallel (up to 12 concurrent slides + Cover Slide)
curl -X POST http://localhost:8085/api/v1/slide/polish-notes-batch \
  -H "Content-Type: application/json" \
  -d '{
    "badge_name": "First Aid",
    "audience_level": "All Scouts (Ages 11-17)",
    "force_refresh": false,
    "storyboard_slides": [
      {"req_number": "1", "title": "First Aid Kit Essentials", "bullet_points": ["Personal Kit: Bandages and gloves."]}
    ]
  }'
```

### 3.3 Check Google account info and export deck to Google Slides (`GET /api/v1/slide/export-gslides/account-info` & `POST /api/v1/slide/export-gslides`)
```bash
# Step 1: Detect workstation/server account and OAuth readiness
curl -fsS http://localhost:8085/api/v1/slide/export-gslides/account-info | jq .

# Step 2: Export the generated .pptx to a native Google Slides presentation and share with a personal Gmail account
curl -X POST http://localhost:8085/api/v1/slide/export-gslides \
  -H "Content-Type: application/json" \
  -d '{
    "badge_name": "First Aid",
    "beautification_tier": "WARM_CREAM",
    "share_with_email": "counselor@gmail.com",
    "use_adc": true
  }'
```

### 3.4 Customize deck structure (`POST /api/v1/slide/deck-customize`)
```bash
# Insert a custom local camp instruction slide, hide home prerequisite slides, or reorder slides
curl -X POST http://localhost:8085/api/v1/slide/deck-customize \
  -H "Content-Type: application/json" \
  -d '{
    "badge_name": "Camping",
    "action": "insert_custom_slide",
    "slide_index": 1,
    "custom_slide": {
      "req_number": "Local",
      "title": "Camp Wanocksett Check-In & Swim Test Rules",
      "bullet_points": [
        "Buddy Tags: Pick up waterfront buddy tags at the boat house before 2:00 PM.",
        "Quartermaster Tent Check: Inspect tent poles and rainfly stakes with your Patrol Leader."
      ]
    },
    "storyboard_slides": []
  }'
```

### 3.5 Estimate cost and generate a custom slide graphic (`NanoBananaImageAgent`)
```bash
# Step 1: Estimate cost before generating ($0.08 USD)
curl -X POST http://localhost:8085/api/v1/slide/estimate-image-cost \
  -H "Content-Type: application/json" \
  -d '{
    "badge_name": "Weather",
    "visual_style": "Auto (Content-Aware Mix)",
    "num_images": 1
  }'

# Step 2: Generate with explicit user consent (user_consented: true) and optional include_humans control
curl -X POST http://localhost:8085/api/v1/slide/generate-nano-banana-image \
  -H "Content-Type: application/json" \
  -d '{
    "badge_name": "Weather",
    "req_number": "2",
    "slide_title": "Cold Front vs Warm Front Dynamics",
    "prompt": "Cross-section diagram showing a steep cold front wedge lifting warm moist air into cumulonimbus clouds",
    "visual_style": "Auto (Content-Aware Mix)",
    "include_humans": false,
    "beautification_tier": "WARM_CREAM",
    "user_consented": true
  }'
```

### 3.6 Upload a local image or custom Troop logo (`POST /api/v1/slide/upload-image` & `POST /api/v1/upload-logo`)
```bash
# Upload a custom slide graphic into the badge catalog ($0.00 USD)
curl -X POST http://localhost:8085/api/v1/slide/upload-image \
  -H "Content-Type: application/json" \
  -d '{
    "badge_name": "Weather",
    "req_number": "2",
    "slide_title": "Troop 19 Anemometer Build",
    "filename": "anemometer_photo.png",
    "title": "Troop 19 Anemometer Build",
    "description": "Scouts calibrating homemade cup anemometers at camp",
    "data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
  }'

# Upload a Troop or Council logo for Slide 1 (Cover)
curl -X POST http://localhost:8085/api/v1/upload-logo \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "troop19_logo.png",
    "data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
  }'
```

### 3.7 Browse in-app documentation (`GET /api/v1/docs` & `GET /api/v1/docs/{doc_id}`)
```bash
# List all allowlisted User Docs (2) and Engineering Docs (10) across 12 total docs
curl -fsS http://localhost:8085/api/v1/docs | jq .

# Fetch a specific document's Markdown content by allowlisted ID
curl -fsS http://localhost:8085/api/v1/docs/user-guide | jq '{id, title, category, path}'
```

### 3.8 Super-User Admin Console curation and diagnostics (`/api/v1/admin/*`)
```bash
# 1. Unlock an Admin session cookie
curl -c /tmp/admin_cookies.txt -X POST http://localhost:8085/api/v1/admin/unlock \
  -H "Content-Type: application/json" \
  -d '{"token": "'"${ADMIN_SUPERUSER_TOKEN}"'"}'

# 2. List catalog images for a badge and update a caption inline
curl -b /tmp/admin_cookies.txt -fsS "http://localhost:8085/api/v1/admin/catalog/images?badge_name=First%20Aid" | jq .

curl -b /tmp/admin_cookies.txt -X PATCH http://localhost:8085/api/v1/admin/catalog/image \
  -H "Content-Type: application/json" \
  -d '{
    "badge_name": "First Aid",
    "image_id": "first_aid_req_1_nano_hero.png",
    "caption": "Patrol First Aid Kit & Personal Essentials Inspection"
  }'

# 3. Inspect 144-badge asset coverage and Zero-PII telemetry summary
curl -b /tmp/admin_cookies.txt -fsS http://localhost:8085/api/v1/admin/diagnostics/assets | jq .
curl -b /tmp/admin_cookies.txt -fsS http://localhost:8085/api/v1/admin/telemetry/summary | jq .
```

### 3.9 Submit and list counselor feedback (`POST /api/v1/feedback` & `GET /api/v1/feedback`)
```bash
curl -X POST http://localhost:8085/api/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "badge_name": "Weather",
    "session_id": "troop_19_session",
    "rating": 5,
    "thumbs_up": true,
    "requirement_accuracy_verified": true,
    "comments": "Warm vs cold front diagram worked well for Tenderfoot Scouts."
  }'

curl -fsS http://localhost:8085/api/v1/feedback | jq .
```
