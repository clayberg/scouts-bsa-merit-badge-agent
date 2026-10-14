"""Regression tests for Merit Badge slide image deduplication and caption quality across all 144 badges."""

import json
from pathlib import Path
import re

from scripts.verify_all_144_images_and_captions import (
    _DANGLING_END_WORDS,
    audit_single_badge,
)

ROOT = Path(__file__).resolve().parent.parent


def test_nano_banana_catalog_captions_clean_and_complete():
  """Every caption in data/nano_banana_image_catalog.json must be colon-free, prefix-free, and end cleanly."""
  cat_path = ROOT / "data" / "nano_banana_image_catalog.json"
  assert cat_path.exists()
  catalog = json.loads(cat_path.read_text(encoding="utf-8"))
  assert len(catalog) >= 1300

  for fname, entry in catalog.items():
    cap = str(entry.get("caption") or "").strip()
    assert cap, f"Empty caption for {fname}"
    assert ":" not in cap, f"Colon found in {fname}: {cap}"
    assert not re.search(
        r"(handbook illustration depicting|instructional field visual illustrating)",
        cap,
        re.IGNORECASE,
    ), f"Boilerplate prefix found in {fname}: {cap}"
    assert cap.endswith((".", "!", "?")), f"Unpunctuated caption in {fname}: {cap}"
    words = re.findall(r"[A-Za-z0-9']+", cap.rstrip(".!? ").lower())
    assert words and words[-1] not in _DANGLING_END_WORDS, f"Truncated caption in {fname}: {cap}"


def test_collections_deck_zero_image_and_caption_issues():
  """Collections deck must have 14 unique visual slides and 0 image/caption issues."""
  res = audit_single_badge("Collections", verbose=True)
  assert res["total_issues"] == 0, f"Collections issues: {res['issues']}"
  assert res["visual_slide_count"] == 14
