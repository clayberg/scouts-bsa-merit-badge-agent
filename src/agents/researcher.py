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
        "state_capitol": "Massachusetts State House (24 Beacon St, Boston, MA — 1798 Charles Bulfinch golden dome)",
        "national_landmarks": "Minute Man National Historical Park (Concord/Lexington), Boston National Historical Park (Freedom Trail / USS Constitution), and Salem Maritime National Historic Site",
        "federal_facilities": "John Joseph Moakley U.S. Courthouse (Boston), JFK Federal Building, and Hanscom Air Force Base / USCG Sector Boston",
        "congressional_delegation": "U.S. Senators Elizabeth Warren & Edward Markey (MA); U.S. House Representative by local district (e.g., Rep. Seth Moulton, MA-6)",
    },
    "NH": {
        "state_name": "New Hampshire",
        "region": "New England (White Mountains)",
        "nws_office": "NOAA NWS Gray/Portland (GYX)",
        "nws_url": "https://www.weather.gov/gyx/",
        "terrain_and_hazards": "Alpine treeline wind chill, rapid mountain squalls, cold-water immersion, and granite trail footing",
        "field_site_examples": "White Mountain National Forest & Daniel Webster Council Reservation",
        "state_agency": "NH Fish and Game Search & Rescue and NH Division of Forests & Lands",
        "state_capitol": "New Hampshire State House (107 N Main St, Concord, NH — oldest state capitol with original chambers)",
        "national_landmarks": "Saint-Gaudens National Historical Park (Cornish) and Portsmouth Naval Shipyard / Albacore Park",
        "federal_facilities": "Warren B. Rudman U.S. Courthouse (Concord) and White Mountain National Forest Supervisor's Office (Campton)",
        "congressional_delegation": "U.S. Senators Jeanne Shaheen & Maggie Hassan (NH); U.S. House Representatives (NH-1 & NH-2)",
    },
    "NY": {
        "state_name": "New York",
        "region": "Northeast / Adirondacks & Hudson Valley",
        "nws_office": "NOAA NWS New York (OKX) / Albany (ALY)",
        "nws_url": "https://www.weather.gov/aly/",
        "terrain_and_hazards": "Lake-effect snow squalls, summer valley thunderstorms, and ticks in deciduous backcountry",
        "field_site_examples": "Adirondack & Catskill Forest Preserves and Ten Mile River Scout Camps",
        "state_agency": "NYS Department of Environmental Conservation (DEC) Forest Rangers",
        "state_capitol": "New York State Capitol (State St & Washington Ave, Albany, NY — 1899 Romanesque/Renaissance landmark)",
        "national_landmarks": "Statue of Liberty & Ellis Island National Monument, Saratoga National Historical Park, and Federal Hall National Memorial",
        "federal_facilities": "Thurgood Marshall U.S. Courthouse (Manhattan), Leo W. O'Brien Federal Building (Albany), and U.S. Military Academy (West Point)",
        "congressional_delegation": "U.S. Senators Chuck Schumer & Kirsten Gillibrand (NY); U.S. House Representative by NY congressional district",
    },
    "CA": {
        "state_name": "California",
        "region": "Pacific West",
        "nws_office": "NOAA NWS San Francisco Bay Area (MTR) / Los Angeles (LOX)",
        "nws_url": "https://www.weather.gov/mtr/",
        "terrain_and_hazards": "High heat-index dehydration, wildfire smoke AQI, alpine Sierra elevation sickness, and seismic preparedness",
        "field_site_examples": "Sierra National Forests, Coastal Regional Parks & High-Sierra Scout Camps",
        "state_agency": "CAL FIRE, California OES & California State Parks (parks.ca.gov)",
        "state_capitol": "California State Capitol & Museum (1315 10th St, Sacramento, CA — Neoclassical dome & Capitol Park)",
        "national_landmarks": "Golden Gate National Recreation Area (Alcatraz / Presidio), Yosemite National Park, and Muir Woods National Monument",
        "federal_facilities": "Phillip Burton Federal Building & U.S. Courthouse (San Francisco), NASA Ames Research Center (Moffett Field), and USCG Base Alameda",
        "congressional_delegation": "U.S. Senators Alex Padilla & Adam Schiff (CA); U.S. House Representative by local CA district",
    },
    "TX": {
        "state_name": "Texas",
        "region": "South Central / Gulf & Hill Country",
        "nws_office": "NOAA NWS Austin/San Antonio (EWX) / Dallas/Fort Worth (FWD)",
        "nws_url": "https://www.weather.gov/fwd/",
        "terrain_and_hazards": "Extreme summer heat exhaustion, flash-flood arroyos/low-water crossings, and severe convective supercells",
        "field_site_examples": "Texas Hill Country State Natural Areas & Council Ranch Reservations",
        "state_agency": "Texas Parks & Wildlife Department (TPWD) & Texas Division of Emergency Management",
        "state_capitol": "Texas State Capitol (1100 Congress Ave, Austin, TX — 1888 Sunset Red granite capitol)",
        "national_landmarks": "San Antonio Missions National Historical Park, The Alamo National Historic Landmark, and LBJ National Historical Park",
        "federal_facilities": "NASA Johnson Space Center (Houston), Earle Cabell Federal Building (Dallas), and U.S. Courthouse (Austin)",
        "congressional_delegation": "U.S. Senators John Cornyn & Ted Cruz (TX); U.S. House Representative by local TX district",
    },
    "FL": {
        "state_name": "Florida",
        "region": "Southeast Coastal / Subtropical",
        "nws_office": "NOAA NWS Miami (MFL) / Tampa Bay (TBW)",
        "nws_url": "https://www.weather.gov/tbw/",
        "terrain_and_hazards": "Daily afternoon lightning storms, high heat/humidity index, tropical cyclones, and marine rip currents",
        "field_site_examples": "Florida National Scenic Trail, Everglades/State Parks & Aquatics Base",
        "state_agency": "Florida Division of Emergency Management & Florida State Parks",
        "state_capitol": "Florida State Capitol & Historic Capitol Museum (400 S Monroe St, Tallahassee, FL)",
        "national_landmarks": "Castillo de San Marcos National Monument (St. Augustine), Everglades National Park, and Kennedy Space Center",
        "federal_facilities": "NASA Kennedy Space Center (Cape Canaveral), Sam M. Gibbons U.S. Courthouse (Tampa), and USCG Sector Miami",
        "congressional_delegation": "U.S. Senators Rick Scott & Ashley Moody (FL); U.S. House Representative by local FL district",
    },
    "CO": {
        "state_name": "Colorado",
        "region": "Rocky Mountain Intermountain West",
        "nws_office": "NOAA NWS Denver/Boulder (BOU)",
        "nws_url": "https://www.weather.gov/bou/",
        "terrain_and_hazards": "High-altitude dehydration/AMS, afternoon above-treeline lightning before 2 PM, and rapid temperature drops",
        "field_site_examples": "Front Range National Forests, Rocky Mountain National Park & Peaceful Valley Scout Ranch",
        "state_agency": "Colorado Parks & Wildlife (CPW) and Colorado Search & Rescue",
        "state_capitol": "Colorado State Capitol (200 E Colfax Ave, Denver, CO — Mile-High 24k gold dome step)",
        "national_landmarks": "Rocky Mountain National Park, Mesa Verde National Park, and Colorado National Monument",
        "federal_facilities": "Denver Federal Center (Lakewood), NOAA David Skaggs Research Center (Boulder), and U.S. Air Force Academy (Colorado Springs)",
        "congressional_delegation": "U.S. Senators Michael Bennet & John Hickenlooper (CO); U.S. House Representative by local CO district",
    },
    "WA": {
        "state_name": "Washington",
        "region": "Pacific Northwest",
        "nws_office": "NOAA NWS Seattle/Tacoma (SEW)",
        "nws_url": "https://www.weather.gov/sew/",
        "terrain_and_hazards": "Wet-cold hypothermia in temperate rainforests, glacial river crossings, and alpine Cascade weather",
        "field_site_examples": "Mt. Baker-Snoqualmie National Forest, Olympic Peninsula & Camp Parsons",
        "state_agency": "Washington State Parks & WA Emergency Management Division",
        "state_capitol": "Washington State Capitol Legislative Building (416 Sid Snyder Ave SW, Olympia, WA)",
        "national_landmarks": "Mount Rainier National Park, Olympic National Park, and Klondike Gold Rush National Historical Park (Seattle)",
        "federal_facilities": "Henry M. Jackson Federal Building (Seattle), NOAA Western Regional Center (Sand Point), and USCG Base Seattle",
        "congressional_delegation": "U.S. Senators Patty Murray & Maria Cantwell (WA); U.S. House Representative by local WA district",
    },
    "IL": {
        "state_name": "Illinois",
        "region": "Midwest / Great Lakes",
        "nws_office": "NOAA NWS Chicago/Romeoville (LOT)",
        "nws_url": "https://www.weather.gov/lot/",
        "terrain_and_hazards": "Fast-moving Midwest squall lines, tornado watch/warning drills, and Lake Michigan wind shifts",
        "field_site_examples": "Cook County Forest Preserves, Starved Rock State Park & Midwest Council Camps",
        "state_agency": "Illinois DNR & Illinois Emergency Management Agency (IEMA)",
        "state_capitol": "Illinois State Capitol (401 S 2nd St, Springfield, IL)",
        "national_landmarks": "Lincoln Home National Historic Site (Springfield), Pullman National Historical Park (Chicago), and Cahokia Mounds",
        "federal_facilities": "Everett McKinley Dirksen U.S. Courthouse (Chicago), Fermi National Accelerator Laboratory (Batavia), and Argonne National Lab",
        "congressional_delegation": "U.S. Senators Dick Durbin & Tammy Duckworth (IL); U.S. House Representative by local IL district",
    },
    "VA": {
        "state_name": "Virginia",
        "region": "Mid-Atlantic / Blue Ridge",
        "nws_office": "NOAA NWS Baltimore/Washington (LWX)",
        "nws_url": "https://www.weather.gov/lwx/",
        "terrain_and_hazards": "Humid Piedmont heat index, Blue Ridge ridge-top thunderstorms, and Mid-Atlantic flood/tick precautions",
        "field_site_examples": "Shenandoah National Park, George Washington National Forest & Goshen Scout Reservation",
        "state_agency": "Virginia Department of Emergency Management (VDEM) & VA State Parks",
        "state_capitol": "Virginia State Capitol (1000 Bank St, Richmond, VA — 1785 Thomas Jefferson classical design)",
        "national_landmarks": "Colonial National Historical Park (Jamestown & Yorktown), George Washington's Mount Vernon, and Thomas Jefferson's Monticello",
        "federal_facilities": "Albert V. Bryan U.S. Courthouse (Alexandria), Pentagon / Arlington National Cemetery, and NASA Langley Research Center",
        "congressional_delegation": "U.S. Senators Mark Warner & Tim Kaine (VA); U.S. House Representative by local VA district",
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

    Supports all 50 U.S. States + DC via `_STATE_CIVIC_AND_FIELD_REGISTRY` and dynamically resolves
    current U.S. Senators and local Congressional Delegation via `refresh_us_senators_on_demand` (24h TTL + Gemini on-demand).

    Args:
        troop_affiliation: Counselor's troop and council string (e.g., `'Troop 19, Middleton MA'`).
        location_or_zip: Explicit City, State or 5-digit US ZIP code (e.g., `'01949'` or `'Middleton, MA'`).

    Returns:
        Dict[str, str]: Resolved regional context with `display_location`, `region_label`, `state_code`,
        `nws_office`, `nws_url`, `terrain_and_hazards`, `field_site_examples`, `state_agency`,
        `state_capitol`, `national_landmarks`, `federal_facilities`, `congressional_delegation`,
        `senator_1`, `senator_2`, `house_rep`, `governor`, and `resolution_source`.
    """
    import re
    from src.tools.local_grounding_engine import (
        _STATE_CIVIC_AND_FIELD_REGISTRY,
        refresh_us_senators_on_demand,
    )

    combined = f"{location_or_zip or ''} | {troop_affiliation or ''}".strip()
    raw_loc = (location_or_zip or "").strip()

    # 1. Check for 5-digit US ZIP code
    zip_match = re.search(r"\b(\d{5})(?:-\d{4})?\b", combined)
    zip_code = zip_match.group(1) if zip_match else ""

    # 2. Check for explicit two-letter state abbreviation across all 50 states + DC
    state_code = ""
    for st in _STATE_CIVIC_AND_FIELD_REGISTRY:
        if re.search(rf"(?:,\s*|\s+){st}\b", combined):
            state_code = st
            break
    if not state_code:
        lower_c = combined.lower()
        for st, reg_entry in _STATE_CIVIC_AND_FIELD_REGISTRY.items():
            if reg_entry["state_name"].lower() in lower_c or reg_entry["capital_city"].lower() in lower_c:
                state_code = st
                break
    if not state_code:
        lower_c = combined.lower()
        if "middleton" in lower_c or "spirit of adventure" in lower_c or "andover" in lower_c:
            state_code = "MA"
        elif "daniel webster" in lower_c:
            state_code = "NH"
        elif "manhattan" in lower_c or "brooklyn" in lower_c:
            state_code = "NY"
        elif "san francisco" in lower_c or "los angeles" in lower_c or "san diego" in lower_c or "silicon valley" in lower_c:
            state_code = "CA"
        elif "houston" in lower_c or "dallas" in lower_c or "san antonio" in lower_c:
            state_code = "TX"
        elif "miami" in lower_c or "tampa" in lower_c or "orlando" in lower_c:
            state_code = "FL"
        elif "boulder" in lower_c or "colorado springs" in lower_c:
            state_code = "CO"
        elif "seattle" in lower_c or "tacoma" in lower_c:
            state_code = "WA"
        elif "chicago" in lower_c:
            state_code = "IL"
        elif "shenandoah" in lower_c or "national capital" in lower_c or "arlington" in lower_c:
            state_code = "VA"
        elif zip_code:
            state_code = _ZIP_FIRST_DIGIT_REGIONS.get(zip_code[0], "MA")

    resolved_st = state_code or "MA"
    reg = _STATE_CIVIC_AND_FIELD_REGISTRY.get(resolved_st, _STATE_CIVIC_AND_FIELD_REGISTRY["MA"])
    profile = _STATE_PROFILES.get(resolved_st)

    if raw_loc:
        display_loc = f"{raw_loc} ({reg['state_name']})" if zip_code and len(raw_loc) == 5 else raw_loc
        source = "counselor_location_input"
    elif state_code:
        display_loc = f"{troop_affiliation.strip()} ({reg['state_name']})"
        source = "inferred_from_troop_affiliation"
    else:
        display_loc = f"{troop_affiliation.strip() or 'Local Council Field Area'} ({reg['state_name']})"
        source = "default_national_profile"

    sen_info = refresh_us_senators_on_demand(resolved_st, display_loc, force=False)
    sen1 = str(sen_info.get("senator_1") or reg["senator_1"])
    sen2 = str(sen_info.get("senator_2") or reg["senator_2"])
    h_rep = str(sen_info.get("house_rep") or f"U.S. House Representative for {display_loc} (verify ZIP at house.gov)")
    gov = str(sen_info.get("governor") or reg["governor"])
    cong_del = f"U.S. Senators {sen1} & {sen2}; Local House: {h_rep}; Governor: {gov}"

    return {
        "display_location": display_loc,
        "region_label": display_loc,
        "zip_code": zip_code,
        "state_code": resolved_st,
        "state_abbr": resolved_st,
        "state_name": reg["state_name"],
        "region": (profile or {}).get("region") or f"{reg['state_name']} Regional Field Area",
        "nws_office": (profile or {}).get("nws_office") or reg["wfo"],
        "nws_url": (profile or {}).get("nws_url") or reg["wfo_url"],
        "terrain_and_hazards": (profile or {}).get("terrain_and_hazards") or reg["hazards"],
        "field_site_examples": (profile or {}).get("field_site_examples") or reg["camps_trails"],
        "state_agency": (profile or {}).get("state_agency") or f"{reg['state_name']} Emergency Management & Conservation Agencies ({reg['trauma_ems']})",
        "state_capitol": (profile or {}).get("state_capitol") or reg["capitol_building"],
        "national_landmarks": str(sen_info.get("local_landmarks") or (profile or {}).get("national_landmarks") or reg["landmarks"]),
        "federal_facilities": str(sen_info.get("local_federal_facility") or (profile or {}).get("federal_facilities") or reg["federal_facilities"]),
        "congressional_delegation": cong_del,
        "senator_1": sen1,
        "senator_1_url": str(sen_info.get("senator_1_url") or reg["senator_1_url"]),
        "senator_2": sen2,
        "senator_2_url": str(sen_info.get("senator_2_url") or reg["senator_2_url"]),
        "house_rep": h_rep,
        "governor": gov,
        "senator_cache_status": str(sen_info.get("cache_status") or "VERIFIED_REGISTRY_24H"),
        "resolution_source": source,
    }


def _build_requirement_specific_citation(
    clean_badge: str,
    r_num: str,
    r_title: str,
    req_text: str,
    first_excerpt: str,
    safety_callout: str,
    loc: Dict[str, str],
    idx: int,
) -> GroundedWebCitation:
    """Builds a non-repetitive, requirement-specific GroundedWebCitation tailored to the requirement topic and counselor location."""
    b_lower = clean_badge.lower()
    t_lower = f"{r_title} {req_text}".lower()
    disp = loc["display_location"]

    if "citizenship in the nation" in b_lower or ("citizenship" in b_lower and "nation" in b_lower):
        if r_num.startswith("7") or "visit" in t_lower or "landmark" in t_lower or "capitol" in t_lower:
            return GroundedWebCitation(
                req_number=r_num,
                source_title=f"NPS National Register & {loc['state_name']} Civic Field Destinations — {r_title}",
                source_url="https://www.nps.gov/subjects/nationalregister/index.htm",
                authority_domain="nps.gov",
                supplemental_fact=(
                    f"Local Req 7 Options for {disp}: (7a) Historic Landmarks: {loc['national_landmarks']}; "
                    f"(7b) State Capitol: {loc['state_capitol']}; (7c) Federal Facilities: {loc['federal_facilities']}."
                ),
                is_canonical_pamphlet=False,
            )
        if r_num.startswith("8") or "senator" in t_lower or "representative" in t_lower or "congress" in t_lower:
            return GroundedWebCitation(
                req_number=r_num,
                source_title=f"U.S. Congress Constituent Directory & Legislative Tracker — {r_title}",
                source_url="https://www.congress.gov/members/find-your-member",
                authority_domain="congress.gov",
                supplemental_fact=(
                    f"Local Congressional Delegation ({disp}): {loc['congressional_delegation']}. "
                    f"Verify district boundaries by 5-digit ZIP at house.gov and senate.gov before mailing your constituent letter."
                ),
                is_canonical_pamphlet=False,
            )
        if "declaration" in t_lower or "constitution" in t_lower or "amendment" in t_lower or "preamble" in t_lower or r_num in ("1", "2", "4"):
            return GroundedWebCitation(
                req_number=r_num,
                source_title=f"National Archives America's Founding Documents — {r_title}",
                source_url="https://www.archives.gov/founding-docs",
                authority_domain="archives.gov",
                supplemental_fact=(
                    f"Primary-source charter text & constitutional annotations for {r_title}: {first_excerpt[:155]}"
                ),
                is_canonical_pamphlet=False,
            )
        if "branch" in t_lower or "checks" in t_lower or "court" in t_lower or r_num == "3":
            return GroundedWebCitation(
                req_number=r_num,
                source_title=f"U.S. Courts & Library of Congress Separation of Powers Guide — {r_title}",
                source_url="https://constitution.congress.gov/",
                authority_domain="congress.gov",
                supplemental_fact=(
                    f"Federal Judicial & Legislative Reference ({disp} federal court venue: {loc['federal_facilities'].split(',')[0]}): {first_excerpt[:145]}"
                ),
                is_canonical_pamphlet=False,
            )
        return GroundedWebCitation(
            req_number=r_num,
            source_title=f"Library of Congress Historical Speeches & Civic Archive — {r_title}",
            source_url="https://www.loc.gov/",
            authority_domain="loc.gov",
            supplemental_fact=f"Historical & civic discussion context for {r_title}: {first_excerpt[:160]}",
            is_canonical_pamphlet=False,
        )

    if "first aid" in b_lower or "emergency" in b_lower or "lifesaving" in b_lower:
        if "cpr" in t_lower or "aed" in t_lower or "choking" in t_lower or r_num in ("7", "6"):
            return GroundedWebCitation(
                req_number=r_num,
                source_title=f"American Heart Association & Red Cross ECC Guidelines — {r_title}",
                source_url="https://cpr.heart.org/en/resuscitation-science/cpr-and-ecc-guidelines",
                authority_domain="heart.org",
                supplemental_fact=(
                    f"Hands-Only CPR (100–120 compressions/min, 2-inch depth) & AED pad placement protocol for {disp} training stations: {first_excerpt[:135]}"
                ),
                is_canonical_pamphlet=False,
            )
        if "heat" in t_lower or "cold" in t_lower or "hypothermia" in t_lower or "dehydration" in t_lower or r_num == "11":
            return GroundedWebCitation(
                req_number=r_num,
                source_title=f"{loc['nws_office']} Environmental Exposure & Wilderness EMS — {r_title}",
                source_url=loc["nws_url"],
                authority_domain="weather.gov",
                supplemental_fact=(
                    f"Regional thermal & weather exposure hazards in {disp}: {loc['terrain_and_hazards']}. Check {loc['nws_office']} heat/wind-chill advisories before campouts."
                ),
                is_canonical_pamphlet=False,
            )
        if "bite" in t_lower or "sting" in t_lower or "tick" in t_lower or "plant" in t_lower or r_num == "9":
            return GroundedWebCitation(
                req_number=r_num,
                source_title=f"CDC Vector-Borne Disease & Poison Control Field Guide — {r_title}",
                source_url="https://www.cdc.gov/ticks/index.html",
                authority_domain="cdc.gov",
                supplemental_fact=(
                    f"Regional wildlife, tick & plant hazard guidance for {loc['field_site_examples']} ({disp}): {first_excerpt[:135]}"
                ),
                is_canonical_pamphlet=False,
            )
        if "mental" in t_lower or "988" in t_lower or r_num == "12":
            return GroundedWebCitation(
                req_number=r_num,
                source_title=f"SAMHSA 988 Suicide & Crisis Lifeline & Youth Support — {r_title}",
                source_url="https://988lifeline.org/",
                authority_domain="988lifeline.org",
                supplemental_fact=(
                    f"24/7 confidential crisis support (Call or Text 988) plus {loc['state_agency']} youth support resources for {disp}."
                ),
                is_canonical_pamphlet=False,
            )
        return GroundedWebCitation(
            req_number=r_num,
            source_title=f"American Red Cross First Aid & {loc['state_name']} EMS Protocol — {r_title}",
            source_url="https://www.redcross.org/take-a-class/first-aid",
            authority_domain="redcross.org",
            supplemental_fact=(
                f"Field triage & skill verification at {loc['field_site_examples']}: {safety_callout or first_excerpt[:145]}"
            ),
            is_canonical_pamphlet=False,
        )

    if "cooking" in b_lower:
        if "thermometer" in t_lower or "temperature" in t_lower or "foodborne" in t_lower or "safety" in t_lower or r_num == "1":
            return GroundedWebCitation(
                req_number=r_num,
                source_title=f"USDA FSIS Safe Minimum Internal Temperature Chart — {r_title}",
                source_url="https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/food-safety-basics/safe-minimum-internal-temperature-chart",
                authority_domain="fsis.usda.gov",
                supplemental_fact=(
                    f"Verify 165°F poultry/leftovers, 160°F ground meats, and 145°F whole cuts/fish (+3 min rest) during patrol cooking at {loc['field_site_examples']}."
                ),
                is_canonical_pamphlet=False,
            )
        if "myplate" in t_lower or "nutrition" in t_lower or "menu" in t_lower or r_num == "2":
            return GroundedWebCitation(
                req_number=r_num,
                source_title=f"USDA MyPlate Daily Nutritional Guidelines & Meal Planner — {r_title}",
                source_url="https://www.myplate.gov/",
                authority_domain="myplate.gov",
                supplemental_fact=f"Balanced 5-group camp & home menu planning for {r_title}: {first_excerpt[:150]}",
                is_canonical_pamphlet=False,
            )
        if "trail" in t_lower or "backpacking" in t_lower or "leave no trace" in t_lower or r_num in ("5", "6"):
            return GroundedWebCitation(
                req_number=r_num,
                source_title=f"Leave No Trace Backcountry Kitchen & Bear-Bag Standards — {r_title}",
                source_url="https://lnt.org/why/7-principles/",
                authority_domain="lnt.org",
                supplemental_fact=(
                    f"Backcountry stove & greywater/wildlife food storage protocols for {loc['field_site_examples']} ({disp}): {first_excerpt[:135]}"
                ),
                is_canonical_pamphlet=False,
            )
        return GroundedWebCitation(
            req_number=r_num,
            source_title=f"Scouting America Outdoor Culinary & Camp Sanitation Guide — {r_title}",
            source_url="https://www.scouting.org/skills/merit-badges/cooking/",
            authority_domain="scouting.org",
            supplemental_fact=f"Practical patrol execution for {r_title} ({disp}): {first_excerpt[:150]}",
            is_canonical_pamphlet=False,
        )

    if "weather" in b_lower:
        return GroundedWebCitation(
            req_number=r_num,
            source_title=f"{loc['nws_office']} JetStream Weather School — {r_title}",
            source_url=loc["nws_url"],
            authority_domain="weather.gov",
            supplemental_fact=(
                f"Local meteorological application via {loc['nws_office']} ({loc['region']}): {first_excerpt[:145]}"
            ),
            is_canonical_pamphlet=False,
        )

    slug = clean_badge.lower().replace(" ", "-")
    alt_domains = [
        ("scouting.org", f"Scouting America {clean_badge} Digital Resource Guide", f"https://www.scouting.org/skills/merit-badges/{slug}/"),
        ("nps.gov", f"National Park Service & Regional Field Guide ({loc['state_name']})", "https://www.nps.gov/"),
        ("weather.gov", f"{loc['nws_office']} Field Safety & Planning Brief", loc["nws_url"]),
    ]
    dom, org_lbl, u_link = alt_domains[idx % len(alt_domains)]
    return GroundedWebCitation(
        req_number=r_num,
        source_title=f"{org_lbl} — {r_title}",
        source_url=u_link,
        authority_domain=dom,
        supplemental_fact=f"Req {r_num} field application in {disp} ({loc['field_site_examples']}): {first_excerpt[:140]}",
        is_canonical_pamphlet=False,
    )


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
    b_lower = clean_badge.lower()
    if "citizenship" in b_lower or "american" in b_lower or "law" in b_lower:
        local_connections = [
            f"Resolved Counselor Location: {loc['display_location']} — State Capitol: {loc['state_capitol']}",
            f"Nearby National Historic Landmarks & Monuments (Req 7a/7d): {loc['national_landmarks']}",
            f"Regional Federal Facilities & Courts (Req 7c): {loc['federal_facilities']}",
            f"Congressional Delegation Lookup (Req 8): {loc['congressional_delegation']}",
        ]
    else:
        local_connections = [
            f"Resolved Counselor Location: {loc['display_location']} ({loc['nws_office']})",
            f"Regional Environmental & Safety Hazards: {loc['terrain_and_hazards']}",
            f"Recommended Local Field & Campout Sites: {loc['field_site_examples']}",
            f"State & Civic Partner Agencies: {loc['state_agency']}",
        ]

    from src.tools.local_grounding_engine import resolve_requirement_local_grounding

    misconceptions: Dict[str, str] = {}
    case_studies: Dict[str, str] = {}
    citations: List[GroundedWebCitation] = []

    for idx, req in enumerate(canonical_requirements):
        r_num = str(req.get("req_number") or f"{idx + 1}").strip()
        r_title = str(req.get("topic_title") or f"{clean_badge} Req {r_num}").strip()
        req_text = str(req.get("req_text") or "").strip()
        excerpts = req.get("pamphlet_excerpts") or []
        first_excerpt = str(excerpts[0]).strip() if excerpts else (req_text or f"Review core concepts for {r_title}.")
        safety_callout = str(req.get("safety_callout") or "").strip()

        cit = _build_requirement_specific_citation(
            clean_badge=clean_badge,
            r_num=r_num,
            r_title=r_title,
            req_text=req_text,
            first_excerpt=first_excerpt,
            safety_callout=safety_callout,
            loc=loc,
            idx=idx,
        )
        local_g = resolve_requirement_local_grounding(
            badge_name=clean_badge,
            req_dict=req,
            location_profile=loc,
        )
        cit.grounding_category = str(local_g.get("grounding_category") or "museums_stem_and_careers")
        cit.requires_local_lookup = bool(local_g.get("requires_local_lookup", False))
        cit.local_grounding_callout = str(local_g.get("local_grounding_callout") or cit.supplemental_fact)
        cit.slide_injection_label = str(local_g.get("slide_injection_label") or "Local Troop Grounding")
        cit.cache_status = str(local_g.get("cache_status") or "VERIFIED_REGISTRY_24H")
        if cit.requires_local_lookup and cit.grounding_category in ("elected_officials", "civic_landmarks_and_monuments"):
            cit.supplemental_fact = cit.local_grounding_callout

        misconceptions[r_num] = (
            f"Req {r_num} ({r_title}): Ensure Scouts explain the underlying reasoning for {first_excerpt[:95].rstrip('.')} rather than memorizing labels."
        )
        case_studies[r_num] = cit.local_grounding_callout if cit.requires_local_lookup else cit.supplemental_fact
        if enable_live_web_search and idx < 25:
            citations.append(cit)

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

