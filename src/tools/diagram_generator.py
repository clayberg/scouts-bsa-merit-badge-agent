"""Tri-Modal Visual & Diagram Engine for Scouts BSA Merit Badge Presentations.

This module generates high-resolution, publication-grade pedagogical diagrams
in both crisp 220 DPI PNG and vector SVG formats using Matplotlib with the
official Scouts BSA brand palette and Material 3 Expressive visual tokens.

Supports:
1. 100% Backward-Compatible Legacy Diagram Generators:
   - generate_water_cycle_diagram / generate_cloud_types_diagram / generate_weather_front_diagram
   - generate_cpr_steps_diagram / generate_first_aid_cpr_diagram / generate_first_aid_bleeding_diagram
   - generate_leave_no_trace_diagram / generate_camping_tent_diagram
   - generate_myplate_cooking_diagram / generate_cooking_stove_diagram
   - generate_universal_badge_diagram
   - get_badge_diagram_path
2. Slide-Specific High-Craft Visual Generator (generate_slide_visual_asset):
   - Guaranteed unique filename per slide (.png + .svg) so no two slides share an image path.
   - 11 Specialized Hand-Made Counselor Visual Renderers:
     * triage_decision_tree
     * heat_comparison
     * cpr_aed_cycle
     * splinting_cms
     * first_aid_kit_grid
     * bearmuda_triangle
     * clothing_layering_3layer
     * stove_comparison
     * water_purification_pipeline
     * checks_balances_triangle
     * fourteenth_amendment_shield
   - Dynamic Data-Driven Archetype Renderers for all 12 slide archetypes using actual slide_data.
"""

import os
import re
import textwrap
from typing import Any, Dict, List, Optional, Tuple

# Ensure MPLCONFIGDIR is set BEFORE importing matplotlib so headless/sandboxed runs never hang or warn
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless/server execution
import matplotlib.patches as patches
import matplotlib.pyplot as plt

from src.config import ScoutsBSAPalette

DIAGRAMS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "assets", "diagrams")
)
os.makedirs(DIAGRAMS_DIR, exist_ok=True)

# Official Palette Shortcuts
NAVY = ScoutsBSAPalette.NAVY_BLUE_HEX          # #003F87
ACTION_BLUE = ScoutsBSAPalette.ACTION_BLUE_HEX # #005AE0
OLIVE = ScoutsBSAPalette.WARM_OLIVE_HEX        # #4B5320
RED = ScoutsBSAPalette.EAGLE_RED_HEX           # #CE1126
GOLD = ScoutsBSAPalette.EAGLE_GOLD_HEX         # #F4C430
SLATE = ScoutsBSAPalette.CRISP_SLATE_HEX       # #F2F4F7
SOFT_BLUE = ScoutsBSAPalette.SOFT_BLUE_CARD_HEX
SOFT_OLIVE = ScoutsBSAPalette.SOFT_OLIVE_CARD_HEX
SOFT_GOLD = ScoutsBSAPalette.SOFT_GOLD_CARD_HEX
SOFT_RED = ScoutsBSAPalette.SOFT_RED_CARD_HEX
DARK_TEXT = ScoutsBSAPalette.DARK_TEXT_HEX
MUTED_TEXT = ScoutsBSAPalette.MUTED_TEXT_HEX
BORDER_GRAY = ScoutsBSAPalette.BORDER_GRAY_HEX
WHITE = ScoutsBSAPalette.WHITE_HEX


# ==============================================================================
# INTERNAL HELPERS FOR CANVAS, TYPOGRAPHY & DATA EXTRACTION
# ==============================================================================

def _sanitize_slug(value: str, max_len: int = 40) -> str:
    """Converts an arbitrary string into a filesystem-safe lowercase identifier."""
    if not value:
        return "item"
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", str(value).strip().lower()).strip("_")
    return (cleaned[:max_len].strip("_")) or "item"


def _wrap(text: str, width: int = 32, max_lines: int = 4) -> str:
    """Wraps text cleanly without truncation ellipses to preserve readability."""
    if not text:
        return ""
    clean = re.sub(r"\s+", " ", str(text).strip())
    clean = re.sub(r"^[•\-\*]+\s*", "", clean)
    lines = textwrap.wrap(clean, width=width, break_long_words=False)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return "\n".join(lines)


def _create_canvas(
    title: str,
    subtitle: str = "",
    badge_tag: str = "SCOUTS BSA VISUAL GUIDE",
    bg_color: str = SLATE,
    header_color: str = NAVY,
) -> Tuple[plt.Figure, plt.Axes]:
    """Creates a standardized 16:10 high-craft diagram canvas (220 DPI) with header banner."""
    fig, ax = plt.subplots(figsize=(9.2, 5.6), dpi=220)
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # Outer subtle frame
    frame = patches.FancyBboxPatch(
        (0.8, 0.8), 98.4, 98.4,
        boxstyle="round,pad=0.3,rounding_size=1.5",
        facecolor=bg_color, edgecolor=BORDER_GRAY, lw=1.2
    )
    ax.add_patch(frame)

    # Top Navy/Brand Header Bar
    header_box = patches.FancyBboxPatch(
        (1.2, 87.5), 97.6, 11.0,
        boxstyle="round,pad=0.2,rounding_size=1.2",
        facecolor=header_color, edgecolor="none"
    )
    ax.add_patch(header_box)

    # Gold accent stripe under header
    gold_stripe = patches.Rectangle((1.2, 86.4), 97.6, 1.1, facecolor=GOLD, edgecolor="none")
    ax.add_patch(gold_stripe)

    # Badge pill in top-right of header
    pill = patches.FancyBboxPatch(
        (74.5, 92.2), 23.0, 4.8,
        boxstyle="round,pad=0.2,rounding_size=1.0",
        facecolor=GOLD, edgecolor="none"
    )
    ax.add_patch(pill)
    ax.text(
        86.0, 94.6, badge_tag[:26].upper(),
        fontsize=7.5, fontweight="bold", color=NAVY, ha="center", va="center"
    )

    # Title & Subtitle inside header
    clean_title = re.sub(r"\s+", " ", title.strip())
    if len(clean_title) > 66:
        clean_title = clean_title[:64].rstrip()
    ax.text(
        3.2, 94.5 if subtitle else 93.0, clean_title,
        fontsize=12.5, fontweight="bold", color=WHITE, ha="left", va="center"
    )
    if subtitle:
        clean_sub = re.sub(r"\s+", " ", subtitle.strip())
        if len(clean_sub) > 88:
            clean_sub = clean_sub[:86].rstrip()
        ax.text(
            3.2, 89.8, clean_sub,
            fontsize=8.8, color="#E2E8F0", ha="left", va="center"
        )

    return fig, ax


def _draw_card(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    header_text: str,
    body_text: str,
    accent_color: str = NAVY,
    fill_color: str = WHITE,
    header_height: float = 7.0,
    body_fontsize: float = 8.6,
    header_fontsize: float = 9.2,
    wrap_width: int = 30,
    max_lines: int = 5,
    header_text_color: str = WHITE,
) -> None:
    """Draws a Material 3 Expressive rounded card with a colored header band and wrapped body text."""
    card = patches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.2,rounding_size=1.4",
        facecolor=fill_color, edgecolor=accent_color, lw=1.8
    )
    ax.add_patch(card)

    hdr_y = y + h - header_height
    hdr = patches.FancyBboxPatch(
        (x, hdr_y), w, header_height,
        boxstyle="round,pad=0.1,rounding_size=1.2",
        facecolor=accent_color, edgecolor="none"
    )
    ax.add_patch(hdr)

    ax.text(
        x + w / 2.0, hdr_y + header_height / 2.0,
        header_text[:38],
        fontsize=header_fontsize, fontweight="bold",
        color=header_text_color, ha="center", va="center"
    )

    wrapped_body = _wrap(body_text, width=wrap_width, max_lines=max_lines)
    ax.text(
        x + w / 2.0, y + (h - header_height) / 2.0,
        wrapped_body,
        fontsize=body_fontsize, color=DARK_TEXT,
        ha="center", va="center", linespacing=1.32
    )


def _save_dual_assets(fig: plt.Figure, png_path: str, svg_path: Optional[str] = None) -> None:
    """Saves the Matplotlib figure as a 220 DPI PNG and optionally a vector SVG, then closes it."""
    os.makedirs(os.path.dirname(os.path.abspath(png_path)), exist_ok=True)
    fig.savefig(
        png_path,
        format="png",
        dpi=220,
        facecolor=fig.get_facecolor(),
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0.1,
    )
    if svg_path:
        os.makedirs(os.path.dirname(os.path.abspath(svg_path)), exist_ok=True)
        fig.savefig(
            svg_path,
            format="svg",
            facecolor=fig.get_facecolor(),
            edgecolor="none",
            bbox_inches="tight",
            pad_inches=0.1,
        )
    plt.close(fig)


def _split_anchor_and_body(raw_item: Any, idx: int = 1) -> Tuple[str, str]:
    """Extracts a (bold anchor header, detailed explanation) tuple from a string or dict."""
    if isinstance(raw_item, dict):
        anchor = (
            raw_item.get("anchor")
            or raw_item.get("title")
            or raw_item.get("header")
            or raw_item.get("label")
            or raw_item.get("name")
            or f"Step {idx}"
        )
        body = (
            raw_item.get("body")
            or raw_item.get("description")
            or raw_item.get("detail")
            or raw_item.get("text")
            or raw_item.get("value")
            or ""
        )
        return str(anchor).strip(), str(body).strip()

    text = re.sub(r"^[•\-\*]+\s*", "", str(raw_item or "").strip())
    if not text:
        return f"Key Point {idx}", "Review requirement standards with your counselor."
    if ":" in text:
        parts = text.split(":", 1)
        anchor = parts[0].strip().strip("*")
        body = parts[1].strip().strip("*")
        if anchor and body:
            return anchor[:34], body
    words = text.split()
    if len(words) <= 4:
        return text[:34], "Apply official Scouts BSA handbook procedures."
    anchor = " ".join(words[:3]).strip(".,;:*")
    body = " ".join(words[3:]).strip()
    return anchor[:34], body


def _extract_slide_pairs(
    slide_data: Optional[Dict[str, Any]],
    slide_title: str,
    badge_name: str,
    req_number: str,
    count: int = 4,
) -> List[Tuple[str, str]]:
    """Extracts up to `count` structured (header, body) pairs from slide_data with smart fallbacks."""
    data: Dict[str, Any] = {}
    if slide_data is not None:
        if isinstance(slide_data, dict):
            data = slide_data
        elif hasattr(slide_data, "model_dump"):
            data = slide_data.model_dump()
        elif hasattr(slide_data, "dict"):
            data = slide_data.dict()

    candidates: List[Any] = []
    for key in (
        "cards",
        "steps",
        "bullet_points",
        "points",
        "items",
        "gear_items",
        "checklist",
        "worked_example_fields",
        "fields",
    ):
        val = data.get(key)
        if isinstance(val, list) and val:
            candidates = val
            break
        elif isinstance(val, dict) and val:
            candidates = [{"title": k, "body": v} for k, v in val.items()]
            break

    if not candidates and isinstance(data.get("left_column"), list):
        candidates = data.get("left_column", []) + data.get("right_column", [])

    pairs: List[Tuple[str, str]] = []
    for i, item in enumerate(candidates[:count], start=1):
        pairs.append(_split_anchor_and_body(item, i))

    # Fill any remaining slots with meaningful requirement-grounded cards
    fallback_defaults = [
        (
            f"1. Requirement {req_number} Core",
            f"Master the foundational concepts for {slide_title or badge_name} using official BSA pamphlet guidance.",
        ),
        (
            "2. Safety & Risk Controls",
            "Follow Guide to Safe Scouting rules, Two-Deep Leadership, and the Buddy System during all activities.",
        ),
        (
            "3. Field Application",
            f"Demonstrate practical execution and explain key decision checkpoints for {badge_name} Req {req_number}.",
        ),
        (
            "4. Counselor Verification",
            "Review your completed examples, field observations, and safety checks with your Merit Badge Counselor.",
        ),
        (
            "5. Equipment Readiness",
            "Inspect all patrol and personal gear prior to departure to verify safe operating condition.",
        ),
        (
            "6. Leave No Trace & Ethics",
            "Practice Outdoor Code stewardship and leave every instructional area cleaner than you found it.",
        ),
    ]
    while len(pairs) < count:
        pairs.append(fallback_defaults[len(pairs) % len(fallback_defaults)])

    return pairs[:count]


# ==============================================================================
# 11 SPECIALIZED HAND-MADE COUNSELOR VISUAL RENDERERS (220 DPI PNG + SVG)
# ==============================================================================

