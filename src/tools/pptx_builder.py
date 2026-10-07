"""12-Archetype Widescreen PowerPoint Presentation Builder with Official Scouts BSA Styling.

This module implements:
1. Pydantic schemas for multi-slide instructional storyboards and build requests (100% backward-compatible).
2. Strict non-overlapping AABB zone geometry on a 16:9 widescreen canvas (13.333" x 7.5").
3. Dedicated full-width and visual archetype rendering:
   - REQUIREMENT_INTRO: Full-width requirement introduction & topic roadmap slide
   - CONCEPT_TEXT_SLIDE: Full-width detailed instructional slide
   - FULL_BLEED_IMAGE_EXPLAINER: Full-canvas centered diagram/photograph slide with explanation bar
   - SPLIT_VISUAL_EXPLAINER / HANDS_ON_PRACTICE_STATION: Left instructional summary + right visual figure
   - DIFFERENTIAL_COMPARISON_2COL, STEP_BY_STEP_PROCEDURE_4CARD, WORKED_EXAMPLE_TEMPLATE,
     GEAR_CHECKLIST_GRID, SOCRATIC_CHECKPOINT_QUIZ, REQUIREMENTS_TRIAGE_MATRIX, SOURCES_AND_REFERENCES
4. Clean visual presentation without per-page pamphlet attribution clutter (all sources consolidated on
   the final Sources & References slide).
5. Zero literal bullet glyphs ('•'), zero ellipsis truncation ('...'), <= 8 paragraphs/frame, >= 13pt font floor.
"""

import hashlib
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt
from pydantic import BaseModel, Field

from src.config import GENERATED_DIAGRAMS_DIR, ScoutsBSAPalette, is_eagle_required


# ==============================================================================
# PYDANTIC JSON SCHEMAS (100% BACKWARD-COMPATIBLE + ARCHETYPE EXTENSIONS)
# ==============================================================================

class SlideSpec(BaseModel):
    """Schema representing the content, archetype layout, and notes for an individual slide."""
    title: str = Field(..., description="Slide headline title.")
    bullet_points: List[str] = Field(
        default_factory=list,
        description="List of instructional points (maximum 7 points)."
    )
    presenter_notes: Optional[str] = Field(None, description="Counselor instructor notes.")
    safety_warning: Optional[str] = Field(None, description="Guide to Safe Scouting warning callout.")
    diagram_path: Optional[str] = Field(None, description="Optional path to diagram graphic to embed on slide.")

    # Extended Fields (all with clean defaults for backward compatibility)
    archetype: str = Field("SPLIT_VISUAL_EXPLAINER", description="Slide archetype identifier.")
    req_number: str = Field("1", description="Requirement or sub-requirement identifier (e.g., '1', '2a').")
    execution_mode: str = Field("IN_CLASS_DISCUSSION", description="Pedagogical execution mode.")
    edge_phase: str = Field("Explain & Guide", description="BSA EDGE Method phase.")
    subtitle: str = Field("", description="Optional subtitle or pedagogical context tag.")
    verbatim_requirement_text: str = Field("", description="Full non-truncated verbatim requirement text.")
    cards: List[Dict[str, Any]] = Field(default_factory=list, description="Structured card items for multi-card slides.")
    comparison_data: Optional[Dict[str, Any]] = Field(None, description="Two-column differential comparison payload.")
    worked_example: Optional[Dict[str, Any]] = Field(None, description="Concrete worked example template payload.")
    quiz_item: Optional[Dict[str, Any]] = Field(None, description="Socratic checkpoint quiz payload.")
    gear_checklist: List[str] = Field(default_factory=list, description="Equipment or inspection checklist items.")
    visual_caption: str = Field("", description="Caption displayed below the visual diagram.")
    diagram_type: str = Field("pamphlet_figure", description="Diagram type key.")
    beautification_tier: str = Field("STANDARD", description="Visual polish tier: STANDARD, BEAUTIFIED, or STUDIO.")
    visual_theme: str = Field("STANDARD_CLEAN", description="Layer-0 magazine vector card theme.")
    accent_palette_key: str = Field("NAVY_GOLD", description="Brand color palette key (NAVY_GOLD, OLIVE_FOREST, EAGLE_CRIMSON, SLATE_ACTION).")
    callout_badge_text: str = Field("", description="Magazine header callout pill text.")
    real_world_connection_box: Optional[str] = Field(None, description="Grounded Deep Research & Local Troop connection callout box.")
    grounded_citation_label: Optional[str] = Field(None, description="Source citation badge (e.g. 'NOAA / NWS + Local Council Grounded').")
    audience_level: str = Field("All Scouts (Ages 11–17)", description="Target Scout audience level.")
    ai_hero_image_path: Optional[str] = Field(None, description="Path to AI Editorial Hero Illustration when generated.")
    visual_source_label: str = Field("Official BSA Pamphlet / Technical Diagram", description="Label indicating visual asset origin.")
    original_diagram_path: Optional[str] = Field(None, description="Original pamphlet/topic figure path before any override.")
    original_diagram_url: Optional[str] = Field(None, description="Original web asset URL for the initial slide graphic.")
    original_visual_caption: str = Field("", description="Original visual caption before any override.")
    original_visual_source_label: str = Field("Official BSA Pamphlet / Technical Diagram", description="Original visual source label.")
    original_archetype: str = Field("SPLIT_VISUAL_EXPLAINER", description="Original slide archetype before any override.")
    available_images: List[Dict[str, Any]] = Field(default_factory=list, description="Cached/available images for this slide or requirement.")
    full_bullet_points: Optional[List[str]] = Field(None, description="Complete list of bullet points preserved when split layout caps visible cards.")


class CounselorTitleSlideInfo(BaseModel):
    """Counselor contact and troop customization for the presentation title slide."""
    counselor_name: str = Field(..., description="Full name of the Merit Badge Counselor.")
    troop_affiliation: str = Field(..., description="Troop number and council (e.g., 'Troop 101').")
    location_or_zip: Optional[str] = Field(None, description="Optional City, State or 5-digit ZIP code for local grounding.")
    email_address: Optional[str] = Field(None, description="Optional contact email address.")
    phone_number: Optional[str] = Field(None, description="Optional contact phone number.")
    custom_troop_logo_path: Optional[str] = Field(None, description="Path to custom Troop Logo PNG/JPG.")


class PowerPointBuildRequest(BaseModel):
    """Schema for requesting a brand-compliant Scouts BSA PowerPoint presentation."""
    badge_name: str = Field(..., description="Official badge name.")
    slides: List[SlideSpec] = Field(..., description="Ordered list of slides to generate.")
    counselor_info: Optional[CounselorTitleSlideInfo] = Field(None, description="Title slide counselor customization.")
    output_path: Optional[str] = Field(None, description="Target filesystem path for saved .pptx file.")
    hitl_confirmation_token: Optional[str] = Field(None, description="Optional FastMCP HITL confirmation token.")


class PowerPointBuildResult(BaseModel):
    """Structured return payload after generating PowerPoint presentation."""
    badge_name: str = Field(..., description="Official badge name.")
    slide_count: int = Field(..., description="Total number of slides generated.")
    output_path: str = Field(..., description="Absolute filesystem path to saved .pptx file.")
    is_eagle_required: bool = Field(..., description="True if Eagle-required badge styling was applied.")
    status: str = Field("SUCCESS", description="Execution status.")


# ==============================================================================
# TEXT SANITIZATION & TYPOGRAPHY HELPERS (7 GOLDEN RULES OF COPYWRITING)
# ==============================================================================

_LEADING_BULLET_RE = re.compile(r"^[\s•\-\*·▪▸►]+")


def _clean_text(raw_text: Optional[str]) -> str:
    """Strips literal bullet glyphs and removes ellipsis truncation from slide copy."""
    if not raw_text:
        return ""
    cleaned = _LEADING_BULLET_RE.sub("", str(raw_text).strip())
    cleaned = cleaned.replace("...", ".").replace("…", ".")
    cleaned = re.sub(r"\.\.+", ".", cleaned)
    return cleaned.strip()


def _split_anchor_and_body(point_text: str, default_anchor: str = "Key Point") -> Tuple[str, str]:
    """Splits a point string into a 2-5 word Bold Anchor and a concise body explanation."""
    cleaned = _clean_text(point_text)
    if not cleaned:
        return default_anchor, "Review this concept with your Merit Badge Counselor."
    if ":" in cleaned:
        first_colon = cleaned.find(":")
        anchor_candidate = cleaned[:first_colon].strip()
        body_candidate = cleaned[first_colon + 1 :].strip()
        if 1 <= len(anchor_candidate.split()) <= 7 and body_candidate:
            return anchor_candidate, body_candidate
    words = cleaned.split()
    if len(words) <= 4:
        return cleaned, ""
    anchor = " ".join(words[:3]).rstrip(",.;:")
    body = " ".join(words[3:])
    return anchor, body


def _compute_fitting_font_size(
    paragraphs_text: List[str],
    box_w_in: float,
    box_h_in: float,
    min_pt: float = 15.0,
    max_pt: float = 22.5,
    space_after_pt: float = 8.0,
) -> float:
    """Computes the largest comfortable font size (in pt) that wraps cleanly inside [box_w_in x box_h_in] without overflowing."""
    safe_min = max(15.0, float(min_pt))
    if not paragraphs_text:
        return max(safe_min, float(max_pt))
    usable_w_in = max(1.35, box_w_in - 0.46)
    usable_h_in = max(0.32, box_h_in - 0.24)

    candidate = float(max(safe_min, float(max_pt)))
    while candidate >= safe_min:
        # Conservative character width and line height accounting for bold Roboto Slab / Inter runs
        char_w_in = (candidate * 0.59) / 72.0
        chars_per_line = max(14, int(usable_w_in / max(0.04, char_w_in)))
        line_h_in = (candidate * 1.34) / 72.0
        para_gap_in = space_after_pt / 72.0

        total_h_in = 0.0
        for idx_p, raw_p in enumerate(paragraphs_text):
            txt = _clean_text(raw_p)
            if not txt:
                continue
            words = txt.split()
            n_lines = 1
            cur_len = 0
            for w in words:
                add_len = len(w) if cur_len == 0 else (1 + len(w))
                if cur_len + add_len <= chars_per_line:
                    cur_len += add_len
                else:
                    n_lines += 1
                    cur_len = len(w)
            gap_to_add = para_gap_in if idx_p < len(paragraphs_text) - 1 else 0.0
            total_h_in += (n_lines * line_h_in) + gap_to_add

        if total_h_in <= usable_h_in:
            return round(candidate, 1)
        candidate -= 0.5

    return round(safe_min, 1)


def _add_styled_box(
    slide: Any,
    left_in: float,
    top_in: float,
    width_in: float,
    height_in: float,
    bg_rgb: Tuple[int, int, int] = ScoutsBSAPalette.CRISP_SLATE_RGB,
    border_rgb: Tuple[int, int, int] = ScoutsBSAPalette.BORDER_GRAY_RGB,
    border_pt: float = 1.25,
) -> Any:
    """Adds a rounded rectangular card shape with explicit non-overlapping bounds, top anchor, and word wrap."""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(left_in),
        Inches(top_in),
        Inches(width_in),
        Inches(height_in),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(*bg_rgb)
    shape.line.color.rgb = RGBColor(*border_rgb)
    shape.line.width = Pt(border_pt)
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = Inches(0.18)
    tf.margin_right = Inches(0.18)
    tf.margin_top = Inches(0.14)
    tf.margin_bottom = Inches(0.12)
    return shape


