# Conversational Slide Deck, Live Demo & Panel Q&A Script (`v2.6`)

This script provides the word-for-word presenter narrative for the **12-Slide Executive Briefing Deck** (`01 / 12` through `12 / 12`), the **6-Act Live Workbench Demonstration**, and the **Panel Q&A Defense**.

---

## Part 1: 12-Slide Executive Briefing Script (`10-12 Minutes`)

### Slide `01 / 12`: Scouts BSA Merit Badge Counselor Workbench
- **On Screen**: Title banner, architecture summary pills (`Google ADK 8-Agent Hierarchy`, `All 144 Official Merit Badges`, `2,297 Pre-Cached Nano Banana PNGs`, `4,317 De-Boxed Pamphlet Figures`, `53 Automated Pytest Tests`).
- **What to Say**:
  > "Hi everyone, I'm Eric Clayberg. Outside of my engineering work, I serve as a Merit Badge Counselor for Scouts BSA Troop 19 in Middleton, Massachusetts. Today I'm presenting the **Scouts BSA Merit Badge Counselor Workbench**, an 8-agent system built on the **Google Agent Development Kit (`google-adk`)** that covers all **144 official Scouts BSA Merit Badges** (`18` Eagle-Required and `126` Electives). It turns 80-page Merit Badge pamphlets into classroom-ready widescreen slide decks, printable Scout workbooks, session pacing agendas, parent prerequisite letters, and Blue Card sign-off matrices, backed by `2,297` pre-cached illustrations, `4,317` de-boxed pamphlet figures, and `53` automated `pytest` tests."

### Slide `02 / 12`: Problem & Customer Empathy: The 12-Hour Prep Tax
- **On Screen**: Comparison of manual counselor prep (`8-15 hours per badge`) vs. naive single-prompt LLM failure modes (curriculum drift, broken slide geometry, noisy PDF image crops, Youth Protection PII exposure).
- **What to Say**:
  > "Every volunteer counselor faces what we call the 12-hour prep tax. When you agree to teach *First Aid*, *Weather*, or *Citizenship in the Nation*, you get an 80-page PDF pamphlet and a list of nested sub-requirements (`1a` through `15c`). You still have to build a slide deck, write BSA EDGE teaching notes (*Explain, Demonstrate, Guide, Enable*), figure out which requirements can be done in a troop meeting versus a weekend campout, email parents about prerequisites, and track Blue Cards (`#34124`). If you try to hand that to a raw single-prompt chatbot, four things break immediately: it paraphrases or skips sub-requirements, it generates overlapping text boxes that bleed off the slide in Google Slides, it pulls raw PDF images with baked-in black caption bars or duplicate titles, and it risks leaking youth roster PII."

### Slide `03 / 12`: System Architecture: 8-Agent Google ADK Hierarchy
- **On Screen**: Architecture diagram showing `MeritBadgeCoordinator` (`gemini-2.5-pro`) orchestrating 7 specialist sub-agents (`ResearcherAgent`, `CurriculumPlannerAgent`, `BeautifierAgent`, `SlideGeneratorAgent`, `QualityReviewerAgent`, `WebImageSearchAgent`, `NanoBananaImageAgent`), plus `FastMCP`, `A2A 1.0`, and `A2UI v0.9`.
- **What to Say**:
  > "To solve this reliably, we built a hierarchical 8-agent topology in `google-adk`. At the root, `MeritBadgeCoordinator` (`gemini-2.5-pro`) enforces our `$1.00` FinOps session ceiling and orchestrates 7 specialist sub-agents. We apply **Strategic Model Routing**: high-volume extraction, theme application, and `.pptx` rendering (`ResearcherAgent`, `BeautifierAgent`, `SlideGeneratorAgent`, `WebImageSearchAgent`) run on `gemini-2.5-flash`, while complex pedagogical triage (`CurriculumPlannerAgent`) and geometry/citation review (`QualityReviewerAgent`) run on `gemini-2.5-pro`. That split cuts per-deck token cost by **71%** (`~$0.042` to `$0.14` per deck). For interoperability, the workbench exposes a `FastMCP` server with HMAC-signed HITL confirmation tokens, an `A2A 1.0` Agent Card at `/.well-known/agent.json`, and `A2UI v0.9` surface envelopes."

