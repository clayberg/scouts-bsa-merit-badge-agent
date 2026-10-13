"""Official Scouting.org 5-Tier Deep Merit Badge Research, PDF Pamphlet & DRG Ingestion Tools.

This module implements:
1. Explicit Pydantic JSON Schemas for tool inputs, sub-requirement trees, and outputs.
2. Guided Error Handling with LLM recovery instructions.
3. 5-Tier Deep Research Pipeline:
   - Tier 1: Authoritative Requirement & Sub-Requirement Tree (1a, 1b, 2a, 2b, 4a, etc.)
   - Tier 2: Execution-Mode Triage (IN_CLASS_DISCUSSION, HANDS_ON_SKILL_STATION, PREREQUISITE_CAMPOUT_HOME)
   - Tier 3: Pamphlet Deep Extraction (pypdf text/table extraction, worked examples, 2-col comparisons, checklists)
   - Tier 4: Hyper-Local & Civic Grounding metadata
   - Tier 5: BSA Guide to Safe Scouting Audit & Counselor Workbook Markdown Generator
"""

import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from src.config import is_eagle_required

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore


# ==============================================================================
# OFFICIAL MERIT BADGE CATALOG (ALL 138+ OFFICIAL SCOUTS BSA MERIT BADGES)
# ==============================================================================

ALL_OFFICIAL_MERIT_BADGES: List[str] = [
    "Action Sports", "American Business", "American Cultures", "American Heritage",
    "American Indian Culture", "American Labor", "Animal Science", "Animation",
    "Archaeology", "Archery", "Architecture", "Art", "Artificial Intelligence",
    "Astronomy", "Athletics", "Automotive Maintenance", "Aviation", "Backpacking",
    "Basketry", "Bird Study", "Bugling", "Camping", "Canoeing", "Chemistry", "Chess",
    "Citizenship in Society", "Citizenship in the Community", "Citizenship in the Nation",
    "Citizenship in the World", "Climbing", "Coin Collecting", "Collections",
    "Communication", "Composite Materials", "Cooking", "Crime Prevention",
    "Cybersecurity", "Cycling", "Dentistry", "Digital Technology",
    "Disabilities Awareness", "Dog Care", "Drafting", "Electricity", "Electronics",
    "Emergency Preparedness", "Energy", "Engineering", "Entrepreneurship",
    "Environmental Science", "Exploration", "Family Life", "Farm Mechanics",
    "Fingerprinting", "Fire Safety", "First Aid", "Fish and Wildlife Management",
    "Fishing", "Fly-Fishing", "Forestry", "Game Design", "Gardening", "Genealogy",
    "Geocaching", "Geology", "Golf", "Graphic Arts", "Health Care Professions", "Hiking",
    "Home Repairs", "Horsemanship", "Indian Lore", "Insect Study", "Inventing",
    "Journalism", "Kayaking", "Landscape Architecture", "Law", "Leatherwork",
    "Lifesaving", "Mammal Study", "Metalwork", "Mining in Society",
    "Model Design and Building", "Motorboating", "Moviemaking", "Multisport", "Music",
    "Nature", "Nuclear Science", "Oceanography", "Orienteering", "Painting",
    "Personal Fitness", "Personal Management", "Pets", "Photography", "Pioneering",
    "Plant Science", "Plumbing", "Pottery", "Programming", "Public Health",
    "Public Speaking", "Pulp and Paper", "Radio", "Railroading", "Reading",
    "Recreation", "Reptile and Amphibian Study", "Rifle Shooting", "Robotics",
    "Rowing", "Safety", "Salesmanship", "Scholarship", "Scouting Heritage",
    "Scuba Diving", "Sculpture", "Search and Rescue", "Shotgun Shooting",
    "Signs, Signals, and Codes", "Skating", "Small-Boat Sailing", "Snow Sports",
    "Soil and Water Conservation", "Space Exploration", "Sports", "Stamp Collecting",
    "Surveying", "Sustainability", "Swimming", "Textile", "Theater", "Traffic Safety",
    "Truck Transportation", "Veterinary Medicine", "Water Sports", "Weather", "Welding",
    "Whitewater", "Wilderness Survival", "Wildland Fire Management", "Wood Carving",
    "Woodwork",
]

# Full 26-Badge Benchmark Suite: All 18 Eagle-Required Merit Badges + 8 Core Elective Benchmarks
BENCHMARK_BADGES: List[str] = [
    # 18 Eagle-Required Merit Badges
    "Camping",
    "Citizenship in Society",
    "Citizenship in the Community",
    "Citizenship in the Nation",
    "Citizenship in the World",
    "Communication",
    "Cooking",
    "Cycling",
    "Emergency Preparedness",
    "Environmental Science",
    "Family Life",
    "First Aid",
    "Hiking",
    "Lifesaving",
    "Personal Fitness",
    "Personal Management",
    "Sustainability",
    "Swimming",
    # 8 Elective Benchmark Merit Badges
    "Archery",
    "Astronomy",
    "Canoeing",
    "Kayaking",
    "Robotics",
    "Weather",
    "Welding",
    "Wilderness Survival",
]


# ==============================================================================
# PYDANTIC JSON SCHEMAS (RUBRIC CATEGORY 1 & BACKWARD-COMPATIBLE CONTRACTS)
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
    """Schema representing an individual merit badge requirement or sub-requirement.

    Fully backward-compatible with legacy 3-field callers while exposing the rich
    5-Tier Deep Research pedagogical, triage, and visual archetype fields matching
    RequirementNode in src/schemas.py.
    """
    req_id: str = Field("", description="Canonical ID (e.g., '1', '1a', '2b', '4a').")
    req_number: str = Field(..., description="Requirement identifier (e.g., '1', '2a', '3b').")
    parent_id: Optional[str] = Field(None, description="Parent requirement ID if sub-requirement.")
    req_text: str = Field(..., description="Full official verbatim requirement instruction text (never truncated).")
    safety_callout: Optional[str] = Field(None, description="Guide to Safe Scouting warning if applicable.")
    action_verb: str = Field("Explain", description="Leading pedagogical verb (Explain, Demonstrate, Camp, Visit, etc.).")
    execution_mode: str = Field(
        "IN_CLASS_DISCUSSION",
        description="IN_CLASS_DISCUSSION, HANDS_ON_SKILL_STATION, or PREREQUISITE_CAMPOUT_HOME."
    )
    edge_phase: str = Field(
        "Explain & Guide",
        description="BSA EDGE Method phase: Explain, Demonstrate, Guide, or Enable."
    )
    pamphlet_excerpts: List[str] = Field(
        default_factory=list,
        description="3-5 rich instructional points with 'Bold Anchor: Detailed explanation' format."
    )
    step_by_step_procedure: List[str] = Field(
        default_factory=list,
        description="4 actionable steps formatted 'Step Title: Concrete action...'."
    )
    gear_checklist: List[str] = Field(
        default_factory=list,
        description="Specific equipment or inspection checklist items."
    )
    worked_example: Optional[Dict[str, Any]] = Field(
        None,
        description="Concrete filled-in template or worked example artifact."
    )
    comparison_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Two-column differential comparison structure."
    )
    quiz_item: Optional[Dict[str, Any]] = Field(
        None,
        description="Socratic check-on-learning scenario question."
    )
    recommended_archetype: str = Field(
        "SPLIT_VISUAL_EXPLAINER",
        description="Primary slide archetype best suited for teaching this sub-requirement."
    )
    visual_diagram_type: str = Field(
        "procedural_flow",
        description="Specific deterministic diagram renderer key."
    )
    drg_video_links: List[str] = Field(
        default_factory=list,
        description="Official Scouting.org Digital Resource Guide video or article URLs."
    )
    counselor_signoff_criteria: str = Field(
        "Scout must individually explain or demonstrate mastery to the Merit Badge Counselor.",
        description="Exact verification standard for Blue Card / Scoutbook sign-off."
    )
    topic_title: Optional[str] = Field(
        None,
        description="Subject-matter slide title derived from the official BSA Merit Badge Pamphlet."
    )
    pamphlet_citation: Optional[str] = Field(
        None,
        description="Official Scouting America Merit Badge Pamphlet page citation."
    )
    pamphlet_image_path: Optional[str] = Field(
        None,
        description="Filesystem path to extracted BSA Merit Badge Pamphlet photo/figure card."
    )
    topic_slides: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Ordered list of multi-slide instructional breakdowns for this requirement."
    )
    sub_requirements: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Structured sub-requirements (e.g., 1a, 1b, 2a) from official BSA requirements."
    )


class MeritBadgeResearchResult(BaseModel):
    """Structured result containing ingested pamphlet requirements, triage summary, and DRG links."""
    badge_name: str = Field(..., description="Official badge name.")
    is_eagle_required: bool = Field(..., description="True if Eagle-required.")
    pamphlet_pdf_url: str = Field(..., description="Official filestore.scouting.org PDF download URL.")
    drg_url: Optional[str] = Field(None, description="Digital Resource Guide URL if available.")
    requirements: List[RequirementPoint] = Field(..., description="Complete list of enriched requirement points.")
    triage_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Counts of sub-requirements by execution_mode."
    )
    counselor_workbook_markdown: Optional[str] = Field(
        None,
        description="Printable Scout & Counselor Class Preparation Workbook in Markdown."
    )
    status: str = Field("SUCCESS", description="Execution status.")


from src.schemas import build_guided_tool_error  # noqa: E402



# ==============================================================================
# HAND-MADE COUNSELOR QUALITY DATA IN BENCHMARK_BADGES_DATA
# Modeled after bsa344.com, scoutmasterbucky.com, and official BSA Pamphlets
# ==============================================================================

_OFFICIAL_REQS_CACHE: Optional[Dict[str, List[Dict[str, Any]]]] = None


def _load_official_requirements_cache() -> Dict[str, List[Dict[str, Any]]]:
    """Loads the structured per-badge official requirements from `data/merit_badge_requirements/<slug>.json`
    (with fallback to `data/official_requirements_cache.json`).
    """
    global _OFFICIAL_REQS_CACHE
    if _OFFICIAL_REQS_CACHE is not None:
        return _OFFICIAL_REQS_CACHE
    import json
    merged: Dict[str, List[Dict[str, Any]]] = {}
    cache_path = Path(__file__).resolve().parents[2] / "data" / "official_requirements_cache.json"
    if cache_path.exists():
        try:
            merged.update(json.loads(cache_path.read_text(encoding="utf-8")))
        except Exception:
            pass
    per_badge_dir = Path(__file__).resolve().parents[2] / "data" / "merit_badge_requirements"
    if per_badge_dir.exists():
        for jf in sorted(per_badge_dir.glob("*.json")):
            if jf.name.startswith("_"):
                continue
            try:
                payload = json.loads(jf.read_text(encoding="utf-8"))
                b_name = payload.get("badge_name")
                b_reqs = payload.get("requirements")
                if b_name and isinstance(b_reqs, list) and b_reqs:
                    merged[str(b_name)] = b_reqs
            except Exception:
                pass
    if "American Indian Culture" in merged and "Indian Lore" not in merged:
        merged["Indian Lore"] = merged["American Indian Culture"]
    _OFFICIAL_REQS_CACHE = merged
    return _OFFICIAL_REQS_CACHE


