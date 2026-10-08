# API and integration guide (`OpenAPI 3.1`, `A2A 1.0`, and `SSE`)

The FastAPI server (`src/server.py`) serves the Material 3 web workbench (`/`), versioned REST endpoints (`/api/v1/*`), Merit Badge Image Studio endpoints (`/api/badge/images`, `/api/slide/*`), counselor profile persistence (`/api/counselor-profile`), Server-Sent Events (`/api/v1/workflow/stream`), Agent-to-Agent (`A2A 1.0`) task routes (`/a2a/*`), and container health checks (`/health`, `/readiness`).

- **OpenAPI 3.1 schema**: [`docs/openapi.yaml`](openapi.yaml) (exported by `scripts/export_openapi.py` and checked in `tests/test_resilience_and_fault_injection.py`).
- **Swagger UI**: `http://localhost:8085/docs`
- **A2A 1.0 Agent Card**: `http://localhost:8085/.well-known/agent.json`

---

## 1. Authentication headers

Controlled by `AUTH_REQUIRED` (`false` by default on `localhost`; `true` in Cloud Run):
- **API key header**: `X-API-Key: <your-bsa-api-key>`
- **OIDC / Bearer token header**: `Authorization: Bearer <OIDC_JWT>`

---

## 2. Endpoint summary

| Method and path | Purpose | Auth required in prod |
| :--- | :--- | :--- |
| `GET /health` | Container liveness check (`{"status": "UP"}`). | No (Cloud Run probe) |
| `GET /readiness` | Deep readiness check for SQLite store, 138-badge catalog, policy JSON files, and circuit breakers. | No (Cloud Run probe) |
| `GET /api/v1/badges` | Lists all 138 official Scouts BSA Merit Badges with category, Eagle status, and pamphlet/DRG URLs. | Yes |
| `GET /api/counselor-profile` | Loads locally cached counselor info (`.cache/counselor_profile.json` on local runs; returns `storage_mode: "browser_local_storage"` on Cloud Run). | Yes |
| `POST /api/counselor-profile` | Saves counselor info to `.cache/counselor_profile.json` (`0600` permissions) on local runs. | Yes |
| `DELETE /api/counselor-profile` | Clears locally cached counselor info (`.cache/counselor_profile.json`). | Yes |
| `POST /api/v1/workflow/run` | Runs the full pipeline and returns the `.pptx` download path, `.md` workbook, storyboard, lesson plan, parent letter, resolved location context, per-badge image catalog, and FinOps cost breakdown. | Yes |
| `GET /api/v1/workflow/stream` | Streams real-time Server-Sent Events (`text/event-stream`) as each agent stage finishes. | No (Browser EventSource) |
| `POST /api/v1/slide/regenerate` | Updates a single slide's layout archetype, card theme, color palette, or right-side graphic (`keep_current`, `restore_original`, `ai_hero`, `custom_image`, or `none`) and rebuilds the `.pptx` file. | Yes |
| `GET /api/badge/images` | Lists all cached images in the Merit Badge Image Catalog (`badge_image_catalog` SQLite table + `assets/badge_image_catalog/<badge_slug>/`) for a given badge. | Yes |
| `DELETE /api/badge/images` | Purges user-searched web (`WEB_IMAGE_SEARCH`) and user-generated AI (`NANO_BANANA_AI`) cached images for a badge while preserving official `PAMPHLET` figures, pre-generated/auto-generated hero illustrations (`NANO_BANANA_HERO`), and `USER_UPLOAD` files. | Yes |
| `POST /api/slide/search-web-images` | Invokes `WebImageSearchAgent` (`gemini-2.5-flash`) to search Wikimedia Commons for up to 12 matching visuals, download them, and cache them for the badge. | Yes |
| `POST /api/slide/estimate-image-cost` | Returns a FinOps cost estimate (`$0.08 USD` per image, ~`2,580` tokens) before running `NanoBananaImageAgent`. | Yes |
| `POST /api/slide/generate-nano-banana-image` | Invokes `NanoBananaImageAgent` (`gemini-2.5-flash-image` / Nano Banana & Imagen 3) across 11 visual styles (including `Auto (Content-Aware Mix)` and `include_humans` control) after verifying `user_consented=True`, verifies prompt alignment (`verify_generated_image_matches_prompt()`), attaches the new graphic to the slide, adjusts text-only slides to `SPLIT_VISUAL_EXPLAINER`, and rebuilds the `.pptx`. | Yes |
| `POST /api/slide/upload-image` | Uploads a local `.png`/`.jpg`/`.webp` image (`<= 10 MB`, `$0.00 USD`), normalizes it to RGB PNG (`max 1600px`), registers it as `USER_UPLOAD` in the badge catalog, and optionally applies it to the slide and rebuilds the `.pptx`. | Yes |
| `POST /api/v1/hitl/confirm` | Validates counselor sign-off and returns an HMAC-SHA256 `confirmation_token`. | Yes |
| `POST /api/v1/feedback` | Records counselor rating (`1-5`), thumbs-up/down, and requirement accuracy sign-off in `deliverables/counselor_hitl_feedback.jsonl`. | Yes |
| `GET /api/v1/metrics` | Returns latency percentiles (`p50`/`p95`/`p99`), token spend, cache hit rate, circuit breaker states, and compliance audit events. | Yes |
| `GET /api/v1/prompts/manifest` | Returns the prompt manifest (`prompts/manifest.json`) with SHA-256 content hashes. | Yes |
| `POST /a2a/tasks/send` | Executes an A2A 1.0 task and returns `application/json+a2ui` v0.9 surface payloads. | Yes |

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
    "beautification_tier": "BEAUTIFIED",
    "enable_deep_research": true,
    "audience_level": "All Scouts (Ages 11-17)",
    "counselor_name": "Eric Clayberg",
    "troop_affiliation": "Troop 19, Middleton MA",
    "location_or_zip": "01949",
    "email_address": "clayberg@gmail.com",
    "phone_number": "(978) 555-0119"
  }'
