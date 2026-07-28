"""Unit tests for Scouts BSA tools, Pydantic schemas, and Guided Error Handling.

Verifies:
1. Pydantic schema validation and GuidedToolError recovery instructions.
2. Eagle-Required merit badge recognition.
3. python-pptx presentation generation with official Scouts BSA branding.
"""

import os
import pytest
from src.tools.scouting_scraper import fetch_merit_badge_pamphlet_pdf, MeritBadgeResearchRequest
from src.tools.pptx_builder import generate_bsa_slide_deck_pptx, PowerPointBuildRequest, SlideSpec, CounselorTitleSlideInfo
from src.config import is_eagle_required

def test_eagle_required_recognition():
    assert is_eagle_required("First Aid") is True
    assert is_eagle_required("Camping") is True
    assert is_eagle_required("Citizenship in the Community") is True
    assert is_eagle_required("Robotics") is False
    assert is_eagle_required("Welding") is False
    assert is_eagle_required(None) is False
    assert is_eagle_required("") is False
    assert is_eagle_required(12345) is False

def test_fetch_merit_badge_pamphlet_success():
    req = MeritBadgeResearchRequest(badge_name="First Aid")
    res = fetch_merit_badge_pamphlet_pdf(req)
    assert res["status"] == "SUCCESS"
    assert res["badge_name"] == "First Aid"
    assert res["is_eagle_required"] is True
    assert len(res["requirements"]) >= 3

def test_guided_error_handling_unknown_badge():
    req = MeritBadgeResearchRequest(badge_name="NonExistentBadge123")
    res = fetch_merit_badge_pamphlet_pdf(req)
    assert "error_type" in res
    assert res["error_type"] == "BADGE_PAMPHLET_NOT_FOUND"
    assert "recovery_suggestion" in res
    assert len(res["available_badges_sample"]) > 0

def test_generate_pptx_presentation(tmp_path):
    out_file = os.path.join(tmp_path, "Test_First_Aid.pptx")
    slides = [
        SlideSpec(
            title="Req 1: Emergency Preparedness",
            bullet_points=["Point 1", "Point 2", "Point 3"],
            presenter_notes="Counselor notes here.",
            safety_warning="Always ensure scene safety."
        )
    ]
    counselor = CounselorTitleSlideInfo(
        counselor_name="John Doe",
        troop_affiliation="Troop 101, Golden Gate",
        email_address="john.doe@example.com"
    )
    req = PowerPointBuildRequest(
        badge_name="First Aid",
        slides=slides,
        counselor_info=counselor,
        output_path=out_file
    )
    res = generate_bsa_slide_deck_pptx(req)
    assert res["status"] == "SUCCESS"
    assert os.path.exists(res["output_path"])
    assert res["slide_count"] == 2  # 1 title slide + 1 content slide
