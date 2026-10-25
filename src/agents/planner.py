"""ADK SlideContentPlannerAgent for creating 12-Archetype pedagogical slide storyboards.

This agent converts Merit Badge requirements and sub-requirements into an ordered,
multi-archetype slide storyboard with:
- Slide 1 (`REQUIREMENTS_TRIAGE_MATRIX`) classifying sub-requirements into In-Class Discussion,
  Hands-On Skill Station, and Prerequisite / Campout / Home.
- Rich archetype selection across all 12 `SlideArchetype` layouts.
- Zero truncation (`...`) and zero literal bullet characters (`•`).
- Keynote/Demo voice presenter notes (`[SAY]`, `[DEMONSTRATE]`, `[ASK SCOUTS]`, <=16 words/clause, zero em-dashes).
"""

from typing import Any, Dict, List, Optional
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
    """Removes ellipses ('...'), em-dashes ('—', '--'), en-dashes ('–'), and PDF kerning glitches."""
    if not text:
        return ""
    from src.tools.pamphlet_extractor import _repair_pdf_word_concatenations

    cleaned = _repair_pdf_word_concatenations(str(text))
    cleaned = cleaned.replace("...", ".").replace("…", ".")
    cleaned = cleaned.replace(" — ", ", ").replace(" – ", ", ").replace(" -- ", ", ")
    cleaned = cleaned.replace("—", ", ").replace("–", "-").replace("--", ", ")
    cleaned = cleaned.replace(" , ", ", ")
    while ".." in cleaned:
        cleaned = cleaned.replace("..", ".")
    return cleaned.strip()


