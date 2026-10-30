"""ADK SlideContentPlannerAgent for creating 12-Archetype pedagogical slide storyboards.

This agent converts Merit Badge requirements and sub-requirements into an ordered,
multi-archetype slide storyboard with:
- Slide 1 (`REQUIREMENTS_TRIAGE_MATRIX`) classifying sub-requirements into In-Class Discussion,
  Hands-On Skill Station, and Prerequisite / Campout / Home.
- Rich archetype selection across all 12 `SlideArchetype` layouts.
- Zero truncation (`...`) and zero literal bullet characters (`•`).
- Keynote/Demo voice presenter notes (`[SAY]`, `[DEMONSTRATE]`, `[ASK SCOUTS]`, <=16 words/clause, zero em-dashes).
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from google import adk
from pydantic import BaseModel, Field

from src.config import (
    SCOUTS_BSA_CONSTITUTION,
    load_prompt,
    select_model_for_task,
)
from src.schemas import ExecutionMode, SlideArchetype, build_guided_tool_error
from src.tools.pptx_builder import SlideSpec
from src.agents.guardrails import (
    before_model_guardrail_callback,
    after_model_guardrail_callback,
)


class StoryboardPlan(BaseModel):
    """Schema representing the full ordered storyboard plan for a presentation."""
    badge_name: str = Field(..., description="Official badge name.")
    is_eagle_required: bool = Field(..., description="True if Eagle-required.")
    depth_mode: str = Field(..., description="Presentation depth mode selected.")
    slides: List[SlideSpec] = Field(..., description="Ordered list of slide specifications.")


def _sanitize_no_ellipsis_or_emdash(text: str) -> str:
    """Removes ellipses ('...'), em-dashes ('—', '--'), en-dashes ('–'), trailing dangling stopwords, and PDF kerning glitches."""
    if not text:
        return ""
    import re
    from src.tools.pamphlet_extractor import _repair_pdf_word_concatenations

    cleaned = _repair_pdf_word_concatenations(str(text))
    cleaned = cleaned.replace("...", ".").replace("…", ".")
    cleaned = cleaned.replace(" — ", ", ").replace(" – ", ", ").replace(" -- ", ", ")
    cleaned = cleaned.replace("—", ", ").replace("–", "-").replace("--", ", ")
    cleaned = cleaned.replace(" , ", ", ")
    while ".." in cleaned:
        cleaned = cleaned.replace("..", ".")
    cleaned = cleaned.strip()
    if cleaned.endswith("."):
        cleaned = re.sub(
            r"(?:\s+(?:and\s+identify\s+the|and\s+the|or\s+the|to\s+the|in\s+the|of\s+the|for\s+the|with\s+the|the|a|an|and|or|to|of|in|for|with|on|at|by|from))+\.$",
            ".",
            cleaned,
            flags=re.IGNORECASE,
        )
    return cleaned.strip()


def _infer_execution_mode(req: Dict[str, Any]) -> str:
    """Determines the pedagogical execution mode for a requirement dictionary."""
    import re

    explicit = req.get("execution_mode")
    if explicit:
        val = explicit.value if hasattr(explicit, "value") else str(explicit)
        if val in {
            ExecutionMode.IN_CLASS_DISCUSSION.value,
            ExecutionMode.HANDS_ON_SKILL_STATION.value,
            ExecutionMode.PREREQUISITE_CAMPOUT_HOME.value,
        }:
            return val

    sub_texts = " ".join(
        str(sr.get("text") or sr.get("sub_req_text") or "")
        for sr in (req.get("sub_requirements") or [])
        if isinstance(sr, dict)
    )
    text_lower = f"{req.get('req_text', '')} {sub_texts}".lower()
    if (
        any(
            kw in text_lower
            for kw in (
                "camp a total",
                "20 nights",
                "attend a",
                "visit a",
                "tour a",
                "interview a",
                "speak with a",
                "12-week",
                "13-week",
                "90-day",
                "30-day",
                "14-day",
                "7-day",
                "five consecutive days",
                "physical examination",
                "weekend campout",
                "overnight campout",
                "field trip",
                "keep a log",
                "keep a record",
                "keep a journal",
                "keep a chart",
                "keep a daily",
                "for at least",
                "over a period of",
            )
        )
        or re.search(
            r"\b(?:\d+|two|three|four|five|six|seven|eight|ten|twelve|fourteen|twenty|thirty|ninety)\s*[-\s]*(?:days?|weeks?|months?|nights?|hours?|miles?|books?|workouts?|meals?)\b",
            text_lower,
        )
    ):
        return ExecutionMode.PREREQUISITE_CAMPOUT_HOME.value
    if any(
        kw in text_lower
        for kw in (
            "demonstrate",
            "show",
            "prepare a",
            "build a",
            "design, build",
            "splinting",
            "cpr",
            "make a",
            "pitch",
            "construct",
            "perform",
            "practice",
            "swim",
            "shoot",
            "cook",
            "repair",
        )
    ):
        return ExecutionMode.HANDS_ON_SKILL_STATION.value
    return ExecutionMode.IN_CLASS_DISCUSSION.value


def _infer_archetype(req: Dict[str, Any], idx: int, exec_mode: str) -> str:
    """Determines the best-fit SlideArchetype for a requirement."""
    explicit = req.get("recommended_archetype")
    if explicit:
        val = explicit.value if hasattr(explicit, "value") else str(explicit)
        if val != SlideArchetype.SPLIT_VISUAL_EXPLAINER.value:
            return val

    if req.get("comparison_data"):
        return SlideArchetype.DIFFERENTIAL_COMPARISON_2COL.value
    if req.get("gear_checklist"):
        return SlideArchetype.GEAR_CHECKLIST_GRID.value
    if req.get("step_by_step_procedure"):
        return SlideArchetype.STEP_BY_STEP_PROCEDURE_4CARD.value
    if req.get("worked_example"):
        return SlideArchetype.WORKED_EXAMPLE_TEMPLATE.value
    if req.get("quiz_item") and idx == 0:
        return SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value

    text_lower = str(req.get("req_text", "")).lower()
    if any(kw in text_lower for kw in ("kit", "clothing", "layering", "equipment", "ppe", "gear")):
        return SlideArchetype.GEAR_CHECKLIST_GRID.value
    if any(kw in text_lower for kw in ("vs", "versus", "heat stroke", "fronts", "compare", "branches")):
        return SlideArchetype.DIFFERENTIAL_COMPARISON_2COL.value
    if any(kw in text_lower for kw in ("menu", "budget", "log", "program", "script", "speech", "record")):
        return SlideArchetype.WORKED_EXAMPLE_TEMPLATE.value
    if exec_mode == ExecutionMode.HANDS_ON_SKILL_STATION.value:
        return SlideArchetype.STEP_BY_STEP_PROCEDURE_4CARD.value

    rotation = [
        SlideArchetype.SPLIT_VISUAL_EXPLAINER.value,
        SlideArchetype.STEP_BY_STEP_PROCEDURE_4CARD.value,
        SlideArchetype.DIFFERENTIAL_COMPARISON_2COL.value,
        SlideArchetype.WORKED_EXAMPLE_TEMPLATE.value,
        SlideArchetype.GEAR_CHECKLIST_GRID.value,
        SlideArchetype.DECISION_TREE_FLOW.value,
    ]
    return rotation[idx % len(rotation)]


def _split_anchor_and_detail(raw_point: str, fallback_anchor: str = "Key Concept") -> tuple[str, str]:
    """Splits a 'Bold Anchor: Body text' string into (anchor, body) without splitting ratios like 30:2."""
    import re
    from src.tools.pamphlet_extractor import _derive_sentence_concept_anchor

    cleaned = _sanitize_no_ellipsis_or_emdash(str(raw_point or "").strip())
    if re.search(r":\s+", cleaned):
        anchor, body = re.split(r":\s+", cleaned, maxsplit=1)
        if 1 <= len(anchor.strip()) <= 60 and body.strip():
            return anchor.strip(), body.strip()
    if len(cleaned.split()) > 4:
        derived = _derive_sentence_concept_anchor(cleaned, 0, set())
        return derived or fallback_anchor, cleaned
    return fallback_anchor, cleaned


_WORKBOOK_ORGANIZER_DISPLAY_LABELS: Dict[str, str] = {
    "CAUSE_PREVENTION_MITIGATION_3COL": "3-Column Hazard & Response Matrix",
    "COMPARE_CONTRAST_2COL": "2-Column Comparison Table",
    "STEP_BY_STEP_CHECKLIST": "Step-by-Step Skill Checklist",
    "TIME_SERIES_LOG_TABLE": "Activity & Observation Log",
    "RULED_EXPLAIN_BOX": "Concept & Examples Notes",
    "CONCEPT_MATRIX": "Structured Concept Matrix",
    "ANATOMY_LABEL_DIAGRAM": "Labeled Diagram & Key",
    "DECISION_TREE_FLOW": "Decision Flowchart",
    "SAFETY_GEAR_SHAKEDOWN": "Gear & Safety Shakedown",
    "HAZARD_5COL": "5-Column Hazard Assessment Matrix",
    "SYMPTOMS_FIRST_AID_PREVENTION_3COL": "Symptoms, First Aid & Prevention Matrix",
    "CAMPING_LOG_20NIGHT": "20-Night Camping Experience Log",
    "FITNESS_ASSESSMENT_4STAGE": "4-Stage Fitness Assessment Log",
    "FITNESS_LOG_12WK": "12-Week Fitness & Activity Log",
    "MEAL_PLANNER_AND_COST_TABLE": "Camp Menu, Cost & Utensil Planner",
    "CITIZENSHIP_CIVIC_ORGANIZER": "Civic & Constitutional Study Organizer",
    "SCIENTIFIC_EXPERIMENT_SHEET": "Scientific Lab & Experiment Sheet",
    "SENSORY_OBSERVATION_LOG": "Field Sensory & Observation Log",
    "ENGINEERING_DESIGN_NOTEBOOK": "Engineering Design Notebook",
    "CAREER_EXPLORATION_CARD": "Career & Profession Exploration Card",
    "SKETCH_AND_OBSERVATION_CANVAS": "Field Sketch & Diagram Canvas",
    "PHYSICAL_SKILL_VERIFICATION_RUBRIC": "Hands-On Skill Verification Rubric",
    "ATOMIC_SOCRATIC_PROMPTS": "Guided Discussion & Study Prompts",
    "INTERVIEW_PREP_ORGANIZER": "Interview Preparation & Notes Organizer",
}

_EXECUTION_MODE_DISPLAY_LABELS: Dict[str, str] = {
    "IN_CLASS_DISCUSSION": "In-Class Discussion",
    "HANDS_ON_SKILL_STATION": "Hands-On Skill Station",
    "PREREQUISITE_CAMPOUT_HOME": "Prerequisite / Home & Troop Prep",
}

_STARTING_GATE_DISPLAY_LABELS: Dict[str, str] = {
    "COUNSELOR_PRE_APPROVAL": "Counselor Pre-Approval Required",
    "PARENT_CONSENT_GATE": "Parent / Guardian Permission Required",
    "HARD_PREREQ_BADGE": "Prerequisite Merit Badge / Certification",
    "EQUIPMENT_GATE": "Required Gear & Equipment Inspection",
    "GATE": "Starting Requirement Gate",
}

_SESSION_MODE_DISPLAY_LABELS: Dict[str, str] = {
    "4_session_mbc": "4-Session Merit Badge Clinic + Make-Up Day",
    "2_session_mbc": "2-Session Merit Badge Clinic",
    "1_day_mbu": "Single-Day Merit Badge University",
    "summer_camp_5day": "5-Day Summer Camp Schedule",
    "troop_meetings": "Troop Meeting Series",
}


def _format_execution_mode_label(mode: Any) -> str:
    """Maps raw execution_mode enum strings to human-friendly display labels."""
    raw = str(mode or "").strip().upper()
    if raw in _EXECUTION_MODE_DISPLAY_LABELS:
        return _EXECUTION_MODE_DISPLAY_LABELS[raw]
    return _sanitize_no_ellipsis_or_emdash(raw.replace("_", " ").title()) if raw else "In-Class Discussion"


def _format_starting_gate_label(gate_type: Any) -> str:
    """Maps raw starting_requirement_gate gate_type enum strings to human-friendly display labels."""
    raw = str(gate_type or "").strip().upper()
    if raw in _STARTING_GATE_DISPLAY_LABELS:
        return _STARTING_GATE_DISPLAY_LABELS[raw]
    return _sanitize_no_ellipsis_or_emdash(raw.replace("_", " ").title()) if raw else "Starting Requirement Gate"


def _format_session_mode_label(session_mode: Any) -> str:
    """Maps raw session_mode codes (e.g. '4_session_mbc') to human-friendly display labels."""
    raw = str(session_mode or "").strip()
    if raw in _SESSION_MODE_DISPLAY_LABELS:
        return _SESSION_MODE_DISPLAY_LABELS[raw]
    if raw.lower() in _SESSION_MODE_DISPLAY_LABELS:
        return _SESSION_MODE_DISPLAY_LABELS[raw.lower()]
    return _sanitize_no_ellipsis_or_emdash(raw.replace("_", " ").title()) if raw else "4-Session Merit Badge Clinic + Make-Up Day"


def _format_workbook_organizer_label(
    wb_org: Any = None,
    org_type_override: Optional[str] = None,
) -> str:
    """Maps raw organizer_type enum codes or dicts to human-friendly Scout Workbook section labels."""
    if org_type_override is not None:
        raw_type = str(org_type_override or "").strip().upper()
        friendly = _WORKBOOK_ORGANIZER_DISPLAY_LABELS.get(
            raw_type,
            _sanitize_no_ellipsis_or_emdash(raw_type.replace("_", " ").title()) if raw_type else "Concept & Examples Notes",
        )
        if str(wb_org or "").strip():
            return f"Workbook Requirement {wb_org} • {friendly}"
        return friendly
    if isinstance(wb_org, str):
        raw_type = wb_org.strip().upper()
        return _WORKBOOK_ORGANIZER_DISPLAY_LABELS.get(
            raw_type,
            _sanitize_no_ellipsis_or_emdash(raw_type.replace("_", " ").title()) if raw_type else "Concept & Examples Notes",
        )
    if not isinstance(wb_org, dict):
        return "Concept & Examples Notes"
    raw_type = str(wb_org.get("organizer_type") or "").strip().upper()
    if raw_type in _WORKBOOK_ORGANIZER_DISPLAY_LABELS:
        return _WORKBOOK_ORGANIZER_DISPLAY_LABELS[raw_type]
    raw_title = str(wb_org.get("table_title") or "").strip()
    if raw_title and "_" not in raw_title:
        return _sanitize_no_ellipsis_or_emdash(raw_title)
    if raw_type:
        return _sanitize_no_ellipsis_or_emdash(raw_type.replace("_", " ").title())
    return "Concept & Examples Notes"


def compile_conversational_speaker_notes(
    badge_name: str,
    req_number: str = "1a",
    slide_title: str = "",
    bullet_points: Optional[List[str]] = None,
    verbatim_text: str = "",
    verbatim_req_text: str = "",
    visual_caption: str = "",
    archetype: str = "CONCEPT_TEXT_SLIDE",
    execution_mode: str = "IN_CLASS_DISCUSSION",
    safety_callout: Optional[str] = None,
    safety_warning: Optional[str] = None,
    audience_level: str = "All Scouts (Ages 11-17)",
    slide_dict: Optional[Dict[str, Any]] = None,
    slide_idx_in_req: int = 0,
) -> str:
    """Public helper that compiles a conversational Counselor Teaching Script for a slide."""
    return _build_slide_teaching_notes(
        badge_name=badge_name,
        req_num=str(req_number or "1a"),
        execution_mode=execution_mode,
        slide_title=slide_title or f"{badge_name} Requirement {req_number}",
        archetype=archetype or "CONCEPT_TEXT_SLIDE",
        req_text=verbatim_req_text or verbatim_text,
        bullet_points=bullet_points or [],
        visual_caption=visual_caption,
        safety_callout=safety_warning or safety_callout,
        audience_level=audience_level,
        slide_dict=slide_dict,
        slide_idx_in_req=slide_idx_in_req,
    )


_GENERIC_META_ANCHORS = {
    "visual inventory",
    "core requirement focus",
    "concept 1",
    "concept 2",
    "concept 3",
    "concept 4",
    "concept 5",
    "concept 6",
    "key step 1",
    "key step 2",
    "key step 3",
    "key step 4",
    "step 1",
    "step 2",
    "step 3",
    "step 4",
    "core principle 1",
    "core principle 2",
    "core principle 3",
    "core principle 4",
    "primary standard",
    "core standard",
    "field evidence recorded",
    "safety & verification",
    "key concept",
    "option a",
    "option b",
    "option c",
    "option d",
    "preparation & study",
    "equipment & safety check",
    "hands-on demonstration",
    "counselor verification",
    "counselor verification tip",
    "workbook entry 1",
    "workbook entry 2",
    "workbook entry 3",
    "workbook entry 4",
    "pamphlet reference anchor",
    "core technical principle",
    "applied field mechanism",
    "preventive controls & ppe",
    "primary field hazard",
    "step-by-step execution",
    "field verification",
    "equipment & station setup",
    "practical verification & sign-off",
    "key standard",
    "field reference",
    "pamphlet verification",
    "buddy check",
    "practical execution",
    "counselor conference check",
}

_PRECOMPUTED_FACILITATOR_NOTES_CACHE: Optional[Dict[str, str]] = None
_PRECOMPUTED_FACILITATOR_NOTES_MTIME: float = 0.0


def _load_precomputed_facilitator_notes() -> Dict[str, str]:
    """Loads optional precomputed facilitator notes from data/precomputed_facilitator_notes_149.json with mtime cache invalidation."""
    import json
    from pathlib import Path

    global _PRECOMPUTED_FACILITATOR_NOTES_CACHE, _PRECOMPUTED_FACILITATOR_NOTES_MTIME
    notes_path = Path(__file__).resolve().parents[2] / "data" / "precomputed_facilitator_notes_149.json"
    if not notes_path.exists():
        return {}
    try:
        cur_mtime = notes_path.stat().st_mtime_ns
        if _PRECOMPUTED_FACILITATOR_NOTES_CACHE is not None and _PRECOMPUTED_FACILITATOR_NOTES_MTIME == cur_mtime:
            return _PRECOMPUTED_FACILITATOR_NOTES_CACHE
        loaded = json.loads(notes_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            flat_map: Dict[str, str] = {}
            if isinstance(loaded.get("badges"), dict):
                for b_key, b_val in loaded["badges"].items():
                    b_norm = str(b_key).replace("-", "_")
                    if isinstance(b_val, dict):
                        notes_obj = b_val.get("notes") or b_val.get("requirements") or b_val
                        if isinstance(notes_obj, dict):
                            for r_key, r_val in notes_obj.items():
                                if isinstance(r_val, str):
                                    flat_map[f"{b_norm}::{r_key}::0"] = r_val
                                elif isinstance(r_val, list):
                                    for idx_n, n_str in enumerate(r_val):
                                        flat_map[f"{b_norm}::{r_key}::{idx_n}"] = str(n_str)
                                elif isinstance(r_val, dict):
                                    for idx_k, n_str in r_val.items():
                                        flat_map[f"{b_norm}::{r_key}::{idx_k}"] = str(n_str)
            else:
                for k, v in loaded.items():
                    ks = str(k)
                    vs = str(v)
                    flat_map[ks] = vs
                    parts = ks.split("::")
                    if len(parts) >= 2:
                        u_s = parts[0].replace("_", "-")
                        f_s = parts[0].replace("-", "_")
                        rest = "::".join(parts[1:])
                        flat_map[f"{u_s}::{rest}"] = vs
                        flat_map[f"{f_s}::{rest}"] = vs
                        if parts[-1] == "0" and len(parts) == 3:
                            flat_map[f"{u_s}::{parts[1]}"] = vs
                            flat_map[f"{f_s}::{parts[1]}"] = vs
            _PRECOMPUTED_FACILITATOR_NOTES_CACHE = flat_map
            _PRECOMPUTED_FACILITATOR_NOTES_MTIME = cur_mtime
            return _PRECOMPUTED_FACILITATOR_NOTES_CACHE
    except Exception:
        pass
    return {}


def _extract_precomputed_note_parts(raw_note: str) -> Tuple[str, str, List[str]]:
    """Extracts sanitized (myth, fact, extra_insights) from a precomputed facilitator note entry."""
    import re

    if not raw_note or not str(raw_note).strip():
        return "", "", []
    text = _sanitize_no_ellipsis_or_emdash(str(raw_note))
    # Strip any truncated trailing '(p.' or '(pp.' fragments
    text = re.sub(r"\s*\(\s*pp?\.?\s*\d*[^)]*$", "", text, flags=re.IGNORECASE)

    myth_out = ""
    fact_out = ""
    m_misc = re.search(
        r"\[COMMON MISCONCEPTION TO CORRECT\]\s*Myth:\s*(.+?)\s*\|\s*BSA Pamphlet Fact:\s*(.+?)(?=\n\[|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m_misc:
        myth_cand = re.sub(r"\s*\(\s*pp?\.?\s*\d*[^)]*$", "", m_misc.group(1).strip()).strip()
        fact_cand = re.sub(r"\s*\(\s*pp?\.?\s*\d*[^)]*$", "", m_misc.group(2).strip()).strip()
        # Deduplicate repeated sentences inside fact_cand
        fact_sents = [s.strip() for s in re.split(r"(?<=[.?!])\s+", fact_cand) if s.strip()]
        dedup_f: List[str] = []
        for fs in fact_sents:
            if fs.lower() not in {x.lower() for x in dedup_f}:
                dedup_f.append(fs)
        fact_cand = " ".join(dedup_f).strip()
        if not _is_generic_meta_misconception(myth_cand, fact_cand):
            myth_out, fact_out = myth_cand, fact_cand

    insights: List[str] = []
    m_key = re.search(
        r"\[EXPECTED PAMPHLET ANSWER KEY\]\s*(.+?)(?=\[Expected Answer:|\n\[|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m_key:
        raw_k = m_key.group(1).strip()
        raw_k = re.sub(r"^Citation:\s*(?:[^(]+\([^)]+\)|[^.]+)\.\s*", "", raw_k, flags=re.IGNORECASE).strip()
        raw_k = re.sub(r"^\d+,\s*pp?\.?\s*\d+[^)]*\)\.\s*", "", raw_k, flags=re.IGNORECASE).strip()
        raw_k = re.sub(r"\s*\(\s*pp?\.?\s*\d*[^)]*$", "", raw_k, flags=re.IGNORECASE).strip()
        if len(raw_k) >= 25 and "(" not in raw_k[-6:]:
            insights.append(raw_k)

    return myth_out, fact_out, insights


def _conjugate_third_person_singular(verb_phrase: str) -> str:
    """Conjugates an action verb or compound verb phrase ('discuss', 'research and discuss') to 3rd-person singular."""
    import re

    def _conj_single(v: str) -> str:
        w = v.strip().lower()
        if not w:
            return "explains"
        irregular = {
            "be": "is",
            "have": "has",
            "do": "does",
            "go": "goes",
        }
        if w in irregular:
            return irregular[w]
        if w.endswith(("ss", "sh", "ch", "x", "z", "o")):
            return f"{w}es"
        if len(w) > 2 and w.endswith("y") and w[-2] not in "aeiou":
            return f"{w[:-1]}ies"
        if w.endswith("s"):
            return w
        return f"{w}s"

    vp = str(verb_phrase or "explain").strip().lower()
    if " and " in vp:
        parts = [p.strip() for p in vp.split(" and ", 1)]
        return f"{_conjugate_third_person_singular(parts[0])} and {_conjugate_third_person_singular(parts[1])}"
    tokens = [t for t in re.split(r"\s+", vp) if t]
    if not tokens:
        return "explains"
    if len(tokens) >= 2 and tokens[0].endswith("ly") and tokens[0] not in {"apply", "fly", "reply", "supply", "multiply"}:
        return f"{tokens[0]} {_conj_single(tokens[1])}"
    return _conj_single(tokens[0])


def _extract_meaningful_topic_phrase(anchor: str, body: str, fallback: str) -> str:
    """Extracts a concrete subject-matter topic phrase from a card's anchor and body.

    Avoids returning bare requirement labels ('Requirement 1a'), generic meta-headers
    ('Visual Inventory', 'Core Requirement Focus'), or leading verbs/interrogatives
    ('Why chess...', 'Connect the visual diagram...') so Socratic questions and rubrics read naturally.
    """
    import re

    clean_anc = _sanitize_no_ellipsis_or_emdash(str(anchor or "").strip())
    clean_bdy = _sanitize_no_ellipsis_or_emdash(str(body or "").strip())

    # Extract inner topic when anchor is 'Field Reference (Req 1: History of Chess)' or 'Pamphlet Verification (...)'
    m_ref_paren = re.match(
        r"^(?:Field\s+Reference|Pamphlet\s+Verification|Buddy\s+Check|Practical\s+Execution|Counselor\s+Conference\s+Check)\s*\(([^)]+)\)$",
        clean_anc,
        flags=re.IGNORECASE,
    )
    if m_ref_paren:
        inner_ref = re.sub(r"^(?:Req(?:uirement)?\s+[0-9a-zA-Z.()]+\s*[:\-]?\s*)", "", m_ref_paren.group(1).strip(), flags=re.IGNORECASE).strip()
        if len(inner_ref) >= 4:
            clean_anc = inner_ref

    # Strip structural headers like 'Core Standard 1 (Req 1):' or 'Primary Standard' or 'Option A:' or 'Workbook Entry 1'
    clean_anc = re.sub(
        r"^(?:Core\s+Standard\s+\d+\s*(?:\([^)]*\))?|Primary\s+Standard|Field\s+Evidence\s+Recorded|Safety\s*&\s*Verification|Option\s+[A-Z0-9]+|Pamphlet\s+Reference\s+Anchor|Core\s+Technical\s+Principle|Applied\s+Field\s+Mechanism|Preventive\s+Controls\s*&\s*PPE|Primary\s+Field\s+Hazard|Step-by-Step\s+Execution|Field\s+Verification|Equipment\s*&\s*Station\s+Setup|Practical\s+Verification\s*&\s*Sign-Off|Step\s+\d+\s*[-:]\s*|Field\s+Reference|Pamphlet\s+Verification|Buddy\s+Check|Practical\s+Execution|Counselor\s+Conference\s+Check|Preparation\s*&\s*Study|Equipment\s*&\s*Safety\s+Check|Hands-On\s+Demonstration|Counselor\s+Verification|Workbook\s+Entry\s+\d+|Key\s+Point\s+\d+)\s*[:\-]?\s*",
        "",
        clean_anc,
        flags=re.IGNORECASE,
    ).strip()
    clean_anc = re.sub(r"\s+(?:Principle|Standard)\s+\d+$", "", clean_anc, flags=re.IGNORECASE).strip()

    _leading_verb_or_wh_re = (
        r"^(?:Explain(?!\s+Phase)|Discuss|Describe|Demonstrate(?!\s+Phase)|Show|Identify|Tell|Find|List|Name|Review|Obtain|Do|"
        r"Prevent|Avoid|Always|Never|Every|Ever|Connect|Trace|Apply|Practice|Present|Record|Check|Verify|Complete|Study|Research|"
        r"Compare|Contrast|Make|Build|Create|Select|Choose|Use|Keep|Write|Draw|Sketch|Visit|Attend|Interview|Share|Read|Watch|"
        r"Play|Set|Teach|Learn|Understand|Know|Why|How|What|When|Where|Which|Who|Whether)\b"
    )

    # Case 1: 'Requirement 1a (Scene Safety & 3 Cs)' -> 'Scene Safety & 3 Cs'
    m_paren = re.match(
        r"^(?:Req(?:uirement)?\s+[0-9a-zA-Z.()]+\s*)\(([^)]+)\)$",
        clean_anc,
        flags=re.IGNORECASE,
    )
    if m_paren and len(m_paren.group(1).strip()) >= 3:
        paren_topic = m_paren.group(1).strip()
        if not re.match(_leading_verb_or_wh_re, paren_topic, flags=re.IGNORECASE):
            return paren_topic

    # Strip leading 'Requirement 1a:' or 'Req 1a -' or '(1)' from anchor
    stripped_anc = re.sub(
        r"^(?:Req(?:uirement)?\s+[0-9a-zA-Z.()]+\s*[:\-]?\s*|\([0-9a-zA-Z]+\)\s*)",
        "",
        clean_anc,
        flags=re.IGNORECASE,
    ).strip()

    is_bare_req = bool(
        re.match(r"^(?:Req(?:uirement)?\s*|Option\s*)?[()0-9a-zA-Z.]+$", stripped_anc or clean_anc, flags=re.IGNORECASE)
    )
    is_verb_clause = bool(
        re.match(_leading_verb_or_wh_re, stripped_anc, flags=re.IGNORECASE)
    )
    if (
        stripped_anc
        and not is_bare_req
        and not is_verb_clause
        and stripped_anc.lower() not in _GENERIC_META_ANCHORS
        and clean_anc.lower() not in _GENERIC_META_ANCHORS
    ):
        return stripped_anc

    # Derive a concrete topic phrase from the card body via _derive_topic_title when available
    candidate = re.sub(
        r"^(?:Req(?:uirement)?\s+[0-9a-zA-Z.()]+\s*(?:\([^)]+\))?\s*[:\-]?\s*|\([a-z0-9]+\)\s*|Option\s+[A-Z0-9]+\s*[:\-]?\s*)",
        "",
        clean_bdy,
        flags=re.IGNORECASE,
    ).strip()
    try:
        from src.tools.pamphlet_extractor import _derive_topic_title
        derived = _derive_topic_title("X", candidate).replace("Req X:", "").strip()
        if (
            derived
            and len(derived) >= 4
            and derived.lower() not in {"requirement overview", "core standard", "field execution"}
            and not re.match(_leading_verb_or_wh_re, derived, flags=re.IGNORECASE)
        ):
            return derived
    except Exception:
        pass
    if " - " in candidate:
        left_seg = candidate.split(" - ", 1)[0].strip()
        if 2 <= len(left_seg.split()) <= 8 and not re.match(
            _leading_verb_or_wh_re,
            left_seg,
            flags=re.IGNORECASE,
        ):
            return left_seg.rstrip(".,;:")

    candidate = re.sub(
        r"^(?:Explain|Discuss|Describe|Demonstrate|Show|Identify|Tell|List|Name|Review|Obtain|Master|Inspect|Define|Perform|"
        r"Connect|Trace|Apply|Practice|Present|Record|Check|Verify|Complete|Study|Research|Compare|Contrast|Make|Build|Use|Keep)\s+"
        r"(?:the\s+(?:steps\s+necessary\s+to|precautions\s+you\s+must\s+take\s+to|importance\s+of|meaning\s+of|difference\s+between|core\s+principles\s+of|key\s+components\s+of|term)\s+|"
        r"evaluation\s+of\s+and\s+|all\s+sub-parts\s+of\s+|how\s+you\s+would\s+|how\s+to\s+|how\s+|why\s+|what\s+|when\s+|where\s+|a\s+)?",
        "",
        candidate,
        flags=re.IGNORECASE,
    ).strip()
    candidate = re.sub(r"^(?:why|how|what|when|where|whether)\s+", "", candidate, flags=re.IGNORECASE).strip()

    clause = re.split(r"[.;,]|(?:\s+-\s+)", candidate)[0].strip()
    words = clause.split()
    if len(words) > 7:
        words = words[:7]
    while words and (
        words[-1].lower()
        in {
            "and",
            "or",
            "to",
            "of",
            "in",
            "for",
            "with",
            "on",
            "at",
            "by",
            "from",
            "the",
            "a",
            "an",
            "such",
            "as",
            "including",
            "checking",
            "reduce",
            "describe",
            "that",
            "you",
            "may",
            "is",
            "are",
            "was",
            "were",
            "applies",
            "apply",
        }
        or words[-1].lower().endswith("'s")
    ):
        words.pop()
    phrase = " ".join(words).strip(" .,:;-")
    phrase = re.sub(r"^(?:why|how|what|when|where|connect|trace|review|apply)\s+", "", phrase, flags=re.IGNORECASE).strip()
    if len(phrase) >= 4:
        return phrase
    fb_clean = re.sub(r"^(?:Req(?:uirement)?\s+[0-9a-zA-Z.()]+\s*[:\-]?\s*)", "", _sanitize_no_ellipsis_or_emdash(fallback), flags=re.IGNORECASE).strip()
    return fb_clean or _sanitize_no_ellipsis_or_emdash(fallback)


def _is_generic_meta_misconception(myth_str: str, fact_str: str = "") -> bool:
    """Returns True when a misconception pair is empty or matches generic meta-boilerplate."""
    m_low = str(myth_str or "").strip().lower()
    f_low = str(fact_str or "").strip().lower()
    if not m_low or not f_low:
        return True
    generic_markers = (
        "many scouts assume",
        "only requires a general overview",
        "according to the official merit badge pamphlet, scouts must demonstrate",
        "assuming a quick verbal summary",
        "reading a short definition",
        "reading a brief summary of",
        "without checking each sub-requirement",
        "completing a quick checklist",
        "skimming the requirement title",
        "relying on unverified assumptions",
        "skipping field preparation is acceptable",
        "improvising primary standard",
        "field evidence recorded",
        "core requirement mastery",
        "safety & verification",
        "step-by-step execution",
        "individually option mastery",
        "applied field standard",
        "estimating define",
        "estimating explain",
        "estimating identify",
        "estimating discuss",
        "estimating tell",
        "estimating do the following",
        "general familiarity with ",
        "students often overlook the real-world impact of ",
        "skipping the preliminary setup for ",
        "emerged all at once rather than evolving through the historical milestones",
        "works the same way under all conditions regardless of how",
        "operate identically and can be used interchangeably",
        "adjust automatically without manual verification",
        "standard household habits can replace",
        "focusing only on ",
        "while bypassing ",
        "only affects appearance and does not alter",
        "only need to review safety rules and emergency procedures after an incident occurs",
        "relies only on hobby experience rather than formal training",
        "from memory at the end of the project satisfies",
        "are interchangeable regardless of operating conditions",
        "verbally can substitute for a physical hands-on demonstration",
        "watching a generic video without preparing questions",
    )
    if any(marker in m_low for marker in generic_markers) or any(marker in f_low for marker in generic_markers):
        return True
    if ("memorizing " in m_low or "rushing past " in m_low) and "is enough" in m_low:
        return True
    if "is enough for " in m_low and "sign-off" in m_low:
        return True
    if "actively explain the specific principles and real-world steps of req" in f_low:
        return True
    return False


def _scope_req_dict_for_slide(
    req_data: Dict[str, Any],
    clean_req: str,
    clean_title: str,
    pts: List[str],
    slide_dict: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], List[str], str]:
    """Builds a slide-scoped requirement dictionary and extracts covered sub-requirement IDs.

    Falls back to `slide_dict` fields when `req_data` is missing or partial, and scopes
    `sub_requirements`, `pamphlet_excerpts`, `common_misconception_pair`, `workbook_organizer`,
    and `pamphlet_page_citation` to the specific sub-requirement chunk shown on this slide.
    """
    import re

    scoped: Dict[str, Any] = dict(req_data or {})
    s_dict: Dict[str, Any] = dict(slide_dict or {})

    # Fall back to slide_dict metadata when req_data is empty or missing fields
    if not scoped.get("common_misconception_pair") and isinstance(s_dict.get("misconception_pair"), dict):
        scoped["common_misconception_pair"] = s_dict["misconception_pair"]
    if not scoped.get("pamphlet_page_citation") and s_dict.get("pamphlet_reference"):
        scoped["pamphlet_page_citation"] = str(s_dict["pamphlet_reference"])
    if not scoped.get("workbook_organizer") and s_dict.get("workbook_table_ref"):
        scoped["workbook_organizer"] = str(s_dict["workbook_table_ref"])
    if not scoped.get("syllabus_bucket") and (s_dict.get("syllabus_tier") or s_dict.get("syllabus_bucket")):
        scoped["syllabus_bucket"] = str(s_dict.get("syllabus_tier") or s_dict.get("syllabus_bucket"))

    # Determine if this slide covers a specific chunk of sub-requirements
    all_subs: List[Dict[str, Any]] = [
        sr for sr in (scoped.get("sub_requirements") or []) if isinstance(sr, dict)
    ]
    explicit_chunk: List[Dict[str, Any]] = [
        sr for sr in (s_dict.get("sub_requirements_chunk") or []) if isinstance(sr, dict)
    ]

    def _sr_norm_id(sr_obj: Dict[str, Any], idx_fallback: int = 0) -> str:
        raw_lbl = str(
            sr_obj.get("req_id")
            or sr_obj.get("sub_id")
            or sr_obj.get("id")
            or sr_obj.get("sub_req_label")
            or ""
        ).strip()
        if not raw_lbl:
            return f"{clean_req}{chr(97 + idx_fallback)}"
        if len(raw_lbl) == 1 and raw_lbl.isalpha() and not str(clean_req).lower().endswith(raw_lbl.lower()):
            return f"{clean_req}{raw_lbl}"
        return raw_lbl

    matched_subs: List[Dict[str, Any]] = []
    if explicit_chunk:
        matched_subs = explicit_chunk
    elif all_subs:
        bullets_blob = " \n ".join(pts)
        # Check for explicit bullet references like 'Requirement 1a' or 'Req 1a'
        for idx_s, sr in enumerate(all_subs):
            sid = _sr_norm_id(sr, idx_s)
            if re.search(rf"\b(?:Req(?:uirement)?\s*)?{re.escape(sid)}\b", bullets_blob, flags=re.IGNORECASE):
                matched_subs.append(sr)
        # Or check for range in slide title like '(Reqs 1a-1d)' or 'Part 1 of 2: 1a-1d'
        if not matched_subs:
            m_range = re.search(
                r"\b([0-9]+[a-z])\s*[-–—]\s*([0-9]+[a-z])\b",
                clean_title,
                flags=re.IGNORECASE,
            )
            if m_range:
                start_id = m_range.group(1).lower()
                end_id = m_range.group(2).lower()
                in_span = False
                for idx_s, sr in enumerate(all_subs):
                    sid = _sr_norm_id(sr, idx_s).lower()
                    if sid == start_id:
                        in_span = True
                    if in_span:
                        matched_subs.append(sr)
                    if sid == end_id:
                        break

    matched_ids = [_sr_norm_id(sr, i) for i, sr in enumerate(matched_subs)]
    range_label = ""
    if matched_ids:
        range_label = (
            f"{matched_ids[0]}-{matched_ids[-1]}"
            if len(matched_ids) > 1
            else matched_ids[0]
        )

    is_subreq_slide = bool(
        matched_subs
        and (
            s_dict.get("is_subreq_slide")
            or "sub-requirement" in clean_title.lower()
            or re.search(r"\bReqs?\s+[0-9]+[a-z]", clean_title, flags=re.IGNORECASE)
            or len(matched_subs) < len(all_subs)
        )
    )

    if is_subreq_slide and matched_subs:
        scoped["sub_requirements"] = matched_subs
        # Scope pamphlet_page_citation to the sub-requirements in this chunk
        sub_cites: List[str] = []
        for sr in matched_subs:
            c_txt = _sanitize_no_ellipsis_or_emdash(str(sr.get("pamphlet_page_citation") or "").strip())
            if c_txt and c_txt not in sub_cites:
                sub_cites.append(c_txt)
        if sub_cites:
            base_cite = sub_cites[0]
            if range_label and range_label.lower() not in base_cite.lower():
                scoped["pamphlet_page_citation"] = f"{base_cite} (Reqs {range_label})"
            else:
                scoped["pamphlet_page_citation"] = base_cite
        elif scoped.get("pamphlet_page_citation") and range_label:
            base_c = _sanitize_no_ellipsis_or_emdash(str(scoped["pamphlet_page_citation"]))
            if range_label.lower() not in base_c.lower():
                scoped["pamphlet_page_citation"] = f"{base_c} (Reqs {range_label})"

        # Scope workbook_organizer from the chunk's sub-requirements
        for sr in matched_subs:
            if isinstance(sr.get("workbook_organizer"), dict) and sr["workbook_organizer"]:
                scoped["workbook_organizer"] = sr["workbook_organizer"]
                break

        # Scope pamphlet_excerpts to the chunk's sub-requirement summaries/texts
        sub_excerpts: List[str] = []
        sub_socratic: List[str] = []
        for idx_s, sr in enumerate(matched_subs):
            sid = _sr_norm_id(sr, idx_s)
            sr_sum = _sanitize_no_ellipsis_or_emdash(
                str(sr.get("pamphlet_summary") or sr.get("sub_req_text") or sr.get("text") or "").strip()
            )
            if sr_sum:
                sub_excerpts.append(f"Req {sid}: {sr_sum}")
            for sq in (sr.get("socratic_questions") or []):
                sq_clean = _sanitize_no_ellipsis_or_emdash(str(sq).strip())
                if sq_clean and sq_clean not in sub_socratic:
                    sub_socratic.append(sq_clean)
        if sub_excerpts:
            scoped["pamphlet_excerpts"] = sub_excerpts + list(scoped.get("pamphlet_excerpts") or [])
        for sq in (scoped.get("socratic_questions") or []):
            sq_clean = _sanitize_no_ellipsis_or_emdash(str(sq).strip())
            if sq_clean and sq_clean not in sub_socratic:
                sub_socratic.append(sq_clean)
        if sub_socratic:
            scoped["socratic_questions"] = sub_socratic

        sub_misc_pool: List[Dict[str, str]] = []
        for sr in matched_subs:
            if isinstance(sr.get("common_misconception_pair"), dict):
                sub_misc_pool.append(sr["common_misconception_pair"])
            for mp_item in (sr.get("misconception_pool") or []):
                if isinstance(mp_item, dict):
                    sub_misc_pool.append(mp_item)
        for mp_item in (scoped.get("misconception_pool") or []):
            if isinstance(mp_item, dict):
                sub_misc_pool.append(mp_item)
        if sub_misc_pool:
            scoped["misconception_pool"] = sub_misc_pool

        # Scope common_misconception_pair: pick non-generic sub-req misconception distinct from parent if present, else clear for synthesis
        parent_mp_raw = (req_data or {}).get("common_misconception_pair")
        parent_myth_norm = (
            str(parent_mp_raw.get("misconception") or parent_mp_raw.get("myth") or "").strip().lower()
            if isinstance(parent_mp_raw, dict)
            else ""
        )
        chosen_sub_misc: Optional[Dict[str, Any]] = None
        for sr in matched_subs:
            mp = sr.get("common_misconception_pair")
            if isinstance(mp, dict):
                m_val = str(mp.get("misconception") or mp.get("myth") or "")
                f_val = str(mp.get("fact") or mp.get("fact_correction") or "")
                if not _is_generic_meta_misconception(m_val, f_val) and m_val.strip().lower() != parent_myth_norm:
                    chosen_sub_misc = mp
                    break
        scoped["common_misconception_pair"] = chosen_sub_misc

    return scoped, matched_ids, range_label


def _synthesize_subject_matter_misconception(
    clean_badge: str,
    clean_req: str,
    clean_title: str,
    arch: str,
    meaningful_topics: List[str],
    parsed_points: List[Tuple[str, str]],
    page_cite: str,
    slide_idx_in_req: int = 0,
    slide_seed: int = 0,
    comparison_data: Optional[Dict[str, Any]] = None,
    worked_example: Optional[Dict[str, Any]] = None,
    quiz_item: Optional[Dict[str, Any]] = None,
    gear_checklist: Optional[List[str]] = None,
    range_label: str = "",
) -> Tuple[str, str]:
    """Synthesizes a concrete subject-matter (Myth, BSA Pamphlet Fact) pair grounded in the slide's cards."""
    req_scope_str = f"Reqs {range_label}" if range_label and "-" in range_label else f"Requirement {range_label or clean_req}"
    n_pts = max(1, len(parsed_points))
    idx_1 = slide_idx_in_req % n_pts
    idx_2 = (slide_idx_in_req + 1) % n_pts if n_pts > 1 else 0

    topic_1 = meaningful_topics[idx_1] if idx_1 < len(meaningful_topics) else (meaningful_topics[0] if meaningful_topics else clean_title)
    topic_2 = meaningful_topics[idx_2] if idx_2 < len(meaningful_topics) else topic_1
    body_1 = parsed_points[idx_1][1].rstrip(".") if idx_1 < len(parsed_points) else f"the technical standard for {topic_1}"
    body_2 = parsed_points[idx_2][1].rstrip(".") if idx_2 < len(parsed_points) else body_1

    # 1. Socratic Quiz slide: use the distractor option vs. verified answer explanation
    if arch == SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value or quiz_item:
        qi = quiz_item or {}
        opts = [str(o).strip() for o in (qi.get("options") or []) if str(o).strip()]
        ans = _sanitize_no_ellipsis_or_emdash(str(qi.get("correct_answer") or topic_1).rstrip("."))
        expl = _sanitize_no_ellipsis_or_emdash(str(qi.get("explanation") or body_1).rstrip("."))
        distractor = ""
        for opt in opts:
            opt_clean = _sanitize_no_ellipsis_or_emdash(opt.rstrip("."))
            if opt_clean and opt_clean[:25].lower() not in ans.lower() and ans[-25:].lower() not in opt_clean.lower():
                distractor = opt_clean
                break
        is_actual_emergency_badge = clean_badge.strip().lower() in {
            "first aid", "emergency preparedness", "lifesaving",
            "wilderness survival", "search and rescue", "fire safety",
        }
        if distractor:
            if is_actual_emergency_badge:
                myth = f"In a real-world {clean_badge} emergency, taking the shortcut of \"{distractor}\"."
            else:
                myth = f"When completing {clean_badge} {req_scope_str}, taking the shortcut of \"{distractor}\"."
        else:
            if is_actual_emergency_badge:
                myth = f"Reacting impulsively during a {clean_title} scenario before sizing up scene hazards and buddy safety."
            else:
                myth = f"Rushing through {clean_title} without verifying the official {clean_badge} Merit Badge Pamphlet standard first."
        fact = f"{ans}. {expl}."
        return myth, fact

    # 2. Differential Comparison 2-Column slide
    if arch == SlideArchetype.DIFFERENTIAL_COMPARISON_2COL.value or comparison_data:
        cd = comparison_data or {}
        left_h = _sanitize_no_ellipsis_or_emdash(str(cd.get("left_header") or topic_1))
        right_h = _sanitize_no_ellipsis_or_emdash(str(cd.get("right_header") or topic_2))
        left_pts = [str(x) for x in (cd.get("left_points") or []) if str(x).strip()]
        right_pts = [str(x) for x in (cd.get("right_points") or []) if str(x).strip()]
        l_detail = _sanitize_no_ellipsis_or_emdash(left_pts[0].rstrip(".")) if left_pts else body_1
        r_detail = _sanitize_no_ellipsis_or_emdash(right_pts[0].rstrip(".")) if right_pts else body_2
        myth = f"Treating {left_h} and {right_h} as interchangeable in the field and applying the exact same response to both."
        fact = f"Scouts must distinguish the two immediately: {left_h} involves {l_detail}, whereas {right_h} requires {r_detail} ({page_cite})."
        return myth, fact

    # 3. Gear Checklist Grid slide
    if arch == SlideArchetype.GEAR_CHECKLIST_GRID.value or gear_checklist:
        myth = f"Packing {topic_1} into a patrol kit without inspecting condition, fit, or expiration before leaving the trailhead."
        fact = f"Every Scout must physically lay out and verify {topic_1} ({body_1}) and {topic_2} ({body_2}) during pre-trip shakedown per {page_cite}."
        return myth, fact

    # 4. Step-by-Step Procedure 4-Card slide
    if arch == SlideArchetype.STEP_BY_STEP_PROCEDURE_4CARD.value:
        myth = f"Skipping past {topic_1} to rush straight into {topic_2} when performing {clean_title} under field pressure."
        fact = f"Sequence integrity is mandatory in {clean_badge}: establish {topic_1} first ({body_1}), then execute {topic_2} ({body_2}) per {page_cite}."
        return myth, fact

    # 5. Worked Example / Scout Log slide
    if arch == SlideArchetype.WORKED_EXAMPLE_TEMPLATE.value or worked_example:
        myth = f"Writing vague one-word notes for {clean_badge} {req_scope_str} without recording field measurements or concrete observations."
        fact = f"A sign-off-ready {clean_badge} log must document specific details for {topic_1} ({body_1}) and {topic_2} ({body_2}) as modeled in {page_cite}."
        return myth, fact

    # 6. Six varied subject-matter templates for Concept, Sub-Requirement Deep Dive, Visual Explainer, and Intro slides
    templates: List[Tuple[str, str]] = [
        (
            f"Separating {topic_1} from {topic_2} instead of checking both together during {clean_badge} {req_scope_str} field practice.",
            f"Under {page_cite if req_scope_str.lower() in page_cite.lower() else f'{page_cite} ({req_scope_str})'}, Scouts must apply {topic_1} ({body_1}) alongside {topic_2} ({body_2}).",
        ),
        (
            f"Overlooking how {topic_2} directly shapes safe decision-making when applying {topic_1} in {clean_badge}.",
            f"The {clean_badge} pamphlet standard integrates {topic_1} ({body_1}) with {topic_2} ({body_2}).",
        ),
        (
            f"Treating {topic_1} as a passive classroom definition rather than an active field check during {clean_badge} outings.",
            f"In practice, Scouts verify {topic_1} by applying {body_1} and cross-checking {topic_2} ({body_2}).",
        ),
        (
            f"Waiting until a field problem escalates before applying {topic_1} and {topic_2} on {req_scope_str}.",
            f"Proactive {clean_badge} practice means executing {topic_1} ({body_1}) early and confirming {topic_2} ({body_2}) per {page_cite}.",
        ),
        (
            f"Relying on guesswork for {topic_1} instead of following the verified {clean_badge} standard for {req_scope_str}.",
            f"Per {page_cite}, accurate execution of {topic_1} requires {body_1}, paired with {topic_2} ({body_2}).",
        ),
        (
            f"Assuming {topic_1} and {topic_2} only apply in extreme emergencies rather than routine troop and patrol operations.",
            f"Every patrol member must consistently practice {topic_1} ({body_1}) and {topic_2} ({body_2}) for {req_scope_str} mastery.",
        ),
    ]
    pick_idx = (slide_seed + slide_idx_in_req * 3) % len(templates)
    return templates[pick_idx]


