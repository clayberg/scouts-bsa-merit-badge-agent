# Scope: Scouts BSA Merit Badge Counselor Workbench

## 1. Problem statement
Volunteer Scouts BSA Merit Badge Counselors typically spend 8 to 15 hours building slide decks, Scout workbooks, lesson plans, and parent prerequisite letters for each of the 138 official Merit Badges. Standard single-prompt LLM slide generators do a poor job on Merit Badges: they summarize requirements down to four generic bullets, cut off multi-part sub-requirements (`1a`, `1b`, `2b1`, `3a-3q`), mix up requirement years, and repeat the same stock diagram across slides.

This project builds a multi-agent curriculum workbench on the Google Agent Development Kit (ADK) for Python (`scouts-bsa-merit-badge-agent`). It generates widescreen (`16:9`) PowerPoint decks (`.pptx`), printable Scout workbooks (`.md`), session agendas, and Youth Protection (YPT) parent letters grounded in the official BSA Merit Badge Pamphlet:

1. **5-tier pamphlet and regional research (`src/agents/researcher.py`)**: Extracts the full requirement and sub-requirement tree verbatim from `scouting.org` and official BSA Pamphlet PDFs (`PyMuPDF`), locks the requirement wording with a SHA-256 hash (`compute_canonical_pamphlet_hash()`), classifies each requirement by how it is taught (`IN_CLASS_DISCUSSION`, `HANDS_ON_SKILL_STATION`, `PREREQUISITE_CAMPOUT_HOME`), and resolves the counselor's City, State, or 5-digit ZIP code (`resolve_counselor_location()`) to regional NOAA National Weather Service offices, local terrain hazards, and state agencies.
2. **12-archetype slide planner and visual pipeline (`src/agents/planner.py`, `src/agents/beautifier.py`, `src/tools/pptx_builder.py`)**: Maps each requirement onto 12 structured `python-pptx` layouts with `[SAY]`, `[DEMONSTRATE]`, and `[ASK SCOUTS]` teaching notes. Preserves extracted BSA Pamphlet figures and 220-DPI technical diagrams (`src/tools/diagram_generator.py`), and attaches pre-populated or on-demand Nano Banana Hero Illustrations (`NANO_BANANA_HERO`, with 76 compressed PNGs cached across the 23 core Merit Badges and deterministic fallback to 220-DPI Scouts BSA EDGE Skill Concept Maps) on requirement intro slides in `BEAUTIFIED` and `STUDIO` modes.
3. **Two-stage layout and safety check (`src/agents/reviewer.py`)**: Stage 1 checks `python-pptx` shape coordinates in memory in under 10ms (`check_pptx_conformance()`) to catch Axis-Aligned Bounding Box (AABB) overlaps, text below `13.0pt`, WCAG contrast ratios below `4.5:1`, or duplicate images. Stage 2 verifies 100% requirement coverage and BSA Guide to Safe Scouting rules inside a bounded `LoopAgent` (`max_iterations=3`).
4. **Dual web workbenches (`ui/` + `src/server.py` and `src/app.py`)**: Provides both a FastAPI/Material 3 web application (`:8085`) with Server-Sent Events (SSE) and A2UI v0.9 JSON payloads, and a Python-native Streamlit workbench (`:8501`). The web slide preview and the downloaded `.pptx` file render identical text, card layouts, and visual themes across all three polish tiers (`STANDARD`, `BEAUTIFIED`, and `STUDIO`).

## 2. Target users
- **Primary**: Scouts BSA Merit Badge Counselors, Summer Camp Area Directors, and Merit Badge University (MBU) instructors.
- **Secondary**: Youth Patrol Leaders and Eagle Scout candidates preparing teaching sessions using the BSA EDGE Method (`Explain, Demonstrate, Guide, Enable`).

## 3. Functional scope

| Area | Included capabilities |
| :--- | :--- |
| **1. Pamphlet and regional research** | Official `scouting.org` requirement tree, PDF pamphlet text and figure extraction, SHA-256 requirement hash lock, and ZIP/City regional agency lookup (`resolve_counselor_location`). |
| **2. Requirement triage** | Classifies every requirement into `IN_CLASS_DISCUSSION`, `HANDS_ON_SKILL_STATION`, or `PREREQUISITE_CAMPOUT_HOME`. |
| **3. Slide planning and StudioKit** | 12 `python-pptx` slide archetypes, worked examples, 2-column comparisons, Socratic quizzes, session lesson plans, and YPT parent letters. |
| **4. Visuals and polish tiers** | Three distinct tiers (`STANDARD` white, `BEAUTIFIED` warm cream `#FAF8F5`, `STUDIO` dark slate `#0F172A`), pamphlet figures, 220-DPI technical diagrams, 76 pre-populated Nano Banana hero illustrations (with EDGE Concept Map fallback), and an 11-style Image Studio (`Auto (Content-Aware Mix)` + `Include Uniformed Scouts`). |
| **5. Layout and safety checks** | Stage 1 `<10ms` AABB geometry, font-floor, and WCAG contrast check + Stage 2 curriculum and Guide to Safe Scouting review. |
| **6. Security and FinOps** | Pre-LLM PII scrubbing (`scrub_pii_before_sink`), Model Armor prompt checks, HMAC-SHA256 HITL build token, and `$1.00` FinOps budget cap. |
| **7. User interfaces** | FastAPI Material 3 Web Workbench (`:8085`) + Streamlit Counselor Workbench (`:8501`) with per-slide co-design controls. |
