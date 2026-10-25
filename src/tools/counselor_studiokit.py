"""Interactive Counselor AI Studio Toolkit (`src/tools/counselor_studiokit.py`).

Provides AI-assisted Merit Badge Counselor session planning and communication tools:
1. `generate_counselor_session_agenda`: Builds a minute-by-minute class schedule and EDGE
   skill station plan for troop meetings, Saturday clinics, or summer camp weeks.
2. `generate_prerequisite_parent_letter`: Generates a ready-to-send email/letter to Scouts
   and parents listing all `PREREQUISITE_CAMPOUT_HOME` requirements, Youth Protection (YPT)
   Two-Deep Leadership & Buddy System reminders, and required field gear.
"""

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

    md_lines = [
        f"# {resolved_badge} Merit Badge - 1-Page Class Preparation Page (CPP)",
        f"**Counselor:** {c_name} ({c_troop}) • **YPT Contact:** {c_email} (always CC a parent/guardian or unit leader)",
        f"**Session Dates:** {' | '.join(dates)} • **Location:** {room}",
        "",
        "## 1. Starting Requirement Gate Alert",
    ]
    if gates:
        for g in gates:
            md_lines.append(f"- **[{g.get('gate_type')}] {g.get('gate_label')}:** {g.get('gate_description')}")
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
    for ir in in_class_reqs[:8]:
        md_lines.append(
            f"- **Req {ir.get('req_number')} ({ir.get('syllabus_bucket', 'In-Class')}):** {ir.get('topic_title') or ir.get('req_text', '')[:90]}"
        )

    gates_html = "".join(
        f"<li><strong>[{_html.escape(str(g.get('gate_type')))}] {_html.escape(str(g.get('gate_label')))}:</strong> {_html.escape(str(g.get('gate_description')))}</li>"
        for g in gates
    ) or "<li><strong>Unit Leader Approval:</strong> Obtain your Scoutmaster's signature on your Blue Card (#34124) before Session 1.</li>"

    prereq_html = "".join(
        f"<li><strong>Req {_html.escape(str(pr.get('req_number')))} ({_html.escape(str(pr.get('syllabus_bucket', 'Prerequisite')))}):</strong> {_html.escape(str(pr.get('req_text')))}</li>"
        for pr in prereq_reqs
    ) or f"<li>Read the {_html.escape(resolved_badge)} Merit Badge Pamphlet overview before Session 1.</li>"

    bring_html = "".join(f"<li>☐ {_html.escape(str(bi))}</li>" for bi in bring_items)
    in_class_html = "".join(
        f"<li><strong>Req {_html.escape(str(ir.get('req_number')))} ({_html.escape(str(ir.get('syllabus_bucket', 'In-Class')))}):</strong> {_html.escape(str(ir.get('topic_title') or ir.get('req_text', '')[:90]))}</li>"
        for ir in in_class_reqs[:8]
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
    spec_md = "\n".join([
        f"# {resolved_badge} Merit Badge - Event Organizer Catalog & Schedule Spec Sheet",
        f"- **Instructor / Counselor:** {c_name} ({c_troop})",
        f"- **Eagle-Required:** {'Yes' if res.get('is_eagle_required') else 'No'}",
        f"- **Session Format:** `{session_mode}` • **Recommended Class Cap:** {max_scouts} Scouts",
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
