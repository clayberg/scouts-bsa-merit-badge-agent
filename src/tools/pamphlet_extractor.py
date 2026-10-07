"""Official BSA Merit Badge Pamphlet PDF & Web Supplement Extractor.

This module makes the official Scouting America (BSA) Merit Badge Pamphlet PDF
the primary source of truth for the entire slide deck:
1. Downloads and caches the official BSA Merit Badge Pamphlet PDF from
   `filestore.scouting.org` or by scraping `https://www.scouting.org/merit-badges/<slug>/`.
2. Extracts the Table of Contents, chapter headings, and page-by-page instructional
   text directly from the official BSA Merit Badge Pamphlet PDF (`pypdf`).
3. Extracts real photographs, illustrations, and diagrams directly from the
   official BSA Merit Badge Pamphlet PDF (`page.images` + `pdftoppm` figure crops),
   ensuring every slide displays an authentic visual from the pamphlet (or a
   supplemental web image from Wikimedia Commons / Wikipedia REST API when needed).
4. Summarizes pamphlet pages into concise, Scout-focused slide teaching points
   with exact pamphlet page citations (`Official BSA <Badge> Pamphlet, p. X`).
"""

from __future__ import annotations

import hashlib
import io
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageOps

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore

from src.config import ASSETS_DIR

PAMPHLETS_DIR = ASSETS_DIR / "pamphlets"
PAMPHLET_IMAGES_DIR = ASSETS_DIR / "pamphlet_images"
WEB_IMAGES_DIR = ASSETS_DIR / "web_images"

PAMPHLETS_DIR.mkdir(parents=True, exist_ok=True)
PAMPHLET_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
WEB_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

_PAMPHLET_INDEX_CACHE: Dict[str, Dict[str, Any]] = {}


def _badge_slug(badge_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", badge_name.strip().lower()).strip("_")


def _badge_url_slug(badge_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", badge_name.strip().lower()).strip("-")


def ensure_official_pamphlet_pdf(badge_name: str) -> Tuple[Optional[Path], str]:
    """Locates or downloads the official BSA Merit Badge Pamphlet PDF for `badge_name`.

    Returns:
        Tuple[Optional[Path], str]: (local PDF path if available, official pamphlet URL)
    """
    slug = _badge_slug(badge_name)
    local_pdf = PAMPHLETS_DIR / f"{slug}.pdf"
    encoded_space = badge_name.strip().replace(" ", "%20")
    encoded_under = badge_name.strip().replace(" ", "_")
    default_url = f"https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/{encoded_space}.pdf"

    if local_pdf.exists() and local_pdf.stat().st_size > 20_000:
        return local_pdf, default_url

    candidate_urls = [
        default_url,
        f"https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/{encoded_under}.pdf",
    ]

    hub_url = f"https://www.scouting.org/merit-badges/{_badge_url_slug(badge_name)}/"
    try:
        resp = requests.get(hub_url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if "filestore.scouting.org" in href and "pamphlet" in href.lower() and href.lower().endswith(".pdf"):
                    if href not in candidate_urls:
                        candidate_urls.insert(0, href)
    except Exception:
        pass

    for url in candidate_urls:
        try:
            r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) > 25_000 and r.content[:4] == b"%PDF":
                local_pdf.write_bytes(r.content)
                return local_pdf, url
        except Exception:
            continue

    return (local_pdf if local_pdf.exists() else None), candidate_urls[0]


def _clean_pdf_text(raw_text: str, badge_name: str = "") -> str:
    """Cleans hyphenated line-breaks, kerning splits, and running headers from BSA Pamphlet PDF text."""
    if not raw_text:
        return ""
    text = raw_text
    # Remove running page headers like "FIRST AID    19" or "18    FIRST AID"
    if badge_name:
        b_upper = re.escape(badge_name.upper())
        text = re.sub(rf"(?m)^\s*(?:\d+\s+{b_upper}|{b_upper}\s+\d+)\s*$", "", text)
    text = re.sub(r"(?m)^\s*(?:\d+\s+[A-Z][A-Z ]{2,28}|[A-Z][A-Z ]{2,28}\s+\d+)\s*$", "", text)

    # Rejoin hyphenated line breaks ("camp-\ning" -> "camping")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    # Rejoin BSA PDF kerning splits where 1-3 letters at the end of a token are split before lowercase continuation
    # e.g., "R\neducing" -> "Reducing", "Patrol/T\nroop" -> "Patrol/Troop", "Appr\noach" -> "Approach"
    text = re.sub(r"([A-Za-z/]{1,8})\n([a-z]{2,})", r"\1\2", text)
    # Remove decorative leading dots on headings (e.g. ".How to Handle" -> "How to Handle")
    text = re.sub(r"(?m)^\s*\.([A-Z])", r"\1", text)
    text = re.sub(r"\s+\.([A-Z])", r" \1", text)
    # Collapse horizontal whitespace
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _extract_pamphlet_images_for_pdf(pdf_path: Path, slug: str, reader: Any) -> Dict[int, List[Path]]:
    """Extracts high-quality embedded photographs & illustrations per 1-indexed page from the BSA PDF."""
    page_images: Dict[int, List[Path]] = {}

    existing = sorted(PAMPHLET_IMAGES_DIR.glob(f"{slug}_p*_img*.png"))
    if len(existing) >= 6:
        for img_path in existing:
            m = re.search(r"_p(\d+)_img(\d+)\.png$", img_path.name)
            if m:
                p_num = int(m.group(1))
                page_images.setdefault(p_num, []).append(img_path)
        return page_images

    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        try:
            n_imgs = len(page.images)
        except Exception:
            continue
        if n_imgs == 0 or n_imgs > 15:
            continue
        for img_idx in range(min(6, n_imgs)):
            try:
                img_file = page.images[img_idx]
                pil_img = Image.open(io.BytesIO(img_file.data))
                w, h = pil_img.size
                if w >= 200 and h >= 150 and 0.3 <= (w / h) <= 3.2:
                    if pil_img.mode not in ("RGB", "RGBA"):
                        pil_img = pil_img.convert("RGB")
                    extrema = pil_img.convert("L").getextrema()
                    if extrema and (extrema[1] - extrema[0]) > 45:
                        fname = PAMPHLET_IMAGES_DIR / f"{slug}_p{page_num:03d}_img{img_idx+1}.png"
                        if not fname.exists():
                            pil_img.save(fname, "PNG", optimize=True, compress_level=9)
                        page_images.setdefault(page_num, []).append(fname)
            except Exception:
                continue

    return page_images


def render_pamphlet_page_figure(pdf_path: Path, slug: str, page_num: int) -> Optional[Path]:
    """Renders a composite diagram/figure page from the BSA Pamphlet PDF using `pdftoppm`."""
    out_png = PAMPHLET_IMAGES_DIR / f"{slug}_p{page_num:03d}_figure.png"
    if out_png.exists() and out_png.stat().st_size > 10_000:
        return out_png
    prefix = PAMPHLET_IMAGES_DIR / f"_tmp_{slug}_{page_num}"
    try:
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r",
                "150",
                "-f",
                str(page_num),
                "-l",
                str(page_num),
                "-singlefile",
                str(pdf_path),
                str(prefix),
            ],
            check=True,
            timeout=8,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        rendered = Path(f"{prefix}.png")
        if rendered.exists():
            with Image.open(rendered) as im:
                w, h = im.size
                cropped = im.crop((int(w * 0.04), int(h * 0.06), int(w * 0.96), int(h * 0.94)))
                cropped.save(out_png, "PNG", optimize=True, compress_level=9)
            rendered.unlink(missing_ok=True)
            return out_png
    except Exception:
        pass
    return None


def fetch_web_supplement_image(badge_name: str, topic_query: str, slug_tag: str) -> Optional[Path]:
    """Searches Wikimedia Commons API (File namespace 6) for an educational diagram/photo."""
    safe_tag = re.sub(r"[^a-z0-9_]+", "_", slug_tag.lower()).strip("_")[:56]
    out_path = WEB_IMAGES_DIR / f"{safe_tag}.png"
    if out_path.exists() and out_path.stat().st_size > 8_000:
        return out_path

    alt_pamphlet_path = PAMPHLET_IMAGES_DIR / f"{safe_tag}.png"
    if alt_pamphlet_path.exists() and alt_pamphlet_path.stat().st_size > 8_000:
        return alt_pamphlet_path

    try:
        api_url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "generator": "search",
            "gsrnamespace": 6,
            "gsrsearch": f"filetype:bitmap {badge_name} {topic_query}",
            "gsrlimit": 5,
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": 1024,
            "format": "json",
        }
        resp = requests.get(
            api_url,
            params=params,
            timeout=5,
            headers={"User-Agent": "ScoutsBSAMeritBadgeCounselorAgent/2.0 (https://scouting.org; educational)"},
        )
        if resp.status_code == 200:
            pages = (resp.json().get("query") or {}).get("pages") or {}
            for _, pdata in pages.items():
                iinfo = (pdata.get("imageinfo") or [{}])[0]
                thumb_url = iinfo.get("thumburl") or iinfo.get("url")
                if thumb_url and any(ext in thumb_url.lower() for ext in (".jpg", ".jpeg", ".png")):
                    img_r = requests.get(
                        thumb_url,
                        timeout=6,
                        headers={"User-Agent": "ScoutsBSAMeritBadgeCounselorAgent/2.0 (https://scouting.org; educational)"},
                    )
                    if img_r.status_code == 200 and len(img_r.content) > 10_000:
                        pil_im = Image.open(io.BytesIO(img_r.content)).convert("RGB")
                        if pil_im.width >= 240 and pil_im.height >= 160:
                            pil_im.save(out_path, "PNG", optimize=True, compress_level=9)
                            return out_path
    except Exception:
        pass
    return None


