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
    """Removes ellipses ('...') and em-dashes ('—', '--') for clean slide and speaker copy."""
    if not text:
        return ""
    cleaned = str(text).replace("...", ".").replace("…", ".")
    cleaned = cleaned.replace(" — ", ", ").replace(" -- ", ", ")
    cleaned = cleaned.replace("—", ", ").replace("--", ", ")
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
    """Splits a 'Bold Anchor: Body text' string into (anchor, body)."""
    cleaned = _sanitize_no_ellipsis_or_emdash(str(raw_point or "").strip())
    if ":" in cleaned:
        anchor, body = cleaned.split(":", 1)
        if 1 <= len(anchor.strip()) <= 60 and body.strip():
            return anchor.strip(), body.strip()
    words = cleaned.split()
    if len(words) > 4:
        return " ".join(words[:3]), " ".join(words[3:])
    return fallback_anchor, cleaned


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
) -> str:
    """Builds rich, slide-specific Counselor Teaching Notes without generic boilerplate.

    Key properties:
    - [SAY] is always included and is more detailed than the text shown on the slide,
      unpacking the underlying mechanisms, real-world Scouting applications, and supplementary
      details for every point, comparison column, worked example, or diagram on the slide.
    - [DEMONSTRATE] is included ONLY when the slide invites a physical demonstration, gear
      inspection, sample template walkthrough, or visual diagram trace.
    - [ASK SCOUTS] is included ONLY when the slide invites a Socratic question, diagnostic
      comparison, or comprehension check.
    """
    clean_badge = _sanitize_no_ellipsis_or_emdash(badge_name)
    clean_req = _sanitize_no_ellipsis_or_emdash(req_num)
    clean_title = _sanitize_no_ellipsis_or_emdash(slide_title or f"{clean_badge} Requirement {clean_req}")
    clean_req_text = _sanitize_no_ellipsis_or_emdash(req_text)
    arch = (archetype or "CONCEPT_TEXT_SLIDE").upper()
    pts = [_sanitize_no_ellipsis_or_emdash(str(p)) for p in (bullet_points or []) if str(p).strip()]
    req_data = req_dict or {}

    parsed_points = [
        _split_anchor_and_detail(p, f"Concept {idx + 1}")
        for idx, p in enumerate(pts)
    ]
    anchors = [a for a, _ in parsed_points if a]

    # Collect supplementary insights from the requirement dictionary that are not already verbatim on the slide
    extra_insights: List[str] = []
    for raw_ex in list(req_data.get("pamphlet_excerpts") or []) + list(req_data.get("step_by_step_procedure") or []):
        clean_ex = _sanitize_no_ellipsis_or_emdash(str(raw_ex))
        if clean_ex and clean_ex not in pts:
            extra_insights.append(clean_ex)

    lines: List[str] = []

    # -------------------------------------------------------------------------
    # CASE 1: REQUIREMENTS OVERVIEW MATRIX (SLIDE 2) — [SAY] ONLY
    # -------------------------------------------------------------------------
    if arch == SlideArchetype.REQUIREMENTS_TRIAGE_MATRIX.value or clean_req.lower() == "overview":
        ov = overview_summary or {}
        in_class_list = ", ".join((ov.get("in_class") or [])[:5]) or "foundational concepts and definitions"
        station_list = ", ".join((ov.get("station") or [])[:5]) or "hands-on field skills"
        prereq_list = ", ".join((ov.get("prereq") or [])[:5]) or "outdoor observations and home projects"
        total_r = ov.get("total_count", [str(len(pts))])[0]
        lines.append(
            f"[SAY] Walk Scouts through the complete roadmap for earning the {clean_badge} Merit Badge across all {total_r} official requirements. "
            f"Explain that our sessions are organized into three practical tracks: first, knowledge and group discussion topics ({in_class_list}) where we build core understanding; "
            f"second, hands-on skill stations ({station_list}) where every Scout will practice and demonstrate techniques individually; "
            f"and third, field, campout, or home prerequisites ({prereq_list}) that require real-world logging and documentation outside the classroom. "
            f"Emphasize that Scouts should use their companion {clean_badge} Workbook to record notes, measurements, and reflections for each requirement prior to final blue-card or Scoutbook sign-off."
        )
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # CASE 2: SOURCES & REFERENCES (FINAL SLIDE) — [SAY] ONLY
    # -------------------------------------------------------------------------
    if arch == "SOURCES_AND_REFERENCES" or clean_req.lower() == "sources":
        lines.append(
            f"[SAY] Conclude the {clean_badge} Merit Badge presentation by reviewing the authoritative reference materials listed on this slide. "
            f"Direct Scouts to the official Scouting America {clean_badge} Merit Badge Pamphlet and Digital Resource Guide URLs so they can review definitions, diagrams, and field checklists before their individual counselor conference. "
            f"Remind Scouts to bring their completed {clean_badge} Workbook logs, any required project artifacts or field sketches, and their signed blue card or Scoutbook record to their final verification review. "
            "Note that this instructional slide deck and companion workbook were generated using the Scouts BSA Merit Badge Counselor Workbench created by Eric Clayberg (Troop 19, Middleton MA)."
        )
        return "\n".join(lines)

    # Build a rich per-point elaboration helper so [SAY] is always deeper than the slide bullets
    point_elaborations: List[str] = []
    for idx_p, (anc, bdy) in enumerate(parsed_points):
        if bdy.endswith("."):
            bdy_clean = bdy[:-1]
        else:
            bdy_clean = bdy
        if idx_p == 0:
            point_elaborations.append(
                f"Start with {anc}: {bdy_clean}, and explain how this principle establishes the foundation for {clean_title}"
            )
        elif idx_p == 1:
            point_elaborations.append(
                f"Next, unpack {anc} ({bdy_clean}), highlighting the real-world cause-and-effect relationship and why Scouts must recognize it in the field"
            )
        elif idx_p == 2:
            point_elaborations.append(
                f"Then cover {anc} ({bdy_clean}), pointing out practical field indicators and common beginner misconceptions to avoid"
            )
        else:
            point_elaborations.append(
                f"Also emphasize {anc} ({bdy_clean}) so Scouts can connect the concept directly to hands-on field application"
            )

    elaboration_paragraph = ". ".join(point_elaborations) + "." if point_elaborations else ""
    supplementary_note = (
        f" Go beyond the slide text by sharing these additional instructional details: {' '.join(extra_insights[:2])}"
        if extra_insights
        else (
            f" Connect these points back to the official Requirement {clean_req} standard ({clean_req_text}) so Scouts can explain not just the definitions, but why each detail matters in practice."
            if clean_req_text
            else ""
        )
    )
    safety_note = (
        f" Reinforce the critical safety rule for this topic: {_sanitize_no_ellipsis_or_emdash(safety_callout)}"
        if safety_callout
        else ""
    )

    # -------------------------------------------------------------------------
    # CASE 3: REQUIREMENT INTRO SLIDE — [SAY] + [ASK SCOUTS] (NO [DEMONSTRATE])
    # -------------------------------------------------------------------------
    if arch == "REQUIREMENT_INTRO":
        lines.append(
            f"[SAY] Introduce {clean_badge} Requirement {clean_req} ({clean_title}) by reading the official requirement expectation aloud: \"{clean_req_text}\" "
            f"Explain what Scouts will need to know and accomplish across this requirement sequence: {elaboration_paragraph}"
            f"{supplementary_note}{safety_note}"
        )
        focus_topics = (
            f"{anchors[0]} and {anchors[1]}"
            if len(anchors) >= 2
            else (anchors[0] if anchors else clean_title)
        )
        lines.append(
            f"[ASK SCOUTS] Looking at the scope of Requirement {clean_req} ({clean_title}), where have you encountered {focus_topics} on a previous troop campout, hike, or at home, and what questions do you have before we dive into the details?"
        )
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # CASE 4: DIFFERENTIAL COMPARISON (2-COLUMN) — [SAY] + [ASK SCOUTS] (+ [DEMONSTRATE] only if visual)
    # -------------------------------------------------------------------------
    if arch == SlideArchetype.DIFFERENTIAL_COMPARISON_2COL.value or comparison_data:
        cd = comparison_data or {}
        left_h = _sanitize_no_ellipsis_or_emdash(str(cd.get("left_header") or (anchors[0] if anchors else "Category A")))
        right_h = _sanitize_no_ellipsis_or_emdash(str(cd.get("right_header") or (anchors[1] if len(anchors) > 1 else "Category B")))
        left_pts = [_sanitize_no_ellipsis_or_emdash(str(x)) for x in (cd.get("left_points") or pts[:3])]
        right_pts = [_sanitize_no_ellipsis_or_emdash(str(x)) for x in (cd.get("right_points") or pts[3:6])]
        left_summary = "; ".join(left_pts[:3]) or elaboration_paragraph
        right_summary = "; ".join(right_pts[:3]) or supplementary_note

        lines.append(
            f"[SAY] Walk Scouts through the side-by-side comparison on \"{clean_title}\" by contrasting {left_h} against {right_h}. "
            f"On the left ({left_h}), explain the defining characteristics and mechanisms in detail: {left_summary}. "
            f"On the right ({right_h}), contrast how the conditions, indicators, or required responses differ: {right_summary}. "
            f"Emphasize why distinguishing accurately between {left_h} and {right_h} under real field conditions is critical for making the right decision.{supplementary_note}{safety_note}"
        )
        if has_visual and visual_caption:
            lines.append(
                f"[DEMONSTRATE] Point to the accompanying diagram ({visual_caption}) and trace the visual differences between {left_h} and {right_h} so Scouts can spot those exact cues in the field."
            )
        lines.append(
            f"[ASK SCOUTS] If your patrol encountered this situation outdoors without instruments or reference notes, which specific indicator on this slide would help you tell {left_h} apart from {right_h} first, and how would your action plan change?"
        )
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # CASE 5: WORKED EXAMPLE TEMPLATE — [SAY] + [DEMONSTRATE] (NO [ASK SCOUTS])
    # -------------------------------------------------------------------------
    if arch == SlideArchetype.WORKED_EXAMPLE_TEMPLATE.value or worked_example:
        we = worked_example or {}
        we_title = _sanitize_no_ellipsis_or_emdash(str(we.get("title") or clean_title))
        we_type = _sanitize_no_ellipsis_or_emdash(str(we.get("artifact_type") or "Sample Log & Template"))
        we_fields = we.get("fields") or {}
        we_tip = _sanitize_no_ellipsis_or_emdash(
            str(we.get("counselor_tip") or "Ensure every entry includes specific dates, measurements, and verifiable observations.")
        )
        field_walkthrough = "; ".join(f"{k} ({v})" for k, v in list(we_fields.items())[:5]) if we_fields else elaboration_paragraph
        field_names = ", ".join(list(we_fields.keys())[:4]) if we_fields else (", ".join(anchors[:3]) or "each required log field")

        lines.append(
            f"[SAY] Guide Scouts through this worked example ({we_type}: {we_title}) for Requirement {clean_req}. "
            f"Break down each completed entry in detail so Scouts understand the level of specificity required for counselor sign-off: {field_walkthrough}. "
            f"Highlight the Counselor Pro-Tip: {we_tip} Explain that vague or one-word entries are not sufficient; Scouts should record concrete measurements, timestamps, and observations just like this model.{supplementary_note}{safety_note}"
        )
        lines.append(
            f"[DEMONSTRATE] Walk through the sample {we_title} fields ({field_names}) line by line and show Scouts how to record their own real observations in their printable {clean_badge} Merit Badge Workbook."
        )
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # CASE 6: SOCRATIC CHECKPOINT QUIZ — [SAY] + [ASK SCOUTS] (NO [DEMONSTRATE])
    # -------------------------------------------------------------------------
    if arch == SlideArchetype.SOCRATIC_CHECKPOINT_QUIZ.value or quiz_item:
        qi = quiz_item or {}
        scenario = _sanitize_no_ellipsis_or_emdash(
            str(qi.get("scenario_prompt") or (pts[0] if pts else f"How should your patrol apply {clean_title}?"))
        )
        options = [_sanitize_no_ellipsis_or_emdash(str(o)) for o in (qi.get("options") or pts[1:4])]
        answer = _sanitize_no_ellipsis_or_emdash(str(qi.get("correct_answer") or "Option A"))
        explanation = _sanitize_no_ellipsis_or_emdash(
            str(qi.get("explanation") or elaboration_paragraph)
        )
        opts_text = " | ".join(options[:3])

        lines.append(
            f"[SAY] Present this patrol scenario checkpoint for {clean_title} and pause to let Scouts debate the options before revealing the verified answer. "
            f"Once patrols have shared their reasoning, confirm the verified answer ({answer}) and explain the underlying principle in detail: {explanation} "
            f"Also discuss why the alternative choices fall short or introduce avoidable risk in the field.{supplementary_note}{safety_note}"
        )
        lines.append(
            f"[ASK SCOUTS] Consider this scenario: \"{scenario}\" Review the options ({opts_text}) with your buddy, pick the best course of action, and be ready to explain why your choice is safest and most effective."
        )
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # CASE 7: FULL-BLEED IMAGE / DIAGRAM EXPLAINER — [SAY] + [DEMONSTRATE] (NO [ASK SCOUTS])
    # -------------------------------------------------------------------------
    if arch == "FULL_BLEED_IMAGE_EXPLAINER":
        fig_name = visual_caption or clean_title
        trace_anchors = ", ".join(anchors[:3]) if anchors else clean_title
        lines.append(
            f"[SAY] Use this full-page visual figure ({fig_name}) to give Scouts a clear, step-by-step tour of the structure and processes behind {clean_title}. "
            f"{elaboration_paragraph} "
            f"Explain how the visual elements in the diagram fit together in real time so Scouts can picture the mechanism rather than just memorizing terms.{supplementary_note}{safety_note}"
        )
        lines.append(
            f"[DEMONSTRATE] Point directly to each labeled stage or feature on the \"{fig_name}\" figure ({trace_anchors}), tracing the flow across the diagram so Scouts can visually follow how each component interacts."
        )
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # CASE 8: STEP-BY-STEP PROCEDURE (4-CARD) — [SAY] + [DEMONSTRATE] + [ASK SCOUTS]
    # -------------------------------------------------------------------------
    if arch == SlideArchetype.STEP_BY_STEP_PROCEDURE_4CARD.value:
        step_sequence = " -> ".join(f"Step {i + 1}: {a}" for i, a in enumerate(anchors[:4])) or clean_title
        first_step = anchors[0] if anchors else "Step 1"
        second_step = anchors[1] if len(anchors) > 1 else "Step 2"
        lines.append(
            f"[SAY] Walk Scouts through the step-by-step procedure for \"{clean_title}\" under Requirement {clean_req}. "
            f"{elaboration_paragraph} "
            f"Emphasize why following this exact sequence ({step_sequence}) prevents errors and ensures safe, repeatable results in the field.{supplementary_note}{safety_note}"
        )
        lines.append(
            f"[DEMONSTRATE] Physically model the \"{clean_title}\" sequence step by step ({step_sequence}) at a deliberate pace using the BSA EDGE method (Explain, Demonstrate, Guide, Enable), pausing at {first_step} and {second_step} so Scouts can observe proper hand placement, setup, or technique."
        )
        lines.append(
            f"[ASK SCOUTS] Why is it important to complete {first_step} before moving on to {second_step} in \"{clean_title},\" and what problem could arise in the field if a Scout rushed or skipped that step?"
        )
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # CASE 9: GEAR CHECKLIST GRID — [SAY] + [DEMONSTRATE] + [ASK SCOUTS]
    # -------------------------------------------------------------------------
    if arch == SlideArchetype.GEAR_CHECKLIST_GRID.value or gear_checklist:
        gear_items = [_sanitize_no_ellipsis_or_emdash(str(g)) for g in (gear_checklist or pts)]
        gear_anchors = [_split_anchor_and_detail(g, f"Item {i + 1}")[0] for i, g in enumerate(gear_items[:4])]
        gear_list_str = ", ".join(gear_anchors) or clean_title
        lines.append(
            f"[SAY] Review the required equipment and pre-trip inspection checklist for \"{clean_title}\" (Requirement {clean_req}). "
            f"{elaboration_paragraph} "
            f"Explain not only what each item ({gear_list_str}) is used for, but also how to inspect it for wear, missing parts, or weather readiness before leaving for the field.{supplementary_note}{safety_note}"
        )
        lines.append(
            f"[DEMONSTRATE] Lay out or hold up examples of the key gear items for \"{clean_title}\" ({gear_list_str}) and demonstrate a hands-on readiness check so Scouts see how to verify condition and fit."
        )
        lines.append(
            f"[ASK SCOUTS] Looking at the \"{clean_title}\" checklist ({gear_list_str}), which item is most often overlooked during a pack shakedown, and what would happen if your patrol needed it in the field and didn't have it?"
        )
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # CASE 10: CONCEPT TEXT SLIDE OR SPLIT VISUAL EXPLAINER
    #   - [SAY]: Always detailed and expanded beyond the slide bullets
    #   - [DEMONSTRATE]: Included ONLY when the slide has a visual figure (`has_visual`)
    #     or explicitly covers a hands-on physical skill/construction/instrument
    #   - [ASK SCOUTS]: Specific comprehension/application question tied to the slide's anchors
    # -------------------------------------------------------------------------
    visual_tie_in = (
        f" Direct Scouts' attention to the visual figure ({visual_caption}) and explain how it illustrates {', '.join(anchors[:2]) or clean_title} in action."
        if has_visual and visual_caption
        else ""
    )
    lines.append(
        f"[SAY] Teach the core concepts on \"{clean_title}\" (Requirement {clean_req}) in depth rather than just reading the cards aloud. "
        f"{elaboration_paragraph}"
        f"{visual_tie_in}{supplementary_note}{safety_note}"
    )

    invites_demo = has_visual or execution_mode == ExecutionMode.HANDS_ON_SKILL_STATION.value or any(
        kw in clean_title.lower()
        for kw in ("demonstrat", "build", "construct", "instrument", "measure", "knot", "splint", "bandage", "cpr", "triage", "rescue", "drill", "station")
    )
    if invites_demo:
        if has_visual and visual_caption:
            trace_targets = ", ".join(anchors[:3]) if anchors else clean_title
            lines.append(
                f"[DEMONSTRATE] Use the \"{visual_caption}\" visual on the right side of the slide to point out {trace_targets}, showing Scouts how each part operates in a real scenario."
            )
        else:
            skill_targets = ", ".join(anchors[:3]) if anchors else clean_title
            lines.append(
                f"[DEMONSTRATE] Model the practical technique for \"{clean_title}\" ({skill_targets}) so Scouts can see the proper form and standard before practicing with their buddy."
            )

    q_focus = (
        f"{anchors[0]} and {anchors[1]}"
        if len(anchors) >= 2
        else (anchors[0] if anchors else clean_title)
    )
    lines.append(
        f"[ASK SCOUTS] Based on what we just covered on \"{clean_title},\" how would you explain the relationship between {q_focus} in your own words, and how does it apply when working on {clean_badge} Requirement {clean_req}?"
    )
    return "\n".join(lines)


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


