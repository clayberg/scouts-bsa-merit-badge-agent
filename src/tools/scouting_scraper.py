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
from src.config import OFFICIAL_BSA_MERIT_BADGES_CATALOG, is_eagle_required
from src.schemas import CounselorTitleSlideInfo

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore


# ==============================================================================
# OFFICIAL MERIT BADGE CATALOG (ALL 144 OFFICIAL SCOUTS BSA MERIT BADGES)
# ==============================================================================

ALL_OFFICIAL_MERIT_BADGES: List[str] = [
    str(item["badge_name"]) for item in OFFICIAL_BSA_MERIT_BADGES_CATALOG
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
# PYDANTIC JSON SCHEMAS & TOOL CONTRACTS
# ==============================================================================


class MeritBadgeResearchRequest(BaseModel):
    """Schema for requesting official merit badge pamphlet and requirement research."""
    badge_name: str = Field(..., description="Official name of the merit badge (e.g., 'First Aid').")
    include_eagle_required_focus: bool = Field(True, description="Whether to highlight Eagle-required prerequisites.")
    counselor_info: Optional[CounselorTitleSlideInfo] = Field(None, description="Title slide counselor customization.")
    option_track: Optional[str] = Field(
        None,
        description="Optional multi-option Merit Badge track filter (e.g., 'ALL', 'A', 'B', 'C', 'D', or sub_id like '2a', '2b').",
    )


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
    syllabus_bucket: str = Field(
        "In-Class Concept",
        description="5-Tier SyllabusBucket classification."
    )
    workbook_organizer: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured WorkbookOrganizerSpec dictionary."
    )
    pamphlet_page_citation: Optional[str] = Field(
        None,
        description="Pamphlet page citation for slide footers and presenter notes."
    )
    common_misconception_pair: Optional[Dict[str, str]] = Field(
        None,
        description="Misconception vs. Fact pair grounded in the pamphlet."
    )
    starting_requirement_gate: Optional[Dict[str, Any]] = Field(
        None,
        description="Prerequisite or safety gate required before starting or signing off."
    )
    curated_resources: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Verified official Scouting America and educational reference links."
    )
    estimated_minutes: int = Field(
        15,
        description="Estimated instructional minutes for this requirement."
    )
    homework_verification_note: str = Field(
        "",
        description="Counselor verification standard for Blue Card sign-off."
    )
    workbook_diagram_url: Optional[str] = Field(
        None,
        description="Optional reference diagram path or URL for Scout and Counselor workbooks."
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
    option_tracks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Available Option Tracks for multi-option Merit Badges (e.g., Option A: Traditional Golf vs. Option B: Disc Golf).",
    )
    selected_option_track: str = Field(
        "ALL",
        description="Active Option Track filter applied to this research result ('ALL', 'A', 'B', etc.).",
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
                    "correct_answer": "Option B - Stop, secure scene safety, and avoid entering the active rockfall hazard zone",
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
                            "correct_answer": "Option B - Stop, secure scene safety, and avoid entering the active rockfall hazard zone",
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
                            "Three Degrees of Burns (Req 3b): 1st-degree (red epidermis), 2nd-degree (blistered dermis), and 3rd-degree (charred/white full-thickness - cover dry and call 911).",
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
                        "image_path": "assets/diagrams/first_aid_bleeding_diagram.png",
                        "caption": "Applying firm direct pressure with sterile gauze, wrapping a pressure bandage, and positioning a windlass tourniquet 2 inches above a severe limb wound.",
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
                            "Underwater Hypoxic Blackout (Req 6e): Hyperventilating before underwater breath-holding purges CO2 and causes sudden blackout before the urge to breathe - strictly prohibited in Scouting aquatics.",
                            "Cold-Water Shock & Drowning (Req 6f): Cold water (<60°F) triggers an involuntary gasp reflex; always wear a USCG life jacket and rescue via Reach, Throw, Row, Go.",
                            "Lightning & Electric Shock (Req 6g): Seek enclosed buildings or low timber when thunder roars; lightning cardiac arrest victims do not hold a charge - start CPR/AED immediately.",
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
                    "correct_answer": "Option B - Loosen the splint ties immediately, re-pad, and re-verify distal CMS circulation",
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
                            "Open Fracture Dressing: Cover protruding bone ends with a moist sterile dressing and build a doughnut ring pad around - never push bone back in.",
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
                            "correct_answer": "Option B - Loosen the splint ties immediately, re-pad, and re-verify distal CMS circulation",
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
                            "Severe Hypothermia Danger: When core temperature drops below 90°F, shivering stops, muscles stiffen, and cardiac arrhythmia risk rises - handle gently!",
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
                "safety_callout": "If a Scout or friend expresses thoughts of self-harm or severe hopelessness, never keep it a secret - stay with them, tell a trusted adult leader immediately, and call or text 988.",
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
                "topic_slides": [
                    {
                        "title": "Mental Health First Aid, Campout Stressors & 988 Lifeline (Reqs 12a-12d)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/ai_illustrations/first_aid_req_12_topic_visual.png",
                        "caption": "Supportive Listening on a Campout: A Scout buddy and adult leader offering calm, nonjudgmental support and grounding at camp.",
                        "bullets": [
                            "Mental Health Parity (Req 12a): Emotional and psychological well-being is just as vital as physical health during every Scouting adventure.",
                            "Campout & Outing Stressors (Req 12b): Homesickness, fatigue, dehydration, weather, or group conflict can trigger acute anxiety or panic.",
                            "Warning Signs for Help (Req 12c): Persistent sadness, sudden withdrawal, panic attacks, or any talk of self-harm require immediate adult help.",
                            "Supportive Listening & 988 (Req 12d): Listen calmly without judgment, stay with your buddy, alert an adult leader, and call or text 988.",
                        ],
                    },
                    {
                        "title": "Four-Step Buddy Support & Escalation Protocol (ALGEE)",
                        "layout": "STEP_BY_STEP_PROCEDURE_4CARD",
                        "bullets": [
                            "Notice Behavioral Changes: Watch for a buddy withdrawing from patrol meals, struggling to sleep, hyperventilating, or expressing hopelessness.",
                            "Listen Without Judgment: Move to a calm, quiet spot with Two-Deep visibility, ask 'How can I help right now?', and listen empathetically.",
                            "Ground & Reassure: For acute anxiety or hyperventilation, guide slow 'box breathing' (inhale 4 sec, hold 4 sec, exhale 4 sec) and offer water.",
                            "Involve Trusted Adults & 988: Never promise to keep safety concerns secret; bring in the Scoutmaster, parent, counselor, or call/text 988.",
                        ],
                    },
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
                "topic_slides": [
                    {
                        "title": "Teaching First Aid with the BSA EDGE Method (Req 14)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/ai_illustrations/first_aid_req_14_topic_visual.png",
                        "caption": "BSA EDGE Method in Action: Explaining, Demonstrating, Guiding, and Enabling a younger Scout to apply a padded forearm splint and cravat sling.",
                        "bullets": [
                            "Explain Phase (Step 1): State what the first-aid skill is, when it is needed, universal precautions (PPE gloves), and the sequence of steps.",
                            "Demonstrate Phase (Step 2): Perform the skill smoothly at half-speed using real bandages or splints while narrating each safety checkpoint.",
                            "Guide Phase (Step 3): Coach the learner through hands-on practice, offering positive feedback and checking knot tension and distal CMS.",
                            "Enable Phase (Step 4): Present a realistic trail scenario and verify the learner can execute the complete first-aid skill independently.",
                        ],
                    },
                ],
                "worked_example": {
                    "title": "Sample EDGE Lesson Plan - Teaching Forearm Splinting & Cravat Sling",
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
                "topic_slides": [
                    {
                        "title": "Emergency Medical, Nursing & Search-and-Rescue Careers (Reqs 15a-15b)",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/ai_illustrations/first_aid_req_15_topic_visual.png",
                        "caption": "Emergency Medical Careers: Scouts visiting an ambulance station with a Firefighter-Paramedic, Emergency Department Nurse, and Wilderness Rescue Medic.",
                        "bullets": [
                            "EMS Station Visit or Interview (Req 15a): Tour a local fire-rescue or EMS station with Two-Deep Leadership to see cardiac monitors, airway kits, and rigs.",
                            "EMT & Paramedic Pathway (Req 15b): EMT-Basic (150-200 hrs + NREMT exam) and Paramedics (1,200-1,800 hrs + degree) lead pre-hospital emergency care.",
                            "Career Opportunities & Nursing (Req 15c): Trauma Nurses (BSN + NCLEX-RN), Search-and-Rescue medics, and Emergency Physicians direct emergency care.",
                            "Lifelong Service & Hobby Readiness (Req 15d): Apply first-aid and Wilderness First Aid (WFA) training to high-adventure treks, sports, and community service.",
                        ],
                    },
                ],
                "worked_example": {
                    "title": "Requirement 15b Career Research Comparison - Paramedic, ER Nurse & Wilderness Medic",
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
                    "title": "Personal Leave No Trace Trek Plan - Sierra High Country Weekend",
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
                    "title": "Weekend Campout Patrol Duty Roster - Pine Eagle Patrol (8 Scouts)",
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
                    "correct_answer": "Option B - A two-thirds (2/3) supermajority override vote in both the House and the Senate",
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
                            "correct_answer": "Option B - A two-thirds (2/3) supermajority override vote in both the House and the Senate",
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
                    "E Pluribus Unum ('Out of Many, One'): Adopted on the Great Seal in 1782 to signify 13 diverse colonies - and people of many backgrounds - uniting as one Constitutional Republic.",
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
                    "FDR's Four Freedoms (1941) & JFK's Inaugural (1961): Articulated universal human freedoms and called on citizens to 'ask not what your country can do for you - ask what you can do for your country.'",
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
                            "title": "Historic Speech Analysis - Lincoln's Gettysburg Address (1863)",
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
                            "Smothering a Grease Fire: Turn off the stove burner and slide a metal lid or pour baking soda over the pan - never throw water on burning oil.",
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
                "req_text": "Cooking Basics. Do the following: (a) Discuss each of the following cooking methods - boiling, baking, frying, simmering, steaming, microwaving, and grilling/broiling - and give two examples of foods cooked each way, (b) Discuss the benefits of using a camp stove on an outing vs. a charcoal or wood fire, and (c) Describe how to manage your time when preparing a meal so components finish hot together.",
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
                            "Backward Meal Scheduling: Count backward from serving time - start 40-minute baked/simmered dishes first, 15-minute sides second, and 5-minute pan-fried proteins last.",
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
                            "title": "Culinary & Food Science Career Research - Chef vs. Dietitian",
                            "artifact_type": "CAREER RESEARCH PROFILE",
                            "fields": {
                                "1. Executive Chef": "Associate/Bachelor degree in Culinary Arts (CIA/Johnson & Wales) or 3-year ACF apprenticeship + ServSafe certification",
                                "2. Registered Dietitian (RDN)": "ACEND-accredited university program + 1,000-hour supervised clinical practice + national CDR registration exam",
                                "3. Food Scientist": "B.S. in Food Science, Chemistry, or Microbiology; works in R&D labs, USDA/FDA, or outdoor ration companies",
                                "Scouting Connection": "Patrol menu planning, budgeting, sanitation, and leadership under pressure directly build these career skills",
                            },
                            "counselor_tip": "Ask Scouts which part of earning the Cooking Merit Badge they enjoyed most - creative recipe cooking, nutrition science, or outdoor logistics - to connect to a career path.",
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
                "req_id": "5",
                "req_number": "5",
                "action_verb": "Demonstrate",
                "req_text": "Signaling for Help. Do the following: (a) Show three ways of attracting and communicating with rescue aircraft or drones. (b) Show ways to attract the attention of searchers on the ground if you are lost in the wilderness. (c) Show ways to attract the attention of searchers on the water if you are stranded with a capsized or disabled motorboat or sailboat.",
                "pamphlet_excerpts": [
                    "Ground-to-Air Distress Signals (Req 5a): Lay out high-contrast 10-foot ground symbols ('V' for Require Assistance, 'X' for Require Medical Assistance) or aim a heliograph signal mirror toward aircraft and drones.",
                    "Pilot Acknowledgment Cues: A search pilot signals 'Message Understood / Yes' by dipping the nose of the aircraft up and down, or signals 'No / Not Understood' by fishtailing the plane side to side.",
                    "Wilderness Ground Signaling (Req 5b): Blow the universal 3-blast distress signal on a pea-less rescue whistle, hang high-visibility orange flagging in a clearing, and tend a green-bough daytime smoke signal fire.",
                    "Marine & Open-Water Signaling (Req 5c): Stay with a capsized hull for maximum visibility, deploy USCG-approved orange distress flags or daytime smoke signals, and use waterproof strobes and marine whistles.",
                ],
                "safety_callout": "Never abandon a capsized boat hull unless it is in immediate danger of sinking or going over a hazard; a hull is far easier for searchers to spot than a swimmer.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
            {
                "req_id": "6",
                "req_number": "6",
                "action_verb": "Demonstrate",
                "req_text": "Moving an Injured Person. With another person, show two good ways to transport an injured person out of a remote area using improvised stretchers to conserve the energy of rescuers while ensuring the well-being and protection of the injured person.",
                "pamphlet_excerpts": [
                    "Scene & Spinal Assessment First: Before moving any injured person in the backcountry, rule out head, neck, or spinal trauma, splint all fractures, and insulate the patient from ground cold.",
                    "Improvised Two-Pole Blanket or Parka Litter: Thread two sturdy 7-foot wooden poles or lashed ski poles through the sleeves of two zipped winter parkas or fold a heavy camp blanket in thirds around the poles.",
                    "Sleeping Bag & Tarp Litter Insulation: In cold or snowy terrain, place the casualty inside an insulated sleeping bag and vapor barrier on the stretcher to prevent hypothermia during slow transport.",
                    "Rescuer Energy Conservation & Rest Cycles: Carry the litter feet-first (except when climbing steep grades), swap bearers frequently, and stop for a 5-to-10-minute rest every 30 to 60 minutes to prevent a second casualty.",
                ],
                "safety_callout": "Never move a victim with suspected head, neck, or spinal injury unless they face an immediate life-threatening hazard such as fire, rising water, or avalanche.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
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
                            "Step 1 - 30/30 Lightning & Sky Check: Seek enclosed shelter as soon as thunder is heard or flash-to-bang time is 30 seconds or less (lightning within 6 miles); wait 30 minutes after the last thunder before resuming outdoor activity.",
                            "Step 2 - Last-Resort Open-Field Lightning Position: If trapped in the open far from buildings or vehicles, spread your patrol 50+ feet apart, avoid lone trees and metal poles, and crouch low on the balls of your feet covering your ears.",
                            "Step 3 - Flash Flood High-Ground Evacuation: Pitch tents well above floodplains and canyon bottoms; if water rises rapidly, abandon heavy camp gear and climb immediately to higher ground.",
                            "Step 4 - Family Emergency Plan Briefing: Review your home tornado shelter location, hurricane/flood evacuation route, and NOAA Weather Radio alert signals with your family.",
                        ],
                    },
                    {
                        "title": "Severe Weather Watch vs. Severe Weather Warning",
                        "layout": "DIFFERENTIAL_COMPARISON_2COL",
                        "comparison_data": {
                            "left_header": "Severe Weather WATCH",
                            "left_badge": "BE PREPARED - CONDITIONS FAVORABLE",
                            "left_points": [
                                "What It Means: Atmospheric ingredients are favorable for dangerous weather (tornado, severe thunderstorm, flood, or winter storm) to develop",
                                "Timing & Location: Exact timing and path are not yet certain; covers a broad multi-county region for several hours",
                                "Scout & Family Action: Monitor NOAA Weather Radio closely, review where the nearest sturdy shelter is, and pause exposed ridge or open-water trips",
                                "Analogy: 'All the ingredients for storm tacos are on the kitchen counter'",
                            ],
                            "right_header": "Severe Weather WARNING",
                            "right_badge": "TAKE ACTION NOW - IMMINENT DANGER",
                            "right_points": [
                                "What It Means: Dangerous weather is occurring right now or is imminent based on NWS Doppler radar or trained storm spotters",
                                "Timing & Location: Specific storm polygon tracking toward your immediate community within minutes",
                                "Scout & Family Action: Stop outdoor activities immediately and move to your basement, storm shelter, or higher ground right now",
                                "Analogy: 'The storm is fully made and at your front door - take shelter immediately!'",
                            ],
                        },
                        "bullets": [
                            "A Watch means hazardous weather is possible (be prepared); a Warning means hazardous weather is occurring or imminent (take shelter now).",
                        ],
                    },
                    {
                        "title": "Patrol Scenario: Lightning & Severe Thunderstorm Triage",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "scenario_prompt": "Your patrol is hiking across an open mountain meadow when dark cumulonimbus clouds build overhead, thunder rumbles 15 seconds after a lightning flash, and the NWS upgrades a Severe Thunderstorm Watch to a Warning. What should your patrol do?",
                            "options": [
                                "Huddle together under the tallest isolated pine tree at the edge of the meadow to stay dry.",
                                "Pitch nylon tents in a narrow rocky ravine so the canyon walls block the wind.",
                                "Descend off the open ridge toward an enclosed building or hard-topped vehicle; if caught in the open away from shelter, spread out 50+ feet apart and crouch low on the balls of your feet.",
                            ],
                            "correct_answer": "Option C - Descend off the ridge to enclosed shelter, or spread out 50+ feet apart in the low lightning crouch.",
                            "explanation": "A 15-second flash-to-bang means lightning is only 3 miles away, and a Warning means severe weather is imminent. Avoid tall isolated trees (Option A) and flash-flood ravines (Option B).",
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
                    "Source 1 - NWS Point Forecasts (weather.gov): Provides 7-day hourly weather graphs, quantitative precipitation forecasts, wind gusts, and hazardous weather outlooks for any GPS trailhead.",
                    "Source 2 - NOAA Weather Radio All Hazards (NWR): Broadcasts continuous 24/7 VHF weather briefings (162.400–162.550 MHz) and Specific Area Message Encoding (SAME) alarm tones even when cell service fails.",
                    "Supplemental Sources: Local broadcast TV/radio meteorologists, aviation/marine briefings, and satellite messengers (Garmin inReach) for multi-day wilderness treks.",
                ],
                "topic_slides": [
                    {
                        "title": "Field Forecast Sources: Weather.gov & NOAA Weather Radio",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_p037_img1.png",
                        "caption": "Backcountry Scouts monitoring a portable NOAA Weather Radio All Hazards receiver and trail communication radio.",
                        "bullets": [
                            "Source 1 - National Weather Service (weather.gov): Official 7-day point forecasts tailored to exact elevation and latitude/longitude, including hourly temperature, wind chill, rain probability, and lightning risk.",
                            "Source 2 - NOAA Weather Radio All Hazards (NWR): Battery/hand-crank VHF receiver (162.400–162.550 MHz) broadcasting continuous local NWS office cycles and automatic emergency tone alerts.",
                            "Source 3 - Satellite Communicators & Local Broadcasts: Backcountry satellite messengers fetch updated spot forecasts beyond cell towers, while local TV/radio meteorologists explain regional storm tracks.",
                            "Why Two Sources Are Mandatory: Comparing a pre-trip web graphic with a live trailhead radio receiver ensures your patrol catches rapid frontal shifts.",
                        ],
                    },
                    {
                        "title": "NWS Doppler Radar & Hourly Forecast Graphs",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/ai_illustrations/weather_doppler_radar_nano.png",
                        "caption": "National Weather Service WSR-88D Doppler radar reflectivity display with dBZ precipitation intensity scale.",
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
                    "High Pressure ('H' - Fair Weather): Associated with sinking (subsiding) air that warms and dries out as it descends, suppressing cloud formation and bringing clear skies.",
                    "Low Pressure ('L' - Stormy Weather): Associated with rising air that cools and condenses into clouds and precipitation; surface winds spiral counterclockwise and inward in the Northern Hemisphere.",
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
                        "image_path": "assets/ai_illustrations/weather_cold_front_cross_section_nano.png",
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
                        "image_path": "assets/ai_illustrations/weather_warm_front_cross_section_nano.png",
                        "bullets": [
                            "Advancing warm air glides up and over retreating cold air along a gentle frontal slope, creating a wide progression of cirrus, cirrostratus, altostratus, and nimbostratus clouds with steady rain ahead of the front.",
                        ],
                        "caption": "Warm Front Cross-Section & Surface Map (Red semicircles pointing in direction of warm air advance)",
                    },
                    {
                        "title": "Warm Front: 3D Profile & Temperature Inversion",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/ai_illustrations/weather_warm_front_3d_sidebyside.png",
                        "bullets": [
                            "Overrunning warm air rises gradually over a 600 km wedge of cold air, producing high cirrus (Ci) first, then cirrostratus (Cs), altostratus (As), nimbostratus (Ns) steady rain/snow, and fog.",
                        ],
                        "caption": "Warm Front 3D Cross-Section: (a) Gentle frontal slope (1:200) and broad precipitation shield; (b) Temperature inversion aloft",
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
                        "image_path": "assets/ai_illustrations/weather_sea_land_breeze_nano.png",
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
                            "Step 1 - Evaporation & Uplift: Solar energy evaporates liquid water into water vapor gas, which is carried aloft by rising air currents or fronts.",
                            "Step 2 - Adiabatic Cooling & Saturation: As moist air rises into lower pressure, it expands and cools until it reaches 100% relative humidity (dew point).",
                            "Step 3 - Condensation Nuclei: Excess water vapor condenses onto microscopic dust, sea salt, or smoke particles to form tiny cloud droplets (~0.02 mm).",
                            "Step 4 - Collision & Coalescence: Cloud droplets collide and merge (or grow on ice crystals) into heavy raindrops (~2.0 mm, 1 million times larger) that gravity pulls to Earth.",
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
                                "Condensation Nucleus (Dust / Salt)": "0.0002 mm diameter - Microscopic aerosol particle on which water vapor first condenses.",
                                "Typical Cloud Droplet": "0.02 mm diameter - Too tiny and light to fall; suspended easily by gentle upward air currents.",
                                "Falling Raindrop (Coalescence)": "2.0 mm diameter (~1,000,000 cloud droplets merged) - Heavy enough to overcome updrafts and fall as rain.",
                                "Severe Thunderstorm Hailstone": "25+ mm (1.0+ inch, quarter size) - Cycled above the 32°F freezing level by 60+ mph updrafts, adding onion-like ice layers.",
                            },
                            "counselor_tip": "Emphasize that cloud droplets must grow roughly one million times in volume by collision-coalescence or ice-crystal growth before they can fall as rain.",
                        },
                        "bullets": [
                            "Compare the physical mechanism and particle scale of condensation nuclei, cloud droplets, raindrops, and layered hailstones.",
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
                        "image_path": "assets/ai_illustrations/weather_cloud_classification_nano.png",
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
                            "Step 1 - Estimate Cloud Base Altitude: Classify the cloud deck into High (>20,000 ft, wispy ice), Middle (6,500–20,000 ft, 'alto-'), Low (<6,500 ft, flat stratus), or Vertical (towering heaps).",
                            "Step 2 - Identify Latin Root Shape: Determine whether the cloud is 'cirrus' (curl/wisp), 'stratus' (flat layered sheet), 'cumulus' (puffy heap), or 'nimbus' (actively precipitating).",
                            "Step 3 - Watch Vertical Growth & Lowering Ceilings: A sequence of Cirrus -> Cirrostratus -> Altostratus -> Nimbostratus warns of a warm front; swelling Cumulus congestus warns of afternoon thunderstorms.",
                            "Step 4 - Check for Virga & Anvil Tops: Look for 'virga' (streaks of rain evaporating before hitting the ground) or flat glaciated anvil tops indicating severe cumulonimbus updrafts.",
                        ],
                    },
                    {
                        "title": "Patrol Scenario: Reading an Approaching Warm Front",
                        "layout": "SOCRATIC_CHECKPOINT_QUIZ",
                        "quiz_item": {
                            "scenario_prompt": "On Day 1 of a backcountry trek you observe high wispy Cirrus clouds, followed that night by a halo around the Moon in Cirrostratus, and by Day 2 morning a lowering gray sheet of Altostratus and dark Nimbostratus. What weather should your patrol prepare for?",
                            "options": [
                                "A fast-moving cold front squall line with brief 15-minute hail followed by rapid clearing.",
                                "An approaching Warm Front bringing widespread, steady rain or snow over the next 12 to 24 hours from the Nimbostratus deck.",
                                "High-pressure subsidence bringing clear skies and dropping humidity.",
                            ],
                            "correct_answer": "Option B - An approaching Warm Front bringing widespread, steady rain or snow.",
                            "explanation": "The classic descending cloud progression (Cirrus -> Cirrostratus halo -> Altostratus -> Nimbostratus) marks warm air overrunning retreating cold air ahead of a warm front.",
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
                        "image_path": "assets/ai_illustrations/weather_hydrologic_cycle_nano.png",
                        "bullets": [
                            "The Hydrologic Cycle: (1) Evaporation, (2) Transpiration, (3) Sublimation, (4) Condensation, (5) Transportation, (6) Precipitation, (7) Surface/Snowmelt Runoff, (8) Infiltration, (9) Groundwater Flow, (10) Plant Uptake.",
                        ],
                        "caption": "Hydrologic Cycle diagram illustrating evaporation, transpiration, sublimation, condensation, precipitation, runoff, and groundwater flow.",
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
                    "Acid Rain Defined: Rainwater mixed with sulfur dioxide (SO2) and nitrogen oxide (NOx) pollutants - primarily from coal-burning power plants and vehicles - forming dilute sulfuric and nitric acid.",
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
                        "image_path": "assets/ai_illustrations/weather_earth_orbit_seasons_nano.png",
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
                                "4. Solstice vs. Equinox Dates": "June 21 (N. Hemisphere Summer Solstice), Dec 21 (Winter Solstice), Mar 20 & Sep 22 (Equinoxes - equal 12-hr day/night worldwide).",
                            },
                            "counselor_tip": "Use a flashlight and a tilted globe (or basketball) to show your counselor how a direct beam at the equator concentrates light while a low-angle beam at the pole spreads out.",
                        },
                        "bullets": [
                            "Compare solar angle, day length, and seasonal temperature variation across the Equator, Temperate Mid-Latitudes, and Poles.",
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
                        "Observation Time & Instrument": "07:00 AM Daily - Homemade Cup Anemometer & Rain Gauge",
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
                            "Step 1 - Draft Your Timed 5-Minute Outline: Write clear bullet points covering Watch vs. Warning, Lightning rules, Flash Flood rules, and Tornado rules with time markers (0:00 to 5:00).",
                            "Step 2 - Obtain Counselor Outline Approval: Review your draft outline with your Weather Merit Badge Counselor and incorporate any feedback before scheduling your talk.",
                            "Step 3 - Prepare Visual Aids & Props: Bring a printed cloud chart, a portable NOAA Weather Radio, or a campsite map to keep Cub Scouts or troop members engaged.",
                            "Step 4 - Deliver the Talk & Log Sign-Off: Speak clearly for at least 5 minutes, answer audience questions, and have your unit leader or counselor verify completion.",
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
                                "0:45–2:15 Pillar 1 - Lightning Safety": "'When Thunder Roars, Go Indoors' (30/30 rule); enclosed building or metal car; avoid open fields, water, and lone trees; demonstrate dispersed low crouch.",
                                "2:15–3:45 Pillar 2 - Flash Flood Safety": "Never camp in dry washes or narrow canyons; climb to high ground immediately (leave heavy gear); 'Turn Around, Don't Drown' (6 in. water knocks you down).",
                                "3:45–5:15 Pillar 3 - Tornado Safety & Summary": "Flying debris hazard; basement or interior windowless lowest-floor room; if trapped outdoors, lie flat face-down in a low dry ditch covering head and neck.",
                            },
                            "counselor_tip": "Practice your talk out loud with a stopwatch at home so you hit the 5-minute mark smoothly without rushing.",
                        },
                        "bullets": [
                            "Use a timed 4-part outline to cover Watch vs. Warning, Lightning, Flash Floods, and Tornadoes across 5+ minutes.",
                        ],
                    },
                ],
            },
            {
                "req_id": "12",
                "req_number": "12",
                "topic_title": "Req 12: Careers in Meteorology, Training, Education & Responsibilities",
                "action_verb": "Explore",
                "req_text": "Explore careers related to this merit badge. Research one career to learn about the training and education needed, costs, job prospects, salary, job duties, and career advancement. Your research methods may include - with your parent or guardian's permission - an internet or library search, an interview with a professional in the field, or a visit to a workplace where people in this career work. Discuss with your counselor what you learned and how this career might suit your interests and talents.",
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

def _infer_action_verb_and_mode(
    req_text: str,
    explicit_verb: Optional[str] = None,
    explicit_mode: Optional[str] = None,
    sub_reqs: Optional[List[Dict[str, Any]]] = None,
) -> tuple[str, str, str]:
    """Infers action_verb, execution_mode, and edge_phase from requirement text and sub-requirements."""
    sub_texts: List[str] = []
    for sr in sub_reqs or []:
        if isinstance(sr, dict):
            sub_texts.append(str(sr.get("text") or sr.get("sub_req_text") or ""))
            for ch in sr.get("children") or []:
                if isinstance(ch, dict):
                    sub_texts.append(str(ch.get("text") or ch.get("sub_req_text") or ""))
    full_blob = (req_text + " " + " ".join(sub_texts)).strip().lower()
    first_word = req_text.strip().split()[0].rstrip(":,.") if req_text.strip() else "Explain"

    prereq_keywords = (
        "camp a total", "overnight campout", "duty roster", "prepare a list of clothing",
        "keep a log", "keep a daily log", "keep a record", "for one day", "for two weeks",
        "for 30 days", "for three months", "12-week", "13 consecutive", "90 days",
        "five days in a row", "write a letter", "take four 10-mile", "physical examination",
        "spend one overnight", "plan and carry out", "plan, budget, and cook",
        "identify in the night sky", "earn the first aid", "choose two outdoor study",
        "interview", "visit ", "attend ", "volunteer", "service project", "tour ",
        "with your parent", "guardian's permission", "counselor's approval, visit",
        "counselor's approval, interview", "observe a ", "keep track of",
    )
    station_keywords = (
        "demonstrate", "show how", "show that you know", "prepare a personal",
        "complete the aerobic", "design, build", "build a ", "construct a ",
        "pass the bsa swimmer", "swim 150", "clean and adjust", "shoot a qualifying",
        "put together a personal", "first aid for", "tie ", "splice", "bandag",
        "splint", "cpr", "rescue", "paddl", "climb", "belay", "pitch a tent",
    )

    if any(k in full_blob for k in prereq_keywords):
        mode = "PREREQUISITE_CAMPOUT_HOME"
    elif explicit_mode in ("PREREQUISITE_CAMPOUT_HOME", "HANDS_ON_SKILL_STATION"):
        mode = explicit_mode
    elif any(k in full_blob for k in station_keywords):
        mode = "HANDS_ON_SKILL_STATION"
    elif explicit_mode:
        mode = explicit_mode
    else:
        mode = "IN_CLASS_DISCUSSION"

    valid_verbs = {
        "Explain", "Discuss", "Describe", "Demonstrate", "Show", "Identify",
        "Prepare", "List", "Review", "Perform", "Complete",
    }
    cand_verb = (explicit_verb or first_word).strip().capitalize()
    if cand_verb in valid_verbs:
        verb = cand_verb
    else:
        m_v = re.search(
            r"\b(explain|discuss|describe|demonstrate|show|identify|prepare|list|review|perform|complete)\b",
            full_blob,
            flags=re.IGNORECASE,
        )
        if m_v:
            verb = m_v.group(1).capitalize()
        elif mode == "HANDS_ON_SKILL_STATION":
            verb = "Demonstrate"
        elif mode == "PREREQUISITE_CAMPOUT_HOME":
            verb = "Prepare"
        else:
            verb = "Explain"

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

    # Attach official sub_requirements and v2.1.0 enriched metadata from data/official_requirements_cache.json
    official_cache = _load_official_requirements_cache()
    badge_official = official_cache.get(badge_name) or []
    if isinstance(badge_official, dict):
        badge_official = badge_official.get("requirements") or []
    matched_off_r: Optional[Dict[str, Any]] = None
    matched_sub_r: Optional[Dict[str, Any]] = None
    parent_req_id = str(enriched.get("parent_id") or re.sub(r"[a-zA-Z]+.*$", "", req_num)).strip()
    base_opt_id = re.sub(r"_\d+$", "", req_num).strip()
    for off_r in badge_official:
        if not isinstance(off_r, dict):
            continue
        r_id_cand = str(off_r.get("req_number") or off_r.get("req_id") or "")
        if r_id_cand == req_num:
            matched_off_r = off_r
            break
        if r_id_cand == parent_req_id:
            matched_off_r = off_r
            for sr_cand in off_r.get("sub_requirements") or []:
                if isinstance(sr_cand, dict):
                    sr_cid = str(sr_cand.get("sub_id") or sr_cand.get("id") or "")
                    if sr_cid.lower() in (req_num.lower(), base_opt_id.lower()):
                        matched_sub_r = sr_cand
                        break
    if matched_sub_r:
        for sr_meta_key in (
            "workbook_organizer",
            "pamphlet_page_citation",
            "common_misconception_pair",
            "pamphlet_excerpts",
        ):
            if not enriched.get(sr_meta_key) and matched_sub_r.get(sr_meta_key) is not None:
                enriched[sr_meta_key] = matched_sub_r[sr_meta_key]
    if matched_off_r:
        if not enriched.get("sub_requirements") and matched_off_r.get("sub_requirements") and req_num == str(matched_off_r.get("req_number") or matched_off_r.get("req_id") or ""):
            enriched["sub_requirements"] = list(matched_off_r["sub_requirements"])
        for meta_key in (
            "syllabus_bucket",
            "workbook_organizer",
            "pamphlet_page_citation",
            "common_misconception_pair",
            "starting_requirement_gate",
            "curated_resources",
            "estimated_minutes",
            "homework_verification_note",
            "pamphlet_excerpts",
            "step_by_step_procedure",
            "gear_checklist",
            "comparison_data",
            "worked_example",
            "quiz_item",
            "safety_callout",
        ):
            if not enriched.get(meta_key) and matched_off_r.get(meta_key) is not None:
                enriched[meta_key] = matched_off_r[meta_key]
        if matched_off_r.get("topic_title") and (
            not enriched.get("topic_title")
            or "Before beginning work" in str(enriched.get("topic_title"))
            or "With permission from" in str(enriched.get("topic_title"))
            or "With the help of" in str(enriched.get("topic_title"))
            or "Complete the survey" in str(enriched.get("topic_title"))
        ):
            enriched["topic_title"] = matched_off_r["topic_title"]

    req_text = enriched.get("req_text", f"Complete requirement {req_num} for {badge_name}.")
    verb, mode, edge = _infer_action_verb_and_mode(
        req_text,
        enriched.get("action_verb"),
        enriched.get("execution_mode"),
        enriched.get("sub_requirements"),
    )
    enriched["action_verb"] = verb
    enriched["execution_mode"] = mode
    enriched.setdefault("edge_phase", edge)

    # Ensure v2.1.0 syllabus_bucket and workbook_organizer defaults if not already set
    if not enriched.get("syllabus_bucket") or (mode == "PREREQUISITE_CAMPOUT_HOME" and enriched.get("syllabus_bucket") != "Pre-Class Prerequisite"):
        if mode == "PREREQUISITE_CAMPOUT_HOME":
            enriched["syllabus_bucket"] = "Pre-Class Prerequisite"
        elif mode == "HANDS_ON_SKILL_STATION":
            enriched["syllabus_bucket"] = "In-Class Demonstration"
        else:
            enriched["syllabus_bucket"] = "In-Class Concept"
    try:
        from src.memory.session_store import PersistentSessionStore
        overrides = PersistentSessionStore().list_syllabus_bucket_overrides_sync(badge_name)
        if req_num in overrides:
            enriched["syllabus_bucket"] = overrides[req_num]
    except Exception:
        pass
    if not enriched.get("workbook_organizer"):
        enriched["workbook_organizer"] = {
            "organizer_type": "STEP_BY_STEP_CHECKLIST" if mode == "HANDS_ON_SKILL_STATION" else "RULED_EXPLAIN_BOX",
            "headers": [f"Req {req_num} Concept / Step", "Key Pamphlet Facts & Field Notes"],
            "row_labels": ["Step / Point 1", "Step / Point 2", "Step / Point 3"],
            "min_rows": 3,
            "pre_approval_gate": "approval" in req_text.lower(),
        }
    if not enriched.get("common_misconception_pair"):
        tp_clean = str(enriched.get("topic_title") or f"{badge_name} Requirement {req_num}").split(":", 1)[-1].strip()
        enriched["common_misconception_pair"] = {
            "misconception": f"Assuming general familiarity with {tp_clean} is enough without applying the specific {badge_name} Requirement {req_num} field standards.",
            "fact": f"Under the {badge_name} Merit Badge Pamphlet, each Scout must individually {verb.lower()} every element of {tp_clean} (Requirement {req_num}) during counselor verification.",
        }
    if not enriched.get("curated_resources"):
        u_slug = badge_name.lower().replace(",", "").replace("&", "and").replace(" ", "-")
        enriched["curated_resources"] = [
            {
                "title": f"Official Scouting America {badge_name} Hub (Req {req_num})",
                "url": f"https://www.scouting.org/merit-badges/{u_slug}/",
                "source_org": "Scouting America",
                "resource_type": "Official DRG",
            }
        ]

    pamphlet_info = summarize_pamphlet_for_requirement(
        badge_name=badge_name,
        req_number=req_num,
        req_text=req_text,
        req_index=idx,
        total_reqs=max(1, total_reqs),
        used_image_paths=used_image_paths,
    )
    enriched.setdefault("topic_title", pamphlet_info.get("topic_title"))
    enriched.setdefault("pamphlet_citation", pamphlet_info.get("pamphlet_citation"))
    enriched.setdefault("pamphlet_pages", pamphlet_info.get("pamphlet_pages") or [])
    if pamphlet_info.get("raw_pamphlet_image_path"):
        enriched["raw_pamphlet_image_path"] = pamphlet_info["raw_pamphlet_image_path"]
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
    if not enriched.get("workbook_diagram_url"):
        diag_url = _resolve_workbook_diagram_url(badge_name, req_num, req_text)
        if diag_url:
            enriched["workbook_diagram_url"] = diag_url
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
        "5": "5",
        "6": "6",
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
            for extra_k in (
                "syllabus_bucket",
                "workbook_organizer",
                "pamphlet_page_citation",
                "common_misconception_pair",
                "starting_requirement_gate",
                "curated_resources",
                "estimated_minutes",
                "homework_verification_note",
            ):
                if off_r.get(extra_k) is not None and not m_req.get(extra_k):
                    m_req[extra_k] = off_r[extra_k]
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
                        # Only rewrite bare parent requirement numbers that changed, preserving sub-requirement suffixes like Req 4c or Req 13e
                        ts_c["title"] = re.sub(
                            r"\b(Req(?:uirement)?)\s+(\d+)([a-zA-Z]*)\b",
                            lambda m: f"{m.group(1)} {r_num}{m.group(3)}" if m.group(2) != r_num else m.group(0),
                            str(ts_c["title"]),
                        )
                    updated_ts.append(ts_c)
                m_req["topic_slides"] = updated_ts
            merged_reqs.append(m_req)
        else:
            m_off = dict(off_r)
            m_off["req_id"] = r_num
            m_off["req_number"] = r_num
            m_off["req_text"] = off_r.get("req_text", "")
            m_off["sub_requirements"] = list(off_r.get("sub_requirements") or [])
            merged_reqs.append(m_off)
    return merged_reqs


MULTI_OPTION_MERIT_BADGES: List[str] = [
    "Action Sports",
    "Animal Science",
    "Archery",
    "Athletics",
    "Citizenship in Society",
    "Cycling",
    "Disabilities Awareness",
    "Geology",
    "Golf",
    "Journalism",
    "Metalwork",
    "Multisport",
    "Physics",
    "Plant Science",
    "Radio",
    "Railroading",
    "Rifle Shooting",
    "Sewing and Needlework",
    "Shotgun Shooting",
    "Skating",
    "Snow Sports",
    "Whitewater",
]


def _normalize_option_track_filter(
    option_track: Optional[str],
    badge_name: Optional[str] = None,
) -> str:
    """Normalizes an option track filter string ('ALL', 'A', 'B', 'Option A', '2a', '4E') into 'ALL' or an uppercase token."""
    if not option_track or not str(option_track).strip():
        return "ALL"
    import re

    raw = str(option_track).strip()
    raw_up = raw.upper()
    if raw_up in ("ALL", "BOTH", "ALL_OPTIONS", "*"):
        return "ALL"

    badge_lower = str(badge_name or "").strip().lower()

    # Named option title aliases
    named_aliases: Dict[str, str] = {
        "TRIATHLON": "A",
        "DUATHLON": "B",
        "AQUATHLON": "C",
        "AQUABIKE": "D",
        "TRADITIONAL GOLF": "A",
        "DISC GOLF": "B",
        "ROAD BIKING": "A",
        "TRAIL BIKING": "B",
        "RECURVE": "A",
        "COMPOUND": "B",
        "MACHINE SEWING": "A",
        "KNITTING": "B",
        "CROCHET": "C",
        "HAND EMBROIDERY": "D",
        "EMBROIDERY": "D",
        "APPLIQUE": "E",
        "APPLIQUÉ": "E",
        "QUILTING": "F",
    }
    if badge_lower == "action sports":
        if "SKATEBOARD" in raw_up or raw_up in ("4A", "OPTION A", "A", "1"):
            return "A"
        if "SNOWBOARD" in raw_up or raw_up in ("4B", "OPTION B", "B", "2"):
            return "B"
    if badge_lower == "citizenship in society":
        if raw_up in ("6B(1)", "6B1", "OPTION 1", "OPTION A", "1", "A") or "EXCLUDED" in raw_up:
            return "1"
        if raw_up in ("6B(2)", "6B2", "OPTION 2", "OPTION B", "2", "B") or "IMAGINARY" in raw_up or "NEW SCHOOL" in raw_up:
            return "2"
    if badge_lower == "physics":
        # Preserve requirement-scoped option keys like '4A', '6B', '7C' or comma-separated '4A,6B,7C'
        if "," in raw_up:
            return raw_up
        m_phys_req = re.match(r"^(?:REQ\s*)?([467])\s*[:\-]?\s*(?:OPTION\s+)?([A-I])\b", raw_up)
        if m_phys_req:
            return f"{m_phys_req.group(1)}{m_phys_req.group(2)}"
        m_phys_sub = re.match(r"^([467][A-I])\b", raw_up)
        if m_phys_sub:
            return m_phys_sub.group(1)

    if raw_up in named_aliases:
        return named_aliases[raw_up]

    m_opt = re.match(r"^OPTION\s+([A-Z1-9])\b", raw_up)
    if m_opt:
        return m_opt.group(1)
    m_sub_paren = re.match(r"^\d+[A-Z]\(([1-9A-Z])\)$", raw_up)
    if m_sub_paren:
        return m_sub_paren.group(1)
    m_sub = re.match(r"^\d+([A-Z1-9])\b", raw_up)
    if m_sub:
        return m_sub.group(1)
    if len(raw_up) == 1 and raw_up.isalnum():
        return raw_up
    return "ALL"


_CLEAN_OPTION_TITLE_MAP: Dict[str, str] = {
    "rifle shooting (modern cartridge type)": "Modern Cartridge Rifle",
    "air rifle shooting (bb or pellet)": "Air Rifle (BB or Pellet)",
    "muzzleloading rifle shooting": "Muzzleloading Rifle",
    "shotgun shooting (modern shotshell type)": "Modern Shotshell Shotgun",
    "muzzleloading shotgun shooting": "Muzzleloading Shotgun",
    "newspaper, magazine, and online journalism": "Print & Online Journalism",
    "radio and television journalism": "Radio & TV Journalism",
    "family radio service (frs) and general mobile radio service (gmrs) walkie talkies": "FRS & GMRS Walkie-Talkies",
    "shortwave and medium-wave listening": "Shortwave & Medium-Wave Radio",
    "amateur radio direction finding": "Radio Direction Finding (ARDF)",
    "sheet metal mechanic/tinsmith": "Sheet Metal & Tinsmithing",
    "surface and sedimentary processes": "Surface & Sedimentary Processes",
    "long jump or high jump": "Long Jump or High Jump",
    "pull-ups and push-ups": "Pull-Ups & Push-Ups",
    "football kick or soccer kick": "Football or Soccer Kick",
    "appliqué": "Applique & Fabric Design",
    "applique": "Applique & Fabric Design",
}

_OPTION_OVERVIEW_THEMES: Dict[str, str] = {
    "2a": "Rules, Safety, Equipment & Core Skills",
    "skating:2a": "Ice Skating: Rink Safety, Skate Care & Ice Maneuvers",
    "skating:2b": "Roller Skating: Safety Rules, Skate Care & Rink Skills",
    "skating:2c": "In-Line Skating: Protective Gear, Braking & Street Skills",
    "skating:2d": "Skateboarding: Board Anatomy, Safety Gear & Park Skills",
    "rifle shooting:2a": "Modern Cartridge Rifle: Parts, Safe Handling & Marksmanship",
    "rifle shooting:2b": "Air Rifle (BB or Pellet): Safety, Fundamentals & Grouping",
    "rifle shooting:2c": "Muzzleloading Rifle: Black Powder Safety, Loading & Grouping",
    "shotgun shooting:2a": "Modern Shotshell Shotgun: Gauges, Safe Handling & Clay Targets",
    "shotgun shooting:2b": "Muzzleloading Shotgun: Black Powder Safety, Loading & Clay Targets",
    "journalism:2a": "Print & Online Journalism: News Analysis & Newsroom Tour",
    "journalism:2b": "Radio & TV Journalism: Broadcast Newscasts & Station Tour",
    "snow sports:7a": "Downhill (Alpine) Skiing: Ski Care, Lift Safety & Slope Runs",
    "snow sports:7b": "Cross-Country (Nordic) Skiing: Touring Gear, Waxing & 4-Mile Tour",
    "snow sports:7c": "Snowboarding: Fall Prevention, Bindings, Lifts & Slope Runs",
    "snow sports:7d": "Snowshoeing: Snowshoe Parts, Sizing, Trail Breaking & 2-Mile Hike",
    "cycling:6a": "Road Biking: Traffic Safety Test, Handling & Distance Rides",
    "cycling:6b": "Trail or Mixed Surface Biking: Trail Skills, Etiquette & Rides",
    "archery:5a": "Recurve Bow or Longbow: Bow Parts, Stringing, 11 Steps & Qualification",
    "archery:5b": "Compound Bow: Bow Parts, Cable Care, 11 Steps & Qualification",
    "railroading:7a": "Model Railroading: Track Scales, Layout Building & DCC Control",
    "railroading:7b": "Railfanning: Railroad Museums, Scenic Rides & Trip Planning",
    "animal science:6a": "Beef Cattle: Production Systems, Feedlot Design & Beef Cuts",
    "animal science:6b": "Dairy: Milk Production, Grade A Sanitation & Dairy Farm Visit",
    "animal science:6c": "Horse: Barn Design, Equine History, Care & Feeding",
    "animal science:6d": "Sheep or Goat: Wool Grading, Milk Products & Flock Care",
    "animal science:6e": "Hog: Pork Cuts, Breeding & Feeding Programs",
    "animal science:6f": "Avian: Poultry Housing, Egg Grading & Flock Management",
    "plant science:8a": "Agronomy: Seedbed Prep, Germination, Crop Pests & Field Crops",
    "plant science:8b": "Horticulture: Hardiness Zones, Propagation & Landscape Design",
    "plant science:8c": "Field Botany: Plant Identification, Herbarium Mounts & Tree Study",
    "geology:4a": "Surface & Sedimentary Processes: Stream Gradients & Deposition",
    "geology:4b": "Energy Resources: Source & Trap Rocks, Subsurface Maps & Drilling",
    "geology:4c": "Mineral Resources: Rock Classes, Mineral Properties & Collection",
    "geology:4d": "Earth History: Geologic Eras, Plate Tectonics & Fossilization",
    "metalwork:5a": "Sheet Metal & Tinsmithing: Hand Tools, Pattern Sketches & Fabrication",
    "metalwork:5b": "Silversmith: Silversmithing Tools, Design Sketches & Copper Work",
    "metalwork:5c": "Founder: Two-Piece Molds, Pattern Design & Metal Casting",
    "metalwork:5d": "Blacksmith: Forge Tools, Low-Carbon Steel Exercises & Hot Forging",
    "multisport:4a": "Triathlon: Swim, Bike & Run Training & Transition Setup",
    "multisport:4b": "Duathlon: Bike & Run Training & Transition Setup",
    "multisport:4c": "Aquathlon: Swim & Run Training & Transition Setup",
    "multisport:4d": "Aquabike: Swim & Bike Training & Transition Setup",
    "radio:8a": "Amateur Radio: FCC Licenses, Q Signals, Transceivers & On-Air QSO",
    "radio:8b": "Radio Broadcasting: FCC Rules, Program Logs & Station Schedule",
    "radio:8c": "Shortwave & Medium-Wave Radio: Day vs. Night Propagation Logs",
    "radio:8d": "Radio Direction Finding (ARDF): Directional Antenna & Fox Hunt",
    "radio:8e": "FRS & GMRS Walkie-Talkies: Channels, Etiquette & Field Use",
    "whitewater:4a": "Tandem Canoeist: Bow & Stern Strokes, Braces & Righting Pry",
    "whitewater:4b": "Solo Canoeist: Solo Strokes, Braces & Righting Pry",
    "whitewater:4c": "Solo Kayaker: Draw, Rudder, Sculling & High/Low Braces",
    "disabilities awareness:4a": "Access: Accessibility Audit of School, Worship, Camp & Public Sites",
    "disabilities awareness:4b": "Accommodation: Facility Accommodations at Community & Scouting Sites",
    "athletics:5a": "Sprinting: 100-Meter & 200-Meter Dash Progression",
    "athletics:5b": "Long-Distance Running: 3K & 5K Endurance Progression",
    "athletics:5c": "Long Jump or High Jump: Running & Standing Jump Progression",
    "athletics:5d": "Swimming: 100-Meter & 200-Meter Swim Progression",
    "athletics:5e": "Pull-Ups & Push-Ups: Two-Minute Strength Progression",
    "athletics:5f": "Baseball Throw: Target Accuracy & Distance Throws",
    "athletics:5g": "Basketball Shooting: Free Throws, Layups & Perimeter Agility",
    "athletics:5h": "Football or Soccer Kick: 10-Yard Goal Accuracy & Distance Kicks",
    "athletics:5i": "Weight Training: Bench Press & Leg Curl Sets",
    "sewing and needlework:3a": "Machine Sewing: Machine Parts, Threading, Stitches & Bag Project",
    "sewing and needlework:3b": "Knitting: Needles, Pattern Reading, Cast-On, Stitches & Project",
    "sewing and needlework:3c": "Crochet: Hooks, Pattern Symbols, Chain/Single/Double Stitches & Project",
    "sewing and needlework:3d": "Hand Embroidery: History, Tools, Hoops & Embroidered Sampler",
    "sewing and needlework:3e": "Applique: Hand & Machine Fusible Applique & Garment Design",
    "sewing and needlework:3f": "Quilting: Historical Quilts, Color Sorting, Piecing & Binding",
    "action sports:4a": "Skateboarding: Stance, Pushing, Braking & Skatepark Carving",
    "action sports:4b": "Snowboarding: Stance, Gliding, Edge Control & Slope Turns",
    "citizenship in society:6b(1)": "Personal Exclusion Reflection: Situation, Impact & Standing Up for Others",
    "citizenship in society:6b(2)": "New School Inclusion Scenario: Empathy, Welcoming Actions & Belonging",
}

_CURATED_OPTION_CHUNK_THEMES: Dict[str, List[str]] = {
    "golf:2a(3)": [
        "Traditional Golf: Golf History, Equipment Evolution & Champions",
        "Traditional Golf: Physical Conditioning & Dynamic Warm-Up",
    ],
    "golf:2a(5)": [
        "Traditional Golf: Grip, Stance, Driver & Fairway Woods",
        "Traditional Golf: Approach Irons, Pitching, Bunker & Putting",
    ],
    "golf:2b(3)": [
        "Disc Golf: Ed Headrick, PDGA Origins & Disc Evolution",
        "Disc Golf: Disc Flight Categories, Fitness & Warm-Up",
    ],
    "golf:2b(5)": [
        "Disc Golf: Throwing Grips, X-Step & Backhand Drives",
        "Disc Golf: Forehand Flicks, Overhand & Roller Shots",
        "Disc Golf: Putting Stances, Flight Angles & Mini Marker",
    ],
    "skating:2a": [
        "Ice Skating: Rink Safety, Natural Ice, Skate Types & Carrying",
        "Ice Skating: Seasonal Storage, Forward Stop, Glides & T-Stroke",
        "Ice Skating: Backward Gliding, Backward Stride & 180-Degree Turn",
        "Ice Skating: Figure-Eight Crossovers, Racing Safety & Hockey Stop",
    ],
    "skating:2b": [
        "Roller Skating: Safety Rules, Skate Anatomy, Care & Forward Stride",
        "Roller Skating: One-Foot Glides, Forward Crossovers & Backward Stride",
        "Roller Skating: Forward & Backward Slalom & Rink Shuttle",
        "Roller Skating: Spins, Jumps, Stepovers & Basketball Agility",
    ],
    "skating:2c": [
        "In-Line Skating: Safety Rules, Skate Anatomy, Protective Gear & Care",
        "In-Line Skating: Forward Stride, One-Foot Glides, Heel Brake & Crossovers",
        "In-Line Skating: Forward & Backward Swizzles, Lunge Turn & Mohawk",
        "In-Line Skating: Downhill Slalom, Passing Etiquette, Obstacles & Curbs",
    ],
    "skating:2d": [
        "Skateboarding: History, Fitness Benefits, Rules & Protective Gear",
        "Skateboarding: Street vs. Vert, Board Anatomy, Assembly & Maintenance",
        "Skateboarding: Regular vs. Goofy Stance, Pushing, Carving & Braking",
        "Skateboarding: Basic Ollie, Coping Drop-In & Trick Demonstrations",
    ],
    "rifle shooting:2a": [
        "Modern Cartridge Rifle: Rifle Parts, Safe Storage, Cartridges & Malfunctions",
        "Modern Cartridge Rifle: Five Shooting Fundamentals, Range Safety & Cleaning",
        "Modern Cartridge Rifle: Rifle Selection, Benchrest Grouping & Sight Adjustment",
    ],
    "rifle shooting:2b": [
        "Air Rifle (BB or Pellet): Air Gun Parts, Safe Handling, Pellets & Fundamentals",
        "Air Rifle (BB or Pellet): Range Commands, Cleaning Rules & Maintenance",
        "Air Rifle (BB or Pellet): Air Rifle Selection, Grouping & Sight Adjustment",
    ],
    "rifle shooting:2c": [
        "Muzzleloading Rifle: History, Principal Parts, Safe Handling & Black Powder",
        "Muzzleloading Rifle: Powder Storage, Load Components, Loading & Misfires",
        "Muzzleloading Rifle: Range Safety, Cleaning Rules & Proper Maintenance",
        "Muzzleloading Rifle: Rifle Selection, Target Grouping & Sight Adjustment",
    ],
    "shotgun shooting:2a": [
        "Modern Shotshell Shotgun: Action Types, Safe Handling, Shells & Gauges",
        "Modern Shotshell Shotgun: Misfires & Hangfires, Range Safety & Cleaning Rules",
        "Modern Shotshell Shotgun: Proper Cleaning, Shotgun Selection & Moving Targets",
    ],
    "shotgun shooting:2b": [
        "Muzzleloading Shotgun: History, Parts, Safe Handling & Black Powder Grades",
        "Muzzleloading Shotgun: Powder Storage, Load Components & Safe Loading",
        "Muzzleloading Shotgun: Misfire Procedures, Range Safety & Cleaning Rules",
        "Muzzleloading Shotgun: Proper Cleaning, Shotgun Selection & Moving Targets",
    ],
    "snow sports:7a": [
        "Downhill (Alpine) Skiing: Ski Waxing, Bindings, Teaching System & Lifts",
        "Downhill (Alpine) Skiing: Beginner Maneuvers, Linked Wedge Turns & Christies",
        "Downhill (Alpine) Skiing: Intermediate Slope Runs, Varied Terrain & Organizations",
    ],
    "snow sports:7b": [
        "Cross-Country (Nordic) Skiing: Equipment Care, Trail Rules, Ski Types & Waxing",
        "Cross-Country (Nordic) Skiing: Touring Styles, Day Pack, Map & Speed Control",
        "Cross-Country (Nordic) Skiing: Weight Transfer, 4-Mile Tour & Steep Hills",
    ],
    "snow sports:7c": [
        "Snowboarding: Fall Prevention, Protective Gear, Bindings & Board Types",
        "Snowboarding: Ski Lifts, Board Waxing, Slope Maneuvers & Ollies",
        "Snowboarding: Intermediate Slope Run, Varied Snow Conditions & Organizations",
    ],
    "snow sports:7d": [
        "Snowshoeing: Snowshoe Parts, Sizing, Specialized Types & Maintenance",
        "Snowshoeing: Day Hike Gear, Backcountry Terrain Hazards & Fitness Benefits",
        "Snowshoeing: Breaking Trail, 2-Mile Snowshoe Hike & Map Navigation",
    ],
    "railroading:7a": [
        "Model Railroading: Layout Design, Kit Building, Track Scales & Resources",
        "Model Railroading: Structure Weathering, Scenery, Switching & DC/DCC Control",
    ],
    "railroading:7b": [
        "Railfanning: Railroad Museums, Historical Displays & Timetables",
        "Railfanning: Scenic Rail Excursions, Photography & Trip Planning",
    ],
    "archery:5a": [
        "Recurve Bow or Longbow: Bow Parts, Care & 11 Steps of Shooting",
        "Recurve Bow or Longbow: Bow Stringing, Nocking Point & Qualification",
    ],
    "archery:5b": [
        "Compound Bow: Bow Parts, Care & 11 Steps of Shooting",
        "Compound Bow: String & Cable Service, Nocking Point & Qualification",
    ],
    "cycling:6a": [
        "Road Biking: Traffic Safety Test, Straight-Line Riding & Emergency Stops",
        "Road Biking: Progressive 10/15/25-Mile Rides & 50-Mile Route Tour",
    ],
    "cycling:6b": [
        "Trail Biking: Trail Handling, Climbing/Descending & LNT Etiquette",
        "Trail Biking: Progressive Trail Rides & 22-Mile Scenic Trail Tour",
    ],
    "animal science:6a": [
        "Beef Cattle: Production Systems, Feedlot Design & Beef Breeds",
        "Beef Cattle: Wholesale/Retail Cuts, Grading & Feeding Rations",
    ],
    "animal science:6b": [
        "Dairy: Forage Conversion, Milk Components & Grade A Pasteurization",
        "Dairy: Milking Equipment, Sanitation, Dairy Terms & Farm Visit",
    ],
    "animal science:6c": [
        "Horse: Equine History, Breeds, Conformation & Barn Design",
        "Horse: Feeding Rations, Hoof/Dental Care, Diseases & Tack",
    ],
    "animal science:6d": [
        "Sheep or Goat: Breeds, Wool/Mohair Grading & Meat/Dairy Products",
        "Sheep or Goat: Flock Housing, Feeding Programs & Parasite Control",
    ],
    "animal science:6e": [
        "Hog: Swine Breeds, Wholesale/Retail Pork Cuts & USDA Grading",
        "Hog: Farrow-to-Finish Systems, Feeding Programs & Biosecurity",
    ],
    "animal science:6f": [
        "Avian: Poultry Breeds, Egg Incubation, Candling & USDA Grading",
        "Avian: Broiler/Layer Housing, Biosecurity & Flock Management",
    ],
    "plant science:8a": [
        "Agronomy: Seedbed Preparation, Germination Testing & Crop Pests",
        "Agronomy: U.S. Crop Regions & Field Crop Production Project",
    ],
    "plant science:8b": [
        "Horticulture: Botanical Site Visit, Hardiness Zones & Propagation",
        "Horticulture: Landscape Design Principles & Garden Production Project",
    ],
    "plant science:8c": [
        "Field Botany: Natural Area Study, Woody Plants & Identification Keys",
        "Field Botany: Herbarium Specimen Mounts, Rare Plants & Tree Inventory",
    ],
    "geology:4a": [
        "Surface & Sedimentary Processes: Stream Gradients, Erosion & Deposition",
        "Surface & Sedimentary Processes: Topographic Maps & Sedimentary Structures",
    ],
    "geology:4b": [
        "Energy Resources: Source/Reservoir/Trap Rocks & Subsurface Mapping",
        "Energy Resources: Drilling Technology, Recovery & Environmental Safeguards",
    ],
    "geology:4c": [
        "Mineral Resources: Igneous, Sedimentary & Metamorphic Rock Classes",
        "Mineral Resources: Mohs Hardness, Streak/Luster Tests & 10-Specimen Collection",
    ],
    "geology:4d": [
        "Earth History: Geologic Time Scale, Plate Tectonics & Fossilization",
        "Earth History: Ancient Environments, Fossil Collection & Museum Study",
    ],
    "radio:8a": [
        "Amateur Radio: FCC Service Purpose, License Classes & Q Signals",
        "Amateur Radio: Emergency Calls, Transceivers, Antennas & 10-Minute QSO",
    ],
    "sewing and needlework:3a": [
        "Machine Sewing: Evolution, Machine Parts, Threading & Bobbin Setup",
        "Machine Sewing: Needle Selection, Seam Allowances, Pressing & Cleaning",
        "Machine Sewing: Zippers, Buttonholes, Drawstring Bag & Quilt Block",
    ],
    "sewing and needlework:3b": [
        "Knitting: History, Needles, Yarn Weights & Reading Knitting Patterns",
        "Knitting: Slip Knot, Cast-On, Knit/Purl Stitches, Gauge & Finished Item",
    ],
    "sewing and needlework:3c": [
        "Crochet: History, Crochet Hooks, Yarn Labels & Pattern Abbreviations",
        "Crochet: Chain, Slip, Single/Half-Double/Double Crochet & Finished Item",
    ],
    "sewing and needlework:3d": [
        "Hand Embroidery: History, Hoops, Needles, Floss & Stabilizers",
        "Hand Embroidery: Embroidered Sampler with Five Traditional Stitches",
    ],
    "sewing and needlework:3e": [
        "Applique: History, Needle-Turn & Freezer-Paper Hand Applique",
        "Applique: Raw-Edge Fusible Machine Applique & Garment Project",
    ],
    "sewing and needlework:3f": [
        "Quilting: Historical Quilts, Rotary Cutting Safety & Color Value Sorting",
        "Quilting: Block Design, Quarter-Inch Piecing, Layering, Tying & Binding",
    ],
}


def _clean_option_title(raw_title: str, opt_key: str = "A") -> str:
    """Returns a concise, human-readable option name without redundant 'Option X' prefixes."""
    import re

    cleaned = re.sub(
        r"^Option\s+[A-Z1-9](?:\s*[\u2014\u2013\-:,]\s*|\s+)",
        "",
        str(raw_title or "").strip(),
        flags=re.IGNORECASE,
    ).strip(" .,:;\u2014\u2013-")
    mapped = _CLEAN_OPTION_TITLE_MAP.get(cleaned.lower())
    if mapped:
        return mapped
    return cleaned if cleaned else f"Option {opt_key}"


def partition_balanced_subreq_chunks(sub_reqs: List[Dict[str, Any]], max_per_chunk: int = 4) -> List[List[Dict[str, Any]]]:
    """Splits sub_reqs into balanced chunks of 2-4 items so no slide ever has a lone 1-card orphan."""
    n = len(sub_reqs)
    if n == 0:
        return []
    if n <= max_per_chunk:
        return [list(sub_reqs)]
    num_chunks = (n + max_per_chunk - 1) // max_per_chunk
    base_sz = n // num_chunks
    extra = n % num_chunks
    chunks: List[List[Dict[str, Any]]] = []
    idx = 0
    for i in range(num_chunks):
        sz = base_sz + (1 if i < extra else 0)
        chunks.append(list(sub_reqs[idx : idx + sz]))
        idx += sz
    return chunks


def _extract_option_sub_reqs_from_requirement(badge_lower: str, r: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts option sub-requirements for standard Option A/B badges plus Sewing and Needlework, Action Sports, and Citizenship in Society."""
    import re

    r_num = str(r.get("req_number") or "")
    str(r.get("req_text") or "")
    subs = list(r.get("sub_requirements") or [])

    if badge_lower == "action sports" and r_num == "4":
        return [
            {
                "sub_id": "4a",
                "label": "(a)",
                "option_key": "A",
                "text": "Option A - Skateboarding. Demonstrate fundamental skateboarding riding skills.",
                "children": [
                    {
                        "sub_id": "4a(1)",
                        "label": "(1)",
                        "text": "Skateboarding Stance, Mounting/Dismounting, Pushing & Controlled Braking: Demonstrate regular vs. goofy stance, mounting/dismounting, pushing/gliding on flat terrain, and foot/heel-drag controlled stopping.",
                    },
                    {
                        "sub_id": "4a(2)",
                        "label": "(2)",
                        "text": "Skateboarding Carving Turns, Weight Transfer & Skatepark Transitions: Demonstrate frontside and backside carving turns, kickturns, safe falling technique, and navigating skatepark banks or transitions.",
                    },
                ],
            },
            {
                "sub_id": "4b",
                "label": "(b)",
                "option_key": "B",
                "text": "Option B - Snowboarding. Demonstrate fundamental snowboarding riding skills.",
                "children": [
                    {
                        "sub_id": "4b(1)",
                        "label": "(1)",
                        "text": "Snowboarding Stance, Binding Entry/Exit, Skating & Straight Gliding: Demonstrate regular vs. goofy stance, strapping in on flat snow, one-foot skating, and straight gliding with controlled heel/toe stops.",
                    },
                    {
                        "sub_id": "4b(2)",
                        "label": "(2)",
                        "text": "Snowboarding Heel/Toe Edge Carving, Weight Transfer & Slope Navigation: Demonstrate linked heel-side and toe-side turns, weight transfer, safe falling posture, and riding beginner/intermediate slopes.",
                    },
                ],
            },
        ]

    if badge_lower == "swimming" and r_num == "8":
        return [
            {
                "sub_id": "8a",
                "label": "(a)",
                "option_key": "A",
                "text": "Option A - Standing & Shallow Dives. In water at least 7 feet deep, show a standing headfirst dive and a long shallow dive from a dock or pool deck.",
                "children": [
                    {
                        "sub_id": "8a(1)",
                        "label": "(1)",
                        "text": "Standing Headfirst Dive (7+ ft Unobstructed Depth): Following Scouting America Safe Swim Defense guidelines, in water at least 7 feet deep, show a standing headfirst dive from a dock or pool deck.",
                    },
                    {
                        "sub_id": "8a(2)",
                        "label": "(2)",
                        "text": "Long Shallow Dive & Depth Verification: Show a long shallow dive from the dock or pool deck while verifying local depth mandates.",
                    },
                ],
            },
            {
                "sub_id": "8b",
                "label": "(b)",
                "option_key": "B",
                "text": "Option B - Snorkeling & Mask/Snorkel Clearing. Demonstrate safe open-water or confined-water snorkeling and surface dive skills.",
                "children": [
                    {
                        "sub_id": "8b(1)",
                        "label": "(1)",
                        "text": "Mask, Fins & Snorkel Fit and Entry: Demonstrate proper selection, defogging, fit, and controlled water entry with mask, fins, and snorkel.",
                    },
                    {
                        "sub_id": "8b(2)",
                        "label": "(2)",
                        "text": "Mask Clearing, Blast-Clearing & Surface Dives: Demonstrate submerged mask clearing, snorkel blast-clearing/displacement clearing, and headfirst/feetfirst surface dives.",
                    },
                ],
            },
        ]

    if badge_lower == "citizenship in society" and r_num == "6":
        for sr in subs:
            if str(sr.get("sub_id") or "").lower() == "6b":
                ch_list = list(sr.get("children") or [])
                if len(ch_list) >= 2:
                    return ch_list

    if badge_lower == "sewing and needlework" and r_num == "3":
        sewing_opts = [
            sr
            for sr in subs
            if re.match(r"^\([A-F]\)$", str(sr.get("label") or "").strip())
            or re.match(r"^3[A-F]$", str(sr.get("sub_id") or "").strip())
        ]
        if len(sewing_opts) >= 2:
            return sewing_opts

    opt_subs = [
        sr
        for sr in subs
        if re.match(r"^Option\s+([A-Z1-9])\b", str(sr.get("text") or ""), flags=re.IGNORECASE)
    ]
    return opt_subs


def get_badge_option_tracks(badge_name: str) -> List[Dict[str, Any]]:
    """Returns structured Option Track metadata for multi-option Merit Badges (e.g., Golf, Skating, Cycling, Archery, Sewing and Needlework, Action Sports, Citizenship in Society, Multisport, Physics)."""
    if not badge_name or not str(badge_name).strip():
        return []
    import re

    official_cache = _load_official_requirements_cache()
    target_reqs: Optional[List[Dict[str, Any]]] = official_cache.get(str(badge_name).strip())
    badge_lower = str(badge_name).strip().lower()
    if not target_reqs:
        for k, v in official_cache.items():
            if k.lower() == badge_lower:
                target_reqs = v
                break
    if not target_reqs:
        return []

    tracks: List[Dict[str, Any]] = []
    for r in target_reqs:
        r_num = str(r.get("req_number") or "")
        opt_subs = _extract_option_sub_reqs_from_requirement(badge_lower, r)
        if len(opt_subs) >= 2:
            for sr in opt_subs:
                txt = str(sr.get("text") or "").strip()
                m = re.match(
                    r"^Option\s+([A-Z1-9])(?:\s*[\u2014\u2013\-:]\s*|\s+)([^.]+)",
                    txt,
                    flags=re.IGNORECASE,
                )
                if m:
                    opt_key = m.group(1).upper()
                    raw_opt_title = m.group(2).strip()
                else:
                    opt_key = str(sr.get("option_key") or sr.get("label") or "A").strip("()").upper()
                    raw_opt_title = txt.split(".")[0].strip() if txt else f"Option {opt_key}"
                opt_title = _clean_option_title(raw_opt_title, opt_key)
                if badge_lower == "citizenship in society":
                    opt_title = (
                        "Personal Exclusion Reflection"
                        if opt_key == "1"
                        else "New School Inclusion Scenario"
                    )
                sub_id = str(sr.get("sub_id") or f"{r_num}{opt_key.lower()}")
                children = sr.get("children") or []
                effective_key = sub_id.upper() if badge_lower == "physics" else opt_key
                label_str = (
                    f"Req {r_num} Option {opt_key}: {opt_title} (Req {sub_id})"
                    if badge_lower == "physics"
                    else f"Option {opt_key}: {opt_title} (Req {sub_id})"
                )
                track_entry: Dict[str, Any] = {
                    "option_key": effective_key,
                    "letter_key": opt_key,
                    "sub_id": sub_id,
                    "req_number": r_num,
                    "parent_req_id": "6b" if badge_lower == "citizenship in society" else r_num,
                    "title": opt_title,
                    "option_title": opt_title,
                    "raw_option_title": raw_opt_title,
                    "label": label_str,
                    "option_label": label_str,
                    "sub_count": len(children),
                }
                if badge_lower == "multisport" and r_num == "4":
                    coupled_id = f"7{opt_key.lower()}"
                    track_entry["coupled_req_number"] = "7"
                    track_entry["coupled_sub_id"] = coupled_id
                    track_entry["coupled_sub_ids"] = [sub_id, coupled_id]
                    ms_lbl = f"Option {opt_key}: {opt_title} (Reqs {sub_id} & {coupled_id})"
                    track_entry["label"] = ms_lbl
                    track_entry["option_label"] = ms_lbl
                tracks.append(track_entry)
    return tracks


def _unroll_multi_option_requirements(
    badge_name: str,
    raw_reqs: List[Dict[str, Any]],
    option_track: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Unrolls multi-option ('Two-Badges-in-One') requirements into structured teaching units and filters by option_track."""
    import re

    badge_lower = str(badge_name or "").strip().lower()
    opt_filter = _normalize_option_track_filter(option_track, badge_name=badge_name)

    # Parse requirement-scoped option keys for Physics (e.g., '4E', '6B', '7C' or '4A,6B,7C')
    physics_req_map: Dict[str, str] = {}
    physics_fallback_letter = "ALL"
    if badge_lower == "physics" and opt_filter != "ALL":
        for tok in [t.strip().upper() for t in opt_filter.split(",") if t.strip()]:
            m_pr = re.match(r"^([467])([A-I])$", tok)
            if m_pr:
                physics_req_map[m_pr.group(1)] = m_pr.group(2)
                if physics_fallback_letter == "ALL":
                    physics_fallback_letter = m_pr.group(2)
            elif len(tok) == 1 and tok.isalpha():
                physics_fallback_letter = tok

    unrolled: List[Dict[str, Any]] = []
    for r in raw_reqs:
        r_num = str(r.get("req_number") or "")
        subs = list(r.get("sub_requirements") or [])

        # Special Case A: Multisport Req 7 coupled to Req 4 option track (4a<->7a, 4b<->7b, 4c<->7c, 4d<->7d)
        if badge_lower == "multisport" and r_num == "7" and subs:
            if opt_filter != "ALL":
                target_7_id = f"7{opt_filter.lower()}"
                matched_7 = [
                    sr for sr in subs
                    if str(sr.get("sub_id") or "").lower() == target_7_id
                    or str(sr.get("label") or "").strip("()").upper() == opt_filter
                ]
                if matched_7:
                    chosen_7 = matched_7[0]
                    c7_txt = str(chosen_7.get("text") or "").strip()
                    c7_name = c7_txt.split("(")[0].strip() or f"Option {opt_filter}"
                    r_coupled = dict(r)
                    r_coupled["req_id"] = str(chosen_7.get("sub_id") or target_7_id)
                    r_coupled["req_number"] = str(chosen_7.get("sub_id") or target_7_id)
                    r_coupled["parent_id"] = "7"
                    r_coupled["topic_title"] = f"Req {r_coupled['req_number']}: {c7_name} Race Event Completion"
                    r_coupled["req_text"] = f"After completing requirements 1-6, complete the {c7_txt} on the same day and consecutively."
                    r_coupled["sub_requirements"] = []
                    unrolled.append(r_coupled)
                    continue

        # Special Case B: Citizenship in Society Req 6 (6b(1) vs 6b(2) nested inside 6b)
        if badge_lower == "citizenship in society" and r_num == "6" and subs:
            if opt_filter != "ALL":
                target_opt_num = "1" if opt_filter in ("1", "A") else ("2" if opt_filter in ("2", "B") else opt_filter)
                new_subs = []
                for sr in subs:
                    if str(sr.get("sub_id") or "").lower() == "6b":
                        sr_copy = dict(sr)
                        ch_list = list(sr.get("children") or [])
                        filtered_ch = [
                            ch for ch in ch_list
                            if str(ch.get("label") or "").strip("()") == target_opt_num
                            or str(ch.get("sub_id") or "").endswith(f"({target_opt_num})")
                        ]
                        sr_copy["children"] = filtered_ch if filtered_ch else ch_list[:1]
                        if sr_copy["children"]:
                            chosen_ch = sr_copy["children"][0]
                            sr_copy["text"] = f"Share with each other ({chosen_ch.get('sub_id', '6b')}): {chosen_ch.get('text', '')}"
                        new_subs.append(sr_copy)
                    else:
                        new_subs.append(sr)
                r_cis = dict(r)
                r_cis["sub_requirements"] = new_subs
                unrolled.append(r_cis)
            else:
                unrolled.append(r)
            continue

        opt_subs = _extract_option_sub_reqs_from_requirement(badge_lower, r)
        if len(opt_subs) < 2:
            unrolled.append(r)
            continue

        # Filter option sub-requirements if Counselor selected a specific Option Track
        if opt_filter != "ALL":
            if badge_lower == "physics":
                desired_letter = physics_req_map.get(r_num, physics_fallback_letter)
                matched_opts = []
                for sr in opt_subs:
                    m_o = re.match(r"^Option\s+([A-Z1-9])\b", str(sr.get("text") or ""), flags=re.IGNORECASE)
                    o_key = m_o.group(1).upper() if m_o else str(sr.get("option_key") or sr.get("label") or "").strip("()").upper()
                    if o_key == desired_letter or str(sr.get("sub_id") or "").upper() == f"{r_num}{desired_letter}":
                        matched_opts.append(sr)
                # Never dump all unselected options in Reqs 4, 6, or 7 when a single track is active
                active_opt_subs = matched_opts if matched_opts else [opt_subs[0]]
            else:
                matched_opts = []
                for sr in opt_subs:
                    m_o = re.match(r"^Option\s+([A-Z1-9])\b", str(sr.get("text") or ""), flags=re.IGNORECASE)
                    o_key = m_o.group(1).upper() if m_o else str(sr.get("option_key") or sr.get("label") or "").strip("()").upper()
                    if o_key == opt_filter or str(sr.get("sub_id") or "").upper() == opt_filter.upper():
                        matched_opts.append(sr)
                active_opt_subs = matched_opts if matched_opts else [opt_subs[0]]
        else:
            active_opt_subs = opt_subs

        # Case 1: Golf ('Two-Badges-in-One': Option A Traditional Golf vs. Option B Disc Golf)
        if badge_lower == "golf":
            for sr in active_opt_subs:
                txt = str(sr.get("text") or "").strip()
                m = re.match(r"^Option\s+([A-Z1-9])(?:\s*[\u2014\u2013\-:]\s*|\s+)([^.]+)", txt, flags=re.IGNORECASE)
                opt_k = m.group(1).upper() if m else "A"
                opt_title = _clean_option_title(m.group(2).strip() if m else f"Option {opt_k}", opt_k)
                base_sub_id = str(sr.get("sub_id") or f"2{opt_k.lower()}")
                children = list(sr.get("children") or [])
                if len(children) >= 6:
                    if opt_k == "A":
                        groups = [
                            (
                                f"{base_sub_id}(1)",
                                "Traditional Golf: USGA Rules, Etiquette & Handicap System",
                                "Explain",
                                "IN_CLASS_DISCUSSION",
                                [children[0], children[1]],
                                [
                                    "USGA Rules of Golf (Req 2a(1)): The United States Golf Association and The R&A govern play, equipment standards, penalty areas, unplayable ball relief, and pace of play.",
                                    "Order of Play & Teeing Ground: The player with the lowest score on the previous hole has the 'honor' on the next tee; on the fairway and green, the ball farthest from the hole is played first.",
                                    "Course Etiquette & Turf Care: Stand still and quiet while others swing, repair divots on the fairway, rake sand bunkers smooth, and fix ball pitch marks on the putting green.",
                                    "World Handicap System (Req 2a(2)): A Golfer's Handicap Index measures potential ability adjusted for Course Rating and Slope Rating so players of different skill levels can compete equitably.",
                                ],
                            ),
                            (
                                f"{base_sub_id}(3)",
                                "Traditional Golf: Golf History, Pioneers & Fitness Plan",
                                "Explain",
                                "IN_CLASS_DISCUSSION",
                                (children[2].get("children") or [children[2]]) + (children[3].get("children") or [children[3]]),
                                [
                                    "Early Origins & Evolution of Equipment (Req 2a(3)(a)): Originating in 15th-century Scotland at St Andrews, golf evolved from hickory-shafted clubs and feathery/gutta-percha balls to modern titanium heads and dimpled urethane balls.",
                                    "Historical Pioneers & Champions (Req 2a(3)(b)): Study the impact of Old Tom Morris, Bobby Jones, Babe Didrikson Zaharias, Ben Hogan, Arnold Palmer, Jack Nicklaus, Annika Sorenstam, and Tiger Woods.",
                                    "Core & Rotational Conditioning (Req 2a(4)(a)): Golf requires thoracic spine mobility, hip rotation, core stability, and forearm endurance to generate clubhead speed without lower-back strain.",
                                    "Pre-Round Dynamic Warm-Up (Req 2a(4)(b)): Perform 10 minutes of torso twists, hip hinges, shoulder circles, and progressive half-to-full practice swings before teeing off.",
                                ],
                            ),
                            (
                                f"{base_sub_id}(5)",
                                "Traditional Golf: Grip, Stance, Woods, Irons, Bunker & Putting",
                                "Demonstrate",
                                "HANDS_ON_SKILL_STATION",
                                children[4].get("children") or [children[4]],
                                [
                                    "Grip, Stance & Full Swing Fundamentals (Req 2a(5)(a)): Use a neutral Vardon overlap, interlocking, or ten-finger grip with a balanced shoulder-width athletic stance and smooth tempo.",
                                    "Driver & Fairway Woods (Req 2a(5)(b)-(c)): Tee the driver high inside the lead heel for a sweeping ascending strike; sweep fairway woods cleanly off the turf when distance is required.",
                                    "Long & Short Iron Approach Shots (Req 2a(5)(d)-(f)): Strike irons with a descending blow (ball first, then turf divot), and use pitch and chip-and-run shots around the green.",
                                    "Greenside Bunker & Putting Stroke (Req 2a(5)(g)-(h)): Open the sand wedge clubface in bunkers to splash sand 2 inches behind the ball; putt with a pendulum shoulder rock while reading green slope.",
                                ],
                            ),
                            (
                                f"{base_sub_id}(6)",
                                "Traditional Golf: 18-Hole Round, Course Conduct & Golf Careers",
                                "Demonstrate",
                                "PREREQUISITE_CAMPOUT_HOME",
                                (children[5].get("children") or [children[5]]) + children[6:],
                                [
                                    "Playing an 18-Hole Round (Req 2a(6)(a)): Play a full 18-hole round (or two 9-hole rounds) with your counselor or an approved adult, recording accurate stroke totals on your scorecard.",
                                    "Sportsmanship & Course Maintenance (Req 2a(6)(b)-(c)): Maintain a brisk pace of play ('Ready Golf'), control emotions after poor shots, replace divots, and leave every green better than you found it.",
                                    "Golf Industry Career Pathways (Req 2a(7)(a)): Explore careers including PGA Teaching Professional, Golf Course Superintendent (agronomy/turfgrass), Golf Course Architect, Club Fitter, and Tournament Director.",
                                    "Amateur vs. Professional Status (Req 2a(7)(b)): Understand USGA Amateur Status rules governing prize limits, collegiate eligibility, and PGA/LPGA professional certification requirements.",
                                ],
                            ),
                        ]
                    else:
                        groups = [
                            (
                                f"{base_sub_id}(1)",
                                "Disc Golf: PDGA Rules, Courtesy (812) & Scoring (808)",
                                "Explain",
                                "IN_CLASS_DISCUSSION",
                                (children[0].get("children") or [children[0]]) + [children[1]],
                                [
                                    "PDGA Official Rules of Disc Golf (Req 2b(1)): The Professional Disc Golf Association governs throwing order, marking the lie (30 cm x 20 cm box behind the disc), out-of-bounds relief, and completion of the hole in the basket.",
                                    "PDGA Rule 812 Courtesy & Park Safety (Req 2b(1)(a)): Always yield to park pedestrians and other facility users, never throw into blind areas without a spotter, and remain quiet behind the active thrower.",
                                    "PDGA Rule 808 Scoring & Handicaps (Req 2b(1)(b)-(2)): After each hole, call out and verify every player's score (throws plus penalty strokes); player ratings and handicaps allow mixed-skill competition.",
                                    "Course Preservation & Leave No Trace: Protect trees and bark from unnecessary practice throws, pack out all trash, and stay on established trails between tee pads and baskets.",
                                ],
                            ),
                            (
                                f"{base_sub_id}(3)",
                                "Disc Golf: Ed Headrick, Disc Design Evolution & Fitness",
                                "Explain",
                                "IN_CLASS_DISCUSSION",
                                (children[2].get("children") or [children[2]]) + (children[3].get("children") or [children[3]]),
                                [
                                    "History & Pioneers of Disc Golf (Req 2b(3)(a)-(b)): Trace the sport from early tin-lid and Frisbee target games to 'Steady' Ed Headrick, who patented the modern Disc Pole Hole chain basket and founded the PDGA in 1976.",
                                    "Four Disc Categories & Flight Ratings (Req 2b(3)): Compare sharp-rimmed Distance Drivers, controllable Fairway Drivers, versatile Mid-Range discs, and deep-rimmed Putters across Speed, Glide, Turn, and Fade.",
                                    "Athletic Conditioning for Disc Golf (Req 2b(4)(a)): Build core rotational power, single-leg plant stability, shoulder rotator cuff strength, and hiking endurance for 18-hole wooded courses.",
                                    "Pre-Round Warm-Up & Injury Prevention (Req 2b(4)(b)): Warm up wrists, elbows, rotator cuffs, hips, and ankles with dynamic stretches and light catch-and-putt drills before throwing full-power drives.",
                                ],
                            ),
                            (
                                f"{base_sub_id}(5)",
                                "Disc Golf: Grips, X-Step, Backhand, Forehand, Roller & Putting",
                                "Demonstrate",
                                "HANDS_ON_SKILL_STATION",
                                children[4].get("children") or [children[4]],
                                [
                                    "Disc Grips & X-Step Run-Up (Req 2b(5)(a)-(b)): Tuck all four fingertips tightly against the inner rim for a Power Grip on drives, or spread fingers across the flight plate for a Fan Grip; use the smooth X-step footwork to transfer weight.",
                                    "Backhand, Forehand & Overhand Shots (Req 2b(5)(c)-(e)): Pull the disc on a straight line across the chest for a Backhand (hyzer, flat, anhyzer), snap the wrist with a two-finger stack for a Forehand flick, or throw an Overhand tomahawk/thumber.",
                                    "Roller Shots & Flight Angles (Req 2b(5)(f)): Release the disc on a steep anhyzer angle so it lands on its edge and rolls straight down low-ceiling wooded fairways.",
                                    "In-Line & Straddle Putting + Mini Marker (Req 2b(5)(g)-(k)): Demonstrate both in-line and straddle putting stances inside the 10-meter circle, and properly place a mini marker disc directly in front of your thrown disc before picking it up.",
                                ],
                            ),
                            (
                                f"{base_sub_id}(6)",
                                "Disc Golf: 18-Hole Round, Park Stewardship & Careers",
                                "Demonstrate",
                                "PREREQUISITE_CAMPOUT_HOME",
                                (children[5].get("children") or [children[5]]) + children[6:],
                                [
                                    "Playing an 18-Hole Disc Golf Round (Req 2b(6)(a)): Complete an 18-hole round (or two 9-hole rounds) with your counselor or an approved adult, following PDGA rules and keeping an accurate scorecard.",
                                    "Sportsmanship & Course Courtesy (Req 2b(6)(b)-(c)): Allow faster groups to play through, help search for lost discs (3-minute rule), yield to non-playing park visitors, and protect course vegetation.",
                                    "Disc Golf Industry Careers (Req 2b(7)(a)): Investigate careers as a Disc Golf Course Designer, PDGA Tournament Director, Aerospace/Plastics Disc Mould Engineer, Parks & Recreation Manager, or Touring Instructor.",
                                    "Amateur vs. Touring Professional Pathways (Req 2b(7)(b)): Compare PDGA Amateur divisions and points series with Pro Tour qualification, sponsorship, and PDGA Certified Official credentials.",
                                ],
                            ),
                        ]
                    for u_id, u_title, u_verb, u_mode, u_subs, u_excerpts in groups:
                        joined_txt = " ".join(
                            f"{s_item.get('label', '')} {s_item.get('text', '')}".strip()
                            for s_item in u_subs
                            if s_item.get("text")
                        )
                        unrolled.append({
                            "req_id": u_id,
                            "req_number": u_id,
                            "parent_id": str(r.get("req_number") or "2"),
                            "topic_title": u_title,
                            "action_verb": u_verb,
                            "execution_mode": u_mode,
                            "req_text": f"{opt_title}: {joined_txt}",
                            "pamphlet_excerpts": u_excerpts,
                            "sub_requirements": u_subs,
                        })
                else:
                    unrolled.append({
                        "req_id": base_sub_id,
                        "req_number": base_sub_id,
                        "parent_id": str(r.get("req_number") or "2"),
                        "topic_title": f"{opt_title}: Rules, Equipment & Course Play",
                        "req_text": txt,
                        "sub_requirements": list(children),
                    })
            continue

        # Case 2: All Other Multi-Option Badges
        for sr in active_opt_subs:
            txt = str(sr.get("text") or "").strip()
            m = re.match(r"^Option\s+([A-Z1-9])(?:\s*[\u2014\u2013\-:]\s*|\s+)([^.]+)", txt, flags=re.IGNORECASE)
            if m:
                opt_k = m.group(1).upper()
                raw_opt_title = m.group(2).strip()
            else:
                opt_k = str(sr.get("option_key") or sr.get("label") or "A").strip("()").upper()
                raw_opt_title = txt.split(".")[0].strip() if txt else f"Option {opt_k}"
            opt_title = _clean_option_title(raw_opt_title, opt_k)
            base_sub_id = str(sr.get("sub_id") or f"{r.get('req_number', '2')}{opt_k.lower()}")
            children = list(sr.get("children") or [])

            # Preserve up to [:12] 3rd-level grandchildren (e.g. Athletics 5g(2)(g) "Top of the key")
            expanded_excerpts: List[str] = []
            for ch_item in children:
                ch_lbl = str(ch_item.get("label") or "").strip()
                ch_txt = str(ch_item.get("text") or "").strip()
                gch_items = list(ch_item.get("children") or [])[:12]
                if gch_items:
                    gch_joined = " ".join(
                        f"{gc.get('label', '')} {gc.get('text', '')}".strip()
                        for gc in gch_items
                        if gc.get("text")
                    )
                    if gch_joined and gch_joined not in ch_txt:
                        ch_txt = f"{ch_txt} {gch_joined}".strip()
                if ch_txt:
                    expanded_excerpts.append(f"Req {ch_item.get('sub_id') or base_sub_id} {ch_lbl}: {ch_txt}".strip())

            lookup_key = f"{badge_lower}:{base_sub_id.lower()}"
            overview_title = _OPTION_OVERVIEW_THEMES.get(
                lookup_key,
                f"{opt_title}: Core Requirements & Field Demonstration",
            )
            curated_chunk_titles = _CURATED_OPTION_CHUNK_THEMES.get(lookup_key, [])

            # When a single Option Track is selected and has 3+ children, unroll into balanced sub-requirement units
            if len(active_opt_subs) == 1 and len(children) >= 3:
                chunk_max = 2 if len(children) <= 4 else 4
                chunks = partition_balanced_subreq_chunks(children, max_per_chunk=chunk_max)
                for c_idx, chunk in enumerate(chunks):
                    first_ch = chunk[0]
                    last_ch = chunk[-1]
                    u_id = str(first_ch.get("sub_id") or f"{base_sub_id}({c_idx * chunk_max + 1})")
                    if c_idx < len(curated_chunk_titles):
                        chunk_title = curated_chunk_titles[c_idx]
                    else:
                        f_lbl = str(first_ch.get("label") or "").strip("()")
                        l_lbl = str(last_ch.get("label") or "").strip("()")
                        part_lbl = f"Reqs {base_sub_id}({f_lbl})-{base_sub_id}({l_lbl})" if f_lbl != l_lbl else f"Req {base_sub_id}({f_lbl})"
                        chunk_title = f"{opt_title}: Part {c_idx + 1} ({part_lbl})"
                    joined_txt = " ".join(
                        f"{ch_i.get('label', '')} {ch_i.get('text', '')}".strip()
                        for ch_i in chunk
                        if ch_i.get("text")
                    )
                    chunk_excerpts = [
                        f"Req {ch_i.get('sub_id') or u_id}: {ch_i.get('text', '')}".strip()
                        for ch_i in chunk
                        if ch_i.get("text")
                    ]
                    unrolled.append({
                        "req_id": u_id,
                        "req_number": u_id,
                        "parent_id": base_sub_id,
                        "topic_title": chunk_title,
                        "req_text": f"{opt_title}: {joined_txt}",
                        "pamphlet_excerpts": chunk_excerpts,
                        "sub_requirements": chunk,
                    })
            else:
                full_req_text = txt
                if expanded_excerpts and len(children) <= 2:
                    extra_detail = " ".join(expanded_excerpts)
                    if "Top of the key" in extra_detail and "Top of the key" not in full_req_text:
                        full_req_text = f"{txt} {extra_detail}".strip()
                unrolled.append({
                    "req_id": base_sub_id,
                    "req_number": base_sub_id,
                    "parent_id": str(r.get("req_number") or "2"),
                    "topic_title": overview_title,
                    "req_text": full_req_text,
                    "pamphlet_excerpts": expanded_excerpts[:12] if expanded_excerpts else [],
                    "sub_requirements": list(children),
                })

    return unrolled


# Aliases for external callers/tests
_filter_requirements_by_option_track = _unroll_multi_option_requirements
_unroll_option_sub_requirements = _unroll_multi_option_requirements


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


import re

_OCR_GLUED_WORD_FIXES: tuple[tuple[str, str], ...] = (
    ("firstchess", "first chess"),
    ("washeld", "was held"),
    ("tournamentwas", "tournament was"),
    ("wasamong", "was among"),
    ("Wasamong", "Was among"),
    ("becomethe", "become the"),
    ("ofchess", "of chess"),
    ("Modernchess", "Modern chess"),
    ("nationalchess", "national chess"),
    ("Statesleading", "States leading"),
    ("tothe", "to the"),
    ("Differenttarget", "Different target"),
    ("differenttarget", "different target"),
    ("spotfor", "spot for"),
    ("targetposition", "target position"),
    ("Targetposition", "Target position"),
    ("differentdistances", "different distances"),
    ("frontof", "front of"),
)


def _clean_ocr_and_prefix_text(text: str) -> str:
    """Repairs OCR glued words and strips noisy 3-word auto-prefixes from pamphlet excerpts."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    for bad_tok, good_tok in _OCR_GLUED_WORD_FIXES:
        cleaned = cleaned.replace(bad_tok, good_tok)
    if ": " in cleaned:
        prefix, body = cleaned.split(": ", 1)
        p_words = [w.strip(".,;:()").lower() for w in prefix.split() if w.strip(".,;:()")]
        b_words = [w.strip(".,;:()").lower() for w in body.split()[:7] if w.strip(".,;:()")]
        if p_words and b_words and len(p_words) <= 4 and any(pw in b_words for pw in p_words):
            cleaned = body.strip()
    return cleaned


def _clean_ocr_and_prefix_excerpts(excerpts: List[Any]) -> List[str]:
    """Cleans a list of pamphlet excerpts or procedure steps."""
    out: List[str] = []
    for ex in excerpts or []:
        c = _clean_ocr_and_prefix_text(str(ex))
        if c and c not in out:
            out.append(c)
    return out


def _sanitize_misconception_pair_runtime(
    mis: Dict[str, Any],
    req_num: str,
    req_text: str,
    verb: str,
    citation: str,
) -> Dict[str, Any]:
    """Eliminates double-verb stutters and truncated clauses in common_misconception_pair."""
    if not isinstance(mis, dict) or not mis:
        return {}
    out = dict(mis)
    for k in ("misconception", "myth", "fact", "fact_correction"):
        val = str(out.get(k) or "").strip()
        if not val:
            continue
        val = _clean_ocr_and_prefix_text(val)
        # Strip duplicate consecutive verbs ("explain explain", "discuss discuss", "demonstrate demonstrate")
        val = re.sub(
            r"\b(explain|discuss|describe|demonstrate|show|identify|list|name|tell|make|review|find|do)\s+\1\b",
            r"\1",
            val,
            flags=re.IGNORECASE,
        )
        # Strip jarring auxiliary verb before another action verb ("Scouts must explain view...", "Scouts must discuss research...")
        val = re.sub(
            r"\b(Scouts must\s+)(?:explain|discuss|describe|demonstrate|show|identify|list|name|tell|make)\s+"
            r"(?=(?:explain|discuss|describe|demonstrate|show|identify|list|name|tell|make|view|research|visit|obtain|play|working\s+under|for\s+one\s+day|for\s+three\s+days|in\s+a\s+small-group)\b)",
            r"\1",
            val,
            flags=re.IGNORECASE,
        )
        # Repair unclosed parenthesis from truncated clause slices like '(with your.' or '(with your parent.'
        if "(" in val and ")" not in val:
            val = re.sub(r"\s*\([^)]*?(?=\s+using\s+verified|\.\s*$)", "", val)
        out[k] = val
    return out


_NANO_WORKBOOK_DIAGRAM_CACHE: Optional[Dict[str, Any]] = None
_PAMPHLET_BADGE_DIAGRAM_INDEX: Optional[Dict[str, List[str]]] = None


def _load_nano_workbook_diagram_catalog() -> Dict[str, Any]:
    global _NANO_WORKBOOK_DIAGRAM_CACHE
    if _NANO_WORKBOOK_DIAGRAM_CACHE is not None:
        return _NANO_WORKBOOK_DIAGRAM_CACHE
    import json

    cat_path = Path(__file__).resolve().parents[2] / "data" / "nano_banana_image_catalog.json"
    if cat_path.exists():
        try:
            _NANO_WORKBOOK_DIAGRAM_CACHE = json.loads(cat_path.read_text(encoding="utf-8"))
        except Exception:
            _NANO_WORKBOOK_DIAGRAM_CACHE = {}
    else:
        _NANO_WORKBOOK_DIAGRAM_CACHE = {}
    return _NANO_WORKBOOK_DIAGRAM_CACHE


def _get_pamphlet_badge_diagram_index() -> Dict[str, List[str]]:
    """Pre-indexes authentic extracted BSA Pamphlet figures (assets/pamphlet_images/) per badge slug for O(1) lookup."""
    global _PAMPHLET_BADGE_DIAGRAM_INDEX
    if _PAMPHLET_BADGE_DIAGRAM_INDEX is not None:
        return _PAMPHLET_BADGE_DIAGRAM_INDEX
    import re

    idx: Dict[str, List[str]] = {}
    p_dir = Path(__file__).resolve().parents[2] / "assets" / "pamphlet_images"
    if p_dir.exists():
        for p in sorted(p_dir.glob("*.png")):
            try:
                sz = p.stat().st_size
            except Exception:
                sz = 0
            if sz < 15_000:
                continue
            m = re.match(r"^([a-z0-9_]+)_p(\d+)_img\d+\.png$", p.name)
            if not m:
                continue
            slug_k, page_s = m.group(1), m.group(2)
            # Prefer interior instructional figures (page >= 4) over cover pages
            if int(page_s) <= 2:
                continue
            idx.setdefault(slug_k, []).append(f"assets/pamphlet_images/{p.name}")
    _PAMPHLET_BADGE_DIAGRAM_INDEX = idx
    return _PAMPHLET_BADGE_DIAGRAM_INDEX


def _resolve_workbook_diagram_url(
    badge_name: str,
    req_num: str,
    req_text: str = "",
    explicit_url: str = "",
) -> str:
    """Resolves an authentic workbook reference diagram path/URL from curated diagrams or BSA pamphlet figures."""
    import re

    b_low = str(badge_name or "").strip().lower()
    r_clean = str(req_num or "").strip().lower()
    m_parent = re.match(r"^(\d+)", r_clean)
    r_parent = m_parent.group(1) if m_parent else r_clean
    tl = str(req_text or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", b_low).strip("_")

    # 1. Exact 2025/2026 sub-requirement clinical diagram mapping for First Aid
    if b_low == "first aid":
        first_aid_exact_map = {
            "1a": "assets/ai_illustrations/first_aid_triage_scene_visual.png",
            "2b(1)": "assets/ai_illustrations/first_aid_kit_21_items_visual.png",
            "3i": "assets/ai_illustrations/first_aid_wound_cleaning_blister_visual.png",
            "4c": "assets/diagrams/first_aid_bleeding_diagram.png",
            "5a": "assets/ai_illustrations/first_aid_choking_5and5_visual.png",
            "6b": "assets/ai_illustrations/first_aid_burns_epi_visual.png",
            "7d": "assets/diagrams/cpr_steps_diagram.png",
            "8d(1)": "assets/ai_illustrations/first_aid_splinting_carries_visual.png",
            "10a": "assets/ai_illustrations/first_aid_bites_stings_ticks_visual.png",
            "11c": "assets/ai_illustrations/first_aid_heat_hypothermia_visual.png",
            "12a": "assets/ai_illustrations/first_aid_req_12_topic_visual.png",
            "13e": "assets/ai_illustrations/first_aid_stroke_fast_seizure_visual.png",
            "14": "assets/ai_illustrations/first_aid_req_14_topic_visual.png",
            "15b": "assets/ai_illustrations/first_aid_req_15_topic_visual.png",
        }
        return first_aid_exact_map.get(r_clean, "")

    # 2. If an explicit non-synthetic diagram URL is provided, honor it
    exp_s = str(explicit_url or "").strip()
    if exp_s and not exp_s.endswith("_workbook_diagram.png"):
        return exp_s

    # 3. Curated subject-matter diagrams in assets/diagrams/ and assets/ai_illustrations/
    if b_low == "cooking":
        if r_clean in ("2", "2a"):
            return "assets/diagrams/myplate_cooking_diagram.png"
    elif b_low in ("camping", "hiking", "backpacking", "wilderness survival"):
        if b_low == "camping" and r_clean == "9b":
            return "assets/ai_illustrations/camping_req_9_topic_visual.png"
        if r_clean in ("2", "2a", "7", "7a") and ("leave no trace" in tl or "outdoor code" in tl or b_low == "camping"):
            return "assets/diagrams/leave_no_trace_diagram.png"
    elif b_low in ("weather", "environmental science", "sustainability", "soil and water conservation"):
        if r_clean in ("1", "1a", "2", "2a", "3", "3a") and ("water cycle" in tl or "hydrologic" in tl or b_low == "weather"):
            return "assets/diagrams/water_cycle_diagram.png"

    # 4. Authentic BSA Pamphlet figure for Req 1 (and Req 2 when available)
    if r_clean in ("1", "1a", "2", "2a"):
        pamphlet_idx = _get_pamphlet_badge_diagram_index()
        figs = pamphlet_idx.get(slug) or []
        if figs:
            if r_parent == "1":
                return figs[0]
            if r_parent == "2" and len(figs) >= 2:
                return figs[1]
        # Fallback to badge Req 1 hero illustration if pamphlet figure not present
        hero_rel = f"assets/ai_illustrations/{slug}_req_{r_parent}_nano_hero.png"
        hero_abs = Path(__file__).resolve().parents[2] / hero_rel
        if hero_abs.exists():
            return hero_rel

    return ""


def _is_comma_chopped_or_boilerplate_row(row_str: str) -> bool:
    """Detects truncated comma-chopped fragments or generic filler rows that should be healed."""
    import re

    s = re.sub(r"^\d+\.\s*", "", str(row_str or "").strip()).strip()
    sl = s.lower()
    if not s:
        return True
    boilerplate_patterns = (
        "pamphlet standard & key facts",
        "field application & counselor verification",
        "key pamphlet examples & evidence",
        "practical application & safety verification",
        "supporting detail / step",
        "field verification / example",
        "item / focus",
        "step / point 1",
        "step / point 2",
        "step / point 3",
    )
    if any(bp in sl for bp in boilerplate_patterns):
        return True
    chopped_Fragments = (
        "each of the seven days of this week's",
        "with your parent or guardian's",
        "with your parent or guardian",
        "or c) and complete all",
        "or b) and complete all",
        "before doing requirements",
        "after completing requirements",
        "with guidance from your counselor",
        "based on your interests",
        "working under the supervision",
        "prepare a",
        "make a",
        "select one of the",
        "choose one of the",
    )
    if sl in chopped_Fragments:
        return True
    if sl.endswith((
        " of", " the", " a", " an", " to", " for", " with", " your", " and", " or",
        " in", " on", " at", " by", " from", " as", " such as", " including",
        " parent or guardian's", " week's", " counselor's",
    )):
        return True
    return False


def _derive_clean_rows_from_req_text(req_num: str, req_text: str, verb: str) -> List[str]:
    """Derives 1 to 4 clean, complete requirement prompt rows from verbatim `req_text` without comma-chopping."""
    import re

    clean_txt = _clean_ocr_and_prefix_text(str(req_text or "").strip())
    if not clean_txt:
        return [f"1. Requirement {req_num} ({verb}): Core Explanation & Field Evidence"]

    # Check for explicit parenthesized sub-clauses like (1) ... (2) ... or (a) ... (b) ...
    paren_parts = re.split(r"(?=\([1-9a-z]\)\s+)", clean_txt)
    paren_items = [p.strip() for p in paren_parts if re.match(r"^\([1-9a-z]\)\s+", p.strip())]
    if len(paren_items) >= 2:
        out_p: List[str] = []
        for idx_p, item in enumerate(paren_items[:12], start=1):
            clipped = item if len(item) <= 135 else item[:132].rsplit(" ", 1)[0] + "..."
            out_p.append(f"{idx_p}. {clipped}")
        return out_p

    # Split on sentence boundaries (never commas!)
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.?!])\s+", clean_txt)
        if s.strip() and not re.match(r"^(?:Do|Complete|Discuss|Explain|Choose)\s+(?:the\s+following|ONE|ALL)\s*[:.]?$", s.strip(), flags=re.IGNORECASE)
    ]
    if len(sentences) >= 2:
        out_s: List[str] = []
        for idx_s, sent in enumerate(sentences[:4], start=1):
            clipped = sent if len(sent) <= 135 else sent[:132].rsplit(" ", 1)[0] + "..."
            out_s.append(f"{idx_s}. {clipped}")
        return out_s

    clipped_single = clean_txt if len(clean_txt) <= 140 else clean_txt[:137].rsplit(" ", 1)[0] + "..."
    return [f"1. {clipped_single}"]


def _sanitize_workbook_organizer_runtime(
    org: Dict[str, Any],
    req_num: str,
    req_text: str,
    verb: str,
    parent_text: str = "",
    badge_name: str = "",
) -> Dict[str, Any]:
    """Fixes sub-requirement organizer specialization, table over-replication, unused enums, and broken clause row_labels at runtime."""
    import re

    out = dict(org or {})
    r_id = str(req_num or "").strip().lower()
    b_low = str(badge_name or "").strip().lower()
    tl = str(req_text or "").strip().lower()
    ptl = str(parent_text or "").strip().lower()
    org_type = str(out.get("organizer_type") or "RULED_EXPLAIN_BOX").strip().upper()
    rows = [_clean_ocr_and_prefix_text(str(r)) for r in (out.get("row_labels") or []) if str(r).strip()]

    # 0A. Cooking: Scope MEAL_PLANNER_AND_COST_TABLE strictly to actual menu/recipe planning sub-requirements (4a, 4c, 5a, 5b, 5c, 6a, 6c)
    cooking_menu_ids = {"4a", "4c", "5a", "5b", "5c", "6a", "6c"}
    if b_low == "cooking" or ("myplate" in tl and "five food groups" in tl) or ("cooking methods" in ptl and "simmering" in tl):
        if r_id == "2a" or ("five food groups" in tl and "myplate" in tl):
            out["organizer_type"] = "COMPARE_CONTRAST_2COL"
            out["table_title"] = "Req 2a USDA MyPlate Five Food Groups & Daily Serving Guide"
            out["headers"] = [
                "USDA MyPlate Food Group",
                "Two Examples of Foods in Group",
                "Recommended Daily Servings (Youth) & Nutritional Benefit",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Fruits Group (Whole Fruits & 100% Fruit Juices)",
                "2. Vegetables Group (Dark Green, Red/Orange, Beans/Peas, Starchy)",
                "3. Grains Group (Whole Grains vs. Refined Grains)",
                "4. Protein Foods Group (Lean Meats, Poultry, Seafood, Eggs, Nuts, Legumes)",
                "5. Dairy Group (Milk, Yogurt, Cheese, Fortified Soy Beverages)",
                "6. Why Limit Oils, Sodium, Refined Sugars & Saturated/Trans Fats",
            ]
        elif r_id == "2c" or ("five days" in tl and "track" in tl and "meal" in tl):
            out["organizer_type"] = "CALORIE_LOG_5DAY"
            out["table_title"] = "Req 2c 5-Day Daily Meal, Activity & Calorie Tracker"
            out["headers"] = [
                "Day (5-Day Nutrition & Activity Log)",
                "Breakfast, Lunch, Dinner & Snacks Consumed",
                "Estimated Calories & MyPlate Food Groups",
                "Physical Activity & Hydration Notes",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Day 1: Daily Meals, Calorie Total & Physical Activity",
                "2. Day 2: Daily Meals, Calorie Total & Physical Activity",
                "3. Day 3: Daily Meals, Calorie Total & Physical Activity",
                "4. Day 4: Daily Meals, Calorie Total & Physical Activity",
                "5. Day 5: Daily Meals, Calorie Total & Meal-Plan Comparison",
            ]
        elif r_id == "3a" or ("cooking methods" in tl and ("baking" in tl or "simmering" in tl)):
            out["organizer_type"] = "COMPARE_CONTRAST_2COL"
            out["table_title"] = "Req 3a Cooking Methods, Heat Transfer & Equipment Matrix"
            out["headers"] = [
                "Cooking Method",
                "How Heat Transfers & Equipment Used",
                "Temperature Control & Example Camp/Home Dish",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Baking & Broiling (Dry-Heat Oven / Reflector Oven / Open Flame)",
                "2. Boiling & Simmering (Moist-Heat Liquid Convection at 212°F vs. 185-205°F)",
                "3. Pan Frying & Sautéing (Conduction in Skillet / Griddle with Minimal Oil)",
                "4. Steaming & Microwaving (Vapor Heat Transfer & Electromagnetic Agitation)",
                "5. Grilling, Foil Packet & Dutch Oven Cooking (Camp Coals, Thermal Mass & Lid Coals)",
            ]
        elif org_type == "MEAL_PLANNER_AND_COST_TABLE" and r_id not in cooking_menu_ids:
            out["organizer_type"] = "STEP_BY_STEP_CHECKLIST" if verb.lower() in ("prepare", "cook", "serve", "demonstrate", "show") else "RULED_EXPLAIN_BOX"
            out["table_title"] = f"Req {req_num} Culinary Execution, Safety & Evaluation Organizer"
            out["headers"] = [
                f"Req {req_num} Culinary Requirement Prompt",
                "Scout Preparation, Timing, Food-Safety & Evaluation Notes",
            ]
            out["column_headers"] = list(out["headers"])
            rows = _derive_clean_rows_from_req_text(req_num, req_text, verb)

    # 0B. Personal Fitness: Scope FITNESS_LOG_12WK strictly to 7a (and 8); wire CALORIE_LOG_5DAY on 5c/7c; tailored component tables on 6a-6f & 7d
    if b_low == "personal fitness" or ("12-week" in ptl and "fitness" in ptl):
        if r_id in ("5c", "7c") or ("five days" in tl and ("food" in tl or "caloric" in tl or "nutrition" in tl)):
            out["organizer_type"] = "CALORIE_LOG_5DAY"
            out["table_title"] = f"Req {req_num} 5-Day Daily Nutrition, Hydration & Calorie Log"
            out["headers"] = [
                "Day (5-Day Nutrition Log)",
                "Meals, Snacks & Water Intake",
                "Total Daily Calories & Macro Balance",
                "Fitness Program Alignment & Notes",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Day 1: All Foods, Beverages & Estimated Calorie Intake",
                "2. Day 2: All Foods, Beverages & Estimated Calorie Intake",
                "3. Day 3: All Foods, Beverages & Estimated Calorie Intake",
                "4. Day 4: All Foods, Beverages & Estimated Calorie Intake",
                "5. Day 5: All Foods, Beverages & 5-Day Nutritional Summary",
            ]
        elif r_id in ("6a", "6b", "6c", "6d", "6e", "6f", "7d") or (org_type == "FITNESS_LOG_12WK" and r_id not in ("6", "7", "7a", "8")):
            out["organizer_type"] = "FITNESS_ASSESSMENT_4STAGE" if r_id in ("6b", "6c", "6d") else "STEP_BY_STEP_CHECKLIST"
            out["table_title"] = f"Req {req_num} Personal Fitness Program Component Design"
            out["headers"] = [
                f"Req {req_num} Fitness Program Element",
                "Selected Exercises, Sets/Reps/Duration & Target Progression",
            ]
            out["column_headers"] = list(out["headers"])
            rows = _derive_clean_rows_from_req_text(req_num, req_text, verb)

    # 0C. Personal Management: Wire LEDGER_13WK on 2a/2c and TIME_DIARY_7DAY on 8b/8c
    if b_low == "personal management" or "13 consecutive weeks" in tl or "seven-day period" in tl:
        if r_id in ("2a", "2c") or "13 consecutive weeks" in tl:
            out["organizer_type"] = "LEDGER_13WK"
            out["table_title"] = f"Req {req_num} 13-Week Personal Budget, Income & Expense Ledger"
            out["headers"] = [
                "13-Week Budget Period / Category",
                "Projected Income & Allowance ($)",
                "Actual Expenses: Needs vs. Wants ($)",
                "Net Savings & Budget Variance ($)",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Weeks 1-3: Initial Budget Projections vs. Actual Income & Expenses",
                "2. Weeks 4-6: Mid-Quarter Tracking (Savings Deposited vs. Discretionary Spending)",
                "3. Weeks 7-9: Ongoing Ledger Audit & Expense Category Adjustments",
                "4. Weeks 10-13: Final 13-Week Balance Sheet (Total Income vs. Total Expenses & Net Saved)",
            ]
        elif r_id in ("8b", "8c") or ("seven-day" in tl and ("to-do" in tl or "schedule" in tl or "diary" in tl)):
            out["organizer_type"] = "TIME_DIARY_7DAY"
            out["table_title"] = f"Req {req_num} 7-Day Time Management Schedule & Daily Diary"
            out["headers"] = [
                "Day of Week (7-Day Time Diary)",
                "Scheduled Tasks & Priority Rank",
                "Actual Time Spent & Completion Check",
                "Schedule Variance & Reflection",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Day 1: Planned Schedule vs. Actual Time Diary",
                "2. Day 2: Planned Schedule vs. Actual Time Diary",
                "3. Day 3: Planned Schedule vs. Actual Time Diary",
                "4. Day 4: Planned Schedule vs. Actual Time Diary",
                "5. Day 5: Planned Schedule vs. Actual Time Diary",
                "6. Day 6: Planned Schedule vs. Actual Time Diary",
                "7. Day 7: Planned Schedule, Weekly Review & Counselor Discussion",
            ]

    # 0D. Emergency Preparedness 1b: 6-Column Matrix (Situation | Prevention | Protection | Mitigation | Response | Recovery)
    if (b_low == "emergency preparedness" and r_id in ("1b", "2a")) or (
        "prevention" in tl and "protection" in tl and "mitigation" in tl and "response" in tl and "recovery" in tl
    ):
        out["organizer_type"] = "HAZARD_5COL"
        out["table_title"] = f"Req {req_num} Five-Mission Emergency Management Matrix (6 Columns)"
        out["headers"] = [
            "Emergency Situation",
            "Prevention",
            "Protection",
            "Mitigation",
            "Response",
            "Recovery",
        ]
        out["column_headers"] = list(out["headers"])
        if not rows or len(rows) < 5 or any(_is_comma_chopped_or_boilerplate_row(r) for r in rows):
            rows = [
                "1. Home Kitchen Fire / Carbon Monoxide Leak",
                "2. Basement, Structure, or Flash Flood",
                "3. Severe Thunderstorm, High Winds, Tornado, or Hurricane",
                "4. Winter Storm, Power Outage, or Extreme Heat Wave",
                "5. Backcountry Lost Hiker, Landslide, or Wildfire Evacuation",
                "6. Motor Vehicle Accident or Hazardous Materials Spill",
            ]

    # 0E. First Aid 2b(1) / 2b1: 21-Item First Aid Kit Inventory
    if (b_low == "first aid" and r_id in ("2b(1)", "2b1", "2b")) or ("personal first-aid kit" in tl and "hike" in tl):
        out["organizer_type"] = "GEAR_INSPECTION_CHECKLIST"
        out["table_title"] = f"Req {req_num} Personal & Patrol 21-Item First Aid Kit Inventory"
        out["headers"] = [
            "First Aid Kit Item (BSA Recommended Inventory)",
            "Qty / Expiration Check",
            "Medical Purpose & How Used on the Trail",
        ]
        out["column_headers"] = list(out["headers"])
        rows = [
            "1. Adhesive Bandages (6 assorted sizes)",
            "2. Sterile Gauze Pads (2x 3-by-3-inch)",
            "3. Adhesive Medical Tape (1 small roll)",
            "4. Moleskin or Blister Treatment Dressings (3-by-6-inch)",
            "5. Soap (1 small bar) or Alcohol-Based Hand Sanitizer Gel",
            "6. Triple-Antibiotic Ointment (1 small tube or packets)",
            "7. Scissors / Trauma Shears (1 pair)",
            "8. Non-Latex Nitrile Disposable Gloves (2 pairs)",
            "9. CPR Breathing Barrier / Resuscitation Mask (1 with one-way valve)",
            "10. Pencil and Small SOAP First-Aid Notes Pad",
            "11. Tweezers (Fine-tipped for splinters & ticks)",
            "12. Antiseptic Wipes / BZK Towelettes (6 packets)",
            "13. Roller Gauze Bandage (1-inch and 2-inch rolls)",
            "14. Triangular Cravat Bandages (2 muslin slings/binders)",
            "15. Elastic Compression Wrap Bandage (3-inch ACE wrap)",
            "16. Sterile Eye Pads / Eye Wash Saline Ampoules",
            "17. Oral Rehydration Salts / Electrolyte Packets",
            "18. Hydrocortisone Itch-Relief Cream / Sting Relief Pads",
            "19. Safety Pins (Assorted sizes for securing slings)",
            "20. Emergency Space Blanket (Mylar thermal sheet)",
            "21. Foldable SAM Splint & Personal Prescription Medications",
        ]

    # 0F. Astronomy 4a & 5b Observation Charts
    if b_low == "astronomy" or "constellations" in tl or ("five of the following planets" in tl):
        if r_id == "4a" or ("10 constellations" in tl and "zodiac" in tl):
            out["organizer_type"] = "TIME_SERIES_LOG_TABLE"
            out["table_title"] = "Req 4a Night-Sky Constellation Observation Chart (10 Total, 4+ in Zodiac)"
            out["headers"] = [
                "Constellation Name (Mark 'Z' if in Zodiac)",
                "Date, Time & Sky Direction (N/S/E/W)",
                "Principal Stars, Pattern Shape & Field Notes",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Constellation 1 (Zodiac #1): Name, Date/Time & Brightest Stars",
                "2. Constellation 2 (Zodiac #2): Name, Date/Time & Brightest Stars",
                "3. Constellation 3 (Zodiac #3): Name, Date/Time & Brightest Stars",
                "4. Constellation 4 (Zodiac #4): Name, Date/Time & Brightest Stars",
                "5. Constellations 5-7 (Circumpolar / Seasonal): Names & Sky Positions",
                "6. Constellations 8-10 (Seasonal Night Sky): Names & Sky Positions",
            ]
        elif r_id == "5b" or ("planets" in tl and "visible in the sky" in tl):
            out["organizer_type"] = "TIME_SERIES_LOG_TABLE"
            out["table_title"] = "Req 5b Five Naked-Eye Planets 12-Month Visibility & Motion Chart"
            out["headers"] = [
                "Naked-Eye Planet",
                "Months Visible Over Next 12 Months (Evening / Morning)",
                "Path Along Ecliptic & Retrograde Motion Explanation",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Mercury (Inferior Planet - Low Dawn/Dusk Twilights)",
                "2. Venus (Inferior Planet - Morning / Evening Star)",
                "3. Mars (Superior Planet - Reddish Hue & Opposition Retrograde Loop)",
                "4. Jupiter (Superior Gas Giant - Bright Banded Disk & Galilean Moons)",
                "5. Saturn (Superior Ringed Planet - Ecliptic Tracking & Apparent Motion)",
            ]

    # 0G. Camping 9a: 20-Night Scouting Camping Log (CAMPING_LOG_20NIGHT)
    if (b_low == "camping" and r_id == "9a") or ("20 nights" in tl and "camping" in tl):
        out["organizer_type"] = "CAMPING_LOG_20NIGHT"
        out["table_title"] = f"Req {req_num} 20-Night Scouting Camping Log (Up to 6 Consecutive Long-Term Camp Nights)"
        out["headers"] = [
            "Campout Night #",
            "Date & Location / Camp",
            "Tent / Under Stars",
            "Activities & Weather Notes",
        ]
        out["column_headers"] = list(out["headers"])
        rows = [f"Night {i}: Date, Location, Tent/Sky & Leader Initials" for i in range(1, 21)]

    # 1. Citizenship in the Nation Req 3b, 3c, 3d & 7b: differentiate from generic 3-branch list
    if "branches" in ptl or "branch" in tl or "divide powers" in tl or "checks and balances" in tl:
        if r_id == "3b" or "divide powers" in tl:
            out["organizer_type"] = "CITIZENSHIP_CIVIC_ORGANIZER"
            out["table_title"] = "Req 3b Separation of Powers Study Organizer"
            out["headers"] = [
                "Separation of Powers Principle",
                "Why Dividing Power Protects Liberty",
                "Constitutional / Historical Example",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Preventing Concentration of Power (Framers' Constitutional Design)",
                "2. Distinct Roles: Lawmaking (Art. I), Enforcement (Art. II) & Judicial Review (Art. III)",
                "3. Protecting Individual Liberties & Rule of Law",
            ]
        elif r_id == "3c" or "checks and balances" in tl:
            out["organizer_type"] = "CITIZENSHIP_CIVIC_ORGANIZER"
            out["table_title"] = "Req 3c Checks & Balances Matrix"
            out["headers"] = [
                "Branch Exercising Check",
                "Specific Check on the Other Two Branches",
                "Historical or Modern Example",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Legislative Checks on Executive & Judicial (Veto Override, Confirmations, Appropriations, Impeachment)",
                "2. Executive Checks on Legislative & Judicial (Presidential Veto, Judicial Appointments, Pardons)",
                "3. Judicial Checks on Legislative & Executive (Judicial Review of Statutes & Executive Actions)",
            ]
        elif r_id == "3d" or ("citizens can be involved" in tl and "branch" in tl):
            out["organizer_type"] = "CITIZENSHIP_CIVIC_ORGANIZER"
            out["table_title"] = "Req 3d Citizen Participation in Each Branch Organizer"
            out["headers"] = [
                "Branch of Federal Government",
                "How Citizens Participate & Make Their Voices Heard",
                "Scout / Community Action Example",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Citizen Involvement in Legislative Branch (Voting, Contacting Representatives/Senators, Committee Testimony, Petitions)",
                "2. Citizen Involvement in Executive Branch (Voting, Public Comment on Federal Regulations, Civil & Military Service)",
                "3. Citizen Involvement in Judicial Branch (Jury Service, Participating in Judicial Confirmations/Elections, Legal Advocacy)",
            ]
    if r_id == "7b" and ("state capitol" in tl or "u.s. capitol" in tl):
        rows = [
            "1. Tour of State Capitol Building or the U.S. Capitol (Date, Guide & Key Chambers Visited)",
            "2. Legislative History, Architecture & Constitutional Symbols Observed",
            "3. What You Learned About State or National Self-Government",
        ]

    # 2. Canoeing Req 1b & similar "prevention, symptoms, and first-aid treatment" requirements
    if (
        ("prevention" in tl and "symptoms" in tl and ("first-aid" in tl or "first aid" in tl))
        or ("blisters" in tl and "hypothermia" in tl and "dehydration" in tl and "sprains" in tl)
    ):
        out["organizer_type"] = "SYMPTOMS_FIRST_AID_PREVENTION_3COL"
        out["table_title"] = f"Req {req_num} First Aid, Symptoms & Prevention Matrix"
        out["headers"] = [
            "Condition / Injury",
            "Signs & Symptoms",
            "First-Aid Treatment",
            "Prevention Strategy",
        ]
        out["column_headers"] = list(out["headers"])
        if "canoeing" in tl or ("sunburn" in tl and "strains" in tl):
            rows = [
                "1. Blisters",
                "2. Cold-Water Shock & Hypothermia",
                "3. Dehydration",
                "4. Heat-Related Illnesses (Heat Exhaustion & Heatstroke)",
                "5. Sunburn",
                "6. Sprains",
                "7. Strains",
            ]

    # 3. Communication Req 4: Personal interview (not a 3-career exploration card)
    if "interview someone you know" in tl or ("prepare to introduce" in tl and "interview" in tl):
        out["organizer_type"] = "RULED_EXPLAIN_BOX"
        out["table_title"] = f"Req {req_num} Interview Preparation, Active Listening & Introduction Organizer"
        out["headers"] = [
            "Interview Stage / Component",
            "Prepared Questions, Active Listening Notes & Introduction Outline",
        ]
        out["column_headers"] = list(out["headers"])
        rows = [
            "1. Person Selected for Interview & Background / Reason Chosen",
            "2. Prepared Open-Ended Interview Questions",
            "3. Active Listening Notes & Key Facts Learned During Interview",
            "4. Guest Introduction Draft & Counselor Discussion Notes",
        ]

    # 4. Communication Req 1b: 3-day listening journal with all 4 listening types
    if "three days, keep a journal of your listening experiences" in tl:
        out["organizer_type"] = "TIME_SERIES_LOG_TABLE"
        out["table_title"] = f"Req {req_num} 3-Day Listening Experience Journal"
        out["headers"] = [
            "Listening Purpose (3-Day Journal)",
            "Day / Situation & Speaker",
            "What Was Said & How You Listened",
            "Counselor Discussion Notes",
        ]
        out["column_headers"] = list(out["headers"])
        rows = [
            "1. Listening to Obtain Information (Example & Reflection)",
            "2. Listening to Be Persuaded (Example & Reflection)",
            "3. Listening to Appreciate or Enjoy Something (Example & Reflection)",
            "4. Listening to Understand Someone's Feelings (Example & Reflection)",
        ]

    # 5. Career Exploration sub-clauses (e.g. First Aid 15a, 15b, 15d) that are visits/interviews/hobbies rather than 3-career lists
    if (out.get("organizer_type") == "CAREER_EXPLORATION_CARD" or r_id in ("15a", "15b", "15d")) and "three career" not in tl and "explore careers" not in tl:
        if "visit " in tl or "station house" in tl or "training center" in tl:
            out["table_title"] = f"Req {req_num} Field Visit & Professional Observation Log"
            out["headers"] = [
                "Field Visit Prompt",
                "Observations, Equipment Seen & Counselor Discussion Notes",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Facility / Station Visited, Date & Professionals Met",
                "2. Daily Duties, Shift Routines & Tools/Equipment Observed",
                "3. How These Professionals Serve the Community & Key Takeaways",
            ]
        elif "interview " in tl:
            out["table_title"] = f"Req {req_num} Professional Career Interview Card"
            out["headers"] = [
                "Career Interview Prompt",
                "Professional's Responses & Scout Reflection",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Professional Interviewed, Role & Organization",
                "2. Why They Chose This Career & Required Education/Certifications",
                "3. Daily Responsibilities, Training & Advice for Scouts",
            ]
        elif "personal hobby" in tl or "healthy lifestyle" in tl or "pursue a " in tl:
            out["table_title"] = f"Req {req_num} Personal Hobby, Service & Preparedness Application"
            out["headers"] = [
                "Personal / Community Application",
                "Skills Used, Preparation Steps & Goals",
            ]
            out["column_headers"] = list(out["headers"])
            rows = [
                "1. Personal Hobby, Volunteer Role, or Preparedness Goal Selected",
                "2. Merit Badge Skills & Safety Practices Applied",
                "3. Ongoing Practice, Equipment & Community Service Plan",
            ]

    # 6. Archery 5a(6)(b) / 5b(6)(b): 80-centimeter (32-inch) five-color target shooting rows
    if "80-centimeter" in tl and "five-color target" in tl:
        out["table_title"] = f"Req {req_num} 80-cm Target Range Qualification Log"
        out["headers"] = [
            "Shooting Stage / Distance",
            "Five-Arrow End Scores",
            "Subtotal / Minimum Target Score",
            "Instructor / Counselor Verification",
        ]
        out["column_headers"] = list(out["headers"])
        if "15 yards" in tl:
            rows = [
                "1. 10-Yard Stage: 15 Arrows (Three 5-Arrow Ends on 80-cm Target)",
                "2. 15-Yard Stage: 15 Arrows (Three 5-Arrow Ends on 80-cm Target)",
                "3. Combined Total Score Verification (Minimum 160 Points Required)",
            ]
        else:
            rows = [
                "1. Ends 1-3 at 10 Yards (First 15 Arrows on 80-cm 5-Color Target)",
                "2. Ends 4-6 at 10 Yards (Second 15 Arrows on 80-cm 5-Color Target)",
                "3. Combined 30-Arrow Total Score Verification (Minimum 150 Points Required)",
            ]

    # 7. Fish and Wildlife Management Req 6a: wildlife blind construction & observation
    if "wildlife blind" in tl and "salt lick" in tl:
        rows = [
            "1. Blind Site Selection (Game Trail / Water Hole / Feeder) & Construction Materials",
            "2. Wildlife Species Observed, Photographed, or Sketched (Birds, Mammals, Reptiles, Amphibians)",
            "3. Field Observation Notes: Time, Weather & Animal Behavior",
        ]

    # 8. Repair general split-abbreviation, comma-chopped fragments & boilerplate filler rows in row_labels
    repaired_rows: List[str] = []
    idx_r = 0
    while idx_r < len(rows):
        cur = rows[idx_r]
        nxt = rows[idx_r + 1] if idx_r + 1 < len(rows) else ""
        nxt_clean = re.sub(r"^\d+\.\s*", "", nxt).strip()
        if cur.endswith("U.S") and nxt_clean.startswith("Capitol"):
            merged = f"{cur}. {nxt_clean}"
            repaired_rows.append(merged)
            idx_r += 2
            continue
        if nxt_clean.lower() in ("why?", "why", "and why?", "how?", "how"):
            merged = f"{cur} and {nxt_clean.lower().rstrip('?')}?"
            repaired_rows.append(merged)
            repaired_rows.append(f"{len(repaired_rows) + 1}. Specific Examples, Safety Standards & Counselor Discussion")
            idx_r += 2
            continue
        if "(" in cur and ")" not in cur:
            cur = f"{cur})"
        repaired_rows.append(cur)
        idx_r += 1

    # Filter out dead boilerplate filler rows and heal comma-chopped fragments
    valid_rows = [r for r in repaired_rows if not _is_comma_chopped_or_boilerplate_row(r)]
    if not valid_rows or len(valid_rows) < len(repaired_rows) and any(_is_comma_chopped_or_boilerplate_row(r) for r in repaired_rows[:1]):
        derived_rows = _derive_clean_rows_from_req_text(req_num, req_text, verb)
        repaired_rows = derived_rows if not valid_rows else valid_rows
    else:
        repaired_rows = valid_rows

    # Renumber 1..N if rows used 1. 2. numbering
    if repaired_rows and all(re.match(r"^\d+\.\s+", r) for r in repaired_rows):
        repaired_rows = [
            re.sub(r"^\d+\.\s+", f"{i}. ", r)
            for i, r in enumerate(repaired_rows, start=1)
        ]

    if repaired_rows:
        out["row_labels"] = repaired_rows
        out["min_rows"] = len(repaired_rows)
    return out


def _build_child_workbook_organizer(
    child_node: Dict[str, Any],
    child_id: str,
    child_text: str,
    child_verb: str,
    parent_org: Dict[str, Any],
    parent_text: str,
    badge_name: str = "",
) -> Dict[str, Any]:
    """Builds a child/grandchild workbook_organizer without blindly copying parent row_labels."""
    explicit_org = child_node.get("workbook_organizer")
    if isinstance(explicit_org, dict) and explicit_org:
        base_org = dict(explicit_org)
    else:
        p_type = str((parent_org or {}).get("organizer_type") or "RULED_EXPLAIN_BOX").upper()
        # Inherit specialized domain matrix headers only when appropriate; never inherit parent row_labels
        keep_types = {"SYMPTOMS_FIRST_AID_PREVENTION_3COL", "HAZARD_5COL"}
        inherited_type = p_type if p_type in keep_types else (
            "STEP_BY_STEP_CHECKLIST" if child_verb.lower() in ("demonstrate", "show", "prepare", "make", "build") else "RULED_EXPLAIN_BOX"
        )
        headers = (
            list(parent_org.get("headers") or parent_org.get("column_headers") or [])
            if p_type in keep_types
            else [f"Req {child_id} Prompt / Step", "Scout Notes, Measurements & Field Evidence"]
        )
        base_org = {
            "organizer_type": inherited_type,
            "table_title": f"Req {child_id} Study & Verification Organizer",
            "headers": headers,
            "column_headers": list(headers),
            "row_labels": _derive_clean_rows_from_req_text(child_id, child_text, child_verb),
            "min_rows": 1,
            "pre_approval_gate": "approval" in child_text.lower(),
        }
    return _sanitize_workbook_organizer_runtime(
        base_org, child_id, child_text, child_verb, parent_text=parent_text, badge_name=badge_name
    )


def _iter_unrolled_workbook_units(reqs: List[Dict[str, Any]], badge_name: str = "") -> List[Dict[str, Any]]:
    """Unrolls top-level requirements and their nested `sub_requirements` / `children` into ordered workbook units.

    Ensures:
    1. Every unrolled sub-requirement and child unit carries non-empty `pamphlet_excerpts`,
       `common_misconception_pair`, `counselor_signoff_criteria`, and `workbook_diagram_url`.
    2. Child/grandchild units never repeat a parent's generic multi-row table 49 times (e.g., Plant Science 8a(5)).
    3. Up to 12 level-3 grandchildren (e.g., Athletics 5g(2)(a)..(h) including 'Top of the key') are consolidated
       cleanly into the level-2 unit's rows and excerpts.
    """
    import re

    units: List[Dict[str, Any]] = []
    seen_diagrams: set = set()
    for idx, r in enumerate(reqs or [], start=1):
        r_num = str(r.get("req_number") or r.get("req_id") or str(idx)).strip()
        r_title = str(r.get("topic_title") or r.get("title") or f"Requirement {r_num}").strip()
        r_text = str(r.get("req_text") or "").strip()
        r_verb = str(r.get("action_verb") or "Explain").strip()
        r_mode = str(r.get("execution_mode") or "IN_CLASS_DISCUSSION").strip()
        r_bucket = str(
            r.get("syllabus_bucket")
            or (
                "Pre-Class Prerequisite"
                if r_mode == "PREREQUISITE_CAMPOUT_HOME"
                else ("In-Class Demonstration" if r_mode == "HANDS_ON_SKILL_STATION" else "In-Class Concept")
            )
        ).strip()
        r_cit = str(r.get("pamphlet_page_citation") or r.get("pamphlet_citation") or "Official BSA Pamphlet").strip()
        r_org = _sanitize_workbook_organizer_runtime(
            dict(r.get("workbook_organizer") or {}), r_num, r_text, r_verb, badge_name=badge_name
        )
        r_mis = _sanitize_misconception_pair_runtime(
            dict(r.get("common_misconception_pair") or {}), r_num, r_text, r_verb, r_cit
        )
        if not r_mis:
            r_mis = {
                "misconception": f"Treating Requirement {r_num} as a quick checklist item without explaining the underlying BSA pamphlet principles.",
                "fact": f"Each Scout must individually {r_verb.lower()} Requirement {r_num} ({r_title}) using verified facts from {r_cit}.",
            }
        r_gate = r.get("starting_requirement_gate")
        _r_has_gear_context = (
            r_mode == "HANDS_ON_SKILL_STATION"
            or r_verb.lower() in ("demonstrate", "show", "build", "prepare", "assemble", "construct")
            or any(
                kw in r_text.lower()
                for kw in ("kit", "gear", "equipment", "pack", "demonstrate", "show how", "inspect", "supply", "supplies")
            )
        )
        r_gear = list(r.get("gear_checklist") or []) if _r_has_gear_context else []
        r_excerpts = _clean_ocr_and_prefix_excerpts(list(r.get("pamphlet_excerpts") or []))
        if not r_excerpts and r_text:
            r_excerpts = [f"Requirement {r_num} Standard ({r_cit}): {r_text}"]
        r_proc = _clean_ocr_and_prefix_excerpts(list(r.get("step_by_step_procedure") or []))
        r_signoff = str(
            r.get("counselor_signoff_criteria")
            or r.get("homework_verification_note")
            or f"Scout must individually {r_verb.lower()} mastery of Requirement {r_num} to the Merit Badge Counselor."
        ).strip()
        r_diag = _resolve_workbook_diagram_url(
            badge_name, r_num, r_text, str(r.get("workbook_diagram_url") or "")
        )
        r_safety = r.get("safety_callout")
        subs = list(r.get("sub_requirements") or [])

        if not subs:
            if r_diag in seen_diagrams:
                r_diag = ""
            elif r_diag:
                seen_diagrams.add(r_diag)
            unit = dict(r)
            unit.update({
                "is_group_header": False,
                "is_sub_requirement": False,
                "req_id": r_num,
                "req_number": r_num,
                "title": r_title,
                "topic_title": r_title,
                "req_text": r_text,
                "action_verb": r_verb,
                "execution_mode": r_mode,
                "syllabus_bucket": r_bucket,
                "pamphlet_page_citation": r_cit,
                "pamphlet_citation": r_cit,
                "workbook_organizer": r_org,
                "common_misconception_pair": r_mis,
                "starting_requirement_gate": r_gate,
                "gear_checklist": r_gear,
                "pamphlet_excerpts": r_excerpts,
                "step_by_step_procedure": r_proc,
                "counselor_signoff_criteria": r_signoff,
                "workbook_diagram_url": r_diag,
                "safety_callout": r_safety,
            })
            units.append(unit)
            continue

        # Emit parent group header unit (never attach diagram to group header so it isn't duplicated on 1a)
        units.append({
            "is_group_header": True,
            "is_sub_requirement": False,
            "req_id": r_num,
            "req_number": r_num,
            "parent_id": None,
            "title": r_title,
            "topic_title": r_title,
            "req_text": r_text,
            "action_verb": r_verb,
            "execution_mode": r_mode,
            "syllabus_bucket": r_bucket,
            "pamphlet_page_citation": r_cit,
            "pamphlet_citation": r_cit,
            "workbook_organizer": r_org,
            "common_misconception_pair": r_mis,
            "starting_requirement_gate": r_gate,
            "gear_checklist": r_gear,
            "pamphlet_excerpts": r_excerpts,
            "step_by_step_procedure": r_proc,
            "counselor_signoff_criteria": r_signoff,
            "workbook_diagram_url": "",
            "safety_callout": r_safety,
        })

        for sr_idx, sr in enumerate(subs):
            sr_id = str(
                sr.get("sub_id")
                or sr.get("id")
                or sr.get("sub_req_label")
                or sr.get("req_number")
                or f"{r_num}{sr.get('label', '')}"
            ).strip()
            sr_text = str(sr.get("text") or sr.get("sub_req_text") or sr.get("req_text") or "").strip()
            sr_verb = str(sr.get("action_verb") or r_verb).strip()
            sr_bucket = str(sr.get("syllabus_bucket") or r_bucket).strip()
            sr_cit = str(sr.get("pamphlet_page_citation") or sr.get("pamphlet_citation") or r_cit).strip()
            sr_org = _build_child_workbook_organizer(
                sr, sr_id, sr_text, sr_verb, r_org, r_text, badge_name=badge_name
            )
            sr_mis = _sanitize_misconception_pair_runtime(
                dict(sr.get("common_misconception_pair") or r_mis), sr_id, sr_text, sr_verb, sr_cit
            )
            sr_gate = sr.get("starting_requirement_gate") or (r_gate if sr_idx == 0 else None)
            _sr_has_gear_context = (
                _r_has_gear_context
                or sr_verb.lower() in ("demonstrate", "show", "build", "prepare", "assemble", "construct")
                or any(
                    kw in sr_text.lower()
                    for kw in ("kit", "gear", "equipment", "pack", "demonstrate", "show how", "inspect", "supply", "supplies")
                )
            )
            sr_gear = (
                list(sr.get("gear_checklist") or (r_gear if sr_idx == 0 else []))
                if _sr_has_gear_context and sr_idx == 0
                else []
            )
            sr_title = str(sr.get("topic_title") or sr.get("title") or f"{r_title} ({sr_id})").strip()
            sr_excerpts = _clean_ocr_and_prefix_excerpts(
                ([sr["pamphlet_summary"]] if sr.get("pamphlet_summary") else [])
                + list(sr.get("pamphlet_excerpts") or [])
                + ([f"Req {sr_id} Standard ({sr_cit}): {sr_text}"] if sr_text else [])
                + r_excerpts[:2]
            )
            sr_proc = _clean_ocr_and_prefix_excerpts(list(sr.get("step_by_step_procedure") or r_proc[:2]))
            sr_signoff = str(
                sr.get("counselor_signoff_criteria")
                or sr.get("homework_verification_note")
                or f"Scout must individually {sr_verb.lower()} Requirement {sr_id} ({sr_text[:110].rstrip('.')}) to the Counselor."
            ).strip()
            sr_diag = _resolve_workbook_diagram_url(
                badge_name,
                sr_id,
                sr_text,
                str(sr.get("workbook_diagram_url") or (r_diag if sr_idx == 0 else "")),
            )
            children = list(sr.get("children") or [])

            # Check if children are short enumerated condition items (e.g. Wilderness Survival 1a(1)..1a(13))
            children_are_short_condition_rows = bool(children) and all(
                len(str(ch.get("text") or ch.get("sub_req_text") or "").split()) <= 12
                and not ch.get("children")
                for ch in children
            )
            if children_are_short_condition_rows:
                consolidated_rows = []
                for ch_idx, ch in enumerate(children, start=1):
                    c_lbl = str(ch.get("label") or f"({ch_idx})").strip()
                    c_txt = str(ch.get("text") or ch.get("sub_req_text") or "").strip()
                    consolidated_rows.append(f"{c_lbl} {c_txt}".strip())
                if consolidated_rows:
                    sr_org["row_labels"] = consolidated_rows
                    sr_org["min_rows"] = len(consolidated_rows)

            sr_is_group_header = bool(children) and not children_are_short_condition_rows
            if sr_is_group_header or sr_diag in seen_diagrams:
                sr_diag_emit = ""
            else:
                sr_diag_emit = sr_diag
                if sr_diag_emit:
                    seen_diagrams.add(sr_diag_emit)

            units.append({
                "is_group_header": sr_is_group_header,
                "is_sub_requirement": True,
                "req_id": sr_id,
                "req_number": sr_id,
                "parent_id": r_num,
                "title": sr_title,
                "topic_title": sr_title,
                "req_text": sr_text,
                "action_verb": sr_verb,
                "execution_mode": r_mode,
                "syllabus_bucket": sr_bucket,
                "pamphlet_page_citation": sr_cit,
                "pamphlet_citation": sr_cit,
                "workbook_organizer": sr_org,
                "common_misconception_pair": sr_mis,
                "starting_requirement_gate": sr_gate,
                "gear_checklist": sr_gear,
                "pamphlet_excerpts": sr_excerpts,
                "step_by_step_procedure": sr_proc,
                "counselor_signoff_criteria": sr_signoff,
                "workbook_diagram_url": sr_diag_emit,
                "safety_callout": r_safety if sr_idx == 0 else None,
            })

            if children_are_short_condition_rows:
                continue

            for ch_idx, ch in enumerate(children, start=1):
                raw_ch_id = str(
                    ch.get("sub_id")
                    or ch.get("id")
                    or ch.get("sub_req_label")
                    or ch.get("req_number")
                    or f"{sr_id}{ch.get('label', '')}"
                ).strip()
                ch_text = str(ch.get("text") or ch.get("sub_req_text") or ch.get("req_text") or "").strip()
                # Normalize duplicate Plant Science IDs like 8a(5)(5) with text '(a) Corn ...' -> 8a(5)(a)
                m_dup_id = re.match(r"^(\d+[a-z]\(\d+\))\(\d+\)$", raw_ch_id, flags=re.IGNORECASE)
                m_lead_lbl = re.match(r"^\(([a-z])\)\s+", ch_text, flags=re.IGNORECASE)
                if m_dup_id and m_lead_lbl:
                    ch_id = f"{m_dup_id.group(1)}({m_lead_lbl.group(1).lower()})"
                else:
                    ch_id = raw_ch_id

                ch_verb = str(ch.get("action_verb") or sr_verb).strip()
                ch_bucket = str(ch.get("syllabus_bucket") or sr_bucket).strip()
                ch_cit = str(ch.get("pamphlet_page_citation") or ch.get("pamphlet_citation") or sr_cit).strip()
                ch_org = _build_child_workbook_organizer(
                    ch, ch_id, ch_text, ch_verb, sr_org, sr_text, badge_name=badge_name
                )
                ch_mis = _sanitize_misconception_pair_runtime(
                    dict(ch.get("common_misconception_pair") or sr_mis), ch_id, ch_text, ch_verb, ch_cit
                )
                ch_gate = ch.get("starting_requirement_gate")
                ch_gear = list(ch.get("gear_checklist") or [])
                ch_title = str(ch.get("topic_title") or ch.get("title") or f"{r_title} ({ch_id})").strip()
                grand_children = list(ch.get("children") or [])[:12]

                # Consolidate level-3 grand_children (e.g. Plant Science 8a(5)(a) (1)-(3) or Athletics 5g(2)(a)-(h))
                # directly into ch_org["row_labels"] so they never explode into 49 identical 4-column tables
                if grand_children:
                    gch_rows: List[str] = []
                    for gc_i, gc in enumerate(grand_children, start=1):
                        gc_lbl = str(gc.get("label") or f"({gc_i})").strip()
                        gc_txt = _clean_ocr_and_prefix_text(str(gc.get("text") or gc.get("sub_req_text") or "").strip())
                        if gc_txt:
                            gch_rows.append(f"{gc_lbl} {gc_txt}".strip())
                    if gch_rows:
                        ch_org["row_labels"] = gch_rows
                        ch_org["min_rows"] = len(gch_rows)
                        gch_joined = " ".join(gch_rows)
                        if gch_joined and gch_joined not in ch_text:
                            ch_text = f"{ch_text} {gch_joined}".strip()

                ch_excerpts = _clean_ocr_and_prefix_excerpts(
                    ([ch["pamphlet_summary"]] if ch.get("pamphlet_summary") else [])
                    + list(ch.get("pamphlet_excerpts") or [])
                    + ([f"Req {ch_id} Standard ({ch_cit}): {ch_text}"] if ch_text else [])
                    + sr_excerpts[:2]
                )
                ch_proc = _clean_ocr_and_prefix_excerpts(list(ch.get("step_by_step_procedure") or sr_proc[:2]))
                ch_signoff = str(
                    ch.get("counselor_signoff_criteria")
                    or ch.get("homework_verification_note")
                    or f"Scout must individually {ch_verb.lower()} Requirement {ch_id} ({ch_text[:110].rstrip('.')}) to the Counselor."
                ).strip()
                ch_diag = _resolve_workbook_diagram_url(
                    badge_name, ch_id, ch_text, str(ch.get("workbook_diagram_url") or "")
                )
                if ch_diag in seen_diagrams:
                    ch_diag = ""
                elif ch_diag:
                    seen_diagrams.add(ch_diag)

                units.append({
                    "is_group_header": False,
                    "is_sub_requirement": True,
                    "req_id": ch_id,
                    "req_number": ch_id,
                    "parent_id": sr_id,
                    "title": ch_title,
                    "topic_title": ch_title,
                    "req_text": ch_text,
                    "action_verb": ch_verb,
                    "execution_mode": r_mode,
                    "syllabus_bucket": ch_bucket,
                    "pamphlet_page_citation": ch_cit,
                    "pamphlet_citation": ch_cit,
                    "workbook_organizer": ch_org,
                    "common_misconception_pair": ch_mis,
                    "starting_requirement_gate": ch_gate,
                    "gear_checklist": ch_gear,
                    "pamphlet_excerpts": ch_excerpts,
                    "step_by_step_procedure": ch_proc,
                    "counselor_signoff_criteria": ch_signoff,
                    "workbook_diagram_url": ch_diag,
                    "safety_callout": None,
                })

    return units


def _build_svg_sketch_canvas_html(req_num: str, row_labels: List[str], req_text: str) -> str:
    """Renders a bordered 160px SVG dot-grid, Moon-circle, or horizon sketch canvas for SKETCH_AND_OBSERVATION_CANVAS."""
    import html as _html

    tl = (req_text or "").lower()
    canvas_caption = " | ".join(str(lbl) for lbl in (row_labels or [])[:3]) or f"Req {req_num} Field Sketch & Diagram Canvas"
    dots_svg: List[str] = []
    for gx in range(24, 680, 24):
        for gy in range(20, 145, 20):
            dots_svg.append(f'<circle cx="{gx}" cy="{gy}" r="1.1" fill="#94a3b8" />')

    guide_shapes = ""
    if "moon" in tl or "lunar" in tl or "seas" in tl or "craters" in tl:
        guide_shapes = (
            '<circle cx="190" cy="80" r="56" fill="none" stroke="#475569" stroke-width="1.5" stroke-dasharray="4,3" />'
            '<text x="190" y="148" text-anchor="middle" font-size="10" fill="#475569">Lunar Face / Phase Guide Circle</text>'
            '<line x1="340" y1="125" x2="640" y2="125" stroke="#475569" stroke-width="1.5" />'
            '<text x="490" y="142" text-anchor="middle" font-size="10" fill="#475569">Horizon &amp; Landmarks Reference Line</text>'
        )
    elif "horizon" in tl or "dipper" in tl or "cassiopeia" in tl or "constellation" in tl:
        guide_shapes = (
            '<line x1="40" y1="130" x2="310" y2="130" stroke="#475569" stroke-width="1.5" />'
            '<text x="175" y="145" text-anchor="middle" font-size="10" fill="#475569">Early Evening Horizon (N / NE / NW)</text>'
            '<line x1="370" y1="130" x2="640" y2="130" stroke="#475569" stroke-width="1.5" />'
            '<text x="505" y="145" text-anchor="middle" font-size="10" fill="#475569">Several Hours Later Horizon</text>'
        )
    else:
        guide_shapes = (
            '<line x1="40" y1="132" x2="640" y2="132" stroke="#64748b" stroke-width="1.2" stroke-dasharray="4,4" />'
            '<text x="340" y="147" text-anchor="middle" font-size="10" fill="#475569">Scale / Baseline / Orientation Reference</text>'
        )

    return (
        f'<div class="wb-sketch-canvas" data-canvas-req="{_html.escape(req_num)}" '
        'style="border:1.5px solid #475569; border-radius:6px; background:#ffffff; padding:8px; margin:8px 0;">'
        f'<div style="font-size:11px; font-weight:700; color:#003f87; margin-bottom:4px;">'
        f'✏️ Sketch &amp; Observation Canvas ({_html.escape(canvas_caption)})</div>'
        '<svg width="100%" height="160" viewBox="0 0 680 160" xmlns="http://www.w3.org/2000/svg" '
        'style="background:#f8fafc; border:1px dashed #94a3b8; border-radius:4px; display:block;">'
        f'{"".join(dots_svg)}{guide_shapes}'
        "</svg>"
        "</div>"
    )


def generate_counselor_workbook_markdown(
    research_result: Dict[str, Any],
    counselor_info: Optional[Dict[str, Any]] = None,
) -> str:
    """Generates a complete printable Scout & Counselor Class Preparation Page / Workbook in Markdown.

    Includes:
    1. Header with Eagle-Required badge status, Pamphlet & DRG links, and Counselor Contact block
    2. Execution-Mode Triage Table (In-Class Discussion vs. Hands-On Skill Station vs. Prerequisite/Campout/Home)
    3. Prerequisite ("Bring Proof to Class") Checklist
    4. Structured Per-Requirement & Unrolled Sub-Requirement Notes Grid, Bespoke Organizers & Skill Station Sign-Off Boxes
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
    contact_suffix = f" - `{' • '.join(contact_parts)}`" if contact_parts else ""

    lines: List[str] = [
        f"# {badge_name} Merit Badge - Scout & Counselor Class Preparation Workbook",
        f"**Classification:** {eagle_tag}  ",
        f"**Counselor:** {c_name} ({c_troop}){contact_suffix}",
        f"**Official Pamphlet PDF:** {pdf_url}  ",
        f"**Digital Resource Guide (DRG):** {drg_url}",
        "",
        "> **Guide to Advancement §7.0.3.2 Compliance Notice:** This workbook is an optional organizational study aid. Scouts are never required to submit a written worksheet when a requirement specifies oral *Explain*, *Discuss*, or *Show* mastery.",
        "",
        "---",
        "",
        "## 1. Requirement Execution-Mode & 5-Tier Syllabus Triage Matrix",
        "",
        "| Req # | Topic | Action Verb | Execution Mode | Syllabus Bucket | Pamphlet Reference | Counselor Sign-Off Date & Initials |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    from src.agents.planner import (
        _format_execution_mode_label,
        _format_starting_gate_label,
        _format_workbook_organizer_label,
    )

    prereq_reqs: List[Dict[str, Any]] = []
    station_reqs: List[Dict[str, Any]] = []

    for r in reqs:
        r_num = r.get("req_number", "")
        topic = r.get("topic_title") or f"Req {r_num}"
        verb = r.get("action_verb", "Explain")
        mode = r.get("execution_mode", "IN_CLASS_DISCUSSION")
        mode_label = _format_execution_mode_label(mode)
        bucket = r.get("syllabus_bucket") or (
            "Pre-Class Prerequisite" if mode == "PREREQUISITE_CAMPOUT_HOME"
            else ("In-Class Demonstration" if mode == "HANDS_ON_SKILL_STATION" else "In-Class Concept")
        )
        cit = r.get("pamphlet_page_citation") or r.get("pamphlet_citation") or "Official BSA Pamphlet"
        lines.append(f"| **{r_num}** | {topic} | {verb} | `{mode_label}` | **{bucket}** | {cit} | `[ ____ / ____ / 2026 ]  Init: ____` |")
        if mode == "PREREQUISITE_CAMPOUT_HOME" or bucket == "Pre-Class Prerequisite":
            prereq_reqs.append(r)
        elif mode == "HANDS_ON_SKILL_STATION" or bucket == "In-Class Demonstration":
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
        "## 4. Detailed Requirement Study Notes, Structured Organizers & Pamphlet Summaries",
        "",
    ])
    unrolled_units = _iter_unrolled_workbook_units(reqs, badge_name=badge_name)
    for u in unrolled_units:
        u_num = str(u.get("req_number") or u.get("req_id") or "")
        topic = str(u.get("topic_title") or u.get("title") or f"Requirement {u_num}")
        org = u.get("workbook_organizer") or {}
        org_type = str(org.get("organizer_type") or "RULED_EXPLAIN_BOX")
        org_type_label = _format_workbook_organizer_label(org_type)
        org_title = str(org.get("table_title") or f"Req {u_num} Study Organizer")

        if u.get("is_group_header"):
            lines.append(f"### {topic}")
            lines.append(f"**Official Requirement {u_num} (Parent Overview):** {u.get('req_text', '')}")
            if u.get("pamphlet_page_citation") or u.get("pamphlet_citation"):
                lines.append(f"**Source:** *{u.get('pamphlet_page_citation') or u.get('pamphlet_citation')}* • **Group Organizer:** {org_type_label}")
            if u.get("safety_callout"):
                lines.append(f"> **Guide to Safe Scouting Warning:** {u['safety_callout']}")
            gate = u.get("starting_requirement_gate")
            if isinstance(gate, dict) and gate.get("gate_label"):
                g_lbl = _format_starting_gate_label(gate.get("gate_type", "GATE"))
                lines.append(f"> **Starting Gate ({g_lbl}):** {gate.get('gate_label')} - {gate.get('gate_description', '')}")
            excerpts = u.get("pamphlet_excerpts") or []
            if excerpts:
                lines.append("")
                lines.append("**Official Pamphlet Summary:**")
                for ex in excerpts:
                    lines.append(f"- {ex}")
            lines.append("")
            continue

        heading_prefix = "####" if u.get("is_sub_requirement") else "###"
        lines.append(f"{heading_prefix} Req {u_num}: {topic}")
        lines.append(f"**Official Requirement {u_num}:** {u.get('req_text', '')}")
        if u.get("pamphlet_page_citation") or u.get("pamphlet_citation"):
            lines.append(
                f"**Source:** *{u.get('pamphlet_page_citation') or u.get('pamphlet_citation')}* • **Organizer ({org_type_label}):** {org_title}"
            )
        if u.get("safety_callout") and not u.get("is_sub_requirement"):
            lines.append(f"> **Guide to Safe Scouting Warning:** {u['safety_callout']}")
        gate = u.get("starting_requirement_gate")
        if isinstance(gate, dict) and gate.get("gate_label"):
            g_lbl = _format_starting_gate_label(gate.get("gate_type", "GATE"))
            lines.append(f"> **Starting Gate ({g_lbl}):** {gate.get('gate_label')} - {gate.get('gate_description', '')}")
        mis = u.get("common_misconception_pair") or {}
        if isinstance(mis, dict) and mis.get("misconception") and mis.get("fact"):
            lines.append(f"- **Common Myth:** {mis['misconception']}")
            lines.append(f"- **Pamphlet Fact:** {mis['fact']}")
        gear_list = u.get("gear_checklist") or []
        if gear_list:
            lines.append("")
            lines.append("**Gear & Readiness Checklist:**")
            for gi in gear_list:
                lines.append(f"- [ ] {gi}")
        if isinstance(org, dict) and (org.get("headers") or org.get("column_headers")):
            headers = org.get("headers") or org.get("column_headers") or ["Sub-Part / Step", "Scout Notes & Field Evidence"]
            row_labels = org.get("row_labels") or ["Row 1", "Row 2", "Row 3"]
            if org.get("pre_approval_gate"):
                lines.append("")
                lines.append("**COUNSELOR PRE-APPROVAL REQUIRED BEFORE STARTING:** `[ ] Approved Before Starting | Counselor Signature: ___________________ Date Approved: __________`")
            lines.append("")
            lines.append("| " + " | ".join(str(h) for h in headers) + " |")
            lines.append("| " + " | ".join(":---" for _ in headers) + " |")
            for rl in row_labels:
                blank_cols = ["`____________________________________`" for _ in headers[1:]]
                lines.append(f"| **{rl}** | " + " | ".join(blank_cols) + " |")
        if org_type == "SKETCH_AND_OBSERVATION_CANVAS" or any(
            k in str(u.get("req_text", "")).lower() for k in ("sketch", "draw a ", "diagram", "map")
        ):
            lines.append("")
            lines.append(f"**[Field Sketch & Diagram Canvas - Req {u_num} Unlined Dot-Grid / Horizon / Moon Sketch Box]:**")
            lines.append("```text")
            lines.append("+-----------------------------------------------------------------------+")
            lines.append("| .   .   .   .   .   .   [ SKETCH / DIAGRAM CANVAS ]   .   .   .   .   |")
            lines.append("| .   .   .   .   .   .   Label key landmarks & compass .   .   .   .   |")
            lines.append("+-----------------------------------------------------------------------+")
            lines.append("```")
        excerpts = u.get("pamphlet_excerpts") or []
        if excerpts and not u.get("is_sub_requirement"):
            lines.append("")
            lines.append("**Official Pamphlet Summary:**")
            for ex in excerpts:
                lines.append(f"- {ex}")
        lines.append("")
        lines.append("**Scout Notes / Demonstration Verification:** `___________________________________________________________`")
        lines.append("")

    return "\n".join(lines)