def _build_slide_teaching_notes(
    badge_name: str,
    req_num: str,
    execution_mode: str,
    slide_title: str = "",
    archetype: str = "CONCEPT_TEXT_SLIDE",
    req_text: str = "",
    bullet_points: Optional[List[str]] = None,
    req_dict: Optional[Dict[str, Any]] = None,
    comparison_data: Optional[Dict[str, Any]] = None,
    worked_example: Optional[Dict[str, Any]] = None,
    quiz_item: Optional[Dict[str, Any]] = None,
    gear_checklist: Optional[List[str]] = None,
    visual_caption: str = "",
    has_visual: bool = False,
    safety_callout: Optional[str] = None,
    overview_summary: Optional[Dict[str, List[str]]] = None,
    audience_level: str = "All Scouts (Ages 11-17)",
    local_grounding_callout: str = "",
    slide_dict: Optional[Dict[str, Any]] = None,
    slide_idx_in_req: int = 0,
) -> str:
    """Compiles the native 5-Part Non-Redundant Facilitator Guide (<5ms per deck).

    Emits the 5 first-class facilitator sections:
    1. `[PACING & MODALITY]`: Estimated slide time (`2-4 min`), syllabus delivery bucket,
       active BSA EDGE stage, and conversational first-person counselor walkthrough with
       inline `[Point to Card N: ...]` stage cues.
    2. `[ASK SCOUTS FIRST]`: Socratic diagnostic opener to ask Patrols before revealing the answer.
    3. `[EXPECTED PAMPHLET ANSWER KEY]`: Concrete facts, measurements, and page citations from the
       official BSA Merit Badge Pamphlet that are not already written verbatim on the slide cards,
       concluding with `[Expected Answer: ...]`.
    4. `[COMMON MISCONCEPTION TO CORRECT]`: The #1 misconception Scouts hold on this slide/sub-requirement
       paired with the official BSA Pamphlet correction (`Myth vs. BSA Pamphlet Fact`).
    5. `[DEMONSTRATION & SIGN-OFF RUBRIC]`: Hands-on EDGE demonstration coaching and the concrete
       verification standard for Blue Card (#34124) and Fillable Workbook sign-off.
    """
    import re

    s_dict = dict(slide_dict or {})
    clean_badge = _sanitize_no_ellipsis_or_emdash(badge_name)
    clean_req = _sanitize_no_ellipsis_or_emdash(req_num)
    clean_title = _sanitize_no_ellipsis_or_emdash(slide_title or str(s_dict.get("title") or f"{clean_badge} Requirement {clean_req}"))
    clean_req_text = _sanitize_no_ellipsis_or_emdash(req_text or str(s_dict.get("verbatim_requirement_text") or ""))
    clean_caption = _sanitize_no_ellipsis_or_emdash(visual_caption or str(s_dict.get("visual_caption") or ""))
    arch = (archetype or str(s_dict.get("archetype") or "CONCEPT_TEXT_SLIDE")).upper()

    raw_bullets = list(bullet_points or s_dict.get("bullet_points") or [])
    if not raw_bullets:
        for vc in (s_dict.get("visual_cards") or s_dict.get("cards") or []):
            if isinstance(vc, dict):
                a_t = str(vc.get("anchor_title") or vc.get("title") or "").strip()
                b_t = str(vc.get("body_text") or vc.get("body") or "").strip()
                if a_t and b_t:
                    raw_bullets.append(f"{a_t}: {b_t}")
                elif b_t or a_t:
                    raw_bullets.append(b_t or a_t)
    pts = [_sanitize_no_ellipsis_or_emdash(str(p)) for p in raw_bullets if str(p).strip()]

    eff_local_callout = local_grounding_callout or str(s_dict.get("local_grounding_callout") or "")
    req_data, matched_sub_ids, sub_range_label = _scope_req_dict_for_slide(
        req_data=req_dict or {},
        clean_req=clean_req,
        clean_title=clean_title,
        pts=pts,
        slide_dict=s_dict,
    )

    parsed_points = [
        _split_anchor_and_detail(p, f"Concept {idx + 1}")
        for idx, p in enumerate(pts)
    ]
    meaningful_topics = [
        _extract_meaningful_topic_phrase(a, b, clean_title)
        for a, b in parsed_points
    ]
    from src.tools.pamphlet_extractor import _is_emergency_or_hazard_context
    is_hazard_ctx = _is_emergency_or_hazard_context(clean_badge, clean_req_text, clean_title)

    # Deduplicate meaningful_topics while preserving order
    dedup_topics: List[str] = []
    if arch == SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value or quiz_item:
        if is_hazard_ctx:
            dedup_topics = ["scene safety assessment", "emergency action sequence", "BSA Pamphlet safety rationale"]
        else:
            dedup_topics = ["requirement scenario analysis", "verified BSA Pamphlet procedure", "practical decision rationale"]
    else:
        for mt in meaningful_topics:
            if mt and mt.lower() not in {x.lower() for x in dedup_topics}:
                dedup_topics.append(mt)
        if not dedup_topics:
            dedup_topics = [clean_title]

    # Deterministic per-slide selector across the 6 phrasing templates
    title_seed = sum((i + 1) * ord(ch) for i, ch in enumerate(clean_title))
    req_seed = sum(ord(ch) for ch in clean_req)
    slide_seed = title_seed + req_seed * 7 + max(0, int(slide_idx_in_req)) * 13
    tpl_idx = slide_seed % 6

    # Consult precomputed facilitator notes (data/precomputed_facilitator_notes_149.json)
    b_slug_hyphen = re.sub(r"[^a-z0-9]+", "-", clean_badge.lower()).strip("-")
    b_slug = re.sub(r"[^a-z0-9]+", "_", clean_badge.lower()).strip("_")
    _role_map = {
        "REQUIREMENT_INTRO": 0,
        "CONCEPT_OVERVIEW": 0,
        "CONCEPT_TEXT_SLIDE": 0,
        "STEP_BY_STEP_PROCEDURE_4CARD": 1,
        "HANDS_ON_STATION": 1,
        "WORKED_EXAMPLE_TEMPLATE": 2,
        "PREREQUISITE_LOG_TRACKER": 2,
        "DIFFERENTIAL_COMPARISON_2COL": 3,
        "GEAR_CHECKLIST_GRID": 4,
        "SPLIT_VISUAL_EXPLAINER": 5,
        "FULL_BLEED_IMAGE_EXPLAINER": 5,
        "SOCRATIC_CHECKPOINT_QUIZ": 6,
    }
    role_idx = _role_map.get(arch, min(6, max(0, int(slide_idx_in_req))))
    precomp_map = _load_precomputed_facilitator_notes()
    lookup_req_id = sub_range_label.split("-")[0] if sub_range_label else clean_req
    raw_precomp_note = (
        precomp_map.get(f"{b_slug_hyphen}::{lookup_req_id}::{role_idx}")
        or precomp_map.get(f"{b_slug_hyphen}::{clean_req}::{role_idx}")
        or precomp_map.get(f"{b_slug}::{lookup_req_id}::{role_idx}")
        or precomp_map.get(f"{b_slug}::{clean_req}::{role_idx}")
        or ""
    )
    precomp_myth, precomp_fact, precomp_insights = _extract_precomputed_note_parts(raw_precomp_note)

    # Build & rotate extra_insights (pamphlet_excerpts) by slide_idx_in_req so consecutive slides
    # for the same requirement never quote the exact same two pamphlet sentences.
    raw_excerpts_pool: List[str] = []
    for raw_ex in list(req_data.get("pamphlet_excerpts") or []) + list(req_data.get("step_by_step_procedure") or []) + precomp_insights:
        clean_ex = _sanitize_no_ellipsis_or_emdash(str(raw_ex))
        if clean_ex and clean_ex not in pts and clean_ex not in raw_excerpts_pool:
            raw_excerpts_pool.append(clean_ex)

    if raw_excerpts_pool:
        offset = (max(0, int(slide_idx_in_req)) * 2) % max(1, len(raw_excerpts_pool))
        rotated_excerpts = raw_excerpts_pool[offset:] + raw_excerpts_pool[:offset]
        # If pool has >2 items, take 2 starting at offset; if <=2 items and slide_idx_in_req > 0, reverse or pick distinct slice
        if len(raw_excerpts_pool) == 2 and slide_idx_in_req % 2 == 1:
            extra_insights = [raw_excerpts_pool[1]]
        else:
            extra_insights = rotated_excerpts[:2]
    else:
        extra_insights = []

    aud_lower = (audience_level or "").lower()
    audience_cue = ""
    if "first-year" in aud_lower or "tenderfoot" in aud_lower or ("11" in aud_lower and "13" in aud_lower):
        audience_cue = (
            " [First-Year / Tenderfoot Note: Keep definitions concrete and hands-on, "
            "and pair each younger Scout with an experienced buddy during practice.]"
        )
    elif "older" in aud_lower or "eagle" in aud_lower or "14" in aud_lower:
        audience_cue = (
            " [Eagle Prep Note: Challenge your Senior Patrol, Star, and Life Scouts to explain the underlying "
            "mechanisms and model the BSA EDGE method for younger patrol members.]"
        )

    local_cue = (
        f" [Local Field Connection: {_sanitize_no_ellipsis_or_emdash(eff_local_callout)}]"
        if eff_local_callout
        else ""
    )

    syllabus_bucket = _sanitize_no_ellipsis_or_emdash(
        str(req_data.get("syllabus_bucket") or (
            "In-Class Demonstration" if execution_mode == ExecutionMode.HANDS_ON_SKILL_STATION.value
            else ("Pre-Class Prerequisite" if execution_mode == ExecutionMode.PREREQUISITE_CAMPOUT_HOME.value else "In-Class Concept")
        ))
    )
    edge_stage = (
        "Demonstrate & Guide"
        if execution_mode == ExecutionMode.HANDS_ON_SKILL_STATION.value
        else ("Guide & Enable" if execution_mode == ExecutionMode.PREREQUISITE_CAMPOUT_HOME.value else "Explain & Demonstrate")
    )
    page_cite = _sanitize_no_ellipsis_or_emdash(
        str(req_data.get("pamphlet_page_citation") or s_dict.get("pamphlet_reference") or f"BSA {clean_badge} Pamphlet, Req {clean_req}")
    )
    wb_org = req_data.get("workbook_organizer") or s_dict.get("workbook_table_ref") or {}
    wb_type = _format_workbook_organizer_label(wb_org)
    # Strip duplicate 'Workbook Requirement X • ' prefix if wb_org was already a formatted string
    wb_type_clean = re.sub(r"^(?:Scout\s+)?Workbook\s+Req(?:uirement)?\s+[^•\-]+\s*[•\-]\s*", "", wb_type, flags=re.IGNORECASE).strip() or wb_type

    req_display_label = f"Reqs {sub_range_label}" if sub_range_label and "-" in sub_range_label else f"Requirement {sub_range_label or clean_req}"

    # Determine misconception pair: use curated non-generic misconception on the lead slide (slide_idx_in_req == 0),
    # rotate through distinct sub-requirement misconceptions on child slides when available, and synthesize a concrete,
    # slide-scoped subject-matter misconception whenever generic or already used on the lead slide.
    parent_mp_dict = (req_dict or {}).get("common_misconception_pair") if isinstance((req_dict or {}).get("common_misconception_pair"), dict) else {}
    parent_myth = _sanitize_no_ellipsis_or_emdash(str(parent_mp_dict.get("misconception") or parent_mp_dict.get("myth") or ""))
    parent_fact = _sanitize_no_ellipsis_or_emdash(str(parent_mp_dict.get("fact") or parent_mp_dict.get("fact_correction") or ""))
    parent_myth_norm = parent_myth.strip().lower()

    misc_pair = req_data.get("common_misconception_pair") if isinstance(req_data.get("common_misconception_pair"), dict) else {}
    raw_myth = _sanitize_no_ellipsis_or_emdash(str(misc_pair.get("misconception") or misc_pair.get("myth") or ""))
    raw_fact = _sanitize_no_ellipsis_or_emdash(str(misc_pair.get("fact") or misc_pair.get("fact_correction") or ""))

    sub_misc_candidates: List[Tuple[str, str]] = []
    seen_sub_myths: set = {parent_myth_norm} if parent_myth_norm else set()

    def _add_misc_candidate(mp_obj: Any) -> None:
        if not isinstance(mp_obj, dict):
            return
        sm = _sanitize_no_ellipsis_or_emdash(str(mp_obj.get("misconception") or mp_obj.get("myth") or ""))
        sf = _sanitize_no_ellipsis_or_emdash(str(mp_obj.get("fact") or mp_obj.get("fact_correction") or ""))
        sm_low = sm.strip().lower()
        if sm and sf and not _is_generic_meta_misconception(sm, sf) and sm_low not in seen_sub_myths:
            seen_sub_myths.add(sm_low)
            sub_misc_candidates.append((sm, sf))

    for mp_it in list(req_data.get("misconception_pool") or []) + list((req_dict or {}).get("misconception_pool") or []):
        _add_misc_candidate(mp_it)

    def _collect_sub_miscs_recursive(nodes_list: List[Any]) -> None:
        for sr_item in nodes_list:
            if not isinstance(sr_item, dict):
                continue
            _add_misc_candidate(sr_item.get("common_misconception_pair"))
            for mp_it in (sr_item.get("misconception_pool") or []):
                _add_misc_candidate(mp_it)
            ch_list = sr_item.get("children") or sr_item.get("sub_requirements") or []
            if ch_list:
                _collect_sub_miscs_recursive(list(ch_list))

    _collect_sub_miscs_recursive(list((req_dict or {}).get("sub_requirements") or []))

    used_myths_in_deck = s_dict.get("_used_myths_in_deck")
    _quiz_only_archs = (
        SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value,
    )

    chosen_pair: Optional[Tuple[str, str]] = None
    if arch not in _quiz_only_archs and not quiz_item:
        ordered_candidates: List[Tuple[str, str]] = []
        if slide_idx_in_req == 0:
            if parent_myth and parent_fact:
                ordered_candidates.append((parent_myth, parent_fact))
            if raw_myth and raw_fact:
                ordered_candidates.append((raw_myth, raw_fact))
            ordered_candidates.extend(sub_misc_candidates)
            if precomp_myth and precomp_fact:
                ordered_candidates.append((precomp_myth, precomp_fact))
        else:
            if matched_sub_ids and raw_myth and raw_fact and raw_myth.strip().lower() != parent_myth_norm:
                ordered_candidates.append((raw_myth, raw_fact))
            if sub_misc_candidates:
                rot_idx = (slide_idx_in_req - 1) % len(sub_misc_candidates)
                ordered_candidates.extend(sub_misc_candidates[rot_idx:] + sub_misc_candidates[:rot_idx])
            if parent_myth and parent_fact:
                ordered_candidates.append((parent_myth, parent_fact))
            if raw_myth and raw_fact:
                ordered_candidates.append((raw_myth, raw_fact))
            if precomp_myth and precomp_fact and precomp_myth.strip().lower() != parent_myth_norm:
                ordered_candidates.append((precomp_myth, precomp_fact))
        for cm, cf in ordered_candidates:
            if not _is_generic_meta_misconception(cm, cf):
                cm_low = cm.strip().lower()
                if not isinstance(used_myths_in_deck, set) or cm_low not in used_myths_in_deck:
                    chosen_pair = (cm, cf)
                    break
        if chosen_pair is None and ordered_candidates:
            base_m, base_f = ordered_candidates[slide_idx_in_req % len(ordered_candidates)]
            if not _is_generic_meta_misconception(base_m, base_f):
                ctx_m = f"{base_m.rstrip('.!? ')} (specifically during \"{clean_title}\")."
                chosen_pair = (ctx_m, base_f)

    if chosen_pair is not None:
        myth_txt, fact_txt = chosen_pair
    else:
        myth_txt, fact_txt = _synthesize_subject_matter_misconception(
            clean_badge=clean_badge,
            clean_req=clean_req,
            clean_title=clean_title,
            arch=arch,
            meaningful_topics=dedup_topics,
            parsed_points=parsed_points,
            page_cite=page_cite,
            slide_idx_in_req=slide_idx_in_req,
            slide_seed=slide_seed,
            comparison_data=comparison_data,
            worked_example=worked_example,
            quiz_item=quiz_item,
            gear_checklist=gear_checklist,
            range_label=sub_range_label,
        )
        if isinstance(used_myths_in_deck, set) and myth_txt.strip().lower() in used_myths_in_deck:
            myth_txt = f"{myth_txt.rstrip('.!? ')} when working on \"{clean_title}\"."

    if isinstance(used_myths_in_deck, set) and myth_txt:
        used_myths_in_deck.add(myth_txt.strip().lower())

    # -------------------------------------------------------------------------
    # CASE 1: REQUIREMENTS OVERVIEW MATRIX (SLIDE 2)
    # -------------------------------------------------------------------------
    if arch == SlideArchetype.REQUIREMENTS_TRIAGE_MATRIX.value or clean_req.lower() == "overview":
        ov = overview_summary or {}
        in_class_list = ", ".join((ov.get("in_class") or [])[:5]) or "core concepts and safety rules"
        station_list = ", ".join((ov.get("station") or [])[:5]) or "hands-on field skill stations"
        prereq_list = ", ".join((ov.get("prereq") or [])[:5]) or "outdoor logs and home preparation"
        total_r = ov.get("total_count", [str(len(pts))])[0]
        pacing_line = (
            f"[PACING & MODALITY] 3 min | Syllabus Roadmap | EDGE: Explain & Plan. "
            f"[Gesture to the Requirements Overview grid on screen] Welcome to the {clean_badge} Merit Badge, Scouts! "
            f"Over our sessions together, we will work through all {total_r} official requirements from your {clean_badge} Merit Badge Pamphlet, "
            f"grouped into three practical tracks. "
            f"[Point to the Blue In-Class cards] First, our discussion topics ({in_class_list}) cover the core knowledge and safety principles we unpack as a patrol. "
            f"[Point to the Olive Skill Station cards] Second, our hands-on skill stations ({station_list}) are where you and your buddy physically practice and demonstrate techniques using the BSA EDGE method. "
            f"[Point to the Red Prerequisite cards] Third, our campout, field, and home requirements ({prereq_list}) are the real-world logs and projects you bring to our counselor conference.{local_cue}{audience_cue}"
        )
        ask_line = (
            f"[ASK SCOUTS FIRST] Looking at our {clean_badge} Requirements Overview matrix, which requirement track ({in_class_list} vs. {station_list}) requires pre-class or home-troop preparation before Blue Card sign-off?"
        )
        key_line = (
            f"[EXPECTED PAMPHLET ANSWER KEY] Reference: Official {clean_badge} Merit Badge Pamphlet Table of Contents. "
            f"[Expected Answer: Prerequisite and home-troop requirements ({prereq_list}) require field logs, campout execution, or family review outside the classroom, while {in_class_list} and {station_list} are completed in class.]"
        )
        misc_line = (
            f"[COMMON MISCONCEPTION TO CORRECT] Myth: Attending a Merit Badge clinic automatically signs off every requirement on the Blue Card. "
            f"BSA Pamphlet Fact: Under Scouting America Guide to Advancement Section 7.0.3.2, each Scout must individually fulfill every requirement as written, and home-troop prerequisites ({prereq_list}) must be verified with evidence."
        )
        rubric_line = (
            f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Hold up a sample {clean_badge} Fillable Scout Workbook and Blue Card #34124] "
            f"Verify each Scout has their signed Application for Merit Badge (#34124) or Scoutbook connection and knows which requirements belong to Session 1 through Session 4."
        )
        return "\n".join(_sanitize_no_ellipsis_or_emdash(ln) for ln in (pacing_line, ask_line, key_line, misc_line, rubric_line))

    # -------------------------------------------------------------------------
    # CASE 2: SOURCES & REFERENCES (FINAL SLIDE)
    # -------------------------------------------------------------------------
    if arch == "SOURCES_AND_REFERENCES" or clean_req.lower() == "sources":
        pacing_line = (
            f"[PACING & MODALITY] 2 min | Final Checkout & References | EDGE: Enable. "
            f"[Point to the Official Pamphlet and Resource links on screen] That wraps up our slide walkthrough for the {clean_badge} Merit Badge! "
            f"Before we sit down for your individual counselor sign-off conference, double-check your {clean_badge} Merit Badge Pamphlet and the official Scouting America Digital Resource Guide for any definitions or diagrams you want to review. "
            f"[Hold up a Blue Card or open Scoutbook] Bring your completed {clean_badge} Workbook logs, your field sketches or project artifacts, and your Blue Card or Scoutbook record when you come up for verification. "
            "As a quick note on the bottom card, this slide deck and companion workbook were built with the Scouts BSA Merit Badge Counselor Workbench created by Eric Clayberg of Troop 19 in Middleton, Massachusetts."
        )
        ask_line = (
            f"[ASK SCOUTS FIRST] Before coming up for your final {clean_badge} Blue Card (#34124) conference, what items and verification evidence should you have ready for your counselor?"
        )
        key_line = (
            f"[EXPECTED PAMPHLET ANSWER KEY] Reference: Scouting America Guide to Advancement Section 7.0.3.2 and Official {clean_badge} Pamphlet. "
            f"[Expected Answer: Bring your signed Blue Card (#34124) or Scoutbook record, any prerequisite logs or field artifacts, and be ready to explain or demonstrate any open requirement.]"
        )
        misc_line = (
            "[COMMON MISCONCEPTION TO CORRECT] Myth: A partial Blue Card expires at the end of summer camp or the Merit Badge College. "
            "BSA Pamphlet Fact: Under Scouting America rules, signed partial requirements on a Blue Card (#34124) never expire until the Scout turns 18."
        )
        rubric_line = (
            "[DEMONSTRATION & SIGN-OFF RUBRIC] [Hold up Blue Card #34124 Applicant's Record and Counselor's Record] "
            "Initial each completed requirement in the Multi-Troop Blue Card Triage Matrix and issue a Smart Partial plan for any remaining home-troop follow-up items."
        )
        return "\n".join(_sanitize_no_ellipsis_or_emdash(ln) for ln in (pacing_line, ask_line, key_line, misc_line, rubric_line))

    # Build non-redundant facilitator stage cues referencing the slide cards without reading them verbatim
    card_cue_parts: List[str] = []
    for idx_p, (anc, bdy) in enumerate(parsed_points[:4]):
        card_num = idx_p + 1
        nice_anc = _extract_meaningful_topic_phrase(anc, bdy, anc)
        card_cue_parts.append(f"[Point to Card {card_num}: {nice_anc}]")

    card_cues_str = " -> ".join(card_cue_parts) if card_cue_parts else f"[Point to Card 1: {clean_title}]"
    topic_summary = ", ".join(dedup_topics[:4]) if dedup_topics else clean_title

    topic_1 = dedup_topics[0] if dedup_topics else clean_title
    topic_2 = dedup_topics[1] if len(dedup_topics) > 1 else topic_1
    first_body = parsed_points[0][1] if parsed_points else (clean_req_text or clean_title)
    second_body = parsed_points[1][1] if len(parsed_points) > 1 else first_body

    # Reference clean_caption ONLY in [PACING & MODALITY] (never duplicate it in [DEMONSTRATION & SIGN-OFF RUBRIC])
    visual_tie_in = ""
    if has_visual and clean_caption:
        vis_templates = [
            f" [Gesture to the right-hand figure: {clean_caption}] Have Scouts trace how {topic_1} is illustrated on the diagram.",
            f" [Point to the visual figure: {clean_caption}] Ask a volunteer to point out where {topic_1} and {topic_2} appear in the illustration.",
            f" [Trace across the diagram: {clean_caption}] Connect each callout on the visual directly to {topic_1}.",
            f" [Gesture to the illustrated graphic: {clean_caption}] Use the figure to show how {topic_1} works in real field conditions.",
            f" [Point to the right-hand diagram: {clean_caption}] Walk the patrol through the visual cues for {topic_1}.",
            f" [Gesture to the slide figure: {clean_caption}] Highlight the visual contrast supporting {clean_badge} {req_display_label}.",
        ]
        visual_tie_in = vis_templates[tpl_idx]

    safety_note = (
        f" [Safety Check] Under the BSA Guide to Safe Scouting, enforce: {_sanitize_no_ellipsis_or_emdash(safety_callout)}"
        if safety_callout
        else ""
    )

    raw_est = req_data.get("estimated_minutes")
    default_slide_mins = 4 if execution_mode == ExecutionMode.HANDS_ON_SKILL_STATION.value else 3
    if isinstance(raw_est, (int, float)):
        per_slide_m = max(2, min(4, round(float(raw_est) / 5.0))) if raw_est > 5 else max(2, int(raw_est))
        est_minutes = f"{per_slide_m} min"
    elif isinstance(raw_est, str) and raw_est.strip():
        m_num = re.search(r"(\d+)", raw_est)
        if m_num and int(m_num.group(1)) > 5:
            per_slide_m = max(2, min(4, round(int(m_num.group(1)) / 5.0)))
            est_minutes = f"{per_slide_m} min"
        else:
            est_minutes = raw_est.strip() if raw_est.strip().endswith("min") else f"{raw_est.strip()} min"
    else:
        est_minutes = f"{default_slide_mins} min"

    action_verb = str(req_data.get("action_verb") or "").strip().lower()
    _valid_verbs = {"explain", "discuss", "describe", "demonstrate", "show", "identify", "prepare", "list", "review", "verify", "complete", "perform"}
    if action_verb not in _valid_verbs:
        m_verb = re.match(r"^(explain|discuss|describe|demonstrate|show|identify|prepare|list|review|perform)\b", clean_req_text, flags=re.IGNORECASE)
        action_verb = m_verb.group(1).lower() if m_verb else ("demonstrate" if execution_mode == ExecutionMode.HANDS_ON_SKILL_STATION.value else "explain")
    action_verb_3p = _conjugate_third_person_singular(action_verb)

    # 1. [PACING & MODALITY] — 6 archetype- & index-differentiated facilitator walkthroughs
    pacing_walkthroughs = [
        (
            f"Open {clean_title} ({clean_badge} {req_display_label}) by stepping through {card_cues_str}. "
            f"Have buddy pairs connect {topic_summary} to how they will {action_verb} this requirement in the field."
        ),
        (
            f"Walk the patrol through {clean_title} for {clean_badge} {req_display_label} using {card_cues_str}. "
            f"Focus discussion on why {topic_1} and {topic_2} matter during real troop operations rather than reading the cards word-for-word."
        ),
        (
            f"Use {card_cues_str} to frame {clean_title} ({clean_badge} {req_display_label}). "
            f"Challenge each patrol table to explain the cause-and-effect link between {topic_1} and {topic_2}."
        ),
        (
            f"Coach Scouts through {clean_title} ({clean_badge} {req_display_label}) via {card_cues_str}. "
            f"Ask buddy teams to spot the practical field standard in {topic_summary} before recording their workbook notes."
        ),
        (
            f"Anchor your session on {clean_title} ({clean_badge} {req_display_label}) with {card_cues_str}. "
            f"Invite a seasoned Scout to contrast proper execution of {topic_1} with common beginner shortcuts."
        ),
        (
            f"Pace this {clean_title} segment ({clean_badge} {req_display_label}) around {card_cues_str}. "
            f"Connect {topic_summary} directly to the hands-on verification standard Scouts need for Blue Card sign-off."
        ),
    ]
    pacing_block = (
        f"[PACING & MODALITY] {est_minutes} | {syllabus_bucket} | EDGE: {edge_stage} | {page_cite}. "
        f"{pacing_walkthroughs[tpl_idx]}{visual_tie_in}{safety_note}{local_cue}{audience_cue}"
    )

    # 2. [ASK SCOUTS FIRST] — Prioritize Gemini-curated Socratic questions across all non-quiz archetypes
    curated_socratic: List[str] = []
    for q in list(req_data.get("socratic_questions") or []) + list((req_dict or {}).get("socratic_questions") or []):
        q_c = _sanitize_no_ellipsis_or_emdash(str(q).strip())
        if len(q_c) >= 25 and q_c not in curated_socratic:
            curated_socratic.append(q_c)

    def _collect_sub_socratic_recursive(nodes_list: List[Any]) -> None:
        for sr_item in nodes_list:
            if not isinstance(sr_item, dict):
                continue
            for q in (sr_item.get("socratic_questions") or []):
                q_c = _sanitize_no_ellipsis_or_emdash(str(q).strip())
                if len(q_c) >= 25 and q_c not in curated_socratic:
                    curated_socratic.append(q_c)
            ch_list = sr_item.get("children") or sr_item.get("sub_requirements") or []
            if ch_list:
                _collect_sub_socratic_recursive(list(ch_list))

    _collect_sub_socratic_recursive(list((req_dict or {}).get("sub_requirements") or []))

    used_asks_in_deck = s_dict.get("_used_asks_in_deck")
    if arch == SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value or quiz_item:
        qi = quiz_item or {}
        scenario = _sanitize_no_ellipsis_or_emdash(
            str(qi.get("scenario_prompt") or (pts[0] if pts else f"What action should your patrol take during {clean_title}?"))
        )
        if scenario.startswith("How do "):
            scenario = "In what specific ways do " + scenario[len("How do "):]
        if is_hazard_ctx:
            ask_block = (
                f"[ASK SCOUTS FIRST] Pose this scenario to buddy pairs before revealing the answer key: \"{scenario}\" Which option do you choose first, and what hazard does it prevent?"
            )
        else:
            ask_block = (
                f"[ASK SCOUTS FIRST] Pose this scenario to buddy pairs before revealing the answer key: \"{scenario}\" Which option do you choose first, and why does it satisfy the {clean_badge} Merit Badge Pamphlet standard?"
            )
    elif curated_socratic:
        chosen_q = ""
        start_q_idx = slide_idx_in_req % len(curated_socratic)
        rotated_q = curated_socratic[start_q_idx:] + curated_socratic[:start_q_idx]
        for cand_q in rotated_q:
            q_norm = cand_q.rstrip("?.! ").lower()
            if not isinstance(used_asks_in_deck, set) or q_norm not in used_asks_in_deck:
                chosen_q = cand_q.rstrip("?.! ") + "?"
                break
        if not chosen_q:
            base_q = rotated_q[0].rstrip("?.! ") + "?"
            chosen_q = f"{base_q} (Focus on {topic_1} and {topic_2} on \"{clean_title}\".)"
        if isinstance(used_asks_in_deck, set):
            used_asks_in_deck.add(chosen_q.rstrip("?.! ").lower())
        ask_block = f"[ASK SCOUTS FIRST] {chosen_q}"
    elif arch == SlideArchetype.DIFFERENTIAL_COMPARISON_2COL.value or comparison_data:
        cd = comparison_data or {}
        left_h = _sanitize_no_ellipsis_or_emdash(str(cd.get("left_header") or topic_1))
        right_h = _sanitize_no_ellipsis_or_emdash(str(cd.get("right_header") or topic_2))
        comp_asks = [
            f"[ASK SCOUTS FIRST] Before looking at the two columns on screen, what is the #1 field clue that distinguishes {left_h} from {right_h} in {clean_badge} {req_display_label}?",
            f"[ASK SCOUTS FIRST] If your patrol encounters this situation at camp, how do you tell within 30 seconds whether you are dealing with {left_h} or {right_h}?",
            f"[ASK SCOUTS FIRST] Why does confusing {left_h} with {right_h} lead to the wrong action in {clean_badge} {req_display_label}, and what check separates them?",
        ]
        ask_block = comp_asks[tpl_idx % len(comp_asks)]
    elif arch == SlideArchetype.STEP_BY_STEP_PROCEDURE_4CARD.value:
        proc_asks = [
            f"[ASK SCOUTS FIRST] Why must your buddy pair complete {topic_1} before moving to {topic_2} during \"{clean_title},\" and what goes wrong if Step 1 is skipped?",
            f"[ASK SCOUTS FIRST] Looking at our 4-step sequence for \"{clean_title},\" which transition between {topic_1} and {topic_2} requires the closest communication between buddies?",
            f"[ASK SCOUTS FIRST] When performing \"{clean_title}\" in the field for {clean_badge} {req_display_label}, how do you verify {topic_1} is locked in before advancing to {topic_2}?",
        ]
        ask_block = proc_asks[tpl_idx % len(proc_asks)]
    elif arch == SlideArchetype.GEAR_CHECKLIST_GRID.value or gear_checklist:
        gear_asks = [
            f"[ASK SCOUTS FIRST] During a 60-second patrol shakedown for \"{clean_title},\" why is {topic_1} critical, and what happens if it is missing or damaged on the trail?",
            f"[ASK SCOUTS FIRST] Which item on our \"{clean_title}\" checklist ({topic_1} vs. {topic_2}) are new Scouts most likely to forget before a troop outing, and why?",
        ]
        ask_block = gear_asks[tpl_idx % len(gear_asks)]
    elif arch == SlideArchetype.WORKED_EXAMPLE_TEMPLATE.value or worked_example:
        ask_block = (
            f"[ASK SCOUTS FIRST] Compare a vague one-line note with this worked example for \"{clean_title}\": what specific detail in {topic_1} makes this log ready for {clean_badge} {req_display_label} sign-off?"
        )
    elif len(dedup_topics) >= 2:
        general_asks_plural = [
            f"[ASK SCOUTS FIRST] How do {topic_1} and {topic_2} reinforce each other in {clean_badge} {req_display_label}, and where would your patrol apply both on a troop outing?",
            f"[ASK SCOUTS FIRST] If a younger Scout asked you why {topic_1} matters alongside {topic_2} in {clean_badge} {req_display_label}, what real-world example would you give first?",
            f"[ASK SCOUTS FIRST] What is the practical connection between {topic_1} and {topic_2} during \"{clean_title},\" and what field clue tells you both are working?",
            f"[ASK SCOUTS FIRST] Before we unpack the cards on screen, how would your buddy pair use {topic_1} and {topic_2} to solve a real problem in {clean_badge} {req_display_label}?",
            f"[ASK SCOUTS FIRST] Between {topic_1} and {topic_2} on this slide, which one requires the most preparation ahead of time for {clean_badge} {req_display_label}, and why?",
            f"[ASK SCOUTS FIRST] When evaluating {clean_title} ({clean_badge} {req_display_label}), how does mastering {topic_1} prepare your patrol to handle {topic_2}?",
        ]
        ask_block = general_asks_plural[tpl_idx]
    else:
        general_asks_singular = [
            f"[ASK SCOUTS FIRST] How does {topic_1} apply in {clean_badge} {req_display_label}, and where can your patrol see its impact on a real Scouting activity?",
            f"[ASK SCOUTS FIRST] Why is {topic_1} a core requirement in {clean_badge} {req_display_label}, and what field sign shows a Scout has mastered it?",
            f"[ASK SCOUTS FIRST] If you had to coach a Tenderfoot buddy on {topic_1} for {clean_badge} {req_display_label}, what is the very first check you would show them?",
            f"[ASK SCOUTS FIRST] What makes {topic_1} essential during \"{clean_title},\" and how do you verify it under real outdoor conditions?",
            f"[ASK SCOUTS FIRST] Before we review the pamphlet standard for {clean_badge} {req_display_label}, what is the most important rule to remember about {topic_1}?",
            f"[ASK SCOUTS FIRST] How does understanding {topic_1} help your patrol stay prepared and effective during {clean_badge} {req_display_label}?",
        ]
        ask_block = general_asks_singular[tpl_idx]

    # 3. [EXPECTED PAMPHLET ANSWER KEY] — Scoped sub-requirements & rotated pamphlet excerpts
    sub_reqs = list(req_data.get("sub_requirements") or [])
    sub_req_summary = ""
    if sub_reqs:
        # Rotate sub_reqs slice if there are more than 4 and not already chunk-scoped
        sr_offset = (max(0, int(slide_idx_in_req)) * 3) % max(1, len(sub_reqs)) if len(sub_reqs) > 4 else 0
        rotated_subs = (sub_reqs[sr_offset:] + sub_reqs[:sr_offset])[:4]
        sub_snippets = []
        for sr in rotated_subs:
            sr_lbl = str(sr.get("sub_req_label") or sr.get("sub_id") or sr.get("id") or sr.get("req_id") or "").strip()
            sr_txt = _sanitize_no_ellipsis_or_emdash(
                str(sr.get("pamphlet_summary") or sr.get("sub_req_text") or sr.get("text") or "").strip()
            )
            if sr_txt:
                sub_snippets.append(f"({sr_lbl}) {sr_txt}" if sr_lbl else sr_txt)
        if sub_snippets:
            sub_req_summary = f"Scoped sub-requirements ({req_display_label}): " + "; ".join(sub_snippets) + ". "

    if slide_idx_in_req == 0 and clean_req_text:
        base_extra = " ".join(extra_insights[:1]) if extra_insights else sub_req_summary.strip()
        supplementary_detail = (
            f"Official BSA {req_display_label} standard: {clean_req_text} {base_extra}".strip()
        )
    elif extra_insights:
        supplementary_detail = " ".join(extra_insights[:2])
        if sub_req_summary and sub_range_label:
            supplementary_detail = f"{sub_req_summary}{supplementary_detail}"
    elif sub_req_summary:
        supplementary_detail = sub_req_summary.strip()
    elif clean_req_text:
        supplementary_detail = f"Official BSA {req_display_label} standard: {clean_req_text}"
    else:
        supplementary_detail = f"Verify {topic_summary} against the official {clean_badge} Merit Badge Pamphlet."

    if arch == SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value or quiz_item:
        qi = quiz_item or {}
        answer = _sanitize_no_ellipsis_or_emdash(str(qi.get("correct_answer") or topic_1).rstrip("."))
        explanation = _sanitize_no_ellipsis_or_emdash(str(qi.get("explanation") or first_body).rstrip("."))
        key_block = (
            f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {page_cite}. {supplementary_detail} "
            f"[Expected Answer: {answer}. {explanation}.]"
        )
    elif worked_example and isinstance(worked_example, dict):
        we_out = _sanitize_no_ellipsis_or_emdash(
            str(worked_example.get("sample_output") or worked_example.get("counselor_tip") or first_body).rstrip(".")
        )
        key_block = (
            f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {page_cite}. {supplementary_detail} "
            f"[Expected Answer: Verify concrete workbook entries matching {we_out} for {topic_1}.]"
        )
    elif comparison_data and isinstance(comparison_data, dict):
        left_h = _sanitize_no_ellipsis_or_emdash(str(comparison_data.get("left_header") or topic_1))
        right_h = _sanitize_no_ellipsis_or_emdash(str(comparison_data.get("right_header") or topic_2))
        l_pts_raw = [str(x).strip() for x in (comparison_data.get("left_points") or []) if str(x).strip()]
        r_pts_raw = [str(x).strip() for x in (comparison_data.get("right_points") or []) if str(x).strip()]
        l_summary = _sanitize_no_ellipsis_or_emdash(l_pts_raw[0].rstrip(".")) if l_pts_raw else first_body.rstrip(".")
        r_summary = _sanitize_no_ellipsis_or_emdash(r_pts_raw[0].rstrip(".")) if r_pts_raw else second_body.rstrip(".")
        key_block = (
            f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {page_cite}. {supplementary_detail} "
            f"[Expected Answer: Contrast {left_h} ({l_summary}) against {right_h} ({r_summary}).]"
        )
    else:
        if extra_insights:
            key_templates = [
                f"[Expected Answer: Scouts should cite {topic_1} and connect it to {topic_2} using the {page_cite} guidance above.]",
                f"[Expected Answer: Look for accurate explanations of {topic_summary} grounded in {page_cite}.]",
                f"[Expected Answer: Verify each Scout can state how {topic_1} and {topic_2} apply in field conditions per {page_cite}.]",
                f"[Expected Answer: Patrol responses should highlight {topic_1} alongside {topic_2} per {page_cite}.]",
                f"[Expected Answer: Confirm Scouts identify the key mechanism behind {topic_1} and practical check for {topic_2}.]",
                f"[Expected Answer: Listen for concrete field examples of {topic_summary} grounded in {page_cite}.]",
            ]
        else:
            key_templates = [
                f"[Expected Answer: Scouts should cite {topic_1} ({first_body.rstrip('.')}) and connect it to {topic_2} ({second_body.rstrip('.')}).]",
                f"[Expected Answer: Look for accurate explanations of {topic_summary}, specifically noting how {first_body.rstrip('.')}.]",
                f"[Expected Answer: Verify each Scout can state why {topic_1} requires {first_body.rstrip('.')} and how {topic_2} ensures {second_body.rstrip('.')}.]",
                f"[Expected Answer: Patrol responses should highlight {topic_1} ({first_body.rstrip('.')}) alongside {topic_2} ({second_body.rstrip('.')}) per {page_cite}.]",
                f"[Expected Answer: Confirm Scouts identify the key mechanism behind {topic_1} ({first_body.rstrip('.')}) and practical check for {topic_2}.]",
                f"[Expected Answer: Listen for concrete field examples of {topic_summary} grounded in {first_body.rstrip('.')}.]",
            ]
        key_block = (
            f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {page_cite}. {supplementary_detail} "
            f"{key_templates[tpl_idx]}"
        )

    # 4. [COMMON MISCONCEPTION TO CORRECT]
    misc_block = (
        f"[COMMON MISCONCEPTION TO CORRECT] Myth: {myth_txt} | BSA Pamphlet Fact: {fact_txt}"
    )

    # 5. [DEMONSTRATION & SIGN-OFF RUBRIC] — Never repeats clean_caption; 6 varied templates tailored to modality & verb
    if arch == SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value or quiz_item:
        q_rule_noun = "key safety rule" if is_hazard_ctx else "key pamphlet principle"
        demo_action = (
            f"[Pause for patrol decision check and hold up the {clean_badge} Workbook] Have each buddy pair justify their chosen response for {clean_title} and record the {q_rule_noun} under {req_display_label} ({wb_type_clean})."
        )
    elif arch == SlideArchetype.DIFFERENTIAL_COMPARISON_2COL.value or comparison_data:
        demo_action = (
            f"[Point to the two comparison columns and open the {clean_badge} Fillable Scout Workbook] Have Scouts complete the {wb_type_clean} for {req_display_label}, contrasting {topic_1} and {topic_2} in their own words."
        )
    elif arch == SlideArchetype.WORKED_EXAMPLE_TEMPLATE.value or worked_example:
        demo_action = (
            f"[Hold up the {clean_badge} Scout Log template on screen] Walk Scouts through recording a complete entry for {clean_title} ({topic_1} and {topic_2}) in their {wb_type_clean}."
        )
    elif arch == SlideArchetype.GEAR_CHECKLIST_GRID.value or gear_checklist:
        demo_action = (
            f"[Conduct a hands-on patrol gear shakedown for {clean_title}] Have buddy pairs physically inspect {topic_1} and {topic_2} and check off each item in their {wb_type_clean}."
        )
    elif execution_mode == ExecutionMode.HANDS_ON_SKILL_STATION.value or arch == SlideArchetype.STEP_BY_STEP_PROCEDURE_4CARD.value:
        demo_actions = [
            f"[Hold up the station gear and model {topic_1} using the BSA EDGE method] Demonstrate {topic_1} followed by {topic_2} at half-speed, then coach buddy pairs as they practice.",
            f"[Point to the skill station table] Walk a two-Scout buddy team through {topic_1} ({first_body.rstrip('.')}) and {topic_2}, verifying each hands-on step.",
            f"[Gesture to the practice station] Use Explain -> Demonstrate -> Guide -> Enable so every Scout physically performs {topic_1} and {topic_2} without prompts.",
            f"[Pause for live buddy station practice] Observe each pair executing {topic_1} and {topic_2}, correcting hand placement and sequence before sign-off.",
            f"[Hold up the field equipment for {req_display_label}] Model the transition from {topic_1} to {topic_2} and have each buddy pair demonstrate it back.",
            f"[Point to Card 1 and step to the demonstration area] Coach Scouts through a hands-on trial of {topic_summary} until every Scout demonstrates independent mastery.",
        ]
        demo_action = demo_actions[tpl_idx]
    else:
        demo_actions_concept = [
            f"[Hold up the {clean_badge} Fillable Scout Workbook] Direct Scouts to {req_display_label} ({wb_type_clean}) to record their key definitions and field examples for {topic_summary}.",
            f"[Pause for 30-second buddy review] Have partners quiz each other on {topic_1} and {topic_2} while completing the {wb_type_clean} in their {clean_badge} Workbook.",
            f"[Point to the {req_display_label} section of the Scout Workbook] Coach Scouts to document concrete examples of {topic_1} and {topic_2} using the {wb_type_clean}.",
            f"[Gesture to the patrol tables] Ask each buddy pair to compare their {wb_type_clean} notes on {topic_1} and {topic_2} before individual counselor verification.",
            f"[Hold up a sample signed Blue Card #34124 and {clean_badge} Workbook] Review what a complete verbal explanation of {topic_summary} looks like for {req_display_label}.",
            f"[Pause for individual workbook check] Confirm every Scout has filled in the {wb_type_clean} for {req_display_label} covering {topic_1} and {topic_2}.",
        ]
        demo_action = demo_actions_concept[tpl_idx]

    signoff_templates = [
        f"Sign-Off Standard (Scout Workbook {req_display_label} • {wb_type_clean}): Each Scout must individually {action_verb} {topic_summary} per {page_cite}.",
        f"Blue Card (#34124) Verification ({req_display_label} • {wb_type_clean}): Confirm each Scout can accurately {action_verb} {topic_1} and {topic_2} grounded in {page_cite}.",
        f"Counselor Sign-Off Rubric (Scout Workbook {req_display_label} • {wb_type_clean}): Verify individual mastery of {topic_summary} against {page_cite}.",
        f"Advancement Check ({req_display_label} • {wb_type_clean}): Under Guide to Advancement Section 7.0.3.2, each Scout personally {action_verb_3p} {topic_1} and {topic_2} ({page_cite}).",
        f"Verification Standard (Scout Workbook {req_display_label} • {wb_type_clean}): Initial {req_display_label} once the Scout clearly {action_verb_3p} {topic_summary} per {page_cite}.",
        f"Sign-Off Criteria ({req_display_label} • {wb_type_clean}): Check that the Scout's verbal or hands-on response covers {topic_1} and {topic_2} ({page_cite}).",
    ]
    rubric_block = f"[DEMONSTRATION & SIGN-OFF RUBRIC] {demo_action} {signoff_templates[tpl_idx]}"

    return "\n".join(
        _sanitize_no_ellipsis_or_emdash(b)
        for b in (pacing_block, ask_block, key_block, misc_block, rubric_block)
    )


