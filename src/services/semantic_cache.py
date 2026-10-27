"""Deterministic 64-Dimensional Semantic Response Cache (`src/services/semantic_cache.py`).

Provides normalized token and character-trigram 64-dimensional vector embeddings,
cosine similarity matching (`cosine_similarity >= threshold`, default `0.92`),
TTL and LRU capacity eviction, and FinOps token/cost savings telemetry.
"""

from __future__ import annotations

import hashlib
import math
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SemanticCacheEntry:
    """Single cached response entry with 64-dim unit embedding and metadata."""

    key_id: str
    query: str
    badge_name: str
    model_tier: str
    embedding: List[float]
    response: Any
    created_at: float
    expires_at: float
    cost_saved_usd: float = 0.006
    hit_count: int = 0


class SemanticCache:
    """Thread-safe semantic cache using deterministic 64-dim token/trigram cosine similarity."""

    EMBEDDING_DIM: int = 64

    def __init__(
        self,
        similarity_threshold: float = 0.92,
        ttl_seconds: float = 3600.0,
        max_entries: int = 512,
    ) -> None:
        self.similarity_threshold = float(max(0.50, min(1.0, similarity_threshold)))
        self.ttl_seconds = float(max(1.0, ttl_seconds))
        self.max_entries = int(max(1, max_entries))
        self._lock = threading.Lock()
        self._entries: Dict[str, SemanticCacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._estimated_savings_usd: float = 0.0
        self._extra: Dict[str, Any] = field(default_factory=dict) if False else {}

    @classmethod
    def compute_embedding(cls, text: str) -> List[float]:
        """Computes a normalized 64-dimensional L2 unit embedding from tokens and trigrams."""
        cleaned = re.sub(r"[^a-z0-9\s]+", " ", str(text or "").lower()).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        vec = [0.0] * cls.EMBEDDING_DIM
        if not cleaned:
            vec[0] = 1.0
            return vec

        tokens = cleaned.split(" ")
        features: List[Tuple[str, float]] = []
        for tok in tokens:
            if tok:
                features.append((f"tok:{tok}", 2.0))
                padded = f"^{tok}$"
                for i in range(max(0, len(padded) - 2)):
                    features.append((f"tri:{padded[i : i + 3]}", 1.0))

        for feat, weight in features:
            digest = hashlib.sha256(feat.encode("utf-8")).digest()
            idx = digest[0] % cls.EMBEDDING_DIM
            sign = 1.0 if (digest[1] & 1) == 0 else -1.0
            vec[idx] += sign * weight

        norm = math.sqrt(sum(v * v for v in vec))
        if norm <= 1e-12:
            vec[0] = 1.0
            return vec
        return [round(v / norm, 8) for v in vec]

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Computes the cosine similarity between two normalized embedding vectors."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a <= 1e-12 or norm_b <= 1e-12:
            return 0.0
        return max(-1.0, min(1.0, dot / (norm_a * norm_b)))

    @staticmethod
    def _normalize_scope(badge_name: str, model_tier: str) -> str:
        b_norm = str(badge_name or "").strip().lower()
        m_norm = str(model_tier or "flash").strip().lower()
        return f"{b_norm}::{m_norm}"

    def _evict_expired_unlocked(self, now: float) -> None:
        expired_keys = [k for k, entry in self._entries.items() if entry.expires_at <= now]
        for k in expired_keys:
            self._entries.pop(k, None)

    def get(
        self,
        query: str,
        badge_name: str = "",
        model_tier: str = "flash",
    ) -> Optional[Dict[str, Any]]:
        """Looks up a cached response whose cosine similarity is >= similarity_threshold."""
        now = time.time()
        scope_prefix = self._normalize_scope(badge_name, model_tier)
        query_emb = self.compute_embedding(query)

        with self._lock:
            self._evict_expired_unlocked(now)
            best_entry: Optional[SemanticCacheEntry] = None
            best_sim: float = -1.0

            for entry in self._entries.values():
                if self._normalize_scope(entry.badge_name, entry.model_tier) != scope_prefix:
                    continue
                sim = self.cosine_similarity(query_emb, entry.embedding)
                if sim >= self.similarity_threshold and sim > best_sim:
                    best_sim = sim
                    best_entry = entry

            if best_entry is None:
                self._misses += 1
                return None

            best_entry.hit_count += 1
            self._hits += 1
            self._estimated_savings_usd = round(
                self._estimated_savings_usd + best_entry.cost_saved_usd,
                6,
            )
            return {
                "cache_hit": True,
                "key_id": best_entry.key_id,
                "matched_query": best_entry.query,
                "badge_name": best_entry.badge_name,
                "model_tier": best_entry.model_tier,
                "cosine_similarity": round(best_sim, 4),
                "response": best_entry.response,
                "hit_count": best_entry.hit_count,
                "cost_saved_usd": best_entry.cost_saved_usd,
            }

    def put(
        self,
        query: str,
        response: Any,
        badge_name: str = "",
        model_tier: str = "flash",
        cost_saved_usd: float = 0.006,
    ) -> Dict[str, Any]:
        """Stores a query and response in the semantic cache with TTL and capacity management."""
        now = time.time()
        scope = self._normalize_scope(badge_name, model_tier)
        norm_query = re.sub(r"\s+", " ", str(query or "").strip().lower())
        key_id = hashlib.sha256(f"{scope}::{norm_query}".encode("utf-8")).hexdigest()[:16]
        emb = self.compute_embedding(query)

        entry = SemanticCacheEntry(
            key_id=key_id,
            query=str(query or "").strip(),
            badge_name=str(badge_name or "").strip(),
            model_tier=str(model_tier or "flash").strip(),
            embedding=emb,
            response=response,
            created_at=now,
            expires_at=now + self.ttl_seconds,
            cost_saved_usd=max(0.0, float(cost_saved_usd)),
        )

        with self._lock:
            self._evict_expired_unlocked(now)
            if key_id not in self._entries and len(self._entries) >= self.max_entries:
                oldest_key = min(
                    self._entries.keys(),
                    key=lambda k: self._entries[k].created_at,
                )
                self._entries.pop(oldest_key, None)
            self._entries[key_id] = entry
            total_entries = len(self._entries)

        return {
            "status": "CACHED",
            "key_id": key_id,
            "badge_name": entry.badge_name,
            "model_tier": entry.model_tier,
            "entries": total_entries,
            "ttl_seconds": self.ttl_seconds,
        }

    def clear(self) -> None:
        """Clears all cached entries and resets hit/miss counters."""
        with self._lock:
            self._entries.clear()
            self._hits = 0
            self._misses = 0
            self._estimated_savings_usd = 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Returns semantic cache hit/miss telemetry and estimated FinOps savings."""
        now = time.time()
        with self._lock:
            self._evict_expired_unlocked(now)
            total_lookups = self._hits + self._misses
            hit_rate = round(self._hits / total_lookups, 4) if total_lookups > 0 else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "total_lookups": total_lookups,
                "hit_rate": hit_rate,
                "entries": len(self._entries),
                "max_entries": self.max_entries,
                "ttl_seconds": self.ttl_seconds,
                "similarity_threshold": self.similarity_threshold,
                "embedding_dim": self.EMBEDDING_DIM,
                "estimated_savings_usd": round(self._estimated_savings_usd, 6),
            }


SemanticResponseCache = SemanticCache
GLOBAL_SEMANTIC_CACHE = SemanticCache()
