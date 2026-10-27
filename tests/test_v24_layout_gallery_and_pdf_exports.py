"""v2.4 regression tests for Clean vs. Boxed marker stability, Patch Gallery header, branded PDFs, and doc screenshots."""

from __future__ import annotations

from pathlib import Path
import re

import fitz
from fastapi.testclient import TestClient

from src.server import app
from src.tools.counselor_studiokit import (
    generate_class_preparation_page_cpp_pdf,
    generate_fillable_scout_workbook_pdf,
    generate_parent_letter_pdf,
    generate_session_agenda_pdf,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_clean_to_boxed_layout_style_does_not_flip_marker_style() -> None:
    """Switching Deck Layout Style from Clean to Boxed must not alter effectiveCardTheme or default triangle markers."""
    app_js = (REPO_ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    assert '!slide._customThemeOverride && archetype !== "SAFETY_CRITICAL_CALLOUT"' in app_js
    assert "isCleanOrLineMode && !slide._customThemeOverride" not in app_js


def test_patch_gallery_header_close_button_and_short_subtitle() -> None:
    """Patch Gallery header places Close button in upper-right row and uses the concise 4-part legend."""
    index_html = (REPO_ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    assert "Gold-bordered = Eagle-Required" in index_html
    assert "= Multi-Option" in index_html
    assert "🧪 = Test Lab Pilot" in index_html
    assert "🚫 = Discontinued" in index_html
    assert "Gold-bordered emblems denote Eagle-Required Merit Badges (18)." not in index_html
    # Verify Close button appears before the filter controls inside the sticky header
    header_pos = index_html.index("id=\"patch-gallery-modal-title\"")
    close_pos = index_html.index("id=\"btn-close-patch-gallery\"")
    search_pos = index_html.index("id=\"patch-gallery-search-input\"")
    assert header_pos < close_pos < search_pos


def test_branded_pdf_generators_and_endpoints() -> None:
    """All 4 counselor/Scout document types generate multi-section branded PDFs with embedded emblems and footers."""
    wb_bytes = generate_fillable_scout_workbook_pdf("First Aid")
    cpp_bytes = generate_class_preparation_page_cpp_pdf("First Aid")
    agenda_bytes = generate_session_agenda_pdf("First Aid")
    letter_bytes = generate_parent_letter_pdf("First Aid", stage="stage_1")

    for label, payload in [
        ("workbook", wb_bytes),
        ("cpp", cpp_bytes),
        ("agenda", agenda_bytes),
        ("parent_letter", letter_bytes),
    ]:
        assert payload.startswith(b"%PDF"), f"{label} did not return valid PDF bytes"
        doc = fitz.open(stream=payload, filetype="pdf")
        assert doc.page_count >= 1
        page1_text = doc[0].get_text("text")
        assert "First Aid" in page1_text
        assert "Page 1 of" in page1_text
        # Page 1 should embed the official Merit Badge patch emblem PNG in the header banner
        assert len(doc[0].get_images()) >= 1, f"{label} page 1 missing embedded badge emblem image"
        doc.close()

    client = TestClient(app)
    for url in [
        "/api/v1/studiokit/fillable-workbook.pdf?badge_name=First+Aid",
        "/api/v1/studiokit/class-prep-cpp.pdf?badge_name=First+Aid",
        "/api/v1/studiokit/cpp.pdf?badge_name=First+Aid",
        "/api/v1/studiokit/agenda.pdf?badge_name=First+Aid",
        "/api/v1/studiokit/parent-letter.pdf?badge_name=First+Aid&stage=stage_1",
    ]:
        resp = client.get(url)
        assert resp.status_code == 200, f"GET {url} failed with {resp.status_code}"
        assert resp.headers["content-type"].startswith("application/pdf")
        assert resp.content.startswith(b"%PDF")


def test_markdown_downloads_replaced_with_pdf_while_keeping_copy_buttons() -> None:
    """UI menus expose .PDF downloads instead of .MD downloads while preserving Copy Markdown/Text buttons."""
    index_html = (REPO_ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    assert "📥 Download Scout Workbook (.PDF)" in index_html
    assert "📥 Download Agenda (.PDF)" in index_html
    assert "📥 Download Letter (.PDF)" in index_html
    assert "📋 Copy Markdown" in index_html or "📋 Copy Workbook Markdown" in index_html
    assert "📋 Copy Agenda" in index_html
    assert "📋 Copy Letter" in index_html


def test_all_user_guide_and_admin_guide_screenshots_exist() -> None:
    """Every screenshot referenced in docs/USER_GUIDE.md and docs/ADMIN_GUIDE.md exists and is non-empty."""
    for doc_name in ["USER_GUIDE.md", "ADMIN_GUIDE.md"]:
        doc_path = REPO_ROOT / "docs" / doc_name
        content = doc_path.read_text(encoding="utf-8")
        refs = re.findall(r"!\[[^\]]*\]\(([^)]+\.png)\)", content)
        assert len(refs) > 0
        for rel in refs:
            img_path = (doc_path.parent / rel).resolve()
            assert img_path.exists(), f"Missing screenshot {rel} referenced in {doc_name}"
            assert img_path.stat().st_size > 5000, f"Screenshot {rel} is unexpectedly small ({img_path.stat().st_size}B)"
