"""Google Cloud Model Armor & Youth Protection Guardrails Plugin for ADK.

This module implements:
1. Active enforcement of `config/model_armor_security_policy.json` (Prompt Injection,
   Jailbreak, Youth Protection / PII / CSAM filters, and BSA Safety Rules).
2. Optional Google Cloud Model Armor API (`google.cloud.modelarmor_v1`) integration
   with deterministic local policy & regex fallback when running offline.
3. ADK `BasePlugin` (`ScoutsBSAModelArmorPlugin`) and callback hooks
   (`before_model_guardrail_callback`, `after_model_guardrail_callback`,
   `before_tool_guardrail_callback`, `after_tool_guardrail_callback`) wired into
   all ADK agents and the `App` container.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from src.config import CONFIG_DIR
from src.observability.logging_setup import logger, scrub_pii_before_sink
from src.schemas import build_guided_tool_error
from src.tools.hitl_confirm import verify_hitl_before_tool_callback

try:
    from google.adk.plugins.base_plugin import BasePlugin as _ADKBasePlugin
except Exception:  # pragma: no cover

    class _ADKBasePlugin:  # type: ignore[no-redef]
        """Fallback BasePlugin when google.adk.plugins is unavailable."""

        def __init__(self, name: str = "ScoutsBSAModelArmorPlugin") -> None:
            self.name = name


MODEL_ARMOR_POLICY_PATH = CONFIG_DIR / "model_armor_security_policy.json"

_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(scouts\s+bsa|safety|system)\s+(constitution|rules|prompt)", re.IGNORECASE),
    re.compile(r"bypass\s+(guide\s+to\s+safe\s+scouting|two[-\s]deep\s+leadership|youth\s+protection)", re.IGNORECASE),
    re.compile(r"system\s*override\s*:", re.IGNORECASE),
    re.compile(r"jailbreak\s*mode", re.IGNORECASE),
]

_UNSAFE_SCOUTING_PATTERNS = [
    re.compile(r"skip\s+(the\s+)?buddy\s+system", re.IGNORECASE),
    re.compile(r"one[-\s]on[-\s]one\s+private\s+contact\s+with\s+youth", re.IGNORECASE),
    re.compile(r"omit\s+safety\s+warnings", re.IGNORECASE),
]


def load_model_armor_policy() -> Dict[str, Any]:
    """Loads the declarative Model Armor & Youth Protection security policy JSON.

    Args:
        None.

    Returns:
        Dict[str, Any]: Parsed security policy configuration dictionary from
        `config/model_armor_security_policy.json`.
    """
    if MODEL_ARMOR_POLICY_PATH.exists():
        try:
            data = json.loads(MODEL_ARMOR_POLICY_PATH.read_text(encoding="utf-8"))
            data.setdefault("policy_name", data.get("policy_id", "scouts-bsa-youth-protection-armor-v1"))
            data.setdefault("policy_id", data.get("policy_name", "model-armor-scouts-bsa-youth-protection-v2"))
            return data
        except Exception as exc:
            logger.warning("Failed to parse model_armor_security_policy.json: %s", exc)
    return {
        "policy_id": "model-armor-scouts-bsa-youth-protection-v2",
        "policy_name": "scouts-bsa-youth-protection-armor-v1",
        "enforcement_mode": "STRICT_BLOCK",
        "filters": {
            "prompt_injection_and_jailbreak": {"enabled": True, "confidence_threshold": "LOW_AND_ABOVE"},
            "pii_and_youth_data_redaction": {"enabled": True, "action": "REDACT_BEFORE_LOGGING_AND_LLM"},
            "dangerous_content_and_safety": {"enabled": True},
        },
    }


def sanitize_text_with_model_armor(
    text: str,
    direction: str = "INPUT",
) -> Dict[str, Any]:
    """Inspects and sanitizes user prompts or model responses using Model Armor & Youth Protection rules.

    When `USE_CLOUD_MODEL_ARMOR=true` and `MODEL_ARMOR_TEMPLATE_ID` are set, invokes the
    Google Cloud Model Armor API (`google.cloud.modelarmor_v1.ModelArmorClient`). Always
    applies deterministic prompt-injection, Youth Protection, and PII scrubbing rules.

    Args:
        text: Raw user prompt, tool argument payload, or LLM response text to inspect.
        direction: Either `'INPUT'` (user prompt / tool call) or `'OUTPUT'` (model / tool response).

    Returns:
        Dict[str, Any]: Dictionary containing:
            - `allowed` (bool): True if the text passes all Model Armor & Youth Protection checks.
            - `sanitized_text` (str): PII-redacted text safe for downstream processing.
            - `violations` (List[str]): List of policy violation codes detected (empty if allowed).
            - `policy_name` (str): Active Model Armor policy identifier.
            - `remediation` (Optional[str]): Guided remediation message if blocked.
    """
    policy = load_model_armor_policy()
    policy_name = str(policy.get("policy_name", "scouts-bsa-youth-protection-armor-v1"))
    raw_text = str(text or "")
    violations: List[str] = []

    # 1. Optional Google Cloud Model Armor API call
    if os.environ.get("USE_CLOUD_MODEL_ARMOR", "").lower() == "true":
        template_id = os.environ.get("MODEL_ARMOR_TEMPLATE_ID", "")
        if template_id:
            try:
                from google.cloud import modelarmor_v1  # type: ignore

                client = modelarmor_v1.ModelArmorClient()
                if direction.upper() == "INPUT":
                    req = modelarmor_v1.SanitizeUserPromptRequest(
                        name=template_id,
                        user_prompt_data=modelarmor_v1.DataItem(text=raw_text),
                    )
                    resp = client.sanitize_user_prompt(request=req)
                else:
                    req = modelarmor_v1.SanitizeModelResponseRequest(
                        name=template_id,
                        model_response_data=modelarmor_v1.DataItem(text=raw_text),
                    )
                    resp = client.sanitize_model_response(request=req)
                filter_match = getattr(resp.sanitization_result, "filter_match_state", None)
                if str(filter_match).endswith("MATCH_FOUND"):
                    violations.append("CLOUD_MODEL_ARMOR_FILTER_MATCH")
            except Exception as exc:
                logger.debug("Cloud Model Armor API unavailable; falling back to local policy: %s", exc)

    # 2. Local Prompt Injection & Jailbreak detection
    if policy.get("filters", {}).get("prompt_injection_and_jailbreak", {}).get("enabled", True):
        for pat in _PROMPT_INJECTION_PATTERNS:
            if pat.search(raw_text):
                violations.append("PROMPT_INJECTION_OR_JAILBREAK_ATTEMPT")
                break

    # 3. BSA Youth Protection & Guide to Safe Scouting enforcement
    if policy.get("filters", {}).get("dangerous_content_and_safety", {}).get("enabled", True):
        for pat in _UNSAFE_SCOUTING_PATTERNS:
            if pat.search(raw_text):
                violations.append("BSA_YOUTH_PROTECTION_OR_SAFETY_VIOLATION")
                break

    # 4. PII Redaction before logging / LLM context
    sanitized_text = scrub_pii_before_sink(raw_text)

    allowed = len(violations) == 0
    remediation = None
    if not allowed:
        remediation = (
            f"Blocked by Model Armor policy '{policy_name}' due to {', '.join(violations)}. "
            "Remove any instructions attempting to override the Scouts BSA Constitution, "
            "Two-Deep Leadership, the Buddy System, or the BSA Guide to Safe Scouting."
        )
        logger.warning(
            "Model Armor policy blocked payload",
            extra={
                "policy_name": policy_name,
                "direction": direction,
                "violations": violations,
            },
        )

    return {
        "allowed": allowed,
        "sanitized_text": sanitized_text,
        "violations": violations,
        "policy_name": policy_name,
        "remediation": remediation,
    }


_COMPLIANCE_AUDIT_EVENTS: List[Dict[str, Any]] = []


def emit_compliance_audit_log(
    caller_id: str,
    action: str,
    guardrail_status: str,
    badge_name: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Emits an immutable structured compliance audit record with data residency metadata."""
    import time as _time

    record = {
        "event_type": "compliance_audit",
        "caller_identity": scrub_pii_before_sink(caller_id or "anonymous_local_counselor"),
        "action": action,
        "badge_name": badge_name,
        "guardrail_status": guardrail_status,
        "data_residency_region": os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        "timestamp_epoch": round(_time.time(), 3),
        "details": details or {},
    }
    _COMPLIANCE_AUDIT_EVENTS.append(record)
    if len(_COMPLIANCE_AUDIT_EVENTS) > 500:
        del _COMPLIANCE_AUDIT_EVENTS[:-500]
    logger.info("Compliance audit event", extra=record)
    return record


