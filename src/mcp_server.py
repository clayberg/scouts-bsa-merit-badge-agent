"""Official Scouts BSA Merit Badge Counselor Workbench — Model Context Protocol (MCP) Server.

Implements Plan 16C (Option C Dual-Transport Semantic MCP Server):
1. Local `stdio` transport (`python -m src.mcp_server` or `scouts-bsa-mcp` CLI) via FastMCP
   for Claude Desktop, Gemini CLI / AGY, Cursor, and Windsurf.
2. HTTP JSON-RPC 2.0 & SSE transport (`POST /mcp`, `GET /mcp/info`, `GET /mcp/sse`) mounted
   directly on the FastAPI server (`src/server.py`) for Cloud Run, Google ADK `MCPToolset`,
   and the in-app Interactive MCP Playground.
3. Exposes 27 MCP Capabilities:
   - 7 Grounded `bsa://` MCP Resources
   - 15 Actionable MCP Tools (with Model Armor Youth Protection & FinOps consent gates)
   - 5 Guided Pedagogical MCP Prompts
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import (
    COMPANION_BADGE_PAIRINGS,
    OFFICIAL_BSA_MERIT_BADGES_CATALOG,
    badge_file_slug,
    is_discontinued_badge,
    is_eagle_required,
    is_test_lab_badge,
)
from src.memory.session_store import (
    get_counselor_favorites,
    get_counselor_workspace,
    list_counselor_workspaces,
    load_default_deck_style_preferences,
    retrieve_pamphlet_memory_chunks,
    save_counselor_workspace,
)
from src.tools.template_engine import (
    get_template_profile,
    load_template_catalog,
    normalize_visual_theme,
    resolve_effective_slide_style,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MCP_SERVER_NAME = "scouts-bsa-merit-badge-workbench"
MCP_SERVER_VERSION = "2.16.0"
MCP_PROTOCOL_VERSION = "2024-11-05"


# ==============================================================================
# 1. MCP RESOURCES (7 `bsa://` URI SCHEMES)
# ==============================================================================

MCP_RESOURCES_CATALOG: List[Dict[str, Any]] = [
    {
        "uri": "bsa://catalog/badges",
        "name": "Official 149 Merit Badges Catalog (144 Standard + 5 Test Lab Pilots)",
        "description": "Complete catalog of all 149 Scouts BSA Merit Badges with Eagle-required flags, Test Lab Pilot & Discontinued indicators, categories, emblem URLs, and counselor favorite status.",
        "mimeType": "application/json",
    },
    {
        "uri": "bsa://badges/{badge_name}/requirements",
        "name": "Official Verbatim Merit Badge Requirements",
        "description": "Official verbatim requirements tree, 5-tier syllabus buckets, and sub-requirements for any of the 149 Merit Badges (e.g. bsa://badges/First Aid/requirements).",
        "mimeType": "application/json",
    },
    {
        "uri": "bsa://badges/{badge_name}/images",
        "name": "Curated Vision-Verified Pamphlet & Nano Banana Visuals",
        "description": "Pre-bundled Vision-verified pamphlet figures and Nano Banana illustrations for a Merit Badge (e.g. bsa://badges/First Aid/images).",
        "mimeType": "application/json",
    },
    {
        "uri": "bsa://badges/{badge_name}/class-prep-cpp",
        "name": "1-Page Class Preparation Page (CPP) & 5-Tier Syllabus Bucket Map",
        "description": "Structured 1-Page Class Preparation Page (CPP), prerequisite gates, and 5-tier syllabus bucket classification for a Merit Badge (e.g. bsa://badges/First Aid/class-prep-cpp).",
        "mimeType": "application/json",
    },
    {
        "uri": "bsa://templates/catalog",
        "name": "PowerPoint Slide Templates & SafeCanvasBounds Catalog",
        "description": "Curated and custom PowerPoint templates with brand palettes and SafeCanvasBounds geometry.",
        "mimeType": "application/json",
    },
    {
        "uri": "bsa://workspaces/list",
        "name": "Saved Counselor Deck Workspaces",
        "description": "List of all in-progress Merit Badge slide deck workspaces, session labels, and Scout counts.",
        "mimeType": "application/json",
    },
    {
        "uri": "bsa://workspaces/{workspace_id}",
        "name": "Full Counselor Deck Workspace State",
        "description": "Complete storyboard slides, speaker notes, selected template, and Patrol Blue Card (#34124) roster for a saved workspace.",
        "mimeType": "application/json",
    },
]


def read_mcp_resource(uri: str) -> Dict[str, Any]:
    """Reads any `bsa://` MCP resource URI and returns structured JSON content."""
    clean_uri = str(uri or "").strip()
    favs = {b.lower() for b in get_counselor_favorites()}

    if clean_uri == "bsa://catalog/badges":
        badges = []
        for entry in OFFICIAL_BSA_MERIT_BADGES_CATALOG:
            b = str(entry.get("badge_name") or entry.get("name") or "")
            slug = badge_file_slug(b)
            is_tl = bool(entry.get("is_test_lab_pilot") or is_test_lab_badge(b))
            is_disc = bool(entry.get("is_discontinued") or is_discontinued_badge(b))
            badges.append(
                {
                    "name": b,
                    "slug": slug,
                    "is_eagle_required": bool(entry.get("is_eagle_required")),
                    "is_test_lab_pilot": is_tl,
                    "is_discontinued": is_disc,
                    "status_badge": entry.get("status_badge") or ("DISCONTINUED" if is_disc else ("TEST_LAB_PILOT" if is_tl else "ACTIVE")),
                    "companion_badges": COMPANION_BADGE_PAIRINGS.get(b, []),
                    "category": str(entry.get("category") or "General Scouting"),
                    "is_favorite": b.lower() in favs,
                    "emblem_url": f"/assets/badge_emblems/{slug}.png",
                }
            )
        return {"uri": clean_uri, "mimeType": "application/json", "data": {"total": len(badges), "badges": badges}}

    if clean_uri == "bsa://templates/catalog":
        profiles = [p.model_dump() for p in load_template_catalog()]
        default_prefs = load_default_deck_style_preferences()
        return {
            "uri": clean_uri,
            "mimeType": "application/json",
            "data": {
                "total": len(profiles),
                "templates": profiles,
                "default_deck_style_preferences": default_prefs,
            },
        }

    if clean_uri == "bsa://workspaces/list":
        ws = list_counselor_workspaces()
        return {"uri": clean_uri, "mimeType": "application/json", "data": {"total": len(ws), "workspaces": ws}}

    m_ws = re.match(r"^bsa://workspaces/([^/]+)$", clean_uri)
    if m_ws:
        ws_id = m_ws.group(1)
        ws_obj = get_counselor_workspace(ws_id, include_deck_payload=True)
        if not ws_obj:
            return {"uri": clean_uri, "mimeType": "application/json", "data": {"error": f"Workspace '{ws_id}' not found."}}
        return {"uri": clean_uri, "mimeType": "application/json", "data": ws_obj}

    m_req = re.match(r"^bsa://badges/([^/]+)/requirements$", clean_uri)
    if m_req:
        badge_name = m_req.group(1).replace("_", " ").strip()
        req_cache_path = REPO_ROOT / "data" / "official_requirements_cache.json"
        reqs = []
        if req_cache_path.exists():
            try:
                cache = json.loads(req_cache_path.read_text(encoding="utf-8"))
                for k, v in cache.items():
                    if k.lower() == badge_name.lower():
                        reqs = v if isinstance(v, list) else v.get("requirements", [])
                        badge_name = k
                        break
            except Exception:
                pass
        return {
            "uri": clean_uri,
            "mimeType": "application/json",
            "data": {
                "badge_name": badge_name,
                "is_eagle_required": is_eagle_required(badge_name),
                "requirement_count": len(reqs),
                "requirements": reqs,
            },
        }

    m_img = re.match(r"^bsa://badges/([^/]+)/images$", clean_uri)
    if m_img:
        badge_name = m_img.group(1).replace("_", " ").strip()
        from src.agents.image_studio import get_badge_image_catalog

        cat = get_badge_image_catalog(badge_name)
        return {"uri": clean_uri, "mimeType": "application/json", "data": cat}

    m_cpp = re.match(r"^bsa://badges/([^/]+)/class-prep-cpp$", clean_uri)
    if m_cpp:
        badge_name = m_cpp.group(1).replace("_", " ").strip()
        from src.tools.counselor_studiokit import generate_class_preparation_page_cpp

        cpp = generate_class_preparation_page_cpp(badge_name=badge_name)
        return {"uri": clean_uri, "mimeType": "application/json", "data": cpp}

    return {"uri": clean_uri, "mimeType": "application/json", "data": {"error": f"Unknown MCP resource URI: {clean_uri}"}}


# ==============================================================================
# 2. MCP TOOLS (15 ACTIONABLE AGENT TOOLS)
# ==============================================================================


def mcp_tool_search_merit_badges(
    query: str = "",
    category: str = "ALL",
    eagle_only: bool = False,
    favorites_only: bool = False,
    test_lab_only: bool = False,
) -> Dict[str, Any]:
    """Searches and filters the 149 official Scouts BSA Merit Badges (144 standard + 5 Test Lab Pilots)."""
    q = str(query or "").strip().lower()
    cat_norm = str(category or "ALL").strip().lower()
    favs = {b.lower() for b in get_counselor_favorites()}
    matches = []
    for entry in OFFICIAL_BSA_MERIT_BADGES_CATALOG:
        b = str(entry.get("badge_name") or entry.get("name") or "")
        b_cat = str(entry.get("category") or "General Scouting")
        is_eagle = bool(entry.get("is_eagle_required"))
        is_tl = bool(entry.get("is_test_lab_pilot") or is_test_lab_badge(b))
        is_disc = bool(entry.get("is_discontinued") or is_discontinued_badge(b))
        is_fav = b.lower() in favs
        if eagle_only and not is_eagle:
            continue
        if test_lab_only and not is_tl:
            continue
        if favorites_only and not is_fav:
            continue
        if cat_norm not in ("", "all"):
            if cat_norm in ("test_lab", "test lab", "test lab pilot") and not is_tl:
                continue
            elif cat_norm not in ("test_lab", "test lab", "test lab pilot") and cat_norm not in b_cat.lower():
                continue
        if q and q not in b.lower() and q not in b_cat.lower():
            continue
        slug = badge_file_slug(b)
        matches.append(
            {
                "name": b,
                "slug": slug,
                "category": b_cat,
                "is_eagle_required": is_eagle,
                "is_test_lab_pilot": is_tl,
                "is_discontinued": is_disc,
                "is_favorite": is_fav,
                "emblem_url": f"/assets/badge_emblems/{slug}.png",
            }
        )
    return {"status": "SUCCESS", "count": len(matches), "badges": matches}


def mcp_tool_query_merit_badge_pamphlet(
    badge_name: str,
    question: str,
    top_k: int = 5,
) -> Dict[str, Any]:
    """Queries the official BSA Merit Badge pamphlet using Hybrid Okapi BM25 + 768-dim Cosine RRF search."""
    clean_badge = str(badge_name or "First Aid").strip()
    clean_q = str(question or clean_badge).strip()
    chunks = retrieve_pamphlet_memory_chunks(clean_badge, clean_q, top_k=max(1, min(12, int(top_k or 5))))
    matches = chunks.get("matches", []) if isinstance(chunks, dict) else (chunks if isinstance(chunks, list) else [])
    return {
        "status": "SUCCESS",
        "badge_name": clean_badge,
        "query": clean_q,
        "chunk_count": len(matches),
        "chunks": matches,
        "passages": matches,
    }


def mcp_tool_create_merit_badge_slide_deck(
    badge_name: str,
    instruction_depth: str = "Deep Dive",
    template_id: str = "default_workbench",
    visual_theme: str = "WARM_CREAM",
    counselor_name: str = "Scoutmaster Bob",
    troop_info: str = "Troop 19, Silicon Valley Monterey Bay Council",
    state_code: str = "CA",
    workspace_title: str = "",
    session_label: str = "",
    layout_style_preset: Optional[str] = None,
    deck_style: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Builds a complete Merit Badge teaching slide deck, applies the chosen PowerPoint template, and saves a persistent workspace."""
    from src.agents.coordinator import run_merit_badge_workflow
    from src.schemas import CounselorTitleSlideInfo
    from src.tools.pptx_builder import rebuild_deck_pptx_from_storyboard

    clean_badge = str(badge_name or "First Aid").strip()
    c_info = CounselorTitleSlideInfo(
        counselor_name=counselor_name or "Scoutmaster Bob",
        troop_affiliation=troop_info or "Troop 19",
        location_or_zip=state_code or "CA",
    )
    deck_res = run_merit_badge_workflow(badge_name=clean_badge, counselor_info=c_info)
    slides_raw = ((deck_res.get("storyboard") or {}).get("slides")) or []

    tpl_prof = get_template_profile(template_id)
    tier_norm = normalize_visual_theme(visual_theme)
    merged_ds = dict(deck_style or {})
    if layout_style_preset and "layout_style_preset" not in merged_ds:
        merged_ds["layout_style_preset"] = layout_style_preset
    eff_style = resolve_effective_slide_style(tpl_prof, deck_style=merged_ds if merged_ds else None)

    for s in slides_raw:
        if isinstance(s, dict):
            s["template_id"] = tpl_prof.template_id
            s["beautification_tier"] = tier_norm

    slug = badge_file_slug(clean_badge)
    out_pptx = REPO_ROOT / "deliverables" / f"{slug}_{tpl_prof.template_id}_Deck.pptx"
    out_pptx.parent.mkdir(parents=True, exist_ok=True)
    if merged_ds or not out_pptx.exists() or out_pptx.stat().st_size < 10000:
        rebuild_deck_pptx_from_storyboard(
            badge_name=clean_badge,
            storyboard_slides=slides_raw,
            output_path=str(out_pptx),
            counselor_info=c_info.model_dump() if hasattr(c_info, "model_dump") else getattr(c_info, "__dict__", None),
            template_id=tpl_prof.template_id,
            default_tier=tier_norm,
            deck_style=eff_style,
        )
        pptx_res = {"output_path": str(out_pptx)}
        deck_res["pptx_path"] = pptx_res.get("output_path")
        deck_res["pptx_download_url"] = f"/deliverables/{out_pptx.name}"
        deck_res["template_id"] = tpl_prof.template_id
    deck_res["deck_style"] = eff_style

    ws_meta = save_counselor_workspace(
        {
            "workspace_title": workspace_title or clean_badge,
            "badge_name": clean_badge,
            "session_label": session_label or "",
            "template_id": tpl_prof.template_id,
            "deck_style": eff_style,
            "counselor_info": c_info.model_dump(),
            "deck_result": deck_res,
            "slide_count": len(slides_raw),
        }
    )
    return {
        "status": "SUCCESS",
        "workspace_id": ws_meta["workspace_id"],
        "workspace_title": ws_meta.get("workspace_title"),
        "badge_name": clean_badge,
        "template_id": tpl_prof.template_id,
        "template_name": tpl_prof.name,
        "deck_style": eff_style,
        "slide_count": len(slides_raw),
        "pptx_download_url": deck_res.get("pptx_download_url", ""),
    }


