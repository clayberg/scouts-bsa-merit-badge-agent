"""Scouts BSA Merit Badge ADK Agents Package.

Lazily exports `root_agent`, `adk_app`, and guardrail utilities for the Google ADK CLI
(`adk web`, `adk run`, `adk eval`, `adk deploy`).
"""

from typing import Any

__all__ = [
    "root_agent",
    "adk_app",
    "get_merit_badge_coordinator_agent",
    "get_merit_badge_sequential_agent",
    "get_merit_badge_adk_app",
    "run_merit_badge_workflow",
    "get_slide_beautifier_agent",
    "get_deep_research_enrichment_agent",
    "get_web_image_search_agent",
    "get_nano_banana_image_agent",
    "get_badge_image_catalog",
    "search_web_images_for_slide",
    "estimate_nano_banana_image_cost",
    "generate_nano_banana_slide_image",
    "ScoutsBSAModelArmorPlugin",
    "FinOpsBudgetPlugin",
    "estimate_workflow_finops_cost",
    "load_model_armor_policy",
    "sanitize_text_with_model_armor",
]


def __getattr__(name: str) -> Any:
    """Lazily resolves agent and guardrail exports without circular import overhead."""
    if name in {
        "root_agent",
        "adk_app",
        "get_merit_badge_coordinator_agent",
        "get_merit_badge_sequential_agent",
        "get_merit_badge_adk_app",
        "run_merit_badge_workflow",
    }:
        from src.agents import coordinator

        return getattr(coordinator, name)
    if name == "get_slide_beautifier_agent":
        from src.agents import beautifier

        return getattr(beautifier, name)
    if name == "get_deep_research_enrichment_agent":
        from src.agents import researcher

        return getattr(researcher, name)
    if name in {
        "get_web_image_search_agent",
        "get_nano_banana_image_agent",
        "get_badge_image_catalog",
        "search_web_images_for_slide",
        "estimate_nano_banana_image_cost",
        "generate_nano_banana_slide_image",
    }:
        from src.agents import image_studio

        return getattr(image_studio, name)
    if name in {
        "ScoutsBSAModelArmorPlugin",
        "FinOpsBudgetPlugin",
        "estimate_workflow_finops_cost",
        "load_model_armor_policy",
        "sanitize_text_with_model_armor",
    }:
        from src.agents import guardrails

        return getattr(guardrails, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

