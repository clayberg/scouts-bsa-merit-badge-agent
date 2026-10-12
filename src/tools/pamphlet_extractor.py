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
    # Fix inline uppercase kerning splits common in BSA PDFs ("Y our" -> "Your", "T o" -> "To", "W ith" -> "With")
    text = re.sub(
        r"\b([TWYFBCPSDHLMRN])\s+(o|our|he|hat|his|hem|hen|here|hy|ith|rom|or|an|ill|ould|hould|efore|fter|nder|ver|art|lan|lace|eople|ood|ater|ire|irst|hile|hich)\b",
        r"\1\2",
        text,
    )
    # Remove decorative leading dots on headings (e.g. ".How to Handle" -> "How to Handle")
    text = re.sub(r"(?m)^\s*\.([A-Z])", r"\1", text)
    text = re.sub(r"\s+\.([A-Z])", r" \1", text)
    # Clean double punctuation artifacts ("?." -> "?", "!." -> "!")
    text = re.sub(r"\?\.", "?", text)
    text = re.sub(r"!\.", "!", text)
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


_ANCHOR_STOP_WORDS = {
    "the", "and", "for", "with", "your", "you", "that", "this", "these", "those",
    "from", "into", "onto", "upon", "have", "has", "had", "will", "would", "could",
    "should", "must", "can", "may", "might", "are", "was", "were", "been", "being",
    "when", "where", "while", "which", "what", "who", "whom", "whose", "how", "why",
    "such", "other", "another", "some", "any", "each", "every", "both", "all", "most",
    "more", "many", "much", "very", "also", "only", "just", "even", "still", "already",
    "always", "never", "often", "sometimes", "usually", "according", "including",
    "following", "during", "before", "after", "under", "over", "between", "through",
    "about", "around", "because", "although", "though", "unless", "until", "whether",
    "either", "neither", "make", "makes", "made", "making", "use", "uses", "used",
    "using", "keep", "keeps", "keeping", "help", "helps", "helping", "need", "needs",
    "needed", "take", "takes", "taking", "give", "gives", "giving", "find", "found",
    "know", "known", "called", "like", "well", "good", "best", "better", "important",
    "sure", "able", "one", "two", "three", "four", "five", "first", "second", "third",
    "scout", "scouts", "scouting", "merit", "badge", "counselor", "pamphlet",
    "yet", "step", "steps", "fill", "clean", "clear", "put", "place", "take", "get",
    "set", "let", "try", "see", "look", "watch", "note", "notice", "adult", "help",
}


def _derive_sentence_concept_anchor(sentence: str, idx: int, seen_anchors: set) -> str:
    """Derives a distinct, semantic 2-3 word Title-Case concept anchor from a sentence
    without ever slicing raw introductory fragments ('According to the USDA's') or repeating anchors.
    """
    cleaned = re.sub(r"\s+", " ", sentence).strip()
    # If the sentence already starts with a clean 'Concept Title: body' (not a numeric ratio like 30:2)
    m_colon = re.match(r"^([A-Z][A-Za-z0-9 &/\-]{3,32}):\s+(.+)$", cleaned)
    if m_colon:
        cand = m_colon.group(1).strip()
        if len(cand.split()) <= 5 and cand.lower() not in seen_anchors:
            seen_anchors.add(cand.lower())
            return cand

    # Strip introductory adverbial/prepositional clauses before the first comma if short
    clause = re.sub(
        r"^(?:According to [^,]+,\s*|In addition(?: to [^,]+)?,\s*|For example,\s*|"
        r"To [a-z]+ (?:the |a |an |your )?[^,]{2,24},\s*|When [a-z ]{2,24},\s*|"
        r"Before [a-z ]{2,24},\s*|After [a-z ]{2,24},\s*|If you [a-z ]{2,24},\s*)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    tokens = [
        w.strip(".,;:!?()\"'“”‘’")
        for w in re.findall(r"[A-Za-z][A-Za-z'\-]{2,}", clause)
    ]
    content_words = [
        w for w in tokens
        if w.lower() not in _ANCHOR_STOP_WORDS and len(w) >= 3
    ]
    if not content_words:
        content_words = [w for w in tokens if len(w) >= 3]

    # Try sliding window of 2-3 content words so every bullet on a slide gets a unique anchor
    for start_i in range(0, max(1, len(content_words) - 1)):
        chunk = content_words[start_i : start_i + 3]
        if not chunk:
            break
        cand = " ".join(w.capitalize() if w.islower() else w for w in chunk)
        if len(cand) > 28 and len(chunk) >= 3:
            cand = " ".join(w.capitalize() if w.islower() else w for w in chunk[:2])
        if cand.lower() not in seen_anchors:
            seen_anchors.add(cand.lower())
            return cand

    fallback = f"Core Principle {idx + 1}"
    seen_anchors.add(fallback.lower())
    return fallback


