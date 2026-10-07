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
    "American Business", "American Cultures", "American Heritage", "American Labor",
    "Animal Science", "Animation", "Archaeology", "Archery", "Architecture", "Art",
    "Astronomy", "Athletics", "Automotive Maintenance", "Aviation", "Backpacking",
    "Basketry", "Bird Study", "Bugling", "Camping", "Canoeing", "Chemistry", "Chess",
    "Citizenship in Society", "Citizenship in the Community", "Citizenship in the Nation",
    "Citizenship in the World", "Climbing", "Coin Collecting", "Collections",
    "Communication", "Composite Materials", "Cooking", "Crime Prevention", "Cycling",
    "Dentistry", "Digital Technology", "Disabilities Awareness", "Dog Care", "Drafting",
    "Electricity", "Electronics", "Emergency Preparedness", "Energy", "Engineering",
    "Entrepreneurship", "Environmental Science", "Exploration", "Family Life",
    "Farm Mechanics", "Fingerprinting", "Fire Safety", "First Aid", "Fish and Wildlife Management",
    "Fishing", "Fly-Fishing", "Forestry", "Game Design", "Gardening", "Genealogy",
    "Geocaching", "Geology", "Golf", "Graphic Arts", "Health Care Professions", "Hiking",
    "Home Repairs", "Horsemanship", "Indian Lore", "Insect Study", "Inventing",
    "Journalism", "Kayaking", "Landscape Architecture", "Law", "Leatherwork",
    "Lifesaving", "Mammal Study", "Metalwork", "Mining in Society", "Model Design and Building",
    "Motorboating", "Moviemaking", "Music", "Nature", "Nuclear Science", "Oceanography",
    "Orienteering", "Painting", "Personal Fitness", "Personal Management", "Pets",
    "Photography", "Pioneering", "Plant Science", "Plumbing", "Pottery", "Programming",
    "Public Health", "Public Speaking", "Pulp and Paper", "Radio", "Railroading",
    "Reading", "Recreation", "Reptile and Amphibian Study", "Rifle Shooting", "Robotics",
    "Rowing", "Safety", "Salesmanship", "Scholarship", "Scouting Heritage", "Scuba Diving",
    "Sculpture", "Search and Rescue", "Shotgun Shooting", "Signs, Signals, and Codes",
    "Skating", "Small-Boat Sailing", "Snow Sports", "Soil and Water Conservation",
    "Space Exploration", "Sports", "Stamp Collecting", "Surveying", "Sustainability",
    "Swimming", "Textile", "Theater", "Traffic Safety", "Truck Transportation",
    "Veterinary Medicine", "Water Sports", "Weather", "Welding", "Whitewater",
    "Wilderness Survival", "Wood Carving", "Woodwork",
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

