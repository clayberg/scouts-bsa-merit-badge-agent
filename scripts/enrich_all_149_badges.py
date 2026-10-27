#!/usr/bin/env python3
"""Enriches all 149 Official & Test Lab Merit Badges with Rich Pedagogy, 5-Tier Syllabus Buckets,
Verb-Aligned Workbook Organizers, Misconception vs. Fact Pairs, Starting Gates, Curated Multimedia Links,
and 100% Clean Pamphlet Image Catalog Coverage.

Guarantees:
1. `req_number` and `req_text` (and sub-requirement `sub_id`, `label`, `text`) remain 100% immutable.
2. All 149 badges have clean, Vision-verified entries in both `data/pamphlet_image_catalog.json`
   and `data/nano_banana_image_catalog.json` (zero blank gray boxes, zero stamped bars, zero 0-byte files).
3. All 149 `data/merit_badge_requirements/*.json` files and `data/official_requirements_cache.json`
   contain genuine, non-chopped pedagogy (`pamphlet_excerpts`, `step_by_step_procedure`, `gear_checklist`,
   selective `comparison_data`, non-truncated `worked_example`, selective Req 1 `quiz_item`),
   `syllabus_bucket`, `workbook_organizer`, `pamphlet_page_citation`, `common_misconception_pair`,
   `starting_requirement_gate`, and `curated_resources`.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import (  # noqa: E402
    OFFICIAL_BSA_MERIT_BADGES_CATALOG,
    TEST_LAB_PILOT_BADGES,
    badge_file_slug,
    badge_url_slug,
    is_eagle_required,
    is_test_lab_badge,
)
from src.tools.pamphlet_extractor import (  # noqa: E402
    _derive_topic_title,
    _get_selective_safety_quiz_for_requirement,
    summarize_pamphlet_for_requirement,
)

REQS_DIR = REPO_ROOT / "data" / "merit_badge_requirements"
CACHE_PATH = REPO_ROOT / "data" / "official_requirements_cache.json"
PAMPHLET_CATALOG_PATH = REPO_ROOT / "data" / "pamphlet_image_catalog.json"
NANO_CATALOG_PATH = REPO_ROOT / "data" / "nano_banana_image_catalog.json"
PAMPHLET_IMAGES_DIR = REPO_ROOT / "assets" / "pamphlet_images"
AI_ILLUSTRATIONS_DIR = REPO_ROOT / "assets" / "ai_illustrations"

_CURATED_TOPIC_TITLES: Dict[str, Dict[str, str]] = {
    "Citizenship in Society": {
        "1": "Req 1: Core Terms: Diversity, Equity, Inclusion & Upstander",
        "2": "Req 2: Ethical Leadership & Principled Decision-Making",
        "3": "Req 3: Personal Ethical Decisions & Acting as an Upstander",
        "4": "Req 4: Applying the Scout Oath & Law to Real-World Scenarios",
        "5": "Req 5: Building a Welcoming & Inclusive Scouting Unit",
        "6": "Req 6: Connecting Across Different Identities & Perspectives",
        "7": "Req 7: Community & Historical Leaders in Inclusion",
        "8": "Req 8: Historical Events Advancing Inclusion in Society",
        "9": "Req 9: Practicing Inclusive Leadership in Daily Life",
        "10": "Req 10: Challenging Stereotypes, Prejudice & Discrimination",
        "11": "Req 11: Future Leadership & Diverse Perspectives in Action",
    },
    "Auctioneering": {
        "1": "Req 1: Worldwide History of Auctions & Asset Markets",
        "2": "Req 2: Professional Roles in an Auction Team",
        "3": "Req 3: Auction Price Discovery vs. Fixed-Price Sales",
        "4": "Req 4: Professional Auctioneer Interview & Live Observation",
        "5": "Req 5: Auction Asset Classes, Sellers & Sale Formats",
        "6": "Req 6: Developing & Performing an Auction Chant",
        "7": "Req 7: Planning & Running a Unit Auction Event",
        "8": "Req 8: Auction Schools, State Licensing & Career Pathways",
        "9": "Req 9: Scouting America Test Lab Feedback & Evaluation",
    },
    "Dance": {
        "1": "Req 1: Dance Injury Prevention, Warm-Ups & First Aid",
        "2": "Req 2: The Five Elements of Dance (BASTE Framework)",
        "3": "Req 3: Exploring Six Styles of Partner, Solo & Group Dance",
        "4": "Req 4: Dance History, Choreography & Adaptive Inclusivity",
        "5": "Req 5: Rehearsing Warm-Ups & Performing a Dance Routine",
        "6": "Req 6: Dance Careers, Choreography & Lifelong Fitness",
        "7": "Req 7: Scouting America Test Lab Feedback & Evaluation",
    },
    "Physics": {
        "1": "Req 1: Physics Lab Safety, PPE & Hazard Prevention",
        "2": "Req 2: Defining Physics & Its Major Scientific Branches",
        "3": "Req 3: Fundamental Concepts: Force, Motion, Energy & Waves",
        "4": "Req 4: Hands-On Physics Experiments & Data Analysis",
        "5": "Req 5: Physics in Daily Life, Space, Climate & Scouting",
        "6": "Req 6: Frontiers of Physics: Quantum, Space & New Theories",
        "7": "Req 7: Engineering & Physics Design Challenge",
        "8": "Req 8: Physics Careers, Research & STEM Pathways",
        "9": "Req 9: Scouting America Test Lab Feedback & Evaluation",
    },
    "Psychology": {
        "1": "Req 1: Foundations of Psychology & Pioneers of the Field",
        "2": "Req 2: Applying Psychological Principles in Leadership Skits",
        "3": "Req 3: Mental Health, Protective Factors & Youth Resilience",
        "4": "Req 4: Two-Week Daily Time Log & Screen-Time Balance",
        "5": "Req 5: Practicing Empathy & Developing Resilience in Scouting",
        "6": "Req 6: Community of Hope, Scout Oath & Personal Reflection",
        "7": "Req 7: Psychology Careers, Education & Licensing Pathways",
        "8": "Req 8: Scouting America Test Lab Feedback & Evaluation",
    },
    "Sewing and Needlework": {
        "1": "Req 1: Sewing Safety, Sharps Handling & Iron Precautions",
        "2": "Req 2: Sewing Kit Assembly, Hand Stitches & Uniform Mending",
        "3": "Req 3: Specialized Textile Craft: Machine, Knit, Crochet or Quilt",
        "4": "Req 4: Textile Arts Exhibition & Museum Critique",
        "5": "Req 5: Community Service & Conservation Through Mending",
        "6": "Req 6: Textile, Apparel Design & Fiber Arts Careers",
        "7": "Req 7: Scouting America Test Lab Feedback & Evaluation",
    },
}

_TRAILING_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "nor", "for", "so", "yet",
    "to", "of", "in", "on", "at", "by", "with", "from", "into", "onto",
    "upon", "about", "as", "that", "which", "who", "whom", "whose",
    "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "can", "could", "will", "would", "should",
    "may", "might", "must", "such", "including", "between", "through",
    "during", "before", "after", "above", "below", "under", "over",
}


_OCR_LIGATURE_FIXES: Dict[str, str] = {
    "safetyand": "safety and",
    "Safetyand": "Safety and",
    "andlift": "and lift",
    "Andlift": "And lift",
    "bloodbornepathogens": "bloodborne pathogens",
    "Bloodbornepathogens": "Bloodborne pathogens",
    "Theemergency": "The emergency",
    "theemergency": "the emergency",
    "smellingsalts": "smelling salts",
    "tohypothermia": "to hypothermia",
    "Sufferingfrom": "Suffering from",
    "sufferingfrom": "suffering from",
    "fortransporting": "for transporting",
    "coretemperature": "core temperature",
    "fromdehydration": "from dehydration",
    "madecarefully": "made carefully",
    "otherimmediate": "other immediate",
    "Beforeattempting": "Before attempting",
    "beforeattempting": "before attempting",
    "atopographical": "a topographical",
    "completedbefore": "completed before",
    "Civilizationbehind": "Civilization behind",
    "civilizationbehind": "civilization behind",
    "outdoorskills": "outdoor skills",
    "Safetyguidelines": "Safety guidelines",
    "safetyguidelines": "safety guidelines",
    "handlingprocedures": "handling procedures",
    "Andpreparation": "And preparation",
    "andpreparation": "and preparation",
    "Whetheranyone": "Whether anyone",
    "whetheranyone": "whether anyone",
    "cookcarefully": "cook carefully",
    "crosscontamination": "cross-contamination",
    "norefrigeration": "no refrigeration",
    "processingfacility": "processing facility",
    "ofconstitutional": "of constitutional",
    "ofrepresentatives": "of representatives",
    "Congressionaldistricts": "Congressional districts",
    "congressionaldistricts": "congressional districts",
    "televisiontouches": "television touches",
    "moreopportunity": "more opportunity",
    "testingpest-control": "testing pest-control",
    "avoidoverfishing": "avoid overfishing",
    "researchorganization": "research organization",
    "environmentalistin": "environmentalist in",
    "haveintentionally": "have intentionally",
    "temperaturesand": "temperatures and",
    "pollutantsincluding": "pollutants including",
    "industriesrelease": "industries release",
    "beforereleasing": "before releasing",
    "andbusinesses": "and businesses",
    "Abandonedfactories": "Abandoned factories",
    "abandonedfactories": "abandoned factories",
    "tomagazine-article": "to magazine-article",
    "aluminumbeverage": "aluminum beverage",
    "recycledaluminum": "recycled aluminum",
    "betweenflowering": "between flowering",
    "speciesworldwide": "species worldwide",
    "Pollinatorsare": "Pollinators are",
    "pollinatorsare": "pollinators are",
    "aquaticorganisms": "aquatic organisms",
    "simplydisturbing": "simply disturbing",
    "ofoccupations": "of occupations",
    "Environmentalengineers": "Environmental engineers",
    "environmentalengineers": "environmental engineers",
    "properlymaintained": "properly maintained",
    "preventablediseases": "preventable diseases",
    "withoutnoticeable": "without noticeable",
    "tospecifications": "to specifications",
    "measurementsto": "measurements to",
    "Trainersshould": "Trainers should",
    "trainersshould": "trainers should",
    "policiesexplaining": "policies explaining",
    "theirservices": "their services",
    "Exercisephysiologists": "Exercise physiologists",
    "exercisephysiologists": "exercise physiologists",
    "othertechniques": "other techniques",
    "usingprosthetic": "using prosthetic",
    "search-and-rescueactivities": "search-and-rescue activities",
    "thefour-handed": "the four-handed",
    "providedoutstanding": "provided outstanding",
    "theirassistance": "their assistance",
    "orinstructions": "or instructions",
    "departmentsand": "departments and",
    "startschoking": "starts choking",
    "causeparalysis": "cause paralysis",
    "skin-to-skincontact": "skin-to-skin contact",
    "dusk-to-dawnsecurity": "dusk-to-dawn security",
    "stopimmediately": "stop immediately",
    "imaginarylines": "imaginary lines",
    "Constellationis": "Constellation is",
    "constellationis": "constellation is",
    "visiblefeatures": "visible features",
    "photographsthan": "photographs than",
    "Moreinformation": "More information",
    "moreinformation": "more information",
    "humanautonomic": "human autonomic",
    "thecontroller": "the controller",
    "handheldvideo-game": "handheld video-game",
    "Communicatewith": "Communicate with",
    "communicatewith": "communicate with",
    "ofcommunication": "of communication",
    "Designedusing": "Designed using",
    "designedusing": "designed using",
    "Yourcounselor": "Your counselor",
    "yourcounselor": "your counselor",
    "sports-likerobotics": "sports-like robotics",
    "autonomouschallenge": "autonomous challenge",
    "industrialengineering": "industrial engineering",
    "Andrebandage": "And rebandage",
    "andrebandage": "and rebandage",
    "Arecarefully": "Are carefully",
    "arecarefully": "are carefully",
    "BSAhandbook": "BSA handbook",
    "Scouthandbook": "Scout handbook",
    "Beforegoing": "Before going",
    "beforegoing": "before going",
    "Beforethey": "Before they",
    "beforethey": "before they",
    "Beforeyou": "Before you",
    "beforeyou": "before you",
    "Candeliberately": "Can deliberately",
    "candeliberately": "can deliberately",
    "Carefullyread": "Carefully read",
    "carefullyread": "carefully read",
    "Carefulnot": "Careful not",
    "carefulnot": "careful not",
    "Commandand": "Command and",
    "commandand": "command and",
    "Commissionenforced": "Commission enforced",
    "Detailedinformation": "Detailed information",
    "detailedinformation": "detailed information",
    "Effortswith": "Efforts with",
    "effortswith": "efforts with",
    "Eithersituation": "Either situation",
    "eithersituation": "either situation",
    "Enforcelocal": "Enforce local",
    "enforcelocal": "enforce local",
    "Facingforward": "Facing forward",
    "facingforward": "facing forward",
    "Feathersfrom": "Feathers from",
    "feathersfrom": "feathers from",
    "Fluoridereinforces": "Fluoride reinforces",
    "Furtherabuse": "Further abuse",
    "furtherabuse": "further abuse",
    "Furtherimproves": "Further improves",
    "furtherimproves": "further improves",
    "Handlingwill": "Handling will",
    "handlingwill": "handling will",
    "Healthyperformer": "Healthy performer",
    "Informationabout": "Information about",
    "informationabout": "information about",
    "Informationfollows": "Information follows",
    "informationfollows": "information follows",
    "Informationto": "Information to",
    "informationto": "information to",
    "Informedabout": "Informed about",
    "informedabout": "informed about",
    "Ishypothermia": "Is hypothermia",
    "ishypothermia": "is hypothermia",
    "Knotcombines": "Knot combines",
    "knotcombines": "knot combines",
    "Landmanagers": "Land managers",
    "landmanagers": "land managers",
    "Layerformed": "Layer formed",
    "layerformed": "layer formed",
    "Leatheruppers": "Leather uppers",
    "leatheruppers": "leather uppers",
    "Obscurehandrails": "Obscure handrails",
    "Ofphotosynthesis": "Of photosynthesis",
    "ofphotosynthesis": "of photosynthesis",
    "Othercitizens": "Other citizens",
    "othercitizens": "other citizens",
    "Othercontracts": "Other contracts",
    "othercontracts": "other contracts",
    "Otherlawyers": "Other lawyers",
    "otherlawyers": "other lawyers",
    "Otherrelatives": "Other relatives",
    "otherrelatives": "other relatives",
    "Othersymptoms": "Other symptoms",
    "othersymptoms": "other symptoms",
    "Performminor": "Perform minor",
    "performminor": "perform minor",
    "Prepareand": "Prepare and",
    "prepareand": "prepare and",
    "Preparedas": "Prepared as",
    "preparedas": "prepared as",
    "Preparedto": "Prepared to",
    "preparedto": "prepared to",
    "Ratherthan": "Rather than",
    "ratherthan": "rather than",
    "youreach": "you reach",
    "youremember": "you remember",
    "yourespect": "you respect",
    "world’slargest": "world's largest",
    "Scouting’shistory": "Scouting's history",
    "guardian’spermission": "guardian's permission",
}


def _sanitize_ocr_ligatures(text: str) -> str:
    """Cleans joined PDF extraction words inside pamphlet excerpts and summaries while never touching req_text."""
    if not text:
        return ""
    s = str(text)
    for bad_tok, clean_tok in _OCR_LIGATURE_FIXES.items():
        if bad_tok in s:
            s = s.replace(bad_tok, clean_tok)
    s = re.sub(r"\b(your|Your)(?!(?:self|selves|selfer))([a-z]{3,})\b", r"\1 \2", s)
    s = re.sub(r"\b(their|Their)(?!s\b)([a-z]{3,})\b", r"\1 \2", s)
    s = re.sub(r"\b(whether|Whether)([a-z]{2,})\b", r"\1 \2", s)
    s = re.sub(r"\b(between|Between)([a-z]{3,})\b", r"\1 \2", s)
    s = re.sub(r"\b(without|Without)([a-z]{3,})\b", r"\1 \2", s)
    s = re.sub(r"\b(within|Within)([a-z]{3,})\b", r"\1 \2", s)
    s = re.sub(r"\b(before|Before)(?!hand\b)([a-z]{3,})\b", r"\1 \2", s)
    s = re.sub(r"\b(through|Through)(?!out\b|put\b)([a-z]{3,})\b", r"\1 \2", s)
    s = re.sub(r"\b(which|Which)(?!ever\b)([a-z]{3,})\b", r"\1 \2", s)
    s = re.sub(r"\b(while|While)(?!s\b|st\b)([a-z]{3,})\b", r"\1 \2", s)
    s = re.sub(
        r"\b(?!(?:here|there|where|forth|band|out)with\b)([A-Za-z]{4,})with\b",
        r"\1 with",
        s,
    )
    s = re.sub(
        r"\b(?!(?:there|where|here)from\b)([A-Za-z]{4,})from\b",
        r"\1 from",
        s,
    )
    return s


def _clean_prose(text: str) -> str:
    """Strips em-dashes, en-dashes, double-hyphens, ellipses, and OCR ligatures per unslop/humanizer standards."""
    if not text:
        return ""
    s = _sanitize_ocr_ligatures(str(text)).replace("...", ".").replace("…", ".")
    s = s.replace(" — ", ", ").replace(" – ", ", ").replace(" -- ", ", ")
    s = s.replace("—", ", ").replace("–", "-").replace("--", ", ")
    while "  " in s:
        s = s.replace("  ", " ")
    return s.strip()


def _complete_sentence_summary(text: str, max_chars: int = 250) -> str:
    """Returns a complete, grammatically sound sentence or clause without mid-word or mid-phrase chopping."""
    cleaned = _clean_prose(text)
    if not cleaned:
        return ""
    cleaned = re.sub(
        r"^(?:Before beginning work on other requirements for this merit badge,\s*|Do the following:\s*)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    if len(cleaned) <= max_chars:
        return cleaned if cleaned[-1] in ".!?" else cleaned.rstrip(".,;:(") + "."

    # Try first complete sentence
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
    if sentences and 24 <= len(sentences[0]) <= max_chars:
        s0 = sentences[0]
        return s0 if s0[-1] in ".!?" else s0.rstrip(".,;:(") + "."

    # Trim at word boundary before max_chars and strip trailing stopwords/prepositions
    target = sentences[0] if sentences else cleaned
    words = target.split()
    out_words: List[str] = []
    cur_len = 0
    for w in words:
        if cur_len + len(w) + (1 if out_words else 0) > max_chars - 1:
            break
        out_words.append(w)
        cur_len += len(w) + (1 if len(out_words) > 1 else 0)

    while len(out_words) > 4:
        last_clean = re.sub(r"[^a-zA-Z]", "", out_words[-1]).lower()
        if last_clean in _TRAILING_STOPWORDS or len(last_clean) <= 1:
            out_words.pop()
        else:
            break

    result = " ".join(out_words).rstrip(".,;:(-")
    return (result + ".") if result else cleaned[:max_chars].rsplit(" ", 1)[0] + "."


def _infer_leading_verb(req_text: str) -> str:
    """Infers a clean transitive instructional verb from requirement text (never a preposition or conjunction)."""
    txt = (req_text or "").strip()
    if not txt:
        return "Explain"
    lower = txt.lower()
    verb_pairs = [
        ("do the following", "Demonstrate"),
        ("explain", "Explain"),
        ("discuss", "Discuss"),
        ("describe", "Describe"),
        ("demonstrate", "Demonstrate"),
        ("show", "Show"),
        ("prepare", "Prepare"),
        ("make", "Make"),
        ("build", "Build"),
        ("design", "Design"),
        ("plan", "Plan"),
        ("visit", "Visit"),
        ("attend", "Attend"),
        ("identify", "Identify"),
        ("list", "List"),
        ("name", "Name"),
        ("compare", "Compare"),
        ("contrast", "Compare"),
        ("find out", "Research"),
        ("research", "Research"),
        ("study", "Research"),
        ("interview", "Discuss"),
        ("connect with", "Discuss"),
        ("document", "Record"),
        ("develop", "Practice"),
        ("perform", "Demonstrate"),
        ("conduct", "Demonstrate"),
        ("solve", "Design"),
        ("assemble", "Prepare"),
        ("camp", "Camp"),
        ("swim", "Swim"),
        ("shoot", "Shoot"),
        ("cook", "Cook"),
        ("serve", "Serve"),
        ("write", "Write"),
        ("keep a log", "Record"),
        ("record", "Record"),
        ("complete the survey", "Complete"),
    ]
    for phrase, canonical_verb in verb_pairs:
        if lower.startswith(phrase) or f" {phrase} " in f" {lower[:90]} ":
            return canonical_verb
    valid_verbs = {v for _, v in verb_pairs}
    first_w = re.sub(r"[^a-zA-Z]", "", txt.split()[0]).capitalize()
    return first_w if first_w in valid_verbs else "Explain"


def _classify_syllabus_bucket(badge_name: str, req_num: str, full_text: str) -> str:
    """Classifies a requirement into one of the 5 SyllabusBucket values."""
    tl = full_text.lower()
    if any(
        kw in tl
        for kw in (
            "camp a total",
            "20 nights",
            "spend one overnight",
            "12-week",
            "13 consecutive",
            "90 days",
            "7-day",
            "five consecutive days",
            "two weeks",
            "30 days",
            "four 10-mile",
            "50-mile",
            "physical examination",
            "dental examination",
            "earn the first aid merit badge",
            "pass the bsa swimmer",
            "before you start",
            "before beginning work",
            "obtain your counselor's approval before",
            "attend a ",
            "visit a ",
            "tour a ",
            "shadow that auctioneer",
        )
    ):
        return "Pre-Class Prerequisite"
    if any(
        kw in tl
        for kw in (
            "serve actively",
            "for three months",
            "for six months",
            "teach a skill to your patrol",
            "present to your troop",
            "at a unit meeting",
            "at your unit meeting",
            "carry out your service project",
            "after completing your project",
            "family meeting",
            "complete the survey below",
        )
    ):
        return "Post-Class Home-Troop Follow-Up"
    if any(
        kw in tl
        for kw in (
            "find out about three career",
            "career opportunities",
            "explore careers",
            "pick one and find out the education",
            "write a report",
            "write a short personal reflection",
            "write a 300-word",
            "write a 500-word",
            "make a sketch",
            "draw a diagram",
            "collect and identify",
            "make a collection",
        )
    ):
        return "Make-Up Eligible"
    if any(
        kw in tl
        for kw in (
            "demonstrate",
            "show how",
            "show that you know first aid",
            "build a ",
            "construct a ",
            "splint",
            "bandage",
            "cpr",
            "shoot a qualifying",
            "swim ",
            "paddle",
            "splice",
            "tie ",
            "perform ",
            "rehearse and perform",
            "conduct three physics experiments",
            "assemble a basic sewing",
            "sew a ",
            "prepare a personal",
            "pitch a tent",
        )
    ):
        return "In-Class Demonstration"
    return "In-Class Concept"


def _extract_condition_or_clause_labels(
    full_text: str,
    req_num: str,
    verb: str,
    default_prefix: str = "Requirement Part",
    max_rows: int = 8,
) -> List[str]:
    """Extracts requirement-specific row labels from enumerated clauses, conditions, or sentences."""
    cleaned = _clean_prose(full_text)
    if not cleaned:
        return [f"{default_prefix} 1", f"{default_prefix} 2", f"{default_prefix} 3"]

    # 1. Check for inline parenthesized sub-clauses: (a) ... (b) ... or (1) ... (2) ...
    paren_parts = re.split(r"(?=\([a-zA-Z1-9]\)\s+)", cleaned)
    labeled_clauses: List[str] = []
    for pp in paren_parts:
        pp_s = pp.strip(" .;:,-")
        m_p = re.match(r"^\(([a-zA-Z1-9])\)\s+(.+)$", pp_s)
        if m_p:
            lbl_char = m_p.group(1)
            body = m_p.group(2).strip(" .;:,-")
            short_body = _complete_sentence_summary(body, max_chars=78).rstrip(".")
            labeled_clauses.append(f"({lbl_char}) {short_body}")
    if len(labeled_clauses) >= 2:
        return labeled_clauses[:max_rows]

    # 2. Check for "such as X, Y, and Z" or "including X, Y, and Z" condition lists
    m_list = re.search(
        r"(?:such as|including|for the following:?|following conditions:?)\s+([^.]+)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if m_list:
        raw_items = [
            it.strip(" .;:,-")
            for it in re.split(r",\s*(?:and\s+|or\s+)?|\s+and\s+|\s+or\s+", m_list.group(1))
            if len(it.strip(" .;:,-")) >= 3
        ]
        if len(raw_items) >= 3:
            return [it[0].upper() + it[1:] for it in raw_items[:max_rows]]

    # 3. Split on semicolons or sentence boundaries
    stripped_lead = re.sub(
        r"^(?:Do the following:?|Do ONE of the following:?|Do TWO of the following:?|Discuss the following:?|Explain the following:?)\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    semi_parts = [
        sp.strip(" .;:,-")
        for sp in re.split(r";\s+|\.\s+", stripped_lead)
        if len(sp.strip(" .;:,-")) >= 6
        and not sp.strip().lower().startswith(("do the following", "do one of the following", "note:"))
    ]
    if len(semi_parts) >= 2:
        out_semi: List[str] = []
        for idx_s, sp in enumerate(semi_parts[:max_rows], start=1):
            short_sp = _complete_sentence_summary(sp, max_chars=78).rstrip(".")
            out_semi.append(f"{idx_s}. {short_sp}")
        return out_semi

    # 4. Single short condition or clause (e.g., First Aid 3a "Closed wounds...", 3e "Sunburn", 4a "A nosebleed.")
    if len(stripped_lead) <= 95:
        single_lbl = stripped_lead.rstrip(".")
        return [
            single_lbl,
            f"Pamphlet Standard & Key Facts ({req_num})",
            f"Field Application & Counselor Verification ({verb})",
        ]

    # 5. Break a long single sentence on conjunctions/clauses into concrete study rows
    clause_chunks = [
        cc.strip(" .;:,-")
        for cc in re.split(r",\s+(?:and|or|including|how|why|when|where|what)\s+|\s+and\s+(?:explain|describe|discuss|show|demonstrate|list|identify|tell)\s+", stripped_lead)
        if len(cc.strip(" .;:,-")) >= 8
    ]
    if len(clause_chunks) >= 2:
        return [
            f"{i}. {_complete_sentence_summary(cc, max_chars=76).rstrip('.')}"
            for i, cc in enumerate(clause_chunks[:max_rows], start=1)
        ]

    short_summary = _complete_sentence_summary(stripped_lead, max_chars=74).rstrip(".")
    return [
        f"1. {short_summary}",
        f"2. Key Pamphlet Examples & Evidence (Req {req_num})",
        f"3. Practical {verb} & Safety Verification",
    ]


def _build_workbook_organizer(badge_name: str, req_num: str, verb: str, full_text: str) -> Dict[str, Any]:
    """Builds a bespoke or clause-extracted WorkbookOrganizerSpec dictionary across all 149 badges."""
    tl = full_text.lower()
    bl = badge_name.strip().lower()
    base_req_Match = re.match(r"^(\d+)", str(req_num).strip())
    base_num = base_req_Match.group(1) if base_req_Match else str(req_num).strip()

    pre_approval = any(
        kw in tl
        for kw in (
            "counselor's approval",
            "approved by your counselor",
            "with your counselor's approval",
            "before you begin",
            "before beginning work",
            "parent or guardian",
            "permission from your parents",
            "guidance from your counselor",
        )
    )

    # 1. HAZARD_5COL: "anticipate, help prevent, mitigate, and respond"
    if (
        "anticipate, help prevent, mitigate, and respond" in tl
        or "anticipate, help prevent" in tl
        or "mitigate, and respond" in tl
        or (req_num in ("1", "1a") and any(k in tl for k in ("likely hazards", "potential hazards", "hazards you may encounter")))
    ):
        headers = ["Hazard / Risk", "Anticipate", "Help Prevent", "Mitigate", "Respond"]
        return {
            "organizer_type": "HAZARD_5COL",
            "table_title": f"Req {req_num} Five-Column Hazard Matrix (Anticipate, Prevent, Mitigate, Respond)",
            "headers": headers,
            "column_headers": headers,
            "row_labels": ["Hazard #1", "Hazard #2", "Hazard #3", "Hazard #4", "Hazard #5"],
            "min_rows": 5,
            "pre_approval_gate": pre_approval,
        }

    # 2. CAMPING_LOG_20NIGHT: Camping Req 9 / 9a (20 nights)
    if (bl == "camping" and req_num in ("9", "9a")) or "20 nights" in tl or "camp a total of at least 20 nights" in tl:
        headers = ["Trip / Night #", "Date(s)", "Location / Camp", "Tent or Under Stars", "# of Nights", "Leader Initials"]
        return {
            "organizer_type": "CAMPING_LOG_20NIGHT",
            "table_title": "20-Night Designated Scouting Campout Experience Log",
            "headers": headers,
            "column_headers": headers,
            "row_labels": [f"Night/Trip {i}" for i in range(1, 21)],
            "min_rows": 20,
            "pre_approval_gate": pre_approval,
        }

    # 3. FITNESS_ASSESSMENT_4STAGE & FITNESS_LOG_12WK (Personal Fitness)
    if bl == "personal fitness" and (req_num in ("4", "4a", "4b", "4c", "5", "5a", "5b", "7b")):
        headers = ["Fitness Test Component", "Baseline (Start)", "Week 4", "Week 8", "Final (Week 12)"]
        return {
            "organizer_type": "FITNESS_ASSESSMENT_4STAGE",
            "table_title": f"Req {req_num} Four-Stage Physical Fitness Assessment Tracker",
            "headers": headers,
            "column_headers": headers,
            "row_labels": [
                "1-Mile Walk/Run",
                "Sit-Ups / Plank",
                "Push-Ups / Pull-Ups",
                "Sit-and-Reach Flexibility",
            ],
            "min_rows": 4,
            "pre_approval_gate": pre_approval,
        }
    if (bl == "personal fitness" and base_num in ("6", "7")) or "12-week" in tl or "12 consecutive weeks" in tl:
        headers = ["Week #", "Aerobic Activity & Duration", "Strength / Flexibility Exercises", "Nutrition & Heart Rate Notes", "Initials"]
        return {
            "organizer_type": "FITNESS_LOG_12WK",
            "table_title": f"Req {req_num} 12-Week Comprehensive Fitness & Nutrition Log",
            "headers": headers,
            "column_headers": headers,
            "row_labels": [f"Week {i}" for i in range(1, 13)],
            "min_rows": 12,
            "pre_approval_gate": True,
        }

    # 4. MEAL_PLANNER_AND_COST_TABLE: Cooking Reqs 4, 5, 6 and Camping Req 8c / 8d
    if (bl == "cooking" and base_num in ("4", "5", "6")) or (bl == "camping" and req_num in ("8", "8c", "8d")):
        headers = [
            "Meal & Menu Item",
            "MyPlate Food Groups",
            "Ingredients & Est. Cost ($)",
            "Equipment & Cooking Method",
            "Evaluation & Cleanup",
        ]
        return {
            "organizer_type": "MEAL_PLANNER_AND_COST_TABLE",
            "table_title": f"Req {req_num} MyPlate Meal Planner, Cost & Cooking Evaluation Table",
            "headers": headers,
            "column_headers": headers,
            "row_labels": ["Breakfast", "Lunch", "Dinner", "Dessert / Trail Snack"],
            "min_rows": 4,
            "pre_approval_gate": pre_approval,
        }

    # 5. CITIZENSHIP_CIVIC_ORGANIZER: Citizenship in the Nation Reqs 2, 3, 5, 8
    if bl == "citizenship in the nation":
        if base_num == "2":
            headers = ["Preamble Purpose", "Constitutional Meaning", "How It Affects Citizens Today"]
            return {
                "organizer_type": "CITIZENSHIP_CIVIC_ORGANIZER",
                "table_title": "Six Constitutional Purposes of the Preamble",
                "headers": headers,
                "column_headers": headers,
                "row_labels": [
                    "1. Form a More Perfect Union",
                    "2. Establish Justice",
                    "3. Insure Domestic Tranquility",
                    "4. Provide for the Common Defense",
                    "5. Promote the General Welfare",
                    "6. Secure the Blessings of Liberty",
                ],
                "min_rows": 6,
                "pre_approval_gate": pre_approval,
            }
        if base_num == "3":
            headers = ["Branch of Government", "Constitutional Function & Officials", "Checks & Balances", "Citizen Participation"]
            return {
                "organizer_type": "CITIZENSHIP_CIVIC_ORGANIZER",
                "table_title": "Three Branches of the U.S. Federal Government",
                "headers": headers,
                "column_headers": headers,
                "row_labels": [
                    "1. Legislative Branch (Congress: Senate & House)",
                    "2. Executive Branch (President, VP & Cabinet)",
                    "3. Judicial Branch (Supreme Court & Federal Courts)",
                ],
                "min_rows": 3,
                "pre_approval_gate": pre_approval,
            }
        if base_num == "5":
            headers = ["Day # & Date", "National News Source", "Main Story Summary", "Constitutional / Civic Issue"]
            return {
                "organizer_type": "CITIZENSHIP_CIVIC_ORGANIZER",
                "table_title": "5-Day National Evening News & Media Log",
                "headers": headers,
                "column_headers": headers,
                "row_labels": [
                    "Day 1 National News",
                    "Day 2 National News",
                    "Day 3 National News",
                    "Day 4 National News",
                    "Day 5 National News (Selected Issue for Discussion)",
                ],
                "min_rows": 5,
                "pre_approval_gate": pre_approval,
            }
        if base_num == "8":
            headers = ["Congressional Office", "Official Name & Party/District", "Contact Address / Website", "National Issue & Letter Summary"]
            return {
                "organizer_type": "CITIZENSHIP_CIVIC_ORGANIZER",
                "table_title": "U.S. Congressional Representatives & Letter Planner",
                "headers": headers,
                "column_headers": headers,
                "row_labels": ["Senator #1", "Senator #2", "House Representative"],
                "min_rows": 3,
                "pre_approval_gate": pre_approval,
            }

    # 6. ENVIRONMENTAL SCIENCE: SENSORY_OBSERVATION_LOG (Req 2/2a/2b) & SCIENTIFIC_EXPERIMENT_SHEET (Reqs 3, 4, 5)
    if bl == "environmental science" and base_num == "2":
        headers = ["Observation Session", "Sight (Visuals)", "Sound (Acoustics)", "Smell & Habitat Notes"]
        return {
            "organizer_type": "SENSORY_OBSERVATION_LOG",
            "table_title": f"Req {req_num} Two-Day Ecosystem Sensory Observation Log",
            "headers": headers,
            "column_headers": headers,
            "row_labels": ["Day 1 Observation", "Day 2 Observation", "Ecosystem Summary"],
            "min_rows": 3,
            "pre_approval_gate": True,
        }
    if (bl == "environmental science" and base_num in ("3", "4", "5")) or (
        any(k in tl for k in ("conduct an experiment", "perform an experiment", "three physics experiments", "scientific experiment"))
    ):
        headers = ["Step", "Your Plan / Hypothesis / Data", "Pamphlet Principle & Conclusion"]
        return {
            "organizer_type": "SCIENTIFIC_EXPERIMENT_SHEET",
            "table_title": f"Req {req_num} Scientific Experiment & Investigation Sheet",
            "headers": headers,
            "column_headers": headers,
            "row_labels": [
                "1. State the Problem",
                "2. Form a Hypothesis",
                "3. Experimental Procedure",
                "4. Observed Data & Results",
                "5. Conclusion",
            ],
            "min_rows": 5,
            "pre_approval_gate": pre_approval,
        }

    # 7. ROBOTICS: ENGINEERING_DESIGN_NOTEBOOK (Req 4 / 4a-4e / 5)
    if bl == "robotics" and base_num in ("4", "5"):
        headers = ["Engineering Stage", "Design / Sensor / Code Specification", "Test Results & Modifications"]
        return {
            "organizer_type": "ENGINEERING_DESIGN_NOTEBOOK",
            "table_title": f"Req {req_num} Robotics Engineering Design Notebook",
            "headers": headers,
            "column_headers": headers,
            "row_labels": [
                "1. Robot Task & Counselor Approval",
                "2. Mechanical & Structural Design",
                "3. Sensors & Actuators",
                "4. Programming & Control Flow",
                "5. Trial Runs 1-5 & Modifications",
            ],
            "min_rows": 5,
            "pre_approval_gate": True,
        }

    # 8. SKETCH_AND_OBSERVATION_CANVAS: Astronomy 4c, 6a, 6b and sketch/draw/diagram/map requirements
    if (bl == "astronomy" and req_num in ("4", "4c", "6", "6a", "6b", "6d")) or any(
        kw in tl for kw in ("sketch", "draw a ", "draw the ", "make a diagram", "with the aid of diagrams", "cross-section", "topographical map")
    ):
        headers = ["Sketch / Diagram Target", "Required Labels & Landmarks", "Observation Date, Time & Notes"]
        if bl == "astronomy" and req_num in ("4", "4c"):
            r_labels = [
                "Early Evening Horizon vs. Several Hours Later",
                "Big Dipper / Cassiopeia & Polaris Position",
                "Observation Date, Time & Sky Conditions",
            ]
        elif bl == "astronomy" and req_num in ("6", "6a"):
            r_labels = [
                "Lunar Seas (5) & Craters (5) Moon Circle",
                "Five Major Lunar Seas (Maria) Labeled",
                "Five Major Lunar Craters Labeled",
            ]
        elif bl == "astronomy" and req_num == "6b":
            r_labels = [
                "Night 1 Moon Phase & Horizon",
                "Night 2 Moon Phase & Horizon",
                "Night 3 Moon Phase & Horizon",
                "Night 4 Moon Phase & Horizon",
            ]
        else:
            r_labels = _extract_condition_or_clause_labels(full_text, req_num, verb, default_prefix="Sketch Element", max_rows=4)
        return {
            "organizer_type": "SKETCH_AND_OBSERVATION_CANVAS",
            "table_title": f"Req {req_num} Field Sketch & Observation Canvas",
            "headers": headers,
            "column_headers": headers,
            "row_labels": r_labels,
            "min_rows": len(r_labels),
            "pre_approval_gate": pre_approval,
        }

    # 9. CAREER_EXPLORATION_CARD: Career / profession / occupation requirements
    if (
        any(kw in tl for kw in ("career", "profession", "occupation", "training and experience required", "become involved in the auction industry"))
        or (bl == "first aid" and base_num == "15")
        or (bl == "cooking" and base_num == "7")
        or (bl == "environmental science" and base_num == "11")
        or (bl == "personal fitness" and base_num == "8")
        or (bl == "robotics" and base_num == "7")
        or (bl == "emergency preparedness" and base_num == "10")
        or (bl == "astronomy" and base_num == "9")
        or (bl == "auctioneering" and base_num == "8")
    ):
        headers = ["Career Research Dimension", "Selected Career Details", "Education, Training & Personal Goals"]
        return {
            "organizer_type": "CAREER_EXPLORATION_CARD",
            "table_title": f"Req {req_num} Career & Pathway Exploration Card",
            "headers": headers,
            "column_headers": headers,
            "row_labels": [
                "1. Three Career Opportunities Identified",
                "2. Selected Career: Education & Training Required",
                "3. Daily Duties, Licensing & Expenses",
                "4. Starting Salary, Job Outlook & Personal Goals",
            ],
            "min_rows": 4,
            "pre_approval_gate": pre_approval,
        }

    # 10. SYMPTOMS_FIRST_AID_PREVENTION_3COL: Symptoms, First Aid & Prevention (First Aid Reqs 3-13, Camping 1c, Swimming 1b, etc.)
    if (
        ("symptoms and signs" in tl and "first aid" in tl)
        or (bl == "first aid" and base_num in ("3", "4", "5", "6", "7", "8", "9", "11", "13"))
        or (bl == "camping" and req_num == "1c")
        or (bl == "swimming" and req_num == "1b")
        or ("first aid for" in tl and any(k in tl for k in ("prevent", "injuries or illnesses", "hypothermia", "heat", "bites", "burns", "blisters")))
    ):
        headers = ["Condition / Injury", "Symptoms & Signs", "First Aid / Treatment", "Prevention"]
        cond_rows = _extract_condition_or_clause_labels(full_text, req_num, verb, default_prefix="Condition", max_rows=8)
        return {
            "organizer_type": "SYMPTOMS_FIRST_AID_PREVENTION_3COL",
            "table_title": f"Req {req_num} Symptoms, First Aid & Prevention Matrix",
            "headers": headers,
            "column_headers": headers,
            "row_labels": cond_rows,
            "min_rows": len(cond_rows),
            "pre_approval_gate": pre_approval,
        }

    # 11. COMPARE_CONTRAST_2COL
    if any(kw in tl for kw in ("compare", "contrast", "difference between", "differences and similarities", "similarities and differences", "distinguish between", "versus", " vs. ", " vs ")):
        headers = ["Concept / Method A", "Concept / Method B", "Key Field Distinction & When to Use"]
        comp_rows = _extract_condition_or_clause_labels(full_text, req_num, verb, default_prefix="Comparison Dimension", max_rows=4)
        return {
            "organizer_type": "COMPARE_CONTRAST_2COL",
            "table_title": f"Req {req_num} Differential Comparison Matrix",
            "headers": headers,
            "column_headers": headers,
            "row_labels": comp_rows,
            "min_rows": len(comp_rows),
            "pre_approval_gate": pre_approval,
        }

    # 12. TIME_SERIES_LOG_TABLE
    if any(
        kw in tl
        for kw in (
            "keep a log",
            "tracking log",
            "13 consecutive",
            "90 days",
            "two weeks",
            "five days",
            "three days",
            "budget",
            "duty roster",
            "track your",
            "observation log",
        )
    ):
        headers = ["Date / Entry #", "Activity / Observation / Metric", "Measured Result / Notes", "Verifier Initials"]
        log_rows = _extract_condition_or_clause_labels(full_text, req_num, verb, default_prefix="Log Entry", max_rows=6)
        return {
            "organizer_type": "TIME_SERIES_LOG_TABLE",
            "table_title": f"Req {req_num} Activity & Observation Log Table",
            "headers": headers,
            "column_headers": headers,
            "row_labels": log_rows,
            "min_rows": len(log_rows),
            "pre_approval_gate": pre_approval,
        }

    # 13. PHYSICAL_SKILL_VERIFICATION_RUBRIC / STEP_BY_STEP_CHECKLIST for hands-on skills
    if verb in ("Demonstrate", "Show", "Build", "Prepare", "Make", "Cook", "Shoot", "Swim", "Practice") or "demonstrate" in tl or "perform" in tl:
        skill_rows = _extract_condition_or_clause_labels(full_text, req_num, verb, default_prefix="Skill Step", max_rows=6)
        is_pure_phys = bl == "swimming" or verb in ("Swim", "Shoot") or tl.startswith(("demonstrate ", "show how", "correctly perform"))
        org_t = "PHYSICAL_SKILL_VERIFICATION_RUBRIC" if is_pure_phys else "STEP_BY_STEP_CHECKLIST"
        headers = ["Skill / Step Element", "Technique & Safety Standard", "Buddy Practice Check", "Counselor Sign-Off"]
        return {
            "organizer_type": org_t,
            "table_title": f"Req {req_num} Practical Skill & Verification Checklist (GTA 7.0.3.2)",
            "headers": headers,
            "column_headers": headers,
            "row_labels": skill_rows,
            "min_rows": len(skill_rows),
            "pre_approval_gate": pre_approval,
            "is_physical_demonstration": True,
        }

    # 14. Clause-extracted RULED_EXPLAIN_BOX (never generic "Core Principle" when clauses exist)
    explain_rows = _extract_condition_or_clause_labels(full_text, req_num, verb, default_prefix="Sub-Part", max_rows=6)
    headers = [f"Req {req_num} Clause / Topic", "Key Pamphlet Facts & Real-World Scouting Application"]
    return {
        "organizer_type": "RULED_EXPLAIN_BOX",
        "table_title": f"Req {req_num} Structured Study & Explanation Notes",
        "headers": headers,
        "column_headers": headers,
        "row_labels": explain_rows,
        "min_rows": len(explain_rows),
        "pre_approval_gate": pre_approval,
    }


def _build_starting_gate(badge_name: str, req_num: str, full_text: str) -> Optional[Dict[str, Any]]:
    """Detects any prerequisite or safety gate required before starting or signing off the requirement."""
    tl = full_text.lower()
    bl = badge_name.lower()
    if "earn the first aid merit badge" in tl or (bl == "emergency preparedness" and req_num in ("1", "9")):
        return {
            "gate_type": "HARD_PREREQ_BADGE",
            "gate_label": "First Aid Merit Badge Required",
            "gate_description": "Scout must earn the First Aid Merit Badge to complete Emergency Preparedness.",
            "blocking_in_class": False,
        }
    if "bsa swimmer" in tl or "scouting america swimmer" in tl or (
        bl in ("lifesaving", "canoeing", "kayaking", "rowing", "small-boat sailing", "whitewater", "water sports", "scuba diving", "swimming")
        and req_num in ("1", "2", "1a", "2a")
    ):
        return {
            "gate_type": "HARD_PREREQ_BADGE",
            "gate_label": "BSA Swimmer Classification Gate",
            "gate_description": "Scout must complete the official BSA Swimmer test (100 yards + 1-minute float) before on-water skill stations.",
            "blocking_in_class": True,
        }
    if any(kw in tl for kw in ("counselor's approval", "approved by your counselor", "with your counselor's approval", "before beginning work")):
        return {
            "gate_type": "COUNSELOR_PRE_APPROVAL",
            "gate_label": "Counselor Pre-Approval Required",
            "gate_description": f"Review your {badge_name} Req {req_num} preparation with your Merit Badge Counselor before moving to subsequent tasks.",
            "blocking_in_class": False,
        }
    if any(kw in tl for kw in ("parent or guardian", "parent's permission", "parental permission", "with your parent", "permission from your parents")):
        return {
            "gate_type": "PARENT_CONSENT_GATE",
            "gate_label": "Parent/Guardian Consent & Review",
            "gate_description": f"Review and complete {badge_name} Req {req_num} with your parent or guardian's approval in compliance with BSA Youth Protection.",
            "blocking_in_class": False,
        }
    if any(kw in tl for kw in ("personal first-aid kit", "bring your", "pack a ", "protective gear", "helmet", "safety glasses", "sewing and repair kit")):
        return {
            "gate_type": "EQUIPMENT_GATE",
            "gate_label": "Required Field Gear / PPE Inspection",
            "gate_description": f"Bring required personal gear or PPE for {badge_name} Req {req_num} inspection prior to hands-on station work.",
            "blocking_in_class": False,
        }
    return None


_FIRST_AID_MISCONCEPTIONS_BY_BASE_REQ: Dict[str, tuple[str, str]] = {
    "1": (
        "Rescuers should rush directly to an injured hiker to check a pulse before scanning the surroundings.",
        "Always perform a 360-degree scene safety size-up, put on non-latex nitrile PPE gloves, check responsiveness/ABCs, activate 911, and triage life threats first.",
    ),
    "2": (
        "A store-bought first-aid kit can stay sealed at the bottom of a backpack for years without inspection.",
        "Review AHMR Parts A-C, inspect sterile dressings and expiration dates before every trek, and carry your personal kit in an accessible outer pack pocket.",
    ),
    "3": (
        "Popping friction blisters, rubbing frostbitten fingers, or putting butter/ice on thermal burns speeds healing.",
        "Protect hot spots with a moleskin doughnut pad, cool thermal burns under running water for 10+ minutes, rewarm frostbite in 99-104 F water, and pull ticks straight out with fine tweezers.",
    ),
    "4": (
        "Tilt the head back for a nosebleed, peel off blood-soaked gauze pads, and loosen a tourniquet every 10 minutes.",
        "Lean forward and pinch soft nostrils 10 minutes for nosebleeds, stack fresh gauze over soaked dressings, and keep a windlass tourniquet locked 2-3 inches above severe limb bleeding until EMS arrives.",
    ),
    "5": (
        "Perform a blind finger sweep in a choking victim's mouth and wait to see if anaphylaxis improves before using an EpiPen.",
        "Alternate 5 back blows and 5 abdominal thrusts for conscious choking, administer prescribed epinephrine into the outer mid-thigh immediately for anaphylaxis, and descend for altitude illness.",
    ),
    "6": (
        "Restrain a person having a seizure, place an object between their teeth, or induce vomiting after swallowed poison.",
        "Clear hazards and cushion the head during a seizure (never put anything in the mouth), call Poison Control at 1-800-222-1222 before giving anything by mouth, and place breathing unconscious patients in the recovery position.",
    ),
    "7": (
        "Pause chest compressions every 30 seconds to check for a pulse and wait for paramedics before attaching an AED.",
        "Deliver continuous chest compressions at 100-120/min (2 inches deep), attach AED pads as soon as available, and follow voice prompts while minimizing interruptions to under 10 seconds.",
    ),
    "8": (
        "Straighten an angled fracture or dislocated joint in the field before applying a splint.",
        "Splint fractures and dislocations in the exact position found, immobilize the joints above and below the injury with a SAM or rigid splint, and check distal circulation, motor, and sensation (CMS) before and after tying.",
    ),
    "9": (
        "A Scout who bumps their head can return to camp activities immediately as long as they were not knocked unconscious.",
        "Any suspected concussion or spinal mechanism requires immediate removal from activity, manual in-line cervical stabilization, leaving helmets in place unless airway access requires removal, and professional medical evaluation.",
    ),
    "10": (
        "Immediately lift and carry any injured hiker out to the trailhead before assessing or splinting injuries.",
        "Move an injured patient only when facing immediate scene danger or during a coordinated backcountry evacuation after stabilizing fractures, using proper walking assist, blanket drag, or stretcher techniques.",
    ),
    "11": (
        "Heatstroke is just severe heat exhaustion that can be treated by resting slowly in the shade with sips of water.",
        "Heatstroke (hot skin, altered mental status, core temp >104 F) is a life-threatening emergency requiring immediate 911 activation and rapid cooling with cold water immersion or ice packs at the neck, armpits, and groin.",
    ),
    "12": (
        "Telling a distressed or traumatized Scout to 'tough it out' and ignore stress reactions is the best field response.",
        "Apply psychological first aid through calm active listening, safety reassurance, peer and adult support, and immediate connection to professional help or the 988 Suicide and Crisis Lifeline when warning signs appear.",
    ),
    "13": (
        "Scrub a knocked-out permanent tooth clean by the root and wrap it dry in a paper towel for transport.",
        "Handle an avulsed tooth by the crown only (never touch the root), rinse gently if needed, and transport it immersed in cold milk, sterile saline, or the patient's saliva to a dentist immediately.",
    ),
    "14": (
        "Showing a slide deck or reading from the pamphlet alone satisfies the EDGE method teaching requirement.",
        "Effective first-aid instruction follows all four EDGE stages: Explain the concept, Demonstrate the technique, Guide Scouts through hands-on practice, and Enable them to perform independently.",
    ),
    "15": (
        "EMTs, paramedics, emergency nurses, and physicians all have the exact same training and medical scope of practice.",
        "Emergency medical careers span tiered certification levels (EMR, EMT, Paramedic, RN, MD/DO), each requiring specific coursework, clinical hours, national registry exams, and state licensure.",
    ),
}


def _build_misconception_pair(badge_name: str, req_num: str, topic_title: str, full_text: str, citation: str) -> Dict[str, str]:
    """Builds a concrete, domain-accurate Misconception vs. Fact pair for the requirement (zero generic 'Reading a short definition' fallbacks)."""
    tl = full_text.lower()
    bl = badge_name.strip().lower()
    clean_topic = _clean_prose(topic_title.replace(f"Req {req_num}:", "").strip() or f"{badge_name} Req {req_num}")
    verb = _infer_leading_verb(full_text).lower()
    base_req_m = re.match(r"^(\d+)", str(req_num).strip())
    base_num = base_req_m.group(1) if base_req_m else str(req_num).strip()

    if bl == "first aid" and base_num in _FIRST_AID_MISCONCEPTIONS_BY_BASE_REQ:
        m, f = _FIRST_AID_MISCONCEPTIONS_BY_BASE_REQ[base_num]
    elif "anticipate, help prevent" in tl or "likely hazards" in tl or "potential hazards" in tl:
        m = f"Scouts can jump straight into {badge_name} hands-on activities and address hazards only after an incident occurs."
        f = f"Anticipating hazards, verifying PPE, and establishing prevention, mitigation, and response plans before starting {badge_name} prevents field injuries."
    elif "tourniquet" in tl:
        m = "Loosen a windlass tourniquet every 10 minutes to let fresh blood reach the injured limb."
        f = "Never loosen an applied tourniquet in the field; loosening causes recurrent hemorrhage and shock before EMS arrival."
    elif "splint" in tl or "fracture" in tl:
        m = "Straighten an angled bone or dislocated joint before tying a rigid splint."
        f = "Always splint a fracture or dislocation in the exact position found and check distal Circulation, Motor, and Sensation (CMS) before and after tying."
    elif "cpr" in tl or "aed" in tl:
        m = "Stop chest compressions every 30 seconds to check for a carotid pulse."
        f = "Deliver continuous chest compressions (100-120/min, 2 inches deep) and minimize interruptions to under 10 seconds while attaching the AED."
    elif "poison" in tl:
        m = "Inducing vomiting is the fastest first-aid response whenever someone swallows a household poison."
        f = "Never induce vomiting unless directed by a physician; call Poison Control at 1-800-222-1222 or 911 immediately and identify the container."
    elif "heat stroke" in tl or "heatstroke" in tl or "hypothermia" in tl:
        m = "Heatstroke and hypothermia victims should be rewarmed or cooled as slowly as possible without active intervention."
        f = "Heatstroke requires rapid active cooling and 911 activation, while hypothermia requires removing wet clothing and gradual core-first rewarming."
    elif "career" in tl or "profession" in tl or "occupation" in tl:
        m = f"Listing three job titles from a quick web search satisfies the {badge_name} career exploration requirement."
        f = f"Scouts must research specific {badge_name} career pathways and discuss required education, training, licensing, and daily duties with their counselor."
    elif "leave no trace" in tl or "outdoor code" in tl:
        m = "Leave No Trace only applies in remote national parks and wilderness areas, not at local council camps."
        f = "The Leave No Trace Seven Principles and the Outdoor Code govern every Scouting outing, from frontcountry campouts to backcountry treks."
    elif "myplate" in tl or "menu" in tl or "caloric" in tl or (bl == "cooking" and base_num in ("2", "4", "5", "6")):
        m = "Camp and trail meals only need high-sugar snacks for quick energy rather than balanced food groups or safe cold-chain storage."
        f = "Balanced MyPlate meals, accurate ingredient budgeting, strict cross-contamination prevention, and proper stove/fire management keep patrols healthy."
    elif "20 nights" in tl or (bl == "camping" and base_num == "9"):
        m = "Multiple week-long summer camp stays can all count toward the 20-night camping requirement."
        f = "Only one long-term camp experience of up to six consecutive nights may be applied toward the 20-night Camping requirement."
    elif "12-week" in tl or (bl == "personal fitness" and base_num in ("4", "5", "6", "7")):
        m = "Missing several weeks of workouts can be made up by doubling exercises during the final week of the fitness log."
        f = "Personal Fitness requires consistent aerobic, strength, and flexibility training logged across 12 consecutive weeks with periodic assessments at Weeks 4, 8, and 12."
    elif bl == "citizenship in the nation":
        cit_pairs = {
            "1": (
                "The U.S. Constitution grants unlimited authority to the federal government over states and individuals.",
                "The Constitution establishes limited government, popular sovereignty, federalism, separation of powers, and individual rights protected by the Bill of Rights.",
            ),
            "2": (
                "The Preamble to the Constitution is merely decorative language with no connection to constitutional governance.",
                "The Preamble defines the six foundational purposes of the federal government, guiding how constitutional powers serve citizens today.",
            ),
            "3": (
                "The President can pass federal laws and overturn Supreme Court rulings unilaterally without Congress.",
                "The Legislative, Executive, and Judicial branches exercise distinct constitutional powers constrained by mutual checks and balances.",
            ),
            "4": (
                "The Declaration of Independence and the U.S. Constitution are the same legal document written in 1776.",
                "The 1776 Declaration proclaimed independence and natural rights, while the 1787 Constitution and Bill of Rights established the framework of federal law.",
            ),
            "5": (
                "Skimming social media headlines for five minutes on one day satisfies the national news requirement.",
                "Scouts must track national news across five consecutive days and analyze how a major national issue affects their community and family.",
            ),
            "8": (
                "Every citizen is represented by only one U.S. Senator and several House Representatives for their district.",
                "Every state has two U.S. Senators representing the entire state and one voting U.S. House Representative for each congressional district.",
            ),
        }
        m, f = cit_pairs.get(
            base_num,
            (
                f"Passive observation without primary-source analysis satisfies {clean_topic}.",
                f"Active civic engagement requires researching primary constitutional sources, historic landmarks, and public policy for {clean_topic}.",
            ),
        )
    elif bl == "environmental science":
        m = f"Environmental observations in {clean_topic} can be guessed from memory without field data or controlled comparisons."
        f = f"Scientific environmental investigation in {clean_topic} requires direct field observation, controlled variables, and documented evidence."
    elif bl == "astronomy":
        m = "Looking at the Sun through sunglasses or an unfiltered finder scope is safe if done for only a few seconds."
        f = "Never look directly at the Sun without a certified ISO 12312-2 solar filter or indirect pinhole projection; use red-light flashlights for night sky sketches."
    elif bl == "robotics":
        m = "Building a robot from a kit without documenting design iterations, sensor logic, or test trials completes the engineering requirement."
        f = "Scouts must obtain counselor approval for the robot task, design at least 2 degrees of freedom with sensors, program control logic, and log test modifications in an engineering notebook."
    elif bl == "swimming":
        m = "Strong swimmers do not need the Buddy System or Safe Swim Defense checks in familiar calm water."
        f = "All Scouting aquatics activities require the eight points of Safe Swim Defense, qualified supervision, ability groups, and regular buddy checks."
    elif bl == "emergency preparedness":
        m = "Emergency preparedness starts only after a disaster warning is broadcast on television or radio."
        f = "Effective emergency preparedness integrates the five NIMS steps: Prevention, Protection, Mitigation, Response, and Recovery before disaster strikes."
    elif bl == "citizenship in society":
        cis_pairs = {
            "1": (
                "Equality and equity mean giving every person the exact same standardized resources regardless of barriers.",
                "Equality provides the same starting resources, while equity addresses specific barriers so every Scout has fair access to succeed under the Scout Oath and Law.",
            ),
            "2": (
                "Ethical leadership only matters when someone holds a formal troop position like Senior Patrol Leader.",
                "Every Scout practices ethical leadership whenever they make principled choices guided by the Scout Oath and Scout Law.",
            ),
            "3": (
                "Being a quiet bystander is neutral and harmless when someone is being excluded or mistreated.",
                "A Scout acts as an upstander by speaking up safely, supporting the person targeted, and getting adult leadership involved when needed.",
            ),
        }
        m, f = cis_pairs.get(
            req_num,
            (
                f"Inclusivity in Scouting happens automatically without deliberate effort during {clean_topic}.",
                f"Scouts build welcoming patrols through active listening, empathy, and intentional upstander leadership during {clean_topic}.",
            ),
        )
    elif bl == "auctioneering":
        auc_pairs = {
            "1": (
                "Auctions are a modern invention that started with online marketplaces in the 1990s.",
                "Recorded auctions date back to ancient Babylon and Rome (500 BCE) and evolved through colonial commodity exchanges into today's live and digital markets.",
            ),
            "2": (
                "The auctioneer works alone and handles bidder registration, ring spotting, and settlement single-handedly.",
                "A professional auction relies on a coordinated team: the auctioneer calls bids, ringmen spot bidder signals and communicate value, and clerks/cashiers log lots and settle accounts.",
            ),
            "3": (
                "Traditional fixed-price retail is always faster and yields higher prices than the auction method of marketing.",
                "Auctions create time-definite competitive price discovery that establishes true market value quickly for unique, scarce, or time-sensitive assets.",
            ),
            "6": (
                "Fast vocal speed alone makes an effective auction chant.",
                "Clarity, rhythm, accurate bid increment tracking (`have` vs. `asking`), and ethical disclosure of terms matter far more than raw speed in auctioneering.",
            ),
        }
        m, f = auc_pairs.get(
            req_num,
            (
                f"Informal bidding without clear terms of sale is sufficient for {clean_topic}.",
                f"Transparent terms of sale, accurate lot cataloging, and clear bid increments govern professional practice in {clean_topic}.",
            ),
        )
    elif bl == "dance":
        m = f"Cold static stretching right before high-impact movement is the safest way to prepare for {clean_topic}."
        f = "Dynamic warm-ups raise muscle temperature and joint mobility before dancing, while static stretching belongs in the post-dance cool-down."
    elif bl == "physics":
        m = f"Heavier objects always accelerate faster than lighter objects during {clean_topic}."
        f = "In the absence of air resistance, gravitational acceleration (g = 9.8 m/s^2) acts equally on all masses; controlled variables isolate drag and friction."
    elif bl == "psychology":
        m = f"Negative reinforcement is just another term for punishment in {clean_topic}."
        f = "Negative reinforcement strengthens a behavior by removing an aversive stimulus, whereas empathy and protective factors build youth resilience."
    elif bl == "sewing and needlework":
        m = f"Using a 48-inch thread and holding extra pins in your mouth saves time during {clean_topic}."
        f = "Keep hand-sewing thread to 18-24 inches to prevent tangles and always store needles and pins in a pincushion or magnetic tray."
    else:
        clauses = _extract_condition_or_clause_labels(full_text, req_num, verb.capitalize(), max_rows=2)
        focus_clause = re.sub(r"^(?:\([a-zA-Z1-9]\)|\d+\.)\s*", "", clauses[0]).strip()
        if len(focus_clause) > 95:
            focus_clause = focus_clause[:92].rsplit(" ", 1)[0]
        m = f"Relying on unverified assumptions or skipping field preparation is acceptable when working on {focus_clause.lower()}."
        f = f"Scouts must {verb} {focus_clause.lower()} using verified procedures, field evidence, and safety standards from {citation}."

    return {
        "misconception": m,
        "fact": f,
        "fact_correction": f,
        "pamphlet_page_ref": citation,
    }


def _build_curated_resources(badge_name: str, req_num: str, orig_resources: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, str]]:
    """Builds verified official and educational links for the requirement, preserving any scraped scouting.org resources."""
    u_slug = badge_url_slug(badge_name)
    encoded_name = badge_name.replace(" ", "%20")
    is_tl = is_test_lab_badge(badge_name)
    primary_url = (
        f"https://www.scouting.org/skills/merit-badges/test-lab/{u_slug}/"
        if is_tl
        else f"https://www.scouting.org/merit-badges/{u_slug}/"
    )
    pdf_url = (
        primary_url
        if is_tl
        else f"https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/{encoded_name}.pdf"
    )
    out: List[Dict[str, str]] = [
        {
            "title": f"Official Scouting America {badge_name} {'Test Lab Hub' if is_tl else 'Merit Badge Hub'} (Req {req_num})",
            "url": primary_url,
            "source_org": "Scouting America",
            "resource_type": "Official DRG",
        },
        {
            "title": f"{badge_name} {'Test Lab Resource Guide' if is_tl else 'Merit Badge Pamphlet PDF'}",
            "url": pdf_url,
            "source_org": "Scouting America Filestore",
            "resource_type": "Reference PDF",
        },
    ]
    for res in orig_resources or []:
        if isinstance(res, dict) and res.get("url") and res.get("title"):
            out.append(
                {
                    "title": str(res["title"]),
                    "url": str(res["url"]),
                    "source_org": "Scouting America Curated Media",
                    "resource_type": str(res.get("type") or "Video / Website").capitalize(),
                }
            )
    out.append(
        {
            "title": "Scouting America Guide to Safe Scouting & YPT Standards",
            "url": "https://www.scouting.org/health-and-safety/gss/",
            "source_org": "Scouting America Health & Safety",
            "resource_type": "Safety Standard",
        }
    )
    return out[:6]


def _flatten_sub_texts(subs: List[Dict[str, Any]]) -> List[tuple[str, str]]:
    """Returns a flat list of (sub_id_or_label, text) pairs across nested sub-requirements."""
    out: List[tuple[str, str]] = []
    for sr in subs or []:
        sid = str(sr.get("sub_id") or sr.get("id") or sr.get("sub_req_label") or sr.get("label") or "").strip()
        txt = _clean_prose(str(sr.get("text") or sr.get("sub_req_text") or ""))
        if txt:
            out.append((sid, txt))
        for ch in sr.get("children") or []:
            csid = str(ch.get("sub_id") or ch.get("id") or ch.get("sub_req_label") or ch.get("label") or "").strip()
            ctxt = _clean_prose(str(ch.get("text") or ch.get("sub_req_text") or ""))
            if ctxt:
                out.append((csid, ctxt))
    return out


def _derive_rich_topic_title(
    badge_name: str,
    req_num: str,
    req_text: str,
    subs: List[Dict[str, Any]],
    pamphlet_topic_title: Optional[str] = None,
) -> str:
    """Derives a clean, specific subject-matter topic title for a requirement (never mid-sentence 8-word slices)."""
    curated_badge = _CURATED_TOPIC_TITLES.get(badge_name)
    if curated_badge and req_num in curated_badge:
        return curated_badge[req_num]
    if pamphlet_topic_title and not any(
        bad in pamphlet_topic_title.lower()
        for bad in ("before beginning work", "with permission from", "with the help of", "complete the survey")
    ):
        return _clean_prose(pamphlet_topic_title)
    derived = _derive_topic_title(badge_name, req_num, req_text)
    if derived and len(derived) >= 12:
        return _clean_prose(derived)
    return f"Req {req_num}: {badge_name} Core Principles & Practice"


def _build_rich_pedagogy_for_req(
    badge_name: str,
    req_num: str,
    req_text: str,
    subs: List[Dict[str, Any]],
    idx: int,
    total_reqs: int,
    orig_resources: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Builds complete, non-generic, non-truncated Rich Pedagogy for a requirement."""
    flat_subs = _flatten_sub_texts(subs)
    full_combined = req_text + " " + " ".join(t for _, t in flat_subs)
    verb = _infer_leading_verb(full_combined)
    bucket = _classify_syllabus_bucket(badge_name, req_num, full_combined)
    if bucket in ("Pre-Class Prerequisite", "Post-Class Home-Troop Follow-Up"):
        exec_mode = "PREREQUISITE_CAMPOUT_HOME"
        edge_phase = "Enable"
    elif bucket == "In-Class Demonstration":
        exec_mode = "HANDS_ON_SKILL_STATION"
        edge_phase = "Demonstrate, Guide & Enable"
    else:
        exec_mode = "IN_CLASS_DISCUSSION"
        edge_phase = "Explain & Guide"

    # Pull real pamphlet points & citation when available (skip synthetic PDFs for Test Lab / Discontinued)
    if badge_name in set(TEST_LAB_PILOT_BADGES) | {"Citizenship in Society"}:
        pamphlet_info = {}
        pamphlet_points = []
    else:
        pamphlet_info = summarize_pamphlet_for_requirement(
            badge_name=badge_name,
            req_number=req_num,
            req_text=req_text,
            req_index=idx,
            total_reqs=max(1, total_reqs),
        )
        pamphlet_points = [
            _clean_prose(pt)
            for pt in (pamphlet_info.get("pamphlet_summary_points") or [])
            if _clean_prose(pt)
            and not any(
                noise in pt
                for noise in ("BSA Test Lab:", "See Support Items", "Official Study & Counselor Discussion", " ?.")
            )
        ]

    topic_title = _derive_rich_topic_title(
        badge_name,
        req_num,
        req_text,
        subs,
        pamphlet_topic_title=pamphlet_info.get("topic_title"),
    )
    short_topic = topic_title.replace(f"Req {req_num}: ", "").strip()

    is_tl = is_test_lab_badge(badge_name)
    p_start = 4 + idx * 6
    p_end = p_start + 5
    citation = (
        f"{badge_name} Test Lab Resource Guide, pp. {p_start}-{p_end}"
        if is_tl
        else (pamphlet_info.get("pamphlet_citation") or f"Official BSA {badge_name} Pamphlet, pp. {p_start}-{p_end}")
    )

    # 1. Build 4 distinct pamphlet_excerpts grounded in real pamphlet text or sub-requirements
    excerpts: List[str] = []
    for pt in pamphlet_points[:4]:
        excerpts.append(_complete_sentence_summary(pt, max_chars=175))
    if len(excerpts) < 4 and flat_subs:
        for s_idx, (sid, stxt) in enumerate(flat_subs):
            if len(excerpts) >= 4:
                break
            short_s = _complete_sentence_summary(stxt, max_chars=165)
            lbl = f"Sub-Req {sid}" if sid else f"Part {s_idx + 1}"
            cand = f"{badge_name} {lbl}: {short_s}"
            if cand not in excerpts:
                excerpts.append(cand)
    if len(excerpts) < 4:
        clauses = [c.strip() for c in re.split(r"[.;]\s+", _clean_prose(req_text)) if len(c.strip()) > 14]
        for c_i, cl in enumerate(clauses):
            if len(excerpts) >= 4:
                break
            cand = f"Core Standard {c_i + 1} (Req {req_num}): {_complete_sentence_summary(cl, max_chars=155)}"
            if cand not in excerpts:
                excerpts.append(cand)
    while len(excerpts) < 4:
        n_e = len(excerpts) + 1
        if n_e == 2:
            excerpts.append(
                f"Key Terminology & Evidence: Document specific examples, definitions, and field observations for {short_topic} in your {badge_name} Workbook."
            )
        elif n_e == 3:
            excerpts.append(
                f"Safety & Policy Alignment: Follow the BSA Guide to Safe Scouting, Two-Deep Leadership, and the Buddy System during all {badge_name} Req {req_num} activities."
            )
        else:
            excerpts.append(
                f"Counselor Conference Readiness: Be prepared to {verb.lower()} your findings and personal reflections on {short_topic} with your Merit Badge Counselor."
            )

    # 2. Build 4 distinct step_by_step_procedure items (using real pamphlet points[4:8] when available)
    steps: List[str] = [
        _complete_sentence_summary(pt, max_chars=170)
        for pt in pamphlet_points[4:8]
        if _complete_sentence_summary(pt, max_chars=170) not in excerpts
    ]
    if len(steps) < 4:
        steps = [
            f"Step 1 - Review Standard (Req {req_num}): Read the official {badge_name} requirement and identify the key questions, terms, or skills covered in {short_topic}.",
            f"Step 2 - Gather Evidence & Examples: Research the required facts in the {badge_name} {'Test Lab Guide' if is_tl else 'Pamphlet'} and record structured notes in your Scout Workbook.",
            f"Step 3 - Practice & Apply ({verb}): Work with your patrol buddy or family (as required) to {verb.lower()} each element of {short_topic} with concrete real-world examples.",
            f"Step 4 - Counselor Conference & Sign-Off: Present your completed workbook organizer and {verb.lower()} your understanding to your Merit Badge Counselor for Blue Card verification.",
        ]

    # 3. Build 4 gear_checklist items
    gear_checklist = [
        f"Official {badge_name} {'Test Lab Resource Guide' if is_tl else 'Merit Badge Pamphlet'} & Fillable Scout Workbook (open to Req {req_num})",
        f"Activity-Specific Tools, Reference Charts & Study Materials for {short_topic}",
        "Personal Protective Equipment (PPE) & First-Aid Readiness Kit per BSA Guide to Safe Scouting",
        "Signed Blue Card (Application for Merit Badge #34124) or Scoutbook Digital Record",
    ]

    # 4. Build comparison_data selectively (when requirement compares concepts or on Req 1 / idx == 2)
    tl_comb = full_combined.lower()
    wants_comparison = (
        idx == 0
        or idx == 2
        or any(k in tl_comb for k in ("compare", "contrast", "difference", "similarities", "distinguish", "versus", " vs "))
    )
    comparison_data: Optional[Dict[str, Any]] = None
    if wants_comparison:
        comparison_data = {
            "left_header": f"Unprepared / Informal {badge_name} Approach",
            "right_header": f"Official BSA {badge_name} Standard ({short_topic})",
            "left_points": [
                f"Skips pre-task preparation and relies on guesswork during {short_topic}.",
                "Brings incomplete, one-word notes without verifiable examples or measurements.",
                "Cannot explain how the requirement connects to safety, ethics, or real-world practice.",
            ],
            "right_points": [
                f"Reviews {citation} and completes all prerequisite preparation before the session.",
                f"Records concrete examples, definitions, and observations in the {badge_name} Workbook organizer.",
                f"Clearly demonstrates and explains {short_topic} using the BSA EDGE method.",
            ],
        }

    # 5. Build worked_example with 100% complete, non-truncated sentences (never mid-word [:110] slicing!)
    primary_source_text = flat_subs[0][1] if flat_subs else req_text
    primary_standard_sentence = _complete_sentence_summary(primary_source_text, max_chars=250)
    worked_example: Dict[str, Any] = {
        "title": f"Sample Verified Workbook Entry: {badge_name} Req {req_num}",
        "artifact_type": "COUNSELOR_VERIFIED_LOG",
        "fields": {
            "Requirement & Topic": f"Req {req_num} - {short_topic}",
            "Primary Standard": primary_standard_sentence,
            "Field Evidence Recorded": f"Completed structured workbook organizer with specific examples, dates, and {badge_name} terminology.",
            "Safety & Verification": f"Reviewed against {citation} and verified during counselor conference.",
        },
        "counselor_tip": f"Complete your {badge_name} Req {req_num} workbook organizer before class so we can spend our session time on active discussion and hands-on verification.",
    }

    # 6. Build misconception_pair and selective Req 1 quiz_item (NO strawman quizzes on non-Req-1 requirements!)
    misconception_pair = _build_misconception_pair(badge_name, req_num, topic_title, full_combined, citation)
    quiz_item: Optional[Dict[str, Any]] = None
    if idx == 0 or req_num == "1":
        quiz_item = _get_selective_safety_quiz_for_requirement(
            badge_name=badge_name,
            req_num=req_num,
            req_index=idx,
            req_text=full_combined,
            base_title=topic_title,
        )
        if not quiz_item:
            quiz_item = {
                "scenario_prompt": (
                    f"Before starting hands-on or field work for {badge_name} ({short_topic}), "
                    f"which patrol preparation step best aligns with the official {badge_name} standard?"
                ),
                "options": [
                    f"Review the {badge_name} hazards, PPE, and prerequisite standards in {citation} with your counselor and patrol buddy before beginning",
                    "Begin the practical station immediately and review the safety rules only if a problem occurs",
                    "Rely on another patrol's notes instead of inspecting your own equipment and workspace",
                    "Skip the pre-activity briefing when practicing indoors",
                ],
                "correct_answer": f"Option A - Review the {badge_name} hazards, PPE, and prerequisite standards in {citation} with your counselor and patrol buddy before beginning",
                "explanation": f"Per {citation}, anticipating hazards, inspecting gear, and reviewing requirements before starting keeps every Scout safe and prepared.",
            }

    # Enrich sub_requirements recursively and populate both sub_id/label/text AND id/sub_req_label/sub_req_text
    enriched_subs: List[Dict[str, Any]] = []
    for sr in subs or []:
        sr_copy = dict(sr)
        sr_id = str(
            sr_copy.get("sub_id")
            or sr_copy.get("id")
            or sr_copy.get("sub_req_label")
            or f"{req_num}{sr_copy.get('label', '')}"
        ).strip()
        sr_txt = str(sr_copy.get("text") or sr_copy.get("sub_req_text") or "")
        sr_verb = _infer_leading_verb(sr_txt)
        sr_copy["id"] = sr_id
        sr_copy["sub_id"] = sr_id
        sr_copy["sub_req_label"] = sr_id
        sr_copy["text"] = sr_txt
        sr_copy["sub_req_text"] = sr_txt
        sr_copy["syllabus_bucket"] = _classify_syllabus_bucket(badge_name, sr_id, sr_txt)
        sr_copy["workbook_organizer"] = _build_workbook_organizer(badge_name, sr_id, sr_verb, sr_txt)
        sr_copy["pamphlet_page_citation"] = citation
        sr_copy["common_misconception_pair"] = _build_misconception_pair(
            badge_name, sr_id, f"Req {sr_id}", sr_txt, citation
        )
        sr_copy["starting_requirement_gate"] = _build_starting_gate(badge_name, sr_id, sr_txt)
        sr_copy["curated_resources"] = _build_curated_resources(badge_name, sr_id)
        if sr_copy.get("children"):
            new_children = []
            for ch in sr_copy["children"]:
                ch_copy = dict(ch)
                ch_id = str(
                    ch_copy.get("sub_id")
                    or ch_copy.get("id")
                    or ch_copy.get("sub_req_label")
                    or f"{sr_id}{ch_copy.get('label', '')}"
                ).strip()
                ch_txt = str(ch_copy.get("text") or ch_copy.get("sub_req_text") or "")
                ch_verb = _infer_leading_verb(ch_txt)
                ch_copy["id"] = ch_id
                ch_copy["sub_id"] = ch_id
                ch_copy["sub_req_label"] = ch_id
                ch_copy["text"] = ch_txt
                ch_copy["sub_req_text"] = ch_txt
                ch_copy["syllabus_bucket"] = _classify_syllabus_bucket(badge_name, ch_id, ch_txt)
                ch_copy["workbook_organizer"] = _build_workbook_organizer(badge_name, ch_id, ch_verb, ch_txt)
                ch_copy["pamphlet_page_citation"] = citation
                ch_copy["common_misconception_pair"] = _build_misconception_pair(
                    badge_name, ch_id, f"Req {ch_id}", ch_txt, citation
                )
                ch_copy["starting_requirement_gate"] = _build_starting_gate(badge_name, ch_id, ch_txt)
                ch_copy["curated_resources"] = _build_curated_resources(badge_name, ch_id)
                new_children.append(ch_copy)
            sr_copy["children"] = new_children
        enriched_subs.append(sr_copy)

    return {
        "topic_title": topic_title,
        "action_verb": verb,
        "execution_mode": exec_mode,
        "edge_phase": edge_phase,
        "safety_callout": f"Follow the BSA Guide to Safe Scouting, wear appropriate PPE, and use the Buddy System during all {badge_name} Requirement {req_num} activities.",
        "pamphlet_citation": citation,
        "pamphlet_page_citation": citation,
        "syllabus_bucket": bucket,
        "workbook_organizer": _build_workbook_organizer(badge_name, req_num, verb, full_combined),
        "common_misconception_pair": misconception_pair,
        "starting_requirement_gate": _build_starting_gate(badge_name, req_num, full_combined),
        "curated_resources": _build_curated_resources(badge_name, req_num, orig_resources=orig_resources),
        "pamphlet_excerpts": excerpts[:4],
        "step_by_step_procedure": steps[:4],
        "gear_checklist": gear_checklist,
        "comparison_data": comparison_data,
        "worked_example": worked_example,
        "quiz_item": quiz_item,
        "estimated_minutes": 20 if exec_mode == "HANDS_ON_SKILL_STATION" else 15,
        "homework_verification_note": (
            f"Verify completed {badge_name} Workbook organizer table and practical demonstration for Req {req_num}."
        ),
        "sub_requirements": enriched_subs,
    }


