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
    """Strips literal bullet glyphs, normalizes punctuation spacing, and removes ellipsis truncation from slide copy."""
    if not raw_text:
        return ""
    cleaned = _LEADING_BULLET_RE.sub("", str(raw_text).strip())
    cleaned = cleaned.replace("...", ".").replace("…", ".")
    cleaned = cleaned.replace(" , ", ", ")
    cleaned = re.sub(r"\.\.+", ".", cleaned)
    return cleaned.strip()


def _split_anchor_and_body(point_text: str, default_anchor: str = "Key Point") -> Tuple[str, str]:
    """Splits a point string into a Bold Anchor and a concise body explanation without inventing mid-sentence colons."""
    cleaned = _clean_text(point_text)
    if not cleaned:
        return default_anchor, "Review this concept with your Merit Badge Counselor."
    if ":" in cleaned:
        parts = [p.strip() for p in cleaned.split(":")]
        if len(parts) >= 3 and 1 <= len(parts[1].split()) <= 7 and ":".join(parts[2:]).strip():
            return parts[1], ":".join(parts[2:]).strip()
        first_colon = cleaned.find(":")
        anchor_candidate = cleaned[:first_colon].strip()
        body_candidate = cleaned[first_colon + 1 :].strip()
        if 1 <= len(anchor_candidate.split()) <= 10 and body_candidate:
            return anchor_candidate, body_candidate
    words = cleaned.split()
    if len(words) <= 4:
        return cleaned, ""
    if not default_anchor:
        return "", cleaned
    return default_anchor, cleaned


_DANGLING_TAIL_WORDS = {
    "and", "or", "with", "to", "for", "in", "on", "of", "by", "the", "a", "an",
    "that", "which", "while", "when", "if", "from", "into", "at", "as", "such",
    "including", "through", "during", "before", "after", "under", "over", "between",
}


def _concise_card_body(body_text: str, max_words: int = 24, max_chars: int = 150) -> str:
    """Condenses a long pamphlet sentence into a crisp clause without ellipsis ('...') so cards stay airy."""
    cleaned = _clean_text(body_text)
    if not cleaned:
        return ""
    words = cleaned.split()
    if len(words) <= max_words and len(cleaned) <= max_chars:
        return cleaned

    # Try splitting at a sentence or secondary clause boundary if the primary clause is substantive
    for sep in (
        ". ",
        "; ",
        " — ",
        " – ",
        ", which ",
        ", while ",
        ", ensuring ",
        ", allowing ",
        ", including ",
        ", such as ",
        ", especially ",
        " so that ",
        " in order to ",
        ", and ",
        ", or ",
        ", then ",
    ):
        if sep in cleaned:
            head = cleaned.split(sep, 1)[0].strip().rstrip(",;:-")
            head_words = head.split()
            if 6 <= len(head_words) <= max_words and len(head) <= max_chars:
                return head if head.endswith((".", "!", "?")) else f"{head}."

    # Otherwise cap at max_words and trim any trailing conjunction/preposition/article cleanly
    capped = list(words[:max_words])
    while len(capped) > 6 and " ".join(capped) and len(" ".join(capped)) > max_chars:
        capped.pop()
    while len(capped) > 6 and capped[-1].lower().strip(",;:-.()") in _DANGLING_TAIL_WORDS:
        capped.pop()
    result = " ".join(capped).rstrip(",;:-(")
    if result.count("(") > result.count(")"):
        result = result.rsplit("(", 1)[0].strip().rstrip(",;:-")
    if result and not result.endswith((".", "!", "?")):
        result += "."
    return result



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


def _set_rounded_rect_radius(shape: Any, width_in: float, height_in: float, radius_in: float = 0.09) -> None:
    """Normalizes MSO_SHAPE.ROUNDED_RECTANGLE corner radius to a constant physical radius in inches
    and disables theme drop shadows so Google Slides renders crisp, uniform corners on both short and tall cards.
    """
    try:
        min_dim = max(0.05, min(float(width_in), float(height_in)))
        shape.adjustments[0] = min(0.32, max(0.02, float(radius_in) / min_dim))
    except Exception:
        pass
    try:
        shape.shadow.inherit = False
    except Exception:
        pass


def _enable_openxml_bullet(paragraph: Any, char: str = "•") -> None:
    """Enables a native OpenXML hanging bullet (`<a:buChar>`) on a paragraph without inserting a literal '•' into `p.text`."""
    try:
        from pptx.oxml import parse_xml
        from pptx.oxml.ns import nsdecls

        pPr = paragraph._p.get_or_add_pPr()
        pPr.set("marL", "205740")
        pPr.set("indent", "-205740")
        for child in list(pPr):
            if child.tag.endswith(("buNone", "buChar", "buAutoNum")):
                pPr.remove(child)
        pPr.append(parse_xml(f'<a:buChar {nsdecls("a")} char="{char}"/>'))
    except Exception:
        pass


def _add_styled_box(
    slide: Any,
    left_in: float,
    top_in: float,
    width_in: float,
    height_in: float,
    bg_rgb: Tuple[int, int, int] = ScoutsBSAPalette.CRISP_SLATE_RGB,
    border_rgb: Tuple[int, int, int] = ScoutsBSAPalette.BORDER_GRAY_RGB,
    border_pt: float = 1.25,
    top_accent_rgb: Optional[Tuple[int, int, int]] = None,
    left_accent_rgb: Optional[Tuple[int, int, int]] = None,
    radius_in: float = 0.09,
) -> Any:
    """Adds a rounded rectangular card shape with an integrated Layered Crescent top or left accent border."""
    body_left = left_in
    body_top = top_in
    body_w = width_in
    body_h = height_in
    fg_radius = radius_in

    if top_accent_rgb is not None and height_in > 0.35:
        bar_h = 0.065
        cap_h = min(height_in, 0.28)
        cap = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(left_in),
            Inches(top_in),
            Inches(width_in),
            Inches(cap_h),
        )
        cap.name = f"CardAccent_Top_{len(slide.shapes)}"
        _set_rounded_rect_radius(cap, width_in, cap_h, radius_in=radius_in)
        cap.fill.solid()
        cap.fill.fore_color.rgb = RGBColor(*top_accent_rgb)
        cap.line.color.rgb = RGBColor(*top_accent_rgb)
        cap.line.width = Pt(1.0)
        cap.text_frame.word_wrap = True
        body_top = round(top_in + bar_h, 3)
        body_h = round(height_in - bar_h, 3)
        fg_radius = max(0.035, radius_in - 0.045)
    elif left_accent_rgb is not None and width_in > 0.50:
        bar_w = 0.075
        cap_w = min(width_in, 0.28)
        bar = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(left_in),
            Inches(top_in),
            Inches(cap_w),
            Inches(height_in),
        )
        bar.name = f"CardAccent_Left_{len(slide.shapes)}"
        _set_rounded_rect_radius(bar, cap_w, height_in, radius_in=radius_in)
        bar.fill.solid()
        bar.fill.fore_color.rgb = RGBColor(*left_accent_rgb)
        bar.line.color.rgb = RGBColor(*left_accent_rgb)
        bar.line.width = Pt(1.0)
        bar.text_frame.word_wrap = True
        body_left = round(left_in + bar_w, 3)
        body_w = round(width_in - bar_w, 3)
        fg_radius = max(0.035, radius_in - 0.045)

    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(body_left),
        Inches(body_top),
        Inches(body_w),
        Inches(body_h),
    )
    _set_rounded_rect_radius(shape, body_w, body_h, radius_in=fg_radius)
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(*bg_rgb)
    shape.line.color.rgb = RGBColor(*border_rgb)
    shape.line.width = Pt(border_pt)
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = Inches(0.16)
    tf.margin_right = Inches(0.16)
    tf.margin_top = Inches(0.10)
    tf.margin_bottom = Inches(0.08)
    return shape


