"""Unit tests for Context & Memory (Rubric Category 2).

Verifies:
1. History compaction (EventsCompactionConfig and additive summarization).
2. Persistent session state in SQLite database.
3. Asynchronous memory operations (save, load, and pamphlet indexing).
"""

import os
import pytest
import asyncio
from src.memory.session_store import (
    EventsCompactionConfig,
    compact_conversation_events,
    PersistentSessionStore,
    save_session_state_async,
    load_session_state_async,
    index_pamphlet_memory_async,
)

def test_history_compaction_algorithm():
    config = EventsCompactionConfig(compaction_interval=3, overlap_size=2, compaction_strategy="additive")
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

def test_persistent_session_store_sqlite(tmp_path):
    db_file = os.path.join(tmp_path, "test_sessions.db")
    store = PersistentSessionStore(db_path=db_file)
    
    saved = store.save_session_sync(
        session_id="counselor_session_101",
        badge_name="First Aid",
        counselor_info={"counselor_name": "Jane Doe", "troop": "101"},
        history=[{"type": "start"}]
    )
    assert saved is True
    
    loaded = store.get_session_sync("counselor_session_101")
    assert loaded is not None
    assert loaded["session_id"] == "counselor_session_101"
    assert loaded["badge_name"] == "First Aid"
    assert loaded["counselor_info"]["counselor_name"] == "Jane Doe"
    assert len(loaded["history"]) == 1

@pytest.mark.asyncio
async def test_asynchronous_memory_operations(tmp_path):
    db_file = os.path.join(tmp_path, "async_test_sessions.db")
    store = PersistentSessionStore(db_path=db_file)
    
    res_save = await save_session_state_async(
        session_id="async_sess_001",
        badge_name="Camping",
        counselor_info={"counselor_name": "John Scout"},
        history=[{"type": "async_start"}],
        store=store
    )
    assert res_save["status"] == "SUCCESS"
    assert res_save["saved"] is True
    
    res_load = await load_session_state_async("async_sess_001", store=store)
    assert res_load["status"] == "SUCCESS"
    assert res_load["session_data"]["badge_name"] == "Camping"
    
    res_index = await index_pamphlet_memory_async("Camping", "Req 1: Camping safety and Leave No Trace.")
    assert res_index["status"] == "SUCCESS"
    assert res_index["indexed_chars"] > 0
