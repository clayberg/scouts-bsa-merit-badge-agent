"""PowerPoint Template & Custom Slide Theme Engine (Option C Hybrid Template Studio).

Supports:
1. Curated built-in library of 17 council-neutral Scouting America & BSA templates across 7 style families.
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

from src.tools.asset_hydrator import hydrate_single_asset_on_demand

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = REPO_ROOT / "assets" / "templates"
OVERLAYS_DIR = TEMPLATES_DIR / "overlays"
PREVIEWS_DIR = TEMPLATES_DIR / "previews"
CUSTOM_TEMPLATES_DIR = TEMPLATES_DIR / "custom"
CATALOG_JSON_PATH = TEMPLATES_DIR / "catalog.json"
CUSTOM_REGISTRY_JSON_PATH = CUSTOM_TEMPLATES_DIR / "custom_registry.json"


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
    family_id: str = Field("custom_uploaded", description="Style family identifier for grouping color/edition variants.")
    family_name: str = Field("Custom Uploaded Templates", description="Human-readable style family title.")
    variant_label: str = Field("Default", description="Short color or edition variant label (e.g. 'Green', 'Blue', 'Red', 'Tan').")
    variant_swatch_hex: str = Field("#003F87", description="Hex color for the variant swatch pill in UI selectors.")
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
    default_text_container_style: str = Field(
        "CLEAN_OPEN",
        description="Default text container style: CLEAN_OPEN, LEFT_ACCENT_LINE, or BOXED_CARDS.",
    )
    default_image_frame_style: str = Field(
        "FRAMELESS_CLEAN",
        description="Default image frame style: FRAMELESS_CLEAN, SOFT_SHADOW, or FRAMED_CARD.",
    )
    default_header_chrome_style: str = Field(
        "MINIMAL_ACCENT",
        description="Default header chrome style: MINIMAL_ACCENT, COMPACT_SINGLE_LINE, or FULL_BANNER.",
    )
    safe_bounds: SafeCanvasBounds = Field(default_factory=SafeCanvasBounds)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the TemplateProfile to a plain dictionary including default style fields."""
        return self.model_dump()


DEFAULT_TEMPLATE_ID = "default_workbench"
LEGACY_WORKBENCH_TEMPLATE_ID = "default_workbench"
DEFAULT_FACTORY_TEMPLATE_ID = "bsa_scouting_america"

VALID_LAYOUT_STYLE_PRESETS = ("AUTO_TEMPLATE", "CLEAN_OPEN", "LEFT_ACCENT_LINE", "BOXED_CARDS")
VALID_TEXT_CONTAINER_STYLES = ("AUTO", "CLEAN_OPEN", "LEFT_ACCENT_LINE", "BOXED_CARDS")
VALID_IMAGE_FRAME_STYLES = ("AUTO", "FRAMELESS_CLEAN", "SOFT_SHADOW", "FRAMED_CARD")
VALID_HEADER_CHROME_STYLES = ("AUTO", "MINIMAL_ACCENT", "COMPACT_SINGLE_LINE", "FULL_BANNER")
VALID_TYPOGRAPHY_SCALES = ("COMFORTABLE", "LARGE_PROJECTOR", "COMPACT")
VALID_SAFETY_BANNER_MODES = ("ACUTE_HAZARDS_ONLY", "COMPACT_ACCENT", "ALL_WARNINGS")


