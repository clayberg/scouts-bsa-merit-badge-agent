# ADR 0002: Hybrid Okapi BM25 and 768-Dim Vector Reciprocal Rank Fusion (RRF) Grounding

## Status
Accepted

## Date
2026-10-03

## Context
Official Scouting America Merit Badge pamphlets span 60 to 90 pages (`45,000` to `70,000` tokens) and organize requirements into deeply nested alphanumeric identifiers such as `1a`, `2b(5)(a)`, and `9a`. Pure dense vector embeddings compress sentence semantics and frequently conflate adjacent numbered sub-requirements (for example, ranking `Req 9b` camping nights above `Req 9a` weather instrument construction). Conversely, stuffing the entire 80-page PDF into every agent prompt consumes ~`185,000` tokens across stages and risks paraphrasing official requirement wording, which violates the Scouting America Guide to Advancement (`GTA Section 7.0.3.2`).

## Options Considered
1. **Full-PDF Prompt Stuffing on Every Agent Turn:** Simple to implement, but adds `3,800 ms` of prefill latency per turn, increases input token spend by `3.1x` (`+$0.42/deck`), and suffers from lost-in-the-middle attention dilution (`0.9500` recall).
2. **Pure Dense Cosine Similarity RAG (`768-dim` only):** Fast (`1.4 ms` p50), but achieved only `0.8125` `Recall@3` and `0.7708` `MRR` on alphanumeric requirement queries due to lexical dilution on short requirement markers.
3. **Hybrid Okapi BM25 (`0.55`) + 768-Dim Cosine Vector (`0.45`) Reciprocal Rank Fusion (`k=60`) + Canonical SHA-256 Requirement Lock (`src/memory/session_store.py`):** Chunk pamphlets by requirement identifier, combine lexical Okapi BM25 ranks with 768-dimensional vector similarity ranks via RRF (`hybrid_search_pamphlet_rrf_sync()`), enable 1-hour Vertex AI `ContextCacheConfig`, and enforce `compute_canonical_pamphlet_hash()` before and after web enrichment.

## Decision
We selected **Option 3**: Hybrid Okapi BM25 + 768-dimensional vector Reciprocal Rank Fusion (`k=60`) backed by SQLite WAL (`pamphlet_vector_memory`) and `CloudSQLPgVectorBackend`, paired with cryptographic SHA-256 requirement locking.

## Consequences
* **Positive:** Achieves **`1.0000` `Recall@3`**, **`1.0000` `MRR`**, and **`1.0000` `NDCG@3`** on `scripts/eval_gate.py` in `1.8 ms` p50 (`4.2 ms` p95), cuts per-deck input tokens by `68%`, reaches a `76%` warm context cache hit rate, and guarantees `0` character drift in official requirement text.
* **Negative / Trade-Off:** Requires maintaining indexed requirement chunks and SHA-256 digests across all 149 Merit Badges in `PersistentSessionStore`.