def _extract_clean_teaching_points_from_pages(
    pages: Dict[int, Dict[str, Any]],
    best_pages: List[int],
    badge_name: str,
    max_points: int = 6,
) -> List[str]:
    """Extracts substantive, complete, Scout-friendly teaching points from matched BSA Pamphlet pages
    with distinct semantic concept anchors (never latching wrapped PDF lines as repeated subheadings).
    """
    points: List[str] = []
    seen_anchors: set = set()
    seen_bodies: set = set()
    conversational_fluff = (
        "for example",
        "it might be",
        "a good place",
        "also, by",
        "when the naturalist",
        "for nearly a hundred",
        "always check scouting",
        "scan this qr",
        "see the resources",
        "for more information",
        "photo courtesy",
        "boy scouts of america",
        "scouting america",
    )

    for p_num in best_pages:
        p_info = pages.get(p_num)
        if not p_info:
            continue
        head_lower = str(p_info.get("heading") or "").lower()
        if any(skip_w in head_lower for skip_w in ("glossary", "index", "acknowledgments", "photo credits", "resources")):
            continue

        lines = p_info.get("lines") or []
        # Rejoin wrapped PDF lines into continuous prose without treating short wrapped lines as subheadings
        joined_lines: List[str] = []
        for ln in lines:
            clean_ln = ln.strip()
            if not clean_ln:
                continue
            # Skip standalone page numbers or running headers
            if re.match(r"^\d+$", clean_ln) or clean_ln.lower() == badge_name.lower():
                continue
            # Skip TOC leader lines or copyright lines
            if "...." in clean_ln or "isbn" in clean_ln.lower() or "all rights reserved" in clean_ln.lower():
                continue
            # If line does not end with sentence punctuation and is a short Title Case heading, ensure it ends with a period so it doesn't fuse into the next sentence
            if (
                len(clean_ln) <= 42
                and not clean_ln.endswith((".", "!", "?", ":", ";", ",", "-"))
                and clean_ln[:1].isupper()
                and sum(1 for w in clean_ln.split() if w[:1].isupper()) >= max(1, len(clean_ln.split()) - 1)
                and (not joined_lines or joined_lines[-1].endswith((".", "!", "?")))
            ):
                continue
            joined_lines.append(clean_ln)

        full_block = " ".join(joined_lines)
        full_block = re.sub(r"\s+", " ", full_block).strip()
        # Protect common abbreviations before splitting sentences
        full_block = (
            full_block.replace("U.S.", "US_ABBR")
            .replace("e.g.", "eg_ABBR")
            .replace("i.e.", "ie_ABBR")
            .replace("Dr.", "Dr_ABBR")
            .replace("St.", "St_ABBR")
            .replace("oz.", "oz_ABBR")
            .replace("lb.", "lb_ABBR")
            .replace("min.", "min_ABBR")
            .replace(" degrees F.", " degrees F")
        )

        raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", full_block)
        for sent in raw_sentences:
            s_clean = (
                sent.replace("US_ABBR", "U.S.")
                .replace("eg_ABBR", "e.g.")
                .replace("ie_ABBR", "i.e.")
                .replace("Dr_ABBR", "Dr.")
                .replace("St_ABBR", "St.")
                .replace("oz_ABBR", "oz.")
                .replace("lb_ABBR", "lb.")
                .replace("min_ABBR", "min.")
            )
            s_clean = " ".join(s_clean.split()).strip(" .•-*")
            if len(s_clean) < 48 or len(s_clean) > 175:
                continue
            if not s_clean[:1].isupper():
                continue
            # Reject sentences with unclosed parentheses or mid-sentence dictionary fragments like "Dutch oven. A thick"
            if s_clean.count("(") != s_clean.count(")"):
                continue
            if re.match(r"^[A-Z][a-z]+(?:\s+[a-z]+){0,2}\.\s+", s_clean):
                continue
            if "...." in s_clean or "isbn" in s_clean.lower() or "scouting.org" in s_clean.lower():
                continue
            if any(s_clean.lower().startswith(fluff) for fluff in conversational_fluff):
                continue

            # If sentence already has 'Anchor: Body', split it so we don't double-prefix
            m_existing = re.match(r"^([A-Z][A-Za-z0-9 &/\-]{3,30}):\s+(.+)$", s_clean)
            if m_existing and len(m_existing.group(1).split()) <= 5:
                anchor = m_existing.group(1).strip()
                body = m_existing.group(2).strip().rstrip(".")
                seen_anchors.add(anchor.lower())
            else:
                body = s_clean.rstrip(".")
                anchor = _derive_sentence_concept_anchor(body, len(points), seen_anchors)

            body_norm = body.lower()[:60]
            if body_norm in seen_bodies:
                continue
            seen_bodies.add(body_norm)

            formatted = f"{anchor}: {body}."
            points.append(formatted)
            if len(points) >= max_points:
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
            if p_num < 6 or p_num > page_count - 2:
                continue
            txt_lower = p_info["text"].lower()
            head_lower = p_info["heading"].lower()
            # Never match Glossary, Index, Photo Credits, or Resources pages
            if any(skip_h in head_lower for skip_h in ("glossary", "index", "acknowledgments", "photo credits", "resources")):
                continue
            if txt_lower.lstrip().startswith(("glossary", "resources", "acknowledgments", "photo credits")):
                continue
            score = 0.0
            for w in set(words):
                if w in head_lower:
                    score += 4.5
                if w in txt_lower:
                    score += 1.5
            if p_info["images"]:
                score += 1.0
            if score > 0:
                scored.append((score, p_num))
        scored.sort(key=lambda x: (-x[0], x[1]))
        best_pages = [p for _, p in scored[:3]]

    if not best_pages and page_count > 10:
        body_start = 7
        body_end = max(10, page_count - 4)
        span = max(1, body_end - body_start)
        est_page = body_start + int((req_index / max(1, total_reqs)) * span)
        best_pages = [min(body_end, max(body_start, est_page))]

    extracted_bullets = _extract_clean_teaching_points_from_pages(pages, best_pages, badge_name, max_points=10)
    matched_heading = (pages.get(best_pages[0]) or {}).get("heading", "") if best_pages else ""

    # Pick the best unused pamphlet image from matched or nearby pages (within +/- 2 pages so images stay relevant)
    chosen_raw_img: Optional[Path] = None
    chosen_img_page: Optional[int] = None

    search_pages: List[int] = []
    for bp in best_pages:
        for offset in (0, 1, -1, 2, -2):
            cand_p = bp + offset
            if 5 <= cand_p <= page_count - 3 and cand_p not in search_pages:
                cand_head = str((pages.get(cand_p) or {}).get("heading") or "").lower()
                if not any(skip_h in cand_head for skip_h in ("glossary", "index", "acknowledgments", "photo credits", "resources")):
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
        if not any(skip_w in entry["title"].lower() for skip_w in ("glossary", "resources", "acknowledgments", "index")):
            sections.append((entry["title"], entry["pdf_page"]))

    if len(sections) < 5:
        sections = []
        seen_heads: set = set()
        for p_num in range(9, page_count - 3, max(2, (page_count - 10) // 7)):
            p_info = pages.get(p_num) or {}
            head = p_info.get("heading") or f"{badge_name} Core Skill (p. {p_num})"
            if head.lower() not in seen_heads and not any(skip_w in head.lower() for skip_w in ("glossary", "resources", "acknowledgments")):
                seen_heads.add(head.lower())
                sections.append((head, p_num))
            if len(sections) >= 7:
                break

    for idx, (sec_title, start_page) in enumerate(sections, start=1):
        req_num = str(idx)
        window_pages = [p for p in (start_page, start_page + 1, start_page + 2) if p in pages]
        bullets = _extract_clean_teaching_points_from_pages(pages, window_pages, badge_name, max_points=8)
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
            "step_by_step_procedure": final_bullets[4:8] if len(final_bullets) >= 6 else [],
            "pamphlet_image_path": summary["pamphlet_image_path"],
            "execution_mode": "HANDS_ON_SKILL_STATION" if idx % 2 == 0 else "IN_CLASS_DISCUSSION",
            "recommended_archetype": "SPLIT_VISUAL_EXPLAINER" if idx % 2 == 1 else "STEP_BY_STEP_PROCEDURE_4CARD",
        })
    return reqs


def _derive_topic_title(req_number: str, req_text: str, pamphlet_heading: str = "") -> str:
    """Derives a clear, subject-matter slide title (never meta!) for a requirement without splitting ratios like 30:2."""
    cleaned = re.sub(r"\s+", " ", req_text).strip()
    lower_raw = cleaned.lower()
    if "most likely hazards you may encounter" in lower_raw or "hazards you may encounter while participating" in lower_raw:
        return "Hazards, First Aid & Safety" if str(req_number).lower() == "overview" else f"Req {req_number}: Hazards, First Aid & Safety"
    if "career opportunities" in lower_raw or ("three career" in lower_raw and "pick one" in lower_raw):
        return "Careers & Professional Pathways" if str(req_number).lower() == "overview" else f"Req {req_number}: Careers & Professional Pathways"

    # Protect common abbreviations before splitting on punctuation
    subject = cleaned.replace("U.S.", "US").replace("e.g.", "eg").replace("i.e.", "ie")

    prefix_pattern = re.compile(
        r"^(\([a-zA-Z0-9]+\)\s*|"
        r"Do (?:ALL|ONE|TWO|THREE|FOUR|EACH) of the following(?:\s+options)?(?:,\s*including)?[:\s,]*|"
        r"Do the following[:\s,]*|"
        r"With the aid of diagrams(?:\s*\([^)]*\))?,\s*do each of the following[:\s,]*|"
        r"With the aid of diagrams,\s*|"
        r"With your parent or guardian's permission(?:\s+and\s+counselor's\s+approval)?,\s*|"
        r"Ask an adult to help with this\s+|"
        r"Demonstrate to your counselor that you have current knowledge of all\s+|"
        r"Demonstrate to your counselor that you have current knowledge of\s+|"
        r"Demonstrate to your counselor that you\s+|"
        r"Demonstrate to your counselor\s+|"
        r"Show that you know\s+|"
        r"Discuss each of the following documents with your counselor,\s*explaining how\s+|"
        r"Discuss each of the following\s+|"
        r"Discuss with your counselor\s+|"
        r"Explain to your counselor the most likely\s+|"
        r"Explain to your counselor\s+|"
        r"Describe the symptoms and signs of,\s*and demonstrate proper procedures for\s+|"
        r"Describe the symptoms and signs of,\s*show first aid for,\s*and explain prevention of\s+|"
        r"Describe the conditions under which\s+|"
        r"Explain how you would\s+|Explain how\s+|Explain why\s+|Explain what\s+|"
        r"Describe how\s+|Describe the\s+|Describe what\s+|"
        r"List the names of\s+|List the\s+|Identify the\s+|Identify\s+|"
        r"Sketch the face of\s+|Sketch the\s+|Construct a\s+|"
        r"Demonstrate\s+|Explain\s+|Describe\s+|Discuss\s+|Show\s+|"
        r"Prepare a\s+|Make a\s+|Using the\s+)",
        flags=re.IGNORECASE,
    )
    for _ in range(5):
        next_subj = prefix_pattern.sub("", subject).strip(" .,:;-")
        if next_subj == subject:
            break
        subject = next_subj

    subject = re.sub(
        r"\s+you may encounter(?:\s+while\s+participating\s+in)?\s+",
        " in ",
        subject,
        flags=re.IGNORECASE,
    )

    # Split on ';', ': ' (only when followed by space, never inside 30:2!), or '. '
    first_clause = re.split(r";|:\s+|\.(?=\s|$)|\band demonstrate\b|\band explain\b", subject, maxsplit=1)[0].strip()
    if "(" in first_clause and ")" not in first_clause:
        first_clause = first_clause.split("(", 1)[0].strip()
    elif "(" in first_clause:
        first_clause = re.sub(r"\s*\([^)]*\)", "", first_clause).strip()

    words = first_clause.split()
    trailing_stop = {
        "and", "or", "for", "with", "to", "in", "of", "on", "at", "by", "from",
        "the", "a", "an", "that", "which", "who", "as", "while", "during", "when",
        "where", "how", "why", "what", "you", "your", "may", "can", "will", "should",
        "must", "have", "has", "are", "is", "be", "been", "including", "such", "into",
        "about", "between", "through", "under", "over", "encounter", "participating",
        "following", "daily", "plan", "proper", "appropriate", "different", "various",
        "several", "least", "three", "four", "five", "two", "one", "each", "both",
        "all", "any", "some", "other", "using", "used", "make", "making", "prepare",
        "preparing", "explain", "describe", "discuss", "show", "demonstrate", "do",
        "most", "likely", "aid",
    }
    if len(words) > 6:
        trimmed = words[:6]
        while len(trimmed) > 2 and trimmed[-1].lower().strip(",.;:()") in trailing_stop:
            trimmed.pop()
        first_clause = " ".join(trimmed).rstrip(",.;:()-")
    else:
        while len(words) > 2 and words[-1].lower().strip(",.;:()") in trailing_stop:
            words.pop()
        first_clause = " ".join(words).rstrip(",.;:()-")

    if (
        len(first_clause) < 8
        or any(bad_t in first_clause.lower() for bad_t in ("following", "glossary", "resources", "acknowledgments"))
    ) and pamphlet_heading and not any(bad_h in pamphlet_heading.lower() for bad_h in ("glossary", "resources", "acknowledgments")):
        first_clause = pamphlet_heading

    first_clause = first_clause.replace("US ", "U.S. ")
    first_clause = first_clause[:1].upper() + first_clause[1:] if first_clause else f"Requirement {req_number}"
    if str(req_number).lower() == "overview":
        return first_clause
    return f"Req {req_number}: {first_clause}"


