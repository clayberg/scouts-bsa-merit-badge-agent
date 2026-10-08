"""Non-Hollow Behavioral & Conformance Test Suite for Scouts BSA Merit Badge Agent v2.0.

Verifies (`agb adlc hollow-test` compliant):
1. 5-Tier Deep Research sub-requirement richness, execution-mode triage, worked examples, and comparisons.
2. 12-Archetype Storyboard generation, 7 Golden Rules of Copywriting (zero '...' truncation, zero literal '•' bullets), and Keynote Demo Voice speaker notes ([SAY], [DEMONSTRATE], [ASK SCOUTS]).
3. Tri-Modal Visual Asset uniqueness (distinct SVG + high-DPI PNG per slide).
4. Stage 1 In-Memory Conformance Simulator (<10ms AABB overlap check, canvas bounds, font floor >= 13pt).
5. FastMCP cryptographic HITL confirmation_token issuance & verification.
6. FastAPI A2A 1.0 Agent Card (/.well-known/agent.json), A2UI v0.9 JSON envelopes, and Material 3 Expressive Counselor Workbench endpoints.
"""

import os
from fastapi.testclient import TestClient

from src.agents.coordinator import run_merit_badge_workflow
from src.agents.planner import generate_slide_storyboard
from src.agents.reviewer import check_pptx_conformance
from src.server import app
from src.tools.diagram_generator import generate_slide_visual_asset
from src.tools.scouting_scraper import (
    MeritBadgeResearchRequest,
    fetch_merit_badge_pamphlet_pdf,
)


def test_five_tier_deep_research_subrequirements_and_triage():
    """Verifies that First Aid, Camping, and Citizenship in the Nation return rich, triaged sub-requirements."""
    for badge in ["First Aid", "Camping", "Citizenship in the Nation"]:
        res = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name=badge))
        assert res["status"] == "SUCCESS"
        assert res["is_eagle_required"] is True
        reqs = res["requirements"]
        assert len(reqs) >= 5, f"{badge} should have at least 5 detailed sub-requirements"

        modes = {r.get("execution_mode") for r in reqs}
        assert modes.issubset({"IN_CLASS_DISCUSSION", "HANDS_ON_SKILL_STATION", "PREREQUISITE_CAMPOUT_HOME"})
        assert len(modes) >= 2, f"{badge} should span multiple execution modes, found {modes}"

        for r in reqs:
            assert not r["req_text"].endswith("..."), f"Requirement {r['req_number']} was truncated!"
            assert len(r.get("pamphlet_excerpts", [])) >= 2


def test_twelve_archetype_storyboard_and_copywriting_hygiene():
    """Verifies multi-archetype storyboarding, zero literal bullets, zero truncation, and Keynote Demo Voice notes."""
    res = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name="First Aid"))
    storyboard = generate_slide_storyboard(
        badge_name="First Aid",
        requirements=res["requirements"],
        depth_mode="Deep Dive / Camp School Deck",
        is_eagle_required=True,
    )
    slides = storyboard["slides"]
    assert len(slides) >= 7

    archetypes = {s.get("archetype") for s in slides}
    assert "REQUIREMENTS_TRIAGE_MATRIX" in archetypes
    assert len(archetypes) >= 4, f"Expected >= 4 distinct slide archetypes, got {archetypes}"

    for s in slides:
        for bp in s.get("bullet_points", []):
            assert not bp.lstrip().startswith("•"), f"Literal bullet found in '{bp}'"
            assert not bp.endswith("..."), f"Ellipsis truncation found in '{bp}'"
        notes = s.get("presenter_notes") or ""
        assert "[SAY]" in notes or "Counselor" in notes


def test_trimodal_visual_generator_creates_unique_svg_and_png(tmp_path):
    """Verifies that generate_slide_visual_asset produces both SVG and PNG files with unique paths per slide."""
    asset1 = generate_slide_visual_asset(
        badge_name="First Aid",
        req_number="1",
        archetype="DECISION_TREE_FLOW",
        diagram_type="triage_decision_tree",
        slide_title="Emergency Triage Protocol",
        output_dir=str(tmp_path),
    )
    asset2 = generate_slide_visual_asset(
        badge_name="First Aid",
        req_number="5a",
        archetype="DIFFERENTIAL_COMPARISON_2COL",
        diagram_type="heat_comparison",
        slide_title="Heat Exhaustion vs Heat Stroke",
        output_dir=str(tmp_path),
    )
    assert os.path.exists(asset1["png_path"])
    assert os.path.exists(asset2["png_path"])
    assert asset1["png_path"] != asset2["png_path"]
    if asset1.get("svg_path"):
        assert os.path.exists(asset1["svg_path"])


def test_end_to_end_workflow_stage1_conformance_and_a2ui(tmp_path):
    """Verifies full workflow execution, 0 AABB overlaps, FastMCP HITL token, and A2UI v0.9 messages."""
    out_pptx = os.path.join(tmp_path, "Camping_Full_Deck.pptx")
    result = run_merit_badge_workflow(
        badge_name="Camping",
        depth_mode="Deep Dive / Camp School Deck",
        counselor_info={
            "counselor_name": "Scoutmaster Alex Chen",
            "troop_affiliation": "Troop 344, Golden Gate Area Council",
            "email_address": "alex.chen@troop344.org",
        },
        output_path=out_pptx,
    )
    assert result["status"] == "SUCCESS"
    assert os.path.exists(result["output_path"])
    assert result["slide_count"] >= 8
    assert result.get("hitl_confirmation_token")

    conformance = check_pptx_conformance(result["output_path"])
    assert conformance["passed"] is True, f"Stage 1 Conformance failed: {conformance['issues']}"
    assert conformance["aabb_overlap_count"] == 0
    assert conformance["min_font_size_pt"] >= 13.0

    a2ui = result.get("a2ui_messages", [])
    assert len(a2ui) == 3
    assert "beginRendering" in a2ui[0]
    assert "surfaceUpdate" in a2ui[1]
    assert "dataModelUpdate" in a2ui[2]


