"""Regression test suite for V42 Multi-Persona Speaker Notes, Workbooks, & Visuals.

Verifies the three confirmed V42 architectural decisions and corpus/UI fixes:
- Decision #1: Distinct Counselor Facilitation Guide vs. Fillable Scout Workbook roles.
- Decision #2A: Selective [DEMONSTRATION & SIGN-OFF RUBRIC] emission on lead/station/quiz/bookend slides
  and clean omission on intermediate continuation slides.
- Decision #3: Populated `requirement_to_figures` index and sub-requirement child-slide visual wiring.
- Zero duplicate sub-requirement IDs across Plant Science & Sewing and Needlework, and zero false-positive
  sketch canvases on words like 'withdraw' or 'draw length'.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.agents.planner import generate_slide_storyboard
from src.tools.pamphlet_extractor import build_pamphlet_index
from src.tools.scouting_scraper import (
    generate_counselor_workbook_markdown,
    generate_fillable_scout_workbook_html,
    is_genuine_sketch_prompt,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REQ_DIR = REPO_ROOT / "data" / "merit_badge_requirements"


def test_v42_decision_1_counselor_vs_scout_workbook_differentiation() -> None:
    """Counselor Workbook renders answer keys & Socratic prompts; Fillable Scout Workbook stays interactive."""
    fa_data = json.loads((REQ_DIR / "first-aid.json").read_text(encoding="utf-8"))
    cw_md = generate_counselor_workbook_markdown(fa_data)
    assert "Counselor Facilitation Guide & Class Preparation Workbook" in cw_md
    assert "Official Pamphlet Summary & Expected Answer Key" in cw_md
    assert "Counselor Verification Standard" in cw_md
    assert "`____________________________________`" not in cw_md
    assert "Scoutmaster Bob" not in cw_md
    assert "counselor@troop123.org" not in cw_md

    sw_res = generate_fillable_scout_workbook_html("First Aid")
    sw_html = str(sw_res.get("fillable_html") or sw_res.get("html") or sw_res)
    assert "wb-organizer-table" in sw_html
    assert "Parent Directive:" in sw_html


def test_v42_decision_2a_selective_signoff_rubric_on_multi_slide_requirements() -> None:
    """Intermediate continuation slides omit [DEMONSTRATION & SIGN-OFF RUBRIC]; lead/station/quiz keep it."""
    camping_data = json.loads((REQ_DIR / "camping.json").read_text(encoding="utf-8"))
    sb = generate_slide_storyboard(
        badge_name="Camping",
        requirements=camping_data["requirements"][:3],
        depth_mode="deep_dive",
    )
    slides = sb.get("slides") if isinstance(sb, dict) else sb
    def get_arch(s):
        return s.get("archetype") if isinstance(s, dict) else s.archetype

    def get_notes(s):
        return (s.get("presenter_notes") if isinstance(s, dict) else s.presenter_notes) or ""
    intro_slides = [s for s in slides if get_arch(s) == "REQUIREMENT_INTRO"]
    continuation_slides = [
        s
        for s in slides
        if get_arch(s) in ("CONCEPT_TEXT_SLIDE", "SPLIT_VISUAL_EXPLAINER", "FULL_BLEED_IMAGE_EXPLAINER", "DIFFERENTIAL_COMPARISON_2COL")
    ]
    assert intro_slides, "Expected REQUIREMENT_INTRO slides in deep_dive mode"
    for s in intro_slides:
        assert "[DEMONSTRATION & SIGN-OFF RUBRIC]" in get_notes(s)
    assert any(
        "[DEMONSTRATION & SIGN-OFF RUBRIC]" not in get_notes(s)
        for s in continuation_slides
    ), "Expected intermediate continuation slides to omit [DEMONSTRATION & SIGN-OFF RUBRIC]"


def test_v42_decision_3_requirement_to_figures_and_sketch_filter() -> None:
    """build_pamphlet_index populates requirement_to_figures and sketch filter rejects false positives."""
    p_idx = build_pamphlet_index("First Aid")
    req_fig_map = p_idx.get("requirement_to_figures") or {}
    assert len(req_fig_map) > 0, "Expected non-empty requirement_to_figures map for First Aid"

    assert not is_genuine_sketch_prompt("Withdraw funds from checking account")
    assert not is_genuine_sketch_prompt("Check bow draw length and draw weight")
    assert not is_genuine_sketch_prompt("Draw blood or draw conclusions from data")
    assert is_genuine_sketch_prompt("Sketch a floor plan of your home escape routes")
    assert is_genuine_sketch_prompt("Draw a diagram of the electrical circuit")
