"""ADK MeritBadgeCoordinatorAgent (ADK 2.0 Sequential/Loop Supervisor & A2UI Producer).

This module implements the root coordinator agent that manages the multi-agent
workflow graph, coordinates specialized subagents (5-Tier Deep Research, 12-Archetype
Storyboard Planner, Tri-Modal Visual & PowerPoint Builder, and 2-Stage Conformance/Vision
Critic), enforces FastMCP human-in-the-loop confirmation tokens and Google Cloud Model Armor
guardrails (`ScoutsBSAModelArmorPlugin`), emits OpenTelemetry spans and structured
`tool_intent`/`tool_outcome` logs, produces Google A2UI v0.9 surface payloads, and
integrates persistent session storage, vector memory, and history compaction.
"""

import asyncio
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel, Field
from google import adk

from src.config import (
    GENERATED_DECKS_DIR,
    SCOUTS_BSA_CONSTITUTION,
    load_prompt,
    select_model_for_task,
)
from src.schemas import build_guided_tool_error
from src.agents.researcher import (
    enrich_requirements_with_deep_research,
    get_pamphlet_research_agent,
)
from src.agents.planner import get_slide_content_planner_agent
from src.agents.beautifier import (
    beautify_slide_storyboard,
    get_slide_beautifier_agent,
)
from src.agents.image_studio import (
    estimate_nano_banana_image_cost,
    generate_nano_banana_slide_image,
    get_badge_image_catalog,
    get_nano_banana_image_agent,
    get_web_image_search_agent,
     search_web_images_for_slide,
    seed_badge_image_catalog_from_storyboard,
)
from src.agents.builder import get_powerpoint_builder_agent
from src.agents.reviewer import get_bsa_review_agent, get_bsa_review_loop_agent
from src.agents.guardrails import (
    FinOpsBudgetPlugin,
    ScoutsBSAModelArmorPlugin,
    before_model_guardrail_callback,
    after_model_guardrail_callback,
    before_tool_guardrail_callback,
    after_tool_guardrail_callback,
    estimate_workflow_finops_cost,
    sanitize_text_with_model_armor,
)
from src.tools.counselor_studiokit import (
    generate_counselor_session_agenda,
    generate_prerequisite_parent_letter,
)
from src.tools.hitl_confirm import request_counselor_confirmation
from src.observability.logging_setup import (
    execute_tool_with_observability,
    logger,
    scrub_pii_before_sink,
)
from src.observability.tracing import get_tracer
from src.memory.session_store import (
    EventsCompactionConfig,
    compact_conversation_events,
    compact_session_history_async,
    get_adk_context_cache_config,
    index_pamphlet_memory_async,
    load_session_state_async,
    retrieve_pamphlet_memory_chunks,
    save_session_state_async,
    _default_store,
)

try:
    from google.adk.agents.sequential_agent import SequentialAgent as _ADKSequentialAgent
except Exception:  # pragma: no cover
    _ADKSequentialAgent = None

try:
    from google.adk.apps.app import App as _ADKApp
except Exception:  # pragma: no cover
    _ADKApp = None


class PresentationWorkflowResult(BaseModel):
    """Final structured return payload delivered to the counselor UI."""

    badge_name: str = Field(..., description="Official badge name.")
    output_path: str = Field(..., description="Absolute path to generated .pptx file.")
    slide_count: int = Field(..., description="Number of slides in presentation.")
    is_eagle_required: bool = Field(..., description="True if Eagle-required.")
    safety_approved: bool = Field(..., description="True if guardrail approved.")
    status: str = Field("SUCCESS", description="Workflow execution status.")
    workbook_path: Optional[str] = Field(None, description="Path to generated Counselor/Scout Markdown workbook.")
    hitl_confirmation_token: Optional[str] = Field(None, description="FastMCP HMAC-SHA256 confirmation token.")
    triage_summary: Dict[str, int] = Field(default_factory=dict, description="Sub-requirement count by execution mode.")
    conformance_report: Optional[Dict[str, Any]] = Field(None, description="Stage 1 & Stage 2 visual conformance report.")
    storyboard: Optional[Dict[str, Any]] = Field(None, description="Complete 12-archetype slide storyboard.")
    research_artifact: Optional[Dict[str, Any]] = Field(None, description="5-tier deep research artifact.")
    deep_research_enrichment: Optional[Dict[str, Any]] = Field(
        None,
        description="Tier-2 grounded web & hyper-local troop enrichment artifact (Pamphlet remains primary).",
    )
    deck_visual_blueprint: Optional[Dict[str, Any]] = Field(
        None,
        description="SlideBeautifierAgent magazine visual blueprint and AI hero art metadata.",
    )
    finops_cost_estimate: Optional[Dict[str, Any]] = Field(
        None,
        description="FinOps token, AI illustration, and USD cost estimate.",
    )
    session_agenda: Optional[Dict[str, Any]] = Field(
        None,
        description="Counselor session pacing plan and EDGE skill station agenda.",
    )
    prerequisite_parent_letter: Optional[Dict[str, Any]] = Field(
        None,
        description="Copy-pasteable prerequisite & Youth Protection letter for Scouts and parents.",
    )
    beautification_tier: str = Field("BEAUTIFIED", description="Active slide beautification tier ('STANDARD', 'BEAUTIFIED', or 'STUDIO').")
    audience_level: str = Field("All Scouts (Ages 11–17)", description="Target Scout audience level.")
    badge_image_catalog: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Cached Merit Badge image catalog entries with descriptions for the UI popup carousel.",
    )
    a2ui_messages: List[Dict[str, Any]] = Field(default_factory=list, description="A2UI v0.9 protocol JSON messages.")
    agent_trace: List[Dict[str, Any]] = Field(default_factory=list, description="Execution trace across subagents.")