def _indent_paragraph_for_pill(paragraph: Any, indent_in: float = 0.52) -> None:
    """Indents a card header paragraph's left margin so the anchor text sits cleanly to the right of a step pill badge."""
    try:
        pPr = paragraph._p.get_or_add_pPr()
        pPr.set("marL", str(int(round(float(indent_in) * 914400))))
        pPr.set("indent", "0")
    except Exception:
        pass


def _add_step_pill_badge(
    slide: Any,
    left_in: float,
    top_in: float,
    pill_text: str,
    bg_rgb: Tuple[int, int, int],
    text_rgb: Tuple[int, int, int] = (255, 255, 255),
    width_in: float = 0.45,
    height_in: float = 0.26,
) -> Any:
    """Adds a dedicated dark/colored rounded pill shape (`CardAccent_StepPill_...`) for `01`–`04` and `STEP 1`–`STEP 4`."""
    pill = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(left_in),
        Inches(top_in),
        Inches(width_in),
        Inches(height_in),
    )
    pill.name = f"CardAccent_StepPill_{len(slide.shapes)}"
    _set_rounded_rect_radius(pill, width_in, height_in, radius_in=0.055)
    pill.fill.solid()
    pill.fill.fore_color.rgb = RGBColor(*bg_rgb)
    pill.line.color.rgb = RGBColor(*bg_rgb)
    pill.line.width = Pt(0.75)
    tf = pill.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.06)
    tf.margin_right = Inches(0.03)
    tf.margin_top = Inches(0.01)
    tf.margin_bottom = Inches(0.01)
    _set_paragraph_runs(
        tf.paragraphs[0],
        pill_text,
        "",
        font_size_pt=15.0,
        anchor_rgb=text_rgb,
        body_rgb=text_rgb,
        space_after_pt=0.0,
    )
    if tf.paragraphs[0].runs:
        tf.paragraphs[0].runs[0].text = f"{_clean_text(pill_text)}  "
    return pill


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
    separator: str = ": ",
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
        r_anchor.text = f"{clean_anchor}{separator}" if clean_body else clean_anchor
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

    # Clone image with a 1-pixel deterministic tweak while preserving RGBA transparency if present
    try:
        os.makedirs(GENERATED_DIAGRAMS_DIR, exist_ok=True)
        base = os.path.splitext(os.path.basename(candidate_path))[0]
        out_path = os.path.join(str(GENERATED_DIAGRAMS_DIR), f"{base}_s{slide_idx}_u.png")
        with Image.open(candidate_path) as im:
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                rgba = im.convert("RGBA")
                cx, cy = rgba.width // 2, rgba.height // 2
                r0, g0, b0, a0 = rgba.getpixel((cx, cy))
                rgba.putpixel((cx, cy), ((r0 + slide_idx) % 256, g0, b0, a0))
                rgba.save(out_path, format="PNG")
            else:
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

def _resolve_palette_tokens(
    slide_spec: SlideSpec,
) -> Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]:
    """Returns `(primary_rgb, accent_rgb, card_bg_rgb)` matching `resolveSlidePaletteTokens` in `ui/app.js` 1:1."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    if tier == "STANDARD":
        return (
            ScoutsBSAPalette.NAVY_BLUE_RGB,
            ScoutsBSAPalette.BORDER_GRAY_RGB,
            ScoutsBSAPalette.CRISP_SLATE_RGB,
        )
    pal = str(getattr(slide_spec, "accent_palette_key", "NAVY_GOLD") or "NAVY_GOLD").upper()
    if tier == "STUDIO":
        if pal == "OLIVE_FOREST":
            return (74, 222, 128), (34, 197, 94), (23, 37, 42)
        if pal == "EAGLE_CRIMSON":
            return (248, 113, 113), (239, 68, 68), (42, 24, 32)
        if pal == "SLATE_ACTION":
            return (56, 189, 248), (14, 165, 233), (23, 37, 84)
        return (244, 196, 48), (56, 189, 248), (30, 41, 59)

    # BEAUTIFIED (Warm Cream Editorial)
    if pal == "OLIVE_FOREST":
        return (46, 70, 0), (75, 83, 32), (241, 248, 233)  # #2E4600, #4B5320, #F1F8E9
    if pal == "EAGLE_CRIMSON":
        return (139, 0, 0), (206, 17, 38), (255, 245, 245)  # #8B0000, #CE1126, #FFF5F5
    if pal == "SLATE_ACTION":
        return (15, 23, 42), (0, 90, 224), (240, 249, 255)  # #0F172A, #005AE0, #F0F9FF
    return (0, 63, 135), (212, 175, 55), (239, 246, 255)  # #003F87, #D4AF37, #EFF6FF


def _resolve_palette_colors(
    slide_spec: SlideSpec,
) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """Returns `(primary_rgb, card_bg_rgb)` for backward compatibility with callers."""
    primary_rgb, _, card_bg_rgb = _resolve_palette_tokens(slide_spec)
    return primary_rgb, card_bg_rgb


def _resolve_text_colors(
    slide_spec: SlideSpec,
    default_anchor_rgb: Optional[Tuple[int, int, int]] = None,
) -> Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]:
    """Returns `(anchor_rgb, body_rgb, title_rgb)` matching `ui/app.js` for the slide's beautification_tier."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    primary_rgb, _, _ = _resolve_palette_tokens(slide_spec)
    anchor_base = default_anchor_rgb or primary_rgb
    if tier == "STUDIO":
        return anchor_base, (226, 232, 240), (248, 250, 252)
    return anchor_base, (51, 65, 85), primary_rgb