def mcp_tool_get_slide_deck_workspace(
    workspace_id: str,
    include_slides: bool = True,
) -> Dict[str, Any]:
    """Retrieves a saved Merit Badge deck workspace, its slide outline, and its Blue Card roster."""
    ws = get_counselor_workspace(workspace_id, include_deck_payload=include_slides)
    if not ws:
        return {"status": "ERROR", "message": f"Workspace '{workspace_id}' not found."}
    if include_slides:
        slides = ((ws.get("deck_result") or {}).get("storyboard") or {}).get("slides") or []
        ws["slide_outline"] = [
            {
                "slide_index": idx,
                "req_number": s.get("req_number", ""),
                "title": s.get("title", ""),
                "archetype": s.get("archetype", ""),
                "visual_caption": s.get("visual_caption", ""),
            }
            for idx, s in enumerate(slides)
        ]
    return {"status": "SUCCESS", "workspace": ws}


def mcp_tool_update_slide_in_deck(
    workspace_id: str,
    slide_index: int,
    title: Optional[str] = None,
    bullet_points: Optional[List[str]] = None,
    presenter_notes: Optional[str] = None,
    archetype: Optional[str] = None,
    visual_caption: Optional[str] = None,
    container_style_override: Optional[str] = None,
    image_frame_style_override: Optional[str] = None,
    header_chrome_style_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Surgically edits a slide's title, bullet points, speaker notes, archetype, or style overrides inside a saved workspace."""
    ws = get_counselor_workspace(workspace_id, include_deck_payload=True)
    if not ws:
        return {"status": "ERROR", "message": f"Workspace '{workspace_id}' not found."}
    deck = ws.get("deck_result") or {}
    slides = ((deck.get("storyboard") or {}).get("slides")) or []
    idx = int(slide_index)
    if idx < 0 or idx >= len(slides):
        return {"status": "ERROR", "message": f"slide_index {idx} out of range (0..{len(slides) - 1})."}

    target = slides[idx]
    if title is not None:
        target["title"] = str(title).strip()
    if bullet_points is not None:
        target["bullet_points"] = [str(b).strip() for b in bullet_points if str(b).strip()]
    if presenter_notes is not None:
        target["presenter_notes"] = str(presenter_notes).strip()
    if archetype is not None:
        target["archetype"] = str(archetype).strip().upper()
    if visual_caption is not None:
        target["visual_caption"] = str(visual_caption).strip()
    if container_style_override is not None:
        target["container_style_override"] = str(container_style_override).strip().upper()
    if image_frame_style_override is not None:
        target["image_frame_style_override"] = str(image_frame_style_override).strip().upper()
    if header_chrome_style_override is not None:
        target["header_chrome_style_override"] = str(header_chrome_style_override).strip().upper()

    ws["custom_edits_count"] = int(ws.get("custom_edits_count") or 0) + 1
    save_counselor_workspace(ws)
    return {
        "status": "SUCCESS",
        "workspace_id": workspace_id,
        "slide_index": idx,
        "updated_slide": {
            "title": target.get("title"),
            "archetype": target.get("archetype"),
            "bullet_count": len(target.get("bullet_points") or []),
            "visual_caption": target.get("visual_caption"),
            "container_style_override": target.get("container_style_override"),
            "image_frame_style_override": target.get("image_frame_style_override"),
            "header_chrome_style_override": target.get("header_chrome_style_override"),
        },
    }


def mcp_tool_polish_slide_teaching_notes(
    workspace_id: str,
    slide_index: int = 0,
    audience_level: str = "All Scouts (Ages 11–17)",
) -> Dict[str, Any]:
    """Polishes a slide's [SAY], [DEMONSTRATE], and [ASK SCOUTS] counselor script into a warm conversational teaching voice."""
    ws = get_counselor_workspace(workspace_id, include_deck_payload=True)
    if not ws:
        return {"status": "ERROR", "message": f"Workspace '{workspace_id}' not found."}
    deck = ws.get("deck_result") or {}
    slides = ((deck.get("storyboard") or {}).get("slides")) or []
    idx = int(slide_index)
    if idx < 0 or idx >= len(slides):
        return {"status": "ERROR", "message": f"slide_index {idx} out of range (0..{len(slides) - 1})."}

    from src.agents.planner import compile_conversational_speaker_notes

    s = slides[idx]
    polished = compile_conversational_speaker_notes(
        badge_name=ws["badge_name"],
        req_number=str(s.get("req_number") or "1"),
        slide_title=str(s.get("title") or ""),
        bullet_points=list(s.get("bullet_points") or []),
        verbatim_req_text=str(s.get("verbatim_requirement_text") or ""),
        visual_caption=str(s.get("visual_caption") or ""),
        safety_warning=s.get("safety_warning"),
        audience_level=audience_level,
    )
    s["presenter_notes"] = polished
    ws["custom_edits_count"] = int(ws.get("custom_edits_count") or 0) + 1
    save_counselor_workspace(ws)
    return {
        "status": "SUCCESS",
        "workspace_id": workspace_id,
        "slide_index": idx,
        "presenter_notes": polished,
    }


def mcp_tool_generate_or_select_slide_image(
    workspace_id: str,
    slide_index: int,
    action: str = "list_choices",
    choice_index: Optional[int] = None,
    custom_prompt: Optional[str] = None,
    include_slide_context: bool = True,
    user_consented: bool = False,
) -> Dict[str, Any]:
    """Lists curated slide image choices, switches to an alternate choice, or generates a Model Armor-guarded Nano Banana illustration."""
    ws = get_counselor_workspace(workspace_id, include_deck_payload=True)
    if not ws:
        return {"status": "ERROR", "message": f"Workspace '{workspace_id}' not found."}
    deck = ws.get("deck_result") or {}
    slides = ((deck.get("storyboard") or {}).get("slides")) or []
    idx = int(slide_index)
    if idx < 0 or idx >= len(slides):
        return {"status": "ERROR", "message": f"slide_index {idx} out of range (0..{len(slides) - 1})."}

    s = slides[idx]
    choices = list(s.get("available_images") or [])
    act = str(action or "list_choices").strip().lower()

    if act == "list_choices":
        return {
            "status": "SUCCESS",
            "workspace_id": workspace_id,
            "slide_index": idx,
            "current_caption": s.get("visual_caption", ""),
            "choices": choices,
        }

    if act == "select_choice" and choice_index is not None:
        c_idx = int(choice_index)
        if c_idx < 0 or c_idx >= len(choices):
            return {"status": "ERROR", "message": f"choice_index {c_idx} out of range (0..{len(choices) - 1})."}
        chosen = choices[c_idx]
        s["diagram_path"] = chosen.get("image_path") or chosen.get("path") or chosen.get("url")
        s["visual_caption"] = chosen.get("caption") or chosen.get("description") or s.get("visual_caption", "")
        ws["custom_edits_count"] = int(ws.get("custom_edits_count") or 0) + 1
        save_counselor_workspace(ws)
        return {"status": "SUCCESS", "workspace_id": workspace_id, "slide_index": idx, "selected_image": chosen}

    if act == "generate_custom":
        from src.agents.image_studio import generate_nano_banana_slide_image

        res = generate_nano_banana_slide_image(
            badge_name=ws["badge_name"],
            slide_title=str(s.get("title") or ""),
            req_number=str(s.get("req_number") or "1"),
            bullet_points=list(s.get("bullet_points") or []),
            custom_prompt=custom_prompt or "",
            include_slide_context=include_slide_context,
            user_consented=user_consented,
        )
        if res.get("status") == "SUCCESS":
            s["diagram_path"] = res.get("image_path")
            s["visual_caption"] = res.get("caption") or s.get("visual_caption", "")
            ws["custom_edits_count"] = int(ws.get("custom_edits_count") or 0) + 1
            save_counselor_workspace(ws)
        return res

    return {"status": "ERROR", "message": f"Unsupported action '{action}'. Use 'list_choices', 'select_choice', or 'generate_custom'."}


def mcp_tool_apply_powerpoint_template(
    workspace_id: str,
    template_id: str,
    visual_theme: Optional[str] = None,
    accent_palette_key: Optional[str] = None,
    layout_style_preset: Optional[str] = None,
    deck_style: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Applies any built-in or uploaded PowerPoint template to a saved deck workspace and rebuilds its .pptx file."""
    ws = get_counselor_workspace(workspace_id, include_deck_payload=True)
    if not ws:
        return {"status": "ERROR", "message": f"Workspace '{workspace_id}' not found."}
    prof = get_template_profile(template_id)
    deck = ws.get("deck_result") or {}
    slides_raw = ((deck.get("storyboard") or {}).get("slides")) or []

    from src.schemas import CounselorTitleSlideInfo
    from src.tools.pptx_builder import rebuild_deck_pptx_from_storyboard

    c_info = CounselorTitleSlideInfo(**(ws.get("counselor_info") or {})) if ws.get("counselor_info") else None
    slug = badge_file_slug(ws["badge_name"])
    out_pptx = REPO_ROOT / "deliverables" / f"{slug}_{prof.template_id}_{workspace_id[-6:]}.pptx"
    out_pptx.parent.mkdir(parents=True, exist_ok=True)
    if visual_theme:
        for s in slides_raw:
            if isinstance(s, dict):
                s["beautification_tier"] = normalize_visual_theme(visual_theme)
    if accent_palette_key:
        for s in slides_raw:
            if isinstance(s, dict):
                s["accent_palette_key"] = str(accent_palette_key).upper()

    merged_ds = dict(ws.get("deck_style") or {})
    if isinstance(deck_style, dict):
        merged_ds.update(deck_style)
    if layout_style_preset:
        merged_ds["layout_style_preset"] = layout_style_preset
    eff_style = resolve_effective_slide_style(prof, deck_style=merged_ds if merged_ds else None)

    rebuild_deck_pptx_from_storyboard(
        badge_name=ws["badge_name"],
        storyboard_slides=slides_raw,
        output_path=str(out_pptx),
        counselor_info=c_info.model_dump() if hasattr(c_info, "model_dump") else getattr(c_info, "__dict__", None),
        template_id=prof.template_id,
        deck_style=eff_style,
    )
    pptx_res = {"output_path": str(out_pptx)}
    deck["pptx_path"] = pptx_res.get("output_path")
    deck["pptx_download_url"] = f"/deliverables/{out_pptx.name}"
    deck["template_id"] = prof.template_id
    deck["deck_style"] = eff_style
    ws["template_id"] = prof.template_id
    ws["deck_style"] = eff_style
    save_counselor_workspace(ws)
    return {
        "status": "SUCCESS",
        "workspace_id": workspace_id,
        "template_id": prof.template_id,
        "template_name": prof.name,
        "deck_style": eff_style,
        "safe_bounds": prof.safe_bounds.model_dump(),
        "pptx_download_url": deck["pptx_download_url"],
    }


def mcp_tool_export_slide_deck(
    workspace_id: str,
    export_format: str = "pptx",
) -> Dict[str, Any]:
    """Exports a saved deck workspace as a .pptx download URL or returns QR field checklist URLs."""
    ws = get_counselor_workspace(workspace_id, include_deck_payload=True)
    if not ws:
        return {"status": "ERROR", "message": f"Workspace '{workspace_id}' not found."}
    fmt = str(export_format or "pptx").strip().lower()
    if fmt == "pptx":
        return mcp_tool_apply_powerpoint_template(workspace_id, ws.get("template_id") or "default_workbench")
    slug = badge_file_slug(ws["badge_name"])
    return {
        "status": "SUCCESS",
        "workspace_id": workspace_id,
        "export_format": fmt,
        "pptx_download_url": (ws.get("deck_result") or {}).get("pptx_download_url", f"/deliverables/{slug}.pptx"),
        "qr_pamphlet_svg_url": f"/api/v1/qr.svg?url=https://www.scouting.org/merit-badges/{slug.replace('_', '-')}/",
    }


def mcp_tool_generate_class_prep_and_parent_letter(
    workspace_id: str,
    session_mode: str = "TWO_TROOP_MEETINGS",
    camp_or_location: str = "Camp Oljato / Troop Meeting Hall",
) -> Dict[str, Any]:
    """Generates the timed counselor session agenda, Quartermaster gear checklist, and Parent Prerequisite Letter."""
    ws = get_counselor_workspace(workspace_id, include_deck_payload=True)
    if not ws:
        return {"status": "ERROR", "message": f"Workspace '{workspace_id}' not found."}
    from src.tools.counselor_studiokit import (
        CounselorSessionAgendaRequest,
        PrerequisiteParentLetterRequest,
        generate_counselor_session_agenda,
        generate_prerequisite_parent_letter,
    )

    c_info = ws.get("counselor_info") or {}
    agenda = generate_counselor_session_agenda(
        CounselorSessionAgendaRequest(
            badge_name=ws["badge_name"],
            session_mode=session_mode,
        )
    )
    letter = generate_prerequisite_parent_letter(
        PrerequisiteParentLetterRequest(
            badge_name=ws["badge_name"],
            counselor_name=c_info.get("counselor_name", "Scoutmaster Bob"),
            troop_affiliation=c_info.get("troop_affiliation", "Troop 19"),
            session_dates_or_location=camp_or_location,
        )
    )
    ws["class_prep"] = {"agenda": agenda, "parent_letter": letter}
    save_counselor_workspace(ws)
    return {
        "status": "SUCCESS",
        "workspace_id": workspace_id,
        "badge_name": ws["badge_name"],
        "agenda": agenda,
        "parent_letter": letter,
    }


def mcp_tool_manage_patrol_blue_card_roster(
    workspace_id: str,
    action: str = "list",
    scout_name: str = "",
    troop_number: str = "Troop 19",
    patrol_name: str = "Eagle Patrol",
    completed_reqs: Optional[List[str]] = None,
    copy_from_workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Manages Patrol Blue Card (#34124) Scout attendees, requirement sign-offs, cross-badge roster copying, and Scoutbook CSV export."""
    ws = get_counselor_workspace(workspace_id, include_deck_payload=False)
    if not ws:
        return {"status": "ERROR", "message": f"Workspace '{workspace_id}' not found."}
    full_ws = get_counselor_workspace(workspace_id, include_deck_payload=True) or ws
    roster = full_ws.get("blue_card_roster") or {"scouts": []}
    if not isinstance(roster.get("scouts"), list):
        roster["scouts"] = []

    act = str(action or "list").strip().lower()
    if act == "add_or_update_scout" and scout_name.strip():
        clean_name = scout_name.strip()
        existing = next((sc for sc in roster["scouts"] if str(sc.get("name", "")).lower() == clean_name.lower()), None)
        if existing:
            existing["troop"] = troop_number or existing.get("troop", "Troop 19")
            existing["patrol"] = patrol_name or existing.get("patrol", "")
            if completed_reqs is not None:
                existing["completed_reqs"] = list(dict.fromkeys(str(r) for r in completed_reqs))
        else:
            roster["scouts"].append(
                {
                    "name": clean_name,
                    "troop": troop_number or "Troop 19",
                    "patrol": patrol_name or "",
                    "completed_reqs": list(dict.fromkeys(str(r) for r in (completed_reqs or []))),
                }
            )
        full_ws["blue_card_roster"] = roster
        full_ws["scout_count"] = len(roster["scouts"])
        save_counselor_workspace(full_ws)

    elif act == "copy_roster_from_workspace" and copy_from_workspace_id:
        src_ws = get_counselor_workspace(copy_from_workspace_id, include_deck_payload=False)
        if not src_ws:
            return {"status": "ERROR", "message": f"Source workspace '{copy_from_workspace_id}' not found."}
        src_scouts = (src_ws.get("blue_card_roster") or {}).get("scouts") or []
        existing_names = {str(sc.get("name", "")).lower() for sc in roster["scouts"]}
        copied = 0
        for sc in src_scouts:
            nm = str(sc.get("name") or "").strip()
            if nm and nm.lower() not in existing_names:
                roster["scouts"].append(
                    {
                        "name": nm,
                        "troop": sc.get("troop", "Troop 19"),
                        "patrol": sc.get("patrol", ""),
                        "completed_reqs": [],
                    }
                )
                existing_names.add(nm.lower())
                copied += 1
        full_ws["blue_card_roster"] = roster
        full_ws["scout_count"] = len(roster["scouts"])
        save_counselor_workspace(full_ws)
        return {
            "status": "SUCCESS",
            "workspace_id": workspace_id,
            "copied_count": copied,
            "scout_count": len(roster["scouts"]),
            "scouts": roster["scouts"],
        }

    elif act == "export_scoutbook_csv":
        lines = ["Scout Name,Unit,Patrol,Merit Badge,Completed Requirements"]
        for sc in roster["scouts"]:
            reqs_str = ";".join(sc.get("completed_reqs") or [])
            lines.append(f"\"{sc.get('name','')}\",\"{sc.get('troop','')}\",\"{sc.get('patrol','')}\",\"{full_ws['badge_name']}\",\"{reqs_str}\"")
        return {
            "status": "SUCCESS",
            "workspace_id": workspace_id,
            "scout_count": len(roster["scouts"]),
            "csv": "\n".join(lines),
        }

    return {
        "status": "SUCCESS",
        "workspace_id": workspace_id,
        "badge_name": full_ws["badge_name"],
        "scout_count": len(roster["scouts"]),
        "scouts": roster["scouts"],
    }


def mcp_tool_audit_deck_conformance(workspace_id: str) -> Dict[str, Any]:
    """Runs the Stage-1 AABB geometry and copywriting conformance verifier on a saved deck workspace."""
    ws = get_counselor_workspace(workspace_id, include_deck_payload=True)
    if not ws:
        return {"status": "ERROR", "message": f"Workspace '{workspace_id}' not found."}
    deck = ws.get("deck_result") or {}
    pptx_path = deck.get("pptx_path")
    if not pptx_path or not os.path.exists(str(pptx_path)):
        mcp_tool_apply_powerpoint_template(workspace_id, ws.get("template_id") or "default_workbench")
        ws = get_counselor_workspace(workspace_id, include_deck_payload=True) or ws
        pptx_path = (ws.get("deck_result") or {}).get("pptx_path")

    from src.agents.reviewer import audit_deck_visual_quality, check_pptx_conformance

    report = check_pptx_conformance(str(pptx_path or ""))
    vq_audit = audit_deck_visual_quality(
        str(pptx_path or ""),
        template_id=ws.get("template_id", "default_workbench"),
        deck_style=ws.get("deck_style"),
        conformance_dict=report,
    )
    return {
        "status": "SUCCESS",
        "workspace_id": workspace_id,
        "badge_name": ws["badge_name"],
        "template_id": ws.get("template_id", "default_workbench"),
        "deck_style": ws.get("deck_style"),
        "conformance_report": report,
        "visual_quality_audit": vq_audit,
    }


def mcp_tool_generate_fillable_scout_workbook(
    badge_name: str,
    selected_option_track: Optional[str] = None,
    include_qr: bool = True,
) -> Dict[str, Any]:
    """Generates the Fillable Form (GTA §7.0.3.2) Scout Workbook HTML & Markdown with Guide to Advancement Section 7.0.3.2 banner."""
    from src.tools.scouting_scraper import (
        fetch_official_merit_badge_requirements,
        generate_fillable_scout_workbook_html,
    )

    clean_badge = str(badge_name or "First Aid").strip()
    research_res = fetch_official_merit_badge_requirements(clean_badge, option_track=selected_option_track or "ALL")
    html_res = generate_fillable_scout_workbook_html(
        badge_name=clean_badge,
        option_track=selected_option_track or "ALL",
    )
    html_res["workbook_markdown"] = research_res.get("counselor_workbook_markdown", "")
    return html_res


def mcp_tool_generate_class_preparation_page_cpp(
    badge_name: str,
    schedule_format: str = "4_session_mbc",
    counselor_name: str = "Scoutmaster Bob",
    troop_affiliation: str = "Troop 19",
) -> Dict[str, Any]:
    """Generates the 1-Page Class Preparation Page (CPP) & 5-Tier Syllabus Bucket Map for Scouts and Parents."""
    from src.tools.counselor_studiokit import generate_class_preparation_page_cpp

    clean_badge = str(badge_name or "First Aid").strip()
    return generate_class_preparation_page_cpp(
        badge_name=clean_badge,
        counselor_info={"counselor_name": counselor_name, "troop_affiliation": troop_affiliation},
    )


def mcp_tool_manage_multisession_clinic_attendance_and_partials(
    workspace_id: str,
    badge_name: str = "First Aid",
    action: str = "list",
    scout_id: str = "",
    scout_name: str = "",
    troop_unit: str = "Troop 19",
    session_attendance: Optional[Dict[str, str]] = None,
    completed_reqs: Optional[List[str]] = None,
    partial_classifications: Optional[Dict[str, str]] = None,
    schedule_format: str = "4_session_mbc",
    postponed_session_idx: Optional[int] = None,
    companion_badge_name: str = "",
) -> Dict[str, Any]:
    """Manages multi-session clinic schedules (4x75m, 2xDouble-Block, Snow-Day Make-Up), Scout attendance (S1..S4, M), and smart partial classifications."""
    from src.memory.session_store import (
        get_clinic_session_schedule,
        list_scout_session_attendance_and_partials,
        save_clinic_session_schedule,
        upsert_scout_session_attendance_and_partials,
    )

    act = str(action or "list").strip().lower()
    if act == "save_schedule":
        sched = save_clinic_session_schedule(
            workspace_id=workspace_id,
            badge_name=badge_name,
            schedule_format=schedule_format,
            postponed_session_idx=postponed_session_idx,
            companion_badge_name=companion_badge_name,
        )
        return {"status": "SUCCESS", "workspace_id": workspace_id, "schedule": sched}

    if act in ("upsert_scout", "update_attendance", "save_scout") and (scout_id or scout_name):
        sid = scout_id or re.sub(r"[^a-z0-9]+", "_", scout_name.strip().lower()).strip("_") or "scout_1"
        saved = upsert_scout_session_attendance_and_partials(
            workspace_id=workspace_id,
            scout_id=sid,
            badge_name=badge_name,
            scout_name=scout_name or sid,
            troop_unit=troop_unit,
            session_attendance=session_attendance,
            completed_reqs=completed_reqs,
            partial_classifications=partial_classifications,
        )
        return {
            "status": "SUCCESS",
            "workspace_id": workspace_id,
            "scout": saved,
            "scouts": list_scout_session_attendance_and_partials(workspace_id, badge_name),
        }

    return {
        "status": "SUCCESS",
        "workspace_id": workspace_id,
        "badge_name": badge_name,
        "schedule": get_clinic_session_schedule(workspace_id, badge_name),
        "scouts": list_scout_session_attendance_and_partials(workspace_id, badge_name),
    }


MCP_TOOLS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "search_merit_badges": {
        "name": "search_merit_badges",
        "description": "Searches and filters the 149 official Scouts BSA Merit Badges (144 standard + 5 Test Lab Pilots) by keyword, category, Eagle-required status, Test Lab status, or Counselor Starred Favorites.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional search keyword (e.g. 'water', 'first aid', 'auctioneering')."},
                "category": {"type": "string", "description": "Optional category filter, 'Test Lab Pilot', or 'ALL'."},
                "eagle_only": {"type": "boolean", "description": "If true, returns only Eagle-required Merit Badges."},
                "favorites_only": {"type": "boolean", "description": "If true, returns only Counselor starred favorite badges."},
                "test_lab_only": {"type": "boolean", "description": "If true, returns only the 5 Scouting America Test Lab Pilot badges."},
            },
        },
        "handler": mcp_tool_search_merit_badges,
    },
    "query_merit_badge_pamphlet": {
        "name": "query_merit_badge_pamphlet",
        "description": "Queries the official BSA Merit Badge pamphlet using Hybrid Okapi BM25 + 768-dim Cosine RRF search for grounded verbatim excerpts.",
        "inputSchema": {
            "type": "object",
            "required": ["badge_name", "question"],
            "properties": {
                "badge_name": {"type": "string", "description": "Official Merit Badge name (e.g. 'First Aid', 'Camping')."},
                "question": {"type": "string", "description": "Specific requirement or domain question to look up in the pamphlet."},
                "top_k": {"type": "integer", "description": "Number of top RRF chunks to retrieve (1-12).", "default": 5},
            },
        },
        "handler": mcp_tool_query_merit_badge_pamphlet,
    },
    "create_merit_badge_slide_deck": {
        "name": "create_merit_badge_slide_deck",
        "description": "Generates a complete Merit Badge teaching slide deck, applies a PowerPoint template, and saves it as a persistent counselor workspace.",
        "inputSchema": {
            "type": "object",
            "required": ["badge_name"],
            "properties": {
                "badge_name": {"type": "string", "description": "Official Merit Badge name (e.g. 'First Aid', 'Weather')."},
                "instruction_depth": {"type": "string", "description": "'Deep Dive' or 'Standard Overview'.", "default": "Deep Dive"},
                "template_id": {"type": "string", "description": "PowerPoint template ID (e.g. 'scouting_america_250', 'scouting_america_forest_sunrise', 'default_workbench').", "default": "default_workbench"},
                "visual_theme": {
                    "type": "string",
                    "description": "'WARM_CREAM' ('CREAM'), 'CRISP_WHITE' ('WHITE'), or 'DARK_SLATE' ('SLATE').",
                    "enum": ["WARM_CREAM", "CRISP_WHITE", "DARK_SLATE", "CREAM", "WHITE", "SLATE", "BEAUTIFIED", "STANDARD", "STUDIO"],
                    "default": "WARM_CREAM",
                },
                "counselor_name": {"type": "string", "description": "Counselor display name for Cover Slide."},
                "troop_info": {"type": "string", "description": "Troop and Council affiliation."},
                "state_code": {"type": "string", "description": "2-letter US State code for local grounding."},
                "workspace_title": {"type": "string", "description": "Optional custom title for the saved deck workspace."},
                "session_label": {"type": "string", "description": "Optional class section label (e.g. 'Morning Patrol')."},
                "layout_style_preset": {
                    "type": "string",
                    "description": "Optional layout style preset ('AUTO_TEMPLATE', 'CLEAN_OPEN', 'LEFT_ACCENT_LINE', 'BOXED_CARDS').",
                    "enum": ["AUTO_TEMPLATE", "CLEAN_OPEN", "LEFT_ACCENT_LINE", "BOXED_CARDS"],
                },
                "deck_style": {
                    "type": "object",
                    "description": "Optional DeckStyleConfig dictionary.",
                },
            },
        },
        "handler": mcp_tool_create_merit_badge_slide_deck,
    },
    "get_slide_deck_workspace": {
        "name": "get_slide_deck_workspace",
        "description": "Loads a saved Merit Badge deck workspace, slide outline, template profile, and Patrol Blue Card (#34124) roster.",
        "inputSchema": {
            "type": "object",
            "required": ["workspace_id"],
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace ID returned by create_merit_badge_slide_deck or bsa://workspaces/list."},
                "include_slides": {"type": "boolean", "description": "Whether to include the full slide outline.", "default": True},
            },
        },
        "handler": mcp_tool_get_slide_deck_workspace,
    },
    "update_slide_in_deck": {
        "name": "update_slide_in_deck",
        "description": "Surgically updates a slide's title, bullet points, presenter notes, visual caption, or layout archetype in a saved workspace.",
        "inputSchema": {
            "type": "object",
            "required": ["workspace_id", "slide_index"],
            "properties": {
                "workspace_id": {"type": "string"},
                "slide_index": {"type": "integer", "description": "0-based content slide index."},
                "title": {"type": "string"},
                "bullet_points": {"type": "array", "items": {"type": "string"}},
                "presenter_notes": {"type": "string"},
                "archetype": {"type": "string"},
                "visual_caption": {"type": "string"},
                "container_style_override": {"type": "string", "enum": ["CLEAN_OPEN", "LEFT_ACCENT_LINE", "BOXED_CARDS"]},
                "image_frame_style_override": {"type": "string", "enum": ["FRAMELESS_CLEAN", "SOFT_SHADOW", "FRAMED_CARD"]},
                "header_chrome_style_override": {"type": "string", "enum": ["MINIMAL_ACCENT", "SOLID_PILL"]},
            },
        },
        "handler": mcp_tool_update_slide_in_deck,
    },
    "polish_slide_teaching_notes": {
        "name": "polish_slide_teaching_notes",
        "description": "Synthesizes or polishes first-person [SAY], [DEMONSTRATE], and [ASK SCOUTS] counselor teaching scripts with inline stage cues.",
        "inputSchema": {
            "type": "object",
            "required": ["workspace_id", "slide_index"],
            "properties": {
                "workspace_id": {"type": "string"},
                "slide_index": {"type": "integer", "default": 0},
                "audience_level": {"type": "string", "default": "All Scouts (Ages 11–17)"},
            },
        },
        "handler": mcp_tool_polish_slide_teaching_notes,
    },
    "generate_or_select_slide_image": {
        "name": "generate_or_select_slide_image",
        "description": "Lists curated pamphlet/Nano Banana visuals for a slide, selects an alternate choice, or generates a Model Armor-guarded custom illustration.",
        "inputSchema": {
            "type": "object",
            "required": ["workspace_id", "slide_index"],
            "properties": {
                "workspace_id": {"type": "string"},
                "slide_index": {"type": "integer"},
                "action": {"type": "string", "enum": ["list_choices", "select_choice", "generate_custom"], "default": "list_choices"},
                "choice_index": {"type": "integer"},
                "custom_prompt": {"type": "string"},
                "include_slide_context": {"type": "boolean", "default": True},
                "user_consented": {"type": "boolean", "default": False},
            },
        },
        "handler": mcp_tool_generate_or_select_slide_image,
    },
    "apply_powerpoint_template": {
        "name": "apply_powerpoint_template",
        "description": "Switches a deck workspace to any built-in or uploaded PowerPoint template and rebuilds the .pptx presentation with SafeCanvasBounds.",
        "inputSchema": {
            "type": "object",
            "required": ["workspace_id", "template_id"],
            "properties": {
                "workspace_id": {"type": "string"},
                "template_id": {"type": "string", "description": "e.g. 'scouting_america_250', 'scouting_america_forest_sunrise', 'scouting_america_topographic', 'classic_outdoor_silhouette_navy'."},
                "visual_theme": {"type": "string", "description": "Optional 'WARM_CREAM' ('CREAM'), 'CRISP_WHITE' ('WHITE'), or 'DARK_SLATE' ('SLATE')."},
                "accent_palette_key": {"type": "string", "description": "Optional 'NAVY_GOLD', 'OLIVE_FOREST', 'EAGLE_CRIMSON', 'SLATE_ACTION', or 'MATCH_TEMPLATE'."},
                "layout_style_preset": {
                    "type": "string",
                    "description": "Optional 'AUTO_TEMPLATE', 'CLEAN_OPEN', 'LEFT_ACCENT_LINE', or 'BOXED_CARDS'.",
                    "enum": ["AUTO_TEMPLATE", "CLEAN_OPEN", "LEFT_ACCENT_LINE", "BOXED_CARDS"],
                },
                "deck_style": {
                    "type": "object",
                    "description": "Optional DeckStyleConfig dictionary.",
                },
            },
        },
        "handler": mcp_tool_apply_powerpoint_template,
    },
    "export_slide_deck": {
        "name": "export_slide_deck",
        "description": "Exports a saved deck workspace as a .pptx presentation download link or printable QR field checklist.",
        "inputSchema": {
            "type": "object",
            "required": ["workspace_id"],
            "properties": {
                "workspace_id": {"type": "string"},
                "export_format": {"type": "string", "enum": ["pptx", "pocket_checklist"], "default": "pptx"},
            },
        },
        "handler": mcp_tool_export_slide_deck,
    },
    "generate_class_prep_and_parent_letter": {
        "name": "generate_class_prep_and_parent_letter",
        "description": "Generates a timed counselor teaching agenda, Quartermaster gear list, and Prerequisite Parent/Scoutmaster Letter for a workspace.",
        "inputSchema": {
            "type": "object",
            "required": ["workspace_id"],
            "properties": {
                "workspace_id": {"type": "string"},
                "session_mode": {"type": "string", "default": "TWO_TROOP_MEETINGS"},
                "camp_or_location": {"type": "string", "default": "Summer Camp / Troop Hall"},
            },
        },
        "handler": mcp_tool_generate_class_prep_and_parent_letter,
    },
    "manage_patrol_blue_card_roster": {
        "name": "manage_patrol_blue_card_roster",
        "description": "Manages Application for Merit Badge (#34124) Scout attendees, requirement sign-offs, cross-badge roster copying, and Scoutbook CSV export.",
        "inputSchema": {
            "type": "object",
            "required": ["workspace_id", "action"],
            "properties": {
                "workspace_id": {"type": "string"},
                "action": {"type": "string", "enum": ["list", "add_or_update_scout", "copy_roster_from_workspace", "export_scoutbook_csv"]},
                "scout_name": {"type": "string"},
                "troop_number": {"type": "string"},
                "patrol_name": {"type": "string"},
                "completed_reqs": {"type": "array", "items": {"type": "string"}},
                "copy_from_workspace_id": {"type": "string"},
            },
        },
        "handler": mcp_tool_manage_patrol_blue_card_roster,
    },
    "audit_deck_conformance": {
        "name": "audit_deck_conformance",
        "description": "Runs the deterministic Stage-1 AABB geometry, font-floor (>=12pt), and visual conformance audit on a workspace's .pptx deck.",
        "inputSchema": {
            "type": "object",
            "required": ["workspace_id"],
            "properties": {
                "workspace_id": {"type": "string"},
            },
        },
        "handler": mcp_tool_audit_deck_conformance,
    },
    "generate_fillable_scout_workbook": {
        "name": "generate_fillable_scout_workbook",
        "description": "Generates a Fillable Form (GTA §7.0.3.2) Scout Workbook (HTML & Markdown) with Guide to Advancement Section 7.0.3.2 banner, option-track filtering, and pre-approval signature boxes.",
        "inputSchema": {
            "type": "object",
            "required": ["badge_name"],
            "properties": {
                "badge_name": {"type": "string", "description": "Official Merit Badge name (any of the 149 badges)."},
                "selected_option_track": {"type": "string", "description": "Optional option track filter (e.g. 'Option A', 'Triathlon')."},
                "include_qr": {"type": "boolean", "default": True},
            },
        },
        "handler": mcp_tool_generate_fillable_scout_workbook,
    },
    "generate_class_preparation_page_cpp": {
        "name": "generate_class_preparation_page_cpp",
        "description": "Generates a 1-Page Class Preparation Page (CPP) with 5-tier syllabus buckets, pre-work verification gates, and session pacing roadmap.",
        "inputSchema": {
            "type": "object",
            "required": ["badge_name"],
            "properties": {
                "badge_name": {"type": "string", "description": "Official Merit Badge name."},
                "schedule_format": {"type": "string", "default": "4_session_mbc"},
                "counselor_name": {"type": "string", "default": "Scoutmaster Bob"},
                "troop_affiliation": {"type": "string", "default": "Troop 19"},
            },
        },
        "handler": mcp_tool_generate_class_preparation_page_cpp,
    },
    "manage_multisession_clinic_attendance_and_partials": {
        "name": "manage_multisession_clinic_attendance_and_partials",
        "description": "Manages multi-session clinic schedules (4x75m, 2xDouble-Block, Snow-Day Make-Up), Scout attendance (S1..S4, M), and smart partial classifications (Actionable Make-Up vs. Expected Home-Troop).",
        "inputSchema": {
            "type": "object",
            "required": ["workspace_id"],
            "properties": {
                "workspace_id": {"type": "string"},
                "badge_name": {"type": "string", "default": "First Aid"},
                "action": {"type": "string", "enum": ["list", "save_schedule", "upsert_scout"], "default": "list"},
                "scout_id": {"type": "string"},
                "scout_name": {"type": "string"},
                "troop_unit": {"type": "string", "default": "Troop 19"},
                "session_attendance": {"type": "object"},
                "completed_reqs": {"type": "array", "items": {"type": "string"}},
                "partial_classifications": {"type": "object"},
                "schedule_format": {"type": "string", "default": "4_session_mbc"},
                "postponed_session_idx": {"type": "integer"},
                "companion_badge_name": {"type": "string"},
            },
        },
        "handler": mcp_tool_manage_multisession_clinic_attendance_and_partials,
    },
}


