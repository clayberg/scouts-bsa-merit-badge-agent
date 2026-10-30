"""V38 Verification Suite: Deep Sub-Requirements (Depth 2-5), Zero Duplicate Slide Misconceptions, Zero Template Socratic Questions & Catalog Captions."""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.agents.planner import generate_slide_storyboard
from src.tools.scouting_scraper import fetch_merit_badge_pamphlet_pdf

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_v38_all_depth_2_to_5_subreqs_have_gemini_content() -> None:
    """Verify all 977 deeply nested (depth 2..5) sub-requirement children across all 56 multi-option badges have Gemini-authored summaries and misconceptions."""
    cache_dir = REPO_ROOT / "data" / "v38_deep_subreqs_cache"
    req_dir = REPO_ROOT / "data" / "merit_badge_requirements"

    cache_files = sorted(cache_dir.glob("*.json"))
    assert len(cache_files) >= 56, (
        f"Expected at least 56 V38 deep sub-requirement cache files, found {len(cache_files)}"
    )

    deep_count = 0

    def walk_deep(nodes: list[dict], depth: int, badge_file: str) -> None:
        nonlocal deep_count
        for n in nodes:
            if not isinstance(n, dict):
                continue
            sid = str(n.get("sub_id") or n.get("req_id") or "")
            if depth >= 2:
                deep_count += 1
                ps = str(n.get("pamphlet_summary") or "")
                assert len(ps) >= 35, (
                    f"Missing/short depth-{depth} pamphlet_summary in {badge_file} {sid}"
                )
                assert "following instructions for Requirement" not in ps, (
                    f"V30 template summary in {badge_file} {sid}: {ps}"
                )
                mp = n.get("common_misconception_pair") or {}
                myth = str(mp.get("misconception") or mp.get("myth") or "")
                assert "only requires a general overview" not in myth.lower(), (
                    f"V30 template myth in {badge_file} {sid}: {myth}"
                )
            ch = n.get("children") or n.get("sub_requirements") or []
            if ch:
                walk_deep(ch, depth + 1, badge_file)

    for bf in sorted(req_dir.glob("*.json")):
        if bf.name.startswith("_") or bf.name == "manifest.json":
            continue
        data = json.loads(bf.read_text(encoding="utf-8"))
        for r in data.get("requirements") or []:
            walk_deep(r.get("sub_requirements") or [], 1, bf.name)

    assert deep_count >= 975, f"Expected >= 975 deep nodes, walked {deep_count}"


def test_v38_rendered_decks_zero_duplicate_myths_and_zero_template_asks() -> None:
    """Verify rendered slide decks have zero duplicate misconceptions across slides and zero template Socratic questions."""
    sample_badges = ["Action Sports", "First Aid", "Camping", "Robotics"]
    template_ask_phrases = (
        "How would you explain the key difference in ",
        "Walk us through your exact sequence for ",
        "How does the visual diagram on this slide help you remember ",
    )

    for bname in sample_badges:
        res = fetch_merit_badge_pamphlet_pdf({"badge_name": bname})
        sb = generate_slide_storyboard(
            badge_name=bname,
            requirements=res["requirements"],
        )
        slides = sb.get("slides") or []
        assert len(slides) >= 12
        seen_myths: set[str] = set()
        for idx, sl in enumerate(slides):
            notes = str(
                sl.get("presenter_notes")
                or sl.get("speaker_notes")
                or sl.get("facilitator_notes")
                or ""
            )
            m = re.search(r"Myth:\s*([^\n]+)", notes)
            if m:
                myth_txt = m.group(1).strip()
                assert myth_txt not in seen_myths, (
                    f"Duplicate slide myth in {bname} slide {idx}: {myth_txt}"
                )
                seen_myths.add(myth_txt)
            for bad_ask in template_ask_phrases:
                assert bad_ask not in notes, (
                    f"Template Socratic question in {bname} slide {idx}: {bad_ask}"
                )


def test_v38_zero_synthetic_organizer_rows_and_clean_catalogs() -> None:
    """Verify zero synthetic row 2 fallbacks, quiz options <= 145 chars, >= 3 patrol quiz items, and zero V36 template catalog captions."""
    req_dir = REPO_ROOT / "data" / "merit_badge_requirements"
    for bf in sorted(req_dir.glob("*.json")):
        if bf.name.startswith("_") or bf.name == "manifest.json":
            continue
        data = json.loads(bf.read_text(encoding="utf-8"))
        qbank = data.get("patrol_quiz_bank") or []
        assert len(qbank) >= 3, (
            f"Small patrol_quiz_bank in {bf.name}: len={len(qbank)}"
        )
        for r in data.get("requirements") or []:
            wo = r.get("workbook_organizer") or {}
            for rl in wo.get("row_labels") or []:
                assert "Practical execution and real-world examples for " not in str(rl), (
                    f"Synthetic fallback row in {bf.name}: {rl}"
                )
            qi = r.get("quiz_item") or {}
            for opt in qi.get("options") or []:
                assert len(str(opt)) <= 145, (
                    f"Quiz option > 145 chars in {bf.name}: len={len(str(opt))}"
                )

    for cat_name in ("pamphlet_image_catalog.json", "nano_banana_image_catalog.json"):
        cat_path = REPO_ROOT / "data" / cat_name
        cat_data = json.loads(cat_path.read_text(encoding="utf-8"))
        for k, v in cat_data.items():
            if isinstance(v, dict):
                cap = str(v.get("caption") or "")
                assert "Field reference diagram illustrating " not in cap, (
                    f"V36 template caption in {cat_name} {k}: {cap}"
                )
                assert "Four-panel instructional diagram for " not in cap, (
                    f"V36 template caption in {cat_name} {k}: {cap}"
                )
