"""FastAPI + SSE + A2A 1.0 + FastMCP + Google Material 3 Expressive A2UI Server.

Exposes:
- GET  /.well-known/agent.json      : A2A 1.0 Agent Card discovery
- POST /a2a/tasks/send              : A2A 1.0 Task execution with A2UI v0.9 DataParts
- GET  /a2a/tasks/{task_id}         : A2A 1.0 Task status retrieval
- POST /a2a/tasks/{task_id}/cancel  : A2A 1.0 Task cancellation
- GET  /api/badges                  : Catalog of official Scouts BSA Merit Badges
- POST /api/workflow/run            : Full 5-Agent Merit Badge Deck & Workbook workflow
- GET  /api/workflow/stream         : Live Server-Sent Events (SSE) streaming
- POST /api/slide/regenerate        : Surgical single-slide archetype & visual regeneration
- POST /api/hitl/confirm            : FastMCP cryptographic confirmation_token verification
- GET  /                            : Google Material 3 Expressive A2UI Counselor Workbench
"""

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.config import (
    ASSETS_DIR,
    CONFIG_DIR,
    EAGLE_REQUIRED_BADGES,
    GENERATED_DECKS_DIR,
    GENERATED_DIAGRAMS_DIR,
    OFFICIAL_BSA_MERIT_BADGES_CATALOG,
    PROJECT_ROOT,
    load_prompt_manifest,
)
from src.agents.coordinator import (
    run_merit_badge_workflow,
    stream_merit_badge_workflow_events,
)
from src.agents.guardrails import get_compliance_audit_events
from src.resilience import METRICS_COLLECTOR
from src.security import verify_caller_auth
from src.tools.hitl_confirm import request_counselor_confirmation

logger = logging.getLogger("scouts_bsa_agent.server")

