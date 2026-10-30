"""V41 Verification Suite: Selective Counselor Teaching Notes, Adaptive Presenter View, and Corpus/Catalog Hygiene."""

from __future__ import annotations

import json
from pathlib import Path

from src.agents.planner import generate_slide_storyboard
from src.tools.scouting_scraper import (
    fetch_merit_badge_pamphlet_pdf,
    generate_counselor_workbook_markdown,
    generate_fillable_scout_workbook_html,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REQ_DIR = REPO_ROOT / "data" / "merit_badge_requirements"
PAMPHLET_CAT_PATH = REPO_ROOT / "data" / "pamphlet_image_catalog.json"


def _iter_badge_files():
    return sorted(
        f for f in REQ_DIR.glob("*.json")
        if not f.name.startswith("_") and f.name != "manifest.json"
    )


def test_v41_selective_speaker_notes_and_zero_parenthetical_repeats() -> None:
    """Verify [COMMON MISCONCEPTION TO CORRECT] is selectively omitted on bookend/quiz/worked-example/gear slides and has 0 repeats."""
    for bname in ("First Aid", "Action Sports", "American Business", "Camping", "Signs, Signals, and Codes"):
        res = fetch_merit_badge_pamphlet_pdf({"badge_name": bname})
        for depth in ("Standard Deck", "Deep Dive"):
            sb = generate_slide_storyboard(
                badge_name=bname,
                requirements=res["requirements"],
                depth_mode=depth,
                is_eagle_required=bool(res.get("is_eagle_required")),
            )
            slides = sb["slides"]
            seen_myths: set[str] = set()
            for idx, sl in enumerate(slides):
                arch = str(sl.get("archetype") or "")
                notes = str(sl.get("presenter_notes") or "")
                assert "[PACING & MODALITY]" in notes, f"{bname} ({depth}) slide {idx} missing [PACING & MODALITY]"
                assert "[DEMONSTRATION & SIGN-OFF RUBRIC]" in notes, f"{bname} ({depth}) slide {idx} missing [DEMONSTRATION & SIGN-OFF RUBRIC]"

                # Zero parenthetical disambiguation repeats
                assert '(specifically during "' not in notes, f"Parenthetical myth repeat in {bname} slide {idx}"
                assert 'when working on "' not in notes, f"Synthesized myth repeat in {bname} slide {idx}"
                assert "(Focus on " not in notes, f"Parenthetical ask repeat in {bname} slide {idx}"

                if arch == "SOURCES_AND_REFERENCES":
                    assert "[ASK SCOUTS FIRST]" not in notes
                    assert "[EXPECTED PAMPHLET ANSWER KEY]" not in notes
                    assert "[COMMON MISCONCEPTION TO CORRECT]" not in notes
                elif arch in (
                    "REQUIREMENTS_TRIAGE_MATRIX",
                    "SOCRATIC_CHECKPOINT_QUIZ",
                    "WORKED_EXAMPLE_TEMPLATE",
                    "GEAR_CHECKLIST_GRID",
                ):
                    assert "[ASK SCOUTS FIRST]" in notes
                    assert "[EXPECTED PAMPHLET ANSWER KEY]" in notes
                    assert "[COMMON MISCONCEPTION TO CORRECT]" not in notes
                    assert sl.get("misconception_pair") is None

                for ln in notes.splitlines():
                    if ln.strip().startswith("[COMMON MISCONCEPTION TO CORRECT]"):
                        assert ln.strip().lower() not in seen_myths, (
                            f"Duplicate [COMMON MISCONCEPTION TO CORRECT] in {bname} ({depth}) slide {idx}: {ln}"
                        )
                        seen_myths.add(ln.strip().lower())

                # Verify on-slide misconception_pair matches the slide's speaker note misconception
                mp = sl.get("misconception_pair")
                if isinstance(mp, dict) and mp.get("misconception"):
                    assert mp["misconception"] in notes, (
                        f"On-slide misconception_pair out of sync with speaker notes in {bname} slide {idx}"
                    )


def test_v41_corpus_selective_safety_gear_comparisons_and_worked_examples() -> None:
    """Verify selective safety_callout, zero Mad-Lib gear items, distinct comparison_data columns, and distinct worked_example fields."""
    badge_files = _iter_badge_files()
    assert len(badge_files) == 149

    non_hazard_safety_count = 0
    for bf in badge_files:
        d = json.loads(bf.read_text(encoding="utf-8"))
        for r in d.get("requirements") or []:
            rid = str(r.get("req_id") or r.get("req_number") or "")
            sc = str(r.get("safety_callout") or "").strip()
            if sc:
                for forced_term in ("accounting fraud", "embezzlement", "encrypted storage drives", "revisionist claims"):
                    assert forced_term not in sc.lower(), f"Forced non-hazard safety_callout in {bf.name} Req {rid}: {sc}"
            else:
                non_hazard_safety_count += 1

            for g in r.get("gear_checklist") or []:
                gs = str(g)
                assert not gs.startswith("Official ") or "Merit" not in gs, f"Mad-Lib gear item in {bf.name} Req {rid}: {gs}"
                assert "Field notebook, verification log sheet, and demonstration materials for" not in gs
                assert "Buddy-pair checklist and counselor review rubric" not in gs
                assert "workbook organizer for Req" not in gs

            cd = r.get("comparison_data") or {}
            l_pts = {str(x).strip().lower() for x in (cd.get("left_points") or []) if str(x).strip()}
            r_pts = {str(x).strip().lower() for x in (cd.get("right_points") or []) if str(x).strip()}
            assert l_pts and r_pts, f"Empty comparison_data points in {bf.name} Req {rid}"
            assert l_pts.isdisjoint(r_pts), f"Overlapping left_points and right_points in {bf.name} Req {rid}"
            comp_blob = json.dumps(cd)
            assert "Review the " not in comp_blob or "pamphlet standards" not in comp_blob, (
                f"Boilerplate comparison_data in {bf.name} Req {rid}"
            )

            we = r.get("worked_example") or {}
            we_vals = {str(v).strip().lower() for v in (we.get("fields") or {}).values() if str(v).strip()}
            assert we_vals, f"Empty worked_example fields in {bf.name} Req {rid}"
            assert we_vals.isdisjoint(l_pts), f"worked_example fields duplicate comparison_data in {bf.name} Req {rid}"

    assert non_hazard_safety_count >= 500, f"Expected >= 500 non-hazard requirements with empty safety_callout, got {non_hazard_safety_count}"


def test_v41_pamphlet_image_catalog_zero_chopped_captions_and_workbook_dedup() -> None:
    """Verify 0 chopped 'figure showing ...' captions in pamphlet_image_catalog.json and deduplicated workbook myths."""
    pcat = json.loads(PAMPHLET_CAT_PATH.read_text(encoding="utf-8"))
    for k, meta in pcat.items():
        if isinstance(meta, dict):
            cap = str(meta.get("caption") or "")
            assert "figure showing " not in cap, f"Chopped caption in pamphlet_image_catalog.json [{k}]: {cap}"

    res = fetch_merit_badge_pamphlet_pdf({"badge_name": "First Aid"})
    md = generate_counselor_workbook_markdown(res)
    myth_count_md = md.count("- **Common Myth:**")
    assert myth_count_md == len(res["requirements"]), (
        f"Expected 1 Common Myth per top-level requirement ({len(res['requirements'])}), got {myth_count_md}"
    )

    wb_html_res = generate_fillable_scout_workbook_html("First Aid")
    html_str = str(wb_html_res.get("workbook_html") or "")
    myth_count_html = html_str.count('class="wb-misconception-strip"')
    assert myth_count_html == len(res["requirements"]), (
        f"Expected {len(res['requirements'])} wb-misconception-strip blocks in HTML workbook, got {myth_count_html}"
    )


def test_v41_presenter_view_adaptive_ui_hooks() -> None:
    """Verify ui/app.js and ui/index.html implement adaptive Presenter View cue counting and slide section chips."""
    ui_js = (REPO_ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    ui_html = (REPO_ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "function countActiveFacilitatorSections(" in ui_js
    assert "function describeSlideActiveSections(" in ui_js
    assert "function syncAdaptiveFacilitatorHeadings(" in ui_js
    assert "m3-pc-slide-sections-strip" in ui_js
    assert "m3-pc-adaptive-cues-grid" in ui_js
    assert 'data-cue-count="${cards.length}"' in ui_js
    assert 'id="fullscreen-teleprompter-heading"' in ui_html
