"""V36 Verification Suite: 149-Badge Corpus, Facilitator Notes, Workbooks, Docs & Readout Deck."""

from __future__ import annotations

import json
from pathlib import Path
from pptx import Presentation

from src.agents.planner import (
    _conjugate_third_person_singular,
    _load_precomputed_facilitator_notes,
    generate_slide_storyboard,
)
from src.tools.pamphlet_extractor import (
    _CURATED_REQ1_SAFETY_QUIZZES,
    _ensure_four_quiz_options,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_v36_149_badge_json_corpus_zero_dimension_labels_and_clean_workbooks() -> None:
    """Verify all 149 badge JSONs have 0 Dimension 1..3 labels, 0 '...' row_labels, and 100+ sketch canvases."""
    req_dir = REPO_ROOT / "data" / "merit_badge_requirements"
    badge_files = sorted(
        p for p in req_dir.glob("*.json") if not p.name.startswith("_")
    )
    assert len(badge_files) == 149

    dim_label_count = 0
    ellipsis_row_count = 0
    generic_compare_header_count = 0
    sketch_canvas_count = 0

    for bf in badge_files:
        data = json.loads(bf.read_text(encoding="utf-8"))
        assert data.get("url"), f"Missing url in {bf.name}"
        assert data.get("source_url"), f"Missing source_url in {bf.name}"
        assert data.get("local_grounding_spec"), (
            f"Missing local_grounding_spec in {bf.name}"
        )

        for req in data.get("requirements", []):
            comp = req.get("comparison_data") or {}
            for row in comp.get("rows", []):
                attr = str(row.get("attribute", "")).strip()
                if attr in {"Dimension 1", "Dimension 2", "Dimension 3"}:
                    dim_label_count += 1

            wb = req.get("workbook_organizer") or {}
            if wb.get("organizer_type") == "SKETCH_AND_OBSERVATION_CANVAS":
                sketch_canvas_count += 1
            headers = wb.get("headers") or []
            if "Primary Concept / System A" in headers:
                generic_compare_header_count += 1
            for rl in wb.get("row_labels") or []:
                if str(rl).strip().endswith("..."):
                    ellipsis_row_count += 1

            for sr in req.get("sub_requirements") or []:
                swb = sr.get("workbook_organizer") or {}
                if swb.get("organizer_type") == "SKETCH_AND_OBSERVATION_CANVAS":
                    sketch_canvas_count += 1
                for rl in swb.get("row_labels") or []:
                    if str(rl).strip().endswith("..."):
                        ellipsis_row_count += 1

    assert dim_label_count == 0
    assert ellipsis_row_count == 0
    assert generic_compare_header_count == 0
    assert sketch_canvas_count >= 100


def test_v36_image_catalogs_and_precomputed_facilitator_notes_wired() -> None:
    """Verify 0 missing catalog PNGs, precomputed facilitator notes loaded & wired, and verb conjugation."""
    pamphlet_cat = json.loads(
        (REPO_ROOT / "data" / "pamphlet_image_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    nano_cat = json.loads(
        (REPO_ROOT / "data" / "nano_banana_image_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(pamphlet_cat) >= 2800
    assert len(nano_cat) >= 2790

    for fname in pamphlet_cat:
        assert (REPO_ROOT / "assets" / "pamphlet_images" / fname).exists(), (
            f"Missing {fname}"
        )
    for fname in nano_cat:
        assert (REPO_ROOT / "assets" / "ai_illustrations" / fname).exists(), (
            f"Missing {fname}"
        )

    notes_cache = _load_precomputed_facilitator_notes()
    assert len(notes_cache) >= 30000

    assert _conjugate_third_person_singular("discuss") == "discusses"
    assert (
        _conjugate_third_person_singular("personally discuss")
        == "personally discusses"
    )
    assert _conjugate_third_person_singular("sketch") == "sketches"
    assert _conjugate_third_person_singular("watch") == "watches"
    assert _conjugate_third_person_singular("do") == "does"
    assert _conjugate_third_person_singular("identify") == "identifies"

    chess_data = json.loads(
        (
            REPO_ROOT / "data" / "merit_badge_requirements" / "chess.json"
        ).read_text(encoding="utf-8")
    )
    chess_storyboard = generate_slide_storyboard(
        "Chess",
        chess_data["requirements"],
        depth_mode="Standard Deck",
    )
    for slide in chess_storyboard.get("slides", []):
        notes = str(
            slide.get("teaching_notes") or slide.get("speaker_notes") or ""
        )
        assert "Chess emergency" not in notes
        assert "discusss" not in notes
        assert "sketchs" not in notes


def test_v36_all_149_counselor_workbook_markdowns_and_4_option_quizzes() -> (
    None
):
    """Verify all 149 deliverables/*_Counselor_Workbook.md exist and quizzes have 4 options."""
    deliv_mds = list((REPO_ROOT / "deliverables").glob("*_Counselor_Workbook.md"))
    assert len(deliv_mds) >= 149

    fa_q1 = _ensure_four_quiz_options(
        _CURATED_REQ1_SAFETY_QUIZZES["first_aid"], badge_name="First Aid"
    )
    assert len(fa_q1["options"]) == 4
    assert any(str(opt).startswith("D.") for opt in fa_q1["options"])


def test_v36_docs_screenshots_and_executive_readout_pptx_valid() -> None:
    """Verify deliverables/FDE_Capstone_Executive_Readout.pptx is a valid 12-slide PPTX and V36 docs/images exist."""
    readout_pptx = (
        REPO_ROOT / "deliverables" / "FDE_Capstone_Executive_Readout.pptx"
    )
    assert readout_pptx.exists()
    prs = Presentation(str(readout_pptx))
    assert len(prs.slides) == 12

    required_screenshots = [
        "ui_hero_landing.png",
        "ui_slide_1_title.png",
        "ui_slide_deck_stage.png",
        "ui_template_gallery_modal.png",
        "ui_nano_banana_ai_studio_modal.png",
        "ui_speaker_notes_drawer.png",
        "ui_counselor_workbook_tab.png",
        "ui_fillable_scout_workbook.png",
        "ui_blue_card_matrix.png",
    ]
    for img_name in required_screenshots:
        img_path = REPO_ROOT / "docs" / "images" / img_name
        assert img_path.exists(), f"Missing screenshot {img_name}"
        assert img_path.stat().st_size > 50000

    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "5,625" in readme_text
    assert "29" in readme_text
    assert "\u2014" not in readme_text
