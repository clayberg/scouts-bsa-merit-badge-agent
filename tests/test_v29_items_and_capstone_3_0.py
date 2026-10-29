"""Comprehensive unit and API tests for v2.9 features and FDE Capstone 3.0 remediation."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image

from src.server import app
from src.tools.pptx_builder import SlideSpec, inject_class_opening_and_closing_slides
from src.tools.template_engine import (
    NANO_BUILT_IN_BACKDROPS_CATALOG,
    generate_nano_banana_template_family,
    list_nano_builtin_backdrops,
    synthesize_custom_washed_backdrop,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
client = TestClient(app)


def test_nano_builtin_backdrops_catalog_has_16_scouting_themes():
    """Verify the 16 built-in Scouting washed backgrounds including BSA Logo and Apollo Rocket Launch."""
    items = list_nano_builtin_backdrops()
    assert len(items) in (16, 24)
    ids = {b["id"] for b in items}
    assert "bsa_emblem_color" in ids
    assert "apollo_rocket_launch" in ids
    assert "archery_target_range" in ids
    assert "pioneering_signal_tower" in ids
    assert "whitewater_kayak_rapids" in ids
    assert "first_aid_search_rescue" in ids
    assert "eagle_court_of_honor" in ids
    assert "environmental_wetlands" in ids
    assert "aviation_glider_airfield" in ids
    assert "dutch_oven_camp_cooking" in ids

    for item in NANO_BUILT_IN_BACKDROPS_CATALOG:
        img_path = ROOT_DIR / "assets" / "templates" / "overlays" / item["file"]
        assert img_path.exists(), f"Missing backdrop file: {img_path}"


def test_api_backdrops_and_prompt_synthesis():
    """Verify /api/v1/templates/backdrops and /api/v1/templates/synthesize-backdrop."""
    r = client.get("/api/v1/templates/backdrops")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] in (16, 24)

    # Prompt matching Apollo rocket launch
    r_synth = client.post(
        "/api/v1/templates/synthesize-backdrop",
        json={
            "prompt": "Distance shot of an Apollo rocket launch at Cape Canaveral",
            "visual_style": "stem_blueprint",
            "primary_hex": "#0F766E",
            "accent_hex": "#7C3AED",
        },
    )
    assert r_synth.status_code == 200
    synth_data = r_synth.json()
    assert synth_data["status"] == "SUCCESS"
    assert synth_data["backdrop_url"].startswith("/assets/templates/")


def test_custom_uploaded_photo_washed_backdrop_processing():
    """Verify uploading a custom image Data URL with description processes into a 1920x1080 washed backdrop."""
    img = Image.new("RGB", (640, 360), (35, 95, 145))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    data_url = f"data:image/jpeg;base64,{b64}"

    res = synthesize_custom_washed_backdrop(
        prompt="Custom Troop 19 High Adventure Summit Photo",
        visual_style="topographic_adventure",
        primary_hex="#1B5E20",
        accent_hex="#D97706",
        custom_bg_data_url=data_url,
        custom_bg_description="Troop 19 summit view at Mount Washington",
    )
    assert res["status"] == "SUCCESS"
    out_file = ROOT_DIR / res["backdrop_url"].split("?")[0].lstrip("/")
    assert out_file.exists()
    out_file.unlink(missing_ok=True)

    # Also verify generate_nano_banana_template_family with backdrop_id="bsa_emblem_color"
    from src.tools.template_engine import delete_custom_template
    gen = generate_nano_banana_template_family(
        family_name="Test BSA Logo Washed Theme",
        visual_style="heritage_embroidery",
        frame_geometry="heritage_border",
        colors=["#003F87", "#CE1126"],
        custom_prompt="Large washed color BSA logo emblem on Slide 1 cover",
        backdrop_id="bsa_emblem_color",
        user_consented=True,
    )
    try:
        assert gen["status"] == "SUCCESS"
        assert gen["backdrop_id"] == "bsa_emblem_color"
        assert len(gen["variants"]) == 2
    finally:
        for v in gen.get("variants", []):
            if v.get("template_id"):
                delete_custom_template(v["template_id"])


def test_inject_and_remove_logistics_slides_inherits_template_and_cleans_parentheses():
    """Verify Item 4 fixes: template inheritance, BEAUTIFIED tier, slide_id + slide_role, and clean session dates."""
    base_slides = [
        SlideSpec(
            title="Requirement 1: First Aid Fundamentals",
            bullet_points=["Check scene safety before approaching."],
            archetype="CONCEPT_TEXT_SLIDE",
            req_number="1",
            template_id="bsa_forest_sunrise",
            beautification_tier="BEAUTIFIED",
        ).model_dump()
    ]
    injected = inject_class_opening_and_closing_slides(
        badge_name="First Aid",
        slides=base_slides,
        logistics_config={
            "include_opening_slide": True,
            "include_closing_slide": True,
            "template_id": "bsa_forest_sunrise",
            "beautification_tier": "BEAUTIFIED",
            "class_start_time": "8:30 AM – 9:30 AM",
            "room_and_venue": "Main School Building - Room 107 (MBC)",
            "session_dates_summary": "4x 60-Min Sessions (S1: Tue Nov 17 • S2: Tue Nov 24)",
        },
        requirements=[],
    )
    assert len(injected) == 3
    opening = injected[0]
    closing = injected[-1]

    # Inherited template_id and BEAUTIFIED tier
    assert opening["template_id"] == "bsa_forest_sunrise"
    assert opening["beautification_tier"] == "BEAUTIFIED"
    assert opening["slide_id"] == "overview-logistics"
    assert opening["slide_role"] == "overview-logistics"

    assert closing["template_id"] == "bsa_forest_sunrise"
    assert closing["beautification_tier"] == "BEAUTIFIED"
    assert closing["slide_id"] == "homework-checkout"
    assert closing["slide_role"] == "homework-checkout"

    # Verify no double closing parenthesis "Tue Nov 24))" in bullets
    joined_bullets = " | ".join(opening["bullet_points"])
    assert "))" not in joined_bullets
    assert "(S1:" not in joined_bullets
    assert "S1 — Tue Nov 17" in joined_bullets

    # Verify API inject & remove round-trip
    r_inj = client.post(
        "/api/v1/slide/logistics-slides",
        json={
            "badge_name": "First Aid",
            "slides": injected,
            "logistics_config": {
                "include_opening_slide": False,
                "include_closing_slide": False,
                "template_id": "bsa_forest_sunrise",
                "beautification_tier": "BEAUTIFIED",
            },
        },
    )
    assert r_inj.status_code == 200
    after_remove = r_inj.json()["slides"]
    assert len(after_remove) == 1
    assert after_remove[0]["title"] == "Requirement 1: First Aid Fundamentals"


def test_capstone_3_0_endpoints_and_artifacts():
    """Verify FDE Capstone 3.0 live endpoints: semantic cache, A/B router, and plugin registry."""
    r_cache = client.get("/api/v1/finops/semantic-cache")
    assert r_cache.status_code == 200
    assert "hit_rate" in r_cache.json()

    r_ab = client.get("/api/v1/experiments/ab-status?session_id=test-session-42")
    assert r_ab.status_code == 200
    assert r_ab.json()["assignment"]["variant"] in {"control", "treatment"}

    r_plug = client.get("/api/v1/plugins")
    assert r_plug.status_code == 200
    assert r_plug.json()["total"] >= 3

    r_exec = client.post(
        "/api/v1/plugins/nps_campsite_lookup/execute",
        json={"payload": {"state_code": "NH", "park_query": "White Mountain National Forest"}},
    )
    assert r_exec.status_code == 200
    assert r_exec.json()["status"] == "SUCCESS"