UI_DIR = PROJECT_ROOT / "ui"
UI_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Scouts BSA Merit Badge Agent — Material 3 Expressive A2UI & A2A 1.0 Server",
    version="3.1.0",
    description=(
        "Production ADK multi-agent system with 5-Tier Deep Pamphlet Research, "
        "12-Archetype Slide Engine, Tri-Modal Visual Synthesis, 2-Stage Conformance/Vision "
        "Critic, FastMCP HITL Confirmation Tokens, and Google Material 3 Expressive A2UI."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_api_version_and_deprecation_headers(request: Any, call_next: Any) -> Any:
    """Attaches `X-API-Version: 1.2.0` and RFC 8594 `Deprecation`/`Sunset` headers on legacy unversioned paths."""
    from src.schemas import CURRENT_SCHEMA_VERSION

    response = await call_next(request)
    response.headers["X-API-Version"] = CURRENT_SCHEMA_VERSION
    path = str(getattr(request, "url", "") and request.url.path or "")
    if path.startswith("/api/") and not path.startswith("/api/v1/"):
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = "2027-01-01"
    elif path.startswith("/assets/construction_anim/") or path.startswith("/assets/badge_emblems/"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    return response


# Mount static directories
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
app.mount("/deliverables", StaticFiles(directory=str(GENERATED_DECKS_DIR)), name="deliverables")
app.mount("/ui", StaticFiles(directory=str(UI_DIR)), name="ui")

# In-memory A2A task registry
_A2A_TASKS: Dict[str, Dict[str, Any]] = {}


# ==============================================================================
# REQUEST / RESPONSE MODELS
# ==============================================================================

class WorkflowRunRequest(BaseModel):
    badge_name: str = Field("First Aid", description="Official Merit Badge name.")
    depth_mode: str = Field(
        "Deep Dive / Camp School Deck",
        description="'Standard Deck' or 'Deep Dive / Camp School Deck'",
    )
    counselor_name: str = Field("Scoutmaster Bob", description="Merit Badge Counselor name.")
    troop_affiliation: str = Field(
        "Troop 123, My Council", description="Troop and Council affiliation."
    )
    location_or_zip: Optional[str] = Field(
        "", description="Optional City, State or 5-digit ZIP code for local NOAA/USGS/field grounding."
    )
    email_address: Optional[str] = Field("counselor@troop123.org", description="Counselor contact email.")
    phone_number: Optional[str] = Field("(000) 555-1234", description="Counselor contact phone.")
    custom_troop_logo_path: Optional[str] = Field(None, description="Optional path to custom Troop Logo PNG/JPG.")
    enable_deep_research: bool = Field(True, description="Whether to run Tier-2 grounded web & local troop research.")
    beautification_tier: str = Field("BEAUTIFIED", description="'STANDARD', 'BEAUTIFIED', or 'STUDIO'.")
    schedule_format: str = Field("3 Troop Meetings (45 min each)", description="Counselor lesson schedule format.")
    audience_level: str = Field("All Scouts (Ages 11–17)", description="Target Scout audience level.")
    session_id: str = Field("a2ui_workbench_session", description="Persistent counselor session ID.")
    webhook_url: Optional[str] = Field(None, description="Optional webhook callback URL notified on completion.")


class CounselorFeedbackRequest(BaseModel):
    badge_name: str = Field("First Aid", description="Merit Badge evaluated by the Counselor.")
    counselor_name: str = Field("Scoutmaster Bob", description="Merit Badge Counselor name.")
    session_id: str = Field("a2ui_workbench_session", description="Session identifier.")
    rating: int = Field(5, ge=1, le=5, description="Counselor quality rating (1 to 5 stars).")
    thumbs_up: bool = Field(True, description="True for positive endorsement, False for issue flag.")
    requirement_accuracy_verified: bool = Field(
        True, description="Whether the Counselor verified 100% sub-requirement fidelity."
    )
    requirement_count: int = Field(5, ge=1, description="Number of official requirements verified in this session.")
    comments: str = Field("", description="Optional Counselor notes or improvement suggestions.")


class TroopLogoUploadRequest(BaseModel):
    filename: str = Field(..., description="Uploaded image filename (.png, .jpg, .jpeg).")
    data_url: str = Field(..., description="Base64 Data URL or raw base64 content of the image.")


class SlideRegenerateRequest(BaseModel):
    badge_name: str
    slide_index: int = Field(..., description="0-based index in storyboard.slides")
    new_archetype: str = Field(..., description="Target SlideArchetype value")
    new_diagram_type: Optional[str] = None
    new_visual_theme: Optional[str] = None
    new_accent_palette: Optional[str] = None
    visual_source_mode: Optional[str] = Field(
        None,
        description="Override mode: 'keep_current', 'restore_original', 'custom_image', 'ai_hero', or 'none'.",
    )
    custom_image_path: Optional[str] = Field(None, description="Path to a selected catalog/web/AI image.")
    custom_image_caption: Optional[str] = Field(None, description="Caption for the selected image.")
    custom_image_source_label: Optional[str] = Field(None, description="Source label for the selected image.")
    slide_data: Dict[str, Any] = Field(default_factory=dict)
    storyboard_slides: Optional[List[Dict[str, Any]]] = Field(
        None, description="Optional full list of storyboard slides to immediately rebuild the .pptx file on disk."
    )
    counselor_info: Optional[Dict[str, Any]] = Field(None, description="Optional counselor personalization info.")
    output_path: Optional[str] = Field(None, description="Optional existing .pptx output path to update.")


class WebImageSearchRequest(BaseModel):
    badge_name: str
    slide_title: str = ""
    req_number: str = "1"
    search_query: str = ""
    bullet_points: List[str] = Field(default_factory=list)
    max_results: int = Field(16, ge=1, le=24)


class NanoBananaCostRequest(BaseModel):
    badge_name: str
    slide_title: str = ""
    req_number: str = "1"
    bullet_points: List[str] = Field(default_factory=list)
    custom_prompt: str = ""
    prompt: str = ""
    visual_style: str = "Photorealistic Image"
    include_humans: Optional[Any] = "auto"
    num_images: int = Field(1, ge=1, le=4)


class NanoBananaGenerateRequest(BaseModel):
    badge_name: str
    slide_title: str = ""
    req_number: str = "1"
    requirement_id: str = ""
    custom_prompt: str = ""
    prompt: str = ""
    bullet_points: List[str] = Field(default_factory=list)
    visual_style: str = "Photorealistic Image"
    include_humans: Optional[Any] = "auto"
    accent_palette_key: str = "NAVY_GOLD"
    beautification_tier: str = "STUDIO"
    user_consented: bool = False


class SlideImageUploadRequest(BaseModel):
    badge_name: str
    req_number: str = "1"
    slide_title: str = ""
    filename: str = "uploaded_slide_image.png"
    data_url: str = Field(default="", description="Base64 Data URL or raw base64 content of the uploaded image.")
    image_base64: str = Field(default="", description="Optional alias for data_url.")
    title: str = ""
    description: str = ""



class CounselorProfileSaveRequest(BaseModel):
    counselor_name: str = "Scoutmaster Bob"
    troop_affiliation: str = "Troop 123, My Council"
    location_or_zip: str = ""
    email_address: str = "counselor@troop123.org"
    phone_number: str = "(000) 555-1234"
    custom_troop_logo_path: Optional[str] = None


class A2ATaskSendRequest(BaseModel):
    id: Optional[str] = None
    sessionId: str = "a2a_default_session"
    message: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)



# ==============================================================================
# 1. A2A 1.0 AGENT CARD & TASK LIFECYCLE ENDPOINTS
# ==============================================================================

@app.get("/.well-known/agent.json")
async def get_a2a_agent_card() -> Dict[str, Any]:
    """Returns the authoritative A2A 1.0 Agent Card for enterprise discovery."""
    return {
        "name": "ScoutsBSAMeritBadgeCoordinatorAgent",
        "description": (
            "ADK 2.0 Hierarchical Multi-Agent System that performs 5-Tier Scouts BSA Merit Badge "
            "research and synthesizes 12-Archetype Widescreen PowerPoint (.pptx) decks, high-DPI "
            "SVG/PNG diagrams, and Counselor Workbooks with 2-Stage Visual Conformance verification."
        ),
        "url": "http://clayberg.c.googlers.com:8085",
        "version": "2.0.0",
        "protocolVersion": "1.0",
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True,
            "a2uiProtocolVersion": "v0.9",
        },
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": [
            "application/json",
            "application/json+a2ui",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/markdown",
        ],
        "skills": [
            {
                "id": "deep-merit-badge-research",
                "name": "5-Tier Merit Badge Pamphlet & Requirement Tree Research",
                "description": (
                    "Scrapes verbatim sub-requirements (1a, 1b, 2a, 3a-3q), extracts official BSA "
                    "Pamphlet PDFs, classifies execution modes (In-Class, Hands-On EDGE, Prerequisite), "
                    "and grounds local troop context."
                ),
                "tags": ["scouts-bsa", "research", "pamphlet", "triage"],
            },
            {
                "id": "twelve-archetype-pptx-generation",
                "name": "12-Archetype Widescreen Slide Deck & Tri-Modal Diagram Generation",
                "description": (
                    "Builds non-truncated 16:9 PowerPoint decks across 12 pedagogical archetypes with "
                    "unique per-slide SVG/PNG visuals and Stage 1 (<10ms AABB/WCAG) + Stage 2 Vision critique."
                ),
                "tags": ["pptx", "slides", "diagrams", "a2ui", "material-3"],
            },
        ],
    }


