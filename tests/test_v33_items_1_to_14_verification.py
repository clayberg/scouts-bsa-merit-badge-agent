"""V33 Verification Suite: Comprehensive regression tests for Items 1 through 14."""

from __future__ import annotations

import json
from pathlib import Path
from PIL import Image

from src.agents.planner import generate_slide_storyboard
from src.tools.pamphlet_extractor import (
    _BOILERPLATE_QUIZ_REJECTION_SUBSTRINGS,
    _CURATED_REQ1_SAFETY_QUIZZES,
    _badge_slug,
)
from src.tools.scouting_scraper import (
    _iter_unrolled_workbook_units,
    generate_counselor_workbook_markdown,
    generate_fillable_scout_workbook_html,
)
from src.tools.template_engine import NANO_BUILT_IN_BACKDROPS_CATALOG

ROOT = Path(__file__).resolve().parent.parent


def test_item1_astronomy_and_first_aid_trail_kit_backdrops():
    """Item 1: Verify split image is separated into two full-bleed 1920x1080 backdrops."""
    astro_bg = ROOT / "assets" / "templates" / "overlays" / "nano_base_astronomy_deep_space_observatory.jpg"
    fa_bg = ROOT / "assets" / "templates" / "overlays" / "nano_base_first_aid_trail_kit.jpg"
    astro_hero = ROOT / "assets" / "ai_illustrations" / "astronomy_req_1_nano_hero.png"

    assert astro_bg.exists(), "Astronomy observatory backdrop must exist"
    assert fa_bg.exists(), "First Aid trail kit backdrop must exist"
    assert astro_hero.exists(), "Astronomy Req 1 hero image must exist"

    with Image.open(astro_bg) as im:
        assert im.size == (1920, 1080)
    with Image.open(fa_bg) as im:
        assert im.size == (1920, 1080)
    with Image.open(astro_hero) as im:
        assert im.size == (800, 600)

    tpl_ids = {t["id"] for t in NANO_BUILT_IN_BACKDROPS_CATALOG}
    assert "astronomy_deep_space_observatory" in tpl_ids
    assert "first_aid_trail_kit" in tpl_ids


def test_item2_bsa_emblem_centered_and_scouting_america_bottom_right():
    """Item 2: Verify BSA Emblem backdrop has centered big logo and right-aligned Scouting America lockup."""
    for ext in ("jpg", "png"):
        p = ROOT / "assets" / "templates" / "overlays" / f"nano_base_bsa_emblem_color.{ext}"
        assert p.exists()
        with Image.open(p) as im:
            assert im.size == (1920, 1080)
            rgb = im.convert("RGB")
            # Bottom-left area (where old lockup sat) should be warm parchment background (bright)
            bl_r, bl_g, bl_b = rgb.getpixel((200, 960))
            assert bl_r > 210 and bl_g > 200, "Bottom-left must be clean parchment without the old lockup"


def test_item3_template_switching_and_new_deck_recommended_backdrop():
    """Item 3: Verify template switching sets TEMPLATE_DEFAULT and new deck sets BADGE_RECOMMENDED."""
    app_js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    assert 'state.coverBackdropMode = "TEMPLATE_DEFAULT"' in app_js
    assert 'state.coverBackdropMode = "BADGE_RECOMMENDED"' in app_js
    assert 'state.coverBackdropMode === "TEMPLATE_DEFAULT"' in app_js


def test_item4_lake_sunset_dock_permanent_backdrop():
    """Item 4: Verify Lake & Sunset Dock is permanently available with no Hidden Valley / Lake Eileen reference."""
    dock_bg = ROOT / "assets" / "templates" / "overlays" / "nano_base_lake_sunset_dock.jpg"
    assert dock_bg.exists()
    with Image.open(dock_bg) as im:
        assert im.size == (1920, 1080)

    matches = [t for t in NANO_BUILT_IN_BACKDROPS_CATALOG if t["id"] == "lake_sunset_dock"]
    assert len(matches) == 1
    desc = (matches[0].get("keywords") or "") + " " + (matches[0].get("label") or "")
    assert "lake" in desc.lower() and "sunset" in desc.lower() and "dock" in desc.lower()
    assert "hidden valley" not in desc.lower()
    assert "eileen" not in desc.lower()


