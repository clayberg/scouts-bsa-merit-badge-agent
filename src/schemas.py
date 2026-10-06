"""Canonical Pydantic v2 Data Contracts for the Scouts BSA Merit Badge Agent System.

Defines the strongly-typed schemas passed across the 5-Tier Deep Research Pipeline,
12-Archetype Slide Storyboard Planner, Tri-Modal Visual Asset Pipeline, 2-Stage
Visual Conformance & Vision Critic, FastMCP HITL Confirmation Gate, A2A 1.0 Server,
and Google Material 3 Expressive A2UI Workbench.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ==============================================================================
# 1. EXECUTION MODES & SLIDE ARCHETYPE ENUMS
# ==============================================================================

class ExecutionMode(str, Enum):
    """Pedagogical execution mode for a Scouts BSA Merit Badge sub-requirement."""
    IN_CLASS_DISCUSSION = "IN_CLASS_DISCUSSION"
    HANDS_ON_SKILL_STATION = "HANDS_ON_SKILL_STATION"
    PREREQUISITE_CAMPOUT_HOME = "PREREQUISITE_CAMPOUT_HOME"


class SlideArchetype(str, Enum):
    """The 12 distinct visual slide archetypes inspired by SlideGen & hand-made BSA decks."""
    COVER_HERO = "COVER_HERO"
    REQUIREMENTS_TRIAGE_MATRIX = "REQUIREMENTS_TRIAGE_MATRIX"
    SUBREQ_SECTION_DIVIDER = "SUBREQ_SECTION_DIVIDER"
    SPLIT_VISUAL_EXPLAINER = "SPLIT_VISUAL_EXPLAINER"
    STEP_BY_STEP_PROCEDURE_4CARD = "STEP_BY_STEP_PROCEDURE_4CARD"
    DIFFERENTIAL_COMPARISON_2COL = "DIFFERENTIAL_COMPARISON_2COL"
    DECISION_TREE_FLOW = "DECISION_TREE_FLOW"
    SPATIAL_FIELD_DIAGRAM = "SPATIAL_FIELD_DIAGRAM"
    WORKED_EXAMPLE_TEMPLATE = "WORKED_EXAMPLE_TEMPLATE"
    GEAR_CHECKLIST_GRID = "GEAR_CHECKLIST_GRID"
    HANDS_ON_PRACTICE_STATION = "HANDS_ON_PRACTICE_STATION"
    SOCRATIC_CHECKPOINT_QUIZ = "SOCRATIC_CHECKPOINT_QUIZ"


class VisualSourceType(str, Enum):
    """Tri-modal visual source classification."""
    PAMPHLET_EXTRACTED_FIGURE = "PAMPHLET_EXTRACTED_FIGURE"
    DETERMINISTIC_SVG_DIAGRAM = "DETERMINISTIC_SVG_DIAGRAM"
    IMAGEN_CONCEPTUAL_PHOTO = "IMAGEN_CONCEPTUAL_PHOTO"
    MERMAID_FLOWCHART = "MERMAID_FLOWCHART"


# ==============================================================================
# 2. DEEP RESEARCH & SUB-REQUIREMENT TREE CONTRACTS
# ==============================================================================

class WorkedExampleData(BaseModel):
    """Concrete, filled-in artifact example for Scouts to model (e.g., Duty Roster, Recipe, Senator Letter)."""
    title: str = Field(..., description="Title of the worked example artifact.")
    artifact_type: str = Field(..., description="Type: 'RECIPE_CARD', 'DUTY_ROSTER', 'LETTER_TEMPLATE', 'BUDGET_LOG', 'ACTION_PLAN'.")
    fields: Dict[str, str] = Field(default_factory=dict, description="Key-value fields of the worked example.")
    counselor_tip: str = Field("", description="Practical tip from experienced Merit Badge Counselors.")


class ComparisonPairData(BaseModel):
    """Structured two-column differential comparison for medical/gear/civic contrasts."""
    left_header: str = Field(..., description="Left column title (e.g., 'Heat Exhaustion').")
    left_badge: str = Field("CAUTION", description="Status badge for left column.")
    left_points: List[str] = Field(default_factory=list, description="3-5 concrete attributes for left column.")
    right_header: str = Field(..., description="Right column title (e.g., 'Heat Stroke (911)').")
    right_badge: str = Field("LIFE-THREATENING", description="Status badge for right column.")
    right_points: List[str] = Field(default_factory=list, description="3-5 concrete attributes for right column.")


class SocraticQuizItem(BaseModel):
    """Interactive check-on-learning scenario question for the patrol."""
    scenario_prompt: str = Field(..., description="Real-world scouting scenario question.")
    options: List[str] = Field(default_factory=list, description="3-4 multiple-choice or discussion options.")
    correct_answer: str = Field(..., description="Verified answer grounded in BSA Pamphlet.")
    explanation: str = Field(..., description="Why this answer is correct per BSA Guide to Safe Scouting / Pamphlet.")


class RequirementNode(BaseModel):
    """Rich requirement or sub-requirement node with full pedagogical & visual metadata.

    Backward-compatible with RequirementPoint (includes req_number, req_text, safety_callout).
    """
    req_id: str = Field("", description="Canonical ID (e.g., '1', '1a', '2b1', '4a').")
    req_number: str = Field(..., description="Requirement identifier (e.g., '1', '2a', '3b').")
    parent_id: Optional[str] = Field(None, description="Parent requirement ID if sub-requirement.")
    action_verb: str = Field("Explain", description="Leading verb: Explain, Discuss, Demonstrate, Show, Camp, Visit.")
    req_text: str = Field(..., description="Full verbatim requirement text (never truncated).")
    execution_mode: ExecutionMode = Field(
        ExecutionMode.IN_CLASS_DISCUSSION,
        description="Triage classification: In-Class Discussion, Hands-On Skill Station, or Prerequisite/Campout/Home."
    )
    edge_phase: str = Field(
        "Explain & Guide",
        description="BSA EDGE Method phase: Explain, Demonstrate, Guide, or Enable."
    )
    pamphlet_excerpts: List[str] = Field(
        default_factory=list,
        description="Detailed instructional facts and technical explanations from the official BSA Pamphlet."
    )
    step_by_step_procedure: List[str] = Field(
        default_factory=list,
        description="4-step actionable procedure with 'Bold Anchor: Explanation' formatting."
    )
    gear_checklist: List[str] = Field(
        default_factory=list,
        description="Specific equipment or inspection checklist items if applicable."
    )
    worked_example: Optional[WorkedExampleData] = Field(
        None,
        description="Concrete filled-in template or worked example for this requirement."
    )
    comparison_data: Optional[ComparisonPairData] = Field(
        None,
        description="Two-column differential comparison (e.g., Heat Exhaustion vs. Heat Stroke, Canister vs. Liquid Fuel)."
    )
    quiz_item: Optional[SocraticQuizItem] = Field(
        None,
        description="Check-on-learning Socratic scenario quiz for Scouts."
    )
    recommended_archetype: SlideArchetype = Field(
        SlideArchetype.SPLIT_VISUAL_EXPLAINER,
        description="Primary slide archetype best suited for teaching this sub-requirement."
    )
    visual_diagram_type: str = Field(
        "procedural_flow",
        description="Specific diagram generator key (e.g., 'triage_tree', 'heat_comparison', 'bearmuda_triangle', 'checks_balances', 'first_aid_kit_grid')."
    )
    safety_callout: Optional[str] = Field(
        None,
        description="Guide to Safe Scouting warning if applicable."
    )
    drg_video_links: List[str] = Field(
        default_factory=list,
        description="Official Scouting.org Digital Resource Guide video or article URLs."
    )
    counselor_signoff_criteria: str = Field(
        "Scout must individually explain or demonstrate mastery to the Merit Badge Counselor.",
        description="Exact verification standard for Blue Card / Scoutbook sign-off."
    )


# ==============================================================================
# 3. 12-ARCHETYPE SLIDE STORYBOARD & VISUAL ASSET CONTRACTS
# ==============================================================================

class VisualAssetSpec(BaseModel):
    """Specification for a slide's visual diagram, pamphlet figure, or Imagen photo."""
    asset_id: str = Field(..., description="Unique asset identifier (e.g., 'first_aid_req_4a_cpr_flow').")
    source_type: VisualSourceType = Field(
        VisualSourceType.DETERMINISTIC_SVG_DIAGRAM,
        description="How the visual is produced."
    )
    diagram_kind: str = Field(
        "procedural_cards",
        description="Specific diagram renderer kind."
    )
    caption: str = Field(..., description="Instructional caption displayed beneath or beside the visual.")
    svg_path: Optional[str] = Field(None, description="Path to vector SVG diagram.")
    png_path: Optional[str] = Field(None, description="Path to high-DPI PNG image for python-pptx embedding.")
    alt_text: str = Field("", description="Accessibility description of the visual.")


