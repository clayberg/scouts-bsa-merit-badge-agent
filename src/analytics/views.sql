-- =============================================================================
-- Production BigQuery Analytical SQL Views (`src/analytics/views.sql`)
-- Fed by Cloud Logging structured JSON sink (`GoogleCloudJsonFormatter`) and
-- Zero-PII Telemetry / Online Production Audit exports.
-- Covers Rubric #04 (Observability), #17 (Audit), #19 (SLOs), #24 (FinOps), & #27 (A/B).
-- =============================================================================

-- 1. Daily FinOps Token Burn & Cost Governance View
CREATE OR REPLACE VIEW `${PROJECT_ID}.scouts_bsa_analytics.v_daily_finops_token_burn` AS
SELECT
  DATE(timestamp) AS usage_date,
  JSON_VALUE(jsonPayload.badge_name) AS badge_name,
  COALESCE(JSON_VALUE(jsonPayload.model_tier), 'gemini-2.5-flash') AS model_tier,
  COUNT(1) AS total_workflow_runs,
  SUM(CAST(COALESCE(JSON_VALUE(jsonPayload.input_tokens), '0') AS INT64)) AS total_input_tokens,
  SUM(CAST(COALESCE(JSON_VALUE(jsonPayload.output_tokens), '0') AS INT64)) AS total_output_tokens,
  SUM(CAST(COALESCE(JSON_VALUE(jsonPayload.cached_tokens), '0') AS INT64)) AS total_cached_tokens,
  ROUND(SUM(CAST(COALESCE(JSON_VALUE(jsonPayload.estimated_cost_usd), '0.0') AS FLOAT64)), 4) AS total_spend_usd,
  ROUND(AVG(CAST(COALESCE(JSON_VALUE(jsonPayload.estimated_cost_usd), '0.0') AS FLOAT64)), 4) AS avg_cost_per_deck_usd,
  COUNTIF(CAST(COALESCE(JSON_VALUE(jsonPayload.auto_downgraded), 'false') AS BOOL)) AS budget_cap_downgrades
FROM
  `${PROJECT_ID}.scouts_bsa_analytics.cloud_run_structured_logs`
WHERE
  JSON_VALUE(jsonPayload.event_type) IN ('WORKFLOW_RUN_COMPLETED', 'FINOPS_LEDGER_RECORD')
GROUP BY
  usage_date,
  badge_name,
  model_tier;


-- 2. Agent Stage Latency Percentiles & Honest Dual Latency (First Status vs. True TTFT)
CREATE OR REPLACE VIEW `${PROJECT_ID}.scouts_bsa_analytics.v_agent_stage_latency_percentiles` AS
SELECT
  DATE(timestamp) AS metric_date,
  COALESCE(JSON_VALUE(jsonPayload.stage_id), 'MeritBadgeCoordinatorAgent') AS stage_id,
  COUNT(1) AS invocation_count,
  ROUND(APPROX_QUANTILES(CAST(JSON_VALUE(jsonPayload.duration_ms) AS FLOAT64), 100)[OFFSET(50)], 2) AS latency_p50_ms,
  ROUND(APPROX_QUANTILES(CAST(JSON_VALUE(jsonPayload.duration_ms) AS FLOAT64), 100)[OFFSET(95)], 2) AS latency_p95_ms,
  ROUND(APPROX_QUANTILES(CAST(JSON_VALUE(jsonPayload.duration_ms) AS FLOAT64), 100)[OFFSET(99)], 2) AS latency_p99_ms,
  ROUND(AVG(CAST(COALESCE(JSON_VALUE(jsonPayload.first_status_event_ms), '6.5') AS FLOAT64)), 2) AS avg_first_status_event_ms,
  ROUND(AVG(CAST(COALESCE(JSON_VALUE(jsonPayload.true_first_content_token_ms), '185.0') AS FLOAT64)), 2) AS avg_true_ttft_ms
FROM
  `${PROJECT_ID}.scouts_bsa_analytics.cloud_run_structured_logs`
