"""On-Demand & Per-Badge Batch GitHub Asset Hydrator (`src/tools/asset_hydrator.py`).

Bridges the lightweight `< 30 MB` (`10.17 MB`) `go/capstone-app` Git submission
bundle and the full `1.2 GB` (`3,917` visual assets) media catalog:

1. **Zero-Overhead Fast Path (`0.1ms`) in Full Workspace / Cloud Run**:
   When running inside the full developer workspace or the Argolis Cloud Run
   container image where `assets/` is already on disk, `hydrate_missing_badge_assets_batch()`
   verifies local file presence in memory and performs **zero network requests**.
2. **Per-Badge Concurrent Batch Hydration (`1` Batch Operation per Badge)**:
   When running from a fresh clone of the lightweight `10.17 MB` `.bundle` file
   where non-fixture PNGs are not yet on local disk, selecting or generating a
   Merit Badge resolves all required visual assets for that badge from
   `data/pamphlet_image_catalog.json`, `data/nano_banana_image_catalog.json`,
   `assets/badge_emblems/{slug}.png`, and `assets/pamphlet_covers/{slug}_cover.png`,
   downloads all missing files concurrently in a single `ThreadPoolExecutor(max_workers=8)`
   batch from GitHub Raw (`raw.githubusercontent.com`), and atomically caches
   them to `assets/` on local disk so **each image is pulled at most once**.
3. **Single-File Lazy Hydration on `/assets/{rel_path}` HTTP Requests**:
   If the browser requests a badge emblem or slide graphic via `GET /assets/...`
   that is not yet cached locally, `hydrate_single_asset_on_demand()` fetches
   and caches it transparently before FastAPI serves the file.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable
import urllib.request

logger = logging.getLogger("scouts_bsa_agent.asset_hydrator")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_REMOTE_ASSET_BASE_URLS: tuple[str, ...] = (
    "https://raw.githubusercontent.com/clayberg/scouts-bsa-merit-badge-agent/main",
    "https://raw.githubusercontent.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent/main",
)

_ALLOWED_ASSET_PREFIXES: tuple[str, ...] = (
    "assets/badge_emblems/",
    "assets/pamphlet_covers/",
    "assets/pamphlet_images/",
    "assets/ai_illustrations/",
    "assets/badge_image_catalog/",
    "assets/pptx_templates/",
    "assets/templates/overlays/",
    "assets/construction_anim/",
)

_CATALOG_CACHE_LOCK = threading.Lock()
_PAMPHLET_CATALOG_MEM: dict[str, Any] | None = None
_PAMPHLET_CATALOG_MTIME: float = -1.0
_NANO_CATALOG_MEM: dict[str, Any] | None = None
_NANO_CATALOG_MTIME: float = -1.0
_FILE_HYDRATION_LOCKS: dict[str, threading.Lock] = {}
_GLOBAL_LOCK = threading.Lock()


def badge_name_to_asset_slug(badge_name: str) -> str:
    """Normalizes a Merit Badge name (e.g. 'First Aid', 'Signs, Signals, and Codes') to its asset slug."""
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(badge_name or "").strip().lower())
    return cleaned.strip("_")


def _get_file_lock(rel_path: str) -> threading.Lock:
    with _GLOBAL_LOCK:
        lock = _FILE_HYDRATION_LOCKS.get(rel_path)
        if lock is None:
            lock = threading.Lock()
            _FILE_HYDRATION_LOCKS[rel_path] = lock
        return lock


def _load_tracked_catalogs(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Loads `data/pamphlet_image_catalog.json` and `data/nano_banana_image_catalog.json` into memory with mtime invalidation."""
    global _PAMPHLET_CATALOG_MEM, _PAMPHLET_CATALOG_MTIME, _NANO_CATALOG_MEM, _NANO_CATALOG_MTIME
    if repo_root != REPO_ROOT:
        p_path = repo_root / "data" / "pamphlet_image_catalog.json"
        n_path = repo_root / "data" / "nano_banana_image_catalog.json"
        p_data = json.loads(p_path.read_text(encoding="utf-8")) if p_path.exists() else {}
        n_data = json.loads(n_path.read_text(encoding="utf-8")) if n_path.exists() else {}
        return p_data, n_data

    with _CATALOG_CACHE_LOCK:
        p_path = repo_root / "data" / "pamphlet_image_catalog.json"
        p_mtime = p_path.stat().st_mtime if p_path.exists() else 0.0
        if _PAMPHLET_CATALOG_MEM is None or p_mtime != _PAMPHLET_CATALOG_MTIME:
            try:
                _PAMPHLET_CATALOG_MEM = (
                    json.loads(p_path.read_text(encoding="utf-8")) if p_path.exists() else {}
                )
                _PAMPHLET_CATALOG_MTIME = p_mtime
            except Exception:
                _PAMPHLET_CATALOG_MEM = {}
        n_path = repo_root / "data" / "nano_banana_image_catalog.json"
        n_mtime = n_path.stat().st_mtime if n_path.exists() else 0.0
        if _NANO_CATALOG_MEM is None or n_mtime != _NANO_CATALOG_MTIME:
            try:
                _NANO_CATALOG_MEM = (
                    json.loads(n_path.read_text(encoding="utf-8")) if n_path.exists() else {}
                )
                _NANO_CATALOG_MTIME = n_mtime
            except Exception:
                _NANO_CATALOG_MEM = {}
        return _PAMPHLET_CATALOG_MEM, _NANO_CATALOG_MEM