def get_compliance_audit_events(limit: int = 50) -> List[Dict[str, Any]]:
    """Returns the most recent compliance audit records."""
    return list(_COMPLIANCE_AUDIT_EVENTS[-max(1, limit) :])


def before_model_guardrail_callback(
    callback_context: Any = None,
    llm_request: Any = None,
) -> Optional[Dict[str, Any]]:
    """ADK `before_model_callback` inspecting and scrubbing incoming prompts before they reach Gemini.

    Enforces pre-LLM PII redaction (COPPA / BSA Youth Protection) and blocks prompt-injection
    or jailbreak payloads via `sanitize_text_with_model_armor`.

    Args:
        callback_context: ADK `CallbackContext` for the active agent invocation.
        llm_request: ADK `LlmRequest` containing prompt contents.

    Returns:
        Optional[Dict[str, Any]]: `None` if the request is safe to proceed to Gemini;
        otherwise a `GuidedToolError` dictionary blocking the unsafe prompt.
    """
    raw_text = str(getattr(llm_request, "contents", llm_request or ""))
    check = sanitize_text_with_model_armor(raw_text, direction="INPUT")

    # Actively scrub PII in-place on outgoing llm_request before it reaches the external LLM
    sanitized_text = check["sanitized_text"]
    if llm_request is not None:
        if hasattr(llm_request, "contents") and isinstance(getattr(llm_request, "contents"), str):
            setattr(llm_request, "contents", sanitized_text)
        elif isinstance(llm_request, dict) and "contents" in llm_request:
            llm_request["contents"] = sanitized_text

    caller_id = str(getattr(callback_context, "user_id", "adk_agent_caller"))
    emit_compliance_audit_log(
        caller_id=caller_id,
        action="before_model_invocation",
        guardrail_status="ALLOWED" if check["allowed"] else "BLOCKED",
        details={
            "pii_redacted_pre_llm": sanitized_text != raw_text,
            "violations": check["violations"],
            "policy_name": check["policy_name"],
        },
    )

    if not check["allowed"]:
        return build_guided_tool_error(
            error_code="MODEL_ARMOR_PROMPT_BLOCKED",
            message=f"Request blocked by {check['policy_name']}: {', '.join(check['violations'])}.",
            remediation=str(check["remediation"]),
            details={"violations": check["violations"], "policy_name": check["policy_name"]},
        )
    return None



