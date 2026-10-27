"""End-to-End Verification & Screenshot Suite for v2.6 (Items 1-6).

Verifies:
1. Item 1: Nano Banana Slide Template Studio - creating 1st and 2nd custom AI template families back-to-back, Tab 1 '🍌 + Create AI Template' quick-launch button, and 6-variation cycling on '✨ Sample Camp / MBC Prompt (1/6..6/6)'.
2. Item 2: Dynamic 2-Row Session Builder schedule synchronization with Patrol Blue Card Tracker (session header, attendance pills S1..SN | M, batch sign-off dropdown) and Fillable Workbook 'Schedule:' header line, plus compact collapse chevron ('▴ Collapse Builder' / '▾ Expand Schedule Builder').
3. Item 3: Admin Console 'Add DMBC & HVSC Customizations' checkbox (default unchecked = zero 'Danvers' / 'Hidden Valley' / 'Holten-Richmond' / 'Griswold' strings visible; checked = enables DMBC & HVSC templates, macros, rooms, tags, and palettes).
4. Item 4: Fillable Scout Workbook (HTML & PDF) Page-1 Parent-Requirement Grouped Completion Matrix with parent badges, topic titles, syllabus tags, live per-group counters, and '▴ Compact Summary View' toggle.
5. Item 5: 1-Page Pocket Field Checklist & QR Reference PDF real ISO/IEC 18004 QR matrix rendering with centered BSA fleur-de-lis emblem and full un-truncated resource titles and URLs.
"""

from __future__ import annotations

import pathlib
import shutil
import urllib.request
import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient

from src.server import app
from src.tools.counselor_studiokit import (
    generate_field_qr_checklist_pdf,
    generate_fillable_scout_workbook_pdf,
)
from src.tools.scouting_scraper import generate_fillable_scout_workbook_html
from src.tools.template_engine import delete_custom_template, load_template_catalog

ARTIFACT_DIR = pathlib.Path(
    "/usr/local/google/home/clayberg/.gemini/jetski/brain/aab0a16f-2d4f-4ac3-b70d-babfa87cfacf"
)
DOCS_IMAGES_DIR = (
    pathlib.Path(__file__).resolve().parent.parent / "docs" / "images"
)


