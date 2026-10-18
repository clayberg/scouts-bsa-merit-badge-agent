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
    content_top_min_in: float = Field(1.15, description="Minimum top coordinate for body cards in inches.")
    content_bottom_max_in: float = Field(
        6.95,
        description="Maximum bottom coordinate for body cards/visuals in inches (clamped to ~6.52\" when template has footer bar/logo).",
    )
    safety_bar_height_in: float = Field(0.72, description="Height of safety/callout bar when present.")
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


BUILTIN_TEMPLATES: List[TemplateProfile] = [
    TemplateProfile(
        template_id="default_workbench",
        name="Workbench Classic (Full Canvas)",
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
        name="Scouting America | America 250™",
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
        name="Scouting America Forest Sunrise",
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
        name="Scouting America Topographic Contour",
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
        name="Scouting America High Adventure Action",
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
        name="Classic Outdoor Adventure Silhouette",
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
            footer_top_in=6.60,
            footer_max_width_in=9.20,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="classic_fleur_crimson_crest",
        name="Eagle Court of Honor & Fleur-de-Lis Crest",
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
        name="Summer Camp & Wood Badge Pine Crest",
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
    return True


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
    bottom_bar_hex = "#003F87"
    use_native_master = False
    pptx_rel_path: Optional[str] = None
    content_layout_idx = 6

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
                media_files = [n for n in z.namelist() if n.startswith("ppt/media/") and n.lower().endswith((".png", ".jpg", ".jpeg"))]
                for idx_m, mname in enumerate(media_files[:3]):
                    m_ext = Path(mname).suffix.lower()
                    saved_m = OVERLAYS_DIR / f"{template_id}_media_{idx_m}{m_ext}"
                    saved_m.write_bytes(z.read(mname))
                    with Image.open(saved_m) as im:
                        if im.width >= 1000 and im.height >= 550 and not watermark_url:
                            watermark_url = f"/assets/templates/overlays/{saved_m.name}"
                        elif im.width >= 120 and not corner_logo_url:
                            corner_logo_url = f"/assets/templates/overlays/{saved_m.name}"
            prs = Presentation(str(out_pptx))
            layouts = list(prs.slide_layouts)
            for idx_l, lay in enumerate(layouts):
                if "blank" in (lay.name or "").lower():
                    content_layout_idx = idx_l
                    break
            use_native_master = True
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
        card_bg_hex="#F0F7FF",
        canvas_watermark_url=watermark_url,
        bottom_bar_hex=bottom_bar_hex,
        bottom_accent_hex=accent_hex,
        corner_logo_url=corner_logo_url,
        corner_logo_dark_url=corner_logo_url,
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=max(5.80, min(6.95, float(bottom_safe_in))),
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.50,
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
    """Applies template watermark, bottom silhouette/bar, and corner logo shapes onto a slide when not already in the native layout."""
    if profile.template_id == "default_workbench":
        return

    # 1. Subtle watermark (e.g. Topographic Contour lines) on non-dark slides if present
    norm_tier = str(tier or "BEAUTIFIED").upper()
    if profile.canvas_watermark_url and norm_tier != "STUDIO" and not is_cover:
        wm_disk = REPO_ROOT / profile.canvas_watermark_url.lstrip("/")
        if wm_disk.exists():
            try:
                pic = slide.shapes.add_picture(str(wm_disk), Inches(0.0), Inches(0.0), width=Inches(13.333), height=Inches(7.5))
                pic.name = "TemplateChrome_Watermark"
            except Exception:
                pass

    # If the template's native slide layout already carries the bottom bar & corner logo (e.g. America 250 / Forest Sunrise),
    # we don't duplicate them unless we're on a non-native layout.
    if profile.use_native_master_layouts:
        return

    # 2. Bottom horizon silhouette (e.g., Classic Outdoor Adventure Silhouette)
    sil_url = profile.bottom_silhouette_dark_url if norm_tier == "STUDIO" else profile.bottom_silhouette_url
    if sil_url:
        sil_disk = REPO_ROOT / sil_url.lstrip("/")
        if sil_disk.exists():
            try:
                pic = slide.shapes.add_picture(str(sil_disk), Inches(0.0), Inches(6.74), width=Inches(13.333), height=Inches(0.76))
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
