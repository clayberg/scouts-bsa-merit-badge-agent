"""ADK PowerPointBuilderAgent for rendering .pptx slide presentations.

This agent uses Gemini 2.5 Flash for fast, deterministic execution of python-pptx
to render the official Scouts BSA-branded presentation deck.
"""

from google import adk
from src.tools.pptx_builder import generate_bsa_slide_deck_pptx
from src.config import SCOUTS_BSA_CONSTITUTION

def get_powerpoint_builder_agent(model_name: str = "gemini-2.5-flash") -> adk.Agent:
    """Instantiates the PowerPointBuilderAgent with python-pptx rendering tools.
    
    Args:
        model_name: Gemini model to use (default: gemini-2.5-flash for speed).
        
    Returns:
        adk.Agent: Configured builder subagent.
    """
    system_instruction = (
        f"{SCOUTS_BSA_CONSTITUTION}\n\n"
        "Your role is the PowerPointBuilderAgent. Given a StoryboardPlan:\n"
        "1. Call generate_bsa_slide_deck_pptx to generate the official .pptx presentation.\n"
        "2. Ensure official BSA colors (Navy Blue #003F87 and Warm Olive #4B5320) are applied.\n"
        "3. Ensure the Eagle-required subtitle badge is added if is_eagle_required is True.\n"
        "4. Return the PowerPointBuildResult dictionary containing the output_path."
    )
    
    agent = adk.Agent(
        name="PowerPointBuilderAgent",
        model=model_name,
        instruction=system_instruction,
        tools=[generate_bsa_slide_deck_pptx],
    )
    return agent
