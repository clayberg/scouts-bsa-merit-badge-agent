"""Unit tests verifying explicit PII scrubbing before observability and eval sinks.

Ensures counselor email addresses and phone numbers are redacted in logs and traces
while preserved on presentation title slides.
"""

import pytest
from src.observability.logging_setup import scrub_pii_before_sink

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

def test_non_pii_preserved():
    raw_payload = "First Aid Merit Badge Req 1: Life-threatening emergencies."
    scrubbed = scrub_pii_before_sink(raw_payload)
    assert scrubbed == raw_payload
