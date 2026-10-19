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
    assert conformance["min_font_size_pt"] >= 12.0

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
    assert conformance["min_font_size_pt"] >= 12.0


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
                            assert run.font.size.pt >= 12.0, f"Slide {idx} font too small: {run.font.size.pt}pt"



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
    if os.path.exists(up_json["logo_path"]):
        os.unlink(up_json["logo_path"])

    # 4. Verify FastAPI Material 3 Counselor Workbench (src/server.py, ui/index.html, ui/app.js, ui/styles.css)
    #    compiles cleanly and legacy Streamlit UI (src/app.py) is completely removed
    import ast
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "src" / "app.py").exists(), "Legacy Streamlit src/app.py should be completely removed"

    server_src = (repo_root / "src" / "server.py").read_text(encoding="utf-8")
    ast.parse(server_src)
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")
    ui_css = (repo_root / "ui" / "styles.css").read_text(encoding="utf-8")
    combined_ui = ui_html + "\n" + ui_js + "\n" + ui_css

    for expected_token in [
        "Scoutmaster Bob",
        "Troop 123, My Council",
        "counselor@troop123.org",
        "(000) 555-1234",
        "Optional Troop Custom Logo",
        "m3-top-bar",
        "m3-hero-banner",
        "m3-widescreen-slide",
        "m3-speaker-notes-card",
        "m3-triage-col",
    ]:
        assert expected_token in combined_ui, f"Expected '{expected_token}' in Material 3 Counselor Workbench UI"

    # 5. Verify README.md updates
    readme_path = repo_root / "README.md"
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
        "./run_local.sh",
    ]:
        assert required_section in readme_text, f"Expected '{required_section}' in README.md"


def test_v7_detailed_teaching_notes_footer_banner_and_final_slide_attribution(tmp_path):
    """Verifies:
    1. Detailed, slide-specific Counselor Teaching Notes where [SAY] is more detailed than the slide text,
       generic boilerplate is eliminated, and [DEMONSTRATE] / [ASK SCOUTS] are selectively included/excluded.
    2. Bottom attribution & feedback banner in the Counselor Workbench UI (ui/index.html) with Eric Clayberg
       (Troop 19, Middleton MA), Google Gemini model info, LinkedIn link, and pre-filled mailto button.
    3. Final slide attribution on the Sources & References slide of every generated deck.
    """
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

    # 3. Verify Bottom Attribution & Feedback Banner in Counselor Workbench UI (ui/index.html)
    client = TestClient(app)
    ui_html = client.get("/").text

    for ui_source_name, ui_content in [("ui/index.html", ui_html)]:
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

    # 6. Verify Location/ZIP input, Audience Level selector, and Per-Slide Co-Design Bar in Material 3 Counselor Workbench
    ui_html = client.get("/").text
    app_js_text = (Path(__file__).resolve().parents[1] / "ui" / "app.js").read_text(encoding="utf-8")

    assert "input-counselor-location" in ui_html
    assert "audience-select" in ui_html
    assert "slide-codesign-bar" in ui_html
    assert "btn-apply-codesign" in app_js_text
    assert "Location (City, State or ZIP Code)" in ui_html
    assert "Target Scout Audience Level" in ui_html
    assert "Per-Slide Interactive Co-Design Bar" in ui_html


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
        assert not consented_gen["image_entry"]["title"].startswith("Line Drawing:")
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

        # Verify Clear Web/AI Cache button, include_humans controls, and Tab 4 File Upload in Counselor Workbench UI
        from src.agents.image_studio import (
            NANO_BANANA_VISUAL_STYLES,
            _canonical_figure_path,
            resolve_content_aware_visual_config,
        )
        from src.tools.pamphlet_extractor import _scoutshop_public_search_context

        rebased_hero = _canonical_figure_path(
            "/some/foreign/workstation/path/assets/badge_image_catalog/first_aid/first_aid_req_1_nano_hero.png"
        )
        assert Path(rebased_hero).exists()

        assert "Auto (Content-Aware Mix)" in NANO_BANANA_VISUAL_STYLES
        assert all("Option E" not in s for s in NANO_BANANA_VISUAL_STYLES)
        assert _scoutshop_public_search_context() == {"apiKeys": [f"klevu-{168554966403}{616429}"]}

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
        server_py_text = (Path(__file__).resolve().parents[1] / "src" / "server.py").read_text(encoding="utf-8")
        assert "btn-studio-clear-cache" in ui_html
        assert "Clear Web/AI Cache" in ui_html
        assert "Auto (Content-Aware Mix)" in ui_html
        assert "Option E" not in ui_html
        assert "Include Uniformed Scouts" in ui_html
        assert "(`include_humans`)" not in ui_html
        assert "studio-ai-humans-select" in ui_html
        assert "studio-ai-include-humans-checkbox" in ui_html
        assert "studio-tab-upload" in ui_html
        assert "📁 4. File Upload" in ui_html
        assert "upload_custom_slide_image" in server_py_text

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

        # 7. Purge test-generated web/AI images for a test badge and preserve pre-generated NANO_BANANA_HERO & tracked First Aid catalog files
        purge_resp = client.delete("/api/badge/images?badge_name=First%20Aid").json()
        assert purge_resp["status"] == "SUCCESS"
        cat_after_purge = client.get("/api/badge/images?badge_name=First%20Aid").json()
        assert all(
            img.get("source_type") not in ("WEB_IMAGE_SEARCH", "NANO_BANANA_AI")
            for img in cat_after_purge["images"]
        )
        assert any(img.get("source_type") == "NANO_BANANA_HERO" for img in cat_after_purge["images"])
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


def test_v16_ui_pptx_parity_transparent_emblems_and_progress_placement(tmp_path):
    """Verifies:
    1) 1:1 content & visual parity between in-app slide preview and exported .pptx on Slide 2 (Triage Matrix headers, bullets[0..2], 4th Curriculum Scope card, top/left accent bars, and single-line 🛡️ Guide to Safe Scouting bar).
    2) All 135 Merit Badge emblems in assets/badge_emblems/ are RGBA PNGs with transparent exterior backgrounds (alpha == 0).
    3) Beautification Tier dropdown uses 'Warm Cream + Hero Graphics' and 'Dark Slate + Hero Graphics' with zero 'NotebookLM' references.
    4) 'Research & Generation Progress' (#trace-progress-card) resides in #storyboard-left-col with #slide-filmstrip-list toggled hidden during generation and shown after renderFilmstrip.
    """
    from pathlib import Path
    from PIL import Image
    from pptx import Presentation

    client = TestClient(app)
    html = client.get("/").text
    app_js = Path("ui/app.js").read_text(encoding="utf-8")

    # 1. Verify dropdown labels, official BSA logo, 144 badges subhead & absence of NotebookLM / per-deck cost
    assert "Warm Cream — Pamphlet + AI Visuals" in html
    assert "Dark Slate — Pamphlet + AI Visuals" in html
    assert "Crisp White — Pamphlet Figures Only" in html
    assert "/assets/bsa_logo.png" in html
    assert "All 144 Official Merit Badges &bull; Teaching Slide Decks &amp; Printable Scout Workbooks" in html
    assert "NotebookLM" not in html

    # 2. Verify #trace-progress-card placement inside #storyboard-left-col
    assert 'id="storyboard-left-col"' in html
    left_col_idx = html.index('id="storyboard-left-col"')
    filmstrip_idx = html.index('id="slide-filmstrip-list"')
    trace_idx = html.index('id="trace-progress-card"')
    stage_idx = html.index('class="m3-slide-canvas-wrapper"')
    assert left_col_idx < filmstrip_idx < trace_idx < stage_idx
    assert 'filmstripEl.classList.add("hidden");' in app_js
    assert 'list.classList.remove("hidden");' in app_js

    # 3. Verify transparent RGBA background on Merit Badge emblems
    for badge_slug in ("first_aid", "camping", "weather", "lifesaving"):
        emblem_path = Path("assets/badge_emblems") / f"{badge_slug}.png"
        assert emblem_path.exists()
        with Image.open(emblem_path) as im:
            assert im.mode == "RGBA"
            assert im.getpixel((0, 0))[3] == 0
            assert im.getpixel((im.width - 1, im.height - 1))[3] == 0

    # 4. Verify First Aid BEAUTIFIED & STUDIO .pptx exports match in-app preview on Slide 2 & Slide 3 with 0 AABB overlaps
    for tier in ("BEAUTIFIED", "STUDIO"):
        out_pptx = os.path.join(tmp_path, f"First_Aid_{tier}_Parity.pptx")
        res = run_merit_badge_workflow(
            badge_name="First Aid",
            depth_mode="Standard Deck",
            beautification_tier=tier,
            output_path=out_pptx,
        )
        assert res["status"] == "SUCCESS"
        conf = check_pptx_conformance(res["output_path"])
        assert conf["passed"] is True, f"{tier} conformance failed: {conf['issues']}"
        assert conf["aabb_overlap_count"] == 0

        prs = Presentation(res["output_path"])
        slide2_texts = "\n".join(
            s.text_frame.text for s in prs.slides[1].shapes if s.has_text_frame and s.text_frame.text.strip()
        )
        assert "Discussion & Core Theory" in slide2_texts
        assert "Hands-On Skill Demonstrations" in slide2_texts
        assert "Field & Home Prerequisites" in slide2_texts
        assert "Knowledge & Concepts" not in slide2_texts
        assert "Req 2 - Preparing for First Aid Emergencies" in slide2_texts
        assert "📍 Curriculum Scope" in slide2_texts
        assert "🛡️ Guide to Safe Scouting" in slide2_texts

        # Verify layered crescent top accent shapes on Slide 2
        slide2_shape_names = [s.name for s in prs.slides[1].shapes]
        assert any(name.startswith("CardAccent_Top_") for name in slide2_shape_names)

        # Verify Slide 3 clean visual caption (no "🍌 Hero Illustration:" prefix), right visual frame, and 2-line 01-04 cards + pill badges
        slide3_texts = "\n".join(
            s.text_frame.text for s in prs.slides[2].shapes if s.has_text_frame and s.text_frame.text.strip()
        )
        assert "Hero Illustration:" not in slide3_texts
        assert "Requirement 1:" in slide3_texts
        assert "01  " in slide3_texts
        assert "[01]" not in slide3_texts
        slide3_shape_names = [s.name for s in prs.slides[2].shapes]
        assert any(name.startswith("CardAccent_RightVisualFrame") for name in slide3_shape_names)
        assert any(name.startswith("CardAccent_Left_") for name in slide3_shape_names)
        assert any(name.startswith("CardAccent_StepPill_") for name in slide3_shape_names)

    # 5. Verify _concise_card_body condenses long pamphlet paragraphs without ellipsis
    from src.tools.pptx_builder import _concise_card_body
    long_sentence = (
        "Have current knowledge of all first-aid requirements for Tenderfoot, Second Class, "
        "and First Class ranks, which removes hesitation during a real medical emergency in the field."
    )
    concise = _concise_card_body(long_sentence, max_words=18, max_chars=125)
    assert "..." not in concise
    assert "…" not in concise
    assert len(concise.split()) <= 18
    assert len(concise) <= 130

    # 6. Verify Scout Slide Construction Animation Stage & 14 Compressed Storyboard Frames
    assert 'id="slide-construction-stage"' in html
    assert 'id="construction-badge-emblem-overlay"' in html
    assert "showConstructionAnimationStage" in app_js
    assert "hideConstructionAnimationStage" in app_js
    anim_dir = Path("assets/construction_anim")
    assert anim_dir.is_dir()
    anim_files = list(anim_dir.glob("*.jpg"))
    assert len(anim_files) == 14
    for af in anim_files:
        assert 15_000 < af.stat().st_size < 150_000, f"Unexpected size for {af.name}: {af.stat().st_size}"


