#!/usr/bin/env python3
"""Capture real headless Chrome screenshots of the live Scouts BSA Merit Badge Counselor Workbench and Super-User Admin Console."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import pathlib
import shutil
import subprocess
import time
import httpx
from PIL import Image, ImageDraw, ImageFont
import websockets

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "images"
ARTIFACT_DIR = (
    pathlib.Path.home()
    / ".gemini"
    / "jetski"
    / "brain"
    / "aab0a16f-2d4f-4ac3-b70d-babfa87cfacf"
)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for c in candidates:
        if pathlib.Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


class CDPSession:
    def __init__(self, ws):
        self.ws = ws
        self.msg_id = 0
        self.scale = 1.5

    async def send(self, method: str, params: dict | None = None) -> dict:
        self.msg_id += 1
        cur_id = self.msg_id
        await self.ws.send(
            json.dumps({"id": cur_id, "method": method, "params": params or {}})
        )
        while True:
            raw = await self.ws.recv()
            resp = json.loads(raw)
            if resp.get("id") == cur_id:
                return resp.get("result", {})

    async def eval_js(self, expression: str):
        res = await self.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        return res.get("result", {}).get("value")

    async def set_viewport(
        self, width: int, height: int, scale: float = 1.5
    ) -> None:
        self.scale = scale
        await self.send(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": scale,
                "mobile": False,
            },
        )
        await asyncio.sleep(0.25)

    async def screenshot_full_viewport(self) -> Image.Image:
        res = await self.send(
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": False},
        )
        data = base64.b64decode(res["data"])
        return Image.open(io.BytesIO(data)).convert("RGB")

    async def screenshot_selector(
        self, selector: str, pad: int = 8
    ) -> Image.Image:
        """Scrolls element into view without sticky header overlap, takes a full viewport screenshot, and crops by bounding rect."""
        await self.eval_js(f"""
        (() => {{
            const hdr = document.querySelector('header.m3-top-app-bar, header');
            if (hdr) hdr.style.position = 'static';
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return null;
            el.scrollIntoView({{block: 'start', inline: 'nearest'}});
            window.scrollBy(0, -16);
        }})()
        """)
        await asyncio.sleep(0.35)
        rect = await self.eval_js(f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {{
                left: r.left,
                top: r.top,
                width: r.width,
                height: r.height
            }};
        }})()
        """)
        full = await self.screenshot_full_viewport()
        await self.eval_js("""
        (() => {
            const hdr = document.querySelector('header.m3-top-app-bar, header');
            if (hdr) hdr.style.position = '';
        })()
        """)
        if not rect:
            return full
        s = self.scale
        x0 = max(0, int((rect["left"] - pad) * s))
        y0 = max(0, int((rect["top"] - pad) * s))
        x1 = min(full.width, int((rect["left"] + rect["width"] + pad) * s))
        y1 = min(full.height, int((rect["top"] + rect["height"] + pad) * s))
        if x1 <= x0 + 20 or y1 <= y0 + 20:
            return full
        return full.crop((x0, y0, x1, y1))


def _stitch_vertical_cards(
    images: list[tuple[str, Image.Image]], target_width: int = 1800
) -> Image.Image:
    """Place multiple real browser screenshots cleanly in a labeled vertical stack."""
    pad = 24
    header_h = 44
    scaled_items: list[tuple[str, Image.Image]] = []
    total_h = pad
    for label, img in images:
        inner_w = target_width - pad * 2
        ratio = inner_w / img.width
        new_h = int(img.height * ratio)
        resized = img.resize((inner_w, new_h), Image.Resampling.LANCZOS)
        scaled_items.append((label, resized))
        total_h += header_h + new_h + pad

    canvas = Image.new("RGB", (target_width, total_h), (241, 245, 249))
    draw = ImageDraw.Draw(canvas)
    font_lbl = _font(20, bold=True)
    y = pad
    for label, img in scaled_items:
        draw.rounded_rectangle(
            (pad, y, target_width - pad, y + header_h + img.height),
            radius=12,
            fill=(255, 255, 255),
            outline=(203, 213, 225),
            width=2,
        )
        draw.rounded_rectangle(
            (pad, y, target_width - pad, y + header_h),
            radius=12,
            fill=(0, 63, 135),
        )
        draw.rectangle(
            (pad, y + header_h - 12, target_width - pad, y + header_h),
            fill=(0, 63, 135),
        )
        draw.text((pad + 16, y + 10), label, fill=(255, 255, 255), font=font_lbl)
        canvas.paste(img, (pad, y + header_h))
        y += header_h + img.height + pad
    return canvas