def _render_triage_decision_tree(
    fig_title: str, badge_name: str, req_number: str
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders 4-Tier Emergency Triage Decision Flowchart (Red -> Yellow -> Green -> 911 Dispatch)."""
    fig, ax = _create_canvas(
        title=fig_title or "Emergency Triage Decision Tree & Mass Casualty Protocol",
        subtitle="Prioritize care rapidly by airway, severe bleeding, perfusion, and mental status",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    # Top Entry Node: Scene Safety & Size-Up
    top_node = patches.FancyBboxPatch(
        (20, 73.5), 60, 9.5,
        boxstyle="round,pad=0.2,rounding_size=1.4",
        facecolor=NAVY, edgecolor=GOLD, lw=2.2
    )
    ax.add_patch(top_node)
    ax.text(
        50, 79.6, "STEP 0: SCENE SAFETY, BSI GLOVES & RAPID TRIAGE SIZE-UP",
        fontsize=9.5, fontweight="bold", color=GOLD, ha="center", va="center"
    )
    ax.text(
        50, 75.8, "Survey hazards first -> Call out to walking wounded -> Assess Airway, Breathing, Circulation",
        fontsize=8.2, color=WHITE, ha="center", va="center"
    )

    # 4 Tier Cards across middle
    tiers = [
        (
            "IMMEDIATE [RED]",
            "TIER 1 • LIFE-THREATENING\n• Uncontrolled arterial bleeding\n• Airway obstruction / apnea\n• Severe shock or unresponsive\nACTION: Treat FIRST now!",
            RED,
            SOFT_RED,
            2.5,
        ),
        (
            "DELAYED [YELLOW]",
            "TIER 2 • URGENT CARE\n• Stable bone fractures\n• Controlled moderate bleeding\n• Back/extremity injuries\nACTION: Monitor & treat 2nd",
            GOLD,
            SOFT_GOLD,
            26.8,
        ),
        (
            "MINIMAL [GREEN]",
            "TIER 3 • WALKING WOUNDED\n• Minor scrapes & abrasions\n• Mild sprains & bruises\n• Alert, oriented, ambulatory\nACTION: Buddy self-aid zone",
            OLIVE,
            SOFT_OLIVE,
            51.1,
        ),
        (
            "SIGNALS & 911 DISPATCH",
            "TIER 4 • EMS COORDINATION\n• Dial 911 / activate SOS beacon\n• Give exact GPS / trailhead\n• Report patient count by tier\nACTION: Station trail runner",
            ACTION_BLUE,
            SOFT_BLUE,
            75.4,
        ),
    ]

    for hdr, body, color, fill, x in tiers:
        hdr_txt_color = DARK_TEXT if color == GOLD else WHITE
        _draw_card(
            ax, x, 22.0, 22.1, 43.5,
            header_text=hdr,
            body_text=body,
            accent_color=color,
            fill_color=fill,
            header_height=8.0,
            body_fontsize=8.1,
            header_fontsize=8.5,
            wrap_width=26,
            max_lines=7,
            header_text_color=hdr_txt_color,
        )
        # Arrow from top bar down to tier card
        cx = x + 11.05
        ax.annotate(
            "", xy=(cx, 66.0), xytext=(cx, 73.2),
            arrowprops=dict(arrowstyle="-|>", lw=2.2, color=color)
        )

    # Horizontal progression arrows between tiers
    for x_left in (24.6, 48.9, 73.2):
        ax.annotate(
            "", xy=(x_left + 2.1, 43.5), xytext=(x_left, 43.5),
            arrowprops=dict(arrowstyle="-|>", lw=2.0, color=NAVY)
        )

    # Bottom Re-Evaluation Banner
    footer = patches.FancyBboxPatch(
        (2.5, 4.5), 95.0, 12.5,
        boxstyle="round,pad=0.2,rounding_size=1.2",
        facecolor=WHITE, edgecolor=NAVY, lw=1.8
    )
    ax.add_patch(footer)
    ax.text(
        50, 12.8, "CONTINUOUS RE-TRIAGE RULE: RE-ASSESS EVERY 5–15 MINUTES UNTIL EMS ARRIVES",
        fontsize=9.2, fontweight="bold", color=RED, ha="center", va="center"
    )
    ax.text(
        50, 7.8, "A Delayed [YELLOW] patient can rapidly deteriorate into Immediate [RED] if internal bleeding or shock progresses.",
        fontsize=8.4, color=DARK_TEXT, ha="center", va="center"
    )
    return fig, ax


def _render_heat_comparison(
    fig_title: str, badge_name: str, req_number: str
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders Split-Screen Differential Diagram comparing Heat Exhaustion vs. Heat Stroke (911)."""
    fig, ax = _create_canvas(
        title=fig_title or "Heat Exhaustion vs. Heat Stroke: Differential Field Triage",
        subtitle="Distinguish moderate fluid/electrolyte depletion from life-threatening thermoregulatory failure",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    # Left Column: Heat Exhaustion
    left_box = patches.FancyBboxPatch(
        (2.5, 14.0), 43.5, 69.5,
        boxstyle="round,pad=0.2,rounding_size=1.5",
        facecolor=SOFT_BLUE, edgecolor=ACTION_BLUE, lw=2.2
    )
    ax.add_patch(left_box)
    left_hdr = patches.FancyBboxPatch(
        (2.5, 74.0), 43.5, 9.5,
        boxstyle="round,pad=0.1,rounding_size=1.2",
        facecolor=ACTION_BLUE, edgecolor="none"
    )
    ax.add_patch(left_hdr)
    ax.text(24.25, 79.8, "HEAT EXHAUSTION", fontsize=11.0, fontweight="bold", color=WHITE, ha="center")
    ax.text(24.25, 76.0, "MODERATE URGENCY • COOL & REHYDRATE", fontsize=8.0, fontweight="bold", color=GOLD, ha="center")

    exhaustion_rows = [
        ("SKIN & SWEATING", "Cool, pale, moist, and clammy skin with heavy, profuse sweating."),
        ("CORE & VITALS", "Core temp <104°F (38–40°C); fast weak pulse; dizziness, nausea, headache."),
        ("MENTAL STATUS", "Alert and oriented (may feel fatigued, weak, or irritable, but coherent)."),
        ("FIELD TREATMENT", "Move to shade/A/C, loosen clothing, apply cool wet cloths, sip cool water slowly, elevate legs 6–12 in."),
    ]
    for idx, (label, desc) in enumerate(exhaustion_rows):
        ry = 59.0 - idx * 14.2
        row_card = patches.FancyBboxPatch(
            (4.5, ry), 39.5, 12.2,
            boxstyle="round,pad=0.15,rounding_size=1.0",
            facecolor=WHITE, edgecolor=ACTION_BLUE, lw=1.2
        )
        ax.add_patch(row_card)
        ax.text(6.0, ry + 9.2, label, fontsize=8.3, fontweight="bold", color=ACTION_BLUE, ha="left")
        ax.text(6.0, ry + 4.2, _wrap(desc, width=44, max_lines=2), fontsize=8.0, color=DARK_TEXT, ha="left", va="center")

    # Center VS Pill
    vs_circle = patches.Circle((50.0, 48.5), 4.2, facecolor=GOLD, edgecolor=NAVY, lw=2.2, zorder=5)
    ax.add_patch(vs_circle)
    ax.text(50.0, 48.5, "VS", fontsize=10.5, fontweight="bold", color=NAVY, ha="center", va="center", zorder=6)

    # Right Column: Heat Stroke
    right_box = patches.FancyBboxPatch(
        (54.0, 14.0), 43.5, 69.5,
        boxstyle="round,pad=0.2,rounding_size=1.5",
        facecolor=SOFT_RED, edgecolor=RED, lw=2.4
    )
    ax.add_patch(right_box)
    right_hdr = patches.FancyBboxPatch(
        (54.0, 74.0), 43.5, 9.5,
        boxstyle="round,pad=0.1,rounding_size=1.2",
        facecolor=RED, edgecolor="none"
    )
    ax.add_patch(right_hdr)
    ax.text(75.75, 79.8, "HEAT STROKE — 911 EMERGENCY", fontsize=10.8, fontweight="bold", color=WHITE, ha="center")
    ax.text(75.75, 76.0, "LIFE-THREATENING • RAPID COOLING NOW", fontsize=8.0, fontweight="bold", color=GOLD, ha="center")

    stroke_rows = [
        ("SKIN & SWEATING", "Hot, flushed red skin (dry OR damp from exertion); thermoregulation has failed."),
        ("CORE & VITALS", "Core body temp >104°F (40°C+); rapid, strong bounding pulse; noisy breathing."),
        ("MENTAL STATUS", "ALTERED MENTAL STATE: Confusion, slurred speech, ataxia, seizures, or unconsciousness."),
        ("FIELD TREATMENT", "CALL 911 IMMEDIATELY! Rapid cooling via cold water immersion or ice packs at neck, armpits & groin. NO fluids by mouth."),
    ]
    for idx, (label, desc) in enumerate(stroke_rows):
        ry = 59.0 - idx * 14.2
        row_card = patches.FancyBboxPatch(
            (56.0, ry), 39.5, 12.2,
            boxstyle="round,pad=0.15,rounding_size=1.0",
            facecolor=WHITE, edgecolor=RED, lw=1.3
        )
        ax.add_patch(row_card)
        ax.text(57.5, ry + 9.2, label, fontsize=8.3, fontweight="bold", color=RED, ha="left")
        ax.text(57.5, ry + 4.2, _wrap(desc, width=44, max_lines=2), fontsize=8.0, color=DARK_TEXT, ha="left", va="center")

    # Bottom Rule Bar
    rule_bar = patches.FancyBboxPatch(
        (2.5, 3.2), 95.0, 8.2,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=NAVY, edgecolor="none"
    )
    ax.add_patch(rule_bar)
    ax.text(
        50.0, 7.3,
        "COUNSELOR KEY: Any change in mental status (confusion, disorientation, unresponsiveness) = HEAT STROKE -> Call 911 & cool first!",
        fontsize=8.5, fontweight="bold", color=GOLD, ha="center", va="center"
    )
    return fig, ax


def _render_cpr_aed_cycle(
    fig_title: str, badge_name: str, req_number: str
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders High-Detail CPR 30:2 Compression-to-Breath Cycle & AED Pad Placement Diagram."""
    fig, ax = _create_canvas(
        title=fig_title or "CPR 30:2 Resuscitation Cycle & AED Pad Placement",
        subtitle="High-quality chest compressions (100–120 BPM, 2+ in depth) paired with rapid defibrillation",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    # Left Panel: 4-Stage 30:2 Cycle
    cycle_cards = [
        (
            "1. SCENE SAFETY & CHECK",
            "Verify hazard-free scene. Put on PPE gloves. Tap shoulder & shout 'Are you OK?' Check breathing (<=10s).",
            NAVY,
            SOFT_BLUE,
            3.0,
            49.0,
        ),
        (
            "2. CALL 911 & GET AED",
            "Point to a specific buddy: 'You call 911 and bring the AED now!' Place victim flat on firm surface.",
            ACTION_BLUE,
            SOFT_BLUE,
            32.0,
            49.0,
        ),
        (
            "3. 30 COMPRESSIONS",
            "Heel of hand on center of chest (lower sternum). Push hard & fast: 100–120 BPM, >=2 inches deep, full recoil.",
            RED,
            SOFT_RED,
            32.0,
            15.0,
        ),
        (
            "4. 2 RESCUE BREATHS",
            "Head-tilt / chin-lift airway, pinch nose, give 2 breaths (1 sec each, watch chest rise). Repeat 30:2 cycle!",
            OLIVE,
            SOFT_OLIVE,
            3.0,
            15.0,
        ),
    ]
    for hdr, body, color, fill, x, y in cycle_cards:
        _draw_card(
            ax, x, y, 25.5, 29.5,
            header_text=hdr,
            body_text=body,
            accent_color=color,
            fill_color=fill,
            header_height=6.8,
            body_fontsize=8.0,
            header_fontsize=8.4,
            wrap_width=27,
            max_lines=5,
        )

    # Cycle Arrows between the 4 cards (clockwise loop)
    ax.annotate("", xy=(31.8, 63.5), xytext=(28.7, 63.5), arrowprops=dict(arrowstyle="-|>", lw=2.4, color=NAVY))
    ax.annotate("", xy=(44.8, 44.8), xytext=(44.8, 48.8), arrowprops=dict(arrowstyle="-|>", lw=2.4, color=RED))
    ax.annotate("", xy=(28.7, 29.5), xytext=(31.8, 29.5), arrowprops=dict(arrowstyle="-|>", lw=2.4, color=OLIVE))
    ax.annotate("", xy=(15.8, 48.8), xytext=(15.8, 44.8), arrowprops=dict(arrowstyle="-|>", lw=2.4, color=NAVY))

    # Center 30:2 Badge
    badge_30_2 = patches.FancyBboxPatch(
        (23.2, 43.5), 14.0, 6.5,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=GOLD, edgecolor=NAVY, lw=2.0, zorder=5
    )
    ax.add_patch(badge_30_2)
    ax.text(30.2, 46.75, "30 : 2 LOOP", fontsize=8.8, fontweight="bold", color=NAVY, ha="center", va="center", zorder=6)

    # Right Panel: AED Pad Placement Diagram
    aed_panel = patches.FancyBboxPatch(
        (61.0, 15.0), 36.5, 63.5,
        boxstyle="round,pad=0.2,rounding_size=1.5",
        facecolor=WHITE, edgecolor=NAVY, lw=2.0
    )
    ax.add_patch(aed_panel)
    aed_hdr = patches.FancyBboxPatch(
        (61.0, 71.0), 36.5, 7.5,
        boxstyle="round,pad=0.1,rounding_size=1.2",
        facecolor=NAVY, edgecolor="none"
    )
    ax.add_patch(aed_hdr)
    ax.text(79.25, 74.75, "ANTERIOR-LATERAL AED PAD MAP", fontsize=9.2, fontweight="bold", color=GOLD, ha="center", va="center")

    # Stylized Torso Silhouette
    torso = patches.FancyBboxPatch(
        (70.5, 31.0), 17.5, 29.0,
        boxstyle="round,pad=0.2,rounding_size=3.0",
        facecolor="#F8FAFC", edgecolor=MUTED_TEXT, lw=1.8
    )
    ax.add_patch(torso)
    head = patches.Circle((79.25, 64.5), 3.6, facecolor="#F8FAFC", edgecolor=MUTED_TEXT, lw=1.8)
    ax.add_patch(head)

    # Pad 1: Upper-Right Chest (viewer's left side of torso)
    pad1 = patches.FancyBboxPatch(
        (72.0, 50.0), 5.5, 6.8,
        boxstyle="round,pad=0.1,rounding_size=0.8",
        facecolor=RED, edgecolor=WHITE, lw=1.5
    )
    ax.add_patch(pad1)
    ax.text(74.75, 53.4, "PAD 1\nUpper\nRight", fontsize=6.8, fontweight="bold", color=WHITE, ha="center", va="center")

    # Pad 2: Lower-Left Ribs (viewer's right-lower side of torso)
    pad2 = patches.FancyBboxPatch(
        (81.2, 35.5), 5.5, 6.8,
        boxstyle="round,pad=0.1,rounding_size=0.8",
        facecolor=ACTION_BLUE, edgecolor=WHITE, lw=1.5
    )
    ax.add_patch(pad2)
    ax.text(83.95, 38.9, "PAD 2\nLower\nLeft", fontsize=6.8, fontweight="bold", color=WHITE, ha="center", va="center")

    # Electrical Vector across Heart
    ax.annotate(
        "", xy=(81.2, 40.5), xytext=(77.2, 51.0),
        arrowprops=dict(arrowstyle="<->", lw=2.2, ls="--", color=GOLD)
    )
    ax.text(79.25, 46.2, "HEART\nVECTOR", fontsize=6.8, fontweight="bold", color=RED, ha="center", va="center")

    # Pad placement callout text
    ax.text(
        79.25, 24.8,
        "• Pad 1: Upper-right chest below collarbone\n• Pad 2: Lower-left ribs below armpit\n• Bare, dry chest; shout 'CLEAR!' before shock",
        fontsize=7.8, color=DARK_TEXT, ha="center", va="center", linespacing=1.3
    )

    # Bottom Banner
    bot = patches.FancyBboxPatch(
        (3.0, 3.5), 94.5, 8.2,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=RED, edgecolor="none"
    )
    ax.add_patch(bot)
    ax.text(
        50.25, 7.6,
        "CRITICAL: Minimize interruptions (<10s) -> Resume 30:2 compressions IMMEDIATELY after AED shock or 'No Shock Advised'!",
        fontsize=8.3, fontweight="bold", color=WHITE, ha="center", va="center"
    )
    return fig, ax


def _render_splinting_cms(
    fig_title: str, badge_name: str, req_number: str
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders Anatomical Splinting & Distal CMS Check 4-Step Diagram."""
    fig, ax = _create_canvas(
        title=fig_title or "Anatomical Splinting & Distal C-M-S Verification Protocol",
        subtitle="Immobilize the joint above and joint below the injury while preserving distal neurovascular perfusion",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    # Top Schematic: Splinted Forearm / Lower Leg Anatomy
    schem = patches.FancyBboxPatch(
        (3.0, 50.5), 94.0, 32.5,
        boxstyle="round,pad=0.2,rounding_size=1.4",
        facecolor=WHITE, edgecolor=NAVY, lw=1.8
    )
    ax.add_patch(schem)
    ax.text(
        50.0, 79.5, "ANATOMICAL SPLINT CROSS-SECTION: IMMOBILIZE JOINT ABOVE & JOINT BELOW",
        fontsize=9.2, fontweight="bold", color=NAVY, ha="center", va="center"
    )

    # Upper & Lower Padded Splint Boards
    top_board = patches.FancyBboxPatch((12.0, 71.0), 62.0, 3.6, boxstyle="round,pad=0.1", facecolor=OLIVE, edgecolor=NAVY, lw=1.4)
    bot_board = patches.FancyBboxPatch((12.0, 55.0), 62.0, 3.6, boxstyle="round,pad=0.1", facecolor=OLIVE, edgecolor=NAVY, lw=1.4)
    ax.add_patch(top_board)
    ax.add_patch(bot_board)
    ax.text(43.0, 72.8, "RIGID SPLINT BOARD + SOFT FOAM/CLOTH PADDING", fontsize=7.5, fontweight="bold", color=WHITE, ha="center", va="center")
    ax.text(43.0, 56.8, "SUPPORT SPLINT BOARD (SPANS FULL LIMB SEGMENT)", fontsize=7.5, fontweight="bold", color=WHITE, ha="center", va="center")

    # Limb shaft in middle
    limb = patches.FancyBboxPatch((14.0, 60.5), 58.0, 8.5, boxstyle="round,pad=0.1", facecolor=SOFT_GOLD, edgecolor=GOLD, lw=1.8)
    ax.add_patch(limb)

    # Proximal Joint, Fracture Zone, Distal Joint badges
    j_prox = patches.Circle((20.0, 64.75), 3.4, facecolor=ACTION_BLUE, edgecolor=WHITE, lw=1.5)
    j_dist = patches.Circle((66.0, 64.75), 3.4, facecolor=ACTION_BLUE, edgecolor=WHITE, lw=1.5)
    ax.add_patch(j_prox)
    ax.add_patch(j_dist)
    ax.text(20.0, 64.75, "JOINT\nABOVE", fontsize=6.5, fontweight="bold", color=WHITE, ha="center", va="center")
    ax.text(66.0, 64.75, "JOINT\nBELOW", fontsize=6.5, fontweight="bold", color=WHITE, ha="center", va="center")

    # Fracture site in center
    fx_box = patches.FancyBboxPatch((37.0, 61.5), 12.0, 6.5, boxstyle="round,pad=0.1", facecolor=RED, edgecolor=WHITE, lw=1.5)
    ax.add_patch(fx_box)
    ax.text(43.0, 64.75, "INJURY SITE\n(DO NOT TIE)", fontsize=6.8, fontweight="bold", color=WHITE, ha="center", va="center")

    # Cravat ties on either side of injury (never directly over fracture)
    for tx in (27.5, 32.5, 53.0, 58.0):
        tie = patches.Rectangle((tx, 54.4), 2.2, 20.8, facecolor=NAVY, alpha=0.85)
        ax.add_patch(tie)

    # Distal C-M-S Check Callout Box on Right
    cms_box = patches.FancyBboxPatch(
        (76.5, 53.5), 18.5, 23.0,
        boxstyle="round,pad=0.15,rounding_size=1.2",
        facecolor=SOFT_RED, edgecolor=RED, lw=2.0
    )
    ax.add_patch(cms_box)
    ax.text(85.75, 73.0, "DISTAL C-M-S", fontsize=8.8, fontweight="bold", color=RED, ha="center")
    ax.text(
        85.75, 62.5,
        "• C: Cap refill <2s\n  & warm pulse\n• M: Wiggle digits\n• S: Can feel touch\nCheck BEFORE &\nAFTER splinting!",
        fontsize=7.6, color=DARK_TEXT, ha="center", va="center", linespacing=1.28
    )

    # Bottom 4 Sequential Step Cards
    steps = [
        (
            "1. MANUAL STABILIZATION",
            "Support limb above and below injury in the exact position found. Never try to straighten an angulated bone.",
            NAVY,
            SOFT_BLUE,
            2.5,
        ),
        (
            "2. PRE-SPLINT C-M-S",
            "Check distal Circulation (pulse & <2s capillary refill), Motor (wiggle fingers/toes), and Sensation before tying.",
            ACTION_BLUE,
            SOFT_BLUE,
            26.8,
        ),
        (
            "3. PAD & IMMOBILIZE",
            "Pad natural hollows. Immobilize both the joint above and joint below using cravats tied away from injury.",
            OLIVE,
            SOFT_OLIVE,
            51.1,
        ),
        (
            "4. RE-VERIFY C-M-S",
            "Re-check distal pulse and capillary refill (<2s) immediately after tying. Loosen ties if digits turn pale or numb.",
            RED,
            SOFT_RED,
            75.4,
        ),
    ]
    for hdr, body, color, fill, x in steps:
        _draw_card(
            ax, x, 5.0, 22.1, 41.0,
            header_text=hdr,
            body_text=body,
            accent_color=color,
            fill_color=fill,
            header_height=7.5,
            body_fontsize=8.0,
            header_fontsize=8.2,
            wrap_width=25,
            max_lines=6,
        )
    return fig, ax


def _render_first_aid_kit_grid(
    fig_title: str, badge_name: str, req_number: str
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders 21-Item Personal & Patrol First Aid Kit Knolling Grid (4 Color-Coded Quadrants)."""
    fig, ax = _create_canvas(
        title=fig_title or "21-Item Personal & Patrol First Aid Kit Knolling Layout",
        subtitle="Organized into 4 rapid-access modular compartments for trail and camp readiness",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    quadrants = [
        (
            "1. WOUND CARE & GAUZE (7 ITEMS)",
            "• Assorted Adhesive Bandages (6+)\n• Sterile Gauze Pads (3x3 & 4x4 in)\n• Roller Gauze Bandage (2 in)\n• Waterproof Adhesive Medical Tape\n• Moleskin / Blister Hydrocolloid Pads\n• Triangular Bandages / Cravats (2)\n• Elastic Support Wrap (ACE 3 in)",
            NAVY,
            SOFT_BLUE,
            2.5,
            46.5,
        ),
        (
            "2. PPE & BARRIER PROTECTION (4 ITEMS)",
            "• Nitrile Exam Gloves (2+ Pairs, Non-Latex)\n• CPR Resuscitation Mask / One-Way Valve\n• Alcohol-Based Hand Sanitizer Gel\n• Resealable Biohazard Waste Bags\n  (Protect rescuer & patient from bloodborne pathogens under BSI rules)",
            ACTION_BLUE,
            SOFT_BLUE,
            51.0,
            46.5,
        ),
        (
            "3. MEDICATIONS & TOPICALS (5 ITEMS)",
            "• Antiseptic Cleansing Wipes (BZK)\n• Triple Antibiotic Ointment Packets\n• Hydrocortisone Anti-Itch Cream (1%)\n• Aloe Vera / Water-Jel Burn Packets\n• Oral Electrolytes, Antihistamine & Pain Reliever (with parent permission)",
            OLIVE,
            SOFT_OLIVE,
            2.5,
            10.5,
        ),
        (
            "4. SPLINTING, SHEARS & EMERGENCY (5 ITEMS)",
            "• SAM Roll / Moldable Foam-Wire Splint\n• Blunt-Tip Paramedic Trauma Shears\n• Fine-Point Splinter/Tick Tweezers\n• Space / Mylar Emergency Thermal Blanket\n• Waterproof First Aid Guide, SOAP Note Card & Pencil",
            RED,
            SOFT_RED,
            51.0,
            10.5,
        ),
    ]

    for hdr, body, color, fill, x, y in quadrants:
        _draw_card(
            ax, x, y, 46.5, 34.5,
            header_text=hdr,
            body_text=body,
            accent_color=color,
            fill_color=fill,
            header_height=6.8,
            body_fontsize=8.0,
            header_fontsize=8.8,
            wrap_width=48,
            max_lines=7,
        )

    # Inspection Footer
    footer = patches.FancyBboxPatch(
        (2.5, 2.2), 95.0, 6.5,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=GOLD, edgecolor=NAVY, lw=1.5
    )
    ax.add_patch(footer)
    ax.text(
        50.0, 5.45,
        "PRE-TRIP INSPECTION RULE: Check expiration dates, replace torn sterile wrappers, and restock used items before every campout!",
        fontsize=8.4, fontweight="bold", color=NAVY, ha="center", va="center"
    )
    return fig, ax


def _render_bearmuda_triangle(
    fig_title: str, badge_name: str, req_number: str
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders The 'Bear'-muda Triangle 200-Foot Backcountry Camp Layout Spatial Diagram."""
    fig, ax = _create_canvas(
        title=fig_title or "The 'Bear'-muda Triangle: 200-Foot Backcountry Camp Layout",
        subtitle="Isolate sleeping tents upwind from cooking and smellable storage by 200 feet (70 adult paces)",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=OLIVE,
    )

    # Prevailing Wind Indicator on Left
    wind_box = patches.FancyBboxPatch(
        (2.5, 69.0), 23.0, 13.5,
        boxstyle="round,pad=0.15,rounding_size=1.2",
        facecolor=SOFT_BLUE, edgecolor=ACTION_BLUE, lw=1.8
    )
    ax.add_patch(wind_box)
    ax.text(14.0, 79.2, "PREVAILING WIND", fontsize=8.5, fontweight="bold", color=ACTION_BLUE, ha="center")
    ax.annotate("", xy=(23.5, 74.5), xytext=(4.5, 74.5), arrowprops=dict(arrowstyle="-|>", lw=2.8, color=ACTION_BLUE))
    ax.text(14.0, 71.2, "Blows odors DOWNWIND\naway from tents", fontsize=7.5, color=DARK_TEXT, ha="center", va="center")

    # Water Source Stream along bottom-left
    water_box = patches.FancyBboxPatch(
        (2.5, 12.0), 23.0, 16.0,
        boxstyle="round,pad=0.15,rounding_size=1.2",
        facecolor="#D6E3FF", edgecolor=NAVY, lw=1.8
    )
    ax.add_patch(water_box)
    ax.text(14.0, 23.8, "LAKE / STREAM", fontsize=8.8, fontweight="bold", color=NAVY, ha="center")
    ax.text(
        14.0, 17.2,
        ">= 200 FT BUFFER\nCamp, wash & dig\ncatholes >=200 ft\nfrom all water!",
        fontsize=7.5, color=DARK_TEXT, ha="center", va="center"
    )

    # Triangle Edges (dashed olive/red safety lines)
    ax.plot([39, 83], [71, 71], ls="--", lw=2.5, color=NAVY, zorder=2)
    ax.plot([39, 60], [71, 21], ls="--", lw=2.5, color=ACTION_BLUE, zorder=2)
    ax.plot([60, 83], [21, 71], ls="--", lw=2.5, color=RED, zorder=2)

    # Distance Labels on Triangle Sides
    ax.text(61.0, 74.0, "<--- 200 FEET (70 ADULT PACES) --->", fontsize=8.0, fontweight="bold", color=NAVY, ha="center",
            bbox=dict(boxstyle="round,pad=0.2", facecolor=WHITE, edgecolor=NAVY, lw=1.2))
    ax.text(43.5, 44.0, "200 FT\nUPWIND", fontsize=7.8, fontweight="bold", color=ACTION_BLUE, ha="center",
            bbox=dict(boxstyle="round,pad=0.2", facecolor=WHITE, edgecolor=ACTION_BLUE, lw=1.2))
    ax.text(77.5, 44.0, "200 FT\nFROM KITCHEN", fontsize=7.8, fontweight="bold", color=RED, ha="center",
            bbox=dict(boxstyle="round,pad=0.2", facecolor=WHITE, edgecolor=RED, lw=1.2))

    # Center Warning Badge inside Triangle
    ax.text(
        61.0, 52.5,
        "BEAR-MUDA\nSAFETY ZONE\nZero food odors\nin sleeping area",
        fontsize=7.8, fontweight="bold", color=RED, ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.3", facecolor=SOFT_RED, edgecolor=RED, lw=1.5)
    )

    # Vertex 1: Tent / Sleeping Zone (Upwind)
    _draw_card(
        ax, 27.5, 62.0, 25.0, 21.0,
        header_text="1. SLEEPING TENTS (UPWIND)",
        body_text="• 200 ft upwind of kitchen\n• ZERO food, wrappers, gum, deodorant, or toothpaste\n• Sleep in clean clothes",
        accent_color=NAVY,
        fill_color=SOFT_BLUE,
        header_height=5.5,
        body_fontsize=7.6,
        header_fontsize=8.0,
        wrap_width=28,
        max_lines=4,
    )

    # Vertex 2: Cooking & 3-Pot Dishwashing Station (Downwind)
    _draw_card(
        ax, 46.0, 11.5, 30.0, 21.5,
        header_text="2. KITCHEN & 3-POT WASH",
        body_text="• 200 ft downwind of tents\n• >=200 ft from water source\n• Strain food bits into trash; scatter greywater 200 ft out",
        accent_color=ACTION_BLUE,
        fill_color=WHITE,
        header_height=5.5,
        body_fontsize=7.6,
        header_fontsize=8.0,
        wrap_width=32,
        max_lines=4,
    )

    # Vertex 3: Bear Hang / Canister Zone (Downwind)
    _draw_card(
        ax, 72.5, 62.0, 25.0, 21.0,
        header_text="3. BEAR HANG / CANISTER",
        body_text="• 12 ft high off ground\n• 6 ft out from tree trunk\n• 10 ft below branch\n• All food, trash & smellables",
        accent_color=RED,
        fill_color=SOFT_RED,
        header_height=5.5,
        body_fontsize=7.6,
        header_fontsize=8.0,
        wrap_width=28,
        max_lines=4,
    )

    # Bottom Summary Bar
    bot = patches.FancyBboxPatch(
        (2.5, 2.5), 95.0, 6.8,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=NAVY, edgecolor="none"
    )
    ax.add_patch(bot)
    ax.text(
        50.0, 5.9,
        "SMELLABLES RULE: Food, trash, soap, toothpaste, lip balm, sunscreen, and fuel bottles ALWAYS go in the Bear Hang/Canister at night!",
        fontsize=8.2, fontweight="bold", color=GOLD, ha="center", va="center"
    )
    return fig, ax


def _render_clothing_layering_3layer(
    fig_title: str, badge_name: str, req_number: str
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders 3-Layer Cold-Weather Clothing Cutaway ('Why Cotton Kills')."""
    fig, ax = _create_canvas(
        title=fig_title or "3-Layer Cold-Weather Clothing Cutaway & Why Cotton Kills",
        subtitle="Manage internal sweat moisture and external wind/precipitation through modular technical layers",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    # Body Skin Core Strip on Far Left
    skin_box = patches.FancyBboxPatch(
        (2.5, 19.0), 11.5, 64.0,
        boxstyle="round,pad=0.15,rounding_size=1.2",
        facecolor="#FDE68A", edgecolor=GOLD, lw=2.0
    )
    ax.add_patch(skin_box)
    ax.text(8.25, 51.0, "WARM\nBODY\nCORE\n\n98.6°F\n(37°C)\n\nSweat\nVapor\nSource", fontsize=8.5, fontweight="bold", color=DARK_TEXT, ha="center", va="center")

    # 3 Cutaway Layers
    layers = [
        (
            "LAYER 1: WICKING BASE",
            "NEXT-TO-SKIN MOISTURE CONTROL\n\n• Material: Merino Wool or Synthetic (Polyester/Polypropylene)\n• Physics: Capillary wicking pulls liquid sweat off skin so it cannot chill your core during rest stops\n• Fit: Snug against skin",
            ACTION_BLUE,
            SOFT_BLUE,
            16.5,
            WHITE,
        ),
        (
            "LAYER 2: LOFT INSULATION",
            "DEAD-AIR THERMAL RETENTION\n\n• Material: Fleece (100–300 wt), Down, or Synthetic Puffy Jacket\n• Physics: Traps warm dead-air pockets heated by your body\n• Action: Vent or shed Layer 2 BEFORE you start sweating uphill!",
            GOLD,
            SOFT_GOLD,
            44.0,
            DARK_TEXT,
        ),
        (
            "LAYER 3: WEATHER SHELL",
            "WINDPROOF & WATERPROOF SHIELD\n\n• Material: Breathable Microporous Membrane (Gore-Tex / Coated Nylon)\n• Physics: Blocks convective windchill and rain/snow while allowing internal water vapor to escape\n• Features: Pit zips & storm hood",
            NAVY,
            WHITE,
            71.5,
            WHITE,
        ),
    ]

    for hdr, body, color, fill, x, hdr_txt in layers:
        _draw_card(
            ax, x, 19.0, 25.5, 64.0,
            header_text=hdr,
            body_text=body,
            accent_color=color,
            fill_color=fill,
            header_height=8.0,
            body_fontsize=8.1,
            header_fontsize=8.5,
            wrap_width=28,
            max_lines=10,
            header_text_color=hdr_txt,
        )

    # Moisture Wicking Arrows going outward (Left -> Right)
    for ax_x in (14.2, 41.8, 69.2):
        ax.annotate(
            "", xy=(ax_x + 2.2, 51.0), xytext=(ax_x, 51.0),
            arrowprops=dict(arrowstyle="-|>", lw=2.4, color=ACTION_BLUE)
        )

    # Bottom Eagle Red Warning Banner: Why Cotton Kills
    cotton_bar = patches.FancyBboxPatch(
        (2.5, 3.0), 94.5, 13.0,
        boxstyle="round,pad=0.2,rounding_size=1.2",
        facecolor=RED, edgecolor="none"
    )
    ax.add_patch(cotton_bar)
    ax.text(
        50.0, 12.2,
        "⚠️ WHY COTTON KILLS IN THE BACKCOUNTRY (NO DENIM JEANS, COTTON HOODIES, OR COTTON SOCKS)",
        fontsize=9.0, fontweight="bold", color=GOLD, ha="center", va="center"
    )
    ax.text(
        50.0, 6.8,
        "Cotton absorbs 27x its weight in water, collapses all insulating air pockets, and conducts heat away from the body 25x faster than air -> Hypothermia!",
        fontsize=8.2, color=WHITE, ha="center", va="center"
    )
    return fig, ax


def _render_stove_comparison(
    fig_title: str, badge_name: str, req_number: str
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders Backcountry Stove Engineering Matrix (Isobutane Canister vs. White Gas Liquid Fuel)."""
    fig, ax = _create_canvas(
        title=fig_title or "Backcountry Stove Engineering Matrix: Canister vs. Liquid Fuel",
        subtitle="Select stove technology based on ambient temperature, elevation, patrol group size, and weight",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    # Left Column: Isobutane Canister Stove
    _draw_card(
        ax, 2.5, 16.0, 45.5, 67.0,
        header_text="ISOBUTANE-PROPANE CANISTER STOVE",
        body_text=(
            "1. WEIGHT & PACKABILITY: Ultra-lightweight (2.5–4 oz burner); threads onto self-sealing Lindal valve fuel canister.\n\n"
            "2. IGNITION & SIMMER CONTROL: Instant lighting with zero priming; precise flame valve for simmering sauces & meals.\n\n"
            "3. COLD-WEATHER PHYSICS: Internal pressure drops sharply below 20°F (-6°C) as canister chills during vaporization.\n\n"
            "4. BEST USE CASE: 3-season backpacking, fast water boils, and small patrol pairs."
        ),
        accent_color=ACTION_BLUE,
        fill_color=SOFT_BLUE,
        header_height=8.2,
        body_fontsize=8.0,
        header_fontsize=9.2,
        wrap_width=48,
        max_lines=12,
    )

    # Right Column: White Gas Liquid Fuel Stove
    _draw_card(
        ax, 52.0, 16.0, 45.5, 67.0,
        header_text="WHITE GAS LIQUID FUEL STOVE",
        body_text=(
            "1. WEIGHT & PACKABILITY: Heavier burner + refillable aluminum bottle & plunger pump (11–16 oz); eco-friendly zero canister waste.\n\n"
            "2. IGNITION & PRIMING: Requires 30–60 sec liquid fuel priming to pre-heat generator tube before blue vapor flame ignites.\n\n"
            "3. COLD-WEATHER PHYSICS: Sub-zero & high-alpine champion (down to -40°F); manual pump maintains strong pressure.\n\n"
            "4. BEST USE CASE: Winter camping, snow melting, high altitude, and large patrol pots (field-maintainable jets & O-rings)."
        ),
        accent_color=OLIVE,
        fill_color=SOFT_OLIVE,
        header_height=8.2,
        body_fontsize=8.0,
        header_fontsize=9.2,
        wrap_width=48,
        max_lines=12,
    )

    # Bottom BSA Chemical Fuel Policy Banner
    safety_bar = patches.FancyBboxPatch(
        (2.5, 2.8), 95.0, 10.5,
        boxstyle="round,pad=0.2,rounding_size=1.2",
        facecolor=RED, edgecolor="none"
    )
    ax.add_patch(safety_bar)
    ax.text(
        50.0, 9.8,
        "BSA CHEMICAL FUEL SAFETY POLICY: ADULT SUPERVISION REQUIRED • NEVER OPERATE STOVES INSIDE A TENT",
        fontsize=8.8, fontweight="bold", color=GOLD, ha="center", va="center"
    )
    ax.text(
        50.0, 5.5,
        "Carbon Monoxide (CO) is odorless and lethal in enclosed spaces. Refill liquid fuel bottles >=20 ft from flames after stove cools completely.",
        fontsize=8.0, color=WHITE, ha="center", va="center"
    )
    return fig, ax


def _render_water_purification_pipeline(
    fig_title: str, badge_name: str, req_number: str
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders 3-Stage Backcountry Water Treatment & 3-Pot Camp Sanitation Pipeline."""
    fig, ax = _create_canvas(
        title=fig_title or "3-Stage Water Purification & 3-Pot Camp Sanitation Pipeline",
        subtitle="Eliminate Giardia, Cryptosporidium, bacteria, and viruses in drinking water and patrol cookware",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    # Row 1 Header: Drinking Water Treatment
    ax.text(
        3.0, 81.8, "PART A: 3-STAGE BACKCOUNTRY DRINKING WATER PURIFICATION PIPELINE",
        fontsize=9.2, fontweight="bold", color=NAVY, ha="left", va="center"
    )

    water_stages = [
        (
            "1. PRE-FILTER SEDIMENT",
            "Pour turbid creek/lake water through a clean bandana or pre-filter screen to remove silt, algae, and organic debris that clog filters or shield pathogens.",
            OLIVE,
            SOFT_OLIVE,
            2.5,
        ),
        (
            "2. BOIL OR 0.1µm FILTER",
            "• ROLLING BOIL 1 FULL MINUTE: 100% kill of bacteria, protozoa & viruses at any altitude.\n• 0.1µm HOLLOW-FIBER FILTER: Removes bacteria & Giardia/Crypto cysts.",
            ACTION_BLUE,
            SOFT_BLUE,
            35.5,
        ),
        (
            "3. CHEMICAL / UV BACKUP",
            "• CHLORINE DIOXIDE TABLETS: Kills viruses, bacteria & Cryptosporidium (wait 30 min to 4 hrs in cold water).\n• Always carry backup tablets if filter freezes!",
            NAVY,
            SOFT_BLUE,
            68.5,
        ),
    ]
    for hdr, body, color, fill, x in water_stages:
        _draw_card(
            ax, x, 48.0, 29.0, 31.5,
            header_text=hdr,
            body_text=body,
            accent_color=color,
            fill_color=fill,
            header_height=6.5,
            body_fontsize=7.8,
            header_fontsize=8.3,
            wrap_width=32,
            max_lines=6,
        )

    ax.annotate("", xy=(35.2, 63.5), xytext=(31.8, 63.5), arrowprops=dict(arrowstyle="-|>", lw=2.2, color=NAVY))
    ax.annotate("", xy=(68.2, 63.5), xytext=(64.8, 63.5), arrowprops=dict(arrowstyle="-|>", lw=2.2, color=NAVY))

    # Row 2 Header: 3-Pot Dishwashing System
    ax.text(
        3.0, 43.2, "PART B: PATROL 3-POT DISHWASHING & SANITATION LINE (>=200 FT FROM WATER)",
        fontsize=9.2, fontweight="bold", color=RED, ha="left", va="center"
    )

    pots = [
        (
            "STEP 0: SCRAPE CLEAN",
            "Scrape all food bits & grease into trash bag (Pack It Out) before plates touch wash water.",
            MUTED_TEXT,
            WHITE,
            2.5,
        ),
        (
            "POT 1: HOT WASH POT",
            "Hot water (~120°F) + a few drops of biodegradable camp soap. Scrub with brush/pad.",
            RED,
            SOFT_RED,
            26.8,
        ),
        (
            "POT 2: CLEAR HOT RINSE",
            "Dip & swish in clear hot water using tongs to remove all soap film before sanitizing.",
            ACTION_BLUE,
            SOFT_BLUE,
            51.1,
        ),
        (
            "POT 3: SANITIZE & AIR DRY",
            "Cold water + sanitizing tablet/bleach drop (or 170°F+ dip). AIR DRY in mesh bag — never towel dry!",
            OLIVE,
            SOFT_OLIVE,
            75.4,
        ),
    ]
    for hdr, body, color, fill, x in pots:
        _draw_card(
            ax, x, 5.5, 22.1, 35.0,
            header_text=hdr,
            body_text=body,
            accent_color=color,
            fill_color=fill,
            header_height=6.5,
            body_fontsize=7.8,
            header_fontsize=8.0,
            wrap_width=25,
            max_lines=5,
        )
    return fig, ax


def _render_checks_balances_triangle(
    fig_title: str, badge_name: str, req_number: str
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders U.S. Constitution Three Branches & Checks and Balances Triangle."""
    fig, ax = _create_canvas(
        title=fig_title or "U.S. Constitution: Three Branches & Checks and Balances",
        subtitle="Articles I, II, and III divide federal authority so no single branch can exercise unchecked power",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    # Top Vertex: Legislative Branch (Article I)
    _draw_card(
        ax, 31.0, 59.5, 38.0, 23.5,
        header_text="LEGISLATIVE BRANCH • ARTICLE I (CONGRESS)",
        body_text="• Bicameral: U.S. Senate (100) & House of Representatives (435)\n• Makes federal laws, controls taxation/spending ('Power of the Purse'), declares war, oversees agencies",
        accent_color=NAVY,
        fill_color=SOFT_BLUE,
        header_height=6.0,
        body_fontsize=7.8,
        header_fontsize=8.4,
        wrap_width=45,
        max_lines=4,
    )

    # Bottom-Left Vertex: Executive Branch (Article II)
    _draw_card(
        ax, 2.5, 12.0, 41.0, 25.0,
        header_text="EXECUTIVE BRANCH • ARTICLE II (PRESIDENT)",
        body_text="• President, Vice President, Cabinet & Federal Agencies\n• Enforces & administers federal laws, Commander-in-Chief, negotiates treaties, appoints judges & ambassadors",
        accent_color=ACTION_BLUE,
        fill_color=WHITE,
        header_height=6.0,
        body_fontsize=7.8,
        header_fontsize=8.4,
        wrap_width=46,
        max_lines=4,
    )

    # Bottom-Right Vertex: Judicial Branch (Article III)
    _draw_card(
        ax, 56.5, 12.0, 41.0, 25.0,
        header_text="JUDICIAL BRANCH • ARTICLE III (SUPREME COURT)",
        body_text="• U.S. Supreme Court (9 Justices) & Lower Federal Courts\n• Interprets Constitution & federal laws, resolves cases & controversies; life tenure during good behavior",
        accent_color=OLIVE,
        fill_color=SOFT_OLIVE,
        header_height=6.0,
        body_fontsize=7.8,
        header_fontsize=8.4,
        wrap_width=46,
        max_lines=4,
    )

    # Directional Check Arrows & Callouts between Branches
    ax.annotate("", xy=(22.0, 38.0), xytext=(33.0, 58.5), arrowprops=dict(arrowstyle="<->", lw=2.4, color=RED))
    ax.text(
        18.5, 49.0,
        "CONGRESS -> PRESIDENT:\n• 2/3 Veto Override\n• Impeachment & Senate Trial\n• Confirms Cabinet & Treaties\nPRESIDENT -> CONGRESS:\n• Veto Bills",
        fontsize=7.1, fontweight="bold", color=DARK_TEXT, ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.25", facecolor=SOFT_RED, edgecolor=RED, lw=1.3)
    )

    ax.annotate("", xy=(78.0, 38.0), xytext=(67.0, 58.5), arrowprops=dict(arrowstyle="<->", lw=2.4, color=NAVY))
    ax.text(
        81.5, 49.0,
        "CONGRESS -> COURTS:\n• Senate Confirms Justices\n• Impeaches Judges\n• Proposes Amendments\nCOURTS -> CONGRESS:\n• Strikes Unconstitutional Laws",
        fontsize=7.1, fontweight="bold", color=DARK_TEXT, ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.25", facecolor=SOFT_BLUE, edgecolor=NAVY, lw=1.3)
    )

    ax.annotate("", xy=(55.8, 24.5), xytext=(44.2, 24.5), arrowprops=dict(arrowstyle="<->", lw=2.4, color=OLIVE))
    ax.text(
        50.0, 4.8,
        "PRESIDENT <-> COURTS CHECKS: President nominates federal judges & grants pardons  |  Supreme Court exercises Judicial Review over Executive Orders",
        fontsize=8.0, fontweight="bold", color=NAVY, ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.3", facecolor=GOLD, edgecolor=NAVY, lw=1.4)
    )
    return fig, ax


def _render_fourteenth_amendment_shield(
    fig_title: str, badge_name: str, req_number: str
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders 14th Amendment Constitutional Architecture (4 Pillars under Pediment)."""
    fig, ax = _create_canvas(
        title=fig_title or "The 14th Amendment: Constitutional Rights & Citizenship Architecture",
        subtitle="Ratified July 9, 1868 — The cornerstone of national citizenship, civil rights, and Bill of Rights incorporation",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    # Architectural Pediment / Capstone Roof
    roof = patches.FancyBboxPatch(
        (2.5, 72.5), 95.0, 10.5,
        boxstyle="round,pad=0.2,rounding_size=1.2",
        facecolor=NAVY, edgecolor=GOLD, lw=2.2
    )
    ax.add_patch(roof)
    ax.text(
        50.0, 79.2, "FOURTEENTH AMENDMENT TO THE U.S. CONSTITUTION (SECTION 1)",
        fontsize=10.0, fontweight="bold", color=GOLD, ha="center", va="center"
    )
    ax.text(
        50.0, 75.0, "\"No State shall make or enforce any law which shall abridge the privileges or immunities of citizens...\"",
        fontsize=8.2, color=WHITE, ha="center", va="center", style="italic"
    )

    # 4 Constitutional Pillars
    pillars = [
        (
            "1. CITIZENSHIP CLAUSE",
            "NATIONAL & STATE CITIZENSHIP\n\nAll persons born or naturalized in the United States are citizens of the U.S. and the state where they reside.\n\n• Overturned Dred Scott v. Sandford (1857)\n• Protects birthright & naturalized citizens equally",
            NAVY,
            SOFT_BLUE,
            2.5,
        ),
        (
            "2. DUE PROCESS CLAUSE",
            "PROCEDURAL & SUBSTANTIVE FAIRNESS\n\nForbids any State from depriving any person of life, liberty, or property without due process of law.\n\n• Guarantees fair notice & impartial hearings\n• Protects fundamental personal liberties",
            ACTION_BLUE,
            SOFT_BLUE,
            26.8,
        ),
        (
            "3. EQUAL PROTECTION",
            "EQUALITY BEFORE THE LAW\n\nMandates that no State shall deny to any person within its jurisdiction the equal protection of the laws.\n\n• Constitutional foundation of Brown v. Board (1954)\n• Bars unlawful state discrimination",
            RED,
            SOFT_RED,
            51.1,
        ),
        (
            "4. INCORPORATION DOCTRINE",
            "APPLYING THE BILL OF RIGHTS TO STATES\n\nThrough the 14th Amendment, Supreme Court decisions apply Bill of Rights protections against state & local governments.\n\n• Free Speech (1st), Search & Seizure (4th), Counsel (6th)",
            OLIVE,
            SOFT_OLIVE,
            75.4,
        ),
    ]

    for hdr, body, color, fill, x in pillars:
        _draw_card(
            ax, x, 14.5, 22.1, 55.5,
            header_text=hdr,
            body_text=body,
            accent_color=color,
            fill_color=fill,
            header_height=7.5,
            body_fontsize=7.8,
            header_fontsize=8.1,
            wrap_width=25,
            max_lines=10,
        )

    # Foundation Base
    base = patches.FancyBboxPatch(
        (2.5, 3.2), 95.0, 8.8,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=GOLD, edgecolor=NAVY, lw=1.8
    )
    ax.add_patch(base)
    ax.text(
        50.0, 7.6,
        "CONSTITUTIONAL FOUNDATION: Before 1868, the Bill of Rights restricted only Congress; the 14th Amendment bound State & Local Governments!",
        fontsize=8.4, fontweight="bold", color=NAVY, ha="center", va="center"
    )
    return fig, ax


# ==============================================================================
# DYNAMIC DATA-DRIVEN ARCHETYPE RENDERERS (FOR ANY BADGE / REQUIREMENT)
# ==============================================================================

def _render_step_by_step_4card(
    fig_title: str,
    badge_name: str,
    req_number: str,
    slide_data: Optional[Dict[str, Any]],
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders a 4-stage horizontal chevron/card flow using actual steps from slide_data."""
    pairs = _extract_slide_pairs(slide_data, fig_title, badge_name, req_number, count=4)
    fig, ax = _create_canvas(
        title=fig_title or f"{badge_name} Req {req_number}: Step-by-Step Procedure",
        subtitle=f"Sequential 4-stage field execution workflow for {badge_name} Requirement {req_number}",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    colors = [(NAVY, SOFT_BLUE), (ACTION_BLUE, SOFT_BLUE), (OLIVE, SOFT_OLIVE), (RED, SOFT_RED)]
    xs = [2.5, 26.8, 51.1, 75.4]

    for i, ((hdr, body), (col, fill), x) in enumerate(zip(pairs, colors, xs), start=1):
        step_hdr = hdr if re.match(r"^\d", hdr) else f"STEP {i}: {hdr.upper()}"
        _draw_card(
            ax, x, 16.0, 22.1, 65.0,
            header_text=step_hdr,
            body_text=body,
            accent_color=col,
            fill_color=fill,
            header_height=8.0,
            body_fontsize=8.2,
            header_fontsize=8.3,
            wrap_width=24,
            max_lines=9,
        )
        if i < 4:
            ax.annotate(
                "", xy=(x + 24.1, 48.5), xytext=(x + 22.2, 48.5),
                arrowprops=dict(arrowstyle="-|>", lw=2.2, color=NAVY)
            )

    footer = patches.FancyBboxPatch(
        (2.5, 3.5), 95.0, 9.0,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=WHITE, edgecolor=NAVY, lw=1.5
    )
    ax.add_patch(footer)
    ax.text(
        50.0, 8.0,
        f"VERIFICATION CHECKPOINT: Complete all 4 stages in sequence and review outcomes with your {badge_name} Merit Badge Counselor.",
        fontsize=8.4, fontweight="bold", color=NAVY, ha="center", va="center"
    )
    return fig, ax


def _render_differential_comparison_2col(
    fig_title: str,
    badge_name: str,
    req_number: str,
    slide_data: Optional[Dict[str, Any]],
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders a side-by-side 2-column visual comparison chart using slide_data."""
    pairs = _extract_slide_pairs(slide_data, fig_title, badge_name, req_number, count=4)
    data = slide_data if isinstance(slide_data, dict) else {}

    left_title = str(data.get("left_title") or pairs[0][0] or "OPTION A / CONCEPT 1").upper()
    right_title = str(data.get("right_title") or (pairs[1][0] if len(pairs) > 1 else "OPTION B / CONCEPT 2")).upper()

    left_body = f"• {pairs[0][0]}: {pairs[0][1]}"
    if len(pairs) > 2:
        left_body += f"\n\n• {pairs[2][0]}: {pairs[2][1]}"

    right_body = f"• {pairs[1][0]}: {pairs[1][1]}" if len(pairs) > 1 else ""
    if len(pairs) > 3:
        right_body += f"\n\n• {pairs[3][0]}: {pairs[3][1]}"

    fig, ax = _create_canvas(
        title=fig_title or f"{badge_name} Req {req_number}: Side-by-Side Comparison",
        subtitle=f"Comparative analysis of key distinctions and field trade-offs for {badge_name}",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    _draw_card(
        ax, 2.5, 14.0, 44.0, 68.0,
        header_text=left_title[:36],
        body_text=left_body,
        accent_color=ACTION_BLUE,
        fill_color=SOFT_BLUE,
        header_height=8.5,
        body_fontsize=8.3,
        header_fontsize=9.0,
        wrap_width=45,
        max_lines=11,
    )

    vs_badge = patches.Circle((50.0, 48.0), 3.8, facecolor=GOLD, edgecolor=NAVY, lw=2.0, zorder=5)
    ax.add_patch(vs_badge)
    ax.text(50.0, 48.0, "VS", fontsize=10.0, fontweight="bold", color=NAVY, ha="center", va="center", zorder=6)

    _draw_card(
        ax, 53.5, 14.0, 44.0, 68.0,
        header_text=right_title[:36],
        body_text=right_body,
        accent_color=OLIVE,
        fill_color=SOFT_OLIVE,
        header_height=8.5,
        body_fontsize=8.3,
        header_fontsize=9.0,
        wrap_width=45,
        max_lines=11,
    )

    bot = patches.FancyBboxPatch(
        (2.5, 3.2), 95.0, 8.0,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=NAVY, edgecolor="none"
    )
    ax.add_patch(bot)
    ax.text(
        50.0, 7.2,
        f"COUNSELOR DISCUSSION: Explain both sides of this comparison and when each applies under {badge_name} Req {req_number}.",
        fontsize=8.3, fontweight="bold", color=GOLD, ha="center", va="center"
    )
    return fig, ax


def _render_worked_example_template(
    fig_title: str,
    badge_name: str,
    req_number: str,
    slide_data: Optional[Dict[str, Any]],
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders a structured visual blueprint card of the worked example fields from slide_data."""
    pairs = _extract_slide_pairs(slide_data, fig_title, badge_name, req_number, count=4)
    fig, ax = _create_canvas(
        title=fig_title or f"{badge_name} Req {req_number}: Worked Example Blueprint",
        subtitle="Model counselor submission showing required fields, concrete data, and verification checks",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    # Blueprint Outer Container
    blueprint = patches.FancyBboxPatch(
        (2.5, 13.5), 95.0, 69.5,
        boxstyle="round,pad=0.2,rounding_size=1.5",
        facecolor=WHITE, edgecolor=ACTION_BLUE, lw=2.0
    )
    ax.add_patch(blueprint)

    banner = patches.FancyBboxPatch(
        (4.5, 73.5), 91.0, 7.2,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=SOFT_BLUE, edgecolor=ACTION_BLUE, lw=1.4
    )
    ax.add_patch(banner)
    ax.text(
        50.0, 77.1,
        f"SCOUT WORKBOOK RECORD • {badge_name.upper()} REQUIREMENT {req_number} MODEL ENTRY",
        fontsize=9.0, fontweight="bold", color=NAVY, ha="center", va="center"
    )

    coords = [(4.5, 45.0), (50.5, 45.0), (4.5, 16.0), (50.5, 16.0)]
    accents = [NAVY, ACTION_BLUE, OLIVE, RED]
    for (hdr, body), (x, y), col in zip(pairs, coords, accents):
        _draw_card(
            ax, x, y, 45.0, 26.5,
            header_text=f"FIELD: {hdr.upper()}",
            body_text=body,
            accent_color=col,
            fill_color=SLATE,
            header_height=6.2,
            body_fontsize=8.1,
            header_fontsize=8.4,
            wrap_width=46,
            max_lines=4,
        )

    bot = patches.FancyBboxPatch(
        (2.5, 3.0), 95.0, 8.2,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=GOLD, edgecolor=NAVY, lw=1.5
    )
    ax.add_patch(bot)
    ax.text(
        50.0, 7.1,
        "COUNSELOR SIGN-OFF TIP: Personalize every field with your own real troop/home numbers — never copy a blank template!",
        fontsize=8.4, fontweight="bold", color=NAVY, ha="center", va="center"
    )
    return fig, ax


def _render_gear_checklist_grid(
    fig_title: str,
    badge_name: str,
    req_number: str,
    slide_data: Optional[Dict[str, Any]],
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders a 2x3 visual equipment inspection grid from slide_data."""
    pairs = _extract_slide_pairs(slide_data, fig_title, badge_name, req_number, count=6)
    fig, ax = _create_canvas(
        title=fig_title or f"{badge_name} Req {req_number}: Equipment & Gear Inspection Grid",
        subtitle="Verify readiness, fit, and safety compliance of every essential item before field deployment",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=OLIVE,
    )

    grid_pos = [
        (2.5, 49.0), (35.5, 49.0), (68.5, 49.0),
        (2.5, 14.0), (35.5, 14.0), (68.5, 14.0),
    ]
    palette_cycle = [
        (NAVY, SOFT_BLUE),
        (ACTION_BLUE, SOFT_BLUE),
        (OLIVE, SOFT_OLIVE),
        (RED, SOFT_RED),
        (NAVY, WHITE),
        (OLIVE, WHITE),
    ]

    for idx, ((hdr, body), (x, y), (col, fill)) in enumerate(zip(pairs, grid_pos, palette_cycle), start=1):
        _draw_card(
            ax, x, y, 29.0, 32.5,
            header_text=f"[✓] {idx}. {hdr.upper()}",
            body_text=body,
            accent_color=col,
            fill_color=fill,
            header_height=6.5,
            body_fontsize=7.9,
            header_fontsize=8.2,
            wrap_width=31,
            max_lines=5,
        )

    bot = patches.FancyBboxPatch(
        (2.5, 3.0), 95.0, 8.2,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=NAVY, edgecolor="none"
    )
    ax.add_patch(bot)
    ax.text(
        50.0, 7.1,
        f"SHAKEDOWN CHECK: Lay out all {badge_name} gear on a groundsheet for buddy-pair inspection prior to departure.",
        fontsize=8.4, fontweight="bold", color=GOLD, ha="center", va="center"
    )
    return fig, ax


def _render_hands_on_edge_station(
    fig_title: str,
    badge_name: str,
    req_number: str,
    slide_data: Optional[Dict[str, Any]],
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders the BSA EDGE Method 4-Quadrant Cycle (1. EXPLAIN -> 2. DEMONSTRATE -> 3. GUIDE -> 4. ENABLE)."""
    pairs = _extract_slide_pairs(slide_data, fig_title, badge_name, req_number, count=4)
    fig, ax = _create_canvas(
        title=fig_title or f"BSA EDGE Method Practice Station: {badge_name} Req {req_number}",
        subtitle="Hands-on skill mastery cycle: Explain -> Demonstrate -> Guide -> Enable",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    edge_quads = [
        (
            "1. EXPLAIN (WHAT & WHY)",
            f"{pairs[0][0]}: {pairs[0][1]}\n• Clarify safety boundaries and key terminology before touching gear.",
            NAVY,
            SOFT_BLUE,
            2.5,
            48.5,
        ),
        (
            "2. DEMONSTRATE (SHOW HOW)",
            f"{pairs[1][0]}: {pairs[1][1]}\n• Instructor models the complete skill at half-speed with clear callouts.",
            ACTION_BLUE,
            SOFT_BLUE,
            53.5,
            48.5,
        ),
        (
            "4. ENABLE (INDEPENDENT MASTERY)",
            f"{pairs[3][0]}: {pairs[3][1]}\n• Scout executes the full requirement independently for counselor sign-off.",
            OLIVE,
            SOFT_OLIVE,
            2.5,
            13.5,
        ),
        (
            "3. GUIDE (COACHED PRACTICE)",
            f"{pairs[2][0]}: {pairs[2][1]}\n• Buddy pairs practice step-by-step with immediate corrective coaching.",
            RED,
            SOFT_RED,
            53.5,
            13.5,
        ),
    ]

    for hdr, body, col, fill, x, y in edge_quads:
        _draw_card(
            ax, x, y, 44.0, 32.5,
            header_text=hdr,
            body_text=body,
            accent_color=col,
            fill_color=fill,
            header_height=6.8,
            body_fontsize=7.9,
            header_fontsize=8.6,
            wrap_width=45,
            max_lines=5,
        )

    # Clockwise arrows around center EDGE medallion
    ax.annotate("", xy=(53.0, 64.5), xytext=(47.0, 64.5), arrowprops=dict(arrowstyle="-|>", lw=2.5, color=NAVY))
    ax.annotate("", xy=(75.5, 46.2), xytext=(75.5, 48.2), arrowprops=dict(arrowstyle="-|>", lw=2.5, color=ACTION_BLUE))
    ax.annotate("", xy=(47.0, 29.5), xytext=(53.0, 29.5), arrowprops=dict(arrowstyle="-|>", lw=2.5, color=RED))
    ax.annotate("", xy=(24.5, 48.2), xytext=(24.5, 46.2), arrowprops=dict(arrowstyle="-|>", lw=2.5, color=OLIVE))

    hub = patches.Circle((50.0, 47.2), 6.2, facecolor=GOLD, edgecolor=NAVY, lw=2.4, zorder=5)
    ax.add_patch(hub)
    ax.text(50.0, 47.2, "BSA\nEDGE\nCYCLE", fontsize=8.2, fontweight="bold", color=NAVY, ha="center", va="center", zorder=6)

    bot = patches.FancyBboxPatch(
        (2.5, 3.0), 95.0, 8.0,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=NAVY, edgecolor="none"
    )
    ax.add_patch(bot)
    ax.text(
        50.0, 7.0,
        f"SKILL STATION TARGET: Every Scout rotates through practitioner and buddy-verifier roles for {badge_name} Req {req_number}.",
        fontsize=8.3, fontweight="bold", color=GOLD, ha="center", va="center"
    )
    return fig, ax


def _render_socratic_checkpoint_quiz(
    fig_title: str,
    badge_name: str,
    req_number: str,
    slide_data: Optional[Dict[str, Any]],
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders a visual Patrol Scenario Challenge & Decision Matrix graphic."""
    pairs = _extract_slide_pairs(slide_data, fig_title, badge_name, req_number, count=4)
    fig, ax = _create_canvas(
        title=fig_title or f"Patrol Scenario Challenge & Decision Matrix: {badge_name}",
        subtitle=f"Socratic knowledge checkpoint and field decision verification for Requirement {req_number}",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    # Top Scenario Prompt Box
    scenario_box = patches.FancyBboxPatch(
        (2.5, 62.0), 95.0, 20.5,
        boxstyle="round,pad=0.2,rounding_size=1.4",
        facecolor=SOFT_GOLD, edgecolor=GOLD, lw=2.2
    )
    ax.add_patch(scenario_box)
    ax.text(
        50.0, 78.5,
        f"PATROL FIELD SCENARIO CHALLENGE • {badge_name.upper()} REQ {req_number}",
        fontsize=9.5, fontweight="bold", color=NAVY, ha="center", va="center"
    )
    ax.text(
        50.0, 69.8,
        _wrap(f"{pairs[0][0]}: {pairs[0][1]}", width=92, max_lines=3),
        fontsize=8.6, color=DARK_TEXT, ha="center", va="center", linespacing=1.3
    )

    # 3 Decision / Verification Cards below
    sub_cards = [
        ("OPTION A: INITIAL ASSESSMENT", f"{pairs[1][0]}: {pairs[1][1]}", ACTION_BLUE, SOFT_BLUE, 2.5),
        ("OPTION B: CRITICAL SAFETY RULE", f"{pairs[2][0]}: {pairs[2][1]}", RED, SOFT_RED, 35.5),
        ("COUNSELOR GOLD STANDARD", f"{pairs[3][0]}: {pairs[3][1]}", OLIVE, SOFT_OLIVE, 68.5),
    ]
    for hdr, body, col, fill, x in sub_cards:
        _draw_card(
            ax, x, 14.5, 29.0, 43.0,
            header_text=hdr,
            body_text=body,
            accent_color=col,
            fill_color=fill,
            header_height=7.5,
            body_fontsize=8.0,
            header_fontsize=8.2,
            wrap_width=31,
            max_lines=7,
        )

    bot = patches.FancyBboxPatch(
        (2.5, 3.0), 95.0, 8.2,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=NAVY, edgecolor="none"
    )
    ax.add_patch(bot)
    ax.text(
        50.0, 7.1,
        "SOCRATIC DEBRIEF: Discuss with your patrol WHY the correct protocol prevents injury or failure before advancing.",
        fontsize=8.3, fontweight="bold", color=GOLD, ha="center", va="center"
    )
    return fig, ax


def _render_concept_architecture_explainer(
    fig_title: str,
    badge_name: str,
    req_number: str,
    slide_data: Optional[Dict[str, Any]],
) -> Tuple[plt.Figure, plt.Axes]:
    """Renders an annotated multi-node concept architecture diagram specific to the slide."""
    pairs = _extract_slide_pairs(slide_data, fig_title, badge_name, req_number, count=4)
    fig, ax = _create_canvas(
        title=fig_title or f"{badge_name} Req {req_number}: Concept Architecture",
        subtitle=f"Core principles, field relationships, and execution standards for {badge_name}",
        badge_tag=f"{badge_name} • REQ {req_number}",
        header_color=NAVY,
    )

    # Central Hub Node
    hub = patches.FancyBboxPatch(
        (36.5, 38.5), 27.0, 17.0,
        boxstyle="round,pad=0.2,rounding_size=1.6",
        facecolor=NAVY, edgecolor=GOLD, lw=2.4, zorder=5
    )
    ax.add_patch(hub)
    ax.text(
        50.0, 49.8, f"{badge_name.upper()}",
        fontsize=9.2, fontweight="bold", color=GOLD, ha="center", va="center", zorder=6
    )
    ax.text(
        50.0, 43.8, _wrap(fig_title or f"Requirement {req_number}", width=26, max_lines=2),
        fontsize=8.0, fontweight="bold", color=WHITE, ha="center", va="center", zorder=6
    )

    # 4 Satellite Nodes connected to Central Hub
    nodes = [
        (pairs[0][0], pairs[0][1], NAVY, SOFT_BLUE, 2.5, 53.0, (30.5, 62.0), (36.5, 51.0)),
        (pairs[1][0], pairs[1][1], ACTION_BLUE, SOFT_BLUE, 69.5, 53.0, (69.5, 62.0), (63.5, 51.0)),
        (pairs[2][0], pairs[2][1], OLIVE, SOFT_OLIVE, 2.5, 13.5, (30.5, 25.0), (36.5, 42.0)),
        (pairs[3][0], pairs[3][1], RED, SOFT_RED, 69.5, 13.5, (69.5, 25.0), (63.5, 42.0)),
    ]

    for hdr, body, col, fill, x, y, p_card, p_hub in nodes:
        _draw_card(
            ax, x, y, 28.0, 29.0,
            header_text=hdr.upper()[:30],
            body_text=body,
            accent_color=col,
            fill_color=fill,
            header_height=6.5,
            body_fontsize=7.9,
            header_fontsize=8.2,
            wrap_width=30,
            max_lines=5,
        )
        ax.annotate(
            "", xy=p_card, xytext=p_hub,
            arrowprops=dict(arrowstyle="-|>", lw=2.2, color=col)
        )

    bot = patches.FancyBboxPatch(
        (2.5, 3.0), 95.0, 7.8,
        boxstyle="round,pad=0.15,rounding_size=1.0",
        facecolor=WHITE, edgecolor=NAVY, lw=1.5
    )
    ax.add_patch(bot)
    ax.text(
        50.0, 6.9,
        f"SCOUTS BSA STANDARD: Connect every concept node above to practical demonstration during your {badge_name} counselor session.",
        fontsize=8.2, fontweight="bold", color=NAVY, ha="center", va="center"
    )
    return fig, ax


# ==============================================================================
# SPECIALIZED DIAGRAM RESOLVER & SLIDE-SPECIFIC ASSET ENTRY POINT
# ==============================================================================

SPECIALIZED_RENDERERS = {
    "triage_decision_tree": _render_triage_decision_tree,
    "heat_comparison": _render_heat_comparison,
    "cpr_aed_cycle": _render_cpr_aed_cycle,
    "splinting_cms": _render_splinting_cms,
    "first_aid_kit_grid": _render_first_aid_kit_grid,
    "bearmuda_triangle": _render_bearmuda_triangle,
    "clothing_layering_3layer": _render_clothing_layering_3layer,
    "stove_comparison": _render_stove_comparison,
    "water_purification_pipeline": _render_water_purification_pipeline,
    "checks_balances_triangle": _render_checks_balances_triangle,
    "fourteenth_amendment_shield": _render_fourteenth_amendment_shield,
}


def _resolve_specialized_diagram(
    badge_name: str,
    req_number: str,
    archetype: str,
    diagram_type: str,
    slide_title: str,
) -> Optional[str]:
    """Resolves a diagram_type or slide context to one of the 11 specialized renderers if matched."""
    dt_clean = (diagram_type or "").strip().lower()
    if dt_clean in SPECIALIZED_RENDERERS:
        return dt_clean

    combined = f"{badge_name} {req_number} {dt_clean} {slide_title}".lower()
    if "triage" in combined and ("tier" in combined or "decision" in combined or "first aid" in combined):
        return "triage_decision_tree"
    if "heat exhaustion" in combined or "heat stroke" in combined or "heat_comparison" in combined:
        return "heat_comparison"
    if "cpr" in combined or "aed" in combined or "30:2" in combined or "resuscitation" in combined:
        return "cpr_aed_cycle"
    if "splint" in combined or "c-m-s" in combined or "cms check" in combined:
        return "splinting_cms"
    if "first aid kit" in combined or "knolling" in combined or "21-item" in combined:
        return "first_aid_kit_grid"
    if "bearmuda" in combined or "bear-muda" in combined or "bear hang" in combined or "200-foot" in combined:
        return "bearmuda_triangle"
    if "cotton kills" in combined or "3-layer" in combined or "layering" in combined:
        return "clothing_layering_3layer"
    if "stove" in combined and ("canister" in combined or "white gas" in combined or "liquid fuel" in combined or "comparison" in combined):
        return "stove_comparison"
    if "water purification" in combined or "water treatment" in combined or "3-pot" in combined or "three-pot" in combined:
        return "water_purification_pipeline"
    if "checks and balances" in combined or "three branches" in combined or "separation of powers" in combined:
        return "checks_balances_triangle"
    if "14th amendment" in combined or "fourteenth amendment" in combined or "equal protection" in combined:
        return "fourteenth_amendment_shield"
    return None


def generate_slide_visual_asset(
    badge_name: str,
    req_number: str,
    archetype: str,
    diagram_type: str = "procedural_flow",
    slide_title: str = "",
    slide_data: Optional[Dict[str, Any]] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Generates a slide-specific high-craft visual asset (220 DPI PNG + vector SVG).

    Guarantees a unique filename per slide so no two slides in a deck ever share
    the same image path, and returns a dictionary compatible with VisualAssetSpec.

    Args:
        badge_name: Official name of the Merit Badge (e.g., 'First Aid', 'Weather').
        req_number: Requirement or sub-requirement identifier (e.g., '1', '2a', 'Overview').
        archetype: Slide archetype key (e.g., 'DECISION_TREE_FLOW', 'DIFFERENTIAL_COMPARISON_2COL').
        diagram_type: Specialized diagram renderer key or fallback category.
        slide_title: Headline title of the target slide.
        slide_data: Optional dictionary of slide bullets, cards, or comparison data.
        output_dir: Optional directory path where the rendered `.png` and `.svg` files are saved.

    Returns:
        Dict[str, Any]: Serialized `VisualAssetSpec` dictionary containing `asset_id`, `source_type`,
        `diagram_kind`, `caption`, `svg_path`, `png_path`, and `alt_text`.
    """
    target_dir = os.path.abspath(output_dir) if output_dir else DIAGRAMS_DIR
    os.makedirs(target_dir, exist_ok=True)

    safe_badge = _sanitize_slug(badge_name, 28)
    safe_req = _sanitize_slug(req_number or "overview", 16)
    safe_archetype = _sanitize_slug(archetype or "split_visual_explainer", 32)
    safe_diagram = _sanitize_slug(diagram_type or "procedural_flow", 32)
    safe_title = _sanitize_slug(slide_title, 24) if slide_title else ""

    if safe_title and safe_title not in safe_diagram:
        stem = f"{safe_badge}_req_{safe_req}_{safe_archetype}_{safe_diagram}_{safe_title}"
    else:
        stem = f"{safe_badge}_req_{safe_req}_{safe_archetype}_{safe_diagram}"

    png_path = os.path.join(target_dir, f"{stem}.png")
    svg_path = os.path.join(target_dir, f"{stem}.svg")

    specialized_key = _resolve_specialized_diagram(
        badge_name=badge_name,
        req_number=req_number,
        archetype=archetype,
        diagram_type=diagram_type,
        slide_title=slide_title,
    )

    arch_upper = (archetype or "").strip().upper()
    display_title = slide_title.strip() if slide_title else f"{badge_name} — Req {req_number}"

    if specialized_key and specialized_key in SPECIALIZED_RENDERERS:
        renderer = SPECIALIZED_RENDERERS[specialized_key]
        fig, _ = renderer(display_title, badge_name, req_number)
        caption = f"{badge_name} Req {req_number}: {display_title} ({specialized_key.replace('_', ' ').title()})"
    elif arch_upper == "STEP_BY_STEP_PROCEDURE_4CARD":
        fig, _ = _render_step_by_step_4card(display_title, badge_name, req_number, slide_data)
        caption = f"{badge_name} Req {req_number}: 4-Step Procedural Workflow — {display_title}"
    elif arch_upper == "DIFFERENTIAL_COMPARISON_2COL":
        fig, _ = _render_differential_comparison_2col(display_title, badge_name, req_number, slide_data)
        caption = f"{badge_name} Req {req_number}: 2-Column Differential Comparison — {display_title}"
    elif arch_upper == "WORKED_EXAMPLE_TEMPLATE":
        fig, _ = _render_worked_example_template(display_title, badge_name, req_number, slide_data)
        caption = f"{badge_name} Req {req_number}: Worked Example Blueprint — {display_title}"
    elif arch_upper == "GEAR_CHECKLIST_GRID":
        fig, _ = _render_gear_checklist_grid(display_title, badge_name, req_number, slide_data)
        caption = f"{badge_name} Req {req_number}: Equipment Inspection Grid — {display_title}"
    elif arch_upper == "HANDS_ON_PRACTICE_STATION":
        fig, _ = _render_hands_on_edge_station(display_title, badge_name, req_number, slide_data)
        caption = f"{badge_name} Req {req_number}: BSA EDGE Method Practice Station — {display_title}"
    elif arch_upper == "SOCRATIC_CHECKPOINT_QUIZ":
        fig, _ = _render_socratic_checkpoint_quiz(display_title, badge_name, req_number, slide_data)
        caption = f"{badge_name} Req {req_number}: Patrol Scenario Decision Matrix — {display_title}"
    else:
        fig, _ = _render_concept_architecture_explainer(display_title, badge_name, req_number, slide_data)
        caption = f"{badge_name} Req {req_number}: Visual Concept Architecture — {display_title}"

    _save_dual_assets(fig, png_path=png_path, svg_path=svg_path)

    return {
        "asset_id": stem,
        "source_type": "DETERMINISTIC_SVG_DIAGRAM",
        "diagram_kind": diagram_type,
        "caption": caption,
        "svg_path": svg_path,
        "png_path": png_path,
        "alt_text": f"Scouts BSA educational diagram for {badge_name} Requirement {req_number}: {display_title}",
    }


# ==============================================================================
# 100% BACKWARD-COMPATIBLE LEGACY DIAGRAM FUNCTIONS
# ==============================================================================

def generate_water_cycle_diagram(output_dir: Optional[str] = None) -> str:
    """Generates an educational graphic illustrating the Water Cycle for the Weather Merit Badge."""
    target_dir = os.path.abspath(output_dir) if output_dir else DIAGRAMS_DIR
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, "water_cycle_diagram.png")
    svg_path = os.path.join(target_dir, "water_cycle_diagram.svg")

    fig, ax = _create_canvas(
        title="The Earth's Hydrologic (Water) Cycle",
        subtitle="Solar evaporation, atmospheric condensation, precipitation, and watershed runoff",
        badge_tag="WEATHER • WATER CYCLE",
        header_color=NAVY,
    )

    ocean = patches.FancyBboxPatch((52, 8), 44, 22, boxstyle="round,pad=0.2", facecolor=ACTION_BLUE, alpha=0.85, edgecolor=NAVY, lw=1.8)
    ax.add_patch(ocean)
    ax.text(74, 19, "OCEAN / SURFACE WATER\n(Thermal Solar Reservoir)", fontsize=9.5, fontweight="bold", color=WHITE, ha="center", va="center")

    mountain = patches.Polygon([[4, 8], [48, 8], [22, 48]], facecolor=OLIVE, edgecolor=NAVY, lw=1.8)
    ax.add_patch(mountain)
    ax.text(24, 18, "WATERSHED / LAND\n(Runoff & Infiltration)", fontsize=9.0, fontweight="bold", color=WHITE, ha="center", va="center")

    cloud = patches.FancyBboxPatch((24, 62), 52, 16, boxstyle="round,pad=0.3,rounding_size=3.0", facecolor=WHITE, edgecolor=NAVY, lw=2.0)
    ax.add_patch(cloud)
    ax.text(50, 70, "2. CONDENSATION & CLOUD FORMATION\nCooling water vapor condenses onto aerosols aloft", fontsize=9.2, fontweight="bold", color=NAVY, ha="center", va="center")

    ax.annotate("", xy=(74, 61), xytext=(74, 31), arrowprops=dict(arrowstyle="-|>", lw=2.8, color=ACTION_BLUE))
    ax.text(85, 46, "1. EVAPORATION\n(Solar Heating)", fontsize=8.8, fontweight="bold", color=ACTION_BLUE, ha="center")

    ax.annotate("", xy=(26, 46), xytext=(36, 61), arrowprops=dict(arrowstyle="-|>", lw=2.8, color=RED))
    ax.text(14, 56, "3. PRECIPITATION\n(Rain, Snow, Hail)", fontsize=8.8, fontweight="bold", color=RED, ha="center")

    ax.annotate("", xy=(51, 18), xytext=(36, 24), arrowprops=dict(arrowstyle="-|>", lw=2.8, color=OLIVE))
    ax.text(44, 30, "4. SURFACE RUNOFF", fontsize=8.5, fontweight="bold", color=OLIVE, ha="center")

    _save_dual_assets(fig, png_path=out_path, svg_path=svg_path)
    return out_path


def generate_cloud_types_diagram(output_dir: Optional[str] = None) -> str:
    """Generates a diagram showing Cirrus, Altostratus, Stratus, and Cumulonimbus cloud types."""
    target_dir = os.path.abspath(output_dir) if output_dir else DIAGRAMS_DIR
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, "cloud_types_diagram.png")
    svg_path = os.path.join(target_dir, "cloud_types_diagram.svg")

    fig, ax = _create_canvas(
        title="Scouts BSA Meteorology: Cloud Etages & Storm Anvils",
        subtitle="Identify high, mid, low, and vertical convective clouds to forecast approaching fronts",
        badge_tag="WEATHER • CLOUD ATLAS",
        header_color=NAVY,
    )

    _draw_card(ax, 3.0, 59.0, 52.0, 22.0, "HIGH CLOUDS (>20,000 FT) • CIRRUS / CIRROSTRATUS",
               "Thin, wispy ice-crystal filaments. Indicates high-altitude moisture ahead of an approaching warm front within 24–36 hours.",
               NAVY, SOFT_BLUE, header_height=6.0, wrap_width=56)
    _draw_card(ax, 3.0, 33.0, 52.0, 22.0, "MID CLOUDS (6,500–20,000 FT) • ALTOCUMULUS / ALTOSTRATUS",
               "Gray/white sheets or turret rows. Thickening altostratus signals steady rain or snow arriving soon.",
               ACTION_BLUE, WHITE, header_height=6.0, wrap_width=56)
    _draw_card(ax, 3.0, 7.0, 52.0, 22.0, "LOW CLOUDS (<6,500 FT) • STRATUS / CUMULUS",
               "Flat overcast stratus layers bring drizzle/fog; fair-weather cumulus puffs remain benign unless vertical towers build.",
               OLIVE, SOFT_OLIVE, header_height=6.0, wrap_width=56)
    _draw_card(ax, 58.0, 7.0, 39.0, 74.0, "⚠️ CUMULONIMBUS (THUNDERSTORM)",
               "TOWERING VERTICAL ANVIL (2,000–50,000+ FT)\n\n• Severe updrafts/downdrafts, lightning, hail, microbursts & flash floods\n\n• 30/30 LIGHTNING RULE: Seek low timber or enclosed shelter immediately when thunder follows flash within 30 seconds!",
               RED, SOFT_RED, header_height=8.0, wrap_width=38, max_lines=10)

    _save_dual_assets(fig, png_path=out_path, svg_path=svg_path)
    return out_path


def generate_weather_front_diagram(output_dir: Optional[str] = None) -> str:
    """Generates a Cold Front vs. Warm Front meteorological cross-section diagram."""
    target_dir = os.path.abspath(output_dir) if output_dir else DIAGRAMS_DIR
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, "weather_front_diagram.png")
    svg_path = os.path.join(target_dir, "weather_front_diagram.svg")

    fig, ax = _create_canvas(
        title="Frontal Wedge Mechanics: Cold Front vs. Warm Front",
        subtitle="Compare steep convective uplift (squalls/thunderstorms) against gradual overrunning precipitation",
        badge_tag="WEATHER • FRONTAL SYSTEMS",
        header_color=NAVY,
    )

    _draw_card(ax, 2.5, 10.0, 46.0, 72.0, "COLD FRONT (STEEP WEDGE • BLUE TRIANGLES)",
               "• Dense cold polar air bulldozes underneath warm moist air\n\n• Steep 1:50 slope forces violent vertical uplift\n\n• Produces towering Cumulonimbus squall lines, gusty winds, heavy downpours, and rapid temperature drop",
               ACTION_BLUE, SOFT_BLUE, header_height=8.0, wrap_width=46, max_lines=10)
    _draw_card(ax, 51.5, 10.0, 46.0, 72.0, "WARM FRONT (GENTLE SLOPE • RED SEMICIRCLES)",
               "• Advancing warm moist air glides gradually up over retreating cold air wedge (1:200 slope)\n\n• Cloud sequence: Cirrus -> Altostratus -> Nimbostratus\n\n• Produces widespread steady rain/fog followed by warmer humid air",
               RED, SOFT_RED, header_height=8.0, wrap_width=46, max_lines=10)

    _save_dual_assets(fig, png_path=out_path, svg_path=svg_path)
    return out_path


def generate_cpr_steps_diagram(output_dir: Optional[str] = None) -> str:
    """Generates an emergency First Aid CPR and AED 4-step infographic."""
    target_dir = os.path.abspath(output_dir) if output_dir else DIAGRAMS_DIR
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, "cpr_steps_diagram.png")
    svg_path = os.path.join(target_dir, "cpr_steps_diagram.svg")
    fig, _ = _render_cpr_aed_cycle("Emergency First Aid: 4-Step CPR & AED Action Plan", "First Aid", "3")
    _save_dual_assets(fig, png_path=out_path, svg_path=svg_path)
    return out_path


def generate_first_aid_cpr_diagram(output_dir: Optional[str] = None) -> str:
    """Backward-compatible alias for the First Aid CPR & AED diagram."""
    target_dir = os.path.abspath(output_dir) if output_dir else DIAGRAMS_DIR
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, "first_aid_cpr_diagram.png")
    svg_path = os.path.join(target_dir, "first_aid_cpr_diagram.svg")
    fig, _ = _render_cpr_aed_cycle("First Aid Merit Badge: CPR 30:2 & AED Protocol", "First Aid", "3")
    _save_dual_assets(fig, png_path=out_path, svg_path=svg_path)
    return out_path


def generate_first_aid_bleeding_diagram(output_dir: Optional[str] = None) -> str:
    """Generates an infographic showing Severe Bleeding Control and Shock Management."""
    target_dir = os.path.abspath(output_dir) if output_dir else DIAGRAMS_DIR
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, "first_aid_bleeding_diagram.png")
    svg_path = os.path.join(target_dir, "first_aid_bleeding_diagram.svg")

    fig, ax = _create_canvas(
        title="First Aid Protocol: Severe Hemorrhage & Shock Control",
        subtitle="Direct pressure, pressure bandages, windlass tourniquet placement, and shock thermal management",
        badge_tag="FIRST AID • BLEEDING",
        header_color=RED,
    )

    steps = [
        ("1. DIRECT PRESSURE", "Apply sterile gauze pad with gloved hands. Press firmly and continuously. Never remove blood-soaked gauze — add new layers on top.", NAVY, SOFT_BLUE, 2.5),
        ("2. PRESSURE BANDAGE", "Wrap roller/elastic bandage snugly over gauze to maintain steady pressure. Check distal pulse & capillary refill (<2s).", ACTION_BLUE, SOFT_BLUE, 35.5),
        ("3. TOURNIQUET & SHOCK", "For life-threatening limb bleeding: place CoTCCC tourniquet 2–3 in above wound (never on joint), twist windlass until bleeding stops, note time, treat for shock.", RED, SOFT_RED, 68.5),
    ]
    for hdr, body, col, fill, x in steps:
        _draw_card(ax, x, 12.0, 29.0, 70.0, hdr, body, col, fill, header_height=8.0, wrap_width=31, max_lines=10)

    _save_dual_assets(fig, png_path=out_path, svg_path=svg_path)
    return out_path


def generate_leave_no_trace_diagram(output_dir: Optional[str] = None) -> str:
    """Generates a Leave No Trace Seven Principles infographic for the Camping Merit Badge."""
    target_dir = os.path.abspath(output_dir) if output_dir else DIAGRAMS_DIR
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, "leave_no_trace_diagram.png")
    svg_path = os.path.join(target_dir, "leave_no_trace_diagram.svg")
    fig, _ = _render_bearmuda_triangle("Camping Merit Badge: Leave No Trace & 200-Foot Camp Layout", "Camping", "9")
    _save_dual_assets(fig, png_path=out_path, svg_path=svg_path)
    return out_path


def generate_camping_tent_diagram(output_dir: Optional[str] = None) -> str:
    """Backward-compatible generator for Camping site selection & Bear-muda triangle layout."""
    target_dir = os.path.abspath(output_dir) if output_dir else DIAGRAMS_DIR
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, "camping_tent_diagram.png")
    svg_path = os.path.join(target_dir, "camping_tent_diagram.svg")
    fig, _ = _render_bearmuda_triangle("Camping Merit Badge: Backcountry Tent & Bear-muda Triangle", "Camping", "6")
    _save_dual_assets(fig, png_path=out_path, svg_path=svg_path)
    return out_path


def generate_myplate_cooking_diagram(output_dir: Optional[str] = None) -> str:
    """Generates a MyPlate nutrition infographic for Cooking Merit Badge camp menus."""
    target_dir = os.path.abspath(output_dir) if output_dir else DIAGRAMS_DIR
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, "myplate_cooking_diagram.png")
    svg_path = os.path.join(target_dir, "myplate_cooking_diagram.svg")

    fig, ax = _create_canvas(
        title="Cooking Merit Badge: USDA MyPlate Camp Nutrition Guide",
        subtitle="Balance complex carbohydrates, lean proteins, fruits, vegetables, and dairy for trail energy",
        badge_tag="COOKING • MYPLATE",
        header_color=NAVY,
    )

    quads = [
        ("FRUITS (VITAMINS & QUICK ENERGY)", "Fresh apples, oranges, dried berries, and trail fruit leathers provide rapid glucose and Vitamin C.", RED, SOFT_RED, 2.5, 46.5),
        ("VEGETABLES (FIBER & MINERALS)", "Carrots, bell peppers, dehydrated greens, and camp stews supply essential micronutrients and hydration.", OLIVE, SOFT_OLIVE, 51.0, 46.5),
        ("GRAINS (COMPLEX CARBS / TRAIL FUEL)", "Whole-grain oats, brown rice, whole-wheat pasta, and tortillas deliver sustained caloric endurance.", GOLD, SOFT_GOLD, 2.5, 9.5),
        ("PROTEIN & DAIRY (MUSCLE RECOVERY)", "Foil-packet fish/chicken, beans, nuts, jerky, hard cheese, and powdered milk repair active muscle fibers.", NAVY, SOFT_BLUE, 51.0, 9.5),
    ]
    for hdr, body, col, fill, x, y in quads:
        hdr_txt = DARK_TEXT if col == GOLD else WHITE
        _draw_card(ax, x, y, 46.5, 34.5, hdr, body, col, fill, header_height=7.0, wrap_width=48, max_lines=5, header_text_color=hdr_txt)

    _save_dual_assets(fig, png_path=out_path, svg_path=svg_path)
    return out_path


def generate_cooking_stove_diagram(output_dir: Optional[str] = None) -> str:
    """Backward-compatible generator for Backcountry Stove & Camp Kitchen comparison."""
    target_dir = os.path.abspath(output_dir) if output_dir else DIAGRAMS_DIR
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, "cooking_stove_diagram.png")
    svg_path = os.path.join(target_dir, "cooking_stove_diagram.svg")
    fig, _ = _render_stove_comparison("Backcountry Stove Engineering & Fuel Safety Matrix", "Camping", "6")
    _save_dual_assets(fig, png_path=out_path, svg_path=svg_path)
    return out_path


def generate_universal_badge_diagram(badge_name: str, output_dir: Optional[str] = None) -> str:
    """Generates a clean 4-pillar competency diagram for any merit badge."""
    target_dir = os.path.abspath(output_dir) if output_dir else DIAGRAMS_DIR
    os.makedirs(target_dir, exist_ok=True)
    safe_name = _sanitize_slug(badge_name, 36)
    out_path = os.path.join(target_dir, f"{safe_name}_diagram.png")
    svg_path = os.path.join(target_dir, f"{safe_name}_diagram.svg")

    fig, ax = _create_canvas(
        title=f"{badge_name} Merit Badge: 4-Pillar Mastery Framework",
        subtitle="Safety policies, core theory, hands-on EDGE skill demonstration, and lifelong application",
        badge_tag=f"{badge_name} • OVERVIEW",
        header_color=NAVY,
    )

    pillars = [
        ("1. SAFETY & STEWARDSHIP", f"Apply Guide to Safe Scouting rules, PPE, and risk controls for all {badge_name} activities.", RED, SOFT_RED, 2.5, 46.5),
        ("2. CORE PRINCIPLES", f"Master the terminology, scientific principles, and official BSA pamphlet standards for {badge_name}.", NAVY, SOFT_BLUE, 51.0, 46.5),
        ("3. HANDS-ON SKILL (EDGE)", f"Demonstrate practical proficiency in {badge_name} procedures with your Merit Badge Counselor.", ACTION_BLUE, SOFT_BLUE, 2.5, 9.5),
        ("4. CAREERS & CITIZENSHIP", f"Explore how {badge_name} skills serve your patrol, community, and future profession.", OLIVE, SOFT_OLIVE, 51.0, 9.5),
    ]
    for hdr, body, col, fill, x, y in pillars:
        _draw_card(ax, x, y, 46.5, 34.5, hdr, body, col, fill, header_height=7.0, wrap_width=48, max_lines=5)

    _save_dual_assets(fig, png_path=out_path, svg_path=svg_path)
    return out_path


def get_badge_diagram_path(
    badge_name: str,
    output_dir: Optional[str] = None,
    slide_title: str = "",
) -> str:
    """Returns the absolute filesystem path to a pedagogical diagram graphic for the badge/slide.

    Maintains 100% backward compatibility whether the second positional argument is
    `output_dir` (a filesystem path) or `slide_title` (a slide heading string).
    """
    resolved_dir: Optional[str] = None
    resolved_title: str = slide_title or ""

    if output_dir:
        if os.path.isdir(output_dir) or "/" in output_dir or "\\" in output_dir:
            resolved_dir = output_dir
        elif not resolved_title:
            resolved_title = output_dir

    clean_name = (badge_name or "Scouts BSA").strip().title()
    title_lower = resolved_title.lower()

    if clean_name == "Weather":
        if "cloud" in title_lower or "req 3" in title_lower or "req 4" in title_lower or "hazard" in title_lower:
            return generate_cloud_types_diagram(output_dir=resolved_dir)
        if "front" in title_lower or "req 2" in title_lower:
            return generate_weather_front_diagram(output_dir=resolved_dir)
        return generate_water_cycle_diagram(output_dir=resolved_dir)

    if clean_name == "First Aid":
        if "bleeding" in title_lower or "shock" in title_lower or "req 2" in title_lower or "tourniquet" in title_lower:
            return generate_first_aid_bleeding_diagram(output_dir=resolved_dir)
        return generate_cpr_steps_diagram(output_dir=resolved_dir)

    if clean_name == "Camping":
        if "stove" in title_lower or "fuel" in title_lower:
            return generate_cooking_stove_diagram(output_dir=resolved_dir)
        return generate_leave_no_trace_diagram(output_dir=resolved_dir)

    if clean_name == "Cooking":
        if "stove" in title_lower or "fuel" in title_lower:
            return generate_cooking_stove_diagram(output_dir=resolved_dir)
        return generate_myplate_cooking_diagram(output_dir=resolved_dir)

    return generate_universal_badge_diagram(clean_name, output_dir=resolved_dir)
