# FinOps Unit Economics, Token Model & Council TCO (`docs/FINOPS_AND_TCO.md`)

> **Executable Cost Model & Full Guide**: Run `.venv/bin/python3 scripts/cost_model.py` to reproduce all tables below programmatically. For full billing and deployment details, see [`docs/finops-billing-and-deployment-guide.md`](finops-billing-and-deployment-guide.md).

---

## 1. Per-Deck Unit Economics (4 Operating Modes)

By pre-bundling **3,917 curated visual assets** (`2,323` Vision-verified BSA Pamphlet figures + `1,306` zero-text Nano Banana illustrations + `144` authentic patch emblems + `144` pamphlet covers) and routing high-throughput tasks to `gemini-2.5-flash` with **1-hour Vertex AI Context Caching (`76%` cache hit rate)**, standard and beautified slide decks incur **`$0.00` runtime image generation spend**:

| Operating Mode | Gemini 2.5 Pro + Flash Input/Output Tokens | Runtime Image Generation Spend | Total Cost Per Deck | Typical Latency |
| :--- | :--- | :--- | :--- | :--- |
| **1. Golden Demo Cache (`First Aid`, `Camping`, `Weather`)** | `0` live tokens (pre-verified SQLite / disk cache) | `$0.000` (pre-bundled assets) | **`$0.000`** | `< 1.5s` |
| **2. Warm Cache Re-Generation (Template / Style Switch)** | `~18,000` cached tokens (`76%` hit rate on `gemini-2.5-flash`) | `$0.000` (pre-bundled assets) | **`$0.006`** | `3 to 6s` |
| **3. Cold Default Build (`WARM_CREAM` / `CRISP_WHITE`, Any of 144 Badges)** | `~112,000` input / `~14,500` output tokens across 7 ADK agents | `$0.000` (`3,917` pre-bundled PNGs + GitHub Raw hydrator) | **`$0.184`** (`$0.38` uncached ceiling) | `45 to 75s` |
| **4. Opt-In AI Image Studio (`DARK_SLATE` / Custom Slide Regeneration)** | Cold default build + `6 to 8` opt-in Nano Banana / Imagen 3 calls | `$0.480 to $0.520` (`$0.08` explicit counselor HITL gate) | **`$0.704`** (`<= $1.00` hard cap via `FinOpsBudgetPlugin`) | `65 to 95s` |

---

## 2. Per-Agent Model Routing & Token Cost Breakdown (Cold Default Deck = `$0.184`)

| ADK Component / Agent | Assigned Model (`config/models.yaml`) | Why This Model Was Selected | Avg Tokens (In / Out) | Cost Contribution |
| :--- | :--- | :--- | :--- | :--- |
| **1. `PamphletResearchAgent`** | `gemini-2.5-pro` | High-precision extraction of multi-level requirement trees (`2a(5)(a)`) and SHA-256 baseline locking | `24K in / 3.2K out` | `$0.052` |
| **2. `WebSearchGroundingAgent`** | `gemini-2.5-flash` (`AgentTool`) | Fast regional NWS weather, state agency, and U.S. Senate synthesis | `16K in / 2.0K out` | `$0.008` |
| **3. `ResearchCoverageCriticAgent`** | `gemini-2.5-flash` (`LoopAgent`) | Deterministic leaf sub-requirement completeness verification | `10K in / 0.8K out` | `$0.004` |
| **4. `SlideContentPlannerAgent`** | `gemini-2.5-pro` | 12-archetype pedagogical storyboarding, multi-option unrolling, and Socratic script synthesis | `34K in / 6.5K out` | `$0.104` |
| **5. `SlideBeautifierAgent`** | `gemini-2.5-flash` | Mapping `DeckStyleConfig` palettes and matching `3,917` pre-bundled visual assets (`$0.00` image spend) | `14K in / 1.2K out` | `$0.006` |
| **6. `PowerPointBuilderAgent`** | `gemini-2.5-flash` | Deterministic `python-pptx` OpenXML compilation and font auto-fitting (`12.0pt` floor) | `8K in / 0.4K out` | `$0.005` |
| **7. `BSABrandAndSafetyReviewAgent`** | `gemini-2.5-flash` (`LoopAgent`) | Stage 1 `<10ms` AABB geometry QA (`$0.00`) + Stage 2 visual layout & safety verification | `6K in / 0.4K out` | `$0.005` |
| **8 & 9. `WebImageSearchAgent` / `NanoBananaImageAgent`** | `gemini-2.5-flash` / `gemini-2.5-flash-image` | On-demand Image Studio only (gated behind explicit `$0.08` counselor confirmation) | `Opt-in only` | `$0.000` default |

---

## 3. Monthly Total Cost of Ownership (TCO): Variable Token Spend + Fixed GCP Platform Costs

Generated via `.venv/bin/python3 scripts/cost_model.py` (`80%` warm/cached builds + `20%` cold builds):

| Deployment Tier | Monthly Volume | Variable Vertex AI Token & Image Spend | Fixed GCP Platform Spend (Cloud Run `min-instances=1`, Storage, Logging) | Total Monthly TCO | Effective Cost Per Deck | Counselor Hours Saved (`10 hrs/deck`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Single Scouting Troop** | `50 decks / mo` | `$2.41 / mo` | `$5.50 / mo` (scale-to-zero / shared local) | **`$7.91 / mo`** | `$0.158 / deck` | `500 volunteer hours / mo` |
| **Tier 2: 500-Counselor Local Council** | `1,500 decks / mo` | **`$87.48 / mo`** | **`$105.02 / mo`** (Cloud Run `min-instances=1` `$68.40` + Cloud SQL / Artifact Registry / Logging `$36.62`) | **`$192.50 / mo`** | **`$0.128 / deck`** | `15,000 volunteer hours / mo` |
| **Tier 3: National Scouting Scale** | `100,000 decks / mo` | `$4,520.00 / mo` | `$880.00 / mo` (autoscaled Cloud Run fleet + Cloud SQL HA + CDN) | **`$5,400.00 / mo`** | **`$0.054 / deck`** | `1,000,000 volunteer hours / mo` |
