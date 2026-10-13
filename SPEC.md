# Product & Technical Specification: Scouts BSA Merit Badge Counselor Workbench (`v2.6`)

## 1. Objective & Scope
Build an autonomous, production-hardened multi-agent system using the **Google Agent Development Kit (ADK)** (`google-adk`), **FastMCP**, **A2A 1.0**, and **A2UI v0.9** that assists Scouts BSA Merit Badge Counselors in researching, planning, co-designing, and generating complete, curriculum-aligned instructional packages for all **144 official Scouts BSA Merit Badges** (`18` Eagle-Required and `126` Electives, plus `2` synthetic validation stubs in the catalog selector).

## 2. Functional Requirements
1. **5-Tier Authoritative Research (`ResearcherAgent`)**:
   - Ingest official Scouting America requirement trees (`1a`, `1b`, `2a`..`15c`) across all `144` official Merit Badges (`data/merit_badge_requirements/*.json`), extract official pamphlet text and `4,316` de-boxed pamphlet figures via `pypdf`, and compute a deterministic **Canonical Pamphlet SHA-256 Hash Lock** (`compute_canonical_pamphlet_hash`) to prevent silent curriculum drift.
   - Ground field examples, local civic ordinances, emergency contacts, and National Weather Service (NWS) offices to the counselor's **Location (City, State or ZIP Code)** (`location_or_zip`).
2. **Pedagogical Triage & Session Pacing (`CurriculumPlannerAgent`)**:
   - Classify every requirement into three execution modes (`IN_CLASS_DISCUSSION`, `HANDS_ON_SKILL_STATION`, `PREREQUISITE_CAMPOUT_HOME`).
   - Generate printable Counselor StudioKit artifacts:
     - **Multi-Format Session Pacing Agenda** (`3 Troop Meetings`, `Summer Camp Week 4x50-Min`, `Saturday Clinic`, `Weekend Campout Practicum`).
     - **Prerequisite Parent Letter** (with one-click Copy, Draft in Email App, Compose in Gmail, Print/PDF, and `.md` export).
     - **Scout Fill-in-the-Blank Workbook** and **Counselor Teaching Guide**.
     - **Master Quartermaster Gear & Materials Checklist** with Patrol Size Multiplier (`1x`, `2x`, `3x`, `4x`).
     - **Interactive Patrol Blue Card (`#34124`) & Scoutbook Plus Sign-Off Matrix** with CSV export.
3. **12-Archetype Storyboard & Visual Pipeline (`BeautifierAgent`, `WebImageSearchAgent`, `NanoBananaImageAgent`)**:
   - Support two depth modes (`Deep Dive / Camp School Deck` with 45-85+ slides and `Troop Meeting Deck` with 16-28 slides) and three visual polish tiers (`STANDARD` Crisp White, `BEAUTIFIED` Warm Cream `#FAF8F5`, and `STUDIO` Dark Slate `#0F172A`).
   - Deliver **100% pre-cached visual coverage across all 144 Merit Badges**: `2,292` pre-generated, compressed (`<= 1,024px`, 8-bit PNG) Nano Banana hero and multi-slide topic illustrations (`assets/ai_illustrations/`), `4,316` extracted and de-boxed official pamphlet figures (`assets/pamphlet_images/`), `135` transparent RGBA Merit Badge emblems (`assets/badge_emblems/`), and `134` official pamphlet covers (`assets/pamphlet_covers/`).
   - Provide high-resolution embedded-text diagrams for key scientific and meteorological concepts (Hydrologic Cycle, WSR-88D Doppler Radar, Cold/Warm Front cross-sections, 3D Warm Front profile, Sea/Land Breezes, Cloud Classification by Altitude Level, and cropped Earth's 23.5° Axial Tilt & Seasons) paired with concise, scene-specific visual captions.
   - Provide a **4-Tab Merit Badge Image Studio** (`Quick-Switch Cached Library`, `Web Image Search`, `Nano Banana Live AI Image Generator` gated by an explicit `$0.08` USD FinOps user consent check, and `Local File Upload`).
4. **Two-Stage Conformance & Hallucination Gate (`QualityReviewerAgent`)**:
   - **Stage 1 Deterministic Simulator (`<10ms`)**: Inspect every generated `.pptx` slide via `python-pptx` to verify `0` Axis-Aligned Bounding Box (AABB) shape overlaps, `0` out-of-bounds shapes (`13.333" x 7.5"` widescreen canvas), and minimum `>= 12pt` body font size.
   - **Citation Grounding & Self-Healing Loop**: Verify `100%` of requirement slides map to canonical requirement IDs and trigger automatic repair (up to `MAX_CONFORMANCE_RETRIES = 2`) if any defect is detected.

## 3. Non-Functional & Youth Protection Requirements
- **Youth Protection (YPT) & Zero-PII Guarantee**: Dual-layer regex and Cloud DLP scrubbing (`src/pii_scrubber.py`) plus Model Armor prompt-injection interception (`src/agents/guardrails.py`) before any prompt, SQLite write, or OpenTelemetry span emission.
- **FinOps Budget Enforcement**: Pre-flight cost estimation (`estimate_workflow_finops_cost`), hard `$1.00` USD per-session ceiling, and `$0.00` runtime image cost when using the `2,292` pre-cached illustrations.
- **Automated Verification**: `53` non-hollow `pytest` behavioral and conformance tests across 5 test modules plus a 12-badge Golden Evaluation Gate (`scripts/eval_gate.py`).