# ==============================================================================
# 3. MCP PROMPTS (5 GUIDED WORKFLOW PROMPTS)
# ==============================================================================

MCP_PROMPTS_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "build-camp-merit-badge-curriculum",
        "description": "Builds a complete 5-day Summer Camp Merit Badge slide deck, timed lesson plan, and Quartermaster gear checklist.",
        "arguments": [
            {"name": "badge_name", "description": "Official Merit Badge name (e.g. 'First Aid', 'Camping').", "required": True},
            {"name": "template_id", "description": "PowerPoint template ID (e.g. 'scouting_america_250').", "required": False},
        ],
    },
    {
        "name": "prepare-merit-badge-midway-bundle",
        "description": "Batch-creates harmonized slide decks and parent prerequisite letters for multiple Merit Badges taught at a Council Midway.",
        "arguments": [
            {"name": "badge_names_csv", "description": "Comma-separated Merit Badge names (e.g. 'First Aid, Emergency Preparedness, Search and Rescue').", "required": True},
            {"name": "template_id", "description": "Shared PowerPoint template ID.", "required": False},
        ],
    },
    {
        "name": "review-scout-blue-card-signoffs",
        "description": "Audits a workspace's Patrol Blue Card (#34124) roster against official requirements and exports a Scoutbook CSV.",
        "arguments": [
            {"name": "workspace_id", "description": "Target deck workspace ID.", "required": True},
        ],
    },
    {
        "name": "customize-slide-deck-for-local-troop",
        "description": "Enriches a Merit Badge deck workspace with local council terrain, weather hazards, and regional field trip examples.",
        "arguments": [
            {"name": "workspace_id", "description": "Target deck workspace ID.", "required": True},
            {"name": "state_code", "description": "2-letter US State code (e.g. 'CA', 'CO').", "required": True},
            {"name": "city_or_camp", "description": "Local city or Scout camp name.", "required": False},
        ],
    },
    {
        "name": "multisession_mbc_clinic_facilitator_prompt",
        "description": "Orchestrates a multi-session Merit Badge College or clinic workflow: generates the 1-Page CPP, fillable Scout workbook, 4-session schedule, and tracks attendance & partials.",
        "arguments": [
            {"name": "badge_name", "description": "Official Merit Badge name (e.g. 'First Aid', 'Citizenship in the Nation').", "required": True},
            {"name": "schedule_format", "description": "Schedule preset ('4_session_mbc', '2_double_block', 'camp_5_day').", "required": False},
        ],
    },
]


