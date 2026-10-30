# Model Context Protocol (MCP) Server Integration Guide

This guide explains how to connect external AI coding assistants, desktop agents, and multi-agent orchestrators to the **Scouts BSA Merit Badge Counselor Workbench MCP Server** ([`src/mcp_server.py`](../src/mcp_server.py)).

The Workbench includes a built-in, dual-transport Model Context Protocol (`2024-11-05`) server (`scouts-bsa-merit-badge-workbench`) that exposes **15 MCP Tools**, **7 grounded `bsa://` MCP Resources**, and **5 guided Pedagogical Prompts** (`27` capabilities total) backed directly by the application's 12-table SQLite WAL database (`scouts_bsa_sessions.db`), hybrid BM25 + vector pamphlet search engine, and 12-archetype PowerPoint builder.

![MCP Server & Agent Hub Modal](images/ug_mcp_hub_light.png)

---

## 1. Architecture & Dual-Transport Modes

The MCP server supports two transport modes out of the box, sharing the same SQLite database (`counselor_workspaces`, `counselor_favorites`, `pamphlet_vector_memory`, `badge_image_catalog`) and asset directories:

```mermaid
flowchart LR
    subgraph Clients["External AI Agents & IDEs"]
        C1["Claude Desktop / Cursor\n(stdio: python -m src.mcp_server)"]
        C2["Gemini CLI / AGY\n(stdio or HTTP POST /mcp)"]
        C3["Google ADK MCPToolset\n(stdio or HTTP /mcp/sse)"]
    end

    subgraph Server["Scouts BSA Workbench MCP Server (src/mcp_server.py)"]
        R["7 Grounded Resources (bsa://*)"]
        T["15 Actionable Tools"]
        P["5 Guided Counselor Prompts"]
        G["Model Armor YPT + FinOps Gates"]
    end

    subgraph Engine["Workbench Core & SQLite WAL"]
        ADK["7-Agent Curriculum & Storyboard Pipeline"]
        PPTX["PowerPoint Template & 12-Archetype Builder"]
        DB[("scouts_bsa_sessions.db\nWorkspaces, Favorites & Blue Cards")]
    end

    Clients <--> Server
    Server --> G --> Engine
```

| Transport Mode | Entrypoint / Endpoint | Best For |
| :--- | :--- | :--- |
| **1. Local `stdio` Transport** | `python -m src.mcp_server` (or `scouts-bsa-mcp` CLI script) | Claude Desktop, Gemini CLI, AGY, Cursor, Windsurf, and local Python Google ADK `StdioServerParameters` agents. |
| **2. HTTP JSON-RPC 2.0 & SSE** | `POST /mcp`, `GET /mcp/info`, `GET /mcp/sse` (also aliased under `/api/v1/mcp*`) | Cloud Run deployments, remote agent orchestrators, browser-based testing, and the in-app **Interactive MCP Playground** (`🤖 MCP Hub`). |

---

## 2. Client Setup & Configuration Snippets

You can copy pre-filled configuration snippets directly from the top-bar **`🤖 MCP Hub`** button inside the Workbench UI, or use the configurations below.

### 2.1 Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "scouts-bsa-workbench": {
      "command": "/path/to/scouts-bsa-merit-badge-agent/.venv/bin/python",
      "args": ["-m", "src.mcp_server"],
      "env": {
        "PYTHONPATH": "/path/to/scouts-bsa-merit-badge-agent"
      }
    }
  }
}
```

### 2.2 Gemini CLI / AGY (`settings.json`)

```json
{
  "mcpServers": {
    "scouts-bsa-workbench": {
      "httpUrl": "http://localhost:8085/mcp",
      "command": "python",
      "args": ["-m", "src.mcp_server"]
    }
  }
}
```

### 2.3 Cursor (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "scouts-bsa-workbench": {
      "url": "http://localhost:8085/mcp/sse"
    }
  }
}
```

### 2.4 Google ADK Python Agent (`MCPToolset`)

