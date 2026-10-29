"""V35 Comprehensive Verification Suite: Complete Elimination of Mad-Libs Templates Across All 149 Badges."""

import json
import re
from pathlib import Path

from src.agents.researcher import compute_canonical_pamphlet_hash

REPO_ROOT = Path(__file__).resolve().parents[1]
REQ_DIR = REPO_ROOT / "data" / "merit_badge_requirements"
CACHE_PATH = REPO_ROOT / "data" / "official_requirements_cache.json"
NOTES_PATH = REPO_ROOT / "data" / "precomputed_facilitator_notes_149.json"


def _iter_badge_files():
    return sorted(
        f for f in REQ_DIR.glob("*.json")
        if not f.name.startswith("_") and f.name != "manifest.json"
    )


def test_v35_item1_titles_compounds_and_prefixes_clean():
    """Verifies clean topic titles, zero split compounds, zero double prefixes, and zero synthetic filler bullets."""
    files = _iter_badge_files()
    assert len(files) == 149

    forbidden_compounds = ("works pace", "incheslong", "skate park", "snow boarder")
    forbidden_synth = ("Verify all ", "Inspect the workspace", "Inspect the works pace", "Apply the official ")

    for f in files:
        raw_txt = f.read_text(encoding="utf-8")
        for bad_c in forbidden_compounds:
            assert bad_c not in raw_txt.lower(), f"Split compound {bad_c!r} found in {f.name}"

        d = json.loads(raw_txt)
        for r in d.get("requirements", []):
            rid = str(r.get("req_id") or r.get("req_number"))
            tt = str(r.get("topic_title") or "")
            assert tt.startswith(f"Req {rid}: "), f"Malformed topic_title {tt!r} in {f.name}"
            assert len(tt.split(":", 1)[1].strip()) >= 5, f"Empty/short topic_title {tt!r} in {f.name}"

            for ex in r.get("pamphlet_excerpts") or []:
                ex_s = str(ex)
                assert not re.search(r"Principle\s+\d+\s*:.*Principle\s+\d+\s*:", ex_s), f"Double prefix in {f.name} Req {rid}: {ex_s}"
                for syn in forbidden_synth:
                    assert syn not in ex_s, f"Synthetic filler excerpt in {f.name} Req {rid}: {ex_s}"

            for pr in r.get("step_by_step_procedure") or []:
                pr_s = str(pr)
                assert not re.search(r"Step\s+\d+.*:\s*Step\s+\d+", pr_s, flags=re.I), f"Double Step prefix in {f.name} Req {rid}: {pr_s}"
                for syn in forbidden_synth:
                    assert syn not in pr_s, f"Synthetic filler procedure in {f.name} Req {rid}: {pr_s}"


def test_v35_item2_gear_checklist_selective_and_accurate():
    """Verifies gear_checklist has zero generic fallback items and zero Archery/Weather false positives."""
    for f in _iter_badge_files():
        d = json.loads(f.read_text(encoding="utf-8"))
        for r in d.get("requirements", []):
            for g in r.get("gear_checklist") or []:
                assert "Primary reference documents, case-study exhibits" not in g, f"Generic gear fallback in {f.name}"

    archery = json.loads((REQ_DIR / "archery.json").read_text(encoding="utf-8"))
    archery_gear_blob = json.dumps(archery.get("requirements", [])).lower()
    assert "personal flotation" not in archery_gear_blob
    assert "throw bag" not in archery_gear_blob

    weather = json.loads((REQ_DIR / "weather.json").read_text(encoding="utf-8"))
    weather_gear_blob = json.dumps(weather.get("requirements", [])).lower()
    assert "specimen press" not in weather_gear_blob
    assert "pocket hand lens" not in weather_gear_blob


def test_v35_item3_and_item4_comparison_and_worked_example_overhaul():
    """Verifies 0 Mad-Libs comparison_data and worked_example across all 1,158 requirements."""
    forbidden_comp = (
        "Foundational Principles (",
        "Applied Field Execution (",
        "Proactive Hazard Prevention (",
        "Theoretical rules, terminology, and specifications for",
    )
    forbidden_we = (
        "Initial benchmark and target parameters recorded for",
        "Calibrated tools, materials, and workspace prepared for",
        "Calibrated tools, materials, and works pace prepared for",
        "Check that the Scout's entry includes specific technical details from",
    )

    for f in _iter_badge_files():
        d = json.loads(f.read_text(encoding="utf-8"))
        for r in d.get("requirements", []):
            rid = r.get("req_id")
            comp_str = json.dumps(r.get("comparison_data") or {})
            for bad_c in forbidden_comp:
                assert bad_c not in comp_str, f"Mad-Libs comparison_data in {f.name} Req {rid}: {bad_c}"

            we = r.get("worked_example") or {}
            we_str = json.dumps(we)
            for bad_w in forbidden_we:
                assert bad_w not in we_str, f"Mad-Libs worked_example in {f.name} Req {rid}: {bad_w}"
            for k in (we.get("fields") or {}).keys():
                assert k.count("(") == k.count(")"), f"Unbalanced parens in worked_example field key {k!r} in {f.name} Req {rid}"


def test_v35_item5_misconception_pairs_authentic_and_unique():
    """Verifies 0 Mad-Libs misconception templates across all 1,158 requirements and 2,911 sub-requirements."""
    forbidden_myths = (
        "only need to review safety rules and emergency procedures after an incident occurs",
        "relies only on hobby experience rather than formal training",
        "from memory at the end of the project satisfies",
        "are interchangeable regardless of operating conditions",
        "verbally can substitute for a physical hands-on demonstration",
        "watching a generic video without preparing questions",
        "general familiarity with ",
        "emerged all at once rather than evolving through the historical milestones",
        "works the same way under all conditions regardless of how",
        "operate identically and can be used interchangeably",
        "adjust automatically without manual verification",
        "standard household habits can replace",
        "focusing only on ",
        "only affects appearance and does not alter",
    )

    for f in _iter_badge_files():
        d = json.loads(f.read_text(encoding="utf-8"))
        for r in d.get("requirements", []):
            rid = r.get("req_id")
            mp = r.get("common_misconception_pair") or {}
            myth = str(mp.get("misconception") or "").strip()
            fact = str(mp.get("fact") or "").strip()
            assert myth and fact, f"Empty misconception/fact in {f.name} Req {rid}"
            for bad_m in forbidden_myths:
                assert bad_m not in myth.lower(), f"Mad-Libs myth in {f.name} Req {rid}: {myth}"

            for sr in r.get("sub_requirements") or []:
                if isinstance(sr, dict) and isinstance(sr.get("common_misconception_pair"), dict):
                    sr_myth = str(sr["common_misconception_pair"].get("misconception") or "").strip()
                    for bad_m in forbidden_myths:
                        assert bad_m not in sr_myth.lower(), f"Mad-Libs sub-req myth in {f.name} {sr.get('sub_id')}: {sr_myth}"
                    assert sr_myth.lower() != myth.lower(), f"Sub-req myth duplicates parent in {f.name} {sr.get('sub_id')}"


def test_v35_item6_quizzes_authentic_across_all_1158_requirements():
    """Verifies 0 Mad-Libs quiz prompts or distractors across all 1,158 requirements."""
    forbidden_quiz = (
        "encounters a decision point on proper procedure",
        "defer all ",
        "substitute uncalibrated equipment",
        "rely on a rough visual guess of",
        "focus only on ",
        "for a post-session summary",
        "reverse the relationship between ",
        "which approach satisfies the official scouting america standard",
        "what does the official scouting america",
    )

    for f in _iter_badge_files():
        d = json.loads(f.read_text(encoding="utf-8"))
        for r in d.get("requirements", []):
            rid = r.get("req_id")
            qi = r.get("quiz_item") or {}
            q_blob = json.dumps(qi).lower()
            for bad_q in forbidden_quiz:
                assert bad_q not in q_blob, f"Mad-Libs quiz in {f.name} Req {rid}: {bad_q}"
            opts = qi.get("options") or []
            assert len(opts) >= 3, f"Too few options in {f.name} Req {rid}"


def test_v35_item7_facilitator_notes_and_canonical_hash_integrity():
    """Verifies precomputed_facilitator_notes_149.json and canonical SHA-256 hash parity with official_requirements_cache.json."""
    notes = json.loads(NOTES_PATH.read_text(encoding="utf-8"))
    assert len(notes) >= 30000
    for k, v in list(notes.items())[:500]:
        for hdr in (
            "[PACING & MODALITY]",
            "[ASK SCOUTS FIRST]",
            "[EXPECTED PAMPHLET ANSWER KEY]",
            "[COMMON MISCONCEPTION TO CORRECT]",
            "[DEMONSTRATION & SIGN-OFF RUBRIC]",
        ):
            assert hdr in v, f"Missing {hdr} in facilitator note {k}"
        assert "what is the first field clue that confirms your patrol is following the official pamphlet standard" not in v

    # Role differentiation across 0..6 for First Aid Req 1
    asks = {notes[f"first-aid::1::{i}"].splitlines()[1] for i in range(7)}
    assert len(asks) == 7, f"Expected 7 distinct [ASK SCOUTS FIRST] lines across roles 0..6, got {len(asks)}"

    # Verify canonical hash parity across all 149 badges
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    for f in _iter_badge_files():
        d = json.loads(f.read_text(encoding="utf-8"))
        bname = d["badge_name"]
        c_entry = cache[bname]
        c_reqs = c_entry["requirements"] if isinstance(c_entry, dict) else c_entry
        assert compute_canonical_pamphlet_hash(d["requirements"]) == compute_canonical_pamphlet_hash(c_reqs), (
            f"Canonical hash mismatch for {bname}"
        )