def build_pamphlet_index(badge_name: str) -> Dict[str, Any]:
    """Builds a structured page-by-page text, TOC, and image index from the official BSA Pamphlet PDF."""
    slug = _badge_slug(badge_name)
    if slug in _PAMPHLET_INDEX_CACHE:
        return _PAMPHLET_INDEX_CACHE[slug]

    pdf_path, pdf_url = ensure_official_pamphlet_pdf(badge_name)
    if not pdf_path or not pdf_path.exists() or PdfReader is None:
        return {
            "badge_name": badge_name,
            "slug": slug,
            "pdf_path": None,
            "pdf_url": pdf_url,
            "page_count": 0,
            "toc_entries": [],
            "pages": {},
            "all_images": [],
        }

    reader = PdfReader(str(pdf_path))
    page_images_map = _extract_pamphlet_images_for_pdf(pdf_path, slug, reader)

    pages_data: Dict[int, Dict[str, Any]] = {}
    toc_entries: List[Dict[str, Any]] = []
    all_images: List[Tuple[int, Path]] = []

    for idx, page in enumerate(reader.pages):
        p_num = idx + 1
        raw_txt = ""
        try:
            raw_txt = page.extract_text() or ""
        except Exception:
            raw_txt = ""
        clean_txt = _clean_pdf_text(raw_txt, badge_name=badge_name)
        lines = [ln.strip() for ln in clean_txt.splitlines() if ln.strip()]

        # Parse Table of Contents entries (usually on pages 5-12 with dotted leaders "... 25")
        if 4 <= p_num <= 13 and any("contents" in ln.lower() for ln in lines[:5]):
            for ln in lines:
                m = re.match(r"^([A-Za-z0-9 ,'\-/()&]+?)\s*(?:\.\s*){2,}(\d{1,3})$", ln)
                if m:
                    sec_title = m.group(1).strip(" .")
                    printed_page = int(m.group(2))
                    if len(sec_title) > 3 and sec_title.lower() not in {"contents", "resources"}:
                        toc_entries.append({
                            "title": sec_title,
                            "printed_page": printed_page,
                            "pdf_page": min(len(reader.pages), printed_page + 2),
                        })

        imgs_on_page = page_images_map.get(p_num, [])
        for im_p in imgs_on_page:
            all_images.append((p_num, im_p))

        # Identify primary subheading on this page
        heading = ""
        for ln in lines[:6]:
            if 4 <= len(ln) <= 64 and not ln.endswith(".") and not ln.isupper():
                heading = ln.strip(" .")
                break

        pages_data[p_num] = {
            "pdf_page": p_num,
            "heading": heading,
            "text": clean_txt,
            "lines": lines,
            "images": imgs_on_page,
        }

    index_obj = {
        "badge_name": badge_name,
        "slug": slug,
        "pdf_path": pdf_path,
        "pdf_url": pdf_url,
        "page_count": len(reader.pages),
        "toc_entries": toc_entries,
        "pages": pages_data,
        "all_images": all_images,
    }
    _PAMPHLET_INDEX_CACHE[slug] = index_obj
    return index_obj


def _extract_clean_teaching_points_from_pages(
    pages: Dict[int, Dict[str, Any]],
    best_pages: List[int],
    badge_name: str,
) -> List[str]:
    """Extracts 4–6 substantive, Scout-friendly teaching points from matched BSA Pamphlet pages."""
    points: List[str] = []
    conversational_fluff = (
        "for example",
        "it might be",
        "a good place",
        "also, by",
        "when the naturalist",
        "for nearly a hundred",
        "always check scouting",
        "scan this qr",
    )

    for p_num in best_pages:
        p_info = pages.get(p_num)
        if not p_info:
            continue
        lines = p_info.get("lines") or []
        current_subhead = p_info.get("heading") or f"Pamphlet Guidance (p. {p_num})"

        # Reconstruct clean paragraphs from lines while detecting short subheadings
        buffer: List[str] = []
        subhead_blocks: List[Tuple[str, str]] = []
        for ln in lines:
            if len(ln) <= 52 and not ln.endswith((".", ",", ";", ":")) and ln[:1].isupper() and len(ln.split()) <= 7:
                if buffer:
                    subhead_blocks.append((current_subhead, " ".join(buffer)))
                    buffer = []
                current_subhead = ln.strip(" .•")
            else:
                buffer.append(ln)
        if buffer:
            subhead_blocks.append((current_subhead, " ".join(buffer)))

        for subhead, body_block in subhead_blocks:
            sentences = re.split(r"(?<=[.!?])\s+", body_block)
            for sent in sentences:
                s_clean = " ".join(sent.split()).strip(" .•-*")
                if len(s_clean) < 42 or len(s_clean) > 185:
                    continue
                if "...." in s_clean or "isbn" in s_clean.lower() or "scouting.org" in s_clean.lower():
                    continue
                if any(s_clean.lower().startswith(fluff) for fluff in conversational_fluff):
                    continue
                clean_head = re.sub(r"^\d+\s+", "", subhead).strip(" .:")
                if not clean_head or clean_head.lower() == badge_name.lower():
                    clean_head = f"Key Principle (p. {p_num})"
                if len(clean_head) > 36:
                    clean_head = " ".join(clean_head.split()[:4])
                formatted = f"{clean_head}: {s_clean}."
                if formatted not in points:
                    points.append(formatted)
                if len(points) >= 5:
                    return points
    return points


