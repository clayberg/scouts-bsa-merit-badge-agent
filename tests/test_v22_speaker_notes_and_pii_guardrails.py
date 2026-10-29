"""Tests for v2.2 Context-Aware PII Guardrails, Archetype-Aware Non-Repetitive Speaker Notes, and Studio AI Polish."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.agents.beautifier import beautify_slide_storyboard
from src.agents.guardrails import (
    NANPA_TOLL_FREE_PREFIXES,
    PERSONAL_PII_PHONE_HOTWORDS,
    PUBLIC_EMERGENCY_AND_INSTITUTIONAL_PHONES,
    PUBLIC_INSTITUTIONAL_PHONE_HOTWORDS,
    sanitize_text_with_model_armor,
)
from src.agents.planner import generate_slide_storyboard
from src.observability.logging_setup import scrub_pii_before_sink, scrub_pii_from_structure
from src.tools.pamphlet_extractor import _CURATED_REQ1_SAFETY_QUIZZES
from src.tools.scouting_scraper import fetch_merit_badge_pamphlet_pdf


def test_v22_layer1_url_and_filename_numeric_sequences_never_redacted() -> None:
    """Verify URL paths and PDF filenames with 10-digit sequences are never corrupted by PHONE_REGEX."""
    sample = (
        "Watch the official Scouting safety video at https://vimeo.com/1115216743 and download "
        "https://filestore.scouting.org/filestore/pdf/512-505-2016-Scout-Planning-Worksheet.pdf "
        "or local file 512-505-2016-Scout-Planning-Worksheet.pdf before class."
    )
    scrubbed = scrub_pii_before_sink(sample)
    assert "https://vimeo.com/1115216743" in scrubbed
    assert "512-505-2016-Scout-Planning-Worksheet.pdf" in scrubbed
    assert "[REDACTED_PHONE]" not in scrubbed


def test_v22_layer2_toll_free_and_emergency_hotlines_preserved() -> None:
    """Verify NANPA toll-free prefixes and curated public/institutional emergency numbers remain intact."""
    for expected_prefix in ("800", "888", "877", "866", "855", "844", "833"):
        assert expected_prefix in NANPA_TOLL_FREE_PREFIXES

    for code in ("8002221222", "8003230736", "2026331000", "8004248802", "8004224453"):
        assert code in PUBLIC_EMERGENCY_AND_INSTITUTIONAL_PHONES

    teaching_text = (
        "In a poisoning emergency, call Poison Control at 1-800-222-1222 immediately. "
        "For uniform parts, call the BSA Scout Shop customer service line at 800-323-0736. "
        "When visiting Washington, D.C., the Smithsonian Institution main switchboard is (202) 633-1000. "
        "Report marine oil spills to the National Response Center at 1-800-424-8802, "
        "and call the Childhelp National Child Abuse Hotline at 1-800-422-4453."
    )
    scrubbed = scrub_pii_before_sink(teaching_text)
    assert "1-800-222-1222" in scrubbed
    assert "800-323-0736" in scrubbed
    assert "(202) 633-1000" in scrubbed
    assert "1-800-424-8802" in scrubbed
    assert "1-800-422-4453" in scrubbed
    assert "[REDACTED_PHONE]" not in scrubbed


def test_v22_layer3_proximity_hotwords_and_personal_phone_redaction() -> None:
    """Verify proximity hotwords preserve institutional numbers while redacting personal Scout/Parent/Counselor phones cleanly."""
    assert "poison control" in PUBLIC_INSTITUTIONAL_PHONE_HOTWORDS
    assert "ranger station" in PUBLIC_INSTITUTIONAL_PHONE_HOTWORDS
    assert "cell" in PERSONAL_PII_PHONE_HOTWORDS

    # Local ranger station / Coast Guard numbers preserved via institutional proximity hotword
    institutional_context = (
        "Check in with the Yosemite Backcountry Ranger Station at (209) 372-0200 before hiking, "
        "or contact the Coast Guard sector dispatch at 415-399-3547."
    )
    scrubbed_inst = scrub_pii_before_sink(institutional_context)
    assert "(209) 372-0200" in scrubbed_inst
    assert "415-399-3547" in scrubbed_inst

    # Personal phone numbers with leading 1- or parentheses are matched in full (no leftover "1-" or "(")
    personal_samples = [
        ("Call Scoutmaster John Smith cell: 1-415-891-2345.", "Call Scoutmaster John Smith cell: [REDACTED_PHONE]."),
        ("Parent mobile: (415) 891-2345 for pickup.", "Parent mobile: [REDACTED_PHONE] for pickup."),
        ("Counselor contact: +1-303-742-9811 or (000) 555-1234.", "Counselor contact: [REDACTED_PHONE] or [REDACTED_PHONE]."),
        ("Unlabeled personal number 415-891-2345 on roster.", "Unlabeled personal number [REDACTED_PHONE] on roster."),
    ]
    for raw_text, expected_text in personal_samples:
        actual = scrub_pii_before_sink(raw_text)
        assert actual == expected_text, f"Expected {expected_text!r}, got {actual!r}"
        assert "1-[REDACTED_PHONE]" not in actual
        assert "([REDACTED_PHONE]" not in actual

    # Verify structure & Model Armor scrubbing preserves Poison Control while scrubbing personal cell
    payload = {
        "slide_notes": "Call Poison Control at 1-800-222-1222 or video https://vimeo.com/1115216743.",
        "private_roster": "Parent cell: 1-415-891-2345",
    }
    scrubbed_payload = scrub_pii_from_structure(payload)
    assert "1-800-222-1222" in scrubbed_payload["slide_notes"]
    assert "https://vimeo.com/1115216743" in scrubbed_payload["slide_notes"]
    assert scrubbed_payload["private_roster"] == "Parent cell: [REDACTED_PHONE]"
    ma_res = sanitize_text_with_model_armor("Call Poison Control at 1-800-222-1222 or Parent cell: (415) 891-2345")
    assert "1-800-222-1222" in ma_res["sanitized_text"]
    assert "Parent cell: [REDACTED_PHONE]" in ma_res["sanitized_text"]


def test_v22_curated_req1_safety_quiz_includes_first_aid() -> None:
    """Verify _CURATED_REQ1_SAFETY_QUIZZES includes a dedicated First Aid Req 1 triage/EMS/Universal Precautions quiz."""
    assert "first_aid" in _CURATED_REQ1_SAFETY_QUIZZES
    fa_quiz = _CURATED_REQ1_SAFETY_QUIZZES["first_aid"]
    assert "power line" in fa_quiz["scenario_prompt"].lower() or "bleeding" in fa_quiz["scenario_prompt"].lower()
    assert len(fa_quiz["options"]) == 3
    assert "911" in fa_quiz["correct_answer"]
    assert "Universal Precautions" in fa_quiz["explanation"] or "Check-Call-Care" in fa_quiz["explanation"]


def test_v22_first_aid_speaker_notes_non_repetitive_and_archetype_aware() -> None:
    """Verify First Aid multi-slide storyboard & beautifier generate distinct, non-repetitive 5-part speaker notes."""
    pamphlet = fetch_merit_badge_pamphlet_pdf({"badge_name": "First Aid"})
    storyboard_res = generate_slide_storyboard(
        badge_name="First Aid",
        requirements=pamphlet["requirements"],
        depth_mode="Deep Dive / Camp School Deck",
        is_eagle_required=True,
    )
    slides = storyboard_res["slides"]
    assert len(slides) >= 45

    req1_slides = [s for s in slides if str(s.get("req_number")) == "1"]
    assert len(req1_slides) >= 5, f"Expected >=5 slides for Requirement 1, got {len(req1_slides)}"

    pacing_lines = []
    ask_lines = []
    key_lines = []
    misc_lines = []
    demo_lines = []

    for idx, s in enumerate(slides):
        notes = str(s.get("presenter_notes") or "")
        assert "[PACING & MODALITY]" in notes, f"Slide {idx} missing [PACING & MODALITY]"
        assert "[ASK SCOUTS FIRST]" in notes, f"Slide {idx} missing [ASK SCOUTS FIRST]"
        assert "[EXPECTED PAMPHLET ANSWER KEY]" in notes, f"Slide {idx} missing [EXPECTED PAMPHLET ANSWER KEY]"
        assert "[COMMON MISCONCEPTION TO CORRECT]" in notes, f"Slide {idx} missing [COMMON MISCONCEPTION TO CORRECT]"
        assert "[DEMONSTRATION & SIGN-OFF RUBRIC]" in notes, f"Slide {idx} missing [DEMONSTRATION & SIGN-OFF RUBRIC]"

        # Banned generic meta-fallbacks and grammatical glitches
        assert "Assuming a quick verbal summary is enough" not in notes, f"Slide {idx} has generic verbal summary myth"
        assert "Reading a short definition of" not in notes, f"Slide {idx} has generic short definition myth"
        assert "how do Visual Inventory work together" not in notes, f"Slide {idx} has broken Visual Inventory grammar"
        assert "how do Requirement 1a and Requirement 1b work together" not in notes, f"Slide {idx} uses raw sub-req IDs as topic nouns"

        # Verify visual_caption is not duplicated verbatim in both Pacing and Rubric
        lines_by_section = {}
        for ln in notes.splitlines():
            for header in (
                "[PACING & MODALITY]",
                "[ASK SCOUTS FIRST]",
                "[EXPECTED PAMPHLET ANSWER KEY]",
                "[COMMON MISCONCEPTION TO CORRECT]",
                "[DEMONSTRATION & SIGN-OFF RUBRIC]",
            ):
                if ln.strip().startswith(header):
                    lines_by_section[header] = ln.strip()

        raw_cap = str(s.get("visual_caption") or "").strip().rstrip(".")
        raw_title = str(s.get("title") or "").strip().rstrip(".")
        if len(raw_cap) > 20 and s.get("diagram_path") and raw_cap.lower() not in raw_title.lower():
            in_pacing = raw_cap in lines_by_section.get("[PACING & MODALITY]", "")
            in_demo = raw_cap in lines_by_section.get("[DEMONSTRATION & SIGN-OFF RUBRIC]", "")
            assert not (in_pacing and in_demo), f"Slide {idx} duplicates visual_caption verbatim in both Pacing and Rubric"

        if str(s.get("req_number")) == "1":
            pacing_lines.append(lines_by_section["[PACING & MODALITY]"])
            ask_lines.append(lines_by_section["[ASK SCOUTS FIRST]"])
            key_lines.append(lines_by_section["[EXPECTED PAMPHLET ANSWER KEY]"])
            misc_lines.append(lines_by_section["[COMMON MISCONCEPTION TO CORRECT]"])
            demo_lines.append(lines_by_section["[DEMONSTRATION & SIGN-OFF RUBRIC]"])

    # Every slide in Requirement 1 must have distinct Pacing, Ask, Answer Key, Misconception, and Rubric blocks
    assert len(set(pacing_lines)) == len(req1_slides), "Req 1 slides must have distinct [PACING & MODALITY] lines"
    assert len(set(ask_lines)) == len(req1_slides), "Req 1 slides must have distinct [ASK SCOUTS FIRST] lines"
    assert len(set(key_lines)) == len(req1_slides), "Req 1 slides must have distinct [EXPECTED PAMPHLET ANSWER KEY] lines"
    assert len(set(misc_lines)) == len(req1_slides), "Req 1 slides must have distinct [COMMON MISCONCEPTION TO CORRECT] lines"
    assert len(set(demo_lines)) == len(req1_slides), "Req 1 slides must have distinct [DEMONSTRATION & SIGN-OFF RUBRIC] lines"

    # Verify Sub-Requirement Deep Dive (1a-1d) and (1e-1g) scope to their own sub-requirements
    deep_dive_slides = [
        s
        for s in req1_slides
        if "Sub-Requirement Deep Dive" in str(s.get("title") or "")
        or "Reqs 1a-1d" in str(s.get("title") or "")
        or "Reqs 1e-1g" in str(s.get("title") or "")
    ]
    assert len(deep_dive_slides) >= 2
    dd_1_notes = str(deep_dive_slides[0].get("presenter_notes") or "")
    dd_2_notes = str(deep_dive_slides[1].get("presenter_notes") or "")
    dd_1_key = dd_1_notes.split("[EXPECTED PAMPHLET ANSWER KEY]")[1].split("[COMMON")[0]
    dd_2_key = dd_2_notes.split("[EXPECTED PAMPHLET ANSWER KEY]")[1].split("[COMMON")[0]
    assert "(1a)" in dd_1_key and "(1e)" not in dd_1_key
    assert "(1e)" in dd_2_key and "(1a)" not in dd_2_key

    # Verify beautify_slide_storyboard preserves non-repetitive notes and passes req_dict + slide_idx_in_req
    beautified = beautify_slide_storyboard(
        storyboard_res,
        beautification_tier="STANDARD",
        max_ai_images=0,
        research_artifact=pamphlet,
    )
    b_slides = beautified["storyboard"]["slides"]
    b_req1 = [s for s in b_slides if str(s.get("req_number")) == "1"]
    b_misc = [
        next(ln.strip() for ln in str(s.get("presenter_notes") or "").splitlines() if ln.strip().startswith("[COMMON MISCONCEPTION TO CORRECT]"))
        for s in b_req1
    ]
    assert len(set(b_misc)) == len(b_req1)
    for m_ln in b_misc:
        assert "Assuming a quick verbal summary is enough" not in m_ln
        assert "Reading a short definition of" not in m_ln


def test_v22_studio_ai_polish_endpoint_and_synthesizer_elevation() -> None:
    """Verify /api/v1/slide/polish-notes and _synthesize_studio_narrative_script produce elevated, non-generic scripts."""
    import builtins
    from typing import Tuple

    if not hasattr(builtins, "Tuple"):
        setattr(builtins, "Tuple", Tuple)
    from src.server import app

    client = TestClient(app)
    sample_slide = {
        "title": "Requirement 1: Sub-Requirement Deep Dive (1a-1d)",
        "req_number": "1",
        "archetype": "SPLIT_VISUAL_EXPLAINER",
        "verbatim_requirement_text": "Demonstrate to your counselor that you have current knowledge of all first-aid requirements for Tenderfoot, Second Class, and First Class ranks.",
        "bullet_points": [
            "Requirement 1a: Explain how you would obtain emergency medical assistance from your home and on a wilderness campout.",
            "Requirement 1b: Define the term triage and explain how it applies to a multi-casualty outdoor emergency.",
            "Requirement 1c: Describe the standard Universal Precautions Scouts take to protect against bloodborne pathogens.",
            "Requirement 1d: Demonstrate how to prepare an emergency action plan for a troop hike.",
        ],
        "visual_caption": "Visual Inventory: Wilderness EMS dispatch and patrol triage protocol",
        "diagram_path": "/assets/diagrams/first_aid_req1.png",
        "local_grounding_callout": "Yosemite Search and Rescue (YOSAR) wilderness dispatch channels",
    }

    resp = client.post(
        "/api/v1/slide/polish-notes",
        json={
            "badge_name": "First Aid",
            "slide_index": 1,
            "slide_data": sample_slide,
            "audience_level": "All Scouts (Ages 11-17)",
            "force_refresh": True,
            "variation_seed": 2,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    notes = data["presenter_notes"]

    for header in (
        "[PACING & MODALITY]",
        "[ASK SCOUTS FIRST]",
        "[EXPECTED PAMPHLET ANSWER KEY]",
        "[COMMON MISCONCEPTION TO CORRECT]",
        "[DEMONSTRATION & SIGN-OFF RUBRIC]",
    ):
        assert header in notes

    assert "Assuming a quick verbal summary is enough" not in notes
    assert "Reading a short definition of" not in notes
    assert "overlooks Requirement 1a" not in notes
    assert "Yosemite Search and Rescue" in notes
