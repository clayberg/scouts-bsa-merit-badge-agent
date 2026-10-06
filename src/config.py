"""Configuration, immutable Scouts BSA Constitution, Material 3 Expressive tokens, and official brand constants.

This module defines the foundational persona, Guide to Safe Scouting policies,
Eagle-Required taxonomy, 12-Archetype Slide Engine rules, 7 Golden Rules of Slide
Copywriting, and official Scouts BSA + Material 3 Expressive visual branding palettes.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
ASSETS_DIR = PROJECT_ROOT / "assets"
GENERATED_DIAGRAMS_DIR = ASSETS_DIR / "diagrams"
BADGE_IMAGE_CATALOG_DIR = ASSETS_DIR / "badge_image_catalog"
GENERATED_DECKS_DIR = PROJECT_ROOT / "deliverables"
LOCAL_CACHE_DIR = PROJECT_ROOT / ".cache"

# Ensure directories exist
GENERATED_DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)
BADGE_IMAGE_CATALOG_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_DECKS_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# SCOUTS BSA CONSTITUTION & PERSONA (ROBUST SYSTEM INSTRUCTIONS)
# ==============================================================================

SCOUTS_BSA_CONSTITUTION = """
You are the official Scouts BSA Merit Badge Counselor Assistant AI.
Your constitution and mandatory operating rules are:
1. YOUTH PROTECTION & SAFETY FIRST: Every presentation must adhere strictly to the
   BSA Guide to Safe Scouting and Scouter Code of Conduct (Two-Deep Leadership,
   No One-on-One Contact, Buddy System). Never recommend or generate activities that
   violate BSA safety rules (e.g., unauthorized tools, uncertified water activities).
2. 100% SUB-REQUIREMENT COVERAGE & EXECUTION TRIAGE: Every single requirement and
   sub-requirement (1a, 1b, 2a, 2b1, etc.) of the target merit badge must be
   explicitly covered and classified into its execution mode:
   - IN_CLASS_DISCUSSION (Explain / Discuss / Describe)
   - HANDS_ON_SKILL_STATION (Demonstrate / Show / Practice using BSA EDGE Method)
   - PREREQUISITE_CAMPOUT_HOME (Campout / Home Log / Civic Visit / Bring Proof)
3. 12-ARCHETYPE VISUAL DIVERSITY & 7 GOLDEN RULES OF COPYWRITING:
   - Never emit a deck of identical bullet slides. Select from the 12 semantic
     slide archetypes (Split Visual Explainer, 4-Card Step-by-Step Procedure,
     2-Column Differential Comparison, Decision Tree Flow, Spatial Field Diagram,
     Worked Example Template, Gear Checklist Grid, Hands-On Practice Station,
     Socratic Checkpoint Quiz, Requirements Triage Matrix, Section Divider, Cover Hero).
   - Never truncate requirement text with ellipses ('...').
   - Never embed literal bullet characters ('•', '-', '*') inside text strings.
   - Start every card/point with a 2-4 word bold anchor phrase.
   - Enforce <= 7 points per slide, <= 8 paragraphs per text frame, and zero AABB shape overlaps.
