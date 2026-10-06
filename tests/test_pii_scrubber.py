"""Unit tests verifying explicit PII scrubbing, structured JSON logging, and OpenTelemetry spans.

Ensures counselor email addresses, phone numbers, SSNs, and API keys are redacted in logs
and traces, and verifies `execute_tool_with_observability` records OpenTelemetry spans.
"""

from src.observability.logging_setup import (
    execute_tool_with_observability,
    scrub_pii_before_sink,
    scrub_pii_from_structure,
)
from src.observability.tracing import clear_recorded_spans, get_recorded_spans


def test_email_redaction_before_sink():
    raw_payload = "Merit badge counselor contact: jane.doe@scouting.org for questions."
    scrubbed = scrub_pii_before_sink(raw_payload)
    assert "jane.doe@scouting.org" not in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed


def test_phone_redaction_before_sink():
    raw_payload = "Call counselor at (415) 555-1234 or 415-555-9876."
    scrubbed = scrub_pii_before_sink(raw_payload)
    assert "(415) 555-1234" not in scrubbed
    assert "415-555-9876" not in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed


def test_ssn_and_api_key_redaction_and_structure_scrubbing():
    raw_payload = "SSN 123-45-6789 and key AIzaSyD1234567890abcdefghijklmnopqrstuvwx"
    scrubbed = scrub_pii_before_sink(raw_payload)
    assert "123-45-6789" not in scrubbed
    assert "[REDACTED_SSN]" in scrubbed
    assert "AIzaSyD" not in scrubbed
    assert "[REDACTED_API_KEY]" in scrubbed

    nested = {
        "email": "bob@troop19.org",
        "notes": ["Call 978-555-0144"],
    }
    clean_nested = scrub_pii_from_structure(nested)
    assert clean_nested["email"] == "[REDACTED_EMAIL]"
    assert clean_nested["notes"][0] == "Call [REDACTED_PHONE]"


def test_non_pii_preserved():
    raw_payload = "First Aid Merit Badge Req 1: Life-threatening emergencies."
    scrubbed = scrub_pii_before_sink(raw_payload)
    assert scrubbed == raw_payload


def test_opentelemetry_span_and_intent_outcome_capture():
    clear_recorded_spans()

    def _sample_tool(badge_name: str) -> dict:
        return {"badge_name": badge_name, "status": "SUCCESS"}

    out = execute_tool_with_observability(
        tool_name="sample_observability_tool",
        func=_sample_tool,
        badge_name="Weather",
    )
    assert out["status"] == "SUCCESS"
    spans = get_recorded_spans()
    assert any(s["name"] == "tool.sample_observability_tool" for s in spans)