async def wait_for_deck_ready(cdp: CDPSession, timeout_s: float = 40.0) -> None:
    for _ in range(int(timeout_s * 4)):
        ready = await cdp.eval_js(
            "Boolean(state && state.currentResult && state.currentResult.storyboard && state.currentResult.storyboard.slides && state.currentResult.storyboard.slides.length > 0)"
        )
        if ready:
            await asyncio.sleep(0.6)
            return
        await asyncio.sleep(0.25)


def _start_fresh_server() -> tuple[str, subprocess.Popen]:
    port = 8098
    srv = subprocess.Popen(
        [
            str(REPO_ROOT / ".venv" / "bin" / "uvicorn"),
            "src.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(45):
        try:
            r = httpx.get(f"{url}/health", timeout=1.5)
            if r.status_code == 200:
                return url, srv
        except Exception:
            pass
        time.sleep(0.3)
    srv.terminate()
    raise RuntimeError("Failed to start fresh uvicorn server on 8098")


async def capture_all() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base_url, srv_proc = _start_fresh_server()
    proc = subprocess.Popen(
        [
            "/usr/bin/google-chrome",
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--remote-debugging-port=9233",
            "--window-size=1680,1240",
            base_url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        ws_url = None
        for _ in range(40):
            try:
                r = httpx.get("http://127.0.0.1:9233/json")
                targets = [t for t in r.json() if t.get("type") == "page"]
                if targets:
                    ws_url = targets[0]["webSocketDebuggerUrl"]
                    break
            except Exception:
                pass
            await asyncio.sleep(0.25)

        if not ws_url:
            raise RuntimeError("Could not connect to headless Chrome on 9233")

        async with websockets.connect(ws_url, max_size=80_000_000) as ws:
            cdp = CDPSession(ws)
            await cdp.send("Page.enable")
            await cdp.send("Runtime.enable")
            await cdp.set_viewport(1680, 1240, scale=1.5)

            # Wait for initial First Aid deck to load
            await wait_for_deck_ready(cdp)

            # Hide Admin tab for Counselor User Guide screenshots and select a slide with a visible right-side image AND multiple image choices
            await cdp.eval_js("""
            (() => {
                if (typeof hideConstructionAnimation === 'function') hideConstructionAnimation();
                state.isAdminSession = false;
                document.getElementById('tab-btn-admin')?.classList.add('hidden');
                const slides = state.currentResult?.storyboard?.slides || [];
                let targetIdx = 4;
                for (let i = 0; i < slides.length; i++) {
                    const s = slides[i];
                    const arch = String(s.archetype || '');
                    const hasVis = Boolean(s.diagram_url) && !['CONCEPT_TEXT_SLIDE', 'ANNOTATED_INFOGRAPHIC_STAGE', 'REQUIREMENT_TRIAGE_MATRIX', 'SOURCES_AND_REFERENCES'].includes(arch);
                    if (hasVis && (s.slide_image_choices || []).length >= 2) {
                        targetIdx = i;
                        break;
                    }
                }
                state.activeSlideIdx = targetIdx;
                if (typeof renderActiveSlide === 'function') renderActiveSlide(targetIdx);
                if (typeof switchUnderstageTab === 'function') switchUnderstageTab('notes');
                window.scrollTo(0, 0);
            })()
            """)
            await asyncio.sleep(0.8)

            # 1. Full Workbench Overview Screenshot (Real browser viewport, Counselor view)
            overview_img = await cdp.screenshot_full_viewport()
            p1 = OUT_DIR / "workbench-overview-layout.png"
            overview_img.save(p1, optimize=True)
            print("Saved", p1, overview_img.size)

            # 2. Under-Stage Co-Design Bar (with Visual SVG Mini-Wireframes), Quick Edit & 4-Tab Image Studio Modal
            await cdp.eval_js("""
            (() => {
                document.getElementById('tab-btn-understage-codesign')?.click();
            })()
            """)
            await asyncio.sleep(0.5)
            codesign_shot = await cdp.screenshot_selector(
                "#understage-drawer", pad=8
            )

            await cdp.eval_js("""
            (() => {
                document.getElementById('btn-open-image-studio')?.click();
            })()
            """)
            await asyncio.sleep(0.6)
            studio_modal_shot = await cdp.screenshot_selector(
                "#image-studio-modal .m3-modal-dialog", pad=8
            )

            await cdp.eval_js("""
            (() => {
                document.getElementById('btn-close-image-studio')?.click();
                document.getElementById('tab-btn-understage-quickedit')?.click();
            })()
            """)
            await asyncio.sleep(0.5)
            quickedit_shot = await cdp.screenshot_selector(
                "#understage-drawer", pad=8
            )

            # Restore notes tab
            await cdp.eval_js("""
            (() => {
                document.getElementById('tab-btn-understage-notes')?.click();
            })()
            """)

            codesign_composite = _stitch_vertical_cards(
                [
                    (
                        "Under-Stage Drawer Tab 2: Customize Slide & Image Studio (Visual SVG Archetype Cards, Card Theme, Palette & Graphic)",
                        codesign_shot,
                    ),
                    (
                        "Popup Modal: Merit Badge Image Catalog & AI Image Studio (Catalog, Web Search, Nano Banana AI & File Upload)",
                        studio_modal_shot,
                    ),
                    (
                        "Under-Stage Drawer Tab 3: Quick Edit Slide Text, Teaching Cards & Speaker Notes",
                        quickedit_shot,
                    ),
                ],
                target_width=1800,
            )
            p4 = OUT_DIR / "codesign-and-image-studio.png"
            codesign_composite.save(p4, optimize=True)
            print("Saved", p4, codesign_composite.size)

            # 3. Counselor Field Toolkit: Tab 2 (Blue Card Bulk Roster + Date Stamp) + Tab 4 (4 Sub-Tabs + Patrol Skill Station Rotator)
            await cdp.set_viewport(1680, 1450, scale=1.5)
            await cdp.eval_js("""
            (() => {
                document.getElementById('tab-triage')?.click();
                document.getElementById('bluecard-bulk-paste-box')?.classList.remove('hidden');
            })()
            """)
            await asyncio.sleep(0.6)
            triage_shot = await cdp.screenshot_selector(
                "#bluecard-tracker-card", pad=8
            )

            await cdp.eval_js("""
            (() => {
                document.getElementById('tab-studiokit')?.click();
                const gearPill = document.querySelector('#studiokit-subtabs-bar [data-studiokit-filter="GEAR"]');
                if (gearPill) gearPill.click();
            })()
            """)
            await asyncio.sleep(0.6)
            studiokit_shot = await cdp.screenshot_selector(
                "#panel-studiokit", pad=8
            )

            toolkit_composite = _stitch_vertical_cards(
                [
                    (
                        "Top Tab 2 (Requirements & Blue Card Sign-Off): Patrol Blue Card (#34124) with Bulk Roster Paste & Completion Date Stamp",
                        triage_shot,
                    ),
                    (
                        "Top Tab 4 (Classroom Toolkit Sub-Tabs): Master Quartermaster Gear List & Patrol Skill Station Rotator Matrix",
                        studiokit_shot,
                    ),
                ],
                target_width=1800,
            )
            p5 = OUT_DIR / "counselor-field-toolkit.png"
            toolkit_composite.save(p5, optimize=True)
            print("Saved", p5, toolkit_composite.size)

            # 4. Super-User Admin Console Screenshot 1: Admin Tab 1 (Cached Image & Caption Studio) + On-Stage Popover Admin Shortcut
            await cdp.set_viewport(1680, 1320, scale=1.5)
            await cdp.eval_js("""
            (() => {
                state.isAdminSession = true;
                document.getElementById('tab-btn-admin')?.classList.remove('hidden');
                switchMainTab('panel-storyboard');
                const slides = state.currentResult?.storyboard?.slides || [];
                let targetIdx = 4;
                for (let i = 0; i < slides.length; i++) {
                    const s = slides[i];
                    const arch = String(s.archetype || '');
                    const hasVis = Boolean(s.diagram_url) && !['CONCEPT_TEXT_SLIDE', 'ANNOTATED_INFOGRAPHIC_STAGE', 'REQUIREMENT_TRIAGE_MATRIX', 'SOURCES_AND_REFERENCES'].includes(arch);
                    if (hasVis && (s.slide_image_choices || []).length >= 2) {
                        targetIdx = i;
                        break;
                    }
                }
                state.activeSlideIdx = targetIdx;
                renderActiveSlide(targetIdx);
                document.getElementById('stage-pill-main')?.click();
            })()
            """)
            await asyncio.sleep(0.7)
            popover_stage_shot = await cdp.screenshot_selector(
                "#widescreen-slide-stage", pad=8
            )

            await cdp.eval_js("""
            (async () => {
                switchMainTab('panel-admin');
                document.getElementById('btn-admin-subtab-catalog')?.click();
                if (typeof loadAdminConsoleData === 'function') {
                    await loadAdminConsoleData();
                }
                const fourthCard = document.querySelector('#admin-catalog-grid [data-admin-card-idx="3"]');
                if (fourthCard) fourthCard.click();
            })()
            """)
            await asyncio.sleep(1.2)
            admin_tab1_shot = await cdp.screenshot_selector(
                "#panel-admin", pad=8
            )

            admin_catalog_composite = _stitch_vertical_cards(
                [
                    (
                        "Super-User Admin Console — Tab 1: Cached Image & Caption Studio (144-Badge Catalog Manager, Vision Recaption & Promote Default)",
                        admin_tab1_shot,
                    ),
                    (
                        "On-Stage Easy Slide Image Switcher Popover with Unlocked Super-User Shortcut (Admin: Edit Caption / Promote Default in Studio)",
                        popover_stage_shot,
                    ),
                ],
                target_width=1800,
            )
            p6 = OUT_DIR / "admin-console-catalog-studio.png"
            admin_catalog_composite.save(p6, optimize=True)
            print("Saved", p6, admin_catalog_composite.size)

            # 5. Super-User Admin Console Screenshot 2: Tab 2 (Zero-PII Telemetry & Swap Hotspots) + Tab 3 (Diagnostics & 144-Badge Health)
            await cdp.eval_js("""
            (async () => {
                document.getElementById('btn-admin-subtab-telemetry')?.click();
                if (typeof loadAdminZeroPiiTelemetry === 'function') {
                    await loadAdminZeroPiiTelemetry();
                }
            })()
            """)
            await asyncio.sleep(0.9)
            admin_tab2_shot = await cdp.screenshot_selector(
                "#panel-admin", pad=8
            )

            await cdp.set_viewport(1680, 1620, scale=1.5)
            await cdp.eval_js("""
            (async () => {
                document.getElementById('btn-admin-subtab-diagnostics')?.click();
                if (typeof loadAdminAssetDiagnostics === 'function') {
                    await loadAdminAssetDiagnostics();
                }
            })()
            """)
            await asyncio.sleep(1.2)
            admin_tab3_shot = await cdp.screenshot_selector(
                "#panel-admin", pad=8
            )

            admin_telemetry_composite = _stitch_vertical_cards(
                [
                    (
                        "Super-User Admin Console — Tab 2: Zero-PII Usage, Latency Percentiles & Visual Swap Hotspots",
                        admin_tab2_shot,
                    ),
                    (
                        "Super-User Admin Console — Tab 3: System Diagnostics, Resilience Circuit Breakers & 144-Badge Asset Health Matrix",
                        admin_tab3_shot,
                    ),
                ],
                target_width=1800,
            )
            p7 = OUT_DIR / "admin-console-telemetry-diagnostics.png"
            admin_telemetry_composite.save(p7, optimize=True)
            print("Saved", p7, admin_telemetry_composite.size)

            # Copy all screenshots to the artifact directory for viewing/embedding
            if ARTIFACT_DIR.exists():
                for p in [p1, p4, p5, p6, p7]:
                    shutil.copy2(p, ARTIFACT_DIR / p.name)
                    print("Copied to artifact dir:", ARTIFACT_DIR / p.name)

    finally:
        proc.terminate()
        srv_proc.terminate()


if __name__ == "__main__":
    asyncio.run(capture_all())
