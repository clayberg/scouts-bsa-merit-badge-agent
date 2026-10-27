# Markdown Architecture Decision Records (MADR Index)

This directory contains the individual numbered Markdown Architecture Decision Records (`0001` through `0009`) for the **Scouts BSA Merit Badge Counselor Workbench**, complementing the consolidated specification in [`docs/ADR.md`](../ADR.md) and [`ARCHITECTURE_DECISIONS.md`](../../ARCHITECTURE_DECISIONS.md).

| ADR | Title | Status | Primary Code Modules |
| :--- | :--- | :--- | :--- |
| [0001](0001-google-adk-multi-agent-orchestration.md) | Google ADK Multi-Agent Orchestration and Tool Boundary Isolation | Accepted | `src/agents/coordinator.py`, `src/agents/researcher.py`, `src/agents/reviewer.py` |
| [0002](0002-hybrid-bm25-vector-rrf-rag-grounding.md) | Hybrid Okapi BM25 and 768-Dim Vector Reciprocal Rank Fusion (RRF) Grounding | Accepted | `src/memory/session_store.py`, `src/tools/scouting_scraper.py` |
| [0003](0003-dual-transport-mcp-and-a2ui-streaming.md) | Dual-Transport Model Context Protocol (MCP) Server and A2UI SSE Streaming | Accepted | `src/mcp_server.py`, `src/server.py`, `ui/app.js` |
| [0004](0004-verifiable-visual-grounding-and-nano-banana.md) | Two-Stage Visual Conformance (`<10ms` AABB Math + Vision QA) and Pre-Bundled Nano Banana Catalog | Accepted | `src/agents/reviewer.py`, `src/agents/image_studio.py`, `src/tools/pptx_builder.py` |
| [0005](0005-multi-layer-model-armor-and-ypt-guardrails.md) | Multi-Layer Model Armor, 3-Layer Context-Aware PII Scrubbing, and BSA Youth Protection Guardrails | Accepted | `src/agents/guardrails.py`, `src/observability/logging_setup.py`, `src/tools/hitl_confirm.py` |
| [0006](0006-finops-semantic-cache-and-model-tiering.md) | FinOps Semantic Caching, Tiered Model Routing, and Hard Budget Governance | Accepted | `src/services/semantic_cache.py`, `src/config.py`, `config/models.yaml` |
| [0007](0007-sqlite-wal-to-cloud-sql-storage-tiering.md) | Dual-Mode Storage Tiering from SQLite WAL to Cloud SQL for PostgreSQL (`pgvector`) | Accepted | `src/memory/session_store.py`, `scripts/verify_dr_restore.py`, `terraform/main.tf` |
| [0008](0008-deterministic-ab-routing-and-canary-rollout.md) | Deterministic SHA-256 Online A/B Experiment Routing, Dynamic Plugin Registry, and Canary Rollouts | Accepted | `src/services/ab_router.py`, `src/plugins/registry.py`, `.github/workflows/ci.yaml`, `cloudbuild.yaml` |
| [0009](0009-zero-pii-telemetry-and-online-audit-sampling.md) | Zero-PII Operational Telemetry, Honest Dual Latency Tracking, and 5% Online Audit Sampling | Accepted | `src/observability/telemetry_store.py`, `src/observability/online_audit_sampler.py`, `src/analytics/views.sql` |