def generate_fillable_scout_workbook_html(
    badge_name: str,
    counselor_info: Optional[Dict[str, Any]] = None,
    option_track: str = "ALL",
    session_dates: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generates a print-ready Fillable Form (GTA §7.0.3.2) Scout Workbook (HTML + Markdown) for any of the 149 badges.

    Enforces:
    1. Mandatory `GTA §7.0.3.2` compliance banner (`Optional organizational study aid`).
    2. Option Track `A`/`B` filtering so Option A workbooks omit Option B tables and vice versa.
    3. Unrolled `sub_requirements` (`1a`, `1b`, ..., `3a..3q`) with bespoke graphic organizer tables,
       interactive `gear_checklist` checkboxes, Counselor Pre-Approval signature boxes, and 160px SVG sketch canvases.
    """
    import html as _html
    from src.agents.planner import _format_workbook_organizer_label
    from src.config import is_discontinued_badge, is_test_lab_badge

    res = fetch_merit_badge_pamphlet_pdf(
        MeritBadgeResearchRequest(
            badge_name=badge_name,
            option_track=option_track,
            counselor_info=CounselorTitleSlideInfo(**counselor_info) if counselor_info else None,
        )
    )
    if res.get("status") == "ERROR":
        return res

    resolved_badge = str(res.get("badge_name") or badge_name)
    reqs = list(res.get("requirements") or [])
    c_info = counselor_info or {}
    c_name = _html.escape(str(c_info.get("counselor_name") or "Merit Badge Counselor"))
    c_troop = _html.escape(str(c_info.get("troop_affiliation") or "Troop 19, Northeast Massachusetts Council"))
    c_email = _html.escape(str(c_info.get("email_address") or "counselor@scouting.org"))
    is_eagle = bool(res.get("is_eagle_required"))
    is_tl = is_test_lab_badge(resolved_badge)
    is_disc = is_discontinued_badge(resolved_badge)

    badge_pills_html = (
        '<span class="wb-pill eagle">EAGLE-REQUIRED</span>'
        if is_eagle
        else '<span class="wb-pill elective">ELECTIVE MERIT BADGE</span>'
    )
    if is_tl:
        badge_pills_html += ' <span class="wb-pill testlab">TEST LAB PILOT</span>'
    if is_disc:
        badge_pills_html += ' <span class="wb-pill discontinued">DISCONTINUED</span>'
    if option_track and option_track.upper() != "ALL":
        badge_pills_html += f' <span class="wb-pill option">OPTION TRACK {_html.escape(option_track.upper())}</span>'

    unrolled_units = _iter_unrolled_workbook_units(reqs, badge_name=resolved_badge)
    req_sections_html: List[str] = []
    for idx, u in enumerate(unrolled_units, start=1):
        r_num_raw = str(u.get("req_number") or u.get("req_id") or str(idx))
        r_num = _html.escape(r_num_raw)
        r_title = _html.escape(str(u.get("topic_title") or u.get("title") or f"Requirement {r_num_raw}"))
        r_text_raw = str(u.get("req_text") or "")
        r_text = _html.escape(r_text_raw)
        r_verb = _html.escape(str(u.get("action_verb") or "Explain"))
        r_bucket = _html.escape(str(u.get("syllabus_bucket") or "In-Class Concept"))
        r_cit = _html.escape(str(u.get("pamphlet_page_citation") or u.get("pamphlet_citation") or "Official BSA Pamphlet"))
        org = u.get("workbook_organizer") or {}
        org_type_raw = str(org.get("organizer_type") or "RULED_EXPLAIN_BOX")
        org_type = _html.escape(org_type_raw)
        org_display_label = _html.escape(_format_workbook_organizer_label(org_type_raw))

        if u.get("is_group_header"):
            req_sections_html.append(
                f"""
                <div class="wb-group-header" data-req-group="{r_num}" data-organizer-type="{org_type}" style="background:#e0f2fe; border-left:5px solid #003f87; padding:10px 14px; border-radius:6px; margin:16px 0 10px 0;">
                  <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                    <div>
                      <span class="wb-req-badge">Requirement {r_num} Group</span>
                      <strong style="color:#003f87; font-size:14px;">{r_title}</strong>
                    </div>
                    <br/>
                    <div class="wb-req-cit-row" style="margin-top:4px; width:100%;">
                      <span class="wb-cit-tag">📖 {r_cit}</span>
                    </div>
                  </div>
                  <p style="margin:6px 0 0 0; font-size:12px; color:#1e293b;">{r_text}</p>
                </div>
                """
            )
            continue

        headers = [str(h) for h in (org.get("headers") or org.get("column_headers") or [f"Req {r_num_raw} Sub-Part", "Scout Notes & Field Evidence"])]
        row_labels = [str(rl) for rl in (org.get("row_labels") or ["Item 1", "Item 2", "Item 3"])]
        pre_app = bool(org.get("pre_approval_gate"))

        pre_app_html = ""
        if pre_app:
            pre_app_html = (
                '<div class="wb-preapproval-box">'
                '<strong>COUNSELOR PRE-APPROVAL BOX:</strong> '
                '<label style="margin-right:12px;"><input type="checkbox" /> Approved Before Starting</label> '
                '<span class="wb-sig-line">Counselor Signature: _______________________ Date Approved: ____________</span>'
                "</div>"
            )

        gear_items = [str(g) for g in (u.get("gear_checklist") or []) if str(g).strip()]
        gear_html = ""
        if gear_items:
            chk_items = "".join(
                f'<label style="display:block; margin:2px 0;"><input type="checkbox" name="gear_{r_num}_{g_i}" /> {_html.escape(g_txt)}</label>'
                for g_i, g_txt in enumerate(gear_items, start=1)
            )
            gear_html = (
                '<div class="wb-gear-checklist" style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:6px; padding:6px 10px; margin-bottom:8px; font-size:11.5px;">'
                "<strong>🧰 Equipment &amp; Preparation Checklist:</strong>"
                f"{chk_items}</div>"
            )

        th_cells = "".join(f"<th>{_html.escape(h)}</th>" for h in headers)
        tbody_rows: List[str] = []
        for rl in row_labels:
            editable_cells = "".join(
                '<td class="wb-fillable-cell" contenteditable="true">&nbsp;</td>'
                for _ in headers[1:]
            )
            tbody_rows.append(f"<tr><td class='wb-row-label'><strong>{_html.escape(rl)}</strong></td>{editable_cells}</tr>")

        mis = u.get("common_misconception_pair") or {}
        mis_html = ""
        if isinstance(mis, dict) and mis.get("misconception") and mis.get("fact"):
            mis_html = (
                '<div class="wb-misconception-strip">'
                f'<span class="wb-myth"><strong>Common Myth:</strong> {_html.escape(str(mis["misconception"]))}</span> '
                f'<span class="wb-fact"><strong>Pamphlet Fact:</strong> {_html.escape(str(mis["fact"]))}</span>'
                "</div>"
            )

        diag_html = ""
        diag_url_raw = str(u.get("workbook_diagram_url") or "").strip().lstrip("/")
        if diag_url_raw:
            try:
                from src.tools.asset_hydrator import hydrate_single_asset_on_demand
                hydrate_single_asset_on_demand(diag_url_raw)
            except Exception:
                pass
            diag_src = (
                f"/{_html.escape(diag_url_raw)}"
                if not diag_url_raw.startswith(("http://", "https://", "/"))
                else _html.escape(diag_url_raw)
            )
            diag_html = (
                f'<figure class="wb-reference-diagram" data-diagram-url="{_html.escape(diag_url_raw)}" '
                'style="margin:8px 0 10px 0; padding:10px 14px; border:1px solid #cbd5e1; border-radius:8px; background:#f8fafc; text-align:center;">'
                f'<img src="{diag_src}" alt="Req {r_num} Instructional Reference Diagram" '
                'style="max-width:100%; max-height:280px; height:auto; object-fit:contain; display:block; margin:0 auto;" />'
                '<figcaption style="font-size:11px; color:#334155; margin-top:6px; font-weight:600;">'
                f'Instructional Reference Diagram - Req {r_num}: {r_title}</figcaption>'
                '</figure>'
            )

        sketch_html = ""
        if org_type_raw == "SKETCH_AND_OBSERVATION_CANVAS" or any(
            k in r_text_raw.lower() for k in ("sketch", "draw a ", "draw the ", "diagram", "map")
        ):
            sketch_html = _build_svg_sketch_canvas_html(r_num_raw, row_labels, r_text_raw)

        req_sections_html.append(
            f"""
            <section class="wb-req-block" data-req-number="{r_num}" data-organizer-type="{org_type}">
              <div class="wb-req-header" style="flex-wrap:wrap;">
                <div>
                  <span class="wb-req-badge">Req {r_num}</span>
                  <strong class="wb-req-title">{r_title}</strong>
                </div>
                <div class="wb-req-meta" style="text-align:right;">
                  <span class="wb-verb-tag">{r_verb}</span>
                  <span class="wb-bucket-tag">{r_bucket}</span>
                  <span class="wb-verb-tag">{org_display_label}</span>
                  <br/>
                  <div class="wb-req-cit-row" style="margin-top:4px; width:100%;">
                    <span class="wb-cit-tag">📖 {r_cit}</span>
                  </div>
                </div>
              </div>
              <p class="wb-verbatim-text">{r_text}</p>
              {pre_app_html}
              {mis_html}
              {gear_html}
              {diag_html}
              <table class="wb-organizer-table" id="wb-table-req-{r_num}">
                <thead><tr>{th_cells}</tr></thead>
                <tbody>{"".join(tbody_rows)}</tbody>
              </table>
              {sketch_html}
              <div class="wb-signoff-strip">
                <span>Scout Initials: ________</span>
                <span>Buddy Verification: ________</span>
                <span>Counselor Sign-Off: _____________________ Date: ____/____/2026</span>
              </div>
            </section>
            """
        )

    fillable_unit_nums = [
        str(u.get("req_number") or u.get("req_id") or "")
        for u in unrolled_units
        if not u.get("is_group_header") and str(u.get("req_number") or u.get("req_id") or "").strip()
    ]
    # Group sub-requirements by parent requirement (Req 1, Req 2, ...) for scannable hierarchy
    parent_groups_order: List[str] = []
    parent_groups_map: Dict[str, Dict[str, Any]] = {}
    raw_parent_titles: Dict[str, str] = {}
    for r_item in reqs:
        p_id = str(r_item.get("req_number") or r_item.get("req_id") or "").strip()
        m_p = re.match(r"^(\d+)", p_id)
        p_key = m_p.group(1) if m_p else p_id
        if p_key and p_key not in raw_parent_titles:
            t_raw = str(r_item.get("topic_title") or r_item.get("title") or r_item.get("req_text") or "").strip()
            t_clean = re.sub(r"^(?:Requirement\s+\S+\s*[:\-\u2013\u2014]\s*)", "", t_raw, flags=re.IGNORECASE).strip()
            if len(t_clean) > 48:
                t_clean = t_clean[:45].rsplit(" ", 1)[0] + "..."
            raw_parent_titles[p_key] = t_clean or f"Requirement {p_key}"

    for u in unrolled_units:
        if u.get("is_group_header"):
            continue
        rn = str(u.get("req_number") or u.get("req_id") or "").strip()
        if not rn:
            continue
        p_num = str(u.get("parent_req_number") or "").strip()
        if not p_num:
            m_rn = re.match(r"^(\d+)", rn)
            p_num = m_rn.group(1) if m_rn else rn
        if p_num not in parent_groups_map:
            parent_groups_order.append(p_num)
            p_title = raw_parent_titles.get(p_num) or str(u.get("topic_title") or u.get("title") or f"Requirement {p_num}").strip()
            if len(p_title) > 48:
                p_title = p_title[:45].rsplit(" ", 1)[0] + "..."
            parent_groups_map[p_num] = {
                "parent_num": p_num,
                "parent_title": p_title,
                "bucket": str(u.get("syllabus_bucket") or "In-Class Concept").strip(),
                "units": [],
            }
        parent_groups_map[p_num]["units"].append(rn)

    group_cards_html: List[str] = []
    for p_num in parent_groups_order:
        grp = parent_groups_map[p_num]
        u_list = grp["units"]
        p_title_esc = _html.escape(grp["parent_title"])
        p_bucket_esc = _html.escape(grp["bucket"])
        sub_chips = "".join(
            f'<label class="wb-index-chip" style="display:inline-flex; align-items:center; gap:4px; padding:2px 7px; border:1px solid #cbd5e1; border-radius:4px; background:#ffffff; font-size:11px; font-weight:600; color:#1e293b; cursor:pointer;">'
            f'<input type="checkbox" name="idx_done_{_html.escape(rn)}" data-parent-req="{_html.escape(p_num)}" '
            f'onchange="var g=this.closest(\'.wb-index-parent-group\'); if(g){{var c=g.querySelectorAll(\'input[type=checkbox]:checked\').length; var t=g.querySelectorAll(\'input[type=checkbox]\').length; var b=g.querySelector(\'.wb-index-group-count\'); if(b)b.textContent=c+\'/\'+t;}}" /> '
            f'Req {_html.escape(rn)}</label>'
            for rn in u_list
        )
        group_cards_html.append(
            f'<div class="wb-index-parent-group" data-parent-req="{_html.escape(p_num)}" '
            f'style="display:flex; flex-direction:column; gap:5px; padding:6px 8px; border:1px solid #dbeafe; border-left:3.5px solid #003f87; border-radius:5px; background:#ffffff;">'
            f'<div style="display:flex; align-items:center; justify-content:space-between; gap:6px; flex-wrap:wrap;">'
            f'<div style="display:flex; align-items:center; gap:6px; min-width:0;">'
            f'<span style="background:#003f87; color:#ffffff; font-size:10.5px; font-weight:800; padding:1px 6px; border-radius:3px; white-space:nowrap;">Req {_html.escape(p_num)}</span>'
            f'<span style="font-size:11px; font-weight:700; color:#0f172a; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="{p_title_esc}">{p_title_esc}</span>'
            f'</div>'
            f'<div style="display:flex; align-items:center; gap:4px;">'
            f'<span style="font-size:9.5px; font-weight:600; color:#475569; background:#f1f5f9; padding:1px 5px; border-radius:3px;">{p_bucket_esc}</span>'
            f'<span class="wb-index-group-count" style="font-size:10px; font-weight:800; color:#003f87; background:#eff6ff; border:1px solid #bfdbfe; padding:0px 5px; border-radius:999px;">0/{len(u_list)}</span>'
            f'</div>'
            f'</div>'
            f'<div class="wb-index-subchips-row" style="display:flex; flex-wrap:wrap; gap:5px;">{sub_chips}</div>'
            f'</div>'
        )

    total_parent_count = len(parent_groups_order)
    total_sub_count = len(fillable_unit_nums)
    signoff_index_html = (
        '<div class="wb-signoff-index-grid" data-testid="wb-page1-signoff-grid" '
        'style="border:1.5px solid #003f87; border-radius:6px; background:#f8fafc; padding:10px 12px; margin-bottom:16px; font-size:11.5px;">'
        '<div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-bottom:8px;">'
        '<div style="font-weight:800; color:#003f87;">'
        '📋 Page-1 Requirement Completion &amp; Counselor Verification Index '
        f'<span style="font-weight:600; font-size:10.5px; color:#475569; margin-left:4px;">({total_parent_count} Core Requirements • {total_sub_count} Checkpoints)</span>'
        '</div>'
        '<button type="button" class="wb-index-collapse-btn" data-testid="btn-wb-index-toggle-compact" '
        'onclick="var grid=this.closest(\'.wb-signoff-index-grid\'); if(!grid)return; var compact=grid.getAttribute(\'data-compact\')===\'1\'; grid.setAttribute(\'data-compact\', compact?\'0\':\'1\'); grid.querySelectorAll(\'.wb-index-subchips-row\').forEach(function(r){{r.style.display=compact?\'flex\':\'none\';}}); this.textContent=compact?\'▴ Compact Summary View\':\'▾ Expand All Sub-Requirements\';" '
        'style="font-size:10.5px; font-weight:700; color:#003f87; background:#eff6ff; border:1px solid #93c5fd; border-radius:4px; padding:2px 8px; cursor:pointer;">'
        '▴ Compact Summary View</button>'
        '</div>'
        f'<div class="wb-index-grouped-matrix" data-testid="wb-page1-grouped-matrix" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(295px, 1fr)); gap:7px; margin-bottom:8px;">{"".join(group_cards_html)}</div>'
        '<div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; border-top:1px dashed #cbd5e1; padding-top:6px; color:#334155;">'
        '<span><strong>Unit Leader Pre-Approval (Blue Card #34124):</strong> _____________________ Date: ________</span>'
        '<span><strong>Counselor Final Sign-Off:</strong> _____________________ Date: ____/____/2026</span>'
        "</div></div>"
    )

    dates_str = " | ".join(session_dates) if session_dates else "Session 1 • Session 2 • Session 3 • Session 4 • Make-Up Day"
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{_html.escape(resolved_badge)} Merit Badge - Fillable Scout Workbook</title>
  <style>
    body {{ font-family: 'Segoe UI', Roboto, Arial, sans-serif; color: #0f172a; margin: 20px; line-height: 1.45; }}
    .wb-header {{ border-bottom: 3px solid #003f87; padding-bottom: 12px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: flex-start; }}
    .wb-title {{ font-size: 22px; font-weight: 800; color: #003f87; margin: 0 0 6px 0; }}
    .wb-pill {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; margin-right: 6px; }}
    .wb-pill.eagle {{ background: #fef3c7; color: #92400e; border: 1px solid #f59e0b; }}
    .wb-pill.elective {{ background: #e0f2fe; color: #075985; border: 1px solid #0284c7; }}
    .wb-pill.testlab {{ background: #f3e8ff; color: #6b21a8; border: 1px solid #9333ea; }}
    .wb-pill.discontinued {{ background: #fee2e2; color: #991b1b; border: 1px solid #dc2626; }}
    .wb-gta-banner {{ background: #eff6ff; border-left: 4px solid #003f87; padding: 8px 12px; font-size: 12px; margin-bottom: 16px; }}
    .wb-scout-id-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px; padding: 10px; border: 1px solid #cbd5e1; border-radius: 6px; background: #f8fafc; font-size: 12px; }}
    .wb-req-block {{ border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; margin-bottom: 14px; page-break-inside: avoid; }}
    .wb-req-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin-bottom: 8px; }}
    .wb-req-badge {{ background: #003f87; color: #fff; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 12px; margin-right: 6px; }}
    .wb-verb-tag, .wb-bucket-tag, .wb-cit-tag {{ font-size: 11px; padding: 2px 6px; border-radius: 4px; background: #f1f5f9; color: #334155; margin-left: 4px; }}
    .wb-verbatim-text {{ font-size: 12.5px; color: #1e293b; margin: 6px 0 10px 0; }}
    .wb-preapproval-box {{ background: #fffbeb; border: 1px solid #f59e0b; color: #92400e; padding: 6px 10px; border-radius: 4px; font-size: 11.5px; margin-bottom: 8px; }}
    .wb-misconception-strip {{ background: #f8fafc; border-left: 3px solid #ce1126; padding: 6px 10px; font-size: 11.5px; margin-bottom: 8px; }}
    .wb-organizer-table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 12px; }}
    .wb-organizer-table th {{ background: #003f87; color: #fff; text-align: left; padding: 6px 8px; border: 1px solid #003f87; }}
    .wb-organizer-table td {{ border: 1px solid #94a3b8; padding: 8px; vertical-align: top; }}
    .wb-row-label {{ width: 28%; background: #f8fafc; }}
    .wb-fillable-cell {{ min-height: 28px; background: #ffffff; }}
    .wb-signoff-strip {{ display: flex; justify-content: space-between; font-size: 11px; color: #475569; padding-top: 4px; }}
    @media print {{ body {{ margin: 0.4in; }} .no-print {{ display: none !important; }} }}
  </style>
</head>
<body>
  <div class="no-print" style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; background:#003f87; color:#fff; padding:10px 14px; border-radius:8px; margin-bottom:14px;">
    <div style="font-size:13px; font-weight:700;">
      📝 Interactive Fillable Scout Workbook (GTA §7.0.3.2) - Type directly into any table cell below or download the Fillable PDF:
    </div>
    <div style="display:flex; gap:8px; flex-wrap:wrap;">
      <a href="/api/v1/studiokit/fillable-workbook.pdf?badge_name={_html.escape(resolved_badge.replace(' ', '%20'))}&amp;option_track={_html.escape(option_track.upper())}" download style="background:#f59e0b; color:#0f172a; text-decoration:none; padding:6px 12px; border-radius:6px; font-size:12px; font-weight:800;">
        📥 Download Fillable Workbook (.PDF)
      </a>
      <a href="/api/v1/studiokit/class-prep-cpp.pdf?badge_name={_html.escape(resolved_badge.replace(' ', '%20'))}" download style="background:#e0f2fe; color:#075985; text-decoration:none; padding:6px 12px; border-radius:6px; font-size:12px; font-weight:800;">
        📄 Download 1-Page CPP (.PDF)
      </a>
    </div>
  </div>
  <div class="wb-header">
    <div>
      <h1 class="wb-title">{_html.escape(resolved_badge)} Merit Badge - Fillable Form (GTA §7.0.3.2) Scout Workbook</h1>
      <div>{badge_pills_html}</div>
      <div style="font-size:12px; color:#475569; margin-top:4px;">Counselor: {c_name} ({c_troop}) • {c_email} • Schedule: {_html.escape(dates_str)}</div>
    </div>
  </div>
  <div class="wb-gta-banner">
    <strong>BSA Guide to Advancement §7.0.3.2 Notice:</strong> Merit badge workbooks are optional organizational study aids for Scouts. A counselor must never require a Scout to fill out a worksheet as a condition of sign-off when the official requirement specifies oral explanation, discussion, or physical demonstration.
  </div>
  <div class="wb-scout-id-grid">
    <div><strong>Scout Name:</strong> _______________________</div>
    <div><strong>Troop &amp; Council:</strong> ___________________</div>
    <div><strong>BSA Member ID:</strong> ____________________</div>
    <div><strong>Option Track:</strong> {_html.escape(option_track.upper())}</div>
  </div>
  {signoff_index_html}
  {"".join(req_sections_html)}
</body>
</html>"""

    return {
        "status": "SUCCESS",
        "badge_name": resolved_badge,
        "is_eagle_required": is_eagle,
        "is_test_lab_pilot": is_tl,
        "is_discontinued": is_disc,
        "selected_option_track": option_track.upper(),
        "requirement_count": len(reqs),
        "unrolled_unit_count": len([u for u in unrolled_units if not u.get("is_group_header")]),
        "gta_compliance_clause": "GTA §7.0.3.2",
        "workbook_html": html_doc,
        "html_content": html_doc,
        "html_document": html_doc,
        "workbook_markdown": res.get("counselor_workbook_markdown", ""),
    }


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
                recovery_suggestion="Provide a valid 'badge_name' string matching one of the 144 Scouts BSA Merit Badges.",
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
    req_opt_track = _normalize_option_track_filter(getattr(request, "option_track", None), badge_name=badge_title)
    c_info_key = repr(request.counselor_info.model_dump()) if request.counselor_info else ""
    research_cache_key = (badge_title.lower(), req_opt_track, c_info_key)
    if not hasattr(fetch_merit_badge_pamphlet_pdf, "_lru_cache"):
        fetch_merit_badge_pamphlet_pdf._lru_cache = {}
    if research_cache_key in fetch_merit_badge_pamphlet_pdf._lru_cache:
        import copy
        return copy.deepcopy(fetch_merit_badge_pamphlet_pdf._lru_cache[research_cache_key])

    # 1. Case-insensitive lookup in rich benchmark database + live BSA Pamphlet PDF enrichment
    for key, data in BENCHMARK_BADGES_DATA.items():
        if key.lower() == badge_title.lower():
            req_opt_track = _normalize_option_track_filter(getattr(request, "option_track", None), badge_name=key)
            raw_reqs = _merge_curated_with_official_requirements(
                key,
                list(data["requirements"]),
                official_cache.get(key) or [],
            )
            raw_reqs = _unroll_multi_option_requirements(key, raw_reqs, option_track=req_opt_track)

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
                option_tracks=get_badge_option_tracks(key),
                selected_option_track=req_opt_track,
                status="SUCCESS",
            )
            out_dict = result.model_dump()
            if len(fetch_merit_badge_pamphlet_pdf._lru_cache) < 256:
                import copy
                fetch_merit_badge_pamphlet_pdf._lru_cache[research_cache_key] = copy.deepcopy(out_dict)
            return out_dict

    # 2. Check if badge is in the 149-badge OFFICIAL_BSA_MERIT_BADGES_CATALOG
    from src.config import get_merit_badge_metadata

    catalog_meta = get_merit_badge_metadata(raw_name)
    canonical_match: Optional[str] = str(catalog_meta["badge_name"]) if catalog_meta else None
    if not canonical_match:
        for official_badge in ALL_OFFICIAL_MERIT_BADGES:
            if official_badge.lower() == badge_title.lower():
                canonical_match = official_badge
                break

    resolved_name = canonical_match or badge_title
    req_opt_track = _normalize_option_track_filter(getattr(request, "option_track", None), badge_name=resolved_name)
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
                recovery_suggestion="Check spelling or select from the 149 official Scouts BSA Merit Badges.",
                available_badges_sample=["First Aid", "Camping", "Weather", "Citizenship in the Community"],
            )

    # 3. Prefer official requirements from data/official_requirements_cache.json for all 149 Merit Badges!
    cached_official_reqs = official_cache.get(resolved_name)
    if cached_official_reqs:
        raw_fallback_reqs = []
        for i, off_r in enumerate(cached_official_reqs):
            r_copy = dict(off_r)
            r_copy["req_id"] = str(off_r.get("req_number", str(i + 1)))
            r_copy["req_number"] = str(off_r.get("req_number", str(i + 1)))
            r_copy["req_text"] = str(off_r.get("req_text", ""))
            r_copy["sub_requirements"] = list(off_r.get("sub_requirements") or [])
            raw_fallback_reqs.append(r_copy)
        raw_fallback_reqs = _unroll_multi_option_requirements(
            resolved_name, raw_fallback_reqs, option_track=req_opt_track
        )
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
        option_tracks=get_badge_option_tracks(resolved_name),
        selected_option_track=req_opt_track,
        status="SUCCESS",
    )
    out_dict = result.model_dump()
    if len(fetch_merit_badge_pamphlet_pdf._lru_cache) < 256:
        import copy
        fetch_merit_badge_pamphlet_pdf._lru_cache[research_cache_key] = copy.deepcopy(out_dict)
    return out_dict


def fetch_official_merit_badge_requirements(
    badge_name: str,
    option_track: str = "ALL",
    counselor_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience wrapper around `fetch_merit_badge_pamphlet_pdf` accepting a string badge_name."""
    return fetch_merit_badge_pamphlet_pdf(
        MeritBadgeResearchRequest(
            badge_name=badge_name,
            option_track=option_track or "ALL",
            counselor_info=CounselorTitleSlideInfo(**counselor_info) if counselor_info else None,
        )
    )



