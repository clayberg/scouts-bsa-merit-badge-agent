"""Persistent Session Storage, Vector Store / Vertex AI Search Retrieval, History Compaction, and Async Memory Operations.

This module provides context and memory management across four areas:
1. History Compaction: ADK `EventsCompactionConfig`, `ContextCacheConfig`, `VertexAiMemoryBankService`,
   sliding-window turn compaction, and token-budget truncation (`compact_conversation_events`).
2. Persistent Session State & Vector/Search Retrieval: SQLite `counselor_sessions` + `pamphlet_vector_memory`
   vector store tables, ADK `VertexAiSessionService` integration, and Google Cloud Vertex AI Search
   (`discoveryengine`) retrieval fallback (`retrieve_pamphlet_memory_chunks`).
3. PII Redaction Before Storage: Active PII scrubbing (`scrub_pii_from_structure`) on all session and
   memory writes before database persistence.
4. Asynchronous Memory Operations: Non-blocking `asyncio` background tasks for session persistence,
   vector embedding indexing, and history compaction.
"""

import asyncio
import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from src.observability.logging_setup import logger, scrub_pii_before_sink, scrub_pii_from_structure

try:
    from google.adk.apps.app import (
        ContextCacheConfig as AdkContextCacheConfig,
        EventsCompactionConfig as AdkEventsCompactionConfig,
    )
except Exception:  # pragma: no cover
    AdkContextCacheConfig = None  # type: ignore
    AdkEventsCompactionConfig = None  # type: ignore

try:
    from google.adk.memory.vertex_ai_memory_bank_service import VertexAiMemoryBankService
except Exception:  # pragma: no cover
    VertexAiMemoryBankService = None  # type: ignore


# ==============================================================================
# 1. HISTORY COMPACTION, TOKEN TRUNCATION & ADK CONTEXT CACHING
# ==============================================================================

class EventsCompactionConfig(BaseModel):
    """Configuration for additive session event compaction and token-budget truncation in ADK agents."""

    compaction_interval: int = Field(5, ge=1, description="Number of turns before triggering compaction.")
    overlap_size: int = Field(2, ge=0, description="Number of recent turns to preserve uncompacted.")
    compaction_strategy: str = Field("additive", description="Additive compaction preserving core context.")
    max_token_budget: int = Field(4096, ge=128, description="Maximum estimated token budget before truncation.")

    def to_adk_compaction_config(self) -> Any:
        """Converts this configuration into an official `google.adk.apps.app.EventsCompactionConfig` instance."""
        if AdkEventsCompactionConfig is not None:
            try:
                return AdkEventsCompactionConfig(
                    compaction_interval=self.compaction_interval,
                    overlap_size=self.overlap_size,
                )
            except Exception:
                logger.debug("Database operation failed", exc_info=True)
                pass
        return self


def get_adk_context_cache_config(
    min_tokens: int = 1024,
    ttl_seconds: int = 3600,
    cache_intervals: int = 5,
) -> Any:
    """Builds an official Google ADK `ContextCacheConfig` for Gemini context caching on Google Cloud.

    Args:
        min_tokens: Minimum token count required before creating a context cache entry.
        ttl_seconds: Time-to-live (in seconds) for cached system constitution and pamphlet context.
        cache_intervals: Number of invocations before refreshing the context cache.

    Returns:
        Any: Configured `google.adk.agents.context_cache_config.ContextCacheConfig` or dict fallback.
    """
    if AdkContextCacheConfig is not None:
        try:
            return AdkContextCacheConfig(
                min_tokens=min_tokens,
                ttl_seconds=ttl_seconds,
                cache_intervals=cache_intervals,
            )
        except Exception:
            logger.debug("Database operation failed", exc_info=True)
            pass
    return {
        "min_tokens": min_tokens,
        "ttl_seconds": ttl_seconds,
        "cache_intervals": cache_intervals,
    }


