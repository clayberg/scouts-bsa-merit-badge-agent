"""V32 Regression Suite: Items 1-10 UI/UX, Quizzes, Workbooks, Templates & 21-Badge Deep Audit."""

from __future__ import annotations

import json
from pathlib import Path

import fitz

from src.agents.planner import generate_slide_storyboard
from src.tools.counselor_studiokit import generate_fillable_scout_workbook_pdf
from src.tools.scouting_scraper import (
    generate_counselor_workbook_markdown,
    generate_fillable_scout_workbook_html,
)
from fastapi.testclient import TestClient
from src.server import app
from src.tools.template_engine import _resolve_nano_photorealistic_base_cover

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_v32_items_1_2_3_5_7_8_9_frontend_ui_contracts() -> None:
    """Verifies Frontend UI contracts for Items 1, 2, 3, 5, 7, 8, and 9."""
    app_js = (REPO_ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    index_html = (REPO_ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    styles_css = (REPO_ROOT / "ui" / "styles.css").read_text(encoding="utf-8")

    # Item 1: Stage inline edit supports header, body cards, caption, and Esc key exit
    assert 'document.getElementById("stage-left-cards") || document.getElementById("stage-left-zone")' in app_js
    assert 'document.getElementById("stage-diagram-caption")' in app_js
    assert "state.stageInlineEditActive" in app_js
    assert ".m3-stage-inline-editable" in styles_css

    # Item 2: Workbook image click-to-zoom lightbox
    assert "openWorkbookImageZoom" in app_js
    assert "OPEN_WORKBOOK_IMAGE_LIGHTBOX" in app_js
    assert "#workbook-markdown-preview img" in styles_css

    # Item 3: Ghost image prevention on rapid slide navigation
    assert "function setStageDiagramImageSrcCleanly(" in app_js
    assert "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" in app_js

    # Item 5: Clean built-in template list (0 leftover test templates) & scrollable dropdown menu
    client = TestClient(app)
    templates = client.get("/api/templates").json().get("templates", [])
    test_Matches = [
        t["name"]
        for t in templates
        if "test bsa logo washed theme" in str(t.get("name", "")).lower()
        or "summer 2026 theme #" in str(t.get("name", "")).lower()
    ]
    assert not test_Matches, f"Found leftover test templates: {test_Matches}"
    assert "m3-stage-template-dropdown-list" in app_js
    assert ".m3-stage-template-dropdown-list" in styles_css

    # Item 7: Animated download progress modal
    assert 'id="download-progress-modal"' in index_html
    assert "showDownloadProgressModal" in app_js
    assert "downloadUrlWithProgressModal" in app_js
    assert "download-progress" in styles_css

    # Item 8: Attractive HITL Learning Hub Promote to Default buttons & compact asset pills
    assert "🖼️ Asset #" in app_js
    assert ".btn-promote-image-override" in styles_css

    # Item 9: Synthesize Washed Backdrop from Prompt instructions, preview sync & custom_backdrop_url
    assert 'id="tpl-ai-how-to-callout"' in index_html
    assert 'value="ai_prompt"' in index_html
    assert "tplAiSynthesizedBackdropUrl" in app_js
    assert "custom_backdrop_url" in app_js


def test_v32_item_9_apollo_rocket_prompt_prioritizes_live_ai_synthesis(monkeypatch) -> None:
    """Verifies that custom prompts like 'Distance shot of an Apollo rocket launch' call live AI synthesis first."""
    called_prompts = []

    def _fake_synth(*, visual_subject: str, **kwargs) -> bool:
        called_prompts.append(visual_subject)
        return False

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr("src.agents.image_studio._try_live_ai_image_synthesis", _fake_synth)
    _resolve_nano_photorealistic_base_cover(
        visual_style="Space Exploration",
        custom_prompt="Distance shot of an Apollo rocket launch",
        family_id="test_apollo_v32",
        backdrop_id="ai_prompt",
        allow_live_synthesis=True,
    )
    assert len(called_prompts) == 1
    assert "Apollo rocket launch" in called_prompts[0]


def test_v32_items_4_6_10_weather_and_all_149_badges_quizzes_and_workbooks() -> None:
    """Verifies Weather + all 149 badges have zero boilerplate quizzes, zero 'Applied Field Standard' titles, and clean workbooks."""
    req_dir = REPO_ROOT / "data" / "merit_badge_requirements"
    json_files = [p for p in sorted(req_dir.glob("*.json")) if not p.name.startswith("_")]
    assert len(json_files) == 149

    for jpath in json_files:
        data = json.loads(jpath.read_text(encoding="utf-8"))
        bname = data["badge_name"]
        for r in data.get("requirements", []):
            rid = r.get("req_id")
            tt = str(r.get("topic_title") or "")
            assert "Applied Field Standard" not in tt, f"{bname} Req {rid} has Applied Field Standard"
            q_str = json.dumps(r.get("quiz_item") or {})
            assert "encounters a decision point on proper procedure" not in q_str, f"{bname} Req {rid} has boilerplate quiz prompt"
            assert "Defer all " not in q_str, f"{bname} Req {rid} has boilerplate distractor"
            assert "Substitute uncalibrated equipment" not in q_str, f"{bname} Req {rid} has boilerplate distractor"
            wb_diag = str(r.get("workbook_diagram_url") or "")
            assert "_workbook_diagram.png" not in wb_diag, f"{bname} Req {rid} has dead _workbook_diagram.png"

    # Check Weather storyboard & workbook PDF/HTML
    w_data = json.loads((req_dir / "weather.json").read_text(encoding="utf-8"))
    sb = generate_slide_storyboard("Weather", w_data["requirements"])
    slides = sb["slides"]
    quiz_slides = [
        s for s in slides
        if (s.archetype if hasattr(s, "archetype") else s.get("archetype")) == "SOCRATIC_CHECKPOINT_QUIZ"
    ]
    assert len(quiz_slides) == 1

    html_res = generate_fillable_scout_workbook_html("Weather")
    html_doc = html_res["html_document"]
    assert "Req 1: Req 1:" not in html_doc
    assert "openWbStandaloneLightbox" in html_doc
    assert "_workbook_diagram.png" not in html_doc

    md_doc = generate_counselor_workbook_markdown(w_data)
    assert "Req 1 — Req 1:" not in md_doc
    assert "](/assets/" in md_doc

    pdf_bytes = generate_fillable_scout_workbook_pdf("Weather")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_pdf_txt = "\n".join(page.get_text("text") for page in doc)
    assert "_workbook_diagram.png" not in full_pdf_txt
    assert "Define meteorology." in full_pdf_txt
    assert "Explain what weather is and what climate is." in full_pdf_txt