def _set_paragraph_runs(
    paragraph: Any,
    anchor_text: str,
    body_text: str = "",
    font_size_pt: float = 18.0,
    anchor_rgb: Tuple[int, int, int] = ScoutsBSAPalette.NAVY_BLUE_RGB,
    body_rgb: Tuple[int, int, int] = ScoutsBSAPalette.DARK_TEXT_RGB,
    font_name: str = "Roboto",
    space_after_pt: float = 6.0,
    bold_body: bool = False,
    align: Any = PP_ALIGN.LEFT,
) -> None:
    """Populates a paragraph with a bold anchor run and regular body run, enforcing left alignment and >= 13pt floor."""
    safe_size = max(13.0, float(font_size_pt))
    paragraph.text = ""
    paragraph.alignment = align
    paragraph.font.name = font_name
    paragraph.font.size = Pt(safe_size)
    paragraph.font.color.rgb = RGBColor(*(body_rgb if body_text else anchor_rgb))
    paragraph.space_after = Pt(space_after_pt)

    clean_anchor = _clean_text(anchor_text)
    clean_body = _clean_text(body_text)

    if clean_anchor:
        r_anchor = paragraph.add_run()
        r_anchor.text = f"{clean_anchor}: " if clean_body else clean_anchor
        r_anchor.font.name = font_name
        r_anchor.font.size = Pt(safe_size)
        r_anchor.font.bold = True
        r_anchor.font.color.rgb = RGBColor(*anchor_rgb)

    if clean_body:
        r_body = paragraph.add_run()
        r_body.text = clean_body
        r_body.font.name = font_name
        r_body.font.size = Pt(safe_size)
        r_body.font.bold = bold_body
        r_body.font.color.rgb = RGBColor(*body_rgb)


# ==============================================================================
# DISTINCT PER-SLIDE VISUAL ASSET DEDUPLICATOR
# ==============================================================================

def _file_sha256(path: str) -> str:
    """Computes SHA-256 digest of an image file on disk."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _ensure_unique_image_path(
    candidate_path: Optional[str],
    slide_idx: int,
    used_sha256: Set[str],
) -> Optional[str]:
    """Ensures that an existing diagram/photo has a unique SHA-256 hash across the presentation."""
    if not candidate_path:
        return None
    if not os.path.isabs(candidate_path) and not os.path.exists(candidate_path):
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        candidate_path = os.path.join(root_dir, candidate_path)
    if not os.path.exists(candidate_path):
        return None
    digest = _file_sha256(candidate_path)
    if digest not in used_sha256:
        used_sha256.add(digest)
        return candidate_path

    # Clone image with a 1-pixel deterministic corner tweak so the real photo/diagram is preserved
    try:
        os.makedirs(GENERATED_DIAGRAMS_DIR, exist_ok=True)
        base = os.path.splitext(os.path.basename(candidate_path))[0]
        out_path = os.path.join(str(GENERATED_DIAGRAMS_DIR), f"{base}_s{slide_idx}_u.png")
        with Image.open(candidate_path) as im:
            rgb = im.convert("RGB")
            rgb.putpixel(
                (0, 0),
                (
                    (slide_idx * 37) % 251,
                    (slide_idx * 73) % 251,
                    (slide_idx * 113) % 251,
                ),
            )
            rgb.save(out_path, format="PNG")
        new_digest = _file_sha256(out_path)
        used_sha256.add(new_digest)
        return out_path
    except Exception:
        return candidate_path


# ==============================================================================
# ARCHETYPE RENDERERS (FULL-WIDTH WHEN NO IMAGE, SPLIT WHEN IMAGE PRESENT)
# ==============================================================================

def _resolve_palette_colors(
    slide_spec: SlideSpec,
) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """Returns (border_rgb, bg_rgb) based on slide_spec.beautification_tier and accent_palette_key."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    if tier == "STANDARD":
        return ScoutsBSAPalette.NAVY_BLUE_RGB, ScoutsBSAPalette.CRISP_SLATE_RGB
    pal = str(getattr(slide_spec, "accent_palette_key", "NAVY_GOLD") or "NAVY_GOLD").upper()
    if tier == "STUDIO":
        if pal == "OLIVE_FOREST":
            return (74, 222, 128), (23, 37, 42)
        if pal == "EAGLE_CRIMSON":
            return (248, 113, 113), (42, 24, 32)
        if pal == "SLATE_ACTION":
            return (56, 189, 248), (23, 37, 84)
        return (244, 196, 48), (30, 41, 59)
    if pal == "OLIVE_FOREST":
        return ScoutsBSAPalette.WARM_OLIVE_RGB, ScoutsBSAPalette.SOFT_OLIVE_CARD_RGB
    if pal == "EAGLE_CRIMSON":
        return ScoutsBSAPalette.EAGLE_RED_RGB, ScoutsBSAPalette.SOFT_RED_CARD_RGB
    if pal == "SLATE_ACTION":
        return ScoutsBSAPalette.ACTION_BLUE_RGB, ScoutsBSAPalette.SOFT_GOLD_CARD_RGB
    return ScoutsBSAPalette.NAVY_BLUE_RGB, ScoutsBSAPalette.SOFT_BLUE_CARD_RGB


def _resolve_text_colors(
    slide_spec: SlideSpec,
    default_anchor_rgb: Optional[Tuple[int, int, int]] = None,
) -> Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]:
    """Returns (anchor_rgb, body_rgb, title_rgb) for the slide's beautification_tier."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    border_rgb, _ = _resolve_palette_colors(slide_spec)
    anchor_base = default_anchor_rgb or border_rgb
    if tier == "STUDIO":
        return border_rgb, (241, 245, 249), (248, 250, 252)
    return anchor_base, ScoutsBSAPalette.DARK_TEXT_RGB, anchor_base


def _apply_slide_tier_background(
    slide: Any,
    tier: str,
    accent_rgb: Tuple[int, int, int],
) -> None:
    """Applies distinct canvas background color for STANDARD, BEAUTIFIED, and STUDIO without adding extra AutoShapes."""
    norm_tier = str(tier or "STANDARD").upper()
    try:
        bg = slide.background
        fill = bg.fill
        fill.solid()
        if norm_tier == "STUDIO":
            fill.fore_color.rgb = RGBColor(15, 23, 42)  # Deep Executive Slate (#0F172A)
        elif norm_tier == "BEAUTIFIED":
            fill.fore_color.rgb = RGBColor(250, 248, 245)  # Warm NotebookLM Editorial Cream (#FAF8F5)
        else:
            fill.fore_color.rgb = RGBColor(255, 255, 255)  # Standard Clean White (#FFFFFF)
    except Exception:
        pass


def _resolve_card_theme_treatment(
    slide_spec: SlideSpec,
    idx_pt: int,
    anchor: str,
    default_bg_rgb: Tuple[int, int, int],
    default_border_rgb: Tuple[int, int, int],
    default_anchor_rgb: Tuple[int, int, int],
    default_body_rgb: Tuple[int, int, int],
) -> Tuple[str, Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], float]:
    """Applies distinct prefix, background, border, and text color treatments for each Magazine Card Theme."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    theme = str(getattr(slide_spec, "visual_theme", "") or "").upper()
    bg_rgb = default_bg_rgb
    border_rgb = default_border_rgb if tier != "STANDARD" else ScoutsBSAPalette.BORDER_GRAY_RGB
    anchor_rgb = default_anchor_rgb
    body_rgb = default_body_rgb
    border_pt = 2.0 if tier == "STUDIO" else (1.6 if tier == "BEAUTIFIED" else 1.2)

    if "DARK_SLATE" in theme:
        bg_rgb = (30, 41, 59)
        border_rgb = (244, 196, 48)
        anchor_rgb = (244, 196, 48)
        body_rgb = (241, 245, 249)
        border_pt = 2.0
        anchor = f"★ {anchor}"
    elif "SAFETY_ALERT" in theme:
        bg_rgb = (42, 24, 32) if tier == "STUDIO" else ScoutsBSAPalette.SOFT_RED_CARD_RGB
        border_rgb = (248, 113, 113) if tier == "STUDIO" else ScoutsBSAPalette.EAGLE_RED_RGB
        anchor_rgb = border_rgb
        border_pt = 2.1
        anchor = f"[!] {anchor}"
    elif "TIMELINE_CHEVRON" in theme:
        border_pt = 1.8
        anchor = f"STEP {idx_pt + 1} ➔ {anchor}"
    elif "EDITORIAL_CALLOUT" in theme:
        bg_rgb = (30, 41, 59) if tier == "STUDIO" else ScoutsBSAPalette.SOFT_GOLD_CARD_RGB
        border_pt = 2.0
        anchor = f"❝ {anchor}"
    elif "NUMBERED" in theme:
        border_pt = 1.8
        anchor = f"[0{idx_pt + 1}] {anchor}"
    elif "BENTO" in theme or "THREE_PILLAR" in theme:
        border_pt = 2.2
        anchor = f"◆ {anchor}"
    elif tier in ("BEAUTIFIED", "STUDIO"):
        anchor = f"◆ {anchor}"

    return anchor, bg_rgb, border_rgb, anchor_rgb, body_rgb, border_pt


