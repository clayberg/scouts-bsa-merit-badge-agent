"""ADK PamphletResearchAgent for Scouts BSA Merit Badge content ingestion.

This agent is responsible for retrieving official Scouts BSA downloadable pamphlet PDFs
and Requirement Resources (DRGs), extracting structured requirement points, and highlighting
Eagle-required prerequisites using Gemini 2.5 Pro.
"""

from google import adk
from src.tools.scouting_scraper import fetch_merit_badge_pamphlet_pdf
from src.config import SCOUTS_BSA_CONSTITUTION

def get_pamphlet_research_agent(model_name: str = "gemini-2.5-pro") -> adk.Agent:
    """Instantiates the PamphletResearchAgent with official PDF scraping tools.
    
    Args:
        model_name: Gemini model to use (default: gemini-2.5-pro).
        
    Returns:
        adk.Agent: Configured research subagent.
    """
    system_instruction = (
        f"{SCOUTS_BSA_CONSTITUTION}\n\n"
        "Your role is the PamphletResearchAgent. When given a merit badge name:\n"
        "1. Call fetch_merit_badge_pamphlet_pdf to ingest official requirements and DRG links.\n"
        "2. Ensure every requirement and sub-requirement is explicitly enumerated.\n"
        "3. Identify any Guide to Safe Scouting callouts (e.g. CPR, swimming, power tools).\n"
        "4. Return the structured MeritBadgeResearchResult dictionary."
    )
    
    agent = adk.Agent(
        name="PamphletResearchAgent",
        model=model_name,
        instruction=system_instruction,
        tools=[fetch_merit_badge_pamphlet_pdf],
    )
    return agent
