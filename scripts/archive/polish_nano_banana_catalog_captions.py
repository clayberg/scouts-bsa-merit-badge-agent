#!/usr/bin/env python3
"""Polishes all 1,306 captions in data/nano_banana_image_catalog.json using data/official_requirements_cache.json.

Eliminates:
- Short 2-4 word fragments ("Safety and Registration.", "Principles of Animation.")
- Abbreviation-split truncations ("Stance (regular vs.", "Examining the role of the U.S.")
- Dangling verb endings ("Explaining composite materials are.", "That you know each.", "and/or.")
- Meta requirement references ("Before doing requirements 4 through 6...", "in requirements 1 or 2.")
- Generic boilerplate fallbacks ("Scouts practicing <Badge> field skills and safety procedures for Requirement <N>.")
"""

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.tools.pamphlet_extractor import (
    _derive_topic_title,
    _ensure_complete_caption_sentence,
)

CATALOG_PATH = ROOT / "data" / "nano_banana_image_catalog.json"
OFFICIAL_CACHE_PATH = ROOT / "data" / "official_requirements_cache.json"

DANGLING_WORDS = {
    "a", "an", "the", "of", "in", "to", "for", "with", "on", "at", "from", "by", "about",
    "as", "into", "like", "through", "after", "over", "between", "out", "against", "during",
    "without", "before", "under", "around", "among", "and", "or", "but", "nor", "so", "yet",
    "because", "although", "since", "unless", "while", "where", "when", "that", "which", "who",
    "whom", "whose", "whether", "there", "their", "these", "those", "this", "other", "such",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "shall", "should", "may", "might", "must", "can", "could", "not",
    "very", "more", "most", "some", "any", "each", "every", "either", "neither", "both",
    "vs", "etc", "eg", "ie", "u", "s",
}


def _protect_abbrevs(text: str) -> str:
  s = text
  for abbr, tok in (
      ("U.S.", "US_DOT"),
      ("vs.", "VS_DOT"),
      ("e.g.", "EG_DOT"),
      ("i.e.", "IE_DOT"),
      ("Dr.", "DR_DOT"),
      ("St.", "ST_DOT"),
      ("Mr.", "MR_DOT"),
      ("Mrs.", "MRS_DOT"),
      ("No.", "NO_DOT"),
      ("ft.", "FT_DOT"),
      ("in.", "IN_DOT"),
      ("oz.", "OZ_DOT"),
      ("lb.", "LB_DOT"),
  ):
    s = s.replace(abbr, tok)
  return s


def _restore_abbrevs(text: str) -> str:
  s = text
  for abbr, tok in (
      ("U.S.", "US_DOT"),
      ("vs.", "VS_DOT"),
      ("e.g.", "EG_DOT"),
      ("i.e.", "IE_DOT"),
      ("Dr.", "DR_DOT"),
      ("St.", "ST_DOT"),
      ("Mr.", "MR_DOT"),
      ("Mrs.", "MRS_DOT"),
      ("No.", "NO_DOT"),
      ("ft.", "FT_DOT"),
      ("in.", "IN_DOT"),
      ("oz.", "OZ_DOT"),
      ("lb.", "LB_DOT"),
  ):
    s = s.replace(tok, abbr)
  return s