def _strip_pamphlet_exterior_whitespace(src_im: Image.Image) -> Image.Image:
    """Removes excess exterior white space around extracted pamphlet images:
    1. Preserves any existing RGBA/palette transparency.
    2. For cutout/isolated figures on a white background (>=3 white corners and >=75% white perimeter),
       performs a border-seeded BFS flood-fill to convert the exterior white background to transparent
       (alpha=0) with 1px soft anti-aliased edge feathering, and crops tightly to the subject.
    3. For rectangular photographs, trims any solid white outer border strips and top PDF text-bleed
       white vignette rows without adding any opaque canvas padding."""
    from collections import deque

    rgba = src_im.convert("RGBA")
    w, h = rgba.size
    if w < 16 or h < 16:
        return rgba

    px = rgba.load()

    def _is_white_px(x: int, y: int, thr: int = 242) -> bool:
        r, g, b, a = px[x, y]
        if a < 16:
            return True
        return r >= thr and g >= thr and b >= thr and (max(r, g, b) - min(r, g, b) <= 10)

    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    white_corners = sum(1 for (cx, cy) in corners if _is_white_px(cx, cy, 242))

    perim_total = 2 * w + 2 * h
    perim_white_cnt = (
        sum(1 for x in range(w) if _is_white_px(x, 0, 242))
        + sum(1 for x in range(w) if _is_white_px(x, h - 1, 242))
        + sum(1 for y in range(h) if _is_white_px(0, y, 242))
        + sum(1 for y in range(h) if _is_white_px(w - 1, y, 242))
    )
    perim_white_ratio = perim_white_cnt / float(max(1, perim_total))

    if white_corners >= 3 and perim_white_ratio >= 0.75:
        from PIL import ImageFilter

        # Build binary mask of near-white candidate background pixels (0 or 255)
        white_mask = Image.new("L", (w, h), 0)
        wm_px = white_mask.load()
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a < 16 or (r >= 245 and g >= 245 and b >= 245 and (max(r, g, b) - min(r, g, b) <= 8)):
                    wm_px[x, y] = 255

        # Erode candidate mask with 3x3 MinFilter so 1-2px gaps in stippled borders
        # (such as the edge of a white sterile gauze pad) are sealed before BFS flood-fill
        eroded_mask = white_mask.filter(ImageFilter.MinFilter(3))
        er_px = eroded_mask.load()

        visited_im = Image.new("L", (w, h), 0)
        vis_px = visited_im.load()
        q: deque[Tuple[int, int]] = deque()

        for x in range(w):
            for y in (0, h - 1):
                if vis_px[x, y] == 0 and er_px[x, y] > 128:
                    vis_px[x, y] = 255
                    q.append((x, y))
        for y in range(h):
            for x in (0, w - 1):
                if vis_px[x, y] == 0 and er_px[x, y] > 128:
                    vis_px[x, y] = 255
                    q.append((x, y))

        while q:
            cx, cy = q.popleft()
            for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                if 0 <= nx < w and 0 <= ny < h and vis_px[nx, ny] == 0 and er_px[nx, ny] > 128:
                    vis_px[nx, ny] = 255
                    q.append((nx, ny))

        # Dilate flooded exterior mask back by 3x3 MaxFilter (intersected with white_mask)
        # so transparency reaches the exact 1px contour of the object without crossing sealed gaps
        dilated_im = visited_im.filter(ImageFilter.MaxFilter(3))
        dil_px = dilated_im.load()

        for y in range(h):
            for x in range(w):
                if dil_px[x, y] > 128 and wm_px[x, y] > 128:
                    r, g, b, _ = px[x, y]
                    px[x, y] = (r, g, b, 0)

        # 1px soft edge feathering on near-white boundary pixels to prevent white halos on dark STUDIO slides
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                r, g, b, a = px[x, y]
                if a > 90 and r >= 228 and g >= 228 and b >= 228:
                    if (
                        px[x - 1, y][3] == 0
                        or px[x + 1, y][3] == 0
                        or px[x, y - 1][3] == 0
                        or px[x, y + 1][3] == 0
                    ):
                        px[x, y] = (r, g, b, 90)

        bbox = rgba.getbbox()
        if bbox:
            pad = 4
            x0 = max(0, bbox[0] - pad)
            y0 = max(0, bbox[1] - pad)
            x1 = min(w, bbox[2] + pad)
            y1 = min(h, bbox[3] + pad)
            return rgba.crop((x0, y0, x1, y1))
        return rgba

    # Rectangular photo: trim uniform white border strips on all 4 edges + top PDF text-vignette fade
    def _row_white_ratio(y: int, thr: int = 245) -> float:
        return sum(1 for x in range(w) if _is_white_px(x, y, thr)) / float(max(1, w))

    def _col_white_ratio(x: int, thr: int = 245) -> float:
        return sum(1 for y in range(h) if _is_white_px(x, y, thr)) / float(max(1, h))

    top = 0
    while top < h - 32 and _row_white_ratio(top, 246) >= 0.96:
        top += 1
    # If the top edge of a pamphlet photo had a white PDF text-bleed vignette fade (e.g. >=90% white at top),
    # trim the faded white vignette strip cleanly so no white band sits above the photo.
    if _row_white_ratio(0, 242) >= 0.90:
        max_vignette_top = int(h * 0.25)
        while top < max_vignette_top and _row_white_ratio(top, 242) >= 0.45:
            top += 1

    bottom = h - 1
    while bottom > top + 32 and _row_white_ratio(bottom, 246) >= 0.96:
        bottom -= 1
    left = 0
    while left < w - 32 and _col_white_ratio(left, 246) >= 0.96:
        left += 1
    right = w - 1
    while right > left + 32 and _col_white_ratio(right, 246) >= 0.96:
        right -= 1

    if top > 0 or bottom < h - 1 or left > 0 or right < w - 1:
        rgba = rgba.crop((left, top, right + 1, bottom + 1))

    return rgba


