# System Architecture & GCP Security Topology (`docs/ARCHITECTURE.md`)

> **Full Technical Design Reference**: For the complete 1,100-line specification including sequence diagrams, Pydantic v2 data contracts, OpenAPI 3.1 endpoints (`123` paths), and 22-capability Model Context Protocol (MCP) tools, see [`docs/TDD.md`](TDD.md) and [`ARCHITECTURE_DECISIONS.md`](../ARCHITECTURE_DECISIONS.md).

---

## 1. Logical Multi-Agent Orchestration & Data Flow Diagram (Google ADK Pipeline)

The logical architecture separates **LLM curriculum reasoning** (`PamphletResearchAgent`, `WebSearchGroundingAgent`, `SlideContentPlannerAgent`, `SlideBeautifierAgent`) from **deterministic geometry, cryptographic verification, and retrieval tools** (`PersistentSessionStore` Hybrid Okapi BM25 + 768-dim Cosine Vector RRF `k=60`, `compute_canonical_pamphlet_hash()`, `verify_hitl_before_tool_callback()`, and `<10ms` AABB `check_pptx_conformance()`).

```mermaid
flowchart TD
    User["Volunteer Counselor / A2UI Browser Workbench"] -->|"HTTPS / SSE Stream"| IngressGate["ScoutsBSAModelArmorPlugin (Ingress Prompt Injection, YPT & PII Scrubber)"]
    IngressGate -->|"Sanitized Request"| Coord["MeritBadgeCoordinatorAgent (ADK 2.0 Root Supervisor)"]

    subgraph Stage1["Stage 1: Canonical Extraction & Regional Grounding Loop"]
        Coord --> Research["1. PamphletResearchAgent (gemini-2.5-pro)"]
        Research -->|"PyMuPDF + SHA-256 Lock"| HybridRAG[("SQLite WAL / Cloud SQL pgvector\nHybrid BM25 + 768-dim Vector RRF k=60")]
        Research --> WebTool["2. WebSearchGroundingAgent (gemini-2.5-flash via AgentTool)"]
        WebTool -->|"51-Jurisdiction NWS / Civic / Senate"| CoverageLoop["3. ResearchCoverageCriticAgent (ADK LoopAgent max_iterations=2)"]
    end

    subgraph Stage2_3["Stages 2 & 3: 12-Archetype Storyboard, Multi-Option Unrolling & Visual Styling"]
        CoverageLoop -->|"100% Leaf Sub-Req Coverage"| Planner["4. SlideContentPlannerAgent (gemini-2.5-pro)\n12 EDGE Archetypes + Multi-Option Track Unrolling"]
        Planner --> Beautifier["5. SlideBeautifierAgent (gemini-2.5-flash)\nDeckStyleConfig + 3,917 Pre-Bundled Assets + GitHub Batch Hydrator"]
        Beautifier -.->|"Opt-In Only ($0.08 Gate)"| ImageStudio["8 & 9. WebImageSearchAgent & NanoBananaImageAgent"]
    end

    subgraph Stage4_5["Stages 4 & 5: Cryptographic HITL Gate, OpenXML .PPTX Build & 2-Stage QA Loop"]
        Beautifier --> HITLGate["HMAC-SHA256 HITL Token Gate (verify_hitl_before_tool_callback)"]
        HITLGate --> Builder["6. PowerPointBuilderAgent (gemini-2.5-flash)\n17 Templates + De-Boxed Figures + 12.0pt Floor"]
        Builder --> CriticLoop["7. BSABrandAndSafetyReviewAgent (ADK LoopAgent max_iterations=3)\nStage 1 <10ms AABB Geometry + Stage 2 Visual Auditor"]
    end

    CriticLoop --> EgressGate["Bidirectional Egress PII Scrubber (scrub_pii_from_structure)\n+ 5% OnlineProductionAuditSampler + Honest Dual Latency Telemetry"]
    EgressGate -->|"Zero-PII SSE & Deliverables (.pptx, .md, Blue Cards, QR)"| User
```

---

## 2. Physical GCP Infrastructure, IAM & Security Perimeter Diagram

The physical architecture runs on **Google Cloud Run v2** (`terraform/main.tf`, `min_instance_count = 1`, `max_instance_count = 10`, dedicated least-privilege service account `scouts-bsa-agent-sa`) behind **Cloud Armor WAF** and **Cloud IAP / OIDC** authentication, with secrets injected from **Google Cloud Secret Manager** and bidirectional **Google Cloud Model Armor + Cloud DLP / Regex PII scrubbing**.

