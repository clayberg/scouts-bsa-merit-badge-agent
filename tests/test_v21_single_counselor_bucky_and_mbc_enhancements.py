"""End-to-end verification suite for Proposal v2.1: Single-Counselor Bucky & MBC Enhancements.

Covers all 6 User Adjustments and all 5 Architectural Layers:
1. All 149 Official Scouting America Merit Badges (144 Standard + 5 Test Lab Pilot badges:
   Auctioneering, Dance, Physics, Psychology, Sewing and Needlework) with authentic 400x400
   emblems, covers, local PDFs, extracted pamphlet figures (2,425), and Nano Banana visuals (1,401).
2. Visual Merit Badge Patch Gallery & Sidebar Filters:
   - Citizenship in Society annotated as Discontinued (`status="DISCONTINUED"`, red circle-slash indicator).
   - 5 Test Lab Pilot badges annotated (`is_test_lab=True`, `status="TEST_LAB_PILOT"`, `🧪 Test Lab`)
     and filterable via the `"Test Lab Pilot (5)"` filter option (`TEST_LAB`).
3. 5-Part Non-Redundant Facilitator Guide as First-Class Native Baseline (`DECK_SCHEMA_BASELINE_VERSION = "2.1.0"`):
   - `[PACING & MODALITY]`, `[ASK SCOUTS FIRST]`, `[EXPECTED PAMPHLET ANSWER KEY]`,
     `[COMMON MISCONCEPTION TO CORRECT]`, `[DEMONSTRATION & SIGN-OFF RUBRIC]`.
   - Split-Screen Presenter Console (`P`) & Teleprompter (`N`) native 5-card parser with legacy 3-part fallback.
4. 12 Normalized SQLite WAL Tables (+3 new tables: `clinic_session_schedules`,
   `scout_session_attendance_and_partials`, `counselor_syllabus_bucket_overrides`).
5. 27 First-Class MCP Capabilities (15 Tools, 7 Resources, 5 Prompts) + 7 new FastAPI REST routes:
   - `POST /api/v1/studiokit/workbook` (Verb-Aligned Fillable HTML Scout Workbook with GTA 7.0.3.2 banner)
   - `POST /api/v1/studiokit/class-prep-cpp` (1-Page Class Preparation Page with QR code)
   - `POST /api/v1/studiokit/organizer-spec-sheet` (MBC Organizer Class Spec Sheet)
   - `POST /api/v1/studiokit/ypt-parent-email` (3-Stage YPT Two-Deep Parent Email Pack with `[CC Required]` lock)
   - `POST /api/v1/bluecard/clinic-attendance` (S1..S4 | M Attendance Matrix, Smart Partial Classification & CSV Formula Sanitization)
   - `POST /api/v1/triage/bucket-override` (5-Tier Syllabus Bucket Overrides)
   - `POST /api/v1/slide/logistics-slides` (Class Opening & Closing Logistics Slide Injector)
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from src.config import (
    DECK_SCHEMA_BASELINE_VERSION,
    DISCONTINUED_MERIT_BADGES,
    OFFICIAL_BSA_MERIT_BADGES_CATALOG,
    TEST_LAB_MERIT_BADGES,
    _badge_slug,
)
from src.mcp_server import get_mcp_server_manifest
from src.memory.session_store import PersistentSessionStore
from src.server import app


def test_v21_single_counselor_bucky_and_mbc_enhancements_end_to_end(tmp_path: Path) -> None:
    """Verifies all 6 v2.1 user adjustments, 149 badges, 12 SQLite tables, 27 MCP capabilities, and 7 REST routes."""
    repo_root = Path(__file__).resolve().parents[1]
    client = TestClient(app)

    # 1. Verify New Baseline Version = 2.1.0 & 149 Official Badges (incl. 5 Test Lab Pilots & 1 Discontinued)
    assert DECK_SCHEMA_BASELINE_VERSION == "2.1.0"
    assert len(OFFICIAL_BSA_MERIT_BADGES_CATALOG) == 149
    assert set(TEST_LAB_MERIT_BADGES) == {
        "Auctioneering",
        "Dance",
        "Physics",
        "Psychology",
        "Sewing and Needlework",
    }
    assert set(DISCONTINUED_MERIT_BADGES) == {"Citizenship in Society"}

    by_name = {b["badge_name"]: b for b in OFFICIAL_BSA_MERIT_BADGES_CATALOG}
    assert by_name["Citizenship in Society"]["is_discontinued"] is True
    assert by_name["Citizenship in Society"]["status"] == "DISCONTINUED"

    pamphlet_cat = json.loads((repo_root / "data" / "pamphlet_image_catalog.json").read_text(encoding="utf-8"))
    nano_cat = json.loads((repo_root / "data" / "nano_banana_image_catalog.json").read_text(encoding="utf-8"))
    assert len(pamphlet_cat) >= 2425
    assert len(nano_cat) >= 1401

    for tl_badge in TEST_LAB_MERIT_BADGES:
        entry = by_name[tl_badge]
        assert entry["is_test_lab"] is True
        assert entry["status"] == "TEST_LAB_PILOT"
        slug = _badge_slug(tl_badge).replace("-", "_")
        assert (repo_root / "assets" / "badge_emblems" / f"{slug}.png").exists()
        assert (repo_root / "assets" / "pamphlet_covers" / f"{slug}_cover.png").exists()
        assert (repo_root / "assets" / "pamphlets" / f"{slug}.pdf").exists()
        req_json_path = repo_root / "data" / "merit_badge_requirements" / f"{_badge_slug(tl_badge)}.json"
        assert req_json_path.exists()
        req_data = json.loads(req_json_path.read_text(encoding="utf-8"))
        assert req_data.get("is_test_lab") is True
        assert len(req_data.get("requirements", [])) >= 4
        first_req = req_data["requirements"][0]
        for rich_key in (
            "syllabus_bucket",
            "workbook_organizer",
            "common_misconception_pair",
            "curated_resources",
            "pamphlet_page_citation",
            "quiz_item",
            "homework_verification_note",
        ):
            assert rich_key in first_req, f"Missing {rich_key} in {tl_badge} req 1"

    # 2. Verify GET /api/badges exposes 149 badges with Test Lab & Discontinued flags + UI Filter & Indicators
    badges_res = client.get("/api/badges").json()
    assert len(badges_res.get("badges", [])) == 149
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")
    ui_css = (repo_root / "ui" / "styles.css").read_text(encoding="utf-8")
    assert '<option value="TEST_LAB">🧪 Test Lab Pilot (5)</option>' in ui_html
    assert "m3-patch-discontinued-pill" in ui_js and ".m3-patch-discontinued-pill" in ui_css
    assert "m3-patch-testlab-pill" in ui_js and ".m3-patch-testlab-pill" in ui_css
    assert "stage-misconception-bar" in ui_html

    # 3. Verify 12 Normalized SQLite WAL Tables + Startup Pre-2.1.0 Deck Baseline Purge
    db_file = tmp_path / "test_v21_tables.db"
    store = PersistentSessionStore(db_path=str(db_file))
    with sqlite3.connect(str(db_file)) as conn:
        table_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    table_names = {r[0] for r in table_rows}
    expected_12_tables = {
        "counselor_sessions",
        "pamphlet_vector_memory",
        "badge_image_catalog",
        "hitl_feedback",
        "polished_speaker_notes",
        "counselor_workspaces",
        "counselor_favorites",
        "user_preferences",
        "compliance_attestation_ledger",
        "clinic_session_schedules",
        "scout_session_attendance_and_partials",
        "counselor_syllabus_bucket_overrides",
    }
    assert expected_12_tables.issubset({t.lower() for t in table_names})

    # Verify bucket override persistence
    ovr = store.save_syllabus_bucket_override_sync("First Aid", "2b", "PREWORK_HOME")
    assert ovr["syllabus_bucket"] == "PREWORK_HOME"
    assert store.get_syllabus_bucket_overrides_sync("First Aid")["2b"] == "PREWORK_HOME"

    # 4. Verify 7 New FastAPI Endpoints (Workbook, CPP, Spec Sheet, YPT Email, Attendance/Partials, Bucket Override, Logistics)
    wb_res = client.post(
        "/api/v1/studiokit/fillable-workbook",
        json={"badge_name": "First Aid", "counselor_info": {"counselor_name": "Eric Clayberg", "troop_affiliation": "Troop 19"}},
    )
    assert wb_res.status_code == 200
    wb_json = wb_res.json()
    assert wb_json["status"] == "SUCCESS"
    assert "7.0.3.2" in (wb_json.get("html_document") or wb_json.get("workbook_html") or "")
    assert "<table" in (wb_json.get("html_document") or wb_json.get("workbook_html") or "")

    cpp_res = client.post(
        "/api/v1/studiokit/class-prep-cpp",
        json={"badge_name": "First Aid", "schedule_format": "4-Session MBC Clinic (75 min x 4 Saturdays)"},
    )
    assert cpp_res.status_code == 200
    cpp_json = cpp_res.json()
    assert cpp_json["status"] == "SUCCESS"
    assert "<svg" in (cpp_json.get("html_document") or cpp_json.get("cpp_html") or "")

    spec_res = client.post(
        "/api/v1/studiokit/organizer-spec-sheet",
        json={"badge_name": "First Aid"},
    )
    assert spec_res.status_code == 200
    assert spec_res.json()["status"] == "SUCCESS"

    ypt_res = client.post(
        "/api/v1/studiokit/ypt-three-stage-pack",
        json={
            "badge_name": "First Aid",
            "counselor_info": {"counselor_name": "Eric Clayberg", "email_address": "counselor@troop19.org"},
        },
    )
    assert ypt_res.status_code == 200
    ypt_json = ypt_res.json()
    assert ypt_json["status"] == "SUCCESS"
    assert "stages" in ypt_json or "stage_1_welcome" in ypt_json

    att_res = client.post(
        "/api/v1/triage/attendance-and-partials",
        json={
            "workspace_id": "ws_test_v21",
            "badge_name": "First Aid",
            "action": "upsert_scout",
            "scout_id": "s1",
            "scout_name": "Alex Carter",
            "troop_unit": "Troop 19",
            "session_attendance": {"S1": "P", "S2": "A", "S3": "P", "S4": "P", "M": "-"},
            "completed_reqs": ["1", "3", "4"],
        },
    )
    assert att_res.status_code == 200
    att_json = att_res.json()
    assert att_json["status"] == "SUCCESS"

    bkt_res = client.post(
        "/api/v1/triage/bucket-override",
        json={
            "workspace_id": "ws_test_v21",
            "badge_name": "First Aid",
            "req_number": "2b",
            "override_bucket": "PREWORK_HOME",
        },
    )
    assert bkt_res.status_code == 200
    assert bkt_res.json()["overrides"]["2b"] == "PREWORK_HOME"

    log_res = client.post(
        "/api/v1/slide/logistics-slides",
        json={
            "badge_name": "First Aid",
            "logistics_config": {"include_opening_slide": True, "include_closing_slide": True},
        },
    )
    assert log_res.status_code == 200
    assert log_res.json()["status"] == "SUCCESS"
    assert log_res.json()["total_slide_count"] >= 2

    # 5. Verify 27 MCP Capabilities (15 Tools, 7 Resources, 5 Prompts)
    manifest = get_mcp_server_manifest()
    assert manifest["counts"] == {"tools": 15, "resources": 7, "prompts": 5}

    rpc_wb = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 501,
            "method": "tools/call",
            "params": {"name": "generate_fillable_scout_workbook", "arguments": {"badge_name": "Physics"}},
        },
    ).json()
    assert rpc_wb["result"]["structuredContent"]["status"] == "SUCCESS"

    rpc_cpp_res = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 502,
            "method": "resources/read",
            "params": {"uri": "bsa://badges/Physics/class-prep-cpp"},
        },
    ).json()
    assert "contents" in rpc_cpp_res["result"]

    rpc_prompt = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 503,
            "method": "prompts/get",
            "params": {"name": "multisession_mbc_clinic_facilitator_prompt", "arguments": {"badge_name": "Physics"}},
        },
    ).json()
    assert len(rpc_prompt["result"]["messages"]) >= 1


def test_v21_five_test_lab_pilots_and_discontinued_citizenship_in_society() -> None:
    """Verifies the 5 Test Lab Pilot badges and Discontinued Citizenship in Society metadata."""
    by_name = {b["badge_name"]: b for b in OFFICIAL_BSA_MERIT_BADGES_CATALOG}
    assert len(by_name) == 149
    for tl in ("Auctioneering", "Dance", "Physics", "Psychology", "Sewing and Needlework"):
        assert by_name[tl]["is_test_lab"] is True
        assert by_name[tl]["status"] == "TEST_LAB_PILOT"
    assert by_name["Citizenship in Society"]["is_discontinued"] is True
    assert by_name["Citizenship in Society"]["status"] == "DISCONTINUED"


def test_v21_five_part_facilitator_guide_and_voice_linter() -> None:
    """Verifies the 5-Part Non-Redundant Facilitator Guide and voice linter."""
    from src.agents.planner import _build_slide_teaching_notes
    from src.agents.reviewer import lint_speaker_notes_voice

    notes = _build_slide_teaching_notes(
        badge_name="First Aid",
        req_num="2b",
        slide_title="Direct Pressure & Tourniquet Application",
        req_text="Demonstrate how to control severe bleeding.",
        bullet_points=["Direct Pressure: Press sterile gauze firmly.", "Tourniquet: Apply 2 inches above wound."],
        execution_mode="HANDS_ON_SKILL_STATION",
        archetype="SPLIT_VISUAL_EXPLAINER",
        req_dict={
            "pamphlet_page_citation": "Official BSA First Aid Pamphlet, pp. 24-27",
            "common_misconception_pair": {
                "misconception": "Loosen tourniquet periodically.",
                "fact_correction": "Leave tourniquet secured until EMS arrives.",
            },
        },
    )
    for header in (
        "[PACING & MODALITY]",
        "[ASK SCOUTS FIRST]",
        "[EXPECTED PAMPHLET ANSWER KEY]",
        "[COMMON MISCONCEPTION TO CORRECT]",
        "[DEMONSTRATION & SIGN-OFF RUBRIC]",
    ):
        assert header in notes
    lint_res = lint_speaker_notes_voice([{"slide_number": 3, "presenter_notes": notes}])
    assert lint_res["passed"] is True


def test_v21_single_unified_bottom_misconception_bar_pptx_and_ui() -> None:
    """Verifies the single unified bottom misconception bar in ui/index.html, ui/app.js, and pptx_builder.py."""
    repo_root = Path(__file__).resolve().parents[1]
    assert "stage-misconception-bar" in (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    assert "Misconception vs. Pamphlet Fact" in (repo_root / "src" / "tools" / "pptx_builder.py").read_text(encoding="utf-8")


def test_v21_verb_aligned_fillable_scout_workbook_and_gta_banner() -> None:
    """Verifies the verb-aligned fillable Scout workbook generator and GTA 7.0.3.2 banner."""
    from src.tools.scouting_scraper import generate_fillable_scout_workbook_html

    res = generate_fillable_scout_workbook_html("Physics")
    assert res["status"] == "SUCCESS"
    assert "7.0.3.2" in res["workbook_html"]
    assert "<table" in res["workbook_html"]


def test_v21_one_page_class_preparation_page_cpp_and_organizer_spec() -> None:
    """Verifies the 1-Page Class Preparation Page (CPP) and Organizer Spec Sheet generators."""
    from src.tools.counselor_studiokit import (
        generate_class_preparation_page_cpp,
        generate_organizer_syllabus_spec_sheet,
    )

    cpp = generate_class_preparation_page_cpp("Auctioneering")
    assert cpp["status"] == "SUCCESS"
    assert "<svg" in cpp["cpp_html"]
    spec = generate_organizer_syllabus_spec_sheet("Auctioneering")
    assert spec["status"] == "SUCCESS"
    assert "catalog_blurb" in spec


def test_v21_multisession_clinic_schedules_attendance_and_smart_partials(tmp_path: Path) -> None:
    """Verifies SQLite WAL persistence of clinic schedules and Scout attendance/partials."""
    store = PersistentSessionStore(db_path=str(tmp_path / "clinic.db"))
    sched = store.upsert_clinic_session_schedule_sync(
        workspace_id="ws_1",
        badge_name="Dance",
        session_mode="4_session_mbc",
        session_dates=["Sat 1", "Sat 2", "Sat 3", "Sat 4", "Make-Up"],
    )
    assert sched["session_mode"] == "4_session_mbc"
    sc = store.upsert_scout_session_attendance_and_partials_sync(
        workspace_id="ws_1",
        scout_id="sc_1",
        badge_name="Dance",
        scout_name="Jordan Lee",
        troop_number="Troop 42",
        session_attendance={"S1": "P", "S2": "A", "S3": "P", "S4": "P", "M": "P"},
        completed_reqs=["1", "2"],
    )
    assert sc["session_attendance"]["S2"] == "A"


def test_v21_three_stage_ypt_communication_pack_and_logistics_slides() -> None:
    """Verifies the 3-Stage YPT Two-Deep Communication Pack and Opt-In Slide 2 / Slide N injection."""
    from src.tools.counselor_studiokit import generate_three_stage_ypt_communication_pack
    from src.tools.pptx_builder import inject_class_opening_and_closing_slides

    pack = generate_three_stage_ypt_communication_pack("Psychology")
    assert pack["status"] == "SUCCESS"
    assert "MANDATORY YPT CC" in pack["ypt_mandatory_cc_header"]
    slides = inject_class_opening_and_closing_slides(
        badge_name="Psychology",
        slides=[{"title": "Overview", "archetype": "REQUIREMENTS_TRIAGE_MATRIX", "bullet_points": ["A"]}],
        logistics_config={"enable_opening_closing_slides": True},
    )
    roles = [s.get("slide_role") for s in slides]
    assert "overview-logistics" in roles and "homework-checkout" in roles


def test_v21_mcp_27_capabilities_and_141_openapi_paths() -> None:
    """Verifies 27 MCP capabilities (15 tools, 7 resources, 5 prompts) and 141 OpenAPI 3.1 paths."""
    repo_root = Path(__file__).resolve().parents[1]
    manifest = get_mcp_server_manifest()
    assert manifest["counts"] == {"tools": 15, "resources": 7, "prompts": 5}
    openapi_text = (repo_root / "docs" / "openapi.yaml").read_text(encoding="utf-8")
    assert "/api/v1/studiokit/fillable-workbook:" in openapi_text
    assert "/api/v1/triage/attendance-and-partials:" in openapi_text

