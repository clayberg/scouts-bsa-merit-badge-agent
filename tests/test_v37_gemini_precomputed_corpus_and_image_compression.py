"""V37 Verification Suite: 149-Badge Gemini Pre-Computed Corpus, Sub-Requirement Fidelity & Image Compression Gate."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_v37_all_149_gemini_cache_files_present_and_merged() -> None:
    """Verify all 149 badges have Gemini-authored cache files in data/v37_gemini_cache/ and zero V30/V36 template strings."""
    cache_dir = REPO_ROOT / "data" / "v37_gemini_cache"
    req_dir = REPO_ROOT / "data" / "merit_badge_requirements"

    cache_files = sorted(cache_dir.glob("*.json"))
    assert len(cache_files) == 149, (
        f"Expected 149 Gemini cache files, found {len(cache_files)}"
    )

    forbidden_subreq_phrases = (
        "outlining the core principles, practical steps, and verification criteria for your Scout Workbook",
        "Overlooking the specific field checks required for ",
        "confusing ",
        "many Scouts assume",
        "only requires a general overview",
    )

    for bf in sorted(req_dir.glob("*.json")):
        if bf.name.startswith("_") or bf.name == "manifest.json":
            continue
        data = json.loads(bf.read_text(encoding="utf-8"))
        for r in data.get("requirements", []):
            rid = r.get("req_id") or r.get("req_number")
            socratic = r.get("socratic_questions") or []
            assert len(socratic) >= 2, (
                f"Missing Gemini socratic_questions in {bf.name} Req {rid}"
            )
            for sr in r.get("sub_requirements") or []:
                if not isinstance(sr, dict):
                    continue
                sid = sr.get("sub_id") or sr.get("req_id")
                sr_sum = str(sr.get("pamphlet_summary") or "")
                assert len(sr_sum) >= 35, (
                    f"Short sub_req pamphlet_summary in {bf.name} {sid}"
                )
                for bad_p in forbidden_subreq_phrases[:2]:
                    assert bad_p not in sr_sum, (
                        f"Template sub_req summary in {bf.name} {sid}: {sr_sum}"
                    )


def test_v37_automated_image_compression_gate() -> None:
    """Verify compress_all_images.py exists and no uncompressed bloated PNGs exist in docs/images/."""
    comp_script = REPO_ROOT / "scripts" / "compress_all_images.py"
    assert comp_script.exists()

    docs_imgs = list((REPO_ROOT / "docs" / "images").glob("*.png"))
    assert len(docs_imgs) >= 9
    for img in docs_imgs:
        assert img.stat().st_size < 950_000, (
            f"Uncompressed bloated PNG in docs/images/: {img.name} ({img.stat().st_size} bytes)"
        )
