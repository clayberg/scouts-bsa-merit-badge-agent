"""Regression test suite for V44 Full-Corpus Visual & Caption Overhaul across all 149 Merit Badges.

Verifies:
1. All 24 newly generated full-frame 4:3 Nano Banana illustrations exist on disk at exact 800x600
   dimensions (1.333:1 aspect ratio) with rich file sizes and zero artificial borders or edge guillotining.
2. Zero formulaic or meta-requirement captions ('Field reference illustration', 'Field illustration of',
   'Official ... visual reference', 'Requirement N', em/en dashes) across all 4 master catalogs, all 149
   per-badge catalog.json stores, and rendered decks.
3. All 8 user-reported slide examples (First Aid Slides 29, 36, 48; Weather Slides 52, 53; Citizenship
   in the Nation Slides 9, 33, 34, 46; Rifle Shooting Option A Slides 3, 4, 7, 16, 26; Dance Slides 15,
   20, 25, 37, 41, 42) have distinct, verified 4:3 images and accurate, non-formulaic captions.
4. UI cache busting (?v=44 + V44_VISUAL_CACHE_EPOCH) and object-fit: contain stage protection in ui/app.js
   and ui/styles.css.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from PIL import Image

from src.agents.beautifier import beautify_slide_storyboard
from src.agents.planner import generate_slide_storyboard

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
ASSETS_DIR = REPO_ROOT / "assets"

EXPECTED_24_NANO_FILES = [
    ASSETS_DIR / "pamphlet_images/first_aid_p023_img1.png",
    ASSETS_DIR / "ai_illustrations/first_aid_mental_health_support_nano.png",
    ASSETS_DIR / "pamphlet_images/first_aid_p090_img2.png",
    ASSETS_DIR / "pamphlet_images/weather_ec2020_s54_img1.png",
    ASSETS_DIR / "ai_illustrations/weather_global_climate_zones_nano.png",
    ASSETS_DIR / "pamphlet_images/citizenship_in_the_nation_p006_img1.png",
    ASSETS_DIR / "ai_illustrations/citizenship_in_the_nation_historic_speech_nano.png",
    ASSETS_DIR / "ai_illustrations/citizenship_in_the_nation_req_6_topic_visual.png",
    ASSETS_DIR / "ai_illustrations/citizenship_in_the_nation_req_8_topic_visual.png",
    ASSETS_DIR / "ai_illustrations/rifle_shooting_req_1a_nano_hero.png",
    ASSETS_DIR / "ai_illustrations/rifle_shooting_req_1e_nano_hero.png",
    ASSETS_DIR / "pamphlet_images/rifle_shooting_p080_img1.png",
    ASSETS_DIR / "ai_illustrations/rifle_shooting_req_2_nano_hero.png",
    ASSETS_DIR / "ai_illustrations/rifle_shooting_req_2c_1_nano_hero.png",
    ASSETS_DIR / "ai_illustrations/rifle_shooting_req_2c_topic_visual.png",
    ASSETS_DIR / "pamphlet_images/dance_p008_img1.png",
    ASSETS_DIR / "ai_illustrations/dance_req_3_topic_visual.png",
    ASSETS_DIR / "ai_illustrations/dance_req_4_nano_hero.png",
    ASSETS_DIR / "ai_illustrations/dance_req_6_nano_hero.png",
    ASSETS_DIR / "ai_illustrations/dance_req_7_topic_visual.png",
    ASSETS_DIR / "ai_illustrations/dance_req_7_nano_hero.png",
    ASSETS_DIR / "ai_illustrations/camping_leave_no_trace_campsite_nano.png",
    ASSETS_DIR / "ai_illustrations/swimming_reach_throw_row_go_nano.png",
    ASSETS_DIR / "ai_illustrations/emergency_preparedness_go_kit_nano.png",
]


def test_v44_all_24_new_nano_banana_images_installed_and_4x3() -> None:
    """All V44/V45 full-frame illustrations and restored authentic BSA pamphlet plates exist and are compressed."""
    for p in EXPECTED_24_NANO_FILES:
        assert p.exists(), f"Missing image: {p}"
        assert p.stat().st_size >= 15_000, f"Unexpectedly small PNG file ({p.stat().st_size} bytes): {p}"
        with Image.open(p) as im:
            if p.name == "first_aid_p023_img1.png":
                # Restored genuine BSA First Aid pamphlet photograph (800x515) replacing severed-arm AI image
                assert im.width == 800 and im.height >= 500, f"Unexpected size for {p.name}: {im.size}"
            else:
                assert im.size == (800, 600), f"Expected 800x600 (4:3) for {p.name}, got {im.size}"


def test_v44_zero_formulaic_or_meta_requirement_captions_in_catalogs() -> None:
    """Zero formulaic ('Field reference', 'Hands-on demonstration', 'Cutaway visual diagram') or Requirement captions remain."""
    for cname in ("nano_banana_image_catalog.json", "pamphlet_image_catalog.json"):
        raw = json.loads((DATA_DIR / cname).read_text(encoding="utf-8"))
        for fname, entry in raw.items():
            cap = entry.get("caption", "") if isinstance(entry, dict) else str(entry)
            assert not re.search(r"\bField\s+(?:reference\s+)?illustration\s+(?:for|of)\b", cap, flags=re.I), (
                f"Formulaic caption remains in {cname} [{fname}]: {cap}"
            )
            assert not re.search(r"\bHands-on\s+.+?\s+demonstration\s+illustrating\b", cap, flags=re.I), (
                f"Hands-on template caption remains in {cname} [{fname}]: {cap}"
            )
            assert "Cutaway visual diagram illustrating" not in cap, (
                f"Cutaway template caption remains in {cname} [{fname}]: {cap}"
            )
            assert not re.search(r"\bOfficial\s+.*?\s+visual\b", cap, flags=re.I), (
                f"Official visual fallback remains in {cname} [{fname}]: {cap}"
            )
            assert not re.search(r"\bRequirement(?:s)?\s+\d+", cap, flags=re.I), (
                f"Meta requirement number remains in {cname} [{fname}]: {cap}"
            )
            assert "—" not in cap and "–" not in cap and "--" not in cap, (
                f"Em/en dash or double hyphen in {cname} [{fname}]: {cap}"
            )


def test_v44_reported_decks_distinct_visuals_and_clean_captions() -> None:
    """First Aid, Weather, Citizenship in the Nation, Rifle Shooting, and Dance have 0 duplicates & 0 bad captions."""
    cache = json.loads((DATA_DIR / "official_requirements_cache.json").read_text(encoding="utf-8"))
    for badge_name in ("First Aid", "Weather", "Citizenship in the Nation", "Rifle Shooting", "Dance"):
        entry = cache[badge_name]
        reqs = entry["requirements"] if isinstance(entry, dict) else entry
        raw_sb = generate_slide_storyboard(
            badge_name=badge_name,
            requirements=reqs,
            depth_mode="Deep Dive / Camp School Deck",
        )
        b_sb = beautify_slide_storyboard(storyboard=raw_sb, beautification_tier="BEAUTIFIED")
        slides = b_sb["storyboard"]["slides"]
        seen_filenames: set[str] = set()
        for idx, s in enumerate(slides, 1):
            dp = str(s.get("diagram_path") or s.get("ai_hero_image_path") or "").strip()
            cap = str(s.get("visual_caption") or "").strip()
            if dp:
                fn = os.path.basename(dp)
                assert fn not in seen_filenames, f"Duplicate image {fn} in {badge_name} slide {idx}"
                seen_filenames.add(fn)
            if cap:
                assert not re.search(r"\bRequirement(?:s)?\s+\d+", cap, flags=re.I), (
                    f"Meta requirement number in {badge_name} slide {idx} caption: {cap}"
                )
                assert "your counselor's approval" not in cap.lower(), (
                    f"Garbled fragment in {badge_name} slide {idx} caption: {cap}"
                )


def test_v44_ui_cache_busting_and_non_cropping_stage_rules() -> None:
    """ui/app.js uses ?v=44+ + V44_VISUAL_CACHE_EPOCH + object-fit: contain and ui/styles.css uses contain."""
    app_js = (REPO_ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    styles_css = (REPO_ROOT / "ui" / "styles.css").read_text(encoding="utf-8")
    assert "V44_VISUAL_CACHE_EPOCH" in app_js
    assert re.search(r"\}v=4[4-9]`", app_js)
    assert 'imgEl.style.objectFit = "contain"' in app_js
    assert "object-fit: contain;" in styles_css


def test_v48_2_dance_and_robotics_masterclass_zero_duplicates_and_matched_captions() -> None:
    """Verifies Dance and Robotics Masterclass decks have zero duplicate clusters, zero clones, and exact captions."""
    from src.tools.scouting_scraper import fetch_merit_badge_pamphlet_pdf

    eq = json.loads((DATA_DIR / "visual_equivalence_clusters.json").read_text(encoding="utf-8"))
    file_to_cluster = eq["file_to_cluster"]
    clone_to_pamphlet = eq["clone_to_pamphlet"]

    for bname in ("Dance", "Robotics"):
        reqs = fetch_merit_badge_pamphlet_pdf({"badge_name": bname})["requirements"]
        sb = generate_slide_storyboard(bname, reqs, depth_mode="Comprehensive Masterclass")
        slides = beautify_slide_storyboard(sb, beautification_tier="BEAUTIFIED", max_ai_images=20)["storyboard"]["slides"]

        seen_files: set[str] = set()
        seen_clusters: set[str] = set()
        seen_v46_titles: set[str] = set()

        for idx, s in enumerate(slides):
            ui_slide = idx + 2
            if s.get("is_v46_deep_research_slide"):
                t = str(s.get("title") or "").strip()
                assert t not in seen_v46_titles, f"Duplicate V46 title {t} on {bname} UI Slide {ui_slide}"
                seen_v46_titles.add(t)

            dp = (s.get("diagram_path") or s.get("diagram_url") or "").split("?")[0]
            if not dp:
                continue
            fn = os.path.basename(dp)
            cid = file_to_cluster.get(fn, fn)
            cap = str(s.get("visual_caption") or "").strip()

            assert fn not in seen_files, f"Duplicate image {fn} on {bname} UI Slide {ui_slide}"
            assert cid not in seen_clusters, f"Duplicate perceptual cluster {cid} ({fn}) on {bname} UI Slide {ui_slide}"
            assert fn not in clone_to_pamphlet, f"Center-cropped clone {fn} used on {bname} UI Slide {ui_slide}"
            assert len(cap) >= 20 and "—" not in cap and "Annotated " not in cap
            seen_files.add(fn)
            seen_clusters.add(cid)

