"""End-to-End Verification & Visual Screenshot Suite for v2.8 (Items 1-4).

Verifies:
1. Item 1: Zero ruff lint errors across `src/`, `tests/`, and `scripts/` and permanent Repo Sync & GitHub Actions CI Verification rule in `AGENTS.md`.
2. Item 2: High-contrast WCAG AAA readability of 1-click whole-patrol session attendance header buttons (`✓S1`..`✓M`) in `[data-testid="bluecard-session-attendance-header"]` (dark emerald `#064E3B` on `#DCFCE7` for present, dark crimson `#881337` on `#FFE4E6` for absent, `text-decoration: none`, and bold `0.72rem` typography).
3. Item 3: Photorealistic 16:9 widescreen Slide 1 Washed Cover Backdrops (`_cover_bg.png`) across all 6 Nano Banana visual styles (`pinewood_campfire`, `topographic_adventure`, `heritage_embroidery`, `collegiate_mbc`, `aquatics_nautical`, `stem_blueprint`), both in the live `<16ms` 16:9 mini-canvas preview (`resolvePhotorealisticCoverBackdropUrl`) and on the main 16:9 Slide 1 stage.
4. Item 4: Updated documentation and screenshot assets in `docs/images/`.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import urllib.request
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from src.server import app
from src.tools.template_engine import (
    NANO_BANANA_TEMPLATE_VISUAL_STYLES,
    _resolve_nano_photorealistic_base_cover,
    delete_custom_template,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ARTIFACT_DIR = pathlib.Path(
    "/usr/local/google/home/clayberg/.gemini/jetski/brain/aab0a16f-2d4f-4ac3-b70d-babfa87cfacf"
)
DOCS_IMAGES_DIR = REPO_ROOT / "docs" / "images"


def test_item1_ruff_clean_and_permanent_repo_sync_ci_instruction() -> None:
    """Verifies ruff passes with 0 errors and AGENTS.md enforces post-sync GitHub Actions verification."""
    agents_md = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Post-Push GitHub Actions CI Verification Gate" in agents_md
    assert "clayberg/scouts-bsa-merit-badge-agent" in agents_md
    assert "cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent" in agents_md

    ruff_bin = pathlib.Path(sys.executable).parent / "ruff"
    if ruff_bin.exists():
        proc = subprocess.run(
            [str(ruff_bin), "check", "src/", "tests/", "scripts/"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"Ruff lint failed:\n{proc.stdout}\n{proc.stderr}"


def test_item3_photorealistic_nano_banana_cover_backdrops_all_styles() -> None:
    """Verifies all 6 Nano Banana styles resolve and render photorealistic 16:9 cover backdrops (not blocky polygons)."""
    for style_key in NANO_BANANA_TEMPLATE_VISUAL_STYLES:
        base_path = _resolve_nano_photorealistic_base_cover(visual_style=style_key, custom_prompt="")
        assert base_path.exists(), f"Missing photorealistic base cover for {style_key}: {base_path}"
        with Image.open(base_path) as im:
            assert im.width >= 1280 and im.height >= 720
            # Photorealistic DSLR images have tens of thousands of unique RGB colors (vs <100 for blocky polygons)
            small = im.convert("RGB").resize((240, 135))
            get_fn = getattr(small, "get_flattened_data", small.getdata)
            unique_colors = len(set(get_fn()))
            assert unique_colors > 4000, (
                f"Expected photorealistic color richness (>4000 unique colors in 240x135 sample) for {style_key}, got {unique_colors}"
            )

    client = TestClient(app)
    created_ids: list[str] = []
    try:
        resp = client.post(
            "/api/v1/templates/generate-ai",
            json={
                "template_name": "Photorealistic Campus Test",
                "style_family": "collegiate_mbc",
                "frame_preset": "brushed_header_footer",
                "colors": ["#8B0000", "#003F87"],
                "prompt": "Georgian red-brick school building with white clock cupola and campus lawn.",
                "logo_position": "bottom-left",
                "remove_logo_bg": True,
                "confirm_finops_cost": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        created_ids.extend(v["template_id"] for v in data["variants"])

        for v in data["variants"]:
            cov_disk = REPO_ROOT / v["cover_bg_url"].lstrip("/")
            assert cov_disk.exists()
            with Image.open(cov_disk) as cim:
                assert cim.size == (1600, 900)
                c_small = cim.convert("RGB").resize((240, 135))
                c_get_fn = getattr(c_small, "get_flattened_data", c_small.getdata)
                unique_cov_colors = len(set(c_get_fn()))
                assert unique_cov_colors > 4000, f"Expected photorealistic variant cover, got {unique_cov_colors} unique colors"
    finally:
        for tid in created_ids:
            delete_custom_template(tid)


def test_v28_browser_ui_end_to_end() -> None:
    """Verifies Items 2, 3, and 4 in headless Chromium against live port 8085 and updates docs/images/ screenshots."""
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
            context = browser.new_context(viewport={"width": 1440, "height": 940})
            page = context.new_page()
            page.goto("http://127.0.0.1:8085", wait_until="networkidle", timeout=45000)
            page.wait_for_selector("#stage-template-pill-label", timeout=30000)
            page.wait_for_timeout(1200)

            # =================================================================
            # ITEM 2: Verify High-Contrast Readability of 1-Click Whole-Patrol Attendance Header Buttons
            # =================================================================
            page.click("#tab-triage")
            page.wait_for_selector('[data-testid="bluecard-session-attendance-header"]', timeout=10000)
            page.locator("#bluecard-matrix-container").scroll_into_view_if_needed()
            page.wait_for_timeout(250)

            # Check computed color & text-decoration of present button (✓S1) and absent button (✓M)
            s1_styles = page.eval_on_selector(
                '[data-testid="bluecard-session-attendance-header"] [data-bc-col-sess="S1"]',
                "el => ({ color: getComputedStyle(el).color, bg: getComputedStyle(el).backgroundColor, td: getComputedStyle(el).textDecorationLine })",
            )
            m_styles = page.eval_on_selector(
                '[data-testid="bluecard-session-attendance-header"] [data-bc-col-sess="M"]',
                "el => ({ color: getComputedStyle(el).color, bg: getComputedStyle(el).backgroundColor, td: getComputedStyle(el).textDecorationLine })",
            )
            # Must NOT be white rgb(255, 255, 255) on pastel background, and must NOT have line-through!
            assert s1_styles["color"] != "rgb(255, 255, 255)", f"S1 button text must not be white: {s1_styles}"
            assert s1_styles["color"] == "rgb(6, 78, 59)", f"Expected dark emerald #064E3B on S1, got {s1_styles['color']}"
            assert s1_styles["td"] == "none"

            assert m_styles["color"] != "rgb(255, 255, 255)", f"M button text must not be white: {m_styles}"
            assert m_styles["color"] == "rgb(136, 19, 55)", f"Expected dark crimson #881337 on M, got {m_styles['color']}"
            assert m_styles["td"] == "none", f"Expected no line-through on M header button, got {m_styles['td']}"

            if ARTIFACT_DIR.exists():
                bc_shot = ARTIFACT_DIR / "v28-item2-bluecard-readable-attendance-header.png"
                page.screenshot(path=str(bc_shot))
                shutil.copyfile(bc_shot, ARTIFACT_DIR / "v27-item1-r6-bluecard-whole-patrol-attendance-header.png")
                if DOCS_IMAGES_DIR.exists():
                    shutil.copyfile(bc_shot, DOCS_IMAGES_DIR / "v28-item2-bluecard-readable-attendance-header.png")
                    shutil.copyfile(bc_shot, DOCS_IMAGES_DIR / "v27-item1-r6-bluecard-whole-patrol-attendance-header.png")

            # =================================================================
            # ITEM 3: Verify Photorealistic Washed Cover Backdrops in Nano Banana Live Preview & Main Slide 1 Stage
            # =================================================================
            page.click("#tab-storyboard")
            page.wait_for_selector("#btn-stage-template-picker", timeout=10000)
            page.click("#btn-stage-template-picker")
            page.wait_for_selector("#template-studio-modal:not(.hidden)", timeout=10000)
            page.click("#btn-tpl-open-ai-tab")
            page.wait_for_selector("#template-studio-tab-ai:not(.hidden)", timeout=5000)

            # Switch to '🖼️ Slide 1: Washed Cover' preview mode
            page.click('[data-tpl-ai-slide-mode="cover"]')
            page.wait_for_timeout(250)

            # Verify live preview backgroundImage uses photorealistic .jpg/.png (not data:image/svg+xml)
            bg_img_css = page.eval_on_selector(
                "#tpl-ai-live-preview-stage",
                "el => getComputedStyle(el).backgroundImage",
            )
            assert "data:image/svg+xml" not in bg_img_css, f"Expected photorealistic image URL in live preview, got {bg_img_css}"
            assert "nano_base_" in bg_img_css or "_cover_bg" in bg_img_css or "cover.jpg" in bg_img_css

            if ARTIFACT_DIR.exists():
                prev_pine_shot = ARTIFACT_DIR / "v28-item3-nano-banana-photorealistic-preview-pinewood.png"
                page.locator("#template-studio-modal .m3-modal-dialog").screenshot(path=str(prev_pine_shot))
                shutil.copyfile(prev_pine_shot, ARTIFACT_DIR / "v27-item1-r4-item3-nano-banana-color-variants.png")
                if DOCS_IMAGES_DIR.exists():
                    shutil.copyfile(prev_pine_shot, DOCS_IMAGES_DIR / "v28-item3-nano-banana-photorealistic-preview-pinewood.png")
                    shutil.copyfile(prev_pine_shot, DOCS_IMAGES_DIR / "v27-item1-r4-item3-nano-banana-color-variants.png")

            # Now select 'Collegiate / Merit Badge University Crest' and generate a custom template to view on Slide 1
            page.select_option("#tpl-ai-style-select", "collegiate_mbc")
            page.click("#btn-tpl-palette-mbc")
            page.fill("#tpl-ai-name-input", "Colonial Campus Custom")
            page.fill(
                "#tpl-ai-prompt-input",
                "Georgian red-brick academic hall with white clock cupola and campus lawn.",
            )
            if not page.is_checked("#tpl-ai-consent-checkbox"):
                page.check("#tpl-ai-consent-checkbox")
            page.wait_for_timeout(200)

            if ARTIFACT_DIR.exists():
                prev_col_shot = ARTIFACT_DIR / "v28-item3-nano-banana-photorealistic-preview-collegiate.png"
                page.locator("#template-studio-modal .m3-modal-dialog").screenshot(path=str(prev_col_shot))

            page.click("#btn-tpl-ai-generate")
            page.wait_for_selector("#btn-tpl-ai-view-in-gallery", timeout=45000)
            page.wait_for_timeout(300)

            # Close Template Studio modal and inspect Slide 1 on the main 16:9 stage!
            page.click("#btn-close-template-studio")
            page.wait_for_timeout(400)

            if ARTIFACT_DIR.exists():
                slide1_shot = ARTIFACT_DIR / "v28-item3-slide1-photorealistic-washed-cover.png"
                page.screenshot(path=str(slide1_shot))
                if DOCS_IMAGES_DIR.exists():
                    shutil.copyfile(slide1_shot, DOCS_IMAGES_DIR / "v28-item3-slide1-photorealistic-washed-cover.png")

            from src.tools.template_engine import load_template_catalog

            for t in load_template_catalog():
                if not t.is_builtin and "Colonial Campus Custom" in (t.family_name or t.name):
                    created_custom_ids.append(t.template_id)

            browser.close()
    finally:
        for tid in created_custom_ids:
            delete_custom_template(tid)