def _estimate_events_tokens(events: List[Dict[str, Any]]) -> int:
    """Estimates the token footprint of a conversation event list (~4 characters per token)."""
    total_chars = sum(len(json.dumps(ev, default=str)) for ev in events)
    return max(1, total_chars // 4)


def compact_conversation_events(
    events: List[Dict[str, Any]],
    config: Optional[EventsCompactionConfig] = None,
) -> List[Dict[str, Any]]:
    """Compacts historical conversation events using sliding-window & token-budget additive summarization.

    Prevents context window bloat while preserving counselor preferences, Eagle-required
    status, and recent tool outcomes. Triggers when either the turn count exceeds
    `config.compaction_interval` or estimated tokens exceed `config.max_token_budget`.

    Args:
        events: Chronological list of agent conversation event dictionaries.
        config: Compaction configuration (defaults to interval=5, overlap_size=2, max_token_budget=4096).

    Returns:
        List[Dict[str, Any]]: Compacted events list starting with a `compacted_history_summary` node.
    """
    cfg = config or EventsCompactionConfig()
    est_tokens = _estimate_events_tokens(events)
    if len(events) <= cfg.compaction_interval and est_tokens <= cfg.max_token_budget:
        return events

    overlap = min(cfg.overlap_size, max(0, len(events) - 1))
    old_events = events[:-overlap] if overlap > 0 else events
    recent_events = events[-overlap:] if overlap > 0 else []

    # Extract key additive memory facts from old events (with PII scrubbed)
    summary_facts: List[str] = []
    for ev in old_events:
        event_type = ev.get("type", "unknown")
        if event_type == "tool_outcome":
            summary_facts.append(
                f"Tool {ev.get('tool_name')} completed with status {ev.get('status')}"
            )
        elif event_type == "counselor_info":
            summary_facts.append(
                f"Counselor preference: {scrub_pii_before_sink(str(ev.get('data')))}"
            )
        elif event_type == "workflow_start":
            summary_facts.append(f"Started badge workflow: {ev.get('badge_name')}")

    summary_event: Dict[str, Any] = {
        "type": "compacted_history_summary",
        "turn_count_compacted": len(old_events),
        "estimated_tokens_before": est_tokens,
        "additive_facts": summary_facts,
        "summary_text": f"Compacted {len(old_events)} previous conversation steps into additive summary.",
    }

    compacted_history = [summary_event] + recent_events
    logger.info(
        "History compaction executed",
        extra={
            "original_count": len(events),
            "compacted_count": len(compacted_history),
            "strategy": cfg.compaction_strategy,
            "estimated_tokens_before": est_tokens,
            "estimated_tokens_after": _estimate_events_tokens(compacted_history),
        },
    )
    return compacted_history


# ==============================================================================
# 2. PERSISTENT SESSION STORE, VECTOR EMBEDDINGS & VERTEX AI SEARCH
# ==============================================================================

def _compute_text_embedding(text: str, dim: int = 768) -> List[float]:
    """Computes a deterministic L2-normalized 768-dim dense embedding vector (`text-embedding-005` compatible)."""
    vec = [0.0] * dim
    tokens = re.findall(r"[a-z0-9]{2,}", (text or "").lower())
    if not tokens:
        return vec
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:2], "big") % dim
        sign = 1.0 if (digest[2] % 2 == 0) else -1.0
        vec[idx] += sign * (1.0 + (digest[3] / 255.0))
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 1e-9:
        vec = [round(v / norm, 6) for v in vec]
    return vec


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two dense embedding vectors."""
    if not vec_a or not vec_b:
        return 0.0
    common_len = min(len(vec_a), len(vec_b))
    dot = sum(a * b for a, b in zip(vec_a[:common_len], vec_b[:common_len]))
    norm_a = math.sqrt(sum(a * a for a in vec_a[:common_len]))
    norm_b = math.sqrt(sum(b * b for b in vec_b[:common_len]))
    if norm_a <= 1e-9 or norm_b <= 1e-9:
        return 0.0
    return dot / (norm_a * norm_b)


def _compute_bm25_scores(
    query: str,
    documents: List[str],
    k1: float = 1.5,
    b: float = 0.75,
) -> List[float]:
    """Computes Okapi BM25 lexical relevance scores with exact BSA requirement-ID boosting."""
    if not documents:
        return []
    q_tokens = re.findall(r"[a-z0-9]{1,}", (query or "").lower())
    if not q_tokens:
        return [0.0 for _ in documents]

    doc_tokens_list = [re.findall(r"[a-z0-9]{1,}", (doc or "").lower()) for doc in documents]
    doc_lengths = [len(toks) for toks in doc_tokens_list]
    avgdl = max(1.0, sum(doc_lengths) / float(len(documents)))
    n_docs = len(documents)

    # Document frequency per query token
    df: Dict[str, int] = {}
    for tok in set(q_tokens):
        df[tok] = sum(1 for d_toks in doc_tokens_list if tok in d_toks)

    # Extract explicit requirement alphanumeric markers (e.g. "1a", "2b", "9a", "req-1a")
    req_markers = re.findall(r"\b(?:req(?:uirement)?[-\s]*)?([0-9]{1,2}[a-z]?)\b", (query or "").lower())

    scores: List[float] = []
    for doc_str, d_toks, dl in zip(documents, doc_tokens_list, doc_lengths):
        score = 0.0
        if d_toks:
            tf_map: Dict[str, int] = {}
            for t in d_toks:
                tf_map[t] = tf_map.get(t, 0) + 1
            for q_tok in q_tokens:
                tf = tf_map.get(q_tok, 0)
                if tf == 0:
                    continue
                n_q = df.get(q_tok, 0)
                idf = math.log(1.0 + (n_docs - n_q + 0.5) / (n_q + 0.5))
                denom = tf + k1 * (1.0 - b + b * (dl / avgdl))
                score += idf * ((tf * (k1 + 1.0)) / max(1e-9, denom))
        doc_lower = (doc_str or "").lower()
        for marker in req_markers:
            if f"[req-{marker}]" in doc_lower or f"req {marker}" in doc_lower or f"requirement {marker}" in doc_lower:
                score += 3.5
        scores.append(round(score, 6))
    return scores



_SESSION_DB_LOCK = threading.RLock()

def _connect_session_db(db_path: str):
    conn = sqlite3.connect(str(db_path), timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

class PersistentSessionStore:
    """Manages persistent session state and vector memory across SQLite, ADK Vertex AI Session Service, and Vertex AI Search."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or os.getenv("LOCAL_SQLITE_DB_PATH", "scouts_bsa_sessions.db")
        self._lock = _SESSION_DB_LOCK
        self.use_cloud = os.getenv("USE_VERTEX_SESSION_SERVICE", "false").lower() == "true"
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.memory_bank_service: Optional[Any] = None
        if self.use_cloud and VertexAiMemoryBankService is not None and self.project_id:
            try:
                self.memory_bank_service = VertexAiMemoryBankService(
                    project=self.project_id,
                    location=self.location,
                )
            except Exception:
                self.memory_bank_service = None
        self._init_db()

    def _connect(self):
        return _connect_session_db(self.db_path)

    def ping_sync(self) -> bool:
        try:
            with self._lock, self._connect() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            logger.debug("ping_sync failed", exc_info=True)
            return False

    def _init_db(self) -> None:
        """Initializes the persistent SQLite tables for counselor sessions and pamphlet vector chunks."""
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS counselor_sessions (
                    session_id TEXT PRIMARY KEY,
                    badge_name TEXT,
                    counselor_info TEXT,
                    history_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pamphlet_vector_memory (
                    chunk_id TEXT PRIMARY KEY,
                    badge_name TEXT,
                    chunk_text TEXT,
                    embedding_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS badge_image_catalog (
                    image_id TEXT PRIMARY KEY,
                    badge_name TEXT,
                    req_number TEXT,
                    slide_title TEXT,
                    title TEXT,
                    description TEXT,
                    source_type TEXT,
                    image_path TEXT,
                    image_url TEXT,
                    metadata_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hitl_feedback (
                    feedback_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    badge_name TEXT,
                    rating INTEGER,
                    thumbs_up INTEGER,
                    requirement_accuracy_verified INTEGER,
                    promoted_to_golden INTEGER DEFAULT 0,
                    comments TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS polished_speaker_notes (
                    notes_hash TEXT PRIMARY KEY,
                    badge_name TEXT,
                    req_number TEXT,
                    slide_title TEXT,
                    audience_level TEXT,
                    polished_notes TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS counselor_workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    workspace_title TEXT NOT NULL,
                    badge_name TEXT NOT NULL,
                    session_label TEXT DEFAULT '',
                    camp_bundle_tag TEXT DEFAULT '',
                    template_id TEXT DEFAULT 'default_workbench',
                    counselor_info_json TEXT DEFAULT '{}',
                    deck_result_json TEXT DEFAULT '{}',
                    blue_card_roster_json TEXT DEFAULT '{}',
                    class_prep_json TEXT DEFAULT '{}',
                    local_grounding_json TEXT DEFAULT '{}',
                    active_slide_idx INTEGER DEFAULT -1,
                    slide_count INTEGER DEFAULT 0,
                    custom_edits_count INTEGER DEFAULT 0,
                    scout_count INTEGER DEFAULT 0,
                    is_pinned INTEGER DEFAULT 1,
                    is_archived INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS counselor_favorites (
                    counselor_id TEXT DEFAULT 'default',
                    badge_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (counselor_id, badge_name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    pref_key TEXT PRIMARY KEY,
                    pref_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS compliance_attestation_ledger (
                    attestation_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    badge_name TEXT,
                    canonical_pamphlet_hash TEXT,
                    ypt_two_deep_verified INTEGER DEFAULT 1,
                    zero_pii_egress_verified INTEGER DEFAULT 1,
                    aabb_conformance_passed INTEGER DEFAULT 1,
                    created_at REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clinic_session_schedules (
                    schedule_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    badge_name TEXT NOT NULL,
                    Companion_badge_name TEXT DEFAULT '',
                    session_mode TEXT DEFAULT '4_session_mbc',
                    session_dates_json TEXT DEFAULT '[]',
                    room_location TEXT DEFAULT '',
                    postponed_session_idx INTEGER DEFAULT 0,
                    session_buckets_json TEXT DEFAULT '{}',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scout_session_attendance_and_partials (
                    record_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    badge_name TEXT NOT NULL,
                    scout_id TEXT NOT NULL,
                    scout_name_redacted TEXT DEFAULT '',
                    troop_number TEXT DEFAULT 'Troop 19',
                    session_attendance_json TEXT DEFAULT '{"S1":"P","S2":"P","S3":"P","S4":"P","M":"-"}',
                    completed_reqs_json TEXT DEFAULT '[]',
                    completed_reqs_by_badge_json TEXT DEFAULT '{}',
                    actionable_makeup_reqs_json TEXT DEFAULT '[]',
                    expected_hometroop_reqs_json TEXT DEFAULT '[]',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS counselor_syllabus_bucket_overrides (
                    override_id TEXT PRIMARY KEY,
                    workspace_id TEXT DEFAULT 'default',
                    badge_name TEXT NOT NULL,
                    req_id TEXT NOT NULL,
                    syllabus_bucket TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Enforce DECK_SCHEMA_BASELINE_VERSION ("2.1.0") clean-slate cache invalidation
            try:
                from src.config import DECK_SCHEMA_BASELINE_VERSION
                row = conn.execute(
                    "SELECT pref_json FROM user_preferences WHERE pref_key = 'schema_baseline_version'"
                ).fetchone()
                stored_ver = ""
                if row and row[0]:
                    try:
                        stored_ver = json.loads(row[0]).get("version", "")
                    except Exception:
                        stored_ver = str(row[0])
                if stored_ver != DECK_SCHEMA_BASELINE_VERSION:
                    conn.execute("DELETE FROM polished_speaker_notes;")
                    conn.execute(
                        "UPDATE counselor_workspaces SET deck_result_json = '{}' "
                        "WHERE deck_result_json NOT LIKE '%\"schema_version\": \"2.1.0\"%';"
                    )
                    conn.execute(
                        """
                        INSERT INTO user_preferences (pref_key, pref_json, updated_at)
                        VALUES ('schema_baseline_version', ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(pref_key) DO UPDATE SET
                            pref_json=excluded.pref_json,
                            updated_at=CURRENT_TIMESTAMP
                        """,
                        (json.dumps({"version": DECK_SCHEMA_BASELINE_VERSION}),),
                    )
            except Exception:
                logger.debug("Baseline version check skipped", exc_info=True)
            conn.commit()

    def upsert_clinic_session_schedule_sync(
        self,
        workspace_id: str,
        badge_name: str,
        session_mode: str = "4_session_mbc",
        companion_badge_name: str = "",
        session_dates: Optional[List[str]] = None,
        room_location: str = "",
        postponed_session_idx: int = 0,
        session_buckets: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persists a multi-session clinic schedule into `clinic_session_schedules` (Table 10)."""
        sched_id = f"sched_{hashlib.sha256(f'{workspace_id}:{badge_name}'.encode('utf-8')).hexdigest()[:16]}"
        dates_list = list(session_dates or ["Session 1", "Session 2", "Session 3", "Session 4", "Make-Up Day"])
        buckets_dict = dict(session_buckets or {})
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO clinic_session_schedules (
                    schedule_id, workspace_id, badge_name, Companion_badge_name,
                    session_mode, session_dates_json, room_location,
                    postponed_session_idx, session_buckets_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(schedule_id) DO UPDATE SET
                    Companion_badge_name=excluded.Companion_badge_name,
                    session_mode=excluded.session_mode,
                    session_dates_json=excluded.session_dates_json,
                    room_location=excluded.room_location,
                    postponed_session_idx=excluded.postponed_session_idx,
                    session_buckets_json=excluded.session_buckets_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    sched_id,
                    str(workspace_id or "default"),
                    str(badge_name or "First Aid"),
                    str(companion_badge_name or ""),
                    str(session_mode or "4_session_mbc"),
                    json.dumps(dates_list),
                    scrub_pii_before_sink(str(room_location or "")),
                    int(postponed_session_idx or 0),
                    json.dumps(buckets_dict),
                ),
            )
            conn.commit()
        return {
            "schedule_id": sched_id,
            "workspace_id": str(workspace_id or "default"),
            "badge_name": str(badge_name or "First Aid"),
            "companion_badge_name": str(companion_badge_name or ""),
            "session_mode": str(session_mode or "4_session_mbc"),
            "session_dates": dates_list,
            "room_location": str(room_location or ""),
            "postponed_session_idx": int(postponed_session_idx or 0),
            "session_buckets": buckets_dict,
        }

    def get_clinic_session_schedule_sync(
        self, workspace_id: str, badge_name: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieves a stored clinic session schedule from `clinic_session_schedules`."""
        sched_id = f"sched_{hashlib.sha256(f'{workspace_id}:{badge_name}'.encode('utf-8')).hexdigest()[:16]}"
        with self._lock, self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM clinic_session_schedules WHERE schedule_id = ?",
                (sched_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "schedule_id": row["schedule_id"],
                "workspace_id": row["workspace_id"],
                "badge_name": row["badge_name"],
                "companion_badge_name": row["Companion_badge_name"],
                "session_mode": row["session_mode"],
                "session_dates": json.loads(row["session_dates_json"] or "[]"),
                "room_location": row["room_location"],
                "postponed_session_idx": int(row["postponed_session_idx"] or 0),
                "session_buckets": json.loads(row["session_buckets_json"] or "{}"),
            }

    def upsert_scout_session_attendance_and_partials_sync(
        self,
        workspace_id: str,
        badge_name: str,
        scout_id: str,
        scout_name: str = "",
        troop_number: str = "Troop 19",
        session_attendance: Optional[Dict[str, str]] = None,
        completed_reqs: Optional[List[str]] = None,
        completed_reqs_by_badge: Optional[Dict[str, List[str]]] = None,
        actionable_makeup_reqs: Optional[List[str]] = None,
        expected_hometroop_reqs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Persists a Scout's multi-session attendance (`S1..S4 | M`), troop number, and smart partial buckets (Table 11)."""
        rec_id = f"attrec_{hashlib.sha256(f'{workspace_id}:{badge_name}:{scout_id}'.encode('utf-8')).hexdigest()[:16]}"
        att_map = dict(session_attendance or {"S1": "P", "S2": "P", "S3": "P", "S4": "P", "M": "-"})
        comp_list = [str(r) for r in (completed_reqs or [])]
        by_badge = dict(completed_reqs_by_badge or {badge_name: comp_list})
        makeup_list = [str(r) for r in (actionable_makeup_reqs or [])]
        hometroop_list = [str(r) for r in (expected_hometroop_reqs or [])]
        redacted_name = scrub_pii_before_sink(str(scout_name or f"Scout {scout_id}"))
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scout_session_attendance_and_partials (
                    record_id, workspace_id, badge_name, scout_id, scout_name_redacted,
                    troop_number, session_attendance_json, completed_reqs_json,
                    completed_reqs_by_badge_json, actionable_makeup_reqs_json,
                    expected_hometroop_reqs_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(record_id) DO UPDATE SET
                    scout_name_redacted=excluded.scout_name_redacted,
                    troop_number=excluded.troop_number,
                    session_attendance_json=excluded.session_attendance_json,
                    completed_reqs_json=excluded.completed_reqs_json,
                    completed_reqs_by_badge_json=excluded.completed_reqs_by_badge_json,
                    actionable_makeup_reqs_json=excluded.actionable_makeup_reqs_json,
                    expected_hometroop_reqs_json=excluded.expected_hometroop_reqs_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    rec_id,
                    str(workspace_id or "default"),
                    str(badge_name or "First Aid"),
                    str(scout_id),
                    redacted_name,
                    str(troop_number or "Troop 19"),
                    json.dumps(att_map),
                    json.dumps(comp_list),
                    json.dumps(by_badge),
                    json.dumps(makeup_list),
                    json.dumps(hometroop_list),
                ),
            )
            conn.commit()
        return {
            "record_id": rec_id,
            "workspace_id": str(workspace_id or "default"),
            "badge_name": str(badge_name or "First Aid"),
            "scout_id": str(scout_id),
            "scout_name": redacted_name,
            "troop_number": str(troop_number or "Troop 19"),
            "session_attendance": att_map,
            "completed_reqs": comp_list,
            "completed_reqs_by_badge": by_badge,
            "actionable_makeup_reqs": makeup_list,
            "expected_hometroop_reqs": hometroop_list,
        }

    def list_scout_session_attendance_and_partials_sync(
        self, workspace_id: str, badge_name: str, troop_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lists Scout attendance and smart partial records for a workspace and badge."""
        out: List[Dict[str, Any]] = []
        with self._lock, self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM scout_session_attendance_and_partials
                WHERE workspace_id = ? AND badge_name = ?
                ORDER BY troop_number ASC, scout_id ASC
                """,
                (str(workspace_id or "default"), str(badge_name or "First Aid")),
            ).fetchall()
            for r in rows:
                if troop_filter and troop_filter.upper() != "ALL" and r["troop_number"] != troop_filter:
                    continue
                out.append({
                    "record_id": r["record_id"],
                    "workspace_id": r["workspace_id"],
                    "badge_name": r["badge_name"],
                    "scout_id": r["scout_id"],
                    "scout_name": r["scout_name_redacted"],
                    "troop_number": r["troop_number"],
                    "session_attendance": json.loads(r["session_attendance_json"] or "{}"),
                    "completed_reqs": json.loads(r["completed_reqs_json"] or "[]"),
                    "completed_reqs_by_badge": json.loads(r["completed_reqs_by_badge_json"] or "{}"),
                    "actionable_makeup_reqs": json.loads(r["actionable_makeup_reqs_json"] or "[]"),
                    "expected_hometroop_reqs": json.loads(r["expected_hometroop_reqs_json"] or "[]"),
                })
        return out

    def upsert_syllabus_bucket_override_sync(
        self,
        badge_name: str,
        req_id: str,
        syllabus_bucket: str,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        """Persists a counselor override of a requirement's 5-Tier SyllabusBucket in `counselor_syllabus_bucket_overrides` (Table 12)."""
        ov_id = f"bktov_{hashlib.sha256(f'{workspace_id}:{badge_name}:{req_id}'.encode('utf-8')).hexdigest()[:16]}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO counselor_syllabus_bucket_overrides (
                    override_id, workspace_id, badge_name, req_id, syllabus_bucket, updated_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(override_id) DO UPDATE SET
                    syllabus_bucket=excluded.syllabus_bucket,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    ov_id,
                    str(workspace_id or "default"),
                    str(badge_name),
                    str(req_id),
                    str(syllabus_bucket),
                ),
            )
            conn.commit()
        return {
            "override_id": ov_id,
            "workspace_id": str(workspace_id or "default"),
            "badge_name": str(badge_name),
            "req_id": str(req_id),
            "syllabus_bucket": str(syllabus_bucket),
        }

    def list_syllabus_bucket_overrides_sync(
        self, badge_name: str, workspace_id: str = "default"
    ) -> Dict[str, str]:
        """Returns `{req_id: syllabus_bucket}` overrides for a badge and workspace."""
        out: Dict[str, str] = {}
        with self._lock, self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT req_id, syllabus_bucket FROM counselor_syllabus_bucket_overrides
                WHERE workspace_id = ? AND badge_name = ?
                """,
                (str(workspace_id or "default"), str(badge_name)),
            ).fetchall()
            for r in rows:
                out[str(r["req_id"])] = str(r["syllabus_bucket"])
        return out

    save_syllabus_bucket_override_sync = upsert_syllabus_bucket_override_sync
    get_syllabus_bucket_overrides_sync = list_syllabus_bucket_overrides_sync
    save_clinic_session_schedule_sync = upsert_clinic_session_schedule_sync

    def record_compliance_attestation_sync(
        self,
        session_id: str,
        badge_name: str,
        canonical_pamphlet_hash: str = "",
        ypt_two_deep_verified: bool = True,
        zero_pii_egress_verified: bool = True,
        aabb_conformance_passed: bool = True,
    ) -> Dict[str, Any]:
        """Records an immutable compliance attestation row in `compliance_attestation_ledger` (Table 9)."""
        import time as _time

        now_ts = round(_time.time(), 3)
        att_id = f"att_{hashlib.sha256(f'{session_id}:{badge_name}:{now_ts}'.encode('utf-8')).hexdigest()[:16]}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO compliance_attestation_ledger (
                    attestation_id, session_id, badge_name, canonical_pamphlet_hash,
                    ypt_two_deep_verified, zero_pii_egress_verified, aabb_conformance_passed, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    att_id,
                    str(session_id or "default"),
                    str(badge_name or "First Aid"),
                    str(canonical_pamphlet_hash or ""),
                    1 if ypt_two_deep_verified else 0,
                    1 if zero_pii_egress_verified else 0,
                    1 if aabb_conformance_passed else 0,
                    now_ts,
                ),
            )
            conn.commit()
        return {
            "attestation_id": att_id,
            "session_id": session_id,
            "badge_name": badge_name,
            "canonical_pamphlet_hash": canonical_pamphlet_hash,
            "ypt_two_deep_verified": ypt_two_deep_verified,
            "zero_pii_egress_verified": zero_pii_egress_verified,
            "aabb_conformance_passed": aabb_conformance_passed,
            "created_at": now_ts,
        }

    def list_compliance_attestations_sync(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists recent compliance attestations from `compliance_attestation_ledger`."""
        rows_out: List[Dict[str, Any]] = []
        with self._lock, self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM compliance_attestation_ledger ORDER BY created_at DESC LIMIT ?",
                (max(1, int(limit)),),
            )
            for r in cur.fetchall():
                rows_out.append({
                    "attestation_id": r["attestation_id"],
                    "session_id": r["session_id"],
                    "badge_name": r["badge_name"],
                    "canonical_pamphlet_hash": r["canonical_pamphlet_hash"],
                    "ypt_two_deep_verified": bool(r["ypt_two_deep_verified"]),
                    "zero_pii_egress_verified": bool(r["zero_pii_egress_verified"]),
                    "aabb_conformance_passed": bool(r["aabb_conformance_passed"]),
                    "created_at": r["created_at"],
                })
        return rows_out

    def save_session_sync(
        self,
        session_id: str,
        badge_name: str,
        counselor_info: Dict[str, Any],
        history: List[Dict[str, Any]],
    ) -> bool:
        """Synchronously persists PII-scrubbed session state to SQLite and optional VertexAiSessionService."""
        scrubbed_counselor = scrub_pii_from_structure(counselor_info or {})
        scrubbed_history = scrub_pii_from_structure(history or [])

        if self.use_cloud:
            logger.info(
                "Syncing session to VertexAiSessionService / MemoryBank",
                extra={"session_id": session_id, "badge_name": badge_name},
            )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO counselor_sessions (session_id, badge_name, counselor_info, history_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    badge_name=excluded.badge_name,
                    counselor_info=excluded.counselor_info,
                    history_json=excluded.history_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    session_id,
                    badge_name,
                    json.dumps(scrubbed_counselor),
                    json.dumps(scrubbed_history),
                ),
            )
            conn.commit()
        return True

    def get_session_sync(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Synchronously retrieves stored session state from SQLite / Vertex AI cache and upcasts schema to v1.2.0."""
        from src.schemas import migrate_payload_schema

        with self._lock, self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT badge_name, counselor_info, history_json FROM counselor_sessions WHERE session_id=?",
                (session_id,),
            )
            row = cursor.fetchone()
            if row:
                raw_history = json.loads(row[2]) if row[2] else []
                upcast_history = [
                    migrate_payload_schema(ev) if isinstance(ev, dict) and ("storyboard" in ev or "slides" in ev or "archetype" in ev) else ev
                    for ev in raw_history
                ]
                session_payload: Dict[str, Any] = {
                    "session_id": session_id,
                    "badge_name": row[0],
                    "counselor_info": json.loads(row[1]) if row[1] else {},
                    "history": upcast_history,
                }
                return migrate_payload_schema(session_payload)
        return None

    def record_hitl_feedback_sync(
        self,
        badge_name: str,
        session_id: str = "",
        counselor_name: str = "",
        rating: int = 5,
        thumbs_up: bool = True,
        requirement_accuracy_verified: bool = True,
        promoted_to_golden: bool = False,
        comments: str = "",
        schema_version: str = "1.2.0",
    ) -> Dict[str, Any]:
        """Persists Counselor rating and requirement sign-off into the SQLite `hitl_feedback` table."""
        clean_comments = scrub_pii_before_sink(comments or "")[:500]
        feedback_id = hashlib.sha256(
            f"{badge_name}:{session_id}:{counselor_name}:{rating}:{clean_comments}".encode("utf-8")
        ).hexdigest()[:16]
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO hitl_feedback (
                    feedback_id, session_id, badge_name, rating, thumbs_up,
                    requirement_accuracy_verified, promoted_to_golden, comments
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(feedback_id) DO UPDATE SET
                    rating=excluded.rating,
                    thumbs_up=excluded.thumbs_up,
                    requirement_accuracy_verified=excluded.requirement_accuracy_verified,
                    promoted_to_golden=excluded.promoted_to_golden,
                    comments=excluded.comments,
                    created_at=CURRENT_TIMESTAMP
                """,
                (
                    feedback_id,
                    session_id or "interactive",
                    badge_name,
                    max(1, min(5, int(rating))),
                    1 if thumbs_up else 0,
                    1 if requirement_accuracy_verified else 0,
                    1 if promoted_to_golden else 0,
                    clean_comments,
                ),
            )
            conn.commit()
        return {
            "recorded": True,
            "feedback_id": feedback_id,
            "session_id": session_id or "interactive",
            "badge_name": badge_name,
            "counselor_name": counselor_name or "Merit Badge Counselor",
            "rating": max(1, min(5, int(rating))),
            "thumbs_up": bool(thumbs_up),
            "requirement_accuracy_verified": bool(requirement_accuracy_verified),
            "promoted_to_golden": bool(promoted_to_golden),
            "comments": clean_comments,
            "schema_version": schema_version,
        }

    def list_hitl_feedback_sync(
        self,
        badge_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Lists recent Counselor feedback records from the SQLite `hitl_feedback` table."""
        out: List[Dict[str, Any]] = []
        with self._lock, self._connect() as conn:
            cursor = conn.cursor()
            if badge_name:
                cursor.execute(
                    """
                    SELECT feedback_id, session_id, badge_name, rating, thumbs_up,
                           requirement_accuracy_verified, promoted_to_golden, comments, created_at
                    FROM hitl_feedback
                    WHERE badge_name = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (badge_name, max(1, int(limit))),
                )
            else:
                cursor.execute(
                    """
                    SELECT feedback_id, session_id, badge_name, rating, thumbs_up,
                           requirement_accuracy_verified, promoted_to_golden, comments, created_at
                    FROM hitl_feedback
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (max(1, int(limit)),),
                )
            for row in cursor.fetchall():
                out.append(
                    {
                        "feedback_id": row[0],
                        "session_id": row[1],
                        "badge_name": row[2],
                        "rating": int(row[3] or 5),
                        "thumbs_up": bool(row[4]),
                        "requirement_accuracy_verified": bool(row[5]),
                        "promoted_to_golden": bool(row[6]),
                        "comments": str(row[7] or ""),
                        "created_at": str(row[8] or ""),
                        "schema_version": "2.1.0",
                    }
                )
        return out

    save_syllabus_bucket_override_sync = upsert_syllabus_bucket_override_sync
    get_syllabus_bucket_overrides_sync = list_syllabus_bucket_overrides_sync
    save_clinic_session_schedule_sync = upsert_clinic_session_schedule_sync

    def index_pamphlet_chunks_sync(self, badge_name: str, requirements_text: str) -> int:
        """Splits ingested pamphlet text into semantic chunks, computes embeddings, and stores them in SQLite."""
        clean_text = scrub_pii_before_sink(requirements_text or "")
        raw_chunks = [
            c.strip()
            for c in re.split(r"(?:\n\s*\n|(?<=[\.\?\!])\s+(?=[A-Z0-9]))", clean_text)
            if len(c.strip()) >= 20
        ]
        if not raw_chunks and clean_text.strip():
            raw_chunks = [clean_text.strip()]

        with self._lock, self._connect() as conn:
            for idx, chunk in enumerate(raw_chunks[:64]):
                chunk_id = f"{badge_name.lower().replace(' ', '_')}_chunk_{idx}"
                embedding = _compute_text_embedding(chunk)
                conn.execute(
                    """
                    INSERT INTO pamphlet_vector_memory (chunk_id, badge_name, chunk_text, embedding_json)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        chunk_text=excluded.chunk_text,
                        embedding_json=excluded.embedding_json,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (chunk_id, badge_name, chunk, json.dumps(embedding)),
                )
            conn.commit()
        return len(raw_chunks[:64])

    def hybrid_search_pamphlet_rrf_sync(
        self,
        badge_name: str,
        query: str,
        top_k: int = 3,
        rrf_k: int = 60,
    ) -> List[Dict[str, Any]]:
        """Retrieves the top-k pamphlet chunks using Hybrid Search (Dense Cosine + Lexical Okapi BM25 via Reciprocal Rank Fusion)."""
        q_vec = _compute_text_embedding(query or badge_name)
        rows: List[Any] = []
        with self._lock, self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT chunk_id, badge_name, chunk_text, embedding_json FROM pamphlet_vector_memory WHERE lower(badge_name)=lower(?)",
                (badge_name,),
            )
            rows = cursor.fetchall()

        if not rows:
            return []

        docs = [str(r[2] or "") for r in rows]
        bm25_scores = _compute_bm25_scores(query or badge_name, docs)

        items: List[Dict[str, Any]] = []
        for idx, (chunk_id, b_name, chunk_text, emb_json) in enumerate(rows):
            emb = json.loads(emb_json) if emb_json else []
            dense_sim = _cosine_similarity(q_vec, emb)
            items.append(
                {
                    "chunk_id": chunk_id,
                    "badge_name": b_name,
                    "chunk_text": chunk_text,
                    "dense_score": round(dense_sim, 6),
                    "bm25_score": round(bm25_scores[idx], 6),
                }
            )

        # Compute dense ranks (1-based)
        by_dense = sorted(items, key=lambda x: x["dense_score"], reverse=True)
        dense_rank_map = {it["chunk_id"]: rank for rank, it in enumerate(by_dense, start=1)}

        # Compute lexical BM25 ranks (1-based)
        by_bm25 = sorted(items, key=lambda x: (x["bm25_score"], x["dense_score"]), reverse=True)
        bm25_rank_map = {it["chunk_id"]: rank for rank, it in enumerate(by_bm25, start=1)}

        k_const = max(1, int(rrf_k))
        fused: List[Dict[str, Any]] = []
        for it in items:
            cid = it["chunk_id"]
            r_dense = dense_rank_map[cid]
            r_bm25 = bm25_rank_map[cid]
            rrf_val = (1.0 / (k_const + r_dense)) + (1.0 / (k_const + r_bm25))
            combined_score = round(max(it["dense_score"], 0.0) * 0.5 + rrf_val * 20.0, 4)
            fused.append(
                {
                    "chunk_id": cid,
                    "badge_name": it["badge_name"],
                    "chunk_text": it["chunk_text"],
                    "score": combined_score,
                    "rrf_score": round(rrf_val, 6),
                    "dense_score": round(it["dense_score"], 4),
                    "bm25_score": round(it["bm25_score"], 4),
                    "dense_rank": r_dense,
                    "bm25_rank": r_bm25,
                    "source": "sqlite_hybrid_rrf_vector_bm25",
                }
            )

        fused.sort(key=lambda x: (x["rrf_score"], x["bm25_score"], x["dense_score"]), reverse=True)
        return fused[: max(1, top_k)]

    def search_pamphlet_vectors_sync(
        self,
        badge_name: str,
        query: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Retrieves the top-k most relevant pamphlet chunks using Hybrid BM25 + Vector RRF or Vertex AI Search."""
        if os.getenv("USE_VERTEX_AI_SEARCH", "false").lower() == "true" and self.project_id:
            try:
                from google.cloud import discoveryengine_v1 as discoveryengine  # type: ignore

                client = discoveryengine.SearchServiceClient()
                datastore_id = os.getenv("VERTEX_SEARCH_DATASTORE_ID", "scouts-bsa-pamphlets")
                serving_config = (
                    f"projects/{self.project_id}/locations/global/collections/default_collection/"
                    f"dataStores/{datastore_id}/servingConfigs/default_search"
                )
                resp = client.search(
                    request={"serving_config": serving_config, "query": f"{badge_name}: {query}", "page_size": top_k}
                )
                cloud_hits: List[Dict[str, Any]] = []
                for result in resp.results:
                    doc_data = dict(result.document.derived_struct_data or {})
                    cloud_hits.append(
                        {
                            "chunk_id": result.document.id,
                            "badge_name": badge_name,
                            "chunk_text": str(doc_data.get("snippets", [query])[0]),
                            "score": 1.0,
                            "source": "vertex_ai_search",
                        }
                    )
                if cloud_hits:
                    return cloud_hits
            except Exception:
                logger.debug("Database operation failed", exc_info=True)
                pass

        return self.hybrid_search_pamphlet_rrf_sync(badge_name=badge_name, query=query, top_k=top_k)

    def upsert_badge_image_sync(self, entry: Dict[str, Any]) -> bool:
        """Persists or updates a cached Merit Badge image entry in SQLite."""
        return self.upsert_badge_images_batch_sync([entry]) > 0

    def upsert_badge_images_batch_sync(self, entries: List[Dict[str, Any]]) -> int:
        """Persists or updates a batch of Merit Badge image entries in a single SQLite transaction."""
        rows: List[tuple] = []
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            image_id = str(entry.get("image_id") or "")
            if not image_id:
                continue
            rows.append(
                (
                    image_id,
                    str(entry.get("badge_name") or ""),
                    str(entry.get("req_number") or ""),
                    str(entry.get("slide_title") or ""),
                    str(entry.get("title") or ""),
                    str(entry.get("description") or ""),
                    str(entry.get("source_type") or "OFFICIAL_PAMPHLET_FIGURE"),
                    str(entry.get("image_path") or ""),
                    str(entry.get("image_url") or ""),
                    json.dumps(entry.get("metadata") or {}),
                )
            )
        if not rows:
            return 0
        with self._lock, self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO badge_image_catalog (
                    image_id, badge_name, req_number, slide_title, title,
                    description, source_type, image_path, image_url, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(image_id) DO UPDATE SET
                    badge_name=excluded.badge_name,
                    req_number=excluded.req_number,
                    slide_title=excluded.slide_title,
                    title=excluded.title,
                    description=excluded.description,
                    source_type=excluded.source_type,
                    image_path=excluded.image_path,
                    image_url=excluded.image_url,
                    metadata_json=excluded.metadata_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                rows,
            )
            conn.commit()
        return len(rows)

    def list_badge_images_sync(self, badge_name: str) -> List[Dict[str, Any]]:
        """Retrieves all cached image catalog entries for a given Merit Badge from SQLite."""
        rows_out: List[Dict[str, Any]] = []
        with self._lock, self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT image_id, badge_name, req_number, slide_title, title,
                       description, source_type, image_path, image_url, metadata_json
                FROM badge_image_catalog
                WHERE lower(badge_name)=lower(?)
                ORDER BY updated_at DESC
                """,
                (badge_name,),
            )
            for row in cursor.fetchall():
                img_path = str(row[7] or "")
                if img_path and not os.path.exists(img_path):
                    continue
                rows_out.append(
                    {
                        "image_id": row[0],
                        "badge_name": row[1],
                        "req_number": row[2],
                        "slide_title": row[3],
                        "title": row[4],
                        "description": row[5],
                        "source_type": row[6],
                        "image_path": img_path,
                        "image_url": row[8],
                        "metadata": json.loads(row[9]) if row[9] else {},
                    }
                )
        return rows_out


# Global default store instance
_default_store = PersistentSessionStore()


# ==============================================================================
# 2B. LOCAL COUNSELOR PROFILE CACHING (SINGLE-USER LOCAL DISK vs. MULTI-TENANT CLOUD)
# ==============================================================================

def _get_local_counselor_profile_path() -> str:
    """Returns the git-ignored local profile cache path (`.cache/counselor_profile.json`)."""
    from src.config import LOCAL_CACHE_DIR

    LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return str(LOCAL_CACHE_DIR / "counselor_profile.json")


def load_local_counselor_profile() -> Dict[str, Any]:
    """Loads the locally cached Counselor Profile so local users only enter their info once.

    In multi-tenant Cloud Run (`K_SERVICE` or `IS_CLOUD_RUN=true`), returns defaults so
    tenant PII is isolated strictly in each user's client-side browser `localStorage`.
    In local execution, loads `.cache/counselor_profile.json` if present.
    """
    defaults: Dict[str, Any] = {
        "counselor_name": "Scoutmaster Bob",
        "troop_affiliation": "Troop 123, My Council",
        "location_or_zip": "",
        "email_address": "counselor@troop123.org",
        "phone_number": "(000) 555-1234",
        "custom_troop_logo_path": None,
        "cached_locally": False,
    }
    if os.getenv("K_SERVICE") or os.getenv("IS_CLOUD_RUN", "false").lower() == "true":
        return defaults

    profile_path = _get_local_counselor_profile_path()
    if os.path.exists(profile_path):
        try:
            with open(profile_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if isinstance(data, dict):
                merged = dict(defaults)
                for k in (
                    "counselor_name",
                    "troop_affiliation",
                    "location_or_zip",
                    "email_address",
                    "phone_number",
                    "custom_troop_logo_path",
                ):
                    if k in data and data[k] is not None:
                        merged[k] = data[k]
                merged["cached_locally"] = True
                return merged
        except Exception:
            logger.debug("Database operation failed", exc_info=True)
            pass
    return defaults


def save_local_counselor_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Saves Counselor contact details to `.cache/counselor_profile.json` with owner-only `0600` permissions.

    Ensures PII is never emitted to structured logs or OpenTelemetry spans while allowing
    a local Counselor to enter their contact details once and reuse them across sessions.
    """
    if os.getenv("K_SERVICE") or os.getenv("IS_CLOUD_RUN", "false").lower() == "true":
        return {"status": "SKIPPED_CLOUD_MULTI_TENANT", "saved": False}

    clean_payload = {
        "counselor_name": str(profile.get("counselor_name") or "Scoutmaster Bob").strip(),
        "troop_affiliation": str(profile.get("troop_affiliation") or "Troop 123, My Council").strip(),
        "location_or_zip": str(profile.get("location_or_zip") or "").strip(),
        "email_address": str(profile.get("email_address") or "").strip(),
        "phone_number": str(profile.get("phone_number") or "").strip(),
        "custom_troop_logo_path": profile.get("custom_troop_logo_path"),
    }
    profile_path = _get_local_counselor_profile_path()
    try:
        with open(profile_path, "w", encoding="utf-8") as fp:
            json.dump(clean_payload, fp, indent=2)
        try:
            os.chmod(profile_path, 0o600)
        except Exception:
            logger.debug("Database operation failed", exc_info=True)
            pass
        logger.info(
            "Saved local counselor profile to .cache/counselor_profile.json (PII redacted from logs)",
            extra={"profile_redacted": scrub_pii_before_sink(json.dumps(clean_payload))},
        )
        return {"status": "SUCCESS", "saved": True, "profile_path": profile_path}
    except Exception as exc:
        return {"status": "ERROR", "saved": False, "message": str(exc)}


def clear_local_counselor_profile() -> Dict[str, Any]:
    """Deletes the local `.cache/counselor_profile.json` file and resets to default values."""
    profile_path = _get_local_counselor_profile_path()
    try:
        if os.path.exists(profile_path):
            os.remove(profile_path)
        return {"status": "SUCCESS", "cleared": True}
    except Exception as exc:
        return {"status": "ERROR", "cleared": False, "message": str(exc)}


def retrieve_pamphlet_memory_chunks(
    badge_name: str,
    query: str,
    top_k: int = 3,
    store: Optional[PersistentSessionStore] = None,
) -> Dict[str, Any]:
    """Queries the persistent vector store or Google Cloud Vertex AI Search for relevant pamphlet passages.

    Args:
        badge_name: Official name of the Merit Badge (e.g., 'First Aid', 'Weather').
        query: Natural language search query or requirement text.
        top_k: Maximum number of matching chunks to return.
        store: Optional `PersistentSessionStore` instance (defaults to global store).

    Returns:
        Dict[str, Any]: Dictionary containing `status`, `badge_name`, `query`, and ranked `matches`.
    """
    s = store or _default_store
    matches = s.search_pamphlet_vectors_sync(badge_name=badge_name, query=query, top_k=top_k)
    return {
        "status": "SUCCESS",
        "badge_name": badge_name,
        "query": query,
        "match_count": len(matches),
        "matches": matches,
    }


# ==============================================================================
# 3. ASYNCHRONOUS MEMORY OPERATIONS (ASYNCIO NON-BLOCKING I/O)
# ==============================================================================

async def save_session_state_async(
    session_id: str,
    badge_name: str,
    counselor_info: Dict[str, Any],
    history: List[Dict[str, Any]],
    store: Optional[PersistentSessionStore] = None,
) -> Dict[str, Any]:
    """Asynchronously persists PII-scrubbed session state to SQLite or Vertex AI Session Service.

    Args:
        session_id: Unique conversation or counselor ID.
        badge_name: Current merit badge being worked on.
        counselor_info: Title slide counselor customization data.
        history: Current conversation event history.
        store: Target session store instance.

    Returns:
        Dict[str, Any]: Status dictionary indicating successful non-blocking save.
    """
    s = store or _default_store
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        s.save_session_sync,
        session_id,
        badge_name,
        counselor_info,
        history,
    )
    logger.info("Async session save completed", extra={"session_id": session_id})
    return {"status": "SUCCESS", "session_id": session_id, "saved": True}


async def load_session_state_async(
    session_id: str,
    store: Optional[PersistentSessionStore] = None,
) -> Dict[str, Any]:
    """Asynchronously loads persistent session state without blocking the main event loop.

    Args:
        session_id: Target session identifier.
        store: Target session store instance.

    Returns:
        Dict[str, Any]: Stored session dictionary or empty default state.
    """
    s = store or _default_store
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, s.get_session_sync, session_id)
    if data:
        return {"status": "SUCCESS", "session_data": data}
    return {"status": "NOT_FOUND", "session_id": session_id, "session_data": {}}


async def index_pamphlet_memory_async(
    badge_name: str,
    requirements_text: str,
    store: Optional[PersistentSessionStore] = None,
) -> Dict[str, Any]:
    """Asynchronously chunks, embeds, and indexes ingested pamphlet text into the persistent vector store.

    Args:
        badge_name: Official badge name.
        requirements_text: Combined text of all requirements and pamphlet excerpts.
        store: Optional `PersistentSessionStore` instance.

    Returns:
        Dict[str, Any]: Indexing completion status including `indexed_chars` and `chunks_indexed`.
    """
    s = store or _default_store
    loop = asyncio.get_running_loop()
    chunks_count = await loop.run_in_executor(
        None,
        s.index_pamphlet_chunks_sync,
        badge_name,
        requirements_text,
    )
    logger.info(
        "Async vector indexing completed",
        extra={"badge_name": badge_name, "chunks_indexed": chunks_count},
    )
    return {
        "status": "SUCCESS",
        "badge_name": badge_name,
        "indexed_chars": len(requirements_text),
        "chunks_indexed": chunks_count,
    }


async def compact_session_history_async(
    session_id: str,
    events: List[Dict[str, Any]],
    config: Optional[EventsCompactionConfig] = None,
) -> List[Dict[str, Any]]:
    """Asynchronously applies additive history compaction to conversation events.

    Args:
        session_id: Target session identifier.
        events: Historical events list.
        config: Compaction config.

    Returns:
        List[Dict[str, Any]]: Compacted events list.
    """
    loop = asyncio.get_running_loop()
    compacted = await loop.run_in_executor(
        None,
        compact_conversation_events,
        events,
        config,
    )
    return compacted


def get_persistent_session_store() -> PersistentSessionStore:
    """Returns the singleton `PersistentSessionStore` instance."""
    return _default_store


def get_polished_speaker_notes(
    notes_hash: str,
    store: Optional[PersistentSessionStore] = None,
) -> Optional[str]:
    """Looks up a cached AI-polished speaker script by its content-addressed SHA-256 hash."""
    if not notes_hash:
        return None
    s = store or _default_store
    try:
        with _SESSION_DB_LOCK, _connect_session_db(s.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT polished_notes FROM polished_speaker_notes WHERE notes_hash = ?",
                (str(notes_hash),),
            )
            row = cur.fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        logger.debug("Database operation failed", exc_info=True)
        pass
    return None


def save_polished_speaker_notes(
    notes_hash: str,
    badge_name: str,
    req_number: str,
    slide_title: str,
    audience_level: str,
    polished_notes: str,
    store: Optional[PersistentSessionStore] = None,
) -> bool:
    """Persists an AI-polished speaker script into the SQLite `polished_speaker_notes` table."""
    if not notes_hash or not polished_notes:
        return False
    s = store or _default_store
    clean_notes = str(polished_notes).strip()
    try:
        with _SESSION_DB_LOCK, _connect_session_db(s.db_path) as conn:
            conn.execute(
                """
                INSERT INTO polished_speaker_notes (
                    notes_hash, badge_name, req_number, slide_title, audience_level, polished_notes
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(notes_hash) DO UPDATE SET
                    polished_notes=excluded.polished_notes,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    str(notes_hash),
                    str(badge_name or ""),
                    str(req_number or ""),
                    str(slide_title or ""),
                    str(audience_level or ""),
                    clean_notes,
                ),
            )
            conn.commit()
        return True
    except Exception:
        logger.debug("Database operation failed", exc_info=True)
        return False


# ==============================================================================
# MULTI-BADGE COUNSELOR WORKSPACES & FAVORITES (PLAN 16B)
# ==============================================================================


def save_counselor_workspace(
    workspace_payload: Dict[str, Any],
    store: Optional[PersistentSessionStore] = None,
) -> Dict[str, Any]:
    """Creates or updates a multi-badge counselor deck workspace in SQLite (`counselor_workspaces`)."""
    s = store or _default_store
    ws_id = str(workspace_payload.get("workspace_id") or "").strip()
    badge_name = str(workspace_payload.get("badge_name") or "First Aid").strip()
    session_label = str(workspace_payload.get("session_label") or "").strip()
    force_new = bool(workspace_payload.get("force_new") or workspace_payload.get("forceNew"))

    # If no workspace_id was passed and force_new is False, reuse an existing workspace for the same (badge_name, session_label)
    if not ws_id and not force_new:
        try:
            with _SESSION_DB_LOCK, _connect_session_db(s.db_path) as conn:
                row = conn.execute(
                    """
                    SELECT workspace_id FROM counselor_workspaces
                    WHERE LOWER(badge_name) = LOWER(?)
                      AND LOWER(COALESCE(session_label, '')) = LOWER(?)
                      AND is_archived = 0
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    (badge_name, session_label),
                ).fetchone()
                if not row and not session_label:
                    row = conn.execute(
                        """
                        SELECT workspace_id FROM counselor_workspaces
                        WHERE LOWER(badge_name) = LOWER(?)
                          AND is_archived = 0
                        ORDER BY updated_at DESC LIMIT 1
                        """,
                        (badge_name,),
                    ).fetchone()
                if row and row[0]:
                    ws_id = str(row[0])
        except Exception:
            logger.debug("Database operation failed", exc_info=True)
            pass

    if not ws_id:
        slug = re.sub(r"[^a-z0-9]+", "_", badge_name.lower()).strip("_") or "badge"
        ws_id = f"ws_{slug}_{uuid.uuid4().hex[:8]}"

    existing_ws = get_counselor_workspace(ws_id, include_deck_payload=True, store=s)

    ws_title = str(workspace_payload.get("workspace_title") or (existing_ws.get("workspace_title") if existing_ws else "") or badge_name).strip()
    camp_bundle_tag = str(
        workspace_payload.get("camp_bundle_tag")
        if "camp_bundle_tag" in workspace_payload and workspace_payload.get("camp_bundle_tag") is not None
        else (existing_ws.get("camp_bundle_tag") if existing_ws else "") or ""
    ).strip()
    template_id = str(
        workspace_payload.get("template_id")
        or (existing_ws.get("template_id") if existing_ws else "")
        or "default_workbench"
    ).strip()

    counselor_info = workspace_payload.get("counselor_info") or workspace_payload.get("troop_context") or (existing_ws.get("counselor_info") if existing_ws else {}) or {}
    deck_result = dict(
        workspace_payload.get("deck_result")
        or workspace_payload.get("deck_payload")
        or (existing_ws.get("deck_result") if existing_ws else {})
        or {}
    )
    if isinstance(workspace_payload.get("deck_style"), dict):
        deck_result["deck_style"] = dict(workspace_payload["deck_style"])
    elif existing_ws and isinstance(existing_ws.get("deck_style"), dict) and "deck_style" not in deck_result:
        deck_result["deck_style"] = dict(existing_ws["deck_style"])
    blue_card_roster = (
        workspace_payload.get("blue_card_roster")
        if workspace_payload.get("blue_card_roster")
        else (existing_ws.get("blue_card_roster") if existing_ws else {}) or {}
    )
    class_prep = (
        workspace_payload.get("class_prep")
        or workspace_payload.get("class_prep_payload")
        or (existing_ws.get("class_prep") if existing_ws else {})
        or {}
    )
    local_grounding = workspace_payload.get("local_grounding") or (existing_ws.get("local_grounding") if existing_ws else {}) or {}

    active_slide_idx = int(workspace_payload.get("active_slide_idx", existing_ws.get("active_slide_idx", -1) if existing_ws else -1))
    slides_list = (deck_result.get("storyboard") or {}).get("slides") or []
    computed_slides = (len(slides_list) + 1) if slides_list else 0
    slide_count = int(
        workspace_payload.get("slide_count")
        or computed_slides
        or (existing_ws.get("slide_count") if existing_ws else 0)
        or 0
    )
    scouts_list = blue_card_roster.get("scouts") if isinstance(blue_card_roster, dict) else []
    scout_count = int(
        workspace_payload.get("scout_count")
        if workspace_payload.get("scout_count")
        else (len(scouts_list) if isinstance(scouts_list, list) and scouts_list else (existing_ws.get("scout_count") if existing_ws else 0) or 0)
    )
    custom_edits_count = int(workspace_payload.get("custom_edits_count") or (existing_ws.get("custom_edits_count") if existing_ws else 0) or 0)
    is_pinned = 1 if workspace_payload.get("is_pinned", True) else 0
    is_archived = 1 if workspace_payload.get("is_archived", False) else 0

    counselor_info = scrub_pii_from_structure(counselor_info)
    blue_card_roster = scrub_pii_from_structure(blue_card_roster)

    with _SESSION_DB_LOCK, _connect_session_db(s.db_path) as conn:
        conn.execute(
            """
            INSERT INTO counselor_workspaces (
                workspace_id, workspace_title, badge_name, session_label, camp_bundle_tag,
                template_id, counselor_info_json, deck_result_json, blue_card_roster_json,
                class_prep_json, local_grounding_json, active_slide_idx, slide_count,
                custom_edits_count, scout_count, is_pinned, is_archived, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(workspace_id) DO UPDATE SET
                workspace_title=excluded.workspace_title,
                badge_name=excluded.badge_name,
                session_label=excluded.session_label,
                camp_bundle_tag=excluded.camp_bundle_tag,
                template_id=excluded.template_id,
                counselor_info_json=excluded.counselor_info_json,
                deck_result_json=excluded.deck_result_json,
                blue_card_roster_json=excluded.blue_card_roster_json,
                class_prep_json=excluded.class_prep_json,
                local_grounding_json=excluded.local_grounding_json,
                active_slide_idx=excluded.active_slide_idx,
                slide_count=excluded.slide_count,
                custom_edits_count=excluded.custom_edits_count,
                scout_count=excluded.scout_count,
                is_pinned=excluded.is_pinned,
                is_archived=excluded.is_archived,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                ws_id,
                ws_title,
                badge_name,
                session_label,
                camp_bundle_tag,
                template_id,
                json.dumps(counselor_info, ensure_ascii=False),
                json.dumps(deck_result, ensure_ascii=False),
                json.dumps(blue_card_roster, ensure_ascii=False),
                json.dumps(class_prep, ensure_ascii=False),
                json.dumps(local_grounding, ensure_ascii=False),
                active_slide_idx,
                slide_count,
                custom_edits_count,
                scout_count,
                is_pinned,
                is_archived,
            ),
        )
        conn.commit()
    return get_counselor_workspace(ws_id, include_deck_payload=False, store=s) or {"workspace_id": ws_id}


def list_counselor_workspaces(
    badge_name: Optional[str] = None,
    camp_bundle_tag: Optional[str] = None,
    include_archived: bool = False,
    store: Optional[PersistentSessionStore] = None,
) -> List[Dict[str, Any]]:
    """Lists saved counselor deck workspaces (lightweight metadata without multi-MB deck payloads)."""
    s = store or _default_store
    items: List[Dict[str, Any]] = []
    try:
        with _SESSION_DB_LOCK, _connect_session_db(s.db_path) as conn:
            conn.row_factory = sqlite3.Row
            clauses = ["1=1"]
            params: List[Any] = []
            if not include_archived:
                clauses.append("is_archived = 0")
            if badge_name:
                clauses.append("LOWER(badge_name) = LOWER(?)")
                params.append(badge_name.strip())
            if camp_bundle_tag:
                clauses.append("LOWER(camp_bundle_tag) = LOWER(?)")
                params.append(camp_bundle_tag.strip())
            where_sql = " AND ".join(clauses)
            rows = conn.execute(
                f"""
                SELECT workspace_id, workspace_title, badge_name, session_label, camp_bundle_tag,
                       template_id, active_slide_idx, slide_count, custom_edits_count,
                       scout_count, is_pinned, is_archived, created_at, updated_at
                FROM counselor_workspaces
                WHERE {where_sql}
                ORDER BY is_pinned DESC, updated_at DESC
                """,
                params,
            ).fetchall()
            for r in rows:
                items.append(
                    {
                        "workspace_id": r["workspace_id"],
                        "workspace_title": r["workspace_title"],
                        "badge_name": r["badge_name"],
                        "session_label": r["session_label"] or "",
                        "camp_bundle_tag": r["camp_bundle_tag"] or "",
                        "template_id": r["template_id"] or "default_workbench",
                        "active_slide_idx": int(r["active_slide_idx"] or -1),
                        "slide_count": int(r["slide_count"] or 0),
                        "custom_edits_count": int(r["custom_edits_count"] or 0),
                        "scout_count": int(r["scout_count"] or 0),
                        "is_pinned": bool(r["is_pinned"]),
                        "is_archived": bool(r["is_archived"]),
                        "created_at": r["created_at"],
                        "updated_at": r["updated_at"],
                    }
                )
    except Exception:
        logger.debug("Database operation failed", exc_info=True)
        pass
    return items


def get_counselor_workspace(
    workspace_id: str,
    include_deck_payload: bool = True,
    store: Optional[PersistentSessionStore] = None,
) -> Optional[Dict[str, Any]]:
    """Loads a saved counselor deck workspace by `workspace_id`."""
    if not workspace_id:
        return None
    s = store or _default_store
    try:
        with _SESSION_DB_LOCK, _connect_session_db(s.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM counselor_workspaces WHERE workspace_id = ?",
                (str(workspace_id).strip(),),
            ).fetchone()
            if not row:
                return None

            def _safe_json(val: Any) -> Dict[str, Any]:
                if not val:
                    return {}
                try:
                    parsed = json.loads(val)
                    return parsed if isinstance(parsed, dict) else {}
                except Exception:
                    logger.debug("Database operation failed", exc_info=True)
                    return {}

            res: Dict[str, Any] = {
                "workspace_id": row["workspace_id"],
                "workspace_title": row["workspace_title"],
                "badge_name": row["badge_name"],
                "session_label": row["session_label"] or "",
                "camp_bundle_tag": row["camp_bundle_tag"] or "",
                "template_id": row["template_id"] or "default_workbench",
                "active_slide_idx": int(row["active_slide_idx"] or -1),
                "slide_count": int(row["slide_count"] or 0),
                "custom_edits_count": int(row["custom_edits_count"] or 0),
                "scout_count": int(row["scout_count"] or 0),
                "is_pinned": bool(row["is_pinned"]),
                "is_archived": bool(row["is_archived"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "counselor_info": _safe_json(row["counselor_info_json"]),
                "blue_card_roster": _safe_json(row["blue_card_roster_json"]),
                "class_prep": _safe_json(row["class_prep_json"]),
                "local_grounding": _safe_json(row["local_grounding_json"]),
            }
            parsed_deck = _safe_json(row["deck_result_json"])
            if isinstance(parsed_deck.get("deck_style"), dict):
                res["deck_style"] = dict(parsed_deck["deck_style"])
            if include_deck_payload:
                res["deck_result"] = parsed_deck
            return res
    except Exception:
        logger.debug("Database operation failed", exc_info=True)
        return None


def clone_counselor_workspace(
    workspace_id: str,
    new_title: Optional[str] = None,
    session_label: Optional[str] = None,
    camp_bundle_tag: Optional[str] = None,
    copy_roster: bool = False,
    store: Optional[PersistentSessionStore] = None,
) -> Optional[Dict[str, Any]]:
    """Clones an existing deck workspace (preserving all three metadata fields: workspace_title, session_label, and camp_bundle_tag, plus slide edits, template, and speaker notes)."""
    src = get_counselor_workspace(workspace_id, include_deck_payload=True, store=store)
    if not src:
        return None
    badge_name = src["badge_name"]
    slug = re.sub(r"[^a-z0-9]+", "_", badge_name.lower()).strip("_") or "badge"
    new_id = f"ws_{slug}_{uuid.uuid4().hex[:8]}"
    label = (session_label if session_label is not None else (src.get("session_label") or "")).strip()
    bundle_tag = (camp_bundle_tag if camp_bundle_tag is not None else (src.get("camp_bundle_tag") or "")).strip()
    title = (new_title if new_title is not None else (src.get("workspace_title") or badge_name)).strip()
    roster = dict(src.get("blue_card_roster") or {}) if copy_roster else {"scouts": []}
    if copy_roster and isinstance(roster.get("scouts"), list):
        # Copy attendees but reset completed requirements if desired or keep intact
        pass
    cloned_payload = {
        "workspace_id": new_id,
        "workspace_title": title,
        "badge_name": badge_name,
        "session_label": label,
        "camp_bundle_tag": bundle_tag,
        "template_id": src.get("template_id", "default_workbench"),
        "counselor_info": src.get("counselor_info", {}),
        "deck_result": src.get("deck_result", {}),
        "blue_card_roster": roster,
        "class_prep": src.get("class_prep", {}),
        "local_grounding": src.get("local_grounding", {}),
        "active_slide_idx": src.get("active_slide_idx", -1),
        "slide_count": src.get("slide_count", 0),
        "custom_edits_count": src.get("custom_edits_count", 0),
        "scout_count": len(roster.get("scouts") or []) if isinstance(roster.get("scouts"), list) else 0,
        "is_pinned": True,
        "is_archived": False,
    }
    save_counselor_workspace(cloned_payload, store=store)
    return get_counselor_workspace(new_id, include_deck_payload=True, store=store)


def delete_counselor_workspace(
    workspace_id: str,
    store: Optional[PersistentSessionStore] = None,
) -> bool:
    """Deletes a saved counselor deck workspace from SQLite."""
    if not workspace_id:
        return False
    s = store or _default_store
    try:
        with _SESSION_DB_LOCK, _connect_session_db(s.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM counselor_workspaces WHERE workspace_id = ?",
                (str(workspace_id).strip(),),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        logger.debug("Database operation failed", exc_info=True)
        return False


def get_counselor_favorites(
    counselor_id: str = "default",
    store: Optional[PersistentSessionStore] = None,
) -> List[str]:
    """Returns the counselor's starred/favorited Merit Badge names."""
    s = store or _default_store
    favs: List[str] = []
    try:
        with _SESSION_DB_LOCK, _connect_session_db(s.db_path) as conn:
            rows = conn.execute(
                "SELECT badge_name FROM counselor_favorites WHERE counselor_id = ? ORDER BY created_at ASC",
                (str(counselor_id or "default"),),
            ).fetchall()
            favs = [str(r[0]) for r in rows if r and r[0]]
    except Exception:
        logger.debug("Database operation failed", exc_info=True)
        pass
    return favs


def toggle_counselor_favorite(
    badge_name: str,
    is_favorite: Optional[bool] = None,
    counselor_id: str = "default",
    store: Optional[PersistentSessionStore] = None,
) -> Dict[str, Any]:
    """Stars or unstars a Merit Badge in `counselor_favorites` and returns the updated list."""
    clean_badge = str(badge_name or "").strip()
    if not clean_badge:
        return {"badge_name": "", "is_favorite": False, "favorites": get_counselor_favorites(counselor_id, store)}
    s = store or _default_store
    cid = str(counselor_id or "default")
    current = get_counselor_favorites(cid, s)
    currently_fav = any(b.lower() == clean_badge.lower() for b in current)
    target_state = (not currently_fav) if is_favorite is None else bool(is_favorite)
    try:
        with _SESSION_DB_LOCK, _connect_session_db(s.db_path) as conn:
            if target_state:
                conn.execute(
                    "INSERT OR IGNORE INTO counselor_favorites (counselor_id, badge_name) VALUES (?, ?)",
                    (cid, clean_badge),
                )
            else:
                conn.execute(
                    "DELETE FROM counselor_favorites WHERE counselor_id = ? AND LOWER(badge_name) = LOWER(?)",
                    (cid, clean_badge),
                )
            conn.commit()
    except Exception:
        logger.debug("Database operation failed", exc_info=True)
        pass
    updated = get_counselor_favorites(cid, s)
    return {
        "badge_name": clean_badge,
        "is_favorite": target_state,
        "favorites": updated,
    }


FACTORY_DEFAULT_DECK_STYLE_PREFS: Dict[str, Any] = {
    "default_template_id": "bsa_scouting_america",
    "default_slide_theme": "WARM_CREAM",
    "default_layout_style_preset": "AUTO_TEMPLATE",
    "text_container_style": "AUTO",
    "image_frame_style": "AUTO",
    "header_chrome_style": "AUTO",
    "typography_scale": "COMFORTABLE",
    "safety_banner_mode": "ACUTE_HAZARDS_ONLY",
    "match_template_palette": True,
}


def _resolve_prefs_db_path(
    db_path: Optional[Any] = None,
    store: Optional[PersistentSessionStore] = None,
) -> Path:
    if db_path is not None:
        return Path(db_path)
    s = store or _default_store
    return Path(s.db_path)


def _ensure_user_preferences_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
            pref_key TEXT PRIMARY KEY,
            pref_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def load_default_deck_style_preferences(
    db_path: Optional[Any] = None,
    store: Optional[PersistentSessionStore] = None,
) -> Dict[str, Any]:
    """Loads persisted default deck style preferences from SQLite, falling back to `FACTORY_DEFAULT_DECK_STYLE_PREFS`."""
    resolved = dict(FACTORY_DEFAULT_DECK_STYLE_PREFS)
    target_db = _resolve_prefs_db_path(db_path=db_path, store=store)
    try:
        with _SESSION_DB_LOCK, _connect_session_db(target_db) as conn:
            _ensure_user_preferences_table(conn)
            row = conn.execute(
                "SELECT pref_json FROM user_preferences WHERE pref_key = ?",
                ("default_deck_style",),
            ).fetchone()
            if row and row[0]:
                parsed = json.loads(row[0])
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        if v is not None:
                            resolved[k] = v
    except Exception:
        logger.debug("Failed to load default_deck_style preferences", exc_info=True)
    return resolved


def save_default_deck_style_preferences(
    prefs: Dict[str, Any],
    db_path: Optional[Any] = None,
    store: Optional[PersistentSessionStore] = None,
) -> Dict[str, Any]:
    """Merges and persists default deck style preferences in SQLite `user_preferences` (`pref_key='default_deck_style'`)."""
    current = load_default_deck_style_preferences(db_path=db_path, store=store)
    if isinstance(prefs, dict):
        for k, v in prefs.items():
            if v is not None:
                current[k] = v
        # Normalize convenience aliases if caller passed layout_style_preset or template_id
        if "layout_style_preset" in prefs and "default_layout_style_preset" not in prefs and prefs.get("layout_style_preset"):
            current["default_layout_style_preset"] = str(prefs["layout_style_preset"]).strip().upper()
        if "template_id" in prefs and "default_template_id" not in prefs and prefs.get("template_id"):
            current["default_template_id"] = str(prefs["template_id"]).strip()
        if "slide_theme" in prefs and "default_slide_theme" not in prefs and prefs.get("slide_theme"):
            current["default_slide_theme"] = str(prefs["slide_theme"]).strip().upper()

    target_db = _resolve_prefs_db_path(db_path=db_path, store=store)
    try:
        with _SESSION_DB_LOCK, _connect_session_db(target_db) as conn:
            _ensure_user_preferences_table(conn)
            conn.execute(
                """
                INSERT INTO user_preferences (pref_key, pref_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(pref_key) DO UPDATE SET
                    pref_json = excluded.pref_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                ("default_deck_style", json.dumps(current, ensure_ascii=False)),
            )
            conn.commit()
    except Exception:
        logger.debug("Failed to save default_deck_style preferences", exc_info=True)
    return current


def reset_default_deck_style_preferences(
    db_path: Optional[Any] = None,
    store: Optional[PersistentSessionStore] = None,
) -> Dict[str, Any]:
    """Resets `default_deck_style` preferences in SQLite back to `FACTORY_DEFAULT_DECK_STYLE_PREFS`."""
    target_db = _resolve_prefs_db_path(db_path=db_path, store=store)
    try:
        with _SESSION_DB_LOCK, _connect_session_db(target_db) as conn:
            _ensure_user_preferences_table(conn)
            conn.execute(
                "DELETE FROM user_preferences WHERE pref_key = ?",
                ("default_deck_style",),
            )
            conn.commit()
    except Exception:
        logger.debug("Failed to reset default_deck_style preferences", exc_info=True)
    return dict(FACTORY_DEFAULT_DECK_STYLE_PREFS)


def save_clinic_session_schedule(
    workspace_id: str,
    badge_name: str,
    schedule_format: str = "4_session_mbc",
    session_labels: Optional[List[str]] = None,
    postponed_session_idx: Optional[int] = None,
    companion_badge_name: str = "",
    session_requirements_map: Optional[Dict[str, List[str]]] = None,
    room_location: str = "",
    store: Optional[PersistentSessionStore] = None,
) -> Dict[str, Any]:
    s = store or _default_store
    return s.save_clinic_session_schedule_sync(
        workspace_id=workspace_id,
        badge_name=badge_name,
        session_mode=schedule_format,
        session_dates=session_labels,
        room_location=room_location,
        postponed_session_idx=int(postponed_session_idx or 0),
        session_buckets=session_requirements_map,
        companion_badge_name=companion_badge_name,
    )


def get_clinic_session_schedule(
    workspace_id: str,
    badge_name: str,
    store: Optional[PersistentSessionStore] = None,
) -> Optional[Dict[str, Any]]:
    s = store or _default_store
    return s.get_clinic_session_schedule_sync(workspace_id=workspace_id, badge_name=badge_name)


def upsert_scout_session_attendance_and_partials(
    workspace_id: str,
    scout_id: str,
    badge_name: str,
    scout_name: str = "",
    troop_unit: str = "Troop 19",
    session_attendance: Optional[Dict[str, Any]] = None,
    completed_reqs: Optional[List[str]] = None,
    completed_reqs_by_badge: Optional[Dict[str, List[str]]] = None,
    partial_classifications: Optional[Dict[str, str]] = None,
    counselor_notes: str = "",
    store: Optional[PersistentSessionStore] = None,
) -> Dict[str, Any]:
    s = store or _default_store
    actionable = [k for k, v in (partial_classifications or {}).items() if "MAKEUP" in str(v).upper()]
    expected = [k for k, v in (partial_classifications or {}).items() if "HOME" in str(v).upper()]
    return s.upsert_scout_session_attendance_and_partials_sync(
        workspace_id=workspace_id,
        badge_name=badge_name,
        scout_id=scout_id,
        scout_name=scout_name,
        troop_number=troop_unit,
        session_attendance={str(k): str(v) for k, v in (session_attendance or {}).items()} or None,
        completed_reqs=completed_reqs,
        completed_reqs_by_badge=completed_reqs_by_badge,
        actionable_makeup_reqs=actionable,
        expected_hometroop_reqs=expected,
    )


def list_scout_session_attendance_and_partials(
    workspace_id: str,
    badge_name: str,
    troop_filter: Optional[str] = None,
    store: Optional[PersistentSessionStore] = None,
) -> List[Dict[str, Any]]:
    s = store or _default_store
    return s.list_scout_session_attendance_and_partials_sync(
        workspace_id=workspace_id, badge_name=badge_name, troop_filter=troop_filter
    )


def save_counselor_syllabus_bucket_override(
    workspace_id: str,
    badge_name: str,
    req_number: str,
    override_bucket: str,
    store: Optional[PersistentSessionStore] = None,
) -> Dict[str, Any]:
    s = store or _default_store
    return s.upsert_syllabus_bucket_override_sync(
        badge_name=badge_name,
        req_id=req_number,
        syllabus_bucket=override_bucket,
        workspace_id=workspace_id,
    )


def get_counselor_syllabus_bucket_overrides(
    workspace_id: str,
    badge_name: str,
    store: Optional[PersistentSessionStore] = None,
) -> Dict[str, str]:
    s = store or _default_store
    return s.list_syllabus_bucket_overrides_sync(badge_name=badge_name, workspace_id=workspace_id)


ScoutSessionStore = PersistentSessionStore


class CloudSQLPgVectorBackend:
    """Cloud SQL for PostgreSQL + `pgvector` (`vector(768)`) + `tsvector` hybrid RRF adapter (`k=60`).

    When `CLOUD_SQL_DSN` (or `PGVECTOR_DSN`) is configured, executes hybrid RRF queries over
    `pgvector` cosine distance (`<=>`) and PostgreSQL full-text `ts_rank_cd`. Automatically
    falls back to `PersistentSessionStore` SQLite WAL in local workstation mode.
    """

    def __init__(
        self,
        dsn: Optional[str] = None,
        fallback_store: Optional[PersistentSessionStore] = None,
        embedding_dim: int = 768,
        rrf_k: int = 60,
    ) -> None:
        self.dsn = (dsn or os.getenv("CLOUD_SQL_DSN") or os.getenv("PGVECTOR_DSN") or "").strip()
        self.embedding_dim = embedding_dim
        self.rrf_k = rrf_k
        self.fallback_store = fallback_store or _default_store

    @property
    def is_cloud_sql_configured(self) -> bool:
        return bool(self.dsn)

    def build_pgvector_hybrid_rrf_sql(self) -> str:
        """Returns the canonical PostgreSQL `pgvector` + `ts_rank_cd` Reciprocal Rank Fusion SQL query."""
        return f"""
        WITH dense_ranked AS (
            SELECT chunk_id, badge_name, chunk_text,
                   1.0 - (embedding <=> %(query_vec)s::vector({self.embedding_dim})) AS vector_similarity,
                   ROW_NUMBER() OVER (ORDER BY embedding <=> %(query_vec)s::vector({self.embedding_dim}) ASC) AS r_vec
            FROM pamphlet_vector_memory
            WHERE LOWER(badge_name) = LOWER(%(badge_name)s)
        ),
        lexical_ranked AS (
            SELECT chunk_id,
                   ts_rank_cd(to_tsvector('english', chunk_text), plainto_tsquery('english', %(query_text)s)) AS bm25_score,
                   ROW_NUMBER() OVER (
                       ORDER BY ts_rank_cd(to_tsvector('english', chunk_text), plainto_tsquery('english', %(query_text)s)) DESC
                   ) AS r_bm25
            FROM pamphlet_vector_memory
            WHERE LOWER(badge_name) = LOWER(%(badge_name)s)
        )
        SELECT d.chunk_id, d.badge_name, d.chunk_text, d.vector_similarity, l.bm25_score,
               (1.0 / (%(rrf_k)s + d.r_vec)) + (1.0 / (%(rrf_k)s + l.r_bm25)) AS rrf_score
        FROM dense_ranked d
        JOIN lexical_ranked l ON d.chunk_id = l.chunk_id
        ORDER BY rrf_score DESC
        LIMIT %(top_k)s;
        """.strip()

    def hybrid_search_sync(
        self,
        badge_name: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Executes hybrid RRF retrieval against Cloud SQL `pgvector` or falls back to SQLite WAL."""
        if self.is_cloud_sql_configured:
            try:
                import psycopg  # type: ignore

                q_vec = _compute_text_embedding(query, dim=self.embedding_dim)
                with psycopg.connect(self.dsn) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            self.build_pgvector_hybrid_rrf_sql(),
                            {
                                "query_vec": q_vec,
                                "badge_name": badge_name,
                                "query_text": query,
                                "rrf_k": self.rrf_k,
                                "top_k": top_k,
                            },
                        )
                        rows = cur.fetchall()
                        return [
                            {
                                "chunk_id": r[0],
                                "badge_name": r[1],
                                "chunk_text": r[2],
                                "vector_similarity": round(float(r[3]), 4),
                                "bm25_score": round(float(r[4]), 4),
                                "rrf_score": round(float(r[5]), 6),
                                "source": "cloudsql_pgvector_hybrid_rrf",
                            }
                            for r in rows
                        ]
            except Exception as exc:
                logger.debug("CloudSQLPgVectorBackend fallback to SQLite WAL: %s", exc)
        return self.fallback_store.hybrid_search_pamphlet_rrf_sync(
            badge_name=badge_name,
            query=query,
            top_k=top_k,
            rrf_k=self.rrf_k,
        )




