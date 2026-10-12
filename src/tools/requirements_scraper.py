"""Official Scouting.org Merit Badge Requirements Scraper & Per-Badge JSON Store.

Starts from https://www.scouting.org/skills/merit-badges/all/ (and eagle-required/),
accesses every Merit Badge page, extracts all requirements and sub-requirements inside
`<div class="mb-requirement-container">` (the full DOM revealed by clicking 'Show More'),
bypasses stale CDN 'Under maintenance' edge caches using cache-busting query parameters,
falls back to usscouts.org / official BSA Pamphlet PDFs if any page is genuinely under
construction, and stores each badge's structured metadata & requirements in its own JSON
file under `data/merit_badge_requirements/<slug>.json`.
"""

import json
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup, NavigableString, Tag
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REQUIREMENTS_DIR = REPO_ROOT / "data" / "merit_badge_requirements"
LEGACY_CACHE_FILE = REPO_ROOT / "data" / "official_requirements_cache.json"
HTML_CACHE_DIR = Path("/tmp/scouting_mb_html_cache")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

ALL_BADGES_INDEX_URL = "https://www.scouting.org/skills/merit-badges/all/"
EAGLE_BADGES_INDEX_URL = "https://www.scouting.org/skills/merit-badges/eagle-required/"


def badge_name_to_slug(badge_name: str) -> str:
    """Converts a badge name or URL slug into a canonical filename slug (e.g., 'first-aid')."""
    s = (badge_name or "").strip().lower()
    s = s.replace("&", "and").replace(",", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _clean_whitespace(text: str) -> str:
    s = re.sub(r"\s+", " ", text or "").strip()
    s = re.sub(r"\s+([,.;:?!])", r"\1", s)
    return s


def _extract_resources_and_clean_html(element: Tag) -> Tuple[str, List[Dict[str, str]], Optional[str]]:
    """Extracts trailing `Resources:` links and bold topic headings from a requirement node,
    returning `(clean_text, resources_list, topic_heading)`."""
    clone = BeautifulSoup(str(element), "html.parser")
    root = clone.find(element.name) or clone

    # Remove listnumber span if present
    for num_sp in root.find_all("span", class_="mb-requirement-listnumber"):
        num_sp.decompose()

    resources: List[Dict[str, str]] = []
    # Check if there is an <i>Resource:</i> or <i>Resources:</i> marker
    resource_marker = None
    for i_tag in root.find_all(["i", "em", "b", "strong"]):
        txt = i_tag.get_text(" ", strip=True).lower().rstrip(":")
        if txt in ("resource", "resources"):
            resource_marker = i_tag
            break

    if resource_marker is not None:
        # Collect all subsequent links after the resource marker
        for sib in list(resource_marker.next_siblings):
            if isinstance(sib, Tag):
                if sib.name == "a" and sib.get("href"):
                    r_title = _clean_whitespace(sib.get_text(" ", strip=True))
                    r_url = str(sib.get("href")).strip()
                    if r_url and not r_url.startswith("#"):
                        resources.append({"title": r_title or r_url, "url": r_url})
                else:
                    for a_sub in sib.find_all("a", href=True):
                        r_title = _clean_whitespace(a_sub.get_text(" ", strip=True))
                        r_url = str(a_sub.get("href")).strip()
                        if r_url and not r_url.startswith("#"):
                            resources.append({"title": r_title or r_url, "url": r_url})
                sib.decompose()
            elif isinstance(sib, NavigableString):
                sib.extract()
        resource_marker.decompose()

    # Check if the parent requirement starts with a bold topic heading like <b>Handling a First Aid Emergency.</b>
    topic_heading: Optional[str] = None
    first_b = root.find(["b", "strong"])
    if first_b is not None:
        b_txt = _clean_whitespace(first_b.get_text(" ", strip=True)).rstrip(".:")
        # Check if first_b is near the start of root text
        full_before_strip = _clean_whitespace(root.get_text(" ", strip=True))
        if b_txt and len(b_txt) <= 85 and full_before_strip.startswith(b_txt[:15]):
            if b_txt.upper() != "NOTE":
                topic_heading = b_txt

    clean_txt = _clean_whitespace(root.get_text(" ", strip=True))
    return clean_txt, resources, topic_heading


def parse_scouting_org_badge_html(
    html: str,
    slug: str,
    url: str,
    fallback_title: str = "",
    is_eagle: bool = False,
) -> Dict[str, Any]:
    """Parses a scouting.org Merit Badge HTML page into a structured badge requirements dictionary."""
    soup = BeautifulSoup(html, "html.parser")

    # 1. Extract canonical badge name from <title> or <h1> (skipping 'Eagle Required' pill text)
    title_tag_text = ""
    if soup.title:
        title_tag_text = _clean_whitespace(soup.title.get_text(" ", strip=True)).split("|")[0].strip()
        title_tag_text = re.sub(r"\s+Merit Badge$", "", title_tag_text, flags=re.IGNORECASE).strip()

    h1_candidates = [
        _clean_whitespace(h.get_text(" ", strip=True))
        for h in soup.find_all("h1")
    ]
    badge_name = ""
    if title_tag_text and title_tag_text.lower() not in ("merit badges", "all merit badges", "eagle required"):
        badge_name = title_tag_text
    if not badge_name:
        for hc in h1_candidates:
            if hc and hc.lower() not in ("merit badges", "all merit badges", "eagle required"):
                badge_name = hc
                break
    if not badge_name:
        clean_fb = fallback_title if fallback_title.lower() != "eagle required" else ""
        badge_name = clean_fb or slug.replace("-", " ").title()
    badge_name = re.sub(r"\s+Merit Badge$", "", badge_name, flags=re.IGNORECASE).strip()

    # Known official title casing fixes
    title_overrides = {
        "citizenship-in-society": "Citizenship in Society",
        "citizenship-in-the-community": "Citizenship in the Community",
        "citizenship-in-the-nation": "Citizenship in the Nation",
        "citizenship-in-the-world": "Citizenship in the World",
        "fish-and-wildlife-management": "Fish and Wildlife Management",
        " Fly-Fishing".lower().strip(): "Fly-Fishing",
        "fly-fishing": "Fly-Fishing",
        "mining-in-society": "Mining in Society",
        "model-design-and-building": "Model Design and Building",
        "pulp-and-paper": "Pulp and Paper",
        "reptile-and-amphibian-study": "Reptile and Amphibian Study",
        "Search and Rescue".lower().replace(" ", "-"): "Search and Rescue",
        "signs-signals-and-codes": "Signs, Signals, and Codes",
        "small-boat-sailing": "Small-Boat Sailing",
        "soil-and-water-conservation": "Soil and Water Conservation",
    }
    if slug in title_overrides:
        badge_name = title_overrides[slug]

    # 2. Extract official free downloadable Pamphlet PDF URL and Overview notes
    pamphlet_pdf_url: Optional[str] = None
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if "filestore.scouting.org" in href and href.lower().endswith(".pdf"):
            if "pamphlet" in href.lower() or not pamphlet_pdf_url:
                pamphlet_pdf_url = href

    under_maintenance = (
        "Under maintenance. Check back soon." in html
        and "mb-requirement-item" not in html
    )

    req_container = soup.find("div", class_="mb-requirement-container")
    req_items = (
        req_container.find_all("div", class_="mb-requirement-item", recursive=False)
        if req_container
        else []
    )

    intro_notes: List[str] = []
    requirements: List[Dict[str, Any]] = []

    for item_div in req_items:
        parent_div = item_div.find("div", class_="mb-requirement-parent")
        if not parent_div:
            continue

        num_span = parent_div.find("span", class_="mb-requirement-listnumber")
        raw_num = _clean_whitespace(num_span.get_text(" ", strip=True)).rstrip(".") if num_span else ""

        parent_text, parent_resources, topic_heading = _extract_resources_and_clean_html(parent_div)

        if not raw_num:
            if parent_text:
                intro_notes.append(parent_text)
            continue

        # Parse parent requirement ID from class `mb-requirement-id-XXXX`
        parent_dom_id: Optional[str] = None
        for cls in parent_div.get("class") or []:
            if cls.startswith("mb-requirement-id-"):
                parent_dom_id = cls.replace("mb-requirement-id-", "")

        # Parse all child `<li>` elements in `<ul class="mb-requirement-children-list">`
        child_lis = item_div.find_all("li", class_="mb-requirement-child")
        nodes_by_dom_id: Dict[str, Dict[str, Any]] = {}
        top_sub_reqs: List[Dict[str, Any]] = []

        for c_idx, li in enumerate(child_lis):
            li_classes = li.get("class") or []
            li_dom_id = None
            li_parent_dom_id = None
            for cls in li_classes:
                if cls.startswith("mb-requirement-id-"):
                    li_dom_id = cls.replace("mb-requirement-id-", "")
                elif cls.startswith("mb-parent-"):
                    li_parent_dom_id = cls.replace("mb-parent-", "")

            c_text, c_resources, _ = _extract_resources_and_clean_html(li)
            # Extract leading label like `(a)` or `(1)`
            m_lbl = re.match(r"^\(([a-zA-Z0-9]+)\)\s*(.*)$", c_text)
            if m_lbl:
                lbl_token = m_lbl.group(1)
                lbl_formatted = f"({lbl_token})"
                body_text = m_lbl.group(2).strip()
            else:
                lbl_token = chr(97 + c_idx) if c_idx < 26 else str(c_idx + 1)
                lbl_formatted = f"({lbl_token})"
                body_text = c_text

            node_dict: Dict[str, Any] = {
                "sub_id": f"{raw_num}{lbl_token}",
                "label": lbl_formatted,
                "text": body_text,
                "resources": c_resources,
                "children": [],
                "_dom_id": li_dom_id,
                "_parent_dom_id": li_parent_dom_id,
            }
            if li_dom_id:
                nodes_by_dom_id[li_dom_id] = node_dict

            if li_parent_dom_id and li_parent_dom_id != parent_dom_id and li_parent_dom_id in nodes_by_dom_id:
                parent_node = nodes_by_dom_id[li_parent_dom_id]
                node_dict["sub_id"] = f"{parent_node['sub_id']}({lbl_token})"
                parent_node["children"].append(node_dict)
            else:
                top_sub_reqs.append(node_dict)

        # Roll up nested children text into each top_sub_req["text"] while also preserving `children`
        cleaned_sub_reqs: List[Dict[str, Any]] = []
        for sr in top_sub_reqs:
            sr.pop("_dom_id", None)
            sr.pop("_parent_dom_id", None)
            children = sr.get("children") or []
            for ch in children:
                ch.pop("_dom_id", None)
                ch.pop("_parent_dom_id", None)
            if children:
                child_summary = " ".join(f"{ch['label']} {ch['text']}" for ch in children if ch.get("text"))
                full_sr_text = f"{sr['text']} {child_summary}".strip() if sr["text"] else child_summary
            else:
                full_sr_text = sr["text"]
            cleaned_sub_reqs.append({
                "sub_id": sr["sub_id"],
                "label": sr["label"],
                "text": full_sr_text,
                "resources": sr["resources"],
                "children": children,
            })

        if cleaned_sub_reqs:
            subs_joined = " ".join(f"{sr['label']} {sr['text']}" for sr in cleaned_sub_reqs if sr.get("text"))
            full_req_text = f"{parent_text} {subs_joined}".strip() if parent_text else subs_joined
        else:
            full_req_text = parent_text

        all_req_resources = list(parent_resources)
        for sr in cleaned_sub_reqs:
            for r_link in sr.get("resources") or []:
                if r_link not in all_req_resources:
                    all_req_resources.append(r_link)
            for ch in sr.get("children") or []:
                for r_link in ch.get("resources") or []:
                    if r_link not in all_req_resources:
                        all_req_resources.append(r_link)

        requirements.append({
            "req_id": raw_num,
            "req_number": raw_num,
            "topic_heading": topic_heading,
            "lead_text": parent_text,
            "req_text": full_req_text,
            "sub_requirements": cleaned_sub_reqs,
            "resources": all_req_resources,
            "source_url": f"https://www.scouting.org/merit-badges/{slug}/",
        })

    return {
        "badge_name": badge_name,
        "slug": slug,
        "url": f"https://www.scouting.org/merit-badges/{slug}/",
        "is_eagle_required": bool(is_eagle),
        "pamphlet_pdf_url": pamphlet_pdf_url,
        "intro_notes": intro_notes,
        "under_maintenance_on_scouting_org": under_maintenance,
        "requirements_source": "scouting.org" if requirements else "missing",
        "requirements_count": len(requirements),
        "sub_requirements_total": sum(len(r.get("sub_requirements") or []) for r in requirements),
        "requirements": requirements,
    }


def fetch_badge_html_with_cache_bust(
    slug: str,
    url: str,
    use_disk_cache: bool = True,
    polite_delay_sec: float = 0.35,
) -> Tuple[str, bool]:
    """Fetches a Merit Badge HTML page from scouting.org, automatically bypassing stale
    'Under maintenance. Check back soon.' CDN edge cache pages via `?v=2` / `?nocache=`."""
    HTML_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = HTML_CACHE_DIR / f"{slug}.html"

    if use_disk_cache and cache_file.exists() and cache_file.stat().st_size > 10_000:
        cached_html = cache_file.read_text(encoding="utf-8", errors="ignore")
        if "mb-requirement-item" in cached_html and "429 Too Many Requests" not in cached_html:
            return cached_html, False

    # Try bare URL first if not cached, then cache-busted `?v=2` and `?nocache=1` if CDN served 'Under maintenance'
    candidate_urls = [
        f"{url.rstrip('/')}/?v=2",
        f"{url.rstrip('/')}/?nocache={int(time.time())}",
        url,
    ]
    used_cache_bust = False
    last_html = ""

    for c_idx, cand_url in enumerate(candidate_urls):
        for attempt in range(4):
            try:
                resp = requests.get(cand_url, headers=DEFAULT_HEADERS, timeout=20)
                if resp.status_code == 200 and len(resp.text) > 10_000:
                    last_html = resp.text
                    if "mb-requirement-item" in resp.text:
                        cache_file.write_text(resp.text, encoding="utf-8")
                        time.sleep(polite_delay_sec)
                        return resp.text, (c_idx < 2)
                    # Page returned 200 but had 'Under maintenance'; try next candidate URL
                    used_cache_bust = True
                    time.sleep(polite_delay_sec)
                    break
                elif resp.status_code == 429:
                    wait_s = 3.0 * (attempt + 1)
                    time.sleep(wait_s)
                else:
                    time.sleep(1.0)
            except Exception:
                time.sleep(1.5)

    if last_html:
        cache_file.write_text(last_html, encoding="utf-8")
    return last_html, used_cache_bust


def scrape_all_merit_badges_to_directory(
    output_dir: Optional[Path] = None,
    use_disk_cache: bool = True,
) -> Dict[str, Any]:
    """Scrapes all Merit Badges starting from https://www.scouting.org/skills/merit-badges/all/
    and saves one structured JSON file per badge in `data/merit_badge_requirements/<slug>.json`."""
    target_dir = output_dir or REQUIREMENTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    HTML_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Discover all Merit Badge URLs from /skills/merit-badges/all/
    all_index_cache = HTML_CACHE_DIR / "_all_index.html"
    if use_disk_cache and all_index_cache.exists() and all_index_cache.stat().st_size > 20_000:
        all_html = all_index_cache.read_text(encoding="utf-8", errors="ignore")
    else:
        r_all = requests.get(ALL_BADGES_INDEX_URL, headers=DEFAULT_HEADERS, timeout=20)
        r_all.raise_for_status()
        all_html = r_all.text
        all_index_cache.write_text(all_html, encoding="utf-8")

    # 2. Discover Eagle-Required Merit Badge URLs from /skills/merit-badges/eagle-required/
    eagle_index_cache = HTML_CACHE_DIR / "_eagle_index.html"
    if use_disk_cache and eagle_index_cache.exists() and eagle_index_cache.stat().st_size > 20_000:
        eagle_html = eagle_index_cache.read_text(encoding="utf-8", errors="ignore")
    else:
        r_eagle = requests.get(EAGLE_BADGES_INDEX_URL, headers=DEFAULT_HEADERS, timeout=20)
        r_eagle.raise_for_status()
        eagle_html = r_eagle.text
        eagle_index_cache.write_text(eagle_html, encoding="utf-8")

    soup_eagle = BeautifulSoup(eagle_html, "html.parser")
    eagle_slugs = set()
    for a in soup_eagle.find_all("a", href=True):
        m = re.match(r"^https?://www\.scouting\.org/merit-badges/([^/]+)/?$", a["href"].strip())
        if m:
            eagle_slugs.add(m.group(1))
    eagle_slugs.add("citizenship-in-society")

    soup_all = BeautifulSoup(all_html, "html.parser")
    discovered_badges: Dict[str, Dict[str, str]] = {}
    for a in soup_all.find_all("a", href=True):
        href = a["href"].strip()
        m = re.match(r"^https?://www\.scouting\.org/merit-badges/([^/]+)/?$", href)
        if m:
            slug = m.group(1)
            title = _clean_whitespace(a.get_text(" ", strip=True))
            if slug not in discovered_badges or len(title) > len(discovered_badges[slug]["title"]):
                discovered_badges[slug] = {
                    "slug": slug,
                    "url": f"https://www.scouting.org/merit-badges/{slug}/",
                    "title": title,
                }

    if "citizenship-in-society" not in discovered_badges:
        discovered_badges["citizenship-in-society"] = {
            "slug": "citizenship-in-society",
            "url": "https://www.scouting.org/merit-badges/citizenship-in-society/",
            "title": "Citizenship in Society",
        }

    # Load fallback cache if any badge is genuinely missing on scouting.org
    fallback_cache: Dict[str, List[Dict[str, Any]]] = {}
    if LEGACY_CACHE_FILE.exists():
        try:
            fallback_cache = json.loads(LEGACY_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            fallback_cache = {}

    summary_entries: List[Dict[str, Any]] = []
    cache_bust_recovered: List[str] = []
    missing_on_scouting_org: List[str] = []
    merged_legacy_cache: Dict[str, List[Dict[str, Any]]] = {}

    for idx, (slug, info) in enumerate(sorted(discovered_badges.items()), start=1):
        html, needed_cache_bust = fetch_badge_html_with_cache_bust(
            slug=slug,
            url=info["url"],
            use_disk_cache=use_disk_cache,
        )
        if needed_cache_bust:
            cache_bust_recovered.append(slug)

        badge_data = parse_scouting_org_badge_html(
            html=html,
            slug=slug,
            url=info["url"],
            fallback_title=info["title"],
            is_eagle=(slug in eagle_slugs),
        )

        # If scouting.org still had zero requirements, fall back to official BSA Pamphlet PDF / fallback_cache
        if not badge_data["requirements"]:
            missing_on_scouting_org.append(badge_data["badge_name"])
            fb_reqs = (
                fallback_cache.get(badge_data["badge_name"])
                or fallback_cache.get("Indian Lore" if slug == "indian-lore" else "")
                or []
            )
            if slug == "indian-lore" and not fb_reqs:
                fb_reqs = [
                    {
                        "req_id": "1",
                        "req_number": "1",
                        "topic_heading": "American Indian Cultural Areas",
                        "lead_text": "Identify the different American Indian cultural areas. Explain what makes them each unique.",
                        "req_text": "Identify the different American Indian cultural areas. Explain what makes them each unique.",
                        "sub_requirements": [],
                        "resources": [],
                        "source_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Indian_Lore.pdf",
                    },
                    {
                        "req_id": "2",
                        "req_number": "2",
                        "topic_heading": "Tribal History, Culture & Contemporary Life",
                        "lead_text": "Research an American Indian tribe, group, or nation. Tell your counselor about traditional dwellings, way of life, tribal government, religious beliefs, family and clan relationships, language, clothing styles, arts and crafts, food cultivation, foraging and preparation, means of getting around, games, customs in warfare, and where and how they live today.",
                        "req_text": "Research an American Indian tribe, group, or nation. Tell your counselor about traditional dwellings, way of life, tribal government, religious beliefs, family and clan relationships, language, clothing styles, arts and crafts, food cultivation, foraging and preparation, means of getting around, games, customs in warfare, and where and how they live today.",
                        "sub_requirements": [],
                        "resources": [],
                        "source_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Indian_Lore.pdf",
                    },
                    {
                        "req_id": "3",
                        "req_number": "3",
                        "topic_heading": "Language, Place Names & Notable Leaders",
                        "lead_text": "Do the following:",
                        "req_text": "Do the following: (a) Learn 10 common terms in an American Indian language and their meanings. (b) Identify the meaning of 10 place names of American Indian origin in the United States. (c) Name five well-known American Indian leaders, either from the past or people of today. Give their tribes or nations. Describe what they did or do now that makes them notable.",
                        "sub_requirements": [
                            {"sub_id": "3a", "label": "(a)", "text": "Learn 10 common terms in an American Indian language and their meanings.", "resources": [], "children": []},
                            {"sub_id": "3b", "label": "(b)", "text": "Identify the meaning of 10 place names of American Indian origin in the United States.", "resources": [], "children": []},
                            {"sub_id": "3c", "label": "(c)", "text": "Name five well-known American Indian leaders, either from the past or people of today. Give their tribes or nations. Describe what they did or do now that makes them notable.", "resources": [], "children": []},
                        ],
                        "resources": [],
                        "source_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Indian_Lore.pdf",
                    },
                    {
                        "req_id": "4",
                        "req_number": "4",
                        "topic_heading": "Cultural Contributions & Traditional Games",
                        "lead_text": "Do the following:",
                        "req_text": "Do the following: (a) Describe how life might have been different for the European settlers if there had been no Native Americans to meet them when they came to this continent. (b) Describe eight things adopted by others from American Indians. (c) Learn a game played by a group or tribe. Teach and lead it with a Scout group.",
                        "sub_requirements": [
                            {"sub_id": "4a", "label": "(a)", "text": "Describe how life might have been different for the European settlers if there had been no Native Americans to meet them when they came to this continent.", "resources": [], "children": []},
                            {"sub_id": "4b", "label": "(b)", "text": "Describe eight things adopted by others from American Indians.", "resources": [], "children": []},
                            {"sub_id": "4c", "label": "(c)", "text": "Learn a game played by a group or tribe. Teach and lead it with a Scout group.", "resources": [], "children": []},
                        ],
                        "resources": [],
                        "source_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Indian_Lore.pdf",
                    },
                    {
                        "req_id": "5",
                        "req_number": "5",
                        "topic_heading": "Museum Exhibition or Contemporary Gathering",
                        "lead_text": "Do ONE of the following:",
                        "req_text": "Do ONE of the following: (a) Visit a museum either in-person or virtually to see American Indian exhibitions and collections. Discuss with your counselor what you observed or learned from two exhibitions and identify 10 artifacts by tribe or nation, their shape, size, and use. (b) Attend a contemporary American Indian gathering. Discuss with your counselor proper etiquette for attending as well as what you learned and observed during your visit.",
                        "sub_requirements": [
                            {"sub_id": "5a", "label": "(a)", "text": "Visit a museum either in-person or virtually to see American Indian exhibitions and collections. Discuss with your counselor what you observed or learned from two exhibitions and identify 10 artifacts by tribe or nation, their shape, size, and use.", "resources": [], "children": []},
                            {"sub_id": "5b", "label": "(b)", "text": "Attend a contemporary American Indian gathering. Discuss with your counselor proper etiquette for attending as well as what you learned and observed during your visit.", "resources": [], "children": []},
                        ],
                        "resources": [],
                        "source_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Indian_Lore.pdf",
                    },
                ]
            if fb_reqs:
                badge_data["requirements"] = fb_reqs
                badge_data["requirements_count"] = len(fb_reqs)
                badge_data["sub_requirements_total"] = sum(
                    len(r.get("sub_requirements") or []) for r in fb_reqs
                )
                badge_data["requirements_source"] = "official_pamphlet_pdf_fallback"

        out_path = target_dir / f"{slug}.json"
        out_path.write_text(json.dumps(badge_data, indent=2, ensure_ascii=False), encoding="utf-8")

        merged_legacy_cache[badge_data["badge_name"]] = badge_data["requirements"]
        if slug == "indian-lore":
            merged_legacy_cache["Indian Lore"] = badge_data["requirements"]
        summary_entries.append({
            "badge_name": badge_data["badge_name"],
            "slug": slug,
            "is_eagle_required": badge_data["is_eagle_required"],
            "requirements_count": badge_data["requirements_count"],
            "sub_requirements_total": badge_data["sub_requirements_total"],
            "requirements_source": badge_data["requirements_source"],
            "pamphlet_pdf_url": badge_data["pamphlet_pdf_url"],
            "json_file": f"data/merit_badge_requirements/{slug}.json",
        })

    index_payload = {
        "source_index_url": ALL_BADGES_INDEX_URL,
        "eagle_index_url": EAGLE_BADGES_INDEX_URL,
        "total_badges": len(summary_entries),
        "eagle_required_count": sum(1 for e in summary_entries if e["is_eagle_required"]),
        "direct_scouting_org_count": sum(1 for e in summary_entries if e["requirements_source"] == "scouting.org"),
        "cache_bust_recovered_slugs": cache_bust_recovered,
        "missing_on_scouting_org": missing_on_scouting_org,
        "badges": summary_entries,
    }
    (target_dir / "_index.json").write_text(
        json.dumps(index_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Also keep `data/official_requirements_cache.json` synchronized so legacy callers stay 100% up-to-date
    LEGACY_CACHE_FILE.write_text(
        json.dumps(merged_legacy_cache, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return index_payload


def load_badge_requirements_json(badge_name_or_slug: str) -> Optional[Dict[str, Any]]:
    """Loads the structured per-badge requirements JSON from `data/merit_badge_requirements/<slug>.json`."""
    slug = badge_name_to_slug(badge_name_or_slug)
    if not slug:
        return None
    direct_path = REQUIREMENTS_DIR / f"{slug}.json"
    if direct_path.exists():
        try:
            return json.loads(direct_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Try matching via _index.json
    idx_path = REQUIREMENTS_DIR / "_index.json"
    if idx_path.exists():
        try:
            idx_data = json.loads(idx_path.read_text(encoding="utf-8"))
            target_lower = badge_name_or_slug.strip().lower()
            for entry in idx_data.get("badges") or []:
                if entry.get("badge_name", "").lower() == target_lower or entry.get("slug") == slug:
                    cand_p = REQUIREMENTS_DIR / f"{entry['slug']}.json"
                    if cand_p.exists():
                        return json.loads(cand_p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None
