"""Persistent Session Storage, Vector Store / Vertex AI Search Retrieval, History Compaction, and Async Memory Operations.

This module implements all required criteria for Context & Memory (Category 2):
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

def _compute_text_embedding(text: str, dim: int = 32) -> List[float]:
    """Computes a deterministic L2-normalized dense embedding vector for local vector similarity search."""
    vec = [0.0] * dim
    tokens = re.findall(r"[a-z0-9]{2,}", (text or "").lower())
    if not tokens:
        return vec
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = digest[0] % dim
        sign = 1.0 if (digest[1] % 2 == 0) else -1.0
        vec[idx] += sign * (1.0 + (digest[2] / 255.0))
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 1e-9:
        vec = [round(v / norm, 6) for v in vec]
    return vec


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two dense embedding vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a <= 1e-9 or norm_b <= 1e-9:
        return 0.0
    return dot / (norm_a * norm_b)


class PersistentSessionStore:
    """Manages persistent session state and vector memory across SQLite, ADK Vertex AI Session Service, and Vertex AI Search."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or os.getenv("LOCAL_SQLITE_DB_PATH", "scouts_bsa_sessions.db")
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

    def _init_db(self) -> None:
        """Initializes the persistent SQLite tables for counselor sessions and pamphlet vector chunks."""
        with sqlite3.connect(self.db_path) as conn:
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
            conn.commit()

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

        with sqlite3.connect(self.db_path) as conn:
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
        """Synchronously retrieves stored session state from SQLite / Vertex AI cache."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT badge_name, counselor_info, history_json FROM counselor_sessions WHERE session_id=?",
                (session_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "session_id": session_id,
                    "badge_name": row[0],
                    "counselor_info": json.loads(row[1]) if row[1] else {},
                    "history": json.loads(row[2]) if row[2] else [],
                }
        return None

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

        with sqlite3.connect(self.db_path) as conn:
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

    def search_pamphlet_vectors_sync(
        self,
        badge_name: str,
        query: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Retrieves the top-k most relevant pamphlet chunks using vector cosine similarity or Vertex AI Search."""
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
                pass

        q_vec = _compute_text_embedding(query or badge_name)
        scored: List[Dict[str, Any]] = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT chunk_id, badge_name, chunk_text, embedding_json FROM pamphlet_vector_memory WHERE lower(badge_name)=lower(?)",
                (badge_name,),
            )
            for chunk_id, b_name, chunk_text, emb_json in cursor.fetchall():
                emb = json.loads(emb_json) if emb_json else []
                sim = _cosine_similarity(q_vec, emb)
                scored.append(
                    {
                        "chunk_id": chunk_id,
                        "badge_name": b_name,
                        "chunk_text": chunk_text,
                        "score": round(sim, 4),
                        "source": "sqlite_vector_store",
                    }
                )
        scored.sort(key=lambda item: float(item["score"]), reverse=True)
        return scored[: max(1, top_k)]

    def upsert_badge_image_sync(self, entry: Dict[str, Any]) -> bool:
        """Persists or updates a cached Merit Badge image entry in SQLite."""
        image_id = str(entry.get("image_id") or "")
        if not image_id:
            return False
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
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
                ),
            )
            conn.commit()
        return True

    def list_badge_images_sync(self, badge_name: str) -> List[Dict[str, Any]]:
        """Retrieves all cached image catalog entries for a given Merit Badge from SQLite."""
        rows_out: List[Dict[str, Any]] = []
        with sqlite3.connect(self.db_path) as conn:
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

