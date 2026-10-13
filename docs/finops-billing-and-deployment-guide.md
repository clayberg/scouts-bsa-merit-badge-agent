# FinOps, Token Billing & Deployment Cost Guide (`v2.6`)

This guide details the token economics, pre-cached visual pipeline savings, explicit human-in-the-loop (HITL) cost gates, and Google Cloud Run deployment costs for the **Scouts BSA Merit Badge Counselor Workbench**.

---

## 1. Strategic Model Routing & Per-Deck Token Economics

The workbench uses **Strategic Model Routing** (`src/config.py`, `src/agents/coordinator.py`) to route high-volume extraction, formatting, and layout tasks to **`gemini-2.5-flash`** while reserving **`gemini-2.5-pro`** for pedagogical curriculum planning and final quality review.

### Published Google Cloud Vertex AI Pricing Baseline
- **`gemini-2.5-flash`**: `$0.15` / 1M input tokens, `$0.60` / 1M output tokens (`$0.0375` / 1M cached context tokens).
- **`gemini-2.5-pro`**: `$1.25` / 1M input tokens, `$10.00` / 1M output tokens (`$0.3125` / 1M cached context tokens).
- **Pre-Cached Visual Assets (`Option 2` Full Visual Pipeline)**: **`$0.00` USD at runtime** across all `144` official Merit Badges (`2,292` pre-generated, compressed 8-bit Nano Banana hero and topic PNGs in `assets/ai_illustrations/` + `4,316` de-boxed official pamphlet figures in `assets/pamphlet_images/`).
- **On-Demand Custom Nano Banana AI Image Generation (`Tab 3` in Image Studio)**: **`$0.08` USD per custom image**, gated by an explicit user consent dialog (`CONSENT_REQUIRED`).

### Per-Deck Cost Breakdown by Visual Polish Tier

| Polish Tier | Canvas Theme | LLM Token Cost (`Flash` + `Pro`) | Pre-Cached Visual Cost (`2,292` PNGs) | Total Runtime Cost per Deck |
| :--- | :--- | :--- | :--- | :--- |
| **`STANDARD` (Crisp White)** | `#FFFFFF` | `~$0.042` USD | `$0.00` USD (Pamphlet Figures) | **`~$0.042` USD** |
| **`BEAUTIFIED` (Warm Cream)** | `#FAF8F5` | `~$0.084` USD | `$0.00` USD (Pre-Cached Hero & Topic PNGs) | **`~$0.084` USD** |
| **`STUDIO` (Dark Slate)** | `#0F172A` | `~$0.140` USD | `$0.00` USD (Pre-Cached Hero & Topic PNGs) | **`~$0.140` USD** |

> **Why Pre-Caching Matters**: Generating 15 to 25 custom AI illustrations live at runtime would cost `$1.20` to `$2.00` per deck and add 90+ seconds of latency. Pre-generating and compressing all **2,292 Nano Banana hero and multi-slide topic illustrations** across all **144 Merit Badges** (`401 MB` total, `<= 1,024px` 8-bit PNG) brings runtime image generation cost down to **`$0.00` USD** while keeping full visual coverage on every requirement.

---

## 2. Hard FinOps Guardrails & Consent Gates (`src/agents/guardrails.py`)

1. **Pre-Flight Workflow Budget Estimator (`estimate_workflow_finops_cost`)**:
   - Before `MeritBadgeCoordinator` executes a workflow, it calculates the projected input/output token cost and verifies that the run stays below the hard **`$1.00` USD per-session ceiling** (`MAX_SESSION_BUDGET_USD = 1.00`).
2. **Explicit `$0.08` User Consent Gate for Live AI Images (`NanoBananaImageAgent`)**:
   - In the 4-Tab Merit Badge Image Studio, Tabs 1 (`Cached Library`), 2 (`Web Image Search`), and 4 (`Local File Upload`) operate at **`$0.00` USD**.
   - Tab 3 (`Nano Banana AI Generator`) calls `POST /api/slide/estimate-image-cost` (`$0.08` USD) and blocks generation (`status: "CONSENT_REQUIRED"`) unless the counselor explicitly approves the cost (`user_consented: true`).
3. **Vertex AI Context Caching (`75%` Input Token Discount)**:
   - Repeated regenerations or single-slide co-design edits on the same Merit Badge reuse the cached canonical pamphlet context (`create_vertex_context_cache_spec` in `src/memory/session_store.py`) and local SHA-256 requirement JSON cache (`data/merit_badge_requirements/*.json`).

---

## 3. Google Cloud Run & Terraform Infrastructure Costs

The production deployment (`terraform/main.tf`) uses scale-to-zero serverless components so idle troop off-nights cost nearly nothing:

| Google Cloud Resource | Configuration | Estimated Monthly Cost (Troop / Council Usage: ~150 Decks/Mo) |
| :--- | :--- | :--- |
| **Cloud Run (`scouts-merit-badge-workbench`)** | `min_instance_count = 0`, `max_instance_count = 4`, `2 vCPU / 2 GiB RAM` | `~$1.80` / month (covered by Cloud Run free tier in `us-central1`) |
| **Vertex AI Gemini API (`2.5-flash` + `2.5-pro`)** | 150 decks/month (`~78%` Flash, `~22%` Pro) | `~$12.60` / month |
| **On-Demand Nano Banana Custom Images** | ~25 custom counselor-requested images/month @ `$0.08` | `~$2.00` / month |
| **Secret Manager & Artifact Registry** | 2 active secret versions + 1 container image | `~$0.35` / month |
| **Cloud Logging & OpenTelemetry Trace** | PII-scrubbed structured JSON logs (`< 5 GB/mo`) | `$0.00` (within GCP free tier) |
| **Total Estimated Monthly Run Rate** | **Full 144-Badge Workbench for a District/Council** | **`~$16.75` / month** |