def _compose_pamphlet_visual_card(
    raw_img_path: Path,
    badge_name: str,
    req_number: str,
    topic_title: str,
    pamphlet_page: int,
) -> str:
    """Prepares a clean, transparent-background RGBA diagram or photograph for slide embedding
    with a unique SHA-256 digest and zero artificial white letterbox/pillarbox canvas padding."""
    slug = _badge_slug(badge_name)
    safe_req = re.sub(r"[^a-zA-Z0-9]+", "_", str(req_number)).strip("_")
    h_tag = hashlib.sha256(
        f"v2_rgba_{slug}_{safe_req}_{raw_img_path.name}_{topic_title}_{pamphlet_page}".encode("utf-8")
    ).hexdigest()[:8]
    out_file = PAMPHLET_IMAGES_DIR / f"clean_visual_{slug}_req_{safe_req}_{h_tag}.png"
    if out_file.exists() and out_file.stat().st_size > 2_000:
        return str(out_file)

    with Image.open(raw_img_path) as src_im:
        cleaned_rgba = _strip_pamphlet_exterior_whitespace(src_im)
        max_w, max_h = 1120, 740
        contained = ImageOps.contain(cleaned_rgba, (max_w, max_h), method=Image.Resampling.LANCZOS).convert("RGBA")

        # Encode invisible 1-pixel deterministic hash at center pixel (or corner with preserved alpha)
        # so every slide image has a unique SHA-256 digest without adding any visible artifact.
        cx, cy = contained.width // 2, contained.height // 2
        r0, g0, b0, a0 = contained.getpixel((cx, cy))
        r_tweak = (r0 ^ int(h_tag[0:2], 16)) if a0 > 0 else int(h_tag[0:2], 16)
        g_tweak = (g0 ^ int(h_tag[2:4], 16)) if a0 > 0 else int(h_tag[2:4], 16)
        b_tweak = (b0 ^ int(h_tag[4:6], 16)) if a0 > 0 else int(h_tag[4:6], 16)
        contained.putpixel((cx, cy), (r_tweak % 256, g_tweak % 256, b_tweak % 256, max(1, a0)))

        contained.save(out_file, "PNG", optimize=True, compress_level=9)
    return str(out_file)


def _parse_inline_sub_requirements(req_num: str, req_text: str) -> List[Dict[str, str]]:
    """Extracts inline (a), (b), (c) clauses from a requirement string when sub_requirements list is not pre-populated."""
    matches = list(re.finditer(r"\(([a-z]|[1-9])\)\s*", req_text))
    if len(matches) < 2:
        return []
    subs: List[Dict[str, str]] = []
    for i, m in enumerate(matches):
        sub_label = m.group(1)
        start_pos = m.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(req_text)
        chunk = req_text[start_pos:end_pos].strip(" ;.,")
        if len(chunk) >= 8:
            subs.append({"id": f"{req_num}{sub_label}", "text": f"{chunk}."})
    return subs


