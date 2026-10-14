#!/usr/bin/env python3
"""Comprehensive 144-badge verification suite for slide images and captions.

Checks every generated slide deck across all 144 Merit Badges for:
1. Unnecessary repetitive prefixes ("handbook illustration depicting", "instructional field visual illustrating")
2. Colons (:) inside visual_caption that could cause bold prefixes
3. Truncated captions ending mid-sentence on dangling prepositions/articles/conjunctions
4. Repeated images (by diagram_path or MD5 hash) within a badge deck
5. Repeated captions (visual_caption) within a badge deck or duplicating a bullet on the same/adjacent slide
"""

from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.agents.beautifier import beautify_slide_storyboard
from src.agents.planner import generate_slide_storyboard
from src.config import OFFICIAL_BSA_MERIT_BADGES_CATALOG
from src.tools.scouting_scraper import fetch_merit_badge_pamphlet_pdf

_DANGLING_END_WORDS = {
    "a", "an", "the", "of", "in", "to", "for", "with", "on", "at", "from", "by", "about",
    "as", "into", "like", "through", "after", "over", "between", "out", "against", "during",
    "without", "before", "under", "around", "among", "and", "or", "but", "nor", "so", "yet",
    "because", "although", "since", "unless", "while", "where", "when", "that", "which", "who",
    "whom", "whose", "whether", "there", "their", "these", "those", "this", "other", "such",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "shall", "should", "may", "might", "must", "can", "could", "not",
    "very", "more", "most", "some", "any", "each", "every", "either", "neither", "both",
}


def _file_md5(path_str: str) -> str:
  if not path_str:
    return ""
  p = Path(path_str)
  if not p.exists():
    p = ROOT / path_str
  if p.exists() and p.is_file():
    return hashlib.md5(p.read_bytes()).hexdigest()[:12]
  return path_str


def audit_single_badge(badge_name: str, verbose: bool = False) -> dict:
  research_res = fetch_merit_badge_pamphlet_pdf({"badge_name": badge_name})
  reqs = research_res.get("requirements") or []
  is_eagle = bool(research_res.get("is_eagle_required"))

  storyboard = generate_slide_storyboard(
      badge_name=badge_name,
      requirements=reqs,
      depth_mode="Deep Dive / Camp School Deck",
      is_eagle_required=is_eagle,
  )
  beautify_res = beautify_slide_storyboard(
      storyboard=storyboard,
      deep_research_enrichment=None,
      beautification_tier="BEAUTIFIED",
      max_ai_images=20,
  )
  if isinstance(beautify_res.get("storyboard"), dict):
    storyboard = beautify_res["storyboard"]

  issues = {
      "prefix_violations": [],
      "colon_violations": [],
      "truncated_captions": [],
      "duplicate_images": [],
      "duplicate_captions": [],
      "bullet_caption_overlap": [],
  }

  seen_img_md5 = {}
  seen_captions = {}
  slide_rows = []

  slides = storyboard.get("slides") or []
  # Note: Slide 1 in the PPTX deck is the Cover Title Slide, so storyboard.slides[0] is Slide 2.
  for s_idx, s in enumerate(slides):
    pptx_slide_num = s_idx + 2
    ltype = str(s.get("archetype") or "")
    if ltype == "REQUIREMENTS_TRIAGE_MATRIX":
      continue
    dp = s.get("diagram_path")
    cap = str(s.get("visual_caption") or "").strip()
    if not dp:
      continue

    img_name = Path(dp).name if dp else "None"
    md5 = _file_md5(dp) if dp else ""

    if verbose:
      slide_rows.append((pptx_slide_num, ltype, s.get("title", ""), img_name, md5, cap))

    # 1. Prefix check
    if re.search(
        r"(handbook illustration depicting|instructional field visual illustrating)",
        cap,
        re.IGNORECASE,
    ):
      issues["prefix_violations"].append((pptx_slide_num, img_name, cap))

    # 2. Colon check
    if ":" in cap:
      issues["colon_violations"].append((pptx_slide_num, img_name, cap))

    # 3. Truncation check
    if cap:
      words = re.findall(r"[A-Za-z0-9']+", cap.rstrip(".!? ").lower())
      last_word = words[-1] if words else ""
      if last_word in _DANGLING_END_WORDS or not cap.endswith((".", "!", "?")):
        issues["truncated_captions"].append((pptx_slide_num, img_name, last_word, cap))

    # 4. Duplicate image check
    if md5:
      if md5 in seen_img_md5:
        prev_idx, prev_img = seen_img_md5[md5]
        issues["duplicate_images"].append((prev_idx, pptx_slide_num, prev_img, img_name, md5))
      else:
        seen_img_md5[md5] = (pptx_slide_num, img_name)

    # 5. Duplicate caption check
    norm_cap = re.sub(r"[^a-z0-9]+", " ", cap.lower()).strip()
    if norm_cap:
      if norm_cap in seen_captions:
        prev_idx = seen_captions[norm_cap]
        issues["duplicate_captions"].append((prev_idx, pptx_slide_num, cap))
      else:
        seen_captions[norm_cap] = pptx_slide_num

      # Check overlap with bullets on same or previous slide
      check_slides = [s]
      if s_idx >= 1:
        check_slides.append(slides[s_idx - 1])
      for cs in check_slides:
        for b in cs.get("bullet_points") or []:
          norm_b = re.sub(r"[^a-z0-9]+", " ", str(b).lower()).strip()
          if norm_b and (
              norm_cap == norm_b
              or (len(norm_cap) > 35 and norm_cap[:45] in norm_b)
          ):
            issues["bullet_caption_overlap"].append((pptx_slide_num, cap, str(b)[:90]))
            break

  total_issues = sum(len(v) for v in issues.values())
  return {
      "badge_name": badge_name,
      "slide_count": len(slides) + 1,
      "visual_slide_count": len(seen_img_md5),
      "total_issues": total_issues,
      "issues": issues,
      "slide_rows": slide_rows,
  }


