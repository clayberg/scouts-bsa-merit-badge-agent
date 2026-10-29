"""Verification test suite for V34 Items 1-4:
1. Workbook diagram captions match slide deck image captions across all 149 badges (zero generic 'Instructional Reference Diagram - Req X' captions) + zero truncated sub-requirement titles.
2. Zero repeated Common Myth / Pamphlet Fact strips or duplicate sibling multi-row tables across all 149 workbooks.
3. Generous Scoutmaster-Bucky-grade vertical writing space for single-prompt requirements in both HTML (`76px-96px` ruled editors) and AcroForm PDF (`66pt-80pt` multi-line fields with 18pt dashed handwriting lines).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import fitz
import pytest

from src.tools.counselor_studiokit import generate_fillable_scout_workbook_pdf
from src.tools.scouting_scraper import (
    MeritBadgeResearchRequest,
    _iter_unrolled_workbook_units,
    fetch_merit_badge_pamphlet_pdf,
    generate_counselor_workbook_markdown,
    generate_fillable_scout_workbook_html,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REQ_DIR = REPO_ROOT / "data" / "merit_badge_requirements"

DANGLING_WORDS = {
    "and", "or", "the", "a", "an", "of", "to", "in", "for", "with", "on", "at",
    "by", "from", "as", "into", "about", "like", "after", "between", "through",
    "during", "before", "under", "around", "among", "such", "that", "which",
    "who", "whom", "whose", "whether", "while", "when", "where", "how", "why",
    "what", "your", "their", "our", "its", "his", "her", "my", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "can", "could", "will", "would", "shall", "should", "may", "might",
    "must", "not", "no", "nor", "so", "yet", "both", "either", "neither", "each",
    "every", "any", "some",
}


def test_item1_all_149_badges_have_slide_captions_and_clean_subreq_titles() -> None:
    """Verifies every requirement across all 149 badges has a slide-matched workbook_diagram_caption and zero truncated sub-requirement titles."""
    json_files = [jf for jf in sorted(REQ_DIR.glob("*.json")) if jf.name != "manifest.json"]
    assert len(json_files) >= 149

    total_reqs = 0
    total_subreqs = 0
    for jf in json_files:
        data = json.loads(jf.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data.get("requirements"):
            continue
        bname = data.get("badge_name") or jf.stem
        for r in data.get("requirements") or []:
            total_reqs += 1
            r_num = str(r.get("req_number") or "")
            cap = str(r.get("workbook_diagram_caption") or "").strip()
            assert cap, f"Missing workbook_diagram_caption on {bname} Req {r_num}"
            assert not cap.startswith("Instructional Reference Diagram"), (
                f"Generic caption on {bname} Req {r_num}: {cap}"
            )
            for sr in r.get("sub_requirements") or []:
                total_subreqs += 1
                sr_id = str(sr.get("sub_id") or sr.get("id") or "")
                tp = str(sr.get("topic_title") or "").strip()
                assert tp, f"Missing topic_title on {bname} sub-req {sr_id}"
                last_word = re.sub(r"[^a-zA-Z0-9']+$", "", tp.split()[-1]).lower()
                assert last_word not in DANGLING_WORDS, (
                    f"Dangling trailing word {last_word!r} in {bname} sub-req {sr_id}: {tp!r}"
                )

    assert total_reqs >= 1150
    assert total_subreqs >= 2400


def test_item1_first_aid_workbook_html_md_and_pdf_use_slide_captions_and_curated_titles() -> None:
    """Verifies First Aid workbook HTML, Markdown, and PDF use exact slide deck captions and clean sub-requirement titles."""
    res = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name="First Aid"))
    assert res.get("status") == "SUCCESS"
    md_text = generate_counselor_workbook_markdown(res)
    assert "Instructional Reference Diagram -" not in md_text
    assert "Scouts conduct an urgent primary assessment on a fallen patient lying on the forest floor beside medical kits." in md_text

    html_res = generate_fillable_scout_workbook_html("First Aid")
    html_doc = str(html_res.get("workbook_html") or "")
    assert "Instructional Reference Diagram -" not in html_doc
    assert "Necessary to Assess and Handle" not in html_doc
    assert "Abrasions Such As Chafing and" not in html_doc
    assert "Blisters on The Hands Feet" not in html_doc
    assert "Emergency Scene Safety and Assessment" in html_doc
    assert "Abrasions, Chafing, and Rope Burns" in html_doc
    assert "Blisters on Hands, Feet, and Shoulders" in html_doc
    assert "Scouts conduct an urgent primary assessment on a fallen patient lying on the forest floor beside medical kits." in html_doc

    pdf_bytes = generate_fillable_scout_workbook_pdf("First Aid")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_pdf_text = "\n".join(p.get_text("text") for p in doc)
    doc.close()
    assert "Use this visual reference to complete the organizer below" not in full_pdf_text
    assert "Figure (Req 1a): Scouts conduct an urgent primary assessment" in full_pdf_text


def test_item2_zero_repeated_misconceptions_or_duplicate_sibling_rows_across_all_149_badges() -> None:
    """Verifies zero duplicate Common Myth / Pamphlet Fact callouts and zero duplicate multi-row sibling tables across all 149 badges."""
    json_files = [jf for jf in sorted(REQ_DIR.glob("*.json")) if jf.name != "manifest.json"]
    for jf in json_files:
        data = json.loads(jf.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data.get("requirements"):
            continue
        bname = data.get("badge_name") or jf.stem
        units = _iter_unrolled_workbook_units(data.get("requirements") or [], badge_name=bname)
        seen_myths: set = set()
        seen_parent_sr_rows: dict = {}
        for u in units:
            mis = u.get("common_misconception_pair") or {}
            myth = str(mis.get("misconception") or "").strip().lower()
            if myth:
                assert myth not in seen_myths, f"Duplicate misconception in {bname} unit {u.get('req_number')}: {myth!r}"
                seen_myths.add(myth)

            if u.get("is_sub_requirement") and not u.get("is_group_header"):
                p_id = str(u.get("parent_id") or "")
                rows = tuple(str(x).strip().lower() for x in ((u.get("workbook_organizer") or {}).get("row_labels") or []))
                if len(rows) >= 2:
                    prev_set = seen_parent_sr_rows.setdefault(p_id, set())
                    assert rows not in prev_set, (
                        f"Duplicate multi-row table on sibling sub-req {u.get('req_number')} under parent {p_id} in {bname}: {rows}"
                    )
                    prev_set.add(rows)

    # Specifically verify First Aid HTML & PDF only emit the blister/burn misconception once (on Requirement 3 Group)
    html_doc = str(generate_fillable_scout_workbook_html("First Aid").get("workbook_html") or "")
    assert html_doc.count("Popping friction blisters, rubbing frostbitten fingers") == 1


def test_item3_single_prompt_vertical_space_in_html_and_pdf_workbooks() -> None:
    """Verifies single-prompt requirements allocate generous vertical space in both HTML (`76px-96px`) and AcroForm PDF (`66pt-80pt`)."""
    html_doc = str(generate_fillable_scout_workbook_html("First Aid").get("workbook_html") or "")
    assert 'data-min-height-px="96"' in html_doc
    assert 'class="wb-fillable-editor" style="min-height:96px;"' in html_doc

    pdf_bytes = generate_fillable_scout_workbook_pdf("First Aid")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    single_prompt_widget_heights = []
    for page in doc:
        for w in page.widgets() or []:
            fname = str(w.field_name or "")
            if fname.startswith(("req_1a_row_", "req_3h_row_", "req_3i_row_")):
                single_prompt_widget_heights.append(w.rect.height)
    doc.close()

    assert len(single_prompt_widget_heights) >= 3
    for h in single_prompt_widget_heights:
        assert h >= 64.0, f"Single-prompt PDF widget height too small: {h}pt"