### Slide `04 / 12`: 5-Tier Authoritative Research & Hybrid RRF RAG
- **On Screen**: 5-Tier ingestion pipeline (`144` requirement JSONs + `134` local PDFs), SHA-256 Fidelity Lock (`compute_canonical_pamphlet_hash`), and Hybrid Dense Cosine + Okapi BM25 Reciprocal Rank Fusion (`k = 60`).
- **What to Say**:
  > "In Scouts BSA, counselors are not allowed to add, subtract, or paraphrase official requirements. Our `ResearcherAgent` locks all **144 official Merit Badges** in structured JSON catalogs (`data/merit_badge_requirements/*.json`) and computes a deterministic **SHA-256 hash** (`compute_canonical_pamphlet_hash`) over every requirement ID and text string. For retrieval across the `134` local pamphlet PDFs, pure dense embeddings often miss exact requirement codes like `Req 4b` or `Blue Card #34124`. So `PersistentSessionStore.hybrid_search_pamphlet_rrf_sync` combines 768-dimensional `text-embedding-004` cosine similarity with **Okapi BM25 (`k1 = 1.5, b = 0.75`)** via **Reciprocal Rank Fusion (`k = 60`)**, plus local **City, State or ZIP Code** grounding (`location_or_zip`) that resolves local agencies like `NWS Boston/Norton` for ZIP `01949`."

### Slide `05 / 12`: Two-Stage PPTX Conformance & 1:1 Google Slides Parity
- **On Screen**: Stage 1 `<10ms` AABB geometry simulator (`check_pptx_conformance`), `_concise_card_body` character budgets, de-boxed pamphlet figures (`4,317`), and high-resolution embedded-text diagrams with scene-specific captions.
- **What to Say**:
  > "Slide generation is only useful if the exported `.pptx` imports cleanly into Google Slides without text bleeding outside boxes or mismatched diagrams. First, `pptx_builder.py` and `ui/app.js` share 1:1 widescreen (`13.333" x 7.5"`) geometry, layered DrawingML rounded-card accents, and strict character budgets (`<= 18` words, `<= 125` chars per card body). Second, we stripped the baked-in dark caption boxes from all `4,317` extracted pamphlet figures, upgraded complex scientific visuals like the NOAA Hydrologic Cycle, WSR-88D Doppler Radar, Cold/Warm Front cross-sections, Cloud Classification chart, and top-cropped Earth's 23.5° Axial Tilt diagram to high-resolution embedded-text PNGs, and paired every visual with a concise, scene-specific caption. Third, `QualityReviewerAgent` runs a **Stage 1 deterministic AABB simulator (`<10ms`)** that verifies `0` shape overlaps, `100%` citation coverage, and a `>= 12pt` font floor across all `72` pre-built benchmark decks."

### Slide `06 / 12`: Defense-in-Depth Security, YPT PII & Model Armor
- **On Screen**: Dual-layer PII scrubbing (`src/pii_scrubber.py` regex + Cloud DLP) and Model Armor prompt-injection interception (`src/agents/guardrails.py`).
- **What to Say**:
  > "Because this tool serves youth troops, **Scouting America Youth Protection (YPT)** is a hard architectural boundary. Every user input, custom prompt, SQLite write, and OpenTelemetry span passes through our dual-layer PII scrubber (`src/pii_scrubber.py`), which combines deterministic regex patterns with Google Cloud DLP to redact youth names (`Scout <First> <Last>`), phone numbers, emails, SSNs, and street addresses. In parallel, `sanitize_text_with_model_armor` blocks prompt-injection, jailbreak, and YPT-bypass payloads before they ever reach an LLM."