```python
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import MCPToolset, StdioServerParameters

bsa_mcp_toolset = MCPToolset(
    connection_params=StdioServerParameters(
        command=".venv/bin/python",
        args=["-m", "src.mcp_server"],
    )
)

counselor_assistant = LlmAgent(
    name="MeritBadgeCampAssistant",
    model="gemini-2.5-flash",
    instruction="Use the Scouts BSA Workbench MCP tools to build slide decks, apply templates, and manage Blue Card rosters.",
    tools=[bsa_mcp_toolset],
)
```

---

## 3. Grounded `bsa://` MCP Resources (7)

External agents can read structured catalog, requirement, template, class preparation page, and workspace state directly via `resources/read`. Inside Section 2 of the in-app **`🤖 MCP Hub`**, every resource card includes interactive **`▶ Read Live`** and **`📋 Copy URI`** buttons so you can inspect the live resource payload in the Interactive MCP Playground or copy the URI into an external agent session:

| Resource URI | Name | Returned JSON Payload |
| :--- | :--- | :--- |
| `bsa://catalog/badges` | Official 149 Merit Badges Catalog | All 149 Merit Badges (`143` Active Official Merit Badges including *Sewing and Needlework*, `5` Scouting America Test Lab Pilots: *Auctioneering*, *Dance*, *Physics*, *Psychology*, and *Sewing and Needlework*, and `1` Discontinued Historical badge: *Citizenship in Society* annotated with a red `🚫 Discontinued` indicator in the Patch Gallery) with `name`, `slug`, `category`, `is_eagle_required`, `is_test_lab`, `is_discontinued`, `status`, `is_favorite`, and `emblem_url`. |
| `bsa://badges/{badge_name}/requirements` | Official Verbatim Merit Badge Requirements | Official verbatim requirements tree and nested `sub_requirements` (`1a..15d`, `3a..3q`, `2b1`) plus 5-Tier `syllabus_bucket`, clause-driven `workbook_organizer`, `gear_checklist`, and `common_misconception_pair` for any badge (e.g., `bsa://badges/First Aid/requirements`). |
| `bsa://badges/{badge_name}/images` | Curated Vision-Verified Pamphlet & Nano Banana Visuals | All pre-bundled Vision-verified pamphlet figures (`2,833`) and Nano Banana illustrations (`2,792`) for the badge (part of `5,625` total visual assets across 149 badges). |
| `bsa://badges/{badge_name}/class-prep-cpp` | 1-Page Class Preparation Page (CPP) | Complete multi-page printable Class Preparation Page (`cpp_html`) with dynamic PyMuPDF text wrapping (`0%` dropped requirement text) and structured organizer syllabus summary for any of the 149 badges. |
| `bsa://templates/catalog` | PowerPoint Slide Templates Catalog | All 29 built-in curated Scouting & event templates across 9 Style Families plus any custom uploaded/URL templates, including `SafeCanvasBounds` and brand palettes. |
| `bsa://workspaces/list` | Saved Counselor Deck Workspaces | Metadata list of all saved counselor deck workspaces (`workspace_id`, `workspace_title`, `badge_name`, `session_label`, `camp_bundle_tag`, `slide_count`, `scout_count`). |
| `bsa://workspaces/{workspace_id}` | Full Counselor Deck Workspace State | Complete storyboard slides, 5-Part Facilitator Guide speaker notes (with `default_presenter_notes`), selected PowerPoint template, and Patrol Blue Card (`#34124`) Scout roster. |

---

## 4. Actionable MCP Tools (15)

All 15 tools can be invoked over `stdio` or via `POST /mcp` (`method: "tools/call"`):

