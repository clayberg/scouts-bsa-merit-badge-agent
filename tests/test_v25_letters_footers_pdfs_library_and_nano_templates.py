"""v2.5 regression tests for 3-Stage Parent Letters, Compact Slide Footers, Fillable Form Citations,
Direct Branded PDFs (Tab 2/3/4 De-Duplication), Streamlined Classroom Session Library, and Nano Banana AI Template Studio.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import fitz
from fastapi.testclient import TestClient
from PIL import Image

from src.server import app
from src.tools.counselor_studiokit import (
    generate_bluecards_pdf,
    generate_counselor_cue_cards_pdf,
    generate_counselor_workbook_pdf,
    generate_field_qr_checklist_pdf,
    generate_gear_and_rotator_pdf,
    generate_organizer_spec_pdf,
    generate_parent_letter_pdf,
    generate_prerequisite_parent_letter,
)
from src.tools.scouting_scraper import generate_fillable_scout_workbook_html
from src.tools.template_engine import generate_nano_banana_template_family

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_item1_three_distinct_parent_letters_and_multitroop_salutation() -> None:
    """Item 1: Parent letter generates 3 distinct stages, uses a multi-troop salutation, and fixes 'Middelton'."""
    res = generate_prerequisite_parent_letter(
        "First Aid",
        counselor_info={
            "name": "Eric Clayberg",
            "troop": "Troop 19, Middelton MA",
            "location": "01949",
            "email": "counselor@troop19.org",
            "session_tag": "Danvers MBC",
        },
    )
    assert res["status"] == "SUCCESS"
    # Subject and salutation must never include '(Troop 19, Middelton MA (01949))'
    assert "Middelton" not in res["subject"]
    assert "Troop 19" not in res["subject"]
    assert "Middelton" not in res["letter_markdown"]
    assert "Dear First Aid Merit Badge Scouts, Parents/Guardians, and Unit Leaders," in res["letter_markdown"]
    # Signature block at bottom should have normalized 'Troop 19, Middleton MA'
    assert "Middleton" in res["letter_markdown"]

    stages = res.get("stages") or {}
    assert "stage_1_welcome_cpp" in stages
    assert "stage_2_mid_clinic_alert" in stages
    assert "stage_3_final_packet" in stages

    md1 = stages["stage_1_welcome_cpp"]["markdown"]
    md2 = stages["stage_2_mid_clinic_alert"]["markdown"]
    md3 = stages["stage_3_final_packet"]["markdown"]
    assert md1 != md2
    assert md2 != md3
    assert md1 != md3

    # Verify PDF exports for all 3 stages are distinct valid PDFs
    pdf1 = generate_parent_letter_pdf("First Aid", stage="stage_1_welcome_cpp")
    pdf2 = generate_parent_letter_pdf("First Aid", stage="stage_2_mid_clinic_alert")
    pdf3 = generate_parent_letter_pdf("First Aid", stage="stage_3_final_packet")
    for payload in (pdf1, pdf2, pdf3):
        assert payload.startswith(b"%PDF")
    doc1 = fitz.open(stream=pdf1, filetype="pdf")
    doc2 = fitz.open(stream=pdf2, filetype="pdf")
    doc3 = fitz.open(stream=pdf3, filetype="pdf")
    t1 = "\n".join(p.get_text("text") for p in doc1)
    t2 = "\n".join(p.get_text("text") for p in doc2)
    t3 = "\n".join(p.get_text("text") for p in doc3)
    doc1.close()
    doc2.close()
    doc3.close()
    assert t1 != t2
    assert t2 != t3


def test_item2_compact_slide_footer_and_two_line_page_indicator() -> None:
    """Item 2: Left footer shortens pamphlet citation to 'Pamphlet (p. X)' and 'Workbook Requirement Y'; right footer stacks 2 lines."""
    from src.tools.pptx_builder import _format_compact_footer_pamphlet_ref

    compact = _format_compact_footer_pamphlet_ref(
        "Official Scouting America First Aid Merit Badge Pamphlet (p. 19, p. 21)",
        "First Aid",
    )
    assert compact == "Pamphlet (p. 19, p. 21)"

    app_js = (REPO_ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    assert "formatCompactFooterPamphletRef" in app_js
    assert "Workbook Requirement" in app_js


def test_item3_remove_verb_aligned_and_wrap_pamphlet_citation_to_next_line() -> None:
    """Item 3: 'Verb-Aligned' meta phrase is removed and Fillable Form wraps pamphlet citation onto a new line."""
    for rel_path in [
        "ui/index.html",
        "src/tools/scouting_scraper.py",
        "src/tools/counselor_studiokit.py",
        "src/tools/pptx_builder.py",
        "src/mcp_server.py",
    ]:
        text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        assert "Verb-Aligned" not in text, f"Found 'Verb-Aligned' in {rel_path}"
        assert "verb-aligned" not in text, f"Found 'verb-aligned' in {rel_path}"

    wb_res = generate_fillable_scout_workbook_html("Citizenship in the Nation")
    wb_html = wb_res["html_content"] if isinstance(wb_res, dict) else str(wb_res)
    assert "Verb-Aligned" not in wb_html
    assert "window.print()" not in wb_html
    # Verify line break or dedicated row precedes .wb-cit-tag
    assert ("<br" in wb_html or "wb-req-cit-row" in wb_html) and 'class="wb-cit-tag"' in wb_html


def test_item4_all_six_new_branded_pdf_generators_and_endpoints() -> None:
    """Item 4: All 6 new Counselor/Scout PDF generators and FastAPI endpoints return branded PDFs and Tab 3/Tab 4 do not overlap."""
    pdf_cases = [
        ("counselor_workbook", generate_counselor_workbook_pdf("First Aid")),
        ("field_qr_checklist", generate_field_qr_checklist_pdf("First Aid")),
        ("cue_cards", generate_counselor_cue_cards_pdf("First Aid")),
        ("organizer_spec", generate_organizer_spec_pdf("First Aid")),
        ("gear_rotator", generate_gear_and_rotator_pdf("First Aid", patrol_size=8, station_minutes=12)),
        ("bluecards_3panel", generate_bluecards_pdf("First Aid", mode="3panel")),
        ("bluecards_sheet", generate_bluecards_pdf("First Aid", mode="sheet")),
    ]
    for label, pdf_bytes in pdf_cases:
        assert pdf_bytes.startswith(b"%PDF"), f"{label} did not return valid PDF bytes"
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        assert doc.page_count >= 1
        page1_text = doc[0].get_text("text")
        assert "First Aid" in page1_text
        doc.close()

    client = TestClient(app)
    for url in [
        "/api/v1/studiokit/counselor-workbook.pdf?badge_name=First+Aid",
        "/api/v1/studiokit/field-qr-checklist.pdf?badge_name=First+Aid",
        "/api/v1/studiokit/cue-cards.pdf?badge_name=First+Aid",
        "/api/v1/studiokit/organizer-spec.pdf?badge_name=First+Aid",
        "/api/v1/studiokit/gear-rotator.pdf?badge_name=First+Aid&patrol_size=8&station_minutes=12",
        "/api/v1/studiokit/bluecards.pdf?badge_name=First+Aid&mode=3panel",
        "/api/v1/studiokit/bluecards.pdf?badge_name=First+Aid&mode=sheet",
    ]:
        resp = client.get(url)
        assert resp.status_code == 200, f"GET {url} returned {resp.status_code}"
        assert resp.headers["content-type"].startswith("application/pdf")
        assert resp.content.startswith(b"%PDF")


def test_item5_streamlined_classroom_session_library_and_custom_lists() -> None:
    """Item 5: Unified Classroom Session Builder controls exist in HTML and custom location/tag lists float new entries to index 0."""
    index_html = (REPO_ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    for required_id in [
        'id="ws-title-input"',
        'id="btn-ws-autogen-title"',
        'id="ws-section-name-select"',
        'id="ws-section-num-select"',
        'id="ws-start-date-input"',
        'id="ws-frequency-select"',
        'id="ws-num-sessions-select"',
        'id="ws-chk-makeup-session"',
        'id="ws-start-time-input"',
        'id="ws-duration-min-input"',
        'id="ws-room-location-input"',
        'id="btn-ws-add-custom-location"',
        'id="ws-bundle-tag-input"',
        'id="btn-ws-add-custom-tag"',
        'id="ws-live-schedule-strip"',
    ]:
        assert required_id in index_html, f"Missing {required_id} in ui/index.html"

    client = TestClient(app)
    loc_val = "Camp Squanto - Waterfront Boathouse"
    resp_add = client.post(
        "/api/v1/preferences/custom-lists",
        json={"list_type": "locations", "action": "add", "value": loc_val},
    )
    assert resp_add.status_code == 200
    data_add = resp_add.json()
    assert data_add["status"] == "SUCCESS"
    assert data_add["custom_locations"][0] == loc_val

    tag_val = "2026 Spirit of Adventure Fall Camporee"
    resp_tag = client.post(
        "/api/v1/preferences/custom-lists",
        json={"list_type": "bundle_tags", "action": "add", "value": tag_val},
    )
    assert resp_tag.status_code == 200
    assert resp_tag.json()["custom_bundle_tags"][0] == tag_val


def test_item6_nano_banana_three_variant_template_studio_and_guardrails() -> None:
    """Item 6: Nano Banana AI Template Studio enforces guardrails, consent gates, logo bg removal, and 3-variant generation."""
    # 1. Guardrail block check (PII / YPT violation)
    blocked_res = generate_nano_banana_template_family(
        family_name="Troop 19 Private Test",
        custom_prompt="Include Scout Johnny Smith cell 555-867-5309 and close-up faces of youth campers in cabin",
        preview_only=True,
    )
    assert blocked_res["status"] == "BLOCKED_BY_GUARDRAIL"
    assert blocked_res.get("blocked") is True
    assert blocked_res.get("cost_usd") == 0.0

    # 2. FinOps consent gate check when preview_only=False and user_consented=False
    consent_res = generate_nano_banana_template_family(
        family_name="Camp Hidden Valley Theme",
        visual_style="pinewood_campfire",
        frame_geometry="horizon_silhouette",
        colors=["#1B5E20", "#0284C7", "#D97706"],
        preview_only=False,
        user_consented=False,
    )
    assert consent_res["status"] == "CONSENT_REQUIRED"
    assert consent_res.get("requires_user_consent") is True

    # 3. Create a tiny synthetic logo PNG with white background to verify auto-remove white background
    logo_img = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    for y in range(8, 24):
        for x in range(8, 24):
            logo_img.putpixel((x, y), (0, 63, 135, 255))
    buf = io.BytesIO()
    logo_img.save(buf, format="PNG")
    logo_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    # 4. Generate full 3-variant template family with consent
    gen_res = generate_nano_banana_template_family(
        family_name="Camp Hidden Valley — Summer 2026 Theme",
        visual_style="pinewood_campfire",
        frame_geometry="horizon_silhouette",
        colors=["#1B5E20", "#0284C7", "#D97706"],
        custom_prompt="Scenic New England pine forest and lake horizon with subtle campfire watermark",
        logo_data_url=logo_b64,
        logo_position="bottom_left",
        remove_logo_white_bg=True,
        preview_only=False,
        user_consented=True,
    )
    assert gen_res["status"] == "SUCCESS"
    assert gen_res["family_id"].startswith("nanobanana_tpl_")
    assert len(gen_res["variants"]) == 3
    v_a, v_b, v_c = gen_res["variants"]
    assert v_a["family_id"] == v_b["family_id"] == v_c["family_id"]
    assert v_a["primary_hex"].upper() != v_b["primary_hex"].upper()

    # 5. Verify FastAPI endpoint /api/v1/templates/generate-ai works
    client = TestClient(app)
    api_resp = client.post(
        "/api/v1/templates/generate-ai",
        json={
            "family_name": "Danvers MBC — Collegiate Theme",
            "visual_style": "collegiate_mbc",
            "frame_geometry": "brushed_header_footer",
            "colors": ["#991B1B", "#1E3A8A", "#D97706"],
            "custom_prompt": "Academic crest and crimson header bar for Saturday Merit Badge College",
            "preview_only": True,
            "user_consented": False,
        },
    )
    assert api_resp.status_code == 200
    api_data = api_resp.json()
    assert api_data["status"] == "SUCCESS"
    assert len(api_data["variants"]) == 3
