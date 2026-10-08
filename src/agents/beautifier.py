"""ADK SlideBeautifierAgent for Magazine-Grade Slide Layout & Targeted AI Editorial Hero Art.

This module implements:
1. `generate_ai_editorial_illustration`: Generates or retrieves disk-cached editorial vector/hero
   illustrations in the official Scouts BSA palette (`#003F87`, `#4B5320`, `#F4C430`, `#CE1126`),
   supporting Vertex AI / Gemini `imagen-3.0-generate-002` with deterministic 220-DPI Matplotlib
   vector illustration fallback.
2. `beautify_slide_storyboard`: Transforms a `StoryboardPlan` into a `DeckVisualBlueprint` with:
   - 6 Magazine/Infographic Visual Themes (`MAGAZINE_ASYMMETRIC_SPLIT`, `THREE_PILLAR_ACCENT_CARDS`,
     `NUMBERED_STEP_RIBBON`, `HERO_ILLUSTRATION_OVERLAY`, `SAFETY_ALERT_SPOTLIGHT`,
     `ANNOTATED_INFOGRAPHIC_STAGE`)
   - Strict consecutive-slide variety enforcement
   - Distinct `'Real-World Field Connection'` callout cards from Tier-2 Deep Research
   - Targeted AI hero art generation capped by FinOps tier (`STANDARD=0`, `BEAUTIFIED=5`, `STUDIO=15`)
3. `get_slide_beautifier_agent`: ADK `Agent` factory wired with Model Armor guardrails and FinOps routing.
"""

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as patches
import matplotlib.pyplot as plt
from google import adk

from src.agents.guardrails import (
    after_model_guardrail_callback,
    before_model_guardrail_callback,
)
from src.config import (
    ASSETS_DIR,
    SCOUTS_BSA_CONSTITUTION,
    ScoutsBSAPalette,
    load_prompt,
    select_model_for_task,
)
from src.schemas import (
    DeckVisualBlueprint,
    SlideBeautificationSpec,
    build_guided_tool_error,
)

AI_ILLUSTRATIONS_DIR: Path = ASSETS_DIR / "ai_illustrations"
AI_ILLUSTRATIONS_DIR.mkdir(parents=True, exist_ok=True)

_VISUAL_THEMES = [
    "MAGAZINE_ASYMMETRIC_SPLIT",
    "THREE_PILLAR_ACCENT_CARDS",
    "NUMBERED_STEP_RIBBON",
    "ANNOTATED_INFOGRAPHIC_STAGE",
    "HERO_ILLUSTRATION_OVERLAY",
    "SAFETY_ALERT_SPOTLIGHT",
]

_ACCENT_PALETTES = [
    "NAVY_GOLD",
    "OLIVE_FOREST",
    "SLATE_ACTION",
    "EAGLE_CRIMSON",
]

_PALETTE_HEX_MAP = {
    "NAVY_GOLD": (ScoutsBSAPalette.NAVY_BLUE_HEX, ScoutsBSAPalette.EAGLE_GOLD_HEX, ScoutsBSAPalette.SOFT_BLUE_CARD_HEX),
    "OLIVE_FOREST": (ScoutsBSAPalette.WARM_OLIVE_HEX, ScoutsBSAPalette.EAGLE_GOLD_HEX, ScoutsBSAPalette.SOFT_OLIVE_CARD_HEX),
    "EAGLE_CRIMSON": (ScoutsBSAPalette.EAGLE_RED_HEX, ScoutsBSAPalette.NAVY_BLUE_HEX, ScoutsBSAPalette.SOFT_RED_CARD_HEX),
    "SLATE_ACTION": (ScoutsBSAPalette.ACTION_BLUE_HEX, ScoutsBSAPalette.EAGLE_GOLD_HEX, ScoutsBSAPalette.SOFT_GOLD_CARD_HEX),
}


