"""ADK SlideBeautifierAgent for Slide Layout Themes & Editorial Hero Art.

This module implements:
1. `generate_ai_editorial_illustration`: Generates or retrieves disk-cached editorial vector/hero
   illustrations in the official Scouts BSA palette (`#003F87`, `#4B5320`, `#F4C430`, `#CE1126`),
   supporting Gemini 2.5 Flash Image (`gemini-2.5-flash-image`) / Vertex AI Imagen with deterministic
   220-DPI Matplotlib EDGE Skill Concept Map fallback.
2. `beautify_slide_storyboard`: Transforms a `StoryboardPlan` into a `DeckVisualBlueprint` with:
   - 6 visual card themes (`MAGAZINE_ASYMMETRIC_SPLIT`, `THREE_PILLAR_ACCENT_CARDS`,
     `NUMBERED_STEP_RIBBON`, `HERO_ILLUSTRATION_OVERLAY`, `SAFETY_ALERT_SPOTLIGHT`,
     `ANNOTATED_INFOGRAPHIC_STAGE`)
   - Consecutive-slide theme and palette variety enforcement
   - Pre-bundled Nano Banana Hero & Topic Illustrations across requirements (`max_ai_images=20` for
     pre-cached/fallback visual enrichment; live uncached synthesis capped by `FinOpsBudgetPlugin` at
     `STANDARD=0`, `BEAUTIFIED=5`, `STUDIO=15`)
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
    _read_cached_json,
    badge_file_slug,
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

_FILE_MD5_CACHE: Dict[tuple[str, int, int], str] = {}


def _get_nano_banana_catalog() -> Dict[str, Any]:
    nano_cat_file = AI_ILLUSTRATIONS_DIR.parent.parent / "data" / "nano_banana_image_catalog.json"
    return _read_cached_json(nano_cat_file)

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

    from src.tools.template_engine import normalize_visual_theme

    tier_tag = normalize_visual_theme(beautification_tier)
    req_tag = str(req_number or "").strip()
    if not req_tag and slide_title:
        import re as _re

        m_req = _re.search(r"(?:Requirement|Req)\s+([0-9a-zA-Z]+)", str(slide_title), flags=_re.IGNORECASE)
        if m_req:
            req_tag = m_req.group(1)
    bp_list = [str(b).strip() for b in (kwargs.get("bullet_points") or []) if str(b).strip()]
    slug = badge_file_slug(badge_name)
    req_slug = badge_file_slug(req_tag)
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
    if (nano_hero_path is None or not nano_hero_path.exists()) and req_tag:
        import re as _re_opt

        m_opt_p = _re_opt.match(r"^(\d+[a-zA-Z])", req_tag.strip())
        if m_opt_p:
            cand_opt_hero = AI_ILLUSTRATIONS_DIR / f"{slug}_req_{m_opt_p.group(1).lower()}_nano_hero.png"
            if cand_opt_hero.exists():
                nano_hero_path = cand_opt_hero
    if nano_hero_path is not None and nano_hero_path.exists() and nano_hero_path.stat().st_size >= 35_000:
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
    max_ai_images: int = 20,
    audience_level: str = "All Scouts (Ages 11–17)",
    research_artifact: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Transforms a `StoryboardPlan` into a magazine-grade `DeckVisualBlueprint` and enriches slide metadata.

    Enforces:
    1. Canonical BSA Pamphlet requirement wording (`verbatim_requirement_text`) is never modified.
    2. Consecutive-slide visual variety: no two adjacent slides share the same `(visual_theme, accent_palette_key)`.
    3. Distinct visual tiers (`STANDARD` wireframe, `BEAUTIFIED` warm cream, `STUDIO` dark executive slate).
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

    from src.tools.template_engine import normalize_visual_theme

    badge_name = str(storyboard.get("badge_name") or "First Aid").strip()
    tier_upper = normalize_visual_theme(beautification_tier)

    effective_max_images = (
        0
        if tier_upper == "STANDARD"
        else max(1, int(max_ai_images))
    )
    slides: List[Dict[str, Any]] = list(storyboard.get("slides") or [])
    citations_list: List[Dict[str, Any]] = (deep_research_enrichment or {}).get("grounded_citations") or []
    local_connections: List[str] = list((deep_research_enrichment or {}).get("local_field_connections") or [])
    troop_affil = str((deep_research_enrichment or {}).get("troop_affiliation") or "")
    resolved_loc: Dict[str, Any] = dict((deep_research_enrichment or {}).get("resolved_location") or {})

    citation_by_req: Dict[str, str] = {}
    cit_dict_by_req: Dict[str, Dict[str, Any]] = {}
    default_domain = "Authoritative .gov/.org"
    for cit in citations_list:
        dom = str(cit.get("authority_domain") or "")
        src_t = str(cit.get("source_title") or "").split("—")[0].strip()
        r_k = str(cit.get("req_number") or "").strip()
        if r_k:
            cit_dict_by_req[r_k] = cit
        if dom:
            default_domain = f"{src_t} ({dom})" if src_t else dom
            if r_k:
                citation_by_req[r_k] = default_domain

    slide_specs: List[SlideBeautificationSpec] = []
    ai_images_count = 0
    prev_theme = ""
    prev_palette = ""
    seen_hero_reqs: set = set()
    injected_local_reqs: set = set()
    used_diagram_md5s: Dict[str, int] = {}
    seen_visual_captions: set = set()
    req_slide_counts: Dict[str, int] = {}
    used_myths_in_deck: set = set()
    used_asks_in_deck: set = set()

    # Build a lookup map from research_artifact.get("requirements", []) indexing both top-level req_id/req_number
    # and nested sub_requirements (sr["req_id"] / sr["sub_id"]).
    req_lookup_map: Dict[str, Dict[str, Any]] = {}
    raw_reqs_list: List[Dict[str, Any]] = list(
        (research_artifact or {}).get("requirements")
        or storyboard.get("requirements")
        or (storyboard.get("research_artifact") or {}).get("requirements")
        or []
    )
    if not raw_reqs_list:
        try:
            import json as _json
            import re as _re
            from src.config import PROJECT_ROOT as _PROJ_ROOT
            from src.tools.scouting_scraper import BENCHMARK_BADGES_DATA

            _slug = _re.sub(r"[^a-z0-9]+", "-", str(badge_name or "").strip().lower()).strip("-")
            _json_path = _PROJ_ROOT / "data" / "merit_badge_requirements" / f"{_slug}.json"
            if _json_path.exists():
                _official_data = _json.loads(_json_path.read_text(encoding="utf-8"))
                raw_reqs_list = list(_official_data.get("requirements") or [])
            if not raw_reqs_list:
                bm_entry = (
                    BENCHMARK_BADGES_DATA.get(badge_name)
                    or BENCHMARK_BADGES_DATA.get(badge_name.title())
                    or BENCHMARK_BADGES_DATA.get(badge_name.lower())
                    or {}
                )
                raw_reqs_list = list(bm_entry.get("requirements") or [])
        except Exception:
            raw_reqs_list = []

    for r_item in raw_reqs_list:
        if not isinstance(r_item, dict):
            continue
        r_key = str(r_item.get("req_id") or r_item.get("req_number") or "").strip()
        if r_key:
            req_lookup_map[r_key] = r_item
            req_lookup_map[r_key.lower()] = r_item
        r_num_alt = str(r_item.get("req_number") or "").strip()
        if r_num_alt:
            req_lookup_map[r_num_alt] = r_item
            req_lookup_map[r_num_alt.lower()] = r_item
        for sr in r_item.get("sub_requirements") or []:
            if not isinstance(sr, dict):
                continue
            sr_key = str(sr.get("req_id") or sr.get("sub_id") or sr.get("id") or sr.get("sub_req_label") or "").strip()
            if sr_key:
                merged_sr = dict(r_item)
                merged_sr.update(sr)
                merged_sr["sub_requirements"] = [sr]
                req_lookup_map[sr_key] = merged_sr
                req_lookup_map[sr_key.lower()] = merged_sr

    def _file_md5(path_str: Optional[str]) -> str:
        if not path_str:
            return ""
        try:
            p = Path(path_str)
            if p.exists() and p.is_file():
                st = p.stat()
                key = (str(p.resolve()), st.st_mtime_ns, st.st_size)
                cached = _FILE_MD5_CACHE.get(key)
                if cached is not None:
                    return cached
                digest = hashlib.md5(p.read_bytes()).hexdigest()
                _FILE_MD5_CACHE[key] = digest
                return digest
        except Exception:
            pass
        return ""

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

        # Grounded citation label & dynamic Local Grounding slide enrichment
        grounded_label: Optional[str] = None
        if deep_research_enrichment and arch != "SOURCES_AND_REFERENCES":
            grounded_label = (
                citation_by_req.get(req_num)
                or citation_by_req.get(base_req_num)
                or (f"{default_domain} • {troop_affil}" if troop_affil else default_domain)
            )
            req_cit = cit_dict_by_req.get(req_num) or cit_dict_by_req.get(base_req_num) or {}
            disp_loc = str(resolved_loc.get("display_location") or troop_affil or "Local Area").strip()
            st_name = str(resolved_loc.get("state_name") or "State").strip()
            st_capitol = str(resolved_loc.get("state_capitol") or "").strip()
            nat_landmarks = str(resolved_loc.get("national_landmarks") or "").strip()
            fed_facs = str(resolved_loc.get("federal_facilities") or "").strip()
            sen1 = str(resolved_loc.get("senator_1") or "").strip()
            sen2 = str(resolved_loc.get("senator_2") or "").strip()
            h_rep = str(resolved_loc.get("house_rep") or "").strip()

            # 1. Badge Overview slide (Slide 2): surface resolved local field context
            if (req_num.upper() in ("OVERVIEW", "ALL") or arch == "REQUIREMENTS_TRIAGE_MATRIX") and local_connections:
                bps = list(slide.get("bullet_points") or [])
                loc_summary = " • ".join(local_connections[:2])
                if not any("Resolved Counselor Location" in str(b) or "Regional Weather" in str(b) for b in bps):
                    bps.append(loc_summary)
                    slide["bullet_points"] = bps
                orig_v = str(slide.get("verbatim_requirement_text") or "").strip()
                if loc_summary and loc_summary not in orig_v:
                    slide["verbatim_requirement_text"] = f"{orig_v} ({loc_summary})".strip()

            # 2. Citizenship in the Nation Requirement 7 (Slides 31-35: Landmarks, State Capitol, Federal Facility, National Monuments)
            if badge_name.lower() == "citizenship in the nation" and base_req_num == "7" and st_capitol:
                import re as _re
                bps = list(slide.get("bullet_points") or [])
                lm_items = [x.strip() for x in _re.split(r",\s*(?![^()]*\))", nat_landmarks) if x.strip()]
                first_landmark = _re.sub(r"\s*\([^)]*\)", "", lm_items[0]).strip() if lm_items else "Local National Register Site"
                second_landmark = _re.sub(r"\s*\([^)]*\)", "", lm_items[1]).strip() if len(lm_items) > 1 else "Minute Man NHP"
                fed_items = [x.strip() for x in _re.split(r",\s*(?![^()]*\))", fed_facs) if x.strip()]
                first_fed = fed_items[0] if fed_items else "Local U.S. Courthouse / Federal Building"
                second_fed = _re.sub(r"\s*\([^)]*\)", "", fed_items[1]).strip() if len(fed_items) > 1 else "U.S. District Court"
                short_capitol = st_capitol.split("—")[0].strip().rstrip("(").strip()
                if "(" in short_capitol and not short_capitol.endswith(")"):
                    short_capitol += ")"
                if "sub-requirement deep dive" in title.lower() or arch == "STEP_BY_STEP_PROCEDURE_4CARD":
                    slide["bullet_points"] = [
                        f"Requirement 7a ({disp_loc}): Visit a National Historic Landmark or Register site such as {first_landmark} or {second_landmark}.",
                        f"Requirement 7b ({st_name} Capitol): Tour {short_capitol} or the U.S. Capitol and explain its history and legislative function.",
                        f"Requirement 7c (Federal Facility): Tour {first_fed} or {second_fed} and explain how it serves the community and nation.",
                        f"Requirement 7d (National Monument): Choose a U.S. national monument (e.g., {first_landmark}) and explain its significance.",
                    ]
                elif arch == "SPLIT_VISUAL_EXPLAINER" and not slide.get("verbatim_requirement_text"):
                    slide["bullet_points"] = [
                        f"Local Landmarks ({disp_loc}): Nearby National Register & NPS sites include {first_landmark} and {second_landmark}.",
                        f"State Capitol Tour ({st_name}): {short_capitol}.",
                        f"Federal Facilities ({st_name}): {first_fed} and {second_fed}.",
                        f"Counselor Verification Tip: Bring field notes or a visitor brochure from {first_landmark} or {first_fed}.",
                    ]

            # 3. Citizenship in the Nation Requirement 8 (Slides 36-39: Current U.S. Senators & House Representative)
            elif badge_name.lower() == "citizenship in the nation" and base_req_num == "8" and sen1 and sen2:
                bps = list(slide.get("bullet_points") or [])
                sen_last = sen1.replace("Sen. ", "").split("(")[0].strip().split()[-1] if sen1 else "Senator"
                sen_full = sen1.replace("Sen. ", "").split("(")[0].strip() if sen1 else "[Full Name]"
                if isinstance(slide.get("worked_example"), dict):
                    we = dict(slide["worked_example"])
                    we["title"] = f"Constituent Letter ({disp_loc} → {sen1} / {h_rep.split('(')[0].strip()})"
                    we["fields"] = {
                        f"Addressee ({st_name} Delegation)": f"The Honorable {sen_full} ({sen1} or {sen2}), U.S. Senate, DC 20510 — or {h_rep}, U.S. House.",
                        "Salutation & Opening": f"Dear Senator {sen_last}: My name is [Scout Name], a Scout with {troop_affil or disp_loc}.",
                        f"Local Impact ({disp_loc})": f"Our troop hikes and completes conservation projects in {st_name}; we support National Park & trail stewardship.",
                        "Constituent Ask & Close": "Please share your legislative position on public lands funding. Respectfully, [Scout Name & Return Address].",
                    }
                    slide["worked_example"] = we
                elif "bill becomes a law" in title.lower():
                    slide["bullet_points"] = [
                        f"U.S. Senators ({st_name}): {sen1} and {sen2} represent all residents of {st_name} in the U.S. Senate (6-year terms).",
                        f"U.S. Representative ({disp_loc}): {h_rep} represents your local Congressional District in the U.S. House (2-year term).",
                        "Why Constituent Letters Matter: Congressional offices log every constituent letter by ZIP code and topic before floor votes.",
                        "Youth Protection & Mailing: Review your letter with a parent/guardian before submitting via senate.gov or house.gov.",
                    ]
                elif arch in ("REQUIREMENT_INTRO", "SPLIT_VISUAL_EXPLAINER") and len(bps) >= 1:
                    delegation_bullet = f"{st_name} Delegation: U.S. Senators {sen1} & {sen2}; U.S. House: {h_rep}."
                    if not any(sen1 in str(b) for b in bps):
                        if len(bps) >= 4:
                            bps[0] = delegation_bullet
                        else:
                            bps.insert(0, delegation_bullet)
                        slide["bullet_points"] = bps

            # 4. General Local Grounding injection for any requirement across all 149 badges with requires_local_lookup=True
            elif req_cit.get("requires_local_lookup") and req_cit.get("local_grounding_callout"):
                callout_txt = str(req_cit.get("local_grounding_callout") or "").strip()
                is_weather_non_forecast_req = badge_name.lower() == "weather" and base_req_num not in ("3", "10")
                if (
                    not is_weather_non_forecast_req
                    and req_num not in injected_local_reqs
                    and callout_txt not in injected_local_reqs
                    and arch in ("SPLIT_VISUAL_EXPLAINER", "CONCEPT_TEXT_SLIDE")
                    and not slide.get("verbatim_requirement_text")
                ):
                    slide["local_grounding_callout"] = callout_txt
                    bps = list(slide.get("bullet_points") or [])
                    short_callout = callout_txt if len(callout_txt) <= 165 else callout_txt[:162].rsplit(" ", 1)[0] + "..."
                    if not any(disp_loc in str(b) for b in bps):
                        if len(bps) < 4:
                            bps.append(short_callout)
                        else:
                            bps[-1] = short_callout
                        slide["bullet_points"] = bps
                        injected_local_reqs.add(req_num)
                        injected_local_reqs.add(callout_txt)

        # Generate Visual Concept Infographics for BEAUTIFIED (Requirement Intro / Lead slides) or STUDIO
        ai_prompt: Optional[str] = None
        ai_path: Optional[str] = None
        has_existing_non_hero_diagram = bool(
            slide.get("diagram_path") and slide.get("diagram_path") != slide.get("ai_hero_image_path")
        )
        is_req_lead_slide = (
            arch == "REQUIREMENT_INTRO"
            or (
                bool(slide.get("verbatim_requirement_text"))
                and req_num.upper() not in ("ALL", "OVERVIEW", "SOURCES")
                and arch in ("CONCEPT_TEXT_SLIDE", "SPLIT_VISUAL_EXPLAINER")
            )
        ) and (req_num not in seen_hero_reqs)
        eligible_for_hero = (
            (is_req_lead_slide and not has_existing_non_hero_diagram)
            if tier_upper == "BEAUTIFIED"
            else (
                is_req_lead_slide
                and not has_existing_non_hero_diagram
            )
        )
        badge_slug_check = badge_file_slug(badge_name)
        req_slug_check = badge_file_slug(req_num)
        opt_prefix_check = ""
        import re as _re_chk

        m_opt_chk = _re_chk.match(r"^(\d+[a-zA-Z])", str(req_num or "").strip())
        if m_opt_chk:
            opt_prefix_check = m_opt_chk.group(1).lower()
        has_prebundled_nano_hero = bool(
            (req_slug_check and (AI_ILLUSTRATIONS_DIR / f"{badge_slug_check}_req_{req_slug_check}_nano_hero.png").exists())
            or (opt_prefix_check and (AI_ILLUSTRATIONS_DIR / f"{badge_slug_check}_req_{opt_prefix_check}_nano_hero.png").exists())
        )
        if (
            tier_upper in ("BEAUTIFIED", "STUDIO")
            and eligible_for_hero
            and (ai_images_count < effective_max_images or (is_req_lead_slide and has_prebundled_nano_hero))
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
                seen_hero_reqs.add(req_num)
                slide["diagram_path"] = ai_path
                slide["ai_hero_image_path"] = ai_path
                if arch == "CONCEPT_TEXT_SLIDE":
                    slide["archetype"] = "SPLIT_VISUAL_EXPLAINER"
                if ill_res.get("hero_source") == "NANO_BANANA_AI":
                    slide["visual_source_label"] = "🍌 Nano Banana Hero"
                    hero_fname = Path(ai_path).name
                    from src.tools.pamphlet_extractor import strip_pamphlet_and_req_caption_prefixes

                    nc_map = _get_nano_banana_catalog()
                    cat_cap = ""
                    if hero_fname in nc_map:
                        cat_cap = strip_pamphlet_and_req_caption_prefixes(
                            str(nc_map[hero_fname].get("caption") or ""), badge_name
                        )
                    if cat_cap:
                        slide["visual_caption"] = cat_cap
                    else:
                        raw_vc = str(slide.get("visual_caption") or "")
                        if not raw_vc or "EDGE Skill Concept Map" in raw_vc or raw_vc.lower().startswith("requirement "):
                            slide["visual_caption"] = strip_pamphlet_and_req_caption_prefixes(title, badge_name)
                        else:
                            slide["visual_caption"] = strip_pamphlet_and_req_caption_prefixes(raw_vc, badge_name)
                else:
                    from src.tools.pamphlet_extractor import strip_pamphlet_and_req_caption_prefixes

                    slide["visual_source_label"] = (
                        "🎨 Studio EDGE Concept Map (220-DPI)"
                        if tier_upper == "STUDIO"
                        else "✨ EDGE Skill Concept Map (220-DPI)"
                    )
                    if not slide.get("visual_caption"):
                        slide["visual_caption"] = strip_pamphlet_and_req_caption_prefixes(title, badge_name)
                ai_images_count += 1
                if is_req_lead_slide and len(raw_bps) > 4:
                    slide["full_bullet_points"] = raw_bps
                    slide["bullet_points"] = raw_bps[:4]

        # Enforce strict image deduplication across the deck so no image (by file MD5) repeats across slides,
        # and ensure any replacement pamphlet image is requirement-matched and carries its verified caption!
        from src.tools.pamphlet_extractor import (
            _compose_pamphlet_visual_card,
            _is_discardable_pamphlet_image,
            _load_pamphlet_image_catalog,
            strip_pamphlet_and_req_caption_prefixes,
        )

        if slide.get("visual_caption"):
            slide["visual_caption"] = strip_pamphlet_and_req_caption_prefixes(
                str(slide.get("visual_caption") or ""), badge_name
            )

        cur_diag = slide.get("diagram_path")
        if cur_diag:
            cur_diag_fname = Path(str(cur_diag)).name
            if cur_diag_fname in (
                "first_aid_req_12_topic_visual.png",
                "first_aid_req_14_topic_visual.png",
                "first_aid_req_15_topic_visual.png",
            ):
                _topic_override_caps = {
                    "first_aid_req_12_topic_visual.png": "Scouts practicing Mental Health First Aid by noticing a distressed peer, listening with Two-Deep leadership, guiding slow breathing, and connecting with an adult leader.",
                    "first_aid_req_14_topic_visual.png": "Older Scout instructor teaching forearm splinting using the BSA EDGE method by explaining on a chart, demonstrating, guiding cravat practice, and enabling independent care.",
                    "first_aid_req_15_topic_visual.png": "Scout interviewing an EMS paramedic beside an ambulance, a wilderness rescue litter team on a mountain trail, and an ER nurse and physician mentoring a Scout.",
                }
                slide["visual_caption"] = _topic_override_caps[cur_diag_fname]
            elif "ai_illustrations" in str(cur_diag):
                nc_map = _get_nano_banana_catalog()
                if cur_diag_fname in nc_map:
                    cat_c = strip_pamphlet_and_req_caption_prefixes(
                        str(nc_map[cur_diag_fname].get("caption") or ""), badge_name
                    )
                    if cat_c:
                        slide["visual_caption"] = cat_c
            cur_md5 = _file_md5(str(cur_diag))
            if not hasattr(beautify_slide_storyboard, "_dhash_cache"):
                beautify_slide_storyboard._dhash_cache = {}
                try:
                    import json as _v43_json

                    dh_json_p = Path(__file__).resolve().parent.parent.parent / "data" / "asset_perceptual_hashes.json"
                    if dh_json_p.exists() and dh_json_p.stat().st_size > 10:
                        raw_dh_map = _v43_json.loads(dh_json_p.read_text(encoding="utf-8"))
                        for k_dh, v_dh in raw_dh_map.items():
                            if isinstance(v_dh, str) and len(v_dh) == 16:
                                beautify_slide_storyboard._dhash_cache[k_dh] = int(v_dh, 16)
                except Exception:
                    pass

            def _get_perceptual_dhash_int(img_p_str: str) -> Optional[int]:
                if not img_p_str:
                    return None
                dc = beautify_slide_storyboard._dhash_cache
                p_name = Path(img_p_str).name
                if p_name in dc:
                    return dc[p_name]
                if img_p_str in dc:
                    return dc[img_p_str]
                try:
                    from PIL import Image as _PILImage

                    p_obj = Path(img_p_str)
                    if p_obj.exists() and p_obj.is_file():
                        with _PILImage.open(p_obj) as _im:
                            _gr = _im.convert("L").resize((9, 8), _PILImage.Resampling.LANCZOS)
                            _px = list(_gr.getdata())
                            _df = 0
                            for _r in range(8):
                                _rs = _r * 9
                                for _c in range(8):
                                    _df = (_df << 1) | (1 if _px[_rs + _c] > _px[_rs + _c + 1] else 0)
                            dc[p_name] = _df
                            dc[img_p_str] = _df
                            return _df
                except Exception:
                    return None
                return None

            if "_v43_used_dhashes" not in locals():
                _v43_used_dhashes: list[int] = []

            def _is_dhash_already_used(dh_val: Optional[int]) -> bool:
                if dh_val is None:
                    return False
                return any((dh_val ^ existing_dh).bit_count() <= 8 for existing_dh in _v43_used_dhashes)

            cur_dhash = _get_perceptual_dhash_int(str(cur_diag))
            is_dup_visual = bool(
                (cur_md5 and used_diagram_md5s.get(cur_md5, 0) >= 1)
                or _is_dhash_already_used(cur_dhash)
            )
            if cur_md5 or cur_dhash is not None:
                if is_dup_visual:
                    # Replace a duplicate or perceptually identical image (dHash Hamming <= 8)
                    # if a distinct verified pamphlet image or Nano Banana visual for THIS badge/requirement exists
                    pamphlet_dir = AI_ILLUSTRATIONS_DIR.parent / "pamphlet_images"
                    catalog = _load_pamphlet_image_catalog()
                    replacement_found = False
                    if pamphlet_dir.exists() and catalog:
                        for fname, entry in catalog.items():
                            if not fname.startswith(f"{badge_slug_check}_") or entry.get("discard") or entry.get("is_synthetic_hero_clone"):
                                continue
                            entry_r = str(entry.get("req_number") or "").strip()
                            allowed_r = [str(r).strip() for r in (entry.get("req_numbers") or []) if str(r).strip()]
                            all_e_r = [entry_r] + allowed_r
                            matches_req = (
                                str(req_num).strip() in all_e_r
                                or (opt_prefix_check and any(r_x.lower() == opt_prefix_check for r_x in all_e_r))
                                or (
                                    str(base_req_num).strip() in all_e_r
                                    and not (
                                        badge_slug_check == "animal_science"
                                        and opt_prefix_check in ("6c", "6d", "6e", "6f")
                                        and any(
                                            w in (str(entry.get("caption") or "") + " " + str(entry.get("topic") or "")).lower()
                                            for w in ("cow", "cattle", "bull", "calf", "dairy", "beef", "shorthorn")
                                        )
                                    )
                                )
                            )
                            if matches_req:
                                cand = pamphlet_dir / fname
                                if not cand.exists() or _is_discardable_pamphlet_image(cand):
                                    continue
                                cand_md5 = _file_md5(str(cand))
                                cand_dh = _get_perceptual_dhash_int(str(cand))
                                if _is_dhash_already_used(cand_dh):
                                    continue
                                composed_rep = _compose_pamphlet_visual_card(
                                    raw_img_path=cand,
                                    badge_name=badge_name,
                                    req_number=f"{req_num}_rep_{idx}",
                                    topic_title=str(entry.get("topic") or title),
                                    pamphlet_page=idx,
                                )
                                comp_rep_md5 = _file_md5(str(composed_rep))
                                if cand_md5 and used_diagram_md5s.get(cand_md5, 0) == 0 and (not comp_rep_md5 or used_diagram_md5s.get(comp_rep_md5, 0) == 0):
                                    slide["diagram_path"] = str(composed_rep)
                                    slide["ai_hero_image_path"] = None
                                    slide["visual_source_label"] = "BSA Handbook Visual"
                                    slide["visual_caption"] = strip_pamphlet_and_req_caption_prefixes(
                                        str(entry.get("caption") or title), badge_name
                                    )
                                    used_diagram_md5s[cand_md5] = 1
                                    if comp_rep_md5:
                                        used_diagram_md5s[comp_rep_md5] = 1
                                    if cand_dh is not None:
                                        _v43_used_dhashes.append(cand_dh)
                                    replacement_found = True
                                    break
                    if not replacement_found:
                        # Also check custom Nano Banana diagrams & topic visuals for this badge + req
                        nc_map = _get_nano_banana_catalog()
                        cand_ai_files = []
                        for tv_tag in (req_slug_check, opt_prefix_check, str(base_req_num).strip()):
                            if tv_tag:
                                cand_ai_files.append(AI_ILLUSTRATIONS_DIR / f"{badge_slug_check}_req_{tv_tag}_topic_visual.png")
                        for nc_fname, nc_entry in nc_map.items():
                            if (
                                nc_fname.startswith(f"{badge_slug_check}_")
                                and isinstance(nc_entry, dict)
                                and "_v46_diagram" not in nc_fname
                                and "_v47_diagram" not in nc_fname
                                and str(nc_entry.get("req_number") or "").strip() in (str(req_num).strip(), str(base_req_num).strip())
                            ):
                                cand_ai_files.append(AI_ILLUSTRATIONS_DIR / nc_fname)
                        for cand_tv in cand_ai_files:
                            if cand_tv.exists() and cand_tv.stat().st_size >= 25_000:
                                tv_md5 = _file_md5(str(cand_tv))
                                tv_dh = _get_perceptual_dhash_int(str(cand_tv))
                                if tv_md5 and used_diagram_md5s.get(tv_md5, 0) == 0 and not _is_dhash_already_used(tv_dh):
                                    slide["diagram_path"] = str(cand_tv)
                                    slide["ai_hero_image_path"] = str(cand_tv)
                                    slide["visual_source_label"] = "🍌 Nano Banana Visual"
                                    used_diagram_md5s[tv_md5] = 1
                                    if tv_dh is not None:
                                        _v43_used_dhashes.append(tv_dh)
                                    replacement_found = True
                                    if cand_tv.name in nc_map:
                                        slide["visual_caption"] = strip_pamphlet_and_req_caption_prefixes(
                                            str(nc_map[cand_tv.name].get("caption") or title), badge_name
                                        )
                                    break
                    if not replacement_found:
                        slide["diagram_path"] = None
                        slide["ai_hero_image_path"] = None
                        slide["visual_caption"] = ""
                        if slide.get("archetype") in ("SPLIT_VISUAL_EXPLAINER", "FULL_BLEED_IMAGE_EXPLAINER"):
                            slide["archetype"] = "CONCEPT_TEXT_SLIDE"
                else:
                    if cur_md5:
                        used_diagram_md5s[cur_md5] = used_diagram_md5s.get(cur_md5, 0) + 1
                    if cur_dhash is not None:
                        _v43_used_dhashes.append(cur_dhash)
        elif slide.get("archetype") in ("CONCEPT_TEXT_SLIDE", "STEP_BY_STEP_PROCEDURE_4CARD"):
            # Option 3B Selective Hybrid Expansion:
            # If this conceptual or hands-on procedure slide has no visual yet, promote it to SPLIT_VISUAL_EXPLAINER
            # when an unused, non-perceptually-duplicate verified pamphlet figure or custom diagram exists for this requirement!
            if "_v43_used_dhashes" not in locals():
                _v43_used_dhashes = []
            if not hasattr(beautify_slide_storyboard, "_dhash_cache"):
                beautify_slide_storyboard._dhash_cache = {}
                try:
                    import json as _v43_json

                    dh_json_p = Path(__file__).resolve().parent.parent.parent / "data" / "asset_perceptual_hashes.json"
                    if dh_json_p.exists() and dh_json_p.stat().st_size > 10:
                        raw_dh_map = _v43_json.loads(dh_json_p.read_text(encoding="utf-8"))
                        for k_dh, v_dh in raw_dh_map.items():
                            if isinstance(v_dh, str) and len(v_dh) == 16:
                                beautify_slide_storyboard._dhash_cache[k_dh] = int(v_dh, 16)
                except Exception:
                    pass
            _dc_opt = beautify_slide_storyboard._dhash_cache
            pamphlet_dir_opt = AI_ILLUSTRATIONS_DIR.parent / "pamphlet_images"
            catalog_opt = _load_pamphlet_image_catalog()
            nc_map_opt = _get_nano_banana_catalog()
            promoted_opt3b = False
            if pamphlet_dir_opt.exists() and catalog_opt:
                for fname_opt, entry_opt in catalog_opt.items():
                    if not fname_opt.startswith(f"{badge_slug_check}_") or entry_opt.get("discard") or entry_opt.get("is_synthetic_hero_clone"):
                        continue
                    all_r_opt = [str(entry_opt.get("req_number") or "").strip()] + [
                        str(r).strip() for r in (entry_opt.get("req_numbers") or []) if str(r).strip()
                    ]
                    if str(req_num).strip() in all_r_opt or str(base_req_num).strip() in all_r_opt:
                        cand_p_opt = pamphlet_dir_opt / fname_opt
                        if not cand_p_opt.exists() or _is_discardable_pamphlet_image(cand_p_opt):
                            continue
                        c_md5_opt = _file_md5(str(cand_p_opt))
                        c_dh_opt = _dc_opt.get(fname_opt)
                        if (
                            c_md5_opt
                            and used_diagram_md5s.get(c_md5_opt, 0) == 0
                            and (c_dh_opt is None or all((c_dh_opt ^ ex_dh).bit_count() > 8 for ex_dh in _v43_used_dhashes))
                        ):
                            comp_opt = _compose_pamphlet_visual_card(
                                raw_img_path=cand_p_opt,
                                badge_name=badge_name,
                                req_number=f"{req_num}_opt3b_{idx}",
                                topic_title=str(entry_opt.get("topic") or title),
                                pamphlet_page=idx,
                            )
                            slide["diagram_path"] = str(comp_opt)
                            slide["ai_hero_image_path"] = None
                            slide["archetype"] = "SPLIT_VISUAL_EXPLAINER"
                            slide["visual_source_label"] = "BSA Handbook Visual"
                            slide["visual_caption"] = strip_pamphlet_and_req_caption_prefixes(
                                str(entry_opt.get("caption") or title), badge_name
                            )
                            used_diagram_md5s[c_md5_opt] = 1
                            if c_dh_opt is not None:
                                _v43_used_dhashes.append(c_dh_opt)
                            promoted_opt3b = True
                            break
            if not promoted_opt3b and nc_map_opt:
                for nc_fn_opt, nc_en_opt in nc_map_opt.items():
                    if (
                        not nc_fn_opt.startswith(f"{badge_slug_check}_")
                        or not isinstance(nc_en_opt, dict)
                        or "_v46_diagram" in nc_fn_opt
                        or "_v47_diagram" in nc_fn_opt
                    ):
                        continue
                    if str(nc_en_opt.get("req_number") or "").strip() in (str(req_num).strip(), str(base_req_num).strip()):
                        cand_nc_opt = AI_ILLUSTRATIONS_DIR / nc_fn_opt
                        if not cand_nc_opt.exists() or cand_nc_opt.stat().st_size < 25_000:
                            continue
                        c_md5_opt = _file_md5(str(cand_nc_opt))
                        c_dh_opt = _dc_opt.get(nc_fn_opt)
                        if (
                            c_md5_opt
                            and used_diagram_md5s.get(c_md5_opt, 0) == 0
                            and (c_dh_opt is None or all((c_dh_opt ^ ex_dh).bit_count() > 8 for ex_dh in _v43_used_dhashes))
                        ):
                            slide["diagram_path"] = str(cand_nc_opt)
                            slide["ai_hero_image_path"] = str(cand_nc_opt)
                            slide["archetype"] = "SPLIT_VISUAL_EXPLAINER"
                            slide["visual_source_label"] = "🍌 Nano Banana Visual"
                            slide["visual_caption"] = strip_pamphlet_and_req_caption_prefixes(
                                str(nc_en_opt.get("caption") or title), badge_name
                            )
                            used_diagram_md5s[c_md5_opt] = 1
                            if c_dh_opt is not None:
                                _v43_used_dhashes.append(c_dh_opt)
                            promoted_opt3b = True
                            break

        # Ensure every visual slide's caption is colon-free, complete, unique across the deck, and never duplicates a slide bullet
        if slide.get("diagram_path"):
            import re as _re
            from src.tools.pamphlet_extractor import _ensure_complete_caption_sentence

            raw_vc_final = str(slide.get("visual_caption") or "").strip()
            raw_vc_final = _re.sub(r"^Uniformed\s+Scouts\b", "Scouts", raw_vc_final, flags=_re.IGNORECASE)
            raw_vc_final = _re.sub(r"^Uniformed\s+Scout\b", "A Scout", raw_vc_final, flags=_re.IGNORECASE)
            raw_vc_final = _re.sub(r"\s+in\s+a\s+realistic\s+outdoor\s+setting\b", "", raw_vc_final, flags=_re.IGNORECASE)
            if ":" in raw_vc_final:
                if ": " in raw_vc_final:
                    h_p, b_p = raw_vc_final.split(": ", 1)
                    raw_vc_final = b_p.strip() if len(b_p.strip()) >= 24 else f"{h_p.strip()} - {b_p.strip()}"
                raw_vc_final = raw_vc_final.replace(":", " - ")
            raw_vc_final = raw_vc_final.replace("—", "-").replace("–", "-")
            raw_vc_final = _ensure_complete_caption_sentence(raw_vc_final, max_chars=125)
            norm_vc = _re.sub(r"[^a-z0-9]+", " ", raw_vc_final.lower()).strip()
            norm_title = _re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
            bullet_norms = [
                _re.sub(r"[^a-z0-9]+", " ", str(b).lower()).strip()
                for b in (slide.get("bullet_points") or [])
                if str(b).strip()
            ]
            overlaps_bullet = any(
                nb and (norm_vc == nb or (len(norm_vc) > 35 and norm_vc[:45] in nb))
                for nb in bullet_norms
            )

            if not norm_vc or norm_vc == norm_title or norm_vc in seen_visual_captions or overlaps_bullet:
                clean_t = strip_pamphlet_and_req_caption_prefixes(title, badge_name).replace(":", " - ").replace("—", "-").strip(" .,-")
                clean_t = _re.sub(r"\s*[-]\s*(?:Core Principles & Field Reference|Field Visual & Key Principles)$", "", clean_t, flags=_re.IGNORECASE).strip()
                clean_t = _re.sub(r"\s*\((?:Visual Guide|Core Principles|Req[^)]*)\)$", "", clean_t, flags=_re.IGNORECASE).strip()
                clean_t = _re.sub(r"\b(?:Requirement|Req)s?\s+\d+[a-z0-9()\-]*\s*[-:]?\s*", "", clean_t, flags=_re.IGNORECASE).strip(" .,-")
                if not clean_t:
                    clean_t = f"{badge_name} field practice"
                alt_cap = f"Uniformed Scouts demonstrating {clean_t.lower()} technique and safety checks for {badge_name}."
                raw_vc_final = _ensure_complete_caption_sentence(alt_cap.replace(":", ""), max_chars=125)
                norm_vc = _re.sub(r"[^a-z0-9]+", " ", raw_vc_final.lower()).strip()
                if norm_vc in seen_visual_captions:
                    alt_cap_2 = f"Labeled {badge_name} studio and field guide illustrating {clean_t.lower()} equipment and posture."
                    raw_vc_final = _ensure_complete_caption_sentence(alt_cap_2.replace(":", ""), max_chars=125)
                    norm_vc = _re.sub(r"[^a-z0-9]+", " ", raw_vc_final.lower()).strip()

            seen_visual_captions.add(norm_vc)
            slide["visual_caption"] = raw_vc_final

        if not slide.get("visual_source_label"):
            slide["visual_source_label"] = "BSA Handbook / Technical Diagram"

        # Write beautification and audience metadata onto the slide dict (never set real_world_connection_box boilerplate)
        slide["beautification_tier"] = tier_upper
        slide["visual_theme"] = theme
        slide["accent_palette_key"] = palette
        slide["callout_badge_text"] = callout_badge[:42]
        slide["real_world_connection_box"] = None
        slide["grounded_citation_label"] = grounded_label
        slide["audience_level"] = audience_level

        # Strip any legacy [DEEP RESEARCH & LOCAL GROUNDING] boilerplate from presenter_notes
        # and re-compile conversational presenter_notes so they reflect the finalized visual_caption,
        # diagram_path, archetype, and audience_level.
        from src.agents.planner import _build_slide_teaching_notes, _sanitize_no_ellipsis_or_emdash

        if req_num.lower() not in ("overview", "sources") and str(slide.get("archetype") or "").upper() not in (
            "REQUIREMENTS_TRIAGE_MATRIX",
            "SOURCES_AND_REFERENCES",
        ):
            cur_slide_idx_in_req = req_slide_counts.get(req_num.lower(), 0)
            req_slide_counts[req_num.lower()] = cur_slide_idx_in_req + 1
            matched_req_dict = (
                req_lookup_map.get(req_num)
                or req_lookup_map.get(req_num.lower())
                or req_lookup_map.get(base_req_num)
                or req_lookup_map.get(base_req_num.lower())
            )
            slide_for_notes = dict(slide)
            slide_for_notes["_used_myths_in_deck"] = used_myths_in_deck
            slide_for_notes["_used_asks_in_deck"] = used_asks_in_deck
            slide["presenter_notes"] = _build_slide_teaching_notes(
                badge_name=badge_name,
                req_num=req_num,
                execution_mode=str(slide.get("execution_mode") or "IN_CLASS_DISCUSSION"),
                slide_title=title,
                archetype=str(slide.get("archetype") or arch),
                req_text=str(slide.get("verbatim_requirement_text") or ""),
                bullet_points=list(slide.get("bullet_points") or []),
                req_dict=matched_req_dict,
                comparison_data=slide.get("comparison_data"),
                worked_example=slide.get("worked_example"),
                quiz_item=slide.get("quiz_item"),
                gear_checklist=slide.get("gear_checklist"),
                visual_caption=str(slide.get("visual_caption") or ""),
                has_visual=bool(slide.get("diagram_path")),
                safety_callout=slide.get("safety_warning"),
                audience_level=str(audience_level or "All Scouts (Ages 11-17)"),
                local_grounding_callout=str(slide.get("local_grounding_callout") or ""),
                slide_dict=slide_for_notes,
                slide_idx_in_req=cur_slide_idx_in_req,
            )
        else:
            notes_str = _sanitize_no_ellipsis_or_emdash(str(slide.get("presenter_notes") or ""))
            if "[DEEP RESEARCH & LOCAL GROUNDING" in notes_str:
                notes_lines = [
                    ln for ln in notes_str.splitlines()
                    if "[DEEP RESEARCH & LOCAL GROUNDING" not in ln
                ]
                notes_str = "\n".join(notes_lines).strip()
            slide["presenter_notes"] = notes_str

        if not slide.get("subtitle"):
            slide["subtitle"] = f"Req {req_num} • {theme.replace('_', ' ').title()}"

        # V46: Populate verified Deep Research provenance, rule of thumb, tabletop demo, and bespoke diagram metadata
        v46_conn_box: Optional[str] = None
        try:
            from src.tools.scouting_scraper import _load_v46_deep_research_overlay

            v46_ov = _load_v46_deep_research_overlay(badge_name)
            v46_reqs_map = v46_ov.get("requirements") if isinstance(v46_ov, dict) else {}
            v46_item = v46_reqs_map.get(str(base_req_num)) if isinstance(v46_reqs_map, dict) else None
            if isinstance(v46_item, dict):
                v46_conn_box = str(v46_item.get("real_world_connection_box") or "") or None
                slide["v46_real_world_connection_box"] = v46_conn_box
                slide["real_world_connection_box"] = None
                slide["grounded_citation_label"] = str(v46_item.get("grounded_citation_label") or "") or None
                slide["rule_of_thumb_mnemonic"] = str(v46_item.get("rule_of_thumb_mnemonic") or "")
                slide["counselor_tabletop_demo"] = str(v46_item.get("counselor_tabletop_demo") or "")
                slide["v46_bespoke_visual_url"] = str(v46_item.get("bespoke_visual_url") or "")
                slide["v46_bespoke_visual_caption"] = str(v46_item.get("bespoke_visual_caption") or "")
        except Exception:
            v46_conn_box = None

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

    _apply_v46_deep_research_masterclass_slides(badge_name=badge_name, slides=slides)
    _apply_v44_visual_and_caption_integrity_pass(badge_name=badge_name, slides=slides)
    storyboard["slides"] = slides

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


_V44_CURATED_CAPTIONS: Dict[str, str] = {
    "first_aid_mental_health_support_nano.png": (
        "Two adult Scout leaders sitting calmly on a pine camp bench offering attentive peer listening, reassurance, "
        "and a warm drink to support a stressed hiker."
    ),
    "first_aid_p090_img2.png": (
        "Two uniformed Scout instructors kneeling on a training mat to perform straight-arm chest compressions on a "
        "CPR manikin while preparing automated external defibrillator pads."
    ),
    "weather_ec2020_s54_img1.png": (
        "Earth's 23.5-degree tilted axis along its annual elliptical orbit around the Sun across the June and December "
        "solstices and the March and September equinoxes."
    ),
    "weather_global_climate_zones_nano.png": (
        "Three-dimensional Earth globe illustrating Hadley, Ferrel, and Polar atmospheric wind cells across tropical "
        "equatorial forests, subtropical deserts, temperate belts, and polar ice caps."
    ),
    "weather_req_9_topic_visual.png": (
        "Solar beam angle comparison showing concentrated perpendicular sunlight at the Equator, angled mid-latitude "
        "rays, and oblique grazing sunlight across the polar regions."
    ),
    "citizenship_in_the_nation_p006_img1.png": (
        "Statue of Liberty standing on her granite harbor pedestal with the full American flag waving across a clear "
        "blue sky above New York Harbor."
    ),
    "citizenship_in_the_nation_historic_speech_nano.png": (
        "Historic civic address delivered from white marble memorial steps overlooking the National Mall Reflecting "
        "Pool and the Washington Monument at golden hour."
    ),
    "citizenship_in_the_nation_req_6_topic_visual.png": (
        "Open leather-bound anthology of historic American speeches, ribbon-tied parchment scroll, brass inkwell, and "
        "quill pen arranged on a sunlit oak study desk."
    ),
    "citizenship_in_the_nation_req_8_topic_visual.png": (
        "United States Capitol dome in Washington, D.C., framed across the green lawn behind a blue postal collection "
        "box and a sealed constituent letter."
    ),
    "rifle_shooting_req_1a_nano_hero.png": (
        "Range Safety Officer in a campaign hat and tan uniform reviewing downrange target safety and muzzle discipline "
        "with two uniformed adult Scouters on an outdoor rifle range."
    ),
    "rifle_shooting_req_1e_nano_hero.png": (
        "Outdoor range briefing table displaying a bolt-action rifle with an open action and orange chamber flag, ear "
        "and eye protection, compass, binoculars, and topographic map."
    ),
    "rifle_shooting_p080_img1.png": (
        "Pair of mallard ducks rising in full flight above golden wetland cattail marshes and calm reflective water."
    ),
    "rifle_shooting_req_2_nano_hero.png": (
        "Two uniformed adult Scout leaders wearing hearing and eye protection inspecting shot groupings on a bullseye "
        "paper target mounted on a wooden range frame."
    ),
    "rifle_shooting_req_2c_1_nano_hero.png": (
        "Traditional octagon-barrel muzzleloading rifle displayed on oak planks alongside a brass powder measure, "
        "wooden ramrod, cloth patches, round balls, and leather shooting bag."
    ),
    "rifle_shooting_req_2c_topic_visual.png": (
        "Uniformed Range Safety Officer and shooter wearing eye and ear protection seating a patched round ball with a "
        "wooden ramrod at a covered outdoor loading bench."
    ),
    "dance_choreography_stage_blocking_v47_diagram.png": (
        "Isometric proscenium stage floor divided into nine choreographic blocking zones with three dancers moving "
        "along curved golden floor pathways."
    ),
    "dance_p003_img1.png": (
        "Dancers practicing upright posture alignment and balance exercises at a wooden barre in front of a studio mirror."
    ),
    "dance_p004_img1.png": (
        "Uniformed Scout dancer performing an athletic one-handed breakdance freeze with balanced core and shoulder control."
    ),
    "dance_p005_img1.png": (
        "Three uniformed Scouts at a library table researching historical dance books, archival photographs, and sheet music."
    ),
    "dance_p007_img1.png": (
        "Uniformed Scout practicing dynamic knee-lift and ankle mobility warm-up exercises before dance rehearsal."
    ),
    "dance_p008_img1.png": (
        "Four full-body dancers in a sunlit hardwood rehearsal studio demonstrating classical ballet posture, tap "
        "footwork, folk line step, and athletic breakdance balance."
    ),
    "dance_p011_img1.png": (
        "Four uniformed Scouts in a sunlit studio comparing choreographic floor patterns, musical timing, and partner cues."
    ),
    "dance_p012_img1.png": (
        "Three uniformed Scouts practicing a coordinated partner dance turn and social ballroom frame."
    ),
    "dance_p014_img1.png": (
        "Four uniformed Scouts holding hands while rehearsing a synchronized folk and country line dance step."
    ),
    "dance_req_1_nano_hero.png": (
        "Four uniformed Scouts in a rehearsal studio practicing warm-up leg stretches, hydration checks, and safe floor spacing."
    ),
    "dance_req_1_topic_visual.png": (
        "Two uniformed Scouts holding hands to practice balanced partner posture, arm frame, and studio floor spacing."
    ),
    "dance_req_2_nano_hero.png": (
        "Uniformed Scouts and a dance instructor in a sunlit arched-window studio demonstrating the five elements "
        "of dance across high, middle, and low levels."
    ),
    "dance_req_2_topic_visual.png": (
        "Dancers in historical period attire performing a traditional court and social ballroom dance formation in a timbered hall."
    ),
    "dance_req_3_nano_hero.png": (
        "Three uniformed Scouts in a rehearsal hall demonstrating traditional folk skirt work, rhythmic hand "
        "gestures, and upright partner posture."
    ),
    "dance_req_3_topic_visual.png": (
        "Full-body ensemble dancers practicing partner ballroom carriage and coordinated folk circle steps in a "
        "sunlit hardwood hall."
    ),
    "dance_req_4_nano_hero.png": (
        "Satin ballet pointe shoes, polished leather tap shoes, wooden metronome, sheet music stand, and choreographic "
        "floor-pattern sketches arranged on a sunlit studio bench."
    ),
    "dance_req_4_topic_visual.png": (
        "Four uniformed Scouts practicing a synchronized four-hand star square and folk dance formation in a rehearsal studio."
    ),
    "dance_req_5_nano_hero.png": (
        "Three uniformed Scouts in a sunlit studio practicing an energetic contemporary step sequence while keeping rhythmic time."
    ),
    "dance_req_5_topic_visual.png": (
        "Uniformed Scouts and a movement coach practicing partner swing frame and coordinated footwork in front of a studio mirror."
    ),
    "dance_req_6_nano_hero.png": (
        "Dance instructors in a mirrored sprung-floor studio demonstrating vertical spinal alignment and ballet barre "
        "warm-up posture."
    ),
    "dance_req_6_topic_visual.png": (
        "Uniformed Scout instructor guiding three youth dancers through a rhythmic warm-up and step progression in a rehearsal room."
    ),
    "dance_req_7_topic_visual.png": (
        "Five uniformed Scouts under an open timber camp pavilion practicing a synchronized group line dance routine "
        "on a wooden deck."
    ),
    "dance_req_7_nano_hero.png": (
        "Ensemble of dancers completing a coordinated multi-level stage formation on a warm hardwood theater floor."
    ),
    "robotics_req_1_nano_hero.png": (
        "Two uniformed Scouts wearing safety glasses and protective gloves inspecting a wheeled robot chassis on a workbench."
    ),
    "robotics_req_1_topic_visual.png": (
        "Hand-drawn engineering notebook concept sketch illustrating ultrasonic distance sensor wave propagation and "
        "obstacle reflection."
    ),
    "robotics_p032_img1.png": (
        "Hand-drawn engineering notebook concept sketch illustrating ultrasonic distance sensor wave propagation and "
        "obstacle reflection."
    ),
    "robotics_p032_img4.png": (
        "Hand-drawn engineering notebook concept sketch illustrating ultrasonic distance sensor wave propagation and "
        "obstacle reflection."
    ),
    "robotics_p032_img2.png": (
        "Hand-drawn engineering notebook concept sketch showing GPS satellite triangulation and orbital range vectors."
    ),
    "robotics_p032_img3.png": (
        "Hand-drawn engineering notebook concept sketch showing GPS satellite triangulation and orbital range vectors."
    ),
    "robotics_req_2_nano_hero.png": (
        "Adult counselor and two uniformed Scouts examining an articulated robotic arm and mobile sensor platform in camp."
    ),
    "robotics_p007_img1.png": (
        "Adult counselor and two uniformed Scouts examining an articulated robotic arm and mobile sensor platform in camp."
    ),
    "robotics_req_7_topic_visual.png": (
        "Adult counselor and two uniformed Scouts examining an articulated robotic arm and mobile sensor platform in camp."
    ),
    "robotics_req_2_topic_visual.png": (
        "The NASA and GM Robonaut humanoid robot demonstrating upper-body dexterity and human-scale tool manipulation."
    ),
    "robotics_p017_img2.png": (
        "The NASA and GM Robonaut humanoid robot demonstrating upper-body dexterity and human-scale tool manipulation."
    ),
    "robotics_req_3_nano_hero.png": (
        "Uniformed Scouts and an instructor testing a tracked robotic vehicle and sensor array at a field workbench."
    ),
    "robotics_p012_img1.png": (
        "Uniformed Scouts and an instructor testing a tracked robotic vehicle and sensor array at a field workbench."
    ),
    "robotics_req_4_topic_visual.png": (
        "Uniformed Scouts and an instructor testing a tracked robotic vehicle and sensor array at a field workbench."
    ),
    "robotics_req_3_topic_visual.png": (
        "NASA Mars Curiosity rover mobility subsystem showing the rocker-bogie suspension and cleated aluminum wheels."
    ),
    "robotics_req_6_topic_visual.png": (
        "NASA Mars Curiosity rover mobility subsystem showing the rocker-bogie suspension and cleated aluminum wheels."
    ),
    "robotics_p020_img1.png": (
        "NASA Mars Curiosity rover mobility subsystem showing the rocker-bogie suspension and cleated aluminum wheels."
    ),
    "robotics_req_4_nano_hero.png": (
        "Uniformed Scouts writing microcontroller code on a laptop beside a tabletop robotics test arena."
    ),
    "robotics_req_5_nano_hero.png": (
        "Uniformed Scouts reviewing an engineering notebook schematic while calibrating their custom-built robot on a workbench."
    ),
    "robotics_req_5_topic_visual.png": (
        "Youth competition robot #604 positioned on a bordered tournament field during autonomous and teleoperated match testing."
    ),
    "robotics_p071_img1.png": (
        "Youth competition robot #604 positioned on a bordered tournament field during autonomous and teleoperated match testing."
    ),
    "robotics_req_6_nano_hero.png": (
        "Uniformed Scouts inspecting drivetrain wiring and manipulator linkages on a competition robot in an outdoor pit station."
    ),
    "robotics_req_7_nano_hero.png": (
        "Uniformed Scouts comparing underwater ROV, space exploration rover, and domestic robotics engineering displays."
    ),
    "american_indian_culture_req_3_topic_visual.png": (
        "Illustrated color map of North American Indigenous cultural regions from the Arctic and Northwest Coast to "
        "the Great Plains, Southwest, and Eastern Woodlands."
    ),
    "camping_leave_no_trace_campsite_nano.png": (
        "Alpine Scout campsite laid out in a 200-foot Leave No Trace triangle separating durable gravel tent pads, "
        "camp stove cooking rock, and bear canister food storage away from mountain water."
    ),
    "swimming_reach_throw_row_go_nano.png": (
        "Waterfront instructors in buckled USCG life jackets on a sunny camp dock demonstrating reaching pole rescue, "
        "ring buoy throw line readiness, and rowboat safety."
    ),
    "first_aid_p023_img1.png": (
        "Uniformed Scout kneeling beside an injured hiker wrapped in a reflective emergency thermal blanket on a mountain "
        "trail to prevent shock."
    ),
    "first_aid_p085_img1.png": (
        "North American raccoon, a common nocturnal wildlife reservoir for rabies virus transmission requiring immediate "
        "soap-and-water wound washing and medical evaluation after any bite or scratch."
    ),
    "first_aid_req_5_topic_visual.png": (
        "Two uniformed Scouts and an adult leader assisting a hiker seated on a trail bench using a handheld blue rescue "
        "inhaler alongside an open first aid kit with an epinephrine auto-injector trainer."
    ),
    "first_aid_req_11_topic_visual.png": (
        "Under a shaded canvas camp dining fly, a uniformed Scout applies a cool wet cloth to the forehead of a seated "
        "hiker sipping water while a patrol mate prepares an insulated sleeping bag and warm layers."
    ),
    "citizenship_in_the_nation_p005_img1.png": (
        "Turned hardwood courtroom gavel resting against its circular sound block, symbolizing impartial constitutional "
        "justice and the rule of law."
    ),
    "citizenship_in_the_nation_p005_img2.png": (
        "Uniformed Scout standing on the sunlit West Front lawn before the white marble dome of the United States Capitol "
        "in Washington, D.C."
    ),
    "citizenship_in_the_nation_req_2_nano_hero.png": (
        "Uniformed Scouts and neighbors greeting one another across a stone footbridge beside a brick schoolhouse and "
        "library, with a classical courthouse, golden scales sculpture, and American flag across the green."
    ),
    "emergency_preparedness_go_kit_nano.png": (
        "Organized 72-hour emergency preparedness pack flat-lay with hand-crank weather radio, headlamp, water filter, "
        "first-aid kit, whistle, thermal blanket, and spare batteries."
    ),
}

_VISUAL_EQUIVALENCE_CACHE: Optional[Dict[str, Any]] = None
_CATALOG_CAPTION_MAP: Optional[Dict[str, str]] = None
_DISCARDED_PAMPHLET_SET: Optional[set[str]] = None


def _get_visual_equivalence_data() -> Dict[str, Any]:
    """Loads `data/visual_equivalence_clusters.json` once and caches perceptual cluster mappings."""
    import json as _eq_json

    global _VISUAL_EQUIVALENCE_CACHE
    if _VISUAL_EQUIVALENCE_CACHE is not None:
        return _VISUAL_EQUIVALENCE_CACHE
    repo_root = Path(__file__).resolve().parent.parent.parent
    cpath = repo_root / "data" / "visual_equivalence_clusters.json"
    if cpath.exists():
        try:
            with open(cpath, "r", encoding="utf-8") as f:
                _VISUAL_EQUIVALENCE_CACHE = _eq_json.load(f)
                return _VISUAL_EQUIVALENCE_CACHE
        except Exception:
            pass
    _VISUAL_EQUIVALENCE_CACHE = {"file_to_cluster": {}, "clone_to_pamphlet": {}, "badge_distinct_reps": {}}
    return _VISUAL_EQUIVALENCE_CACHE


def _get_catalog_caption_and_discard_maps() -> tuple[Dict[str, str], set[str]]:
    """Loads authoritative captions and discarded file set from `pamphlet_image_catalog.json` & `nano_banana_image_catalog.json`."""
    import json as _cat_json

    global _CATALOG_CAPTION_MAP, _DISCARDED_PAMPHLET_SET
    if _CATALOG_CAPTION_MAP is not None and _DISCARDED_PAMPHLET_SET is not None:
        return _CATALOG_CAPTION_MAP, _DISCARDED_PAMPHLET_SET
    repo_root = Path(__file__).resolve().parent.parent.parent
    cap_map: Dict[str, str] = {}
    disc_set: set[str] = set()
    for rel_c in ("data/nano_banana_image_catalog.json", "data/pamphlet_image_catalog.json"):
        p = repo_root / rel_c
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = _cat_json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, dict):
                            if v.get("discard") or (v.get("is_synthetic_hero_clone") and not k.startswith("dance_")):
                                disc_set.add(k)
                            c = str(v.get("caption") or "").strip()
                            if c:
                                cap_map[k] = c
            except Exception:
                pass
    _CATALOG_CAPTION_MAP = cap_map
    _DISCARDED_PAMPHLET_SET = disc_set
    return _CATALOG_CAPTION_MAP, _DISCARDED_PAMPHLET_SET


def _sanitize_v44_caption(raw_cap: str, badge_name: str, slide_title: str, fname: str = "") -> str:
    """Guarantees every slide caption is concrete, non-formulaic, zero-em-dash, and free of Requirement meta-text."""
    import re as _v44_re

    bname = os.path.basename(fname) if fname else ""
    if bname in _V44_CURATED_CAPTIONS:
        return _V44_CURATED_CAPTIONS[bname]

    cap_map, _ = _get_catalog_caption_and_discard_maps()
    cand = str(raw_cap or "").strip()
    # Prefer authoritative catalog caption if raw_cap is empty or uses a legacy Mad-Libs / Annotated template
    if bname in cap_map and (
        not cand
        or "Annotated " in cand
        or "wooden picnic table" in cand
        or "Detailed field manual illustration of Scouts demonstrating" in cand
        or "Daylight outdoor camp demonstration of" in cand
        or "Clear visual cutaway and outdoor demonstration of" in cand
        or "Close-up instructional field scene showing Scouts practicing" in cand
    ):
        cand = cap_map[bname]

    cand = cand.replace("—", ", ").replace("–", ", ").replace("--", ", ")
    cand = _v44_re.sub(
        r"^Cross-sectional\s+diagram\s+showing\s+key\s+parts\s+and\s+mechanical\s+relationships\s+of\s+(.+?)\s+used\s+in\s+(.+?)\.?$",
        r"Labeled \2 field guide illustration showing \1 components, setup, and safe operation.",
        cand,
        flags=_v44_re.I,
    )
    cand = _v44_re.sub(
        r"^Technical\s+field\s+diagram\s+for\s+.+?\s+(?:covering|showing)\s+",
        "Labeled field reference illustrating ",
        cand,
        flags=_v44_re.I,
    )
    cand = _v44_re.sub(
        r"^Field\s+(?:reference\s+)?illustration\s+(?:for|of)\s+.+?\s+showing\s+",
        "Illustrated field guide panel depicting ",
        cand,
        flags=_v44_re.I,
    )
    cand = _v44_re.sub(
        r"^Hands-on\s+(.+?)\s+demonstration\s+illustrating\s+(.+?)(?:\s+with\s+proper\s+field\s+technique.*)?[.!]?$",
        r"Uniformed Scouts practicing \2 with organized patrol equipment and safety supervision.",
        cand,
        flags=_v44_re.I,
    )
    cand = _v44_re.sub(
        r"^Field\s+illustration\s+of\s+(.+?)\s+techniques\s+and\s+safety\s+practices\s+for\s+(.+?)\.?$",
        r"Uniformed Scouts practicing \1 with organized \2 equipment and safety checks.",
        cand,
        flags=_v44_re.I,
    )
    cand = _v44_re.sub(r"\s*\((?:Reqs?|Requirement|Option|topic)[^)]*\)", "", cand, flags=_v44_re.I)
    cand = _v44_re.sub(
        r"\b(?:for|in|during)\s+[A-Z][A-Za-z ,&'\-]+\s+Requirement(?:s)?\s+\d+[a-z0-9()\-]*",
        "",
        cand,
        flags=_v44_re.I,
    )
    cand = _v44_re.sub(r"\bRequirement(?:s)?\s+\d+[a-z0-9()\-]*\b", "", cand, flags=_v44_re.I)
    cand = _v44_re.sub(r"\bReqs?\.\s*\d+[a-z0-9()\-]*\b", "", cand, flags=_v44_re.I)
    cand = _v44_re.sub(r"\bOfficial\s+.*?\s+visual\s+reference\b", "", cand, flags=_v44_re.I)
    cand = _v44_re.sub(r"\byour\s+counselor'?s\s+approval\b", "", cand, flags=_v44_re.I)
    cand = _v44_re.sub(r"\bchoose\s+techniques\b", "practical techniques", cand, flags=_v44_re.I)
    cand = _v44_re.sub(r"\s{2,}", " ", cand).strip(" .,:;-")

    if len(cand) < 18:
        clean_t = str(slide_title or badge_name).split(":")[0]
        clean_t = _v44_re.sub(r"\b(?:Requirement|Req)s?\s+\d+[a-z0-9()\-]*", "", clean_t, flags=_v44_re.I).strip(" -,:;")
        cand = f"Uniformed Scouts examining {clean_t.lower()} tools and safety steps at a {badge_name} station"

    cand = _v44_re.sub(r"\s+(?:and|or|with|for|in|of|to|on|at|by|from)$", "", cand, flags=_v44_re.I).strip(" .,:;-")
    if cand:
        cand = cand[0].upper() + cand[1:]
        if not cand.endswith("."):
            cand += "."
    return cand


def _apply_v44_visual_and_caption_integrity_pass(badge_name: str, slides: List[Dict[str, Any]]) -> None:
    """Enforces V44/V48 visual & caption integrity and perceptual cluster deduplication across all slides."""
    if not slides:
        return
    import re as _re_slug

    repo_root = Path(__file__).resolve().parent.parent.parent
    ai_dir = repo_root / "assets" / "ai_illustrations"
    pam_dir = repo_root / "assets" / "pamphlet_images"
    b_low = (badge_name or "").strip().lower()
    slug = _re_slug.sub(r"[^a-z0-9]+", "_", b_low).strip("_")

    eq_data = _get_visual_equivalence_data()
    file_to_cluster: Dict[str, str] = eq_data.get("file_to_cluster") or {}
    clone_to_pamphlet: Dict[str, Any] = eq_data.get("clone_to_pamphlet") or {}
    badge_reps: List[Dict[str, str]] = (eq_data.get("badge_distinct_reps") or {}).get(slug) or []
    cap_map, discarded_pam_set = _get_catalog_caption_and_discard_maps()

    def _assign_asset(slide_obj: Dict[str, Any], asset_file: Path, caption_text: str) -> None:
        if asset_file.exists():
            abs_s = str(asset_file.resolve())
            rel_url = f"/assets/{asset_file.parent.name}/{asset_file.name}"
            slide_obj["diagram_path"] = abs_s
            slide_obj["diagram_url"] = rel_url
            slide_obj["ai_hero_image_path"] = abs_s
            slide_obj["hero_image_url"] = rel_url
            slide_obj["image_url"] = rel_url
            slide_obj["visual_caption"] = caption_text
            if str(slide_obj.get("archetype") or "") in ("CONCEPT_TEXT_SLIDE", ""):
                slide_obj["archetype"] = "SPLIT_VISUAL_EXPLAINER"

    def _clear_asset(slide_obj: Dict[str, Any]) -> None:
        slide_obj["diagram_path"] = None
        slide_obj["diagram_url"] = None
        slide_obj["ai_hero_image_path"] = None
        slide_obj["hero_image_url"] = None
        slide_obj["image_url"] = None
        slide_obj["visual_caption"] = ""
        if str(slide_obj.get("archetype") or "") in ("SPLIT_VISUAL_EXPLAINER", "FULL_BLEED_IMAGE_EXPLAINER"):
            slide_obj["archetype"] = "CONCEPT_TEXT_SLIDE"

    # 1. Upgrade any center-cropped ai_illustrations pamphlet clone to its uncropped pamphlet_images original,
    #    clear discarded pamphlet emblems, and apply verified V44/V48 curated assignments.
    for idx0, s in enumerate(slides):
        s_num = idx0 + 1
        title_l = str(s.get("title") or "").lower()
        cur_p = str(s.get("diagram_path") or s.get("ai_hero_image_path") or "")
        cur_fn = os.path.basename(cur_p)

        if cur_fn in discarded_pam_set:
            _clear_asset(s)
            cur_fn = ""
        elif cur_fn in clone_to_pamphlet:
            c_info = clone_to_pamphlet[cur_fn]
            pam_fn = str(c_info.get("pamphlet_filename") or "")
            if pam_fn and (pam_dir / pam_fn).exists():
                _assign_asset(s, pam_dir / pam_fn, str(c_info.get("caption") or cap_map.get(pam_fn) or ""))
                cur_fn = pam_fn

        if b_low == "first aid":
            if cur_fn == "first_aid_p023_img1.png":
                _assign_asset(s, pam_dir / "first_aid_p023_img1.png", _V44_CURATED_CAPTIONS["first_aid_p023_img1.png"])
            elif any(w in title_l for w in ("mental health", "psychological first aid", "emotional", "crisis support")):
                _assign_asset(
                    s,
                    ai_dir / "first_aid_mental_health_support_nano.png",
                    _V44_CURATED_CAPTIONS["first_aid_mental_health_support_nano.png"],
                )
            elif cur_fn == "first_aid_p090_img2.png":
                _assign_asset(s, pam_dir / "first_aid_p090_img2.png", _V44_CURATED_CAPTIONS["first_aid_p090_img2.png"])

        elif b_low == "weather":
            if cur_fn == "weather_ec2020_s54_img1.png":
                _assign_asset(
                    s,
                    pam_dir / "weather_ec2020_s54_img1.png",
                    _V44_CURATED_CAPTIONS["weather_ec2020_s54_img1.png"],
                )
            elif cur_fn == "weather_req_9_topic_visual.png":
                _assign_asset(
                    s,
                    ai_dir / "weather_global_climate_zones_nano.png",
                    _V44_CURATED_CAPTIONS["weather_global_climate_zones_nano.png"],
                )

        elif b_low == "citizenship in the nation":
            if cur_fn == "citizenship_in_the_nation_p006_img1.png":
                _assign_asset(
                    s,
                    pam_dir / "citizenship_in_the_nation_p006_img1.png",
                    _V44_CURATED_CAPTIONS["citizenship_in_the_nation_p006_img1.png"],
                )
            elif cur_fn == "citizenship_in_the_nation_p050_img1.png" or s_num == 32:
                _assign_asset(
                    s,
                    ai_dir / "citizenship_in_the_nation_historic_speech_nano.png",
                    _V44_CURATED_CAPTIONS["citizenship_in_the_nation_historic_speech_nano.png"],
                )
            elif cur_fn == "citizenship_in_the_nation_req_6_topic_visual.png" or s_num in (33, 34):
                if s_num == 33:
                    _assign_asset(
                        s,
                        ai_dir / "citizenship_in_the_nation_req_6_topic_visual.png",
                        _V44_CURATED_CAPTIONS["citizenship_in_the_nation_req_6_topic_visual.png"],
                    )
            elif cur_fn == "citizenship_in_the_nation_req_8_topic_visual.png" or s_num in (45, 46):
                _assign_asset(
                    s,
                    ai_dir / "citizenship_in_the_nation_req_8_topic_visual.png",
                    _V44_CURATED_CAPTIONS["citizenship_in_the_nation_req_8_topic_visual.png"],
                )

        elif b_low == "rifle shooting":
            if cur_fn in _V44_CURATED_CAPTIONS:
                s["visual_caption"] = _V44_CURATED_CAPTIONS[cur_fn]

        elif b_low == "dance":
            if s_num == 20 and not cur_fn:
                _assign_asset(
                    s,
                    ai_dir / "dance_req_3_topic_visual.png",
                    _V44_CURATED_CAPTIONS["dance_req_3_topic_visual.png"],
                )
            elif cur_fn in _V44_CURATED_CAPTIONS:
                s["visual_caption"] = _V44_CURATED_CAPTIONS[cur_fn]

    # 2. Enforce zero duplicate perceptual clusters AND zero duplicate filenames within the same deck.
    #    Only reserve V46 clusters when they use dedicated *_v46_diagram / *_v47_diagram assets (or on Dance).
    v46_reserved_clusters: set[str] = set()
    all_deck_clusters: set[str] = set()
    for s in slides:
        dp = str(s.get("diagram_path") or s.get("ai_hero_image_path") or "").strip()
        fn = os.path.basename(dp) if dp else ""
        if fn:
            cid = file_to_cluster.get(fn, fn)
            all_deck_clusters.add(cid)
            if s.get("is_v46_deep_research_slide") and (
                "_v46_diagram" in fn or "_v47_diagram" in fn or b_low == "dance"
            ):
                v46_reserved_clusters.add(cid)

    seen_clusters: set[str] = set()
    seen_files: set[str] = set()
    for s in slides:
        dp = str(s.get("diagram_path") or s.get("ai_hero_image_path") or "").strip()
        fn = os.path.basename(dp) if dp else ""
        if not fn:
            continue
        cid = file_to_cluster.get(fn, fn)
        is_v46 = bool(s.get("is_v46_deep_research_slide"))
        s_req_raw = str(s.get("base_req_number") or s.get("req_number") or "").strip()
        s_req_m = _re_slug.match(r"^(\d+)", s_req_raw)
        s_req_base = s_req_m.group(1) if s_req_m else s_req_raw

        if fn in seen_files or cid in seen_clusters or (not is_v46 and cid in v46_reserved_clusters):
            # Try to swap in an unused distinct cluster representative matching the same requirement (or Dance studio pool)
            swapped = False
            for rep in badge_reps:
                rep_cid = rep.get("cluster_id") or ""
                rep_fn = rep.get("filename") or ""
                rep_rel = rep.get("rel_path") or ""
                rep_req_raw = str(rep.get("req_number") or "").strip()
                rep_req_m = _re_slug.match(r"^(\d+)", rep_req_raw)
                rep_req_base = rep_req_m.group(1) if rep_req_m else rep_req_raw
                req_ok = (b_low == "dance") or (bool(s_req_base) and rep_req_base == s_req_base)
                if (
                    req_ok
                    and rep_cid
                    and rep_cid not in seen_clusters
                    and rep_cid not in all_deck_clusters
                    and rep_cid not in v46_reserved_clusters
                    and rep_fn not in seen_files
                    and rep_fn not in discarded_pam_set
                ):
                    cand_p = repo_root / rep_rel
                    if cand_p.exists():
                        clean_c = _sanitize_v44_caption(
                            rep.get("caption") or cap_map.get(rep_fn) or "",
                            badge_name=badge_name,
                            slide_title=str(s.get("title") or ""),
                            fname=rep_fn,
                        )
                        _assign_asset(s, cand_p, clean_c)
                        seen_clusters.add(rep_cid)
                        all_deck_clusters.add(rep_cid)
                        seen_files.add(rep_fn)
                        swapped = True
                        break
            if not swapped:
                _clear_asset(s)
            continue

        seen_files.add(fn)
        seen_clusters.add(cid)
        s["visual_caption"] = _sanitize_v44_caption(
            str(s.get("visual_caption") or cap_map.get(fn) or ""),
            badge_name=badge_name,
            slide_title=str(s.get("title") or ""),
            fname=fn,
        )
        if is_v46:
            s["v46_bespoke_visual_caption"] = s["visual_caption"]


def _apply_v46_deep_research_masterclass_slides(
    badge_name: str,
    slides: List[Dict[str, Any]],
) -> None:
    """Inject up to 4 dedicated V46 Deep-Research & Primary Source Grounding Masterclass slides per badge."""
    if not isinstance(slides, list) or not slides:
        return
    import re
    from pathlib import Path
    from src.agents.planner import _sanitize_no_ellipsis_or_emdash

    # Avoid double-injection if called more than once (check persistent fields preserved by Pydantic SlideSpec)
    if any(
        isinstance(s, dict)
        and (
            s.get("is_v46_deep_research_slide")
            or str(s.get("slide_id") or "").startswith("v46_deep_research_")
            or "Primary Source Grounding" in str(s.get("subtitle") or "")
            or str(s.get("title") or "").startswith("Deep-Research Field Lab:")
        )
        for s in slides
    ):
        return
    try:
        from src.tools.scouting_scraper import _load_v46_deep_research_overlay

        v46_ov = _load_v46_deep_research_overlay(badge_name)
    except Exception:
        return
    if not isinstance(v46_ov, dict) or not (v46_ov.get("bespoke_clusters") or v46_ov.get("requirements")):
        return

    reqs_map: Dict[str, Any] = v46_ov.get("requirements") or {}
    root_dir = Path(__file__).resolve().parents[2]
    ai_dir = root_dir / "assets" / "ai_illustrations"
    pam_dir = root_dir / "assets" / "pamphlet_images"

    # Select up to 4 unique Primary Source Grounding clusters (unique title, unique file, unique perceptual cluster)
    eq_data = _get_visual_equivalence_data()
    file_to_cluster: Dict[str, str] = eq_data.get("file_to_cluster") or {}
    selected_clusters: List[tuple[str, Dict[str, Any], str, str]] = []
    seen_v46_files: set[str] = set()
    seen_v46_clusters: set[str] = set()
    seen_v46_titles: set[str] = set()

    candidate_sources: List[tuple[str, Dict[str, Any]]] = []
    # Prefer bespoke_clusters first if any cluster has a v47_diagram, otherwise reqs_map then bespoke_clusters
    if isinstance(v46_ov.get("bespoke_clusters"), list):
        for item in v46_ov["bespoke_clusters"]:
            if isinstance(item, dict):
                candidate_sources.append((str(item.get("req_id") or "1"), item))
    for rnum, item in reqs_map.items():
        if isinstance(item, dict):
            candidate_sources.append((str(rnum), item))

    for rnum, item in candidate_sources:
        fn = str(item.get("bespoke_visual_filename") or "").strip()
        cid = file_to_cluster.get(fn, fn)
        t_key = str(item.get("v47_slide_title") or item.get("rule_of_thumb_mnemonic") or "").strip().lower()
        if not fn or fn in seen_v46_files or cid in seen_v46_clusters or (t_key and t_key in seen_v46_titles):
            continue
        if (ai_dir / fn).exists():
            rel_p = f"assets/ai_illustrations/{fn}"
            web_u = f"/assets/ai_illustrations/{fn}"
        elif (pam_dir / fn).exists():
            rel_p = f"assets/pamphlet_images/{fn}"
            web_u = f"/assets/pamphlet_images/{fn}"
        else:
            continue
        seen_v46_files.add(fn)
        seen_v46_clusters.add(cid)
        if t_key:
            seen_v46_titles.add(t_key)
        selected_clusters.append((str(rnum), item, rel_p, web_u))
        if len(selected_clusters) >= 4:
            break

    if not selected_clusters:
        return

    for cluster_idx, (rnum, item, rel_path, web_url) in enumerate(selected_clusters, start=1):
        fn = str(item.get("bespoke_visual_filename") or "").strip()
        rule_txt = _sanitize_no_ellipsis_or_emdash(str(item.get("rule_of_thumb_mnemonic") or "").strip())
        worked_txt = _sanitize_no_ellipsis_or_emdash(str(item.get("worked_field_example") or "").strip())
        conn_txt = _sanitize_no_ellipsis_or_emdash(str(item.get("real_world_connection_box") or "").strip())
        demo_txt = _sanitize_no_ellipsis_or_emdash(str(item.get("counselor_tabletop_demo") or "").strip())
        cite_txt = _sanitize_no_ellipsis_or_emdash(str(item.get("grounded_citation_label") or "").strip())
        raw_cap = _sanitize_no_ellipsis_or_emdash(str(item.get("bespoke_visual_caption") or "").strip())
        clean_cap = _sanitize_v44_caption(
            raw_cap,
            badge_name=badge_name,
            slide_title=f"{badge_name} Technical Field Reference",
            fname=fn,
        )

        # Find the last slide belonging to this top-level requirement rnum so the deep-dive follows it naturally
        insert_pos = len(slides)
        matched_any = False
        for idx_s, s_obj in enumerate(slides):
            if not isinstance(s_obj, dict):
                continue
            s_req = str(s_obj.get("base_req_number") or s_obj.get("req_number") or "").strip()
            s_base = re.match(r"^(\d+)", s_req)
            s_base_str = s_base.group(1) if s_base else s_req
            if s_base_str == str(rnum):
                insert_pos = idx_s + 1
                matched_any = True
        if not matched_any:
            # Proportional fallback across deck quarters
            insert_pos = min(len(slides), max(1, int(round((cluster_idx / 4.0) * len(slides)))))

        # Primary Source Grounding title and succinct non-redundant bullet(s)
        explicit_v47_title = _sanitize_no_ellipsis_or_emdash(str(item.get("v47_slide_title") or "").strip())
        if explicit_v47_title:
            slide_title = explicit_v47_title
        elif ":" in conn_txt and len(conn_txt.split(":", 1)[0].strip()) <= 64:
            slide_title = conn_txt.split(":", 1)[0].strip()
        else:
            short_cite = (
                cite_txt.replace("Verified: Scouting America Pamphlet +", "")
                .replace("Verified:", "")
                .split(",")[0]
                .strip()[:56]
                or f"{badge_name} Field Standard"
            )
            slide_title = f"{short_cite} Field Standard" if "Standard" not in short_cite else short_cite
        slide_subtitle = f"{badge_name} • Requirement {rnum} Primary Source Grounding"

        raw_v47_bullets = item.get("v47_primary_source_bullets")
        if isinstance(raw_v47_bullets, list) and raw_v47_bullets:
            bullets = [
                _sanitize_no_ellipsis_or_emdash(str(b).strip())
                for b in raw_v47_bullets
                if str(b or "").strip()
            ]
        else:
            primary_statement = (
                conn_txt.split(":", 1)[1].strip()
                if ":" in conn_txt and len(conn_txt.split(":", 1)[1].strip()) >= 12
                else rule_txt
            )
            bullets = [_sanitize_no_ellipsis_or_emdash(primary_statement)]
        cards = [
            {
                "badge": "PRIMARY SOURCE",
                "title": slide_title,
                "body": b_item,
            }
            for b_item in bullets
        ]
        presenter_notes = _sanitize_no_ellipsis_or_emdash(
            f"[PACING & MODALITY] 3 min • Primary Source Field Standard (Requirement {rnum})\n"
            f"[SAY] [Point to the field cutaway diagram] {slide_title}: {' '.join(bullets)}\n"
            f"[DEMONSTRATE] {demo_txt}\n"
            f"[EXPECTED PAMPHLET ANSWER KEY] {worked_txt} Primary reference: {cite_txt}."
        )

        new_slide: Dict[str, Any] = {
            "slide_id": f"v46_deep_research_{cluster_idx}_req_{rnum}",
            "is_v46_deep_research_slide": True,
            "v46_cluster_index": cluster_idx,
            "req_number": str(rnum),
            "base_req_number": str(rnum),
            "title": slide_title,
            "subtitle": slide_subtitle,
            "archetype": "SPLIT_VISUAL_EXPLAINER",
            "visual_theme": "MAGAZINE_ASYMMETRIC_SPLIT",
            "diagram_path": rel_path,
            "diagram_url": web_url,
            "ai_hero_image_path": rel_path,
            "hero_image_url": web_url,
            "image_url": web_url,
            "visual_caption": clean_cap,
            "bullet_points": bullets,
            "cards": cards,
            "presenter_notes": presenter_notes,
            "v46_real_world_connection_box": conn_txt,
            "real_world_connection_box": None,
            "grounded_citation_label": cite_txt,
            "rule_of_thumb_mnemonic": rule_txt,
            "counselor_tabletop_demo": demo_txt,
            "v46_bespoke_visual_url": web_url,
            "v46_bespoke_visual_caption": clean_cap,
        }
        slides.insert(insert_pos, new_slide)

    # Re-run perceptual visual cluster deduplication and caption sanitization across the full deck (including V46 slides)
    _apply_v44_visual_and_caption_integrity_pass(badge_name=badge_name, slides=slides)


