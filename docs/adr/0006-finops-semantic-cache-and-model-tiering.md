# ADR 0006: FinOps Semantic Caching, Tiered Model Routing, and Hard Budget Governance

## Status
Accepted

## Date
2026-10-18

## Context
Routing every agent turn to `gemini-2.5-pro` and invoking live LLM/image calls for every slide would cost `$1.45` to `$2.60` per deck, making a 500-counselor Council deployment prohibitively expensive. Furthermore, counselors running Merit Badge clinics frequently request semantically identical curriculum synthesis or speaker-note refinements across sections (for example, multiple counselors teaching *First Aid* or *Camping* at the same summer camp).

## Options Considered
1. **All-Pro Model Routing with No Semantic Caching:** High reasoning quality, but costs `>$1.45/deck` and repeats redundant token spend on semantically equivalent requests.
2. **All-Flash Model Routing with Static Templates Only:** Low cost, but loses deep multi-option sub-requirement decomposition on complex Eagle-required badges (*First Aid*, *Lifesaving*, *Environmental Science*).
3. **Config-Driven `gemini-2.5-pro` / `gemini-2.5-flash` Tiering (`config/models.yaml`) + Deterministic 64-Dim `SemanticCache` (`src/services/semantic_cache.py`) + `FinOpsBudgetPlugin($1.00)` (`src/agents/guardrails.py`):**
   * Assign `gemini-2.5-pro` only to `PamphletResearchAgent` (`$0.052`) and `SlideContentPlannerAgent` (`$0.104`), while routing `WebSearchGroundingAgent`, `ResearchCoverageCriticAgent`, `SlideBeautifierAgent`, `PowerPointBuilderAgent`, `BSABrandAndSafetyReviewAgent`, and on-demand speaker-note polishing (`thinking_budget=0`, `$0.000835/slide`) to `gemini-2.5-flash`.
   * Implement `SemanticCache` (`src/services/semantic_cache.py`) with deterministic 64-dimensional token/trigram embedding normalization and cosine similarity matching (`cosine_similarity >= 0.92`, `ttl_seconds = 3600`), plus SQLite `polished_speaker_notes` caching (`$0.00` on cache hits).
   * Enforce a hard `$1.00/deck` ceiling via `FinOpsBudgetPlugin` and explicit consent modals for `$0.08` custom Nano Banana images (`Layer A1`) and `$0.000835/slide` speaker-note polish (`Layer A2`).

## Decision
We selected **Option 3**: Config-driven `Pro`/`Flash` model tiering combined with `SemanticCache` (`cosine_similarity >= 0.92`), Vertex AI `ContextCacheConfig`, and a hard `$1.00/deck` FinOps ceiling.

## Consequences
* **Positive:** Reduces cold-cache 25-slide deck synthesis cost to **`$0.184`** (`$0.00` runtime image spend), reduces warm-cache regeneration cost to **`$0.006`** (`< 2ms` semantic cache lookup), and brings 500-counselor Council monthly TCO (`1,500 decks/mo`) down to **`$192.50/month`** (`$0.128/deck`).
* **Negative / Trade-Off:** Requires maintaining token pricing tables in `config/models.yaml` and TTL eviction (`max_entries`, `ttl_seconds`) in `SemanticCache`.