def _build_cards_for_req(req: Dict[str, Any], bullets: List[str]) -> List[Dict[str, Any]]:
    """Builds 4 structured card dictionaries from the pamphlet's step-by-step procedures and excerpts."""
    steps = list(req.get("step_by_step_procedure") or [])
    for ex in req.get("pamphlet_excerpts") or []:
        if ex not in steps:
            steps.append(ex)
    if not steps:
        steps = list(bullets[:4])

    cards: List[Dict[str, Any]] = []
    colors = ["#003F87", "#005AE0", "#4B5320", "#CE1126"]
    for idx_s, raw_step in enumerate(steps[:4], start=1):
        clean_s = _sanitize_no_ellipsis_or_emdash(str(raw_step))
        if ":" in clean_s:
            anchor, body = clean_s.split(":", 1)
        else:
            words = clean_s.split()
            anchor = " ".join(words[:3]) if words else f"Step {idx_s}"
            body = " ".join(words[3:]) if len(words) > 3 else clean_s
        cards.append({
            "badge_label": f"STEP {idx_s}",
            "anchor_title": anchor.strip()[:36] or f"Step {idx_s}",
            "body_text": body.strip() or clean_s,
            "accent_color_hex": colors[(idx_s - 1) % len(colors)],
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
        summarize_pamphlet_for_requirement,
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

    overview_pamphlet = summarize_pamphlet_for_requirement(
        badge_name=clean_badge,
        req_number="Overview",
        req_text=f"{clean_badge} Merit Badge overview and core skills",
        req_index=0,
        total_reqs=max(1, len(requirements)),
    )

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
            diagram_path=overview_pamphlet.get("pamphlet_image_path"),
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

        raw_topic_slides = list(req.get("topic_slides") or [])
        if not raw_topic_slides or (is_deep_dive and len(raw_topic_slides) < 5):
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
            intro_title = f"Requirement {req_num}: {clean_section_title}"
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
                )
            )
            selected_topic_slides = raw_topic_slides
            first_topic_shows_req = False
        else:
            # Standard Troop Meeting mode: 1-3 focused slides per requirement.
            # Slide 1 of the sequence lists the requirement AND teaches the first topic.
            selected_topic_slides = raw_topic_slides[:2] if len(requirements) >= 8 else raw_topic_slides[:3]
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

            ts_cards = _build_cards_for_req({"step_by_step_procedure": ts_bullets}, ts_bullets)
            ts_img = ts.get("image_path")
            ts_caption = _sanitize_no_ellipsis_or_emdash(str(ts.get("caption") or ts_title))

            # Only show the requirement text on the first slide of the sequence (if not already shown)
            show_req_on_this_slide = first_topic_shows_req and (t_idx == 1)
            if show_req_on_this_slide and ts_layout == "FULL_BLEED_IMAGE_EXPLAINER":
                ts_layout = "SPLIT_VISUAL_EXPLAINER"

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
                        safety_callout=safety if show_req_on_this_slide else None,
                    ),
                    safety_warning=safety if show_req_on_this_slide else None,
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
    ]
    if clean_badge.lower() == "weather":
        source_bullets.append(
            "Meteorological & Instructional References: National Weather Service (NWS) JetStream (https://www.weather.gov), NOAA, USGS, EPA, AMS Glossary, WFO Medford (Jay R. Stockton), and Danvers Merit Badge College / Troop 19 Middleton."
        )
    source_bullets.append(
        "Slide Deck Attribution: This slide deck was created by the Scouts BSA Merit Badge Counselor Workbench tool (https://github.com/clayberg/scouts-bsa-merit-badge-agent), created by Eric Clayberg (Troop 19, Middleton MA)."
    )

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