class SlideCardItem(BaseModel):
    """Individual card or callout item on a multi-card slide."""
    badge_label: str = Field("", description="Short step number or tag (e.g., 'STEP 1', 'CHECK', 'RULE').")
    anchor_title: str = Field(..., description="2-4 word bold anchor title.")
    body_text: str = Field(..., description="Concise explanation (<= 22 words, zero truncation).")
    accent_color_hex: str = Field("#003F87", description="Card accent hex color.")


class ConformanceIssue(BaseModel):
    """Single geometry, contrast, typography, or copywriting violation detected in Stage 1."""
    slide_index: int = Field(..., description="1-based slide index.")
    issue_type: Literal[
        "AABB_SHAPE_OVERLAP",
        "OUT_OF_CANVAS_BOUNDS",
        "TEXT_BOX_OVERFLOW",
        "FONT_FLOOR_VIOLATION",
        "WCAG_CONTRAST_VIOLATION",
        "LITERAL_BULLET_GLYPH",
        "ELLIPSIS_TRUNCATION",
        "PARAGRAPH_COUNT_EXCEEDED",
        "DUPLICATE_VISUAL_ASSET",
    ]
    severity: Literal["CRITICAL", "WARNING"] = "CRITICAL"
    description: str = Field(..., description="Detailed mathematical or rule explanation.")
    remediation_hint: str = Field(..., description="Specific parameter fix for the builder.")