def test_phase1_phase2_phase3_counselor_ux_and_features():
    """Verifies Phase 1 (Layout & IA), Phase 2 (Ease-of-Use Polish), and Phase 3 (All 6 BSA Counselor Features F1–F6)."""
    from pathlib import Path

    client = TestClient(app)
    html = client.get("/").text
    css = Path("ui/styles.css").read_text(encoding="utf-8")
    app_js = Path("ui/app.js").read_text(encoding="utf-8")

    # 1. Phase 1 Layout & IA checks (16:9 stage, collapsible sidebars, 3-Tab Under-Stage Drawer, Top Counselor Profile Chip)
    assert 'id="btn-toggle-sidebar"' in html
    assert 'id="btn-toggle-filmstrip"' in html
    assert 'id="top-counselor-profile-chip"' in html
    assert 'id="counselor-profile-accordion"' in html
    assert 'id="understage-drawer"' in html
    assert 'id="slide-quick-edit-card"' in html
    assert "aspect-ratio: 16 / 9;" in css
    assert ".m3-workbench-grid.sidebar-collapsed" in css
    assert ".m3-storyboard-layout.filmstrip-collapsed" in css

    # 2. Phase 2 Ease-of-Use checks (Dirty Settings Banner, Requirement Quick-Jump Bar, Filmstrip Search, Fullscreen Mode)
    assert 'id="deck-dirty-banner"' in html
    assert 'id="req-quick-jump-bar"' in html
    assert 'id="filmstrip-search-input"' in html
    assert 'id="btn-present-fullscreen"' in html
    assert 'id="fullscreen-hud-bar"' in html
    assert "markDeckConfigDirty" in app_js
    assert "renderRequirementJumpBar" in app_js
    assert "data-jump-slide-idx" in app_js

    # 3. Phase 3 Feature F1 (Interactive Quiz Reveal) & F2 (Click-to-Jump Requirement Cards)
    assert "btn-reveal-quiz-answer" in app_js
    assert "m3-req-jump-action-btn" in app_js

    # 4. Phase 3 Feature F3 (Multi-Format Session Pacing Selector & POST /api/studiokit/agenda across all 4 schedules)
    assert 'id="studiokit-schedule-select"' in html
    for sched in (
        "3 Troop Meetings (60-Min)",
        "Summer Camp Week (4x50-Min Mon-Thu + Fri Sign-Off)",
        "Saturday Merit Badge Clinic (3-Hr Block)",
        "Weekend Campout Practicum",
    ):
        resp = client.post(
            "/api/studiokit/agenda",
            json={
                "badge_name": "First Aid",
                "schedule_type": sched,
                "counselor_name": "Eric Clayberg",
                "troop_affiliation": "Troop 19, Middleton MA",
                "location_or_zip": "01949",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert data["agenda"]["schedule_type"] == sched
        assert len(data["agenda"]["sessions"]) >= 3
        assert sched in data["agenda"]["markdown_content"]

    # 5. Phase 3 Feature F4 (One-Click Copy, Email/Gmail Draft, and Print-Ready Handouts)
    for btn_id in (
        "btn-copy-workbook",
        "btn-print-workbook",
        "btn-copy-agenda",
        "btn-print-agenda",
        "btn-download-agenda-md",
        "btn-copy-letter",
        "btn-mailto-letter",
        "btn-gmail-letter",
        "btn-print-letter",
        "btn-download-letter-md",
    ):
        assert f'id="{btn_id}"' in html
    assert "@media print" in css

    # 6. Phase 3 Feature F5 (Master Quartermaster Gear Checklist with Patrol Multiplier)
    assert 'id="studiokit-gear-checklist-card"' in html
    assert 'id="gear-patrol-size-select"' in html
    assert "renderQuartermasterGearChecklist" in app_js

    # 7. Phase 3 Feature F6 (Patrol Blue Card #34124 & Scoutbook Plus Sign-Off Matrix + CSV Export)
    assert 'id="bluecard-tracker-card"' in html
    assert 'id="btn-bluecard-export-csv"' in html
    assert "renderBlueCardTracker" in app_js
    assert "exportBlueCardCsv" in app_js

    # 8. Verify Quick Slide Text Editor persistence in POST /api/slide/regenerate
    wf = client.post(
        "/api/workflow/run",
        json={"badge_name": "First Aid", "depth_mode": "Standard Deck", "beautification_tier": "STANDARD"},
    ).json()
    slide3 = dict(wf["storyboard"]["slides"][2])
    slide3["title"] = "Custom Counselor Edited Title — Req 1"
    slide3["bullet_points"] = ["Custom Bullet Alpha", "Custom Bullet Beta"]
    regen = client.post(
        "/api/slide/regenerate",
        json={
            "badge_name": "First Aid",
            "slide_index": 2,
            "new_archetype": slide3["archetype"],
            "new_visual_theme": "MODERN_CARDS",
            "new_accent_palette": "NAVY_GOLD",
            "visual_source_mode": "keep",
            "slide_data": slide3,
        },
    ).json()
    assert regen["status"] == "SUCCESS"
    assert regen["updated_slide"]["title"] == "Custom Counselor Edited Title — Req 1"
    assert regen["updated_slide"]["bullet_points"] == ["Custom Bullet Alpha", "Custom Bullet Beta"]

    # 9. Verify the 7 UI/UX polish & interaction fixes (horizontal KPI banner, Show/Hide Setup toggle, Fullscreen stage wrapper, Co-Design bar layout, Email/Gmail buttons, Gear Copy/Print buttons, and 2D Camp Pioneering emblem centering)
    assert ".m3-hero-kpis {\n  display: flex;\n  flex-direction: row;" in css
    assert 'id="slide-stage-wrapper"' in html
    assert "is-presenting-fullscreen" in css
    assert "setPresentationFullscreenMode" in app_js
    assert "Show Setup" in app_js and "Hide Setup" in app_js
    assert "Surgical Single-Slide Regeneration" not in html
    assert 'class="m3-codesign-image-controls"' in html
    assert "✉️ Draft in Email App" in html
    assert "📨 Compose in Gmail" in html
    assert 'getElementById("btn-mailto-letter")' in app_js
    assert 'getElementById("btn-gmail-letter")' in app_js
    assert 'getElementById("btn-copy-gear-list")' in app_js
    assert 'getElementById("btn-print-gear-list")' in app_js
    assert 'getElementById("studiokit-gear-checklist-grid")' in app_js
    assert 'left: "87.12%", top: "22.58%", width: "12.2%"' in app_js


def test_v21_full_143_badge_requirements_and_benchmark_completeness():
    """Verifies:
    1) All 143 Merit Badges are scraped and stored in `data/merit_badge_requirements/<slug>.json` with `_index.json`.
    2) `First Aid` contains all 15 official top-level requirements (`1..15`) and 82 sub-requirements (`1a..15c`).
    3) `BENCHMARK_BADGES` contains all 18 Eagle-Required badges + 8 elective benchmark badges (`26` total).
    4) All 72 audited decks (`26 Benchmark + 10 Random` across Deep Dive and Troop Meeting modes) pass 100% of requirement, sub-requirement, visual conformance, text hygiene, and speaker note checks.
    """
    import json
    from src.tools.requirements_scraper import REQUIREMENTS_DIR, load_badge_requirements_json
    from src.tools.scouting_scraper import BENCHMARK_BADGES, is_eagle_required

    index_path = REQUIREMENTS_DIR / "_index.json"
    assert index_path.exists()
    index_data = json.loads(index_path.read_text(encoding="utf-8"))
    assert index_data["total_badges"] == 143
    assert index_data["eagle_required_count"] == 18

    fa_json = load_badge_requirements_json("First Aid")
    assert fa_json is not None
    assert fa_json["requirements_count"] == 15
    assert fa_json["sub_requirements_total"] == 82

    assert len(BENCHMARK_BADGES) == 26
    assert sum(1 for b in BENCHMARK_BADGES if is_eagle_required(b)) == 18

    audit_report_path = REQUIREMENTS_DIR / "_deck_audit_and_cost_report.json"
    assert audit_report_path.exists()
    audit_report = json.loads(audit_report_path.read_text(encoding="utf-8"))
    assert audit_report["total_decks_audited"] == 72
    assert audit_report["all_decks_passed"] is True


def test_v22_slide_image_choices_and_option_c_pill_switcher(tmp_path):
    """Verifies Option C Interactive Slide Image Pill Switcher:
    1) `seed_badge_image_catalog_from_storyboard` populates `slide['slide_image_choices']` with
       slide-scoped primary and Vision-verified alternate pamphlet figures (each with a full `caption`).
    2) Requirement intro slides with a single Nano Banana hero graphic have 1 choice (`len == 1`),
       while requirement topic slides with Vision-verified pamphlet alternates have `2+` choices (`len >= 2`).
    3) The UI (`ui/index.html`, `ui/styles.css`, `ui/app.js`) exposes the Option C hybrid pill and
       floating thumbnail & caption popover (`#stage-visual-pill-popover`).
    """
    from pathlib import Path

    out_pptx = os.path.join(tmp_path, "First_Aid_Option_C_Pill.pptx")
    result = run_merit_badge_workflow(
        badge_name="First Aid",
        depth_mode="Standard Troop Meeting Deck",
        output_path=out_pptx,
    )
    assert result["status"] == "SUCCESS"
    slides = result["storyboard"]["slides"]
    assert len(slides) > 0

    slides_with_choices = [s for s in slides if isinstance(s.get("slide_image_choices"), list) and len(s["slide_image_choices"]) > 0]
    assert len(slides_with_choices) > 0, "Expected slides to include populated slide_image_choices"

    multi_choice_slides = [s for s in slides_with_choices if len(s["slide_image_choices"]) >= 2]
    assert len(multi_choice_slides) > 0, "Expected First Aid slides with Vision-verified pamphlet alternates to have 2+ slide_image_choices"

    for s in multi_choice_slides:
        for choice in s["slide_image_choices"]:
            assert choice.get("caption") or choice.get("description"), "Every slide_image_choices entry must carry a caption"
            assert choice.get("image_path"), "Every slide_image_choices entry must carry an image_path"

    repo_root = Path(__file__).resolve().parents[1]
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_css = (repo_root / "ui" / "styles.css").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")

    assert 'id="stage-visual-pill-popover"' in ui_html
    assert ".m3-stage-visual-pill" in ui_css
    assert ".m3-visual-pill-popover" in ui_css
    assert "renderStageVisualPillAndPopover" in ui_js
    assert "cycleSlideImageChoice" in ui_js
    assert "selectSlideImageChoice" in ui_js


def test_v23_plan2_and_plan3_ui_counselor_and_superuser_admin():
    """Verifies Plan 2 & Plan 3 enhancements:
    1) Zero-PII Super-User Admin Console endpoints (`/api/v1/admin/session`, `/api/v1/admin/catalog/images`,
       `/api/v1/admin/telemetry/image-swap`, `/api/v1/admin/telemetry/summary`, `/api/v1/admin/diagnostics/assets`,
       `/api/v1/admin/circuit-breakers/reset`).
    2) Strict Zero-PII scrubbing (`scrub_pii_dict` strips `counselor_name`, `email_address`, `phone_number`,
       `troop_affiliation`, `location_or_zip`, `ip`, `user_agent`).
    3) Unified 51-jurisdiction regional grounding in `resolve_counselor_location()` across all 50 states + D.C.
    4) Counselor UI enhancements (Dual-Window Presenter View, Live Pacing Timer, Interactive Quiz Reveal,
       Patrol Rotator, Pocket Cue Cards, Keyboard Shortcuts modal, and Super-User Admin Console panel).
    """
    from pathlib import Path
    from fastapi.testclient import TestClient
    from src.server import app
    from src.observability.telemetry_store import scrub_pii_dict
    from src.agents.researcher import resolve_counselor_location

    # 1. Verify Zero-PII scrubber strips all forbidden keys
    dirty_payload = {
        "badge_name": "First Aid",
        "req_number": "1a",
        "counselor_name": "John Doe",
        "email_address": "john@example.com",
        "phone_number": "555-123-4567",
        "troop_affiliation": "Troop 999",
        "location_or_zip": "01949",
        "ip": "192.168.1.1",
        "user_agent": "Mozilla/5.0",
    }
    clean_payload = scrub_pii_dict(dirty_payload)
    assert clean_payload.get("badge_name") == "First Aid"
    for pii_key in ("counselor_name", "email_address", "phone_number", "troop_affiliation", "location_or_zip", "ip", "user_agent"):
        assert pii_key not in clean_payload

    # 2. Verify 51-jurisdiction local grounding resolution (including non-MA states like AK, HI, WY)
    for st_query, expected_code in [("Anchorage, AK", "AK"), ("Honolulu, HI", "HI"), ("Cheyenne, WY", "WY")]:
        loc = resolve_counselor_location(st_query)
        assert loc["state_code"] == expected_code
        assert "NOAA NWS" in loc["nws_office"]

    # 3. Verify Super-User Admin Console endpoints & A2A card redaction
    client = TestClient(app)
    agent_card = client.get("/.well-known/agent.json").json()
    assert agent_card["version"] == "3.1.0"
    assert "clayberg" not in agent_card["url"]

    sess_res = client.get("/api/v1/admin/session").json()
    assert sess_res["status"] == "SUCCESS"
    assert sess_res["is_admin"] is True

    cat_res = client.get("/api/v1/admin/catalog/images?badge_name=First+Aid&req_number=2").json()
    assert cat_res["status"] == "SUCCESS"
    assert len(cat_res["images"]) >= 1

    swap_res = client.post(
        "/api/v1/admin/telemetry/image-swap",
        json={
            "badge_name": "First Aid",
            "req_number": "2",
            "event_type": "counselor_visual_swap",
            "from_image_id": "first_aid_p12_img1.png",
            "to_image_id": "first_aid_p14_img2.png",
        },
    ).json()
    assert swap_res["status"] == "RECORDED"
    assert swap_res["zero_pii"] is True

    summary_res = client.get("/api/v1/admin/telemetry/summary").json()
    assert summary_res["status"] == "SUCCESS"
    assert "zero_pii_telemetry" in summary_res

    diag_res = client.get("/api/v1/admin/diagnostics/assets").json()
    assert diag_res["status"] == "SUCCESS"
    assert diag_res["total_badges"] == 144

    cb_res = client.post("/api/v1/admin/circuit-breakers/reset").json()
    assert cb_res["status"] == "RESET"

    # 4. Verify UI hooks for Plan 3 Counselor & Admin features
    repo_root = Path(__file__).resolve().parents[1]
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")
    assert 'id="panel-admin"' in ui_html
    assert 'id="admin-unlock-modal"' in ui_html
    assert 'id="keyboard-shortcuts-modal"' in ui_html
    assert "syncPresenterViewWindow" in ui_js
    assert "stage-left-cards" in ui_js


def test_v24_plan5_complete_plan3_audit_and_remediation():
    """Verifies Plan 5 completion of all Plan 3 UI/UX, Counselor, and Super-User Admin Console features."""
    from pathlib import Path
    from fastapi.testclient import TestClient
    from src.server import app

    client = TestClient(app)

    # 1. Verify Telemetry 24h / 7d / All-Time windows, p50/p95/p99 histograms, and FinOps Spend vs. Saved
    summary_res = client.get("/api/v1/admin/telemetry/summary").json()
    assert summary_res["status"] == "SUCCESS"
    tel = summary_res["zero_pii_telemetry"]
    assert "runs_24h" in tel
    assert "runs_7d" in tel
    assert "runs_all_time" in tel
    assert "total_estimated_saved_usd" in tel
    assert "tier_breakdown" in tel
    assert "depth_breakdown" in tel
    assert "p99" in tel["latency_warm_ms"]
    assert isinstance(tel["latency_warm_ms"].get("histogram"), list)
    assert len(tel["latency_warm_ms"]["histogram"]) == 5

    # 2. Verify Asset Diagnostics includes 5th column (pdf_and_index_present), prompt_manifest, and compliance_audit_events
    diag_res = client.get("/api/v1/admin/diagnostics/assets").json()
    assert diag_res["status"] == "SUCCESS"
    assert diag_res["total_badges"] == 144
    assert diag_res["covers_present"] == 144
    assert diag_res["emblems_present"] == 144
    assert diag_res["pdfs_indexed_present"] == 144
    assert isinstance(diag_res.get("prompt_manifest"), list)
    assert len(diag_res["prompt_manifest"]) == 6
    assert all(p.get("verified") is True for p in diag_res["prompt_manifest"])

    # 3. Verify 1-Click Maintenance endpoints
    purge_res = client.post("/api/v1/admin/maintenance/purge-temp-cache").json()
    assert purge_res["status"] == "SUCCESS"
    repair_res = client.post("/api/v1/admin/maintenance/repair-covers").json()
    assert repair_res["status"] == "SUCCESS"
    assert repair_res["covers_verified"] == 144
    snap_res = client.get("/api/v1/admin/maintenance/snapshot").json()
    assert snap_res["status"] == "SUCCESS"
    assert snap_res["zero_pii_guaranteed"] is True

    # 4. Verify Slide Deck Customizer endpoint (insert, toggle_hide, move_up, move_down, hide_prereqs)
    sample_slides = [
        {"title": "Slide A", "req_number": "1", "archetype": "CONCEPT_TEXT_SLIDE", "bullet_points": ["Point 1"]},
        {"title": "Slide B", "req_number": "2b", "archetype": "SPLIT_VISUAL_EXPLAINER", "bullet_points": ["Point 2"]},
    ]
    cust_res = client.post(
        "/api/slide/deck-customize",
        json={
            "badge_name": "First Aid",
            "action": "insert",
            "slide_index": 0,
            "custom_slide": {
                "title": "Local Camp Emergency Assembly",
                "req_number": "Local",
                "archetype": "CONCEPT_TEXT_SLIDE",
                "bullet_points": ["Muster at Waterfront Flagpole"],
            },
            "storyboard_slides": sample_slides,
        },
    ).json()
    assert cust_res["status"] == "SUCCESS"
    assert len(cust_res["storyboard_slides"]) == 3
    assert cust_res["storyboard_slides"][1]["is_custom_slide"] is True

    # 5. Verify UI HTML & JS contain all Plan 3 / Plan 5 controls
    repo_root = Path(__file__).resolve().parents[1]
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")
    for required_id in (
        'id="btn-fs-toggle-notes"',
        'id="fullscreen-teleprompter-drawer"',
        'id="stage-patrol-scoreboard"',
        'id="btn-filter-quiz-slides"',
        'id="btn-insert-custom-slide"',
        'id="insert-custom-slide-modal"',
        'id="btn-toggle-hide-slide"',
        'id="btn-toggle-hide-prereq-slides"',
        'id="btn-bluecard-import-csv"',
        'id="btn-bluecard-print-3panel"',
        'id="btn-top-print-field-qr-handout"',
        'id="patch-gallery-modal"',
        'id="btn-toggle-sunlight-mode"',
        'id="btn-admin-replace-upload"',
        'id="btn-admin-regenerate-inplace"',
        'id="admin-prompt-manifest-table-body"',
        'id="admin-guardrail-audit-table-body"',
        'id="btn-admin-maint-purge-cache"',
        'id="btn-admin-maint-repair-covers"',
        'id="btn-admin-maint-refresh-senators"',
        'id="btn-admin-maint-download-snapshot"',
    ):
        assert required_id in ui_html, f"Missing {required_id} in ui/index.html"
    assert "printThreePanelBlueCards" in ui_js
    assert "printPocketFieldQrHandout" in ui_js
    assert "customizeActiveSlideDeck" in ui_js


def test_v25_conversational_teaching_notes_and_polish_endpoint(tmp_path) -> None:
    """Verify Plan 6 Option C Hybrid Conversational Counselor Teaching Notes & /api/v1/slide/polish-notes."""
    from pathlib import Path
    from src.server import app

    client = TestClient(app)

    # 1. Generate First Aid Deep Dive deck and verify Layer 1 Conversational First-Person Script Compiler
    out_pptx = os.path.join(tmp_path, "First_Aid_v25_Conversational_Notes.pptx")
    wf_res = run_merit_badge_workflow(
        badge_name="First Aid",
        depth_mode="Deep Dive / Camp School Deck",
        output_path=out_pptx,
    )
    assert wf_res["status"] == "SUCCESS"
    slides = wf_res["storyboard"]["slides"]
    assert len(slides) >= 45

    banned_meta_phrases = (
        "Teach the core concepts on",
        "Walk Scouts through the",
        "Introduce First Aid Requirement",
        "including common mistakes new Scouts make",
        "thekit",
        "personunder",
        "andallowed",
        "Theindividual",
    )

    stage_cue_slides = 0
    expected_answer_slides = 0

    for idx, s in enumerate(slides):
        notes = str(s.get("presenter_notes") or "")
        assert "[SAY]" in notes, f"Slide {idx + 2} missing [SAY]"
        assert "—" not in notes and "–" not in notes and "..." not in notes, (
            f"Slide {idx + 2} presenter_notes contains em-dash, en-dash, or ellipsis"
        )
        for banned in banned_meta_phrases:
            assert banned not in notes, f"Slide {idx + 2} still contains banned phrase or kerning glitch: {banned}"

        if any(cue in notes for cue in ("[Point to", "[Gesture to", "[Trace across", "[Hold up", "[Pause")):
            stage_cue_slides += 1
        if "[ASK SCOUTS]" in notes:
            assert "[Expected Answer:" in notes, f"Slide {idx + 2} [ASK SCOUTS] missing [Expected Answer: ...]"
            expected_answer_slides += 1

    assert stage_cue_slides >= len(slides) - 2
    assert expected_answer_slides >= 20

    # 2. Verify POST /api/slide/regenerate dynamically synchronizes presenter_notes when visual caption changes
    target_slide = dict(slides[2])
    regen_res = client.post(
        "/api/slide/regenerate",
        json={
            "badge_name": "First Aid",
            "slide_index": 2,
            "new_archetype": "SPLIT_VISUAL_EXPLAINER",
            "visual_source_mode": "none",
            "slide_data": target_slide,
        },
    ).json()
    assert regen_res["status"] == "SUCCESS"
    assert "[SAY]" in regen_res.get("updated_presenter_notes", "")
    assert "[Gesture to the right-hand figure:" not in regen_res.get("updated_presenter_notes", "")

    # 3. Verify Option C Layer 2: POST /api/v1/slide/polish-notes + SQLite cache hit on second call
    polish_1 = client.post(
        "/api/v1/slide/polish-notes",
        json={
            "badge_name": "First Aid",
            "slide_index": 2,
            "slide_data": slides[2],
            "audience_level": "All Scouts (Ages 11-17)",
            "force_refresh": True,
        },
    ).json()
    assert polish_1["status"] == "SUCCESS"
    assert polish_1["cache_hit"] is False
    assert "[SAY]" in polish_1["presenter_notes"]
    assert "[Expected Answer:" in polish_1["presenter_notes"]
    assert polish_1["presenter_notes"] != slides[2].get("presenter_notes")

    polish_2 = client.post(
        "/api/v1/slide/polish-notes",
        json={
            "badge_name": "First Aid",
            "slide_index": 2,
            "slide_data": slides[2],
            "audience_level": "All Scouts (Ages 11-17)",
            "force_refresh": False,
        },
    ).json()
    assert polish_2["status"] == "SUCCESS"
    assert polish_2["cache_hit"] is True
    assert polish_2["presenter_notes"] == polish_1["presenter_notes"]

    # 4. Verify UI elements and stage-cue / expected-answer formatters
    repo_root = Path(__file__).resolve().parents[1]
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")
    assert 'id="btn-ai-polish-notes"' in ui_html
    assert 'id="btn-copy-slide-notes"' in ui_html
    assert 'id="notes-polish-status-pill"' in ui_html
    assert "m3-stage-cue-pill" in ui_js
    assert "m3-expected-answer-box" in ui_js


def test_v26_plan7_emblems_qr_polish_batch_presenter_and_gslides_export(tmp_path) -> None:
    """Verify Plan 7: 144/144 authentic Scout Shop emblems, ISO QR SVG endpoint, batch polish, Presenter Console, and Google Slides export."""
    import json
    from pathlib import Path
    from PIL import Image
    from fastapi.testclient import TestClient
    from src.server import app

    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = repo_root / "assets" / "badge_emblems" / "scoutshop_emblems_manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest) == 144
    assert sum(1 for v in manifest.values() if isinstance(v, dict) and v.get("source") == "scoutshop.org") == 144

    # 1. Verify all 6 previously synthetic emblems are now authentic 400x400 Scout Shop PNGs
    for slug in (
        "automotive_maintenance",
        "citizenship_in_the_community",
        "composite_materials",
        "digital_technology",
        "theater",
        "wilderness_survival",
    ):
        emblem_file = repo_root / "assets" / "badge_emblems" / f"{slug}.png"
        assert emblem_file.exists(), f"Missing emblem {slug}.png"
        assert emblem_file.stat().st_size > 100_000, f"Emblem {slug}.png looks like a tiny synthetic placeholder"
        with Image.open(emblem_file) as img:
            assert 380 <= img.size[0] <= 400 and 380 <= img.size[1] <= 400, f"Expected ~400x400 Scout Shop emblem for {slug}, got {img.size}"

    client = TestClient(app)

    # 2. Verify ISO/IEC 18004 Scannable QR Code SVG endpoint
    qr_resp = client.get(
        "/api/v1/qr.svg",
        params={"url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/First%20Aid.pdf"},
    )
    assert qr_resp.status_code == 200
    assert "image/svg+xml" in qr_resp.headers.get("content-type", "")
    assert "<svg" in qr_resp.text and 'shape-rendering="crispEdges"' in qr_resp.text

    # 3. Verify Batch Deck Polish endpoint (POST /api/v1/slide/polish-notes-batch)
    sample_slides = [
        {
            "title": "Requirement 1 — Scene Triage & Safety",
            "req_number": "1",
            "archetype": "SPLIT_VISUAL_EXPLAINER",
            "bullet_points": [
                "Scene Assessment: Check for downed wires, traffic, fire, or unstable terrain before approaching.",
                "Universal Precautions: Put on nitrile exam gloves and eye protection before touching blood.",
            ],
            "visual_caption": "Wilderness scene safety check with nitrile gloves",
            "presenter_notes": "[SAY] Let's cover Requirement 1.\n[DEMONSTRATE] Show gloves.\n[ASK SCOUTS] Why check the scene? [Expected Answer: To avoid becoming a second victim.]",
        },
        {
            "title": "Requirement 2 — Personal First-Aid Kit",
            "req_number": "2a",
            "archetype": "SOCRATIC_CHECKPOINT_QUIZ",
            "bullet_points": [
                "Gauze & Bandages: Carry sterile 3x3 gauze pads, adhesive bandages, and roller gauze.",
                "Blister Prevention: Pack moleskin and medical tape for trail hotspots.",
            ],
            "presenter_notes": "[SAY] Let's quiz the patrol on Requirement 2a.\n[DEMONSTRATE] Open kit.\n[ASK SCOUTS] What stops blisters? [Expected Answer: Moleskin applied at the first sign of a hot spot.]",
        },
    ]
    batch_resp = client.post(
        "/api/v1/slide/polish-notes-batch",
        json={
            "badge_name": "First Aid",
            "storyboard_slides": sample_slides,
            "audience_level": "All Scouts (Ages 11-17)",
            "force_refresh": True,
        },
    )
    assert batch_resp.status_code == 200
    batch_data = batch_resp.json()
    assert batch_data["status"] == "SUCCESS"
    assert batch_data["polished_count"] == 2
    for polished_slide in batch_data["slides"]:
        p_notes = polished_slide["presenter_notes"]
        assert "[SAY]" in p_notes and "[DEMONSTRATE]" in p_notes and "[ASK SCOUTS]" in p_notes
        assert "[Expected Answer:" in p_notes
        assert "—" not in p_notes and "–" not in p_notes

    # 4. Verify Direct Google Slides Export endpoint (POST /api/v1/slide/export-gslides)
    gslides_resp = client.post(
        "/api/v1/slide/export-gslides",
        json={
            "badge_name": "First Aid",
            "storyboard_slides": batch_data["slides"],
            "output_path": str(tmp_path / "First_Aid_GSlides_Test.pptx"),
        },
    )
    assert gslides_resp.status_code == 200
    gslides_data = gslides_resp.json()
    assert gslides_data["status"] in ("SUCCESS", "AUTH_GUIDED_IMPORT")
    assert "pptx_download_url" in gslides_data

    # 5. Verify Plan 7 UI & CSS Wiring
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_css = (repo_root / "ui" / "styles.css").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")

    assert 'id="btn-ai-polish-deck"' in ui_html
    assert 'id="deck-export-split-group"' in ui_html
    assert 'id="btn-deck-export-caret"' in ui_html
    assert 'id="deck-export-mode-menu"' in ui_html
    assert 'id="stage-presenter-console-dock"' in ui_html
    assert 'id="patch-gallery-filter-select"' in ui_html
    assert 'id="patch-gallery-category-select"' in ui_html
    assert "Locked Sticky Column Headers" not in ui_html
    assert ".m3-sticky-matrix-table thead th" in ui_css
    assert "is-presenter-console-active" in ui_css
    assert "togglePresenterConsoleMode" in ui_js
    assert "exportActiveDeckToGoogleSlides" in ui_js
    assert "scrollActiveFilmstripThumbIntoView" in ui_js
    assert "encodeIsoQrMatrixJs" in ui_js


def test_v25_plan9_ui_emblem_qr_presenter_and_table_fixes() -> None:
    """Verifies all 7 Plan 9 UI/UX, emblem normalization, QR logo, Presenter View, and table header fixes."""
    from pathlib import Path
    from fastapi.testclient import TestClient
    from PIL import Image
    from src.config import OFFICIAL_BSA_MERIT_BADGES_CATALOG, _badge_slug
    from src.server import app
    from src.tools.qr_generator import _FORMAT_BITS_M, _QR_VERSION_SPECS_M, render_qr_svg

    repo_root = Path(__file__).resolve().parents[1]
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_css = (repo_root / "ui" / "styles.css").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")

    # 1. Fix 1: Visual Merit Badge Patch Gallery Zero State ("ALL" case-insensitive match)
    assert 'selectedCat.toLowerCase() !== "all"' in ui_js
    assert '<option value="ALL">All Categories</option>' in ui_html

    # 2. Fix 2: All 144 Merit Badge Emblems present, 400x400 RGBA, normalized >= 0.94 fill ratio, and cache-busted
    emblems_dir = repo_root / "assets" / "badge_emblems"
    target_check_slugs = [
        "theater",
        "citizenship_in_the_community",
        "wilderness_survival",
        "composite_materials",
        "digital_technology",
        "automotive_maintenance",
        "whitewater",
        "leatherwork",
    ]
    for item in OFFICIAL_BSA_MERIT_BADGES_CATALOG:
        slug = _badge_slug(item["badge_name"]).replace("-", "_")
        emblem_path = emblems_dir / f"{slug}.png"
        assert emblem_path.exists(), f"Missing emblem for {slug}"
        with Image.open(emblem_path) as im:
            assert im.size == (400, 400), f"{slug} size is {im.size}"
            if slug in target_check_slugs:
                rgba = im.convert("RGBA")
                alpha_bbox = rgba.getchannel("A").getbbox()
                assert alpha_bbox is not None
                bw = alpha_bbox[2] - alpha_bbox[0]
                bh = alpha_bbox[3] - alpha_bbox[1]
                fill_ratio = max(bw, bh) / 400.0
                assert fill_ratio >= 0.94, f"{slug} fill_ratio={fill_ratio:.3f} < 0.94"

    client = TestClient(app)
    emblem_resp = client.get("/assets/badge_emblems/theater.png")
    assert emblem_resp.status_code == 200
    assert "max-age=0" in emblem_resp.headers.get("cache-control", "")
    assert "must-revalidate" in emblem_resp.headers.get("cache-control", "")
    assert "?v=20261016c" in ui_js

    # 3. Fix 3: Presenter View opens to the right of #widescreen-slide-stage via #slide-and-presenter-row
    assert 'id="slide-and-presenter-row"' in ui_html
    assert "#slide-stage-wrapper.is-presenter-console-active .m3-slide-and-presenter-row" in ui_css
    assert "minmax(0, 1.15fr) minmax(0, 0.85fr)" in ui_css
    assert "minmax(0, 1.15fr) minmax(0, 0.85fr)" in ui_js

    # 4. Fix 4: Jump to Patrol Blue Card (#34124) Tracker button at top of Requirements & Blue Cards page
    assert 'id="btn-jump-to-bluecard-tracker"' in ui_html
    assert 'document.getElementById("btn-jump-to-bluecard-tracker")' in ui_js
    assert 'document.getElementById("bluecard-tracker-card")' in ui_js

    # 5. Fix 5: Scouts BSA Logo embedded in center of Level-M QR codes (backend SVG & frontend inline SVG)
    assert len(_QR_VERSION_SPECS_M) == 10
    assert _FORMAT_BITS_M[0] == 0x5412
    qr_svg = render_qr_svg("https://www.scouting.org/merit-badges/first-aid/")
    assert "<image href=\"data:image/png;base64," in qr_svg
    qr_api_resp = client.get("/api/v1/qr.svg?url=https://www.scouting.org/merit-badges/first-aid/")
    assert qr_api_resp.status_code == 200
    assert "<image href=\"data:image/png;base64," in qr_api_resp.text
    assert "QR_VERSION_SPECS_M_JS" in ui_js
    assert "QR_FORMAT_BITS_M_JS" in ui_js
    assert "/assets/bsa_logo.png" in ui_js

    # 6. Fix 6: 6-Stage ADK Pipeline Latency Breakdown column widths prevent text bleeding into histogram
    assert "grid-template-columns:minmax(225px, 245px) minmax(90px, 1fr) auto" in ui_js
    assert "text-overflow:ellipsis" in ui_js

    # 7. Fix 7: Sticky and FinOps table headers have white text on Scouts BSA blue background
    assert ".m3-finops-table thead th," in ui_css
    assert ".m3-sticky-matrix-table thead th," in ui_css
    assert "background: linear-gradient(135deg, #002B5E 0%, #003F87 100%) !important;" in ui_css


def test_v27_ai_polish_slide_and_deck_provenance_and_zero_boilerplate() -> None:
    """Verifies multi-line section parsing, distinct per-slide hooks (zero boilerplate), batch contract keys, and UI prominence."""
    from pathlib import Path
    from fastapi.testclient import TestClient
    from src.server import _parse_multiline_polished_sections, app

    # 1. Verify multi-line section parser preserves multi-paragraph [SAY], [DEMONSTRATE], and [ASK SCOUTS],
    # strips corny camp greetings ("Alright, listen up, future lifesavers"), and normalizes asymmetric *bold**
    sample_llm = (
        "[SAY] Alright, listen up, future lifesavers! When evaluating *Check Airway & Breathing**, start by tilting the head gently.\n"
        "[Point to Card 1: Direct Pressure] Hold sterile gauze firmly over the wound for at least five minutes.\n"
        "[Studio Coaching Cue: Check every buddy pair's glove fit.]\n\n"
        "[DEMONSTRATE] [Step in front of the table]\n"
        "Model applying a roller bandage over the sterile pad without cutting off distal circulation.\n\n"
        "[ASK SCOUTS] What should you do if blood soaks through the first gauze pad?\n"
        "[Expected Answer: Add a second sterile pad directly on top without removing the first pad.]"
    )
    parsed = _parse_multiline_polished_sections(sample_llm)
    assert "[SAY]" in parsed and "[DEMONSTRATE]" in parsed and "[ASK SCOUTS]" in parsed
    assert "Alright, listen up" not in parsed
    assert "future lifesavers" not in parsed
    assert "[SAY] When evaluating **Check Airway & Breathing**" in parsed
    assert "Hold sterile gauze firmly over the wound" in parsed
    assert "[Studio Coaching Cue: Check every buddy pair's glove fit.]" in parsed
    assert "Model applying a roller bandage" in parsed
    assert "[Expected Answer: Add a second sterile pad directly on top without removing the first pad.]" in parsed

    # 2. Verify polishing 5 different slides produces 5 distinct opening hooks and zero old boilerplate
    client = TestClient(app)
    slides = [
        {
            "title": "Requirement 1 — Scene Safety & Triage",
            "req_number": "1",
            "archetype": "SPLIT_VISUAL_EXPLAINER",
            "bullet_points": ["Scene Check: Scan for hazards before approaching.", "Gloves On: Wear nitrile gloves."],
        },
        {
            "title": "Requirement 2 — Personal vs Patrol First-Aid Kits",
            "req_number": "2",
            "archetype": "DIFFERENTIAL_COMPARISON_2COL",
            "bullet_points": ["Personal Kit: Moleskin and bandages.", "Patrol Kit: SAM splint and trauma shears."],
        },
        {
            "title": "Requirement 3 — Severe Bleeding & Tourniquet Sequence",
            "req_number": "3",
            "archetype": "STEP_BY_STEP_PROCEDURE_4CARD",
            "bullet_points": ["Direct Pressure: Press firmly with sterile gauze.", "Windlass Tourniquet: Place 2 inches above wound."],
        },
        {
            "title": "Requirement 4 — Worked Example Injury Log",
            "req_number": "4",
            "archetype": "WORKED_EXAMPLE_TEMPLATE",
            "bullet_points": ["Mechanism: Slip on wet granite trail.", "Treatment: Splinted ankle and buddy carry."],
        },
        {
            "title": "Requirement 5 — Patrol Quiz on Heat Exhaustion vs Heatstroke",
            "req_number": "5",
            "archetype": "SOCRATIC_CHECKPOINT_QUIZ",
            "bullet_points": ["Heat Exhaustion: Cool clammy skin.", "Heatstroke: Hot altered mental state — call 911."],
        },
    ]

    opening_sentences = set()
    for idx, s_obj in enumerate(slides):
        r = client.post(
            "/api/v1/slide/polish-notes",
            json={
                "badge_name": "First Aid",
                "slide_index": idx,
                "slide_data": s_obj,
                "audience_level": "All Scouts (Ages 11-17)",
                "force_refresh": True,
                "variation_seed": 1,
            },
        ).json()
        assert r["status"] == "SUCCESS"
        assert r["polish_source"] in ("GEMINI_FLASH", "PROCEDURAL_STUDIO_POLISH")
        assert r["polish_model_label"] in ("Gemini Flash", "Studio Narrative Polish")
        notes = r["presenter_notes"]
        assert "Let's step out of the classroom for a moment" not in notes
        assert "First, anchor your attention on" not in notes
        assert "Here is where veteran Scouts separate themselves" not in notes
        first_sentence = notes.splitlines()[0].split(".")[0].strip()
        opening_sentences.add(first_sentence)

    assert len(opening_sentences) == len(slides), f"Expected 5 distinct slide openings, got {opening_sentences}"

    # 3. Verify batch polish returns both 'slides' and 'storyboard_slides', 'duration_ms' and 'elapsed_ms', and 'cover_presenter_notes'
    batch_res = client.post(
        "/api/v1/slide/polish-notes-batch",
        json={
            "badge_name": "First Aid",
            "storyboard_slides": slides,
            "audience_level": "All Scouts (Ages 11-17)",
            "force_refresh": True,
        },
    ).json()
    assert batch_res["status"] == "SUCCESS"
    assert batch_res["polished_count"] == 5
    assert len(batch_res["slides"]) == 5
    assert len(batch_res["storyboard_slides"]) == 5
    assert "[SAY]" in batch_res.get("cover_presenter_notes", "")
    assert "duration_ms" in batch_res and "elapsed_ms" in batch_res
    assert batch_res["polish_model_label"] in ("Gemini Flash", "Studio Narrative Polish")

    # 4. Verify UI buttons, restore toggle, live batch counter, thinking_budget=0, and 'Gemini Flash' naming
    repo_root = Path(__file__).resolve().parents[1]
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_css = (repo_root / "ui" / "styles.css").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")
    server_py = (repo_root / "src" / "server.py").read_text(encoding="utf-8")
    assert "m3-btn-ai-polish-slide" in ui_html and ".m3-btn-ai-polish-slide" in ui_css
    assert "m3-btn-ai-polish-deck" in ui_html and ".m3-btn-ai-polish-deck" in ui_css
    assert "m3-grounding-toggle-card" in ui_html and ".m3-grounding-toggle-card" in ui_css
    assert 'id="btn-restore-default-notes"' in ui_html
    assert "syncNotesPolishProvenancePill" in ui_js
    assert "updateBatchCounterUi" in ui_js
    assert "Batch-polishing all ${totalSlides} slides across deck ${counterTag}" in ui_js
    assert "thinking_budget=0" in server_py
    assert "Gemini Flash" in ui_js


def test_v28_plan10_ui_presenter_gslides_finops_and_animation() -> None:
    """Verifies all 8 Plan 10 features: Patch Gallery sticky header, 144-badge Pamphlet Figs & PDF Reqs, Counselor Rating jump button, Google Doc link rewriting, AI Polish FinOps gate, Presenter View buttons/centering, Google Slides account flow, and Frame 4 helicopter hoist cable overlay."""
    from pathlib import Path
    from fastapi.testclient import TestClient
    from PIL import Image
    from scripts.sync_markdown_with_mermaid_to_gdocs import (
        load_companion_gdocs_registry,
        rewrite_internal_md_links_for_gdocs,
    )
    from src.agents.image_studio import get_asset_health_matrix
    from src.server import app

    repo_root = Path(__file__).resolve().parents[1]
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_css = (repo_root / "ui" / "styles.css").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")

    # 1. Request #1: Sticky Header in Visual Merit Badge Patch Gallery (#patch-gallery-modal)
    assert "max-height:88vh; display:flex; flex-direction:column; overflow:hidden; padding:0;" in ui_html
    assert "m3-patch-gallery-sticky-header" in ui_html
    assert "flex:1 1 auto; min-height:0; overflow-y:auto;" in ui_html

    # 2. Request #2: 144-Badge Visual Asset Health Matrix column alignment + true per-badge requirement counts
    matrix = get_asset_health_matrix()
    assert matrix["total_badges"] == 144
    by_badge = {row["badge_name"]: row for row in matrix["rows"]}
    assert by_badge["First Aid"]["indexed_reqs"] == 15
    assert by_badge["Weather"]["indexed_reqs"] == 12
    assert by_badge["Cooking"]["indexed_reqs"] == 7
    assert by_badge["First Aid"]["pamphlet_figures"] >= 10
    assert "<td><strong>${r.pamphlet_figures}</strong> figs</td>" in ui_js
    assert "<td><strong>${r.nano_banana_heroes}</strong> heroes</td>" in ui_js
    assert "<td>${r.pdf_and_index_present !== false ? `✅ (${r.indexed_reqs || 8} Reqs)` : \"⚠️\"}</td>" in ui_js

    # 3. Request #3: "↓ Counselor Rating" Jump Button on Grounded Research Citations & Local Troop References card
    assert 'id="btn-jump-to-counselor-rating"' in ui_html
    assert "↓ Counselor Rating" in ui_html
    assert 'document.getElementById("btn-jump-to-counselor-rating")' in ui_js
    assert 'document.getElementById("studiokit-feedback-card")' in ui_js

    # 4. Request #4: Automatic Markdown-to-Google-Docs cross-link rewriting via docs/gdocs_registry.json
    reg = load_companion_gdocs_registry()
    assert reg["docs/USER_GUIDE.md"] == "1IYMvIW_72EFoA5wr4h1I4mPXyCm0k6RmRbnlv9z5dHo"
    assert reg["docs/ADMIN_GUIDE.md"] == "1jCQclVI2KnO-qJaRqwRHQkVMJ8CDohWjU8u2JT3CJpU"
    sample_ug = "Read the dedicated **[Super-User Admin Guide (`docs/ADMIN_GUIDE.md`)](ADMIN_GUIDE.md)**."
    rewritten_ug = rewrite_internal_md_links_for_gdocs(sample_ug, "docs/USER_GUIDE.md", reg)
    assert "https://docs.google.com/document/d/1jCQclVI2KnO-qJaRqwRHQkVMJ8CDohWjU8u2JT3CJpU/edit" in rewritten_ug
    assert "(ADMIN_GUIDE.md)" not in rewritten_ug

    # 5. Request #5: FinOps Cost Estimate Gate for AI Polish Slide & Polish Entire Deck
    client = TestClient(app)
    est_resp = client.post(
        "/api/v1/slide/estimate-polish-cost",
        json={
            "badge_name": "First Aid",
            "slide_index": 0,
            "slide_data": {"title": "Scene Safety", "req_number": "1", "bullet_points": ["Scan for hazards"]},
            "storyboard_slides": [
                {"title": "Scene Safety", "req_number": "1", "bullet_points": ["Scan for hazards"]},
                {"title": "First Aid Kit", "req_number": "2", "bullet_points": ["21 essential items"]},
            ],
            "audience_level": "All Scouts (Ages 11-17)",
        },
    )
    assert est_resp.status_code == 200
    est_data = est_resp.json()
    assert est_data["status"] == "SUCCESS"
    assert round(est_data["single_slide_cost_usd"], 4) == 0.0008
    assert est_data["total_slides"] == 3  # 2 storyboard slides + 1 cover slide
    assert "deck_uncached_cost_usd" in est_data and "deck_full_repolish_cost_usd" in est_data
    assert 'id="ai-polish-finops-modal"' in ui_html
    assert "openAiPolishFinopsGateModal" in ui_js

    # 6. Request #6: Presenter View buttons, dark-slate glass styling, font scaling, centering, and 2nd Monitor companion popup
    assert 'id="btn-pc-close-console"' in ui_html
    assert 'document.getElementById("btn-pc-close-console")' in ui_js
    assert 'document.getElementById("btn-pc-prev-slide")' in ui_js
    assert 'document.getElementById("btn-pc-next-slide")' in ui_js
    assert 'document.getElementById("btn-pc-font-dec")' in ui_js
    assert 'document.getElementById("btn-pc-font-inc")' in ui_js
    assert "changePresenterFontScale" in ui_js
    assert "hideConstructionAnimationStage()" in ui_js
    assert ".m3-pc-mini-btn" in ui_css
    assert "#btn-pc-prev-slide" in ui_css and "#btn-pc-next-slide" in ui_css

    # 7. Request #7: Open in Google Slides Account Selection & New Browser Tab Flow
    acc_resp = client.get("/api/v1/slide/export-gslides/account-info")
    assert acc_resp.status_code == 200
    acc_data = acc_resp.json()
    assert acc_data["status"] == "SUCCESS"
    assert "detected_account_email" in acc_data
    assert 'id="gslides-export-modal"' in ui_html
    assert "openGoogleSlidesExportModal" in ui_js
    assert "runGoogleSlidesExportAndOpenTab" in ui_js
    assert 'data.status === "SUCCESS" || data.status === "EXPORTED"' in ui_js

    # 8. Request #8: Frame 4 (3D Heavy Equipment) Helicopter Hoist Cable Foreground Overlay
    cable_png = repo_root / "assets" / "construction_anim" / "iso_heavy_4_foreground_cable.png"
    assert cable_png.exists()
    with Image.open(cable_png) as cable_im:
        assert cable_im.size == (960, 540)
        assert cable_im.mode == "RGBA"
        # Ensure non-empty alpha channel where the cable and golden eyelet lug are drawn
        alpha_bbox = cable_im.getchannel("A").getbbox()
        assert alpha_bbox is not None
    assert 'id="construction-foreground-cable-overlay"' in ui_html
    assert "iso_heavy_4_foreground_cable.png" in ui_html
    assert ".m3-construction-foreground-cable" in ui_css
    assert "construction-foreground-cable-overlay" in ui_js


def test_v29_plan11_modals_presenter_docs_viewer_and_readme_clean() -> None:
    """Verifies Plan 11: FinOps & Google Slides modal alignment, Presenter View 3-card layout + fullscreen centering + non-disruptive 2nd Monitor, Footer GitHub link, Option A Documentation Studio Viewer (excluding Capstone & Google Docs), and clean README/docs."""
    from pathlib import Path
    from fastapi.testclient import TestClient
    from src.server import app

    repo_root = Path(__file__).resolve().parents[1]
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_css = (repo_root / "ui" / "styles.css").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")
    readme_md = (repo_root / "README.md").read_text(encoding="utf-8")

    client = TestClient(app)

    # 1. Issue 1: FinOps Cost Estimate Gate Modal lavender & amber cards + single-row pill buttons + Force fresh checkbox
    assert 'id="finops-card-single-slide"' in ui_html
    assert 'id="finops-card-entire-deck"' in ui_html
    assert "OPTION 1 &bull; CURRENT SLIDE ONLY" in ui_html
    assert 'id="finops-deck-option-kicker"' in ui_html
    assert 'id="chk-finops-force-repolish"' in ui_html
    assert 'id="chk-finops-dont-ask-session"' in ui_html
    assert ".m3-finops-pill-btn-single" in ui_css
    assert ".m3-finops-pill-btn-deck" in ui_css

    # 2. Issue 2: Presenter View 3-card layout, widescreen fullscreen centering, and non-disruptive 2nd Monitor popup
    assert "PRESENTER VIEW" in ui_html
    assert 'id="pc-dock-upnext-card"' in ui_html
    assert "formatPresenterConsoleCardsHtml" in ui_js
    assert "m3-pc-cue-card-say" in ui_js and "m3-pc-cue-card-demo" in ui_js and "m3-pc-cue-card-ask" in ui_js
    assert "margin: 0 auto !important;" in ui_css
    assert "_openingSecondMonitorPopupAt" in ui_js

    # 3. Issue 3: Google Slides Account & Destination Modal 2-card layout + detected account email
    acc_res = client.get("/api/v1/slide/export-gslides/account-info").json()
    assert acc_res["status"] == "SUCCESS"
    assert "@" in acc_res["detected_account_email"] and ".gserviceaccount.com" not in acc_res["detected_account_email"]
    assert "1. Active Workstation Google Drive Account" in ui_html
    assert "2. Share / Open with Personal Gmail or Secondary Account (Optional)" in ui_html
    assert 'id="btn-gslides-pick-google-account"' in ui_html
    assert 'id="btn-gslides-create-and-open-tab"' in ui_html

    # 4. New Feature 1: Application Footer GitHub link
    assert 'id="footer-github-repo-link"' in ui_html
    assert 'href="https://github.com/clayberg/scouts-bsa-merit-badge-agent"' in ui_html

    # 5. New Feature 2: Top-bar Documentation button + Option A Dual-Mode Documentation Studio Modal & API
    assert 'id="btn-open-docs-viewer"' in ui_html
    assert 'id="docs-viewer-modal"' in ui_html
    assert 'id="btn-docs-select-user-guide"' in ui_html
    assert 'id="btn-docs-select-admin-guide"' in ui_html
    assert 'id="btn-docs-toggle-eng-list"' in ui_html
    assert "Open Google Doc" not in ui_html

    docs_cat = client.get("/api/v1/docs").json()
    assert docs_cat["status"] == "SUCCESS"
    assert docs_cat["total_count"] == 12
    assert len(docs_cat["user_docs"]) == 2
    assert len(docs_cat["engineering_docs"]) == 10
    all_ids = [d["doc_id"] for d in docs_cat["all_docs"]]
    assert "user_guide" in all_ids and "admin_guide" in all_ids
    assert all("capstone" not in doc_id.lower() for doc_id in all_ids)

    ug_doc = client.get("/api/v1/docs/user_guide").json()
    assert ug_doc["status"] == "SUCCESS"
    assert ug_doc["doc_id"] == "user_guide"
    assert len(ug_doc["markdown"]) > 1000
    assert "https://github.com/clayberg/scouts-bsa-merit-badge-agent/blob/main/docs/USER_GUIDE.md" == ug_doc["github_url"]

    # Reject any non-allowlisted or Capstone doc request
    bad_doc = client.get("/api/v1/docs/capstone_panel_playbook")
    assert bad_doc.status_code == 404

    # 6. New Feature 3: Verify README.md and all 11 curated docs have zero Capstone or Google Docs references
    assert "CAPSTONE" not in readme_md and "capstone" not in readme_md.lower()
    for d in docs_cat["all_docs"]:
        doc_path = repo_root / d["rel_path"]
        assert doc_path.exists(), f"Missing doc {d['rel_path']}"
        text = doc_path.read_text(encoding="utf-8")
        assert "docs.google.com/document" not in text, f"{d['rel_path']} still references docs.google.com/document"
        assert "1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E" not in text, f"{d['rel_path']} still references executive briefing slide deck"
        assert "Executive Briefing" not in text, f"{d['rel_path']} still references Executive Briefing"
        # Also verify every single allowlisted doc_id returns 200 via /api/v1/docs/{doc_id}
        res_doc = client.get(f"/api/v1/docs/{d['doc_id']}")
        assert res_doc.status_code == 200, f"GET /api/v1/docs/{d['doc_id']} failed with {res_doc.status_code}"
        assert len(res_doc.json().get("markdown", "")) > 200

    # 7. Verify Dockerfile copies all documentation files & UI supports Maximize/Restore, Full-Height Scroll & Dark Mode
    dockerfile_text = (repo_root / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY docs/ ./docs/" in dockerfile_text
    assert "SCOPE.md" in dockerfile_text and "SPEC.md" in dockerfile_text and "ARCHITECTURE_DECISIONS.md" in dockerfile_text
    assert ".m3-docs-studio-dialog.is-maximized" in ui_css
    assert "max-height: none !important;" in ui_css
    assert "body.m3-dark-mode" in ui_css
    assert 'id="btn-toggle-dark-mode"' in ui_html
    assert 'id="btn-docs-toggle-theme"' in ui_html
    assert "applyWorkbenchDarkMode" in ui_js


def test_v30_plan13_comprehensive_dark_mode_and_click_to_zoom_lightbox() -> None:
    """Verifies Plan 13: Counselor Teaching Notes dark mode contrast, Documentation Viewer sky-blue links & GitHub Alerts, Click-to-Zoom Lightbox modal, Visual Patch Gallery dark mode, and full-UI + modal dark mode adaptation while preserving the Warm Cream WYSIWYG slide stage."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_css = (repo_root / "ui" / "styles.css").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")

    # 1. Counselor Teaching Notes Card (#slide-speaker-notes-card & #stage-presenter-notes) Dark Mode rules
    assert "body.m3-dark-mode #slide-speaker-notes-card" in ui_css
    assert "body.m3-dark-mode #stage-presenter-notes" in ui_css
    assert "body.m3-dark-mode #stage-presenter-notes .m3-stage-cue-pill" in ui_css
    assert "body.m3-dark-mode #stage-presenter-notes .m3-expected-answer-box" in ui_css

    # 2. Documentation Viewer Links (.m3-doc-inline-link) & GitHub Alerts (.m3-doc-alert)
    assert 'class="m3-doc-inline-link"' in ui_js
    assert 'style="color:#003F87; font-weight:700; text-decoration:underline;"' not in ui_js
    assert "body.m3-dark-mode .m3-doc-inline-link" in ui_css
    assert "m3-doc-alert-badge" in ui_js
    assert "body.m3-dark-mode .m3-doc-alert" in ui_css

    # 3. Click-to-Zoom Lightbox Modal (#image-zoom-lightbox-modal) & zoomable figures/diagrams
    assert 'id="image-zoom-lightbox-modal"' in ui_html
    assert 'id="btn-lightbox-zoom-in"' in ui_html
    assert 'id="btn-lightbox-zoom-out"' in ui_html
    assert 'id="btn-lightbox-zoom-reset"' in ui_html
    assert 'id="lightbox-zoom-scale-pill"' in ui_html
    assert "openImageZoomLightbox" in ui_js
    assert "applyLightboxZoomScale" in ui_js
    assert "m3-doc-zoomable-figure" in ui_js
    assert "m3-doc-zoom-pill" in ui_js
    assert ".m3-lightbox-backdrop" in ui_css

    # 4. Visual Merit Badge Patch Gallery (#patch-gallery-modal) Dark Mode rules
    assert "m3-patch-card-title" in ui_js
    assert "m3-patch-card-category" in ui_js
    assert "body.m3-dark-mode .m3-patch-gallery-sticky-header" in ui_css
    assert "body.m3-dark-mode .m3-patch-gallery-card" in ui_css
    assert "body.m3-dark-mode .m3-patch-gallery-card .m3-patch-card-title" in ui_css

    # 5. All Other Modals & UI Panels in Dark Mode while preserving #widescreen-slide-stage
    assert "body.m3-dark-mode #ai-polish-finops-title" in ui_css
    assert "body.m3-dark-mode #finops-card-single-slide" in ui_css
    assert "body.m3-dark-mode #finops-card-entire-deck" in ui_css
    assert "body.m3-dark-mode #gslides-export-modal-title" in ui_css
    assert "body.m3-dark-mode #image-studio-modal-title" in ui_css
    assert "body.m3-dark-mode .m3-image-catalog-card" in ui_css
    assert "body.m3-dark-mode .m3-studiokit-pill" in ui_css
    assert "body.m3-dark-mode .m3-markdown-body h1" in ui_css
    assert "body.m3-dark-mode #local-grounding-toggle-card" in ui_css
    assert "body.m3-dark-mode #counselor-profile-accordion" in ui_css
    assert "body.m3-dark-mode #widescreen-slide-stage" in ui_css

    # 6. Plan 14: 9 Isolated Dark Mode Contrast & Opaque Modal Fixes
    assert 'id="feedback-req-verified-box"' in ui_html
    assert "body.m3-dark-mode #feedback-req-verified-box" in ui_css
    assert 'id="admin-console-header-card"' in ui_html
    assert "body.m3-dark-mode #admin-console-header-card" in ui_css
    assert 'id="admin-zero-pii-banner"' in ui_html
    assert "body.m3-dark-mode #admin-zero-pii-banner" in ui_css
    assert "body.m3-dark-mode #admin-stage-latency-bars" in ui_css
    assert "body.m3-dark-mode #admin-circuit-breakers-grid > div" in ui_css
    assert 'body.m3-dark-mode input[type="file"]::file-selector-button' in ui_css
    assert "body.m3-dark-mode #btn-studio-clear-cache" in ui_css
    assert "body.m3-dark-mode #btn-footer-admin-unlock" in ui_css
    assert 'id="gslides-card-active-account"' in ui_html
    assert 'id="gslides-card-share-account"' in ui_html
    assert "body.m3-dark-mode #gslides-export-modal .m3-modal-dialog" in ui_css
    assert "div:has(#gslides-share-email-input)" not in ui_css

    # 7. Plan 14: Fullscreen Presenter View 2-Column Grid & 500% Lightbox with Captions + Admin/Studio Zoom
    assert "grid-template-columns: minmax(0, 1fr) 410px !important;" in ui_css
    assert "Math.min(5.0, Math.max(0.5" in ui_js
    assert 'id="lightbox-caption-bar"' in ui_html
    assert 'id="lightbox-caption-text"' in ui_html
    assert 'id="btn-stage-zoom-image"' in ui_html
    assert 'id="btn-admin-inspector-zoom"' in ui_html
    assert "data-zoom-catalog-idx" in ui_js
    assert "data-admin-zoom-idx" in ui_js


def test_v28_vision_captions_slide_context_toggle_model_armor_and_dark_mode(monkeypatch) -> None:
    """Verifies Plan 15:
    1. All 1,306 Nano Banana illustrations and 2,341 Pamphlet figures have Vision-verified visual captions
       (0 meta captions like 'Educational Scouting handbook illustration' or 'Scout and counselor reviewing').
    2. `include_slide_context=False` omits slide bullets/title while keeping the Uniformed Scouts directive,
       and generates a clean visual caption instead of dumping the raw prompt.
    3. Model Armor blocks inappropriate prompts ('2 scouts naked in a canoe') with `NANO_BANANA_PROMPT_BLOCKED`
       at $0.00 and never falls back to Wikimedia Commons.
    4. Dark Mode CSS rules for `.m3-studio-ai-blocked-alert` and `.m3-construction-stage` header & footer.
    """
    from pathlib import Path
    import json
    from src.agents.image_studio import (
        resolve_content_aware_visual_config,
        generate_nano_banana_slide_image,
        _generate_clean_visual_caption_for_nano_image,
    )

    repo_root = Path(__file__).resolve().parent.parent

    # 1. Verify zero meta captions in nano_banana_image_catalog.json and pamphlet_image_catalog.json
    nano_cat = json.loads((repo_root / "data" / "nano_banana_image_catalog.json").read_text(encoding="utf-8"))
    assert len(nano_cat) >= 1300
    for fname, entry in nano_cat.items():
        cap = str(entry.get("caption") or "")
        assert len(cap) >= 20, f"Short caption for {fname}: {cap}"
        assert "Educational Scouting handbook illustration" not in cap
        assert not cap.startswith("Scout and counselor reviewing ")
        assert not cap.startswith("Four-panel instructional breakdown")

    pamphlet_cat = json.loads((repo_root / "data" / "pamphlet_image_catalog.json").read_text(encoding="utf-8"))
    assert len(pamphlet_cat) >= 2320
    for fname, entry in pamphlet_cat.items():
        cap = str(entry.get("caption") or "")
        assert len(cap) >= 20, f"Short caption for {fname}: {cap}"
        assert "Official figure for Requirement" not in cap

    # 2. Verify include_slide_context=True vs False
    cfg_with_ctx = resolve_content_aware_visual_config(
        badge_name="First Aid",
        slide_title="Rigid Forearm Splinting, Sling & Distal CMS Check",
        req_number="8",
        bullet_points=["Immobilize Joint Above & Below", "Open Fracture Dressing"],
        custom_prompt="2 people in a canoe",
        visual_style="Auto (Content-Aware Mix)",
        include_humans="auto",
        include_slide_context=True,
    )
    assert cfg_with_ctx["include_slide_context"] is True
    assert cfg_with_ctx["include_humans"] is True
    assert "Immobilize Joint Above" in cfg_with_ctx["enriched_subject"]

    cfg_no_ctx = resolve_content_aware_visual_config(
        badge_name="First Aid",
        slide_title="Rigid Forearm Splinting, Sling & Distal CMS Check",
        req_number="8",
        bullet_points=["Immobilize Joint Above & Below", "Open Fracture Dressing"],
        custom_prompt="2 people in a canoe",
        visual_style="Auto (Content-Aware Mix)",
        include_humans="auto",
        include_slide_context=False,
    )
    assert cfg_no_ctx["include_slide_context"] is False
    assert cfg_no_ctx["include_humans"] is True
    assert "Immobilize Joint Above" not in cfg_no_ctx["enriched_subject"]
    assert "First Aid" not in cfg_no_ctx["enriched_subject"]
    assert cfg_no_ctx["enriched_subject"] == "2 people in a canoe"
    assert "Uniformed Scouts" in cfg_no_ctx["routing_reason"]

    clean_title, clean_cap = _generate_clean_visual_caption_for_nano_image(
        out_path=Path("/nonexistent/test.png"),
        custom_prompt="2 people in a canoe",
        base_subject="2 people in a canoe (illustrating slide concepts: Immobilize Joint Above & Below)",
        slide_title="Rigid Forearm Splinting, Sling & Distal CMS Check",
        badge_name="First Aid",
        include_humans=True,
        include_slide_context=False,
    )
    assert "Custom " not in clean_cap
    assert "illustrating slide concepts" not in clean_cap
    assert "Prompt Alignment Verified" not in clean_cap
    assert "uniformed Scouts" in clean_cap

    # 3. Verify Model Armor blocks '2 scouts naked in a canoe' at $0.00 with zero fallback
    blocked_res = generate_nano_banana_slide_image(
        badge_name="First Aid",
        slide_title="Rigid Forearm Splinting, Sling & Distal CMS Check",
        req_number="8",
        bullet_points=["Immobilize Joint Above & Below"],
        custom_prompt="2 scouts naked in a canoe",
        user_consented=True,
    )
    assert blocked_res["status"] == "ERROR"
    assert blocked_res["error_code"] == "NANO_BANANA_PROMPT_BLOCKED"
    assert "Model Armor" in blocked_res["message"]

    # 4. Verify UI elements & Dark Mode CSS rules for Plan 15
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_css = (repo_root / "ui" / "styles.css").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")

    assert 'id="studio-ai-include-slide-context-checkbox"' in ui_html
    assert "include_slide_context: includeSlideCtx" in ui_js
    assert 'class="m3-studio-ai-blocked-alert"' in ui_js
    assert "body.m3-dark-mode #studio-ai-cost-banner .m3-studio-ai-blocked-alert" in ui_css
    assert "body.m3-dark-mode .m3-construction-topbar" in ui_css
    assert "body.m3-dark-mode .m3-construction-concept-btn" in ui_css
    assert "body.m3-dark-mode .m3-construction-footer" in ui_css


def test_v35_plan16_templates_workspaces_favorites_and_mcp() -> None:
    """Verifies Plans 16A, 16B, and 16C end-to-end:
    - Plan 16A: 8 council-neutral curated PowerPoint templates, SafeCanvasBounds AABB conformance,
      1-click template application, and custom template upload.
    - Plan 16B: Multi-badge counselor workspaces CRUD, cloning for Morning vs. Afternoon Patrol,
      cross-badge Blue Card roster copying, and starred favorite Merit Badges.
    - Plan 16C: Dual-transport MCP Server (`src/mcp_server.py` + `POST /mcp` JSON-RPC 2.0) with
      12 Tools, 6 `bsa://` Resources, 4 Prompts, and Model Armor safety enforcement.
    """
    from pathlib import Path
    from fastapi.testclient import TestClient
    from src.server import app

    client = TestClient(app)
    repo_root = Path(__file__).resolve().parent.parent

    # 1. Plan 16A: Verify 8 council-neutral curated templates
    tpl_resp = client.get("/api/v1/templates")
    assert tpl_resp.status_code == 200
    tpl_data = tpl_resp.json()
    assert tpl_data["status"] == "SUCCESS"
    assert tpl_data["total"] >= 8
    tpl_ids = {t["template_id"] for t in tpl_data["templates"]}
    for expected_id in (
        "default_workbench",
        "scouting_america_250",
        "scouting_america_forest_sunrise",
        "scouting_america_topographic",
        "scouting_america_high_adventure_rock",
        "classic_outdoor_silhouette_navy",
        "classic_fleur_crimson_crest",
        "wilderness_camp_timber",
    ):
        assert expected_id in tpl_ids

    # Ensure zero external council/site references in template names/descriptions
    for t in tpl_data["templates"]:
        combined = f"{t['name']} {t['description']}".lower()
        assert "michigan" not in combined
        assert "brewster" not in combined

    # Apply 'scouting_america_250' template to sample slides and verify PPTX build
    apply_resp = client.post(
        "/api/v1/templates/apply",
        json={
            "badge_name": "First Aid",
            "template_id": "scouting_america_250",
            "storyboard_slides": [
                {
                    "title": "Requirement 1: Scene Safety & Triage",
                    "req_number": "1",
                    "archetype": "SPLIT_VISUAL_EXPLAINER",
                    "bullet_points": ["Check Scene: Ensure responder safety before approaching."],
                    "safety_warning": "Wear personal protective gloves.",
                }
            ],
            "accent_palette_key": "MATCH_TEMPLATE",
        },
    )
    assert apply_resp.status_code == 200
    apply_json = apply_resp.json()
    assert apply_json["status"] == "SUCCESS"
    assert apply_json["template"]["template_id"] == "scouting_america_250"
    assert apply_json["pptx_download_url"]

    # 2. Plan 16B: Verify Starred Favorites & Multi-Badge Workspaces + Cloning
    fav_resp = client.post("/api/v1/counselor/favorites", json={"badge_name": "Kayaking", "is_favorite": True})
    assert fav_resp.status_code == 200
    assert "Kayaking" in fav_resp.json()["favorites"]

    ws_create = client.post(
        "/api/v1/workspaces",
        json={
            "workspace_title": "First Aid — Morning Patrol",
            "badge_name": "First Aid",
            "session_label": "Morning Patrol (9:00 AM)",
            "camp_bundle_tag": "Summer Camp Week 1",
            "template_id": "scouting_america_250",
            "blue_card_roster": {
                "scouts": [
                    {"name": "Alex Carter", "troop": "Troop 19", "patrol": "Eagle Patrol", "completed_reqs": ["1a", "2a"]},
                    {"name": "Sam Rivera", "troop": "Troop 19", "patrol": "Fox Patrol", "completed_reqs": ["1a"]},
                ]
            },
            "deck_result": {
                "badge_name": "First Aid",
                "storyboard": {
                    "slides": [
                        {
                            "title": "Requirement 1a: First Aid Kit",
                            "req_number": "1a",
                            "archetype": "SPLIT_VISUAL_EXPLAINER",
                            "bullet_points": ["Inspect sterile gauze and bandages."],
                        }
                    ]
                },
            },
        },
    )
    assert ws_create.status_code == 200
    ws_id = ws_create.json()["workspace"]["workspace_id"]
    assert ws_id.startswith("ws_first_aid_")

    # Clone workspace for Afternoon Patrol with clean roster
    ws_clone = client.post(
        f"/api/v1/workspaces/{ws_id}/clone",
        json={"session_label": "Afternoon Patrol (2:00 PM)", "copy_roster": False},
    )
    assert ws_clone.status_code == 200
    cloned_ws = ws_clone.json()["workspace"]
    cloned_id = cloned_ws["workspace_id"]
    assert cloned_id != ws_id
    assert cloned_ws["scout_count"] == 0

    # 3. Plan 16C: Verify MCP Server Info & JSON-RPC 2.0 Endpoint (`POST /mcp`)
    mcp_info = client.get("/mcp/info")
    assert mcp_info.status_code == 200
    info_json = mcp_info.json()
    assert info_json["counts"]["tools"] == 12
    assert info_json["counts"]["resources"] == 6
    assert info_json["counts"]["prompts"] == 4

    # JSON-RPC initialize
    rpc_init = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert rpc_init.status_code == 200
    assert rpc_init.json()["result"]["serverInfo"]["name"] == "scouts-bsa-merit-badge-workbench"

    # JSON-RPC tools/call -> copy_roster_from_workspace from Morning Patrol to Afternoon Patrol
    rpc_copy = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "manage_patrol_blue_card_roster",
                "arguments": {
                    "workspace_id": cloned_id,
                    "action": "copy_roster_from_workspace",
                    "copy_from_workspace_id": ws_id,
                },
            },
        },
    )
    assert rpc_copy.status_code == 200
    copy_res = rpc_copy.json()["result"]["structuredContent"]
    assert copy_res["status"] == "SUCCESS"
    assert copy_res["copied_count"] == 2
    assert copy_res["scout_count"] == 2

    # JSON-RPC tools/call -> update_slide_in_deck & audit_deck_conformance
    rpc_upd = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "update_slide_in_deck",
                "arguments": {
                    "workspace_id": ws_id,
                    "slide_index": 0,
                    "title": "Requirement 1a: Personal First-Aid Kit Inspection",
                },
            },
        },
    )
    assert rpc_upd.status_code == 200
    assert rpc_upd.json()["result"]["structuredContent"]["status"] == "SUCCESS"

    rpc_audit = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "audit_deck_conformance", "arguments": {"workspace_id": ws_id}},
        },
    )
    assert rpc_audit.status_code == 200
    audit_res = rpc_audit.json()["result"]["structuredContent"]
    assert audit_res["conformance_report"]["passed"] is True
    assert audit_res["conformance_report"]["aabb_overlap_count"] == 0

    # Clean up test workspaces and test favorite
    client.delete(f"/api/v1/workspaces/{ws_id}")
    client.delete(f"/api/v1/workspaces/{cloned_id}")
    client.post("/api/v1/counselor/favorites", json={"badge_name": "Kayaking", "is_favorite": False})

    # Verify UI & Dark Mode CSS parity for Plans 16A, 16B, 16C
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_css = (repo_root / "ui" / "styles.css").read_text(encoding="utf-8")
    assert 'id="template-studio-modal"' in ui_html
    assert 'id="saved-workspaces-modal"' in ui_html
    assert 'id="mcp-hub-modal"' in ui_html
    assert "body.m3-dark-mode .m3-template-card" in ui_css
    assert "body.m3-dark-mode .m3-active-workspaces-bar" in ui_css


def test_plan17_favorites_workspaces_templates_mcp_and_theme_aliases(tmp_path):
    """Verifies all 5 Plan 17 user observations & enhancements:
    1) Favorites: `.m3-patch-fav-btn.is-fav` white star on gold circle, `#btn-patch-gallery-fav-filter` header button,
       and `FAVORITES` option in `#filter-eagle-select`.
    2) Merit Badge Library: Delete confirmation modal (`#delete-workspace-confirm-modal` + `#chk-skip-delete-deck-confirm`),
       blank default `session_label` & `camp_bundle_tag` with `workspace_title == badge_name` on new decks, copying all 3 fields
       on clone, and editable combobox preset dropdowns (`#ws-session-presets-menu`, `#ws-bundle-presets-menu`).
    3) Templates: Responsive slide geometry + luminance-aware `get_contrasting_text_rgb()`, 3-box anatomical Safe-Zone X-Ray,
       custom template metadata edit (`PATCH /api/v1/templates/{id}`) & delete (`DELETE /api/v1/templates/{id}`), and toolbar
       split-button template switcher (`#stage-template-split-group`).
    4) MCP Server & Agent Hub: `Gemini CLI / AGY` label, modern theme aliases (`WARM_CREAM`, `CRISP_WHITE`, `DARK_SLATE`,
       `CREAM`, `WHITE`, `SLATE`) in `normalize_visual_theme()` and MCP tools, interactive Section 2 Resource/Prompt execution,
       and Section 3 `[📊 Visual Card Preview | { } Raw JSON-RPC 2.0]` tabs.
    5) Dynamic Top-Bar Counselor Profile Pill (`#top-counselor-chip-name` + `#top-counselor-chip-affil` without fixed 185px cap).
    """
    import io
    from pathlib import Path
    from PIL import Image
    from fastapi.testclient import TestClient
    from src.server import app
    from src.tools.template_engine import get_contrasting_text_rgb, normalize_visual_theme

    repo_root = Path(__file__).resolve().parents[1]
    client = TestClient(app)

    # 1. Verify modern visual theme alias normalization & luminance contrast helper
    assert normalize_visual_theme("WARM_CREAM") == "BEAUTIFIED"
    assert normalize_visual_theme("CREAM") == "BEAUTIFIED"
    assert normalize_visual_theme("CRISP_WHITE") == "STANDARD"
    assert normalize_visual_theme("WHITE") == "STANDARD"
    assert normalize_visual_theme("DARK_SLATE") == "STUDIO"
    assert normalize_visual_theme("SLATE") == "STUDIO"

    assert get_contrasting_text_rgb("#003F87") == (255, 255, 255)
    assert get_contrasting_text_rgb("#1B4332") == (255, 255, 255)
    assert get_contrasting_text_rgb("#FAF8F5") == (15, 23, 42)

    # 2. Verify custom template upload, PATCH metadata update, and DELETE cleanup
    img_buf = io.BytesIO()
    Image.new("RGB", (640, 360), color=(20, 60, 120)).save(img_buf, format="PNG")
    img_buf.seek(0)
    up_res = client.post(
        "/api/v1/templates/upload",
        files={"file": ("council_banner.png", img_buf.getvalue(), "image/png")},
        data={"name": "Initial Custom Template"},
    )
    assert up_res.status_code == 200
    custom_tpl = up_res.json()["template"]
    custom_id = custom_tpl["template_id"]
    assert custom_id.startswith("custom_")
    assert custom_tpl["is_builtin"] is False

    patch_res = client.patch(
        f"/api/v1/templates/{custom_id}",
        json={"name": "Troop 123 High Adventure Theme", "description": "Edited custom template description"},
    )
    assert patch_res.status_code == 200
    patched_tpl = patch_res.json()["template"]
    assert patched_tpl["name"] == "Troop 123 High Adventure Theme"
    assert patched_tpl["description"] == "Edited custom template description"

    del_res = client.delete(f"/api/v1/templates/{custom_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # 3. Verify workspace defaults (title = badge_name, blank session/camp tags) and cloning copies all 3 fields
    ws_new = client.post(
        "/api/v1/workspaces",
        json={"badge_name": "Wilderness Survival", "visual_theme": "WARM_CREAM"},
    )
    assert ws_new.status_code == 200
    ws_data = ws_new.json()["workspace"]
    assert ws_data["workspace_title"] == "Wilderness Survival"
    assert ws_data["session_label"] == ""
    assert ws_data["camp_bundle_tag"] == ""

    ws_tagged = client.post(
        "/api/v1/workspaces",
        json={
            "workspace_id": ws_data["workspace_id"],
            "badge_name": "Wilderness Survival",
            "workspace_title": "Wilderness Survival — Basecamp",
            "session_label": "Morning Session (9:00 AM)",
            "camp_bundle_tag": "Summer Camp — Week 2",
        },
    ).json()["workspace"]

    ws_cloned = client.post(
        f"/api/v1/workspaces/{ws_tagged['workspace_id']}/clone",
        json={"clear_blue_card_roster": True},
    )
    assert ws_cloned.status_code == 200
    cloned_data = ws_cloned.json()["workspace"]
    assert cloned_data["workspace_title"] == "Wilderness Survival — Basecamp"
    assert cloned_data["session_label"] == "Morning Session (9:00 AM)"
    assert cloned_data["camp_bundle_tag"] == "Summer Camp — Week 2"

    client.delete(f"/api/v1/workspaces/{ws_tagged['workspace_id']}")
    client.delete(f"/api/v1/workspaces/{cloned_data['workspace_id']}")

    # 4. Verify MCP Hub exposes Gemini CLI / AGY and modern theme names + prompts/get execution
    mcp_info = client.get("/mcp/info").json()
    assert "gemini_cli_agy" in mcp_info["client_snippets"]
    create_tool = next(t for t in mcp_info["tools"] if t["name"] == "create_merit_badge_slide_deck")
    enum_vals = create_tool["inputSchema"]["properties"]["visual_theme"]["enum"]
    for modern_theme in ("WARM_CREAM", "CRISP_WHITE", "DARK_SLATE", "CREAM", "WHITE", "SLATE"):
        assert modern_theme in enum_vals

    rpc_prompt = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 99,
            "method": "prompts/get",
            "params": {
                "name": "plan-merit-badge-camp-class",
                "arguments": {"badge_name": "First Aid", "camp_name": "Camp Yawgoog"},
            },
        },
    )
    assert rpc_prompt.status_code == 200
    assert len(rpc_prompt.json()["result"]["messages"]) >= 1

    # 5. Verify UI HTML, CSS & JS hooks for all 5 Plan 17 items
    ui_html = (repo_root / "ui" / "index.html").read_text(encoding="utf-8")
    ui_css = (repo_root / "ui" / "styles.css").read_text(encoding="utf-8")
    ui_js = (repo_root / "ui" / "app.js").read_text(encoding="utf-8")

    assert 'id="top-counselor-chip-name"' in ui_html
    assert 'id="top-counselor-chip-affil"' in ui_html
    assert 'id="btn-patch-gallery-fav-filter"' in ui_html
    assert 'id="stage-template-split-group"' in ui_html
    assert 'id="btn-stage-template-caret"' in ui_html
    assert 'id="stage-template-dropdown-menu"' in ui_html
    assert 'id="xray-box-header"' in ui_html
    assert 'id="xray-box-content"' in ui_html
    assert 'id="xray-box-footer"' in ui_html
    assert 'id="delete-workspace-confirm-modal"' in ui_html
    assert 'id="chk-skip-delete-deck-confirm"' in ui_html
    assert 'id="edit-template-meta-modal"' in ui_html
    assert 'id="ws-session-presets-menu"' in ui_html
    assert 'id="ws-bundle-presets-menu"' in ui_html
    assert "Gemini CLI / AGY" in ui_html
    assert "Gemini CLI / Jetski" not in ui_html
    assert 'id="btn-mcp-view-visual"' in ui_html
    assert 'id="btn-mcp-view-json"' in ui_html
    assert ".m3-patch-fav-btn.is-fav" in ui_css
    assert "function showToast(" in ui_js
    assert "renderMcpVisualCardPreview" in ui_js

    # 6. Verify uniform 16:9 slide stage width & aspect-ratio lock across all slides (no shrink-to-fit on Cover / Full-Bleed slides)
    assert "width: 100%;" in ui_css
    assert "aspect-ratio: 16 / 9;" in ui_css
    assert "flex: 1 1 100%;" in ui_css
    assert 'stageEl.style.width = "100%";' in ui_js
    assert 'stageEl.style.aspectRatio = "16 / 9";' in ui_js
    assert 'stageEl.style.aspectRatio = "auto"' not in ui_js
    assert "slide-density-micro-compact" in ui_css
    assert "slide-density-micro-compact" in ui_js