def _build_keynote_presenter_notes(
    badge_name: str,
    req_num: str,
    execution_mode: str,
    safety_callout: Optional[str] = None,
    slide_title: str = "",
    archetype: str = "CONCEPT_TEXT_SLIDE",
    req_text: str = "",
    bullet_points: Optional[List[str]] = None,
    req_dict: Optional[Dict[str, Any]] = None,
    comparison_data: Optional[Dict[str, Any]] = None,
    worked_example: Optional[Dict[str, Any]] = None,
    quiz_item: Optional[Dict[str, Any]] = None,
    gear_checklist: Optional[List[str]] = None,
    visual_caption: str = "",
    has_visual: bool = False,
    overview_summary: Optional[Dict[str, List[str]]] = None,
    audience_level: str = "All Scouts (Ages 11-17)",
    local_grounding_callout: str = "",
    slide_dict: Optional[Dict[str, Any]] = None,
    slide_idx_in_req: int = 0,
) -> str:
    """Wrapper around `_build_slide_teaching_notes` for slide-specific Counselor Teaching Notes."""
    return _build_slide_teaching_notes(
        badge_name=badge_name,
        req_num=req_num,
        execution_mode=execution_mode,
        slide_title=slide_title,
        archetype=archetype,
        req_text=req_text,
        bullet_points=bullet_points,
        req_dict=req_dict,
        comparison_data=comparison_data,
        worked_example=worked_example,
        quiz_item=quiz_item,
        gear_checklist=gear_checklist,
        visual_caption=visual_caption,
        has_visual=has_visual,
        safety_callout=safety_callout,
        overview_summary=overview_summary,
        audience_level=audience_level,
        local_grounding_callout=local_grounding_callout,
        slide_dict=slide_dict,
        slide_idx_in_req=slide_idx_in_req,
    )


