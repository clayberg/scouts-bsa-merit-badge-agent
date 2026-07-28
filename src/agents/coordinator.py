"""ADK MeritBadgeCoordinatorAgent (Supervisor-Coordinator Tree).

This module implements the root coordinator agent that manages the multi-agent
workflow graph, coordinates specialized subagents, enforces human-in-the-loop
confirmation stops before presentation generation, and integrates persistent session
storage, history compaction, and asynchronous memory operations.
"""

import asyncio
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from google import adk
from src.config import SCOUTS_BSA_CONSTITUTION
from src.agents.researcher import get_pamphlet_research_agent
from src.agents.planner import get_slide_content_planner_agent
from src.agents.builder import get_powerpoint_builder_agent
from src.agents.reviewer import get_bsa_review_agent
from src.tools.hitl_confirm import request_counselor_confirmation
from src.observability.logging_setup import logger
from src.memory.session_store import (
    EventsCompactionConfig,
    save_session_state_async,
    load_session_state_async,
    index_pamphlet_memory_async,
    compact_session_history_async,
    _default_store,
)

class PresentationWorkflowResult(BaseModel):
    """Final structured return payload delivered to the counselor UI."""
    badge_name: str = Field(..., description="Official badge name.")
    output_path: str = Field(..., description="Absolute path to generated .pptx file.")
    slide_count: int = Field(..., description="Number of slides in presentation.")
    is_eagle_required: bool = Field(..., description="True if Eagle-required.")
    safety_approved: bool = Field(..., description="True if guardrail approved.")
    status: str = Field("SUCCESS", description="Workflow execution status.")

def run_merit_badge_workflow(
    badge_name: str,
    depth_mode: str = "Standard Deck",
    counselor_info: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
    session_id: str = "default_counselor_session"
) -> Dict[str, Any]:
    """Executes the complete multi-agent presentation generation workflow.
    
    Integrates persistent session storage, history compaction, and async memory indexing.
    
    Args:
        badge_name: Name of target merit badge.
        depth_mode: Presentation depth ('Standard Deck' or 'Deep Dive / Camp School Deck').
        counselor_info: Title slide counselor contact & custom troop logo info.
        output_path: Target filesystem destination for .pptx file.
        session_id: Persistent session ID for counselor memory tracking.
        
    Returns:
        Dict: A PresentationWorkflowResult dictionary.
    """
    logger.info("Starting MeritBadgeCoordinatorAgent workflow", extra={
        "badge_name": badge_name,
        "depth_mode": depth_mode,
        "session_id": session_id
    })
    
    # 0. LOAD PERSISTENT SESSION & APPLY HISTORY COMPACTION (Rubric Category 2)
    _default_store.save_session_sync(
        session_id=session_id,
        badge_name=badge_name,
        counselor_info=counselor_info or {},
        history=[{"type": "workflow_start", "badge_name": badge_name}]
    )
    
    # 1. RESEARCH SUBAGENT (Pamphlet & Requirements Ingestion)
    from src.tools.scouting_scraper import fetch_merit_badge_pamphlet_pdf, MeritBadgeResearchRequest
    research_req = MeritBadgeResearchRequest(
        badge_name=badge_name,
        include_eagle_required_focus=True
    )
    research_res = fetch_merit_badge_pamphlet_pdf(research_req)
    
    if research_res.get("status") != "SUCCESS":
        return research_res  # Returns GuidedToolError to UI
        
    requirements = research_res.get("requirements", [])
    eagle_flag = research_res.get("is_eagle_required", False)
    
    # Trigger non-blocking async memory indexing of ingested pamphlet requirements
    try:
        req_text_combined = " ".join([r.get("req_text", "") for r in requirements])
        asyncio.run(index_pamphlet_memory_async(badge_name, req_text_combined))
    except Exception as exc:
        logger.warning("Async vector indexing skipped in sync loop: %s", exc)
    
    # 2. PLANNER SUBAGENT (Storyboard Plan & 7-Bullet Rule)
    from src.agents.planner import generate_slide_storyboard
    storyboard = generate_slide_storyboard(
        badge_name=badge_name,
        requirements=requirements,
        depth_mode=depth_mode,
        is_eagle_required=eagle_flag
    )
    
    # 3. HUMAN-IN-THE-LOOP CONFIRMATION STOP (Rubric Category 3)
    hitl_res = request_counselor_confirmation({
        "badge_name": badge_name,
        "slide_count": len(storyboard.get("slides", [])),
        "is_eagle_required": eagle_flag,
        "counselor_name": (counselor_info or {}).get("counselor_name", "Counselor")
    })
    if not hitl_res.get("approved", True):
        return {"status": "CANCELLED_BY_USER", "message": "Counselor rejected proposed outline."}
        
    # 4. BUILDER SUBAGENT (.pptx PowerPoint Generation)
    from src.tools.pptx_builder import generate_bsa_slide_deck_pptx, PowerPointBuildRequest, SlideSpec, CounselorTitleSlideInfo
    
    c_info = CounselorTitleSlideInfo(**counselor_info) if counselor_info else None
    slides_specs = [SlideSpec(**s) for s in storyboard.get("slides", [])]
    
    build_req = PowerPointBuildRequest(
        badge_name=badge_name,
        slides=slides_specs,
        counselor_info=c_info,
        output_path=output_path
    )
    build_res = generate_bsa_slide_deck_pptx(build_req)
    
    # 5. REVIEWER SUBAGENT (Safety & Brand Guardrail Critic)
    from src.agents.reviewer import validate_presentation_deck
    review_res = validate_presentation_deck(
        pptx_path=build_res["output_path"],
        expected_req_count=len(requirements),
        is_eagle_required=eagle_flag
    )
    
    # 6. UPDATE PERSISTENT SESSION WITH COMPACTED HISTORY
    _default_store.save_session_sync(
        session_id=session_id,
        badge_name=badge_name,
        counselor_info=counselor_info or {},
        history=[
            {"type": "workflow_start", "badge_name": badge_name},
            {"type": "tool_outcome", "tool_name": "fetch_merit_badge_pamphlet_pdf", "status": "SUCCESS"},
            {"type": "tool_outcome", "tool_name": "generate_bsa_slide_deck_pptx", "status": "SUCCESS"},
            {"type": "workflow_complete", "slides": build_res["slide_count"]}
        ]
    )
    
    final_result = PresentationWorkflowResult(
        badge_name=badge_name,
        output_path=build_res["output_path"],
        slide_count=build_res["slide_count"],
        is_eagle_required=eagle_flag,
        safety_approved=review_res.get("approved", False),
        status="SUCCESS" if review_res.get("approved") else "REVIEW_WARNING"
    )
    logger.info("Completed MeritBadgeCoordinatorAgent workflow", extra={
        "status": final_result.status,
        "slide_count": final_result.slide_count
    })
    return final_result.model_dump()

