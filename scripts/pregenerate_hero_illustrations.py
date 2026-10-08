#!/usr/bin/env python3
"""Batch pre-generator for Scope Tier 2 (23 Prepopulated Merit Badges) Nano Banana Hero Illustrations.

Uses the Option E Content-Aware Hybrid Mix (`resolve_content_aware_visual_config`) to route each
`REQUIREMENT_INTRO` slide across the 23 prepopulated badges to its optimal visual paradigm:
- `4-Quadrant Concept Map` (foundational / triage / multi-part overview requirements)
- `Photorealistic Image` with `include_humans=False` (equipment flat-lays, kits, instruments, weather/astronomy)
- `3D Isometric Illustration` with `include_humans=False` (robotics/mechanical/kit comparisons)
- `Watercolor Field Sketch` / `Line Drawing` with `include_humans=True` (step-by-step procedures, knots, bandages, splints)
- `Photorealistic Image` with `include_humans=True` (hands-on outdoor field action in Adult Scouts BSA Field Uniforms)

All generated images are downscaled to 800x600 and quantized to 256-color optimized PNGs (~80-210 KB)
in `assets/ai_illustrations/{badge_slug}_req_{req_slug}_nano_hero.png`.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agents.beautifier import AI_ILLUSTRATIONS_DIR  # noqa: E402
from src.agents.image_studio import (  # noqa: E402
    _try_live_ai_image_synthesis,
    compress_hero_illustration,
    resolve_content_aware_visual_config,
)
from src.agents.planner import generate_slide_storyboard  # noqa: E402
from src.config import get_merit_badge_metadata  # noqa: E402
from src.tools.scouting_scraper import (  # noqa: E402
    MeritBadgeResearchRequest,
    fetch_merit_badge_pamphlet_pdf,
)

SCOPE_TIER_2_BADGES: List[str] = [
    "First Aid",
    "Camping",
    "Weather",
    "Robotics",
    "Archery",
    "Astronomy",
    "Canoeing",
    "Citizenship in the Community",
    "Citizenship in the Nation",
    "Citizenship in the World",
    "Communication",
    "Cooking",
    "Cycling",
    "Emergency Preparedness",
    "Environmental Science",
    "Family Life",
    "Hiking",
    "Lifesaving",
    "Personal Fitness",
    "Personal Management",
    "Sustainability",
    "Swimming",
    "Wilderness Survival",
]


def _slugify(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(text or "").strip().lower()).strip("_")


def collect_tier2_hero_tasks(badges: List[str]) -> List[Dict[str, Any]]:
    """Collects all REQUIREMENT_INTRO slide hero tasks across the specified Merit Badges."""
    tasks: List[Dict[str, Any]] = []

    for badge in badges:
        meta = get_merit_badge_metadata(badge) or {}
        req = MeritBadgeResearchRequest(badge_name=badge)
        pamphlet = fetch_merit_badge_pamphlet_pdf(req)
        reqs = pamphlet.get("requirements") or []
        sb = generate_slide_storyboard(
            badge_name=badge,
            requirements=reqs,
            depth_mode="Deep Dive / Camp School Deck",
            is_eagle_required=bool(meta.get("is_eagle_required")),
        )
        slides = sb.get("slides") or []
        slug = _slugify(badge)
        seen_req_slugs: set[str] = set()

        for s in slides:
            if str(s.get("archetype") or "").upper() != "REQUIREMENT_INTRO":
                continue
            req_num = str(s.get("req_number") or "1").strip()
            req_slug = _slugify(req_num) or "1"
            if req_slug in seen_req_slugs:
                continue
            seen_req_slugs.add(req_slug)

            title = str(s.get("title") or f"{badge} Requirement {req_num}").strip()
            bps = [str(b).strip() for b in (s.get("bullet_points") or []) if str(b).strip()]
            bps_summary = ". ".join(bps[:3])
            visual_prompt = f"{title}. {bps_summary}" if bps_summary else f"{badge} Requirement {req_num}: {title}."

            cfg = resolve_content_aware_visual_config(
                badge_name=badge,
                slide_title=title,
                req_number=req_num,
                bullet_points=bps,
                custom_prompt="",
                visual_style="Auto (Option E Content-Aware Mix)",
                include_humans="auto",
            )
            out_path = AI_ILLUSTRATIONS_DIR / f"{slug}_req_{req_slug}_nano_hero.png"
            tasks.append(
                {
                    "badge_name": badge,
                    "badge_slug": slug,
                    "req_number": req_num,
                    "req_slug": req_slug,
                    "slide_title": title,
                    "bullet_points": bps,
                    "visual_prompt": visual_prompt,
                    "config": cfg,
                    "out_path": out_path,
                }
            )
    return tasks


def _execute_single_hero_task(task: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
    out_path: Path = task["out_path"]
    if not force and out_path.exists() and out_path.stat().st_size > 4_000:
        # Ensure existing file is compressed to 800x600 if it's still > 400KB raw
        raw_sz = out_path.stat().st_size
        if raw_sz > 400_000:
            compressed = compress_hero_illustration(out_path.read_bytes(), target_size=(800, 600))
            if compressed and len(compressed) >= 3_000:
                out_path.write_bytes(compressed)
        return {
            "status": "CACHED",
            "badge": task["badge_name"],
            "req": task["req_number"],
            "style": task["config"]["effective_style"],
            "include_humans": task["config"]["include_humans"],
            "size_kb": round(out_path.stat().st_size / 1024.0, 1),
            "path": str(out_path),
        }

    cfg = task["config"]
    seed_int = (
        int(
            hashlib.md5(
                f"{task['badge_slug']}:{task['req_slug']}:{task['slide_title']}".encode("utf-8")
            ).hexdigest()[:6],
            16,
        )
        % 99999
    )

    t0 = time.time()
    for attempt in range(1, 3):
        ok = _try_live_ai_image_synthesis(
            visual_subject=cfg["enriched_subject"],
            visual_style=cfg["effective_style"],
            seed_int=seed_int + attempt - 1,
            out_path=out_path,
            include_humans=bool(cfg["include_humans"]),
            compress_800x600=True,
        )
        if ok and out_path.exists() and out_path.stat().st_size > 4_000:
            elapsed = round(time.time() - t0, 1)
            return {
                "status": "GENERATED",
                "badge": task["badge_name"],
                "req": task["req_number"],
                "style": cfg["effective_style"],
                "include_humans": cfg["include_humans"],
                "size_kb": round(out_path.stat().st_size / 1024.0, 1),
                "elapsed_s": elapsed,
                "path": str(out_path),
            }
        time.sleep(1.5 * attempt)

    return {
        "status": "FAILED",
        "badge": task["badge_name"],
        "req": task["req_number"],
        "style": cfg["effective_style"],
        "include_humans": cfg["include_humans"],
        "size_kb": 0.0,
        "path": str(out_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-generate Option E Nano Banana hero illustrations.")
    parser.add_argument("--badges", nargs="*", help="Optional subset of badge names to generate.")
    parser.add_argument("--workers", type=int, default=4, help="Parallel worker count (default: 4).")
    parser.add_argument("--force", action="store_true", help="Re-generate even if cached file exists.")
    args = parser.parse_args()

    AI_ILLUSTRATIONS_DIR.mkdir(parents=True, exist_ok=True)
    target_badges = args.badges if args.badges else SCOPE_TIER_2_BADGES
    tasks = collect_tier2_hero_tasks(target_badges)
    print(f"Collected {len(tasks)} REQUIREMENT_INTRO hero tasks across {len(target_badges)} badges.")

    generated = 0
    cached = 0
    failed = 0
    total_kb = 0.0

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        future_map = {pool.submit(_execute_single_hero_task, t, args.force): t for t in tasks}
        for idx, fut in enumerate(as_completed(future_map), 1):
            res = fut.result()
            st = res["status"]
            if st == "GENERATED":
                generated += 1
            elif st == "CACHED":
                cached += 1
            else:
                failed += 1
            total_kb += float(res.get("size_kb") or 0.0)
            hum_tag = "Uniforms" if res["include_humans"] else "No-Humans"
            print(
                f"[{idx}/{len(tasks)}] {st}: {res['badge']} Req {res['req']} | "
                f"{res['style']} ({hum_tag}) | {res['size_kb']} KB"
            )

    print(
        f"\nSummary: {generated} generated, {cached} cached, {failed} failed | "
        f"Total compressed footprint: {total_kb / 1024.0:.2f} MB"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