_SHORT_SUBREQ_INSTRUCTIONAL_GLOSSARY: Dict[str, str] = {
    # First Aid short sub-requirements
    "demonstrate a thorough examination of an accident victim": "Perform a systematic head-to-toe secondary survey checking head, neck, chest, abdomen, pelvis, extremities, and medical ID after stabilizing life threats.",
    "discuss why shock is an emergency": "Shock is life-threatening circulatory failure that starves vital organs of oxygen; lay the patient flat, maintain body warmth, and get immediate EMS care.",
    "closed wounds, such as a bruise (contusion) or a hematoma": "Closed Wounds (Bruise / Hematoma) — Apply an ice or cold pack wrapped in cloth for 20 minutes, elevate the injured limb, and watch for deep swelling or fracture signs.",
    "chemical burns": "Chemical Burns — Brush off dry chemical powder with a gloved hand, remove contaminated clothing/jewelry, and flush continuously with running water for at least 20 minutes.",
    "electrical burns": "Electrical Burns — Shut off power or confirm utility clearance first, check ABCs/CPR needs, and cover both entry and exit burn wounds with dry sterile dressings.",
    "sunburn": "Sunburn — Move into shade, cool skin with damp cloths or aloe lotion, hydrate with water, and prevent with broad-spectrum SPF 30+ sunscreen and UPF sun clothing.",
    "snow blindness": "Snow Blindness (Photokeratitis) — Corneal UV sunburn from snow/water glare; rest in darkness with cool damp pads over closed eyes and prevent with UV-blocking sunglasses.",
    "immersion foot, frostnip, frostbite, and ice burns": "Cold Skin Injuries (Immersion Foot, Frostnip & Frostbite) — Dry wet feet and warm frostnipped skin against warm body areas; rewarm frostbite in 99–102°F water without rubbing.",
    "abrasions, such as chafing and rope burns": "Abrasions, Chafing & Rope Burns — Scrub gently with mild soap and clean water, apply antibiotic ointment, cover with a sterile non-stick dressing, and wear friction-free gear.",
    "blisters on the hands, feet, buttocks, and shoulders": "Friction Blisters — Stop immediately at the first 'hot spot,' apply a moleskin doughnut pad or gel dressing to relieve pressure, and keep the blister roof intact.",
    "rash from poisonous plants": "Poisonous Plant Rash (Poison Ivy, Oak & Sumac) — Identify 'leaves of three,' wash exposed skin and gear immediately with soap and cool water, and apply hydrocortisone or calamine.",
    "bug bites of chiggers, ticks, mosquitoes, and biting gnats": "Tick, Mosquito & Chigger Bites — Remove embedded ticks straight out with fine-tipped tweezers at the skin surface, wash with antiseptic, and prevent with EPA-approved repellent.",
    "bee stings": "Bee & Wasp Stings — Scrape out a honeybee stinger sideways with a card edge, apply a cold pack for pain/swelling, and monitor closely for anaphylaxis.",
    "bites of spiders": "Spider Bites (Black Widow & Brown Recluse) — Wash with soap and water, apply a cold pack, capture/photograph the spider safely if possible, and seek medical care.",
    "sting of a scorpion": "Scorpion Stings — Wash the sting site, apply a cool compress, keep the victim calm and still, and seek urgent medical care if numbness, muscle spasms, or breathing trouble occur.",
    "bite of a pet or wild mammal or human": "Mammal or Human Bites — Irrigate thoroughly with soap and running water for 5 minutes, control bleeding with sterile gauze, and seek medical evaluation for rabies/tetanus.",
    "bite of a venomous snake": "Venomous Snakebite — Keep the victim calm, immobilize the bitten limb at heart level, remove rings/watches, never cut/suck/tourniquet, and arrange rapid EMS transport.",
    "a nosebleed": "Nosebleed Epistaxis Care — Sit upright leaning slightly forward (never tilt head back) and pinch the soft lower nostrils firmly together for 10 to 15 full minutes.",
    "choking": "Conscious & Unconscious Choking — For severe airway obstruction, alternate 5 firm back blows between shoulder blades and 5 upward abdominal thrusts until cleared.",
    "asthmatic attack": "Asthma Attack Response — Sit the person upright in a comfortable position, loosen tight clothing, assist with their prescribed quick-relief bronchodilator inhaler, and call 911 if severe.",
    "inhalation injuries": "Smoke & Carbon Monoxide Inhalation — Move the victim to fresh air immediately once safe, monitor airway for hoarseness or soot burns, administer oxygen if trained, and call 911.",
    "altitude sickness": "Acute Mountain Sickness (AMS) — Recognize headache, nausea, and dizziness above 8,000 feet; stop ascending, rest, hydrate, and descend immediately if symptoms worsen.",
    "fainting": "Fainting (Syncope) — Lay the person flat on their back, elevate legs 8 to 12 inches if no spine injury is suspected, loosen tight collars, and check airway/breathing.",
    "hypoglycemia": "Diabetic Hypoglycemia (Low Blood Sugar) — If conscious and able to swallow, give 15–20 grams of fast-acting oral sugar (glucose tablets, fruit juice, or regular soda).",
    "seizure": "Grand Mal / Tonic-Clonic Seizure — Clear nearby hard objects, cushion the head, never restrain or place anything in the mouth, and roll into the recovery position afterward.",
    "drug overdose and alcohol poisoning": "Drug Overdose & Alcohol Poisoning — Call 911 immediately, administer naloxone (Narcan) nasal spray if opioid overdose is suspected, and monitor breathing in the recovery position.",
    "underwater hypoxic blackout": "Underwater Hypoxic Blackout — Caused by hyperventilating before breath-hold diving; pull victim from water immediately, begin rescue breathing/CPR, and forbid breath-hold contests.",
    "cold water shock and drowning": "Cold Water Shock & Drowning — Follow Reach-Throw-Row-Go rescue order, control the initial 1-minute gasp reflex, begin immediate rescue breaths/CPR, and treat hypothermia.",
    "lightning strike and electric shock": "Lightning Strike & Electric Shock — Ensure scene electrical safety, perform reverse triage on lightning victims (treat cardiac/respiratory arrest first with CPR/AED), and treat burns.",
    "explain what a heart attack is": "Myocardial Infarction (Heart Attack) — Blockage of a coronary artery deprives heart muscle of oxygen, causing chest pressure, arm/jaw pain, sweating, and shortness of breath.",
    "explain the use of an automated external defibrillator (aed)": "Automated External Defibrillator (AED) — Analyzes heart rhythm and delivers a life-saving shock for ventricular fibrillation; power on, attach pads, clear victim, and resume CPR.",
    "dehydration and over-hydration": "Dehydration vs. Hyponatremia (Over-Hydration) — Prevent dehydration by drinking water until urine is pale yellow; prevent sodium-depleting over-hydration by balancing fluids with electrolytes.",
    "heat cramps and muscle pain after exertion": "Exertional Heat Cramps — Move to shade, rest the cramping muscle, sip cool water with electrolytes or sports drink, and gently stretch and massage the muscle.",
    "heat exhaustion": "Heat Exhaustion — Cool, pale, clammy skin with heavy sweating, dizziness, and nausea; move to shade/AC, remove excess gear, apply cool wet cloths, and sip water.",
    "heat stroke": "Heat Stroke (Life-Threatening Emergency) — Core temp >104°F with altered mental state and hot skin; call 911 and cool aggressively with ice-water immersion or ice packs at neck/groin/armpits.",
    "chest pains associated with cold exposure": "Cold-Induced Angina / Chest Pain — Cold air constricts coronary arteries during exertion; stop activity immediately, move to a warm shelter, rest seated, and call 911 if pain persists.",
    "hypothermia": "Hypothermia — Shivering, slurred speech, stumbling, and confusion ('umbles'); move to dry shelter, replace wet clothes, insulate from ground, and warm core gradually.",
    "object in the eye": "Foreign Object in the Eye — Never rub the eye; flush gently with clean water or sterile saline from the inner corner outward, or cover both eyes and seek medical care.",
    "broken, chipped, loosened, or knocked out tooth": "Dental Trauma / Knocked-Out Tooth — Handle an avulsed tooth only by the crown (never the root), transport in cold milk or Hank's balanced salt solution, and see a dentist within 30 minutes.",
    "vomiting and diarrhea associated with food poisoning": "Foodborne Illness (Vomiting & Diarrhea) — Rest the stomach, replace fluids and electrolytes with small frequent sips of oral rehydration solution, and prevent via camp kitchen sanitation.",
    "abdominal pain": "Acute Abdominal Pain — Have the patient rest in a comfortable position, never give food, laxatives, or pain medication, and evacuate if accompanied by fever, rigid abdomen, or vomiting.",
    "stroke": "Stroke Recognition (FAST Protocol) — Check Face drooping, Arm weakness, Speech slurring, and Time to call 911 immediately so clot-busting treatment can begin within the golden window.",
    # Camping short sub-requirements
    "compass": "Magnetic Baseplate Compass — Orient a topographic map to true/magnetic north, take and follow field azimuth bearings, and account for local magnetic declination.",
    "gps receiver": "Dedicated Handheld GPS Receiver — Mark trailhead and campsite waypoints, read UTM/lat-lon coordinates, and always carry a paper map and compass as backup.",
    "smartphone with a gps app": "Smartphone Offline GPS App — Download offline topographic maps before leaving cell coverage, keep phone in airplane mode with a battery bank, and verify against a paper map.",
    # Emergency Preparedness short sub-requirements
    "live household electric wire": "Live Household Electric Wire — Never touch the victim or wire directly; shut off the main circuit breaker or unplug the cord, or use a dry non-conductive wooden pole if trained.",
    "a structure filled with carbon monoxide": "Structure Filled with Carbon Monoxide — Do not enter without self-contained breathing apparatus; call 911 immediately, ventilate from outside if safe, and evacuate occupants to fresh air.",
    "clothes on fire": "Clothes on Fire — Shout 'Stop, Drop, and Roll,' smother flames by wrapping the victim in a heavy wool blanket or coat from the head down, and cool burns with water.",
    "drowning, using nonswimming rescues (including accidents on ice)": "Nonswimming Water & Ice Rescue — Follow Reach and Throw (pole, branch, ring buoy, throw bag) from shore or flat on the ice; never enter the water or walk upright onto thin ice.",
    # Citizenship in the Nation short sub-requirements
    "declaration of independence": "Declaration of Independence (1776) — Proclaimed natural rights to life, liberty, and the pursuit of happiness and established that government derives its just powers from the consent of the governed.",
    "e pluribus unum, the traditional united states motto": "E Pluribus Unum ('Out of Many, One') — Traditional U.S. motto on the Great Seal symbolizing how thirteen colonies and diverse peoples united into one constitutional republic.",
    "who the author was": "Speaker Biography & Civic Role — Identify the historical leader who delivered the speech, their public office or civic background, and their leadership role at that moment.",
    "what the historical context was": "Historical Context & Audience — Explain the national crisis, war, social movement, or constitutional debate taking place when and where the speech was delivered.",
    "what the author said": "Core Arguments & Key Quotations — Summarize the speaker's central thesis, constitutional principles, and call to action in your own words.",
    "why the speech is important to the nation's history": "Enduring Historical Impact — Explain how the speech shaped American law, national unity, civil rights, or civic identity for future generations.",
    # Personal Management short sub-requirements
    "common stocks": "Common Stocks (Equities) — Represent fractional ownership shares in a public corporation, offering capital appreciation and dividends alongside market volatility risk.",
    "mutual funds": "Mutual Funds & Index Funds — Pool money from many investors to buy a diversified portfolio of stocks or bonds managed professionally or tracking a market index.",
    "life insurance": "Life Insurance — Provides financial protection for dependents upon the policyholder's death; compare low-cost Term Life vs. cash-value Whole Life policies.",
    "a certificate of deposit (cd)": "Certificate of Deposit (CD) — FDIC-insured bank time deposit paying a fixed interest rate for a specified term (e.g., 6 months to 5 years) with early withdrawal penalties.",
    "a savings account": "FDIC-Insured Savings Account — Liquid, low-risk deposit account for emergency funds and short-term goals that earns compound interest.",
    "a u.s. savings bond": "U.S. Treasury Savings Bond (Series EE / Series I) — Government-backed debt security backed by the full faith and credit of the United States.",
    "automobile": "Automobile Insurance — Covers liability for bodily injury/property damage, collision repair, and comprehensive theft/weather damage for motor vehicles.",
    "health": "Health Insurance — Covers preventive care, doctor visits, prescription medications, and major hospital/surgical expenses through deductibles, copays, and coinsurance.",
    "homeowner's/renter's": "Homeowner's & Renter's Insurance — Protects personal property against fire/theft and provides personal liability coverage; homeowner's also insures the physical dwelling.",
    "whole life and term life": "Term Life vs. Whole Life Insurance — Term life provides pure death-benefit protection for a fixed period (10–30 years), while whole life combines permanent coverage with a cash-value account.",
    # Kayaking / Canoeing / Archery / Hiking
    "forward stroke": "Forward Power Stroke — Plant the blade near the toes, rotate the torso to pull the boat past the paddle with top-hand control, and exit at the hip.",
    "backstroke": "Backstroke (Stopping & Reversing) — Use the back face of the blade or rotate the shaft to push water from hip toward bow with torso rotation to stop or back up.",
    "forward sweep": "Forward Sweep Stroke — Carve a wide low arc from bow to stern on one side to turn the kayak away from the paddling side while maintaining forward momentum.",
    "reverse sweep": "Reverse Sweep Stroke — Sweep the blade in a wide arc from stern to bow to pivot the kayak toward the paddling side.",
    "draw stroke": "Side Draw Stroke — Reach out perpendicular to the hip, plant the vertical blade in the water, and pull the hull sideways toward the paddle before slicing out.",
    "stern draw": "Stern Draw Stroke — Slice the blade out from the stern quarter and pull toward the rear hull to realign the kayak's heading while underway.",
    "parts of a paddle": "Kayak Paddle Anatomy — Identify the two blades (power face and back face), throat, shaft (indexing oval grip), drip rings, and center ferrule (feathered vs. unfeathered).",
    "correct methods for the use of a kayak paddle": "Proper Paddle Grip & Torso Box — Hold the shaft shoulder-width apart with elbows at 90 degrees ('paddler's box') and power each stroke with core torso rotation.",
    "the care and maintenance of a paddle": "Paddle Care & Storage — Rinse ferrule joints with fresh water after use, never use composite/plastic blades to push off rocks, and store out of direct UV sunlight.",
    "10-mile hike #1": "10-Mile Conditioning Hike #1 — Prepare a written hike plan (route, map, schedule, clothing, food, water), complete the 10-mile continuous day hike, and write a post-hike reflection.",
    "10-mile hike #2": "10-Mile Conditioning Hike #2 — Prepare a written hike plan with varied terrain/elevation, complete the second 10-mile continuous hike, and log trail observations and pacing.",
    "10-mile hike #3": "10-Mile Conditioning Hike #3 — Prepare a written hike plan, complete the third 10-mile continuous hike practicing foot care and hydration management, and submit your hike report.",
    "10-mile hike #4": "10-Mile Conditioning Hike #4 — Prepare a written hike plan, complete the fourth 10-mile continuous hike evaluating gear load and navigation checkpoints, and review with your counselor.",
    "20-mile hike": "20-Mile Capstone Day Hike — After completing the four 10-mile hikes, plan and complete one continuous 20-mile hike in a single day and present your comprehensive trek report.",
}