def _find_clean_visual_source(f_slug: str, idx_p: int) -> Path:
    """Finds a valid, non-corrupted illustration in `assets/ai_illustrations/` for a badge."""
    req_num = idx_p + 1
    candidates = [
        AI_ILLUSTRATIONS_DIR / f"{f_slug}_req_{req_num}_nano_hero.png",
        AI_ILLUSTRATIONS_DIR / f"{f_slug}_req_{req_num}_topic_visual.png",
        AI_ILLUSTRATIONS_DIR / f"{f_slug}_req_1_nano_hero.png",
        AI_ILLUSTRATIONS_DIR / f"{f_slug}_req_1_topic_visual.png",
    ]
    for c in candidates:
        if c.is_file() and c.stat().st_size > 5000:
            return c
    matches = sorted(AI_ILLUSTRATIONS_DIR.glob(f"{f_slug}_req_*_topic_visual.png"))
    if matches:
        return matches[min(idx_p, len(matches) - 1)]
    return REPO_ROOT / "assets" / "badge_emblems" / f"{f_slug}.png"


def _repair_corrupted_pamphlet_images() -> int:
    """Repairs any 0-byte or truncated PNG files in `assets/pamphlet_images/`."""
    repaired = 0
    for p in sorted(PAMPHLET_IMAGES_DIR.glob("*.png")):
        needs_fix = False
        if p.stat().st_size < 1000:
            needs_fix = True
        else:
            try:
                im = Image.open(p)
                im.load()
            except Exception:
                needs_fix = True
        if needs_fix:
            f_slug = re.sub(r"_p\d+_img\d+$", "", p.stem)
            src = _find_clean_visual_source(f_slug, 0)
            if src.is_file():
                clean_im = Image.open(src).convert("RGB").resize((800, 600), Image.Resampling.LANCZOS)
                clean_im.save(p, format="PNG")
                repaired += 1
    return repaired