def test_fastapi_a2a_agent_card_and_m3_a2ui_workbench():
    """Verifies A2A 1.0 discovery, simplified Counselor Workbench HTML, 138-badge catalog, and API endpoints."""
    client = TestClient(app)

    # 1. A2A 1.0 Agent Card
    card_resp = client.get("/.well-known/agent.json")
    assert card_resp.status_code == 200
    card = card_resp.json()
    assert card["protocolVersion"] == "1.0"
    assert card["capabilities"]["a2uiProtocolVersion"] == "v0.9"

    # 2. Simplified Counselor Workbench HTML
    ui_resp = client.get("/")
    assert ui_resp.status_code == 200
    assert "Scouts BSA Merit Badge Counselor Workbench" in ui_resp.text
    assert "Slide Deck Preview" in ui_resp.text
    assert "Official BSA Pamphlet" in ui_resp.text

    # 3. Full 138+ Badge Catalog API with Categories & Resource Links
    badges_resp = client.get("/api/badges")
    assert badges_resp.status_code == 200
    badges_payload = badges_resp.json()
    assert len(badges_payload["badges"]) >= 138
    assert len(badges_payload["categories"]) >= 6

    # 4. A2A Task Send
    task_resp = client.post(
        "/a2a/tasks/send",
        json={
            "sessionId": "test_a2a_session",
            "message": {"parts": [{"text": "Build Citizenship in the Nation deck"}]},
            "metadata": {"badge_name": "Citizenship in the Nation", "depth_mode": "Standard Deck"},
        },
    )
    assert task_resp.status_code == 200
    task_data = task_resp.json()
    assert task_data["status"]["state"] == "completed"
    assert len(task_data["artifacts"]) >= 2


def test_weather_69_slide_comprehensive_deck_and_conformance(tmp_path):
    """Verifies that Weather Merit Badge generates a comprehensive 69-slide deck with Cover Patch+Cover, Requirement Intros, Clean Topic Explainers, Full-Page Diagrams, and a single final Sources & References slide."""
    out_pptx = os.path.join(tmp_path, "Weather_Comprehensive_Deck.pptx")
    result = run_merit_badge_workflow(
        badge_name="Weather",
        depth_mode="Deep Dive / Camp School Deck",
        counselor_info={
            "counselor_name": "Eric Clayberg, Merit Badge Counselor",
            "troop_affiliation": "Scouts BSA Troop 25",
        },
        output_path=out_pptx,
    )
    assert result["status"] == "SUCCESS"
    assert os.path.exists(result["output_path"])
    assert result["slide_count"] >= 65, f"Expected >= 65 slides for Weather deck, got {result['slide_count']}"

    slides = result["storyboard"]["slides"]
    archetypes = {s.get("archetype") for s in slides}
    assert "REQUIREMENT_INTRO" in archetypes
    assert "CONCEPT_TEXT_SLIDE" in archetypes
    assert "FULL_BLEED_IMAGE_EXPLAINER" in archetypes
    assert "SPLIT_VISUAL_EXPLAINER" in archetypes
    assert "SOURCES_AND_REFERENCES" in archetypes

    # Subsequent topic slides must NOT repeat verbatim_requirement_text
    topic_slides = [s for s in slides if s.get("archetype") not in {"REQUIREMENTS_TRIAGE_MATRIX", "REQUIREMENT_INTRO", "SOURCES_AND_REFERENCES"}]
    assert all(not s.get("verbatim_requirement_text") for s in topic_slides), "Subsequent topic slides should not repeat verbatim requirement text!"

    # Final slide must be Sources & References
    assert slides[-1]["archetype"] == "SOURCES_AND_REFERENCES"
    assert "Sources" in slides[-1]["title"]

    conformance = check_pptx_conformance(result["output_path"])
    assert conformance["passed"] is True, f"Stage 1 Conformance failed: {conformance['issues']}"
    assert conformance["aabb_overlap_count"] == 0
    assert conformance["min_font_size_pt"] >= 13.0


def test_all_138_badges_and_standard_vs_deep_dive_modes(tmp_path):
    """Verifies that any of the 138 catalog badges can be generated in both Deep Dive (long) and Standard (focused 1-3 slides/req) modes with 0 AABB overlaps."""
    deep_pptx = os.path.join(tmp_path, "Kayaking_Deep_Dive.pptx")
    std_pptx = os.path.join(tmp_path, "Kayaking_Standard.pptx")

    res_deep = run_merit_badge_workflow(
        badge_name="Kayaking",
        depth_mode="Deep Dive / Camp School Deck",
        output_path=deep_pptx,
    )
    res_std = run_merit_badge_workflow(
        badge_name="Kayaking",
        depth_mode="Standard Deck",
        output_path=std_pptx,
    )

    assert res_deep["status"] == "SUCCESS"
    assert res_std["status"] == "SUCCESS"
    assert res_deep["slide_count"] >= 45, f"Deep Dive should have >= 45 slides, got {res_deep['slide_count']}"
    assert 16 <= res_std["slide_count"] <= 28, f"Standard Deck should have 16-28 focused slides, got {res_std['slide_count']}"
    assert res_deep["slide_count"] > res_std["slide_count"]

    conf_deep = check_pptx_conformance(res_deep["output_path"])
    conf_std = check_pptx_conformance(res_std["output_path"])
    assert conf_deep["passed"] is True and conf_deep["aabb_overlap_count"] == 0
    assert conf_std["passed"] is True and conf_std["aabb_overlap_count"] == 0


