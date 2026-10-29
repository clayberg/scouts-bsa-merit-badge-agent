"""Tests for Track B: 4-Pillar Scout Workbook & CPP PDF/HTML/MD Upgrade + 149-Badge Bespoke Organizers & Misconceptions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import fitz
import pytest

from src.agents.researcher import compute_canonical_pamphlet_hash
from src.schemas import WorkbookOrganizerSpec, WorkbookOrganizerType
from src.tools.counselor_studiokit import (
    _sanitize_pdf_text,
    generate_class_preparation_page_cpp,
    generate_class_preparation_page_cpp_pdf,
    generate_fillable_scout_workbook_pdf,
)
from src.tools.scouting_scraper import (
    MeritBadgeResearchRequest,
    _iter_unrolled_workbook_units,
    fetch_merit_badge_pamphlet_pdf,
    generate_counselor_workbook_markdown,
    generate_fillable_scout_workbook_html,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REQ_DIR = REPO_ROOT / "data" / "merit_badge_requirements"
CACHE_PATH = REPO_ROOT / "data" / "official_requirements_cache.json"

BENCHMARK_BADGES: List[str] = [
    "First Aid",
    "Camping",
    "Cooking",
    "Citizenship in the Nation",
    "Environmental Science",
    "Personal Fitness",
    "Emergency Preparedness",
    "Swimming",
    "Astronomy",
    "Robotics",
    "Auctioneering",
]

FORBIDDEN_OCR_LIGATURES = (
    "safetyand",
    "andlift",
    "bloodbornepathogens",
    "Theemergency",
    "smellingsalts",
    "tohypothermia",
    "ofhypothermia",
    "andfirstaid",
)


def test_workbook_organizer_schema_supports_all_bespoke_types() -> None:
    """Verifies WorkbookOrganizerType and WorkbookOrganizerSpec accept all bespoke organizer enums and fields."""
    expected_enums = {
        "HAZARD_5COL",
        "SYMPTOMS_FIRST_AID_PREVENTION_3COL",
        "CAMPING_LOG_20NIGHT",
        "FITNESS_ASSESSMENT_4STAGE",
        "FITNESS_LOG_12WK",
        "MEAL_PLANNER_AND_COST_TABLE",
        "CITIZENSHIP_CIVIC_ORGANIZER",
        "SCIENTIFIC_EXPERIMENT_SHEET",
        "SENSORY_OBSERVATION_LOG",
        "ENGINEERING_DESIGN_NOTEBOOK",
        "CAREER_EXPLORATION_CARD",
        "SKETCH_AND_OBSERVATION_CANVAS",
        "PHYSICAL_SKILL_VERIFICATION_RUBRIC",
        "CAUSE_PREVENTION_MITIGATION_3COL",
        "COMPARE_CONTRAST_2COL",
        "TIME_SERIES_LOG_TABLE",
        "STEP_BY_STEP_CHECKLIST",
        "RULED_EXPLAIN_BOX",
    }
    actual_enums = {e.value for e in WorkbookOrganizerType}
    assert expected_enums.issubset(actual_enums)

    spec = WorkbookOrganizerSpec(
        organizer_type=WorkbookOrganizerType.CAMPING_LOG_20NIGHT,
        columns=["Night #", "Date", "Location", "Tent/Sky", "Activities"],
        headers=["Night #", "Date", "Location", "Tent/Sky", "Activities"],
        row_labels=[f"Night {i}" for i in range(1, 21)],
        min_rows=20,
        pre_approval_gate=True,
        helper_prompt="Log 20 nights of camping.",
    )
    assert spec.min_rows == 20
    assert spec.pre_approval_gate is True
    assert len(spec.headers) == 5


def test_all_149_badges_enriched_and_canonical_hashes_intact() -> None:
    """Verifies all 149 badge JSON files have bespoke organizers, non-generic misconceptions, clean OCR prose, and intact hashes."""
    cache_data: Dict[str, Any] = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    assert len(cache_data) >= 149

    json_files = [
        jf for jf in sorted(REQ_DIR.glob("*.json"))
        if jf.name != "manifest.json"
    ]
    assert len(json_files) >= 149

    for jf in json_files:
        data = json.loads(jf.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data.get("requirements"):
            continue
        badge_name = data.get("badge_name") or jf.stem
        reqs = data.get("requirements") or []
        assert reqs, f"{badge_name} has no requirements"

        # Canonical hash must match cache
        h1 = compute_canonical_pamphlet_hash(reqs)
        assert len(h1) == 64
        if badge_name in cache_data:
            cached_entry = cache_data[badge_name]
            cached_reqs = cached_entry if isinstance(cached_entry, list) else (cached_entry.get("requirements") or [])
            h2 = compute_canonical_pamphlet_hash(cached_reqs)
            assert h1 == h2, f"Canonical hash mismatch for {badge_name}"

        for r in reqs:
            org = r.get("workbook_organizer") or {}
            assert org.get("organizer_type"), f"Missing organizer_type in {badge_name} req {r.get('req_number')}"
            assert org.get("headers") or org.get("columns"), f"Missing headers in {badge_name} req {r.get('req_number')}"
            assert org.get("row_labels"), f"Missing row_labels in {badge_name} req {r.get('req_number')}"

            mis = r.get("common_misconception_pair") or {}
            myth = str(mis.get("misconception") or mis.get("myth") or "")
            fact = str(mis.get("fact") or mis.get("fact_correction") or "")
            assert myth and fact, f"Missing myth/fact in {badge_name} req {r.get('req_number')}"
            assert "Reading a short definition of" not in myth, (
                f"Generic boilerplate myth found in {badge_name} req {r.get('req_number')}: {myth}"
            )

            # Check OCR ligature sanitization in pamphlet_excerpts and step_by_step_procedure
            prose_blob = " ".join(
                [*(str(x) for x in (r.get("pamphlet_excerpts") or [])), *(str(x) for x in (r.get("step_by_step_procedure") or []))]
            )
            for bad_tok in FORBIDDEN_OCR_LIGATURES:
                assert bad_tok not in prose_blob, f"Unsanitized OCR ligature {bad_tok!r} in {badge_name} req {r.get('req_number')}"

            for sr in r.get("sub_requirements") or []:
                sr_org = sr.get("workbook_organizer") or {}
                assert sr_org.get("organizer_type"), (
                    f"Missing sub-requirement organizer_type in {badge_name} sub-req {sr.get('sub_id')}"
                )
                sr_mis = sr.get("common_misconception_pair") or {}
                sr_myth = str(sr_mis.get("misconception") or sr_mis.get("myth") or "")
                if sr_myth:
                    assert "Reading a short definition of" not in sr_myth
                    assert sr_myth.strip().lower() != myth.strip().lower(), (
                        f"Duplicate parent myth on sub-req {sr.get('sub_id')} in {badge_name}"
                    )


def test_bespoke_organizers_on_benchmark_badges() -> None:
    """Verifies domain-specific graphic organizers are assigned on benchmark badges."""
    camping = json.loads((REQ_DIR / "camping.json").read_text(encoding="utf-8"))
    camping_units = _iter_unrolled_workbook_units(camping["requirements"])
    camping_types = {u["workbook_organizer"]["organizer_type"] for u in camping_units}
    assert "CAMPING_LOG_20NIGHT" in camping_types
    req_9a = next(u for u in camping_units if str(u["req_number"]).lower() == "9a")
    assert len(req_9a["workbook_organizer"]["row_labels"]) >= 20

    pf = json.loads((REQ_DIR / "personal-fitness.json").read_text(encoding="utf-8"))
    pf_units = _iter_unrolled_workbook_units(pf["requirements"])
    pf_types = {u["workbook_organizer"]["organizer_type"] for u in pf_units}
    assert "FITNESS_LOG_12WK" in pf_types or "FITNESS_ASSESSMENT_4STAGE" in pf_types

    fa = json.loads((REQ_DIR / "first-aid.json").read_text(encoding="utf-8"))
    fa_units = _iter_unrolled_workbook_units(fa["requirements"])
    fa_types = {u["workbook_organizer"]["organizer_type"] for u in fa_units}
    assert "SYMPTOMS_FIRST_AID_PREVENTION_3COL" in fa_types or "HAZARD_5COL" in fa_types


@pytest.mark.parametrize("badge_name", BENCHMARK_BADGES)
def test_workbook_md_html_and_pdf_unroll_and_zero_dropped_requirements(badge_name: str) -> None:
    """Verifies MD, HTML, and AcroForm PDF workbooks unroll sub-requirements and render 100% of requirement texts without overflow drops."""
    res = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name=badge_name))
    assert res.get("status") == "SUCCESS"
    reqs = res.get("requirements") or []
    units = _iter_unrolled_workbook_units(reqs)
    assert len(units) >= len(reqs)

    # 1. Markdown workbook check
    md_text = generate_counselor_workbook_markdown(res)
    for u in units:
        r_num = str(u["req_number"])
        assert f"Req {r_num}" in md_text or f"Requirement {r_num}" in md_text

    # 2. Fillable HTML workbook check
    html_res = generate_fillable_scout_workbook_html(badge_name)
    html_text = str(html_res.get("workbook_html") or html_res.get("html_document") or "")
    assert 'type="checkbox"' in html_text
    for u in units:
        r_num = str(u["req_number"])
        assert r_num in html_text
    if badge_name == "Astronomy":
        assert "<svg" in html_text

    # 3. Fillable AcroForm PDF workbook check via PyMuPDF
    pdf_bytes = generate_fillable_scout_workbook_pdf(badge_name)
    assert pdf_bytes.startswith(b"%PDF")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) >= 1

    extracted_pages = [page.get_text("text") for page in doc]
    full_pdf_text = "\n".join(extracted_pages)

    # Every single unrolled unit (including all 7 requirements + sub-requirements of Cooking) must appear in the PDF
    for u in units:
        r_num = str(u["req_number"])
        assert f"Official Requirement {r_num}:" in full_pdf_text, (
            f"{badge_name} Workbook PDF dropped Official Requirement {r_num}"
        )
        # Verify snippet of sanitized verbatim text appears in the PDF
        sanitized_snippet = _sanitize_pdf_text(str(u.get("req_text") or ""))[:32].strip()
        if sanitized_snippet:
            assert sanitized_snippet in full_pdf_text, (
                f"{badge_name} Req {r_num} verbatim text snippet {sanitized_snippet!r} missing from PDF"
            )

    # Verify interactive AcroForm widgets exist
    total_widgets = sum(len(list(page.widgets() or [])) for page in doc)
    fillable_units = [u for u in units if not u.get("is_group_header")]
    assert total_widgets >= len(fillable_units) * 2
    doc.close()


@pytest.mark.parametrize("badge_name", BENCHMARK_BADGES)
def test_cpp_html_md_and_multipage_pdf_never_blank(badge_name: str) -> None:
    """Verifies Class Preparation Page (CPP) renders all 4 sections and never produces blank PDF pages on dense badges like Cooking."""
    cpp_res = generate_class_preparation_page_cpp(badge_name)
    assert cpp_res.get("status") == "SUCCESS"
    assert "1. Starting Requirement Gate Alert" in cpp_res["cpp_markdown"]
    assert "2. Do Before Session 1" in cpp_res["cpp_markdown"]
    assert "3. What to Bring to Every Session" in cpp_res["cpp_markdown"]
    assert "4. What We Will Complete Together in Class" in cpp_res["cpp_markdown"]

    cpp_pdf = generate_class_preparation_page_cpp_pdf(badge_name)
    assert cpp_pdf.startswith(b"%PDF")
    cpp_doc = fitz.open(stream=cpp_pdf, filetype="pdf")
    assert len(cpp_doc) >= 1

    for page_idx, page in enumerate(cpp_doc):
        page_text = page.get_text("text").strip()
        assert len(page_text) >= 80, (
            f"{badge_name} CPP PDF page {page_idx + 1} is blank or nearly empty: {page_text!r}"
        )

    full_cpp_pdf_text = "\n".join(p.get_text("text") for p in cpp_doc)
    assert "1. Starting Requirement Gate Alert" in full_cpp_pdf_text
    assert "2. Do Before Session 1" in full_cpp_pdf_text
    assert "3. What to Bring to Every Session" in full_cpp_pdf_text
    assert "4. What We Will Complete Together in Class" in full_cpp_pdf_text
    cpp_doc.close()


BUCKY_10_COMPARISON_BADGES: List[str] = [
    "Archery",
    "Aviation",
    "Canoeing",
    "Chemistry",
    "Chess",
    "Communication",
    "Cybersecurity",
    "Electricity",
    "Fish and Wildlife Management",
    "Wilderness Survival",
]

FORBIDDEN_RAW_ENUM_STRINGS = (
    "RULED_EXPLAIN_BOX",
    "CITIZENSHIP_CIVIC_ORGANIZER",
    "HAZARD_5COL",
    "SYMPTOMS_FIRST_AID_PREVENTION_3COL",
    "IN_CLASS_DISCUSSION",
    "HANDS_ON_SKILL_STATION",
    "PREREQUISITE_CAMPOUT_HOME",
    "COUNSELOR_PRE_APPROVAL",
    "PARENT_CONSENT_GATE",
    "HARD_PREREQ_BADGE",
    "SKETCH_AND_OBSERVATION_CANVAS",
)


@pytest.mark.parametrize("badge_name", ["Citizenship in the Nation", *BUCKY_10_COMPARISON_BADGES])
def test_zero_raw_enum_strings_and_page1_signoff_grid_and_multicol_acroform(badge_name: str) -> None:
    """Verifies zero raw internal enum codes leak into user-facing MD, HTML, PDF, or CPP, and checks Page-1 Sign-Off Grid + multi-col AcroForm cells."""
    import re
    from src.tools.counselor_studiokit import generate_organizer_syllabus_spec_sheet

    res = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name=badge_name))
    assert res.get("status") == "SUCCESS"

    # 1. Markdown workbook has zero raw enum codes
    md_text = generate_counselor_workbook_markdown(res)
    for raw_enum in FORBIDDEN_RAW_ENUM_STRINGS:
        assert raw_enum not in md_text, f"{badge_name} Markdown workbook leaked raw enum {raw_enum}"

    # 2. Fillable HTML workbook has Page-1 Sign-Off Grid and zero raw enum codes in visible text
    html_res = generate_fillable_scout_workbook_html(badge_name)
    html_doc = str(html_res.get("workbook_html") or html_res.get("html_document") or "")
    assert 'data-testid="wb-page1-signoff-grid"' in html_doc
    assert "Requirement Completion &amp; Counselor Verification Index" in html_doc
    # Strip data-organizer-type="..." attribute before checking visible HTML text
    html_visible = re.sub(r'data-organizer-type="[^"]*"', "", html_doc)
    for raw_enum in FORBIDDEN_RAW_ENUM_STRINGS:
        assert raw_enum not in html_visible, f"{badge_name} HTML workbook leaked raw enum {raw_enum}"

    # 3. CPP and Syllabus Spec Sheet have zero raw enum codes
    cpp_res = generate_class_preparation_page_cpp(badge_name)
    spec_res = generate_organizer_syllabus_spec_sheet(badge_name)
    combined_counselor_docs = (
        str(cpp_res.get("cpp_markdown") or "")
        + "\n"
        + str(cpp_res.get("cpp_html") or "")
        + "\n"
        + str(spec_res.get("spec_sheet_markdown") or "")
    )
    for raw_enum in FORBIDDEN_RAW_ENUM_STRINGS:
        assert raw_enum not in combined_counselor_docs, f"{badge_name} CPP/Syllabus leaked raw enum {raw_enum}"

    # 4. Fillable AcroForm PDF has Page-1 Sign-Off Grid, zero raw enum codes, and multi-column AcroForm widgets
    pdf_bytes = generate_fillable_scout_workbook_pdf(badge_name)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_pdf_text = "\n".join(p.get_text("text") for p in doc)
    assert "Page-1 Requirement Completion & Counselor Verification Index" in full_pdf_text
    for raw_enum in FORBIDDEN_RAW_ENUM_STRINGS:
        assert raw_enum not in full_pdf_text, f"{badge_name} PDF workbook leaked raw enum {raw_enum}"

    widget_names = [
        str(w.field_name or "")
        for page in doc
        for w in (page.widgets() or [])
    ]
    assert any("_col_1" in name for name in widget_names), f"{badge_name} PDF missing _col_1 AcroForm widgets"
    assert any("_col_2" in name for name in widget_names), f"{badge_name} PDF missing _col_2 multi-column AcroForm widgets"
    doc.close()


def test_runtime_workbook_quality_and_bucky_10_badge_parity() -> None:
    """Verifies runtime workbook organizer sanitization, hierarchical unrolling, and bespoke parity across Citizenship in the Nation and the 10 Bucky comparison badges."""
    # 1. Citizenship in the Nation: distinct 3b, 3c, 3d organizers + 7b "U.S. Capitol" merge
    cit = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name="Citizenship in the Nation"))
    cit_units = {str(u["req_number"]): u for u in _iter_unrolled_workbook_units(cit["requirements"])}
    assert "Separation of Powers Principle" in " ".join(cit_units["3b"]["workbook_organizer"]["headers"])
    assert "Branch Exercising Check" in " ".join(cit_units["3c"]["workbook_organizer"]["headers"])
    assert "How Citizens Participate" in " ".join(cit_units["3d"]["workbook_organizer"]["headers"])
    assert any("U.S. Capitol" in rl for rl in cit_units["7b"]["workbook_organizer"]["row_labels"])

    # 2. Canoeing 1b: 7 canoeing first aid conditions in 3-column organizer
    can = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name="Canoeing"))
    can_units = {str(u["req_number"]): u for u in _iter_unrolled_workbook_units(can["requirements"])}
    assert can_units["1b"]["workbook_organizer"]["organizer_type"] == "SYMPTOMS_FIRST_AID_PREVENTION_3COL"
    assert len(can_units["1b"]["workbook_organizer"]["row_labels"]) == 7

    # 3. Communication 4 (Interview Prep Organizer) and 1b (all 4 listening types)
    comm = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name="Communication"))
    comm_units = {str(u["req_number"]): u for u in _iter_unrolled_workbook_units(comm["requirements"])}
    assert "Interview Preparation" in str(comm_units["4"]["workbook_organizer"].get("table_title") or "")
    assert len(comm_units["4"]["workbook_organizer"]["row_labels"]) == 4
    assert any("Appreciate or Enjoy" in rl for rl in comm_units["1b"]["workbook_organizer"]["row_labels"])
    assert any("Understand Someone's Feelings" in rl for rl in comm_units["1b"]["workbook_organizer"]["row_labels"])

    # 4. First Aid 15a, 15b, 15d tailored row labels
    fa = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name="First Aid"))
    fa_units = {str(u["req_number"]): u for u in _iter_unrolled_workbook_units(fa["requirements"])}
    assert len(fa_units["15a"]["workbook_organizer"]["row_labels"]) == 3
    assert len(fa_units["15b"]["workbook_organizer"]["row_labels"]) == 3
    assert len(fa_units["15d"]["workbook_organizer"]["row_labels"]) == 3

    # 5. Wilderness Survival 1a consolidated 13-condition table
    ws = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name="Wilderness Survival"))
    ws_units = {str(u["req_number"]): u for u in _iter_unrolled_workbook_units(ws["requirements"])}
    assert ws_units["1a"]["is_group_header"] is False
    assert ws_units["1a"]["workbook_organizer"]["organizer_type"] == "SYMPTOMS_FIRST_AID_PREVENTION_3COL"
    assert len(ws_units["1a"]["workbook_organizer"]["row_labels"]) == 13
    assert "1a(1)" not in ws_units

    # 6. Archery 2d, 5a, 5b group headers and 5a(6)(b) 80-cm target rows
    arch = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name="Archery"))
    arch_units = {str(u["req_number"]): u for u in _iter_unrolled_workbook_units(arch["requirements"])}
    assert arch_units["2d"]["is_group_header"] is True
    assert arch_units["5a"]["is_group_header"] is True
    assert arch_units["5b"]["is_group_header"] is True
    assert "5a(6)(b)" in arch_units
    assert any("80-cm" in rl or "10 Yards" in rl for rl in arch_units["5a(6)(b)"]["workbook_organizer"]["row_labels"])


def test_slide2_insertion_index_and_independent_opening_closing_flags() -> None:
    """Verifies inject_class_opening_and_closing_slides inserts overview-logistics at index 0 (Slide 2) and supports independent flags and logistics fields."""
    from src.tools.pptx_builder import inject_class_opening_and_closing_slides

    base_slides = [
        {"title": "Requirement 1: Foundations", "archetype": "REQUIREMENTS_TRIAGE_MATRIX", "bullet_points": ["Point A"]},
        {"title": "Requirement 2: Practice", "archetype": "HANDS_ON_STATION", "bullet_points": ["Point B"]},
    ]

    # Both enabled: opening slide must be at index 0 (Slide 2 immediately after Cover), closing slide at the end
    both = inject_class_opening_and_closing_slides(
        badge_name="Citizenship in the Nation",
        slides=base_slides,
        logistics_config={
            "include_opening_slide": True,
            "include_closing_slide": True,
            "class_start_time": "9:00 AM Sharp",
            "room_and_venue": "Scout Hall Room 104",
            "session_dates_summary": "Oct 10 & Oct 17",
        },
    )
    assert len(both) == 4
    assert both[0].get("slide_role") == "overview-logistics"
    assert any("9:00 AM Sharp" in bp for bp in both[0].get("bullet_points", []))
    assert any("Scout Hall Room 104" in bp for bp in both[0].get("bullet_points", []))
    assert any("Oct 10 & Oct 17" in bp for bp in both[0].get("bullet_points", []))
    assert both[-1].get("slide_role") == "homework-checkout"

    # Opening only
    open_only = inject_class_opening_and_closing_slides(
        badge_name="Citizenship in the Nation",
        slides=both,
        logistics_config={
            "include_opening_slide": True,
            "include_closing_slide": False,
        },
    )
    assert len(open_only) == 3
    assert open_only[0].get("slide_role") == "overview-logistics"
    assert all(s.get("slide_role") != "homework-checkout" for s in open_only)

    # Closing only
    close_only = inject_class_opening_and_closing_slides(
        badge_name="Citizenship in the Nation",
        slides=both,
        logistics_config={
            "include_opening_slide": False,
            "include_closing_slide": True,
        },
    )
    assert len(close_only) == 3
    assert all(s.get("slide_role") != "overview-logistics" for s in close_only)
    assert close_only[-1].get("slide_role") == "homework-checkout"

    # Both disabled: cleanly strips both
    neither = inject_class_opening_and_closing_slides(
        badge_name="Citizenship in the Nation",
        slides=both,
        logistics_config={
            "include_opening_slide": False,
            "include_closing_slide": False,
        },
    )
    assert len(neither) == 2
    assert [s.get("title") for s in neither] == ["Requirement 1: Foundations", "Requirement 2: Practice"]