### Slide `07 / 12`: Production Resilience, Circuit Breakers & Self-Healing
- **On Screen**: 3-state `CircuitBreaker` (`CLOSED` -> `OPEN` -> `HALF_OPEN`), exponential backoff with jitter (`src/resilience.py`), and `MAX_CONFORMANCE_RETRIES = 2` layout self-healing loop (`tests/test_resilience_and_fault_injection.py`).
- **What to Say**:
  > "In production, a volunteer counselor prepping 30 minutes before a troop meeting cannot be blocked by a Vertex AI `HTTP 429` rate limit or `503` spike. `src/resilience.py` wraps model calls in exponential backoff with jitter and a stateful 3-state `CircuitBreaker`. After 3 consecutive failures, the breaker trips `OPEN` and `call_with_model_fallback` routes requests to `gemini-2.5-flash` or deterministic pre-cached JSON synthesis. Similarly, if `QualityReviewerAgent` detects any AABB overlap on a generated slide, it triggers an automatic self-healing compaction pass (`MAX_CONFORMANCE_RETRIES = 2`)."

### Slide `08 / 12`: FinOps Governance & Pre-Cached Visual Pipeline
- **On Screen**: 3 Polish Tiers (`STANDARD` `~$0.04`, `BEAUTIFIED` `~$0.08`, `STUDIO` `~$0.14`), `2,297` pre-cached 8-bit PNGs (`$0.00` runtime image cost), `$1.00` session cap, and `$0.08` explicit consent gate (`CONSENT_REQUIRED`).
- **What to Say**:
  > "Generating 20 custom AI images live at runtime would cost `$1.60` per deck and take over a minute. Instead, we pre-generated and compressed **`2,297` Nano Banana hero and multi-slide topic illustrations** (`<= 1,024px`, 8-bit PNG) across all **144 Merit Badges**. That means generating a full `STANDARD`, `BEAUTIFIED`, or `STUDIO` deck for any of the 144 badges incurs **`$0.00` in runtime image generation fees** and only `$0.04` to `$0.14` in LLM tokens. When a counselor opens Tab 3 of the Image Studio to generate a brand-new custom AI image, `NanoBananaImageAgent` returns `CONSENT_REQUIRED` and pauses until the user explicitly approves the `$0.08` USD FinOps estimate."

### Slide `09 / 12`: Evaluation Engineering & Continuous Learning Flywheel
- **On Screen**: `53` automated `pytest` tests across 5 suites, 12-badge Golden Evaluation Gate (`scripts/eval_gate.py`), `72` audited sample decks, and `/api/v1/feedback` Golden Dataset promotion flywheel.
- **What to Say**:
  > "Our verification suite runs **53 non-hollow `pytest` tests** across 5 modules, plus a 12-badge Golden Evaluation Gate (`scripts/eval_gate.py`) and `72` pre-built benchmark decks audited for `100%` sub-requirement coverage and `0` AABB overlaps. To close the loop in production, the workbench includes a **Counselor Sign-Off & Continuous Learning Flywheel** (`POST /api/v1/feedback`): when a counselor rates a generated deck 4 or 5 stars and checks `requirement_accuracy_verified`, the session is persisted to SQLite and automatically promoted into `tests/data/golden_extensions.json` for CI regression testing."

### Slide `10 / 12`: Counselor UX: Co-Design Studio & Field Toolkit
- **On Screen**: Real UI screenshots (`workbench-overview-layout.png`, `codesign-and-image-studio.png`, `counselor-field-toolkit.png`, `construction-animations-triptych.png`).
- **What to Say**:
  > "Here is the Material 3 Expressive Counselor Workbench in action. We designed a collapsible 3-column layout so the 16:9 slide stage stays front and center. While a deck builds, counselors can watch one of three whimsical Scout slide-construction animations that dynamically hoist the selected Merit Badge emblem onto the slide. Once built, counselors can edit slide text inline, swap layouts or color palettes, open the 4-Tab Image Studio, or use the 5-Tab Under-Stage Toolkit Drawer to switch session pacing agendas (*3 Troop Meetings* vs. *Summer Camp Week*), email the Prerequisite Parent Letter via Gmail, scale the Quartermaster Gear Checklist by patrol size, and export a Scoutbook-compatible Blue Card CSV."

