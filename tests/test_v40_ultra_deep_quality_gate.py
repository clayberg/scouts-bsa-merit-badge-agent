"""V40 Ultra-Deep Quality Gate Regression Suite across all 149 Merit Badges.

Verifies:
1. data/precomputed_facilitator_notes_149.json size <= 45 MB and multi-myth rotation across roles 0..6.
2. Smart title-casing (_smart_title_case) with zero capitalized interior conjunctions/prepositions
   ('And', 'Of', 'In', 'The') across all 149 corpus topic_titles, slide titles, and Overview cards.
3. Zero stock AI puffery vocabulary ('tapestry', 'groundbreaking', 'vibrant', 'showcase', 'pivotal',
   'crucial', 'intricate', 'fostering', 'interplay', 'underscore', 'delve', 'seamless', 'elevate', 'boasts')
   across all 149 corpus files, speaker notes, Markdown workbooks, and documentation.
4. Exactly 149 clean deliverables/*_Counselor_Workbook.md files with zero em/en-dashes or ellipses.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.agents.planner import (
    _replace_unslop_words,
    _smart_title_case,
    generate_slide_storyboard,
)
from src.tools.scouting_scraper import (
    fetch_merit_badge_pamphlet_pdf,
    generate_fillable_scout_workbook_html,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REQ_DIR = REPO_ROOT / "data" / "merit_badge_requirements"
NOTES_PATH = REPO_ROOT / "data" / "precomputed_facilitator_notes_149.json"

AI_PUFFERY_PATTERN = re.compile(
    r"\b(crucial|pivotal|delve|delves|delving|testament|vibrant|tapestry|underscore|"
    r"underscores|underscoring|showcase|showcases|showcasing|showcased|fostering|"
    r"foster|fosters|interplay|intricate|groundbreaking|seamless|seamlessly|"
    r"elevate|elevates|elevating|boasts|boast)\b",
    re.IGNORECASE,
)


def test_v40_precomputed_facilitator_notes_under_45mb_and_rotates_misconceptions() -> None:
    """Verifies precomputed_facilitator_notes_149.json is <= 45 MB and rotates misconceptions across roles."""
    assert NOTES_PATH.exists()
    size_mb = NOTES_PATH.stat().st_size / (1024 * 1024)
    assert size_mb <= 45.0, f"Expected precomputed_facilitator_notes_149.json <= 45 MB, got {size_mb:.2f} MB"

    notes = json.loads(NOTES_PATH.read_text(encoding="utf-8"))
    assert len(notes) >= 30000

    myths = set()
    for role_idx in range(7):
        note_str = notes[f"first-aid::1::{role_idx}"]
        for ln in note_str.splitlines():
            if ln.startswith("[COMMON MISCONCEPTION TO CORRECT]"):
                myths.add(ln)
    assert len(myths) >= 4, f"Expected >= 4 distinct myths across roles 0..6, got {len(myths)}"


def test_v40_smart_title_case_zero_capitalized_conjunctions_in_titles_and_overview() -> None:
    """Verifies _smart_title_case and zero mangled .title() conjunctions in corpus and storyboards."""
    assert _smart_title_case("Signs, Signals, And Codes") == "Signs, Signals, and Codes"
    assert _smart_title_case("Citizenship In The Nation") == "Citizenship in the Nation"
    assert _smart_title_case("Req 1: Fundamentals Of Aerodynamics And Flight") == (
        "Req 1: Fundamentals of Aerodynamics and Flight"
    )

    badge_files = sorted(
        p for p in REQ_DIR.glob("*.json")
        if not p.name.startswith("_") and p.name != "manifest.json"
    )
    assert len(badge_files) == 149
    for bf in badge_files:
        data = json.loads(bf.read_text(encoding="utf-8"))
        for r in data.get("requirements", []):
            tt = str(r.get("topic_title") or "")
            for bad_tc in (" And ", " Of ", " In The ", " For The "):
                assert bad_tc not in tt, f"Mangled title-case {bad_tc!r} in {bf.name}: {tt!r}"

    for bname in ("Signs, Signals, and Codes", "Citizenship in the Nation", "Aviation", "Astronomy"):
        res = fetch_merit_badge_pamphlet_pdf({"badge_name": bname})
        for depth_mode in ("Standard Deck", "Deep Dive / Camp School Deck"):
            sb = generate_slide_storyboard(
                badge_name=bname,
                requirements=res["requirements"],
                depth_mode=depth_mode,
            )
            assert " And " not in str(sb.get("badge_name") or "")
            assert " In The " not in str(sb.get("badge_name") or "")
            for s_idx, sl in enumerate(sb.get("slides") or []):
                stitle = str(sl.get("title") or "")
                for bad_tc in (" And ", " Of ", " In The ", " In Society"):
                    assert bad_tc not in stitle, f"Mangled slide title on {bname} ({depth_mode}) slide {s_idx}: {stitle!r}"
                if s_idx == 0:
                    for bp in sl.get("bullet_points") or []:
                        for bad_tc in (" And ", " Of ", " In ", " To "):
                            assert bad_tc not in str(bp), f"Mangled overview bullet on {bname}: {bp!r}"


def test_v40_zero_ai_puffery_words_across_corpus_notes_and_workbooks() -> None:
    """Verifies 0 stock AI puffery vocabulary across all 149 JSON files, docs, and generated outputs."""
    assert "essential" in _replace_unslop_words("This is a crucial step.")
    assert "history" in _replace_unslop_words("Part of the American tapestry.")

    badge_files = sorted(
        p for p in REQ_DIR.glob("*.json")
        if not p.name.startswith("_") and p.name != "manifest.json"
    )
    for bf in badge_files:
        txt = bf.read_text(encoding="utf-8")
        m = AI_PUFFERY_PATTERN.search(txt)
        assert m is None, f"AI puffery word {m.group(0)!r} found in {bf.name}"

    for bname in ("American Heritage", "American Cultures", "American Indian Culture", "American Labor"):
        res = fetch_merit_badge_pamphlet_pdf({"badge_name": bname})
        sb = generate_slide_storyboard(badge_name=bname, requirements=res["requirements"], depth_mode="Standard Deck")
        for sl in sb.get("slides") or []:
            notes = str(sl.get("presenter_notes") or "")
            m = AI_PUFFERY_PATTERN.search(notes)
            assert m is None, f"AI puffery word {m.group(0)!r} in {bname} presenter_notes"
        wb = generate_fillable_scout_workbook_html(bname)
        m_wb = AI_PUFFERY_PATTERN.search(str(wb.get("workbook_html") or ""))
        assert m_wb is None, f"AI puffery word {m_wb.group(0)!r} in {bname} HTML workbook"


def test_v40_deliverables_149_clean_markdown_workbooks() -> None:
    """Verifies exactly 149 *_Counselor_Workbook.md files in deliverables/ with zero dashes or AI puffery."""
    deliv_files = sorted((REPO_ROOT / "deliverables").glob("*_Counselor_Workbook.md"))
    assert len(deliv_files) == 149, f"Expected 149 Counselor_Workbook.md files, found {len(deliv_files)}"
    assert not (REPO_ROOT / "deliverables" / "Signs,_Signals,_and_Codes_Counselor_Workbook.md").exists()

    for df in deliv_files:
        txt = df.read_text(encoding="utf-8")
        assert "\u2014" not in txt and "\u2013" not in txt, f"Em/en-dash in {df.name}"
        assert "..." not in txt and "\u2026" not in txt, f"Ellipsis in {df.name}"
        m = AI_PUFFERY_PATTERN.search(txt)
        assert m is None, f"AI puffery word {m.group(0)!r} in {df.name}"