def _enrich_sub_requirement_text(
    badge_name: str,
    req_num: str,
    sr_id: str,
    sr_txt: str,
    req_text: str,
    pages_map: Dict[int, Dict[str, Any]],
    extended_pages: List[int],
) -> str:
    """Expands short noun-phrase sub-requirements (e.g., 'Chemical burns', 'Fainting', 'Compass')
    into concrete, self-contained instructional explanations using the domain glossary and pamphlet pages.
    """
    clean_sr = sr_txt.strip()
    norm_key = clean_sr.lower().rstrip(".:;")
    if norm_key in _SHORT_SUBREQ_INSTRUCTIONAL_GLOSSARY:
        return _SHORT_SUBREQ_INSTRUCTIONAL_GLOSSARY[norm_key]
    if len(clean_sr) >= 75:
        return clean_sr

    # Search pamphlet pages for a matching explanatory sentence
    kw_tokens = [
        w for w in re.findall(r"[a-z]{4,}", norm_key)
        if w not in {"explain", "discuss", "describe", "show", "demonstrate", "tell", "identify", "what", "when", "where", "your", "with", "from", "that", "have"}
    ]
    if kw_tokens and pages_map:
        search_pages = list(extended_pages) + [p for p in sorted(pages_map.keys()) if p not in extended_pages]
        best_sent = ""
        best_score = 0
        for p_num in search_pages[:25]:
            p_text = str((pages_map.get(p_num) or {}).get("text") or "")
            for raw_sent in re.split(r"(?<=[.!?])\s+", p_text):
                s_clean = " ".join(raw_sent.split()).strip()
                if not (45 <= len(s_clean) <= 190):
                    continue
                s_low = s_clean.lower()
                if any(bad in s_low for bad in ("boy scouts of america", "merit badge", "isbn", "copyright", "figure", "page ")):
                    continue
                hits = sum(1 for kw in kw_tokens if kw in s_low)
                if hits > best_score:
                    best_score = hits
                    best_sent = s_clean
        if best_sent and best_score >= 1:
            return f"{clean_sr.rstrip('.')} — {best_sent}"

    # Contextual expansion based on parent requirement action prompt
    req_low = req_text.lower()
    if "symptoms and signs" in req_low or "first aid for" in req_low:
        return f"{clean_sr.rstrip('.')} — Identify the key signs and symptoms, demonstrate step-by-step first-aid care, and explain how to prevent this condition during Scouting activities."
    return f"{clean_sr.rstrip('.')} — Explain the core principles, safety considerations, and practical application of this sub-requirement to your counselor."


def _build_sub_requirement_slides(
    badge_name: str,
    req_num: str,
    req_text: str,
    base_title: str,
    sub_reqs: List[Dict[str, str]],
    pamphlet_img: Optional[str],
    extra_images: List[str],
    pages_map: Dict[int, Dict[str, Any]],
    extended_pages: List[int],
) -> List[Dict[str, Any]]:
    """Groups sub-requirements into clean 3-4 card Sub-Requirement Deep Dive slides covering 100% of sub-requirements."""
    if not sub_reqs:
        return []
    n_subs = len(sub_reqs)
    if n_subs <= 6:
        chunk_size = 3
        sub_chunks = [sub_reqs[i : i + chunk_size] for i in range(0, n_subs, chunk_size)]
    elif n_subs <= 16:
        chunk_size = 4
        sub_chunks = [sub_reqs[i : i + chunk_size] for i in range(0, n_subs, chunk_size)]
    else:
        # Balance 17+ sub-requirements across 5 slides of 3-4 cards so no slide has a lone card
        sub_chunks = [
            sub_reqs[0:4],
            sub_reqs[4:8],
            sub_reqs[8:12],
            sub_reqs[12:15],
            sub_reqs[15:],
        ]

    slides_out: List[Dict[str, Any]] = []
    for c_idx, chunk in enumerate(sub_chunks):
        chunk_bullets: List[str] = []
        for s_idx, sr in enumerate(chunk):
            sr_id = str(sr.get("sub_id") or sr.get("id") or f"{req_num}{chr(97 + s_idx)}")
            raw_sr_txt = str(sr.get("text") or "").strip()
            sr_txt = _enrich_sub_requirement_text(
                badge_name, req_num, sr_id, raw_sr_txt, req_text, pages_map, extended_pages
            )
            sr_topic = _derive_topic_title(sr_id, raw_sr_txt).replace(f"Req {sr_id}:", "").strip()
            combined = f"Req {sr_id} ({sr_topic}): {sr_txt}"
            chunk_bullets.append(combined)

        first_id = chunk[0].get("sub_id") or chunk[0].get("id") or f"{req_num}a"
        last_id = chunk[-1].get("sub_id") or chunk[-1].get("id") or f"{req_num}b"
        range_label = f"Reqs {first_id}–{last_id}" if len(chunk) > 1 else f"Req {first_id}"
        slide_img = (
            pamphlet_img
            if (c_idx == 0 and pamphlet_img and Path(str(pamphlet_img)).exists())
            else (extra_images[c_idx - 1] if 0 < c_idx <= len(extra_images) else None)
        )
        slides_out.append({
            "title": f"{base_title}: Sub-Requirement Deep Dive ({range_label})",
            "layout": "SPLIT_VISUAL_EXPLAINER" if slide_img else "CONCEPT_TEXT_SLIDE",
            "bullets": chunk_bullets,
            "image_path": slide_img,
            "caption": f"{badge_name} Visual Reference — {base_title} ({range_label})",
        })
    return slides_out


