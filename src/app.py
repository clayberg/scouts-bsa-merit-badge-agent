"""Scouts BSA Merit Badge Counselor Workbench — Google Material 3 Expressive Streamlit UI (`src/app.py`).

Matches the Google Material 3 Expressive A2UI (`ui/index.html` + `ui/app.js`) in layout, styling, and functionality:
1. Left Rail Sidebar:
   - Card 1: Find & Select Merit Badge (Search, Category & Eagle filters, Select Merit Badge dropdown, and Quick-Select Popular Badge pills).
   - Card 2: Deck Style & Counselor Info (Deep Dive vs. Standard Deck, Counselor Name 'Scoutmaster Bob', Troop & Council 'Troop 123, My Council', Contact Email 'counselor@troop123.org', Contact Phone '(000) 555-1234', and Optional Troop Custom Logo upload).
   - Card 3: Research & Generation Progress trace cards.
2. Right Main Stage:
   - Top App Bar with one-click links to the Official BSA Pamphlet (PDF), Scouting.org Resource Guide, Workbook (.MD) download, and Slide Deck (.PPTX) download.
   - Navy & Scouting Gold Hero Summary Banner with circular standalone Merit Badge Emblem, Eagle/Elective status kicker, and Total Slides / Requirements KPI pills.
   - Tab 1 (Slide Deck Preview): 2-Column Interactive Storyboard with Left Filmstrip + Right 16:9 Widescreen Slide Stage (Prev/Next navigation, borderless Cover Slide 1 rendering all counselor inputs + troop logo + badge emblem + pamphlet cover, and clean teaching/diagram slides) + Counselor Teaching Notes card.
   - Tab 2 (Official Requirements & Resource Guides): 3-Column Triage Matrix (Discussion & Core Knowledge, Hands-On Skill Demonstrations, Campout, Field & Home Projects).
   - Tab 3 (Scout & Counselor Workbook): Printable `.md` workbook preview & download.
"""

import base64
import html
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.agents.beautifier import generate_ai_editorial_illustration
from src.agents.coordinator import run_merit_badge_workflow
from src.agents.guardrails import estimate_workflow_finops_cost
from src.agents.image_studio import (
    NANO_BANANA_VISUAL_STYLES,
    clean_slide_topic_boilerplate,
    estimate_nano_banana_image_cost,
    generate_nano_banana_slide_image,
    get_badge_image_catalog,
    purge_cached_web_and_ai_images,
    register_image_in_badge_catalog,
    resolve_content_aware_visual_config,
    search_web_images_for_slide,
    upload_custom_slide_image,
)
from src.config import (
    OFFICIAL_BSA_MERIT_BADGES_CATALOG,
    ScoutsBSAPalette,
    get_merit_badge_metadata,
)
from src.memory.session_store import (
    clear_local_counselor_profile,
    get_persistent_session_store,
    load_local_counselor_profile,
    save_local_counselor_profile,
)
from src.schemas import CURRENT_SCHEMA_VERSION
from src.tools.counselor_studiokit import generate_prerequisite_parent_letter
from src.tools.pamphlet_extractor import get_badge_cover_and_patch_paths
from src.tools.pptx_builder import (
    CounselorTitleSlideInfo,
    PowerPointBuildRequest,
    SlideSpec,
    generate_bsa_slide_deck_pptx,
)


# ==============================================================================
# HELPER UTILITIES FOR M3 HTML STAGE & BASE64 ASSETS
# ==============================================================================

def _escape(val: Any) -> str:
    return html.escape(str(val if val is not None else ""))


def _clean_html(raw_html: str) -> str:
    """Strips leading indentation and blank lines so CommonMark never parses HTML as 4-space code blocks."""
    return "\n".join(line.strip() for line in raw_html.splitlines() if line.strip())


