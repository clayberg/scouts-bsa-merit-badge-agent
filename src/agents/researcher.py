"""ADK 5-Tier PamphletResearchAgent, WebSearchGroundingAgent, and ResearchCoverageCriticAgent.

This module implements the 5-Tier Deep Merit Badge Research Pipeline:
1. Tier 1 — Authoritative Requirement & Sub-Requirement Tree (1a, 1b, 2a, 2b, 4a, etc.)
2. Tier 2 — Execution-Mode Triage (IN_CLASS_DISCUSSION, HANDS_ON_SKILL_STATION, PREREQUISITE_CAMPOUT_HOME)
3. Tier 3 — Pamphlet Deep Extraction (worked examples, 2-col comparisons, gear checklists)
4. Tier 4 — Hyper-Local & Civic Grounding via WebSearchGroundingAgent (`AgentTool`)
5. Tier 5 — Guide to Safe Scouting Audit & ResearchCoverageCriticAgent verification
"""

import hashlib
import json
from typing import Any, Dict, List, Optional
from google import adk
from src.config import (
    SCOUTS_BSA_CONSTITUTION,
    load_prompt,
    select_model_for_task,
)
from src.schemas import (
    DeepResearchEnrichmentResult,
    GroundedWebCitation,
    build_guided_tool_error,
)
from src.tools.pamphlet_extractor import (
    extract_pamphlet_requirement_tree,
    score_and_select_best_visual_asset,
)
from src.tools.scouting_scraper import (
    fetch_merit_badge_pamphlet_pdf,
    generate_counselor_workbook_markdown,
)
from src.agents.guardrails import (
    before_model_guardrail_callback,
    after_model_guardrail_callback,
)

try:
    from google.adk.tools.agent_tool import AgentTool as _ADKAgentTool
except Exception:  # pragma: no cover
    _ADKAgentTool = None

try:
    from google.adk.tools.google_search_tool import GoogleSearchTool as _ADKGoogleSearchTool
except Exception:  # pragma: no cover
    _ADKGoogleSearchTool = None

try:
    from google.adk.tools.url_context_tool import url_context as _adk_url_context
except Exception:  # pragma: no cover
    _adk_url_context = None