def _infer_execution_mode(req: Dict[str, Any]) -> str:
    """Determines the pedagogical execution mode for a requirement dictionary."""
    explicit = req.get("execution_mode")
    if explicit:
        val = explicit.value if hasattr(explicit, "value") else str(explicit)
        if val in {
            ExecutionMode.IN_CLASS_DISCUSSION.value,
            ExecutionMode.HANDS_ON_SKILL_STATION.value,
            ExecutionMode.PREREQUISITE_CAMPOUT_HOME.value,
        }:
            return val

    text_lower = str(req.get("req_text", "")).lower()
    if any(
        kw in text_lower
        for kw in (
            "camp a total",
            "20 nights",
            "attend a",
            "visit a",
            "12-week",
            "7-day",
            "five consecutive days",
            "physical examination",
            "weekend campout",
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
    if req.get("worked_example"):
        return SlideArchetype.WORKED_EXAMPLE_TEMPLATE.value
    if req.get("gear_checklist"):
        return SlideArchetype.GEAR_CHECKLIST_GRID.value
    if req.get("quiz_item"):
        return SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value
    if req.get("step_by_step_procedure"):
        return SlideArchetype.STEP_BY_STEP_PROCEDURE_4CARD.value

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
    )


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
    4. `[COMMON MISCONCEPTION TO CORRECT]`: The #1 misconception Scouts hold on this requirement
       paired with the official BSA Pamphlet correction (`Myth vs. BSA Pamphlet Fact`).
    5. `[DEMONSTRATION & SIGN-OFF RUBRIC]`: Hands-on EDGE demonstration coaching and the concrete
       verification standard for Blue Card (#34124) and Fillable Workbook sign-off.
    """
    clean_badge = _sanitize_no_ellipsis_or_emdash(badge_name)
    clean_req = _sanitize_no_ellipsis_or_emdash(req_num)
    clean_title = _sanitize_no_ellipsis_or_emdash(slide_title or f"{clean_badge} Requirement {clean_req}")
    clean_req_text = _sanitize_no_ellipsis_or_emdash(req_text)
    clean_caption = _sanitize_no_ellipsis_or_emdash(visual_caption)
    arch = (archetype or "CONCEPT_TEXT_SLIDE").upper()
    pts = [_sanitize_no_ellipsis_or_emdash(str(p)) for p in (bullet_points or []) if str(p).strip()]
    req_data = req_dict or {}

    parsed_points = [
        _split_anchor_and_detail(p, f"Concept {idx + 1}")
        for idx, p in enumerate(pts)
    ]
    anchors = [a for a, _ in parsed_points if a]

    extra_insights: List[str] = []
    for raw_ex in list(req_data.get("pamphlet_excerpts") or []) + list(req_data.get("step_by_step_procedure") or []):
        clean_ex = _sanitize_no_ellipsis_or_emdash(str(raw_ex))
        if clean_ex and clean_ex not in pts:
            extra_insights.append(clean_ex)

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
        f" {_sanitize_no_ellipsis_or_emdash(local_grounding_callout)}"
        if local_grounding_callout
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
        str(req_data.get("pamphlet_page_citation") or f"BSA {clean_badge} Pamphlet, Req {clean_req}")
    )
    wb_org = req_data.get("workbook_organizer") if isinstance(req_data.get("workbook_organizer"), dict) else {}
    wb_type = _sanitize_no_ellipsis_or_emdash(str(wb_org.get("organizer_type") or "CONCEPT_MATRIX"))
    misc_pair = req_data.get("common_misconception_pair") if isinstance(req_data.get("common_misconception_pair"), dict) else {}
    myth_txt = _sanitize_no_ellipsis_or_emdash(
        str(misc_pair.get("misconception") or f"Rushing through {clean_title} without verifying each step in the {clean_badge} pamphlet.")
    )
    fact_txt = _sanitize_no_ellipsis_or_emdash(
        str(misc_pair.get("fact_correction") or f"Follow the official {clean_badge} Merit Badge Pamphlet criteria for Requirement {clean_req} and verify with a buddy.")
    )

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
            f"[COMMON MISCONCEPTION TO CORRECT] Myth: A partial Blue Card expires at the end of summer camp or the Merit Badge College. "
            f"BSA Pamphlet Fact: Under Scouting America rules, signed partial requirements on a Blue Card (#34124) never expire until the Scout turns 18."
        )
        rubric_line = (
            f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Hold up Blue Card #34124 Applicant's Record and Counselor's Record] "
            f"Initial each completed requirement in the Multi-Troop Blue Card Triage Matrix and issue a Smart Partial plan for any remaining home-troop follow-up items."
        )
        return "\n".join(_sanitize_no_ellipsis_or_emdash(ln) for ln in (pacing_line, ask_line, key_line, misc_line, rubric_line))

    # Build conversational first-person card walkthroughs with inline [Point to Card N] stage cues
    card_monologue_parts: List[str] = []
    for idx_p, (anc, bdy) in enumerate(parsed_points):
        bdy_clean = bdy[:-1] if bdy.endswith(".") else bdy
        card_num = idx_p + 1
        if idx_p == 0:
            card_monologue_parts.append(
                f"[Point to Card {card_num}: {anc}] Let's start with {anc}: {bdy_clean}."
            )
        elif idx_p == 1:
            card_monologue_parts.append(
                f"[Point to Card {card_num}: {anc}] Building on that, look at {anc}: {bdy_clean}."
            )
        elif idx_p == 2:
            card_monologue_parts.append(
                f"[Point to Card {card_num}: {anc}] Pay special attention to {anc}: {bdy_clean}."
            )
        elif idx_p == 3:
            card_monologue_parts.append(
                f"[Point to Card {card_num}: {anc}] And fourth, notice {anc}: {bdy_clean}."
            )
        else:
            card_monologue_parts.append(
                f"Also keep in mind {anc}: {bdy_clean}."
            )

    conversational_cards = " ".join(card_monologue_parts)
    visual_tie_in = (
        f" [Gesture to the right-hand figure: {clean_caption}] Notice the visual figure ({clean_caption}), which illustrates how {', '.join(anchors[:2]) or clean_title} works in the field."
        if has_visual and clean_caption
        else ""
    )
    safety_note = (
        f" [Safety Check] Under the BSA Guide to Safe Scouting, always enforce: {_sanitize_no_ellipsis_or_emdash(safety_callout)}"
        if safety_callout
        else ""
    )

    first_anchor = anchors[0] if anchors else clean_title
    first_body = parsed_points[0][1] if parsed_points else clean_req_text or clean_title
    second_anchor = anchors[1] if len(anchors) > 1 else first_anchor
    second_body = parsed_points[1][1] if len(parsed_points) > 1 else first_body

    est_minutes = "4 min" if execution_mode == ExecutionMode.HANDS_ON_SKILL_STATION.value else "3 min"

    # 1. [PACING & MODALITY]
    pacing_block = (
        f"[PACING & MODALITY] {est_minutes} | {syllabus_bucket} | EDGE: {edge_stage} | {page_cite}. "
        f"Let's unpack {clean_title} for {clean_badge} Requirement {clean_req}. "
        f"{conversational_cards}"
        f"{visual_tie_in}{safety_note}{local_cue}{audience_cue} [Pause for questions]"
    )

    # 2. [ASK SCOUTS FIRST]
    if arch == SlideArchetype.DIFFERENTIAL_COMPARISON_2COL.value or comparison_data:
        cd = comparison_data or {}
        left_h = _sanitize_no_ellipsis_or_emdash(str(cd.get("left_header") or first_anchor))
        right_h = _sanitize_no_ellipsis_or_emdash(str(cd.get("right_header") or second_anchor))
        ask_block = (
            f"[ASK SCOUTS FIRST] Before we read the comparison columns on screen, if your patrol encountered this situation outdoors without reference notes, what is the #1 field clue that separates {left_h} from {right_h}?"
        )
    elif arch == SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value or quiz_item:
        qi = quiz_item or {}
        scenario = _sanitize_no_ellipsis_or_emdash(
            str(qi.get("scenario_prompt") or (pts[0] if pts else f"How should your patrol apply {clean_title}?"))
        )
        ask_block = (
            f"[ASK SCOUTS FIRST] Picture your patrol in this exact scenario before looking at the answer key: \"{scenario}\" Which option does your buddy pair choose first, and what risk are you preventing?"
        )
    elif arch == SlideArchetype.STEP_BY_STEP_PROCEDURE_4CARD.value:
        ask_block = (
            f"[ASK SCOUTS FIRST] Why must we complete {first_anchor} before moving on to {second_anchor} during \"{clean_title},\" and what goes wrong in the field if a Scout skips Step 1?"
        )
    elif arch == SlideArchetype.GEAR_CHECKLIST_GRID.value or gear_checklist:
        ask_block = (
            f"[ASK SCOUTS FIRST] During a 60-second trailhead pack shakedown for \"{clean_title},\" which item on this checklist is most often overlooked or damaged, and how would your patrol adapt?"
        )
    else:
        q_focus = f"{first_anchor} and {second_anchor}" if len(anchors) >= 2 else first_anchor
        ask_block = (
            f"[ASK SCOUTS FIRST] Where have you seen {q_focus} matter on a real troop campout, hike, or project, and how does it directly satisfy {clean_badge} Requirement {clean_req}?"
        )

    # 3. [EXPECTED PAMPHLET ANSWER KEY]
    supplementary_detail = (
        " ".join(extra_insights[:2])
        if extra_insights
        else (
            f"Official BSA Requirement {clean_req} standard: {clean_req_text}"
            if clean_req_text
            else f"Connect {first_anchor} ({first_body}) and {second_anchor} ({second_body}) to the {clean_badge} Merit Badge Pamphlet."
        )
    )
    if arch == SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value or quiz_item:
        qi = quiz_item or {}
        answer = _sanitize_no_ellipsis_or_emdash(str(qi.get("correct_answer") or first_anchor))
        explanation = _sanitize_no_ellipsis_or_emdash(str(qi.get("explanation") or first_body))
        key_block = (
            f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {page_cite}. Supplementary Pamphlet Detail: {supplementary_detail} "
            f"[Expected Answer: {answer}. {explanation}]"
        )
    else:
        key_block = (
            f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {page_cite}. Supplementary Pamphlet Detail: {supplementary_detail} "
            f"[Expected Answer: Scouts should cite {first_anchor} ({first_body}) paired with {second_anchor} ({second_body}) to fulfill {clean_badge} Requirement {clean_req}.]"
        )

    # 4. [COMMON MISCONCEPTION TO CORRECT]
    misc_block = (
        f"[COMMON MISCONCEPTION TO CORRECT] Myth: {myth_txt} | BSA Pamphlet Fact: {fact_txt}"
    )

    # 5. [DEMONSTRATION & SIGN-OFF RUBRIC]
    if has_visual and clean_caption:
        demo_action = (
            f"[Point to the right-hand visual: {clean_caption}] Trace {', '.join(anchors[:3]) or clean_title} on the \"{clean_caption}\" figure using the BSA EDGE method."
        )
    elif execution_mode == ExecutionMode.HANDS_ON_SKILL_STATION.value or arch == SlideArchetype.STEP_BY_STEP_PROCEDURE_4CARD.value:
        demo_action = (
            f"[Model the hands-on skill using the BSA EDGE method] Demonstrate {first_anchor} followed by {second_anchor} at half-speed, then guide buddy pairs as they practice."
        )
    else:
        demo_action = (
            f"[Hold up the printable {clean_badge} Fillable Scout Workbook] Show Scouts where to record their notes for Requirement {clean_req} ({wb_type})."
        )
    rubric_block = (
        f"[DEMONSTRATION & SIGN-OFF RUBRIC] {demo_action} "
        f"Sign-Off Standard (Workbook Table Req {clean_req} - {wb_type}): Scout must accurately explain or demonstrate {first_anchor} and {second_anchor} in their own words per {page_cite}."
    )

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
    )


def _build_bullet_points_for_req(req: Dict[str, Any], req_num: str, req_text: str) -> List[str]:
    """Constructs <= 6 non-truncated, bold-anchored teaching points summarized from the BSA Merit Badge Pamphlet."""
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
        if cleaned_step and cleaned_step not in bullets and len(bullets) < 6:
            bullets.append(cleaned_step)

    for gear in checklist[:2]:
        cleaned_gear = _sanitize_no_ellipsis_or_emdash(str(gear))
        if cleaned_gear and cleaned_gear not in bullets and len(bullets) < 6:
            bullets.append(cleaned_gear)

    if len(bullets) < 3:
        bullets.append(f"Core Requirement {req_num}: {req_text}")

    safety = req.get("safety_callout")
    if safety and len(bullets) < 6:
        bullets.append(f"Safety Rule: {_sanitize_no_ellipsis_or_emdash(str(safety))}")

    return bullets[:6]


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
        verb_badge, verb_color = _infer_action_verb_badge(req_txt, anchor, body, idx_s)
        cards.append({
            "badge_label": verb_badge,
            "anchor_title": anchor.strip()[:36] or f"Step {idx_s}",
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
    in_class_reqs: List[str] = []
    station_reqs: List[str] = []
    prereq_reqs: List[str] = []
    triage_cards: List[Dict[str, Any]] = []

    for req in requirements:
        r_num = str(req.get("req_number", "1"))
        r_text = _sanitize_no_ellipsis_or_emdash(str(req.get("req_text", "Complete requirement.")))
        raw_topic = str(req.get("topic_title") or _derive_topic_title(r_num, r_text))
        clean_topic = _sanitize_no_ellipsis_or_emdash(raw_topic.replace(f"Req {r_num}:", "").strip())
        mode = _infer_execution_mode(req)
        short_summary = clean_topic if len(clean_topic) >= 8 else (
            r_text if len(r_text) <= 70 else " ".join(r_text.split()[:10]) + "."
        )
        if mode == ExecutionMode.HANDS_ON_SKILL_STATION.value:
            station_reqs.append(f"Req {r_num} - {clean_topic}")
            triage_cards.append({
                "badge_label": "HANDS_ON_SKILL_STATION",
                "anchor_title": f"Req {r_num}",
                "body_text": short_summary,
                "accent_color_hex": "#4B5320",
            })
        elif mode == ExecutionMode.PREREQUISITE_CAMPOUT_HOME.value:
            prereq_reqs.append(f"Req {r_num} - {clean_topic}")
            triage_cards.append({
                "badge_label": "PREREQUISITE_CAMPOUT_HOME",
                "anchor_title": f"Req {r_num}",
                "body_text": short_summary,
                "accent_color_hex": "#CE1126",
            })
        else:
            in_class_reqs.append(f"Req {r_num} - {clean_topic}")
            triage_cards.append({
                "badge_label": "IN_CLASS_DISCUSSION",
                "anchor_title": f"Req {r_num}",
                "body_text": short_summary,
                "accent_color_hex": "#003F87",
            })

    triage_bullets = [
        "; ".join(in_class_reqs[:4]) if in_class_reqs else "Core principles, definitions, and safety concepts",
        "; ".join(station_reqs[:4]) if station_reqs else "Practical hands-on demonstrations with your patrol",
        "; ".join(prereq_reqs[:4]) if prereq_reqs else "Outdoor observation, field logs, or home preparation",
        f"Curriculum Scope: {len(requirements)} official requirements broken down into step-by-step instructional slides.",
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
            visual_caption=f"{clean_badge} Merit Badge Overview",
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
        wb_type_label = str(wb_org.get("organizer_type") or "CONCEPT_MATRIX")
        req_wb_ref = f"Workbook Table Req {req_num} ({wb_type_label})"
        gate_obj = req.get("starting_requirement_gate") if isinstance(req.get("starting_requirement_gate"), dict) else {}
        req_gate_badges = [str(gate_obj["gate_label"])] if gate_obj.get("gate_label") else []
        req_curated_res = list(req.get("curated_resources") or [])

        raw_topic_slides = list(req.get("topic_slides") or [])
        min_topic_slides = 2
        if not raw_topic_slides or (is_deep_dive and len(raw_topic_slides) < min_topic_slides):
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
            core_teaching_points = _build_bullet_points_for_req(req, req_num, req_text)
            intro_title = (
                f"{clean_section_title} (Req {req_num})"
                if ":" in clean_section_title
                else f"Requirement {req_num}: {clean_section_title}"
            )
            slides.append(
                SlideSpec(
                    title=intro_title,
                    bullet_points=core_teaching_points[:6],
                    presenter_notes=_build_slide_teaching_notes(
                        badge_name=clean_badge,
                        req_num=req_num,
                        execution_mode=exec_mode,
                        slide_title=intro_title,
                        archetype="REQUIREMENT_INTRO",
                        req_text=req_text,
                        bullet_points=core_teaching_points[:6],
                        req_dict=req,
                        safety_callout=safety,
                    ),
                    safety_warning=safety,
                    diagram_path=None,
                    archetype="REQUIREMENT_INTRO",
                    req_number=req_num,
                    execution_mode=exec_mode,
                    edge_phase=edge_phase,
                    subtitle=clean_section_title,
                    verbatim_requirement_text=req_text,
                    cards=_build_cards_for_req(req, core_teaching_points),
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
                all_sub_bullets: List[str] = []
                for ss in sub_slides:
                    all_sub_bullets.extend(str(b) for b in (ss.get("bullets") or []))
                # Pack >12 sub-requirements into 12 cards (3 slides x 4 cards) so 100% of sub-reqs fit in 3 slides + 1 execution slide = 4 slides
                packed_cards: List[str] = []
                idx_b = 0
                rem_items = len(all_sub_bullets)
                rem_slots = 12
                while idx_b < len(all_sub_bullets):
                    if rem_items > rem_slots and idx_b + 1 < len(all_sub_bullets):
                        b1 = all_sub_bullets[idx_b]
                        b2 = all_sub_bullets[idx_b + 1]
                        packed_cards.append(f"{b1} | {b2}")
                        idx_b += 2
                        rem_items -= 2
                    else:
                        packed_cards.append(all_sub_bullets[idx_b])
                        idx_b += 1
                        rem_items -= 1
                    rem_slots -= 1
                compacted_sub_slides: List[Dict[str, Any]] = []
                for c_i in range(0, len(packed_cards), 4):
                    base_ss = dict(sub_slides[min(c_i // 4, len(sub_slides) - 1)])
                    base_ss["bullets"] = packed_cards[c_i : c_i + 4]
                    compacted_sub_slides.append(base_ss)
                selected_topic_slides = compacted_sub_slides[:3] + other_slides[:1]
            elif sub_slides:
                extra_budget = 2 if (len(sub_slides) == 1 and n_reqs <= 6) else 1
                selected_topic_slides = sub_slides + other_slides[:extra_budget]
            else:
                per_req_cap = 3 if n_reqs <= 6 else 2
                selected_topic_slides = raw_topic_slides[:per_req_cap]
            selected_topic_slides = selected_topic_slides[:4]
            first_topic_shows_req = True

        # Topic Instruction & Full-Page Diagram Slides for Requirement N
        for t_idx, ts in enumerate(selected_topic_slides, start=1):
            ts_title = _sanitize_no_ellipsis_or_emdash(str(ts.get("title") or f"{clean_section_title} (Part {t_idx})"))
            ts_layout = str(ts.get("layout") or "CONCEPT_TEXT_SLIDE")
            raw_ts_bullets = ts.get("bullets") or _build_bullet_points_for_req(req, req_num, req_text)
            ts_bullets = [
                _sanitize_no_ellipsis_or_emdash(str(b))
                for b in raw_ts_bullets
                if str(b).strip()
            ][:6]

            ts_comp = ts.get("comparison_data") or (
                req.get("comparison_data") if ts_layout == SlideArchetype.DIFFERENTIAL_COMPARISON_2COL.value else None
            )
            if hasattr(ts_comp, "model_dump"):
                ts_comp = ts_comp.model_dump()

            ts_we = ts.get("worked_example") or (
                req.get("worked_example") if ts_layout == SlideArchetype.WORKED_EXAMPLE_TEMPLATE.value else None
            )
            if hasattr(ts_we, "model_dump"):
                ts_we = ts_we.model_dump()

            ts_quiz = ts.get("quiz_item") or (
                req.get("quiz_item") if ts_layout == SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value else None
            )
            if hasattr(ts_quiz, "model_dump"):
                ts_quiz = ts_quiz.model_dump()

            ts_gear = [
                _sanitize_no_ellipsis_or_emdash(str(g))
                for g in (ts.get("gear_checklist") or (
                    req.get("gear_checklist") if ts_layout == SlideArchetype.GEAR_CHECKLIST_GRID.value else []
                ) or [])
            ]

            ts_cards = _build_cards_for_req({"req_text": req_text, "step_by_step_procedure": ts_bullets}, ts_bullets)
            ts_img = ts.get("image_path")
            ts_caption = _sanitize_no_ellipsis_or_emdash(str(ts.get("caption") or ts_title))

            # Only show the requirement text on the first slide of the sequence (if not already shown)
            show_req_on_this_slide = first_topic_shows_req and (t_idx == 1)
            if show_req_on_this_slide and ts_layout == "FULL_BLEED_IMAGE_EXPLAINER":
                ts_layout = "SPLIT_VISUAL_EXPLAINER"

            slide_safety = safety if show_req_on_this_slide else None
            # Attach misconception_pair on the first non-safety slide of the requirement sequence
            show_misc_on_this_slide = (t_idx == 1 and not slide_safety) or (t_idx == 2 and bool(safety))

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