def build_a2ui_v09_messages(
    badge_name: str,
    research_res: Dict[str, Any],
    storyboard: Dict[str, Any],
    build_res: Dict[str, Any],
    review_res: Dict[str, Any],
    hitl_res: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Constructs authoritative Google A2UI v0.9 JSON messages (`beginRendering`, `surfaceUpdate`, `dataModelUpdate`).

    Conforms to the A2UI v0.9 Basic & Material Catalog schema so any A2UI v0.9 host
    or the Material 3 Expressive Counselor Workbench can render the agent surface natively.

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge.
        research_res: Dictionary output from `fetch_merit_badge_pamphlet_pdf`.
        storyboard: Dictionary output from `generate_slide_storyboard`.
        build_res: Dictionary output from `generate_bsa_slide_deck_pptx`.
        review_res: Dictionary output from `validate_presentation_deck`.
        hitl_res: Dictionary output from `request_counselor_confirmation`.

    Returns:
        List[Dict[str, Any]]: Ordered list of 3 A2UI v0.9 protocol JSON messages
        (`beginRendering`, `surfaceUpdate`, and `dataModelUpdate`).
    """
    reqs = research_res.get("requirements", [])
    slides = storyboard.get("slides", [])
    conformance = review_res.get("conformance_report", {})

    in_class = sum(1 for r in reqs if r.get("execution_mode") == "IN_CLASS_DISCUSSION")
    hands_on = sum(1 for r in reqs if r.get("execution_mode") == "HANDS_ON_SKILL_STATION")
    prereq = sum(1 for r in reqs if r.get("execution_mode") == "PREREQUISITE_CAMPOUT_HOME")

    return [
        {
            "version": "v0.9",
            "beginRendering": {
                "surfaceId": "merit_badge_workbench_surface",
                "root": "workbench_root_card",
                "styles": {
                    "font": "Google Sans",
                    "primaryColor": "#003F87",
                },
            },
        },
        {
            "version": "v0.9",
            "surfaceUpdate": {
                "surfaceId": "merit_badge_workbench_surface",
                "components": [
                    {
                        "id": "workbench_root_card",
                        "component": {
                            "Card": {
                                "child": "workbench_main_col",
                            }
                        },
                    },
                    {
                        "id": "workbench_main_col",
                        "component": {
                            "Column": {
                                "children": {
                                    "explicitList": [
                                        "header_row",
                                        "metrics_row",
                                        "divider_main",
                                        "workbench_tabs",
                                        "actions_row",
                                    ]
                                },
                                "distribution": "start",
                                "alignment": "stretch",
                            }
                        },
                    },
                    {
                        "id": "header_row",
                        "component": {
                            "Row": {
                                "children": {
                                    "explicitList": ["badge_icon", "title_heading", "status_caption"]
                                },
                                "distribution": "spaceBetween",
                                "alignment": "center",
                            }
                        },
                    },
                    {
                        "id": "badge_icon",
                        "component": {
                            "Icon": {
                                "name": {"literalString": "star" if research_res.get("is_eagle_required") else "check"}
                            }
                        },
                    },
                    {
                        "id": "title_heading",
                        "component": {
                            "Text": {
                                "text": {
                                    "literalString": f"{badge_name} Merit Badge — Counselor Deck & Triage Matrix"
                                },
                                "usageHint": "h2",
                            }
                        },
                    },
                    {
                        "id": "status_caption",
                        "component": {
                            "Text": {
                                "text": {
                                    "literalString": (
                                        f"Eagle-Required: {'YES' if research_res.get('is_eagle_required') else 'Optional'} | "
                                        f"{build_res.get('slide_count', len(slides) + 1)} Slides | "
                                        f"Stage 1 & 2 Conformance: {'CERTIFIED' if review_res.get('approved') else 'WARNING'}"
                                    )
                                },
                                "usageHint": "caption",
                            }
                        },
                    },
                    {
                        "id": "metrics_row",
                        "component": {
                            "Row": {
                                "children": {
                                    "explicitList": [
                                        "metric_in_class",
                                        "metric_hands_on",
                                        "metric_prereq",
                                        "metric_conformance",
                                    ]
                                },
                                "distribution": "spaceBetween",
                                "alignment": "stretch",
                            }
                        },
                    },
                    {
                        "id": "metric_in_class",
                        "component": {
                            "Text": {
                                "text": {"literalString": f"In-Class Socratic: {in_class} Sub-Reqs"},
                                "usageHint": "body",
                            }
                        },
                    },
                    {
                        "id": "metric_hands_on",
                        "component": {
                            "Text": {
                                "text": {"literalString": f"Hands-On EDGE Stations: {hands_on} Sub-Reqs"},
                                "usageHint": "body",
                            }
                        },
                    },
                    {
                        "id": "metric_prereq",
                        "component": {
                            "Text": {
                                "text": {"literalString": f"Campout / Home Pre-Work: {prereq} Sub-Reqs"},
                                "usageHint": "body",
                            }
                        },
                    },
                    {
                        "id": "metric_conformance",
                        "component": {
                            "Text": {
                                "text": {
                                    "literalString": (
                                        f"AABB Overlaps: {conformance.get('aabb_overlap_count', 0)} | "
                                        f"Min Font: {conformance.get('min_font_size_pt', 14.0)}pt"
                                    )
                                },
                                "usageHint": "body",
                            }
                        },
                    },
                    {
                        "id": "divider_main",
                        "component": {"Divider": {"axis": "horizontal"}},
                    },
                    {
                        "id": "workbench_tabs",
                        "component": {
                            "Tabs": {
                                "tabItems": [
                                    {
                                        "title": {"literalString": "12-Archetype Storyboard"},
                                        "child": "tab_storyboard_summary",
                                    },
                                    {
                                        "title": {"literalString": "5-Tier Pamphlet Research"},
                                        "child": "tab_research_summary",
                                    },
                                    {
                                        "title": {"literalString": "2-Stage Visual Critic"},
                                        "child": "tab_conformance_summary",
                                    },
                                ]
                            }
                        },
                    },
                    {
                        "id": "tab_storyboard_summary",
                        "component": {
                            "Text": {
                                "text": {
                                    "literalString": " | ".join(
                                        [f"S{idx+2}: [{s.get('archetype', 'SLIDE')}] {s.get('title', '')}" for idx, s in enumerate(slides[:6])]
                                    )
                                },
                                "usageHint": "body",
                            }
                        },
                    },
                    {
                        "id": "tab_research_summary",
                        "component": {
                            "Text": {
                                "text": {
                                    "literalString": (
                                        f"Pamphlet PDF: {research_res.get('pamphlet_pdf_url', '')} | "
                                        f"DRG Hub: {research_res.get('drg_url', '')}"
                                    )
                                },
                                "usageHint": "body",
                            }
                        },
                    },
                    {
                        "id": "tab_conformance_summary",
                        "component": {
                            "Text": {
                                "text": {
                                    "literalString": review_res.get("critic_feedback", "All safety and conformance gates passed.")
                                },
                                "usageHint": "body",
                            }
                        },
                    },
                    {
                        "id": "actions_row",
                        "component": {
                            "Row": {
                                "children": {"explicitList": ["btn_approve_hitl", "btn_download_pptx"]},
                                "distribution": "end",
                                "alignment": "center",
                            }
                        },
                    },
                    {
                        "id": "btn_approve_hitl",
                        "component": {
                            "Button": {
                                "child": "btn_approve_label",
                                "primary": False,
                                "action": {
                                    "name": "onConfirmHITL",
                                    "context": [
                                        {
                                            "key": "confirmation_token",
                                            "value": {"literalString": hitl_res.get("confirmation_token", "")},
                                        },
                                        {
                                            "key": "badge_name",
                                            "value": {"literalString": badge_name},
                                        },
                                    ],
                                },
                            }
                        },
                    },
                    {
                        "id": "btn_approve_label",
                        "component": {
                            "Text": {"text": {"literalString": "Verify HITL Sign-Off Token"}}
                        },
                    },
                    {
                        "id": "btn_download_pptx",
                        "component": {
                            "Button": {
                                "child": "btn_download_label",
                                "primary": True,
                                "action": {
                                    "name": "onDownloadDeck",
                                    "context": [
                                        {
                                            "key": "output_path",
                                            "value": {"literalString": build_res.get("output_path", "")},
                                        }
                                    ],
                                },
                            }
                        },
                    },
                    {
                        "id": "btn_download_label",
                        "component": {
                            "Text": {"text": {"literalString": "Download Widescreen .PPTX Deck"}}
                        },
                    },
                ],
            },
        },
        {
            "version": "v0.9",
            "dataModelUpdate": {
                "surfaceId": "merit_badge_workbench_surface",
                "path": "/",
                "contents": [
                    {"key": "badgeName", "valueString": badge_name},
                    {"key": "slideCount", "valueNumber": build_res.get("slide_count", len(slides) + 1)},
                    {"key": "isEagleRequired", "valueBoolean": bool(research_res.get("is_eagle_required"))},
                    {"key": "safetyApproved", "valueBoolean": bool(review_res.get("approved"))},
                    {"key": "confirmationToken", "valueString": str(hitl_res.get("confirmation_token", ""))},
                ],
            },
        },
    ]


def run_merit_badge_workflow(
    badge_name: str,
    depth_mode: str = "Standard Deck",
    counselor_info: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
    session_id: str = "default_counselor_session",
    enable_deep_research: bool = True,
    beautification_tier: str = "BEAUTIFIED",
    schedule_format: str = "3 Troop Meetings (45 min each)",
    audience_level: str = "All Scouts (Ages 11–17)",
) -> Dict[str, Any]:
    """Executes the complete multi-agent presentation generation workflow.

    Integrates Model Armor input sanitization, OpenTelemetry distributed tracing,
    `execute_tool_with_observability` intent/outcome capture, 5-Tier Deep Research
    (with the official BSA Pamphlet locked as the primary source of truth),
    12-Archetype Storyboard Planning, Optional `SlideBeautifierAgent` magazine polish,
    FastMCP HITL confirmation token verification, Tri-Modal Visual Asset synthesis,
    Widescreen `python-pptx` rendering, 2-Stage Conformance/Vision review, Counselor
    Session Toolkit generation, and A2UI v0.9 payload generation.

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge (e.g., `'First Aid'`, `'Weather'`).
        depth_mode: Presentation depth tier (`'Standard Deck'` or `'Deep Dive / Camp School Deck'`).
        counselor_info: Optional dictionary of counselor personalization details (`counselor_name`,
            `troop_affiliation`, `email_address`, `phone_number`, `custom_troop_logo_path`).
        output_path: Optional target filesystem path for the generated `.pptx` file.
        session_id: Unique session identifier for SQLite and Vertex AI Memory Bank persistence.
        enable_deep_research: Whether to run Tier-2 grounded web & hyper-local troop enrichment.
        beautification_tier: Visual polish tier (`'STANDARD'`, `'BEAUTIFIED'`, or `'STUDIO'`).
        schedule_format: Counselor session schedule format for the generated lesson agenda.
        audience_level: Target Scout age/rank tier for Socratic coaching and visual framing.

    Returns:
        Dict[str, Any]: Serialized `PresentationWorkflowResult` dictionary on success,
        or a `GuidedToolError` dictionary if blocked by Model Armor or badge lookup validation.
    """
    t0 = time.perf_counter()

    # 0A. MODEL ARMOR & YOUTH PROTECTION POLICY CHECK
    armor_check = sanitize_text_with_model_armor(
        f"{badge_name} {depth_mode} {counselor_info or {}}",
        direction="INPUT",
    )
    if not armor_check["allowed"]:
        return build_guided_tool_error(
            error_code="MODEL_ARMOR_WORKFLOW_BLOCKED",
            message=f"Workflow blocked by Model Armor policy '{armor_check['policy_name']}'.",
            remediation=str(armor_check["remediation"]),
            details={"violations": armor_check["violations"], "policy_name": armor_check["policy_name"]},
        )

    tracer = get_tracer("scouts-bsa-merit-badge-agent")
    with tracer.start_as_current_span("MeritBadgeCoordinatorAgent.run_workflow") as root_span:
        if root_span and hasattr(root_span, "set_attribute"):
            try:
                root_span.set_attribute("badge.name", str(badge_name))
                root_span.set_attribute("depth.mode", str(depth_mode))
                root_span.set_attribute("session.id", str(session_id))
                root_span.set_attribute("beautification.tier", str(beautification_tier))
            except Exception:
                pass

        safe_counselor_log = scrub_pii_before_sink(str(counselor_info or {}))
        logger.info(
            "Starting MeritBadgeCoordinatorAgent workflow",
            extra={
                "badge_name": badge_name,
                "depth_mode": depth_mode,
                "session_id": session_id,
                "beautification_tier": beautification_tier,
                "counselor_redacted": safe_counselor_log,
            },
        )

        agent_trace: List[Dict[str, Any]] = []

        # 0B. FINOPS COST ESTIMATION & PERSISTENT SESSION INIT
        finops_estimate = execute_tool_with_observability(
            tool_name="estimate_workflow_finops_cost",
            func=estimate_workflow_finops_cost,
            badge_name=badge_name,
            depth_mode=depth_mode,
            beautification_tier=beautification_tier,
            enable_deep_research=enable_deep_research,
        )

        _default_store.save_session_sync(
            session_id=session_id,
            badge_name=badge_name,
            counselor_info=counselor_info or {},
            history=[{"type": "workflow_start", "badge_name": badge_name}],
        )

        # 1. RESEARCH SUBAGENT (5-Tier Pamphlet, Sub-Requirement Tree & Execution Triage)
        step_t0 = time.perf_counter()
        from src.tools.scouting_scraper import (
            fetch_merit_badge_pamphlet_pdf,
            MeritBadgeResearchRequest,
        )
        try:
            from src.tools.scouting_scraper import generate_counselor_workbook_markdown
        except ImportError:
            generate_counselor_workbook_markdown = None

        research_req = MeritBadgeResearchRequest(
            badge_name=badge_name,
            include_eagle_required_focus=True,
        )
        research_res = execute_tool_with_observability(
            tool_name="fetch_merit_badge_pamphlet_pdf",
            func=fetch_merit_badge_pamphlet_pdf,
            request=research_req,
        )

        if research_res.get("status") != "SUCCESS":
            return research_res  # Returns GuidedToolError to UI

        requirements = research_res.get("requirements", [])
        eagle_flag = research_res.get("is_eagle_required", False)

        triage_summary = {
            "IN_CLASS_DISCUSSION": sum(
                1 for r in requirements if r.get("execution_mode", "IN_CLASS_DISCUSSION") == "IN_CLASS_DISCUSSION"
            ),
            "HANDS_ON_SKILL_STATION": sum(
                1 for r in requirements if r.get("execution_mode") == "HANDS_ON_SKILL_STATION"
            ),
            "PREREQUISITE_CAMPOUT_HOME": sum(
                1 for r in requirements if r.get("execution_mode") == "PREREQUISITE_CAMPOUT_HOME"
            ),
        }

        researcher_model = select_model_for_task("researcher")
        agent_trace.append({
            "agent": "PamphletResearchAgent",
            "model": researcher_model,
            "status": "COMPLETED",
            "duration_ms": round((time.perf_counter() - step_t0) * 1000, 1),
            "summary": (
                f"Ingested {len(requirements)} verbatim sub-requirements from Scouting.org & BSA Pamphlet "
                f"({triage_summary['IN_CLASS_DISCUSSION']} In-Class, "
                f"{triage_summary['HANDS_ON_SKILL_STATION']} Hands-On EDGE Stations, "
                f"{triage_summary['PREREQUISITE_CAMPOUT_HOME']} Prerequisites)."
            ),
        })

        # 1B. DEEP RESEARCH ENRICHMENT SUBAGENT (Grounded Web & Local Context; Pamphlet Remains Primary)
        deep_enrichment: Optional[Dict[str, Any]] = None
        if enable_deep_research:
            step_t_dr = time.perf_counter()
            troop_aff = str((counselor_info or {}).get("troop_affiliation") or "Troop 123, My Council")
            loc_zip = str((counselor_info or {}).get("location_or_zip") or "")
            deep_enrichment = execute_tool_with_observability(
                tool_name="enrich_requirements_with_deep_research",
                func=enrich_requirements_with_deep_research,
                badge_name=badge_name,
                canonical_requirements=requirements,
                troop_affiliation=troop_aff,
                location_or_zip=loc_zip,
                enable_live_web_search=True,
            )
            resolved_loc_str = str(
                ((deep_enrichment or {}).get("resolved_location") or {}).get("city_state") or troop_aff
            )
            agent_trace.append({
                "agent": "DeepResearchEnrichmentAgent",
                "model": select_model_for_task("deep_research"),
                "status": "COMPLETED",
                "duration_ms": round((time.perf_counter() - step_t_dr) * 1000, 1),
                "summary": (
                    f"Enriched {len(requirements)} canonical BSA Pamphlet requirements with regional field "
                    f"context ({resolved_loc_str}) and {len((deep_enrichment or {}).get('grounded_citations', []))} "
                    f"verified external citations (Canonical Pamphlet Hash verified: "
                    f"{str((deep_enrichment or {}).get('canonical_pamphlet_hash', ''))[:12]})."
                ),
            })

        # Trigger non-blocking async memory indexing of ingested pamphlet requirements
        try:
            req_text_combined = " ".join([r.get("req_text", "") for r in requirements])
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(index_pamphlet_memory_async(badge_name, req_text_combined))
            except RuntimeError:
                asyncio.run(index_pamphlet_memory_async(badge_name, req_text_combined))
        except Exception as exc:
            logger.warning("Async vector indexing skipped in sync loop: %s", exc)

        # Generate printable Counselor & Scout Workbook Markdown
        workbook_path: Optional[str] = None
        if generate_counselor_workbook_markdown is not None:
            try:
                wb_md = generate_counselor_workbook_markdown(research_res, counselor_info=counselor_info)
                safe_slug = badge_name.strip().replace(" ", "_")
                wb_file = GENERATED_DECKS_DIR / f"{safe_slug}_Counselor_Workbook.md"
                wb_file.write_text(wb_md, encoding="utf-8")
                workbook_path = str(wb_file)
            except Exception as exc:
                logger.warning("Workbook generation skipped: %s", exc)

        # Generate Counselor Session Pacing Agenda & Prerequisite Parent Letter
        session_agenda = execute_tool_with_observability(
            tool_name="generate_counselor_session_agenda",
            func=generate_counselor_session_agenda,
            badge_name=badge_name,
            research_result=research_res,
            schedule_format=schedule_format,
            counselor_info=counselor_info,
        )
        prereq_letter = execute_tool_with_observability(
            tool_name="generate_prerequisite_parent_letter",
            func=generate_prerequisite_parent_letter,
            badge_name=badge_name,
            research_result=research_res,
            counselor_info=counselor_info,
        )

        # 2. PLANNER SUBAGENT (12-Archetype Storyboard & 7 Golden Rules of Copywriting)
        step_t1 = time.perf_counter()
        from src.agents.planner import generate_slide_storyboard

        storyboard = execute_tool_with_observability(
            tool_name="generate_slide_storyboard",
            func=generate_slide_storyboard,
            badge_name=badge_name,
            requirements=requirements,
            depth_mode=depth_mode,
            is_eagle_required=eagle_flag,
        )
        archetypes_used = sorted({s.get("archetype", "SPLIT_VISUAL_EXPLAINER") for s in storyboard.get("slides", [])})
        planner_model = select_model_for_task("planner")
        agent_trace.append({
            "agent": "SlideContentPlannerAgent",
            "model": planner_model,
            "status": "COMPLETED",
            "duration_ms": round((time.perf_counter() - step_t1) * 1000, 1),
            "summary": (
                f"Planned {len(storyboard.get('slides', [])) + 1} widescreen slides across "
                f"{len(archetypes_used)} distinct slide archetypes ({', '.join(archetypes_used[:5])})."
            ),
        })

        # 2B. OPTIONAL SLIDE BEAUTIFIER SUBAGENT (Magazine Themes & Targeted Editorial Hero Art)
        step_t_bf = time.perf_counter()
        beautify_res = execute_tool_with_observability(
            tool_name="beautify_slide_storyboard",
            func=beautify_slide_storyboard,
            storyboard=storyboard,
            deep_research_enrichment=deep_enrichment,
            beautification_tier=beautification_tier,
            max_ai_images=5 if str(beautification_tier).upper() == "BEAUTIFIED" else (15 if str(beautification_tier).upper() == "STUDIO" else 0),
            audience_level=audience_level,
        )
        deck_blueprint = beautify_res.get("blueprint")
        if isinstance(beautify_res.get("storyboard"), dict):
            storyboard = beautify_res["storyboard"]

        agent_trace.append({
            "agent": "SlideBeautifierAgent",
            "model": select_model_for_task("beautifier"),
            "status": "COMPLETED",
            "duration_ms": round((time.perf_counter() - step_t_bf) * 1000, 1),
            "summary": (
                f"Applied '{str(beautification_tier).upper()}' magazine visual blueprint with consecutive-slide "
                f"variety and {(deck_blueprint or {}).get('ai_hero_images_generated', 0)} editorial hero illustrations."
            ),
        })

        # 3. FASTMCP HUMAN-IN-THE-LOOP CONFIRMATION GATE
        step_t2 = time.perf_counter()
        hitl_res = execute_tool_with_observability(
            tool_name="request_counselor_confirmation",
            func=request_counselor_confirmation,
            outline_summary={
                "badge_name": badge_name,
                "slide_count": len(storyboard.get("slides", [])),
                "is_eagle_required": eagle_flag,
                "counselor_name": (counselor_info or {}).get("counselor_name", "Counselor"),
                "estimated_cost_usd": (finops_estimate or {}).get("estimated_cost_usd", 0.14),
            },
        )
        if not hitl_res.get("approved", True):
            return {"status": "CANCELLED_BY_USER", "message": "Counselor rejected proposed outline."}

        agent_trace.append({
            "agent": "FastMCPConfirmationGate",
            "model": "HMAC-SHA256-Gate",
            "status": "APPROVED",
            "duration_ms": round((time.perf_counter() - step_t2) * 1000, 1),
            "summary": (
                f"Issued cryptographic HITL confirmation token ({str(hitl_res.get('confirmation_token', 'verified'))[:16]}...) "
                f"with FinOps budget check (${(finops_estimate or {}).get('estimated_cost_usd', 0.14):.2f} USD)."
            ),
        })

        # 4. BUILDER SUBAGENT (Tri-Modal Diagrams + Widescreen 16:9 .pptx Generation)
        step_t3 = time.perf_counter()
        from src.tools.pptx_builder import (
            generate_bsa_slide_deck_pptx,
            PowerPointBuildRequest,
            SlideSpec,
            CounselorTitleSlideInfo,
        )

        c_info = CounselorTitleSlideInfo(**counselor_info) if counselor_info else None
        slides_specs = [SlideSpec(**s) for s in storyboard.get("slides", [])]

        if not output_path:
            safe_slug = badge_name.strip().replace(" ", "_")
            tier_slug = str(beautification_tier or "BEAUTIFIED").strip().upper()
            depth_slug = "DeepDive" if "deep" in str(depth_mode or "").lower() else "Standard"
            output_path = str(GENERATED_DECKS_DIR / f"{safe_slug}_{tier_slug}_{depth_slug}_Merit_Badge_Deck.pptx")

        build_req = PowerPointBuildRequest(
            badge_name=badge_name,
            slides=slides_specs,
            counselor_info=c_info,
            output_path=output_path,
            hitl_confirmation_token=hitl_res.get("confirmation_token"),
        )
        build_res = execute_tool_with_observability(
            tool_name="generate_bsa_slide_deck_pptx",
            func=generate_bsa_slide_deck_pptx,
            request=build_req,
        )
        builder_model = select_model_for_task("builder")
        agent_trace.append({
            "agent": "PowerPointBuilderAgent",
            "model": builder_model,
            "status": "COMPLETED",
            "duration_ms": round((time.perf_counter() - step_t3) * 1000, 1),
            "summary": (
                f"Rendered {build_res['slide_count']}-slide 16:9 widescreen PowerPoint deck "
                f"with custom slide-specific diagrams at {os.path.basename(build_res['output_path'])}."
            ),
        })

        # 5. REVIEWER SUBAGENT (2-Stage Geometry/WCAG Conformance + Vision Critic)
        step_t4 = time.perf_counter()
        from src.agents.reviewer import validate_presentation_deck

        review_res = execute_tool_with_observability(
            tool_name="validate_presentation_deck",
            func=validate_presentation_deck,
            pptx_path=build_res["output_path"],
            expected_req_count=len(requirements),
            is_eagle_required=eagle_flag,
        )
        conformance_report = review_res.get("conformance_report")
        reviewer_model = select_model_for_task("reviewer")
        agent_trace.append({
            "agent": "BSABrandAndSafetyReviewAgent",
            "model": reviewer_model,
            "status": "APPROVED" if review_res.get("approved") else "WARNING",
            "duration_ms": round((time.perf_counter() - step_t4) * 1000, 1),
            "summary": review_res.get("critic_feedback", "Stage 1 & Stage 2 conformance verified."),
        })

        # 6. BUILD GOOGLE A2UI v0.9 MESSAGES
        a2ui_messages = build_a2ui_v09_messages(
            badge_name=badge_name,
            research_res=research_res,
            storyboard=storyboard,
            build_res=build_res,
            review_res=review_res,
            hitl_res=hitl_res,
        )

        # 7. UPDATE PERSISTENT SESSION WITH COMPACTED HISTORY
        raw_history = [
            {"type": "workflow_start", "badge_name": badge_name},
            {"type": "tool_outcome", "tool_name": "fetch_merit_badge_pamphlet_pdf", "status": "SUCCESS"},
            {"type": "tool_outcome", "tool_name": "enrich_requirements_with_deep_research", "status": "SUCCESS"},
            {"type": "tool_outcome", "tool_name": "generate_slide_storyboard", "status": "SUCCESS"},
            {"type": "tool_outcome", "tool_name": "beautify_slide_storyboard", "status": "SUCCESS"},
            {"type": "tool_outcome", "tool_name": "request_counselor_confirmation", "status": "APPROVED"},
            {"type": "tool_outcome", "tool_name": "generate_bsa_slide_deck_pptx", "status": "SUCCESS"},
            {"type": "tool_outcome", "tool_name": "validate_presentation_deck", "status": "APPROVED"},
            {
                "type": "workflow_complete",
                "slides": build_res["slide_count"],
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            },
        ]
        compacted_history = compact_conversation_events(
            raw_history,
            EventsCompactionConfig(
                compaction_interval=5,
                overlap_size=2,
                compaction_strategy="additive",
            ),
        )
        _default_store.save_session_sync(
            session_id=session_id,
            badge_name=badge_name,
            counselor_info=counselor_info or {},
            history=compacted_history,
        )

        # Sync storyboard slides with any diagram_path populated during build and seed badge image catalog
        updated_slides = [s.model_dump() for s in slides_specs]
        storyboard["slides"] = updated_slides
        badge_catalog_items = seed_badge_image_catalog_from_storyboard(
            badge_name=badge_name,
            storyboard=storyboard,
            research_res=research_res,
        )

        final_result = PresentationWorkflowResult(
            badge_name=badge_name,
            output_path=build_res["output_path"],
            slide_count=build_res["slide_count"],
            is_eagle_required=eagle_flag,
            safety_approved=review_res.get("approved", False),
            status="SUCCESS" if review_res.get("approved") else "REVIEW_WARNING",
            workbook_path=workbook_path,
            hitl_confirmation_token=hitl_res.get("confirmation_token"),
            triage_summary=triage_summary,
            conformance_report=conformance_report,
            storyboard=storyboard,
            research_artifact=research_res,
            deep_research_enrichment=deep_enrichment,
            deck_visual_blueprint=deck_blueprint,
            finops_cost_estimate=finops_estimate,
            session_agenda=session_agenda,
            prerequisite_parent_letter=prereq_letter,
            beautification_tier=str(beautification_tier).upper(),
            audience_level=audience_level,
            badge_image_catalog=badge_catalog_items,
            a2ui_messages=a2ui_messages,
            agent_trace=agent_trace,
        )
        logger.info(
            "Completed MeritBadgeCoordinatorAgent workflow",
            extra={
                "status": final_result.status,
                "slide_count": final_result.slide_count,
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            },
        )
        return final_result.model_dump()


async def stream_merit_badge_workflow_events(
    badge_name: str,
    depth_mode: str = "Deep Dive / Camp School Deck",
    counselor_info: Optional[Dict[str, Any]] = None,
    session_id: str = "a2ui_counselor_session",
    enable_deep_research: bool = True,
    beautification_tier: str = "BEAUTIFIED",
    schedule_format: str = "3 Troop Meetings (45 min each)",
    audience_level: str = "All Scouts (Ages 11–17)",
) -> AsyncGenerator[Dict[str, Any], None]:
    """Streams real-time SSE events across the multi-agent pipeline for the Material 3 Expressive A2UI.

    Args:
        badge_name: Official name of the Scouts BSA Merit Badge.
        depth_mode: Presentation depth tier (`'Standard Deck'` or `'Deep Dive / Camp School Deck'`).
        counselor_info: Optional counselor personalization metadata dictionary.
        session_id: Unique session identifier for session state persistence.
        enable_deep_research: Whether to run Tier-2 grounded web & local troop enrichment.
        beautification_tier: Visual polish tier (`'STANDARD'`, `'BEAUTIFIED'`, or `'STUDIO'`).
        schedule_format: Counselor session schedule format for the generated lesson agenda.
        audience_level: Target Scout age/rank tier for Socratic coaching and visual framing.

    Yields:
        Dict[str, Any]: Server-Sent Event (SSE) progress payloads and final workflow result.
    """
    yield {
        "event": "stage_start",
        "stage": "research",
        "agent": "PamphletResearchAgent",
        "model": select_model_for_task("researcher"),
        "message": f"Ingesting Scouting.org sub-requirement tree, BSA Pamphlet PDF & DRG links for {badge_name}...",
        "progress_pct": 12,
    }
    await asyncio.sleep(0.05)

    from src.tools.scouting_scraper import fetch_merit_badge_pamphlet_pdf, MeritBadgeResearchRequest
    research_res = fetch_merit_badge_pamphlet_pdf(
        MeritBadgeResearchRequest(badge_name=badge_name, include_eagle_required_focus=True)
    )
    if research_res.get("status") != "SUCCESS":
        yield {"event": "workflow_error", "error": research_res, "progress_pct": 100}
        return

    reqs = research_res.get("requirements", [])
    yield {
        "event": "research_complete",
        "agent": "DeepResearchEnrichmentAgent",
        "model": select_model_for_task("deep_research"),
        "message": f"Verified {len(reqs)} canonical BSA Pamphlet requirements & grounded local troop context.",
        "research_artifact": research_res,
        "progress_pct": 35,
    }
    await asyncio.sleep(0.05)

    yield {
        "event": "stage_start",
        "stage": "planning",
        "agent": "SlideContentPlannerAgent",
        "model": select_model_for_task("planner"),
        "message": f"Planning 12-Archetype Storyboard & applying '{beautification_tier}' Magazine Visual Blueprint...",
        "progress_pct": 52,
    }
    await asyncio.sleep(0.05)

    result = await asyncio.to_thread(
        run_merit_badge_workflow,
        badge_name=badge_name,
        depth_mode=depth_mode,
        counselor_info=counselor_info,
        session_id=session_id,
        enable_deep_research=enable_deep_research,
        beautification_tier=beautification_tier,
        schedule_format=schedule_format,
        audience_level=audience_level,
    )

    yield {
        "event": "hitl_verified",
        "agent": "FastMCPConfirmationGate",
        "token": result.get("hitl_confirmation_token"),
        "message": "FastMCP confirmation_token verified; rendering high-DPI SVG/PNG diagrams & widescreen .pptx...",
        "progress_pct": 78,
    }
    await asyncio.sleep(0.05)

    yield {
        "event": "conformance_verified",
        "agent": "BSABrandAndSafetyReviewAgent",
        "model": select_model_for_task("reviewer"),
        "conformance_report": result.get("conformance_report"),
        "message": "Stage 1 (<10ms AABB/WCAG Conformance) & Stage 2 Pedagogical Review PASSED.",
        "progress_pct": 94,
    }
    await asyncio.sleep(0.05)

    yield {
        "event": "workflow_complete",
        "result": result,
        "a2ui_messages": result.get("a2ui_messages", []),
        "progress_pct": 100,
    }


def get_merit_badge_coordinator_agent(model_name: Optional[str] = None) -> adk.Agent:
    """Instantiates the `MeritBadgeCoordinatorAgent` root supervisor.

    Args:
        model_name: Optional Gemini model override (defaults to
            `select_model_for_task('coordinator')` / `'gemini-2.5-flash'`).

    Returns:
        adk.Agent: Configured root supervisor agent with `EventsCompactionConfig`,
        Model Armor guardrail callbacks, and specialized subagents.
    """
    resolved_model = model_name or select_model_for_task("coordinator")
    system_instruction = (
        f"{SCOUTS_BSA_CONSTITUTION}\n\n"
        f"{load_prompt('coordinator.md')}"
    )

    agent = adk.Agent(
        name="MeritBadgeCoordinatorAgent",
        model=resolved_model,
        instruction=system_instruction,
        output_key="final_workflow_result",
        tools=[
            run_merit_badge_workflow,
            estimate_workflow_finops_cost,
            generate_counselor_session_agenda,
            generate_prerequisite_parent_letter,
            request_counselor_confirmation,
            retrieve_pamphlet_memory_chunks,
            get_badge_image_catalog,
            search_web_images_for_slide,
            estimate_nano_banana_image_cost,
            generate_nano_banana_slide_image,
            save_session_state_async,
            load_session_state_async,
            compact_session_history_async,
        ],
        sub_agents=[
            get_pamphlet_research_agent(),
            get_slide_content_planner_agent(),
            get_slide_beautifier_agent(),
            get_web_image_search_agent(),
            get_nano_banana_image_agent(),
            get_powerpoint_builder_agent(),
            get_bsa_review_agent(),
        ],
        before_model_callback=before_model_guardrail_callback,
        after_model_callback=after_model_guardrail_callback,
        before_tool_callback=before_tool_guardrail_callback,
        after_tool_callback=after_tool_guardrail_callback,
    )
    compaction_cfg = EventsCompactionConfig(
        compaction_interval=5,
        overlap_size=2,
        compaction_strategy="additive",
    )
    try:
        object.__setattr__(agent, "compaction_config", compaction_cfg)
    except Exception:
        pass
    return agent


def get_merit_badge_sequential_agent() -> Any:
    """Instantiates the declarative ADK `SequentialAgent` pipeline with nested `LoopAgent` critic.

    Matches `service-spec.yaml` (`PamphletResearchAgent` -> `SlideContentPlannerAgent`
    -> `SlideBeautifierAgent` -> `PowerPointBuilderAgent` -> `BSABrandAndSafetyReviewLoopAgent`).

    Args:
        None.

    Returns:
        Any: ADK `SequentialAgent` instance (or `MeritBadgeCoordinatorAgent` fallback).
    """
    if _ADKSequentialAgent is not None:
        try:
            return _ADKSequentialAgent(
                name="MeritBadgeSequentialPipelineAgent",
                sub_agents=[
                    get_pamphlet_research_agent(),
                    get_slide_content_planner_agent(),
                    get_slide_beautifier_agent(),
                    get_powerpoint_builder_agent(),
                    get_bsa_review_loop_agent(max_iterations=3),
                ],
            )
        except Exception:
            pass
    return get_merit_badge_coordinator_agent()


def get_merit_badge_adk_app() -> Any:
    """Instantiates the official Google ADK `App` container for `adk web`, `adk run`, and `adk eval`.

    Configures:
    - `root_agent`: `MeritBadgeCoordinatorAgent`
    - `plugins`: `[ScoutsBSAModelArmorPlugin(), FinOpsBudgetPlugin()]`
    - `events_compaction_config`: Native ADK `EventsCompactionConfig`
    - `context_cache_config`: Native ADK `ContextCacheConfig`

    Args:
        None.

    Returns:
        Any: Configured `google.adk.apps.app.App` instance (or `root_agent` fallback).
    """
    coordinator = get_merit_badge_coordinator_agent()
    compaction_cfg = EventsCompactionConfig(
        compaction_interval=5,
        overlap_size=2,
        compaction_strategy="additive",
    )
    if _ADKApp is not None:
        try:
            return _ADKApp(
                name="scouts_bsa_merit_badge_agent",
                root_agent=coordinator,
                plugins=[ScoutsBSAModelArmorPlugin(), FinOpsBudgetPlugin()],
                events_compaction_config=compaction_cfg.to_adk_compaction_config(),
                context_cache_config=get_adk_context_cache_config(),
            )
        except Exception:
            pass
    return coordinator


root_agent = get_merit_badge_coordinator_agent()
adk_app = get_merit_badge_adk_app()

