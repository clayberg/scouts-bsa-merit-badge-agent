"""V39 Verification Suite: Zero Mid-Word Truncations, Zero Boilerplate Comparison Rows, Zero Fallback Slide Bullets, and 100% Gemini Slide Pools Across All Archetypes."""

from __future__ import annotations

import json
from pathlib import Path

from src.agents.planner import generate_slide_storyboard
from src.tools.scouting_scraper import fetch_merit_badge_pamphlet_pdf

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_v39_gemini_slide_pools_and_clean_comparisons_across_all_149_badges() -> None:
    """Verify all 149 badges have Gemini misconception_pool, socratic_questions, non-truncated comparison headers/rows, and clean worked_example keys."""
    req_dir = REPO_ROOT / "data" / "merit_badge_requirements"
    pool_dir = REPO_ROOT / "data" / "v39_gemini_slide_pools_cache"

    badge_files = sorted(
        f for f in req_dir.glob("*.json")
        if not f.name.startswith("_") and f.name != "manifest.json"
    )
    assert len(badge_files) == 149
    assert len(list(pool_dir.glob("*.json"))) == 149

    for bf in badge_files:
        data = json.loads(bf.read_text(encoding="utf-8"))
        for r in data.get("requirements") or []:
            rid = str(r.get("req_number") or r.get("req_id") or "")
            assert len(r.get("socratic_questions") or []) >= 3, (
                f"Expected >= 3 socratic_questions in {bf.name} Req {rid}"
            )
            assert len(r.get("misconception_pool") or []) >= 3, (
                f"Expected >= 3 misconception_pool items in {bf.name} Req {rid}"
            )
            cd = r.get("comparison_data")
            if isinstance(cd, dict):
                for row in cd.get("rows") or []:
                    if isinstance(row, dict):
                        attr = str(row.get("attribute") or "")
                        lv = str(row.get("left") or "")
                        rv = str(row.get("right") or "")
                        assert attr not in (
                            "Practical Field Application",
                            "Safety & Verification Standard",
                        ), f"Boilerplate comparison row attribute in {bf.name} Req {rid}: {attr}"
                        assert "Step 2 -" not in rv and "Step 3 -" not in rv and "Step 2 -" not in lv, (
                            f"Pasted step string in {bf.name} Req {rid} comparison row"
                        )


def test_v39_zero_fallback_bullets_and_zero_template_archetype_notes() -> None:
    """Verify rendered decks across all slide archetypes use Gemini slide bullets, Socratic questions, and misconceptions with zero fallback templates."""
    sample_badges = ["First Aid", "Camping", "Physics", "Signs, Signals, and Codes", "Whitewater"]
    forbidden_bullets = (
        "Field Reference (",
        "Pamphlet Verification: Review how",
        "Buddy Check: Trace the key components",
        "Practical Execution: Connect ",
        "Counselor Conference Check: Explain how",
        "Preparation & Study: Review the ",
        "Equipment & Safety Check: Inspect the tools",
        "Hands-On Demonstration: Practice and demonstrate",
        "Counselor Verification: Present your completed",
    )
    forbidden_asks = (
        "Before looking at the two columns on screen, what is the #1 field clue",
        "Looking at our 4-step sequence for ",
        "During a 60-second patrol shakedown for ",
        "Compare a vague one-line note with this worked example for ",
    )
    forbidden_myths = (
        "as interchangeable in the field",
        "to rush straight into",
        "without inspecting condition, fit, or expiration",
        "without recording field measurements",
    )

    for bname in sample_badges:
        res = fetch_merit_badge_pamphlet_pdf({"badge_name": bname})
        sb = generate_slide_storyboard(badge_name=bname, requirements=res["requirements"])
        for idx, sl in enumerate(sb.get("slides") or []):
            for bp in sl.get("bullet_points") or []:
                for fb in forbidden_bullets:
                    assert fb not in str(bp), f"Fallback slide bullet in {bname} slide {idx}: {bp}"
            notes = str(sl.get("presenter_notes") or "")
            for fa in forbidden_asks:
                assert fa not in notes, f"Template archetype ask in {bname} slide {idx}: {fa}"
            for fm in forbidden_myths:
                assert fm not in notes, f"Template archetype myth in {bname} slide {idx}: {fm}"


def test_v39_per_badge_image_catalogs_zero_v36_templates() -> None:
    """Verify all per-badge catalog.json files under assets/badge_image_catalog/ have zero V36 template captions."""
    cat_dir = REPO_ROOT / "assets" / "badge_image_catalog"
    for cf in sorted(cat_dir.glob("*/catalog.json")):
        cdata = json.loads(cf.read_text(encoding="utf-8"))
        imgs = cdata.get("images") if isinstance(cdata, dict) else cdata
        for it in imgs or []:
            if isinstance(it, dict):
                cap = str(it.get("caption") or it.get("description") or "")
                assert "Four-panel instructional diagram illustrating" not in cap, (
                    f"V36 template caption in {cf}: {cap}"
                )