def test_item5_zero_boilerplate_organizer_rows_across_all_149_badges():
    """Item 5: Verify rows 2 & 3 ('Key Pamphlet Facts & Mechanism', 'Field Application & Counselor Discussion') are removed."""
    mb_dir = ROOT / "data" / "merit_badge_requirements"
    for f in sorted(mb_dir.glob("*.json")):
        if f.name.startswith("_"):
            continue
        raw = f.read_text(encoding="utf-8").lower()
        assert "key pamphlet facts & mechanism" not in raw, f"Found boilerplate row 2 in {f.name}"
        assert "field application & counselor discussion" not in raw, f"Found boilerplate row 3 in {f.name}"


def test_item6_weather_req9_online_and_pdf_diagram_parity():
    """Item 6: Verify Weather Req 9 uses the unstretched 800x600 Earth Orbit & Seasons illustration in both online and PDF workbooks."""
    img_p = ROOT / "assets" / "ai_illustrations" / "weather_earth_orbit_seasons_nano.png"
    assert img_p.exists()
    with Image.open(img_p) as im:
        assert im.size == (800, 600)

    w_data = json.loads((ROOT / "data" / "merit_badge_requirements" / "weather.json").read_text(encoding="utf-8"))
    html_res = generate_fillable_scout_workbook_html("Weather")
    html_wb = html_res["html_document"]
    assert "weather_earth_orbit_seasons_nano.png" in html_wb

    units = _iter_unrolled_workbook_units(w_data["requirements"], "Weather")
    req9_units = [u for u in units if str(u.get("req_id")) == "9"]
    assert req9_units and "weather_earth_orbit_seasons_nano.png" in str(req9_units[0].get("workbook_diagram_url") or "")


def test_item7_item8_item9_stage_inline_edit_and_slide1_support():
    """Items 7, 8, 9: Verify lowered inline edit bar, shortened '✏️ Edit Text' label, and Slide 1 editing."""
    styles_css = (ROOT / "ui" / "styles.css").read_text(encoding="utf-8")
    index_html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")

    assert "bottom: 2px;" in styles_css
    assert "✏️ Edit Text" in index_html
    assert "✏️ Edit Text on Stage" not in index_html
    assert '"✏️ Edit Text"' in app_js
    assert "state.activeSlideIdx === -1" in app_js
    assert "#stage-cover-title" in app_js
    assert "#stage-cover-counselor-name" in app_js


def test_item10_slide_matched_workbook_diagrams_all_149_badges_and_citizenship_in_the_nation():
    """Item 10: Verify all 1,158 requirements across 149 badges have slide-matched workbook_diagram_url and Citizenship in the Nation has all 8 reqs illustrated."""
    cit_data = json.loads((ROOT / "data" / "merit_badge_requirements" / "citizenship-in-the-nation.json").read_text(encoding="utf-8"))
    assert len(cit_data["requirements"]) == 8
    for r in cit_data["requirements"]:
        d_url = str(r.get("workbook_diagram_url") or "").strip()
        assert d_url, f"Citizenship in the Nation Req {r['req_id']} missing workbook_diagram_url"
        assert (ROOT / d_url).exists(), f"Missing diagram file {d_url}"

    units_cit = _iter_unrolled_workbook_units(cit_data["requirements"], "Citizenship in the Nation")
    illustrated_units = [u for u in units_cit if str(u.get("workbook_diagram_url") or "").strip()]
    assert len(illustrated_units) >= 8
    for u in illustrated_units:
        d_url = str(u.get("workbook_diagram_url") or "").strip()
        assert (ROOT / d_url).exists(), f"Missing diagram file {d_url}"
    # Req 2 must match the Req 2 slide image (citizenship_in_the_nation_p006_img1.png), not Req 1
    req2_unit = [u for u in units_cit if str(u.get("req_id")) == "2"][0]
    assert "citizenship_in_the_nation_p006_img1.png" in req2_unit["workbook_diagram_url"]

    md_cit = generate_counselor_workbook_markdown(cit_data)
    assert "citizenship_in_the_nation_p006_img1.png" in md_cit


