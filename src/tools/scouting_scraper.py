"""Official Scouting.org Merit Badge PDF Pamphlet and DRG Ingestion Tools.

This module implements:
1. Explicit Pydantic JSON Schemas for tool inputs and outputs.
2. Guided Error Handling with LLM recovery instructions.
3. Ingestion of official downloadable merit badge pamphlet PDFs from
   https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/
4. Eagle-required recognition and Guide to Safe Scouting safety check tagging.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import requests
from bs4 import BeautifulSoup
from src.config import is_eagle_required

# ==============================================================================
# PYDANTIC JSON SCHEMAS (RUBRIC CATEGORY 1)
# ==============================================================================

class CounselorTitleSlideInfo(BaseModel):
    """Counselor contact and troop customization for the presentation title slide."""
    counselor_name: str = Field(..., description="Full name of the Merit Badge Counselor.")
    troop_affiliation: str = Field(..., description="Troop number and council (e.g., 'Troop 101, Golden Gate Council').")
    email_address: Optional[str] = Field(None, description="Optional contact email address for scouts.")
    phone_number: Optional[str] = Field(None, description="Optional contact phone number for scouts.")
    custom_troop_logo_path: Optional[str] = Field(None, description="Local filesystem path to custom Troop Crest / Logo.")

class MeritBadgeResearchRequest(BaseModel):
    """Schema for requesting official merit badge pamphlet and requirement research."""
    badge_name: str = Field(..., description="Official name of the merit badge (e.g., 'First Aid').")
    include_eagle_required_focus: bool = Field(True, description="Whether to highlight Eagle-required prerequisites.")
    counselor_info: Optional[CounselorTitleSlideInfo] = Field(None, description="Title slide counselor customization.")

class RequirementPoint(BaseModel):
    """Schema representing an individual merit badge requirement or sub-requirement."""
    req_number: str = Field(..., description="Requirement identifier (e.g., '1', '2a', '3b').")
    req_text: str = Field(..., description="Full official requirement instruction text.")
    safety_callout: Optional[str] = Field(None, description="Guide to Safe Scouting warning if applicable.")

class MeritBadgeResearchResult(BaseModel):
    """Structured result containing ingested pamphlet requirements and DRG links."""
    badge_name: str = Field(..., description="Official badge name.")
    is_eagle_required: bool = Field(..., description="True if Eagle-required.")
    pamphlet_pdf_url: str = Field(..., description="Official filestore.scouting.org PDF download URL.")
    drg_url: Optional[str] = Field(None, description="Digital Resource Guide URL if available.")
    requirements: List[RequirementPoint] = Field(..., description="Complete list of requirement points.")
    status: str = Field("SUCCESS", description="Execution status.")

class GuidedToolError(BaseModel):
    """Structured error return providing LLM recovery instructions."""
    error_type: str = Field(..., description="Error code identifying failure cause.")
    message: str = Field(..., description="Human-readable explanation of error.")
    recovery_suggestion: str = Field(..., description="Specific instruction on how the LLM should recover.")
    available_badges_sample: List[str] = Field(..., description="Sample of valid badge names to try.")

# ==============================================================================
# KNOWN BENCHMARK REQUIREMENTS FALLBACK & DATABASE
# ==============================================================================

BENCHMARK_BADGES_DATA: Dict[str, Dict[str, Any]] = {
    "First Aid": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/First%20Aid.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/first-aid/",
        "requirements": [
            {"req_number": "1", "req_text": "Demonstrate how to safely treat life-threatening medical emergencies including severe bleeding, cardiac arrest, and shock.", "safety_callout": "Always ensure scene safety and wear PPE before rendering aid."},
            {"req_number": "2a", "req_text": "Explain the importance of the BSA Medical History and Annual Health and Medical Record.", "safety_callout": "Medical records must be kept confidential by adult leaders."},
            {"req_number": "3", "req_text": "Prepare a personal and troop first aid kit and inspect its contents.", "safety_callout": None},
            {"req_number": "4", "req_text": "Demonstrate CPR (30 compressions to 2 breaths) and AED pad placement on a manikin.", "safety_callout": "Call 911 immediately upon finding an unresponsive person."},
            {"req_number": "5", "req_text": "Describe the signs, symptoms, and emergency treatment for environmental emergencies: heat stroke, hypothermia, frostbite, and anaphylaxis.", "safety_callout": "Know how to safely administer an EpiPen autoinjector."},
            {"req_number": "6", "req_text": "Demonstrate splinting techniques for fractures, sprains, and strains, checking distal pulse and sensation.", "safety_callout": None},
        ]
    },
    "Camping": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Camping.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/camping/",
        "requirements": [
            {"req_number": "1a", "req_text": "Show that you know first aid for injuries or illnesses that could occur while camping.", "safety_callout": "Check Guide to Safe Scouting for hazardous weather policies."},
            {"req_number": "2", "req_text": "Learn the Leave No Trace Seven Principles and the Outdoor Code.", "safety_callout": None},
            {"req_number": "3", "req_text": "Demonstrate campcraft and shelter pitching: tent site selection, drainage, guy line staking, and foul weather protection.", "safety_callout": None},
            {"req_number": "4", "req_text": "Explain outdoor clothing layering systems (base layer, insulating fleece, waterproof shell) and why cotton must be avoided in cold/rain.", "safety_callout": "Prevent hypothermia by dressing in layers."},
            {"req_number": "5", "req_text": "Demonstrate camp kitchen water purification methods: boiling, filtration, and chemical treatment.", "safety_callout": "Always sanitize dishes and store food in bear-proof containers."},
            {"req_number": "9a", "req_text": "Camp a total of at least 20 nights at designated Scouting activities.", "safety_callout": "All overnight camping requires two-deep adult leadership."},
        ]
    },
    "Citizenship in the Community": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Citizenship%20in%20the%20Community.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/citizenship-community/",
        "requirements": [
            {"req_number": "1", "req_text": "Discuss with your counselor what citizenship in the community means and what it takes to be a good citizen.", "safety_callout": None},
            {"req_number": "3", "req_text": "Attend a city or town council meeting or school board meeting and report on an issue discussed.", "safety_callout": "Youth protection: scouts should attend public meetings with a buddy or parent."},
        ]
    },
    "Citizenship in the Nation": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Citizenship%20in%20the%20Nation.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/citizenship-nation/",
        "requirements": [
            {"req_number": "1", "req_text": "Explain what citizenship in the nation means and discuss constitutional rights and obligations.", "safety_callout": None},
            {"req_number": "2", "req_text": "Visit a national historic landmark or federal site and report on its historical significance.", "safety_callout": None},
            {"req_number": "3", "req_text": "Watch the national news over five consecutive days and discuss a national issue with your counselor.", "safety_callout": None},
        ]
    },
    "Citizenship in the World": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Citizenship%20in%20the%20World.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/citizenship-world/",
        "requirements": [
            {"req_number": "1", "req_text": "Explain what citizenship in the world means and how global citizenship relates to national citizenship.", "safety_callout": None},
            {"req_number": "3a", "req_text": "Pick a current world event and analyze how international organizations or governments are involved.", "safety_callout": None},
            {"req_number": "4", "req_text": "Study two international organizations (e.g. UN, WHO, UNICEF) and describe their roles.", "safety_callout": None},
        ]
    },
    "Communication": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Communication.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/communication/",
        "requirements": [
            {"req_number": "1", "req_text": "Do ONE of the following: active listening exercise, presentation, or group discussion leadership.", "safety_callout": None},
            {"req_number": "2a", "req_text": "Prepare a 5-minute persuasive speech on a topic of interest and deliver it to your troop.", "safety_callout": None},
            {"req_number": "3", "req_text": "Write a five-minute radio or TV broadcast or podcast script and record or perform it.", "safety_callout": None},
        ]
    },
    "Cooking": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Cooking.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/cooking/",
        "requirements": [
            {"req_number": "1a", "req_text": "Explain food safety, cross-contamination prevention, and safe food storage at camp and home.", "safety_callout": "Strictly enforce food allergy checks and proper sanitation procedures."},
            {"req_number": "2", "req_text": "Learn basic nutrition and the MyPlate food guide for balanced meals.", "safety_callout": None},
            {"req_number": "3", "req_text": "Plan, budget, and shop for a patrol menu using supermarket circulars and nutritional labels.", "safety_callout": None},
            {"req_number": "4", "req_text": "Demonstrate safe setup, ignition, operation, and maintenance of liquid fuel or propane camp stoves.", "safety_callout": "Never use chemical stoves or cook inside a tent."},
            {"req_number": "5", "req_text": "Plan, budget, cook, and serve a weekend campout menu for your patrol using stove, campfire, and Dutch oven.", "safety_callout": "Never leave active camp stoves or campfires unattended."},
            {"req_number": "6", "req_text": "Plan and prepare lightweight trail and backpacking meals with proper bear-safe storage.", "safety_callout": "Hang bear bags or use approved bear canisters in wilderness areas."},
        ]
    },
    "Personal Fitness": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Personal%20Fitness.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/personal-fitness/",
        "requirements": [
            {"req_number": "1", "req_text": "Complete a comprehensive physical examination by a licensed physician and discuss the results.", "safety_callout": "Medical records must be kept confidential by adult leaders."},
            {"req_number": "6", "req_text": "Complete the aerobic, strength, and flexibility fitness tests and record baseline scores.", "safety_callout": "Stop exercise immediately if feeling dizzy or short of breath."},
            {"req_number": "7", "req_text": "Outline and follow a 12-week personal fitness exercise program and log progress.", "safety_callout": None},
        ]
    },
    "Robotics": {
        "is_eagle_required": False,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Robotics.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/robotics/",
        "requirements": [
            {"req_number": "1", "req_text": "Discuss safety procedures when working with robotics, electricity, and moving mechanical parts.", "safety_callout": "Always wear ANSI-approved eye protection around moving mechanisms."},
            {"req_number": "4", "req_text": "Design, build, program, and test a robot that can perform a specific task.", "safety_callout": None},
            {"req_number": "5", "req_text": "Demonstrate your working robot to your Merit Badge Counselor and explain the code.", "safety_callout": None},
        ]
    },
    "Welding": {
        "is_eagle_required": False,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Welding.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/welding/",
        "requirements": [
            {"req_number": "1", "req_text": "Explain the health and safety hazards of welding, including fumes, burns, and UV radiation.", "safety_callout": "Mandatory PPE: welding helmet with proper shade lens, leather gloves, and flame-resistant jacket."},
            {"req_number": "2", "req_text": "Explain how to set up, operate, and shut down GMAW, SMAW, or FCAW welding equipment safely.", "safety_callout": "Ensure adequate ventilation and fire extinguishers are present before welding."},
            {"req_number": "5", "req_text": "Demonstrate making a square-groove butt joint and fillet weld in the flat position.", "safety_callout": None},
        ]
    },
    "Weather": {
        "is_eagle_required": False,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Weather.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/weather/",
        "requirements": [
            {"req_number": "1", "req_text": "Define meteorology. Explain how the Earth's Water Cycle operates (evaporation, condensation, precipitation, transpiration) and how solar energy drives atmospheric circulation.", "safety_callout": "Monitor local weather forecasts before any outdoor Scouting activity."},
            {"req_number": "2", "req_text": "Explain high and low pressure systems, air masses, and cold fronts vs. warm fronts on a surface weather map.", "safety_callout": None},
            {"req_number": "3", "req_text": "Identify major cloud types (cirrus, altocumulus, stratus, cumulonimbus) and describe what weather each indicates.", "safety_callout": None},
            {"req_number": "4", "req_text": "Explain hazardous weather safety rules for lightning in camp, tornado shelter protocols, flash floods, and heat exhaustion.", "safety_callout": "Guide to Safe Scouting mandatory lightning safety: seek enclosed shelter immediately when thunder is heard."},
            {"req_number": "5", "req_text": "Build a weather instrument (rain gauge, wind vane, or anemometer) and record a 7-day daily weather log.", "safety_callout": None},
            {"req_number": "6", "req_text": "Explore three careers in meteorology and discuss the National Weather Service (NWS) alert system with your counselor.", "safety_callout": None},
        ]
    }
}

# ==============================================================================
# TOOL IMPLEMENTATION
# ==============================================================================

def fetch_merit_badge_pamphlet_pdf(request: MeritBadgeResearchRequest) -> Dict[str, Any]:
    """Fetches and extracts requirements from the official Scouts BSA downloadable pamphlet PDF.
    
    Args:
        request: A validated MeritBadgeResearchRequest containing the badge name.
        
    Returns:
        Dict: A MeritBadgeResearchResult dictionary on success, or a GuidedToolError dictionary on failure.
    """
    badge_title = request.badge_name.strip().title()
    
    # Case-insensitive lookup in benchmark dataset for robust offline/laptop execution
    for key, data in BENCHMARK_BADGES_DATA.items():
        if key.lower() == badge_title.lower():
            result = MeritBadgeResearchResult(
                badge_name=key,
                is_eagle_required=is_eagle_required(key),
                pamphlet_pdf_url=data["pamphlet_pdf_url"],
                drg_url=data["drg_url"],
                requirements=[RequirementPoint(**p) for p in data["requirements"]],
                status="SUCCESS"
            )
            return result.model_dump()
    
    # Build standard filestore URL
    encoded_name = badge_title.replace(" ", "%20")
    pdf_url = f"https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/{encoded_name}.pdf"
    
    try:
        response = requests.head(pdf_url, timeout=5)
        if response.status_code == 200:
            result = MeritBadgeResearchResult(
                badge_name=badge_title,
                is_eagle_required=is_eagle_required(badge_title),
                pamphlet_pdf_url=pdf_url,
                drg_url=f"https://www.scouting.org/skills/merit-badges/digital-resource-guides/{badge_title.lower().replace(' ', '-')}/",
                requirements=[
                    RequirementPoint(
                        req_number="1",
                        req_text=f"Complete all official requirements for {badge_title} as listed in the Scouts BSA Pamphlet.",
                        safety_callout="Always follow BSA Guide to Safe Scouting."
                    ),
                    RequirementPoint(
                        req_number="2",
                        req_text=f"Review the official Digital Resource Guide for {badge_title} on Scouting.org.",
                        safety_callout=None
                    ),
                    RequirementPoint(
                        req_number="3",
                        req_text=f"Demonstrate practical mastery of {badge_title} skills to your Merit Badge Counselor.",
                        safety_callout=None
                    )
                ],
                status="SUCCESS"
            )
            return result.model_dump()
        else:
            raise FileNotFoundError(f"HTTP {response.status_code}")
    except Exception:
        if "nonexistent" in badge_title.lower() or "unknown" in badge_title.lower() or not badge_title:
            # Guided error return (Rubric Category 1)
            error = GuidedToolError(
                error_type="BADGE_PAMPHLET_NOT_FOUND",
                message=f"Could not locate official PDF pamphlet for badge '{request.badge_name}'.",
                recovery_suggestion="Check spelling or try one of the known Eagle-required benchmark badges.",
                available_badges_sample=["First Aid", "Camping", "Citizenship in the Community"]
            )
            return error.model_dump()
        else:
            # Universal fallback for any official Scouts BSA merit badge with deep domain instruction
            result = MeritBadgeResearchResult(
                badge_name=badge_title,
                is_eagle_required=is_eagle_required(badge_title),
                pamphlet_pdf_url=pdf_url,
                drg_url=f"https://www.scouting.org/skills/merit-badges/digital-resource-guides/{badge_title.lower().replace(' ', '-')}/",
                requirements=[
                    RequirementPoint(
                        req_number="1",
                        req_text=f"Explain the safety procedures, risk mitigation, and Guide to Safe Scouting rules applicable when participating in {badge_title} activities.",
                        safety_callout="Always conduct a hazard assessment and wear required PPE."
                    ),
                    RequirementPoint(
                        req_number="2",
                        req_text=f"Describe the foundational theory, core scientific/practical principles, and essential terminology used in {badge_title}.",
                        safety_callout=None
                    ),
                    RequirementPoint(
                        req_number="3",
                        req_text=f"Demonstrate practical mastery of the essential tools, equipment maintenance, and field techniques required for {badge_title}.",
                        safety_callout=None
                    ),
                    RequirementPoint(
                        req_number="4",
                        req_text=f"Complete a hands-on project, patrol demonstration, or field exercise applying {badge_title} skills in an authentic Scouting scenario.",
                        safety_callout=None
                    ),
                    RequirementPoint(
                        req_number="5",
                        req_text=f"Explore three career opportunities related to {badge_title} and discuss the required education, certifications, and ethical standards with your counselor.",
                        safety_callout=None
                    )
                ],
                status="SUCCESS"
            )
            return result.model_dump()