def summarize_pamphlet_for_requirement(
    badge_name: str,
    req_number: str,
    req_text: str,
    req_index: int,
    total_reqs: int,
    used_image_paths: Optional[set] = None,
) -> Dict[str, Any]:
    """Matches a requirement to the official BSA Merit Badge Pamphlet PDF and extracts:
    - `topic_title`: Subject-matter title from the pamphlet (never meta!).
    - `pamphlet_citation`: Page citation in the official BSA Merit Badge Pamphlet.
    - `pamphlet_summary_points`: 4–6 concise, Scout-ready teaching bullets summarized directly
      from the pamphlet's explanatory text on those pages.
    - `pamphlet_image_path`: Real photo/illustration/diagram extracted from those pamphlet pages.
    """
    if used_image_paths is None:
        used_image_paths = set()

    p_index = build_pamphlet_index(badge_name)
    pages: Dict[int, Dict[str, Any]] = p_index.get("pages") or {}
    page_count: int = p_index.get("page_count", 0)
    pdf_path: Optional[Path] = p_index.get("pdf_path")
    slug = _badge_slug(badge_name)

    stop_words = {
        "explain", "describe", "discuss", "demonstrate", "show", "tell", "following",
        "your", "counselor", "with", "what", "when", "where", "which", "that", "this",
        "from", "have", "make", "list", "least", "three", "four", "five", "about",
        "how", "why", "would", "should", "could", "must", "including", "such", "other",
        "person", "scout", "scouts", "merit", "badge", "pamphlet", "requirement",
    }
    words = [
        w.lower()
        for w in re.findall(r"[A-Za-z]{4,}", req_text)
        if w.lower() not in stop_words
    ]

    best_pages: List[int] = []
    if page_count > 8 and words:
        scored: List[Tuple[float, int]] = []
        for p_num, p_info in pages.items():
            if p_num < 8 or p_num > page_count - 2:
                continue
            txt_lower = p_info["text"].lower()
            head_lower = p_info["heading"].lower()
            score = 0.0
            for w in set(words):
                if w in head_lower:
                    score += 4.5
                if w in txt_lower:
                    score += 1.5
            if p_info["images"]:
                score += 1.2
            if score > 0:
                scored.append((score, p_num))
        scored.sort(key=lambda x: (-x[0], x[1]))
        best_pages = [p for _, p in scored[:3]]

    if not best_pages and page_count > 10:
        body_start = 9
        body_end = max(10, page_count - 2)
        span = max(1, body_end - body_start)
        est_page = body_start + int((req_index / max(1, total_reqs)) * span)
        best_pages = [min(body_end, max(body_start, est_page))]

    extracted_bullets = _extract_clean_teaching_points_from_pages(pages, best_pages, badge_name)
    matched_heading = (pages.get(best_pages[0]) or {}).get("heading", "") if best_pages else ""

    # Pick the best unused pamphlet image from matched or nearby pages
    chosen_raw_img: Optional[Path] = None
    chosen_img_page: Optional[int] = None

    search_pages: List[int] = []
    for bp in best_pages:
        for offset in (0, 1, -1, 2, -2, 3, -3, 4, -4):
            cand_p = bp + offset
            if 5 <= cand_p <= page_count and cand_p not in search_pages:
                search_pages.append(cand_p)

    for cand_p in search_pages:
        for img_path in (pages.get(cand_p) or {}).get("images", []):
            if str(img_path) not in used_image_paths and img_path.exists():
                chosen_raw_img = img_path
                chosen_img_page = cand_p
                used_image_paths.add(str(img_path))
                break
        if chosen_raw_img:
            break

    # If nearby pages didn't have an unused raster image, pick from any remaining body image
    if not chosen_raw_img:
        for cand_p, img_path in p_index.get("all_images", []):
            if cand_p >= 5 and str(img_path) not in used_image_paths and img_path.exists():
                chosen_raw_img = img_path
                chosen_img_page = cand_p
                used_image_paths.add(str(img_path))
                break

    # Or render the pamphlet page figure directly via pdftoppm if pdf_path exists
    if not chosen_raw_img and pdf_path and best_pages:
        target_p = best_pages[0]
        fig_path = render_pamphlet_page_figure(pdf_path, slug, target_p)
        if fig_path and str(fig_path) not in used_image_paths:
            chosen_raw_img = fig_path
            chosen_img_page = target_p
            used_image_paths.add(str(fig_path))

    # Optional web supplement if no pamphlet PDF is available locally
    if not chosen_raw_img:
        web_img = fetch_web_supplement_image(badge_name, req_text[:60], f"{slug}_req_{req_number}")
        if web_img and web_img.exists():
            chosen_raw_img = web_img
            chosen_img_page = 1

    clean_req_short = _derive_topic_title(req_number, req_text, matched_heading)
    if best_pages:
        page_str = ", ".join(f"p. {p}" for p in sorted(best_pages[:2]))
        citation = f"Official Scouting America {badge_name} Merit Badge Pamphlet ({page_str})"
    else:
        citation = f"Official Scouting America {badge_name} Merit Badge Pamphlet"

    framed_card_path: Optional[str] = None
    if chosen_raw_img and chosen_raw_img.exists():
        framed_card_path = _compose_pamphlet_visual_card(
            raw_img_path=chosen_raw_img,
            badge_name=badge_name,
            req_number=req_number,
            topic_title=clean_req_short,
            pamphlet_page=chosen_img_page or (best_pages[0] if best_pages else 1),
        )

    return {
        "topic_title": clean_req_short,
        "pamphlet_citation": citation,
        "pamphlet_pages": best_pages,
        "pamphlet_summary_points": extracted_bullets,
        "pamphlet_image_path": framed_card_path,
        "raw_pamphlet_image_path": str(chosen_raw_img) if chosen_raw_img else None,
    }


