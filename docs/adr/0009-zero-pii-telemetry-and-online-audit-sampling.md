# ADR 0009: Zero-PII Operational Telemetry, Honest Dual Latency Tracking, and 5% Online Audit Sampling

## Status
Accepted

## Date
2026-10-25

## Context
Operating a multi-agent AI workbench for youth organizations requires deep observability into token burn, per-stage latency percentiles (`p50`/`p95`/`p99`), image-swap preferences, and curriculum grounding quality without ever persisting Youth or Counselor Personally Identifiable Information (PII). In addition, many streaming AI applications conflate the time to emit a hardcoded `"Thinking..."` status frame with True Time-To-First-Token (`TTFT`), masking real model prefill latency.

## Options Considered
1. **Log Raw Prompts and Completions to Cloud Logging / SQLite:** Violates Scouting America Youth Protection privacy rules and risks storing personal emails or phone numbers in telemetry tables.
2. **Stop the TTFT Clock on the Initial SSE Status Event:** Artificially reports `<10 ms` TTFT while hiding true model synthesis latency.
3. **`ZeroPiiTelemetryStore` (`src/observability/telemetry_store.py`) + Honest Dual Latency Telemetry (`src/resilience.py`) + 5% `OnlineProductionAuditSampler` (`src/observability/online_audit_sampler.py`) + BigQuery Analytical Views (`src/analytics/views.sql`):**
   * Scrub all telemetry dictionaries via `scrub_pii_dict()` before writing to `scouts_bsa_telemetry.db` or structured Cloud Logging JSON (`logging.googleapis.com/trace`).
   * Track and report two separate timestamps on every run: `first_status_event_ms` (`6.5 ms` p50) and `true_first_content_token_ms` (`185.0 ms` p50), setting `cosmetic_status_timer_conflation = False`.
   * Deterministically sample **5% (`configured_sample_rate = 0.05`)** of production runs in `OnlineProductionAuditSampler` to continuously audit requirement recall, SHA-256 requirement lock integrity, and AABB overlap counts.
   * Expose 4+ canonical BigQuery analytical SQL views in `src/analytics/views.sql` (`v_daily_finops_token_burn`, `v_agent_stage_latency_percentiles`, `v_semantic_cache_efficiency`, `v_ab_experiment_scorecard`).

## Decision
We selected **Option 3**: `ZeroPiiTelemetryStore` with mandatory pre-sink PII scrubbing, Honest Dual Latency telemetry, 5% deterministic online production trace auditing, and BigQuery SQL analytics views (`src/analytics/views.sql`).

## Consequences
* **Positive:** Enables council administrators to monitor FinOps burn, stage latency percentiles, Easy Slide Image Switcher swap leaderboards, and 5% online quality audits with **zero PII exposure**, while providing transparent latency metrics during technical reviews.
* **Negative / Trade-Off:** Adds ~`0.8 ms` of recursive dictionary scrubbing prior to telemetry writes and maintains a separate `scouts_bsa_telemetry.db` SQLite WAL store alongside `scouts_bsa_sessions.db`.