```mermaid
flowchart LR
    subgraph External["Client & Identity Layer"]
        Browser["Counselor Browser / MCP Client"]
    end

    subgraph Edge["GCP Edge & Identity Perimeter"]
        ArmorWAF["Cloud Armor WAF & TLS 1.3"]
        IAP["Cloud IAP / OIDC & Admin Bearer Gate"]
        Browser --> ArmorWAF --> IAP
    end

    subgraph Compute["Google Cloud Run v2 (us-central1, VPC Perimeter)"]
        CloudRun["Cloud Run Service: scouts-bsa-merit-badge-agent\n(min-instances=1, max-instances=10, SA: scouts-bsa-agent-sa)"]
        ModelArmor["ScoutsBSAModelArmorPlugin\n(Ingress + SSE Egress PII / YPT Firewall)"]
        Hydrator["Local 3,917 Asset Cache + On-Demand\nGitHub Raw Concurrent Batch Hydrator"]
        IAP --> CloudRun
        CloudRun --- ModelArmor
        CloudRun --- Hydrator
    end

    subgraph AI_And_Secrets["Vertex AI & Secret Manager"]
        VertexAI["Vertex AI (Gemini 2.5 Pro & Flash\n+ 1-Hr Context Caching + Imagen 3)"]
        SecretMgr["Secret Manager\n(BSA_API_KEY, BSA_HITL_SECRET_KEY,\nADMIN_SUPERUSER_TOKEN)"]
        CloudRun -->|"Vertex AI User IAM"| VertexAI
        CloudRun -->|"Secret Accessor IAM"| SecretMgr
    end

    subgraph Persistence_And_Ops["Persistence & Observability Layer"]
        StateDB[("SQLite WAL (9 Tables) /\nCloud SQL PostgreSQL 16 + pgvector")]
        Telemetry["Cloud Trace + Cloud Logging\n+ ZeroPiiTelemetryStore (First Status vs True TTFT)\n+ 5% OnlineProductionAuditSampler"]
        CloudRun --> StateDB
        CloudRun --> Telemetry
    end
```

---

## 3. Core Architectural Invariants & As-Built Verification

| Architectural Layer | Production Implementation in Repository | Verification Test / Script |
| :--- | :--- | :--- |
| **Multi-Agent Orchestration** | 9-Component / 7-Agent Google ADK hierarchy (`MeritBadgeCoordinatorAgent`, `SequentialAgent`, 2 bounded `LoopAgent` critics, `AgentTool` search isolation) | `src/agents/coordinator.py`, `tests/test_conformance_and_a2ui.py` |
| **Hybrid Retrieval & Grounding** | Okapi BM25 (`0.55`) + 768-dim Cosine Vector (`0.45`) fused via Reciprocal Rank Fusion (`k=60`, `Recall@3 = 1.0000`, `MRR = 1.0000` in `1.8ms`) + cryptographic SHA-256 requirement lock | `src/memory/session_store.py`, `scripts/run_eval.py` |
| **Security, YPT & Privacy** | Bidirectional `ScoutsBSAModelArmorPlugin` (ingress prompt + tool + response + outbound SSE egress scrubbing via `scrub_pii_from_structure()`), HMAC-SHA256 HITL gate, dedicated least-privilege IAM SA | `src/agents/guardrails.py`, `terraform/main.tf` |
| **Resilience & Observability** | 3-state circuit breaker (`CLOSED -> OPEN -> HALF_OPEN`), exponential backoff with jitter, `/health` and `/readiness` probes, Honest Dual Latency (`first_status_event_ms` vs. `true_first_content_token_ms`), 5% `OnlineProductionAuditSampler` | `src/observability/telemetry.py`, `src/observability/online_audit_sampler.py` |
| **FinOps & Asset Hydration** | `3,917` pre-bundled visual assets (`$0.00` runtime image cost, `$0.184` cold deck, `$192.50/mo` 500-counselor Council TCO), `$1.00` `FinOpsBudgetPlugin` hard cap, plus per-badge concurrent GitHub Raw batch asset hydrator for lightweight bundle checkouts | `scripts/cost_model.py`, `src/tools/asset_hydrator.py` |