class ConformanceReport(BaseModel):
    """Stage 1 fast (<10ms) deterministic geometry, contrast, and copywriting audit report."""
    passed: bool = Field(..., description="True if 0 CRITICAL conformance issues.")
    total_slides_audited: int = Field(..., description="Total slides inspected.")
    unique_visual_assets_count: int = Field(0, description="Number of distinct visual images embedded.")
    min_font_size_pt: float = Field(14.0, description="Smallest font size detected across deck.")
    min_contrast_ratio: float = Field(7.0, description="Lowest foreground/background contrast ratio.")
    aabb_overlap_count: int = Field(0, description="Number of overlapping bounding box pairs.")
    issues: List[ConformanceIssue] = Field(default_factory=list, description="Detected conformance issues.")


class VisualCritiqueVerdict(BaseModel):
    """Stage 2 Vision-LLM + Pedagogical Critic structured verdict."""
    slide_index: int = Field(..., description="1-based slide index.")
    layout_score: int = Field(5, ge=1, le=5, description="Visual layout & whitespace balance score (1-5).")
    pedagogical_depth_score: int = Field(5, ge=1, le=5, description="Instructional depth vs hand-made counselor decks (1-5).")
    visual_relevance_score: int = Field(5, ge=1, le=5, description="How well the diagram/image teaches the requirement (1-5).")
    has_text_overlap: bool = Field(False, description="True if any text overlaps or overflows.")
    passed: bool = Field(True, description="True if all scores >= 4 and no overlaps.")
    surgical_fix_instructions: Optional[str] = Field(None, description="Specific fix instruction if passed is False.")