4. BRAND & WCAG CONTRAST COMPLIANCE: Use official Scouts BSA colors (Navy Blue #003F87,
   Action Blue #005AE0, Warm Olive #4B5320, Eagle Red #CE1126, Eagle Gold #F4C430) with
   >= 4.5:1 WCAG contrast ratio and >= 13pt minimum font floor.
5. SOURCE TRACEABILITY & SPEAKER CADENCE: Reference official BSA Downloadable Pamphlets,
   scouting.org requirement hubs, and Digital Resource Guides (DRGs). Format speaker notes
   with [SAY], [DEMONSTRATE], and [ASK SCOUTS] tags using conversational breath units
   (<= 16 words per clause, zero em-dashes).
"""


def load_prompt_manifest() -> Dict[str, object]:
    """Loads the versioned prompt manifest (`prompts/manifest.json`) with SHA-256 integrity hashes."""
    import hashlib
    import json

    manifest_path = PROMPTS_DIR / "manifest.json"
    manifest: Dict[str, object] = {"schema_version": "1.0.0", "prompts": {}}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    prompts_meta = manifest.get("prompts", {})
    if isinstance(prompts_meta, dict):
        for fname, entry in prompts_meta.items():
            fpath = PROMPTS_DIR / fname
            if isinstance(entry, dict) and fpath.exists():
                entry["sha256"] = hashlib.sha256(fpath.read_bytes()).hexdigest()[:16]
    return manifest


def load_prompt(
    prompt_filename: str,
    fallback: str = "",
    variant: str = "control",
) -> str:
    """Loads an externalized Markdown prompt from `prompts/`, supporting A/B variant selection."""
    manifest = load_prompt_manifest()
    prompts_meta = manifest.get("prompts", {})
    resolved_filename = prompt_filename
    if isinstance(prompts_meta, dict) and prompt_filename in prompts_meta:
        entry = prompts_meta[prompt_filename]
        if isinstance(entry, dict):
            variants = entry.get("ab_variants", {})
            if isinstance(variants, dict) and variant in variants:
                resolved_filename = str(variants[variant])

    prompt_path = PROMPTS_DIR / resolved_filename
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return fallback or SCOUTS_BSA_CONSTITUTION



# ==============================================================================
# OFFICIAL SCOUTS BSA BRAND PALETTES & MATERIAL 3 EXPRESSIVE TOKENS
# ==============================================================================

class ScoutsBSAPalette:
    """Official Scouts BSA brand color palette constants & Material 3 Expressive tokens."""
    NAVY_BLUE_HEX: str = "#003F87"
    NAVY_BLUE_RGB: tuple = (0, 63, 135)

    ACTION_BLUE_HEX: str = "#005AE0"
    ACTION_BLUE_RGB: tuple = (0, 90, 224)

    WARM_OLIVE_HEX: str = "#4B5320"
    WARM_OLIVE_RGB: tuple = (75, 83, 32)

    FOREST_GREEN_HEX: str = "#1B4D3E"
    FOREST_GREEN_RGB: tuple = (27, 77, 62)

    EAGLE_RED_HEX: str = "#CE1126"
    EAGLE_RED_RGB: tuple = (206, 17, 38)

    EAGLE_GOLD_HEX: str = "#F4C430"
    EAGLE_GOLD_RGB: tuple = (244, 196, 48)

    CRISP_SLATE_HEX: str = "#F2F4F7"
    CRISP_SLATE_RGB: tuple = (242, 244, 247)

    SOFT_BLUE_CARD_HEX: str = "#E8F0FE"
    SOFT_BLUE_CARD_RGB: tuple = (232, 240, 254)

    SOFT_OLIVE_CARD_HEX: str = "#F1F4E8"
    SOFT_OLIVE_CARD_RGB: tuple = (241, 244, 232)

    SOFT_GOLD_CARD_HEX: str = "#FFF8E1"
    SOFT_GOLD_CARD_RGB: tuple = (255, 248, 225)

    SOFT_RED_CARD_HEX: str = "#FDECEA"
    SOFT_RED_CARD_RGB: tuple = (253, 236, 234)

    BORDER_GRAY_HEX: str = "#CBD5E1"
    BORDER_GRAY_RGB: tuple = (203, 213, 225)

    MUTED_TEXT_HEX: str = "#475569"
    MUTED_TEXT_RGB: tuple = (71, 85, 105)

    DARK_TEXT_HEX: str = "#212121"
    DARK_TEXT_RGB: tuple = (33, 33, 33)

    WHITE_HEX: str = "#FFFFFF"
    WHITE_RGB: tuple = (255, 255, 255)


MATERIAL_3_EXPRESSIVE_TOKENS: Dict[str, str] = {
    "--md-sys-color-primary": "#003F87",
    "--md-sys-color-on-primary": "#FFFFFF",
    "--md-sys-color-primary-container": "#D6E3FF",
    "--md-sys-color-on-primary-container": "#001B3E",
    "--md-sys-color-secondary": "#4B5320",
    "--md-sys-color-on-secondary": "#FFFFFF",
    "--md-sys-color-secondary-container": "#DCE7C8",
    "--md-sys-color-on-secondary-container": "#141E00",
    "--md-sys-color-tertiary": "#CE1126",
    "--md-sys-color-on-tertiary": "#FFFFFF",
    "--md-sys-color-tertiary-container": "#FFDAD6",
    "--md-sys-color-on-tertiary-container": "#410004",
    "--md-sys-color-gold-accent": "#F4C430",
    "--md-sys-color-surface": "#F8FAFC",
    "--md-sys-color-surface-container-low": "#F1F5F9",
    "--md-sys-color-surface-container": "#E2E8F0",
    "--md-sys-color-surface-container-high": "#CBD5E1",
    "--md-sys-color-on-surface": "#0F172A",
    "--md-sys-color-on-surface-variant": "#475569",
    "--md-sys-shape-corner-extra-large": "28px",
    "--md-sys-shape-corner-large": "20px",
    "--md-sys-shape-corner-medium": "14px",
}


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
    """Returns True if the badge is one of the 18 Eagle-Required merit badges.

    Args:
        badge_name: Name of the merit badge to check.

    Returns:
        bool: True if badge is Eagle-required, False otherwise.
    """
    if not badge_name or not isinstance(badge_name, str):
        return False
    cleaned_name = badge_name.strip().title()
    for req_badge in EAGLE_REQUIRED_BADGES:
        if req_badge.lower() == cleaned_name.lower():
            return True
    return False


# ==============================================================================
# COMPLETE CATALOG OF ALL 138 OFFICIAL SCOUTS BSA MERIT BADGES
# ==============================================================================

_RAW_MERIT_BADGE_CATALOG: List[tuple] = [
    # 18 Eagle-Required Merit Badges
    ("Camping", "Outdoor & Campcraft", True),
    ("Citizenship in Society", "Citizenship & Personal Development", True),
    ("Citizenship in the Community", "Citizenship & Personal Development", True),
    ("Citizenship in the Nation", "Citizenship & Personal Development", True),
    ("Citizenship in the World", "Citizenship & Personal Development", True),
    ("Communication", "Citizenship & Personal Development", True),
    ("Cooking", "Outdoor & Campcraft", True),
    ("Cycling", "Aquatics & Sports", True),
    ("Emergency Preparedness", "Health & Public Safety", True),
    ("Environmental Science", "Nature & Environment", True),
    ("Family Life", "Citizenship & Personal Development", True),
    ("First Aid", "Health & Public Safety", True),
    ("Hiking", "Outdoor & Campcraft", True),
    ("Lifesaving", "Aquatics & Sports", True),
    ("Personal Fitness", "Health & Public Safety", True),
    ("Personal Management", "Citizenship & Personal Development", True),
    ("Sustainability", "Nature & Environment", True),
    ("Swimming", "Aquatics & Sports", True),

    # 120 Elective Merit Badges (Alphabetical)
    ("American Business", "Trades, Business & Careers", False),
    ("American Cultures", "Citizenship & Personal Development", False),
    ("American Heritage", "Citizenship & Personal Development", False),
    ("American Labor", "Trades, Business & Careers", False),
    ("Animal Science", "Nature & Environment", False),
    ("Animation", "Arts, Crafts & Hobbies", False),
    ("Archaeology", "STEM & Science", False),
    ("Archery", "Aquatics & Sports", True if False else False),
    ("Architecture", "STEM & Science", False),
    ("Art", "Arts, Crafts & Hobbies", False),
    ("Astronomy", "STEM & Science", False),
    ("Athletics", "Aquatics & Sports", False),
    ("Automotive Maintenance", "Trades, Business & Careers", False),
    ("Aviation", "STEM & Science", False),
    ("Backpacking", "Outdoor & Campcraft", False),
    ("Basketry", "Arts, Crafts & Hobbies", False),
    ("Bird Study", "Nature & Environment", False),
    ("Bugling", "Arts, Crafts & Hobbies", False),
    ("Canoeing", "Aquatics & Sports", False),
    ("Chemistry", "STEM & Science", False),
    ("Chess", "Arts, Crafts & Hobbies", False),
    ("Climbing", "Outdoor & Campcraft", False),
    ("Coin Collecting", "Arts, Crafts & Hobbies", False),
    ("Collections", "Arts, Crafts & Hobbies", False),
    ("Composite Materials", "STEM & Science", False),
    ("Crime Prevention", "Health & Public Safety", False),
    ("Dentistry", "Health & Public Safety", False),
    ("Digital Technology", "STEM & Science", False),
    ("Disabilities Awareness", "Citizenship & Personal Development", False),
    ("Dog Care", "Nature & Environment", False),
    ("Drafting", "STEM & Science", False),
    ("Electricity", "STEM & Science", False),
    ("Electronics", "STEM & Science", False),
    ("Energy", "STEM & Science", False),
    ("Engineering", "STEM & Science", False),
    ("Entrepreneurship", "Trades, Business & Careers", False),
    ("Exploration", "Outdoor & Campcraft", False),
    ("Farm Mechanics", "Trades, Business & Careers", False),
    ("Fingerprinting", "Health & Public Safety", False),
    ("Fire Safety", "Health & Public Safety", False),
    ("Fish and Wildlife Management", "Nature & Environment", False),
    ("Fishing", "Outdoor & Campcraft", False),
    ("Fly-Fishing", "Outdoor & Campcraft", False),
    ("Forestry", "Nature & Environment", False),
    ("Game Design", "STEM & Science", False),
    ("Gardening", "Nature & Environment", False),
    ("Genealogy", "Citizenship & Personal Development", False),
    ("Geocaching", "Outdoor & Campcraft", False),
    ("Geology", "STEM & Science", False),
    ("Golf", "Aquatics & Sports", False),
    ("Graphic Arts", "Arts, Crafts & Hobbies", False),
    ("Health Care Professions", "Health & Public Safety", False),
    ("Home Repairs", "Trades, Business & Careers", False),
    ("Horsemanship", "Aquatics & Sports", False),
    ("Indian Lore", "Citizenship & Personal Development", False),
    ("Insect Study", "Nature & Environment", False),
    ("Inventing", "STEM & Science", False),
    ("Journalism", "Trades, Business & Careers", False),
    ("Kayaking", "Aquatics & Sports", False),
    ("Landscape Architecture", "Trades, Business & Careers", False),
    ("Law", "Citizenship & Personal Development", False),
    ("Leatherwork", "Arts, Crafts & Hobbies", False),
    ("Mammal Study", "Nature & Environment", False),
    ("Metalwork", "Arts, Crafts & Hobbies", False),
    ("Mining in Society", "STEM & Science", False),
    ("Model Design and Building", "Arts, Crafts & Hobbies", False),
    ("Motorboating", "Aquatics & Sports", False),
    ("Moviemaking", "Arts, Crafts & Hobbies", False),
    ("Music", "Arts, Crafts & Hobbies", False),
    ("Nature", "Nature & Environment", False),
    ("Nuclear Science", "STEM & Science", False),
    ("Oceanography", "STEM & Science", False),
    ("Orienteering", "Outdoor & Campcraft", False),
    ("Painting", "Arts, Crafts & Hobbies", False),
    ("Pets", "Nature & Environment", False),
    ("Photography", "Arts, Crafts & Hobbies", False),
    ("Pioneering", "Outdoor & Campcraft", False),
    ("Plant Science", "Nature & Environment", False),
    ("Plumbing", "Trades, Business & Careers", False),
    ("Pottery", "Arts, Crafts & Hobbies", False),
    ("Programming", "STEM & Science", False),
    ("Public Health", "Health & Public Safety", False),
    ("Public Speaking", "Citizenship & Personal Development", False),
    ("Pulp and Paper", "Trades, Business & Careers", False),
    ("Radio", "STEM & Science", False),
    ("Railroading", "Trades, Business & Careers", False),
    ("Reading", "Citizenship & Personal Development", False),
    ("Reptile and Amphibian Study", "Nature & Environment", False),
    ("Rifle Shooting", "Aquatics & Sports", False),
    ("Robotics", "STEM & Science", False),
    ("Rowing", "Aquatics & Sports", False),
    ("Safety", "Health & Public Safety", False),
    ("Salesmanship", "Trades, Business & Careers", False),
    ("Scholarship", "Citizenship & Personal Development", False),
    ("Scouting Heritage", "Citizenship & Personal Development", False),
    ("Scuba Diving", "Aquatics & Sports", False),
    ("Sculpture", "Arts, Crafts & Hobbies", False),
    ("Search and Rescue", "Health & Public Safety", False),
    ("Shotgun Shooting", "Aquatics & Sports", False),
    ("Signs, Signals, and Codes", "Outdoor & Campcraft", False),
    ("Skating", "Aquatics & Sports", False),
    ("Small-Boat Sailing", "Aquatics & Sports", False),
    ("Snow Sports", "Aquatics & Sports", False),
    ("Soil and Water Conservation", "Nature & Environment", False),
    ("Space Exploration", "STEM & Science", False),
    ("Sports", "Aquatics & Sports", False),
    ("Stamp Collecting", "Arts, Crafts & Hobbies", False),
    ("Surveying", "STEM & Science", False),
    ("Textile", "Arts, Crafts & Hobbies", False),
    ("Theater", "Arts, Crafts & Hobbies", False),
    ("Traffic Safety", "Health & Public Safety", False),
    ("Truck Transportation", "Trades, Business & Careers", False),
    ("Veterinary Medicine", "Health & Public Safety", False),
    ("Water Sports", "Aquatics & Sports", False),
    ("Weather", "STEM & Science", False),
    ("Welding", "Trades, Business & Careers", False),
    ("Whitewater", "Aquatics & Sports", False),
    ("Wilderness Survival", "Outdoor & Campcraft", False),
    ("Wood Carving", "Arts, Crafts & Hobbies", False),
    ("Woodwork", "Arts, Crafts & Hobbies", False),
]


def _badge_slug(name: str) -> str:
    return (
        name.lower()
        .replace(",", "")
        .replace("&", "and")
        .replace(" ", "-")
        .replace("--", "-")
        .strip("-")
    )


OFFICIAL_BSA_MERIT_BADGES_CATALOG: List[Dict[str, object]] = [
    {
        "badge_name": name,
        "category": category,
        "is_eagle_required": is_eagle,
        "slug": _badge_slug(name),
        "pamphlet_pdf_url": f"https://www.scouting.org/merit-badges/{_badge_slug(name)}/",
        "drg_url": f"https://www.scouting.org/merit-badges/{_badge_slug(name)}/",
    }
    for name, category, is_eagle in sorted(
        _RAW_MERIT_BADGE_CATALOG, key=lambda x: x[0].lower()
    )
]

ALL_OFFICIAL_BADGE_NAMES: Set[str] = {
    str(item["badge_name"]).lower(): str(item["badge_name"])
    for item in OFFICIAL_BSA_MERIT_BADGES_CATALOG
}


def get_merit_badge_metadata(badge_name: str) -> Optional[Dict[str, object]]:
    """Looks up official catalog metadata for any of the 138 Scouts BSA Merit Badges."""
    if not badge_name or not isinstance(badge_name, str):
        return None
    target = badge_name.strip().lower()
    for item in OFFICIAL_BSA_MERIT_BADGES_CATALOG:
        if str(item["badge_name"]).lower() == target:
            return dict(item)
    return None


def get_badge_cover_and_patch_paths(badge_name: str) -> Dict[str, Optional[str]]:
    """Resolves local cached paths for a Merit Badge's official patch emblem and pamphlet cover."""
    slug_underscore = "".join(ch if ch.isalnum() else "_" for ch in (badge_name or "").strip().lower()).strip("_")
    slug_hyphen = _badge_slug(badge_name or "")
    patch_candidates = [
        ASSETS_DIR / "badge_emblems" / f"{slug_underscore}.png",
        ASSETS_DIR / "badge_emblems" / f"{slug_underscore}_patch.png",
        ASSETS_DIR / "badge_emblems" / f"{slug_hyphen}.png",
        ASSETS_DIR / "diagrams" / f"{slug_underscore}_patch.png",
    ]
    cover_candidates = [
        ASSETS_DIR / "pamphlet_covers" / f"{slug_underscore}_cover.png",
        ASSETS_DIR / "pamphlet_covers" / f"{slug_hyphen}_cover.png",
        ASSETS_DIR / "diagrams" / f"{slug_underscore}_cover.png",
    ]
    patch_path = next((str(p) for p in patch_candidates if p.exists()), None)
    cover_path = next((str(p) for p in cover_candidates if p.exists()), None)
    return {"patch_path": patch_path, "cover_path": cover_path}


# ==============================================================================
# PRESENTATION DEPTH SETTINGS & FINOPS ROUTING
# ==============================================================================

PRESENTATION_DEPTH_CONFIGS: Dict[str, Dict[str, int]] = {
    "Standard Deck": {
        "min_slides_per_req": 1,
        "max_slides_per_req": 3,
        "include_troop_activities": True,
        "include_guide_to_safe_scouting": True,
    },
    "Deep Dive / Camp School Deck": {
        "min_slides_per_req": 4,
        "max_slides_per_req": 12,
        "include_troop_activities": True,
        "include_guide_to_safe_scouting": True,
    },
}

MODEL_ROUTING_POLICY: Dict[str, str] = {
    "coordinator": os.environ.get("BSA_COORDINATOR_MODEL", "gemini-2.5-flash"),
    "researcher": os.environ.get("BSA_RESEARCHER_MODEL", "gemini-2.5-pro"),
    "web_search": os.environ.get("BSA_WEB_SEARCH_MODEL", "gemini-2.5-flash"),
    "deep_research": os.environ.get("BSA_DEEP_RESEARCH_MODEL", "gemini-2.5-flash"),
    "planner": os.environ.get("BSA_PLANNER_MODEL", "gemini-2.5-pro"),
    "beautifier": os.environ.get("BSA_BEAUTIFIER_MODEL", "gemini-2.5-flash"),
    "web_image_search": os.environ.get("BSA_WEB_IMAGE_SEARCH_MODEL", "gemini-2.5-flash"),
    "nano_banana_image": os.environ.get("BSA_NANO_BANANA_MODEL", "gemini-2.5-flash-image"),
    "builder": os.environ.get("BSA_BUILDER_MODEL", "gemini-2.5-flash"),
    "reviewer": os.environ.get("BSA_REVIEWER_MODEL", "gemini-2.5-pro"),
    "imagen": os.environ.get("BSA_IMAGEN_MODEL", "imagen-3.0-generate-002"),
}


def select_model_for_task(agent_role: str, task_complexity: str = "auto") -> str:
    """Strategically routes requests between Gemini 2.5 Flash (fast tier) and Gemini 2.5 Pro (deep reasoning tier).

    Reads `config/finops_model_policy.json` and `MODEL_ROUTING_POLICY` so latency-sensitive
    routing, grounding, and deterministic build tasks execute on `gemini-2.5-flash`, while
    multi-requirement synthesis, 12-archetype storyboard planning, and 2-stage conformance
    critique execute on `gemini-2.5-pro`.

    Args:
        agent_role: Identifier of the agent or task ('coordinator', 'researcher', 'web_search',
            'planner', 'builder', 'reviewer', or 'imagen').
        task_complexity: Optional override ('fast', 'deep_reasoning', 'visual', or 'auto').

    Returns:
        str: Resolved model identifier (e.g., 'gemini-2.5-flash' or 'gemini-2.5-pro').
    """
    import json

    policy_file = PROJECT_ROOT / "config" / "finops_model_policy.json"
    finops_models: Dict[str, Any] = {}
    if policy_file.exists():
        try:
            finops_data = json.loads(policy_file.read_text(encoding="utf-8"))
            finops_models = finops_data.get("models", {})
        except Exception:
            finops_models = {}

    if task_complexity in ("fast", "low"):
        return str(
            finops_models.get("fast_tier", {}).get(
                "model_id", MODEL_ROUTING_POLICY.get("coordinator", "gemini-2.5-flash")
            )
        )
    if task_complexity in ("deep_reasoning", "high"):
        return str(
            finops_models.get("deep_reasoning_tier", {}).get(
                "model_id", MODEL_ROUTING_POLICY.get("planner", "gemini-2.5-pro")
            )
        )
    if task_complexity == "visual":
        return str(
            finops_models.get("visual_generation_tier", {}).get(
                "model_id", MODEL_ROUTING_POLICY.get("imagen", "imagen-3.0-generate-002")
            )
        )

    role_key = (agent_role or "coordinator").strip().lower()
    return MODEL_ROUTING_POLICY.get(role_key, "gemini-2.5-flash")


# ==============================================================================
# SECURE SECRET MANAGEMENT (GOOGLE CLOUD SECRET MANAGER + ENV FALLBACK)
# ==============================================================================

_RUNTIME_EPHEMERAL_SECRETS: Dict[str, str] = {}


def get_secret(
    secret_id: str,
    default: Optional[str] = None,
    project_id: Optional[str] = None,
) -> str:
    """Retrieves a sensitive secret from Google Cloud Secret Manager with local environment fallback.

    Ensures zero hardcoded API keys or HMAC secrets exist in the source tree. In Google Cloud
    deployments (when `USE_GCP_SECRET_MANAGER=true`), fetches the latest version from
    `projects/{project_id}/secrets/{secret_id}/versions/latest` via `google.cloud.secretmanager`.
    In local laptop development, falls back to environment variables (`.env`) or generates
    a cryptographically random per-process ephemeral secret.

    Args:
        secret_id: Environment variable or Secret Manager identifier (e.g., 'GEMINI_API_KEY',
            'BSA_HITL_SECRET_KEY').
        default: Optional non-sensitive fallback value if unconfigured.
        project_id: Optional GCP project ID (defaults to `GOOGLE_CLOUD_PROJECT` env var).

    Returns:
        str: Resolved secret value string.
    """
    import secrets as stdlib_secrets

    env_val = os.environ.get(secret_id)
    if env_val and env_val not in ("your-gemini-api-key-here", "your-google-api-key-here"):
        return env_val

    gcp_secret_name = secret_id.lower().replace("_", "-")
    resolved_project = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
    use_sm = os.environ.get("USE_GCP_SECRET_MANAGER", "false").lower() == "true"

    if use_sm and resolved_project:
        try:
            from google.cloud import secretmanager  # type: ignore

            client = secretmanager.SecretManagerServiceClient()
            resource_name = f"projects/{resolved_project}/secrets/{gcp_secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": resource_name})
            payload = response.payload.data.decode("utf-8").strip()
            if payload:
                return payload
        except Exception:
            pass

    if default is not None:
        return default

    if secret_id not in _RUNTIME_EPHEMERAL_SECRETS:
        _RUNTIME_EPHEMERAL_SECRETS[secret_id] = stdlib_secrets.token_hex(32)
    return _RUNTIME_EPHEMERAL_SECRETS[secret_id]


