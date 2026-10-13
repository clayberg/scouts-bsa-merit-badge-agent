# Architecture Decision Records (ADRs)

This directory indexes the core architectural decisions for the **Scouts BSA Merit Badge Counselor Workbench**. The full specification and code cross-references reside in [`ARCHITECTURE_DECISIONS.md`](../ARCHITECTURE_DECISIONS.md) and [`docs/TDD.md`](TDD.md).

## ADR Index

| ADR ID | Decision Title | Status | Summary |
| :--- | :--- | :--- | :--- |
| **ADR-001** | **Google ADK 8-Agent Hierarchy & Strategic Model Routing** | Accepted | Uses `MeritBadgeCoordinator` orchestrating 7 specialist sub-agents (`ResearcherAgent`, `CurriculumPlannerAgent`, `SlideGeneratorAgent`, `BeautifierAgent`, `WebImageSearchAgent`, `NanoBananaImageAgent`, `QualityReviewerAgent`), routing high-volume tasks to `gemini-2.5-flash` and complex reasoning to `gemini-2.5-pro`. |
| **ADR-002** | **Canonical Pamphlet SHA-256 Lock & Hybrid BM25 + Vector RRF Retrieval** | Accepted | Locks all `144` official Merit Badge requirement trees (`data/merit_badge_requirements/*.json`) with SHA-256 hashes and pairs dense cosine embeddings with Okapi BM25 via Reciprocal Rank Fusion (`k = 60`). |
| **ADR-003** | **Two-Stage PPTX Conformance Gate (`<10ms` AABB Simulator + Vision Critique)** | Accepted | Verifies `0` bounding-box overlaps, `13.333" x 7.5"` canvas bounds, and `>= 12pt` font floors in `<10ms` via `python-pptx` before optional multimodal vision review. |
| **ADR-004** | **Pre-Cached Multimodal Visual Asset Pipeline (`2,297` Nano Banana PNGs + `4,317` De-Boxed Figures)** | Accepted | Pre-generates and compresses (`<= 1,024px`, 8-bit PNG) `2,297` Nano Banana hero and multi-slide topic illustrations across all `144` badges plus `4,317` de-boxed pamphlet figures for `$0.00` runtime image cost, while gating live custom AI image generation behind an explicit `$0.08` USD FinOps consent check. |
| **ADR-005** | **Dual-Layer Youth Protection (YPT) PII Scrubbing & Model Armor Guardrails** | Accepted | Enforces deterministic regex + Cloud DLP scrubbing and Model Armor prompt-injection interception on all inputs, outputs, SQLite records, and OpenTelemetry spans. |
| **ADR-006** | **FastMCP Cryptographic HITL Tokens, A2A 1.0 Discovery & A2UI v0.9 Envelopes** | Accepted | Exposes standardized agent interoperability (`/.well-known/agent.json`, `/a2a/tasks/send`) and requires HMAC-signed confirmation tokens before destructive or paid actions. |
