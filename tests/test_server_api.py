"""API and UI verification tests for Track D `src/server.py` and `ui/*` (v3.0)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient

from src.server import app

REPO_ROOT = Path(__file__).resolve().parent.parent
client = TestClient(app)


def test_class_packet_zip_get_and_post_endpoints() -> None:
    """Verifies GET and POST /api/v1/export/class-packet.zip return a valid 9-file ZIP archive."""
    resp_get = client.get("/api/v1/export/class-packet.zip?badge_name=First%20Aid")
    assert resp_get.status_code == 200
    assert resp_get.headers["content-type"] == "application/zip"
    assert "First_Aid_Complete_Class_Packet.zip" in resp_get.headers.get("content-disposition", "")

    expected_entries = {
        "01_Slide_Deck/First_Aid_Merit_Badge_Deck.pptx",
        "02_Scout_Handouts/First_Aid_Fillable_Scout_Workbook.pdf",
        "02_Scout_Handouts/First_Aid_1Page_Class_Preparation_CPP.pdf",
        "02_Scout_Handouts/First_Aid_Pocket_Field_QR_Checklist.pdf",
        "03_Counselor_Materials/First_Aid_Counselor_Answer_Key_Guide.pdf",
        "03_Counselor_Materials/First_Aid_Session_Lesson_Plan_Agenda.pdf",
        "03_Counselor_Materials/First_Aid_3x5_EDGE_Pocket_Cue_Cards.pdf",
        "03_Counselor_Materials/First_Aid_Quartermaster_Gear_and_Rotator.pdf",
        "04_YPT_Communications/First_Aid_3Stage_Parent_Scoutmaster_Emails.md",
    }

    with zipfile.ZipFile(io.BytesIO(resp_get.content), "r") as zf:
        names = set(zf.namelist())
        assert expected_entries.issubset(names), f"Missing ZIP entries: {expected_entries - names}"
        for name in expected_entries:
            data = zf.read(name)
            assert len(data) > 64, f"ZIP entry {name} is unexpectedly empty"
            if name.endswith(".pdf"):
                assert data.startswith(b"%PDF-"), f"ZIP entry {name} is not a valid PDF"

    resp_post = client.post(
        "/api/v1/export/class-packet.zip",
        json={
            "badge_name": "Camping",
            "template_id": "bsa_scouting_america",
            "counselor_info": {
                "counselor_name": "Alex Rivera",
                "troop_or_event": "Troop 42",
            },
            "storyboard_slides": [
                {
                    "req_number": "1a",
                    "title": "Requirement 1a: Outdoor Hazards & First Aid",
                    "bullet_points": ["Identify common backcountry hazards.", "Pack a patrol first-aid kit."],
                    "presenter_notes": "[SAY] Review outdoor hazards with your patrol.",
                }
            ],
        },
    )
    assert resp_post.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp_post.content), "r") as zf2:
        assert "01_Slide_Deck/Camping_Merit_Badge_Deck.pptx" in zf2.namelist()
        assert "04_YPT_Communications/Camping_3Stage_Parent_Scoutmaster_Emails.md" in zf2.namelist()


def test_delete_custom_slide_endpoint() -> None:
    """Verifies action='delete_custom' deletes custom slides and rejects official requirement slides."""
    slides = [
        {"slide_id": "1a", "req_number": "1a", "title": "Requirement 1a"},
        {
            "slide_id": "custom-1a-abc123",
            "req_number": "1a (Local Example)",
            "title": "Local Troop Example",
            "is_custom_slide": True,
        },
    ]

    # Deleting custom slide succeeds
    resp_ok = client.post(
        "/api/slide/customize",
        json={
            "badge_name": "First Aid",
            "action": "delete_custom",
            "slides": slides,
            "target_slide_index": 1,
        },
    )
    assert resp_ok.status_code == 200
    body_ok = resp_ok.json()
    assert body_ok["status"] == "SUCCESS"
    assert len(body_ok["slides"]) == 1
    assert body_ok["slides"][0]["slide_id"] == "1a"

    # Deleting official requirement slide returns HTTP 400
    resp_err = client.post(
        "/api/slide/customize",
        json={
            "badge_name": "First Aid",
            "action": "delete_custom",
            "slides": slides,
            "target_slide_index": 0,
        },
    )
    assert resp_err.status_code == 400


def test_ui_html_css_js_deliverables_present() -> None:
    """Verifies all Track D HTML, CSS, and JS deliverables are wired."""
    html_text = (REPO_ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    css_text = (REPO_ROOT / "ui" / "styles.css").read_text(encoding="utf-8")
    js_text = (REPO_ROOT / "ui" / "app.js").read_text(encoding="utf-8")

    # Deliverable 1 & 2: 6 new templates & 8 new backdrops in HTML & JS
    for tpl_id in (
        "stem_nova_blueprint",
        "eagle_court_of_honor",
        "sea_scouts_maritime",
        "oa_ceremonial_lodge",
        "venturing_alpine_emerald",
        "wood_badge_gilwell",
    ):
        assert tpl_id in html_text
    for bd_id in (
        "citizenship_capitol_civic",
        "personal_management_ledger",
        "fitness_cycling_trail",
        "communications_studio",
        "trades_welding_workshop",
        "wildlife_forestry_conservation",
        "astronomy_deep_space_observatory",
        "emergency_medical_triage",
    ):
        assert bd_id in html_text
        assert bd_id in js_text
    assert 'id="style-cover-backdrop"' in html_text

    # Deliverable 4: 1-Click Class Packet (.ZIP)
    assert 'data-action="download-class-packet-zip"' in html_text
    assert "downloadCompleteClassPacketZip" in js_text

    # Deliverable 5: On-Stage Inline contenteditable Click-to-Edit
    assert 'id="btn-stage-inline-edit"' in html_text
    assert ".m3-stage-inline-editable" in css_text
    assert "commitStageInlineEdits" in js_text

    # Deliverable 6: 20-State Undo/Redo, Delete Custom Slide, Sub-Req Jump Chips & Filmstrip Search
    assert 'id="btn-stage-undo"' in html_text
    assert 'id="btn-stage-redo"' in html_text
    assert "pushSlideUndoState" in js_text
    assert "performSlideUndo" in js_text
    assert "performSlideRedo" in js_text
    assert "delete_custom" in js_text

    # Deliverable 7: RFC 4180 CSV parser & non-destructive merge
    assert "parseRfc4180CsvRows" in js_text

    # Deliverable 8: Left Sidebar Advanced Deck Settings accordion & Schedule Builder shortcuts
    assert 'id="advanced-deck-settings-accordion"' in html_text
    assert 'data-action="open-schedule-builder"' in html_text
    assert 'id="logistics-drawer-schedule-summary-strip"' in html_text
    assert 'id="btn-logistics-drawer-open-schedule-builder"' in html_text

    # Deliverable 10: Global shortcuts W, G, M and dynamic state parsing
    assert "open-patch-gallery" in html_text
    assert "149 Merit Badges" in html_text or "149-Badge" in html_text
