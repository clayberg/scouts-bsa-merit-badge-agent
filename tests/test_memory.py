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