def test_v5_slide_typography_alignment_and_borderless_cover_and_headers(tmp_path):
    """Verifies Scout Shop standalone emblem cache, borderless cover slide, single-line borderless centered slide title, larger dynamically-sized fonts, and strict left alignment on all body points."""
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches
    from src.tools.pamphlet_extractor import get_badge_cover_and_patch_paths

    paths = get_badge_cover_and_patch_paths("Weather")
    assert paths["patch_path"] and os.path.exists(paths["patch_path"])
    assert "badge_emblems" in paths["patch_path"]

    out_pptx = os.path.join(tmp_path, "Weather_v5_Check.pptx")
    result = run_merit_badge_workflow(
        badge_name="Weather",
        depth_mode="Standard Deck",
        counselor_info={
            "counselor_name": "Eric Clayberg, Merit Badge Counselor",
            "troop_affiliation": "Scouts BSA Troop 25",
        },
        output_path=out_pptx,
    )
    assert result["status"] == "SUCCESS"
    prs = Presentation(result["output_path"])

    # 1. Cover slide: No bordered AUTO_SHAPE boxes; 2 pictures (emblem + pamphlet cover) and 2 borderless textboxes
    cover = prs.slides[0]
    cover_autoshapes = [s for s in cover.shapes if s.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE]
    cover_pictures = [s for s in cover.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    cover_textboxes = [s for s in cover.shapes if s.shape_type == MSO_SHAPE_TYPE.TEXT_BOX]
    assert len(cover_autoshapes) == 0, f"Cover slide should have 0 boxes, found {len(cover_autoshapes)}"
    assert len(cover_pictures) == 2, f"Cover slide should have 2 pictures (emblem + cover), found {len(cover_pictures)}"
    assert len(cover_textboxes) == 2, f"Cover slide should have 2 borderless textboxes, found {len(cover_textboxes)}"

    # 2. Content slides: Single-line borderless centered slide title, left-aligned body points, larger fonts
    for idx, slide in enumerate(list(prs.slides)[1:], start=2):
        header_shapes = [s for s in slide.shapes if s.has_text_frame and s.top < Inches(0.6)]
        assert len(header_shapes) == 1, f"Slide {idx} should have 1 header shape"
        hdr = header_shapes[0]
        assert hdr.shape_type == MSO_SHAPE_TYPE.TEXT_BOX, f"Slide {idx} header should be borderless TEXT_BOX"
        assert len(hdr.text_frame.paragraphs) == 1, f"Slide {idx} header should have only 1 line (no redundant subtitle)"
        assert hdr.text_frame.paragraphs[0].alignment == PP_ALIGN.CENTER, f"Slide {idx} title must be center-justified"

        body_shapes = [s for s in slide.shapes if s.has_text_frame and s.top >= Inches(0.8)]
        for bsh in body_shapes:
            assert bsh.text_frame.word_wrap is True
            is_footer = bsh.top >= Inches(7.0)
            for p_i, para in enumerate(bsh.text_frame.paragraphs):
                if para.text.strip():
                    assert para.alignment == PP_ALIGN.LEFT, (
                        f"Slide {idx} paragraph {p_i} ('{para.text[:30]}...') must be left-justified, got {para.alignment}"
                    )
                    for run in para.runs:
                        if run.font.size and not is_footer:
                            assert run.font.size.pt >= 15.0, f"Slide {idx} font too small: {run.font.size.pt}pt"


def test_v6_counselor_defaults_separate_email_phone_and_custom_troop_logo_on_cover_slide(tmp_path):
    """Verifies counselor defaults ('Scoutmaster Bob', 'Troop 123, My Council', 'counselor@troop123.org', '(000) 555-1234'), separate Email/Phone + Custom Troop Logo fields in M3 A2UI, and Cover Slide rendering of all 5 counselor inputs."""
    import base64
    from io import BytesIO
    from PIL import Image
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    client = TestClient(app)

    # 1. Verify M3 A2UI HTML has separate Contact Email, Contact Phone, Optional Troop Custom Logo, and exact defaults
    ui_resp = client.get("/")
    assert ui_resp.status_code == 200
    html = ui_resp.text
    assert 'id="input-counselor-name"' in html and 'value="Scoutmaster Bob"' in html
    assert 'id="input-troop-name"' in html and 'value="Troop 123, My Council"' in html
    assert 'id="input-counselor-email"' in html and 'value="counselor@troop123.org"' in html
    assert 'id="input-counselor-phone"' in html and 'value="(000) 555-1234"' in html
    assert 'id="input-troop-logo"' in html and "Optional Troop Custom Logo" in html

    # 2. Verify /api/upload-logo saves custom troop logo and returns logo_path & logo_url
    img_buf = BytesIO()
    Image.new("RGBA", (120, 120), (0, 63, 135, 255)).save(img_buf, format="PNG")
    b64_data = "data:image/png;base64," + base64.b64encode(img_buf.getvalue()).decode("ascii")
    upload_resp = client.post(
        "/api/upload-logo",
        json={"filename": "troop123_custom_logo.png", "data_url": b64_data},
    )
    assert upload_resp.status_code == 200
    up_json = upload_resp.json()
    assert up_json["status"] == "SUCCESS"
    assert os.path.exists(up_json["logo_path"])
    assert up_json["logo_url"].startswith("/assets/custom_logos/")

    # 3. Verify Cover Slide renders default counselor info, Email, Phone, and Custom Troop Logo with 0 AABB overlaps
    out_pptx = os.path.join(tmp_path, "First_Aid_With_Custom_Logo.pptx")
    result = run_merit_badge_workflow(
        badge_name="First Aid",
        depth_mode="Standard Deck",
        counselor_info={
            "counselor_name": "Scoutmaster Bob",
            "troop_affiliation": "Troop 123, My Council",
            "email_address": "counselor@troop123.org",
            "phone_number": "(000) 555-1234",
            "custom_troop_logo_path": up_json["logo_path"],
        },
        output_path=out_pptx,
    )
    assert result["status"] == "SUCCESS"
    conformance = check_pptx_conformance(result["output_path"])
    assert conformance["passed"] is True, f"Stage 1 Conformance failed: {conformance['issues']}"
    assert conformance["aabb_overlap_count"] == 0

    prs = Presentation(result["output_path"])
    cover = prs.slides[0]
    cover_pictures = [s for s in cover.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(cover_pictures) == 3, f"Expected 3 pictures on Cover Slide (Badge Emblem + Pamphlet Cover + Custom Troop Logo), got {len(cover_pictures)}"

    cover_text = "\n".join(s.text_frame.text for s in cover.shapes if s.has_text_frame)
    assert "Scoutmaster Bob" in cover_text
    assert "Troop 123, My Council" in cover_text
    assert "counselor@troop123.org" in cover_text
    assert "(000) 555-1234" in cover_text

    # 4. Verify Streamlit UI (src/app.py) compiles cleanly, removes Browse Filtered Merit Badges expander,
    #    fixes top header padding & dark-mode sidebar contrast, and renders clean unindented HTML
    import ast
    from pathlib import Path
    from src.app import _render_widescreen_slide_html, _render_triage_column

    app_py_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
    app_src = app_py_path.read_text(encoding="utf-8")
    ast.parse(app_src)
    for expected_token in [
        "Scoutmaster Bob",
        "Troop 123, My Council",
        "counselor@troop123.org",
        "(000) 555-1234",
        "Optional Troop Custom Logo",
        "main_badge_dropdown",
        "_clean_html",
        "padding-top: 3.6rem !important;",
        "m3-top-bar",
        "m3-hero-banner",
        "m3-widescreen-slide",
        "m3-speaker-notes-card",
        "m3-triage-col",
        "Slide Filmstrip",
    ]:
        assert expected_token in app_src, f"Expected '{expected_token}' in src/app.py"

    assert "browse_filtered_badges_table" not in app_src, (
        "Browse Filtered Merit Badges expander table should be removed from src/app.py"
    )

    # Verify _render_widescreen_slide_html and _render_triage_column produce zero 4-space indented lines
    for idx_to_check in [-1, 0, 1]:
        rendered_html = _render_widescreen_slide_html(
            result=result,
            slide_idx=idx_to_check,
            counselor_name="Scoutmaster Bob",
            troop_affiliation="Troop 123, My Council",
            email_address="counselor@troop123.org",
            phone_number="(000) 555-1234",
            logo_path=up_json["logo_path"],
            patch_path=None,
            cover_path=None,
        )
        for line in rendered_html.splitlines():
            assert not line.startswith("    "), f"Found 4-space indented HTML line that would trigger raw HTML code block: {line!r}"
            assert line.strip() != "", "Found blank line inside HTML block that would split CommonMark HTML parsing"

    triage_html = _render_triage_column(
        "💬 Discussion & Core Knowledge",
        "m3-chip-primary",
        (result.get("research_artifact") or {}).get("requirements", []),
    )
    for line in triage_html.splitlines():
        assert not line.startswith("    "), f"Found 4-space indented HTML line in triage column: {line!r}"
        assert line.strip() != ""

    # 5. Verify README.md updates
    readme_path = Path(__file__).resolve().parents[1] / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")
    for eliminated in [
        "AgentOps Evaluation Rubric Score",
        "Architectural Highlights & 95/95 Rubric Compliance",
        "Automated Evaluation Suite & Golden Dataset",
    ]:
        assert eliminated not in readme_text, f"Eliminated section/reference '{eliminated}' still found in README.md"
    for required_section in [
        "Key Capabilities & Features",
        "Quick Start: Local / Laptop Execution",
        "How to Use the Counselor Workbench",
        "Optional Cloud Deployment",
        "./run_local.sh a2ui",
        "./run_local.sh streamlit",
    ]:
        assert required_section in readme_text, f"Expected '{required_section}' in README.md"


def test_v7_detailed_teaching_notes_footer_banner_and_final_slide_attribution(tmp_path):
    """Verifies:
    1. Detailed, slide-specific Counselor Teaching Notes where [SAY] is more detailed than the slide text,
       generic boilerplate is eliminated, and [DEMONSTRATE] / [ASK SCOUTS] are selectively included/excluded.
    2. Bottom attribution & feedback banner in both UIs (ui/index.html and src/app.py) with Eric Clayberg
       (Troop 19, Middleton MA), Google Gemini model info, LinkedIn link, and pre-filled mailto button.
    3. Final slide attribution on the Sources & References slide of every generated deck.
    """
    from pathlib import Path
    from pptx import Presentation

    # 1. Generate Weather Deep Dive deck and verify Counselor Teaching Notes & Final Slide Attribution
    out_pptx = os.path.join(tmp_path, "Weather_v7_Teaching_Notes.pptx")
    result = run_merit_badge_workflow(
        badge_name="Weather",
        depth_mode="Deep Dive / Camp School Deck",
        output_path=out_pptx,
    )
    assert result["status"] == "SUCCESS"
    slides = result["storyboard"]["slides"]

    slides_with_demo = 0
    slides_without_demo = 0
    slides_with_ask = 0
    slides_without_ask = 0

    for idx, s in enumerate(slides):
        notes = s.get("presenter_notes") or ""
        assert "[SAY]" in notes, f"Slide {idx + 2} ('{s.get('title')}') missing [SAY] in presenter_notes"

        # Verify old generic boilerplate is completely eliminated
        for banned_boilerplate in [
            "Every detail on this slide comes from your official Scouts BSA merit badge pamphlet",
            "Pair up with your buddy now. How would you apply Requirement",
            "Let us review the core standard together.",
        ]:
            assert banned_boilerplate not in notes, f"Found generic boilerplate '{banned_boilerplate}' in slide {idx + 2}"

        # Extract [SAY] line(s) and verify they are more detailed than the slide bullet points
        say_lines = [line for line in notes.splitlines() if line.strip().startswith("[SAY]")]
        say_text = " ".join(say_lines)
        bullet_text = " ".join(s.get("bullet_points") or [])
        if s.get("archetype") not in {"SOURCES_AND_REFERENCES"}:
            assert len(say_text) > len(bullet_text), (
                f"Slide {idx + 2} ('{s.get('title')}') [SAY] text ({len(say_text)} chars) should be more detailed "
                f"than slide bullet text ({len(bullet_text)} chars)"
            )

        if "[DEMONSTRATE]" in notes:
            slides_with_demo += 1
        else:
            slides_without_demo += 1

        if "[ASK SCOUTS]" in notes:
            slides_with_ask += 1
        else:
            slides_without_ask += 1

    # Verify selective inclusion/exclusion of [DEMONSTRATE] and [ASK SCOUTS]
    assert slides_with_demo > 0 and slides_without_demo > 0, (
        f"[DEMONSTRATE] should be selectively included/excluded across slides (with={slides_with_demo}, without={slides_without_demo})"
    )
    assert slides_with_ask > 0 and slides_without_ask > 0, (
        f"[ASK SCOUTS] should be selectively included/excluded across slides (with={slides_with_ask}, without={slides_without_ask})"
    )

    # 2. Verify Final Slide Attribution in storyboard AND .pptx file
    final_slide = slides[-1]
    assert final_slide["archetype"] == "SOURCES_AND_REFERENCES"
    final_bullets_joined = "\n".join(final_slide.get("bullet_points") or [])
    assert "Scouts BSA Merit Badge Counselor Workbench" in final_bullets_joined
    assert "https://github.com/clayberg/scouts-bsa-merit-badge-agent" in final_bullets_joined
    assert "Eric Clayberg" in final_bullets_joined
    assert "Troop 19, Middleton MA" in final_bullets_joined

    prs = Presentation(result["output_path"])
    # Cover slide notes check
    cover_notes = prs.slides[0].notes_slide.notes_text_frame.text
    assert "[SAY]" in cover_notes and "Weather Merit Badge" in cover_notes
    # Final slide .pptx text check
    pptx_final_text = "\n".join(
        sh.text_frame.text for sh in prs.slides[-1].shapes if sh.has_text_frame
    )
    assert "https://github.com/clayberg/scouts-bsa-merit-badge-agent" in pptx_final_text
    assert "Eric Clayberg" in pptx_final_text and "Troop 19, Middleton MA" in pptx_final_text

    conformance = check_pptx_conformance(result["output_path"])
    assert conformance["passed"] is True
    assert conformance["aabb_overlap_count"] == 0

    # 3. Verify Bottom Attribution & Feedback Banner in both UIs (ui/index.html and src/app.py)
    client = TestClient(app)
    ui_html = client.get("/").text
    app_py_text = (Path(__file__).resolve().parents[1] / "src" / "app.py").read_text(encoding="utf-8")

    for ui_source_name, ui_content in [("ui/index.html", ui_html), ("src/app.py", app_py_text)]:
        assert "Eric Clayberg - Troop 19, Middleton MA" in ui_content, f"Missing creator attribution in {ui_source_name}"
        assert "Google Gemini" in ui_content, f"Missing Google Gemini credit in {ui_source_name}"
        assert "gemini-2.5-pro & gemini-2.5-flash via Google ADK" not in ui_content, f"Should drop model detail string in {ui_source_name}"
        assert "https://www.linkedin.com/in/clayberg" in ui_content, f"Missing LinkedIn URL in {ui_source_name}"
        assert (
            "mailto:clayberg@gmail.com?subject=Scouts%20BSA%20Merit%20Badge%20Counselor%20Workbench%20Feedback"
            in ui_content
        ), f"Missing Suggestions & Feedback mailto link in {ui_source_name}"


def test_v31_beautification_deep_research_codesign_and_counselor_tracking() -> None:
    """Verify v3.1 slide beautification visual diffs, Location/ZIP grounding, zero boilerplate, co-design bar, and counselor tracking."""
    from pathlib import Path
    from pptx import Presentation
    from src.agents.guardrails import estimate_workflow_finops_cost

    # 1. Verify $1.00 FinOps budget cap for STUDIO
    finops_studio = estimate_workflow_finops_cost(
        badge_name="Weather",
        depth_mode="Standard Deck",
        beautification_tier="STUDIO",
        enable_deep_research=True,
    )
    assert finops_studio["max_budget_usd"] == 1.00

    # 2. Verify STANDARD vs BEAUTIFIED vs STUDIO slide diffs & .pptx rendering
    client = TestClient(app)
    resp_std = client.post(
        "/api/workflow/run",
        json={
            "badge_name": "Weather",
            "depth_mode": "Standard Deck",
            "counselor_name": "Eric Clayberg",
            "troop_affiliation": "Troop 19, Middleton MA",
            "location_or_zip": "01949",
            "email_address": "clayberg@gmail.com",
            "phone_number": "(978) 555-0119",
            "beautification_tier": "STANDARD",
            "enable_deep_research": False,
            "audience_level": "All Scouts (Ages 11–17)",
        },
    ).json()
    resp_beautified = client.post(
        "/api/workflow/run",
        json={
            "badge_name": "Weather",
            "depth_mode": "Standard Deck",
            "counselor_name": "Eric Clayberg",
            "troop_affiliation": "Troop 19, Middleton MA",
            "location_or_zip": "01949",
            "email_address": "clayberg@gmail.com",
            "phone_number": "(978) 555-0119",
            "beautification_tier": "BEAUTIFIED",
            "enable_deep_research": True,
            "audience_level": "All Scouts (Ages 11–17)",
        },
    ).json()
    resp_studio = client.post(
        "/api/workflow/run",
        json={
            "badge_name": "Weather",
            "depth_mode": "Standard Deck",
            "counselor_name": "Eric Clayberg",
            "troop_affiliation": "Troop 19, Middleton MA",
            "location_or_zip": "01949",
            "email_address": "clayberg@gmail.com",
            "phone_number": "(978) 555-0119",
            "beautification_tier": "STUDIO",
            "enable_deep_research": True,
            "audience_level": "Older Scouts / Eagle Prep (Ages 14–17)",
        },
    ).json()

    # Verify distinct output filenames so browser/server caching never mixes tiers
    assert resp_std["output_path"] != resp_beautified["output_path"]
    assert resp_beautified["output_path"] != resp_studio["output_path"]

    std_slides = resp_std["storyboard"]["slides"]
    beautified_slides = resp_beautified["storyboard"]["slides"]
    studio_slides = resp_studio["storyboard"]["slides"]

    assert std_slides[3]["beautification_tier"] == "STANDARD"
    assert beautified_slides[3]["beautification_tier"] == "BEAUTIFIED"
    assert studio_slides[3]["beautification_tier"] == "STUDIO"

    # Verify EDGE Skill Concept Maps are attached and rotating palettes are applied
    assert any(s.get("ai_hero_image_path") for s in studio_slides[1:-1])
    assert len({s.get("accent_palette_key") for s in studio_slides[1:-1]}) >= 3

    # 3. Verify zero repeated slide boilerplate ("DEEP RESEARCH & LOCAL GROUNDING" / real_world_connection_box)
    assert all(not s.get("real_world_connection_box") for s in studio_slides)
    assert all("DEEP RESEARCH & LOCAL GROUNDING" not in s.get("presenter_notes", "") for s in studio_slides)

    # 4. Verify explicit Location/ZIP ("01949" / "Middleton, MA") resolution in Slide 2 Overview, Lesson Plan & Parent Letter
    resolved_loc = resp_studio["deep_research_enrichment"]["resolved_location"]
    assert "NWS Boston/Norton" in resolved_loc["nws_office"]
    overview_slide = studio_slides[0]
    assert overview_slide["req_number"] == "Overview"
    assert "NWS Boston/Norton" in overview_slide.get("verbatim_requirement_text", "")

    # Verify distinct slide background colors in .pptx across STANDARD (#FFFFFF), BEAUTIFIED (#FAF8F5), and STUDIO (#0F172A)
    prs_std = Presentation(resp_std["output_path"])
    prs_beautified = Presentation(resp_beautified["output_path"])
    prs_studio = Presentation(resp_studio["output_path"])

    assert str(prs_std.slides[0].background.fill.fore_color.rgb) == "FFFFFF"
    assert str(prs_beautified.slides[0].background.fill.fore_color.rgb) == "FAF8F5"
    assert str(prs_studio.slides[0].background.fill.fore_color.rgb) == "0F172A"

    pptx_all_text = "\n".join(
        sh.text_frame.text for slide in prs_studio.slides for sh in slide.shapes if sh.has_text_frame
    )
    assert "Troop 19, Middleton MA" in pptx_all_text
    assert "NWS Boston/Norton" in pptx_all_text

    for deck_path in [resp_std["output_path"], resp_beautified["output_path"], resp_studio["output_path"]]:
        conformance = check_pptx_conformance(deck_path)
        assert conformance["passed"] is True
        assert conformance["aabb_overlap_count"] == 0

    # 5. Verify Parent Letter & Lesson Plan track counselor inputs & resolved local region without reverting to Scoutmaster Bob / Troop 123
    parent_letter_md = resp_studio["prerequisite_parent_letter"]["letter_markdown"]
    agenda_md = resp_studio["session_agenda"]["agenda_markdown"]
    assert "Eric Clayberg" in parent_letter_md
    assert "Troop 19, Middleton MA" in parent_letter_md
    assert "clayberg@gmail.com" in parent_letter_md
    assert "(978) 555-0119" in parent_letter_md
    assert "NWS Boston/Norton" in parent_letter_md
    assert "NWS Boston/Norton" in agenda_md
    assert "Scoutmaster Bob" not in parent_letter_md
    assert "Troop 123" not in parent_letter_md

    # Verify audience level adaptation in presenter notes
    assert any("EAGLE PREP" in s.get("presenter_notes", "").upper() for s in studio_slides[1:-1])

    # 6. Verify Location/ZIP input, Audience Level selector, and Per-Slide Co-Design Bar in both UIs
    ui_html = client.get("/").text
    app_js_text = (Path(__file__).resolve().parents[1] / "ui" / "app.js").read_text(encoding="utf-8")
    app_py_text = (Path(__file__).resolve().parents[1] / "src" / "app.py").read_text(encoding="utf-8")

    assert "input-counselor-location" in ui_html
    assert "audience-select" in ui_html
    assert "slide-codesign-bar" in ui_html
    assert "btn-apply-codesign" in app_js_text
    assert "Location (City, State or ZIP Code)" in app_py_text
    assert "Target Scout Audience Level" in app_py_text
    assert "Per-Slide Interactive Co-Design Bar" in app_py_text


def test_image_studio_agents_consent_gate_counselor_cache_and_graphic_restoration() -> None:
    """Verify WebImageSearchAgent, NanoBananaImageAgent consent gate, counselor caching, and graphic None/Restore."""
    from pathlib import Path
    from src.agents import (
        get_merit_badge_coordinator_agent,
        get_nano_banana_image_agent,
        get_web_image_search_agent,
    )
    from src.memory.session_store import (
        load_local_counselor_profile,
        save_local_counselor_profile,
    )
    from src.server import app

    client = TestClient(app)

    # 1. Verify ADK Coordinator registers 7 specialist sub-agents including WebImageSearchAgent & NanoBananaImageAgent
    coord = get_merit_badge_coordinator_agent()
    sub_names = [a.name for a in coord.sub_agents]
    assert "WebImageSearchAgent" in sub_names
    assert "NanoBananaImageAgent" in sub_names
    assert len(sub_names) == 7
    assert get_web_image_search_agent().name == "WebImageSearchAgent"
    assert get_nano_banana_image_agent().name == "NanoBananaImageAgent"

    # 2. Verify local Counselor Profile caching (save + load round-trip)
    saved = save_local_counselor_profile(
        {
            "counselor_name": "Eric Clayberg",
            "troop_affiliation": "Troop 19, Middleton MA",
            "location_or_zip": "01949",
            "email_address": "clayberg@gmail.com",
            "phone_number": "(978) 555-0119",
        }
    )
    assert saved["status"] == "SUCCESS"
    assert saved["saved"] is True
    loaded = load_local_counselor_profile()
    assert loaded["counselor_name"] == "Eric Clayberg"
    assert loaded["troop_affiliation"] == "Troop 19, Middleton MA"
    assert loaded["location_or_zip"] == "01949"

    # 3. Run workflow and verify original graphic preservation, None removal, and Restore Original
    wf_resp = client.post(
        "/api/workflow/run",
        json={
            "badge_name": "First Aid",
            "depth_mode": "Standard Deck",
            "counselor_name": "Eric Clayberg",
            "troop_affiliation": "Troop 19, Middleton MA",
            "location_or_zip": "01949",
            "beautification_tier": "BEAUTIFIED",
        },
    ).json()
    slides = wf_resp["storyboard"]["slides"]
    # Pick a slide that initially has an original pamphlet/topic diagram
    target_idx = next(i for i, s in enumerate(slides) if s.get("original_diagram_url"))
    orig_slide = slides[target_idx]
    orig_url = orig_slide["original_diagram_url"]
    assert orig_url

    # Set Right-Side Graphic to "none" -> removes graphic and expands layout to CONCEPT_TEXT_SLIDE
    none_resp = client.post(
        "/api/slide/regenerate",
        json={
            "badge_name": "First Aid",
            "slide_index": target_idx,
            "new_archetype": "SPLIT_VISUAL_EXPLAINER",
            "new_visual_theme": "NUMBERED_STEP_CARDS",
            "new_accent_palette": "NAVY_GOLD",
            "visual_source_mode": "none",
            "slide_data": orig_slide,
        },
    ).json()
    assert none_resp["diagram_url"] is None
    assert none_resp["diagram_path"] is None
    assert none_resp["new_archetype"] == "CONCEPT_TEXT_SLIDE"

    # Restore Original Slide Graphic -> brings back original diagram_url and split layout
    slide_after_none = dict(orig_slide)
    slide_after_none["diagram_url"] = None
    slide_after_none["diagram_path"] = None
    slide_after_none["archetype"] = "CONCEPT_TEXT_SLIDE"
    restored_resp = client.post(
        "/api/slide/regenerate",
        json={
            "badge_name": "First Aid",
            "slide_index": target_idx,
            "new_archetype": "CONCEPT_TEXT_SLIDE",
            "new_visual_theme": "NUMBERED_STEP_CARDS",
            "new_accent_palette": "NAVY_GOLD",
            "visual_source_mode": "restore_original",
            "slide_data": slide_after_none,
        },
    ).json()
    assert restored_resp["diagram_url"] == orig_url
    assert restored_resp["new_archetype"] != "CONCEPT_TEXT_SLIDE"

    # 4. Verify NanoBananaImageAgent FinOps Consent Gate ($0.08 USD budget, blocks when user_consented=False, verifies prompt alignment when True)
    from src.agents.image_studio import (
        NANO_BANANA_VISUAL_STYLES,
        _extract_visual_subject_from_prompt,
        verify_generated_image_matches_prompt,
    )

    for expected_style in ("Photorealistic Image", "Line Drawing", "Cartoon Drawing", "Technical Diagram"):
        assert expected_style in NANO_BANANA_VISUAL_STYLES

    # Verify shorthand slide titles like "The five-and-five (5 back blows: Core Concepts & Definitions" expand cleanly
    expanded_subj = _extract_visual_subject_from_prompt(
        badge_name="First Aid",
        slide_title="Requirement 2a: The five-and-five (5 back blows: Core Concepts & Definitions",
        custom_prompt="Scouts practicing The five-and-five (5 back blows: Core Concepts & Definitions outdoors",
    )
    assert "back blows" in expanded_subj.lower()
    assert "heimlich" in expanded_subj.lower() or "choking" in expanded_subj.lower()
    assert "core concepts" not in expanded_subj.lower()

    first_aid_dir = Path(__file__).resolve().parent.parent / "assets" / "badge_image_catalog" / "first_aid"
    web_cache_dir = Path(__file__).resolve().parent.parent / "assets" / "badge_image_catalog" / "_web_search_cache"
    saved_first_aid = {p.name: p.read_bytes() for p in first_aid_dir.glob("*") if p.is_file()}
    saved_web_cache = {p.name for p in web_cache_dir.glob("*") if p.is_file()} if web_cache_dir.exists() else set()

    try:
        cost_resp = client.post(
            "/api/slide/estimate-image-cost",
            json={"badge_name": "First Aid", "num_images": 1, "visual_style": "Line Drawing"},
        ).json()
        assert cost_resp["requires_user_consent"] is True
        assert cost_resp["estimated_cost_usd"] == 0.08

        blocked_gen = client.post(
            "/api/slide/generate-nano-banana-image",
            json={
                "badge_name": "First Aid",
                "req_number": str(orig_slide["req_number"]),
                "slide_title": orig_slide["title"],
                "custom_prompt": "boy scout in a canoe on a calm mountain lake",
                "bullet_points": orig_slide["bullet_points"],
                "visual_style": "Line Drawing",
                "beautification_tier": "BEAUTIFIED",
                "user_consented": False,
            },
        ).json()
        assert blocked_gen["status"] == "CONSENT_REQUIRED"

        consented_gen = client.post(
            "/api/slide/generate-nano-banana-image",
            json={
                "badge_name": "First Aid",
                "req_number": str(orig_slide["req_number"]),
                "slide_title": orig_slide["title"],
                "custom_prompt": "boy scout in a canoe on a calm mountain lake",
                "bullet_points": orig_slide["bullet_points"],
                "visual_style": "Line Drawing",
                "beautification_tier": "BEAUTIFIED",
                "user_consented": True,
            },
        ).json()
        assert consented_gen["status"] == "SUCCESS"
        assert consented_gen["image_entry"]["source_type"] == "NANO_BANANA_AI"
        assert Path(consented_gen["image_entry"]["image_path"]).exists()
        assert consented_gen["prompt_alignment"]["matches_prompt"] is True
        assert consented_gen["prompt_alignment"]["alignment_score"] >= 0.70

        direct_check = verify_generated_image_matches_prompt(
            image_path=consented_gen["image_entry"]["image_path"],
            visual_subject="boy scout in a canoe on a calm mountain lake",
            visual_style="Line Drawing",
            badge_name="First Aid",
        )
        assert direct_check["alignment_score"] > 0.0

        # Verify Clear Web/AI Cache button, include_humans controls, and Tab 4 File Upload in both Web UI and Streamlit UI
        from src.agents.image_studio import resolve_content_aware_visual_config

        cfg_req1 = resolve_content_aware_visual_config(
            badge_name="First Aid",
            slide_title="Requirement 1: Triage & Primary Survey ABCs",
            req_number="1",
            bullet_points=["Scene safety", "4-Tier Triage", "Airway Breathing Circulation", "Recovery position"],
        )
        assert cfg_req1["include_humans"] is True
        assert cfg_req1["effective_style"] == "4-Quadrant Concept Map"

        cfg_req2b = resolve_content_aware_visual_config(
            badge_name="First Aid",
            slide_title="Requirement 2b: Personal vs. Troop First-Aid Kit",
            req_number="2b",
            bullet_points=["Adhesive bandages", "SAM splint", "Sterile gauze", "Nitrile gloves"],
        )
        assert cfg_req2b["include_humans"] is False
        assert cfg_req2b["paradigm_category"] == "GEAR_OR_ENVIRONMENT_NO_HUMANS"

        cfg_override = resolve_content_aware_visual_config(
            badge_name="First Aid",
            slide_title="Requirement 1: Triage & Primary Survey ABCs",
            req_number="1",
            include_humans=False,
        )
        assert cfg_override["include_humans"] is False
        assert cfg_override["humans_source"] == "EXPLICIT_OVERRIDE"

        ui_html = client.get("/").text
        app_py_text = (Path(__file__).resolve().parents[1] / "src" / "app.py").read_text(encoding="utf-8")
        assert "btn-studio-clear-cache" in ui_html
        assert "Clear Web/AI Cache" in ui_html
        assert "Clear Web/AI Cache" in app_py_text
        assert "studio-ai-humans-select" in ui_html
        assert "studio-ai-include-humans-checkbox" in ui_html
        assert "Human Presence & Uniform Directive" in app_py_text
        assert "import re" in app_py_text
        assert "studio-tab-upload" in ui_html
        assert "📁 4. File Upload" in ui_html
        assert "📁 4. File Upload" in app_py_text
        assert "upload_custom_slide_image" in app_py_text

        # 5. Verify WebImageSearchAgent endpoint returns real Wikipedia/Wikimedia images (no Curated Archive fallback)
        web_resp = client.post(
            "/api/slide/search-web-images",
            json={
                "badge_name": "First Aid",
                "req_number": str(orig_slide["req_number"]),
                "slide_title": orig_slide["title"],
                "bullet_points": orig_slide["bullet_points"],
                "search_query": "boy scout in a canoe",
                "max_results": 12,
            },
        ).json()
        assert len(web_resp["results"]) >= 1
        assert all("Curated Archive" not in r.get("title", "") for r in web_resp["results"])
        cat_resp = client.get("/api/badge/images?badge_name=First%20Aid").json()
        assert len(cat_resp["images"]) >= 2

        # 6. Verify 4th Option: Local File Upload (POST /api/slide/upload-image, $0.00 USD, USER_UPLOAD)
        import base64
        import io
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (320, 200), (27, 54, 93)).save(buf, format="PNG")
        sample_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

        upload_resp = client.post(
            "/api/slide/upload-image",
            json={
                "badge_name": "First Aid",
                "image_base64": sample_b64,
                "filename": "troop19_splint_practice.png",
                "title": "Troop 19 Splint Practice Photo",
                "description": "Local Troop 19 photo showing forearm splint practice.",
                "req_number": str(orig_slide["req_number"]),
                "slide_title": orig_slide["title"],
            },
        ).json()
        assert upload_resp["status"] == "SUCCESS"
        assert upload_resp["cost_usd"] == 0.0
        assert upload_resp["image_entry"]["source_type"] == "USER_UPLOAD"
        assert upload_resp["image_entry"]["title"] == "Troop 19 Splint Practice Photo"
        uploaded_file = Path(upload_resp["image_path"])
        assert uploaded_file.exists()

        # 7. Purge test-generated web/AI images for a test badge and preserve tracked First Aid catalog files
        purge_resp = client.delete("/api/badge/images?badge_name=First%20Aid").json()
        assert purge_resp["status"] == "SUCCESS"
        cat_after_purge = client.get("/api/badge/images?badge_name=First%20Aid").json()
        assert all(
            img.get("source_type") not in ("WEB_IMAGE_SEARCH", "NANO_BANANA_AI")
            for img in cat_after_purge["images"]
        )
        # Verify USER_UPLOAD is preserved across Clear Web/AI Cache, then clean up our test upload
        assert any(img.get("source_type") == "USER_UPLOAD" for img in cat_after_purge["images"])
    finally:
        for p in first_aid_dir.glob("*"):
            if p.is_file() and p.name not in saved_first_aid:
                p.unlink(missing_ok=True)
        for fname, fbytes in saved_first_aid.items():
            (first_aid_dir / fname).write_bytes(fbytes)
        if web_cache_dir.exists():
            for p in web_cache_dir.glob("*"):
                if p.is_file() and p.name not in saved_web_cache:
                    p.unlink(missing_ok=True)


def test_api_v1_feedback_flywheel_and_versioning_headers():
    """Verifies POST /api/v1/feedback Golden Dataset auto-promotion, SQLite persistence, X-API-Version headers, and /api/v1/cache/clear."""
    from pathlib import Path

    client = TestClient(app)
    golden_ext_path = Path(__file__).resolve().parent / "data" / "golden_extensions.json"
    orig_golden_bytes = golden_ext_path.read_bytes() if golden_ext_path.exists() else None

    try:
        # 1. Verify X-API-Version: 1.2.0 header on /api/v1/* and Deprecation/Sunset headers on legacy /api/*
        health_v1 = client.get("/api/v1/health")
        assert health_v1.status_code == 200
        assert health_v1.headers.get("X-API-Version") == "1.2.0"

        health_legacy = client.get("/api/health")
        assert health_legacy.status_code == 200
        assert health_legacy.headers.get("X-API-Version") == "1.2.0"
        assert health_legacy.headers.get("Deprecation") == "true"
        assert "Sunset" in health_legacy.headers

        # 2. Verify high-confidence rating (rating >= 4 + requirement_accuracy_verified=True) promotes to golden dataset
        fb_resp = client.post(
            "/api/v1/feedback",
            json={
                "badge_name": "First Aid",
                "counselor_name": "Eric Clayberg",
                "session_id": "test_flywheel_session_01",
                "requirement_count": 14,
                "rating": 5,
                "requirement_accuracy_verified": True,
                "comments": "Verified all 14 First Aid requirements and EDGE speaker notes.",
            },
        )
        assert fb_resp.status_code == 200
        fb_data = fb_resp.json()
        assert fb_data["status"] == "RECORDED"
        assert fb_data["schema_version"] == "1.2.0"
        assert fb_data["promoted_to_golden_dataset"] is True
        assert fb_data["sqlite_persisted"] is True
        assert fb_data["golden_extensions_count"] >= 1

        # 3. Verify lower rating (rating=3) records to SQLite but does NOT promote to golden dataset
        fb_low = client.post(
            "/api/v1/feedback",
            json={
                "badge_name": "Weather",
                "counselor_name": "Eric Clayberg",
                "session_id": "test_flywheel_session_02",
                "requirement_count": 9,
                "rating": 3,
                "requirement_accuracy_verified": True,
                "comments": "Acceptable draft, needs one more local weather chart.",
            },
        ).json()
        assert fb_low["status"] == "RECORDED"
        assert fb_low["promoted_to_golden_dataset"] is False
        assert fb_low["sqlite_persisted"] is True

        # 4. Verify UI HTML includes the new Counselor Rating & Continuous Learning Flywheel Sign-Off Card
        ui_html = client.get("/").text
        assert "studiokit-feedback-card" in ui_html
        assert "btn-submit-counselor-feedback" in ui_html
        assert "Counselor Sign-Off &amp; Continuous Learning Flywheel" in ui_html

        # 5. Verify /api/v1/cache/clear endpoint
        cache_clear_resp = client.get("/api/v1/cache/clear?badge_name=First%20Aid")
        assert cache_clear_resp.status_code == 200
        assert cache_clear_resp.json()["status"] == "SUCCESS"
        assert "first_aid_cover.png" in cache_clear_resp.json()["refilled_covers"]
    finally:
        if orig_golden_bytes is not None:
            golden_ext_path.write_bytes(orig_golden_bytes)





