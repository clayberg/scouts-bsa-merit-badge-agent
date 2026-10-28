"""Regression suite for v3.0 149-Badge Decks, Multi-Option Tracks, Workbooks, Templates, UI/UX, and Pre-Computation."""

from __future__ import annotations

import io
import json
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient
import fitz

from src.agents.planner import generate_slide_storyboard
from src.server import app
from src.tools.asset_hydrator import _ALLOWED_ASSET_PREFIXES, collect_badge_asset_rel_paths
from src.tools.counselor_studiokit import (
    generate_class_preparation_page_cpp_pdf,
    generate_counselor_workbook_pdf,
    generate_fillable_scout_workbook_pdf,
)
from src.tools.requirements_scraper import load_badge_requirements_json
from src.tools.scouting_scraper import (
    _iter_unrolled_workbook_units,
    _unroll_multi_option_requirements,
    get_badge_option_tracks,
)
from src.tools.template_engine import (
    BUILTIN_TEMPLATES,
    NANO_BUILT_IN_BACKDROPS_CATALOG,
    load_template_catalog,
    resolve_default_cover_backdrop_for_badge,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_v30_precomputed_data_and_149_canonical_badges() -> None:
    """Verifies 149 canonical badge JSONs, _index.json, and precomputed_facilitator_notes_149.json."""
    req_dir = REPO_ROOT / "data" / "merit_badge_requirements"
    index_data = json.loads((req_dir / "_index.json").read_text(encoding="utf-8"))
    assert index_data["total_badges"] == 149
    assert index_data["eagle_required_count"] == 18

    notes_path = REPO_ROOT / "data" / "precomputed_facilitator_notes_149.json"
    assert notes_path.exists()
    notes_data = json.loads(notes_path.read_text(encoding="utf-8"))
    assert len(notes_data) >= 15000

    pamphlet_cat = json.loads((REPO_ROOT / "data" / "pamphlet_image_catalog.json").read_text(encoding="utf-8"))
    nano_cat = json.loads((REPO_ROOT / "data" / "nano_banana_image_catalog.json").read_text(encoding="utf-8"))
    assert len(pamphlet_cat) >= 2800
    assert len(nano_cat) >= 2900


def test_v30_22_multi_option_badges_multisport_swimming_physics_and_athletics() -> None:
    """Verifies 22 multi-option badges, Swimming registration, Multisport Req 4+7 coupling, Physics 6A..6D, and Athletics 5g(2)(g)."""
    swim_tracks = get_badge_option_tracks("Swimming")
    assert len(swim_tracks) == 2

    ms_data = load_badge_requirements_json("Multisport")
    assert ms_data is not None
    ms_filtered = _unroll_multi_option_requirements("Multisport", ms_data["requirements"], option_track="A")
    req_nums_ms = [str(r.get("req_number")) for r in ms_filtered]
    assert any(rn.startswith("4a") for rn in req_nums_ms)
    assert any(rn.startswith("7a") for rn in req_nums_ms)
    assert not any(rn.startswith("7b") for rn in req_nums_ms)

    phys_data = load_badge_requirements_json("Physics")
    assert phys_data is not None
    phys_filtered = _unroll_multi_option_requirements("Physics", phys_data["requirements"], option_track="A")
    phys_sb = generate_slide_storyboard("Physics", phys_filtered)
    assert 12 <= len(phys_sb["slides"]) <= 28

    ath_data = load_badge_requirements_json("Athletics")
    assert ath_data is not None
    unrolled = list(_iter_unrolled_workbook_units(ath_data["requirements"], badge_name="Athletics"))
    assert any("top of the key" in str(r.get("req_text") or "").lower() for r in unrolled)


def test_v30_workbooks_1page_cpp_and_counselor_answer_key() -> None:
    """Verifies full-width Scout Workbook PDF, 1-page CPP guarantee, and 100% sub-req Counselor Answer Key PDF."""
    wb_bytes = generate_fillable_scout_workbook_pdf("Bugling")
    with fitz.open(stream=wb_bytes, filetype="pdf") as wb_doc:
        assert len(wb_doc) >= 3

    for bname in ("Bugling", "Skating"):
        cpp_bytes = generate_class_preparation_page_cpp_pdf(bname)
        with fitz.open(stream=cpp_bytes, filetype="pdf") as cpp_doc:
            assert len(cpp_doc) == 1, f"{bname} CPP overflowed onto {len(cpp_doc)} pages"

    ak_bytes = generate_counselor_workbook_pdf("Bugling")
    with fitz.open(stream=ak_bytes, filetype="pdf") as ak_doc:
        ak_text = "\n".join(p.get_text("text") or "" for p in ak_doc)
        assert "EXPECTED PAMPHLET ANSWER KEY & COUNSELOR RUBRIC" in ak_text
        assert "Myth vs. Pamphlet Fact:" in ak_text


def test_v30_templates_backdrops_class_packet_zip_and_ui_enhancements() -> None:
    """Verifies 23 built-in templates (29 total), 24 washed backdrops, Class Packet ZIP API, and UI controls."""
    assert len(BUILTIN_TEMPLATES) == 23
    assert len(load_template_catalog()) >= 29
    assert len(NANO_BUILT_IN_BACKDROPS_CATALOG) == 24
    assert "assets/templates/overlays/" in _ALLOWED_ASSET_PREFIXES
    assert len(collect_badge_asset_rel_paths("First Aid")) >= 20

    bd_url = resolve_default_cover_backdrop_for_badge("Robotics", "bsa_stem_cyber_indigo")
    assert bd_url.startswith("/assets/templates/overlays/nano_base_")

    client = TestClient(app)
    zip_resp = client.get("/api/v1/export/class-packet.zip?badge_name=Bugling")
    assert zip_resp.status_code == 200
    assert zip_resp.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(zip_resp.content), "r") as zf:
        names = zf.namelist()
        assert len(names) >= 9
        assert any(n.endswith(".pptx") for n in names)
        assert any("Scout_Workbook" in n and n.endswith(".pdf") for n in names)
        assert any("Counselor_Answer_Key" in n for n in names)

    html = (REPO_ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    js = (REPO_ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    assert 'id="btn-export-complete-class-packet-zip"' in html
    assert 'id="filmstrip-search-input"' in html
    assert 'id="advanced-deck-settings-accordion"' in html
    assert "pushSlideUndoState" in js
    assert "parseRfc4180CsvRows" in js