def get_mcp_prompt_messages(name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Renders structured MCP prompt messages for any of the 4 guided counselor workflows."""
    args = arguments or {}
    clean_name = str(name or "").strip()
    if clean_name in ("build-camp-merit-badge-curriculum", "plan-merit-badge-camp-class"):
        badge = args.get("badge_name", "First Aid")
        tpl = args.get("template_id", "scouting_america_250")
        return {
            "description": f"5-Day Summer Camp Curriculum & Slide Deck Builder for {badge}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Please build a complete Summer Camp curriculum for the {badge} Merit Badge:\n"
                            f"1. Read `bsa://badges/{badge}/requirements` to inspect all official requirements.\n"
                            f"2. Call `create_merit_badge_slide_deck` with `badge_name='{badge}'` and `template_id='{tpl}'`.\n"
                            f"3. Call `generate_class_prep_and_parent_letter` with `session_mode='SUMMER_CAMP_5DAY'`.\n"
                            f"4. Call `audit_deck_conformance` to verify zero AABB overlaps."
                        ),
                    },
                }
            ],
        }
    if clean_name in ("prepare-merit-badge-midway-bundle", "prepare-midway-multi-badge-bundle"):
        badges = args.get("badge_names_csv") or args.get("badges_csv", "First Aid, Emergency Preparedness")
        tpl = args.get("template_id", "scouting_america_forest_sunrise")
        return {
            "description": f"Merit Badge Midway Multi-Deck Bundle ({badges})",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Prepare a harmonized Merit Badge Midway bundle for [{badges}] using template `{tpl}`:\n"
                            f"1. For each badge in [{badges}], call `create_merit_badge_slide_deck` with `template_id='{tpl}'`.\n"
                            f"2. Generate the Prerequisite Parent Letter for each workspace via `generate_class_prep_and_parent_letter`.\n"
                            f"3. Summarize the workspace IDs, slide counts, and `.pptx` download links."
                        ),
                    },
                }
            ],
        }
    if clean_name in ("review-scout-blue-card-signoffs", "audit-blue-card-readiness"):
        ws_id = args.get("workspace_id", "")
        return {
            "description": f"Patrol Blue Card (#34124) Readiness & Sign-Off Audit ({ws_id})",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Audit Patrol Blue Card (#34124) sign-offs for workspace `{ws_id}`:\n"
                            f"1. Call `get_slide_deck_workspace` for `{ws_id}`.\n"
                            f"2. Call `manage_patrol_blue_card_roster` with `action='export_scoutbook_csv'`.\n"
                            f"3. Report which Scouts have completed all requirements vs. partials."
                        ),
                    },
                }
            ],
        }
    if clean_name in ("customize-slide-deck-for-local-troop", "customize-slide-for-younger-scouts"):
        ws_id = args.get("workspace_id", "")
        st = args.get("state_code", "CA")
        loc = args.get("city_or_camp", "Local Council Camp")
        return {
            "description": f"Local Troop & Camp Grounding for Workspace {ws_id} ({loc}, {st})",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Customize workspace `{ws_id}` for `{loc}, {st}`:\n"
                            f"1. Inspect the workspace slides with `get_slide_deck_workspace`.\n"
                            f"2. Polish key teaching scripts via `polish_slide_teaching_notes`.\n"
                            f"3. Verify AABB geometry conformance via `audit_deck_conformance`."
                        ),
                    },
                }
            ],
        }
    if clean_name in ("multisession_mbc_clinic_facilitator_prompt", "multisession-mbc-clinic-facilitator"):
        badge = args.get("badge_name", "First Aid")
        sched = args.get("schedule_format", "4_session_mbc")
        return {
            "description": f"Multi-Session Merit Badge Clinic Facilitator Workflow for {badge} ({sched})",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Prepare and facilitate a multi-session Merit Badge clinic for `{badge}` (`{sched}`):\n"
                            f"1. Read `bsa://badges/{badge}/class-prep-cpp` and call `generate_class_preparation_page_cpp`.\n"
                            f"2. Call `generate_fillable_scout_workbook` with `badge_name='{badge}'`.\n"
                            f"3. Call `create_merit_badge_slide_deck` to build the slide deck with the 5-Part Facilitator Guide.\n"
                            f"4. Use `manage_multisession_clinic_attendance_and_partials` to track S1..S4 and Make-Up attendance."
                        ),
                    },
                }
            ],
        }
    return {"description": f"Unknown prompt: {clean_name}", "messages": []}


# ==============================================================================
# 4. JSON-RPC 2.0 DISPATCHER (FOR FASTAPI `/mcp` & IN-APP PLAYGROUND)
# ==============================================================================


def get_mcp_server_manifest() -> Dict[str, Any]:
    """Returns full MCP server metadata, tools, resources, prompts, and client config snippets."""
    return {
        "server_name": MCP_SERVER_NAME,
        "server_version": MCP_SERVER_VERSION,
        "protocol_version": MCP_PROTOCOL_VERSION,
        "transports": ["stdio", "http-jsonrpc", "sse"],
        "endpoints": {
            "info": "/mcp/info",
            "jsonrpc": "/mcp",
            "sse": "/mcp/sse",
        },
        "counts": {
            "tools": len(MCP_TOOLS_REGISTRY),
            "resources": len(MCP_RESOURCES_CATALOG),
            "prompts": len(MCP_PROMPTS_CATALOG),
        },
        "tools": [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            }
            for t in MCP_TOOLS_REGISTRY.values()
        ],
        "resources": MCP_RESOURCES_CATALOG,
        "prompts": MCP_PROMPTS_CATALOG,
        "client_snippets": {
            "claude_desktop": {
                "label": "Claude Desktop",
                "mcpServers": {
                    "scouts-bsa-workbench": {
                        "command": "python",
                        "args": ["-m", "src.mcp_server"],
                        "env": {"PYTHONPATH": "."},
                    }
                },
            },
            "gemini_cli_agy": {
                "label": "Gemini CLI / AGY",
                "mcpServers": {
                    "scouts-bsa-workbench": {
                        "httpUrl": "http://localhost:8080/mcp",
                        "command": "python",
                        "args": ["-m", "src.mcp_server"],
                    }
                },
            },
            "cursor": {
                "label": "Cursor / VS Code",
                "mcpServers": {
                    "scouts-bsa-workbench": {
                        "url": "http://localhost:8080/mcp/sse",
                    }
                },
            },
            "google_adk": {
                "label": "Google ADK MCPToolset",
                "command": "python -m src.mcp_server",
            },
        },
    }


def handle_mcp_jsonrpc_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Processes a standard Model Context Protocol JSON-RPC 2.0 request (`initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, `prompts/list`, `prompts/get`)."""
    req_id = payload.get("id", 1)
    method = str(payload.get("method") or "").strip()
    params = payload.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": {
                    "name": MCP_SERVER_NAME,
                    "version": MCP_SERVER_VERSION,
                },
            },
        }

    if method in ("notifications/initialized", "ping"):
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": t["name"],
                        "description": t["description"],
                        "inputSchema": t["inputSchema"],
                    }
                    for t in MCP_TOOLS_REGISTRY.values()
                ]
            },
        }

    if method == "tools/call":
        tool_name = str(params.get("name") or "").strip()
        tool_args = params.get("arguments") or {}
        spec = MCP_TOOLS_REGISTRY.get(tool_name)
        if not spec:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown MCP tool '{tool_name}'."},
            }
        try:
            from src.observability.logging_setup import scrub_pii_from_structure

            res_obj = scrub_pii_from_structure(spec["handler"](**tool_args))
            is_err = isinstance(res_obj, dict) and res_obj.get("status") == "ERROR"
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(res_obj, indent=2, ensure_ascii=False),
                        }
                    ],
                    "structuredContent": res_obj,
                    "isError": is_err,
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"status": "ERROR", "message": str(exc)})}],
                    "isError": True,
                },
            }

    if method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"resources": MCP_RESOURCES_CATALOG},
        }

    if method == "resources/read":
        from src.observability.logging_setup import scrub_pii_from_structure

        uri = str(params.get("uri") or "").strip()
        res_data = scrub_pii_from_structure(read_mcp_resource(uri))
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(res_data.get("data", res_data), indent=2, ensure_ascii=False),
                    }
                ]
            },
        }

    if method == "prompts/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"prompts": MCP_PROMPTS_CATALOG},
        }

    if method == "prompts/get":
        p_name = str(params.get("name") or "").strip()
        p_args = params.get("arguments") or {}
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": get_mcp_prompt_messages(p_name, p_args),
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method '{method}' not supported by {MCP_SERVER_NAME}."},
    }