def _polish_slide_bullet_for_card(
    raw_bullet: str,
    fallback_anchor: str = "Key Principle",
    max_anchor_chars: int = 44,
    max_body_words: int = 15,
    max_body_chars: int = 96,
) -> str:
    """Polishes a slide bullet so its anchor and body fit card bounds cleanly without render-time truncation."""
    import re
    from src.tools.pptx_builder import (
        _clean_text,
        _concise_anchor_title,
        _concise_card_body,
        _split_anchor_and_body,
    )

    txt = _sanitize_no_ellipsis_or_emdash(str(raw_bullet or "").strip())
    if not txt:
        return ""

    # Clean PDF extraction noise (ISBN, catalog numbers, all-caps series headers, bare page citations, glued camelCase words)
    txt = re.sub(r"\b(?:ISBN\s*[0-9\-X]+|35\d{3}|MERIT BADGE SERIES|BOY SCOUTS OF AMERICA)\b", "", txt, flags=re.IGNORECASE)
    txt = re.sub(r"^(?:pp?\.?\s*\d+(?:\s*[-–,]\s*\d+)?\s*[:.\-]?\s*)+", "", txt, flags=re.IGNORECASE).strip()
    if not txt or re.match(r"^(?:pp?\.?\s*\d+(?:\s*[-–,]\s*\d+)?\.?)$", txt, flags=re.IGNORECASE):
        return ""
    _keep_camel = {"Scoutbook", "PowerPoint", "YouTube", "JavaScript", "GitHub", "PlayStation", "eSports", "McDonald", " McDonalds", "iPhone", "iPad", "macOS", "OneDrive", "SharePoint", " WordPress", "LinkedIn", "GameCube", "SmartBoard", " RoboCup", "FirstNet", "AmeriCorps", "PeaceCorps", " JetBlue", "FedEx", "MasterCard", "QuickBooks", " AutoCAD", "SolidWorks"}
    def _unglue_camel(m: re.Match) -> str:
        full_w = m.group(0)
        if any(k.strip().lower() in full_w.lower() for k in _keep_camel):
            return full_w
        return f"{m.group(1)} {m.group(2)}"
    txt = re.sub(r"\b([a-z]{4,})([A-Z][a-z]{3,})\b", _unglue_camel, txt)
    _ocr_glued_map = {
        "whohave": "who have",
        "along-sleeved": "a long-sleeved",
        "toavoid": "to avoid",
        "thevictim": "the victim",
        "inwhich": "in which",
        "suchas": "such as",
        "aswell": "as well",
        "atleast": "at least",
        "morethan": "more than",
        "beable": "be able",
        "makea": "make a",
        "witha": "with a",
        "froma": "from a",
    }
    for bad_w, good_w in _ocr_glued_map.items():
        txt = re.sub(rf"\b{re.escape(bad_w)}\b", good_w, txt, flags=re.IGNORECASE)
    txt = re.sub(r"\s{2,}", " ", txt).strip()

    raw_a, raw_b = _split_anchor_and_body(txt, fallback_anchor)
    clean_a = _concise_anchor_title(raw_a, max_chars=max_anchor_chars).replace(":", "").strip(" .,-;")
    if "(" in clean_a and ")" not in clean_a:
        clean_a = clean_a.split("(", 1)[0].strip()
    elif clean_a.count("(") != clean_a.count(")"):
        clean_a = clean_a.replace("(", "").replace(")", "").strip()
    if len(clean_a) < 3 or re.match(r"^pp?\.?\s*\d+$", clean_a, flags=re.IGNORECASE):
        clean_a = _concise_anchor_title(fallback_anchor, max_chars=max_anchor_chars)

    body_src = (raw_b if raw_b else txt).strip()
    body_src = re.sub(r"^(?:pp?\.?\s*\d+(?:\s*[-–,]\s*\d+)?\s*[:.\-]?\s*)+", "", body_src, flags=re.IGNORECASE).strip()
    if not body_src or re.match(r"^(?:pp?\.?\s*\d+(?:\s*[-–,]\s*\d+)?\.?)$", body_src, flags=re.IGNORECASE):
        return ""
    # Remove unbalanced parentheses before concising
    if body_src.count("(") != body_src.count(")"):
        body_src = re.sub(r"\([^)]*$", "", body_src).replace("(", "").replace(")", "").strip()

    clean_b = _concise_card_body(body_src, max_words=max_body_words, max_chars=max_body_chars)
    if clean_b.count("(") != clean_b.count(")"):
        clean_b = re.sub(r"\([^)]*$", "", clean_b).replace("(", "").replace(")", "").strip()

    _dangling_words = {
        "a", "an", "the", "and", "or", "but", "nor", "for", "yet", "so",
        "in", "on", "at", "to", "from", "by", "with", "of", "as", "into",
        "like", "through", "after", "over", "between", "out", "against",
        "during", "without", "before", "under", "around", "among", "upon",
        "within", "along", "following", "across", "behind", "beyond", "plus",
        "except", "up", "down", "off", "above", "near", "than", "per", "via",
        "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "will", "would", "shall", "should", "may", "might",
        "must", "can", "could", "that", "which", "who", "whom", "whose", "where",
        "when", "why", "how", "while", "if", "because", "although", "though",
        "until", "unless", "since", "whether", "whereas", "your", "their", "our",
        "my", "his", "her", "its", "this", "these", "those", "some", "any", "each",
        "every", "either", "neither", "both", "such", "what", "whatever", "not", "no",
        "very", "more", "most", "other", "another", "and/or",
    }
    _abbrev_tails = {
        "e.g", "i.e", "u.s", "dr", "mr", "mrs", "ms", "st", "ft", "in", "oz", "lb",
        "lbs", "sec", "min", "hr", "hrs", "fig", "figs", "no", "nos", "vol", "ch",
        "pp", "p", "approx", "vs", "etc", "dept", "assn", "inc", "corp", "co", "jr", "sr",
    }
    b_words = clean_b.rstrip(".!?\"') -").split()
    while len(b_words) > 3:
        last_tok = re.sub(r"^[^A-Za-z0-9']+|[^A-Za-z0-9'.]+$", "", b_words[-1]).lower().rstrip(".")
        if not last_tok or last_tok in _dangling_words or last_tok in _abbrev_tails:
            b_words.pop()
        else:
            break
    clean_b = " ".join(b_words).rstrip(" ,;:-.")
    if not clean_b or re.match(r"^(?:pp?\.?\s*\d+)$", clean_b, flags=re.IGNORECASE):
        return ""
    if len(clean_b) < 16:
        clean_b = f"Explain and verify {clean_b} with your counselor"
    if not clean_b.endswith((".", "!", "?")):
        clean_b += "."

    # Final check that _concise_card_body on clean_b does not truncate it further
    re_checked_b = _concise_card_body(clean_b, max_words=max_body_words, max_chars=max_body_chars)
    if len(re_checked_b) < len(_clean_text(clean_b)):
        clean_b = re_checked_b
        if clean_b.count("(") != clean_b.count(")"):
            clean_b = clean_b.replace("(", "").replace(")", "").strip()
        if not clean_b.endswith((".", "!", "?")):
            clean_b = clean_b.rstrip(" ,;:-") + "."

    return f"{clean_a}: {clean_b}"