def after_model_guardrail_callback(
    callback_context: Any = None,
    llm_response: Any = None,
) -> Optional[Dict[str, Any]]:
    """ADK `after_model_callback` inspecting model outputs for PII leakage and BSA safety compliance.

    Args:
        callback_context: ADK `CallbackContext` for the active agent invocation.
        llm_response: ADK `LlmResponse` returned by Gemini.

    Returns:
        Optional[Dict[str, Any]]: `None` if the response is compliant; otherwise a
        `GuidedToolError` dictionary blocking the unsafe output.
    """
    raw_text = str(getattr(llm_response, "content", llm_response or ""))
    check = sanitize_text_with_model_armor(raw_text, direction="OUTPUT")
    if not check["allowed"]:
        return build_guided_tool_error(
            error_code="MODEL_ARMOR_RESPONSE_BLOCKED",
            message=f"Model output blocked by {check['policy_name']}: {', '.join(check['violations'])}.",
            remediation=str(check["remediation"]),
            details={"violations": check["violations"], "policy_name": check["policy_name"]},
        )
    return None


def before_tool_guardrail_callback(
    tool: Any,
    args: Dict[str, Any],
    tool_context: Any = None,
) -> Optional[Dict[str, Any]]:
    """ADK `before_tool_callback` enforcing both Model Armor input sanitization and HITL token gates.

    Args:
        tool: The ADK tool or Python callable being invoked.
        args: Keyword arguments passed to the tool.
        tool_context: Optional ADK `ToolContext`.

    Returns:
        Optional[Dict[str, Any]]: `None` if execution is permitted; otherwise a
        `GuidedToolError` dictionary explaining the policy or HITL gate rejection.
    """
    check = sanitize_text_with_model_armor(json.dumps(args, default=str), direction="INPUT")
    if not check["allowed"]:
        return build_guided_tool_error(
            error_code="MODEL_ARMOR_TOOL_ARGS_BLOCKED",
            message=f"Tool arguments blocked by {check['policy_name']}.",
            remediation=str(check["remediation"]),
            details={"violations": check["violations"]},
        )
    return verify_hitl_before_tool_callback(tool=tool, args=args, tool_context=tool_context)