def _clean_subreq_phrase(txt: str) -> str:
  s = re.sub(r"\s+", " ", str(txt or "")).strip()
  s = re.sub(r"^\(?[0-9a-zA-Z]{1,3}\)?[.\s:;\-—]+", "", s).strip()
  s = re.sub(
      r"^(?:Explain|Describe|Discuss|Demonstrate|Show|Identify|Name|List|Tell|Define|Compare|Contrast|State|Review|Make|Prepare|Complete|Do)\s+"
      r"(?:to\s+your\s+counselor\s+|with\s+your\s+counselor\s+)?(?:how\s+to\s+|what\s+|why\s+|when\s+|where\s+|how\s+)?",
      "",
      s,
      flags=re.IGNORECASE,
  ).strip()
  s = re.sub(r"\b(?:in|for|from)\s+requirements?\s+\d+(?:\s*(?:through|to|or|and)\s*\d+)?", "", s, flags=re.IGNORECASE)
  s = _protect_abbrevs(s)
  first_sent = re.split(r"(?<=[.!?])\s+", s)[0]
  first_sent = _restore_abbrevs(first_sent).strip(" .,:;-—()")
  if len(first_sent) > 48:
    first_sent = first_sent[:48].rsplit(" ", 1)[0].strip(" .,:;-—()")
  words = first_sent.split()
  while len(words) > 2 and re.sub(r"[^a-z]", "", words[-1].lower()) in DANGLING_WORDS:
    words.pop()
  return " ".join(words).strip(" .,:;-—()")


def _needs_polish(cap: str) -> bool:
  if not cap or len(cap) < 48:
    return True
  if ":" in cap or "(" in cap and ")" not in cap:
    return True
  words = re.findall(r"[A-Za-z0-9']+", cap.rstrip(".!? ").lower())
  if not words or words[-1] in DANGLING_WORDS:
    return True
  if re.search(
      r"(\b(is|are|each|and/or|4through|5or|vs)\.$|\brequirements?\s+\d+|"
      r"^(That |After |Before |While |If |Though |Because |Unless |And |Or |With your counselor|Explore careers related to this|"
      r"Scouts practicing .+ field skills and safety procedures|.+ hands-on field practice and equipment for Requirement)|"
      r"\b(Identifying and point|Exploring and demonstrate|Visiting a .+ and complete|Explaining .+ is\.|Explaining .+ are\.))",
      cap,
      re.IGNORECASE,
  ):
    return True
  return False


def build_rich_caption(
    fname: str,
    entry: dict,
    official_reqs_by_badge: dict,
) -> str:
  badge_name = str(entry.get("badge_name") or "").strip()
  req_num = str(entry.get("req_number") or "1").strip()
  base_req = re.sub(r"[a-zA-Z]+$", "", req_num).strip() or req_num
  is_topic_vis = "topic_visual" in fname

  badge_reqs = official_reqs_by_badge.get(badge_name.lower(), [])
  req_obj = None
  for r in badge_reqs:
    if str(r.get("req_number")) == req_num or str(r.get("req_number")) == base_req:
      req_obj = r
      break

  req_text = str((req_obj or {}).get("req_text") or entry.get("slide_title") or "").strip()
  sub_reqs = list((req_obj or {}).get("sub_requirements") or [])

  topic = _derive_topic_title(base_req, req_text).replace(f"Req {base_req}:", "").strip(" .,:;-—")
  if not topic or len(topic) < 5 or topic.lower().startswith(("do the following", "with your", "choose ", "complete ")):
    topic = f"{badge_name} Requirement {req_num}"

  # Extract 2-3 clean sub-topic phrases from sub_requirements or req_text clauses
  sub_phrases = []
  for sr in sub_reqs[:4]:
    p = _clean_subreq_phrase(sr.get("text") or "")
    if p and len(p) >= 6 and p.lower() not in {x.lower() for x in sub_phrases}:
      sub_phrases.append(p.lower() if not p[:2].isupper() else p)
      if len(sub_phrases) >= 3:
        break

  if not sub_phrases and req_text:
    # Try splitting req_text into clauses or extracting key noun phrases
    cleaned_rt = re.sub(
        r"^(?:Do the following|Do ONE of the following|With your parent or guardian's and counselor's permission|Before doing requirements?[^,]+|After successfully completing[^,]+)[,.\s:]*",
        "",
        req_text,
        flags=re.IGNORECASE,
    ).strip()
    if "career" in req_text.lower() or "profession" in req_text.lower():
      if is_topic_vis:
        return _ensure_complete_caption_sentence(
            f"Professional {badge_name} career pathways showing education, training credentials, and workplace mentorship.",
            max_chars=120,
        )
      return _ensure_complete_caption_sentence(
          f"Uniformed Scout interviewing a {badge_name} professional about career training, education, and daily duties.",
          max_chars=120,
      )
    p_single = _clean_subreq_phrase(cleaned_rt)
    if p_single and len(p_single) >= 10:
      sub_phrases.append(p_single.lower() if not p_single[:2].isupper() else p_single)

  if sub_phrases:
    if len(sub_phrases) == 1:
      detail_str = sub_phrases[0]
    elif len(sub_phrases) == 2:
      detail_str = f"{sub_phrases[0]} and {sub_phrases[1]}"
    else:
      detail_str = f"{sub_phrases[0]}, {sub_phrases[1]}, and {sub_phrases[2]}"
    if is_topic_vis:
      raw = f"Four-panel {badge_name} visual illustrating {detail_str}."
    else:
      raw = f"Scout and counselor reviewing {detail_str} for {badge_name}."
  else:
    if is_topic_vis:
      raw = f"Four-panel {badge_name} visual demonstrating {topic.lower()} equipment, safety checks, and field technique."
    else:
      raw = f"Uniformed Scout and counselor reviewing {topic.lower()} concepts and field equipment for {badge_name}."

  raw = raw.replace(":", " — ")
  cap = _ensure_complete_caption_sentence(raw, max_chars=120)
  words = re.findall(r"[A-Za-z0-9']+", cap.rstrip(".!? ").lower())
  while len(words) > 4 and words[-1] in DANGLING_WORDS:
    cap = cap.rstrip(".!? ").rsplit(" ", 1)[0].rstrip(" ,;:-—") + "."
    words = re.findall(r"[A-Za-z0-9']+", cap.rstrip(".!? ").lower())
  return cap