def _polish_slide_bullets_list(
    bullets: List[str],
    max_count: int = 4,
    max_total_chars: int = 435,
    max_anchor_chars: int = 44,
    max_body_words: int = 15,
    max_body_chars: int = 96,
    deck_seen_norms: Optional[set] = None,
    badge_name: str = "",
    req_num: str = "",
    slide_title: str = "",
) -> List[str]:
    """Polishes a list of slide bullets to fit card bounds, stay under 435 total chars, and avoid deck-wide duplicates."""
    import re
    from src.tools.pptx_builder import _concise_anchor_title

    out: List[str] = []
    local_seen: set = set()
    for idx_b, raw_b in enumerate(bullets):
        if len(out) >= max_count:
            break
        polished = _polish_slide_bullet_for_card(
            raw_b,
            fallback_anchor=f"Key Point {idx_b + 1}",
            max_anchor_chars=max_anchor_chars,
            max_body_words=max_body_words,
            max_body_chars=max_body_chars,
        )
        if not polished:
            continue
        norm = re.sub(r"[^a-z0-9]+", " ", polished.lower()).strip()
        if norm[:65] in local_seen:
            continue
        if deck_seen_norms is not None and len(norm) > 35 and norm in deck_seen_norms:
            # Disambiguate with slide context so two slides in the same deck never share an identical bullet
            if ": " in polished:
                anc_p, bod_p = polished.split(": ", 1)
                raw_ctx = re.sub(r"[^A-Za-z0-9 &/-]+", "", slide_title or f"Req {req_num}").strip()
                short_ctx = _concise_anchor_title(raw_ctx, max_chars=20)
                trimmed_anc = _concise_anchor_title(anc_p, max_chars=24)
                new_anc = f"{trimmed_anc} ({short_ctx})" if short_ctx and short_ctx.lower() not in anc_p.lower() else f"{trimmed_anc} {idx_b + 1}"
                polished = _polish_slide_bullet_for_card(
                    f"{new_anc}: {bod_p}",
                    fallback_anchor=new_anc,
                    max_anchor_chars=max_anchor_chars,
                    max_body_words=max_body_words,
                    max_body_chars=max_body_chars,
                )
                norm = re.sub(r"[^a-z0-9]+", " ", polished.lower()).strip()
        local_seen.add(norm[:65])
        if deck_seen_norms is not None and len(norm) > 35:
            deck_seen_norms.add(norm)
        out.append(polished)

    # Ensure total chars across all bullets on this slide stays <= max_total_chars (435)
    if sum(len(x) for x in out) > max_total_chars:
        tighter: List[str] = []
        for idx_b, b_it in enumerate(out):
            tighter.append(
                _polish_slide_bullet_for_card(
                    b_it,
                    fallback_anchor=f"Key Point {idx_b + 1}",
                    max_anchor_chars=min(36, max_anchor_chars),
                    max_body_words=12,
                    max_body_chars=74,
                )
            )
        out = [x for x in tighter if x]
    return out


