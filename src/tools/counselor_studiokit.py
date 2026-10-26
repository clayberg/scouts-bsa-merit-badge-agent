"""Interactive Counselor AI Studio Toolkit (`src/tools/counselor_studiokit.py`).

Provides AI-assisted Merit Badge Counselor session planning and communication tools:
1. `generate_counselor_session_agenda`: Builds a minute-by-minute class schedule and EDGE
   skill station plan for troop meetings, Saturday clinics, or summer camp weeks.
2. `generate_prerequisite_parent_letter`: Generates a ready-to-send email/letter to Scouts
   and parents listing all `PREREQUISITE_CAMPOUT_HOME` requirements, Youth Protection (YPT)
   Two-Deep Leadership & Buddy System reminders, and required field gear.
"""

import re
from typing import Any, Dict, List, Optional
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


def generate_counselor_session_agenda(
    badge_name: str,
    research_result: Optional[Dict[str, Any]] = None,
    schedule_format: str = "3 Troop Meetings (45 min each)",
    counselor_info: Optional[Dict[str, Any]] = None,
    postponed_session_idx: Optional[int] = None,
    companion_badge_name: Optional[str] = None,
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

        research_result = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name=str(badge_name).strip()))
    if not isinstance(research_result, dict):
        return build_guided_tool_error(
            error_code="INVALID_RESEARCH_RESULT",
            message="research_result must be a dictionary containing Merit Badge requirements.",
            remediation="Call fetch_merit_badge_pamphlet_pdf first and pass its output dictionary.",
        )

    clean_badge = badge_name.strip()
    c_info = counselor_info or {}
    loc = resolve_counselor_location(
        troop_affiliation=str(c_info.get("troop_affiliation") or ""),
        location_or_zip=str(c_info.get("location_or_zip") or ""),
    )
    reqs: List[Dict[str, Any]] = list(research_result.get("requirements") or [])
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
                    "55–75 min: Verb-Aligned Fillable Workbook checkpoint & assignment of Session 2 skill station prep.",
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

    md_lines = [
        f"# {clean_badge}" + (f" + {companion_clean}" if companion_clean else "") + " Merit Badge — Counselor Session Pacing Plan",
        f"**Schedule Format:** {schedule_format}  ",
        f"**Local Field Context:** {loc['display_location']} • {loc['nws_office']}  ",
        f"**Primary Reference:** Official Scouting America *{clean_badge}* Merit Badge Pamphlet",
        "",
    ]
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
        "postponed_session_idx": postponed_session_idx,
        "schedule_format": schedule_format,
        "resolved_location": loc,
        "sessions": sessions,
        "agenda_markdown": "\n".join(md_lines),
        "status": "SUCCESS",
    }


