# Project Scope & Boundaries (`SCOPE.md`)

## 1. In-Scope Capabilities
- **All 144 Official Scouts BSA Merit Badges**:
  - Complete requirement and sub-requirement JSON trees (`data/merit_badge_requirements/*.json`) for all `144` official Merit Badges (`18` Eagle-Required and `126` Electives, including 2025/2026 Scouting America additions such as *Artificial Intelligence*, *Cybersecurity*, *Wildland Fire Management*, *Multisport*, *Action Sports*, and *Health Care Professions*).
  - Deep benchmark coverage for `26` Merit Badges (`18` Eagle-Required + `8` high-demand Electives) and `72` pre-built `.pptx` decks (`deliverables/benchmark_and_random_samples/`).
- **Pre-Cached Multimodal Visual Asset Pipeline (`$0.00` Runtime Image Cost)**:
  - `2,297` pre-generated, compressed (`<= 1,024px`, 8-bit PNG) Nano Banana hero and multi-slide topic illustrations (`assets/ai_illustrations/`) covering every requirement across all `144` Merit Badges.
  - `4,317` extracted and de-boxed official BSA Pamphlet figures (`assets/pamphlet_images/`), `135` transparent RGBA Merit Badge emblems (`assets/badge_emblems/`), and `134` official pamphlet covers (`assets/pamphlet_covers/`).
  - High-resolution embedded-text diagrams for key scientific and meteorological concepts (Hydrologic Cycle, WSR-88D Doppler Radar, Cold/Warm Front cross-sections, 3D Warm Front side-by-side profile, Sea/Land Breezes, Cloud Classification by Altitude Level, and cropped Earth's 23.5° Axial Tilt & Seasons) with scene-specific visual captions.
- **Material 3 Expressive Counselor Workbench (`src/server.py`, `ui/`)**:
  - 3-column responsive layout with collapsible Setup and Filmstrip panels, 16:9 widescreen HTML5 preview stage with 1:1 `.pptx` visual parity, Fullscreen Presentation Mode (`F`), Per-Slide Co-Design Bar, 4-Tab Merit Badge Image Studio, and 5-Tab Under-Stage Counselor Toolkit Drawer.
- **Enterprise AgentOps & Security Controls**:
  - Google ADK 7-sub-agent coordinator hierarchy (`MeritBadgeCoordinator`), FastMCP cryptographic HITL confirmation tokens, A2A 1.0 Agent Card discovery (`/.well-known/agent.json`), A2UI v0.9 JSON envelopes, Youth Protection (YPT) PII scrubbing, Model Armor prompt-injection defense, OpenTelemetry distributed tracing, and SQLite + Vertex AI Memory Bank hybrid BM25/Vector RRF retrieval.

## 2. Out-of-Scope Boundaries
- **Official Scoutbook Plus Direct Database Writes**: The workbench generates Scoutbook-compatible CSV sign-off exports (`#btn-bluecard-export-csv`) and printable Blue Card (`#34124`) matrices, but does not write directly into Scouting America's closed production Scoutbook database.
- **Storage of Youth Personal Identifiable Information (PII)**: By design and Scouting America Youth Protection guidelines, the system never persists youth names, phone numbers, email addresses, or home addresses to cloud logs or long-term storage.
- **Autonomous Modification of Official Requirement Text**: Agents are strictly prohibited from altering, abbreviating, or paraphrasing official Scouting America requirement text on `REQUIREMENT_INTRO` slides.