def _build_bullet_points_for_req(req: Dict[str, Any], req_num: str, req_text: str) -> List[str]:
    """Constructs <= 4 non-truncated, bold-anchored teaching points summarized from the BSA Merit Badge Pamphlet."""
    bullets: List[str] = []

    excerpts = req.get("pamphlet_excerpts") or []
    procedures = req.get("step_by_step_procedure") or []
    checklist = req.get("gear_checklist") or []

    for item in excerpts[:4]:
        cleaned_item = _sanitize_no_ellipsis_or_emdash(str(item))
        if cleaned_item and cleaned_item not in bullets:
            bullets.append(cleaned_item)

    for step in procedures[:3]:
        cleaned_step = _sanitize_no_ellipsis_or_emdash(str(step))
        if cleaned_step and cleaned_step not in bullets and len(bullets) < 4:
            bullets.append(cleaned_step)

    for gear in checklist[:2]:
        cleaned_gear = _sanitize_no_ellipsis_or_emdash(str(gear))
        if cleaned_gear and cleaned_gear not in bullets and len(bullets) < 4:
            bullets.append(cleaned_gear)

    if len(bullets) < 3:
        bullets.append(f"Core Requirement {req_num}: {req_text}")

    safety = req.get("safety_callout")
    if safety and len(bullets) < 4:
        bullets.append(f"Safety Rule: {_sanitize_no_ellipsis_or_emdash(str(safety))}")

    return bullets[:4]