def main():
  print("=== Step 1: Detailed Audit of Collections Merit Badge ===")
  col_res = audit_single_badge("Collections", verbose=True)
  for pptx_num, ltype, title, img_name, md5, cap in col_res["slide_rows"]:
    print(f"  Slide {pptx_num:02d} [{ltype:<26}] | {img_name:<38} ({md5}) | {cap}")
  print(
      f"\nCollections summary: {col_res['slide_count']} slides, "
      f"{col_res['visual_slide_count']} unique visual slides, "
      f"total_issues={col_res['total_issues']}"
  )
  if col_res["total_issues"] > 0:
    print("Collections issues:", json.dumps(col_res["issues"], indent=2))

  all_badges = sorted([
      b if isinstance(b, str) else (b.get("badge_name") or b.get("name"))
      for b in OFFICIAL_BSA_MERIT_BADGES_CATALOG
  ])
  print(f"\n=== Step 2: Auditing All {len(all_badges)} Merit Badges in Parallel ===")
  results = []
  with ProcessPoolExecutor(max_workers=16) as ex:
    fut_map = {ex.submit(audit_single_badge, b, False): b for b in all_badges}
    done_cnt = 0
    for fut in as_completed(fut_map):
      b = fut_map[fut]
      done_cnt += 1
      res = fut.result()
      results.append(res)
      if res["total_issues"] > 0 or done_cnt % 25 == 0 or done_cnt == len(all_badges):
        print(
            f"  [{done_cnt:03d}/{len(all_badges)}] {b:<32} -> "
            f"slides={res['slide_count']:02d}, visuals={res['visual_slide_count']:02d}, "
            f"issues={res['total_issues']}"
        )

  results.sort(key=lambda r: r["badge_name"])
  agg = {
      "prefix_violations": 0,
      "colon_violations": 0,
      "truncated_captions": 0,
      "duplicate_images": 0,
      "duplicate_captions": 0,
      "bullet_caption_overlap": 0,
  }
  badges_with_issues = []
  for r in results:
    for k in agg:
      agg[k] += len(r["issues"][k])
    if r["total_issues"] > 0:
      badges_with_issues.append(r)

  print("\n=== 144-Badge Aggregate Summary ===")
  print(json.dumps(agg, indent=2))
  print(f"Badges with 0 issues: {len(results) - len(badges_with_issues)}/{len(results)}")

  if badges_with_issues:
    print(f"\n=== Detailed Issues ({len(badges_with_issues)} badges) ===")
    for r in badges_with_issues[:30]:
      print(f"\n--- {r['badge_name']} (total={r['total_issues']}) ---")
      for k, v in r["issues"].items():
        if v:
          print(f"  {k}: {v}")

  out_path = ROOT / "data" / "audit_144_images_and_captions_report.json"
  out_path.write_text(
      json.dumps(
          {
              "aggregate": agg,
              "total_badges": len(results),
              "clean_badges": len(results) - len(badges_with_issues),
              "badges_with_issues": badges_with_issues,
          },
          indent=2,
      )
  )
  print(f"\nSaved full report to {out_path}")


if __name__ == "__main__":
  main()
