"""Scouts BSA Merit Badge Presentation & Counselor Workbench Agent Package.

Lazily exports `root_agent` and `adk_app` for the Google ADK CLI (`adk web`, `adk run`, `adk eval`, `adk deploy`).
"""

from typing import Any

__all__ = ["root_agent", "adk_app"]


def __getattr__(name: str) -> Any:
    """Lazily resolves `root_agent` and `adk_app` for ADK CLI discovery without circular imports."""
    if name in ("root_agent", "adk_app"):
        from src.agents import coordinator

        return getattr(coordinator, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
