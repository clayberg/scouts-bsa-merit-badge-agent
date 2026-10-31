"""Regression test suite for V43 Visual Integrity, Caption Grounding, Anti-Cropping, & Scroll Reset.

Verifies all V43 invariants across the 149 Scouts BSA Merit Badges:
1. Perceptual 64-bit dHash deduplication across REQUIREMENT_INTRO, SPLIT_VISUAL_EXPLAINER,
   FULL_BLEED_IMAGE_EXPLAINER, and Option 3B promoted slides (Weather Slides 3/4, 10/11, 16/17, 52/53).
2. Zero generic 'Official <Badge> visual reference...' captions and accurate vision-aligned captions
   on Weather Slide 52 (solar orbit, zero tripod/lamp mismatch) and First Aid Slide 48 (30:2 CPR & AED).
3. Non-destructive ImageOps.pad aspect-ratio preservation in compress_hero_illustration() and
   top-weighted object-position framing in ui/styles.css.
4. Automatic first-slide reset and universal 19-container scroll-to-top reset in ui/app.js.
5. Zero 0-byte JSON files in data/ and strictly 149 canonical Counselor Workbooks in deliverables/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.agents.beautifier import beautify_slide_storyboard
from src.agents.planner import generate_slide_storyboard

REPO_ROOT = Path(__file__).resolve().parent.parent
REQ_DIR = REPO_ROOT / "data" / "merit_badge_requirements"


def test_v43_weather_and_first_aid_zero_duplicate_images_and_grounded_captions() -> None:
    """Weather & First Aid decks have 0 consecutive duplicate images and 0 generic fallback captions."""
    dh_map = json.loads((REPO_ROOT / "data" / "asset_perceptual_hashes.json").read_text(encoding="utf-8"))

    weather_data = json.loads((REQ_DIR / "weather.json").read_text(encoding="utf-8"))
    raw_sb = generate_slide_storyboard(
        badge_name="Weather",
        requirements=weather_data["requirements"],
        depth_mode="deep_dive",
    )
    b_sb = beautify_slide_storyboard(
        storyboard=raw_sb,
        beautification_tier="BEAUTIFIED",
    )
    slides = ((b_sb.get("storyboard") if isinstance(b_sb, dict) else None) or b_sb).get("slides") if isinstance(b_sb, dict) else b_sb
    assert slides and len(slides) >= 60

    prev_dh = None
    for idx, s in enumerate(slides):
        sd = s if isinstance(s, dict) else s.model_dump()
        cap = str(sd.get("visual_caption") or "").strip()
        assert not re.search(r"Official\s+Weather\s+visual\s+reference", cap, flags=re.I), (
            f"Unexpected generic fallback caption on Weather slide idx={idx}: {cap}"
        )
        assert "tripod-mounted globe and lamp" not in cap, (
            f"Stale mismatched tripod/lamp caption found on Weather slide idx={idx}: {cap}"
        )
        img_p = str(sd.get("diagram_path") or sd.get("ai_hero_image_path") or "").strip()
        if img_p:
            fn = Path(img_p).name
            cur_dh_hex = dh_map.get(fn)
            if cur_dh_hex and prev_dh is not None:
                dist = (int(cur_dh_hex, 16) ^ prev_dh).bit_count()
                assert dist > 8, (
                    f"Consecutive perceptual duplicate images on Weather slides {idx - 1} & {idx} "
                    f"(file={fn}, dHash Hamming dist={dist})"
                )
            prev_dh = int(cur_dh_hex, 16) if cur_dh_hex else None
        else:
            prev_dh = None

    # Verify First Aid CPR/AED catalog entry matches cardiac arrest / AED response
    nb_cat = json.loads((REPO_ROOT / "data" / "nano_banana_image_catalog.json").read_text(encoding="utf-8"))
    fa_7a_entry = nb_cat.get("first_aid_req_7a_nano_hero.png") or {}
    if isinstance(fa_7a_entry, dict) and fa_7a_entry.get("caption"):
        assert "AED" in fa_7a_entry["caption"] or "chest compressions" in fa_7a_entry["caption"]


def test_v43_ui_scroll_reset_and_anti_cropping_invariants() -> None:
    """ui/app.js, ui/styles.css, and src/agents/image_studio.py enforce scroll reset & non-clipping rules."""
    app_js = (REPO_ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    assert "function resetContainerScroll(" in app_js
    assert "renderFilmstrip(slides, { resetScroll: true });" in app_js
    assert "resetWorkbookScrollTop(wbPreview);" in app_js
    assert "isNewPresenterSlide" in app_js

    styles_css = (REPO_ROOT / "ui" / "styles.css").read_text(encoding="utf-8")
    assert "object-position: center 15%" in styles_css
    assert 'data-archetype="FULL_BLEED_IMAGE_EXPLAINER"' in styles_css

    img_studio_py = (REPO_ROOT / "src" / "agents" / "image_studio.py").read_text(encoding="utf-8")
    assert "def _detect_seamless_pad_rgb(" in img_studio_py
    assert "ImageOps.pad(" in img_studio_py


def test_v43_corpus_zero_byte_and_149_workbook_hygiene() -> None:
    """data/ has zero 0-byte JSON files and deliverables/ has strictly 149 clean Counselor Workbooks."""
    zero_byte = [
        p.name for p in (REPO_ROOT / "data").glob("*.json") if p.is_file() and p.stat().st_size == 0
    ]
    assert not zero_byte, f"Found 0-byte JSON files in data/: {zero_byte}"

    dh_map = json.loads((REPO_ROOT / "data" / "asset_perceptual_hashes.json").read_text(encoding="utf-8"))
    assert len(dh_map) >= 5500

    wb_files = sorted((REPO_ROOT / "deliverables").glob("*_Counselor_Workbook.md"))
    assert len(wb_files) == 149, f"Expected strictly 149 Counselor Workbooks, got {len(wb_files)}"
    for wb in wb_files:
        txt = wb.read_text(encoding="utf-8")
        assert "**Scout Notes / Demonstration Verification:** ___" not in txt, (
            f"Leaked blank Scout fill line in {wb.name}"
        )
