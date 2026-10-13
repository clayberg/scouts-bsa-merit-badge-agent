# ⚜️ Scouts BSA Merit Badge Counselor Workbench

An AI-powered instructional design studio and teaching assistant built for **Scouts BSA Merit Badge Counselors**, summer camp directors, and troop advancement chairs.

Select any of the **144 official Scouts BSA Merit Badges** (`18` Eagle-Required and `126` Electives), enter your counselor contact info and troop location, and generate a ready-to-teach **PowerPoint (`.pptx`) / Google Slides deck**, **Printable Scout Workbook**, **Multi-Format Session Pacing Agenda**, **Prerequisite Parent Letter**, **Quartermaster Gear Checklist**, and **Patrol Blue Card (`#34124`) Sign-Off Matrix** grounded in official Scouting America pamphlets and the **Guide to Safe Scouting**.

![Scouts BSA Merit Badge Counselor Workbench Overview](docs/images/workbench-overview-layout.png)

---

## ✨ Key Capabilities & Features

- **All 144 Official Merit Badges Supported**:
  - Covers all **18 Eagle-Required Merit Badges** (*First Aid*, *Camping*, *Cooking*, *Citizenship in the Community*, *Citizenship in the Nation*, *Citizenship in the World*, *Citizenship in Society*, *Communication*, *Personal Fitness*, *Emergency Preparedness*, *Lifesaving*, *Environmental Science*, *Sustainability*, *Personal Management*, *Swimming*, *Hiking*, *Cycling*, *Family Life*) and **126 Elective Merit Badges** (including 2025/2026 Scouting America additions such as *Artificial Intelligence*, *Cybersecurity*, *Wildland Fire Management*, *Multisport*, *Action Sports*, and *Health Care Professions*).
  - **100% Pre-Cached Visual Pipeline (`$0.00` Runtime Image Cost)**: Ships with **144 structured requirement JSON catalogs** (`data/merit_badge_requirements/*.json`), **134 local official BSA Merit Badge Pamphlet PDFs** (`pdfs/`), **135 transparent RGBA Merit Badge patch emblems** (`assets/badge_emblems/`), **134 pamphlet cover images** (`assets/pamphlet_covers/`), **4,317 extracted and de-boxed pamphlet figures** (`assets/pamphlet_images/`), and **2,297 pre-generated, compressed (`<= 1,024px`, 8-bit PNG) Nano Banana hero and multi-slide topic illustrations** (`assets/ai_illustrations/`).
  - **26 Deep Benchmark Badges & 72 Pre-Built Sample Decks**: Includes pre-verified `.pptx` decks across both *Deep Dive / Camp School* (`45-85+` slides) and *Troop Meeting* (`16-28` slides) modes in `deliverables/benchmark_and_random_samples/`.

