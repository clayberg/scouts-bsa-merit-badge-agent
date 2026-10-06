"""Interactive Counselor AI Studio Toolkit (`src/tools/counselor_studiokit.py`).

Provides AI-assisted Merit Badge Counselor session planning and communication tools:
1. `generate_counselor_session_agenda`: Builds a minute-by-minute class schedule and EDGE
   skill station plan for troop meetings, Saturday clinics, or summer camp weeks.
2. `generate_prerequisite_parent_letter`: Generates a ready-to-send email/letter to Scouts
   and parents listing all `PREREQUISITE_CAMPOUT_HOME` requirements, Youth Protection (YPT)
   Two-Deep Leadership & Buddy System reminders, and required field gear.
"""

from typing import Any, Dict, List, Optional
from src.agents.researcher import resolve_counselor_location
from src.schemas import build_guided_tool_error


def generate_counselor_session_agenda(
    badge_name: str,
    research_result: Dict[str, Any],
    schedule_format: str = "3 Troop Meetings (45 min each)",
    counselor_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generates a structured minute-by-minute Merit Badge teaching agenda and EDGE station guide.

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge (e.g., `'Weather'`, `'First Aid'`).
        research_result: Serialized `MeritBadgeResearchResult` dictionary containing `requirements`.
        schedule_format: Selected session schedule format (`'3 Troop Meetings (45 min each)'`,
            `'Saturday Merit Badge Clinic (3 hours)'`, or `'Summer Camp Week (4x 45-min blocks)'`).
        counselor_info: Optional dictionary with `counselor_name`, `troop_affiliation`,
            and `location_or_zip`.

    Returns:
        Dict[str, Any]: Dictionary containing `badge_name`, `schedule_format`, `sessions`
        (list of structured session blocks), `agenda_markdown`, and `status` (or a
        `GuidedToolError` dictionary if `badge_name` or `research_result` is invalid).
    """
    if not badge_name or not str(badge_name).strip():
        return build_guided_tool_error(
            error_code="EMPTY_BADGE_NAME",
            message="badge_name cannot be empty when generating a counselor session agenda.",
            remediation="Provide a valid Scouts BSA Merit Badge name such as 'Weather' or 'First Aid'.",
        )
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

    sessions = [
        {
            "session_number": 1,
            "title": f"Session 1: Safety First, Core Concepts & Official BSA {clean_badge} Pamphlet Overview",
            "duration_minutes": 45,
            "focus_requirements": in_class_ids,
            "edge_method_focus": "Explain & Demonstrate",
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
            "activities": [
                f"00–15 min: Review completed Campout, Field, and Home Prerequisite logs ({prereq_ids}).",
                f"15–30 min: Connect {clean_badge} to local field sites ({loc['field_site_examples']}) and {loc['nws_office']} / {loc['state_agency']}.",
                "30–45 min: Individual Blue Card / Scoutbook verification and counselor sign-off.",
            ],
        },
    ]

    md_lines = [
        f"# {clean_badge} Merit Badge — Counselor Session Pacing Plan",
        f"**Schedule Format:** {schedule_format}  ",
        f"**Local Field Context:** {loc['display_location']} • {loc['nws_office']}  ",
        f"**Primary Reference:** Official Scouting America *{clean_badge}* Merit Badge Pamphlet",
        "",
    ]
    for s in sessions:
        md_lines.append(f"## {s['title']} ({s['duration_minutes']} min • EDGE: {s['edge_method_focus']})")
        for act in s["activities"]:
            md_lines.append(f"- {act}")
        md_lines.append("")

    return {
        "badge_name": clean_badge,
        "schedule_format": schedule_format,
        "resolved_location": loc,
        "sessions": sessions,
        "agenda_markdown": "\n".join(md_lines),
        "status": "SUCCESS",
    }


def generate_prerequisite_parent_letter(
    badge_name: str,
    research_result: Dict[str, Any],
    counselor_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generates a copy-pasteable email/letter to Scouts and parents detailing prerequisites and YPT rules.

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge.
        research_result: Serialized `MeritBadgeResearchResult` dictionary containing `requirements`.
        counselor_info: Optional dictionary with `counselor_name`, `troop_affiliation`,
            `location_or_zip`, `email_address`, and `phone_number`.

    Returns:
        Dict[str, Any]: Dictionary containing `badge_name`, `subject_line`, `letter_markdown`,
        `prerequisite_count`, and `status` (or a `GuidedToolError` dictionary on invalid input).
    """
    if not badge_name or not str(badge_name).strip():
        return build_guided_tool_error(
            error_code="EMPTY_BADGE_NAME",
            message="badge_name cannot be empty when generating a prerequisite parent letter.",
            remediation="Provide a valid Scouts BSA Merit Badge name such as 'Weather' or 'First Aid'.",
        )
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
            f"- **Official BSA *{clean_badge}* Merit Badge Pamphlet:** {pamphlet_url}",
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