@st.cache_data(show_spinner=False)
def _file_to_data_uri(path_str: Optional[str], mtime: float = 0.0) -> str:
    """Converts a local image file (.png/.jpg) into a base64 data URI for inline 16:9 slide stage rendering."""
    if not path_str or not os.path.exists(path_str):
        return ""
    ext = os.path.splitext(path_str)[1].lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    try:
        with open(path_str, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""


def _get_data_uri(path_str: Optional[str]) -> str:
    if not path_str or not os.path.exists(path_str):
        return ""
    try:
        mtime = os.path.getmtime(path_str)
    except Exception:
        mtime = 0.0
    return _file_to_data_uri(path_str, mtime)


def _format_speaker_notes_html(raw_notes: Optional[str]) -> str:
    lines = [line.strip() for line in (raw_notes or "").splitlines() if line.strip()]
    rendered_lines: List[str] = []
    for line in lines:
        decorated = (
            _escape(line)
            .replace("[SAY]", '<span class="m3-cue-tag">[SAY]</span>')
            .replace(
                "[DEMONSTRATE]",
                '<span class="m3-cue-tag" style="background:#E2EDC8;color:#151E00;">[DEMONSTRATE]</span>',
            )
            .replace(
                "[ASK SCOUTS]",
                '<span class="m3-cue-tag" style="background:#FEF3C7;color:#B45309;">[ASK SCOUTS]</span>',
            )
        )
        rendered_lines.append(f'<div style="margin-bottom:8px;">{decorated}</div>')
    return "".join(rendered_lines)


def _render_finops_table_html(finops_data: Dict[str, Any]) -> str:
    """Renders the FinOps Cost & Token Budget dictionary as a clean, styled 2-column HTML table."""
    f = finops_data or {}
    est_cost = float(f.get("estimated_cost_usd", 0.14))
    max_cap = float(f.get("max_budget_usd", 1.00))
    headroom = max(0.0, max_cap - est_cost)
    rerun_cost = float(f.get("cached_rerun_cost_usd", 0.02))
    within_budget = bool(f.get("within_budget", est_cost <= max_cap))
    status_badge = (
        '<span style="background:#DCFCE7; color:#15803D; font-weight:700; padding:3px 10px; border-radius:999px; font-size:0.76rem;">✓ Within $1.00 Cap</span>'
        if within_budget
        else '<span style="background:#FEE2E2; color:#B91C1C; font-weight:700; padding:3px 10px; border-radius:999px; font-size:0.76rem;">⚠️ Over Cap</span>'
    )
    in_tok = int(f.get("estimated_input_tokens", 18500))
    out_tok = int(f.get("estimated_output_tokens", 6200))
    total_tok = in_tok + out_tok
    planned_imgs = int(f.get("planned_ai_hero_images", 0))
    tier_lbl = _escape(f.get("beautification_tier", "BEAUTIFIED"))
    depth_lbl = _escape(f.get("depth_mode", "Deep Dive / Camp School Deck"))
    dr_lbl = "Enabled (NOAA / Terrain / Field Sites)" if f.get("enable_deep_research", True) else "Disabled"

    rows = [
        ("Budget Status", status_badge),
        (
            "Estimated Deck Cost",
            f'<span style="font-family:\'JetBrains Mono\',monospace; font-weight:800; color:#003F87; font-size:0.92rem;">${est_cost:.2f} USD</span>',
        ),
        (
            "Per-Deck Budget Ceiling",
            f'<span style="font-family:\'JetBrains Mono\',monospace; font-weight:700;">${max_cap:.2f} USD</span> '
            f'<span style="color:#15803D; font-size:0.78rem; font-weight:600;">(${headroom:.2f} headroom)</span>',
        ),
        (
            "Cached Rerun Cost",
            f'<span style="font-family:\'JetBrains Mono\',monospace; font-weight:700; color:#15803D;">${rerun_cost:.2f} USD</span> (75% ADK prefix discount)',
        ),
        ("Visual Polish Tier", f"<code>{tier_lbl}</code> ({planned_imgs} hero graphics)"),
        ("Deck Depth Mode", depth_lbl),
        ("Input Context Tokens", f'<span style="font-family:\'JetBrains Mono\',monospace; font-weight:600;">{in_tok:,}</span> tokens'),
        ("Output Generation Tokens", f'<span style="font-family:\'JetBrains Mono\',monospace; font-weight:600;">{out_tok:,}</span> tokens'),
        ("Total Token Footprint", f'<strong style="font-family:\'JetBrains Mono\',monospace;">{total_tok:,} tokens</strong>'),
        ("Local Regional Grounding", dr_lbl),
        ("On-Demand AI Image Rate", '<span style="font-family:\'JetBrains Mono\',monospace; font-weight:700;">$0.04 USD</span> / image (Consent Gate)'),
    ]
    tr_html = "".join(
        f'<tr style="border-bottom:1px solid #E2E8F0;">'
        f'<td style="padding:9px 14px; font-weight:600; color:#1E293B; background:#F8FAFC; width:48%;">{label}</td>'
        f'<td style="padding:9px 14px; color:#0F172A;">{val}</td>'
        f"</tr>"
        for label, val in rows
    )
    return _clean_html(
        f"""
        <div style="background:#FFFFFF; border:1.5px solid #CBD5E1; border-radius:14px; overflow:hidden; box-shadow:0 2px 6px rgba(15,23,42,0.05);">
          <table style="width:100%; border-collapse:collapse; font-size:0.84rem; text-align:left;">
            <thead>
              <tr style="background:linear-gradient(135deg, #002B5E 0%, #003F87 100%); color:#FFFFFF;">
                <th style="padding:10px 14px; font-weight:700;">FinOps Metric</th>
                <th style="padding:10px 14px; font-weight:700;">Value</th>
              </tr>
            </thead>
            <tbody>
              {tr_html}
            </tbody>
          </table>
        </div>
        """
    )


def _resolve_slide_palette_tokens(slide: Optional[Dict[str, Any]], deck_tier: str) -> Dict[str, Any]:
    """Resolves Layer-0 Magazine Vector Card styling tokens for STANDARD, BEAUTIFIED, and STUDIO modes."""
    s_obj = slide or {}
    tier = str(s_obj.get("beautification_tier") or deck_tier or "BEAUTIFIED").upper()
    if tier == "STANDARD":
        return {
            "tier": "STANDARD",
            "is_beautified": False,
            "is_studio": False,
            "stage_bg": "#FFFFFF",
            "text_fg": "#0F172A",
            "sub_text_fg": "#334155",
            "primary_hex": "#003F87",
            "accent_hex": "#CBD5E1",
            "card_bg": "#F1F5F9",
            "badge_bg": "#E2E8F0",
            "badge_fg": "#334155",
            "stage_border": "2px solid #CBD5E1",
            "header_bg": "transparent",
            "footer_color": "#64748B",
        }

    palette_key = str(s_obj.get("accent_palette_key") or "NAVY_GOLD").upper()
    if tier == "STUDIO":
        studio_accents = {
            "NAVY_GOLD": {"primary_hex": "#38BDF8", "accent_hex": "#F4C430"},
            "OLIVE_FOREST": {"primary_hex": "#4ADE80", "accent_hex": "#A3E635"},
            "EAGLE_CRIMSON": {"primary_hex": "#FB7185", "accent_hex": "#F4C430"},
            "SLATE_ACTION": {"primary_hex": "#60A5FA", "accent_hex": "#38BDF8"},
        }
        st_choice = studio_accents.get(palette_key, studio_accents["NAVY_GOLD"])
        return {
            "tier": "STUDIO",
            "is_beautified": True,
            "is_studio": True,
            "stage_bg": "#0F172A",
            "text_fg": "#F8FAFC",
            "sub_text_fg": "#E2E8F0",
            "primary_hex": st_choice["primary_hex"],
            "accent_hex": st_choice["accent_hex"],
            "card_bg": "#1E293B",
            "badge_bg": "#1E293B",
            "badge_fg": st_choice["accent_hex"],
            "stage_border": f"3px solid {st_choice['accent_hex']}",
            "header_bg": "linear-gradient(90deg, rgba(30,41,59,0.92) 0%, rgba(15,23,42,0.92) 100%)",
            "footer_color": "#94A3B8",
        }

    palette_map = {
        "NAVY_GOLD": {
            "primary_hex": "#003F87",
            "accent_hex": "#D4AF37",
            "card_bg": "#EFF6FF",
            "badge_bg": "#FEF3C7",
            "badge_fg": "#92400E",
            "header_bg": "linear-gradient(90deg, rgba(0,63,135,0.06) 0%, rgba(212,175,55,0.12) 100%)",
        },
        "OLIVE_FOREST": {
            "primary_hex": "#2E4600",
            "accent_hex": "#4B5320",
            "card_bg": "#F1F8E9",
            "badge_bg": "#DCFCE7",
            "badge_fg": "#166534",
            "header_bg": "linear-gradient(90deg, rgba(46,70,0,0.06) 0%, rgba(75,83,32,0.12) 100%)",
        },
        "EAGLE_CRIMSON": {
            "primary_hex": "#8B0000",
            "accent_hex": "#CE1126",
            "card_bg": "#FFF5F5",
            "badge_bg": "#FEE2E2",
            "badge_fg": "#991B1B",
            "header_bg": "linear-gradient(90deg, rgba(139,0,0,0.06) 0%, rgba(206,17,38,0.12) 100%)",
        },
        "SLATE_ACTION": {
            "primary_hex": "#0F172A",
            "accent_hex": "#005AE0",
            "card_bg": "#F0F9FF",
            "badge_bg": "#DBEAFE",
            "badge_fg": "#1E40AF",
            "header_bg": "linear-gradient(90deg, rgba(15,23,42,0.06) 0%, rgba(0,90,224,0.12) 100%)",
        },
    }
    chosen = palette_map.get(palette_key, palette_map["NAVY_GOLD"])
    return {
        "tier": "BEAUTIFIED",
        "is_beautified": True,
        "is_studio": False,
        "stage_bg": "#FAF8F5",
        "text_fg": "#0F172A",
        "sub_text_fg": "#334155",
        "primary_hex": chosen["primary_hex"],
        "accent_hex": chosen["accent_hex"],
        "card_bg": chosen["card_bg"],
        "badge_bg": chosen["badge_bg"],
        "badge_fg": chosen["badge_fg"],
        "stage_border": f"2.5px solid {chosen['accent_hex']}",
        "header_bg": chosen["header_bg"],
        "footer_color": "#64748B",
    }


def _render_widescreen_slide_html(
    result: Dict[str, Any],
    slide_idx: int,
    counselor_name: str,
    troop_affiliation: str,
    email_address: str,
    phone_number: str,
    logo_path: Optional[str],
    patch_path: Optional[str],
    cover_path: Optional[str],
    location_or_zip: str = "",
) -> str:
    """Renders the 16:9 Widescreen Slide Stage HTML matching `ui/index.html`, `ui/app.js`, and `pptx_builder.py`."""
    badge_name = result.get("badge_name", "First Aid")
    eagle_flag = bool(result.get("is_eagle_required"))
    deck_tier = str(result.get("beautification_tier") or "BEAUTIFIED").upper()
    slides: List[Dict[str, Any]] = (result.get("storyboard") or {}).get("slides", [])
    total_slides = len(slides) + 1

    # CASE A: Slide 1 — Borderless Cover Slide (Emblem Upper-Left, Title Center, Pamphlet Right, Counselor + Troop Logo Lower-Left)
    if slide_idx == -1:
        cover_tokens = _resolve_slide_palette_tokens(None, deck_tier)
        patch_uri = _get_data_uri(patch_path)
        cover_uri = _get_data_uri(cover_path)
        logo_uri = _get_data_uri(logo_path)

        patch_html = (
            f'<img src="{patch_uri}" alt="Badge Emblem" style="width:118px; height:118px; object-fit:contain; flex-shrink:0;" />'
            if patch_uri
            else ""
        )
        title_color = "#F8FAFC" if cover_tokens["is_studio"] else "#003F87"
        subtitle_color = (
            ("#F4C430" if eagle_flag else "#4ADE80")
            if cover_tokens["is_studio"]
            else ("#CE1126" if eagle_flag else "#4B5320")
        )
        subtitle_text = "Eagle-Required Merit Badge" if eagle_flag else "Scouts BSA Merit Badge"
        lbl_color = "#38BDF8" if cover_tokens["is_studio"] else "#003F87"
        unit_lbl_color = "#F4C430" if cover_tokens["is_studio"] else "#4B5320"
        body_txt_color = cover_tokens["text_fg"]

        resolved_loc = (
            location_or_zip.strip()
            or ((result.get("deep_research_enrichment") or {}).get("resolved_location") or {}).get("region_label")
            or ""
        )
        loc_html = (
            f'<div style="font-size:0.98rem; color:{body_txt_color}; margin-bottom:4px;"><strong style="color:{unit_lbl_color};">Location:</strong> {_escape(resolved_loc)}</div>'
            if resolved_loc
            else ""
        )
        email_html = (
            f'<div style="font-size:0.98rem; color:{body_txt_color}; margin-bottom:4px;"><strong style="color:{lbl_color};">Email:</strong> {_escape(email_address)}</div>'
            if email_address
            else ""
        )
        phone_html = (
            f'<div style="font-size:0.98rem; color:{body_txt_color};"><strong style="color:{lbl_color};">Phone:</strong> {_escape(phone_number)}</div>'
            if phone_number
            else ""
        )
        logo_html = (
            f'<img src="{logo_uri}" alt="Troop Custom Logo" style="width:94px; height:94px; object-fit:contain; flex-shrink:0;" />'
            if logo_uri
            else ""
        )
        cover_right_html = (
            f'<div class="m3-slide-right-visual" style="border:none; background:transparent;">'
            f'<img src="{cover_uri}" alt="{_escape(badge_name)} Official Pamphlet Cover" style="max-height:360px; width:auto;" />'
            f"</div>"
            if cover_uri
            else ""
        )
        grid_cols = "1.2fr 0.8fr" if cover_uri else "1fr"

        return _clean_html(
            f"""
            <div class="m3-widescreen-slide" style="background:{cover_tokens['stage_bg']}; border:{cover_tokens['stage_border']};">
              <div class="m3-slide-body-split" style="grid-template-columns:{grid_cols}; padding-top:28px;">
                <div class="m3-slide-left-zone" style="justify-content:space-between;">
                  <div style="display:flex; align-items:center; gap:24px; padding:12px 8px;">
                    {patch_html}
                    <div style="flex:1; text-align:center;">
                      <div style="font-size:2.2rem; font-weight:800; color:{title_color}; line-height:1.15;">{_escape(badge_name)}</div>
                      <div style="font-size:1.15rem; font-weight:700; margin-top:6px; color:{subtitle_color};">{subtitle_text}</div>
                    </div>
                  </div>
                  <div style="display:flex; align-items:center; justify-content:space-between; gap:18px; padding:18px 8px; text-align:left;">
                    <div style="flex:1;">
                      <div style="font-size:1.24rem; font-weight:800; color:{lbl_color}; margin-bottom:6px;">Counselor: {_escape(counselor_name)}</div>
                      <div style="font-size:1.06rem; color:{body_txt_color}; margin-bottom:5px;"><strong style="color:{unit_lbl_color};">Unit / Council:</strong> {_escape(troop_affiliation)}</div>
                      {loc_html}
                      {email_html}
                      {phone_html}
                    </div>
                    {logo_html}
                  </div>
                </div>
                {cover_right_html}
              </div>
              <div class="m3-slide-footer-strip" style="color:{cover_tokens['footer_color']}; background:transparent;">
                <span>Scouts BSA {_escape(badge_name)} Merit Badge &bull; {_escape(deck_tier)} Mode</span>
                <span>{total_slides} Slides</span>
              </div>
            </div>
            """
        )

    # CASE B: Content Slides (slide_idx = 0 .. len(slides) - 1)
    slide = slides[slide_idx]
    archetype = slide.get("archetype") or "SPLIT_VISUAL_EXPLAINER"
    req_num = str(slide.get("req_number") or (slide_idx + 1))
    req_label = req_num if req_num in ("Overview", "Sources") else f"Requirement {req_num}"
    req_header_label = "Curriculum & Local Context" if req_num == "Overview" else f"Official {req_label}"
    title = slide.get("title") or ""
    tokens = _resolve_slide_palette_tokens(slide, deck_tier)
    vis_theme = str(slide.get("visual_theme") or "STANDARD_CARDS")
    callout_badge = str(slide.get("callout_badge_text") or "")

    verbatim = str(slide.get("verbatim_requirement_text") or "").strip()
    req_strip_html = (
        f'<div class="m3-slide-req-strip" style="border-color:{tokens["accent_hex"]}; background:{tokens["card_bg"] if tokens["is_beautified"] else "#FFFFFF"}; color:{tokens["text_fg"]};">'
        f'<div><strong style="color:{tokens["primary_hex"]};">{_escape(req_header_label)}:</strong> {_escape(verbatim)}</div></div>'
        if verbatim
        else ""
    )

    diag_path = slide.get("diagram_path")
    diag_uri = _get_data_uri(diag_path) if diag_path else ""
    has_visual = bool(diag_uri)
    hide_visual_for_intro = (
        archetype in ("CONCEPT_TEXT_SLIDE", "SOURCES_AND_REFERENCES", "REQUIREMENTS_TRIAGE_MATRIX")
        or (archetype == "REQUIREMENT_INTRO" and not tokens["is_beautified"])
    )
    is_split_with_req_banner = bool(verbatim and has_visual and not hide_visual_for_intro)

    theme_alias_map = {
        "NUMBERED_STEP_RIBBON": "NUMBERED_STEP_CARDS",
        "THREE_PILLAR_ACCENT_CARDS": "THREE_PILLAR_BENTO",
        "MAGAZINE_ASYMMETRIC_SPLIT": "THREE_PILLAR_BENTO",
        "ANNOTATED_INFOGRAPHIC_STAGE": "EDITORIAL_CALLOUT_QUOTE",
        "SAFETY_ALERT_SPOTLIGHT": "SAFETY_ALERT_SPLIT",
    }
    norm_theme = theme_alias_map.get(vis_theme, vis_theme)

    def _get_card_theme_spec(bp_idx: int) -> Tuple[str, str, str, str]:
        pad_override = " padding:9px 12px;" if is_split_with_req_banner else ""
        if not tokens["is_beautified"]:
            return (
                f"background:#F1F5F9; border:1px solid #CBD5E1; color:#0F172A;{pad_override}",
                tokens["primary_hex"],
                tokens["sub_text_fg"],
                "",
            )
        if norm_theme == "DARK_SLATE_SPOTLIGHT":
            return (
                f"background:#1E293B; border:1.5px solid #F4C430; border-left:6px solid #38BDF8; color:#F8FAFC; box-shadow:0 4px 12px rgba(15,23,42,0.22);{pad_override}",
                "#F4C430",
                "#E2E8F0",
                '<span style="color:#38BDF8; font-weight:900; margin-right:6px;">★</span>',
            )
        if norm_theme == "SAFETY_ALERT_SPLIT":
            s_bg = "#311018" if tokens["is_studio"] else "#FFF1F2"
            s_border = "#FB7185" if tokens["is_studio"] else "#CE1126"
            return (
                f"background:{s_bg}; border:1.5px solid {s_border}; border-left:6px solid {s_border}; color:{tokens['text_fg']}; box-shadow:0 3px 10px rgba(206,17,38,0.10);{pad_override}",
                s_border,
                tokens["sub_text_fg"],
                f'<span style="display:inline-block; background:{s_border}; color:#FFFFFF; font-size:0.70rem; font-weight:800; padding:1px 6px; border-radius:5px; margin-right:6px;">⚠️ SAFETY</span>',
            )
        if norm_theme == "TIMELINE_CHEVRON_CARDS":
            return (
                f"background:{tokens['card_bg']}; border:1.5px solid {tokens['accent_hex']}; border-left:6px solid {tokens['primary_hex']}; color:{tokens['text_fg']};{pad_override}",
                tokens["primary_hex"],
                tokens["sub_text_fg"],
                f'<span style="display:inline-block; background:{tokens["badge_bg"]}; color:{tokens["badge_fg"]}; border:1px solid {tokens["accent_hex"]}; font-family:\'JetBrains Mono\',monospace; font-size:0.71rem; font-weight:800; padding:1px 7px; border-radius:999px; margin-right:7px;">STEP {bp_idx + 1} &#10140;</span>',
            )
        if norm_theme == "EDITORIAL_CALLOUT_QUOTE":
            q_bg = "#1E293B" if tokens["is_studio"] else "#FFFBEB"
            q_anc = "#FBBF24" if tokens["is_studio"] else "#B45309"
            return (
                f"background:{q_bg}; border:1.5px solid #F59E0B; border-left:6px solid #D97706; color:{tokens['text_fg']};{pad_override}",
                q_anc,
                tokens["sub_text_fg"],
                f'<span style="color:{q_anc}; font-size:1.05rem; font-weight:900; margin-right:6px;">&#10077;</span>',
            )
        if norm_theme == "THREE_PILLAR_BENTO":
            return (
                f"background:{tokens['card_bg']}; border:1.5px solid {tokens['accent_hex']}; border-top:5px solid {tokens['primary_hex']}; color:{tokens['text_fg']}; box-shadow:0 3px 10px rgba(15,23,42,0.08);{pad_override}",
                tokens["primary_hex"],
                tokens["sub_text_fg"],
                f'<span style="color:{tokens["accent_hex"]}; font-weight:900; margin-right:6px;">◆</span>',
            )
        num_fg = "#0F172A" if tokens["is_studio"] else "#FFFFFF"
        return (
            f"background:{tokens['card_bg']}; border:1.5px solid {tokens['accent_hex']}; border-left:6px solid {tokens['primary_hex']}; color:{tokens['text_fg']}; box-shadow:0 3px 10px rgba(15,23,42,0.08);{pad_override}",
            tokens["primary_hex"],
            tokens["sub_text_fg"],
            f'<span style="display:inline-block; background:{tokens["primary_hex"]}; color:{num_fg}; font-family:\'JetBrains Mono\',monospace; font-size:0.73rem; font-weight:700; padding:1px 7px; border-radius:6px; margin-right:7px;">0{bp_idx + 1}</span>',
        )

    card_style, base_anc_color, base_body_color, _ = _get_card_theme_spec(0)
    raw_bullets = slide.get("bullet_points") or []
    bullets = raw_bullets[:4] if (is_split_with_req_banner and len(raw_bullets) > 4) else raw_bullets
    left_cards_html = ""
    if archetype == "DIFFERENTIAL_COMPARISON_2COL":
        mid_idx = max(1, (len(bullets) + 1) // 2)
        cmp = slide.get("comparison_data") or {
            "left_header": "Primary Condition / Method A",
            "left_points": bullets[:mid_idx],
            "right_header": "Contrast Condition / Method B",
            "right_points": bullets[mid_idx:] or ["Compare key differences and field response."],
        }
        right_bg = "#311018" if tokens["is_studio"] else "#FFF5F5"
        right_anchor = "#FB7185" if tokens["is_studio"] else "#CE1126"
        l_pts = "".join(
            f'<div class="m3-slide-card-text" style="margin-top:4px; color:{tokens["sub_text_fg"]};">&bull; {_escape(pt)}</div>'
            for pt in (cmp.get("left_points") or [])
        )
        r_pts = "".join(
            f'<div class="m3-slide-card-text" style="margin-top:4px; color:{tokens["sub_text_fg"]};">&bull; {_escape(pt)}</div>'
            for pt in (cmp.get("right_points") or [])
        )
        left_cards_html = f"""
        <div class="m3-slide-2col-grid">
          <div class="m3-slide-card-item" style="border-top:4px solid {tokens['primary_hex']}; background:{tokens['card_bg']}; color:{tokens['text_fg']};">
            <div class="m3-slide-card-anchor" style="color:{tokens['primary_hex']};">{_escape(cmp.get("left_header") or "Concept A")}</div>
            {l_pts}
          </div>
          <div class="m3-slide-card-item" style="border-top:4px solid {right_anchor}; background:{right_bg}; color:{tokens['text_fg']};">
            <div class="m3-slide-card-anchor" style="color:{right_anchor};">{_escape(cmp.get("right_header") or "Concept B")}</div>
            {r_pts}
          </div>
        </div>
        """
    elif archetype == "REQUIREMENTS_TRIAGE_MATRIX":
        c2_color = "#4ADE80" if tokens["is_studio"] else "#4B5320"
        c3_color = "#F4C430" if tokens["is_studio"] else "#CE1126"
        b0 = bullets[0] if len(bullets) > 0 else "Review core principles."
        b1 = bullets[1] if len(bullets) > 1 else "Practice hands-on demonstrations."
        b2 = bullets[2] if len(bullets) > 2 else "Complete field logs and observations."
        local_card_html = (
            f'<div class="m3-slide-card-item" style="{card_style} margin-top:8px;">'
            f'<div class="m3-slide-card-text" style="color:{base_body_color};">📍 {_escape(bullets[3])}</div></div>'
            if len(bullets) > 3
            else ""
        )
        left_cards_html = f"""
        <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; width:100%;">
          <div class="m3-slide-card-item" style="border-top:5px solid {tokens['primary_hex']}; background:{tokens['card_bg']}; color:{tokens['text_fg']};">
            <div class="m3-slide-card-anchor" style="color:{tokens['primary_hex']}; margin-bottom:6px;">1. Discussion &amp; Core Theory</div>
            <div class="m3-slide-card-text" style="color:{tokens['sub_text_fg']};">&bull; {_escape(b0)}</div>
          </div>
          <div class="m3-slide-card-item" style="border-top:5px solid {c2_color}; background:{tokens['card_bg']}; color:{tokens['text_fg']};">
            <div class="m3-slide-card-anchor" style="color:{c2_color}; margin-bottom:6px;">2. Hands-On Skill Demonstrations</div>
            <div class="m3-slide-card-text" style="color:{tokens['sub_text_fg']};">&bull; {_escape(b1)}</div>
          </div>
          <div class="m3-slide-card-item" style="border-top:5px solid {c3_color}; background:{tokens['card_bg']}; color:{tokens['text_fg']};">
            <div class="m3-slide-card-anchor" style="color:{c3_color}; margin-bottom:6px;">3. Field &amp; Home Prerequisites</div>
            <div class="m3-slide-card-text" style="color:{tokens['sub_text_fg']};">&bull; {_escape(b2)}</div>
          </div>
        </div>
        {local_card_html}
        """
    elif archetype in ("STEP_BY_STEP_PROCEDURE_4CARD", "GEAR_CHECKLIST_GRID") and len(bullets) >= 2:
        grid_items = []
        for idx_bp, bp in enumerate(bullets[:6]):
            c_style, c_anc, c_body, _ = _get_card_theme_spec(idx_bp)
            bp_str = str(bp)
            colon_idx = bp_str.find(":")
            badge_tag = (
                f'<span style="display:inline-block; background:{c_anc}; color:#FFFFFF; font-family:\'JetBrains Mono\',monospace; font-size:0.72rem; font-weight:700; padding:1px 7px; border-radius:6px; margin-right:6px;">STEP {idx_bp + 1}</span>'
                if archetype == "STEP_BY_STEP_PROCEDURE_4CARD"
                else f'<span style="color:{c_anc}; font-weight:800; margin-right:6px;">[✓]</span>'
            )
            if 0 < colon_idx < 52:
                anchor = bp_str[:colon_idx]
                rest = bp_str[colon_idx + 1 :].strip()
                grid_items.append(
                    f'<div class="m3-slide-card-item" style="{c_style}">'
                    f'<div class="m3-slide-card-anchor" style="color:{c_anc};">{badge_tag}{_escape(anchor)}</div>'
                    f'<div class="m3-slide-card-text" style="color:{c_body};">{_escape(rest)}</div></div>'
                )
            else:
                grid_items.append(
                    f'<div class="m3-slide-card-item" style="{c_style}">'
                    f'<div class="m3-slide-card-text" style="color:{c_body};">{badge_tag}{_escape(bp_str)}</div></div>'
                )
        left_cards_html = f'<div class="m3-slide-2col-grid">{"".join(grid_items)}</div>'
    elif archetype == "WORKED_EXAMPLE_TEMPLATE":
        fallback_fields = {}
        for i_b, bp in enumerate(bullets[:4]):
            bp_s = str(bp)
            c_idx = bp_s.find(":")
            if 0 < c_idx < 48:
                fallback_fields[bp_s[:c_idx].strip()] = bp_s[c_idx + 1 :].strip()
            else:
                fallback_fields[f"Step {i_b + 1}"] = bp_s
        we = slide.get("worked_example") or {
            "title": f"Worked Example — {req_label}",
            "fields": fallback_fields,
        }
        fields_html = "".join(
            f'<div class="m3-slide-card-item" style="padding:8px 12px; {card_style}"><span style="font-weight:700; color:{base_anc_color};">{_escape(k)}:</span> <span class="m3-slide-card-text" style="color:{base_body_color};">{_escape(v)}</span></div>'
            for k, v in (we.get("fields") or fallback_fields).items()
        )
        left_cards_html = f"""
        <div class="m3-chip m3-chip-gold" style="align-self:flex-start;">📋 {_escape(we.get("title") or "Sample Log & Template")}</div>
        {fields_html}
        """
    elif archetype == "SOCRATIC_CHECKPOINT_QUIZ":
        qz = slide.get("quiz_item") or {
            "scenario_prompt": bullets[0] if bullets else f"How should your patrol apply {req_label} safely in the field?",
            "options": bullets[1:4] if len(bullets) > 1 else [
                "Follow the step-by-step BSA pamphlet procedure and verify with your buddy.",
                "Rely on guesswork without checking field safety conditions.",
            ],
            "correct_answer": "Option A — Follow official BSA pamphlet procedure",
            "explanation": "Grounded in the official Scouts BSA Merit Badge Pamphlet and Guide to Safe Scouting.",
        }
        opts_html = "".join(
            f'<div class="m3-slide-card-item" style="{card_style}"><strong style="color:{base_anc_color};">Option {chr(65 + i)}:</strong> <span style="color:{base_body_color};">{_escape(opt)}</span></div>'
            for i, opt in enumerate(qz.get("options") or [])
        )
        ans_bg = "#064E3B" if tokens["is_studio"] else "#DCFCE7"
        ans_fg = "#4ADE80" if tokens["is_studio"] else "#15803D"
        left_cards_html = f"""
        <div class="m3-slide-card-item" style="background:{tokens['card_bg']}; border-color:{tokens['primary_hex']}; color:{tokens['text_fg']};">
          <div class="m3-slide-card-anchor" style="color:{tokens['primary_hex']};">❓ Patrol Scenario Challenge</div>
          <div class="m3-slide-card-text" style="color:{tokens['sub_text_fg']};">{_escape(qz.get("scenario_prompt") or "")}</div>
        </div>
        {opts_html}
        <div class="m3-slide-card-item" style="background:{ans_bg}; border-color:#15803D; color:{tokens['text_fg']};">
          <div class="m3-slide-card-anchor" style="color:{ans_fg};">✓ Verified Answer: {_escape(qz.get("correct_answer") or "")}</div>
          <div class="m3-slide-card-text" style="color:{tokens['sub_text_fg']};">{_escape(qz.get("explanation") or "")}</div>
        </div>
        """
    else:
        cards_list = []
        for idx_bp, bp in enumerate(bullets):
            c_style, c_anc, c_body, step_prefix = _get_card_theme_spec(idx_bp)
            bp_str = str(bp)
            colon_idx = bp_str.find(":")
            if 0 < colon_idx < 52:
                anchor = bp_str[:colon_idx]
                rest = bp_str[colon_idx + 1 :].strip()
                cards_list.append(
                    f'<div class="m3-slide-card-item" style="{c_style}">'
                    f'<div class="m3-slide-card-anchor" style="color:{c_anc};">{step_prefix}{_escape(anchor)}</div>'
                    f'<div class="m3-slide-card-text" style="color:{c_body};">{_escape(rest)}</div>'
                    f"</div>"
                )
            else:
                cards_list.append(
                    f'<div class="m3-slide-card-item" style="{c_style}"><div class="m3-slide-card-text" style="color:{c_body};">{step_prefix}{_escape(bp_str)}</div></div>'
                )
        left_cards_html = "".join(cards_list)

    vis_source_badge = ""
    if tokens["is_beautified"] and has_visual and not hide_visual_for_intro:
        src_lbl = str(slide.get("visual_source_label") or "")
        is_ai_hero = bool(slide.get("ai_hero_image_path")) or "EDGE Skill" in src_lbl
        if "NanoBanana" in src_lbl or "Nano Banana" in src_lbl:
            badge_txt = "🍌 NANO BANANA AI GRAPHIC"
        elif "WebImageSearch" in src_lbl or "Web Image" in src_lbl:
            badge_txt = "🌐 WEB IMAGE ARCHIVE"
        elif is_ai_hero:
            badge_txt = "✨ EDGE SKILL CONCEPT MAP"
        else:
            badge_txt = "📐 OFFICIAL PAMPHLET VISUAL"
        vis_source_badge = (
            f'<div style="align-self:flex-end; background:{tokens["badge_bg"]}; color:{tokens["badge_fg"]}; '
            f'font-size:0.68rem; font-weight:800; padding:3px 9px; border-radius:999px; border:1px solid {tokens["accent_hex"]};">'
            f"{_escape(badge_txt)}</div>"
        )

    right_frame_style = (
        f"background:#1E293B; border:2px solid {tokens['accent_hex']}; color:#F8FAFC;"
        if tokens["is_studio"]
        else (
            f"background:{tokens['card_bg']}; border:1.5px solid {tokens['accent_hex']};"
            if tokens["is_beautified"]
            else "background:#F8FAFC; border:1px solid #CBD5E1;"
        )
    )
    caption_color = "#E2E8F0" if tokens["is_studio"] else "#334155"

    if not has_visual or hide_visual_for_intro:
        body_html = f"""
        <div class="m3-slide-body-split" style="grid-template-columns:1fr;">
          <div class="m3-slide-left-zone">{left_cards_html}</div>
        </div>
        """
    elif archetype == "FULL_BLEED_IMAGE_EXPLAINER":
        cap_txt = bullets[0] if bullets else (slide.get("visual_caption") or title)
        body_html = f"""
        <div class="m3-slide-body-split" style="grid-template-columns:1fr;">
          <div class="m3-slide-right-visual" style="{right_frame_style}">
            {vis_source_badge}
            <img src="{diag_uri}" alt="{_escape(title)}" style="max-height:330px;" />
            <div class="m3-slide-visual-caption" style="font-size:0.92rem; color:{caption_color}; text-align:left; width:100%; padding:4px 8px;">{_escape(cap_txt)}</div>
          </div>
        </div>
        """
    else:
        cap_txt = slide.get("visual_caption") or title
        body_html = f"""
        <div class="m3-slide-body-split" style="grid-template-columns:1.15fr 0.85fr;">
          <div class="m3-slide-left-zone">{left_cards_html}</div>
          <div class="m3-slide-right-visual" style="{right_frame_style}">
            {vis_source_badge}
            <img src="{diag_uri}" alt="{_escape(cap_txt)}" style="max-height:270px;" />
            <div class="m3-slide-visual-caption" style="color:{caption_color};">{_escape(cap_txt)}</div>
          </div>
        </div>
        """

    safety_warning = slide.get("safety_warning")
    safety_html = (
        f'<div class="m3-slide-safety-bar">⚠️ Guide to Safe Scouting: {_escape(safety_warning)}</div>'
        if safety_warning
        else ""
    )

    header_badge_html = (
        f'<div style="margin-top:4px;"><span style="display:inline-block; background:{tokens["badge_bg"]}; color:{tokens["badge_fg"]}; '
        f'border:1px solid {tokens["accent_hex"]}; font-size:0.72rem; font-weight:700; padding:2px 10px; border-radius:999px;">'
        f'🎨 {_escape(tokens["tier"])} &bull; {_escape(callout_badge or vis_theme)}</span></div>'
        if tokens["is_beautified"]
        else ""
    )
    top_ribbon_style = f"border-top:6px solid {tokens['accent_hex']}; background:{tokens['header_bg']};" if tokens["is_beautified"] else ""
    title_hdr_color = "#F8FAFC" if tokens["is_studio"] else tokens["primary_hex"]

    return _clean_html(
        f"""
        <div class="m3-widescreen-slide" style="background:{tokens['stage_bg']}; border:{tokens['stage_border']};">
          <div class="m3-slide-header-band" style="{top_ribbon_style}">
            <div class="m3-slide-header-title" style="color:{title_hdr_color};">{_escape(title)}</div>
            {header_badge_html}
          </div>
          {req_strip_html}
          {body_html}
          {safety_html}
          <div class="m3-slide-footer-strip" style="color:{tokens['footer_color']}; background:transparent;">
            <span>Scouts BSA {_escape(badge_name)} Merit Badge &bull; {_escape(tokens['tier'])} Mode</span>
            <span>Slide {slide_idx + 2} of {total_slides} &bull; {_escape(req_label)}</span>
          </div>
        </div>
        """
    )


def _render_triage_column(col_title: str, chip_class: str, items: List[Dict[str, Any]]) -> str:
    """Renders a 3-column Requirement Triage card column with zero 4-space indentation."""
    card_parts: List[str] = []
    for r in items:
        safety_txt = r.get("safety_callout")
        safety_html = (
            f'<div style="font-size:0.76rem; color:#CE1126; font-weight:600; margin-top:4px;">⚠️ {_escape(safety_txt)}</div>'
            if safety_txt
            else ""
        )
        card_parts.append(
            f'<div class="m3-req-node-card">'
            f'<div><span class="m3-chip m3-chip-primary" style="font-size:0.72rem; padding:2px 8px;">Requirement {_escape(r.get("req_number"))}</span></div>'
            f'<div style="font-size:0.85rem; font-weight:600; color:#0F172A; margin-top:6px;">{_escape(r.get("req_text"))}</div>'
            f"{safety_html}"
            f"</div>"
        )
    cards_html = "".join(card_parts)
    return _clean_html(
        f"""
        <div class="m3-triage-col">
          <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:12px;">
            <span style="font-family:'Roboto Slab',serif; font-size:0.96rem; font-weight:700; color:#003F87;">{col_title}</span>
            <span class="m3-chip {chip_class}">{len(items)}</span>
          </div>
          {cards_html}
        </div>
        """
    )


def _sync_from_main_dropdown() -> None:
    st.session_state["selected_badge_name"] = st.session_state["main_badge_dropdown"]
    st.session_state["active_slide_idx"] = -1


def _rebuild_pptx_in_place(
    result: Dict[str, Any],
    slides: List[Dict[str, Any]],
    badge_name: str,
    counselor_name: str,
    troop_affiliation: str,
    location_or_zip: Optional[str],
    email_address: Optional[str],
    phone_number: Optional[str],
    logo_path: Optional[str],
) -> None:
    """Rebuilds the downloadable .pptx file in-place whenever a slide is modified."""
    try:
        c_info_obj = CounselorTitleSlideInfo(
            counselor_name=counselor_name,
            troop_affiliation=troop_affiliation,
            location_or_zip=location_or_zip if location_or_zip else None,
            email_address=email_address if email_address else None,
            phone_number=phone_number if phone_number else None,
            custom_troop_logo_path=logo_path,
        )
        s_specs = [SlideSpec(**sl) for sl in slides]
        generate_bsa_slide_deck_pptx(
            PowerPointBuildRequest(
                badge_name=badge_name,
                slides=s_specs,
                counselor_info=c_info_obj,
                output_path=result.get("output_path"),
                hitl_confirmation_token=result.get("hitl_confirmation_token"),
            )
        )
    except Exception:
        pass


def _extract_catalog_items(raw_catalog: Any, default_req: str = "") -> List[Dict[str, Any]]:
    """Normalizes a badge image catalog (dict with 'images' or list of dicts/strings) into a clean List[Dict]."""
    if isinstance(raw_catalog, dict):
        items = raw_catalog.get("images") or raw_catalog.get("results") or raw_catalog.get("badge_catalog") or []
    elif isinstance(raw_catalog, list):
        items = raw_catalog
    else:
        items = []

    normalized: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            p = item.get("image_path")
            if p and isinstance(p, str):
                normalized.append(item)
        elif isinstance(item, str) and os.path.exists(item):
            normalized.append({
                "image_path": item,
                "title": os.path.basename(item),
                "description": f"Slide visual asset ({os.path.basename(item)})",
                "source_type": "OFFICIAL_PAMPHLET_FIGURE",
                "req_number": default_req,
            })
    return normalized


def _apply_image_entry_to_slide(
    curr_s: Dict[str, Any],
    entry: Dict[str, Any],
    result: Dict[str, Any],
    slides: List[Dict[str, Any]],
    badge_name: str,
    counselor_name: str,
    troop_affiliation: str,
    location_or_zip: Optional[str],
    email_address: Optional[str],
    phone_number: Optional[str],
    logo_path: Optional[str],
) -> None:
    """Applies a catalog/web/AI image entry to a slide, persists it in the badge catalog, auto-adjusts layout, and rebuilds .pptx."""
    entry = register_image_in_badge_catalog(badge_name, entry)
    img_path = entry.get("image_path")
    if not img_path or not os.path.exists(img_path):
        return
    curr_s["diagram_path"] = img_path
    curr_s["ai_hero_image_path"] = None
    curr_s["visual_caption"] = entry.get("title") or entry.get("description") or curr_s.get("title")
    curr_s["visual_source_label"] = entry.get("source_label") or entry.get("attribution") or entry.get("source_type") or "Badge Image Catalog"
    # If slide was previously full-width text (CONCEPT_TEXT_SLIDE), automatically adjust layout to split visual!
    if curr_s.get("archetype") in ("CONCEPT_TEXT_SLIDE", "SOURCES_AND_REFERENCES", "REQUIREMENTS_TRIAGE_MATRIX"):
        curr_s["archetype"] = "SPLIT_VISUAL_EXPLAINER"
    avail = _extract_catalog_items(curr_s.get("available_images") or [], default_req=str(curr_s.get("req_number") or ""))
    if not any(os.path.abspath(str(a.get("image_path", ""))) == os.path.abspath(img_path) for a in avail if a.get("image_path")):
        avail.append(entry)
    curr_s["available_images"] = avail
    cat_res = get_badge_image_catalog(badge_name, storyboard=result.get("storyboard"))
    result["badge_image_catalog"] = _extract_catalog_items(cat_res)
    _rebuild_pptx_in_place(
        result=result,
        slides=slides,
        badge_name=badge_name,
        counselor_name=counselor_name,
        troop_affiliation=troop_affiliation,
        location_or_zip=location_or_zip,
        email_address=email_address,
        phone_number=phone_number,
        logo_path=logo_path,
    )


@st.dialog("🖼️ Merit Badge Image Catalog & AI Image Studio", width="large")
def _open_image_studio_dialog(
    res_badge: str,
    active_idx: int,
    curr_s: Dict[str, Any],
    result: Dict[str, Any],
    slides: List[Dict[str, Any]],
    counselor_name: str,
    troop_affiliation: str,
    location_or_zip: Optional[str],
    email_address: Optional[str],
    phone_number: Optional[str],
    logo_path: Optional[str],
) -> None:
    """Popup modal catalog/carousel to browse cached badge images, search web images, or generate Nano Banana AI graphics."""
    slide_num = active_idx + 2
    req_num = str(curr_s.get("req_number") or (active_idx + 1))
    slide_title = str(curr_s.get("title") or "")
    clean_topic = clean_slide_topic_boilerplate(slide_title)

    st.markdown(
        f"**Active Target:** Slide {slide_num} (`Req {req_num}` — *{slide_title}*) • **{res_badge} Merit Badge**\n\n"
        "Select any cached image below to place on this slide (automatically adjusting full-width text slides to a split visual layout), "
        "search Wikipedia & Wikimedia Commons via **`WebImageSearchAgent`**, create & verify a custom concept illustration via **`NanoBananaImageAgent`**, "
        "or upload a local image file from your computer."
    )

    dlg_tab_catalog, dlg_tab_web, dlg_tab_ai, dlg_tab_upload = st.tabs([
        "🗂️ 1. Badge Image Catalog & Carousel",
        "🌐 2. Web Image Search Agent",
        "🍌 3. Nano Banana AI Image Generator",
        "📁 4. File Upload",
    ])

    with dlg_tab_catalog:
        raw_cat = get_badge_image_catalog(res_badge, storyboard=result.get("storyboard"))
        catalog_items = _extract_catalog_items(raw_cat, default_req=req_num)
        hdr_c1, hdr_c2 = st.columns([3.0, 1.4])
        with hdr_c1:
            st.caption(
                f"Showing **{len(catalog_items)}** cached images for **{res_badge}**. "
                "Official pamphlet figures and any Web, AI, or Uploaded images you apply are cached here for instant reuse."
            )
        with hdr_c2:
            if st.button(
                "🗑️ Clear Web/AI Cache",
                key=f"dlg_purge_cache_{active_idx}",
                type="secondary",
                use_container_width=True,
                help="Remove user-added Nano Banana AI or Web Search images while keeping pre-generated/auto hero graphics, official BSA pamphlet figures, and uploaded files.",
            ):
                purge_res = purge_cached_web_and_ai_images(res_badge)
                st.session_state.pop(f"_last_web_search_{active_idx}", None)
                refreshed = get_badge_image_catalog(res_badge, storyboard=result.get("storyboard"))
                result["badge_image_catalog"] = _extract_catalog_items(refreshed, default_req=req_num)
                st.session_state[f"_purge_notice_{active_idx}"] = (
                    f"Cleared {purge_res.get('removed_files', 0)} user-added Web/AI image(s) for {res_badge}. Hero graphics & official figures preserved."
                )
                st.rerun()

        purge_notice = st.session_state.pop(f"_purge_notice_{active_idx}", None)
        if purge_notice:
            st.success(f"✅ {purge_notice}")

        if not catalog_items:
            st.info(f"No cached images found yet for {res_badge}. Use the Web Search, Nano Banana AI, or File Upload tabs to add images.")
        else:
            curr_diag = curr_s.get("diagram_path")
            cols = st.columns(2, gap="medium")
            for idx_entry, entry in enumerate(catalog_items):
                img_p = entry.get("image_path")
                if not img_p or not os.path.exists(img_p):
                    continue
                is_active_img = bool(curr_diag and os.path.exists(curr_diag) and os.path.abspath(curr_diag) == os.path.abspath(img_p))
                with cols[idx_entry % 2]:
                    with st.container(border=True):
                        st.image(img_p, use_container_width=True)
                        src_type = str(entry.get("source_type") or "CATALOG")
                        title_str = str(entry.get("title") or "Slide Visual")
                        desc_str = str(entry.get("description") or "")
                        req_tag = str(entry.get("req_number") or "")
                        st.markdown(f"**{title_str}**  \n`{src_type}` • Req `{req_tag}`")
                        st.caption(desc_str)
                        btn_lbl = "✓ Currently Active on Slide" if is_active_img else f"✅ Use on Slide {slide_num}"
                        if st.button(
                            btn_lbl,
                            key=f"dlg_cat_use_{idx_entry}_{entry.get('image_id', idx_entry)}",
                            type="secondary" if is_active_img else "primary",
                            use_container_width=True,
                        ):
                            _apply_image_entry_to_slide(
                                curr_s=curr_s,
                                entry=entry,
                                result=result,
                                slides=slides,
                                badge_name=res_badge,
                                counselor_name=counselor_name,
                                troop_affiliation=troop_affiliation,
                                location_or_zip=location_or_zip,
                                email_address=email_address,
                                phone_number=phone_number,
                                logo_path=logo_path,
                            )
                            st.session_state[f"img_rev_{active_idx}"] = st.session_state.get(f"img_rev_{active_idx}", 0) + 1
                            st.rerun()

    with dlg_tab_web:
        st.markdown("##### 🌐 `WebImageSearchAgent` — Wikipedia & Wikimedia Commons Live Image Search")
        st.caption(
            "Enter any visual topic (for example, `'boy scout in a canoe'`, `'ankle splint bandage'`, or `'camp stove'`). "
            "Returns up to 16–24 real photographs and illustrations from Wikimedia Commons and Wikipedia."
        )
        q_col1, q_col2 = st.columns([3.2, 1.0])
        default_q = f"{res_badge} {clean_topic}".strip()
        with q_col1:
            web_query = st.text_input(
                "Search Query for Slide Visuals",
                value=default_q,
                placeholder="e.g., boy scout in a canoe",
                key=f"dlg_web_q_{active_idx}",
                help="Type any subject you want to find on Wikipedia / Wikimedia Commons.",
            )
        with q_col2:
            max_web_res = st.selectbox(
                "Max Results",
                options=[12, 16, 24],
                index=1,
                key=f"dlg_web_max_{active_idx}",
            )

        if st.button("🔎 Search Wikipedia & Wikimedia Commons", key=f"dlg_web_btn_{active_idx}", type="primary", use_container_width=True):
            with st.spinner(f"WebImageSearchAgent searching Wikipedia & Wikimedia Commons for '{web_query}'..."):
                web_res = search_web_images_for_slide(
                    badge_name=res_badge,
                    req_number=req_num,
                    slide_title=slide_title,
                    search_query=web_query,
                    bullet_points=curr_s.get("bullet_points") or [],
                    max_results=int(max_web_res),
                )
                st.session_state[f"_last_web_search_{active_idx}"] = web_res

        last_web = st.session_state.get(f"_last_web_search_{active_idx}")
        if last_web and last_web.get("results"):
            results_list = last_web["results"]
            st.success(
                f"Showing **{len(results_list)}** Wikipedia / Wikimedia Commons images for **`{last_web.get('query_used', web_query)}`** "
                "(`$0.00 USD`). Click **Apply & Cache to Slide** on any image you want to use:"
            )
            w_cols = st.columns(3, gap="small")
            for w_idx, w_entry in enumerate(results_list):
                w_path = w_entry.get("image_path")
                with w_cols[w_idx % 3]:
                    with st.container(border=True):
                        if w_path and os.path.exists(w_path):
                            st.image(w_path, use_container_width=True)
                        st.markdown(f"**{w_entry.get('title', 'Web Visual')}**")
                        st.caption(w_entry.get("description", ""))
                        if st.button(
                            f"✅ Apply & Cache to Slide {slide_num}",
                            key=f"dlg_web_use_{active_idx}_{w_idx}_{w_entry.get('image_id', w_idx)}",
                            type="primary",
                            use_container_width=True,
                        ):
                            _apply_image_entry_to_slide(
                                curr_s=curr_s,
                                entry=w_entry,
                                result=result,
                                slides=slides,
                                badge_name=res_badge,
                                counselor_name=counselor_name,
                                troop_affiliation=troop_affiliation,
                                location_or_zip=location_or_zip,
                                email_address=email_address,
                                phone_number=phone_number,
                                logo_path=logo_path,
                            )
                            st.session_state[f"img_rev_{active_idx}"] = st.session_state.get(f"img_rev_{active_idx}", 0) + 1
                            st.rerun()

    with dlg_tab_ai:
        st.markdown("##### 🍌 `NanoBananaImageAgent` — Verified Concept-Illustrative AI Graphic Generator")
        st.caption(
            "Generates a pure visual illustration of the subject described in your prompt in your chosen artistic style "
            "(with zero prompt text printed inside the image), and runs **post-generation prompt & style alignment verification**. "
            "Requires explicit FinOps cost consent (`$0.08 USD`)."
        )
        style_options = list(NANO_BANANA_VISUAL_STYLES)
        col_st1, col_st2 = st.columns(2)
        with col_st1:
            selected_style = st.selectbox(
                "1. Visual Illustration Style",
                style_options,
                index=0,
                key=f"dlg_nb_style_{active_idx}",
                help="Choose Auto (Content-Aware Mix) or a specific visual style.",
            )
        with col_st2:
            humans_mode_label = st.selectbox(
                "2. Human Presence & Uniform Directive",
                [
                    "✨ Auto-Detect (Content-Aware Mix)",
                    "👕 Include Humans (Adult Scouts BSA Uniforms)",
                    "🧰 No Humans (Pure Equipment / Environment)",
                ],
                index=0,
                key=f"dlg_nb_humans_{active_idx}",
                help="Controls whether Nano Banana applies the Adult Scouts BSA Field Uniform directive or the Zero-Humans / Pure Equipment & Environment directive.",
            )
        humans_mode_val: Any = (
            "auto"
            if "Auto-Detect" in humans_mode_label
            else (True if "Include Humans" in humans_mode_label else False)
        )
        preview_cfg = resolve_content_aware_visual_config(
            badge_name=res_badge,
            slide_title=slide_title,
            req_number=req_num,
            bullet_points=curr_s.get("bullet_points") or [],
            custom_prompt="",
            visual_style=selected_style,
            include_humans=humans_mode_val,
        )
        default_prompt = preview_cfg["enriched_subject"]
        custom_prompt = st.text_area(
            "3. Visual Subject / Scene to Illustrate (No words will be printed inside the image)",
            value=default_prompt,
            placeholder="e.g., A Boy Scout paddling a red canoe across a calm mountain lake surrounded by pine trees",
            height=85,
            key=f"dlg_nb_prompt_{active_idx}",
        )
        live_cfg = resolve_content_aware_visual_config(
            badge_name=res_badge,
            slide_title=slide_title,
            req_number=req_num,
            bullet_points=curr_s.get("bullet_points") or [],
            custom_prompt=custom_prompt,
            visual_style=selected_style,
            include_humans=humans_mode_val,
        )
        dir_lbl = (
            "👕 Adult Scouts BSA Field Uniforms"
            if live_cfg["include_humans"]
            else "🧰 Zero Humans (Pure Equipment / Environment)"
        )
        st.caption(
            f"🧠 **Content-Aware Resolution:** {dir_lbl} • **Effective Style:** `{live_cfg['effective_style']}`"
        )

        cost_est = estimate_nano_banana_image_cost(
            badge_name=res_badge,
            req_number=req_num,
            slide_title=slide_title,
            custom_prompt=custom_prompt,
            style_preset=live_cfg["effective_style"],
        )
        consent_txt = cost_est.get("consent_message") or cost_est.get("consent_prompt_text") or ""
        st.markdown(
            _clean_html(
                f"""
                <div style="background:#FFFBEB; border:1.5px solid #F59E0B; border-radius:12px; padding:10px 14px; margin:8px 0; color:#78350F; font-size:0.83rem;">
                  <div style="font-weight:700; font-size:0.88rem; margin-bottom:3px;">
                    💰 FinOps AI Image + Verification Cost Estimate: <strong>${cost_est['estimated_cost_usd']:.2f} USD</strong> ({cost_est['model_id']})
                  </div>
                  <div>{consent_txt}</div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )
        user_consented = st.checkbox(
            f"✅ I consent to the estimated ${cost_est['estimated_cost_usd']:.2f} USD cost to generate & verify this '{live_cfg['effective_style']}' illustration and cache it for {res_badge}.",
            value=False,
            key=f"dlg_nb_consent_{active_idx}",
        )
        if st.button(
            f"🍌 Generate, Verify & Apply '{live_cfg['effective_style']}' to Slide {slide_num} (${cost_est['estimated_cost_usd']:.2f})",
            key=f"dlg_nb_gen_{active_idx}",
            type="primary",
            disabled=not user_consented,
            use_container_width=True,
        ):
            with st.spinner(f"NanoBananaImageAgent generating & verifying '{live_cfg['effective_style']}' illustration for Slide {slide_num}..."):
                nb_res = generate_nano_banana_slide_image(
                    badge_name=res_badge,
                    req_number=req_num,
                    slide_title=slide_title,
                    bullet_points=curr_s.get("bullet_points") or [],
                    custom_prompt=custom_prompt,
                    style_preset=selected_style,
                    include_humans=humans_mode_val,
                    accent_palette_key=str(curr_s.get("accent_palette_key") or "NAVY_GOLD"),
                    user_consented=user_consented,
                )
                nb_entry = nb_res.get("entry") or nb_res.get("image_entry")
                if nb_res.get("status") == "SUCCESS" and nb_entry:
                    align_info = nb_res.get("prompt_alignment") or {}
                    _apply_image_entry_to_slide(
                        curr_s=curr_s,
                        entry=nb_entry,
                        result=result,
                        slides=slides,
                        badge_name=res_badge,
                        counselor_name=counselor_name,
                        troop_affiliation=troop_affiliation,
                        location_or_zip=location_or_zip,
                        email_address=email_address,
                        phone_number=phone_number,
                        logo_path=logo_path,
                    )
                    st.session_state[f"_last_nb_align_{active_idx}"] = align_info.get("verification_summary")
                    st.session_state[f"img_rev_{active_idx}"] = st.session_state.get(f"img_rev_{active_idx}", 0) + 1
                    st.rerun()
                else:
                    st.warning(nb_res.get("message") or "User consent is required before generating AI images.")

    with dlg_tab_upload:
        st.markdown("##### 📁 Upload Local Image File (`$0.00 USD` — Zero Token Cost)")
        st.caption(
            "Have your own photograph, troop campout snapshot, diagram, or illustration on your computer? "
            "Upload it below (`PNG`, `JPG`, `JPEG`, `WEBP`, or `GIF`) to cache it in this Merit Badge's catalog and apply it immediately to this slide."
        )
        uploaded_file = st.file_uploader(
            "1. Choose a local image file",
            type=["png", "jpg", "jpeg", "webp", "gif"],
            key=f"dlg_upload_file_{active_idx}",
        )
        default_up_title = ""
        if uploaded_file is not None:
            raw_stem = os.path.splitext(uploaded_file.name)[0]
            default_up_title = re.sub(r"[_\-]+", " ", raw_stem).strip().title()
        up_col1, up_col2 = st.columns(2)
        with up_col1:
            up_title = st.text_input(
                "2. Image Title / Slide Caption (Optional)",
                value=default_up_title,
                placeholder="e.g., Troop 19 First-Aid Kit Inspection",
                key=f"dlg_upload_title_{active_idx}",
            )
        with up_col2:
            up_desc = st.text_input(
                "3. Catalog Description (Optional)",
                value="",
                placeholder="e.g., Local photograph uploaded by Counselor",
                key=f"dlg_upload_desc_{active_idx}",
            )
        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            st.image(file_bytes, caption=f"Preview: {uploaded_file.name} ({max(1, len(file_bytes) // 1024)} KB • $0.00 USD)", width=320)
            if st.button(
                f"📁 Upload, Cache & Apply '{uploaded_file.name}' to Slide {slide_num} ($0.00 USD)",
                key=f"dlg_upload_btn_{active_idx}",
                type="primary",
                use_container_width=True,
            ):
                up_res = upload_custom_slide_image(
                    badge_name=res_badge,
                    image_data=file_bytes,
                    filename=uploaded_file.name,
                    title=up_title,
                    description=up_desc,
                    req_number=req_num,
                    slide_title=slide_title,
                )
                up_entry = up_res.get("entry") or up_res.get("image_entry")
                if up_res.get("status") == "SUCCESS" and up_entry:
                    _apply_image_entry_to_slide(
                        curr_s=curr_s,
                        entry=up_entry,
                        result=result,
                        slides=slides,
                        badge_name=res_badge,
                        counselor_name=counselor_name,
                        troop_affiliation=troop_affiliation,
                        location_or_zip=location_or_zip,
                        email_address=email_address,
                        phone_number=phone_number,
                        logo_path=logo_path,
                    )
                    st.session_state[f"img_rev_{active_idx}"] = st.session_state.get(f"img_rev_{active_idx}", 0) + 1
                    st.rerun()
                else:
                    st.error(up_res.get("message") or "Could not process uploaded image file.")



def main() -> None:
    """Renders the Google Material 3 Expressive Streamlit Counselor Workbench."""
    st.set_page_config(
        page_title="Scouts BSA Merit Badge Counselor Workbench",
        page_icon="⚜️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ==========================================================================
    # MATERIAL 3 EXPRESSIVE CSS INJECTION
    # ==========================================================================
    st.markdown(
        _clean_html(
            f"""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Roboto+Slab:wght@600;700;800&display=swap');

            :root {{
              --md-sys-color-primary: #003F87;
              --md-sys-color-primary-container: #D6E3FF;
              --md-sys-color-on-primary-container: #001B3E;
              --md-sys-color-action-blue: #005AE0;
              --md-sys-color-secondary: #4B5320;
              --md-sys-color-secondary-container: #E2EDC8;
              --md-sys-color-on-secondary-container: #151E00;
              --md-sys-color-tertiary: #CE1126;
              --md-sys-color-tertiary-container: #FFDAD6;
              --md-sys-color-on-tertiary-container: #410004;
              --md-sys-color-gold-bright: #F4C430;
              --md-sys-color-gold-container: #FEF3C7;
              --md-sys-color-on-gold-container: #451A03;
              --md-sys-color-surface: #F8FAFC;
              --md-sys-color-surface-container-low: #F1F5F9;
              --md-sys-color-surface-container: #E8EEF5;
              --md-sys-color-on-surface: #0F172A;
              --md-sys-color-on-surface-variant: #475569;
              --md-sys-color-outline: #CBD5E1;
              --md-sys-color-outline-variant: #E2E8F0;
            }}

            header[data-testid="stHeader"] {{
              background: transparent !important;
            }}

            .block-container {{
              padding-top: 3.6rem !important;
              padding-bottom: 2.5rem !important;
              max-width: 1680px !important;
            }}

            /* Top App Bar */
            .m3-top-bar {{
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 16px;
              padding: 16px 22px;
              background: #FFFFFF;
              border-radius: 20px;
              border: 1px solid var(--md-sys-color-outline-variant);
              box-shadow: 0 2px 8px -2px rgba(15, 23, 42, 0.06);
              margin-top: 6px;
              margin-bottom: 14px;
            }}
            .m3-brand-cluster {{
              display: flex;
              align-items: center;
              gap: 14px;
            }}
            .m3-brand-emblem {{
              width: 44px;
              height: 44px;
              border-radius: 14px;
              background: var(--md-sys-color-primary);
              color: var(--md-sys-color-gold-bright);
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 22px;
              font-weight: 800;
            }}
            .m3-brand-titles h1 {{
              font-family: 'Roboto Slab', Georgia, serif;
              font-size: 1.30rem !important;
              font-weight: 700 !important;
              color: var(--md-sys-color-primary) !important;
              margin: 0 !important;
              padding: 2px 0 0 0 !important;
              line-height: 1.3 !important;
            }}
            .m3-brand-subtitle {{
              font-family: 'Plus Jakarta Sans', sans-serif;
              font-size: 0.80rem;
              color: var(--md-sys-color-on-surface-variant);
              font-weight: 500;
            }}

            /* Sidebar Section Headers (High-Contrast BSA Navy & Gold Pill for both Light & Dark Mode) */
            .m3-sidebar-card-hdr {{
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 8px;
              margin: 6px 0 12px 0;
              padding: 10px 14px;
              background: linear-gradient(135deg, #002B5E 0%, #003F87 100%);
              border: 1px solid rgba(255, 255, 255, 0.22);
              border-bottom: 3px solid #D4AF37;
              border-radius: 12px;
              box-shadow: 0 2px 6px rgba(0, 0, 0, 0.16);
            }}
            .m3-sidebar-card-title {{
              font-family: 'Roboto Slab', serif;
              font-size: 0.94rem;
              font-weight: 700;
              color: #FFFFFF !important;
            }}

            /* Chips */
            .m3-chip {{
              display: inline-flex;
              align-items: center;
              gap: 6px;
              padding: 5px 12px;
              border-radius: 9999px;
              font-size: 0.75rem;
              font-weight: 700;
            }}
            .m3-chip-primary {{
              background: var(--md-sys-color-primary-container);
              color: var(--md-sys-color-on-primary-container);
            }}
            .m3-chip-secondary {{
              background: var(--md-sys-color-secondary-container);
              color: var(--md-sys-color-on-secondary-container);
            }}
            .m3-chip-eagle {{
              background: var(--md-sys-color-tertiary-container);
              color: var(--md-sys-color-on-tertiary-container);
            }}
            .m3-chip-gold {{
              background: var(--md-sys-color-gold-container);
              color: var(--md-sys-color-on-gold-container);
            }}

            /* Hero Summary Banner */
            .m3-hero-banner {{
              background: linear-gradient(135deg, #002B5E 0%, #003F87 60%, #0052A5 100%);
              border-bottom: 4px solid #D4AF37;
              color: #FFFFFF;
              border-radius: 26px;
              padding: 22px 28px;
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 20px;
              flex-wrap: wrap;
              box-shadow: 0 10px 28px -6px rgba(0, 63, 135, 0.16);
              margin-bottom: 16px;
            }}
            .m3-hero-kicker {{
              font-size: 0.76rem;
              font-weight: 700;
              text-transform: uppercase;
              letter-spacing: 0.06em;
              color: #F4C430;
            }}
            .m3-hero-title {{
              font-family: 'Roboto Slab', serif;
              font-size: 1.65rem;
              font-weight: 700;
              color: #FFFFFF;
              line-height: 1.2;
              margin: 2px 0;
            }}
            .m3-hero-meta {{
              font-size: 0.86rem;
              color: #DBEAFE;
            }}
            .m3-hero-kpis {{
              display: flex;
              gap: 12px;
            }}
            .m3-kpi-pill {{
              background: rgba(255, 255, 255, 0.13);
              border: 1px solid rgba(255, 255, 255, 0.24);
              border-radius: 14px;
              padding: 10px 18px;
              text-align: center;
              min-width: 115px;
            }}
            .m3-kpi-value {{
              font-family: 'Roboto Slab', serif;
              font-size: 1.30rem;
              font-weight: 700;
              color: #FFFFFF;
            }}
            .m3-kpi-label {{
              font-size: 0.70rem;
              text-transform: uppercase;
              letter-spacing: 0.04em;
              color: #DBEAFE;
            }}

            /* 16:9 Widescreen Slide Stage */
            .m3-widescreen-slide {{
              background: #FFFFFF;
              border-radius: 20px;
              border: 2px solid var(--md-sys-color-outline);
              box-shadow: 0 18px 40px -10px rgba(0, 63, 135, 0.15);
              overflow: hidden;
              display: flex;
              flex-direction: column;
              min-height: 510px;
              height: auto;
              justify-content: space-between;
              margin-bottom: 14px;
              box-sizing: border-box;
            }}
            .m3-slide-header-band {{
              background: transparent;
              color: var(--md-sys-color-primary);
              padding: 16px 24px 6px 24px;
              text-align: center;
            }}
            .m3-slide-header-title {{
              font-family: 'Plus Jakarta Sans', sans-serif;
              font-size: 1.48rem;
              font-weight: 800;
              color: var(--md-sys-color-primary);
              text-align: center;
              overflow-wrap: break-word;
              word-break: break-word;
            }}
            .m3-slide-req-strip {{
              background: #FFFFFF;
              margin: 4px 24px 0 24px;
              padding: 10px 16px;
              border: 2px solid var(--md-sys-color-primary);
              border-radius: 12px;
              font-size: 0.92rem;
              line-height: 1.42;
              color: var(--md-sys-color-on-surface);
              text-align: left;
              overflow-wrap: break-word;
              word-break: break-word;
              box-sizing: border-box;
            }}
            .m3-slide-body-split {{
              display: grid;
              gap: 18px;
              padding: 14px 24px 18px 24px;
              flex: 1;
              align-items: stretch;
              box-sizing: border-box;
            }}
            .m3-slide-left-zone {{
              display: flex;
              flex-direction: column;
              gap: 9px;
              text-align: left;
              min-width: 0;
            }}
            .m3-slide-card-item {{
              background: var(--md-sys-color-surface-container-low);
              border: 1.5px solid var(--md-sys-color-outline);
              border-radius: 12px;
              padding: 11px 14px;
              text-align: left;
              overflow-wrap: break-word;
              word-break: break-word;
              box-sizing: border-box;
              min-width: 0;
            }}
            .m3-slide-card-anchor {{
              font-weight: 700;
              color: var(--md-sys-color-primary);
              font-size: 0.96rem;
              margin-bottom: 3px;
              text-align: left;
              overflow-wrap: break-word;
              word-break: break-word;
            }}
            .m3-slide-card-text {{
              font-size: 0.91rem;
              color: var(--md-sys-color-on-surface);
              line-height: 1.44;
              text-align: left;
              overflow-wrap: break-word;
              word-break: break-word;
            }}
            .m3-slide-2col-grid {{
              display: grid;
              grid-template-columns: 1fr 1fr;
              gap: 12px;
              width: 100%;
              min-width: 0;
            }}
            .m3-slide-right-visual {{
              background: var(--md-sys-color-surface-container-low);
              border: 1px solid var(--md-sys-color-outline);
              border-radius: 14px;
              padding: 12px;
              display: flex;
              flex-direction: column;
              align-items: center;
              justify-content: center;
              gap: 8px;
            }}
            .m3-slide-right-visual img {{
              width: 100%;
              max-height: 330px;
              object-fit: contain;
              border-radius: 8px;
              background: #FFFFFF;
            }}
            .m3-slide-visual-caption {{
              font-size: 0.76rem;
              font-weight: 600;
              color: var(--md-sys-color-on-surface-variant);
              text-align: center;
            }}
            .m3-slide-safety-bar {{
              margin: 0 24px 12px;
              padding: 10px 16px;
              border-radius: 10px;
              background: var(--md-sys-color-tertiary-container);
              color: var(--md-sys-color-on-tertiary-container);
              font-size: 0.82rem;
              font-weight: 600;
              text-align: left;
            }}
            .m3-slide-footer-strip {{
              background: var(--md-sys-color-surface-container);
              padding: 8px 24px;
              font-size: 0.74rem;
              color: var(--md-sys-color-on-surface-variant);
              display: flex;
              justify-content: space-between;
            }}

            /* Speaker Notes & Trace Cards */
            .m3-speaker-notes-card {{
              background: #FFFFFF;
              border-radius: 14px;
              border: 1px solid var(--md-sys-color-outline-variant);
              padding: 15px 18px;
              box-shadow: 0 2px 8px -2px rgba(15, 23, 42, 0.05);
            }}
            .m3-cue-tag {{
              display: inline-block;
              padding: 2px 8px;
              border-radius: 6px;
              font-family: 'JetBrains Mono', monospace;
              font-size: 0.72rem;
              font-weight: 700;
              margin-right: 6px;
              background: var(--md-sys-color-primary-container);
              color: var(--md-sys-color-primary);
            }}
            .m3-trace-item {{
              padding: 9px 11px;
              border-radius: 12px;
              background: #F8FAFC !important;
              border: 1px solid #CBD5E1 !important;
              font-size: 0.78rem;
              margin-bottom: 8px;
              color: #0F172A !important;
            }}
            .m3-trace-top {{
              display: flex;
              align-items: center;
              justify-content: space-between;
              font-weight: 700;
              color: #003F87 !important;
              margin-bottom: 2px;
            }}
            .m3-trace-meta {{
              font-family: 'JetBrains Mono', monospace;
              font-size: 0.68rem;
              color: #4B5320 !important;
            }}
            .m3-trace-desc {{
              color: #334155 !important;
              font-size: 0.74rem;
            }}

            /* Triage Cards */
            .m3-triage-col {{
              background: #FFFFFF;
              border-radius: 18px;
              border: 1px solid var(--md-sys-color-outline-variant);
              padding: 16px;
              box-shadow: 0 2px 8px -2px rgba(15, 23, 42, 0.05);
            }}
            .m3-req-node-card {{
              padding: 12px;
              border-radius: 12px;
              background: var(--md-sys-color-surface-container-low);
              border: 1px solid var(--md-sys-color-outline);
              margin-bottom: 10px;
              text-align: left;
            }}

            .stButton>button[kind="primary"],
            .stDownloadButton>button[kind="primary"] {{
              background-color: {ScoutsBSAPalette.NAVY_BLUE_HEX};
              color: white;
              font-weight: 700;
              border-radius: 999px;
              border: none;
            }}
            .stButton>button[kind="primary"]:hover,
            .stDownloadButton>button[kind="primary"]:hover {{
              background-color: {ScoutsBSAPalette.ACTION_BLUE_HEX};
              color: white;
            }}
            </style>
            """
        ),
        unsafe_allow_html=True,
    )

    # ==========================================================================
    # CATALOG DATAFRAME & SESSION STATE INITIALIZATION
    # ==========================================================================
    all_badges_rows = [
        {
            "Badge Name": b["badge_name"],
            "Category": b["category"],
            "Eagle Required": bool(b["is_eagle_required"]),
            "Official Pamphlet PDF": b["pamphlet_pdf_url"],
            "Resource Guide": b["drg_url"],
        }
        for b in OFFICIAL_BSA_MERIT_BADGES_CATALOG
    ]
    df = pd.DataFrame(all_badges_rows)
    total_catalog_count = len(df)
    eagle_catalog_count = int(df["Eagle Required"].sum())
    elective_catalog_count = total_catalog_count - eagle_catalog_count

    if "selected_badge_name" not in st.session_state:
        st.session_state["selected_badge_name"] = "First Aid"
    if "active_slide_idx" not in st.session_state:
        st.session_state["active_slide_idx"] = -1  # -1 = Slide 1 (Cover Slide)

    # ==========================================================================
    # LEFT RAIL SIDEBAR: 1. FIND & SELECT BADGE | 2. DECK STYLE & COUNSELOR INFO | 3. PROGRESS
    # ==========================================================================
    with st.sidebar:
        # --- CARD 1: 1. FIND & SELECT MERIT BADGE ---
        search_query = st.session_state.get("sidebar_search_input", "")
        category_filter = st.session_state.get("sidebar_cat_select", "All Categories")
        eagle_filter = st.session_state.get(
            "sidebar_eagle_select", f"All Badges ({total_catalog_count})"
        )

        # Compute filtered_df first so header chip shows live count
        filtered_df = df.copy()
        if str(search_query).strip():
            q = str(search_query).strip()
            filtered_df = filtered_df[
                filtered_df["Badge Name"].str.contains(q, case=False, na=False)
                | filtered_df["Category"].str.contains(q, case=False, na=False)
            ]
        if category_filter != "All Categories":
            filtered_df = filtered_df[filtered_df["Category"] == category_filter]
        if str(eagle_filter).startswith("Eagle-Required"):
            filtered_df = filtered_df[filtered_df["Eagle Required"].eq(True)]
        elif str(eagle_filter).startswith("Electives"):
            filtered_df = filtered_df[filtered_df["Eagle Required"].eq(False)]
        filtered_df = filtered_df.reset_index(drop=True)

        st.markdown(
            _clean_html(
                f"""
                <div class="m3-sidebar-card-hdr">
                  <span class="m3-sidebar-card-title">🔎 1. Find &amp; Select Merit Badge</span>
                  <span class="m3-chip m3-chip-gold">{len(filtered_df)} of {total_catalog_count} Badges</span>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        search_query = st.text_input(
            "Search Merit Badge Name",
            value="",
            placeholder="Search all merit badges (e.g., Weather, First Aid)...",
            key="sidebar_search_input",
        )
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            category_filter = st.selectbox(
                "Category",
                ["All Categories"] + sorted(df["Category"].unique().tolist()),
                key="sidebar_cat_select",
            )
        with f_col2:
            eagle_filter = st.selectbox(
                "Eagle Status",
                [
                    f"All Badges ({total_catalog_count})",
                    f"Eagle-Required ({eagle_catalog_count})",
                    f"Electives ({elective_catalog_count})",
                ],
                key="sidebar_eagle_select",
            )

        # Re-evaluate filtered_df with current widget states
        filtered_df = df.copy()
        if search_query.strip():
            q = search_query.strip()
            filtered_df = filtered_df[
                filtered_df["Badge Name"].str.contains(q, case=False, na=False)
                | filtered_df["Category"].str.contains(q, case=False, na=False)
            ]
        if category_filter != "All Categories":
            filtered_df = filtered_df[filtered_df["Category"] == category_filter]
        if eagle_filter.startswith("Eagle-Required"):
            filtered_df = filtered_df[filtered_df["Eagle Required"].eq(True)]
        elif eagle_filter.startswith("Electives"):
            filtered_df = filtered_df[filtered_df["Eagle Required"].eq(False)]
        filtered_df = filtered_df.reset_index(drop=True)

        badge_options = filtered_df["Badge Name"].tolist()
        if not badge_options:
            st.warning("⚠️ No Merit Badges match your current filters. Clear or adjust the filters above.")
            st.stop()

        if st.session_state["selected_badge_name"] not in badge_options:
            st.session_state["selected_badge_name"] = (
                "First Aid" if "First Aid" in badge_options else badge_options[0]
            )

        st.session_state["main_badge_dropdown"] = st.session_state["selected_badge_name"]
        selected_badge_name = st.selectbox(
            f"Select Merit Badge ({len(badge_options)} matching badges):",
            badge_options,
            key="main_badge_dropdown",
            on_change=_sync_from_main_dropdown,
        )

        st.caption("**Quick-Select Popular Badges**")
        quick_badges = [
            ("★ First Aid", "First Aid"),
            ("Weather", "Weather"),
            ("★ Camping", "Camping"),
            ("★ Cit. in Nation", "Citizenship in the Nation"),
            ("★ Cooking", "Cooking"),
            ("★ Emergency Prep", "Emergency Preparedness"),
            ("★ Env. Science", "Environmental Science"),
            ("Robotics", "Robotics"),
        ]
        q_cols = st.columns(2)
        for q_idx, (q_label, q_badge) in enumerate(quick_badges):
            with q_cols[q_idx % 2]:
                is_curr = selected_badge_name == q_badge
                if st.button(
                    q_label,
                    key=f"quick_pill_{q_badge}",
                    use_container_width=True,
                    type="primary" if is_curr else "secondary",
                ):
                    st.session_state["selected_badge_name"] = q_badge
                    st.session_state["active_slide_idx"] = -1
                    st.rerun()

        # --- CARD 2: 2. DECK STYLE & COUNSELOR INFO ---
        st.markdown(
            _clean_html(
                """
                <div class="m3-sidebar-card-hdr" style="margin-top:16px;">
                  <span class="m3-sidebar-card-title">🎞️ 2. Deck Style &amp; Counselor Info</span>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        depth_label = st.selectbox(
            "Slide Deck Length & Depth",
            [
                "Deep Dive Teaching Deck (Detailed — 50 to 70+ Slides)",
                "Standard Troop Meeting Deck (Focused — 1 to 3 Slides / Req)",
            ],
            index=0,
        )
        depth_mode = (
            "Deep Dive / Camp School Deck"
            if "Deep Dive" in depth_label
            else "Standard Deck"
        )

        beautification_label = st.selectbox(
            "Slide Visual Polish Mode (Beautification Tier)",
            [
                "Standard Fast Deck — Crisp White (~$0.14)",
                "AI Beautified — Warm Cream + Hero Graphics (~$0.38)",
                "AI Studio — Dark Slate + Hero Graphics ($1.00 Budget)",
            ],
            index=1,
        )
        if "Studio" in beautification_label:
            beautification_tier = "STUDIO"
        elif "Beautified" in beautification_label:
            beautification_tier = "BEAUTIFIED"
        else:
            beautification_tier = "STANDARD"

        audience_level = st.selectbox(
            "Target Scout Audience Level",
            [
                "All Scouts (Ages 11–17)",
                "First-Year / Tenderfoot Focus (Ages 11–12)",
                "Older Scouts / Eagle Prep (Ages 14–17)",
            ],
            index=0,
        )

        enable_deep_research = st.checkbox(
            "Enable Local Regional Grounding (NOAA / Terrain / Field Sites)",
            value=True,
        )

        # Load locally cached counselor profile (.cache/counselor_profile.json, 0600 permissions) on first run
        if "_cached_counselor_profile" not in st.session_state:
            st.session_state["_cached_counselor_profile"] = load_local_counselor_profile()
        cached_prof = st.session_state["_cached_counselor_profile"]

        counselor_name = st.text_input(
            "Counselor Name",
            value=str(cached_prof.get("counselor_name") or "Scoutmaster Bob"),
        )
        troop_affiliation = st.text_input(
            "Troop & Council Affiliation",
            value=str(cached_prof.get("troop_affiliation") or "Troop 123, My Council"),
        )
        location_or_zip = st.text_input(
            "Location (City, State or ZIP Code)",
            value=str(cached_prof.get("location_or_zip") or ""),
            placeholder="e.g., Middleton, MA or 01949 (auto-inferred if blank)",
            help="Resolves your local NOAA Weather Forecast Office, terrain hazards, and council field study sites.",
        )
        email_address = st.text_input(
            "Contact Email (Optional)",
            value=str(cached_prof.get("email_address") or "counselor@troop123.org"),
        )
        phone_number = st.text_input(
            "Contact Phone (Optional)",
            value=str(cached_prof.get("phone_number") or "(000) 555-1234"),
        )

        uploaded_logo = st.file_uploader("Optional Troop Custom Logo (.png / .jpg)", type=["png", "jpg", "jpeg"])
        logo_path: Optional[str] = cached_prof.get("custom_troop_logo_path")
        if uploaded_logo:
            os.makedirs("scratch_assets", exist_ok=True)
            logo_path = os.path.abspath(os.path.join("scratch_assets", uploaded_logo.name))
            with open(logo_path, "wb") as f:
                f.write(uploaded_logo.getbuffer())
            st.caption(f"✓ Uploaded: `{uploaded_logo.name}`")

        # Automatically persist counselor profile locally when changed
        live_prof_snapshot = {
            "counselor_name": counselor_name,
            "troop_affiliation": troop_affiliation,
            "location_or_zip": location_or_zip,
            "email_address": email_address,
            "phone_number": phone_number,
            "custom_troop_logo_path": logo_path,
        }
        if any(
            live_prof_snapshot.get(k) != cached_prof.get(k)
            for k in ("counselor_name", "troop_affiliation", "location_or_zip", "email_address", "phone_number", "custom_troop_logo_path")
        ):
            saved_prof = save_local_counselor_profile(live_prof_snapshot)
            st.session_state["_cached_counselor_profile"] = saved_prof
            cached_prof = saved_prof

        cache_col1, cache_col2 = st.columns([2.2, 1.0])
        with cache_col1:
            if cached_prof.get("cached_locally"):
                st.caption("🔒 **Cached locally** (`.cache/counselor_profile.json`, `0600` owner-only; PII scrubbed from logs)")
            else:
                st.caption("🔒 **PII Protected:** Contact details stay in session & are scrubbed from telemetry logs.")
        with cache_col2:
            if st.button("↺ Reset Info", key="btn_reset_counselor_cache", use_container_width=True):
                reset_prof = clear_local_counselor_profile()
                st.session_state["_cached_counselor_profile"] = reset_prof
                st.rerun()

        preview_finops = estimate_workflow_finops_cost(
            badge_name=selected_badge_name,
            depth_mode=depth_mode,
            beautification_tier=beautification_tier,
            enable_deep_research=enable_deep_research,
        )
        st.markdown(
            _clean_html(
                f"""
                <div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:10px; padding:8px 12px; margin:6px 0 10px 0; font-size:0.78rem; color:#1E3A8A; display:flex; align-items:center; justify-content:space-between;">
                  <span><strong>FinOps Est. Cost:</strong> ${preview_finops['estimated_cost_usd']:.2f} / $1.00 Cap</span>
                  <span>{preview_finops['beautification_tier']} &bull; ~{(preview_finops['estimated_input_tokens'] + preview_finops['estimated_output_tokens']) // 1000}K tokens</span>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        generate_clicked = st.button(
            "✨ Generate Slide Deck & Workbook",
            type="primary",
            use_container_width=True,
        )

        # Auto-generate on initial load, when selected badge or style/counselor inputs change, or when Generate is clicked
        prev_result = st.session_state.get("last_workflow_result")
        needs_generation = (
            generate_clicked
            or prev_result is None
            or prev_result.get("badge_name") != selected_badge_name
            or st.session_state.get("_last_depth_mode") != depth_mode
            or st.session_state.get("_last_beautification_tier") != beautification_tier
            or st.session_state.get("_last_audience_level") != audience_level
            or st.session_state.get("_last_enable_deep_research") != enable_deep_research
            or st.session_state.get("_last_counselor_name") != counselor_name
            or st.session_state.get("_last_troop_affiliation") != troop_affiliation
            or st.session_state.get("_last_location_or_zip") != location_or_zip
            or st.session_state.get("_last_email_address") != email_address
            or st.session_state.get("_last_phone_number") != phone_number
            or st.session_state.get("_last_logo_path") != logo_path
        )

        if needs_generation:
            with st.status(f"Generating **{selected_badge_name}** Slide Deck & Workbook ({beautification_tier})...", expanded=True) as status_box:
                st.write("🔎 **1. Official Requirements & Pamphlet**: Extracting official requirements and badge graphics...")
                counselor_info = {
                    "counselor_name": counselor_name,
                    "troop_affiliation": troop_affiliation,
                    "location_or_zip": location_or_zip if location_or_zip else None,
                    "email_address": email_address if email_address else None,
                    "phone_number": phone_number if phone_number else None,
                    "custom_troop_logo_path": logo_path,
                }
                st.write("🗂️ **2. Slide Deck Outline, Grounded Research & Beautification**: Building requirement teaching sequences and figures...")
                result = run_merit_badge_workflow(
                    badge_name=selected_badge_name,
                    depth_mode=depth_mode,
                    counselor_info=counselor_info,
                    beautification_tier=beautification_tier,
                    enable_deep_research=enable_deep_research,
                    audience_level=audience_level,
                )
                st.session_state["last_workflow_result"] = result
                st.session_state["_last_depth_mode"] = depth_mode
                st.session_state["_last_beautification_tier"] = beautification_tier
                st.session_state["_last_audience_level"] = audience_level
                st.session_state["_last_enable_deep_research"] = enable_deep_research
                st.session_state["_last_counselor_name"] = counselor_name
                st.session_state["_last_troop_affiliation"] = troop_affiliation
                st.session_state["_last_location_or_zip"] = location_or_zip
                st.session_state["_last_email_address"] = email_address
                st.session_state["_last_phone_number"] = phone_number
                st.session_state["_last_logo_path"] = logo_path
                st.session_state["active_slide_idx"] = -1
                if status_box is not None and hasattr(status_box, "update"):
                    status_box.update(
                        label=f"✅ Ready! {result.get('slide_count', 0)} Slides ({beautification_tier}) & Workbook Generated",
                        state="complete",
                        expanded=False,
                    )

        # --- CARD 3: RESEARCH & GENERATION PROGRESS ---
        result = st.session_state.get("last_workflow_result")
        if result and result.get("status") in ("SUCCESS", "REVIEW_WARNING"):
            r_reqs = (result.get("research_artifact") or {}).get("requirements", [])
            dr_citations = (result.get("deep_research_enrichment") or {}).get("grounded_citations", [])
            resolved_loc_obj = ((result.get("deep_research_enrichment") or {}).get("resolved_location") or {})
            loc_suffix = f" • {resolved_loc_obj.get('region_label')}" if resolved_loc_obj.get("region_label") else ""
            finops_res = result.get("finops_cost_estimate") or preview_finops
            st.markdown(
                _clean_html(
                    f"""
                    <div class="m3-sidebar-card-hdr" style="margin-top:16px;">
                      <span class="m3-sidebar-card-title">⏳ Research &amp; Generation Progress</span>
                      <span class="m3-chip m3-chip-secondary">Complete</span>
                    </div>
                    <div class="m3-trace-item">
                      <div class="m3-trace-top"><span>1. Official Requirements &amp; Pamphlet</span><span class="m3-trace-meta">Loaded</span></div>
                      <div class="m3-trace-desc">Extracted {len(r_reqs)} official requirements + {len(dr_citations)} grounded citations for {_escape(result.get("badge_name"))} ({_escape(troop_affiliation)}{_escape(loc_suffix)}).</div>
                    </div>
                    <div class="m3-trace-item">
                      <div class="m3-trace-top"><span>2. Teaching Slides &amp; Beautification</span><span class="m3-trace-meta">{result.get("slide_count", 0)} Slides ({_escape(result.get("beautification_tier", beautification_tier))})</span></div>
                      <div class="m3-trace-desc">Applied {_escape(result.get("beautification_tier", beautification_tier))} theme styling, {_escape(result.get("audience_level", audience_level))} coaching, and EDGE Skill Concept Maps.</div>
                    </div>
                    <div class="m3-trace-item">
                      <div class="m3-trace-top"><span>3. PowerPoint, Workbook &amp; StudioKit</span><span class="m3-trace-meta">${finops_res.get("estimated_cost_usd", 0.14):.2f}</span></div>
                      <div class="m3-trace-desc">Ready to preview and download (.pptx slide deck, .md workbook, lesson plan &amp; parent letter).</div>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )

    # ==========================================================================
    # RIGHT MAIN STAGE: TOP APP BAR, HERO BANNER & 4 WORKBENCH TABS
    # ==========================================================================
    result = st.session_state.get("last_workflow_result")
    if not result or result.get("status") not in ("SUCCESS", "REVIEW_WARNING"):
        st.error("Unable to generate Merit Badge workbench payload. Please try selecting another Merit Badge.")
        st.stop()

    res_badge = result.get("badge_name", selected_badge_name)
    res_meta = get_merit_badge_metadata(res_badge) or {}
    res_assets = get_badge_cover_and_patch_paths(res_badge)
    reqs = (result.get("research_artifact") or {}).get("requirements", [])
    slides = (result.get("storyboard") or {}).get("slides", [])
    total_slides = result.get("slide_count") or (len(slides) + 1)

    pamphlet_url = (
        (result.get("research_artifact") or {}).get("pamphlet_pdf_url")
        or res_meta.get("pamphlet_pdf_url")
        or f"https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/{res_badge.replace(' ', '%20')}.pdf"
    )
    drg_url = (
        (result.get("research_artifact") or {}).get("drg_url")
        or res_meta.get("drg_url")
        or f"https://www.scouting.org/merit-badges/{res_badge.lower().replace(' ', '-')}/"
    )

    # 1. Top App Bar + 4 Action Buttons (Matching M3 Top Bar)
    st.markdown(
        _clean_html(
            """
            <div class="m3-top-bar">
              <div class="m3-brand-cluster">
                <div class="m3-brand-emblem">⚜️</div>
                <div class="m3-brand-titles">
                  <h1>Scouts BSA Merit Badge Counselor Workbench</h1>
                  <div class="m3-brand-subtitle">All Official Merit Badges &bull; Teaching Slide Decks &amp; Printable Scout Workbooks</div>
                </div>
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    act_c1, act_c2, act_c3, act_c4 = st.columns(4)
    with act_c1:
        st.link_button("📕 Official BSA Pamphlet", pamphlet_url, use_container_width=True)
    with act_c2:
        st.link_button("🌐 Resource Guide", drg_url, use_container_width=True)
    with act_c3:
        wb_path = result.get("workbook_path")
        if wb_path and os.path.exists(wb_path):
            with open(wb_path, "rb") as wbfp:
                st.download_button(
                    label="📘 Download Workbook (.MD)",
                    data=wbfp.read(),
                    file_name=os.path.basename(wb_path),
                    mime="text/markdown",
                    use_container_width=True,
                    key="top_dl_wb",
                )
    with act_c4:
        pptx_file_path = result.get("output_path")
        if pptx_file_path and os.path.exists(pptx_file_path):
            with open(pptx_file_path, "rb") as fp:
                st.download_button(
                    label="📥 Download Slide Deck (.PPTX)",
                    data=fp.read(),
                    file_name=os.path.basename(pptx_file_path),
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                    type="primary",
                    key="top_dl_pptx",
                )

    # 2. Hero Summary Banner with Circular Standalone Emblem & KPI Pills
    patch_uri = _get_data_uri(res_assets.get("patch_path"))
    hero_patch_html = (
        f'<img src="{patch_uri}" alt="Merit Badge Patch" style="width:78px; height:78px; border-radius:50%; object-fit:contain; background:rgba(255,255,255,0.14); padding:4px; box-shadow:0 4px 12px rgba(0,0,0,0.22);" />'
        if patch_uri
        else ""
    )
    cat_upper = f" • {res_meta.get('category', '').upper()}" if res_meta.get("category") else ""
    kicker_text = (
        f"★ EAGLE-REQUIRED MERIT BADGE{cat_upper}"
        if result.get("is_eagle_required")
        else f"⚜️ SCOUTS BSA ELECTIVE MERIT BADGE{cat_upper}"
    )
    depth_desc = (
        "Detailed Deep-Dive Teaching Deck"
        if "deep" in depth_mode.lower()
        else "Standard Troop Meeting Deck (1–3 Slides per Requirement)"
    )

    st.markdown(
        _clean_html(
            f"""
            <div class="m3-hero-banner">
              <div style="display:flex; align-items:center; gap:18px;">
                {hero_patch_html}
                <div>
                  <div class="m3-hero-kicker">{_escape(kicker_text)}</div>
                  <div class="m3-hero-title">{_escape(res_badge)} Merit Badge</div>
                  <div class="m3-hero-meta">{_escape(depth_desc)} &bull; {_escape(result.get("beautification_tier", beautification_tier))} Polish &bull; {_escape(audience_level)}</div>
                </div>
              </div>
              <div class="m3-hero-kpis">
                <div class="m3-kpi-pill">
                  <div class="m3-kpi-value">{total_slides}</div>
                  <div class="m3-kpi-label">Total Slides</div>
                </div>
                <div class="m3-kpi-pill">
                  <div class="m3-kpi-value">{len(reqs)}</div>
                  <div class="m3-kpi-label">Requirements</div>
                </div>
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    # 3. Four Workbench Views (Matching M3 Navigation Tabs)
    tab_slides, tab_reqs, tab_wb, tab_studiokit = st.tabs([
        "🎞️ Slide Deck Preview",
        "📚 Official Requirements & Resource Guides",
        "📘 Scout & Counselor Workbook",
        "📋 Lesson Plan, Parent Letter & FinOps",
    ])

    # --------------------------------------------------------------------------
    # TAB 1: INTERACTIVE SLIDE DECK PREVIEW (LEFT FILMSTRIP + RIGHT 16:9 STAGE)
    # --------------------------------------------------------------------------
    with tab_slides:
        active_idx = int(st.session_state.get("active_slide_idx", -1))
        if active_idx < -1 or active_idx >= len(slides):
            active_idx = -1
            st.session_state["active_slide_idx"] = -1

        film_col, stage_col = st.columns([1.05, 2.95], gap="medium")

        with film_col:
            st.markdown(f"**Slide Filmstrip ({total_slides} Slides)**")
            with st.container(height=650):
                is_cover_active = active_idx == -1
                if st.button(
                    f"Slide 1 • Cover [Title & Badge]\n{res_badge} Merit Badge",
                    key="film_thumb_cover",
                    use_container_width=True,
                    type="primary" if is_cover_active else "secondary",
                ):
                    st.session_state["active_slide_idx"] = -1
                    st.rerun()

                for s_idx, s in enumerate(slides):
                    has_req_def = bool(s.get("verbatim_requirement_text") and str(s["verbatim_requirement_text"]).strip())
                    has_img = bool(s.get("diagram_path") and os.path.exists(s["diagram_path"]))
                    has_hero = bool(s.get("ai_hero_image_path"))
                    r_num = str(s.get("req_number") or "")
                    kind_label = (
                        "Sources"
                        if r_num == "Sources"
                        else "Overview"
                        if r_num == "Overview"
                        else "Req Intro"
                        if has_req_def
                        else "Diagram"
                        if has_img
                        else "Teaching"
                    )
                    badges_suffix = f"{' ✨' if has_hero else ''}"
                    r_tag = r_num if r_num in ("Overview", "Sources") else f"Req {r_num}"
                    s_title = str(s.get("title") or "")
                    short_title = s_title if len(s_title) <= 44 else s_title[:42] + "…"
                    if st.button(
                        f"Slide {s_idx + 2} • {r_tag} [{kind_label}]{badges_suffix}\n{short_title}",
                        key=f"film_thumb_{s_idx}",
                        use_container_width=True,
                        type="primary" if active_idx == s_idx else "secondary",
                    ):
                        st.session_state["active_slide_idx"] = s_idx
                        st.rerun()

        with stage_col:
            # Slide Toolbar
            tb_left, tb_prev, tb_next = st.columns([3.4, 0.9, 0.9])
            if active_idx == -1:
                slide_num_label = f"Slide 1 of {total_slides}"
                req_chip_label = "Cover Slide"
                theme_chip_label = f"🎨 {result.get('beautification_tier', beautification_tier)}"
                eagle_cover_note = (
                    f"As an Eagle-Required Merit Badge, {res_badge} builds essential lifelong citizenship, safety, and outdoor leadership skills."
                    if result.get("is_eagle_required")
                    else f"The {res_badge} Merit Badge gives Scouts an opportunity to explore a specialized field through hands-on practice and real-world observation."
                )
                active_notes = (
                    f"[SAY] Welcome Scouts to our {res_badge} Merit Badge session, and introduce yourself ({counselor_name}, {troop_affiliation}) along with how Scouts and parents can reach you ({email_address or 'via unit leadership'}) using Two-Deep Leadership / Youth Protection guidelines. "
                    f"{eagle_cover_note} Explain how we will work through each official requirement using this presentation, hands-on demonstrations, and your printable {res_badge} Merit Badge Workbook."
                )
            else:
                curr_slide = slides[active_idx]
                r_num = str(curr_slide.get("req_number") or (active_idx + 1))
                slide_num_label = f"Slide {active_idx + 2} of {total_slides}"
                req_chip_label = r_num if r_num in ("Overview", "Sources") else f"Requirement {r_num}"
                theme_chip_label = f"🎨 {curr_slide.get('beautification_tier', beautification_tier)} • {curr_slide.get('visual_theme', 'NUMBERED_STEP_CARDS')}"
                active_notes = str(curr_slide.get("presenter_notes") or "")

            with tb_left:
                st.markdown(
                    _clean_html(
                        f"""
                        <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap; padding-top:4px;">
                          <span class="m3-chip m3-chip-primary">{_escape(slide_num_label)}</span>
                          <span class="m3-chip m3-chip-secondary">{_escape(req_chip_label)}</span>
                          <span class="m3-chip m3-chip-primary">{_escape(theme_chip_label)}</span>
                          <span class="m3-chip m3-chip-secondary">👥 {_escape(audience_level)}</span>
                        </div>
                        """
                    ),
                    unsafe_allow_html=True,
                )
            with tb_prev:
                if st.button("◀ Prev Slide", use_container_width=True, disabled=(active_idx <= -1)):
                    st.session_state["active_slide_idx"] = max(-1, active_idx - 1)
                    st.rerun()
            with tb_next:
                if st.button("Next Slide ▶", use_container_width=True, disabled=(active_idx >= len(slides) - 1)):
                    st.session_state["active_slide_idx"] = min(len(slides) - 1, active_idx + 1)
                    st.rerun()

            # 16:9 Widescreen Slide Stage
            stage_html = _render_widescreen_slide_html(
                result=result,
                slide_idx=active_idx,
                counselor_name=counselor_name,
                troop_affiliation=troop_affiliation,
                email_address=email_address,
                phone_number=phone_number,
                logo_path=logo_path,
                patch_path=res_assets.get("patch_path"),
                cover_path=res_assets.get("cover_path"),
                location_or_zip=location_or_zip,
            )
            st.markdown(stage_html, unsafe_allow_html=True)

            # Per-Slide Interactive Co-Design Bar (Content Slides)
            if active_idx >= 0:
                curr_s = slides[active_idx]
                st.markdown(
                    _clean_html(
                        """
                        <div style="background:#F8FAFC; border:1.5px solid #CBD5E1; border-radius:12px; padding:10px 14px; margin-bottom:8px;">
                          <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px; flex-wrap:wrap; gap:8px;">
                            <span style="font-family:'Roboto Slab',serif; font-size:0.90rem; font-weight:700; color:#003F87;">🎨 Per-Slide Interactive Co-Design Bar &amp; Image Studio — Customize Slide &amp; Rebuild PowerPoint</span>
                            <span class="m3-chip m3-chip-gold">Surgical Single-Slide Regeneration</span>
                          </div>
                          <div style="font-size:0.77rem; color:#475569; line-height:1.45; background:#EFF6FF; border-left:3px solid #003F87; padding:6px 10px; border-radius:6px;">
                            <strong>How to customize this slide:</strong>
                            <strong>(1) Slide Layout</strong> rearranges the teaching cards;
                            <strong>(2) Card Style</strong> changes card badges &amp; borders;
                            <strong>(3) Brand Palette</strong> updates slide colors;
                            <strong>(4) Right-Side Graphic</strong> keeps the current graphic, restores the original slide picture/illustration, applies an EDGE Skill Concept Map, or sets <strong>None</strong> (removing the graphic and expanding text to full width). Use the <strong>Image Switcher &amp; Image Studio</strong> below to switch images, search web archives, or generate a custom Nano Banana AI graphic.
                          </div>
                        </div>
                        """
                    ),
                    unsafe_allow_html=True,
                )
                cd_c1, cd_c2, cd_c3, cd_c4, cd_c5 = st.columns([1.35, 1.25, 1.05, 1.25, 1.05])
                arch_label_map = {
                    "SPLIT_VISUAL_EXPLAINER": "Stacked Cards + Right Visual (Standard)",
                    "STEP_BY_STEP_PROCEDURE_4CARD": "2×2 Step Grid (Numbered Cards)",
                    "DIFFERENTIAL_COMPARISON_2COL": "2-Column Side-by-Side Comparison",
                    "GEAR_CHECKLIST_GRID": "2-Column Inspection Checklist ([✓])",
                    "REQUIREMENTS_TRIAGE_MATRIX": "3-Column Triage (Theory / Skills / Field)",
                    "WORKED_EXAMPLE_TEMPLATE": "Worked Example & Counselor Pro-Tip",
                    "SOCRATIC_CHECKPOINT_QUIZ": "Patrol Scenario & Checkpoint Quiz",
                    "CONCEPT_TEXT_SLIDE": "Full-Width Text Cards (Hide Right Graphic)",
                    "FULL_BLEED_IMAGE_EXPLAINER": "Full-Slide Large Diagram Spotlight",
                    "REQUIREMENT_INTRO": "Requirement Intro Banner + Split Cards",
                }
                archetype_opts = list(arch_label_map.keys())
                curr_arch = str(curr_s.get("archetype") or "SPLIT_VISUAL_EXPLAINER")
                arch_idx = archetype_opts.index(curr_arch) if curr_arch in archetype_opts else 0

                theme_label_map = {
                    "NUMBERED_STEP_CARDS": "Numbered Step Badges (01, 02, 03)",
                    "THREE_PILLAR_BENTO": "Bento Accent Cards (Top Color Bar ◆)",
                    "EDITORIAL_CALLOUT_QUOTE": "Editorial Callout Cards (Warm Gold ❝)",
                    "DARK_SLATE_SPOTLIGHT": "High-Contrast Dark Slate Cards (★)",
                    "TIMELINE_CHEVRON_CARDS": "Timeline Sequence Cards (STEP 1 ➔)",
                    "SAFETY_ALERT_SPLIT": "Safety Warning Highlight (Crimson ⚠️)",
                }
                theme_alias = {
                    "NUMBERED_STEP_RIBBON": "NUMBERED_STEP_CARDS",
                    "THREE_PILLAR_ACCENT_CARDS": "THREE_PILLAR_BENTO",
                    "MAGAZINE_ASYMMETRIC_SPLIT": "THREE_PILLAR_BENTO",
                    "ANNOTATED_INFOGRAPHIC_STAGE": "EDITORIAL_CALLOUT_QUOTE",
                    "SAFETY_ALERT_SPOTLIGHT": "SAFETY_ALERT_SPLIT",
                }
                theme_opts = list(theme_label_map.keys())
                raw_thm = str(curr_s.get("visual_theme") or "NUMBERED_STEP_CARDS")
                curr_thm = theme_alias.get(raw_thm, raw_thm)
                thm_idx = theme_opts.index(curr_thm) if curr_thm in theme_opts else 0

                pal_label_map = {
                    "NAVY_GOLD": "Scouts Navy & Eagle Gold",
                    "OLIVE_FOREST": "Outdoor Olive & Forest Green",
                    "EAGLE_CRIMSON": "Eagle Crimson & Navy",
                    "SLATE_ACTION": "Executive Slate & Action Blue",
                }
                pal_opts = list(pal_label_map.keys())
                curr_pal = str(curr_s.get("accent_palette_key") or "NAVY_GOLD")
                pal_idx = pal_opts.index(curr_pal) if curr_pal in pal_opts else 0

                vis_src_opts = [
                    "Keep Current Slide Graphic",
                    "Restore Original Slide Graphic",
                    "EDGE Skill Concept Map (Badge Emblem)",
                    "None (Remove Graphic & Expand Text to Full Width)",
                ]
                is_currently_none = (
                    curr_arch == "CONCEPT_TEXT_SLIDE"
                    or (not curr_s.get("diagram_path") and "None" in str(curr_s.get("visual_source_label") or ""))
                )
                curr_src_idx = (
                    3
                    if is_currently_none
                    else (2 if curr_s.get("ai_hero_image_path") else 0)
                )

                with cd_c1:
                    new_arch = st.selectbox(
                        "1. Slide Layout (Archetype)",
                        archetype_opts,
                        index=arch_idx,
                        format_func=lambda k: arch_label_map.get(k, k),
                        key=f"cd_arch_{active_idx}",
                    )
                with cd_c2:
                    new_thm = st.selectbox(
                        "2. Card Style (Magazine Theme)",
                        theme_opts,
                        index=thm_idx,
                        format_func=lambda k: theme_label_map.get(k, k),
                        key=f"cd_thm_{active_idx}",
                    )
                with cd_c3:
                    new_pal = st.selectbox(
                        "3. Brand Palette",
                        pal_opts,
                        index=pal_idx,
                        format_func=lambda k: pal_label_map.get(k, k),
                        key=f"cd_pal_{active_idx}",
                    )
                with cd_c4:
                    new_src = st.selectbox(
                        "4. Right-Side Graphic",
                        vis_src_opts,
                        index=curr_src_idx,
                        key=f"cd_src_{active_idx}",
                    )
                with cd_c5:
                    st.markdown('<div style="height:27px;"></div>', unsafe_allow_html=True)
                    if st.button("✨ Apply to Slide", key=f"cd_apply_{active_idx}", type="primary", use_container_width=True):
                        curr_s["visual_theme"] = new_thm
                        curr_s["accent_palette_key"] = new_pal
                        curr_s["beautification_tier"] = "STUDIO" if "EDGE Skill" in new_src else (
                            beautification_tier if beautification_tier != "STANDARD" else "BEAUTIFIED"
                        )
                        if "None" in new_src or new_arch == "CONCEPT_TEXT_SLIDE":
                            curr_s["diagram_path"] = None
                            curr_s["diagram_url"] = None
                            curr_s["ai_hero_image_path"] = None
                            curr_s["ai_hero_image_url"] = None
                            # Automatically update layout to full-width text when removing the graphic
                            if new_arch in ("SPLIT_VISUAL_EXPLAINER", "FULL_BLEED_IMAGE_EXPLAINER", "REQUIREMENT_INTRO"):
                                curr_s["archetype"] = "CONCEPT_TEXT_SLIDE"
                            else:
                                curr_s["archetype"] = new_arch
                            curr_s["visual_source_label"] = "None (Full-Width Text Layout)"
                            curr_s["callout_badge_text"] = f"📄 {new_thm.replace('_', ' ').title()} • {new_pal} • Full-Width Text"
                            if curr_s.get("full_bullet_points"):
                                curr_s["bullet_points"] = list(curr_s["full_bullet_points"])
                        elif "Restore Original" in new_src:
                            orig_path = curr_s.get("original_diagram_path")
                            orig_arch = curr_s.get("original_archetype") or "SPLIT_VISUAL_EXPLAINER"
                            if orig_path and os.path.exists(str(orig_path)):
                                curr_s["diagram_path"] = str(orig_path)
                                curr_s["ai_hero_image_path"] = None
                                curr_s["visual_caption"] = curr_s.get("original_visual_caption") or curr_s.get("title")
                                curr_s["visual_source_label"] = curr_s.get("original_visual_source_label") or "Official BSA Pamphlet / Wikimedia Figure"
                                curr_s["archetype"] = (
                                    orig_arch if orig_arch != "CONCEPT_TEXT_SLIDE" else "SPLIT_VISUAL_EXPLAINER"
                                ) if new_arch == curr_arch else new_arch
                                curr_s["callout_badge_text"] = f"📐 {new_thm.replace('_', ' ').title()} • {new_pal} • Restored Original"
                            else:
                                curr_s["diagram_path"] = None
                                curr_s["ai_hero_image_path"] = None
                                curr_s["archetype"] = orig_arch if new_arch == curr_arch else new_arch
                                curr_s["visual_source_label"] = "None (Originally Text-Only Slide)"
                                curr_s["callout_badge_text"] = f"📄 {new_thm.replace('_', ' ').title()} • {new_pal}"
                        elif "EDGE Skill" in new_src:
                            hero_res = generate_ai_editorial_illustration(
                                badge_name=res_badge,
                                req_number=f"{curr_s.get('req_number', active_idx+1)}_hero",
                                slide_title=str(curr_s.get("title") or ""),
                                visual_prompt=" | ".join((curr_s.get("bullet_points") or [])[:4]),
                                accent_palette_key=new_pal,
                                beautification_tier="STUDIO",
                            )
                            curr_s["diagram_path"] = hero_res["image_path"]
                            curr_s["ai_hero_image_path"] = hero_res["image_path"]
                            curr_s["archetype"] = "SPLIT_VISUAL_EXPLAINER" if new_arch == "CONCEPT_TEXT_SLIDE" else new_arch
                            curr_s["visual_source_label"] = "EDGE Skill Concept Map (SlideBeautifierAgent)"
                            curr_s["callout_badge_text"] = f"✨ {new_thm.replace('_', ' ').title()} • {new_pal} • EDGE Concept Map"
                        else:
                            # Keep Current Slide Graphic (never overwrite with generic vector flow chart!)
                            curr_s["archetype"] = new_arch
                            if not curr_s.get("diagram_path") and curr_s.get("original_diagram_path") and new_arch != "CONCEPT_TEXT_SLIDE":
                                curr_s["diagram_path"] = curr_s.get("original_diagram_path")
                                curr_s["visual_caption"] = curr_s.get("original_visual_caption") or curr_s.get("title")
                                curr_s["visual_source_label"] = curr_s.get("original_visual_source_label") or "Official BSA Pamphlet / Wikimedia Figure"
                            curr_s["callout_badge_text"] = f"📐 {new_thm.replace('_', ' ').title()} • {new_pal}"

                        _rebuild_pptx_in_place(
                            result=result,
                            slides=slides,
                            badge_name=res_badge,
                            counselor_name=counselor_name,
                            troop_affiliation=troop_affiliation,
                            location_or_zip=location_or_zip,
                            email_address=email_address,
                            phone_number=phone_number,
                            logo_path=logo_path,
                        )
                        st.rerun()

                # --- MULTI-IMAGE SWITCHER (◀ / DROPDOWN / ▶) & IMAGE STUDIO MODAL LAUNCHER ---
                raw_badge_cat = get_badge_image_catalog(res_badge, storyboard=result.get("storyboard"))
                req_str_curr = str(curr_s.get("req_number") or (active_idx + 1))
                badge_catalog_list = _extract_catalog_items(raw_badge_cat, default_req=req_str_curr)
                slide_avail_list = _extract_catalog_items(curr_s.get("available_images") or [], default_req=req_str_curr)
                # Merge slide available_images + badge_catalog_list without duplicates
                combined_images: List[Dict[str, Any]] = []
                seen_paths = set()
                for item in slide_avail_list + badge_catalog_list:
                    p = item.get("image_path")
                    if p and os.path.exists(p) and os.path.abspath(p) not in seen_paths:
                        seen_paths.add(os.path.abspath(p))
                        combined_images.append(item)

                curr_diag_abs = (
                    os.path.abspath(curr_s["diagram_path"])
                    if curr_s.get("diagram_path") and os.path.exists(str(curr_s["diagram_path"]))
                    else ""
                )
                is_currently_none = (not curr_diag_abs) or (curr_s.get("archetype") == "CONCEPT_TEXT_SLIDE")
                active_img_idx = -1 if is_currently_none else 0
                if not is_currently_none:
                    for idx_ci, ci in enumerate(combined_images):
                        if os.path.abspath(str(ci["image_path"])) == curr_diag_abs:
                            active_img_idx = idx_ci
                            break

                img_rev = st.session_state.get(f"img_rev_{active_idx}", 0)
                im_prev_col, im_sel_col, im_next_col, im_studio_col = st.columns([0.38, 2.35, 0.38, 1.89])

                with im_prev_col:
                    st.markdown('<div style="height:27px;"></div>', unsafe_allow_html=True)
                    if st.button(
                        "◀",
                        key=f"btn_prev_img_{active_idx}",
                        help="Previous cached Merit Badge image",
                        disabled=(len(combined_images) == 0),
                        use_container_width=True,
                    ):
                        base_idx = 0 if active_img_idx < 0 else active_img_idx
                        prev_idx = (base_idx - 1) % len(combined_images)
                        _apply_image_entry_to_slide(
                            curr_s=curr_s,
                            entry=combined_images[prev_idx],
                            result=result,
                            slides=slides,
                            badge_name=res_badge,
                            counselor_name=counselor_name,
                            troop_affiliation=troop_affiliation,
                            location_or_zip=location_or_zip,
                            email_address=email_address,
                            phone_number=phone_number,
                            logo_path=logo_path,
                        )
                        st.session_state[f"img_rev_{active_idx}"] = img_rev + 1
                        st.rerun()

                with im_sel_col:
                    if combined_images:
                        dropdown_options = list(range(len(combined_images))) + [-1]
                        default_opt_pos = dropdown_options.index(active_img_idx) if active_img_idx in dropdown_options else 0

                        def _fmt_img_opt(opt_val: int) -> str:
                            if opt_val == -1:
                                return "🚫 None (Remove Graphic & Expand Text to Full Width)"
                            ci_entry = combined_images[opt_val]
                            src_t = str(ci_entry.get("source_type") or "IMAGE")
                            tag = (
                                "🍌 AI"
                                if "NANO" in src_t
                                else "🌐 Web"
                                if "WEB" in src_t
                                else "✨ EDGE"
                                if "EDGE" in src_t
                                else "📐 BSA"
                            )
                            return f"[{opt_val + 1}/{len(combined_images)}] {tag} • Req {ci_entry.get('req_number', '')}: {str(ci_entry.get('title') or 'Visual')[:48]}"

                        selected_opt = st.selectbox(
                            f"🖼️ Quick-Switch Slide Image ({len(combined_images)} cached for {res_badge} — selects immediately)",
                            dropdown_options,
                            index=default_opt_pos,
                            format_func=_fmt_img_opt,
                            key=f"quick_img_switch_{active_idx}_{img_rev}",
                        )
                        if selected_opt != active_img_idx:
                            if selected_opt == -1:
                                curr_s["diagram_path"] = None
                                curr_s["ai_hero_image_path"] = None
                                curr_s["archetype"] = "CONCEPT_TEXT_SLIDE"
                                curr_s["visual_source_label"] = "None (Full-Width Text Layout)"
                                if curr_s.get("full_bullet_points"):
                                    curr_s["bullet_points"] = list(curr_s["full_bullet_points"])
                                _rebuild_pptx_in_place(
                                    result=result,
                                    slides=slides,
                                    badge_name=res_badge,
                                    counselor_name=counselor_name,
                                    troop_affiliation=troop_affiliation,
                                    location_or_zip=location_or_zip,
                                    email_address=email_address,
                                    phone_number=phone_number,
                                    logo_path=logo_path,
                                )
                            elif 0 <= selected_opt < len(combined_images):
                                _apply_image_entry_to_slide(
                                    curr_s=curr_s,
                                    entry=combined_images[selected_opt],
                                    result=result,
                                    slides=slides,
                                    badge_name=res_badge,
                                    counselor_name=counselor_name,
                                    troop_affiliation=troop_affiliation,
                                    location_or_zip=location_or_zip,
                                    email_address=email_address,
                                    phone_number=phone_number,
                                    logo_path=logo_path,
                                )
                            st.session_state[f"img_rev_{active_idx}"] = img_rev + 1
                            st.rerun()
                    else:
                        st.caption("No cached images yet for this badge. Click **Manage & Add Slide Images** to search or generate.")

                with im_next_col:
                    st.markdown('<div style="height:27px;"></div>', unsafe_allow_html=True)
                    if st.button(
                        "▶",
                        key=f"btn_next_img_{active_idx}",
                        help="Next cached Merit Badge image",
                        disabled=(len(combined_images) == 0),
                        use_container_width=True,
                    ):
                        base_idx = -1 if active_img_idx < 0 else active_img_idx
                        next_idx = (base_idx + 1) % len(combined_images)
                        _apply_image_entry_to_slide(
                            curr_s=curr_s,
                            entry=combined_images[next_idx],
                            result=result,
                            slides=slides,
                            badge_name=res_badge,
                            counselor_name=counselor_name,
                            troop_affiliation=troop_affiliation,
                            location_or_zip=location_or_zip,
                            email_address=email_address,
                            phone_number=phone_number,
                            logo_path=logo_path,
                        )
                        st.session_state[f"img_rev_{active_idx}"] = img_rev + 1
                        st.rerun()

                with im_studio_col:
                    st.markdown('<div style="height:27px;"></div>', unsafe_allow_html=True)
                    if st.button(
                        "🖼️ Manage & Add Slide Images (Catalog / Web / AI)",
                        key=f"btn_open_img_studio_{active_idx}",
                        type="secondary",
                        use_container_width=True,
                    ):
                        _open_image_studio_dialog(
                            res_badge=res_badge,
                            active_idx=active_idx,
                            curr_s=curr_s,
                            result=result,
                            slides=slides,
                            counselor_name=counselor_name,
                            troop_affiliation=troop_affiliation,
                            location_or_zip=location_or_zip,
                            email_address=email_address,
                            phone_number=phone_number,
                            logo_path=logo_path,
                        )

            # Counselor Teaching Notes Card
            st.markdown(
                _clean_html(
                    f"""
                    <div class="m3-speaker-notes-card">
                      <div style="font-family:'Roboto Slab',serif; font-size:0.95rem; font-weight:700; color:#003F87; margin-bottom:6px;">
                        🎙️ Counselor Teaching Notes ({_escape(audience_level)})
                      </div>
                      <div style="font-size:0.88rem; color:#0F172A; line-height:1.5;">
                        {_format_speaker_notes_html(active_notes)}
                      </div>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )

    # --------------------------------------------------------------------------
    # TAB 2: OFFICIAL REQUIREMENTS & RESOURCE GUIDES (3-COLUMN TRIAGE MATRIX)
    # --------------------------------------------------------------------------
    with tab_reqs:
        rc1, rc2 = st.columns([3, 2])
        with rc1:
            st.markdown("#### 📚 Official BSA Merit Badge Pamphlet & Digital Resource Guides")
            st.caption(
                "Below are the official requirements for this Merit Badge, organized to help Counselors plan troop discussions, hands-on skill demonstrations, and campout or home prerequisites."
            )
        with rc2:
            rl1, rl2 = st.columns(2)
            rl1.link_button("📕 Open Official Pamphlet (PDF)", pamphlet_url, use_container_width=True)
            rl2.link_button("🌐 Open Resource Guide", drg_url, use_container_width=True)

        in_class = [r for r in reqs if (r.get("execution_mode") or "IN_CLASS_DISCUSSION") == "IN_CLASS_DISCUSSION"]
        hands_on = [r for r in reqs if r.get("execution_mode") == "HANDS_ON_SKILL_STATION"]
        prereq = [r for r in reqs if r.get("execution_mode") == "PREREQUISITE_CAMPOUT_HOME"]

        tc1, tc2, tc3 = st.columns(3)

        with tc1:
            st.markdown(
                _render_triage_column("💬 Discussion & Core Knowledge", "m3-chip-primary", in_class),
                unsafe_allow_html=True,
            )
        with tc2:
            st.markdown(
                _render_triage_column("🛠️ Hands-On Skill Demonstrations", "m3-chip-secondary", hands_on),
                unsafe_allow_html=True,
            )
        with tc3:
            st.markdown(
                _render_triage_column("🏕️ Campout, Field & Home Projects", "m3-chip-eagle", prereq),
                unsafe_allow_html=True,
            )

    # --------------------------------------------------------------------------
    # TAB 3: PRINTABLE SCOUT & COUNSELOR WORKBOOK (.MD)
    # --------------------------------------------------------------------------
    with tab_wb:
        wb_path = result.get("workbook_path")
        wb_hdr1, wb_hdr2 = st.columns([3, 1])
        with wb_hdr1:
            st.markdown("#### 📘 Printable Scout & Counselor Workbook")
            st.caption("Rendered below as styled, wrapped Markdown for easy reading and printing. Click **Download Workbook (.MD)** for the raw Markdown file.")
        with wb_hdr2:
            if wb_path and os.path.exists(wb_path):
                with open(wb_path, "rb") as wbfp:
                    st.download_button(
                        label="📥 Download Workbook (.MD)",
                        data=wbfp.read(),
                        file_name=os.path.basename(wb_path),
                        mime="text/markdown",
                        use_container_width=True,
                        key="tab_dl_wb",
                    )
        if wb_path and os.path.exists(wb_path):
            wb_text = Path(wb_path).read_text(encoding="utf-8")
            with st.container(height=680, border=True):
                st.markdown(wb_text)
        else:
            st.info("No companion workbook found.")

    # --------------------------------------------------------------------------
    # TAB 4: COUNSELOR STUDIOKIT (LESSON PLAN, PARENT LETTER, CITATIONS & FINOPS)
    # --------------------------------------------------------------------------
    with tab_studiokit:
        sk_col1, sk_col2 = st.columns(2, gap="medium")
        agenda_md = (result.get("session_agenda") or {}).get("agenda_markdown") or "# Session Lesson Plan"

        # Dynamically generate Prerequisite Parent Letter with live Counselor inputs so it never reverts to defaults
        live_letter_res = generate_prerequisite_parent_letter(
            badge_name=res_badge,
            research_result=result.get("research_artifact") or {},
            counselor_info={
                "counselor_name": counselor_name,
                "troop_affiliation": troop_affiliation,
                "location_or_zip": location_or_zip,
                "email_address": email_address,
                "phone_number": phone_number,
            },
        )
        letter_md = live_letter_res.get("letter_markdown") or "# Parent Prerequisite Letter"

        with sk_col1:
            st.markdown("#### ⏱️ Counselor Session Agenda & Lesson Plan")
            st.download_button(
                label="📥 Download Session Agenda (.MD)",
                data=agenda_md.encode("utf-8"),
                file_name=f"{res_badge.replace(' ', '_')}_Session_Agenda.md",
                mime="text/markdown",
                use_container_width=True,
                key="dl_session_agenda",
            )
            with st.container(height=680, border=True):
                st.markdown(agenda_md)

        with sk_col2:
            st.markdown("#### ✉️ Prerequisite & Parent Welcome Letter (YPT-Compliant)")
            st.download_button(
                label="📥 Download Parent Letter (.MD)",
                data=letter_md.encode("utf-8"),
                file_name=f"{res_badge.replace(' ', '_')}_Parent_Prerequisite_Letter.md",
                mime="text/markdown",
                use_container_width=True,
                key="dl_parent_letter",
            )
            with st.container(height=680, border=True):
                st.markdown(letter_md)

        st.markdown("---")
        dr_payload = result.get("deep_research_enrichment") or {}
        resolved_loc_info = dr_payload.get("resolved_location") or {}
        finops_data = result.get("finops_cost_estimate") or preview_finops
        dr_col1, dr_col2 = st.columns([1.85, 1.15], gap="medium")
        with dr_col1:
            st.markdown("#### 🌐 Grounded Deep Research Citations & Local Regional Grounding")
            st.caption(
                f"Canonical Pamphlet Fidelity Verified: `{dr_payload.get('canonical_fidelity_verified', True)}` "
                f"(SHA-256: `{str(dr_payload.get('canonical_pamphlet_hash', ''))[:16]}…`) • "
                f"Local Troop Context: **{troop_affiliation}** • "
                f"Resolved Region: **{resolved_loc_info.get('region_label', 'Regional Context')}** ({resolved_loc_info.get('nws_office', 'NOAA NWS')})"
            )
            stored_troop = str(dr_payload.get("troop_affiliation") or "Troop 123, My Council")
            for cit in dr_payload.get("grounded_citations") or []:
                fact_txt = str(cit.get("supplemental_fact") or "").replace(stored_troop, troop_affiliation).replace("Troop 123, My Council", troop_affiliation)
                st.markdown(
                    f"- **[{cit.get('source_title')}]({cit.get('source_url')})** (`{cit.get('authority_domain')}` • Req `{cit.get('req_number')}`): {fact_txt}"
                )
        with dr_col2:
            st.markdown("#### 💰 FinOps Cost & Token Budget ($1.00 Max Cap)")
            st.markdown(_render_finops_table_html(finops_data), unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(
            f"#### 🌟 Counselor Sign-Off & Continuous Learning Flywheel (Schema `v{result.get('schema_version', CURRENT_SCHEMA_VERSION)}`)"
        )
        st.caption(
            "Rate this generated Merit Badge package (`POST /api/v1/feedback`). High-confidence counselor ratings (**≥ 4/5 Stars** + **Requirement Accuracy Verified**) automatically promote this session into `tests/data/golden_extensions.json` for CI/CD regression gating."
        )
        fb_col1, fb_col2, fb_col3, fb_col4 = st.columns([1.1, 1.3, 1.6, 1.1], gap="small")
        with fb_col1:
            fb_rating = st.selectbox(
                "1. Counselor Quality Rating",
                options=[5, 4, 3, 2, 1],
                index=0,
                format_func=lambda r: {
                    5: "⭐⭐⭐⭐⭐ 5/5 — Exemplary (Golden)",
                    4: "⭐⭐⭐⭐ 4/5 — Production Ready",
                    3: "⭐⭐⭐ 3/5 — Acceptable",
                    2: "⭐⭐ 2/5 — Below Standard",
                    1: "⭐ 1/5 — Reject",
                }[r],
                key=f"fb_rating_{res_badge}",
            )
        with fb_col2:
            st.markdown('<div style="height:26px;"></div>', unsafe_allow_html=True)
            fb_verified = st.checkbox(
                "✅ Requirement Accuracy Verified (2026 BSA Pamphlet)",
                value=True,
                key=f"fb_verified_{res_badge}",
            )
        with fb_col3:
            fb_comments = st.text_input(
                "2. Counselor Sign-Off Notes (Optional)",
                value="Verified all requirement numbers, EDGE teaching notes, and YPT safety callouts for troop instruction.",
                key=f"fb_comments_{res_badge}",
            )
        with fb_col4:
            st.markdown('<div style="height:26px;"></div>', unsafe_allow_html=True)
            if st.button(
                "🌟 Submit Rating & Promote",
                type="primary",
                use_container_width=True,
                key=f"btn_submit_fb_{res_badge}",
            ):
                from scripts.eval_gate import promote_session_to_golden_dataset

                should_promote = fb_rating >= 4 and fb_verified
                promo_res: Dict[str, Any] = {}
                if should_promote:
                    promo_res = promote_session_to_golden_dataset(
                        badge_name=res_badge,
                        counselor_rating=fb_rating,
                        requirement_count=len(reqs) or 5,
                        verified_by=counselor_name,
                    )
                promoted_flag = bool(promo_res.get("promoted", False))
                store = get_persistent_session_store()
                store.record_hitl_feedback_sync(
                    session_id=str(result.get("session_id") or f"session-{res_badge.lower().replace(' ', '-')}"),
                    badge_name=res_badge,
                    counselor_name=counselor_name,
                    rating=fb_rating,
                    requirement_accuracy_verified=fb_verified,
                    comments=fb_comments,
                    promoted_to_golden=promoted_flag,
                    schema_version=str(result.get("schema_version") or CURRENT_SCHEMA_VERSION),
                )
                if promoted_flag:
                    st.success(
                        f"✅ **Promoted to Golden Evaluation Dataset!** Recorded {fb_rating}/5 rating by **{counselor_name}** in SQLite (`hitl_feedback`) & updated `{promo_res.get('golden_extensions_path', 'tests/data/golden_extensions.json')}` ({promo_res.get('total_extensions', 1)} verified extensions • Schema `v{CURRENT_SCHEMA_VERSION}`)."
                    )
                else:
                    st.info(
                        f"📝 **Feedback Recorded in SQLite (`hitl_feedback`):** {fb_rating}/5 rating logged for **{res_badge}**."
                    )

    # --------------------------------------------------------------------------
    # BOTTOM ATTRIBUTION & FEEDBACK BANNER
    # --------------------------------------------------------------------------
    st.markdown(
        _clean_html(
            """
            <div style="background:#FFFFFF; border:1.5px solid #CBD5E1; border-radius:16px; padding:14px 22px; margin-top:24px; display:flex; align-items:center; justify-content:center; text-align:center; gap:12px; flex-wrap:wrap; box-shadow:0 2px 6px rgba(15,23,42,0.06);">
              <div style="font-size:0.88rem; color:#0F172A; line-height:1.5;">
                <span>Created by <strong>Eric Clayberg - Troop 19, Middleton MA</strong> with help from <strong>Google Gemini</strong> &bull; </span>
                <a href="https://www.linkedin.com/in/clayberg" target="_blank" rel="noopener noreferrer" style="color:#005AE0; font-weight:700; text-decoration:none;">LinkedIn Profile</a>
                <span> &bull; Suggestions &amp; Feedback: </span>
                <a href="mailto:clayberg@gmail.com?subject=Scouts%20BSA%20Merit%20Badge%20Counselor%20Workbench%20Feedback" style="color:#005AE0; font-weight:700; text-decoration:none;">clayberg@gmail.com</a>
                <span> (</span><a href="https://mail.google.com/mail/?view=cm&amp;fs=1&amp;to=clayberg@gmail.com&amp;su=Scouts%20BSA%20Merit%20Badge%20Counselor%20Workbench%20Feedback" target="_blank" rel="noopener noreferrer" style="color:#005AE0; font-weight:700; text-decoration:none;">Open in Gmail</a><span>)</span>
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


if st.runtime.exists():
    main()