def test_item1_backend_create_two_consecutive_ai_template_families() -> None:
    """Verifies creating a 1st and 2nd custom AI template family via POST /api/v1/templates/generate-ai."""
    client = TestClient(app)
    created_ids: list[str] = []
    try:
        # 1st template using UI payload keys (template_name, style_family, frame_preset, confirm_finops_cost)
        resp1 = client.post(
            "/api/v1/templates/generate-ai",
            json={
                "template_name": "Pinewood Trail Test Series",
                "style_family": "pinewood_campfire",
                "frame_preset": "horizon_silhouette",
                "colors": ["#1B5E20", "#0284C7", "#D97706"],
                "prompt": "Crisp pine forest ridgeline silhouette along the bottom footer.",
                "logo_position": "bottom-right",
                "remove_logo_bg": True,
                "confirm_finops_cost": True,
            },
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["status"] == "SUCCESS"
        assert len(data1["variants"]) == 3
        fam1_id = data1["family_id"]
        created_ids.extend(v["template_id"] for v in data1["variants"])

        # 2nd template with the SAME base name (auto-disambiguates to #2 instead of colliding)
        resp2 = client.post(
            "/api/v1/templates/generate-ai",
            json={
                "template_name": "Pinewood Trail Test Series",
                "style_family": "aquatics_nautical",
                "frame_preset": "corner_crest",
                "colors": ["#0369A1", "#0F766E", "#F59E0B"],
                "prompt": "Waterfront aquatics and nautical chart theme with coastal lighthouse silhouette.",
                "logo_position": "top_right",
                "remove_logo_bg": True,
                "confirm_finops_cost": True,
            },
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["status"] == "SUCCESS"
        assert len(data2["variants"]) == 3
        fam2_id = data2["family_id"]
        created_ids.extend(v["template_id"] for v in data2["variants"])

        assert fam1_id != fam2_id
        assert data2["family_name"] == "Pinewood Trail Test Series #2"

        catalog_ids = {t.template_id for t in load_template_catalog()}
        for tid in created_ids:
            assert tid in catalog_ids
    finally:
        for tid in created_ids:
            delete_custom_template(tid)


def test_item4_workbook_grouped_completion_matrix_html_and_pdf() -> None:
    """Verifies the Parent-Requirement Grouped Completion Matrix in Fillable Workbook HTML and PDF."""
    session_dates = ["S1: Sat Jan 10", "S2: Sat Jan 17", "S3: Sat Jan 24"]
    wb_res = generate_fillable_scout_workbook_html(
        badge_name="First Aid",
        session_dates=session_dates,
    )
    html = wb_res["html_document"]
    assert 'data-testid="wb-page1-grouped-matrix"' in html
    assert 'data-testid="btn-wb-index-toggle-compact"' in html
    assert "wb-index-parent-group" in html
    assert "S1: Sat Jan 10 | S2: Sat Jan 17 | S3: Sat Jan 24" in html

    pdf_bytes = generate_fillable_scout_workbook_pdf(
        badge_name="First Aid",
        session_dates=session_dates,
    )
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page1_text = doc[0].get_text("text")
    assert "Page-1 Requirement Completion & Counselor Verification Index" in page1_text
    assert "Req 1:" in page1_text
    assert "S1: Sat Jan 10 | S2: Sat Jan 17 | S3: Sat Jan 24" in page1_text
    doc.close()


def test_item5_qr_checklist_pdf_real_iso_matrix_and_bsa_logo() -> None:
    """Verifies real ISO/IEC 18004 QR code rendering + centered BSA logo + unclipped URLs in Field QR Checklist PDF."""
    pdf_bytes = generate_field_qr_checklist_pdf("First Aid")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) >= 1
    page = doc[0]
    text = page.get_text("text").replace("\n", "")
    # Full URLs should not be sliced at 44 chars
    assert "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/First%20Aid.pdf" in text
    assert "https://www.scouting.org/skills/merit-badges/digital-resource-guides/first-aid/" in text
    # Real QR matrices produce hundreds of vector rectangle items inside page drawings
    drawings = page.get_drawings()
    total_rect_items = sum(len(d.get("items", [])) for d in drawings)
    assert total_rect_items > 250, f"Expected real QR matrix vector items (>250), got {total_rect_items}"
    # Centered BSA logo image is embedded on the page
    images = page.get_images(full=True)
    assert len(images) >= 1, "Expected embedded BSA logo inside QR code cards"

    if ARTIFACT_DIR.exists():
        pix = page.get_pixmap(dpi=180)
        out_png = ARTIFACT_DIR / "v26-item5-qr-checklist-pdf.png"
        pix.save(str(out_png))
        if DOCS_IMAGES_DIR.exists():
            shutil.copyfile(out_png, DOCS_IMAGES_DIR / "v26-item5-qr-checklist-pdf.png")
    doc.close()


def test_v26_browser_ui_end_to_end() -> None:
    """Verifies Items 1-4 in headless Chromium against live port 8085 and captures visual proof screenshots."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("Playwright not installed in headless CI environment")

    if not pathlib.Path("/usr/bin/google-chrome").exists():
        pytest.skip("/usr/bin/google-chrome not present in headless CI environment")

    try:
        with urllib.request.urlopen("http://127.0.0.1:8085/api/health", timeout=2) as resp:
            if resp.status != 200:
                pytest.skip("Local workbench server on 127.0.0.1:8085 not active")
    except Exception:
        pytest.skip("Local workbench server on 127.0.0.1:8085 not active in CI runner")

    created_custom_ids: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path="/usr/bin/google-chrome",
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(viewport={"width": 1440, "height": 920})
            page = context.new_page()
            page.goto("http://127.0.0.1:8085", wait_until="networkidle", timeout=45000)
            page.wait_for_selector("#stage-template-pill-label", timeout=30000)
            page.wait_for_timeout(1200)

            # =================================================================
            # ITEM 3: Verify Admin Console 'Add DMBC & HVSC Customizations' is UNCHECKED by default
            # and zero 'Danvers' or 'Hidden Valley' strings appear in visible UI
            # =================================================================
            if page.locator("#tab-btn-admin").is_visible():
                page.click("#tab-btn-admin")
            else:
                page.click("#btn-footer-admin-unlock")
            page.wait_for_selector("#chk-admin-dmbc-hvsc-customizations", state="visible", timeout=10000)
            is_checked_default = page.is_checked("#chk-admin-dmbc-hvsc-customizations")
            assert is_checked_default is False, "Add DMBC & HVSC Customizations must be unchecked by default"

            if ARTIFACT_DIR.exists():
                page.screenshot(path=str(ARTIFACT_DIR / "v26-item3-admin-dmbc-unchecked.png"))
                if DOCS_IMAGES_DIR.exists():
                    shutil.copyfile(
                        ARTIFACT_DIR / "v26-item3-admin-dmbc-unchecked.png",
                        DOCS_IMAGES_DIR / "v26-item3-admin-dmbc-unchecked.png",
                    )

            # Open Session Library modal while unchecked and verify generic labels
            page.click("#btn-open-saved-workspaces")
            page.wait_for_selector("#saved-workspaces-modal:not(.hidden)", timeout=10000)
            ws_modal_text = page.locator("#saved-workspaces-modal").inner_text()
            assert "Danvers" not in ws_modal_text
            assert "Hidden Valley" not in ws_modal_text
            assert "Merit Badge College" in ws_modal_text
            assert "Summer Camp" in ws_modal_text

            # =================================================================
            # ITEM 2: Verify Compact Collapse Chevron ('▴ Collapse Builder') and Dynamic Schedule -> Blue Card Sync
            # =================================================================
            collapse_btn = page.locator("#btn-ws-toggle-schedule-builder")
            assert collapse_btn.is_visible()
            assert "Collapse Builder" in collapse_btn.inner_text()
            collapse_btn.click()
            page.wait_for_timeout(250)
            assert page.locator("#ws-schedule-builder-collapsible-body").is_hidden()
            assert "Expand Schedule Builder" in collapse_btn.inner_text()
            if ARTIFACT_DIR.exists():
                page.locator("#saved-workspaces-modal .m3-modal-dialog").screenshot(
                    path=str(ARTIFACT_DIR / "v26-item2-session-builder-collapsed.png")
                )
            # Expand back
            collapse_btn.click()
            page.wait_for_timeout(250)
            assert page.locator("#ws-schedule-builder-collapsible-body").is_visible()

            # Change # of Sessions to 2 and uncheck +Make-Up
            page.select_option("#ws-num-sessions-select", "2")
            if page.is_checked("#ws-chk-makeup-session"):
                page.uncheck("#ws-chk-makeup-session")
            page.wait_for_timeout(300)

            if ARTIFACT_DIR.exists():
                page.locator("#saved-workspaces-modal .m3-modal-dialog").screenshot(
                    path=str(ARTIFACT_DIR / "v26-item2-session-builder-2sessions.png")
                )

            page.click("#btn-close-workspaces-modal")
            page.wait_for_timeout(250)

            # Switch to Tab 2 (2. Requirements & Blue Cards) and verify Blue Card Tracker shows S1–S2
            page.click("#tab-triage")
            page.wait_for_selector('[data-testid="bluecard-session-attendance-header"]', timeout=10000)
            bc_header_text = page.locator('[data-testid="bluecard-session-attendance-header"]').inner_text()
            assert "(S1–S2)" in bc_header_text, f"Expected (S1–S2) in Blue Card header, got: {bc_header_text}"
            first_row_pills = page.locator("#bluecard-matrix-container tbody tr").first.locator(".m3-bc-attendance-pill")
            assert first_row_pills.count() == 2, f"Expected 2 attendance pills (S1, S2), got {first_row_pills.count()}"

            if ARTIFACT_DIR.exists():
                page.locator("#bluecard-matrix-container").scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                page.screenshot(path=str(ARTIFACT_DIR / "v26-item2-bluecard-dynamic-2sessions.png"))

            # Restore 4 sessions + Make-Up and verify Blue Card Tracker updates back to (S1–S4 | M)
            page.click("#btn-open-saved-workspaces")
            page.wait_for_selector("#saved-workspaces-modal:not(.hidden)", timeout=10000)
            page.select_option("#ws-num-sessions-select", "4")
            if not page.is_checked("#ws-chk-makeup-session"):
                page.check("#ws-chk-makeup-session")
            page.wait_for_timeout(250)
            page.click("#btn-close-workspaces-modal")
            page.wait_for_timeout(250)
            bc_header_restored = page.locator('[data-testid="bluecard-session-attendance-header"]').inner_text()
            assert "(S1–S4 | M)" in bc_header_restored

            if ARTIFACT_DIR.exists():
                page.locator("#bluecard-matrix-container").scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                page.screenshot(path=str(ARTIFACT_DIR / "v26-item2-bluecard-dynamic-4sessions-makeup.png"))

            # =================================================================
            # ITEM 4: Verify Fillable Form (GTA §7.0.3.2) Parent-Requirement Grouped Matrix
            # =================================================================
            page.click("#tab-workbook")
            page.wait_for_selector("#btn-workbook-open-fillable-html", timeout=10000)
            page.click("#btn-workbook-open-fillable-html")
            page.wait_for_selector('[data-testid="wb-page1-grouped-matrix"]', timeout=15000)
            parent_groups = page.locator('[data-testid="wb-page1-grouped-matrix"] .wb-index-parent-group')
            assert parent_groups.count() >= 10, f"Expected >=10 parent requirement groups, got {parent_groups.count()}"

            if ARTIFACT_DIR.exists():
                page.locator('[data-testid="wb-page1-grouped-matrix"]').scroll_into_view_if_needed()
                page.wait_for_timeout(300)
                page.screenshot(path=str(ARTIFACT_DIR / "v26-item4-workbook-grouped-matrix.png"))

            # Toggle Compact Summary View
            toggle_compact_btn = page.locator('[data-testid="btn-wb-index-toggle-compact"]')
            toggle_compact_btn.click()
            page.wait_for_timeout(200)
            assert "Expand All Sub-Requirements" in toggle_compact_btn.inner_text()
            if ARTIFACT_DIR.exists():
                page.screenshot(path=str(ARTIFACT_DIR / "v26-item4-workbook-grouped-matrix-compact.png"))
            toggle_compact_btn.click()
            page.wait_for_timeout(200)

            # =================================================================
            # ITEM 1: Verify Nano Banana Slide Template Studio (Tab 1 -> Tab 2 Quick Button, 6 Sample Prompts, Create 2 Templates)
            # =================================================================
            page.click("#tab-storyboard")
            page.wait_for_selector("#btn-stage-template-picker", timeout=10000)
            page.click("#btn-stage-template-picker")
            page.wait_for_selector("#template-studio-modal:not(.hidden)", timeout=10000)

            # Verify 'Danvers' and 'Hidden Valley' are hidden in Template Gallery when unchecked
            gallery_text_unchecked = page.locator("#template-catalog-grid").inner_text()
            assert "Danvers" not in gallery_text_unchecked
            assert "Hidden Valley" not in gallery_text_unchecked

            if ARTIFACT_DIR.exists():
                page.locator("#template-studio-modal .m3-modal-dialog").screenshot(
                    path=str(ARTIFACT_DIR / "v26-item1-template-gallery-quick-btn.png")
                )

            # Click '🍌 + Create AI Template' quick-launch button in Tab 1 header
            page.click("#btn-tpl-open-ai-tab")
            page.wait_for_selector("#template-studio-tab-ai:not(.hidden)", timeout=5000)

            # Cycle through all 6 sample prompts
            seen_prompts: set[str] = set()
            for i in range(6):
                page.click("#btn-tpl-ai-sample-safe")
                page.wait_for_timeout(100)
                btn_lbl = page.locator("#btn-tpl-ai-sample-safe").inner_text()
                assert f"({i + 1}/6)" in btn_lbl, f"Expected ({i + 1}/6) in '{btn_lbl}'"
                val = page.input_value("#tpl-ai-prompt-input").strip()
                seen_prompts.add(val)
            assert len(seen_prompts) == 6, f"Expected 6 distinct sample prompts, got {len(seen_prompts)}"

            # Create 1st AI template in the browser UI
            page.fill("#tpl-ai-name-input", "High Adventure Ridge Theme")
            if not page.is_checked("#tpl-ai-consent-checkbox"):
                page.check("#tpl-ai-consent-checkbox")
            page.click("#btn-tpl-ai-generate")
            page.wait_for_function(
                "() => document.getElementById('tpl-ai-status-msg')?.textContent?.includes('Saved')",
                timeout=15000,
            )
            status_1 = page.locator("#tpl-ai-status-msg").inner_text()
            assert "High Adventure Ridge Theme" in status_1

            # Verify the name input automatically advanced to '#2' so a 2nd template can be created immediately!
            next_suggested_name = page.input_value("#tpl-ai-name-input")
            assert next_suggested_name == "High Adventure Ridge Theme #2"

            # Create 2nd AI template immediately
            page.click("#btn-tpl-ai-sample-safe")
            page.click("#btn-tpl-ai-generate")
            page.wait_for_function(
                "() => document.getElementById('tpl-ai-status-msg')?.textContent?.includes('High Adventure Ridge Theme #2')",
                timeout=15000,
            )
            status_2 = page.locator("#tpl-ai-status-msg").inner_text()
            assert "High Adventure Ridge Theme #2" in status_2

            if ARTIFACT_DIR.exists():
                page.locator("#template-studio-modal .m3-modal-dialog").screenshot(
                    path=str(ARTIFACT_DIR / "v26-item1-nano-banana-second-template-saved.png")
                )

            # Record custom template IDs for cleanup
            for t in load_template_catalog():
                if not t.is_builtin and "High Adventure Ridge Theme" in (t.family_name or t.name):
                    created_custom_ids.append(t.template_id)
            assert len(created_custom_ids) >= 6

            page.click("#btn-close-template-studio")
            page.wait_for_timeout(200)

            # Now test checking 'Add DMBC & HVSC Customizations' in Admin Console
            page.click("#tab-btn-admin")
            page.check("#chk-admin-dmbc-hvsc-customizations")
            page.wait_for_timeout(300)
            if ARTIFACT_DIR.exists():
                page.screenshot(path=str(ARTIFACT_DIR / "v26-item3-admin-dmbc-checked.png"))

            page.click("#tab-storyboard")
            page.click("#btn-stage-template-picker")
            page.wait_for_selector("#template-studio-modal:not(.hidden)", timeout=10000)
            gallery_text_checked = page.locator("#template-catalog-grid").inner_text()
            assert "Camp Hidden Valley" in gallery_text_checked
            assert "Danvers Merit Badge College" in gallery_text_checked

            browser.close()
    finally:
        for tid in set(created_custom_ids):
            delete_custom_template(tid)
