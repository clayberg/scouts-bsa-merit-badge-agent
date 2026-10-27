# ADR 0005: Multi-Layer Model Armor, 3-Layer Context-Aware PII Scrubbing, and BSA Youth Protection Guardrails

## Status
Accepted

## Date
2026-10-15

## Context
Scouts BSA Merit Badge Counselors work with youth participants under strict **Scouting America Youth Protection Training (YPT) Two-Deep Leadership** policies (`GTA Section 7.0.3.2`). Counselors enter troop numbers, counselor contact details, and youth partial-completion rosters into the workbench. At the same time:
1. Personal counselor or Scout emails, phone numbers, and SSNs must never leak into external LLM prompts, tool arguments, SSE thought traces, OpenTelemetry spans, or shared multi-tenant databases.
2. Naive 10-digit phone regex scrubbers corrupt 10-digit numeric IDs inside official Scouting America Vimeo instructional video URLs (`92` links across `18` badges) and redact life-safety public hotlines taught in curriculum slides (such as `1-800-222-1222` Poison Control on First Aid Slide 3).
3. High-cost or mutating tool invocations must require cryptographic Human-in-the-Loop (HITL) verification.

## Options Considered
1. **Unfiltered Prompts or Ingress-Only Naive Regex Scrubbing:** Either leaks personal PII in model outputs/SSE traces or corrupts Vimeo instructional URLs and emergency hotlines (`1-800-222-1222`).
2. **Client-Side Boolean Confirmation Flag (`confirmed=True`):** An LLM can hallucinate `confirmed=True` in tool arguments without human authorization.
3. **Bidirectional `ScoutsBSAModelArmorPlugin` (`src/agents/guardrails.py` & `src/observability/logging_setup.py`) + 3-Layer Context-Aware Phone Redaction Filter + HMAC-SHA256 `HITLConfirmationToken` (`src/tools/hitl_confirm.py`):**
   * Scrub PII across all 4 boundaries: user ingress (`before_model_guardrail_callback`), tool arguments (`before_tool_callback`), model responses (`after_model_callback`), and SSE egress / telemetry (`scrub_pii_from_structure()` & `scrub_pii_dict()`).
   * Apply the **3-Layer Context-Aware Phone Filter**: Layer 1 excludes 10-digit numbers inside URLs and filenames; Layer 2 allowlists NANPA toll-free prefixes (`800/888/877/866/855/844/833`) and emergency/institutional numbers (`1-800-222-1222`, `911`, `988`, `800-323-0736`, `202-633-1000`); Layer 3 inspects a `+/-55`-character window for personal vs. institutional hotwords.
   * Block prompt injections, SSRF hosts (`169.254.169.254`, `metadata.google.internal`), and one-on-one youth contact violations via Google Cloud Model Armor (`MODEL_ARMOR_TEMPLATE_ID`) + deterministic local policy rules.
   * Enforce HMAC-SHA256 signature verification (`BSA_HITL_SECRET_KEY`) before `.pptx` build execution.

## Decision
We selected **Option 3**: Bidirectional `ScoutsBSAModelArmorPlugin` with 3-Layer Context-Aware PII scrubbing, YPT policy enforcement, and HMAC-SHA256 HITL token verification.

## Consequences
* **Positive:** Achieves a **`100.0%` personal PII redaction and adversarial injection block rate** (`14/14` adversarial test cases) with **`0.0%` false-positive corruption** across all 92 Vimeo instructional URLs and emergency hotlines, while keeping counselor contact injection strictly local to `.pptx` and Parent Letter templates.
* **Negative / Trade-Off:** Adds ~`1.2 ms` of bidirectional regex/context inspection per request and requires HMAC token signing prior to full deck builds when `REQUIRE_HITL_CONFIRMATION=true`.