def main():
  catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
  official_cache = json.loads(OFFICIAL_CACHE_PATH.read_text(encoding="utf-8")) if OFFICIAL_CACHE_PATH.exists() else {}
  official_by_lower = {k.lower(): v for k, v in official_cache.items()}

  polished_count = 0
  seen_per_badge = {}

  for fname in sorted(catalog.keys()):
    entry = catalog[fname]
    b_name = str(entry.get("badge_name") or "").strip()
    b_key = b_name.lower()
    seen_set = seen_per_badge.setdefault(b_key, set())

    cur_cap = str(entry.get("caption") or "").strip()
    # Keep manually curated Collections captions intact
    if fname.startswith("collections_"):
      norm_c = re.sub(r"[^a-z0-9]+", " ", cur_cap.lower()).strip()
      seen_set.add(norm_c)
      continue

    norm_cur = re.sub(r"[^a-z0-9]+", " ", cur_cap.lower()).strip()
    if _needs_polish(cur_cap) or norm_cur in seen_set:
      new_cap = build_rich_caption(fname, entry, official_by_lower)
      norm_new = re.sub(r"[^a-z0-9]+", " ", new_cap.lower()).strip()
      if norm_new in seen_set:
        req_num = str(entry.get("req_number") or "1").strip()
        if "topic_visual" in fname:
          new_cap = _ensure_complete_caption_sentence(
              f"Step-by-step {b_name} field breakdown for Requirement {req_num} showing equipment and hands-on practice.",
              max_chars=120,
          )
        else:
          new_cap = _ensure_complete_caption_sentence(
              f"Uniformed Scout demonstrating {b_name} Requirement {req_num} skills and safety checks with a counselor.",
              max_chars=120,
          )
        norm_new = re.sub(r"[^a-z0-9]+", " ", new_cap.lower()).strip()
      entry["caption"] = new_cap
      seen_set.add(norm_new)
      polished_count += 1
    else:
      seen_set.add(norm_cur)

  CATALOG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
  print(f"Polished {polished_count} captions across {len(catalog)} entries in {CATALOG_PATH.name}.")


if __name__ == "__main__":
  main()
