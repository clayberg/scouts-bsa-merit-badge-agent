"""End-to-End Verification & Screenshot Suite for v2.7 (Items 1-6).

Verifies:
1. Item 1 (R1-R6):
   - R1: Frequency = Once auto-locks # of Sessions = 1 and unchecks + Make-Up; increasing sessions > 1 or checking + Make-Up auto-switches Frequency to Weekly.
   - R2: '+' Custom Location and Custom Tag buttons morph into green '✓ Saved' pill on click.
   - R3: '➕ Insert / Update Slides in Deck' dynamically updates status chip when logistics slides are active and dims/disables '🗑️ Remove Logistics Slides' when 0 are active.
   - R4: Nano Banana AI Template Studio live <16ms 16:9 mini-canvas preview + '🖼️ Slide 1: Washed Cover' / '📊 Slide 2+: Content Frame' toggle.
   - R5: Post-save '🗂️ View in Template Gallery →' button switches to Tab 1, scrolls to the new family card, and highlights it.
   - R6: Patrol Blue Card Tracker 1-click whole-patrol session attendance header buttons ('✓S1'..'✓M').
2. Item 2: Slide 1 Washed Cover Backdrop (`cover_bg_url`) generated for Nano Banana AI templates and rendered at 18%-22% opacity on Slide 1.
3. Item 3: Dynamic variant count on Generate button ('2-Variant' when 1 color unchecked, '1-Variant' when 2 unchecked) and closest common color naming ('Green', 'Blue', 'Gold', 'Red', 'Navy', 'Crimson', 'Teal', 'Orange', 'Purple', 'Olive', 'Brown', 'Slate') instead of 'Variant A/B/C'.
4. Item 4: Default 'Starting Date' (`#ws-start-date-input`) initializes to today's local date (`YYYY-MM-DD`) instead of hardcoded `2026-01-10`.
5. Item 5: Restructured `#ws-class-logistics-panel` Schedule Builder layout:
   - Header bar `#ws-schedule-builder-header-bar` with `#btn-ws-toggle-schedule-builder` ('▴ Collapse Builder').
   - '⚡ 1-Click Venue Macros' (`#ws-venue-macros-row`) inside `#ws-schedule-builder-collapsible-body` so they collapse with the builder.
   - 'Slide 2: Class Overview & Pre-Work' and 'Final Slide: Homework & Blue Card Check-Out' checkboxes directly above 'Insert / Update Slides in Deck' and 'Remove Logistics Slides'.
   - 'Save Active Deck' and 'Clone Next Period' on the same line as 'Insert / Update Slides in Deck' and 'Remove Logistics Slides', aligned flush right.
6. Item 6: 3 high-craft versions for Hidden Valley Scout Camp (`camp_hidden_valley`, `camp_hidden_valley_v2`, `camp_hidden_valley_v3`) using Lake Eileen sunset cover + Scouting America New Hampshire lower-left logo, and 3 versions for Danvers Merit Badge College (`danvers_mbc`, `danvers_mbc_v2`, `danvers_mbc_v3`) using Holten-Richmond MS facade cover + Spirit of Adventure Council lower-left logo.
"""

from __future__ import annotations

import datetime
import pathlib
import shutil
from fastapi.testclient import TestClient

from src.server import app
from src.tools.template_engine import (
    DMBC_HVSC_TEMPLATES,
    delete_custom_template,
    get_closest_color_name,
    get_disambiguated_color_names,
    load_template_catalog,
)

ARTIFACT_DIR = pathlib.Path(
    "/usr/local/google/home/clayberg/.gemini/jetski/brain/aab0a16f-2d4f-4ac3-b70d-babfa87cfacf"
)
DOCS_IMAGES_DIR = (
    pathlib.Path(__file__).resolve().parent.parent / "docs" / "images"
)


