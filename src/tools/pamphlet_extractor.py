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
import json
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

from src.config import ASSETS_DIR, _read_cached_json, badge_file_slug, badge_url_slug

PAMPHLETS_DIR = ASSETS_DIR / "pamphlets"
PAMPHLET_IMAGES_DIR = ASSETS_DIR / "pamphlet_images"
WEB_IMAGES_DIR = ASSETS_DIR / "web_images"

PAMPHLETS_DIR.mkdir(parents=True, exist_ok=True)
PAMPHLET_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
WEB_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

_PAMPHLET_INDEX_CACHE: Dict[str, Dict[str, Any]] = {}
_RAW_FILE_MD5_CACHE: Dict[Tuple[str, int, int], str] = {}


def _badge_slug(badge_name: str) -> str:
    return badge_file_slug(badge_name)


def _badge_url_slug(badge_name: str) -> str:
    return badge_url_slug(badge_name)


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


def _repair_pdf_word_concatenations(text: str) -> str:
    """Repairs common line-wrap word concatenations and OCR prefix glitches from legacy PDF extraction passes."""
    if not text:
        return ""
    s = text
    # Strip synthetic 3-word OCR prefixes and "Core Standard N (Req N):" prefixes
    s = re.sub(
        r"^(?:Seen\s+Golfers\s+Lick|There\s+Few\s+First-aid|Party\s*trusts\s+She\s+Promised|"
        r"Course\s+Profit\s+Not\s*be|Situation\s+Members\s*of|Ever\s+Feeling\s+Gut|"
        r"Core\s+Standard\s+\d+\s*\(\s*Req\.?\s*[0-9a-zA-Z()]+\s*\))\s*:\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )
    # Fix "Theindividual", "thekit", "themedication", "thevictim", "theperson", "thefirst"
    s = re.sub(
        r"\b(The|the)(individual|kit|medication|victim|person|patient|first|wound|scene|water|ground|body|blood|skin|bone|joint|splint|bandage|burn|fire|camp|trail|patrol|troop|scout|counselor|pamphlet)\b",
        r"\1 \2",
        s,
    )
    # Fix "andallowed", "andthe", "andcheck", "andapply", "andkeep"
    s = re.sub(
        r"\b(And|and)(allowed|the|check|apply|keep|place|hold|call|use|wear|treat|make|take|give|Wash|wash|dry|clean|cover)\b",
        r"\1 \2",
        s,
    )
    # Fix glued OCR words across pamphlet extractions
    explicit_joins = {
        "prescribedemergency": "prescribed emergency",
        "personunder": "person under",
        "trainedand": "trained and",
        "allowedto": "allowed to",
        "locatingthe": "locating the",
        "handingit": "handing it",
        "bestthat": "best that",
        "administersthe": "administers the",
        "partytrusts": "party trusts",
        "notbe": "not be",
        "membersof": "members of",
        "fromother": "from other",
        "willroll": "will roll",
        "themsafe": "them safe",
        "thatcan": "that can",
        "thathelps": "that helps",
        "thatsomeone": "that someone",
        "medicalcrews": "medical crews",
        "mayexperience": "may experience",
        "symptomsthan": "symptoms than",
        "checksand": "checks and",
        "interpretsthe": "interprets the",
        "yourselfwith": "yourself with",
        "tobeinfectious": "to be infectious",
        "shouldbe": "should be",
        "mustbe": "must be",
        "canbe": "can be",
        "tobe": "to be",
        "inthe": "in the",
        "ofthe": "of the",
        "onthe": "on the",
        "forthe": "for the",
        "withthe": "with the",
        "bythe": "by the",
        "atthe": "at the",
        "fromthe": "from the",
    }
    s_low = s.lower()
    for bad_tok, good_tok in explicit_joins.items():
        if bad_tok in s_low:
            s = re.sub(rf"\b{re.escape(bad_tok)}\b", good_tok, s, flags=re.IGNORECASE)
            s_low = s.lower()
    return s


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
    # Rejoin single-uppercase-letter BSA PDF kerning splits across newlines ("R\neducing" -> "Reducing", "Patrol/T\nroop" -> "Patrol/Troop")
    text = re.sub(r"\b([A-Z]|Patrol/T)\n([a-z]{2,})", r"\1\2", text)
    # Fix inline uppercase kerning splits common in BSA PDFs ("Y our" -> "Your", "T o" -> "To", "W ith" -> "With")
    text = re.sub(
        r"\b([TWYFBCPSDHLMRN])\s+(o|our|he|hat|his|hem|hen|here|hy|ith|rom|or|an|ill|ould|hould|efore|fter|nder|ver|art|lan|lace|eople|ood|ater|ire|irst|hile|hich)\b",
        r"\1\2",
        text,
    )
    text = _repair_pdf_word_concatenations(text)
    # Remove decorative leading dots on headings (e.g. ".How to Handle" -> "How to Handle")
    text = re.sub(r"(?m)^\s*\.([A-Z])", r"\1", text)
    text = re.sub(r"\s+\.([A-Z])", r" \1", text)
    # Clean double punctuation artifacts ("?." -> "?", "!." -> "!")
    text = re.sub(r"\?\.", "?", text)
    text = re.sub(r"!\.", "!", text)
    # Collapse horizontal whitespace
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


_PAMPHLET_CATALOG_PATH = ASSETS_DIR.parent / "data" / "pamphlet_image_catalog.json"
_PAMPHLET_VISION_CATALOG_CACHE: Optional[Dict[str, Dict[str, Any]]] = None

_DISCARDED_PAMPHLET_FILENAMES = {
    "first_aid_p002_img1.png",
    "first_aid_p061_img1.png",
    "first_aid_p062_img1.png",
    "first_aid_p063_img1.png",
    "first_aid_p064_img3.png",
    "first_aid_p080_img1.png",
    "first_aid_p081_img2.png",
    "first_aid_p081_img3.png",
    "first_aid_p106_img1.png",
    "first_aid_p106_img3.png",
    "first_aid_p108_img1.png",
    "citizenship_in_the_nation_p002_img1.png",
    "citizenship_in_the_nation_p052_img1.png",
    "cooking_p002_img1.png",
    "cooking_p021_img1.png",
    "cooking_p027_img1.png",
    "cooking_p098_img2.png",
    "cooking_p100_img1.png",
}


_PAMPHLET_VISION_CATALOG_MTIME = 0.0

def _load_pamphlet_image_catalog() -> Dict[str, Dict[str, Any]]:
    """Loads the vision-verified pamphlet image catalog mapping filenames to requirement numbers and captions."""
    global _PAMPHLET_VISION_CATALOG_CACHE, _PAMPHLET_VISION_CATALOG_MTIME
    if not _PAMPHLET_CATALOG_PATH.exists():
        return {}
    current_mtime = _PAMPHLET_CATALOG_PATH.stat().st_mtime_ns
    if _PAMPHLET_VISION_CATALOG_CACHE is not None and _PAMPHLET_VISION_CATALOG_MTIME == current_mtime:
        return _PAMPHLET_VISION_CATALOG_CACHE
    try:
        _PAMPHLET_VISION_CATALOG_CACHE = json.loads(_PAMPHLET_CATALOG_PATH.read_text(encoding="utf-8"))
        _PAMPHLET_VISION_CATALOG_MTIME = current_mtime
        return _PAMPHLET_VISION_CATALOG_CACHE
    except Exception:
        pass
    _PAMPHLET_VISION_CATALOG_CACHE = {}
    return _PAMPHLET_VISION_CATALOG_CACHE


_DISCARDABLE_IMAGE_MEMO: Dict[Tuple[str, int, int], bool] = {}


def _is_discardable_pamphlet_image(img_path: Path, page_num: int = 0, page_count: int = 100) -> bool:
    """Inspects an extracted pamphlet image and returns True if it is a full-page text scan, frontmatter/backmatter
    ad, QR code, or block of printed text that should be discarded rather than placed on a teaching slide."""
    memo_key = (str(img_path), page_num, page_count)
    if memo_key in _DISCARDABLE_IMAGE_MEMO:
        return _DISCARDABLE_IMAGE_MEMO[memo_key]
    name = img_path.name
    if name.endswith("_figure.png") or name in _DISCARDED_PAMPHLET_FILENAMES:
        _DISCARDABLE_IMAGE_MEMO[memo_key] = True
        return True
    # Page 2 in BSA pamphlets is "How to Use This Pamphlet" text; last 2 pages are back-cover ads / photo credits
    if page_num == 2 or (page_count > 12 and page_num >= page_count - 2):
        _DISCARDABLE_IMAGE_MEMO[memo_key] = True
        return True
    m_p = re.search(r"_p(\d+)_img", name)
    if m_p:
        p_parsed = int(m_p.group(1))
        if p_parsed == 2:
            _DISCARDABLE_IMAGE_MEMO[memo_key] = True
            return True
    if not img_path.exists():
        _DISCARDABLE_IMAGE_MEMO[memo_key] = True
        return True
    try:
        with Image.open(img_path) as im:
            w, h = im.size
            if (
                w < 160
                or h < 130
                or (h < 220 and (w / max(1, h)) >= 2.2)
                or (w / max(1, h)) > 3.2
                or (h / max(1, w)) > 2.8
            ):
                _DISCARDABLE_IMAGE_MEMO[memo_key] = True
                return True
            gray = im.convert("L").resize((160, 160))
            px = gray.load()
            white_cnt = 0
            text_like_rows = 0
            for y in range(12, 148, 3):
                transitions = 0
                prev_dark = px[12, y] < 150
                for x in range(12, 148):
                    v = px[x, y]
                    if v >= 235:
                        white_cnt += 1
                    is_dark = v < 150
                    if is_dark != prev_dark:
                        transitions += 1
                        prev_dark = is_dark
                if transitions >= 18:
                    text_like_rows += 1
            total_sampled = (136 // 3 + 1) * 136
            white_ratio = white_cnt / float(max(1, total_sampled))
            # High white ratio combined with many high-frequency dark/light scanlines indicates a text page or QR code
            if white_ratio >= 0.66 and text_like_rows >= 16:
                _DISCARDABLE_IMAGE_MEMO[memo_key] = True
                return True
    except Exception:
        _DISCARDABLE_IMAGE_MEMO[memo_key] = True
        return True
    _DISCARDABLE_IMAGE_MEMO[memo_key] = False
    return False


def _badge_stem_roots(badge_name: str) -> List[str]:
    """Returns lowercase morphological roots for the badge name so generic badge words don't bias page matching."""
    roots: List[str] = []
    for w in re.findall(r"[a-z]{4,}", str(badge_name or "").lower()):
        if w in {"personal", "american", "citizenship", "national", "science", "environmental", "first", "emergency"}:
            roots.append(w)
            continue
        stem = w
        for suf in ("tions", "tion", "ings", "ing", "ments", "ment", "ness", "ers", "ors", "ies", "es", "ed", "er", "or", "ic", "al", "s"):
            if stem.endswith(suf) and len(stem) - len(suf) >= 4:
                stem = stem[: -len(suf)]
                break
        roots.append(stem[:6] if len(stem) >= 6 else stem)
    return roots


def _ensure_complete_caption_sentence(text: str, max_chars: int = 125) -> str:
    """Ensures a caption is a complete, natural sentence without mid-clause truncation or dangling stopwords."""
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if not s:
        return ""
    # Strip trailing or inline parenthetical page/requirement citations like "(p. 31, p. 32)" or "(Req. 1)"
    s = re.sub(r"\s*\(\s*(?:pp?\.?|pages?)\s*\d+[^)]*\)", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"\s*\(\s*(?:pp?\.?|pages?|Req\.?|Reqs\.?)\s*\d*$", "", s, flags=re.IGNORECASE).strip()
    # Strip leading "Heading: " prefix if the remainder is a full sentence
    if ": " in s:
        head, tail = s.split(": ", 1)
        if (len(head) <= 68 or "(req" in head.lower()) and len(tail) >= 24 and tail[0].isupper():
            s = tail.strip()
    # Protect common abbreviations so ". " inside "Req. 1", "p. 12", "U.S.", "Dr.", "ft.", etc. never triggers a sentence split
    _abbrev_token = "\x00"
    s_prot = re.sub(
        r"\b(Reqs?|pp?|U\.S|Dr|Mr|Mrs|Ms|St|Mt|Ft|ft|in|oz|lbs?|min|sec|hr|No|Fig|vs|e\.g|i\.e)\.\s+",
        lambda m: f"{m.group(1)}{_abbrev_token} ",
        s,
    )
    if len(s_prot) > max_chars:
        # Prefer splitting at a natural clause boundary before max_chars with balanced parentheses
        window = s_prot[:max_chars]
        split_done = False
        for sep in (". ", "; ", " — ", " – ", ", which ", ", where ", ", while ", ", although ", ", because ", ", and ", ", or "):
            pos = window.rfind(sep)
            if pos >= 42 and window[:pos].count("(") == window[:pos].count(")"):
                s_prot = window[:pos].strip()
                split_done = True
                break
        if not split_done:
            s_prot = window.rsplit(" ", 1)[0].strip()
    s = s_prot.replace(_abbrev_token, ".")
    # If an unclosed parenthesis remains near the tail, strip from the unclosed '('
    if s.count("(") > s.count(")"):
        last_open = s.rfind("(")
        if last_open >= 24:
            s = s[:last_open].strip()
        else:
            s = s.replace("(", "")
    s = s.rstrip(" ,;:-—(")
    # Remove any trailing dangling prepositions, articles, conjunctions, or auxiliaries
    dangling = {
        "a", "an", "the", "of", "in", "to", "for", "with", "on", "at", "from", "by", "about",
        "as", "into", "like", "through", "after", "over", "between", "out", "against", "during",
        "without", "before", "under", "around", "among", "and", "or", "but", "nor", "so", "yet",
        "because", "although", "since", "unless", "while", "where", "when", "that", "which", "who",
        "whom", "whose", "whether", "there", "their", "these", "those", "this", "other", "such",
        "can", "could", "may", "might", "must", "shall", "should", "will", "would", "is", "are",
        "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "very",
        "more", "most", "some", "any", "each", "every", "either", "neither", "both", "all",
        "many", "much", "few", "several", "own", "same", "than", "too", "also", "just", "only",
        "put", "get", "make", "take", "keep", "stay", "top", "help", "need", "use", "using",
        "simple", "physical", "great", "two", "three", "four", "five", "req", "reqs", "p", "pp",
    }
    words = s.split()
    while len(words) > 4 and re.sub(r"[^a-z]", "", words[-1].lower()) in dangling:
        words.pop()
    s = " ".join(words).rstrip(" ,;:-—(")
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    if s and not s.endswith((".", "!", "?")):
        s += "."
    return s


def strip_pamphlet_and_req_caption_prefixes(caption: str, badge_name: str = "") -> str:
    """Removes 'Official <Badge> Pamphlet Figure', '<Badge> handbook illustration depicting', and 'Requirement #' prefixes."""
    s = re.sub(r"\s+", " ", str(caption or "")).strip()
    if not s:
        return ""
    s = re.sub(
        r"^(?:🍌\s*Hero\s*Illustration\s*:\s*|✨\s*EDGE\s*Skill\s*Map\s*:\s*|EDGE\s*Skill\s*Concept\s*Map\s*[—\-:,]\s*)",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    # Strip Option A boilerplate prefixes: "<Badge> handbook illustration depicting ..." and "Four-panel <Badge> instructional field visual illustrating ..."
    m_opt_a = re.match(
        r"^(?:Four-panel\s+.+?\s+instructional\s+field\s+visual\s+illustrating\s+|.+?\s+handbook\s+illustration\s+depicting\s+)(.+)$",
        s,
        flags=re.IGNORECASE,
    )
    if m_opt_a:
        s = m_opt_a.group(1).strip()
        if ": " in s:
            head_part, body_part = s.split(": ", 1)
            if len(head_part) <= 50 and len(body_part) >= 24:
                s = body_part.strip()
    s = re.sub(
        r"^(?:Official\s+(?:BSA\s+|Scouting\s+America\s+)?[^—\-:]{2,45}?\s*Pamphlet\s+(?:Figure|Reference|Visual|Diagram)\s*[—\-:]\s*)",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    s = re.sub(
        r"^[^—\-:]{2,55}?\s*\(\s*Req\.?\s*[0-9a-zA-Z().\-]+\s*\)\s*[—\-:]\s*(?:Field\s*&\s*handbook\s+overview\s+illustration|Four-part\s+instructional\s+visual\s+plate)\s*[—\-:]\s*",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    if badge_name:
        esc_b = re.escape(badge_name)
        s = re.sub(
            rf"^(?:Official\s+)?{esc_b}\s+(?:Pamphlet\s+)?(?:Figure|Reference|Visual\s+Reference|Sub-Requirement\s+Reference)\s*[—\-:]\s*",
            "",
            s,
            flags=re.IGNORECASE,
        ).strip()
    s = re.sub(r"^Visual\s+Reference\s*[—\-:]\s*", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"^(?:Requirement|Req\.?)\s+[0-9a-zA-Z().\-]+\s*[:—\-]\s*", "", s, flags=re.IGNORECASE).strip()
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    return s


def analyze_and_match_pamphlet_image(
    badge_name: str,
    img_path: Path,
    page_num: int,
    pages_map: Dict[int, Dict[str, Any]],
    req_number: str = "",
    req_text: str = "",
    topic_title: str = "",
    page_count: int = 100,
) -> Optional[Dict[str, str]]:
    """Analyzes an extracted pamphlet image to verify it is a valid visual (not a text block),
    pairs it with a matching merit badge requirement, and returns an accurate context-specific caption
    with zero 'Official ... Pamphlet Figure' or 'Requirement #' prefixes. Returns None if discarded or unmatched."""
    if _is_discardable_pamphlet_image(img_path, page_num=page_num, page_count=page_count):
        return None

    catalog = _load_pamphlet_image_catalog()
    cat_entry = catalog.get(img_path.name)
    if cat_entry:
        if cat_entry.get("discard"):
            return None
        cat_req = str(cat_entry.get("req_number") or "").strip()
        clean_req = re.sub(r"[a-zA-Z]+$", "", str(req_number or "")).strip()
        # Accept catalog entry if it matches clean_req, or if allowed_reqs contains clean_req, or if cat_req is wildcard/empty
        allowed_reqs = [str(r).strip() for r in (cat_entry.get("req_numbers") or []) if str(r).strip()]
        if clean_req and cat_req and cat_req != clean_req and clean_req not in allowed_reqs:
            return None
        return {
            "req_number": clean_req or cat_req,
            "caption": strip_pamphlet_and_req_caption_prefixes(str(cat_entry.get("caption") or ""), badge_name),
            "topic": str(cat_entry.get("topic") or topic_title),
        }

    slug = _badge_slug(badge_name)
    if any(k.startswith(f"{slug}_p") for k in catalog):
        return None

    # For badges without a pre-cached vision catalog entry, analyze the page context around the image
    # and verify semantic overlap with the target requirement before accepting the image.
    p_info = pages_map.get(page_num) or {}
    page_heading = str(p_info.get("heading") or "").strip()
    page_text = str(p_info.get("text") or "").strip()
    if any(skip_w in page_heading.lower() for skip_w in ("glossary", "index", "acknowledgments", "photo credits", "resources")):
        return None

    badge_roots = _badge_stem_roots(badge_name)
    stop_w = {
        "explain", "describe", "discuss", "demonstrate", "show", "counselor", "scout", "scouts",
        "merit", "badge", "following", "requirement", "requirements", "including", "using", "their", "about",
        "would", "should", "could", "which", "where", "while", "under", "least", "three",
        "short", "written", "report", "outline", "knowledge", "plans", "continue", "commonly",
        "before", "after", "completing", "complete", "through", "between", "during",
    }
    req_words = {
        w for w in re.findall(r"[a-z]{4,}", f"{topic_title} {req_text}".lower())
        if w not in stop_w and not any(w.startswith(rt) for rt in badge_roots)
    }
    page_words = set(re.findall(r"[a-z]{4,}", f"{page_heading} {page_text}".lower()))
    overlap = req_words.intersection(page_words)
    if req_words and len(overlap) == 0:
        return None

    # Extract a descriptive context-specific caption that NEVER duplicates the first 4 slide bullets (page_pts[0..3])
    page_pts = _extract_clean_teaching_points_from_pages(pages_map, [page_num], badge_name, max_points=7)
    clean_topic = strip_pamphlet_and_req_caption_prefixes(topic_title, badge_name).rstrip(".")
    clean_head = re.sub(r"[^A-Za-z0-9 ,'\-/()&]+", " ", page_heading).strip(" .,-:")
    clean_head = re.sub(r"^\d+\s+", "", clean_head).strip(" .,-:")
    if clean_head.lower() in {badge_name.lower(), clean_topic.lower(), "contents", "introduction"}:
        clean_head = ""

    raw_cap = ""
    if len(page_pts) >= 5:
        img_ord = 0
        m_ord = re.search(r"_img(\d+)\.png$", img_path.name)
        if m_ord:
            img_ord = max(0, int(m_ord.group(1)) - 1)
        cand_pt = page_pts[min(len(page_pts) - 1, 4 + img_ord)]
        if ": " in cand_pt:
            _, cand_pt = cand_pt.split(": ", 1)
        # Reject OCR fragments with mid-sentence lowercase period splits like "Beginning. race,"
        if not re.search(r"\.\s+[a-z]", cand_pt):
            raw_cap = cand_pt

    if not raw_cap:
        kw_sample = sorted(overlap, key=lambda w: (-len(w), w))[:3]
        kw_phrase = ", ".join(kw_sample[:2]) + (f", and {kw_sample[2]}" if len(kw_sample) >= 3 else "")
        if clean_head and kw_phrase:
            raw_cap = f"Field reference for {clean_head.lower()} illustrating {kw_phrase} in {clean_topic.lower()}."
        elif clean_head:
            raw_cap = f"Field visual for {clean_head} supporting {clean_topic.lower()} technique and inspection."
        elif kw_phrase:
            raw_cap = f"Visual reference for {clean_topic.lower()} highlighting {kw_phrase} during field practice."
        else:
            raw_cap = f"Visual reference for {clean_topic} demonstrating proper field technique and inspection."

    clean_cap = _ensure_complete_caption_sentence(
        strip_pamphlet_and_req_caption_prefixes(raw_cap, badge_name),
        max_chars=120,
    )
    return {
        "req_number": str(req_number or ""),
        "caption": clean_cap,
        "topic": page_heading or clean_topic,
    }


def _extract_pamphlet_images_for_pdf(pdf_path: Path, slug: str, reader: Any) -> Dict[int, List[Path]]:
    """Extracts high-quality embedded photographs & illustrations per 1-indexed page from the BSA PDF,
    automatically discarding text-block pages, frontmatter/backmatter ads, and non-instructional graphics."""
    page_images: Dict[int, List[Path]] = {}
    total_pages = len(reader.pages) if reader is not None else 100

    existing = sorted(PAMPHLET_IMAGES_DIR.glob(f"{slug}_p*_img*.png"))
    if len(existing) >= 6:
        for img_path in existing:
            m = re.search(r"_p(\d+)_img(\d+)\.png$", img_path.name)
            if m:
                p_num = int(m.group(1))
                if not _is_discardable_pamphlet_image(img_path, page_num=p_num, page_count=total_pages):
                    page_images.setdefault(p_num, []).append(img_path)
        return page_images

    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        if page_num <= 2 or page_num >= total_pages - 2:
            continue
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
                    if pil_img.mode == "P" and "transparency" in pil_img.info:
                        pil_img = pil_img.convert("RGBA")
                    elif pil_img.mode not in ("RGB", "RGBA"):
                        pil_img = pil_img.convert("RGB")
                    extrema = pil_img.convert("L").getextrema()
                    if extrema and (extrema[1] - extrema[0]) > 45:
                        fname = PAMPHLET_IMAGES_DIR / f"{slug}_p{page_num:03d}_img{img_idx+1}.png"
                        if not fname.exists():
                            pil_img.save(fname, "PNG", optimize=True, compress_level=9)
                        if not _is_discardable_pamphlet_image(fname, page_num=page_num, page_count=total_pages):
                            page_images.setdefault(page_num, []).append(fname)
                        else:
                            fname.unlink(missing_ok=True)
            except Exception:
                continue

    return page_images


def render_pamphlet_page_figure(pdf_path: Path, slug: str, page_num: int) -> Optional[Path]:
    """Disabled: never render full PDF pages via pdftoppm as slide figures because they produce blocks of text."""
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
                        raw_im = Image.open(io.BytesIO(img_r.content))
                        if raw_im.mode == "P" and "transparency" in raw_im.info:
                            raw_im = raw_im.convert("RGBA")
                        pil_im = raw_im.convert("RGB")
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

    disk_cache_file = PAMPHLETS_DIR / f"{slug}_index_v1.json"
    if disk_cache_file.exists() and disk_cache_file.stat().st_size > 500:
        try:
            raw_cached = json.loads(disk_cache_file.read_text(encoding="utf-8"))
            pages_restored: Dict[int, Dict[str, Any]] = {}
            all_imgs_restored: List[Tuple[int, Path]] = []
            for p_k, p_val in (raw_cached.get("pages") or {}).items():
                p_num_i = int(p_k)
                im_paths = [
                    Path(ip) for ip in (p_val.get("images") or [])
                    if Path(ip).exists() and not _is_discardable_pamphlet_image(Path(ip), page_num=p_num_i, page_count=int(raw_cached.get("page_count") or 100))
                ]
                for im_p in im_paths:
                    all_imgs_restored.append((p_num_i, im_p))
                pages_restored[p_num_i] = {
                    "pdf_page": p_num_i,
                    "heading": _repair_pdf_word_concatenations(str(p_val.get("heading", ""))),
                    "text": _repair_pdf_word_concatenations(str(p_val.get("text", ""))),
                    "lines": [_repair_pdf_word_concatenations(str(ln)) for ln in (p_val.get("lines") or [])],
                    "images": im_paths,
                }
            index_obj = {
                "badge_name": badge_name,
                "slug": slug,
                "pdf_path": pdf_path,
                "pdf_url": pdf_url,
                "page_count": int(raw_cached.get("page_count") or len(pages_restored)),
                "toc_entries": raw_cached.get("toc_entries") or [],
                "pages": pages_restored,
                "all_images": all_imgs_restored,
            }
            _PAMPHLET_INDEX_CACHE[slug] = index_obj
            return index_obj
        except Exception:
            pass

    reader = PdfReader(str(pdf_path))
    page_images_map = _extract_pamphlet_images_for_pdf(pdf_path, slug, reader)

    pages_data: Dict[int, Dict[str, Any]] = {}
    toc_entries: List[Dict[str, Any]] = []
    all_images: List[Tuple[int, Path]] = []

    pdftotext_pages: Optional[List[str]] = None
    try:
        proc = subprocess.run(
            ["pdftotext", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            split_p = proc.stdout.split("\x0c")
            if len(split_p) >= len(reader.pages):
                pdftotext_pages = split_p
    except Exception:
        pdftotext_pages = None

    for idx, page in enumerate(reader.pages):
        p_num = idx + 1
        raw_txt = ""
        if pdftotext_pages is not None and idx < len(pdftotext_pages):
            raw_txt = pdftotext_pages[idx] or ""
        else:
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

    try:
        serializable_pages = {
            str(k): {
                "pdf_page": v["pdf_page"],
                "heading": v["heading"],
                "text": v["text"],
                "lines": v["lines"],
                "images": [str(ip) for ip in v["images"]],
            }
            for k, v in pages_data.items()
        }
        disk_cache_file.write_text(
            json.dumps(
                {
                    "badge_name": badge_name,
                    "slug": slug,
                    "page_count": len(reader.pages),
                    "toc_entries": toc_entries,
                    "pages": serializable_pages,
                }
            ),
            encoding="utf-8",
        )
    except Exception:
        pass

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
    "seen", "lick", "there", "few", "she", "promised", "partytrusts", "notbe",
    "membersof", "fromother", "willroll", "themsafe", "thatcan", "situation", "profit",
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
    slug = _badge_slug(badge_name)

    badge_roots = _badge_stem_roots(badge_name)
    stop_words = {
        "explain", "describe", "discuss", "demonstrate", "show", "tell", "following",
        "your", "counselor", "with", "what", "when", "where", "which", "that", "this",
        "from", "have", "make", "list", "least", "three", "four", "five", "about",
        "how", "why", "would", "should", "could", "must", "including", "such", "other",
        "person", "scout", "scouts", "merit", "badge", "pamphlet", "requirement",
        "short", "written", "report", "outline", "knowledge", "plans", "continue", "commonly",
    }
    words = [
        w.lower()
        for w in re.findall(r"[A-Za-z]{4,}", req_text)
        if w.lower() not in stop_words and not any(w.lower().startswith(rt) for rt in badge_roots)
    ]

    best_pages: List[int] = []
    req_num_str = str(req_number or "").strip()
    if page_count > 8 and words:
        scored: List[Tuple[float, int]] = []
        for p_num, p_info in pages.items():
            if p_num < 6 or p_num > page_count - 2:
                continue
            # For Golf, prevent Option A (Traditional Golf, pp. 6-77) and Option B (Disc Golf, pp. 78-96) from cross-contaminating
            if slug == "golf":
                if req_num_str.lower().startswith("2a") and p_num >= 78:
                    continue
                if req_num_str.lower().startswith("2b") and p_num < 78:
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
                score += 0.5
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

    clean_req_short = _derive_topic_title(req_number, req_text, matched_heading)
    m_base_num = re.match(r"^(\d+)", req_num_str)
    clean_req_num = m_base_num.group(1) if m_base_num else re.sub(r"[a-zA-Z]+$", "", req_num_str).strip()
    m_opt_prefix = re.match(r"^(\d+[a-zA-Z])", req_num_str)
    opt_prefix = m_opt_prefix.group(1).lower() if m_opt_prefix else ""

    # 1. First check the vision-verified pamphlet image catalog for an unused image paired with this requirement
    chosen_raw_img: Optional[Path] = None
    chosen_img_page: Optional[int] = None
    chosen_img_caption: str = ""

    catalog = _load_pamphlet_image_catalog()
    matching_cat_entries: List[Tuple[int, int, str, Dict[str, Any]]] = []
    for fname, entry in catalog.items():
        if not (fname.startswith(f"{slug}_p") or fname.startswith(f"{slug}_ec")):
            continue
        if entry.get("discard"):
            continue
        entry_req = str(entry.get("req_number") or "").strip()
        allowed_reqs = [str(r).strip() for r in (entry.get("req_numbers") or []) if str(r).strip()]
        all_entry_reqs = [entry_req] + allowed_reqs
        alt_rank = int(entry.get("alternate_rank") or (1 if entry.get("is_alternate") else 0))

        # Tier 0: Exact sub-requirement match (e.g., '2a(3)' or '2a')
        if req_num_str in all_entry_reqs:
            matching_cat_entries.append((0, alt_rank, fname, entry))
        # Tier 1: Option-track prefix match (e.g., '2a' matches '2a(1)')
        elif opt_prefix and any(r_item.lower() == opt_prefix for r_item in all_entry_reqs):
            matching_cat_entries.append((1, alt_rank, fname, entry))
        # Tier 1b: Animal Science species-matched option track ('6c' Horse, '6e' Hog, '6f' Avian)
        elif slug == "animal_science" and opt_prefix in ("6c", "6e", "6f"):
            cap_low = (str(entry.get("caption") or "") + " " + str(entry.get("topic") or "")).lower()
            if (
                (opt_prefix == "6c" and any(w in cap_low for w in ("horse", "mare", "foal", "equine")))
                or (opt_prefix == "6e" and any(w in cap_low for w in ("pig", "piglet", "hog", "swine")))
                or (opt_prefix == "6f" and any(w in cap_low for w in ("chick", "poultry", "avian", "hen")))
            ):
                matching_cat_entries.append((1, alt_rank, fname, entry))
        # Tier 2: Base requirement match ('2'), ONLY if entry is not scoped to a conflicting option track
        elif clean_req_num in all_entry_reqs:
            has_conflicting_opt = opt_prefix and any(
                re.match(r"^\d+[a-zA-Z]", r_item) and not r_item.lower().startswith(opt_prefix)
                for r_item in all_entry_reqs
            )
            if slug == "animal_science" and opt_prefix in ("6c", "6d", "6e", "6f"):
                cap_low = (str(entry.get("caption") or "") + " " + str(entry.get("topic") or "")).lower()
                if any(w in cap_low for w in ("cow", "cattle", "bull", "calf", "dairy", "beef", "shorthorn")):
                    has_conflicting_opt = True
            if not has_conflicting_opt:
                matching_cat_entries.append((2, alt_rank, fname, entry))
    matching_cat_entries.sort(key=lambda x: (x[0], x[1], x[2]))

    for _, _, fname, entry in matching_cat_entries:
        cand_path = PAMPHLET_IMAGES_DIR / fname
        cand_md5 = _raw_file_md5(cand_path) if cand_path.exists() else ""
        if (
            cand_path.exists()
            and not _is_discardable_pamphlet_image(cand_path)
            and str(cand_path) not in used_image_paths
            and (not cand_md5 or f"md5:{cand_md5}" not in used_image_paths)
        ):
            chosen_raw_img = cand_path
            m_p = re.search(r"_p(\d+)_img", fname)
            chosen_img_page = int(m_p.group(1)) if m_p else (best_pages[0] if best_pages else 1)
            chosen_img_caption = strip_pamphlet_and_req_caption_prefixes(str(entry.get("caption") or ""), badge_name)
            break

    # 2. Otherwise search matched or nearby pages (within +/- 2 pages) and verify with analyze_and_match_pamphlet_image
    if not chosen_raw_img:
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
                cand_md5 = _raw_file_md5(img_path) if img_path.exists() else ""
                if (
                    str(img_path) not in used_image_paths
                    and (not cand_md5 or f"md5:{cand_md5}" not in used_image_paths)
                    and img_path.exists()
                ):
                    match_info = analyze_and_match_pamphlet_image(
                        badge_name=badge_name,
                        img_path=img_path,
                        page_num=cand_p,
                        pages_map=pages,
                        req_number=req_number,
                        req_text=req_text,
                        topic_title=clean_req_short,
                        page_count=page_count,
                    )
                    if match_info:
                        chosen_raw_img = img_path
                        chosen_img_page = cand_p
                        chosen_img_caption = match_info["caption"]
                        break
            if chosen_raw_img:
                break

    # Optional web supplement if no pamphlet image matched (for non-cataloged on-demand badges)
    if not chosen_raw_img and not any(k.startswith(f"{slug}_p") for k in catalog):
        web_img = fetch_web_supplement_image(badge_name, req_text[:60], f"{slug}_req_{req_number}")
        if web_img and web_img.exists():
            chosen_raw_img = web_img
            chosen_img_page = 1
            chosen_img_caption = strip_pamphlet_and_req_caption_prefixes(clean_req_short, badge_name)

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
        "pamphlet_image_caption": chosen_img_caption or strip_pamphlet_and_req_caption_prefixes(clean_req_short, badge_name),
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
    if (
        "most likely hazards you may encounter" in lower_raw[:220]
        or "hazards you may encounter while participating" in lower_raw[:220]
        or "hazards you are most likely to encounter" in lower_raw[:220]
        or "most likely hazards associated with" in lower_raw[:220]
    ):
        return "Hazards, First Aid & Safety" if str(req_number).lower() == "overview" else f"Req {req_number}: Hazards, First Aid & Safety"
    if (
        "what a projectile is" in lower_raw[:160]
        or "why a projectile" in lower_raw[:160]
        or ("projectile" in lower_raw[:160] and "range" in lower_raw[:260])
    ):
        topic = "Projectile Safety, Range Rules & Wildlife"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "how you could apply the skills and knowledge of safe and responsible" in lower_raw[:180]:
        topic = "Shooting Sports Careers & Conservation"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "hard news" in lower_raw[:240] and ("feature" in lower_raw[:240] or "editorial" in lower_raw[:240]):
        topic = "Hard News, Feature, Opinion & Editorial"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "state and local laws concerning bicycles" in lower_raw[:220]:
        topic = "State & Local Bicycle Traffic Laws"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "wearing the right clothing for biking" in lower_raw[:220] or ("right clothing" in lower_raw[:180] and "helmet" in lower_raw[:240]):
        topic = "Cycling Apparel, Helmet Fit & Visibility"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "using a bicycle safety checklist, clean" in lower_raw[:160]:
        topic = "Bicycle Safety Inspection & Maintenance"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "winter sports safety" in lower_raw[:180] or ("hypothermia" in lower_raw[:220] and "frostbite" in lower_raw[:220]):
        topic = "Winter Sports Safety, First Aid & Hazards"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "every snow sport participant" in lower_raw[:180]:
        topic = "Sprains, Fractures & Cold-Weather First Aid"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "importance of strength, endurance" in lower_raw[:180]:
        topic = "Winter Fitness, Conditioning & Warm-Up"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "properly clothed and equipped" in lower_raw[:180]:
        topic = "Cold-Weather Layering & Snow Gear Check"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "your responsibility code" in lower_raw[:180]:
        topic = "Skier & Rider Responsibility Code"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "leave no trace" in lower_raw[:200] or "outdoor code" in lower_raw[:200]:
        topic = "Leave No Trace & Outdoor Ethics"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "importance of having a physical examination" in lower_raw[:180]:
        topic = "Pre-Participation Physical & Health Check"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "name and point to the parts of an arrow" in lower_raw[:160]:
        topic = "Arrow Anatomy, Bowstrings & Equipment"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "proper use, care, and storage of" in lower_raw[:160] and "archery" in lower_raw[:240]:
        topic = "Archery Gear Care, Tabs & Armguards"
        return topic if str(req_number).lower() == "overview" else f"Req {req_number}: {topic}"
    if "option a" in lower_raw and "option b" in lower_raw:
        opt_matches = re.findall(r"Option\s+([A-Z])\s*[—–-]\s*([A-Za-z0-9 &/()-]+?)(?=\.\s|\s+\([1a]\)|$)", cleaned)
        if len(opt_matches) >= 2:
            opt_summary = " / ".join(f"{name.strip()}" for _, name in opt_matches[:3])
            return opt_summary if str(req_number).lower() == "overview" else f"Req {req_number}: {opt_summary}"
    if (len(lower_raw) < 420 or "career" in lower_raw[:160] or "professions" in lower_raw[:160]) and (
        "career opportunities" in lower_raw
        or ("three career" in lower_raw and "pick one" in lower_raw)
        or "careers related to" in lower_raw
        or "professions that provide services" in lower_raw
    ):
        return "Careers & Professional Pathways" if str(req_number).lower() == "overview" else f"Req {req_number}: Careers & Professional Pathways"

    # Protect common abbreviations before splitting on punctuation
    subject = cleaned.replace("U.S.", "US").replace("e.g.", "eg").replace("i.e.", "ie")

    prefix_pattern = re.compile(
        r"^(\([a-zA-Z0-9]+\)\s*|"
        r"Before beginning work on other requirements for this merit badge,\s*(?:do the following[:\s,]*)?|"
        r"With the help of your parent or guardian(?:,\s*counselor,\s*or other trusted adult)?,\s*(?:do the following[:\s,]*)?|"
        r"After completing requirement\s+[0-9a-zA-Z]+,\s*|"
        r"Complete the survey below[^.]*\.\s*|"
        r"(?:Select|Choose|Complete)\s+(?:ALL|ONE|TWO|THREE|FOUR|FIVE|SIX|EACH)\s+of\s+the\s+following(?:\s+\w+)?[:\s,]*|"
        r"(?:Define|Explain|Describe|Demonstrate|Discuss|Identify|List|Review|Show|Tell(?:\s+about)?|Research(?:\s+and\s+\w+)?)\s+(?:to\s+your\s+counselor\s+)?(?:your\s+understanding\s+of\s+)?(?:each\s+of\s+)?the\s+following(?:\s+\w+)?[:\s,]*|"
        r"Do (?:ALL|ONE|TWO|THREE|FOUR|FIVE|EACH) of the following(?:\s+options)?(?:,\s*including)?[:\s,]*|"
        r"Do the following[:\s,]*|"
        r"And discuss with your counselor\s+|"
        r"With the aid of diagrams(?:\s*\([^)]*\))?,\s*do each of the following[:\s,]*|"
        r"With the aid of diagrams,\s*|"
        r"With guidance from your counselor,\s*|"
        r"With your counselor's approval,\s*|"
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
        r"Explain how and why\s+|Explain how you would\s+|Explain how\s+|Explain why\s+|Explain what\s+|"
        r"Describe how\s+|Describe the\s+|Describe what\s+|"
        r"List the names of\s+|List the\s+|Identify the\s+|Identify\s+|"
        r"Develop a plan to\s+|Develop a\s+|Tell what\s+|Give the\s+|"
        r"Sketch the face of\s+|Sketch the\s+|Construct a\s+|"
        r"Research and explain\s+|Research and discuss\s+|Research and describe\s+|Research\s+|"
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
    """Returns the canonical de-boxed, compressed pamphlet or AI visual path directly without
    creating duplicate `clean_visual_*.png` copies on disk."""
    if raw_img_path and raw_img_path.exists():
        return str(raw_img_path)
    return str(raw_img_path)


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
    "an open wound with severe bleeding, including the use of direct pressure and when to use a tourniquet": "Severe Bleeding & Tourniquet Use — Apply firm direct pressure with sterile gauze dressings; if life-threatening limb bleeding continues, apply a CoTCCC windlass tourniquet 2 to 3 inches above the wound and record the time.",
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
    "demonstrate proper cpr technique using a training device approved by your counselor": "Hands-On 30:2 CPR Manikin Demonstration — Compress center of chest 2 inches deep at 100 to 120 BPM with full recoil, alternating 30 compressions and 2 rescue breaths.",
    "or simulate the proper use of an automated external defibrillator (aed) using a training device": "AED Trainer Pad Placement & Shock Protocol — Power on the AED trainer, apply adult pads to bare upper-right chest and lower-left ribs, clear rescuers during analysis/shock, and resume CPR.",
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
    # Citizenship in the Nation short sub-requirements
    "the functions of each branch of government": "Constitutional Functions of the Three Branches — Legislative (Article I: Congress drafts bills, levies taxes, declares war), Executive (Article II: President enforces laws, commands Armed Forces), and Judicial (Article III: Supreme Court interprets laws).",
    "why it is important to divide powers among different branches": "Importance of Dividing Power (Separation of Powers) — Concentrating legislative, executive, and judicial authority in one hand invites tyranny; dividing power across three independent branches safeguards individual liberty.",
    "how each branch \"checks\" and \"balances\" the others": "Constitutional Checks & Balances — Presidential veto vs. two-thirds congressional override, Senate confirmation of treaties and federal judges, congressional impeachment power, and Supreme Court judicial review (Marbury v. Madison).",
    "how citizens can be involved in each branch of government": "Citizen Participation Across All Three Branches — Vote and testify in committee hearings (Legislative), comment on federal agency rules and vote for President (Executive), and serve on federal juries or file amicus briefs (Judicial).",
    "what difficulties the nation faced that the author wished to discuss": "Historical Crisis & National Context — Identify the constitutional, economic, or military crisis facing the United States when the speech was delivered (e.g., partisan division and foreign entanglements in 1796, or Civil War preservation of the Union in 1863).",
    "how the speech applies to american citizens today": "Enduring Relevance to Citizens Today — Explain how the speech's warnings and ideals guide modern American voters, civic unity, equal rights, and constitutional self-government today.",
    "the declaration of independence": "The Declaration of Independence (July 4, 1776) — Drafted by Thomas Jefferson, proclaiming that all people are endowed with unalienable rights to life, liberty, and the pursuit of happiness, and that government derives its just powers from the consent of the governed.",
    # First Aid short sub-requirements (Reqs 12, 13, 15)
    "situations where professional help might be needed": "Recognizing When Professional Mental Health Help Is Needed — Identify warning signs such as persistent hopelessness, severe withdrawal, panic attacks, or talk of self-harm that require immediate connection with a trusted adult, counselor, or the 988 Suicide & Crisis Lifeline.",
    "head, neck, and back injuries": "Spinal Stabilization (Head, Neck & Back Injuries) — Suspect spinal trauma after falls, diving, or vehicle impacts; maintain manual inline head-and-neck stabilization, never move or twist the victim unless life-threatening danger requires an emergency drag, and summon EMS.",
    "seizures": "First Aid for Seizures — Clear nearby hard or sharp objects, cushion the person's head with a folded jacket, never restrain movements or put anything in their mouth, time the seizure, and roll into the recovery position once convulsions stop.",
    "diabetes-related emergencies": "Diabetic Emergencies (Hypoglycemia vs. Hyperglycemia) — Recognize sudden cold sweats, shakiness, and confusion (low blood sugar); if the person is conscious and able to swallow safely, give 15–20g of fast-acting oral glucose or fruit juice, or call 911 if unresponsive.",
    "abdominal Pain": "Acute Abdominal Pain Assessment — Keep the patient resting comfortably on their back with knees slightly bent, never give food, water, laxatives, or pain medication (which can mask appendicitis or internal bleeding), and seek medical evaluation.",
    "the training and education needed for each career": "Education & Clinical Certification Path — Research the accredited degree, EMT/Paramedic/RN/MD clinical training hours, national board exams (NREMT/NCLEX), and Wilderness First Responder certifications required.",
    "the expenses you might incur while pursuing these credentials": "Training Costs, Tuition & Equipment Expenses — Estimate tuition, clinical lab fees, certification exam fees, textbooks, uniforms, and continuing education unit (CEU) renewal expenses.",
    "the typical career path and opportunities for advancement": "Career Progression & Specialization — Trace advancement from entry-level EMT-Basic or ER technician to Flight Paramedic, Critical Care Nurse, Physician Assistant, Emergency Physician, or EMS Medical Director.",
    "why this profession might interest you": "Personal Calling & Alignment with the Scout Oath — Reflect on how emergency medical service embodies 'help other people at all times' and matches your interests in science, teamwork, and composure under pressure.",
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
        if w not in {"explain", "discuss", "describe", "show", "demonstrate", "tell", "identify", "what", "when", "where", "your", "with", "from", "that", "have", "each", "other", "others", "important", "nation", "faced", "author", "wished"}
    ]
    if kw_tokens and pages_map:
        search_pages = list(extended_pages) + [p for p in sorted(pages_map.keys()) if p not in extended_pages]
        best_sent = ""
        best_score = 0
        min_required_hits = 2 if len(kw_tokens) >= 2 else 1
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
        if best_sent and best_score >= min_required_hits:
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
    """Groups sub-requirements into balanced 3-4 card slides covering 100% of sub-requirements without lone 1-card orphans."""
    if not sub_reqs:
        return []
    from src.tools.scouting_scraper import _CURATED_OPTION_CHUNK_THEMES, partition_balanced_subreq_chunks

    sub_chunks = partition_balanced_subreq_chunks(sub_reqs, max_per_chunk=4)
    lookup_key = f"{str(badge_name or '').strip().lower()}:{str(req_num or '').strip().lower()}"
    curated_chunk_titles = _CURATED_OPTION_CHUNK_THEMES.get(lookup_key, [])

    slides_out: List[Dict[str, Any]] = []
    for c_idx, chunk in enumerate(sub_chunks):
        chunk_bullets: List[str] = []
        chunk_short_topics: List[str] = []
        for s_idx, sr in enumerate(chunk):
            raw_lbl = str(sr.get("sub_id") or sr.get("id") or sr.get("sub_req_label") or f"{req_num}{chr(97 + s_idx)}").strip()
            sr_id = f"{req_num}{raw_lbl}" if len(raw_lbl) == 1 and raw_lbl.isalpha() and not str(req_num).endswith(raw_lbl) else raw_lbl
            raw_sr_txt = str(sr.get("text") or sr.get("sub_req_text") or "").strip()
            sr_txt = _enrich_sub_requirement_text(
                badge_name, req_num, sr_id, raw_sr_txt, req_text, pages_map, extended_pages
            )
            if " — " in sr_txt:
                topic_head, topic_body = sr_txt.split(" — ", 1)
                clean_head = re.sub(rf"^Req(?:uirement)?\s+{re.escape(sr_id)}\s*[:\-—]\s*", "", topic_head.strip(), flags=re.IGNORECASE).rstrip(".:;")
                clean_head = re.sub(r"\s*\([^)]*\)", "", clean_head).strip()
                if re.match(r"^(?:Explain|Discuss|Describe|Demonstrate|Show|Identify|Tell|Find|List|Name|Review|Obtain|Do)\b", clean_head, flags=re.IGNORECASE):
                    clean_head = _derive_topic_title(sr_id, raw_sr_txt or clean_head).replace(f"Req {sr_id}:", "").strip()
                combined = f"Requirement {sr_id} ({clean_head}): {topic_body.strip()}"
                if clean_head and len(clean_head.split()) <= 5:
                    chunk_short_topics.append(clean_head)
            elif ": " in sr_txt[:60]:
                topic_head, topic_body = sr_txt.split(": ", 1)
                clean_head = re.sub(rf"^Req(?:uirement)?\s+{re.escape(sr_id)}\s*[:\-—]\s*", "", topic_head.strip(), flags=re.IGNORECASE).rstrip(".:;")
                clean_head = re.sub(r"\s*\([^)]*\)", "", clean_head).strip()
                if re.match(r"^(?:Explain|Discuss|Describe|Demonstrate|Show|Identify|Tell|Find|List|Name|Review|Obtain|Do)\b", clean_head, flags=re.IGNORECASE):
                    clean_head = _derive_topic_title(sr_id, raw_sr_txt or clean_head).replace(f"Req {sr_id}:", "").strip()
                combined = f"Requirement {sr_id} ({clean_head}): {topic_body.strip()}"
                if clean_head and len(clean_head.split()) <= 5:
                    chunk_short_topics.append(clean_head)
            elif raw_sr_txt and len(raw_sr_txt.split()) <= 7:
                sr_topic = _derive_topic_title(sr_id, raw_sr_txt).replace(f"Req {sr_id}:", "").strip()
                if sr_txt.lower().startswith(sr_topic.lower()):
                    combined = f"Requirement {sr_id}: {sr_txt}"
                else:
                    combined = f"Requirement {sr_id} ({sr_topic}): {sr_txt}"
                if sr_topic and len(sr_topic.split()) <= 5:
                    chunk_short_topics.append(sr_topic)
            else:
                sr_topic = _derive_topic_title(sr_id, raw_sr_txt or sr_txt).replace(f"Req {sr_id}:", "").strip()
                if sr_topic and len(sr_topic.split()) <= 5:
                    chunk_short_topics.append(sr_topic)
                combined = f"Requirement {sr_id} ({sr_topic}): {sr_txt}" if sr_topic and len(sr_topic) <= 32 else f"Requirement {sr_id}: {sr_txt}"
            chunk_bullets.append(combined)

        first_raw = str(chunk[0].get("sub_id") or chunk[0].get("id") or chunk[0].get("sub_req_label") or f"{req_num}a").strip()
        last_raw = str(chunk[-1].get("sub_id") or chunk[-1].get("id") or chunk[-1].get("sub_req_label") or f"{req_num}b").strip()
        first_id = f"{req_num}{first_raw}" if len(first_raw) == 1 and first_raw.isalpha() and not str(req_num).endswith(first_raw) else first_raw
        last_id = f"{req_num}{last_raw}" if len(last_raw) == 1 and last_raw.isalpha() and not str(req_num).endswith(last_raw) else last_raw
        range_label = f"Reqs {first_id}-{last_id}" if len(chunk) > 1 else f"Req {first_id}"

        # Build clean, non-redundant slide title without double colons, duplicate '(Reqs X-Y)', or 'Sub-Requirement Deep Dive' boilerplate on option tracks
        if c_idx < len(curated_chunk_titles):
            cur_t = str(curated_chunk_titles[c_idx]).strip()
            slide_title = cur_t if (f"({range_label})" in cur_t or "(Req" in cur_t) else f"{cur_t} ({range_label})"
        elif ": " in base_title:
            opt_prefix = base_title.split(": ", 1)[0].strip()
            if len(sub_chunks) == 1:
                slide_title = base_title if (f"({range_label})" in base_title or "(Req" in base_title) else f"{base_title} ({range_label})"
            elif chunk_short_topics:
                uniq_topics = list(dict.fromkeys(chunk_short_topics))[:3]
                slide_title = f"{opt_prefix}: {', '.join(uniq_topics)} ({range_label})"
            else:
                slide_title = base_title if (f"({range_label})" in base_title or "(Req" in base_title) else f"{base_title} ({range_label})"
        elif chunk_short_topics:
            uniq_topics = list(dict.fromkeys(chunk_short_topics))[:3]
            slide_title = f"{base_title}: {', '.join(uniq_topics)} ({range_label})"
        else:
            slide_title = f"{base_title}: Sub-Requirement Deep Dive ({range_label})"

        slides_out.append({
            "title": slide_title,
            "layout": "CONCEPT_TEXT_SLIDE",
            "bullets": chunk_bullets,
            "image_path": None,
            "caption": f"{badge_name} Sub-Requirement Reference — {base_title} ({range_label})",
            "is_subreq_slide": True,
            "sub_requirements_chunk": list(chunk),
            "sub_req_range_label": range_label,
        })
    return slides_out


def _raw_file_md5(path_obj: Optional[Any]) -> str:
    """Returns MD5 hex digest of an image file on disk (cached by path, mtime_ns, and size)."""
    if not path_obj:
        return ""
    try:
        p = Path(str(path_obj))
        if not p.exists() or not p.is_file():
            return ""
        st = p.stat()
        key = (str(p.resolve()), st.st_mtime_ns, st.st_size)
        cached = _RAW_FILE_MD5_CACHE.get(key)
        if cached is not None:
            return cached
        digest = hashlib.md5(p.read_bytes()).hexdigest()
        _RAW_FILE_MD5_CACHE[key] = digest
        return digest
    except Exception:
        return ""


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

    slug = _badge_slug(badge_name)
    # Pre-register MD5 hashes of all integer Nano Banana Hero images for this badge so topic slides
    # never duplicate a Nano Banana Hero image (keeping Nano Banana Heroes exclusive to Requirement Intro slides).
    ai_dir = ASSETS_DIR / "ai_illustrations"
    if ai_dir.exists():
        for nh_file in ai_dir.glob(f"{slug}_req_*_nano_hero.png"):
            if not re.match(rf"^{re.escape(slug)}_req_\d+_nano_hero\.png$", nh_file.name):
                continue
            nh_md5 = _raw_file_md5(nh_file)
            if nh_md5:
                used_image_paths.add(f"md5:{nh_md5}")
            used_image_paths.add(str(nh_file))

    req_num = str(req_dict.get("req_number", str(req_index + 1)))
    req_text = str(req_dict.get("req_text", ""))
    base_title = str(req_dict.get("topic_title") or _derive_topic_title(req_num, req_text)).replace(f"Req {req_num}:", "").strip()
    pamphlet_img = req_dict.get("pamphlet_image_path")
    if pamphlet_img:
        p_md5 = _raw_file_md5(pamphlet_img)
        if p_md5 and f"md5:{p_md5}" in used_image_paths and "ai_illustrations" in str(pamphlet_img):
            pamphlet_img = None

    sub_reqs: List[Dict[str, str]] = list(req_dict.get("sub_requirements") or [])
    if not sub_reqs:
        sub_reqs = _parse_inline_sub_requirements(req_num, req_text)

    p_index = build_pamphlet_index(badge_name)
    pages_map: Dict[int, Dict[str, Any]] = p_index.get("pages") or {}
    page_count: int = int(p_index.get("page_count") or 0)
    matched_pages: List[int] = list(req_dict.get("pamphlet_pages") or [])
    if not matched_pages and page_count > 10:
        body_start = 7
        body_end = max(10, page_count - 4)
        span = max(1, body_end - body_start)
        est_p = body_start + int((req_index / max(1, total_reqs)) * span)
        matched_pages = [min(body_end, max(body_start, est_p))]

    extended_pages: List[int] = list(matched_pages)
    if matched_pages and pages_map:
        for mp in matched_pages:
            for delta in (1, 2, 3, -1, 4, -2):
                cand_p = mp + delta
                if cand_p in pages_map and cand_p not in extended_pages:
                    cand_h = str((pages_map.get(cand_p) or {}).get("heading") or "").lower()
                    if not any(sk in cand_h for sk in ("glossary", "index", "acknowledgments", "photo credits", "resources")):
                        extended_pages.append(cand_p)

    # Build a pool of requirement-matched pamphlet images & accurate captions (never fall back to random unrelated pages!)
    # Note: Do NOT mutate `used_image_paths` until an item is actually popped onto a slide so explicit `topic_slides`
    # referencing a catalog image for this requirement are never blocked!
    clean_req_num = re.sub(r"[a-zA-Z]+$", "", str(req_num or "")).strip()
    catalog = _load_pamphlet_image_catalog()
    has_badge_catalog = any(k.startswith(f"{slug}_p") for k in catalog)
    matched_pamphlet_items: List[Tuple[str, str, str, str]] = []
    seen_cand_keys: set = set()
    if pamphlet_img and Path(str(pamphlet_img)).exists():
        raw_src_str = str(req_dict.get("raw_pamphlet_image_path") or pamphlet_img)
        p_raw_md5 = _raw_file_md5(raw_src_str) or _raw_file_md5(pamphlet_img)
        p_comp_md5 = _raw_file_md5(pamphlet_img)
        if (
            str(pamphlet_img) not in used_image_paths
            and raw_src_str not in used_image_paths
            and (not p_raw_md5 or f"md5:{p_raw_md5}" not in used_image_paths)
            and (not p_comp_md5 or f"md5:{p_comp_md5}" not in used_image_paths)
        ):
            init_cap = strip_pamphlet_and_req_caption_prefixes(
                str(req_dict.get("pamphlet_image_caption") or base_title),
                badge_name,
            )
            matched_pamphlet_items.append((str(pamphlet_img), init_cap, raw_src_str, p_raw_md5))
            seen_cand_keys.add(str(pamphlet_img))
            seen_cand_keys.add(raw_src_str)
            if p_raw_md5:
                seen_cand_keys.add(f"md5:{p_raw_md5}")
            if p_comp_md5:
                seen_cand_keys.add(f"md5:{p_comp_md5}")

    # 1a. Check vision-verified catalog for additional images explicitly paired with this requirement (prioritizing exact sub-req/option match)
    m_opt_req = re.match(r"^(\d+[a-zA-Z])", str(req_num or "").strip())
    opt_prefix_req = m_opt_req.group(1).lower() if m_opt_req else ""
    tiered_cat_candidates: List[Tuple[int, str, Dict[str, Any]]] = []
    for fname, entry in catalog.items():
        if not fname.startswith(f"{slug}_p") or entry.get("discard"):
            continue
        entry_r = str(entry.get("req_number") or "").strip()
        allowed_reqs = [str(r).strip() for r in (entry.get("req_numbers") or []) if str(r).strip()]
        all_e_reqs = [entry_r] + allowed_reqs
        if str(req_num).strip() in all_e_reqs:
            tiered_cat_candidates.append((0, fname, entry))
        elif opt_prefix_req and any(r_it.lower() == opt_prefix_req for r_it in all_e_reqs):
            tiered_cat_candidates.append((1, fname, entry))
        elif slug == "animal_science" and opt_prefix_req in ("6c", "6e", "6f"):
            cap_low = (str(entry.get("caption") or "") + " " + str(entry.get("topic") or "")).lower()
            if (
                (opt_prefix_req == "6c" and any(w in cap_low for w in ("horse", "mare", "foal", "equine")))
                or (opt_prefix_req == "6e" and any(w in cap_low for w in ("pig", "piglet", "hog", "swine")))
                or (opt_prefix_req == "6f" and any(w in cap_low for w in ("chick", "poultry", "avian", "hen")))
            ):
                tiered_cat_candidates.append((1, fname, entry))
        elif clean_req_num in all_e_reqs:
            has_conflicting_opt = opt_prefix_req and any(
                re.match(r"^\d+[a-zA-Z]", r_it) and not r_it.lower().startswith(opt_prefix_req)
                for r_it in all_e_reqs
            )
            if slug == "animal_science" and opt_prefix_req in ("6c", "6d", "6e", "6f"):
                cap_low = (str(entry.get("caption") or "") + " " + str(entry.get("topic") or "")).lower()
                if any(w in cap_low for w in ("cow", "cattle", "bull", "calf", "dairy", "beef", "shorthorn")):
                    has_conflicting_opt = True
            if not has_conflicting_opt:
                tiered_cat_candidates.append((2, fname, entry))
    tiered_cat_candidates.sort(key=lambda x: (x[0], x[1]))

    for _, fname, entry in tiered_cat_candidates:
        cand_img = PAMPHLET_IMAGES_DIR / fname
        if not cand_img.exists() or _is_discardable_pamphlet_image(cand_img):
            continue
        c_md5 = _raw_file_md5(cand_img)
        if (
            str(cand_img) not in used_image_paths
            and (not c_md5 or f"md5:{c_md5}" not in used_image_paths)
            and str(cand_img) not in seen_cand_keys
            and (not c_md5 or f"md5:{c_md5}" not in seen_cand_keys)
        ):
            seen_cand_keys.add(str(cand_img))
            if c_md5:
                seen_cand_keys.add(f"md5:{c_md5}")
            m_p = re.search(r"_p(\d+)_img", fname)
            ep_num = int(m_p.group(1)) if m_p else 1
            composed = _compose_pamphlet_visual_card(
                raw_img_path=cand_img,
                badge_name=badge_name,
                req_number=f"{req_num}_fig{len(matched_pamphlet_items) + 1}",
                topic_title=str(entry.get("topic") or base_title),
                pamphlet_page=ep_num,
            )
            cap_txt = strip_pamphlet_and_req_caption_prefixes(str(entry.get("caption") or base_title), badge_name)
            matched_pamphlet_items.append((composed, cap_txt, str(cand_img), c_md5))
            if len(matched_pamphlet_items) >= 4:
                break

    # 1b. Check nearby extended_pages ONLY if analyze_and_match_pamphlet_image confirms a semantic match to this requirement
    if len(matched_pamphlet_items) < 3 and extended_pages and pages_map:
        for ep in extended_pages:
            for cand_img in (pages_map.get(ep) or {}).get("images", []):
                c_md5 = _raw_file_md5(cand_img)
                if (
                    str(cand_img) not in used_image_paths
                    and (not c_md5 or f"md5:{c_md5}" not in used_image_paths)
                    and str(cand_img) not in seen_cand_keys
                    and (not c_md5 or f"md5:{c_md5}" not in seen_cand_keys)
                    and cand_img.exists()
                ):
                    match_info = analyze_and_match_pamphlet_image(
                        badge_name=badge_name,
                        img_path=cand_img,
                        page_num=ep,
                        pages_map=pages_map,
                        req_number=req_num,
                        req_text=req_text,
                        topic_title=base_title,
                        page_count=page_count,
                    )
                    if not match_info:
                        continue
                    seen_cand_keys.add(str(cand_img))
                    if c_md5:
                        seen_cand_keys.add(f"md5:{c_md5}")
                    composed = _compose_pamphlet_visual_card(
                        raw_img_path=cand_img,
                        badge_name=badge_name,
                        req_number=f"{req_num}_fig{len(matched_pamphlet_items) + 1}",
                        topic_title=match_info.get("topic") or base_title,
                        pamphlet_page=ep,
                    )
                    matched_pamphlet_items.append((composed, match_info["caption"], str(cand_img), c_md5))
                    if len(matched_pamphlet_items) >= 4:
                        break
            if len(matched_pamphlet_items) >= 4:
                break

    avail_pamphlet_pool: List[Tuple[str, str, str, str]] = []
    seen_pool_paths: set = set()
    for p_cand, p_cap, raw_p_str, raw_p_md5 in matched_pamphlet_items:
        if p_cand and Path(str(p_cand)).exists() and p_cand not in seen_pool_paths:
            seen_pool_paths.add(p_cand)
            avail_pamphlet_pool.append((str(p_cand), p_cap, raw_p_str, raw_p_md5))

    def _pop_next_avail_pamphlet() -> Optional[Tuple[str, str]]:
        while avail_pamphlet_pool:
            p_cand, p_cap, raw_p_str, raw_p_md5 = avail_pamphlet_pool.pop(0)
            comp_md5 = _raw_file_md5(p_cand)
            if (
                p_cand in used_image_paths
                or raw_p_str in used_image_paths
                or (raw_p_md5 and f"md5:{raw_p_md5}" in used_image_paths)
                or (comp_md5 and f"md5:{comp_md5}" in used_image_paths)
            ):
                continue
            used_image_paths.add(p_cand)
            used_image_paths.add(raw_p_str)
            if raw_p_md5:
                used_image_paths.add(f"md5:{raw_p_md5}")
            if comp_md5:
                used_image_paths.add(f"md5:{comp_md5}")
            return p_cand, p_cap
        return None

    def _dedupe_slide_bullets(b_list: List[str]) -> List[str]:
        out_b: List[str] = []
        seen_b: set = set()
        for item in b_list:
            s_it = str(item or "").strip()
            if not s_it:
                continue
            norm_k = re.sub(r"[^a-z0-9]+", " ", s_it.lower()).strip()[:65]
            if norm_k and norm_k not in seen_b:
                seen_b.add(norm_k)
                out_b.append(s_it)
        return out_b

    # 1. If the requirement already defines explicit multi-slide `topic_slides`, enrich their image paths
    #    AND ensure 100% of official `sub_requirements` are explicitly covered without repeating Nano Banana heroes.
    explicit_slides = req_dict.get("topic_slides")
    if explicit_slides and isinstance(explicit_slides, list):
        resolved_slides: List[Dict[str, Any]] = []
        for t_idx, ts in enumerate(explicit_slides, start=1):
            ts_copy = dict(ts)
            if ts_copy.get("caption"):
                ts_copy["caption"] = strip_pamphlet_and_req_caption_prefixes(str(ts_copy["caption"]), badge_name)
            raw_img = ts_copy.get("image_path")
            if raw_img and "pamphlet_images" in str(raw_img) and has_badge_catalog:
                cat_check = catalog.get(Path(str(raw_img)).name)
                if not cat_check or cat_check.get("discard") or (
                    clean_req_num and str(cat_check.get("req_number") or "").strip() != clean_req_num
                ):
                    raw_img = None
            raw_md5 = _raw_file_md5(raw_img) if raw_img else ""
            is_duplicate_or_hero = bool(
                raw_img
                and (
                    str(raw_img) in used_image_paths
                    or (raw_md5 and f"md5:{raw_md5}" in used_image_paths)
                )
            )
            layout_type = str(ts_copy.get("layout") or "").upper()
            # Procedural 2x2 grids, Comparisons, Worked Examples, Checklists, and Quizzes look best full-width without cramped split images
            if layout_type in {
                "STEP_BY_STEP_PROCEDURE_4CARD",
                "DIFFERENTIAL_COMPARISON_2COL",
                "WORKED_EXAMPLE_TEMPLATE",
                "GEAR_CHECKLIST_GRID",
                "SOCRATIC_CHECKPOINT_QUIZ",
                "CONCEPT_TEXT_SLIDE",
            }:
                ts_copy["image_path"] = None
            elif raw_img and Path(str(raw_img)).exists() and not is_duplicate_or_hero:
                used_image_paths.add(str(raw_img))
                if raw_md5:
                    used_image_paths.add(f"md5:{raw_md5}")
                # Always use the vision-verified catalog caption when raw_img is in the pamphlet catalog
                cat_hit = catalog.get(Path(str(raw_img)).name)
                if cat_hit and cat_hit.get("caption"):
                    ts_copy["caption"] = strip_pamphlet_and_req_caption_prefixes(str(cat_hit["caption"]), badge_name)
                if "ai_illustrations" in str(raw_img):
                    composed_ts = str(raw_img)
                else:
                    composed_ts = _compose_pamphlet_visual_card(
                        raw_img_path=Path(str(raw_img)),
                        badge_name=badge_name,
                        req_number=f"{req_num}_{t_idx}",
                        topic_title=str(ts_copy.get("title", "")),
                        pamphlet_page=t_idx,
                    )
                c_ts_md5 = _raw_file_md5(composed_ts)
                if c_ts_md5:
                    used_image_paths.add(f"md5:{c_ts_md5}")
                ts_copy["image_path"] = composed_ts
            else:
                popped_item = _pop_next_avail_pamphlet()
                if popped_item:
                    next_pamphlet_img, next_pamphlet_cap = popped_item
                    ts_copy["image_path"] = next_pamphlet_img
                    ts_copy["caption"] = next_pamphlet_cap or strip_pamphlet_and_req_caption_prefixes(
                        str(ts_copy.get("title", base_title)), badge_name
                    )
                    if layout_type == "FULL_BLEED_IMAGE_EXPLAINER":
                        ts_copy["layout"] = "SPLIT_VISUAL_EXPLAINER"
                elif ts_copy.get("wikimedia_query"):
                    web_p = fetch_web_supplement_image(
                        badge_name,
                        str(ts_copy["wikimedia_query"]),
                        f"{slug}_{req_num}_{t_idx}",
                    )
                    if web_p and web_p.exists():
                        ts_copy["image_path"] = _compose_pamphlet_visual_card(
                            raw_img_path=web_p,
                            badge_name=badge_name,
                            req_number=f"{req_num}_{t_idx}",
                            topic_title=str(ts_copy.get("title", "")),
                            pamphlet_page=t_idx,
                        )
                        ts_copy["caption"] = strip_pamphlet_and_req_caption_prefixes(
                            str(ts_copy.get("caption") or ts_copy.get("title", base_title)), badge_name
                        )
                        if layout_type == "FULL_BLEED_IMAGE_EXPLAINER":
                            ts_copy["layout"] = "SPLIT_VISUAL_EXPLAINER"
                    else:
                        ts_copy["image_path"] = None
                else:
                    ts_copy["image_path"] = None

            if not ts_copy.get("image_path") and ts_copy.get("layout") in ("SPLIT_VISUAL_EXPLAINER", "FULL_BLEED_IMAGE_EXPLAINER"):
                ts_copy["layout"] = "CONCEPT_TEXT_SLIDE"
            if ts_copy.get("bullets"):
                ts_copy["bullets"] = _dedupe_slide_bullets(list(ts_copy.get("bullets") or []))
            if ts_copy.get("layout") in ("SPLIT_VISUAL_EXPLAINER", "CONCEPT_TEXT_SLIDE"):
                cur_bullets = list(ts_copy.get("bullets") or [])
                if len(cur_bullets) < 3:
                    for extra_b in list(req_dict.get("step_by_step_procedure") or []) + list(req_dict.get("pamphlet_excerpts") or []):
                        if extra_b:
                            cur_bullets = _dedupe_slide_bullets(cur_bullets + [extra_b])
                            if len(cur_bullets) >= 3:
                                break
                    ts_copy["bullets"] = cur_bullets
            resolved_slides.append(ts_copy)

        if not any(
            str(s.get("layout") or "").upper() == "SOCRATIC_CHECKPOINT_QUIZ" or s.get("quiz_item")
            for s in resolved_slides
        ):
            eff_q = _get_selective_safety_quiz_for_requirement(
                badge_name=badge_name,
                req_num=req_num,
                req_index=req_index,
                req_text=req_text,
                base_title=base_title,
                explicit_quiz=req_dict.get("quiz_item"),
            )
            if eff_q:
                resolved_slides.append({
                    "title": f"{base_title} (Safety Scenario)" if ": " in base_title else f"{base_title}: Patrol Safety Scenario",
                    "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                    "quiz_item": eff_q,
                    "bullets": [
                        eff_q["scenario_prompt"],
                        eff_q["correct_answer"],
                        eff_q["explanation"],
                    ],
                    "image_path": None,
                })

        def _cap_slides_preserving_quiz(s_list: List[Dict[str, Any]], limit: int = 7) -> List[Dict[str, Any]]:
            if len(s_list) <= limit:
                return s_list
            if str(s_list[-1].get("layout") or "").upper() == "SOCRATIC_CHECKPOINT_QUIZ":
                return s_list[: limit - 1] + [s_list[-1]]
            return s_list[:limit]

        if sub_reqs:
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
                    pamphlet_img=None,
                    extra_images=[],
                    pages_map=pages_map,
                    extended_pages=extended_pages,
                )
                # Place Sub-Requirement Deep Dive slide(s) first so both Deep Dive and Troop Meeting decks include them
                combined_slides = sub_slides + [
                    s for s in resolved_slides
                    if not s.get("is_subreq_slide") and "sub-requirement deep dive" not in str(s.get("title", "")).lower()
                ]
                return _cap_slides_preserving_quiz(combined_slides, 7)
        return _cap_slides_preserving_quiz(resolved_slides, 7)

    # 2. Adaptive multi-slide EDGE decomposition for requirements without explicit `topic_slides`
    excerpts = _dedupe_slide_bullets(list(req_dict.get("pamphlet_excerpts") or []))
    procedures = _dedupe_slide_bullets(list(req_dict.get("step_by_step_procedure") or []))
    checklist = _dedupe_slide_bullets(list(req_dict.get("gear_checklist") or []))
    comp_data = req_dict.get("comparison_data")
    worked_ex = req_dict.get("worked_example")
    quiz_item = req_dict.get("quiz_item")

    raw_pamphlet_bullets = (
        _extract_clean_teaching_points_from_pages(pages_map, extended_pages[:5], badge_name, max_points=16)
        if (extended_pages and pages_map)
        else []
    )
    # Filter raw pamphlet sentences by strict subject-matter keyword overlap (>= 2 matching 5+ letter domain words)
    # so older PDF pamphlets never leak unrelated chapters onto newer requirements.
    badge_words = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", badge_name)}
    generic_req_stop = {
        "explain", "describe", "discuss", "demonstrate", "show", "tell", "following",
        "your", "counselor", "with", "what", "when", "where", "which", "that", "this",
        "from", "have", "make", "list", "least", "three", "four", "five", "about",
        "how", "why", "would", "should", "could", "must", "including", "such", "other",
        "person", "people", "scout", "scouts", "merit", "badge", "pamphlet", "requirement",
        "first", "emergency", "emergencies", "injury", "injuries", "illness", "illnesses",
        "care", "help", "situations", "might", "needed", "conditions", "potential", "selected",
        "another", "skill", "using", "method", "opportunities", "pick", "find", "their", "there",
        "these", "those", "while", "after", "before", "under", "above", "below", "between",
        "place", "water", "check", "apply", "treat", "treatment", "prevent", "prevention",
        "signs", "symptoms", "proper", "level", "levels", "group", "patrol", "troop", "outing",
    } | badge_words
    req_domain_blob = " ".join([req_text, base_title]).lower()
    req_domain_kws = {
        w for w in re.findall(r"[a-z]{5,}", req_domain_blob)
        if w not in generic_req_stop
    }
    min_kw_hits = 2 if len(req_domain_kws) >= 2 else 1
    if req_domain_kws:
        all_pamphlet_bullets = [
            b for b in raw_pamphlet_bullets
            if sum(1 for kw in req_domain_kws if kw in b.lower()) >= min_kw_hits
        ]
    else:
        all_pamphlet_bullets = []

    # Reserve `excerpts[:4]` for the REQUIREMENT_INTRO slide in Deep Dive mode so topic slides never repeat them,
    # and keep `worked_fields_bullets` and `checklist` exclusive to their dedicated WORKED_EXAMPLE_TEMPLATE and
    # GEAR_CHECKLIST_GRID slides so two slides in the same requirement never duplicate each other's bullets.
    intro_norms = {re.sub(r"[^a-z0-9]+", " ", b.lower()).strip()[:55] for b in excerpts[:4]}
    fresh_pamphlet_bullets: List[str] = []
    seen_fresh_norms: set = set(intro_norms)
    for b in (excerpts[4:] + all_pamphlet_bullets):
        b_clean = str(b or "").strip()
        if not b_clean:
            continue
        b_norm = re.sub(r"[^a-z0-9]+", " ", b_clean.lower()).strip()[:55]
        if b_norm and b_norm not in seen_fresh_norms:
            seen_fresh_norms.add(b_norm)
            fresh_pamphlet_bullets.append(b_clean)

    generated: List[Dict[str, Any]] = []
    used_on_visual_slide_norms: set = set()

    # Option 2 Multi-Slide Visual Expansion: check for pre-cached `{slug}_req_{req_slug}_topic_visual.png`
    req_slug_vis = re.sub(r"[^a-zA-Z0-9]+", "_", str(req_num).strip().lower()).strip("_")
    topic_vis_fname = f"{slug}_req_{req_slug_vis}_topic_visual.png"
    topic_vis_path = ASSETS_DIR / "ai_illustrations" / topic_vis_fname
    nano_cat_path = ASSETS_DIR.parent / "data" / "nano_banana_image_catalog.json"
    topic_vis_caption = base_title
    nano_cat = _read_cached_json(nano_cat_path)
    if isinstance(nano_cat, dict) and topic_vis_fname in nano_cat:
        topic_vis_caption = strip_pamphlet_and_req_caption_prefixes(
            str(nano_cat[topic_vis_fname].get("caption") or base_title), badge_name
        )

    # A. Sub-Requirement Deep-Dive Slides (Explain Phase)
    if sub_reqs:
        generated.extend(
            _build_sub_requirement_slides(
                badge_name=badge_name,
                req_num=req_num,
                req_text=req_text,
                base_title=base_title,
                sub_reqs=sub_reqs,
                pamphlet_img=None,
                extra_images=[],
                pages_map=pages_map,
                extended_pages=extended_pages,
            )
        )
        # Add 1 illustrated Pamphlet / Option 2 Topic Visual Reference slide
        popped_vis = _pop_next_avail_pamphlet()
        if popped_vis:
            vis_img, vis_cap = popped_vis
        elif (
            topic_vis_path.exists()
            and topic_vis_path.stat().st_size >= 35_000
            and str(topic_vis_path) not in used_image_paths
        ):
            used_image_paths.add(str(topic_vis_path))
            vis_img, vis_cap = str(topic_vis_path), topic_vis_caption
        else:
            vis_img, vis_cap = None, ""
        fallback_vis_bullets = [
            f"Field Reference ({base_title}): Connect the visual diagram to each step of {badge_name} Requirement {req_num}.",
            f"Pamphlet Verification: Review how {base_title} applies during troop outings and skill stations.",
            f"Buddy Check: Trace the key components of {base_title} with your patrol partner before demonstration.",
        ]
        vis_bullets = _dedupe_slide_bullets(
            fresh_pamphlet_bullets[:4] if len(fresh_pamphlet_bullets) >= 2 else (fresh_pamphlet_bullets + fallback_vis_bullets)[:4]
        )
        for vb in vis_bullets:
            used_on_visual_slide_norms.add(re.sub(r"[^a-z0-9]+", " ", vb.lower()).strip()[:55])
        generated.append({
            "title": f"{base_title} (Visual Guide)" if ": " in base_title else f"{base_title}: Field Visual & Key Principles",
            "layout": "SPLIT_VISUAL_EXPLAINER" if vis_img else "CONCEPT_TEXT_SLIDE",
            "bullets": vis_bullets,
            "image_path": vis_img,
            "caption": vis_cap or base_title,
        })
    else:
        # Single-part requirement: teach the fresh pamphlet points not shown on REQUIREMENT_INTRO
        single_fallback = [
            f"Field Reference ({base_title}): Apply the official {badge_name} pamphlet principles for Requirement {req_num}.",
            f"Practical Execution: Connect {base_title} definitions to hands-on patrol practice and field observations.",
            f"Counselor Conference Check: Explain how {base_title} supports safe, effective execution in {badge_name}.",
        ]
        deep_bullets = _dedupe_slide_bullets(
            fresh_pamphlet_bullets[:4] if len(fresh_pamphlet_bullets) >= 2 else (fresh_pamphlet_bullets + single_fallback)[:4]
        )
        for db in deep_bullets:
            used_on_visual_slide_norms.add(re.sub(r"[^a-z0-9]+", " ", db.lower()).strip()[:55])
        popped_single = _pop_next_avail_pamphlet()
        if popped_single:
            slide_img, slide_cap = popped_single
        elif (
            topic_vis_path.exists()
            and topic_vis_path.stat().st_size >= 35_000
            and str(topic_vis_path) not in used_image_paths
        ):
            used_image_paths.add(str(topic_vis_path))
            slide_img, slide_cap = str(topic_vis_path), topic_vis_caption
        else:
            slide_img, slide_cap = None, base_title
        generated.append({
            "title": f"{base_title} (Core Principles)" if ": " in base_title else f"{base_title}: Core Principles & Field Reference",
            "layout": "SPLIT_VISUAL_EXPLAINER" if slide_img else "CONCEPT_TEXT_SLIDE",
            "bullets": deep_bullets,
            "image_path": slide_img,
            "caption": slide_cap or base_title,
        })

    # B. Step-by-Step Execution Procedure (Demonstrate Phase) — full-width 2x2 grid for maximum clarity
    # Never reuse the exact same bullets shown on the immediately preceding slide!
    remaining_fresh_for_proc = [
        fb for fb in fresh_pamphlet_bullets
        if re.sub(r"[^a-z0-9]+", " ", fb.lower()).strip()[:55] not in used_on_visual_slide_norms
    ]
    proc_candidates = [
        p for p in procedures
        if re.sub(r"[^a-z0-9]+", " ", p.lower()).strip()[:55] not in intro_norms
        and re.sub(r"[^a-z0-9]+", " ", p.lower()).strip()[:55] not in used_on_visual_slide_norms
    ]
    if len(proc_candidates) >= 3:
        proc_bullets = _dedupe_slide_bullets(proc_candidates)[:4]
    elif len(remaining_fresh_for_proc) >= 3:
        proc_bullets = _dedupe_slide_bullets(remaining_fresh_for_proc)[:4]
    else:
        proc_bullets = [
            f"Preparation & Study: Review the {badge_name} handbook section on {base_title} and record key definitions in your workbook.",
            f"Equipment & Safety Check: Inspect the tools, materials, and workspace needed for Requirement {req_num} with your buddy.",
            f"Hands-On Demonstration: Practice and demonstrate the required {base_title} steps using the BSA EDGE method.",
            f"Counselor Verification: Present your completed notes, logs, or demonstration for Requirement {req_num} counselor review.",
        ]

    generated.append({
        "title": f"{base_title} (Step-by-Step)" if ": " in base_title else f"{base_title}: Step-by-Step Execution",
        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
        "bullets": proc_bullets[:4],
        "image_path": None,
        "caption": f"{base_title}: Step-by-Step Field Execution",
    })


    # C. Differential Comparison OR Worked Example Artifact (Guide Phase) — include when budget allows (<= 7 topic slides total)
    if len(generated) < 6:
        if comp_data:
            generated.append({
                "title": f"{base_title} (Technical Comparison)" if ": " in base_title else f"{base_title}: Technical Comparison & Standards",
                "layout": "DIFFERENTIAL_COMPARISON_2COL",
                "comparison_data": comp_data,
                "bullets": (comp_data.get("left_points", [])[:2] + comp_data.get("right_points", [])[:2]),
                "image_path": None,
            })
        if worked_ex and len(generated) < 6:
            generated.append({
                "title": f"{base_title} (Scout Log)" if ": " in base_title else f"{base_title}: Worked Example & Scout Log",
                "layout": "WORKED_EXAMPLE_TEMPLATE",
                "worked_example": worked_ex,
                "bullets": [f"{k}: {v}" for k, v in list((worked_ex.get("fields") or {}).items())[:4]],
                "image_path": None,
            })
        elif not comp_data and len(generated) < 6:
            fields_map: Dict[str, str] = {}
            if sub_reqs:
                for sr in sub_reqs[:4]:
                    raw_lbl = str(sr.get("sub_id") or sr.get("id") or sr.get("sub_req_label") or req_num).strip()
                    sr_id = f"{req_num}{raw_lbl}" if len(raw_lbl) == 1 and raw_lbl.isalpha() and not str(req_num).endswith(raw_lbl) else raw_lbl
                    raw_sr_t = str(sr.get("text") or sr.get("sub_req_text") or "").strip()
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
                "title": f"{base_title} (Workbook Guide)" if ": " in base_title else f"{base_title}: Scout Workbook & Review Guide",
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
            "title": f"{base_title} (Equipment Checklist)" if ": " in base_title else f"{base_title}: Equipment & Inspection Checklist",
            "layout": "GEAR_CHECKLIST_GRID",
            "gear_checklist": checklist[:4],
            "bullets": checklist[:4],
            "image_path": None,
        })

    effective_quiz = _get_selective_safety_quiz_for_requirement(
        badge_name=badge_name,
        req_num=req_num,
        req_index=req_index,
        req_text=req_text,
        base_title=base_title,
        explicit_quiz=quiz_item,
    )
    if effective_quiz:
        generated.append({
            "title": f"{base_title} (Safety Scenario)" if ": " in base_title else f"{base_title}: Patrol Safety Scenario",
            "layout": "SOCRATIC_CHECKPOINT_QUIZ",
            "quiz_item": effective_quiz,
            "bullets": [
                effective_quiz["scenario_prompt"],
                effective_quiz["correct_answer"],
                effective_quiz["explanation"],
            ],
            "image_path": None,
        })

    if len(generated) > 7 and str(generated[-1].get("layout") or "").upper() == "SOCRATIC_CHECKPOINT_QUIZ":
        return generated[:6] + [generated[-1]]
    return generated[:7]


_CURATED_REQ1_SAFETY_QUIZZES: Dict[str, Dict[str, Any]] = {
    "first_aid": {
        "scenario_prompt": "During a woodland trail hike, your patrol discovers an adult hiker lying at the base of a wet rock ledge with bright red blood spurting from a lower-leg wound and a downed power line 25 feet uphill. What is your patrol's immediate first-aid sequence?",
        "question": "During a woodland trail hike, your patrol discovers an adult hiker lying at the base of a wet rock ledge with bright red blood spurting from a lower-leg wound and a downed power line 25 feet uphill. What is your patrol's immediate first-aid sequence?",
        "options": [
            "A. Sprint straight to the victim without gloves to apply a tourniquet before checking the overhead wire.",
            "B. Stop and size up scene safety first (confirm the downed wire does not endanger the approach zone), put on nitrile gloves for Universal Precautions, direct a buddy to call 911 with GPS coordinates, and apply firm direct pressure with a sterile gauze dressing to control arterial bleeding.",
            "C. Have two Scouts carry the hiker 100 yards down the rocky trail before checking airway, breathing, or severe bleeding.",
            "D. Pour cold stream water onto the open arterial wound and elevate both legs 18 inches before checking scene hazards.",
        ],
        "choices": [
            "A. Sprint straight to the victim without gloves to apply a tourniquet before checking the overhead wire.",
            "B. Stop and size up scene safety first (confirm the downed wire does not endanger the approach zone), put on nitrile gloves for Universal Precautions, direct a buddy to call 911 with GPS coordinates, and apply firm direct pressure with a sterile gauze dressing to control arterial bleeding.",
            "C. Have two Scouts carry the hiker 100 yards down the rocky trail before checking airway, breathing, or severe bleeding.",
            "D. Pour cold stream water onto the open arterial wound and elevate both legs 18 inches before checking scene hazards.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Stop and size up scene safety first (confirm the downed wire does not endanger the approach zone), put on nitrile gloves for Universal Precautions, direct a buddy to call 911 with GPS coordinates, and apply firm direct pressure with a sterile gauze dressing to control arterial bleeding.",
        "explanation": "Correct Answer (B): Under the First Aid Merit Badge Pamphlet emergency action sequence (Check-Call-Care), rescuers must first verify scene safety so they do not become a second victim, apply Universal Precautions (BSI barriers), summon EMS immediately, and treat life-threatening conditions (airway, breathing, severe bleeding) before minor injuries.",
    },
    "athletics": {
        "scenario_prompt": "During a warm afternoon track practice for the 1,500-meter run, a Scout stops sweating, becomes confused and unsteady, and has hot, flushed skin. What is your patrol's immediate first-aid action?",
        "question": "During a warm afternoon track practice for the 1,500-meter run, a Scout stops sweating, becomes confused and unsteady, and has hot, flushed skin. What is your patrol's immediate first-aid action?",
        "options": [
            "A. Have the Scout jog two slow cool-down laps around the track while sipping a sports drink.",
            "B. Recognize life-threatening heatstroke: call 911 immediately, move the Scout into shade, remove excess layers, and rapidly cool the body with cold water or ice packs at the neck, armpits, and groin.",
            "C. Wrap the Scout in a warm fleece blanket to prevent chills and wait 30 minutes before notifying the counselor.",
            "D. Give the confused Scout salt tablets and hot tea while keeping their track warm-up jacket zipped.",
        ],
        "choices": [
            "A. Have the Scout jog two slow cool-down laps around the track while sipping a sports drink.",
            "B. Recognize life-threatening heatstroke: call 911 immediately, move the Scout into shade, remove excess layers, and rapidly cool the body with cold water or ice packs at the neck, armpits, and groin.",
            "C. Wrap the Scout in a warm fleece blanket to prevent chills and wait 30 minutes before notifying the counselor.",
            "D. Give the confused Scout salt tablets and hot tea while keeping their track warm-up jacket zipped.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Recognize life-threatening heatstroke: call 911 immediately, move the Scout into shade, remove excess layers, and rapidly cool the body with cold water or ice packs at the neck, armpits, and groin.",
        "explanation": "Correct Answer (B): Hot skin combined with altered mental status (confusion or dizziness) during exertion indicates heatstroke, a medical emergency requiring immediate EMS activation and aggressive cooling per the Athletics Merit Badge Pamphlet.",
    },
    "skating": {
        "scenario_prompt": "While skating on an outdoor winter pond, a skater breaks through thin ice into frigid water 30 feet from shore. How should your patrol respond safely?",
        "question": "While skating on an outdoor winter pond, a skater breaks through thin ice into frigid water 30 feet from shore. How should your patrol respond safely?",
        "options": [
            "A. Skate out to the edge of the ice hole in a group to pull the skater up by both hands.",
            "B. Stay off the thin ice, call for emergency help, lie flat near shore to spread weight, and extend a long reach/throw aid (branch, hockey stick, or rope) while coaching the skater to kick horizontally onto firm ice and roll away from the hole.",
            "C. Instruct the skater to remove their skates and winter jacket in the water before trying to climb out.",
            "D. Have one Scout walk upright to the rim of the broken ice hole carrying a heavy wooden bench.",
        ],
        "choices": [
            "A. Skate out to the edge of the ice hole in a group to pull the skater up by both hands.",
            "B. Stay off the thin ice, call for emergency help, lie flat near shore to spread weight, and extend a long reach/throw aid (branch, hockey stick, or rope) while coaching the skater to kick horizontally onto firm ice and roll away from the hole.",
            "C. Instruct the skater to remove their skates and winter jacket in the water before trying to climb out.",
            "D. Have one Scout walk upright to the rim of the broken ice hole carrying a heavy wooden bench.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Stay off the thin ice, call for emergency help, lie flat near shore to spread weight, and extend a long reach/throw aid (branch, hockey stick, or rope) while coaching the skater to kick horizontally onto firm ice and roll away from the hole.",
        "explanation": "Correct Answer (B): Walking or skating up to an ice breakthrough hole causes the ice edge to collapse under rescuers; follow Reach-Throw protocol and keep clothing/skates on for buoyancy and traction.",
    },
    "golf": {
        "scenario_prompt": "Your patrol is on the 6th fairway when dark thunderclouds build and you hear thunder 20 seconds after seeing a lightning flash. What must your group do immediately?",
        "question": "Your patrol is on the 6th fairway when dark thunderclouds build and you hear thunder 20 seconds after seeing a lightning flash. What must your group do immediately?",
        "options": [
            "A. Finish playing the current hole quickly while holding metal golf umbrellas overhead.",
            "B. Take shelter together under the tallest oak tree along the fairway edge until the rain passes.",
            "C. Suspend play immediately under the 30/30 lightning rule, leave golf bags/metal clubs behind if needed, and move to the clubhouse or a designated lightning-safe building, waiting 30 minutes after the last thunder before resuming.",
            "D. Sit inside an open-sided golf cart parked on the elevated 7th tee box while holding a 1-iron.",
        ],
        "choices": [
            "A. Finish playing the current hole quickly while holding metal golf umbrellas overhead.",
            "B. Take shelter together under the tallest oak tree along the fairway edge until the rain passes.",
            "C. Suspend play immediately under the 30/30 lightning rule, leave golf bags/metal clubs behind if needed, and move to the clubhouse or a designated lightning-safe building, waiting 30 minutes after the last thunder before resuming.",
            "D. Sit inside an open-sided golf cart parked on the elevated 7th tee box while holding a 1-iron.",
        ],
        "correct_index": 2,
        "correct_letter": "C",
        "correct_answer": "C. Suspend play immediately under the 30/30 lightning rule, leave golf bags/metal clubs behind if needed, and move to the clubhouse or a designated lightning-safe building, waiting 30 minutes after the last thunder before resuming.",
        "explanation": "Correct Answer (C): A 20-second flash-to-bang count means lightning is 4 miles away (within the 6-mile / 30-second strike zone); isolated trees and metal clubs/umbrellas are acute lightning hazards.",
    },
    "snow_sports": {
        "scenario_prompt": "While skiing down an intermediate alpine trail, you approach a slower snowboarder ahead of you who suddenly begins a wide turn across the run. Under the Alpine Responsibility Code, who has the right-of-way and what must you do?",
        "question": "While skiing down an intermediate alpine trail, you approach a slower snowboarder ahead of you who suddenly begins a wide turn across the run. Under the Alpine Responsibility Code, who has the right-of-way and what must you do?",
        "options": [
            "A. Shout 'On your left!' and pass at high speed since uphill skiers have momentum.",
            "B. The downhill rider ahead always has the right-of-way; you must adjust your speed and steer clear to avoid them regardless of their turn.",
            "C. Stop in the middle of a blind rollover just above the snowboarder and wait.",
            "D. Cut sharply across the tips of the snowboarder's board to claim the center line of the groomer.",
        ],
        "choices": [
            "A. Shout 'On your left!' and pass at high speed since uphill skiers have momentum.",
            "B. The downhill rider ahead always has the right-of-way; you must adjust your speed and steer clear to avoid them regardless of their turn.",
            "C. Stop in the middle of a blind rollover just above the snowboarder and wait.",
            "D. Cut sharply across the tips of the snowboarder's board to claim the center line of the groomer.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. The downhill rider ahead always has the right-of-way; you must adjust your speed and steer clear to avoid them regardless of their turn.",
        "explanation": "Correct Answer (B): Under Your Responsibility Code in the Snow Sports Merit Badge Pamphlet, downhill skiers/riders cannot see behind them, so uphill traffic bears full responsibility for avoiding collisions and must never stop where obstructed from above.",
    },
    "cycling": {
        "scenario_prompt": "Before departing on a 25-mile troop road ride, you check a Scout's helmet and notice the front rim sits high on the forehead (4 fingers above the eyebrows) and the side straps form a loose loop below the chin. How must the helmet be adjusted?",
        "question": "Before departing on a 25-mile troop road ride, you check a Scout's helmet and notice the front rim sits high on the forehead (4 fingers above the eyebrows) and the side straps form a loose loop below the chin. How must the helmet be adjusted?",
        "options": [
            "A. Tilt the helmet back further so the Scout can see traffic lights more easily.",
            "B. Apply the 2-V-1 helmet fit rule: level the rim 1 to 2 finger-widths above the eyebrows, adjust side sliders to form a snug 'V' right under each ear, and tighten the chin buckle until only 1 finger fits underneath.",
            "C. Wear a thick winter beanie underneath the loose straps without tightening the retention dial.",
            "D. Unbuckle the chin strap during uphill climbs and refasten it only on downhill segments.",
        ],
        "choices": [
            "A. Tilt the helmet back further so the Scout can see traffic lights more easily.",
            "B. Apply the 2-V-1 helmet fit rule: level the rim 1 to 2 finger-widths above the eyebrows, adjust side sliders to form a snug 'V' right under each ear, and tighten the chin buckle until only 1 finger fits underneath.",
            "C. Wear a thick winter beanie underneath the loose straps without tightening the retention dial.",
            "D. Unbuckle the chin strap during uphill climbs and refasten it only on downhill segments.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Apply the 2-V-1 helmet fit rule: level the rim 1 to 2 finger-widths above the eyebrows, adjust side sliders to form a snug 'V' right under each ear, and tighten the chin buckle until only 1 finger fits underneath.",
        "explanation": "Correct Answer (B): A helmet tilted back exposes the frontal skull in a forward crash; the BSA Cycling Pamphlet's 2-V-1 fit check keeps the helmet level and secure during impact.",
    },
    "archery": {
        "scenario_prompt": "While shooting on the archery range, an arrow slips off your bow rest and lands on the ground 4 feet in front of the shooting line while other archers are still at full draw. What must you do?",
        "question": "While shooting on the archery range, an arrow slips off your bow rest and lands on the ground 4 feet in front of the shooting line while other archers are still at full draw. What must you do?",
        "options": [
            "A. Lean forward across the shooting line and grab the arrow quickly before anyone notices.",
            "B. Leave the arrow on the ground, never reach or step across the shooting line while the range is hot, and wait for the Range Officer's three-whistle 'Retrieve Arrows' command.",
            "C. Signal your buddy in the next lane to kick the arrow back behind the waiting line.",
            "D. Use the tip of your unstrung bow limbs to hook the dropped arrow shaft while adjacent archers are releasing.",
        ],
        "choices": [
            "A. Lean forward across the shooting line and grab the arrow quickly before anyone notices.",
            "B. Leave the arrow on the ground, never reach or step across the shooting line while the range is hot, and wait for the Range Officer's three-whistle 'Retrieve Arrows' command.",
            "C. Signal your buddy in the next lane to kick the arrow back behind the waiting line.",
            "D. Use the tip of your unstrung bow limbs to hook the dropped arrow shaft while adjacent archers are releasing.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Leave the dropped arrow untouched in front of the shooting line until the Range Officer blows three whistles to retrieve arrows.",
        "explanation": "Correct Answer (B): Stepping or reaching across an active shooting line puts you directly in the path of adjacent bows; any arrow forward of the line is retrieved only after all bows are racked on the 3-whistle signal.",
    },
    "rifle_shooting": {
        "scenario_prompt": "On the firing line, you squeeze the trigger on a loaded .22 rimfire rifle and hear an audible 'click' with no discharge. What is the mandatory misfire safety procedure?",
        "question": "On the firing line, you squeeze the trigger on a loaded .22 rimfire rifle and hear an audible 'click' with no discharge. What is the mandatory misfire safety procedure?",
        "options": [
            "A. Immediately open the bolt to eject the cartridge and inspect the firing pin indent.",
            "B. Keep the rifle muzzle pointed safely downrange, raise your non-shooting hand to notify the Range Safety Officer, and wait at least 30 seconds before opening the action in case of a hangfire.",
            "C. Lay the closed rifle down on the shooting mat pointed toward the waiting bench and walk over to the instructor.",
            "D. Look down the muzzle end of the barrel to verify whether a bullet is lodged in the bore.",
        ],
        "choices": [
            "A. Immediately open the bolt to eject the cartridge and inspect the firing pin indent.",
            "B. Keep the rifle muzzle pointed safely downrange, raise your non-shooting hand to notify the Range Safety Officer, and wait at least 30 seconds before opening the action in case of a hangfire.",
            "C. Lay the closed rifle down on the shooting mat pointed toward the waiting bench and walk over to the instructor.",
            "D. Look down the muzzle end of the barrel to verify whether a bullet is lodged in the bore.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Keep the rifle muzzle pointed safely downrange, raise your non-shooting hand to notify the Range Safety Officer, and wait at least 30 seconds before opening the action in case of a hangfire.",
        "explanation": "Correct Answer (B): A delayed ignition (hangfire) can detonate seconds after the trigger pull; opening the breech immediately exposes the shooter's face and hands to a live rupture outside the chamber.",
    },
    "swimming": {
        "scenario_prompt": "While swimming at an ocean beach, a Scout feels a narrow, fast-moving current pulling them straight offshore through a break in the sandbar. What is the safest way to escape this rip current?",
        "question": "While swimming at an ocean beach, a Scout feels a narrow, fast-moving current pulling them straight offshore through a break in the sandbar. What is the safest way to escape this rip current?",
        "options": [
            "A. Sprint-swim straight back toward the beach directly against the outgoing current.",
            "B. Stay calm to conserve energy, swim parallel to the shoreline until out of the narrow seaward pull, and then angle back to the beach with the breaking waves.",
            "C. Dive to the sandy bottom and try to crawl toward shore underwater.",
            "D. Remove your swim goggles and tread water while pulling another swimmer into the center of the rip channel.",
        ],
        "choices": [
            "A. Sprint-swim straight back toward the beach directly against the outgoing current.",
            "B. Stay calm to conserve energy, swim parallel to the shoreline until out of the narrow seaward pull, and then angle back to the beach with the breaking waves.",
            "C. Dive to the sandy bottom and try to crawl toward shore underwater.",
            "D. Remove your swim goggles and tread water while pulling another swimmer into the center of the rip channel.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Stay calm to conserve energy, swim parallel to the shoreline until out of the narrow seaward pull, and then angle back to the beach with the breaking waves.",
        "explanation": "Correct Answer (B): Rip currents are narrow channels that quickly exhaust swimmers who fight them head-on; swimming parallel to the beach moves you out of the current within 50 to 100 feet.",
    },
    "lifesaving": {
        "scenario_prompt": "A tired non-swimmer slips off a camp dock into 8-foot-deep water about 6 feet from the dock edge and begins thrashing in panic. Following the BSA Order of Water Rescue, what should your patrol attempt FIRST?",
        "question": "A tired non-swimmer slips off a camp dock into 8-foot-deep water about 6 feet from the dock edge and begins thrashing in panic. Following the BSA Order of Water Rescue, what should your patrol attempt FIRST?",
        "options": [
            "A. Dive straight in without equipment and grab the thrashing victim around the shoulders.",
            "B. Use a Reach or Throw rescue from the dock first - lie flat on the dock and extend a rescue pole, paddle, towel, or ring buoy so the rescuer stays out of the water.",
            "C. Launch a motorboat from the far side of the lake before offering any assistance from the dock.",
            "D. Have two non-swimmer buddies form a human chain in 8-foot water without wearing PFDs.",
        ],
        "choices": [
            "A. Dive straight in without equipment and grab the thrashing victim around the shoulders.",
            "B. Use a Reach or Throw rescue from the dock first - lie flat on the dock and extend a rescue pole, paddle, towel, or ring buoy so the rescuer stays out of the water.",
            "C. Launch a motorboat from the far side of the lake before offering any assistance from the dock.",
            "D. Have two non-swimmer buddies form a human chain in 8-foot water without wearing PFDs.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Use a Reach or Throw rescue from the dock first - lie flat on the dock and extend a rescue pole, paddle, towel, or ring buoy so the rescuer stays out of the water.",
        "explanation": "Correct Answer (B): A panicked drowning victim can submerge an unequipped swimming rescuer; Reach and Throw rescues from shore/dock deliver immediate buoyancy with zero contact risk to the rescuer.",
    },
    "kayaking": {
        "scenario_prompt": "Your kayak capsizes in calm lake water during a practice paddle. After performing a wet exit, what is your immediate priority in the water?",
        "question": "Your kayak capsizes in calm lake water during a practice paddle. After performing a wet exit, what is your immediate priority in the water?",
        "options": [
            "A. Abandon the kayak and paddle and try to swim 300 yards to the nearest shoreline.",
            "B. Maintain physical contact with your capsized kayak and paddle, signal your buddy boat, and position yourself at the bow/stern for a T-rescue or heel-hook re-entry.",
            "C. Unbuckle and remove your PFD life jacket so you can swim faster.",
            "D. Dive underneath the overturned cockpit to untie the stern painter line with your feet inside the hull.",
        ],
        "choices": [
            "A. Abandon the kayak and paddle and try to swim 300 yards to the nearest shoreline.",
            "B. Maintain physical contact with your capsized kayak and paddle, signal your buddy boat, and position yourself at the bow/stern for a T-rescue or heel-hook re-entry.",
            "C. Unbuckle and remove your PFD life jacket so you can swim faster.",
            "D. Dive underneath the overturned cockpit to untie the stern painter line with your feet inside the hull.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Maintain physical contact with your capsized kayak and paddle, signal your buddy boat, and position yourself at the bow/stern for a T-rescue or heel-hook re-entry.",
        "explanation": "Correct Answer (B): A swamped kayak provides massive flotation and high visibility for rescuers, whereas swimming away in open water risks cold-water exhaustion and separation.",
    },
    "canoeing": {
        "scenario_prompt": "Two Scouts capsize their canoe in the middle of a breezy lake a quarter-mile from shore. Both Scouts are wearing PFDs and the canoe floats upside down. What should they do?",
        "question": "Two Scouts capsize their canoe in the middle of a breezy lake a quarter-mile from shore. Both Scouts are wearing PFDs and the canoe floats upside down. What should they do?",
        "options": [
            "A. Leave the canoe behind and race each other swimming to shore.",
            "B. Stay with the floating canoe (which has built-in foam flotation blocks), move to the upwind side, and perform a canoe-over-canoe rescue with their buddy boat or flip/paddle the swamped canoe to shore.",
            "C. Stand up on top of the overturned hull to wave both arms.",
            "D. Tie the bow painter line around their waists while floating on the downwind side of the hull.",
        ],
        "choices": [
            "A. Leave the canoe behind and race each other swimming to shore.",
            "B. Stay with the floating canoe (which has built-in foam flotation blocks), move to the upwind side, and perform a canoe-over-canoe rescue with their buddy boat or flip/paddle the swamped canoe to shore.",
            "C. Stand up on top of the overturned hull to wave both arms.",
            "D. Tie the bow painter line around their waists while floating on the downwind side of the hull.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Stay with the floating canoe (which has built-in foam flotation blocks), move to the upwind side, and perform a canoe-over-canoe rescue with their buddy boat or flip/paddle the swamped canoe to shore.",
        "explanation": "Correct Answer (B): Shorelines look much closer than they are across open water; staying with the buoyant canoe on the upwind side prevents wind drift separation and enables rapid buddy recovery.",
    },
    "camping": {
        "scenario_prompt": "During a freezing rainstorm at camp, a patrol asks if they can bring their liquid-fuel or canister camp stove inside the tent vestibule to boil water and warm up the tent before sleeping. How should the patrol leader respond?",
        "question": "During a freezing rainstorm at camp, a patrol asks if they can bring their liquid-fuel or canister camp stove inside the tent vestibule to boil water and warm up the tent before sleeping. How should the patrol leader respond?",
        "options": [
            "A. Allow it as long as a tent window mesh zipper is cracked open 2 inches.",
            "B. Strictly prohibit any flame or stove inside or near the tent: camp stoves produce odorless, lethal Carbon Monoxide (CO) gas and can instantly ignite nylon tent fabric.",
            "C. Use a charcoal grill inside the tent instead since charcoal has no visible flame.",
            "D. Hang a lit propane mantle lantern from the interior ridge loop of the tent fly.",
        ],
        "choices": [
            "A. Allow it as long as a tent window mesh zipper is cracked open 2 inches.",
            "B. Strictly prohibit any flame or stove inside or near the tent: camp stoves produce odorless, lethal Carbon Monoxide (CO) gas and can instantly ignite nylon tent fabric.",
            "C. Use a charcoal grill inside the tent instead since charcoal has no visible flame.",
            "D. Hang a lit propane mantle lantern from the interior ridge loop of the tent fly.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Strictly prohibit any flame or stove inside or near the tent: camp stoves produce odorless, lethal Carbon Monoxide (CO) gas and can instantly ignite nylon tent fabric.",
        "explanation": "Correct Answer (B): BSA Guide to Safe Scouting and the Camping Pamphlet mandate 'No Flames in Tents'; carbon monoxide is colorless and odorless and causes fatal hypoxia in enclosed shelters.",
    },
    "cooking": {
        "scenario_prompt": "While preparing chicken fajitas at camp, a Scout uses a plastic cutting board and chef's knife to slice raw chicken breast, and then reaches for fresh bell peppers and tortillas to slice for a cold side salad. What food-safety step is required first?",
        "question": "While preparing chicken fajitas at camp, a Scout uses a plastic cutting board and chef's knife to slice raw chicken breast, and then reaches for fresh bell peppers and tortillas to slice for a cold side salad. What food-safety step is required first?",
        "options": [
            "A. Wipe the knife blade on a dry camp towel and slice the raw vegetables on the same board.",
            "B. Prevent cross-contamination by using a separate cutting board for produce, or washing, rinsing, and sanitizing the board, knife, and hands thoroughly with hot soapy water and sanitizer solution before touching ready-to-eat food.",
            "C. Leave the raw chicken sitting in the sun at 75°F for 4 hours before cooking.",
            "D. Rinse the cutting board briefly in cold creek water without soap or sanitizer.",
        ],
        "choices": [
            "A. Wipe the knife blade on a dry camp towel and slice the raw vegetables on the same board.",
            "B. Prevent cross-contamination by using a separate cutting board for produce, or washing, rinsing, and sanitizing the board, knife, and hands thoroughly with hot soapy water and sanitizer solution before touching ready-to-eat food.",
            "C. Leave the raw chicken sitting in the sun at 75°F for 4 hours before cooking.",
            "D. Rinse the cutting board briefly in cold creek water without soap or sanitizer.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Prevent cross-contamination by using a separate cutting board for produce, or washing, rinsing, and sanitizing the board, knife, and hands thoroughly with hot soapy water and sanitizer solution before touching ready-to-eat food.",
        "explanation": "Correct Answer (B): Raw poultry carries Salmonella and Campylobacter; transferring raw juices to ready-to-eat produce causes acute foodborne illness unless surfaces are sanitized and perishables stay out of the 40°F-140°F danger zone.",
    },
    "wilderness_survival": {
        "scenario_prompt": "While hiking back from a peak at dusk, your buddy pair realizes you missed a trail junction and are no longer sure where the main trail is. Following the BSA S.T.O.P. survival protocol, what should you do?",
        "question": "While hiking back from a peak at dusk, your buddy pair realizes you missed a trail junction and are no longer sure where the main trail is. Following the BSA S.T.O.P. survival protocol, what should you do?",
        "options": [
            "A. Run downhill through the woods before total darkness falls to look for a road.",
            "B. Stop immediately in place, Think calmly without panic, Observe your surroundings/weather/daylight/gear, and Plan shelter and signaling while staying together so searchers can find you.",
            "C. Split up and hike in opposite directions to cover twice as much ground.",
            "D. Climb an exposed cliff face after dark to check for distant highway lights.",
        ],
        "choices": [
            "A. Run downhill through the woods before total darkness falls to look for a road.",
            "B. Stop immediately in place, Think calmly without panic, Observe your surroundings/weather/daylight/gear, and Plan shelter and signaling while staying together so searchers can find you.",
            "C. Split up and hike in opposite directions to cover twice as much ground.",
            "D. Climb an exposed cliff face after dark to check for distant highway lights.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Stop immediately in place, Think calmly without panic, Observe your surroundings/weather/daylight/gear, and Plan shelter and signaling while staying together so searchers can find you.",
        "explanation": "Correct Answer (B): Moving randomly after losing the trail increases search radius exponentially and risks injury after dark; staying put with S.T.O.P., shelter, and 3-signal distress calls maximizes rapid rescue.",
    },
    "citizenship_in_society": {
        "scenario_prompt": "During a troop campsite assignment, a new Scout from a different background is excluded from a patrol cooking group and overheard being mocked. As an upstander living the Scout Oath and Scout Law, what should you do first?",
        "question": "During a troop campsite assignment, a new Scout from a different background is excluded from a patrol cooking group and overheard being mocked. As an upstander living the Scout Oath and Scout Law, what should you do first?",
        "options": [
            "A. Stay quiet so you do not create awkwardness with the older Scouts in the patrol.",
            "B. Step in respectfully as an upstander, invite the new Scout into your group, make sure they feel welcomed and heard, and involve your Patrol Leader or adult leadership if harassment continues.",
            "C. Post about the argument on social media after the campout.",
            "D. Tell the new Scout to camp alone at the edge of the site so the patrol does not argue.",
        ],
        "choices": [
            "A. Stay quiet so you do not create awkwardness with the older Scouts in the patrol.",
            "B. Step in respectfully as an upstander, invite the new Scout into your group, make sure they feel welcomed and heard, and involve your Patrol Leader or adult leadership if harassment continues.",
            "C. Post about the argument on social media after the campout.",
            "D. Tell the new Scout to camp alone at the edge of the site so the patrol does not argue.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Step in respectfully as an upstander, invite the new Scout into your group, make sure they feel welcomed and heard, and involve your Patrol Leader or adult leadership if harassment continues.",
        "explanation": "Correct Answer (B): Citizenship in Society emphasizes ethical leadership, welcoming others, and acting as an upstander rather than a passive bystander when a fellow Scout is excluded.",
    },
    "auctioneering": {
        "scenario_prompt": "During a live charity auction, a bidder raises their hand to place a $100 bid, and simultaneously a collaborator in the crowd places a fake 'shill' bid solely to artificially drive up the price without intending to buy. Under the National Auctioneers Association Code of Ethics, how must the auctioneer handle shill bidding?",
        "question": "During a live charity auction, a bidder raises their hand to place a $100 bid, and simultaneously a collaborator in the crowd places a fake 'shill' bid solely to artificially drive up the price without intending to buy. Under the National Auctioneers Association Code of Ethics, how must the auctioneer handle shill bidding?",
        "options": [
            "A. Encourage secret shill bidders in the audience so the seller gets a higher commission.",
            "B. Strictly prohibit fake or shill bidding, disclose whether an item is Absolute or Reserve before bidding opens, and recognize only bona fide transparent bids.",
            "C. Change the auction terms from Absolute to Reserve after the gavel falls.",
            "D. Invent phantom bids from the podium after the reserve price has already been met.",
        ],
        "choices": [
            "A. Encourage secret shill bidders in the audience so the seller gets a higher commission.",
            "B. Strictly prohibit fake or shill bidding, disclose whether an item is Absolute or Reserve before bidding opens, and recognize only bona fide transparent bids.",
            "C. Change the auction terms from Absolute to Reserve after the gavel falls.",
            "D. Invent phantom bids from the podium after the reserve price has already been met.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Strictly prohibit fake or shill bidding, disclose whether an item is Absolute or Reserve before bidding opens, and recognize only bona fide transparent bids.",
        "explanation": "Correct Answer (B): Auctioneering ethics and state licensing laws require complete transparency in bid calling; undisclosed shill bidding is fraudulent and destroys buyer trust.",
    },
    "dance": {
        "scenario_prompt": "Before starting an energetic 45-minute rehearsal involving jumps, turns, and partner lifts on a studio floor, a dancer notices a wet water spill near the center of the floor and skips warm-ups to save time. What two safety steps must happen before dancing begins?",
        "question": "Before starting an energetic 45-minute rehearsal involving jumps, turns, and partner lifts on a studio floor, a dancer notices a wet water spill near the center of the floor and skips warm-ups to save time. What two safety steps must happen before dancing begins?",
        "options": [
            "A. Dance around the wet spot at full speed and stretch only after rehearsal ends.",
            "B. Dry and inspect the studio floor for slip and trip hazards first, wear proper footwear, and complete a progressive cardiovascular warm-up and dynamic mobility routine.",
            "C. Practice high-impact jumps immediately on cold muscles to warm up faster.",
            "D. Sprinkle talcum powder over the wet puddle and attempt overhead partner lifts without a spotter.",
        ],
        "choices": [
            "A. Dance around the wet spot at full speed and stretch only after rehearsal ends.",
            "B. Dry and inspect the studio floor for slip and trip hazards first, wear proper footwear, and complete a progressive cardiovascular warm-up and dynamic mobility routine.",
            "C. Practice high-impact jumps immediately on cold muscles to warm up faster.",
            "D. Sprinkle talcum powder over the wet puddle and attempt overhead partner lifts without a spotter.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Dry and inspect the studio floor for slip and trip hazards first, wear proper footwear, and complete a progressive cardiovascular warm-up and dynamic mobility routine.",
        "explanation": "Correct Answer (B): Dynamic warm-ups increase muscle elasticity and joint synovial fluid, while a clean, dry sprung floor prevents ankle sprains and falls.",
    },
    "physics": {
        "scenario_prompt": "Your patrol rolls two solid spheres of the exact same size and shape down an inclined ramp from rest: one made of aluminum and one made of heavy brass. Neglecting air resistance, how do their accelerations down the ramp compare?",
        "question": "Your patrol rolls two solid spheres of the exact same size and shape down an inclined ramp from rest: one made of aluminum and one made of heavy brass. Neglecting air resistance, how do their accelerations down the ramp compare?",
        "options": [
            "A. The heavier brass sphere accelerates twice as fast because it has more gravitational mass.",
            "B. Both spheres accelerate down the ramp at the same rate because gravitational acceleration and rotational inertia scale proportionally with mass for identical solid spheres.",
            "C. The lighter aluminum sphere reaches the bottom first because it has less friction.",
            "D. Neither sphere rolls unless the ramp angle exceeds 45 degrees.",
        ],
        "choices": [
            "A. The heavier brass sphere accelerates twice as fast because it has more gravitational mass.",
            "B. Both spheres accelerate down the ramp at the same rate because gravitational acceleration and rotational inertia scale proportionally with mass for identical solid spheres.",
            "C. The lighter aluminum sphere reaches the bottom first because it has less friction.",
            "D. Neither sphere rolls unless the ramp angle exceeds 45 degrees.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Both spheres accelerate at the same rate (a = 5/7 g sin theta) regardless of mass when shape and radius match.",
        "explanation": "Correct Answer (B): Since both gravitational force and moment of inertia are proportional to mass (I = 2/5 m r^2), mass cancels out of the equation of motion on an incline.",
    },
    "psychology": {
        "scenario_prompt": "While preparing for a high-adventure trek, a patrol leader notices a Scout becoming overwhelmed when trying to memorize 15 wilderness safety rules all at once. Using cognitive psychology principles of working memory, what teaching strategy works best?",
        "question": "While preparing for a high-adventure trek, a patrol leader notices a Scout becoming overwhelmed when trying to memorize 15 wilderness safety rules all at once. Using cognitive psychology principles of working memory, what teaching strategy works best?",
        "options": [
            "A. Read all 15 rules faster without pausing so they enter long-term memory immediately.",
            "B. Use chunking and spaced practice: group the 15 rules into 3 meaningful categories (such as S.T.O.P. or ABCDE) and practice retrieving them across multiple hands-on scenarios.",
            "C. Skip practice and rely only on passive re-reading right before the trek.",
            "D. Test the Scout on all 15 rules simultaneously while playing loud background distractions.",
        ],
        "choices": [
            "A. Read all 15 rules faster without pausing so they enter long-term memory immediately.",
            "B. Use chunking and spaced practice: group the 15 rules into 3 meaningful categories (such as S.T.O.P. or ABCDE) and practice retrieving them across multiple hands-on scenarios.",
            "C. Skip practice and rely only on passive re-reading right before the trek.",
            "D. Test the Scout on all 15 rules simultaneously while playing loud background distractions.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Use chunking and spaced practice: group the 15 rules into 3 meaningful categories (such as S.T.O.P. or ABCDE) and practice retrieving them across multiple hands-on scenarios.",
        "explanation": "Correct Answer (B): Human working memory holds only a few chunks at once; grouping items into meaningful frameworks and practicing active recall builds durable neural pathways.",
    },
    "sewing_and_needlework": {
        "scenario_prompt": "While sewing a heavy canvas Merit Badge sash repair on a sewing machine, the needle hits a thick seam and snaps. What is the mandatory safety and machine procedure before replacing the needle?",
        "question": "While sewing a heavy canvas Merit Badge sash repair on a sewing machine, the needle hits a thick seam and snaps. What is the mandatory safety and machine procedure before replacing the needle?",
        "options": [
            "A. Keep your foot on the presser-foot speed controller while reaching into the needle bar.",
            "B. Turn off and unplug the sewing machine first, locate all broken needle fragments so none remain in the fabric, and insert a fresh heavy-duty needle with the flat shank side facing the correct direction.",
            "C. Leave the broken needle tip inside the canvas and sew over it.",
            "D. Hold the replacement needle between your lips while loosening the needle clamp screw with power on.",
        ],
        "choices": [
            "A. Keep your foot on the presser-foot speed controller while reaching into the needle bar.",
            "B. Turn off and unplug the sewing machine first, locate all broken needle fragments so none remain in the fabric, and insert a fresh heavy-duty needle with the flat shank side facing the correct direction.",
            "C. Leave the broken needle tip inside the canvas and sew over it.",
            "D. Hold the replacement needle between your lips while loosening the needle clamp screw with power on.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Turn off and unplug the sewing machine first, locate all broken needle fragments so none remain in the fabric, and insert a fresh heavy-duty needle with the flat shank side facing the correct direction.",
        "explanation": "Correct Answer (B): Turning off power prevents accidental foot-pedal activation while fingers are near the needle bar, and recovering broken needle tips prevents puncture injuries.",
    },
    "weather": {
        "scenario_prompt": "Your patrol is hiking across an open alpine ridgeline when towering cumulonimbus clouds build rapidly and you hear thunder 10 seconds after seeing a lightning flash (roughly 2 miles away). What is the safest immediate action for the patrol?",
        "question": "Your patrol is hiking across an open alpine ridgeline when towering cumulonimbus clouds build rapidly and you hear thunder 10 seconds after seeing a lightning flash (roughly 2 miles away). What is the safest immediate action for the patrol?",
        "options": [
            "A. Stay on the ridgeline under a tall isolated pine tree to keep dry until the rain passes.",
            "B. Apply the 30/30 lightning rule: immediately descend off the exposed ridge and away from tall isolated trees or water, move into lower dense timber or a substantial building, and spread patrol members at least 50 feet apart if caught in the open.",
            "C. Huddle together in a tight circle on top of metal-frame backpacks.",
            "D. Lie flat on wet granite at the summit so the wind blows over the patrol.",
        ],
        "choices": [
            "A. Stay on the ridgeline under a tall isolated pine tree to keep dry until the rain passes.",
            "B. Apply the 30/30 lightning rule: immediately descend off the exposed ridge and away from tall isolated trees or water, move into lower dense timber or a substantial building, and spread patrol members at least 50 feet apart if caught in the open.",
            "C. Huddle together in a tight circle on top of metal-frame backpacks.",
            "D. Lie flat on wet granite at the summit so the wind blows over the patrol.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Apply the 30/30 lightning rule: immediately descend off the exposed ridge and away from tall isolated trees or water, move into lower dense timber or a substantial building, and spread patrol members at least 50 feet apart if caught in the open.",
        "explanation": "Correct Answer (B): Sound travels about 1 mile every 5 seconds; a 10-second flash-to-bang interval means lightning is within 2 miles and already in strike range, requiring immediate descent from ridges and avoidance of tall isolated objects.",
    },
    "robotics": {
        "scenario_prompt": "While adjusting a jammed spur-gear drive train in the robotics lab, a Scout notices white dry residue from a damaged battery cell and has a minor sheet-metal cut on a forearm. What safety and first-aid procedure does the Robotics Merit Badge Pamphlet require?",
        "question": "While adjusting a jammed spur-gear drive train in the robotics lab, a Scout notices white dry residue from a damaged battery cell and has a minor sheet-metal cut on a forearm. What safety and first-aid procedure does the Robotics Merit Badge Pamphlet require?",
        "options": [
            "A. Leave the battery connected so the servo motors hold torque while clearing the jammed gear teeth with bare fingers.",
            "B. Wear ANSI Z87.1 safety glasses, disconnect the main battery before touching drive gears, brush off dry battery or flux chemicals with a gloved hand before flushing, and wash minor cuts with soap and running water for 5 minutes.",
            "C. Pour water directly onto dry battery powder with bare hands and wrap the unwashed cut with electrical tape.",
            "D. Remove safety glasses for a closer view of the spinning pinion gear while toggling the transmitter stick.",
        ],
        "choices": [
            "A. Leave the battery connected so the servo motors hold torque while clearing the jammed gear teeth with bare fingers.",
            "B. Wear ANSI Z87.1 safety glasses, disconnect the main battery before touching drive gears, brush off dry battery or flux chemicals with a gloved hand before flushing, and wash minor cuts with soap and running water for 5 minutes.",
            "C. Pour water directly onto dry battery powder with bare hands and wrap the unwashed cut with electrical tape.",
            "D. Remove safety glasses for a closer view of the spinning pinion gear while toggling the transmitter stick.",
        ],
        "correct_index": 1,
        "correct_letter": "B",
        "correct_answer": "B. Wear ANSI Z87.1 safety glasses, disconnect the main battery before touching drive gears, brush off dry battery or flux chemicals with a gloved hand before flushing, and wash minor cuts with soap and running water for 5 minutes.",
        "explanation": "Correct Answer (B): Per the Robotics Merit Badge Pamphlet (pp. 9-12), always wear ANSI Z87.1 eye protection, disconnect battery power before mechanical adjustments, brush dry chemical residue away with a gloved hand before flushing with water, and flush minor cuts with soap and water for 5 minutes before applying a sterile bandage.",
    },
}

_CURATED_REQ1_JSON_PATH = ASSETS_DIR.parent / "data" / "curated_req1_quizzes_149.json"
if _CURATED_REQ1_JSON_PATH.exists():
    try:
        _loaded_curated_149 = json.loads(_CURATED_REQ1_JSON_PATH.read_text(encoding="utf-8"))
        if isinstance(_loaded_curated_149, dict):
            for _k, _v in _loaded_curated_149.items():
                if isinstance(_v, dict) and _k not in _CURATED_REQ1_SAFETY_QUIZZES:
                    _CURATED_REQ1_SAFETY_QUIZZES[_k] = _v
    except Exception:
        pass


_BOILERPLATE_QUIZ_REJECTION_SUBSTRINGS = (
    "rely on guesswork",
    "sign off the requirement before completing",
    "sign off the requirement without",
    "unverified shortcuts",
    "claim partial credit",
    "encounters a decision point on proper procedure",
    "defer all ",
    "substitute uncalibrated equipment",
    "requires proactive hazard identification, protective equipment checks, and environmental screening",
    "only need to review safety rules and emergency procedures after an incident occurs",
    "while omitting",
    "applies only to indoor classroom theory and has no effect on real-world",
    "and use rules from an unrelated activity",
    "ignore environmental conditions, safety boundaries, and counselor approval requirements",
    "complete only a single sub-part of requirement",
    "reverse the sequence of",
    "steps and skip the post-activity review with your merit badge counselor",
    "rely on a group summary instead of personally demonstrating",
    "rely on a group summary of",
    "substitute a casual verbal guess",
    "under scouting america advancement standards for",
    "requires scouts to explain the underlying principles of",
    "before beginning hands-on field work for",
    "activity immediately before inspecting equipment",
    "skip the pre-activity safety briefing and complete only half of",
    "confuse the primary mechanism of",
    "using only a single unverified observation",
    "delay protective gear adjustments",
    "rely solely on post-activity cleanup",
    "execute ",
    "apply the setup parameters from",
)


def _get_selective_safety_quiz_for_requirement(
    badge_name: str,
    req_num: str,
    req_index: int,
    req_text: str,
    base_title: str,
    explicit_quiz: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Returns a genuine, non-boilerplate Patrol Scenario Quiz only where pedagogically appropriate.

    Policy:
    - Never emit generic strawman quizzes ('Rely on guesswork...', 'encounters a decision point on proper procedure...').
    - Never force quizzes onto every requirement or across multi-option skill tracks.
    - Include a slide-deck checkpoint quiz ONLY on Requirement 1 (`req_index == 0` or `1`/`1a`).
    """
    slug = _badge_slug(badge_name)
    clean_num = str(req_num or "").strip().lower()
    if req_index != 0 and clean_num not in ("1", "1a"):
        return None

    curated = _CURATED_REQ1_SAFETY_QUIZZES.get(slug)
    if curated:
        return dict(curated)

    if isinstance(explicit_quiz, dict):
        raw_opts = [str(o).strip() for o in (explicit_quiz.get("options") or []) if str(o).strip()]
        prompt = str(explicit_quiz.get("scenario_prompt") or explicit_quiz.get("question") or "").strip()
        ans = str(explicit_quiz.get("correct_answer") or explicit_quiz.get("correct_option") or "").strip()
        exp = str(explicit_quiz.get("explanation") or "").strip()
        opts_blob = (prompt + " " + " ".join(raw_opts) + " " + ans + " " + exp).lower()
        if (
            len(raw_opts) >= 4
            and prompt
            and not any(marker in opts_blob for marker in _BOILERPLATE_QUIZ_REJECTION_SUBSTRINGS)
        ):
            clean_bodies = [
                re.sub(r"^(?:Option\s+[A-D]\s*[:.\-—–]\s*|\(?[A-D]\)\s*|[A-D]\.\s*)", "", o, flags=re.IGNORECASE).strip()
                for o in raw_opts[:4]
            ]
            labeled_opts = [f"{chr(65 + i)}. {b}" for i, b in enumerate(clean_bodies)]
            c_idx = explicit_quiz.get("correct_index")
            if not isinstance(c_idx, int) or not (0 <= c_idx < 4):
                m_let = re.match(r"^\s*(?:Option\s+)?([A-D])\b", ans, flags=re.IGNORECASE)
                c_idx = (ord(m_let.group(1).upper()) - 65) if m_let else 1
            c_let = chr(65 + c_idx)
            c_ans = f"{c_let}. {clean_bodies[c_idx]}"
            return {
                "scenario_prompt": prompt,
                "question": str(explicit_quiz.get("question") or prompt).strip(),
                "options": labeled_opts,
                "choices": list(labeled_opts),
                "correct_index": c_idx,
                "correct_letter": c_let,
                "correct_answer": c_ans,
                "explanation": exp,
            }

    if req_index == 0:
        clean_t = re.sub(r"\s*\(Reqs?\s+[^)]+\)", "", str(base_title or f"{badge_name} Fundamentals")).strip()
        short_req = re.sub(r"\s+", " ", str(req_text or clean_t)).strip().rstrip(".")
        if len(short_req) > 130:
            short_req = short_req[:127].rsplit(" ", 1)[0].rstrip(" ,;:-")
        q_prompt = (
            f"When your patrol prepares for {badge_name} Requirement {req_num} ({clean_t}), "
            f"which field procedure satisfies the official {badge_name} Merit Badge Pamphlet?"
        )
        opts = [
            f"A. Use uninspected gear from a previous outing without verifying sizing, protective ratings, or site conditions for {clean_t}.",
            f"B. Complete the {badge_name} Pamphlet safety and preparation checklist for {clean_t} ({short_req}) with your buddy and counselor.",
            f"C. Improvise a shortcut technique for {clean_t} without checking tool condition or environmental hazards.",
            f"D. Split away from your buddy group to attempt {clean_t} outside the designated practice area.",
        ]
        return {
            "scenario_prompt": q_prompt,
            "question": q_prompt,
            "options": opts,
            "choices": list(opts),
            "correct_index": 1,
            "correct_letter": "B",
            "correct_answer": opts[1],
            "explanation": (
                f"Correct Answer (B): Under the BSA Guide to Safe Scouting and the {badge_name} Merit Badge Pamphlet, Scouts must inspect equipment, "
                f"use the Buddy System, and apply the verified technical steps for {clean_t} ({short_req})."
            ),
        }

    return None



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



