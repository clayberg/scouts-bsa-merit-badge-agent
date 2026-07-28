"""ADK SlideContentPlannerAgent for creating pedagogical slide storyboards.

This agent converts raw merit badge requirements into an ordered, pedagogical
slide storyboard (max 7 bullet points per slide) using Gemini 2.5 Pro.
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field
from google import adk
from src.config import SCOUTS_BSA_CONSTITUTION, PRESENTATION_DEPTH_CONFIGS
from src.tools.pptx_builder import SlideSpec

class StoryboardPlan(BaseModel):
    """Schema representing the full ordered storyboard plan for a presentation."""
    badge_name: str = Field(..., description="Official badge name.")
    is_eagle_required: bool = Field(..., description="True if Eagle-required.")
    depth_mode: str = Field(..., description="Presentation depth mode selected.")
    slides: List[SlideSpec] = Field(..., description="Ordered list of slide specifications.")

def generate_slide_storyboard(
    badge_name: str,
    requirements: List[Dict[str, Any]],
    depth_mode: str = "Standard Deck",
    is_eagle_required: bool = False
) -> Dict[str, Any]:
    """Generates an ordered storyboard of SlideSpec objects adhering to the 7-bullet rule.
    
    Args:
        badge_name: Name of the merit badge.
        requirements: List of requirement dictionaries from the researcher agent.
        depth_mode: Presentation depth ('Standard Deck' or 'Deep Dive / Camp School Deck').
        is_eagle_required: True if badge is Eagle-required.
        
    Returns:
        Dict: Structured StoryboardPlan dictionary.
    """
    slides = []
    
    # Generate 1 to 2 slides per requirement point
    for req in requirements:
        req_num = req.get("req_number", "1")
        req_text = req.get("req_text", "Complete requirement.")
        safety = req.get("safety_callout")
        
        # Slide 1: Core requirement instruction
        bullets = [
            f"Requirement {req_num}: Overview and Objectives.",
            req_text[:120] + "..." if len(req_text) > 120 else req_text,
            "Review official Scouting.org downloadable pamphlet.",
            "Complete practical demonstration with your counselor.",
        ]
        if safety:
            bullets.append(f"Safety First: {safety}")
            
        slide = SlideSpec(
            title=f"Req {req_num}: Core Objectives",
            bullet_points=bullets[:7],  # Strictly enforce max 7 bullet points
            presenter_notes=f"Counselor Notes for Req {req_num}: Ask scouts to explain this point in their own words.",
            safety_warning=safety
        )
        slides.append(slide)
        
        # Deep Dive mode adds an activity/discussion slide
        if depth_mode == "Deep Dive / Camp School Deck":
            activity_slide = SlideSpec(
                title=f"Req {req_num}: Troop Activity & Practice",
                bullet_points=[
                    "Patrol Breakout: Practice this requirement with your buddy.",
                    "Demonstrate mastery to your Merit Badge Counselor.",
                    "Record completion in your Scout Handbook / Blue Card.",
                ],
                presenter_notes="Supervise practical patrol demonstration."
            )
            slides.append(activity_slide)
            
    plan = StoryboardPlan(
        badge_name=badge_name,
        is_eagle_required=is_eagle_required,
        depth_mode=depth_mode,
        slides=slides
    )
    return plan.model_dump()

def get_slide_content_planner_agent(model_name: str = "gemini-2.5-pro") -> adk.Agent:
    """Instantiates the SlideContentPlannerAgent for storyboarding presentations.
    
    Args:
        model_name: Gemini model to use (default: gemini-2.5-pro).
        
    Returns:
        adk.Agent: Configured planner subagent.
    """
    system_instruction = (
        f"{SCOUTS_BSA_CONSTITUTION}\n\n"
        "Your role is the SlideContentPlannerAgent. Given structured requirements:\n"
        "1. Call generate_slide_storyboard to build an ordered slide-by-slide plan.\n"
        "2. Strictly enforce the pedagogical scannability rule: NEVER exceed 7 bullet points per slide.\n"
        "3. Include Guide to Safe Scouting warnings on relevant slides.\n"
        "4. Return the structured StoryboardPlan dictionary."
    )
    
    agent = adk.Agent(
        name="SlideContentPlannerAgent",
        model=model_name,
        instruction=system_instruction,
        tools=[generate_slide_storyboard],
    )
    return agent