```

### 3.2 Estimate cost and generate a custom slide graphic (`NanoBananaImageAgent`)
```bash
# Step 1: Estimate cost before generating ($0.08 USD)
curl -X POST http://localhost:8085/api/slide/estimate-image-cost \
  -H "Content-Type: application/json" \
  -d '{
    "badge_name": "Weather",
    "visual_style": "Auto (Content-Aware Mix)",
    "num_images": 1
  }'

# Step 2: Generate with explicit user consent (user_consented: true) and optional include_humans control
curl -X POST http://localhost:8085/api/slide/generate-nano-banana-image \
  -H "Content-Type: application/json" \
  -d '{
    "badge_name": "Weather",
    "slide_index": 2,
    "req_number": "Req 2",
    "slide_title": "Cold Front vs Warm Front Dynamics",
    "prompt": "Cross-section diagram showing a steep cold front wedge lifting warm moist air into cumulonimbus clouds",
    "visual_style": "Auto (Content-Aware Mix)",
    "include_humans": false,
    "beautification_tier": "BEAUTIFIED",
    "user_consented": true,
    "apply_to_slide": true
  }'
```

### 3.3 Upload a local custom image to a slide (`POST /api/slide/upload-image`)
```bash
curl -X POST http://localhost:8085/api/slide/upload-image \
  -H "X-API-Key: ${BSA_API_KEY}" \
  -F "badge_name=Weather" \
  -F "slide_index=2" \
  -F "req_number=Req 2" \
  -F "title=Troop 19 Anemometer Build" \
  -F "description=Scouts calibrating homemade cup anemometers at camp" \
  -F "apply_to_slide=true" \
  -F "file=@./my_troop_photo.jpg"
```

### 3.4 Submit counselor feedback (`POST /api/v1/feedback`)
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
```