def _apply_slide_tier_background(
    slide: Any,
    tier: str,
    accent_rgb: Optional[Tuple[int, int, int]] = None,
) -> None:
    """Applies distinct canvas background color for STANDARD, BEAUTIFIED, and STUDIO plus an optional top accent band."""
    from pptx.enum.shapes import MSO_CONNECTOR

    norm_tier = str(tier or "STANDARD").upper()
    try:
        bg = slide.background
        fill = bg.fill
        fill.solid()
        if norm_tier == "STUDIO":
            fill.fore_color.rgb = RGBColor(15, 23, 42)  # Deep Executive Slate (#0F172A)
        elif norm_tier == "BEAUTIFIED":
            fill.fore_color.rgb = RGBColor(250, 248, 245)  # Warm Editorial Cream (#FAF8F5)
        else:
            fill.fore_color.rgb = RGBColor(255, 255, 255)  # Standard Clean White (#FFFFFF)

        if accent_rgb and norm_tier in ("BEAUTIFIED", "STUDIO"):
            band = slide.shapes.add_connector(
                MSO_CONNECTOR.STRAIGHT,
                Inches(0.0),
                Inches(0.03),
                Inches(13.333),
                Inches(0.03),
            )
            band.line.color.rgb = RGBColor(*accent_rgb)
            band.line.width = Pt(4.5)
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
    """Applies distinct prefix, background, border, and text color treatments matching `getCardThemeSpec` in `ui/app.js`."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    theme = str(getattr(slide_spec, "visual_theme", "") or "").upper()
    primary_rgb, accent_rgb, card_bg_rgb = _resolve_palette_tokens(slide_spec)
    bg_rgb = card_bg_rgb if tier != "STANDARD" else default_bg_rgb
    border_rgb = accent_rgb if tier != "STANDARD" else ScoutsBSAPalette.BORDER_GRAY_RGB
    anchor_rgb = primary_rgb if tier != "STANDARD" else default_anchor_rgb
    body_rgb = default_body_rgb
    border_pt = 1.4 if tier == "STUDIO" else (1.25 if tier == "BEAUTIFIED" else 1.0)

    if tier == "STANDARD":
        return anchor, bg_rgb, border_rgb, anchor_rgb, body_rgb, border_pt

    if "DARK_SLATE" in theme:
        bg_rgb = (30, 41, 59)
        border_rgb = (244, 196, 48)
        anchor_rgb = (244, 196, 48)
        body_rgb = (226, 232, 240)
        border_pt = 1.5
        anchor = f"★ {anchor}" if anchor else "★"
    elif "SAFETY_ALERT" in theme:
        bg_rgb = (49, 16, 24) if tier == "STUDIO" else (255, 241, 242)
        border_rgb = (251, 113, 133) if tier == "STUDIO" else ScoutsBSAPalette.EAGLE_RED_RGB
        anchor_rgb = border_rgb
        border_pt = 1.5
        anchor = f"⚠️ {anchor}" if anchor else "⚠️ SAFETY"
    elif "TIMELINE_CHEVRON" in theme:
        border_pt = 1.35
        anchor = f"STEP {idx_pt + 1} ➔  {anchor}" if anchor else f"STEP {idx_pt + 1} ➔"
    elif "EDITORIAL_CALLOUT" in theme or "ANNOTATED_INFOGRAPHIC" in theme:
        bg_rgb = (30, 41, 59) if tier == "STUDIO" else (255, 251, 235)
        border_rgb = (245, 158, 11)
        anchor_rgb = (251, 191, 36) if tier == "STUDIO" else (180, 83, 9)
        border_pt = 1.35
        anchor = f"❝ {anchor}" if anchor else "❝"
    elif "BENTO" in theme or "THREE_PILLAR" in theme or "ASYMMETRIC" in theme:
        border_pt = 1.35
        anchor = f"◆ {anchor}" if anchor else "◆"
    else:
        # Default NUMBERED_STEP_CARDS / NUMBERED_STEP_RIBBON (matches `01  Anchor` in ui/app.js)
        border_pt = 1.35
        anchor = f"0{idx_pt + 1}  {anchor}" if anchor else f"0{idx_pt + 1}"

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
    """Renders each bullet point as an individual horizontal card matching UI preview `.m3-slide-card-item`
    (with Bold Anchor on Line 1 and Regular Body on Line 2 when sufficient vertical height exists).
    """
    primary_rgb, accent_rgb, card_bg_rgb = _resolve_palette_tokens(slide_spec)
    anchor_rgb, body_rgb, _ = _resolve_text_colors(slide_spec, primary_rgb)
    theme = str(getattr(slide_spec, "visual_theme", "") or "").upper()
    use_top_bar = "BENTO" in theme or "THREE_PILLAR" in theme or "ASYMMETRIC" in theme

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
            weights.append(0.45 + float(est_lines))
        total_w = sum(weights)
        min_card_h = min(0.62, avg_h * 0.80)
        raw_heights = [max(min_card_h, avail_cards_h * (w / total_w)) for w in weights]
        scale_h = avail_cards_h / max(0.01, sum(raw_heights))
        card_heights = [round(h * scale_h, 3) for h in raw_heights]
        if card_heights:
            card_heights[-1] = round(avail_cards_h - sum(card_heights[:-1]), 3)

        tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
        cur_top = top_in
        for idx_pt, (pt, c_h) in enumerate(zip(clean_pts, card_heights)):
            c_top = round(cur_top, 3)
            cur_top += c_h + gap_y
            raw_anchor, raw_body = _split_anchor_and_body(pt, "")
            body = _concise_card_body(raw_body)
            anchor, c_bg, c_border, c_anchor_rgb, c_body_rgb, c_border_pt = _resolve_card_theme_treatment(
                slide_spec, idx_pt, raw_anchor, card_bg_rgb, accent_rgb, anchor_rgb, body_rgb
            )
            bar_color = (56, 189, 248) if "DARK_SLATE" in theme else (
                c_border if "SAFETY_ALERT" in theme else primary_rgb
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
                top_accent_rgb=bar_color if use_top_bar else None,
                left_accent_rgb=None if use_top_bar else bar_color,
            )
            tf = card.text_frame
            tf.margin_top = Inches(0.06 if c_h < 0.94 else 0.08)
            tf.margin_bottom = Inches(0.05 if c_h < 0.94 else 0.06)
            tf.margin_left = Inches(0.14 if width_in < 7.0 else 0.18)
            tf.margin_right = Inches(0.14 if width_in < 7.0 else 0.18)

            use_step_pill = (
                tier != "STANDARD"
                and anchor.startswith(f"0{idx_pt + 1}")
                and bool(raw_anchor and body and c_h >= 0.72)
            )

            if raw_anchor and body and c_h >= 0.72:
                f_pt = _compute_fitting_font_size(
                    [anchor, body],
                    box_w_in=width_in - 0.10,
                    box_h_in=c_h,
                    min_pt=15.0,
                    max_pt=18.0 if width_in > 8.0 else 16.5,
                    space_after_pt=2.5,
                )
                header_text = raw_anchor if use_step_pill else anchor
                _set_paragraph_runs(
                    tf.paragraphs[0],
                    header_text,
                    "",
                    font_size_pt=f_pt,
                    anchor_rgb=c_anchor_rgb,
                    body_rgb=c_body_rgb,
                    space_after_pt=2.5,
                )
                if use_step_pill:
                    _indent_paragraph_for_pill(tf.paragraphs[0], indent_in=0.52)
                    pill_left = round(
                        left_in + (0.0 if use_top_bar else 0.075) + (0.14 if width_in < 7.0 else 0.18),
                        3,
                    )
                    pill_top = round(
                        c_top + (0.065 if use_top_bar else 0.0) + (0.055 if c_h < 0.94 else 0.075),
                        3,
                    )
                    pill_bg = primary_rgb if tier == "STUDIO" else (15, 23, 42)
                    pill_fg = (15, 23, 42) if tier == "STUDIO" else (255, 255, 255)
                    _add_step_pill_badge(
                        slide,
                        left_in=pill_left,
                        top_in=pill_top,
                        pill_text=f"0{idx_pt + 1}",
                        bg_rgb=pill_bg,
                        text_rgb=pill_fg,
                        width_in=0.45,
                        height_in=0.25,
                    )
                p_body = tf.add_paragraph()
                _set_paragraph_runs(
                    p_body,
                    "",
                    body,
                    font_size_pt=f_pt,
                    anchor_rgb=c_anchor_rgb,
                    body_rgb=c_body_rgb,
                    space_after_pt=0.0,
                )
            else:
                single_text = body if not raw_anchor else (f"{anchor}: {body}" if body else anchor)
                f_pt = _compute_fitting_font_size(
                    [single_text],
                    box_w_in=width_in - 0.10,
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
                    separator="  " if not raw_anchor else ": ",
                )
        return

    # Fallback unified card when compact vertical space
    _, c_bg, c_border, c_anchor_rgb, c_body_rgb, c_border_pt = _resolve_card_theme_treatment(
        slide_spec, 0, "", card_bg_rgb, accent_rgb, anchor_rgb, body_rgb
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
        left_accent_rgb=primary_rgb,
    )
    tf = card.text_frame
    body_font_pt = _compute_fitting_font_size(
        clean_pts,
        box_w_in=width_in - 0.10,
        box_h_in=total_h,
        min_pt=15.0,
        max_pt=19.5 if width_in > 8.0 else 17.0,
        space_after_pt=5.5,
    )
    for idx_pt, pt in enumerate(clean_pts):
        p = tf.paragraphs[0] if idx_pt == 0 else tf.add_paragraph()
        raw_anchor, body = _split_anchor_and_body(pt, f"{default_anchor_prefix} {idx_pt + 1}")
        anchor, _, _, _, _, _ = _resolve_card_theme_treatment(
            slide_spec, idx_pt, raw_anchor, card_bg_rgb, accent_rgb, anchor_rgb, body_rgb
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


def _render_right_visual_card(
    slide: Any,
    slide_spec: SlideSpec,
    resolved_diagram: str,
    top_in: float,
    bottom_in: float,
) -> None:
    """Renders the unified right-hand visual card container (`[x: 7.00..12.733, y: top_in..bottom_in]`)
    with the embedded image and a clean single-line caption inside the card (matching `rightZone` in `ui/app.js`).
    """
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    primary_rgb, accent_rgb, card_bg_rgb = _resolve_palette_tokens(slide_spec)
    anchor_rgb, body_rgb, _ = _resolve_text_colors(slide_spec, primary_rgb)

    frame_bg = (30, 41, 59) if tier == "STUDIO" else (card_bg_rgb if tier == "BEAUTIFIED" else (248, 250, 252))
    frame_border = accent_rgb if tier in ("BEAUTIFIED", "STUDIO") else ScoutsBSAPalette.BORDER_GRAY_RGB
    frame_h = max(2.40, round(bottom_in - top_in, 3))

    # Outer visual container card (named CardAccent_RightVisualFrame so child picture + caption sit inside it cleanly)
    frame_box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(7.00),
        Inches(top_in),
        Inches(5.733),
        Inches(frame_h),
    )
    frame_box.name = f"CardAccent_RightVisualFrame_{len(slide.shapes)}"
    _set_rounded_rect_radius(frame_box, 5.733, frame_h, radius_in=0.10)
    frame_box.fill.solid()
    frame_box.fill.fore_color.rgb = RGBColor(*frame_bg)
    frame_box.line.color.rgb = RGBColor(*frame_border)
    frame_box.line.width = Pt(1.5 if tier in ("BEAUTIFIED", "STUDIO") else 1.0)
    frame_box.text_frame.word_wrap = True

    cap_h = 0.48
    img_pad_x = 0.16
    img_pad_top = 0.12
    avail_img_w = 5.733 - (2 * img_pad_x)
    avail_img_h = max(1.80, frame_h - cap_h - img_pad_top - 0.08)
    try:
        pic = slide.shapes.add_picture(
            resolved_diagram,
            Inches(7.00 + img_pad_x),
            Inches(top_in + img_pad_top),
            width=Inches(avail_img_w),
        )
        max_h = Inches(avail_img_h)
        if pic.height > max_h:
            scale = float(max_h) / float(pic.height)
            pic.height = max_h
            pic.width = int(pic.width * scale)
        pic.left = int(Inches(7.00) + (Inches(5.733) - pic.width) // 2)
        pic.top = int(Inches(top_in + img_pad_top) + (Inches(avail_img_h) - pic.height) // 2)
    except Exception:
        pass

    raw_cap = _clean_text(slide_spec.visual_caption) or _clean_text(slide_spec.title)
    for prefix_rm in (
        "🍌 Hero Illustration: ",
        "✨ EDGE Skill Map: ",
        "EDGE Skill Concept Map — ",
        "EDGE Skill Concept Map - ",
        "EDGE Skill Concept Map, ",
        "EDGE Skill Map: ",
        "Figure: ",
    ):
        if raw_cap.startswith(prefix_rm):
            raw_cap = raw_cap[len(prefix_rm) :].strip()
    if len(raw_cap) > 68:
        raw_cap = raw_cap[:68].rsplit(" ", 1)[0].strip(" .,:;-—") or raw_cap[:68]

    cap_box = slide.shapes.add_textbox(
        Inches(7.14),
        Inches(round(bottom_in - cap_h - 0.04, 3)),
        Inches(5.45),
        Inches(cap_h),
    )
    captf = cap_box.text_frame
    captf.word_wrap = True
    captf.vertical_anchor = MSO_ANCHOR.MIDDLE
    captf.margin_top = Inches(0.02)
    captf.margin_bottom = Inches(0.02)
    captf.margin_left = Inches(0.06)
    captf.margin_right = Inches(0.06)
    cap_anchor, cap_body = _split_anchor_and_body(raw_cap, "")
    _set_paragraph_runs(
        captf.paragraphs[0],
        cap_anchor,
        cap_body,
        font_size_pt=15.0,
        anchor_rgb=anchor_rgb,
        body_rgb=body_rgb,
        space_after_pt=0.0,
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
    3. Right-zone unified visual card + clean caption when `resolved_diagram` is present in `BEAUTIFIED` / `STUDIO` modes.
    """
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    has_hero = bool(tier in ("BEAUTIFIED", "STUDIO") and resolved_diagram and os.path.exists(resolved_diagram))
    primary_rgb, accent_rgb, card_bg_rgb = _resolve_palette_tokens(slide_spec)
    anchor_rgb, body_rgb, _ = _resolve_text_colors(slide_spec, primary_rgb)
    req_bg_rgb = (30, 41, 59) if tier == "STUDIO" else (card_bg_rgb if tier == "BEAUTIFIED" else ScoutsBSAPalette.WHITE_RGB)

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

    # Top Strip: Full-width Official Requirement text (matches UI preview `.m3-slide-req-strip` with thick left accent)
    req_box = _add_styled_box(
        slide,
        left_in=0.60,
        top_in=1.10,
        width_in=12.133,
        height_in=req_h,
        bg_rgb=req_bg_rgb,
        border_rgb=accent_rgb,
        border_pt=1.5,
        left_accent_rgb=accent_rgb,
    )
    rtf = req_box.text_frame
    rtf.margin_top = Inches(0.06)
    rtf.margin_bottom = Inches(0.05)
    req_font_pt = _compute_fitting_font_size(
        [full_req_line],
        box_w_in=12.00,
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

    if has_hero and resolved_diagram:
        _render_right_visual_card(
            slide=slide,
            slide_spec=slide_spec,
            resolved_diagram=resolved_diagram,
            top_in=teach_top,
            bottom_in=content_bottom,
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
        left_accent_rgb=border_rgb,
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


def _parse_triage_column_items(raw_bullet: str, fallback_text: str) -> List[Tuple[str, str]]:
    """Parses a Triage Matrix column string into individual `(req_label, description)` items,
    stripping any legacy `'Knowledge & Concepts (N):'` prefixes.
    """
    s = _clean_text(raw_bullet) or _clean_text(fallback_text)
    s = re.sub(
        r"^(Knowledge & Concepts|Hands-On Field Skills|Field & Home Prerequisites)\s*\(\d+\)\s*:\s*",
        "",
        s,
        flags=re.IGNORECASE,
    ).rstrip(".")
    if ";" in s:
        raw_parts = [p.strip() for p in s.split(";") if p.strip()]
    else:
        raw_parts = [p.strip() for p in re.split(r"\)\s*,\s*(?=Req\s)", s, flags=re.IGNORECASE) if p.strip()]

    parsed: List[Tuple[str, str]] = []
    for p in raw_parts:
        item = p
        if "(" in item and not item.endswith(")") and ";" not in s:
            item += ")"
        m_paren = re.match(r"^(Req\s+[0-9a-zA-Z]+)\s*\((.+)\)$", item, flags=re.IGNORECASE)
        m_dash = re.match(r"^(Req\s+[0-9a-zA-Z]+)\s*[-:]\s*(.+)$", item, flags=re.IGNORECASE)
        if m_paren:
            parsed.append((m_paren.group(1).strip(), m_paren.group(2).strip()))
        elif m_dash:
            parsed.append((m_dash.group(1).strip(), m_dash.group(2).strip()))
        elif item:
            parsed.append(("", item.strip()))
    return parsed or [("", _clean_text(fallback_text))]


def _render_triage_matrix_zone(
    slide: Any,
    slide_spec: SlideSpec,
    full_width: bool = False,
    content_top: float = 2.08,
    content_bottom: float = 6.25,
) -> None:
    """Renders 3 non-overlapping vertical topic columns with clean headers and native OpenXML bulleted
    requirement items + optional Curriculum Scope bottom bar matching `ui/app.js` and `snipit_06ekalt1nmvvo.png`.
    """
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    primary_rgb, accent_rgb, card_bg_rgb = _resolve_palette_tokens(slide_spec)
    _, body_rgb, _ = _resolve_text_colors(slide_spec, primary_rgb)

    if tier == "STUDIO":
        c1_color = primary_rgb
        c2_color = (74, 222, 128)
        c3_color = (244, 196, 48)
        c1_bg = card_bg_rgb
        c2_bg = card_bg_rgb
        c3_bg = card_bg_rgb
        req_bold_rgb = (248, 250, 252)
        scope_bg = card_bg_rgb
        scope_border = accent_rgb
        scope_left = primary_rgb
    else:
        c1_color = ScoutsBSAPalette.NAVY_BLUE_RGB
        c2_color = (74, 93, 35)
        c3_color = ScoutsBSAPalette.EAGLE_RED_RGB
        c1_bg = (237, 244, 255)
        c2_bg = (242, 245, 236)
        c3_bg = (255, 245, 245)
        req_bold_rgb = (15, 23, 42)
        scope_bg = (241, 245, 249)
        scope_border = ScoutsBSAPalette.NAVY_BLUE_RGB
        scope_left = ScoutsBSAPalette.NAVY_BLUE_RGB

    if full_width:
        col_specs = [
            ("Discussion & Core Theory", c1_color, c1_bg, 0.60, 3.90),
            ("Hands-On Skill Demonstrations", c2_color, c2_bg, 4.71, 3.90),
            ("Field & Home Prerequisites", c3_color, c3_bg, 8.83, 3.90),
        ]
    else:
        col_specs = [
            ("Discussion & Core Theory", c1_color, c1_bg, 0.60, 1.96),
            ("Hands-On Skill Demonstrations", c2_color, c2_bg, 2.72, 1.96),
            ("Field & Home Prerequisites", c3_color, c3_bg, 4.84, 1.96),
        ]

    defaults = [
        "Core principles, definitions, and safety concepts.",
        "Practical hands-on techniques practiced with your patrol.",
        "Outdoor observation, field logs, or project application.",
    ]
    parsed_cols: List[List[Tuple[str, str]]] = [[], [], []]
    extra_bullets: List[str] = []

    if len(slide_spec.bullet_points) >= 3:
        for i in range(3):
            parsed_cols[i] = _parse_triage_column_items(slide_spec.bullet_points[i], defaults[i])
        extra_bullets = (
            [slide_spec.bullet_points[3]]
            if len(slide_spec.bullet_points) >= 4 and str(slide_spec.bullet_points[3]).strip()
            else []
        )
    elif slide_spec.cards:
        for card in slide_spec.cards:
            label = str(card.get("badge_label", "")).upper()
            r_tag = _clean_text(card.get("anchor_title") or "")
            r_desc = _clean_text(card.get("body_text") or "")
            if "HANDS" in label or "STATION" in label or "DEMONSTRATE" in label:
                parsed_cols[1].append((r_tag, r_desc))
            elif "CAMP" in label or "HOME" in label or "PREREQ" in label:
                parsed_cols[2].append((r_tag, r_desc))
            else:
                parsed_cols[0].append((r_tag, r_desc))
    else:
        for i in range(3):
            raw_b = slide_spec.bullet_points[i] if i < len(slide_spec.bullet_points) else ""
            parsed_cols[i] = _parse_triage_column_items(raw_b, defaults[i])

    total_avail_h = max(3.20, content_bottom - content_top)
    if extra_bullets:
        scope_h = 0.68 if len(extra_bullets) == 1 else 0.94
        gap_y = 0.14
        box_h = max(2.20, total_avail_h - scope_h - gap_y)
    else:
        scope_h = 0.0
        gap_y = 0.0
        box_h = total_avail_h

    for col_idx, (col_title, header_rgb, bg_rgb, left_x, col_w) in enumerate(col_specs):
        card = _add_styled_box(
            slide,
            left_in=left_x,
            top_in=content_top,
            width_in=col_w,
            height_in=box_h,
            bg_rgb=bg_rgb,
            border_rgb=header_rgb,
            border_pt=1.5 if tier in ("BEAUTIFIED", "STUDIO") else 1.25,
            top_accent_rgb=header_rgb,
        )
        tf = card.text_frame
        tf.margin_top = Inches(0.08)
        tf.margin_bottom = Inches(0.06)
        col_items = (parsed_cols[col_idx] or [("", defaults[col_idx])])[:4]
        col_font_pt = 15.0 if len(col_items) >= 4 else 16.0
        bullet_space_after = 2.0 if len(col_items) >= 4 else 4.0
        _set_paragraph_runs(
            tf.paragraphs[0],
            col_title,
            "",
            font_size_pt=min(18.0, col_font_pt + 1.5),
            anchor_rgb=header_rgb,
            space_after_pt=4.0,
        )
        for r_lbl, r_dsc in col_items:
            p = tf.add_paragraph()
            _enable_openxml_bullet(p, "•")
            _set_paragraph_runs(
                p,
                r_lbl,
                r_dsc,
                font_size_pt=col_font_pt,
                anchor_rgb=req_bold_rgb,
                body_rgb=body_rgb,
                space_after_pt=bullet_space_after,
                separator=" - ",
            )

    if extra_bullets:
        scope_top = round(content_top + box_h + gap_y, 2)
        scope_w = 12.133 if full_width else 6.20
        scope_card = _add_styled_box(
            slide,
            left_in=0.60,
            top_in=scope_top,
            width_in=scope_w,
            height_in=scope_h,
            bg_rgb=scope_bg,
            border_rgb=scope_border,
            border_pt=1.4,
            left_accent_rgb=scope_left,
        )
        stf = scope_card.text_frame
        stf.margin_top = Inches(0.05)
        stf.margin_bottom = Inches(0.05)
        scope_font_pt = _compute_fitting_font_size(
            extra_bullets,
            box_w_in=scope_w,
            box_h_in=scope_h,
            min_pt=15.0,
            max_pt=16.5,
            space_after_pt=3.0,
        )
        for idx_eb, eb in enumerate(extra_bullets):
            p_eb = stf.paragraphs[0] if idx_eb == 0 else stf.add_paragraph()
            eb_anchor, eb_body = _split_anchor_and_body(eb, "Curriculum Scope")
            icon_prefix = "📍 " if idx_eb == 0 else "🌐 "
            _set_paragraph_runs(
                p_eb,
                f"{icon_prefix}{eb_anchor}",
                eb_body,
                font_size_pt=scope_font_pt,
                anchor_rgb=primary_rgb,
                body_rgb=body_rgb,
                space_after_pt=2.0,
            )


def _render_differential_comparison_zone(
    slide: Any,
    slide_spec: SlideSpec,
    full_width: bool = False,
    content_top: float = 1.15,
    content_bottom: float = 6.95,
) -> None:
    """Renders 2 non-overlapping comparison cards matching `ui/app.js`."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    primary_rgb, accent_rgb, card_bg_rgb = _resolve_palette_tokens(slide_spec)
    _, body_rgb, _ = _resolve_text_colors(slide_spec, primary_rgb)

    cd = slide_spec.comparison_data or {}
    left_header = _clean_text(cd.get("left_header") or "Primary Condition / Method A")
    left_pts = cd.get("left_points") or slide_spec.bullet_points[:3] or ["Verify primary indicators and characteristics."]

    right_header = _clean_text(cd.get("right_header") or "Contrast Condition / Method B")
    right_pts = cd.get("right_points") or slide_spec.bullet_points[3:6] or ["Compare key differences and field response."]

    if tier == "STUDIO":
        l_accent, l_border, l_bg = primary_rgb, accent_rgb, card_bg_rgb
        r_accent, r_border, r_bg = (251, 113, 133), (251, 113, 133), (49, 16, 24)
    else:
        l_accent, l_border, l_bg = primary_rgb, accent_rgb, card_bg_rgb
        r_accent, r_border, r_bg = ScoutsBSAPalette.EAGLE_RED_RGB, ScoutsBSAPalette.EAGLE_RED_RGB, (255, 245, 245)

    if full_width:
        specs = [
            (0.60, 5.95, left_header, left_pts[:5], l_accent, l_border, l_bg),
            (6.78, 5.95, right_header, right_pts[:5], r_accent, r_border, r_bg),
        ]
    else:
        specs = [
            (0.60, 3.00, left_header, left_pts[:5], l_accent, l_border, l_bg),
            (3.75, 3.00, right_header, right_pts[:5], r_accent, r_border, r_bg),
        ]
    box_h = max(3.50, content_bottom - content_top)
    for left_x, box_w, header_text, pts, top_rgb, border_rgb, bg_rgb in specs:
        box = _add_styled_box(
            slide,
            left_in=left_x,
            top_in=content_top,
            width_in=box_w,
            height_in=box_h,
            bg_rgb=bg_rgb,
            border_rgb=border_rgb,
            border_pt=1.5,
            top_accent_rgb=top_rgb,
        )
        tf = box.text_frame
        col_font_pt = _compute_fitting_font_size(
            [header_text] + list(pts),
            box_w_in=box_w,
            box_h_in=box_h,
            min_pt=15.0,
            max_pt=19.5 if full_width else 17.0,
            space_after_pt=7.0,
        )
        _set_paragraph_runs(
            tf.paragraphs[0],
            header_text,
            "",
            font_size_pt=min(20.5, col_font_pt + 1.0),
            anchor_rgb=top_rgb,
            space_after_pt=8.0,
        )
        for pt in pts:
            p = tf.add_paragraph()
            _enable_openxml_bullet(p, "•")
            anchor, body = _split_anchor_and_body(pt, "")
            _set_paragraph_runs(
                p,
                anchor,
                body,
                font_size_pt=col_font_pt,
                anchor_rgb=top_rgb,
                body_rgb=body_rgb,
                space_after_pt=7.0,
            )


def _render_step_by_step_4card_zone(
    slide: Any,
    slide_spec: SlideSpec,
    full_width: bool = False,
    content_top: float = 1.15,
    content_bottom: float = 6.95,
) -> None:
    """Renders a 2x2 grid of procedural step cards matching `ui/app.js`."""
    primary_rgb, accent_rgb, card_bg_rgb = _resolve_palette_tokens(slide_spec)
    anchor_rgb, body_rgb, _ = _resolve_text_colors(slide_spec, primary_rgb)
    theme = str(getattr(slide_spec, "visual_theme", "") or "").upper()
    use_top_bar = "BENTO" in theme or "THREE_PILLAR" in theme or "ASYMMETRIC" in theme

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

    if full_width:
        grid_coords = [
            (0.60, content_top, 5.95),
            (6.78, content_top, 5.95),
            (0.60, row2_top, 12.133 if len(step_items) == 3 else 5.95),
            (6.78, row2_top, 5.95),
        ]
    else:
        grid_coords = [
            (0.60, content_top, 3.00),
            (3.75, content_top, 3.00),
            (0.60, row2_top, 6.15 if len(step_items) == 3 else 3.00),
            (3.75, row2_top, 3.00),
        ]
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    for idx_s, ((badge, anchor, raw_body), (lx, ty, cw)) in enumerate(zip(step_items[:4], grid_coords)):
        body = _concise_card_body(raw_body)
        _, c_bg, c_border, c_anchor_rgb, c_body_rgb, c_border_pt = _resolve_card_theme_treatment(
            slide_spec, idx_s, anchor, card_bg_rgb, accent_rgb, anchor_rgb, body_rgb
        )
        bar_color = (56, 189, 248) if "DARK_SLATE" in theme else (
            c_border if "SAFETY_ALERT" in theme else primary_rgb
        )
        card = _add_styled_box(
            slide,
            left_in=lx,
            top_in=ty,
            width_in=cw,
            height_in=card_h,
            bg_rgb=c_bg,
            border_rgb=c_border,
            border_pt=c_border_pt,
            top_accent_rgb=bar_color if use_top_bar else None,
            left_accent_rgb=None if use_top_bar else bar_color,
        )
        tf = card.text_frame
        head_line = f"{badge}  {anchor}"
        step_font_pt = _compute_fitting_font_size(
            [head_line, body],
            box_w_in=cw,
            box_h_in=card_h,
            min_pt=15.0,
            max_pt=18.5 if full_width else 16.5,
            space_after_pt=4.5,
        )
        use_pill = tier != "STANDARD" and card_h >= 1.10
        _set_paragraph_runs(
            tf.paragraphs[0],
            anchor if use_pill else head_line,
            "",
            font_size_pt=min(19.5, step_font_pt + 0.5),
            anchor_rgb=c_anchor_rgb,
            space_after_pt=4.5,
        )
        if use_pill:
            _indent_paragraph_for_pill(tf.paragraphs[0], indent_in=0.92)
            pill_left = round(lx + (0.0 if use_top_bar else 0.075) + 0.16, 3)
            pill_top = round(ty + (0.065 if use_top_bar else 0.0) + 0.09, 3)
            pill_bg = primary_rgb if tier == "STUDIO" else (15, 23, 42)
            pill_fg = (15, 23, 42) if tier == "STUDIO" else (255, 255, 255)
            _add_step_pill_badge(
                slide,
                left_in=pill_left,
                top_in=pill_top,
                pill_text=badge,
                bg_rgb=pill_bg,
                text_rgb=pill_fg,
                width_in=0.84,
                height_in=0.26,
            )
        p_body = tf.add_paragraph()
        _set_paragraph_runs(
            p_body,
            "",
            body,
            font_size_pt=step_font_pt,
            anchor_rgb=c_anchor_rgb,
            body_rgb=c_body_rgb,
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
    primary_rgb, accent_rgb, card_bg_rgb = _resolve_palette_tokens(slide_spec)
    anchor_rgb, body_rgb, _ = _resolve_text_colors(slide_spec, primary_rgb)

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
        bg_rgb=card_bg_rgb,
        border_rgb=accent_rgb,
        border_pt=1.5,
        left_accent_rgb=primary_rgb,
    )
    tf = top_box.text_frame
    entry_lines = (
        [f"{k}: {v}" for k, v in list(fields_dict.items())[:5]]
        if fields_dict
        else list(slide_spec.bullet_points[:5])
    )
    we_font_pt = _compute_fitting_font_size(
        [f"📋 {we_title}"] + entry_lines,
        box_w_in=box_w,
        box_h_in=top_h,
        min_pt=15.0,
        max_pt=19.5 if full_width else 17.0,
        space_after_pt=6.0,
    )
    _set_paragraph_runs(
        tf.paragraphs[0],
        f"📋 [{we_type}] {we_title}",
        "",
        font_size_pt=min(20.5, we_font_pt + 1.0),
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
        left_accent_rgb=tip_border,
    )
    ttf = tip_box.text_frame
    tip_font_pt = _compute_fitting_font_size(
        [f"Counselor Pro-Tip: {tip}"],
        box_w_in=box_w,
        box_h_in=tip_h,
        min_pt=15.0,
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
    """Renders a 2x2 grid of individual equipment & inspection checklist cards matching `ui/app.js`."""
    primary_rgb, accent_rgb, card_bg_rgb = _resolve_palette_tokens(slide_spec)
    anchor_rgb, body_rgb, _ = _resolve_text_colors(slide_spec, primary_rgb)
    theme = str(getattr(slide_spec, "visual_theme", "") or "").upper()
    use_top_bar = "BENTO" in theme or "THREE_PILLAR" in theme or "ASYMMETRIC" in theme

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

    chk_items = items[:4]
    total_h = max(3.40, content_bottom - content_top)
    gap_y = 0.16
    is_two_rows = len(chk_items) >= 3
    card_h = (total_h - gap_y) / 2.0 if is_two_rows else total_h
    row2_top = content_top + card_h + gap_y

    if full_width:
        grid_coords = [
            (0.60, content_top, 5.95),
            (6.78, content_top, 5.95),
            (0.60, row2_top, 12.133 if len(chk_items) == 3 else 5.95),
            (6.78, row2_top, 5.95),
        ]
    else:
        grid_coords = [
            (0.60, content_top, 3.00),
            (3.75, content_top, 3.00),
            (0.60, row2_top, 6.15 if len(chk_items) == 3 else 3.00),
            (3.75, row2_top, 3.00),
        ]

    for idx_c, (raw_item, (lx, ty, cw)) in enumerate(zip(chk_items, grid_coords)):
        a, b = _split_anchor_and_body(raw_item, f"Checklist {idx_c + 1}")
        _, c_bg, c_border, c_anchor_rgb, c_body_rgb, c_border_pt = _resolve_card_theme_treatment(
            slide_spec, idx_c, a, card_bg_rgb, accent_rgb, anchor_rgb, body_rgb
        )
        bar_color = (56, 189, 248) if "DARK_SLATE" in theme else (
            c_border if "SAFETY_ALERT" in theme else primary_rgb
        )
        card = _add_styled_box(
            slide,
            left_in=lx,
            top_in=ty,
            width_in=cw,
            height_in=card_h,
            bg_rgb=c_bg,
            border_rgb=c_border,
            border_pt=c_border_pt,
            top_accent_rgb=bar_color if use_top_bar else None,
            left_accent_rgb=None if use_top_bar else bar_color,
        )
        tf = card.text_frame
        head_line = f"[✓] {a}"
        chk_font_pt = _compute_fitting_font_size(
            [head_line, b] if b else [head_line],
            box_w_in=cw,
            box_h_in=card_h,
            min_pt=15.0,
            max_pt=18.5 if full_width else 16.0,
            space_after_pt=4.5,
        )
        _set_paragraph_runs(
            tf.paragraphs[0],
            head_line,
            "",
            font_size_pt=min(19.5, chk_font_pt + 0.5),
            anchor_rgb=c_anchor_rgb,
            space_after_pt=4.5,
        )
        if b:
            p_b = tf.add_paragraph()
            _set_paragraph_runs(
                p_b,
                "",
                b,
                font_size_pt=chk_font_pt,
                anchor_rgb=c_anchor_rgb,
                body_rgb=c_body_rgb,
                space_after_pt=3.0,
            )


def _render_socratic_quiz_zone(
    slide: Any,
    slide_spec: SlideSpec,
    full_width: bool = False,
    content_top: float = 1.15,
    content_bottom: float = 6.95,
) -> None:
    """Renders 3 stacked non-overlapping Socratic Quiz boxes (Scenario, Options, Verified Answer) matching `ui/app.js`."""
    tier = str(getattr(slide_spec, "beautification_tier", "STANDARD") or "STANDARD").upper()
    primary_rgb, accent_rgb, card_bg_rgb = _resolve_palette_tokens(slide_spec)
    _, body_rgb, _ = _resolve_text_colors(slide_spec, primary_rgb)
    qi = slide_spec.quiz_item or {}
    scenario = _clean_text(
        qi.get("scenario_prompt")
        or (slide_spec.bullet_points[0] if slide_spec.bullet_points else f"How should your patrol apply Requirement {slide_spec.req_number} in the field?")
    )
    options = qi.get("options") or slide_spec.bullet_points[1:4] or [
        "Follow standard step-by-step field procedure.",
        "Improvise without checking safety guidelines.",
        "Skip buddy check and proceed alone.",
    ]
    answer = _clean_text(qi.get("correct_answer") or "Option A — Follow standard step-by-step field procedure.")
    explanation = _clean_text(qi.get("explanation") or "Grounded in the BSA Guide to Safe Scouting and merit badge instruction.")
    box_w = 12.133 if full_width else 6.20
    total_h = max(3.60, content_bottom - content_top)
    gap = 0.14
    h1 = round((total_h - 2 * gap) * 0.27, 2)
    h2 = round((total_h - 2 * gap) * 0.40, 2)
    h3 = round(total_h - 2 * gap - h1 - h2, 2)

    s_bg = (30, 41, 59) if tier == "STUDIO" else card_bg_rgb
    s_border = primary_rgb
    s_box = _add_styled_box(
        slide, left_in=0.60, top_in=content_top, width_in=box_w, height_in=h1,
        bg_rgb=s_bg, border_rgb=s_border, border_pt=1.5, left_accent_rgb=s_border,
    )
    s_font = _compute_fitting_font_size(
        [f"❓ Patrol Scenario Challenge: {scenario}"], box_w_in=box_w, box_h_in=h1, min_pt=15.0, max_pt=18.5, space_after_pt=3.0
    )
    _set_paragraph_runs(
        s_box.text_frame.paragraphs[0], "❓ Patrol Scenario Challenge", scenario,
        font_size_pt=s_font, anchor_rgb=s_border, body_rgb=body_rgb,
    )

    o_bg = (30, 41, 59) if tier == "STUDIO" else card_bg_rgb
    o_border = accent_rgb
    o_box = _add_styled_box(
        slide, left_in=0.60, top_in=content_top + h1 + gap, width_in=box_w, height_in=h2,
        bg_rgb=o_bg, border_rgb=o_border, border_pt=1.35, left_accent_rgb=primary_rgb,
    )
    otf = o_box.text_frame
    o_font = _compute_fitting_font_size(
        ["Discussion Options (Ask Scouts First)"] + list(options[:3]),
        box_w_in=box_w, box_h_in=h2, min_pt=15.0, max_pt=17.5, space_after_pt=4.0
    )
    _set_paragraph_runs(
        otf.paragraphs[0], "Discussion Options (Ask Scouts First)", "",
        font_size_pt=min(18.5, o_font + 0.5), anchor_rgb=primary_rgb, space_after_pt=4.0,
    )
    for idx_o, opt in enumerate(options[:3], start=1):
        p = otf.add_paragraph()
        opt_letter = chr(64 + idx_o)
        clean_opt = _clean_text(opt)
        clean_opt = re.sub(rf"^Option\s+{opt_letter}\s*[:\-—]\s*", "", clean_opt, flags=re.IGNORECASE)
        _set_paragraph_runs(
            p, f"Option {opt_letter}", clean_opt, font_size_pt=o_font, anchor_rgb=primary_rgb, body_rgb=body_rgb, space_after_pt=4.0
        )

    a_bg = (6, 78, 59) if tier == "STUDIO" else (220, 252, 231)
    a_border = (74, 222, 128) if tier == "STUDIO" else (21, 128, 61)
    a_box = _add_styled_box(
        slide, left_in=0.60, top_in=content_top + h1 + gap + h2 + gap, width_in=box_w, height_in=h3,
        bg_rgb=a_bg, border_rgb=a_border, border_pt=1.5, left_accent_rgb=a_border,
    )
    atf = a_box.text_frame
    a_font = _compute_fitting_font_size(
        [f"✓ Verified Answer: {answer}", f"Why It Matters: {explanation}"],
        box_w_in=box_w, box_h_in=h3, min_pt=15.0, max_pt=17.5, space_after_pt=4.0
    )
    _set_paragraph_runs(
        atf.paragraphs[0], "✓ Verified Answer", answer,
        font_size_pt=a_font, anchor_rgb=a_border, body_rgb=body_rgb, space_after_pt=4.0,
    )
    p_exp = atf.add_paragraph()
    _set_paragraph_runs(
        p_exp, "Why It Matters", explanation,
        font_size_pt=a_font, anchor_rgb=a_border, body_rgb=body_rgb, space_after_pt=2.0,
    )


def _render_split_explainer_zone(
    slide: Any,
    slide_spec: SlideSpec,
    full_width: bool = False,
    content_top: float = 1.15,
    content_bottom: float = 6.95,
) -> None:
    """Renders structured bold-anchored instructional points as individual stacked horizontal cards
    matching the UI preview (`ui/app.js`).
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
    _apply_slide_tier_background(cover_slide, deck_tier, None)
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
        s_primary_rgb, s_accent_rgb, s_card_bg_rgb = _resolve_palette_tokens(slide_spec)
        s_anchor_rgb, s_body_rgb, s_title_rgb = _resolve_text_colors(slide_spec, s_primary_rgb)
        _apply_slide_tier_background(content_slide, s_tier, s_accent_rgb)

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
                strip_bg = (30, 41, 59) if s_tier == "STUDIO" else (s_card_bg_rgb if s_tier == "BEAUTIFIED" else ScoutsBSAPalette.WHITE_RGB)
                req_strip = _add_styled_box(
                    content_slide, left_in=0.60, top_in=1.10, width_in=12.133, height_in=strip_h,
                    bg_rgb=strip_bg, border_rgb=s_accent_rgb, border_pt=1.5, left_accent_rgb=s_accent_rgb,
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
                _render_right_visual_card(
                    slide=content_slide,
                    slide_spec=slide_spec,
                    resolved_diagram=resolved_diagram,
                    top_in=content_top,
                    bottom_in=content_bottom,
                )

        # ---------------------------------------------------------------------
        # OPTIONAL ZONE 5: Bottom Safety Warning or Full-Bleed Diagram Bar
        # ---------------------------------------------------------------------
        if slide_spec.safety_warning:
            warn_str = _clean_text(slide_spec.safety_warning)
            warn_font_pt = _compute_fitting_font_size(
                [f"🛡️ Guide to Safe Scouting: {warn_str}"], box_w_in=12.133, box_h_in=0.68, min_pt=15.0, max_pt=16.0, space_after_pt=0.0
            )
            warn_bg = (42, 24, 32) if s_tier == "STUDIO" else ScoutsBSAPalette.SOFT_RED_CARD_RGB
            warn_border = (248, 113, 113) if s_tier == "STUDIO" else ScoutsBSAPalette.EAGLE_RED_RGB
            callout_box = _add_styled_box(
                content_slide, left_in=0.60, top_in=6.38, width_in=12.133, height_in=0.68,
                bg_rgb=warn_bg, border_rgb=warn_border, border_pt=1.5, left_accent_rgb=warn_border,
            )
            stf = callout_box.text_frame
            stf.margin_top = Inches(0.05)
            stf.margin_bottom = Inches(0.04)
            _set_paragraph_runs(
                stf.paragraphs[0],
                "🛡️ Guide to Safe Scouting",
                warn_str,
                font_size_pt=warn_font_pt,
                anchor_rgb=warn_border,
                body_rgb=s_body_rgb,
                font_name="Roboto",
                space_after_pt=0.0,
                bold_body=False,
            )
        elif arch == "FULL_BLEED_IMAGE_EXPLAINER" and has_visual:
            diag_bg = (23, 37, 42) if s_tier == "STUDIO" else ScoutsBSAPalette.SOFT_OLIVE_CARD_RGB
            diag_border = (74, 222, 128) if s_tier == "STUDIO" else ScoutsBSAPalette.WARM_OLIVE_RGB
            callout_box = _add_styled_box(
                content_slide, left_in=0.60, top_in=6.38, width_in=12.133, height_in=0.68,
                bg_rgb=diag_bg, border_rgb=diag_border, border_pt=1.25, left_accent_rgb=diag_border,
            )
            stf = callout_box.text_frame
            key_takeaway = _clean_text(
                " ".join(slide_spec.bullet_points[:2])
                if slide_spec.bullet_points
                else (slide_spec.visual_caption or slide_spec.title)
            )
            diag_font_pt = _compute_fitting_font_size(
                [f"DIAGRAM EXPLANATION: {key_takeaway}"], box_w_in=12.133, box_h_in=0.68, min_pt=15.0, max_pt=16.5, space_after_pt=0.0
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
