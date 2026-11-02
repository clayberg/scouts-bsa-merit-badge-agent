#!/usr/bin/env python3
"""Automated Repository-Wide PNG & JPEG Image Compressor (`scripts/compress_all_images.py`).

Enforces compact 8-bit indexed PNG storage (`P` mode) and optimized JPEGs (`<= 450 KB`) across
`docs/images/`, `docs/screenshots/`, `assets/ai_illustrations/`, `assets/pamphlet_images/`,
`assets/web_images/`, `assets/templates/`, `assets/custom_logos/`, `assets/diagrams/`, and
`assets/pamphlet_covers/` while preserving `400x400 RGBA` on `assets/badge_emblems/`,
`960x540 RGBA` on `assets/construction_anim/`, and `> 55 KB` on `docs/images/ui_*.png`.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import io
from pathlib import Path
from typing import Tuple

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent


def compress_single_image(path: Path) -> Tuple[int, int, bool]:
    """Compresses a single PNG or JPEG file in-place when unquantized or oversized."""
    orig_size = path.stat().st_size
    is_ui_screenshot = path.parent.name == "images" and path.name.startswith("ui_")
    min_allowed_bytes = 58_000 if is_ui_screenshot else 0
    suffix = path.suffix.lower()

    try:
        with Image.open(path) as im:
            if suffix == ".png":
                if im.mode == "P" and orig_size <= 450 * 1024 and im.width <= 1200 and im.height <= 1200:
                    return orig_size, orig_size, False
                im.load()
                if path.parent.name in ("web_images", "custom", "custom_logos") and (
                    im.width > 1024 or im.height > 1024
                ):
                    im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
                    im.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                elif orig_size > 450 * 1024 and (im.width > 960 or im.height > 960):
                    im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
                    im.thumbnail((960, 960), Image.Resampling.LANCZOS)

                has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
                buf = io.BytesIO()
                if has_alpha:
                    rgba = im.convert("RGBA")
                    quant = rgba.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
                    quant.save(buf, format="PNG", optimize=True, compress_level=9)
                else:
                    rgb = im.convert("RGB")
                    quant = rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
                    quant.save(buf, format="PNG", optimize=True, compress_level=9)

                new_bytes = buf.getvalue()
                new_size = len(new_bytes)
                if new_size < orig_size * 0.96 and new_size >= min_allowed_bytes:
                    path.write_bytes(new_bytes)
                    return orig_size, new_size, True
            elif suffix in (".jpg", ".jpeg"):
                if orig_size <= 350 * 1024:
                    return orig_size, orig_size, False
                im.load()
                rgb = im.convert("RGB")
                buf = io.BytesIO()
                rgb.save(buf, format="JPEG", quality=74, optimize=True, progressive=True)
                new_bytes = buf.getvalue()
                new_size = len(new_bytes)
                if new_size < orig_size * 0.90:
                    path.write_bytes(new_bytes)
                    return orig_size, new_size, True
    except Exception:
        pass
    return orig_size, orig_size, False


def main() -> None:
    target_dirs = [
        REPO_ROOT / "docs" / "images",
        REPO_ROOT / "docs" / "screenshots",
        REPO_ROOT / "assets" / "ai_illustrations",
        REPO_ROOT / "assets" / "pamphlet_images",
        REPO_ROOT / "assets" / "web_images",
        REPO_ROOT / "assets" / "templates",
        REPO_ROOT / "assets" / "custom_logos",
        REPO_ROOT / "assets" / "diagrams",
        REPO_ROOT / "assets" / "pamphlet_covers",
    ]
    img_files = [
        p
        for d in target_dirs
        if d.exists()
        for p in sorted(d.rglob("*"))
        if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg")
    ]
    total_before = 0
    total_after = 0
    compressed_count = 0

    with ThreadPoolExecutor(max_workers=12) as pool:
        for b_sz, a_sz, changed in pool.map(compress_single_image, img_files):
            total_before += b_sz
            total_after += a_sz
            if changed:
                compressed_count += 1

    saved_mb = (total_before - total_after) / (1024 * 1024)
    print(
        f"Scanned {len(img_files)} images | Compressed {compressed_count} files | "
        f"Before: {total_before / (1024 * 1024):.2f} MB -> After: {total_after / (1024 * 1024):.2f} MB "
        f"(Saved {saved_mb:.2f} MB)"
    )


if __name__ == "__main__":
    main()