| # | Tool Name | Purpose & Key Arguments |
| :--- | :--- | :--- |
| **1** | `search_merit_badges` | Filters the 149 Merit Badges (`143` Active Official, `5` Test Lab Pilots, `1` Discontinued Historical) by `query`, `category`, `eagle_only`, `test_lab_only`, or `favorites_only`. |
| **2** | `query_merit_badge_pamphlet` | Runs Hybrid Okapi BM25 + 768-dim Cosine RRF search across the official BSA Merit Badge pamphlet PDF (`badge_name`, `question`, `top_k`). |
| **3** | `create_merit_badge_slide_deck` | Builds a complete Merit Badge teaching slide deck, applies `template_id` (`bsa_scouting_america`, `scouting_america_250`, `scouting_america_forest_sunrise`, etc.), `visual_theme` (`WARM_CREAM`, `CRISP_WHITE`, or `DARK_SLATE`; short aliases `CREAM`, `WHITE`, `SLATE` and legacy enum aliases `BEAUTIFIED`, `STANDARD`, `STUDIO` are also accepted), and optional `deck_style` (`DeckStyleConfig`: `CLEAN_OPEN`, `LEFT_ACCENT_LINE`, `BOXED_CARDS` where `BOXED_CARDS` only updates `text_container_style` while `image_frame_style` remains `"FRAMELESS_CLEAN"` by default, resolved via `resolve_effective_slide_style()`), saves a persistent workspace in `counselor_workspaces`, and returns `workspace_id` and `pptx_download_url`. |
| **4** | `get_slide_deck_workspace` | Loads a saved deck workspace (`workspace_id`), returning its full slide outline, template profile, and Patrol Blue Card (`#34124`) roster. |
| **5** | `update_slide_in_deck` | Surgically updates a slide (`workspace_id`, `slide_index`) with new `title`, `bullet_points`, `presenter_notes`, `archetype`, or `visual_caption`. |
| **6** | `polish_slide_teaching_notes` | Transforms and expands the `<5ms` deterministic **5-Part Non-Redundant Facilitator Guide** (`[PACING & MODALITY]`, `[ASK SCOUTS FIRST]`, `[EXPECTED PAMPHLET ANSWER KEY]`, `[COMMON MISCONCEPTION TO CORRECT]`, `[DEMONSTRATION & SIGN-OFF RUBRIC]`, with child slides scoped to their specific sub-requirements `1a-1d` vs. `1e-1g`, `3a-3q` and rotated `pamphlet_excerpts`) into a conversational facilitator script tailored to `local_context`, adding physical stage directions, spoken Socratic dialogue with follow-up probes, synthesized visual-card answer keys, field-trap coaching, and observable sign-off rubrics while preserving the 5 headers and saving `default_presenter_notes` for 1-click restore (`workspace_id`, `slide_index`, `audience_level`). |
| **7** | `generate_or_select_slide_image` | Lists curated slide image choices (`action="list_choices"`), selects an alternate choice (`action="select_choice"`, `choice_index`), or generates a custom Nano Banana illustration (`action="generate_custom"`, `custom_prompt`, `include_slide_context`, `user_consented`). Enforces Model Armor YPT/safety checks (including the 3-layer context-aware phone redaction filter) and the `$0.08` FinOps consent gate. |
| **8** | `apply_powerpoint_template` | Switches a saved workspace (`workspace_id`) to any built-in or uploaded PowerPoint template (`template_id`, `visual_theme` (`WARM_CREAM`, `CRISP_WHITE`, `DARK_SLATE`, or aliases), `accent_palette_key`, and optional `deck_style` `DeckStyleConfig`) and rebuilds the `.pptx` deck using `SafeCanvasBounds` and `resolve_effective_slide_style()`. |
| **9** | `export_slide_deck` | Exports a workspace (`workspace_id`) as a downloadable `.pptx` presentation (`export_format="pptx"`) or returns scannable ISO 18004 QR checklist links (`export_format="pocket_checklist"`). |
| **10** | `generate_class_prep_and_parent_letter` | Generates a timed counselor session agenda and 3-Stage YPT Two-Deep Prerequisite Parent/Scoutmaster Letter (`workspace_id`, `session_mode`, `camp_or_location`). |
| **11** | `manage_patrol_blue_card_roster` | Manages Application for Merit Badge (`#34124`) Scout attendees (`action="list"`, `"add_or_update_scout"`, `"copy_roster_from_workspace"`, or formula-sanitized `"export_scoutbook_csv"` with Per-Troop Privacy Isolation). |
| **12** | `audit_deck_conformance` | Runs the deterministic Stage-1 AABB geometry verifier (`0` shape overlaps, `>= 12.0pt` font floor, `<= 8` paragraphs per card) and Stage-2 Visual Quality Auditor (`audit_deck_visual_quality()`: `visual_quality_score`, `box_density_ratio`, `whitespace_ratio`) on a workspace's `.pptx` deck. |
| **13** | `generate_fillable_scout_workbook` | Generates a **4-Pillar Sub-Requirement-Unrolled Fillable HTML5 & AcroForm PDF Scout Merit Badge Workbook (`GTA §7.0.3.2`)** (`badge_name`, `counselor_info`) that unrolls all nested `sub_requirements` (`1a..15d`, `3a..3q`, `2b1`) across `.MD`, `contenteditable` `.HTML`, and AcroForm `.PDF` with dynamic multi-page PyMuPDF text wrapping (`0%` dropped requirement text), 13 clause-driven bespoke graphic organizers (`HAZARD_5COL`, `SYMPTOMS_FIRST_AID_PREVENTION_3COL`, `CAMPING_LOG_20NIGHT`, `FITNESS_ASSESSMENT_4STAGE`, `FITNESS_LOG_12WK`, `MEAL_PLANNER_AND_COST_TABLE`, `CITIZENSHIP_CIVIC_ORGANIZER`, `SCIENTIFIC_EXPERIMENT_SHEET`, `SENSORY_OBSERVATION_LOG`, `ENGINEERING_DESIGN_NOTEBOOK`, `CAREER_EXPLORATION_CARD`, `SKETCH_AND_OBSERVATION_CANVAS`, `PHYSICAL_SKILL_VERIFICATION_RUBRIC`), interactive `gear_checklist` checkboxes, and Counselor Pre-Approval signature gates. |
| **14** | `generate_class_preparation_page_cpp` | Generates a **Multi-Page Printable Class Preparation Page (`CPP`)** (`badge_name`, `schedule_format`, `companion_badge_name`) with inline SVG QR code, 5-Tier Syllabus Bucket table, dynamic multi-page PyMuPDF text wrapping (`0%` dropped requirement text), and Organizer Catalog Spec Sheet. |
| **15** | `manage_multisession_clinic_attendance_and_partials` | Manages multi-session `S1|S2|S3|S4|M` attendance, multi-troop unit tags with Per-Troop Privacy Isolation (`Troop 19` vs. `Troop 114`), and Smart Partial differentiation (`actionable_makeup_reqs` vs. `expected_hometroop_reqs`) in SQLite WAL (`scout_session_attendance_and_partials`). |