@app.post("/a2a/tasks/send")
async def a2a_send_task(
    req: A2ATaskSendRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Executes an A2A 1.0 task and returns A2UI v0.9 DataPart payloads."""
    task_id = req.id or f"task-{uuid.uuid4().hex[:10]}"
    badge_name = req.metadata.get("badge_name", "First Aid")
    depth_mode = req.metadata.get("depth_mode", "Deep Dive / Camp School Deck")

    # Also allow extracting badge_name from message parts
    parts = req.message.get("parts", [])
    for part in parts:
        text = part.get("text", "")
        for candidate in ["First Aid", "Camping", "Citizenship in the Nation", "Cooking", "Personal Fitness", "Emergency Preparedness", "Environmental Science", "Communication", "Swimming", "Lifesaving", "Robotics", "Weather"]:
            if candidate.lower() in text.lower():
                badge_name = candidate
                break

    result = await asyncio.to_thread(
        run_merit_badge_workflow,
        badge_name=badge_name,
        depth_mode=depth_mode,
        session_id=req.sessionId,
    )

    task_record = {
        "id": task_id,
        "sessionId": req.sessionId,
        "status": {
            "state": "completed" if result.get("status") == "SUCCESS" else "failed",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "artifacts": [
            {
                "name": f"{badge_name}_Slide_Deck.pptx",
                "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "uri": f"/deliverables/{os.path.basename(result.get('output_path', ''))}",
            },
            {
                "name": "a2ui_workbench_surface",
                "mimeType": "application/json+a2ui",
                "parts": [
                    {
                        "kind": "data",
                        "metadata": {"mimeType": "application/json+a2ui"},
                        "data": msg,
                    }
                    for msg in result.get("a2ui_messages", [])
                ],
            },
        ],
        "result": result,
    }
    _A2A_TASKS[task_id] = task_record
    return task_record


@app.get("/a2a/tasks/{task_id}")
async def a2a_get_task(
    task_id: str,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    if task_id not in _A2A_TASKS:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return _A2A_TASKS[task_id]


@app.post("/a2a/tasks/{task_id}/cancel")
async def a2a_cancel_task(
    task_id: str,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    if task_id not in _A2A_TASKS:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    _A2A_TASKS[task_id]["status"]["state"] = "canceled"
    return _A2A_TASKS[task_id]



# ==============================================================================
# 2. COUNSELOR WORKBENCH API & SSE STREAMING ENDPOINTS
# ==============================================================================

def _to_web_asset_url(fs_path: Optional[str]) -> Optional[str]:
    """Converts a local filesystem path under assets/ or deliverables/ into a web-servable URL."""
    if not fs_path:
        return None
    p = Path(fs_path)
    try:
        rel_assets = p.resolve().relative_to(ASSETS_DIR.resolve())
        return f"/assets/{rel_assets.as_posix()}"
    except Exception:
        pass
    try:
        rel_deliv = p.resolve().relative_to(GENERATED_DECKS_DIR.resolve())
        return f"/deliverables/{rel_deliv.as_posix()}"
    except Exception:
        pass
    if p.exists():
        # Copy into assets/diagrams so it is web-servable
        dest = GENERATED_DIAGRAMS_DIR / p.name
        if p.resolve() != dest.resolve():
            import shutil
            shutil.copyfile(str(p), str(dest))
        return f"/assets/diagrams/{p.name}"
    return None


def _decorate_result_urls(result: Dict[str, Any]) -> Dict[str, Any]:
    """Attaches web-accessible URLs for .pptx, workbook .md, pamphlet/DRG links, cover/patch images, and per-slide visuals."""
    from src.config import get_merit_badge_metadata
    from src.tools.pamphlet_extractor import get_badge_cover_and_patch_paths

    badge_name = result.get("badge_name", "First Aid")
    meta = get_merit_badge_metadata(badge_name) or {}
    research = result.get("research_artifact") or {}

    result["pamphlet_pdf_url"] = (
        research.get("pamphlet_pdf_url")
        or meta.get("pamphlet_pdf_url")
        or f"https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/{badge_name.replace(' ', '%20')}.pdf"
    )
    result["drg_url"] = (
        research.get("drg_url")
        or meta.get("drg_url")
        or f"https://www.scouting.org/merit-badges/{badge_name.lower().replace(' ', '-')}/"
    )
    result["category"] = meta.get("category", "Scouts BSA Merit Badge")

    cover_assets = get_badge_cover_and_patch_paths(badge_name)
    if cover_assets.get("cover_path"):
        base_cov_url = _to_web_asset_url(cover_assets["cover_path"])
        try:
            cov_sz = os.path.getsize(cover_assets["cover_path"])
            result["cover_url"] = f"{base_cov_url}?v={cov_sz}" if base_cov_url else None
        except Exception:
            result["cover_url"] = base_cov_url
    if cover_assets.get("patch_path"):
        base_patch_url = _to_web_asset_url(cover_assets["patch_path"])
        try:
            patch_sz = os.path.getsize(cover_assets["patch_path"])
            result["patch_url"] = f"{base_patch_url}?v={patch_sz}" if base_patch_url else None
        except Exception:
            result["patch_url"] = base_patch_url

    if result.get("output_path"):
        result["pptx_download_url"] = _to_web_asset_url(result["output_path"])
    if result.get("workbook_path"):
        result["workbook_download_url"] = _to_web_asset_url(result["workbook_path"])
        try:
            result["workbook_markdown"] = Path(result["workbook_path"]).read_text(encoding="utf-8")
        except Exception:
            result["workbook_markdown"] = ""

    storyboard = result.get("storyboard") or {}
    for slide in storyboard.get("slides", []):
        diag_path = slide.get("diagram_path")
        if diag_path:
            slide["diagram_url"] = _to_web_asset_url(diag_path)
            svg_candidate = Path(diag_path).with_suffix(".svg")
            if svg_candidate.exists():
                slide["svg_url"] = _to_web_asset_url(str(svg_candidate))
        else:
            slide["diagram_url"] = None
        orig_path = slide.get("original_diagram_path")
        if orig_path:
            slide["original_diagram_url"] = _to_web_asset_url(orig_path)
        for av_img in slide.get("available_images") or []:
            if isinstance(av_img, dict) and av_img.get("image_path"):
                av_img["image_url"] = _to_web_asset_url(av_img["image_path"]) or av_img.get("image_url", "")

    raw_cat = result.get("badge_image_catalog")
    cat_list = raw_cat.get("images", []) if isinstance(raw_cat, dict) else (raw_cat or [])
    for cat_img in cat_list:
        if isinstance(cat_img, dict) and cat_img.get("image_path"):
            cat_img["image_url"] = _to_web_asset_url(cat_img["image_path"]) or cat_img.get("image_url", "")
    return result


@app.get("/api/badges")
@app.get("/api/v1/badges")
async def list_merit_badges(
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Returns catalog of all 138 official Scouts BSA Merit Badges with category, Eagle status, and resource links."""
    from src.config import OFFICIAL_BSA_MERIT_BADGES_CATALOG
    from src.tools.scouting_scraper import BENCHMARK_BADGES_DATA

    badges = []
    categories_set = set()
    for entry in OFFICIAL_BSA_MERIT_BADGES_CATALOG:
        b_name = entry["badge_name"]
        cat = entry["category"]
        categories_set.add(cat)
        b_data = BENCHMARK_BADGES_DATA.get(b_name, {})
        reqs = b_data.get("requirements", [])
        badges.append({
            "badge_name": b_name,
            "category": cat,
            "is_eagle_required": bool(entry["is_eagle_required"]),
            "subrequirement_count": len(reqs) if reqs else 8,
            "pamphlet_pdf_url": b_data.get("pamphlet_pdf_url") or entry["pamphlet_pdf_url"],
            "drg_url": b_data.get("drg_url") or entry["drg_url"],
        })

    return {
        "badges": badges,
        "total_badges": len(badges),
        "categories": sorted(categories_set),
        "eagle_required_count": len(EAGLE_REQUIRED_BADGES),
    }


@app.post("/api/upload-logo")
@app.post("/api/v1/upload-logo")
async def api_upload_troop_logo(
    req: TroopLogoUploadRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Saves an uploaded Troop Custom Logo (.png, .jpg, .jpeg) to assets/custom_logos and returns its local path and web URL."""
    import base64
    import re as _re

    custom_logos_dir = ASSETS_DIR / "custom_logos"
    custom_logos_dir.mkdir(parents=True, exist_ok=True)

    raw_name = os.path.basename(req.filename or "troop_logo.png")
    base, ext = os.path.splitext(raw_name)
    ext_lower = ext.lower()
    if ext_lower not in (".png", ".jpg", ".jpeg"):
        ext_lower = ".png"
    safe_base = _re.sub(r"[^a-zA-Z0-9_\-]+", "_", base).strip("_") or "troop_logo"
    safe_filename = f"{safe_base}{ext_lower}"

    b64_str = req.data_url.strip()
    if "," in b64_str and b64_str.startswith("data:"):
        b64_str = b64_str.split(",", 1)[1]

    try:
        raw_bytes = base64.b64decode(b64_str)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {exc}")

    dest_path = custom_logos_dir / safe_filename
    dest_path.write_bytes(raw_bytes)
    return {
        "status": "SUCCESS",
        "filename": safe_filename,
        "logo_path": str(dest_path),
        "logo_url": f"/assets/custom_logos/{safe_filename}",
    }


@app.post("/api/workflow/run")
@app.post("/api/v1/workflow/run")
async def api_run_workflow(
    req: WorkflowRunRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Executes the full multi-agent workflow and returns decorated A2UI & slide deck payloads."""
    t0 = time.perf_counter()
    counselor_info = {
        "counselor_name": req.counselor_name,
        "troop_affiliation": req.troop_affiliation,
        "location_or_zip": req.location_or_zip or "",
        "email_address": req.email_address,
        "phone_number": req.phone_number,
        "custom_troop_logo_path": req.custom_troop_logo_path,
    }
    result = await asyncio.to_thread(
        run_merit_badge_workflow,
        badge_name=req.badge_name,
        depth_mode=req.depth_mode,
        counselor_info=counselor_info,
        session_id=req.session_id,
        enable_deep_research=req.enable_deep_research,
        beautification_tier=req.beautification_tier,
        schedule_format=req.schedule_format,
        audience_level=req.audience_level,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    finops = result.get("finops_cost_estimate") or {}
    METRICS_COLLECTOR.record_workflow_run(
        latency_ms=elapsed_ms,
        tokens_used=int(finops.get("estimated_input_tokens", 0)) + int(finops.get("estimated_output_tokens", 0)),
        cost_usd=float(finops.get("estimated_cost_usd", 0.0)),
        cache_hit=bool(result.get("cache_hit", False)),
    )
    if result.get("status") not in ("SUCCESS", "REVIEW_WARNING"):
        return JSONResponse(status_code=400, content=result)
    result["counselor_info"] = counselor_info
    if req.custom_troop_logo_path:
        result["custom_troop_logo_url"] = _to_web_asset_url(req.custom_troop_logo_path)
    decorated = _decorate_result_urls(result)
    if req.webhook_url:
        decorated["webhook_notification"] = {
            "webhook_url": req.webhook_url,
            "delivery_status": "QUEUED",
        }
    return decorated


@app.get("/api/workflow/stream")
@app.get("/api/v1/workflow/stream")
async def api_stream_workflow(
    badge_name: str = Query("First Aid"),
    depth_mode: str = Query("Deep Dive / Camp School Deck"),
    counselor_name: str = Query("Scoutmaster Bob"),
    troop_affiliation: str = Query("Troop 123, My Council"),
    location_or_zip: str = Query(""),
    email_address: str = Query("counselor@troop123.org"),
    phone_number: str = Query("(000) 555-1234"),
    custom_troop_logo_path: Optional[str] = Query(None),
    enable_deep_research: bool = Query(True),
    beautification_tier: str = Query("BEAUTIFIED"),
    schedule_format: str = Query("3 Troop Meetings (45 min each)"),
    audience_level: str = Query("All Scouts (Ages 11–17)"),
) -> StreamingResponse:
    """Streams live Server-Sent Events (SSE) as each agent completes its work."""
    counselor_info = {
        "counselor_name": counselor_name,
        "troop_affiliation": troop_affiliation,
        "location_or_zip": location_or_zip,
        "email_address": email_address,
        "phone_number": phone_number,
        "custom_troop_logo_path": custom_troop_logo_path,
    }

    async def event_generator():
        async for ev in stream_merit_badge_workflow_events(
            badge_name=badge_name,
            depth_mode=depth_mode,
            counselor_info=counselor_info,
            enable_deep_research=enable_deep_research,
            beautification_tier=beautification_tier,
            schedule_format=schedule_format,
            audience_level=audience_level,
        ):
            if ev.get("event") == "workflow_complete" and ev.get("result"):
                ev["result"]["counselor_info"] = counselor_info
                if custom_troop_logo_path:
                    ev["result"]["custom_troop_logo_url"] = _to_web_asset_url(custom_troop_logo_path)
                ev["result"] = _decorate_result_urls(ev["result"])
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/slide/regenerate")
@app.post("/api/v1/slide/regenerate")
async def api_regenerate_slide(
    req: SlideRegenerateRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Surgically updates a single slide's graphic, magazine theme, palette, and archetype layout, and rebuilds the .pptx."""
    from src.agents.beautifier import generate_ai_editorial_illustration
    from src.agents.image_studio import register_image_in_badge_catalog
    from src.tools.pptx_builder import (
        CounselorTitleSlideInfo,
        PowerPointBuildRequest,
        SlideSpec,
        generate_bsa_slide_deck_pptx,
    )

    req_num = str(req.slide_data.get("req_number") or (req.slide_index + 1))
    title = str(req.slide_data.get("title") or f"Req {req_num}")
    bullets = req.slide_data.get("bullet_points") or []
    palette_key = req.new_accent_palette or req.slide_data.get("accent_palette_key", "NAVY_GOLD")
    vis_theme = req.new_visual_theme or req.slide_data.get("visual_theme", "NUMBERED_STEP_CARDS")
    tier = str(req.slide_data.get("beautification_tier") or "BEAUTIFIED").upper()
    effective_archetype = str(req.new_archetype or req.slide_data.get("archetype") or "SPLIT_VISUAL_EXPLAINER")
    vis_mode = str(req.visual_source_mode or "keep_current").lower()
    vis_caption = str(req.slide_data.get("visual_caption") or title)

    if vis_mode == "none" or (effective_archetype == "CONCEPT_TEXT_SLIDE" and vis_mode in ("keep_current", "none")):
        png_path = None
        png_url = None
        svg_url = None
        vis_label = "None (Full-Width Text Layout)"
        if effective_archetype in ("SPLIT_VISUAL_EXPLAINER", "FULL_BLEED_IMAGE_EXPLAINER"):
            effective_archetype = "CONCEPT_TEXT_SLIDE"
        asset_payload = {"status": "SUCCESS", "visual_source_mode": "none"}
    elif vis_mode == "restore_original":
        orig_p = req.slide_data.get("original_diagram_path")
        if orig_p and os.path.exists(str(orig_p)):
            png_path = str(orig_p)
            png_url = _to_web_asset_url(png_path)
            svg_url = None
            vis_label = str(req.slide_data.get("original_visual_source_label") or "Official BSA Pamphlet Figure")
            vis_caption = str(req.slide_data.get("original_visual_caption") or title)
            orig_arch = str(req.slide_data.get("original_archetype") or "SPLIT_VISUAL_EXPLAINER")
            effective_archetype = orig_arch if orig_arch != "CONCEPT_TEXT_SLIDE" else "SPLIT_VISUAL_EXPLAINER"
        else:
            png_path = None
            png_url = None
            svg_url = None
            vis_label = "None (Originally Text-Only Slide)"
            effective_archetype = str(req.slide_data.get("original_archetype") or "CONCEPT_TEXT_SLIDE")
        asset_payload = {"status": "SUCCESS", "visual_source_mode": "restore_original"}
    elif vis_mode == "custom_image" and req.custom_image_path and os.path.exists(str(req.custom_image_path)):
        png_path = str(req.custom_image_path)
        png_url = _to_web_asset_url(png_path)
        svg_url = None
        vis_label = str(req.custom_image_source_label or "Selected Merit Badge Catalog Image")
        vis_caption = str(req.custom_image_caption or title)
        if effective_archetype in ("CONCEPT_TEXT_SLIDE", "SOURCES_AND_REFERENCES"):
            effective_archetype = "SPLIT_VISUAL_EXPLAINER"
        register_image_in_badge_catalog(
            req.badge_name,
            {
                "badge_name": req.badge_name,
                "req_number": req_num,
                "slide_title": title,
                "title": vis_caption[:68],
                "description": f"Selected image for Requirement {req_num} ({title}).",
                "source_type": "WEB_IMAGE_SEARCH" if "_web_search_cache" in png_path else "CUSTOM_IMAGE",
                "source_label": vis_label,
                "image_path": png_path,
                "image_url": png_url or "",
            },
        )
        asset_payload = {"status": "SUCCESS", "visual_source_mode": "custom_image", "image_path": png_path}
    elif vis_mode == "ai_hero":
        hero_res = await asyncio.to_thread(
            generate_ai_editorial_illustration,
            badge_name=req.badge_name,
            slide_title=title,
            visual_prompt=" | ".join(bullets[:4]) if bullets else title,
            accent_palette_key=palette_key,
            req_number=req_num,
            bullet_points=bullets,
            beautification_tier=tier if tier in ("BEAUTIFIED", "STUDIO") else "STUDIO",
        )
        png_path = hero_res.get("image_path")
        png_url = _to_web_asset_url(png_path)
        svg_url = None
        is_nano_hero = hero_res.get("hero_source") == "NANO_BANANA_AI" or str(png_path or "").endswith("_nano_hero.png")
        eff_st = str(hero_res.get("effective_style") or ("Nano Banana Hero" if is_nano_hero else "EDGE Skill Concept Map"))
        vis_label = (
            "🍌 Nano Banana Hero"
            if is_nano_hero
            else "EDGE Skill Concept Map (SlideBeautifierAgent)"
        )
        vis_caption = (
            title
            if is_nano_hero
            else f"EDGE Skill Concept Map — {title}"
        )
        if effective_archetype == "CONCEPT_TEXT_SLIDE":
            effective_archetype = "SPLIT_VISUAL_EXPLAINER"
        if png_path and os.path.exists(str(png_path)):
            register_image_in_badge_catalog(
                req.badge_name,
                {
                    "badge_name": req.badge_name,
                    "req_number": req_num,
                    "slide_title": title,
                    "title": title[:68] if is_nano_hero else f"EDGE Skill Concept Map: {title}"[:68],
                    "description": (
                        f"Context-grounded Nano Banana ({eff_st}) hero graphic for Requirement {req_num} ({title})."
                        if is_nano_hero
                        else f"220-DPI BSA EDGE Method concept map for Requirement {req_num} ({title})."
                    ),
                    "source_type": "NANO_BANANA_HERO" if is_nano_hero else "EDGE_CONCEPT_MAP",
                    "source_label": "🍌 Nano Banana Hero" if is_nano_hero else "✨ EDGE Skill Concept Map",
                    "image_path": str(png_path),
                    "image_url": png_url or "",
                },
            )
        asset_payload = hero_res
    else:
        # 'keep_current' or 'pamphlet': preserve the slide's existing diagram or original diagram without overwriting with generic vector art
        curr_p = req.slide_data.get("diagram_path")
        orig_p = req.slide_data.get("original_diagram_path")
        chosen_p = orig_p if (vis_mode == "pamphlet" and orig_p and os.path.exists(str(orig_p))) else curr_p
        if chosen_p and os.path.exists(str(chosen_p)):
            png_path = str(chosen_p)
            png_url = _to_web_asset_url(png_path)
            svg_url = None
            vis_label = str(req.slide_data.get("visual_source_label") or "Official BSA Pamphlet / Instructional Figure")
        else:
            png_path = None
            png_url = None
            svg_url = None
            vis_label = "None (Full-Width Text Layout)"
        asset_payload = {"status": "SUCCESS", "visual_source_mode": vis_mode, "image_path": png_path}

    rebuilt_pptx_url: Optional[str] = None
    if req.storyboard_slides:
        try:
            slides_copy = [dict(s) for s in req.storyboard_slides]
            if 0 <= req.slide_index < len(slides_copy):
                target_s = slides_copy[req.slide_index]
                target_s["archetype"] = effective_archetype
                target_s["visual_theme"] = vis_theme
                target_s["accent_palette_key"] = palette_key
                target_s["visual_source_label"] = vis_label
                target_s["visual_caption"] = vis_caption
                target_s["diagram_path"] = png_path
                target_s["ai_hero_image_path"] = png_path if vis_mode == "ai_hero" else None
                if png_path is None and target_s.get("full_bullet_points"):
                    target_s["bullet_points"] = list(target_s["full_bullet_points"])
            c_info = CounselorTitleSlideInfo(**req.counselor_info) if req.counselor_info else None
            out_file = req.output_path or str(
                GENERATED_DECKS_DIR / f"{req.badge_name.strip().replace(' ', '_')}_{tier}_Regen_Merit_Badge_Deck.pptx"
            )
            build_res = await asyncio.to_thread(
                generate_bsa_slide_deck_pptx,
                PowerPointBuildRequest(
                    badge_name=req.badge_name,
                    slides=[SlideSpec(**s) for s in slides_copy],
                    counselor_info=c_info,
                    output_path=out_file,
                ),
            )
            if build_res.get("output_path"):
                rebuilt_pptx_url = _to_web_asset_url(build_res["output_path"])
        except Exception as exc:
            logger.warning("Failed to rebuild PPTX during slide regenerate: %s", exc)

    return {
        "status": "SUCCESS",
        "slide_index": req.slide_index,
        "new_archetype": effective_archetype,
        "new_visual_theme": vis_theme,
        "new_accent_palette": palette_key,
        "visual_source_mode": vis_mode,
        "visual_source_label": vis_label,
        "visual_caption": vis_caption,
        "asset": asset_payload,
        "diagram_path": png_path,
        "diagram_url": png_url,
        "svg_url": svg_url,
        "pptx_download_url": rebuilt_pptx_url,
    }


@app.get("/api/counselor-profile")
@app.get("/api/v1/counselor-profile")
async def api_get_counselor_profile(
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Loads locally cached Counselor profile (in local mode) or returns browser-localStorage guidance (in Cloud Run)."""
    from src.memory.session_store import load_local_counselor_profile

    profile = load_local_counselor_profile()
    if profile.get("custom_troop_logo_path"):
        profile["custom_troop_logo_url"] = _to_web_asset_url(profile["custom_troop_logo_path"])
    return {"status": "SUCCESS", "profile": profile}


@app.post("/api/counselor-profile")
@app.post("/api/v1/counselor-profile")
async def api_save_counselor_profile(
    req: CounselorProfileSaveRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Persists Counselor profile locally in `.cache/counselor_profile.json` (`0600` owner-only permissions)."""
    from src.memory.session_store import save_local_counselor_profile

    return save_local_counselor_profile(req.model_dump())


@app.delete("/api/counselor-profile")
@app.delete("/api/v1/counselor-profile")
async def api_delete_counselor_profile(
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Clears locally cached Counselor profile."""
    from src.memory.session_store import clear_local_counselor_profile

    return clear_local_counselor_profile()


@app.get("/api/badge/images")
@app.get("/api/v1/badge/images")
async def api_get_badge_image_catalog(
    badge_name: str = Query("First Aid"),
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Returns all cached images and descriptions for a Merit Badge."""
    from src.agents.image_studio import get_badge_image_catalog

    res = await asyncio.to_thread(get_badge_image_catalog, badge_name=badge_name)
    for item in res.get("images") or []:
        if item.get("image_path"):
            item["image_url"] = _to_web_asset_url(item["image_path"]) or item.get("image_url", "")
    return res


@app.delete("/api/badge/images")
@app.delete("/api/v1/badge/images")
async def api_purge_badge_images(
    badge_name: Optional[str] = Query(None),
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Purges previously generated/cached Web Search and Nano Banana AI images while also cleaning any synthetic pamphlet covers."""
    from src.agents.image_studio import purge_cached_web_and_ai_images
    from src.tools.pamphlet_extractor import clear_corrupted_pamphlet_cover_caches

    purge_res = await asyncio.to_thread(purge_cached_web_and_ai_images, badge_name=badge_name)
    cover_res = await asyncio.to_thread(
        clear_corrupted_pamphlet_cover_caches,
        refill_badges=[badge_name] if badge_name else None,
    )
    purge_res["pamphlet_cover_cache_cleanup"] = cover_res
    return purge_res


@app.post("/api/cache/clear")
@app.post("/api/v1/cache/clear")
@app.get("/api/cache/clear")
@app.get("/api/v1/cache/clear")
async def api_clear_and_refill_caches(
    badge_name: Optional[str] = Query(None),
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Clears any synthetic 720x1040 pamphlet covers and web cover art, and refills official BSA pamphlet covers on demand."""
    from src.tools.pamphlet_extractor import clear_corrupted_pamphlet_cover_caches

    return await asyncio.to_thread(
        clear_corrupted_pamphlet_cover_caches,
        refill_badges=[badge_name] if badge_name else ["First Aid", "Camping", "Weather", "Robotics"],
    )


@app.post("/api/slide/search-web-images")
@app.post("/api/v1/slide/search-web-images")
async def api_search_web_images(
    req: WebImageSearchRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Invokes `WebImageSearchAgent` to search and cache Wikimedia / reference images for a slide."""
    from src.agents.image_studio import search_web_images_for_slide

    res = await asyncio.to_thread(
        search_web_images_for_slide,
        badge_name=req.badge_name,
        slide_title=req.slide_title,
        req_number=req.req_number,
        search_query=req.search_query,
        bullet_points=req.bullet_points,
        max_results=req.max_results,
    )
    for item in res.get("results") or []:
        if item.get("image_path"):
            item["image_url"] = _to_web_asset_url(item["image_path"]) or item.get("image_url", "")
    return res


@app.post("/api/slide/estimate-image-cost")
@app.post("/api/v1/slide/estimate-image-cost")
async def api_estimate_nano_banana_cost(
    req: NanoBananaCostRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Computes FinOps USD cost estimate and consent prompt before running `NanoBananaImageAgent`."""
    from src.agents.image_studio import estimate_nano_banana_image_cost

    return estimate_nano_banana_image_cost(
        badge_name=req.badge_name,
        slide_title=req.slide_title,
        req_number=req.req_number,
        custom_prompt=req.custom_prompt or req.prompt,
        visual_style=req.visual_style,
        include_humans=req.include_humans,
        num_images=req.num_images,
    )


@app.post("/api/slide/generate-nano-banana-image")
@app.post("/api/v1/slide/generate-nano-banana-image")
async def api_generate_nano_banana_image(
    req: NanoBananaGenerateRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Invokes `NanoBananaImageAgent` (enforcing `user_consented=True`) to create & cache a custom slide graphic."""
    from src.agents.image_studio import generate_nano_banana_slide_image

    eff_req_num = req.req_number if (req.req_number and req.req_number != "1") else (req.requirement_id or req.req_number or "1")
    res = await asyncio.to_thread(
        generate_nano_banana_slide_image,
        badge_name=req.badge_name,
        slide_title=req.slide_title,
        req_number=eff_req_num,
        custom_prompt=req.custom_prompt or req.prompt,
        bullet_points=req.bullet_points,
        visual_style=req.visual_style,
        include_humans=req.include_humans,
        accent_palette_key=req.accent_palette_key,
        beautification_tier=req.beautification_tier,
        user_consented=req.user_consented,
    )
    if res.get("status") == "SUCCESS" and res.get("image_entry"):
        img_p = res["image_entry"].get("image_path")
        if img_p:
            web_u = _to_web_asset_url(img_p) or res["image_entry"].get("image_url", "")
            res["image_entry"]["image_url"] = web_u
            res["image_url"] = web_u
    return res


@app.post("/api/slide/upload-image")
@app.post("/api/v1/slide/upload-image")
@app.post("/api/badge/images/upload")
async def api_upload_slide_image(
    req: SlideImageUploadRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Saves, validates, and caches a Counselor-uploaded local image file into the Merit Badge catalog ($0.00 cost)."""
    from src.agents.image_studio import upload_custom_slide_image

    res = await asyncio.to_thread(
        upload_custom_slide_image,
        badge_name=req.badge_name,
        image_data=req.data_url or req.image_base64,
        filename=req.filename,
        title=req.title,
        description=req.description,
        req_number=req.req_number,
        slide_title=req.slide_title,
    )
    if res.get("status") == "SUCCESS" and res.get("image_entry"):
        img_p = res["image_entry"].get("image_path")
        if img_p:
            web_u = _to_web_asset_url(img_p) or res["image_entry"].get("image_url", "")
            res["image_entry"]["image_url"] = web_u
            res["entry"]["image_url"] = web_u
            res["image_url"] = web_u
    return res


@app.post("/api/hitl/confirm")
@app.post("/api/v1/hitl/confirm")
async def api_confirm_hitl(
    payload: Dict[str, Any],
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Validates Counselor HITL sign-off and returns a cryptographic confirmation_token."""
    return request_counselor_confirmation(payload)


# ==============================================================================
# 3. OPERATIONAL HEALTH, READINESS, TELEMETRY & HITL FEEDBACK ENDPOINTS
# ==============================================================================

@app.get("/health")
@app.get("/api/health")
@app.get("/api/v1/health")
async def health_liveness_probe() -> Dict[str, Any]:
    """Fast container liveness probe for Cloud Run / Kubernetes."""
    return {
        "status": "UP",
        "service": "scouts-bsa-merit-badge-agent",
        "version": "3.1.0",
        "timestamp_epoch": round(time.time(), 3),
    }


@app.get("/readiness")
async def readiness_deep_probe() -> Dict[str, Any]:
    """Deep dependency readiness check verifying SQLite session store, catalog, and FinOps policy."""
    from src.memory.session_store import PersistentSessionStore

    checks: Dict[str, Any] = {}
    overall_ready = True

    # 1. SQLite session store check
    try:
        store = PersistentSessionStore()
        store.save_session_sync("readiness_probe", "First Aid", {}, [{"probe_ts": time.time()}])
        loaded = store.get_session_sync("readiness_probe")
        checks["session_store"] = "READY" if loaded else "DEGRADED"
    except Exception as exc:
        checks["session_store"] = f"FAILED: {exc}"
        overall_ready = False


    # 2. 138-badge catalog check
    catalog_len = len(OFFICIAL_BSA_MERIT_BADGES_CATALOG)
    checks["merit_badge_catalog"] = "READY" if catalog_len >= 138 else f"INCOMPLETE ({catalog_len})"
    if catalog_len < 138:
        overall_ready = False

    # 3. FinOps & Model Armor policy config files check
    finops_ok = (CONFIG_DIR / "finops_model_policy.json").exists()
    armor_ok = (CONFIG_DIR / "model_armor_security_policy.json").exists()
    checks["policy_configs"] = "READY" if (finops_ok and armor_ok) else "MISSING_CONFIG"
    if not (finops_ok and armor_ok):
        overall_ready = False

    # 4. Circuit breakers snapshot
    metrics_snap = METRICS_COLLECTOR.snapshot()
    checks["circuit_breakers"] = metrics_snap["circuit_breakers"]

    status_code = 200 if overall_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "READY" if overall_ready else "NOT_READY",
            "checks": checks,
            "timestamp_epoch": round(time.time(), 3),
        },
    )


@app.get("/api/metrics")
@app.get("/api/v1/metrics")
async def get_runtime_metrics(
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Returns real-time AI telemetry, latency percentiles, circuit breaker states, and audit events."""
    snap = METRICS_COLLECTOR.snapshot()
    snap["recent_compliance_audit_events"] = get_compliance_audit_events(limit=20)
    return snap


@app.post("/api/feedback")
@app.post("/api/v1/feedback")
async def submit_counselor_feedback(
    req: CounselorFeedbackRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Captures Human-in-the-Loop Counselor ratings, persists to SQLite, and auto-promotes verified >=4/5 sessions to the Golden Suite."""
    from scripts.eval_gate import promote_session_to_golden_dataset
    from src.memory.session_store import _default_store
    from src.schemas import CURRENT_SCHEMA_VERSION

    payload = req.model_dump()
    record = METRICS_COLLECTOR.record_counselor_feedback(payload)

    promoted_to_golden = bool(req.rating >= 4 and req.requirement_accuracy_verified)
    promotion_result: Optional[Dict[str, Any]] = None
    golden_dataset_size = 0

    if promoted_to_golden:
        try:
            promotion_result = promote_session_to_golden_dataset(
                {
                    "badge_name": req.badge_name,
                    "is_eagle_required": req.badge_name in EAGLE_REQUIRED_BADGES,
                    "requirement_count": max(1, int(req.requirement_count or 5)),
                    "session_id": req.session_id,
                    "counselor_name": req.counselor_name,
                }
            )
            golden_dataset_size = int(promotion_result.get("total_golden_extensions", 0))
        except Exception as exc:
            logger.warning("Golden dataset promotion warning: %s", exc)
            promoted_to_golden = False

    sqlite_rec = _default_store.record_hitl_feedback_sync(
        badge_name=req.badge_name,
        session_id=req.session_id,
        counselor_name=req.counselor_name,
        rating=req.rating,
        thumbs_up=req.thumbs_up,
        requirement_accuracy_verified=req.requirement_accuracy_verified,
        promoted_to_golden=promoted_to_golden,
        comments=req.comments,
        schema_version=CURRENT_SCHEMA_VERSION,
    )

    return {
        "status": "RECORDED",
        "schema_version": CURRENT_SCHEMA_VERSION,
        "promoted_to_golden_dataset": promoted_to_golden,
        "sqlite_persisted": True,
        "golden_dataset_size": golden_dataset_size,
        "golden_extensions_count": golden_dataset_size,
        "golden_dataset_path": "tests/data/golden_extensions.json",
        "golden_promotion": promotion_result,
        "feedback": record,
        "sqlite_record": sqlite_rec,
        "summary": METRICS_COLLECTOR.get_feedback_summary(),
    }


@app.get("/api/feedback")
@app.get("/api/v1/feedback")
async def list_counselor_feedback(
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Returns aggregated Human-in-the-Loop Counselor feedback statistics and SQLite records."""
    from src.memory.session_store import _default_store
    from src.schemas import CURRENT_SCHEMA_VERSION

    summary = dict(METRICS_COLLECTOR.get_feedback_summary() or {})
    summary["schema_version"] = CURRENT_SCHEMA_VERSION
    summary["sqlite_feedback_records"] = _default_store.list_hitl_feedback_sync(limit=25)
    return summary


@app.get("/api/v1/prompts/manifest")
async def get_prompt_manifest_endpoint(
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Returns the active versioned prompt manifest with SHA-256 content hashes."""
    return load_prompt_manifest()


@app.get("/", response_class=HTMLResponse)
async def serve_a2ui_workbench() -> HTMLResponse:
    """Serves the Google Material 3 Expressive A2UI Counselor Workbench."""
    index_file = UI_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>UI loading...</h1>", status_code=200)
    return HTMLResponse(index_file.read_text(encoding="utf-8"))