def _infer_action_verb_badge(req_text: str, anchor: str, body: str, idx_s: int) -> tuple[str, str]:
    """Derives an action-verb card badge ('DISCUSS', 'STEP', 'HAZARD', 'FIRST AID', 'COMPARE', 'VERIFY') and accent color."""
    combined = f"{anchor} {body}".lower()
    req_low = (req_text or "").lower()
    if any(k in combined for k in ("hazard", "safety", "danger", "caution", "ppe", "prevent", "avoid")):
        return f"HAZARD {idx_s}", "#CE1126"
    if any(k in combined for k in ("first aid", "triage", "cpr", "bleed", "splint", "bandage", "treat", "shock")):
        return f"FIRST AID {idx_s}", "#CE1126"
    if any(k in (req_low + " " + combined) for k in ("compare", "contrast", "versus", "difference", "distinguish")):
        return f"COMPARE {idx_s}", "#005AE0"
    if any(k in combined for k in ("verify", "check", "inspect", "log", "record", "sign-off", "checklist")):
        return f"VERIFY {idx_s}", "#003F87"
    if any(k in (req_low + " " + combined) for k in ("demonstrate", "show", "build", "make", "perform", "practice", "step", "procedure")):
        return f"STEP {idx_s}", "#4B5320"
    return f"DISCUSS {idx_s}", "#003F87"


def _build_cards_for_req(req: Dict[str, Any], bullets: List[str]) -> List[Dict[str, Any]]:
    """Builds 4 structured card dictionaries with action-verb badges aligned with the primary slide bullets and pamphlet steps."""
    from src.tools.pptx_builder import _concise_anchor_title

    steps = [str(b) for b in (bullets or [])[:4] if str(b).strip()]
    for raw_item in list(req.get("step_by_step_procedure") or []) + list(req.get("pamphlet_excerpts") or []):
        clean_item = _sanitize_no_ellipsis_or_emdash(str(raw_item))
        if clean_item and clean_item not in steps and len(steps) < 4:
            steps.append(clean_item)

    req_txt = str(req.get("req_text") or "")
    cards: List[Dict[str, Any]] = []
    colors = ["#003F87", "#005AE0", "#4B5320", "#CE1126"]
    for idx_s, raw_step in enumerate(steps[:4], start=1):
        clean_s = _sanitize_no_ellipsis_or_emdash(str(raw_step))
        anchor, body = _split_anchor_and_detail(clean_s, fallback_anchor=f"Step {idx_s}")
        anchor_clean = re.sub(r"^Step\s+\d+\s*[-:]\s*", "", anchor.strip(), flags=re.IGNORECASE).strip() or anchor.strip()
        verb_badge, verb_color = _infer_action_verb_badge(req_txt, anchor_clean, body, idx_s)
        cards.append({
            "badge_label": verb_badge,
            "anchor_title": _concise_anchor_title(anchor_clean, max_chars=44) or f"Step {idx_s}",
            "body_text": body.strip() or clean_s,
            "accent_color_hex": verb_color or colors[(idx_s - 1) % len(colors)],
        })
    return cards