---

## 5. Guided Counselor MCP Prompts (5) & Interactive MCP Playground

MCP Prompts are reusable multi-step workflow templates exposed via the standard `prompts/list` and `prompts/get` JSON-RPC 2.0 methods. In MCP-compatible clients such as **Claude Desktop**, **Gemini CLI / AGY**, and **Cursor**, these prompts appear directly in the `/` slash-command picker (for example, `/build-camp-merit-badge-curriculum`). When selected, the server returns a structured multi-step instruction message that guides the host AI agent through reading the appropriate `bsa://` resources and calling the Workbench's MCP tools in sequence.

Inside Section 2 of the in-app **`🤖 MCP Hub`**, each prompt card also includes **`▶ Execute Prompt`** and **`📋 Copy Prompt`** buttons so you can run the prompt live in the Interactive MCP Playground or copy the rendered workflow prompt to your clipboard.

| Prompt Name | Arguments | Workflow Summary |
| :--- | :--- | :--- |
| `build-camp-merit-badge-curriculum` | `badge_name`, `template_id` | Reads official requirements, generates a Deep Dive deck with the chosen template, builds a 5-day Summer Camp lesson plan, and audits Stage-1 AABB conformance. |
| `prepare-merit-badge-midway-bundle` | `badge_names_csv`, `template_id` | Batch-creates harmonized slide decks and parent prerequisite letters across multiple badges for a Council Merit Badge Midway. |
| `review-scout-blue-card-signoffs` | `workspace_id` | Audits each Scout's completed requirements against the official requirement tree and exports a Scoutbook-ready CSV. |
| `customize-slide-deck-for-local-troop` | `workspace_id`, `state_code`, `city_or_camp` | Tailors a saved deck workspace and teaching scripts to local state weather, terrain, and council camp context. |
| `multisession_mbc_clinic_facilitator_prompt` | `badge_name`, `companion_badge_name` | Orchestrates a 4-session Merit Badge College clinic (`75 min x 4 Saturdays`), generating the 1-Page CPP, Fillable Scout Workbook, 3-Stage YPT Two-Deep Email Pack, and S1-S4 Smart Partial matrix. |