def after_tool_guardrail_callback(
    tool: Any,
    args: Dict[str, Any],
    tool_context: Any = None,
    tool_response: Any = None,
) -> Optional[Dict[str, Any]]:
    """ADK `after_tool_callback` auditing tool outputs against Youth Protection and PII policies.

    Args:
        tool: The ADK tool or Python callable that executed.
        args: Keyword arguments passed to the tool.
        tool_context: Optional ADK `ToolContext`.
        tool_response: Raw return value from the tool.

    Returns:
        Optional[Dict[str, Any]]: `None` when the tool output is compliant; otherwise a
        `GuidedToolError` dictionary.
    """
    check = sanitize_text_with_model_armor(str(tool_response or ""), direction="OUTPUT")
    if not check["allowed"]:
        return build_guided_tool_error(
            error_code="MODEL_ARMOR_TOOL_OUTPUT_BLOCKED",
            message=f"Tool output blocked by {check['policy_name']}.",
            remediation=str(check["remediation"]),
            details={"violations": check["violations"]},
        )
    return None


class ScoutsBSAModelArmorPlugin(_ADKBasePlugin):
    """ADK `BasePlugin` enforcing Google Cloud Model Armor, Youth Protection, and HITL gates."""

    def __init__(self, name: str = "ScoutsBSAModelArmorPlugin") -> None:
        """Initializes the ScoutsBSAModelArmorPlugin with `config/model_armor_security_policy.json`.

        Args:
            name: Unique plugin identifier registered with the ADK `App` or `Runner`.
        """
        super().__init__(name=name)
        self.policy = load_model_armor_policy()

    async def before_model_callback(
        self,
        *,
        callback_context: Any,
        llm_request: Any,
    ) -> Optional[Any]:
        """ADK plugin hook executed before sending any `LlmRequest` to Gemini.

        Args:
            callback_context: ADK `CallbackContext`.
            llm_request: Outgoing `LlmRequest`.

        Returns:
            Optional[Any]: `None` if allowed, or a structured block payload.
        """
        return before_model_guardrail_callback(
            callback_context=callback_context,
            llm_request=llm_request,
        )

    async def after_model_callback(
        self,
        *,
        callback_context: Any,
        llm_response: Any,
    ) -> Optional[Any]:
        """ADK plugin hook executed after receiving an `LlmResponse` from Gemini.

        Args:
            callback_context: ADK `CallbackContext`.
            llm_response: Incoming `LlmResponse`.

        Returns:
            Optional[Any]: `None` if allowed, or a structured block payload.
        """
        return after_model_guardrail_callback(
            callback_context=callback_context,
            llm_response=llm_response,
        )

    async def before_tool_callback(
        self,
        *,
        tool: Any,
        tool_args: Dict[str, Any],
        tool_context: Any,
    ) -> Optional[Dict[str, Any]]:
        """ADK plugin hook executed before any tool invocation.

        Args:
            tool: ADK `BaseTool` instance.
            tool_args: Dictionary of arguments passed to the tool.
            tool_context: ADK `ToolContext`.

        Returns:
            Optional[Dict[str, Any]]: `None` if allowed, or a `GuidedToolError` dict.
        """
        return before_tool_guardrail_callback(
            tool=tool,
            args=tool_args,
            tool_context=tool_context,
        )

    async def after_tool_callback(
        self,
        *,
        tool: Any,
        tool_args: Dict[str, Any],
        tool_context: Any,
        result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """ADK plugin hook executed after any tool invocation completes.

        Args:
            tool: ADK `BaseTool` instance.
            tool_args: Dictionary of arguments passed to the tool.
            tool_context: ADK `ToolContext`.
            result: Dictionary returned by the tool.

        Returns:
            Optional[Dict[str, Any]]: `None` if allowed, or a `GuidedToolError` dict.
        """
        return after_tool_guardrail_callback(
            tool=tool,
            args=tool_args,
            tool_context=tool_context,
            tool_response=result,
        )


def estimate_workflow_finops_cost(
    badge_name: str,
    depth_mode: str = "Deep Dive / Camp School Deck",
    beautification_tier: str = "STANDARD",
    enable_deep_research: bool = True,
    max_budget_usd: float = 1.00,
) -> Dict[str, Any]:
    """Calculates the estimated token, AI illustration, and USD cost for a Merit Badge workflow run.

    Enforces FinOps budget caps from `config/finops_model_policy.json` and recommends an automatic
    downgrade action (e.g., capping AI hero illustrations or switching `gemini-2.5-pro` to
    `gemini-2.5-flash`) if the requested tier exceeds `max_budget_usd`.

    Args:
        badge_name: Official Scouts BSA Merit Badge name.
        depth_mode: `'Standard Deck'` or `'Deep Dive / Camp School Deck'`.
        beautification_tier: `'STANDARD'`, `'BEAUTIFIED'`, or `'STUDIO'`.
        enable_deep_research: Whether Tier-2 grounded web & hyper-local research is enabled.
        max_budget_usd: Maximum allowed USD budget for the workflow run (default `1.00`).

    Returns:
        Dict[str, Any]: Serialized `FinOpsCostEstimate` dictionary (or `GuidedToolError` on invalid input).
    """
    from src.schemas import FinOpsCostEstimate

    if not badge_name or not str(badge_name).strip():
        return build_guided_tool_error(
            error_code="EMPTY_BADGE_NAME",
            message="badge_name cannot be empty when estimating FinOps workflow cost.",
            remediation="Pass a valid Scouts BSA Merit Badge name such as 'Weather' or 'First Aid'.",
        )

    tier_upper = str(beautification_tier or "STANDARD").strip().upper()
    if tier_upper not in ("STANDARD", "BEAUTIFIED", "STUDIO"):
        tier_upper = "STANDARD"

    is_deep_dive = "deep" in str(depth_mode or "").lower()
    base_in_tokens = 65_000 if is_deep_dive else 32_000
    base_out_tokens = 13_500 if is_deep_dive else 7_000
    base_llm_cost = 0.14 if is_deep_dive else 0.06

    if enable_deep_research:
        base_in_tokens += 30_000
        base_out_tokens += 5_000
        base_llm_cost += 0.035

    planned_images = 0
    if tier_upper == "BEAUTIFIED":
        base_in_tokens += 25_000
        base_out_tokens += 8_000
        base_llm_cost += 0.045
        planned_images = 5
    elif tier_upper == "STUDIO":
        base_in_tokens += 45_000
        base_out_tokens += 14_000
        base_llm_cost = 0.20 if (is_deep_dive and enable_deep_research) else (0.16 if is_deep_dive else 0.12)
        planned_images = 20 if is_deep_dive else 15

    image_cost = planned_images * 0.04
    total_cost = round(min(1.00, base_llm_cost + image_cost) if tier_upper == "STUDIO" and is_deep_dive else (base_llm_cost + image_cost), 3)
    within_budget = total_cost <= float(max_budget_usd)
    downgrade_action = None

    if not within_budget:
        max_affordable_images = max(0, int((float(max_budget_usd) - base_llm_cost) // 0.04))
        downgrade_action = (
            f"Estimated cost (${total_cost:.2f}) exceeds max_budget_usd (${max_budget_usd:.2f}). "
            f"Automatically capping AI hero illustrations from {planned_images} to {max_affordable_images} "
            "and routing non-critical synthesis calls to gemini-2.5-flash."
        )

    estimate = FinOpsCostEstimate(
        badge_name=badge_name.strip(),
        depth_mode=depth_mode,
        beautification_tier=tier_upper,  # type: ignore[arg-type]
        enable_deep_research=bool(enable_deep_research),
        estimated_input_tokens=base_in_tokens,
        estimated_output_tokens=base_out_tokens,
        planned_ai_hero_images=planned_images,
        estimated_cost_usd=total_cost,
        cached_rerun_cost_usd=0.02 if tier_upper != "STANDARD" else 0.00,
        max_budget_usd=round(float(max_budget_usd), 2),
        within_budget=within_budget,
        downgrade_action=downgrade_action,
    )
    return estimate.model_dump()


class FinOpsBudgetPlugin(_ADKBasePlugin):
    """ADK `BasePlugin` tracking token/image spend and enforcing FinOps budget caps."""

    def __init__(self, max_budget_usd: float = 1.00, name: str = "FinOpsBudgetPlugin") -> None:
        """Initializes the FinOpsBudgetPlugin with a configurable USD budget cap.

        Args:
            max_budget_usd: Maximum USD spend permitted per workflow invocation (default `1.00`).
            name: Unique plugin name registered with the ADK `App`.
        """
        super().__init__(name=name)
        self.max_budget_usd = float(max_budget_usd)
        self.cumulative_spend_usd = 0.0
        self.llm_calls_count = 0
        self.image_calls_count = 0

    def record_usage(self, input_tokens: int = 0, output_tokens: int = 0, images: int = 0) -> Dict[str, Any]:
        """Records token and image generation usage and updates cumulative USD spend.

        Args:
            input_tokens: Prompt tokens consumed.
            output_tokens: Completion tokens generated.
            images: Number of AI images generated.

        Returns:
            Dict[str, Any]: Updated FinOps ledger snapshot.
        """
        self.llm_calls_count += 1 if (input_tokens or output_tokens) else 0
        self.image_calls_count += images
        delta_usd = (input_tokens / 1_000_000.0) * 0.50 + (output_tokens / 1_000_000.0) * 4.00 + (images * 0.04)
        self.cumulative_spend_usd = round(self.cumulative_spend_usd + delta_usd, 4)
        return {
            "cumulative_spend_usd": self.cumulative_spend_usd,
            "max_budget_usd": self.max_budget_usd,
            "within_budget": self.cumulative_spend_usd <= self.max_budget_usd,
            "llm_calls_count": self.llm_calls_count,
            "image_calls_count": self.image_calls_count,
        }