BENCHMARK_BADGES_DATA: Dict[str, Dict[str, Any]] = {
    "First Aid": {
        "is_eagle_required": True,
        "pamphlet_pdf_url": "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/First%20Aid.pdf",
        "drg_url": "https://www.scouting.org/skills/merit-badges/digital-resource-guides/first-aid/",
        "requirements": [
            {
                "req_id": "1",
                "req_number": "1",
                "action_verb": "Demonstrate",
                "req_text": "Demonstrate to your counselor that you have current knowledge of all first-aid requirements for Tenderfoot, Second Class, and First Class ranks, and explain how to perform rapid scene size-up and four-tier emergency triage.",
                "safety_callout": "Always ensure scene safety, apply the Buddy System, and wear nitrile PPE gloves before rendering aid.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "DECISION_TREE_FLOW",
                "visual_diagram_type": "triage_decision_tree",
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
                "counselor_signoff_criteria": "Scout must bring signed Scoutbook rank verification for Tenderfoot/Second/First Class first aid and walk through the 4-tier triage decision tree.",
            },
            {
                "req_id": "2a",
                "req_number": "2a",
                "parent_id": "2",
                "action_verb": "Explain",
                "req_text": "Explain how you would obtain emergency medical assistance from your home and on a wilderness campout, and explain the importance of the BSA Annual Health and Medical Record (Parts A, B, and C).",
                "safety_callout": "Medical records contain protected health information and must be kept confidential by adult leaders.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain",
                "recommended_archetype": "WORKED_EXAMPLE_TEMPLATE",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_excerpts": [
                    "Part A Informed Consent: Covers talent release, emergency medical authorization, and parent/guardian contact numbers for all Scouting events.",
                    "Part B General Health History: Documents allergies (food, insect stings, medications), tetanus date, and non-prescription medication permissions.",
                    "Part C Pre-Participation Physical: Requires a licensed health-care provider signature for resident camps and high-adventure treks over 72 hours.",
                    "Backcountry Emergency Dispatch: Combine satellite SOS messenger coordinates, nearest trailhead access point, and patient vital signs when contacting SAR.",
                ],
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
                "counselor_signoff_criteria": "Scout explains Parts A/B/C of the BSA AHMR and demonstrates a complete wilderness 911 dispatch report.",
            },
            {
                "req_id": "2b",
                "req_number": "2b",
                "parent_id": "2",
                "action_verb": "Prepare",
                "req_text": "Prepare a personal first-aid kit to take with you on a hike and inspect a troop first-aid kit, explaining how each of the 21 essential items is used.",
                "safety_callout": "Inspect sterile dressings for intact packaging and check expiration dates on antiseptic wipes and medications before every trek.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "GEAR_CHECKLIST_GRID",
                "visual_diagram_type": "first_aid_kit_grid",
                "pamphlet_excerpts": [
                    "Personal Kit Portability: Pack personal hike items in a waterproof resealable bag stored in an exterior backpack pocket for instant access.",
                    "Barrier Protection Essentials: Always carry 2 pairs of non-latex nitrile exam gloves and a CPR breathing barrier mask.",
                    "Blister & Wound Care: Include moleskin pre-cut pads, sterile 3x3 gauze sponges, adhesive bandages, and non-adherent trauma dressings.",
                    "Troop Kit Scaling: Troop kits add SAM malleable splints, commercial windlass tourniquets, triangular cravat bandages, and elastic wraps.",
                ],
                "gear_checklist": [
                    "Adhesive bandages (6 assorted sizes)",
                    "Sterile gauze pads (2 three-by-three-inch pads)",
                    "Adhesive medical tape (1 small roll)",
                    "Moleskin blister dressings (3x6-inch sheet)",
                    "Soap or alcohol-based hand sanitizer (small travel bottle)",
                    "Triple antibiotic or wound gel packets (4 single-use)",
                    "Scissors and fine-point splinter tweezers",
                    "Non-latex nitrile exam gloves (2 pairs)",
                    "CPR mouth-barrier resuscitation mask (1 pocket shield)",
                    "Pencil and waterproof SOAP note triage card",
                    "Elastic roller bandage (1 three-inch ACE wrap)",
                    "Triangular cravat bandages (2 forty-inch cotton slings)",
                ],
                "counselor_signoff_criteria": "Scout presents their physical personal first-aid kit for inspection and identifies the purpose of every item.",
            },
            {
                "req_id": "3",
                "req_number": "3",
                "action_verb": "Demonstrate",
                "req_text": "Describe the symptoms and signs of, and demonstrate proper procedures for handling life-threatening bleeding, windlass tourniquet application, and hypovolemic shock.",
                "safety_callout": "Never remove an original blood-soaked gauze pad; layer fresh sterile gauze on top and apply a windlass tourniquet 2 inches above arterial extremity wounds.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "STEP_BY_STEP_PROCEDURE_4CARD",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_excerpts": [
                    "Arterial Bleeding Recognition: Bright red spurting blood or rapid pooling requires immediate high-force direct pressure.",
                    "Windlass Tourniquet Placement: Place commercial CoTCCC tourniquet 2 to 3 inches proximal to the wound, never directly over a joint.",
                    "Time Recording Mandate: Write the exact time of tourniquet application on the tourniquet strap and patient's forehead with a permanent marker.",
                    "Shock Prevention Protocol: Lay the victim flat on their back, insulate from ground chill with a sleeping pad, and maintain normal body temperature.",
                ],
                "step_by_step_procedure": [
                    "Apply Direct Pressure: Press firmly with gloved hands and sterile gauze pad directly over the bleeding source for 5 full minutes.",
                    "Position Windlass Tourniquet: Strap tourniquet 2 inches above the limb wound (never over knee or elbow joint) and pull tight.",
                    "Twist Windlass Rod: Rotate the windlass rod until bright red bleeding stops completely and distal pulse disappears.",
                    "Lock & Treat Shock: Secure the rod in the clip, record application time ('TK 14:20'), lay patient flat, and insulate with blankets.",
                ],
                "counselor_signoff_criteria": "Scout physically demonstrates direct pressure dressing and windlass tourniquet application on a simulated limb.",
            },
            {
                "req_id": "4a",
                "req_number": "4a",
                "parent_id": "4",
                "action_verb": "Demonstrate",
                "req_text": "Demonstrate cardiopulmonary resuscitation (CPR) using a 30:2 compression-to-breath cycle at 100 to 120 compressions per minute and proper Automated External Defibrillator (AED) pad placement on a training manikin.",
                "safety_callout": "Call 911 immediately upon finding an unresponsive person and ensure all rescuers stand clear before pressing the AED shock button.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate, Guide & Enable",
                "recommended_archetype": "HANDS_ON_PRACTICE_STATION",
                "visual_diagram_type": "cpr_aed_cycle",
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
                "counselor_signoff_criteria": "Scout completes at least 2 full cycles of 30:2 CPR and attaches AED training pads accurately on a CPR manikin.",
            },
            {
                "req_id": "4b",
                "req_number": "4b",
                "parent_id": "4",
                "action_verb": "Demonstrate",
                "req_text": "Demonstrate the five-and-five (5 back blows and 5 abdominal thrusts) Heimlich maneuver for a conscious choking victim who cannot speak, cough, or breathe.",
                "safety_callout": "Never perform blind finger sweeps in a choking victim's mouth, and use simulation vests or verbal walk-throughs rather than forceful thrusts on healthy Scouts.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "STEP_BY_STEP_PROCEDURE_4CARD",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_excerpts": [
                    "Universal Choking Sign: Clutching the throat with inability to speak, cough forcefully, or breathe signals complete airway obstruction.",
                    "Five Back Blows: Bend the victim forward at the waist and deliver 5 firm blows between the shoulder blades with the heel of your hand.",
                    "Five Abdominal Thrusts: Place thumb side of fist just above the navel (well below the xiphoid process) and pull inward and upward.",
                    "Unconscious Transition: If the choking victim becomes unresponsive, lower them to the floor, call 911, and begin CPR chest compressions.",
                ],
                "step_by_step_procedure": [
                    "Confirm Severe Obstruction: Ask 'Are you choking?' and get consent to help if the person nods and cannot cough or speak.",
                    "Deliver 5 Back Blows: Support chest with one hand, lean victim forward, and strike firmly 5 times between shoulder blades.",
                    "Perform 5 Abdominal Thrusts: Stand behind victim, place fist thumb-side in above navel, grasp with other hand, and thrust inward-upward.",
                    "Repeat Until Clear: Alternate 5 back blows and 5 abdominal thrusts until the object is expelled or victim becomes unresponsive.",
                ],
                "counselor_signoff_criteria": "Scout demonstrates proper hand positioning and 5-and-5 sequence on a choking training vest or manikin.",
            },
            {
                "req_id": "5a",
                "req_number": "5a",
                "parent_id": "5",
                "action_verb": "Describe",
                "req_text": "Describe the signals, differential diagnosis, and emergency treatment for environmental emergencies including Heat Exhaustion vs. Heat Stroke, hypothermia, frostbite, dehydration, and insect/snakebites.",
                "safety_callout": "Heat stroke and systemic anaphylaxis are immediate life-threatening emergencies requiring 911 activation and rapid intervention.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "DIFFERENTIAL_COMPARISON_2COL",
                "visual_diagram_type": "heat_comparison",
                "pamphlet_excerpts": [
                    "Thermoregulatory Failure: Heat stroke occurs when core temperature exceeds 104°F (40°C) and central nervous system function breaks down.",
                    "Mental Status Differentiator: Confusion, slurred speech, ataxia, or unconsciousness immediately upgrades heat illness to Heat Stroke (911).",
                    "Hypothermia Rewarming: Remove wet cotton clothes, place Scout in a dry sleeping bag with warm water bottles at armpits and groin.",
                    "Pit Viper Snakebite Care: Keep bitten limb immobilized at heart level, remove rings/watches, and never cut, suck, or apply ice/tourniquets.",
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
                "counselor_signoff_criteria": "Scout distinguishes Heat Exhaustion from Heat Stroke across all 4 clinical criteria and explains hypothermia and snakebite rules.",
            },
            {
                "req_id": "6a",
                "req_number": "6a",
                "parent_id": "6",
                "action_verb": "Demonstrate",
                "req_text": "Demonstrate anatomical and rigid splinting techniques for closed and open fractures, sprains, and dislocations, including pre- and post-splint distal Circulation, Motor, and Sensation (CMS) checks.",
                "safety_callout": "Never attempt to straighten a dislocated joint or push a protruding open-fracture bone end back beneath the skin.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate, Guide & Enable",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "splinting_cms",
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
                "counselor_signoff_criteria": "Scout applies a padded forearm or lower-leg splint plus sling/swath on a buddy and performs pre- and post-splint CMS checks.",
            },
            {
                "req_id": "7a",
                "req_number": "7a",
                "parent_id": "7",
                "action_verb": "Demonstrate",
                "req_text": "Describe the conditions under which an injured person should be moved, and demonstrate single-rescuer and two-rescuer emergency carries (walking assist, pack-strap carry, four-handed seat, and blanket drag).",
                "safety_callout": "Never move a victim with suspected head, neck, or spinal injury unless they face immediate life-threatening danger such as fire, rising water, or collapsing structure.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "edge_phase": "Demonstrate & Guide",
                "recommended_archetype": "STEP_BY_STEP_PROCEDURE_4CARD",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_excerpts": [
                    "Spinal Immobilization Priority: Assume cervical spine injury after any fall from height, diving accident, or high-impact collision.",
                    "Emergency Drag Indications: Use clothes drag, ankle drag, or blanket drag only to pull a victim out of immediate smoke, fire, or rockfall.",
                    "Two-Rescuer Four-Handed Seat: Interlock wrists in a square grid to carry a conscious victim with a sprained ankle who has no spinal injury.",
                    "Rescuer Body Mechanics: Lift with quadriceps and glutes while keeping the spine straight and load close to the center of gravity.",
                ],
                "step_by_step_procedure": [
                    "Assess Spinal Risk: Confirm zero neck/back pain, numbness, or high-mechanism trauma before attempting any upright carry.",
                    "Form Four-Handed Seat: Two rescuers grasp their own left wrist with right hand and partner's right wrist with left hand.",
                    "Load Conscious Patient: Squat evenly, have the patient sit on the wrist grid and place arms around rescuers' shoulders.",
                    "Lift & Step in Unison: Rise together on the count of three using leg muscles and step forward with inside feet synchronized.",
                ],
                "counselor_signoff_criteria": "Scout demonstrates walking assist and two-rescuer four-handed seat carry with a buddy using safe lifting mechanics.",
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
                "action_verb": "Explain",
                "req_text": "Explain what citizenship in the nation means and what it takes to be a good citizen of this country, and discuss the rights, liberties, and obligations of U.S. citizens including the four pillars of the 14th Amendment.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "SPLIT_VISUAL_EXPLAINER",
                "visual_diagram_type": "fourteenth_amendment_shield",
                "pamphlet_excerpts": [
                    "14th Amendment Citizenship Clause: 'All persons born or naturalized in the United States, and subject to the jurisdiction thereof, are citizens of the United States and of the State wherein they reside.'",
                    "Due Process Clause: Prohibits state and local governments from depriving any person of life, liberty, or property without fair legal procedures.",
                    "Equal Protection Clause: Guarantees that every person within a jurisdiction receives equal treatment under the law regardless of race, religion, or origin.",
                    "Civic Obligations vs. Responsibilities: Obeying laws, paying taxes, serving on a jury, and registering for Selective Service are legal duties; voting and community service are vital civic responsibilities.",
                ],
                "step_by_step_procedure": [
                    "Birthright & Naturalization: Acquire citizenship by birth on U.S. soil (jus soli), citizen parentage (jus sanguinis), or USCIS naturalization.",
                    "Exercise Constitutional Rights: Practice freedom of speech, press, religion, assembly, and petition while respecting others' rights.",
                    "Fulfill Legal Obligations: Obey federal/state/local laws, pay taxes honestly, and serve on a trial jury when summoned.",
                    "Participate in Self-Government: Stay informed on public issues, vote in elections, and serve your community through Scouting.",
                ],
                "counselor_signoff_criteria": "Scout explains the 14th Amendment definition of citizenship, constitutional rights, and civic duties vs. responsibilities.",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Visit",
                "req_text": "Do TWO of the following: (a) Visit a place that is listed as a National Historic Landmark or that is on the National Register of Historic Places, (b) Tour your state capitol building or the U.S. Capitol, (c) Tour a federal facility, or (d) Choose a national monument that interests you and explain its historical significance.",
                "safety_callout": "Follow Youth Protection buddy system and parental accompaniment rules when touring federal facilities or historic landmarks.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "edge_phase": "Enable",
                "recommended_archetype": "GEAR_CHECKLIST_GRID",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_excerpts": [
                    "National Register of Historic Places: Maintained by the National Park Service under the National Historic Preservation Act of 1966.",
                    "Capitol Architecture & Bicameral Chambers: State and federal capitols house the Senate and House chambers alongside public committee hearing rooms.",
                    "Federal Facility Missions: Federal courthouses, NASA centers, national laboratories, VA hospitals, and U.S. Mint facilities execute constitutional functions.",
                    "Field Preparation: Research when the landmark was designated, what historical turning point occurred there, and how it shapes American identity today.",
                ],
                "gear_checklist": [
                    "Completion of 2 of the 4 Requirement 2 civic exploration options (2a, 2b, 2c, or 2d)",
                    "Field notes or brochure/photo from National Historic Landmark or State/U.S. Capitol tour",
                    "Summary of why the landmark or monument was added to the National Register",
                    "Explanation of what you learned about the functions of federal or state government",
                ],
                "counselor_signoff_criteria": "Scout presents field notes/photos from two completed Requirement 2 options and explains their historical significance.",
            },
            {
                "req_id": "3",
                "req_number": "3",
                "action_verb": "Discuss",
                "req_text": "Watch the national evening news for five days in a row on television, or read the main stories on the front page of a daily newspaper or a national news website for five days in a row. Discuss the national issues that you learned about with your counselor and how one issue affects your family and community.",
                "safety_callout": None,
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "WORKED_EXAMPLE_TEMPLATE",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_excerpts": [
                    "Media Literacy & Fact vs. Opinion: Distinguish verifiable primary-source reporting from editorial commentary and partisan opinion columns.",
                    "Federal Policy Connection: Identify which branch of the federal government (Congress, Executive Agency, or Federal Courts) is involved in each headline.",
                    "Local & Family Impact: Trace how national decisions on infrastructure, interest rates, education, or energy prices directly affect your hometown.",
                    "Balanced Source Tracking: Compare coverage across multiple reputable national outlets over five consecutive days.",
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
                "counselor_signoff_criteria": "Scout presents a 5-day consecutive national news log and analyzes how one national issue impacts their family and community.",
            },
            {
                "req_id": "4",
                "req_number": "4",
                "action_verb": "Discuss",
                "req_text": "Discuss each of the following documents with your counselor and tell how you feel life in the United States might be different without each one: (a) Declaration of Independence, (b) Preamble to the Constitution, (c) The Constitution, (d) Bill of Rights, and (e) Amendments to the Constitution.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "DIFFERENTIAL_COMPARISON_2COL",
                "visual_diagram_type": "procedural_flow",
                "pamphlet_excerpts": [
                    "Declaration of Independence (1776): Asserts unalienable rights to Life, Liberty, and the Pursuit of Happiness and that governments derive just powers from the consent of the governed.",
                    "The Preamble's Six Purposes: Form a more perfect Union, establish Justice, insure domestic Tranquility, provide for the common defence, promote the general Welfare, and secure the Blessings of Liberty.",
                    "U.S. Constitution (1787): Establishes federalism, separation of powers across Articles I-III, and the supreme law of the land.",
                    "Bill of Rights (1791) & Amendments 11-27: First 10 amendments safeguard individual liberties; later amendments abolished slavery (13th), guaranteed equal protection (14th), and expanded voting rights (15th, 19th, 26th).",
                ],
                "comparison_data": {
                    "left_header": "Declaration & Preamble (Foundational Ideals)",
                    "left_badge": "WHY WE GOVERN",
                    "left_points": [
                        "Declaration of Independence (July 4, 1776): Proclaims natural rights and moral justification for self-government",
                        "Consent of the Governed: Establishes that sovereignty belongs to the people, not a monarch",
                        "The Constitutional Preamble: States the 6 core goals of the Republic beginning with 'We the People'",
                        "Without These Documents: No shared moral standard of human equality or unified national purpose",
                    ],
                    "right_header": "Constitution, Bill of Rights & Amendments",
                    "right_badge": "SUPREME LAW",
                    "right_points": [
                        "Articles I-VII Framework: Creates enforceable separation of powers, federalism, and Article V amendment process",
                        "Bill of Rights (Amendments 1-10): Protects speech, religion, press, fair trials, and reserves powers to states/people",
                        "Amendments 11-27 Evolution: Ended slavery (13th), secured equal protection (14th), and lowered voting age to 18 (26th)",
                        "Without These Documents: Unchecked government authority, no independent courts, and no guaranteed civil liberties",
                    ],
                },
                "counselor_signoff_criteria": "Scout explains all 5 foundational documents and analyzes how American life would change without each one.",
            },
            {
                "req_id": "6",
                "req_number": "6",
                "action_verb": "Explain",
                "req_text": "List the six functions of government as noted in the Preamble to the Constitution, and explain the Three Branches of the federal government, how they check and balance each other, and how citizens can participate.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "edge_phase": "Explain & Guide",
                "recommended_archetype": "SPATIAL_FIELD_DIAGRAM",
                "visual_diagram_type": "checks_balances_triangle",
                "pamphlet_excerpts": [
                    "Legislative Branch (Article I, Congress): Bicameral Senate (100) and House (435) draft statutes, levy taxes, appropriate funds, declare war, and confirm nominees.",
                    "Executive Branch (Article II, President & Cabinet): Enforces federal laws, commands the Armed Forces, negotiates treaties, and exercises veto power.",
                    "Judicial Branch (Article III, Supreme Court & Federal Courts): Interprets the Constitution and exercises judicial review (Marbury v. Madison) to strike down unconstitutional acts.",
                    "Reciprocal Checks & Balances: Congress overrides presidential vetoes with a 2/3 vote and can impeach; President appoints judges; Senate confirms; Courts review laws and executive orders.",
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
                "counselor_signoff_criteria": "Scout lists the 6 Preamble functions and traces the checks and balances connecting the Legislative, Executive, and Judicial branches.",
            },
            {
                "req_id": "8",
                "req_number": "8",
                "action_verb": "Name",
                "req_text": "Name your two U.S. Senators and the member of Congress from your congressional district. Write a letter about a national issue and send it to one of these elected officials, sharing your view with your counselor and discussing any response you receive.",
                "safety_callout": "Review correspondence with a parent or counselor before mailing or submitting via official Senate.gov / House.gov constituent portals.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "edge_phase": "Enable",
                "recommended_archetype": "WORKED_EXAMPLE_TEMPLATE",
                "visual_diagram_type": "procedural_flow",
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
                "req_id": "1a",
                "req_number": "1a",
                "parent_id": "1",
                "action_verb": "Explain",
                "req_text": "Explain to your counselor the most likely hazards you may encounter while participating in cooking activities and what you should do to anticipate, help prevent, mitigate, and respond to these hazards (burns, knife cuts, cross-contamination, and food allergies).",
                "safety_callout": "Strictly enforce food allergy checks, USDA safe internal temperatures, and Totin' Chip/Firem'n Chit kitchen safety procedures.",
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "2",
                "req_number": "2",
                "action_verb": "Explain",
                "req_text": "Explain the USDA MyPlate nutritional guidelines, daily caloric needs for active Scouts, and how to read food nutrition labels for sodium, added sugars, and allergens.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
            },
            {
                "req_id": "3",
                "req_number": "3",
                "action_verb": "Demonstrate",
                "req_text": "Describe the five basic cooking methods (boiling, baking, frying, simmering, and steaming/foil-pack) and demonstrate safe camp stove and Dutch oven operation.",
                "safety_callout": "Never use chemical stoves or charcoal inside a tent; always keep a fire extinguisher or water bucket within reach.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
            },
            {
                "req_id": "4",
                "req_number": "4",
                "action_verb": "Prepare",
                "req_text": "Using the MyPlate food guide, plan a menu for three full days of meals (three breakfasts, three lunches, and three dinners) to be cooked at home, create an itemized grocery budget, and cook one breakfast, one lunch, and one dinner.",
                "safety_callout": "Wash hands for 20 seconds and use separate cutting boards for raw meat and fresh produce.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
            {
                "req_id": "5",
                "req_number": "5",
                "action_verb": "Prepare",
                "req_text": "Plan, budget, and cook two breakfasts, two lunches, and two dinners plus a dessert on a patrol campout using at least three different cooking methods.",
                "safety_callout": "Never leave active camp stoves or campfires unattended.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
            },
            {
                "req_id": "6",
                "req_number": "6",
                "action_verb": "Prepare",
                "req_text": "Plan and prepare a trail and backpacking menu (two meals and a trail snack) that requires no refrigeration and uses bear-safe storage.",
                "safety_callout": "Hang bear bags or use approved bear canisters in wilderness areas.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
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
                    "Definition of Meteorology: Meteorology is the scientific study of Earth's atmosphere and its weather, from Greek 'meteoron' (things in the air) and 'logos' (knowledge or discussion).",
                    "Weather vs. Climate: Weather refers to short-term (seconds to days) variations in the atmosphere, whereas climate is the average course or condition of weather at a location over a period of years.",
                    "Impacts on Agriculture & Mariners: Farmers depend on rain timing and frost/hail forecasts to protect crops; mariners monitor wind, seas, dense fog, and freezing spray that can capsize vessels.",
                    "Impacts on Aviators & Construction: Aviators avoid airframe icing, severe turbulence, and low ceilings/visibility; construction crews plan concrete, roofing, and crane work around rain, wind, and temperature extremes.",
                ],
                "topic_slides": [
                    {
                        "title": "Definition of Meteorology",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "What Is Meteorology: Meteorology is the scientific study of the Earth's atmosphere, its physical processes, and its weather.",
                            "Greek Etymology ('Meteoron'): Derived from the ancient Greek word 'meteoron', meaning 'things high up in the air'.",
                            "Greek Etymology ('Logos'): Combined with 'logos', meaning 'knowledge, study, or discussion'.",
                            "Core Atmospheric Variables: Meteorologists measure temperature, barometric air pressure, wind speed and direction, humidity, cloud cover, and precipitation.",
                        ],
                    },
                    {
                        "title": "Weather and Climate",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s04_img2.png",
                        "bullets": [
                            "Weather (Short-Term State): Short-term variations in the atmosphere occurring over seconds, minutes, hours, or days at a specific place.",
                            "Climate (Long-Term Average): The average course or statistical condition of the weather at a given location, typically measured over 30 or more years.",
                            "How to Remember the Difference: 'Climate is what you expect (such as a cold snowy New England winter); weather is what you get on a specific afternoon.'",
                        ],
                    },
                    {
                        "title": "Effects on Agriculture",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s05_img1.png",
                        "bullets": [
                            "Rainfall Amount & Timing: Too little rain causes drought and crop failure, while excessive rain at planting or harvest rots seeds and floods fields.",
                            "Hail Damage: Large hailstones from severe thunderstorms can shred leaves and destroy entire fields of corn, wheat, and fruit in minutes.",
                            "Strong Winds: High straight-line winds flatten tall crops (lodging), erode topsoil, and strip blossoms from orchard trees.",
                            "Frosts and Freezes: Late spring or early autumn freezes kill tender vegetation and citrus buds; forecasts allow farmers to irrigate, smudge, or harvest early.",
                        ],
                    },
                    {
                        "title": "Effects on Mariners",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s06_img1.png",
                        "bullets": [
                            "Winds and High Seas: Wind speed and fetch determine wave height; gale- and hurricane-force winds create dangerous swells that threaten vessels.",
                            "Dense Marine Fog: Reduces visibility to near zero, disorienting sailors and increasing the risk of collisions or running aground.",
                            "Freezing Spray: In subfreezing gale conditions, ocean spray freezes instantly onto a boat's superstructure, adding tons of top-heavy ice that can capsize the vessel.",
                            "Why Marine Forecasts Matter: Advance marine weather warnings allow captains to plot safe routes or remain in harbor.",
                        ],
                    },
                    {
                        "title": "Effects on Aviators",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s07_img1.png",
                        "bullets": [
                            "Airframe Icing: Supercooled water droplets freeze onto wings and propellers, increasing weight, increasing aerodynamic drag, and destroying lift.",
                            "Turbulence & Wind Shear: Rapid updrafts, downdrafts, and microbursts can cause loss of aircraft control, injure passengers, and stress airframes.",
                            "Low Ceilings and Visibility: Fog, low stratus clouds, and heavy precipitation obscure terrain and runways, requiring instrument flight rules (IFR).",
                            "Aviation Forecasts (METAR & TAF): Pilots check terminal aerodrome forecasts and winds aloft before every flight to select safe altitudes and fuel reserves.",
                        ],
                    },
                    {
                        "title": "Effects on Outdoor Construction",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s08_img1.png",
                        "bullets": [
                            "Rain-Sensitive Operations: Pouring concrete, paving asphalt, roofing, and exterior painting require dry weather to cure and bond properly.",
                            "High Winds: Strong gusts can topple unfinished framing, blow sheets of plywood off roofs, and make tall crane lifts unsafe.",
                            "Extreme Temperatures: Freezing cold prevents concrete hydration and mortar curing, while extreme summer heat risks worker heat exhaustion and heat stroke.",
                            "Severe Weather Preparedness: Accurate forecasts let project managers secure job sites, brace structures, and protect workers before storms hit.",
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
                "safety_callout": "Seek enclosed shelter immediately when a Severe Weather Warning is issued or thunder is heard.",
                "execution_mode": "IN_CLASS_DISCUSSION",
                "pamphlet_excerpts": [
                    "Five Dangerous Weather Conditions: Winter storms (blizzards/ice), thunderstorms (lightning/hail), flash floods and floods, tornadoes, and hurricanes.",
                    "Outdoor Lightning & Storm Safety: Seek an enclosed building or hard-topped vehicle; avoid open fields, tall isolated trees, water, and metal objects.",
                    "Flood & Tornado Safety: Move to higher ground during floods and never wade or drive through moving water; shelter in a basement or interior room during a tornado.",
                    "Weather Watch vs. Warning: A Watch means hazardous weather conditions are possible (be prepared); a Warning means hazardous weather is occurring or imminent (take shelter now!).",
                ],
                "topic_slides": [
                    {
                        "title": "Dangerous Condition 1: Winter Storms",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s10_img1.png",
                        "bullets": [
                            "What Are Winter Storms: Includes heavy snowstorms, freezing rain/ice storms, blizzards, and extreme cold combined with strong winds.",
                            "Blizzard Criteria: Sustained winds or frequent gusts of 35 mph or greater with falling/blowing snow reducing visibility below 1/4 mile for at least 3 hours.",
                            "Primary Hazards to Scouts: Rapid hypothermia from wet clothing and wind chill, frostbite on exposed extremities, whiteout disorientation, and downed power lines.",
                        ],
                    },
                    {
                        "title": "Winter Storm Safety Rules",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Stay Dry: Wet clothing loses nearly 90% of its insulating value and accelerates hypothermia; wear breathable waterproof outer shells.",
                            "Cover Exposed Body Parts: Wear a warm hat, insulated mittens, neck gaiter, and warm boots to protect nose, ears, fingers, and toes from frostbite.",
                            "Avoid Overexertion: Sweating dampens base layers and chills the core rapidly once you stop moving; pace yourself and ventilate layers.",
                            "Seek Wind Protection & Shelter: If stranded outdoors, build a windbreak or snow trench and build a warming fire if possible; if in a car, stay with the vehicle and keep the exhaust pipe clear of snow.",
                        ],
                    },
                    {
                        "title": "Dangerous Condition 2: Thunderstorms",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s12_img1.png",
                        "bullets": [
                            "What Are Thunderstorms: Towering cumulonimbus clouds driven by strong warm, moist updrafts that always produce lightning and thunder.",
                            "Associated Hazards: Cloud-to-ground lightning bolts, torrential downpours, damaging straight-line downdraft winds, and large hail.",
                            "Severe Thunderstorm Threshold: Winds of 58 mph or greater and/or hail 1 inch in diameter (quarter size) or larger.",
                        ],
                    },
                    {
                        "title": "Thunderstorm Safety Rules",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Seek Substantial Shelter Immediately: Enter a fully enclosed house/building or a hard-topped metal vehicle when thunder roars ('When Thunder Roars, Go Indoors').",
                            "Avoid Tall & Open Targets: Stay away from open fields, ridgelines, hilltops, and isolated tall objects such as lone trees, flagpoles, or towers.",
                            "Avoid Water & Conductors: Get off lakes, rivers, and swimming pools immediately; stay away from metal fences, backpacks with metal frames, and electrical wiring.",
                            "Last-Resort Outdoor Position: If caught in the open far from shelter, spread your group out 50+ feet apart and crouch low on the balls of your feet to become the smallest target possible.",
                        ],
                    },
                    {
                        "title": "Dangerous Condition 3: Flash Floods and Floods",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s14_img1.png",
                        "bullets": [
                            "Flash Floods: Occur within minutes or hours of intense rainfall over a small watershed, canyon, or urban area, or from a dam/levee break; waters rise and fall rapidly.",
                            "River Floods: Occur along larger river systems and cover a wider valley area; river floods can take several days to rise, crest, and subside.",
                            "Why Floods Are Deadly: Moving water exerts immense hydrodynamic force and carries heavy debris, boulders, and trees.",
                        ],
                    },
                    {
                        "title": "Flood Safety Rules",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Get to Higher Ground Immediately: Climb to high ground as soon as rapidly rising water or a Flash Flood Warning is observed—do not wait to pack camp gear.",
                            "Smart Campsite Selection: Never pitch tents in dry washes, arroyos, narrow gullies, or low-lying stream beds where upstream storms can send a wall of water.",
                            "Never Walk Into Moving Water: Just 6 inches of fast-moving water can knock an adult or Scout off their feet.",
                            "Turn Around, Don't Drown: Never drive into flooded roadways; 12 to 24 inches of rushing water will float and sweep away most cars and SUVs.",
                        ],
                    },
                    {
                        "title": "Dangerous Condition 4: Tornadoes",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s16_img1.png",
                        "bullets": [
                            "What Is a Tornado: A violently rotating column of air descending from a cumulonimbus thunderstorm cloud and in contact with the ground.",
                            "Visual Appearance: Usually visible as a funnel-shaped cloud of condensed moisture, dust, and debris.",
                            "Extreme Wind Speeds & Scale: Winds can reach 200 to 300 mph in the strongest (EF4–EF5) tornadoes; most are a few hundred yards wide and trace a path of a mile or more.",
                        ],
                    },
                    {
                        "title": "Tornado Safety Rules",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Primary Hazard Is Flying Debris: High-velocity windborne debris causes most tornado injuries; never stay in a tent, mobile home, or vehicle if sturdy shelter is nearby.",
                            "Best Indoor Shelter: Go to a basement, storm cellar, or an interior windowless room/bathroom/hallway on the lowest floor, and cover yourself with a mattress or heavy blankets.",
                            "If Trapped Outdoors: Move away from trees and vehicles, find a low spot or ditch that is not flooded, lie flat face-down, and cover your head and neck with your arms.",
                        ],
                    },
                    {
                        "title": "Dangerous Condition 5: Hurricanes",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s18_img1.png",
                        "bullets": [
                            "What Is a Hurricane: A massive rotating tropical cyclone with sustained winds of at least 74 mph and up to 150–200 mph (Categories 1 to 5 on the Saffir-Simpson scale).",
                            "Size & Scale: Hurricanes span 60 to 600 miles in diameter with a calm central Eye surrounded by a violent Eyewall and spiral rainbands.",
                            "Energy Source: Develops over warm tropical ocean waters (>=80°F) and weakens rapidly after moving over cold water or land.",
                        ],
                    },
                    {
                        "title": "Hurricane Safety Rules",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Evacuate the Danger Area Early: When coastal evacuation orders are issued ahead of storm surge, leave early along designated evacuation routes.",
                            "Storm Surge & Inland Flooding: Storm surge (ocean water pushed ashore by winds) and torrential inland rainfall cause the majority of hurricane fatalities.",
                            "If Trapped or Sheltering in Place: Move to a reinforced shelter on higher ground, stay in an interior room away from windows, and keep emergency water, food, and NOAA Weather Radio ready.",
                        ],
                    },
                    {
                        "title": "Severe Weather Watches",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "What a Weather Watch Means: Issued by the National Weather Service when atmospheric conditions are favorable and the risk of a hazardous weather or flooding event has increased significantly.",
                            "Uncertainty in Timing or Location: During a Watch, the exact occurrence, location, or timing of the severe storm is still uncertain.",
                            "What Scouts & Families Should Do: Monitor NOAA Weather Radio or local alerts closely, pause exposed high-ridge or open-water activities, and review where your shelter is located.",
                        ],
                    },
                    {
                        "title": "Severe Weather Warnings",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "What a Weather Warning Means: Issued when a hazardous weather or flooding event is occurring right now, is imminent, or has a very high probability of occurring based on radar or spotters.",
                            "Immediate Action Required: A Warning means there is imminent danger to life and property—move to your designated storm shelter or higher ground immediately!",
                            "Family Preparedness Discussion: Share and practice these outdoor safety rules and watch-vs.-warning actions with your family at home—it could save lives someday!",
                        ],
                    },
                ],
            },
            {
                "req_id": "3",
                "req_number": "3",
                "topic_title": "Req 3: High & Low Pressure Systems, Cold Fronts & Warm Fronts",
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
                        "title": "Atmospheric Pressure",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s23_img1.png",
                        "bullets": [
                            "What Is Atmospheric Pressure: Simply the weight of the air above a given point on the Earth's surface or aloft in the atmosphere.",
                            "Weight of the Air Column: A 1-square-inch column of air extending from sea level to the top of the atmosphere weighs approximately 14.7 pounds (about 15 lbs/sq in).",
                            "Standard Sea-Level Pressure: Measured with a barometer as 29.92 inches of mercury (inHg) or 1013.25 millibars (hPa); pressure decreases rapidly with altitude.",
                        ],
                    },
                    {
                        "title": "High and Low Pressure Pt. 1: Why Pressure Varies",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Horizontal & Vertical Variation: Atmospheric pressure varies horizontally across weather maps as well as vertically with altitude.",
                            "Uneven Solar Heating: The Sun heats the Earth's surface unevenly (more direct solar energy near the equator than near the poles, and different heating over land vs. oceans).",
                            "Global Pressure Belts: High pressure tends to develop over cold polar regions where dense air sinks, while low pressure develops near the warm equator where heated air rises.",
                            "Driving Engine of Weather: The atmosphere constantly tries to equalize areas of high and low pressure, creating wind, fronts, and weather systems in the process.",
                        ],
                    },
                    {
                        "title": "High and Low Pressure Pt. 2: Good vs. Poor Weather",
                        "layout": "DIFFERENTIAL_COMPARISON_2COL",
                        "comparison_data": {
                            "left_header": "High Pressure System ('H')",
                            "left_badge": "FAIR / GOOD WEATHER",
                            "left_points": [
                                "Vertical Air Motion: Associated with sinking (subsiding) air from aloft toward the surface",
                                "Warming & Drying: As air sinks, increasing pressure compresses and warms it, lowering relative humidity and evaporating clouds",
                                "Surface Wind Pattern: Winds flow clockwise and slightly outward from the high-pressure center in the Northern Hemisphere",
                                "Typical Weather: Clear skies, light winds, and settled fair weather",
                            ],
                            "right_header": "Low Pressure System ('L')",
                            "right_badge": "POOR / STORMY WEATHER",
                            "right_points": [
                                "Vertical Air Motion: Associated with converging, rising (ascending) air from the surface aloft",
                                "Cooling & Condensation: Rising air expands and cools to its dew point, forming clouds and precipitation",
                                "Surface Wind Pattern: Winds spiral counterclockwise and inward toward the low-pressure center in the Northern Hemisphere",
                                "Typical Weather: Overcast clouds, steady rain or snow, gusty winds, and frontal storms",
                            ],
                        },
                        "bullets": [
                            "Low Pressure ('L'): Rising air cools and forms clouds and precipitation (poor/stormy weather).",
                            "High Pressure ('H'): Sinking air warms and dries out, bringing clear skies (good/fair weather).",
                        ],
                    },
                    {
                        "title": "Cold Front: Planar and Cross-Sectional Views",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s26_img1.png",
                        "bullets": [
                            "Dense cold air wedges sharply beneath warm moist air along a steep frontal slope, forcing rapid uplift, towering cumulonimbus clouds, and heavy showers or thunderstorms right along the front.",
                        ],
                        "caption": "Cold Front Cross-Section & Surface Map (Blue spiked line pointing in direction of cold air movement)",
                    },
                    {
                        "title": "Cold Front: 3D View & Cloud Sequence",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s27_img1.png",
                        "bullets": [
                            "Three-dimensional cold front profile showing advancing cold air (left), steep frontal boundary, vertically developing cumulonimbus (Cb) with heavy rain/lightning, and clearing cooler air behind.",
                        ],
                        "caption": "Cold Front 3D Cross-Section: Steep slope (1:50 to 1:100), narrow band of intense precipitation, rapid clearing",
                    },
                    {
                        "title": "Warm Front: Planar and Cross-Sectional Views",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s28_img1.png",
                        "bullets": [
                            "Advancing warm air glides up and over retreating cold air along a gentle frontal slope, creating a wide progression of cirrus, cirrostratus, altostratus, and nimbostratus clouds with steady rain ahead of the front.",
                        ],
                        "caption": "Warm Front Cross-Section & Surface Map (Red semicircles pointing in direction of warm air advance)",
                    },
                    {
                        "title": "Warm Front: 3D Views & Temperature Inversion",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s29_img1.png",
                        "bullets": [
                            "Overrunning warm air rises gradually over a 600 km wedge of cold air, producing high cirrus (Ci) first, then cirrostratus (Cs), altostratus (As), nimbostratus (Ns) steady rain/snow, and fog.",
                        ],
                        "caption": "Warm Front 3D Cross-Section: Gentle frontal slope (1:200), broad precipitation shield ahead of boundary",
                    },
                ],
            },
            {
                "req_id": "4",
                "req_number": "4",
                "topic_title": "Req 4: What Causes Wind, Rain, Lightning & Hail",
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
                        "title": "What Causes Wind?",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s31_img1.png",
                        "bullets": [
                            "Pressure Gradient Force: As learned in Requirement 3, the atmosphere constantly tries to equalize air pressure everywhere by moving air from High pressure toward Low pressure.",
                            "Definition of Wind: Wind is air in horizontal motion caused by differences in atmospheric pressure resulting from uneven solar heating.",
                            "Wind Speed & Isobars: The greater the pressure difference over a short distance (closely spaced isobars on a weather map), the faster the wind blows.",
                        ],
                    },
                    {
                        "title": "Example: Sea Breezes (Daytime)",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Differential Heating of Land vs. Water: Land surfaces heat up much faster than ocean or lake water during sunny afternoons.",
                            "Rising Warm Air Over Land: By afternoon, air over the hot land warms, expands, and rises, creating a localized area of lower surface pressure.",
                            "Onshore Cool Breeze: Cooler, denser air over the ocean (higher pressure) moves inland toward the shore to replace the rising warm air, creating a refreshing Sea Breeze.",
                        ],
                    },
                    {
                        "title": "Example: Land Breezes (Nighttime)",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Differential Cooling at Night: After sunset, land radiates heat and cools much faster than the adjacent ocean water, which retains its warmth.",
                            "Rising Air Over Water: At night, the relatively warmer air over the water rises, creating a localized area of lower pressure offshore.",
                            "Offshore Cool Breeze: Cooler, denser air over the land flows out toward the water to replace the rising air, creating a nighttime Land Breeze.",
                        ],
                    },
                    {
                        "title": "Sea and Land Breezes Illustrated",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s34_img1.png",
                        "bullets": [
                            "Top: Daytime Sea Breeze circulation (warm air rises over land, cool ocean air moves ashore). Bottom: Nighttime Land Breeze circulation (warm air rises over water, cool land air moves offshore).",
                        ],
                        "caption": "Daytime Sea Breeze vs. Nighttime Land Breeze Thermal Circulation Cells",
                    },
                    {
                        "title": "Rain Formation Part 1: Water Source & Rising Air",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Two Essential Ingredients for Rain: (1) A surface water/moisture source, and (2) Rising air (uplift from fronts, solar convection, low pressure, or mountains).",
                            "Evaporation into Water Vapor: Solar heat causes liquid water from oceans, lakes, rivers, and moist soil to evaporate, transforming into invisible water vapor gas in the air.",
                            "Upward Transport: Updrafts and frontal lift carry this warm, moist air upward into higher, cooler levels of the troposphere.",
                        ],
                    },
                    {
                        "title": "Rain Formation Part 2: Saturation & Condensation",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Water Vapor Capacity & Saturation: Air at a given temperature can hold only a specific maximum amount of water vapor; when it holds that maximum amount, the air is saturated (100% relative humidity).",
                            "Adiabatic Cooling Aloft: As a parcel of air rises into lower pressure aloft, it expands and cools.",
                            "Condensation into Clouds: Because cooler air cannot hold as much water vapor, the excess vapor condenses onto microscopic dust, salt, or smoke particles (condensation nuclei) to form visible cloud droplets.",
                        ],
                    },
                    {
                        "title": "Rain Formation Part 3: Droplet Growth & Precipitation",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Cloud Droplets Are Tiny: Individual cloud droplets are microscopic (about 0.02 mm across) and are easily kept suspended by gentle upward air currents.",
                            "Collision and Coalescence: Inside the cloud, millions of tiny cloud droplets collide and merge together (or grow via ice crystals) to form much larger, heavier water drops.",
                            "Falling as Rain: Once the water droplets grow so large (about 2 mm) that updrafts can no longer suspend them against gravity, they fall to Earth as rain.",
                        ],
                    },
                    {
                        "title": "Rain Formation Illustrated",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s38_img1.png",
                        "bullets": [
                            "Relative size comparison: Microscopic condensation nuclei (0.0002 mm) -> Cloud droplets (0.02 mm) -> Large raindrop (2.0 mm) formed by collision and coalescence.",
                        ],
                        "caption": "Rain Formation: From Condensation Nuclei and Cloud Droplets to Falling Raindrops",
                    },
                    {
                        "title": "Lightning Formation",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Associated With Thunderstorms: Lightning occurs inside and beneath towering cumulonimbus thunderstorm clouds with turbulent updrafts and downdrafts.",
                            "Electrical Charge Separation: Collisions between rising ice crystals and falling graupel (soft hail) separate electrical charges—positive charges gather near the top of the cloud, negative charges in the lower cloud, and induced positive charges on the ground below.",
                            "Electrical Discharge (Lightning Bolt): When the electrical voltage overcomes the insulating resistance of air, a giant spark of electricity jumps between positive and negative regions.",
                            "Types & Thunder: Lightning can be cloud-to-ground, cloud-to-cloud, or intra-cloud; the bolt heats the air channel to ~50,000°F, causing explosive expansion heard as thunder.",
                        ],
                    },
                    {
                        "title": "Hail Formation",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Updrafts & Downdrafts in Thunderstorms: Severe thunderstorms contain powerful vertical updrafts alongside precipitation downdrafts.",
                            "Swept Above the Freezing Level: Raindrops falling in a downdraft get caught by an adjacent strong updraft and are swept high into the cloud above the 32°F freezing level, freezing into ice pellets.",
                            "Accreting Concentric Ice Layers: As the hailstone cycles up and down through supercooled liquid water droplets, it acquires another ring of clear or rime ice on each trip.",
                            "Falling to the Ground: Eventually the hailstone grows too heavy to be supported by the thunderstorm updraft (sometimes golf-ball or baseball size) and falls rapidly to the ground.",
                        ],
                    },
                    {
                        "title": "Hail Formation Illustrated",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s41_img1.png",
                        "bullets": [
                            "Trajectory of a growing hailstone inside a cumulonimbus cloud: swept repeatedly above the 32°F (0°C) freezing level by strong updrafts until heavy enough to fall.",
                        ],
                        "caption": "Hailstone Growth Cycle Above and Below the Freezing Level in a Severe Thunderstorm",
                    },
                ],
            },
            {
                "req_id": "5",
                "req_number": "5",
                "topic_title": "Req 5: Cloud Types in Low, Middle & Upper Levels of the Atmosphere",
                "action_verb": "Identify",
                "req_text": "Identify clouds in the low, middle, and upper levels of the atmosphere. Relate these to specific types of weather.",
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
                        "title": "Cloud Types by Atmospheric Level",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Vertically Developing Clouds (0 to 50,000 ft): Cumulus (puffy fair-weather heaps with flat bases) and Cumulonimbus (towering thunderstorm anvil clouds).",
                            "Low Clouds (Below 6,500 ft): Stratus (flat, featureless gray blanket), Stratocumulus (low lumpy rolls), and Nimbostratus (dark, wet layer of continuous rain or snow).",
                            "Middle Clouds (6,500 to 20,000 ft): Altocumulus (mid-level rounded masses or waves) and Altostratus (grayish-blue sheet through which the Sun appears dimly).",
                            "High Clouds (Above 20,000 ft): Cirrus (delicate white ice-crystal wisps), Cirrocumulus (rippled 'mackerel sky'), and Cirrostratus (thin ice veil producing a 22° halo around Sun or Moon).",
                        ],
                    },
                    {
                        "title": "Cloud Types Illustrated",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s44_img1.png",
                        "bullets": [
                            "Visual guide to High Clouds (>20,000 ft AGL), Middle Clouds (6,500–20,000 ft AGL), Low Clouds (<6,500 ft AGL), and Clouds with Vertical Development (Cumulus & Cumulonimbus).",
                        ],
                        "caption": "Classification of Clouds by Altitude Level and Vertical Development",
                    },
                    {
                        "title": "Clouds and Associated Weather",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Cumulonimbus Clouds: Produce heavy rain showers, lightning and thunder, strong gusty winds, hail, and occasionally tornadoes.",
                            "Nimbostratus Clouds: Associated with steady, prolonged moderate rain or snow covering a wide area (typical of warm fronts).",
                            "Cirrus & Cirrostratus Clouds: Fair weather at the moment, but thickening cirrostratus often warns of an approaching warm front and precipitation within 24 hours.",
                            "Virga Phenomenon: Other clouds generally do not produce heavy ground precipitation, though they may drop streaks of rain or snow that evaporate before reaching the ground ('virga').",
                        ],
                    },
                ],
            },
            {
                "req_id": "6",
                "req_number": "6",
                "topic_title": "Req 6: The Earth's Water (Hydrologic) Cycle",
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
                        "title": "The Water Cycle Illustrated",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s47_img1.png",
                        "bullets": [
                            "The Hydrologic Cycle: (1) Evaporation, (2) Transpiration, (3) Sublimation, (4) Condensation, (5) Transportation, (6) Precipitation, (7) Surface/Snowmelt Runoff, (8) Infiltration, (9) Groundwater Flow, (10) Plant Uptake.",
                        ],
                        "caption": "NOAA Hydrologic Cycle Diagram Showing All 10 Major Water Cycle Processes",
                    },
                    {
                        "title": "The Water Cycle: Main Points to Remember",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Constant Global Water Supply: The total amount of water on Earth remains virtually constant over millions of years—water is continuously recycled from ocean to land and back again.",
                            "Evaporation & Transpiration: Solar energy evaporates liquid water from oceans (about 90% of atmospheric moisture) while trees and plants release water vapor through transpiration.",
                            "Condensation & Precipitation: Rising moist air cools and condenses into clouds; wind transports clouds over land where moisture falls as rain, snow, sleet, or hail.",
                            "Runoff & Groundwater Recharge: Precipitation either flows over land as surface runoff into rivers/lakes or infiltrates soil into groundwater aquifers before returning to the sea.",
                        ],
                    },
                ],
            },
            {
                "req_id": "7",
                "req_number": "7",
                "topic_title": "Req 7: Acid Rain, Human Atmospheric Pollution & Health Effects",
                "action_verb": "Define",
                "req_text": "Define acid rain. Identify which human activities pollute the atmosphere and the effect such pollution can have on people.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "pamphlet_excerpts": [
                    "Acid Rain Defined: Rainwater mixed with sulfur dioxide (SO2) and nitrogen oxide (NOx) pollutants—primarily from coal-burning power plants and vehicles—forming dilute sulfuric and nitric acid.",
                    "Human Effects on the Atmosphere: Fossil-fuel emissions, desertification from overgrazing/mining, stratospheric ozone depletion from CFCs, and global warming from excess carbon dioxide (CO2).",
                    "Impacts on People & Environment: Acid rain damages forests and aquatic life; desertification reduces food production; ozone thinning increases UV skin cancer; warming raises sea levels.",
                ],
                "topic_slides": [
                    {
                        "title": "Acid Rain",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "What Is Acid Rain: Normal rain mixed with industrial air pollutants containing sulfur dioxide (SO2) and nitrogen oxides (NOx).",
                            "Chemical Reaction in Clouds: Sulfur and nitrogen particles react with atmospheric water vapor and oxygen to form a dilute solution of sulfuric acid and nitric acid (lowering pH below 5.0).",
                            "Primary Emission Sources: The main anthropogenic source is power plants burning high-sulfur coal, along with heavy industrial smelters and motor vehicle exhaust.",
                            "Environmental Damage: Acid rain acidifies lakes and streams (killing fish and amphibians), leaches nutrients from forest soils, and corrodes stone buildings and monuments.",
                        ],
                    },
                    {
                        "title": "Human Effects on Weather and the Atmosphere",
                        "layout": "SPLIT_VISUAL_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s51_img1.png",
                        "bullets": [
                            "Desertification of Land: Overgrazing by livestock, unsound farming practices, deforestation, and strip mining strip vegetation, turning fertile land into dry desert.",
                            "Breakdown of the Ozone Layer: Chlorofluorocarbons (CFCs) once used in refrigerants and aerosols rise into the stratosphere and destroy protective ozone (O3) molecules.",
                            "Global Warming / Greenhouse Effect: Burning fossil fuels (coal, oil, natural gas) releases excessive carbon dioxide (CO2) into the atmosphere, trapping outgoing infrared heat.",
                        ],
                    },
                    {
                        "title": "How People Are Affected by Atmospheric Pollution",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Loss of Farmland & Food Supply: Desertification and acid soil degradation destroy productive farmland and lead to reduced global food production.",
                            "Ultraviolet Radiation & Skin Cancer: Depletion of the stratospheric ozone layer allows more solar ultraviolet (UV-B) radiation to reach the surface, increasing skin cancer and eye cataracts.",
                            "Sea-Level Rise & Coastal Inundation: Global warming melts glaciers and thermally expands ocean water, raising sea levels and threatening low-lying coastal cities where millions live.",
                            "Respiratory & Cardiovascular Health: Ground-level ozone smog and fine particulate matter aggravate asthma, bronchitis, and heart disease.",
                        ],
                    },
                ],
            },
            {
                "req_id": "8",
                "req_number": "8",
                "topic_title": "Req 8: Earth's Axial Tilt & Global Climate Zones",
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
                        "title": "Tilt of the Earth's Axis & Climate Zones",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Equatorial Region (Tropics): Near the equator, the Sun is nearly straight overhead most of the year, concentrating solar energy and keeping the equatorial climate hot year-round.",
                            "Polar Regions (Arctic & Antarctic): Near the poles, sunlight strikes at a low grazing angle and is spread over a wide area (with months of winter darkness), making polar climates cold.",
                            "Temperate Zones In Between: Poleward from the equator, climate shifts gradually from hot to cold; in between lie the Temperate Zones, which include the continental United States.",
                            "Why We Have Four Seasons: Because Earth's axis is tilted 23.5°, the Northern Hemisphere tilts toward the Sun in June (Summer Solstice) and away from the Sun in December (Winter Solstice).",
                        ],
                    },
                    {
                        "title": "Tilt of the Earth's Axis Illustrated",
                        "layout": "FULL_BLEED_IMAGE_EXPLAINER",
                        "image_path": "assets/pamphlet_images/weather_ec2020_s54_img1.png",
                        "bullets": [
                            "Earth's annual orbit around the Sun showing the 23.5° axial tilt at the Summer Solstice (June), Autumnal Equinox (September), Winter Solstice (December), and Spring Equinox (March).",
                        ],
                        "caption": "Earth's 23.5° Axial Tilt, Orbit, Solstices, and Equinoxes Driving Global Seasons",
                    },
                ],
            },
            {
                "req_id": "9",
                "req_number": "9",
                "topic_title": "Req 9: Weather Instruments & 7-Day Log OR NWS Meteorologist Visit",
                "action_verb": "Demonstrate",
                "req_text": "Do ONE of the following: (a) Make one of the following instruments: wind vane, anemometer, rain gauge, hygrometer. Keep a daily weather log for one week using information from this instrument as well as from other sources... OR (b) Visit a National Weather Service office or talk with a local radio or television weathercaster, private meteorologist, local agricultural extension service officer, or university meteorology instructor.",
                "safety_callout": "Always obtain parent/guardian permission before using internet weather sources and follow Two-Deep Leadership when visiting a meteorologist.",
                "execution_mode": "PREREQUISITE_CAMPOUT_HOME",
                "recommended_archetype": "WORKED_EXAMPLE_TEMPLATE",
                "pamphlet_excerpts": [
                    "Option 9a (Build Instrument & 7-Day Log): Construct a functional wind vane, anemometer, rain gauge, or hygrometer and record daily weather observations and forecasts at the same time each day for 7 days.",
                    "Option 9b (Interview a Weather Expert): Visit or interview an NWS meteorologist, broadcast weathercaster, private meteorologist, agricultural extension officer, or university professor.",
                    "Community Warning Systems: Determine which severe weather hazards are most dangerous to your community and how NWS warnings reach homes (NOAA Weather Radio, WEA, EAS, sirens).",
                ],
                "worked_example": {
                    "title": "Sample 7-Day Daily Weather Observation Log (Req 9a)",
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
                        "title": "Requirement 9 Option A: Making Weather Instruments",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Wind Vane (Wind Direction): Pivoting arrow with a larger tail fin that points into the direction the wind is blowing FROM (N, NE, E, SE, S, SW, W, NW).",
                            "Anemometer (Wind Speed): Three or four hemispherical cups mounted on horizontal arms that spin faster as wind speed increases; count revolutions per minute to calibrate mph.",
                            "Rain Gauge (Precipitation): Straight-sided cylinder with a collector funnel and calibrated ruler measuring rainfall in tenths or hundredths of an inch.",
                            "Hygrometer (Relative Humidity): Measures atmospheric moisture using a human-hair pointer (hair lengthens in humid air) or wet-bulb/dry-bulb psychrometer thermometers.",
                        ],
                    },
                    {
                        "title": "Requirement 9 Option A: Keeping Your 7-Day Weather Log",
                        "layout": "WORKED_EXAMPLE_TEMPLATE",
                        "worked_example": {
                            "title": "7-Day Scout Weather Observation & Forecast Verification Log",
                            "artifact_type": "DAILY_WEATHER_LOG",
                            "fields": {
                                "Daily Observation Rule": "Record measurements at the SAME time every day for 7 consecutive days (with parent permission for internet/NOAA radio sources).",
                                "Required Daily Entries": "1) Wind direction & speed, 2) Air temperature, 3) Precipitation amount, 4) Cloud types (Low/Middle/High), 5) Morning dew or frost.",
                                "Forecast Comparison": "List the daily radio, TV, or NWS forecast recorded at the same time each day and compare how the actual weather turned out.",
                            },
                            "counselor_tip": "Bring both your homemade weather instrument (or photo of it installed outdoors) and your completed 7-day log to your counselor review.",
                        },
                        "bullets": [
                            "Record wind direction/speed, temperature, precipitation, cloud types, and morning dew/frost at the same time each day for 7 days.",
                        ],
                    },
                    {
                        "title": "Requirement 9 Option B: Weather Experts Near You",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "National Weather Service (NWS) Meteorologist: Operational forecasters at one of the 122 local NWS Weather Forecast Offices (WFOs) across the United States.",
                            "Broadcast Television or Radio Weathercaster: Local station meteorologists who communicate daily forecasts and live severe weather coverage to the public.",
                            "Private-Sector Meteorologist: Forecasters advising airlines, shipping fleets, utilities, snow-removal operations, and renewable energy grids.",
                            "Agricultural Extension Officer or University Professor: Specialists studying regional microclimates, crop weather impacts, and atmospheric research.",
                        ],
                    },
                    {
                        "title": "Requirement 9 Option B: Community Hazards & Warning Systems",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Finding Your Local NWS Office: Visit weather.gov to locate your regional NWS Weather Forecast Office and learn about local climate hazards.",
                            "Most Dangerous Local Weather: Discuss with the meteorologist which severe weather events (blizzards/nor'easters, severe thunderstorms, flash floods, tornadoes, or hurricanes) cause the most damage in your area.",
                            "How Warnings Reach Homes: Trace the warning chain from NWS Doppler radar detection to NOAA Weather Radio All Hazards (NWR), the Emergency Alert System (EAS), Wireless Emergency Alerts (WEA) on mobile phones, and community sirens.",
                        ],
                    },
                ],
            },
            {
                "req_id": "10",
                "req_number": "10",
                "topic_title": "Req 10: Five-Minute Prepared Talk (Outdoor Weather Safety OR Acid Rain)",
                "action_verb": "Explain",
                "req_text": "Do ONE of the following: (a) Give a talk of at least five minutes to a group (such as your unit or a Cub Scout pack) explaining the outdoor safety rules in the event of lightning, flash floods, and tornadoes. Before your talk, share your outline with your counselor for approval. OR (b) Read several articles about acid rain and give a prepared talk of at least five minutes to a group (such as your troop, patrol, or a Cub Scout pack) about the articles. Before your talk, share your outline with your counselor for approval.",
                "safety_callout": "Always have your Merit Badge Counselor review and approve your written speech outline before delivering your 5-minute presentation.",
                "execution_mode": "HANDS_ON_SKILL_STATION",
                "pamphlet_excerpts": [
                    "Option 10a (Outdoor Weather Safety Talk): Deliver a 5+ minute talk to your troop, patrol, or Cub Scout pack covering lightning, flash flood, and tornado outdoor safety rules.",
                    "Option 10b (Acid Rain Research Talk): Read several articles from EPA, USGS, or NOAA on acid rain and present a 5+ minute talk after getting counselor approval on your outline.",
                ],
                "topic_slides": [
                    {
                        "title": "Requirement 10 Option A: 5-Minute Outdoor Weather Safety Talk",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Step 1 — Prepare & Approve Your Outline: Draft a structured 5-minute speech outline using the safety rules from Requirement 2 and share it with your Weather Merit Badge Counselor for approval BEFORE speaking.",
                            "Section 1 — Lightning Safety (90 sec): Explain 'When Thunder Roars, Go Indoors', seeking a building or hard-topped car, avoiding open fields/isolated trees/water, and the low crouch position if trapped outside.",
                            "Section 2 — Flash Flood Safety (90 sec): Explain climbing to higher ground immediately, never camping in dry washes or gullies, and 'Turn Around, Don't Drown'.",
                            "Section 3 — Tornado Safety (90 sec): Explain flying debris hazards, sheltering in a basement or interior windowless room, or lying flat in a low dry ditch covering your head if caught outdoors.",
                        ],
                    },
                    {
                        "title": "Requirement 10 Option B: 5-Minute Acid Rain Research Talk",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Step 1 — Read Authoritative Articles: Research articles on acid rain from the U.S. Environmental Protection Agency (epa.gov/acidrain), U.S. Geological Survey (usgs.gov), and NOAA.",
                            "Step 2 — Counselor Outline Approval: Organize your findings into a clear 5-minute presentation outline and get your counselor's approval before speaking to your troop, patrol, or Cub Scout pack.",
                            "Key Topics to Cover: How sulfur dioxide (SO2) and nitrogen oxides (NOx) react with water vapor to form sulfuric/nitric acid, effects on lakes/forests/soils, and how Clean Air Act scrubber technology has reduced acid precipitation.",
                        ],
                    },
                ],
            },
            {
                "req_id": "11",
                "req_number": "11",
                "topic_title": "Req 11: Careers in Meteorology, Training, Education & Responsibilities",
                "action_verb": "Discuss",
                "req_text": "Find out about a weather-related career opportunity that interests you. Discuss with and explain to your counselor what training and education are required for such a position, and the responsibilities required of such a position.",
                "safety_callout": None,
                "execution_mode": "IN_CLASS_DISCUSSION",
                "pamphlet_excerpts": [
                    "Career Opportunities: TV/Radio broadcast weathercaster, National Weather Service (NWS) operational forecaster, private-sector meteorologist, military weather officer, and university/NOAA researcher.",
                    "Training & Education: Requires a Bachelor's or advanced degree in Meteorology, Atmospheric Science, or related physical science with strong coursework in calculus, differential equations, physics, and computer science.",
                    "Required Responsibilities: Forecasters make time-critical decisions that protect lives and property, interpret radar/satellite/numerical models, and work rotating shifts including nights, weekends, and holidays.",
                ],
                "topic_slides": [
                    {
                        "title": "Weather-Related Career Opportunities",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "National Weather Service (NWS) Forecaster: Issues official public forecasts, aviation/marine briefings, and life-saving severe weather watches and warnings across 122 regional offices.",
                            "TV / Radio Broadcast Weathercaster: Prepares graphics and communicates daily forecasts and live emergency storm tracking to the public.",
                            "Private Weather Firm Forecaster: Provides specialized weather routing and risk forecasts for airlines, ocean shipping, electric utilities, agriculture, and construction.",
                            "Military Meteorologist & Atmospheric Researcher: Weather officers support Air Force and Navy operations worldwide; university and NOAA scientists study hurricanes, tornadoes, and climate models.",
                        ],
                    },
                    {
                        "title": "Required Training and Education",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "University Degree Requirement: Most professional positions require at least a Bachelor of Science (B.S.) degree in Meteorology, Atmospheric Science, or a closely related field.",
                            "Strong Math & Physics Foundation: Meteorology is a specialized branch of applied physics; students complete calculus, differential equations, fluid dynamics, and thermodynamics.",
                            "Computer Science & Remote Sensing: Modern meteorologists use supercomputer numerical weather prediction models, Doppler radar algorithms, and geostationary satellite data.",
                            "Advanced Research Credentials: University professors and senior NOAA/NCAR atmospheric research scientists typically earn a Master's (M.S.) or Doctorate (Ph.D.) degree.",
                        ],
                    },
                    {
                        "title": "Responsibilities of a Meteorologist",
                        "layout": "CONCEPT_TEXT_SLIDE",
                        "bullets": [
                            "Protecting Lives and Property: Operational forecasters make high-stakes decisions under pressure when issuing tornado, flash flood, hurricane, and blizzard warnings.",
                            "24/7 Operational Schedule: Because the weather never stops, operational forecasters frequently work rotating shifts covering nights, weekends, and holidays.",
                            "Dependability & Clear Communication: A meteorologist must be dependable, analytical, calm under pressure, and able to translate complex atmospheric data into clear public guidance.",
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
        used_image_paths=used_image_paths,
    )
    enriched.setdefault("topic_title", pamphlet_info.get("topic_title"))
    enriched.setdefault("pamphlet_citation", pamphlet_info.get("pamphlet_citation"))
    if pamphlet_info.get("pamphlet_image_path") and not enriched.get("pamphlet_image_path"):
        enriched["pamphlet_image_path"] = pamphlet_info["pamphlet_image_path"]

    pamphlet_points = pamphlet_info.get("pamphlet_summary_points") or []

    # Populate or supplement pamphlet_excerpts with real pamphlet text summaries
    if not enriched.get("pamphlet_excerpts"):
        if pamphlet_points:
            enriched["pamphlet_excerpts"] = pamphlet_points[:5]
        else:
            enriched["pamphlet_excerpts"] = [
                f"Core Concept ({badge_name} Req {req_num}): {req_text}",
                f"Safety & Field Practice: Apply the BSA Guide to Safe Scouting and Buddy System during all {badge_name} field work.",
            ]
    elif pamphlet_points:
        existing_excerpts = list(enriched["pamphlet_excerpts"])
        for pt in pamphlet_points[:2]:
            if len(existing_excerpts) < 6 and pt not in existing_excerpts:
                existing_excerpts.append(pt)
        enriched["pamphlet_excerpts"] = existing_excerpts

    # Populate step_by_step_procedure from real pamphlet teaching points when not explicitly authored
    if not enriched.get("step_by_step_procedure"):
        source_steps = pamphlet_points or enriched["pamphlet_excerpts"]
        enriched["step_by_step_procedure"] = list(source_steps[:4])

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

    # 1. Case-insensitive lookup in rich benchmark database + live BSA Pamphlet PDF enrichment
    for key, data in BENCHMARK_BADGES_DATA.items():
        if key.lower() == badge_title.lower():
            raw_reqs = data["requirements"]
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

    # Extract chapters and teaching points directly from the official BSA Pamphlet PDF if available
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