### Slide `11 / 12`: Live End-to-End Workbench Walkthrough
- **On Screen**: Live demo roadmap across the 4 browser/CLI acts.
- **What to Say**:
  > "Let's switch over to the live workbench on port `8080` and walk through these capabilities hands-on."

### Slide `12 / 12`: Summary & Engineering Scorecard
- **On Screen**: Final scorecard (`144` Official Merit Badges, `2,297` Pre-Cached Nano Banana PNGs, `4,317` De-Boxed Pamphlet Figures, `72` Audited Sample Decks, `0` AABB Overlaps, `0` PII Leaks, `53` Automated `pytest` Tests).
- **What to Say**:
  > "To wrap up: the **Scouts BSA Merit Badge Counselor Workbench** pairs a domain-grounded 8-agent Google ADK architecture with all `144` official Merit Badges, `2,297` pre-cached illustrations at `$0.00` runtime image cost, `<10ms` deterministic PPTX geometry verification, and strict Youth Protection PII and FinOps guardrails. I'd be happy to take your questions or dive into any module in the codebase."

---

## Part 2: High-Probability Panel Q&A Defense

### Q1: Why use hybrid BM25 + Vector RRF instead of pure vector embeddings or stuffing the entire PDF into Gemini's context window?
- **Answer**:
  1. **Precision on Alphanumeric Codes**: Scouting requirements rely on exact alphanumeric identifiers (`Req 2b`, `Req 9a`, `Form 34124`, `165°F`). Dense embeddings alone frequently blur adjacent sub-requirements (`2a` vs. `2b`), whereas **Okapi BM25 (`k1 = 1.5, b = 0.75`)** fused with `text-embedding-004` via **Reciprocal Rank Fusion (`k = 60`)** (`src/memory/session_store.py`) guarantees exact requirement IDs land at Rank 1.
  2. **Latency & Token Economics**: Passing an entire 80-page pamphlet across 7 sub-agents on every step inflates input token costs and latency. Combining pre-indexed SHA-256 requirement JSONs (`data/merit_badge_requirements/*.json`), targeted RRF retrieval, and Vertex AI Context Caching (`75%` discount) keeps per-deck token costs between `$0.042` and `$0.14`.

### Q2: How do you guarantee that exported `.pptx` slides don't have overlapping boxes or unreadable text when imported into Google Slides?
- **Answer**:
  We enforce three deterministic layers before any deck reaches the user:
  1. **Character-Budget Compaction (`_concise_card_body` in `src/tools/pptx_builder.py`)**: Caps card bodies at `<= 18` words and `<= 125` characters with zero ellipsis truncation (`...`), accounting for font-metric differences between PowerPoint and Google Slides.
  2. **Pre-Cleaned Visual Assets**: All `4,317` extracted pamphlet figures have their dark caption boxes stripped (`_strip_pamphlet_caption_box`), and key scientific diagrams (such as the Hydrologic Cycle, Cold/Warm Fronts, Cloud Classification, and top-cropped Earth's 23.5° Axial Tilt on Weather Slide 49) are high-resolution PNGs paired with concise, scene-specific captions.
  3. **Stage 1 `<10ms` AABB Geometry Simulator (`check_pptx_conformance` in `src/agents/reviewer.py`)**: Computes pairwise Axis-Aligned Bounding Box intersections across every shape on every slide, verifies `13.333" x 7.5"` widescreen bounds, and enforces a `>= 12pt` font floor, triggering up to `MAX_CONFORMANCE_RETRIES = 2` self-healing passes if any violation occurs.
