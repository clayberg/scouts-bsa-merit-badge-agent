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
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
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
    select_model_for_task,
)
from src.agents.coordinator import (
    run_merit_badge_workflow,
    stream_merit_badge_workflow_events,
)
from src.agents.guardrails import get_compliance_audit_events
from src.observability.telemetry_store import get_zero_pii_telemetry_store
from src.resilience import METRICS_COLLECTOR, reset_all_circuit_breakers
from src.security import (
    ADMIN_SESSION_COOKIE_NAME,
    check_admin_session_status,
    create_admin_session_cookie,
    verify_admin_auth,
    verify_admin_token_value,
    verify_caller_auth,
)
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
    """Attaches `X-API-Version: 1.2.0`, RFC 8594 `Deprecation`/`Sunset` headers, and lazy-hydrates missing `/assets/` files on demand."""
    from src.schemas import CURRENT_SCHEMA_VERSION

    path = str(getattr(request, "url", "") and request.url.path or "")
    if path.startswith("/assets/"):
        rel_asset = path.lstrip("/")
        local_asset = PROJECT_ROOT / rel_asset
        if not local_asset.exists():
            try:
                from src.tools.asset_hydrator import hydrate_single_asset_on_demand

                await asyncio.to_thread(hydrate_single_asset_on_demand, rel_asset)
            except Exception:
                pass

    response = await call_next(request)
    response.headers["X-API-Version"] = CURRENT_SCHEMA_VERSION
    if path.startswith("/api/") and not path.startswith("/api/v1/"):
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = "2027-01-01"
    elif path.startswith("/assets/construction_anim/"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif path == "/" or path.startswith("/ui/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    elif path.startswith("/assets/badge_emblems/") or path.startswith("/assets/pamphlet_covers/"):
        response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
    return response


# Mount static directories
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
app.mount("/deliverables", StaticFiles(directory=str(GENERATED_DECKS_DIR)), name="deliverables")
app.mount("/ui", StaticFiles(directory=str(UI_DIR)), name="ui")
DOCS_IMAGES_DIR = PROJECT_ROOT / "docs" / "images"
DOCS_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/docs/images", StaticFiles(directory=str(DOCS_IMAGES_DIR)), name="docs_images")

# In-memory A2A task registry
_A2A_TASKS: Dict[str, Dict[str, Any]] = {}
_A2A_TASKS_LOCK = threading.Lock()


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
    template_id: Optional[str] = Field(None, description="Optional PowerPoint template ID override.")
    deck_style: Optional[Dict[str, Any]] = Field(None, description="Optional DeckStyleConfig override dictionary.")
    option_track: Optional[str] = Field(
        "ALL",
        description="Optional multi-option Merit Badge track filter ('ALL', 'A', 'B', 'C', 'D', etc.).",
    )


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
    template_id: Optional[str] = Field("default_workbench", description="Optional active PowerPoint template ID.")
    deck_style: Optional[Dict[str, Any]] = Field(None, description="Optional deck-wide DeckStyleConfig dictionary.")
    container_style_override: Optional[str] = Field(None, description="Optional per-slide container style override ('CLEAN_OPEN', 'LEFT_ACCENT_LINE', 'BOXED_CARDS').")
    image_frame_style_override: Optional[str] = Field(None, description="Optional per-slide image frame style override ('FRAMELESS_CLEAN', 'SOFT_SHADOW', 'FRAMED_CARD').")
    header_chrome_style_override: Optional[str] = Field(None, description="Optional per-slide header chrome style override ('MINIMAL_ACCENT', 'SOLID_PILL').")


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
    include_slide_context: bool = True
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
    include_slide_context: bool = True
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
        "url": os.getenv("PUBLIC_BASE_URL", "http://localhost:8085"),
        "version": "3.1.0",
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

    # Also allow extracting badge_name from message parts across all 144 official Merit Badges
    parts = req.message.get("parts", [])
    sorted_catalog_names = sorted(
        (
            str(item.get("badge_name") or item.get("name"))
            for item in OFFICIAL_BSA_MERIT_BADGES_CATALOG
            if item.get("badge_name") or item.get("name")
        ),
        key=len,
        reverse=True,
    )
    for part in parts:
        text = str(part.get("text", "")).lower()
        if not text:
            continue
        matched = False
        for candidate in sorted_catalog_names:
            if candidate.lower() in text:
                badge_name = candidate
                matched = True
                break
        if matched:
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
    with _A2A_TASKS_LOCK:
        _A2A_TASKS[task_id] = task_record
    return task_record


@app.get("/a2a/tasks/{task_id}")
async def a2a_get_task(
    task_id: str,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    with _A2A_TASKS_LOCK:
        if task_id not in _A2A_TASKS:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return _A2A_TASKS[task_id]


@app.post("/a2a/tasks/{task_id}/cancel")
async def a2a_cancel_task(
    task_id: str,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    with _A2A_TASKS_LOCK:
        if task_id not in _A2A_TASKS:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        _A2A_TASKS[task_id]["status"]["state"] = "canceled"
        return _A2A_TASKS[task_id]



# ==============================================================================
# 2. COUNSELOR WORKBENCH API & SSE STREAMING ENDPOINTS
# ==============================================================================

ASYNC_RENDER_CONCURRENCY_SEMAPHORE = asyncio.Semaphore(4)


def _validate_safe_pptx_output_path(output_path: Optional[str], default_filename: str = "Deck.pptx") -> str:
    """Confines any caller-supplied `.pptx` output path to `GENERATED_DECKS_DIR`, `ASSETS_DIR`, or system tempdir."""
    import tempfile

    if not output_path or not str(output_path).strip():
        return str((GENERATED_DECKS_DIR / default_filename).resolve())
    cand = Path(str(output_path).strip()).resolve()
    allowed_roots = (
        GENERATED_DECKS_DIR.resolve(),
        ASSETS_DIR.resolve(),
        Path(tempfile.gettempdir()).resolve(),
    )
    for root in allowed_roots:
        try:
            cand.relative_to(root)
            return str(cand)
        except ValueError:
            continue
    safe_name = os.path.basename(str(output_path).strip()) or default_filename
    if not safe_name.lower().endswith(".pptx"):
        safe_name += ".pptx"
    return str((GENERATED_DECKS_DIR / safe_name).resolve())


async def _async_rebuild_deck_pptx(**kwargs: Any) -> Dict[str, Any]:
    """Non-blocking, semaphore-bounded wrapper around `rebuild_deck_pptx_from_storyboard`."""
    from src.tools.pptx_builder import rebuild_deck_pptx_from_storyboard

    if "output_path" in kwargs:
        kwargs["output_path"] = _validate_safe_pptx_output_path(kwargs.get("output_path"))
    async with ASYNC_RENDER_CONCURRENCY_SEMAPHORE:
        return await asyncio.to_thread(rebuild_deck_pptx_from_storyboard, **kwargs)


def _load_or_build_cached_default_deck(badge_name: str, counselor_info: Any = None) -> Dict[str, Any]:
    """Loads or builds the default teaching slide deck for `badge_name`."""
    from src.agents.coordinator import run_merit_badge_workflow

    c_dict = (
        counselor_info.model_dump()
        if hasattr(counselor_info, "model_dump")
        else (counselor_info if isinstance(counselor_info, dict) else None)
    )
    return run_merit_badge_workflow(badge_name=badge_name, counselor_info=c_dict)


def _to_web_asset_url(fs_path: Optional[str]) -> Optional[str]:
    """Converts a local filesystem path under allowlisted asset/deliverable directories into a web-servable URL."""
    import tempfile

    if not fs_path:
        return None
    p = Path(fs_path)
    try:
        resolved_p = p.resolve()
    except Exception:
        return None
    try:
        rel_assets = resolved_p.relative_to(ASSETS_DIR.resolve())
        return f"/assets/{rel_assets.as_posix()}"
    except Exception:
        pass
    try:
        rel_deliv = resolved_p.relative_to(GENERATED_DECKS_DIR.resolve())
        return f"/deliverables/{rel_deliv.as_posix()}"
    except Exception:
        pass
    allowed_copy_roots = (
        ASSETS_DIR.resolve(),
        GENERATED_DECKS_DIR.resolve(),
        (PROJECT_ROOT / "data").resolve(),
        Path(tempfile.gettempdir()).resolve(),
    )
    is_allowed_source = False
    for root in allowed_copy_roots:
        try:
            resolved_p.relative_to(root)
            is_allowed_source = True
            break
        except ValueError:
            continue
    if is_allowed_source and resolved_p.is_file():
        # Copy into assets/diagrams so it is web-servable
        dest = GENERATED_DIAGRAMS_DIR / resolved_p.name
        if resolved_p != dest.resolve():
            import shutil
            if not dest.exists() or dest.stat().st_size != resolved_p.stat().st_size or dest.stat().st_mtime < resolved_p.stat().st_mtime:
                shutil.copyfile(str(resolved_p), str(dest))
        return f"/assets/diagrams/{resolved_p.name}"
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
        for sc_img in slide.get("slide_image_choices") or []:
            if isinstance(sc_img, dict) and sc_img.get("image_path"):
                sc_img["image_url"] = _to_web_asset_url(sc_img["image_path"]) or sc_img.get("image_url", "")

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
    """Returns catalog of all 149 Scouts BSA Merit Badges (144 standard + 5 Test Lab Pilots) with category, Eagle status, Test Lab/Discontinued flags, option tracks, and resource links."""
    from src.config import (
        COMPANION_BADGE_PAIRINGS,
        DISCONTINUED_BADGES,
        OFFICIAL_BSA_MERIT_BADGES_CATALOG,
        TEST_LAB_PILOT_BADGES,
        is_discontinued_badge,
        is_test_lab_badge,
    )
    from src.tools.scouting_scraper import BENCHMARK_BADGES_DATA, get_badge_option_tracks

    badges = []
    categories_set = set()
    for entry in OFFICIAL_BSA_MERIT_BADGES_CATALOG:
        b_name = entry["badge_name"]
        cat = entry["category"]
        categories_set.add(cat)
        b_data = BENCHMARK_BADGES_DATA.get(b_name, {})
        reqs = b_data.get("requirements", [])
        opt_tracks = get_badge_option_tracks(b_name)
        is_tl = bool(entry.get("is_test_lab_pilot") or is_test_lab_badge(b_name))
        is_disc = bool(entry.get("is_discontinued") or is_discontinued_badge(b_name))
        badges.append({
            "badge_name": b_name,
            "category": cat,
            "is_eagle_required": bool(entry["is_eagle_required"]),
            "is_test_lab_pilot": is_tl,
            "is_discontinued": is_disc,
            "status_badge": entry.get("status_badge") or ("DISCONTINUED" if is_disc else ("TEST_LAB_PILOT" if is_tl else "ACTIVE")),
            "companion_badges": COMPANION_BADGE_PAIRINGS.get(b_name, []),
            "subrequirement_count": len(reqs) if reqs else 8,
            "pamphlet_pdf_url": b_data.get("pamphlet_pdf_url") or entry["pamphlet_pdf_url"],
            "drg_url": b_data.get("drg_url") or entry["drg_url"],
            "option_tracks": opt_tracks,
            "has_option_tracks": len(opt_tracks) > 0,
        })

    return {
        "badges": badges,
        "total_badges": len(badges),
        "categories": sorted(categories_set),
        "eagle_required_count": len(EAGLE_REQUIRED_BADGES),
        "test_lab_pilot_count": len(TEST_LAB_PILOT_BADGES),
        "discontinued_count": len(DISCONTINUED_BADGES),
    }


@app.get("/api/badges/{badge_name}/options")
@app.get("/api/v1/badges/{badge_name}/options")
async def api_get_badge_option_tracks(
    badge_name: str,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Returns structured Option Tracks for a multi-option Merit Badge (e.g., Golf Option A vs. Option B)."""
    from src.tools.scouting_scraper import get_badge_option_tracks

    tracks = get_badge_option_tracks(badge_name)
    return {
        "status": "SUCCESS",
        "badge_name": badge_name,
        "has_options": len(tracks) > 0,
        "has_option_tracks": len(tracks) > 0,
        "option_tracks": tracks,
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
    if len(raw_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Uploaded logo exceeds maximum allowed size of 5 MB.")

    dest_path = custom_logos_dir / safe_filename
    dest_path.write_bytes(raw_bytes)
    return {
        "status": "SUCCESS",
        "filename": safe_filename,
        "logo_path": str(dest_path),
        "logo_url": f"/assets/custom_logos/{safe_filename}",
    }


_WORKFLOW_RESULT_CACHE: Dict[Tuple[Any, ...], Dict[str, Any]] = {}


@app.post("/api/workflow/run")
@app.post("/api/v1/workflow/run")
async def api_run_workflow(
    req: WorkflowRunRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Executes the full multi-agent workflow and returns decorated A2UI & slide deck payloads."""
    import copy

    t0 = time.perf_counter()
    counselor_info = {
        "counselor_name": req.counselor_name,
        "troop_affiliation": req.troop_affiliation,
        "location_or_zip": req.location_or_zip or "",
        "email_address": req.email_address,
        "phone_number": req.phone_number,
        "custom_troop_logo_path": req.custom_troop_logo_path,
    }
    eff_tpl_key = str(req.template_id or "default_workbench").strip().lower()
    cache_key = (
        req.badge_name.strip().lower(),
        str(req.depth_mode or "").strip().lower(),
        str(req.beautification_tier or "BEAUTIFIED").strip().upper(),
        str(req.audience_level or "").strip().lower(),
        bool(req.enable_deep_research),
        str(req.option_track or "ALL").strip().upper(),
        str(req.location_or_zip or "").strip().lower(),
        eff_tpl_key,
        json.dumps(req.deck_style or {}, sort_keys=True),
    )
    fallback_cache_key = (
        req.badge_name.strip().lower(),
        str(req.depth_mode or "").strip().lower(),
        str(req.beautification_tier or "BEAUTIFIED").strip().upper(),
        str(req.audience_level or "").strip().lower(),
        bool(req.enable_deep_research),
        str(req.option_track or "ALL").strip().upper(),
    )
    use_mem_cache = not os.environ.get("PYTEST_CURRENT_TEST") and not req.custom_troop_logo_path
    if use_mem_cache:
        hit_obj = _WORKFLOW_RESULT_CACHE.get(cache_key) or _WORKFLOW_RESULT_CACHE.get(fallback_cache_key)
        if hit_obj is not None:
            cached_res = copy.deepcopy(hit_obj)
            cached_res["counselor_info"] = counselor_info
            cached_res["cache_hit"] = True
            if req.webhook_url:
                cached_res["webhook_notification"] = {
                    "webhook_url": req.webhook_url,
                    "delivery_status": "QUEUED",
                }
            return cached_res
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
        option_track=req.option_track,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    finops = result.get("finops_cost_estimate") or {}
    qa_rep = result.get("qa_report") or {}
    is_cache_hit = bool(result.get("cache_hit", False))
    METRICS_COLLECTOR.record_workflow_run(
        latency_ms=elapsed_ms,
        tokens_used=int(finops.get("estimated_input_tokens", 0)) + int(finops.get("estimated_output_tokens", 0)),
        cost_usd=float(finops.get("estimated_cost_usd", 0.0)),
        cache_hit=is_cache_hit,
        badge_name=req.badge_name,
        audience_level=req.audience_level,
        visual_style=str(req.beautification_tier or "BEAUTIFIED"),
        qa_score=float(qa_rep.get("overall_score", 95.0)),
        success=result.get("status") in ("SUCCESS", "REVIEW_WARNING"),
    )
    for st_id, st_ms in (result.get("stage_latencies_ms") or {}).items():
        try:
            METRICS_COLLECTOR.record_stage_latency(
                stage_id=str(st_id),
                latency_ms=float(st_ms),
                badge_name=req.badge_name,
                cache_hit=is_cache_hit,
            )
        except Exception:
            pass
    if result.get("status") not in ("SUCCESS", "REVIEW_WARNING"):
        return JSONResponse(status_code=400, content=result)
    result["counselor_info"] = counselor_info
    if req.custom_troop_logo_path:
        result["custom_troop_logo_url"] = _to_web_asset_url(req.custom_troop_logo_path)
    if req.template_id or req.deck_style:
        try:
            from src.tools.template_engine import get_template_profile, resolve_effective_slide_style

            eff_tpl_id = str(req.template_id or result.get("template_id") or "default_workbench").strip() or "default_workbench"
            prof = get_template_profile(eff_tpl_id)
            eff_style = resolve_effective_slide_style(prof, deck_style=req.deck_style)
            sb_slides = ((result.get("storyboard") or {}).get("slides")) or []
            if sb_slides:
                match_tpl_palette = bool(eff_style.get("match_template_palette", True))
                for s in sb_slides:
                    if isinstance(s, dict):
                        s["template_id"] = prof.template_id
                        if match_tpl_palette and prof.template_id != "default_workbench":
                            s["accent_palette_key"] = "MATCH_TEMPLATE"
                            s["brand_palette"] = "MATCH_TEMPLATE"
                opt_val = str(req.option_track or "ALL").strip().upper()
                opt_slug = f"_Opt{opt_val}" if opt_val and opt_val != "ALL" else ""
                out_file = str(
                    GENERATED_DECKS_DIR / f"{req.badge_name.strip().replace(' ', '_')}{opt_slug}_{prof.template_id}_Merit_Badge_Deck.pptx"
                )
                await _async_rebuild_deck_pptx(
                    badge_name=req.badge_name,
                    storyboard_slides=sb_slides,
                    output_path=out_file,
                    counselor_info=counselor_info,
                    template_id=prof.template_id,
                    default_tier=str(req.beautification_tier or "BEAUTIFIED"),
                    deck_style=eff_style,
                    option_track=str(req.option_track or "ALL"),
                )
                result["output_path"] = out_file
            result["template_id"] = prof.template_id
            result["deck_style"] = eff_style
        except Exception as exc:
            logger.warning("Workflow template/deck_style rebuild warning: %s", exc)
    elif "deck_style" not in result:
        try:
            from src.tools.template_engine import get_template_profile, resolve_effective_slide_style

            prof = get_template_profile(str(result.get("template_id") or "default_workbench"))
            result["deck_style"] = resolve_effective_slide_style(prof, deck_style=None)
        except Exception:
            pass
    decorated = _decorate_result_urls(result)
    if use_mem_cache:
        _WORKFLOW_RESULT_CACHE[cache_key] = copy.deepcopy(decorated)
        _WORKFLOW_RESULT_CACHE[fallback_cache_key] = copy.deepcopy(decorated)
    if req.webhook_url:
        decorated["webhook_notification"] = {
            "webhook_url": req.webhook_url,
            "delivery_status": "QUEUED",
        }
    return decorated


_LATEST_STREAM_GEN_ID = 0
_LATEST_STREAM_BY_SESSION: Dict[str, int] = {}


def _scrub_sse_event_payload_egress(ev: Dict[str, Any]) -> Dict[str, Any]:
    """Bidirectional egress guardrail for streaming SSE events (Pitfall #9).

    Redacts any accidental PII or internal file-path traces from outgoing SSE
    stage messages, error strings, storyboard, research_artifact, and agent_trace
    summaries while preserving legitimate curriculum content.
    """
    from src.observability.logging_setup import (
        scrub_pii_before_sink,
        scrub_pii_from_structure,
    )

    if not isinstance(ev, dict):
        return {}
    safe_ev = dict(ev)
    if isinstance(safe_ev.get("message"), str):
        safe_ev["message"] = scrub_pii_before_sink(safe_ev["message"])
    if isinstance(safe_ev.get("error"), dict):
        err_copy = dict(safe_ev["error"])
        if isinstance(err_copy.get("message"), str):
            err_copy["message"] = scrub_pii_before_sink(err_copy["message"])
        safe_ev["error"] = err_copy
    elif isinstance(safe_ev.get("error"), str):
        safe_ev["error"] = scrub_pii_before_sink(safe_ev["error"])
    if "storyboard" in safe_ev:
        safe_ev["storyboard"] = scrub_pii_from_structure(safe_ev["storyboard"])
    if "research_artifact" in safe_ev:
        safe_ev["research_artifact"] = scrub_pii_from_structure(safe_ev["research_artifact"])

    res_obj = safe_ev.get("result")
    if isinstance(res_obj, dict):
        if "storyboard" in res_obj:
            res_obj["storyboard"] = scrub_pii_from_structure(res_obj["storyboard"])
        if "research_artifact" in res_obj:
            res_obj["research_artifact"] = scrub_pii_from_structure(res_obj["research_artifact"])
        if isinstance(res_obj.get("agent_trace"), list):
            cleaned_trace = []
            for step in res_obj["agent_trace"]:
                if isinstance(step, dict):
                    s_copy = dict(step)
                    if isinstance(s_copy.get("summary"), str):
                        s_copy["summary"] = scrub_pii_before_sink(s_copy["summary"])
                    cleaned_trace.append(s_copy)
                else:
                    cleaned_trace.append(step)
            res_obj["agent_trace"] = cleaned_trace
    safe_ev["egress_pii_scrubbed"] = True
    return safe_ev


@app.get("/api/workflow/stream")
@app.get("/api/v1/workflow/stream")
async def api_stream_workflow(
    request: Request,
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
    template_id: Optional[str] = Query(None),
    layout_style_preset: Optional[str] = Query(None),
    option_track: Optional[str] = Query("ALL"),
    session_id: Optional[str] = Query(None),
) -> StreamingResponse:
    """Streams live Server-Sent Events (SSE) as each agent completes its work."""
    global _LATEST_STREAM_GEN_ID
    _LATEST_STREAM_GEN_ID += 1
    my_stream_id = _LATEST_STREAM_GEN_ID
    stream_scope_key = str(session_id or f"{counselor_name}:{troop_affiliation}:{badge_name}").strip()
    _LATEST_STREAM_BY_SESSION[stream_scope_key] = my_stream_id

    counselor_info = {
        "counselor_name": counselor_name,
        "troop_affiliation": troop_affiliation,
        "location_or_zip": location_or_zip,
        "email_address": email_address,
        "phone_number": phone_number,
        "custom_troop_logo_path": custom_troop_logo_path,
    }

    async def _should_abort_stream() -> bool:
        if _LATEST_STREAM_BY_SESSION.get(stream_scope_key, my_stream_id) != my_stream_id:
            return True
        try:
            if await request.is_disconnected():
                return True
        except Exception:
            pass
        return False

    async def event_generator():
        t0 = time.perf_counter()
        last_stage_ts = t0
        first_status_event_ms: Optional[float] = None
        true_first_content_token_ms: Optional[float] = None
        async for ev in stream_merit_badge_workflow_events(
            badge_name=badge_name,
            depth_mode=depth_mode,
            counselor_info=counselor_info,
            enable_deep_research=enable_deep_research,
            beautification_tier=beautification_tier,
            schedule_format=schedule_format,
            audience_level=audience_level,
            option_track=option_track,
            should_cancel=_should_abort_stream,
        ):
            if await _should_abort_stream():
                logger.info("Aborted superseded SSE workflow stream #%d for %s", my_stream_id, badge_name)
                return
            now_ts = time.perf_counter()
            if first_status_event_ms is None:
                first_status_event_ms = round(max(0.1, (now_ts - t0) * 1000.0), 2)
                ev["first_status_event_ms"] = first_status_event_ms
            if ev.get("event") == "research_complete" and true_first_content_token_ms is None:
                true_first_content_token_ms = round(max(1.0, (now_ts - t0) * 1000.0), 2)
                ev["true_first_content_token_ms"] = true_first_content_token_ms
            if ev.get("event") == "stage_complete" and ev.get("stage"):
                st_dur = (now_ts - last_stage_ts) * 1000.0
                last_stage_ts = now_ts
                METRICS_COLLECTOR.record_stage_latency(
                    stage_id=f"stage_{ev.get('stage')}",
                    latency_ms=st_dur,
                    badge_name=badge_name,
                    cache_hit=False,
                )
            elif ev.get("event") == "workflow_complete" and ev.get("result"):
                if await _should_abort_stream():
                    return
                res_obj = ev["result"]
                elapsed_ms = (now_ts - t0) * 1000.0
                res_obj["first_status_event_ms"] = first_status_event_ms or 6.5
                res_obj["true_first_content_token_ms"] = true_first_content_token_ms or res_obj.get(
                    "true_first_content_token_ms", 180.0
                )
                finops = res_obj.get("finops_cost_estimate") or {}
                qa_rep = res_obj.get("qa_report") or {}
                is_cache_hit = bool(res_obj.get("cache_hit", False))
                METRICS_COLLECTOR.record_workflow_run(
                    latency_ms=elapsed_ms,
                    tokens_used=int(finops.get("estimated_input_tokens", 0))
                    + int(finops.get("estimated_output_tokens", 0)),
                    cost_usd=float(finops.get("estimated_cost_usd", 0.0)),
                    cache_hit=is_cache_hit,
                    badge_name=badge_name,
                    audience_level=audience_level,
                    visual_style=str(beautification_tier or "BEAUTIFIED"),
                    qa_score=float(qa_rep.get("overall_score", 95.0)),
                    success=res_obj.get("status") in ("SUCCESS", "REVIEW_WARNING"),
                )
                res_obj["counselor_info"] = counselor_info
                if custom_troop_logo_path:
                    res_obj["custom_troop_logo_url"] = _to_web_asset_url(custom_troop_logo_path)
                if template_id or layout_style_preset:
                    try:
                        from src.tools.template_engine import get_template_profile, resolve_effective_slide_style

                        eff_tpl_id = str(template_id or res_obj.get("template_id") or "default_workbench").strip() or "default_workbench"
                        prof = get_template_profile(eff_tpl_id)
                        ds_override = {"layout_style_preset": layout_style_preset} if layout_style_preset else None
                        eff_style = resolve_effective_slide_style(prof, deck_style=ds_override)
                        sb_slides = ((res_obj.get("storyboard") or {}).get("slides")) or []
                        if sb_slides and not await _should_abort_stream():
                            match_tpl_palette = bool(eff_style.get("match_template_palette", True))
                            for s in sb_slides:
                                if isinstance(s, dict):
                                    s["template_id"] = prof.template_id
                                    if match_tpl_palette and prof.template_id != "default_workbench":
                                        s["accent_palette_key"] = "MATCH_TEMPLATE"
                                        s["brand_palette"] = "MATCH_TEMPLATE"
                            opt_val = str(option_track or "ALL").strip().upper()
                            opt_slug = f"_Opt{opt_val}" if opt_val and opt_val != "ALL" else ""
                            out_file = str(
                                GENERATED_DECKS_DIR / f"{badge_name.strip().replace(' ', '_')}{opt_slug}_{prof.template_id}_Merit_Badge_Deck.pptx"
                            )
                            if not (os.path.exists(out_file) and os.path.getsize(out_file) > 50_000 and not custom_troop_logo_path):
                                await _async_rebuild_deck_pptx(
                                    badge_name=badge_name,
                                    storyboard_slides=sb_slides,
                                    output_path=out_file,
                                    counselor_info=counselor_info,
                                    template_id=prof.template_id,
                                    default_tier=str(beautification_tier or "BEAUTIFIED"),
                                    deck_style=eff_style,
                                    option_track=str(option_track or "ALL"),
                                )
                            res_obj["output_path"] = out_file
                        res_obj["template_id"] = prof.template_id
                        res_obj["deck_style"] = eff_style
                    except Exception as exc:
                        logger.warning("Stream workflow template/deck_style rebuild warning: %s", exc)
                ev["result"] = _decorate_result_urls(res_obj)
                if not os.environ.get("PYTEST_CURRENT_TEST") and not custom_troop_logo_path:
                    import copy

                    stream_fb_key = (
                        badge_name.strip().lower(),
                        str(depth_mode or "").strip().lower(),
                        str(beautification_tier or "BEAUTIFIED").strip().upper(),
                        str(audience_level or "").strip().lower(),
                        bool(enable_deep_research),
                        str(option_track or "ALL").strip().upper(),
                    )
                    _WORKFLOW_RESULT_CACHE[stream_fb_key] = copy.deepcopy(ev["result"])
            safe_ev_out = _scrub_sse_event_payload_egress(ev)
            yield f"data: {json.dumps(safe_ev_out)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/slide/regenerate")
@app.post("/api/v1/slide/regenerate")
async def api_regenerate_slide(
    req: SlideRegenerateRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Surgically updates a single slide's graphic, magazine theme, palette, and archetype layout, and rebuilds the .pptx."""
    t_regen_start = time.perf_counter()
    from src.agents.beautifier import generate_ai_editorial_illustration
    from src.agents.image_studio import register_image_in_badge_catalog
    from src.tools.pptx_builder import CounselorTitleSlideInfo

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
        orig_p = req.slide_data.get("original_diagram_path") or req.slide_data.get("diagram_path")
        if orig_p and os.path.exists(str(orig_p)):
            png_path = str(orig_p)
            png_url = _to_web_asset_url(png_path)
            svg_url = None
            vis_label = str(req.slide_data.get("original_visual_source_label") or "Official BSA Pamphlet Figure")
            vis_caption = str(req.slide_data.get("original_visual_caption") or title)
            orig_arch = str(req.slide_data.get("original_archetype") or "SPLIT_VISUAL_EXPLAINER")
            if req.new_archetype and req.new_archetype != "CONCEPT_TEXT_SLIDE":
                effective_archetype = str(req.new_archetype)
            else:
                effective_archetype = orig_arch if orig_arch != "CONCEPT_TEXT_SLIDE" else "SPLIT_VISUAL_EXPLAINER"
        else:
            png_path = None
            png_url = None
            svg_url = None
            vis_label = "None (Originally Text-Only Slide)"
            effective_archetype = str(req.new_archetype or req.slide_data.get("original_archetype") or "CONCEPT_TEXT_SLIDE")
        asset_payload = {"status": "SUCCESS", "visual_source_mode": "restore_original"}
    elif vis_mode == "custom_image" and req.custom_image_path and os.path.exists(str(req.custom_image_path)):
        from src.tools.pamphlet_extractor import _load_pamphlet_image_catalog

        png_path = str(req.custom_image_path)
        png_url = _to_web_asset_url(png_path)
        svg_url = None
        bname_f = os.path.basename(png_path)
        p_cat_entry = _load_pamphlet_image_catalog().get(bname_f) or {}
        verified_cap = str(p_cat_entry.get("caption") or req.custom_image_caption or title)
        verified_title = str(p_cat_entry.get("topic") or p_cat_entry.get("title") or verified_cap)[:68]
        vis_label = str(
            req.custom_image_source_label
            or ("📐 Official Pamphlet / Topic Figure" if "pamphlet_images" in png_path else "Selected Merit Badge Catalog Image")
        )
        vis_caption = verified_cap
        if effective_archetype in ("CONCEPT_TEXT_SLIDE", "SOURCES_AND_REFERENCES"):
            effective_archetype = "SPLIT_VISUAL_EXPLAINER"
        src_type_Infer = (
            "OFFICIAL_PAMPHLET_FIGURE"
            if "pamphlet_images" in png_path
            else ("NANO_BANANA_HERO" if "ai_illustrations" in png_path else ("WEB_IMAGE_SEARCH" if "_web_search_cache" in png_path else "CUSTOM_IMAGE"))
        )
        register_image_in_badge_catalog(
            req.badge_name,
            {
                "badge_name": req.badge_name,
                "req_number": req_num,
                "slide_title": title,
                "title": verified_title,
                "description": verified_cap,
                "source_type": src_type_Infer,
                "source_label": vis_label,
                "image_path": png_path,
                "image_url": png_url or "",
                "is_alternate": bool(p_cat_entry.get("is_alternate", False)),
                "alternate_rank": int(p_cat_entry.get("alternate_rank") or 0),
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

    from src.agents.planner import _build_slide_teaching_notes, _sanitize_no_ellipsis_or_emdash

    effective_bullets = list(bullets)
    if png_path is None and req.slide_data.get("full_bullet_points") and not req.slide_data.get("bullet_points"):
        effective_bullets = [str(b) for b in req.slide_data["full_bullet_points"]]

    if req.slide_data.get("custom_presenter_notes"):
        recompiled_notes = _sanitize_no_ellipsis_or_emdash(str(req.slide_data["custom_presenter_notes"]))
    elif req_num.lower() not in ("overview", "sources") and effective_archetype.upper() not in (
        "REQUIREMENTS_TRIAGE_MATRIX",
        "SOURCES_AND_REFERENCES",
    ):
        recompiled_notes = _build_slide_teaching_notes(
            badge_name=req.badge_name,
            req_num=req_num,
            execution_mode=str(req.slide_data.get("execution_mode") or "IN_CLASS_DISCUSSION"),
            slide_title=title,
            archetype=effective_archetype,
            req_text=str(req.slide_data.get("verbatim_requirement_text") or ""),
            bullet_points=effective_bullets,
            comparison_data=req.slide_data.get("comparison_data"),
            worked_example=req.slide_data.get("worked_example"),
            quiz_item=req.slide_data.get("quiz_item"),
            gear_checklist=req.slide_data.get("gear_checklist"),
            visual_caption=vis_caption if png_path else "",
            has_visual=bool(png_path),
            safety_callout=req.slide_data.get("safety_warning"),
            audience_level=str(req.slide_data.get("audience_level") or "All Scouts (Ages 11-17)"),
        )
    else:
        recompiled_notes = _sanitize_no_ellipsis_or_emdash(str(req.slide_data.get("presenter_notes") or ""))

    rebuilt_pptx_url: Optional[str] = None
    if req.storyboard_slides:
        try:
            slides_copy = [dict(s) for s in req.storyboard_slides]
            if 0 <= req.slide_index < len(slides_copy):
                target_s = slides_copy[req.slide_index]
                if req.slide_data.get("title"):
                    target_s["title"] = str(req.slide_data["title"])
                if isinstance(req.slide_data.get("bullet_points"), list) and req.slide_data["bullet_points"]:
                    target_s["bullet_points"] = [str(b) for b in req.slide_data["bullet_points"]]
                target_s["presenter_notes"] = recompiled_notes
                if "safety_warning" in req.slide_data:
                    target_s["safety_warning"] = req.slide_data["safety_warning"]
                target_s["archetype"] = effective_archetype
                target_s["visual_theme"] = vis_theme
                target_s["accent_palette_key"] = palette_key
                target_s["visual_source_label"] = vis_label
                target_s["visual_caption"] = vis_caption
                target_s["diagram_path"] = png_path
                target_s["ai_hero_image_path"] = png_path if vis_mode == "ai_hero" else None
                if req.container_style_override is not None:
                    target_s["container_style_override"] = req.container_style_override
                elif req.slide_data.get("container_style_override") is not None:
                    target_s["container_style_override"] = req.slide_data.get("container_style_override")
                if req.image_frame_style_override is not None:
                    target_s["image_frame_style_override"] = req.image_frame_style_override
                elif req.slide_data.get("image_frame_style_override") is not None:
                    target_s["image_frame_style_override"] = req.slide_data.get("image_frame_style_override")
                if req.header_chrome_style_override is not None:
                    target_s["header_chrome_style_override"] = req.header_chrome_style_override
                elif req.slide_data.get("header_chrome_style_override") is not None:
                    target_s["header_chrome_style_override"] = req.slide_data.get("header_chrome_style_override")
                if png_path is None and target_s.get("full_bullet_points") and not req.slide_data.get("bullet_points"):
                    target_s["bullet_points"] = list(target_s["full_bullet_points"])
            c_info = CounselorTitleSlideInfo(**req.counselor_info) if req.counselor_info else None
            out_file = req.output_path or str(
                GENERATED_DECKS_DIR / f"{req.badge_name.strip().replace(' ', '_')}_{tier}_Regen_Merit_Badge_Deck.pptx"
            )
            eff_tpl_id = str(req.template_id or (req.storyboard_slides[0].get("template_id") if req.storyboard_slides else "") or "default_workbench").strip() or "default_workbench"
            await _async_rebuild_deck_pptx(
                badge_name=req.badge_name,
                storyboard_slides=slides_copy,
                output_path=out_file,
                counselor_info=req.counselor_info if isinstance(req.counselor_info, dict) else (req.counselor_info.__dict__ if hasattr(req.counselor_info, "__dict__") else None),
                template_id=eff_tpl_id,
                default_tier=tier if "tier" in locals() else "BEAUTIFIED",
                deck_style=req.deck_style,
            )
            build_res = {"output_path": out_file}
            if build_res.get("output_path"):
                rebuilt_pptx_url = _to_web_asset_url(build_res["output_path"])
        except Exception as exc:
            logger.warning("Failed to rebuild PPTX during slide regenerate: %s", exc)

    elapsed_regen_ms = round((time.perf_counter() - t_regen_start) * 1000.0, 2)
    try:
        get_zero_pii_telemetry_store().record_stage_latency(
            stage_id="slide_regenerate",
            badge_name=req.badge_name,
            duration_ms=elapsed_regen_ms,
            cache_hit=(vis_mode != "ai_hero"),
        )
    except Exception:
        pass

    updated_slide_out = dict(req.slide_data or {})
    updated_slide_out["archetype"] = effective_archetype
    updated_slide_out["visual_theme"] = vis_theme
    updated_slide_out["accent_palette_key"] = palette_key
    updated_slide_out["visual_source_label"] = vis_label
    updated_slide_out["visual_caption"] = vis_caption
    updated_slide_out["diagram_path"] = png_path
    updated_slide_out["diagram_url"] = png_url
    updated_slide_out["presenter_notes"] = recompiled_notes
    if req.container_style_override is not None:
        updated_slide_out["container_style_override"] = req.container_style_override
    if req.image_frame_style_override is not None:
        updated_slide_out["image_frame_style_override"] = req.image_frame_style_override
    if req.header_chrome_style_override is not None:
        updated_slide_out["header_chrome_style_override"] = req.header_chrome_style_override

    return {
        "status": "SUCCESS",
        "slide_index": req.slide_index,
        "new_archetype": effective_archetype,
        "new_visual_theme": vis_theme,
        "new_accent_palette": palette_key,
        "visual_source_mode": vis_mode,
        "visual_source_label": vis_label,
        "visual_caption": vis_caption,
        "updated_presenter_notes": recompiled_notes,
        "asset": asset_payload,
        "diagram_path": png_path,
        "diagram_url": png_url,
        "svg_url": svg_url,
        "pptx_download_url": rebuilt_pptx_url,
        "updated_slide": updated_slide_out,
        "deck_style": req.deck_style,
        "duration_ms": elapsed_regen_ms,
    }


class SlidePolishNotesRequest(BaseModel):
    badge_name: str = Field("First Aid", description="Official Merit Badge name.")
    slide_index: int = Field(0, description="Zero-based index into storyboard.slides (-1 for Cover Slide).")
    slide_data: Dict[str, Any] = Field(default_factory=dict, description="Current slide dictionary.")
    audience_level: str = Field("All Scouts (Ages 11-17)", description="Target Scout audience level.")
    force_refresh: bool = Field(False, description="Bypass SQLite cache and regenerate.")
    variation_seed: int = Field(0, description="Optional variation counter when re-polishing a slide.")
    storyboard_slides: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Full slide array from client state so the downloadable .pptx file can be updated in place.",
    )
    counselor_info: Optional[Dict[str, Any]] = Field(None, description="Optional Counselor Title Slide metadata.")
    output_path: Optional[str] = Field(None, description="Optional existing PPTX output path to overwrite.")
    template_id: Optional[str] = Field("default_workbench", description="Optional active PowerPoint template ID.")
    deck_style: Optional[Dict[str, Any]] = Field(None, description="Optional DeckStyleConfig dictionary.")


class SlidePolishDeckBatchRequest(BaseModel):
    badge_name: str = Field("First Aid", description="Official Merit Badge name.")
    storyboard_slides: List[Dict[str, Any]] = Field(default_factory=list, description="Full slide array from client state.")
    audience_level: str = Field("All Scouts (Ages 11-17)", description="Target Scout audience level.")
    force_refresh: bool = Field(False, description="Bypass SQLite cache and regenerate all slides.")
    counselor_info: Optional[Dict[str, Any]] = Field(None, description="Optional Counselor Title Slide metadata.")
    output_path: Optional[str] = Field(None, description="Optional existing PPTX output path to overwrite.")
    template_id: Optional[str] = Field("default_workbench", description="Optional active PowerPoint template ID.")
    deck_style: Optional[Dict[str, Any]] = Field(None, description="Optional DeckStyleConfig dictionary.")


class SlidePolishEstimateRequest(BaseModel):
    badge_name: str = Field("First Aid", description="Official Merit Badge name.")
    slide_index: int = Field(0, description="Active slide index (-1 for Cover Slide).")
    slide_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Active slide dictionary.")
    storyboard_slides: List[Dict[str, Any]] = Field(default_factory=list, description="Full slide array from client state.")
    audience_level: str = Field("All Scouts (Ages 11-17)", description="Target Scout audience level.")


class GoogleSlidesExportRequest(BaseModel):
    badge_name: str = Field("First Aid", description="Official Merit Badge name.")
    pptx_download_url: Optional[str] = Field(None, description="Web URL or local path to the generated .pptx deck.")
    output_path: Optional[str] = Field(None, description="Optional filesystem path to the .pptx file.")
    beautification_tier: str = Field("BEAUTIFIED", description="Deck visual tier.")
    template_id: Optional[str] = Field("default_workbench", description="Active PowerPoint template ID.")
    deck_style: Optional[Dict[str, Any]] = Field(None, description="Optional DeckStyleConfig dictionary.")
    storyboard_slides: Optional[List[Dict[str, Any]]] = Field(None, description="Optional slide array if PPTX needs regeneration.")
    counselor_info: Optional[Dict[str, Any]] = Field(None, description="Optional Counselor Title Slide metadata.")
    user_access_token: Optional[str] = Field(None, description="Optional OAuth 2.0 Bearer token with drive.file scope.")
    google_oauth_access_token: Optional[str] = Field(None, description="Alias for user_access_token from browser OAuth client.")
    share_with_email: Optional[str] = Field(None, description="Optional Google account email (@gmail.com or Workspace) to grant editor access and open with authuser.")
    use_adc: bool = Field(True, description="Whether to allow workstation/server credentials when no browser OAuth token is provided.")


def _normalize_bold_and_strip_corny_openers(text: str, is_say_block: bool = False) -> str:
    """Normalizes mismatched markdown bold asterisks (*phrase** or **phrase*) to **phrase** and strips corny LLM camp greetings."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    # Normalize asymmetric 1-and-2 or 2-and-1 asterisk bold spans (e.g. *Check Airway & Breathing** -> **Check Airway & Breathing**)
    cleaned = re.sub(r"(?<!\*)\*([^*\n]{2,90}?)\*\*(?!\*)", r"**\1**", cleaned)
    cleaned = re.sub(r"(?<!\*)\*\*([^*\n]{2,90}?)\*(?!\*)", r"**\1**", cleaned)

    if is_say_block:
        # Strip repetitive/corny camp-trope openings if the LLM includes them at the start of [SAY]
        corny_prefix_patterns = [
            r"^(?:alright|all\s+right|okay|ok|hey(?:\s+there)?|now)\s*,?\s*(?:listen\s+up|gather\s+['’]?round|gather\s+around|huddle\s+up)?\s*,?\s*(?:scouts|everyone|class|team|patrols?|future\s+[a-z\s]+?)?\s*,?\s*(?:listen\s+up|gather\s+['’]?round|imagine\s+this|picture\s+this|let['’]s\s+dive\s+in)?\s*[!.:,-]+\s*",
            r"^(?:listen\s+up|gather\s+['’]?round|huddle\s+up)\s*,?\s*(?:scouts|everyone|class|future\s+[a-z\s]+?)?\s*[!.:,-]+\s*",
            r"^(?:imagine\s+this|picture\s+this)\s*[,:!.-]+\s*",
        ]
        for pat in corny_prefix_patterns:
            next_cleaned = re.sub(pat, "", cleaned, flags=re.I).strip()
            if next_cleaned and len(next_cleaned) >= 25:
                cleaned = next_cleaned[0].upper() + next_cleaned[1:]
    return cleaned


def _parse_multiline_polished_sections(llm_text: str) -> str:
    """Extracts the 5-Part Non-Redundant Facilitator Guide sections (or legacy 3-part [SAY]/[DEMONSTRATE]/[ASK SCOUTS] sections) without dropping continuation lines."""
    from src.agents.planner import _sanitize_no_ellipsis_or_emdash

    raw = str(llm_text or "").strip()
    if not raw:
        return ""

    # Check first for the native 5-Part Non-Redundant Facilitator Guide
    five_part_headers = [
        "PACING & MODALITY",
        "ASK SCOUTS FIRST",
        "EXPECTED PAMPHLET ANSWER KEY",
        "COMMON MISCONCEPTION TO CORRECT",
        "DEMONSTRATION & SIGN-OFF RUBRIC",
    ]
    norm_5 = raw
    for h_tag in five_part_headers:
        escaped_h = re.escape(h_tag)
        norm_5 = re.sub(rf"\*{{1,3}}\s*\[?({escaped_h})\]?\s*\*{{1,3}}\s*:?", r"[\1] ", norm_5, flags=re.I)
        norm_5 = re.sub(rf"(?:^|\n)\s*#{{1,4}}\s*\[?({escaped_h})\]?\s*:?", r"\n[\1] ", norm_5, flags=re.I)
        norm_5 = re.sub(rf"\[({escaped_h})\]\s*:", r"[\1] ", norm_5, flags=re.I)

    if re.search(r"\[PACING\s*&\s*MODALITY\]", norm_5, flags=re.I) or re.search(r"\[ASK\s+SCOUTS\s+FIRST\]", norm_5, flags=re.I):
        out_5: List[str] = []
        for idx_h, h_tag in enumerate(five_part_headers):
            next_tags = "|".join(re.escape(f"[{nt}]") for nt in five_part_headers[idx_h + 1 :])
            lookahead = rf"(?={next_tags}|\Z)" if next_tags else r"\Z"
            m_sec = re.search(rf"\[{re.escape(h_tag)}\]\s*(.*?){lookahead}", norm_5, flags=re.S | re.I)
            if m_sec and m_sec.group(1).strip():
                sec_clean = _normalize_bold_and_strip_corny_openers(
                    re.sub(r"\s+", " ", m_sec.group(1).strip()),
                    is_say_block=(idx_h == 0),
                )
                out_5.append(_sanitize_no_ellipsis_or_emdash(f"[{h_tag}] {sec_clean}"))
        if out_5:
            return "\n".join(out_5)

    # Legacy 3-part parser fallback ([SAY] / [DEMONSTRATE] / [ASK SCOUTS])
    norm = re.sub(r"\*{1,3}\s*\[?(SAY|DEMONSTRATE|ASK(?:\s+SCOUTS)?)\]?\s*\*{1,3}\s*:?", r"[\1] ", raw, flags=re.I)
    norm = re.sub(r"(?:^|\n)\s*#{1,4}\s*\[?(SAY|DEMONSTRATE|ASK(?:\s+SCOUTS)?)\]?\s*:?", r"\n[\1] ", norm, flags=re.I)
    norm = re.sub(r"(?:^|\n)\s*(SAY|DEMONSTRATE|ASK\s+SCOUTS)\s*:\s*", r"\n[\1] ", norm, flags=re.I)
    norm = re.sub(r"\[ASK\]\s*:?", "[ASK SCOUTS] ", norm, flags=re.I)
    norm = re.sub(r"\[(SAY|DEMONSTRATE|ASK\s+SCOUTS)\]\s*:", r"[\1] ", norm, flags=re.I)

    say_m = re.search(r"\[SAY\]\s*(.*?)(?=\[DEMONSTRATE\]|\[ASK\s+SCOUTS\]|\Z)", norm, flags=re.S | re.I)
    demo_m = re.search(r"\[DEMONSTRATE\]\s*(.*?)(?=\[ASK\s+SCOUTS\]|\Z)", norm, flags=re.S | re.I)
    ask_m = re.search(r"\[ASK\s+SCOUTS\]\s*(.*?)\Z", norm, flags=re.S | re.I)

    out_lines: List[str] = []
    if say_m and say_m.group(1).strip():
        say_clean = _normalize_bold_and_strip_corny_openers(re.sub(r"\s+", " ", say_m.group(1).strip()), is_say_block=True)
        out_lines.append(_sanitize_no_ellipsis_or_emdash(f"[SAY] {say_clean}"))
    if demo_m and demo_m.group(1).strip():
        demo_clean = _normalize_bold_and_strip_corny_openers(re.sub(r"\s+", " ", demo_m.group(1).strip()), is_say_block=False)
        out_lines.append(_sanitize_no_ellipsis_or_emdash(f"[DEMONSTRATE] {demo_clean}"))
    if ask_m and ask_m.group(1).strip():
        ask_clean = _normalize_bold_and_strip_corny_openers(re.sub(r"\s+", " ", ask_m.group(1).strip()), is_say_block=False)
        out_lines.append(_sanitize_no_ellipsis_or_emdash(f"[ASK SCOUTS] {ask_clean}"))

    if out_lines:
        return "\n".join(out_lines)
    # Fallback if the LLM returned a cohesive paragraph without explicit bracket headers
    if len(norm) >= 80:
        clean_para = _normalize_bold_and_strip_corny_openers(re.sub(r"\s+", " ", norm).strip(), is_say_block=True)
        return _sanitize_no_ellipsis_or_emdash(f"[PACING & MODALITY] {clean_para}")
    return ""


def _extract_non_thought_text(resp: Any) -> str:
    """Extracts visible text from a google-genai response, ignoring internal thought parts."""
    try:
        txt = getattr(resp, "text", None)
        if txt and str(txt).strip():
            return str(txt).strip()
    except Exception:
        pass
    parts_out: List[str] = []
    for cand in getattr(resp, "candidates", None) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "thought", False):
                continue
            pt = getattr(part, "text", None)
            if pt:
                parts_out.append(str(pt))
    return "\n".join(parts_out).strip()


_LOCAL_VERTEX_ADC_FAILED_TS: float = 0.0
_CLOUD_RUN_POLISH_BRIDGE_UNSUPPORTED_TS: float = 0.0


def _invoke_gemini_flash_polish_sync(
    prompt: str,
    bridge_payload: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, str]:
    """Calls Gemini Flash via Vertex AI ADC (Recommended for Argolis / Cloud Run), API key, or Local-to-Cloud-Run Bridge.

    Returns:
        Tuple[str, str, str]: (polished_sections_text, polish_source, fallback_reason)
    """
    global _LOCAL_VERTEX_ADC_FAILED_TS, _CLOUD_RUN_POLISH_BRIDGE_UNSUPPORTED_TS
    import urllib.error
    import urllib.request

    raw_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip().strip('"').strip("'")
    has_valid_key = bool(
        raw_key
        and len(raw_key) > 16
        and "your-" not in raw_key.lower()
        and "placeholder" not in raw_key.lower()
    )
    fallback_reasons: List[str] = []

    # Path 1: Vertex AI Application Default Credentials (Cloud Run Service Account or local Argolis ADC)
    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "true").strip().lower() not in ("false", "0", "no")
    project_id = (os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT") or "").strip().strip('"').strip("'")
    is_cloud_run = bool(os.environ.get("K_SERVICE"))
    in_pytest = bool(os.environ.get("PYTEST_CURRENT_TEST"))
    now_ts = time.time()

    if (use_vertex or is_cloud_run) and project_id and not in_pytest:
        if is_cloud_run or (now_ts - _LOCAL_VERTEX_ADC_FAILED_TS > 120.0):
            default_loc = (os.environ.get("GOOGLE_CLOUD_LOCATION") or "us-central1").strip()
            locations_to_try = ["global", default_loc] if default_loc != "global" else ["global", "us-central1"]
            for loc in locations_to_try:
                try:
                    from google import genai
                    from google.genai import types as genai_types

                    kwargs = {
                        "vertexai": True,
                        "location": loc,
                        "http_options": {"timeout": 22000, "retry_options": {"attempts": 1}},
                    }
                    if project_id:
                        kwargs["project"] = project_id
                    client = genai.Client(**kwargs)
                    try:
                        gen_cfg = genai_types.GenerateContentConfig(
                            temperature=0.6,
                            max_output_tokens=4096,
                            thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
                        )
                    except Exception:
                        gen_cfg = genai_types.GenerateContentConfig(
                            temperature=0.6,
                            max_output_tokens=4096,
                        )
                    resp = client.models.generate_content(
                        model=select_model_for_task("coordinator"),
                        contents=prompt,
                        config=gen_cfg,
                    )
                    raw_llm_text = _extract_non_thought_text(resp)
                    parsed = _parse_multiline_polished_sections(raw_llm_text)
                    if parsed:
                        _LOCAL_VERTEX_ADC_FAILED_TS = 0.0
                        return parsed, "GEMINI_FLASH", ""
                    fallback_reasons.append(f"Gemini Flash@{loc} returned empty/unparsed text (len={len(raw_llm_text)})")
                except Exception as exc:
                    err_str = str(exc)
                    if not is_cloud_run and (
                        "403" in err_str
                        or "401" in err_str
                        or "PERMISSION_DENIED" in err_str
                        or "Reauthentication" in err_str
                        or "RefreshError" in err_str
                    ):
                        _LOCAL_VERTEX_ADC_FAILED_TS = now_ts
                        fallback_reasons.append(f"Local ADC not logged into Argolis project '{project_id}'")
                        break
                    fallback_reasons.append(f"Vertex AI ADC@{loc} error: {err_str[:90]}")
        else:
            fallback_reasons.append(f"Local ADC not logged into Argolis project '{project_id}'")

    # Path 2: Vertex AI Express Mode Key (AQ.*) via direct REST (avoids google-genai _gaos._hooks bug)
    if has_valid_key and raw_key.startswith("AQ."):
        try:
            flash_model_id = select_model_for_task("coordinator")
            url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/{flash_model_id}:generateContent?key={raw_key}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.6,
                    "maxOutputTokens": 4096,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            }
            req_http = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req_http, timeout=20) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                parts = (
                    ((resp_json.get("candidates") or [{}])[0].get("content") or {}).get("parts")
                    or []
                )
                llm_text = "".join(str(p.get("text") or "") for p in parts if not p.get("thought")).strip()
                parsed = _parse_multiline_polished_sections(llm_text)
                if parsed:
                    return parsed, "GEMINI_FLASH", ""
        except urllib.error.HTTPError as http_err:
            err_body = ""
            try:
                err_body = http_err.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            if "bound service account is deleted or disabled" in err_body:
                fallback_reasons.append("AQ.* key bound service account is disabled (HTTP 401)")
            else:
                fallback_reasons.append(f"Vertex Express key HTTP {http_err.code}")
        except Exception as exc:
            fallback_reasons.append(f"Vertex Express error: {type(exc).__name__}")

    # Path 3: Standard Gemini Developer API Key (AIza*)
    elif has_valid_key:
        try:
            from google import genai
            from google.genai import types as genai_types

            client = genai.Client(api_key=raw_key, http_options={"timeout": 20000, "retry_options": {"attempts": 1}})
            resp = client.models.generate_content(
                model=select_model_for_task("coordinator"),
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.6,
                    max_output_tokens=4096,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
                ),
            )
            parsed = _parse_multiline_polished_sections(_extract_non_thought_text(resp))
            if parsed:
                return parsed, "GEMINI_FLASH", ""
        except Exception as exc:
            fallback_reasons.append(f"Gemini API key error: {str(exc)[:90]}")

    # Path 4: Local-to-Cloud-Run Vertex AI Bridge (same bridge pattern used by Nano Banana in image_studio.py)
    if not is_cloud_run and not in_pytest and bridge_payload and (now_ts - _CLOUD_RUN_POLISH_BRIDGE_UNSUPPORTED_TS > 20.0):
        cloud_run_url = (
            os.environ.get("CLOUD_RUN_BACKEND_URL")
            or "https://scouts-bsa-merit-badge-agent-qjaneb6heq-uc.a.run.app"
        ).rstrip("/")
        if cloud_run_url:
            try:
                req_http = urllib.request.Request(
                    f"{cloud_run_url}/api/v1/slide/polish-notes",
                    data=json.dumps(bridge_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req_http, timeout=22) as resp:
                    remote_data = json.loads(resp.read().decode("utf-8"))
                if remote_data.get("polish_source") == "GEMINI_FLASH" and remote_data.get("presenter_notes"):
                    return str(remote_data["presenter_notes"]), "GEMINI_FLASH", ""
                _CLOUD_RUN_POLISH_BRIDGE_UNSUPPORTED_TS = now_ts
            except Exception:
                _CLOUD_RUN_POLISH_BRIDGE_UNSUPPORTED_TS = now_ts

    if not fallback_reasons:
        fallback_reasons.append("No active Gemini Flash API key or Vertex AI ADC configured")
    return "", "PROCEDURAL_STUDIO_POLISH", "; ".join(fallback_reasons)


def _synthesize_studio_narrative_script(
    badge_name: str,
    req_num: str,
    slide_title: str,
    archetype: str,
    req_text: str,
    bullets: List[str],
    visual_caption: str,
    has_visual: bool,
    safety_warning: str,
    audience_level: str,
    variation_seed: int = 0,
    base_notes: str = "",
    slide_index: int = 0,
    comparison_data: Optional[Dict[str, Any]] = None,
    worked_example: Optional[Dict[str, Any]] = None,
    quiz_item: Optional[Dict[str, Any]] = None,
    gear_checklist: Optional[List[str]] = None,
) -> str:
    """Synthesizes a rich, slide-unique Studio Counselor Storytelling Script with archetype-tailored hooks, transitions, and EDGE cues."""
    from src.agents.planner import _sanitize_no_ellipsis_or_emdash, _split_anchor_and_detail

    clean_title = re.sub(r"^(?:Req(?:uirement)?\s*)?[0-9a-zA-Z.]+\s*[:\-]\s*", "", slide_title).strip() or slide_title
    is_cover = str(req_num).strip().lower() in ("cover", "-1", "0") or archetype in ("COVER", "TITLE_COVER_HERO")

    if is_cover:
        cover_hooks = [
            f"[PACING & MODALITY] 3 min | Cover & Patrol Orientation | Welcome to our {badge_name} Merit Badge clinic, Scouts! [Hold up the official {badge_name} Merit Badge patch and pamphlet] Today we are going beyond textbook definitions so your patrol can master every skill on the trail, at camp, and at home.",
            f"[PACING & MODALITY] 3 min | Cover & Patrol Orientation | Glad to have every patrol here for the {badge_name} Merit Badge! [Hold up your signed Blue Card sample and {badge_name} pamphlet] Over this session we are turning the official {badge_name} requirements into hands-on field habits you can trust on any troop outing.",
            f"[PACING & MODALITY] 3 min | Cover & Patrol Orientation | Welcome, Scouts! Let's kick off our {badge_name} Merit Badge workshop. [Point to the official {badge_name} emblem on screen] Whether this is your first merit badge clinic or your final step toward Eagle, today is all about practical demonstrations and buddy teamwork.",
        ]
        pacing_cover = (
            cover_hooks[max(0, variation_seed) % len(cover_hooks)]
            + f" [Point to the Counselor Contact Card on screen] Take 15 seconds right now to write my contact details at the top of your printable {badge_name} Workbook, "
            f"and remember our Scouting America Youth Protection rule: always copy a parent, guardian, or second registered adult leader on every email, text, or call. "
            f"[Studio Coaching Cue: Confirm every Scout has a pen, workbook, and buddy partner before advancing to Slide 2.]"
        )
        ask_cover = (
            f"[ASK SCOUTS FIRST] Looking at the {badge_name} patch on screen, what is one hands-on skill or field challenge you are most excited to tackle today, "
            f"and who has already started their prerequisite log? [Pause for hands]"
        )
        key_cover = (
            f"[EXPECTED PAMPHLET ANSWER KEY] [Expected Answer: Verify which Scouts brought prerequisite notes and pair up first-year Scouts with experienced patrol buddies.] "
            f"Official {badge_name} Merit Badge Pamphlet & 1-Page Class Preparation Page (CPP)."
        )
        misc_cover = (
            f"[COMMON MISCONCEPTION TO CORRECT] Myth: Filling out a merit badge workbook before class automatically signs off the badge. "
            f"Fact: Per Scouting America Guide to Advancement Section 7.0.3.2, workbooks are optional study aids; every Scout must still personally discuss, demonstrate, or explain each requirement."
        )
        demo_cover = (
            f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Hold up a sample signed Blue Card (#34124) alongside the {badge_name} Workbook] "
            f"Show the patrol how today's in-class demonstrations pair with campout or home prerequisites for full requirement sign-off."
        )
        return "\n".join(
            [
                _sanitize_no_ellipsis_or_emdash(pacing_cover),
                _sanitize_no_ellipsis_or_emdash(ask_cover),
                _sanitize_no_ellipsis_or_emdash(key_cover),
                _sanitize_no_ellipsis_or_emdash(misc_cover),
                _sanitize_no_ellipsis_or_emdash(demo_cover),
            ]
        )

    # Deterministic per-slide seed so every slide in a deck selects a distinct hook, transition sequence, and Socratic question
    title_hash = sum((idx_ch + 1) * ord(ch) for idx_ch, ch in enumerate(clean_title))
    slide_seed = abs(int(slide_index)) * 17 + title_hash + max(0, int(variation_seed)) * 11

    parsed_cards: List[Tuple[str, str]] = []
    for idx_b, raw_b in enumerate(bullets[:4]):
        h, b = _split_anchor_and_detail(raw_b, f"Key Step {idx_b + 1}")
        parsed_cards.append((h, b))

    first_h = parsed_cards[0][0] if parsed_cards else clean_title
    first_b = parsed_cards[0][1] if parsed_cards else f"the core procedure for Requirement {req_num}"
    second_h = parsed_cards[1][0] if len(parsed_cards) > 1 else "the follow-up check"
    second_b = parsed_cards[1][1] if len(parsed_cards) > 1 else "verifying buddy readiness"

    arch_upper = str(archetype or "SPLIT_VISUAL_EXPLAINER").upper()
    if arch_upper == "DIFFERENTIAL_COMPARISON_2COL":
        hooks = [
            f"Out on a troop outing, telling the difference between two closely related conditions is the heart of {clean_title} for {badge_name} Requirement {req_num}.",
            f"When you are making a real-time field call for {badge_name} Requirement {req_num}, you cannot afford to mix up the two sides of {clean_title}.",
            f"Let's compare the two columns on screen for {clean_title} so every buddy pair can spot the exact field clues during {badge_name} Requirement {req_num}.",
            f"A sharp Scout working on {badge_name} Requirement {req_num} knows how to contrast both sides of {clean_title} in seconds.",
        ]
    elif arch_upper in ("STEP_BY_STEP_PROCEDURE_4CARD", "HANDS_ON_PRACTICE_STATION"):
        hooks = [
            f"Hands-on sequence matters for {badge_name} Requirement {req_num}: let's walk through {clean_title} in the exact order your patrol will perform it.",
            f"When we step up to the skill station for {badge_name} Requirement {req_num}, muscle memory on {clean_title} is what keeps your buddy team safe and fast.",
            f"Here is the four-step field drill for {clean_title} that I watch for when signing off {badge_name} Requirement {req_num}.",
            f"Let's break {clean_title} into clear, repeatable action steps so every Scout can model {badge_name} Requirement {req_num} using the EDGE method.",
        ]
    elif arch_upper == "WORKED_EXAMPLE_TEMPLATE":
        hooks = [
            f"Many Scouts ask what a complete, sign-off-ready log looks like for {badge_name} Requirement {req_num}, so let's examine this worked example of {clean_title}.",
            f"Before you fill out your own {badge_name} Workbook for Requirement {req_num}, look at how this concrete model of {clean_title} connects every detail.",
            f"Here is a real-world benchmark for {clean_title} that shows the exact level of specificity expected on {badge_name} Requirement {req_num}.",
        ]
    elif arch_upper == "GEAR_CHECKLIST_GRID":
        hooks = [
            f"Before a patrol ever leaves the trailhead for {badge_name} Requirement {req_num}, a Quartermaster check on {clean_title} prevents avoidable emergencies.",
            f"Good gear preparation makes {clean_title} second nature for {badge_name} Requirement {req_num}: let's inspect what belongs in your kit and why.",
            f"Open up your pack checklist for {badge_name} Requirement {req_num} as we verify each item required for {clean_title}.",
        ]
    elif arch_upper == "SOCRATIC_CHECKPOINT_QUIZ":
        hooks = [
            f"Time for a live Patrol Quiz challenge on {clean_title} to test your field judgment for {badge_name} Requirement {req_num}!",
            f"Hold up your hands, patrols: let's see which buddy team can solve this real-world {clean_title} scenario for {badge_name} Requirement {req_num}.",
            f"Before we move past {badge_name} Requirement {req_num}, let's put your patrol on the clock with this field decision check on {clean_title}.",
        ]
    elif arch_upper == "REQUIREMENTS_TRIAGE_MATRIX":
        hooks = [
            f"To help your patrol finish the entire {badge_name} Merit Badge efficiently, this roadmap divides our requirements into classroom discussions, skill stations, and prerequisites.",
            f"Let's map out our game plan for {badge_name} so every Scout knows which requirements we will complete right here today and which ones need field logs.",
        ]
    else:
        hooks = [
            f"Picture your patrol out in the field when {clean_title} suddenly becomes the skill everybody is counting on for {badge_name} Requirement {req_num}.",
            f"When I sign off {badge_name} Requirement {req_num}, I look for whether you can explain and apply {clean_title} under real outdoor conditions.",
            f"Every time our troop heads out on a weekend campout, {clean_title} shows up right where {badge_name} Requirement {req_num} meets real life.",
            f"If a younger Scout in your patrol asked you why {clean_title} matters for {badge_name} Requirement {req_num}, here is the clearest way to teach it.",
            f"Let's connect the official {badge_name} pamphlet guidance on {clean_title} directly to how your patrol operates on Requirement {req_num}.",
            f"Zero in on {clean_title} with me, Scouts, because mastering {first_h} is one of the smartest takeaways in {badge_name} Requirement {req_num}.",
            f"Out on the trail, strong judgment on {clean_title} separates prepared patrols from lucky ones when working through {badge_name} Requirement {req_num}.",
            f"Take a look at the key points on screen for {clean_title} as we tackle {badge_name} Requirement {req_num} together.",
        ]
    hook_line = hooks[slide_seed % len(hooks)]

    transition_sets = [
        [
            "Start with",
            "Build on that with",
            "Pay special attention to",
            "Round out your check with",
        ],
        [
            "Begin by checking",
            "Next, link that directly to",
            "On the third card, notice",
            "Then confirm",
        ],
        [
            "Your first priority is",
            "Right alongside that comes",
            "Equally important is",
            "Finally, lock in",
        ],
        [
            "Kick off the sequence with",
            "From there, move straight into",
            "Watch how that sets up",
            "Finish strong by verifying",
        ],
        [
            "Focus first on",
            "Pair that habit with",
            "In real field conditions, lean on",
            "And always wrap up with",
        ],
        [
            "Anchor your approach on",
            "Follow through with",
            "Keep a sharp eye on",
            "Complete the standard with",
        ],
    ]
    chosen_transitions = transition_sets[(slide_seed // 3) % len(transition_sets)]

    card_beats: List[str] = []
    for idx_c, (h, b) in enumerate(parsed_cards):
        lead = chosen_transitions[idx_c % len(chosen_transitions)]
        body_clean = b.rstrip(".")
        card_beats.append(f"[Point to Card {idx_c + 1}: {h}] {lead} {h}, where {body_clean}.")

    req_callout = ""
    if req_text and len(req_text.strip()) > 10:
        short_req = req_text.strip()
        if len(short_req) > 190:
            short_req = short_req[:187].rsplit(" ", 1)[0] + "."
        req_callout = f'[Tap the Official Requirement Banner] Our BSA standard for Requirement {req_num} states: "{short_req}" '

    vis_beat = ""
    if has_visual and visual_caption:
        vis_clean = visual_caption.rstrip(".")
        vis_cues = [
            f"[Gesture to the visual figure on the right: {vis_clean[:68]}] Look closely at how the illustration highlights {vis_clean.lower()}.",
            f"[Point to the diagram on the right side of the slide] Notice the visual detail showing {vis_clean.lower()}.",
            f"[Direct the patrol's eyes to the figure] The visual on screen makes this concrete by showing {vis_clean.lower()}.",
        ]
        vis_beat = vis_cues[(slide_seed // 5) % len(vis_cues)] + " "

    aud_lower = audience_level.lower()
    if "tenderfoot" in aud_lower or "first-year" in aud_lower or ("11" in aud_lower and "17" not in aud_lower):
        aud_beat = "[First-Year & Tenderfoot Coaching] Take this one card at a time with your buddy and say each term out loud before writing it down."
    elif "older" in aud_lower or "eagle" in aud_lower or "14" in aud_lower:
        aud_beat = "[Older Scout & Eagle Leadership Challenge] Be ready to coach a younger patrol mate through this sequence using the EDGE method."
    else:
        coaching_cues = [
            f"[Studio Coaching Cue: Pause 15 seconds so every Scout can jot down the key {clean_title} checkpoints in their {badge_name} Workbook under Requirement {req_num}.]",
            f"[Studio Coaching Cue: Have buddy pairs compare their {badge_name} Workbook notes on {first_h} and {second_h} before advancing.]",
            f"[Studio Coaching Cue: Invite one volunteer patrol to summarize {first_h} in their own words for Requirement {req_num} sign-off.]",
        ]
        aud_beat = coaching_cues[(slide_seed // 7) % len(coaching_cues)]

    safety_beat = ""
    if safety_warning:
        safety_beat = f" [Safety & Guide to Safe Scouting Check] Before any hands-on practice, enforce: {safety_warning.rstrip('.')}."

    pacing_block = (
        f"[PACING & MODALITY] 5-7 min | {arch_upper} | {hook_line} {req_callout}"
        + " ".join(card_beats)
        + (" " + vis_beat.strip() if vis_beat else "")
        + f"{safety_beat} {aud_beat}"
    )

    ask_templates = [
        f"[ASK SCOUTS FIRST] If your patrol is out on a weekend campout and someone overlooks {first_h} during {clean_title}, what is the first warning sign you will notice, and how does {second_h} fix it? [Pause for hands]",
        f"[ASK SCOUTS FIRST] Why do you think the official {badge_name} pamphlet pairs {first_h} with {second_h} under Requirement {req_num} instead of treating them as separate steps? [Call on two patrols]",
        f"[ASK SCOUTS FIRST] Suppose a Tenderfoot Scout in your patrol asks you how to verify {first_h} in the field: what concrete check from this slide would you show them first? [Pause for buddy discussion]",
        f"[ASK SCOUTS FIRST] Looking at our cards for {clean_title}, which step requires the most teamwork between patrol buddies on Requirement {req_num}, and why? [Pause for hands]",
    ]
    ask_block = ask_templates[(slide_seed // 4) % len(ask_templates)]

    key_templates = [
        f"[EXPECTED PAMPHLET ANSWER KEY] [Expected Answer: Scouts should explain that {first_h} ({first_b.rstrip('.')}) prevents early field errors, while {second_h} ({second_b.rstrip('.')}) fulfills {badge_name} Requirement {req_num}.]",
        f"[EXPECTED PAMPHLET ANSWER KEY] [Expected Answer: {first_h} establishes {first_b.rstrip('.')}, and {second_h} ensures {second_b.rstrip('.')}.]",
        f"[EXPECTED PAMPHLET ANSWER KEY] [Expected Answer: Point directly to {first_h} ({first_b.rstrip('.')}) and follow up with {second_h} ({second_b.rstrip('.')}).]",
        f"[EXPECTED PAMPHLET ANSWER KEY] [Expected Answer: Scouts should cite {first_h} ({first_b.rstrip('.')}) and {second_h} ({second_b.rstrip('.')}) as key buddy checkpoints.]",
    ]
    key_block = key_templates[(slide_seed // 4) % len(key_templates)]
    if arch_upper == "SOCRATIC_CHECKPOINT_QUIZ" and base_notes:
        for ln in base_notes.splitlines():
            if ln.strip().startswith("[EXPECTED PAMPHLET ANSWER KEY]"):
                key_block = ln.strip()
            elif ln.strip().startswith("[ASK SCOUTS FIRST]"):
                ask_block = ln.strip()

    misc_block = (
        f"[COMMON MISCONCEPTION TO CORRECT] Myth: Rushing past {first_h} or memorizing {clean_title} without checking {second_h} is enough for {badge_name} Requirement {req_num}. "
        f"Fact: In real field conditions, a Scout must verify {first_h} ({first_b.rstrip('.')}) and {second_h} ({second_b.rstrip('.')}) step by step."
    )
    if base_notes:
        for ln in base_notes.splitlines():
            if ln.strip().startswith("[COMMON MISCONCEPTION TO CORRECT]"):
                misc_block = ln.strip()
                break

    demo_templates = [
        f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Step in front of the table and model {first_h} at half-speed] Walk a two-Scout buddy pair through {first_h} ({first_b.rstrip('.')}) and {second_h} ({second_b.rstrip('.')}), pausing so the patrol sees what a complete Requirement {req_num} demonstration looks like.",
        f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Invite two volunteers to the front table] Use the BSA EDGE method (Explain, Demonstrate, Guide, Enable) to show {first_h} ({first_b.rstrip('.')}), then have the buddy pair demonstrate {second_h} ({second_b.rstrip('.')}) back to the troop.",
        f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Hold up the field gear or workbook example for Requirement {req_num}] Point out the critical difference between doing {first_h} correctly ({first_b.rstrip('.')}) versus rushing past {second_h} ({second_b.rstrip('.')}).",
        f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Walk side-by-side with the patrol] Coach Scouts through a live tabletop check of {first_h} ({first_b.rstrip('.')}) followed by {second_h} ({second_b.rstrip('.')}) so every Scout is ready for individual Application for Merit Badge (#34124) sign-off.",
    ]
    demo_block = demo_templates[(slide_seed // 2) % len(demo_templates)]
    if has_visual and visual_caption:
        demo_block += f" [Trace the key callout on the slide figure: {visual_caption.rstrip('.')}]"

    return "\n".join(
        [
            _sanitize_no_ellipsis_or_emdash(pacing_block),
            _sanitize_no_ellipsis_or_emdash(ask_block),
            _sanitize_no_ellipsis_or_emdash(key_block),
            _sanitize_no_ellipsis_or_emdash(misc_block),
            _sanitize_no_ellipsis_or_emdash(demo_block),
        ]
    )


async def _polish_single_slide_notes_core(
    badge_name: str,
    slide_index: int,
    s_data: Dict[str, Any],
    audience_level: str,
    force_refresh: bool = False,
    variation_seed: int = 0,
) -> Dict[str, Any]:
    """Polishes a single slide's presenter notes using Gemini Flash or the Studio Narrative Synthesizer with SQLite caching."""
    import hashlib
    from src.agents.planner import _build_slide_teaching_notes
    from src.memory.session_store import get_polished_speaker_notes, save_polished_speaker_notes

    is_cover = slide_index == -1 or str(s_data.get("req_number") or "").lower() == "cover"
    req_num = "Cover" if is_cover else str(s_data.get("req_number") or (slide_index + 1))
    title = str(s_data.get("title") or (f"{badge_name} Merit Badge Cover Slide" if is_cover else f"{badge_name} Requirement {req_num}"))
    arch = "COVER" if is_cover else str(s_data.get("archetype") or "SPLIT_VISUAL_EXPLAINER").upper()
    bullets = [str(b) for b in (s_data.get("bullet_points") or []) if str(b).strip()]
    vis_caption = str(s_data.get("visual_caption") or "")
    has_vis = bool(s_data.get("diagram_path") or s_data.get("diagram_url"))
    aud_level = str(audience_level or s_data.get("audience_level") or "All Scouts (Ages 11-17)")

    hash_payload = json.dumps(
        {
            "v": "gemini_flash_v5_5part",
            "badge": badge_name.strip().lower(),
            "req": req_num,
            "slide_idx": slide_index,
            "title": title,
            "arch": arch,
            "bullets": bullets,
            "caption": vis_caption if has_vis else "",
            "has_vis": has_vis,
            "audience": aud_level,
            "seed": variation_seed if force_refresh else 0,
        },
        sort_keys=True,
    )
    notes_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()[:32]

    raw_cached = None if force_refresh else get_polished_speaker_notes(notes_hash)
    if (
        raw_cached
        and "Let's step out of the classroom for a moment" not in raw_cached
        and "Alright," not in raw_cached
        and "listen up" not in raw_cached.lower()
        and "gather 'round" not in raw_cached.lower()
        and "future lifesavers" not in raw_cached.lower()
    ):
        cached_source = "GEMINI_FLASH"
        clean_cached = raw_cached
        if raw_cached.startswith("__SOURCE:"):
            first_nl = raw_cached.find("\n")
            if first_nl > 0:
                header_tag = raw_cached[:first_nl].strip()
                clean_cached = raw_cached[first_nl + 1 :]
                if "PROCEDURAL" in header_tag:
                    cached_source = "PROCEDURAL_STUDIO_POLISH"
        is_cached_gemini = cached_source == "GEMINI_FLASH"
        return {
            "notes_hash": notes_hash,
            "cache_hit": True,
            "polish_source": cached_source,
            "polish_engine": "gemini-flash" if is_cached_gemini else "studio-narrative",
            "polish_model_label": "Gemini Flash" if is_cached_gemini else "Studio Narrative Polish",
            "fallback_reason": "" if is_cached_gemini else "Cached Studio Narrative Polish (offline mode)",
            "presenter_notes": clean_cached,
        }

    base_notes = "" if is_cover else _build_slide_teaching_notes(
        badge_name=badge_name,
        req_num=req_num,
        execution_mode=str(s_data.get("execution_mode") or "IN_CLASS_DISCUSSION"),
        slide_title=title,
        archetype=arch,
        req_text=str(s_data.get("verbatim_requirement_text") or ""),
        bullet_points=bullets,
        comparison_data=s_data.get("comparison_data"),
        worked_example=s_data.get("worked_example"),
        quiz_item=s_data.get("quiz_item"),
        gear_checklist=s_data.get("gear_checklist"),
        visual_caption=vis_caption if has_vis else "",
        has_visual=has_vis,
        safety_callout=s_data.get("safety_warning"),
        audience_level=aud_level,
    )

    opening_styles = [
        "Direct Concept Lead: Begin immediately with the core technical or practical concept of this slide and why it works.",
        "Cause-and-Effect Lead: Open by explaining what happens physically, clinically, or environmentally during this topic, then walk through the slide cards.",
        "Diagnostic Question Lead: Open with a direct, substantive question a teacher would ask students about this topic, then unpack the answer across the cards.",
        "Contrast & Common Misconception Lead: Start by contrasting the correct technique on this slide with a common mistake beginners often make.",
        "Direct First-Card Lead: Start directly with the first card's key principle or decision rule and connect it logically to the remaining cards.",
        "Practical Standard Lead: Open by stating the concrete standard or field criterion students need to demonstrate for this requirement.",
    ]
    chosen_opening_style = (
        "Welcome & Course Overview Lead: Welcome students warmly and professionally to the course and explain how the session is organized."
        if is_cover
        else opening_styles[(abs(int(slide_index)) + max(0, int(variation_seed))) % len(opening_styles)]
    )

    prompt = (
        f"You are an experienced, knowledgeable instructor teaching a {badge_name} Merit Badge class ({aud_level}).\n"
        f"Rewrite the speaker notes for Slide #{slide_index + 2 if slide_index >= 0 else 1} '{title}' "
        f"(Requirement {req_num}, Archetype: {arch}, Variation #{variation_seed}) into a clear, "
        f"conversational, and professional 5-Part Non-Redundant Facilitator Guide.\n"
        f"Official Requirement Text: {s_data.get('verbatim_requirement_text') or 'N/A'}\n"
        f"Slide Cards: {json.dumps(bullets)}\n"
        f"Visual Caption: {vis_caption if has_vis else 'None'}\n"
        f"Baseline Notes: {base_notes}\n\n"
        f"STRICT TONE & FORMAT RULES:\n"
        f"1. Output exactly 5 sections starting with [PACING & MODALITY], [ASK SCOUTS FIRST], [EXPECTED PAMPHLET ANSWER KEY], [COMMON MISCONCEPTION TO CORRECT], and [DEMONSTRATION & SIGN-OFF RUBRIC].\n"
        f"2. TONE: Write like a great classroom or field teacher talking naturally and respectfully to students in the middle of an ongoing lesson. "
        f"Keep the language clear, grounded, conversational, and professional.\n"
        f"3. OPENING STYLE FOR THIS SLIDE: Use this specific opening structure in [PACING & MODALITY] so slides across the deck never sound repetitive: {chosen_opening_style}\n"
        f"4. BANNED CLICHES: NEVER start with greetings, roll-calls, or corny camp catchphrases such as 'Alright', 'Listen up', "
        f"'Gather round', 'Future lifesavers', 'Hey Scouts', 'Imagine this', 'Picture this', or 'Let's step out of the classroom'. "
        f"Jump straight into the substance of '{title}'.\n"
        f"5. In [PACING & MODALITY], include time budget, modality, and first-person instructor prose with 2-3 bracketed stage directions like "
        f"[Point to Card 1: ...] or [Studio Coaching Cue: ...]. When emphasizing key terms, wrap them in balanced double asterisks (**Term**).\n"
        f"6. In [ASK SCOUTS FIRST], ask a clear Socratic comprehension question before lecturing.\n"
        f"7. In [EXPECTED PAMPHLET ANSWER KEY], provide the concrete answer key starting with [Expected Answer: ...].\n"
        f"8. In [COMMON MISCONCEPTION TO CORRECT], state Myth vs. Fact for this requirement.\n"
        f"9. In [DEMONSTRATION & SIGN-OFF RUBRIC], give a concrete physical, equipment, or tabletop EDGE demonstration action and Application for Merit Badge (#34124) sign-off criterion.\n"
        f"10. Do NOT use em-dashes, en-dashes, or ellipses."
    )

    bridge_payload = {
        "badge_name": badge_name,
        "slide_index": slide_index,
        "slide_data": s_data,
        "audience_level": aud_level,
        "force_refresh": force_refresh,
        "variation_seed": variation_seed,
    }
    polished_notes, polish_source, fallback_reason = await asyncio.to_thread(
        _invoke_gemini_flash_polish_sync,
        prompt,
        bridge_payload,
    )

    if not polished_notes:
        polished_notes = _synthesize_studio_narrative_script(
            badge_name=badge_name,
            req_num=req_num,
            slide_title=title,
            archetype=arch,
            req_text=str(s_data.get("verbatim_requirement_text") or ""),
            bullets=bullets,
            visual_caption=vis_caption if has_vis else "",
            has_visual=has_vis,
            safety_warning=str(s_data.get("safety_warning") or ""),
            audience_level=aud_level,
            variation_seed=variation_seed,
            base_notes=base_notes,
            slide_index=slide_index,
            comparison_data=s_data.get("comparison_data"),
            worked_example=s_data.get("worked_example"),
            quiz_item=s_data.get("quiz_item"),
            gear_checklist=s_data.get("gear_checklist"),
        )
        polish_source = "PROCEDURAL_STUDIO_POLISH"

    save_polished_speaker_notes(
        notes_hash=notes_hash,
        badge_name=badge_name,
        req_number=req_num,
        slide_title=title,
        audience_level=aud_level,
        polished_notes=f"__SOURCE:{polish_source}__\n{polished_notes}",
    )

    is_gemini = polish_source == "GEMINI_FLASH"
    return {
        "notes_hash": notes_hash,
        "cache_hit": False,
        "polish_source": polish_source,
        "polish_engine": "gemini-flash" if is_gemini else "studio-narrative",
        "polish_model_label": "Gemini Flash" if is_gemini else "Studio Narrative Polish",
        "fallback_reason": fallback_reason,
        "presenter_notes": polished_notes,
    }


@app.post("/api/slide/polish-notes")
@app.post("/api/v1/slide/polish-notes")
async def api_polish_slide_speaker_notes(
    req: SlidePolishNotesRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Option C Layer 2: Polishes a single slide's Counselor Teaching Notes via Gemini Flash or Studio Narrative Synthesizer with SQLite caching."""
    from src.tools.pptx_builder import CounselorTitleSlideInfo

    t_start = time.perf_counter()
    s_data = dict(req.slide_data or {})
    res = await _polish_single_slide_notes_core(
        badge_name=req.badge_name,
        slide_index=req.slide_index,
        s_data=s_data,
        audience_level=req.audience_level,
        force_refresh=req.force_refresh,
        variation_seed=req.variation_seed,
    )
    polished_notes = res["presenter_notes"]

    rebuilt_pptx_url: Optional[str] = None
    if req.storyboard_slides:
        try:
            slides_copy = [dict(s) for s in req.storyboard_slides]
            if 0 <= req.slide_index < len(slides_copy):
                slides_copy[req.slide_index]["presenter_notes"] = polished_notes
            c_info = CounselorTitleSlideInfo(**req.counselor_info) if req.counselor_info else None
            tier = str(s_data.get("beautification_tier") or "BEAUTIFIED").upper()
            out_file = req.output_path or str(
                GENERATED_DECKS_DIR / f"{req.badge_name.strip().replace(' ', '_')}_{tier}_Polished_Merit_Badge_Deck.pptx"
            )
            eff_tpl_id = str(req.template_id or (req.storyboard_slides[0].get("template_id") if req.storyboard_slides else "") or "default_workbench").strip() or "default_workbench"
            await _async_rebuild_deck_pptx(
                badge_name=req.badge_name,
                storyboard_slides=slides_copy,
                output_path=out_file,
                counselor_info=req.counselor_info if isinstance(req.counselor_info, dict) else (req.counselor_info.__dict__ if hasattr(req.counselor_info, "__dict__") else None),
                template_id=eff_tpl_id,
                default_tier=tier if "tier" in locals() else "BEAUTIFIED",
                deck_style=req.deck_style,
            )
            build_res = {"output_path": out_file}
            if build_res.get("output_path"):
                rebuilt_pptx_url = _to_web_asset_url(build_res["output_path"])
        except Exception as exc:
            logger.warning("Failed to rebuild PPTX during polish-notes: %s", exc)

    elapsed_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
    return {
        "status": "SUCCESS",
        "slide_index": req.slide_index,
        "notes_hash": res["notes_hash"],
        "cache_hit": res["cache_hit"],
        "polish_source": res["polish_source"],
        "polish_engine": res["polish_engine"],
        "polish_model_label": res["polish_model_label"],
        "fallback_reason": res["fallback_reason"],
        "presenter_notes": polished_notes,
        "pptx_download_url": rebuilt_pptx_url,
        "duration_ms": elapsed_ms,
        "elapsed_ms": elapsed_ms,
    }


@app.post("/api/slide/polish-notes-batch")
@app.post("/api/v1/slide/polish-notes-batch")
async def api_polish_deck_speaker_notes_batch(
    req: SlidePolishDeckBatchRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Polishes all slides across the entire Merit Badge deck in parallel with SQLite caching and a single PPTX rebuild."""
    from src.tools.pptx_builder import CounselorTitleSlideInfo

    t_start = time.perf_counter()
    slides_copy = [dict(s) for s in (req.storyboard_slides or [])]
    sem = asyncio.Semaphore(12)
    cache_hits = 0
    gemini_count = 0
    last_fallback_reason = ""
    cover_presenter_notes = ""

    async def _polish_cover() -> None:
        nonlocal cover_presenter_notes
        async with sem:
            c_res = await _polish_single_slide_notes_core(
                badge_name=req.badge_name,
                slide_index=-1,
                s_data={
                    "title": f"{req.badge_name} Merit Badge - Cover Slide",
                    "req_number": "Cover",
                    "archetype": "TITLE_COVER_HERO",
                },
                audience_level=req.audience_level,
                force_refresh=req.force_refresh,
                variation_seed=1,
            )
            cover_presenter_notes = c_res["presenter_notes"]

    async def _polish_idx(idx: int, s_obj: Dict[str, Any]) -> None:
        nonlocal cache_hits, gemini_count, last_fallback_reason
        if not req.force_refresh and s_obj.get("_isPolishedNotes") and s_obj.get("presenter_notes"):
            cache_hits += 1
            if s_obj.get("_polishSource") == "GEMINI_FLASH":
                gemini_count += 1
            return
        async with sem:
            if not s_obj.get("_originalProceduralNotes") and s_obj.get("presenter_notes"):
                s_obj["_originalProceduralNotes"] = s_obj["presenter_notes"]
            r = await _polish_single_slide_notes_core(
                badge_name=req.badge_name,
                slide_index=idx,
                s_data=s_obj,
                audience_level=req.audience_level,
                force_refresh=req.force_refresh,
                variation_seed=(idx % 5) + 1,
            )
            s_obj["presenter_notes"] = r["presenter_notes"]
            s_obj["_isPolishedNotes"] = True
            s_obj["_polishSource"] = r["polish_source"]
            s_obj["_polishEngine"] = r["polish_engine"]
            s_obj["_polishModelLabel"] = r["polish_model_label"]
            s_obj["_polishFallbackReason"] = r["fallback_reason"]
            if r["cache_hit"]:
                cache_hits += 1
            if r["polish_source"] == "GEMINI_FLASH":
                gemini_count += 1
            elif r["fallback_reason"] and not last_fallback_reason:
                last_fallback_reason = r["fallback_reason"]

    await asyncio.gather(
        _polish_cover(),
        *[_polish_idx(i, s) for i, s in enumerate(slides_copy)],
    )

    rebuilt_pptx_url: Optional[str] = None
    if slides_copy:
        try:
            c_info = CounselorTitleSlideInfo(**req.counselor_info) if req.counselor_info else None
            tier = str(slides_copy[0].get("beautification_tier") or "BEAUTIFIED").upper()
            out_file = req.output_path or str(
                GENERATED_DECKS_DIR / f"{req.badge_name.strip().replace(' ', '_')}_{tier}_Deck_Polished_Merit_Badge_Deck.pptx"
            )
            eff_tpl_id = str(req.template_id or (req.storyboard_slides[0].get("template_id") if req.storyboard_slides else "") or "default_workbench").strip() or "default_workbench"
            await _async_rebuild_deck_pptx(
                badge_name=req.badge_name,
                storyboard_slides=slides_copy,
                output_path=out_file,
                counselor_info=req.counselor_info if isinstance(req.counselor_info, dict) else (req.counselor_info.__dict__ if hasattr(req.counselor_info, "__dict__") else None),
                template_id=eff_tpl_id,
                default_tier=tier if "tier" in locals() else "BEAUTIFIED",
                deck_style=req.deck_style,
            )
            build_res = {"output_path": out_file}
            if build_res.get("output_path"):
                rebuilt_pptx_url = _to_web_asset_url(build_res["output_path"])
        except Exception as exc:
            logger.warning("Failed to rebuild PPTX during polish-notes-batch: %s", exc)

    elapsed_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
    batch_source = "GEMINI_FLASH" if gemini_count > 0 else "PROCEDURAL_STUDIO_POLISH"
    return {
        "status": "SUCCESS",
        "badge_name": req.badge_name,
        "polished_count": len(slides_copy),
        "gemini_count": gemini_count,
        "cache_hits": cache_hits,
        "polish_source": batch_source,
        "polish_engine": "gemini-flash" if gemini_count > 0 else "studio-narrative",
        "polish_model_label": "Gemini Flash" if gemini_count > 0 else "Studio Narrative Polish",
        "fallback_reason": last_fallback_reason,
        "cover_presenter_notes": cover_presenter_notes,
        "slides": slides_copy,
        "storyboard_slides": slides_copy,
        "pptx_download_url": rebuilt_pptx_url,
        "duration_ms": elapsed_ms,
        "elapsed_ms": elapsed_ms,
    }


@app.post("/api/slide/estimate-polish-cost")
@app.post("/api/v1/slide/estimate-polish-cost")
async def api_estimate_slide_polish_cost(
    req: SlidePolishEstimateRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Calculates exact Gemini Flash token & USD cost estimates for polishing a single slide vs. the entire deck, accounting for SQLite cache hits."""
    import hashlib
    from src.memory.session_store import get_polished_speaker_notes

    def _hash_for_slide(idx: int, s_data: Dict[str, Any]) -> str:
        is_cover = idx == -1 or str(s_data.get("req_number") or "").lower() == "cover"
        req_num = "Cover" if is_cover else str(s_data.get("req_number") or (idx + 1))
        title = str(
            s_data.get("title")
            or (f"{req.badge_name} Merit Badge Cover Slide" if is_cover else f"{req.badge_name} Requirement {req_num}")
        )
        arch = "COVER" if is_cover else str(s_data.get("archetype") or "SPLIT_VISUAL_EXPLAINER").upper()
        bullets = [str(b) for b in (s_data.get("bullet_points") or []) if str(b).strip()]
        vis_caption = str(s_data.get("visual_caption") or "")
        has_vis = bool(s_data.get("diagram_path") or s_data.get("diagram_url"))
        aud_level = str(req.audience_level or s_data.get("audience_level") or "All Scouts (Ages 11-17)")
        payload = json.dumps(
            {
                "v": "gemini_flash_v4",
                "badge": req.badge_name.strip().lower(),
                "req": req_num,
                "slide_idx": idx,
                "title": title,
                "arch": arch,
                "bullets": bullets,
                "caption": vis_caption if has_vis else "",
                "has_vis": has_vis,
                "audience": aud_level,
                "seed": 0,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

    def _is_valid_cached(h: str) -> bool:
        raw = get_polished_speaker_notes(h)
        if not raw:
            return False
        if (
            "Let's step out of the classroom for a moment" in raw
            or "Alright," in raw
            or "listen up" in raw.lower()
            or "gather 'round" in raw.lower()
            or "future lifesavers" in raw.lower()
        ):
            return False
        return True

    # Gemini Flash (thinking_budget=0) pricing: $0.30 / 1M input tokens, $2.50 / 1M output tokens
    # Avg per-slide: ~450 input tokens ($0.000135) + ~280 output tokens ($0.000700) = $0.000835 / slide
    per_slide_in_tokens = 450
    per_slide_out_tokens = 280
    per_slide_usd = round((per_slide_in_tokens * 0.30 / 1_000_000.0) + (per_slide_out_tokens * 2.50 / 1_000_000.0), 6)

    active_s_data = dict(req.slide_data or {})
    if not active_s_data and 0 <= req.slide_index < len(req.storyboard_slides):
        active_s_data = dict(req.storyboard_slides[req.slide_index] or {})
    single_cached = _is_valid_cached(_hash_for_slide(req.slide_index, active_s_data))

    visible_slides = [
        (idx, s) for idx, s in enumerate(req.storyboard_slides or []) if isinstance(s, dict) and not s.get("hidden")
    ]
    total_deck_slides = len(visible_slides) + 1  # Include Cover Slide (-1)
    cached_count = 1 if _is_valid_cached(_hash_for_slide(-1, {"req_number": "Cover", "title": f"{req.badge_name} Merit Badge Cover Slide"})) else 0
    for idx, s in visible_slides:
        if _is_valid_cached(_hash_for_slide(idx, s)):
            cached_count += 1
    uncached_count = max(0, total_deck_slides - cached_count)

    return {
        "status": "SUCCESS",
        "badge_name": req.badge_name,
        "model_label": "Gemini Flash",
        "single_slide_index": req.slide_index,
        "single_slide_cached": single_cached,
        "single_slide_input_tokens": per_slide_in_tokens,
        "single_slide_output_tokens": per_slide_out_tokens,
        "single_slide_cost_usd": round(per_slide_usd, 5),
        "total_slides": total_deck_slides,
        "cached_slides_count": cached_count,
        "uncached_slides_count": uncached_count,
        "deck_uncached_cost_usd": round(uncached_count * per_slide_usd, 4),
        "deck_full_repolish_cost_usd": round(total_deck_slides * per_slide_usd, 4),
        "pricing_rate_summary": "$0.30 / 1M input tokens • $2.50 / 1M output tokens (thinking_budget=0)",
    }


@app.get("/api/qr.svg")
@app.get("/api/v1/qr.svg")
async def api_generate_qr_svg(
    url: str = Query("https://www.scouting.org/skills/merit-badges/", description="Target URL to encode as an ISO/IEC 18004 QR Code SVG."),
    data: Optional[str] = Query(None, description="Optional alias for `url` query parameter."),
    size: int = Query(96, ge=48, le=512, description="Rendered SVG width/height in pixels."),
) -> Response:
    """Returns a standard-compliant, phone-camera-scannable ISO/IEC 18004 QR Code SVG for `url`."""
    from src.tools.qr_generator import render_qr_svg

    effective_url = str(data or url or "https://www.scouting.org/skills/merit-badges/").strip()
    svg_str = render_qr_svg(url=effective_url, size_px=size)
    return Response(content=svg_str, media_type="image/svg+xml")


def _detect_workstation_google_account() -> Dict[str, Any]:
    """Detects the active workstation/server Google account and whether direct Google Drive upload is available."""
    import subprocess

    gdrive_bin = Path("/google/bin/releases/gemini-agents-gdrive/gdrive")
    has_gdrive_cli = gdrive_bin.exists()
    account_email = os.environ.get("GOOGLE_ACCOUNT_EMAIL", "").strip()
    if not account_email:
        try:
            proc = subprocess.run(
                ["gcloud", "config", "get-value", "account"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            candidate = (proc.stdout or "").strip()
            if proc.returncode == 0 and "@" in candidate and not candidate.endswith(".gserviceaccount.com"):
                account_email = candidate
        except Exception:
            pass
    if not account_email:
        user_env = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
        if user_env and user_env not in ("root", "nobody", "appuser"):
            account_email = f"{user_env}@google.com"
    if not account_email:
        account_email = os.environ.get("BSA_DEFAULT_GOOGLE_ACCOUNT", "counselor@scouting.org")

    oauth_client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    has_env_token = bool(os.environ.get("GOOGLE_DRIVE_ACCESS_TOKEN", "").strip())
    adc_available = bool(has_gdrive_cli or has_env_token or os.environ.get("K_SERVICE") or account_email)
    return {
        "status": "SUCCESS",
        "detected_account_email": account_email,
        "workstation_account_email": account_email,
        "direct_drive_ready": bool(has_gdrive_cli or has_env_token or account_email),
        "gdrive_cli_available": has_gdrive_cli,
        "has_gdrive_cli": has_gdrive_cli,
        "adc_available": adc_available,
        "oauth_client_id": oauth_client_id,
        "google_account_chooser_url": "https://accounts.google.com/AccountChooser?continue=https://docs.google.com/presentation/u/0/",
    }


# Allowlisted User & Engineering Documentation Registry (Strictly excludes all 5 CAPSTONE files and Google Docs links)
GITHUB_REPO_BASE_URL = "https://github.com/clayberg/scouts-bsa-merit-badge-agent"

CURATED_DOCUMENTATION_CATALOG: List[Dict[str, str]] = [
    {
        "id": "user_guide",
        "title": "User Guide",
        "short_label": "📘 User Guide",
        "subtitle": "Complete Counselor Workbench Manual, Visual Tour & Field Toolkit Guide",
        "category": "user",
        "repo_path": "docs/USER_GUIDE.md",
    },
    {
        "id": "admin_guide",
        "title": "Admin Guide",
        "short_label": "🛡️ Admin Guide",
        "subtitle": "Super-User Admin Console, 144-Badge Visual Catalog Studio & Zero-PII Telemetry",
        "category": "user",
        "repo_path": "docs/ADMIN_GUIDE.md",
    },
    {
        "id": "readme",
        "title": "README",
        "short_label": "📦 README",
        "subtitle": "Repository Overview, Quick Start, Architecture & Configuration Reference",
        "category": "engineering",
        "repo_path": "README.md",
    },
    {
        "id": "tdd",
        "title": "TDD",
        "short_label": "🏗️ TDD",
        "subtitle": "Technical Design Document: Multi-Agent Pipeline, Data Contracts & Conformance",
        "category": "engineering",
        "repo_path": "docs/TDD.md",
    },
    {
        "id": "architecture_decisions",
        "title": "ARCHITECTURE DECISIONS",
        "short_label": "⚖️ ARCHITECTURE DECISIONS",
        "subtitle": "Full Architecture Decision Records (ADR-01 through ADR-11) & Trade-Off Matrices",
        "category": "engineering",
        "repo_path": "ARCHITECTURE_DECISIONS.md",
    },
    {
        "id": "adr_readme",
        "title": "ADR SUMMARY (docs/ADR.md)",
        "short_label": "🗂️ docs/ADR.md",
        "subtitle": "Summary Index of Architecture Decision Records, Deferred Sandbox Matrix & Rubric A4 Log",
        "category": "engineering",
        "repo_path": "docs/ADR.md",
    },
    {
        "id": "api_integration_guide",
        "title": "API INTEGRATION GUIDE",
        "short_label": "🔌 API INTEGRATION GUIDE",
        "subtitle": "REST (/api/v1/*), Server-Sent Events (SSE), and A2A 1.0 Integration Reference",
        "category": "engineering",
        "repo_path": "docs/API_INTEGRATION_GUIDE.md",
    },
    {
        "id": "mcp_server_guide",
        "title": "MCP SERVER GUIDE",
        "short_label": "🤖 MCP SERVER GUIDE",
        "subtitle": "Model Context Protocol (MCP) Server: stdio + HTTP /mcp, 14 Tools, 5 Resources & 3 Prompts",
        "category": "engineering",
        "repo_path": "docs/MCP_SERVER_INTEGRATION_GUIDE.md",
    },
    {
        "id": "finops_guide",
        "title": "FINOPS & TCO GUIDE",
        "short_label": "💰 FINOPS & TCO",
        "subtitle": "FinOps Token Billing, Pre-Bundled Visual Economics, Council TCO & Cost Consent Gates",
        "category": "engineering",
        "repo_path": "docs/FINOPS_AND_TCO.md",
    },
    {
        "id": "scope",
        "title": "SCOPE",
        "short_label": "🎯 SCOPE",
        "subtitle": "Product Scope, Target Personas, Boundaries & Definition of Done",
        "category": "engineering",
        "repo_path": "SCOPE.md",
    },
    {
        "id": "spec",
        "title": "SPEC",
        "short_label": "📐 SPEC",
        "subtitle": "Technical Specification of Agent Topology, Schemas & API Endpoints",
        "category": "engineering",
        "repo_path": "SPEC.md",
    },
    {
        "id": "runbook",
        "title": "RUNBOOK",
        "short_label": "🚨 RUNBOOK",
        "subtitle": "SRE Operational Runbook, Diagnostics, Incident Playbooks & Recovery",
        "category": "engineering",
        "repo_path": "docs/RUNBOOK.md",
    },
]


def _extract_markdown_headings(md_text: str) -> List[Dict[str, Any]]:
    """Extracts H1-H3 headings from Markdown text (ignoring fenced code blocks) for the 'On This Page' TOC."""
    headings: List[Dict[str, Any]] = []
    in_fence = False
    for raw_line in (md_text or "").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(#{1,3})\s+(.+?)\s*$", stripped)
        if m:
            level = len(m.group(1))
            clean_title = re.sub(r"[`*_~]+", "", m.group(2)).strip()
            clean_title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_title)
            slug = re.sub(r"[^a-z0-9]+", "-", clean_title.lower()).strip("-")
            if clean_title and slug:
                headings.append({"level": level, "title": clean_title, "slug": slug})
    return headings


@app.get("/api/docs")
@app.get("/api/v1/docs")
async def api_list_curated_documentation() -> Dict[str, Any]:
    """Returns the catalog of User Docs (2) and Engineering Docs (9) for the In-App Documentation Viewer."""
    items: List[Dict[str, Any]] = []
    for entry in CURATED_DOCUMENTATION_CATALOG:
        items.append(
            {
                **entry,
                "doc_id": entry["id"],
                "rel_path": entry["repo_path"],
                "github_url": f"{GITHUB_REPO_BASE_URL}/blob/main/{entry['repo_path']}",
            }
        )
    return {
        "status": "SUCCESS",
        "github_repo_url": GITHUB_REPO_BASE_URL,
        "default_doc_id": "user_guide",
        "total_count": len(items),
        "user_docs": [d for d in items if d["category"] == "user"],
        "engineering_docs": [d for d in items if d["category"] == "engineering"],
        "documents": items,
        "all_docs": items,
    }


@app.get("/api/docs/{doc_id}")
@app.get("/api/v1/docs/{doc_id}")
async def api_get_curated_documentation_content(doc_id: str) -> Dict[str, Any]:
    """Returns the Markdown content, GitHub URL, and parsed section outline for an allowlisted document."""
    norm_id = doc_id.strip().lower().replace("-", "_")
    raw_lower = doc_id.strip().lower()
    alias_map = {
        "arch_decisions": "architecture_decisions",
        "api_guide": "api_integration_guide",
    }
    norm_id = alias_map.get(norm_id, norm_id)
    matched = next(
        (
            d
            for d in CURATED_DOCUMENTATION_CATALOG
            if d["id"] == norm_id
            or d["repo_path"].lower() == raw_lower
            or Path(d["repo_path"]).name.lower() == raw_lower
        ),
        None,
    )
    if not matched:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' is not in the curated documentation catalog.")
    file_path = PROJECT_ROOT / matched["repo_path"]
    content: Optional[str] = None
    if file_path.exists():
        content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
    else:
        # Resilient fallback: fetch from canonical GitHub raw URL if a doc file was omitted from a minimal container layer
        raw_url = f"https://raw.githubusercontent.com/clayberg/scouts-bsa-merit-badge-agent/main/{matched['repo_path']}"
        def _fetch_remote_md() -> Optional[str]:
            import urllib.request
            try:
                req = urllib.request.Request(raw_url, headers={"User-Agent": "ScoutsBSA-Workbench/2.5"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    if resp.status == 200:
                        return resp.read().decode("utf-8", errors="replace")
            except Exception:
                return None
            return None
        content = await asyncio.to_thread(_fetch_remote_md)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Documentation file '{matched['repo_path']}' not found on disk.")
    headings = _extract_markdown_headings(content)
    return {
        "status": "SUCCESS",
        **matched,
        "doc_id": matched["id"],
        "rel_path": matched["repo_path"],
        "github_url": f"{GITHUB_REPO_BASE_URL}/blob/main/{matched['repo_path']}",
        "markdown": content,
        "headings": headings,
    }


@app.get("/api/slide/export-gslides/account-info")
@app.get("/api/v1/slide/export-gslides/account-info")
async def api_get_google_slides_account_info(
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Returns the detected Google account and authentication options for 'Open in Google Slides'."""
    return await asyncio.to_thread(_detect_workstation_google_account)


@app.post("/api/slide/export-gslides")
@app.post("/api/v1/slide/export-gslides")
async def api_export_slide_deck_to_google_slides(
    req: GoogleSlidesExportRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Exports the active Merit Badge slide deck directly to a native Google Slides presentation via Google Drive API conversion."""
    import subprocess
    import requests as ext_requests
    from src.tools.pptx_builder import CounselorTitleSlideInfo

    t_start = time.perf_counter()
    pptx_file: Optional[Path] = None
    eff_tpl_id = str(
        req.template_id
        or (req.storyboard_slides[0].get("template_id") if req.storyboard_slides else "")
        or "default_workbench"
    ).strip() or "default_workbench"

    # When storyboard_slides are supplied, rebuild .pptx with the active template_id so any template changes or slide edits are guaranteed in Google Slides
    if req.storyboard_slides:
        try:
            c_info = CounselorTitleSlideInfo(**req.counselor_info) if req.counselor_info else None
            out_file = str(
                GENERATED_DECKS_DIR
                / f"{req.badge_name.strip().replace(' ', '_')}_{eff_tpl_id}_{req.beautification_tier}_GoogleSlides_Export.pptx"
            )
            if req.storyboard_slides:
                await _async_rebuild_deck_pptx(
                    badge_name=req.badge_name,
                    storyboard_slides=req.storyboard_slides,
                    output_path=out_file,
                    counselor_info=c_info.model_dump() if hasattr(c_info, "model_dump") else getattr(c_info, "__dict__", None),
                    template_id=eff_tpl_id,
                    deck_style=req.deck_style,
                )
                build_res = {"output_path": out_file}
                if build_res.get("output_path") and Path(build_res["output_path"]).exists():
                    pptx_file = Path(build_res["output_path"])
        except Exception as exc:
            logger.warning("Rebuild before export-gslides warning: %s", exc)

    if not pptx_file or not pptx_file.exists():
        if req.pptx_download_url:
            clean_rel = req.pptx_download_url.split("?")[0].lstrip("/")
            cand = PROJECT_ROOT / clean_rel
            if cand.exists():
                pptx_file = cand
            elif (GENERATED_DECKS_DIR / Path(clean_rel).name).exists():
                pptx_file = GENERATED_DECKS_DIR / Path(clean_rel).name
        if (not pptx_file or not pptx_file.exists()) and req.output_path and Path(req.output_path).exists():
            pptx_file = Path(req.output_path)

    if not pptx_file or not pptx_file.exists():
        # Fallback to most recent .pptx matching badge_name in GENERATED_DECKS_DIR
        slug_prefix = req.badge_name.strip().replace(" ", "_").lower()
        candidates = sorted(
            [p for p in GENERATED_DECKS_DIR.glob("*.pptx") if p.name.lower().startswith(slug_prefix)],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            candidates = sorted(GENERATED_DECKS_DIR.glob("*.pptx"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            pptx_file = candidates[0]

    if not pptx_file or not pptx_file.exists():
        raise HTTPException(status_code=404, detail="No generated PPTX deck found to convert to Google Slides.")

    theme_display = {"STANDARD": "Crisp White", "BEAUTIFIED": "Warm Cream", "STUDIO": "Dark Slate"}.get(
        str(req.beautification_tier or "BEAUTIFIED").upper(), "Warm Cream"
    )
    deck_title = f"{req.badge_name} Merit Badge — Counselor Teaching Deck ({theme_display})"
    explicit_oauth_token = (req.user_access_token or req.google_oauth_access_token or "").strip()
    access_token = explicit_oauth_token or os.environ.get("GOOGLE_DRIVE_ACCESS_TOKEN", "").strip()
    auth_mode = "USER_OAUTH_TOKEN" if explicit_oauth_token else ("ENV_TOKEN" if access_token else "")
    target_share_email = (req.share_with_email or "").strip()
    acct_info = await asyncio.to_thread(_detect_workstation_google_account)
    detected_email = str(acct_info.get("workstation_account_email") or "")

    if not access_token and req.use_adc:
        try:
            import google.auth
            import google.auth.transport.requests

            creds, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
            )
            creds.refresh(google.auth.transport.requests.Request())
            if creds.token:
                access_token = str(creds.token).strip()
                auth_mode = "GOOGLE_ADC"
        except Exception:
            pass

    if not access_token and req.use_adc:
        try:
            proc = subprocess.run(
                ["gcloud", "auth", "print-access-token"],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                access_token = proc.stdout.strip()
                auth_mode = "GCLOUD_CLI"
        except Exception:
            pass

    # Tier 1 & 2: Direct Google Drive v3 Multipart REST Upload (when token has Drive scope)
    if access_token:
        try:
            def _upload_to_drive() -> Dict[str, Any]:
                metadata = {
                    "name": deck_title,
                    "mimeType": "application/vnd.google-apps.presentation",
                }
                boundary = "===============bsa_merit_badge_gslides_boundary=="
                pptx_bytes = pptx_file.read_bytes()
                body = (
                    f"--{boundary}\r\n"
                    f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
                    f"{json.dumps(metadata)}\r\n"
                    f"--{boundary}\r\n"
                    f"Content-Type: application/vnd.openxmlformats-officedocument.presentationml.presentation\r\n\r\n"
                ).encode("utf-8") + pptx_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

                resp = ext_requests.post(
                    "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink,owners",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": f"multipart/related; boundary={boundary}",
                    },
                    data=body, timeout=15,
                )
                if resp.status_code in (200, 201):
                    data_json = resp.json()
                    if target_share_email and "@" in target_share_email and data_json.get("id"):
                        try:
                            ext_requests.post(
                                f"https://www.googleapis.com/drive/v3/files/{data_json['id']}/permissions",
                                headers={
                                    "Authorization": f"Bearer {access_token}",
                                    "Content-Type": "application/json",
                                },
                                json={"role": "writer", "type": "user", "emailAddress": target_share_email}, timeout=15,
                            )
                        except Exception:
                            pass
                    return data_json
                return {"error_status": resp.status_code, "error_body": resp.text[:300]}

            drive_res = await asyncio.to_thread(_upload_to_drive)
            if drive_res.get("id"):
                pres_id = str(drive_res["id"])
                owners = drive_res.get("owners") or []
                owner_email = (
                    str(owners[0].get("emailAddress") or "")
                    if owners and isinstance(owners[0], dict)
                    else detected_email
                )
                pres_url = str(drive_res.get("webViewLink") or f"https://docs.google.com/presentation/d/{pres_id}/edit")
                if target_share_email and "@" in target_share_email:
                    sep = "&" if "?" in pres_url else "?"
                    pres_url = f"{pres_url}{sep}authuser={target_share_email}"
                return {
                    "status": "SUCCESS",
                    "auth_mode": auth_mode,
                    "account_email": owner_email or detected_email,
                    "shared_with_email": target_share_email,
                    "badge_name": req.badge_name,
                    "presentation_id": pres_id,
                    "presentation_url": pres_url,
                    "deck_title": deck_title,
                    "pptx_download_url": _to_web_asset_url(str(pptx_file)),
                    "duration_ms": round((time.perf_counter() - t_start) * 1000.0, 2),
                }
        except Exception as exc:
            logger.warning("Direct Drive API Google Slides conversion warning: %s", exc)

    # Tier 3: Workstation gdrive CLI (/google/bin/releases/gemini-agents-gdrive/gdrive)
    gdrive_bin = Path("/google/bin/releases/gemini-agents-gdrive/gdrive")
    if req.use_adc and gdrive_bin.exists():
        try:
            def _upload_via_gdrive_cli() -> Optional[str]:
                proc = subprocess.run(
                    [
                        str(gdrive_bin),
                        "mutate",
                        "upload",
                        str(pptx_file),
                        "--mime-type",
                        "application/vnd.google-apps.presentation",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=45,
                    check=False,
                )
                combined = f"{proc.stdout or ''}\n{proc.stderr or ''}"
                m_id = re.search(r"\(ID:\s*([A-Za-z0-9_-]{15,})\)", combined)
                if not m_id:
                    return None
                fid = m_id.group(1)
                try:
                    subprocess.run(
                        [str(gdrive_bin), "mutate", "rename", fid, deck_title],
                        capture_output=True,
                        text=True,
                        timeout=12,
                        check=False,
                    )
                except Exception:
                    pass
                if target_share_email and "@" in target_share_email and target_share_email.lower() != detected_email.lower():
                    try:
                        subprocess.run(
                            [
                                str(gdrive_bin),
                                "mutate",
                                "share",
                                fid,
                                "--email",
                                target_share_email,
                                "--role",
                                "writer",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=15,
                            check=False,
                        )
                    except Exception:
                        pass
                return fid

            cli_pres_id = await asyncio.to_thread(_upload_via_gdrive_cli)
            if cli_pres_id:
                pres_url = f"https://docs.google.com/presentation/d/{cli_pres_id}/edit"
                effective_user = target_share_email if (target_share_email and "@" in target_share_email) else detected_email
                if effective_user:
                    pres_url = f"{pres_url}?authuser={effective_user}"
                return {
                    "status": "SUCCESS",
                    "auth_mode": "WORKSTATION_GDRIVE_CLI",
                    "account_email": detected_email or "Workstation Google Account",
                    "shared_with_email": target_share_email,
                    "badge_name": req.badge_name,
                    "presentation_id": cli_pres_id,
                    "presentation_url": pres_url,
                    "deck_title": deck_title,
                    "pptx_download_url": _to_web_asset_url(str(pptx_file)),
                    "duration_ms": round((time.perf_counter() - t_start) * 1000.0, 2),
                }
        except Exception as exc:
            logger.warning("gdrive CLI Google Slides conversion warning: %s", exc)

    return {
        "status": "AUTH_GUIDED_IMPORT",
        "auth_mode": "OAUTH_CLIENT_OR_GUIDED_IMPORT",
        "account_email": detected_email,
        "oauth_client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
        "badge_name": req.badge_name,
        "deck_title": deck_title,
        "pptx_download_url": _to_web_asset_url(str(pptx_file)),
        "slides_import_url": "https://accounts.google.com/AccountChooser?continue=https://docs.google.com/presentation/u/0/",
        "google_slides_import_url": "https://accounts.google.com/AccountChooser?continue=https://docs.google.com/presentation/u/0/",
        "message": (
            "Choose a Google account via OAuth 2.0 or import the generated .pptx into your selected Google account."
        ),
        "duration_ms": round((time.perf_counter() - t_start) * 1000.0, 2),
    }


class SlideDeckCustomizeRequest(BaseModel):
    badge_name: str = Field("First Aid", description="Official Merit Badge name.")
    action: str = Field(
        "sync_slides",
        description="Customization action (`insert_custom_slide`, `toggle_hide_slide`, `hide_home_prereq_slides`, `reorder_slide`, `sync_slides`).",
    )
    slide_index: int = Field(0, description="Target slide index in storyboard_slides.")
    direction: Optional[str] = Field(None, description="Reorder direction (`up` or `down`).")
    hide_prereqs: Optional[bool] = Field(None, description="Whether to hide home-prereq slides.")
    custom_slide: Optional[Dict[str, Any]] = Field(None, description="Custom slide payload when action is `insert_custom_slide`.")
    storyboard_slides: List[Dict[str, Any]] = Field(default_factory=list, description="Full slide array from client state.")
    counselor_info: Optional[Dict[str, Any]] = Field(None, description="Optional Counselor Title Slide metadata.")
    output_path: Optional[str] = Field(None, description="Optional PPTX output path.")
    template_id: Optional[str] = Field("default_workbench", description="Optional PowerPoint template ID.")
    deck_style: Optional[Dict[str, Any]] = Field(None, description="Optional DeckStyleConfig dictionary.")


@app.post("/api/slide/deck-customize")
@app.post("/api/v1/slide/deck-customize")
async def api_customize_slide_deck(
    req: SlideDeckCustomizeRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Inserts a custom local slide, hides/skips slides, or reorders slides, and rebuilds the .pptx excluding hidden slides."""
    from src.tools.pptx_builder import (
    CounselorTitleSlideInfo,
        PowerPointBuildRequest,
        SlideSpec,
        generate_bsa_slide_deck_pptx,
    )

    slides_list = [dict(s) for s in (req.storyboard_slides or [])]
    tpl_id = str(req.template_id or "default_workbench").strip() or "default_workbench"
    for s in slides_list:
        if tpl_id != "default_workbench" or not s.get("template_id"):
            s["template_id"] = tpl_id
    act = (req.action or "sync_slides").strip().lower()
    active_idx = max(0, min(req.slide_index, max(0, len(slides_list) - 1)))

    if act in ("insert_custom_slide", "insert") and isinstance(req.custom_slide, dict):
        cs = dict(req.custom_slide)
        new_slide = {
            "req_number": str(cs.get("req_number") or "Local"),
            "title": str(cs.get("title") or "Local Camp & Troop Instructions"),
            "bullet_points": [
                str(b).strip()
                for b in (cs.get("bullet_points") or ["Local troop or camp expectation."])
                if str(b).strip()
            ][:4],
            "presenter_notes": str(
                cs.get("presenter_notes")
                or "[SAY] Review these local camp rules and troop expectations with your patrol."
            ),
            "safety_warning": cs.get("safety_warning"),
            "archetype": str(cs.get("archetype") or "CONCEPT_TEXT_SLIDE"),
            "visual_theme": str(cs.get("visual_theme") or "NUMBERED_STEP_CARDS"),
            "accent_palette_key": str(cs.get("accent_palette_key") or "FOREST_GREEN"),
            "beautification_tier": str(cs.get("beautification_tier") or "BEAUTIFIED"),
            "visual_source_label": str(cs.get("visual_source_label") or "Custom Counselor Slide"),
            "visual_caption": str(cs.get("visual_caption") or cs.get("title") or "Custom Slide"),
            "diagram_path": cs.get("diagram_path"),
            "diagram_url": cs.get("diagram_url"),
            "is_custom_slide": True,
            "hidden": False,
        }
        insert_pos = min(len(slides_list), active_idx + 1)
        slides_list.insert(insert_pos, new_slide)
        active_idx = insert_pos
    elif act in ("toggle_hide_slide", "toggle_hide") and 0 <= active_idx < len(slides_list):
        slides_list[active_idx]["hidden"] = not bool(slides_list[active_idx].get("hidden"))
    elif act in ("hide_home_prereq_slides", "hide_prereqs"):
        prereq_keywords = (
            "home", "30 day", "90 day", "chore", "log", "budget", "family", "parent",
            "prerequisite", "prereq", "before camp", "track for", "menu for",
        )
        target_hide = True if req.hide_prereqs is None else bool(req.hide_prereqs)
        for s in slides_list:
            blob = f"{s.get('title', '')} {' '.join(s.get('bullet_points') or [])}".lower()
            if any(k in blob for k in prereq_keywords) or bool(s.get("is_home_prereq")):
                s["hidden"] = target_hide
                s["is_home_prereq"] = True
    elif act in ("reorder_slide", "move_up", "move_down") and 0 <= active_idx < len(slides_list):
        direction = "up" if act == "move_up" else ("down" if act == "move_down" else (req.direction or "down").strip().lower())
        swap_idx = active_idx - 1 if direction == "up" else active_idx + 1
        if 0 <= swap_idx < len(slides_list):
            slides_list[active_idx], slides_list[swap_idx] = slides_list[swap_idx], slides_list[active_idx]
            active_idx = swap_idx

    visible_specs = [
        SlideSpec(**{k: v for k, v in s.items() if k in SlideSpec.model_fields})
        for s in slides_list
        if not s.get("hidden")
    ]
    rebuilt_pptx_url: Optional[str] = None
    if visible_specs:
        try:
            c_info = CounselorTitleSlideInfo(**req.counselor_info) if req.counselor_info else None
            out_file = req.output_path or str(
                GENERATED_DECKS_DIR / f"{req.badge_name.strip().replace(' ', '_')}_Customized_Merit_Badge_Deck.pptx"
            )
            build_res = await asyncio.to_thread(
                generate_bsa_slide_deck_pptx,
                PowerPointBuildRequest(
                    badge_name=req.badge_name,
                    slides=visible_specs,
                    counselor_info=c_info,
                    output_path=out_file,
                    template_id=tpl_id,
                    deck_style=req.deck_style,
                ),
            )
            if build_res.get("output_path"):
                rebuilt_pptx_url = _to_web_asset_url(build_res["output_path"])
        except Exception as exc:
            logger.warning("Failed to rebuild PPTX in deck-customize: %s", exc)

    hidden_cnt = sum(1 for s in slides_list if s.get("hidden"))
    return {
        "status": "SUCCESS",
        "action": act,
        "active_slide_index": active_idx,
        "total_slide_count": len(slides_list),
        "visible_slide_count": len(visible_specs),
        "hidden_slide_count": hidden_cnt,
        "pptx_download_url": rebuilt_pptx_url,
        "slides": slides_list,
        "storyboard_slides": slides_list,
    }


class StudioKitAgendaRequest(BaseModel):
    badge_name: str = "First Aid"
    schedule_format: str = "3 Troop Meetings (45 min each)"
    schedule_type: Optional[str] = None
    research_result: Dict[str, Any] = Field(default_factory=dict)
    counselor_info: Optional[Dict[str, Any]] = None
    counselor_name: Optional[str] = None
    troop_affiliation: Optional[str] = None
    location_or_zip: Optional[str] = None
    postponed_session_idx: Optional[int] = None
    companion_badge_name: Optional[str] = None


class StudioKitFillableWorkbookRequest(BaseModel):
    badge_name: str = "First Aid"
    selected_option_track: Optional[str] = None
    counselor_info: Optional[Dict[str, Any]] = None
    include_qr: bool = True


class StudioKitClassPrepCppRequest(BaseModel):
    badge_name: str = "First Aid"
    schedule_format: str = "4_session_mbc"
    counselor_info: Optional[Dict[str, Any]] = None
    class_logistics: Optional[Dict[str, Any]] = None
    research_result: Dict[str, Any] = Field(default_factory=dict)


class StudioKitOrganizerSpecRequest(BaseModel):
    badge_name: str = "First Aid"
    schedule_format: str = "4_session_mbc"
    counselor_info: Optional[Dict[str, Any]] = None
    class_logistics: Optional[Dict[str, Any]] = None
    research_result: Dict[str, Any] = Field(default_factory=dict)


class StudioKitYptThreeStageRequest(BaseModel):
    badge_name: str = "First Aid"
    counselor_info: Optional[Dict[str, Any]] = None
    class_logistics: Optional[Dict[str, Any]] = None
    scout_roster: Optional[List[Dict[str, Any]]] = None
    research_result: Dict[str, Any] = Field(default_factory=dict)


class SlideLogisticsInjectRequest(BaseModel):
    badge_name: str = "First Aid"
    slides: List[Dict[str, Any]] = Field(default_factory=list)
    logistics_config: Dict[str, Any] = Field(default_factory=dict)
    counselor_info: Optional[Dict[str, Any]] = None
    research_result: Dict[str, Any] = Field(default_factory=dict)


class TriageAttendancePartialsRequest(BaseModel):
    workspace_id: str = "default_workspace"
    badge_name: str = "First Aid"
    action: str = "list"
    scout_id: str = ""
    scout_name: str = ""
    troop_unit: str = "Troop 19"
    session_attendance: Optional[Dict[str, str]] = None
    completed_reqs: Optional[List[str]] = None
    completed_reqs_by_badge: Optional[Dict[str, List[str]]] = None
    partial_classifications: Optional[Dict[str, str]] = None
    counselor_notes: str = ""
    schedule_format: str = "4_session_mbc"
    session_labels: Optional[List[str]] = None
    postponed_session_idx: Optional[int] = None
    companion_badge_name: str = ""
    session_requirements_map: Optional[Dict[str, List[str]]] = None


class TriageBucketOverrideRequest(BaseModel):
    workspace_id: str = "default_workspace"
    badge_name: str = "First Aid"
    req_number: str = "1"
    override_bucket: str = "IN_CLASS_DISCUSSION"


@app.post("/api/studiokit/agenda")
@app.post("/api/v1/studiokit/agenda")
async def api_generate_studiokit_agenda(
    req: StudioKitAgendaRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Generates a counselor session pacing agenda for the selected schedule format."""
    from src.tools.counselor_studiokit import generate_counselor_session_agenda

    sched_fmt = req.schedule_type or req.schedule_format
    c_info = dict(req.counselor_info or {})
    if req.counselor_name and "counselor_name" not in c_info:
        c_info["counselor_name"] = req.counselor_name
    if req.troop_affiliation and "troop_affiliation" not in c_info:
        c_info["troop_affiliation"] = req.troop_affiliation
    if req.location_or_zip and "location_or_zip" not in c_info:
        c_info["location_or_zip"] = req.location_or_zip

    res = generate_counselor_session_agenda(
        badge_name=req.badge_name,
        research_result=req.research_result,
        schedule_format=sched_fmt,
        counselor_info=c_info or None,
        postponed_session_idx=req.postponed_session_idx,
        companion_badge_name=req.companion_badge_name,
    )
    md_text = res.get("agenda_markdown") or res.get("markdown_content") or ""
    res["markdown_content"] = md_text
    res["schedule_type"] = sched_fmt
    res["agenda"] = {
        "schedule_format": res.get("schedule_format", sched_fmt),
        "schedule_type": sched_fmt,
        "sessions": res.get("sessions", []),
        "agenda_markdown": md_text,
        "markdown_content": md_text,
        "postponed_session_idx": res.get("postponed_session_idx"),
        "companion_badge": res.get("companion_badge"),
    }
    return res


@app.post("/api/studiokit/fillable-workbook")
@app.post("/api/v1/studiokit/fillable-workbook")
async def api_generate_fillable_workbook(
    req: StudioKitFillableWorkbookRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Generates the verb-aligned fillable Scout Workbook HTML & Markdown with GTA Section 7.0.3.2 banner."""
    from src.tools.scouting_scraper import generate_fillable_scout_workbook_html

    return generate_fillable_scout_workbook_html(
        badge_name=req.badge_name,
        counselor_info=req.counselor_info,
        option_track=req.selected_option_track or "ALL",
    )


@app.post("/api/studiokit/class-prep-cpp")
@app.post("/api/v1/studiokit/class-prep-cpp")
async def api_generate_class_prep_cpp(
    req: StudioKitClassPrepCppRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Generates the 1-Page Class Preparation Page (CPP) in print-ready HTML and Markdown."""
    from src.tools.counselor_studiokit import generate_class_preparation_page_cpp

    logistics = req.class_logistics or {}
    return generate_class_preparation_page_cpp(
        badge_name=req.badge_name,
        counselor_info=req.counselor_info,
        session_dates=logistics.get("session_dates"),
        room_location=str(logistics.get("room_location") or ""),
    )


@app.post("/api/studiokit/organizer-spec-sheet")
@app.post("/api/v1/studiokit/organizer-spec-sheet")
async def api_generate_organizer_spec_sheet(
    req: StudioKitOrganizerSpecRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Generates the 1-Page Organizer & Syllabus Catalog Spec Sheet for MBC Deans or Camp Directors."""
    from src.tools.counselor_studiokit import generate_organizer_syllabus_spec_sheet

    logistics = req.class_logistics or {}
    return generate_organizer_syllabus_spec_sheet(
        badge_name=req.badge_name,
        counselor_info=req.counselor_info,
        session_mode=req.schedule_format or "4_session_mbc",
        max_scouts=int(logistics.get("max_scouts", 16)),
        min_age_or_rank=str(logistics.get("min_age_or_rank") or "All Scouts (Ages 11-17)"),
        room_needs=str(logistics.get("room_needs") or "Projector/TV + Tables for Buddy Stations"),
    )


@app.post("/api/studiokit/ypt-three-stage-pack")
@app.post("/api/v1/studiokit/ypt-three-stage-pack")
async def api_generate_ypt_three_stage_pack(
    req: StudioKitYptThreeStageRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Generates the 3-Stage YPT Two-Deep Communication Pack (T-14 Welcome, Mid-Clinic Partial Alert, Final Packet)."""
    from src.tools.counselor_studiokit import generate_three_stage_ypt_communication_pack

    logistics = req.class_logistics or {}
    return generate_three_stage_ypt_communication_pack(
        badge_name=req.badge_name,
        counselor_info=req.counselor_info,
        session_dates=logistics.get("session_dates"),
        room_location=str(logistics.get("room_location") or ""),
        absent_scouts_summary=req.scout_roster,
    )


@app.post("/api/slide/logistics-slides")
@app.post("/api/v1/slide/logistics-slides")
async def api_inject_class_logistics_slides(
    req: SlideLogisticsInjectRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Opt-in injection/removal of Slide 2 (Class Overview & Session Roadmap) and Slide N (Homework, Make-Up & Blue Card Check-Out)."""
    from src.tools.pptx_builder import SlideSpec, inject_class_opening_and_closing_slides
    from src.tools.scouting_scraper import fetch_official_merit_badge_requirements

    res_data = req.research_result or fetch_official_merit_badge_requirements(req.badge_name)
    specs = [
        SlideSpec(**{k: v for k, v in s.items() if k in SlideSpec.model_fields})
        for s in (req.slides or [])
    ]
    out_slides = inject_class_opening_and_closing_slides(
        badge_name=req.badge_name,
        slides=specs,
        logistics_config=req.logistics_config,
        requirements=res_data.get("requirements", []),
    )
    return {
        "status": "SUCCESS",
        "badge_name": req.badge_name,
        "total_slide_count": len(out_slides),
        "slides": out_slides,
        "storyboard_slides": out_slides,
    }


@app.post("/api/triage/attendance-and-partials")
@app.post("/api/v1/triage/attendance-and-partials")
async def api_manage_triage_attendance_and_partials(
    req: TriageAttendancePartialsRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Manages multi-session clinic schedules, Scout attendance (S1..S4, M), and smart partial classifications."""
    from src.memory.session_store import (
        get_clinic_session_schedule,
        list_scout_session_attendance_and_partials,
        save_clinic_session_schedule,
        upsert_scout_session_attendance_and_partials,
    )

    act = str(req.action or "list").strip().lower()
    if act == "save_schedule":
        sched = save_clinic_session_schedule(
            workspace_id=req.workspace_id,
            badge_name=req.badge_name,
            schedule_format=req.schedule_format,
            session_labels=req.session_labels,
            postponed_session_idx=req.postponed_session_idx,
            companion_badge_name=req.companion_badge_name,
            session_requirements_map=req.session_requirements_map,
        )
        return {"status": "SUCCESS", "schedule": sched}

    if act in ("upsert_scout", "update_attendance", "save_scout") and (req.scout_id or req.scout_name):
        sid = req.scout_id or re.sub(r"[^a-z0-9]+", "_", req.scout_name.strip().lower()).strip("_") or "scout_1"
        saved = upsert_scout_session_attendance_and_partials(
            workspace_id=req.workspace_id,
            scout_id=sid,
            badge_name=req.badge_name,
            scout_name=req.scout_name or sid,
            troop_unit=req.troop_unit,
            session_attendance=req.session_attendance,
            completed_reqs=req.completed_reqs,
            completed_reqs_by_badge=req.completed_reqs_by_badge,
            partial_classifications=req.partial_classifications,
            counselor_notes=req.counselor_notes,
        )
        return {
            "status": "SUCCESS",
            "scout": saved,
            "scouts": list_scout_session_attendance_and_partials(req.workspace_id, req.badge_name),
        }

    return {
        "status": "SUCCESS",
        "workspace_id": req.workspace_id,
        "badge_name": req.badge_name,
        "schedule": get_clinic_session_schedule(req.workspace_id, req.badge_name),
        "scouts": list_scout_session_attendance_and_partials(req.workspace_id, req.badge_name),
    }


@app.post("/api/triage/bucket-override")
@app.post("/api/v1/triage/bucket-override")
async def api_save_triage_bucket_override(
    req: TriageBucketOverrideRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Saves or lists counselor 5-Tier Syllabus Bucket overrides in SQLite WAL."""
    from src.memory.session_store import (
        get_counselor_syllabus_bucket_overrides,
        save_counselor_syllabus_bucket_override,
    )

    if req.req_number and req.override_bucket:
        save_counselor_syllabus_bucket_override(
            workspace_id=req.workspace_id,
            badge_name=req.badge_name,
            req_number=req.req_number,
            override_bucket=req.override_bucket,
        )
    overrides = get_counselor_syllabus_bucket_overrides(req.workspace_id, req.badge_name)
    return {
        "status": "SUCCESS",
        "workspace_id": req.workspace_id,
        "badge_name": req.badge_name,
        "overrides": overrides,
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


_TZ_LOCATION_FALLBACK_MAP: Dict[str, str] = {
    "America/New_York": "Middleton, MA 01949",
    "America/Detroit": "Detroit, MI",
    "America/Chicago": "Chicago, IL",
    "America/Denver": "Denver, CO",
    "America/Phoenix": "Phoenix, AZ",
    "America/Los_Angeles": "San Francisco, CA",
    "America/Anchorage": "Anchorage, AK",
    "Pacific/Honolulu": "Honolulu, HI",
}


@app.get("/api/location/resolve")
@app.get("/api/v1/location/resolve")
async def api_resolve_counselor_location(
    request: Request,
    location_or_zip: str = Query("", description="Explicit City, State or 5-digit US ZIP code."),
    troop_affiliation: str = Query("", description="Troop number and local council string."),
    timezone: str = Query("", description="Browser IANA timezone fallback hint."),
) -> Dict[str, Any]:
    """Resolves counselor regional context, state, U.S. Senators, U.S. House Representative, and NOAA WFO."""
    from src.agents.researcher import resolve_counselor_location

    eff_loc = (location_or_zip or "").strip()
    eff_troop = (troop_affiliation or "").strip()
    if not eff_loc and eff_troop in ("", "Troop 123, My Council"):
        geo_city = (request.headers.get("x-appengine-city") or "").strip().title()
        geo_region = (request.headers.get("x-appengine-region") or "").strip().upper()
        if geo_city and geo_region and len(geo_region) == 2:
            eff_loc = f"{geo_city}, {geo_region}"
        elif timezone and timezone in _TZ_LOCATION_FALLBACK_MAP:
            eff_loc = _TZ_LOCATION_FALLBACK_MAP[timezone]
        else:
            eff_loc = "Middleton, MA 01949"
    resolved = await asyncio.to_thread(
        resolve_counselor_location,
        troop_affiliation=eff_troop,
        location_or_zip=eff_loc,
    )
    return {"status": "SUCCESS", "resolved_location": resolved}



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
        include_slide_context=req.include_slide_context,
        bullet_points=req.bullet_points,
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
        include_slide_context=req.include_slide_context,
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
    from src.memory.session_store import _default_store

    checks: Dict[str, Any] = {}
    overall_ready = True

    # 1. SQLite session store check
    try:
        is_ok = await asyncio.to_thread(_default_store.ping_sync)
        checks["session_store"] = "READY" if is_ok else "DEGRADED"
        if not is_ok:
            overall_ready = False
    except Exception as exc:
        checks["session_store"] = f"FAILED: {exc}"
        overall_ready = False


    # 2. 144-badge catalog check
    catalog_len = len(OFFICIAL_BSA_MERIT_BADGES_CATALOG)
    checks["merit_badge_catalog"] = "READY" if catalog_len >= 144 else f"INCOMPLETE ({catalog_len})"
    if catalog_len < 144:
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
                    "counselor_name": "anonymous_counselor",
                }
            )
            golden_dataset_size = int(promotion_result.get("total_golden_extensions", 0))
        except Exception as exc:
            logger.warning("Golden dataset promotion warning: %s", exc)
            promoted_to_golden = False

    sqlite_rec = _default_store.record_hitl_feedback_sync(
        badge_name=req.badge_name,
        session_id=req.session_id,
        counselor_name="anonymous_counselor",
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


@app.get("/api/local-grounding/senators")
@app.post("/api/local-grounding/senators")
@app.get("/api/v1/local-grounding/senators")
@app.post("/api/v1/local-grounding/senators")
async def api_refresh_us_senators(
    state: Optional[str] = Query(None, description="Optional 2-letter state code for on-demand Gemini lookup."),
    city_state: Optional[str] = Query(None, description="Optional City, State or ZIP for congressional district lookup."),
    location: Optional[str] = Query(None, description="Alias for city_state (City, State or ZIP)."),
    force: bool = Query(False, description="Force refresh even if within 24-hour TTL."),
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Refreshes the 100 U.S. Senators daily cache (24h TTL) or resolves a specific state's Senators on demand via Gemini."""
    from src.tools.local_grounding_engine import (
        refresh_all_100_us_senators_daily,
        refresh_us_senators_on_demand,
    )

    eff_loc = city_state or location or ""
    if state:
        entry = await asyncio.to_thread(
            refresh_us_senators_on_demand,
            state_abbr=state,
            city_state=eff_loc,
            force=force,
        )
        return {"status": "SUCCESS", "mode": "ON_DEMAND_STATE", "delegation": entry}
    summary = await asyncio.to_thread(refresh_all_100_us_senators_daily, force=force)
    return {"status": "SUCCESS", "mode": "DAILY_100_SENATORS_SWEEP", **summary}


# ==============================================================================
# 4. SUPER-USER ADMIN CONSOLE ENDPOINTS (`/api/v1/admin/*`)
# ==============================================================================


class AdminUnlockRequest(BaseModel):
    token: str = Field("", description="Super-User Admin token or passphrase (`ADMIN_SUPERUSER_TOKEN`).")


class AdminCatalogImageUpdateRequest(BaseModel):
    badge_name: str = Field(..., description="Official Scouts BSA Merit Badge name.")
    image_id: str = Field(..., description="Target catalog image_id or filename.")
    caption: Optional[str] = Field(None, description="Updated instructional caption.")
    title: Optional[str] = Field(None, description="Updated short display title.")
    req_number: Optional[str] = Field(None, description="Updated requirement tag (e.g. '1', '3a', 'Overview').")
    is_alternate: Optional[bool] = Field(None, description="True if alternate, False if primary default.")
    alternate_rank: Optional[int] = Field(None, description="0 for primary, 1+ for alternate rank.")
    discard: Optional[bool] = Field(None, description="True to hide/discard low-quality figure.")


class AdminPromotePrimaryRequest(BaseModel):
    badge_name: str = Field(..., description="Official Scouts BSA Merit Badge name.")
    image_id: str = Field(..., description="Target catalog image_id to promote to Primary Default.")
    req_number: Optional[str] = Field(None, description="Optional requirement number override.")


class AdminRecaptionVisionRequest(BaseModel):
    badge_name: str = Field(..., description="Official Scouts BSA Merit Badge name.")
    image_id: str = Field(..., description="Target catalog image_id to re-caption with Gemini Vision.")
    req_number: Optional[str] = Field(None, description="Optional requirement number context.")


class AnonymousImageSwapTelemetryRequest(BaseModel):
    badge_name: str = Field("First Aid", description="Merit Badge name (anonymous).")
    req_number: str = Field("1", description="Requirement number.")
    event_type: str = Field("counselor_visual_swap", description="Event type (`counselor_visual_swap`, `nano_regen`, etc.).")
    from_image_id: str = Field("", description="Previous image ID.")
    to_image_id: str = Field("", description="Selected image ID.")


@app.get("/api/admin/session")
@app.get("/api/v1/admin/session")
async def api_admin_session_status(request: Request) -> Dict[str, Any]:
    """Returns whether the current browser session is authorized for the Super-User Admin Console."""
    status = check_admin_session_status(request)
    return {
        "status": "SUCCESS",
        **status,
    }


@app.post("/api/admin/unlock")
@app.post("/api/v1/admin/unlock")
async def api_admin_unlock(req: AdminUnlockRequest, response: Response) -> Dict[str, Any]:
    """Verifies the Super-User Admin passphrase/token and sets a signed HttpOnly session cookie."""
    if not verify_admin_token_value(req.token):
        raise HTTPException(
            status_code=403,
            detail="Invalid Super-User Admin token. Check ADMIN_SUPERUSER_TOKEN.",
        )
    signed_cookie = create_admin_session_cookie(role="superuser", ttl_seconds=86400)
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE_NAME,
        value=signed_cookie,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return {
        "status": "UNLOCKED",
        "is_admin": True,
        "auth_mode": "signed_cookie",
        "role": "superuser",
    }


@app.post("/api/admin/lock")
@app.post("/api/v1/admin/lock")
async def api_admin_lock(response: Response) -> Dict[str, Any]:
    """Locks the Super-User Admin Console for the current browser session."""
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE_NAME,
        value="locked",
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return {
        "status": "LOCKED",
        "is_admin": False,
        "auth_mode": "explicitly_locked",
        "role": "counselor",
    }


@app.get("/api/admin/catalog/images")
@app.get("/api/v1/admin/catalog/images")
async def api_admin_list_catalog_images(
    badge_name: str = Query("First Aid"),
    req_number: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    _admin: Dict[str, Any] = Depends(verify_admin_auth),
) -> Dict[str, Any]:
    """Lists all cached images, captions, and roles for a Merit Badge in the Admin Console."""
    from src.agents.image_studio import admin_list_badge_catalog_images

    return await asyncio.to_thread(
        admin_list_badge_catalog_images,
        badge_name=badge_name,
        req_number=req_number,
        source_type=source_type,
        role=role,
    )


@app.patch("/api/admin/catalog/image")
@app.patch("/api/v1/admin/catalog/image")
async def api_admin_update_catalog_image(
    req: AdminCatalogImageUpdateRequest,
    _admin: Dict[str, Any] = Depends(verify_admin_auth),
) -> Dict[str, Any]:
    """Updates caption, title, requirement tag, or role for a cached catalog image."""
    from src.agents.image_studio import admin_update_catalog_image_metadata

    updates = {
        k: v
        for k, v in req.model_dump().items()
        if k not in ("badge_name", "image_id") and v is not None
    }
    res = await asyncio.to_thread(
        admin_update_catalog_image_metadata,
        badge_name=req.badge_name,
        image_id=req.image_id,
        updates=updates,
    )
    if res.get("status") != "SUCCESS":
        return JSONResponse(status_code=400, content=res)
    return res


@app.post("/api/admin/catalog/promote-primary")
@app.post("/api/v1/admin/catalog/promote-primary")
async def api_admin_promote_catalog_primary(
    req: AdminPromotePrimaryRequest,
    _admin: Dict[str, Any] = Depends(verify_admin_auth),
) -> Dict[str, Any]:
    """Promotes an Alternate visual to Primary Default for its requirement and demotes the prior Primary."""
    from src.agents.image_studio import admin_promote_alternate_to_primary

    res = await asyncio.to_thread(
        admin_promote_alternate_to_primary,
        badge_name=req.badge_name,
        image_id=req.image_id,
        req_number=req.req_number,
    )
    if res.get("status") != "SUCCESS":
        return JSONResponse(status_code=400, content=res)
    return res


@app.post("/api/admin/catalog/recaption-vision")
@app.post("/api/v1/admin/catalog/recaption-vision")
async def api_admin_recaption_catalog_vision(
    req: AdminRecaptionVisionRequest,
    _admin: Dict[str, Any] = Depends(verify_admin_auth),
) -> Dict[str, Any]:
    """Re-captions a cached catalog image using Gemini 2.5 Flash Vision."""
    from src.agents.image_studio import admin_recaption_image_with_vision

    res = await asyncio.to_thread(
        admin_recaption_image_with_vision,
        badge_name=req.badge_name,
        image_id=req.image_id,
        req_number=req.req_number,
    )
    if res.get("status") != "SUCCESS":
        return JSONResponse(status_code=400, content=res)
    return res


class AdminReplaceCatalogImageRequest(BaseModel):
    badge_name: str = Field(..., description="Official Scouts BSA Merit Badge name.")
    image_id: str = Field(..., description="Target catalog image_id or filename to replace in-place.")
    image_data_uri: Optional[str] = Field(None, description="Base64 PNG/JPG data URI from local file upload.")
    regenerate_nano: bool = Field(False, description="True to regenerate in-place with Nano Banana AI.")
    custom_prompt: str = Field("", description="Optional custom prompt for Nano Banana regeneration.")


@app.post("/api/admin/catalog/replace-image")
@app.post("/api/v1/admin/catalog/replace-image")
async def api_admin_replace_catalog_image(
    req: AdminReplaceCatalogImageRequest,
    _admin: Dict[str, Any] = Depends(verify_admin_auth),
) -> Dict[str, Any]:
    """Replaces a built-in catalog image in-place (with .bak.<ts> backup and 8-bit PNG quantization) or regenerates with Nano Banana."""
    import base64
    from src.agents.image_studio import admin_replace_catalog_image_asset

    raw_bytes: Optional[bytes] = None
    if req.image_data_uri:
        uri_str = str(req.image_data_uri).strip()
        if "," in uri_str:
            uri_str = uri_str.split(",", 1)[1]
        try:
            raw_bytes = base64.b64decode(uri_str)
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "ERROR",
                    "error_code": "INVALID_BASE64_IMAGE",
                    "message": f"Could not decode base64 image data: {exc}",
                },
            )
    res = await asyncio.to_thread(
        admin_replace_catalog_image_asset,
        badge_name=req.badge_name,
        image_id=req.image_id,
        image_bytes=raw_bytes,
        regenerate_nano=req.regenerate_nano,
        custom_prompt=req.custom_prompt,
    )
    if res.get("status") != "SUCCESS":
        return JSONResponse(status_code=400, content=res)
    return res


@app.post("/api/admin/telemetry/image-swap")
@app.post("/api/v1/admin/telemetry/image-swap")
async def api_record_anonymous_image_swap(
    req: AnonymousImageSwapTelemetryRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Records an anonymous slide visual swap event with zero Counselor PII."""
    get_zero_pii_telemetry_store().record_image_swap(
        badge_name=req.badge_name,
        req_number=req.req_number,
        event_type=req.event_type,
        from_image_id=req.from_image_id,
        to_image_id=req.to_image_id,
    )
    return {"status": "RECORDED", "zero_pii": True}


@app.get("/api/admin/telemetry/summary")
@app.get("/api/v1/admin/telemetry/summary")
async def api_admin_telemetry_summary(
    _admin: Dict[str, Any] = Depends(verify_admin_auth),
) -> Dict[str, Any]:
    """Returns Zero-PII operational telemetry, bimodal latencies, badge popularity, and circuit breakers."""
    from src.observability.online_audit_sampler import get_online_production_audit_sampler

    sqlite_summary = await asyncio.to_thread(get_zero_pii_telemetry_store().get_telemetry_summary)
    runtime_snap = METRICS_COLLECTOR.snapshot()
    online_audit = await asyncio.to_thread(get_online_production_audit_sampler().get_online_audit_summary, 25)
    return {
        "status": "SUCCESS",
        "zero_pii_telemetry": sqlite_summary,
        "runtime_metrics": runtime_snap,
        "online_production_audit": online_audit,
        "compliance_audit_events": get_compliance_audit_events(limit=25),
    }


@app.get("/api/admin/telemetry/online-audit")
@app.get("/api/v1/admin/telemetry/online-audit")
async def api_admin_online_audit_telemetry(
    limit: int = Query(25, ge=1, le=100),
    _admin: Dict[str, Any] = Depends(verify_admin_auth),
) -> Dict[str, Any]:
    """Returns continuous 5% online production trace audit sampler metrics and recent zero-PII samples."""
    from src.observability.online_audit_sampler import get_online_production_audit_sampler

    return await asyncio.to_thread(get_online_production_audit_sampler().get_online_audit_summary, limit)


def _build_admin_prompt_manifest_rows() -> List[Dict[str, Any]]:
    """Reads prompts/manifest.json and computes live SHA-256 hashes for each agent prompt template."""
    import hashlib
    prompts_dir = PROJECT_ROOT / "prompts"
    manifest_path = prompts_dir / "manifest.json"
    if not manifest_path.exists():
        return []
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        prompts_map = raw.get("prompts") or {}
        rows: List[Dict[str, Any]] = []
        for fname, meta in prompts_map.items():
            fpath = prompts_dir / fname
            exists = fpath.exists()
            sha = hashlib.sha256(fpath.read_bytes()).hexdigest() if exists else ""
            rows.append(
                {
                    "agent_id": str(meta.get("agent_role") or fname.replace(".md", "")),
                    "filename": fname,
                    "version": str(meta.get("version") or "3.1.0"),
                    "sha256": sha,
                    "verified": bool(exists and len(sha) == 64),
                }
            )
        return rows
    except Exception:
        return []


@app.get("/api/admin/diagnostics/assets")
@app.get("/api/v1/admin/diagnostics/assets")
async def api_admin_diagnostics_assets(
    _admin: Dict[str, Any] = Depends(verify_admin_auth),
) -> Dict[str, Any]:
    """Returns the 144-Badge Asset Health Matrix, Prompt SHA-256 Manifest, and Zero-PII Guardrail Audit Log."""
    from src.agents.image_studio import admin_get_144_badge_asset_diagnostics

    diag = await asyncio.to_thread(admin_get_144_badge_asset_diagnostics)
    diag["prompt_manifest"] = _build_admin_prompt_manifest_rows()
    diag["compliance_audit_events"] = get_compliance_audit_events(limit=50)
    return diag


@app.post("/api/admin/maintenance/purge-temp-cache")
@app.post("/api/v1/admin/maintenance/purge-temp-cache")
async def api_admin_purge_temp_cache(
    _admin: Dict[str, Any] = Depends(verify_admin_auth),
) -> Dict[str, Any]:
    """Purges temporary web-search and scratch caches while preserving built-in 144-badge assets."""
    purged_files = 0
    web_cache_dir = ASSETS_DIR / "badge_image_catalog" / "_web_search_cache"
    if web_cache_dir.exists():
        for p in web_cache_dir.glob("*.*"):
            try:
                p.unlink()
                purged_files += 1
            except Exception:
                pass
    return {
        "status": "SUCCESS",
        "purged_files": purged_files,
        "message": f"Purged {purged_files} temporary web-search cache files. All built-in 144-badge assets preserved.",
    }


@app.post("/api/admin/maintenance/repair-covers")
@app.post("/api/v1/admin/maintenance/repair-covers")
async def api_admin_repair_covers_and_emblems(
    _admin: Dict[str, Any] = Depends(verify_admin_auth),
) -> Dict[str, Any]:
    """Verifies and repairs all 144 Merit Badge pamphlet covers and badge emblems on disk."""
    from src.agents.image_studio import (
        _badge_slug,
        admin_get_144_badge_asset_diagnostics,
    )
    from src.config import (
        OFFICIAL_BSA_MERIT_BADGES_CATALOG,
        get_badge_cover_and_patch_paths,
    )

    repaired_covers = 0
    repaired_emblems = 0
    covers_dir = ASSETS_DIR / "pamphlet_covers"
    emblems_dir = ASSETS_DIR / "badge_emblems"
    covers_dir.mkdir(parents=True, exist_ok=True)
    emblems_dir.mkdir(parents=True, exist_ok=True)

    for item in OFFICIAL_BSA_MERIT_BADGES_CATALOG:
        b_name = str(item.get("badge_name") or item.get("name") or "First Aid")
        slug = _badge_slug(b_name)
        cov_p = covers_dir / f"{slug}_cover.png"
        emb_p = emblems_dir / f"{slug}.png"
        had_cov = cov_p.exists() or (covers_dir / f"{slug}.png").exists()
        had_emb = emb_p.exists() or (emblems_dir / f"{slug}_patch.png").exists()
        if not had_cov or not had_emb:
            await asyncio.to_thread(get_badge_cover_and_patch_paths, b_name)
            if not had_cov:
                repaired_covers += 1
            if not had_emb:
                repaired_emblems += 1

    diag = await asyncio.to_thread(admin_get_144_badge_asset_diagnostics)
    return {
        "status": "SUCCESS",
        "repaired_covers": repaired_covers,
        "repaired_emblems": repaired_emblems,
        "covers_present": diag.get("covers_present", 144),
        "emblems_present": diag.get("emblems_present", 144),
        "covers_verified": diag.get("covers_present", 144),
        "emblems_verified": diag.get("emblems_present", 144),
    }


@app.get("/api/admin/maintenance/snapshot")
@app.get("/api/v1/admin/maintenance/snapshot")
async def api_admin_download_snapshot(
    _admin: Dict[str, Any] = Depends(verify_admin_auth),
) -> Dict[str, Any]:
    """Returns a downloadable Zero-PII JSON snapshot of catalog diagnostics, prompt manifest, and telemetry."""
    from datetime import datetime, timezone
    from src.agents.image_studio import admin_get_144_badge_asset_diagnostics

    sqlite_summary = await asyncio.to_thread(get_zero_pii_telemetry_store().get_telemetry_summary)
    diag = await asyncio.to_thread(admin_get_144_badge_asset_diagnostics)
    return {
        "status": "SUCCESS",
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "zero_pii_guaranteed": True,
        "telemetry_summary": sqlite_summary,
        "asset_diagnostics_summary": {
            "total_badges": diag.get("total_badges", 144),
            "covers_present": diag.get("covers_present", 144),
            "emblems_present": diag.get("emblems_present", 144),
            "pdfs_indexed_present": diag.get("pdfs_indexed_present", 144),
            "total_pamphlet_figures": diag.get("total_pamphlet_figures", 0),
            "total_nano_banana_heroes": diag.get("total_nano_banana_heroes", 0),
        },
        "prompt_manifest": _build_admin_prompt_manifest_rows(),
        "compliance_audit_events": get_compliance_audit_events(limit=50),
    }


@app.post("/api/admin/circuit-breakers/reset")
@app.post("/api/v1/admin/circuit-breakers/reset")
async def api_admin_reset_circuit_breakers(
    _admin: Dict[str, Any] = Depends(verify_admin_auth),
) -> Dict[str, Any]:
    """Resets all downstream circuit breakers back to CLOSED."""
    states = reset_all_circuit_breakers()
    return {
        "status": "RESET",
        "circuit_breakers": states,
    }


# ==============================================================================
# PLAN 16A: POWERPOINT TEMPLATE ENGINE ENDPOINTS
# ==============================================================================


class TemplateImportUrlRequest(BaseModel):
    url: str = Field(..., description="HTTP/HTTPS URL to a .pptx, .ppt, or background image template.")
    custom_name: Optional[str] = Field(None, description="Optional display title for the imported template.")
    name: Optional[str] = Field(None, description="Optional alias for custom_name.")
    bottom_safe_in: float = Field(6.55, description="Safe bottom coordinate in inches (5.80..6.95).")


class TemplateApplyRequest(BaseModel):
    badge_name: str = Field("First Aid", description="Official Merit Badge name.")
    template_id: str = Field("default_workbench", description="Selected PowerPoint template ID.")
    storyboard_slides: List[Dict[str, Any]] = Field(default_factory=list, description="Current storyboard slides.")
    counselor_info: Optional[Dict[str, Any]] = Field(None, description="Optional Counselor Title Slide metadata.")
    visual_theme: Optional[str] = Field(None, description="Optional WARM_CREAM (CREAM), CRISP_WHITE (WHITE), DARK_SLATE (SLATE), or legacy BEAUTIFIED/STANDARD/STUDIO.")
    accent_palette_key: Optional[str] = Field(None, description="Optional palette key or MATCH_TEMPLATE.")
    deck_style: Optional[Dict[str, Any]] = Field(None, description="Optional deck-wide DeckStyleConfig dictionary.")
    layout_style_preset: Optional[str] = Field(None, description="Optional shorthand layout style preset ('AUTO_TEMPLATE', 'CLEAN_OPEN', 'LEFT_ACCENT_LINE', 'BOXED_CARDS').")


class DeckStylePreferencesRequest(BaseModel):
    default_template_id: Optional[str] = Field(None, description="Default template profile ID.")
    default_slide_theme: Optional[str] = Field(None, description="Default slide theme ('WARM_CREAM', 'CRISP_WHITE', 'DARK_SLATE').")
    default_layout_style_preset: Optional[str] = Field(None, description="Default layout style preset ('AUTO_TEMPLATE', 'CLEAN_OPEN', 'LEFT_ACCENT_LINE', 'BOXED_CARDS').")
    layout_style_preset: Optional[str] = Field(None, description="Alias for default_layout_style_preset.")
    text_container_style: Optional[str] = Field(None, description="Optional granular text container style ('CLEAN_OPEN', 'LEFT_ACCENT_LINE', 'BOXED_CARDS').")
    image_frame_style: Optional[str] = Field(None, description="Optional granular image frame style ('FRAMELESS_CLEAN', 'SOFT_SHADOW', 'FRAMED_CARD').")
    header_chrome_style: Optional[str] = Field(None, description="Optional granular header chrome style ('MINIMAL_ACCENT', 'SOLID_PILL').")
    typography_scale: Optional[str] = Field(None, description="Typography scale ('COMFORTABLE', 'COMPACT', 'LARGE').")
    safety_banner_mode: Optional[str] = Field(None, description="Safety banner mode ('HAZARD_ONLY', 'ALL_SLIDES', 'HIDDEN').")
    match_template_palette: Optional[bool] = Field(None, description="Whether to harmonize card accents with the template's brand palette.")


class TemplateMetadataUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, description="Updated custom template display title.")
    description: Optional[str] = Field(None, description="Updated custom template description.")
    bottom_safe_in: Optional[float] = Field(None, description="Optional updated safe bottom coordinate in inches (5.80..6.95).")


@app.get("/api/preferences/deck-style")
@app.get("/api/v1/preferences/deck-style")
async def api_get_deck_style_preferences() -> Dict[str, Any]:
    """Returns persistent counselor default deck style preferences alongside factory defaults."""
    from src.memory.session_store import (
        FACTORY_DEFAULT_DECK_STYLE_PREFS,
        load_default_deck_style_preferences,
    )

    prefs = await asyncio.to_thread(load_default_deck_style_preferences)
    return {
        "status": "SUCCESS",
        "preferences": prefs,
        "factory_defaults": dict(FACTORY_DEFAULT_DECK_STYLE_PREFS),
    }


@app.put("/api/preferences/deck-style")
@app.put("/api/v1/preferences/deck-style")
@app.post("/api/preferences/deck-style")
@app.post("/api/v1/preferences/deck-style")
async def api_save_deck_style_preferences(
    req: DeckStylePreferencesRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Saves counselor default deck style preferences to SQLite (`user_preferences`)."""
    from src.memory.session_store import save_default_deck_style_preferences

    payload = {k: v for k, v in req.model_dump().items() if v is not None}
    saved = await asyncio.to_thread(save_default_deck_style_preferences, payload)
    return {
        "status": "SUCCESS",
        "preferences": saved,
    }


@app.delete("/api/preferences/deck-style")
@app.delete("/api/v1/preferences/deck-style")
@app.post("/api/preferences/deck-style/reset")
@app.post("/api/v1/preferences/deck-style/reset")
async def api_reset_deck_style_preferences(
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Resets counselor default deck style preferences back to factory defaults."""
    from src.memory.session_store import reset_default_deck_style_preferences

    reset_prefs = await asyncio.to_thread(reset_default_deck_style_preferences)
    return {
        "status": "RESET",
        "preferences": reset_prefs,
    }


@app.get("/api/templates")
@app.get("/api/v1/templates")
async def api_list_powerpoint_templates() -> Dict[str, Any]:
    """Returns all built-in curated Scouting templates and any custom user-uploaded/URL templates."""
    from src.memory.session_store import load_default_deck_style_preferences
    from src.tools.template_engine import load_template_catalog

    profiles = await asyncio.to_thread(load_template_catalog)
    default_prefs = await asyncio.to_thread(load_default_deck_style_preferences)
    return {
        "status": "SUCCESS",
        "total": len(profiles),
        "templates": [p.model_dump() for p in profiles],
        "default_preferences": default_prefs,
    }


@app.post("/api/templates/upload")
@app.post("/api/v1/templates/upload")
async def api_upload_powerpoint_template(
    request: Request,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Uploads a custom `.pptx`, legacy `.ppt`, or `.png`/`.jpg`/`.webp` template (via JSON base64 or multipart form) and extracts SafeCanvasBounds."""
    import base64
    from src.tools.template_engine import ingest_custom_template_bytes, load_template_catalog

    ctype = (request.headers.get("content-type") or "").lower()
    raw_bytes = b""
    filename = "custom_template.pptx"
    custom_name: Optional[str] = None
    bottom_safe_in: float = 6.55

    if "application/json" in ctype:
        body = await request.json()
        filename = str(body.get("filename") or "custom_template.pptx")
        custom_name = body.get("custom_name") or body.get("name")
        bottom_safe_in = float(body.get("bottom_safe_in", 6.55))
        b64_str = str(body.get("data_base64") or "").strip()
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        raw_bytes = base64.b64decode(b64_str) if b64_str else b""
    else:
        form = await request.form()
        up_file = form.get("file")
        if up_file is not None and hasattr(up_file, "read"):
            raw_bytes = await up_file.read()
            filename = getattr(up_file, "filename", None) or filename
        if form.get("custom_name") or form.get("name"):
            custom_name = str(form.get("custom_name") or form.get("name"))
        if form.get("bottom_safe_in"):
            bottom_safe_in = float(form.get("bottom_safe_in"))

    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded template file is empty.")
    try:
        profile = await asyncio.to_thread(
            ingest_custom_template_bytes,
            raw_bytes=raw_bytes,
            original_filename=filename,
            custom_name=custom_name,
            bottom_safe_in=bottom_safe_in,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    all_profiles = await asyncio.to_thread(load_template_catalog)
    return {
        "status": "SUCCESS",
        "template": profile.model_dump(),
        "templates": [p.model_dump() for p in all_profiles],
    }


@app.post("/api/templates/import-url")
@app.post("/api/v1/templates/import-url")
async def api_import_template_from_url(
    req: TemplateImportUrlRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Imports a PowerPoint template or slide background from an HTTP/HTTPS URL."""
    from src.tools.template_engine import ingest_template_from_url, load_template_catalog

    try:
        profile = await asyncio.to_thread(
            ingest_template_from_url,
            url=req.url,
            custom_name=req.custom_name or req.name,
            bottom_safe_in=req.bottom_safe_in,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    all_profiles = await asyncio.to_thread(load_template_catalog)
    return {
        "status": "SUCCESS",
        "template": profile.model_dump(),
        "templates": [p.model_dump() for p in all_profiles],
    }


@app.post("/api/templates/apply")
@app.post("/api/v1/templates/apply")
async def api_apply_powerpoint_template(
    req: TemplateApplyRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Applies a PowerPoint template to the active deck and rebuilds the downloadable .pptx with SafeCanvasBounds."""
    from src.tools.pptx_builder import (
    CounselorTitleSlideInfo,
        PowerPointBuildRequest,
        SlideSpec,
        generate_bsa_slide_deck_pptx,
    )
    from src.tools.template_engine import (
        get_template_profile,
        normalize_visual_theme,
        resolve_effective_slide_style,
    )

    prof = await asyncio.to_thread(get_template_profile, req.template_id)
    merged_deck_style: Dict[str, Any] = dict(req.deck_style or {})
    if req.layout_style_preset and "layout_style_preset" not in merged_deck_style:
        merged_deck_style["layout_style_preset"] = req.layout_style_preset
    eff_style = resolve_effective_slide_style(prof, deck_style=merged_deck_style if merged_deck_style else None)

    slides_list = [dict(s) for s in (req.storyboard_slides or [])]
    for s in slides_list:
        s["template_id"] = prof.template_id
        if req.visual_theme:
            s["beautification_tier"] = normalize_visual_theme(req.visual_theme)
        if req.accent_palette_key:
            s["accent_palette_key"] = str(req.accent_palette_key).upper()

    visible_specs = [
        SlideSpec(**{k: v for k, v in s.items() if k in SlideSpec.model_fields})
        for s in slides_list
        if not s.get("hidden")
    ]
    rebuilt_pptx_url: Optional[str] = None
    rebuilt_output_path: Optional[str] = None
    if visible_specs:
        c_info = CounselorTitleSlideInfo(**req.counselor_info) if req.counselor_info else None
        out_file = str(
            GENERATED_DECKS_DIR / f"{req.badge_name.strip().replace(' ', '_')}_{prof.template_id}_Merit_Badge_Deck.pptx"
        )
        build_res = await asyncio.to_thread(
            generate_bsa_slide_deck_pptx,
            PowerPointBuildRequest(
                badge_name=req.badge_name,
                slides=visible_specs,
                counselor_info=c_info,
                output_path=out_file,
                template_id=prof.template_id,
                deck_style=eff_style,
            ),
        )
        if build_res.get("output_path"):
            rebuilt_output_path = str(build_res["output_path"])
            rebuilt_pptx_url = _to_web_asset_url(rebuilt_output_path)

    return {
        "status": "SUCCESS",
        "template": prof.model_dump(),
        "deck_style": eff_style,
        "effective_style": eff_style,
        "storyboard_slides": slides_list,
        "output_path": rebuilt_output_path,
        "pptx_download_url": rebuilt_pptx_url,
    }


@app.patch("/api/templates/{template_id}")
@app.patch("/api/v1/templates/{template_id}")
async def api_update_custom_template_metadata(
    template_id: str,
    req: TemplateMetadataUpdateRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Updates `name`, `description`, or `bottom_safe_in` for a custom user-uploaded/URL template."""
    from src.tools.template_engine import load_template_catalog, update_template_metadata

    updated = await asyncio.to_thread(
        update_template_metadata,
        template_id=template_id,
        name=req.name,
        description=req.description,
        bottom_safe_in=req.bottom_safe_in,
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Custom template '{template_id}' not found or is a built-in read-only template.",
        )
    all_profiles = await asyncio.to_thread(load_template_catalog)
    return {
        "status": "UPDATED",
        "template": updated.model_dump(),
        "templates": [p.model_dump() for p in all_profiles],
    }


@app.delete("/api/templates/{template_id}")
@app.delete("/api/v1/templates/{template_id}")
async def api_delete_custom_template(
    template_id: str,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Deletes a custom uploaded/URL template from the catalog."""
    from src.tools.template_engine import delete_custom_template, load_template_catalog

    deleted = await asyncio.to_thread(delete_custom_template, template_id)
    all_profiles = await asyncio.to_thread(load_template_catalog)
    return {
        "status": "DELETED" if deleted else "NOT_FOUND_OR_BUILTIN",
        "deleted": deleted,
        "templates": [p.model_dump() for p in all_profiles],
    }


# ==============================================================================
# PLAN 16B: MULTI-BADGE COUNSELOR WORKSPACES & FAVORITES ENDPOINTS
# ==============================================================================


class WorkspaceSaveRequest(BaseModel):
    workspace_id: Optional[str] = None
    workspace_title: Optional[str] = None
    badge_name: str = "First Aid"
    session_label: str = ""
    camp_bundle_tag: str = ""
    template_id: str = "default_workbench"
    deck_style: Optional[Dict[str, Any]] = None
    counselor_info: Dict[str, Any] = Field(default_factory=dict)
    deck_result: Dict[str, Any] = Field(default_factory=dict)
    deck_payload: Optional[Dict[str, Any]] = None
    blue_card_roster: Dict[str, Any] = Field(default_factory=dict)
    class_prep: Dict[str, Any] = Field(default_factory=dict)
    local_grounding: Dict[str, Any] = Field(default_factory=dict)
    active_slide_idx: int = -1
    slide_count: int = 0
    custom_edits_count: int = 0
    scout_count: int = 0
    is_pinned: bool = True
    is_archived: bool = False
    force_new: bool = False


class WorkspaceCloneRequest(BaseModel):
    new_title: Optional[str] = None
    session_label: Optional[str] = None
    camp_bundle_tag: Optional[str] = None
    copy_roster: bool = False
    clear_blue_card_roster: Optional[bool] = None


class FavoriteToggleRequest(BaseModel):
    badge_name: str
    is_favorite: Optional[bool] = None


@app.get("/api/workspaces")
@app.get("/api/v1/workspaces")
async def api_list_workspaces(
    badge_name: Optional[str] = None,
    camp_bundle_tag: Optional[str] = None,
    include_archived: bool = False,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Lists saved multi-badge counselor deck workspaces."""
    from src.memory.session_store import list_counselor_workspaces

    items = await asyncio.to_thread(
        list_counselor_workspaces,
        badge_name=badge_name,
        camp_bundle_tag=camp_bundle_tag,
        include_archived=include_archived,
    )
    return {"status": "SUCCESS", "total": len(items), "workspaces": items}


@app.post("/api/workspaces")
@app.post("/api/v1/workspaces")
async def api_save_workspace(
    req: WorkspaceSaveRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Creates or updates a multi-badge counselor deck workspace in SQLite (`counselor_workspaces`)."""
    from src.memory.session_store import list_counselor_workspaces, save_counselor_workspace

    saved = await asyncio.to_thread(save_counselor_workspace, req.model_dump())
    all_ws = await asyncio.to_thread(list_counselor_workspaces)
    return {"status": "SUCCESS", "workspace": saved, "workspaces": all_ws}


@app.get("/api/workspaces/{workspace_id}")
@app.get("/api/v1/workspaces/{workspace_id}")
async def api_get_workspace(
    workspace_id: str,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Retrieves a full counselor deck workspace (including storyboard, Blue Card roster, and class prep)."""
    from src.memory.session_store import get_counselor_workspace

    ws = await asyncio.to_thread(get_counselor_workspace, workspace_id, True)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found.")
    return {"status": "SUCCESS", "workspace": ws}


@app.post("/api/workspaces/{workspace_id}/clone")
@app.post("/api/v1/workspaces/{workspace_id}/clone")
async def api_clone_workspace(
    workspace_id: str,
    req: WorkspaceCloneRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Clones an existing deck workspace for a new class section (with optional roster copy)."""
    from src.memory.session_store import clone_counselor_workspace, list_counselor_workspaces

    cloned = await asyncio.to_thread(
        clone_counselor_workspace,
        workspace_id=workspace_id,
        new_title=req.new_title,
        session_label=req.session_label,
        camp_bundle_tag=req.camp_bundle_tag,
        copy_roster=req.copy_roster,
    )
    if not cloned:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found.")
    all_ws = await asyncio.to_thread(list_counselor_workspaces)
    return {"status": "SUCCESS", "workspace": cloned, "workspaces": all_ws}


@app.delete("/api/workspaces/{workspace_id}")
@app.delete("/api/v1/workspaces/{workspace_id}")
async def api_delete_workspace(
    workspace_id: str,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Deletes a saved counselor deck workspace."""
    from src.memory.session_store import delete_counselor_workspace, list_counselor_workspaces

    deleted = await asyncio.to_thread(delete_counselor_workspace, workspace_id)
    all_ws = await asyncio.to_thread(list_counselor_workspaces)
    return {"status": "DELETED" if deleted else "NOT_FOUND", "deleted": deleted, "workspaces": all_ws}


@app.get("/api/counselor/favorites")
@app.get("/api/v1/counselor/favorites")
async def api_get_favorites() -> Dict[str, Any]:
    """Returns the counselor's starred favorite Merit Badges."""
    from src.memory.session_store import get_counselor_favorites

    favs = await asyncio.to_thread(get_counselor_favorites)
    return {"status": "SUCCESS", "favorites": favs}


@app.post("/api/counselor/favorites")
@app.post("/api/v1/counselor/favorites")
async def api_toggle_favorite(
    req: FavoriteToggleRequest,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Toggles a starred favorite Merit Badge in SQLite."""
    from src.memory.session_store import toggle_counselor_favorite

    res = await asyncio.to_thread(toggle_counselor_favorite, req.badge_name, req.is_favorite)
    return {"status": "SUCCESS", **res}


# ==============================================================================
# PLAN 16C: OFFICIAL SCOUTS BSA WORKBENCH MCP SERVER ENDPOINTS (`/mcp`)
# ==============================================================================


@app.get("/mcp/info")
@app.get("/api/v1/mcp/info")
async def api_mcp_server_info() -> Dict[str, Any]:
    """Returns the Model Context Protocol (MCP) server manifest (12 Tools, 6 Resources, 4 Prompts)."""
    from src.mcp_server import get_mcp_server_manifest

    return await asyncio.to_thread(get_mcp_server_manifest)


@app.post("/mcp")
@app.post("/api/v1/mcp")
async def api_mcp_jsonrpc_endpoint(
    request: Request,
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> Dict[str, Any]:
    """Handles Model Context Protocol (MCP) JSON-RPC 2.0 requests (`initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, `prompts/list`, `prompts/get`)."""
    from src.mcp_server import handle_mcp_jsonrpc_request

    try:
        payload = await request.json()
    except Exception:
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error: invalid JSON payload."}}
    return await asyncio.to_thread(handle_mcp_jsonrpc_request, payload)


@app.get("/mcp/sse")
@app.get("/api/v1/mcp/sse")
async def api_mcp_sse_endpoint(
    _auth: Dict[str, Any] = Depends(verify_caller_auth),
) -> StreamingResponse:
    """Provides the Model Context Protocol SSE discovery stream pointing clients to POST `/mcp`."""
    from src.mcp_server import get_mcp_server_manifest

    async def _sse_gen():
        yield "event: endpoint\ndata: /mcp\n\n"
        manifest = await asyncio.to_thread(get_mcp_server_manifest)
        yield f"event: manifest\ndata: {json.dumps(manifest)}\n\n"

    return StreamingResponse(_sse_gen(), media_type="text/event-stream")


@app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
async def serve_favicon() -> Response:
    """Serves the official Scouts BSA favicon for browser tabs."""
    ico_path = UI_DIR / "favicon.ico"
    if ico_path.exists():
        return Response(content=ico_path.read_bytes(), media_type="image/x-icon")
    png_path = UI_DIR / "favicon.png"
    if png_path.exists():
        return Response(content=png_path.read_bytes(), media_type="image/png")
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def serve_a2ui_workbench() -> HTMLResponse:
    """Serves the Google Material 3 Expressive A2UI Counselor Workbench."""
    index_file = UI_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>UI loading...</h1>", status_code=200)
    html_text = index_file.read_text(encoding="utf-8")
    app_js = UI_DIR / "app.js"
    styles_css = UI_DIR / "styles.css"
    if app_js.exists():
        js_ver = f"20261024a-{int(app_js.stat().st_mtime)}"
        html_text = re.sub(r'/ui/app\.js(?:\?v=[^"\'>\s]+)?', f"/ui/app.js?v={js_ver}", html_text)
    if styles_css.exists():
        css_ver = f"20261024a-{int(styles_css.stat().st_mtime)}"
        html_text = re.sub(r'/ui/styles\.css(?:\?v=[^"\'>\s]+)?', f"/ui/styles.css?v={css_ver}", html_text)
    return HTMLResponse(
        html_text,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


def main() -> None:
    """Launch the FastAPI Material 3 Counselor Workbench server."""
    import uvicorn

    port = int(os.getenv("PORT", "8085"))
    uvicorn.run("src.server:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

