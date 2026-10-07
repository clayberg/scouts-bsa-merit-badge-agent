"""ADK PowerPointBuilderAgent for rendering 12-Archetype widescreen .pptx slide presentations.

This agent uses Gemini 2.5 Flash (`select_model_for_task('builder')`) for fast,
deterministic execution of `python-pptx` to render the official Scouts BSA-branded
16:9 widescreen presentation deck with strict non-overlapping AABB zone geometry,
cryptographic FastMCP HITL confirmation token verification (`before_tool_callback`),
and distinct per-slide visual diagrams.
"""

from typing import Any, List, Optional
from google import adk
from src.config import (
    SCOUTS_BSA_CONSTITUTION,
    load_prompt,
    select_model_for_task,
)
from src.tools.pptx_builder import generate_bsa_slide_deck_pptx
from src.tools.diagram_generator import generate_slide_visual_asset
from src.tools.hitl_confirm import (
    request_counselor_confirmation,
)
from src.agents.guardrails import (
    before_model_guardrail_callback,
    after_model_guardrail_callback,
    before_tool_guardrail_callback,
    after_tool_guardrail_callback,
)

try:
    from google.adk.tools.function_tool import FunctionTool as _ADKFunctionTool
except Exception:  # pragma: no cover
    _ADKFunctionTool = None


def get_hitl_confirmation_function_tool() -> Any:
    """Wraps `request_counselor_confirmation` in an ADK `FunctionTool(require_confirmation=True)`.

    Args:
        None.

    Returns:
        Any: ADK `FunctionTool` instance with `require_confirmation=True` when supported,
        otherwise the callable `request_counselor_confirmation`.
    """
    if _ADKFunctionTool is not None:
        try:
            return _ADKFunctionTool(
                func=request_counselor_confirmation,
                require_confirmation=True,
            )
        except Exception:
            pass
    return request_counselor_confirmation


def get_powerpoint_builder_agent(model_name: Optional[str] = None) -> adk.Agent:
    """Instantiates the `PowerPointBuilderAgent` with `python-pptx` 12-archetype rendering and HITL hooks.

    Args:
        model_name: Gemini model identifier to use (defaults to
            `select_model_for_task('builder')` / `'gemini-2.5-flash'`).

    Returns:
        adk.Agent: Configured `PowerPointBuilderAgent` with `before_tool_callback` enforcing
        cryptographic HITL confirmation tokens and Model Armor guardrails.
    """
    resolved_model = model_name or select_model_for_task("builder")
    external_prompt = load_prompt("builder.md", fallback="")
    system_instruction = (
        f"{SCOUTS_BSA_CONSTITUTION}\n\n"
        f"{external_prompt}\n\n"
        "Your role is the PowerPointBuilderAgent. Given a StoryboardPlan:\n"
        "1. Verify counselor approval via request_counselor_confirmation and pass hitl_confirmation_token.\n"
        "2. Call generate_bsa_slide_deck_pptx to generate the official 16:9 widescreen .pptx presentation.\n"
        "3. Ensure official BSA colors (Navy Blue #003F87, Action Blue #005AE0, Warm Olive #4B5320, "
        "Eagle Red #CE1126, Eagle Gold #F4C430) and Material 3 Expressive card tokens are applied.\n"
        "4. Enforce zero AABB shape overlaps, >= 13pt font floor, <= 8 paragraphs per text frame, "
        "zero literal bullet glyphs ('•'), and a distinct visual diagram on every content slide.\n"
        "5. Return the PowerPointBuildResult dictionary containing the output_path and slide_count."
    )

    tools_list: List[Any] = [
        request_counselor_confirmation,
        generate_bsa_slide_deck_pptx,
        generate_slide_visual_asset,
    ]

    agent = adk.Agent(
        name="PowerPointBuilderAgent",
        model=resolved_model,
        instruction=system_instruction,
        output_key="build_artifact",
        tools=tools_list,
        before_model_callback=before_model_guardrail_callback,
        after_model_callback=after_model_guardrail_callback,
        before_tool_callback=before_tool_guardrail_callback,
        after_tool_callback=after_tool_guardrail_callback,
    )
    return agent