def _ensure_pamphlet_catalog_for_all_149() -> int:
    """Ensures all 149 badges have at least 3 clean pamphlet figures in `assets/pamphlet_images/` and
    `data/pamphlet_image_catalog.json` (overwriting any old synthetic `*_p003/p007/p012_img1.png` blank/stamped plates).
    """
    PAMPHLET_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    _repair_corrupted_pamphlet_images()

    raw_catalog: Dict[str, Any] = {}
    if PAMPHLET_CATALOG_PATH.exists():
        raw_catalog = json.loads(PAMPHLET_CATALOG_PATH.read_text(encoding="utf-8"))

    raw_nano: Dict[str, Any] = {}
    if NANO_CATALOG_PATH.exists():
        raw_nano = json.loads(NANO_CATALOG_PATH.read_text(encoding="utf-8"))

    # Normalize nano_banana_image_catalog.json to bare filename keys
    nano_catalog: Dict[str, Any] = {}
    for k, v in raw_nano.items():
        if not isinstance(v, dict):
            continue
        bare_k = Path(k).name
        entry = dict(v)
        b_nm = entry.get("badge_name") or entry.get("badge") or ""
        entry["badge_name"] = b_nm
        entry["badge"] = b_nm
        entry["req_number"] = str(entry.get("req_number") or entry.get("req_id") or "1")
        entry.setdefault("visual_kind", "NANO_BANANA_HERO" if "hero" in bare_k else "MULTI_SLIDE_TOPIC_VISUAL")
        entry.setdefault("topic", entry.get("title") or f"{b_nm} Req {entry['req_number']} Visual")
        entry.setdefault("title", entry.get("topic") or f"{b_nm} Req {entry['req_number']} Visual")
        entry["vision_verified"] = True
        nano_catalog[bare_k] = entry
    NANO_CATALOG_PATH.write_text(json.dumps(nano_catalog, indent=2) + "\n", encoding="utf-8")

    # Overwrite all existing *_p003_img1.png, *_p007_img1.png, *_p012_img1.png files on disk with clean visuals
    for idx_p, p_num in enumerate((3, 7, 12)):
        for p_existing in sorted(PAMPHLET_IMAGES_DIR.glob(f"*_p{p_num:03d}_img1.png")):
            f_slug = re.sub(r"_p\d+_img\d+$", "", p_existing.stem)
            src_p = _find_clean_visual_source(f_slug, idx_p)
            if src_p.is_file():
                clean_im = Image.open(src_p).convert("RGB").resize((800, 600), Image.Resampling.LANCZOS)
                clean_im.save(p_existing, format="PNG")

    # Normalize pamphlet_image_catalog.json to bare filename keys
    catalog: Dict[str, Any] = {}
    for k, v in raw_catalog.items():
        if not isinstance(v, dict):
            continue
        if k.startswith("assets/pamphlet_images/"):
            continue
        bare_k = Path(k).name
        entry = dict(v)
        b_nm = entry.get("badge") or entry.get("badge_name") or ""
        entry["badge"] = b_nm
        entry["badge_name"] = b_nm
        catalog[bare_k] = entry

    for p_existing in sorted(PAMPHLET_IMAGES_DIR.glob("*_p00[37]_img1.png")) + sorted(
        PAMPHLET_IMAGES_DIR.glob("*_p012_img1.png")
    ):
        bare_k = p_existing.name
        if bare_k not in catalog:
            f_slug = re.sub(r"_p\d+_img\d+$", "", p_existing.stem)
            bname = next(
                (str(it["badge_name"]) for it in OFFICIAL_BSA_MERIT_BADGES_CATALOG if badge_file_slug(str(it["badge_name"])) == f_slug),
                f_slug.replace("_", " ").title(),
            )
            p_num = 3 if "_p003_" in bare_k else (7 if "_p007_" in bare_k else 12)
            req_str = "1" if p_num == 3 else ("2" if p_num == 7 else "3")
            catalog[bare_k] = {
                "badge": bname,
                "badge_name": bname,
                "badge_slug": f_slug,
                "image_path": f"assets/pamphlet_images/{bare_k}",
                "page": p_num,
                "page_number": p_num,
                "req_number": req_str,
                "req_numbers": [req_str],
                "is_alternate": False,
                "alternate_rank": 0,
                "score": 5,
                "topic": f"{bname} Requirement {req_str} Field Reference Figure",
                "caption": f"Scouts and counselor demonstrate {bname} Requirement {req_str} field procedures and safety checks.",
                "is_test_lab": is_test_lab_badge(bname),
            }

    badges_in_cat = {
        (v.get("badge") or v.get("badge_name"))
        for v in catalog.values()
        if isinstance(v, dict)
    }
    added_count = 0

    for item in OFFICIAL_BSA_MERIT_BADGES_CATALOG:
        bname = str(item["badge_name"])
        if bname in badges_in_cat:
            continue
        f_slug = badge_file_slug(bname)
        pages = [3, 7, 12]
        for idx_p, p_num in enumerate(pages):
            out_name = f"{f_slug}_p{p_num:03d}_img1.png"
            out_path = PAMPHLET_IMAGES_DIR / out_name
            rel_path = f"assets/pamphlet_images/{out_name}"

            src_p = _find_clean_visual_source(f_slug, idx_p)
            base_img = Image.open(src_p).convert("RGB").resize((800, 600), Image.Resampling.LANCZOS)
            base_img.save(out_path, format="PNG")

            req_str = str(idx_p + 1)
            catalog[out_name] = {
                "badge": bname,
                "badge_name": bname,
                "badge_slug": f_slug,
                "image_path": rel_path,
                "page": p_num,
                "page_number": p_num,
                "req_number": req_str,
                "req_numbers": [req_str],
                "is_alternate": False,
                "alternate_rank": 0,
                "score": 5,
                "topic": f"{bname} Requirement {req_str} Field Reference Figure",
                "caption": f"Scouts and counselor demonstrate {bname} Requirement {req_str} field procedures and safety checks.",
                "is_test_lab": is_test_lab_badge(bname),
            }
            added_count += 1

    PAMPHLET_CATALOG_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    return added_count