### 5.1 In-App Interactive MCP Playground (`[📊 Visual Card Preview | { } Raw JSON-RPC 2.0]`)

Section 3 of the **`🤖 MCP Hub`** provides a full-height Interactive MCP Playground (`min-height: 440px`) that supports all **27 MCP capabilities** (**15 Tools**, **7 `bsa://` Resources**, and **5 Guided Prompts**) directly from the browser:

- **Unified Capability Selector**: Pick any of the 15 Tools (`tools/call`), 7 `bsa://` Resources (`resources/read`), or 5 Guided Prompts (`prompts/get`) from the grouped selector, or click any card in Section 2 to auto-populate the JSON arguments editor and execute immediately.
- **Dual-Mode Output Toggle (`[📊 Visual Card Preview | { } Raw JSON-RPC 2.0]`)**:
  - **`📊 Visual Card Preview`**: Renders human-friendly Material 3 summary cards for Merit Badge search results (with patch emblems and Eagle-Required pills), pamphlet BM25+Vector passages (with badge emblems), template safe-zone profiles (with inline color dots), saved deck workspaces (with badge emblems and template color dots), Blue Card rosters, and multi-step guided prompt workflows.
  - **`{ } Raw JSON-RPC 2.0`**: Displays the exact JSON-RPC 2.0 response envelope returned by `POST /mcp`, alongside a live RPC latency and status pill (`200 OK • X ms`) and a 1-click **`📋 Copy Response`** button.

---

## 6. HTTP JSON-RPC 2.0 Examples (`POST /mcp`)

### 6.1 List Available MCP Tools
```bash
curl -s -X POST http://localhost:8085/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'
```

### 6.2 Build a Deck with the `BSA America 250™` Template
```bash
curl -s -X POST http://localhost:8085/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "create_merit_badge_slide_deck",
      "arguments": {
        "badge_name": "First Aid",
        "template_id": "scouting_america_250",
        "visual_theme": "WARM_CREAM",
        "workspace_title": "First Aid - Morning Patrol",
        "session_label": "Period 1 (9:00 AM)"
      }
    }
  }'
```

### 6.3 Read the PowerPoint Template Catalog Resource
```bash
curl -s -X POST http://localhost:8085/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "resources/read",
    "params": {
      "uri": "bsa://templates/catalog"
    }
  }'
```

---

## 7. Related Documentation

- [API Integration Guide](API_INTEGRATION_GUIDE.md) - REST (`/api/v1/*`), Server-Sent Events (SSE), and A2A 1.0 protocol reference.
- [User Guide](USER_GUIDE.md) - Counselor walkthrough for the Template Studio, Multi-Badge Deck Library, Favorites, and MCP Hub.
- [Admin Guide](ADMIN_GUIDE.md) - Super-User Admin Console, asset diagnostics, and Zero-PII telemetry.