def generate_prerequisite_parent_letter(
    badge_name: str,
    research_result: Optional[Dict[str, Any]] = None,
    counselor_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generates a copy-pasteable email/letter to Scouts and parents detailing prerequisites and YPT rules.

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge (or a `PrerequisiteParentLetterRequest` instance).
        research_result: Serialized `MeritBadgeResearchResult` dictionary containing `requirements`.
        counselor_info: Optional dictionary with `counselor_name`, `troop_affiliation`,
            `location_or_zip`, `email_address`, and `phone_number`.

    Returns:
        Dict[str, Any]: Dictionary containing `badge_name`, `subject_line`, `letter_markdown`,
        `prerequisite_count`, and `status` (or a `GuidedToolError` dictionary on invalid input).
    """
    if isinstance(badge_name, PrerequisiteParentLetterRequest):
        req_obj = badge_name
        badge_name = req_obj.badge_name
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

        research_result = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name=str(badge_name).strip()))
    if not isinstance(research_result, dict):
        return build_guided_tool_error(
            error_code="INVALID_RESEARCH_RESULT",
            message="research_result must be a dictionary containing Merit Badge requirements.",
            remediation="Call fetch_merit_badge_pamphlet_pdf first and pass its output dictionary.",
        )

    clean_badge = badge_name.strip()
    c_info = counselor_info or {}
    c_name = str(c_info.get("counselor_name") or "Scoutmaster Bob")
    c_troop = str(c_info.get("troop_affiliation") or "Troop 123, My Council")
    c_loc_raw = str(c_info.get("location_or_zip") or "").strip()
    c_email = str(c_info.get("email_address") or "counselor@troop123.org")
    c_phone = str(c_info.get("phone_number") or "(000) 555-1234")
    pamphlet_url = str(research_result.get("pamphlet_url") or "https://www.scouting.org/skills/merit-badges/")
    loc = resolve_counselor_location(troop_affiliation=c_troop, location_or_zip=c_loc_raw)

    reqs: List[Dict[str, Any]] = list(research_result.get("requirements") or [])
    prereqs = [r for r in reqs if str(r.get("execution_mode", "")).upper() == "PREREQUISITE_CAMPOUT_HOME"]

    prereq_bullets: List[str] = []
    for r in prereqs:
        prereq_bullets.append(f"- **Requirement {r.get('req_number')}**: {r.get('req_text')}")
    if not prereq_bullets:
        prereq_bullets.append(
            f"- Review Chapter 1 of the official *{clean_badge}* Merit Badge Pamphlet and bring your Scout Workbook to Session 1."
        )

    troop_header = f"{c_troop} ({c_loc_raw})" if c_loc_raw and c_loc_raw not in c_troop else c_troop
    subject = f"Scouts BSA {clean_badge} Merit Badge — Class Preparation & Prerequisite Guide ({troop_header})"
    letter_md = "\n".join(
        [
            f"**Subject:** {subject}",
            "",
            f"Dear Scouts and Parents/Guardians of {troop_header},",
            "",
            f"Welcome to the **{clean_badge} Merit Badge** clinic! To help every Scout succeed and get the most out of our hands-on sessions, please review the following preparation checklist before our first meeting:",
            "",
            "### 1. Official Source of Truth & Local Field Reference",
            f"- **Official BSA {clean_badge} Merit Badge Pamphlet:** {pamphlet_url}",
            f"- **Local Field & Weather Context ({loc['display_location']}):** {loc['nws_office']} ({loc['nws_url']}) • {loc['field_site_examples']}",
            "- **Signed Blue Card / Scoutbook Connection:** Please obtain unit leader approval before our first session.",
            "",
            "### 2. Prerequisite, Campout & Home-Study Items",
            *prereq_bullets,
            "",
            "### 3. Scouting America Youth Protection (YPT) Reminder",
            "- In accordance with Scouting America's *Guide to Safe Scouting*, **all email/digital communications between Scouts and Merit Badge Counselors must copy a parent/guardian or second registered adult leader**, and all meetings follow Two-Deep Leadership and the Buddy System.",
            "",
            "Yours in Scouting,",
            f"**{c_name}**  ",
            f"Merit Badge Counselor • {troop_header}  ",
            f"Email: {c_email} | Phone: {c_phone}",
        ]
    )

    return {
        "badge_name": clean_badge,
        "subject_line": subject,
        "prerequisite_count": len(prereqs),
        "resolved_location": loc,
        "letter_markdown": letter_md,
        "status": "SUCCESS",
    }


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
    reqs = list(res.get("requirements") or [])
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
        f"Verb-Aligned {resolved_badge} Fillable Scout Workbook (printed or tablet)",
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
        f"**Session Dates:** {' | '.join(dates)} • **Location:** {room}",
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
    <div><strong>Schedule:</strong> {_html.escape(" | ".join(dates))} • <strong>Room:</strong> {_html.escape(room)}</div>
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
        "prerequisite_count": len(prereq_reqs),
        "in_class_count": len(in_class_reqs),
        "starting_gates": gates,
        "what_to_bring": bring_items,
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
) -> Dict[str, Any]:
    """Generates a 1-Page Event Organizer Catalog & Schedule Spec Sheet for Merit Badge University/College chairs."""
    from src.agents.planner import _format_session_mode_label
    from src.tools.scouting_scraper import MeritBadgeResearchRequest, fetch_merit_badge_pamphlet_pdf

    res = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name=badge_name))
    if res.get("status") == "ERROR":
        return res
    resolved_badge = str(res.get("badge_name") or badge_name)
    reqs = list(res.get("requirements") or [])
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
) -> Dict[str, Any]:
    """Generates the 3-Stage YPT Two-Deep Communication Pack:
    - Stage 1: 7-Day Pre-Class Welcome + 1-Page CPP + Fillable Workbook
    - Stage 2: Mid-Clinic Absentee & Make-Up Day Alert (auto-populated from S1..S4 attendance)
    - Stage 3: Post-Clinic Smart Partial & Blue Card Summary (grouped by Troop)
    Every stage includes the mandatory Scouting America YPT Two-Deep CC header.
    """
    from src.tools.scouting_scraper import MeritBadgeResearchRequest, fetch_merit_badge_pamphlet_pdf

    res = fetch_merit_badge_pamphlet_pdf(MeritBadgeResearchRequest(badge_name=badge_name))
    if res.get("status") == "ERROR":
        return res
    resolved_badge = str(res.get("badge_name") or badge_name)
    reqs = list(res.get("requirements") or [])
    c_info = counselor_info or {}
    c_name = str(c_info.get("counselor_name") or "Merit Badge Counselor")
    c_troop = str(c_info.get("troop_affiliation") or "Troop 19, Northeast Massachusetts Council")
    c_email = str(c_info.get("email_address") or "counselor@scouting.org")
    dates = list(session_dates or ["Session 1", "Session 2", "Session 3", "Session 4", "Make-Up Day"])
    room = str(room_location or "Main Clinic Room")

    ypt_header = "[MANDATORY YPT CC: Unit Leader & Parent/Guardian — Required per Scouting America Youth Protection Policy]"
    prereq_ids = ", ".join(str(r.get("req_number")) for r in reqs if r.get("syllabus_bucket") == "Pre-Class Prerequisite") or "Pamphlet Chapter 1"
    makeup_ids = ", ".join(str(r.get("req_number")) for r in reqs if r.get("syllabus_bucket") == "Make-Up Eligible") or "Missed session topics"
    followup_ids = ", ".join(str(r.get("req_number")) for r in reqs if r.get("syllabus_bucket") == "Post-Class Home-Troop Follow-Up") or "Home-troop logs"

    stage1_md = "\n".join([
        ypt_header,
        f"**Subject:** [Stage 1: Pre-Class Welcome] {resolved_badge} Merit Badge — CPP & Fillable Workbook ({' | '.join(dates[:2])})",
        "",
        "Dear Scouts, Parents/Guardians, and Scoutmasters,",
        "",
        f"Welcome to our upcoming **{resolved_badge} Merit Badge** class in **{room}**! Attached are your **1-Page Class Preparation Page (CPP)** and **Verb-Aligned Fillable Scout Workbook**.",
        f"- **Pre-Class Prerequisites to Prepare Before Session 1:** Requirements {prereq_ids}",
        "- **What to Bring:** Signed Blue Card (#34124), official pamphlet, and your workbook (optional study aid per GTA §7.0.3.2).",
        "",
        f"Yours in Scouting,\n**{c_name}** ({c_troop}) • {c_email}",
    ])

    abs_lines = []
    for sc in absent_scouts_summary or []:
        abs_lines.append(
            f"- **{sc.get('scout_name', 'Scout')} ({sc.get('troop_number', 'Troop')}):** Missed {sc.get('missed_sessions', 'Session')} -> Actionable Make-Up Reqs: {sc.get('actionable_makeup_reqs', makeup_ids)}"
        )
    if not abs_lines:
        abs_lines.append(f"- **Make-Up Day Eligible Requirements:** {makeup_ids} (for any Scout who missed an in-class session).")

    stage2_md = "\n".join([
        ypt_header,
        f"**Subject:** [Stage 2: Mid-Clinic Make-Up Alert] {resolved_badge} Merit Badge — Make-Up Day Preparation ({dates[-1]})",
        "",
        "Dear Scouts, Parents/Guardians, and Unit Advancement Chairs,",
        "",
        f"As we approach our **{dates[-1]}** session in **{room}**, here is the targeted Make-Up plan for Scouts who missed an earlier block:",
        *abs_lines,
        "",
        f"Please review the corresponding sections in the official {resolved_badge} Merit Badge Pamphlet and bring your notes to Make-Up Day.",
        "",
        f"Yours in Scouting,\n**{c_name}** ({c_troop}) • {c_email}",
    ])

    stage3_md = "\n".join([
        ypt_header,
        f"**Subject:** [Stage 3: Post-Clinic Blue Card & Smart Partial Summary] {resolved_badge} Merit Badge ({troop_filter})",
        "",
        "Dear Scoutmasters, Unit Advancement Chairs, Parents, and Scouts,",
        "",
        f"Thank you for a great **{resolved_badge} Merit Badge** clinic! Attached is the **Per-Troop Blue Card (#34124) & Scoutbook CSV Packet**.",
        f"- **Actionable Make-Up Partial Requirements (can be finished with counselor anytime):** {makeup_ids}",
        f"- **Expected Home-Troop Follow-Up Requirements (campouts, long-term logs, or troop service):** {followup_ids}",
        "",
        f"Yours in Scouting,\n**{c_name}** ({c_troop}) • {c_email}",
    ])

    return {
        "status": "SUCCESS",
        "badge_name": resolved_badge,
        "ypt_mandatory_cc_header": ypt_header,
        "troop_filter": troop_filter,
        "stages": {
            "stage_1_pre_class": {
                "title": "Stage 1: 7-Day Pre-Class Welcome + CPP + Workbook",
                "markdown": stage1_md,
            },
            "stage_2_mid_clinic_makeup": {
                "title": "Stage 2: Mid-Clinic Absentee & Make-Up Day Alert",
                "markdown": stage2_md,
            },
            "stage_3_post_clinic_partials": {
                "title": "Stage 3: Post-Clinic Smart Partial & Per-Troop Blue Card Summary",
                "markdown": stage3_md,
            },
        },
    }


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
        ("—", "-"),
        ("–", "-"),
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


def _wrap_pdf_lines(
    text: str,
    max_width: float,
    fontname: str = "helv",
    fontsize: float = 8.0,
) -> List[str]:
    """Word-wraps sanitized text using exact PyMuPDF font metrics so every line fits inside `max_width`."""
    import fitz

    clean = _sanitize_pdf_text(text)
    if not clean.strip():
        return []
    usable_width = max(40.0, float(max_width) - 4.0)
    wrapped: List[str] = []
    for raw_para in clean.splitlines():
        para = raw_para.strip()
        if not para:
            wrapped.append("")
            continue
        words = para.split(" ")
        cur_line = ""
        for word in words:
            if not word:
                continue
            # Break single ultra-long unbroken tokens (e.g. URLs) if needed
            if fitz.get_text_length(word, fontname=fontname, fontsize=fontsize) > usable_width:
                if cur_line:
                    wrapped.append(cur_line)
                    cur_line = ""
                chunk = ""
                for ch in word:
                    cand_chunk = chunk + ch
                    if fitz.get_text_length(cand_chunk, fontname=fontname, fontsize=fontsize) <= usable_width:
                        chunk = cand_chunk
                    else:
                        if chunk:
                            wrapped.append(chunk)
                        chunk = ch
                cur_line = chunk
                continue
            cand = f"{cur_line} {word}".strip() if cur_line else word
            if fitz.get_text_length(cand, fontname=fontname, fontsize=fontsize) <= usable_width:
                cur_line = cand
            else:
                if cur_line:
                    wrapped.append(cur_line)
                cur_line = word
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
        if bg_fill is not None or border_color is not None:
            page.draw_rect(
                fitz.Rect(x0, y_cursor, x1, y_cursor + box_h),
                color=border_color or bg_fill,
                fill=bg_fill,
            )
        if left_stripe_color is not None:
            page.draw_rect(
                fitz.Rect(x0, y_cursor, x0 + 4.0, y_cursor + box_h),
                color=left_stripe_color,
                fill=left_stripe_color,
            )
        for line_idx, line_str in enumerate(chunk):
            if line_str:
                baseline_y = y_cursor + pad_y + (line_idx + 0.82) * line_h
                page.insert_text(
                    fitz.Point(x0 + eff_pad_x, baseline_y),
                    line_str,
                    fontsize=fontsize,
                    fontname=fontname,
                    color=color,
                )
        y_cursor += box_h + 2.0
        idx += len(chunk)
        if idx < total_lines:
            page = doc.new_page(width=612, height=792)
            y_cursor = 36.0

    return page, y_cursor


def generate_fillable_scout_workbook_pdf(
    badge_name: str,
    counselor_info: Optional[Dict[str, Any]] = None,
    option_track: str = "ALL",
    session_dates: Optional[List[str]] = None,
) -> bytes:
    """Generates a downloadable, interactive AcroForm PDF Fillable Scout Workbook for any of the 149 badges.

    Includes:
    - Branded Scouting America Navy & Gold header banner with embedded official Merit Badge patch emblem.
    - Scouting America Guide to Advancement Section 7.0.3.2 compliance notice banner.
    - Interactive AcroForm text fields (`Scout Name`, `Troop & Council`, `BSA Member ID`, `Counselor Name`).
    - Unrolled sub-requirements (`1a`, `1b`, `2a`, `2b1`, etc.) with color-coded parent requirement group banners.
    - Full verbatim requirement text (zero mid-word truncation or overflow drops), pamphlet fact-vs-myth callout,
      counselor pre-approval gate checkboxes, interactive gear checklist checkboxes, bordered dot-grid sketch canvases,
      zebra-striped multi-row/multi-column graphic organizer tables with per-row AcroForm text fields, and Counselor Sign-Off checkboxes.
    """
    import fitz

    from src.agents.planner import _format_workbook_organizer_label
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
    resolved_badge = str(res.get("badge_name") or badge_name)
    is_eagle = bool(res.get("is_eagle_required"))
    reqs = list(res.get("requirements") or [])
    c_info = counselor_info or {}
    c_name = _sanitize_pdf_text(str(c_info.get("counselor_name") or "Merit Badge Counselor"))
    c_troop = _sanitize_pdf_text(str(c_info.get("troop_affiliation") or "Troop 19, Northeast Massachusetts Council"))
    dates_str = _sanitize_pdf_text(" | ".join(session_dates) if session_dates else "Sessions 1-4 + Make-Up Day")

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # Branded Navy & Gold Header Banner with Embedded Merit Badge Emblem
    y_cursor = _draw_branded_pdf_header(
        page=page,
        badge_name=resolved_badge,
        doc_title=f"{resolved_badge.upper()} MERIT BADGE - FILLABLE SCOUT WORKBOOK",
        subtitle_line=f"Counselor: {c_name} ({c_troop})  |  Track: {option_track.upper()}  |  Schedule: {dates_str}",
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
        fontsize=7.6,
        fontname="helv",
        color=(0.35, 0.22, 0.02),
        bg_fill=(1.0, 0.98, 0.90),
        border_color=(0.88, 0.72, 0.22),
        left_stripe_color=(0.85, 0.55, 0.05),
    )
    y_cursor += 6.0

    # Interactive Scout Info AcroForm Card
    page.draw_rect(
        fitz.Rect(28.0, y_cursor, 584.0, y_cursor + 30.0),
        color=(0.78, 0.84, 0.92),
        fill=(0.97, 0.985, 1.0),
    )
    id_fields = [
        ("scout_name", "Scout Name:", "", fitz.Rect(34, y_cursor + 10, 198, y_cursor + 26)),
        ("troop_unit", "Troop & Council:", "", fitz.Rect(208, y_cursor + 10, 396, y_cursor + 26)),
        ("bsa_id", "BSA Member ID:", "", fitz.Rect(406, y_cursor + 10, 578, y_cursor + 26)),
    ]
    for f_key, f_lbl, f_val, f_rect in id_fields:
        page.insert_text(fitz.Point(f_rect.x0, f_rect.y0 - 2), f_lbl, fontsize=7.4, fontname="helv", color=(0.0, 0.22, 0.48))
        w = fitz.Widget()
        w.field_name = f_key
        w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        w.field_value = f_val
        w.rect = fitz.Rect(f_rect.x0, f_rect.y0 + 1, f_rect.x1, f_rect.y1 + 2)
        w.border_color = (0.58, 0.66, 0.76)
        w.fill_color = (1.0, 1.0, 1.0)
        w.text_fontsize = 8.5
        page.add_widget(w)

    y_cursor += 35.0
    units = _iter_unrolled_workbook_units(reqs)

    # Page-1 At-a-Glance Requirement Completion & Counselor Sign-Off Index
    fillable_req_nums = [
        str(u.get("req_number") or u.get("req_id") or "").strip()
        for u in units
        if not u.get("is_group_header") and str(u.get("req_number") or u.get("req_id") or "").strip()
    ]
    if fillable_req_nums:
        chips_line = "   ".join(f"[ ] Req {rn}" for rn in fillable_req_nums)
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            28.0,
            584.0,
            f"Page-1 Requirement Completion & Counselor Verification Index:  {chips_line}\n"
            "Unit Leader Pre-Approval (Blue Card #34124): ______________________   Counselor Final Sign-Off: ______________________   Date: ____/____/2026",
            fontsize=7.3,
            fontname="helv",
            color=(0.08, 0.18, 0.36),
            bg_fill=(0.94, 0.97, 1.0),
            border_color=(0.68, 0.78, 0.90),
            left_stripe_color=(0.0, 0.247, 0.529),
            pad_y=3.0,
        )
        y_cursor += 6.0

    for idx, u in enumerate(units, start=1):
        r_num = str(u.get("req_number") or u.get("req_id") or str(idx)).strip()
        r_title = str(u.get("topic_title") or u.get("title") or f"Requirement {r_num}").strip()
        r_text = str(u.get("req_text") or "").strip()
        r_bucket = str(u.get("syllabus_bucket") or "In-Class Concept").strip()
        r_cit = str(u.get("pamphlet_page_citation") or u.get("pamphlet_citation") or "Official BSA Pamphlet").strip()
        org = u.get("workbook_organizer") or {}
        org_type = str(org.get("organizer_type") or "RULED_EXPLAIN_BOX").strip()
        org_type_friendly = _format_workbook_organizer_label(org_type)
        org_label = _format_workbook_organizer_label(r_num, org_type)
        headers = [str(h) for h in (org.get("headers") or ["Concept / Step", "Scout Notes & Field Evidence"])]
        row_labels = [str(rl) for rl in (org.get("row_labels") or ["Point 1", "Point 2", "Point 3"])]
        pre_approval_gate = bool(org.get("pre_approval_gate")) or bool(u.get("starting_requirement_gate"))
        gear_checklist = [str(g) for g in (u.get("gear_checklist") or []) if str(g).strip()]
        mis_pair = u.get("common_misconception_pair") or {}

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
            y_cursor += 4.0
            continue

        if y_cursor > 645.0:
            page = doc.new_page(width=612, height=792)
            y_cursor = 36.0

        # Requirement / Sub-Requirement Header Strip (full text, zero slicing, color-coded left stripe)
        page, y_cursor = _insert_wrapped_pdf_text(
            doc,
            page,
            y_cursor,
            28.0,
            584.0,
            f"[Req {r_num}] {r_title}   |   {r_bucket}   |   {org_type_friendly}   |   {r_cit}",
            fontsize=8.1,
            fontname="helv",
            color=(0.0, 0.22, 0.48),
            bg_fill=(0.93, 0.96, 0.99),
            border_color=(0.80, 0.86, 0.94),
            left_stripe_color=stripe_rgb,
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

        # Counselor Pre-Approval Gate Box (when required before starting)
        if pre_approval_gate:
            if y_cursor > 715.0:
                page = doc.new_page(width=612, height=792)
                y_cursor = 36.0
            gate_y0 = y_cursor
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                48.0,
                580.0,
                "COUNSELOR PRE-APPROVAL GATE: Obtain Counselor approval BEFORE starting this requirement/plan/experiment. Counselor Initials & Date: ____________",
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

        # Sketch & Observation Canvas (dot-grid / astronomy circle canvas)
        low_text = r_text.lower()
        if org_type == "SKETCH_AND_OBSERVATION_CANVAS" or any(
            kw in low_text for kw in ("sketch", "draw", "diagram", "map", "chart the")
        ):
            if y_cursor + 92.0 > 748.0:
                page = doc.new_page(width=612, height=792)
                y_cursor = 36.0
            canvas_rect = fitz.Rect(32.0, y_cursor, 580.0, y_cursor + 84.0)
            page.draw_rect(canvas_rect, color=(0.55, 0.64, 0.76), fill=(0.99, 0.995, 1.0))
            page.insert_text(
                fitz.Point(38.0, y_cursor + 11.0),
                _sanitize_pdf_text(f"Sketch & Observation Canvas (Req {r_num}) - Draw, diagram, and label key features:"),
                fontsize=7.3,
                fontname="helv",
                color=(0.25, 0.32, 0.42),
            )
            for gx in range(48, 570, 24):
                for gy in range(int(y_cursor) + 20, int(y_cursor) + 78, 16):
                    page.draw_circle(fitz.Point(float(gx), float(gy)), 0.6, color=(0.75, 0.80, 0.86), fill=(0.75, 0.80, 0.86))
            if any(k in low_text for k in ("moon", "planet", "constellation", "sky", "eclipse", "telescope", "horizon")):
                page.draw_circle(fitz.Point(500.0, y_cursor + 46.0), 22.0, color=(0.60, 0.68, 0.78))
                page.draw_line(fitz.Point(40.0, y_cursor + 72.0), fitz.Point(455.0, y_cursor + 72.0), color=(0.65, 0.72, 0.80))
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

        # Render Multi-Column Header Row + Zebra-Striped Organizer Rows + AcroForm Text Fields + Counselor Sign-Off Checkbox
        input_headers = headers[1:] if len(headers) > 1 else ["Scout Notes & Field Evidence"]
        input_cols = max(1, len(input_headers))
        left_col_x0 = 32.0
        left_col_x1 = 188.0
        input_region_x0 = 188.0
        input_region_x1 = 515.0
        col_w = (input_region_x1 - input_region_x0) / float(input_cols)
        col_hdr_h = 15.0
        if y_cursor + col_hdr_h + 24.0 > 748.0:
            page = doc.new_page(width=612, height=792)
            y_cursor = 36.0
        page.draw_rect(
            fitz.Rect(left_col_x0, y_cursor, left_col_x1, y_cursor + col_hdr_h),
            color=(0.0, 0.247, 0.529),
            fill=(0.0, 0.247, 0.529),
        )
        page.insert_text(
            fitz.Point(left_col_x0 + 4.0, y_cursor + 10.5),
            _sanitize_pdf_text(headers[0])[:30],
            fontsize=7.0,
            fontname="helv",
            color=(1.0, 1.0, 1.0),
        )
        for c_idx, h_title in enumerate(input_headers):
            cx0 = input_region_x0 + c_idx * col_w
            cx1 = input_region_x0 + (c_idx + 1) * col_w
            page.draw_rect(
                fitz.Rect(cx0, y_cursor, cx1, y_cursor + col_hdr_h),
                color=(0.82, 0.88, 0.95),
                fill=(0.0, 0.247, 0.529),
            )
            max_chars_hdr = max(8, int((col_w - 6.0) / 3.9))
            page.insert_text(
                fitz.Point(cx0 + 3.5, y_cursor + 10.5),
                _sanitize_pdf_text(h_title)[:max_chars_hdr],
                fontsize=6.9,
                fontname="helv",
                color=(1.0, 1.0, 1.0),
            )
        # Rightmost Sign-Off column header cell
        page.draw_rect(
            fitz.Rect(input_region_x1, y_cursor, 580.0, y_cursor + col_hdr_h),
            color=(0.0, 0.247, 0.529),
            fill=(0.0, 0.247, 0.529),
        )
        page.insert_text(
            fitz.Point(input_region_x1 + 4.0, y_cursor + 10.5),
            "Counselor",
            fontsize=6.9,
            fontname="helv",
            color=(0.992, 0.78, 0.20),
        )
        y_cursor += col_hdr_h

        safe_r_num = re.sub(r"[^a-zA-Z0-9_]", "_", r_num)
        signoff_placed = False
        for r_idx, rl in enumerate(row_labels, start=1):
            clean_rl = re.sub(r"^\s*\d+[.)]\s*", "", str(rl)).strip()
            label_lines = _wrap_pdf_lines(f"{r_idx}. {clean_rl}", 148.0, fontname="helv", fontsize=7.2) or [f"{r_idx}."]
            row_h = max(20.0, len(label_lines) * 9.6 + 6.0)
            if y_cursor + row_h > 748.0:
                page = doc.new_page(width=612, height=792)
                y_cursor = 36.0
            row_y0 = y_cursor
            zebra_fill = (0.945, 0.97, 1.0) if r_idx % 2 == 1 else (0.98, 0.99, 1.0)
            page.draw_rect(
                fitz.Rect(left_col_x0, row_y0, left_col_x1, row_y0 + row_h),
                color=(0.78, 0.83, 0.90),
                fill=zebra_fill,
            )
            for l_i, l_str in enumerate(label_lines):
                page.insert_text(
                    fitz.Point(left_col_x0 + 4.0, row_y0 + 3.0 + (l_i + 0.82) * 9.6),
                    l_str,
                    fontsize=7.2,
                    fontname="helv",
                    color=(0.12, 0.18, 0.26),
                )

            for c_idx in range(input_cols):
                cx0 = input_region_x0 + c_idx * col_w
                cx1 = input_region_x0 + (c_idx + 1) * col_w
                page.draw_rect(
                    fitz.Rect(cx0, row_y0, cx1, row_y0 + row_h),
                    color=(0.78, 0.83, 0.90),
                    fill=(1.0, 1.0, 1.0),
                )
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

            page.draw_rect(
                fitz.Rect(input_region_x1, row_y0, 580.0, row_y0 + row_h),
                color=(0.78, 0.83, 0.90),
                fill=(0.98, 0.99, 1.0),
            )
            if not signoff_placed:
                page.insert_text(fitz.Point(520.0, row_y0 + 10.0), "Done:", fontsize=7.2, fontname="helv", color=(0.15, 0.22, 0.33))
                w_chk = fitz.Widget()
                w_chk.field_name = f"req_{safe_r_num}_done_{idx}"
                w_chk.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
                w_chk.field_value = False
                w_chk.rect = fitz.Rect(546.0, row_y0 + 2.0, 559.0, row_y0 + 15.0)
                w_chk.border_color = (0.0, 0.25, 0.53)
                page.add_widget(w_chk)
                page.insert_text(fitz.Point(520.0, row_y0 + 19.0), "Init:____", fontsize=6.9, fontname="helv", color=(0.3, 0.35, 0.42))
                signoff_placed = True

            y_cursor += row_h + 1.0

        y_cursor += 7.0

    _finalize_branded_pdf_pages(
        doc=doc,
        badge_name=resolved_badge,
        doc_short_title="FILLABLE SCOUT WORKBOOK (GTA SEC. 7.0.3.2)",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_class_preparation_page_cpp_pdf(
    badge_name: str,
    counselor_info: Optional[Dict[str, Any]] = None,
    session_dates: Optional[List[str]] = None,
    room_location: str = "",
) -> bytes:
    """Generates a graphically styled Class Preparation Page (CPP) in PDF format with embedded badge emblem, callout cards, and 0% overflow drops."""
    import fitz

    cpp_data = generate_class_preparation_page_cpp(
        badge_name=badge_name,
        counselor_info=counselor_info,
        session_dates=session_dates,
        room_location=room_location,
    )
    resolved_badge = str(cpp_data.get("badge_name") or badge_name)
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
        subtitle_line=f"Counselor: {c_name} ({c_troop})  |  Room / Venue: {room_str}",
        kicker_text="SCOUTS BSA PRE-CLASS SCOUT, PARENT & UNIT LEADER HANDOUT",
    )

    in_gate_section = False
    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if not line:
            y_cursor += 4.0
            continue
        if line.startswith("# "):
            continue
        clean_line = (
            line.replace("**", "")
            .replace("`", "")
            .replace("- [ ] ", "[ ] ")
        )
        clean_line = re.sub(r"\*([^*]+)\*", r"\1", clean_line)
        if clean_line.startswith("## "):
            hdr_text = clean_line[3:].strip()
            in_gate_section = "Gate Alert" in hdr_text
            y_cursor += 3.0
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                28.0,
                584.0,
                hdr_text,
                fontsize=9.4,
                fontname="helv",
                color=(0.0, 0.22, 0.48),
                bg_fill=(0.92, 0.96, 0.99),
                border_color=(0.78, 0.85, 0.94),
                left_stripe_color=(0.992, 0.725, 0.075) if in_gate_section else (0.0, 0.247, 0.529),
                pad_y=3.5,
            )
        elif in_gate_section:
            page, y_cursor = _insert_wrapped_pdf_text(
                doc,
                page,
                y_cursor,
                32.0,
                580.0,
                clean_line,
                fontsize=8.4,
                fontname="helv",
                color=(0.38, 0.22, 0.02),
                bg_fill=(1.0, 0.98, 0.90),
                border_color=(0.88, 0.68, 0.18),
                left_stripe_color=(0.85, 0.55, 0.05),
                pad_y=3.0,
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
                pad_y=2.0,
            )

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
) -> bytes:
    """Generates a graphically styled Counselor Session Agenda & Lesson Plan in PDF format with embedded Merit Badge emblem and session cards."""
    import fitz

    from src.agents.planner import _format_session_mode_label

    c_info = counselor_info or {}
    c_name = _sanitize_pdf_text(str(c_info.get("counselor_name") or "Merit Badge Counselor"))
    c_troop = _sanitize_pdf_text(str(c_info.get("troop_affiliation") or "Troop 19, Northeast Massachusetts Council"))
    friendly_fmt = _format_session_mode_label(schedule_format)

    agenda_data = generate_counselor_session_agenda(
        badge_name=badge_name,
        schedule_format=schedule_format,
        counselor_info=counselor_info,
        postponed_session_idx=postponed_session_idx,
        companion_badge_name=companion_badge_name,
    )
    resolved_badge = str(agenda_data.get("badge_name") or badge_name)
    md_text = str(agenda_markdown_override or agenda_data.get("agenda_markdown") or "")
    md_text = md_text.replace(f"Schedule Format: {schedule_format}", f"Schedule Format: {friendly_fmt}")
    md_text = md_text.replace(f"**Schedule Format:** {schedule_format}", f"**Schedule Format:** {friendly_fmt}")

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y_cursor = _draw_branded_pdf_header(
        page=page,
        badge_name=resolved_badge,
        doc_title=f"{resolved_badge.upper()} MERIT BADGE - SESSION AGENDA & LESSON PLAN",
        subtitle_line=f"Format: {friendly_fmt}  |  Counselor: {c_name} ({c_troop})",
        kicker_text="SCOUTS BSA COUNSELOR FACILITATION & PACING GUIDE (EDGE METHOD)",
    )

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
) -> bytes:
    """Generates a graphically styled YPT-Compliant Parent Prerequisite & Welcome Letter in PDF format with embedded Merit Badge emblem."""
    import fitz

    c_info = counselor_info or {}
    c_name = _sanitize_pdf_text(str(c_info.get("counselor_name") or "Merit Badge Counselor"))
    c_troop = _sanitize_pdf_text(str(c_info.get("troop_affiliation") or "Troop 19, Northeast Massachusetts Council"))
    c_email = _sanitize_pdf_text(str(c_info.get("email_address") or "counselor@scouting.org"))

    resolved_badge = str(badge_name).strip() or "First Aid"
    md_text = str(letter_markdown_override or "").strip()
    if not md_text:
        if stage in ("stage_2_mid_clinic_alert", "stage_2_mid_clinic_makeup", "stage_3_final_packet", "stage_3_post_clinic_partials"):
            pack = generate_three_stage_ypt_communication_pack(
                badge_name=resolved_badge,
                counselor_info=counselor_info,
            )
            resolved_badge = str(pack.get("badge_name") or resolved_badge)
            stages_map = pack.get("stages") or {}
            if "2" in stage:
                md_text = str((stages_map.get("stage_2_mid_clinic_makeup") or {}).get("markdown") or "")
            else:
                md_text = str((stages_map.get("stage_3_post_clinic_partials") or {}).get("markdown") or "")
        if not md_text:
            letter_res = generate_prerequisite_parent_letter(
                badge_name=resolved_badge,
                counselor_info=counselor_info,
            )
            resolved_badge = str(letter_res.get("badge_name") or resolved_badge)
            md_text = str(letter_res.get("letter_markdown") or "")

    stage_label = (
        "STAGE 2: MID-CLINIC MAKE-UP ALERT"
        if "2" in stage
        else "STAGE 3: POST-CLINIC SMART PARTIAL & BLUE CARD PACKET"
        if "3" in stage
        else "STAGE 1: PRE-CLASS WELCOME & PREREQUISITE GUIDE"
    )

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y_cursor = _draw_branded_pdf_header(
        page=page,
        badge_name=resolved_badge,
        doc_title=f"{resolved_badge.upper()} MERIT BADGE - PARENT & SCOUT COMMUNICATION",
        subtitle_line=f"{stage_label}  |  Counselor: {c_name} ({c_troop})  |  {c_email}",
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



