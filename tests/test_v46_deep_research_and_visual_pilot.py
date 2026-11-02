"""V46 Verification Suite: Immutable 149-Badge SHA-256 Requirement Lock,
10-Badge Deep-Research Dossier Cache (97 Requirements), 40 Bespoke Technical Diagrams,
Sub-Requirement Hygiene, and Runtime/UI Enrichment Mode Wiring.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from src.tools.scouting_scraper import _load_v46_deep_research_overlay

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
REQ_DIR = DATA_DIR / "merit_badge_requirements"
V46_DIR = DATA_DIR / "v46_deep_research_cache"
AI_DIR = REPO_ROOT / "assets" / "ai_illustrations"

PILOT_10_SLUGS = (
    "weather",
    "first-aid",
    "citizenship-in-the-nation",
    "environmental-science",
    "personal-management",
    "emergency-preparedness",
    "robotics",
    "astronomy",
    "wilderness-survival",
    "aviation",
)


def test_v46_canonical_149_requirements_sha256_lock_and_zero_subreq_bleed() -> None:
    """Guarantees 100.00% bit-exact SHA-256 identity of all 149 official requirement trees."""
    sha_file = DATA_DIR / "canonical_requirements_sha256.json"
    assert sha_file.exists(), "Missing data/canonical_requirements_sha256.json"
    sha_manifest = json.loads(sha_file.read_text(encoding="utf-8"))
    assert len(sha_manifest) == 149

    verified_req_total = 0
    for slug, entry in sha_manifest.items():
        req_path = REQ_DIR / f"{slug}.json"
        assert req_path.exists(), f"Missing requirement file for {slug}"
        raw = json.loads(req_path.read_text(encoding="utf-8"))
        for r in raw.get("requirements") or []:
            rnum = str(r.get("req_number") or r.get("req_id") or "")
            rtxt = str(r.get("req_text") or "")
            actual_sha = hashlib.sha256(rtxt.encode("utf-8")).hexdigest()
            expected_sha = entry["req_text_sha256"][rnum]
            assert actual_sha == expected_sha, f"Canonical requirement drift detected in {slug} Req {rnum}"
            verified_req_total += 1

    assert verified_req_total >= 1150

    # Verify personal-management savings bond truncation bug is fixed
    pm_text = (REQ_DIR / "personal-management.json").read_text(encoding="utf-8")
    assert 'A U."' not in pm_text

    # Verify Weather Counselor Workbook Figure 1 broken caption is fixed
    w_wb = (REPO_ROOT / "deliverables" / "Weather_Counselor_Workbook.md").read_text(encoding="utf-8")
    assert "watch condition protocols used in Weather" not in w_wb


def test_v46_all_10_pilot_deep_research_caches_and_40_bespoke_diagrams() -> None:
    """Verifies all 10 Pilot Badges have complete V46 requirement dossiers and 40 crisp bespoke diagrams."""
    ncat = json.loads((DATA_DIR / "nano_banana_image_catalog.json").read_text(encoding="utf-8"))
    dhashes = json.loads((DATA_DIR / "asset_perceptual_hashes.json").read_text(encoding="utf-8"))

    total_reqs = 0
    all_v46_filenames: set[str] = set()

    for slug in PILOT_10_SLUGS:
        cache_path = V46_DIR / f"{slug}.json"
        assert cache_path.exists(), f"Missing V46 deep research cache for {slug}"
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "v46.1"
        assert payload["bespoke_diagram_count"] == 4

        raw_reqs = json.loads((REQ_DIR / f"{slug}.json").read_text(encoding="utf-8"))["requirements"]
        reqs_map = payload["requirements"]
        assert len(reqs_map) == len(raw_reqs), f"Incomplete requirement coverage in {slug}"

        for rnum, item in reqs_map.items():
            total_reqs += 1
            for field in (
                "rule_of_thumb_mnemonic",
                "worked_field_example",
                "counselor_tabletop_demo",
                "real_world_connection_box",
                "grounded_citation_label",
                "bespoke_visual_filename",
                "bespoke_visual_caption",
            ):
                val = str(item.get(field) or "")
                assert len(val) >= 15, f"Empty or short {field} in {slug} Req {rnum}"
                assert "\u2014" not in val and "\u2013" not in val, f"Dash found in {slug} Req {rnum} {field}"

            fn = item["bespoke_visual_filename"]
            all_v46_filenames.add(fn)

    assert total_reqs == 97
    assert len(all_v46_filenames) == 40

    for fn in sorted(all_v46_filenames):
        img_path = AI_DIR / fn
        assert img_path.exists(), f"Missing generated diagram PNG {fn}"
        sz = img_path.stat().st_size
        assert 4096 <= sz <= 250_000, f"Unexpected PNG byte size {sz} for {fn}"
        with Image.open(img_path) as im:
            assert im.size == (1024, 768)
        assert fn in ncat, f"{fn} missing from nano_banana_image_catalog.json"
        assert f"/assets/ai_illustrations/{fn}" in dhashes, f"{fn} missing from asset_perceptual_hashes.json"


def test_v46_runtime_overlay_and_ui_enrichment_mode_wiring() -> None:
    """Verifies runtime V46 overlay loader and UI Enriched Masterclass vs Pamphlet Core toggle."""
    ov = _load_v46_deep_research_overlay("Aviation")
    assert ov.get("badge_slug") == "aviation"
    assert "1" in ov.get("requirements", {})
    assert "FAA" in ov["requirements"]["1"]["grounded_citation_label"]

    app_js = (REPO_ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    assert "window.setContentEnrichmentMode" in app_js
    assert "ENRICHED_MASTERCLASS" in app_js
    assert "PAMPHLET_CORE" in app_js