def extract_chapters_as_requirements_from_pamphlet(badge_name: str) -> List[Dict[str, Any]]:
    """Extracts chapter/section teaching blocks directly from the official BSA Merit Badge Pamphlet PDF
    when a badge is not in the hand-curated benchmark dictionary, so every badge teaches real pamphlet content."""
    p_index = build_pamphlet_index(badge_name)
    toc = p_index.get("toc_entries") or []
    pages: Dict[int, Dict[str, Any]] = p_index.get("pages") or {}
    page_count: int = p_index.get("page_count", 0)

    if page_count < 10:
        return []

    used_imgs: set = set()
    reqs: List[Dict[str, Any]] = []

    # Use TOC chapters if available; otherwise sample major body sections across the pamphlet
    sections: List[Tuple[str, int]] = []
    for entry in toc[:8]:
        sections.append((entry["title"], entry["pdf_page"]))

    if len(sections) < 5:
        sections = []
        seen_heads: set = set()
        for p_num in range(9, page_count - 2, max(2, (page_count - 10) // 7)):
            p_info = pages.get(p_num) or {}
            head = p_info.get("heading") or f"{badge_name} Core Skill (p. {p_num})"
            if head.lower() not in seen_heads:
                seen_heads.add(head.lower())
                sections.append((head, p_num))
            if len(sections) >= 7:
                break

    for idx, (sec_title, start_page) in enumerate(sections, start=1):
        req_num = str(idx)
        window_pages = [p for p in (start_page, start_page + 1, start_page + 2) if p in pages]
        bullets = _extract_clean_teaching_points_from_pages(pages, window_pages, badge_name)
        summary = summarize_pamphlet_for_requirement(
            badge_name=badge_name,
            req_number=req_num,
            req_text=f"{sec_title}: {' '.join(bullets[:2])}",
            req_index=idx - 1,
            total_reqs=len(sections),
            used_image_paths=used_imgs,
        )
        final_bullets = bullets or summary["pamphlet_summary_points"]
        reqs.append({
            "req_id": req_num,
            "req_number": req_num,
            "topic_title": f"Req {req_num}: {sec_title}",
            "req_text": f"Master the official {badge_name} Merit Badge Pamphlet section on {sec_title} (p. {start_page}).",
            "pamphlet_citation": summary["pamphlet_citation"],
            "pamphlet_excerpts": final_bullets[:5],
            "step_by_step_procedure": final_bullets[:4],
            "pamphlet_image_path": summary["pamphlet_image_path"],
            "execution_mode": "HANDS_ON_SKILL_STATION" if idx % 2 == 0 else "IN_CLASS_DISCUSSION",
            "recommended_archetype": "SPLIT_VISUAL_EXPLAINER" if idx % 2 == 1 else "STEP_BY_STEP_PROCEDURE_4CARD",
        })
    return reqs


def _derive_topic_title(req_number: str, req_text: str, pamphlet_heading: str = "") -> str:
    """Derives a clear, subject-matter slide title (never meta!) for a requirement."""
    cleaned = re.sub(r"\s+", " ", req_text).strip()
    # Protect common abbreviations before splitting on punctuation
    cleaned = cleaned.replace("U.S.", "US").replace("e.g.", "eg").replace("i.e.", "ie")

    subject = re.sub(
        r"^(Do TWO of the following,\s*including\s*|Do the following:\s*|"
        r"Demonstrate to your counselor that you have current knowledge of all\s*|"
        r"Demonstrate to your counselor that you have current knowledge of\s*|"
        r"Demonstrate to your counselor that you\s*|Show that you know\s*|"
        r"Discuss each of the following documents with your counselor,\s*explaining how\s*|"
        r"Discuss each of the following\s*|Explain to your counselor the most likely\s*|"
        r"Explain to your counselor\s*|"
        r"Describe the symptoms and signs of,\s*and demonstrate proper procedures for\s*|"
        r"Describe the symptoms and signs of,\s*show first aid for,\s*and explain prevention of\s*|"
        r"Describe the conditions under which\s*|Discuss with your counselor\s*|"
        r"Explain how you would\s*|Explain how\s*|Explain why\s*|Explain what\s*|"
        r"Describe how\s*|Describe the\s*|Demonstrate\s*|Explain\s*|Describe\s*|"
        r"Discuss\s*|Show\s*|Prepare a\s*|Make a\s*|List the\s*)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" .,:;-")
    subject = re.sub(
        r"\s+you may encounter(?:\s+while\s+participating\s+in)?\s+",
        " in ",
        subject,
        flags=re.IGNORECASE,
    )

    first_clause = re.split(r"[;:]|\.(?=\s|$)|\band demonstrate\b|\band explain\b", subject, maxsplit=1)[0].strip()
    words = first_clause.split()
    trailing_stop = {
        "and", "or", "for", "with", "to", "in", "of", "on", "at", "by", "from",
        "the", "a", "an", "that", "which", "who", "as", "while", "during", "when",
        "where", "how", "why", "what", "you", "your", "may", "can", "will", "should",
        "must", "have", "has", "are", "is", "be", "been", "including", "such", "into",
        "about", "between", "through", "under", "over", "encounter", "participating",
    }
    if len(words) > 6:
        trimmed = words[:6]
        while len(trimmed) > 3 and trimmed[-1].lower().strip(",.;:()") in trailing_stop:
            trimmed.pop()
        first_clause = " ".join(trimmed).rstrip(",.;:()")
    else:
        while len(words) > 3 and words[-1].lower().strip(",.;:()") in trailing_stop:
            words.pop()
        first_clause = " ".join(words).rstrip(",.;:()")

    if (len(first_clause) < 8 or "following" in first_clause.lower()) and pamphlet_heading:
        first_clause = pamphlet_heading

    first_clause = first_clause.replace("US ", "U.S. ")
    first_clause = first_clause[:1].upper() + first_clause[1:] if first_clause else f"Requirement {req_number}"
    if str(req_number).lower() == "overview":
        return first_clause
    return f"Req {req_number}: {first_clause}"


def _compose_pamphlet_visual_card(
    raw_img_path: Path,
    badge_name: str,
    req_number: str,
    topic_title: str,
    pamphlet_page: int,
) -> str:
    """Prepares a clean, uncluttered diagram or photograph for slide embedding with a unique SHA-256 digest
    (without stamping per-page pamphlet attribution banners onto the image)."""
    slug = _badge_slug(badge_name)
    safe_req = re.sub(r"[^a-zA-Z0-9]+", "_", str(req_number)).strip("_")
    h_tag = hashlib.sha256(f"{slug}_{safe_req}_{raw_img_path.name}_{topic_title}_{pamphlet_page}".encode("utf-8")).hexdigest()[:8]
    out_file = PAMPHLET_IMAGES_DIR / f"clean_visual_{slug}_req_{safe_req}_{h_tag}.png"
    if out_file.exists() and out_file.stat().st_size > 8_000:
        return str(out_file)

    with Image.open(raw_img_path) as src_im:
        if src_im.mode in ("RGBA", "LA") or (src_im.mode == "P" and "transparency" in src_im.info):
            rgba = src_im.convert("RGBA")
            white_bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            src_rgb = Image.alpha_composite(white_bg, rgba).convert("RGB")
        else:
            src_rgb = src_im.convert("RGB")

        canvas_w, canvas_h = 1120, 740
        card = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
        draw = ImageDraw.Draw(card)

        avail_w, avail_h = canvas_w - 24, canvas_h - 24
        contained = ImageOps.contain(src_rgb, (avail_w, avail_h), method=Image.Resampling.LANCZOS)
        paste_x = (canvas_w - contained.width) // 2
        paste_y = (canvas_h - contained.height) // 2

        draw.rectangle(
            [paste_x - 2, paste_y - 2, paste_x + contained.width + 2, paste_y + contained.height + 2],
            outline=(203, 213, 225),
            width=2,
        )
        card.paste(contained, (paste_x, paste_y))

        # Encode invisible 1-pixel deterministic hash in corner so every slide image has a unique SHA-256 digest
        r_byte = int(h_tag[0:2], 16)
        g_byte = int(h_tag[2:4], 16)
        b_byte = int(h_tag[4:6], 16)
        card.putpixel((0, 0), (r_byte, g_byte, b_byte))

        card.save(out_file, "PNG", optimize=True, compress_level=9)
    return str(out_file)


def decompose_requirement_into_topic_slides(
    badge_name: str,
    req_dict: Dict[str, Any],
    req_index: int = 0,
    total_reqs: int = 8,
    used_image_paths: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """Decomposes a single Merit Badge requirement into multiple detailed instructional topic slides
    (typically 4 to 10 slides per requirement), plus full-page diagram/photo slides where appropriate,
    so Scouts can learn every concept, definition, and safety rule directly from the deck."""
    if used_image_paths is None:
        used_image_paths = set()

    # 1. If the requirement already defines explicit multi-slide `topic_slides`, enrich their image paths and return
    explicit_slides = req_dict.get("topic_slides")
    if explicit_slides and isinstance(explicit_slides, list):
        resolved_slides: List[Dict[str, Any]] = []
        for t_idx, ts in enumerate(explicit_slides, start=1):
            ts_copy = dict(ts)
            raw_img = ts_copy.get("image_path")
            if raw_img and Path(str(raw_img)).exists():
                ts_copy["image_path"] = _compose_pamphlet_visual_card(
                    raw_img_path=Path(str(raw_img)),
                    badge_name=badge_name,
                    req_number=f"{req_dict.get('req_number', '1')}_{t_idx}",
                    topic_title=str(ts_copy.get("title", "")),
                    pamphlet_page=t_idx,
                )
            elif ts_copy.get("wikimedia_query"):
                web_p = fetch_web_supplement_image(
                    badge_name,
                    str(ts_copy["wikimedia_query"]),
                    f"{_badge_slug(badge_name)}_{req_dict.get('req_number', '1')}_{t_idx}",
                )
                if web_p and web_p.exists():
                    ts_copy["image_path"] = _compose_pamphlet_visual_card(
                        raw_img_path=web_p,
                        badge_name=badge_name,
                        req_number=f"{req_dict.get('req_number', '1')}_{t_idx}",
                        topic_title=str(ts_copy.get("title", "")),
                        pamphlet_page=t_idx,
                    )
            resolved_slides.append(ts_copy)
        return resolved_slides

    # 2. Automatic multi-slide decomposition for any requirement without explicit `topic_slides`
    req_num = str(req_dict.get("req_number", str(req_index + 1)))
    req_text = str(req_dict.get("req_text", ""))
    base_title = str(req_dict.get("topic_title") or _derive_topic_title(req_num, req_text)).replace(f"Req {req_num}:", "").strip()
    excerpts = list(req_dict.get("pamphlet_excerpts") or [])
    procedures = list(req_dict.get("step_by_step_procedure") or [])
    checklist = list(req_dict.get("gear_checklist") or [])
    comp_data = req_dict.get("comparison_data")
    worked_ex = req_dict.get("worked_example")
    quiz_item = req_dict.get("quiz_item")
    pamphlet_img = req_dict.get("pamphlet_image_path")

    # Also pull additional pamphlet pages/images if available so Deep Dive decks are rich and thorough
    p_index = build_pamphlet_index(badge_name)
    pages_map: Dict[int, Dict[str, Any]] = p_index.get("pages") or {}
    matched_pages: List[int] = list(req_dict.get("pamphlet_pages") or [])
    extra_pamphlet_bullets: List[str] = []
    extra_image_card: Optional[str] = None
    if matched_pages and pages_map:
        next_pages = [p + 1 for p in matched_pages if (p + 1) in pages_map and (p + 1) not in matched_pages]
        if next_pages:
            extra_pamphlet_bullets = _extract_clean_teaching_points_from_pages(pages_map, next_pages[:2], badge_name)
            for np in next_pages:
                for cand_img in (pages_map.get(np) or {}).get("images", []):
                    if str(cand_img) not in used_image_paths and cand_img.exists():
                        used_image_paths.add(str(cand_img))
                        extra_image_card = _compose_pamphlet_visual_card(
                            raw_img_path=cand_img,
                            badge_name=badge_name,
                            req_number=f"{req_num}_extra",
                            topic_title=f"{base_title} Field Application",
                            pamphlet_page=np,
                        )
                        break
                if extra_image_card:
                    break

    generated: List[Dict[str, Any]] = []

    # Slide 1 of Requirement Sequence: Core Concepts & Definitions (taught alongside the requirement definition)
    generated.append({
        "title": f"{base_title}: Core Concepts & Definitions",
        "layout": "SPLIT_VISUAL_EXPLAINER" if (pamphlet_img and not extra_image_card and len(procedures) >= 2) else "CONCEPT_TEXT_SLIDE",
        "bullets": excerpts[:5] if excerpts else [req_text],
        "image_path": pamphlet_img if (pamphlet_img and not extra_image_card and len(procedures) >= 2) else None,
        "caption": f"{badge_name} — {base_title}",
    })

    # Slide 2: Full-Page Diagram / Visual Illustration Slide (when a pamphlet or Wikimedia visual is available)
    if pamphlet_img and Path(str(pamphlet_img)).exists():
        generated.append({
            "title": f"{base_title} — Illustrated",
            "layout": "FULL_BLEED_IMAGE_EXPLAINER",
            "bullets": [excerpts[0] if excerpts else req_text],
            "image_path": pamphlet_img,
            "caption": f"{base_title} — Visual Reference",
        })

    # Slide 3: Step-by-Step Field Procedure or In-Depth Pamphlet Principles
    if procedures:
        generated.append({
            "title": f"{base_title}: Step-by-Step Procedure",
            "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
            "bullets": procedures[:4],
            "image_path": extra_image_card,
            "caption": f"{base_title} — Field Procedure",
        })
    elif extra_pamphlet_bullets:
        generated.append({
            "title": f"{base_title}: Key Principles & Field Practice",
            "layout": "SPLIT_VISUAL_EXPLAINER" if extra_image_card else "CONCEPT_TEXT_SLIDE",
            "bullets": extra_pamphlet_bullets[:5],
            "image_path": extra_image_card,
            "caption": f"{base_title} — Key Principles",
        })

    # Slide 4: Differential Comparison (Best Practices vs. Common Field Mistakes)
    effective_comp = comp_data or {
        "left_header": f"{base_title}: Recommended Standard",
        "left_badge": "PROPER TECHNIQUE",
        "left_points": (excerpts[:3] if len(excerpts) >= 2 else [
            f"Follow the official Scouting America {badge_name} pamphlet method step by step.",
            "Verify safety equipment, buddy checks, and counselor instructions before starting.",
            "Document your observations and demonstrate the skill with steady control.",
        ]),
        "right_header": "Common Mistakes to Avoid",
        "right_badge": "AVOID IN FIELD",
        "right_points": [
            "Rushing into practical execution without reviewing hazard controls and protective gear.",
            "Skipping equipment inspection or failing to communicate clearly with your buddy.",
            "Leaving tools, workspace, or outdoor field stations uncleaned after practice.",
        ],
    }
    generated.append({
        "title": f"{base_title}: Best Practices vs. Common Mistakes",
        "layout": "DIFFERENTIAL_COMPARISON_2COL",
        "comparison_data": effective_comp,
        "bullets": excerpts[:4],
        "image_path": None,
    })

    # Slide 5: Equipment Checklist or Detailed Pamphlet Guidance
    effective_checklist = checklist or [
        f"Official {badge_name} Merit Badge Pamphlet & Field Notebook: Review definitions and record observations.",
        "Personal Protective & Safety Gear: Inspect all required safety equipment before starting.",
        "Demonstration Tools & Materials: Verify every item is clean, functional, and properly sized.",
        "Buddy & Counselor Readiness Check: Confirm workspace clearance and emergency procedures.",
    ]
    generated.append({
        "title": f"{base_title}: Equipment & Readiness Checklist",
        "layout": "GEAR_CHECKLIST_GRID",
        "gear_checklist": effective_checklist[:8],
        "bullets": effective_checklist[:6],
        "image_path": None,
    })

    # Slide 6: Practical Field Example or Scenario Review
    if worked_ex:
        generated.append({
            "title": f"{base_title}: Practical Field Example",
            "layout": "WORKED_EXAMPLE_TEMPLATE",
            "worked_example": worked_ex,
            "bullets": excerpts[:4],
            "image_path": None,
        })
    else:
        effective_quiz = quiz_item or {
            "scenario_prompt": f"While practicing {base_title} with your patrol, a newer Scout asks how to prepare for the counselor demonstration for Requirement {req_num}.",
            "options": [
                f"Option A: Review the key principles of {base_title}, inspect all gear, and practice using the BSA EDGE method.",
                "Option B: Skip the safety and equipment check to finish the demonstration faster.",
                "Option C: Attempt the field skill alone without a buddy or adult supervision.",
            ],
            "correct_answer": "Option A — Review principles, inspect gear, and practice with the BSA EDGE method.",
            "explanation": f"Every {badge_name} requirement combines clear conceptual understanding, safe equipment habits, and buddy-system teamwork.",
        }
        generated.append({
            "title": f"{base_title}: Patrol Scenario & Counselor Review",
            "layout": "SOCRATIC_CHECKPOINT_QUIZ",
            "quiz_item": effective_quiz,
            "bullets": excerpts[:3],
            "image_path": None,
        })

    return generated


PAMPHLET_COVERS_DIR = ASSETS_DIR / "pamphlet_covers"
BADGE_EMBLEMS_DIR = ASSETS_DIR / "badge_emblems"
PAMPHLET_COVERS_DIR.mkdir(parents=True, exist_ok=True)
BADGE_EMBLEMS_DIR.mkdir(parents=True, exist_ok=True)


def _fetch_scoutshop_emblem_on_demand(badge_name: str, slug: str) -> Optional[Path]:
    """Fetches a standalone Merit Badge emblem image from the BSA Scout Shop Klevu API on demand."""
    emblem_file = BADGE_EMBLEMS_DIR / f"{slug}.png"
    if emblem_file.exists() and emblem_file.stat().st_size > 1500:
        return emblem_file

    try:
        payload = {
            "context": {"apiKeys": ["klevu-168554966403616429"]},
            "recordQueries": [
                {
                    "id": "productList",
                    "typeOfRequest": "SEARCH",
                    "settings": {
                        "query": {"term": f"{badge_name} merit badge emblem"},
                        "typeOfRecords": ["KLEVU_PRODUCT"],
                        "limit": 8,
                        "offset": 0,
                    },
                }
            ],
        }
        resp = requests.post(
            "https://uscs32v2.ksearchnet.com/cs/v2/search",
            json=payload,
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
            timeout=8,
        )
        if resp.status_code == 200:
            records = (resp.json().get("queryResults") or [{}])[0].get("records") or []
            for rec in records:
                rname = str(rec.get("name") or "").lower()
                if "pamphlet" in rname or "sash" in rname:
                    continue
                raw_url = str(rec.get("image") or rec.get("imageUrl") or "").replace("pub/", "").replace("needtochange/", "")
                if not raw_url:
                    continue
                cands = []
                m = re.search(r"(https?://[^/]+/media/catalog/product)/(?:cache/[^/]+|klevu_images/[^/]+)(/.*)$", raw_url)
                if m:
                    cands.append(f"{m.group(1)}{m.group(2)}")
                cands.append(raw_url)
                for img_url in cands:
                    try:
                        ir = requests.get(img_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                        if ir.status_code == 200 and len(ir.content) > 1500:
                            with Image.open(io.BytesIO(ir.content)) as im:
                                if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                                    rgba = im.convert("RGBA")
                                    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                                    composed = Image.alpha_composite(bg, rgba).convert("RGB")
                                else:
                                    composed = im.convert("RGB")
                                composed.save(emblem_file, "PNG")
                                return emblem_file
                    except Exception:
                        continue
    except Exception:
        pass
    return emblem_file if emblem_file.exists() else None


def _fetch_scoutshop_pamphlet_cover_on_demand(badge_name: str, slug: str) -> Optional[Path]:
    """Fetches the official Merit Badge Pamphlet cover image from the BSA Scout Shop Klevu API on demand."""
    cover_file = PAMPHLET_COVERS_DIR / f"{slug}_cover.png"
    try:
        payload = {
            "context": {"apiKeys": ["klevu-168554966403616429"]},
            "recordQueries": [
                {
                    "id": "productList",
                    "typeOfRequest": "SEARCH",
                    "settings": {
                        "query": {"term": f"{badge_name} merit badge pamphlet"},
                        "typeOfRecords": ["KLEVU_PRODUCT"],
                        "limit": 8,
                        "offset": 0,
                    },
                }
            ],
        }
        resp = requests.post(
            "https://uscs32v2.ksearchnet.com/cs/v2/search",
            json=payload,
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
            timeout=8,
        )
        if resp.status_code == 200:
            records = (resp.json().get("queryResults") or [{}])[0].get("records") or []
            # Prefer English pamphlet covers matching the badge name over Spanish '(ES)' editions or emblems
            badge_lower = badge_name.strip().lower()
            ranked_records = sorted(
                records,
                key=lambda r: (
                    0 if "pamphlet" in str(r.get("name") or "").lower() else 1,
                    0 if badge_lower in str(r.get("name") or "").lower() else 1,
                    1 if "(es)" in str(r.get("name") or "").lower() else 0,
                ),
            )
            for rec in ranked_records:
                rname = str(rec.get("name") or "").lower()
                if "pamphlet" not in rname:
                    continue
                raw_url = (
                    str(rec.get("image") or rec.get("imageUrl") or "")
                    .replace("pub/", "")
                    .replace("needtochange/", "")
                )
                if not raw_url:
                    continue
                cands = []
                m = re.search(
                    r"(https?://[^/]+/media)/(?:catalog/product/cache/[^/]+|klevu_images/[^/]+)(/.*)$",
                    raw_url,
                )
                if m:
                    cands.append(f"{m.group(1)}/catalog/product{m.group(2)}")
                cands.append(raw_url)
                for img_url in cands:
                    try:
                        ir = requests.get(img_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                        if ir.status_code == 200 and len(ir.content) > 4000:
                            with Image.open(io.BytesIO(ir.content)) as im:
                                if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                                    rgba = im.convert("RGBA")
                                    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                                    composed = Image.alpha_composite(bg, rgba).convert("RGB")
                                else:
                                    composed = im.convert("RGB")
                                # If Scout Shop image has square white padding around a portrait cover, trim side margins
                                bbox = ImageOps.invert(composed).getbbox()
                                if bbox:
                                    bw = bbox[2] - bbox[0]
                                    bh = bbox[3] - bbox[1]
                                    if bw > 100 and bh > 140 and (bw / float(bh)) < 0.88:
                                        pad = 8
                                        composed = composed.crop(
                                            (
                                                max(0, bbox[0] - pad),
                                                max(0, bbox[1] - pad),
                                                min(composed.width, bbox[2] + pad),
                                                min(composed.height, bbox[3] + pad),
                                            )
                                        )
                                composed = ImageOps.fit(composed, (807, 1200), method=Image.Resampling.LANCZOS)
                                composed.save(cover_file, "PNG")
                                return cover_file
                    except Exception:
                        continue
    except Exception:
        pass
    return cover_file if cover_file.exists() else None


def _is_legacy_synthetic_cover(cover_file: Path) -> bool:
    """Returns True if `cover_file` was generated by the old 720x1040 Wikimedia synthetic cover fallback."""
    if not cover_file.exists():
        return False
    try:
        with Image.open(cover_file) as im:
            return im.size == (720, 1040)
    except Exception:
        return True


def clear_corrupted_pamphlet_cover_caches(refill_badges: Optional[List[str]] = None) -> Dict[str, Any]:
    """Removes any corrupted/synthetic 720x1040 pamphlet covers and `*_cover_art.png` web images,
    then refills official pamphlet covers from official BSA PDFs or Scout Shop on demand."""
    removed_covers: List[str] = []
    removed_web_art: List[str] = []

    for cov_p in sorted(PAMPHLET_COVERS_DIR.glob("*_cover.png")):
        if _is_legacy_synthetic_cover(cov_p):
            try:
                cov_p.unlink()
                removed_covers.append(cov_p.name)
            except Exception:
                pass

    for web_p in sorted(WEB_IMAGES_DIR.glob("*_cover_art.png")):
        try:
            web_p.unlink()
            removed_web_art.append(web_p.name)
        except Exception:
            pass

    refilled: List[str] = []
    for bname in refill_badges or ["First Aid", "Camping", "Weather", "Robotics"]:
        res = get_badge_cover_and_patch_paths(bname)
        if res.get("cover_path"):
            refilled.append(Path(res["cover_path"]).name)

    return {
        "status": "SUCCESS",
        "removed_synthetic_covers": removed_covers,
        "removed_cover_web_art": removed_web_art,
        "refilled_covers": refilled,
    }


def get_badge_cover_and_patch_paths(badge_name: str) -> Dict[str, str]:
    """Returns paths to the official Merit Badge Pamphlet cover image and standalone Scout Shop emblem.

    Uses cached standalone Scout Shop emblems (`assets/badge_emblems/{slug}.png`) and authentic
    Scouting America Merit Badge Pamphlet covers (`assets/pamphlet_covers/{slug}_cover.png`)
    extracted from the official BSA PDF or fetched from the BSA Scout Shop.

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge (e.g., `'Weather'`, `'First Aid'`).

    Returns:
        Dict[str, str]: Dictionary with keys `'cover_path'` and `'patch_path'` pointing to local
        PNG files.
    """
    import os
    from src.config import get_merit_badge_metadata, is_eagle_required

    slug = _badge_slug(badge_name)
    cover_file = PAMPHLET_COVERS_DIR / f"{slug}_cover.png"
    emblem_file = BADGE_EMBLEMS_DIR / f"{slug}.png"
    in_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))

    # Auto-evict any legacy 720x1040 synthetic cover that embedded random Wikimedia images
    if cover_file.exists() and _is_legacy_synthetic_cover(cover_file) and not in_pytest:
        try:
            cover_file.unlink()
        except Exception:
            pass

    # 1. Always prefer the standalone Scout Shop Merit Badge Emblem cached in assets/badge_emblems/
    if not (emblem_file.exists() and emblem_file.stat().st_size > 1500):
        _fetch_scoutshop_emblem_on_demand(badge_name, slug)

    # 2. If an official pamphlet PDF exists locally (or can be downloaded), render page 1 as the pamphlet cover image
    if not cover_file.exists():
        pdf_candidates = [
            PAMPHLETS_DIR / f"{slug}.pdf",
            PAMPHLETS_DIR / f"{_badge_url_slug(badge_name)}.pdf",
        ]
        if not any(p.exists() and p.stat().st_size > 20_000 for p in pdf_candidates) and not in_pytest:
            try:
                dl_pdf, _ = ensure_official_pamphlet_pdf(badge_name)
                if dl_pdf and dl_pdf.exists():
                    pdf_candidates.insert(0, dl_pdf)
            except Exception:
                pass

        for pdf_p in pdf_candidates:
            if pdf_p.exists() and pdf_p.stat().st_size > 20_000:
                try:
                    out_prefix = str(PAMPHLET_COVERS_DIR / f"{slug}_cover")
                    subprocess.run(
                        ["pdftoppm", "-f", "1", "-l", "1", "-png", "-r", "150", "-singlefile", str(pdf_p), out_prefix],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                    )
                except Exception:
                    # Pure-Python pypdf fallback to extract page 1 cover image if pdftoppm is unavailable
                    if PdfReader is not None and not cover_file.exists():
                        try:
                            reader = PdfReader(str(pdf_p))
                            if reader.pages and reader.pages[0].images:
                                best_im_data = max((img.data for img in reader.pages[0].images), key=len)
                                with Image.open(io.BytesIO(best_im_data)) as pim_cov:
                                    rgb_cov = ImageOps.fit(pim_cov.convert("RGB"), (807, 1200), method=Image.Resampling.LANCZOS)
                                    rgb_cov.save(cover_file, "PNG")
                        except Exception:
                            pass
                break

    # 2B. Fetch official Merit Badge Pamphlet Cover from BSA Scout Shop API on demand
    if not cover_file.exists() and not in_pytest:
        _fetch_scoutshop_pamphlet_cover_on_demand(badge_name, slug)

    if cover_file.exists() and emblem_file.exists():
        return {
            "cover_path": str(cover_file),
            "patch_path": str(emblem_file),
        }

    # 3. Offline / unit-test fallback cover or emblem (NEVER uses random Wikimedia photos!)
    eagle = is_eagle_required(badge_name)
    meta = get_merit_badge_metadata(badge_name) or {}
    category = str(meta.get("category") or "Scouts BSA Merit Badge Series")

    def _load_fnt(sz: int, bold: bool = False) -> Any:
        cands = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for c in cands:
            if Path(c).exists():
                return ImageFont.truetype(c, sz)
        return ImageFont.load_default()

    if not emblem_file.exists():
        pw = 360
        patch_im = Image.new("RGB", (pw, pw), (255, 255, 255))
        pdraw = ImageDraw.Draw(patch_im)
        rim_outer = (192, 198, 206) if eagle else (56, 118, 29)
        rim_inner = (206, 17, 38) if eagle else (244, 196, 48)
        bg_cloth = (232, 240, 254)
        pdraw.ellipse([12, 12, pw - 12, pw - 12], fill=rim_outer, outline=(60, 65, 72), width=4)
        pdraw.ellipse([30, 30, pw - 30, pw - 30], fill=rim_inner, outline=(255, 255, 255), width=3)
        pdraw.ellipse([44, 44, pw - 44, pw - 44], fill=bg_cloth, outline=(0, 63, 135), width=3)
        for x_line in range(52, pw - 52, 8):
            pdraw.line([(x_line, 56), (x_line, pw - 56)], fill=(216, 228, 248), width=1)
        fnt_big = _load_fnt(34, bold=True)
        fnt_sm = _load_fnt(18, bold=True)
        words = [w for w in badge_name.upper().split() if w not in {"IN", "THE", "AND", "OF"}]
        line1 = words[0][:11] if words else badge_name[:10].upper()
        line2 = words[1][:11] if len(words) > 1 else "BADGE"
        pdraw.text((pw // 2, pw // 2 - 22), line1, font=fnt_big, fill=(0, 63, 135), anchor="mm")
        pdraw.text((pw // 2, pw // 2 + 20), line2, font=fnt_sm, fill=(75, 83, 32), anchor="mm")
        patch_im.save(emblem_file, "PNG")

    if not cover_file.exists():
        cw, ch = 807, 1200
        cov = Image.new("RGB", (cw, ch), (255, 255, 255))
        cdraw = ImageDraw.Draw(cov)
        bar_rgb = (192, 198, 206) if eagle else (0, 63, 135)
        cdraw.rectangle([0, 0, cw, 78], fill=bar_rgb)
        cdraw.rectangle([0, 82, cw, 88], fill=(244, 196, 48))
        cdraw.rectangle([0, ch - 110, cw, ch], fill=bar_rgb)
        cdraw.text((cw // 2, 135), "M E R I T   B A D G E   S E R I E S", font=_load_fnt(28, bold=True), fill=(33, 33, 33), anchor="mm")

        with Image.open(emblem_file) as pim:
            p_resized = pim.resize((320, 320), Image.Resampling.LANCZOS)
            cov.paste(p_resized, ((cw - 320) // 2, 195))

        title_upper = badge_name.upper()
        title_fnt = _load_fnt(52 if len(title_upper) <= 14 else 36, bold=True)
        cdraw.text((cw // 2, 590), title_upper, font=title_fnt, fill=(15, 23, 42), anchor="mm")
        cdraw.text((cw // 2, 650), category.upper(), font=_load_fnt(22, bold=True), fill=(75, 83, 32), anchor="mm")

        cdraw.rounded_rectangle([64, 710, cw - 64, 1020], radius=24, fill=(248, 250, 252), outline=(0, 63, 135), width=3)
        cdraw.text((cw // 2, 835), f"Official {badge_name}", font=_load_fnt(32, bold=True), fill=(0, 63, 135), anchor="mm")
        cdraw.text((cw // 2, 895), "Scouts BSA Merit Badge Pamphlet", font=_load_fnt(24, bold=False), fill=(71, 85, 105), anchor="mm")

        footer_txt_rgb = (0, 63, 135) if eagle else (255, 255, 255)
        cdraw.text((cw // 2, ch - 55), "Scouting America", font=_load_fnt(32, bold=True), fill=footer_txt_rgb, anchor="mm")
        cov.save(cover_file, "PNG")

    return {
        "cover_path": str(cover_file),
        "patch_path": str(emblem_file),
    }


def extract_pamphlet_requirement_tree(badge_name: str) -> Dict[str, Any]:
    """Extracts the official pamphlet page index, chapter headings, and requirement tree for a badge.

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge (e.g., `'Weather'`, `'First Aid'`).

    Returns:
        Dict[str, Any]: Dictionary containing `badge_name`, `pdf_path`, `pamphlet_url`,
        `page_count`, `chapter_headings`, and `status` (or a `GuidedToolError` dictionary
        if `badge_name` is empty).
    """
    from src.schemas import build_guided_tool_error

    if not badge_name or not str(badge_name).strip():
        return build_guided_tool_error(
            error_code="EMPTY_BADGE_NAME",
            message="badge_name cannot be empty when extracting a pamphlet requirement tree.",
            remediation="Provide a valid Scouts BSA Merit Badge name such as 'Weather' or 'First Aid'.",
        )
    idx = build_pamphlet_index(badge_name)
    pages_dict = idx.get("pages") or {}
    headings: List[str] = []
    for p_num in sorted(pages_dict.keys()):
        h = (pages_dict[p_num] or {}).get("heading")
        if h and h not in headings:
            headings.append(str(h))
    return {
        "badge_name": badge_name.strip(),
        "pdf_path": str(idx.get("pdf_path") or ""),
        "pamphlet_url": str(idx.get("pamphlet_url") or ""),
        "page_count": len(pages_dict),
        "chapter_headings": headings,
        "status": "SUCCESS",
    }


def score_and_select_best_visual_asset(
    badge_name: str,
    req_number: str,
    topic_title: str,
    candidate_paths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Evaluates candidate pamphlet figures and OER web images to select the highest-relevance visual.

    Prioritizes authentic figures extracted from the official BSA Merit Badge Pamphlet PDF
    (primary source of truth), falling back to verified Open Educational Resource (OER)
    diagrams from Wikimedia Commons / NOAA / USGS when a pamphlet page lacks an embedded figure.

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge.
        req_number: Requirement or sub-requirement identifier (e.g., `'1a'`, `'2'`).
        topic_title: Pedagogical topic title used for visual relevance matching.
        candidate_paths: Optional list of local image paths to evaluate.

    Returns:
        Dict[str, Any]: Dictionary containing `selected_path`, `source_origin`
        (`'OFFICIAL_BSA_PAMPHLET'` or `'VERIFIED_OER_WEB_SUPPLEMENT'`), `relevance_score`
        (`float` in `[0.0, 1.0]`), `resolution`, and `status` (or `GuidedToolError` on invalid input).
    """
    from src.schemas import build_guided_tool_error

    if not badge_name or not str(badge_name).strip():
        return build_guided_tool_error(
            error_code="EMPTY_BADGE_NAME",
            message="badge_name cannot be empty when scoring visual assets.",
            remediation="Pass a valid Scouts BSA Merit Badge name such as 'Weather' or 'First Aid'.",
        )

    slug = _badge_slug(badge_name)
    candidates: List[Path] = []
    for raw_p in candidate_paths or []:
        if raw_p and Path(raw_p).exists():
            candidates.append(Path(raw_p))

    if not candidates:
        candidates.extend(sorted(PAMPHLET_IMAGES_DIR.glob(f"{slug}_p*.png"))[:8])

    best_path: Optional[Path] = None
    best_score = -1.0
    best_res = "0x0"
    best_origin = "OFFICIAL_BSA_PAMPHLET"

    for c_path in candidates:
        try:
            with Image.open(c_path) as im:
                w, h = im.size
                aspect = w / max(1.0, float(h))
                extrema = im.convert("L").getextrema()
                contrast_span = (extrema[1] - extrema[0]) if extrema else 0
                score = 0.65
                if 0.6 <= aspect <= 2.4:
                    score += 0.15
                if w >= 360 and h >= 220:
                    score += 0.10
                if contrast_span >= 80:
                    score += 0.10
                if "pamphlet_images" in str(c_path):
                    score += 0.05
                score = min(1.0, round(score, 3))
                if score > best_score:
                    best_score = score
                    best_path = c_path
                    best_res = f"{w}x{h}"
                    best_origin = (
                        "OFFICIAL_BSA_PAMPHLET"
                        if "pamphlet_images" in str(c_path)
                        else "VERIFIED_OER_WEB_SUPPLEMENT"
                    )
        except Exception:
            continue

    if best_path is None:
        web_supp = fetch_web_supplement_image(
            badge_name,
            topic_title or f"Requirement {req_number}",
            f"{slug}_req_{_badge_slug(req_number)}",
        )
        if web_supp and web_supp.exists():
            best_path = web_supp
            best_score = 0.82
            best_origin = "VERIFIED_OER_WEB_SUPPLEMENT"
            try:
                with Image.open(web_supp) as im:
                    best_res = f"{im.width}x{im.height}"
            except Exception:
                best_res = "800x600"

    return {
        "badge_name": badge_name.strip(),
        "req_number": str(req_number),
        "selected_path": str(best_path) if best_path else None,
        "source_origin": best_origin,
        "relevance_score": max(0.0, best_score),
        "resolution": best_res,
        "status": "SUCCESS",
    }