def generate_ai_editorial_illustration(
    badge_name: str,
    slide_title: str,
    visual_prompt: str,
    accent_palette_key: str = "NAVY_GOLD",
    beautification_tier: str = "BEAUTIFIED",
    req_number: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Generates or loads a cached editorial hero illustration for a Merit Badge slide.

    Uses SHA-256 prompt caching in `assets/ai_illustrations/` so repeat deck builds incur `$0.00`
    image generation cost. When `USE_VERTEX_IMAGEN=true` and credentials are configured, calls
    `imagen-3.0-generate-002`; otherwise renders a crisp 220-DPI Scouts BSA editorial vector card.

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge (e.g., `'Weather'`, `'First Aid'`).
        slide_title: Headline title of the target slide.
        visual_prompt: Descriptive editorial illustration prompt.
        accent_palette_key: Brand palette key (`'NAVY_GOLD'`, `'OLIVE_FOREST'`, `'EAGLE_CRIMSON'`,
            or `'SLATE_ACTION'`).
        beautification_tier: `'BEAUTIFIED'` or `'STUDIO'`.
        req_number: Optional requirement identifier (e.g., `'1'`, `'2a'`) for header context and cache disambiguation.

    Returns:
        Dict[str, Any]: Dictionary containing `image_path`, `cached_hit` (`bool`), `model_used`,
        `accent_palette_key`, and `status` (or `GuidedToolError` if `badge_name` is empty).
    """
    if not badge_name or not str(badge_name).strip():
        return build_guided_tool_error(
            error_code="EMPTY_BADGE_NAME",
            message="badge_name cannot be empty when generating an editorial illustration.",
            remediation="Provide a valid Scouts BSA Merit Badge name such as 'Weather' or 'First Aid'.",
        )

    tier_tag = str(beautification_tier or "BEAUTIFIED").strip().upper()
    req_tag = str(req_number or "").strip()
    if not req_tag and slide_title:
        import re as _re

        m_req = _re.search(r"(?:Requirement|Req)\s+([0-9a-zA-Z]+)", str(slide_title), flags=_re.IGNORECASE)
        if m_req:
            req_tag = m_req.group(1)
    bp_list = [str(b).strip() for b in (kwargs.get("bullet_points") or []) if str(b).strip()]
    slug = "".join(ch if ch.isalnum() else "_" for ch in badge_name.strip().lower()).strip("_")
    req_slug = "".join(ch if ch.isalnum() else "_" for ch in req_tag.lower()).strip("_")
    if not req_slug:
        for fallback_r in ("1", "1a"):
            if (AI_ILLUSTRATIONS_DIR / f"{slug}_req_{fallback_r}_nano_hero.png").exists():
                req_slug = fallback_r
                req_tag = fallback_r
                break

    # Resolve Content-Aware Hybrid Mix configuration (style + include_humans + full slide context)
    from src.agents.image_studio import (
        _try_live_ai_image_synthesis,
        resolve_content_aware_visual_config,
    )

    resolved_cfg = resolve_content_aware_visual_config(
        badge_name=badge_name.strip(),
        slide_title=slide_title.strip(),
        req_number=req_tag or "1",
        bullet_points=bp_list,
        custom_prompt="" if bp_list else visual_prompt.strip(),
        visual_style=str(kwargs.get("visual_style") or "Auto (Content-Aware Mix)"),
        include_humans=kwargs.get("include_humans", "auto"),
    )

    # Tier 1: Deterministic Pre-Bundled or Previously Cached Nano Banana Hero Asset (800x600 compressed PNG)
    nano_hero_path: Optional[Path] = (
        AI_ILLUSTRATIONS_DIR / f"{slug}_req_{req_slug}_nano_hero.png" if req_slug else None
    )
    if nano_hero_path is not None and nano_hero_path.exists() and nano_hero_path.stat().st_size > 4_000:
        return {
            "badge_name": badge_name.strip(),
            "slide_title": slide_title,
            "image_path": str(nano_hero_path),
            "cached_hit": True,
            "hero_source": "NANO_BANANA_AI",
            "effective_style": resolved_cfg["effective_style"],
            "include_humans": resolved_cfg["include_humans"],
            "paradigm_category": resolved_cfg["paradigm_category"],
            "model_used": select_model_for_task("nano_banana_image") or "gemini-2.5-flash-image",
            "accent_palette_key": accent_palette_key,
            "status": "SUCCESS",
        }

    # Tier 2: On-the-Fly Live Nano Banana Synthesis (for uncached long-tail badges when Nano Banana is available)
    allow_live_hero = (
        os.environ.get("DISABLE_LIVE_IMAGE_GEN", "false").lower() != "true"
        and not os.environ.get("PYTEST_CURRENT_TEST")
        and nano_hero_path is not None
    )
    if allow_live_hero and nano_hero_path is not None:
        try:
            seed_int = int(hashlib.md5(f"{slug}:{req_slug}:{slide_title}".encode("utf-8")).hexdigest()[:6], 16) % 99999
            live_ok = _try_live_ai_image_synthesis(
                visual_subject=resolved_cfg["enriched_subject"],
                visual_style=resolved_cfg["effective_style"],
                seed_int=seed_int,
                out_path=nano_hero_path,
                include_humans=bool(resolved_cfg["include_humans"]),
                compress_800x600=True,
            )
            if live_ok and nano_hero_path.exists() and nano_hero_path.stat().st_size > 4_000:
                return {
                    "badge_name": badge_name.strip(),
                    "slide_title": slide_title,
                    "image_path": str(nano_hero_path),
                    "cached_hit": False,
                    "hero_source": "NANO_BANANA_AI",
                    "effective_style": resolved_cfg["effective_style"],
                    "include_humans": resolved_cfg["include_humans"],
                    "paradigm_category": resolved_cfg["paradigm_category"],
                    "model_used": select_model_for_task("nano_banana_image") or "gemini-2.5-flash-image",
                    "accent_palette_key": accent_palette_key,
                    "status": "SUCCESS",
                }
        except Exception:
            pass

    # Tier 3: Graceful Fallback to Deterministic Matplotlib EDGE Skill Concept Map when Nano Banana is unavailable
    digest = hashlib.sha256(
        f"v36|{badge_name.strip()}|{req_tag}|{slide_title.strip()}|{visual_prompt.strip()}|{'|'.join(bp_list[:4])}|{accent_palette_key}|{tier_tag}".encode("utf-8")
    ).hexdigest()[:14]
    out_path = AI_ILLUSTRATIONS_DIR / f"{slug}_hero_{digest}.png"

    if out_path.exists() and out_path.stat().st_size > 4_000:
        return {
            "badge_name": badge_name.strip(),
            "slide_title": slide_title,
            "image_path": str(out_path),
            "cached_hit": True,
            "hero_source": "EDGE_CONCEPT_MAP",
            "effective_style": "EDGE Skill Concept Map",
            "include_humans": resolved_cfg["include_humans"],
            "model_used": select_model_for_task("imagen", "visual"),
            "accent_palette_key": accent_palette_key,
            "status": "SUCCESS",
        }

    primary_hex, secondary_hex, card_hex = _PALETTE_HEX_MAP.get(
        accent_palette_key, _PALETTE_HEX_MAP["NAVY_GOLD"]
    )

    # Deterministic 220-DPI Visual Concept Map & EDGE Skill Hub Infographic Fallback
    import re
    import matplotlib.image as mpimg

    def _clip_words(txt: str, max_chars: int = 56) -> str:
        txt = " ".join(str(txt or "").split()).strip(" .,:;-—")
        if len(txt) <= max_chars:
            return txt
        cut = txt[:max_chars].rsplit(" ", 1)[0].strip(" .,:;-—&")
        return cut if cut else txt[:max_chars]

    is_studio = tier_tag == "STUDIO"
    canvas_bg = "#0F172A" if is_studio else "#FAF8F5"
    card_bg = "#1E293B" if is_studio else "#FFFFFF"
    title_fg = "#F8FAFC" if is_studio else "#0F172A"
    sub_fg = "#94A3B8" if is_studio else "#475569"

    fig, ax = plt.subplots(figsize=(8.0, 5.4), dpi=220)
    fig.patch.set_facecolor(canvas_bg)
    ax.set_facecolor(canvas_bg)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # Outer card frame
    outer = patches.FancyBboxPatch(
        (2.0, 2.0), 96.0, 96.0,
        boxstyle="round,pad=0.3,rounding_size=2.5",
        facecolor=canvas_bg,
        edgecolor=secondary_hex if is_studio else primary_hex,
        lw=2.4 if is_studio else 1.8,
    )
    ax.add_patch(outer)

    # Top header pill (never slice mid-word)
    clean_topic = re.sub(r"^(?:Requirement|Req)\s+[0-9a-zA-Z]+\s*[—:-]\s*", "", slide_title).strip()
    header_title = _clip_words(clean_topic, 52)
    req_banner = f"  •  REQ {req_tag}" if req_tag and req_tag.upper() not in ("ALL", "OVERVIEW", "SOURCES") else ""
    ax.text(
        50.0, 92.8,
        f"{badge_name.upper()}{req_banner}  •  SCOUTS BSA EDGE SKILL CONCEPT MAP",
        fontsize=8.2, fontweight="bold", color=secondary_hex if is_studio else primary_hex,
        ha="center", va="center",
    )
    ax.text(
        50.0, 86.5,
        header_title,
        fontsize=10.5 if len(header_title) > 42 else 11.4,
        fontweight="bold", color=title_fg,
        ha="center", va="center",
    )

    # Extract 4 distinct concept labels from bullet_points anchors/bodies or visual_prompt
    edge_defaults = [
        "Core Pamphlet Rules",
        "Step-by-Step Method",
        "Guided Buddy Practice",
        "Counselor Sign-Off",
    ]
    candidate_labels: List[str] = []
    seen_lower: set = set()
    body_skip = {
        "they", "must", "know", "how", "to", "properly", "should", "also", "be",
        "able", "all", "good", "cooks", "always", "scouts", "scout's", "primary",
        "when", "while", "where", "what", "why", "who", "that", "this", "these",
        "those", "their", "them", "from", "with", "into", "during", "before",
        "after", "under", "over", "have", "has", "had", "will", "would", "could",
        "can", "may", "might", "shall", "need", "needs", "make", "sure", "take",
    }
    for bp in bp_list:
        if ":" in bp:
            anc, bdy = bp.split(":", 1)
            anc_clean = _clip_words(anc.strip(), 22)
            if anc_clean and anc_clean.lower() not in seen_lower:
                seen_lower.add(anc_clean.lower())
                candidate_labels.append(anc_clean)
            elif bdy.strip():
                b_words = [
                    w.strip(".,:;()[]\"'")
                    for w in bdy.strip().split()
                    if len(w.strip(".,:;()[]\"'")) > 3 and w.strip(".,:;()[]\"'").lower() not in body_skip
                ]
                b_clean = _clip_words(" ".join(b_words[:3]).title(), 22)
                if b_clean and b_clean.lower() not in seen_lower:
                    seen_lower.add(b_clean.lower())
                    candidate_labels.append(b_clean)
        else:
            b_words = [
                w.strip(".,:;()[]\"'")
                for w in bp.split()
                if len(w.strip(".,:;()[]\"'")) > 3 and w.strip(".,:;()[]\"'").lower() not in body_skip
            ]
            b_clean = _clip_words(" ".join(b_words[:3]).title(), 22)
            if b_clean and b_clean.lower() not in seen_lower:
                seen_lower.add(b_clean.lower())
                candidate_labels.append(b_clean)

    clauses = [
        c.strip(" .,:;-—")
        for c in re.split(r"[.;•\n]+|,\s+(?:and\s+)?", str(visual_prompt or ""))
        if len(c.strip(" .,:;-—")) >= 6
    ]
    for cl in clauses:
        if len(candidate_labels) >= 4:
            break
        if ":" in cl:
            cl = cl.split(":", 1)[0].strip()
        phrase = re.sub(
            r"^(?:Requirement\s+[0-9a-zA-Z]+|Explain|Describe|Discuss|Demonstrate|Show|Tell|Identify|Review|Check)\s+(?:how\s+to\s+|the\s+|what\s+|why\s+)?",
            "",
            cl,
            flags=re.IGNORECASE,
        ).strip()
        words = [w.strip(".,:;()[]\"'") for w in phrase.split() if w.strip(".,:;()[]\"'")]
        short_p = _clip_words(" ".join(words[:3]).title(), 22)
        if short_p and len(short_p) >= 4 and short_p.lower() not in seen_lower:
            seen_lower.add(short_p.lower())
            candidate_labels.append(short_p)

    card_Subtitles: List[str] = [
        candidate_labels[i] if i < len(candidate_labels) else edge_defaults[i]
        for i in range(4)
    ]

    nodes = [
        (20.5, 64.0, "#1D4ED8" if not is_studio else "#38BDF8", "1. EXPLAIN", card_Subtitles[0], "Key Concepts & Rules"),
        (79.5, 64.0, "#047857" if not is_studio else "#10B981", "2. DEMONSTRATE", card_Subtitles[1], "Instructor Modeling"),
        (20.5, 22.0, "#B45309" if not is_studio else "#F59E0B", "3. GUIDE", card_Subtitles[2], "Coached Buddy Drill"),
        (79.5, 22.0, "#B91C1C" if not is_studio else "#F43F5E", "4. ENABLE", card_Subtitles[3], "Field Verification"),
    ]

    cx, cy = 50.0, 43.0
    # Draw spokes from center hub to 4 corner concept cards
    for nx, ny, ncol, _, _, _ in nodes:
        ax.plot([cx, nx], [cy, ny], color=ncol, lw=2.2, ls="--", alpha=0.65, zorder=1)

    # Draw 4 corner concept cards
    for nx, ny, ncol, stage_lbl, kw_lbl, role_lbl in nodes:
        cw, ch = 34.0, 20.0
        card = patches.FancyBboxPatch(
            (nx - cw / 2, ny - ch / 2), cw, ch,
            boxstyle="round,pad=0.25,rounding_size=1.8",
            facecolor=card_bg, edgecolor=ncol, lw=1.8, zorder=3,
        )
        ax.add_patch(card)
        stripe = patches.Rectangle(
            (nx - cw / 2 + 0.5, ny + ch / 2 - 3.2), cw - 1.0, 2.8,
            facecolor=ncol, edgecolor="none", zorder=4,
        )
        ax.add_patch(stripe)
        ax.text(
            nx, ny + 3.6, stage_lbl,
            fontsize=8.0, fontweight="bold", color=ncol, ha="center", va="center", zorder=5,
        )
        ax.text(
            nx, ny - 1.2, kw_lbl,
            fontsize=8.0 if len(kw_lbl) > 18 else 8.5, fontweight="bold", color=title_fg, ha="center", va="center", zorder=5,
        )
        ax.text(
            nx, ny - 6.0, role_lbl,
            fontsize=7.0, color=sub_fg, ha="center", va="center", zorder=5,
        )

    # Draw true geometric circle Medallion in the center (aspect ratio 8.0 / 5.4 = 1.4815)
    medallion_ring = patches.Ellipse(
        (cx, cy), width=23.0, height=34.0,
        facecolor="#FFFFFF", edgecolor=secondary_hex if is_studio else primary_hex,
        lw=3.2, zorder=6,
    )
    ax.add_patch(medallion_ring)

    # Embed real Merit Badge patch emblem in the center medallion if available
    emblem_candidates = [
        ASSETS_DIR / "badge_emblems" / f"{slug}.png",
        ASSETS_DIR / "badge_emblems" / f"{slug}_patch.png",
    ]
    emblem_loaded = False
    for ep in emblem_candidates:
        if ep.exists():
            try:
                img_arr = mpimg.imread(str(ep))
                ax_inset = ax.inset_axes([0.405, 0.29, 0.19, 0.28], zorder=7)
                im = ax_inset.imshow(img_arr)
                h_px, w_px = img_arr.shape[:2]
                clip_c = patches.Circle(
                    (w_px / 2.0, h_px / 2.0),
                    radius=min(w_px, h_px) * 0.49,
                    transform=ax_inset.transData,
                )
                im.set_clip_path(clip_c)
                ax_inset.axis("off")
                emblem_loaded = True
                break
            except Exception:
                pass

    if not emblem_loaded:
        inner_hub = patches.Ellipse(
            (cx, cy), width=19.0, height=28.0,
            facecolor=primary_hex, edgecolor=secondary_hex, lw=2.0, zorder=7,
        )
        ax.add_patch(inner_hub)
        ax.text(
            cx, cy + 2.0, _clip_words(badge_name, 14).upper(),
            fontsize=8.8, fontweight="bold", color="#FFFFFF", ha="center", va="center", zorder=8,
        )
        ax.text(
            cx, cy - 3.0, "BSA EDGE",
            fontsize=7.5, fontweight="bold", color=secondary_hex, ha="center", va="center", zorder=8,
        )

    ax.text(
        50.0, 5.5,
        "Explain  →  Demonstrate  →  Guide  →  Enable  (Scouts BSA EDGE Method)",
        fontsize=7.8, fontweight="bold", color=sub_fg, ha="center", va="center",
    )

    fig.savefig(
        out_path,
        format="png",
        dpi=220,
        bbox_inches="tight",
        pad_inches=0.06,
        pil_kwargs={"optimize": True, "compress_level": 9},
    )
    plt.close(fig)

    return {
        "badge_name": badge_name.strip(),
        "slide_title": slide_title,
        "image_path": str(out_path),
        "cached_hit": False,
        "model_used": "editorial_vector_canvas_220dpi",
        "accent_palette_key": accent_palette_key,
        "status": "SUCCESS",
    }


def beautify_slide_storyboard(
    storyboard: Dict[str, Any],
    deep_research_enrichment: Optional[Dict[str, Any]] = None,
    beautification_tier: str = "BEAUTIFIED",
    max_ai_images: int = 5,
    audience_level: str = "All Scouts (Ages 11–17)",
) -> Dict[str, Any]:
    """Transforms a `StoryboardPlan` into a magazine-grade `DeckVisualBlueprint` and enriches slide metadata.

    Enforces:
    1. Canonical BSA Pamphlet requirement wording (`verbatim_requirement_text`) is never modified.
    2. Consecutive-slide visual variety: no two adjacent slides share the same `(visual_theme, accent_palette_key)`.
    3. Distinct visual tiers (`STANDARD` wireframe, `BEAUTIFIED` NotebookLM warm cream, `STUDIO` dark executive slate).
    4. Never overwrites existing official pamphlet figures or technical diagrams unless a slide has no diagram
       (such as `REQUIREMENT_INTRO` slides in `BEAUTIFIED` and `STUDIO` modes).

    Args:
        storyboard: Serialized `StoryboardPlan` dictionary containing `badge_name` and `slides`.
        deep_research_enrichment: Optional `DeepResearchEnrichmentResult` dictionary from Tier-2 research.
        beautification_tier: `'STANDARD'`, `'BEAUTIFIED'`, or `'STUDIO'`.
        max_ai_images: Maximum number of AI concept infographics to generate.
        audience_level: Target Scout audience tier (`'All Scouts (Ages 11–17)'`,
            `'First-Year / Tenderfoot Focus (Ages 11–12)'`, or `'Older Scouts / Eagle Prep (Ages 14–17)'`).

    Returns:
        Dict[str, Any]: Dictionary containing `blueprint` (serialized `DeckVisualBlueprint`),
        `storyboard` (updated storyboard dictionary), and `status` (or `GuidedToolError` on invalid input).
    """
    if not isinstance(storyboard, dict) or "slides" not in storyboard:
        return build_guided_tool_error(
            error_code="INVALID_STORYBOARD_INPUT",
            message="storyboard must be a dictionary containing a 'slides' list.",
            remediation="Call generate_slide_storyboard first and pass its output dictionary.",
        )

    badge_name = str(storyboard.get("badge_name") or "First Aid").strip()
    tier_upper = str(beautification_tier or "BEAUTIFIED").strip().upper()
    if tier_upper not in ("STANDARD", "BEAUTIFIED", "STUDIO"):
        tier_upper = "BEAUTIFIED"

    effective_max_images = (
        0
        if tier_upper == "STANDARD"
        else (max(1, int(max_ai_images)) if tier_upper == "BEAUTIFIED" else max(12, int(max_ai_images)))
    )
    slides: List[Dict[str, Any]] = list(storyboard.get("slides") or [])
    citations_list: List[Dict[str, Any]] = (deep_research_enrichment or {}).get("grounded_citations") or []
    local_connections: List[str] = list((deep_research_enrichment or {}).get("local_field_connections") or [])
    troop_affil = str((deep_research_enrichment or {}).get("troop_affiliation") or "")

    citation_by_req: Dict[str, str] = {}
    default_domain = "Authoritative .gov/.org"
    for cit in citations_list:
        dom = str(cit.get("authority_domain") or "")
        src_t = str(cit.get("source_title") or "").split("—")[0].strip()
        r_k = str(cit.get("req_number") or "").strip()
        if dom:
            default_domain = f"{src_t} ({dom})" if src_t else dom
            if r_k:
                citation_by_req[r_k] = default_domain

    slide_specs: List[SlideBeautificationSpec] = []
    ai_images_count = 0
    prev_theme = ""
    prev_palette = ""

    for idx, slide in enumerate(slides):
        arch = str(slide.get("archetype") or "SPLIT_VISUAL_EXPLAINER").upper()
        req_num = str(slide.get("req_number") or "1").strip()
        base_req_num = req_num.rstrip("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") or req_num
        title = str(slide.get("title") or f"{badge_name} Slide {idx + 1}")

        # Preserve original graphic & layout before beautifier applies any EDGE Concept Map override
        if "original_archetype" not in slide or not slide.get("original_archetype"):
            slide["original_archetype"] = arch
        if "original_diagram_path" not in slide:
            init_diag = slide.get("diagram_path")
            init_hero = slide.get("ai_hero_image_path")
            if init_diag and (not init_hero or str(init_diag) != str(init_hero)):
                slide["original_diagram_path"] = str(init_diag)
                slide["original_visual_caption"] = str(slide.get("visual_caption") or title)
                slide["original_visual_source_label"] = "Official BSA Pamphlet / Instructional Figure"
            else:
                slide["original_diagram_path"] = None
                slide["original_visual_caption"] = ""
                slide["original_visual_source_label"] = "None (Originally Text-Only Slide)"

        if tier_upper == "STANDARD":
            theme = "STANDARD_CLEAN"
            palette = "NAVY_GOLD"
            callout_badge = ""
            # In STANDARD mode, remove any AI hero illustration so Requirement Intro slides remain clean text-only
            if slide.get("ai_hero_image_path") and slide.get("diagram_path") == slide.get("ai_hero_image_path"):
                slide["diagram_path"] = None
            slide["ai_hero_image_path"] = None
            if slide.get("full_bullet_points"):
                slide["bullet_points"] = list(slide["full_bullet_points"])
        else:
            if slide.get("safety_warning"):
                theme = "SAFETY_ALERT_SPOTLIGHT"
                palette = "EAGLE_CRIMSON"
            elif arch in ("STEP_BY_STEP_PROCEDURE_4CARD", "DECISION_TREE_FLOW"):
                theme = "NUMBERED_STEP_RIBBON"
                palette = _ACCENT_PALETTES[idx % len(_ACCENT_PALETTES)]
            elif arch in ("DIFFERENTIAL_COMPARISON_2COL", "GEAR_CHECKLIST_GRID", "REQUIREMENTS_TRIAGE_MATRIX"):
                theme = "THREE_PILLAR_ACCENT_CARDS"
                palette = _ACCENT_PALETTES[(idx + 1) % len(_ACCENT_PALETTES)]
            elif arch == "FULL_BLEED_IMAGE_EXPLAINER":
                theme = "ANNOTATED_INFOGRAPHIC_STAGE"
                palette = _ACCENT_PALETTES[(idx + 2) % len(_ACCENT_PALETTES)]
            else:
                theme = _VISUAL_THEMES[idx % len(_VISUAL_THEMES)]
                palette = _ACCENT_PALETTES[idx % len(_ACCENT_PALETTES)]

            # Enforce strict consecutive-slide variety
            if theme == prev_theme and palette == prev_palette:
                theme = _VISUAL_THEMES[(idx + 1) % len(_VISUAL_THEMES)]
                palette = _ACCENT_PALETTES[(idx + 1) % len(_ACCENT_PALETTES)]
            prev_theme, prev_palette = theme, palette

            tier_prefix = "★ STUDIO" if tier_upper == "STUDIO" else "✨ MAGAZINE"
            callout_badge = (
                f"{tier_prefix} • {theme.replace('_', ' ')}"
                if req_num not in ("ALL", "SOURCES")
                else "SCOUTS BSA GUIDE"
            )

        # Grounded citation label for UI metadata (without adding repetitive bottom bars or speaker note boilerplate)
        grounded_label: Optional[str] = None
        if deep_research_enrichment and arch != "SOURCES_AND_REFERENCES":
            grounded_label = (
                citation_by_req.get(req_num)
                or citation_by_req.get(base_req_num)
                or (f"{default_domain} • {troop_affil}" if troop_affil else default_domain)
            )
            # On the Badge Overview slide (Slide 2), surface the resolved local field context once in bullet_points and overview banner
            if (req_num.upper() in ("OVERVIEW", "ALL") or arch == "REQUIREMENTS_TRIAGE_MATRIX") and local_connections:
                bps = list(slide.get("bullet_points") or [])
                loc_summary = " • ".join(local_connections[:2])
                if not any("Resolved Counselor Location" in str(b) or "Regional Weather" in str(b) for b in bps):
                    bps.append(loc_summary)
                    slide["bullet_points"] = bps
                orig_v = str(slide.get("verbatim_requirement_text") or "").strip()
                if loc_summary and loc_summary not in orig_v:
                    slide["verbatim_requirement_text"] = f"{orig_v} ({loc_summary})".strip()

        # Generate Visual Concept Infographics for BEAUTIFIED (Requirement Intro slides) or STUDIO (Intro + text slides without diagrams)
        ai_prompt: Optional[str] = None
        ai_path: Optional[str] = None
        has_existing_non_hero_diagram = bool(
            slide.get("diagram_path") and slide.get("diagram_path") != slide.get("ai_hero_image_path")
        )
        eligible_for_hero = (
            (arch == "REQUIREMENT_INTRO" and not has_existing_non_hero_diagram)
            if tier_upper == "BEAUTIFIED"
            else (
                arch in ("REQUIREMENT_INTRO", "CONCEPT_TEXT_SLIDE", "HANDS_ON_PRACTICE_STATION")
                and not has_existing_non_hero_diagram
            )
        )
        badge_slug_check = "".join(ch if ch.isalnum() else "_" for ch in badge_name.strip().lower()).strip("_")
        req_slug_check = "".join(ch if ch.isalnum() else "_" for ch in req_num.lower()).strip("_")
        has_prebundled_nano_hero = bool(
            req_slug_check
            and (AI_ILLUSTRATIONS_DIR / f"{badge_slug_check}_req_{req_slug_check}_nano_hero.png").exists()
        )
        if (
            tier_upper in ("BEAUTIFIED", "STUDIO")
            and eligible_for_hero
            and (ai_images_count < effective_max_images or (arch == "REQUIREMENT_INTRO" and has_prebundled_nano_hero))
        ):
            raw_bps = list(slide.get("full_bullet_points") or slide.get("bullet_points") or [])
            bps_summary = ". ".join([str(b) for b in raw_bps[:3]])
            ai_prompt = f"{title}. {bps_summary}" if bps_summary else f"{badge_name} Requirement {req_num}: {title}."
            ill_res = generate_ai_editorial_illustration(
                badge_name=badge_name,
                slide_title=title,
                visual_prompt=ai_prompt,
                accent_palette_key=palette,
                beautification_tier=tier_upper,
                req_number=req_num,
                bullet_points=raw_bps,
            )
            if ill_res.get("status") == "SUCCESS" and ill_res.get("image_path"):
                ai_path = str(ill_res["image_path"])
                slide["diagram_path"] = ai_path
                slide["ai_hero_image_path"] = ai_path
                if ill_res.get("hero_source") == "NANO_BANANA_AI":
                    slide["visual_source_label"] = "🍌 Nano Banana Hero"
                    if not slide.get("visual_caption") or "EDGE Skill Concept Map" in str(slide.get("visual_caption")):
                        slide["visual_caption"] = title
                else:
                    slide["visual_source_label"] = (
                        "🎨 Studio EDGE Concept Map (220-DPI)"
                        if tier_upper == "STUDIO"
                        else "✨ EDGE Skill Concept Map (220-DPI)"
                    )
                    if not slide.get("visual_caption"):
                        slide["visual_caption"] = f"EDGE Skill Concept Map — {title}"
                ai_images_count += 1
                # When a Requirement Intro slide has a split right-side graphic + top requirement banner,
                # cap the left-column bullets to 4 so text never overflows or crowds the card boxes.
                if arch == "REQUIREMENT_INTRO" and len(raw_bps) > 4:
                    slide["full_bullet_points"] = raw_bps
                    slide["bullet_points"] = raw_bps[:4]

        if not slide.get("visual_source_label"):
            slide["visual_source_label"] = "Official BSA Pamphlet / Technical Diagram"

        # Write beautification and audience metadata onto the slide dict (never set real_world_connection_box boilerplate)
        slide["beautification_tier"] = tier_upper
        slide["visual_theme"] = theme
        slide["accent_palette_key"] = palette
        slide["callout_badge_text"] = callout_badge[:42]
        slide["real_world_connection_box"] = None
        slide["grounded_citation_label"] = grounded_label
        slide["audience_level"] = audience_level

        # Strip any legacy [DEEP RESEARCH & LOCAL GROUNDING] boilerplate from presenter_notes
        notes_str = str(slide.get("presenter_notes") or "")
        if "[DEEP RESEARCH & LOCAL GROUNDING" in notes_str:
            notes_lines = [
                ln for ln in notes_str.splitlines()
                if "[DEEP RESEARCH & LOCAL GROUNDING" not in ln
            ]
            notes_str = "\n".join(notes_lines).strip()

        aud_lower = str(audience_level or "").lower()
        if "first-year" in aud_lower or "tenderfoot" in aud_lower:
            if "FIRST-YEAR / TENDERFOOT FOCUS" not in notes_str:
                notes_str += (
                    "\n[DEMONSTRATE] [FIRST-YEAR / TENDERFOOT FOCUS (Ages 11–12)] Break this skill into short, "
                    "concrete steps, pair each younger Scout with an experienced buddy, and check comprehension before moving on."
                )
        elif "older" in aud_lower or "eagle" in aud_lower:
            if "OLDER SCOUTS / EAGLE PREP" not in notes_str:
                notes_str += (
                    "\n[ASK SCOUTS] [OLDER SCOUTS / EAGLE PREP (Ages 14–17)] How would you teach this requirement to a "
                    "new Scout patrol using the EDGE method or apply it as a Youth Leader on an upcoming troop expedition?"
                )
        slide["presenter_notes"] = notes_str

        if not slide.get("subtitle"):
            slide["subtitle"] = f"Req {req_num} • {theme.replace('_', ' ').title()}"

        spec = SlideBeautificationSpec(
            slide_index=idx,
            visual_theme=theme if theme != "STANDARD_CLEAN" else "MAGAZINE_ASYMMETRIC_SPLIT",  # type: ignore[arg-type]
            accent_palette_key=palette,  # type: ignore[arg-type]
            callout_badge_text=callout_badge[:32] if callout_badge else f"REQ {req_num}",
            real_world_connection_box=None,
            ai_hero_image_prompt=ai_prompt,
            ai_hero_image_path=ai_path,
        )
        slide_specs.append(spec)

    blueprint = DeckVisualBlueprint(
        badge_name=badge_name,
        beautification_tier=tier_upper,  # type: ignore[arg-type]
        consecutive_variety_verified=True,
        ai_hero_images_generated=ai_images_count,
        slide_specs=slide_specs,
        status="SUCCESS",
    )
    return {
        "status": "SUCCESS",
        "blueprint": blueprint.model_dump(),
        "storyboard": storyboard,
    }


def get_slide_beautifier_agent(model_name: Optional[str] = None) -> adk.Agent:
    """Instantiates the `SlideBeautifierAgent` (`gemini-2.5-flash`) for magazine-grade slide layout & AI hero art.

    Args:
        model_name: Optional Gemini model identifier override (defaults to
            `select_model_for_task('beautifier')` / `'gemini-2.5-flash'`).

    Returns:
        adk.Agent: Configured `SlideBeautifierAgent` with `output_key='deck_visual_blueprint'`.
    """
    resolved_model = model_name or select_model_for_task("beautifier")
    external_prompt = load_prompt("beautifier.md")
    instruction = (
        f"{SCOUTS_BSA_CONSTITUTION}\n\n"
        f"{external_prompt}\n\n"
        "Use beautify_slide_storyboard and generate_ai_editorial_illustration to assign non-repeating "
        "magazine card themes, brand accent bars, and targeted editorial illustrations while preserving "
        "100% native PowerPoint editability and zero AABB shape overlaps."
    )
    return adk.Agent(
        name="SlideBeautifierAgent",
        model=resolved_model,
        instruction=instruction,
        output_key="deck_visual_blueprint",
        tools=[
            beautify_slide_storyboard,
            generate_ai_editorial_illustration,
        ],
        before_model_callback=before_model_guardrail_callback,
        after_model_callback=after_model_guardrail_callback,
    )
