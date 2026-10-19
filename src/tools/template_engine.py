"""PowerPoint Template & Custom Slide Theme Engine (Option C Hybrid Template Studio).

Supports:
1. Curated built-in library of 8 council-neutral Scouting America & BSA templates.
2. Native OpenXML `.pptx` Slide Master & Layout ingestion, legacy OLE2 `.ppt` binary stream
   extraction, and custom background/frame image uploads (`.png`, `.jpg`, `.webp`) or URL imports.
3. Dynamic `SafeCanvasBounds` calculation so all 12 BSA EDGE slide archetypes scale cleanly
   above template footer bars, horizon silhouettes, and corner logos with zero AABB collisions.
4. Orthogonal layering with `Warm Cream` (`BEAUTIFIED`), `Crisp White` (`STANDARD`), and
   `Dark Slate` (`STUDIO`) slide themes, plus `MATCH_TEMPLATE` brand palette extraction.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = REPO_ROOT / "assets" / "templates"
OVERLAYS_DIR = TEMPLATES_DIR / "overlays"
PREVIEWS_DIR = TEMPLATES_DIR / "previews"
CUSTOM_TEMPLATES_DIR = TEMPLATES_DIR / "custom"
CATALOG_JSON_PATH = TEMPLATES_DIR / "catalog.json"


class SafeCanvasBounds(BaseModel):
    """Defines the non-overlapping safe instructional bounding box (in inches on a 13.333" x 7.50" canvas)."""

    left_in: float = Field(0.60, description="Left safe margin in inches.")
    right_in: float = Field(12.733, description="Right safe coordinate in inches.")
    header_top_in: float = Field(0.20, description="Top coordinate for header banner in inches.")
    header_height_in: float = Field(0.82, description="Height of header banner in inches.")
    header_banner_height_in: float = Field(0.0, description="Height of top template header strip in inches when present.")
    content_top_min_in: float = Field(1.15, description="Minimum top coordinate for body cards in inches.")
    content_bottom_max_in: float = Field(
        6.95,
        description="Maximum bottom coordinate for body cards/visuals in inches (clamped to ~6.52\" when template has footer bar/logo).",
    )
    safety_bar_height_in: float = Field(0.72, description="Height of safety/callout bar when present.")
    footer_left_in: float = Field(0.60, description="Left coordinate for slide footer metadata (shifts right when template has a bottom-left logo).")
    footer_top_in: float = Field(7.15, description="Top coordinate for slide footer metadata.")
    footer_max_width_in: float = Field(12.133, description="Max width for footer text to avoid bottom-right logos.")
    suppress_native_footer: bool = Field(
        False,
        description="When True, renders compact footer metadata inside or above the template branding strip without overlapping corner logos.",
    )


class TemplateProfile(BaseModel):
    """Metadata, visual overlay layers, brand palette, and SafeCanvasBounds for a PowerPoint template."""

    template_id: str = Field(..., description="Unique slug identifier for the template.")
    name: str = Field(..., description="Clean, descriptive template title.")
    category: str = Field("Scouting America Official", description="Template category label.")
    description: str = Field("", description="Human-friendly summary of the template design and layout.")
    is_builtin: bool = Field(True, description="True for built-in curated templates; False for user-uploaded/URL templates.")
    pptx_path: Optional[str] = Field(None, description="Relative or absolute path to the master .pptx template file.")
    content_layout_index: int = Field(6, description="Preferred slide_layouts index in pptx_path for instructional slides.")
    cover_layout_index: int = Field(0, description="Preferred slide_layouts index in pptx_path for cover slide.")
    use_native_master_layouts: bool = Field(
        False,
        description="True if pptx_path has native Slide Layouts with embedded footer/logo shapes (e.g., America 250 or Forest Sunrise).",
    )
    primary_hex: str = Field("#003F87", description="Primary brand color hex extracted from or assigned to the template.")
    accent_hex: str = Field("#D4AF37", description="Secondary accent color hex extracted from or assigned to the template.")
    card_bg_hex: str = Field("#EFF6FF", description="Soft tinted card background hex harmonizing with the template.")
    cover_bg_url: str = Field("", description="Optional cover slide hero background image URL.")
    canvas_watermark_url: str = Field("", description="Optional subtle full-canvas watermark/contour URL for content slides.")
    bottom_bar_hex: str = Field("", description="Optional bottom branding bar hex color.")
    bottom_accent_hex: str = Field("", description="Optional thin accent stripe hex above bottom bar.")
    bottom_silhouette_url: str = Field("", description="Optional full-width bottom horizon silhouette PNG URL.")
    bottom_silhouette_dark_url: str = Field("", description="Optional white silhouette PNG URL for Dark Slate mode.")
    corner_logo_url: str = Field("", description="Optional bottom-right branding lockup PNG URL.")
    corner_logo_dark_url: str = Field("", description="Optional white bottom-right lockup PNG URL for Dark Slate mode.")
    top_banner_url: str = Field("", description="Optional top header crest/banner PNG URL.")
    safe_bounds: SafeCanvasBounds = Field(default_factory=SafeCanvasBounds)


def hex_to_rgb(hex_str: str, default: Tuple[int, int, int] = (0, 63, 135)) -> Tuple[int, int, int]:
    """Converts a `#RRGGBB` string into an `(R, G, B)` integer tuple."""
    clean = str(hex_str or "").strip().lstrip("#")
    if len(clean) == 6:
        try:
            return (int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))
        except ValueError:
            pass
    return default


VISUAL_THEME_ALIAS_MAP: Dict[str, str] = {
    "WARM_CREAM": "BEAUTIFIED",
    "WARM_CREME": "BEAUTIFIED",
    "CREAM": "BEAUTIFIED",
    "CREME": "BEAUTIFIED",
    "BEAUTIFIED": "BEAUTIFIED",
    "CRISP_WHITE": "STANDARD",
    "WHITE": "STANDARD",
    "STANDARD": "STANDARD",
    "DARK_SLATE": "STUDIO",
    "SLATE": "STUDIO",
    "STUDIO": "STUDIO",
}


def normalize_visual_theme(raw_tier: Optional[str], default: str = "BEAUTIFIED") -> str:
    """Normalizes modern slide theme names (`WARM_CREAM`/`CREAM`, `CRISP_WHITE`/`WHITE`, `DARK_SLATE`/`SLATE`) and legacy aliases (`BEAUTIFIED`, `STANDARD`, `STUDIO`)."""
    clean = str(raw_tier or "").strip().upper().replace("-", "_").replace(" ", "_")
    return VISUAL_THEME_ALIAS_MAP.get(clean, default)


def get_contrasting_text_rgb(bg_hex: Optional[str]) -> Tuple[int, int, int]:
    """Computes relative luminance of `bg_hex` and returns high-contrast white `(255, 255, 255)` for dark bars or dark slate `(15, 23, 42)` for light bars."""
    r, g, b = hex_to_rgb(str(bg_hex or "#003F87"), (0, 63, 135))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return (255, 255, 255) if luminance < 0.55 else (15, 23, 42)


BUILTIN_TEMPLATES: List[TemplateProfile] = [
    TemplateProfile(
        template_id="default_workbench",
        name="Workbench Classic",
        category="Workbench Default",
        description="Full-bleed 16:9 instructional canvas maximizing vertical card space (6.95\" content height) with Scout Navy & Gold accents.",
        is_builtin=True,
        pptx_path=None,
        use_native_master_layouts=False,
        primary_hex="#003F87",
        accent_hex="#D4AF37",
        card_bg_hex="#EFF6FF",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.20,
            header_height_in=0.82,
            content_top_min_in=1.15,
            content_bottom_max_in=6.95,
            safety_bar_height_in=0.74,
            footer_top_in=7.15,
            footer_max_width_in=12.133,
            suppress_native_footer=False,
        ),
    ),
    TemplateProfile(
        template_id="scouting_america_250",
        name="BSA America 250™",
        category="Scouting America Official",
        description="Commemorative 250th Anniversary widescreen template featuring the dual Scouting America | America 250™ lockup, red-and-blue ribbon emblem, and #075697 footer bar.",
        is_builtin=True,
        pptx_path="assets/templates/scouting_america_250.pptx",
        content_layout_index=11,  # 'Blank' layout carrying Rectangle 2 (#075697 bar) + Picture 6 (America 250 lockup)
        cover_layout_index=0,
        use_native_master_layouts=True,
        primary_hex="#075697",
        accent_hex="#CE1126",
        card_bg_hex="#F0F7FF",
        bottom_bar_hex="#075697",
        bottom_accent_hex="#CE1126",
        corner_logo_url="/assets/templates/overlays/america250_lockup.png",
        corner_logo_dark_url="/assets/templates/overlays/america250_lockup.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.54,
            safety_bar_height_in=0.68,
            footer_top_in=7.02,
            footer_max_width_in=9.80,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="scouting_america_forest_sunrise",
        name="BSA Forest Sunrise",
        category="Scouting America Official",
        description="National Scouting America widescreen template with a sunlit pine meadow cover slide, #075697 bottom branding bar, and official Scouting America™ horizontal lockup.",
        is_builtin=True,
        pptx_path="assets/templates/scouting_america_forest_sunrise.pptx",
        content_layout_index=12,  # 'Blank' layout carrying Rectangle 5 (#075697 bar) + Picture 4 (Scouting America lockup)
        cover_layout_index=7,
        use_native_master_layouts=True,
        primary_hex="#075697",
        accent_hex="#D4AF37",
        card_bg_hex="#F0F7FF",
        cover_bg_url="/assets/templates/overlays/forest_sunrise_cover.jpg",
        bottom_bar_hex="#075697",
        bottom_accent_hex="#D4AF37",
        corner_logo_url="/assets/templates/overlays/scouting_america_horiz_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_america_horiz_white.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.54,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.40,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="scouting_america_topographic",
        name="BSA Topographic",
        category="Scouting America Official",
        description="Modern topographic contour-map watermark template with subtle backcountry elevation lines, airy instructional whitespace, and the national Scouting America™ lockup.",
        is_builtin=True,
        pptx_path="assets/templates/scouting_america_topographic.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=True,
        primary_hex="#003F87",
        accent_hex="#0284C7",
        card_bg_hex="#F0F9FF",
        canvas_watermark_url="/assets/templates/overlays/topographic_contour_bg.png",
        bottom_bar_hex="#003F87",
        bottom_accent_hex="#38BDF8",
        corner_logo_url="/assets/templates/overlays/scouting_america_horiz_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_america_horiz_white.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.55,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.50,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="scouting_america_high_adventure_rock",
        name="BSA High Adventure",
        category="Scouting America Official",
        description="Dynamic outdoor action template featuring rock-climbing and backcountry adventure photography paired with crisp widescreen layouts and Scouting America™ branding.",
        is_builtin=True,
        pptx_path="assets/templates/scouting_america_high_adventure_rock.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=False,
        primary_hex="#075697",
        accent_hex="#EA580C",
        card_bg_hex="#FFF7ED",
        cover_bg_url="/assets/templates/overlays/high_adventure_climb.jpg",
        bottom_bar_hex="#075697",
        bottom_accent_hex="#CE1126",
        corner_logo_url="/assets/templates/overlays/scouting_america_horiz_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_america_horiz_white.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.55,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.50,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="classic_outdoor_silhouette_navy",
        name="BSA Outdoor Adventure",
        category="Heritage & High Adventure",
        description="Heritage Scouting template featuring the iconic Scout Navy outdoor adventure horizon silhouette (zip-lining, canoe portage, mountain biking, and backpacking) along the bottom ridge.",
        is_builtin=True,
        pptx_path="assets/templates/classic_outdoor_silhouette_navy.pptx",
        content_layout_index=6,
        cover_layout_index=6,
        use_native_master_layouts=False,
        primary_hex="#003F87",
        accent_hex="#D4AF37",
        card_bg_hex="#EFF6FF",
        bottom_silhouette_url="/assets/templates/overlays/classic_silhouette_navy.png",
        bottom_silhouette_dark_url="/assets/templates/overlays/classic_silhouette_white.png",
        corner_logo_url="",
        corner_logo_dark_url="",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.78,
            content_top_min_in=1.10,
            content_bottom_max_in=6.55,
            safety_bar_height_in=0.68,
            footer_top_in=7.08,
            footer_max_width_in=12.133,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="classic_fleur_crimson_crest",
        name="BSA Fleur-de-Lis Crest",
        category="Heritage & High Adventure",
        description="Formal Court of Honor and Eagle-required instruction template with Eagle Crimson & Navy footer rule and the full-color universal Scouting Fleur-de-Lis emblem.",
        is_builtin=True,
        pptx_path="assets/templates/classic_fleur_crimson_crest.pptx",
        content_layout_index=6,
        cover_layout_index=6,
        use_native_master_layouts=False,
        primary_hex="#8B0000",
        accent_hex="#003F87",
        card_bg_hex="#FFF5F5",
        bottom_bar_hex="#8B0000",
        bottom_accent_hex="#003F87",
        corner_logo_url="/assets/templates/overlays/scouting_fleur_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_fleur_color.png",
        top_banner_url="/assets/templates/overlays/classic_fleur_banner.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.54,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=11.20,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="wilderness_camp_timber",
        name="BSA Summer Camp",
        category="Heritage & High Adventure",
        description="Outdoor summer camp and Wood Badge timber heritage template with forest-olive and gold accents, designed for camp pavilions and field instruction.",
        is_builtin=True,
        pptx_path="assets/templates/wilderness_camp_timber.pptx",
        content_layout_index=6,
        cover_layout_index=6,
        use_native_master_layouts=False,
        primary_hex="#2E4600",
        accent_hex="#D4AF37",
        card_bg_hex="#F1F8E9",
        cover_bg_url="/assets/templates/overlays/forest_sunrise_cover.jpg",
        bottom_bar_hex="#2E4600",
        bottom_accent_hex="#D4AF37",
        corner_logo_url="/assets/templates/overlays/scouting_america_horiz_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_america_horiz_white.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.54,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.50,
            suppress_native_footer=True,
        ),
    ),
]


def _ensure_dirs() -> None:
    for d in (TEMPLATES_DIR, OVERLAYS_DIR, PREVIEWS_DIR, CUSTOM_TEMPLATES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_template_catalog() -> List[TemplateProfile]:
    """Returns all built-in templates plus any custom user-uploaded or URL-imported templates."""
    _ensure_dirs()
    by_id: Dict[str, TemplateProfile] = {t.template_id: t for t in BUILTIN_TEMPLATES}
    if CATALOG_JSON_PATH.exists():
        try:
            raw = json.loads(CATALOG_JSON_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict) and item.get("template_id"):
                        tid = str(item["template_id"])
                        if tid not in by_id:
                            by_id[tid] = TemplateProfile(**item)
        except Exception:
            pass
    else:
        save_template_catalog(list(by_id.values()))
    return list(by_id.values())


def save_template_catalog(profiles: List[TemplateProfile]) -> None:
    """Persists the full template catalog to `assets/templates/catalog.json`."""
    _ensure_dirs()
    CATALOG_JSON_PATH.write_text(
        json.dumps([p.model_dump() for p in profiles], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_template_profile(template_id: Optional[str]) -> TemplateProfile:
    """Resolves a `TemplateProfile` by `template_id`, falling back to `default_workbench`."""
    norm = str(template_id or "default_workbench").strip() or "default_workbench"
    for prof in load_template_catalog():
        if prof.template_id == norm:
            return prof
    return BUILTIN_TEMPLATES[0]


def delete_custom_template(template_id: str) -> bool:
    """Deletes a custom (non-builtin) template from the catalog."""
    norm = str(template_id or "").strip()
    if not norm:
        return False
    profiles = load_template_catalog()
    target = next((p for p in profiles if p.template_id == norm), None)
    if not target or target.is_builtin:
        return False
    remaining = [p for p in profiles if p.template_id != norm]
    save_template_catalog(remaining)
    for f in list(OVERLAYS_DIR.glob(f"{norm}*")) + list(TEMPLATES_DIR.glob(f"{norm}*")):
        try:
            if f.is_file():
                f.unlink()
        except Exception:
            pass
    return True


def update_template_metadata(
    template_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    bottom_safe_in: Optional[float] = None,
) -> Optional[TemplateProfile]:
    """Updates `name`, `description`, and optional `bottom_safe_in` for a custom (non-builtin) template."""
    norm = str(template_id or "").strip()
    if not norm:
        return None
    profiles = load_template_catalog()
    updated_target: Optional[TemplateProfile] = None
    for p in profiles:
        if p.template_id == norm:
            if p.is_builtin:
                return None
            if name is not None and str(name).strip():
                p.name = str(name).strip()
            if description is not None:
                p.description = str(description).strip()
            if bottom_safe_in is not None:
                p.safe_bounds.content_bottom_max_in = max(5.80, min(6.95, float(bottom_safe_in)))
            updated_target = p
            break
    if updated_target is not None:
        save_template_catalog(profiles)
    return updated_target


def _extract_dominant_color_hex(img_path: Path, default_hex: str = "#003F87") -> str:
    """Extracts a rich dark/medium brand color from an uploaded image or logo."""
    try:
        with Image.open(img_path) as im:
            rgba = im.convert("RGBA").resize((64, 64))
            pixels = list(rgba.getdata())
            candidates: List[Tuple[int, int, int]] = []
            for r, g, b, a in pixels:
                if a < 128:
                    continue
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                if 20 <= lum <= 210:
                    candidates.append((r, g, b))
            if candidates:
                r_avg = sum(c[0] for c in candidates) // len(candidates)
                g_avg = sum(c[1] for c in candidates) // len(candidates)
                b_avg = sum(c[2] for c in candidates) // len(candidates)
                return f"#{r_avg:02X}{g_avg:02X}{b_avg:02X}"
    except Exception:
        pass
    return default_hex


def _derive_soft_card_bg_hex(primary_hex: str) -> str:
    """Blends 92% white (#FFFFFF) with 8% of `primary_hex` to produce a subtle, harmonious card tint."""
    r, g, b = hex_to_rgb(primary_hex, (0, 63, 135))
    cr = min(255, int(round(255 * 0.92 + r * 0.08)))
    cg = min(255, int(round(255 * 0.92 + g * 0.08)))
    cb = min(255, int(round(255 * 0.92 + b * 0.08)))
    return f"#{cr:02X}{cg:02X}{cb:02X}"


def _iter_master_leaf_pictures(shapes: Any, scale_x: float = 1.0, scale_y: float = 1.0, off_x: float = 0.0, off_y: float = 0.0):
    """Recursively yields `(shape, left_in, top_in, width_in, height_in)` for all picture shapes on a Slide Master or Layout."""
    for s in shapes:
        try:
            sx = off_x + float(s.left.inches) * scale_x
            sy = off_y + float(s.top.inches) * scale_y
            sw = float(s.width.inches) * scale_x
            sh = float(s.height.inches) * scale_y
            if s.shape_type == 13:  # PICTURE
                yield (s, sx, sy, sw, sh)
            elif s.shape_type == 6:  # GROUP
                # Map child coordinates from group chOff/chExt to slide coordinates when available
                grp_el = s._element
                xfrm = grp_el.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm")
                if xfrm is not None:
                    ext_el = xfrm.find("{http://schemas.openxmlformats.org/drawingml/2006/main}ext")
                    choff_el = xfrm.find("{http://schemas.openxmlformats.org/drawingml/2006/main}chOff")
                    chext_el = xfrm.find("{http://schemas.openxmlformats.org/drawingml/2006/main}chExt")
                    if ext_el is not None and choff_el is not None and chext_el is not None:
                        cx = max(1.0, float(ext_el.get("cx", "1")))
                        cy = max(1.0, float(ext_el.get("cy", "1")))
                        ch_cx = max(1.0, float(chext_el.get("cx", "1")))
                        ch_cy = max(1.0, float(chext_el.get("cy", "1")))
                        ch_x_in = float(choff_el.get("x", "0")) / 914400.0
                        ch_y_in = float(choff_el.get("y", "0")) / 914400.0
                        g_sx = scale_x * (cx / ch_cx)
                        g_sy = scale_y * (cy / ch_cy)
                        g_ox = sx - ch_x_in * g_sx
                        g_oy = sy - ch_y_in * g_sy
                        yield from _iter_master_leaf_pictures(s.shapes, g_sx, g_sy, g_ox, g_oy)
                        continue
                yield from _iter_master_leaf_pictures(s.shapes, scale_x, scale_y, 0.0, 0.0)
        except Exception:
            continue


def ingest_custom_template_bytes(
    raw_bytes: bytes,
    original_filename: str,
    custom_name: Optional[str] = None,
    bottom_safe_in: float = 6.55,
) -> TemplateProfile:
    """Ingests an uploaded `.pptx`, legacy `.ppt`, or `.png`/`.jpg`/`.webp` file and registers a `TemplateProfile`."""
    _ensure_dirs()
    ext = Path(original_filename or "template.pptx").suffix.lower()
    digest = hashlib.sha256(raw_bytes).hexdigest()[:10]
    stem_slug = re.sub(r"[^a-z0-9]+", "_", Path(original_filename or "custom").stem.lower()).strip("_") or "custom"
    template_id = f"custom_{stem_slug}_{digest}"
    display_name = (custom_name or Path(original_filename).stem.replace("-", " ").replace("_", " ").title()).strip()

    primary_hex = "#003F87"
    accent_hex = "#D4AF37"
    watermark_url = ""
    corner_logo_url = ""
    bottom_silhouette_url = ""
    top_banner_url = ""
    bottom_bar_hex = "#003F87"
    use_native_master = False
    pptx_rel_path: Optional[str] = None
    content_layout_idx = 6
    header_top_in = 0.18
    header_banner_height_in = 0.0
    content_top_min_in = 1.12
    footer_left_in = 0.60
    footer_top_in = 6.98
    footer_max_width_in = 9.50

    if ext == ".pptx":
        out_pptx = CUSTOM_TEMPLATES_DIR / f"{template_id}.pptx"
        out_pptx.write_bytes(raw_bytes)
        pptx_rel_path = f"assets/templates/custom/{template_id}.pptx"
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as z:
                if "ppt/theme/theme1.xml" in z.namelist():
                    xml = z.read("ppt/theme/theme1.xml").decode("utf-8", errors="ignore")
                    clrs = re.findall(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', xml)
                    if len(clrs) >= 3:
                        primary_hex = f"#{clrs[2].upper()}"
                    if len(clrs) >= 4:
                        accent_hex = f"#{clrs[3].upper()}"

            prs = Presentation(str(out_pptx))
            slide_w = max(1.0, float(prs.slide_width.inches))
            slide_h = max(1.0, float(prs.slide_height.inches))
            layouts = list(prs.slide_layouts)
            for idx_l, lay in enumerate(layouts):
                if "blank" in (lay.name or "").lower():
                    content_layout_idx = idx_l
                    break

            # Inspect Slide Master (and fallback layouts) for top header strips, bottom footer banners, and corner logos
            master_pics = list(_iter_master_leaf_pictures(prs.slide_masters[0].shapes)) if prs.slide_masters else []
            if not master_pics:
                for lay in layouts:
                    master_pics.extend(list(_iter_master_leaf_pictures(lay.shapes)))

            top_strip_pics = []
            bottom_band_pics = []
            full_bg_pics = []
            sampled_banner_colors: List[str] = []

            for shp, sx, sy, sw, sh in master_pics:
                # Full-canvas background watermark
                if sw >= slide_w * 0.80 and sh >= slide_h * 0.65:
                    full_bg_pics.append((shp, sx, sy, sw, sh))
                # Clean top header strip (e.g. Guide to Advancement Master Picture 9 at y=-0.03, h=0.27, w=10.03)
                elif sy <= slide_h * 0.10 and sh <= slide_h * 0.22 and sw >= slide_w * 0.70:
                    top_strip_pics.append((shp, sx, sy, sw, sh))
                # Bottom footer banner or bottom-left/bottom-right logo (y >= 0.78 * slide_h)
                elif sy >= slide_h * 0.78 and sh <= slide_h * 0.25:
                    bottom_band_pics.append((shp, sx, sy, sw, sh))

            # 1. Extract Top Header Strip if present on Slide Master
            if top_strip_pics:
                top_shp, _, _, _, top_h_in = top_strip_pics[-1]
                with Image.open(io.BytesIO(top_shp.image.blob)) as tim:
                    t_rgba = tim.convert("RGBA").resize((2400, max(48, int(round(tim.height * (2400.0 / max(1, tim.width)))))))
                    top_path = OVERLAYS_DIR / f"{template_id}_header_strip.png"
                    t_rgba.save(top_path)
                    top_banner_url = f"/assets/templates/overlays/{top_path.name}"
                    sampled_banner_colors.append(_extract_dominant_color_hex(top_path, primary_hex))
                    header_banner_height_in = round(max(0.24, min(0.45, top_h_in)), 2)
                    header_top_in = round(header_banner_height_in + 0.06, 2)
                    content_top_min_in = round(max(1.12, header_top_in + 0.82), 2)

            # 2. Composite Bottom Footer Banner (supports full-width textured bars + left/right logos in z-order)
            has_wide_bottom_bar = any(sw >= slide_w * 0.65 for _, _, _, sw, _ in bottom_band_pics)
            if bottom_band_pics and (has_wide_bottom_bar or len(bottom_band_pics) >= 2):
                min_y = min(max(0.0, sy) for _, _, sy, _, _ in bottom_band_pics)
                band_h_in = max(0.48, min(0.95, slide_h - min_y))
                canvas_w_px = 2400
                canvas_h_px = max(96, int(round((band_h_in / 13.333) * canvas_w_px)))
                comp = Image.new("RGBA", (canvas_w_px, canvas_h_px), (0, 0, 0, 0))
                left_logo_right_in_16_9 = 0.0
                right_logo_left_in_16_9 = 13.333

                for shp, sx, sy, sw, sh in bottom_band_pics:
                    with Image.open(io.BytesIO(shp.image.blob)) as pim:
                        p_rgba = pim.convert("RGBA")
                        # Stretch full-width background strips across 13.333"; preserve 1:1 aspect ratio on logos
                        if sw >= slide_w * 0.65:
                            target_w_px = canvas_w_px
                            target_x_px = 0
                        else:
                            # Preserve physical width in inches on the 13.333" widescreen canvas
                            w_in_16_9 = sw
                            target_w_px = max(16, int(round((w_in_16_9 / 13.333) * canvas_w_px)))
                            if sx <= slide_w * 0.25:
                                x_in_16_9 = max(0.0, sx)
                                left_logo_right_in_16_9 = max(left_logo_right_in_16_9, x_in_16_9 + w_in_16_9)
                            elif sx + sw >= slide_w * 0.75:
                                right_margin_in = max(0.0, slide_w - (sx + sw))
                                x_in_16_9 = max(0.0, 13.333 - right_margin_in - w_in_16_9)
                                right_logo_left_in_16_9 = min(right_logo_left_in_16_9, x_in_16_9)
                            else:
                                x_in_16_9 = (sx / slide_w) * 13.333
                            target_x_px = max(0, min(canvas_w_px - target_w_px, int(round((x_in_16_9 / 13.333) * canvas_w_px))))

                        rel_y = max(0.0, (sy - min_y) / max(0.05, band_h_in))
                        target_y_px = max(0, min(canvas_h_px - 8, int(round(rel_y * canvas_h_px))))
                        target_h_px = max(8, min(canvas_h_px - target_y_px, int(round((sh / max(0.05, band_h_in)) * canvas_h_px))))
                        resized = p_rgba.resize((target_w_px, target_h_px), Image.Resampling.LANCZOS)
                        comp.alpha_composite(resized, (target_x_px, target_y_px))

                footer_out = OVERLAYS_DIR / f"{template_id}_footer_banner.png"
                comp.save(footer_out)
                bottom_silhouette_url = f"/assets/templates/overlays/{footer_out.name}"
                sampled_banner_colors.insert(0, _extract_dominant_color_hex(footer_out, primary_hex))
                footer_top_in = round(max(6.92, 7.50 - band_h_in + 0.08), 2)
                if left_logo_right_in_16_9 > 0.8:
                    footer_left_in = round(min(5.2, left_logo_right_in_16_9 + 0.25), 2)
                footer_right_limit = min(12.733, right_logo_left_in_16_9 - 0.25)
                footer_max_width_in = round(max(5.5, footer_right_limit - footer_left_in), 2)
            elif bottom_band_pics:
                # Single corner logo without a full-width bottom texture bar
                logo_shp, _, _, _, _ = bottom_band_pics[-1]
                l_ext = f".{logo_shp.image.ext.lower()}" if getattr(logo_shp.image, "ext", None) else ".png"
                saved_l = OVERLAYS_DIR / f"{template_id}_logo{l_ext}"
                saved_l.write_bytes(logo_shp.image.blob)
                corner_logo_url = f"/assets/templates/overlays/{saved_l.name}"
                sampled_banner_colors.append(_extract_dominant_color_hex(saved_l, primary_hex))

            # 3. Extract Full-Canvas Watermark if present
            if full_bg_pics:
                bg_shp, _, _, _, _ = full_bg_pics[0]
                b_ext = f".{bg_shp.image.ext.lower()}" if getattr(bg_shp.image, "ext", None) else ".png"
                saved_bg = OVERLAYS_DIR / f"{template_id}_bg{b_ext}"
                saved_bg.write_bytes(bg_shp.image.blob)
                watermark_url = f"/assets/templates/overlays/{saved_bg.name}"
                sampled_banner_colors.append(_extract_dominant_color_hex(saved_bg, primary_hex))

            # 4. Fallback media scan if Slide Master had no direct picture shapes
            if not bottom_silhouette_url and not corner_logo_url and not watermark_url:
                with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as z:
                    media_files = [
                        n for n in z.namelist() if n.startswith("ppt/media/") and n.lower().endswith((".png", ".jpg", ".jpeg"))
                    ]
                    for idx_m, mname in enumerate(media_files[:3]):
                        m_ext = Path(mname).suffix.lower()
                        saved_m = OVERLAYS_DIR / f"{template_id}_media_{idx_m}{m_ext}"
                        saved_m.write_bytes(z.read(mname))
                        with Image.open(saved_m) as im:
                            aspect = im.width / max(1, im.height)
                            if im.width >= 1000 and im.height >= 550 and not watermark_url:
                                watermark_url = f"/assets/templates/overlays/{saved_m.name}"
                            elif im.width >= 90 and im.height <= 420 and aspect >= 0.75 and not corner_logo_url:
                                corner_logo_url = f"/assets/templates/overlays/{saved_m.name}"

            # Prioritize true visual colors sampled from the Master's header/footer banners over generic Office theme1.xml defaults
            if sampled_banner_colors:
                primary_hex = sampled_banner_colors[0]
                accent_hex = sampled_banner_colors[1] if len(sampled_banner_colors) >= 2 else primary_hex
            bottom_bar_hex = primary_hex

            # Use native master layouts only when the source presentation is already 16:9 widescreen and doesn't rely on our 16:9 composited banner
            use_native_master = bool(slide_w >= 12.5 and not bottom_silhouette_url)
        except Exception as exc:
            raise ValueError(f"Invalid .pptx template file: {exc}") from exc

    elif ext == ".ppt":
        # Extract embedded PNG/JPEG streams from legacy OLE2 .ppt binary container
        extracted_imgs: List[Path] = []
        for idx_p, m in enumerate(re.finditer(b"\x89PNG\r\n\x1a\n", raw_bytes)):
            end = raw_bytes.find(b"IEND", m.start())
            if end != -1:
                try:
                    chunk = raw_bytes[m.start() : end + 8]
                    im = Image.open(io.BytesIO(chunk))
                    p_out = OVERLAYS_DIR / f"{template_id}_ppt_{idx_p}.png"
                    im.save(p_out)
                    extracted_imgs.append(p_out)
                except Exception:
                    pass
        if extracted_imgs:
            primary_hex = _extract_dominant_color_hex(extracted_imgs[0], "#003F87")
            bottom_bar_hex = primary_hex
            corner_logo_url = f"/assets/templates/overlays/{extracted_imgs[0].name}"
        out_pptx = CUSTOM_TEMPLATES_DIR / f"{template_id}.pptx"
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        prs.slides.add_slide(prs.slide_layouts[6])
        prs.save(str(out_pptx))
        pptx_rel_path = f"assets/templates/custom/{template_id}.pptx"

    elif ext in (".png", ".jpg", ".jpeg", ".webp"):
        img_out = OVERLAYS_DIR / f"{template_id}{ext}"
        img_out.write_bytes(raw_bytes)
        primary_hex = _extract_dominant_color_hex(img_out, "#003F87")
        bottom_bar_hex = primary_hex
        with Image.open(img_out) as im:
            if im.width >= im.height * 1.45 and im.height >= 400:
                watermark_url = f"/assets/templates/overlays/{img_out.name}"
                bottom_bar_hex = ""
            else:
                corner_logo_url = f"/assets/templates/overlays/{img_out.name}"
        out_pptx = CUSTOM_TEMPLATES_DIR / f"{template_id}.pptx"
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        prs.slides.add_slide(prs.slide_layouts[6])
        prs.save(str(out_pptx))
        pptx_rel_path = f"assets/templates/custom/{template_id}.pptx"
    else:
        raise ValueError(f"Unsupported template file format '{ext}'. Upload .pptx, .ppt, .png, .jpg, or .webp.")

    profile = TemplateProfile(
        template_id=template_id,
        name=display_name,
        category="Custom Uploaded Template",
        description=f"Custom template imported from {original_filename} with automatic AABB safe-zone adaptation.",
        is_builtin=False,
        pptx_path=pptx_rel_path,
        content_layout_index=content_layout_idx,
        use_native_master_layouts=use_native_master,
        primary_hex=primary_hex,
        accent_hex=accent_hex,
        card_bg_hex=_derive_soft_card_bg_hex(primary_hex),
        canvas_watermark_url=watermark_url,
        bottom_bar_hex=bottom_bar_hex,
        bottom_accent_hex=accent_hex,
        bottom_silhouette_url=bottom_silhouette_url,
        bottom_silhouette_dark_url=bottom_silhouette_url,
        corner_logo_url=corner_logo_url,
        corner_logo_dark_url=corner_logo_url,
        top_banner_url=top_banner_url,
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=header_top_in,
            header_height_in=0.80,
            header_banner_height_in=header_banner_height_in,
            content_top_min_in=content_top_min_in,
            content_bottom_max_in=max(5.80, min(6.95, float(bottom_safe_in))),
            safety_bar_height_in=0.68,
            footer_left_in=footer_left_in,
            footer_top_in=footer_top_in,
            footer_max_width_in=footer_max_width_in,
            suppress_native_footer=True,
        ),
    )
    catalog = [p for p in load_template_catalog() if p.template_id != template_id]
    catalog.append(profile)
    save_template_catalog(catalog)
    return profile


def ingest_template_from_url(
    url: str,
    custom_name: Optional[str] = None,
    bottom_safe_in: float = 6.55,
) -> TemplateProfile:
    """Downloads a `.pptx`, `.ppt`, or background image template from an HTTP/HTTPS URL and registers it."""
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Template URL must be a valid http:// or https:// URL.")
    host = parsed.hostname or ""
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254") or host.startswith("10.") or host.startswith("192.168."):
        raise ValueError("Internal or loopback network URLs are not permitted.")

    req = urllib.request.Request(url, headers={"User-Agent": "ScoutsBSAMeritBadgeWorkbench/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw_bytes = resp.read(25 * 1024 * 1024)  # 25 MB safety cap
    fname = Path(parsed.path).name or "remote_template.pptx"
    if not Path(fname).suffix:
        fname += ".pptx"
    return ingest_custom_template_bytes(raw_bytes, fname, custom_name=custom_name, bottom_safe_in=bottom_safe_in)


def _strip_slide_placeholders(slide: Any) -> None:
    """Removes empty inherited layout placeholders ('Click to add title/text') so they never overlap AABB cards."""
    try:
        for shp in list(slide.placeholders):
            sp = shp._element
            if sp is not None and sp.getparent() is not None:
                sp.getparent().remove(sp)
    except Exception:
        pass


def decorate_slide_with_template_chrome(
    slide: Any,
    profile: TemplateProfile,
    is_cover: bool = False,
    tier: str = "BEAUTIFIED",
) -> None:
    """Applies template watermark, top header strip, bottom silhouette/bar, and corner logo shapes onto a slide when not already in the native layout."""
    if profile.template_id == "default_workbench":
        return

    norm_tier = normalize_visual_theme(tier)

    # 1. Cover hero background or subtle content-slide watermark
    if is_cover and profile.cover_bg_url and not profile.use_native_master_layouts:
        cov_disk = REPO_ROOT / profile.cover_bg_url.lstrip("/")
        if cov_disk.exists():
            try:
                pic = slide.shapes.add_picture(str(cov_disk), Inches(0.0), Inches(0.0), width=Inches(13.333), height=Inches(7.5))
                pic.name = "TemplateChrome_CoverBg"
            except Exception:
                pass
    elif profile.canvas_watermark_url and norm_tier != "STUDIO" and not is_cover:
        wm_disk = REPO_ROOT / profile.canvas_watermark_url.lstrip("/")
        if wm_disk.exists():
            try:
                pic = slide.shapes.add_picture(str(wm_disk), Inches(0.0), Inches(0.0), width=Inches(13.333), height=Inches(7.5))
                pic.name = "TemplateChrome_Watermark"
            except Exception:
                pass

    # 1b. Top header strip / crest banner (e.g. Guide to Advancement green header strip or Fleur-de-Lis crest)
    if profile.top_banner_url and not profile.use_native_master_layouts:
        top_disk = REPO_ROOT / profile.top_banner_url.lstrip("/")
        if top_disk.exists():
            try:
                with Image.open(top_disk) as tim:
                    t_aspect = tim.width / max(1, tim.height)
                if t_aspect >= 8.0:
                    th = max(0.24, float(profile.safe_bounds.header_banner_height_in or 0.27))
                    pic = slide.shapes.add_picture(str(top_disk), Inches(0.0), Inches(0.0), width=Inches(13.333), height=Inches(th))
                    pic.name = "TemplateChrome_TopStrip"
            except Exception:
                pass

    # If the template's native slide layout already carries the bottom bar & corner logo (e.g. America 250 / Forest Sunrise),
    # we don't duplicate them unless we're on a non-native layout.
    if profile.use_native_master_layouts:
        return

    # 2. Bottom horizon silhouette or composited custom footer banner (e.g., BSA Outdoor Adventure or Guide to Advancement)
    sil_url = profile.bottom_silhouette_dark_url if norm_tier == "STUDIO" else profile.bottom_silhouette_url
    if sil_url:
        sil_disk = REPO_ROOT / sil_url.lstrip("/")
        if sil_disk.exists():
            try:
                sil_h = 0.56 if "_footer_banner" in sil_disk.name else 0.76
                pic = slide.shapes.add_picture(str(sil_disk), Inches(0.0), Inches(7.50 - sil_h), width=Inches(13.333), height=Inches(sil_h))
                pic.name = "TemplateChrome_Silhouette"
            except Exception:
                pass
    elif profile.bottom_bar_hex and not is_cover:
        bar_rgb = hex_to_rgb(profile.bottom_bar_hex, (7, 86, 151))
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.0), Inches(6.96), Inches(10.15), Inches(0.36))
        bar.name = "TemplateChrome_BottomBar"
        bar.fill.solid()
        bar.fill.fore_color.rgb = RGBColor(*bar_rgb)
        bar.line.color.rgb = RGBColor(*bar_rgb)
        if profile.bottom_accent_hex:
            acc_rgb = hex_to_rgb(profile.bottom_accent_hex, (212, 175, 55))
            stripe = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.0), Inches(6.90), Inches(10.15), Inches(0.06))
            stripe.name = "TemplateChrome_AccentStripe"
            stripe.fill.solid()
            stripe.fill.fore_color.rgb = RGBColor(*acc_rgb)
            stripe.line.color.rgb = RGBColor(*acc_rgb)

    # 3. Bottom-right corner logo
    logo_url = profile.corner_logo_dark_url if norm_tier == "STUDIO" else profile.corner_logo_url
    if logo_url and not is_cover:
        logo_disk = REPO_ROOT / logo_url.lstrip("/")
        if logo_disk.exists():
            try:
                with Image.open(logo_disk) as im:
                    aspect = im.width / max(1, im.height)
                if aspect >= 2.2:
                    lw = 2.65
                    lh = round(lw / aspect, 3)
                    lx = 13.05 - lw
                    ly = 7.36 - lh if not sil_url else 6.56 - lh
                else:
                    lh = 0.68
                    lw = round(lh * aspect, 3)
                    lx = 12.95 - lw
                    ly = 6.68
                pic = slide.shapes.add_picture(str(logo_disk), Inches(lx), Inches(ly), width=Inches(lw))
                pic.name = "TemplateChrome_CornerLogo"
            except Exception:
                pass