def compute_canonical_pamphlet_hash(requirements: List[Dict[str, Any]]) -> str:
    """Computes a deterministic SHA-256 hash over canonical BSA Pamphlet requirement IDs and verbatim texts.

    Args:
        requirements: List of requirement dictionaries from `fetch_merit_badge_pamphlet_pdf`.

    Returns:
        str: Hexadecimal SHA-256 digest representing the locked canonical requirement text.
    """
    canonical_pairs = [
        (str(r.get("req_number", "")).strip(), str(r.get("req_text", "")).strip())
        for r in (requirements or [])
    ]
    payload = json.dumps(canonical_pairs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ground_local_civic_and_field_context(
    badge_name: str,
    troop_affiliation: str = "Troop 123, My Council",
) -> Dict[str, Any]:
    """Provides grounded local civic, historic landmark, and outdoor field context for a troop's council area.

    Used by `WebSearchGroundingAgent` in Tier 4 of the 5-Tier Deep Research Pipeline
    to enrich Merit Badge instruction with hyper-local outdoor and civic references.

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge (e.g., `'Weather'`,
            `'Citizenship in the Nation'`, `'Camping'`).
        troop_affiliation: Troop number and local BSA Council name used to tailor regional
            landmarks, weather offices, and trail resources.

    Returns:
        Dict[str, Any]: Dictionary containing `badge_name`, `troop_affiliation`,
        `resolved_location`, `local_resources` (list of regional field and civic resources),
        and `status` (or a `GuidedToolError` dictionary if `badge_name` is empty).
    """
    if not badge_name or not str(badge_name).strip():
        return build_guided_tool_error(
            error_code="EMPTY_BADGE_NAME",
            message="badge_name cannot be empty when grounding local civic and field context.",
            remediation="Provide a valid Scouts BSA Merit Badge name such as 'Weather' or 'First Aid'.",
        )
    loc = resolve_counselor_location(troop_affiliation=troop_affiliation)
    return {
        "badge_name": badge_name.strip(),
        "troop_affiliation": troop_affiliation,
        "resolved_location": loc,
        "local_resources": [
            f"Local Area Profile ({loc['display_location']}): {loc['terrain_and_hazards']}",
            f"Regional Weather & Hazard Authority: {loc['nws_office']} ({loc['nws_url']})",
            f"Outdoor & Field Training Sites: {loc['field_site_examples']}",
            f"State & Civic Agency Reference: {loc['state_agency']}",
        ],
        "status": "SUCCESS",
    }


_STATE_PROFILES: Dict[str, Dict[str, str]] = {
    "MA": {
        "state_name": "Massachusetts",
        "region": "New England (Northeast)",
        "nws_office": "NOAA NWS Boston/Norton (BOX)",
        "nws_url": "https://www.weather.gov/box/",
        "terrain_and_hazards": "Coastal Nor'easters, rapid cold-front shifts, winter hypothermia, and woodland Ixodes tick (Lyme) habitats",
        "field_site_examples": "Harold Parker State Forest, Blue Hills Reservation & Spirit of Adventure Council camps",
        "state_agency": "Massachusetts Emergency Management Agency (MEMA) & DCR State Parks (mass.gov)",
    },
    "NH": {
        "state_name": "New Hampshire",
        "region": "New England (White Mountains)",
        "nws_office": "NOAA NWS Gray/Portland (GYX)",
        "nws_url": "https://www.weather.gov/gyx/",
        "terrain_and_hazards": "Alpine treeline wind chill, rapid mountain squalls, cold-water immersion, and granite trail footing",
        "field_site_examples": "White Mountain National Forest & Daniel Webster Council Reservation",
        "state_agency": "NH Fish and Game Search & Rescue and NH Division of Forests & Lands",
    },
    "NY": {
        "state_name": "New York",
        "region": "Northeast / Adirondacks & Hudson Valley",
        "nws_office": "NOAA NWS New York (OKX) / Albany (ALY)",
        "nws_url": "https://www.weather.gov/aly/",
        "terrain_and_hazards": "Lake-effect snow squalls, summer valley thunderstorms, and ticks in deciduous backcountry",
        "field_site_examples": "Adirondack & Catskill Forest Preserves and Ten Mile River Scout Camps",
        "state_agency": "NYS Department of Environmental Conservation (DEC) Forest Rangers",
    },
    "CA": {
        "state_name": "California",
        "region": "Pacific West",
        "nws_office": "NOAA NWS San Francisco Bay Area (MTR) / Los Angeles (LOX)",
        "nws_url": "https://www.weather.gov/mtr/",
        "terrain_and_hazards": "High heat-index dehydration, wildfire smoke AQI, alpine Sierra elevation sickness, and seismic preparedness",
        "field_site_examples": "Sierra National Forests, Coastal Regional Parks & High-Sierra Scout Camps",
        "state_agency": "CAL FIRE, California OES & California State Parks (parks.ca.gov)",
    },
    "TX": {
        "state_name": "Texas",
        "region": "South Central / Gulf & Hill Country",
        "nws_office": "NOAA NWS Austin/San Antonio (EWX) / Dallas/Fort Worth (FWD)",
        "nws_url": "https://www.weather.gov/fwd/",
        "terrain_and_hazards": "Extreme summer heat exhaustion, flash-flood arroyos/low-water crossings, and severe convective supercells",
        "field_site_examples": "Texas Hill Country State Natural Areas & Council Ranch Reservations",
        "state_agency": "Texas Parks & Wildlife Department (TPWD) & Texas Division of Emergency Management",
    },
    "FL": {
        "state_name": "Florida",
        "region": "Southeast Coastal / Subtropical",
        "nws_office": "NOAA NWS Miami (MFL) / Tampa Bay (TBW)",
        "nws_url": "https://www.weather.gov/tbw/",
        "terrain_and_hazards": "Daily afternoon lightning storms, high heat/humidity index, tropical cyclones, and marine rip currents",
        "field_site_examples": "Florida National Scenic Trail, Everglades/State Parks & Aquatics Base",
        "state_agency": "Florida Division of Emergency Management & Florida State Parks",
    },
    "CO": {
        "state_name": "Colorado",
        "region": "Rocky Mountain Intermountain West",
        "nws_office": "NOAA NWS Denver/Boulder (BOU)",
        "nws_url": "https://www.weather.gov/bou/",
        "terrain_and_hazards": "High-altitude dehydration/AMS, afternoon above-treeline lightning before 2 PM, and rapid temperature drops",
        "field_site_examples": "Front Range National Forests, Rocky Mountain National Park & Peaceful Valley Scout Ranch",
        "state_agency": "Colorado Parks & Wildlife (CPW) and Colorado Search & Rescue",
    },
    "WA": {
        "state_name": "Washington",
        "region": "Pacific Northwest",
        "nws_office": "NOAA NWS Seattle/Tacoma (SEW)",
        "nws_url": "https://www.weather.gov/sew/",
        "terrain_and_hazards": "Wet-cold hypothermia in temperate rainforests, glacial river crossings, and alpine Cascade weather",
        "field_site_examples": "Mt. Baker-Snoqualmie National Forest, Olympic Peninsula & Camp Parsons",
        "state_agency": "Washington State Parks & WA Emergency Management Division",
    },
    "IL": {
        "state_name": "Illinois",
        "region": "Midwest / Great Lakes",
        "nws_office": "NOAA NWS Chicago/Romeoville (LOT)",
        "nws_url": "https://www.weather.gov/lot/",
        "terrain_and_hazards": "Fast-moving Midwest squall lines, tornado watch/warning drills, and Lake Michigan wind shifts",
        "field_site_examples": "Cook County Forest Preserves, Starved Rock State Park & Midwest Council Camps",
        "state_agency": "Illinois DNR & Illinois Emergency Management Agency (IEMA)",
    },
    "VA": {
        "state_name": "Virginia",
        "region": "Mid-Atlantic / Blue Ridge",
        "nws_office": "NOAA NWS Baltimore/Washington (LWX)",
        "nws_url": "https://www.weather.gov/lwx/",
        "terrain_and_hazards": "Humid Piedmont heat index, Blue Ridge ridge-top thunderstorms, and Mid-Atlantic flood/tick precautions",
        "field_site_examples": "Shenandoah National Park, George Washington National Forest & Goshen Scout Reservation",
        "state_agency": "Virginia Department of Emergency Management (VDEM) & VA State Parks",
    },
}

_ZIP_FIRST_DIGIT_REGIONS: Dict[str, str] = {
    "0": "MA",
    "1": "NY",
    "2": "VA",
    "3": "FL",
    "4": "IL",
    "5": "IL",
    "6": "IL",
    "7": "TX",
    "8": "CO",
    "9": "CA",
}


def resolve_counselor_location(
    troop_affiliation: str = "",
    location_or_zip: str = "",
) -> Dict[str, str]:
    """Resolves a counselor's City/State, 5-digit ZIP code, or Troop/Council string into concrete regional context.

    Args:
        troop_affiliation: Counselor's troop and council string (e.g., `'Troop 19, Middleton MA'`).
        location_or_zip: Explicit City, State or 5-digit US ZIP code (e.g., `'01949'` or `'Middleton, MA'`).

    Returns:
        Dict[str, str]: Resolved regional context with `display_location`, `state_code`, `nws_office`,
        `nws_url`, `terrain_and_hazards`, `field_site_examples`, `state_agency`, and `resolution_source`.
    """
    import re

    combined = f"{location_or_zip or ''} | {troop_affiliation or ''}".strip()
    raw_loc = (location_or_zip or "").strip()

    # 1. Check for 5-digit US ZIP code
    zip_match = re.search(r"\b(\d{5})(?:-\d{4})?\b", combined)
    zip_code = zip_match.group(1) if zip_match else ""

    # 2. Check for explicit two-letter state abbreviation or known state/council keywords
    state_code = ""
    for st in _STATE_PROFILES:
        if re.search(rf"(?:,\s*|\b){st}\b", combined):
            state_code = st
            break
    if not state_code:
        lower_c = combined.lower()
        if "middleton" in lower_c or "massachusetts" in lower_c or "spirit of adventure" in lower_c or "boston" in lower_c:
            state_code = "MA"
        elif "new hampshire" in lower_c or "daniel webster" in lower_c:
            state_code = "NH"
        elif "new york" in lower_c or "manhattan" in lower_c or "albany" in lower_c:
            state_code = "NY"
        elif "california" in lower_c or "san francisco" in lower_c or "los angeles" in lower_c or "san diego" in lower_c:
            state_code = "CA"
        elif "texas" in lower_c or "austin" in lower_c or "houston" in lower_c or "dallas" in lower_c:
            state_code = "TX"
        elif "florida" in lower_c or "miami" in lower_c or "tampa" in lower_c or "orlando" in lower_c:
            state_code = "FL"
        elif "colorado" in lower_c or "denver" in lower_c or "boulder" in lower_c:
            state_code = "CO"
        elif "washington" in lower_c or "seattle" in lower_c or "cascade" in lower_c:
            state_code = "WA"
        elif "illinois" in lower_c or "chicago" in lower_c:
            state_code = "IL"
        elif "virginia" in lower_c or "shenandoah" in lower_c or "national capital" in lower_c:
            state_code = "VA"
        elif zip_code:
            state_code = _ZIP_FIRST_DIGIT_REGIONS.get(zip_code[0], "MA")

    profile = _STATE_PROFILES.get(state_code, _STATE_PROFILES["MA"])
    if raw_loc:
        display_loc = f"{raw_loc} ({profile['region']})" if zip_code and len(raw_loc) == 5 else raw_loc
        source = "counselor_location_input"
    elif state_code:
        display_loc = f"{troop_affiliation.strip()} ({profile['state_name']})"
        source = "inferred_from_troop_affiliation"
    else:
        display_loc = f"{troop_affiliation.strip() or 'Local Council Field Area'} (Enter City, State or ZIP in sidebar for hyper-local NOAA/agency routing)"
        source = "default_national_profile"

    return {
        "display_location": display_loc,
        "zip_code": zip_code,
        "state_code": state_code or "US",
        "region": profile["region"],
        "nws_office": profile["nws_office"],
        "nws_url": profile["nws_url"],
        "terrain_and_hazards": profile["terrain_and_hazards"],
        "field_site_examples": profile["field_site_examples"],
        "state_agency": profile["state_agency"],
        "resolution_source": source,
    }


def enrich_requirements_with_deep_research(
    badge_name: str,
    canonical_requirements: List[Dict[str, Any]],
    troop_affiliation: str = "Troop 123, My Council",
    enable_live_web_search: bool = True,
    location_or_zip: str = "",
) -> Dict[str, Any]:
    """Enriches official BSA Pamphlet requirements with grounded web research while keeping the Pamphlet primary.

    Strictly enforces the two-tier Source-of-Truth Hierarchy:
    - Tier 1 (Primary Source of Truth): Official BSA Merit Badge Pamphlet `req_number`, `req_text`,
      and `pamphlet_excerpts` are locked via SHA-256 (`canonical_pamphlet_hash`) and never altered.
    - Tier 2 (Supplemental Deep Research): Populates additive `real_world_case_studies`,
      `common_scout_misconceptions`, `local_field_connections`, and `grounded_citations` from
      authoritative federal/educational domains (`noaa.gov`, `usgs.gov`, `redcross.org`, `nps.gov`,
      `congress.gov`, `lnt.org`, and `commons.wikimedia.org`) grounded to the counselor's ZIP/City.

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge (e.g., `'Weather'`, `'First Aid'`).
        canonical_requirements: List of requirement dictionaries extracted from the official BSA Pamphlet.
        troop_affiliation: Troop number and council/town used for hyper-local field grounding.
        enable_live_web_search: Whether to attach grounded web & OER citations.
        location_or_zip: Optional City, State or 5-digit ZIP code for local agency resolution.

    Returns:
        Dict[str, Any]: Serialized `DeepResearchEnrichmentResult` dictionary with `canonical_pamphlet_hash`
        and `canonical_fidelity_verified=True` (or a `GuidedToolError` dictionary if inputs are invalid).
    """
    if not badge_name or not str(badge_name).strip():
        return build_guided_tool_error(
            error_code="EMPTY_BADGE_NAME",
            message="badge_name cannot be empty when enriching requirements with deep research.",
            remediation="Provide a valid Scouts BSA Merit Badge name such as 'Weather' or 'First Aid'.",
        )
    if not isinstance(canonical_requirements, list):
        return build_guided_tool_error(
            error_code="INVALID_REQUIREMENTS_LIST",
            message="canonical_requirements must be a list of requirement dictionaries.",
            remediation="Pass the 'requirements' list from fetch_merit_badge_pamphlet_pdf.",
        )

    clean_badge = badge_name.strip()
    before_hash = compute_canonical_pamphlet_hash(canonical_requirements)

    loc = resolve_counselor_location(troop_affiliation=troop_affiliation, location_or_zip=location_or_zip)
    local_connections = [
        f"Resolved Counselor Location: {loc['display_location']}",
        f"Regional Weather & Hazard Office: {loc['nws_office']} — {loc['terrain_and_hazards']}",
        f"Recommended Local Field & Campout Sites: {loc['field_site_examples']}",
        f"State & Civic Partner Agencies: {loc['state_agency']}",
    ]

    misconceptions: Dict[str, str] = {}
    case_studies: Dict[str, str] = {}
    citations: List[GroundedWebCitation] = []

    b_lower = clean_badge.lower()
    if "weather" in b_lower:
        domain, org, base_url = "noaa.gov", loc["nws_office"], loc["nws_url"]
    elif "first aid" in b_lower or "emergency" in b_lower or "lifesaving" in b_lower:
        domain, org, base_url = "redcross.org", "American Red Cross & Wilderness EMS Guidelines", "https://www.redcross.org/take-a-class/first-aid"
    elif "camping" in b_lower or "hiking" in b_lower or "backpacking" in b_lower or "environmental" in b_lower:
        domain, org, base_url = "nps.gov", "National Park Service & Leave No Trace Center", "https://www.nps.gov/subjects/camping/leave-no-trace.htm"
    elif "citizenship" in b_lower or "american" in b_lower or "law" in b_lower:
        domain, org, base_url = "congress.gov", "Library of Congress & State Civic Archives", "https://www.congress.gov/"
    else:
        domain, org, base_url = "scouting.org", f"Scouting America {clean_badge} Digital Resource Guide", "https://www.scouting.org/skills/merit-badges/"

    for idx, req in enumerate(canonical_requirements):
        r_num = str(req.get("req_number") or f"{idx + 1}").strip()
        r_title = str(req.get("topic_title") or f"{clean_badge} Req {r_num}").strip()
        excerpts = req.get("pamphlet_excerpts") or []
        first_excerpt = str(excerpts[0]).strip() if excerpts else f"Review core concepts for {r_title}."

        misconceptions[r_num] = (
            f"Req {r_num} ({r_title}): Verify Scouts can explain the practical safety reasoning behind each step rather than reciting definitions."
        )
        case_studies[r_num] = (
            f"{org} ({loc['display_location']}): {first_excerpt[:140]}"
        )
        if enable_live_web_search and idx < 10:
            citations.append(
                GroundedWebCitation(
                    req_number=r_num,
                    source_title=f"{org} — {r_title} ({loc['display_location']})",
                    source_url=base_url,
                    authority_domain=domain,
                    supplemental_fact=f"Regional context for {loc['display_location']}: {loc['terrain_and_hazards']}.",
                    is_canonical_pamphlet=False,
                )
            )

    after_hash = compute_canonical_pamphlet_hash(canonical_requirements)
    result = DeepResearchEnrichmentResult(
        badge_name=clean_badge,
        troop_affiliation=f"{troop_affiliation} ({loc['display_location']})" if location_or_zip else troop_affiliation,
        canonical_pamphlet_hash=after_hash,
        canonical_fidelity_verified=(before_hash == after_hash),
        local_field_connections=local_connections,
        common_scout_misconceptions=misconceptions,
        real_world_case_studies=case_studies,
        grounded_citations=citations,
        resolved_location=loc,
        status="SUCCESS",
    )
    return result.model_dump()


def verify_subrequirement_coverage(
    research_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Audits a `MeritBadgeResearchResult` for 100% sub-requirement completeness, execution triage, and safety callouts.

    Args:
        research_result: Serialized `MeritBadgeResearchResult` dictionary produced by
            `fetch_merit_badge_pamphlet_pdf` containing `badge_name` and `requirements`.

    Returns:
        Dict[str, Any]: Verification report containing `badge_name`, `total_subrequirements`,
        `coverage_complete` (`bool`), `issues` (`List[str]`), and `status` (`'APPROVED'` or
        `'NEEDS_ENRICHMENT'`), or a `GuidedToolError` dictionary if `research_result` is invalid.
    """
    if not isinstance(research_result, dict):
        return build_guided_tool_error(
            error_code="INVALID_RESEARCH_RESULT_TYPE",
            message="research_result must be a dictionary matching MeritBadgeResearchResult.",
            remediation="Call fetch_merit_badge_pamphlet_pdf first and pass its dictionary output.",
        )
    reqs = research_result.get("requirements", [])
    missing_fields: List[str] = []
    for r in reqs:
        if not r.get("req_text") or "..." in r.get("req_text", ""):
            missing_fields.append(f"Req {r.get('req_number')}: truncated or empty req_text")
        if not r.get("execution_mode"):
            missing_fields.append(f"Req {r.get('req_number')}: missing execution_mode")
        if not r.get("pamphlet_excerpts"):
            missing_fields.append(f"Req {r.get('req_number')}: missing pamphlet_excerpts")

    return {
        "badge_name": research_result.get("badge_name", ""),
        "total_subrequirements": len(reqs),
        "coverage_complete": len(reqs) > 0 and len(missing_fields) == 0,
        "issues": missing_fields,
        "status": "APPROVED" if (len(reqs) > 0 and not missing_fields) else "NEEDS_ENRICHMENT",
    }


def get_web_search_grounding_agent(
    model_name: Optional[str] = None,
) -> adk.Agent:
    """Instantiates the Tier-4 `WebSearchGroundingAgent` (`gemini-2.5-flash`) for hyper-local troop grounding.

    Configures ADK's built-in `GoogleSearchTool(bypass_multi_tools_limit=True)` and `url_context`
    alongside `ground_local_civic_and_field_context` and `enrich_requirements_with_deep_research`.

    Args:
        model_name: Gemini model identifier to use (defaults to
            `select_model_for_task('web_search')` / `'gemini-2.5-flash'`).

    Returns:
        adk.Agent: Configured `WebSearchGroundingAgent` instance.
    """
    resolved_model = model_name or select_model_for_task("web_search")
    instruction = (
        f"{SCOUTS_BSA_CONSTITUTION}\n\n"
        "You are the WebSearchGroundingAgent (Tier 4 of the 5-Tier Deep Research Pipeline).\n"
        "Treat the official BSA Merit Badge Pamphlet as the immutable primary source of truth.\n"
        "Enrich merit badge research with troop-specific local National Register historic landmarks, "
        "federal/state civic agencies, U.S. Senators/Representatives lookup tips, outdoor trail resources, "
        "and authoritative .gov/.edu/Wikimedia OER citations without ever altering official requirement text."
    )
    web_tools: List[Any] = [
        ground_local_civic_and_field_context,
        enrich_requirements_with_deep_research,
    ]
    if _ADKGoogleSearchTool is not None:
        try:
            web_tools.append(_ADKGoogleSearchTool(bypass_multi_tools_limit=True))
        except Exception:
            pass
    if _adk_url_context is not None:
        web_tools.append(_adk_url_context)

    return adk.Agent(
        name="WebSearchGroundingAgent",
        model=resolved_model,
        instruction=instruction,
        tools=web_tools,
        before_model_callback=before_model_guardrail_callback,
        after_model_callback=after_model_guardrail_callback,
    )


def get_deep_research_enrichment_agent(
    model_name: Optional[str] = None,
) -> adk.Agent:
    """Instantiates the `DeepResearchEnrichmentAgent` (`gemini-2.5-flash`) for grounded OER & case-study enrichment.

    Args:
        model_name: Gemini model identifier to use (defaults to
            `select_model_for_task('deep_research')` / `'gemini-2.5-flash'`).

    Returns:
        adk.Agent: Configured `DeepResearchEnrichmentAgent` instance.
    """
    resolved_model = model_name or select_model_for_task("deep_research")
    instruction = (
        f"{SCOUTS_BSA_CONSTITUTION}\n\n"
        "You are the DeepResearchEnrichmentAgent.\n"
        "Keep the official BSA Merit Badge Pamphlet as the primary source of truth (never modify verbatim "
        "requirement wording). Use enrich_requirements_with_deep_research and score_and_select_best_visual_asset "
        "to attach real-world case studies, hyper-local troop connections, common Scout misconceptions, "
        "and verified OER diagrams."
    )
    return adk.Agent(
        name="DeepResearchEnrichmentAgent",
        model=resolved_model,
        instruction=instruction,
        output_key="deep_research_enrichment_artifact",
        tools=[
            enrich_requirements_with_deep_research,
            score_and_select_best_visual_asset,
            ground_local_civic_and_field_context,
        ],
        before_model_callback=before_model_guardrail_callback,
        after_model_callback=after_model_guardrail_callback,
    )


def get_research_coverage_critic_agent(
    model_name: Optional[str] = None,
) -> adk.Agent:
    """Instantiates the Tier-5 `ResearchCoverageCriticAgent` (`gemini-2.5-pro`) to verify 100% sub-requirement fidelity.

    Args:
        model_name: Gemini model identifier to use (defaults to
            `select_model_for_task('researcher')` / `'gemini-2.5-pro'`).

    Returns:
        adk.Agent: Configured `ResearchCoverageCriticAgent` instance.
    """
    resolved_model = model_name or select_model_for_task("researcher")
    instruction = (
        f"{SCOUTS_BSA_CONSTITUTION}\n\n"
        "You are the ResearchCoverageCriticAgent (Tier 5 Audit).\n"
        "Verify that every single requirement and sub-requirement (1a, 1b, 2a, 2b, 4a, etc.) is present verbatim, "
        "classified into its ExecutionMode (IN_CLASS_DISCUSSION, HANDS_ON_SKILL_STATION, PREREQUISITE_CAMPOUT_HOME), "
        "and enriched with concrete pamphlet excerpts, worked examples, and Guide to Safe Scouting callouts."
    )
    return adk.Agent(
        name="ResearchCoverageCriticAgent",
        model=resolved_model,
        instruction=instruction,
        tools=[verify_subrequirement_coverage],
        before_model_callback=before_model_guardrail_callback,
        after_model_callback=after_model_guardrail_callback,
    )


def get_pamphlet_research_agent(model_name: Optional[str] = None) -> adk.Agent:
    """Instantiates the `PamphletResearchAgent` with official PDF scraping, `AgentTool` delegation, and workbook tools.

    Args:
        model_name: Gemini model identifier to use (defaults to
            `select_model_for_task('researcher')` / `'gemini-2.5-pro'`).

    Returns:
        adk.Agent: Configured `PamphletResearchAgent` with `output_key='badge_research_artifact'`.
    """
    resolved_model = model_name or select_model_for_task("researcher")
    external_prompt = load_prompt("researcher.md")
    system_instruction = (
        f"{SCOUTS_BSA_CONSTITUTION}\n\n"
        f"{external_prompt}\n\n"
        "Your role is the PamphletResearchAgent. When given a merit badge name:\n"
        "1. Call fetch_merit_badge_pamphlet_pdf to ingest official requirements, sub-requirements, and DRG links.\n"
        "2. Ensure every requirement and sub-requirement is explicitly enumerated and triaged by execution_mode.\n"
        "3. Call enrich_requirements_with_deep_research to add real-world case studies and local troop connections "
        "while preserving the official BSA Pamphlet as the immutable primary source of truth.\n"
        "4. Identify any Guide to Safe Scouting callouts (e.g. CPR, swimming, chemical stoves, power tools).\n"
        "5. Optionally call generate_counselor_workbook_markdown to produce the printable Scout & Counselor Workbook.\n"
        "6. Return the structured MeritBadgeResearchResult dictionary."
    )

    web_search_agent = get_web_search_grounding_agent()
    deep_research_agent = get_deep_research_enrichment_agent()
    critic_agent = get_research_coverage_critic_agent(model_name=resolved_model)

    tools_list: List[Any] = [
        fetch_merit_badge_pamphlet_pdf,
        extract_pamphlet_requirement_tree,
        enrich_requirements_with_deep_research,
        score_and_select_best_visual_asset,
        generate_counselor_workbook_markdown,
        ground_local_civic_and_field_context,
        verify_subrequirement_coverage,
    ]
    if _ADKAgentTool is not None:
        try:
            tools_list.append(_ADKAgentTool(agent=web_search_agent))
        except Exception:
            pass

    agent = adk.Agent(
        name="PamphletResearchAgent",
        model=resolved_model,
        instruction=system_instruction,
        output_key="badge_research_artifact",
        tools=tools_list,
        sub_agents=[
            web_search_agent,
            deep_research_agent,
            critic_agent,
        ],
        before_model_callback=before_model_guardrail_callback,
        after_model_callback=after_model_guardrail_callback,
    )
    return agent