# ==============================================================================
# MODULAR MODEL PROVIDER ABSTRACTION (DESIGNING FOR CHANGE)
# ==============================================================================

class ModelProvider:
    """Provider-agnostic interface for resolving and invoking LLM models.

    Decouples agent orchestration logic from a single hardcoded vendor SDK so
    models can be swapped via environment variables or `config/finops_model_policy.json`
    without modifying business logic.
    """

    provider_name: str = "google_vertex_gemini"

    def resolve_model(self, agent_role: str, task_complexity: str = "auto") -> str:
        """Resolves the canonical model ID for a given agent role and complexity tier."""
        return select_model_for_task(agent_role=agent_role, task_complexity=task_complexity)

    def get_fallback_chain(self, agent_role: str) -> List[str]:
        """Returns the ordered fallback model chain if the primary model experiences quota/503 errors."""
        primary = self.resolve_model(agent_role=agent_role)
        chain = [primary]
        if "gemini-2.5-pro" in primary:
            chain.append("gemini-2.5-flash")
        chain.append("deterministic-local-curriculum-engine")
        return chain


class SecondaryLiteLLMModelProvider(ModelProvider):
    """Secondary/fallback provider adapter supporting OpenAI/Anthropic/LiteLLM-compatible model strings."""

    provider_name: str = "litellm_multi_provider"

    def resolve_model(self, agent_role: str, task_complexity: str = "auto") -> str:
        override_prefix = os.environ.get("BSA_MODEL_PROVIDER_PREFIX", "")
        base_model = select_model_for_task(agent_role=agent_role, task_complexity=task_complexity)
        return f"{override_prefix}/{base_model}" if override_prefix else base_model


def get_model_provider(provider_name: Optional[str] = None) -> ModelProvider:
    """Factory returning the active `ModelProvider` implementation."""
    resolved = (provider_name or os.environ.get("BSA_MODEL_PROVIDER", "google_vertex_gemini")).strip().lower()
    if resolved in ("litellm", "litellm_multi_provider", "secondary"):
        return SecondaryLiteLLMModelProvider()
    return ModelProvider()



