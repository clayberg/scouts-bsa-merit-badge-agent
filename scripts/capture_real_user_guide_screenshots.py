#!/usr/bin/env python3
"""Capture real headless Chrome screenshots of the live Scouts BSA Merit Badge Counselor Workbench (`http://localhost:8080`)."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import pathlib
import shutil
import subprocess
import httpx
from PIL import Image, ImageDraw, ImageFont
import websockets

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "images"
ARTIFACT_DIR = pathlib.Path(
    "/usr/local/google/home/clayberg/.gemini/jetski/brain/aab0a16f-2d4f-4ac3-b70d-babfa87cfacf"
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
        """Scrolls element into view, takes a full viewport screenshot, and crops by bounding rect."""
        rect = await self.eval_js(f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return null;
            el.scrollIntoView({{block: 'center', inline: 'nearest'}});
            const r = el.getBoundingClientRect();
            return {{
                left: r.left,
                top: r.top,
                width: r.width,
                height: r.height
            }};
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


def _stitch_horizontal_cards(
    images: list[tuple[str, Image.Image]], target_width: int = 1920
) -> Image.Image:
    """Place 3 real browser screenshots side-by-side in a labeled horizontal triptych."""
    pad = 20
    header_h = 42
    n = len(images)
    col_w = (target_width - pad * (n + 1)) // n
    resized_list: list[tuple[str, Image.Image]] = []
    max_img_h = 0
    for label, img in images:
        ratio = col_w / img.width
        new_h = int(img.height * ratio)
        resized = img.resize((col_w, new_h), Image.Resampling.LANCZOS)
        resized_list.append((label, resized))
        if new_h > max_img_h:
            max_img_h = new_h

    total_h = pad * 2 + header_h + max_img_h
    canvas = Image.new("RGB", (target_width, total_h), (241, 245, 249))
    draw = ImageDraw.Draw(canvas)
    font_lbl = _font(18, bold=True)
    x = pad
    for label, img in resized_list:
        draw.rounded_rectangle(
            (x, pad, x + col_w, pad + header_h + img.height),
            radius=12,
            fill=(255, 255, 255),
            outline=(203, 213, 225),
            width=2,
        )
        draw.rounded_rectangle(
            (x, pad, x + col_w, pad + header_h),
            radius=12,
            fill=(0, 63, 135),
        )
        draw.rectangle(
            (x, pad + header_h - 12, x + col_w, pad + header_h),
            fill=(0, 63, 135),
        )
        draw.text((x + 14, pad + 10), label, fill=(255, 255, 255), font=font_lbl)
        canvas.paste(img, (x, pad + header_h))
        x += col_w + pad
    return canvas


async def wait_for_deck_ready(cdp: CDPSession, timeout_s: float = 35.0) -> None:
    for _ in range(int(timeout_s * 4)):
        ready = await cdp.eval_js(
            "Boolean(state && state.currentResult && state.currentResult.storyboard && state.currentResult.storyboard.slides && state.currentResult.storyboard.slides.length > 0)"
        )
        if ready:
            await asyncio.sleep(0.6)
            return
        await asyncio.sleep(0.25)


async def capture_all() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            "/usr/bin/google-chrome",
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--remote-debugging-port=9232",
            "--window-size=1680,1240",
            "http://localhost:8080",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        ws_url = None
        for _ in range(40):
            try:
                r = httpx.get("http://127.0.0.1:9232/json")
                targets = [t for t in r.json() if t.get("type") == "page"]
                if targets:
                    ws_url = targets[0]["webSocketDebuggerUrl"]
                    break
            except Exception:
                pass
            await asyncio.sleep(0.25)

        if not ws_url:
            raise RuntimeError("Could not connect to headless Chrome on 9232")

        async with websockets.connect(ws_url, max_size=80_000_000) as ws:
            cdp = CDPSession(ws)
            await cdp.send("Page.enable")
            await cdp.send("Runtime.enable")
            await cdp.set_viewport(1680, 1240, scale=1.5)

            # Wait for initial First Aid deck to load
            await wait_for_deck_ready(cdp)

            # Select Slide 3 (idx=1 in storyboard.slides, which is "Slide 3 • Req 1")
            await cdp.eval_js("""
            (() => {
                if (typeof hideConstructionAnimation === 'function') hideConstructionAnimation();
                state.activeSlideIdx = 1;
                if (typeof renderActiveSlide === 'function') renderActiveSlide(1);
                if (typeof switchUnderstageTab === 'function') switchUnderstageTab('notes');
                window.scrollTo(0, 0);
            })()
            """)
            await asyncio.sleep(0.8)

            # 1. Full Workbench Overview Screenshot (Real browser viewport)
            overview_img = await cdp.screenshot_full_viewport()
            p1 = OUT_DIR / "workbench-overview-layout.png"
            overview_img.save(p1, optimize=True)
            print("Saved", p1, overview_img.size)

            # 2. Real Scout Slide Construction Animations Triptych
            await cdp.eval_js("""
            (() => {
                document.getElementById('btn-toggle-construction-anim')?.click();
            })()
            """)
            await asyncio.sleep(0.5)

            anim_shots: list[tuple[str, Image.Image]] = []
            anim_specs = [
                (
                    "iso_heavy",
                    3,
                    "1. 3D Heavy Equipment (6 Frames) — Helicopter Emblem Hoist",
                ),
                (
                    "camp_pioneer",
                    2,
                    "2. 2D Camp Pioneering (4 Frames) — Field Sketch & Medallion",
                ),
                (
                    "clay_workshop",
                    2,
                    "3. 3D Slide-O-Matic (4 Frames) — Lodge Contraption",
                ),
            ]
            for concept_key, frame_idx, title_lbl in anim_specs:
                await cdp.eval_js(f"""
                (() => {{
                    state.constructionPlaying = false;
                    if (state.constructionTimerId) {{
                        clearInterval(state.constructionTimerId);
                        state.constructionTimerId = null;
                    }}
                    state.constructionConcept = {json.dumps(concept_key)};
                    if (typeof syncConstructionConceptButtons === 'function') {{
                        syncConstructionConceptButtons({json.dumps(concept_key)});
                    }}
                    if (typeof renderConstructionFrame === 'function') {{
                        renderConstructionFrame({frame_idx}, false);
                    }}
                }})()
                """)
                await asyncio.sleep(0.6)
                shot = await cdp.screenshot_selector(
                    "#slide-construction-stage", pad=6
                )
                anim_shots.append((title_lbl, shot))

            triptych_img = _stitch_horizontal_cards(
                anim_shots, target_width=1920
            )
            p2 = OUT_DIR / "construction-animations-triptych.png"
            triptych_img.save(p2, optimize=True)
            print("Saved", p2, triptych_img.size)

            # Close construction anim back to finished slides
            await cdp.eval_js("""
            (() => {
                document.getElementById('btn-close-construction-anim')?.click();
            })()
            """)
            await asyncio.sleep(0.5)

            # 3. Real Slide Polish Modes Comparison (Standard, Beautified, Studio) on Slide 3 (idx=1)
            polish_shots: list[tuple[str, Image.Image]] = []
            polish_modes = [
                (
                    "STANDARD",
                    "Standard Fast Deck — Crisp White (~$0.14)",
                ),
                (
                    "BEAUTIFIED",
                    "AI Beautified — Warm Cream + Hero Graphics (~$0.38)",
                ),
                (
                    "STUDIO",
                    "AI Studio — Dark Slate + Hero Graphics ($1.00 Budget)",
                ),
            ]
            for mode_val, mode_label in polish_modes:
                await cdp.eval_js(f"""
                (() => {{
                    const sel = document.getElementById('beautification-select');
                    if (sel) sel.value = {json.dumps(mode_val)};
                    if (state.currentResult) {{
                        state.currentResult.beautification_tier = {json.dumps(mode_val)};
                        const sl = state.currentResult.storyboard?.slides?.[1];
                        if (sl) sl.beautification_tier = {json.dumps(mode_val)};
                    }}
                    state.activeSlideIdx = 1;
                    if (typeof renderActiveSlide === 'function') renderActiveSlide(1);
                }})()
                """)
                await asyncio.sleep(0.5)
                shot = await cdp.screenshot_selector(
                    "#widescreen-slide-stage", pad=6
                )
                polish_shots.append((mode_label, shot))

            # Restore Beautified mode
            await cdp.eval_js("""
            (() => {
                const sel = document.getElementById('beautification-select');
                if (sel) sel.value = 'BEAUTIFIED';
                if (state.currentResult) {
                    state.currentResult.beautification_tier = 'BEAUTIFIED';
                    const sl = state.currentResult.storyboard?.slides?.[1];
                    if (sl) sl.beautification_tier = 'BEAUTIFIED';
                }
                if (typeof renderActiveSlide === 'function') renderActiveSlide(1);
            })()
            """)
            await asyncio.sleep(0.4)

            polish_img = _stitch_horizontal_cards(
                polish_shots, target_width=1920
            )
            p3 = OUT_DIR / "slide-polish-tiers-comparison.png"
            polish_img.save(p3, optimize=True)
            print("Saved", p3, polish_img.size)

            # 4. Under-Stage Co-Design Bar, Quick Edit & 4-Tab Image Studio Modal
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
                        "Under-Stage Drawer Tab 2: Customize Slide & Image Studio (Layout, Card Style, Palette, Graphic & Quick-Switch Image)",
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

            # 5. Counselor Field Toolkit: Tab 2 (Requirements & Blue Card Sign-Off) + Tab 4 (Agenda, Parent Letter & Quartermaster Gear Checklist)
            await cdp.set_viewport(1680, 1550, scale=1.5)
            await cdp.eval_js("""
            (() => {
                document.getElementById('tab-triage')?.click();
                window.scrollTo(0, 0);
            })()
            """)
            await asyncio.sleep(0.6)
            triage_shot = await cdp.screenshot_selector(
                "#bluecard-tracker-card", pad=8
            )

            await cdp.eval_js("""
            (() => {
                document.getElementById('tab-studiokit')?.click();
                window.scrollTo(0, 0);
            })()
            """)
            await asyncio.sleep(0.6)
            # Capture the top half of Tab 4 (Session Agenda + Parent Welcome Letter + Master Quartermaster Gear Checklist)
            studiokit_top = await cdp.eval_js("""
            (() => {
                const p = document.getElementById('panel-studiokit');
                const g = document.getElementById('studiokit-gear-checklist-card');
                if (!p || !g) return null;
                window.scrollTo(0, 0);
                const r1 = p.getBoundingClientRect();
                const r2 = g.getBoundingClientRect();
                return {
                    left: r1.left,
                    top: r1.top,
                    width: r1.width,
                    height: (r2.top + r2.height) - r1.top
                };
            })()
            """)
            full_sk = await cdp.screenshot_full_viewport()
            if studiokit_top:
                s = cdp.scale
                x0 = max(0, int((studiokit_top["left"] - 8) * s))
                y0 = max(0, int((studiokit_top["top"] - 8) * s))
                x1 = min(
                    full_sk.width,
                    int((studiokit_top["left"] + studiokit_top["width"] + 8) * s),
                )
                y1 = min(
                    full_sk.height,
                    int((studiokit_top["top"] + studiokit_top["height"] + 8) * s),
                )
                studiokit_shot = full_sk.crop((x0, y0, x1, y1))
            else:
                studiokit_shot = full_sk

            toolkit_composite = _stitch_vertical_cards(
                [
                    (
                        "Top Tab 2 (Requirements & Blue Card Sign-Off): Patrol Blue Card (#34124) & Scoutbook Plus Requirement Sign-Off Tracker",
                        triage_shot,
                    ),
                    (
                        "Top Tab 4 (Lesson Plan, Gear List, Parent Letter & FinOps): Session Agenda, Parent Letter & Quartermaster Gear Checklist",
                        studiokit_shot,
                    ),
                ],
                target_width=1800,
            )
            p5 = OUT_DIR / "counselor-field-toolkit.png"
            toolkit_composite.save(p5, optimize=True)
            print("Saved", p5, toolkit_composite.size)

            # Copy all 5 real screenshots to the artifact directory for viewing/embedding
            if ARTIFACT_DIR.exists():
                for p in [p1, p2, p3, p4, p5]:
                    shutil.copy2(p, ARTIFACT_DIR / p.name)
                    print("Copied to artifact dir:", ARTIFACT_DIR / p.name)

    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(capture_all())