class DeckStyleConfig(BaseModel):
    """Global and per-deck styling configuration for layout presets and granular visual overrides."""

    layout_style_preset: str = Field(
        "AUTO_TEMPLATE",
        description="High-level layout style preset: AUTO_TEMPLATE, CLEAN_OPEN, LEFT_ACCENT_LINE, or BOXED_CARDS.",
    )
    text_container_style: str = Field(
        "AUTO",
        description="Granular text container style override: AUTO, CLEAN_OPEN, LEFT_ACCENT_LINE, or BOXED_CARDS.",
    )
    image_frame_style: str = Field(
        "AUTO",
        description="Granular image frame style override: AUTO, FRAMELESS_CLEAN, SOFT_SHADOW, or FRAMED_CARD.",
    )
    header_chrome_style: str = Field(
        "AUTO",
        description="Granular header chrome style override: AUTO, MINIMAL_ACCENT, COMPACT_SINGLE_LINE, or FULL_BANNER.",
    )
    typography_scale: str = Field(
        "COMFORTABLE",
        description="Typography density scale: COMFORTABLE (0.0pt), LARGE_PROJECTOR (+1.5pt), or COMPACT (-1.0pt).",
    )
    safety_banner_mode: str = Field(
        "ACUTE_HAZARDS_ONLY",
        description="Safety callout banner behavior: ACUTE_HAZARDS_ONLY, COMPACT_ACCENT, or ALL_WARNINGS.",
    )
    match_template_palette: bool = Field(
        True,
        description="When True, slide accent colors automatically harmonize with the active template palette.",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the DeckStyleConfig to a plain dictionary."""
        return self.model_dump()


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
    # 0. Minimal Full-Canvas Default
    TemplateProfile(
        template_id="default_workbench",
        name="Workbench Classic",
        category="Workbench Default",
        family_id="workbench_default",
        family_name="Workbench Default",
        variant_label="Classic",
        variant_swatch_hex="#003F87",
        description="Full-bleed 16:9 instructional canvas maximizing vertical card space (6.95\" content height) with Scout Navy & Gold accents.",
        is_builtin=True,
        pptx_path=None,
        use_native_master_layouts=False,
        primary_hex="#003F87",
        accent_hex="#D4AF37",
        card_bg_hex="#EFF6FF",
        default_text_container_style="BOXED_CARDS",
        default_image_frame_style="FRAMELESS_CLEAN",
        default_header_chrome_style="MINIMAL_ACCENT",
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
    # 1. Brushed Banner Series (BSA Scouting America: Green, Blue, Red)
    TemplateProfile(
        template_id="bsa_scouting_america",
        name="BSA Scouting America (Green)",
        category="Scouting America Official",
        family_id="brushed_banner",
        family_name="1. Brushed Banner Series",
        variant_label="Green",
        variant_swatch_hex="#5A6F43",
        description="Official Scouting America brushed forest-green widescreen template featuring a textured pine-green header rule, full-width olive-green footer banner, and the white Scouting America™ fleur-de-lis lockup.",
        is_builtin=True,
        pptx_path="assets/templates/bsa_scouting_america.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=False,
        primary_hex="#5A6F43",
        accent_hex="#435835",
        card_bg_hex="#F2F3F0",
        bottom_bar_hex="#5A6F43",
        bottom_accent_hex="#435835",
        bottom_silhouette_url="/assets/templates/overlays/bsa_scouting_america_footer_banner.png",
        bottom_silhouette_dark_url="/assets/templates/overlays/bsa_scouting_america_footer_banner.png",
        top_banner_url="/assets/templates/overlays/bsa_scouting_america_header_strip.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.33,
            header_height_in=0.80,
            header_banner_height_in=0.27,
            content_top_min_in=1.15,
            content_bottom_max_in=6.88,
            safety_bar_height_in=0.68,
            footer_left_in=3.49,
            footer_top_in=7.05,
            footer_max_width_in=9.24,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="bsa_scouting_america_blue",
        name="BSA Scouting America (Blue)",
        category="Scouting America Official",
        family_id="brushed_banner",
        family_name="1. Brushed Banner Series",
        variant_label="Blue",
        variant_swatch_hex="#075697",
        description="Official Scouting America brushed Scout-Blue widescreen template featuring a textured navy header strip, full-width brushed blue footer banner, and the white Scouting America™ fleur-de-lis lockup.",
        is_builtin=True,
        pptx_path="assets/templates/bsa_scouting_america_blue.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=False,
        primary_hex="#075697",
        accent_hex="#003F87",
        card_bg_hex="#F0F7FF",
        bottom_bar_hex="#075697",
        bottom_accent_hex="#003F87",
        bottom_silhouette_url="/assets/templates/overlays/bsa_scouting_america_blue_footer_banner.png",
        bottom_silhouette_dark_url="/assets/templates/overlays/bsa_scouting_america_blue_footer_banner.png",
        top_banner_url="/assets/templates/overlays/bsa_scouting_america_blue_header_strip.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.33,
            header_height_in=0.80,
            header_banner_height_in=0.27,
            content_top_min_in=1.15,
            content_bottom_max_in=6.88,
            safety_bar_height_in=0.68,
            footer_left_in=3.49,
            footer_top_in=7.05,
            footer_max_width_in=9.24,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="bsa_scouting_america_red",
        name="BSA Scouting America (Red)",
        category="Scouting America Official",
        family_id="brushed_banner",
        family_name="1. Brushed Banner Series",
        variant_label="Red",
        variant_swatch_hex="#8B0000",
        description="Official Scouting America brushed Eagle-Crimson widescreen template featuring a textured burgundy header strip, full-width brushed crimson footer banner, and the white Scouting America™ fleur-de-lis lockup.",
        is_builtin=True,
        pptx_path="assets/templates/bsa_scouting_america_red.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=False,
        primary_hex="#8B0000",
        accent_hex="#5C0000",
        card_bg_hex="#FFF5F5",
        bottom_bar_hex="#8B0000",
        bottom_accent_hex="#5C0000",
        bottom_silhouette_url="/assets/templates/overlays/bsa_scouting_america_red_footer_banner.png",
        bottom_silhouette_dark_url="/assets/templates/overlays/bsa_scouting_america_red_footer_banner.png",
        top_banner_url="/assets/templates/overlays/bsa_scouting_america_red_header_strip.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.33,
            header_height_in=0.80,
            header_banner_height_in=0.27,
            content_top_min_in=1.15,
            content_bottom_max_in=6.88,
            safety_bar_height_in=0.68,
            footer_left_in=3.49,
            footer_top_in=7.05,
            footer_max_width_in=9.24,
            suppress_native_footer=True,
        ),
    ),
    # 2. Horizon Silhouette Series (BSA Outdoor Adventure: Blue, Green, Red)
    TemplateProfile(
        template_id="classic_outdoor_silhouette_navy",
        name="BSA Outdoor Adventure (Blue)",
        category="Heritage & High Adventure",
        family_id="outdoor_silhouette",
        family_name="2. Horizon Silhouette Series",
        variant_label="Blue",
        variant_swatch_hex="#003F87",
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
            content_bottom_max_in=6.82,
            safety_bar_height_in=0.68,
            footer_top_in=7.08,
            footer_max_width_in=12.133,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="classic_outdoor_silhouette_green",
        name="BSA Outdoor Adventure (Green)",
        category="Heritage & High Adventure",
        family_id="outdoor_silhouette",
        family_name="2. Horizon Silhouette Series",
        variant_label="Green",
        variant_swatch_hex="#2E4600",
        description="Backcountry Pine horizon silhouette template featuring zip-lining, canoe portage, mountain biking, and backpacking in deep forest green with Gold accents.",
        is_builtin=True,
        pptx_path="assets/templates/classic_outdoor_silhouette_green.pptx",
        content_layout_index=6,
        cover_layout_index=6,
        use_native_master_layouts=False,
        primary_hex="#2E4600",
        accent_hex="#D4AF37",
        card_bg_hex="#F1F8E9",
        bottom_silhouette_url="/assets/templates/overlays/classic_silhouette_green.png",
        bottom_silhouette_dark_url="/assets/templates/overlays/classic_silhouette_white.png",
        corner_logo_url="",
        corner_logo_dark_url="",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.78,
            content_top_min_in=1.10,
            content_bottom_max_in=6.82,
            safety_bar_height_in=0.68,
            footer_top_in=7.08,
            footer_max_width_in=12.133,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="classic_outdoor_silhouette_red",
        name="BSA Outdoor Adventure (Red)",
        category="Heritage & High Adventure",
        family_id="outdoor_silhouette",
        family_name="2. Horizon Silhouette Series",
        variant_label="Red",
        variant_swatch_hex="#8B0000",
        description="High-Adventure Canyon Crimson horizon silhouette template featuring zip-lining, canoe portage, mountain biking, and backpacking in deep crimson with Gold accents.",
        is_builtin=True,
        pptx_path="assets/templates/classic_outdoor_silhouette_red.pptx",
        content_layout_index=6,
        cover_layout_index=6,
        use_native_master_layouts=False,
        primary_hex="#8B0000",
        accent_hex="#D4AF37",
        card_bg_hex="#FFF5F5",
        bottom_silhouette_url="/assets/templates/overlays/classic_silhouette_red.png",
        bottom_silhouette_dark_url="/assets/templates/overlays/classic_silhouette_white.png",
        corner_logo_url="",
        corner_logo_dark_url="",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.78,
            content_top_min_in=1.10,
            content_bottom_max_in=6.82,
            safety_bar_height_in=0.68,
            footer_top_in=7.08,
            footer_max_width_in=12.133,
            suppress_native_footer=True,
        ),
    ),
    # 3. Forest Sunrise & Camp Series (BSA Forest Sunrise: Blue, Green, Red)
    TemplateProfile(
        template_id="scouting_america_forest_sunrise",
        name="BSA Forest Sunrise (Blue)",
        category="Scouting America Official",
        family_id="forest_sunrise",
        family_name="3. Forest Sunrise & Camp Series",
        variant_label="Blue",
        variant_swatch_hex="#075697",
        description="National Scouting America widescreen template with a sunlit pine meadow cover slide, #075697 Scout Blue bottom branding bar, and official Scouting America™ horizontal lockup.",
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
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.40,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="wilderness_camp_timber",
        name="BSA Forest Sunrise (Green)",
        category="Scouting America Official",
        family_id="forest_sunrise",
        family_name="3. Forest Sunrise & Camp Series",
        variant_label="Green",
        variant_swatch_hex="#2E4600",
        description="Outdoor summer camp and Wood Badge timber heritage template with sunlit pine meadow cover slide, #2E4600 Timber Green bottom bar, Gold stripe, and Scouting America™ lockup.",
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
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.50,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="scouting_america_forest_sunrise_red",
        name="BSA Forest Sunrise (Red)",
        category="Scouting America Official",
        family_id="forest_sunrise",
        family_name="3. Forest Sunrise & Camp Series",
        variant_label="Red",
        variant_swatch_hex="#8B0000",
        description="Eagle-Crimson edition of the Forest Sunrise template featuring the sunlit pine meadow cover slide, #8B0000 Crimson bottom branding bar, Gold accent stripe, and Scouting America™ horizontal lockup.",
        is_builtin=True,
        pptx_path="assets/templates/scouting_america_forest_sunrise_red.pptx",
        content_layout_index=6,
        cover_layout_index=6,
        use_native_master_layouts=False,
        primary_hex="#8B0000",
        accent_hex="#D4AF37",
        card_bg_hex="#FFF5F5",
        cover_bg_url="/assets/templates/overlays/forest_sunrise_cover.jpg",
        bottom_bar_hex="#8B0000",
        bottom_accent_hex="#D4AF37",
        corner_logo_url="/assets/templates/overlays/scouting_america_horiz_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_america_horiz_white.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.50,
            suppress_native_footer=True,
        ),
    ),
    # 4. Topographic Contour Series (BSA Topographic: Blue, Green, Tan)
    TemplateProfile(
        template_id="scouting_america_topographic",
        name="BSA Topographic (Blue)",
        category="Scouting America Official",
        family_id="topographic",
        family_name="4. Topographic Contour Series",
        variant_label="Blue",
        variant_swatch_hex="#003F87",
        description="Modern topographic contour-map watermark template in Scout Navy with subtle backcountry elevation lines, airy instructional whitespace, and the national Scouting America™ lockup.",
        is_builtin=True,
        pptx_path="assets/templates/scouting_america_topographic.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=False,
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
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.50,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="scouting_america_topographic_green",
        name="BSA Topographic (Green)",
        category="Scouting America Official",
        family_id="topographic",
        family_name="4. Topographic Contour Series",
        variant_label="Green",
        variant_swatch_hex="#2E4600",
        description="Forest-Pine topographic contour-map watermark template with subtle green elevation lines, #2E4600 bottom branding bar, sage accent stripe, and Scouting America™ lockup.",
        is_builtin=True,
        pptx_path="assets/templates/scouting_america_topographic_green.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=False,
        primary_hex="#2E4600",
        accent_hex="#15803D",
        card_bg_hex="#F1F8E9",
        canvas_watermark_url="/assets/templates/overlays/topographic_contour_green_bg.png",
        bottom_bar_hex="#2E4600",
        bottom_accent_hex="#4ADE80",
        corner_logo_url="/assets/templates/overlays/scouting_america_horiz_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_america_horiz_white.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.50,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="scouting_america_topographic_tan",
        name="BSA Topographic (Tan)",
        category="Scouting America Official",
        family_id="topographic",
        family_name="4. Topographic Contour Series",
        variant_label="Tan",
        variant_swatch_hex="#78350F",
        description="USGS Cartographer Tan/Sepia topographic contour-map watermark template with warm elevation lines, #78350F field-tan bottom bar, Gold stripe, and Scouting America™ lockup.",
        is_builtin=True,
        pptx_path="assets/templates/scouting_america_topographic_tan.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=False,
        primary_hex="#78350F",
        accent_hex="#B45309",
        card_bg_hex="#FEFCE8",
        canvas_watermark_url="/assets/templates/overlays/topographic_contour_tan_bg.png",
        bottom_bar_hex="#78350F",
        bottom_accent_hex="#D4AF37",
        corner_logo_url="/assets/templates/overlays/scouting_america_horiz_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_america_horiz_white.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.50,
            suppress_native_footer=True,
        ),
    ),
    # 5. Fleur-de-Lis Crest Series (BSA Fleur-de-Lis Crest: Red, Blue)
    TemplateProfile(
        template_id="classic_fleur_crimson_crest",
        name="BSA Fleur-de-Lis Crest (Red)",
        category="Heritage & High Adventure",
        family_id="fleur_crest",
        family_name="5. Fleur-de-Lis Crest Series",
        variant_label="Red",
        variant_swatch_hex="#8B0000",
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
        top_banner_url="",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=11.20,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="classic_fleur_navy_crest",
        name="BSA Fleur-de-Lis Crest (Blue)",
        category="Heritage & High Adventure",
        family_id="fleur_crest",
        family_name="5. Fleur-de-Lis Crest Series",
        variant_label="Blue",
        variant_swatch_hex="#003F87",
        description="Scout Navy and Crimson Court of Honor instruction template featuring a #003F87 Navy footer bar, #CE1126 Crimson stripe, and the universal Scouting Fleur-de-Lis emblem.",
        is_builtin=True,
        pptx_path="assets/templates/classic_fleur_navy_crest.pptx",
        content_layout_index=6,
        cover_layout_index=6,
        use_native_master_layouts=False,
        primary_hex="#003F87",
        accent_hex="#CE1126",
        card_bg_hex="#EFF6FF",
        bottom_bar_hex="#003F87",
        bottom_accent_hex="#CE1126",
        corner_logo_url="/assets/templates/overlays/scouting_fleur_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_fleur_color.png",
        top_banner_url="",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=11.20,
            suppress_native_footer=True,
        ),
    ),
    # 6. Special & Action Editions (BSA America 250™, BSA High Adventure)
    TemplateProfile(
        template_id="scouting_america_250",
        name="BSA America 250™",
        category="Scouting America Official",
        family_id="special_editions",
        family_name="6. Special & Action Editions",
        variant_label="America 250™",
        variant_swatch_hex="#CE1126",
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
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=7.02,
            footer_max_width_in=9.80,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="scouting_america_high_adventure_rock",
        name="BSA High Adventure",
        category="Scouting America Official",
        family_id="special_editions",
        family_name="6. Special & Action Editions",
        variant_label="High Adventure",
        variant_swatch_hex="#EA580C",
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
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.50,
            suppress_native_footer=True,
        ),
    ),
    # 7. Specialty Program & Heritage Editions (6 New Built-In Templates -> 23 Built-In Total)
    TemplateProfile(
        template_id="stem_nova_blueprint",
        name="STEM Nova Engineering • Blueprint",
        category="Scouting America Official",
        family_id="stem_nova_series",
        family_name="9. STEM Nova & Specialty Programs",
        variant_label="Blueprint",
        variant_swatch_hex="#1E3A8A",
        description="STEM Nova engineering blueprint template in Cobalt (#1E3A8A), Circuit Teal (#0284C7), and Amber (#D97706) with a robotics & laboratory washed cover backdrop.",
        is_builtin=True,
        pptx_path="assets/templates/scouting_america_topographic.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=False,
        primary_hex="#1E3A8A",
        accent_hex="#0284C7",
        card_bg_hex="#EFF6FF",
        cover_bg_url="assets/templates/overlays/nano_base_stem_robotics_lab.jpg",
        canvas_watermark_url="/assets/templates/overlays/topographic_contour_bg.png",
        bottom_bar_hex="#1E3A8A",
        bottom_accent_hex="#D97706",
        corner_logo_url="/assets/templates/overlays/scouting_america_horiz_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_america_horiz_white.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.50,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="eagle_court_of_honor",
        name="Eagle Court of Honor • Navy & Silver",
        category="Heritage & High Adventure",
        family_id="eagle_court_series",
        family_name="10. Eagle Court of Honor & Ceremonial Series",
        variant_label="Navy & Silver",
        variant_swatch_hex="#0F172A",
        description="Formal Eagle Scout Court of Honor template in Royal Navy (#0F172A), Eagle Crimson (#DC2626), and Sterling Silver (#475569) with a Capitol civic heritage cover backdrop.",
        is_builtin=True,
        pptx_path="assets/templates/classic_fleur_navy_crest.pptx",
        content_layout_index=6,
        cover_layout_index=6,
        use_native_master_layouts=False,
        primary_hex="#0F172A",
        accent_hex="#DC2626",
        card_bg_hex="#F8FAFC",
        cover_bg_url="assets/templates/overlays/nano_base_citizenship_capitol_civic.jpg",
        bottom_bar_hex="#0F172A",
        bottom_accent_hex="#475569",
        corner_logo_url="/assets/templates/overlays/scouting_fleur_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_fleur_color.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=11.20,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="sea_scouts_maritime",
        name="Sea Scouts Maritime • Admiral Navy",
        category="Scouting America Official",
        family_id="sea_scouts_series",
        family_name="11. Sea Scouts & Venturing Series",
        variant_label="Admiral Navy",
        variant_swatch_hex="#0C4A6E",
        description="Sea Scouts maritime navigation and aquatics template in Dress Navy (#0C4A6E), Ocean Teal (#0D9488), and Brass (#B45309) with a coastal lighthouse waterfront cover backdrop.",
        is_builtin=True,
        pptx_path="assets/templates/bsa_scouting_america_blue.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=False,
        primary_hex="#0C4A6E",
        accent_hex="#0D9488",
        card_bg_hex="#F0FDFA",
        cover_bg_url="assets/templates/overlays/nano_base_aquatics_nautical.jpg",
        bottom_bar_hex="#0C4A6E",
        bottom_accent_hex="#B45309",
        corner_logo_url="/assets/templates/overlays/scouting_america_horiz_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_america_horiz_white.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.50,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="oa_ceremonial_lodge",
        name="Order of the Arrow • Lodge Sash",
        category="Heritage & High Adventure",
        family_id="oa_ceremonial_series",
        family_name="10. Eagle Court of Honor & Ceremonial Series",
        variant_label="Lodge Sash",
        variant_swatch_hex="#B91C1C",
        description="Order of the Arrow ceremonial lodge template in Ceremonial Pine (#1F2937), Sash Scarlet (#B91C1C), and Warm Gold (#B45309) with a pinewood campfire clearing cover backdrop.",
        is_builtin=True,
        pptx_path="assets/templates/classic_fleur_crimson_crest.pptx",
        content_layout_index=6,
        cover_layout_index=6,
        use_native_master_layouts=False,
        primary_hex="#1F2937",
        accent_hex="#B91C1C",
        card_bg_hex="#FEF2F2",
        cover_bg_url="assets/templates/overlays/nano_base_pinewood_campfire.jpg",
        bottom_bar_hex="#1F2937",
        bottom_accent_hex="#B45309",
        corner_logo_url="/assets/templates/overlays/scouting_fleur_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_fleur_color.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=11.20,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="venturing_alpine_emerald",
        name="Venturing High Adventure • Alpine Emerald",
        category="Heritage & High Adventure",
        family_id="venturing_series",
        family_name="11. Sea Scouts & Venturing Series",
        variant_label="Alpine Emerald",
        variant_swatch_hex="#065F46",
        description="Venturing high-adventure backcountry template in Venturing Green (#065F46), Summit Slate (#334155), and Gold (#D97706) with an alpine summit ridge cover backdrop.",
        is_builtin=True,
        pptx_path="assets/templates/scouting_america_topographic_green.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=False,
        primary_hex="#065F46",
        accent_hex="#334155",
        card_bg_hex="#ECFDF5",
        cover_bg_url="assets/templates/overlays/nano_base_high_adventure_summit.jpg",
        canvas_watermark_url="/assets/templates/overlays/topographic_contour_green_bg.png",
        bottom_bar_hex="#065F46",
        bottom_accent_hex="#D97706",
        corner_logo_url="/assets/templates/overlays/scouting_america_horiz_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_america_horiz_white.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=9.50,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="wood_badge_gilwell",
        name="Wood Badge Heritage • MacLaren Tartan",
        category="Heritage & High Adventure",
        family_id="wood_badge_series",
        family_name="12. Wood Badge Gilwell Heritage",
        variant_label="MacLaren Tartan",
        variant_swatch_hex="#14532D",
        description="Wood Badge Gilwell leadership heritage template in Gilwell Forest (#14532D), Tartan Crimson (#991B1B), and Buff (#92400E) with a pioneering timber tower cover backdrop.",
        is_builtin=True,
        pptx_path="assets/templates/wilderness_camp_timber.pptx",
        content_layout_index=6,
        cover_layout_index=6,
        use_native_master_layouts=False,
        primary_hex="#14532D",
        accent_hex="#991B1B",
        card_bg_hex="#FEFCE8",
        cover_bg_url="assets/templates/overlays/nano_base_pioneering_timber_tower.jpg",
        canvas_watermark_url="/assets/templates/overlays/topographic_contour_tan_bg.png",
        bottom_bar_hex="#14532D",
        bottom_accent_hex="#92400E",
        corner_logo_url="/assets/templates/overlays/scouting_fleur_color.png",
        corner_logo_dark_url="/assets/templates/overlays/scouting_fleur_color.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.18,
            header_height_in=0.80,
            content_top_min_in=1.12,
            content_bottom_max_in=6.86,
            safety_bar_height_in=0.68,
            footer_top_in=6.98,
            footer_max_width_in=11.20,
            suppress_native_footer=True,
        ),
    ),
]

BUILT_IN_TEMPLATES: List[TemplateProfile] = BUILTIN_TEMPLATES

# Optional Camp & Merit Badge College Customizations (Visible when 'Add DMBC & HVSC Customizations' is enabled in Admin Console)
DMBC_HVSC_TEMPLATES: List[TemplateProfile] = [
    TemplateProfile(
        template_id="camp_hidden_valley",
        name="Camp Hidden Valley (Green)",
        category="Camp & Merit Badge College",
        family_id="camp_hidden_valley_edition",
        family_name="7. Camp Hidden Valley (Griswold Scout Reservation)",
        variant_color="green",
        variant_label="Green",
        variant_swatch_hex="#1B4332",
        description="Version 1 (Green - Split Council Dock): Full-bleed washed Lake Eileen sunset dock cover backdrop with full-color Scouting America New Hampshire lower-left badge dock, White Mountains Pine (#1B4332) bar, and Sunset Gold (#D97706) trim.",
        is_builtin=True,
        pptx_path="assets/templates/scouting_america_forest_sunrise.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=False,
        primary_hex="#1B4332",
        accent_hex="#D97706",
        card_bg_hex="#F0FDF4",
        cover_bg_url="/assets/templates/overlays/hvsc_v1_cover_bg.jpg",
        canvas_watermark_url="/assets/templates/overlays/hvsc_v1_watermark.png",
        top_banner_url="/assets/templates/overlays/hvsc_v1_top_banner.png",
        bottom_silhouette_url="/assets/templates/overlays/hvsc_v1_footer_banner.png",
        bottom_silhouette_dark_url="/assets/templates/overlays/hvsc_v1_footer_banner_dark.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.22,
            header_height_in=0.80,
            header_banner_height_in=0.26,
            content_top_min_in=1.12,
            content_bottom_max_in=6.84,
            safety_bar_height_in=0.68,
            footer_left_in=3.49,
            footer_top_in=7.02,
            footer_max_width_in=9.24,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="camp_hidden_valley_v2",
        name="Camp Hidden Valley (Olive)",
        category="Camp & Merit Badge College",
        family_id="camp_hidden_valley_edition",
        family_name="7. Camp Hidden Valley (Griswold Scout Reservation)",
        variant_color="olive",
        variant_label="Olive",
        variant_swatch_hex="#2E4600",
        description="Version 2 (Olive - Brushed Pine & Reverse-White Council Lockup): Washed Lake Eileen sunset cover with topographic contours and a full-width brushed Woodland Pine (#2E4600) footer banner featuring a luminous reverse-white Scouting America New Hampshire lockup in the lower-left corner.",
        is_builtin=True,
        pptx_path="assets/templates/scouting_america_forest_sunrise.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=False,
        primary_hex="#2E4600",
        accent_hex="#F59E0B",
        card_bg_hex="#F7FEE7",
        cover_bg_url="/assets/templates/overlays/hvsc_v2_cover_bg.jpg",
        canvas_watermark_url="/assets/templates/overlays/hvsc_v2_watermark.png",
        top_banner_url="/assets/templates/overlays/hvsc_v2_top_banner.png",
        bottom_silhouette_url="/assets/templates/overlays/hvsc_v2_footer_banner.png",
        bottom_silhouette_dark_url="/assets/templates/overlays/hvsc_v2_footer_banner_dark.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.22,
            header_height_in=0.80,
            header_banner_height_in=0.26,
            content_top_min_in=1.12,
            content_bottom_max_in=6.84,
            safety_bar_height_in=0.68,
            footer_left_in=3.49,
            footer_top_in=7.02,
            footer_max_width_in=9.24,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="camp_hidden_valley_v3",
        name="Camp Hidden Valley (Blue)",
        category="Camp & Merit Badge College",
        family_id="camp_hidden_valley_edition",
        family_name="7. Camp Hidden Valley (Griswold Scout Reservation)",
        variant_color="blue",
        variant_label="Blue",
        variant_swatch_hex="#075697",
        description="Version 3 (Blue - Lake Eileen Waterfront Horizon): Double-rule framed Lake Eileen sunset cover with a scenic White Mountains pine-ridge silhouette footer in Lake Blue (#075697) and a rounded cream Scouting America New Hampshire emblem in the lower-left corner.",
        is_builtin=True,
        pptx_path="assets/templates/scouting_america_forest_sunrise.pptx",
        content_layout_index=6,
        cover_layout_index=0,
        use_native_master_layouts=False,
        primary_hex="#075697",
        accent_hex="#EA580C",
        card_bg_hex="#F0F9FF",
        cover_bg_url="/assets/templates/overlays/hvsc_v3_cover_bg.jpg",
        canvas_watermark_url="/assets/templates/overlays/hvsc_v3_watermark.png",
        top_banner_url="/assets/templates/overlays/hvsc_v3_top_banner.png",
        bottom_silhouette_url="/assets/templates/overlays/hvsc_v3_footer_banner.png",
        bottom_silhouette_dark_url="/assets/templates/overlays/hvsc_v3_footer_banner_dark.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.22,
            header_height_in=0.80,
            header_banner_height_in=0.26,
            content_top_min_in=1.12,
            content_bottom_max_in=6.80,
            safety_bar_height_in=0.68,
            footer_left_in=3.49,
            footer_top_in=7.02,
            footer_max_width_in=9.24,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="danvers_mbc",
        name="Danvers Merit Badge College (Crimson)",
        category="Camp & Merit Badge College",
        family_id="danvers_mbc_edition",
        family_name="8. Danvers Merit Badge College (Holten-Richmond MS)",
        variant_color="crimson",
        variant_label="Crimson",
        variant_swatch_hex="#8B0000",
        description="Version 1 (Crimson - Collegiate Split Council Dock): Full-bleed washed Holten-Richmond Middle School facade cover backdrop with a full-color Spirit of Adventure Council lower-left badge dock, Collegiate Crimson (#8B0000) bar, and Gold (#D4AF37) chevron trim.",
        is_builtin=True,
        pptx_path="assets/templates/classic_fleur_crimson_crest.pptx",
        content_layout_index=6,
        cover_layout_index=6,
        use_native_master_layouts=False,
        primary_hex="#8B0000",
        accent_hex="#D4AF37",
        card_bg_hex="#FEF2F2",
        cover_bg_url="/assets/templates/overlays/dmbc_v1_cover_bg.jpg",
        canvas_watermark_url="/assets/templates/overlays/dmbc_v1_watermark.png",
        top_banner_url="/assets/templates/overlays/dmbc_v1_top_banner.png",
        bottom_silhouette_url="/assets/templates/overlays/dmbc_v1_footer_banner.png",
        bottom_silhouette_dark_url="/assets/templates/overlays/dmbc_v1_footer_banner_dark.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.22,
            header_height_in=0.80,
            header_banner_height_in=0.26,
            content_top_min_in=1.12,
            content_bottom_max_in=6.84,
            safety_bar_height_in=0.68,
            footer_left_in=3.55,
            footer_top_in=7.02,
            footer_max_width_in=9.18,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="danvers_mbc_v2",
        name="Danvers Merit Badge College (Navy)",
        category="Camp & Merit Badge College",
        family_id="danvers_mbc_edition",
        family_name="8. Danvers Merit Badge College (Holten-Richmond MS)",
        variant_color="navy",
        variant_label="Navy",
        variant_swatch_hex="#003F87",
        description="Version 2 (Navy - Brushed Council Bar & Reverse-White Lockup): Framed washed Holten-Richmond MS cupola cover backdrop with a full-width brushed Scouting Navy (#003F87) footer banner and luminous reverse-white Spirit of Adventure Council lockup in the lower-left corner.",
        is_builtin=True,
        pptx_path="assets/templates/classic_fleur_crimson_crest.pptx",
        content_layout_index=6,
        cover_layout_index=6,
        use_native_master_layouts=False,
        primary_hex="#003F87",
        accent_hex="#CE1126",
        card_bg_hex="#EFF6FF",
        cover_bg_url="/assets/templates/overlays/dmbc_v2_cover_bg.jpg",
        canvas_watermark_url="/assets/templates/overlays/dmbc_v2_watermark.png",
        top_banner_url="/assets/templates/overlays/dmbc_v2_top_banner.png",
        bottom_silhouette_url="/assets/templates/overlays/dmbc_v2_footer_banner.png",
        bottom_silhouette_dark_url="/assets/templates/overlays/dmbc_v2_footer_banner_dark.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.22,
            header_height_in=0.80,
            header_banner_height_in=0.26,
            content_top_min_in=1.12,
            content_bottom_max_in=6.84,
            safety_bar_height_in=0.68,
            footer_left_in=3.55,
            footer_top_in=7.02,
            footer_max_width_in=9.18,
            suppress_native_footer=True,
        ),
    ),
    TemplateProfile(
        template_id="danvers_mbc_v3",
        name="Danvers Merit Badge College (Brick)",
        category="Camp & Merit Badge College",
        family_id="danvers_mbc_edition",
        family_name="8. Danvers Merit Badge College (Holten-Richmond MS)",
        variant_color="brown",
        variant_label="Brick",
        variant_swatch_hex="#7F1D1D",
        description="Version 3 (Brick & Patina - Georgian Cupola Heritage): Parchment-washed Holten-Richmond MS brick & cupola cover with Copper-Cupola Patina (#0F766E) trim and a rounded cream Spirit of Adventure Council crest in the lower-left corner.",
        is_builtin=True,
        pptx_path="assets/templates/classic_fleur_crimson_crest.pptx",
        content_layout_index=6,
        cover_layout_index=6,
        use_native_master_layouts=False,
        primary_hex="#7F1D1D",
        accent_hex="#0F766E",
        card_bg_hex="#FFFBEB",
        cover_bg_url="/assets/templates/overlays/dmbc_v3_cover_bg.jpg",
        canvas_watermark_url="/assets/templates/overlays/dmbc_v3_watermark.png",
        top_banner_url="/assets/templates/overlays/dmbc_v3_top_banner.png",
        bottom_silhouette_url="/assets/templates/overlays/dmbc_v3_footer_banner.png",
        bottom_silhouette_dark_url="/assets/templates/overlays/dmbc_v3_footer_banner_dark.png",
        safe_bounds=SafeCanvasBounds(
            left_in=0.60,
            right_in=12.733,
            header_top_in=0.22,
            header_height_in=0.80,
            header_banner_height_in=0.26,
            content_top_min_in=1.12,
            content_bottom_max_in=6.80,
            safety_bar_height_in=0.68,
            footer_left_in=3.55,
            footer_top_in=7.02,
            footer_max_width_in=9.18,
            suppress_native_footer=True,
        ),
    ),
]


def _ensure_dirs() -> None:
    for d in (TEMPLATES_DIR, OVERLAYS_DIR, PREVIEWS_DIR, CUSTOM_TEMPLATES_DIR):
        d.mkdir(parents=True, exist_ok=True)


_CATALOG_CACHE = None
_CATALOG_MTIME = 0.0

def load_template_catalog() -> List[TemplateProfile]:
    global _CATALOG_CACHE, _CATALOG_MTIME
    _ensure_dirs()
    by_id: Dict[str, TemplateProfile] = {t.template_id: t for t in [*BUILTIN_TEMPLATES, *DMBC_HVSC_TEMPLATES]}
    cat_mtime = CATALOG_JSON_PATH.stat().st_mtime_ns if CATALOG_JSON_PATH.exists() else 0
    reg_mtime = CUSTOM_REGISTRY_JSON_PATH.stat().st_mtime_ns if CUSTOM_REGISTRY_JSON_PATH.exists() else 0
    combined_mtime = cat_mtime + reg_mtime
    if CATALOG_JSON_PATH.exists() or CUSTOM_REGISTRY_JSON_PATH.exists():
        try:
            if _CATALOG_CACHE is not None and _CATALOG_MTIME == combined_mtime:
                return _CATALOG_CACHE

            for json_p in (CATALOG_JSON_PATH, CUSTOM_REGISTRY_JSON_PATH):
                if not json_p.exists():
                    continue
                raw = json.loads(json_p.read_text(encoding="utf-8"))
                items_list = raw.get("templates", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
                for item in items_list:
                    if isinstance(item, dict) and item.get("template_id"):
                        tid = str(item["template_id"])
                        if tid not in by_id:
                            prof = TemplateProfile(**item)
                            if prof.variant_label and prof.variant_label.startswith("Variant "):
                                cname = get_closest_color_name(prof.variant_swatch_hex or prof.primary_hex or "#003F87")
                                old_lbl = prof.variant_label
                                prof.variant_label = cname
                                prof.variant_color = cname.lower().replace(" ", "_")
                                if f"({old_lbl})" in (prof.name or ""):
                                    prof.name = prof.name.replace(f"({old_lbl})", f"({cname})")
                                if f"({old_lbl})" in (prof.description or ""):
                                    prof.description = prof.description.replace(f"({old_lbl})", f"({cname})")
                            by_id[tid] = prof

            _CATALOG_CACHE = list(by_id.values())
            _CATALOG_MTIME = combined_mtime
        except Exception:
            pass
    else:
        save_template_catalog(list(by_id.values()))
        _CATALOG_CACHE = list(by_id.values())
        _CATALOG_MTIME = 0.0

    return _CATALOG_CACHE if _CATALOG_CACHE is not None else list(by_id.values())


def save_template_catalog(profiles: List[TemplateProfile]) -> None:
    """Persists the full template catalog to `assets/templates/catalog.json` and custom templates to `custom_registry.json`."""
    global _CATALOG_CACHE, _CATALOG_MTIME
    _ensure_dirs()
    CATALOG_JSON_PATH.write_text(
        json.dumps([p.model_dump() for p in profiles], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    custom_only = [p.model_dump() for p in profiles if not p.is_builtin]
    CUSTOM_REGISTRY_JSON_PATH.write_text(
        json.dumps(custom_only, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _CATALOG_CACHE = list(profiles)
    cat_mtime = CATALOG_JSON_PATH.stat().st_mtime_ns if CATALOG_JSON_PATH.exists() else 0
    reg_mtime = CUSTOM_REGISTRY_JSON_PATH.stat().st_mtime_ns if CUSTOM_REGISTRY_JSON_PATH.exists() else 0
    _CATALOG_MTIME = cat_mtime + reg_mtime


def _resolve_and_hydrate_template_asset(rel_or_abs: str | Path) -> Path:
    """Resolves a template or backdrop path on disk, calling `hydrate_single_asset_on_demand` for `assets/...` paths."""
    if isinstance(rel_or_abs, Path):
        try:
            rel_str = rel_or_abs.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
        except Exception:
            rel_str = str(rel_or_abs).lstrip("/")
        disk_path = rel_or_abs
    else:
        rel_str = str(rel_or_abs or "").split("?")[0].strip().lstrip("/")
        disk_path = REPO_ROOT / rel_str
    if rel_str.startswith("assets/"):
        try:
            hydrate_single_asset_on_demand(rel_str, repo_root=REPO_ROOT)
        except Exception:
            pass
    return disk_path


def get_template_profile(
    template_id: Optional[str],
    badge_name: str = "",
    cover_backdrop_id: str = "AUTO_TEMPLATE",
) -> TemplateProfile:
    """Resolves a `TemplateProfile` by `template_id`, falling back to `default_workbench`."""
    norm = str(template_id or "default_workbench").strip() or "default_workbench"
    matched: Optional[TemplateProfile] = None
    for prof in load_template_catalog():
        if prof.template_id == norm:
            matched = prof
            break
    if matched is None:
        matched = BUILTIN_TEMPLATES[0]
    norm_bd = str(cover_backdrop_id or "AUTO_TEMPLATE").strip()
    if matched.is_builtin and matched.template_id != "default_workbench" and not matched.cover_bg_url and norm_bd.upper() in ("", "AUTO", "AUTO_TEMPLATE") and badge_name:
        cloned = matched.model_copy(deep=True)
        cloned.cover_bg_url = resolve_default_cover_backdrop_for_badge(badge_name, cloned.template_id)
        return cloned
    return matched


def resolve_effective_slide_style(
    template_profile: Any = None,
    deck_style: Optional[Any] = None,
    slide_spec: Optional[Any] = None,
    badge_name: str = "",
) -> Dict[str, Any]:
    """Resolves the effective slide layout & chrome styling with strict precedence:
    1. Per-slide override (`slide_spec.container_style_override`, `card_theme_style`, or `visual_theme` when set to a layout style).
    2. Granular `deck_style` field (`text_container_style`, `image_frame_style`, `header_chrome_style`) when not `"AUTO"`.
    3. `deck_style["layout_style_preset"]` (or `default_layout_style_preset`) when not `"AUTO_TEMPLATE"`.
    4. `TemplateProfile` defaults (`default_text_container_style`, `default_image_frame_style`, `default_header_chrome_style`).
    """
    # Resolve TemplateProfile
    if isinstance(template_profile, TemplateProfile):
        prof = template_profile
    elif isinstance(template_profile, dict) and template_profile.get("template_id"):
        prof = get_template_profile(str(template_profile.get("template_id")), badge_name=badge_name)
    elif isinstance(template_profile, str) and template_profile.strip():
        prof = get_template_profile(template_profile.strip(), badge_name=badge_name)
    else:
        slide_tpl = None
        if isinstance(slide_spec, dict):
            slide_tpl = slide_spec.get("template_id")
        elif slide_spec is not None:
            slide_tpl = getattr(slide_spec, "template_id", None)
        prof = get_template_profile(str(slide_tpl or "default_workbench"), badge_name=badge_name)

    # Normalize deck_style dict
    ds: Dict[str, Any] = {}
    if isinstance(deck_style, DeckStyleConfig):
        ds = deck_style.to_dict()
    elif isinstance(deck_style, dict):
        ds = dict(deck_style)
    elif slide_spec is not None:
        s_ds = slide_spec.get("deck_style") if isinstance(slide_spec, dict) else getattr(slide_spec, "deck_style", None)
        if isinstance(s_ds, dict):
            ds = dict(s_ds)

    raw_preset = str(
        ds.get("layout_style_preset")
        or ds.get("default_layout_style_preset")
        or "AUTO_TEMPLATE"
    ).strip().upper()
    if raw_preset not in VALID_LAYOUT_STYLE_PRESETS:
        raw_preset = "AUTO_TEMPLATE"

    # Step 4: Start from TemplateProfile defaults
    eff_text = str(getattr(prof, "default_text_container_style", "CLEAN_OPEN") or "CLEAN_OPEN").upper()
    eff_img = str(getattr(prof, "default_image_frame_style", "FRAMELESS_CLEAN") or "FRAMELESS_CLEAN").upper()
    eff_hdr = str(getattr(prof, "default_header_chrome_style", "MINIMAL_ACCENT") or "MINIMAL_ACCENT").upper()

    # Step 3: Apply layout_style_preset when not AUTO_TEMPLATE
    if raw_preset == "CLEAN_OPEN":
        eff_text = "CLEAN_OPEN"
        eff_img = "FRAMELESS_CLEAN"
        eff_hdr = "MINIMAL_ACCENT"
    elif raw_preset == "LEFT_ACCENT_LINE":
        eff_text = "LEFT_ACCENT_LINE"
        eff_img = "FRAMELESS_CLEAN"
        eff_hdr = "MINIMAL_ACCENT"
    elif raw_preset == "BOXED_CARDS":
        eff_text = "BOXED_CARDS"
        eff_img = "FRAMELESS_CLEAN"
        eff_hdr = "MINIMAL_ACCENT"

    # Step 2: Apply granular deck_style fields when not AUTO
    gran_text = str(ds.get("text_container_style") or "AUTO").strip().upper()
    if gran_text in ("CLEAN_OPEN", "LEFT_ACCENT_LINE", "BOXED_CARDS"):
        eff_text = gran_text

    gran_img = str(ds.get("image_frame_style") or "AUTO").strip().upper()
    if gran_img in ("FRAMELESS_CLEAN", "SOFT_SHADOW", "FRAMED_CARD"):
        eff_img = gran_img

    gran_hdr = str(ds.get("header_chrome_style") or "AUTO").strip().upper()
    if gran_hdr in ("MINIMAL_ACCENT", "COMPACT_SINGLE_LINE", "FULL_BANNER"):
        eff_hdr = gran_hdr

    # Step 1: Apply per-slide overrides if present on slide_spec
    if slide_spec is not None:
        def _get_field(obj: Any, key: str) -> Any:
            return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)

        for key_candidate in ("container_style_override", "card_theme_style", "visual_theme"):
            val = str(_get_field(slide_spec, key_candidate) or "").strip().upper()
            if val in ("CLEAN_OPEN", "LEFT_ACCENT_LINE", "BOXED_CARDS"):
                eff_text = val
                break

        img_ov = str(_get_field(slide_spec, "image_frame_style_override") or "").strip().upper()
        if img_ov in ("FRAMELESS_CLEAN", "SOFT_SHADOW", "FRAMED_CARD"):
            eff_img = img_ov

        hdr_ov = str(_get_field(slide_spec, "header_chrome_style_override") or "").strip().upper()
        if hdr_ov in ("MINIMAL_ACCENT", "COMPACT_SINGLE_LINE", "FULL_BANNER"):
            eff_hdr = hdr_ov

    # Typography scale & delta
    typo_scale = str(ds.get("typography_scale") or "COMFORTABLE").strip().upper()
    if typo_scale not in VALID_TYPOGRAPHY_SCALES:
        typo_scale = "COMFORTABLE"
    font_delta_map = {
        "COMFORTABLE": 0.0,
        "LARGE_PROJECTOR": 1.5,
        "COMPACT": -1.0,
    }
    font_size_delta_pt = font_delta_map.get(typo_scale, 0.0)

    # Safety banner mode
    safety_mode = str(ds.get("safety_banner_mode") or "ACUTE_HAZARDS_ONLY").strip().upper()
    if safety_mode not in VALID_SAFETY_BANNER_MODES:
        safety_mode = "ACUTE_HAZARDS_ONLY"

    match_palette = bool(ds.get("match_template_palette", True))

    cover_backdrop_id = str(ds.get("cover_backdrop_id") or "AUTO_TEMPLATE").strip()
    eff_cover_bg_url = str(getattr(prof, "cover_bg_url", "") or "").strip()
    if cover_backdrop_id.upper() == "NONE":
        eff_cover_bg_url = ""
    elif cover_backdrop_id and cover_backdrop_id.upper() not in ("", "AUTO", "AUTO_TEMPLATE"):
        by_bid = {item["id"]: item["url"] for item in NANO_BUILT_IN_BACKDROPS_CATALOG}
        eff_cover_bg_url = by_bid.get(cover_backdrop_id.lower(), eff_cover_bg_url)
    elif not eff_cover_bg_url and getattr(prof, "is_builtin", True):
        eff_cover_bg_url = resolve_default_cover_backdrop_for_badge(
            badge_name or str(ds.get("badge_name") or ""),
            prof.template_id,
        )

    return {
        "template_id": prof.template_id,
        "layout_style_preset": raw_preset,
        "text_container_style": eff_text,
        "image_frame_style": eff_img,
        "header_chrome_style": eff_hdr,
        "typography_scale": typo_scale,
        "font_size_delta_pt": font_size_delta_pt,
        "safety_banner_mode": safety_mode,
        "match_template_palette": match_palette,
        "cover_backdrop_id": cover_backdrop_id,
        "cover_bg_url": eff_cover_bg_url,
        "explicit_image_frame_override": gran_img in ("FRAMELESS_CLEAN", "SOFT_SHADOW", "FRAMED_CARD") or raw_preset != "AUTO_TEMPLATE",
        "explicit_header_chrome_override": gran_hdr in ("MINIMAL_ACCENT", "COMPACT_SINGLE_LINE", "FULL_BANNER") or raw_preset != "AUTO_TEMPLATE",
    }


def delete_custom_template(template_id: str) -> bool:
    """Deletes a custom (non-builtin) template or 3-variant custom Nano Banana family from the catalog."""
    norm = str(template_id or "").strip()
    if not norm:
        return False
    profiles = load_template_catalog()
    target = next((p for p in profiles if p.template_id == norm or p.family_id == norm), None)
    if not target or target.is_builtin:
        return False
    fam_id = str(target.family_id or "").strip()
    if fam_id and fam_id.startswith("nanobanana_tpl_"):
        ids_to_delete = {
            p.template_id
            for p in profiles
            if not p.is_builtin and (p.family_id == fam_id or p.template_id == norm)
        }
        prefixes_to_clean = list(ids_to_delete | {fam_id})
    else:
        ids_to_delete = {target.template_id}
        prefixes_to_clean = [target.template_id]

    remaining = [p for p in profiles if p.template_id not in ids_to_delete]
    save_template_catalog(remaining)
    for pfx in prefixes_to_clean:
        for f in (
            list(OVERLAYS_DIR.glob(f"{pfx}*"))
            + list(TEMPLATES_DIR.glob(f"{pfx}*"))
            + list(CUSTOM_TEMPLATES_DIR.glob(f"{pfx}*"))
        ):
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
            pixels = list(rgba.get_flattened_data()) if hasattr(rgba, 'get_flattened_data') else list(rgba.get_flattened_data()) if hasattr(rgba, "get_flattened_data") else list(rgba.getdata())
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


def _validate_public_template_url_host(host: str) -> None:
    """Blocks SSRF attempts against loopback, RFC1918 private, link-local, IPv6 internal, or cloud metadata hosts."""
    import ipaddress
    import socket

    clean_host = (host or "").strip().lower().rstrip(".")
    if not clean_host:
        raise ValueError("Template URL must include a valid hostname.")
    blocked_names = {
        "localhost",
        "metadata.google.internal",
        "metadata",
        "169.254.169.254",
        "0.0.0.0",
        "127.0.0.1",
        "::1",
    }
    if (
        clean_host in blocked_names
        or clean_host.endswith(".internal")
        or clean_host.endswith(".local")
        or clean_host.startswith("10.")
        or clean_host.startswith("192.168.")
    ):
        raise ValueError("Internal, loopback, or cloud metadata network URLs are not permitted.")

    def _check_ip(ip_str: str) -> None:
        ip_obj = ipaddress.ip_address(ip_str)
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            raise ValueError(f"Internal or non-routable IP address '{ip_str}' is not permitted.")

    try:
        _check_ip(clean_host)
        return
    except ValueError as exc:
        if "not permitted" in str(exc):
            raise

    try:
        addr_infos = socket.getaddrinfo(clean_host, None)
    except Exception as exc:
        raise ValueError(f"Unable to resolve template hostname '{clean_host}': {exc}") from exc

    for info in addr_infos:
        sockaddr = info[4]
        if sockaddr and sockaddr[0]:
            _check_ip(str(sockaddr[0]))


def ingest_template_from_url(
    url: str,
    custom_name: Optional[str] = None,
    bottom_safe_in: float = 6.55,
) -> TemplateProfile:
    """Downloads a `.pptx`, `.ppt`, or background image template from an HTTP/HTTPS URL and registers it."""
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Template URL must be a valid http:// or https:// URL.")
    _validate_public_template_url_host(parsed.hostname or "")

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
    badge_name: str = "",
    cover_backdrop_id: str = "AUTO_TEMPLATE",
) -> None:
    """Applies template watermark, top header strip, bottom silhouette/bar, and corner logo shapes onto a slide when not already in the native layout."""
    norm_tier = normalize_visual_theme(tier)
    norm_bd = str(cover_backdrop_id or "AUTO_TEMPLATE").strip()

    # Resolve effective cover_bg_url (auto-matching built-in templates with cover_bg_url == "" when AUTO_TEMPLATE)
    eff_cover_bg_url = str(profile.cover_bg_url or "").strip()
    if norm_bd.upper() == "NONE":
        eff_cover_bg_url = ""
    elif norm_bd and norm_bd.upper() not in ("", "AUTO", "AUTO_TEMPLATE"):
        by_bid = {item["id"]: item["url"] for item in NANO_BUILT_IN_BACKDROPS_CATALOG}
        eff_cover_bg_url = by_bid.get(norm_bd.lower(), eff_cover_bg_url)
    elif is_cover and not eff_cover_bg_url and profile.is_builtin and profile.template_id != "default_workbench":
        eff_cover_bg_url = resolve_default_cover_backdrop_for_badge(badge_name, profile.template_id)

    # 1. Cover hero background or subtle content-slide watermark
    if is_cover and eff_cover_bg_url and (
        not profile.use_native_master_layouts
        or profile.template_id in ("scouting_america_forest_sunrise", "scouting_america_250")
    ):
        cov_disk = _resolve_and_hydrate_template_asset(eff_cover_bg_url)
        if cov_disk.exists():
            try:
                with Image.open(cov_disk) as cim:
                    c_rgb = cim.convert("RGB")
                    veil_rgb = (15, 23, 42) if norm_tier == "STUDIO" else (250, 248, 245)
                    veil = Image.new("RGB", c_rgb.size, veil_rgb)
                    washed = Image.blend(veil, c_rgb, alpha=0.22)
                    buf = io.BytesIO()
                    washed.save(buf, format="JPEG", quality=90)
                    buf.seek(0)
                pic = slide.shapes.add_picture(buf, Inches(0.0), Inches(0.0), width=Inches(13.333), height=Inches(7.5))
                pic.name = "TemplateChrome_CoverBg"
            except Exception:
                pass
    elif profile.canvas_watermark_url:
        wm_disk = _resolve_and_hydrate_template_asset(profile.canvas_watermark_url)
        if wm_disk.exists():
            try:
                if norm_tier == "STUDIO":
                    with Image.open(wm_disk) as wim:
                        w_rgba = wim.convert("RGBA")
                        r_ch, g_ch, b_ch, a_ch = w_rgba.split()
                        dark_a = a_ch.point(lambda a: min(18, int(a * 0.35)))
                        silver = Image.new("L", w_rgba.size, 180)
                        dark_wm = Image.merge("RGBA", (silver, silver, silver, dark_a))
                        wbuf = io.BytesIO()
                        dark_wm.save(wbuf, format="PNG")
                        wbuf.seek(0)
                    pic = slide.shapes.add_picture(wbuf, Inches(0.0), Inches(0.0), width=Inches(13.333), height=Inches(7.5))
                    pic.name = "TemplateChrome_Watermark"
                else:
                    pic = slide.shapes.add_picture(str(wm_disk), Inches(0.0), Inches(0.0), width=Inches(13.333), height=Inches(7.5))
                    pic.name = "TemplateChrome_Watermark"
            except Exception:
                pass

    if profile.template_id == "default_workbench":
        return

    # 1b. Top header strip / crest banner (e.g. Guide to Advancement green header strip or Fleur-de-Lis crest)
    if profile.top_banner_url and not profile.use_native_master_layouts:
        top_disk = _resolve_and_hydrate_template_asset(profile.top_banner_url)
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
        sil_disk = _resolve_and_hydrate_template_asset(sil_url)
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
        logo_disk = _resolve_and_hydrate_template_asset(logo_url)
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
    badge_name: str = "",
    cover_backdrop_id: str = "AUTO_TEMPLATE",
) -> Tuple[Presentation, Callable[[bool, str], Any], SafeCanvasBounds, TemplateProfile]:
    """Instantiates a `Presentation` backed by `template_id` (Option C Hybrid).

    Returns:
      - `prs`: `Presentation` object (13.333" x 7.50")
      - `add_slide_fn(is_cover: bool, tier: str) -> Slide`: adds a slide using the template's layout,
        strips ghost placeholders, and applies template chrome.
      - `safe_bounds`: `SafeCanvasBounds` for AABB card/visual placement.
      - `profile`: `TemplateProfile` metadata.
    """
    profile = get_template_profile(template_id, badge_name=badge_name, cover_backdrop_id=cover_backdrop_id)
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
        decorate_slide_with_template_chrome(
            slide,
            profile,
            is_cover=is_cover,
            tier=tier,
            badge_name=badge_name,
            cover_backdrop_id=cover_backdrop_id,
        )
        return slide

    return prs, _add_slide, profile.safe_bounds, profile


# ==============================================================================
# NANO BANANA 3-VARIANT AI SLIDE TEMPLATE GENERATOR (v2.5 ITEM 6)
# ==============================================================================

NANO_BANANA_TEMPLATE_VISUAL_STYLES: Dict[str, Dict[str, str]] = {
    "topographic_adventure": {
        "label": "Topographic High Adventure & Contour Map",
        "description": "USGS contour lines, compass rose watermark, and mountain ridge silhouette.",
    },
    "pinewood_campfire": {
        "label": "Pinewood, Lake & Campfire Silhouette",
        "description": "Brushed timber header, pine trees & lake horizon footer silhouette, and campfire emblem watermark.",
    },
    "heritage_embroidery": {
        "label": "Heritage Embroidery & Merit Badge Sash",
        "description": "Twill border stitching, classic heritage frame, and fleur-de-lis watermark.",
    },
    "collegiate_mbc": {
        "label": "Collegiate / Merit Badge University Crest",
        "description": "Academic column/chevron header band, shield watermark, and podium footer.",
    },
    "aquatics_nautical": {
        "label": "Aquatics, Nautical & Waterfront Chart",
        "description": "Bathymetric depth contours, rope-knot accent stripe, and wave-crest footer.",
    },
    "stem_blueprint": {
        "label": "STEM Blueprint & Engineering Grid",
        "description": "Isometric CAD grid header/footer and technical circuit/gear watermark.",
    },
}

NANO_BANANA_FRAME_GEOMETRIES: Tuple[str, ...] = (
    "brushed_header_footer",
    "horizon_silhouette",
    "heritage_border",
    "split_header_minimal",
)

_TEMPLATE_YPT_AND_PII_PATTERNS: List[Tuple[str, re.Pattern]] = [
    (
        "YPT_YOUTH_PHOTO_OR_FACE_REQUEST",
        re.compile(
            r"\b(?:youth\s+photos?|scout\s+photos?|real\s+scout\s+faces?|child(?:ren)?\s+faces?|"
            r"minor\s+faces?|photos?\s+of\s+(?:a\s+)?(?:youth|child|children|minor|boy|girl|scouts?)|"
            r"faces?\s+of\s+(?:scouts?|youth|children|minors|kids)|identifiable\s+(?:youth|scout|child|minor)|"
            r"realistic\s+(?:youth|child|scout)\s+portraits?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "YPT_ONE_ON_ONE_CONTACT_VIOLATION",
        re.compile(
            r"\b(?:one[-\s]on[-\s]one|private\s+(?:meeting|tent|session|chat|dm)|"
            r"alone\s+with\s+(?:a\s+)?(?:scout|youth|child|minor)|no\s+adults?\s+present|"
            r"skip\s+two[-\s]deep|bypass\s+ypt)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ZERO_PII_EMAIL_DETECTED",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "ZERO_PII_PHONE_DETECTED",
        re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    ),
    (
        "ZERO_PII_STREET_ADDRESS_DETECTED",
        re.compile(
            r"\b\d{1,5}\s+[A-Za-z0-9.\s]{2,30}\s+"
            r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Parkway|Pkwy)\b",
            re.IGNORECASE,
        ),
    ),
]


def _clean_hex_color(raw: Optional[str], fallback: str = "#003F87") -> str:
    """Normalizes a `#RRGGBB` or `#RGB` hex color string."""
    s = str(raw or "").strip().lstrip("#").upper()
    if len(s) == 3 and all(c in "0123456789ABCDEF" for c in s):
        s = "".join(c * 2 for c in s)
    if len(s) == 6 and all(c in "0123456789ABCDEF" for c in s):
        return f"#{s}"
    return fallback


def _ensure_wcag_aa_dark_hex(hex_str: str) -> str:
    """Ensures `hex_str` is dark enough that white (`#FFFFFF`) header/footer text achieves >= 4.5:1 WCAG AA contrast."""
    r, g, b = hex_to_rgb(hex_str, (180, 83, 9))

    def _srgb_chan(c: int) -> float:
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    def _rel_lum(ri: int, gi: int, bi: int) -> float:
        return 0.2126 * _srgb_chan(ri) + 0.7152 * _srgb_chan(gi) + 0.0722 * _srgb_chan(bi)

    # White luminance is 1.0; contrast = 1.05 / (L + 0.05) >= 4.5 => L <= 0.1833
    lum = _rel_lum(r, g, b)
    while lum > 0.175 and (r > 0 or g > 0 or b > 0):
        r = int(r * 0.88)
        g = int(g * 0.88)
        b = int(b * 0.88)
        lum = _rel_lum(r, g, b)
    return f"#{r:02X}{g:02X}{b:02X}"


def _normalize_three_variant_colors(colors: Optional[List[str]]) -> Tuple[str, str, str]:
    """Normalizes 0..3 input hex colors into 3 distinct coordinated brand colors `(c1, c2, c3)`."""
    valid: List[str] = []
    for raw in colors or []:
        if not raw or not str(raw).strip():
            continue
        cleaned = _clean_hex_color(raw, "")
        if cleaned and cleaned not in valid:
            valid.append(cleaned)

    if not valid:
        return ("#003F87", "#1B5E20", "#D97706")

    if len(valid) == 1:
        c1 = valid[0]
        r1, g1, b1 = hex_to_rgb(c1, (0, 63, 135))
        # Derive c2 (complementary dark forest/navy)
        if b1 > r1 and b1 > g1:
            c2 = "#1B5E20"
        elif g1 > r1 and g1 >= b1:
            c2 = "#003F87"
        else:
            c2 = "#003F87" if c1 != "#003F87" else "#1B5E20"
        # Derive c3 (warm gold/amber accent or crimson if c1 is already gold/amber)
        if r1 > 160 and g1 > 90 and b1 < 80:
            c3 = "#8B0000"
        else:
            c3 = "#D97706"
        return (c1, c2, c3)

    if len(valid) == 2:
        c1, c2 = valid[0], valid[1]
        for candidate in ("#D97706", "#003F87", "#1B5E20", "#8B0000"):
            if candidate not in (c1, c2):
                return (c1, c2, candidate)
        return (c1, c2, "#D97706")

    return (valid[0], valid[1], valid[2])


def _compute_nano_template_safe_bounds(
    frame_geometry: str,
    logo_position: str,
    has_logo: bool = False,
) -> SafeCanvasBounds:
    """Computes collision-free `SafeCanvasBounds` dynamically from `frame_geometry` and `logo_position`."""
    geom = str(frame_geometry or "horizon_silhouette").strip().lower()
    logo_pos = str(logo_position or "bottom_left").strip().lower()

    left_in = 0.60
    right_in = 12.733
    header_top_in = 0.22
    header_height_in = 0.80
    header_banner_height_in = 0.22
    content_top_min_in = 1.12
    content_bottom_max_in = 6.82
    footer_left_in = 0.60
    footer_top_in = 7.02
    footer_max_width_in = 12.133

    if geom == "brushed_header_footer":
        header_top_in = 0.32
        header_banner_height_in = 0.27
        content_top_min_in = 1.15
        content_bottom_max_in = 6.86
        footer_top_in = 7.04
    elif geom == "horizon_silhouette":
        header_top_in = 0.22
        header_banner_height_in = 0.18
        content_top_min_in = 1.12
        content_bottom_max_in = 6.80
        footer_top_in = 7.06
    elif geom == "heritage_border":
        left_in = 0.68
        right_in = 12.65
        header_top_in = 0.28
        header_banner_height_in = 0.24
        content_top_min_in = 1.16
        content_bottom_max_in = 6.78
        footer_top_in = 7.00
    elif geom == "split_header_minimal":
        header_top_in = 0.18
        header_banner_height_in = 0.14
        content_top_min_in = 1.08
        content_bottom_max_in = 6.90
        footer_top_in = 7.08

    if logo_pos == "bottom_left":
        footer_left_in = 2.45 if has_logo else 1.85
        footer_max_width_in = round(right_in - footer_left_in, 3)
    elif logo_pos == "bottom_right":
        footer_left_in = left_in
        footer_max_width_in = round((10.35 if has_logo else 10.95) - footer_left_in, 3)
    elif logo_pos == "top_right":
        footer_left_in = left_in
        footer_max_width_in = round(right_in - left_in, 3)
        if has_logo:
            header_top_in = max(header_top_in, 0.28)
    else:  # cover_only
        footer_left_in = left_in
        footer_max_width_in = round(right_in - left_in, 3)

    return SafeCanvasBounds(
        left_in=left_in,
        right_in=right_in,
        header_top_in=header_top_in,
        header_height_in=header_height_in,
        header_banner_height_in=header_banner_height_in,
        content_top_min_in=content_top_min_in,
        content_bottom_max_in=content_bottom_max_in,
        safety_bar_height_in=0.68,
        footer_left_in=footer_left_in,
        footer_top_in=footer_top_in,
        footer_max_width_in=footer_max_width_in,
        suppress_native_footer=True,
    )


NANO_BUILT_IN_BACKDROPS_CATALOG: List[Dict[str, str]] = [
    {
        "id": "pinewood_campfire",
        "label": "🌲 Pinewood Forest & Campfire Clearing",
        "url": "/assets/templates/overlays/nano_base_pinewood_campfire.jpg",
        "path": "assets/templates/overlays/nano_base_pinewood_campfire.jpg",
        "file": "nano_base_pinewood_campfire.jpg",
        "keywords": "pinewood forest campfire clearing woods timber camp tent lantern",
    },
    {
        "id": "topographic_adventure",
        "label": "🏔️ High Adventure Alpine Summit Ridge",
        "url": "/assets/templates/overlays/nano_base_topographic_adventure.jpg",
        "path": "assets/templates/overlays/nano_base_topographic_adventure.jpg",
        "file": "nano_base_topographic_adventure.jpg",
        "keywords": "topographic mountain summit ridge hiking trail peak high adventure backpack",
    },
    {
        "id": "heritage_embroidery",
        "label": "🏕️ Rustic Timber Council Lodge & Stone Hearth",
        "url": "/assets/templates/overlays/nano_base_heritage_embroidery.jpg",
        "path": "assets/templates/overlays/nano_base_heritage_embroidery.jpg",
        "file": "nano_base_heritage_embroidery.jpg",
        "keywords": "heritage lodge timber fireplace pavilion cabin council hall",
    },
    {
        "id": "collegiate_mbc",
        "label": "🎓 Collegiate Brick Quadrangle & Bell Cupola",
        "url": "/assets/templates/overlays/nano_base_collegiate_mbc.jpg",
        "path": "assets/templates/overlays/nano_base_collegiate_mbc.jpg",
        "file": "nano_base_collegiate_mbc.jpg",
        "keywords": "collegiate university school cupola campus academic danvers holten brick merit badge college",
    },
    {
        "id": "aquatics_nautical",
        "label": "⚓ Coastal Lighthouse & Waterfront Dock",
        "url": "/assets/templates/overlays/nano_base_aquatics_nautical.jpg",
        "path": "assets/templates/overlays/nano_base_aquatics_nautical.jpg",
        "file": "nano_base_aquatics_nautical.jpg",
        "keywords": "aquatics nautical lighthouse ocean harbor cove sail sea waterfront dock",
    },
    {
        "id": "stem_blueprint",
        "label": "🔬 STEM Robotics Lab & Observatory Dome",
        "url": "/assets/templates/overlays/nano_base_stem_blueprint.jpg",
        "path": "assets/templates/overlays/nano_base_stem_blueprint.jpg",
        "file": "nano_base_stem_blueprint.jpg",
        "keywords": "stem blueprint robot circuit observatory engineering cad lab workshop",
    },
    {
        "id": "bsa_emblem_color",
        "label": "⚜️ Large Washed Color BSA Universal Emblem",
        "url": "/assets/templates/overlays/nano_base_bsa_emblem_color.jpg",
        "path": "assets/templates/overlays/nano_base_bsa_emblem_color.jpg",
        "file": "nano_base_bsa_emblem_color.jpg",
        "keywords": "bsa logo emblem fleur de lis scouting america universal crest shield color",
    },
    {
        "id": "apollo_rocket_launch",
        "label": "🚀 Space Exploration & Apollo Rocket Launch",
        "url": "/assets/templates/overlays/nano_base_apollo_rocket_launch.jpg",
        "path": "assets/templates/overlays/nano_base_apollo_rocket_launch.jpg",
        "file": "nano_base_apollo_rocket_launch.jpg",
        "keywords": "apollo rocket launch space exploration nasa saturn pad astronautcape canaveral",
    },
    {
        "id": "archery_target_range",
        "label": "🏹 Archery & Target Sports Timber Range",
        "url": "/assets/templates/overlays/nano_base_archery_target_range.jpg",
        "path": "assets/templates/overlays/nano_base_archery_target_range.jpg",
        "file": "nano_base_archery_target_range.jpg",
        "keywords": "archery bow arrow target range shooting sports rifle shotgun",
    },
    {
        "id": "pioneering_signal_tower",
        "label": "🪢 Pioneering Lashed Signal Tower & Monkey Bridge",
        "url": "/assets/templates/overlays/nano_base_pioneering_signal_tower.jpg",
        "path": "assets/templates/overlays/nano_base_pioneering_signal_tower.jpg",
        "file": "nano_base_pioneering_signal_tower.jpg",
        "keywords": "pioneering signal tower monkey bridge lashing rope knot spar timber",
    },
    {
        "id": "whitewater_kayak_rapids",
        "label": "🛶 Whitewater Kayaking & Canoeing River Rapids",
        "url": "/assets/templates/overlays/nano_base_whitewater_kayak_rapids.jpg",
        "path": "assets/templates/overlays/nano_base_whitewater_kayak_rapids.jpg",
        "file": "nano_base_whitewater_kayak_rapids.jpg",
        "keywords": "whitewater kayak canoe rapids river paddle rafting watercraft",
    },
    {
        "id": "first_aid_search_rescue",
        "label": "⛑️ Wilderness First Aid & Search-and-Rescue Basecamp",
        "url": "/assets/templates/overlays/nano_base_first_aid_search_rescue.jpg",
        "path": "assets/templates/overlays/nano_base_first_aid_search_rescue.jpg",
        "file": "nano_base_first_aid_search_rescue.jpg",
        "keywords": "first aid emergency medical search rescue triage wilderness survival",
    },
    {
        "id": "eagle_court_of_honor",
        "label": "🦅 Eagle Scout Court of Honor Ceremony Amphitheater",
        "url": "/assets/templates/overlays/nano_base_eagle_court_of_honor.jpg",
        "path": "assets/templates/overlays/nano_base_eagle_court_of_honor.jpg",
        "file": "nano_base_eagle_court_of_honor.jpg",
        "keywords": "eagle court of honor ceremony amphitheater flag stage citizenship",
    },
    {
        "id": "environmental_wetlands",
        "label": "🌿 Environmental Science & Nature Wetland Boardwalk",
        "url": "/assets/templates/overlays/nano_base_environmental_wetlands.jpg",
        "path": "assets/templates/overlays/nano_base_environmental_wetlands.jpg",
        "file": "nano_base_environmental_wetlands.jpg",
        "keywords": "environmental science nature ecology wetland marsh boardwalk forestry wildlife",
    },
    {
        "id": "aviation_glider_airfield",
        "label": "✈️ Aviation Airfield & Sailplane Glider Flight Line",
        "url": "/assets/templates/overlays/nano_base_aviation_glider_airfield.jpg",
        "path": "assets/templates/overlays/nano_base_aviation_glider_airfield.jpg",
        "file": "nano_base_aviation_glider_airfield.jpg",
        "keywords": "aviation airplane aircraft glider sailplane airfield flight pilot airport",
    },
    {
        "id": "dutch_oven_camp_cooking",
        "label": "🍳 Campfire Dutch Oven & Backcountry Trail Cooking",
        "url": "/assets/templates/overlays/nano_base_dutch_oven_camp_cooking.jpg",
        "path": "assets/templates/overlays/nano_base_dutch_oven_camp_cooking.jpg",
        "file": "nano_base_dutch_oven_camp_cooking.jpg",
        "keywords": "dutch oven cooking campfire hearth kitchen chuck box coals cast iron",
    },
    {
        "id": "citizenship_capitol_civic",
        "label": "🏛️ Capitol Dome, Constitution & Civic Heritage",
        "url": "/assets/templates/overlays/nano_base_citizenship_capitol_civic.jpg",
        "path": "assets/templates/overlays/nano_base_citizenship_capitol_civic.jpg",
        "file": "nano_base_citizenship_capitol_civic.jpg",
        "keywords": "citizenship capitol dome constitution civic heritage government law nation community world american",
    },
    {
        "id": "personal_management_ledger",
        "label": "🧭 Financial Ledger, Planning Compass & Time Management",
        "url": "/assets/templates/overlays/nano_base_personal_management_ledger.jpg",
        "path": "assets/templates/overlays/nano_base_personal_management_ledger.jpg",
        "file": "nano_base_personal_management_ledger.jpg",
        "keywords": "personal management financial ledger planning compass time budget family life entrepreneurship business",
    },
    {
        "id": "fitness_cycling_trail",
        "label": "🚴 Athletic Track, Cycling Trail & Personal Fitness",
        "url": "/assets/templates/overlays/nano_base_fitness_cycling_trail.jpg",
        "path": "assets/templates/overlays/nano_base_fitness_cycling_trail.jpg",
        "file": "nano_base_fitness_cycling_trail.jpg",
        "keywords": "athletic track cycling trail personal fitness sports athletics skating running",
    },
    {
        "id": "communications_studio",
        "label": "🎙️ Broadcast Microphone, Press Notebook & Council Podium",
        "url": "/assets/templates/overlays/nano_base_communications_studio.jpg",
        "path": "assets/templates/overlays/nano_base_communications_studio.jpg",
        "file": "nano_base_communications_studio.jpg",
        "keywords": "communication broadcast microphone press notebook council podium journalism public speaking radio theater",
    },
    {
        "id": "trades_welding_workshop",
        "label": "🛠️ Craftsman Workbench, Welding Sparks & Skilled Trades",
        "url": "/assets/templates/overlays/nano_base_trades_welding_workshop.jpg",
        "path": "assets/templates/overlays/nano_base_trades_welding_workshop.jpg",
        "file": "nano_base_trades_welding_workshop.jpg",
        "keywords": "trades welding workshop craftsman workbench sparks metalwork woodwork plumbing electricity automotive",
    },
    {
        "id": "wildlife_forestry_conservation",
        "label": "🦌 Old-Growth Forest Canopy, Wildlife Habitat & Conservation",
        "url": "/assets/templates/overlays/nano_base_wildlife_forestry_conservation.jpg",
        "path": "assets/templates/overlays/nano_base_wildlife_forestry_conservation.jpg",
        "file": "nano_base_wildlife_forestry_conservation.jpg",
        "keywords": "old growth forest canopy wildlife habitat conservation forestry mammal bird reptile nature fish",
    },
    {
        "id": "astronomy_deep_space_observatory",
        "label": "🔭 Night Sky Observatory Dome, Telescope & Milky Way",
        "url": "/assets/templates/overlays/nano_base_astronomy_deep_space_observatory.jpg",
        "path": "assets/templates/overlays/nano_base_astronomy_deep_space_observatory.jpg",
        "file": "nano_base_astronomy_deep_space_observatory.jpg",
        "keywords": "night sky observatory dome telescope milky way astronomy stars constellation galaxy deep space",
    },
    {
        "id": "emergency_medical_triage",
        "label": "🚑 Emergency First Aid Kit, Rescue Litter & Field Triage",
        "url": "/assets/templates/overlays/nano_base_emergency_medical_triage.jpg",
        "path": "assets/templates/overlays/nano_base_emergency_medical_triage.jpg",
        "file": "nano_base_emergency_medical_triage.jpg",
        "keywords": "emergency first aid kit rescue litter field triage preparedness lifesaving cpr medical health",
    },
]


def list_nano_builtin_backdrops() -> List[Dict[str, str]]:
    """Returns the catalog of 24 built-in Scouting washed background images."""
    return [dict(item) for item in NANO_BUILT_IN_BACKDROPS_CATALOG]


_BADGE_KEYWORD_TO_BACKDROP_ID: List[Tuple[Tuple[str, ...], str]] = [
    (("space exploration", "apollo", "rocket", "launch", "saturn", "nasa", "astronaut", "launchpad"), "apollo_rocket_launch"),
    (("astronomy", "night sky", "observatory dome", "telescope", "milky way", "constellation", "planetarium"), "astronomy_deep_space_observatory"),
    (("bsa logo", "bsa emblem", "universal emblem", "scouting logo", "color bsa"), "bsa_emblem_color"),
    (("archery", "bow", "arrow", "target range", "rifle shooting", "shotgun shooting", "shooting sports"), "archery_target_range"),
    (("pioneering", "signal tower", "monkey bridge", "lashing", "lashed", "spar", "timber tower"), "pioneering_signal_tower"),
    (("whitewater", "kayaking", "kayak", "canoeing", "canoe", "rapids", "rafting", "paddle"), "whitewater_kayak_rapids"),
    (("emergency preparedness", "emergency medical", "field triage", "rescue litter", "first aid kit", "dentistry", "health care", "medicine", "public health", "disabilities awareness"), "emergency_medical_triage"),
    (("first aid", "search and rescue", "wilderness survival", "lifesaving", "safety", "fire safety", "crime prevention", "traffic safety", "signs, signals, and codes"), "first_aid_search_rescue"),
    (("citizenship in the nation", "citizenship in the community", "citizenship in the world", "citizenship in society", "american heritage", "american cultures", "american labor", "law", "capitol dome", "constitution", "civic heritage"), "citizenship_capitol_civic"),
    (("court of honor", "eagle scout", "amphitheater", "ceremony stage", "color guard", "scouting heritage"), "eagle_court_of_honor"),
    (("personal management", "family life", "american business", "entrepreneurship", "salesmanship", "coin collecting", "stamp collecting", "collections", "genealogy", "scholarship", "reading", "financial ledger", "planning compass"), "personal_management_ledger"),
    (("personal fitness", "cycling", "athletics", "sports", "skating", "golf", "geocaching", "horsemanship", "snow sports", "climbing", "athletic track", "cycling trail"), "fitness_cycling_trail"),
    (("communication", "communications", "journalism", "public speaking", "radio", "theater", "moviemaking", "photography", "graphic arts", "music", "bugling", "animation", "art", "sculpture", "pottery", "broadcast microphone", "press notebook"), "communications_studio"),
    (("welding", "metalwork", "woodwork", "wood carving", "plumbing", "electricity", "automotive maintenance", "home repairs", "painting", "Pulp and Paper", "pulp and paper", "textile", "leatherwork", "basketry", "model design", "composite materials", "drafting", "surveying", "farm mechanics", "truck transportation", "railroading", "craftsman workbench"), "trades_welding_workshop"),
    (("forestry", "fish and wildlife", "mammal study", "bird study", "reptile and amphibian", "insect study", "nature", "plant science", "gardening", "landscape architecture", "animal science", "veterinary", "dog care", "pets", "horsemanship", "old-growth forest", "wildlife habitat"), "wildlife_forestry_conservation"),
    (("environmental science", "sustainability", "soil and water", "oceanography", "weather", "geology", "energy", "wetland", "marsh", "boardwalk", "ecology"), "environmental_wetlands"),
    (("aviation", "glider", "sailplane", "airfield", "airplane", "aircraft", "flight line"), "aviation_glider_airfield"),
    (("cooking", "dutch oven", "camp cooking", "cast iron", "chuck box", "campfire cooking", "outdoor kitchen"), "dutch_oven_camp_cooking"),
    (("collegiate", "university", "school", "cupola", "campus", "academic", "danvers", "holten", "brick"), "collegiate_mbc"),
    (("swimming", "small-boat sailing", "motorboating", "water sports", "scuba", "rowing", "fishing", "fly-fishing", "aquatic", "nautical", "lighthouse", "ocean", "harbor", "cove", "sail", "waterfront"), "aquatics_nautical"),
    (("robotics", "programming", "cybersecurity", "digital technology", "electronics", "engineering", "chemistry", "nuclear science", "mining in society", "inventing", "game design", "architecture", "chess", "stem", "blueprint", "robot", "circuit", "cad"), "stem_blueprint"),
    (("indian lore", "archaeology", "Theater", "lodge", "fireplace", "council ring", "pavilion", "embroidery"), "heritage_embroidery"),
    (("backpacking", "hiking", "orienteering", "mountaineering", "summit", "alpine", "mountain", "ridge", "topographic", "philmont"), "topographic_adventure"),
    (("camping", "woodcraft", "totin", "firem", "pinewood", "campfire", "forest", "pine"), "pinewood_campfire"),
]


def resolve_default_cover_backdrop_for_badge(badge_name: str, template_id: str = "") -> str:
    """Resolves the badge-matched washed cover backdrop relative URL (`assets/templates/overlays/nano_base_*.jpg`)."""
    clean_badge = str(badge_name or "").strip()
    clean_tpl = str(template_id or "").strip().lower()
    if clean_tpl and not clean_badge:
        for prof in [*BUILTIN_TEMPLATES, *DMBC_HVSC_TEMPLATES]:
            if prof.template_id == clean_tpl and prof.cover_bg_url:
                _resolve_and_hydrate_template_asset(prof.cover_bg_url)
                return prof.cover_bg_url
    resolved_path = _resolve_nano_photorealistic_base_cover(
        visual_style=clean_badge or clean_tpl or "pinewood_campfire",
        custom_prompt=clean_badge,
    )
    try:
        rel_str = resolved_path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
        return f"/{rel_str}" if not rel_str.startswith("/") else rel_str
    except Exception:
        return f"/assets/templates/overlays/{resolved_path.name}"


def _match_badge_catalog_photo_for_prompt(custom_prompt: str) -> Optional[Path]:
    """Searches `assets/badge_image_catalog/` for a high-resolution photo matching `custom_prompt` keywords."""
    if not custom_prompt or not custom_prompt.strip():
        return None
    badge_cat_dir = OVERLAYS_DIR.parent.parent / "badge_image_catalog"
    if not badge_cat_dir.is_dir():
        return None
    tokens = [
        tok
        for tok in re.findall(r"[a-z0-9]+", custom_prompt.lower())
        if len(tok) >= 3 and tok not in {"the", "and", "for", "with", "shot", "distance", "from", "into", "over", "under", "washed", "background", "backdrop", "slide", "template"}
    ]
    if not tokens:
        return None
    best_folder: Optional[Path] = None
    best_score = 0
    for folder in sorted(badge_cat_dir.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        fname = folder.name.lower()
        score = sum(3 if tok in fname.split("_") else (2 if tok in fname else 0) for tok in tokens)
        if score > best_score:
            best_score = score
            best_folder = folder
    if best_folder is not None and best_score >= 2:
        imgs = sorted(
            [p for p in best_folder.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and p.stat().st_size > 25000],
            key=lambda p: p.stat().st_size,
            reverse=True,
        )
        if imgs:
            return imgs[0]
    return None


def _resolve_nano_photorealistic_base_cover(
    visual_style: str = "pinewood_campfire",
    custom_prompt: str = "",
    family_id: str = "",
    allow_live_synthesis: bool = False,
    backdrop_id: str = "",
    custom_bg_path: Optional[Path] = None,
) -> Path:
    """Resolves a high-resolution 16:9 photorealistic scenic base photograph for Slide 1 cover_bg_url."""
    import os

    if custom_bg_path is not None and custom_bg_path.exists():
        return custom_bg_path

    clean_backdrop_id = str(backdrop_id or "").strip().lower()
    by_id = {item["id"]: OVERLAYS_DIR / item["file"] for item in NANO_BUILT_IN_BACKDROPS_CATALOG}

    # If user explicitly chose one of the 24 built-in backdrops from the dropdown:
    if clean_backdrop_id and clean_backdrop_id not in ("auto", "ai_prompt", "custom_upload"):
        explicit_path = by_id.get(clean_backdrop_id)
        if explicit_path is not None:
            _resolve_and_hydrate_template_asset(explicit_path)
            if explicit_path.exists():
                return explicit_path

    style_key = str(visual_style or "pinewood_campfire").strip().lower()
    custom_lc = (custom_prompt or "").strip().lower()
    # Allow calling `_resolve_nano_photorealistic_base_cover(badge_name)` with 1 positional argument
    search_lc = custom_lc if custom_lc else (style_key if style_key not in by_id else "")

    matched_builtin_path: Optional[Path] = None
    if search_lc:
        for kw_tuple, bid in _BADGE_KEYWORD_TO_BACKDROP_ID:
            if any(k in search_lc for k in kw_tuple):
                cand_p = by_id.get(bid)
                if cand_p is not None:
                    _resolve_and_hydrate_template_asset(cand_p)
                    if cand_p.exists():
                        matched_builtin_path = cand_p
                        break

    # Live AI Image Synthesis when requested (`ai_prompt` or custom_prompt with `allow_live_synthesis`)
    if (
        allow_live_synthesis
        and family_id
        and (clean_backdrop_id == "ai_prompt" or (custom_lc and matched_builtin_path is None))
        and not os.getenv("PYTEST_CURRENT_TEST")
        and os.getenv("ENABLE_LIVE_TEMPLATE_COVER_AI", "true").lower() in ("true", "1", "yes")
    ):
        ai_base_path = CUSTOM_TEMPLATES_DIR / f"{family_id}_ai_base_cover.png"
        if ai_base_path.exists() and ai_base_path.stat().st_size > 10000:
            return ai_base_path
        try:
            from src.agents.image_studio import _try_live_ai_image_synthesis

            subj = (
                custom_prompt.strip()
                if custom_prompt and len(custom_prompt.strip()) >= 6
                else f"Wide-angle 16:9 DSLR outdoor scenic landscape for {style_key.replace('_', ' ')} Scouting theme"
            )
            if _try_live_ai_image_synthesis(
                visual_subject=f"Wide-angle 16:9 DSLR landscape or architectural photograph: {subj}",
                visual_style="Photorealistic Image",
                seed_int=abs(hash(f"{family_id}:{subj}")) % 10000,
                out_path=ai_base_path,
                include_humans=False,
                compress_800x600=False,
                badge_name="Camping",
            ):
                if ai_base_path.exists() and ai_base_path.stat().st_size > 10000:
                    return ai_base_path
        except Exception:
            pass

    if matched_builtin_path is not None and matched_builtin_path.exists():
        return matched_builtin_path

    badge_photo = _match_badge_catalog_photo_for_prompt(custom_prompt or search_lc)
    if badge_photo is not None and badge_photo.exists():
        return badge_photo

    if style_key in by_id:
        _resolve_and_hydrate_template_asset(by_id[style_key])
        if by_id[style_key].exists():
            return by_id[style_key]

    for fallback_name in ("nano_base_pinewood_campfire.jpg", "forest_sunrise_cover.jpg", "high_adventure_climb.jpg"):
        cand = OVERLAYS_DIR / fallback_name
        _resolve_and_hydrate_template_asset(cand)
        if cand.exists():
            return cand
    return OVERLAYS_DIR / "forest_sunrise_cover.jpg"


def _render_nano_template_variant_assets(
    variant_id: str,
    visual_style: str,
    frame_geometry: str,
    primary_hex: str,
    accent_hex: str,
    logo_img: Optional[Image.Image],
    logo_position: str,
    custom_prompt: str = "",
    base_cover_path: Optional[Path] = None,
) -> Dict[str, str]:
    """Synthesizes coordinated 16:9 artwork for top_banner, bottom_silhouette, canvas_watermark (5% opacity), and photorealistic cover_bg."""
    import math as _math
    from PIL import ImageDraw, ImageEnhance, ImageOps

    _ensure_dirs()
    p_rgb = hex_to_rgb(primary_hex, (0, 63, 135))
    a_rgb = hex_to_rgb(accent_hex, (217, 119, 6))
    style_key = str(visual_style or "pinewood_campfire").strip().lower()
    geom_key = str(frame_geometry or "horizon_silhouette").strip().lower()
    logo_pos = str(logo_position or "bottom_left").strip().lower()

    # 1. Top Header Strip (1600 x 72)
    top_w, top_h = 1600, 72
    top_im = Image.new("RGBA", (top_w, top_h), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(top_im)
    bar_h = 52 if geom_key != "split_header_minimal" else 34
    tdraw.rectangle([0, 0, top_w, bar_h], fill=(*p_rgb, 255))
    tdraw.rectangle([0, bar_h, top_w, bar_h + 8], fill=(*a_rgb, 255))
    if style_key == "heritage_embroidery" or geom_key == "heritage_border":
        for x in range(16, top_w - 16, 28):
            tdraw.rectangle([x, bar_h - 10, x + 14, bar_h - 6], fill=(*a_rgb, 230))
    elif style_key == "stem_blueprint":
        for x in range(0, top_w, 40):
            tdraw.line([(x, 0), (x, bar_h)], fill=(255, 255, 255, 45), width=1)
    elif style_key == "collegiate_mbc":
        for x in range(40, top_w, 120):
            tdraw.polygon([(x, 0), (x + 24, 0), (x + 12, bar_h)], fill=(*a_rgb, 95))
    elif style_key == "topographic_adventure":
        for y_off in (12, 26, 38):
            pts = [(x, int(y_off + 5 * _math.sin(x / 90.0))) for x in range(0, top_w + 20, 20)]
            tdraw.line(pts, fill=(255, 255, 255, 55), width=2)
    elif style_key == "aquatics_nautical":
        pts = [(x, int(bar_h - 10 + 4 * _math.sin(x / 32.0))) for x in range(0, top_w + 16, 16)]
        tdraw.line(pts, fill=(*a_rgb, 220), width=3)

    if logo_img is not None and logo_pos == "top_right":
        l_thumb = logo_img.copy()
        l_thumb.thumbnail((56, 56), Image.Resampling.LANCZOS)
        top_im.alpha_composite(l_thumb, (top_w - l_thumb.width - 28, max(2, (bar_h - l_thumb.height) // 2)))

    top_path = CUSTOM_TEMPLATES_DIR / f"{variant_id}_top_banner.png"
    top_im.save(top_path)

    # 2. Bottom Silhouette / Footer Banner (1600 x 110) + Dark Slate Variant
    bot_w, bot_h = 1600, 110
    bot_im = Image.new("RGBA", (bot_w, bot_h), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(bot_im)
    bot_dark = Image.new("RGBA", (bot_w, bot_h), (0, 0, 0, 0))
    bddraw = ImageDraw.Draw(bot_dark)

    # Base footer band (bot_dark uses genuinely dark translucent slate (15, 23, 42) behind #FFFFFF footer text for 13.8:1 contrast)
    bdraw.rectangle([0, 46, bot_w, bot_h], fill=(*p_rgb, 255))
    bdraw.rectangle([0, 38, bot_w, 46], fill=(*a_rgb, 255))
    bddraw.rectangle([0, 46, bot_w, bot_h], fill=(15, 23, 42, 240))
    bddraw.rectangle([0, 38, bot_w, 46], fill=(*a_rgb, 255))

    if style_key in ("pinewood_campfire", "topographic_adventure"):
        # Mountain ridge + pine tree horizon silhouette along top of footer
        ridge_pts = [(0, 46)]
        for x in range(0, bot_w + 40, 40):
            y_r = int(28 - 14 * abs(_math.sin(x / 180.0)) - 6 * _math.cos(x / 75.0))
            ridge_pts.append((x, max(6, y_r)))
        ridge_pts.append((bot_w, 46))
        bdraw.polygon(ridge_pts, fill=(*p_rgb, 255))
        bddraw.polygon(ridge_pts, fill=(15, 23, 42, 240))
        if style_key == "pinewood_campfire":
            for tx in range(60, bot_w - 60, 55):
                th = 22 + (tx % 14)
                bdraw.polygon([(tx, 44 - th), (tx - 10, 44), (tx + 10, 44)], fill=(*p_rgb, 255))
                bddraw.polygon([(tx, 44 - th), (tx - 10, 44), (tx + 10, 44)], fill=(15, 23, 42, 240))
    elif style_key == "aquatics_nautical":
        wave_pts = [(0, 46)]
        for x in range(0, bot_w + 20, 20):
            y_w = int(32 + 8 * _math.sin(x / 28.0))
            wave_pts.append((x, y_w))
        wave_pts.append((bot_w, 46))
        bdraw.polygon(wave_pts, fill=(*p_rgb, 255))
        bddraw.polygon(wave_pts, fill=(15, 23, 42, 240))
    elif style_key == "collegiate_mbc":
        # Classical academic podium band with subtle gold accent rule
        bdraw.rectangle([0, 32, bot_w, 38], fill=(*p_rgb, 235))
        bddraw.rectangle([0, 32, bot_w, 38], fill=(15, 23, 42, 225))
    elif style_key == "stem_blueprint":
        for x in range(0, bot_w, 40):
            bdraw.line([(x, 46), (x, bot_h)], fill=(255, 255, 255, 42), width=1)
            bddraw.line([(x, 46), (x, bot_h)], fill=(255, 255, 255, 42), width=1)
    elif style_key == "heritage_embroidery" or geom_key == "heritage_border":
        for x in range(20, bot_w - 20, 32):
            bdraw.rectangle([x, 52, x + 16, 57], fill=(*a_rgb, 235))
            bddraw.rectangle([x, 52, x + 16, 57], fill=(*a_rgb, 235))

    if logo_img is not None and logo_pos in ("bottom_left", "bottom_right"):
        l_thumb = logo_img.copy()
        l_thumb.thumbnail((72, 72), Image.Resampling.LANCZOS)
        lx = 32 if logo_pos == "bottom_left" else (bot_w - l_thumb.width - 32)
        ly = max(8, bot_h - l_thumb.height - 10)
        bot_im.alpha_composite(l_thumb, (lx, ly))
        bot_dark.alpha_composite(l_thumb, (lx, ly))

    bot_path = CUSTOM_TEMPLATES_DIR / f"{variant_id}_bottom_silhouette.png"
    bot_dark_path = CUSTOM_TEMPLATES_DIR / f"{variant_id}_bottom_silhouette_dark.png"
    bot_im.save(bot_path)
    bot_dark.save(bot_dark_path)

    # 3. Subtle 5% Opacity Full-Canvas Watermark (1600 x 900)
    wm_w, wm_h = 1600, 900
    wm_im = Image.new("RGBA", (wm_w, wm_h), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(wm_im)
    wm_alpha = 13  # ~5% opacity (13 / 255 = 5.1%)
    cx, cy = wm_w // 2, wm_h // 2

    if style_key == "topographic_adventure":
        for rad in range(90, 680, 65):
            wdraw.ellipse([cx - rad * 1.3, cy - rad * 0.8, cx + rad * 1.3, cy + rad * 0.8], outline=(*p_rgb, wm_alpha), width=3)
        # Compass rose in center
        wdraw.ellipse([cx - 110, cy - 110, cx + 110, cy + 110], outline=(*a_rgb, wm_alpha + 4), width=3)
        wdraw.polygon([(cx, cy - 140), (cx + 28, cy), (cx, cy + 140), (cx - 28, cy)], outline=(*p_rgb, wm_alpha + 4))
    elif style_key == "pinewood_campfire":
        # Campfire + pine emblem watermark
        wdraw.ellipse([cx - 170, cy - 170, cx + 170, cy + 170], outline=(*p_rgb, wm_alpha), width=4)
        wdraw.polygon([(cx, cy - 110), (cx + 65, cy + 40), (cx - 65, cy + 40)], outline=(*a_rgb, wm_alpha + 4), fill=(*a_rgb, wm_alpha // 2))
        wdraw.rectangle([cx - 75, cy + 48, cx + 75, cy + 68], fill=(*p_rgb, wm_alpha))
    elif style_key == "heritage_embroidery":
        # Sash diagonal stitching & fleur crest ring
        wdraw.line([(160, 80), (1440, 820)], fill=(*p_rgb, wm_alpha), width=5)
        wdraw.line([(185, 80), (1465, 820)], fill=(*a_rgb, wm_alpha), width=3)
        wdraw.ellipse([cx - 160, cy - 160, cx + 160, cy + 160], outline=(*p_rgb, wm_alpha + 3), width=5)
    elif style_key == "collegiate_mbc":
        # Academic shield crest
        shield_pts = [(cx - 140, cy - 150), (cx + 140, cy - 150), (cx + 140, cy + 20), (cx, cy + 170), (cx - 140, cy + 20)]
        wdraw.polygon(shield_pts, outline=(*p_rgb, wm_alpha + 4), fill=(*p_rgb, wm_alpha // 2))
    elif style_key == "aquatics_nautical":
        for wy in range(160, 760, 85):
            pts = [(x, int(wy + 18 * _math.sin(x / 75.0))) for x in range(120, 1480, 24)]
            wdraw.line(pts, fill=(*p_rgb, wm_alpha), width=3)
    elif style_key == "stem_blueprint":
        for gx in range(100, 1500, 80):
            wdraw.line([(gx, 80), (gx, 820)], fill=(*p_rgb, wm_alpha), width=1)
        for gy in range(100, 820, 80):
            wdraw.line([(100, gy), (1500, gy)], fill=(*p_rgb, wm_alpha), width=1)
        wdraw.ellipse([cx - 150, cy - 150, cx + 150, cy + 150], outline=(*a_rgb, wm_alpha + 4), width=4)

    wm_path = CUSTOM_TEMPLATES_DIR / f"{variant_id}_watermark.png"
    wm_im.save(wm_path)

    # 4. Full-Bleed Photorealistic Slide 1 Washed Cover Backdrop (1600 x 900)
    # Note: In `ui/app.js` (`opacity: 0.18-0.22`) and `decorate_slide_with_template_chrome` (`alpha=0.22`),
    # `cover_bg_url` is blended across the entire first slide just like `BSA Forest Sunrise` (`forest_sunrise_cover.jpg`),
    # `BSA High Adventure` (`high_adventure_climb.jpg`), `Camp Hidden Valley` (`hvsc_v1_cover_bg.jpg`), and `Danvers MBC` (`dmbc_v1_cover_bg.jpg`).
    cov_w, cov_h = 1600, 900
    resolved_cover_src = base_cover_path or _resolve_nano_photorealistic_base_cover(
        visual_style=style_key,
        custom_prompt=custom_prompt,
    )
    if resolved_cover_src.exists():
        with Image.open(resolved_cover_src) as raw_cov:
            photo_rgb = ImageOps.fit(raw_cov.convert("RGB"), (cov_w, cov_h), method=Image.Resampling.LANCZOS)
        # Apply subtle, natural photographic color grading toward the variant's primary & accent brand palette
        # while preserving 100% of the crisp DSLR photographic detail, clouds, water reflections, and textures.
        gray = ImageOps.grayscale(photo_rgb)
        mid_tint = (
            min(255, int(p_rgb[0] * 0.55 + a_rgb[0] * 0.45)),
            min(255, int(p_rgb[1] * 0.55 + a_rgb[1] * 0.45)),
            min(255, int(p_rgb[2] * 0.55 + a_rgb[2] * 0.45)),
        )
        high_tint = (
            min(255, int(235 + a_rgb[0] * 0.08)),
            min(255, int(235 + a_rgb[1] * 0.08)),
            min(255, int(235 + a_rgb[2] * 0.08)),
        )
        duotone = ImageOps.colorize(gray, black=p_rgb, mid=mid_tint, white=high_tint)
        graded_rgb = Image.blend(photo_rgb, duotone, alpha=0.18)
        graded_rgb = ImageEnhance.Contrast(graded_rgb).enhance(1.05)
        cov_im = graded_rgb.convert("RGBA")
    else:
        cov_im = Image.new("RGBA", (cov_w, cov_h), (248, 246, 240, 255))

    if logo_img is not None:
        c_logo = logo_img.copy()
        c_logo.thumbnail((150, 150), Image.Resampling.LANCZOS)
        cov_im.alpha_composite(c_logo, (cov_w - c_logo.width - 48, cov_h - c_logo.height - 28))

    cov_path = CUSTOM_TEMPLATES_DIR / f"{variant_id}_cover_bg.png"
    cov_im.save(cov_path)

    return {
        "top_banner_url": f"/assets/templates/custom/{top_path.name}",
        "bottom_silhouette_url": f"/assets/templates/custom/{bot_path.name}",
        "bottom_silhouette_dark_url": f"/assets/templates/custom/{bot_dark_path.name}",
        "canvas_watermark_url": f"/assets/templates/custom/{wm_path.name}",
        "cover_bg_url": f"/assets/templates/custom/{cov_path.name}",
    }


_generate_nano_banana_pillow_overlays = _render_nano_template_variant_assets


_NAMED_COLOR_ANCHORS: List[Tuple[str, Tuple[int, int, int]]] = [
    ("Red", (206, 17, 38)),
    ("Crimson", (139, 0, 0)),
    ("Green", (27, 94, 32)),
    ("Olive", (63, 98, 18)),
    ("Blue", (2, 132, 199)),
    ("Navy", (0, 63, 135)),
    ("Gold", (217, 119, 6)),
    ("Orange", (234, 88, 12)),
    ("Teal", (15, 118, 110)),
    ("Purple", (124, 58, 237)),
    ("Brown", (120, 63, 4)),
    ("Slate", (30, 41, 59)),
]


def get_closest_color_name(hex_str: str) -> str:
    """Maps any hex color to a human-friendly common color name (Red, Green, Blue, Gold, Navy, Teal, Orange, Purple, Crimson, Brown, Slate, Olive)."""
    import colorsys

    r, g, b = hex_to_rgb(hex_str, (27, 94, 32))
    h_val, l_val, s_val = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    deg = (h_val * 360.0) % 360.0

    if s_val < 0.16 or l_val < 0.12:
        return "Slate"
    if 345 <= deg or deg < 14:
        return "Crimson" if l_val < 0.34 else "Red"
    if 14 <= deg < 30:
        return "Brown" if l_val < 0.34 else "Orange"
    if 30 <= deg < 62:
        return "Brown" if (l_val < 0.28 and s_val < 0.65) else "Gold"
    if 62 <= deg < 92:
        return "Olive"
    if 92 <= deg < 164:
        return "Green"
    if 164 <= deg < 194:
        return "Teal"
    if 194 <= deg < 255:
        return "Navy" if l_val < 0.30 else "Blue"
    if 255 <= deg < 315:
        return "Purple"
    return "Crimson" if l_val < 0.35 else "Red"


def get_disambiguated_color_names(hex_list: List[str]) -> List[str]:
    """Returns distinct color names for up to 3 hex colors (e.g. ['Green', 'Blue', 'Gold'])."""
    fallbacks_by_base = {
        "Blue": ["Navy", "Teal", "Slate"],
        "Navy": ["Blue", "Slate", "Teal"],
        "Red": ["Crimson", "Orange", "Gold"],
        "Crimson": ["Red", "Brown", "Gold"],
        "Green": ["Olive", "Teal", "Gold"],
        "Olive": ["Green", "Brown", "Gold"],
        "Gold": ["Orange", "Brown", "Red"],
        "Orange": ["Gold", "Red", "Brown"],
        "Teal": ["Blue", "Green", "Navy"],
        "Purple": ["Navy", "Crimson", "Slate"],
        "Brown": ["Gold", "Crimson", "Olive"],
        "Slate": ["Navy", "Blue", "Teal"],
    }
    used: set[str] = set()
    out: List[str] = []
    for hx in hex_list:
        base = get_closest_color_name(hx)
        chosen = base
        if chosen in used:
            for alt in fallbacks_by_base.get(base, ["Blue", "Gold", "Red"]):
                if alt not in used:
                    chosen = alt
                    break
        used.add(chosen)
        out.append(chosen)
    return out


def _build_nano_template_master_pptx(profile: TemplateProfile) -> str:
    """Creates and saves a valid 16:9 widescreen `.pptx` master file for `profile` under `CUSTOM_TEMPLATES_DIR`."""
    _ensure_dirs()
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[min(6, len(prs.slide_layouts) - 1)]

    # Add sample cover and content slides decorated with the variant's chrome
    cover_slide = prs.slides.add_slide(blank_layout)
    _strip_slide_placeholders(cover_slide)
    decorate_slide_with_template_chrome(cover_slide, profile, is_cover=True, tier="BEAUTIFIED")

    content_slide = prs.slides.add_slide(blank_layout)
    _strip_slide_placeholders(content_slide)
    decorate_slide_with_template_chrome(content_slide, profile, is_cover=False, tier="BEAUTIFIED")

    out_pptx = CUSTOM_TEMPLATES_DIR / f"{profile.template_id}.pptx"
    prs.save(str(out_pptx))
    return f"assets/templates/custom/{out_pptx.name}"


def synthesize_custom_washed_backdrop(
    prompt: str = "",
    visual_style: str = "pinewood_campfire",
    backdrop_id: str = "ai_prompt",
    custom_bg_data_url: str = "",
    custom_bg_description: str = "",
    primary_hex: str = "#1B5E20",
    accent_hex: str = "#D97706",
) -> Dict[str, Any]:
    """Synthesizes or resolves a 16:9 washed background image from a custom prompt, uploaded photo, or built-in theme."""
    import base64
    from PIL import ImageEnhance, ImageOps

    try:
        from src.security.spiffe_and_armor import sanitize_text_with_model_armor  # type: ignore
    except Exception:
        from src.agents.guardrails import sanitize_text_with_model_armor

    clean_prompt = str(prompt or "").strip()
    clean_bg_desc = str(custom_bg_description or "").strip()
    combined = f"{clean_prompt} {clean_bg_desc}".strip()
    if combined:
        raw_guard = sanitize_text_with_model_armor(combined)
        guard_res = dict(raw_guard) if isinstance(raw_guard, dict) else {"is_safe": True, "allowed": True}
        violations = list(guard_res.get("violations") or [])
        for v_code, pat in _TEMPLATE_YPT_AND_PII_PATTERNS:
            if pat.search(combined) and v_code not in violations:
                violations.append(v_code)
        if not bool(guard_res.get("is_safe", True)) or not bool(guard_res.get("allowed", True)) or violations:
            return {
                "status": "BLOCKED_BY_GUARDRAIL",
                "blocked": True,
                "message": "Blocked by Scouting America Youth Protection (YPT) & Zero-PII Model Armor Guardrail.",
                "violations": violations,
            }

    _ensure_dirs()
    short_key = hashlib.sha256(
        f"{clean_prompt}:{visual_style}:{backdrop_id}:{clean_bg_desc}:{primary_hex}:{accent_hex}:{len(custom_bg_data_url or '')}".encode("utf-8")
    ).hexdigest()[:10]
    synth_id = f"nanobg_{short_key}"

    uploaded_path: Optional[Path] = None
    if custom_bg_data_url and str(custom_bg_data_url).strip():
        raw_b64 = str(custom_bg_data_url).strip()
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        try:
            bg_bytes = base64.b64decode(raw_b64)
            with Image.open(io.BytesIO(bg_bytes)) as uim:
                fitted_u = ImageOps.fit(uim.convert("RGB"), (1600, 900), method=Image.Resampling.LANCZOS)
                uploaded_path = CUSTOM_TEMPLATES_DIR / f"{synth_id}_uploaded_raw.jpg"
                fitted_u.save(uploaded_path, "JPEG", quality=92)
        except Exception:
            uploaded_path = None

    resolved_src = _resolve_nano_photorealistic_base_cover(
        visual_style=visual_style,
        custom_prompt=clean_prompt or clean_bg_desc,
        family_id=synth_id,
        allow_live_synthesis=True,
        backdrop_id=backdrop_id,
        custom_bg_path=uploaded_path,
    )

    p_rgb = hex_to_rgb(primary_hex, (27, 94, 32))
    a_rgb = hex_to_rgb(accent_hex, (217, 119, 6))
    cov_w, cov_h = 1600, 900
    if resolved_src.exists():
        with Image.open(resolved_src) as raw_cov:
            photo_rgb = ImageOps.fit(raw_cov.convert("RGB"), (cov_w, cov_h), method=Image.Resampling.LANCZOS)
        gray = ImageOps.grayscale(photo_rgb)
        mid_tint = (
            min(255, int(p_rgb[0] * 0.55 + a_rgb[0] * 0.45)),
            min(255, int(p_rgb[1] * 0.55 + a_rgb[1] * 0.45)),
            min(255, int(p_rgb[2] * 0.55 + a_rgb[2] * 0.45)),
        )
        high_tint = (
            min(255, int(235 + a_rgb[0] * 0.08)),
            min(255, int(235 + a_rgb[1] * 0.08)),
            min(255, int(235 + a_rgb[2] * 0.08)),
        )
        duotone = ImageOps.colorize(gray, black=p_rgb, mid=mid_tint, white=high_tint)
        graded_rgb = Image.blend(photo_rgb, duotone, alpha=0.18)
        graded_rgb = ImageEnhance.Contrast(graded_rgb).enhance(1.05)
    else:
        graded_rgb = Image.new("RGB", (cov_w, cov_h), (248, 246, 240))

    graded_out = CUSTOM_TEMPLATES_DIR / f"{synth_id}_cover_bg.jpg"
    graded_rgb.save(graded_out, "JPEG", quality=91)

    # Also build a pre-washed 16:9 canvas image (blended 26% with warm cream #FAF8F5) for standalone Washed Background inspection
    warm_cream = Image.new("RGB", (cov_w, cov_h), (250, 248, 245))
    washed_canvas = Image.blend(warm_cream, graded_rgb, alpha=0.26)
    washed_out = CUSTOM_TEMPLATES_DIR / f"{synth_id}_washed_preview.jpg"
    washed_canvas.save(washed_out, "JPEG", quality=91)

    matched_id = backdrop_id
    matched_label = "Nano Banana AI Washed Backdrop"
    if uploaded_path is not None and uploaded_path.exists():
        matched_label = f"Uploaded Photo ({clean_bg_desc or 'Custom Background'})"
    else:
        for item in NANO_BUILT_IN_BACKDROPS_CATALOG:
            if resolved_src.name == item["file"]:
                matched_id = item["id"]
                matched_label = item["label"]
                break

    cover_bg_rel = f"/assets/templates/custom/{graded_out.name}"
    return {
        "status": "SUCCESS",
        "synth_id": synth_id,
        "backdrop_id": matched_id,
        "source_file": resolved_src.name,
        "source_label": matched_label,
        "backdrop_url": cover_bg_rel,
        "cover_bg_url": cover_bg_rel,
        "washed_preview_url": f"/assets/templates/custom/{washed_out.name}",
        "description": clean_bg_desc or clean_prompt or resolved_src.stem.replace("nano_base_", "").replace("_", " ").title(),
    }


def generate_nano_banana_template_family(
    family_name: str,
    visual_style: str = "pinewood_campfire",
    frame_geometry: str = "horizon_silhouette",
    colors: Optional[List[str]] = None,
    custom_prompt: str = "",
    logo_data_url: str = "",
    logo_position: str = "bottom_left",
    remove_logo_white_bg: bool = True,
    preview_only: bool = False,
    user_consented: bool = False,
    include_secondary: Optional[bool] = None,
    include_accent: Optional[bool] = None,
    backdrop_id: str = "auto",
    custom_bg_data_url: str = "",
    custom_bg_description: str = "",
) -> Dict[str, Any]:
    """Generates a coordinated 1-to-3 Color Variant Nano Banana AI Slide Template Family with YPT/Zero-PII guardrails and FinOps gating."""
    import base64
    from PIL import ImageOps

    try:
        from src.security.spiffe_and_armor import sanitize_text_with_model_armor  # type: ignore
    except Exception:
        from src.agents.guardrails import sanitize_text_with_model_armor

    clean_name = str(family_name or "Custom Scouting Template").strip() or "Custom Scouting Template"
    clean_prompt = str(custom_prompt or "").strip()
    clean_bg_desc = str(custom_bg_description or "").strip()
    combined_input = f"{clean_name} {clean_prompt} {clean_bg_desc}".strip()

    # Step 1 — Model Armor & YPT / Zero-PII Guardrail Check
    raw_guardrail = sanitize_text_with_model_armor(combined_input)
    guardrail_res: Dict[str, Any] = dict(raw_guardrail) if isinstance(raw_guardrail, dict) else {"is_safe": True, "allowed": True}
    detected_violations: List[str] = list(guardrail_res.get("violations") or [])
    for v_code, pat in _TEMPLATE_YPT_AND_PII_PATTERNS:
        if pat.search(combined_input) and v_code not in detected_violations:
            detected_violations.append(v_code)

    is_safe = (
        bool(guardrail_res.get("is_safe", True))
        and bool(guardrail_res.get("allowed", True))
        and len(detected_violations) == 0
    )
    if not is_safe:
        block_msg = (
            guardrail_res.get("block_reason")
            or guardrail_res.get("remediation")
            or (
                "Blocked by Scouting America Youth Protection (YPT) & Zero-PII Model Armor Guardrail: "
                + ", ".join(detected_violations)
                if detected_violations
                else "Blocked by Scouting America Youth Protection (YPT) & Zero-PII Model Armor Guardrail."
            )
        )
        guardrail_res["is_safe"] = False
        guardrail_res["allowed"] = False
        guardrail_res["violations"] = detected_violations
        guardrail_res["block_reason"] = block_msg
        return {
            "status": "BLOCKED_BY_GUARDRAIL",
            "blocked": True,
            "guardrail": guardrail_res,
            "cost_usd": 0.0,
            "message": block_msg,
        }

    # Step 2 — FinOps Consent Check
    if not preview_only and not user_consented:
        return {
            "status": "CONSENT_REQUIRED",
            "requires_user_consent": True,
            "estimated_cost_usd": 0.08,
            "message": "User consent ($0.08 USD) is required before generating a Nano Banana AI template family.",
        }

    # Step 3 — Normalize Colors & Determine Active Variant Count (1, 2, or 3)
    cleaned_input_colors: List[str] = []
    for raw in colors or []:
        if raw and str(raw).strip():
            chx = _clean_hex_color(raw, "")
            if chx:
                cleaned_input_colors.append(chx)

    c1, c2, c3 = _normalize_three_variant_colors(cleaned_input_colors or None)
    c3_safe_primary = _ensure_wcag_aa_dark_hex(c3)

    # Determine how many variants are enabled (default 3 when colors is None or 3 colors given; 1 or 2 when fewer colors enabled)
    if cleaned_input_colors and len(cleaned_input_colors) in (1, 2):
        target_variant_count = len(cleaned_input_colors)
    else:
        target_variant_count = 3
        if include_secondary is False and include_accent is False:
            target_variant_count = 1
        elif include_secondary is False or include_accent is False:
            target_variant_count = 2

    style_key = str(visual_style or "pinewood_campfire").strip().lower()
    if style_key not in NANO_BANANA_TEMPLATE_VISUAL_STYLES:
        style_key = "pinewood_campfire"
    style_meta = NANO_BANANA_TEMPLATE_VISUAL_STYLES[style_key]

    geom_key = str(frame_geometry or "horizon_silhouette").strip().lower()
    if geom_key not in NANO_BANANA_FRAME_GEOMETRIES:
        geom_key = "horizon_silhouette"

    logo_pos = str(logo_position or "bottom_left").strip().lower()
    if logo_pos not in ("bottom_left", "bottom_right", "top_right", "cover_only"):
        logo_pos = "bottom_left"

    if not preview_only:
        existing_profiles = load_template_catalog()
        existing_family_names = {
            str(p.family_name or "").strip().lower()
            for p in existing_profiles
            if not p.is_builtin and str(p.family_name or "").strip()
        }
        existing_family_ids = {
            str(p.family_id or "").strip()
            for p in existing_profiles
            if not p.is_builtin and str(p.family_id or "").strip()
        }
        base_clean_name = re.sub(r"\s+#\d+$", "", clean_name).strip() or clean_name
        candidate_name = clean_name
        suffix_num = 2
        while (
            candidate_name.lower() in existing_family_names
            or f"nanobanana_tpl_{hashlib.sha256(f'{candidate_name}:{style_key}:{geom_key}:{c1}:{c2}:{c3}:{clean_prompt}:{logo_pos}'.encode('utf-8')).hexdigest()[:8]}"
            in existing_family_ids
        ):
            candidate_name = f"{base_clean_name} #{suffix_num}"
            suffix_num += 1
        clean_name = candidate_name

    short_hash = hashlib.sha256(
        f"{clean_name}:{style_key}:{geom_key}:{c1}:{c2}:{c3}:{clean_prompt}:{logo_pos}".encode("utf-8")
    ).hexdigest()[:8]
    family_id = f"nanobanana_tpl_{short_hash}"

    # Step 4 — Process Optional Uploaded Logo (`logo_data_url`)
    _ensure_dirs()
    processed_logo_img: Optional[Image.Image] = None
    logo_rel_url = ""
    if logo_data_url and str(logo_data_url).strip():
        raw_b64 = str(logo_data_url).strip()
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        try:
            logo_bytes = base64.b64decode(raw_b64)
            with Image.open(io.BytesIO(logo_bytes)) as lim:
                rgba = lim.convert("RGBA")
                if remove_logo_white_bg:
                    get_fn = getattr(rgba, "get_flattened_data", None) or rgba.getdata
                    pixels = list(get_fn())
                    cleaned_pixels = [
                        (255, 255, 255, 0) if (r > 238 and g > 238 and b > 238) else (r, g, b, a)
                        for (r, g, b, a) in pixels
                    ]
                    rgba.putdata(cleaned_pixels)
                rgba.thumbnail((240, 240), Image.Resampling.LANCZOS)
                processed_logo_img = rgba.copy()
                logo_out_path = CUSTOM_TEMPLATES_DIR / f"{family_id}_logo.png"
                processed_logo_img.save(logo_out_path)
                logo_rel_url = f"/assets/templates/custom/{logo_out_path.name}"
        except Exception:
            processed_logo_img = None
            logo_rel_url = ""

    # Step 5 — Synthesize Coordinated Header, Footer, Watermark & Cover Backdrop Assets Named by Closest Color
    all_swatches = [c1, c2, c3][:target_variant_count]
    color_names = get_disambiguated_color_names(all_swatches)
    raw_specs = [
        ("a", c1, c2, c1),
        ("b", c2, c3, c2),
        ("c", c3_safe_primary, c1, c3),
    ][:target_variant_count]
    variant_specs = [
        (slug, color_names[idx], pri, acc, sw)
        for idx, (slug, pri, acc, sw) in enumerate(raw_specs)
    ]

    safe_bounds = _compute_nano_template_safe_bounds(
        frame_geometry=geom_key,
        logo_position=logo_pos,
        has_logo=(processed_logo_img is not None),
    )

    uploaded_bg_path: Optional[Path] = None
    if custom_bg_data_url and str(custom_bg_data_url).strip():
        raw_bg_b64 = str(custom_bg_data_url).strip()
        if "," in raw_bg_b64:
            raw_bg_b64 = raw_bg_b64.split(",", 1)[1]
        try:
            bg_bytes = base64.b64decode(raw_bg_b64)
            with Image.open(io.BytesIO(bg_bytes)) as ubim:
                fitted_ub = ImageOps.fit(ubim.convert("RGB"), (1600, 900), method=Image.Resampling.LANCZOS)
                uploaded_bg_path = CUSTOM_TEMPLATES_DIR / f"{family_id}_uploaded_base_cover.jpg"
                fitted_ub.save(uploaded_bg_path, "JPEG", quality=92)
        except Exception:
            uploaded_bg_path = None

    family_base_cover = _resolve_nano_photorealistic_base_cover(
        visual_style=style_key,
        custom_prompt=clean_prompt or clean_bg_desc,
        family_id=family_id,
        allow_live_synthesis=(not preview_only),
        backdrop_id=backdrop_id,
        custom_bg_path=uploaded_bg_path,
    )

    built_profiles: List[TemplateProfile] = []
    for var_slug, var_label, pri_hex, acc_hex, swatch_hex in variant_specs:
        variant_id = f"{family_id}_{var_slug}"
        asset_urls = _render_nano_template_variant_assets(
            variant_id=variant_id,
            visual_style=style_key,
            frame_geometry=geom_key,
            primary_hex=pri_hex,
            accent_hex=acc_hex,
            logo_img=processed_logo_img,
            logo_position=logo_pos,
            custom_prompt=clean_prompt,
            base_cover_path=family_base_cover,
        )
        desc_parts = [
            f"Nano Banana AI {style_meta['label']} template ({var_label})",
            style_meta["description"],
        ]
        if clean_prompt:
            desc_parts.append(f"Theme focus: {clean_prompt}.")
        if clean_bg_desc:
            desc_parts.append(f"Backdrop: {clean_bg_desc}.")
        profile = TemplateProfile(
            template_id=variant_id,
            name=f"{clean_name} ({var_label})",
            category="Nano Banana AI Custom Series",
            family_id=family_id,
            family_name=clean_name,
            variant_color=var_label.lower(),
            variant_label=var_label,
            variant_swatch_hex=swatch_hex,
            description=" — ".join(desc_parts),
            is_builtin=False,
            pptx_path=f"assets/templates/custom/{variant_id}.pptx" if not preview_only else None,
            content_layout_index=6,
            cover_layout_index=0,
            use_native_master_layouts=False,
            primary_hex=pri_hex,
            accent_hex=acc_hex,
            card_bg_hex=_derive_soft_card_bg_hex(pri_hex),
            cover_bg_url=asset_urls["cover_bg_url"],
            canvas_watermark_url=asset_urls["canvas_watermark_url"],
            bottom_bar_hex=pri_hex,
            bottom_accent_hex=acc_hex,
            bottom_silhouette_url=asset_urls["bottom_silhouette_url"],
            bottom_silhouette_dark_url=asset_urls["bottom_silhouette_dark_url"],
            corner_logo_url=logo_rel_url if logo_pos == "bottom_right" else "",
            corner_logo_dark_url=logo_rel_url if logo_pos == "bottom_right" else "",
            top_banner_url=asset_urls["top_banner_url"],
            safe_bounds=safe_bounds.model_copy(deep=True),
        )
        if not preview_only:
            profile.pptx_path = _build_nano_template_master_pptx(profile)
        built_profiles.append(profile)

    if not preview_only:
        new_ids = {p.template_id for p in built_profiles}
        catalog = [p for p in load_template_catalog() if p.template_id not in new_ids]
        catalog.extend(built_profiles)
        save_template_catalog(catalog)

    return {
        "status": "SUCCESS",
        "family_id": family_id,
        "family_name": clean_name,
        "visual_style": style_key,
        "frame_geometry": geom_key,
        "backdrop_id": backdrop_id,
        "source_cover_file": family_base_cover.name,
        "preview_only": bool(preview_only),
        "cost_usd": 0.0 if preview_only else 0.08,
        "variant_count": len(built_profiles),
        "color_names": color_names,
        "variants": [p.to_dict() for p in built_profiles],
        "default_template_id": built_profiles[0].template_id,
    }