class HITLConfirmationToken(BaseModel):
    """Cryptographic FastMCP human-in-the-loop approval token before .pptx build."""
    token_id: str = Field(..., description="HMAC/SHA-256 confirmation token bound to storyboard hash.")
    badge_name: str = Field(..., description="Official badge name.")
    slide_count: int = Field(..., description="Number of storyboard slides approved.")
    subrequirement_count: int = Field(..., description="Number of sub-requirements covered.")
    counselor_name: str = Field(..., description="Approving counselor name.")
    approved: bool = Field(True, description="Whether counselor approved the storyboard.")
    timestamp_iso: str = Field(..., description="ISO-8601 approval timestamp.")


# ==============================================================================
# 4. GOOGLE A2UI v0.9 & MATERIAL 3 EXPRESSIVE WORKBENCH PAYLOAD
# ==============================================================================

class A2UIMessageEnvelope(BaseModel):
    """A2UI v0.9 compliant message envelope for dynamic Agent-to-UI rendering."""
    version: str = Field("v0.9", description="A2UI specification version.")
    beginRendering: Optional[Dict[str, Any]] = None
    surfaceUpdate: Optional[Dict[str, Any]] = None
    dataModelUpdate: Optional[Dict[str, Any]] = None
    deleteSurface: Optional[Dict[str, Any]] = None


# ==============================================================================
# 5. UNIVERSAL GUIDED TOOL ERROR & EXPLICIT JSON SCHEMA REGISTRY (CATEGORY 1)
# ==============================================================================

class GuidedToolError(BaseModel):
    """Structured error payload providing LLM self-correction and recovery guidance.

    Returned by tools instead of raising unhandled exceptions when input validation
    or external resource lookup fails.
    """

    status: str = Field("ERROR", description="Error status indicator ('ERROR').")
    error_type: str = Field(..., description="Machine-readable error classification code.")
    error_code: str = Field("", description="Alias for error_type for standardized tool error parsing.")
    message: str = Field(..., description="Human- and LLM-readable explanation of what failed.")
    recovery_suggestion: str = Field(
        ...,
        description="Actionable recovery instruction telling the LLM how to self-correct on the next turn.",
    )
    remediation: str = Field(
        "",
        description="Alias for recovery_suggestion with remediation guidance.",
    )
    recovery_guidance: str = Field(
        "",
        description="Detailed step-by-step remediation guidance for the calling agent.",
    )
    available_badges_sample: List[str] = Field(
        default_factory=list,
        description="Sample of valid Merit Badge names when a badge lookup fails.",
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional structured diagnostic details.",
    )