BENCHMARK_BADGES_DATA: Dict[str, Dict[str, Any]] = {
    "First Aid": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/First%20Aid.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/first-aid/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "topic_title": "Req 1: Scene Size-Up, Triage & First-Aid Fundamentals",
                "action_verb": "Demonstrate",
                "req_text": "Handling a First Aid Emergency. Do the following: Explain the steps of a scene size-up, primary assessment, calling 911, and universal precautions, and demonstrate current knowledge of all first-aid requirements for Tenderfoot, Second Class, and First Class ranks.",
                "safety_callout": "Always ensure scene safety, apply the Buddy System, and wear nitrile PPE gloves before rendering aid.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "DECISION_TREE_FLOW",
                "visual_diagram_type": "triage_decision_tree",
                "pamphlet_image_path": "assets/ai_illustrations/first_aid_triage_scene_visual.png",
                "pamphlet_excerpts": [
                    "Scene Size-Up First: Check for downed power lines, traffic, fire, falling rock, or aggressive animals before approaching any victim.",
                    "Primary Assessment ABCs: Verify Airway patency, Breathing adequacy, and Circulation/life-threatening hemorrhage within 15 seconds.",
                    "Emergency Call Protocol: Direct a specific bystander by name to call 911, fetch the troop first aid kit, and bring an AED.",
                    "Universal Precautions: Treat all blood and body fluids as potentially infectious by wearing non-latex nitrile exam gloves and eye protection.",
                ],
                "step_by_step_procedure": [
                    "Scan Hazard Zone: Survey 360 degrees for environmental dangers before stepping into the accident scene.",
                    "Check Responsiveness: Tap the victim's shoulder firmly and shout 'Are you OK?' while scanning chest rise.",
                    "Activate 911 & AED: Point to a specific Scout to call 911 with GPS coordinates and retrieve the AED.",
                    "Triage Priority Victims: Treat Immediate (Red) airway/bleeding threats before Delayed (Yellow) or Minor (Green) injuries.",
                ],
                "quiz_item": {
                    "scenario_prompt": "Your patrol finds a hiker unconscious at the base of a wet cliff with loose rocks still falling. What is your FIRST action?",
                    "options": [
                        "Rush in immediately to check for a carotid pulse and start CPR",
                        "Stop, secure scene safety, and avoid entering the active rockfall hazard zone",
                        "Give the hiker water and elevate their legs 12 inches",
                        "Move the hiker onto a sleeping pad without stabilizing the neck",
                    ],
                    "correct_answer": "Stop, secure scene safety, and avoid entering the active rockfall hazard zone",
                    "explanation": "Per the BSA First Aid Pamphlet, rescuers must never become a second victim; scene safety always precedes patient contact.",
                },
                "topic_slides": [
                    {
                        "title": "Scene Size-Up & Universal Precautions",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p016_img1.png",
                        "caption": "Scouts performing a scene safety check and initial injury assessment on a fallen hiker along a rocky trail.",
                        "bullets": [
                            "360-Degree Hazard Scan: Survey the scene for falling rock, fire, downed wires, deep water, or traffic before stepping forward.",
                            "BSI / PPE Barrier Protection: Put on non-latex nitrile exam gloves and eye protection before touching blood or bodily fluids.",
                            "Mechanism of Injury (MOI): Determine whether a fall from height or high-impact collision requires cervical spine immobilization.",
                            "Number of Patients: Count all injured persons quickly so you can brief 911 dispatch and organize patrol triage.",
                        ],
                    },
                    {
                        "title": "Primary Assessment & Calling 911",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p018_img1.png",
                        "caption": "First-aider kneeling beside an injured person to check responsiveness, breathing, and life-threatening conditions.",
                        "bullets": [
                            "Check-Call-Care Sequence: Check scene and responsiveness, Call 911 and bring an AED, then Care for life-threatening conditions in order of priority.",
                            "Head-Tilt / Chin-Lift: Open the airway of an unresponsive victim by tilting the forehead back and lifting the chin bony rim.",
                            "Side-Lying Recovery Position: Place a breathing, unresponsive patient with no spinal injury onto their side so fluids drain safely from the mouth.",
                            "Good Samaritan Protection: Act within the scope of your training and obtain consent from conscious patients (or parent/guardian of a minor).",
                        ],
                    },
                    {
                        "title": "Four-Step Primary Triage Sequence",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Scan Hazard Zone: Survey 360 degrees for environmental dangers before stepping into the accident scene.",
                            "Check Responsiveness: Tap the victim's shoulder firmly and shout 'Are you OK?' while scanning chest rise.",
                            "Activate 911 & AED: Point to a specific Scout to call 911 with GPS coordinates and retrieve the AED.",
                            "Triage Priority Victims: Treat Immediate (Red) airway/bleeding threats before Delayed (Yellow) or Minor (Green) injuries.",
                        ],
                    },
                    {
                        "title": "Patrol Scenario: Rockfall Triage Decision",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "scenario_prompt": "Your patrol finds a hiker unconscious at the base of a wet cliff with loose rocks still falling. What is your FIRST action?",
                            "options": [
                                "Rush in immediately to check for a carotid pulse and start CPR",
                                "Stop, secure scene safety, and avoid entering the active rockfall hazard zone",
                                "Give the hiker water and elevate their legs 12 inches",
                                "Move the hiker onto a sleeping pad without stabilizing the neck",
                            ],
                            "correct_answer": "Stop, secure scene safety, and avoid entering the active rockfall hazard zone",
                            "explanation": "Per the BSA First Aid Pamphlet, rescuers must never become a second victim; scene safety always precedes patient contact.",
                        },
                        "bullets": [
                            "Your patrol finds a hiker unconscious at the base of a wet cliff with loose rocks still falling. What is your FIRST action?",
                            "Stop, secure scene safety, and avoid entering the active rockfall hazard zone",
                            "Per the BSA First Aid Pamphlet, rescuers must never become a second victim; scene safety always precedes patient contact.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout brings signed Scoutbook rank verification for Tenderfoot/Second/First Class first aid and walks through the 4-tier triage decision tree.",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "topic_title": "Req 2: Preparing for First Aid Emergencies",
                "action_verb": "Prepare",
                "req_text": "Preparing for First Aid Emergencies. Do the following: Prepare a personal first-aid kit to take with you on a hike, inspect a troop/patrol first-aid kit, and explain how each item is used.",
                "safety_callout": "Inspect sterile dressings for intact packaging and check expiration dates on antiseptic wipes and medications before every trek.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "GEAR_CHECKLIST_GRID",
                "visual_diagram_type": "first_aid_kit_grid",
                "pamphlet_image_path": "assets/ai_illustrations/first_aid_kit_21_items_visual.png",
                "pamphlet_excerpts": [
                    "Personal Kit Portability: Pack personal hike items in a waterproof resealable bag stored in an exterior backpack pocket for instant access.",
                    "Barrier Protection Essentials: Always carry 2 pairs of non-latex nitrile exam gloves and a CPR breathing barrier mask.",
                    "Blister & Wound Care: Include moleskin pre-cut pads, sterile 3x3 gauze sponges, adhesive bandages, and non-adherent trauma dressings.",
                    "Troop Kit Scaling: Troop kits add SAM malleable splints, commercial windlass tourniquets, triangular cravat bandages, and elastic wraps.",
                ],
                "gear_checklist": [
                    "Sterile Dressings: Adhesive bandages (6 assorted sizes) & 2 sterile 3x3-inch gauze pads",
                    "Tape & Blister Care: Adhesive medical tape (1 roll) & moleskin blister dressings (3x6-inch)",
                    "Barrier Protection: Non-latex nitrile exam gloves (2 pairs) & CPR pocket breathing barrier",
                    "Antiseptic & Instruments: Soap/hand sanitizer, antibiotic gel packets, scissors, tweezers & SOAP card",
                ],
                "topic_slides": [
                    {
                        "title": "Personal vs. Troop First-Aid Kit Layout",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/ai_illustrations/first_aid_kit_21_items_visual.png",
                        "caption": "Flat-Lay Inspection of Personal & Troop First-Aid Supplies: Waterproof red case containing sterile gauze, roller bandages, moleskin, trauma shears, tweezers, nitrile gloves, CPR mask, SAM splint, and triangular cravats.",
                        "bullets": [
                            "Visual Inventory: Every Scout carries a compact personal hike kit for blisters, minor cuts, and PPE, while the patrol carries the comprehensive 21-item Troop First-Aid Kit.",
                        ],
                    },
                    {
                        "title": "Inspecting Patrol, Personal & Camp First-Aid Kits",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p012_img1.png",
                        "caption": "Scouts inspecting and organizing the contents of their personal and patrol first-aid kits at camp.",
                        "bullets": [
                            "Annual Health & Medical Record (Req 2a): Review AHMR Parts A, B, and C before every outing to check allergies, asthma inhalers, EpiPens, and tetanus dates.",
                            "Personal Hike Kit Essentials (Req 2b1): Carry adhesive bandages, sterile 3x3 gauze, moleskin, adhesive tape, nitrile gloves, CPR barrier, soap, and scissors.",
                            "Unit & Camp Kit Audit (Req 2b2): Inspect troop kits before each campout to replace expired antiseptic wipes, torn gauze packages, or missing cravats.",
                            "Exterior Pocket Readiness: Store your personal first-aid kit in a waterproof zip-top bag inside an top/outer pack pocket so any buddy can locate it.",
                        ],
                    },
                    {
                        "title": "Personal Hike Kit Inspection Checklist",
                        "layout": "GEAR_CHECKLIST_GRID",
                        "gear_checklist": [
                            "Sterile Dressings: Adhesive bandages (6 assorted sizes) & 2 sterile 3x3-inch gauze pads",
                            "Tape & Blister Care: Adhesive medical tape (1 roll) & moleskin blister dressings (3x6-inch)",
                            "Barrier Protection: Non-latex nitrile exam gloves (2 pairs) & CPR pocket breathing barrier",
                            "Antiseptic & Instruments: Soap/hand sanitizer, antibiotic gel packets, scissors, tweezers & SOAP card",
                        ],
                        "bullets": [
                            "Sterile Dressings: Adhesive bandages (6 assorted sizes) & 2 sterile 3x3-inch gauze pads",
                            "Tape & Blister Care: Adhesive medical tape (1 roll) & moleskin blister dressings (3x6-inch)",
                            "Barrier Protection: Non-latex nitrile exam gloves (2 pairs) & CPR pocket breathing barrier",
                            "Antiseptic & Instruments: Soap/hand sanitizer, antibiotic gel packets, scissors, tweezers & SOAP card",
                        ],
                    },
                    {
                        "title": "Home & Backcountry Emergency Medical Dispatch",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "Backcountry 911 / SAR Emergency Dispatch Script",
                            "artifact_type": "ACTION_PLAN",
                            "fields": {
                                "Location & Coordinates": "Philmont Trail Camp Beaubien, UTM 13S 496120E 4031850N, Nearest Road: HWY 21",
                                "Patient Profile": "14-year-old male Scout, conscious, known severe bee-sting allergy on AHMR Part B",
                                "Chief Complaint & Vitals": "Anaphylactic reaction after yellowjacket sting; HR 118, RR 24, wheezing",
                                "Treatment Rendered": "EpiPen 0.3mg auto-injector administered in outer right thigh at 14:12; monitoring airway",
                            },
                            "counselor_tip": "Have every Scout write down the exact address and cross-streets of their home and troop meeting place before class.",
                        },
                        "bullets": [
                            "Location & Coordinates: Philmont Trail Camp Beaubien, UTM 13S 496120E 4031850N, Nearest Road: HWY 21",
                            "Patient Profile: 14-year-old male Scout, conscious, known severe bee-sting allergy on AHMR Part B",
                            "Chief Complaint & Vitals: Anaphylactic reaction after yellowjacket sting; HR 118, RR 24, wheezing",
                            "Treatment Rendered: EpiPen 0.3mg auto-injector administered in outer right thigh at 14:12; monitoring airway",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout presents their physical personal first-aid kit for inspection and identifies the purpose of every item in the personal and troop kits.",
            },
            {
                "req_id": "3",
                "req_number": "3",
                "topic_title": "Req 3: Closed Wounds, Burns, Frostbite, Blisters & Bites/Stings",
                "action_verb": "Explain",
                "req_text": "Wounds with No External Bleeding. Describe the symptoms and signs of, show first aid for, and explain prevention of closed wounds, thermal/chemical/electrical burns, sunburn, snow blindness, frostbite, abrasions, blisters, puncture wounds, poisonous plants, and insect/tick/spider/snake bites.",
                "safety_callout": "Cool thermal burns under running water (never apply ice or butter), never rub frostbitten tissue, and stop hiking at the first warm 'hot spot' to apply moleskin.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/ai_illustrations/first_aid_wound_cleaning_blister_visual.png",
                "pamphlet_excerpts": [
                    "Closed Wounds & Burns (Reqs 3a–3d): Apply wrapped cold packs to contusions; cool 1st/2nd-degree thermal burns with running water for 10+ minutes; flush chemical burns for 20 minutes and shut off power before approaching electrical burns.",
                    "Sunburn, Snow Blindness & Frostbite (Reqs 3e–3g): Wear SPF 30+ sunscreen and UV-blocking glacier sunglasses; rewarm frostbitten fingers/toes in 99°F–104°F water (never rub or rewarm if refreezing is possible).",
                    "Abrasions, Blisters & Punctures (Reqs 3h–3j): Irrigate scrapes with clean water, surround foot hot spots/blisters with a cutout moleskin doughnut pad, pull splinters along the entry angle, and stabilize embedded fishhooks for a physician.",
                    "Poisonous Plants, Ticks, Spiders & Snakes (Reqs 3k–3q): Wash poison ivy/oak/sumac urushiol oil off immediately with soap and cool water, pull ticks straight out with fine tweezers, and keep venomous snakebites immobilized at heart level.",
                ],
                "step_by_step_procedure": [
                    "Cool Thermal Burns Promptly: Hold superficial and partial-thickness burns under cool running water until pain subsides, then cover loosely with dry sterile gauze.",
                    "Apply Moleskin Doughnut: Stop hiking at the first warm hot spot, dry the skin, and center a cutout moleskin ring around the blister.",
                    "Remove Ticks & Splinters Safely: Grasp ticks close to the skin with fine-tipped tweezers and pull straight out steadily without twisting.",
                    "Wash Urushiol & Immobilize Bites: Scrub skin exposed to poison ivy with soap and water within 15 minutes; call 911 and immobilize venomous bites.",
                ],
                "topic_slides": [
                    {
                        "title": "Abrasions, Wound Irrigation & Trail Blister Protection",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/ai_illustrations/first_aid_wound_cleaning_blister_visual.png",
                        "caption": "Minor Wound & Trail Blister Care: (Left) Irrigating a forearm abrasion with clean water from a canteen and mild soap; (Right) Applying a doughnut-cutout moleskin pad over a heel blister.",
                        "bullets": [
                            "Clean Irrigation & Friction Relief: Flush abrasions with potable water to prevent infection, and relieve trail friction immediately with a moleskin doughnut pad.",
                        ],
                    },
                    {
                        "title": "Thermal, Chemical & Electrical Burns, Sunburn & Frostbite (Reqs 3b–3g)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p066_img1.png",
                        "caption": "Cooling a thermal forearm burn immediately under cool running water in a sink until pain subsides.",
                        "bullets": [
                            "Three Degrees of Burns (Req 3b): 1st-degree (red epidermis), 2nd-degree (blistered dermis), and 3rd-degree (charred/white full-thickness—cover dry and call 911).",
                            "Chemical & Electrical Burns (Reqs 3c–3d): Brush dry chemicals off before flushing with water for 20 minutes; verify electrical power is off before touching the patient.",
                            "Sunburn & Snow Blindness (Reqs 3e–3f): Prevent with broad-spectrum SPF 30+ sunscreen and UV sunglasses; treat snow blindness with cool damp cloths in darkness.",
                            "Immersion Foot & Frostbite (Req 3g): Keep feet dry in wool socks; rewarm frostbite in 99°F–104°F warm water and place dry sterile gauze between toes.",
                        ],
                    },
                    {
                        "title": "Foot Blister Moleskin Care, Ticks, Poison Ivy & Bites (Reqs 3i–3q)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p042_img1.png",
                        "caption": "Protective moleskin pad applied over the heel to shield a friction hot spot and prevent blister rupture.",
                        "bullets": [
                            "Moleskin Doughnut Technique (Req 3i): Stop at the first 'hot spot' sensation and apply a doughnut-shaped moleskin pad so boot friction spares the blister roof.",
                            "Splinters & Fishhooks (Req 3j): Pull splinters out along the entry angle with sterile tweezers; never push a barbed fishhook through skin in the backcountry.",
                            "Poison Ivy, Oak & Sumac (Req 3k): Learn 'leaves of three, let it be'; scrub urushiol oil off skin and boot laces with soap and cool water.",
                            "Ticks, Spiders & Snakebites (Reqs 3l–3q): Pull ticks straight out with fine tweezers; for venomous snakebites, keep calm, immobilize at heart level, and call 911 (no tourniquets or suction!).",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout explains signs, prevention, and first aid for closed wounds, 1st/2nd/3rd-degree burns, frostbite, blisters, punctures, poisonous plants, and bites/stings.",
            },
            {
                "req_id": "4",
                "req_number": "4",
                "topic_title": "Req 4: Bleeding Wounds, Nosebleeds, Tourniquets & Shock",
                "action_verb": "Demonstrate",
                "req_text": "Bleeding Wounds. Describe the symptoms and signs of, show first aid for, and explain prevention of nosebleeds, open wounds with mild or moderate bleeding, open wounds with severe bleeding, and windlass tourniquet application.",
                "safety_callout": "Never remove an original blood-soaked gauze pad; layer fresh sterile gauze on top and apply a windlass tourniquet 2 inches above life-threatening extremity wounds.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "STEP_BY_STEP_PROCEDURE_4CARD",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/first_aid_p036_img1.png",
                "pamphlet_excerpts": [
                    "Nosebleed Care (Req 4a): Have the patient sit upright and lean slightly forward (never tilt the head back!) while pinching the soft lower nostrils firmly for 10 full minutes.",
                    "Mild to Moderate Open Wounds (Req 4b): Irrigate under clean running water with mild soap for 5 minutes, apply antibiotic ointment if no allergy exists, and cover with a sterile adhesive dressing.",
                    "Severe Arterial Bleeding (Req 4c): Apply firm, continuous gloved direct pressure using a thick sterile gauze pad and secure with a snug pressure roller bandage.",
                    "Windlass Tourniquet Protocol (Req 4d): When direct pressure cannot stop life-threatening limb bleeding, strap a commercial tourniquet 2–3 inches above the wound (never over a joint), twist until bleeding stops, and note the exact time.",
                ],
                "step_by_step_procedure": [
                    "Apply Direct Pressure: Press firmly with gloved hands and sterile gauze pad directly over the bleeding source for 5 full minutes.",
                    "Position Windlass Tourniquet: Strap tourniquet 2 inches above the limb wound (never over knee or elbow joint) and pull tight.",
                    "Twist Windlass Rod: Rotate the windlass rod until bright red bleeding stops completely and distal pulse disappears.",
                    "Lock & Treat Shock: Secure the rod in the clip, record application time ('TK 14:20'), lay patient flat, and insulate with blankets.",
                ],
                "topic_slides": [
                    {
                        "title": "Direct Pressure & Pressure Bandages for Severe Bleeding (Req 4c)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p036_img1.png",
                        "caption": "Applying firm direct pressure with a sterile gauze pad over a forearm wound to control severe bleeding.",
                        "bullets": [
                            "Continuous Firm Pressure: Hold uninterrupted direct pressure with a sterile gauze pad for at least 5 full minutes without lifting to peek.",
                            "Never Peel Blood-Soaked Gauze: Pulling off the first pad rips away clotting fibrin; stack a second sterile pad on top and wrap snugly.",
                            "When to Use a Tourniquet (Req 4d): Use only for life-threatening extremity bleeding that direct pressure cannot control; never tighten a real tourniquet on a healthy Scout during practice.",
                            "Check Distal Circulation: After wrapping a roller pressure bandage, check fingers or toes for bluish skin, numbness, or coldness.",
                        ],
                    },
                    {
                        "title": "Controlling Nosebleeds & Mild Open Wounds (Reqs 4a–4b)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p076_img1.png",
                        "caption": "Controlling a nosebleed by leaning the head forward and pinching the soft lower nostrils firmly for 10 minutes.",
                        "bullets": [
                            "Sit Upright & Lean Forward (Req 4a): Leaning forward keeps blood from draining down the back of the throat into the airway or stomach.",
                            "Pinch Soft Nostrils 10 Minutes: Pinch the soft lower part of the nose just below the bony bridge continuously for 10 minutes and apply a cool compress.",
                            "Flush Mild Cuts Thoroughly (Req 4b): Wash shallow cuts and scrapes under clean running tap or canteen water with soap to flush out bacteria and grit.",
                            "Monitor for Shock & Infection: Treat severe bleeding patients for shock (flat on a pad, insulated with blankets) and watch minor wounds for redness or pus.",
                        ],
                    },
                    {
                        "title": "Four-Step Hemorrhage & Tourniquet Protocol",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Apply Direct Pressure: Press firmly with gloved hands and sterile gauze pad directly over the bleeding source for 5 full minutes.",
                            "Position Windlass Tourniquet: Strap tourniquet 2 inches above the limb wound (never over knee or elbow joint) and pull tight.",
                            "Twist Windlass Rod: Rotate the windlass rod until bright red bleeding stops completely and distal pulse disappears.",
                            "Lock & Treat Shock: Secure the rod in the clip, record application time ('TK 14:20'), lay patient flat, and insulate with blankets.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout demonstrates nosebleed care, mild wound dressing, direct pressure bandage, and simulated windlass tourniquet placement (without tightening).",
            },
            {
                "req_id": "5",
                "req_number": "5",
                "topic_title": "Req 5: Breathing Emergencies: Choking, Asthma, Anaphylaxis & Altitude",
                "action_verb": "Demonstrate",
                "req_text": "Breathing Emergencies. Describe the symptoms and signs of, show first aid for, and explain prevention of choking, asthmatic attack, anaphylaxis from an insect bite/sting or food/product allergy, inhalation injuries, and altitude sickness.",
                "safety_callout": "Never perform blind finger sweeps in a choking victim's mouth, and assist immediately with prescribed epinephrine auto-injectors or asthma inhalers when airway swelling or bronchospasm occurs.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "STEP_BY_STEP_PROCEDURE_4CARD",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/ai_illustrations/first_aid_choking_5and5_visual.png",
                "pamphlet_excerpts": [
                    "Conscious Choking 5-and-5 (Req 5a): Alternate 5 firm back blows between the shoulder blades with the heel of your hand and 5 inward-upward abdominal thrusts above the navel.",
                    "Asthmatic Attack Care (Req 5b): Help the Scout sit upright in a comfortable tripod position, loosen tight pack straps, and assist with their prescribed quick-relief bronchodilator inhaler and spacer.",
                    "Anaphylaxis & Epinephrine Auto-Injector (Req 5c): Hives, facial/throat swelling, and wheezing require immediate 911 activation and pressing a prescribed epinephrine auto-injector against the outer mid-thigh for 3–10 seconds.",
                    "Inhalation Injuries & Altitude Sickness (Reqs 5d–5e): Move carbon monoxide or smoke victims to fresh air if safe; for Acute Mountain Sickness (AMS), HAPE, or HACE on high-altitude treks, stop ascending and descend immediately.",
                ],
                "step_by_step_procedure": [
                    "Confirm Airway Obstruction: Ask 'Are you choking?' and obtain consent if the person clutches their throat and cannot cough or speak.",
                    "Deliver 5 Back Blows & 5 Thrusts: Alternate 5 back blows and 5 upward abdominal thrusts above the navel until the object clears.",
                    "Assist Asthma Inhaler or EpiPen: For asthma, assist with bronchodilator inhaler + spacer; for anaphylaxis, inject EpiPen into outer mid-thigh and call 911.",
                    "Fresh Air & Descent Protocol: Move inhalation victims to fresh air; descend 1,500–3,000 feet immediately if altitude sickness symptoms worsen.",
                ],
                "topic_slides": [
                    {
                        "title": "Conscious Choking Care: 5 Back Blows & 5 Abdominal Thrusts (Req 5a)",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/ai_illustrations/first_aid_choking_5and5_visual.png",
                        "caption": "Two-Panel Choking Rescue Technique: (Left) Supporting the chest while delivering 5 firm back blows between the shoulder blades; (Right) Delivering 5 upward-inward abdominal thrusts just above the navel.",
                        "bullets": [
                            "Five-and-Five Airway Clearance: Alternate 5 firm back blows with the heel of your hand and 5 inward-upward abdominal thrusts (Heimlich maneuver) until the obstruction is expelled.",
                        ],
                    },
                    {
                        "title": "Asthma Inhalers, Anaphylaxis EpiPen & Altitude Sickness (Reqs 5b–5e)",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Asthma Action Plan (Req 5b): Sit the Scout upright, attach the valved holding chamber (spacer) to their rescue inhaler, and have them inhale slowly and hold for 10 seconds.",
                            "Anaphylaxis & EpiPen (Req 5c): Pull safety cap ('Blue to the Sky, Orange to the Thigh'), press firmly at 90° into the outer mid-thigh for 3–10 seconds, call 911, and prepare a second dose if needed.",
                            "Carbon Monoxide & Smoke Inhalation (Req 5d): Never run camp stoves or lanterns inside a tent; move victims to fresh air immediately and call 911.",
                            "Altitude Sickness Prevention & Care (Req 5e): Acclimatize gradually above 8,000 ft, hydrate well, and descend immediately if headache, dizziness, breathlessness at rest (HAPE), or confusion (HACE) appears.",
                        ],
                    },
                    {
                        "title": "Four-Step Breathing Emergency Response",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Confirm Airway Obstruction: Ask 'Are you choking?' and obtain consent if the person clutches their throat and cannot cough or speak.",
                            "Deliver 5 Back Blows & 5 Thrusts: Alternate 5 back blows and 5 upward abdominal thrusts above the navel until the object clears.",
                            "Assist Asthma Inhaler or EpiPen: For asthma, assist with bronchodilator inhaler + spacer; for anaphylaxis, inject EpiPen into outer mid-thigh and call 911.",
                            "Fresh Air & Descent Protocol: Move inhalation victims to fresh air; descend 1,500–3,000 feet immediately if altitude sickness symptoms worsen.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout demonstrates 5-and-5 choking rescue positioning, explains asthma inhaler and epinephrine auto-injector use, and describes care for inhalation injuries and altitude sickness.",
            },
            {
                "req_id": "6",
                "req_number": "6",
                "topic_title": "Req 6: Loss of Consciousness: Fainting, Seizures, Drowning & Lightning",
                "action_verb": "Explain",
                "req_text": "Loss of Consciousness. Describe the symptoms and signs of, show first aid for, and explain prevention of fainting, hypoglycemia, seizure, drug overdose and alcohol poisoning, underwater hypoxic blackout, cold water shock and drowning, and lightning strike and electric shock.",
                "safety_callout": "Never place anything inside a seizure victim's mouth, never give oral food or liquids to an unconscious person, and never enter water or active electrical zones without securing scene safety.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/first_aid_p074_img2.png",
                "pamphlet_excerpts": [
                    "Fainting & Hypoglycemia (Reqs 6a–6b): Lay a fainting person flat and raise legs 12 inches; for a conscious diabetic with low blood sugar, apply the Rule of 15 (15–20g fast-acting oral glucose/juice).",
                    "Seizures & Overdose/Poisoning (Reqs 6c–6d): Cushion the head during a seizure, clear nearby hazards, never restrain or put anything in the mouth, and roll into the recovery position afterward; call 911/Poison Control (1-800-222-1222) and administer naloxone if opioid overdose is suspected.",
                    "Underwater Blackout & Cold-Water Drowning (Reqs 6e–6f): Ban hyperventilating or extended breath-holding games before underwater swimming; follow Reach-Throw-Row-Go with Support and wear PFDs in cold water.",
                    "Lightning Strike & Electric Shock (Req 6g): Leave high ridges and open water at the first thunder (30/30 rule); verify power is off before touching electrocution victims and start CPR/AED immediately if pulseless.",
                ],
                "step_by_step_procedure": [
                    "Check Airway & Breathing: Verify scene safety, tap shoulder, and check for normal breathing for 5–10 seconds.",
                    "Place in Recovery Position: If unconscious but breathing normally (with no spinal trauma), roll the patient onto their side so the airway stays clear.",
                    "Protect Seizure or Fainting Patient: Cushion the head during convulsions; for simple fainting, lay flat on the back and elevate legs 12 inches.",
                    "Treat Hypoglycemia & Call 911: Give 15–20g oral glucose ONLY if conscious and able to swallow; call 911 for any prolonged unconsciousness, drowning, or lightning strike.",
                ],
                "topic_slides": [
                    {
                        "title": "Lateral Recovery Position, Fainting, Hypoglycemia & Seizures (Reqs 6a–6c)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p074_img2.png",
                        "caption": "Rolling an unconscious, breathing patient onto their side into the recovery position to keep the airway clear.",
                        "bullets": [
                            "Lateral Recovery Position: Roll an unconscious, breathing patient with no spinal injury onto their side so the tongue falls forward and fluids drain out.",
                            "Simple Fainting (Syncope, Req 6a): Caused by temporary drop in blood flow to the brain from heat, dehydration, or locking knees; lay flat and elevate legs 12 inches.",
                            "Diabetic Hypoglycemia (Req 6b): Sweating, shakiness, and confusion require 15–20g oral glucose/juice if conscious; call 911 if unresponsive (never give oral liquid!).",
                            "Generalized Seizures (Req 6c): Pad beneath the head, move hard gear away, time the seizure, never hold the person down, and roll onto their side once jerking stops.",
                        ],
                    },
                    {
                        "title": "Overdose, Underwater Blackout, Drowning & Lightning (Reqs 6d–6g)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p074_img1.png",
                        "caption": "Positioning an unconscious, breathing patient's arm and knee to roll them safely onto their side.",
                        "bullets": [
                            "Overdose & Poisoning (Req 6d): Call 911 and 1-800-222-1222 immediately, monitor airway/breathing, place in recovery position, and begin CPR if breathing stops.",
                            "Underwater Hypoxic Blackout (Req 6e): Hyperventilating before underwater breath-holding purges CO2 and causes sudden blackout before the urge to breathe—strictly prohibited in Scouting aquatics.",
                            "Cold-Water Shock & Drowning (Req 6f): Cold water (<60°F) triggers an involuntary gasp reflex; always wear a USCG life jacket and rescue via Reach, Throw, Row, Go.",
                            "Lightning & Electric Shock (Req 6g): Seek enclosed buildings or low timber when thunder roars; lightning cardiac arrest victims do not hold a charge—start CPR/AED immediately.",
                        ],
                    },
                    {
                        "title": "Four-Step Unconscious Patient Protocol",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Check Airway & Breathing: Verify scene safety, tap shoulder, and check for normal breathing for 5–10 seconds.",
                            "Place in Recovery Position: If unconscious but breathing normally (with no spinal trauma), roll the patient onto their side so the airway stays clear.",
                            "Protect Seizure or Fainting Patient: Cushion the head during convulsions; for simple fainting, lay flat on the back and elevate legs 12 inches.",
                            "Treat Hypoglycemia & Call 911: Give 15–20g oral glucose ONLY if conscious and able to swallow; call 911 for any prolonged unconsciousness, drowning, or lightning strike.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout demonstrates placing a breathing unresponsive patient into the recovery position and explains first aid and prevention for all 7 Req 6 conditions (6a–6g).",
            },
            {
                "req_id": "7",
                "req_number": "7",
                "topic_title": "Req 7: Heart Attack, 30:2 CPR & AED Defibrillation",
                "action_verb": "Demonstrate",
                "req_text": "Heart Attack, CPR, and AED. Describe the warning signs of a heart attack, and demonstrate cardiopulmonary resuscitation (CPR) using a 30:2 compression-to-breath cycle at 100 to 120 compressions per minute and proper Automated External Defibrillator (AED) pad placement on a training manikin.",
                "safety_callout": "Call 911 immediately upon finding an unresponsive person and ensure all rescuers stand clear before pressing the AED shock button.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate, Guide & Enable",
                "recommended_archetype": "HANDS_ON_PRACTICE_STATION",
                "visual_diagram_type": "cpr_aed_cycle",
                "pamphlet_image_path": "assets/ai_illustrations/first_aid_cpr_aed_visual.png",
                "pamphlet_excerpts": [
                    "Compression Depth & Rate: Push hard and fast in the center of the lower sternum at 2.0 to 2.4 inches depth and 100 to 120 BPM.",
                    "Full Chest Recoil: Allow the chest wall to recoil completely after each compression so the heart refills with blood.",
                    "30:2 Rescue Cycle: Deliver 30 chest compressions followed by 2 rescue breaths (1 second each using head-tilt/chin-lift and barrier mask).",
                    "Anterolateral AED Placement: Apply upper-right pad below right collarbone and lower-left pad on left side of chest below armpit.",
                ],
                "step_by_step_procedure": [
                    "Verify Unresponsiveness: Tap shoulder, check for normal breathing for 5 to 10 seconds, and dispatch 911 plus AED.",
                    "Deliver 30 Compressions: Lock elbows over center of sternum, compressing 2 inches deep at 100 to 120 beats per minute.",
                    "Give 2 Rescue Breaths: Perform head-tilt/chin-lift, seal pocket mask, and deliver 2 breaths watching for visible chest rise.",
                    "Attach AED & Follow Prompts: Bare and dry chest, place upper-right and lower-left pads, clear victim, and resume CPR immediately after shock.",
                ],
                "topic_slides": [
                    {
                        "title": "High-Quality 30:2 CPR & Anterolateral AED Placement",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/ai_illustrations/first_aid_cpr_aed_visual.png",
                        "caption": "CPR & AED Skill Station: Rescuer with locked straight elbows compressing the center of a CPR manikin's sternum beside an open AED with pads placed on the upper-right chest and lower-left ribs.",
                        "bullets": [
                            "Chain of Survival Execution: Combine immediate 100-120 BPM chest compressions (2.0-2.4 inches deep) with rapid AED defibrillation.",
                        ],
                    },
                    {
                        "title": "Chest Compression Body Mechanics & AED Safety",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p090_img1.png",
                        "caption": "Scouts practicing CPR chest compressions and rescue breaths on a training manikin.",
                        "bullets": [
                            "Heart Attack Warning Signs (Reqs 7a–7b): Uncomfortable squeezing chest pressure, pain radiating to left arm/shoulder/jaw, shortness of breath, cold sweat, and nausea.",
                            "Aspirin Protocol (Conscious Adult): If a conscious adult has suspected heart attack symptoms and no aspirin allergy or bleeding disorder, offer chewable aspirin while awaiting EMS.",
                            "Dry & Bare Chest for AED (Reqs 7e–7f): Wipe sweat or water off the chest, shouting 'Everybody clear!' during AED rhythm analysis or shock delivery.",
                            "Community AED Locations (Req 7g): Locate AEDs near main entrances, gymnasiums, cafeterias, camp health lodges, and worship centers for <3-minute access.",
                        ],
                    },
                    {
                        "title": "Four-Step CPR & AED Rescue Sequence",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Verify Unresponsiveness: Tap shoulder, check for normal breathing for 5 to 10 seconds, and dispatch 911 plus AED.",
                            "Deliver 30 Compressions: Lock elbows over center of sternum, compressing 2 inches deep at 100 to 120 beats per minute.",
                            "Give 2 Rescue Breaths: Perform head-tilt/chin-lift, seal pocket mask, and deliver 2 breaths watching for visible chest rise.",
                            "Attach AED & Follow Prompts: Bare and dry chest, place upper-right and lower-left pads, clear victim, and resume CPR immediately after shock.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout completes at least 2 full cycles of 30:2 CPR and attaches AED training pads accurately on a CPR manikin.",
            },
            {
                "req_id": "8",
                "req_number": "8",
                "topic_title": "Req 8: Fractures, Sprains, Splinting & CMS Checks",
                "action_verb": "Demonstrate",
                "req_text": "Bone, Joint, and Muscle Injuries. Describe the symptoms and signs of, and demonstrate anatomical and rigid splinting techniques for closed and open fractures, sprains, and dislocations, including pre- and post-splint distal Circulation, Motor, and Sensation (CMS) checks.",
                "safety_callout": "Never attempt to straighten a dislocated joint or push a protruding open-fracture bone end back beneath the skin.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate, Guide & Enable",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "splinting_cms",
                "pamphlet_image_path": "assets/ai_illustrations/first_aid_splinting_carries_visual.png",
                "pamphlet_excerpts": [
                    "Splint Where It Lies: Immobilize the injured bone and both the joint above and the joint below in the position found.",
                    "Distal CMS Verification: Check radial/pedal pulse, capillary refill (<2 sec), finger/toe wiggle, and light touch before and after tying.",
                    "Padding Void Spaces: Pad natural hollows with fleece, foam sleeping pads, or roller gauze so cravats apply even pressure.",
                    "Sling & Swath Stabilization: Support upper-extremity fractures with a triangular bandage sling tied off-center of the cervical spine plus a chest swath.",
                ],
                "step_by_step_procedure": [
                    "Check Pre-Splint CMS: Verify distal pulse, capillary refill under 2 seconds, sensation, and finger/toe movement.",
                    "Stabilize Above & Below: Position padded rigid board or SAM splint spanning the joints above and below the fracture.",
                    "Secure With Cravats: Tie square knots over the rigid splint (never directly over the fracture site) firmly enough to prevent motion.",
                    "Re-Verify Distal CMS: Re-check pulse, warmth, and sensation every 15 minutes; loosen cravats if fingers/toes turn pale or numb.",
                ],
                "quiz_item": {
                    "scenario_prompt": "Ten minutes after you apply a forearm splint on a trail hike, the Scout complains that their fingers feel numb and tingling, and nailbed capillary refill takes 5 seconds. What must you do?",
                    "options": [
                        "Tighten the cravat knots further to prevent bone movement",
                        "Loosen the splint ties immediately, re-pad, and re-verify distal CMS circulation",
                        "Have the Scout hold their arm below waist level while hiking",
                        "Apply an ice pack directly onto bare skin for 45 minutes",
                    ],
                    "correct_answer": "Loosen the splint ties immediately, re-pad, and re-verify distal CMS circulation",
                    "explanation": "Delayed capillary refill (>2 sec) and paresthesia indicate vascular/nerve compression from swelling; loosen ties immediately while maintaining manual stabilization.",
                },
                "topic_slides": [
                    {
                        "title": "Rigid Forearm Splinting, Sling & Distal CMS Check",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/ai_illustrations/first_aid_splinting_carries_visual.png",
                        "caption": "Splinting & Transport Reference: (Left) Padded forearm splint with triangular cravat sling and distal finger circulation check; (Right) Two-rescuer four-handed seat carry.",
                        "bullets": [
                            "Immobilize Joint Above & Below: A forearm splint must immobilize both the wrist joint and the elbow joint to prevent bone rotation.",
                            "Open Fracture Dressing: Cover protruding bone ends with a moist sterile dressing and build a doughnut ring pad around—never push bone back in.",
                            "R.I.C.E. for Sprains: Rest the joint, apply wrapped Ice packs for 20 minutes, apply light Compression wrap, and Elevate.",
                            "Boot-On Ankle Figure-Eight: Leave the hiking boot laced on for trail ankle sprains and tie a figure-eight cravat support wrap outside the boot.",
                        ],
                    },
                    {
                        "title": "Lower-Leg & Ankle R.I.C.E. Care, Slings & Splinting",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p045_img1.png",
                        "caption": "Applying a wrapped cold pack and compression wrap to stabilize a lower-leg and ankle sprain using R.I.C.E. care.",
                        "bullets": [
                            "R.I.C.E. Cold Compression (Reqs 8b–8d): Apply a wrapped cold pack and elastic compression bandage to an ankle or lower-leg sprain to limit swelling.",
                            "Anatomical ('Buddy') Splinting (Req 8e): Secure an injured lower leg to the uninjured leg with folded blanket padding placed between the knees and ankles.",
                            "Leave Toes & Fingers Exposed: Always leave fingertips or toes visible outside the splint so you can check skin color, warmth, and capillary refill (<2 sec).",
                            "Collarbone & Shoulder Fractures (Req 8d1): Apply a triangular arm sling plus a broad chest binder ('swath') around the upper arm and torso.",
                        ],
                    },
                    {
                        "title": "Four-Step Splinting & CMS Verification Protocol",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Check Pre-Splint CMS: Verify distal pulse, capillary refill under 2 seconds, sensation, and finger/toe movement.",
                            "Stabilize Above & Below: Position padded rigid board or SAM splint spanning the joints above and below the fracture.",
                            "Secure With Cravats: Tie square knots over the rigid splint (never directly over the fracture site) firmly enough to prevent motion.",
                            "Re-Verify Distal CMS: Re-check pulse, warmth, and sensation every 15 minutes; loosen cravats if fingers/toes turn pale or numb.",
                        ],
                    },
                    {
                        "title": "Patrol Scenario: Post-Splint Numbness & Swelling",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "scenario_prompt": "Ten minutes after you apply a forearm splint on a trail hike, the Scout complains that their fingers feel numb and tingling, and nailbed capillary refill takes 5 seconds. What must you do?",
                            "options": [
                                "Tighten the cravat knots further to prevent bone movement",
                                "Loosen the splint ties immediately, re-pad, and re-verify distal CMS circulation",
                                "Have the Scout hold their arm below waist level while hiking",
                                "Apply an ice pack directly onto bare skin for 45 minutes",
                            ],
                            "correct_answer": "Loosen the splint ties immediately, re-pad, and re-verify distal CMS circulation",
                            "explanation": "Delayed capillary refill (>2 sec) and paresthesia indicate vascular/nerve compression from swelling; loosen ties immediately while maintaining manual stabilization.",
                        },
                        "bullets": [
                            "Ten minutes after you apply a forearm splint on a trail hike, the Scout complains that their fingers feel numb and tingling, and nailbed capillary refill takes 5 seconds. What must you do?",
                            "Loosen the splint ties immediately, re-pad, and re-verify distal CMS circulation",
                            "Delayed capillary refill (>2 sec) and paresthesia indicate vascular/nerve compression from swelling; loosen ties immediately while maintaining manual stabilization.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout applies a padded forearm or lower-leg splint plus sling/swath on a buddy and performs pre- and post-splint CMS checks.",
            },
            {
                "req_id": "9",
                "req_number": "9",
                "topic_title": "Req 9: Head, Neck, and Back Injuries & Concussion Care",
                "action_verb": "Demonstrate",
                "req_text": "Head and Spine Injuries. Do the following: (a) Describe the symptoms and signs of, relationships between, possible complications of, and prevention of head, neck, and back injuries. (b) Describe the symptoms and signs of and first aid for a concussion. (c) Demonstrate first aid for an open head wound with a triangular or other bandage. (d) Demonstrate first aid for someone with a suspected neck or back injury.",
                "safety_callout": "Assume a cervical spine injury after any fall from height, diving accident, or high-impact collision; hold manual in-line head stabilization and never move the patient unless life-threatening danger exists.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/first_aid_p022_img1.png",
                "pamphlet_excerpts": [
                    "When to Suspect Spinal Trauma (Req 9a): Any fall from height, diving into shallow water, bike/auto collision, or lightning strike can fracture vertebrae and damage the spinal cord.",
                    "Concussion Signs & Care (Req 9b): Headache, confusion, dizziness, nausea, blurry vision, or memory loss after a blow to the head require immediate removal from activity and medical evaluation.",
                    "Open Scalp Wound Bandaging (Req 9c): Control scalp bleeding with gentle diffuse pressure over a sterile gauze pad (never press hard on a suspected skull fracture!) secured with a triangular head bandage.",
                    "Manual In-Line Cervical Stabilization (Req 9d): Kneel behind the victim's head with elbows braced on the ground and hold both sides of the head in line with the neck until EMS arrives.",
                ],
                "step_by_step_procedure": [
                    "Assess Mechanism & Don PPE: Suspect spinal trauma after falls or collisions; put on nitrile gloves and instruct the patient not to nod or turn their head.",
                    "Hold Manual In-Line Stabilization: Kneel at the top of the head, brace your elbows on the ground, and cradle both sides of the head and ears steadily.",
                    "Dress Open Head Wounds Gently: Apply a sterile dressing and triangular forehead-occiput head wrap using gentle pressure (never press into a soft or depressed skull area).",
                    "Monitor Airway & Concussion Signs: Watch breathing, pupils, and consciousness continuously while awaiting EMS transport on a spinal board.",
                ],
                "topic_slides": [
                    {
                        "title": "Manual In-Line Cervical Spine Stabilization (Reqs 9a, 9d)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p022_img1.png",
                        "caption": "Rescuer wearing nitrile exam gloves applying manual in-line stabilization to protect the head and cervical spine.",
                        "bullets": [
                            "High-Risk Mechanisms (Req 9a): Falls from trees or cliffs, diving accidents, cycling crashes, and head impacts link head trauma directly to cervical spine fractures.",
                            "Spinal Cord Complications: Twisting or flexing an unstable neck fracture can sever or compress the spinal cord, causing permanent paralysis or respiratory arrest.",
                            "Manual In-Line Technique (Req 9d): Rest your elbows on the ground behind the patient's head and hold both sides of the head in neutral alignment.",
                            "Prevention in Scouting: Always wear helmets for cycling, climbing, snowboarding, and whitewater, and never dive into shallow or murky water.",
                        ],
                    },
                    {
                        "title": "Concussion Recognition & Open Head Wound Bandaging (Reqs 9b–9c)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p022_img2.png",
                        "caption": "Maintaining manual head and neck alignment while assessing responsiveness in a suspected spinal injury patient.",
                        "bullets": [
                            "Concussion Warning Signs (Req 9b): Dazed appearance, headache, nausea/vomiting, balance trouble, sensitivity to light/noise, or repeating the same question.",
                            "Red-Flag Brain Injury Signs: Unequal pupil size, clear fluid or blood draining from ears/nose, slurred speech, seizures, or worsening drowsiness require immediate 911.",
                            "Open Scalp Wound Care (Req 9c): Scalp wounds bleed heavily; place a thick sterile gauze pad over the wound and apply gentle, even pressure.",
                            "Triangular Head Bandage: Fold a narrow hem along the base of a triangular bandage, place across the forehead just above the eyebrows, wrap tails behind the skull, and tie.",
                        ],
                    },
                    {
                        "title": "Four-Step Head & Spinal Injury Protocol",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Assess Mechanism & Don PPE: Suspect spinal trauma after falls or collisions; put on nitrile gloves and instruct the patient not to nod or turn their head.",
                            "Hold Manual In-Line Stabilization: Kneel at the top of the head, brace your elbows on the ground, and cradle both sides of the head and ears steadily.",
                            "Dress Open Head Wounds Gently: Apply a sterile dressing and triangular forehead-occiput head wrap using gentle pressure (never press into a soft or depressed skull area).",
                            "Monitor Airway & Concussion Signs: Watch breathing, pupils, and consciousness continuously while awaiting EMS transport on a spinal board.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout explains head/neck/back injury signs and concussion care, demonstrates a triangular head bandage for an open scalp wound, and demonstrates manual in-line spinal stabilization.",
            },
            {
                "req_id": "10",
                "req_number": "10",
                "topic_title": "Req 10: Emergency Movement, Rescuer Carries & Litters",
                "action_verb": "Demonstrate",
                "req_text": "Moving a Patient. Describe the conditions under which an injured person should be moved, and demonstrate single-rescuer and two-rescuer emergency carries (walking assist, pack-strap carry, four-handed seat, blanket drag, and improvised two-pole stretcher).",
                "safety_callout": "Never move a victim with suspected head, neck, or spinal injury unless they face immediate life-threatening danger such as fire, rising water, or collapsing structure.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "STEP_BY_STEP_PROCEDURE_4CARD",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/first_aid_p030_img2.png",
                "pamphlet_excerpts": [
                    "Spinal Immobilization Priority: Assume cervical spine injury after any fall from height, diving accident, or high-impact collision.",
                    "Emergency Drag Indications: Use clothes drag, ankle drag, or blanket drag only to pull a victim out of immediate smoke, fire, or rockfall.",
                    "Two-Rescuer Four-Handed Seat: Interlock wrists in a square grid to carry a conscious victim with a sprained ankle who has no spinal injury.",
                    "Improvised Two-Pole Litter: Construct a sturdy stretcher from two 7-foot wooden spars threaded through heavy jackets or folded inside a wool blanket/tarp.",
                ],
                "step_by_step_procedure": [
                    "Assess Spinal Risk: Confirm zero neck/back pain, numbness, or high-mechanism trauma before attempting any upright carry.",
                    "Form Four-Handed Seat: Two rescuers grasp their own left wrist with right hand and partner's right wrist with left hand.",
                    "Load Conscious Patient: Squat evenly, have the patient sit on the wrist grid and place arms around rescuers' shoulders.",
                    "Lift & Step in Unison: Rise together on the count of three using leg muscles and step forward with inside feet synchronized.",
                ],
                "topic_slides": [
                    {
                        "title": "Single-Rescuer Blanket Drag & Smoke Extrication (Reqs 10a–10c)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p030_img2.png",
                        "caption": "Single-rescuer blanket drag used to pull an injured person to safety along the long axis of the body.",
                        "bullets": [
                            "Golden Rule of Patient Movement (Req 10a): Do NOT move a seriously injured person unless fire, flood, rockfall, or toxic smoke threatens their life.",
                            "Choosing the Best Method (Req 10b): Weigh victim consciousness, injury type, rescuer strength, number of helpers, and terrain distance.",
                            "Smoke-Filled Room Extrication (Req 10c): Stay low beneath rising smoke and pull along the long axis of the body using the blanket drag, shoulder/clothes drag, or ankle drag.",
                            "Single-Rescuer Walking Assist (Req 10d): Use the 'human crutch' walking assist or cradle carry for conscious hikers with a minor sprained ankle.",
                        ],
                    },
                    {
                        "title": "Two-Rescuer Four-Handed Seat & Improvised Stretcher (Reqs 10d–10e)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p033_img1.png",
                        "caption": "Two-rescuer four-handed seat carry transporting a conscious hiker who cannot bear weight on an injured ankle.",
                        "bullets": [
                            "Four-Handed Seat Wrist Grid (Req 10d): Each rescuer grasps their own left wrist with their right hand and their partner's right wrist with their left hand to carry 25+ yards.",
                            "Two-Pole Blanket Stretcher (Req 10e): Fold a heavy wool blanket or tarp in thirds over two sturdy 7-foot wooden spars to carry an unconscious patient 25+ yards.",
                            "Buttoned Jacket Litter: Turn two heavy zipped jackets inside-out with sleeves tucked inside and slide two poles through the sleeves.",
                            "Litter Team Safety: Always test an improvised stretcher with an uninjured Scout of equal weight before lifting the patient.",
                        ],
                    },
                    {
                        "title": "Four-Step Two-Rescuer Carry Procedure",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Assess Spinal Risk: Confirm zero neck/back pain, numbness, or high-mechanism trauma before attempting any upright carry.",
                            "Form Four-Handed Seat: Two rescuers grasp their own left wrist with right hand and partner's right wrist with left hand.",
                            "Load Conscious Patient: Squat evenly, have the patient sit on the wrist grid and place arms around rescuers' shoulders.",
                            "Lift & Step in Unison: Rise together on the count of three using leg muscles and step forward with inside feet synchronized.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout demonstrates smoke-room extrication drag, 25-yard sprained-ankle transport (solo and two-rescuer), and 25-yard improvised stretcher carry.",
            },
            {
                "req_id": "11",
                "req_number": "11",
                "topic_title": "Req 11: Heat Exhaustion vs. Heat Stroke & Hypothermia",
                "action_verb": "Describe",
                "req_text": "Heat- and Cold-Related Conditions. Describe the signals, differential diagnosis, prevention, and emergency treatment for dehydration, heat cramps, heat exhaustion, heat stroke, and hypothermia.",
                "safety_callout": "Heat stroke (>104°F with altered mental status) and severe hypothermia are immediate life-threatening emergencies requiring 911 activation.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "DIFFERENTIAL_COMPARISON_2COL",
                "visual_diagram_type": "heat_comparison",
                "pamphlet_image_path": "assets/ai_illustrations/first_aid_heat_hypothermia_visual.png",
                "pamphlet_excerpts": [
                    "Thermoregulatory Failure: Heat stroke occurs when core temperature exceeds 104°F (40°C) and central nervous system function breaks down.",
                    "Mental Status Differentiator: Confusion, slurred speech, ataxia, or unconsciousness immediately upgrades heat illness to Heat Stroke (911).",
                    "Hypothermia Rewarming: Remove wet cotton clothes, place Scout in a dry sleeping bag with warm water bottles at armpits and groin.",
                    "Proactive Hydration & Layering: Drink water before feeling thirsty until urine is pale straw-colored, and wear synthetic/wool wicking layers in cold weather.",
                ],
                "comparison_data": {
                    "left_header": "Heat Exhaustion",
                    "left_badge": "URGENT FIELD CARE",
                    "left_points": [
                        "Skin Appearance: Cool, pale, moist, and clammy skin with heavy profuse sweating",
                        "Core Temp & Pulse: Core body temperature 98.6°F to 103°F; rapid weak pulse and muscle cramps",
                        "Mental Status: Alert and oriented, but experiencing dizziness, nausea, headache, and fatigue",
                        "Field Treatment: Move to shade, loosen clothing, fan skin, and give small sips of cool electrolyte water",
                    ],
                    "right_header": "Heat Stroke (Call 911)",
                    "right_badge": "LIFE-THREATENING",
                    "right_points": [
                        "Skin Appearance: Hot, flushed red skin (dry or damp from exertion) with failed thermoregulation",
                        "Core Temp & Pulse: Core body temperature above 104°F (40°C); rapid bounding pulse transitioning to weak",
                        "Mental Status: Altered mental state including confusion, combativeness, seizures, or unconsciousness",
                        "Emergency Action: Call 911 immediately; rapid cold-water immersion or ice packs at neck, armpits, and groin",
                    ],
                },
                "topic_slides": [
                    {
                        "title": "Heat Emergencies vs. Hypothermia Field Care",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/ai_illustrations/first_aid_heat_hypothermia_visual.png",
                        "caption": "Wilderness Thermal Emergencies: (Left) Cooling an overheated hiker in deep shade with cool wet cloths and hydration; (Right) Rewarming a shivering hypothermic hiker inside a dry sleeping bag under a tarp.",
                        "bullets": [
                            "Thermal Extremes on the Trail: Rapidly cool heat exhaustion/stroke patients in shade with cold water, and gently rewarm hypothermic hikers after replacing wet clothing with dry insulation.",
                        ],
                    },
                    {
                        "title": "Heat Exhaustion vs. Heat Stroke Differential",
                        "layout": "DIFFERENTIAL_COMPARISON_2COL",
                        "comparison_data": {
                            "left_header": "Heat Exhaustion",
                            "left_badge": "URGENT FIELD CARE",
                            "left_points": [
                                "Skin Appearance: Cool, pale, moist, and clammy skin with heavy profuse sweating",
                                "Core Temp & Pulse: Core body temperature 98.6°F to 103°F; rapid weak pulse and muscle cramps",
                                "Mental Status: Alert and oriented, but experiencing dizziness, nausea, headache, and fatigue",
                                "Field Treatment: Move to shade, loosen clothing, fan skin, and give small sips of cool electrolyte water",
                            ],
                            "right_header": "Heat Stroke (Call 911)",
                            "right_badge": "LIFE-THREATENING",
                            "right_points": [
                                "Skin Appearance: Hot, flushed red skin (dry or damp from exertion) with failed thermoregulation",
                                "Core Temp & Pulse: Core body temperature above 104°F (40°C); rapid bounding pulse transitioning to weak",
                                "Mental Status: Altered mental state including confusion, combativeness, seizures, or unconsciousness",
                                "Emergency Action: Call 911 immediately; rapid cold-water immersion or ice packs at neck, armpits, and groin",
                            ],
                        },
                        "bullets": [
                            "Heat Exhaustion: Cool clammy skin, heavy sweating, alert mental status -> shade, fan, and oral electrolytes.",
                            "Heat Stroke (>104°F): Altered mental status/confusion, hot skin -> call 911 and rapid cold-water cooling immediately.",
                        ],
                    },
                    {
                        "title": "Hypothermia ('The UMBLES') & Wilderness Shade/Wind Shelters",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p058_img1.png",
                        "caption": "Scouts rigging an improvised tarp shade shelter and providing cool water to treat a hiker with heat exhaustion.",
                        "bullets": [
                            "Hypothermia Signals ('UMBLES'): Uncontrollable shivering, fumbles, stumbles, mumbles, and grumbles as core temp drops below 95°F.",
                            "Severe Hypothermia Danger: When core temperature drops below 90°F, shivering stops, muscles stiffen, and cardiac arrhythmia risk rises—handle gently!",
                            "Hypothermia Wrap Protocol: Pitch shelter out of wind, strip wet cotton clothes, wrap Scout in a dry sleeping bag over two foam pads, and place warm water bottles at armpits/groin.",
                            "Warm Sweet Liquids (Conscious Only): Offer warm broth, cocoa, or electrolyte water ONLY if the Scout is alert and able to hold the cup and swallow safely.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout distinguishes Heat Exhaustion from Heat Stroke across all 4 clinical criteria and explains hypothermia prevention and rewarming.",
            },
            {
                "req_id": "12",
                "req_number": "12",
                "topic_title": "Req 12: Mental Health First Aid & Supportive Listening",
                "action_verb": "Discuss",
                "req_text": "Mental Health Emergencies. Discuss with your counselor what mental health is, why Scouts might experience stress or anxiety on an outing, situations where professional help is needed, and how to support a friend and seek adult help.",
                "safety_callout": "If a Scout or friend expresses thoughts of self-harm or severe hopelessness, never keep it a secret—stay with them, tell a trusted adult leader immediately, and call or text 988.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "CONCEPT_TEXT_SLIDE",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_excerpts": [
                    "Mental Health Parity (Req 12a): Emotional and psychological well-being is just as vital as physical health; everyone experiences stress, grief, or anxiety at times.",
                    "Campout & Outing Stressors (Req 12b): Homesickness, exhaustion, dehydration, conflict, or challenging weather on a trek can trigger acute stress or panic attacks.",
                    "Warning Signs for Professional Help (Req 12c): Persistent sadness, sudden withdrawal from friends, panic attacks, or any talk of self-harm require immediate adult and professional support.",
                    "Active Listening & 988 Lifeline (Req 12d): Listen calmly without judgment, reassure your buddy they are not alone, involve an adult leader/parent immediately, and utilize the 988 Suicide & Crisis Lifeline.",
                ],
                "step_by_step_procedure": [
                    "Notice Behavioral Changes: Watch for a buddy withdrawing from patrol meals, struggling to sleep, hyperventilating, or expressing hopelessness.",
                    "Listen Without Judgment: Move to a calm, quiet spot with Two-Deep visibility, ask 'How can I help right now?', and listen empathetically.",
                    "Ground & Reassure: For acute anxiety or hyperventilation, guide slow 'box breathing' (inhale 4 sec, hold 4 sec, exhale 4 sec) and offer water.",
                    "Involve Trusted Adults & 988: Never promise to keep safety concerns secret; bring in the Scoutmaster, parent, counselor, or call/text 988.",
                ],
                "worked_example": {
                    "title": "Mental Health First Aid Action Plan (ALGEE / Buddy Support Model)",
                    "artifact_type": "SUPPORT PROTOCOL",
                    "fields": {
                        "1. Approach & Assess": "Check in privately and kindly with your buddy when you notice uncharacteristic silence, tearfulness, or panic",
                        "2. Listen Nonjudgmentally": "Validate their feelings ('It makes sense you feel overwhelmed right now') instead of dismissing them",
                        "3. Give Reassurance & Grounding": "Help them slow their breathing, warm up, hydrate, and know the patrol supports them",
                        "4. Connect to Adult & Professional Help": "Walk together to the Scoutmaster/adult leader or contact a parent, school counselor, or 988 Lifeline",
                    },
                    "counselor_tip": "Remind Scouts that asking for help for yourself or a buddy is a sign of courage and exemplifies 'A Scout is Brave, Kind, and Helpful.'",
                },
                "counselor_signoff_criteria": "Scout discusses all four parts of Requirement 12 (12a–12d), including campout stressors, warning signs, supportive listening, and connecting to adult/professional help.",
            },
            {
                "req_id": "13",
                "req_number": "13",
                "topic_title": "Req 13: Miscellaneous Conditions: Eye, Tooth, GI & Stroke (FAST)",
                "action_verb": "Describe",
                "req_text": "Miscellaneous Conditions. Describe the symptoms and signs of, show first aid for, and explain prevention of: (a) Object in the eye, (b) Broken, chipped, loosened, or knocked out tooth, (c) Vomiting and diarrhea associated with food poisoning, (d) Abdominal pain, and (e) Stroke.",
                "safety_callout": "Never rub an eye with a foreign object, never touch the root of a knocked-out permanent tooth, never give food or laxatives for acute abdominal pain, and call 911 immediately if FAST stroke signs appear.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/ai_illustrations/first_aid_stroke_fast_seizure_visual.png",
                "pamphlet_excerpts": [
                    "Object in the Eye (Req 13a): Flush loose grit from the inner corner outward with clean running water or saline; stabilize any impaled eye object with a paper cup and bandage both eyes.",
                    "Dental Emergencies (Req 13b): Pick up a knocked-out permanent tooth by the crown only (never touch the root!), rinse gently with milk/saline, transport in cold milk or Save-A-Tooth solution, and see a dentist within 30–60 minutes.",
                    "Food Poisoning & Dehydration (Req 13c): Prevent with strict camp handwashing, 40°F–140°F cold-chain storage, and 3-pot sanitation; treat vomiting/diarrhea with small frequent sips of oral rehydration salts.",
                    "Acute Abdominal Pain & Stroke FAST (Reqs 13d–13e): For severe abdominal pain, keep resting and give nothing by mouth; for stroke, run the FAST check (Face drooping, Arm weakness, Speech slurring, Time to call 911).",
                ],
                "step_by_step_procedure": [
                    "Irrigate or Shield the Eye: Flush loose specks under gentle running water; cover impaled eye objects with a protective paper cup without pressure.",
                    "Preserve Knocked-Out Tooth: Hold by the white crown, place in cold milk or balanced salt solution, and transport to a dentist immediately.",
                    "Manage GI & Abdominal Pain: Rehydrate food-poisoning patients with small sips of electrolyte water; give nothing by mouth if surgical abdominal pain (appendicitis) is suspected.",
                    "Run Stroke FAST Check: Ask the person to smile (Face), raise both arms (Arms), and repeat a simple phrase (Speech); call 911 immediately (Time).",
                ],
                "topic_slides": [
                    {
                        "title": "Stroke Recognition (FAST Protocol) & Emergency Response (Req 13e)",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/ai_illustrations/first_aid_stroke_fast_seizure_visual.png",
                        "caption": "Neurological Emergency Care: (Left) Performing the FAST stroke check for facial droop and unilateral arm drift; (Right) Protecting a patient in the side-lying recovery position with a padded jacket under the head.",
                        "bullets": [
                            "Stroke FAST Protocol (Req 13e): Check Face drooping, Arm drift/weakness, and Speech slurring; note the exact Time symptoms started and call 911 immediately.",
                        ],
                    },
                    {
                        "title": "Foreign Object in the Eye, Dental Trauma & Abdominal Pain (Reqs 13a–13d)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/first_aid_p067_img5.png",
                        "caption": "Flushing an eye under a gentle stream of clean running water to rinse away a chemical splash or foreign speck.",
                        "bullets": [
                            "Object in the Eye (Req 13a): Never rub the eye; flush loose dust with clean water from the nose side outward, or tape a paper cup over an impaled object.",
                            "Knocked-Out or Broken Tooth (Req 13b): Handle by the chewing crown only, rinse gently, store in cold milk or Save-A-Tooth solution, and reach a dentist within 30–60 minutes.",
                            "Food Poisoning Vomiting & Diarrhea (Req 13c): Prevent with USDA cooking temperatures and ice-packed coolers; replace fluids with small sips of oral rehydration solution.",
                            "Acute Abdominal Pain (Req 13d): Have the patient rest comfortably; NEVER give food, water, or laxatives, which can rupture an inflamed appendix.",
                        ],
                    },
                    {
                        "title": "Four-Step Miscellaneous Emergency Protocol",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Irrigate or Shield the Eye: Flush loose specks under gentle running water; cover impaled eye objects with a protective paper cup without pressure.",
                            "Preserve Knocked-Out Tooth: Hold by the white crown, place in cold milk or balanced salt solution, and transport to a dentist immediately.",
                            "Manage GI & Abdominal Pain: Rehydrate food-poisoning patients with small sips of electrolyte water; give nothing by mouth if surgical abdominal pain (appendicitis) is suspected.",
                            "Run Stroke FAST Check: Ask the person to smile (Face), raise both arms (Arms), and repeat a simple phrase (Speech); call 911 immediately (Time).",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout explains signs, prevention, and first aid for eye objects, knocked-out teeth, food poisoning, acute abdominal pain, and stroke (FAST).",
            },
            {
                "req_id": "14",
                "req_number": "14",
                "topic_title": "Req 14: Teaching First Aid with the BSA EDGE Method",
                "action_verb": "Teach",
                "req_text": "Teach another Scout a first-aid skill selected by your counselor using the BSA EDGE method (Explain, Demonstrate, Guide, Enable).",
                "safety_callout": "Supervise learner practice closely during the Guide phase so tourniquets or splints are never over-tightened on a live buddy.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Explain, Demonstrate, Guide & Enable",
                "recommended_archetype": "STEP_BY_STEP_PROCEDURE_4CARD",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_excerpts": [
                    "1. Explain Phase: Clearly state what the first-aid skill is, when it is needed, the safety rules (PPE gloves), and the sequence of steps.",
                    "2. Demonstrate Phase: Perform the skill smoothly at half-speed using real bandages, splints, or a manikin while narrating each checkpoint.",
                    "3. Guide Phase: Coach the learner as they practice the skill hands-on, offering positive feedback and correcting hand placement or knot tension.",
                    "4. Enable Phase: Have the learner perform the complete first-aid skill independently in a realistic scenario to prove mastery.",
                ],
                "step_by_step_procedure": [
                    "Explain (The 'Why' & 'What'): Introduce the injury scenario, universal precautions, and each step of the procedure in clear terms.",
                    "Demonstrate (Show How): Model the complete first-aid technique step-by-step using real dressings or splints while the learner watches.",
                    "Guide (Coach Practice): Hand the supplies to the learner and coach them through the skill, checking CMS circulation or compression depth.",
                    "Enable (Independent Mastery): Present a realistic trail scenario and verify the learner can execute the skill solo from start to finish.",
                ],
                "worked_example": {
                    "title": "Sample EDGE Lesson Plan — Teaching Forearm Splinting & Cravat Sling",
                    "artifact_type": "EDGE LESSON PLAN",
                    "fields": {
                        "Explain (3 mins)": "Explain why we splint a fracture 'where it lies', why we immobilize wrist + elbow, and how to check distal CMS",
                        "Demonstrate (4 mins)": "Show pre-splint CMS check, padding a SAM splint, tying cravat square knots, and tying an off-center arm sling",
                        "Guide (5 mins)": "Have the younger Scout apply the padded splint and sling on a buddy while coaching knot placement and padding",
                        "Enable (3 mins)": "Give a simulated trail fall scenario and let the Scout complete pre-CMS, splint, sling, swath, and post-CMS solo",
                    },
                    "counselor_tip": "Have each candidate pick one hands-on skill (such as figure-eight ankle wrap, forearm splint, or direct pressure bandage) and teach it to a buddy in class.",
                },
                "counselor_signoff_criteria": "Scout prepares an EDGE lesson plan and teaches a counselor-selected first-aid skill to another Scout using Explain, Demonstrate, Guide, and Enable.",
            },
            {
                "req_id": "15",
                "req_number": "15",
                "topic_title": "Req 15: Emergency Medical, Nursing & Rescue Careers",
                "action_verb": "Discuss",
                "req_text": "Emergency Medical Careers. Do ONE of the following: (a) Visit an emergency medical station or interview an EMS professional, OR (b) Explore three career opportunities in emergency medicine or first aid and discuss the education, training, expenses, career advancement, and why one profession interests you.",
                "safety_callout": "Follow Youth Protection Two-Deep Leadership and parental accompaniment rules when visiting an EMS station or interviewing a healthcare professional.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "WORKED_EXAMPLE_TEMPLATE",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_excerpts": [
                    "EMT & Paramedic Pathway: Emergency Medical Technicians (150–200 hours + NREMT exam) and Paramedics (1,200–1,800 hours + Associate degree) deliver pre-hospital trauma and cardiac care.",
                    "Wilderness Medicine & Search and Rescue (SAR): Wilderness EMTs (WEMT) and National Park Service rescue rangers combine technical rope/mountain rescue with extended backcountry medicine.",
                    "Emergency Room Nurse (CEN) & Physician (MD/DO): ER nurses (BSN + NCLEX) and board-certified Emergency Physicians lead hospital trauma bays and medical control.",
                    "Lifelong Readiness in Scouting: Earning CPR/AED, Wilderness First Aid (WFA), or Wilderness First Responder (WFR) certifications prepares Scouts for high-adventure treks and healthcare careers.",
                ],
                "step_by_step_procedure": [
                    "Compare Three EMS Roles: Research the daily duties of an EMT/Paramedic, Wilderness Rescue Medic, and Emergency Department Nurse or Physician.",
                    "Map Education & Licensing: List required coursework, clinical/field internship hours, and national registry board exams (NREMT, NCLEX, USMLE).",
                    "Estimate Training Expenses: Calculate community college or university tuition, lab fees, textbooks, stethoscope/uniforms, and certification renewal costs.",
                    "Evaluate Career Progression: Trace advancement opportunities from entry-level responder to Flight Paramedic, Nurse Practitioner, or EMS Medical Director.",
                ],
                "worked_example": {
                    "title": "Requirement 15b Career Research Comparison — Paramedic, ER Nurse & Wilderness Medic",
                    "artifact_type": "CAREER RESEARCH PROFILE",
                    "fields": {
                        "1. Firefighter / Paramedic": "EMT-B certification + 1–2 year CAAHEP Paramedic program (1,200+ clinical/field hours) + NREMT exam ($4,000–$12,000 tuition)",
                        "2. Trauma / Emergency Nurse (RN)": "4-year Bachelor of Science in Nursing (BSN) + NCLEX-RN license + Trauma Nursing Core Course (TNCC)",
                        "3. Search & Rescue / WEMT": "EMT-Basic + 160-hour Wilderness EMT module + technical rope, swiftwater, and avalanche rescue certifications",
                        "Advancement & Calling": "Progress to Critical Care Flight Paramedic, Nurse Practitioner, or Emergency Physician while living the Scout Oath daily",
                    },
                    "counselor_tip": "Encourage Scouts age 14+ to take the 16-hour BSA-approved Wilderness First Aid (WFA) course required for Philmont, Northern Tier, Sea Base, and Summit Bechtel Reserve.",
                },
                "counselor_signoff_criteria": "Scout reports on an EMS station visit/interview (15a) OR presents career research on emergency medical professions covering training, costs, advancement, and personal interest (15b).",
            },
        ],
    },
    "Camping": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Camping.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/camping/",
        "requirements": [
            {
                "req_id": "1a",
                "req_number": "1a",
                "parent_id": "1",
                "action_verb": "Explain",
                "req_text": "Show that you know first aid for and how to prevent injuries or illnesses that could occur while camping, including hypothermia, frostbite, heat reactions, dehydration, altitude sickness, and the 3-layer cold-weather clothing system.",
                "safety_callout": "Check the BSA Guide to Safe Scouting for hazardous weather policies and remember 'Cotton Kills' in wet or cold backcountry conditions.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "clothing_layering_3layer",
                "pamphlet_excerpts": [
                    "Wicking Base Layer: Synthetic polyester, polypropylene, or merino wool pulls sweat away from skin to prevent evaporative chilling.",
                    "Insulating Middle Layer: High-loft fleece or compressible down/synthetic puffer traps warm dead-air pockets around the torso.",
                    "Weatherproof Outer Shell: Breathable waterproof membrane (Gore-Tex/coated nylon) blocks wind and rain while venting vapor.",
                    "Why Cotton Kills: Cotton absorbs up to 27 times its weight in water, loses 90% of its thermal insulation when wet, and accelerates hypothermia.",
                ],
                "step_by_step_procedure": [
                    "Wear Synthetic Base: Start with moisture-wicking merino wool or polyester next to skin; ban cotton t-shirts, jeans, and socks.",
                    "Add Modular Fleece/Down: Layer fleece or synthetic insulation when resting in camp; shed layers before hiking uphill to avoid sweating.",
                    "Seal With Wind/Rain Shell: Don breathable waterproof jacket and rain pants at the first sign of wind-driven rain or sleet.",
                    "Protect Extremities: Pack a warm fleece beanie, insulated gloves, and dry sleeping socks dedicated exclusively to your sleeping bag.",
                ],
                "counselor_signoff_criteria": "Scout explains the Wicking-Insulating-Shell 3-layer system and prevention/treatment of backcountry hypothermia and altitude illness.",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Explain",
                "req_text": "Learn the Leave No Trace Seven Principles and the Outdoor Code, and exemplify them by creating a personal Leave No Trace action plan for an upcoming troop trek.",
                "safety_callout": "Always camp on durable surfaces at least 200 feet from lakes and streams to protect riparian ecosystems.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "WORKED_EXAMPLE_TEMPLATE",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_excerpts": [
                    "Plan Ahead and Prepare: Check trail regulations, group size limits, fire bans, and weather forecasts before leaving home.",
                    "Travel & Camp on Durable Surfaces: Concentrate tent pads on established gravel/dirt sites, rock, snow, or dry grasses.",
                    "Dispose of Waste Properly: Pack out all trash and food scraps; bury human waste in a 6-to-8-inch cathole at least 200 feet from water.",
                    "Outdoor Code Commitment: Be clean in outdoor manners, be careful with fire, be considerate in the outdoors, and be conservation-minded.",
                ],
                "worked_example": {
                    "title": "Personal Leave No Trace Trek Plan — Sierra High Country Weekend",
                    "artifact_type": "ACTION_PLAN",
                    "fields": {
                        "1. Plan Ahead & Prepare": "Repackage trail meals into reusable zip-top bags at home to eliminate cardboard trash in camp",
                        "2. Durable Surfaces": "Pitch patrol tents on established decomposed granite pads 200+ feet from Alpine Lake shoreline",
                        "3. Waste & Graywater": "Strain dishwater through fine mesh screen into trash bag; scatter soapy graywater 200 ft from water",
                        "4. Campfire Impact": "Cook 100% of meals on canister backpacking stoves during seasonal fire restrictions",
                    },
                    "counselor_tip": "Use the thumb trick for wildlife distance: extend your arm and hold up your thumb; if you cannot cover the animal, you are too close!",
                },
                "counselor_signoff_criteria": "Scout recites the Outdoor Code and 7 Leave No Trace Principles and presents a completed LNT trip plan.",
            },
            {
                "req_id": "3",
                "req_number": "3",
                "action_verb": "Demonstrate",
                "req_text": "Describe the features of a good campsite and demonstrate the 'Bear'-muda Triangle 200-foot backcountry layout separating sleeping tents, cooking/dining fly, and bear bag/canister storage.",
                "safety_callout": "Never store food, toothpaste, deodorant, or scented lip balm inside a sleeping tent; Check Upstairs for widowmaker dead branches before pitching.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "SPATIAL_FIELD_DIAGRAM",
                "visual_diagram_type": "bearmuda_triangle",
                "pamphlet_excerpts": [
                    "The 'Bear'-muda Triangle: Arrange Sleeping Tents, Cooking/Sump Area, and Bear Hang/Canister in an equilateral triangle spaced 200 feet apart.",
                    "Upwind Sleeping Zone: Pitch sleeping tents 200 feet upwind of the cooking and dishwashing area so food odors drift away from sleepers.",
                    "PCT Bear Bag Hang Dimensions: Hang smellables at least 12 feet above the ground, 6 feet out from the tree trunk, and 4 feet below the limb.",
                    "Overhead & Drainage Audit: Avoid dry washes, depressions, lone tall trees (lightning hazard), and overhead dead 'widowmaker' limbs.",
                ],
                "step_by_step_procedure": [
                    "Inspect Overhead & Ground: Look up for dead widowmaker branches and verify high, level, durable ground 200 feet from lakes/streams.",
                    "Pitch Upwind Tent Zone: Stake sleeping tents with doors facing away from prevailing wind over a properly tucked groundsheet.",
                    "Set Downwind Kitchen & Sump: Establish stove table and 3-pot dishwashing station 200 feet downwind of the sleeping tents.",
                    "Secure Smellables Apex: Hang bear bags (12 ft high, 6 ft from trunk) or place locked bear canisters 200 feet from both tents and kitchen.",
                ],
                "counselor_signoff_criteria": "Scout sketches and explains the 200-ft Bear-muda Triangle layout and demonstrates pitching a tent with taut guy lines.",
            },
            {
                "req_id": "4",
                "req_number": "4",
                "action_verb": "Prepare",
                "req_text": "Make a written plan for an overnight trek and show how to organize your patrol using a structured Weekend Campout Patrol Duty Roster.",
                "safety_callout": "Ensure Youth Protection Two-Deep Leadership and assign at least one buddy pair per duty rotation.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "WORKED_EXAMPLE_TEMPLATE",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_excerpts": [
                    "Equitable Task Rotation: Rotate Head Cook, Assistant Cook, Water/Fire Crew, and Cleanup/Sanitation Crew across every meal.",
                    "Patrol Leader Oversight: The Patrol Leader coordinates schedule transitions while the Quartermaster inspects stove and tent gear before departure.",
                    "Firem'n Chit & Totin' Chip: Only Scouts carrying valid Firem'n Chit and Totin' Chip credentials may manage stoves, fires, or camp tools.",
                    "Leave No Trace Sweep: Final Sunday morning duty rotation includes a shoulder-to-shoulder micro-trash police line across the entire site.",
                ],
                "worked_example": {
                    "title": "Weekend Campout Patrol Duty Roster — Pine Eagle Patrol (8 Scouts)",
                    "artifact_type": "DUTY_ROSTER",
                    "fields": {
                        "Saturday Breakfast": "Cooks: Scouts A & B | Water & Stove Prep: Scouts C & D | 3-Pot Dish Cleanup: Scouts E & F | Site & Bear Bag: Scouts G & H",
                        "Saturday Lunch (Trail)": "Cooks: Scouts C & D | Water Filtration: Scouts E & F | Trash & LNT Pack-Out: Scouts G & H | Navigation Lead: Scouts A & B",
                        "Saturday Dinner": "Cooks: Scouts E & F | Water & Dutch Oven: Scouts G & H | 3-Pot Dish Cleanup: Scouts A & B | Bear Canister Lock: Scouts C & D",
                        "Sunday Breakfast & Strike": "Cooks: Scouts G & H | Water & Gear Inspection: Scouts A & B | Final Cleanup: Scouts C & D | LNT Micro-Trash Sweep: All Patrol",
                    },
                    "counselor_tip": "Post the laminated Duty Roster inside the chuck box lid so every Scout knows their exact job before meal prep starts.",
                },
                "counselor_signoff_criteria": "Scout presents a completed Patrol Duty Roster and overnight trek logistics plan.",
            },
            {
                "req_id": "5",
                "req_number": "5",
                "action_verb": "Explain",
                "req_text": "Compare the advantages, limitations, cold-weather performance, and BSA safety rules of Isobutane Canister Stoves vs. White Gas Liquid Fuel Stoves.",
                "safety_callout": "Never light or operate any fuel stove inside or near a tent (carbon monoxide and flash fire hazard), and always require adult supervision per BSA chemical fuel policy.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "DIFFERENTIAL_COMPARISON_2COL",
                "visual_diagram_type": "stove_comparison",
                "pamphlet_excerpts": [
                    "BSA Chemical Fuel Policy: Compressed or liquid-gas stoves may be used only with knowledgeable adult supervision and never inside tents.",
                    "Vapor Pressure Physics: Isobutane/propane canisters lose vapor pressure below 20°F (-6°C), whereas pumped white gas works to -40°F.",
                    "Fuel Storage & Refueling: Allow liquid fuel stoves to cool completely before refueling at least 20 feet away from any open flame.",
                    "Simmer & Weight Tradeoffs: Upright canister stoves weigh 3 to 4 oz and light instantly; liquid fuel stoves excel at group melting of snow.",
                ],
                "comparison_data": {
                    "left_header": "Isobutane Canister Stove",
                    "left_badge": "3-SEASON ULTRALIGHT",
                    "left_points": [
                        "Ignition & Operation: Screw onto threaded Lindal valve, open control knob, and light immediately with no priming required",
                        "Weight & Packability: Ultralight burner (2.5 to 4 oz) nests directly inside a 750mL titanium or anodized aluminum trail mug",
                        "Cold-Weather Limit: Pressure drops sharply below 20°F (-6°C) as liquid isobutane fails to vaporize in freezing air",
                        "Maintenance & Waste: Zero field maintenance, but empty metal canisters must be packed out and recycled properly",
                    ],
                    "right_header": "White Gas Liquid Fuel Stove",
                    "right_badge": "4-SEASON EXPEDITION",
                    "right_points": [
                        "Ignition & Operation: Requires manual fuel bottle pumping (15 to 25 strokes) and pre-heating generator tube with priming paste/fuel",
                        "Weight & Stability: Low-center-of-gravity tripod base supports wide 4-liter patrol pots without tipping",
                        "Cold-Weather Mastery: Operates reliably down to -40°F for winter camping, snow melting, and high-altitude expeditions",
                        "Maintenance & Refill: Field-serviceable jets and O-rings; reusable aluminum fuel bottles reduce canister waste on long treks",
                    ],
                },
                "counselor_signoff_criteria": "Scout compares canister vs. liquid fuel stoves across weight, priming, cold-weather physics, and BSA chemical fuel safety rules.",
            },
            {
                "req_id": "6",
                "req_number": "6",
                "action_verb": "Demonstrate",
                "req_text": "Demonstrate three methods of backcountry water purification (rolling boil, 0.1-micron hollow-fiber filtration, and chlorine dioxide chemical treatment) and the BSA 3-pot camp dishwashing sanitation pipeline.",
                "safety_callout": "Untreated surface water may harbor Giardia lamblia, Cryptosporidium oocysts, and enteric bacteria; always sanitize dishes in Pot 3 before air-drying.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "STEP_BY_STEP_PROCEDURE_4CARD",
                "visual_diagram_type": "water_purification_pipeline",
                "pamphlet_excerpts": [
                    "Rolling Boil Gold Standard: Bringing water to a full rolling boil for 1 full minute kills 100% of bacteria, viruses, and protozoan cysts at any altitude.",
                    "Hollow-Fiber Microfiltration: 0.1 to 0.2 micron pore size physically blocks bacteria and Giardia/Cryptosporidium; protect filter cartridge from freezing.",
                    "Chlorine Dioxide Dwell Time: Chemical tablets kill viruses and bacteria in 15 to 30 minutes, but require a full 4-hour contact time for Cryptosporidium cysts.",
                    "Three-Pot Dishwashing Pipeline: Scrape food into trash -> Pot 1 Hot Wash with biodegradable soap -> Pot 2 Warm Clear Rinse -> Pot 3 Sanitize -> Air Dry.",
                ],
                "step_by_step_procedure": [
                    "Pre-Filter & Collect: Draw water upstream from camp and pre-filter sediment through a clean bandana into your dirty reservoir.",
                    "Purify Drinking Water: Boil at a rolling boil for 60 seconds, squeeze through a 0.1-micron filter, or dose with chlorine dioxide.",
                    "Run 3-Pot Dish Line: Scrape plates clean, wash in Pot 1 (hot soapy), rinse in Pot 2 (clear warm), and immerse in Pot 3 (sanitizer).",
                    "Air Dry & Sump Straining: Hang mesh dunk bags to air-dry (never use a dirty dish towel) and strain graywater before scattering 200 ft from water.",
                ],
                "counselor_signoff_criteria": "Scout demonstrates operating a backpacking water filter and sets up the 3-pot dishwashing sanitation line.",
            },
            {
                "req_id": "9a",
                "req_number": "9a",
                "parent_id": "9",
                "action_verb": "Camp",
                "req_text": "Camp a total of at least 20 nights at designated Scouting activities or events (one long-term camp experience of up to six consecutive nights may be applied toward this requirement), sleeping each night under the sky or in a tent you have pitched.",
                "safety_callout": "All overnight Scouting camping requires Two-Deep Adult Leadership, Youth Protection compliance, and age-appropriate tenting accommodations.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "edge_phase": "Enable",
                "recommended_archetype": "GEAR_CHECKLIST_GRID",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_excerpts": [
                    "20-Night Camping Standard: At least 14 nights must come from short-term weekend troop/patrol campouts; maximum 6 nights from one long-term resident summer camp.",
                    "Tent or Bivy Requirement: Every qualifying night must be spent sleeping in a tent you helped pitch or under the open stars (cabin nights do not count).",
                    "9b Adventure Options: Complete two adventure experiences such as a 4-hour 1,000-ft elevation hike, 15-mile bike trek, or 5-mile canoe trip.",
                    "9c Conservation Project: Perform a conservation project approved by the landowner or land management agency during a campout.",
                ],
                "gear_checklist": [
                    "Scoutbook Camping Log export showing >= 20 total qualifying tent/sky nights",
                    "Maximum 6 nights credited from a single long-term summer camp session",
                    "At least 14 nights from weekend troop/patrol overnight campouts",
                    "Documentation of two Requirement 9b outdoor adventure experiences",
                    "Documentation of Requirement 9c conservation project on campout",
                    "Scoutmaster or Unit Leader verification signature on camping log",
                ],
                "counselor_signoff_criteria": "Scout presents a signed Scoutbook Camping Log verifying 20+ qualifying nights plus completion of 9b and 9c.",
            },
        ],
    },
    "Citizenship in the Nation": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Citizenship%20in%20the%20Nation.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/citizenship-nation/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "topic_title": "Req 1: 14th Amendment, Constitutional Rights & Civic Duties",
                "action_verb": "Explain",
                "req_text": "What is the Constitution of the United States? What does the Constitution do? What principles does it reflect? Why is it important to have a Constitution? Explain what citizenship in the nation means, the 14th Amendment, and the duties and responsibilities of U.S. citizens.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "fourteenth_amendment_shield",
                "pamphlet_image_path": "assets/ai_illustrations/citizenship_in_the_nation_14th_amendment_visual.png",
                "pamphlet_excerpts": [
                    "14th Amendment Citizenship Clause: 'All persons born or naturalized in the United States, and subject to the jurisdiction thereof, are citizens of the United States and of the State wherein they reside.'",
                    "Due Process Clause: Prohibits federal, state, and local governments from depriving any person of life, liberty, or property without fair legal procedures.",
                    "Equal Protection Clause: Guarantees that every person within a jurisdiction receives equal treatment under the law regardless of race, religion, or origin.",
                    "Civic Obligations vs. Responsibilities: Obeying laws, paying taxes, serving on a jury, and Selective Service registration are mandatory duties; voting and community service are vital responsibilities.",
                ],
                "step_by_step_procedure": [
                    "Birthright & Naturalization: Acquire citizenship by birth on U.S. soil (jus soli), citizen parentage (jus sanguinis), or USCIS naturalization.",
                    "Exercise Constitutional Rights: Practice freedom of speech, press, religion, assembly, and petition while respecting others' rights.",
                    "Fulfill Legal Obligations: Obey federal/state/local laws, pay taxes honestly, and serve on a trial jury when summoned.",
                    "Participate in Self-Government: Stay informed on public issues, vote in elections, and serve your community through Scouting.",
                ],
                "topic_slides": [
                    {
                        "title": "Constitutional Rule of Law & Equal Justice",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/citizenship_in_the_nation_p005_img1.png",
                        "caption": "Wooden courtroom gavel and sound block symbolizing constitutional rule of law and equal justice.",
                        "bullets": [
                            "Four Pillars of the 14th Amendment: Birthright & Naturalized Citizenship, Privileges or Immunities, Due Process of Law, and Equal Protection under the Law.",
                        ],
                    },
                    {
                        "title": "Six Core Principles of the U.S. Constitution",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/citizenship_in_the_nation_p005_img2.png",
                        "caption": "Uniformed Scout standing before the U.S. Capitol dome in Washington, D.C.",
                        "bullets": [
                            "Popular Sovereignty: Government authority flows directly from 'We the People' through free and fair elections.",
                            "Limited Government & Rule of Law: Public officials are bound by written constitutional limits; nobody is above the law.",
                            "Separation of Powers & Checks: Legislative, Executive, and Judicial powers are divided so no single branch can become tyrannical.",
                            "Federalism & Individual Rights: Power is shared between national and state governments while the Bill of Rights protects personal liberty.",
                        ],
                    },
                    {
                        "title": "Mandatory Civic Duties vs. Civic Responsibilities",
                        "layout": "DIFFERENTIAL_COMPARISON_2COL",
                        "comparison_data": {
                            "left_header": "Mandatory Legal Duties",
                            "left_badge": "REQUIRED BY LAW",
                            "left_points": [
                                "Obeying Laws: Follow federal, state, and municipal statutes enacted by elected representatives",
                                "Paying Taxes Honestly: Fund national defense, courts, highways, and public schools through federal/state taxes",
                                "Serving on a Jury: Guarantee the Sixth and Seventh Amendment right to an impartial trial by peers when summoned",
                                "Defending the Nation: Register with the Selective Service System at age 18 as required by federal statute",
                            ],
                            "right_header": "Voluntary Civic Responsibilities",
                            "right_badge": "ACTIVE CITIZENSHIP",
                            "right_points": [
                                "Informed Voting: Research candidates and ballot measures and vote in local, state, and federal elections",
                                "Respecting Others' Rights: Safeguard free speech, religious liberty, and equal dignity for all neighbors",
                                "Community & Scouting Service: Volunteer in conservation, food banks, civic boards, and Eagle Scout projects",
                                "Public Engagement: Contact elected representatives, attend town halls, and stay informed via credible news",
                            ],
                        },
                        "bullets": [
                            "Legal Duties: Obeying laws, paying taxes, jury duty, and Selective Service registration.",
                            "Civic Responsibilities: Voting, staying informed, volunteering, and respecting the rights of others.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout explains the Constitution's core principles, the 14th Amendment definition of citizenship, and civic duties vs. responsibilities.",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "topic_title": "Req 2: Six Functions of Government in the Preamble",
                "action_verb": "List",
                "req_text": "List the six functions of government as noted in the Preamble to the United States Constitution. Discuss with your counselor how these functions affect your family and local community.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/citizenship_in_the_nation_p006_img1.png",
                "pamphlet_excerpts": [
                    "1. Form a More Perfect Union: Unite the individual states under one cohesive national framework for commerce, currency, and interstate cooperation.",
                    "2. Establish Justice & 3. Insure Domestic Tranquility: Operate impartial federal courts and maintain civil peace, disaster response, and law enforcement.",
                    "4. Provide for the Common Defence: Maintain the U.S. Armed Forces and Coast Guard to protect the nation from external threats.",
                    "5. Promote the General Welfare & 6. Secure the Blessings of Liberty: Support public infrastructure, science, clean water, and constitutional rights for future generations.",
                ],
                "topic_slides": [
                    {
                        "title": "The Preamble's Six Purposes of Government",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/citizenship_in_the_nation_p006_img1.png",
                        "caption": "The Statue of Liberty raising her torch before the American flag as an emblem of constitutional liberty.",
                        "bullets": [
                            "Form a More Perfect Union: Binds 50 states together with a single currency, interstate highway network, and unified constitutional law.",
                            "Establish Justice: Creates an independent federal judiciary and guarantees due process and equal treatment in court.",
                            "Insure Domestic Tranquility: Preserves peace at home through law enforcement, National Guard disaster relief, and FEMA aid.",
                            "Provide for the Common Defence: Equips the Army, Navy, Air Force, Marine Corps, Space Force, and Coast Guard to defend the nation.",
                        ],
                    },
                    {
                        "title": "Providing for the Common Defense & General Welfare",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/citizenship_in_the_nation_p010_img1.png",
                        "caption": "Scouts examining a national defense and September 11 memorial exhibit on civic service and common defense.",
                        "bullets": [
                            "Common Defense & National Security: Protects citizens, borders, airspace, and maritime trade routes through the Armed Forces and Coast Guard.",
                            "National Guard & Disaster Response: Bridges federal and state readiness during hurricanes, floods, and wildfire emergencies.",
                            "Promote the General Welfare: Invests in interstate highways, clean water infrastructure, public health research, and national parks.",
                            "Secure the Blessings of Liberty: Preserves constitutional rights and self-government for present and future generations of Americans.",
                        ],
                    },
                    {
                        "title": "How the Six Preamble Functions Impact Your Community",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "Preamble Functions in Daily Family & Community Life",
                            "artifact_type": "CIVIC IMPACT MATRIX",
                            "fields": {
                                "Union & Justice": "Interstate highways, U.S. Postal Service delivery, and federal civil rights & court protections",
                                "Domestic Tranquility": "FEMA flood/wildfire disaster relief grants and National Weather Service severe storm warnings",
                                "Common Defence": "Active-duty Armed Forces, National Guard armories, and cybersecurity protection of critical utilities",
                                "General Welfare & Liberty": "National Parks & public lands where our Troop camps, clean air/water standards, and First Amendment freedoms",
                            },
                            "counselor_tip": "Ask each Scout to name one specific federal service their family used this week for each of the 6 Preamble goals.",
                        },
                        "bullets": [
                            "Union & Justice: Interstate highways, U.S. Postal Service delivery, and federal civil rights & court protections",
                            "Domestic Tranquility: FEMA flood/wildfire disaster relief grants and National Weather Service severe storm warnings",
                            "Common Defence: Active-duty Armed Forces, National Guard armories, and cybersecurity protection of critical utilities",
                            "General Welfare & Liberty: National Parks & public lands where our Troop camps, clean air/water standards, and First Amendment freedoms",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout recites or lists all 6 functions of government in the Preamble and gives concrete examples of how each affects their family and community.",
            },
            {
                "req_id": "3",
                "req_number": "3",
                "topic_title": "Req 3: Three Branches of Government & Checks and Balances",
                "action_verb": "Explain",
                "req_text": "Explain how our federal government is structured: (a) List the three branches of government and their functions, (b) Explain how the three branches check and balance each other, and (c) Describe how citizens can be involved in each branch.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "SPATIAL_FIELD_DIAGRAM",
                "visual_diagram_type": "checks_balances_triangle",
                "pamphlet_image_path": "assets/ai_illustrations/citizenship_in_the_nation_checks_balances_veto_visual.png",
                "pamphlet_excerpts": [
                    "Legislative Branch (Article I, Congress): Bicameral Senate (100 Senators) and House (435 Representatives) draft statutes, levy taxes, appropriate funds, and declare war.",
                    "Executive Branch (Article II, President & Cabinet): Enforces federal laws, commands the Armed Forces, negotiates treaties, and appoints federal officials.",
                    "Judicial Branch (Article III, Supreme Court & Federal Courts): Interprets the Constitution and exercises judicial review (Marbury v. Madison) over statutes and executive acts.",
                    "Reciprocal Checks & Balances: Congress can override a presidential veto by 2/3 vote in both chambers; the Senate confirms treaties and judicial nominees.",
                ],
                "step_by_step_procedure": [
                    "Legislative Check on Executive: Congress passes bills, controls the federal budget, ratifies treaties, and overrides vetoes by 2/3 vote.",
                    "Executive Check on Legislative: The President can veto congressional legislation and call special sessions of Congress.",
                    "Executive & Legislative on Judicial: The President nominates federal judges and Supreme Court Justices; the Senate confirms or rejects them.",
                    "Judicial Check on Both Branches: The Supreme Court reviews statutes and executive actions for constitutional compliance.",
                ],
                "quiz_item": {
                    "scenario_prompt": "If the President vetoes a bill passed by Congress, what constitutional check allows Congress to enact the bill into law anyway?",
                    "options": [
                        "A simple majority vote in the House of Representatives alone",
                        "A two-thirds (2/3) supermajority override vote in both the House and the Senate",
                        "An executive order signed by the Chief Justice of the Supreme Court",
                        "A national referendum signed by 10 state governors",
                    ],
                    "correct_answer": "A two-thirds (2/3) supermajority override vote in both the House and the Senate",
                    "explanation": "Under Article I, Section 7 of the U.S. Constitution, Congress can override a presidential veto if both chambers re-pass the bill by a two-thirds vote.",
                },
                "topic_slides": [
                    {
                        "title": "Constitutional Checks & Balances Across Three Branches",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/ai_illustrations/citizenship_in_the_nation_checks_balances_veto_visual.png",
                        "caption": "Constitutional Checks & Balances in Action: Presidential signature or veto power (left), Congressional legislative debate and override votes (center), and Supreme Court judicial review (right).",
                        "bullets": [
                            "Articles I, II, and III Architecture: By dividing lawmaking (Congress), law enforcement (President), and constitutional interpretation (Courts), the Framers prevented any single branch from seizing absolute power.",
                        ],
                    },
                    {
                        "title": "How Citizens Participate in All Three Branches",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/citizenship_in_the_nation_p025_img1.png",
                        "caption": "The U.S. Capitol building in Washington, D.C., seat of the bicameral Legislative Branch (Senate and House).",
                        "bullets": [
                            "Participating in the Legislative Branch: Vote for U.S. Senators and Representatives, testify at hearings, and write constituent letters.",
                            "Participating in the Executive Branch: Vote in presidential elections, submit public comments on agency rules (Regulations.gov), and serve in civil/military service.",
                            "Participating in the Judicial Branch: Serve honestly on federal trial or grand juries, serve as a witness, or file amicus curiae briefs.",
                            "First Amendment Petition Power: Every Scout and citizen has the constitutional right to petition any branch for a redress of grievances.",
                        ],
                    },
                    {
                        "title": "How the Three Branches Check & Balance Each Other",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Legislative Check on Executive: Congress passes bills, controls the federal budget, ratifies treaties, and overrides vetoes by 2/3 vote.",
                            "Executive Check on Legislative: The President can veto congressional legislation and call special sessions of Congress.",
                            "Executive & Legislative on Judicial: The President nominates federal judges and Supreme Court Justices; the Senate confirms or rejects them.",
                            "Judicial Check on Both Branches: The Supreme Court reviews statutes and executive actions for constitutional compliance.",
                        ],
                    },
                    {
                        "title": "Patrol Scenario: Overriding a Presidential Veto",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "scenario_prompt": "If the President vetoes a bill passed by Congress, what constitutional check allows Congress to enact the bill into law anyway?",
                            "options": [
                                "A simple majority vote in the House of Representatives alone",
                                "A two-thirds (2/3) supermajority override vote in both the House and the Senate",
                                "An executive order signed by the Chief Justice of the Supreme Court",
                                "A national referendum signed by 10 state governors",
                            ],
                            "correct_answer": "A two-thirds (2/3) supermajority override vote in both the House and the Senate",
                            "explanation": "Under Article I, Section 7 of the U.S. Constitution, Congress can override a presidential veto if both chambers re-pass the bill by a two-thirds vote.",
                        },
                        "bullets": [
                            "If the President vetoes a bill passed by Congress, what constitutional check allows Congress to enact the bill into law anyway?",
                            "A two-thirds (2/3) supermajority override vote in both the House and the Senate",
                            "Under Article I, Section 7 of the U.S. Constitution, Congress can override a presidential veto if both chambers re-pass the bill by a two-thirds vote.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout explains the functions of all 3 branches, traces reciprocal checks and balances, and explains citizen participation in each branch.",
            },
            {
                "req_id": "4",
                "req_number": "4",
                "topic_title": "Req 4: Declaration of Independence, Constitution & Bill of Rights",
                "action_verb": "Discuss",
                "req_text": "Discuss the importance of: (a) Declaration of Independence, (b) The Bill of Rights (the first 10 Amendments to the Constitution) and the 14th Amendment, and (c) the traditional United States motto 'E Pluribus Unum'.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "DIFFERENTIAL_COMPARISON_2COL",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/citizenship_in_the_nation_p023_img1.png",
                "pamphlet_excerpts": [
                    "Declaration of Independence (July 4, 1776): Drafted by Thomas Jefferson; proclaims unalienable rights to Life, Liberty, and the Pursuit of Happiness and consent of the governed.",
                    "The Bill of Rights (Ratified December 15, 1791): The first 10 Amendments added to protect individual civil liberties and reserve unenumerated powers to the states and people.",
                    "The 14th Amendment (1868): Incorporates the Bill of Rights against state governments and guarantees citizenship, due process, and equal protection to all persons.",
                    "E Pluribus Unum ('Out of Many, One'): Adopted on the Great Seal in 1782 to signify 13 diverse colonies—and people of many backgrounds—uniting as one Constitutional Republic.",
                ],
                "comparison_data": {
                    "left_header": "Declaration & 'E Pluribus Unum'",
                    "left_badge": "FOUNDING CHARTER",
                    "left_points": [
                        "Declaration of Independence (1776): Asserts universal human equality and natural rights that no ruler can take away",
                        "Consent of the Governed: Establishes that legitimate power comes from the citizens",
                        "E Pluribus Unum ('Out of Many, One'): Traditional Latin motto on the Great Seal and U.S. coinage since 1782",
                        "Civic Unity: Celebrates how 50 states and diverse Americans unite around shared constitutional ideals",
                    ],
                    "right_header": "Bill of Rights & 14th Amendment",
                    "right_badge": "CIVIL LIBERTIES",
                    "right_points": [
                        "1st Amendment Five Freedoms: Protects freedom of religion, speech, press, peaceable assembly, and petition",
                        "4th to 8th Due Process Protections: Bans unreasonable searches, double jeopardy, forced self-incrimination, and cruel punishment",
                        "9th & 10th Amendments: Reserves unenumerated rights to the people and non-delegated powers to the states",
                        "14th Amendment Incorporation: Extends Bill of Rights protections to apply against state and local governments",
                    ],
                },
                "topic_slides": [
                    {
                        "title": "Charters of Freedom: Declaration, Constitution & Bill of Rights",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/citizenship_in_the_nation_p023_img1.png",
                        "caption": "Continental Congress delegates presenting the draft Declaration of Independence at Independence Hall in 1776.",
                        "bullets": [
                            "How the Charters Work Together: The Declaration of Independence states our moral promise of equality and natural rights; the Constitution and Bill of Rights turn that promise into enforceable supreme law.",
                        ],
                    },
                    {
                        "title": "Enduring Symbols of Liberty & Living Amendments",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/citizenship_in_the_nation_p008_img1.png",
                        "caption": "The historic Liberty Bell displayed beneath the U.S. flag at Independence National Historical Park in Philadelphia.",
                        "bullets": [
                            "Article V Amendment Process: Proposed by 2/3 of both houses of Congress (or 2/3 of state conventions) and ratified by 3/4 (38) of the states.",
                            "Reconstruction Amendments (13th-15th): Abolished slavery (13th), guaranteed equal citizenship (14th), and banned racial voting denial (15th).",
                            "Expanding the Franchise (19th, 24th, 26th): Guaranteed women's suffrage (19th, 1920), banned poll taxes (24th, 1964), and lowered voting age to 18 (26th, 1971).",
                            "Life Without These Documents: Without written rights and independent courts, minority viewpoints and personal liberties would have no legal shield.",
                        ],
                    },
                    {
                        "title": "Founding Ideals vs. Enforceable Constitutional Rights",
                        "layout": "DIFFERENTIAL_COMPARISON_2COL",
                        "comparison_data": {
                            "left_header": "Declaration & 'E Pluribus Unum'",
                            "left_badge": "FOUNDING CHARTER",
                            "left_points": [
                                "Declaration of Independence (1776): Asserts universal human equality and natural rights that no ruler can take away",
                                "Consent of the Governed: Establishes that legitimate power comes from the citizens",
                                "E Pluribus Unum ('Out of Many, One'): Traditional Latin motto on the Great Seal and U.S. coinage since 1782",
                                "Civic Unity: Celebrates how 50 states and diverse Americans unite around shared constitutional ideals",
                            ],
                            "right_header": "Bill of Rights & 14th Amendment",
                            "right_badge": "CIVIL LIBERTIES",
                            "right_points": [
                                "1st Amendment Five Freedoms: Protects freedom of religion, speech, press, peaceable assembly, and petition",
                                "4th to 8th Due Process Protections: Bans unreasonable searches, double jeopardy, forced self-incrimination, and cruel punishment",
                                "9th & 10th Amendments: Reserves unenumerated rights to the people and non-delegated powers to the states",
                                "14th Amendment Incorporation: Extends Bill of Rights protections to apply against state and local governments",
                            ],
                        },
                        "bullets": [
                            "Declaration & E Pluribus Unum: Natural rights, consent of the governed, and 'Out of Many, One' national unity.",
                            "Bill of Rights & 14th Amendment: Enforceable civil liberties, due process, and equal protection across all 50 states.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout explains the Declaration of Independence, Bill of Rights, 14th Amendment, and 'E Pluribus Unum' and how American life depends on them.",
            },
            {
                "req_id": "5",
                "req_number": "5",
                "topic_title": "Req 5: Five-Day National News Tracking & Community Impact",
                "action_verb": "Discuss",
                "req_text": "Watch the national evening news for five days in a row on television, or read the main stories on the front page of a daily newspaper or a national news website for five days in a row. Discuss the national issues that you learned about with your counselor and how one issue affects your family and community.",
                "safety_callout": None,
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "WORKED_EXAMPLE_TEMPLATE",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/citizenship_in_the_nation_p040_img1.png",
                "pamphlet_excerpts": [
                    "Media Literacy & Primary Sources: Distinguish verifiable factual reporting and official roll-call votes from editorial commentary and opinion columns.",
                    "Constitutional Branch Tracking: Identify whether each national story involves Congress (legislation/oversight), the Executive (agency action/foreign policy), or the Federal Courts.",
                    "Local & Family Impact Analysis: Trace how federal decisions on infrastructure, energy, disaster relief, or interest rates directly affect your hometown.",
                    "Five-Day Continuity: Following major stories across five consecutive days reveals how public debate, committee hearings, and checks and balances unfold.",
                ],
                "worked_example": {
                    "title": "5-Day National News Tracking Log (Worked Example)",
                    "artifact_type": "BUDGET_LOG",
                    "fields": {
                        "Day 1-2 Headlines": "Federal Highway & Bridge Modernization Funding Bill debated in Senate Transportation Committee",
                        "Day 3-4 Headlines": "National Weather Service & FEMA update wildfire mitigation grants for Western forest communities",
                        "Day 5 Headline": "U.S. Supreme Court hears oral arguments on Fourth Amendment digital privacy protections",
                        "Selected Deep-Dive Issue": "Wildfire Mitigation Grants: Directly funds brush clearance in our local county watershed and protects our troop's summer camp",
                    },
                    "counselor_tip": "Bring your 5-day dated log to class showing the news source, date, headline summary, and which branch of government is acting.",
                },
                "topic_slides": [
                    {
                        "title": "How Informed Citizens Track National News",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/citizenship_in_the_nation_p040_img1.png",
                        "caption": "Scout reading a daily print newspaper to track national front-page news over five consecutive days.",
                        "bullets": [
                            "Free Press & Self-Government: The First Amendment protects an independent press so citizens can hold elected officials accountable.",
                            "Fact vs. Editorial Opinion: Verify straight news reporting against primary documents (bill text on Congress.gov or Supreme Court opinions).",
                            "Cross-Checking Perspectives: Compare how multiple reputable national news outlets report the same policy debate.",
                            "Connecting National to Local: Ask how a federal budget bill, agency regulation, or court ruling affects your school, family, or troop.",
                        ],
                    },
                    {
                        "title": "Worked Example: 5-Day National News Log",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "5-Day National News Tracking Log (Worked Example)",
                            "artifact_type": "BUDGET_LOG",
                            "fields": {
                                "Day 1-2 Headlines": "Federal Highway & Bridge Modernization Funding Bill debated in Senate Transportation Committee",
                                "Day 3-4 Headlines": "National Weather Service & FEMA update wildfire mitigation grants for Western forest communities",
                                "Day 5 Headline": "U.S. Supreme Court hears oral arguments on Fourth Amendment digital privacy protections",
                                "Selected Deep-Dive Issue": "Wildfire Mitigation Grants: Directly funds brush clearance in our local county watershed and protects our troop's summer camp",
                            },
                            "counselor_tip": "Bring your 5-day dated log to class showing the news source, date, headline summary, and which branch of government is acting.",
                        },
                        "bullets": [
                            "Day 1-2 Headlines: Federal Highway & Bridge Modernization Funding Bill debated in Senate Transportation Committee",
                            "Day 3-4 Headlines: National Weather Service & FEMA update wildfire mitigation grants for Western forest communities",
                            "Day 5 Headline: U.S. Supreme Court hears oral arguments on Fourth Amendment digital privacy protections",
                            "Selected Deep-Dive Issue: Wildfire Mitigation Grants: Directly funds brush clearance in our local county watershed and protects our troop's summer camp",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout presents a 5-day consecutive national news log and analyzes how one national issue impacts their family and community.",
            },
            {
                "req_id": "6",
                "req_number": "6",
                "topic_title": "Req 6: Historic American Speeches & National Unity",
                "action_verb": "Choose",
                "req_text": "Choose a speech of national historical importance, find out about the author, describe the historical situation at the time it was given, explain how it united Americans or advanced constitutional ideals, and explain how it applies to American citizens today.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/citizenship_in_the_nation_p012_img1.png",
                "pamphlet_excerpts": [
                    "Washington's Farewell Address (1796): Warned against geographical sectionalism, hyper-partisan factions, and permanent foreign entanglements while urging fidelity to the Constitution.",
                    "Lincoln's Gettysburg Address (November 19, 1863): In 272 words, redefined the Civil War as a test of whether a nation 'conceived in Liberty, and dedicated to the proposition that all men are created equal' can endure.",
                    "FDR's Four Freedoms (1941) & JFK's Inaugural (1961): Articulated universal human freedoms and called on citizens to 'ask not what your country can do for you—ask what you can do for your country.'",
                    "Dr. Martin Luther King Jr.'s 'I Have a Dream' (August 28, 1963): Called on America to honor the 'promissory note' of the Declaration and Constitution for citizens of every race.",
                ],
                "topic_slides": [
                    {
                        "title": "Abraham Lincoln & The Gettysburg Address (1863)",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/citizenship_in_the_nation_p012_img1.png",
                        "caption": "Scout with merit badge sash standing before the statue of Abraham Lincoln inside the Lincoln Memorial.",
                        "bullets": [
                            "Words That Redefined the Nation: Great American speeches anchor moments of national crisis back to the founding promises of the Declaration of Independence and the U.S. Constitution.",
                        ],
                    },
                    {
                        "title": "Landmark Speeches That Advanced Constitutional Ideals",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/citizenship_in_the_nation_p050_img1.png",
                        "caption": "The Stone of Hope statue at the Martin Luther King Jr. Memorial on the National Mall in Washington, D.C.",
                        "bullets": [
                            "George Washington's Farewell Address (1796): Urged Americans to place national union and constitutional law above regional or partisan rivalry.",
                            "Abraham Lincoln's Gettysburg Address (1863): Dedicated the nation to a 'new birth of freedom' so 'government of the people, by the people, for the people, shall not perish.'",
                            "John F. Kennedy's Inaugural Address (1961): Challenged a new generation of Americans to active civic service and defense of liberty.",
                            "Dr. Martin Luther King Jr.'s 'I Have a Dream' (1963): Appealed to the Declaration's unalienable rights to unite Americans around civil rights and equal justice.",
                        ],
                    },
                    {
                        "title": "Worked Example: Analyzing the Gettysburg Address",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "Historic Speech Analysis — Lincoln's Gettysburg Address (1863)",
                            "artifact_type": "SPEECH ANALYSIS GUIDE",
                            "fields": {
                                "Author & Historical Context": "President Abraham Lincoln, November 19, 1863, dedicating the Soldiers' National Cemetery 4 months after the Battle of Gettysburg",
                                "Core Constitutional Principle": "Connects the Union's survival directly to the 1776 Declaration ('all men are created equal')",
                                "Impact at the Time": "Transformed the Civil War from a territorial dispute into a moral struggle for human liberty and self-government",
                                "Relevance Today": "Reminds every generation of citizens that constitutional democracy requires active stewardship and sacrifice",
                            },
                            "counselor_tip": "Pick one historic speech, read the full text before class, and be ready to quote one sentence that stood out to you.",
                        },
                        "bullets": [
                            "Author & Historical Context: President Abraham Lincoln, November 19, 1863, dedicating the Soldiers' National Cemetery",
                            "Core Constitutional Principle: Connects the Union's survival directly to the 1776 Declaration ('all men are created equal')",
                            "Impact at the Time: Transformed the Civil War into a moral struggle for human liberty and self-government",
                            "Relevance Today: Reminds every generation that constitutional democracy requires active stewardship",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout analyzes a historic American speech, explaining the author, historical context, main arguments, and modern relevance.",
            },
            {
                "req_id": "7",
                "req_number": "7",
                "topic_title": "Req 7: National Historic Landmarks, Capitols & Federal Facilities",
                "action_verb": "Visit",
                "req_text": "Do TWO of the following (with parent and counselor approval): (a) Visit a National Historic Landmark or National Register site, (b) Tour your state capitol or the U.S. Capitol, (c) Tour a federal facility, or (d) Choose a national monument and explain its historical significance.",
                "safety_callout": "Follow Youth Protection buddy system and parental accompaniment rules when touring federal facilities or historic landmarks.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "edge_phase": "Enable",
                "recommended_archetype": "GEAR_CHECKLIST_GRID",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/ai_illustrations/citizenship_in_the_nation_landmarks_visual.png",
                "pamphlet_excerpts": [
                    "National Register of Historic Places: Administered by the National Park Service under the National Historic Preservation Act of 1966 to preserve sites of local, state, and national significance.",
                    "State & U.S. Capitol Tours (Option 7b): Observe bicameral legislative chambers, committee rooms, and civic art depicting state and national history.",
                    "Federal Facility Missions (Option 7c): Federal courthouses, NASA centers, national laboratories, VA medical centers, and U.S. Mint facilities carry out constitutional duties.",
                    "National Monuments (Option 7d): Designated by Congress or the President under the Antiquities Act of 1906 to protect historic landmarks and natural wonders.",
                ],
                "gear_checklist": [
                    "Two Civic Options: Completion of 2 of the 4 Requirement 7 civic exploration options (7a, 7b, 7c, or 7d)",
                    "Tour Documentation: Field notes, visitor guide, or photo from National Historic Landmark or Capitol tour",
                    "Historical Significance: Summary of why the landmark or monument was added to the National Register",
                    "Government Function Summary: Explanation of what you learned about the functions of federal or state government",
                ],
                "topic_slides": [
                    {
                        "title": "Exploring National Landmarks, Capitols & Monuments",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/ai_illustrations/citizenship_in_the_nation_landmarks_visual.png",
                        "caption": "Civic Field Exploration: Uniformed Scouts with field notebooks visiting the U.S. Capitol, Independence Hall, the Washington Monument, and the Lincoln Memorial.",
                        "bullets": [
                            "Experiencing History Firsthand: Visiting historic landmarks, capitols, and federal facilities connects textbook civics to the real places where laws are made and history unfolded.",
                        ],
                    },
                    {
                        "title": "National Monuments & Historic Preservation (Options 7a–7d)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/citizenship_in_the_nation_p047_img1.png",
                        "caption": "Mount Rushmore National Memorial depicting Presidents Washington, Jefferson, Theodore Roosevelt, and Lincoln.",
                        "bullets": [
                            "Option 7a (Historic Sites): Over 95,000 properties are listed on the National Register of Historic Places, including ~2,600 National Historic Landmarks.",
                            "Option 7b (Capitol Tour): Compare your state legislature's bicameral chambers (or unicameral in Nebraska) with the U.S. Congress.",
                            "Option 7c (Federal Facility): Tour a federal court, post office hub, Coast Guard station, national fish hatchery, or NOAA weather office.",
                            "Option 7d (National Monument): Research a monument's founding date, historical figures, and why Americans preserved it.",
                        ],
                    },
                    {
                        "title": "Civic Field Visit & Landmark Verification Checklist",
                        "layout": "GEAR_CHECKLIST_GRID",
                        "gear_checklist": [
                            "Two Civic Options: Completion of 2 of the 4 Requirement 7 civic exploration options (7a, 7b, 7c, or 7d)",
                            "Tour Documentation: Field notes, visitor guide, or photo from National Historic Landmark or Capitol tour",
                            "Historical Significance: Summary of why the landmark or monument was added to the National Register",
                            "Government Function Summary: Explanation of what you learned about the functions of federal or state government",
                        ],
                        "bullets": [
                            "Two Civic Options: Completion of 2 of the 4 Requirement 7 civic exploration options (7a, 7b, 7c, or 7d)",
                            "Tour Documentation: Field notes, visitor guide, or photo from National Historic Landmark or Capitol tour",
                            "Historical Significance: Summary of why the landmark or monument was added to the National Register",
                            "Government Function Summary: Explanation of what you learned about the functions of federal or state government",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout presents field notes/photos from two completed Requirement 7 options and explains their historical and civic significance.",
            },
            {
                "req_id": "8",
                "req_number": "8",
                "topic_title": "Req 8: Congressional Delegation & Constituent Letter",
                "action_verb": "Name",
                "req_text": "Name your two U.S. Senators and the member of Congress from your congressional district. Write a letter about a national issue and send it to one of these elected officials, sharing your view with your counselor and discussing any response you receive.",
                "safety_callout": "Review correspondence with a parent or counselor before mailing or submitting via official Senate.gov / House.gov constituent portals.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "edge_phase": "Enable",
                "recommended_archetype": "WORKED_EXAMPLE_TEMPLATE",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/ai_illustrations/citizenship_in_the_nation_bill_to_law_visual.png",
                "pamphlet_excerpts": [
                    "Identifying Your Delegation: Every state elects 2 U.S. Senators for 6-year terms; each congressional district elects 1 U.S. Representative for a 2-year term.",
                    "Proper Honorific Address: Address Senators as 'The Honorable [Full Name], United States Senate' and Representatives as 'The Honorable [Full Name], House of Representatives'.",
                    "Effective Constituent Structure: Keep your letter to 1 concise page focusing on a single national issue, citing a specific bill number if possible.",
                    "Personal Scouting Connection: Explain how the issue impacts your community, troop, or local public lands, and politely request a written reply stating their position.",
                ],
                "worked_example": {
                    "title": "Formal Constituent Letter Template to a U.S. Senator / Representative",
                    "artifact_type": "LETTER_TEMPLATE",
                    "fields": {
                        "Header & Salutation": "The Honorable [Full Name] | United States Senate, Washington, DC 20510 | Dear Senator [Last Name]:",
                        "Paragraph 1 (Who & Issue)": "My name is [Scout Name], a Scout in Troop [Number] in [Hometown, State]. I am writing to share my perspective on federal funding for National Park trail maintenance (S. [Bill #]).",
                        "Paragraph 2 (Local Impact)": "Our troop hikes and completes conservation projects on public lands every month. Maintaining safe trails and clean watersheds protects wildlife and outdoor recreation.",
                        "Paragraph 3 (Ask & Close)": "Thank you for your service to our state. Please let me know your position on this legislation. Sincerely, [Scout Name], [Street Address, City, State, ZIP]",
                    },
                    "counselor_tip": "Always include your return mailing address or email in the body of the letter so the Senator's constituent services office can send an official reply.",
                },
                "topic_slides": [
                    {
                        "title": "How a Bill Becomes a Law & Your Constituent Voice",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/ai_illustrations/citizenship_in_the_nation_bill_to_law_visual.png",
                        "caption": "Four-Stage Federal Legislative Process: Committee markup, House and Senate floor votes, Presidential signature, and judicial review.",
                        "bullets": [
                            "Two U.S. Senators (Statewide): Represent your entire state in the Senate for 6-year staggered terms (lookup at senate.gov).",
                            "One U.S. Representative (District): Represents your local congressional district in the House for a 2-year term (lookup at house.gov).",
                            "Why Constituent Letters Matter: Congressional offices log every constituent letter by ZIP code and topic to brief the Member before floor votes.",
                            "Youth Protection & Mailing: Review your letter with a parent/guardian before mailing or submitting via the official congressional contact form.",
                        ],
                    },
                    {
                        "title": "Mailing Your Constituent Letter to Congress",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/citizenship_in_the_nation_p043_img1.png",
                        "caption": "U.S. Postal Service mailbox used to mail a formal constituent letter to a U.S. Senator or Representative.",
                        "bullets": [
                            "District vs. Washington Offices: Senators and Representatives maintain local district offices in your home state as well as Capitol Hill offices.",
                            "Focusing on One Issue: Clearly state the specific bill number or national issue in your opening paragraph and explain why you support or oppose it.",
                            "Sharing Local Scouting Impact: Describe how the policy affects your hometown, school, watershed, or troop outdoor program.",
                            "Discussing the Official Response: Bring a copy of your letter and any reply from the Senator or Representative to discuss with your counselor.",
                        ],
                    },
                    {
                        "title": "Worked Example: Constituent Letter Template",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "Formal Constituent Letter Template to a U.S. Senator / Representative",
                            "artifact_type": "LETTER_TEMPLATE",
                            "fields": {
                                "Header & Salutation": "The Honorable [Full Name] | United States Senate, Washington, DC 20510 | Dear Senator [Last Name]:",
                                "Paragraph 1 (Who & Issue)": "My name is [Scout Name], a Scout in Troop [Number] in [Hometown, State]. I am writing to share my perspective on federal funding for National Park trail maintenance (S. [Bill #]).",
                                "Paragraph 2 (Local Impact)": "Our troop hikes and completes conservation projects on public lands every month. Maintaining safe trails and clean watersheds protects wildlife and outdoor recreation.",
                                "Paragraph 3 (Ask & Close)": "Thank you for your service to our state. Please let me know your position on this legislation. Sincerely, [Scout Name], [Street Address, City, State, ZIP]",
                            },
                            "counselor_tip": "Always include your return mailing address or email in the body of the letter so the Senator's constituent services office can send an official reply.",
                        },
                        "bullets": [
                            "Header & Salutation: The Honorable [Full Name] | United States Senate, Washington, DC 20510 | Dear Senator [Last Name]:",
                            "Paragraph 1 (Who & Issue): Identify yourself as a constituent Scout and state the specific national issue or bill number.",
                            "Paragraph 2 (Local Impact): Explain with facts and personal Scouting experience how the issue affects your hometown.",
                            "Paragraph 3 (Ask & Close): Thank the official, ask for their written position, and include your return address.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout names both U.S. Senators and their House Representative and shows a copy of their sent constituent letter (and any reply).",
            },
        ],
    },
    "Citizenship in the Community": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Citizenship%20in%20the%20Community.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/citizenship-community/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "action_verb": "Discuss",
                "req_text": "Discuss with your counselor what citizenship in the community means and what it takes to be a good citizen in your community, including rights, duties, and obligations.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2a",
                "req_number": "2a",
                "parent_id": "2",
                "action_verb": "Locate",
                "req_text": "On a map of your community or using an electronic device, locate and point out the chief government buildings such as city hall, county courthouse, police station, fire station, public works, and hospitals.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "3a",
                "req_number": "3a",
                "parent_id": "3",
                "action_verb": "Attend",
                "req_text": "Attend a meeting of your city, town, or county council or school board; OR attend a municipal, county, or state court session, and report on an issue where differing opinions were expressed.",
                "safety_callout": "Youth protection: Scouts must attend public civic meetings with a parent, guardian, or Two-Deep adult leadership.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
            {
                "req_id": "7c",
                "req_number": "7c",
                "parent_id": "7",
                "action_verb": "Volunteer",
                "req_text": "Volunteer at least eight hours of your time working for a charitable or non-profit organization in your community and discuss how your service benefited the community.",
                "safety_callout": "All community service hours require parental permission and Youth Protection compliance.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
        ],
    },
    "Citizenship in the World": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Citizenship%20in%20the%20World.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/citizenship-world/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "action_verb": "Explain",
                "req_text": "Explain what citizenship in the world means to you and what you think it takes to be a good world citizen.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Explain",
                "req_text": "Explain how one becomes a citizen in the United States, and explain the rights, duties, and obligations of U.S. citizenship compared with two other countries.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "3a",
                "req_number": "3a",
                "parent_id": "3",
                "action_verb": "Analyze",
                "req_text": "Pick a current world event and explain to your counselor how a country's national interest, history, and geography affect its international relations.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "4",
                "req_number": "4",
                "action_verb": "Describe",
                "req_text": "Explain international law and describe the roles of international organizations including the United Nations (UN), World Health Organization (WHO), NATO, and World Organization of the Scout Movement (WOSM).",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
        ],
    },
    "Communication": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Communication.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/communication/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "action_verb": "Demonstrate",
                "req_text": "Do ONE of the following: keep a 1-day communication log, practice active listening in a group discussion, or analyze body language and non-verbal communication cues.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "3",
                "req_number": "3",
                "action_verb": "Deliver",
                "req_text": "Write a five-minute speech and give it at a meeting of a group using effective vocal projection, eye contact, and structured outline.",
                "safety_callout": None,
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
            {
                "req_id": "5",
                "req_number": "5",
                "action_verb": "Attend",
                "req_text": "Attend a public meeting (city council, school board, or debate) approved by your counselor where citizens present opposing viewpoints, and take notes on each speaker's points.",
                "safety_callout": "Follow Youth Protection guidelines when attending public meetings.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
            {
                "req_id": "8",
                "req_number": "8",
                "action_verb": "Plan",
                "req_text": "Plan a troop court of honor, campfire program, or interfaith worship service, write the script, and serve as master of ceremonies.",
                "safety_callout": None,
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
        ],
    },
    "Cooking": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Cooking.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/cooking/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "topic_title": "Req 1: Kitchen Safety, First Aid, Safe Temps & Allergens",
                "action_verb": "Explain",
                "req_text": "Health and Safety. Do the following: (a) Explain the most likely hazards in cooking activities and how to prevent and respond to them, (b) Show first aid for burns, scalds, cuts, choking, and allergic reactions, (c) Describe how meat, fish, poultry, eggs, dairy, and produce must be stored, transported, and cooked to safe internal temperatures, (d) Discuss cross-contamination and foodborne illnesses, and (e) Discuss food allergies, intolerances, and food-related illnesses.",
                "safety_callout": "Strictly enforce food allergy checks, USDA safe internal temperatures, and Totin' Chip/Firem'n Chit kitchen safety procedures.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/ai_illustrations/cooking_req_1_nano_hero.png",
                "pamphlet_excerpts": [
                    "Kitchen Hazard Prevention (Req 1a-1b): Turn pot handles inward, use dry potholders, slice with the 'claw grip' away from the body, and smother grease fires with a metal lid or baking soda (never water).",
                    "Temperature Danger Zone (Req 1c): Bacteria multiply rapidly between 40°F and 140°F; keep cold perishables at or below 40°F in an ice-packed cooler and hot foods above 140°F.",
                    "USDA Minimum Internal Temps (Req 1c): Cook all poultry to 165°F, ground beef/pork to 160°F, and whole steaks, pork chops, roasts, and fish to 145°F (with a 3-minute rest).",
                    "Cross-Contamination & Allergens (Req 1d-1e): Wash hands with soap for 20 seconds, separate raw meats from ready-to-eat produce, and screen patrol menus for the 9 major food allergens.",
                ],
                "step_by_step_procedure": [
                    "Clean Hands & Surfaces: Wash hands with warm water and soap for 20 seconds before and after handling raw food.",
                    "Separate Raw & Ready Foods: Use separate cutting boards and utensils for raw poultry/meat and fresh vegetables.",
                    "Cook to Safe Internal Temps: Verify internal temperatures with a calibrated digital food thermometer in the thickest part.",
                    "Chill Below 40°F Promptly: Pack perishables on ice at <=40°F and refrigerate leftovers within 2 hours (1 hour if >90°F).",
                ],
                "comparison_data": {
                    "left_header": "Life-Threatening Food Allergy",
                    "left_badge": "IMMUNE SYSTEM (911)",
                    "left_points": [
                        "Physiological Cause: Immune system overreacts to a specific food protein (peanuts, tree nuts, shellfish, milk, eggs, wheat, soy, fish, sesame)",
                        "Trace Exposure Risk: Even microscopic cross-contact on a knife or skillet can trigger systemic anaphylaxis",
                        "Warning Symptoms: Throat/tongue swelling, hives, wheezing, shortness of breath, dizziness, and drop in blood pressure",
                        "Emergency Response: Inject epinephrine auto-injector (EpiPen) into outer thigh immediately and call 911",
                    ],
                    "right_header": "Food Intolerance & Sensitivity",
                    "right_badge": "DIGESTIVE SYSTEM",
                    "right_points": [
                        "Physiological Cause: Digestive tract cannot properly break down a food component (such as lactose intolerance) or celiac gluten reaction",
                        "Dose & Symptoms: Causes stomach cramps, bloating, nausea, or diarrhea without acute airway closure",
                        "Celiac Disease Note: Autoimmune reaction to gluten (wheat, barley, rye) requiring strict gluten-free cookware and ingredients",
                        "Menu Planning Rule: Audit every Scout's AHMR Part B before shopping and substitute safe ingredients for the entire patrol",
                    ],
                },
                "topic_slides": [
                    {
                        "title": "Kitchen Hazards & First Aid for Burns, Cuts & Grease Fires",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/cooking_p017_img2.png",
                        "caption": "Wearing insulated oven mitts and tilting a pot lid away from the body to shield hands from scalding steam.",
                        "bullets": [
                            "Burns & Scalds First Aid: Cool 1st- and 2nd-degree burns under cool running water for 10+ minutes; never apply butter, ice, or ointments.",
                            "Knife Safety & Cuts: Curl fingers into a 'claw grip' when chopping; apply firm direct pressure with sterile gauze to stop bleeding.",
                            "Smothering a Grease Fire: Turn off the stove burner and slide a metal lid or pour baking soda over the pan—never throw water on burning oil.",
                            "Carbon Monoxide Prevention: Never operate propane, butane, white-gas stoves, or charcoal inside a tent, cabin, or unventilated shelter.",
                        ],
                    },
                    {
                        "title": "USDA Safe Internal Temperatures & Cold Storage",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/ai_illustrations/cooking_usda_temps_visual.png",
                        "caption": "Thermometer Verification & Cold Chain: Inserting an instant-read thermometer into the thickest center of poultry (165°F), ground beef (160°F), and pork/steaks (145°F) alongside an ice-packed cooler (<=40°F).",
                        "bullets": [
                            "USDA Internal Temperature Standards: Poultry & reheated leftovers = 165°F; Ground beef & pork = 160°F; Whole cuts of beef, pork, lamb & fish = 145°F; Cold storage <= 40°F.",
                        ],
                    },
                    {
                        "title": "Safe Knife Handling & Preventing Cross-Contamination",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/cooking_p068_img1.png",
                        "caption": "Practicing safe claw-grip knife technique with curled fingertips on a dedicated cutting board.",
                        "bullets": [
                            "Clean Hands & Surfaces: Wash hands with warm water and soap for 20 seconds before and after handling raw food.",
                            "Separate Raw & Ready Foods: Use separate cutting boards and utensils for raw poultry/meat and fresh vegetables.",
                            "Cook to Safe Internal Temps: Verify internal temperatures with a calibrated digital food thermometer in the thickest part.",
                            "Chill Below 40°F Promptly: Pack perishables on ice at <=40°F and refrigerate leftovers within 2 hours (1 hour if >90°F).",
                        ],
                    },
                    {
                        "title": "Food Allergies, Anaphylaxis vs. Food Intolerances",
                        "layout": "DIFFERENTIAL_COMPARISON_2COL",
                        "comparison_data": {
                            "left_header": "Life-Threatening Food Allergy",
                            "left_badge": "IMMUNE SYSTEM (911)",
                            "left_points": [
                                "Physiological Cause: Immune system overreacts to a specific food protein (peanuts, tree nuts, shellfish, milk, eggs, wheat, soy, fish, sesame)",
                                "Trace Exposure Risk: Even microscopic cross-contact on a knife or skillet can trigger systemic anaphylaxis",
                                "Warning Symptoms: Throat/tongue swelling, hives, wheezing, shortness of breath, dizziness, and drop in blood pressure",
                                "Emergency Response: Inject epinephrine auto-injector (EpiPen) into outer thigh immediately and call 911",
                            ],
                            "right_header": "Food Intolerance & Sensitivity",
                            "right_badge": "DIGESTIVE SYSTEM",
                            "right_points": [
                                "Physiological Cause: Digestive tract cannot properly break down a food component (such as lactose intolerance) or celiac gluten reaction",
                                "Dose & Symptoms: Causes stomach cramps, bloating, nausea, or diarrhea without acute airway closure",
                                "Celiac Disease Note: Autoimmune reaction to gluten (wheat, barley, rye) requiring strict gluten-free cookware and ingredients",
                                "Menu Planning Rule: Audit every Scout's AHMR Part B before shopping and substitute safe ingredients for the entire patrol",
                            ],
                        },
                        "bullets": [
                            "Food Allergy (Immune System): Big-9 allergens can cause anaphylaxis; treat with EpiPen and call 911.",
                            "Food Intolerance (Digestive): Lactose intolerance or gluten sensitivity requires safe menu substitutions.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout explains kitchen hazards, first aid for burns/cuts/choking/anaphylaxis, USDA safe temperatures, cross-contamination rules, and food allergies.",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "topic_title": "Req 2: USDA MyPlate Nutrition, Food Labels & Meal Balance",
                "action_verb": "Explain",
                "req_text": "Nutrition. Do the following: (a) Using the MyPlate food guide or the current USDA nutrition model, give five examples for EACH of the five food groups, the recommended daily servings, and the caloric needs for an active Scout, (b) Explain why you should limit oils, solid fats, added sugars, and sodium, and (c) Explain how to read a Nutrition Facts label.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/cooking_p041_img1.png",
                "pamphlet_excerpts": [
                    "Five USDA MyPlate Groups (Req 2a): Fruits (2 cups/day), Vegetables (2.5-3 cups/day), Grains (6-8 oz/day, at least half whole grains), Protein Foods (5.5-6.5 oz/day), and Dairy (3 cups/day).",
                    "Active Scout Caloric Needs (Req 2a): Moderately active teen Scouts require 2,200 to 2,800 kcal/day at home, rising to 3,000-4,000+ kcal/day during strenuous backpacking or cold-weather camping.",
                    "Limiting Fats, Sugars & Sodium (Req 2b): Keep saturated fat <10% of calories, added sugars <10% of calories (<50g/day), and sodium below 2,300 mg/day to protect cardiovascular health.",
                    "Reading Nutrition Facts Labels (Req 2c): Check Serving Size and Servings Per Container first, then compare % Daily Value (5% DV or less is low; 20% DV or more is high).",
                ],
                "topic_slides": [
                    {
                        "title": "Selecting Nutrient-Dense MyPlate Food Group Ingredients",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/cooking_p041_img1.png",
                        "caption": "Scout and parent selecting fresh vegetables and whole-food ingredients in the grocery produce aisle.",
                        "bullets": [
                            "Five Food Groups & Daily Targets for Active Youth: Fruits (2 cups), Vegetables (2.5-3 cups), Grains (6-8 oz, >=50% whole grain), Protein (5.5-6.5 oz), and Dairy (3 cups).",
                        ],
                    },
                    {
                        "title": "Five Examples from Each MyPlate Food Group",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Fruits & Vegetables (5 Each): Apples, bananas, berries, oranges, dried apricots; broccoli, carrots, spinach, bell peppers, sweet potatoes.",
                            "Grains (5 Examples): Rolled oats, brown rice, whole-wheat pasta, whole-grain tortillas, and quinoa (make at least half your grains whole).",
                            "Protein Foods (5 Examples): Chicken breast, salmon/tuna, lean beef, eggs, black beans/lentils, and peanut or almond butter.",
                            "Dairy Group (5 Examples): Low-fat milk, Greek yogurt, cheddar cheese, string cheese, and calcium-fortified soy milk.",
                        ],
                    },
                    {
                        "title": "Reading Nutrition Labels & Limiting Sodium, Sugar & Fats",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "How to Audit a Trail Food Nutrition Facts Label",
                            "artifact_type": "NUTRITION LABEL AUDIT",
                            "fields": {
                                "1. Serving Size & Count": "Always multiply calories and sodium by the number of servings you actually eat",
                                "2. Sodium (<2,300 mg/day)": "Dehydrated camp meals often exceed 900 mg sodium per pouch; choose low-sodium broth and herbs",
                                "3. Added Sugars (<50g/day)": "Avoid sodas and candy spikes that cause trail energy crashes; prefer complex carbs + protein",
                                "4. Healthy Oils vs. Solid Fats": "Use liquid olive or canola oil (unsaturated) instead of trans fats, lard, or heavy saturated fats",
                            },
                            "counselor_tip": "Use the 5/20 Rule on % Daily Value: 5% DV or less is LOW (aim low for sodium, saturated fat, added sugar); 20% DV or more is HIGH (aim high for fiber, calcium, iron, potassium).",
                        },
                        "bullets": [
                            "1. Serving Size & Count: Always multiply calories and sodium by the number of servings you actually eat",
                            "2. Sodium (<2,300 mg/day): Dehydrated camp meals often exceed 900 mg sodium per pouch; choose low-sodium broth and herbs",
                            "3. Added Sugars (<50g/day): Avoid sodas and candy spikes that cause trail energy crashes; prefer complex carbs + protein",
                            "4. Healthy Oils vs. Solid Fats: Use liquid olive or canola oil (unsaturated) instead of trans fats, lard, or heavy saturated fats",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout names 5 examples and daily servings for each MyPlate group, explains why to limit sodium/added sugars/saturated fats, and interprets a Nutrition Facts label.",
            },
            {
                "req_id": "3",
                "req_number": "3",
                "topic_title": "Req 3: Five Cooking Methods, Stoves & Cast-Iron Care",
                "action_verb": "Demonstrate",
                "req_text": "Cooking Basics. Do the following: (a) Discuss each of the following cooking methods—boiling, baking, frying, simmering, steaming, microwaving, and grilling/broiling—and give two examples of foods cooked each way, (b) Discuss the benefits of using a camp stove on an outing vs. a charcoal or wood fire, and (c) Describe how to manage your time when preparing a meal so components finish hot together.",
                "safety_callout": "Never use chemical stoves or charcoal inside a tent; always keep a fire extinguisher or water bucket within reach.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/cooking_p036_img1.png",
                "pamphlet_excerpts": [
                    "Seven Core Cooking Methods (Req 3a): Boiling (212°F rolling bubbles), Simmering (185°F-205°F gentle bubbles), Steaming/Foil Packet, Baking (Dutch oven dry heat), Frying/Sautéing, Grilling/Broiling, and Microwaving.",
                    "Dutch Oven Coal Math (Req 3a): For 350°F baking in a cast-iron Dutch oven, use the 'Plus-2 / Minus-2' rule (Oven Diameter + 2 briquettes on the lid; Oven Diameter - 2 briquettes underneath).",
                    "Camp Stove vs. Campfire (Req 3b): Camp stoves light instantly in rain, leave zero ash scar, obey fire-ban rules, and provide precise simmer control; wood/charcoal excels at Dutch oven baking.",
                    "Backward Meal Timing (Req 3c): Start longest-cooking items (baked potatoes, brown rice, stews) first and quick-cooking items (eggs, sautéed greens, toast) last so everything finishes hot together.",
                ],
                "comparison_data": {
                    "left_header": "Camp Stove (Propane / Liquid / Canister)",
                    "left_badge": "PRECISION & LEAVE NO TRACE",
                    "left_points": [
                        "Instant Heat Control: Turn control valve from roaring boil to gentle simmer in seconds without waiting for coals",
                        "All-Weather Reliability: Boils water quickly in rain, snow, or high wind when firewood is soaked",
                        "Leave No Trace Compliance: Leaves zero ash scar, preserves downed forest wood, and is legal during stage-1 fire bans",
                        "Clean Cookware: Clean blue gas flame does not coat pots in black creosote soot",
                    ],
                    "right_header": "Charcoal & Wood Campfire",
                    "right_badge": "TRADITIONAL & DUTCH OVEN",
                    "right_points": [
                        "Dutch Oven & Foil Mastery: Glowing hardwood coals provide steady radiant top-and-bottom heat for baking and foil packs",
                        "Preparation Time: Requires 30 to 45 minutes to burn down wood or chimney-start charcoal briquettes to white ash coals",
                        "Environmental & Fire Risk: Embers can spark wildfires in dry brush; restricted in alpine and high-fire-danger zones",
                        "Soot & Cleanup: Coat exterior of pots with a thin film of liquid dish soap before cooking over wood to wash soot off easily",
                    ],
                },
                "topic_slides": [
                    {
                        "title": "Cast-Iron Dutch Oven Baking & Core Cooking Methods",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/cooking_p036_img1.png",
                        "caption": "Cast-iron Dutch oven baking with glowing charcoal briquettes placed on the flanged lid and beneath the base.",
                        "bullets": [
                            "Matching Heat Transfer to Ingredients: Boiling (pasta, potatoes), Simmering (chili, oatmeal), Steaming/Foil (fish, vegetables), Baking (biscuits, cobbler), Frying (pancakes, eggs), and Grilling (burgers, fajitas).",
                        ],
                    },
                    {
                        "title": "Propane Camp Stove Operation & Backward Meal Timing",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/cooking_p033_img2.png",
                        "caption": "Two-burner propane camp stove connected to a regulated fuel cylinder on a level surface.",
                        "bullets": [
                            "Dutch Oven 350°F Briquette Rule: For a 12-inch Dutch oven, place 14 lit coals on the lid (12 + 2) and 10 coals under the base (12 - 2); rotate lid and pot every 15 minutes.",
                            "Seasoning & Cleaning Cast Iron: Scrape with warm water and a stiff brush (never soak in dish soap), dry over low heat, and wipe with a thin coat of vegetable oil.",
                            "Mise en Place (Prep First): Measure, wash, and chop all ingredients before lighting the stove so nothing burns while you search for utensils.",
                            "Backward Meal Scheduling: Count backward from serving time—start 40-minute baked/simmered dishes first, 15-minute sides second, and 5-minute pan-fried proteins last.",
                        ],
                    },
                    {
                        "title": "Camp Stove vs. Charcoal & Wood Fire Comparison",
                        "layout": "DIFFERENTIAL_COMPARISON_2COL",
                        "comparison_data": {
                            "left_header": "Camp Stove (Propane / Liquid / Canister)",
                            "left_badge": "PRECISION & LEAVE NO TRACE",
                            "left_points": [
                                "Instant Heat Control: Turn control valve from roaring boil to gentle simmer in seconds without waiting for coals",
                                "All-Weather Reliability: Boils water quickly in rain, snow, or high wind when firewood is soaked",
                                "Leave No Trace Compliance: Leaves zero ash scar, preserves downed forest wood, and is legal during stage-1 fire bans",
                                "Clean Cookware: Clean blue gas flame does not coat pots in black creosote soot",
                            ],
                            "right_header": "Charcoal & Wood Campfire",
                            "right_badge": "TRADITIONAL & DUTCH OVEN",
                            "right_points": [
                                "Dutch Oven & Foil Mastery: Glowing hardwood coals provide steady radiant top-and-bottom heat for baking and foil packs",
                                "Preparation Time: Requires 30 to 45 minutes to burn down wood or chimney-start charcoal briquettes to white ash coals",
                                "Environmental & Fire Risk: Embers can spark wildfires in dry brush; restricted in alpine and high-fire-danger zones",
                                "Soot & Cleanup: Coat exterior of pots with a thin film of liquid dish soap before cooking over wood to wash soot off easily",
                            ],
                        },
                        "bullets": [
                            "Camp Stoves: Fast ignition, precise flame control, clean pots, and Leave No Trace friendly.",
                            "Charcoal & Wood Fires: Ideal for cast-iron Dutch oven baking and foil packets over glowing coals.",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout explains all cooking methods with food examples, compares camp stoves vs. wood/charcoal fires, and explains backward meal timing.",
            },
            {
                "req_id": "4",
                "req_number": "4",
                "topic_title": "Req 4: Home Cooking: 3-Day Menu, Grocery Budget & Execution",
                "action_verb": "Prepare",
                "req_text": "Cooking at Home. Using the MyPlate food guide, plan a menu for three full days of meals (three breakfasts, three lunches, and three dinners) plus one dessert. Create an itemized equipment list and grocery shopping budget, then cook and serve one breakfast, one lunch, and one dinner for your family.",
                "safety_callout": "Wash hands for 20 seconds and use separate cutting boards for raw meat and fresh produce.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "edge_phase": "Enable",
                "recommended_archetype": "WORKED_EXAMPLE_TEMPLATE",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/cooking_p042_img1.png",
                "pamphlet_excerpts": [
                    "Three-Day Home Menu Design (Req 4a): Plan 3 breakfasts, 3 lunches, 3 dinners, and 1 dessert that hit every MyPlate food group across the day.",
                    "Recipe Scaling & Unit Pricing (Req 4b-4c): Scale ingredient quantities to match your family size, check pantry staples first, and compare unit prices ($/oz or $/lb) at the grocery store.",
                    "Equipment & Timing Sheet (Req 4d-4e): List every pot, skillet, baking sheet, thermometer, and measuring tool required before turning on the oven or range.",
                    "Family Meal Evaluation (Req 4f-4g): Cook and serve 1 breakfast, 1 lunch, and 1 dinner using varied cooking methods, then record family feedback on taste, timing, and presentation.",
                ],
                "worked_example": {
                    "title": "Home Cooking Menu, Cost & Timing Plan (Family of 4)",
                    "artifact_type": "MENU & BUDGET LOG",
                    "fields": {
                        "Breakfast (Pan-Fry & Simmer)": "Whole-grain blueberry pancakes, scrambled eggs, turkey sausage, fresh orange slices & milk ($11.40 total / $2.85 per serving)",
                        "Lunch (Grill & Assemble)": "Grilled chicken & avocado whole-wheat wraps, carrot/celery sticks with hummus, apple slices & yogurt ($13.80 total / $3.45 per serving)",
                        "Dinner (Bake, Roast & Steam)": "Herb-baked salmon (145°F), brown rice pilaf, steamed broccoli, garden salad & baked cinnamon apples ($21.60 total / $5.40 per serving)",
                        "Synchronized Dinner Timeline": "17:15 Preheat oven 400°F & start brown rice (40m) -> 17:35 Bake salmon & apples (20m) -> 17:45 Steam broccoli (8m) -> 17:55 Serve hot",
                    },
                    "counselor_tip": "Bring your complete 3-day menu chart, itemized grocery receipt/price list, photos of the 3 meals you cooked at home, and parent verification notes.",
                },
                "topic_slides": [
                    {
                        "title": "Planning & Budgeting Your 3-Day Home Menu",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/cooking_p042_img1.png",
                        "caption": "Supermarket shelf tag comparing total retail package price against unit cost per ounce for meal budgeting.",
                        "bullets": [
                            "Nutritional Completeness: Every day's breakfast, lunch, and dinner must incorporate Fruits, Vegetables, Whole Grains, lean Protein, and Dairy.",
                            "Pantry Audit Before Shopping: Check spices, oils, flour, and rice already at home so your grocery budget only buys needed perishables.",
                            "Unit-Price Comparison: Compare store brands vs. name brands using the shelf tag unit price (cost per ounce or pound) to stay on budget.",
                            "Variety of Cooking Methods: Demonstrate at least three distinct cooking methods (such as pan-frying, baking/roasting, simmering, and steaming) across your three cooked meals.",
                        ],
                    },
                    {
                        "title": "Worked Example: Home Menu, Budget & Kitchen Timeline",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "Home Cooking Menu, Cost & Timing Plan (Family of 4)",
                            "artifact_type": "MENU & BUDGET LOG",
                            "fields": {
                                "Breakfast (Pan-Fry & Simmer)": "Whole-grain blueberry pancakes, scrambled eggs, turkey sausage, fresh orange slices & milk ($11.40 total / $2.85 per serving)",
                                "Lunch (Grill & Assemble)": "Grilled chicken & avocado whole-wheat wraps, carrot/celery sticks with hummus, apple slices & yogurt ($13.80 total / $3.45 per serving)",
                                "Dinner (Bake, Roast & Steam)": "Herb-baked salmon (145°F), brown rice pilaf, steamed broccoli, garden salad & baked cinnamon apples ($21.60 total / $5.40 per serving)",
                                "Synchronized Dinner Timeline": "17:15 Preheat oven 400°F & start brown rice (40m) -> 17:35 Bake salmon & apples (20m) -> 17:45 Steam broccoli (8m) -> 17:55 Serve hot",
                            },
                            "counselor_tip": "Bring your complete 3-day menu chart, itemized grocery receipt/price list, photos of the 3 meals you cooked at home, and parent verification notes.",
                        },
                        "bullets": [
                            "Breakfast (Pan-Fry & Simmer): Whole-grain blueberry pancakes, scrambled eggs, turkey sausage, fresh orange slices & milk ($11.40)",
                            "Lunch (Grill & Assemble): Grilled chicken & avocado whole-wheat wraps, carrot/celery sticks with hummus, apple & yogurt ($13.80)",
                            "Dinner (Bake, Roast & Steam): Herb-baked salmon (145°F), brown rice pilaf, steamed broccoli, salad & baked apples ($21.60)",
                            "Synchronized Dinner Timeline: 17:15 Start brown rice -> 17:35 Bake salmon & apples -> 17:45 Steam broccoli -> 17:55 Serve hot",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout presents a 3-day MyPlate home menu, equipment list, itemized grocery budget, and parent-verified notes/photos from cooking 1 breakfast, 1 lunch, and 1 dinner.",
            },
            {
                "req_id": "5",
                "req_number": "5",
                "topic_title": "Req 5: Camp Cooking: Patrol Menus, 3 Methods & 3-Pot Sanitation",
                "action_verb": "Prepare",
                "req_text": "Camp Cooking. Plan a patrol campout menu (two breakfasts, two lunches, two dinners, and one dessert) using MyPlate, calculate per-Scout food quantities and budget, and serve as patrol head cook for at least one breakfast, one lunch, one dinner, and one dessert using at least three cooking methods and BSA 3-pot dishwashing sanitation.",
                "safety_callout": "Never leave active camp stoves or campfires unattended, and sanitize all patrol dishes in Pot 3 before air-drying.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "edge_phase": "Demonstrate, Guide & Enable",
                "recommended_archetype": "STEP_BY_STEP_PROCEDURE_4CARD",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/cooking_p085_img1.png",
                "pamphlet_excerpts": [
                    "Patrol Menu & Per-Scout Budgeting (Req 5a-5c): Scale recipes for your patrol size (typically 6-8 Scouts), divide total grocery cost per Scout, and repackage bulk items at home to reduce camp trash.",
                    "Cold-Chain Packing in Camp (Req 5d): Pre-chill coolers, pack frozen meats at the bottom on block ice, keep a thermometer inside (<=40°F), and use a separate beverage cooler so the food cooler stays closed.",
                    "Three Camp Cooking Methods (Req 5e-5f): Prepare meals outdoors using camp stoves, Dutch ovens, foil packets, or skillets across at least three distinct cooking methods.",
                    "BSA Three-Pot Sanitation & Leave No Trace (Req 5g-5h): Scrape plates clean -> Pot 1 Hot Soapy Wash -> Pot 2 Clear Warm Rinse -> Pot 3 Sanitize -> Air-dry in mesh bag; strain graywater and scatter 200+ feet from water sources.",
                ],
                "step_by_step_procedure": [
                    "Scrape All Food Scraps: Wipe plates and pots clean with a rubber spatula into the trash bag before touching wash water.",
                    "Pot 1 (Hot Soapy Wash): Scrub dishes thoroughly in hot water (~120°F) with a few drops of biodegradable camp soap.",
                    "Pot 2 (Clear Warm Rinse): Dip and swish every item in clean warm water to remove all soap residue.",
                    "Pot 3 (Sanitize & Air-Dry): Submerge in chemical sanitizing solution (or 170°F+ hot water) and hang in a mesh bag to air-dry.",
                ],
                "gear_checklist": [
                    "Stove & Fuel System: Two-burner camp stove, fuel canisters/bottles, and level cooking table",
                    "Dutch Oven Gear: Cast-iron Dutch oven, lid lifter, leather heat gloves, and charcoal chimney",
                    "Cook Kit & Thermometer: Patrol cook kit (pots, skillet, tongs, spatula, cutting boards) & digital thermometer",
                    "Three-Pot Sanitation Kit: Three dishwashing basins, biodegradable soap, sanitizer, mesh bag & strainer",
                ],
                "topic_slides": [
                    {
                        "title": "Patrol Camp Cooking Execution & Dutch Oven Mastery",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/cooking_p085_img1.png",
                        "caption": "Scouts using a steel lid lifter to inspect a hot meal baking inside a cast-iron Dutch oven at camp.",
                        "bullets": [
                            "Serving as Patrol Head Cook: Coordinate patrol prep, manage three distinct outdoor cooking methods, and enforce strict 3-pot dishwashing sanitation.",
                        ],
                    },
                    {
                        "title": "Cold-Chain Cooler Packing & Three-Pot Dishwashing",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/cooking_p016_img1.png",
                        "caption": "Scouts packing perishable foods into an insulated cooler with ice packs to keep cold food below 40°F.",
                        "bullets": [
                            "Scrape All Food Scraps: Wipe plates and pots clean with a rubber spatula into the trash bag before touching wash water.",
                            "Pot 1 (Hot Soapy Wash): Scrub dishes thoroughly in hot water (~120°F) with a few drops of biodegradable camp soap.",
                            "Pot 2 (Clear Warm Rinse): Dip and swish every item in clean warm water to remove all soap residue.",
                            "Pot 3 (Sanitize & Air-Dry): Submerge in chemical sanitizing solution (or 170°F+ hot water) and hang in a mesh bag to air-dry.",
                        ],
                    },
                    {
                        "title": "Patrol Chuckbox & Camp Kitchen Equipment Checklist",
                        "layout": "GEAR_CHECKLIST_GRID",
                        "gear_checklist": [
                            "Stove & Fuel System: Two-burner camp stove, fuel canisters/bottles, and level cooking table",
                            "Dutch Oven Gear: Cast-iron Dutch oven, lid lifter, leather heat gloves, and charcoal chimney",
                            "Cook Kit & Thermometer: Patrol cook kit (pots, skillet, tongs, spatula, cutting boards) & digital thermometer",
                            "Three-Pot Sanitation Kit: Three dishwashing basins, biodegradable soap, sanitizer, mesh bag & strainer",
                        ],
                        "bullets": [
                            "Stove & Fuel System: Two-burner camp stove, fuel canisters/bottles, and level cooking table",
                            "Dutch Oven Gear: Cast-iron Dutch oven, lid lifter, leather heat gloves, and charcoal chimney",
                            "Cook Kit & Thermometer: Patrol cook kit (pots, skillet, tongs, spatula, cutting boards) & digital thermometer",
                            "Three-Pot Sanitation Kit: Three dishwashing basins, biodegradable soap, sanitizer, mesh bag & strainer",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout presents patrol campout menu, budget, equipment list, and counselor/leader verification of cooking 1 breakfast, 1 lunch, 1 dinner, and 1 dessert using 3+ methods and 3-pot sanitation.",
            },
            {
                "req_id": "6",
                "req_number": "6",
                "topic_title": "Req 6: Trail & Backpacking Meals, Ultralight Stoves & Bear Safety",
                "action_verb": "Prepare",
                "req_text": "Trail and Backpacking Meals. Plan a trail/backpacking menu (two meals and one high-energy trail snack) requiring no refrigeration, repackage ingredients to minimize weight and trash, cook on a backpacking stove or trail hike, and demonstrate Leave No Trace and bear-safe food storage.",
                "safety_callout": "Hang bear bags (12 ft high, 6 ft out from trunk) or use approved bear canisters in a 100-foot Bearmuda Triangle downwind of sleeping tents.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "edge_phase": "Demonstrate, Guide & Enable",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/cooking_p047_img1.png",
                "pamphlet_excerpts": [
                    "Caloric Density for the Trail (Req 6a-6b): Aim for 100 to 125+ calories per ounce (3,000-4,500 kcal/day) using shelf-stable whole grains, dehydrated vegetables, jerky/tuna pouches, nuts, and olive oil.",
                    "Pre-Trek Repackaging (Req 6c): Transfer ingredients from cardboard boxes into labeled resealable freezer bags with cooking water measurements written on the outside.",
                    "One-Pot Backpacking Stove Efficiency (Req 6d): Use a windscreen around upright/remote canister stoves, keep lids on pots to save fuel, and rehydrate meals in an insulated cozy.",
                    "Bearmuda Triangle & Odor Control (Req 6e-6f): Cook, wash dishes, and hang bear bags (12 ft above ground, 6 ft from tree trunk, 4 ft below branch) or place bear canisters 100-200 feet downwind from sleeping tents.",
                ],
                "worked_example": {
                    "title": "Ultralight Backpacking Menu & Repackaging Plan (No Refrigeration)",
                    "artifact_type": "BACKPACKING MENU LOG",
                    "fields": {
                        "Trail Breakfast (Boil-in-Bag)": "Instant rolled oats + powdered whole milk + chia seeds + dried cranberries & walnuts (620 kcal, 4.8 oz dry weight)",
                        "Trail Snack (GORP Energy Mix)": "Roasted almonds, cashews, sunflower seeds, raisins, pretzel sticks & dark chocolate M&Ms (480 kcal, 3.5 oz)",
                        "Trail Dinner (One-Pot Simmer)": "Couscous + foil-pouch salmon + sun-dried tomatoes + freeze-dried peas + 1 tbsp olive oil packet (780 kcal, 5.6 oz)",
                        "Fuel & Waste Footprint": "Requires 18g isobutane fuel total; all packaging nests into a single 1-quart zip-top trash bag to pack out",
                    },
                    "counselor_tip": "Never sleep in the clothes you wore while cooking pungent meals in bear country, and store toothpaste, lip balm, and trash inside your bear bag or canister.",
                },
                "topic_slides": [
                    {
                        "title": "Wildlife-Proof Food Storage & Backpacking Stoves",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/cooking_p047_img1.png",
                        "caption": "Raccoon raiding unsecured camp food, illustrating why wildlife-proof food storage and bear bags are essential.",
                        "bullets": [
                            "Backcountry Trail Discipline: Combine lightweight shelf-stable meals (100+ kcal/oz) with strict Bearmuda Triangle odor isolation (100-200 ft between sleeping tents, cooking area, and bear hang/canister).",
                        ],
                    },
                    {
                        "title": "Worked Example: No-Refrigeration Backpacking Menu",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "Ultralight Backpacking Menu & Repackaging Plan (No Refrigeration)",
                            "artifact_type": "BACKPACKING MENU LOG",
                            "fields": {
                                "Trail Breakfast (Boil-in-Bag)": "Instant rolled oats + powdered whole milk + chia seeds + dried cranberries & walnuts (620 kcal, 4.8 oz dry weight)",
                                "Trail Snack (GORP Energy Mix)": "Roasted almonds, cashews, sunflower seeds, raisins, pretzel sticks & dark chocolate M&Ms (480 kcal, 3.5 oz)",
                                "Trail Dinner (One-Pot Simmer)": "Couscous + foil-pouch salmon + sun-dried tomatoes + freeze-dried peas + 1 tbsp olive oil packet (780 kcal, 5.6 oz)",
                                "Fuel & Waste Footprint": "Requires 18g isobutane fuel total; all packaging nests into a single 1-quart zip-top trash bag to pack out",
                            },
                            "counselor_tip": "Never sleep in the clothes you wore while cooking pungent meals in bear country, and store toothpaste, lip balm, and trash inside your bear bag or canister.",
                        },
                        "bullets": [
                            "Trail Breakfast (Boil-in-Bag): Instant rolled oats + powdered milk + chia seeds + dried cranberries & walnuts (620 kcal, 4.8 oz)",
                            "Trail Snack (GORP Energy Mix): Roasted almonds, cashews, sunflower seeds, raisins, pretzels & dark chocolate (480 kcal, 3.5 oz)",
                            "Trail Dinner (One-Pot Simmer): Couscous + foil-pouch salmon + sun-dried tomatoes + freeze-dried peas + olive oil (780 kcal, 5.6 oz)",
                            "Fuel & Waste Footprint: 18g isobutane fuel total; all packaging nests into one 1-quart zip-top trash bag",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout presents a no-refrigeration backpacking menu, repackaged ingredients, and verification of preparing 2 trail meals and 1 trail snack with Leave No Trace cleanup.",
            },
            {
                "req_id": "7",
                "req_number": "7",
                "topic_title": "Req 7: Culinary Careers, Nutrition Science & Lifelong Skills",
                "action_verb": "Discuss",
                "req_text": "Food-Related Careers. Find out about three career opportunities in cooking, culinary arts, food science, or dietetics. Pick one and find out the education, training, and experience required, and discuss this with your counselor, explaining why this profession might interest you.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_image_path": "assets/pamphlet_images/cooking_p081_img1.png",
                "pamphlet_excerpts": [
                    "Executive Chef & Culinary Arts: Leads commercial kitchen brigade menu design, food costing, and ServSafe sanitation; trained via ACF apprenticeship or culinary institute degree.",
                    "Registered Dietitian Nutritionist (RDN): Designs clinical, sports, and public-health nutrition programs; requires an accredited degree, supervised practice internship, and CDR board exam.",
                    "Food Scientist & Technologist: Develops shelf-stable rations (including NASA and backpacking freeze-dried foods), flavor chemistry, and packaging safety; requires a B.S./M.S. in Food Science.",
                    "Public Health & USDA Food Safety Inspector: Audits farms, processing plants, and restaurants for HACCP compliance and pathogen prevention.",
                ],
                "topic_slides": [
                    {
                        "title": "Exploring Careers in Culinary Arts, Nutrition & Food Science",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/cooking_p081_img1.png",
                        "caption": "Food safety and quality assurance specialists inspecting commercial egg processing in a food facility.",
                        "bullets": [
                            "Executive Chef / Sous Chef: Combines culinary artistry, high-tempo team leadership, inventory budgeting, and ServSafe Manager certification.",
                            "Registered Dietitian Nutritionist (RDN): Applies biochemistry and nutrition science to optimize athletic performance and manage medical diets.",
                            "Food Scientist / Product Developer: Formulates freeze-dried trail meals, plant-based proteins, and safe food preservation systems.",
                            "Hospitality & Restaurant Management: Oversees supply-chain sourcing, farm-to-table sustainability, and commercial food service operations.",
                        ],
                    },
                    {
                        "title": "Worked Example: Career Pathway Comparison",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "Culinary & Food Science Career Research — Chef vs. Dietitian",
                            "artifact_type": "CAREER RESEARCH PROFILE",
                            "fields": {
                                "1. Executive Chef": "Associate/Bachelor degree in Culinary Arts (CIA/Johnson & Wales) or 3-year ACF apprenticeship + ServSafe certification",
                                "2. Registered Dietitian (RDN)": "ACEND-accredited university program + 1,000-hour supervised clinical practice + national CDR registration exam",
                                "3. Food Scientist": "B.S. in Food Science, Chemistry, or Microbiology; works in R&D labs, USDA/FDA, or outdoor ration companies",
                                "Scouting Connection": "Patrol menu planning, budgeting, sanitation, and leadership under pressure directly build these career skills",
                            },
                            "counselor_tip": "Ask Scouts which part of earning the Cooking Merit Badge they enjoyed most—creative recipe cooking, nutrition science, or outdoor logistics—to connect to a career path.",
                        },
                        "bullets": [
                            "1. Executive Chef: Culinary degree or ACF apprenticeship + ServSafe Manager certification",
                            "2. Registered Dietitian (RDN): Accredited nutrition degree + 1,000-hour supervised internship + CDR board exam",
                            "3. Food Scientist: B.S. in Food Science/Chemistry; develops shelf-stable and freeze-dried foods",
                            "Scouting Connection: Patrol menu planning, budgeting, sanitation, and leadership build real culinary skills",
                        ],
                    },
                ],
                "counselor_signoff_criteria": "Scout researches 3 food-related careers and discusses the education, training, and experience required for 1 chosen profession.",
            },
        ],
    },
    "Personal Fitness": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Personal%20Fitness.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/personal-fitness/",
        "requirements": [
            {
                "req_id": "1a",
                "req_number": "1a",
                "parent_id": "1",
                "action_verb": "Complete",
                "req_text": "Before completing requirements 2 through 9, have your health-care practitioner give you a physical examination using the Scouts BSA Annual Health and Medical Record form.",
                "safety_callout": "Medical records must be kept confidential by adult leaders; obtain physician clearance before starting intensive training.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Explain",
                "req_text": "Explain to your counselor the four components of physical fitness (cardiorespiratory endurance, muscular strength/endurance, flexibility, and body composition) and the FITT principle.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "6",
                "req_number": "6",
                "action_verb": "Demonstrate",
                "req_text": "Complete the aerobic (1-mile run/walk), muscular strength (push-ups, pull-ups, sit-ups), and flexibility (sit-and-reach) baseline fitness tests and record your results.",
                "safety_callout": "Warm up for 5 to 10 minutes prior to testing and stop exercise immediately if feeling dizzy or short of breath.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
            {
                "req_id": "8",
                "req_number": "8",
                "action_verb": "Complete",
                "req_text": "Outline and follow a comprehensive 12-week personal physical fitness program, keeping a daily log of your workouts and repeating the fitness tests at Weeks 4, 8, and 12.",
                "safety_callout": "Hydrate before, during, and after every training session.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
        ],
    },
    "Environmental Science": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Environmental%20Science.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/environmental-science/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "action_verb": "Explain",
                "req_text": "Make a timeline of the history of environmental science in America, including the contribution of the Boy Scouts of America to conservation.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Define",
                "req_text": "Define population, community, ecosystem, biosphere, symbiosis, niche, habitat, conservation, threatened species, endangered species, and extinction.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "3",
                "req_number": "3",
                "action_verb": "Demonstrate",
                "req_text": "Complete biological, water pollution, air pollution, land pollution, endangered species, and pollination experiments and observations.",
                "safety_callout": "Wear eye protection and gloves when handling soil/water samples or lab reagents.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
            {
                "req_id": "4",
                "req_number": "4",
                "action_verb": "Observe",
                "req_text": "Choose two outdoor study areas that are very different from one another and conduct ecological plot observations of species density and biodiversity.",
                "safety_callout": "Use the Buddy System and check for ticks and poisonous plants during field study.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
        ],
    },
    "Emergency Preparedness": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Emergency%20Preparedness.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/emergency-preparedness/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "action_verb": "Complete",
                "req_text": "Earn the First Aid merit badge prior to completing Emergency Preparedness.",
                "safety_callout": "First Aid skills form the mandatory foundation for all emergency response operations.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
            {
                "req_id": "2a",
                "req_number": "2a",
                "parent_id": "2",
                "action_verb": "Explain",
                "req_text": "Discuss with your counselor the five aspects of emergency preparedness: Prevention, Protection, Mitigation, Response, and Recovery.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2b",
                "req_number": "2b",
                "parent_id": "2",
                "action_verb": "Prepare",
                "req_text": "Create a chart showing how your family and troop would Prevent, Protect, Mitigate, Respond to, and Recover from 10 emergency situations.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "8b",
                "req_number": "8b",
                "parent_id": "8",
                "action_verb": "Prepare",
                "req_text": "Prepare a personal emergency service pack for a mobilization call and a 72-hour family emergency kit.",
                "safety_callout": "Store water (1 gallon per person per day for 3 days) and check battery/food expiration dates semi-annually.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
        ],
    },
    "Lifesaving": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Lifesaving.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/lifesaving/",
        "requirements": [
            {
                "req_id": "1a",
                "req_number": "1a",
                "parent_id": "1",
                "action_verb": "Explain",
                "req_text": "Before doing requirements 2 through 17, review with your counselor the principles of BSA Safe Swim Defense.",
                "safety_callout": "All water rescues and training require BSA Safe Swim Defense, qualified supervision, and Certified Lifeguards.",
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Demonstrate",
                "req_text": "Pass the BSA Swimmer test (400-yard continuous swim using four strokes) and explain the Order of Water Rescue: Reach, Throw, Row, Go with Support.",
                "safety_callout": "Always prioritize non-contact Reach and Throw rescues before entering the water.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
            {
                "req_id": "8",
                "req_number": "8",
                "action_verb": "Demonstrate",
                "req_text": "Demonstrate buoyant aid rescues, line rescues, and defensive escapes (block, wrist-grip escape, and rear head-hold escape) in deep water.",
                "safety_callout": "Practice contact escapes only under direct supervision of an Aquatics Instructor or Lifeguard.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
        ],
    },
    "Personal Management": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Personal%20Management.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/personal-management/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "action_verb": "Prepare",
                "req_text": "Choose an item that your family might want to purchase that is considered a major expense, and develop a comparison shopping and savings plan.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2a",
                "req_number": "2a",
                "parent_id": "2",
                "action_verb": "Prepare",
                "req_text": "Prepare a budget reflecting your expected income, allowance, gifts, and expenses, and track actual cash flow for 13 consecutive weeks.",
                "safety_callout": None,
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
            {
                "req_id": "4",
                "req_number": "4",
                "action_verb": "Explain",
                "req_text": "Explain the difference between saving and investing, compound interest, stocks, mutual funds, bonds, and risk vs. return.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
        ],
    },
    "Swimming": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Swimming.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/swimming/",
        "requirements": [
            {
                "req_id": "1a",
                "req_number": "1a",
                "parent_id": "1",
                "action_verb": "Explain",
                "req_text": "Explain the eight points of BSA Safe Swim Defense and how to prevent and treat hypothermia, dehydration, sunburn, cramps, and swimmer's ear.",
                "safety_callout": "Strictly enforce all 8 points of BSA Safe Swim Defense and the Buddy System during all aquatic activities.",
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Demonstrate",
                "req_text": "Pass the BSA Swimmer classification test: jump feetfirst into water over the head, swim 75 yards in a strong manner, swim 25 yards using an easy resting backstroke, and float.",
                "safety_callout": "Conduct swim tests in a clearly marked area with lifeguards on station.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
            {
                "req_id": "3",
                "req_number": "3",
                "action_verb": "Demonstrate",
                "req_text": "Swim 150 yards continuously using front crawl, sidestroke, breaststroke, and elementary backstroke with proper breathing and kick mechanics.",
                "safety_callout": None,
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
        ],
    },
    "Sustainability": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Sustainability.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/sustainability/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "action_verb": "Explain",
                "req_text": "Describe the meaning of sustainability in your own words and explain the importance of conservation and stewardship of natural resources.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Complete",
                "req_text": "Complete sustainability action projects and household audits across Water, Food, Community, Energy, and Stuff (waste reduction and circular lifecycle).",
                "safety_callout": "Have an adult assist when inspecting household water heaters, utility meters, or breaker panels.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
        ],
    },
    "Family Life": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Family%20Life.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/family-life/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "action_verb": "Discuss",
                "req_text": "Prepare an outline on what a family is and discuss with your counselor why families are important to individuals and to society.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "3",
                "req_number": "3",
                "action_verb": "Prepare",
                "req_text": "Prepare a list of your regular home duties or chores (at least five) and do them for 90 days, keeping a daily record of how often you do each of them.",
                "safety_callout": None,
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
            {
                "req_id": "6a",
                "req_number": "6a",
                "parent_id": "6",
                "action_verb": "Plan",
                "req_text": "Plan and carry out a family meeting covering topics such as family emergency preparedness, household finances, or shared goals.",
                "safety_callout": None,
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
        ],
    },
    "Hiking": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Hiking.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/hiking/",
        "requirements": [
            {
                "req_id": "1a",
                "req_number": "1a",
                "parent_id": "1",
                "action_verb": "Explain",
                "req_text": "Explain to your counselor the most likely hazards you may encounter while hiking, including blister care, hypothermia, heat reactions, lightning, and lost-hiker STOP protocol.",
                "safety_callout": "Always hike with the Buddy System, file a written trip plan, and carry the BSA Ten Essentials.",
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "3",
                "req_number": "3",
                "action_verb": "Explain",
                "req_text": "Explain how proper footwear selection, sock layering, pack weight distribution, and pace regulation prevent trail injuries.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "4",
                "req_number": "4",
                "action_verb": "Complete",
                "req_text": "Take four 10-mile hikes, one 15-mile hike, and one continuous 20-mile hike in a single day, submitting a written hike plan and post-hike reflection for each.",
                "safety_callout": "All conditioning hikes require Two-Deep Adult Leadership and road-walking high-visibility safety gear where applicable.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
        ],
    },
    "Cycling": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Cycling.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/cycling/",
        "requirements": [
            {
                "req_id": "1a",
                "req_number": "1a",
                "parent_id": "1",
                "action_verb": "Explain",
                "req_text": "Explain to your counselor the most likely hazards you may encounter while participating in cycling activities and how to prevent and respond to road/trail crashes and heat illness.",
                "safety_callout": "Mandatory CPSC-approved bicycle helmet must be worn and properly buckled at all times when riding.",
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Demonstrate",
                "req_text": "Clean and adjust a bicycle, perform the ABC Quick Check (Air, Brakes, Cranks/Chain, Quick releases), and demonstrate fixing a flat tire.",
                "safety_callout": None,
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
            {
                "req_id": "6",
                "req_number": "6",
                "action_verb": "Complete",
                "req_text": "Complete the road cycling (two 10-mile, two 15-mile, two 25-mile, and one 50-mile ride) or mountain biking trek progression.",
                "safety_callout": "Ride single-file with traffic flow, use hand turn signals, and maintain Two-Deep Adult Leadership.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
        ],
    },
    "Citizenship in Society": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Citizenship%20in%20Society.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/citizenship-in-society/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "action_verb": "Discuss",
                "req_text": "Discuss with your counselor how the Scout Oath and Scout Law guide ethical leadership, respect for all individuals, and welcoming everyone in your unit.",
                "safety_callout": "Maintain a respectful, youth-led Socratic discussion environment adhering to BSA Youth Protection.",
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Explain",
                "req_text": "Explain what ethical leadership means and how being an upstander helps prevent bullying, hazing, and exclusion in Scouting and school.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
        ],
    },
    "Weather": {
        "is_eagle_required": False,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Weather.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/weather/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "topic_title": "Req 1: Meteorology, Weather vs. Climate & Industry Impacts",
                "action_verb": "Define",
                "req_text": "Define meteorology. Explain what weather is and what climate is. Discuss how the weather affects farmers, sailors, aviators, and the outdoor construction industry. Tell why weather forecasts are important to each of these groups.",
                "safety_callout": "Always check local National Weather Service forecasts before any outdoor Scouting activity.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "pamphlet_excerpts": [
                    "Definition of Meteorology: Meteorology is the scientific study of Earth's atmosphere and its weather, from Greek 'meteoron' (things high in the air) and 'logos' (knowledge or discussion).",
                    "Weather vs. Climate: Weather refers to short-term (seconds to days) variations in the atmosphere, whereas climate is the average course or statistical condition of weather over 30+ years.",
                    "Impacts on Agriculture & Mariners: Farmers depend on rain timing and frost/hail forecasts to protect crops; mariners monitor wind, seas, dense fog, and freezing spray that can capsize vessels.",
                    "Impacts on Aviators & Construction: Aviators avoid airframe icing, severe turbulence, and low ceilings/visibility; construction crews plan concrete, roofing, and crane work around rain, wind, and temperature extremes.",
                ],
                "topic_slides": [
                    {
                        "title": "Meteorology & Core Atmospheric Variables",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_p019_img1.png",
                        "caption": "Analog dial thermometer (°C) and relative humidity hygrometer (%) used to measure core atmospheric variables.",
                        "bullets": [
                            "What Is Meteorology: The scientific study of Earth's atmosphere, its physical processes, and short-term weather patterns.",
                            "Greek Etymology: Derived from 'meteoron' (things high up in the air) and 'logos' (knowledge, study, or discussion).",
                            "Six Core Variables Measured: Air temperature, barometric pressure, wind speed and direction, relative humidity, cloud cover, and precipitation.",
                            "Operational Forecasting: Meteorologists combine surface instrument readings, upper-air radiosondes, Doppler radar, and satellites to predict atmospheric change.",
                        ],
                    },
                    {
                        "title": "Weather vs. Climate: Short-Term State vs. Long-Term Average",
                        "layout": "DIFFERENTIAL_COMPARISON_2COL",
                        "comparison_data": {
                            "left_header": "Weather (Immediate Atmosphere)",
                            "left_badge": "HOURS TO DAYS",
                            "left_points": [
                                "Time Scale: Short-term atmospheric variations occurring over minutes, hours, days, or a single week",
                                "What It Measures: Today's cold front, afternoon thunderstorm, wind gust, temperature, or snowfall",
                                "Forecast Horizon: Predicted by operational NWS meteorologists from 1 hour out to 7–10 days",
                                "Field Rule: 'Weather is what you get on a specific campout afternoon (pack your rain jacket today)'",
                            ],
                            "right_header": "Climate (Long-Term Statistics)",
                            "right_badge": "30+ YEAR NORMALS",
                            "right_points": [
                                "Time Scale: Long-term statistical average of weather at a region measured over 30 or more years",
                                "What It Measures: Seasonal temperature averages, annual precipitation totals, and regional freeze dates",
                                "Planning Horizon: Guides crop zone selection, building codes, and seasonal camp gear ratings",
                                "Field Rule: 'Climate is what you expect for the season (pack a 20°F sleeping bag for November in New England)'",
                            ],
                        },
                        "bullets": [
                            "Weather describes short-term atmospheric conditions (hours to days), while climate describes 30-year regional averages.",
                            "Mnemonic for Scouts: 'Climate is what you expect; weather is what you get.'",
                        ],
                    },
                    {
                        "title": "How Weather Affects Four Critical Industries",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Agriculture & Farming: Farmers rely on rainfall, frost, and hail forecasts to time planting, protect tender blossoms from freezes, irrigate during droughts, and harvest dry grain before storms.",
                            "Mariners & Ocean Shipping: Sailors track gale winds, wave fetch, dense marine fog, and subfreezing ocean spray that can coat a vessel's superstructure in heavy ice and capsize it.",
                            "Aviation & Flight Safety: Pilots check METARs and TAFs before every flight to avoid wing icing, microburst wind shear, severe thunderstorm turbulence, and low visibility ceilings.",
                            "Outdoor Construction: Project managers schedule concrete pours, asphalt paving, roofing, and high crane lifts around rain, freezing temperatures, summer heat waves, and high wind gusts.",
                        ],
                    },
                    {
                        "title": "Industry Weather Forecast Decision Matrix",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "Operational Forecast Thresholds & Protective Actions by Sector",
                            "artifact_type": "INDUSTRY_FORECAST_LOG",
                            "fields": {
                                "Farmers (Frost / Hail Alert)": "Overnight temp <= 32°F or severe hail threat -> Activate orchard wind machines/sprinklers or harvest ripe crops early.",
                                "Mariners (Gale / Freezing Spray)": "Winds >= 34 knots or freezing spray warning -> Plot alternative harbor refuge route and secure deck cargo.",
                                "Aviators (IFR / Icing / Wind Shear)": "Ceiling < 1,000 ft, visibility < 3 mi, or supercooled icing -> File Instrument Flight Rules (IFR) alternate or delay takeoff.",
                                "Construction (Crane & Concrete)": "Wind gusts > 25–30 mph or temp < 40°F -> Suspend tower crane picks, brace framing, and use heated concrete curing blankets.",
                            },
                            "counselor_tip": "Be ready to explain both how weather hazards impact each group AND why advance forecasts save lives and money.",
                        },
                        "bullets": [
                            "Advance weather forecasts allow farmers, captains, pilots, and construction superintendents to take protective action before hazards strike.",
                        ],
                    },
                ],
            },
            {
                "req_id": "2",
                "req_number": "2",
                "topic_title": "Req 2: Five Dangerous Weather Conditions, Safety Rules & Watch vs. Warning",
                "action_verb": "Explain",
                "req_text": "Name five dangerous weather-related conditions. Give the safety rules for each when outdoors and explain the difference between a severe weather watch and a warning. Discuss the safety rules with your family.",
                "safety_callout": "Seek enclosed shelter immediately when a Severe Weather Warning is issued or thunder is heard ('When Thunder Roars, Go Indoors').",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "pamphlet_excerpts": [
                    "Five Dangerous Weather Conditions: Winter storms (blizzards/ice), thunderstorms (lightning/hail), flash floods and floods, tornadoes, and hurricanes.",
                    "Outdoor Lightning & Storm Safety: Seek an enclosed building or hard-topped vehicle; avoid open fields, tall isolated trees, water, and metal objects.",
                    "Flood & Tornado Safety: Move to higher ground during floods and never wade or drive through moving water; shelter in a basement or interior room during a tornado.",
                    "Weather Watch vs. Warning: A Watch means hazardous weather conditions are possible (be prepared); a Warning means hazardous weather is occurring or imminent (take shelter now!).",
                ],
                "topic_slides": [
                    {
                        "title": "Thunderstorms, Lightning & Winter Blizzards",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_p036_img1.png",
                        "caption": "Cloud-to-ground lightning discharge beneath a severe cumulonimbus thunderstorm base ('When Thunder Roars, Go Indoors').",
                        "bullets": [
                            "Thunderstorms & Lightning: Every thunderstorm produces lightning; severe storms bring 58+ mph downdraft winds and hail >= 1 inch in diameter.",
                            "Lightning Outdoor Rules: Enter a substantial building or hard-topped metal vehicle immediately; avoid open fields, ridgelines, lakes, and isolated tall trees.",
                            "Winter Storms & Blizzards: Blizzards combine winds >= 35 mph with blowing snow reducing visibility below 1/4 mile for 3+ hours.",
                            "Winter Storm Outdoor Rules: Stay dry with breathable waterproof outer shells, cover exposed skin to prevent frostbite, avoid overexertion sweating, and build a windbreak shelter if stranded.",
                        ],
                    },
                    {
                        "title": "Flash Floods, Tornadoes & Hurricanes",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/ai_illustrations/weather_req_2_topic_visual.png",
                        "caption": "(Left) Climbing above a canyon flash flood; (Center) Tornado funnel and storm cellar; (Right) Coastal hurricane winds and storm surge.",
                        "bullets": [
                            "Flash Floods & Floods: Flash floods rise within minutes in canyons, dry washes, and streams; never camp in dry streambeds, climb to high ground immediately, and obey 'Turn Around, Don't Drown' (6 in. knocks you down; 12–24 in. floats a car).",
                            "Tornadoes: Violently rotating columns of air (up to 200–300 mph) descending from a thunderstorm; flying debris is the primary killer.",
                            "Tornado Safety Rules: Go to a basement or interior windowless room on the lowest floor; if caught outdoors far from shelter, lie flat face-down in a low dry ditch and cover your head.",
                            "Hurricanes: 60–600 mile wide tropical cyclones with winds >= 74 mph, torrential rain, and deadly coastal storm surge; evacuate early when ordered.",
                        ],
                    },
                    {
                        "title": "Outdoor Severe Weather Emergency Action Protocol",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Step 1 — 30/30 Lightning & Sky Check: Seek enclosed shelter as soon as thunder is heard or flash-to-bang time is 30 seconds or less (lightning within 6 miles); wait 30 minutes after the last thunder before resuming outdoor activity.",
                            "Step 2 — Last-Resort Open-Field Lightning Position: If trapped in the open far from buildings or vehicles, spread your patrol 50+ feet apart, avoid lone trees and metal poles, and crouch low on the balls of your feet covering your ears.",
                            "Step 3 — Flash Flood High-Ground Evacuation: Pitch tents well above floodplains and canyon bottoms; if water rises rapidly, abandon heavy camp gear and climb immediately to higher ground.",
                            "Step 4 — Family Emergency Plan Briefing: Review your home tornado shelter location, hurricane/flood evacuation route, and NOAA Weather Radio alert signals with your family.",
                        ],
                    },
                    {
                        "title": "Severe Weather Watch vs. Severe Weather Warning",
                        "layout": "DIFFERENTIAL_COMPARISON_2COL",
                        "comparison_data": {
                            "left_header": "Severe Weather WATCH",
                            "left_badge": "BE PREPARED — CONDITIONS FAVORABLE",
                            "left_points": [
                                "What It Means: Atmospheric ingredients are favorable for dangerous weather (tornado, severe thunderstorm, flood, or winter storm) to develop",
                                "Timing & Location: Exact timing and path are not yet certain; covers a broad multi-county region for several hours",
                                "Scout & Family Action: Monitor NOAA Weather Radio closely, review where the nearest sturdy shelter is, and pause exposed ridge or open-water trips",
                                "Analogy: 'All the ingredients for storm tacos are on the kitchen counter'",
                            ],
                            "right_header": "Severe Weather WARNING",
                            "right_badge": "TAKE ACTION NOW — IMMINENT DANGER",
                            "right_points": [
                                "What It Means: Dangerous weather is occurring right now or is imminent based on NWS Doppler radar or trained storm spotters",
                                "Timing & Location: Specific storm polygon tracking toward your immediate community within minutes",
                                "Scout & Family Action: Stop outdoor activities immediately and move to your basement, storm shelter, or higher ground right now",
                                "Analogy: 'The storm is fully made and at your front door—take shelter immediately!'",
                            ],
                        },
                        "bullets": [
                            "A Watch means hazardous weather is possible (be prepared); a Warning means hazardous weather is occurring or imminent (take shelter now).",
                        ],
                    },
                    {
                        "title": "Check for Understanding: Dangerous Weather Safety",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "question": "Your patrol is hiking across an open mountain meadow when dark cumulonimbus clouds build overhead, thunder rumbles 15 seconds after a lightning flash, and the NWS upgrades a Severe Thunderstorm Watch to a Warning. What should your patrol do?",
                            "options": [
                                "A) Huddle together under the tallest pine tree at the edge of the meadow to stay dry.",
                                "B) Pitch nylon tents in a rocky ravine so the canyon walls block the wind.",
                                "C) Descend off the open ridge toward an enclosed building or hard-topped vehicle; if caught in the open away from shelter, spread out 50+ feet apart and crouch low on the balls of your feet.",
                                "D) Keep hiking along the ridge since a Warning only means storms are possible later tonight.",
                            ],
                            "correct_option": "C",
                            "explanation": "A 15-second flash-to-bang means lightning is only 3 miles away, and a Warning means severe weather is imminent. Avoid tall isolated trees (A) and flash-flood ravines (B); seek enclosed shelter or use the dispersed low lightning crouch (C).",
                        },
                        "bullets": [
                            "Scenario Triage: Apply outdoor lightning, flash flood, and watch-vs.-warning safety rules during a patrol trek.",
                        ],
                    },
                ],
            },
            {
                "req_id": "3",
                "req_number": "3",
                "topic_title": "Req 3: Two Sources of Weather Forecasts for Outdoor Activities",
                "action_verb": "Identify",
                "req_text": "Identify at least two sources of weather forecasts that can be used to prepare for hikes, overnight camping, and other outdoor activities. Discuss with your counselor the types of information each source provides and how you can use them.",
                "safety_callout": "Always verify at least two independent weather forecast sources before departing on any backcountry hike or campout.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "pamphlet_excerpts": [
                    "Source 1 — NWS Point Forecasts (weather.gov): Provides 7-day hourly weather graphs, quantitative precipitation forecasts, wind gusts, and hazardous weather outlooks for any GPS trailhead.",
                    "Source 2 — NOAA Weather Radio All Hazards (NWR): Broadcasts continuous 24/7 VHF weather briefings (162.400–162.550 MHz) and Specific Area Message Encoding (SAME) alarm tones even when cell service fails.",
                    "Supplemental Sources: Local broadcast TV/radio meteorologists, aviation/marine briefings, and satellite messengers (Garmin inReach) for multi-day wilderness treks.",
                ],
                "topic_slides": [
                    {
                        "title": "Field Forecast Sources: Weather.gov & NOAA Weather Radio",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_p037_img1.png",
                        "caption": "Backcountry Scouts monitoring a portable NOAA Weather Radio All Hazards receiver and trail communication radio.",
                        "bullets": [
                            "Source 1 — National Weather Service (weather.gov): Official 7-day point forecasts tailored to exact elevation and latitude/longitude, including hourly temperature, wind chill, rain probability, and lightning risk.",
                            "Source 2 — NOAA Weather Radio All Hazards (NWR): Battery/hand-crank VHF receiver (162.400–162.550 MHz) broadcasting continuous local NWS office cycles and automatic emergency tone alerts.",
                            "Source 3 — Satellite Communicators & Local Broadcasts: Backcountry satellite messengers fetch updated spot forecasts beyond cell towers, while local TV/radio meteorologists explain regional storm tracks.",
                            "Why Two Sources Are Mandatory: Comparing a pre-trip web graphic with a live trailhead radio receiver ensures your patrol catches rapid frontal shifts.",
                        ],
                    },
                    {
                        "title": "NWS Doppler Radar & Hourly Forecast Graphs",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_p065_img1.png",
                        "caption": "National Weather Service WSR-88D Doppler radar reflectivity mosaic tracking severe thunderstorm precipitation bands.",
                        "bullets": [
                            "WSR-88D Doppler Radar Reflectivity: Measures precipitation intensity (dBZ from light green rain to red/purple heavy thunderstorm cores and hail) and storm speed/direction.",
                            " radial Velocity Scans: Detects rotation inside supercell thunderstorms (tornado signatures) and damaging straight-line wind gusts.",
                            "Hourly Weather Graph (Meteogram): Plots hour-by-hour temperature, dew point, wind speed/direction, sky cover %, and quantitative rainfall totals for campout planning.",
                            "Hazardous Weather Outlook (HWO): Summarizes days 1–7 severe storm, flash flood, fire weather, or winter storm potential for trip go/no-go decisions.",
                        ],
                    },
                    {
                        "title": "Pre-Campout Weather Forecast Verification Protocol",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "72 Hours Before Departure (Gear & Menu Planning): Check the NWS 7-day trailhead forecast for high/low temperatures and precipitation probability to select sleeping bag ratings, rain gear, and stove fuel.",
                            "24 Hours Before Departure (Route & Hazard Triage): Review the NWS Hourly Weather Graph and Hazardous Weather Outlook; identify bail-out trails if thunderstorms or high winds are forecast.",
                            "At the Trailhead (Final Go / No-Go Check): Tune your portable NOAA Weather Radio to the local VHF frequency and record barometric pressure and sky conditions in your trip log.",
                            "On the Trail (Continuous Monitoring): Listen to scheduled NOAA Weather Radio updates each morning and evening while watching cloud development and wind shifts.",
                        ],
                    },
                    {
                        "title": "Check for Understanding: Outdoor Forecast Sources",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "question": "Your troop is heading into a wilderness valley with zero cell phone reception for a 3-day weekend campout. Which combination of two forecast sources best prepares your patrol before and during the trip?",
                            "options": [
                                "A) A printed farmer's almanac and a smartphone social media app that requires 5G data.",
                                "B) Pre-trip NWS point forecast & hourly meteogram (weather.gov) for the trailhead elevation, plus a battery/hand-crank NOAA Weather Radio All Hazards receiver carried in camp.",
                                "C) Looking at the morning sky on Friday and guessing the weekend low temperature.",
                                "D) Checking the forecast for a city 200 miles away at sea level.",
                            ],
                            "correct_option": "B",
                            "explanation": "NWS point forecasts (weather.gov) adjust for exact mountain elevation before departure, and a portable VHF NOAA Weather Radio receives live NWS warnings in the backcountry without needing cell service.",
                        },
                        "bullets": [
                            "Combine pre-trip digital NWS elevation forecasts with an off-grid VHF NOAA Weather Radio receiver in the field.",
                        ],
                    },
                ],
            },
            {
                "req_id": "4",
                "req_number": "4",
                "topic_title": "Req 4: High & Low Pressure Systems, Cold Fronts & Warm Fronts",
                "action_verb": "Explain",
                "req_text": "Explain the difference between high and low pressure systems in the atmosphere. Tell which is related to good and to poor weather. Draw cross sections of a cold front and a warm front, showing the location and movements of the cold and warm air, the frontal slope, the locations and types of clouds associated with each type of front, and the location of precipitation.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "recommended_archetype": "DIFFERENTIAL_COMPARISON_2COL",
                "pamphlet_excerpts": [
                    "Atmospheric Pressure: The weight of the air column above a point on Earth's surface, averaging 14.7 pounds per square inch (1013.25 millibars / 29.92 inHg) at sea level.",
                    "High Pressure ('H' — Fair Weather): Associated with sinking (subsiding) air that warms and dries out as it descends, suppressing cloud formation and bringing clear skies.",
                    "Low Pressure ('L' — Stormy Weather): Associated with rising air that cools and condenses into clouds and precipitation; surface winds spiral counterclockwise and inward in the Northern Hemisphere.",
                    "Cold Fronts vs. Warm Fronts: Cold fronts have a steep slope where dense cold air wedges under warm air causing cumulonimbus storms; warm fronts have a gentle slope where warm air glides over cold air producing stratus/nimbostratus rain.",
                ],
                "topic_slides": [
                    {
                        "title": "High Pressure ('H') vs. Low Pressure ('L') Systems",
                        "layout": "DIFFERENTIAL_COMPARISON_2COL",
                        "comparison_data": {
                            "left_header": "High Pressure System ('H')",
                            "left_badge": "FAIR / GOOD WEATHER",
                            "left_points": [
                                "Vertical Air Motion: Sinking (subsiding) air column from aloft toward the surface",
                                "Warming & Drying: Descending air compresses and warms, lowering relative humidity and evaporating clouds",
                                "Northern Hemisphere Winds: Flows clockwise and slightly outward from the high-pressure center",
                                "Typical Field Weather: Clear skies, light winds, good visibility, and settled fair weather",
                            ],
                            "right_header": "Low Pressure System ('L')",
                            "right_badge": "POOR / STORMY WEATHER",
                            "right_points": [
                                "Vertical Air Motion: Converging, rising (ascending) air column from the surface aloft",
                                "Cooling & Condensation: Rising air expands and cools to its dew point, forming clouds and precipitation",
                                "Northern Hemisphere Winds: Spirals counterclockwise and inward toward the low-pressure center",
                                "Typical Field Weather: Overcast clouds, steady rain or snow, gusty winds, and frontal storms",
                            ],
                        },
                        "bullets": [
                            "Atmospheric pressure averages 14.7 psi (29.92 inHg / 1013.25 mb) at sea level.",
                            "High pressure ('H') brings sinking air and fair weather; Low pressure ('L') brings rising air, clouds, and stormy weather.",
                        ],
                    },
                    {
                        "title": "Cold Front: Planar Map and Vertical Cross-Section",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s26_img1.png",
                        "bullets": [
                            "Dense cold air wedges sharply beneath warm moist air along a steep frontal slope, forcing rapid uplift, towering cumulonimbus clouds, and heavy showers or thunderstorms right along the front.",
                        ],
                        "caption": "Cold Front Cross-Section & Surface Map (Blue spiked line pointing in direction of cold air movement)",
                    },
                    {
                        "title": "Cold Front: 3D Profile & Cloud Sequence",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s27_img1.png",
                        "bullets": [
                            "Three-dimensional cold front profile showing advancing cold air (left), steep frontal boundary (1:50 to 1:100), vertically developing cumulonimbus (Cb) with heavy rain/lightning, and clearing cooler air behind.",
                        ],
                        "caption": "Cold Front 3D Cross-Section: Steep slope (1:50 to 1:100), narrow band of intense precipitation, rapid clearing",
                    },
                    {
                        "title": "Warm Front: Planar Map and Vertical Cross-Section",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s28_img1.png",
                        "bullets": [
                            "Advancing warm air glides up and over retreating cold air along a gentle frontal slope, creating a wide progression of cirrus, cirrostratus, altostratus, and nimbostratus clouds with steady rain ahead of the front.",
                        ],
                        "caption": "Warm Front Cross-Section & Surface Map (Red semicircles pointing in direction of warm air advance)",
                    },
                    {
                        "title": "Warm Front: 3D Profile & Temperature Inversion",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s29_img1.png",
                        "bullets": [
                            "Overrunning warm air rises gradually over a 600 km wedge of cold air, producing high cirrus (Ci) first, then cirrostratus (Cs), altostratus (As), nimbostratus (Ns) steady rain/snow, and fog.",
                        ],
                        "caption": "Warm Front 3D Cross-Section: Gentle frontal slope (1:200), broad precipitation shield ahead of boundary",
                    },
                    {
                        "title": "Check for Understanding: Pressure Systems & Fronts",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "question": "When drawing your cross-sections for your counselor, how does the frontal slope, cloud sequence, and precipitation zone of a Cold Front differ from a Warm Front?",
                            "options": [
                                "A) Cold fronts have a gentle 1:200 slope with drizzle far ahead; warm fronts have a steep slope with tornadoes.",
                                "B) Cold fronts have a steep wedge slope forcing rapid uplift, cumulonimbus storms, and a narrow band of heavy rain right along the front; warm fronts have a gentle overrunning slope producing a broad shield of Ci -> Cs -> As -> Ns clouds and steady rain ahead of the front.",
                                "C) Both fronts have identical slopes and only produce fair-weather cumulus clouds.",
                                "D) Warm air wedges underneath cold air in both fronts because warm air is denser.",
                            ],
                            "correct_option": "B",
                            "explanation": "Cold air is denser than warm air: in a cold front it plows steeply under warm air (cumulonimbus squalls along the boundary); in a warm front, warm air glides gently up over retreating cold air (widespread stratus/nimbostratus rain ahead of the boundary).",
                        },
                        "bullets": [
                            "Contrast frontal slope, air-mass density, cloud progression, and precipitation location when sketching your two cross-sections.",
                        ],
                    },
                ],
            },
            {
                "req_id": "5",
                "req_number": "5",
                "topic_title": "Req 5: What Causes Wind, Rain, Lightning & Hail",
                "action_verb": "Explain",
                "req_text": "Tell what causes wind, why it rains, and how lightning and hail are formed.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "pamphlet_excerpts": [
                    "What Causes Wind: Uneven solar heating creates pressure differences; air flows from High pressure to Low pressure (wind), demonstrated locally by daytime sea breezes and nighttime land breezes.",
                    "Why It Rains: Surface water evaporates into water vapor; rising air cools until saturated, condensing onto nuclei into cloud droplets that coalesce until heavy enough to fall as rain.",
                    "How Lightning Forms: Updrafts and colliding ice particles separate electrical charges inside a cumulonimbus cloud until a bolt of electricity jumps between opposite charge regions.",
                    "How Hail Forms: Strong thunderstorm updrafts repeatedly carry raindrops above the freezing level, adding concentric layers of ice until the hailstone falls to the ground.",
                ],
                "topic_slides": [
                    {
                        "title": "What Causes Wind: Pressure Gradients & Sea/Land Breezes",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s34_img1.png",
                        "bullets": [
                            "Uneven solar heating creates pressure differences (air flows from High to Low pressure). Top: Daytime Sea Breeze (warm air rises over sun-heated land; cool ocean air moves ashore). Bottom: Nighttime Land Breeze (warm air rises over water; cool land air flows offshore).",
                        ],
                        "caption": "Daytime Sea Breeze vs. Nighttime Land Breeze Thermal Circulation Cells",
                    },
                    {
                        "title": "Why It Rains: Evaporation, Cooling & Coalescence",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/ai_illustrations/weather_req_5_topic_visual.png",
                        "caption": "Precipitation Formation: Solar lake evaporation rising into a cumulus cloud, droplet collision-coalescence on nuclei, and valley rainfall.",
                        "bullets": [
                            "Step 1 — Evaporation & Uplift: Solar energy evaporates liquid water into water vapor gas, which is carried aloft by rising air currents or fronts.",
                            "Step 2 — Adiabatic Cooling & Saturation: As moist air rises into lower pressure, it expands and cools until it reaches 100% relative humidity (dew point).",
                            "Step 3 — Condensation Nuclei: Excess water vapor condenses onto microscopic dust, sea salt, or smoke particles to form tiny cloud droplets (~0.02 mm).",
                            "Step 4 — Collision & Coalescence: Cloud droplets collide and merge (or grow on ice crystals) into heavy raindrops (~2.0 mm, 1 million times larger) that gravity pulls to Earth.",
                        ],
                    },
                    {
                        "title": "How Lightning & Hail Form Inside Thunderstorms",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "1. Thunderstorm Charge Separation: Turbulent updrafts and downdrafts cause rising ice crystals and falling soft hail (graupel) to collide inside a cumulonimbus cloud.",
                            "2. Opposite Electrical Zones: Positive electrical charges accumulate near the upper anvil of the cloud, negative charges build in the lower cloud base, and a positive shadow forms on the ground below.",
                            "3. Lightning Discharge & Thunder: When voltage overcomes air's insulation, a massive spark jumps (cloud-to-ground or intra-cloud), heating the air channel to ~50,000°F and creating a sonic shockwave (thunder).",
                            "4. Concentric Hailstone Growth: Powerful updrafts sweep raindrops repeatedly above the 32°F (0°C) freezing level, freezing concentric rings of supercooled water onto the hailstone until it is too heavy to stay aloft.",
                        ],
                    },
                    {
                        "title": "Atmospheric Microphysics: Droplet & Hailstone Growth",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "Scale Comparison: From Condensation Nucleus to Severe Hailstone",
                            "artifact_type": "PRECIPITATION_PHYSICS_TABLE",
                            "fields": {
                                "Condensation Nucleus (Dust / Salt)": "0.0002 mm diameter — Microscopic aerosol particle on which water vapor first condenses.",
                                "Typical Cloud Droplet": "0.02 mm diameter — Too tiny and light to fall; suspended easily by gentle upward air currents.",
                                "Falling Raindrop (Coalescence)": "2.0 mm diameter (~1,000,000 cloud droplets merged) — Heavy enough to overcome updrafts and fall as rain.",
                                "Severe Thunderstorm Hailstone": "25+ mm (1.0+ inch, quarter size) — Cycled above the 32°F freezing level by 60+ mph updrafts, adding onion-like ice layers.",
                            },
                            "counselor_tip": "Emphasize that cloud droplets must grow roughly one million times in volume by collision-coalescence or ice-crystal growth before they can fall as rain.",
                        },
                        "bullets": [
                            "Compare the physical mechanism and particle scale of condensation nuclei, cloud droplets, raindrops, and layered hailstones.",
                        ],
                    },
                    {
                        "title": "Check for Understanding: Wind, Rain, Lightning & Hail",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "question": "When you slice open a large hailstone after a summer thunderstorm, you see alternating clear and milky-white rings of ice like an onion. What atmospheric process created those rings?",
                            "options": [
                                "A) The hailstone rolled across snowy ground after landing.",
                                "B) Strong thunderstorm updrafts repeatedly carried the ice pellet up above the 32°F freezing level through supercooled liquid water, adding a new layer of ice on each cycle before it grew too heavy to stay aloft.",
                                "C) Lightning bolts melted and refroze the raindrop in midair.",
                                "D) Gentle stratus clouds slowly froze fog droplets at ground level.",
                            ],
                            "correct_option": "B",
                            "explanation": "Hail forms only in cumulonimbus clouds with strong updrafts that cycle the growing hailstone above and below the freezing level through supercooled water droplets.",
                        },
                        "bullets": [
                            "Verify Scout understanding of pressure-gradient wind, coalescence rain, charge-separation lightning, and updraft hail accretion.",
                        ],
                    },
                ],
            },
            {
                "req_id": "6",
                "req_number": "6",
                "topic_title": "Req 6: Cloud Types in Low, Middle & Upper Levels of the Atmosphere",
                "action_verb": "Identify",
                "req_text": "Identify and describe clouds in the low, middle, and upper levels of the atmosphere. Relate these to specific types of weather.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "pamphlet_excerpts": [
                    "High Clouds (Above 20,000 ft): Cirrus (thin wispy mares' tails), Cirrocumulus, and Cirrostratus (halo around Sun/Moon); composed of ice crystals and often precede a warm front.",
                    "Middle Clouds (6,500 to 20,000 ft): Altocumulus (puffy mid-level patches) and Altostratus (gray sheet covering sky ahead of steady rain or snow).",
                    "Low Clouds (Below 6,500 ft): Stratus (uniform gray layer/fog aloft), Stratocumulus, and Nimbostratus (dark rain/snow cloud producing continuous precipitation).",
                    "Vertically Developing Clouds (Surface to 50,000 ft): Fair-weather Cumulus and towering Cumulonimbus thunderstorm clouds with anvil tops.",
                ],
                "topic_slides": [
                    {
                        "title": "Cloud Classification by Atmospheric Altitude Level",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s44_img1.png",
                        "bullets": [
                            "Visual guide to High Clouds (>20,000 ft AGL: Cirrus, Cirrocumulus, Cirrostratus), Middle Clouds (6,500–20,000 ft AGL: Altocumulus, Altostratus), Low Clouds (<6,500 ft AGL: Stratus, Stratocumulus, Nimbostratus), and Vertical Clouds (Cumulus, Cumulonimbus).",
                        ],
                        "caption": "Classification of Clouds by Altitude Level and Vertical Development",
                    },
                    {
                        "title": "High-Altitude Clouds (Above 20,000 Feet AGL)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_p025_img1.png",
                        "caption": "High-altitude cirrocumulus undulatus ('mackerel sky') ice-crystal clouds above 20,000 feet heralding an approaching front.",
                        "bullets": [
                            "Prefix 'Cirro-' & Ice Composition: High clouds form above 20,000 feet where air is subfreezing, so they are composed almost entirely of ice crystals.",
                            "Cirrus (Ci): Thin, wispy 'mares' tails' blown by high-altitude jet stream winds; indicate fair weather now but often signal an approaching warm front within 24–36 hours.",
                            "Cirrocumulus (Cc): High rippled rows of small white ice puffs resembling fish scales ('mackerel sky').",
                            "Cirrostratus (Cs): Thin, sheet-like veil of ice crystals that creates a distinctive 22° halo ring around the Sun or Moon ahead of an advancing storm system.",
                        ],
                    },
                    {
                        "title": "Middle, Low & Vertically Developing Clouds",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_p023_img1.png",
                        "caption": "Mid-level altocumulus cloud deck between 6,500 and 20,000 feet AGL above a pine forest.",
                        "bullets": [
                            "Middle Clouds ('Alto-', 6,500–20,000 ft): Altocumulus (gray/white rounded layers) and Altostratus (uniform gray sheet where the Sun looks like a dim frosted glass disc before rain/snow).",
                            "Low Clouds (Below 6,500 ft): Stratus (flat gray blanket producing mist/drizzle), Stratocumulus (low lumpy rolls), and Nimbostratus ('nimbo' = rain; dark gray layer producing steady, prolonged rain or snow).",
                            "Fair-Weather Cumulus: Fluffy, flat-bottomed 'cotton ball' heaps formed by gentle daytime thermals.",
                            "Cumulonimbus (Thunderheads): Towering vertical anvil clouds spanning from 2,000 ft up to 50,000+ ft that produce heavy downpours, lightning, hail, strong gusts, and tornadoes.",
                        ],
                    },
                    {
                        "title": "Field Cloud Observation & Weather Forecasting Protocol",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Step 1 — Estimate Cloud Base Altitude: Classify the cloud deck into High (>20,000 ft, wispy ice), Middle (6,500–20,000 ft, 'alto-'), Low (<6,500 ft, flat stratus), or Vertical (towering heaps).",
                            "Step 2 — Identify Latin Root Shape: Determine whether the cloud is 'cirrus' (curl/wisp), 'stratus' (flat layered sheet), 'cumulus' (puffy heap), or 'nimbus' (actively precipitating).",
                            "Step 3 — Watch Vertical Growth & Lowering Ceilings: A sequence of Cirrus -> Cirrostratus -> Altostratus -> Nimbostratus warns of a warm front; swelling Cumulus congestus warns of afternoon thunderstorms.",
                            "Step 4 — Check for Virga & Anvil Tops: Look for 'virga' (streaks of rain evaporating before hitting the ground) or flat glaciated anvil tops indicating severe cumulonimbus updrafts.",
                        ],
                    },
                    {
                        "title": "Check for Understanding: Cloud Types & Weather",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "question": "On Day 1 of a hike you see wispy Cirrus clouds, followed that night by a halo around the Moon in Cirrostratus, and by Day 2 morning a lowering gray sheet of Altostratus and dark Nimbostratus. What weather should your patrol expect?",
                            "options": [
                                "A) Immediate clearing and bone-dry desert heat.",
                                "B) An approaching Warm Front bringing widespread, steady rain or snow from the Nimbostratus deck.",
                                "C) A brief 10-minute fair-weather cumulus shower followed by blue skies.",
                                "D) No change in weather for the next week.",
                            ],
                            "correct_option": "B",
                            "explanation": "The classic descending cloud progression (Cirrus -> Cirrostratus halo -> Altostratus -> Nimbostratus) marks warm air overrunning cold air ahead of a warm front, bringing steady precipitation.",
                        },
                        "bullets": [
                            "Relate cloud altitude family and root morphology to current and approaching weather conditions.",
                        ],
                    },
                ],
            },
            {
                "req_id": "7",
                "req_number": "7",
                "topic_title": "Req 7: The Earth's Water (Hydrologic) Cycle",
                "action_verb": "Explain",
                "req_text": "Draw a diagram of the water cycle and label its major processes. Explain the water cycle to your counselor.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "pamphlet_excerpts": [
                    "Conservation of Earth's Water: The total amount of water on Earth does not change significantly; it is continuously recycled between oceans, atmosphere, and land.",
                    "Evaporation, Transpiration & Sublimation: Solar heat evaporates liquid water from oceans/lakes, plants release water vapor via transpiration, and snow/ice sublimes directly into vapor.",
                    "Condensation, Transportation & Precipitation: Rising water vapor cools and condenses into clouds, winds transport moisture over land, and precipitation falls as rain, snow, sleet, or hail.",
                    "Runoff, Infiltration & Groundwater Flow: Snowmelt and surface runoff flow into streams and rivers while infiltration recharges underground aquifers that return water to the oceans.",
                ],
                "topic_slides": [
                    {
                        "title": "The Earth's Hydrologic (Water) Cycle Illustrated",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s47_img1.png",
                        "bullets": [
                            "The Hydrologic Cycle: (1) Evaporation, (2) Transpiration, (3) Sublimation, (4) Condensation, (5) Transportation, (6) Precipitation, (7) Surface/Snowmelt Runoff, (8) Infiltration, (9) Groundwater Flow, (10) Plant Uptake.",
                        ],
                        "caption": "NOAA Hydrologic Cycle Diagram Showing All 10 Major Water Cycle Processes",
                    },
                    {
                        "title": "Atmospheric Moisture: Evaporation to Precipitation",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/ai_illustrations/weather_req_7_topic_visual.png",
                        "caption": "Hydrologic Moisture Cycle: Solar ocean evaporation and forest transpiration rising up a mountain slope to condense into rain clouds.",
                        "bullets": [
                            "Evaporation (Liquid -> Gas): Solar energy heats oceans, lakes, and rivers, turning liquid water into invisible water vapor (oceans supply ~90% of atmospheric moisture).",
                            "Transpiration & Sublimation: Trees and plants release water vapor through leaf pores (~10% of moisture), while high-altitude snow and ice sublime directly from solid to vapor.",
                            "Condensation & Advection (Transportation): Rising water vapor cools and condenses into liquid/ice clouds that winds transport across continents.",
                            "Precipitation: When condensed water droplets or ice crystals grow too heavy for cloud updrafts, moisture returns to Earth as rain, snow, sleet, or hail.",
                        ],
                    },
                    {
                        "title": "Watershed Return Pathways: Runoff, Infiltration & Aquifers",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "Diagram Checklist: Labeling Your Water Cycle Drawing for Requirement 7",
                            "artifact_type": "HYDROLOGIC_CYCLE_CHECKLIST",
                            "fields": {
                                "1. Upward Vapor Pathways": "Label Evaporation (from ocean/lake surface), Transpiration (from forest/plants), and Sublimation (from mountain snowpack).",
                                "2. Atmospheric Pathways": "Label Condensation (cloud formation aloft) and Transportation (wind moving clouds from ocean over land).",
                                "3. Downward Delivery": "Label Precipitation (rain and mountain snowfall falling from clouds to the watershed).",
                                "4. Terrestrial & Underground Return": "Label Snowmelt & Surface Runoff (streams/rivers to sea), Infiltration (percolation into soil), Plant Uptake, and Groundwater Flow.",
                            },
                            "counselor_tip": "Make sure your hand-drawn diagram includes arrows showing the continuous closed loop returning water back to the ocean.",
                        },
                        "bullets": [
                            "Include all four phases (upward vapor, atmospheric cloud transport, precipitation, and surface/groundwater return) on your labeled diagram.",
                        ],
                    },
                    {
                        "title": "Check for Understanding: The Hydrologic Cycle",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "question": "Which two processes are responsible for moving water from Earth's surface and vegetation upward into the atmosphere as invisible water vapor?",
                            "options": [
                                "A) Precipitation and Infiltration",
                                "B) Evaporation (from oceans, lakes, and soil) and Transpiration (from plants and trees), along with Sublimation from ice/snow",
                                "C) Condensation and Surface Runoff",
                                "D) Groundwater Flow and Advection",
                            ],
                            "correct_option": "B",
                            "explanation": "Evaporation (~90%) and plant transpiration (~10%), plus sublimation from snow/ice, supply the water vapor that rises and condenses into clouds.",
                        },
                        "bullets": [
                            "Trace how solar energy and gravity drive the continuous closed-loop recycling of Earth's water.",
                        ],
                    },
                ],
            },
            {
                "req_id": "8",
                "req_number": "8",
                "topic_title": "Req 8: Human Activities, Acid Rain, Pollution & Climate Impacts",
                "action_verb": "Identify",
                "req_text": "Identify some human activities that can alter the environment, and describe how they affect the climate and people.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "pamphlet_excerpts": [
                    "Acid Rain Defined: Rainwater mixed with sulfur dioxide (SO2) and nitrogen oxide (NOx) pollutants—primarily from coal-burning power plants and vehicles—forming dilute sulfuric and nitric acid.",
                    "Human Effects on the Atmosphere: Fossil-fuel emissions, desertification from overgrazing/mining, stratospheric ozone depletion from CFCs, and global warming from excess carbon dioxide (CO2).",
                    "Impacts on People & Environment: Acid rain damages forests and aquatic life; desertification reduces food production; ozone thinning increases UV skin cancer; warming raises sea levels.",
                ],
                "topic_slides": [
                    {
                        "title": "Acid Rain Chemistry & Industrial Air Pollution",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/ai_illustrations/weather_req_8_topic_visual.png",
                        "caption": "(Left) Factory and vehicle exhaust plumes; (Center) Cloud droplet chemical reaction inset; (Right) Acidic rain on mountain pines and lake.",
                        "bullets": [
                            "What Is Acid Rain: Precipitation contaminated with sulfur dioxide (SO2) and nitrogen oxides (NOx) emitted by coal-fired power plants, smelters, and motor vehicles.",
                            "Atmospheric Chemical Reaction: SO2 and NOx react with water vapor and oxygen in clouds to form dilute sulfuric acid and nitric acid, dropping rain pH below 5.0.",
                            "Ecosystem & Infrastructure Damage: Acidifies mountain lakes and streams (harming trout and amphibians), leaches calcium/magnesium from forest soils, and corrodes stone monuments.",
                            "Desertification & Deforestation: Overgrazing, strip mining, and clearing forests strip topsoil and alter regional rainfall and surface albedo.",
                        ],
                    },
                    {
                        "title": "Atmospheric Alterations & Impacts on Climate and People",
                        "layout": "DIFFERENTIAL_COMPARISON_2COL",
                        "comparison_data": {
                            "left_header": "Human Atmospheric Drivers",
                            "left_badge": "EMISSIONS & LAND USE",
                            "left_points": [
                                "Fossil Fuel Combustion (CO2 & Methane): Burning coal, oil, and gas increases greenhouse gas concentrations that trap outgoing infrared heat",
                                "Sulfur & Nitrogen Oxides (SO2 / NOx): Industrial smokestacks and vehicle exhaust create acid precipitation and ground-level photochemical smog",
                                "Ozone-Depleting CFCs: Halocarbon refrigerants/aerosols rose into the stratosphere and broke down protective ozone (O3) molecules",
                                "Deforestation & Urban Heat Islands: Replacing forests with dark asphalt/concrete absorbs solar heat and reduces carbon uptake",
                            ],
                            "right_header": "Effects on Climate & People",
                            "right_badge": "HEALTH & ECOSYSTEM IMPACTS",
                            "right_points": [
                                "Global Warming & Sea-Level Rise: Melting glaciers and thermal ocean expansion threaten low-lying coastal cities and intensify heat waves",
                                "Respiratory & Cardiovascular Illness: Fine particulates (PM2.5) and ground-level ozone trigger asthma, bronchitis, and heart strain",
                                "UV-B Radiation Exposure: Thinner stratospheric ozone allows more ultraviolet radiation to reach Earth, increasing skin cancer and cataracts",
                                "Agricultural & Water Stress: Desertification, shifting drought patterns, and acidified soils reduce crop yields and freshwater quality",
                            ],
                        },
                        "bullets": [
                            "Connect each human activity (fossil fuel combustion, SO2/NOx emissions, CFCs, land clearing) to its specific effect on climate and human health.",
                        ],
                    },
                    {
                        "title": "Mitigation & Clean Air Stewardship Actions",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "1. Clean Air Act Flue-Gas Scrubbers & Catalytic Converters: Power-plant smokestack scrubbers and vehicle catalytic converters remove SO2 and NOx before they form acid rain.",
                            "2. Montreal Protocol & Ozone Recovery: Global phaseout of chlorofluorocarbons (CFCs) has allowed the stratospheric ozone layer to steadily heal.",
                            "3. Clean Energy & Energy Efficiency: Transitioning to renewable energy (solar, wind, hydro) and improving building/vehicle efficiency cuts CO2 greenhouse emissions.",
                            "4. Reforestation & Sustainable Land Management: Planting trees, restoring wetlands, and preventing overgrazing protect watersheds and absorb atmospheric carbon.",
                        ],
                    },
                    {
                        "title": "Check for Understanding: Human Impacts on the Atmosphere",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "question": "How do sulfur dioxide (SO2) and nitrogen oxides (NOx) from burning fossil fuels alter precipitation, and how does excess carbon dioxide (CO2) affect global climate?",
                            "options": [
                                "A) SO2 and NOx cool the Earth's core, while CO2 destroys the stratospheric ozone layer.",
                                "B) SO2 and NOx react with water vapor in clouds to form sulfuric and nitric acid (acid rain that harms lakes and forests), while excess CO2 traps outgoing infrared heat in the atmosphere (warming global climate and raising sea levels).",
                                "C) Both gases immediately turn into pure oxygen when exposed to sunlight.",
                                "D) Human activities only affect indoor air and never reach the troposphere.",
                            ],
                            "correct_option": "B",
                            "explanation": "SO2 and NOx react with atmospheric moisture to produce acid rain, whereas CO2 is a long-lived greenhouse gas that traps infrared heat and drives climate warming.",
                        },
                        "bullets": [
                            "Distinguish between acid rain precursors (SO2/NOx), greenhouse gases (CO2/CH4), and ozone-depleting substances (CFCs).",
                        ],
                    },
                ],
            },
            {
                "req_id": "9",
                "req_number": "9",
                "topic_title": "Req 9: Earth's Axial Tilt & Global Climate Zones",
                "action_verb": "Describe",
                "req_text": "Describe how the tilt of Earth's axis helps determine the climate of a region near the equator, near the poles, and across the area in between.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "pamphlet_excerpts": [
                    "Earth's 23.5-Degree Axial Tilt: Earth's rotational axis is tilted 23.5 degrees relative to its orbital plane around the Sun, causing seasonal changes in solar angle and daylight length.",
                    "Equatorial vs. Polar Climates: At the Equator, the Sun is nearly straight overhead year-round (hot tropical climate); near the Poles, sunlight strikes at a low angle (cold polar climate).",
                    "Temperate Zones In Between: Between the tropics and polar circles lie the temperate zones (including the United States), experiencing distinct spring, summer, autumn, and winter seasons.",
                ],
                "topic_slides": [
                    {
                        "title": "Earth's 23.5° Axial Tilt, Orbit, Solstices & Equinoxes",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s54_img1.png",
                        "bullets": [
                            "Earth's annual orbit around the Sun showing the 23.5° axial tilt at the Summer Solstice (June), Autumnal Equinox (September), Winter Solstice (December), and Spring Equinox (March).",
                        ],
                        "caption": "Earth's 23.5° Axial Tilt, Orbit, Solstices, and Equinoxes Driving Global Seasons",
                    },
                    {
                        "title": "Solar Beam Angle Across Equator, Temperate & Polar Zones",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/ai_illustrations/weather_req_9_topic_visual.png",
                        "caption": "Solar Incidence Angles: Concentrated perpendicular rays at the Equator, angled mid-latitude rays, and grazing oblique rays at the Poles.",
                        "bullets": [
                            "Near the Equator (Tropics, 23.5°N to 23.5°S): Sunlight strikes nearly perpendicular (90°) year-round with ~12 hours of daylight daily, concentrating solar energy into a hot tropical climate.",
                            "Near the Poles (Arctic & Antarctic, >66.5° Latitude): Sunlight strikes at a low, oblique grazing angle spread over a wide surface area (plus months of winter darkness), creating a cold polar climate.",
                            "The Area In Between (Mid-Latitude Temperate Zones, 23.5° to 66.5°): Includes the continental United States; solar angle and daylight length shift substantially across the year, creating four distinct seasons.",
                            "Why Distance From the Sun Is Not the Cause: Earth is actually slightly closer to the Sun in January; seasons are caused by the 23.5° axial tilt, not orbital distance.",
                        ],
                    },
                    {
                        "title": "Global Climate Zone Comparison Matrix",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "How Earth's 23.5° Tilt Shapes the Three Major Latitude Regions",
                            "artifact_type": "CLIMATE_ZONE_MATRIX",
                            "fields": {
                                "1. Equatorial / Tropical Zone (0°–23.5°)": "High direct sun angle all year; ~12 hr daylight year-round -> Warm/hot temperatures every month; wet/dry seasons instead of winter.",
                                "2. Mid-Latitude Temperate Zone (23.5°–66.5°)": "Tilted toward Sun in June (long days, high sun -> warm summer) and away in December (short days, low sun -> cold winter) -> Four distinct seasons.",
                                "3. Polar Zone (66.5°–90° N/S)": "Very low grazing solar angle + high snow/ice reflectivity (albedo); 24-hr darkness in midwinter and 24-hr low sun in midsummer -> Frigid polar climate.",
                                "4. Solstice vs. Equinox Dates": "June 21 (N. Hemisphere Summer Solstice), Dec 21 (Winter Solstice), Mar 20 & Sep 22 (Equinoxes — equal 12-hr day/night worldwide).",
                            },
                            "counselor_tip": "Use a flashlight and a tilted globe (or basketball) to show your counselor how a direct beam at the equator concentrates light while a low-angle beam at the pole spreads out.",
                        },
                        "bullets": [
                            "Compare solar angle, day length, and seasonal temperature variation across the Equator, Temperate Mid-Latitudes, and Poles.",
                        ],
                    },
                    {
                        "title": "Check for Understanding: Axial Tilt & Climate Zones",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "question": "Why does the continental United States experience warm summers in June–August and cold winters in December–February, while regions near the Equator stay hot year-round?",
                            "options": [
                                "A) The Earth moves twice as close to the Sun every July and twice as far away every January.",
                                "B) Because Earth's axis is tilted 23.5°, the Northern Hemisphere tilts toward the Sun in June (higher sun angle and longer daylight hours) and tilts away in December, whereas the Equator receives nearly direct overhead sunlight all year.",
                                "C) Ocean tides push warm water north only during the summer months.",
                                "D) The Equator is higher in elevation and closer to the top of the troposphere.",
                            ],
                            "correct_option": "B",
                            "explanation": "Earth's 23.5° axial tilt controls both the angle of incoming solar rays and the number of daylight hours across latitudes throughout the year.",
                        },
                        "bullets": [
                            "Explain how solar incidence angle and daylight duration vary across the Equator, Poles, and Temperate Zones.",
                        ],
                    },
                ],
            },
            {
                "req_id": "10",
                "req_number": "10",
                "topic_title": "Req 10: Weather Instruments & 7-Day Log OR NWS Meteorologist Visit",
                "action_verb": "Demonstrate",
                "req_text": "Do ONE of the following: (a) Make one of the following instruments: wind vane, anemometer, rain gauge, or hygrometer. Keep a daily weather log for one week using information from this instrument as well as from other sources such as local radio and television broadcasts, NOAA Weather Radio All Hazards, or internet sources (with your parent or guardian's permission). Record the following information at the same time every day: wind direction and speed, temperature, precipitation, and types of clouds. Be sure to make a note of any morning dew or frost. In the log, also list the weather forecasts from radio or television at the same time each day and show how the weather really turned out. (b) Visit a National Weather Service office or talk with a local radio or television weathercaster, private meteorologist, local agricultural extension service officer, or university meteorology instructor. Find out what type of weather is most dangerous or damaging to your community. Determine how severe weather and flood warnings reach the homes in your community.",
                "safety_callout": "Always obtain parent/guardian permission before using internet weather sources and follow Two-Deep Leadership when visiting or interviewing a meteorologist.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "recommended_archetype": "WORKED_EXAMPLE_TEMPLATE",
                "pamphlet_excerpts": [
                    "Option 10a (Build Instrument & 7-Day Log): Construct a functional wind vane, anemometer, rain gauge, or hygrometer and record daily weather observations and forecasts at the same time each day for 7 days.",
                    "Option 10b (Interview a Weather Expert): Visit or interview an NWS meteorologist, broadcast weathercaster, private meteorologist, agricultural extension officer, or university professor.",
                    "Community Warning Systems: Determine which severe weather hazards are most dangerous to your community and how NWS warnings reach homes (NOAA Weather Radio, WEA, EAS, sirens).",
                ],
                "worked_example": {
                    "title": "Sample 7-Day Daily Weather Observation Log (Req 10a)",
                    "artifact_type": "WEATHER_LOG",
                    "fields": {
                        "Observation Time & Instrument": "07:00 AM Daily — Homemade Cup Anemometer & Rain Gauge",
                        "Day 1–3 Log Summary": "Day 1: NW 8 mph, 58°F, 0.00 in, Cirrus, Heavy Dew | Day 2: S 14 mph, 64°F, 0.42 in, Nimbostratus | Day 3: W 18 mph, 52°F, 0.10 in, Cumulus",
                        "Day 4–7 Log Summary": "Day 4: NW 6 mph, 49°F, 0.00 in, Clear, Light Frost | Day 5: SW 10 mph, 67°F, 0.00 in, Altocumulus | Day 6–7: S 15 mph, 71°F, Cumulonimbus",
                        "Forecast vs. Actual Comparison": "NWS 24-hr temperature forecasts were within 2°F on 6 of 7 days; Day 6 afternoon thunderstorm arrived 1 hour earlier than morning TV forecast.",
                    },
                    "counselor_tip": "Record your observations at the exact same time every day for 7 consecutive days and note any morning dew or frost.",
                },
                "topic_slides": [
                    {
                        "title": "Option 10a: Building a Wind Vane, Rain Gauge or Hygrometer",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_p048_img1.png",
                        "caption": "Scout wearing safety glasses cutting an aluminum arrow vane and tail fin to construct a directional wind vane.",
                        "bullets": [
                            "Wind Vane (Wind Direction): Pivoting arrow with a larger tail fin mounted on a free-spinning pin; always points into the direction the wind is blowing FROM (aligned with a compass to N, E, S, W).",
                            "Rain Gauge (Precipitation): Straight-sided cylinder and collector funnel with a calibrated ruler measuring rainfall in tenths/hundredths of an inch in an open area away from trees/roofs.",
                            "Hair Hygrometer (Relative Humidity): Uses a clean strand of human hair attached to a lightweight pointer card; hair cells lengthen as humidity rises and shorten as air dries.",
                            "Placement Rule: Mount your homemade instrument in an unobstructed outdoor spot so buildings or trees do not block wind or rainfall.",
                        ],
                    },
                    {
                        "title": "Option 10a/10b: Calibrating an Anemometer & NWS Expert Visit",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_p050_img3.png",
                        "caption": "Scout testing a homemade four-cup rotational anemometer built from paper cups and wooden dowels to measure wind speed.",
                        "bullets": [
                            "Four-Cup Anemometer (Option 10a): Four lightweight cups mounted on crossed wooden dowels that spin on a center spindle; mark one cup with a bold color to count revolutions per minute (RPM) and convert to mph.",
                            "Visiting a Weather Expert (Option 10b): Interview an NWS Weather Forecast Office (WFO) meteorologist, TV/radio weathercaster, private meteorologist, agricultural extension agent, or university professor.",
                            "Local Community Hazards (Option 10b): Identify which weather events cause the most damage locally (e.g., coastal hurricanes/nor'easters, Midwest tornadoes, canyon flash floods, or ice storms).",
                            "Warning Dissemination Chain (Option 10b): Trace how alerts travel from NWS Doppler radar to NOAA Weather Radio (SAME tones), Wireless Emergency Alerts (WEA), Emergency Alert System (EAS), and outdoor sirens.",
                        ],
                    },
                    {
                        "title": "DIY Weather Station Materials & Observation Checklist",
                        "layout": "GEAR_CHECKLIST_GRID",
                        "bullets": [
                            "Instrument Construction Supplies: Wooden dowels, 4 paper/plastic cups, straight pin, soda straw, aluminum/cardstock tail fin, straight-sided glass jar, ruler, waterproof tape, and safety glasses.",
                            "Site Orientation Tools: Magnetic compass (to align Wind Vane True/Magnetic North), stopwatch/watch (to count anemometer revolutions per minute), and outdoor thermometer.",
                            "7-Day Logbook & Forecast Sources: Printed 7-Day Weather Log table, NOAA Weather Radio or parent-approved weather.gov/TV forecast source, and pen.",
                            "Daily Same-Time Checklist: Record 1) Wind direction & speed, 2) Temperature, 3) Precipitation, 4) Cloud types, 5) Morning dew or frost, and 6) Forecast vs. actual outcome.",
                        ],
                    },
                    {
                        "title": "Worked Example: 7-Day Scout Weather Observation Log",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "7-Day Scout Weather Observation & Forecast Verification Log (Req 10a)",
                            "artifact_type": "DAILY_WEATHER_LOG",
                            "fields": {
                                "Daily Observation Rule": "Record measurements at the SAME time every day for 7 consecutive days (with parent permission for internet/NOAA radio sources).",
                                "Required Daily Entries": "1) Wind direction & speed, 2) Air temperature, 3) Precipitation amount, 4) Cloud types (Low/Middle/High), 5) Morning dew or frost.",
                                "Sample Day 2 & Day 4 Entries": "Day 2 (07:00): Wind SE 12 mph, 59°F, Rain 0.35 in, Nimbostratus, No Dew | Day 4 (07:00): Wind NW 5 mph, 31°F, 0.00 in, Clear, White Frost on grass.",
                                "Forecast vs. Actual Evaluation": "Compare the daily radio/TV/NWS forecast logged each morning against what actually happened and discuss why any frontal timing shifted.",
                            },
                            "counselor_tip": "Bring both your homemade weather instrument (or photo of it installed outdoors) and your completed 7-day log to your counselor review.",
                        },
                        "bullets": [
                            "Record wind direction/speed, temperature, precipitation, cloud types, morning dew/frost, and forecast vs. actual results for 7 consecutive days.",
                        ],
                    },
                ],
            },
            {
                "req_id": "11",
                "req_number": "11",
                "topic_title": "Req 11: Five-Minute Prepared Talk on Outdoor Weather Safety Rules",
                "action_verb": "Explain",
                "req_text": "Give a talk of at least five minutes to a group (such as your unit or a Cub Scout pack) explaining the outdoor safety rules in the event of lightning, flash floods, and tornadoes. Before your talk, share your outline with your counselor for approval.",
                "safety_callout": "Always have your Merit Badge Counselor review and approve your written speech outline BEFORE delivering your 5-minute presentation.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "pamphlet_excerpts": [
                    "Counselor Pre-Approval Rule: Write a structured 5-minute speech outline and get your Weather Merit Badge Counselor's sign-off before speaking to your troop, patrol, or Cub Scout pack.",
                    "Core Safety Topics Required: Must clearly explain outdoor safety actions for (1) Lightning, (2) Flash Floods, and (3) Tornadoes.",
                    "Engaging Your Audience: Use visual aids (cloud charts, lightning crouch demonstration, 'When Thunder Roars, Go Indoors' & 'Turn Around, Don't Drown' slogans) so younger Scouts remember the rules.",
                ],
                "topic_slides": [
                    {
                        "title": "Structuring Your 5-Minute Outdoor Weather Safety Talk",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/ai_illustrations/weather_req_11_topic_visual.png",
                        "caption": "Outdoor Safety Briefing: Uniformed Scout at a campsite easel pointing to a weather hazard flip-chart while addressing his patrol.",
                        "bullets": [
                            "Mandatory Pre-Approval Step: Share your written speech outline with your Merit Badge Counselor for review and approval BEFORE giving your talk.",
                            "Target Audience & Setting: Present to your Scout troop, patrol, Den/Cub Scout pack, or classroom for at least 5 full minutes.",
                            "Three Required Hazard Pillars: Dedicate ~90 seconds each to outdoor safety rules for (1) Lightning, (2) Flash Floods, and (3) Tornadoes, plus a 30-second intro and 30-second Q&A.",
                            "Active Demonstration Tip: Have the group practice spacing out and demonstrating the low lightning crouch or identifying safe campsite elevation on a topo map.",
                        ],
                    },
                    {
                        "title": "4-Step Preparation & Delivery Workflow",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Step 1 — Draft Your Timed 5-Minute Outline: Write clear bullet points covering Watch vs. Warning, Lightning rules, Flash Flood rules, and Tornado rules with time markers (0:00 to 5:00).",
                            "Step 2 — Obtain Counselor Outline Approval: Review your draft outline with your Weather Merit Badge Counselor and incorporate any feedback before scheduling your talk.",
                            "Step 3 — Prepare Visual Aids & Props: Bring a printed cloud chart, a portable NOAA Weather Radio, or a campsite map to keep Cub Scouts or troop members engaged.",
                            "Step 4 — Deliver the Talk & Log Sign-Off: Speak clearly for at least 5 minutes, answer audience questions, and have your unit leader or counselor verify completion.",
                        ],
                    },
                    {
                        "title": "Worked Example: Approved 5-Minute Speech Outline",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "Sample Counselor-Approved 5-Minute Outdoor Weather Safety Outline (Req 11)",
                            "artifact_type": "SPEECH_OUTLINE_TEMPLATE",
                            "fields": {
                                "0:00–0:45 Introduction (Watch vs. Warning)": "Hook audience with a real campout storm story; define Weather Watch (be prepared) vs. Warning (take shelter now!).",
                                "0:45–2:15 Pillar 1 — Lightning Safety": "'When Thunder Roars, Go Indoors' (30/30 rule); enclosed building or metal car; avoid open fields, water, and lone trees; demonstrate dispersed low crouch.",
                                "2:15–3:45 Pillar 2 — Flash Flood Safety": "Never camp in dry washes or narrow canyons; climb to high ground immediately (leave heavy gear); 'Turn Around, Don't Drown' (6 in. water knocks you down).",
                                "3:45–5:15 Pillar 3 — Tornado Safety & Summary": "Flying debris hazard; basement or interior windowless lowest-floor room; if trapped outdoors, lie flat face-down in a low dry ditch covering head and neck.",
                            },
                            "counselor_tip": "Practice your talk out loud with a stopwatch at home so you hit the 5-minute mark smoothly without rushing.",
                        },
                        "bullets": [
                            "Use a timed 4-part outline to cover Watch vs. Warning, Lightning, Flash Floods, and Tornadoes across 5+ minutes.",
                        ],
                    },
                    {
                        "title": "Check for Understanding: 5-Minute Weather Safety Talk",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "question": "Before you stand up in front of a Cub Scout pack or your patrol to deliver your 5-minute talk on lightning, flash flood, and tornado safety for Requirement 11, what required step must you complete first?",
                            "options": [
                                "A) Wait until an actual tornado warning is issued.",
                                "B) Prepare a written outline of your talk and share it with your Weather Merit Badge Counselor for approval BEFORE giving the talk.",
                                "C) Memorize the entire Weather Merit Badge pamphlet word-for-word without an outline.",
                                "D) Give a 60-second talk covering only sunny weather.",
                            ],
                            "correct_option": "B",
                            "explanation": "Requirement 11 explicitly specifies: 'Before your talk, share your outline with your counselor for approval,' and the talk must last at least five minutes covering lightning, flash floods, and tornadoes.",
                        },
                        "bullets": [
                            "Confirm counselor outline approval prior to delivering the 5-minute safety presentation.",
                        ],
                    },
                ],
            },
            {
                "req_id": "12",
                "req_number": "12",
                "topic_title": "Req 12: Careers in Meteorology, Training, Education & Responsibilities",
                "action_verb": "Explore",
                "req_text": "Explore careers related to this merit badge. Research one career to learn about the training and education needed, costs, job prospects, salary, job duties, and career advancement. Your research methods may include — with your parent or guardian's permission — an internet or library search, an interview with a professional in the field, or a visit to a workplace where people in this career work. Discuss with your counselor what you learned and how this career might suit your interests and talents.",
                "safety_callout": "Obtain parent or guardian permission before conducting internet research or scheduling a workplace visit with a meteorology professional.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "pamphlet_excerpts": [
                    "Career Opportunities: National Weather Service (NWS) operational forecaster, broadcast TV/radio meteorologist, private-sector/aviation/renewable-energy meteorologist, military weather officer, and NOAA/university atmospheric scientist.",
                    "Training & Education: Requires a Bachelor of Science (B.S.) or advanced degree (M.S./Ph.D.) in Meteorology or Atmospheric Science with coursework in calculus, differential equations, physics, thermodynamics, and computer modeling.",
                    "Duties, Prospects & Advancement: Forecasters analyze radar, satellite, and supercomputer numerical models on 24/7 operational shifts to protect life and property, advancing to Science & Operations Officer (SOO) or Warning Coordination Meteorologist (WCM).",
                ],
                "topic_slides": [
                    {
                        "title": "Career Pathways in Meteorology & Atmospheric Science",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_p073_img2.png",
                        "caption": "National Weather Service operational meteorologist analyzing satellite, Doppler radar, and numerical models at an AWIPS workstation.",
                        "bullets": [
                            "National Weather Service (NWS) Operational Forecaster: Staffs 122 regional Weather Forecast Offices (WFOs) 24/7, issuing public forecasts, aviation/marine briefings, and severe weather warnings.",
                            "Broadcast TV & Digital Meteorologist: Translates complex computer models into clear on-air graphics and conducts live continuous coverage during tornado or hurricane emergencies.",
                            "Private-Sector & Forensic Meteorologist: Advises airlines, ocean shipping fleets, wind/solar power grids, commodities traders, and emergency managers.",
                            "Military Weather Officer & Research Scientist: U.S. Air Force/Navy weather officers brief global flight and fleet missions; NOAA, NASA, and university scientists build climate and storm models.",
                        ],
                    },
                    {
                        "title": "Required Education, STEM Coursework & Training",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "University Degree (B.S. in Meteorology / Atmospheric Science): Operational NWS and private forecasting roles require a 4-year Bachelor of Science degree meeting federal GS-1340 meteorology standards.",
                            "Core Physics & Mathematics Foundation: Students complete multivariable calculus, differential equations, classical physics, atmospheric thermodynamics, and fluid dynamics.",
                            "Computer Programming & Remote Sensing: Modern meteorologists write Python/Fortran data scripts and interpret WSR-88D dual-polarization radar, GOES-R satellites, and ensemble supercomputer models.",
                            "Graduate Degrees & Certifications: Research scientists and university faculty earn M.S. or Ph.D. degrees; broadcast and consulting meteorologists earn the AMS Certified Broadcast/Consulting Meteorologist (CBM/CCM) seal.",
                        ],
                    },
                    {
                        "title": "Worked Example: Meteorology Career Research Profile",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "Sample Career Research Worksheet: NWS Operational Meteorologist (GS-1340)",
                            "artifact_type": "CAREER_RESEARCH_PROFILE",
                            "fields": {
                                "1. Education & Training Costs": "4-year B.S. in Meteorology/Atmospheric Science ($40k–$120k total in-state public university tuition; NOAA Hollings Scholarship & graduate assistantships available).",
                                "2. Daily Job Duties & Schedule": "Analyze upper-air soundings, Doppler radar, and numerical models; issue public/aviation forecasts and severe storm warnings on rotating 24/7 shifts (including nights/holidays).",
                                "3. Salary Range & Job Prospects": "Entry-level GS-5/7/9 ($45k–$68k) advancing to Journey/Senior Forecaster GS-12/13 ($90k–$125k+); strong growth in private renewable-energy and climate risk analytics.",
                                "4. Career Advancement Ladder": "Intern Meteorologist -> General Forecaster -> Lead Forecaster -> Warning Coordination Meteorologist (WCM) / Science & Operations Officer (SOO) -> Meteorologist-in-Charge (MIC).",
                            },
                            "counselor_tip": "Be ready to discuss how your personal interests in STEM, outdoor observation, computer modeling, or public communication connect to this career.",
                        },
                        "bullets": [
                            "Cover education, costs, job duties, salary range, job prospects, and advancement path during your counselor discussion.",
                        ],
                    },
                    {
                        "title": "Check for Understanding: Meteorology Careers",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "question": "Why do universities require meteorology students to complete rigorous coursework in calculus, differential equations, physics, and computer science?",
                            "options": [
                                "A) Because weather forecasting is based on guessing from historical almanacs.",
                                "B) Because meteorology is applied physics of the atmosphere—predicting how air pressure, temperature, moisture, and winds evolve requires solving fluid-dynamics and thermodynamic equations on supercomputers.",
                                "C) Only television news anchors need calculus to read a teleprompter.",
                                "D) Meteorologists only study rocks and tectonic plates.",
                            ],
                            "correct_option": "B",
                            "explanation": "Atmospheric motion and phase changes are governed by physical laws of fluid dynamics and thermodynamics modeled numerically on supercomputers.",
                        },
                        "bullets": [
                            "Synthesize training requirements, operational responsibilities, and career pathways in atmospheric science.",
                        ],
                    },
                ],
            },
        ],
    },
    "Robotics": {
        "is_eagle_required": False,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Robotics.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/robotics/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "action_verb": "Discuss",
                "req_text": "Discuss safety procedures when working with robotics, electricity, lithium-polymer batteries, soldering irons, and moving mechanical parts.",
                "safety_callout": "Always wear ANSI Z87.1-approved safety glasses around moving mechanisms, soldering, and cutting tools.",
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Explain",
                "req_text": "Explain the three degrees of freedom, robotic sensors (ultrasonic, optical encoder, gyroscope), and actuators (servos, DC gearmotors, pneumatics).",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "4",
                "req_number": "4",
                "action_verb": "Demonstrate",
                "req_text": "Design, build, program, and test a robot that can perform a specific task and document the engineering notebook.",
                "safety_callout": "Disconnect battery power before modifying wiring or mechanical drivetrain gears.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
            {
                "req_id": "5",
                "req_number": "5",
                "action_verb": "Demonstrate",
                "req_text": "Demonstrate your working robot to your Merit Badge Counselor and explain the control loop code and engineering notebook.",
                "safety_callout": None,
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
        ],
    },
    "Welding": {
        "is_eagle_required": False,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Welding.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/welding/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "action_verb": "Explain",
                "req_text": "Explain the health and safety hazards of welding, including toxic fumes, thermal burns, electrical shock, and arc-flash UV/IR radiation.",
                "safety_callout": "Mandatory PPE: auto-darkening welding helmet (shade 10-13), leather gauntlet gloves, closed leather boots, and flame-resistant cotton/leather jacket.",
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Explain",
                "req_text": "Explain how to set up, operate, and shut down GMAW (MIG), SMAW (Stick), GTAW (TIG), or FCAW welding equipment safely.",
                "safety_callout": "Ensure adequate fume extraction ventilation and ABC fire extinguishers are present within 10 feet before striking an arc.",
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "5",
                "req_number": "5",
                "action_verb": "Demonstrate",
                "req_text": "Demonstrate making a tack weld, square-groove butt joint, and T-joint fillet weld in the flat position on carbon steel plate.",
                "safety_callout": "Mark hot metal with soapstone ('HOT') and quench or cool safely using pliers.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
        ],
    },
    "Astronomy": {
        "is_eagle_required": False,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Astronomy.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/astronomy/",
        "requirements": [
            {
                "req_id": "1a",
                "req_number": "1a",
                "parent_id": "1",
                "action_verb": "Explain",
                "req_text": "Explain the hazards of direct solar observation, nighttime trip hazards, and cold/heat exposure during night-sky observing sessions.",
                "safety_callout": "NEVER look directly at the Sun through binoculars, a telescope, or an unfiltered camera viewfinder; permanent blindness occurs instantly without an ISO 12312-2 solar filter.",
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "3",
                "req_number": "3",
                "action_verb": "Explain",
                "req_text": "Compare refracting, Newtonian reflecting, and catadioptric (Schmidt-Cassegrain) telescopes and demonstrate setting up and aligning a finder scope.",
                "safety_callout": None,
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
            {
                "req_id": "4",
                "req_number": "4",
                "action_verb": "Identify",
                "req_text": "Identify in the night sky at least 10 constellations (including 4 in the zodiac) and 8 first-magnitude stars, and sketch the Big Dipper and Cassiopeia over several hours.",
                "safety_callout": "Use red-lens flashlights during night observing to preserve night vision and prevent tripping hazards.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
        ],
    },
    "Wilderness Survival": {
        "is_eagle_required": False,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Wilderness%20Survival.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/wilderness-survival/",
        "requirements": [
            {
                "req_id": "1a",
                "req_number": "1a",
                "parent_id": "1",
                "action_verb": "Explain",
                "req_text": "Explain the seven priorities of wilderness survival in order of importance and how the S.T.O.P. protocol (Stop, Think, Observe, Plan) prevents panic.",
                "safety_callout": "Always stay put when lost so Search and Rescue teams can locate you at your last known point.",
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "5",
                "req_number": "5",
                "action_verb": "Prepare",
                "req_text": "Put together a personal survival kit (signal mirror, whistle, fire starter, pocket knife, cordage, space blanket, water purification tablets, duct tape) and explain each item.",
                "safety_callout": "Carry valid Totin' Chip and Firem'n Chit credentials when packing knives and fire starters.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
            {
                "req_id": "8",
                "req_number": "8",
                "action_verb": "Improvised",
                "req_text": "Improvise a natural shelter (debris hut or tarp A-frame) for the environment and spend one overnight sleeping in the shelter you built.",
                "safety_callout": "Disassemble natural debris shelters after your campout in accordance with Leave No Trace principles.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
        ],
    },
    "Archery": {
        "is_eagle_required": False,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Archery.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/archery/",
        "requirements": [
            {
                "req_id": "1a",
                "req_number": "1a",
                "parent_id": "1",
                "action_verb": "Explain",
                "req_text": "State and explain the range safety rules, whistle commands (1 blast = Shoot, 2 blasts = Get Bows, 3 blasts = Walk to Target/Retrieve Arrows, 5+ blasts = Emergency Stop), and protective gear.",
                "safety_callout": "All live archery range shooting requires a USA Archery / BSA Certified Archery Director on the firing line and strict whistle discipline.",
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Demonstrate",
                "req_text": "Name and point out the parts of an arrow and a recurve or compound bow, and demonstrate stringing a bow, tying a nocking point, and making a bowstring.",
                "safety_callout": "Never dry-fire a bow without an arrow nocked on the string.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
            {
                "req_id": "4",
                "req_number": "4",
                "action_verb": "Shoot",
                "req_text": "Using a recurve or compound bow and the 11-step National Archery in the Schools Program (NASP) shot cycle, shoot a qualifying score on an official BSA target.",
                "safety_callout": "Wear an armguard and finger tab/glove, and never cross the shooting line until 3 whistle blasts sound.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
        ],
    },
}


# ==============================================================================
# INTELLIGENT REQUIREMENT ENRICHMENT HELPER (5-TIER DEEP RESEARCH)
# ==============================================================================

def _infer_action_verb_and_mode(req_text: str, explicit_verb: Optional[str] = None, explicit_mode: Optional[str] = None) -> tuple[str, str, str]:
    """Infers action_verb, execution_mode, and edge_phase from requirement text."""
    text_lower = req_text.strip().lower()
    first_word = req_text.strip().split()[0].rstrip(":,.") if req_text.strip() else "Explain"

    prereq_keywords = (
        "camp a total", "camp ", "visit ", "attend ", "volunteer", "12-week", "13 consecutive",
        "90 days", "five days in a row", "write a letter", "take four 10-mile", "physical examination",
        "spend one overnight", "plan and carry out", "plan, budget, and cook", "identify in the night sky",
        "earn the first aid", "choose two outdoor study",
    )
    station_keywords = (
        "demonstrate", "show ", "prepare a personal", "complete the aerobic", "design, build",
        "build a ", "pass the bsa swimmer", "swim 150", "clean and adjust", "shoot a qualifying",
        "put together a personal",
    )

    if explicit_mode:
        mode = explicit_mode
    elif any(k in text_lower for k in prereq_keywords):
        mode = "PREREQUISITE_CAMPOUT_HOME"
    elif any(k in text_lower for k in station_keywords):
        mode = "HANDS_ON_SKILL_STATION"
    else:
        mode = "IN_CLASS_DISCUSSION"

    verb = explicit_verb or (first_word.capitalize() if len(first_word) > 2 else "Explain")
    if mode == "HANDS_ON_SKILL_STATION":
        edge = "Demonstrate, Guide & Enable"
    elif mode == "PREREQUISITE_CAMPOUT_HOME":
        edge = "Enable"
    else:
        edge = "Explain & Guide"
    return verb, mode, edge


def enrich_requirement_point(
    badge_name: str,
    req_dict: Dict[str, Any],
    idx: int = 0,
    total_reqs: int = 8,
    used_image_paths: Optional[set] = None,
) -> Dict[str, Any]:
    """Enriches any requirement dictionary using the official BSA Merit Badge Pamphlet PDF as the primary source of truth.

    Extracts:
    - `topic_title`: Subject-matter title from the pamphlet (never meta).
    - `pamphlet_citation`: Exact page citation in the official BSA Merit Badge Pamphlet.
    - `pamphlet_image_path`: Real photo, illustration, or diagram extracted from the BSA Merit Badge Pamphlet PDF.
    - `pamphlet_excerpts` & `step_by_step_procedure`: Summarized directly from the pamphlet pages.
    """
    from src.tools.pamphlet_extractor import (
        decompose_requirement_into_topic_slides,
        summarize_pamphlet_for_requirement,
    )

    enriched = dict(req_dict)
    req_num = str(enriched.get("req_number", str(idx + 1)))
    enriched.setdefault("req_id", req_num)
    if len(req_num) > 1 and req_num[-1].isalpha() and not enriched.get("parent_id"):
        enriched["parent_id"] = req_num[:-1]

    # Attach official sub_requirements from data/official_requirements_cache.json if not already present
    if not enriched.get("sub_requirements"):
        official_cache = _load_official_requirements_cache()
        badge_official = official_cache.get(badge_name) or []
        for off_r in badge_official:
            if str(off_r.get("req_number")) == req_num:
                if off_r.get("sub_requirements"):
                    enriched["sub_requirements"] = list(off_r["sub_requirements"])
                break

    req_text = enriched.get("req_text", f"Complete requirement {req_num} for {badge_name}.")
    verb, mode, edge = _infer_action_verb_and_mode(
        req_text,
        enriched.get("action_verb"),
        enriched.get("execution_mode"),
    )
    enriched["action_verb"] = verb
    enriched["execution_mode"] = mode
    enriched.setdefault("edge_phase", edge)

    pamphlet_info = summarize_pamphlet_for_requirement(
        badge_name=badge_name,
        req_number=req_num,
        req_text=req_text,
        req_index=idx,
        total_reqs=max(1, total_reqs),
        used_image_paths=set(used_image_paths) if used_image_paths else set(),
    )
    enriched.setdefault("topic_title", pamphlet_info.get("topic_title"))
    enriched.setdefault("pamphlet_citation", pamphlet_info.get("pamphlet_citation"))
    enriched.setdefault("pamphlet_pages", pamphlet_info.get("pamphlet_pages") or [])
    if pamphlet_info.get("pamphlet_image_path"):
        existing_img = str(enriched.get("pamphlet_image_path") or "")
        if not existing_img or "ai_illustrations" in existing_img:
            enriched["pamphlet_image_path"] = pamphlet_info["pamphlet_image_path"]
            if pamphlet_info.get("pamphlet_image_caption"):
                enriched["pamphlet_image_caption"] = pamphlet_info["pamphlet_image_caption"]
    if pamphlet_info.get("pamphlet_image_caption"):
        enriched.setdefault("pamphlet_image_caption", pamphlet_info["pamphlet_image_caption"])

    pamphlet_points = pamphlet_info.get("pamphlet_summary_points") or []

    # Populate pamphlet_excerpts from pamphlet_points ONLY when fewer than 4 curated excerpts exist
    if not enriched.get("pamphlet_excerpts"):
        if pamphlet_points:
            enriched["pamphlet_excerpts"] = pamphlet_points[:5]
        else:
            enriched["pamphlet_excerpts"] = [
                f"Core Concept ({badge_name} Req {req_num}): {req_text}",
                f"Safety & Field Practice: Apply the BSA Guide to Safe Scouting and Buddy System during all {badge_name} field work.",
            ]
    elif len(enriched["pamphlet_excerpts"]) < 4 and pamphlet_points:
        existing_excerpts = list(enriched["pamphlet_excerpts"])
        for pt in pamphlet_points:
            if len(existing_excerpts) < 4 and pt not in existing_excerpts:
                existing_excerpts.append(pt)
        enriched["pamphlet_excerpts"] = existing_excerpts

    # Populate step_by_step_procedure ONLY from distinct pamphlet teaching points (never duplicate pamphlet_excerpts[:4])
    if not enriched.get("step_by_step_procedure"):
        distinct_steps = [
            pt for pt in pamphlet_points[4:9]
            if pt not in (enriched.get("pamphlet_excerpts") or [])
        ]
        if len(distinct_steps) >= 3:
            enriched["step_by_step_procedure"] = distinct_steps[:4]
        else:
            enriched["step_by_step_procedure"] = []

    # Determine recommended_archetype and visual_diagram_type if not explicitly set
    if not enriched.get("recommended_archetype"):
        if enriched.get("comparison_data"):
            enriched["recommended_archetype"] = "DIFFERENTIAL_COMPARISON_2COL"
        elif enriched.get("worked_example"):
            enriched["recommended_archetype"] = "WORKED_EXAMPLE_TEMPLATE"
        elif enriched.get("gear_checklist"):
            enriched["recommended_archetype"] = "GEAR_CHECKLIST_GRID"
        elif enriched.get("quiz_item"):
            enriched["recommended_archetype"] = "SOCRATIC_CHECKPOINT_QUIZ"
        elif mode == "HANDS_ON_SKILL_STATION":
            enriched["recommended_archetype"] = "STEP_BY_STEP_PROCEDURE_4CARD" if idx % 2 == 0 else "HANDS_ON_PRACTICE_STATION"
        else:
            enriched["recommended_archetype"] = "SPLIT_VISUAL_EXPLAINER" if idx % 2 == 0 else "STEP_BY_STEP_PROCEDURE_4CARD"

    enriched.setdefault("visual_diagram_type", "pamphlet_figure")
    enriched.setdefault(
        "drg_video_links",
        [f"https://www.scouting.org/skills/merit-badges/digital-resource-guides/{badge_name.lower().replace(' ', '-')}/"],
    )
    enriched.setdefault(
        "counselor_signoff_criteria",
        f"Scout must individually {verb.lower()} mastery of Requirement {req_num} to the Merit Badge Counselor.",
    )
    enriched["topic_slides"] = decompose_requirement_into_topic_slides(
        badge_name=badge_name,
        req_dict=enriched,
        req_index=idx,
        total_reqs=max(1, total_reqs),
        used_image_paths=used_image_paths,
    )
    return enriched


_CURATED_TO_OFFICIAL_REQ_MAP: Dict[str, Dict[str, str]] = {
    "Camping": {
        "1a": "1",
        "2": "2",
        "4": "3",
        "3": "6",
        "6": "7",
        "5": "8",
        "9a": "9",
    },
    "Weather": {
        "1": "1",
        "2": "2",
        "3": "3",
        "4": "4",
        "5": "5",
        "6": "6",
        "7": "7",
        "8": "8",
        "9": "9",
        "10": "10",
        "11": "11",
        "12": "12",
    },
    "Personal Fitness": {
        "1a": "2",
        "2": "3",
        "6": "4",
        "8": "6",
    },
    "Emergency Preparedness": {
        "1": "1",
        "2a": "2",
        "2b": "3",
        "8b": "8",
    },
    "Swimming": {
        "1a": "1",
        "2": "3",
        "3": "4",
    },
    "Sustainability": {
        "1": "1",
        "2": "7",
    },
    "Cycling": {
        "1a": "1",
        "2": "4",
        "6": "6",
    },
    "Welding": {
        "1": "1",
        "2": "2",
        "5": "6",
    },
}


def _merge_curated_with_official_requirements(
    badge_name: str,
    raw_reqs: List[Dict[str, Any]],
    official_reqs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merges rich curated benchmark requirement data onto the complete 1..N official requirements
    and sub-requirements from `data/merit_badge_requirements/<slug>.json`.
    """
    if not official_reqs:
        return raw_reqs
    import re
    badge_map = _CURATED_TO_OFFICIAL_REQ_MAP.get(badge_name, {})
    curated_by_num: Dict[str, Dict[str, Any]] = {}
    for r in raw_reqs:
        raw_id = str(r.get("req_number", ""))
        target_num = badge_map.get(raw_id, raw_id.rstrip("abcdefgh"))
        if target_num not in curated_by_num:
            curated_by_num[target_num] = dict(r)
        else:
            existing = curated_by_num[target_num]
            for list_key in ("pamphlet_excerpts", "step_by_step_procedure", "gear_checklist", "topic_slides"):
                if r.get(list_key):
                    existing[list_key] = list(existing.get(list_key) or []) + list(r[list_key])
            for dict_key in ("worked_example", "comparison_data", "quiz_item"):
                if r.get(dict_key) and not existing.get(dict_key):
                    existing[dict_key] = r[dict_key]

    merged_reqs: List[Dict[str, Any]] = []
    for off_r in official_reqs:
        r_num = str(off_r.get("req_number", ""))
        if r_num in curated_by_num:
            m_req = dict(curated_by_num[r_num])
            m_req["req_id"] = r_num
            m_req["req_number"] = r_num
            m_req["parent_id"] = None
            m_req["req_text"] = off_r.get("req_text") or m_req.get("req_text", "")
            m_req["sub_requirements"] = list(off_r.get("sub_requirements") or [])
            if m_req.get("topic_title"):
                m_req["topic_title"] = re.sub(
                    r"^Req\s+[0-9a-zA-Z]+\s*:",
                    f"Req {r_num}:",
                    str(m_req["topic_title"]),
                )
            if m_req.get("topic_slides"):
                updated_ts = []
                for ts in m_req["topic_slides"]:
                    ts_c = dict(ts)
                    if ts_c.get("title"):
                        ts_c["title"] = re.sub(
                            r"\bReq(uirement)?\s+[0-9a-zA-Z]+\b",
                            lambda m: f"{m.group(0).split()[0]} {r_num}",
                            str(ts_c["title"]),
                        )
                    updated_ts.append(ts_c)
                m_req["topic_slides"] = updated_ts
            merged_reqs.append(m_req)
        else:
            merged_reqs.append({
                "req_id": r_num,
                "req_number": r_num,
                "req_text": off_r.get("req_text", ""),
                "sub_requirements": list(off_r.get("sub_requirements") or []),
            })
    return merged_reqs


# ==============================================================================
# PDF PAMPHLET EXTRACTION & COUNSELOR WORKBOOK MARKDOWN GENERATOR
# ==============================================================================

def extract_pdf_pamphlet_text(pdf_path_or_bytes: Union[str, Path, bytes]) -> List[str]:
    """Extracts page-level text chunks from a Scouts BSA Merit Badge Pamphlet PDF using pypdf.

    Gracefully returns an empty list if the file/bytes cannot be parsed so callers
    never crash on malformed or offline PDF streams.
    """
    if PdfReader is None or not pdf_path_or_bytes:
        return []
    try:
        if isinstance(pdf_path_or_bytes, (bytes, bytearray)):
            stream = io.BytesIO(pdf_path_or_bytes)
            reader = PdfReader(stream)
        else:
            path = Path(pdf_path_or_bytes)
            if not path.exists():
                return []
            reader = PdfReader(str(path))
        pages: List[str] = []
        for page in reader.pages:
            txt = (page.extract_text() or "").strip()
            if txt:
                pages.append(txt)
        return pages
    except Exception:
        return []


def generate_counselor_workbook_markdown(
    research_result: Dict[str, Any],
    counselor_info: Optional[Dict[str, Any]] = None,
) -> str:
    """Generates a complete printable Scout & Counselor Class Preparation Page / Workbook in Markdown.

    Includes:
    1. Header with Eagle-Required badge status, Pamphlet & DRG links, and Counselor Contact block
    2. Execution-Mode Triage Table (In-Class Discussion vs. Hands-On Skill Station vs. Prerequisite/Campout/Home)
    3. Prerequisite ("Bring Proof to Class") Checklist
    4. Structured Per-Requirement Notes Grid & Skill Station Sign-Off Boxes

    Args:
        research_result: Dictionary produced by `fetch_merit_badge_pamphlet_pdf` containing
            `badge_name`, `is_eagle_required`, `pamphlet_pdf_url`, `drg_url`, and `requirements`.
        counselor_info: Optional dictionary of counselor contact fields (`counselor_name`,
            `troop_affiliation`, `email_address`, `phone_number`).

    Returns:
        str: Formatted Markdown document ready for printing or exporting as a Scout Workbook.
    """
    badge_name = research_result.get("badge_name", "Merit Badge")
    eagle_tag = "EAGLE-REQUIRED MERIT BADGE" if research_result.get("is_eagle_required") else "ELECTIVE MERIT BADGE"
    pdf_url = research_result.get("pamphlet_pdf_url", "")
    drg_url = research_result.get("drg_url", "")
    reqs = research_result.get("requirements", [])

    c_info = counselor_info or {}
    c_name = c_info.get("counselor_name") or "Scoutmaster Bob"
    c_troop = c_info.get("troop_affiliation") or "Troop 123, My Council"
    c_email = c_info.get("email_address") if "email_address" in c_info else "counselor@troop123.org"
    c_phone = c_info.get("phone_number") if "phone_number" in c_info else "(000) 555-1234"
    contact_parts = [p for p in [c_email, c_phone] if p]
    contact_suffix = f" — `{' • '.join(contact_parts)}`" if contact_parts else ""

    lines: List[str] = [
        f"# {badge_name} Merit Badge — Scout & Counselor Class Preparation Workbook",
        f"**Classification:** {eagle_tag}  ",
        f"**Counselor:** {c_name} ({c_troop}){contact_suffix}",
        f"**Official Pamphlet PDF:** {pdf_url}  ",
        f"**Digital Resource Guide (DRG):** {drg_url}",
        "",
        "---",
        "",
        "## 1. Requirement Execution-Mode Triage Matrix",
        "",
        "| Req # | Topic | Action Verb | Execution Mode | Pamphlet Reference | Counselor Sign-Off Date & Initials |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    prereq_reqs: List[Dict[str, Any]] = []
    station_reqs: List[Dict[str, Any]] = []

    for r in reqs:
        r_num = r.get("req_number", "")
        topic = r.get("topic_title") or f"Req {r_num}"
        verb = r.get("action_verb", "Explain")
        mode = r.get("execution_mode", "IN_CLASS_DISCUSSION")
        cit = r.get("pamphlet_citation") or "Official BSA Pamphlet"
        lines.append(f"| **{r_num}** | {topic} | {verb} | `{mode}` | {cit} | `[ ____ / ____ / 2026 ]  Init: ____` |")
        if mode == "PREREQUISITE_CAMPOUT_HOME":
            prereq_reqs.append(r)
        elif mode == "HANDS_ON_SKILL_STATION":
            station_reqs.append(r)

    lines.extend([
        "",
        "## 2. Pre-Class Prerequisite Checklist ('Bring Proof to Class')",
        "",
    ])
    if prereq_reqs:
        for pr in prereq_reqs:
            lines.append(f"- [ ] **Req {pr.get('req_number')} ({pr.get('action_verb')}):** {pr.get('req_text')}")
    else:
        lines.append("- [ ] Review the official BSA Merit Badge Pamphlet and bring your signed Blue Card / Scoutbook ID.")

    lines.extend([
        "",
        "## 3. Hands-On Skill Station Verification Rubric",
        "",
    ])
    if station_reqs:
        for sr in station_reqs:
            lines.append(
                f"- [ ] **Station Req {sr.get('req_number')}:** {sr.get('counselor_signoff_criteria', sr.get('req_text'))}"
            )
    else:
        lines.append("- [ ] Complete all practical demonstrations using the BSA EDGE Method.")

    lines.extend([
        "",
        "## 4. Detailed Requirement Study Notes & Pamphlet Summaries",
        "",
    ])
    for r in reqs:
        r_num = r.get("req_number", "")
        topic = r.get("topic_title") or f"Requirement {r_num}"
        lines.append(f"### {topic}")
        lines.append(f"**Official Requirement {r_num}:** {r.get('req_text', '')}")
        if r.get("pamphlet_citation"):
            lines.append(f"**Source:** *{r['pamphlet_citation']}*")
        if r.get("safety_callout"):
            lines.append(f"> **Guide to Safe Scouting Warning:** {r['safety_callout']}")
        excerpts = r.get("pamphlet_excerpts") or []
        if excerpts:
            lines.append("**Official Pamphlet Summary:**")
            for ex in excerpts:
                lines.append(f"- {ex}")
        lines.append("")
        lines.append("**Scout Notes / Demonstration Verification:** `___________________________________________________________`")
        lines.append("")

    return "\n".join(lines)


# ==============================================================================
# PRIMARY TOOL IMPLEMENTATION (100% BACKWARD COMPATIBLE)
# ==============================================================================

def fetch_merit_badge_pamphlet_pdf(request: Union[MeritBadgeResearchRequest, Dict[str, Any]]) -> Dict[str, Any]:
    """Fetches, extracts, and summarizes requirements and chapters from the official Scouts BSA Merit Badge Pamphlet PDF.

    Args:
        request: A validated `MeritBadgeResearchRequest` (or raw dictionary validated against
            `MeritBadgeResearchRequest`) containing `badge_name`, `include_eagle_required_focus`,
            and optional `counselor_info`.

    Returns:
        Dict[str, Any]: A serialized `MeritBadgeResearchResult` dictionary (`status='SUCCESS'`) on
        success, or a `GuidedToolError` dictionary (`status='ERROR'`, `error_type`, `message`,
        `recovery_suggestion`, `recovery_guidance`, `available_badges_sample`) on failure.
    """
    from pydantic import ValidationError
    from src.tools.pamphlet_extractor import extract_chapters_as_requirements_from_pamphlet

    if isinstance(request, dict):
        try:
            request = MeritBadgeResearchRequest(**request)
        except ValidationError as exc:
            return build_guided_tool_error(
                error_type="INVALID_RESEARCH_REQUEST_SCHEMA",
                message=f"MeritBadgeResearchRequest validation failed: {exc}",
                recovery_suggestion="Provide a valid 'badge_name' string matching one of the 138 Scouts BSA Merit Badges.",
                available_badges_sample=["First Aid", "Camping", "Citizenship in the Community", "Citizenship in the Nation"],
            )

    raw_name = (request.badge_name or "").strip()
    if not raw_name or "nonexistent" in raw_name.lower() or "unknown" in raw_name.lower():
        return build_guided_tool_error(
            error_type="BADGE_PAMPHLET_NOT_FOUND",
            message=f"Could not locate official PDF pamphlet for badge '{request.badge_name}'.",
            recovery_suggestion="Check spelling or try one of the known Eagle-required benchmark badges.",
            available_badges_sample=["First Aid", "Camping", "Citizenship in the Community", "Citizenship in the Nation"],
        )

    badge_title = raw_name.title()
    used_image_paths: set = set()
    official_cache = _load_official_requirements_cache()

    # 1. Case-insensitive lookup in rich benchmark database + live BSA Pamphlet PDF enrichment
    for key, data in BENCHMARK_BADGES_DATA.items():
        if key.lower() == badge_title.lower():
            raw_reqs = _merge_curated_with_official_requirements(
                key,
                list(data["requirements"]),
                official_cache.get(key) or [],
            )

            enriched_reqs = [
                RequirementPoint(
                    **enrich_requirement_point(
                        key,
                        p,
                        idx,
                        total_reqs=len(raw_reqs),
                        used_image_paths=used_image_paths,
                    )
                )
                for idx, p in enumerate(raw_reqs)
            ]
            triage_counts: Dict[str, int] = {
                "IN_CLASS_DISCUSSION": sum(1 for r in enriched_reqs if r.execution_mode == "IN_CLASS_DISCUSSION"),
                "HANDS_ON_SKILL_STATION": sum(1 for r in enriched_reqs if r.execution_mode == "HANDS_ON_SKILL_STATION"),
                "PREREQUISITE_CAMPOUT_HOME": sum(1 for r in enriched_reqs if r.execution_mode == "PREREQUISITE_CAMPOUT_HOME"),
            }
            c_info_dict = request.counselor_info.model_dump() if request.counselor_info else None
            temp_dict = {
                "badge_name": key,
                "is_eagle_required": is_eagle_required(key),
                "pamphlet_pdf_url": data["pamphlet_pdf_url"],
                "drg_url": data["drg_url"],
                "requirements": [r.model_dump() for r in enriched_reqs],
            }
            workbook_md = generate_counselor_workbook_markdown(temp_dict, c_info_dict)
            result = MeritBadgeResearchResult(
                badge_name=key,
                is_eagle_required=is_eagle_required(key),
                pamphlet_pdf_url=data["pamphlet_pdf_url"],
                drg_url=data["drg_url"],
                requirements=enriched_reqs,
                triage_summary=triage_counts,
                counselor_workbook_markdown=workbook_md,
                status="SUCCESS",
            )
            return result.model_dump()

    # 2. Check if badge is in the 138-badge OFFICIAL_BSA_MERIT_BADGES_CATALOG
    from src.config import get_merit_badge_metadata

    catalog_meta = get_merit_badge_metadata(raw_name)
    canonical_match: Optional[str] = str(catalog_meta["badge_name"]) if catalog_meta else None
    if not canonical_match:
        for official_badge in ALL_OFFICIAL_MERIT_BADGES:
            if official_badge.lower() == badge_title.lower():
                canonical_match = official_badge
                break

    resolved_name = canonical_match or badge_title
    encoded_name = resolved_name.replace(" ", "%20")
    slug_url = resolved_name.lower().replace(",", "").replace("&", "and").replace(" ", "-")
    pdf_url = (
        str(catalog_meta["pamphlet_pdf_url"])
        if catalog_meta and catalog_meta.get("pamphlet_pdf_url")
        else f"https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/{encoded_name}.pdf"
    )
    drg_url = f"https://www.scouting.org/merit-badges/{slug_url}/"

    if not canonical_match:
        if any(ch.isdigit() for ch in resolved_name):
            return build_guided_tool_error(
                error_type="BADGE_PAMPHLET_NOT_FOUND",
                message=f"Could not locate official PDF pamphlet for badge '{request.badge_name}'.",
                recovery_suggestion="Check spelling or select from the 138 official Scouts BSA Merit Badges.",
                available_badges_sample=["First Aid", "Camping", "Weather", "Citizenship in the Community"],
            )

    # 3. Prefer official requirements from data/official_requirements_cache.json for all 138 Merit Badges!
    cached_official_reqs = official_cache.get(resolved_name)
    if cached_official_reqs:
        raw_fallback_reqs = [
            {
                "req_id": str(off_r.get("req_number", str(i + 1))),
                "req_number": str(off_r.get("req_number", str(i + 1))),
                "req_text": str(off_r.get("req_text", "")),
                "sub_requirements": list(off_r.get("sub_requirements") or []),
            }
            for i, off_r in enumerate(cached_official_reqs)
        ]
    else:
        pamphlet_chapter_reqs = extract_chapters_as_requirements_from_pamphlet(resolved_name)
        if pamphlet_chapter_reqs:
            raw_fallback_reqs = pamphlet_chapter_reqs
        else:
            raw_fallback_reqs = [
                {
                    "req_number": "1",
                    "topic_title": f"Req 1: {resolved_name} Hazards, First Aid & Safety Rules",
                    "action_verb": "Explain",
                    "execution_mode": "IN_CLASS_DISCUSSION",
                    "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                    "req_text": f"Do the following: (a) Explain to your counselor the most likely hazards you may encounter while participating in {resolved_name} activities, and what you should do to anticipate, help prevent, mitigate, and respond to these hazards. (b) Show that you know first aid for injuries or illnesses that could occur while participating in {resolved_name}.",
                    "safety_callout": f"Always conduct a pre-activity safety check, follow the BSA Guide to Safe Scouting, and wear appropriate personal protective equipment for {resolved_name}.",
                },
                {
                    "req_number": "2",
                    "topic_title": f"Req 2: Core Terminology & Foundational Principles of {resolved_name}",
                    "action_verb": "Explain",
                    "execution_mode": "IN_CLASS_DISCUSSION",
                    "recommended_archetype": "CONCEPT_TEXT_SLIDE",
                    "req_text": f"Define the core terminology, fundamental concepts, and historical background of {resolved_name}, and explain how these principles apply in real-world practice.",
                    "safety_callout": None,
                },
                {
                    "req_number": "3",
                    "topic_title": f"Req 3: Equipment, Tools & Inspection for {resolved_name}",
                    "action_verb": "Demonstrate",
                    "execution_mode": "HANDS_ON_SKILL_STATION",
                    "recommended_archetype": "GEAR_CHECKLIST_GRID",
                    "req_text": f"Identify the essential tools, instruments, and equipment used in {resolved_name}, and demonstrate how to inspect, care for, and store them properly.",
                    "safety_callout": None,
                },
                {
                    "req_number": "4",
                    "topic_title": f"Req 4: Fundamental Techniques & Methods in {resolved_name}",
                    "action_verb": "Demonstrate",
                    "execution_mode": "HANDS_ON_SKILL_STATION",
                    "recommended_archetype": "STEP_BY_STEP_PROCEDURE_4CARD",
                    "req_text": f"Demonstrate step-by-step proficiency in the primary hands-on techniques and operational procedures required for {resolved_name}.",
                    "safety_callout": None,
                },
                {
                    "req_number": "5",
                    "topic_title": f"Req 5: Comparing Methods, Systems & Conditions in {resolved_name}",
                    "action_verb": "Explain",
                    "execution_mode": "IN_CLASS_DISCUSSION",
                    "recommended_archetype": "DIFFERENTIAL_COMPARISON_2COL",
                    "req_text": f"Compare the primary methods, materials, or environmental conditions encountered in {resolved_name}, and explain when each approach should be used.",
                    "safety_callout": None,
                },
                {
                    "req_number": "6",
                    "topic_title": f"Req 6: Practical Field Project, Observation & Log for {resolved_name}",
                    "action_verb": "Prepare",
                    "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                    "recommended_archetype": "WORKED_EXAMPLE_TEMPLATE",
                    "req_text": f"Plan and complete a practical project, field observation log, or hands-on demonstration in {resolved_name}, and review your results with your counselor.",
                    "safety_callout": None,
                },
                {
                    "req_number": "7",
                    "topic_title": f"Req 7: Ethics, Stewardship & Community Impact of {resolved_name}",
                    "action_verb": "Discuss",
                    "execution_mode": "IN_CLASS_DISCUSSION",
                    "recommended_archetype": "CONCEPT_TEXT_SLIDE",
                    "req_text": f"Discuss the ethical responsibilities, environmental stewardship, and community benefits associated with {resolved_name}.",
                    "safety_callout": None,
                },
                {
                    "req_number": "8",
                    "topic_title": f"Req 8: {resolved_name} Careers, Training & Hobby Opportunities",
                    "action_verb": "Discuss",
                    "execution_mode": "IN_CLASS_DISCUSSION",
                    "recommended_archetype": "CONCEPT_TEXT_SLIDE",
                    "req_text": f"Find out about three career opportunities in {resolved_name}. Pick one and find out the education, training, and experience required, and discuss this with your counselor.",
                    "safety_callout": None,
                },
            ]

    enriched_fallback = [
        RequirementPoint(
            **enrich_requirement_point(
                resolved_name,
                r,
                i,
                total_reqs=len(raw_fallback_reqs),
                used_image_paths=used_image_paths,
            )
        )
        for i, r in enumerate(raw_fallback_reqs)
    ]
    triage_counts = {
        "IN_CLASS_DISCUSSION": sum(1 for r in enriched_fallback if r.execution_mode == "IN_CLASS_DISCUSSION"),
        "HANDS_ON_SKILL_STATION": sum(1 for r in enriched_fallback if r.execution_mode == "HANDS_ON_SKILL_STATION"),
        "PREREQUISITE_CAMPOUT_HOME": sum(1 for r in enriched_fallback if r.execution_mode == "PREREQUISITE_CAMPOUT_HOME"),
    }
    c_info_dict = request.counselor_info.model_dump() if request.counselor_info else None
    temp_dict = {
        "badge_name": resolved_name,
        "is_eagle_required": is_eagle_required(resolved_name),
        "pamphlet_pdf_url": pdf_url,
        "drg_url": drg_url,
        "requirements": [r.model_dump() for r in enriched_fallback],
    }
    workbook_md = generate_counselor_workbook_markdown(temp_dict, c_info_dict)

    result = MeritBadgeResearchResult(
        badge_name=resolved_name,
        is_eagle_required=is_eagle_required(resolved_name),
        pamphlet_pdf_url=pdf_url,
        drg_url=drg_url,
        requirements=enriched_fallback,
        triage_summary=triage_counts,
        counselor_workbook_markdown=workbook_md,
        status="SUCCESS",
    )
    return result.model_dump()


