"""Configuration, immutable Scouts BSA Constitution, and official brand constants.

This module defines the foundational persona, Guide to Safe Scouting policies,
Eagle-Required taxonomy, and official Scouts BSA visual branding palettes to enforce
rubric criteria for Robust System Instructions (Context & Memory) and Brand Compliance.
"""

from typing import List, Dict, Set

# ==============================================================================
# SCOUTS BSA CONSTITUTION & PERSONA (ROBUST SYSTEM INSTRUCTIONS)
# ==============================================================================

SCOUTS_BSA_CONSTITUTION = """
You are the official Scouts BSA Merit Badge Counselor Assistant AI.
Your constitution and mandatory operating rules are:
1. YOUTH PROTECTION & SAFETY FIRST: Every presentation must adhere strictly to the
   BSA Guide to Safe Scouting. Never recommend or generate activities that violate
   BSA safety rules (e.g., unauthorized tools, uncertified water activities).
2. 100% REQUIREMENT COVERAGE: Every single requirement and sub-requirement of the
   target merit badge must be explicitly covered in the presentation slide deck.
3. PEDAGOGICAL SCANNABILITY: Slides must be clear, engaging, and readable for both
   youth Scouts and adult leaders. Never exceed 7 bullet points per slide.
4. BRAND COMPLIANCE: Use only official Scouts BSA colors and iconography.
5. SOURCE TRACEABILITY: Always reference official BSA Downloadable Pamphlets and
   Digital Resource Guides (DRGs) from Scouting.org.
"""

# ==============================================================================
# OFFICIAL SCOUTS BSA BRAND PALETTES (HEX CODES & RGB)
# ==============================================================================

class ScoutsBSAPalette:
    """Official Scouts BSA brand color palette constants."""
    NAVY_BLUE_HEX: str = "#003F87"
    NAVY_BLUE_RGB: tuple = (0, 63, 135)
    
    ACTION_BLUE_HEX: str = "#005AE0"
    ACTION_BLUE_RGB: tuple = (0, 90, 224)
    
    WARM_OLIVE_HEX: str = "#4B5320"
    WARM_OLIVE_RGB: tuple = (75, 83, 32)
    
    EAGLE_RED_HEX: str = "#CE1126"
    EAGLE_RED_RGB: tuple = (206, 17, 38)
    
    EAGLE_GOLD_HEX: str = "#F4C430"
    EAGLE_GOLD_RGB: tuple = (244, 196, 48)
    
    CRISP_SLATE_HEX: str = "#F2F4F7"
    CRISP_SLATE_RGB: tuple = (242, 244, 247)
    
    DARK_TEXT_HEX: str = "#212121"
    DARK_TEXT_RGB: tuple = (33, 33, 33)
    
    WHITE_HEX: str = "#FFFFFF"
    WHITE_RGB: tuple = (255, 255, 255)

# ==============================================================================
# EAGLE-REQUIRED MERIT BADGES TAXONOMY
# ==============================================================================

EAGLE_REQUIRED_BADGES: Set[str] = {
    "First Aid",
    "Citizenship in the Community",
    "Citizenship in the Nation",
    "Citizenship in the World",
    "Citizenship in Society",
    "Communication",
    "Cooking",
    "Personal Fitness",
    "Emergency Preparedness",
    "Lifesaving",
    "Environmental Science",
    "Sustainability",
    "Personal Management",
    "Swimming",
    "Hiking",
    "Cycling",
    "Camping",
    "Family Life",
}

def is_eagle_required(badge_name: str) -> bool:
    """Returns True if the badge is one of the 14+ Eagle-Required merit badges.
    
    Args:
        badge_name: Name of the merit badge to check.
        
    Returns:
        bool: True if badge is Eagle-required, False otherwise.
    """
    cleaned_name = badge_name.strip().title()
    for req_badge in EAGLE_REQUIRED_BADGES:
        if req_badge.lower() == cleaned_name.lower():
            return True
    return False

# ==============================================================================
# PRESENTATION DEPTH SETTINGS
# ==============================================================================

PRESENTATION_DEPTH_CONFIGS: Dict[str, Dict[str, int]] = {
    "Standard Deck": {
        "min_slides_per_req": 1,
        "max_slides_per_req": 2,
        "include_troop_activities": False,
        "include_guide_to_safe_scouting": True,
    },
    "Deep Dive / Camp School Deck": {
        "min_slides_per_req": 2,
        "max_slides_per_req": 4,
        "include_troop_activities": True,
        "include_guide_to_safe_scouting": True,
    },
}