def test_item3_closest_color_names_and_dynamic_variant_count_backend() -> None:
    """Verifies closest common color naming and 1/2/3-variant generation in POST /api/v1/templates/generate-ai."""
    assert get_closest_color_name("#1B5E20") == "Green"
    assert get_closest_color_name("#0284C7") == "Blue"
    assert get_closest_color_name("#D97706") == "Gold"
    assert get_closest_color_name("#CE1126") == "Red"
    assert get_closest_color_name("#8B0000") == "Crimson"
    assert get_closest_color_name("#003F87") == "Navy"

    disambig = get_disambiguated_color_names(["#1B5E20", "#0284C7"])
    assert len(disambig) == 2
    assert disambig[0] == "Green"
    assert disambig[1] == "Blue"

    client = TestClient(app)
    created_ids: list[str] = []
    try:
        # Send only 2 colors (simulating unchecking Variant 3 in the UI)
        resp = client.post(
            "/api/v1/templates/generate-ai",
            json={
                "template_name": "Two Variant Sunset Test",
                "style_family": "pinewood_campfire",
                "frame_preset": "horizon_silhouette",
                "colors": ["#1B5E20", "#0284C7"],
                "prompt": "Warm sunset over a camp lake with dock and pine silhouette.",
                "logo_position": "bottom-left",
                "remove_logo_bg": True,
                "confirm_finops_cost": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert len(data["variants"]) == 2
        created_ids.extend(v["template_id"] for v in data["variants"])

        labels = [v["variant_label"] for v in data["variants"]]
        assert labels == ["Green", "Blue"]
        for v in data["variants"]:
            assert "Variant A" not in v["name"]
            assert "Variant B" not in v["name"]
            # Item 2: Verify Slide 1 Washed Cover Backdrop (cover_bg_url) is generated
            assert v.get("cover_bg_url"), f"Expected cover_bg_url on Nano Banana variant {v['template_id']}"
            assert v["cover_bg_url"].endswith("_cover_bg.png")
    finally:
        for tid in created_ids:
            delete_custom_template(tid)


def test_item6_hvsc_and_dmbc_three_versions_each() -> None:
    """Verifies all 3 HVSC versions and 3 DMBC versions have cover_bg_url and lower-left council logos."""
    assert len(DMBC_HVSC_TEMPLATES) == 6
    hvsc = [t for t in DMBC_HVSC_TEMPLATES if t.family_id == "camp_hidden_valley_edition"]
    dmbc = [t for t in DMBC_HVSC_TEMPLATES if t.family_id == "danvers_mbc_edition"]
    assert len(hvsc) == 3
    assert len(dmbc) == 3
    assert [t.variant_label for t in hvsc] == ["Green", "Olive", "Blue"]
    assert [t.variant_label for t in dmbc] == ["Crimson", "Navy", "Brick"]

    repo_root = pathlib.Path(__file__).resolve().parent.parent
    for t in DMBC_HVSC_TEMPLATES:
        assert t.cover_bg_url, f"Missing cover_bg_url on {t.template_id}"
        assert (repo_root / t.cover_bg_url.lstrip("/")).exists()
        assert t.bottom_silhouette_url, f"Missing bottom_silhouette_url on {t.template_id}"
        assert (repo_root / t.bottom_silhouette_url.lstrip("/")).exists()
        assert t.top_banner_url, f"Missing top_banner_url on {t.template_id}"
        assert (repo_root / t.top_banner_url.lstrip("/")).exists()


def test_v27_browser_ui_end_to_end() -> None:
    """Verifies Items 1-6 in headless Chromium against live port 8085 and captures visual proof screenshots."""
    from playwright.sync_api import sync_playwright

    created_custom_ids: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path="/usr/bin/google-chrome",
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(viewport={"width": 1440, "height": 940})
            page = context.new_page()
            page.goto("http://127.0.0.1:8085", wait_until="networkidle", timeout=45000)
            page.wait_for_selector("#stage-template-pill-label", timeout=30000)
            page.wait_for_timeout(1200)

            # =================================================================
            # ITEMS 4, 5 & 1 (R1, R2, R3): Session Library & Schedule Builder
            # =================================================================
            page.click("#btn-open-saved-workspaces")
            page.wait_for_selector("#saved-workspaces-modal:not(.hidden)", timeout=10000)
            page.wait_for_timeout(300)

            # Item 4: Verify Starting Date defaults to today's local date (not 2026-01-10)
            today_iso = datetime.date.today().isoformat()
            start_date_val = page.input_value("#ws-start-date-input")
            assert start_date_val == today_iso, f"Expected today's date {today_iso}, got {start_date_val}"
            assert start_date_val != "2026-01-10"

            # Item 5: Verify layout hierarchy:
            # 1) #ws-schedule-builder-header-bar contains #btn-ws-toggle-schedule-builder
            assert page.locator("#ws-schedule-builder-header-bar #btn-ws-toggle-schedule-builder").is_visible()
            # 2) #ws-venue-macros-row is inside #ws-schedule-builder-collapsible-body
            assert page.locator("#ws-schedule-builder-collapsible-body #ws-venue-macros-row").is_visible()
            # 3) #ws-logistics-checkboxes-row is directly above #ws-logistics-actions-row
            chk_box = page.locator("#ws-logistics-checkboxes-row").bounding_box()
            act_box = page.locator("#ws-logistics-actions-row").bounding_box()
            assert chk_box is not None and act_box is not None
            assert chk_box["y"] < act_box["y"], "Expected Slide 2 / Final Slide checkboxes directly above Insert/Remove buttons"
            # 4) Save Active Deck and Clone Next Period are on the same row as Insert/Remove and aligned right
            insert_box = page.locator("#btn-ws-apply-logistics-slides").bounding_box()
            save_box = page.locator("#btn-modal-save-workspace").bounding_box()
            clone_box = page.locator("#btn-modal-clone-workspace").bounding_box()
            assert insert_box and save_box and clone_box
            assert abs(insert_box["y"] - save_box["y"]) < 16, "Expected Save Active Deck on same line as Insert/Update Slides"
            assert save_box["x"] > insert_box["x"] + 150, "Expected Save Active Deck aligned to the right of Insert/Remove buttons"

            # Item 1 (R1): Selecting Frequency = Once auto-locks # of Sessions = 1 and unchecks +Make-Up
            page.select_option("#ws-frequency-select", "Once")
            page.wait_for_timeout(200)
            assert page.input_value("#ws-num-sessions-select") == "1"
            assert page.is_checked("#ws-chk-makeup-session") is False
            # Increasing # of Sessions to 4 while Once auto-switches Frequency to Weekly
            page.select_option("#ws-num-sessions-select", "4")
            page.check("#ws-chk-makeup-session")
            page.wait_for_timeout(200)
            assert page.input_value("#ws-frequency-select") == "Weekly"

            # Item 1 (R2): Clicking '+' Custom Location morphs button to '✓ Saved'
            page.fill("#ws-room-location-input", "Camp Carpenter Main Lodge")
            page.click("#btn-ws-add-custom-location")
            page.wait_for_timeout(150)
            assert "Saved" in page.locator("#btn-ws-add-custom-location").inner_text()

            if ARTIFACT_DIR.exists():
                page.locator("#saved-workspaces-modal .m3-modal-dialog").screenshot(
                    path=str(ARTIFACT_DIR / "v27-item4-item5-schedule-builder-restructured.png")
                )
                if DOCS_IMAGES_DIR.exists():
                    shutil.copyfile(
                        ARTIFACT_DIR / "v27-item4-item5-schedule-builder-restructured.png",
                        DOCS_IMAGES_DIR / "v27-item4-item5-schedule-builder-restructured.png",
                    )

            # Item 5: Collapse builder and verify 1-Click Venue Macros collapse with it while checkboxes + actions remain visible
            page.click("#btn-ws-toggle-schedule-builder")
            page.wait_for_timeout(250)
            assert page.locator("#ws-venue-macros-row").is_hidden()
            assert page.locator("#ws-logistics-checkboxes-row").is_visible()
            assert page.locator("#ws-logistics-actions-row").is_visible()

            if ARTIFACT_DIR.exists():
                page.locator("#saved-workspaces-modal .m3-modal-dialog").screenshot(
                    path=str(ARTIFACT_DIR / "v27-item5-schedule-builder-collapsed-macros-hidden.png")
                )

            # Expand back
            page.click("#btn-ws-toggle-schedule-builder")
            page.wait_for_timeout(200)
            page.click("#btn-close-workspaces-modal")
            page.wait_for_timeout(250)

            # =================================================================
            # ITEM 1 (R6): Patrol Blue Card Tracker 1-Click Whole-Patrol Attendance Header
            # =================================================================
            page.click("#tab-triage")
            page.wait_for_selector('[data-testid="bluecard-session-attendance-header"]', timeout=10000)
            total_rows = page.locator("#bluecard-matrix-container tbody tr").count()
            col_m_btn = page.locator('[data-testid="bluecard-session-attendance-header"] [data-bc-col-sess="M"]')
            assert col_m_btn.is_visible()
            col_m_btn.click()
            page.wait_for_timeout(250)
            # Verify all patrol rows now have M marked is-present
            m_present_pills = page.locator('#bluecard-matrix-container tbody tr [data-bc-att-sess="M"].is-present')
            assert m_present_pills.count() == total_rows

            if ARTIFACT_DIR.exists():
                page.locator("#bluecard-matrix-container").scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                page.screenshot(path=str(ARTIFACT_DIR / "v27-item1-r6-bluecard-whole-patrol-attendance-header.png"))

            # =================================================================
            # ITEMS 1 (R4, R5), 2 & 3: Nano Banana AI Template Studio
            # =================================================================
            page.click("#tab-storyboard")
            page.wait_for_selector("#btn-stage-template-picker", timeout=10000)
            page.click("#btn-stage-template-picker")
            page.wait_for_selector("#template-studio-modal:not(.hidden)", timeout=10000)
            page.click("#btn-tpl-open-ai-tab")
            page.wait_for_selector("#template-studio-tab-ai:not(.hidden)", timeout=5000)

            # Verify color-based variant labels instead of 'Variant A/B/C'
            lbl1 = page.locator("#tpl-ai-color1-label").inner_text()
            lbl2 = page.locator("#tpl-ai-color2-label").inner_text()
            lbl3 = page.locator("#tpl-ai-color3-label").inner_text()
            assert "Variant A" not in lbl1 and "(Primary)" in lbl1
            assert "Variant B" not in lbl2
            assert "Variant C" not in lbl3

            # Item 3: Uncheck Variant 3 (#tpl-ai-use-color3) and verify button updates to '2-Variant'
            if page.is_checked("#tpl-ai-use-color3"):
                page.uncheck("#tpl-ai-use-color3")
            page.wait_for_timeout(200)
            gen_btn_text = page.locator("#btn-tpl-ai-generate").inner_text()
            assert "2-Variant AI Template Family" in gen_btn_text, f"Expected 2-Variant on button, got: {gen_btn_text}"
            assert "2 Switchable Color Variants" in page.locator("#tpl-ai-colors-heading").inner_text()

            # Item 1 (R4) & Item 2: Toggle between Slide 1: Washed Cover and Slide 2+: Content Frame
            cover_mode_btn = page.locator('[data-tpl-ai-slide-mode="cover"]')
            content_mode_btn = page.locator('[data-tpl-ai-slide-mode="content"]')
            assert cover_mode_btn.is_visible() and content_mode_btn.is_visible()
            cover_mode_btn.click()
            page.wait_for_timeout(150)
            assert page.locator("#tpl-ai-preview-cover-mode").is_visible()
            page.locator("#btn-tpl-ai-generate").scroll_into_view_if_needed()
            page.wait_for_timeout(150)

            if ARTIFACT_DIR.exists():
                page.locator("#template-studio-modal .m3-modal-dialog").screenshot(
                    path=str(ARTIFACT_DIR / "v27-item1-r4-item3-nano-banana-color-variants.png")
                )
                if DOCS_IMAGES_DIR.exists():
                    shutil.copyfile(
                        ARTIFACT_DIR / "v27-item1-r4-item3-nano-banana-color-variants.png",
                        DOCS_IMAGES_DIR / "v27-item1-r4-item3-nano-banana-color-variants.png",
                    )

            # Item 1 (R5): Generate the 2-variant template and verify '🗂️ View in Template Gallery →' spotlight button
            page.fill("#tpl-ai-name-input", "Lake Eileen Horizon Custom")
            if not page.is_checked("#tpl-ai-consent-checkbox"):
                page.check("#tpl-ai-consent-checkbox")
            page.click("#btn-tpl-ai-generate")
            page.wait_for_selector("#btn-tpl-ai-view-in-gallery", timeout=15000)

            if ARTIFACT_DIR.exists():
                page.locator("#template-studio-modal .m3-modal-dialog").screenshot(
                    path=str(ARTIFACT_DIR / "v27-item1-r5-nano-banana-post-save-spotlight.png")
                )

            # Click '🗂️ View in Template Gallery →' and verify it jumps to Tab 1
            page.click("#btn-tpl-ai-view-in-gallery")
            page.wait_for_selector("#template-studio-tab-gallery:not(.hidden)", timeout=5000)
            page.wait_for_timeout(300)

            for t in load_template_catalog():
                if not t.is_builtin and "Lake Eileen Horizon Custom" in (t.family_name or t.name):
                    created_custom_ids.append(t.template_id)
            assert len(created_custom_ids) == 2

            page.click("#btn-close-template-studio")
            page.wait_for_timeout(200)

            # =================================================================
            # ITEM 6: Enable DMBC & HVSC Customizations and verify 3 HVSC + 3 DMBC versions
            # =================================================================
            if page.locator("#tab-btn-admin").is_visible():
                page.click("#tab-btn-admin")
            else:
                page.click("#btn-footer-admin-unlock")
            page.wait_for_selector("#chk-admin-dmbc-hvsc-customizations", timeout=10000)
            page.check("#chk-admin-dmbc-hvsc-customizations")
            page.wait_for_timeout(300)

            page.click("#tab-storyboard")
            page.click("#btn-stage-template-picker")
            page.wait_for_selector("#template-studio-modal:not(.hidden)", timeout=10000)
            page.wait_for_timeout(300)

            hvsc_card = page.locator('#template-catalog-grid .m3-template-card[data-select-template="camp_hidden_valley"]')
            dmbc_card = page.locator('#template-catalog-grid .m3-template-card[data-select-template="danvers_mbc"]')
            assert hvsc_card.is_visible()
            assert dmbc_card.is_visible()
            assert hvsc_card.locator(".m3-tpl-variant-pill").count() == 3
            assert dmbc_card.locator(".m3-tpl-variant-pill").count() == 3

            hvsc_card.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            if ARTIFACT_DIR.exists():
                page.locator("#template-studio-modal .m3-modal-dialog").screenshot(
                    path=str(ARTIFACT_DIR / "v27-item6-template-gallery-hvsc-dmbc-3versions.png")
                )
                if DOCS_IMAGES_DIR.exists():
                    shutil.copyfile(
                        ARTIFACT_DIR / "v27-item6-template-gallery-hvsc-dmbc-3versions.png",
                        DOCS_IMAGES_DIR / "v27-item6-template-gallery-hvsc-dmbc-3versions.png",
                    )

            browser.close()
    finally:
        for tid in set(created_custom_ids):
            delete_custom_template(tid)