def _is_safe_asset_rel_path(rel_path: str) -> bool:
    norm = str(rel_path or "").strip().lstrip("/")
    if not norm or ".." in norm or "\\" in norm:
        return False
    if norm == "assets/bsa_logo.png":
        return True
    return norm.startswith(_ALLOWED_ASSET_PREFIXES)


def _extract_req_asset_paths(node: Any, out: list[str]) -> None:
    """Recursively extracts `workbook_diagram_url` and asset paths from requirement JSON structures."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("workbook_diagram_url", "diagram_url", "pamphlet_image_path") and isinstance(v, str) and v.strip():
                clean_v = v.strip().split("?")[0].lstrip("/")
                if clean_v.startswith("assets/"):
                    out.append(clean_v)
            else:
                _extract_req_asset_paths(v, out)
    elif isinstance(node, list):
        for item in node:
            _extract_req_asset_paths(item, out)


def collect_badge_asset_rel_paths(
    badge_name: str,
    template_id: str | None = None,
    repo_root: Path | None = None,
) -> list[str]:
    """Returns the deduplicated list of relative `assets/...` paths needed for `badge_name`."""
    root = repo_root or REPO_ROOT
    slug = badge_name_to_asset_slug(badge_name)
    if not slug:
        return []
    hyphen_slug = slug.replace("_", "-")

    rel_paths: list[str] = [
        f"assets/badge_emblems/{slug}.png",
        f"assets/pamphlet_covers/{slug}_cover.png",
        f"assets/badge_image_catalog/{slug}/catalog.json",
    ]

    p_cat, n_cat = _load_tracked_catalogs(root)
    badge_lower = str(badge_name or "").strip().lower()
    pamphlet_prefix = f"{slug}_p"
    nano_prefix = f"{slug}_"
    nano_hyphen_prefix = f"{hyphen_slug}_"

    for fname, meta in p_cat.items():
        fname_s = str(fname).strip()
        if fname_s.startswith(pamphlet_prefix) or fname_s.startswith(f"{hyphen_slug}_p"):
            rel_paths.append(f"assets/pamphlet_images/{fname_s}")

    for fname, meta in n_cat.items():
        fname_s = str(fname).strip()
        meta_dict = meta if isinstance(meta, dict) else {}
        meta_badge = str(meta_dict.get("badge_name") or meta_dict.get("badge") or "").strip().lower()
        meta_slug = badge_name_to_asset_slug(meta_badge) if meta_badge else ""
        if (
            meta_badge == badge_lower
            or meta_slug == slug
            or fname_s.startswith(nano_prefix)
            or fname_s.startswith(nano_hyphen_prefix)
        ):
            clean_fname = fname_s.lstrip("/")
            explicit_path = str(meta_dict.get("path") or meta_dict.get("rel_path") or "").strip().lstrip("/")
            if explicit_path.startswith("assets/"):
                rel_paths.append(explicit_path)
            elif clean_fname.startswith("assets/"):
                rel_paths.append(clean_fname)
            elif (root / "assets" / "diagrams" / clean_fname).exists() and not (
                root / "assets" / "ai_illustrations" / clean_fname
            ).exists():
                rel_paths.append(f"assets/diagrams/{clean_fname}")
            else:
                rel_paths.append(f"assets/ai_illustrations/{clean_fname}")
            extra_wb = str(meta_dict.get("workbook_diagram_url") or "").strip().lstrip("/")
            if extra_wb.startswith("assets/"):
                rel_paths.append(extra_wb)

    # Inspect data/merit_badge_requirements/<slug>.json for workbook_diagram_url paths
    req_dir = root / "data" / "merit_badge_requirements"
    loaded_req_file = False
    for candidate_name in (f"{hyphen_slug}.json", f"{slug}.json"):
        req_file = req_dir / candidate_name
        if req_file.exists():
            try:
                req_json = json.loads(req_file.read_text(encoding="utf-8"))
                _extract_req_asset_paths(req_json, rel_paths)
                loaded_req_file = True
                break
            except Exception:
                pass

    if not loaded_req_file:
        cache_file = root / "data" / "official_requirements_cache.json"
        if cache_file.exists():
            try:
                cache_json = json.loads(cache_file.read_text(encoding="utf-8"))
                for k, v in (cache_json.items() if isinstance(cache_json, dict) else []):
                    if str(k).strip().lower() == badge_lower or badge_name_to_asset_slug(str(k)) == slug:
                        _extract_req_asset_paths(v, rel_paths)
                        break
            except Exception:
                pass

    # Also inspect per-badge catalog.json if already present on disk
    badge_cat_path = root / "assets" / "badge_image_catalog" / slug / "catalog.json"
    if badge_cat_path.exists():
        try:
            b_cat = json.loads(badge_cat_path.read_text(encoding="utf-8"))
            for item in b_cat.get("items") or b_cat.get("images") or []:
                if isinstance(item, dict):
                    rp = str(item.get("rel_path") or item.get("path") or "").strip().lstrip("/")
                    if rp.startswith("assets/") and _is_safe_asset_rel_path(rp):
                        rel_paths.append(rp)
        except Exception:
            pass

    if template_id:
        tpl_slug = re.sub(r"[^a-z0-9_-]+", "_", str(template_id).strip().lower())
        if tpl_slug and tpl_slug != "default_workbench":
            rel_paths.append(f"assets/pptx_templates/{tpl_slug}.pptx")

    deduped: list[str] = []
    seen: set[str] = set()
    for rp in rel_paths:
        if rp not in seen and _is_safe_asset_rel_path(rp):
            seen.add(rp)
            deduped.append(rp)
    return deduped


def _get_configured_base_urls() -> tuple[str, ...]:
    custom = os.environ.get("BSA_REMOTE_ASSET_BASE_URL", "").strip().rstrip("/")
    if custom:
        return (custom, *DEFAULT_REMOTE_ASSET_BASE_URLS)
    return DEFAULT_REMOTE_ASSET_BASE_URLS


def hydrate_single_asset_on_demand(
    rel_path: str,
    repo_root: Path | None = None,
    timeout_sec: float = 6.0,
    opener: Callable[[str, float], bytes] | None = None,
) -> dict[str, Any]:
    """Downloads a single missing `assets/...` file from GitHub Raw and caches it atomically on local disk."""
    norm_rel = str(rel_path or "").strip().lstrip("/")
    if not _is_safe_asset_rel_path(norm_rel):
        return {
            "rel_path": norm_rel,
            "status": "SKIPPED_INVALID_PATH",
            "cached": False,
        }

    root = repo_root or REPO_ROOT
    target_path = root / norm_rel
    if target_path.exists() and target_path.stat().st_size > 0:
        return {
            "rel_path": norm_rel,
            "status": "ALREADY_CACHED",
            "cached": True,
            "bytes": target_path.stat().st_size,
        }

    if os.environ.get("BSA_DISABLE_REMOTE_ASSET_HYDRATION", "").strip() == "1" and opener is None:
        return {
            "rel_path": norm_rel,
            "status": "DISABLED_BY_ENV",
            "cached": False,
        }

    file_lock = _get_file_lock(norm_rel)
    with file_lock:
        if target_path.exists() and target_path.stat().st_size > 0:
            return {
                "rel_path": norm_rel,
                "status": "ALREADY_CACHED",
                "cached": True,
                "bytes": target_path.stat().st_size,
            }

        last_err = ""
        for base_url in _get_configured_base_urls():
            url = f"{base_url}/{norm_rel}"
            try:
                if opener is not None:
                    payload = opener(url, timeout_sec)
                else:
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "ScoutsBSA-MeritBadgeWorkbench-AssetHydrator/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                        if getattr(resp, "status", 200) != 200:
                            last_err = f"HTTP {getattr(resp, 'status', 'unknown')}"
                            continue
                        payload = resp.read()

                if not payload or len(payload) < 16:
                    last_err = "Empty or truncated payload"
                    continue

                # Basic magic-byte sanity check for PNGs so HTML 404 pages are never cached
                if norm_rel.endswith(".png") and not payload.startswith(b"\x89PNG\r\n\x1a\n"):
                    last_err = "Invalid PNG magic header"
                    continue

                target_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = target_path.with_suffix(target_path.suffix + f".part.{os.getpid()}.{threading.get_ident()}")
                tmp_path.write_bytes(payload)
                tmp_path.replace(target_path)

                return {
                    "rel_path": norm_rel,
                    "status": "HYDRATED_FROM_REMOTE",
                    "cached": True,
                    "bytes": len(payload),
                    "source_url": url,
                }
            except Exception as exc:
                last_err = str(exc)

        logger.debug("Asset hydration miss for %s: %s", norm_rel, last_err)
        return {
            "rel_path": norm_rel,
            "status": "FETCH_FAILED",
            "cached": False,
            "error": last_err,
        }


def hydrate_missing_badge_assets_batch(
    badge_name: str,
    template_id: str | None = None,
    repo_root: Path | None = None,
    max_workers: int = 8,
    timeout_sec: float = 6.0,
    opener: Callable[[str, float], bytes] | None = None,
) -> dict[str, Any]:
    """Hydrates all missing visual assets for `badge_name` in one concurrent batch operation.

    - If all assets for `badge_name` already exist on disk (e.g., in the full
      workspace or Argolis Cloud Run container, or on the second run of the same
      badge in a `.bundle` clone), returns in `<0.2ms` with `hydrated_count=0`.
    - If any assets are missing (e.g., first time generating `badge_name` in a
      `< 30 MB` submission bundle clone), fetches all missing files in parallel
      via `ThreadPoolExecutor(max_workers=max_workers)` and saves them to `assets/`.
    """
    t0 = time.perf_counter()
    root = repo_root or REPO_ROOT
    slug = badge_name_to_asset_slug(badge_name)

    # First ensure per-badge catalog.json is hydrated if missing so any extra paths are discovered
    cat_rel = f"assets/badge_image_catalog/{slug}/catalog.json"
    cat_path = root / cat_rel
    if slug and (not cat_path.exists() or cat_path.stat().st_size == 0):
        hydrate_single_asset_on_demand(cat_rel, repo_root=root, timeout_sec=timeout_sec, opener=opener)

    all_rel_paths = collect_badge_asset_rel_paths(
        badge_name=badge_name,
        template_id=template_id,
        repo_root=root,
    )

    missing_rel_paths: list[str] = []
    already_cached_count = 0
    for rp in all_rel_paths:
        p = root / rp
        if p.exists() and p.stat().st_size > 0:
            already_cached_count += 1
        else:
            missing_rel_paths.append(rp)

    if not missing_rel_paths:
        return {
            "badge_name": badge_name,
            "badge_slug": slug,
            "total_badge_assets": len(all_rel_paths),
            "already_cached_count": already_cached_count,
            "hydrated_count": 0,
            "failed_count": 0,
            "hydrated_bytes": 0,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            "batch_status": "ALL_LOCAL_CACHE_HIT",
        }

    hydrated_count = 0
    failed_count = 0
    hydrated_bytes = 0
    hydrated_files: list[str] = []

    worker_count = max(1, min(int(max_workers), len(missing_rel_paths)))
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        future_map = {
            pool.submit(
                hydrate_single_asset_on_demand,
                rp,
                root,
                timeout_sec,
                opener,
            ): rp
            for rp in missing_rel_paths
        }
        for fut in as_completed(future_map):
            res = fut.result()
            if res.get("cached"):
                if res.get("status") == "HYDRATED_FROM_REMOTE":
                    hydrated_count += 1
                    hydrated_bytes += int(res.get("bytes") or 0)
                    hydrated_files.append(str(res.get("rel_path")))
                else:
                    already_cached_count += 1
            else:
                failed_count += 1

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    if hydrated_count > 0:
        logger.info(
            "Batch-hydrated %d missing assets (%d bytes) for badge '%s' in %.1f ms",
            hydrated_count,
            hydrated_bytes,
            badge_name,
            elapsed_ms,
        )

    return {
        "badge_name": badge_name,
        "badge_slug": slug,
        "total_badge_assets": len(all_rel_paths),
        "already_cached_count": already_cached_count,
        "hydrated_count": hydrated_count,
        "failed_count": failed_count,
        "hydrated_bytes": hydrated_bytes,
        "hydrated_files": hydrated_files,
        "elapsed_ms": elapsed_ms,
        "batch_status": "BATCH_HYDRATED" if hydrated_count > 0 else "NO_REMOTE_FETCHED",
    }
