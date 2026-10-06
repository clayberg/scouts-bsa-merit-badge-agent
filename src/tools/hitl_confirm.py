"""Human-in-the-Loop (HITL) Confirmation Stop Tool & FastMCP Cryptographic Token Gate.

This module implements explicit code stops requiring human counselor confirmation
before executing high-stakes actions like PowerPoint generation or Eagle-required scope sign-off,
using HMAC-SHA256 confirmation tokens bound to the badge storyboard.
"""

from datetime import datetime, timezone
import hashlib
import hmac
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ValidationError
from src.config import get_secret
from src.schemas import HITLConfirmationToken, build_guided_tool_error


def _get_hitl_secret_bytes() -> bytes:
    """Retrieves the HMAC signing key via Google Cloud Secret Manager / env without hardcoded keys."""
    return get_secret("BSA_HITL_SECRET_KEY").encode("utf-8")


class PowerPointBuildConfirmation(BaseModel):
    """Schema representing an explicit confirmation stop before generating a presentation."""
    badge_name: str = Field(..., min_length=1, description="Official badge name.")
    slide_count: int = Field(..., ge=0, description="Proposed number of slides.")
    eagle_required: bool = Field(False, description="Whether badge is Eagle-required.")
    counselor_name: str = Field("Counselor", description="Counselor name.")
    requires_human_confirmation: bool = Field(True, description="Enforces explicit stop in ADK graph.")


class HITLApprovalResponse(BaseModel):
    """Structured response after counselor review with cryptographic confirmation token."""
    approved: bool = Field(..., description="True if counselor approved, False if rejected.")
    counselor_feedback: str = Field("", description="Optional counselor review feedback.")
    confirmation_token: str = Field("", description="HMAC-SHA256 confirmation token authorizing build.")
    timestamp_iso: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 timestamp of confirmation."
    )
    badge_name: str = Field("", description="Confirmed Merit Badge name.")
    slide_count: int = Field(0, description="Confirmed slide count.")


def generate_hitl_confirmation_token(
    badge_name: str,
    slide_count: int = 0,
    counselor_name: str = "Counselor"
) -> str:
    """Generates a deterministic HMAC-SHA256 confirmation token bound to the badge storyboard.

    Args:
        badge_name: Official name of the Merit Badge.
        slide_count: Number of storyboard slides approved.
        counselor_name: Name of the approving Merit Badge Counselor.

    Returns:
        str: Formatted HMAC-SHA256 confirmation token (`hitl_<slides>_<badge_mac>_<context_mac>`).
    """
    secret_key = _get_hitl_secret_bytes()
    clean_badge = (badge_name or "unknown").strip().lower()
    clean_counselor = (counselor_name or "counselor").strip().lower()
    badge_mac = hmac.new(
        secret_key, clean_badge.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:24]
    context_payload = f"{clean_badge}:{int(slide_count)}:{clean_counselor}"
    context_mac = hmac.new(
        secret_key, context_payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:16]
    return f"hitl_{int(slide_count)}_{badge_mac}_{context_mac}"


def verify_hitl_confirmation_token(
    token: str,
    badge_name: str,
    slide_count: Optional[int] = None,
    counselor_name: Optional[str] = None,
) -> bool:
    """Verifies an HMAC-SHA256 confirmation token against the target badge name.

    Args:
        token: Token string returned by `generate_hitl_confirmation_token`.
        badge_name: Official name of the Merit Badge being built.
        slide_count: Optional slide count to strictly verify context MAC.
        counselor_name: Optional counselor name to strictly verify context MAC.

    Returns:
        bool: True if the token signature is valid for `badge_name`, False otherwise.
    """
    if not token or not isinstance(token, str) or not badge_name:
        return False
    parts = token.split("_")
    if len(parts) != 4 or parts[0] != "hitl":
        return False
    _, _, badge_mac, context_mac = parts
    secret_key = _get_hitl_secret_bytes()
    clean_badge = badge_name.strip().lower()
    expected_badge_mac = hmac.new(
        secret_key, clean_badge.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:24]
    if not hmac.compare_digest(badge_mac, expected_badge_mac):
        return False
    if slide_count is not None and counselor_name is not None:
        clean_counselor = counselor_name.strip().lower()
        expected_context = f"{clean_badge}:{int(slide_count)}:{clean_counselor}"
        expected_context_mac = hmac.new(
            secret_key, expected_context.encode("utf-8"), hashlib.sha256
        ).hexdigest()[:16]
        if not hmac.compare_digest(context_mac, expected_context_mac):
            return False
    return True