def build_guided_tool_error(
    error_type: Optional[str] = None,
    message: str = "",
    recovery_suggestion: Optional[str] = None,
    available_badges_sample: Optional[List[str]] = None,
    *,
    error_code: Optional[str] = None,
    remediation: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Constructs a standardized GuidedToolError dictionary for LLM recovery.

    Args:
        error_type: Specific machine-readable error code (e.g., `'BADGE_PAMPHLET_NOT_FOUND'`).
        message: Clear description of the validation or execution failure.
        recovery_suggestion: Concrete instruction for the LLM to recover on its next tool call.
        available_badges_sample: Optional list of valid badge names to guide retry.
        error_code: Optional alias for `error_type`.
        remediation: Optional alias for `recovery_suggestion`.
        details: Optional dictionary of structured diagnostic details.

    Returns:
        Dict[str, Any]: Serialized `GuidedToolError` dictionary containing `status`, `error_type`,
        `error_code`, `message`, `recovery_suggestion`, `remediation`, `recovery_guidance`,
        `available_badges_sample`, and `details`.
    """
    resolved_code = error_type or error_code or "TOOL_EXECUTION_ERROR"
    resolved_remediation = (
        recovery_suggestion
        or remediation
        or "Verify tool arguments against the Pydantic JSON schema and retry."
    )
    err = GuidedToolError(
        status="ERROR",
        error_type=resolved_code,
        error_code=resolved_code,
        message=message,
        recovery_suggestion=resolved_remediation,
        remediation=resolved_remediation,
        recovery_guidance=resolved_remediation,
        available_badges_sample=available_badges_sample
        or ["First Aid", "Camping", "Weather", "Citizenship in the Nation"],
        details=details or {},
    )
    return err.model_dump()


# ==============================================================================
# 6. DEEP RESEARCH ENRICHMENT, SLIDE BEAUTIFICATION & FINOPS SCHEMAS (v3.0)
# ==============================================================================

class GroundedWebCitation(BaseModel):
    """Verified external web or open-educational-resource citation supplementing the BSA Pamphlet."""

    req_number: str = Field(..., description="Associated Merit Badge requirement number (e.g., '1a', '2').")
    source_title: str = Field(..., description="Title of the authoritative external source (e.g., 'NOAA JetStream').")
    source_url: str = Field(..., description="HTTPS URL of the grounded web source.")
    authority_domain: str = Field(..., description="Domain category (e.g., 'noaa.gov', 'usgs.gov', 'redcross.org').")
    supplemental_fact: str = Field(..., description="Real-world case study, local landmark, or worked example.")
    is_canonical_pamphlet: bool = Field(
        False,
        description="Always False for web supplements; the BSA Pamphlet remains the primary source of truth.",
    )


class DeepResearchEnrichmentResult(BaseModel):
    """Structured enrichment payload returned by DeepResearchEnrichmentAgent while locking canonical Pamphlet text."""

    badge_name: str = Field(..., description="Official Scouts BSA Merit Badge name.")
    troop_affiliation: str = Field(..., description="Troop and Council affiliation used for hyper-local grounding.")
    canonical_pamphlet_hash: str = Field(
        ...,
        description="SHA-256 integrity hash of the verbatim BSA Pamphlet requirements (must remain unchanged).",
    )
    canonical_fidelity_verified: bool = Field(
        True,
        description="True when 100% of official requirement texts match the canonical BSA Pamphlet untouched.",
    )
    local_field_connections: List[str] = Field(
        default_factory=list,
        description="Hyper-local troop, council, trail, weather office, and civic connections.",
    )
    common_scout_misconceptions: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of requirement numbers to common Scout misconceptions and counselor coaching tips.",
    )
    real_world_case_studies: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of requirement numbers to contemporary real-world case studies.",
    )
    grounded_citations: List[GroundedWebCitation] = Field(
        default_factory=list,
        description="Verified external web and OER citations.",
    )
    resolved_location: Dict[str, str] = Field(
        default_factory=dict,
        description="Resolved counselor regional location metadata (NWS office, terrain, field sites).",
    )
    status: str = Field("SUCCESS", description="Enrichment execution status.")


class SlideBeautificationSpec(BaseModel):
    """Visual layout and editorial illustration directives produced by SlideBeautifierAgent."""

    slide_index: int = Field(..., ge=0, description="0-based index of the slide in the storyboard.")
    visual_theme: Literal[
        "MAGAZINE_ASYMMETRIC_SPLIT",
        "THREE_PILLAR_ACCENT_CARDS",
        "NUMBERED_STEP_RIBBON",
        "HERO_ILLUSTRATION_OVERLAY",
        "SAFETY_ALERT_SPOTLIGHT",
        "ANNOTATED_INFOGRAPHIC_STAGE",
    ] = Field("MAGAZINE_ASYMMETRIC_SPLIT", description="Magazine-grade visual card theme.")
    accent_palette_key: Literal["NAVY_GOLD", "OLIVE_FOREST", "EAGLE_CRIMSON", "SLATE_ACTION"] = Field(
        "NAVY_GOLD",
        description="Brand-aligned accent palette key.",
    )
    callout_badge_text: str = Field("", description="Short 2-4 word pill badge in top-right of card.")
    real_world_connection_box: Optional[str] = Field(
        None,
        description="Grounded case study or hyper-local troop field connection callout.",
    )
    ai_hero_image_prompt: Optional[str] = Field(
        None,
        description="Prompt for Imagen 3 / Gemini Flash Image editorial illustration if selected.",
    )
    ai_hero_image_path: Optional[str] = Field(
        None,
        description="Filesystem path to cached or generated AI editorial hero illustration.",
    )


class DeckVisualBlueprint(BaseModel):
    """Complete deck-level visual beautification blueprint with consecutive-slide variety enforcement."""

    badge_name: str = Field(..., description="Official Merit Badge name.")
    beautification_tier: Literal["STANDARD", "BEAUTIFIED", "STUDIO"] = Field(
        "BEAUTIFIED",
        description="Selected visual polish tier.",
    )
    consecutive_variety_verified: bool = Field(
        True,
        description="True when no two adjacent content slides share an identical visual_theme + accent_palette_key.",
    )
    ai_hero_images_generated: int = Field(0, description="Count of AI editorial hero illustrations attached.")
    slide_specs: List[SlideBeautificationSpec] = Field(
        default_factory=list,
        description="Per-slide visual beautification specifications.",
    )
    status: str = Field("SUCCESS", description="Blueprint generation status.")


class FinOpsCostEstimate(BaseModel):
    """Token, image, and USD cost estimate and budget guardrail status for a workflow run."""

    badge_name: str = Field(..., description="Official Merit Badge name.")
    depth_mode: str = Field(..., description="Slide deck depth mode.")
    beautification_tier: Literal["STANDARD", "BEAUTIFIED", "STUDIO"] = Field(
        "STANDARD",
        description="Selected visual polish tier.",
    )
    enable_deep_research: bool = Field(True, description="Whether grounded web & local research is enabled.")
    estimated_input_tokens: int = Field(..., description="Estimated prompt/context tokens across agents.")
    estimated_output_tokens: int = Field(..., description="Estimated completion tokens across agents.")
    planned_ai_hero_images: int = Field(0, description="Number of Imagen 3 / Gemini Flash Image calls planned.")
    estimated_cost_usd: float = Field(..., description="Estimated total run cost in USD before cache hits.")
    cached_rerun_cost_usd: float = Field(0.02, description="Estimated cost in USD when assets are disk-cached.")
    max_budget_usd: float = Field(0.50, description="Configured FinOps budget cap in USD.")
    within_budget: bool = Field(True, description="True if estimated_cost_usd <= max_budget_usd.")
    downgrade_action: Optional[str] = Field(
        None,
        description="Automatic FinOps downgrade action if estimate exceeds max_budget_usd.",
    )


def get_tool_json_schemas() -> Dict[str, Dict[str, Any]]:
    """Exports strict JSON Schemas (`.model_json_schema()`) for all core agent data contracts.

    Returns:
        Dict[str, Dict[str, Any]]: Mapping of schema model names to their JSON Schema definitions.
    """
    from src.tools.scouting_scraper import MeritBadgeResearchRequest, MeritBadgeResearchResult
    from src.tools.pptx_builder import (
        CounselorTitleSlideInfo,
        PowerPointBuildRequest,
        PowerPointBuildResult,
        SlideSpec,
    )

    models = [
        MeritBadgeResearchRequest,
        MeritBadgeResearchResult,
        PowerPointBuildRequest,
        PowerPointBuildResult,
        SlideSpec,
        CounselorTitleSlideInfo,
        WorkedExampleData,
        ComparisonPairData,
        SocraticQuizItem,
        RequirementNode,
        VisualAssetSpec,
        SlideCardItem,
        ConformanceIssue,
        ConformanceReport,
        VisualCritiqueVerdict,
        HITLConfirmationToken,
        A2UIMessageEnvelope,
        GuidedToolError,
        GroundedWebCitation,
        DeepResearchEnrichmentResult,
        SlideBeautificationSpec,
        DeckVisualBlueprint,
        FinOpsCostEstimate,
    ]
    return {m.__name__: m.model_json_schema() for m in models}