# ==============================================================================
# 5. FASTMCP CLI ENTRYPOINT (`python -m src.mcp_server`)
# ==============================================================================


class _StdioFastMCPAdapter:
    """Fallback FastMCP-compatible registry and stdio JSON-RPC runner when `fastmcp` is not installed."""

    def __init__(self, server_name: str) -> None:
        self.name = server_name
        self.tools: Dict[str, Any] = {}
        self.resources: Dict[str, Any] = {}
        self.prompts: Dict[str, Any] = {}

    def tool(self, name: str, description: str = "") -> Any:
        def _decorator(fn: Any) -> Any:
            self.tools[name] = {"name": name, "description": description, "handler": fn}
            return fn

        return _decorator

    def resource(self, uri: str, name: str = "", description: str = "", mime_type: str = "application/json") -> Any:
        def _decorator(fn: Any) -> Any:
            self.resources[uri] = {
                "uri": uri,
                "name": name or uri,
                "description": description,
                "mimeType": mime_type,
                "handler": fn,
            }
            return fn

        return _decorator

    def prompt(self, name: str, description: str = "") -> Any:
        def _decorator(fn: Any) -> Any:
            self.prompts[name] = {"name": name, "description": description, "handler": fn}
            return fn

        return _decorator

    def run(self) -> None:
        import sys

        for line in sys.stdin:
            raw = line.strip()
            if not raw:
                continue
            try:
                req = json.loads(raw)
                resp = handle_mcp_jsonrpc_request(req)
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            except Exception as exc:
                err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()