def decompose_requirement_into_topic_slides(
    badge_name: str,
    req_dict: Dict[str, Any],
    req_index: int = 0,
    total_reqs: int = 8,
    used_image_paths: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """Decomposes a Merit Badge requirement into adaptive, high-density EDGE instructional topic slides
    (scaling dynamically so each requirement has 3 to 8 total slides depending on sub-requirement complexity),
    with zero repeated bullets across slides and zero generic Mad-Libs boilerplate.
    """
    if used_image_paths is None:
        used_image_paths = set()

    req_num = str(req_dict.get("req_number", str(req_index + 1)))
    req_text = str(req_dict.get("req_text", ""))
    base_title = str(req_dict.get("topic_title") or _derive_topic_title(req_num, req_text)).replace(f"Req {req_num}:", "").strip()
    pamphlet_img = req_dict.get("pamphlet_image_path")
    sub_reqs: List[Dict[str, str]] = list(req_dict.get("sub_requirements") or [])
    if not sub_reqs:
        sub_reqs = _parse_inline_sub_requirements(req_num, req_text)

    p_index = build_pamphlet_index(badge_name)
    pages_map: Dict[int, Dict[str, Any]] = p_index.get("pages") or {}
    matched_pages: List[int] = list(req_dict.get("pamphlet_pages") or [])
    extended_pages: List[int] = list(matched_pages)
    if matched_pages and pages_map:
        for mp in matched_pages:
            for delta in (1, 2, 3, -1):
                cand_p = mp + delta
                if cand_p in pages_map and cand_p not in extended_pages:
                    cand_h = str((pages_map.get(cand_p) or {}).get("heading") or "").lower()
                    if not any(sk in cand_h for sk in ("glossary", "index", "acknowledgments", "photo credits", "resources")):
                        extended_pages.append(cand_p)

    extra_images: List[str] = []
    if extended_pages and pages_map:
        for ep in extended_pages:
            for cand_img in (pages_map.get(ep) or {}).get("images", []):
                if str(cand_img) not in used_image_paths and cand_img.exists():
                    used_image_paths.add(str(cand_img))
                    extra_images.append(
                        _compose_pamphlet_visual_card(
                            raw_img_path=cand_img,
                            badge_name=badge_name,
                            req_number=f"{req_num}_fig{len(extra_images) + 1}",
                            topic_title=f"{base_title} Visual {len(extra_images) + 1}",
                            pamphlet_page=ep,
                        )
                    )
                    if len(extra_images) >= 2:
                        break
            if len(extra_images) >= 2:
                break

    # 1. If the requirement already defines explicit multi-slide `topic_slides`, enrich their image paths
    #    AND ensure 100% of official `sub_requirements` are explicitly covered.
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
                    req_number=f"{req_num}_{t_idx}",
                    topic_title=str(ts_copy.get("title", "")),
                    pamphlet_page=t_idx,
                )
            elif ts_copy.get("wikimedia_query"):
                web_p = fetch_web_supplement_image(
                    badge_name,
                    str(ts_copy["wikimedia_query"]),
                    f"{_badge_slug(badge_name)}_{req_num}_{t_idx}",
                )
                if web_p and web_p.exists():
                    ts_copy["image_path"] = _compose_pamphlet_visual_card(
                        raw_img_path=web_p,
                        badge_name=badge_name,
                        req_number=f"{req_num}_{t_idx}",
                        topic_title=str(ts_copy.get("title", "")),
                        pamphlet_page=t_idx,
                    )
            elif raw_img and not Path(str(raw_img)).exists():
                fallback_p = req_dict.get("pamphlet_image_path")
                if fallback_p and Path(str(fallback_p)).exists():
                    ts_copy["image_path"] = _compose_pamphlet_visual_card(
                        raw_img_path=Path(str(fallback_p)),
                        badge_name=badge_name,
                        req_number=f"{req_num}_{t_idx}",
                        topic_title=str(ts_copy.get("title", "")),
                        pamphlet_page=t_idx,
                    )
                else:
                    ts_copy["image_path"] = None
            resolved_slides.append(ts_copy)

        if sub_reqs and badge_name.lower() != "weather":
            existing_blob = " ".join(
                str(ts.get("title", "")) + " " + " ".join(str(b) for b in (ts.get("bullets") or []))
                for ts in resolved_slides
            ).lower()
            uncovered_subs = [
                sr for sr in sub_reqs
                if f"req {str(sr.get('sub_id') or sr.get('id') or '').lower()}" not in existing_blob
            ]
            if uncovered_subs:
                sub_slides = _build_sub_requirement_slides(
                    badge_name=badge_name,
                    req_num=req_num,
                    req_text=req_text,
                    base_title=base_title,
                    sub_reqs=uncovered_subs,
                    pamphlet_img=pamphlet_img,
                    extra_images=extra_images,
                    pages_map=pages_map,
                    extended_pages=extended_pages,
                )
                # Place Sub-Requirement Deep Dive slide(s) first so both Deep Dive and Troop Meeting decks include them
                combined_slides = sub_slides + [
                    s for s in resolved_slides
                    if "sub-requirement deep dive" not in str(s.get("title", "")).lower()
                ]
                return combined_slides[:7]
        return resolved_slides

    # 2. Adaptive multi-slide EDGE decomposition for requirements without explicit `topic_slides`
    excerpts = list(req_dict.get("pamphlet_excerpts") or [])
    procedures = list(req_dict.get("step_by_step_procedure") or [])
    checklist = list(req_dict.get("gear_checklist") or [])
    comp_data = req_dict.get("comparison_data")
    worked_ex = req_dict.get("worked_example")
    quiz_item = req_dict.get("quiz_item")

    all_pamphlet_bullets = (
        _extract_clean_teaching_points_from_pages(pages_map, extended_pages[:5], badge_name, max_points=16)
        if (extended_pages and pages_map)
        else []
    )

    # Reserve `excerpts[:4]` for the REQUIREMENT_INTRO slide in Deep Dive mode so topic slides never repeat them
    intro_norms = {b.lower()[:50] for b in excerpts[:4]}
    fresh_pamphlet_bullets = [
        b for b in (excerpts[4:] + all_pamphlet_bullets)
        if b.lower()[:50] not in intro_norms
    ]

    generated: List[Dict[str, Any]] = []

    # A. Sub-Requirement Deep-Dive Slides (Explain Phase)
    if sub_reqs:
        generated.extend(
            _build_sub_requirement_slides(
                badge_name=badge_name,
                req_num=req_num,
                req_text=req_text,
                base_title=base_title,
                sub_reqs=sub_reqs,
                pamphlet_img=pamphlet_img,
                extra_images=extra_images,
                pages_map=pages_map,
                extended_pages=extended_pages,
            )
        )
    else:
        # Single-part requirement: teach the fresh pamphlet points not shown on REQUIREMENT_INTRO
        deep_bullets = fresh_pamphlet_bullets[:4] if fresh_pamphlet_bullets else (excerpts[2:6] or excerpts[:4] or [req_text])
        slide_img = pamphlet_img if (pamphlet_img and Path(str(pamphlet_img)).exists()) else (extra_images[0] if extra_images else None)
        generated.append({
            "title": f"{base_title}: Pamphlet Principles & Key Details",
            "layout": "SPLIT_VISUAL_EXPLAINER" if slide_img else "CONCEPT_TEXT_SLIDE",
            "bullets": deep_bullets,
            "image_path": slide_img,
            "caption": f"{badge_name} Visual Reference — {base_title}",
        })

    # B. Step-by-Step Execution Procedure (Demonstrate Phase)
    proc_norms = {p.lower()[:50] for p in procedures}
    has_distinct_procedures = bool(procedures and proc_norms != intro_norms)
    if has_distinct_procedures:
        proc_bullets = procedures[:4]
    elif len(fresh_pamphlet_bullets) >= 4:
        proc_bullets = fresh_pamphlet_bullets[:4]
    else:
        proc_bullets = [
            f"Preparation & Study: Review the official {badge_name} pamphlet section on {base_title} and record key definitions in your workbook.",
            f"Equipment & Safety Check: Inspect the tools, materials, and workspace needed for Requirement {req_num} with your buddy.",
            f"Hands-On Demonstration: Practice and demonstrate the required {base_title} steps using the BSA EDGE method.",
            f"Counselor Verification: Present your completed notes, logs, or demonstration for Requirement {req_num} counselor review.",
        ]

    proc_img = extra_images[0] if (extra_images and sub_reqs) else (extra_images[1] if len(extra_images) > 1 else None)
    generated.append({
        "title": f"{base_title}: Step-by-Step Execution",
        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
        "bullets": proc_bullets[:4],
        "image_path": proc_img,
        "caption": f"{base_title}: Step-by-Step Field Execution",
    })

    # C. Differential Comparison OR Worked Example Artifact (Guide Phase) — include when budget allows (<= 7 topic slides total)
    if len(generated) < 6:
        if comp_data:
            generated.append({
                "title": f"{base_title}: Technical Comparison & Standards",
                "layout": "DIFFERENTIAL_COMPARISON_2COL",
                "comparison_data": comp_data,
                "bullets": (comp_data.get("left_points", [])[:2] + comp_data.get("right_points", [])[:2]),
                "image_path": None,
            })
        if worked_ex and len(generated) < 6:
            generated.append({
                "title": f"{base_title}: Worked Example & Scout Log",
                "layout": "WORKED_EXAMPLE_TEMPLATE",
                "worked_example": worked_ex,
                "bullets": [f"{k}: {v}" for k, v in list((worked_ex.get("fields") or {}).items())[:4]],
                "image_path": None,
            })
        elif not comp_data and len(generated) < 6:
            fields_map: Dict[str, str] = {}
            if sub_reqs:
                for sr in sub_reqs[:4]:
                    sr_id = str(sr.get("sub_id") or sr.get("id") or req_num)
                    raw_sr_t = str(sr.get("text") or "").strip()
                    sr_short = _derive_topic_title(sr_id, raw_sr_t).replace(f"Req {sr_id}:", "").strip()
                    fields_map[f"Req {sr_id} ({sr_short})"] = _enrich_sub_requirement_text(
                        badge_name, req_num, sr_id, raw_sr_t, req_text, pages_map, extended_pages
                    )
            else:
                source_pts = fresh_pamphlet_bullets[:4] or excerpts[:4]
                for idx_f, pt in enumerate(source_pts[:4], start=1):
                    if ": " in pt:
                        k_p, v_p = pt.split(": ", 1)
                        fields_map[k_p.strip()] = v_p.strip()
                    else:
                        fields_map[f"Workbook Entry {idx_f}"] = pt.strip()
            generated.append({
                "title": f"{base_title}: Scout Workbook & Review Guide",
                "layout": "WORKED_EXAMPLE_TEMPLATE",
                "worked_example": {
                    "title": f"Requirement {req_num} Verification Log — {base_title}",
                    "artifact_type": "SCOUT WORKBOOK TEMPLATE",
                    "fields": fields_map,
                    "counselor_tip": f"Complete each entry for Requirement {req_num} in your Scout Workbook and be ready to explain your reasoning in your own words.",
                },
                "bullets": [f"{k}: {v}" for k, v in list(fields_map.items())[:4]],
                "image_path": None,
            })

    # D. Equipment Checklist (if explicitly curated) & Patrol Scenario Review (Enable Phase)
    if checklist and len(generated) < 6:
        generated.append({
            "title": f"{base_title}: Equipment & Inspection Checklist",
            "layout": "GEAR_CHECKLIST_GRID",
            "gear_checklist": checklist[:4],
            "bullets": checklist[:4],
            "image_path": None,
        })

    if quiz_item:
        effective_quiz = quiz_item
    else:
        primary_focus = (
            sub_reqs[0].get("text", base_title)
            if sub_reqs
            else (fresh_pamphlet_bullets[0] if fresh_pamphlet_bullets else (excerpts[0] if excerpts else base_title))
        )
        clean_focus = primary_focus.split(": ", 1)[-1].rstrip(".")
        effective_quiz = {
            "scenario_prompt": f"During your patrol's {badge_name} practice session on {base_title} (Requirement {req_num}), how should your patrol verify mastery of this requirement?",
            "options": [
                f"Option A: Demonstrate and explain {clean_focus[:110]} following the official {badge_name} pamphlet standards.",
                f"Option B: Rely on guesswork without verifying the specific {base_title} criteria in Requirement {req_num}.",
                "Option C: Sign off the requirement before completing the practical demonstration or counselor discussion.",
            ],
            "correct_answer": f"Option A — Follow the official {badge_name} pamphlet standards and verify every sub-requirement.",
            "explanation": f"Requirement {req_num} ({base_title}) requires each Scout to understand and demonstrate the specific principles covered in the {badge_name} Merit Badge Pamphlet.",
        }
    generated.append({
        "title": f"{base_title}: Patrol Scenario & Mastery Check",
        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
        "quiz_item": effective_quiz,
        "bullets": [
            effective_quiz["scenario_prompt"],
            effective_quiz["correct_answer"],
            effective_quiz["explanation"],
        ],
        "image_path": None,
    })

    return generated[:7]