def create_presentation_from_template(
    template_id: Optional[str] = None,
) -> Tuple[Presentation, Callable[[bool, str], Any], SafeCanvasBounds, TemplateProfile]:
    """Instantiates a `Presentation` backed by `template_id` (Option C Hybrid).

    Returns:
      - `prs`: `Presentation` object (13.333" x 7.50")
      - `add_slide_fn(is_cover: bool, tier: str) -> Slide`: adds a slide using the template's layout,
        strips ghost placeholders, and applies template chrome.
      - `safe_bounds`: `SafeCanvasBounds` for AABB card/visual placement.
      - `profile`: `TemplateProfile` metadata.
    """
    profile = get_template_profile(template_id)
    prs: Optional[Presentation] = None

    if profile.pptx_path and profile.use_native_master_layouts:
        abs_pptx = REPO_ROOT / profile.pptx_path if not Path(profile.pptx_path).is_absolute() else Path(profile.pptx_path)
        if abs_pptx.exists():
            try:
                prs = Presentation(str(abs_pptx))
                # Remove sample slides from the loaded template while preserving Slide Masters & Layouts
                xml_slides = prs.slides._sldIdLst
                for sldId in list(xml_slides):
                    rId = sldId.rId
                    prs.part.drop_rel(rId)
                    xml_slides.remove(sldId)
            except Exception:
                prs = None

    if prs is None:
        prs = Presentation()

    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    layouts = list(prs.slide_layouts)
    content_idx = min(max(0, profile.content_layout_index), len(layouts) - 1)
    blank_layout = layouts[content_idx]

    def _add_slide(is_cover: bool = False, tier: str = "BEAUTIFIED") -> Any:
        slide = prs.slides.add_slide(blank_layout)
        _strip_slide_placeholders(slide)
        decorate_slide_with_template_chrome(slide, profile, is_cover=is_cover, tier=tier)
        return slide

    return prs, _add_slide, profile.safe_bounds, profile
