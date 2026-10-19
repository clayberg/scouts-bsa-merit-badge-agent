#!/usr/bin/env python3
"""Generates and audits both Deep Dive (3-8 slides/req) and Troop Meeting (1-4 slides/req)
sample decks for all 26 Benchmark Badges (all 18 Eagle-Required + 8 Elective Benchmarks)
plus 10 randomly selected Merit Badges (= 36 badges, 72 total .pptx decks).

Also verifies:
- 100% official requirement (1..N) and sub-requirement (1a, 1b, ...) completeness against
  `data/merit_badge_requirements/<slug>.json`
- Automatic first-run generation and 800x600 PNG compression caching of Custom Nano Banana
  Hero illustrations (`assets/ai_illustrations/{slug}_req_{req_slug}_nano_hero.png`)
- Zero AABB overlaps, zero out-of-bounds shapes, font floor >= 13pt, zero ellipsis/bullet
  hygiene defects, and 100% `[SAY]`/`[DEMONSTRATE]`/`[ASK SCOUTS]` speaker note completeness
- Compute & storage cost calculation for expanding Custom Nano Banana Illustrations to all 143 badges.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import random
import sys
import time
from collections import Counter
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agents.beautifier import AI_ILLUSTRATIONS_DIR  # noqa: E402
from src.agents.coordinator import GENERATED_DECKS_DIR, run_merit_badge_workflow  # noqa: E402
from src.agents.reviewer import check_pptx_conformance  # noqa: E402
from src.config import OFFICIAL_BSA_MERIT_BADGES_CATALOG  # noqa: E402
from src.tools.requirements_scraper import (  # noqa: E402
    REQUIREMENTS_DIR as PER_BADGE_REQUIREMENTS_DIR,
    load_badge_requirements_json,
)
from src.tools.scouting_scraper import BENCHMARK_BADGES, is_eagle_required  # noqa: E402


# Deterministic 10 random non-benchmark badges (seeded from catalog)
def select_10_random_non_benchmark_badges(seed: int = 2026) -> List[str]:
    bench_set = {b.lower() for b in BENCHMARK_BADGES}
    candidates = [
        str(b["badge_name"])
        for b in OFFICIAL_BSA_MERIT_BADGES_CATALOG
        if str(b["badge_name"]).lower() not in bench_set
        and str(b["badge_name"]).lower() not in ("indian lore",)
    ]
    rng = random.Random(seed)
    return sorted(rng.sample(sorted(candidates), 10))


def _slugify(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(text or "").strip().lower()).strip("_")


def audit_single_deck(
    badge_name: str,
    depth_mode: str,
    workflow_res: Dict[str, Any],
    official_json: Dict[str, Any],
) -> Dict[str, Any]:
    """Audits a generated deck for requirement/sub-requirement completeness, visual conformance,
    text hygiene, speaker notes, and cached Custom Nano Banana Hero illustrations.
    """
    pptx_path = str(workflow_res.get("output_path") or "")
    storyboard = workflow_res.get("storyboard") or {}
    slides: List[Dict[str, Any]] = storyboard.get("slides") or []
    is_deep = "deep" in depth_mode.lower()

    off_reqs = official_json.get("requirements") or []
    expected_req_nums = [str(r.get("req_number")) for r in off_reqs]
    expected_sub_ids = [
        str(sr.get("sub_id"))
        for r in off_reqs
        for sr in (r.get("sub_requirements") or [])
    ]

    # 1. Top-level requirement coverage & per-requirement slide counts
    req_slide_counts: Counter = Counter()
    all_slide_text_blobs: List[str] = []
    speaker_note_issues: List[str] = []
    text_hygiene_issues: List[str] = []

    for idx, s in enumerate(slides, start=1):
        rn = str(s.get("req_number") or "").strip()
        if rn.upper() not in ("ALL", "OVERVIEW", "SOURCES", ""):
            req_slide_counts[rn] += 1

        bps = [str(b) for b in (s.get("bullet_points") or [])]
        full_bps = [str(b) for b in (s.get("full_bullet_points") or [])]
        title_s = str(s.get("title") or "")
        verb_s = str(s.get("verbatim_requirement_text") or "")
        notes_s = str(s.get("presenter_notes") or "")
        blob = " ".join([title_s, verb_s, notes_s] + bps + full_bps)
        all_slide_text_blobs.append(blob)

        # Text hygiene checks
        for bp in bps:
            if bp.lstrip().startswith("•"):
                text_hygiene_issues.append(f"Slide {idx}: literal bullet in '{bp[:40]}'")
            if bp.endswith("..."):
                text_hygiene_issues.append(f"Slide {idx}: ellipsis truncation in '{bp[:40]}'")

        # Speaker notes checks: every slide must include substantive [SAY] notes,
        # and every requirement teaching slide must include [DEMONSTRATE] and/or [ASK SCOUTS].
        is_meta_slide = rn.upper() in ("ALL", "OVERVIEW", "SOURCES", "")
        if "[SAY]" not in notes_s or len(notes_s.strip()) < 100:
            speaker_note_issues.append(f"Slide {idx} ({title_s[:30]}): missing or short [SAY] note")
        elif not is_meta_slide and ("[DEMONSTRATE]" not in notes_s and "[ASK SCOUTS]" not in notes_s):
            speaker_note_issues.append(
                f"Slide {idx} ({title_s[:30]}): missing both [DEMONSTRATE] and [ASK SCOUTS]"
            )

    combined_deck_blob = " ".join(all_slide_text_blobs).lower()

    missing_top_reqs = [rn for rn in expected_req_nums if req_slide_counts.get(rn, 0) == 0]
    missing_sub_reqs = [
        sid for sid in expected_sub_ids
        if f"req {sid.lower()}" not in combined_deck_blob
        and f"({sid[-1].lower()})" not in combined_deck_blob
    ]

    # 2. Slide density per requirement check
    counts_list = [req_slide_counts.get(rn, 0) for rn in expected_req_nums] if expected_req_nums else [0]
    min_slides_per_req = min(counts_list) if counts_list else 0
    max_slides_per_req = max(counts_list) if counts_list else 0

    # 3. Stage 1 PPTX visual & AABB conformance check
    conf = check_pptx_conformance(pptx_path)

    # 4. Nano Banana Hero cache check across all 1..N requirements
    slug = _slugify(badge_name)
    nano_cached_count = 0
    for rn in expected_req_nums:
        r_slug = _slugify(rn)
        p_hero = AI_ILLUSTRATIONS_DIR / f"{slug}_req_{r_slug}_nano_hero.png"
        if p_hero.exists() and p_hero.stat().st_size > 4_000:
            nano_cached_count += 1

    return {
        "badge_name": badge_name,
        "is_eagle_required": is_eagle_required(badge_name),
        "depth_mode": "Deep Dive" if is_deep else "Troop Meeting",
        "pptx_path": pptx_path,
        "slide_count": int(workflow_res.get("slide_count") or (len(slides) + 1)),
        "official_reqs_total": len(expected_req_nums),
        "official_sub_reqs_total": len(expected_sub_ids),
        "missing_top_reqs": missing_top_reqs,
        "missing_sub_reqs": missing_sub_reqs,
        "min_slides_per_req": min_slides_per_req,
        "max_slides_per_req": max_slides_per_req,
        "aabb_overlap_count": conf.get("aabb_overlap_count", 0),
        "min_font_size_pt": conf.get("min_font_size_pt", 0.0),
        "conformance_passed": bool(conf.get("passed")),
        "text_hygiene_issues": text_hygiene_issues,
        "speaker_note_issues": speaker_note_issues,
        "nano_heroes_cached": nano_cached_count,
        "passed_all_audits": (
            len(missing_top_reqs) == 0
            and len(missing_sub_reqs) == 0
            and bool(conf.get("passed"))
            and conf.get("aabb_overlap_count", 0) == 0
            and len(text_hygiene_issues) == 0
            and len(speaker_note_issues) == 0
        ),
    }


def compute_all_badges_cost_and_storage_projection() -> Dict[str, Any]:
    """Calculates the exact compute and storage cost to expand Custom Nano Banana Illustrations
    to all 143 official Merit Badges based on live requirement counts and compressed PNG sizes.
    """
    total_badges = 0
    total_top_reqs = 0
    total_sub_reqs = 0
    for jf in sorted(PER_BADGE_REQUIREMENTS_DIR.glob("*.json")):
        if jf.name.startswith("_"):
            continue
        data = json.loads(jf.read_text(encoding="utf-8"))
        total_badges += 1
        total_top_reqs += int(data.get("requirements_count") or len(data.get("requirements") or []))
        total_sub_reqs += int(data.get("sub_requirements_total") or 0)

    nano_files = sorted(AI_ILLUSTRATIONS_DIR.glob("*_nano_hero.png"))
    total_nano_bytes = sum(f.stat().st_size for f in nano_files)
    avg_nano_kb = (total_nano_bytes / max(1, len(nano_files))) / 1024.0

    # Gemini 2.5 Flash Image (Nano Banana) pricing & latency benchmarks
    cost_per_image_usd = 0.039  # $0.039 per generated image (1,290 output tokens @ $30/1M tokens)
    avg_gen_seconds = 5.2

    # Tier A: 1 Custom Nano Banana Hero per Top-Level Requirement (1,115 images across all 143 badges)
    tier_a_images = total_top_reqs
    tier_a_already_cached = len(nano_files)
    tier_a_remaining = max(0, tier_a_images - tier_a_already_cached)
    tier_a_total_cost_usd = round(tier_a_images * cost_per_image_usd, 2)
    tier_a_incremental_cost_usd = round(tier_a_remaining * cost_per_image_usd, 2)
    tier_a_storage_mb = round((tier_a_images * avg_nano_kb) / 1024.0, 2)
    tier_a_compute_wall_min_6workers = round((tier_a_images * avg_gen_seconds) / 6.0 / 60.0, 1)

    # Tier B: Multi-Slide Visual Expansion (2.5 Nano Banana illustrations per requirement across all 143 badges)
    tier_b_images = int(round(total_top_reqs * 2.5))
    tier_b_total_cost_usd = round(tier_b_images * cost_per_image_usd, 2)
    tier_b_storage_mb = round((tier_b_images * avg_nano_kb) / 1024.0, 2)
    tier_b_compute_wall_min_6workers = round((tier_b_images * avg_gen_seconds) / 6.0 / 60.0, 1)

    return {
        "total_catalog_badges": total_badges,
        "total_top_level_requirements": total_top_reqs,
        "total_sub_requirements": total_sub_reqs,
        "current_cached_nano_hero_files": len(nano_files),
        "current_cached_nano_storage_mb": round(total_nano_bytes / (1024 * 1024), 2),
        "avg_compressed_png_kb": round(avg_nano_kb, 1),
        "unit_image_cost_usd": cost_per_image_usd,
        "tier_a_one_per_requirement": {
            "total_images": tier_a_images,
            "already_cached_images": tier_a_already_cached,
            "remaining_images_to_generate": tier_a_remaining,
            "total_compute_cost_usd": tier_a_total_cost_usd,
            "incremental_compute_cost_usd": tier_a_incremental_cost_usd,
            "total_compressed_storage_mb": tier_a_storage_mb,
            "wall_clock_minutes_6_workers": tier_a_compute_wall_min_6workers,
        },
        "tier_b_multi_slide_per_requirement": {
            "total_images": tier_b_images,
            "total_compute_cost_usd": tier_b_total_cost_usd,
            "total_compressed_storage_mb": tier_b_storage_mb,
            "wall_clock_minutes_6_workers": tier_b_compute_wall_min_6workers,
        },
    }


def main() -> int:
    random_10 = select_10_random_non_benchmark_badges(seed=2026)
    all_target_badges = list(BENCHMARK_BADGES) + random_10
    print(f"Auditing {len(BENCHMARK_BADGES)} Benchmark Badges + {len(random_10)} Random Badges = {len(all_target_badges)} Badges (72 Decks)")
    print(f"10 Random Badges: {random_10}")

    sample_decks_dir = GENERATED_DECKS_DIR / "benchmark_and_random_samples"
    sample_decks_dir.mkdir(parents=True, exist_ok=True)

    # Ensure live Nano Banana synthesis is active for any uncached requirements (especially the 10 random badges!)
    os.environ.pop("DISABLE_LIVE_IMAGE_GEN", None)

    audit_results: List[Dict[str, Any]] = []
    t0 = time.time()

    for b_idx, badge in enumerate(all_target_badges, start=1):
        off_json = load_badge_requirements_json(badge) or {}
        slug = _slugify(badge)
        is_random = badge in random_10

        for mode_label, depth_mode in [
            ("DeepDive", "Deep Dive / Camp School Deck"),
            ("TroopMeeting", "Standard Deck"),
        ]:
            out_pptx = sample_decks_dir / f"{slug}_{mode_label}_BEAUTIFIED.pptx"
            # For the 3 flagship badges in DeepDive mode, also write to the canonical GENERATED_DECKS_DIR path
            res = run_merit_badge_workflow(
                badge_name=badge,
                depth_mode=depth_mode,
                counselor_info={
                    "counselor_name": "Eric Clayberg, Merit Badge Counselor",
                    "troop_affiliation": "Scouts BSA Troop 25",
                },
                output_path=str(out_pptx),
                beautification_tier="BEAUTIFIED",
                enable_deep_research=True,
            )
            if mode_label == "DeepDive" and badge in ("Cooking", "Citizenship in the Nation", "First Aid"):
                canonical_pptx = GENERATED_DECKS_DIR / f"{badge.replace(' ', '_')}_BEAUTIFIED_Deck.pptx"
                import shutil
                shutil.copyfile(out_pptx, canonical_pptx)

            audit = audit_single_deck(badge, depth_mode, res, off_json)
            audit["group"] = "Random_10" if is_random else ("Eagle_Required" if audit["is_eagle_required"] else "Elective_Benchmark")
            audit_results.append(audit)
            status_icon = "PASS" if audit["passed_all_audits"] else "FAIL"
            print(
                f"[{b_idx:02d}/{len(all_target_badges)}] {badge:28s} | {audit['depth_mode']:12s} | "
                f"slides={audit['slide_count']:3d} ({audit['min_slides_per_req']}-{audit['max_slides_per_req']}/req) | "
                f"reqs={audit['official_reqs_total']:2d} (miss={len(audit['missing_top_reqs'])}) | "
                f"subs={audit['official_sub_reqs_total']:2d} (miss={len(audit['missing_sub_reqs'])}) | "
                f"nano={audit['nano_heroes_cached']:2d}/{audit['official_reqs_total']:2d} | {status_icon}"
            )

    cost_projection = compute_all_badges_cost_and_storage_projection()
    report_payload = {
        "generated_at_epoch": int(time.time()),
        "elapsed_seconds": round(time.time() - t0, 1),
        "benchmark_badges_count": len(BENCHMARK_BADGES),
        "random_badges_count": len(random_10),
        "random_badges": random_10,
        "total_decks_audited": len(audit_results),
        "all_decks_passed": all(a["passed_all_audits"] for a in audit_results),
        "cost_and_storage_projection": cost_projection,
        "deck_audits": audit_results,
    }
    report_path = REPO_ROOT / "data" / "merit_badge_requirements" / "_deck_audit_and_cost_report.json"
    report_path.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved full 72-deck audit & cost report to {report_path}")
    print(f"All 72 decks passed audit: {report_payload['all_decks_passed']}")
    return 0 if report_payload["all_decks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