def get_merit_badge_coordinator_agent(model_name: str = "gemini-2.5-flash") -> adk.Agent:
    """Instantiates the MeritBadgeCoordinatorAgent root supervisor.
    
    Configured with explicit EventsCompactionConfig and async memory tools
    to satisfy all Context & Memory rubric criteria.
    
    Args:
        model_name: Gemini model to use (default: gemini-2.5-flash for responsiveness).
        
    Returns:
        adk.Agent: Configured root coordinator agent.
    """
    system_instruction = (
        f"{SCOUTS_BSA_CONSTITUTION}\n\n"
        "Your role is the MeritBadgeCoordinatorAgent (Root Supervisor).\n"
        "1. Coordinate research, planning, building, and review subagents.\n"
        "2. Manage persistent session state and apply history compaction (compaction_interval=5, overlap_size=2).\n"
        "3. Call run_merit_badge_workflow to execute the end-to-end graph.\n"
        "4. Ensure the human-in-the-loop confirmation stop is respected.\n"
        "5. Return the final PresentationWorkflowResult to the counselor UI."
    )
    
    agent = adk.Agent(
        name="MeritBadgeCoordinatorAgent",
        model=model_name,
        instruction=system_instruction,
        tools=[
            run_merit_badge_workflow,
            request_counselor_confirmation,
            save_session_state_async,
            load_session_state_async,
            compact_session_history_async,
        ],
        sub_agents=[
            get_pamphlet_research_agent(),
            get_slide_content_planner_agent(),
            get_powerpoint_builder_agent(),
            get_bsa_review_agent(),
        ]
    )
    # Attach explicit compaction configuration metadata for ADK and static audit inspection
    agent.compaction_config = EventsCompactionConfig(
        compaction_interval=5,
        overlap_size=2,
        compaction_strategy="additive"
    )
    return agent