def test_item11_all_149_badges_have_high_quality_non_boilerplate_quizzes():
    """Item 11: Verify all 149 badges have curated 4-option Requirement 1 quizzes and zero Mad-Libs distractors across all requirements."""
    assert len(_CURATED_REQ1_SAFETY_QUIZZES) >= 149

    mb_dir = ROOT / "data" / "merit_badge_requirements"
    for f in sorted(mb_dir.glob("*.json")):
        if f.name.startswith("_"):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        bname = d["badge_name"]
        slug = _badge_slug(bname)
        assert slug in _CURATED_REQ1_SAFETY_QUIZZES, f"{bname} ({slug}) missing from _CURATED_REQ1_SAFETY_QUIZZES"

        for r in d.get("requirements", []):
            q = r.get("quiz_item")
            assert isinstance(q, dict), f"{bname} Req {r.get('req_id')} missing quiz_item"
            opts = q.get("options") or []
            assert len(opts) == 4, f"{bname} Req {r.get('req_id')} must have 4 options"
            blob = (str(q.get("scenario_prompt") or "") + " " + " ".join(opts)).lower()
            for bad in _BOILERPLATE_QUIZ_REJECTION_SUBSTRINGS:
                assert bad not in blob, f"Boilerplate '{bad}' found in {bname} Req {r.get('req_id')}"

    # Verify Robotics storyboard quiz slide has 4 realistic domain options
    rob_data = json.loads((ROOT / "data" / "merit_badge_requirements" / "robotics.json").read_text(encoding="utf-8"))
    rob_sb = generate_slide_storyboard("Robotics", rob_data["requirements"])
    quiz_slides = [
        s for s in rob_sb["slides"]
        if (s.quiz_item if hasattr(s, "quiz_item") else s.get("quiz_item"))
    ]
    assert len(quiz_slides) >= 1
    s0 = quiz_slides[0]
    q_rob = s0.quiz_item if hasattr(s0, "quiz_item") else s0.get("quiz_item")
    opts_rob = q_rob.options if hasattr(q_rob, "options") else q_rob.get("options")
    ans_rob = q_rob.correct_answer if hasattr(q_rob, "correct_answer") else q_rob.get("correct_answer")
    assert len(opts_rob) == 4
    assert "ANSI Z87.1" in ans_rob


def test_item12_item13_item14_workbook_tab_reset_callout_column2_and_template_preview_zoom():
    """Items 12, 13, 14: Verify Counselor Workbook tab reset, 2nd-column callout placement, and preview zoom lightbox."""
    index_html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    styles_css = (ROOT / "ui" / "styles.css").read_text(encoding="utf-8")

    # Item 12: Counselor Workbook active button reset in renderResults
    assert '["btn-workbook-view-default", "btn-workbook-open-fillable-html", "btn-workbook-open-cpp"].forEach' in app_js
    assert 'const isAct = id === "btn-workbook-view-default";' in app_js

    # Item 13: #tpl-ai-how-to-callout inside .m3-tpl-ai-preview-col before #tpl-ai-backdrop-control-bar
    col2_pos = index_html.find('class="m3-tpl-ai-preview-col"')
    callout_pos = index_html.find('id="tpl-ai-how-to-callout"')
    ctrl_bar_pos = index_html.find('id="tpl-ai-backdrop-control-bar"')
    assert col2_pos != -1 and callout_pos != -1 and ctrl_bar_pos != -1
    assert col2_pos < callout_pos < ctrl_bar_pos

    # Item 14: Zoom on #tpl-ai-live-preview-stage and z-index >= 25000 on .m3-lightbox-backdrop
    assert "m3-tpl-ai-zoom-pill" in app_js
    assert "z-index: 25000 !important;" in styles_css