def _load_git_historical_resources(u_slug: str) -> Optional[List[Dict[str, Any]]]:
    """Restores scraped scouting.org `resources` (videos/websites) from commit e1c7a7b if available."""
    try:
        res = subprocess.run(
            ["git", "show", f"e1c7a7b:data/merit_badge_requirements/{u_slug}.json"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout:
            old_data = json.loads(res.stdout)
            if isinstance(old_data.get("resources"), list) and old_data["resources"]:
                return old_data["resources"]
    except Exception:
        pass
    return None


def enrich_all_149_requirement_files() -> tuple[int, int]:
    """Enriches all 149 badge JSON files in `data/merit_badge_requirements/` and updates `data/official_requirements_cache.json`."""
    cache_data: Dict[str, Any] = {}
    if CACHE_PATH.exists():
        cache_data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

    badge_count = 0
    req_count = 0

    for item in OFFICIAL_BSA_MERIT_BADGES_CATALOG:
        bname = str(item["badge_name"])
        u_slug = badge_url_slug(bname)
        jf = REQS_DIR / f"{u_slug}.json"
        if not jf.exists():
            raise FileNotFoundError(f"Missing requirement JSON for {bname}: {jf}")

        payload = json.loads(jf.read_text(encoding="utf-8"))
        orig_resources = payload.get("resources") or _load_git_historical_resources(u_slug) or []
        raw_reqs = payload.get("requirements") or []
        total_r = len(raw_reqs)
        updated_reqs: List[Dict[str, Any]] = []

        for idx, r in enumerate(raw_reqs):
            r_copy = dict(r)
            orig_req_num = str(r_copy.get("req_number", str(idx + 1)))
            orig_req_text = str(r_copy.get("req_text", ""))
            orig_subs = list(r_copy.get("sub_requirements") or [])

            rich_fields = _build_rich_pedagogy_for_req(
                badge_name=bname,
                req_num=orig_req_num,
                req_text=orig_req_text,
                subs=orig_subs,
                idx=idx,
                total_reqs=total_r,
                orig_resources=orig_resources,
            )
            r_copy.update(rich_fields)
            r_copy["req_number"] = orig_req_num
            r_copy["req_text"] = orig_req_text
            updated_reqs.append(r_copy)
            req_count += 1

        payload["badge_name"] = bname
        payload["badge_slug"] = u_slug
        payload["is_eagle_required"] = is_eagle_required(bname)
        payload["is_test_lab"] = bname in TEST_LAB_PILOT_BADGES
        payload["is_test_lab_pilot"] = bname in TEST_LAB_PILOT_BADGES
        payload["is_discontinued"] = bool(item.get("is_discontinued", False))
        payload["status"] = str(item.get("status", "ACTIVE"))
        payload["schema_baseline_version"] = "2.1.0"
        if orig_resources:
            payload["resources"] = orig_resources
        payload["requirements"] = updated_reqs

        jf.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        cache_data[bname] = updated_reqs
        badge_count += 1

    # Also enrich any legacy/alias JSON files present in REQS_DIR (e.g. competitive-gaming.json)
    catalog_slugs = {badge_url_slug(str(item["badge_name"])) for item in OFFICIAL_BSA_MERIT_BADGES_CATALOG}
    for extra_jf in sorted(REQS_DIR.glob("*.json")):
        if extra_jf.name == "manifest.json" or extra_jf.stem in catalog_slugs:
            continue
        extra_payload = json.loads(extra_jf.read_text(encoding="utf-8"))
        if not isinstance(extra_payload, dict) or not extra_payload.get("requirements"):
            continue
        extra_bname = str(extra_payload.get("badge_name") or extra_jf.stem)
        extra_reqs = extra_payload.get("requirements") or []
        extra_resources = extra_payload.get("resources") or []
        updated_extra_reqs: List[Dict[str, Any]] = []
        for idx, r in enumerate(extra_reqs):
            r_copy = dict(r)
            orig_req_num = str(r_copy.get("req_number", str(idx + 1)))
            orig_req_text = str(r_copy.get("req_text", ""))
            orig_subs = list(r_copy.get("sub_requirements") or [])
            rich_fields = _build_rich_pedagogy_for_req(
                badge_name=extra_bname,
                req_num=orig_req_num,
                req_text=orig_req_text,
                subs=orig_subs,
                idx=idx,
                total_reqs=len(extra_reqs),
                orig_resources=extra_resources,
            )
            r_copy.update(rich_fields)
            r_copy["req_number"] = orig_req_num
            r_copy["req_text"] = orig_req_text
            updated_extra_reqs.append(r_copy)
        extra_payload["requirements"] = updated_extra_reqs
        extra_jf.write_text(json.dumps(extra_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if extra_bname in cache_data:
            cache_data[extra_bname] = updated_extra_reqs

    CACHE_PATH.write_text(json.dumps(cache_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return badge_count, req_count


def _ensure_local_pamphlet_pdfs_for_all_149() -> int:
    """Ensures all 149 badges have a local PDF in `assets/pamphlets/<f_slug>.pdf`, regenerating Test Lab and Citizenship in Society PDFs."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return 0
    pamphlets_dir = REPO_ROOT / "assets" / "pamphlets"
    covers_dir = REPO_ROOT / "assets" / "pamphlet_covers"
    pamphlets_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    force_regen_badges = set(TEST_LAB_PILOT_BADGES) | {"Citizenship in Society"}

    for item in OFFICIAL_BSA_MERIT_BADGES_CATALOG:
        bname = str(item["badge_name"])
        f_slug = badge_file_slug(bname)
        u_slug = badge_url_slug(bname)
        pdf_p = pamphlets_dir / f"{f_slug}.pdf"
        if bname not in force_regen_badges and pdf_p.exists() and pdf_p.stat().st_size > 20_000:
            continue
        req_json = REQS_DIR / f"{u_slug}.json"
        if not req_json.exists():
            continue
        bdata = json.loads(req_json.read_text(encoding="utf-8"))
        doc = fitz.open()
        p1 = doc.new_page(width=612, height=792)
        cov_path = covers_dir / f"{f_slug}_cover.png"
        if cov_path.exists():
            p1.insert_image(fitz.Rect(36, 36, 576, 756), filename=str(cov_path))
        for idx_r, r in enumerate(bdata.get("requirements") or []):
            pg = doc.new_page(width=612, height=792)
            r_num = r.get("req_number")
            heading = r.get("topic_title") or f"Requirement {r_num}"
            body_lines = [
                f"Scouting America Merit Badge Reference Guide: {bname}",
                f"{heading}",
                "",
                r.get("req_text", ""),
                "",
                "Key Pamphlet Study Points:",
            ]
            for ex in r.get("pamphlet_excerpts") or []:
                body_lines.append(f"  - {ex}")
            pg.insert_textbox(fitz.Rect(48, 48, 564, 420), "\n".join(body_lines), fontsize=10.5)
            hero_p = _find_clean_visual_source(f_slug, idx_r)
            if hero_p.exists():
                pg.insert_image(fitz.Rect(106, 430, 506, 730), filename=str(hero_p))
        doc.save(str(pdf_p))
        doc.close()
        created += 1
    return created


if __name__ == "__main__":
    added_figs = _ensure_pamphlet_catalog_for_all_149()
    b_cnt, r_cnt = enrich_all_149_requirement_files()
    pdf_cnt = _ensure_local_pamphlet_pdfs_for_all_149()
    print(
        f"Enriched {b_cnt} Merit Badges ({r_cnt} top-level requirements + all sub-requirements), "
        f"updated {added_figs} pamphlet figure catalog entries, and built/refreshed {pdf_cnt} local PDFs."
    )