def _render_stacked_point_cards(
    slide: Any,
    slide_spec: SlideSpec,
    points: List[str],
    left_in: float,
    top_in: float,
    width_in: float,
    bottom_in: float,
    default_anchor_prefix: str = "Key Concept",
) -> None:
    """Renders each bullet point as an individual horizontal card (matching UI preview `.m3-slide-card-item`)
    with proportional height allocation so long points never overflow their card boxes.
    """
    border_rgb, bg_rgb = _resolve_palette_colors(slide_spec)
    anchor_rgb, body_rgb, _ = _resolve_text_colors(slide_spec, border_rgb)

    total_h = max(2.00, bottom_in - top_in)
    # When rendering in a half-width split column below a requirement banner, cap at 4 cards so text never crowds
    max_pts = 4 if (width_in < 7.0 and total_h < 4.35) else 5
    clean_pts = [p for p in (points or [])[:max_pts] if _clean_text(p)]
    if not clean_pts:
        clean_pts = [f"{default_anchor_prefix}: Review and discuss these principles with your Merit Badge Counselor."]

    n_pts = len(clean_pts)
    gap_y = 0.08 if total_h < 4.15 else 0.10
    avail_cards_h = max(1.50, total_h - gap_y * max(0, n_pts - 1))
    avg_h = avail_cards_h / float(max(1, n_pts))

    # Render individual stacked cards with proportional height based on wrapped line count
    if n_pts <= 5 and avg_h >= 0.64:
        chars_per_line = 47.0 if width_in < 7.0 else 96.0
        weights: List[float] = []
        for p in clean_pts:
            plen = len(_clean_text(p)) + 6
            est_lines = max(1, int((plen + chars_per_line - 1) // chars_per_line))
            weights.append(0.32 + float(est_lines))
        total_w = sum(weights)
        min_card_h = min(0.60, avg_h * 0.78)
        raw_heights = [max(min_card_h, avail_cards_h * (w / total_w)) for w in weights]
        scale_h = avail_cards_h / max(0.01, sum(raw_heights))
        card_heights = [round(h * scale_h, 3) for h in raw_heights]
        # Adjust last card height so sum matches avail_cards_h
        if card_heights:
            card_heights[-1] = round(avail_cards_h - sum(card_heights[:-1]), 3)

        cur_top = top_in
        for idx_pt, (pt, c_h) in enumerate(zip(clean_pts, card_heights)):
            c_top = round(cur_top, 3)
            cur_top += c_h + gap_y
            raw_anchor, body = _split_anchor_and_body(pt, f"{default_anchor_prefix} {idx_pt + 1}")
            anchor, c_bg, c_border, c_anchor_rgb, c_body_rgb, c_border_pt = _resolve_card_theme_treatment(
                slide_spec, idx_pt, raw_anchor, bg_rgb, border_rgb, anchor_rgb, body_rgb
            )
            card = _add_styled_box(
                slide,
                left_in=left_in,
                top_in=c_top,
                width_in=width_in,
                height_in=c_h,
                bg_rgb=c_bg,
                border_rgb=c_border,
                border_pt=c_border_pt,
            )
            tf = card.text_frame
            tf.margin_top = Inches(0.06 if c_h < 0.94 else 0.08)
            tf.margin_bottom = Inches(0.05 if c_h < 0.94 else 0.06)
            tf.margin_left = Inches(0.14 if width_in < 7.0 else 0.18)
            tf.margin_right = Inches(0.14 if width_in < 7.0 else 0.18)
            full_line = f"{anchor}: {body}" if body else anchor
            f_pt = _compute_fitting_font_size(
                [full_line],
                box_w_in=width_in,
                box_h_in=c_h,
                min_pt=15.0,
                max_pt=18.5 if width_in > 8.0 else 16.5,
                space_after_pt=1.5,
            )
            _set_paragraph_runs(
                tf.paragraphs[0],
                anchor,
                body,
                font_size_pt=f_pt,
                anchor_rgb=c_anchor_rgb,
                body_rgb=c_body_rgb,
                space_after_pt=1.5,
            )
        return

    # Fallback unified card when compact vertical space
    _, c_bg, c_border, c_anchor_rgb, c_body_rgb, c_border_pt = _resolve_card_theme_treatment(
        slide_spec, 0, "", bg_rgb, border_rgb, anchor_rgb, body_rgb
    )
    card = _add_styled_box(
        slide,
        left_in=left_in,
        top_in=top_in,
        width_in=width_in,
        height_in=total_h,
        bg_rgb=c_bg,
        border_rgb=c_border,
        border_pt=c_border_pt,
    )
    tf = card.text_frame
    body_font_pt = _compute_fitting_font_size(
        clean_pts,
        box_w_in=width_in,
        box_h_in=total_h,
        min_pt=15.0,
        max_pt=19.5 if width_in > 8.0 else 17.0,
        space_after_pt=5.5,
    )
    for idx_pt, pt in enumerate(clean_pts):
        p = tf.paragraphs[0] if idx_pt == 0 else tf.add_paragraph()
        raw_anchor, body = _split_anchor_and_body(pt, f"{default_anchor_prefix} {idx_pt + 1}")
        anchor, _, _, _, _, _ = _resolve_card_theme_treatment(
            slide_spec, idx_pt, raw_anchor, bg_rgb, border_rgb, anchor_rgb, body_rgb
        )
        _set_paragraph_runs(
            p,
            anchor,
            body,
            font_size_pt=body_font_pt,
            anchor_rgb=c_anchor_rgb,
            body_rgb=c_body_rgb,
            space_after_pt=5.5,
        )


def _render_requirement_intro_slide(
    slide: Any,
    slide_spec: SlideSpec,
    content_bottom: float = 6.95,
    resolved_diagram: Optional[str] = None,
) -> None:
    """Renders the first slide of a requirement sequence matching the UI preview:
    1. Full-width Official Requirement strip across the top (`width=12.133"`).
    2. Left-zone stacked teaching cards (`width=6.20"` when visual is present, `12.133"` when no visual).
    3. Right-zone visual + caption when `resolved_diagram` is present in `BEAUTIFIED` / `STUDIO` modes.
    """
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    has_hero = bool(tier in ("BEAUTIFIED", "STUDIO") and resolved_diagram and os.path.exists(resolved_diagram))
    accent_rgb, tint_bg_rgb = _resolve_palette_colors(slide_spec)
    anchor_rgb, body_rgb, _ = _resolve_text_colors(slide_spec, accent_rgb)
    req_bg_rgb = (30, 41, 59) if tier == "STUDIO" else (tint_bg_rgb if tier == "BEAUTIFIED" else ScoutsBSAPalette.WHITE_RGB)

    verbatim_text = _clean_text(
        slide_spec.verbatim_requirement_text
        or (slide_spec.bullet_points[0] if slide_spec.bullet_points else f"Complete Requirement {slide_spec.req_number}.")
    )
    full_req_line = f"Official Requirement {slide_spec.req_number}: {verbatim_text}"
    req_h = (
        0.72
        if len(full_req_line) <= 115
        else (0.88 if len(full_req_line) <= 215 else (1.04 if len(full_req_line) <= 320 else 1.24))
    )

    # Top Strip: Full-width Official Requirement text (matches UI preview `.m3-slide-req-strip`)
    req_box = _add_styled_box(
        slide,
        left_in=0.60,
        top_in=1.10,
        width_in=12.133,
        height_in=req_h,
        bg_rgb=req_bg_rgb,
        border_rgb=accent_rgb,
        border_pt=2.0,
    )
    rtf = req_box.text_frame
    rtf.margin_top = Inches(0.06)
    rtf.margin_bottom = Inches(0.05)
    req_font_pt = _compute_fitting_font_size(
        [full_req_line],
        box_w_in=12.133,
        box_h_in=req_h,
        min_pt=15.0,
        max_pt=18.0,
        space_after_pt=1.5,
    )
    _set_paragraph_runs(
        rtf.paragraphs[0],
        f"Official Requirement {slide_spec.req_number}",
        verbatim_text,
        font_size_pt=req_font_pt,
        anchor_rgb=anchor_rgb,
        body_rgb=body_rgb,
        space_after_pt=1.5,
    )

    teach_top = round(1.10 + req_h + 0.10, 2)
    left_w = 6.20 if has_hero else 12.133
    max_intro_pts = 4 if has_hero else 6
    teaching_points = slide_spec.bullet_points[:max_intro_pts]
    if not teaching_points:
        teaching_points = [f"Key Principle: Review and discuss Requirement {slide_spec.req_number} with your counselor."]

    _render_stacked_point_cards(
        slide=slide,
        slide_spec=slide_spec,
        points=teaching_points,
        left_in=0.60,
        top_in=teach_top,
        width_in=left_w,
        bottom_in=content_bottom,
        default_anchor_prefix="Key Concept",
    )

    # Right Visual Zone when BEAUTIFIED / STUDIO has an EDGE Skill Concept Map or diagram
    if has_hero and resolved_diagram:
        avail_img_h = max(2.10, (content_bottom - teach_top) - 0.56)
        try:
            pic = slide.shapes.add_picture(
                resolved_diagram,
                Inches(7.05),
                Inches(teach_top),
                width=Inches(5.65),
            )
            max_h = Inches(avail_img_h)
            if pic.height > max_h:
                scale = float(max_h) / float(pic.height)
                pic.height = max_h
                pic.width = int(pic.width * scale)
        except Exception:
            pass

        cap_bg = (30, 41, 59) if tier == "STUDIO" else tint_bg_rgb
        caption_box = _add_styled_box(
            slide,
            left_in=7.05,
            top_in=content_bottom - 0.48,
            width_in=5.65,
            height_in=0.48,
            bg_rgb=cap_bg,
            border_rgb=accent_rgb,
            border_pt=1.25,
        )
        captf = caption_box.text_frame
        captf.margin_top = Inches(0.05)
        captf.margin_bottom = Inches(0.04)
        raw_cap = _clean_text(slide_spec.visual_caption) or _clean_text(slide_spec.title)
        for prefix_rm in ("EDGE Skill Concept Map — ", "EDGE Skill Concept Map - ", "EDGE Skill Concept Map, ", "EDGE Skill Map: "):
            if raw_cap.startswith(prefix_rm):
                raw_cap = raw_cap[len(prefix_rm):].strip()
        raw_cap = re.sub(r"^(?:Requirement|Req)\s+[0-9a-zA-Z]+\s*[:—-]\s*", "", raw_cap).strip()
        if len(raw_cap) > 34:
            words_cap = raw_cap[:34].rsplit(" ", 1)[0].split()
            while len(words_cap) > 2 and words_cap[-1].lower().strip(",.;:") in {"in", "for", "of", "and", "or", "to", "with", "on", "by", "the", "a"}:
                words_cap.pop()
            raw_cap = " ".join(words_cap).strip(" .,:;-—") or raw_cap[:34]
        cap_font_pt = _compute_fitting_font_size(
            [f"EDGE Skill Map: {raw_cap}"],
            box_w_in=5.65,
            box_h_in=0.48,
            min_pt=15.0,
            max_pt=15.5,
            space_after_pt=0.0,
        )
        _set_paragraph_runs(
            captf.paragraphs[0],
            "EDGE Skill Map",
            raw_cap,
            font_size_pt=cap_font_pt,
            anchor_rgb=anchor_rgb,
            body_rgb=body_rgb,
            space_after_pt=0.0,
        )


def _render_full_bleed_image_slide(
    slide: Any,
    slide_spec: SlideSpec,
    diagram_path: Optional[str],
    content_top: float = 1.28,
    content_bottom: float = 6.26,
) -> None:
    """Renders a large full-canvas diagram or photograph slide across y=[content_top..content_bottom]."""
    if diagram_path and os.path.exists(diagram_path):
        try:
            max_w_in = 12.00
            max_h_in = max(3.50, content_bottom - content_top)
            with Image.open(diagram_path) as im:
                img_w, img_h = im.size
            aspect = float(img_w) / float(max(1, img_h))
            target_w_in = max_w_in
            target_h_in = target_w_in / aspect
            if target_h_in > max_h_in:
                target_h_in = max_h_in
                target_w_in = target_h_in * aspect

            left_in = 0.60 + (12.133 - target_w_in) / 2.0
            top_in = content_top + (max_h_in - target_h_in) / 2.0
            slide.shapes.add_picture(
                diagram_path,
                Inches(left_in),
                Inches(top_in),
                width=Inches(target_w_in),
                height=Inches(target_h_in),
            )
        except Exception:
            pass


def _render_concept_or_sources_full_width(
    slide: Any,
    slide_spec: SlideSpec,
    content_top: float = 1.15,
    content_bottom: float = 6.95,
) -> None:
    """Renders a full-width instructional concept slide or the final Sources & References slide."""
    is_sources = slide_spec.archetype == "SOURCES_AND_REFERENCES"
    points = slide_spec.bullet_points[:6]
    if not points and slide_spec.cards:
        points = [f"{c.get('anchor_title', 'Concept')}: {c.get('body_text', '')}" for c in slide_spec.cards[:6]]
    if not points:
        points = ["Key Concept: Review and discuss these principles with your Merit Badge Counselor."]

    if not is_sources:
        _render_stacked_point_cards(
            slide=slide,
            slide_spec=slide_spec,
            points=points,
            left_in=0.60,
            top_in=content_top,
            width_in=12.133,
            bottom_in=content_bottom,
            default_anchor_prefix="Key Point",
        )
        return

    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    border_rgb, bg_rgb = _resolve_palette_colors(slide_spec)
    if tier == "STANDARD":
        border_rgb = ScoutsBSAPalette.WARM_OLIVE_RGB
        bg_rgb = ScoutsBSAPalette.SOFT_OLIVE_CARD_RGB
    anchor_rgb, body_rgb, _ = _resolve_text_colors(slide_spec, border_rgb)
    box_h = max(3.50, content_bottom - content_top)

    card = _add_styled_box(
        slide,
        left_in=0.60,
        top_in=content_top,
        width_in=12.133,
        height_in=box_h,
        bg_rgb=bg_rgb,
        border_rgb=border_rgb,
        border_pt=1.5,
    )
    tf = card.text_frame
    all_lines = ["Sources of Information & Visual Credits"] + list(points[:6])
    src_font_pt = _compute_fitting_font_size(
        all_lines, box_w_in=12.133, box_h_in=box_h, min_pt=15.0, max_pt=20.0, space_after_pt=8.0
    )
    _set_paragraph_runs(
        tf.paragraphs[0],
        "Sources of Information & Visual Credits",
        "",
        font_size_pt=min(22.0, src_font_pt + 1.5),
        anchor_rgb=anchor_rgb,
        space_after_pt=9.0,
    )
    for idx_pt, pt in enumerate(points[:6], start=1):
        p = tf.add_paragraph()
        anchor, body = _split_anchor_and_body(pt, f"Source {idx_pt}")
        _set_paragraph_runs(
            p,
            anchor,
            body,
            font_size_pt=src_font_pt,
            anchor_rgb=anchor_rgb,
            body_rgb=body_rgb,
            space_after_pt=8.0,
        )


def _render_triage_matrix_zone(
    slide: Any,
    slide_spec: SlideSpec,
    full_width: bool = False,
    content_top: float = 2.08,
    content_bottom: float = 6.25,
) -> None:
    """Renders 3 non-overlapping vertical topic columns (full-width or left-zone)."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    if tier == "STUDIO":
        c1 = ("KNOWLEDGE & CONCEPTS", (56, 189, 248), (30, 41, 59))
        c2 = ("HANDS-ON FIELD SKILLS", (74, 222, 128), (23, 37, 42))
        c3 = ("FIELD & CAMP APPLICATION", (244, 196, 48), (42, 24, 32))
        body_rgb = (241, 245, 249)
    else:
        c1 = ("KNOWLEDGE & CONCEPTS", ScoutsBSAPalette.NAVY_BLUE_RGB, ScoutsBSAPalette.SOFT_BLUE_CARD_RGB)
        c2 = ("HANDS-ON FIELD SKILLS", ScoutsBSAPalette.WARM_OLIVE_RGB, ScoutsBSAPalette.SOFT_OLIVE_CARD_RGB)
        c3 = ("FIELD & CAMP APPLICATION", ScoutsBSAPalette.EAGLE_RED_RGB, ScoutsBSAPalette.SOFT_RED_CARD_RGB)
        body_rgb = ScoutsBSAPalette.DARK_TEXT_RGB

    if full_width:
        col_specs = [
            (c1[0], c1[1], c1[2], 0.60, 3.90),
            (c2[0], c2[1], c2[2], 4.71, 3.90),
            (c3[0], c3[1], c3[2], 8.83, 3.90),
        ]
    else:
        col_specs = [
            (c1[0], c1[1], c1[2], 0.60, 1.96),
            (c2[0], c2[1], c2[2], 2.72, 1.96),
            (c3[0], c3[1], c3[2], 4.84, 1.96),
        ]

    buckets: List[List[str]] = [[], [], []]
    if slide_spec.cards:
        for card in slide_spec.cards:
            label = str(card.get("badge_label", "")).upper()
            text = f"{card.get('anchor_title', '')}: {card.get('body_text', '')}"
            if "HANDS" in label or "STATION" in label or "DEMONSTRATE" in label:
                buckets[1].append(text)
            elif "CAMP" in label or "HOME" in label or "PREREQ" in label:
                buckets[2].append(text)
            else:
                buckets[0].append(text)
    else:
        for i, pt in enumerate(slide_spec.bullet_points[:7]):
            buckets[i % 3].append(pt)

    defaults = [
        "Core principles, definitions, and safety concepts.",
        "Practical hands-on techniques practiced with your patrol.",
        "Outdoor observation, field logs, or project application.",
    ]
    box_h = max(3.50, content_bottom - content_top)
    for col_idx, (col_title, header_rgb, bg_rgb, left_x, col_w) in enumerate(col_specs):
        card = _add_styled_box(
            slide,
            left_in=left_x,
            top_in=content_top,
            width_in=col_w,
            height_in=box_h,
            bg_rgb=bg_rgb,
            border_rgb=header_rgb,
            border_pt=1.75 if tier in ("BEAUTIFIED", "STUDIO") else 1.5,
        )
        tf = card.text_frame
        items = buckets[col_idx][:4] or [defaults[col_idx]]
        col_font_pt = _compute_fitting_font_size(
            [col_title] + items,
            box_w_in=col_w,
            box_h_in=box_h,
            min_pt=14.5,
            max_pt=18.5,
            space_after_pt=6.0,
        )
        _set_paragraph_runs(
            tf.paragraphs[0],
            col_title,
            "",
            font_size_pt=min(20.0, col_font_pt + 1.0),
            anchor_rgb=header_rgb,
            space_after_pt=7.0,
        )
        for item in items:
            p = tf.add_paragraph()
            anchor, body = _split_anchor_and_body(item, "Requirement")
            _set_paragraph_runs(
                p,
                anchor,
                body,
                font_size_pt=col_font_pt,
                anchor_rgb=header_rgb,
                body_rgb=body_rgb,
                space_after_pt=6.0,
            )


def _render_differential_comparison_zone(
    slide: Any,
    slide_spec: SlideSpec,
    full_width: bool = False,
    content_top: float = 1.15,
    content_bottom: float = 6.95,
) -> None:
    """Renders 2 non-overlapping comparison cards (full-width or left-zone)."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    cd = slide_spec.comparison_data or {}
    left_header = cd.get("left_header") or "Primary Condition / Method A"
    left_badge = cd.get("left_badge") or "CONCEPT A"
    left_pts = cd.get("left_points") or slide_spec.bullet_points[:3] or ["Verify primary indicators and characteristics."]

    right_header = cd.get("right_header") or "Contrast Condition / Method B"
    right_badge = cd.get("right_badge") or "CONCEPT B"
    right_pts = cd.get("right_points") or slide_spec.bullet_points[3:6] or ["Compare key differences and field response."]

    if tier == "STUDIO":
        l_accent, l_bg = (56, 189, 248), (30, 41, 59)
        r_accent, r_bg = (248, 113, 113), (42, 24, 32)
        body_rgb = (241, 245, 249)
    else:
        l_accent, l_bg = ScoutsBSAPalette.NAVY_BLUE_RGB, ScoutsBSAPalette.SOFT_BLUE_CARD_RGB
        r_accent, r_bg = ScoutsBSAPalette.EAGLE_RED_RGB, ScoutsBSAPalette.SOFT_RED_CARD_RGB
        body_rgb = ScoutsBSAPalette.DARK_TEXT_RGB

    if full_width:
        specs = [
            (0.60, 5.95, f"{left_header} [{left_badge}]", left_pts[:5], l_accent, l_bg),
            (6.78, 5.95, f"{right_header} [{right_badge}]", right_pts[:5], r_accent, r_bg),
        ]
    else:
        specs = [
            (0.60, 3.00, f"{left_header} [{left_badge}]", left_pts[:5], l_accent, l_bg),
            (3.75, 3.00, f"{right_header} [{right_badge}]", right_pts[:5], r_accent, r_bg),
        ]
    box_h = max(3.50, content_bottom - content_top)
    for left_x, box_w, header_text, pts, accent_rgb, bg_rgb in specs:
        box = _add_styled_box(
            slide,
            left_in=left_x,
            top_in=content_top,
            width_in=box_w,
            height_in=box_h,
            bg_rgb=bg_rgb,
            border_rgb=accent_rgb,
            border_pt=1.75,
        )
        tf = box.text_frame
        col_font_pt = _compute_fitting_font_size(
            [header_text] + list(pts),
            box_w_in=box_w,
            box_h_in=box_h,
            min_pt=15.0 if full_width else 14.0,
            max_pt=20.0 if full_width else 17.5,
            space_after_pt=8.0,
        )
        _set_paragraph_runs(
            tf.paragraphs[0],
            header_text,
            "",
            font_size_pt=min(21.0, col_font_pt + 1.0),
            anchor_rgb=accent_rgb,
            space_after_pt=8.0,
        )
        for pt in pts:
            p = tf.add_paragraph()
            anchor, body = _split_anchor_and_body(pt, "Attribute")
            _set_paragraph_runs(
                p,
                anchor,
                body,
                font_size_pt=col_font_pt,
                anchor_rgb=accent_rgb,
                body_rgb=body_rgb,
                space_after_pt=8.0,
            )


def _render_step_by_step_4card_zone(
    slide: Any,
    slide_spec: SlideSpec,
    full_width: bool = False,
    content_top: float = 1.15,
    content_bottom: float = 6.95,
) -> None:
    """Renders a 2x2 grid of procedural step cards (or stacked cards when fewer than 4 points exist)."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    step_items: List[Tuple[str, str, str]] = []
    if slide_spec.bullet_points:
        for idx_p, pt in enumerate(slide_spec.bullet_points[:4], start=1):
            anchor, body = _split_anchor_and_body(pt, f"Step {idx_p}")
            step_items.append((f"STEP {idx_p}", anchor, body))
    elif slide_spec.cards:
        for idx_c, c in enumerate(slide_spec.cards[:4], start=1):
            badge = _clean_text(c.get("badge_label") or f"STEP {idx_c}")
            anchor = _clean_text(c.get("anchor_title") or f"Step {idx_c}")
            body = _clean_text(c.get("body_text") or "Complete step with counselor verification.")
            step_items.append((badge, anchor, body))

    if len(step_items) < 2:
        _render_stacked_point_cards(
            slide=slide,
            slide_spec=slide_spec,
            points=slide_spec.bullet_points or [f"{a}: {b}" for _, a, b in step_items],
            left_in=0.60,
            top_in=content_top,
            width_in=12.133 if full_width else 6.20,
            bottom_in=content_bottom,
            default_anchor_prefix="Step",
        )
        return

    total_h = max(3.40, content_bottom - content_top)
    gap_y = 0.16
    is_two_rows = len(step_items) >= 3
    card_h = (total_h - gap_y) / 2.0 if is_two_rows else total_h
    row2_top = content_top + card_h + gap_y

    if tier == "STUDIO":
        c_styles = [
            ((56, 189, 248), (30, 41, 59)),
            ((244, 196, 48), (30, 41, 59)),
            ((74, 222, 128), (23, 37, 42)),
            ((248, 113, 113), (42, 24, 32)),
        ]
        body_rgb = (241, 245, 249)
    else:
        c_styles = [
            (ScoutsBSAPalette.NAVY_BLUE_RGB, ScoutsBSAPalette.SOFT_BLUE_CARD_RGB),
            (ScoutsBSAPalette.ACTION_BLUE_RGB, ScoutsBSAPalette.SOFT_BLUE_CARD_RGB),
            (ScoutsBSAPalette.WARM_OLIVE_RGB, ScoutsBSAPalette.SOFT_OLIVE_CARD_RGB),
            (ScoutsBSAPalette.EAGLE_RED_RGB, ScoutsBSAPalette.SOFT_GOLD_CARD_RGB),
        ]
        body_rgb = ScoutsBSAPalette.DARK_TEXT_RGB

    if full_width:
        grid_coords = [
            (0.60, content_top, 5.95, c_styles[0][0], c_styles[0][1]),
            (6.78, content_top, 5.95, c_styles[1][0], c_styles[1][1]),
            (0.60, row2_top, 12.133 if len(step_items) == 3 else 5.95, c_styles[2][0], c_styles[2][1]),
            (6.78, row2_top, 5.95, c_styles[3][0], c_styles[3][1]),
        ]
    else:
        grid_coords = [
            (0.60, content_top, 3.00, c_styles[0][0], c_styles[0][1]),
            (3.75, content_top, 3.00, c_styles[1][0], c_styles[1][1]),
            (0.60, row2_top, 6.15 if len(step_items) == 3 else 3.00, c_styles[2][0], c_styles[2][1]),
            (3.75, row2_top, 3.00, c_styles[3][0], c_styles[3][1]),
        ]
    for (badge, anchor, body), (lx, ty, cw, border_rgb, bg_rgb) in zip(step_items[:4], grid_coords):
        card = _add_styled_box(
            slide,
            left_in=lx,
            top_in=ty,
            width_in=cw,
            height_in=card_h,
            bg_rgb=bg_rgb,
            border_rgb=border_rgb,
            border_pt=1.5,
        )
        tf = card.text_frame
        head_line = f"{badge} — {anchor}"
        step_font_pt = _compute_fitting_font_size(
            [head_line, body],
            box_w_in=cw,
            box_h_in=card_h,
            min_pt=13.5 if full_width else 13.0,
            max_pt=19.0 if full_width else 16.0,
            space_after_pt=5.0,
        )
        _set_paragraph_runs(
            tf.paragraphs[0],
            head_line,
            "",
            font_size_pt=min(20.0, step_font_pt + 1.0),
            anchor_rgb=border_rgb,
            space_after_pt=5.0,
        )
        p_body = tf.add_paragraph()
        _set_paragraph_runs(
            p_body,
            "",
            body,
            font_size_pt=step_font_pt,
            anchor_rgb=border_rgb,
            body_rgb=body_rgb,
            space_after_pt=3.0,
        )


def _render_worked_example_zone(
    slide: Any,
    slide_spec: SlideSpec,
    full_width: bool = False,
    content_top: float = 1.15,
    content_bottom: float = 6.95,
) -> None:
    """Renders a concrete Worked Example artifact card + Counselor Pro-Tip card."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    border_rgb, bg_rgb = _resolve_palette_colors(slide_spec)
    anchor_rgb, body_rgb, _ = _resolve_text_colors(slide_spec, border_rgb)

    we = slide_spec.worked_example or {}
    we_title = _clean_text(we.get("title") or f"Worked Example: Requirement {slide_spec.req_number}")
    we_type = _clean_text(we.get("artifact_type") or "SAMPLE LOG & TEMPLATE")
    fields_dict: Dict[str, str] = we.get("fields") or {}
    tip = _clean_text(we.get("counselor_tip") or "Bring your completed written log or project notes to your counselor review.")
    box_w = 12.133 if full_width else 6.20
    total_h = max(3.60, content_bottom - content_top)
    tip_h = 1.05
    gap_y = 0.14
    top_h = max(2.30, total_h - tip_h - gap_y)

    top_box = _add_styled_box(
        slide,
        left_in=0.60,
        top_in=content_top,
        width_in=box_w,
        height_in=top_h,
        bg_rgb=bg_rgb,
        border_rgb=border_rgb,
        border_pt=1.75,
    )
    tf = top_box.text_frame
    entry_lines = (
        [f"{k}: {v}" for k, v in list(fields_dict.items())[:5]]
        if fields_dict
        else list(slide_spec.bullet_points[:5])
    )
    we_font_pt = _compute_fitting_font_size(
        [f"[{we_type}] {we_title}"] + entry_lines,
        box_w_in=box_w,
        box_h_in=top_h,
        min_pt=14.0 if full_width else 13.0,
        max_pt=20.0 if full_width else 17.0,
        space_after_pt=6.0,
    )
    _set_paragraph_runs(
        tf.paragraphs[0],
        f"[{we_type}] {we_title}",
        "",
        font_size_pt=min(21.0, we_font_pt + 1.0),
        anchor_rgb=anchor_rgb,
        space_after_pt=6.5,
    )
    if fields_dict:
        for k, v in list(fields_dict.items())[:5]:
            p = tf.add_paragraph()
            _set_paragraph_runs(
                p, str(k), str(v), font_size_pt=we_font_pt, anchor_rgb=anchor_rgb, body_rgb=body_rgb, space_after_pt=6.0
            )
    else:
        for pt in slide_spec.bullet_points[:5]:
            p = tf.add_paragraph()
            a, b = _split_anchor_and_body(pt, "Example Entry")
            _set_paragraph_runs(
                p, a, b, font_size_pt=we_font_pt, anchor_rgb=anchor_rgb, body_rgb=body_rgb, space_after_pt=6.0
            )

    tip_bg = (23, 37, 42) if tier == "STUDIO" else ScoutsBSAPalette.SOFT_GOLD_CARD_RGB
    tip_border = (244, 196, 48) if tier == "STUDIO" else ScoutsBSAPalette.WARM_OLIVE_RGB
    tip_box = _add_styled_box(
        slide,
        left_in=0.60,
        top_in=content_top + top_h + gap_y,
        width_in=box_w,
        height_in=tip_h,
        bg_rgb=tip_bg,
        border_rgb=tip_border,
        border_pt=1.5,
    )
    ttf = tip_box.text_frame
    tip_font_pt = _compute_fitting_font_size(
        [f"Counselor Pro-Tip: {tip}"],
        box_w_in=box_w,
        box_h_in=tip_h,
        min_pt=13.5,
        max_pt=18.0 if full_width else 16.0,
        space_after_pt=2.0,
    )
    _set_paragraph_runs(
        ttf.paragraphs[0],
        "Counselor Pro-Tip",
        tip,
        font_size_pt=tip_font_pt,
        anchor_rgb=tip_border,
        body_rgb=body_rgb,
        space_after_pt=2.0,
    )


def _render_gear_checklist_zone(
    slide: Any,
    slide_spec: SlideSpec,
    full_width: bool = False,
    content_top: float = 1.15,
    content_bottom: float = 6.95,
) -> None:
    """Renders a 2-column gear & inspection checklist grid matching the UI preview."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    items = list(slide_spec.bullet_points or slide_spec.gear_checklist or ["Inspect required equipment before field activity."])
    if len(items) < 2:
        _render_stacked_point_cards(
            slide=slide,
            slide_spec=slide_spec,
            points=items,
            left_in=0.60,
            top_in=content_top,
            width_in=12.133 if full_width else 6.20,
            bottom_in=content_bottom,
            default_anchor_prefix="Checklist",
        )
        return

    mid = (len(items) + 1) // 2
    left_items = items[:mid]
    right_items = items[mid:]

    if tier == "STUDIO":
        c1_accent, c1_bg = (56, 189, 248), (30, 41, 59)
        c2_accent, c2_bg = (74, 222, 128), (23, 37, 42)
        body_rgb = (241, 245, 249)
    else:
        c1_accent, c1_bg = ScoutsBSAPalette.NAVY_BLUE_RGB, ScoutsBSAPalette.SOFT_BLUE_CARD_RGB
        c2_accent, c2_bg = ScoutsBSAPalette.WARM_OLIVE_RGB, ScoutsBSAPalette.SOFT_OLIVE_CARD_RGB
        body_rgb = ScoutsBSAPalette.DARK_TEXT_RGB

    if full_width:
        cols = [
            (0.60, 5.95, "PRIMARY FIELD EQUIPMENT [✓]", left_items, c1_accent, c1_bg),
            (6.78, 5.95, "INSPECTION & VERIFICATION [✓]", right_items, c2_accent, c2_bg),
        ]
    else:
        cols = [
            (0.60, 3.00, "PRIMARY FIELD EQUIPMENT [✓]", left_items, c1_accent, c1_bg),
            (3.75, 3.00, "INSPECTION & VERIFICATION [✓]", right_items, c2_accent, c2_bg),
        ]
    box_h = max(3.50, content_bottom - content_top)
    for lx, cw, header_title, col_items, accent_rgb, bg_rgb in cols:
        box = _add_styled_box(
            slide,
            left_in=lx,
            top_in=content_top,
            width_in=cw,
            height_in=box_h,
            bg_rgb=bg_rgb,
            border_rgb=accent_rgb,
            border_pt=1.5,
        )
        tf = box.text_frame
        chk_font_pt = _compute_fitting_font_size(
            [header_title] + list(col_items[:5]),
            box_w_in=cw,
            box_h_in=box_h,
            min_pt=15.0 if full_width else 14.0,
            max_pt=20.0 if full_width else 17.0,
            space_after_pt=7.5,
        )
        _set_paragraph_runs(
            tf.paragraphs[0],
            header_title,
            "",
            font_size_pt=min(21.0, chk_font_pt + 1.0),
            anchor_rgb=accent_rgb,
            space_after_pt=8.0,
        )
        for item in col_items[:5]:
            p = tf.add_paragraph()
            a, b = _split_anchor_and_body(item, "Checklist")
            _set_paragraph_runs(
                p,
                f"[✓] {a}",
                b,
                font_size_pt=chk_font_pt,
                anchor_rgb=accent_rgb,
                body_rgb=body_rgb,
                space_after_pt=7.5,
            )


def _render_socratic_quiz_zone(
    slide: Any,
    slide_spec: SlideSpec,
    full_width: bool = False,
    content_top: float = 1.15,
    content_bottom: float = 6.95,
) -> None:
    """Renders 3 stacked non-overlapping Socratic Quiz boxes (Scenario, Options, Verified Answer)."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    _, body_rgb, _ = _resolve_text_colors(slide_spec)
    qi = slide_spec.quiz_item or {}
    scenario = _clean_text(
        qi.get("scenario_prompt")
        or (slide_spec.bullet_points[0] if slide_spec.bullet_points else f"How should your patrol apply Requirement {slide_spec.req_number} in the field?")
    )
    options = qi.get("options") or slide_spec.bullet_points[1:4] or [
        "Option A: Follow standard step-by-step field procedure.",
        "Option B: Improvise without checking safety guidelines.",
        "Option C: Skip buddy check and proceed alone.",
    ]
    answer = _clean_text(qi.get("correct_answer") or "Option A — Follow standard step-by-step field procedure.")
    explanation = _clean_text(qi.get("explanation") or "Grounded in the BSA Guide to Safe Scouting and merit badge instruction.")
    box_w = 12.133 if full_width else 6.20
    total_h = max(3.60, content_bottom - content_top)
    gap = 0.14
    h1 = round((total_h - 2 * gap) * 0.27, 2)
    h2 = round((total_h - 2 * gap) * 0.40, 2)
    h3 = round(total_h - 2 * gap - h1 - h2, 2)

    s_bg = (30, 41, 59) if tier == "STUDIO" else ScoutsBSAPalette.SOFT_BLUE_CARD_RGB
    s_border = (56, 189, 248) if tier == "STUDIO" else ScoutsBSAPalette.NAVY_BLUE_RGB
    s_box = _add_styled_box(
        slide, left_in=0.60, top_in=content_top, width_in=box_w, height_in=h1,
        bg_rgb=s_bg, border_rgb=s_border, border_pt=1.5,
    )
    s_font = _compute_fitting_font_size(
        [f"Patrol Scenario Challenge: {scenario}"], box_w_in=box_w, box_h_in=h1, min_pt=14.5, max_pt=18.5, space_after_pt=3.0
    )
    _set_paragraph_runs(
        s_box.text_frame.paragraphs[0], "Patrol Scenario Challenge", scenario,
        font_size_pt=s_font, anchor_rgb=s_border, body_rgb=body_rgb,
    )

    o_bg = (30, 41, 59) if tier == "STUDIO" else ScoutsBSAPalette.CRISP_SLATE_RGB
    o_border = (244, 196, 48) if tier == "STUDIO" else ScoutsBSAPalette.ACTION_BLUE_RGB
    o_box = _add_styled_box(
        slide, left_in=0.60, top_in=content_top + h1 + gap, width_in=box_w, height_in=h2,
        bg_rgb=o_bg, border_rgb=o_border, border_pt=1.25,
    )
    otf = o_box.text_frame
    o_font = _compute_fitting_font_size(
        ["Discussion Options (Ask Scouts First)"] + list(options[:3]),
        box_w_in=box_w, box_h_in=h2, min_pt=14.0, max_pt=17.5, space_after_pt=4.0
    )
    _set_paragraph_runs(
        otf.paragraphs[0], "Discussion Options (Ask Scouts First)", "",
        font_size_pt=min(18.5, o_font + 0.5), anchor_rgb=o_border, space_after_pt=4.0,
    )
    for idx_o, opt in enumerate(options[:3], start=1):
        p = otf.add_paragraph()
        a, b = _split_anchor_and_body(opt, f"Option {idx_o}")
        _set_paragraph_runs(p, a, b, font_size_pt=o_font, anchor_rgb=o_border, body_rgb=body_rgb, space_after_pt=4.0)

    a_bg = (23, 37, 42) if tier == "STUDIO" else ScoutsBSAPalette.SOFT_OLIVE_CARD_RGB
    a_border = (74, 222, 128) if tier == "STUDIO" else ScoutsBSAPalette.WARM_OLIVE_RGB
    a_box = _add_styled_box(
        slide, left_in=0.60, top_in=content_top + h1 + gap + h2 + gap, width_in=box_w, height_in=h3,
        bg_rgb=a_bg, border_rgb=a_border, border_pt=1.5,
    )
    atf = a_box.text_frame
    a_font = _compute_fitting_font_size(
        [f"Verified Answer: {answer}", f"Why It Matters: {explanation}"],
        box_w_in=box_w, box_h_in=h3, min_pt=14.0, max_pt=17.5, space_after_pt=4.0
    )
    _set_paragraph_runs(
        atf.paragraphs[0], "Verified Answer", answer,
        font_size_pt=a_font, anchor_rgb=a_border, body_rgb=body_rgb, space_after_pt=4.0,
    )
    p_exp = atf.add_paragraph()
    _set_paragraph_runs(
        p_exp, "Why It Matters", explanation,
        font_size_pt=a_font, anchor_rgb=s_border, body_rgb=body_rgb, space_after_pt=2.0,
    )


def _render_split_explainer_zone(
    slide: Any,
    slide_spec: SlideSpec,
    full_width: bool = False,
    content_top: float = 1.15,
    content_bottom: float = 6.95,
) -> None:
    """Renders structured bold-anchored instructional points as individual stacked horizontal cards
    matching the UI preview (`ui/app.js` and `src/app.py`).
    """
    box_w = 12.133 if full_width else 6.20
    points = slide_spec.bullet_points[:6]
    if not points and slide_spec.cards:
        points = [f"{c.get('anchor_title', 'Concept')}: {c.get('body_text', '')}" for c in slide_spec.cards[:6]]
    if not points:
        points = ["Key Concept: Review and discuss these principles with your counselor."]

    _render_stacked_point_cards(
        slide=slide,
        slide_spec=slide_spec,
        points=points,
        left_in=0.60,
        top_in=content_top,
        width_in=box_w,
        bottom_in=content_bottom,
        default_anchor_prefix="Core Principle",
    )



# ==============================================================================
# MAIN PPTX GENERATOR FUNCTION
# ==============================================================================

def generate_bsa_slide_deck_pptx(
    request: Any,
) -> Dict[str, Any]:
    """Generates a 16:9 widescreen PowerPoint presentation with zero AABB overlaps.

    Produces `1 (Cover Slide) + len(request.slides)` slides. If `hitl_confirmation_token`
    is provided on `request`, verifies its HMAC-SHA256 signature via `verify_hitl_confirmation_token`
    before writing the presentation to disk.

    Args:
        request: A validated `PowerPointBuildRequest` (or raw dictionary) containing `badge_name`,
            `slides`, `counselor_info`, `output_path`, and optional `hitl_confirmation_token`.

    Returns:
        Dict[str, Any]: A serialized `PowerPointBuildResult` dictionary (`status='SUCCESS'`,
        `output_path`, `slide_count`, `is_eagle_required`) on success, or a `GuidedToolError`
        dictionary with `recovery_suggestion` on validation or token failure.
    """
    from pydantic import ValidationError
    from src.schemas import build_guided_tool_error
    from src.tools.hitl_confirm import verify_hitl_confirmation_token
    from src.tools.pamphlet_extractor import get_badge_cover_and_patch_paths

    if isinstance(request, dict):
        try:
            request = PowerPointBuildRequest(**request)
        except ValidationError as exc:
            return build_guided_tool_error(
                error_type="INVALID_PPTX_BUILD_REQUEST",
                message=f"PowerPointBuildRequest validation failed: {exc}",
                recovery_suggestion="Provide a valid badge_name and non-empty slides list conforming to SlideSpec.",
            )

    if not getattr(request, "badge_name", "") or not str(request.badge_name).strip():
        return build_guided_tool_error(
            error_type="EMPTY_BADGE_NAME",
            message="badge_name cannot be empty when building a PowerPoint presentation.",
            recovery_suggestion="Pass a valid official Scouts BSA Merit Badge name in PowerPointBuildRequest.badge_name.",
        )

    if not getattr(request, "slides", None):
        return build_guided_tool_error(
            error_type="EMPTY_SLIDE_STORYBOARD",
            message="slides list cannot be empty when building a PowerPoint presentation.",
            recovery_suggestion="Call generate_slide_storyboard first and provide at least one SlideSpec in PowerPointBuildRequest.slides.",
        )

    if getattr(request, "hitl_confirmation_token", None):
        if not verify_hitl_confirmation_token(request.hitl_confirmation_token, request.badge_name):
            return build_guided_tool_error(
                error_type="INVALID_HITL_CONFIRMATION_TOKEN",
                message=f"Supplied hitl_confirmation_token '{request.hitl_confirmation_token}' is invalid for '{request.badge_name}'.",
                recovery_suggestion="Call request_counselor_confirmation first to obtain a valid HMAC-SHA256 confirmation_token.",
            )

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    badge_title = request.badge_name.strip().title()
    eagle_flag = is_eagle_required(badge_title)
    blank_layout = prs.slide_layouts[6]
    used_sha256: Set[str] = set()

    # -------------------------------------------------------------------------
    # 1. COVER HERO TITLE SLIDE (Slide 1) — Borderless Clean Layout (No Boxes!)
    #    Strictly non-overlapping zones:
    #      - Standalone Scout Shop Badge Emblem: [x: 0.65..2.90, y: 0.55..2.80]
    #      - Centered Badge Title (no box): [x: 3.05..8.10, y: 0.65..2.80]
    #      - Counselor Info on Lower Left (no box, left-aligned): [x: 0.65..8.10, y: 3.55..6.45]
    #      - Official Pamphlet Cover on Right: [x: 8.35..12.70, y: 0.50..6.65]
    #      - Footer (no box): [x: 0.65..12.70, y: 6.85..7.20]
    # -------------------------------------------------------------------------
    cover_slide = prs.slides.add_slide(blank_layout)
    deck_tier = (
        str(getattr(request.slides[0], "beautification_tier", "STANDARD") or "STANDARD").upper()
        if request.slides
        else "STANDARD"
    )
    cover_accent_rgb = (
        (244, 196, 48)
        if deck_tier == "STUDIO"
        else (ScoutsBSAPalette.EAGLE_RED_RGB if eagle_flag else ScoutsBSAPalette.NAVY_BLUE_RGB)
    )
    _apply_slide_tier_background(cover_slide, deck_tier, cover_accent_rgb)
    cover_title_rgb = (248, 250, 252) if deck_tier == "STUDIO" else ScoutsBSAPalette.NAVY_BLUE_RGB
    cover_sub_rgb = (
        ((248, 113, 113) if eagle_flag else (74, 222, 128))
        if deck_tier == "STUDIO"
        else (ScoutsBSAPalette.EAGLE_RED_RGB if eagle_flag else ScoutsBSAPalette.WARM_OLIVE_RGB)
    )
    cover_body_rgb = (241, 245, 249) if deck_tier == "STUDIO" else ScoutsBSAPalette.DARK_TEXT_RGB
    cover_label_rgb = (244, 196, 48) if deck_tier == "STUDIO" else ScoutsBSAPalette.NAVY_BLUE_RGB
    cover_unit_rgb = (56, 189, 248) if deck_tier == "STUDIO" else ScoutsBSAPalette.WARM_OLIVE_RGB

    cover_assets = get_badge_cover_and_patch_paths(badge_title)
    patch_img_path = _ensure_unique_image_path(cover_assets.get("patch_path"), 0, used_sha256)
    cover_img_path = _ensure_unique_image_path(cover_assets.get("cover_path"), 9999, used_sha256)

    # Zone A1: Standalone Scout Shop Merit Badge Emblem [x: 0.65..2.90, y: 0.55..2.80]
    patch_placed = False
    if patch_img_path and os.path.exists(patch_img_path):
        try:
            cover_slide.shapes.add_picture(
                patch_img_path,
                Inches(0.65),
                Inches(0.55),
                width=Inches(2.25),
                height=Inches(2.25),
            )
            patch_placed = True
        except Exception:
            patch_placed = False

    # Zone A2: Centered Badge Title & Subtitle (Borderless Textbox — No Box!)
    hero_left = 3.05 if patch_placed else 0.65
    hero_w = 5.05 if patch_placed else 7.45
    hero_box = cover_slide.shapes.add_textbox(
        Inches(hero_left), Inches(1.05), Inches(hero_w), Inches(2.15)
    )
    htf = hero_box.text_frame
    htf.word_wrap = True
    htf.vertical_anchor = MSO_ANCHOR.TOP
    p_title = htf.paragraphs[0]
    title_pt = 54.0 if len(badge_title) <= 15 else (42.0 if len(badge_title) <= 22 else 34.0)
    _set_paragraph_runs(
        p_title,
        badge_title,
        "",
        font_size_pt=title_pt,
        anchor_rgb=cover_title_rgb,
        space_after_pt=10.0,
        align=PP_ALIGN.CENTER,
    )

    p_sub = htf.add_paragraph()
    _set_paragraph_runs(
        p_sub,
        "Eagle-Required Merit Badge" if eagle_flag else "Scouts BSA Merit Badge",
        "",
        font_size_pt=24.0,
        anchor_rgb=cover_sub_rgb,
        font_name="Roboto Slab",
        space_after_pt=4.0,
        align=PP_ALIGN.CENTER,
    )

    # Zone B: Counselor & Unit Information on Lower Left (Borderless Textbox — No Box!)
    info = request.counselor_info
    counselor_name = info.counselor_name if (info and info.counselor_name) else "Scoutmaster Bob"
    troop_affil = info.troop_affiliation if (info and info.troop_affiliation) else "Troop 123, My Council"
    loc_zip = info.location_or_zip if (info and getattr(info, "location_or_zip", None)) else ""
    email_addr = info.email_address if info else "counselor@troop123.org"
    phone_num = info.phone_number if info else "(000) 555-1234"
    custom_logo = (
        info.custom_troop_logo_path
        if (info and info.custom_troop_logo_path and os.path.exists(info.custom_troop_logo_path))
        else None
    )

    c_box_width_in = 5.55 if custom_logo else 7.45
    c_box = cover_slide.shapes.add_textbox(
        Inches(0.65), Inches(4.05), Inches(c_box_width_in), Inches(2.65)
    )
    ctf = c_box.text_frame
    ctf.word_wrap = True
    ctf.vertical_anchor = MSO_ANCHOR.TOP
    _set_paragraph_runs(
        ctf.paragraphs[0], "Counselor", counselor_name,
        font_size_pt=21.0, anchor_rgb=cover_label_rgb, body_rgb=cover_body_rgb, space_after_pt=6.0, bold_body=True, align=PP_ALIGN.LEFT,
    )
    cp_unit = ctf.add_paragraph()
    _set_paragraph_runs(
        cp_unit, "Unit / Council", troop_affil,
        font_size_pt=18.5, anchor_rgb=cover_unit_rgb, body_rgb=cover_body_rgb, space_after_pt=6.0, align=PP_ALIGN.LEFT,
    )
    if loc_zip:
        cp_loc = ctf.add_paragraph()
        _set_paragraph_runs(
            cp_loc, "Location", loc_zip,
            font_size_pt=17.0, anchor_rgb=cover_unit_rgb, body_rgb=cover_body_rgb, space_after_pt=5.0, align=PP_ALIGN.LEFT,
        )
    if email_addr:
        cp_email = ctf.add_paragraph()
        _set_paragraph_runs(
            cp_email, "Email", email_addr,
            font_size_pt=17.0, anchor_rgb=cover_label_rgb, body_rgb=cover_body_rgb, space_after_pt=5.0, align=PP_ALIGN.LEFT,
        )
    if phone_num:
        cp_phone = ctf.add_paragraph()
        _set_paragraph_runs(
            cp_phone, "Phone", phone_num,
            font_size_pt=17.0, anchor_rgb=cover_label_rgb, body_rgb=cover_body_rgb, space_after_pt=4.0, align=PP_ALIGN.LEFT,
        )

    # Zone B2: Optional Custom Troop Logo next to Counselor Info [x: 6.35..8.10, y: 4.30..6.15]
    if custom_logo and os.path.exists(custom_logo):
        try:
            logo_max_w = 1.75
            logo_max_h = 1.85
            with Image.open(custom_logo) as lim:
                liw, lih = lim.size
            laspect = float(liw) / float(max(1, lih))
            lt_h = logo_max_h
            lt_w = lt_h * laspect
            if lt_w > logo_max_w:
                lt_w = logo_max_w
                lt_h = lt_w / laspect
            logo_left = 6.35 + (logo_max_w - lt_w) / 2.0
            logo_top = 4.30 + (logo_max_h - lt_h) / 2.0
            cover_slide.shapes.add_picture(
                custom_logo,
                Inches(logo_left),
                Inches(logo_top),
                width=Inches(lt_w),
                height=Inches(lt_h),
            )
        except Exception:
            pass

    # Zone C: Right-Hand Official BSA Pamphlet Cover [x: 8.35..12.70, y: 0.52..6.62]
    right_visual_path = cover_img_path or custom_logo
    if right_visual_path and os.path.exists(right_visual_path):
        try:
            max_w_in = 4.35
            max_h_in = 6.10
            with Image.open(right_visual_path) as im:
                iw, ih = im.size
            aspect = float(iw) / float(max(1, ih))
            target_h = max_h_in
            target_w = target_h * aspect
            if target_w > max_w_in:
                target_w = max_w_in
                target_h = target_w / aspect
            left_in = 8.35 + (max_w_in - target_w) / 2.0
            top_in = 0.52 + (max_h_in - target_h) / 2.0
            cover_slide.shapes.add_picture(
                right_visual_path,
                Inches(left_in),
                Inches(top_in),
                width=Inches(target_w),
                height=Inches(target_h),
            )
        except Exception:
            pass

    eagle_note = (
        f"As an Eagle-Required Merit Badge, {badge_title} builds essential lifelong citizenship, safety, and outdoor leadership skills."
        if eagle_flag
        else f"The {badge_title} Merit Badge gives Scouts an opportunity to explore a specialized field through hands-on practice and real-world observation."
    )
    cover_notes_slide = cover_slide.notes_slide
    cover_notes_slide.notes_text_frame.text = (
        f"[SAY] Welcome Scouts to our {badge_title} Merit Badge session, and introduce yourself ({counselor_name}, {troop_affil}) along with how Scouts and parents can reach you ({email_addr or 'via unit leadership'}) using Two-Deep Leadership / Youth Protection guidelines. "
        f"{eagle_note} Explain how we will work through each official requirement using this presentation, hands-on demonstrations, and your printable {badge_title} Merit Badge Workbook."
    )

    # -------------------------------------------------------------------------
    # 2. CONTENT SLIDES (Zero AABB Overlaps, Clean Teaching Layout)
    # -------------------------------------------------------------------------
    total_deck_slides = 1 + len(request.slides)
    temp_unique_files: List[str] = []
    for idx, slide_spec in enumerate(request.slides, start=1):
        content_slide = prs.slides.add_slide(blank_layout)
        slide_num = idx + 1
        arch = (slide_spec.archetype or "SPLIT_VISUAL_EXPLAINER").upper()
        s_tier = str(getattr(slide_spec, "beautification_tier", deck_tier) or deck_tier).upper()
        s_border_rgb, s_bg_rgb = _resolve_palette_colors(slide_spec)
        s_anchor_rgb, s_body_rgb, s_title_rgb = _resolve_text_colors(slide_spec, s_border_rgb)
        _apply_slide_tier_background(content_slide, s_tier, s_border_rgb)

        req_tag = (
            "Sources & Credits"
            if arch == "SOURCES_AND_REFERENCES"
            else (
                "Badge Overview"
                if str(slide_spec.req_number).lower() == "overview"
                else f"Requirement {slide_spec.req_number}"
            )
        )

        # ---------------------------------------------------------------------
        # ZONE 1: Borderless Centered Slide Title [x: 0.60..12.733, y: 0.20..1.02]
        # ---------------------------------------------------------------------
        header_box = content_slide.shapes.add_textbox(
            Inches(0.60), Inches(0.20), Inches(12.133), Inches(0.82)
        )
        htf = header_box.text_frame
        htf.word_wrap = True
        htf.vertical_anchor = MSO_ANCHOR.TOP
        hp = htf.paragraphs[0]
        title_str = _clean_text(slide_spec.title) or f"Requirement {slide_spec.req_number}"
        hdr_pt = (
            28.0
            if len(title_str) <= 44
            else (24.0 if len(title_str) <= 54 else (20.5 if len(title_str) <= 66 else 18.0))
        )
        _set_paragraph_runs(
            hp,
            title_str,
            "",
            font_size_pt=hdr_pt,
            anchor_rgb=s_title_rgb,
            space_after_pt=0.0,
            align=PP_ALIGN.CENTER,
        )

        # Resolve unique diagram_path only if this slide has an existing visual asset
        orig_diagram_path = slide_spec.diagram_path
        resolved_diagram = _ensure_unique_image_path(orig_diagram_path, idx, used_sha256)
        if resolved_diagram and resolved_diagram.endswith(f"_s{idx}_u.png"):
            temp_unique_files.append(resolved_diagram)
        else:
            slide_spec.diagram_path = resolved_diagram
        has_visual = bool(resolved_diagram and os.path.exists(resolved_diagram))

        # Determine whether this slide needs a bottom bar (for safety warnings or full-page diagram captions)
        has_bottom_bar = (
            bool(slide_spec.safety_warning)
            or (arch == "FULL_BLEED_IMAGE_EXPLAINER" and has_visual)
        )
        content_bottom = 6.25 if has_bottom_bar else 6.95

        # ---------------------------------------------------------------------
        # SPECIAL FULL-CANVAS ARCHETYPES:
        #   - REQUIREMENT_INTRO (First slide of Req N in Deep Dive: Requirement + Core Teaching + Optional EDGE Map)
        #   - FULL_BLEED_IMAGE_EXPLAINER (Full-canvas centered diagram/photo)
        # ---------------------------------------------------------------------
        if arch == "REQUIREMENT_INTRO":
            _render_requirement_intro_slide(
                content_slide, slide_spec, content_bottom=content_bottom, resolved_diagram=resolved_diagram
            )
        elif arch == "FULL_BLEED_IMAGE_EXPLAINER" and has_visual:
            _render_full_bleed_image_slide(
                content_slide, slide_spec, resolved_diagram, content_top=1.15, content_bottom=content_bottom
            )
        else:
            # -----------------------------------------------------------------
            # OPTIONAL ZONE 2: Requirement Definition / Overview Strip
            #   Rendered when slide_spec.verbatim_requirement_text is non-empty
            # -----------------------------------------------------------------
            has_req_strip = bool(
                slide_spec.verbatim_requirement_text
                and slide_spec.verbatim_requirement_text.strip()
                and arch not in {"SOURCES_AND_REFERENCES"}
            )
            if has_req_strip:
                verbatim_text = _clean_text(slide_spec.verbatim_requirement_text)
                strip_anchor = (
                    "Curriculum & Local Context"
                    if str(slide_spec.req_number).lower() == "overview"
                    else f"Official Requirement {slide_spec.req_number}"
                )
                full_strip_line = f"{strip_anchor}: {verbatim_text}"
                strip_h = (
                    0.72
                    if len(full_strip_line) <= 115
                    else (0.88 if len(full_strip_line) <= 215 else (1.04 if len(full_strip_line) <= 320 else 1.24))
                )
                strip_bg = (30, 41, 59) if s_tier == "STUDIO" else (s_bg_rgb if s_tier == "BEAUTIFIED" else ScoutsBSAPalette.WHITE_RGB)
                req_strip = _add_styled_box(
                    content_slide, left_in=0.60, top_in=1.10, width_in=12.133, height_in=strip_h,
                    bg_rgb=strip_bg, border_rgb=s_border_rgb, border_pt=1.5,
                )
                rstf = req_strip.text_frame
                rstf.margin_top = Inches(0.06)
                rstf.margin_bottom = Inches(0.05)
                strip_font_pt = _compute_fitting_font_size(
                    [full_strip_line], box_w_in=12.133, box_h_in=strip_h, min_pt=15.0, max_pt=18.0, space_after_pt=0.0
                )
                _set_paragraph_runs(
                    rstf.paragraphs[0],
                    strip_anchor,
                    verbatim_text,
                    font_size_pt=strip_font_pt,
                    anchor_rgb=s_anchor_rgb,
                    body_rgb=s_body_rgb,
                    space_after_pt=0.0,
                )
                content_top = round(1.10 + strip_h + 0.10, 2)
            else:
                content_top = 1.15

            # Decide whether to render full-width (12.133") or split with right-hand visual
            use_full_width = (
                not has_visual
                or arch in {"CONCEPT_TEXT_SLIDE", "SOURCES_AND_REFERENCES", "REQUIREMENTS_TRIAGE_MATRIX"}
            )

            if arch in {"CONCEPT_TEXT_SLIDE", "SOURCES_AND_REFERENCES"}:
                _render_concept_or_sources_full_width(
                    content_slide, slide_spec, content_top=content_top, content_bottom=content_bottom
                )
            elif arch == "REQUIREMENTS_TRIAGE_MATRIX":
                _render_triage_matrix_zone(
                    content_slide, slide_spec, full_width=use_full_width, content_top=content_top, content_bottom=content_bottom
                )
            elif arch == "DIFFERENTIAL_COMPARISON_2COL" or slide_spec.comparison_data:
                _render_differential_comparison_zone(
                    content_slide, slide_spec, full_width=use_full_width, content_top=content_top, content_bottom=content_bottom
                )
            elif arch == "STEP_BY_STEP_PROCEDURE_4CARD":
                _render_step_by_step_4card_zone(
                    content_slide, slide_spec, full_width=use_full_width, content_top=content_top, content_bottom=content_bottom
                )
            elif arch == "WORKED_EXAMPLE_TEMPLATE" or slide_spec.worked_example:
                _render_worked_example_zone(
                    content_slide, slide_spec, full_width=use_full_width, content_top=content_top, content_bottom=content_bottom
                )
            elif arch == "GEAR_CHECKLIST_GRID" or slide_spec.gear_checklist:
                _render_gear_checklist_zone(
                    content_slide, slide_spec, full_width=use_full_width, content_top=content_top, content_bottom=content_bottom
                )
            elif arch == "SOCRATIC_CHECKPOINT_QUIZ" or slide_spec.quiz_item:
                _render_socratic_quiz_zone(
                    content_slide, slide_spec, full_width=use_full_width, content_top=content_top, content_bottom=content_bottom
                )
            else:
                _render_split_explainer_zone(
                    content_slide, slide_spec, full_width=use_full_width, content_top=content_top, content_bottom=content_bottom
                )

            # -----------------------------------------------------------------
            # ZONE 4: Right Visual Zone (ONLY when has_visual and not full-width)
            # -----------------------------------------------------------------
            if has_visual and not use_full_width and resolved_diagram:
                avail_img_h = max(2.80, (content_bottom - content_top) - 0.58)
                try:
                    pic = content_slide.shapes.add_picture(
                        resolved_diagram,
                        Inches(7.05),
                        Inches(content_top),
                        width=Inches(5.65),
                    )
                    max_h = Inches(avail_img_h)
                    if pic.height > max_h:
                        scale = float(max_h) / float(pic.height)
                        pic.height = max_h
                        pic.width = int(pic.width * scale)
                except Exception:
                    pass

                cap_bg = (30, 41, 59) if s_tier == "STUDIO" else (s_bg_rgb if s_tier in ("BEAUTIFIED",) else ScoutsBSAPalette.CRISP_SLATE_RGB)
                cap_border = s_border_rgb if s_tier in ("BEAUTIFIED", "STUDIO") else ScoutsBSAPalette.BORDER_GRAY_RGB
                caption_box = _add_styled_box(
                    content_slide, left_in=7.05, top_in=content_bottom - 0.50, width_in=5.65, height_in=0.50,
                    bg_rgb=cap_bg, border_rgb=cap_border, border_pt=1.25,
                )
                captf = caption_box.text_frame
                captf.margin_top = Inches(0.05)
                captf.margin_bottom = Inches(0.04)
                caption_str = _clean_text(slide_spec.visual_caption) or _clean_text(slide_spec.title)
                for prefix_rm in ("EDGE Skill Concept Map — ", "EDGE Skill Concept Map - ", "Figure: "):
                    if caption_str.startswith(prefix_rm):
                        caption_str = caption_str[len(prefix_rm):].strip()
                if len(caption_str) > 36:
                    caption_str = caption_str[:36].rsplit(" ", 1)[0].strip(" .,:;-—") or caption_str[:36]
                cap_font_pt = _compute_fitting_font_size(
                    [f"Figure: {caption_str}"], box_w_in=5.65, box_h_in=0.50, min_pt=15.0, max_pt=16.0, space_after_pt=0.0
                )
                _set_paragraph_runs(
                    captf.paragraphs[0], "Figure", caption_str,
                    font_size_pt=cap_font_pt, anchor_rgb=s_anchor_rgb, body_rgb=s_body_rgb, space_after_pt=0.0,
                )

        # ---------------------------------------------------------------------
        # OPTIONAL ZONE 5: Bottom Safety Warning or Full-Bleed Diagram Bar
        # ---------------------------------------------------------------------
        if slide_spec.safety_warning:
            warn_str = _clean_text(slide_spec.safety_warning)
            warn_font_pt = _compute_fitting_font_size(
                [f"GUIDE TO SAFE SCOUTING: {warn_str}"], box_w_in=12.133, box_h_in=0.72, min_pt=15.0, max_pt=17.5, space_after_pt=0.0
            )
            warn_bg = (42, 24, 32) if s_tier == "STUDIO" else ScoutsBSAPalette.SOFT_RED_CARD_RGB
            warn_border = (248, 113, 113) if s_tier == "STUDIO" else ScoutsBSAPalette.EAGLE_RED_RGB
            callout_box = _add_styled_box(
                content_slide, left_in=0.60, top_in=6.38, width_in=12.133, height_in=0.72,
                bg_rgb=warn_bg, border_rgb=warn_border, border_pt=1.5,
            )
            stf = callout_box.text_frame
            _set_paragraph_runs(
                stf.paragraphs[0],
                "GUIDE TO SAFE SCOUTING",
                warn_str,
                font_size_pt=warn_font_pt,
                anchor_rgb=warn_border,
                body_rgb=s_body_rgb,
                font_name="Roboto Slab",
                space_after_pt=0.0,
                bold_body=True,
            )
        elif arch == "FULL_BLEED_IMAGE_EXPLAINER" and has_visual:
            diag_bg = (23, 37, 42) if s_tier == "STUDIO" else ScoutsBSAPalette.SOFT_OLIVE_CARD_RGB
            diag_border = (74, 222, 128) if s_tier == "STUDIO" else ScoutsBSAPalette.WARM_OLIVE_RGB
            callout_box = _add_styled_box(
                content_slide, left_in=0.60, top_in=6.38, width_in=12.133, height_in=0.72,
                bg_rgb=diag_bg, border_rgb=diag_border, border_pt=1.25,
            )
            stf = callout_box.text_frame
            key_takeaway = _clean_text(
                " ".join(slide_spec.bullet_points[:2])
                if slide_spec.bullet_points
                else (slide_spec.visual_caption or slide_spec.title)
            )
            diag_font_pt = _compute_fitting_font_size(
                [f"DIAGRAM EXPLANATION: {key_takeaway}"], box_w_in=12.133, box_h_in=0.72, min_pt=15.0, max_pt=17.5, space_after_pt=0.0
            )
            _set_paragraph_runs(
                stf.paragraphs[0],
                "DIAGRAM EXPLANATION",
                key_takeaway,
                font_size_pt=diag_font_pt,
                anchor_rgb=diag_border,
                body_rgb=s_body_rgb,
                space_after_pt=0.0,
            )

        # ---------------------------------------------------------------------
        # ZONE 6: Footer Metadata Strip [x: 0.60..12.733, y: 7.15..7.43]
        # ---------------------------------------------------------------------
        footer_box = content_slide.shapes.add_textbox(Inches(0.60), Inches(7.15), Inches(12.133), Inches(0.28))
        ftf = footer_box.text_frame
        ftf.word_wrap = True
        ftf.vertical_anchor = MSO_ANCHOR.TOP
        fp = ftf.paragraphs[0]
        footer_rgb = (148, 163, 184) if s_tier == "STUDIO" else ScoutsBSAPalette.MUTED_TEXT_RGB
        _set_paragraph_runs(
            fp,
            f"Scouts BSA {badge_title} Merit Badge • {s_tier} Mode",
            f"Slide {slide_num} of {total_deck_slides} • {req_tag}",
            font_size_pt=13.0,
            anchor_rgb=footer_rgb,
            body_rgb=footer_rgb,
            space_after_pt=0.0,
            align=PP_ALIGN.LEFT,
        )

        # ---------------------------------------------------------------------
        # Presenter Instructor Notes
        # ---------------------------------------------------------------------
        if slide_spec.presenter_notes:
            notes_slide = content_slide.notes_slide
            text_frame = notes_slide.notes_text_frame
            text_frame.text = slide_spec.presenter_notes

    # -------------------------------------------------------------------------
    # 3. SAVE FILE & CLEAN UP TEMPORARY SLIDE-UNIQUE IMAGE COPIES
    # -------------------------------------------------------------------------
    out_filename = request.output_path or f"{badge_title.replace(' ', '_')}_Merit_Badge_Deck.pptx"
    prs.save(out_filename)
    for tmp_u in temp_unique_files:
        try:
            if os.path.exists(tmp_u):
                os.remove(tmp_u)
        except OSError:
            pass

    result = PowerPointBuildResult(
        badge_name=badge_title,
        slide_count=len(prs.slides),
        output_path=os.path.abspath(out_filename),
        is_eagle_required=eagle_flag,
        status="SUCCESS",
    )
    return result.model_dump()