def generate_slide_storyboard(
    badge_name: str,
    requirements: List[Dict[str, Any]],
    depth_mode: str = "Standard Deck",
    is_eagle_required: bool = False,
) -> Dict[str, Any]:
    """Generates an ordered, multi-slide-per-requirement instructional storyboard.

    For each requirement, emits:
    1. A Requirement Introduction Slide (`REQUIREMENT_INTRO`) presenting the full verbatim requirement text
       and the roadmap of sub-topics.
    2. Multiple dedicated Topic Instruction & Full-Page Diagram Slides (`CONCEPT_TEXT_SLIDE`,
       `SPLIT_VISUAL_EXPLAINER`, `FULL_BLEED_IMAGE_EXPLAINER`, `DIFFERENTIAL_COMPARISON_2COL`,
       `STEP_BY_STEP_PROCEDURE_4CARD`, `WORKED_EXAMPLE_TEMPLATE`, `GEAR_CHECKLIST_GRID`,
       `SOCRATIC_CHECKPOINT_QUIZ`) explaining, defining, and illustrating every concept in detail.
    3. A single final `Sources & References` slide at the end of the presentation (no per-slide attribution clutter).

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge (e.g., `'Weather'`, `'First Aid'`).
        requirements: List of requirement dictionaries returned by `fetch_merit_badge_pamphlet_pdf`.
        depth_mode: Presentation depth tier (`'Standard Deck'` or `'Deep Dive / Camp School Deck'`).
        is_eagle_required: True if the badge is Eagle-required (activates Silver/Gold accents).

    Returns:
        Dict[str, Any]: Serialized `StoryboardPlan` dictionary containing `badge_name`,
        `is_eagle_required`, `depth_mode`, and `slides` (`List[SlideSpec]`), or a
        `GuidedToolError` dictionary if `badge_name` is invalid.
    """
    if not badge_name or not str(badge_name).strip():
        return build_guided_tool_error(
            error_code="EMPTY_STORYBOARD_BADGE_NAME",
            message="badge_name cannot be empty when generating a slide storyboard.",
            remediation="Provide a valid Scouts BSA Merit Badge name from Scouting.org.",
        )
    from src.tools.pamphlet_extractor import (
        _derive_topic_title,
        decompose_requirement_into_topic_slides,
    )

    clean_badge = _sanitize_no_ellipsis_or_emdash(badge_name.strip().title())
    slides: List[SlideSpec] = []

    # -------------------------------------------------------------------------
    # 1. SLIDE 1 OF STORYBOARD: REQUIREMENTS OVERVIEW MATRIX
    # -------------------------------------------------------------------------
    from src.tools.pptx_builder import _concise_card_body

    in_class_reqs: List[str] = []
    station_reqs: List[str] = []
    prereq_reqs: List[str] = []
    triage_cards: List[Dict[str, Any]] = []
    deck_seen_bullet_norms: set = set()

    for req in requirements:
        r_num = str(req.get("req_number", "1"))
        r_text = _sanitize_no_ellipsis_or_emdash(str(req.get("req_text", "Complete requirement.")))
        raw_topic = str(req.get("topic_title") or _derive_topic_title(r_num, r_text))
        clean_topic = _sanitize_no_ellipsis_or_emdash(raw_topic.replace(f"Req {r_num}:", "").strip())
        triage_topic = _concise_card_body(clean_topic, max_words=5, max_chars=32).rstrip(" .,:;-")
        if "(" in triage_topic and ")" not in triage_topic:
            triage_topic = triage_topic.split("(", 1)[0].strip()
        mode = _infer_execution_mode(req)
        short_summary = triage_topic if len(triage_topic) >= 6 else (
            _concise_card_body(r_text, max_words=5, max_chars=32).rstrip(" .,:;-")
        )
        if mode == ExecutionMode.HANDS_ON_SKILL_STATION.value:
            station_reqs.append(f"Req {r_num} - {short_summary}")
            triage_cards.append({
                "badge_label": _format_execution_mode_label(mode),
                "anchor_title": f"Req {r_num}",
                "body_text": short_summary,
                "accent_color_hex": "#4B5320",
            })
        elif mode == ExecutionMode.PREREQUISITE_CAMPOUT_HOME.value:
            prereq_reqs.append(f"Req {r_num} - {short_summary}")
            triage_cards.append({
                "badge_label": _format_execution_mode_label(mode),
                "anchor_title": f"Req {r_num}",
                "body_text": short_summary,
                "accent_color_hex": "#CE1126",
            })
        else:
            in_class_reqs.append(f"Req {r_num} - {short_summary}")
            triage_cards.append({
                "badge_label": _format_execution_mode_label(mode),
                "anchor_title": f"Req {r_num}",
                "body_text": short_summary,
                "accent_color_hex": "#003F87",
            })

    def _finish_triage_line(items: List[str], fallback_line: str) -> str:
        s = ("; ".join(items[:3]) if items else fallback_line).rstrip(" .,:;-")
        if "(" in s and s.count("(") != s.count(")"):
            s = s.replace("(", "").replace(")", "").strip()
        return f"{s}."

    triage_bullets = [
        _finish_triage_line(in_class_reqs, "Core principles, definitions, and safety concepts"),
        _finish_triage_line(station_reqs, "Practical hands-on demonstrations with your patrol"),
        _finish_triage_line(prereq_reqs, "Outdoor observation, field logs, or home preparation"),
        f"Curriculum Scope: {len(requirements)} official requirements organized into step-by-step instructional slides.",
    ]
    overview_title = f"{clean_badge} Merit Badge: Requirements Overview"
    slides.append(
        SlideSpec(
            title=overview_title,
            bullet_points=triage_bullets[:6],
            presenter_notes=_build_slide_teaching_notes(
                badge_name=clean_badge,
                req_num="Overview",
                execution_mode=ExecutionMode.IN_CLASS_DISCUSSION.value,
                slide_title=overview_title,
                archetype=SlideArchetype.REQUIREMENTS_TRIAGE_MATRIX.value,
                bullet_points=triage_bullets[:6],
                overview_summary={
                    "in_class": in_class_reqs,
                    "station": station_reqs,
                    "prereq": prereq_reqs,
                    "total_count": [str(len(requirements))],
                },
            ),
            safety_warning="Always follow the BSA Guide to Safe Scouting, Two-Deep Leadership, and the Buddy System.",
            diagram_path=None,
            archetype=SlideArchetype.REQUIREMENTS_TRIAGE_MATRIX.value,
            req_number="Overview",
            execution_mode=ExecutionMode.IN_CLASS_DISCUSSION.value,
            edge_phase="Explain & Plan",
            subtitle=f"{clean_badge} Merit Badge Curriculum Roadmap",
            verbatim_requirement_text=(
                f"Complete all {len(requirements)} official requirements and review each topic with your Merit Badge Counselor."
            ),
            cards=triage_cards[:15],
            visual_caption="",
            diagram_type="triage_matrix",
        )
    )

    # -------------------------------------------------------------------------
    # 2. MULTI-SLIDE EXPANSION PER REQUIREMENT:
    #    - First slide of each requirement sequence lists the official requirement
    #      AND teaches the core material on the same slide.
    #    - Subsequent slides in the sequence omit the requirement definition strip
    #      and bottom boilerplate bar so they remain clean teaching/visual slides.
    #    - Deep Dive mode: 5-12 slides per requirement (50-70+ slides total).
    #    - Standard mode: 1-3 focused slides per requirement (~18-26 slides total).
    # -------------------------------------------------------------------------
    is_deep_dive = any(
        kw in (depth_mode or "").lower()
        for kw in ("deep", "camp", "detailed", "comprehensive")
    )
    used_imgs: set = set()
    used_myths_in_deck: set = set()
    used_asks_in_deck: set = set()
    for idx, req in enumerate(requirements):
        req_num = str(req.get("req_number", str(idx + 1)))
        req_text = _sanitize_no_ellipsis_or_emdash(str(req.get("req_text", "Complete requirement.")))
        safety = _sanitize_no_ellipsis_or_emdash(req["safety_callout"]) if req.get("safety_callout") else None
        exec_mode = _infer_execution_mode(req)
        edge_phase = str(req.get("edge_phase") or (
            "Demonstrate & Guide" if exec_mode == ExecutionMode.HANDS_ON_SKILL_STATION.value else "Explain & Guide"
        ))
        raw_topic_title = _sanitize_no_ellipsis_or_emdash(
            str(req.get("topic_title") or _derive_topic_title(req_num, req_text))
        )
        clean_section_title = raw_topic_title.replace(f"Req {req_num}:", "").strip()
        req_misc_pair = req.get("common_misconception_pair") if isinstance(req.get("common_misconception_pair"), dict) else None
        req_pamphlet_ref = _sanitize_no_ellipsis_or_emdash(
            str(req.get("pamphlet_page_citation") or f"BSA {clean_badge} Pamphlet • Req {req_num}")
        )
        wb_org = req.get("workbook_organizer") if isinstance(req.get("workbook_organizer"), dict) else {}
        wb_type_label = _format_workbook_organizer_label(wb_org)
        req_wb_ref = f"Workbook Requirement {req_num} • {wb_type_label}"
        gate_obj = req.get("starting_requirement_gate") if isinstance(req.get("starting_requirement_gate"), dict) else {}
        req_gate_badges = [str(gate_obj["gate_label"])] if gate_obj.get("gate_label") else []
        req_curated_res = list(req.get("curated_resources") or [])

        raw_topic_slides = list(req.get("topic_slides") or [])
        min_topic_slides = 2
        has_quiz_in_raw = any(
            str(s.get("layout") or "").upper() == "SOCRATIC_CHECKPOINT_QUIZ" or s.get("quiz_item")
            for s in raw_topic_slides
        )
        if (
            not raw_topic_slides
            or (is_deep_dive and len(raw_topic_slides) < min_topic_slides)
            or (idx == 0 and not has_quiz_in_raw)
        ):
            extra_slides = decompose_requirement_into_topic_slides(
                badge_name=clean_badge,
                req_dict=req,
                req_index=idx,
                total_reqs=max(1, len(requirements)),
                used_image_paths=used_imgs,
            )
            existing_titles = {str(s.get("title", "")).strip().lower() for s in raw_topic_slides}
            for es in extra_slides:
                if str(es.get("title", "")).strip().lower() not in existing_titles:
                    raw_topic_slides.append(es)
                    existing_titles.add(str(es.get("title", "")).strip().lower())

        if is_deep_dive:
            # Deep Dive mode: First slide lists & teaches core concepts for Req N,
            # followed by all detailed topic & full-page diagram slides
            raw_core_points = _build_bullet_points_for_req(req, req_num, req_text)
            intro_title = (
                f"{clean_section_title} (Req {req_num})"
                if ": " in clean_section_title
                else f"Requirement {req_num}: {clean_section_title}"
            )
            core_teaching_points = _polish_slide_bullets_list(
                raw_core_points,
                max_count=4,
                max_total_chars=435,
                max_anchor_chars=34,
                max_body_words=15,
                max_body_chars=96,
                deck_seen_norms=deck_seen_bullet_norms,
                badge_name=clean_badge,
                req_num=req_num,
                slide_title=intro_title,
            )
            slides.append(
                SlideSpec(
                    title=intro_title,
                    bullet_points=core_teaching_points[:4],
                    presenter_notes=_build_slide_teaching_notes(
                        badge_name=clean_badge,
                        req_num=req_num,
                        execution_mode=exec_mode,
                        slide_title=intro_title,
                        archetype="REQUIREMENT_INTRO",
                        req_text=req_text,
                        bullet_points=core_teaching_points[:4],
                        req_dict=req,
                        safety_callout=safety,
                        slide_dict={
                            "_used_myths_in_deck": used_myths_in_deck,
                            "_used_asks_in_deck": used_asks_in_deck,
                        },
                        slide_idx_in_req=0,
                    ),
                    safety_warning=safety,
                    diagram_path=None,
                    archetype="REQUIREMENT_INTRO",
                    req_number=req_num,
                    execution_mode=exec_mode,
                    edge_phase=edge_phase,
                    subtitle=clean_section_title,
                    verbatim_requirement_text=req_text,
                    cards=_build_cards_for_req(req, core_teaching_points[:4]),
                    visual_caption="",
                    diagram_type="requirement_intro",
                    slide_role="instructional",
                    misconception_pair=req_misc_pair if not safety else None,
                    pamphlet_reference=req_pamphlet_ref,
                    workbook_table_ref=req_wb_ref,
                    gate_badges=req_gate_badges,
                    curated_resources=req_curated_res,
                )
            )
            selected_topic_slides = raw_topic_slides
            first_topic_shows_req = False
        else:
            # Standard Troop Meeting mode: 1-4 focused slides per requirement covering 100% of sub-requirements.
            n_reqs = max(1, len(requirements))
            sub_slides = [
                s for s in raw_topic_slides
                if s.get("is_subreq_slide") or "sub-requirement deep dive" in str(s.get("title", "")).lower()
            ]
            other_slides = [
                s for s in raw_topic_slides
                if not s.get("is_subreq_slide") and "sub-requirement deep dive" not in str(s.get("title", "")).lower()
            ]
            if len(sub_slides) > 3:
                # For dense requirements with >12 sub-requirements (e.g., Cycling 6a/6b, Camping 9b, Archery 2d),
                # keep dedicated 4-card sub-requirement slides instead of pipe-concatenating two sub-reqs into one card.
                selected_topic_slides = sub_slides + other_slides[:1]
            elif sub_slides:
                extra_budget = 2 if (len(sub_slides) == 1 and n_reqs <= 6) else 1
                selected_topic_slides = sub_slides + other_slides[:extra_budget]
                selected_topic_slides = selected_topic_slides[:4]
            else:
                per_req_cap = 3 if n_reqs <= 6 else 2
                selected_topic_slides = raw_topic_slides[:per_req_cap]
                selected_topic_slides = selected_topic_slides[:4]
            if idx == 0 and not any(
                str(s.get("layout") or "").upper() == "SOCRATIC_CHECKPOINT_QUIZ" or s.get("quiz_item")
                for s in selected_topic_slides
            ):
                quiz_candidates = [
                    s for s in raw_topic_slides
                    if str(s.get("layout") or "").upper() == "SOCRATIC_CHECKPOINT_QUIZ" or s.get("quiz_item")
                ]
                if quiz_candidates:
                    selected_topic_slides.append(quiz_candidates[0])
            first_topic_shows_req = True

        from src.tools.pamphlet_extractor import (
            _ensure_complete_caption_sentence,
            _ensure_four_quiz_options,
            _is_emergency_or_hazard_context,
        )
        from src.tools.pptx_builder import _concise_anchor_title

        # Topic Instruction & Full-Page Diagram Slides for Requirement N
        for t_idx, ts in enumerate(selected_topic_slides, start=1):
            ts_title = _sanitize_no_ellipsis_or_emdash(str(ts.get("title") or f"{clean_section_title} (Part {t_idx})"))
            ts_layout = str(ts.get("layout") or "CONCEPT_TEXT_SLIDE")
            raw_ts_bullets = ts.get("bullets") or _build_bullet_points_for_req(req, req_num, req_text)

            ts_comp = ts.get("comparison_data") or (
                req.get("comparison_data") if ts_layout == SlideArchetype.DIFFERENTIAL_COMPARISON_2COL.value else None
            )
            if hasattr(ts_comp, "model_dump"):
                ts_comp = ts_comp.model_dump()
            if isinstance(ts_comp, dict):
                ts_comp = dict(ts_comp)
                ts_comp["left_points"] = [
                    _polish_slide_bullet_for_card(str(lp), fallback_anchor=f"Left Point {i_lp + 1}", max_anchor_chars=42, max_body_words=15, max_body_chars=96)
                    for i_lp, lp in enumerate(list(ts_comp.get("left_points") or [])[:4])
                    if str(lp).strip()
                ]
                ts_comp["right_points"] = [
                    _polish_slide_bullet_for_card(str(rp), fallback_anchor=f"Right Point {i_rp + 1}", max_anchor_chars=42, max_body_words=15, max_body_chars=96)
                    for i_rp, rp in enumerate(list(ts_comp.get("right_points") or [])[:4])
                    if str(rp).strip()
                ]

            ts_we = ts.get("worked_example") or (
                req.get("worked_example") if ts_layout == SlideArchetype.WORKED_EXAMPLE_TEMPLATE.value else None
            )
            if hasattr(ts_we, "model_dump"):
                ts_we = ts_we.model_dump()
            if isinstance(ts_we, dict) and isinstance(ts_we.get("fields"), dict):
                ts_we = dict(ts_we)
                polished_fields: Dict[str, str] = {}
                for k_f, v_f in list(ts_we["fields"].items())[:4]:
                    pol_kv = _polish_slide_bullet_for_card(
                        f"{k_f}: {v_f}", fallback_anchor=str(k_f), max_anchor_chars=42, max_body_words=15, max_body_chars=96
                    )
                    if ": " in pol_kv:
                        pk, pv = pol_kv.split(": ", 1)
                        polished_fields[pk] = pv
                    else:
                        polished_fields[_concise_anchor_title(str(k_f), max_chars=42)] = pol_kv
                ts_we["fields"] = polished_fields

            ts_quiz = ts.get("quiz_item") or (
                req.get("quiz_item") if ts_layout == SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value else None
            )
            if hasattr(ts_quiz, "model_dump"):
                ts_quiz = ts_quiz.model_dump()
            if isinstance(ts_quiz, dict):
                ts_quiz = _ensure_four_quiz_options(ts_quiz, badge_name=clean_badge, base_title=clean_section_title)

            ts_gear = [
                _polish_slide_bullet_for_card(str(g), fallback_anchor=f"Item {i_g + 1}", max_anchor_chars=42, max_body_words=15, max_body_chars=96)
                for i_g, g in enumerate(
                    (ts.get("gear_checklist") or (
                        req.get("gear_checklist") if ts_layout == SlideArchetype.GEAR_CHECKLIST_GRID.value else []
                    ) or [])[:4]
                )
                if str(g).strip()
            ]

            if ts_layout == SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value and isinstance(ts_quiz, dict):
                rationale_label = (
                    "Safety Rationale"
                    if _is_emergency_or_hazard_context(clean_badge, req_text, ts_title)
                    else "Pamphlet Rationale"
                )
                ts_bullets = [
                    f"Scenario Prompt: {_sanitize_no_ellipsis_or_emdash(str(ts_quiz.get('scenario_prompt') or ''))}",
                    f"Correct Action: {_sanitize_no_ellipsis_or_emdash(str(ts_quiz.get('correct_answer') or ''))}",
                    f"{rationale_label}: {_sanitize_no_ellipsis_or_emdash(str(ts_quiz.get('explanation') or ''))}",
                ]
            else:
                ts_bullets = _polish_slide_bullets_list(
                    [str(b) for b in raw_ts_bullets if str(b).strip()],
                    max_count=4,
                    max_total_chars=435,
                    max_anchor_chars=42 if ts_layout == SlideArchetype.DIFFERENTIAL_COMPARISON_2COL.value else 44,
                    max_body_words=15,
                    max_body_chars=96,
                    deck_seen_norms=deck_seen_bullet_norms,
                    badge_name=clean_badge,
                    req_num=req_num,
                    slide_title=ts_title,
                )

            ts_cards = _build_cards_for_req({"req_text": req_text, "step_by_step_procedure": ts_bullets}, ts_bullets)
            ts_img = ts.get("image_path")
            if ts_img:
                raw_ts_cap = _sanitize_no_ellipsis_or_emdash(str(ts.get("caption") or ""))
                if not raw_ts_cap or raw_ts_cap.strip().lower().rstrip(".") == ts_title.strip().lower().rstrip("."):
                    raw_ts_cap = f"{clean_badge} Requirement {req_num} visual guide illustrating {clean_section_title}"
                ts_caption = _ensure_complete_caption_sentence(raw_ts_cap, max_chars=160)
            else:
                ts_caption = ""

            # Only show the requirement text on the first slide of the sequence (if not already shown)
            show_req_on_this_slide = first_topic_shows_req and (t_idx == 1)
            if show_req_on_this_slide and ts_layout == "FULL_BLEED_IMAGE_EXPLAINER":
                ts_layout = "SPLIT_VISUAL_EXPLAINER"

            slide_safety = safety if show_req_on_this_slide else None
            # Attach misconception_pair on the first non-safety slide of the requirement sequence
            show_misc_on_this_slide = (t_idx == 1 and not slide_safety) or (t_idx == 2 and bool(safety))
            child_slide_idx_in_req = t_idx if is_deep_dive else max(0, t_idx - 1)

            ts_for_notes = dict(ts)
            ts_for_notes["_used_myths_in_deck"] = used_myths_in_deck
            ts_for_notes["_used_asks_in_deck"] = used_asks_in_deck
            slides.append(
                SlideSpec(
                    title=ts_title,
                    bullet_points=ts_bullets,
                    presenter_notes=_build_slide_teaching_notes(
                        badge_name=clean_badge,
                        req_num=req_num,
                        execution_mode=exec_mode,
                        slide_title=ts_title,
                        archetype=ts_layout,
                        req_text=req_text,
                        bullet_points=ts_bullets,
                        req_dict=req,
                        comparison_data=ts_comp,
                        worked_example=ts_we,
                        quiz_item=ts_quiz,
                        gear_checklist=ts_gear,
                        visual_caption=ts_caption,
                        has_visual=bool(ts_img),
                        safety_callout=slide_safety,
                        slide_dict=ts_for_notes,
                        slide_idx_in_req=child_slide_idx_in_req,
                    ),
                    safety_warning=slide_safety,
                    diagram_path=str(ts_img) if ts_img else None,
                    archetype=ts_layout,
                    req_number=req_num,
                    execution_mode=exec_mode,
                    edge_phase=edge_phase,
                    subtitle=clean_section_title,
                    verbatim_requirement_text=req_text if show_req_on_this_slide else "",
                    cards=ts_cards,
                    comparison_data=ts_comp,
                    worked_example=ts_we,
                    quiz_item=ts_quiz,
                    gear_checklist=ts_gear,
                    visual_caption=ts_caption,
                    diagram_type="full_bleed_diagram" if ts_layout == "FULL_BLEED_IMAGE_EXPLAINER" else "topic_slide",
                    slide_role="instructional",
                    misconception_pair=req_misc_pair if show_misc_on_this_slide else None,
                    pamphlet_reference=req_pamphlet_ref,
                    workbook_table_ref=req_wb_ref,
                    gate_badges=req_gate_badges if t_idx == 1 else [],
                    curated_resources=req_curated_res,
                )
            )

    # -------------------------------------------------------------------------
    # 3. FINAL SLIDE OF STORYBOARD: SOURCES & REFERENCES + WORKBENCH ATTRIBUTION
    # -------------------------------------------------------------------------
    encoded_badge = clean_badge.replace(" ", "%20")
    slug_hyphen = clean_badge.lower().replace(" ", "-")
    source_bullets = [
        f"Primary Source of Truth: {clean_badge}, Scouting America (Boy Scouts of America) Merit Badge Series Pamphlet (https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/{encoded_badge}.pdf).",
        f"Official Merit Badge Hub & Digital Resource Guide: Scouting America {clean_badge} Requirements & Multimedia Resources (https://www.scouting.org/merit-badges/{slug_hyphen}/).",
        "Safety & Youth Protection Standards: Scouting America Guide to Safe Scouting (https://www.scouting.org/health-and-safety/gss/).",
        "Scientific Diagrams & Photographs: Wikimedia Commons Educational Media Repository (https://commons.wikimedia.org) and Public-Domain Federal Agency Archives.",
        "Slide Deck Attribution: This slide deck was created by the Scouts BSA Merit Badge Counselor Workbench tool (https://github.com/clayberg/scouts-bsa-merit-badge-agent), created by Eric Clayberg (Troop 19, Middleton MA).",
    ]

    sources_title = f"{clean_badge} Merit Badge: Sources & References"
    slides.append(
        SlideSpec(
            title=sources_title,
            bullet_points=source_bullets[:6],
            presenter_notes=_build_slide_teaching_notes(
                badge_name=clean_badge,
                req_num="Sources",
                execution_mode=ExecutionMode.IN_CLASS_DISCUSSION.value,
                slide_title=sources_title,
                archetype="SOURCES_AND_REFERENCES",
                bullet_points=source_bullets[:6],
            ),
            safety_warning=None,
            diagram_path=None,
            archetype="SOURCES_AND_REFERENCES",
            req_number="Sources",
            execution_mode=ExecutionMode.IN_CLASS_DISCUSSION.value,
            edge_phase="Explain & Enable",
            subtitle="Official Pamphlet, Scientific Diagrams & Instructional Credits",
            verbatim_requirement_text=(
                f"Primary requirement text and instructional summaries are grounded in the official Scouting America {clean_badge} Merit Badge Pamphlet."
            ),
            cards=[],
            visual_caption="",
            diagram_type="sources_and_references",
        )
    )

    plan = StoryboardPlan(
        badge_name=badge_name,
        is_eagle_required=is_eagle_required,
        depth_mode=depth_mode,
        slides=slides,
    )
    return plan.model_dump()


def get_slide_content_planner_agent(model_name: Optional[str] = None) -> adk.Agent:
    """Instantiates the SlideContentPlannerAgent for storyboarding presentations.

    Args:
        model_name: Gemini model identifier to use (defaults to
            `select_model_for_task('planner')` / `'gemini-2.5-pro'`).

    Returns:
        adk.Agent: Configured planner subagent with `output_key='slide_deck_spec'`.
    """
    resolved_model = model_name or select_model_for_task("planner")
    external_prompt = load_prompt("planner.md", fallback="")
    system_instruction = (
        f"{SCOUTS_BSA_CONSTITUTION}\n\n"
        f"{external_prompt}\n\n"
        "Your role is the SlideContentPlannerAgent. Given structured requirements:\n"
        "1. Call generate_slide_storyboard to build an ordered 12-Archetype slide-by-slide plan.\n"
        "2. Always begin the storyboard with a REQUIREMENTS_TRIAGE_MATRIX slide classifying sub-requirements.\n"
        "3. Strictly enforce the 7 Golden Rules of Slide Copywriting: max 7 points per slide, zero ellipses ('...'), "
        "zero literal bullet characters ('•'), and 2-4 word bold anchors.\n"
        "4. Format presenter_notes with [SAY], [DEMONSTRATE], and [ASK SCOUTS] cues (<=16 words/clause, zero em-dashes).\n"
        "5. Return the structured StoryboardPlan dictionary."
    )

    agent = adk.Agent(
        name="SlideContentPlannerAgent",
        model=resolved_model,
        instruction=system_instruction,
        output_key="slide_deck_spec",
        tools=[generate_slide_storyboard],
        before_model_callback=before_model_guardrail_callback,
        after_model_callback=after_model_guardrail_callback,
    )
    return agent
