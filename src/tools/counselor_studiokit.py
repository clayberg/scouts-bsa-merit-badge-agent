"""Interactive Counselor AI Studio Toolkit (`src/tools/counselor_studiokit.py`).

Provides AI-assisted Merit Badge Counselor session planning and communication tools:
1. `generate_counselor_session_agenda`: Builds a minute-by-minute class schedule and EDGE
   skill station plan for troop meetings, Saturday clinics, or summer camp weeks.
2. `generate_prerequisite_parent_letter`: Generates a ready-to-send email/letter to Scouts
   and parents listing all `PREREQUISITE_CAMPOUT_HOME` requirements, Youth Protection (YPT)
   Two-Deep Leadership & Buddy System reminders, and required field gear.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from src.agents.researcher import resolve_counselor_location
from src.schemas import build_guided_tool_error


class CounselorSessionAgendaRequest(BaseModel):
    """Pydantic request contract for `generate_counselor_session_agenda`."""

    badge_name: str = Field(..., description="Official Scouts BSA Merit Badge name.")
    schedule_format: str = Field(
        default="3 Troop Meetings (45 min each)",
        description="Selected session schedule format.",
    )
    session_mode: str = Field(
        default="",
        description="Optional alias for schedule_format (e.g., 4_session_mbc, 2_double_block, TWO_TROOP_MEETINGS, SATURDAY_CLINIC, SUMMER_CAMP).",
    )
    option_track: str = Field(
        default="ALL",
        description="Optional Merit Badge Option Track (e.g., A, B, ALL).",
    )
    counselor_name: str = Field(default="", description="Optional Merit Badge Counselor name.")
    troop_affiliation: str = Field(default="", description="Optional troop and council affiliation.")
    location_or_zip: str = Field(default="", description="Optional ZIP code or city/state.")
    postponed_session_idx: Optional[int] = Field(
        default=None,
        description="Optional 1-based session index (1..4) postponed due to weather/snow day, shifting subsequent sessions into Make-Up Day.",
    )
    companion_badge_name: Optional[str] = Field(
        default=None,
        description="Optional companion Merit Badge name for 2-in-1 paired clinics (Sessions 1-2 Badge A, Sessions 3-4 Badge B).",
    )
    research_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional pre-fetched MeritBadgeResearchResult dictionary.",
    )


class PrerequisiteParentLetterRequest(BaseModel):
    """Pydantic request contract for `generate_prerequisite_parent_letter`."""

    badge_name: str = Field(..., description="Official Scouts BSA Merit Badge name.")
    option_track: str = Field(
        default="ALL",
        description="Optional Merit Badge Option Track (e.g., A, B, ALL).",
    )
    counselor_name: str = Field(default="", description="Optional Merit Badge Counselor name.")
    troop_affiliation: str = Field(default="", description="Optional troop and council affiliation.")
    location_or_zip: str = Field(default="", description="Optional ZIP code or city/state.")
    session_dates_or_location: str = Field(default="", description="Optional session dates or camp/hall location.")
    counselor_email: str = Field(default="", description="Optional counselor contact email.")
    phone_number: str = Field(default="", description="Optional counselor contact phone.")
    research_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional pre-fetched MeritBadgeResearchResult dictionary.",
    )


def _resolve_option_track_and_filter_reqs(
    badge_name: str,
    reqs: List[Dict[str, Any]],
    option_track: str = "ALL",
) -> tuple[str, str, List[Dict[str, Any]]]:
    """Normalizes `option_track`, resolves a human-readable track label, and filters `reqs` if an option track is active."""
    from src.tools.scouting_scraper import (
        _filter_requirements_by_option_track,
        _normalize_option_track_filter,
        get_badge_option_tracks,
    )

    opt_norm = _normalize_option_track_filter(option_track, badge_name=badge_name)
    tracks = get_badge_option_tracks(badge_name)
    opt_label = f"Option Track {opt_norm}" if opt_norm != "ALL" else "All Options (ALL)"
    if tracks and opt_norm != "ALL":
        for tr in tracks:
            if str(tr.get("option_key") or "").upper() == opt_norm or str(tr.get("letter_key") or "").upper() == opt_norm:
                opt_label = str(tr.get("label") or tr.get("option_label") or opt_label)
                break
    filtered = list(reqs or [])
    if opt_norm != "ALL" and filtered:
        # Filter out other options if raw/unfiltered reqs were passed
        has_other_opts = any(
            str(r.get("selected_option_key") or "").upper() not in ("", opt_norm)
            for r in filtered
            if r.get("selected_option_key")
        )
        if has_other_opts:
            filtered = [
                r
                for r in filtered
                if not r.get("selected_option_key")
                or str(r.get("selected_option_key")).upper() == opt_norm
                or str(r.get("req_number") or "").upper().startswith(opt_norm)
            ]
        else:
            filtered = _filter_requirements_by_option_track(badge_name, filtered, option_track=opt_norm)
    return opt_norm, opt_label, filtered


def _normalize_middleton_text(val: str) -> str:
    """Normalizes common 'Middelton' typo to 'Middleton' and cleans redundant nested ZIP parens."""
    out = re.sub(r"\bmiddelton\b", "Middleton", str(val or "").strip(), flags=re.IGNORECASE)
    out = re.sub(r"\s*\(\d{5}(?:-\d{4})?\)\s*$", "", out).strip()
    return out


def _extract_normalized_counselor_fields(
    counselor_info: Optional[Dict[str, Any]],
    default_name: str = "Scoutmaster Bob",
    default_troop: str = "Troop 19, Middleton MA",
    default_email: str = "counselor@troop123.org",
) -> Dict[str, Any]:
    """Extracts and normalizes counselor metadata across all alias keys."""
    c_info = dict(counselor_info or {})
    c_name = _normalize_middleton_text(
        str(c_info.get("counselor_name") or c_info.get("name") or default_name)
    )
    c_loc_raw = _normalize_middleton_text(
        str(c_info.get("location_or_zip") or c_info.get("location") or "")
    )
    raw_troop = str(c_info.get("troop_affiliation") or c_info.get("troop") or default_troop)
    c_troop = _normalize_middleton_text(raw_troop)
    if c_loc_raw and f"({c_loc_raw})" in c_troop:
        c_troop = c_troop.replace(f"({c_loc_raw})", "").strip()
    c_email = str(c_info.get("email_address") or c_info.get("email") or default_email).strip()
    c_phone = str(c_info.get("phone_number") or c_info.get("phone") or "(000) 555-1234").strip()
    session_tag = _normalize_middleton_text(
        str(c_info.get("session_tag") or c_info.get("bundle_tag") or "")
    )
    bundle_tag = _normalize_middleton_text(
        str(c_info.get("bundle_tag") or c_info.get("session_tag") or "")
    )
    section_label = str(c_info.get("section_label") or "").strip()
    class_start_time = str(c_info.get("class_start_time") or "").strip()
    room_location = _normalize_middleton_text(
        str(c_info.get("room_location") or c_info.get("room_and_venue") or "")
    )
    raw_dates = c_info.get("session_dates_list") or c_info.get("session_dates") or []
    if isinstance(raw_dates, str):
        session_dates_list = [s.strip() for s in re.split(r"[|•,;]+", raw_dates) if s.strip()]
    elif isinstance(raw_dates, list):
        session_dates_list = [str(s).strip() for s in raw_dates if str(s).strip()]
    else:
        session_dates_list = []

    return {
        "c_name": c_name,
        "c_troop": c_troop,
        "c_loc_raw": c_loc_raw,
        "c_email": c_email,
        "c_phone": c_phone,
        "session_tag": session_tag,
        "bundle_tag": bundle_tag,
        "section_label": section_label,
        "class_start_time": class_start_time,
        "room_location": room_location,
        "session_dates_list": session_dates_list,
    }


def generate_counselor_session_agenda(
    badge_name: str,
    research_result: Optional[Dict[str, Any]] = None,
    schedule_format: str = "3 Troop Meetings (45 min each)",
    counselor_info: Optional[Dict[str, Any]] = None,
    postponed_session_idx: Optional[int] = None,
    companion_badge_name: Optional[str] = None,
    class_start_time: str = "",
    room_location: str = "",
    session_dates_list: Optional[List[str]] = None,
    session_dates: Optional[List[str]] = None,
    section_label: str = "",
    bundle_tag: str = "",
    option_track: str = "ALL",
) -> Dict[str, Any]:
    """Generates a structured minute-by-minute Merit Badge teaching agenda and EDGE station guide.

    Supports:
    - `'3 Troop Meetings (45 min each)'`
    - `'Multi-Session Merit Badge Clinic (4x 75-min + Make-Up Day)'` (`4_session_mbc`)
    - `'Two-Period Double-Block Clinic (2x 150-min Sessions)'` (`2_double_block`)
    - `'Saturday Merit Badge Clinic (3 hours)'`
    - `'Summer Camp Week (4x 50-min blocks)'`
    - Snow-Day Make-Up Shift (`postponed_session_idx` 1..4)
    - Companion Dual-Badge (`2-in-1`) Split (`companion_badge_name`)
    """
    if isinstance(badge_name, CounselorSessionAgendaRequest):
        req_obj = badge_name
        badge_name = req_obj.badge_name
        schedule_format = req_obj.session_mode or req_obj.schedule_format or schedule_format
        if getattr(req_obj, "option_track", None):
            option_track = req_obj.option_track
        counselor_info = counselor_info or {
            "counselor_name": req_obj.counselor_name,
            "troop_affiliation": req_obj.troop_affiliation,
            "location_or_zip": req_obj.location_or_zip,
        }
        if postponed_session_idx is None:
            postponed_session_idx = req_obj.postponed_session_idx
        if not companion_badge_name:
            companion_badge_name = req_obj.companion_badge_name
        if req_obj.research_result is not None:
            research_result = req_obj.research_result

    if not badge_name or not str(badge_name).strip():
        return build_guided_tool_error(
            error_code="EMPTY_BADGE_NAME",
            message="badge_name cannot be empty when generating a counselor session agenda.",
            remediation="Provide a valid Scouts BSA Merit Badge name such as 'Weather' or 'First Aid'.",
        )
    if research_result is None:
        from src.tools.scouting_scraper import MeritBadgeResearchRequest, fetch_merit_badge_pamphlet_pdf

        research_result = fetch_merit_badge_pamphlet_pdf(
            MeritBadgeResearchRequest(badge_name=str(badge_name).strip(), option_track=option_track)
        )
    if not isinstance(research_result, dict):
        return build_guided_tool_error(
            error_code="INVALID_RESEARCH_RESULT",
            message="research_result must be a dictionary containing Merit Badge requirements.",
            remediation="Call fetch_merit_badge_pamphlet_pdf first and pass its output dictionary.",
        )

    clean_badge = str(research_result.get("badge_name") or badge_name).strip()
    c_info = counselor_info or {}
    loc = resolve_counselor_location(
        troop_affiliation=str(c_info.get("troop_affiliation") or ""),
        location_or_zip=str(c_info.get("location_or_zip") or ""),
    )
    raw_reqs: List[Dict[str, Any]] = list(research_result.get("requirements") or [])
    opt_norm, opt_label, reqs = _resolve_option_track_and_filter_reqs(clean_badge, raw_reqs, option_track=option_track)
    in_class = [r for r in reqs if str(r.get("execution_mode", "")).upper() == "IN_CLASS_DISCUSSION"]
    hands_on = [r for r in reqs if str(r.get("execution_mode", "")).upper() == "HANDS_ON_SKILL_STATION"]
    prereqs = [r for r in reqs if str(r.get("execution_mode", "")).upper() == "PREREQUISITE_CAMPOUT_HOME"]

    in_class_ids = ", ".join(str(r.get("req_number")) for r in in_class[:8]) or "1, 2"
    hands_on_ids = ", ".join(str(r.get("req_number")) for r in hands_on[:8]) or "3, 4"
    prereq_ids = ", ".join(str(r.get("req_number")) for r in prereqs[:8]) or "Field / Home Logs"

    companion_clean = str(companion_badge_name or "").strip()
    fmt_lower = str(schedule_format or "").lower()

    if "4_session_mbc" in fmt_lower or "75-min" in fmt_lower or "75 min" in fmt_lower or "multi-session" in fmt_lower or "mbc" in fmt_lower:
        b2_label = companion_clean or clean_badge
        sessions = [
            {
                "session_number": 1,
                "badge_focus": clean_badge,
                "title": f"Session 1 (75 min): {clean_badge} Intake, Prerequisite Gate Check & Core Theory",
                "duration_minutes": 75,
                "focus_requirements": f"{prereq_ids} (Gate Check) + {in_class_ids}",
                "edge_method_focus": "Explain & Demonstrate",
                "slide_range": "Cover, Overview, Slide 2 Logistics & Core Concept Slides (Part 1)",
                "activities": [
                    f"00–15 min: Multi-Troop Blue Card (#34124) intake, YPT Buddy pairing, and Starting Requirement Gate check ({prereq_ids}).",
                    f"15–55 min: Interactive slide walkthrough of {clean_badge} Core Concept Requirements ({in_class_ids}) using the 5-Part Facilitator Guide.",
                    "55–75 min: Fillable Form (GTA §7.0.3.2) Workbook checkpoint & assignment of Session 2 skill station prep.",
                ],
            },
            {
                "session_number": 2,
                "badge_focus": clean_badge,
                "title": f"Session 2 (75 min): {clean_badge} Hands-On EDGE Skill Stations (Part 1)",
                "duration_minutes": 75,
                "focus_requirements": hands_on_ids,
                "edge_method_focus": "Demonstrate & Guide",
                "slide_range": "Step-by-Step Procedure & Differential Comparison Slides",
                "activities": [
                    f"00–15 min: Counselor tabletop/field EDGE demonstration of primary {clean_badge} procedures.",
                    f"15–60 min: Rotating Buddy-Pair Hands-On Skill Stations for Requirements ({hands_on_ids}).",
                    "60–75 min: Batch Session 2 requirement sign-off stamp for present Scouts.",
                ],
            },
            {
                "session_number": 3,
                "badge_focus": b2_label,
                "title": (
                    f"Session 3 (75 min): Companion Badge ({b2_label}) Core Theory & Practical Stations"
                    if companion_clean
                    else f"Session 3 (75 min): {clean_badge} Applied Practicum, Worked Examples & Local {loc['state_code']} Context"
                ),
                "duration_minutes": 75,
                "focus_requirements": f"{hands_on_ids}, {prereq_ids}",
                "edge_method_focus": "Guide & Enable",
                "slide_range": "Worked Examples, Gear Checklists & Local Field Slides",
                "activities": [
                    f"00–20 min: Connect {b2_label} to local {loc['display_location']} field sites ({loc['field_site_examples']}).",
                    f"20–60 min: Independent Scout skill demonstrations and Worked Example log verification ({hands_on_ids}).",
                    "60–75 min: Mid-clinic attendance audit and Stage 2 YPT Make-Up Alert preparation.",
                ],
            },
            {
                "session_number": 4,
                "badge_focus": b2_label,
                "title": f"Session 4 (75 min): {b2_label} Final Verification, Socratic Quiz & Blue Card Sign-Off",
                "duration_minutes": 75,
                "focus_requirements": f"All In-Class & Prerequisite Requirements ({in_class_ids}, {hands_on_ids}, {prereq_ids})",
                "edge_method_focus": "Enable",
                "slide_range": "Socratic Quiz Checkpoints, Closing Homework Slide & Sources",
                "activities": [
                    f"00–25 min: Final verification of Pre-Class Prerequisite and Home-Troop logs ({prereq_ids}).",
                    "25–50 min: Patrol Socratic Checkpoint Quiz and misconception review.",
                    "50–75 min: Per-Troop Blue Card (#34124) & Scoutbook CSV sign-off (identifying any Smart Partials for Make-Up Day).",
                ],
            },
            {
                "session_number": 5,
                "badge_focus": f"{clean_badge}" + (f" + {companion_clean}" if companion_clean else ""),
                "title": "Session 5 (Make-Up & Partial Verification Day - 75 min): Targeted Make-Up Stations & Final Sign-Off",
                "duration_minutes": 75,
                "focus_requirements": "Actionable Make-Up Partial Requirements",
                "edge_method_focus": "Guide & Enable",
                "slide_range": "Targeted Make-Up Requirement Slides",
                "is_makeup_session": True,
                "activities": [
                    "00–15 min: Check-in for Scouts with Actionable Make-Up Partials from Sessions 1–4.",
                    "15–55 min: Targeted 1-on-1 (within view of adults per YPT) and buddy-pair make-up demonstrations.",
                    "55–75 min: Final Per-Troop Blue Card (#34124) & Stage 3 Post-Clinic Summary export.",
                ],
            },
        ]
    elif "2_double_block" in fmt_lower or "150-min" in fmt_lower or "double-block" in fmt_lower or "double block" in fmt_lower:
        sessions = [
            {
                "session_number": 1,
                "badge_focus": clean_badge,
                "title": f"Double-Block 1 (150 min): {clean_badge} Prerequisites, Core Theory & Guided Skill Stations",
                "duration_minutes": 150,
                "focus_requirements": f"{in_class_ids}, {hands_on_ids}",
                "edge_method_focus": "Explain, Demonstrate & Guide",
                "slide_range": "Slides 1–Midpoint (Cover, Triage, Core Concepts & Procedures)",
                "activities": [
                    f"00–20 min: Multi-Troop Blue Card intake, Starting Gate check, and {clean_badge} safety briefing.",
                    f"20–75 min: Interactive slide walkthrough of Core Discussion Requirements ({in_class_ids}).",
                    "75–85 min: 10-minute patrol stretch & hydration break.",
                    f"85–150 min: Counselor EDGE demonstration and rotating Buddy-Pair Skill Stations ({hands_on_ids}).",
                ],
            },
            {
                "session_number": 2,
                "badge_focus": companion_clean or clean_badge,
                "title": f"Double-Block 2 (150 min): {companion_clean or clean_badge} Advanced Stations, Log Audit & Sign-Off",
                "duration_minutes": 150,
                "focus_requirements": f"{hands_on_ids}, {prereq_ids}",
                "edge_method_focus": "Guide & Enable",
                "slide_range": "Midpoint–End (Worked Examples, Socratic Quizzes & Closing Checkout)",
                "activities": [
                    f"00–60 min: Applied field scenarios, Worked Example walkthroughs, and local {loc['state_code']} context.",
                    "60–70 min: 10-minute patrol break.",
                    f"70–120 min: Individual verification of Prerequisite/Home logs ({prereq_ids}) and Socratic Quiz review.",
                    "120–150 min: Per-Troop Blue Card (#34124) & Scoutbook CSV sign-off packet generation.",
                ],
            },
        ]
    elif "summer camp" in fmt_lower or "4x" in fmt_lower or "50-min" in fmt_lower:
        sessions = [
            {
                "session_number": 1,
                "title": f"Monday Block: Safety Briefing, Core Theory & Official BSA {clean_badge} Pamphlet Overview",
                "duration_minutes": 50,
                "focus_requirements": in_class_ids,
                "edge_method_focus": "Explain",
                "slide_range": "Cover, Overview & Core Discussion Slides",
                "activities": [
                    f"00–12 min: Camp area check-in, Buddy System pairing, Blue Card (#34124) intake, and {clean_badge} Safety review ({loc['terrain_and_hazards']}).",
                    f"12–38 min: Interactive slide walkthrough of Core Knowledge Requirements ({in_class_ids}) grounded in the Official BSA {clean_badge} Pamphlet.",
                    "38–50 min: Socratic Patrol Quiz checkpoint & assignment of campout/evening observation logs.",
                ],
            },
            {
                "session_number": 2,
                "title": f"Tuesday Block: Counselor Demonstration & Guided {clean_badge} Skill Stations (Part 1)",
                "duration_minutes": 50,
                "focus_requirements": hands_on_ids,
                "edge_method_focus": "Demonstrate & Guide",
                "slide_range": "Hands-On Procedure & Worked Example Slides (Part 1)",
                "activities": [
                    f"00–15 min: Counselor physical step-by-step demonstration of primary {clean_badge} field procedures and quartermaster gear check.",
                    f"15–40 min: Patrol Buddy-Pair guided practice stations for Requirements ({hands_on_ids}).",
                    "40–50 min: Station debrief, safety check, and initial skill sign-offs.",
                ],
            },
            {
                "session_number": 3,
                "title": f"Wednesday Block: Hands-On Field Practicum & Local {loc['state_code']} Environment Application",
                "duration_minutes": 50,
                "focus_requirements": f"{hands_on_ids}, {prereq_ids}",
                "edge_method_focus": "Guide & Enable",
                "slide_range": "Hands-On Skill Stations (Part 2) & Field Scenario Slides",
                "activities": [
                    f"00–15 min: Connect {clean_badge} to local camp terrain ({loc['field_site_examples']}) and {loc['nws_office']} / {loc['state_agency']}.",
                    f"15–40 min: Full patrol scenario simulation & independent skill demonstrations ({hands_on_ids}).",
                    "40–50 min: Mid-week Blue Card progress audit (identifying any Partial items for Friday make-up).",
                ],
            },
            {
                "session_number": 4,
                "title": "Thursday Block: Field Log Verification, Socratic Review & Final Blue Card Sign-Off",
                "duration_minutes": 50,
                "focus_requirements": prereq_ids,
                "edge_method_focus": "Enable",
                "slide_range": "Prerequisite, Quiz & Sources Slides",
                "activities": [
                    f"00–20 min: Individual review of completed camp/field logs and projects ({prereq_ids}).",
                    "20–35 min: Final Patrol Challenge Quiz using interactive slide checkpoints.",
                    "35–50 min: Complete Blue Card (#34124) & Scoutbook Plus sign-offs (Friday open block reserved for make-up).",
                ],
            },
        ]
    elif "saturday" in fmt_lower or "clinic" in fmt_lower or "midway" in fmt_lower or "3-hour" in fmt_lower or "3 hours" in fmt_lower:
        sessions = [
            {
                "session_number": 1,
                "title": f"Hour 1 (00:00–01:00): Clinic Check-In, Prerequisite Audit & Core {clean_badge} Theory",
                "duration_minutes": 60,
                "focus_requirements": f"{prereq_ids} (Audit) + {in_class_ids}",
                "edge_method_focus": "Explain & Demonstrate",
                "slide_range": "Slides 1–20 (Cover, Triage & Core Theory)",
                "activities": [
                    f"00–15 min: Two-Deep Leadership check, Blue Card intake, Prerequisite homework verification ({prereq_ids}), and {loc['terrain_and_hazards']} safety briefing.",
                    f"15–50 min: High-energy interactive slide walkthrough of Discussion Requirements ({in_class_ids}) grounded in the Official BSA {clean_badge} Pamphlet.",
                    "50–60 min: Patrol Quiz checkpoint & 5-minute stretch/hydration break.",
                ],
            },
            {
                "session_number": 2,
                "title": "Hour 2 (01:00–02:00): Round-Robin Hands-On EDGE Skill Stations",
                "duration_minutes": 60,
                "focus_requirements": hands_on_ids,
                "edge_method_focus": "Demonstrate & Guide",
                "slide_range": "Slides 21–48 (Step-by-Step Procedures & Skill Stations)",
                "activities": [
                    f"00–12 min: Counselor live demonstration of {clean_badge} equipment and procedural steps.",
                    f"12–50 min: Rotating 15-minute Buddy-Pair Skill Stations covering Requirements ({hands_on_ids}).",
                    "50–60 min: Station gear inspection and peer buddy check.",
                ],
            },
            {
                "session_number": 3,
                "title": f"Hour 3 (02:00–03:00): Individual Mastery Verification, Local {loc['state_code']} Context & Blue Cards",
                "duration_minutes": 60,
                "focus_requirements": f"All Requirements ({in_class_ids}, {hands_on_ids}, {prereq_ids})",
                "edge_method_focus": "Guide & Enable",
                "slide_range": "Slides 49–End (Worked Examples, Checkpoints & Sources)",
                "activities": [
                    f"00–20 min: Local field application discussion ({loc['field_site_examples']} • {loc['nws_office']} / {loc['state_agency']}).",
                    "20–45 min: Individual Scout 1-on-1 (within view of adults per YPT) skill verification.",
                    "45–60 min: Blue Card (#34124) / Scoutbook Plus completion or Partial documentation.",
                ],
            },
        ]
    elif "campout" in fmt_lower or "weekend" in fmt_lower:
        sessions = [
            {
                "session_number": 1,
                "title": f"Friday Evening Cracker-Barrel (30 min): Camp Safety, Gear Check & {clean_badge} Briefing",
                "duration_minutes": 30,
                "focus_requirements": in_class_ids,
                "edge_method_focus": "Explain",
                "slide_range": "Cover, Overview & Safety / Core Concept Slides",
                "activities": [
                    f"00–10 min: Campsite hazard check ({loc['terrain_and_hazards']}) and forecast review via {loc['nws_office']}.",
                    f"10–25 min: Lantern/tablet discussion of Core Requirements ({in_class_ids}) and Quartermaster gear readiness.",
                    "25–30 min: Buddy assignments for Saturday morning field stations.",
                ],
            },
            {
                "session_number": 2,
                "title": f"Saturday Morning Field Practicum (90 min): Hands-On {clean_badge} Stations & Field Logs",
                "duration_minutes": 90,
                "focus_requirements": f"{hands_on_ids}, {prereq_ids}",
                "edge_method_focus": "Demonstrate, Guide & Enable",
                "slide_range": "All Hands-On Skill Station & Field Project Slides",
                "activities": [
                    f"00–20 min: Counselor field demonstration at {loc['field_site_examples']}.",
                    f"20–70 min: Hands-on patrol rotations for Requirements ({hands_on_ids}) and field project execution ({prereq_ids}).",
                    "70–90 min: Field workbook logging and equipment clean-up.",
                ],
            },
            {
                "session_number": 3,
                "title": "Sunday Morning Roses, Thorns & Buds (45 min): Debrief & Blue Card Sign-Off",
                "duration_minutes": 45,
                "focus_requirements": prereq_ids,
                "edge_method_focus": "Enable",
                "slide_range": "Checkpoint Quiz & Sources Slides",
                "activities": [
                    "00–15 min: Patrol reflection on field scenarios and Socratic quiz review.",
                    f"15–35 min: Final verification of Scout Workbook logs ({prereq_ids}) and skill mastery.",
                    "35–45 min: Counselor Blue Card (#34124) & Scoutbook Plus sign-off.",
                ],
            },
        ]
    else:
        sessions = [
            {
                "session_number": 1,
                "title": f"Session 1: Safety First, Core Concepts & Official BSA {clean_badge} Pamphlet Overview",
                "duration_minutes": 45,
                "focus_requirements": in_class_ids,
                "edge_method_focus": "Explain & Demonstrate",
                "slide_range": "Cover, Overview & Core Discussion Slides",
                "activities": [
                    f"00–10 min: Welcome, Two-Deep Leadership check, Blue Card intake, and {clean_badge} Hazards & Safety review ({loc['terrain_and_hazards']}).",
                    f"10–30 min: Interactive slide walkthrough of Core Discussion Requirements ({in_class_ids}) grounded in the Official BSA {clean_badge} Pamphlet.",
                    "30–45 min: Socratic Patrol Check-on-Learning & assignment of Prerequisite/Home projects.",
                ],
            },
            {
                "session_number": 2,
                "title": f"Session 2: Hands-On EDGE Skill Stations & Practical {clean_badge} Demonstrations",
                "duration_minutes": 45,
                "focus_requirements": hands_on_ids,
                "edge_method_focus": "Demonstrate & Guide",
                "slide_range": "Hands-On Skill Station & Worked Example Slides",
                "activities": [
                    f"00–10 min: Counselor physical demonstration of key {clean_badge} procedures and equipment inspection.",
                    f"10–35 min: Patrol Buddy-Pair Hands-On Skill Stations covering Requirements ({hands_on_ids}).",
                    "35–45 min: Individual Scout skill verification and immediate coaching feedback.",
                ],
            },
            {
                "session_number": 3,
                "title": f"Session 3: Field/Prerequisite Review, Local {loc['state_code']} Applications & Blue Card Sign-Off",
                "duration_minutes": 45,
                "focus_requirements": prereq_ids,
                "edge_method_focus": "Guide & Enable",
                "slide_range": "Prerequisite, Quiz & Sources Slides",
                "activities": [
                    f"00–15 min: Review completed Campout, Field, and Home Prerequisite logs ({prereq_ids}).",
                    f"15–30 min: Connect {clean_badge} to local field sites ({loc['field_site_examples']}) and {loc['nws_office']} / {loc['state_agency']}.",
                    "30–45 min: Individual Blue Card / Scoutbook verification and counselor sign-off.",
                ],
            },
        ]

    if postponed_session_idx is not None and 1 <= int(postponed_session_idx) <= len(sessions):
        p_idx = int(postponed_session_idx)
        shifted_sessions: List[Dict[str, Any]] = []
        for idx_s, s_item in enumerate(sessions, start=1):
            s_copy = dict(s_item)
            if idx_s < p_idx:
                shifted_sessions.append(s_copy)
            elif idx_s == p_idx:
                shifted_sessions.append(
                    {
                        "session_number": p_idx,
                        "badge_focus": s_copy.get("badge_focus", clean_badge),
                        "title": f"Session {p_idx} (POSTPONED / WEATHER SNOW DAY): Shifted to Session {p_idx + 1}..Make-Up Day",
                        "duration_minutes": 0,
                        "focus_requirements": s_copy.get("focus_requirements", ""),
                        "edge_method_focus": "Postponed (Snow Day Shift Active)",
                        "slide_range": s_copy.get("slide_range", ""),
                        "is_postponed": True,
                        "activities": [
                            f"Weather / Facility Cancellation: All curriculum blocks from Session {p_idx} ({s_copy.get('focus_requirements', '')}) shift forward one slot into Session {p_idx + 1} through Make-Up Day without losing requirement coverage."
                        ],
                    }
                )
                s_shifted = dict(s_copy)
                s_shifted["session_number"] = p_idx + 1
                s_shifted["title"] = f"[Shifted from Session {p_idx}] " + str(s_copy.get("title", ""))
                s_shifted["shifted_from_session"] = p_idx
                shifted_sessions.append(s_shifted)
            else:
                if not s_copy.get("is_makeup_session"):
                    s_copy["session_number"] = idx_s + 1
                    s_copy["title"] = f"[Shifted to Slot {idx_s + 1} / Make-Up Day] " + str(s_copy.get("title", ""))
                    s_copy["shifted_from_session"] = idx_s
                    shifted_sessions.append(s_copy)
        sessions = shifted_sessions

    norm_c = _extract_normalized_counselor_fields(c_info)
    eff_section = str(section_label or norm_c["section_label"] or "").strip()
    eff_bundle = str(bundle_tag or norm_c["bundle_tag"] or "").strip()
    eff_time = str(class_start_time or norm_c["class_start_time"] or "").strip()
    eff_room = str(room_location or norm_c["room_location"] or "").strip()
    eff_dates = list(session_dates_list or session_dates or norm_c["session_dates_list"] or [])

    md_lines = [
        f"# {clean_badge}" + (f" + {companion_clean}" if companion_clean else "") + f" Merit Badge - Counselor Session Pacing Plan ({opt_label})",
        f"**Schedule Format:** {schedule_format} • **Option Track:** {opt_label}  ",
        f"**Local Field Context:** {loc['display_location']} • {loc['nws_office']}  ",
        f"**Primary Reference:** Official Scouting America *{clean_badge}* Merit Badge Pamphlet",
    ]
    meta_parts: List[str] = []
    if eff_section:
        meta_parts.append(f"**Section:** {eff_section}")
    if eff_bundle:
        meta_parts.append(f"**Event / Tag:** {eff_bundle}")
    if eff_room:
        meta_parts.append(f"**Room / Location:** {eff_room}")
    if eff_time:
        meta_parts.append(f"**Start Time:** {eff_time}")
    if eff_dates:
        meta_parts.append(f"**Session Dates:** {' | '.join(str(d) for d in eff_dates)}")
    if meta_parts:
        md_lines.append(" • ".join(meta_parts) + "  ")
    md_lines.append("")
    if postponed_session_idx:
        md_lines.append(f"> **Snow-Day Make-Up Shift Active:** Session {postponed_session_idx} was postponed; subsequent sessions automatically shifted into Make-Up Day.")
        md_lines.append("")
    for s in sessions:
        slide_rng = f" • {s['slide_range']}" if s.get("slide_range") else ""
        md_lines.append(f"## {s['title']} ({s['duration_minutes']} min • EDGE: {s['edge_method_focus']}{slide_rng})")
        for act in s["activities"]:
            md_lines.append(f"- {act}")
        md_lines.append("")

    return {
        "badge_name": clean_badge,
        "companion_badge_name": companion_clean or None,
        "option_track": opt_norm,
        "option_track_label": opt_label,
        "postponed_session_idx": postponed_session_idx,
        "schedule_format": schedule_format,
        "section_label": eff_section or None,
        "bundle_tag": eff_bundle or None,
        "room_location": eff_room or None,
        "class_start_time": eff_time or None,
        "session_dates_list": eff_dates,
        "resolved_location": loc,
        "sessions": sessions,
        "agenda_markdown": "\n".join(md_lines),
        "status": "SUCCESS",
    }


generate_session_agenda = generate_counselor_session_agenda


def generate_prerequisite_parent_letter(
    badge_name: str,
    research_result: Optional[Dict[str, Any]] = None,
    counselor_info: Optional[Dict[str, Any]] = None,
    stage: str = "stage_1_welcome_cpp",
    option_track: str = "ALL",
) -> Dict[str, Any]:
    """Generates a copy-pasteable email/letter to Scouts and parents detailing prerequisites and YPT rules.

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge (or a `PrerequisiteParentLetterRequest` instance).
        research_result: Serialized `MeritBadgeResearchResult` dictionary containing `requirements`.
        counselor_info: Optional dictionary with `counselor_name`, `troop_affiliation`,
            `location_or_zip`, `email_address`, and `phone_number`.
        stage: Optional active communication stage (`stage_1_welcome_cpp`, `stage_2_mid_clinic_alert`, `stage_3_final_packet`).
        option_track: Optional Merit Badge Option Track (`A`, `B`, `ALL`, etc.).

    Returns:
        Dict[str, Any]: Dictionary containing `badge_name`, `subject`, `subject_line`, `letter_markdown`,
        `stages`, `prerequisite_count`, and `status` (or a `GuidedToolError` dictionary on invalid input).
    """
    if isinstance(badge_name, PrerequisiteParentLetterRequest):
        req_obj = badge_name
        badge_name = req_obj.badge_name
        if getattr(req_obj, "option_track", None):
            option_track = req_obj.option_track
        counselor_info = counselor_info or {
            "counselor_name": req_obj.counselor_name,
            "troop_affiliation": req_obj.troop_affiliation,
            "location_or_zip": req_obj.location_or_zip or req_obj.session_dates_or_location,
            "email_address": req_obj.counselor_email,
            "phone_number": req_obj.phone_number,
        }
        if req_obj.research_result is not None:
            research_result = req_obj.research_result

    if not badge_name or not str(badge_name).strip():
        return build_guided_tool_error(
            error_code="EMPTY_BADGE_NAME",
            message="badge_name cannot be empty when generating a prerequisite parent letter.",
            remediation="Provide a valid Scouts BSA Merit Badge name such as 'Weather' or 'First Aid'.",
        )
    if research_result is None:
        from src.tools.scouting_scraper import MeritBadgeResearchRequest, fetch_merit_badge_pamphlet_pdf

        research_result = fetch_merit_badge_pamphlet_pdf(
            MeritBadgeResearchRequest(badge_name=str(badge_name).strip(), option_track=option_track)
        )
    if not isinstance(research_result, dict):
        return build_guided_tool_error(
            error_code="INVALID_RESEARCH_RESULT",
            message="research_result must be a dictionary containing Merit Badge requirements.",
            remediation="Call fetch_merit_badge_pamphlet_pdf first and pass its output dictionary.",
        )

    clean_badge = str(research_result.get("badge_name") or badge_name).strip()
    norm_c = _extract_normalized_counselor_fields(
        counselor_info,
        default_name="Scoutmaster Bob",
        default_troop="Troop 19, Middleton MA",
        default_email="counselor@troop123.org",
    )
    c_name = norm_c["c_name"]
    c_troop = norm_c["c_troop"]
    c_loc_raw = norm_c["c_loc_raw"]
    c_email = norm_c["c_email"]
    c_phone = norm_c["c_phone"]
    session_tag = norm_c["session_tag"]
    room_loc = norm_c["room_location"] or "Main Clinic Room / Troop Hall"
    start_time = norm_c["class_start_time"]
    dates_list = norm_c["session_dates_list"]
    pamphlet_url = str(
        research_result.get("pamphlet_pdf_url")
        or research_result.get("pamphlet_url")
        or "https://www.scouting.org/skills/merit-badges/"
    )
    loc = resolve_counselor_location(troop_affiliation=c_troop, location_or_zip=c_loc_raw)

    raw_reqs: List[Dict[str, Any]] = list(research_result.get("requirements") or [])
    opt_norm, opt_label, reqs = _resolve_option_track_and_filter_reqs(clean_badge, raw_reqs, option_track=option_track)
    prereqs = [
        r for r in reqs
        if str(r.get("execution_mode", "")).upper() == "PREREQUISITE_CAMPOUT_HOME"
        or r.get("syllabus_bucket") == "Pre-Class Prerequisite"
    ]
    in_class_reqs = [
        r for r in reqs
        if r.get("syllabus_bucket") in ("In-Class Concept", "In-Class Demonstration")
        or str(r.get("execution_mode", "")).upper() in ("IN_CLASS_DISCUSSION", "HANDS_ON_SKILL_STATION")
    ]
    homework_makeup_reqs = [
        r for r in reqs
        if r.get("syllabus_bucket") in ("Between-Session Homework", "Make-Up Eligible")
        or str(r.get("execution_mode", "")).upper() == "HANDS_ON_SKILL_STATION"
    ]
    followup_reqs = [
        r for r in reqs
        if r.get("syllabus_bucket") == "Post-Class Home-Troop Follow-Up"
        or str(r.get("execution_mode", "")).upper() == "PREREQUISITE_CAMPOUT_HOME"
    ]

    prereq_bullets: List[str] = []
    for r in prereqs:
        prereq_bullets.append(f"- **Requirement {r.get('req_number')}**: {r.get('req_text')}")
    if not prereq_bullets:
        prereq_bullets.append(
            f"- Review Chapter 1 of the official *{clean_badge}* Merit Badge Pamphlet and bring your Scout Workbook to Session 1."
        )

    homework_bullets: List[str] = []
    for r in homework_makeup_reqs[:6]:
        homework_bullets.append(
            f"- **Requirement {r.get('req_number')} ({r.get('syllabus_bucket', 'Hands-On / Make-Up Eligible')})**: {r.get('topic_title') or r.get('req_text')}"
        )
    if not homework_bullets:
        homework_bullets.append(
            f"- Practice the hands-on {clean_badge} skill stations demonstrated in class and prepare any missed discussion topics for Make-Up Day."
        )

    in_class_ids_str = ", ".join(str(r.get("req_number")) for r in in_class_reqs[:10]) or "1, 2, 3"
    followup_bullets: List[str] = []
    for r in followup_reqs[:6]:
        followup_bullets.append(
            f"- **Requirement {r.get('req_number')} (Post-Class Home-Troop Follow-Up)**: {r.get('req_text')}"
        )
    if not followup_bullets:
        followup_bullets.append(
            "- Complete any remaining field or campout logs with your home Troop and schedule a quick verification check to convert your Partial Blue Card (#34124) to a full completion."
        )

    opt_suffix = f" [Option Track: {opt_label}]" if opt_norm != "ALL" else ""
    tag_suffix = f" ({session_tag})" if session_tag else ""
    sig_troop_line = f"Merit Badge Counselor • {c_troop}  " if c_troop else "Merit Badge Counselor  "
    schedule_summary = " | ".join(dates_list) if dates_list else "Sessions 1–4 + Make-Up Day"
    if start_time:
        schedule_summary += f" ({start_time})"

    subject_1 = f"Scouts BSA {clean_badge} Merit Badge: Pre-Class Welcome & Prerequisite Guide{opt_suffix}{tag_suffix}"
    stage1_md = "\n".join(
        [
            f"**Subject:** {subject_1}",
            f"**Option Track:** {opt_label}",
            "",
            f"Dear {clean_badge} Merit Badge Scouts, Parents/Guardians, and Unit Leaders,",
            "",
            f"Welcome to the **{clean_badge} Merit Badge** clinic! Because Scouts in our sessions often join us from several different troops across the district and council, please review the following class schedule and preparation checklist before Session 1:",
            "",
            "### 1. Schedule, Venue & Official Pamphlet Reference",
            f"- **Session Schedule & Room:** {schedule_summary} • {room_loc}",
            f"- **Option Track:** {opt_label}",
            f"- **Official Scouting America {clean_badge} Merit Badge Pamphlet:** {pamphlet_url}",
            f"- **Local Field & Weather Context ({loc['display_location']}):** {loc['nws_office']} ({loc['nws_url']}) • {loc['field_site_examples']}",
            "",
            "### 2. Pre-Class Prerequisite Checklist",
            *prereq_bullets,
            "",
            "### 3. What to Bring to Session 1",
            "- **Signed Application for Merit Badge (Blue Card #34124)** with your Unit Leader's pre-approval signature (or active Scoutbook Plus connection).",
            f"- **Fillable Form (GTA §7.0.3.2) {clean_badge} Scout Workbook** (optional study aid for organizing your notes) and a pen/pencil.",
            "",
            "### 4. Scouting America Youth Protection (YPT) Two-Deep Policy",
            "- In accordance with Scouting America's *Guide to Safe Scouting*, **all email/digital communications between Scouts and Merit Badge Counselors must copy a parent/guardian or second registered adult leader**, and all sessions follow Two-Deep Leadership and the Buddy System.",
            "",
            "Yours in Scouting,",
            f"**{c_name}**  ",
            sig_troop_line,
            f"Email: {c_email} | Phone: {c_phone}",
        ]
    )

    subject_2 = f"Scouts BSA {clean_badge} Merit Badge: Mid-Session Progress, Homework & Make-Up Alert{opt_suffix}{tag_suffix}"
    stage2_md = "\n".join(
        [
            f"**Subject:** {subject_2}",
            f"**Option Track:** {opt_label}",
            "",
            f"Dear {clean_badge} Merit Badge Scouts, Parents/Guardians, and Unit Advancement Chairs,",
            "",
            f"Thank you for the outstanding energy in our **{clean_badge} Merit Badge** sessions so far! As we move through our midpoint hands-on stations toward Make-Up Day, please review our progress summary and homework reminders below:",
            "",
            "### 1. In-Class Requirements Covered vs. Hands-On Stations",
            f"- **Core In-Class Requirements Reviewed ({opt_label}):** Requirements {in_class_ids_str}",
            f"- **Venue & Schedule Check:** {schedule_summary} • {room_loc}",
            "",
            "### 2. Between-Session Homework & Make-Up Eligible Items",
            *homework_bullets,
            "",
            "### 3. Upcoming Make-Up Session Reminder & YPT Notice",
            "- Scouts who missed an earlier session block or need to finish a hands-on EDGE skill demonstration should bring their Fillable Form (GTA §7.0.3.2) notes and prerequisite logs to our scheduled Make-Up session.",
            "- **YPT Two-Deep Reminder:** Always copy (CC) a parent/guardian or unit leader on any email or digital message sent to your Merit Badge Counselor.",
            "",
            "Yours in Scouting,",
            f"**{c_name}**  ",
            sig_troop_line,
            f"Email: {c_email} | Phone: {c_phone}",
        ]
    )

    subject_3 = f"Scouts BSA {clean_badge} Merit Badge: Final Completion, Blue Card (#34124) Sign-Off & Partial Transfer Guide{opt_suffix}{tag_suffix}"
    stage3_md = "\n".join(
        [
            f"**Subject:** {subject_3}",
            f"**Option Track:** {opt_label}",
            "",
            f"Dear {clean_badge} Merit Badge Scouts, Parents/Guardians, Scoutmasters, and Advancement Chairs,",
            "",
            f"Congratulations to all Scouts on completing our **{clean_badge} Merit Badge** clinic! Below is the final summary of completed requirements, home-troop follow-up items, and Blue Card (#34124) / Scoutbook Plus advancement instructions:",
            "",
            "### 1. In-Class Completed Requirements vs. Post-Class Home-Troop Follow-Up",
            f"- **In-Class Completed & Verified Requirements ({opt_label}):** Requirements {in_class_ids_str}",
            "- **Post-Class Home-Troop Follow-Up / Campout Log Items:**",
            *followup_bullets,
            "",
            "### 2. Blue Card (#34124) 3-Part Record & Scoutbook Plus CSV Import Guide",
            "- **Part 1 (Application for Merit Badge) & Part 2 (Applicant's Record):** Return the signed Blue Card (#34124) to your Unit Leader / Troop Advancement Chair so your troop can record completed requirements and retain the Applicant's Record.",
            "- **Part 3 (Counselor's Record):** Retained by the Merit Badge Counselor for council advancement verification.",
            "- **Scoutbook Plus CSV Import:** Unit Advancement Chairs may directly import the attached per-troop Scoutbook CSV advancement file or follow up anytime when remaining partial requirements are ready for final sign-off.",
            "",
            "### 3. Scouting America Youth Protection (YPT) Reminder",
            "- When emailing photos, campout logs, or follow-up questions to complete a Partial Blue Card, always copy (CC) a parent/guardian or registered unit leader per Scouting America Two-Deep digital communication policy.",
            "",
            "Yours in Scouting,",
            f"**{c_name}**  ",
            sig_troop_line,
            f"Email: {c_email} | Phone: {c_phone}",
        ]
    )

    stages_map = {
        "stage_1_welcome_cpp": {
            "title": "Stage 1: Pre-Class Welcome & Prerequisite Checklist",
            "subject": subject_1,
            "markdown": stage1_md,
        },
        "stage_2_mid_clinic_alert": {
            "title": "Stage 2: Mid-Session Progress, Homework & Make-Up Alert",
            "subject": subject_2,
            "markdown": stage2_md,
        },
        "stage_3_final_packet": {
            "title": "Stage 3: Final Completion, Blue Card (#34124) Sign-Off & Partial Transfer Guide",
            "subject": subject_3,
            "markdown": stage3_md,
        },
    }

    stage_norm = str(stage or "stage_1_welcome_cpp").strip().lower()
    if "2" in stage_norm or "mid" in stage_norm:
        active_stage = stages_map["stage_2_mid_clinic_alert"]
    elif "3" in stage_norm or "final" in stage_norm or "post" in stage_norm:
        active_stage = stages_map["stage_3_final_packet"]
    else:
        active_stage = stages_map["stage_1_welcome_cpp"]

    return {
        "badge_name": clean_badge,
        "option_track": opt_norm,
        "option_track_label": opt_label,
        "subject": active_stage["subject"],
        "subject_line": active_stage["subject"],
        "prerequisite_count": len(prereqs),
        "resolved_location": loc,
        "letter_markdown": active_stage["markdown"],
        "stages": stages_map,
        "status": "SUCCESS",
    }


generate_parent_prerequisite_letter = generate_prerequisite_parent_letter


def generate_class_preparation_page_cpp(
    badge_name: str,
    counselor_info: Optional[Dict[str, Any]] = None,
    session_dates: Optional[List[str]] = None,
    room_location: str = "",
    option_track: str = "ALL",
) -> Dict[str, Any]:
    """Generates the 1-Page Pre-Class Scout & Parent Handout ('Class Preparation Page / CPP') in HTML and Markdown.

    Contains 5 structured sections:
    1. Counselor & Schedule Banner (Counselor name, troop, YPT two-deep email, session dates, room).
    2. Starting Requirement Gate Alert (Prerequisite badge, swim test, counselor pre-approval, or parent consent).
    3. Do Before Session 1 (Pre-Class Prerequisites) Checklist.
    4. What to Bring to Every Session (Pamphlet, Fillable Workbook, Blue Card #34124, field gear).
    5. What We Will Complete Together in Class (In-Class Concept & Demonstration syllabus summary).
    """
    import html as _html
    from src.tools.scouting_scraper import MeritBadgeResearchRequest, fetch_merit_badge_pamphlet_pdf

    res = fetch_merit_badge_pamphlet_pdf(
        MeritBadgeResearchRequest(badge_name=badge_name, option_track=option_track)
    )
    if res.get("status") == "ERROR":
        return res

    resolved_badge = str(res.get("badge_name") or badge_name)
    raw_reqs = list(res.get("requirements") or [])
    opt_norm, opt_label, reqs = _resolve_option_track_and_filter_reqs(resolved_badge, raw_reqs, option_track=option_track)
    c_info = counselor_info or {}
    c_name = str(c_info.get("counselor_name") or "Merit Badge Counselor")
    c_troop = str(c_info.get("troop_affiliation") or "Troop 19, Northeast Massachusetts Council")
    c_email = str(c_info.get("email_address") or "counselor@scouting.org")
    dates = list(session_dates or ["Session 1", "Session 2", "Session 3", "Session 4", "Make-Up Day"])
    room = str(room_location or "Main Clinic Room / Troop Hall")

    prereq_reqs = [
        r for r in reqs
        if r.get("syllabus_bucket") in ("Pre-Class Prerequisite", "Post-Class Home-Troop Follow-Up")
        or r.get("execution_mode") == "PREREQUISITE_CAMPOUT_HOME"
    ]
    in_class_reqs = [r for r in reqs if r not in prereq_reqs]
    gates = [
        r.get("starting_requirement_gate")
        for r in reqs
        if isinstance(r.get("starting_requirement_gate"), dict) and r.get("starting_requirement_gate", {}).get("gate_label")
    ]

    bring_items = [
        f"Official Scouting America {resolved_badge} Merit Badge Pamphlet (PDF or print)",
        f"Fillable Form (GTA §7.0.3.2) {resolved_badge} Scout Workbook (printed or tablet)",
        "Application for Merit Badge (Blue Card #34124) signed by your Unit Leader, or active Scoutbook connection",
        "Notebook, pen/pencil, and any completed Pre-Class Prerequisite evidence logs/photos",
    ]
    for r in reqs[:3]:
        for g_item in (r.get("gear_checklist") or [])[:1]:
            if g_item not in bring_items and len(bring_items) < 6:
                bring_items.append(str(g_item))

    from src.agents.planner import _format_starting_gate_label

    md_lines = [
        f"# {resolved_badge} Merit Badge - 1-Page Class Preparation Page (CPP)",
        f"**Counselor:** {c_name} ({c_troop}) • **YPT Contact:** {c_email} (always CC a parent/guardian or unit leader)",
        f"**Session Dates:** {' | '.join(dates)} • **Location:** {room} • **Option Track:** {opt_label}",
        "",
        "## 1. Starting Requirement Gate Alert",
    ]
    if gates:
        for g in gates:
            g_lbl = _format_starting_gate_label(g.get("gate_type"))
            md_lines.append(f"- **[{g_lbl}] {g.get('gate_label')}:** {g.get('gate_description')}")
    else:
        md_lines.append("- **Unit Leader Approval:** Obtain your Scoutmaster's signature on your Blue Card (#34124) before Session 1.")

    md_lines.extend(["", "## 2. Do Before Session 1 (Pre-Class Prerequisites & Home-Troop Items)"])
    if prereq_reqs:
        for pr in prereq_reqs:
            md_lines.append(
                f"- [ ] **Req {pr.get('req_number')} ({pr.get('syllabus_bucket', 'Prerequisite')}):** {pr.get('req_text')}"
            )
    else:
        md_lines.append(f"- [ ] Read the {resolved_badge} Merit Badge Pamphlet overview and review Requirement 1 hazards.")

    md_lines.extend(["", "## 3. What to Bring to Every Session"])
    for bi in bring_items:
        md_lines.append(f"- [ ] {bi}")

    md_lines.extend(["", "## 4. What We Will Complete Together in Class"])
    for ir in in_class_reqs:
        md_lines.append(
            f"- **Req {ir.get('req_number')} ({ir.get('syllabus_bucket', 'In-Class')}):** {ir.get('topic_title') or ir.get('req_text', '')}"
        )

    gates_html = "".join(
        f"<li><strong>[{_html.escape(_format_starting_gate_label(g.get('gate_type')))}] {_html.escape(str(g.get('gate_label')))}:</strong> {_html.escape(str(g.get('gate_description')))}</li>"
        for g in gates
    ) or "<li><strong>Unit Leader Approval:</strong> Obtain your Scoutmaster's signature on your Blue Card (#34124) before Session 1.</li>"

    prereq_html = "".join(
        f"<li><strong>Req {_html.escape(str(pr.get('req_number')))} ({_html.escape(str(pr.get('syllabus_bucket', 'Prerequisite')))}):</strong> {_html.escape(str(pr.get('req_text')))}</li>"
        for pr in prereq_reqs
    ) or f"<li>Read the {_html.escape(resolved_badge)} Merit Badge Pamphlet overview before Session 1.</li>"

    bring_html = "".join(f"<li>☐ {_html.escape(str(bi))}</li>" for bi in bring_items)
    in_class_html = "".join(
        f"<li><strong>Req {_html.escape(str(ir.get('req_number')))} ({_html.escape(str(ir.get('syllabus_bucket', 'In-Class')))}):</strong> {_html.escape(str(ir.get('topic_title') or ir.get('req_text', '')))}</li>"
        for ir in in_class_reqs
    )

    cpp_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{_html.escape(resolved_badge)} - 1-Page Class Preparation Page (CPP)</title>
  <style>
    body {{ font-family: 'Segoe UI', Roboto, Arial, sans-serif; color: #0f172a; margin: 18px; font-size: 12.5px; line-height: 1.4; }}
    .cpp-banner {{ background: #003f87; color: #fff; padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; }}
    .cpp-banner h1 {{ margin: 0 0 4px 0; font-size: 20px; }}
    .cpp-box {{ border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px 14px; margin-bottom: 10px; }}
    .cpp-box.gate {{ background: #fffbeb; border-color: #f59e0b; }}
    .cpp-box h2 {{ margin: 0 0 6px 0; font-size: 14px; color: #003f87; }}
    ul {{ margin: 4px 0; padding-left: 20px; }}
  </style>
</head>
<body>
  <div class="cpp-banner">
    <h1 style="display:flex;align-items:center;gap:8px;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2"><path d="M12 2L4 5v6c0 5.55 3.84 10.74 8 12 4.16-1.26 8-6.45 8-12V5l-8-3z"/></svg>{_html.escape(resolved_badge)} Merit Badge - 1-Page Class Preparation Page (CPP)</h1>
    <div><strong>Counselor:</strong> {_html.escape(c_name)} ({_html.escape(c_troop)}) • <strong>YPT Email:</strong> {_html.escape(c_email)}</div>
    <div><strong>Schedule:</strong> {_html.escape(" | ".join(dates))} • <strong>Room:</strong> {_html.escape(room)} • <strong>Option Track:</strong> {_html.escape(opt_label)}</div>
  </div>
  <div class="cpp-box gate">
    <h2>1. Starting Requirement Gate Alert</h2>
    <ul>{gates_html}</ul>
  </div>
  <div class="cpp-box">
    <h2>2. Do Before Session 1 (Pre-Class Prerequisites &amp; Home-Troop Items)</h2>
    <ul>{prereq_html}</ul>
  </div>
  <div class="cpp-box">
    <h2>3. What to Bring to Every Session</h2>
    <ul style="list-style:none; padding-left:4px;">{bring_html}</ul>
  </div>
  <div class="cpp-box">
    <h2>4. What We Will Complete Together in Class</h2>
    <ul>{in_class_html}</ul>
  </div>
</body>
</html>"""

    return {
        "status": "SUCCESS",
        "badge_name": resolved_badge,
        "option_track": opt_norm,
        "option_track_label": opt_label,
        "prerequisite_count": len(prereq_reqs),
        "in_class_count": len(in_class_reqs),
        "starting_gates": gates,
        "what_to_bring": bring_items,
        "prereq_reqs": prereq_reqs,
        "in_class_reqs": in_class_reqs,
        "cpp_markdown": "\n".join(md_lines),
        "cpp_html": cpp_html,
        "html_document": cpp_html,
    }


def generate_organizer_syllabus_spec_sheet(
    badge_name: str,
    counselor_info: Optional[Dict[str, Any]] = None,
    session_mode: str = "4_session_mbc",
    max_scouts: int = 16,
    min_age_or_rank: str = "All Scouts (Ages 11-17)",
    room_needs: str = "Projector/TV + Tables for Buddy Stations",
    option_track: str = "ALL",
) -> Dict[str, Any]:
    """Generates a 1-Page Event Organizer Catalog & Schedule Spec Sheet for Merit Badge University/College chairs."""
    from src.agents.planner import _format_session_mode_label
    from src.tools.scouting_scraper import MeritBadgeResearchRequest, fetch_merit_badge_pamphlet_pdf

    res = fetch_merit_badge_pamphlet_pdf(
        MeritBadgeResearchRequest(badge_name=badge_name, option_track=option_track)
    )
    if res.get("status") == "ERROR":
        return res
    resolved_badge = str(res.get("badge_name") or badge_name)
    raw_reqs = list(res.get("requirements") or [])
    opt_norm, opt_label, reqs = _resolve_option_track_and_filter_reqs(resolved_badge, raw_reqs, option_track=option_track)
    c_info = counselor_info or {}
    c_name = str(c_info.get("counselor_name") or "Merit Badge Counselor")
    c_troop = str(c_info.get("troop_affiliation") or "Troop 19, Northeast Massachusetts Council")

    prereq_ids = [str(r.get("req_number")) for r in reqs if r.get("syllabus_bucket") == "Pre-Class Prerequisite"]
    in_class_ids = [str(r.get("req_number")) for r in reqs if r.get("syllabus_bucket") in ("In-Class Concept", "In-Class Demonstration")]
    makeup_ids = [str(r.get("req_number")) for r in reqs if r.get("syllabus_bucket") == "Make-Up Eligible"]
    followup_ids = [str(r.get("req_number")) for r in reqs if r.get("syllabus_bucket") == "Post-Class Home-Troop Follow-Up"]

    catalog_blurb = (
        f"Scouts will explore the official {resolved_badge} Merit Badge through interactive visual briefings, "
        f"hands-on EDGE skill stations, and Socratic patrol scenarios. "
        f"Prerequisites: {', '.join(prereq_ids) if prereq_ids else 'None (read pamphlet Chapter 1)'}."
    )
    session_mode_label = _format_session_mode_label(session_mode)
    spec_md = "\n".join([
        f"# {resolved_badge} Merit Badge - Event Organizer Catalog & Schedule Spec Sheet",
        f"- **Instructor / Counselor:** {c_name} ({c_troop})",
        f"- **Option Track:** {opt_label}",
        f"- **Eagle-Required:** {'Yes' if res.get('is_eagle_required') else 'No'}",
        f"- **Session Format:** {session_mode_label} • **Recommended Class Cap:** {max_scouts} Scouts",
        f"- **Recommended Age / Rank:** {min_age_or_rank}",
        f"- **Room & AV Requirements:** {room_needs}",
        f"- **Pre-Class Prerequisites:** {', '.join(prereq_ids) if prereq_ids else 'None'}",
        f"- **In-Class Completed Requirements:** {', '.join(in_class_ids) if in_class_ids else 'All core requirements'}",
        f"- **Make-Up Day Eligible Requirements:** {', '.join(makeup_ids) if makeup_ids else 'Any missed concept review'}",
        f"- **Post-Class Home-Troop Follow-Up:** {', '.join(followup_ids) if followup_ids else 'None'}",
        "",
        "### Course Catalog Description (Copy-Paste Ready for Event Website)",
        catalog_blurb,
    ])
    return {
        "status": "SUCCESS",
        "badge_name": resolved_badge,
        "option_track": opt_norm,
        "option_track_label": opt_label,
        "session_mode": session_mode,
        "max_scouts": max_scouts,
        "min_age_or_rank": min_age_or_rank,
        "room_needs": room_needs,
        "catalog_blurb": catalog_blurb,
        "prerequisite_reqs": prereq_ids,
        "in_class_reqs": in_class_ids,
        "makeup_reqs": makeup_ids,
        "followup_reqs": followup_ids,
        "spec_sheet_markdown": spec_md,
    }


def generate_three_stage_ypt_communication_pack(
    badge_name: str,
    counselor_info: Optional[Dict[str, Any]] = None,
    session_dates: Optional[List[str]] = None,
    room_location: str = "",
    absent_scouts_summary: Optional[List[Dict[str, Any]]] = None,
    troop_filter: str = "ALL",
    option_track: str = "ALL",
) -> Dict[str, Any]:
    """Generates the 3-Stage YPT Two-Deep Communication Pack:
    - Stage 1: 7-Day Pre-Class Welcome + 1-Page CPP + Fillable Workbook
    - Stage 2: Mid-Clinic Absentee & Make-Up Day Alert (auto-populated from S1..S4 attendance)
    - Stage 3: Post-Clinic Smart Partial & Blue Card Summary (grouped by Troop)
    Every stage includes the mandatory Scouting America YPT Two-Deep CC header.
    """
    from src.tools.scouting_scraper import MeritBadgeResearchRequest, fetch_merit_badge_pamphlet_pdf

    res = fetch_merit_badge_pamphlet_pdf(
        MeritBadgeResearchRequest(badge_name=badge_name, option_track=option_track)
    )
    if res.get("status") == "ERROR":
        return res
    resolved_badge = str(res.get("badge_name") or badge_name)
    raw_reqs = list(res.get("requirements") or [])
    opt_norm, opt_label, reqs = _resolve_option_track_and_filter_reqs(resolved_badge, raw_reqs, option_track=option_track)
    norm_c = _extract_normalized_counselor_fields(
        counselor_info,
        default_name="Merit Badge Counselor",
        default_troop="Troop 19, Northeast Massachusetts Council",
        default_email="counselor@scouting.org",
    )
    c_name = norm_c["c_name"]
    c_troop = norm_c["c_troop"]
    c_email = norm_c["c_email"]
    dates = list(session_dates or norm_c["session_dates_list"] or ["Session 1", "Session 2", "Session 3", "Session 4", "Make-Up Day"])
    room = str(room_location or norm_c["room_location"] or "Main Clinic Room")

    ypt_header = "[MANDATORY YPT CC: Unit Leader & Parent/Guardian - Required per Scouting America Youth Protection Policy]"
    prereq_ids = ", ".join(str(r.get("req_number")) for r in reqs if r.get("syllabus_bucket") == "Pre-Class Prerequisite") or "Pamphlet Chapter 1"
    makeup_ids = ", ".join(str(r.get("req_number")) for r in reqs if r.get("syllabus_bucket") == "Make-Up Eligible") or "Missed session topics"
    followup_ids = ", ".join(str(r.get("req_number")) for r in reqs if r.get("syllabus_bucket") == "Post-Class Home-Troop Follow-Up") or "Home-troop logs"
    sig_troop_line = f"Merit Badge Counselor • {c_troop}  " if c_troop else "Merit Badge Counselor  "
    opt_suffix = f" [Option Track: {opt_label}]" if opt_norm != "ALL" else ""

    subj_1 = f"Scouts BSA {resolved_badge} Merit Badge: Pre-Class Welcome & Prerequisite Guide{opt_suffix} ({' | '.join(dates[:2])})"
    stage1_md = "\n".join([
        ypt_header,
        f"**Subject:** {subj_1}",
        f"**Option Track:** {opt_label}",
        "",
        f"Dear {resolved_badge} Merit Badge Scouts, Parents/Guardians, and Unit Leaders,",
        "",
        f"Welcome to our upcoming **{resolved_badge} Merit Badge** class ({opt_label}) in **{room}**! Attached are your **1-Page Class Preparation Page (CPP)** and **Fillable Form (GTA §7.0.3.2) Scout Workbook**.",
        f"- **Pre-Class Prerequisites to Prepare Before Session 1:** Requirements {prereq_ids}",
        "- **What to Bring:** Signed Blue Card (#34124), official pamphlet, and your workbook (optional study aid per GTA §7.0.3.2).",
        "",
        "Yours in Scouting,",
        f"**{c_name}**  ",
        sig_troop_line,
        f"Email: {c_email}",
    ])

    abs_lines = []
    for sc in absent_scouts_summary or []:
        abs_lines.append(
            f"- **{sc.get('scout_name', 'Scout')} ({sc.get('troop_number', 'Troop')}):** Missed {sc.get('missed_sessions', 'Session')} -> Actionable Make-Up Reqs: {sc.get('actionable_makeup_reqs', makeup_ids)}"
        )
    if not abs_lines:
        abs_lines.append(f"- **Make-Up Day Eligible Requirements:** {makeup_ids} (for any Scout who missed an in-class session).")

    subj_2 = f"Scouts BSA {resolved_badge} Merit Badge: Mid-Session Progress, Homework & Make-Up Alert{opt_suffix} ({dates[-1]})"
    stage2_md = "\n".join([
        ypt_header,
        f"**Subject:** {subj_2}",
        f"**Option Track:** {opt_label}",
        "",
        f"Dear {resolved_badge} Merit Badge Scouts, Parents/Guardians, and Unit Advancement Chairs,",
        "",
        f"As we approach our **{dates[-1]}** session ({opt_label}) in **{room}**, here is the targeted Make-Up plan for Scouts who missed an earlier block:",
        *abs_lines,
        "",
        f"Please review the corresponding sections in the official {resolved_badge} Merit Badge Pamphlet and bring your notes to Make-Up Day.",
        "",
        "Yours in Scouting,",
        f"**{c_name}**  ",
        sig_troop_line,
        f"Email: {c_email}",
    ])

    subj_3 = f"Scouts BSA {resolved_badge} Merit Badge: Final Completion, Blue Card (#34124) Sign-Off & Partial Transfer Guide{opt_suffix}"
    stage3_md = "\n".join([
        ypt_header,
        f"**Subject:** {subj_3}",
        f"**Option Track:** {opt_label}",
        "",
        f"Dear {resolved_badge} Merit Badge Scouts, Parents/Guardians, Scoutmasters, and Advancement Chairs,",
        "",
        f"Thank you for a great **{resolved_badge} Merit Badge** clinic ({opt_label})! Attached is the **Per-Troop Blue Card (#34124) & Scoutbook CSV Packet**.",
        f"- **Actionable Make-Up Partial Requirements (can be finished with counselor anytime):** {makeup_ids}",
        f"- **Expected Home-Troop Follow-Up Requirements (campouts, long-term logs, or troop service):** {followup_ids}",
        "",
        "Yours in Scouting,",
        f"**{c_name}**  ",
        sig_troop_line,
        f"Email: {c_email}",
    ])

    s1_obj = {
        "title": "Stage 1: 7-Day Pre-Class Welcome + CPP + Workbook",
        "subject": subj_1,
        "markdown": stage1_md,
    }
    s2_obj = {
        "title": "Stage 2: Mid-Clinic Absentee & Make-Up Day Alert",
        "subject": subj_2,
        "markdown": stage2_md,
    }
    s3_obj = {
        "title": "Stage 3: Post-Clinic Smart Partial & Per-Troop Blue Card Summary",
        "subject": subj_3,
        "markdown": stage3_md,
    }

    return {
        "status": "SUCCESS",
        "badge_name": resolved_badge,
        "option_track": opt_norm,
        "option_track_label": opt_label,
        "ypt_mandatory_cc_header": ypt_header,
        "troop_filter": troop_filter,
        "stages": {
            "stage_1_pre_class": s1_obj,
            "stage_1_welcome_cpp": s1_obj,
            "stage_1": s1_obj,
            "stage_2_mid_clinic_makeup": s2_obj,
            "stage_2_mid_clinic_alert": s2_obj,
            "stage_2": s2_obj,
            "stage_3_post_clinic_partials": s3_obj,
            "stage_3_final_packet": s3_obj,
            "stage_3": s3_obj,
        },
    }


generate_ypt_3stage_communication_pack = generate_three_stage_ypt_communication_pack


def _sanitize_pdf_text(text: str) -> str:
    """Replaces Unicode symbols outside WinAnsiEncoding / Latin-1 with clean ASCII equivalents for Base-14 PDF fonts."""
    if not text:
        return ""
    replacements = (
        ("•", "-"),
        ("‣", "-"),
        ("▪", "-"),
        ("◦", "-"),
        ("●", "-"),
        ("☐", "[ ]"),
        ("☑", "[x]"),
        ("✓", "[x]"),
        ("✔", "[x]"),
        ("✅", "[x]"),
        ("\u2014", "-"),
        ("\u2013", "-"),
        ("−", "-"),
        ("“", '"'),
        ("”", '"'),
        ("‘", "'"),
        ("’", "'"),
        ("…", "..."),
        ("§", "Sec. "),
        ("→", "->"),
        ("\u00a0", " "),
    )
    out = str(text)
    for src, dst in replacements:
        out = out.replace(src, dst)
    out = out.encode("latin-1", errors="ignore").decode("latin-1")
    return "".join(ch for ch in out if ch == "\n" or ch == "\t" or 32 <= ord(ch) <= 255)


_PDF_WORD_WIDTH_CACHE: Dict[Tuple[str, float, str], float] = {}
_PDF_DIAGRAM_STREAM_CACHE: Dict[str, bytes] = {}
_WORKBOOK_PDF_LRU_CACHE: Dict[Tuple[str, str, str, str, str, bool], bytes] = {}
_COUNSELOR_PDF_LRU_CACHE: Dict[Tuple[str, str, str, str, str], bytes] = {}


def _measure_pdf_text_cached(text: str, fontname: str, fontsize: float) -> float:
    """Fast memoized wrapper around `fitz.get_text_length` to avoid redundant SWIG font-metric calls."""
    import fitz

    key = (fontname, round(float(fontsize), 2), text)
    cached = _PDF_WORD_WIDTH_CACHE.get(key)
    if cached is not None:
        return cached
    val = float(fitz.get_text_length(text, fontname=fontname, fontsize=fontsize))
    if len(_PDF_WORD_WIDTH_CACHE) < 60000:
        _PDF_WORD_WIDTH_CACHE[key] = val
    return val


def _wrap_pdf_lines(
    text: str,
    max_width: float,
    fontname: str = "helv",
    fontsize: float = 8.0,
) -> List[str]:
    """Word-wraps sanitized text using exact PyMuPDF font metrics so every line fits inside `max_width`."""
    clean = _sanitize_pdf_text(text)
    if not clean.strip():
        return []
    usable_width = max(40.0, float(max_width) - 4.0)
    space_w = _measure_pdf_text_cached(" ", fontname, fontsize)
    wrapped: List[str] = []
    for raw_para in clean.splitlines():
        para = raw_para.strip()
        if not para:
            wrapped.append("")
            continue
        words = para.split(" ")
        cur_line = ""
        cur_w = 0.0
        for word in words:
            if not word:
                continue
            word_w = _measure_pdf_text_cached(word, fontname, fontsize)
            # Break single ultra-long unbroken tokens (e.g. URLs) if needed
            if word_w > usable_width:
                if cur_line:
                    wrapped.append(cur_line)
                    cur_line = ""
                    cur_w = 0.0
                chunk = ""
                chunk_w = 0.0
                for ch in word:
                    ch_w = _measure_pdf_text_cached(ch, fontname, fontsize)
                    if chunk_w + ch_w <= usable_width:
                        chunk += ch
                        chunk_w += ch_w
                    else:
                        if chunk:
                            wrapped.append(chunk)
                        chunk = ch
                        chunk_w = ch_w
                cur_line = chunk
                cur_w = chunk_w
                continue
            if not cur_line:
                cur_line = word
                cur_w = word_w
            elif cur_w + space_w + word_w <= usable_width:
                cur_line = f"{cur_line} {word}"
                cur_w += space_w + word_w
            else:
                wrapped.append(cur_line)
                cur_line = word
                cur_w = word_w
        if cur_line:
            wrapped.append(cur_line)
    return wrapped


def _resolve_badge_emblem_path(badge_name: str) -> Optional[str]:
    """Resolves the local PNG path for the official Merit Badge patch emblem if available on disk."""
    from pathlib import Path
    from src.config import ASSETS_DIR, badge_file_slug, get_badge_cover_and_patch_paths

    slug = badge_file_slug(badge_name)
    emblems_dir = ASSETS_DIR / "badge_emblems"
    for cand in (
        emblems_dir / f"{slug}.png",
        emblems_dir / f"{slug}_patch.png",
    ):
        if cand.exists() and cand.stat().st_size > 200:
            return str(cand)
    try:
        paths = get_badge_cover_and_patch_paths(badge_name)
        patch_p = paths.get("patch_path")
        if patch_p and Path(str(patch_p)).exists():
            return str(patch_p)
    except Exception:
        pass
    return None


def _draw_branded_pdf_header(
    page: Any,
    badge_name: str,
    doc_title: str,
    subtitle_line: str,
    kicker_text: str = "SCOUTS BSA MERIT BADGE COUNSELOR WORKBENCH",
    is_eagle_required: bool = False,
) -> float:
    """Draws a graphically rich Scouting America Navy (#003F87) & Gold (#FDB913) header banner with embedded Merit Badge patch emblem.

    Returns the initial `y_cursor` below the banner.
    """
    import fitz

    # Outer Navy Banner Card + Top/Bottom Gold Accent Trim
    banner_rect = fitz.Rect(28.0, 20.0, 584.0, 80.0)
    page.draw_rect(banner_rect, color=(0.0, 0.247, 0.529), fill=(0.0, 0.247, 0.529))
    page.draw_rect(fitz.Rect(28.0, 20.0, 584.0, 24.5), color=(0.992, 0.725, 0.075), fill=(0.992, 0.725, 0.075))
    page.draw_rect(fitz.Rect(28.0, 77.5, 584.0, 80.0), color=(0.992, 0.725, 0.075), fill=(0.992, 0.725, 0.075))

    text_x0 = 38.0
    emblem_path = _resolve_badge_emblem_path(badge_name)
    if emblem_path:
        try:
            # Draw subtle gold-bordered emblem medallion on the left of the header banner
            page.draw_circle(
                fitz.Point(56.0, 51.0),
                21.5,
                color=(0.992, 0.725, 0.075),
                fill=(0.96, 0.98, 1.0),
                width=1.5,
            )
            page.insert_image(
                fitz.Rect(37.5, 32.5, 74.5, 69.5),
                filename=emblem_path,
                keep_proportion=True,
            )
            text_x0 = 84.0
        except Exception:
            text_x0 = 38.0

    eagle_tag = "  |  EAGLE-REQUIRED MERIT BADGE" if is_eagle_required else ""
    page.insert_text(
        fitz.Point(text_x0, 36.0),
        _sanitize_pdf_text(f"{kicker_text}{eagle_tag}"),
        fontsize=6.8,
        fontname="helv",
        color=(0.992, 0.78, 0.20),
    )
    page.insert_text(
        fitz.Point(text_x0, 53.0),
        _sanitize_pdf_text(doc_title),
        fontsize=12.0,
        fontname="helv",
        color=(1.0, 1.0, 1.0),
    )
    page.insert_text(
        fitz.Point(text_x0, 69.0),
        _sanitize_pdf_text(subtitle_line),
        fontsize=7.4,
        fontname="helv",
        color=(0.88, 0.94, 1.0),
    )
    return 86.0


def _finalize_branded_pdf_pages(
    doc: Any,
    badge_name: str,
    doc_short_title: str,
    footer_left_note: str = "Scouting America GTA Sec. 7.0.3.2 & Youth Protection (YPT) Compliant",
) -> None:
    """Adds a slim Navy/Gold running header to continuation pages (2..N) and a branded page footer ('Page X of Y') to all pages."""
    import fitz

    total_pages = len(doc)
    for page_idx, pg in enumerate(doc, start=1):
        if page_idx > 1:
            # Slim continuation header bar at top of page (above y=36 content start)
            pg.draw_rect(fitz.Rect(28.0, 14.0, 584.0, 29.0), color=(0.0, 0.247, 0.529), fill=(0.0, 0.247, 0.529))
            pg.draw_rect(fitz.Rect(28.0, 14.0, 584.0, 16.0), color=(0.992, 0.725, 0.075), fill=(0.992, 0.725, 0.075))
            pg.insert_text(
                fitz.Point(35.0, 24.5),
                _sanitize_pdf_text(f"{badge_name.upper()} MERIT BADGE  |  {doc_short_title}"),
                fontsize=7.0,
                fontname="helv",
                color=(1.0, 1.0, 1.0),
            )
            pg.insert_text(
                fitz.Point(515.0, 24.5),
                _sanitize_pdf_text(f"Cont. Page {page_idx}/{total_pages}"),
                fontsize=7.0,
                fontname="helv",
                color=(0.992, 0.78, 0.20),
            )

        # Bottom footer rule and Page X of Y badge (below max_y=752)
        pg.draw_line(
            fitz.Point(28.0, 760.0),
            fitz.Point(584.0, 760.0),
            color=(0.78, 0.83, 0.90),
            width=0.8,
        )
        pg.insert_text(
            fitz.Point(28.0, 772.0),
            _sanitize_pdf_text(f"Scouts BSA {badge_name} Merit Badge  |  {footer_left_note}"),
            fontsize=6.8,
            fontname="helv",
            color=(0.35, 0.42, 0.52),
        )
        pg.draw_rect(
            fitz.Rect(516.0, 763.0, 584.0, 776.0),
            color=(0.0, 0.247, 0.529),
            fill=(0.93, 0.96, 1.0),
        )
        pg.insert_text(
            fitz.Point(524.0, 772.0),
            _sanitize_pdf_text(f"Page {page_idx} of {total_pages}"),
            fontsize=7.0,
            fontname="helv",
            color=(0.0, 0.247, 0.529),
        )


def _insert_wrapped_pdf_text(
    doc: Any,
    page: Any,
    y_cursor: float,
    x0: float,
    x1: float,
    text: str,
    fontsize: float = 8.0,
    fontname: str = "helv",
    color: tuple[float, float, float] = (0.1, 0.14, 0.2),
    bg_fill: Optional[tuple[float, float, float]] = None,
    border_color: Optional[tuple[float, float, float]] = None,
    left_stripe_color: Optional[tuple[float, float, float]] = None,
    pad_x: float = 5.0,
    pad_y: float = 3.5,
    max_y: float = 752.0,
) -> tuple[Any, float]:
    """Renders wrapped multi-line text onto `page`, dynamically growing box height and paginating across pages so 0 text is ever dropped."""
    import fitz

    eff_pad_x = pad_x + (4.0 if left_stripe_color is not None else 0.0)
    lines = _wrap_pdf_lines(text, (x1 - x0) - 2.0 * eff_pad_x, fontname=fontname, fontsize=fontsize)
    if not lines:
        return page, y_cursor

    line_h = max(10.0, fontsize * 1.32)
    total_h = len(lines) * line_h + 2.0 * pad_y
    page_usable_h = max_y - 36.0

    # If the block fits on a single page cleanly but overflows the remaining space on the current page, start a new page first
    if total_h <= page_usable_h and (y_cursor + total_h > max_y):
        page = doc.new_page(width=612, height=792)
        y_cursor = 36.0

    idx = 0
    total_lines = len(lines)
    while idx < total_lines:
        avail_h = max_y - y_cursor
        max_lines_here = int((avail_h - 2.0 * pad_y) // line_h)
        if max_lines_here < 1:
            page = doc.new_page(width=612, height=792)
            y_cursor = 36.0
            avail_h = max_y - y_cursor
            max_lines_here = max(1, int((avail_h - 2.0 * pad_y) // line_h))

        chunk = lines[idx : idx + max_lines_here]
        box_h = len(chunk) * line_h + 2.0 * pad_y
        sh = page.new_shape()
        if bg_fill is not None or border_color is not None:
            sh.draw_rect(fitz.Rect(x0, y_cursor, x1, y_cursor + box_h))
            sh.finish(color=border_color or bg_fill, fill=bg_fill)
        if left_stripe_color is not None:
            sh.draw_rect(fitz.Rect(x0, y_cursor, x0 + 4.0, y_cursor + box_h))
            sh.finish(color=left_stripe_color, fill=left_stripe_color)
        for line_idx, line_str in enumerate(chunk):
            if line_str:
                baseline_y = y_cursor + pad_y + (line_idx + 0.82) * line_h
                sh.insert_text(
                    fitz.Point(x0 + eff_pad_x, baseline_y),
                    line_str,
                    fontsize=fontsize,
                    fontname=fontname,
                    color=color,
                )
        sh.commit()
        y_cursor += box_h + 2.0
        idx += len(chunk)
        if idx < total_lines:
            page = doc.new_page(width=612, height=792)
            y_cursor = 36.0

    return page, y_cursor


def _draw_workbook_table_column_headers(
    page: Any,
    y_pos: float,
    headers: List[str],
    left_col_x0: float = 32.0,
    left_col_x1: float = 188.0,
    input_region_x0: float = 188.0,
    input_region_x1: float = 580.0,
    col_hdr_h: float = 15.0,
    is_continuation: bool = False,
) -> float:
    """Draws the dark Navy multi-column table header row (and redraws with '(Cont.)' on page breaks)."""
    import fitz

    input_headers = headers[1:] if len(headers) > 1 else ["Scout Notes & Field Evidence", "Key Examples & Verification"]
    input_cols = max(1, len(input_headers))
    col_w = (input_region_x1 - input_region_x0) / float(input_cols)

    hdr_shape = page.new_shape()
    hdr_shape.draw_rect(fitz.Rect(left_col_x0, y_pos, left_col_x1, y_pos + col_hdr_h))
    hdr_shape.finish(color=(0.0, 0.247, 0.529), fill=(0.0, 0.247, 0.529))
    first_hdr = str(headers[0] if headers else "Item / Step").strip()
    if is_continuation and "(Cont.)" not in first_hdr:
        first_hdr = f"{first_hdr} (Cont.)"
    hdr_shape.insert_text(
        fitz.Point(left_col_x0 + 4.0, y_pos + 10.5),
        _sanitize_pdf_text(first_hdr),
        fontsize=6.8,
        fontname="helv",
        color=(1.0, 1.0, 1.0),
    )
    for c_idx, h_title in enumerate(input_headers):
        cx0 = input_region_x0 + c_idx * col_w
        cx1 = input_region_x0 + (c_idx + 1) * col_w
        hdr_shape.draw_rect(fitz.Rect(cx0, y_pos, cx1, y_pos + col_hdr_h))
        hdr_shape.finish(color=(0.82, 0.88, 0.95), fill=(0.0, 0.247, 0.529))
        hdr_clean = _sanitize_pdf_text(str(h_title))
        if is_continuation and c_idx == 0 and "(Cont.)" not in hdr_clean:
            hdr_clean = f"{hdr_clean} (Cont.)"
        hdr_fs = 6.8 if len(hdr_clean) * 3.6 <= (col_w - 6.0) else max(5.6, (col_w - 6.0) / max(1, len(hdr_clean)) * 1.8)
        hdr_shape.insert_text(
            fitz.Point(cx0 + 3.5, y_pos + 10.5),
            hdr_clean,
            fontsize=hdr_fs,
            fontname="helv",
            color=(1.0, 1.0, 1.0),
        )
    hdr_shape.commit()
    return y_pos + col_hdr_h


def _draw_pdf_workbook_diagram_card(
    doc: Any,
    page: Any,
    y_cursor: float,
    badge_name: str,
    r_num: str,
    r_title: str,
    diagram_url: str,
    max_y: float = 746.0,
    diagram_caption: str = "",
) -> Tuple[Any, float]:
    """Hydrates and embeds a compact instructional reference diagram card right above a workbook requirement table."""
    import fitz
    from pathlib import Path
    from src.config import ASSETS_DIR
    from src.tools.scouting_scraper import _resolve_workbook_diagram_caption

    raw_url = str(diagram_url or "").strip()
    if not raw_url:
        return page, y_cursor

    resolved_path: Optional[Path] = None
    try:
        cand = raw_url.lstrip("/")
        for p_try in (
            Path(raw_url),
            ASSETS_DIR / cand,
            ASSETS_DIR.parent / cand,
        ):
            if p_try.is_file() and p_try.suffix.lower() in (".png", ".jpg", ".jpeg"):
                resolved_path = p_try
                break
        if resolved_path is None and cand.startswith("assets/"):
            from src.tools.asset_hydrator import hydrate_single_asset_on_demand

            hydrate_single_asset_on_demand(cand, timeout_sec=1.5)
            for p_try in (
                ASSETS_DIR / cand,
                ASSETS_DIR.parent / cand,
            ):
                if p_try.is_file() and p_try.suffix.lower() in (".png", ".jpg", ".jpeg"):
                    resolved_path = p_try
                    break
    except Exception:
        resolved_path = None

    if resolved_path is not None and resolved_path.is_file():
        card_h = 196.0
        if y_cursor + card_h > max_y:
            page = doc.new_page(width=612, height=792)
            y_cursor = 36.0
        card_rect = fitz.Rect(32.0, y_cursor, 580.0, y_cursor + card_h)
        page.draw_rect(card_rect, color=(0.68, 0.78, 0.90), fill=(0.97, 0.985, 1.0), width=0.9)
        clean_diag_title = re.sub(r"^Req(?:uirement)?\s+[0-9a-zA-Z().\-]+\s*[:\-]\s*", "", str(r_title), flags=re.IGNORECASE).strip() or r_title
        resolved_cap = str(diagram_caption or "").strip() or _resolve_workbook_diagram_caption(
            badge_name=badge_name,
            req_num=r_num,
            diagram_url=raw_url,
            explicit_caption="",
            r_title=clean_diag_title,
        )
        if len(resolved_cap) > 112:
            from src.tools.scouting_scraper import _clean_row_clause_without_ellipsis
            resolved_cap = _clean_row_clause_without_ellipsis(resolved_cap, max_chars=112)
        page.insert_text(
            fitz.Point(38.0, y_cursor + 11.5),
            _sanitize_pdf_text(f"Figure (Req {r_num}): {resolved_cap}"),
            fontsize=7.3,
            fontname="helv",
            color=(0.0, 0.22, 0.48),
        )
        try:
            cache_key = str(resolved_path.resolve())
            img_stream = _PDF_DIAGRAM_STREAM_CACHE.get(cache_key)
            if img_stream is None:
                import io as _io
                from PIL import Image as _PILImage

                with _PILImage.open(resolved_path) as _im:
                    if _im.mode in ("RGBA", "LA") or (_im.mode == "P" and "transparency" in _im.info):
                        _rgba = _im.convert("RGBA")
                        _bg = _PILImage.new("RGB", _rgba.size, (248, 251, 255))
                        _bg.paste(_rgba, mask=_rgba.split()[3])
                        _rgb = _bg
                    else:
                        _rgb = _im.convert("RGB")
                    if _rgb.width > 760 or _rgb.height > 570:
                        _rgb.thumbnail((760, 570), _PILImage.Resampling.LANCZOS)
                    _buf = _io.BytesIO()
                    _rgb.save(_buf, format="JPEG", quality=76, optimize=True)
                    img_stream = _buf.getvalue()
                if len(_PDF_DIAGRAM_STREAM_CACHE) < 512:
                    _PDF_DIAGRAM_STREAM_CACHE[cache_key] = img_stream
            page.insert_image(
                fitz.Rect(38.0, y_cursor + 16.0, 574.0, y_cursor + card_h - 4.0),
                stream=img_stream,
                keep_proportion=True,
            )
        except Exception:
            try:
                page.insert_image(
                    fitz.Rect(38.0, y_cursor + 16.0, 574.0, y_cursor + card_h - 4.0),
                    filename=str(resolved_path),
                    keep_proportion=True,
                )
            except Exception:
                pass
        y_cursor += card_h + 4.0

    return page, y_cursor


def generate_fillable_scout_workbook_pdf(
    badge_name: str,
    counselor_info: Optional[Dict[str, Any]] = None,
    option_track: str = "ALL",
    session_dates: Optional[List[str]] = None,
    include_cpp_cover: bool = True,
) -> bytes:
    """Generates a downloadable, interactive AcroForm PDF Fillable Scout Workbook for any of the 149 badges.

    Includes:
    - Branded Scouting America Navy & Gold header banner with embedded official Merit Badge patch emblem.
    - Scouting America Guide to Advancement Section 7.0.3.2 compliance notice banner.
    - Interactive AcroForm text fields (`Scout Name`, `Troop & Council`, `BSA Member ID`, `Counselor Name`).
    - Compact Page-1 Class Preparation (CPP) Summary (Prerequisites, Bring-to-Class Checklist, & Session Plan).
    - Clickable Page-1 Requirement Completion & Counselor Verification Index checkboxes (`chk_idx_<badge>_<idx>`).
    - Unrolled sub-requirements (`1a`, `1b`, `2a`, `2b1`, etc.) with color-coded parent requirement group banners.
    - Full verbatim requirement text (zero mid-word truncation or overflow drops), pamphlet fact-vs-myth callout,
      instructional reference diagrams, counselor pre-approval gate checkboxes, interactive gear checklist checkboxes,
      bordered dot-grid sketch canvases, full-width 548pt (`x=32..580`) zebra-striped multi-row/multi-column graphic
      organizer tables with 36pt handwriting guide rows, repeated headers on page breaks, and header-bar Counselor Sign-Off.
    """
    import fitz

    from src.agents.planner import _format_workbook_organizer_label
    from src.tools.scouting_scraper import (
        CounselorTitleSlideInfo,
        MeritBadgeResearchRequest,
        _iter_unrolled_workbook_units,
        fetch_merit_badge_pamphlet_pdf,
    )

    c_info = counselor_info or {}
    c_name = _sanitize_pdf_text(str(c_info.get("counselor_name") or "Merit Badge Counselor"))
    c_troop = _sanitize_pdf_text(str(c_info.get("troop_affiliation") or "Troop 19, Northeast Massachusetts Council"))
    dates_str = _sanitize_pdf_text(" | ".join(session_dates) if session_dates else "Sessions 1-4 + Make-Up Day")

    lru_key = (
        str(badge_name or "").strip().lower(),
        str(option_track or "ALL").strip().upper(),
        c_name,
        c_troop,
        dates_str,
        bool(include_cpp_cover),
    )
    if lru_key in _WORKBOOK_PDF_LRU_CACHE:
        return _WORKBOOK_PDF_LRU_CACHE[lru_key]

    res = fetch_merit_badge_pamphlet_pdf(
        MeritBadgeResearchRequest(
            badge_name=badge_name,
            option_track=option_track,
            counselor_info=CounselorTitleSlideInfo(**counselor_info) if counselor_info else None,
        )
    )
    resolved_badge = str(res.get("badge_name") or badge_name)
    is_eagle = bool(res.get("is_eagle_required"))
    raw_reqs = list(res.get("requirements") or [])
    _opt_norm, opt_label_raw, reqs = _resolve_option_track_and_filter_reqs(resolved_badge, raw_reqs, option_track)
    opt_label = _sanitize_pdf_text(str(opt_label_raw or option_track or "ALL").strip())

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # Branded Navy & Gold Header Banner with Embedded Merit Badge Emblem
    y_cursor = _draw_branded_pdf_header(
        page=page,
        badge_name=resolved_badge,
        doc_title=f"{resolved_badge.upper()} MERIT BADGE - FILLABLE SCOUT WORKBOOK",
        subtitle_line=f"Counselor: {c_name} ({c_troop})  |  Track: {opt_label}  |  Schedule: {dates_str}",
        kicker_text="SCOUTS BSA INTERACTIVE ACROFORM STUDY AID (GTA SEC. 7.0.3.2)",
        is_eagle_required=is_eagle,
    )

    # GTA 7.0.3.2 Compliance Banner with Gold Left Accent Bar
    page, y_cursor = _insert_wrapped_pdf_text(
        doc,
        page,
        y_cursor,
        28.0,
        584.0,
        "BSA Guide to Advancement Section 7.0.3.2 Notice: Merit badge workbooks are optional organizational study aids. "
        "A counselor must never require a Scout to submit a written worksheet when the official requirement specifies oral explanation, discussion, or physical demonstration.",
        fontsize=7.4,
        fontname="helv",
        color=(0.35, 0.22, 0.02),
        bg_fill=(1.0, 0.98, 0.90),
        border_color=(0.88, 0.72, 0.22),
        left_stripe_color=(0.85, 0.55, 0.05),
        pad_y=2.5,
    )
    y_cursor += 4.0

    # Interactive Scout Info AcroForm Card
    page.draw_rect(
        fitz.Rect(28.0, y_cursor, 584.0, y_cursor + 28.0),
        color=(0.78, 0.84, 0.92),
        fill=(0.97, 0.985, 1.0),
    )
    id_fields = [
        ("scout_name", "Scout Name:", "", fitz.Rect(34, y_cursor + 9, 198, y_cursor + 24)),
        ("troop_unit", "Troop & Council:", "", fitz.Rect(208, y_cursor + 9, 396, y_cursor + 24)),
        ("bsa_id", "BSA Member ID:", "", fitz.Rect(406, y_cursor + 9, 578, y_cursor + 24)),
    ]
    for f_key, f_lbl, f_val, f_rect in id_fields:
        page.insert_text(fitz.Point(f_rect.x0, f_rect.y0 - 1.5), f_lbl, fontsize=7.2, fontname="helv", color=(0.0, 0.22, 0.48))
        w = fitz.Widget()
        w.field_name = f_key
        w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        w.field_value = f_val
        w.rect = fitz.Rect(f_rect.x0, f_rect.y0 + 1, f_rect.x1, f_rect.y1 + 2)
        w.border_color = (0.58, 0.66, 0.76)
        w.fill_color = (1.0, 1.0, 1.0)
        w.text_fontsize = 8.5
        page.add_widget(w)

    y_cursor += 32.0
    units = _iter_unrolled_workbook_units(reqs, badge_name=resolved_badge)

    # Compact Class Preparation (CPP) Summary on Page 1 by default (Deliverable 8)
    if include_cpp_cover:
        prereq_nums = [
            str(u.get("req_number") or "").strip()
            for u in units
            if not u.get("is_group_header") and "prereq" in str(u.get("syllabus_bucket") or "").lower()
        ]
        inclass_nums = [
            str(u.get("req_number") or "").strip()
            for u in units
            if not u.get("is_group_header") and "prereq" not in str(u.get("syllabus_bucket") or "").lower()
        ]
        prereq_str = ", ".join(prereq_nums[:10]) if prereq_nums else "Read Official Merit Badge Pamphlet Chapter 1"
        inclass_str = ", ".join(inclass_nums[:14]) + (f" (+{len(inclass_nums) - 14} more)" if len(inclass_nums) > 14 else "") if inclass_nums else "All Core Requirements"
        cpp_summary_text = (
            f"Class Preparation Summary (CPP)  |  1. Do Before Session 1 (Prerequisites): Reqs {prereq_str}\n"
            f"2. Bring to Every Session: Signed Blue Card (#34124), {resolved_badge} Pamphlet, this Fillable Workbook, & Scout Basic Essentials\n"
            f"3. Session Plan ({dates_str}): In-Class Guided Discussion & EDGE Stations (Reqs {inclass_str})"
        )
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            28.0,
            584.0,
            cpp_summary_text,
            fontsize=7.0,
            fontname="helv",
            color=(0.12, 0.22, 0.34),
            bg_fill=(0.96, 0.985, 0.995),
            border_color=(0.74, 0.83, 0.92),
            left_stripe_color=(0.08, 0.50, 0.24),
            pad_y=2.2,
        )
        y_cursor += 3.0

    # Page-1 At-a-Glance Requirement Completion & Counselor Sign-Off Index with Clickable Checkboxes (Deliverable 6)
    fillable_req_nums = [
        str(u.get("req_number") or u.get("req_id") or "").strip()
        for u in units
        if not u.get("is_group_header") and str(u.get("req_number") or u.get("req_id") or "").strip()
    ]
    badge_slug = re.sub(r"[^a-z0-9]+", "_", resolved_badge.lower()).strip("_") or "badge"
    if fillable_req_nums:
        grouped_pdf_reqs: Dict[str, List[str]] = {}
        grouped_pdf_order: List[str] = []
        for rn in fillable_req_nums:
            m_p = re.match(r"^(\d+)", rn)
            p_key = m_p.group(1) if m_p else rn
            if p_key not in grouped_pdf_reqs:
                grouped_pdf_order.append(p_key)
                grouped_pdf_reqs[p_key] = []
            grouped_pdf_reqs[p_key].append(rn)
        grouped_segments = [
            f"Req {pk}: " + " ".join(grouped_pdf_reqs[pk])
            for pk in grouped_pdf_order
        ]
        chips_lines_formatted = "  |  ".join(grouped_segments)
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            28.0,
            584.0,
            f"Page-1 Requirement Completion & Counselor Verification Index ({len(grouped_pdf_order)} Core Reqs / {len(fillable_req_nums)} Checkpoints):\n"
            f"{chips_lines_formatted}",
            fontsize=6.9,
            fontname="helv",
            color=(0.08, 0.18, 0.36),
            bg_fill=(0.94, 0.97, 1.0),
            border_color=(0.68, 0.78, 0.90),
            left_stripe_color=(0.0, 0.247, 0.529),
            pad_y=2.2,
        )
        # Render interactive AcroForm checkboxes in a compact multi-column grid right below the header line
        cols_per_row = 10
        grid_rows = (len(fillable_req_nums) + cols_per_row - 1) // cols_per_row
        row_step_h = 11.0
        grid_box_h = grid_rows * row_step_h + 16.0
        page.draw_rect(
            fitz.Rect(28.0, y_cursor, 584.0, y_cursor + grid_box_h),
            color=(0.68, 0.78, 0.90),
            fill=(0.965, 0.985, 1.0),
        )
        page.draw_rect(
            fitz.Rect(28.0, y_cursor, 32.0, y_cursor + grid_box_h),
            color=(0.0, 0.247, 0.529),
            fill=(0.0, 0.247, 0.529),
        )
        cell_w = (580.0 - 36.0) / float(cols_per_row)
        for chk_idx, rn in enumerate(fillable_req_nums, start=1):
            c_i = (chk_idx - 1) % cols_per_row
            r_i = (chk_idx - 1) // cols_per_row
            cx = 36.0 + c_i * cell_w
            cy = y_cursor + 2.5 + r_i * row_step_h
            w_idx = fitz.Widget()
            w_idx.field_name = f"chk_idx_{badge_slug}_{chk_idx}"
            w_idx.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
            w_idx.field_value = False
            w_idx.rect = fitz.Rect(cx, cy, cx + 8.5, cy + 8.5)
            w_idx.border_color = (0.0, 0.247, 0.529)
            w_idx.fill_color = (1.0, 1.0, 1.0)
            page.add_widget(w_idx)
            page.insert_text(
                fitz.Point(cx + 10.5, cy + 7.2),
                _sanitize_pdf_text(rn[:8]),
                fontsize=6.3,
                fontname="helv",
                color=(0.08, 0.18, 0.36),
            )
        sig_y = y_cursor + grid_rows * row_step_h + 11.5
        page.insert_text(
            fitz.Point(36.0, sig_y),
            "Unit Leader Pre-Approval (Blue Card #34124): ______________________   Counselor Final Sign-Off: ______________________   Date: ____/____/2026",
            fontsize=6.9,
            fontname="helv",
            color=(0.08, 0.18, 0.36),
        )
        y_cursor += grid_box_h + 5.0

    for idx, u in enumerate(units, start=1):
        r_num = str(u.get("req_number") or u.get("req_id") or str(idx)).strip()
        raw_r_title = str(u.get("topic_title") or u.get("title") or f"Requirement {r_num}").strip()
        r_title = re.sub(r"^Req(?:uirement)?\s+[0-9a-zA-Z().\-]+\s*[:\-]\s*", "", raw_r_title, flags=re.IGNORECASE).strip() or raw_r_title
        r_text = str(u.get("req_text") or "").strip()
        r_bucket = str(u.get("syllabus_bucket") or "In-Class Concept").strip()
        r_cit = str(u.get("pamphlet_page_citation") or u.get("pamphlet_citation") or "Official BSA Pamphlet").strip()
        org = u.get("workbook_organizer") or {}
        org_type = str(org.get("organizer_type") or "RULED_EXPLAIN_BOX").strip()
        org_type_friendly = _format_workbook_organizer_label(org_type)
        org_label = _format_workbook_organizer_label(r_num, org_type)
        headers = [str(h) for h in (org.get("headers") or ["Concept / Step", "Scout Notes & Field Evidence", "Key Examples & Verification"])]
        if any("primary concept / system a" in h.lower() or "secondary concept / system b" in h.lower() for h in headers):
            comp_u = u.get("comparison_data") if isinstance(u.get("comparison_data"), dict) else {}
            lh_u = str(comp_u.get("left_header") or "").strip()
            rh_u = str(comp_u.get("right_header") or "").strip()
            if lh_u and rh_u:
                headers = [f"Req {r_num} Comparison Aspect", lh_u, rh_u]
            else:
                headers = [f"Req {r_num} Concept / Prompt", f"Req {r_num} Key Characteristics", "Key Difference & Field Application"]
        if len(headers) < 3:
            headers = headers + ["Key Examples & Verification"] * (3 - len(headers))
        row_labels = [str(rl) for rl in (org.get("row_labels") or ["1. Core explanation & evidence"]) if str(rl).strip()] or ["1. Core explanation & evidence"]
        pre_approval_gate = bool(org.get("pre_approval_gate")) or bool(u.get("starting_requirement_gate"))
        gear_checklist = [str(g) for g in (u.get("gear_checklist") or []) if str(g).strip()]
        mis_pair = u.get("common_misconception_pair") or {}
        diagram_url = str(u.get("workbook_diagram_url") or org.get("diagram_url") or "").strip()

        # Color-code left accent bar by syllabus bucket
        bucket_lower = r_bucket.lower()
        if "prereq" in bucket_lower:
            stripe_rgb = (0.85, 0.47, 0.02)  # Amber
        elif "demonstration" in bucket_lower or "hands-on" in bucket_lower:
            stripe_rgb = (0.08, 0.50, 0.24)  # Forest Green
        elif "make-up" in bucket_lower:
            stripe_rgb = (0.31, 0.27, 0.90)  # Indigo
        elif "follow-up" in bucket_lower or "home-troop" in bucket_lower:
            stripe_rgb = (0.73, 0.11, 0.11)  # Crimson
        else:
            stripe_rgb = (0.0, 0.247, 0.529)  # Scouting Navy

        if u.get("is_group_header"):
            if y_cursor > 685.0:
                page = doc.new_page(width=612, height=792)
                y_cursor = 36.0
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                28.0,
                584.0,
                f"[Requirement {r_num} Overview] {r_title}   |   {r_bucket}   |   {r_cit}",
                fontsize=8.4,
                fontname="helv",
                color=(0.0, 0.20, 0.45),
                bg_fill=(0.88, 0.93, 0.99),
                border_color=(0.0, 0.247, 0.529),
                left_stripe_color=(0.992, 0.725, 0.075),
            )
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                32.0,
                580.0,
                f"Official Requirement {r_num}: {r_text}",
                fontsize=8.0,
                fontname="helv",
                color=(0.08, 0.12, 0.18),
            )
            grp_myth_val = str(mis_pair.get("misconception") or mis_pair.get("myth") or "").strip() if isinstance(mis_pair, dict) else ""
            grp_fact_val = str(mis_pair.get("fact") or mis_pair.get("fact_correction") or "").strip() if isinstance(mis_pair, dict) else ""
            if grp_myth_val and grp_fact_val:
                page, y_cursor = _insert_wrapped_pdf_text(
                    doc,
                    page,
                    y_cursor,
                    32.0,
                    580.0,
                    f"Common Misconception: {grp_myth_val}  |  Pamphlet Fact: {grp_fact_val}",
                    fontsize=7.2,
                    fontname="helv",
                    color=(0.32, 0.22, 0.04),
                    bg_fill=(1.0, 0.99, 0.94),
                    border_color=(0.90, 0.78, 0.38),
                    left_stripe_color=(0.85, 0.55, 0.05),
                    pad_y=2.5,
                )
            if diagram_url:
                page, y_cursor = _draw_pdf_workbook_diagram_card(
                    doc,
                    page,
                    y_cursor,
                    resolved_badge,
                    r_num,
                    r_title,
                    diagram_url,
                    diagram_caption=str(u.get("workbook_diagram_caption") or ""),
                )
            y_cursor += 4.0
            continue

        if y_cursor > 635.0:
            page = doc.new_page(width=612, height=792)
            y_cursor = 36.0

        safe_r_num = re.sub(r"[^a-zA-Z0-9_]", "_", r_num)

        # Requirement / Sub-Requirement Header Strip with Top-Right Counselor Sign-Off (x = 465..584)
        hdr_y0 = y_cursor
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            28.0,
            464.0,
            f"[Req {r_num}] {r_title}   |   {r_bucket}   |   {org_type_friendly}   |   {r_cit}",
            fontsize=8.0,
            fontname="helv",
            color=(0.0, 0.22, 0.48),
            bg_fill=(0.93, 0.96, 0.99),
            border_color=(0.80, 0.86, 0.94),
            left_stripe_color=stripe_rgb,
        )
        hdr_h = max(16.0, (y_cursor - 2.0) - hdr_y0)
        # Draw top-right Counselor Sign-Off capsule inside the requirement header bar (x = 465..584)
        page.draw_rect(
            fitz.Rect(465.0, hdr_y0, 584.0, hdr_y0 + hdr_h),
            color=(0.80, 0.86, 0.94),
            fill=(0.95, 0.975, 1.0),
        )
        page.insert_text(
            fitz.Point(469.0, hdr_y0 + 11.0),
            "Done:",
            fontsize=7.1,
            fontname="helv",
            color=(0.08, 0.18, 0.36),
        )
        w_chk = fitz.Widget()
        w_chk.field_name = f"req_{safe_r_num}_done_{idx}"
        w_chk.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
        w_chk.field_value = False
        w_chk.rect = fitz.Rect(492.0, hdr_y0 + 2.5, 503.0, hdr_y0 + 13.5)
        w_chk.border_color = (0.0, 0.25, 0.53)
        w_chk.fill_color = (1.0, 1.0, 1.0)
        page.add_widget(w_chk)
        page.insert_text(
            fitz.Point(507.0, hdr_y0 + 11.0),
            "Init:_______",
            fontsize=6.9,
            fontname="helv",
            color=(0.22, 0.28, 0.38),
        )

        # Full Verbatim Requirement Text (dynamically wrapped and paginated)
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            32.0,
            580.0,
            f"Official Requirement {r_num}: {r_text}",
            fontsize=8.0,
            fontname="helv",
            color=(0.1, 0.14, 0.2),
        )

        # Common Misconception vs Pamphlet Truth Strip
        myth_val = str(mis_pair.get("misconception") or mis_pair.get("myth") or "").strip() if isinstance(mis_pair, dict) else ""
        fact_val = str(mis_pair.get("fact") or mis_pair.get("fact_correction") or "").strip() if isinstance(mis_pair, dict) else ""
        if myth_val and fact_val:
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                32.0,
                580.0,
                f"Common Misconception: {myth_val}  |  Pamphlet Fact: {fact_val}",
                fontsize=7.2,
                fontname="helv",
                color=(0.32, 0.22, 0.04),
                bg_fill=(1.0, 0.99, 0.94),
                border_color=(0.90, 0.78, 0.38),
                left_stripe_color=(0.85, 0.55, 0.05),
                pad_y=2.5,
            )

        # Starting / Pre-Approval Gate Box (with distinct gate labels for Equipment, Parent Consent, or Pre-Approval)
        gate_meta = u.get("starting_requirement_gate") if isinstance(u.get("starting_requirement_gate"), dict) else {}
        if pre_approval_gate or gate_meta.get("gate_label"):
            if y_cursor > 715.0:
                page = doc.new_page(width=612, height=792)
                y_cursor = 36.0
            gate_y0 = y_cursor
            g_type_up = str(gate_meta.get("gate_type") or "").upper()
            g_custom_lbl = str(gate_meta.get("gate_label") or "").strip()
            g_custom_desc = str(gate_meta.get("gate_description") or "").strip()
            if "EQUIPMENT" in g_type_up:
                gate_banner_txt = f"EQUIPMENT & SAFETY GATE: {g_custom_lbl or 'Verify required safety gear'} - {g_custom_desc or 'Inspect before starting station.'} Counselor Initials & Date: ____________"
            elif "PARENT" in g_type_up or "CONSENT" in g_type_up:
                gate_banner_txt = f"PARENT / GUARDIAN CONSENT GATE: {g_custom_lbl or 'Obtain parent/guardian and Counselor approval'} - {g_custom_desc or 'Verify before starting.'} Initials & Date: ____________"
            else:
                gate_banner_txt = "COUNSELOR PRE-APPROVAL GATE: Obtain Counselor approval BEFORE starting this requirement/plan/project. Counselor Initials & Date: ____________"
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                48.0,
                580.0,
                gate_banner_txt,
                fontsize=7.4,
                fontname="helv",
                color=(0.45, 0.18, 0.02),
                bg_fill=(1.0, 0.95, 0.88),
                border_color=(0.88, 0.48, 0.08),
                left_stripe_color=(0.85, 0.35, 0.05),
                pad_y=3.0,
            )
            w_gate = fitz.Widget()
            w_gate.field_name = f"req_{r_num}_preapproval_{idx}"
            w_gate.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
            w_gate.field_value = False
            w_gate.rect = fitz.Rect(33.0, gate_y0 + 2.0, 45.0, gate_y0 + 14.0)
            w_gate.border_color = (0.85, 0.40, 0.05)
            page.add_widget(w_gate)

        # Interactive Gear / Preparation Checklist
        if gear_checklist:
            for g_idx, g_item in enumerate(gear_checklist, start=1):
                if y_cursor > 728.0:
                    page = doc.new_page(width=612, height=792)
                    y_cursor = 36.0
                g_y0 = y_cursor
                page, y_cursor = _insert_wrapped_pdf_text(
                    doc,
                    page,
                    y_cursor,
                    48.0,
                    580.0,
                    f"Gear / Kit Checklist: {g_item}",
                    fontsize=7.3,
                    fontname="helv",
                    color=(0.18, 0.24, 0.32),
                    pad_y=1.5,
                )
                w_gear = fitz.Widget()
                w_gear.field_name = f"req_{r_num}_gear_{idx}_{g_idx}"
                w_gear.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
                w_gear.field_value = False
                w_gear.rect = fitz.Rect(33.0, g_y0 + 1.0, 44.0, g_y0 + 12.0)
                w_gear.border_color = (0.35, 0.45, 0.58)
                page.add_widget(w_gear)

        # Instructional Reference Diagram Card right above organizer table (Deliverable 7)
        if diagram_url:
            page, y_cursor = _draw_pdf_workbook_diagram_card(
                doc,
                page,
                y_cursor,
                resolved_badge,
                r_num,
                r_title,
                diagram_url,
                diagram_caption=str(u.get("workbook_diagram_caption") or ""),
            )

        # Sketch & Observation Canvas (dot-grid / astronomy circle canvas)
        from src.tools.scouting_scraper import is_genuine_sketch_prompt
        low_text = r_text.lower()
        if org_type == "SKETCH_AND_OBSERVATION_CANVAS" or is_genuine_sketch_prompt(low_text):
            if y_cursor + 92.0 > 746.0:
                page = doc.new_page(width=612, height=792)
                y_cursor = 36.0
            canvas_rect = fitz.Rect(32.0, y_cursor, 580.0, y_cursor + 84.0)
            sk_shape = page.new_shape()
            sk_shape.draw_rect(canvas_rect)
            sk_shape.finish(color=(0.55, 0.64, 0.76), fill=(0.99, 0.995, 1.0))
            for gy in range(int(y_cursor) + 22, int(y_cursor) + 78, 16):
                sk_shape.draw_line(fitz.Point(44.0, float(gy)), fitz.Point(568.0, float(gy)))
            sk_shape.finish(color=(0.76, 0.81, 0.87), width=0.6, dashes="[1 11] 0")
            if any(k in low_text for k in ("moon", "planet", "constellation", "sky", "eclipse", "telescope", "horizon")):
                sk_shape.draw_circle(fitz.Point(500.0, y_cursor + 46.0), 22.0)
                sk_shape.draw_line(fitz.Point(40.0, y_cursor + 72.0), fitz.Point(455.0, y_cursor + 72.0))
                sk_shape.finish(color=(0.60, 0.68, 0.78), width=0.8)
            sk_shape.commit()
            page.insert_text(
                fitz.Point(38.0, y_cursor + 11.0),
                _sanitize_pdf_text(f"Sketch & Observation Canvas (Req {r_num}) - Draw, diagram, and label key features:"),
                fontsize=7.3,
                fontname="helv",
                color=(0.25, 0.32, 0.42),
            )
            y_cursor += 88.0

        # Structured Graphic Organizer Header Strip
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            32.0,
            580.0,
            f"{org_label}  |  Columns: {' / '.join(headers)}",
            fontsize=7.4,
            fontname="helv",
            color=(0.15, 0.24, 0.38),
            bg_fill=(0.91, 0.95, 0.99),
            border_color=(0.76, 0.83, 0.92),
            pad_y=2.5,
        )

        # Render Full-Width 548pt (x=32..580) Multi-Column Header Row + 36pt Handwriting Rows + Page-Break Header Redraw
        input_headers = headers[1:] if len(headers) > 1 else ["Scout Notes & Field Evidence", "Key Examples & Verification"]
        input_cols = max(1, len(input_headers))
        left_col_x0 = 32.0
        left_col_x1 = 188.0
        input_region_x0 = 188.0
        input_region_x1 = 580.0
        col_w = (input_region_x1 - input_region_x0) / float(input_cols)
        col_hdr_h = 15.0
        if y_cursor + col_hdr_h + 38.0 > 746.0:
            page = doc.new_page(width=612, height=792)
            y_cursor = 36.0
        y_cursor = _draw_workbook_table_column_headers(
            page=page,
            y_pos=y_cursor,
            headers=headers,
            left_col_x0=left_col_x0,
            left_col_x1=left_col_x1,
            input_region_x0=input_region_x0,
            input_region_x1=input_region_x1,
            col_hdr_h=col_hdr_h,
            is_continuation=False,
        )

        r_verb_low = str(u.get("action_verb") or "Explain").strip().lower()
        if len(row_labels) == 1:
            base_row_min_h = 80.0 if (r_verb_low in ("explain", "discuss", "describe", "tell", "compare", "contrast") or len(headers) >= 3) else 66.0
        else:
            base_row_min_h = 42.0

        for r_idx, rl in enumerate(row_labels, start=1):
            clean_rl = re.sub(r"^\s*\d+[.)]\s*", "", str(rl)).strip()
            label_lines = _wrap_pdf_lines(f"{r_idx}. {clean_rl}", 148.0, fontname="helv", fontsize=7.2) or [f"{r_idx}."]
            row_h = max(base_row_min_h, len(label_lines) * 9.5 + 10.0)
            if y_cursor + row_h > 746.0:
                page = doc.new_page(width=612, height=792)
                y_cursor = 36.0
                y_cursor = _draw_workbook_table_column_headers(
                    page=page,
                    y_pos=y_cursor,
                    headers=headers,
                    left_col_x0=left_col_x0,
                    left_col_x1=left_col_x1,
                    input_region_x0=input_region_x0,
                    input_region_x1=input_region_x1,
                    col_hdr_h=col_hdr_h,
                    is_continuation=True,
                )
            row_y0 = y_cursor
            zebra_fill = (0.945, 0.97, 1.0) if r_idx % 2 == 1 else (0.98, 0.99, 1.0)
            row_shape = page.new_shape()
            row_shape.draw_rect(fitz.Rect(left_col_x0, row_y0, left_col_x1, row_y0 + row_h))
            row_shape.finish(color=(0.78, 0.83, 0.90), fill=zebra_fill)

            for c_idx in range(input_cols):
                cx0 = input_region_x0 + c_idx * col_w
                cx1 = input_region_x0 + (c_idx + 1) * col_w
                row_shape.draw_rect(fitz.Rect(cx0, row_y0, cx1, row_y0 + row_h))
            row_shape.finish(color=(0.78, 0.83, 0.90), fill=(1.0, 1.0, 1.0))

            # Faint horizontal dashed handwriting guide lines (#CBD5E1) spaced every 18pt across each input cell
            for gy_offset in range(18, int(row_h) - 6, 18):
                guide_y = row_y0 + float(gy_offset)
                for c_idx in range(input_cols):
                    cx0 = input_region_x0 + c_idx * col_w
                    cx1 = input_region_x0 + (c_idx + 1) * col_w
                    row_shape.draw_line(fitz.Point(cx0 + 4.0, guide_y), fitz.Point(cx1 - 4.0, guide_y))
            row_shape.finish(color=(0.796, 0.835, 0.882), width=0.5, dashes="[4 4] 0")

            for l_i, l_str in enumerate(label_lines):
                row_shape.insert_text(
                    fitz.Point(left_col_x0 + 4.0, row_y0 + 3.5 + (l_i + 0.82) * 9.5),
                    l_str,
                    fontsize=7.2,
                    fontname="helv",
                    color=(0.12, 0.18, 0.26),
                )
            row_shape.commit()

            for c_idx in range(input_cols):
                cx0 = input_region_x0 + c_idx * col_w
                cx1 = input_region_x0 + (c_idx + 1) * col_w
                w_row = fitz.Widget()
                w_row.field_name = f"req_{safe_r_num}_row_{idx}_{r_idx}_col_{c_idx + 1}"
                w_row.field_type = fitz.PDF_WIDGET_TYPE_TEXT
                w_row.field_flags = fitz.PDF_TX_FIELD_IS_MULTILINE
                w_row.field_value = ""
                w_row.rect = fitz.Rect(cx0 + 1.0, row_y0 + 1.0, cx1 - 1.0, row_y0 + row_h - 1.0)
                w_row.border_color = (0.68, 0.75, 0.84)
                w_row.fill_color = (1.0, 1.0, 1.0)
                w_row.text_fontsize = 7.8
                page.add_widget(w_row)

            y_cursor += row_h + 1.0

        y_cursor += 7.0

    _finalize_branded_pdf_pages(
        doc=doc,
        badge_name=resolved_badge,
        doc_short_title="FILLABLE SCOUT WORKBOOK (GTA SEC. 7.0.3.2)",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    if len(_WORKBOOK_PDF_LRU_CACHE) < 64:
        _WORKBOOK_PDF_LRU_CACHE[lru_key] = pdf_bytes
    return pdf_bytes


def generate_class_preparation_page_cpp_pdf(
    badge_name: str,
    counselor_info: Optional[Dict[str, Any]] = None,
    session_dates: Optional[List[str]] = None,
    room_location: str = "",
    option_track: str = "ALL",
) -> bytes:
    """Generates a strictly 1-page graphically styled Class Preparation Page (CPP) in PDF format across 100% of all 149+ badges."""
    import fitz

    cpp_data = generate_class_preparation_page_cpp(
        badge_name=badge_name,
        counselor_info=counselor_info,
        session_dates=session_dates,
        room_location=room_location,
        option_track=option_track,
    )
    resolved_badge = str(cpp_data.get("badge_name") or badge_name)
    opt_label = _sanitize_pdf_text(str(cpp_data.get("option_label") or option_track or "ALL"))
    md_text = str(cpp_data.get("cpp_markdown") or "")
    c_info = counselor_info or {}
    c_name = _sanitize_pdf_text(str(c_info.get("counselor_name") or "Merit Badge Counselor"))
    c_troop = _sanitize_pdf_text(str(c_info.get("troop_affiliation") or "Troop 19, Northeast Massachusetts Council"))
    room_str = _sanitize_pdf_text(str(room_location or "Main Clinic Room / Troop Hall"))

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y_cursor = _draw_branded_pdf_header(
        page=page,
        badge_name=resolved_badge,
        doc_title=f"{resolved_badge.upper()} MERIT BADGE - 1-PAGE CLASS PREPARATION PAGE (CPP)",
        subtitle_line=f"Counselor: {c_name} ({c_troop})  |  Track: {opt_label}  |  Venue: {room_str}",
        kicker_text="SCOUTS BSA PRE-CLASS SCOUT, PARENT & UNIT LEADER HANDOUT",
    )

    # Parse markdown into preamble + structured sections so we can dynamically scale and 2-column pack to strictly 1 page
    preamble_lines: List[str] = []
    sections: List[Tuple[str, List[str]]] = []
    curr_hdr: Optional[str] = None
    curr_items: List[str] = []

    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("# "):
            continue
        clean_line = (
            line.replace("**", "")
            .replace("`", "")
            .replace("- [ ] ", "[ ] ")
        )
        clean_line = re.sub(r"\*([^*]+)\*", r"\1", clean_line)
        if clean_line.startswith("## "):
            if curr_hdr is not None:
                sections.append((curr_hdr, curr_items))
            curr_hdr = clean_line[3:].strip()
            curr_items = []
        else:
            if curr_hdr is None:
                preamble_lines.append(clean_line)
            else:
                curr_items.append(clean_line)
    if curr_hdr is not None:
        sections.append((curr_hdr, curr_items))

    # Render compact metadata preamble on 1-2 lines
    if preamble_lines:
        meta_joined = "  |  ".join(preamble_lines[:3])
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            28.0,
            584.0,
            meta_joined,
            fontsize=7.3,
            fontname="helv",
            color=(0.12, 0.18, 0.28),
            bg_fill=(0.96, 0.98, 1.0),
            border_color=(0.82, 0.88, 0.95),
            pad_y=2.0,
            max_y=752.0,
        )
        y_cursor += 2.0

    total_items = sum(len(items) for _, items in sections)
    compact_mode = total_items > 12

    for hdr_text, items in sections:
        in_gate_section = "Gate Alert" in hdr_text
        if y_cursor > 725.0:
            break
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            28.0,
            584.0,
            hdr_text,
            fontsize=8.6 if compact_mode else 9.0,
            fontname="helv",
            color=(0.0, 0.22, 0.48),
            bg_fill=(0.92, 0.96, 0.99),
            border_color=(0.78, 0.85, 0.94),
            left_stripe_color=(0.992, 0.725, 0.075) if in_gate_section else (0.0, 0.247, 0.529),
            pad_y=2.2 if compact_mode else 3.0,
            max_y=752.0,
        )
        if in_gate_section:
            gate_joined = "  ".join(items)
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                32.0,
                580.0,
                gate_joined,
                fontsize=7.6 if compact_mode else 8.1,
                fontname="helv",
                color=(0.38, 0.22, 0.02),
                bg_fill=(1.0, 0.98, 0.90),
                border_color=(0.88, 0.68, 0.18),
                left_stripe_color=(0.85, 0.55, 0.05),
                pad_y=2.2,
                max_y=752.0,
            )
            y_cursor += 2.0
            continue

        # Determine if this section should render in 2 columns to guarantee 1-page fit
        bullet_items = [it for it in items if it.startswith("[ ]") or it.startswith("-") or it.startswith("*")]
        non_bullet_items = [it for it in items if it not in bullet_items]
        use_two_cols = len(bullet_items) >= 5 or (compact_mode and len(bullet_items) >= 3)

        if use_two_cols and bullet_items:
            # Cap or compact ultra-long bullet lists (e.g. 40+ sub-requirements) so they never overflow y=742
            avail_h = max(48.0, 738.0 - y_cursor - (len(non_bullet_items) * 14.0))
            line_h = 8.4 if len(bullet_items) > 16 else 9.2
            fs = 6.9 if len(bullet_items) > 16 else 7.4
            max_rows_possible = max(3, int(avail_h // (line_h * 1.45)))
            max_bullets = max_rows_possible * 2
            display_bullets = list(bullet_items)
            if len(display_bullets) > max_bullets:
                overflow_cnt = len(display_bullets) - (max_bullets - 1)
                display_bullets = display_bullets[: max_bullets - 1] + [
                    f"[ ] +{overflow_cnt} additional sub-requirements completed in guided clinic stations (see Workbook Index)."
                ]
            for pair_i in range(0, len(display_bullets), 2):
                left_txt = _sanitize_pdf_text(display_bullets[pair_i])
                right_txt = _sanitize_pdf_text(display_bullets[pair_i + 1]) if pair_i + 1 < len(display_bullets) else ""
                left_lines = _wrap_pdf_lines(left_txt, 262.0, fontname="helv", fontsize=fs)[:2]
                right_lines = _wrap_pdf_lines(right_txt, 262.0, fontname="helv", fontsize=fs)[:2] if right_txt else []
                row_lines = max(len(left_lines), len(right_lines), 1)
                row_block_h = row_lines * line_h + 2.0
                if y_cursor + row_block_h > 744.0:
                    break
                for li, l_str in enumerate(left_lines):
                    page.insert_text(
                        fitz.Point(32.0, y_cursor + (li + 0.82) * line_h),
                        l_str,
                        fontsize=fs,
                        fontname="helv",
                        color=(0.08, 0.12, 0.18),
                    )
                for ri, r_str in enumerate(right_lines):
                    page.insert_text(
                        fitz.Point(310.0, y_cursor + (ri + 0.82) * line_h),
                        r_str,
                        fontsize=fs,
                        fontname="helv",
                        color=(0.08, 0.12, 0.18),
                    )
                y_cursor += row_block_h
            for nb in non_bullet_items:
                if y_cursor + 12.0 > 744.0:
                    break
                page, y_cursor = _insert_wrapped_pdf_text(
                    doc,
                    page,
                    y_cursor,
                    32.0,
                    580.0,
                    nb,
                    fontsize=7.2,
                    fontname="helv",
                    color=(0.12, 0.18, 0.26),
                    pad_y=1.5,
                    max_y=752.0,
                )
        else:
            for item_line in items:
                if y_cursor + 12.0 > 744.0:
                    break
                page, y_cursor = _insert_wrapped_pdf_text(
                    doc,
                    page,
                    y_cursor,
                    32.0,
                    580.0,
                    item_line,
                    fontsize=7.6 if compact_mode else 8.1,
                    fontname="helv",
                    color=(0.08, 0.12, 0.18),
                    pad_y=1.5 if compact_mode else 2.0,
                    max_y=752.0,
                )
        y_cursor += 2.0

    # Safety clamp: ensure standalone CPP is strictly 1 single page (len(doc) == 1)
    while len(doc) > 1:
        doc.delete_page(len(doc) - 1)

    _finalize_branded_pdf_pages(
        doc=doc,
        badge_name=resolved_badge,
        doc_short_title="1-PAGE CLASS PREPARATION PAGE (CPP)",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_session_agenda_pdf(
    badge_name: str,
    schedule_format: str = "3 Troop Meetings (45 min each)",
    counselor_info: Optional[Dict[str, Any]] = None,
    postponed_session_idx: Optional[int] = None,
    companion_badge_name: Optional[str] = None,
    agenda_markdown_override: Optional[str] = None,
    class_start_time: str = "",
    room_location: str = "",
    session_dates_list: Optional[List[str]] = None,
    session_dates: Optional[List[str]] = None,
    section_label: str = "",
    bundle_tag: str = "",
    option_track: str = "ALL",
) -> bytes:
    """Generates a graphically styled Counselor Session Agenda & Lesson Plan in PDF format with embedded Merit Badge emblem and session cards."""
    import fitz

    from src.agents.planner import _format_session_mode_label

    norm_c = _extract_normalized_counselor_fields(
        counselor_info,
        default_name="Merit Badge Counselor",
        default_troop="Troop 19, Northeast Massachusetts Council",
    )
    c_name = _sanitize_pdf_text(norm_c["c_name"])
    c_troop = _sanitize_pdf_text(norm_c["c_troop"])
    friendly_fmt = _format_session_mode_label(schedule_format)

    eff_section = str(section_label or norm_c["section_label"] or "").strip()
    eff_bundle = str(bundle_tag or norm_c["bundle_tag"] or "").strip()
    eff_time = str(class_start_time or norm_c["class_start_time"] or "").strip()
    eff_room = str(room_location or norm_c["room_location"] or "").strip()
    eff_dates = list(session_dates_list or session_dates or norm_c["session_dates_list"] or [])

    agenda_data = generate_counselor_session_agenda(
        badge_name=badge_name,
        schedule_format=schedule_format,
        counselor_info=counselor_info,
        postponed_session_idx=postponed_session_idx,
        companion_badge_name=companion_badge_name,
        class_start_time=eff_time,
        room_location=eff_room,
        session_dates_list=eff_dates,
        section_label=eff_section,
        bundle_tag=eff_bundle,
        option_track=option_track,
    )
    resolved_badge = str(agenda_data.get("badge_name") or badge_name)
    opt_label = _sanitize_pdf_text(str(agenda_data.get("option_label") or option_track or "ALL"))
    md_text = str(agenda_markdown_override or agenda_data.get("agenda_markdown") or "")
    md_text = md_text.replace(f"Schedule Format: {schedule_format}", f"Schedule Format: {friendly_fmt}")
    md_text = md_text.replace(f"**Schedule Format:** {schedule_format}", f"**Schedule Format:** {friendly_fmt}")

    subtitle_parts = [f"Format: {friendly_fmt}", f"Track: {opt_label}", f"Counselor: {c_name} ({c_troop})"]
    if eff_section:
        subtitle_parts.append(f"Section: {_sanitize_pdf_text(eff_section)}")
    if eff_room:
        subtitle_parts.append(f"Room: {_sanitize_pdf_text(eff_room)}")
    if eff_time:
        subtitle_parts.append(f"Start: {_sanitize_pdf_text(eff_time)}")
    if eff_bundle:
        subtitle_parts.append(f"Event: {_sanitize_pdf_text(eff_bundle)}")

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y_cursor = _draw_branded_pdf_header(
        page=page,
        badge_name=resolved_badge,
        doc_title=f"{resolved_badge.upper()} MERIT BADGE - SESSION AGENDA & LESSON PLAN",
        subtitle_line="  |  ".join(subtitle_parts[:4]),
        kicker_text="SCOUTS BSA COUNSELOR FACILITATION & PACING GUIDE (EDGE METHOD)",
    )

    if eff_section or eff_bundle or eff_room or eff_time or eff_dates:
        meta_bar_items = []
        if eff_section:
            meta_bar_items.append(f"Section: {eff_section}")
        if eff_bundle:
            meta_bar_items.append(f"Event / Tag: {eff_bundle}")
        if eff_room:
            meta_bar_items.append(f"Room / Location: {eff_room}")
        if eff_time:
            meta_bar_items.append(f"Start Time: {eff_time}")
        if eff_dates:
            meta_bar_items.append(f"Session Dates: {' | '.join(str(d) for d in eff_dates)}")
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            28.0,
            584.0,
            "  |  ".join(meta_bar_items),
            fontsize=7.6,
            fontname="helv",
            color=(0.35, 0.22, 0.02),
            bg_fill=(1.0, 0.98, 0.90),
            border_color=(0.88, 0.72, 0.22),
            left_stripe_color=(0.992, 0.725, 0.075),
            pad_y=3.0,
        )
        y_cursor += 3.0

    # EDGE Method & GTA Pacing Summary Strip
    page, y_cursor = _insert_wrapped_pdf_text(
        doc,
        page,
        y_cursor,
        28.0,
        584.0,
        "Facilitator Pacing Note: Each session block balances interactive visual briefing, hands-on EDGE skill stations (Explain, Demonstrate, Guide, Enable), and individual Scout verification per GTA Sec. 7.0.3.1.",
        fontsize=7.6,
        fontname="helv",
        color=(0.08, 0.18, 0.36),
        bg_fill=(0.94, 0.97, 1.0),
        border_color=(0.72, 0.82, 0.94),
        left_stripe_color=(0.0, 0.247, 0.529),
        pad_y=3.0,
    )
    y_cursor += 4.0

    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if not line:
            y_cursor += 3.5
            continue
        if line.startswith("# "):
            continue
        clean_line = (
            line.replace("**", "")
            .replace("`", "")
            .replace("*   ", "- ")
        )
        clean_line = re.sub(r"\*([^*]+)\*", r"\1", clean_line)
        if clean_line.startswith("## ") or clean_line.startswith("### "):
            hdr_text = clean_line.lstrip("#").strip()
            is_makeup = "make-up" in hdr_text.lower() or "postponed" in hdr_text.lower()
            y_cursor += 3.0
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                28.0,
                584.0,
                hdr_text,
                fontsize=9.2,
                fontname="helv",
                color=(0.38, 0.20, 0.02) if is_makeup else (0.0, 0.22, 0.48),
                bg_fill=(1.0, 0.97, 0.90) if is_makeup else (0.91, 0.95, 0.99),
                border_color=(0.88, 0.68, 0.18) if is_makeup else (0.76, 0.84, 0.94),
                left_stripe_color=(0.85, 0.50, 0.05) if is_makeup else (0.0, 0.247, 0.529),
                pad_y=3.5,
            )
        elif clean_line.startswith("- ") or clean_line.startswith("* "):
            bullet_body = clean_line[2:].strip()
            is_time_block = any(k in bullet_body.lower() for k in ("min:", "min -", "00-", "10-", "20-", "30-", "45-", "60-"))
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                32.0,
                580.0,
                f"- {bullet_body}",
                fontsize=8.2,
                fontname="helv",
                color=(0.08, 0.14, 0.22),
                bg_fill=(0.98, 0.99, 1.0) if is_time_block else None,
                border_color=(0.84, 0.89, 0.95) if is_time_block else None,
                left_stripe_color=(0.08, 0.50, 0.24) if is_time_block else None,
                pad_y=2.5 if is_time_block else 1.8,
            )
        else:
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                32.0,
                580.0,
                clean_line,
                fontsize=8.2,
                fontname="helv",
                color=(0.12, 0.16, 0.22),
                pad_y=2.0,
            )

    _finalize_branded_pdf_pages(
        doc=doc,
        badge_name=resolved_badge,
        doc_short_title="COUNSELOR SESSION AGENDA & LESSON PLAN",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_parent_letter_pdf(
    badge_name: str,
    counselor_info: Optional[Dict[str, Any]] = None,
    stage: str = "stage_1_welcome_cpp",
    letter_markdown_override: Optional[str] = None,
    option_track: str = "ALL",
) -> bytes:
    """Generates a graphically styled YPT-Compliant Parent Prerequisite & Welcome Letter in PDF format with embedded Merit Badge emblem."""
    import fitz

    norm_c = _extract_normalized_counselor_fields(
        counselor_info,
        default_name="Merit Badge Counselor",
        default_troop="Troop 19, Middleton MA",
        default_email="counselor@scouting.org",
    )
    c_name = _sanitize_pdf_text(norm_c["c_name"])
    c_troop = _sanitize_pdf_text(norm_c["c_troop"])
    c_email = _sanitize_pdf_text(norm_c["c_email"])

    resolved_badge = str(badge_name).strip() or "First Aid"
    md_text = str(letter_markdown_override or "").strip()
    stage_norm = str(stage or "stage_1_welcome_cpp").strip().lower()
    opt_label = _sanitize_pdf_text(str(option_track or "ALL"))
    if not md_text:
        letter_res = generate_prerequisite_parent_letter(
            badge_name=resolved_badge,
            counselor_info=counselor_info,
            stage=stage_norm,
            option_track=option_track,
        )
        resolved_badge = str(letter_res.get("badge_name") or resolved_badge)
        opt_label = _sanitize_pdf_text(str(letter_res.get("option_label") or option_track or "ALL"))
        stages_map = letter_res.get("stages") or {}
        if "2" in stage_norm or "mid" in stage_norm:
            md_text = str((stages_map.get("stage_2_mid_clinic_alert") or {}).get("markdown") or "")
        elif "3" in stage_norm or "final" in stage_norm or "post" in stage_norm:
            md_text = str((stages_map.get("stage_3_final_packet") or {}).get("markdown") or "")
        else:
            md_text = str((stages_map.get("stage_1_welcome_cpp") or {}).get("markdown") or letter_res.get("letter_markdown") or "")

    stage_label = (
        "STAGE 2: MID-SESSION PROGRESS, HOMEWORK & MAKE-UP ALERT"
        if ("2" in stage_norm or "mid" in stage_norm)
        else "STAGE 3: FINAL COMPLETION, BLUE CARD (#34124) & PARTIAL TRANSFER GUIDE"
        if ("3" in stage_norm or "final" in stage_norm or "post" in stage_norm)
        else "STAGE 1: PRE-CLASS WELCOME & PREREQUISITE GUIDE"
    )

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y_cursor = _draw_branded_pdf_header(
        page=page,
        badge_name=resolved_badge,
        doc_title=f"{resolved_badge.upper()} MERIT BADGE - PARENT & SCOUT COMMUNICATION",
        subtitle_line=f"{stage_label}  |  Track: {opt_label}  |  Counselor: {c_name} ({c_troop})  |  {c_email}",
        kicker_text="SCOUTING AMERICA YOUTH PROTECTION (YPT) TWO-DEEP COMMUNICATION",
    )

    # Mandatory YPT Two-Deep Leadership Shield Banner
    page, y_cursor = _insert_wrapped_pdf_text(
        doc,
        page,
        y_cursor,
        28.0,
        584.0,
        "MANDATORY SCOUTING AMERICA YOUTH PROTECTION (YPT) POLICY: All digital/email communications between Scouts and Merit Badge Counselors must copy (CC) a parent/guardian or second registered adult leader. All sessions follow Two-Deep Leadership and the Buddy System.",
        fontsize=7.6,
        fontname="helv",
        color=(0.35, 0.22, 0.02),
        bg_fill=(1.0, 0.98, 0.90),
        border_color=(0.88, 0.72, 0.22),
        left_stripe_color=(0.85, 0.55, 0.05),
        pad_y=3.0,
    )
    y_cursor += 5.0

    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if not line:
            y_cursor += 4.0
            continue
        if line.startswith("[MANDATORY YPT CC:"):
            continue
        clean_line = (
            line.replace("**", "")
            .replace("`", "")
            .replace("- [ ] ", "[ ] ")
        )
        clean_line = re.sub(r"\*([^*]+)\*", r"\1", clean_line)
        if clean_line.lower().startswith("subject:"):
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                28.0,
                584.0,
                clean_line,
                fontsize=8.8,
                fontname="helv",
                color=(0.0, 0.22, 0.48),
                bg_fill=(0.93, 0.96, 1.0),
                border_color=(0.76, 0.84, 0.94),
                left_stripe_color=(0.0, 0.247, 0.529),
                pad_y=3.5,
            )
            y_cursor += 2.0
        elif clean_line.startswith("### ") or clean_line.startswith("## "):
            hdr_text = clean_line.lstrip("#").strip()
            y_cursor += 3.0
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                28.0,
                584.0,
                hdr_text,
                fontsize=9.2,
                fontname="helv",
                color=(0.0, 0.22, 0.48),
                bg_fill=(0.92, 0.96, 0.99),
                border_color=(0.78, 0.85, 0.94),
                left_stripe_color=(0.0, 0.247, 0.529),
                pad_y=3.2,
            )
        else:
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                32.0,
                580.0,
                clean_line,
                fontsize=8.4,
                fontname="helv",
                color=(0.08, 0.12, 0.18),
                pad_y=2.2,
            )

    _finalize_branded_pdf_pages(
        doc=doc,
        badge_name=resolved_badge,
        doc_short_title="YPT-COMPLIANT PARENT & SCOUT LETTER",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_counselor_workbook_pdf(
    badge_name: str,
    counselor_info: Optional[Dict[str, Any]] = None,
    option_track: str = "ALL",
) -> bytes:
    """Generates a branded multi-page Counselor Instructor Guide & Answer Key PDF with 100% sub-requirement answer keys."""
    import fitz
    from src.tools.scouting_scraper import (
        CounselorTitleSlideInfo,
        MeritBadgeResearchRequest,
        _iter_unrolled_workbook_units,
        fetch_merit_badge_pamphlet_pdf,
    )

    res = fetch_merit_badge_pamphlet_pdf(
        MeritBadgeResearchRequest(
            badge_name=badge_name,
            option_track=option_track,
            counselor_info=CounselorTitleSlideInfo(**counselor_info) if counselor_info else None,
        )
    )
    resolved_badge = str(res.get("badge_name") or badge_name).strip() or "First Aid"
    is_eagle = bool(res.get("is_eagle_required"))
    raw_reqs = list(res.get("requirements") or [])
    _opt_norm, opt_label_raw, reqs = _resolve_option_track_and_filter_reqs(resolved_badge, raw_reqs, option_track)
    opt_label = _sanitize_pdf_text(str(opt_label_raw or option_track or "ALL"))
    norm_c = _extract_normalized_counselor_fields(
        counselor_info,
        default_name="Merit Badge Counselor",
        default_troop="Troop 19, Middleton MA",
    )
    c_name = _sanitize_pdf_text(norm_c["c_name"])
    c_troop = _sanitize_pdf_text(norm_c["c_troop"])

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y_cursor = _draw_branded_pdf_header(
        page=page,
        badge_name=resolved_badge,
        doc_title=f"{resolved_badge} Merit Badge - Counselor Instructor Guide & Answer Key",
        subtitle_line=f"Counselor: {c_name} ({c_troop})  |  Option Track: {opt_label}  |  EDGE Method & GTA Sec. 7.0.3.1",
        kicker_text="SCOUTS BSA COUNSELOR FACILITATOR WORKBOOK & ANSWER KEY",
        is_eagle_required=is_eagle,
    )

    page, y_cursor = _insert_wrapped_pdf_text(
        doc,
        page,
        y_cursor,
        28.0,
        584.0,
        f"Counselor Facilitation Overview ({resolved_badge}): Use this Instructor Guide alongside the slide deck to verify each Scout's individual mastery. Every requirement and sub-requirement below includes official BSA requirement text, Syllabus Bucket classification, EDGE Method teaching notes, expected pamphlet answer keys, common misconceptions, and sign-off criteria.",
        fontsize=7.8,
        fontname="helv",
        color=(0.08, 0.18, 0.36),
        bg_fill=(0.94, 0.97, 1.0),
        border_color=(0.72, 0.82, 0.94),
        left_stripe_color=(0.0, 0.247, 0.529),
        pad_y=3.2,
    )
    y_cursor += 5.0

    units = _iter_unrolled_workbook_units(reqs, badge_name=resolved_badge)
    for idx, u in enumerate(units, start=1):
        r_num = str(u.get("req_number") or u.get("req_id") or str(idx)).strip()
        raw_r_title = str(u.get("topic_title") or u.get("title") or f"Requirement {r_num}").strip()
        r_title = re.sub(r"^Req(?:uirement)?\s+[0-9a-zA-Z().\-]+\s*[:\-]\s*", "", raw_r_title, flags=re.IGNORECASE).strip() or raw_r_title
        r_text = str(u.get("req_text") or "").strip()
        r_bucket = str(u.get("syllabus_bucket") or "In-Class Concept").strip()
        r_mode = str(u.get("execution_mode") or "IN_CLASS_DISCUSSION").strip()
        r_cit = str(u.get("pamphlet_page_citation") or u.get("pamphlet_citation") or f"Official {resolved_badge} Pamphlet").strip()
        excerpts = [str(e) for e in (u.get("pamphlet_excerpts") or []) if str(e).strip()]
        if not excerpts:
            excerpts = [
                f"Official {resolved_badge} Pamphlet Key Point ({r_num} - {r_title}): {r_text[:180]}"
                if r_text
                else f"Verify core principles for Requirement {r_num} ({r_title}) per the official {resolved_badge} Merit Badge Pamphlet."
            ]
        mis = u.get("common_misconception_pair") if isinstance(u.get("common_misconception_pair"), dict) else {}
        myth_str = str(mis.get("misconception") or mis.get("myth") or f"Rushing through Requirement {r_num} without verifying official {resolved_badge} pamphlet criteria.").strip()
        fact_str = str(mis.get("fact") or mis.get("fact_correction") or f"Follow the exact steps in {r_cit} and demonstrate individual mastery to the counselor.").strip()
        signoff = str(u.get("counselor_signoff_criteria") or f"Verify Scout can accurately explain or demonstrate Requirement {r_num} per the official {resolved_badge} Merit Badge Pamphlet.").strip()
        org = u.get("workbook_organizer") or {}
        diagram_url = str(u.get("workbook_diagram_url") or org.get("diagram_url") or "").strip()

        bucket_lower = r_bucket.lower()
        if "prereq" in bucket_lower:
            stripe_rgb = (0.85, 0.47, 0.02)
        elif "demonstration" in bucket_lower or "hands-on" in bucket_lower:
            stripe_rgb = (0.08, 0.50, 0.24)
        elif "make-up" in bucket_lower:
            stripe_rgb = (0.31, 0.27, 0.90)
        elif "follow-up" in bucket_lower or "home-troop" in bucket_lower:
            stripe_rgb = (0.73, 0.11, 0.11)
        else:
            stripe_rgb = (0.0, 0.247, 0.529)

        edge_focus = (
            "Demonstrate & Guide (Hands-On Station)"
            if "HANDS_ON" in r_mode
            else "Guide & Enable (Field / Prerequisite Review)"
            if "PREREQ" in r_mode
            else "Explain & Demonstrate (Socratic Discussion)"
        )

        if u.get("is_group_header"):
            if y_cursor > 690.0:
                page = doc.new_page(width=612, height=792)
                y_cursor = 36.0
            stem_only = r_text.split(":", 1)[0].strip() + ":" if ":" in r_text[:180] else r_text
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                28.0,
                584.0,
                f"[Requirement {r_num} Section Header] {r_title} - {stem_only} ({r_cit})",
                fontsize=8.2,
                fontname="helv",
                color=(0.0, 0.22, 0.48),
                bg_fill=(0.94, 0.97, 1.0),
                border_color=(0.75, 0.84, 0.95),
                left_stripe_color=stripe_rgb,
                pad_y=3.0,
            )
            y_cursor += 3.0
            continue

        if y_cursor > 655.0:
            page = doc.new_page(width=612, height=792)
            y_cursor = 36.0

        parent_dir_pdf = str(u.get("parent_directive") or "").strip()
        soc_qs_pdf = [str(q).strip() for q in (u.get("socratic_questions") or []) if str(q).strip()]
        soc_prompt_line = f"Socratic Prompt (Ask Scouts First): {soc_qs_pdf[0]}\n" if soc_qs_pdf else ""

        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            28.0,
            584.0,
            f"[Requirement {r_num}] {r_title}  |  Bucket: {r_bucket}  |  EDGE: {edge_focus}  |  {r_cit}",
            fontsize=8.3,
            fontname="helv",
            color=(0.0, 0.22, 0.48),
            bg_fill=(0.92, 0.96, 0.99),
            border_color=(0.78, 0.85, 0.94),
            left_stripe_color=stripe_rgb,
            pad_y=3.0,
        )
        req_line_pdf = (
            f"Official Requirement {r_num} [Parent Directive: {parent_dir_pdf}]: {r_text}"
            if parent_dir_pdf
            else f"Official Requirement {r_num}: {r_text}"
        )
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            32.0,
            580.0,
            req_line_pdf,
            fontsize=8.0,
            fontname="helv",
            color=(0.08, 0.12, 0.18),
            pad_y=2.0,
        )
        if diagram_url:
            page, y_cursor = _draw_pdf_workbook_diagram_card(
                doc, page, y_cursor, resolved_badge, r_num, r_title, diagram_url
            )
        # Green [EXPECTED PAMPHLET ANSWER KEY & COUNSELOR RUBRIC] box on 100% of unrolled leaf sub-requirements
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            32.0,
            580.0,
            f"[COUNSELOR FACILITATION & ANSWER KEY] {soc_prompt_line}"
            f"Expected Pamphlet Answer Key & Teaching Points: {' | '.join(excerpts[:3])}\n"
            f"Counselor Mastery & Sign-Off Rubric: {signoff}",
            fontsize=7.5,
            fontname="helv",
            color=(0.05, 0.32, 0.15),
            bg_fill=(0.93, 0.985, 0.95),
            border_color=(0.56, 0.82, 0.65),
            left_stripe_color=(0.08, 0.50, 0.24),
            pad_y=2.8,
        )
        has_real_mis = bool(mis.get("misconception") or mis.get("myth"))
        if has_real_mis:
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                32.0,
                580.0,
                f"Myth vs. Pamphlet Fact: [Myth] {myth_str}  ->  [Fact] {fact_str}",
                fontsize=7.4,
                fontname="helv",
                color=(0.35, 0.22, 0.02),
                bg_fill=(1.0, 0.985, 0.92),
                border_color=(0.88, 0.72, 0.22),
                left_stripe_color=(0.85, 0.55, 0.05),
                pad_y=2.4,
            )
        y_cursor += 4.0

    _finalize_branded_pdf_pages(
        doc=doc,
        badge_name=resolved_badge,
        doc_short_title="COUNSELOR INSTRUCTOR GUIDE & ANSWER KEY",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_field_qr_checklist_pdf(
    badge_name: str,
    counselor_info: Optional[Dict[str, Any]] = None,
    option_track: str = "ALL",
) -> bytes:
    """Generates a branded 1-Page Pocket Field Checklist & QR Reference Handout PDF."""
    import fitz
    from src.tools.scouting_scraper import MeritBadgeResearchRequest, fetch_merit_badge_pamphlet_pdf

    res = fetch_merit_badge_pamphlet_pdf(
        MeritBadgeResearchRequest(badge_name=badge_name, option_track=option_track)
    )
    resolved_badge = str(res.get("badge_name") or badge_name).strip() or "First Aid"
    is_eagle = bool(res.get("is_eagle_required"))
    raw_reqs = list(res.get("requirements") or [])
    _opt_norm, opt_label_raw, reqs = _resolve_option_track_and_filter_reqs(resolved_badge, raw_reqs, option_track)
    opt_label = _sanitize_pdf_text(str(opt_label_raw or option_track or "ALL"))
    pamphlet_url = str(res.get("pamphlet_pdf_url") or "https://www.scouting.org/skills/merit-badges/")
    drg_url = str(res.get("drg_url") or "https://www.scouting.org/skills/merit-badges/")

    norm_c = _extract_normalized_counselor_fields(
        counselor_info,
        default_name="Merit Badge Counselor",
        default_troop="Troop 19, Middleton MA",
    )
    c_name = _sanitize_pdf_text(norm_c["c_name"])
    c_troop = _sanitize_pdf_text(norm_c["c_troop"])

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y_cursor = _draw_branded_pdf_header(
        page=page,
        badge_name=resolved_badge,
        doc_title=f"{resolved_badge} Merit Badge - 1-Page Pocket Field Checklist & QR Reference",
        subtitle_line=f"Counselor: {c_name} ({c_troop})  |  Track: {opt_label}  |  Emergency: 911  |  Poison Help: 1-800-222-1222",
        kicker_text="SCOUTS BSA POCKET FIELD CHECKLIST & DIGITAL QR RESOURCE SHEET",
        is_eagle_required=is_eagle,
    )

    # Emergency & Safety Quick-Call Banner
    page, y_cursor = _insert_wrapped_pdf_text(
        doc,
        page,
        y_cursor,
        28.0,
        584.0,
        "FIELD SAFETY & EMERGENCY NUMBERS: Emergency EMS/Fire: 911  |  National Poison Help Hotline: 1-800-222-1222  |  Always follow Scouting America Youth Protection (YPT) Two-Deep Leadership, the Buddy System, and the Ten Essentials.",
        fontsize=7.8,
        fontname="helv",
        color=(0.45, 0.12, 0.12),
        bg_fill=(1.0, 0.95, 0.95),
        border_color=(0.85, 0.25, 0.25),
        left_stripe_color=(0.80, 0.07, 0.15),
        pad_y=3.2,
    )
    y_cursor += 5.0

    # Real Scannable ISO/IEC 18004 QR Code Quick-Access Reference Cards + Centered BSA Emblem + Full Wrapped URLs
    from src.config import ASSETS_DIR
    from src.tools.qr_generator import encode_qr_matrix

    bsa_logo_path = ASSETS_DIR / "bsa_logo.png"
    has_bsa_logo = bsa_logo_path.exists()
    qr_box_y0 = y_cursor
    qr_box_h = 82.0
    for box_idx, (title_lbl, url_val) in enumerate(
        [
            (f"Official {resolved_badge} Pamphlet PDF", pamphlet_url),
            (f"Scouting.org {resolved_badge} Digital Resource Guide", drg_url),
        ]
    ):
        bx0 = 28.0 if box_idx == 0 else 310.0
        bx1 = 302.0 if box_idx == 0 else 584.0
        card_rect = fitz.Rect(bx0, qr_box_y0, bx1, qr_box_y0 + qr_box_h)
        page.draw_rect(card_rect, color=(0.0, 0.247, 0.529), fill=(0.95, 0.98, 1.0), width=1.1)

        # Render real ISO/IEC 18004 vector QR matrix with quiet zone + centered BSA emblem
        qx0 = bx0 + 7.0
        qy0 = qr_box_y0 + 7.0
        qr_size_pt = 68.0
        qr_outer_rect = fitz.Rect(qx0, qy0, qx0 + qr_size_pt, qy0 + qr_size_pt)
        page.draw_rect(qr_outer_rect, color=(0.0, 0.247, 0.529), fill=(1.0, 1.0, 1.0), width=1.0)
        try:
            qr_matrix = encode_qr_matrix(url_val)
            mod_count = len(qr_matrix)
            quiet_mods = 2
            total_mods = mod_count + quiet_mods * 2
            cell_pt = qr_size_pt / float(total_mods)
            shape = page.new_shape()
            for r_i, row_vals in enumerate(qr_matrix):
                for c_i, is_dark in enumerate(row_vals):
                    if is_dark:
                        mx0 = qx0 + (c_i + quiet_mods) * cell_pt
                        my0 = qy0 + (r_i + quiet_mods) * cell_pt
                        shape.draw_rect(fitz.Rect(mx0, my0, mx0 + cell_pt + 0.08, my0 + cell_pt + 0.08))
            shape.finish(color=None, fill=(0.0, 0.16, 0.36))
            shape.commit()
            if has_bsa_logo:
                logo_box_w = qr_size_pt * 0.21
                lx0 = qx0 + (qr_size_pt - logo_box_w) / 2.0
                ly0 = qy0 + (qr_size_pt - logo_box_w) / 2.0
                logo_bg_rect = fitz.Rect(lx0 - 1.4, ly0 - 1.4, lx0 + logo_box_w + 1.4, ly0 + logo_box_w + 1.4)
                page.draw_rect(logo_bg_rect, color=(0.0, 0.247, 0.529), fill=(1.0, 1.0, 1.0), width=0.6)
                page.insert_image(fitz.Rect(lx0, ly0, lx0 + logo_box_w, ly0 + logo_box_w), filename=str(bsa_logo_path), keep_proportion=True)
        except Exception:
            pass

        text_x0 = qx0 + qr_size_pt + 7.0
        text_x1 = bx1 - 5.0
        text_w = text_x1 - text_x0
        clean_title = _sanitize_pdf_text(title_lbl)
        title_lines = _wrap_pdf_lines(clean_title, text_w, fontsize=8.1)
        ty = qr_box_y0 + 16.0
        for tl in title_lines[:2]:
            page.insert_text(fitz.Point(text_x0, ty), tl, fontsize=8.1, fontname="helv", color=(0.0, 0.22, 0.48))
            ty += 9.5
        page.insert_text(fitz.Point(text_x0, ty + 1.0), "Scan QR or click card to open official BSA resource:", fontsize=6.8, fontname="helv", color=(0.25, 0.32, 0.42))
        ty += 10.5
        clean_url = _sanitize_pdf_text(url_val)
        url_char_cap = max(24, int(text_w / 3.15))
        url_chunks = [clean_url[i : i + url_char_cap] for i in range(0, len(clean_url), url_char_cap)]
        for u_line in url_chunks[:3]:
            page.insert_text(fitz.Point(text_x0, ty), u_line, fontsize=6.2, fontname="helv", color=(0.02, 0.38, 0.75))
            ty += 8.0
        try:
            page.insert_link({"kind": fitz.LINK_URI, "from": card_rect, "uri": url_val})
        except Exception:
            pass

    y_cursor = qr_box_y0 + qr_box_h + 8.0

    page, y_cursor = _insert_wrapped_pdf_text(
        doc,
        page,
        y_cursor,
        28.0,
        584.0,
        f"{resolved_badge} Pocket Requirement & Field Station Verification Checklist",
        fontsize=9.2,
        fontname="helv",
        color=(0.0, 0.22, 0.48),
        bg_fill=(0.91, 0.95, 0.99),
        border_color=(0.76, 0.84, 0.94),
        left_stripe_color=(0.0, 0.247, 0.529),
        pad_y=3.2,
    )

    gear_collected: List[str] = []
    for r in reqs[:12]:
        r_num = str(r.get("req_number") or "").strip()
        r_topic = str(r.get("topic_title") or r.get("req_text") or "").strip()
        r_bucket = str(r.get("syllabus_bucket") or "In-Class").strip()
        for g_item in (r.get("gear_checklist") or [])[:2]:
            if str(g_item).strip() and str(g_item).strip() not in gear_collected:
                gear_collected.append(str(g_item).strip())
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            32.0,
            580.0,
            f"[ ] Req {r_num} ({r_bucket}): {r_topic}",
            fontsize=8.0,
            fontname="helv",
            color=(0.08, 0.14, 0.22),
            pad_y=2.2,
        )

    if not gear_collected:
        gear_collected = [
            f"Official Scouting America {resolved_badge} Merit Badge Pamphlet",
            "Signed Application for Merit Badge (Blue Card #34124)",
            "Scout Basic Essentials (First-Aid Kit, Water Bottle, Flashlight, Trail Food, Sun Protection)",
        ]

    y_cursor += 4.0
    page, y_cursor = _insert_wrapped_pdf_text(
        doc,
        page,
        y_cursor,
        28.0,
        584.0,
        "Essential Field Gear & Station Readiness Reminders:  " + "  |  ".join(f"[ ] {g}" for g in gear_collected[:6]),
        fontsize=7.8,
        fontname="helv",
        color=(0.35, 0.22, 0.02),
        bg_fill=(1.0, 0.98, 0.90),
        border_color=(0.88, 0.72, 0.22),
        left_stripe_color=(0.992, 0.725, 0.075),
        pad_y=3.2,
    )

    _finalize_branded_pdf_pages(
        doc=doc,
        badge_name=resolved_badge,
        doc_short_title="1-PAGE POCKET FIELD CHECKLIST & QR REFERENCE",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _parse_five_part_speaker_notes(
    notes_raw: str,
    fallback_pacing: str,
    fallback_ask: str,
    fallback_answer_key: str,
    fallback_misconception: str,
    fallback_rubric: str,
) -> Dict[str, str]:
    """Parses the 5-Part Facilitator Guide blocks from speaker_notes/presenter_notes while preserving any custom text."""
    text = str(notes_raw or "").strip()
    out = {
        "pacing": fallback_pacing,
        "ask_first": fallback_ask,
        "answer_key": fallback_answer_key,
        "misconception": fallback_misconception,
        "rubric": fallback_rubric,
    }
    if not text:
        return out

    tag_pattern = re.compile(
        r"\[("
        r"PACING & MODALITY|PACING|"
        r"ASK SCOUTS FIRST|ASK SCOUTS|"
        r"EXPECTED PAMPHLET ANSWER KEY|ANSWER KEY|SAY|"
        r"COMMON MISCONCEPTION TO CORRECT|MISCONCEPTION|MYTH VS\.? FACT|"
        r"DEMONSTRATION & SIGN-OFF RUBRIC|DEMONSTRATE|SIGN-OFF RUBRIC"
        r")[^\]]*\]",
        re.IGNORECASE,
    )
    matches = list(tag_pattern.finditer(text))
    if not matches:
        # Entire speaker_notes string is custom counselor notes: preserve in full inside answer_key / pacing
        out["answer_key"] = f"{text} | {fallback_answer_key}" if fallback_answer_key not in text else text
        return out

    leading_custom = text[: matches[0].start()].strip(" \t\r\n-|:")
    for idx_m, m in enumerate(matches):
        raw_tag = m.group(1).upper()
        seg_start = m.end()
        seg_end = matches[idx_m + 1].start() if idx_m + 1 < len(matches) else len(text)
        seg_val = re.sub(r"\s+", " ", text[seg_start:seg_end]).strip(" \t\r\n-|:")
        if not seg_val:
            continue
        if "PACING" in raw_tag:
            out["pacing"] = seg_val
        elif "ASK" in raw_tag:
            out["ask_first"] = seg_val
        elif "ANSWER" in raw_tag or raw_tag == "SAY":
            out["answer_key"] = seg_val
        elif "MISCONCEPTION" in raw_tag or "MYTH" in raw_tag:
            out["misconception"] = seg_val
        elif "DEMONSTRAT" in raw_tag or "RUBRIC" in raw_tag or "SIGN-OFF" in raw_tag:
            out["rubric"] = seg_val

    if leading_custom:
        out["pacing"] = f"{leading_custom} | {out['pacing']}"
    return out


def generate_counselor_cue_cards_pdf(
    badge_name: str,
    slides: Optional[List[Dict[str, Any]]] = None,
    counselor_info: Optional[Dict[str, Any]] = None,
    option_track: str = "ALL",
) -> bytes:
    """Generates branded printable 3x5 / 4x6 Counselor Pocket Cue Cards (2 cards per page with 5-Part Facilitator Guide blocks)."""
    import fitz
    from src.tools.scouting_scraper import MeritBadgeResearchRequest, fetch_merit_badge_pamphlet_pdf

    norm_c = _extract_normalized_counselor_fields(
        counselor_info,
        default_name="Merit Badge Counselor",
        default_troop="Troop 19, Middleton MA",
    )
    c_name = _sanitize_pdf_text(norm_c["c_name"])
    c_troop = _sanitize_pdf_text(norm_c["c_troop"])

    resolved_badge = str(badge_name or "First Aid").strip()
    res = fetch_merit_badge_pamphlet_pdf(
        MeritBadgeResearchRequest(badge_name=resolved_badge, option_track=option_track)
    )
    resolved_badge = str(res.get("badge_name") or resolved_badge)
    raw_reqs = list(res.get("requirements") or [])
    _opt_norm, opt_label_raw, reqs = _resolve_option_track_and_filter_reqs(resolved_badge, raw_reqs, option_track)
    opt_label = _sanitize_pdf_text(str(opt_label_raw or option_track or "ALL"))
    req_lookup = {str(r.get("req_number") or "").strip(): r for r in reqs}

    card_items: List[Dict[str, str]] = []
    if slides:
        for idx, s in enumerate(slides, start=1):
            s_dict = s.model_dump() if hasattr(s, "model_dump") else dict(s)
            r_num = str(s_dict.get("req_number") or f"Slide {idx}").strip()
            title = str(s_dict.get("title") or f"{resolved_badge} - {r_num}").strip()
            bullets = [str(b) for b in (s_dict.get("bullet_points") or []) if str(b).strip()]
            notes_raw = str(s_dict.get("speaker_notes") or s_dict.get("presenter_notes") or "").strip()
            matched_req = req_lookup.get(r_num) or req_lookup.get(re.sub(r"^Req\s*", "", r_num, flags=re.I).strip()) or {}
            r_bucket = str(s_dict.get("syllabus_bucket") or matched_req.get("syllabus_bucket") or "In-Class Guided Station").strip()
            r_cit = str(s_dict.get("pamphlet_citation") or matched_req.get("pamphlet_page_citation") or f"Official {resolved_badge} Pamphlet").strip()
            excerpts = [str(e) for e in (matched_req.get("pamphlet_excerpts") or []) if str(e).strip()]
            mis = matched_req.get("common_misconception_pair") if isinstance(matched_req.get("common_misconception_pair"), dict) else {}

            fb_pacing = f"5-8 min | {r_bucket} (EDGE Method) | Source: {r_cit}"
            fb_ask = f"How would your patrol apply {r_num} ({title}) during a troop campout or field scenario?"
            fb_answer = " | ".join(bullets[:2]) if bullets else (" | ".join(excerpts[:2]) if excerpts else f"Review core concepts for {title} in the official {resolved_badge} Merit Badge Pamphlet.")
            fb_mis = (
                f"Myth: {mis.get('misconception')} -> Pamphlet Fact: {mis.get('fact')}"
                if (mis.get("misconception") and mis.get("fact"))
                else f"Avoid skipping safety or pre-check steps on {r_num}; verify against the official {resolved_badge} pamphlet."
            )
            fb_rubric = str(
                matched_req.get("counselor_signoff_criteria")
                or (bullets[1] if len(bullets) > 1 else f"Demonstrate step-by-step mastery for {r_num} using the BSA EDGE Method (GTA Sec. 7.0.3.1).")
            )

            parsed_5 = _parse_five_part_speaker_notes(
                notes_raw=notes_raw,
                fallback_pacing=fb_pacing,
                fallback_ask=fb_ask,
                fallback_answer_key=fb_answer,
                fallback_misconception=fb_mis,
                fallback_rubric=fb_rubric,
            )
            card_items.append(
                {
                    "req_badge": f"Req {r_num}" if not r_num.lower().startswith(("req", "slide")) else r_num,
                    "title": title,
                    **parsed_5,
                }
            )
    else:
        for idx, r in enumerate(reqs, start=1):
            r_num = str(r.get("req_number") or str(idx)).strip()
            title = str(r.get("topic_title") or f"{resolved_badge} Requirement {r_num}").strip()
            r_text = str(r.get("req_text") or "").strip()
            r_bucket = str(r.get("syllabus_bucket") or "In-Class Concept").strip()
            r_mode = str(r.get("execution_mode") or "IN_CLASS_DISCUSSION").strip()
            r_cit = str(r.get("pamphlet_page_citation") or r.get("pamphlet_citation") or f"Official {resolved_badge} Pamphlet").strip()
            excerpts = [str(e) for e in (r.get("pamphlet_excerpts") or []) if str(e).strip()]
            mis = r.get("common_misconception_pair") if isinstance(r.get("common_misconception_pair"), dict) else {}
            pacing_txt = f"6-10 min | {r_bucket} ({r_mode.replace('_', ' ').title()}) | {r_cit}"
            ask_txt = f"What is the most important safety or procedural rule in {resolved_badge} Requirement {r_num}, and why?"
            answer_txt = " | ".join(excerpts[:2]) if excerpts else (r_text or f"Core concepts from {resolved_badge} Pamphlet for Requirement {r_num}.")
            mis_txt = (
                f"Myth: {mis.get('misconception')} -> Pamphlet Fact: {mis.get('fact')}"
                if (mis.get("misconception") and mis.get("fact"))
                else f"Myth: Group observation satisfies {r_num}. -> Fact: Each Scout must individually explain or demonstrate {r_num}."
            )
            rubric_txt = str(
                r.get("counselor_signoff_criteria")
                or f"Guide Scouts through a hands-on EDGE demonstration and individual verification for Requirement {r_num}."
            )
            card_items.append(
                {
                    "req_badge": f"Requirement {r_num}",
                    "title": title,
                    "pacing": pacing_txt,
                    "ask_first": ask_txt,
                    "answer_key": answer_txt,
                    "misconception": mis_txt,
                    "rubric": rubric_txt,
                }
            )

    if not card_items:
        card_items.append(
            {
                "req_badge": "Requirement 1",
                "title": f"{resolved_badge} Core Safety & Fundamentals",
                "pacing": f"8 min | In-Class Concept (EDGE Explain & Demonstrate) | Official {resolved_badge} Pamphlet",
                "ask_first": "Which hazard is most common in our local council terrain, and how do we prevent it?",
                "answer_key": f"Introduce {resolved_badge} hazards and prevention using the official Scouting America pamphlet.",
                "misconception": "Myth: Equipment checks are only needed before campouts. -> Fact: Inspect gear before every session.",
                "rubric": "Walk through equipment inspection and verify each Scout's individual buddy-pair station setup.",
            }
        )

    doc = fitz.open()
    for i in range(0, len(card_items), 2):
        page = doc.new_page(width=612, height=792)
        _draw_branded_pdf_header(
            page=page,
            badge_name=resolved_badge,
            doc_title=f"{resolved_badge} Merit Badge - Printable Counselor Pocket Cue Cards",
            subtitle_line=f"Counselor: {c_name} ({c_troop})  |  Track: {opt_label}  |  2 Cards/Page (5-Part Facilitator Guide)",
            kicker_text="SCOUTS BSA 4x6 POCKET FACILITATOR CUE CARDS (EDGE METHOD)",
        )
        pair = card_items[i : i + 2]
        for slot_idx, card in enumerate(pair):
            card_top = 94.0 if slot_idx == 0 else 428.0
            card_bot = 402.0 if slot_idx == 0 else 736.0
            card_rect = fitz.Rect(32.0, card_top, 580.0, card_bot)
            page.draw_rect(card_rect, color=(0.0, 0.247, 0.529), fill=(0.985, 0.992, 1.0), width=1.3)
            page.draw_rect(fitz.Rect(32.0, card_top, 580.0, card_top + 22.0), color=(0.0, 0.247, 0.529), fill=(0.0, 0.247, 0.529))
            page.insert_text(
                fitz.Point(40.0, card_top + 15.0),
                _sanitize_pdf_text(f"[{card['req_badge']}]  {card['title']}  ({resolved_badge} - {opt_label})")[:86],
                fontsize=8.6,
                fontname="helv",
                color=(1.0, 1.0, 1.0),
            )
            cy = card_top + 26.0
            five_blocks = [
                ("[PACING & MODALITY]", card["pacing"], (0.31, 0.27, 0.90), (0.95, 0.96, 1.0)),
                ("[ASK SCOUTS FIRST]", card["ask_first"], (0.85, 0.50, 0.05), (1.0, 0.98, 0.91)),
                ("[EXPECTED PAMPHLET ANSWER KEY]", card["answer_key"], (0.0, 0.247, 0.529), (0.93, 0.96, 1.0)),
                ("[COMMON MISCONCEPTION TO CORRECT]", card["misconception"], (0.80, 0.26, 0.05), (1.0, 0.96, 0.93)),
                ("[DEMONSTRATION & SIGN-OFF RUBRIC]", card["rubric"], (0.08, 0.50, 0.24), (0.93, 0.98, 0.95)),
            ]
            for tag_lbl, body_val, stripe_c, bg_c in five_blocks:
                if cy + 16.0 > card_bot - 4.0:
                    break
                # Wrap compactly (max 3 lines per block) so all 5 facilitator blocks fit cleanly inside the 4x6 pocket card
                block_text = f"{tag_lbl} {body_val}"
                wrapped_lines = _wrap_pdf_lines(block_text, 514.0, fontname="helv", fontsize=7.1)[:3]
                line_h = 8.8
                box_h = len(wrapped_lines) * line_h + 4.0
                if cy + box_h > card_bot - 3.0:
                    avail_lines = max(1, int((card_bot - 3.0 - cy - 4.0) // line_h))
                    wrapped_lines = wrapped_lines[:avail_lines]
                    box_h = len(wrapped_lines) * line_h + 4.0
                page.draw_rect(
                    fitz.Rect(40.0, cy, 572.0, cy + box_h),
                    color=(0.78, 0.84, 0.92),
                    fill=bg_c,
                )
                page.draw_rect(
                    fitz.Rect(40.0, cy, 44.0, cy + box_h),
                    color=stripe_c,
                    fill=stripe_c,
                )
                for l_i, l_str in enumerate(wrapped_lines):
                    page.insert_text(
                        fitz.Point(48.0, cy + 2.0 + (l_i + 0.82) * line_h),
                        l_str,
                        fontsize=7.1,
                        fontname="helv",
                        color=(0.08, 0.14, 0.22),
                    )
                cy += box_h + 2.5

            if slot_idx == 0 and len(pair) > 1:
                # Dashed cut line between Card 1 and Card 2
                for dx in range(28, 580, 14):
                    page.draw_line(
                        fitz.Point(float(dx), 415.0),
                        fitz.Point(float(min(dx + 8, 584)), 415.0),
                        color=(0.45, 0.52, 0.62),
                        width=0.9,
                    )
                page.insert_text(
                    fitz.Point(242.0, 412.5),
                    "--- CUT ALONG DASHED LINE (4x6 POCKET CARD) ---",
                    fontsize=6.8,
                    fontname="helv",
                    color=(0.35, 0.42, 0.52),
                )

    _finalize_branded_pdf_pages(
        doc=doc,
        badge_name=resolved_badge,
        doc_short_title="COUNSELOR POCKET CUE CARDS (5-PART FACILITATOR GUIDE)",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_organizer_spec_pdf(
    badge_name: str,
    counselor_info: Optional[Dict[str, Any]] = None,
    option_track: str = "ALL",
) -> bytes:
    """Generates a branded 1-Page MBC Dean & Summer Camp Program Director Course Catalog & Facility Spec Sheet PDF."""
    import fitz

    spec = generate_organizer_syllabus_spec_sheet(
        badge_name=badge_name,
        counselor_info=counselor_info,
        option_track=option_track,
    )
    resolved_badge = str(spec.get("badge_name") or badge_name).strip() or "First Aid"
    opt_label = _sanitize_pdf_text(str(spec.get("option_label") or option_track or "ALL"))
    norm_c = _extract_normalized_counselor_fields(
        counselor_info,
        default_name="Merit Badge Counselor",
        default_troop="Troop 19, Middleton MA",
    )
    c_name = _sanitize_pdf_text(norm_c["c_name"])
    c_troop = _sanitize_pdf_text(norm_c["c_troop"])

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y_cursor = _draw_branded_pdf_header(
        page=page,
        badge_name=resolved_badge,
        doc_title=f"{resolved_badge} Merit Badge - Organizer Course Catalog & Facility Spec Sheet",
        subtitle_line=f"Instructor: {c_name} ({c_troop})  |  Option Track: {opt_label}  |  Max Cap: {spec.get('max_scouts', 16)} Scouts",
        kicker_text="MBC DEAN & SUMMER CAMP PROGRAM DIRECTOR COURSE SPECIFICATION",
    )

    sections = [
        (
            "1. Recommended Period Length, Section Cap & Target Audience",
            f"Recommended Schedule Format: {spec.get('session_mode', '4-Session Merit Badge Clinic + Make-Up Day')} (or 2x 150-min Double-Block / 4x 50-min Camp Blocks)\n"
            f"Maximum Section Capacity: {spec.get('max_scouts', 16)} Scouts (paired into Buddy Teams per Scouting America YPT)\n"
            f"Recommended Age / Rank Readiness: {spec.get('min_age_or_rank', 'All Scouts (Ages 11-17)')}",
            (0.0, 0.247, 0.529),
        ),
        (
            "2. Classroom, Outdoor Facility & AV Requirements",
            f"Facility & AV Setup: {spec.get('room_needs', 'Projector/TV + Tables for Buddy Stations')}\n"
            "Safety & Supervision: Requires Two-Deep Adult Leadership room layout with clear sightlines for hands-on skill stations.",
            (0.08, 0.50, 0.24),
        ),
        (
            "3. Pre-Class Prerequisites vs. In-Class Completions Breakdown",
            f"Pre-Class Prerequisites (Do Before Session 1): {', '.join(spec.get('prerequisite_reqs') or []) or 'Read Pamphlet Chapter 1'}\n"
            f"In-Class Completed Requirements: {', '.join(spec.get('in_class_reqs') or []) or 'All core discussion & skill station requirements'}\n"
            f"Make-Up Day Eligible Requirements: {', '.join(spec.get('makeup_reqs') or []) or 'Any missed concept review'}\n"
            f"Post-Class Home-Troop Follow-Up Items: {', '.join(spec.get('followup_reqs') or []) or 'None'}",
            (0.85, 0.47, 0.02),
        ),
        (
            "4. Quartermaster Equipment & Event Catalog Blurb",
            f"Quartermaster Station Kit: Official {resolved_badge} Merit Badge Pamphlets, Buddy Station props, and Blue Card (#34124) sign-off packet.\n"
            f"Copy-Paste Event Catalog Description: {spec.get('catalog_blurb', '')}",
            (0.31, 0.27, 0.90),
        ),
    ]

    for hdr, body, stripe_c in sections:
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            28.0,
            584.0,
            hdr,
            fontsize=9.2,
            fontname="helv",
            color=(0.0, 0.22, 0.48),
            bg_fill=(0.92, 0.96, 0.99),
            border_color=(0.78, 0.85, 0.94),
            left_stripe_color=stripe_c,
            pad_y=3.5,
        )
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            32.0,
            580.0,
            body,
            fontsize=8.3,
            fontname="helv",
            color=(0.08, 0.14, 0.22),
            pad_y=3.0,
        )
        y_cursor += 5.0

    _finalize_branded_pdf_pages(
        doc=doc,
        badge_name=resolved_badge,
        doc_short_title="ORGANIZER COURSE CATALOG & FACILITY SPEC SHEET",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_gear_and_rotator_pdf(
    badge_name: str,
    patrol_size: int = 8,
    station_minutes: int = 12,
    counselor_info: Optional[Dict[str, Any]] = None,
    option_track: str = "ALL",
) -> bytes:
    """Generates a branded PDF combining the Master Quartermaster Gear Checklist and Timed Patrol Skill Station Rotation Matrix."""
    import fitz
    from src.tools.scouting_scraper import MeritBadgeResearchRequest, fetch_merit_badge_pamphlet_pdf

    res = fetch_merit_badge_pamphlet_pdf(
        MeritBadgeResearchRequest(badge_name=badge_name, option_track=option_track)
    )
    resolved_badge = str(res.get("badge_name") or badge_name).strip() or "First Aid"
    raw_reqs = list(res.get("requirements") or [])
    _opt_norm, opt_label_raw, reqs = _resolve_option_track_and_filter_reqs(resolved_badge, raw_reqs, option_track)
    opt_label = _sanitize_pdf_text(str(opt_label_raw or option_track or "ALL"))
    p_size = max(2, int(patrol_size or 8))
    s_mins = max(5, int(station_minutes or 12))
    buddy_pairs = max(1, (p_size + 1) // 2)

    norm_c = _extract_normalized_counselor_fields(
        counselor_info,
        default_name="Merit Badge Counselor",
        default_troop="Troop 19, Middleton MA",
    )
    c_name = _sanitize_pdf_text(norm_c["c_name"])
    c_troop = _sanitize_pdf_text(norm_c["c_troop"])

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y_cursor = _draw_branded_pdf_header(
        page=page,
        badge_name=resolved_badge,
        doc_title=f"{resolved_badge} Merit Badge - Quartermaster Gear & Patrol Station Rotator",
        subtitle_line=f"Counselor: {c_name} ({c_troop})  |  Track: {opt_label}  |  Patrol: {p_size} Scouts ({buddy_pairs} Pairs)  |  {s_mins} Min/Station",
        kicker_text="SCOUTS BSA QUARTERMASTER LOGISTICS & EDGE SKILL STATION ROTATOR",
    )

    page, y_cursor = _insert_wrapped_pdf_text(
        doc,
        page,
        y_cursor,
        28.0,
        584.0,
        f"Part 1: Master Quartermaster Gear & Skill Station Packing Checklist (Scaled for {p_size} Scouts / {buddy_pairs} Buddy Teams - Track: {opt_label})",
        fontsize=9.2,
        fontname="helv",
        color=(0.0, 0.22, 0.48),
        bg_fill=(0.91, 0.95, 0.99),
        border_color=(0.76, 0.84, 0.94),
        left_stripe_color=(0.0, 0.247, 0.529),
        pad_y=3.5,
    )

    gear_items: List[str] = [
        f"[ ] {p_size}x Fillable Form (GTA Sec. 7.0.3.2) {resolved_badge} Scout Workbooks & Blue Cards (#34124)",
        f"[ ] {buddy_pairs}x Official Scouting America {resolved_badge} Merit Badge Pamphlets (1 per Buddy Team)",
        f"[ ] {buddy_pairs}x Station Sanitization, PPE & Safety Check Kits (BSA Guide to Safe Scouting)",
    ]
    for r in reqs:
        r_num = str(r.get("req_number") or "")
        for g in (r.get("gear_checklist") or [])[:2]:
            if str(g).strip():
                gear_items.append(f"[ ] {buddy_pairs}x Sets (Req {r_num}): {g}")

    for gi in gear_items[:12]:
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            32.0,
            580.0,
            gi,
            fontsize=8.1,
            fontname="helv",
            color=(0.08, 0.14, 0.22),
            pad_y=2.0,
        )

    y_cursor += 6.0
    page, y_cursor = _insert_wrapped_pdf_text(
        doc,
        page,
        y_cursor,
        28.0,
        584.0,
        f"Part 2: Timed Patrol & Buddy Skill Station Rotation Matrix ({s_mins} Minutes Per Station)",
        fontsize=9.2,
        fontname="helv",
        color=(0.0, 0.22, 0.48),
        bg_fill=(0.91, 0.95, 0.99),
        border_color=(0.76, 0.84, 0.94),
        left_stripe_color=(0.08, 0.50, 0.24),
        pad_y=3.5,
    )

    hands_on = [r for r in reqs if str(r.get("execution_mode", "")).upper() == "HANDS_ON_SKILL_STATION"] or reqs[:4]
    stations = hands_on[:4]
    while len(stations) < 4 and reqs:
        stations.append(reqs[len(stations) % len(reqs)])

    for rot_idx, st in enumerate(stations, start=1):
        t_start = (rot_idx - 1) * s_mins
        t_end = rot_idx * s_mins
        r_num = str(st.get("req_number") or str(rot_idx))
        r_title = str(st.get("topic_title") or f"{resolved_badge} Skill Station {rot_idx}")
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            32.0,
            580.0,
            f"Rotation {rot_idx} ({t_start:02d}:00 - {t_end:02d}:00 | {s_mins} min) - Station {rot_idx} [Req {r_num}]: {r_title}\n"
            f"   Buddy Teams A/B/C/D rotate clockwise -> Demonstrate skill using EDGE Method -> Peer Buddy Check & Counselor Initials",
            fontsize=8.1,
            fontname="helv",
            color=(0.08, 0.14, 0.22),
            bg_fill=(0.97, 0.99, 0.98),
            border_color=(0.78, 0.88, 0.82),
            left_stripe_color=(0.08, 0.50, 0.24),
            pad_y=3.0,
        )
        y_cursor += 3.0

    _finalize_branded_pdf_pages(
        doc=doc,
        badge_name=resolved_badge,
        doc_short_title="QUARTERMASTER GEAR & PATROL ROTATION MATRIX",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


generate_quartermaster_and_rotator_pdf = generate_gear_and_rotator_pdf


def generate_bluecards_pdf(
    badge_name: str,
    roster: Optional[List[Dict[str, Any]]] = None,
    counselor_info: Optional[Dict[str, Any]] = None,
    signoff_date: str = "",
    mode: str = "3panel",
) -> bytes:
    """Renders authentic 3-column perforated BSA Application for Merit Badge (#34124) Blue Cards ('3panel') or Patrol Sign-Off Matrix ('sheet')."""
    import fitz
    from src.tools.scouting_scraper import MeritBadgeResearchRequest, fetch_merit_badge_pamphlet_pdf

    res = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name=badge_name))
    resolved_badge = str(res.get("badge_name") or badge_name).strip() or "First Aid"
    reqs = list(res.get("requirements") or [])
    req_nums = [str(r.get("req_number") or "") for r in reqs if str(r.get("req_number") or "").strip()] or ["1", "2", "3", "4", "5"]

    norm_c = _extract_normalized_counselor_fields(
        counselor_info,
        default_name="Merit Badge Counselor",
        default_troop="Troop 19, Middleton MA",
    )
    c_name = _sanitize_pdf_text(norm_c["c_name"])
    c_troop = _sanitize_pdf_text(norm_c["c_troop"])
    c_email = _sanitize_pdf_text(norm_c["c_email"])
    eff_date = _sanitize_pdf_text(signoff_date or "2026-10-27")

    effective_roster = list(roster or [])
    if not effective_roster:
        effective_roster = [
            {
                "scout_name": "Scout Roster Entry 1",
                "troop_number": "Troop 19",
                "patrol_name": "Eagle Patrol",
                "completed_reqs": req_nums[:-1] if len(req_nums) > 1 else req_nums,
                "partial_reqs": req_nums[-1:] if len(req_nums) > 1 else [],
            },
            {
                "scout_name": "Scout Roster Entry 2",
                "troop_number": "Troop 42",
                "patrol_name": "Fox Patrol",
                "completed_reqs": req_nums,
                "partial_reqs": [],
            },
        ]

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    mode_norm = str(mode or "3panel").strip().lower()

    if mode_norm == "sheet":
        y_cursor = _draw_branded_pdf_header(
            page=page,
            badge_name=resolved_badge,
            doc_title=f"{resolved_badge} Merit Badge - Patrol Blue Card (#34124) & Scoutbook Sign-Off Sheet",
            subtitle_line=f"Counselor: {c_name} ({c_troop})  |  Sign-Off Date: {eff_date}  |  Scoutbook Plus Ready",
            kicker_text="SCOUTS BSA PATROL ADVANCEMENT & BLUE CARD (#34124) SIGN-OFF MATRIX",
        )
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            28.0,
            584.0,
            f"Patrol Requirement Sign-Off Matrix ({resolved_badge}): Check off completed requirements per Scout for Blue Card (#34124) and Scoutbook Plus CSV advancement import.",
            fontsize=8.0,
            fontname="helv",
            color=(0.08, 0.18, 0.36),
            bg_fill=(0.94, 0.97, 1.0),
            border_color=(0.72, 0.82, 0.94),
            left_stripe_color=(0.0, 0.247, 0.529),
            pad_y=3.2,
        )
        y_cursor += 5.0
        for sc_idx, sc in enumerate(effective_roster, start=1):
            s_name = str(sc.get("scout_name") or f"Scout {sc_idx}")
            s_troop = str(sc.get("troop_number") or sc.get("troop_unit") or "Troop")
            comp = [str(x) for x in (sc.get("completed_reqs") or req_nums)]
            part = [str(x) for x in (sc.get("partial_reqs") or []) if str(x) not in comp]
            status_lbl = "COMPLETE" if not part else "PARTIAL"
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                28.0,
                584.0,
                f"{sc_idx}. {s_name} ({s_troop})  |  Badge: {resolved_badge}  |  Status: {status_lbl}  |  Date: {eff_date}\n"
                f"   Completed Reqs: {', '.join(comp) if comp else 'None'}   |   Remaining Partial Reqs: {', '.join(part) if part else 'None (Full Completion)'}\n"
                f"   Counselor Signature: {c_name} ({c_troop})   |   Unit Leader Verification: ________________________",
                fontsize=8.1,
                fontname="helv",
                color=(0.08, 0.14, 0.22),
                bg_fill=(0.96, 0.985, 1.0) if sc_idx % 2 == 1 else (0.99, 0.995, 1.0),
                border_color=(0.76, 0.84, 0.94),
                left_stripe_color=(0.08, 0.50, 0.24) if status_lbl == "COMPLETE" else (0.85, 0.47, 0.02),
                pad_y=3.5,
            )
            y_cursor += 4.0
    else:
        y_cursor = _draw_branded_pdf_header(
            page=page,
            badge_name=resolved_badge,
            doc_title=f"{resolved_badge} Merit Badge - 3-Panel Perforated Blue Cards (#34124)",
            subtitle_line=f"Counselor: {c_name} ({c_troop})  |  Date: {eff_date}  |  Royal Blue (#003F87) & Gold",
            kicker_text="APPLICATION FOR MERIT BADGE (#34124) - 3-PANEL PERFORATED RECORD",
        )
        for sc_idx, sc in enumerate(effective_roster):
            if y_cursor + 210.0 > 748.0:
                page = doc.new_page(width=612, height=792)
                y_cursor = 36.0
            s_name = _sanitize_pdf_text(str(sc.get("scout_name") or f"Scout {sc_idx + 1}"))
            s_troop = _sanitize_pdf_text(str(sc.get("troop_number") or sc.get("troop_unit") or "Troop 19"))
            comp = [str(x) for x in (sc.get("completed_reqs") or req_nums)]
            part = [str(x) for x in (sc.get("partial_reqs") or []) if str(x) not in comp]

            card_top = y_cursor
            card_h = 196.0
            card_bot = card_top + card_h
            outer_rect = fitz.Rect(28.0, card_top, 584.0, card_bot)
            page.draw_rect(outer_rect, color=(0.0, 0.247, 0.529), fill=(0.94, 0.975, 1.0), width=1.5)

            panel_w = (584.0 - 28.0) / 3.0
            panels = [
                ("PART 1: APPLICATION FOR MERIT BADGE", "To Scoutmaster / Unit Leader"),
                ("PART 2: APPLICANT'S RECORD", "Retained by Scout for Eagle Rank"),
                ("PART 3: COUNSELOR'S RECORD", "Retained by Merit Badge Counselor"),
            ]
            for p_i, (p_title, p_sub) in enumerate(panels):
                px0 = 28.0 + p_i * panel_w
                px1 = px0 + panel_w
                # Royal Blue (#003F87) & Gold header bar on each panel
                page.draw_rect(fitz.Rect(px0, card_top, px1, card_top + 22.0), color=(0.0, 0.247, 0.529), fill=(0.0, 0.247, 0.529))
                page.draw_rect(fitz.Rect(px0, card_top + 20.0, px1, card_top + 22.5), color=(0.992, 0.725, 0.075), fill=(0.992, 0.725, 0.075))
                page.insert_text(fitz.Point(px0 + 5.0, card_top + 11.0), p_title, fontsize=6.5, fontname="helv", color=(1.0, 1.0, 1.0))
                page.insert_text(fitz.Point(px0 + 5.0, card_top + 18.0), p_sub, fontsize=5.8, fontname="helv", color=(0.992, 0.78, 0.20))

                py = card_top + 28.0
                panel_text = (
                    f"Merit Badge: {resolved_badge} (#34124)\n"
                    f"Scout: {s_name}\n"
                    f"Unit: {s_troop}\n"
                    f"Completed Reqs: {', '.join(comp[:10])}\n"
                    f"Partials: {', '.join(part[:6]) if part else 'None (Complete)'}\n"
                    f"Date Signed: {eff_date}\n"
                    f"Counselor: {c_name}\n"
                    f"Affiliation: {c_troop}\n"
                    f"Contact: {c_email}\n"
                    "Unit Leader Sig: __________________"
                )
                page, _ = _insert_wrapped_pdf_text(
                    doc,
                    page,
                    py,
                    px0 + 4.0,
                    px1 - 4.0,
                    panel_text,
                    fontsize=7.1,
                    fontname="helv",
                    color=(0.04, 0.14, 0.30),
                    pad_x=3.0,
                    pad_y=2.0,
                    max_y=card_bot - 4.0,
                )

                if p_i > 0:
                    # Perforated vertical fold/tear line between panels
                    for dy in range(int(card_top), int(card_bot), 10):
                        page.draw_line(
                            fitz.Point(px0, float(dy)),
                            fitz.Point(px0, float(min(dy + 5, int(card_bot)))),
                            color=(0.0, 0.247, 0.529),
                            width=0.9,
                        )

            y_cursor = card_bot + 12.0

    _finalize_branded_pdf_pages(
        doc=doc,
        badge_name=resolved_badge,
        doc_short_title="APPLICATION FOR MERIT BADGE (#34124) BLUE CARDS",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes




