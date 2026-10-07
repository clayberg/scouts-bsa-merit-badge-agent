"""Unit tests for Context & Memory (Rubric Category 2).

Verifies:
1. History compaction (`EventsCompactionConfig`, ADK `to_adk_compaction_config()`, `get_adk_context_cache_config()`, and token-budget truncation).
2. Persistent session state in SQLite database with automatic PII redaction.
3. Asynchronous memory operations (`save_session_state_async`, `load_session_state_async`, `index_pamphlet_memory_async`, and `retrieve_pamphlet_memory_chunks`).
"""

import os
import pytest
from src.memory.session_store import (
    EventsCompactionConfig,
    compact_conversation_events,
    get_adk_context_cache_config,
    PersistentSessionStore,
    save_session_state_async,
    load_session_state_async,
    index_pamphlet_memory_async,
    retrieve_pamphlet_memory_chunks,
)


def test_history_compaction_algorithm():
    config = EventsCompactionConfig(
        compaction_interval=3,
        overlap_size=2,
        compaction_strategy="additive",
        token_Compaction_budget=4000,
    )
    events = [
        {"type": "user_input", "content": "Generate First Aid deck"},
        {"type": "tool_outcome", "tool_name": "fetch_merit_badge_pamphlet_pdf", "status": "SUCCESS"},
        {"type": "counselor_info", "data": "Troop 101"},
        {"type": "tool_outcome", "tool_name": "generate_bsa_slide_deck_pptx", "status": "SUCCESS"},
        {"type": "workflow_complete", "slides": 10},
    ]
    compacted = compact_conversation_events(events, config=config)
    assert len(compacted) == 3  # 1 summary event + last 2 overlap events
    assert compacted[0]["type"] == "compacted_history_summary"
    assert compacted[0]["turn_count_compacted"] == 3
    assert compacted[-1]["type"] == "workflow_complete"

    # Also verify native ADK compaction & context cache config builders
    adk_compaction = config.to_adk_compaction_config()
    assert adk_compaction is not None
    adk_cache = get_adk_context_cache_config()
    assert adk_cache is not None


def test_persistent_session_store_sqlite(tmp_path):
    db_file = os.path.join(tmp_path, "test_sessions.db")
    store = PersistentSessionStore(db_path=db_file)

    saved = store.save_session_sync(
        session_id="counselor_session_101",
        badge_name="First Aid",
        counselor_info={"counselor_name": "Jane Doe", "troop": "101", "email": "jane.doe@troop101.org"},
        history=[{"type": "start", "note": "Reach counselor at (415) 555-0199"}],
    )
    assert saved is True

    loaded = store.get_session_sync("counselor_session_101")
    assert loaded is not None
    assert loaded["session_id"] == "counselor_session_101"
    assert loaded["badge_name"] == "First Aid"
    assert loaded["counselor_info"]["counselor_name"] == "Jane Doe"
    # Verify PII is automatically scrubbed before SQLite persistence
    assert loaded["counselor_info"]["email"] == "[REDACTED_EMAIL]"
    assert "[REDACTED_PHONE]" in loaded["history"][0]["note"]
    assert len(loaded["history"]) == 1


@pytest.mark.asyncio
async def test_asynchronous_memory_operations_and_vector_retrieval(tmp_path):
    db_file = os.path.join(tmp_path, "async_test_sessions.db")
    store = PersistentSessionStore(db_path=db_file)

    res_save = await save_session_state_async(
        session_id="async_sess_001",
        badge_name="Camping",
        counselor_info={"counselor_name": "John Scout"},
        history=[{"type": "async_start"}],
        store=store,
    )
    assert res_save["status"] == "SUCCESS"
    assert res_save["saved"] is True

    res_load = await load_session_state_async("async_sess_001", store=store)
    assert res_load["status"] == "SUCCESS"
    assert res_load["session_data"]["badge_name"] == "Camping"

    res_index = await index_pamphlet_memory_async(
        badge_name="Camping",
        requirements_text=(
            "Requirement 1a: Explain Leave No Trace Seven Principles and Outdoor Code.\n\n"
            "Requirement 2: Demonstrate tent pitching, campsite selection, and hypothermia prevention."
        ),
        store=store,
    )
    assert res_index["status"] == "SUCCESS"
    assert res_index["indexed_chars"] > 0
    assert res_index["chunks_indexed"] >= 1

    # Verify vector similarity retrieval from persistent SQLite store
    chunks = store.search_pamphlet_vectors_sync("Camping", "Leave No Trace Outdoor Code", top_k=2)
    assert len(chunks) >= 1
    assert "Leave No Trace" in chunks[0]["chunk_text"]

    # Also test the ADK tool wrapper retrieve_pamphlet_memory_chunks
    await index_pamphlet_memory_async(
        badge_name="Weather",
        requirements_text="Cold fronts lift warm moist air rapidly to form cumulonimbus thunderstorms.",
    )
    tool_res = retrieve_pamphlet_memory_chunks("Weather", "cold fronts cumulonimbus", top_k=2)
    assert tool_res["status"] == "SUCCESS"
    assert tool_res["match_count"] >= 1


def test_hybrid_rrf_bm25_and_citation_grounding_and_trajectory_eval(tmp_path):
    """Verifies Hybrid RRF (BM25 + Dense Vector), citation grounding, trajectory metrics, and demo preflight."""
    from scripts.eval_gate import (
        EXPECTED_AGENT_TRAJECTORY,
        evaluate_tool_trajectory,
        promote_session_to_golden_dataset,
        run_vertex_genai_eval_task,
    )
    from scripts.verify_live_demo_readiness import verify_live_demo_readiness
    from src.agents.reviewer import verify_slide_citation_grounding

    db_file = os.path.join(tmp_path, "rrf_test.db")
    store = PersistentSessionStore(db_path=db_file)
    store.index_pamphlet_chunks_sync(
        badge_name="First Aid",
        requirements_text=(
            "[REQ-1a] Demonstrate how to care for someone who is choking using abdominal thrusts.\n\n"
            "[REQ-2b] Apply direct pressure and a tourniquet for life-threatening arterial bleeding.\n\n"
            "[REQ-4a] Describe the signs and symptoms of anaphylaxis and how to use an epinephrine auto-injector."
        ),
    )

    hits = store.hybrid_search_pamphlet_rrf_sync("First Aid", "Requirement 2b tourniquet arterial", top_k=2)
    assert len(hits) >= 1
    assert "[REQ-2b]" in hits[0]["chunk_text"]
    assert hits[0]["source"] == "sqlite_hybrid_rrf_vector_bm25"
    assert hits[0]["rrf_score"] > 0.0
    assert hits[0]["bm25_score"] > 0.0

    # Verify Citation Grounding Check
    cit = verify_slide_citation_grounding(
        slides=[
            {"title": "First Aid Cover", "archetype": "TITLE_COVER"},
            {"title": "Req 1a: Choking Care", "req_number": "1a", "bullet_points": ["Abdominal thrusts"]},
            {"title": "Req 2b: Bleeding Control", "req_number": "2b", "bullet_points": ["Direct pressure"]},
        ],
        requirements=[
            {"req_number": "1a", "description": "Care for choking"},
            {"req_number": "2b", "description": "Control bleeding"},
        ],
    )
    assert cit["passed"] is True
    assert cit["citation_coverage_ratio"] == 1.0

    # Verify Agent/Tool Trajectory Evaluation
    traj = evaluate_tool_trajectory(list(EXPECTED_AGENT_TRAJECTORY))
    assert traj["trajectory_exact_match"] == 1.0
    assert traj["trajectory_in_order_match"] == 1.0
    assert traj["trajectory_precision"] == 1.0
    assert traj["trajectory_recall"] == 1.0

    eval_task_res = run_vertex_genai_eval_task([{"badge_name": "First Aid", "score": 1.0}])
    assert eval_task_res["evaluated_rows"] == 1

    # Verify Continuous-Learning Golden Dataset Promotion (Subcategory 6.7)
    ext_file = tmp_path / "golden_extensions.json"
    promo = promote_session_to_golden_dataset(
        session_trace={
            "badge_name": "First Aid",
            "is_eagle_required": True,
            "requirement_count": 10,
            "session_id": "test_promo_session_1",
        },
        target_path=ext_file,
    )
    assert promo["status"] == "PROMOTED"
    assert promo["total_golden_extensions"] == 1

    # Verify Live Demo Readiness Pre-Flight Check (Subcategory 5.2)
    demo_report = verify_live_demo_readiness()
    assert demo_report["demo_ready"] is True


def test_schema_version_upcasting_and_sqlite_hitl_feedback(tmp_path):
    """Verifies non-breaking schema migration (v1.0 -> v1.1 -> v1.2.0) and SQLite hitl_feedback persistence."""
    from src.schemas import CURRENT_SCHEMA_VERSION, migrate_payload_schema

    # 1. Legacy v1.0 payload lacking schema_version, beautification_tier, audience_level, and citation_coverage_ratio
    legacy_v1_0 = {
        "badge_name": "First Aid",
        "counselor_info": {"counselor_name": "Eric Clayberg", "troop_affiliation": "Troop 19, Middleton MA"},
        "storyboard": {
            "slides": [
                {"req_number": "1a", "title": "Choking Care", "bullet_points": ["5 back blows", "5 abdominal thrusts"]}
            ]
        },
        "conformance_report": {"passed": True, "aabb_overlap_count": 0},
    }
    migrated = migrate_payload_schema(legacy_v1_0)
    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION == "1.2.0"
    assert migrated["beautification_tier"] == "BEAUTIFIED"
    assert migrated["audience_level"] == "All Scouts (Ages 11–17)"
    assert migrated["storyboard"]["slides"][0]["visual_source_label"] == "Official BSA Pamphlet Diagram"
    assert migrated["storyboard"]["slides"][0]["available_images"] == []
    assert migrated["conformance_report"]["citation_coverage_ratio"] == 1.0

    # 2. Verify PersistentSessionStore automatically upcasts legacy sessions on load and persists hitl_feedback
    db_file = os.path.join(tmp_path, "schema_evolution_test.db")
    store = PersistentSessionStore(db_path=db_file)
    store.save_session_sync(
        session_id="legacy_v1_session",
        badge_name="Weather",
        counselor_info={"counselor_name": "Eric Clayberg"},
        history=[{"type": "legacy_event"}],
    )
    loaded = store.get_session_sync("legacy_v1_session")
    assert loaded is not None
    assert loaded["schema_version"] == "1.2.0"

    fb_res = store.record_hitl_feedback_sync(
        session_id="legacy_v1_session",
        badge_name="Weather",
        counselor_name="Eric Clayberg",
        rating=5,
        requirement_accuracy_verified=True,
        comments="Verified 100% 2026 BSA Weather requirement fidelity.",
        promoted_to_golden=True,
        schema_version="1.2.0",
    )
    assert fb_res["recorded"] is True
    assert fb_res["promoted_to_golden"] is True

    rows = store.list_hitl_feedback_sync(badge_name="Weather")
    assert len(rows) == 1
    assert rows[0]["badge_name"] == "Weather"
    assert rows[0]["rating"] == 5
    assert rows[0]["requirement_accuracy_verified"] is True
    assert rows[0]["promoted_to_golden"] is True
    assert rows[0]["schema_version"] == "1.2.0"


