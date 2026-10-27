# ADR 0008: Deterministic SHA-256 Online A/B Experiment Routing, Dynamic Plugin Registry, and Canary Rollouts

## Status
Accepted

## Date
2026-10-22

## Context
Continuous AI lifecycle management (Rubric `#25`, `#27`, and `#32`) requires three production capabilities:
1. **Deterministic Online A/B Experimentation:** Evaluating prompt and model variants (such as `control`: `gemini-2.5-flash-standard` vs. `treatment`: `gemini-2.5-flash-grounded-cot`) requires sticky per-session bucketing so a counselor never flips variants mid-session, alongside latency and quality outcome tracking.
2. **Zero-Core-Edit Tool Extensibility:** Adding new external field data sources (such as NOAA weather forecasts, USGS topographic elevations, or National Park Service campsite lookups) should not require modifying core `MeritBadgeCoordinatorAgent` code.
3. **Progressive Canary Rollouts:** New container revisions must pass automated lint, unit/chaos tests, DR verification, and the 20-badge golden evaluation gate before receiving production traffic.

## Options Considered
1. **Random Per-Request `random.random()` Splits + Hardcoded Tool Imports + Direct 100% Deployments:** Causes inconsistent mid-session behavior for counselors, requires modifying core orchestrator files to add tools, and exposes 100% of users to unverified container builds.
2. **External Third-Party Feature Flag SaaS:** Adds external network dependencies and recurring seat licensing costs.
3. **Deterministic SHA-256 `ABExperimentRouter` (`src/services/ab_router.py`) + Entry-Point `PluginRegistry` (`src/plugins/registry.py` & `pyproject.toml`) + Dual CI/CD Canary Pipeline (`cloudbuild.yaml` & `.github/workflows/ci.yaml`):**
   * Compute deterministic bucket indices via `int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 100` in `ABExperimentRouter`, routing sessions sticky-by-ID between `control` (`gemini-2.5-flash-standard`) and `treatment` (`gemini-2.5-flash-grounded-cot`) and recording latency/quality outcomes for BigQuery (`v_ab_experiment_scorecard`).
   * Register domain tools via `@register_tool_plugin` and `importlib.metadata.entry_points(group="scouts_bsa.plugins")` with JSON-Schema input validation (`validate_plugin_input()`).
   * Gate deployments via `.github/workflows/ci.yaml` and `cloudbuild.yaml` (`--no-traffic` deploy -> `/readiness` smoke probe -> `10%` canary traffic shift -> `100%` promotion).

## Decision
We selected **Option 3**: Deterministic SHA-256 `ABExperimentRouter`, `@register_tool_plugin` / `entry_points` `PluginRegistry`, and gated Cloud Run canary rollouts.

## Consequences
* **Positive:** Guarantees sticky per-session A/B assignments (`100%` reproducibility), allows third-party Python packages to register tools via `[project.entry-points."scouts_bsa.plugins"]` in `pyproject.toml` without touching core agent code, and prevents regressions from reaching production.
* **Negative / Trade-Off:** Requires JSON-Schema declarations on every registered plugin and explicit traffic-promotion steps in `cloudbuild.yaml`.