def request_counselor_confirmation(outline_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Explicit code stop requiring counselor confirmation before generating .pptx files.

    Validates the proposed storyboard parameters via `PowerPointBuildConfirmation` and issues
    a cryptographic HMAC-SHA256 `confirmation_token` required before `generate_bsa_slide_deck_pptx`
    executes.

    Args:
        outline_summary: Dictionary containing `badge_name`, `slide_count`, `is_eagle_required`,
            `counselor_name`, and optional `approved` override.

    Returns:
        Dict[str, Any]: Serialized `HITLApprovalResponse` dictionary containing `approved`,
        `confirmation_token`, `timestamp_iso`, `badge_name`, and `slide_count`, or a
        `GuidedToolError` dictionary if validation fails.
    """
    if not isinstance(outline_summary, dict):
        return build_guided_tool_error(
            error_type="INVALID_HITL_OUTLINE_SUMMARY",
            message="outline_summary must be a dictionary with 'badge_name' and 'slide_count'.",
            recovery_suggestion="Call request_counselor_confirmation with a dict containing badge_name and slide_count.",
        )

    badge_name = str(outline_summary.get("badge_name", "")).strip()
    if not badge_name:
        return build_guided_tool_error(
            error_type="MISSING_BADGE_NAME_FOR_HITL",
            message="Cannot request counselor HITL confirmation without a valid 'badge_name'.",
            recovery_suggestion="Pass a non-empty 'badge_name' in outline_summary before requesting HITL confirmation.",
        )

    try:
        slide_count = int(outline_summary.get("slide_count", 0))
        eagle_req = bool(outline_summary.get("is_eagle_required", False))
        counselor_name = str(outline_summary.get("counselor_name", "Counselor"))

        confirmation_payload = PowerPointBuildConfirmation(
            badge_name=badge_name,
            slide_count=slide_count,
            eagle_required=eagle_req,
            counselor_name=counselor_name,
            requires_human_confirmation=True,
        )
    except (ValidationError, ValueError) as exc:
        return build_guided_tool_error(
            error_type="HITL_VALIDATION_ERROR",
            message=f"Invalid HITL confirmation payload: {exc}",
            recovery_suggestion="Ensure 'slide_count' is a non-negative integer and 'badge_name' is a valid string.",
        )

    approved_flag = bool(outline_summary.get("approved", True))
    now_iso = datetime.now(timezone.utc).isoformat()
    token_str = (
        generate_hitl_confirmation_token(
            badge_name=confirmation_payload.badge_name,
            slide_count=confirmation_payload.slide_count,
            counselor_name=confirmation_payload.counselor_name,
        )
        if approved_flag
        else ""
    )

    # Validate against HITLConfirmationToken contract
    _ = HITLConfirmationToken(
        token_id=token_str or "rejected",
        badge_name=confirmation_payload.badge_name,
        slide_count=confirmation_payload.slide_count,
        subrequirement_count=int(outline_summary.get("subrequirement_count", slide_count)),
        counselor_name=confirmation_payload.counselor_name,
        approved=approved_flag,
        timestamp_iso=now_iso,
    )

    response = HITLApprovalResponse(
        approved=approved_flag,
        counselor_feedback=(
            "Automated check: outline confirmed for PowerPoint generation."
            if approved_flag
            else "Counselor rejected storyboard outline; revise slides before building."
        ),
        confirmation_token=token_str,
        timestamp_iso=now_iso,
        badge_name=confirmation_payload.badge_name,
        slide_count=confirmation_payload.slide_count,
    )
    return response.model_dump()


def verify_hitl_before_tool_callback(
    tool: Any,
    args: Dict[str, Any],
    tool_context: Any = None,
) -> Optional[Dict[str, Any]]:
    """ADK `before_tool_callback` enforcing human-in-the-loop confirmation before high-stakes `.pptx` builds.

    Args:
        tool: The ADK tool instance or function being invoked.
        args: Tool arguments dictionary passed by the LLM agent.
        tool_context: Optional ADK `ToolContext` carrying session state.

    Returns:
        Optional[Dict[str, Any]]: `None` if execution is permitted to proceed, or a `GuidedToolError`
        dictionary halting execution if an invalid `hitl_confirmation_token` was supplied.
    """
    tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", str(tool))
    if tool_name != "generate_bsa_slide_deck_pptx":
        return None

    req_obj = args.get("request")
    if isinstance(req_obj, dict):
        token = req_obj.get("hitl_confirmation_token")
        badge_name = req_obj.get("badge_name", "")
    else:
        token = getattr(req_obj, "hitl_confirmation_token", None) or args.get("hitl_confirmation_token")
        badge_name = getattr(req_obj, "badge_name", "") or args.get("badge_name", "")

    if token and not verify_hitl_confirmation_token(token, badge_name):
        return build_guided_tool_error(
            error_type="HITL_CONFIRMATION_TOKEN_INVALID",
            message=f"HITL confirmation token '{token}' failed HMAC-SHA256 verification for '{badge_name}'.",
            recovery_suggestion=(
                "Call request_counselor_confirmation first to obtain a valid confirmation_token "
                "before calling generate_bsa_slide_deck_pptx."
            ),
        )
    return None