- **Material 3 Expressive Counselor Workbench (`1:1` Preview-to-PPTX Parity)**:
  - **16:9 Widescreen Preview Stage & Fullscreen Mode (`F`)**: What you see in the browser matches the exported `.pptx` and Google Slides deck (`13.333" x 7.5"` widescreen canvas, rounded cards with top and left accent bars, transparent upper-right Merit Badge emblem, and zero bounding-box overlaps).
  - **Three Visual Polish Tiers**:
    1. **Standard Lightweight (`STANDARD`, Crisp White `#FFFFFF`)**: Clean printable layout using official BSA pamphlet figures (`~$0.04` LLM tokens, `$0.00` image cost).
    2. **AI Beautified (`BEAUTIFIED`, Warm Cream `#FAF8F5`)**: Rotating 4-palette card accents paired with pre-cached Nano Banana hero and topic illustrations (`~$0.08` LLM tokens, `$0.00` pre-cached image cost).
    3. **AI Studio (`STUDIO`, Dark Slate `#0F172A`)**: High-contrast auditorium and campfire presentation theme with full pre-cached visual coverage (`~$0.14` LLM tokens, `$0.00` pre-cached image cost).
  - **High-Resolution Scientific Diagrams & Scene-Specific Captions**: Key meteorological, medical, and civic slides feature high-resolution embedded-text diagrams (such as the NOAA Hydrologic Cycle, WSR-88D Doppler Radar reflectivity, Cold and Warm Front cross-sections, 3D Warm Front profile, Sea and Land Breezes, Cloud Classification by Altitude Level, and cropped Earth's 23.5° Axial Tilt and Seasons) paired with concise, scene-specific captions.
  - **Whimsical Scout Slide-Construction Animation**: While a deck builds, choose from three animated storyboard themes (*3D Heavy Equipment*, *2D Camp Pioneering*, or *3D Claymation Workshop*) that dynamically mount the selected Merit Badge emblem onto the slide under construction.

![Slide Polish Tiers Comparison](docs/images/slide-polish-tiers-comparison.png)

- **Per-Slide Interactive Co-Design & 4-Tab Merit Badge Image Studio**:
  - Edit any slide's title and bullet points inline (`Quick Slide Text Editor`), switch layouts (`3-Column Modern Cards`, `Numbered Step Cards`, `Split Visual Explainer`, `Full-Bleed Diagram`, `Comparison Table`), or change color palettes (`Navy & Gold`, `Forest & Sage`, `Crimson & Ember`, `Slate & Cyan`).
  - Open the **4-Tab Merit Badge Image Studio** on any slide to swap visuals from the **Quick-Switch Cached Library** (`$0.00`), run a **Web Image Search** (`$0.00`), generate a custom **Nano Banana AI Illustration** (`$0.08` USD gated by an explicit user consent dialog), or upload a **Local Troop Photo** (`$0.00`).

![Per-Slide Co-Design and 4-Tab Image Studio](docs/images/codesign-and-image-studio.png)

- **Complete Counselor Field Toolkit (`5-Tab Under-Stage Drawer`)**:
  - **Counselor Teaching Notes**: Slide-by-slide BSA EDGE method scripts (`[SAY]`, `[DEMONSTRATE]`, `[ASK SCOUTS]`) adapted to the selected Scout audience level (*New Scouts Ages 11-13*, *All Scouts Ages 11-17*, or *Older Scouts / Eagle Prep Ages 14-17*).
  - **Multi-Format Session Pacing Agenda**: Switch instantaneously between *3 Troop Meetings (60-Min)*, *Summer Camp Week (4x50-Min Mon-Thu + Fri Sign-Off)*, *Saturday Merit Badge Clinic (3-Hr Block)*, and *Weekend Campout Practicum*.
  - **Prerequisite Parent/Guardian Letter**: Customized with your counselor contact info and local **City, State or ZIP Code** (`location_or_zip`), with one-click **Copy**, **Draft in Email App**, **Compose in Gmail**, **Print / Save PDF**, and **Download `.md`**.
  - **Master Quartermaster Gear & Materials Checklist**: Aggregated per-requirement equipment list with a live **Patrol Size Multiplier** (`1x`, `2x`, `3x`, `4x`).
  - **Patrol Blue Card (`#34124`) & Scoutbook Plus Sign-Off Matrix**: Interactive roster grid to check off requirements during class and export a **Scoutbook-compatible CSV**.

![Counselor Field Toolkit](docs/images/counselor-field-toolkit.png)

---

## 🚀 Quick Start: Local / Laptop Execution

### Prerequisites
- **Python 3.11+**
- **Git**
- *(Optional)* A **Google Gemini API Key** (`GEMINI_API_KEY`) or **Google Cloud Vertex AI project** (`GOOGLE_CLOUD_PROJECT`) if you want live LLM customization or live `$0.08` Nano Banana custom image generation. All `144` official badges and `2,297` pre-cached illustrations work out of the box in offline/deterministic mode.

### 1. Clone & Launch with `./run_local.sh`
```bash
git clone https://github.com/clayberg/scouts-bsa-merit-badge-agent.git
cd scouts-bsa-merit-badge-agent

# Optional: configure your Gemini / Vertex AI credentials
cp .env.example .env

# Create virtual environment, install dependencies, and start the server on port 8080
./run_local.sh
```

Then open **`http://localhost:8080`** in your browser.

---

## 🧭 How to Use the Counselor Workbench

1. **Choose a Merit Badge**: Browse or filter all **144 official Merit Badges** by category (*Eagle-Required*, *Outdoor & Backcountry*, *Aquatics & Paddle*, *STEM & Digital*, *Civics & Business*, *Arts, Crafts & Trades*, *Sports & Shooting*) in the left setup panel.
2. **Enter Your Counselor & Troop Profile**:
   - Fill in your **Counselor Name**, **Troop & Council**, **Location (City, State or ZIP Code)** (used to ground local agencies such as your local National Weather Service forecast office or civic contacts), **Contact Email**, **Contact Phone**, and optional **Troop Custom Logo**.
   - Your profile is automatically cached in your browser (`localStorage`) and local SQLite store so you only need to enter it once.
3. **Select Deck Depth & Visual Polish Tier**:
   - **Deck Depth**: Choose **Deep Dive / Camp School Deck (45-85+ Slides)** for comprehensive sub-requirement coverage or **Troop Meeting Deck (16-28 Slides)** for a focused overview.
   - **Slide Polish Tier**: Choose **AI Beautified (Warm Cream)**, **AI Studio (Dark Slate)**, or **Standard Lightweight (Crisp White)**.
4. **Generate & Inspect**:
   - Click **Generate Complete Curriculum & Slide Deck**.
   - Use the **Slide Deck Outline** filmstrip, **Requirement Quick-Jump Pills**, or keyboard arrows (`Left` / `Right`) to step through your slides, or press **`F`** for Fullscreen Presentation Mode.
5. **Co-Design, Print & Export**:
   - Customize any slide's text, layout, or visual using the **Per-Slide Co-Design Bar** and **4-Tab Image Studio**.
   - Click **Download `.pptx`** in the top bar (imports directly into Google Slides or Microsoft PowerPoint with 1:1 fidelity) and print or email your **Scout Workbook**, **Session Pacing Agenda**, **Prerequisite Parent Letter**, **Quartermaster Gear List**, and **Blue Card CSV**.

---

## ☁️ Optional Cloud Deployment

To deploy the Counselor Workbench as a serverless container on **Google Cloud Run** with Infrastructure-as-Code (**Terraform**) and **Google Secret Manager**:

```bash
# 1. Provision Cloud Run, Artifact Registry, Secret Manager, and least-privilege IAM
cd terraform
terraform init
terraform apply -var="project_id=YOUR_GCP_PROJECT_ID" -var="region=us-central1"

# 2. Or build and deploy directly via Cloud Build / gcloud
gcloud run deploy scouts-merit-badge-workbench \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

---

## 📚 Documentation Index

- **[Detailed User Guide (`docs/USER_GUIDE.md`)](docs/USER_GUIDE.md)**: Step-by-step walkthrough of every screen, drawer, co-design control, and printable counselor tool.
- **[Technical Design Document (`docs/TDD.md`)](docs/TDD.md)**: Complete multi-agent architecture, data schemas, hybrid RAG math, two-stage conformance gate, and security controls.
- **[Architecture Decision Records (`ARCHITECTURE_DECISIONS.md`)](ARCHITECTURE_DECISIONS.md)**: Key engineering trade-offs (ADK 8-agent routing, SHA-256 curriculum lock, `<10ms` AABB simulator, pre-cached visual pipeline, and YPT PII scrubbing).
- **[API & Interoperability Integration Guide (`docs/API_INTEGRATION_GUIDE.md`)](docs/API_INTEGRATION_GUIDE.md)**: REST `/api/v1/*` endpoints, A2A 1.0 Agent Card discovery, A2UI v0.9 schemas, and FastMCP tool contracts.
- **[FinOps, Token Billing & Deployment Cost Guide (`docs/finops-billing-and-deployment-guide.md`)](docs/finops-billing-and-deployment-guide.md)**: Per-deck token economics, pre-cached `$0.00` visual pipeline vs. `$0.08` on-demand Nano Banana consent gate, and Cloud Run cost projections.
- **[Operational Runbook (`docs/runbook.md`)](docs/runbook.md)**: Health checks, readiness probes, cache management, circuit breaker recovery, and troubleshooting.
- **[Capstone Companion Guide (`docs/FDE_CAPSTONE_COMPANION_GUIDE.md`)](docs/FDE_CAPSTONE_COMPANION_GUIDE.md)**: Executive mapping of the codebase to production AgentOps engineering standards.
- **[Capstone Panel Playbook (`docs/CAPSTONE_PANEL_PLAYBOOK.md`)](docs/CAPSTONE_PANEL_PLAYBOOK.md)**: Live demo runbook, 6-act verification script, and panel Q&A defense guide.
- **[Conversational Presentation & Demo Script (`docs/CAPSTONE_CONVERSATIONAL_PRESENTATION_AND_DEMO_SCRIPT.md`)](docs/CAPSTONE_CONVERSATIONAL_PRESENTATION_AND_DEMO_SCRIPT.md)**: Word-for-word presenter script for the 12-slide Executive Briefing deck and live demo.
- **[Submission & Bundling Guide (`docs/CAPSTONE_SUBMISSION_AND_BUNDLING_GUIDE.md`)](docs/CAPSTONE_SUBMISSION_AND_BUNDLING_GUIDE.md)**: Pre-submission checklist and automated audit commands.
- **[Artifact Analyzer Report (`docs/CAPSTONE_ARTIFACT_ANALYZER_REPORT.md`)](docs/CAPSTONE_ARTIFACT_ANALYZER_REPORT.md)**: Detailed code verification report across all 5 engineering pillars.

---

## 🧪 Running the Automated Verification Suite

```bash
# Run all 53 behavioral, conformance, security, and resilience pytest tests
.venv/bin/pytest -q

# Run the <5s pre-flight live demo readiness verification across all 6 acts
.venv/bin/python scripts/verify_live_demo_readiness.py

# Run the 12-badge Golden Evaluation Gate
.venv/bin/python scripts/eval_gate.py
```