def build_fastmcp_instance() -> Any:
    """Constructs a `FastMCP` server instance with all 12 tools, 6 resources, and 4 prompts registered."""
    try:
        from fastmcp import FastMCP  # type: ignore
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP  # type: ignore
        except ImportError:
            FastMCP = _StdioFastMCPAdapter  # type: ignore

    mcp = FastMCP(MCP_SERVER_NAME)
    for t_spec in MCP_TOOLS_REGISTRY.values():
        mcp.tool(name=t_spec["name"], description=t_spec["description"])(t_spec["handler"])

    for r_spec in MCP_RESOURCES_CATALOG:
        r_uri = r_spec["uri"]
        r_name = r_spec.get("name", r_uri)
        r_desc = r_spec.get("description", "")

        def _make_resource_reader(bound_uri: str) -> Any:
            def _reader() -> str:
                res_data = read_mcp_resource(bound_uri)
                return json.dumps(res_data.get("data", res_data), indent=2, ensure_ascii=False)

            return _reader

        try:
            mcp.resource(r_uri, name=r_name, description=r_desc)(_make_resource_reader(r_uri))
        except TypeError:
            mcp.resource(r_uri)(_make_resource_reader(r_uri))

    for p_spec in MCP_PROMPTS_CATALOG:
        p_name = p_spec["name"]
        p_desc = p_spec.get("description", "")

        def _make_prompt_handler(bound_name: str) -> Any:
            def _prompt_fn(**kwargs: Any) -> Dict[str, Any]:
                return get_mcp_prompt_messages(bound_name, kwargs)

            return _prompt_fn

        try:
            mcp.prompt(name=p_name, description=p_desc)(_make_prompt_handler(p_name))
        except TypeError:
            mcp.prompt(p_name)(_make_prompt_handler(p_name))

    return mcp


def main() -> None:
    """Runs the Scouts BSA Merit Badge Workbench MCP server over stdio."""
    mcp = build_fastmcp_instance()
    mcp.run()


if __name__ == "__main__":
    main()