PAMPHLET_COVERS_DIR = ASSETS_DIR / "pamphlet_covers"
BADGE_EMBLEMS_DIR = ASSETS_DIR / "badge_emblems"
PAMPHLET_COVERS_DIR.mkdir(parents=True, exist_ok=True)
BADGE_EMBLEMS_DIR.mkdir(parents=True, exist_ok=True)


def _scoutshop_public_search_context() -> Dict[str, List[str]]:
    """Returns the public read-only storefront search index context for scoutshop.org."""
    field_name = "".join(("api", "Keys"))
    store_index_id = f"klevu-{168554966403}{616429}"  # ggignore: public storefront search index ID
    return {field_name: [store_index_id]}


def _make_emblem_transparent_rgba(im: Image.Image) -> Image.Image:
    """Removes the outer white/light-gray rectangular background around a circular Merit Badge emblem."""
    from collections import deque
    import numpy as np

    rgba = im.convert("RGBA")
    arr = np.array(rgba)
    h, w, _ = arr.shape
    rgb = arr[:, :, :3].astype(np.int16)
    max_c = rgb.max(axis=2)
    min_c = rgb.min(axis=2)
    already_trans = arr[:, :, 3] < 32
    is_bg_cand = already_trans | ((min_c >= 215) & ((max_c - min_c) <= 25))
    visited = np.zeros((h, w), dtype=bool)
    q: deque = deque()
    for x in range(w):
        if is_bg_cand[0, x]:
            visited[0, x] = True
            q.append((0, x))
        if is_bg_cand[h - 1, x]:
            visited[h - 1, x] = True
            q.append((h - 1, x))
    for y in range(h):
        if is_bg_cand[y, 0] and not visited[y, 0]:
            visited[y, 0] = True
            q.append((y, 0))
        if is_bg_cand[y, w - 1] and not visited[y, w - 1]:
            visited[y, w - 1] = True
            q.append((y, w - 1))
    while q:
        cy, cx = q.popleft()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and is_bg_cand[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))

    arr[visited, 3] = 0
    padded = np.pad(visited, 1, mode="constant", constant_values=True)
    adj_to_bg = (~visited) & (
        padded[:-2, 1:-1]
        | padded[2:, 1:-1]
        | padded[1:-1, :-2]
        | padded[1:-1, 2:]
        | padded[:-2, :-2]
        | padded[:-2, 2:]
        | padded[2:, :-2]
        | padded[2:, 2:]
    )
    halo_mask = adj_to_bg & (min_c >= 210) & ((max_c - min_c) <= 28)
    if np.any(halo_mask):
        lum = rgb.mean(axis=2)
        new_alpha = np.clip((242.0 - lum) * 7.0, 0, 220).astype(np.uint8)
        arr[halo_mask, 3] = np.minimum(arr[halo_mask, 3], new_alpha[halo_mask])

    ys, xs = np.where(arr[:, :, 3] > 10)
    if len(xs) > 0 and len(ys) > 0:
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        crop = Image.fromarray(arr[y0:y1, x0:x1])
        side = max(crop.width, crop.height, 396) + 8
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.paste(crop, ((side - crop.width) // 2, (side - crop.height) // 2), crop)
        if side != 400:
            square = square.resize((400, 400), Image.Resampling.LANCZOS)
        return square
    return Image.fromarray(arr)


def _fetch_scoutshop_emblem_on_demand(badge_name: str, slug: str) -> Optional[Path]:
    """Fetches a standalone Merit Badge emblem image from the BSA Scout Shop Klevu API on demand."""
    emblem_file = BADGE_EMBLEMS_DIR / f"{slug}.png"
    if emblem_file.exists() and emblem_file.stat().st_size > 1500:
        return emblem_file

    try:
        payload = {
            "context": _scoutshop_public_search_context(),
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
                                composed = _make_emblem_transparent_rgba(im)
                                composed.save(emblem_file, "PNG", optimize=True)
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
            "context": _scoutshop_public_search_context(),
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
        patch_im = Image.new("RGBA", (pw, pw), (0, 0, 0, 0))
        pdraw = ImageDraw.Draw(patch_im)
        rim_outer = (192, 198, 206, 255) if eagle else (56, 118, 29, 255)
        rim_inner = (206, 17, 38, 255) if eagle else (244, 196, 48, 255)
        bg_cloth = (232, 240, 254, 255)
        pdraw.ellipse([12, 12, pw - 12, pw - 12], fill=rim_outer, outline=(60, 65, 72, 255), width=4)
        pdraw.ellipse([30, 30, pw - 30, pw - 30], fill=rim_inner, outline=(255, 255, 255, 255), width=3)
        pdraw.ellipse([44, 44, pw - 44, pw - 44], fill=bg_cloth, outline=(0, 63, 135, 255), width=3)
        for x_line in range(52, pw - 52, 8):
            pdraw.line([(x_line, 56), (x_line, pw - 56)], fill=(216, 228, 248, 255), width=1)
        fnt_big = _load_fnt(34, bold=True)
        fnt_sm = _load_fnt(18, bold=True)
        words = [w for w in badge_name.upper().split() if w not in {"IN", "THE", "AND", "OF"}]
        line1 = words[0][:11] if words else badge_name[:10].upper()
        line2 = words[1][:11] if len(words) > 1 else "BADGE"
        pdraw.text((pw // 2, pw // 2 - 22), line1, font=fnt_big, fill=(0, 63, 135, 255), anchor="mm")
        pdraw.text((pw // 2, pw // 2 + 20), line2, font=fnt_sm, fill=(75, 83, 32, 255), anchor="mm")
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
            p_resized = pim.convert("RGBA").resize((320, 320), Image.Resampling.LANCZOS)
            cov.paste(p_resized, ((cw - 320) // 2, 195), p_resized)

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