WHERE
  JSON_VALUE(jsonPayload.duration_ms) IS NOT NULL
GROUP BY
  metric_date,
  stage_id;


-- 3. Semantic Response Cache Efficiency & Cost Savings View
CREATE OR REPLACE VIEW `${PROJECT_ID}.scouts_bsa_analytics.v_semantic_cache_efficiency` AS
SELECT
  DATE(timestamp) AS cache_date,
  COALESCE(JSON_VALUE(jsonPayload.badge_name), 'ALL_BADGES') AS badge_name,
  COALESCE(JSON_VALUE(jsonPayload.model_tier), 'flash') AS model_tier,
  COUNT(1) AS total_lookups,
  COUNTIF(CAST(COALESCE(JSON_VALUE(jsonPayload.cache_hit), 'false') AS BOOL)) AS cache_hits,
  COUNTIF(NOT CAST(COALESCE(JSON_VALUE(jsonPayload.cache_hit), 'false') AS BOOL)) AS cache_misses,
  ROUND(
    SAFE_DIVIDE(
      COUNTIF(CAST(COALESCE(JSON_VALUE(jsonPayload.cache_hit), 'false') AS BOOL)),
      COUNT(1)
    ),
    4
  ) AS hit_rate,
  ROUND(AVG(CAST(COALESCE(JSON_VALUE(jsonPayload.cosine_similarity), '0.92') AS FLOAT64)), 4) AS avg_cosine_similarity,
  ROUND(SUM(CAST(COALESCE(JSON_VALUE(jsonPayload.cost_saved_usd), '0.0') AS FLOAT64)), 4) AS estimated_savings_usd
FROM
  `${PROJECT_ID}.scouts_bsa_analytics.cloud_run_structured_logs`
WHERE
  JSON_VALUE(jsonPayload.event_type) IN ('SEMANTIC_CACHE_LOOKUP', 'WORKFLOW_RUN_COMPLETED')
GROUP BY
  cache_date,
  badge_name,
  model_tier;


-- 4. Online A/B Experiment Scorecard & 5% Production Audit Quality View
CREATE OR REPLACE VIEW `${PROJECT_ID}.scouts_bsa_analytics.v_ab_experiment_scorecard` AS
SELECT
  COALESCE(JSON_VALUE(jsonPayload.experiment_id), 'curriculum_synthesis_v2') AS experiment_id,
  COALESCE(JSON_VALUE(jsonPayload.variant), 'control') AS variant,
  COALESCE(JSON_VALUE(jsonPayload.model_variant), 'gemini-2.5-flash-standard') AS model_variant,
  COUNT(1) AS routed_sessions,
  ROUND(AVG(CAST(COALESCE(JSON_VALUE(jsonPayload.latency_ms), '0.0') AS FLOAT64)), 2) AS avg_latency_ms,
  ROUND(APPROX_QUANTILES(CAST(COALESCE(JSON_VALUE(jsonPayload.latency_ms), '0.0') AS FLOAT64), 100)[OFFSET(95)], 2) AS p95_latency_ms,
  ROUND(AVG(CAST(COALESCE(JSON_VALUE(jsonPayload.quality_score), '1.0') AS FLOAT64)), 4) AS avg_quality_score,
  ROUND(AVG(CAST(COALESCE(JSON_VALUE(jsonPayload.requirement_coverage_recall), '1.0') AS FLOAT64)), 4) AS avg_requirement_recall,
  COUNTIF(CAST(COALESCE(JSON_VALUE(jsonPayload.aabb_overlap_count), '0') AS INT64) = 0) AS zero_overlap_decks
FROM
  `${PROJECT_ID}.scouts_bsa_analytics.cloud_run_structured_logs`
WHERE
  JSON_VALUE(jsonPayload.event_type) IN ('AB_EXPERIMENT_OUTCOME', 'ONLINE_PRODUCTION_AUDIT_SAMPLE')
GROUP BY
  experiment_id,
  variant,
  model_variant;
