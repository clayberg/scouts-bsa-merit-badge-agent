"""Downloads and caches standalone Merit Badge emblem images from the official BSA Scout Shop.

Source: https://www.scoutshop.org/new-insignia/patches-and-badges/merit-badge.html
Uses Scout Shop's Klevu Search API v2 (https://uscs32v2.ksearchnet.com/cs/v2/search)
to locate the official standalone emblem product image for each Merit Badge, then
downloads and caches the image locally in `assets/badge_emblems/{slug}.png` and
`assets/pamphlet_covers/{slug}_patch.png`.
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.config import ASSETS_DIR, OFFICIAL_BSA_MERIT_BADGES_CATALOG

BADGE_EMBLEMS_DIR = ASSETS_DIR / "badge_emblems"
PAMPHLET_COVERS_DIR = ASSETS_DIR / "pamphlet_covers"
BADGE_EMBLEMS_DIR.mkdir(parents=True, exist_ok=True)
PAMPHLET_COVERS_DIR.mkdir(parents=True, exist_ok=True)

KLEVU_SEARCH_URL = "https://uscs32v2.ksearchnet.com/cs/v2/search"
KLEVU_API_KEY = "klevu-168554966403616429"


def _badge_slug(badge_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", badge_name.strip().lower()).strip("_")


def _normalize_title(text: str) -> str:
    t = text.lower()
    t = t.replace("&amp;", "and").replace("&", "and")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _clean_scoutshop_image_url(raw_url: str) -> List[str]:
    """Returns candidate high-res and standard Scout Shop image URLs from a Klevu product record."""
    if not raw_url:
        return []
    u = raw_url.strip()
    u = u.replace("pub/", "").replace("needtochange/", "")
    candidates = []
    # If Klevu points to a 200x200 klevu_images cache or Magento cache, also try original media/catalog/product path
    m = re.search(r"(https?://[^/]+/media/catalog/product)/(?:cache/[^/]+|klevu_images/[^/]+)(/.*)$", u)
    if m:
        candidates.append(f"{m.group(1)}{m.group(2)}")
    if u not in candidates:
        candidates.append(u)
    return candidates


def query_klevu_records(
    term: str = "*",
    category_path: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Queries Scout Shop's Klevu v2 endpoint."""
    query_obj: Dict[str, Any] = {"term": term}
    req_type = "SEARCH"
    if category_path:
        query_obj["categoryPath"] = category_path
        req_type = "CATNAV"

    payload = {
        "context": {"apiKeys": [KLEVU_API_KEY]},
        "recordQueries": [
            {
                "id": "productList",
                "typeOfRequest": req_type,
                "settings": {
                    "query": query_obj,
                    "typeOfRecords": ["KLEVU_PRODUCT"],
                    "limit": limit,
                    "offset": offset,
                },
            }
        ],
    }
    resp = requests.post(
        KLEVU_SEARCH_URL,
        json=payload,
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    q_results = data.get("queryResults") or []
    if not q_results:
        return []
    return q_results[0].get("records") or []


def collect_all_merit_badge_emblem_records() -> Dict[str, Dict[str, Any]]:
    """Collects all Scout Shop Merit Badge Emblem records keyed by normalized product name."""
    all_records: Dict[str, Dict[str, Any]] = {}

    # 1. Category queries + broad search queries
    search_configs = [
        ("*", "Insignia;Patches and Badges;Merit Badges"),
        ("*", "New Insignia;Patches and Badges;Merit Badge"),
        ("merit badge emblem", None),
        ("merit badge patch", None),
        ("merit badge", None),
    ]
    for term, cat_path in search_configs:
        for offset in (0, 100, 200, 300):
            try:
                recs = query_klevu_records(term=term, category_path=cat_path, limit=100, offset=offset)
            except Exception as exc:
                print(f"Warning querying term={term!r} cat={cat_path!r} offset={offset}: {exc}")
                break
            if not recs:
                break
            for r in recs:
                name = str(r.get("name") or "")
                if "pamphlet" in name.lower():
                    continue
                if "merit badge" in name.lower() or cat_path:
                    all_records[str(r.get("id") or name)] = r
            if len(recs) < 100:
                break

    print(f"Collected {len(all_records)} bulk Scout Shop emblem records.")
    return all_records


def match_record_for_badge(badge_name: str, records: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Finds the best matching Scout Shop Merit Badge emblem product record for `badge_name`."""
    norm_badge = _normalize_title(badge_name)
    # Also handle special naming differences on Scout Shop
    aliases = [norm_badge]
    if norm_badge == "fish and wildlife management":
        aliases.append("fish wildlife management")
    elif norm_badge == "signs signals and codes":
        aliases.append("signs signals codes")
    elif norm_badge == "indian lore":
        aliases.append("american indian")
    elif norm_badge == "disabilities awareness":
        aliases.append("disability awareness")
    elif norm_badge == "small boat sailing":
        aliases.append("small boat")

    best_rec = None
    best_score = -1

    for rec in records.values():
        name = str(rec.get("name") or "")
        norm_name = _normalize_title(name)
        if "pamphlet" in norm_name or "pocket" in norm_name or "sash" in norm_name or "display" in norm_name:
            continue
        for alias in aliases:
            # Exact prefix match like "<badge> merit badge emblem"
            if norm_name.startswith(alias + " merit badge"):
                score = 100 - abs(len(norm_name) - len(alias + " merit badge emblem"))
                if score > best_score:
                    best_score = score
                    best_rec = rec
            elif re.search(rf"\b{re.escape(alias)}\b", norm_name) and "merit badge" in norm_name:
                # Avoid matching "citizenship in the world" when looking for "citizenship in society"
                score = 60 - abs(len(norm_name) - len(alias + " merit badge emblem"))
                if score > best_score:
                    best_score = score
                    best_rec = rec

    if best_rec and best_score >= 50:
        return best_rec

    # Fallback: targeted Klevu search for "<badge_name> merit badge" and "<badge_name>"
    for search_q in (f"{badge_name} merit badge emblem", f"{badge_name} merit badge", badge_name):
        try:
            targeted = query_klevu_records(term=search_q, category_path=None, limit=15, offset=0)
            for rec in targeted:
                name = str(rec.get("name") or "")
                norm_name = _normalize_title(name)
                if "pamphlet" in norm_name or "sash" in norm_name or "pocket" in norm_name or "kit" in norm_name:
                    continue
                if "merit badge" in norm_name or "emblem" in norm_name:
                    return rec
        except Exception:
            pass

    return best_rec


def download_and_cache_emblem(badge_name: str, rec: Dict[str, Any]) -> Optional[Path]:
    """Downloads the emblem image from Scout Shop and saves it to badge_emblems and pamphlet_covers."""
    slug = _badge_slug(badge_name)
    emblem_path = BADGE_EMBLEMS_DIR / f"{slug}.png"
    patch_path = PAMPHLET_COVERS_DIR / f"{slug}_patch.png"

    raw_img_url = str(rec.get("image") or rec.get("imageUrl") or "")
    candidate_urls = _clean_scoutshop_image_url(raw_img_url)
    for url in candidate_urls:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
            if r.status_code == 200 and len(r.content) > 1500:
                with Image.open(io.BytesIO(r.content)) as im:
                    # Convert RGBA/P onto clean white background or keep RGBA
                    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                        rgba = im.convert("RGBA")
                        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                        composed = Image.alpha_composite(bg, rgba).convert("RGB")
                    else:
                        composed = im.convert("RGB")
                    composed.save(emblem_path, "PNG")
                    composed.save(patch_path, "PNG")
                    return emblem_path
        except Exception:
            continue
    return None


def fetch_scouting_org_emblem(badge_name: str) -> Optional[Path]:
    """Fallback to fetch the official standalone Merit Badge emblem from scouting.org if missed on Scout Shop."""
    slug = _badge_slug(badge_name)
    url_slug = re.sub(r"[^a-z0-9]+", "-", badge_name.strip().lower()).strip("-")
    emblem_path = BADGE_EMBLEMS_DIR / f"{slug}.png"
    patch_path = PAMPHLET_COVERS_DIR / f"{slug}_patch.png"
    hub_url = f"https://www.scouting.org/merit-badges/{url_slug}/"
    try:
        from bs4 import BeautifulSoup
        r = requests.get(hub_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for img in soup.find_all("img", src=True):
                src = str(img.get("src") or "")
                alt = str(img.get("alt") or "").lower()
                if (
                    ("filestore.scouting.org" in src.lower() or "scouting.org/wp-content/uploads" in src.lower())
                    and not src.lower().endswith(".svg")
                    and "logo" not in src.lower()
                ):
                    if src.startswith("/"):
                        src = "https://www.scouting.org" + src
                    img_resp = requests.get(src, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    if img_resp.status_code == 200 and len(img_resp.content) > 1500:
                        with Image.open(io.BytesIO(img_resp.content)) as im:
                            w, h = im.size
                            if 0.75 <= (w / max(1, h)) <= 1.35 and w >= 100:
                                if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                                    rgba = im.convert("RGBA")
                                    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                                    composed = Image.alpha_composite(bg, rgba).convert("RGB")
                                else:
                                    composed = im.convert("RGB")
                                composed.save(emblem_path, "PNG")
                                composed.save(patch_path, "PNG")
                                return emblem_path
    except Exception:
        pass
    return None


def main() -> None:
    manifest_path = BADGE_EMBLEMS_DIR / "scoutshop_emblems_manifest.json"
    manifest: Dict[str, Dict[str, str]] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}

    records = collect_all_merit_badge_emblem_records()
    catalog_names = [str(b.get("badge_name") or b.get("name")) for b in OFFICIAL_BSA_MERIT_BADGES_CATALOG]
    matched_count = 0
    downloaded_count = 0
    missed: List[str] = []

    for bname in catalog_names:
        slug = _badge_slug(bname)
        emblem_path = BADGE_EMBLEMS_DIR / f"{slug}.png"
        patch_path = PAMPHLET_COVERS_DIR / f"{slug}_patch.png"
        if emblem_path.exists() and emblem_path.stat().st_size > 1500 and slug in manifest:
            if not patch_path.exists():
                patch_path.write_bytes(emblem_path.read_bytes())
            matched_count += 1
            downloaded_count += 1
            continue

        rec = match_record_for_badge(bname, records)
        if rec:
            matched_count += 1
            saved = download_and_cache_emblem(bname, rec)
            if saved:
                downloaded_count += 1
                manifest[slug] = {
                    "badge_name": bname,
                    "source": "scoutshop.org",
                    "product_name": str(rec.get("name") or ""),
                    "product_url": str(rec.get("url") or ""),
                    "image_url": str(rec.get("image") or ""),
                    "local_path": str(saved),
                }
                continue

        # Fallback to scouting.org official merit badge emblem if not on Scout Shop
        fallback_saved = fetch_scouting_org_emblem(bname)
        if fallback_saved:
            downloaded_count += 1
            manifest[slug] = {
                "badge_name": bname,
                "source": "scouting.org",
                "product_name": f"{bname} Merit Badge Emblem",
                "product_url": f"https://www.scouting.org/merit-badges/{re.sub(r'[^a-z0-9]+', '-', bname.lower()).strip('-')}/",
                "image_url": "",
                "local_path": str(fallback_saved),
            }
        else:
            missed.append(bname)

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Matched {matched_count}/{len(catalog_names)} on Scout Shop; total downloaded {downloaded_count}/{len(catalog_names)} emblems.")
    if missed:
        print(f"Missed ({len(missed)}): {missed}")


if __name__ == "__main__":
    main()
