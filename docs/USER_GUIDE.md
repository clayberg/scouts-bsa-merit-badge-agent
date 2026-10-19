# Scouts BSA Merit Badge Counselor Workbench: User Guide

Welcome to the **Scouts BSA Merit Badge Counselor Workbench**. Whether you are preparing for three 45-minute troop meetings, a week of summer camp instruction, a Saturday Merit Badge Midway clinic, or a weekend campout practicum, this tool helps you prepare a complete, grounded teaching package for any of the **144 official Scouts BSA Merit Badges** in a few minutes.

Instead of spending an entire weekend formatting slides and typing up handouts from scratch, you can generate:
- A widescreen (`16:9`) **PowerPoint Slide Deck (`.pptx`)** (or 1-click **native Google Slides deck**) with official requirement wording, clear teaching cards, diagrams, official pamphlet figures, counselor speaker notes, and your choice of **8 built-in Scouting America & Heritage PowerPoint templates** (or your own uploaded `.pptx`/image template).
- A **Multi-Badge Saved Decks & Classroom Sessions Library (`🗂️ My Decks`)** and **1-Click Starred Favorites (`⭐`)** so you can switch between multiple Merit Badges or Morning vs. Afternoon patrol sections in under `80ms` with isolated Patrol Blue Card (`#34124`) rosters.
- A **Centered Split-Screen Presenter View (`🪟 Presenter View` / `P`)** with 3 color-coded `[SAY]`, `[DEMONSTRATE]`, and `[ASK SCOUTS]` teleprompter cards and a non-disruptive **`↗ 2nd Monitor`** floating speaker window, plus a **Fullscreen Teleprompter Notes Drawer (`🎙️ Notes (N)`)**, **Interactive Patrol Scoreboard (`🏆 Patrol Scoreboard`)**, and **Live Classroom & Skill Station Timer (`⏱️ Timer`)**.
- An **In-App Markdown Documentation Viewer (`📘 Documentation` / `D`)** and **MCP Server & Agent Hub (`🤖 MCP Hub`)** in the Top Application Bar so you can read the User Guide, Admin Guide, and 10 engineering references (including the **[MCP Server Integration Guide](MCP_SERVER_INTEGRATION_GUIDE.md)**) or connect AI assistants (`12` MCP tools, `6` `bsa://` resources, `4` guided prompts) without leaving your active slide deck.
- A **Slide Deck Customizer** directly in the left outline so you can insert custom local camp slides (`➕ Insert Slide`), hide home-prerequisite slides (`👁️ Hide Prereqs`), or reorder and skip individual slides (`▲` / `▼` / `👁`) before exporting your `.pptx`.
- A printable **Scout & Counselor Workbook (`.md` / PDF)** with section filters, fill-in-the-blank study boxes, and requirement sign-off checklists.
- **Printable 3x5 Counselor Pocket Cue Cards** (4 cards per page) and a **1-Page Printable Pocket Field Checklist & QR Handout** for outdoor field instruction away from a screen.
- A **Counselor Session Agenda & Patrol Skill Station Rotator Matrix** tailored to your meeting schedule and patrol count.
- A **Master Quartermaster Gear Checklist** and **Pre-Class Prerequisite Readiness Checklist** scaled to the size of your patrol or class.
- A **Youth Protection (YPT) Prerequisite & Parent Welcome Letter** ready to open in your email app or Gmail.
- An interactive **Patrol Blue Card (`#34124`) & Scoutbook Plus Sign-Off Tracker** with Scoutbook `.csv` import (`📤 Import CSV`), **`🔁 Copy Scouts From Deck`** cross-badge roster copy, bulk roster paste, 1-click column header sign-off, completion date stamping, and **Printable 3-Panel Blue Cards (`#34124`)**.

> [!NOTE]
> **System Administrators, Maintainers & AI Agent Integrators**: Looking for the Zero-PII Super-User Admin Console (144-badge image and caption curation studio, aggregated usage/latency/image-swap telemetry, and system diagnostics)? Read the dedicated **[Super-User Admin Guide (`docs/ADMIN_GUIDE.md`)](ADMIN_GUIDE.md)**. To connect Claude Desktop, Gemini CLI, Cursor, or Google ADK agents to the built-in Model Context Protocol server, read the **[MCP Server Integration Guide (`docs/MCP_SERVER_INTEGRATION_GUIDE.md`)](MCP_SERVER_INTEGRATION_GUIDE.md)**.

---

## Table of Contents

1. [Getting Started in 60 Seconds](#1-getting-started-in-60-seconds)
2. [Tour of the Counselor Workbench Screen](#2-tour-of-the-counselor-workbench-screen)
3. [Step 1: Finding & Selecting a Merit Badge](#3-step-1-finding--selecting-a-merit-badge)
4. [Step 2: Choosing Your Deck Style & Saving Your Counselor Profile](#4-step-2-choosing-your-deck-style--saving-your-counselor-profile)
5. [Step 3: Watching the Scout Slide Construction Showcase](#5-step-3-watching-the-scout-slide-construction-showcase)
6. [Step 4: Previewing, Presenting, Timing & Switching Slide Images](#6-step-4-previewing-presenting-timing--switching-slide-images)
7. [Step 5: Customizing Individual Slides, Layouts, Graphics & Text](#7-step-5-customizing-individual-slides-layouts-graphics--text)
8. [Step 6: Tracking Requirements & Signing Off Blue Cards (`#34124`)](#8-step-6-tracking-requirements--signing-off-blue-cards-34124)
9. [Step 7: Using the Workbook, 4-Tab Classroom Toolkit, Cue Cards & Station Rotator](#9-step-7-using-the-workbook-4-tab-classroom-toolkit-cue-cards--station-rotator)
10. [Exporting Your Slide Deck to PowerPoint (`.PPTX`) or Direct Google Slides](#10-exporting-your-slide-deck-to-powerpoint-pptx-or-direct-google-slides)
11. [Frequently Asked Questions for Counselors](#11-frequently-asked-questions-for-counselors)

---

## 1. Getting Started in 60 Seconds

```mermaid
flowchart LR
    Step1["1. Select a Merit Badge<br/>(All 144 Official Badges)"] --> Step2["2. Pick Depth, Audience<br/>& Enter Counselor Info"]
    Step2 --> Step3["3. Click 'Generate Slide Deck<br/>& Workbook'"]
    Step3 --> Step4["4. Review Slides, Switch<br/>Images or AI-Polish Notes"]
    Step4 --> Step5["5. Present (P / F) or Export<br/>(.PPTX / Google Slides)"]
```

1. **Pick a Merit Badge**: In the left sidebar under **1. Find & Select Merit Badge**, search for any badge by name, filter by category or Eagle-Required status, open **`⚜️ Browse Visual Patch Gallery (144)`**, or click one of the **Quick-Select Popular Badges** buttons (such as **★ First Aid**, **Weather**, or **★ Camping**).
2. **Choose Your Deck Settings**: Under **2. Deck Style & Counselor Info**, choose whether you want a **Deep Dive Teaching Deck (3 to 8 Slides / Req • 30 to 100+ Slides)** or a shorter **Standard Troop Meeting Deck (1 to 4 Slides / Req • 18 to 48 Slides)**, and select your **Target Scout Audience Level**. Every deck uses the unified **Warm Cream (`#FAF8F5`) Rich Visual Slide Theme** (`Visual Assets: 100% Pre-Cached (8-Bit PNG)` in the sidebar, bundling all `3,917` curated pamphlet figures and Nano Banana illustrations at `$0.00` runtime image cost), with per-slide Card Style and Brand Palette pickers in Drawer Tab 2.
3. **Add Your Counselor & Troop Details (One Time)**: Click **👤 Counselor & Troop Profile (Saved) • Edit ▾** to enter your name, troop and council, city/state or ZIP code, optional email/phone, and optional troop logo. Your browser remembers these details automatically for future badges.
4. **Generate Your Package**: Click **Generate Slide Deck & Workbook**. While your slides are being built, you can watch the animated **Scout Slide Construction Showcase**.
5. **Present, Export, or Print**: Step through your slides on the **16:9 Slide Stage**, click **🪟 Presenter View (`P`)** or **🖥️ Present Fullscreen (`F`)** to teach from your browser, use the **Sticky Export Split-Button** (`📥 Download Slide Deck (.PPTX)` or `🟨 Open in Google Slides`), or open the **📥 Export & Print ▾** menu in the top bar to download your `.pptx` slide deck, `.md` workbook, `3x5` pocket cue cards, 1-page QR field handout, prerequisite checklist, or Blue Card CSV.

---

## 2. Tour of the Counselor Workbench Screen

![Scouts BSA Merit Badge Counselor Workbench Overview](images/workbench-overview-layout.png)

The Workbench is organized into four main areas (plus a bottom footer) so you can set up your class on the left and review all of your teaching materials on the right without losing your place:

| Screen Area | Where to Find It | What You Use It For |
| :--- | :--- | :--- |
| **Top Application Bar** | Across the very top of the window | Displays your **Dynamic Counselor Profile Pill** (which expands to show your full `"Name • Affiliation"` when top-bar space permits and collapses cleanly to `"Name"` when horizontal space is tight), the **`🗂️ My Decks | ▾` Split-Button** (`#top-workspaces-split-group`, where clicking the main button opens the **My Merit Badge Decks & Classroom Sessions Library Modal** and clicking `▾` opens a 1-click deck switcher, save, and clone menu even when the left sidebar is collapsed), the **`🤖 MCP Hub`** button opening the **MCP Server & Agent Hub Modal** (see **[MCP Server Integration Guide](MCP_SERVER_INTEGRATION_GUIDE.md)**), the **`📘 Documentation`** button (`#btn-open-docs-viewer`, shortcut `D`) opening the **In-App Markdown Documentation Viewer** (Option A: Dual-Mode Material 3 Documentation Studio Modal with `📘 User Guide` preselected, `🛡️ Admin Guide`, and `⚙️ Engineering Docs (10)` toggle across `12` docs), the **`?` Keyboard Shortcuts** button, direct links to the **Official BSA Pamphlet** and **Resource Guide**, the **`🪟 Presenter View`** button (`P`), the **Sticky Export Split-Button** (`📥 Download Slide Deck (.PPTX)` / `🟨 Open in Google Slides`), the **`📥 Export & Print ▾`** dropdown menu, and the **`☀️ Sunlight`** high-contrast outdoor mode toggle. |
| **Left Setup Sidebar** | Left column (`1. Find & Select Merit Badge` and `2. Deck Style & Counselor Info`) | Lets you choose or star (`⭐`) any of the 144 Merit Badges, switch the 3-mode Quick-Select bar (`🔥 Popular | ⭐ Favorites | 🗂️ Decks` with rich badge-emblem deck pills and `[💾 Save] [📑 Clone] [🗂️ Library]` actions), open the 144-Badge Visual Patch Gallery, pick a **PowerPoint Slide Template** (`17` built-in Scouting templates across `7` Style Families or upload/URL custom templates), set deck length and target Scout age group, inspect the `Visual Assets: 100% Pre-Cached (8-Bit PNG)` status badge, enter your local troop information, and click the sticky **Generate Slide Deck & Workbook** footer button. Collapse this sidebar anytime by clicking **Hide Setup** on the left side of the main tab bar. |
| **Blue Merit Badge Summary Banner** | Top of the right main stage | Shows the official Merit Badge patch emblem, whether the badge is **Eagle-Required** or **Elective**, the badge category, and three side-by-side summary boxes on the right: **TOTAL SLIDES**, **REQUIREMENTS**, and **SLIDE THEME** (`Warm Cream` with pre-bundled visuals). |
| **4 Main Workbench Tabs** | Directly below the blue summary banner | Switches the main workspace between:<br/>1. **Slide Deck Preview**<br/>2. **Requirements & Blue Card Sign-Off**<br/>3. **Scout & Counselor Workbook**<br/>4. **Lesson Plan, Gear List, Parent Letter & FinOps** |
| **Application Footer** | Bottom of the window (`#workbench-footer-banner`) | Displays creator credits, **LinkedIn Profile**, the **`GitHub`** repository link (`https://github.com/clayberg/scouts-bsa-merit-badge-agent`), feedback email, and the **`🔒 Admin`** Console link. |

> [!TIP]
> **Need More Screen Space for Your Projector?** Click **Hide Setup** on the far-left edge of the main tabs bar to fold away the left setup sidebar, and click **« Hide Outline** above the slide stage to fold away the slide list. Click **Show Setup** or **» Show Outline** whenever you want them back.

---

## 3. Step 1: Finding & Selecting a Merit Badge

In the upper-left card (**1. Find & Select Merit Badge**), you have five ways to locate the badge you are teaching:

| Control | How It Works | Practical Tip for Counselors |
| :--- | :--- | :--- |
| **Search Merit Badge Name** | Type any word (such as `First Aid`, `Weather`, `Canoeing`, `Robotics`, or `Citizenship`). | Narrows the dropdown list immediately as you type. |
| **Category** | Filter by Scouting subject area: *All Categories*, *Outdoor & Campcraft*, *Health & Public Safety*, *Citizenship & Personal Development*, *Nature & Environment*, *STEM & Science*, *Aquatics & Sports*, *Trades, Business & Careers*, or *Arts, Crafts & Hobbies*. | Helpful when planning a themed campout weekend (such as an Aquatics weekend or a STEM Merit Badge Midway). |
| **Eagle / Favorites (`#filter-eagle-select`)** | Choose **All Badges (144)**, **Eagle-Required (18)**, **Electives (126)**, or **★ Favorites**. | In the dropdown list, Eagle-Required badges are marked with a star (**★**). Choosing **★ Favorites** narrows the Merit Badge dropdown directly to your starred badges. |
| **1-Click `⭐` Favorite Star, Live Badge Emblem & 3-Mode Quick-Select Bar (`🔥 Popular \| ⭐ Favorites \| 🗂️ Decks`)** | Displays a live `17x17` Merit Badge patch emblem right beside the **Select Merit Badge** label (`#active-selected-badge-emblem`). Click the **`⭐`** button right next to the dropdown (or the inverted gold-circle **`★`** star in the top-right corner of any patch card in the gallery) to star/unstar a badge in SQLite (`counselor_favorites`) and `localStorage`. Switch the Quick-Select bar between **`🔥 Popular`** (8 top badges), **`⭐ Favorites`** (your starred badges), and **`🗂️ Decks`** (your saved deck sessions + `[💾 Save] [📑 Clone] [🗂️ Library]`). All three Quick-Select modes render `15x15` circular Merit Badge emblem icons on every pill (`m3-pill-badge-emblem`). | Lets counselors who teach 3 to 6 Merit Badges at troop meetings or summer camp access their personal badge lineup and saved patrol decks in one click with visual badge recognition across every tab. |
| **⚜️ Browse Visual Patch Gallery (144)** | Opens an interactive 144-badge visual patch grid modal (`#patch-gallery-modal`) displaying all 144 authentic `400x400` Scout Shop emblems (`assets/badge_emblems/`). Features a **Sticky Header** (`position: sticky; top: 0`) that keeps the search bar, **All / Eagle-Required / Electives** dropdown, **Header Favorites Filter Toggle (`★` button with `"Toggle favorites filter"` tooltip)**, **Category** filter, live badge count indicator (`144 / 144 badges`), and `✕` close button pinned at the top while you scroll through the grid. Every patch card displays an **Inverted Gold-Circle Star (`★` white star on `#D97706` amber-gold circle)** when favorited. | Click any Merit Badge patch card in the gallery to load that badge, or click the header **`★`** toggle button to filter the grid to only the badges you counsel. |

### Managing Multiple Merit Badge Decks & Patrol Sections (`🗂️ My Decks | ▾` & `Quick-Select -> 🗂️ Decks`)

Counselors who teach multiple Merit Badges at summer camp or run separate **Morning Patrol** and **Afternoon Patrol** sections of the same badge can manage all of their active decks in three consolidated places without taking up vertical space above the slide stage: the **Quick-Select `🗂️ Decks` tab** in the Left Setup Sidebar, the **Top-Bar `[🗂️ My Decks | ▾]` Split-Button**, and the **My Merit Badge Decks & Classroom Sessions Library Modal (`🗂️ My Decks`)**:

![Saved Decks & Sessions Library](images/ug_saved_workspaces_light.png)

![Saved Decks Library Dark Mode](images/ug_saved_workspaces_dark.png)

- **Dual-Tier Persistence (`scouts_bsa_sessions.db` + `localStorage`)**: Every saved deck workspace (`counselor_workspaces` table in SQLite) stores its full slide storyboard, custom slide edits, speaker notes, selected PowerPoint template, session label (such as `Period 1 - Morning Patrol`), Camp Week / Midway bundle tag (such as `Summer Camp Week 1`), and isolated **Patrol Blue Card (`#34124`)** Scout roster.
- **Clean New-Deck Defaults & Editable Preset Dropdowns**: When saving a brand-new deck (`💾 Save Current Deck to Library`), **Deck / Session Title** defaults cleanly to the Merit Badge name (such as `First Aid`) while **Class Section / Period** and **Camp Week / Midway Tag** start blank so you only add tags when needed. Both fields pair free-text inputs with illustrative preset dropdowns (for example, `Period 1 - Morning Patrol`, `Period 2 - Afternoon Patrol`, `Tuesday Troop Meeting`, or `Summer Camp Week 1`, `Council Merit Badge Midway`) so you can either pick a preset or type your own label.
- **`<80ms` Hot-Swapping via `Quick-Select -> 🗂️ Decks` & Top-Bar `[🗂️ My Decks | ▾]`**: Switch to the **`🗂️ Decks`** tab under **Quick-Select Badges** in the left sidebar (which renders rich badge-emblem pills with Scout roster counts plus a compact **`[💾 Save] [📑 Clone] [🗂️ Library]`** action strip), or click the **`▾`** caret on the Top App Bar **`[🗂️ My Decks | ▾]`** split-button when the setup sidebar is hidden, to switch your slide stage, workbook, and Blue Card roster in under `80ms` without re-running the AI pipeline.
- **`📑 Clone for New Section` (Morning vs. Afternoon Patrols)**: Click **`📑 Clone`** in the Quick-Select `🗂️ Decks` strip, in the Top-Bar `🗂️ My Decks ▾` menu, or on any card in the library modal to copy all three metadata fields (**Deck Title**, **Class Section / Period**, and **Camp Week / Midway Tag**) along with your customized slides, templates, and speaker notes into a fresh workspace with an empty Blue Card roster for your next class period.
- **Delete Confirmation Dialog (`Don't ask again`)**: Clicking **`🗑️`** on a saved deck opens a confirmation dialog with a **`Don't ask again`** checkbox (`localStorage`) to prevent accidental deletion of active class decks.
- **Portable `.bsadeck.json` Backup Export & Import**: Click **`📤 Export .bsadeck.json`** on any workspace card to save a portable JSON backup file to your laptop, or click **`📥 Import .bsadeck.json`** in the modal header to restore a saved deck and Blue Card roster on another machine.

---

## 4. Step 2: Choosing Your Deck Style & Saving Your Counselor Profile

In the lower-left card (**2. Deck Style & Counselor Info**), you control how detailed the presentation should be, which Scout age group you are teaching, and what local troop information should appear on the cover slide and handouts.

### Choosing Deck Depth, Unified Warm Cream Visual Theme & Audience Age

![Workbench Visual & Teaching Showcase](images/slide-polish-tiers-comparison.png)

| Setting | Options Available | When to Use Each Option |
| :--- | :--- | :--- |
| **Slide Deck Length & Depth** | • **Deep Dive Teaching Deck (3 to 8 Slides / Req • 30 to 100+ Slides)**<br/>• **Standard Troop Meeting Deck (1 to 4 Slides / Req • 18 to 48 Slides)** | Choose **Deep Dive** for multi-week troop classes, summer camp blocks, or Merit Badge Universities where you want dedicated slides for every sub-requirement (`1a`, `1b`, `2a`), worked examples, and review quizzes. Choose **Standard** for a compact overview deck. |
| **PowerPoint Slide Template & Branding (`🎨 Template Studio`)** | • **17 Built-In Council-Neutral Scouting America & Heritage Templates Organized Across 7 Style Families (`Option A` Naming)**:<br/>  - *0. Workbench Default*: `Workbench Classic` (`default_workbench`)<br/>  - *1. Brushed Banner Series*: `BSA Scouting America (Green)`, `BSA Scouting America (Blue)`, `BSA Scouting America (Red)`<br/>  - *2. Horizon Silhouette Series*: `BSA Outdoor Adventure (Blue)`, `BSA Outdoor Adventure (Green)`, `BSA Outdoor Adventure (Red)`<br/>  - *3. Forest Sunrise & Camp Series*: `BSA Forest Sunrise (Blue)`, `BSA Forest Sunrise (Green)`, `BSA Forest Sunrise (Red)`<br/>  - *4. Topographic Contour Series*: `BSA Topographic (Blue)`, `BSA Topographic (Green)`, `BSA Topographic (Tan)`<br/>  - *5. Fleur-de-Lis Crest Series*: `BSA Fleur-de-Lis Crest (Red)`, `BSA Fleur-de-Lis Crest (Blue)`<br/>  - *6. Special & Action Editions*: `BSA America 250™`, `BSA High Adventure`<br/>• **Custom Upload, URL Import & Edit/Delete**: Upload `.pptx`, `.ppt`, `.png`, `.jpg`, or `.webp` (`POST /api/v1/templates/upload`), import by URL (`POST /api/v1/templates/import-url`), edit custom template Name/Description (`PATCH /api/v1/templates/{template_id}`), or delete custom templates (`DELETE /api/v1/templates/{template_id}`) | Applies decorative header/footer banners, outdoor horizon silhouettes, corner medallions, auto-contrasted luminance footer text, and responsive `SafeCanvasBounds` (`content_bottom_max_in <= 6.86"` / `6.88"` / `6.82"` clamping so teaching cards and the `🛡️ Guide to Safe Scouting` bar sit right above footer bars or corner logos with zero gap or overlap). Works orthogonally with **`WARM_CREAM`** (`CREAM`, `#FAF8F5`), **`CRISP_WHITE`** (`WHITE`, `#FFFFFF`), and **`DARK_SLATE`** (`SLATE`, `#0F172A`). |
| **Unified Warm Cream (`WARM_CREAM` / `#FAF8F5`) Rich Visual Slide Theme** | • **Sidebar Status Badge**: `Visual Assets: 100% Pre-Cached (8-Bit PNG)` *(`$0.00` runtime image cost; `~$0.18` cold LLM / `$0.00` cached)*<br/>• **Per-Slide Overrides (Drawer Tab 2)**: 6 Card Styles & 5 Brand Palettes (including `MATCH_TEMPLATE`) | Every deck uses a warm editorial cream canvas (`WARM_CREAM`, `#FAF8F5`) with colored `1.5pt` card accent borders and pre-bundled visuals from all **3,917 built-in curated assets** (`1,306` 8-bit PNG Nano Banana requirement heroes, topic illustrations, and scientific diagrams + `2,323` Vision-verified BSA Pamphlet figures + `144` emblems + `144` covers). You can customize any individual slide's **Card Style** or **Brand Palette** in Drawer Tab 2, and REST/MCP/Python API callers can specify `WARM_CREAM` (`CREAM`), `CRISP_WHITE` (`WHITE`), or `DARK_SLATE` (`SLATE`) (with legacy enum aliases `BEAUTIFIED`, `STANDARD`, and `STUDIO` retained for backward compatibility). |
| **Target Scout Audience Level** | • **All Scouts (Ages 11 to 17)**<br/>• **First-Year / Tenderfoot Focus (Ages 11 to 12)**<br/>• **Older Scouts / Eagle Prep (Ages 14 to 17)** | Adjusts the counselor speaker notes (`[SAY]`, `[DEMONSTRATE]`, `[ASK SCOUTS]`) so your explanations and check questions fit either younger crossovers or older Scouts preparing for Eagle Boards of Review. |
| **Enable Local Regional Grounding (NOAA / Terrain / Field Sites)** | Checked by default | Tailors your **Badge Overview slide (Slide 2)**, **Session Lesson Plan**, and **Parent Welcome Letter** to your local area, referencing your nearest National Weather Service office, current state U.S. Senators (for civic badges), local terrain hazards, and nearby parks or field study sites. |

### PowerPoint Template & Custom Slide Theme Studio (`[🖼️ Template Name | ▾]`)

Click **`🎨 Template Studio`** in the left sidebar or use the **Split-Button Template Switcher (`[🖼️ Template Name | ▾]`)** in the stage toolbar: clicking the main button opens the **PowerPoint Template & Theme Studio Modal**, while clicking the right **`▾`** caret opens a compact Style Family dropdown menu with inline **1-Click Color Swatch Pills (`[🟢 Green] [🔵 Blue] [🔴 Red]`)** right on each family row:

![PowerPoint Template Studio](images/ug_template_studio_light.png)

![Template Studio Dark Mode](images/ug_template_studio_dark.png)

- **17 Curated Scouting Templates Organized into Style Family Cards (`#template-catalog-grid`)**: Multi-variant template families (*Brushed Banner Series*, *Horizon Silhouette Series*, *Forest Sunrise & Camp Series*, *Topographic Contour Series*, and *Fleur-de-Lis Crest Series*) display an interactive **Color Variant Swatch Bar (`[🟢 Green] [🔵 Blue] [🔴 Red]`)** directly underneath the 16:9 miniature preview. Clicking any color pill updates the card preview and applies that template variant to your active deck in one click.
- **True Responsive Slide Geometry & Auto-Contrasted Footer Text**: When you apply a branded template with a bottom footer bar, horizon silhouette, or corner logo, both the live 16:9 web stage (`#widescreen-slide-stage`) and the exported `.pptx` presentation automatically lift instructional cards and the **`🛡️ Guide to Safe Scouting`** warning banner cleanly above the reserved bottom zone (`y <= 6.86"` / `6.82"`), shift the footer attribution text clear of the left or right logo, and auto-select crisp white (`#FFFFFF`) text on dark navy/forest/crimson footer bars or dark slate (`#0F172A`) text on light footer bars.
- **Tab 2 (`📤 Upload Custom Template (.PPTX / Image)`) & Custom Template Edit/Delete**: Upload your own `.pptx`, `.ppt`, `.png`, `.jpg`, or `.webp` slide template (`POST /api/v1/templates/upload`). User-added templates display a **`✏️` pencil icon** (`PATCH /api/v1/templates/{template_id}`) to edit the template's Name and Description in place and a **`🗑️` delete icon** (`DELETE /api/v1/templates/{template_id}`) that removes the template and automatically reverts the active deck to **`Workbench Classic`** (`default_workbench`).
- **Tab 3 (`🌐 Import Template from URL`)**: Paste a direct link to a `.pptx` or background image (`POST /api/v1/templates/import-url`) to register it in your template catalog.
- **Redesigned 3-Box Anatomical Safe-Zone X-Ray (`📐 Preview Safe-Zone X-Ray`)**: Toggle the Safe-Zone X-Ray switch in the modal header to inspect a clear 3-zone anatomical diagram overlaid on the 16:9 preview: **Zone 1 (`Header Reserve`)**, **Zone 2 (`Active Pedagogical Content & Safety Safe-Box` with live dimension and delta badge)**, and **Zone 3 (`Template Footer & Protected Corner Logo Zone`)**.

### Saving Your Counselor & Troop Profile

Click **👤 Counselor & Troop Profile (Saved) • Edit ▾** at the bottom of the left sidebar to open your contact fields:
- **Counselor Name**: Printed on your Cover Slide (Slide 1), Parent Welcome Letter, and Blue Card Sign-Off Sheet (for example, `Scoutmaster Bob`).
- **Troop & Council Affiliation**: Your unit and council name (for example, `Troop 19, Spirit of Adventure Council`).
- **Location (City, State or ZIP Code)**: Enter your town or 5-digit ZIP code (such as `Middleton, MA` or `01949`) so local weather, terrain hazards, and field study locations match your troop's home area.
- **Contact Email & Contact Phone (Optional)**: Displayed in the counselor contact box on Slide 1 and in your Parent Welcome Letter so Scouts (copying a parent or guardian under Youth Protection rules) know how to reach you.
- **Optional Troop Custom Logo (`.png` / `.jpg`)**: Upload your troop numeral patch, patrol medallion, or council shoulder strip to display it in the lower-left counselor block on Slide 1.
- **↺ Reset Info**: Clears your saved profile and restores the default sample values anytime.

---

## 5. Step 3: Watching the Scout Slide Construction Showcase

![Three Scout Slide Construction Animations](images/construction-animations-triptych.png)

Whenever a new Merit Badge deck is being assembled, or anytime you click **Merit Badge Construction Animation** in the **Research & Generation Progress** card in the left outline column, the Workbench displays an interactive **Scout Slide Construction Showcase** featuring your selected Merit Badge emblem:

1. **🏗️ 1. 3D Heavy Equipment (6f)**: Miniature Scouts in campaign hats and construction hardhats use a yellow mini-bulldozer, tower crane, forklift, scissor-lift, and twin-rotor cargo helicopter to erect a giant 16:9 slide and hoist your Merit Badge patch into the upper-right mounting ring. On Frame 4 (`iso_heavy_4_helicopter_emblem.jpg`), a transparent foreground hoist cable and golden mounting ring eyelet (`iso_heavy_4_foreground_cable.png`) render in front of the badge patch so the helicopter cable physically holds the emblem from above.
2. **🪵 2. 2D Camp Pioneering (4f)**: A patrol at a pine forest campsite ties square and diagonal lashings on timber spars and uses an A-frame block-and-tackle pulley rig to hoist a canvas projection screen framed with your Merit Badge emblem.
3. **⚙️ 3. 3D Slide-O-Matic (4f)**: Stop-motion clay Scouts inside a log-cabin workshop feed Merit Badge pamphlets into a brass-and-oak *"Slide-O-Matic"* contraption before cutting a ceremonial red ribbon.

You can switch between the three animations using the top buttons, step backward or forward through individual frames with the **`◀`**, **`⏸`**, and **`▶`** controls in the bottom-right corner of the canvas, or click **✨ View Finished Slides** to return to your presentation.

---

## 6. Step 4: Previewing, Presenting, Timing & Switching Slide Images

When **Slide Deck Preview** (Tab 1) is active, you have fast controls for navigating slides, switching visuals, timing your class, and projecting to a patrol:

### 1. Single-Row Slide Outline Filter, Active-Slide Micro-Pills (`➕`, `👁️`, `↑`, `↓`) & Unified `[🛠️ Tools ▾]` Menu (Left Column of Tab 1)
- At the top of the **Slide Filmstrip Outline** (`#filmstrip-toolbar`), the **`🔎 Filter slides or req...`** search box and the unified **`[🛠️ Tools ▾]`** dropdown button sit side-by-side on a single horizontal row (`36px` total header height, giving the slide outline extra vertical room).
- Type a requirement number (such as `2b` or `4a`) or a topic word (such as `CPR`, `tourniquet`, or `splint`) into **🔎 Filter slides or req...** to narrow the slide list immediately.
- **Inline Active-Slide Customizer Micro-Pills (`➕`, `👁️`, `↑`, `↓`) with Immediate (`0ms`) Visual Updates & Debounced Net-Zero `.PPTX` Sync**:
  - In the lower-right corner of the **active slide** in the Slide Filmstrip Outline (`.m3-thumb-customizer-cluster`), four compact circular micro-pill buttons appear with hover tooltips:
    * **`➕`** (*Insert a custom local camp or troop slide right after this slide*)
    * **`👁️`** (*Hide this slide from the presentation & exported .PPTX* or *Unhide this slide so it is included in the presentation*)
    * **`↑`** (*Move active slide earlier in the deck*)
    * **`↓`** (*Move active slide later in the deck*)
  - Clicking **`↑`**, **`↓`**, or **`👁️`** updates the slide position or hidden state **immediately (`0ms`)** in the outline and on the stage so you can click **`↑`** or **`↓`** several times in a row without waiting.
  - Background `.pptx` regeneration is debounced (`1200ms` window after your last click). If you toggle **`👁️` Hide** and then **`👁️` Unhide** (or move a slide up and back down) within the debounce window so that the net deck change is zero, the background `.pptx` rebuild is automatically skipped (`computeStoryboardDeckSignature`).
- Click **`[🛠️ Tools ▾]`** (`#btn-stage-tools-menu-toggle`) to access three grouped sections in one menu (clicking `↑`, `↓`, or `👁️ Hide Slide` inside the menu also keeps the popover open for repeated clicks):
  1. **Filter Slide Outline**: Toggle **`⚡ Quiz Slides Only`** (`#btn-filter-quiz-slides`) or **`🏠 Hide Home-Prereqs`** (`#btn-toggle-hide-prereq-slides`). Whenever a filter is active, the button highlights in amber and displays a live count badge (**`🛠️ Tools • 1 ▾`**).
  2. **Slide Deck Customizer**: Click **`➕ Insert Slide`** to insert a custom local camp slide right after the active slide, **`👁️ Hide Slide` / `👁️ Unhide Slide`** to toggle visibility of the current slide, or **`↑` / `↓`** to reorder slides.
  3. **Classroom Quiz & Patrol Game**: Toggle **`🎯 Quiz Reveal: Off`** or open the **`🏆 Patrol Scoreboard`**.
- Each card in the **Slide Filmstrip Outline** also displays a **`32x32` miniature visual thumbnail**, a color-coded visual source badge (`[🍌 Hero]`, `[📘 Pamphlet]`, `[📊 Diagram]`, `[📁 Custom]`, or `[📝 Text]`), and a **`🖼️ 1/2`** multi-choice count badge.

### 2. Single Above-Stage Toolbar & Interactive Requirement Jump Dropdown (`[📍 Overview ▾]` / `[📍 Req X ▾]`)
- To maximize vertical space for the 16:9 slide canvas, all above-stage controls are consolidated into a **single `42px` Stage Toolbar (`#slide-stage-toolbar`)**.
- Directly to the right of **`Next ▶`** (`Slide X / Y`), the active requirement indicator (**`[📍 Cover ▾]`**, **`[📍 Overview ▾]`**, or **`[📍 Req 2b ▾]`**, `#btn-stage-req-jump-toggle`) serves as both your live location badge and a **1-Click Requirement Quick-Jump Dropdown (`#req-jump-dropdown-menu`)**.
- Clicking **`[📍 Overview ▾]`** opens a 2-column popover grid listing **Cover Slide**, **Overview**, and every requirement (**Req 1** through **Req 15**) with slide ranges and an active **`✓`** checkmark. Clicking any requirement jumps straight to its introductory slide and automatically scrolls the left **Slide Filmstrip Outline** to center the active slide card.

### 3. Easy Slide Image Switcher (On-Stage Visual Pill & Popover)
- Look at the source pill above the image on the right side of the 16:9 slide stage:
  - When a slide has a single visual (such as a Requirement Intro slide with one Nano Banana hero illustration), the pill shows a static label (`🍌 NANO BANANA AI ILLUSTRATION`).
  - When a slide has multiple visual choices (such as the primary pamphlet figure plus up to 2 Gemini Vision-verified BSA pamphlet alternates for that requirement, or custom images you uploaded for that slide), the pill shows **`◀`** and **`▶`** arrows and a **`(1/3) ▾`** counter.
  - Click **`◀`** or **`▶`** (or press **`[`** and **`]`** on your keyboard) to switch between the slide's image options in one click, or click **`(1/3) ▾`** to open a popover showing each option's thumbnail, role label (`Primary Pamphlet Figure`, `Pamphlet Alternate #1`, `Pamphlet Alternate #2`), and Vision-verified caption. Picking any option updates the slide image, its caption, and your `[SAY]` / `[DEMONSTRATE]` teaching script right away and rebuilds your `.pptx` file in the background at `$0.00` cost. You can also click **`+ Upload / Add Custom Image for This Slide...`** at the bottom of the popover to open the 4-Tab Image Studio.

### 4. Centered Split-Screen Presenter View (`P`), Non-Disruptive `↗ 2nd Monitor` Window, Fullscreen Teleprompter (`N`), Classroom Timer & Patrol Scoreboard (`Space`)
- **🪟 Centered Split-Screen Presenter View (`🪟 Presenter View` or press `P`)**: Clicking **`🪟 Presenter View`** (or pressing **`P`**) in either normal preview mode or Fullscreen mode (`F`) opens the **Split-Screen Presenter Console** (`#stage-presenter-console-dock`) centered side-by-side with the 16:9 slide stage:
  - **Compact Header Bar**: Displays a gold **`PRESENTER VIEW`** badge and clickable cyan **`MM:SS`** session timer on the left, plus **`A−`** / **`A+`** teleprompter font-scaling buttons, **`↗ 2nd Monitor`**, and a red-tinted **`✕`** close button on the right.
  - **Top `"Up Next"` Preview Card**: Full-width card right below the header showing `UP NEXT • SLIDE X OF Y`, the next slide's full title, and a **`⏱ ~2 min`** pacing badge.
  - **Full-Width Slide Switcher Buttons**: Equal-width **`◀ Prev Slide`** and **`Next Slide ▶`** buttons directly below the Up Next card.
  - **3 Separate Color-Coded Teleprompter Cards**: Renders **`🗣️ [SAY]`** in a royal-blue card, **`🛠️ [DEMONSTRATE]`** in an amber card, and **`❓ [ASK SCOUTS]`** (with its **`✓ Expected Answer:`** callout) in an emerald card, with rendered **`**bold**`** emphasis and highlighted `🎬 [Stage Cues]`.
- **↗ Non-Disruptive `↗ 2nd Monitor` Floating Teleprompter Window**: Teaching with a projector or dual display? Click **`↗ 2nd Monitor`** inside the Presenter Console header to open a synchronized floating speaker-notes window (`scouts_bsa_presenter_sync_v1`, positioned on your secondary screen via `window.getScreenDetails()` or screen offsets). Opening the 2nd-monitor window automatically hides the in-stage right-hand dock and keeps the main browser window in **centered Fullscreen presentation mode** so your Scouts only ever see the centered 16:9 slide.
- **🖥️ Centered Present Fullscreen (`🖥️ Present Fullscreen` or press `F`) & Teleprompter Notes (`🎙️ Notes (N)`)**: Expands the 16:9 slide canvas centered on widescreen and ultrawide monitors with a floating bottom control bar (**◀ Prev**, **Next ▶**, **🎙️ Notes (N)**, **✕ Exit Fullscreen**). Clicking **`🎙️ Notes (N)`** (or pressing **`N`**) slides up a semi-transparent bottom teleprompter drawer displaying your **`[SAY]` / `[DEMONSTRATE]` / `[ASK SCOUTS]`** script right inside Fullscreen mode, or press **`P`** in Fullscreen for the centered side-by-side Presenter Console.
- **🖥️ Unified `[🖥️ Present | ▾]` Split-Button & Collapsible Live Classroom Timer (`Option TP1`)**: On the right side of the stage toolbar, clicking the main **`🖥️ Present`** button launches **Centered Fullscreen Mode (`F`)** immediately, while clicking the **`▾`** caret (`#btn-stage-present-caret`) opens the **Presentation, Session Timer & Classroom Engagement Popover (`#stage-present-dropdown-menu`)** containing:
  - **Presentation Modes**: `🖥️ Present Fullscreen (F)` and `🪟 Split-Screen Presenter View (P)`.
  - **Classroom Session Timer (`#session-timer-cluster`)**: Preset selector (`45m Troop`, `30m Fast`, `60m Camp`, `90m Midway`, `10m Drill`), digital readout (`45:00`), `▶` Start/Pause, and `↺` Reset. While the timer is idle at its default preset, it stays tucked inside the `▾` menu so the stage toolbar remains uncluttered; the moment you start the countdown (or pause it mid-session), a **Live Countdown Pill (`⏱️ 44:59 ⏸`, `#stage-live-timer-badge`)** appears automatically on the stage toolbar next to `🖥️ Present` (turning amber at 5 minutes remaining and crimson at 1 minute remaining, and clicking it pauses/resumes in 1 click).
  - **Live Patrol Engagement**: Quick toggles for **`🎯 Quiz Reveal Mode`** and the **`🏆 Patrol Scoreboard`**.
- **❓ Interactive Quiz Reveal Mode (`Q`), `Space` Bar Reveal & 🏆 Patrol Scoreboard**: On Socratic Checkpoint & Scenario slides (or whenever **Hide Quiz Answers (Scout Mode)** is checked), pressing the **`Space`** bar (or clicking a masked quiz card or the **`👁️ Reveal Answer & Coaching Tip (Space)`** button) reveals the counselor answer key and coaching tip on the spot, paired with an interactive **🏆 Patrol Scoreboard** (`🦅 Eagle`, `🦊 Fox`, `🐺 Wolf`, `🐻 Bear` with `+1` / `-1` / `↺ Reset` buttons) so patrols can compete during checkpoint reviews.
- **`?` Keyboard Shortcuts Cheat-Sheet Modal**: Click **`?`** in the top bar (or press `?` on your keyboard) to view all stage and image shortcuts:

| Key | Action |
| :--- | :--- |
| **`←` / `→`** | Previous / Next slide |
| **`Space`** | Reveal / hide quiz answer on Socratic Checkpoint slides (or when Scout Quiz Mode is active) |
| **`[` / `]`** | Cycle previous / next image choice in the Easy Slide Image Switcher |
| **`F`** | Toggle Centered Fullscreen classroom projector mode |
| **`N`** | Toggle Fullscreen Teleprompter Notes Drawer (`[SAY]` / `[DEMO]` / `[ASK]`) |
| **`P`** | Toggle Centered Split-Screen Presenter View (in Preview or Fullscreen) + `↗ 2nd Monitor` |
| **`Q`** | Toggle Quiz Answer Hide/Reveal mode (`Scout Mode`) |
| **`D`** | Open / close the In-App Markdown Documentation Viewer (`📘 User Guide`, `🛡️ Admin Guide`, & `⚙️ Engineering Docs (10)` across `12` docs) |
| **`?`** | Open Keyboard Shortcuts Cheat-Sheet modal |
| **`Esc`** | Close active popover, modal, or Fullscreen view |

---

## 7. Step 5: Customizing Individual Slides, Layouts, Graphics & Text

Directly below the 16:9 slide stage sits the **3-Tab Under-Stage Drawer**, which gives you everything you need to teach or customize the active slide without scrolling down a long page:

```mermaid
flowchart TD
    Drawer["Under-Stage Drawer<br/>(Directly Below the 16:9 Slide Stage)"] --> Tab1["🎙️ Tab 1: Counselor Teaching Notes<br/>([SAY], [DEMONSTRATE], [ASK SCOUTS])"]
    Drawer --> Tab2["🎨 Tab 2: Customize Slide & Image Studio<br/>(10 SVG Layout Cards, Theme, Palette & Graphic)"]
    Drawer --> Tab3["✏️ Tab 3: Quick Edit Slide Text<br/>(Edit Title, Caption, Cards & Notes in Place)"]
    Tab2 --> Modal["🖼️ Manage & Add Slide Images Button<br/>(Opens 4-Tab Popup Image Studio)"]
    Modal --> M1["🗂️ 1. Badge Image Catalog & Carousel"]
    Modal --> M2["🌐 2. Web Image Search Agent"]
    Modal --> M3["🍌 3. Nano Banana AI Image Generator"]
    Modal --> M4["📁 4. File Upload"]
```

![Under-Stage Co-Design Bar, Popup Image Studio & Quick Text Editor](images/codesign-and-image-studio.png)

### Drawer Tab 1: `🎙️ Counselor Teaching Notes ([SAY] / [DEMO] / [ASK])` & FinOps Cost Gate
Displays your ready-to-speak **EDGE Method** script for the current slide, compiled on the fly (`<5ms` per deck) directly from the slide's teaching cards, official requirement text, and active visual caption:
- **`[SAY]`**: A conversational first-person speaking script that teaches the actual material on the slide and includes highlighted inline stage directions (`🎬 [Point to Card 1: ...]`, `🎬 [Gesture to the right-hand figure: ...]`, `🎬 [Pause for hands]`).
- **`[DEMONSTRATE]`**: Included selectively when the slide calls for a hands-on skill demonstration, gear inspection, worked-example walkthrough, or diagram trace.
- **`[ASK SCOUTS]`**: A specific patrol or field check question followed by a highlighted **`✓ Expected Answer:`** key so you have the exact BSA pamphlet answer in front of you.
- **`✨ AI Polish Slide`, `✨ Polish Entire Deck` & FinOps Cost Transparency Gate Modal (`#ai-polish-finops-modal`)**:
  - Clicking **`✨ AI Polish Slide`** (`POST /api/v1/slide/polish-notes`) or **`✨ Polish Entire Deck`** (`POST /api/v1/slide/polish-notes-batch`) opens the **FinOps Cost Transparency Gate Modal** (`POST /api/v1/slide/estimate-polish-cost`) comparing two side-by-side options:
    1. **Option 1: Current Slide Only (`~$0.0008` on `gemini-2.5-flash`)** displayed in a soft lavender card (`#FAF5FF`).
    2. **Option 2: Entire Deck (`~$0.068` for an 82-slide deck)** displayed in a warm amber card (`#FFFBEB`).
  - **Session Controls & Cache Bypass**: Check **`Force fresh Gemini Flash generation even for slides already cached in SQLite`** if you want to bypass cached scripts (`$0.00` cache hits), or check **`Don't show this FinOps cost popup again during this browser session`** (`sessionStorage`) for 1-click polishing during the rest of your session.
  - **Single-Row Action Pills, Live `[1/82]` Progress & `↺ Restore Default`**: Click **`✨ Polish This Slide (~$0.0008)`** or **`✨ Polish All 82 Slides (~$0.068)`** to generate warm, teacher-style coaching scripts with rendered **`**bold**`** emphasis (and live **`⏳ Polishing [1/82]...`** batch progress). Polished slides display an **`✨ AI-Polished (Gemini 2.5 Flash)`** provenance badge, sync into your downloadable `.pptx` file, and include a **`↺ Restore Default`** button alongside **`📋 Copy Script`**. Whenever you switch a slide's image or edit its cards, the teaching script updates automatically to match.

### Drawer Tab 2: `🎨 Customize Slide & Image Studio`
Lets you change the layout, colors, or illustration on the active slide and automatically rebuilds your downloadable `.pptx` file:

| Control | Options Available | What It Does |
| :--- | :--- | :--- |
| **1. Slide Layout (10 Clickable SVG Mini-Wireframe Cards)** | • *Split + Visual* (`SPLIT_VISUAL_EXPLAINER`)<br/>• *2x2 Step Grid* (`PROCESS_STEP_GRID`)<br/>• *2-Col Compare* (`TWO_COLUMN_COMPARISON`)<br/>• *Checklist (`[✓]`)* (`SAFETY_CHECKLIST_GRID`)<br/>• *3-Col Triage* (`REQUIREMENT_TRIAGE_MATRIX`)<br/>• *Worked Example* (`WORKED_EXAMPLE_CARD`)<br/>• *Patrol Quiz* (`SOCRATIC_CHECKPOINT`)<br/>• *Full-Width Text* (`CONCEPT_TEXT_SLIDE`)<br/>• *Large Diagram* (`FULL_BLEED_IMAGE_EXPLAINER`)<br/>• *Req Intro* (`REQUIREMENT_INTRO_BANNER`) | Click any visual mini-wireframe card (or select from the dropdown) to rearrange how the teaching cards and right-side visual are positioned on the current slide. |
| **2. Card Style (Magazine Theme)** | • *Numbered Step Badges (01, 02, 03)*<br/>• *Bento Accent Cards (Top Color Bar ◆)*<br/>• *Editorial Callout Cards (Warm Gold ❝)*<br/>• *High-Contrast Dark Slate Cards (★)*<br/>• *Timeline Sequence Cards (STEP 1 ➔)*<br/>• *Safety Warning Highlight (Crimson ⚠️)* | Changes the visual style, numbered badges, and accent borders of the teaching cards on the slide. |
| **3. Brand Palette** | • *Scouts Navy & Eagle Gold*<br/>• *Outdoor Olive & Forest Green*<br/>• *Eagle Crimson & Navy*<br/>• *Executive Slate & Action Blue* | Updates the color scheme of the header bar and card borders on the active slide. |
| **4. Right-Side Graphic** | • *Keep Current Slide Graphic*<br/>• *Restore Original Slide Graphic*<br/>• *🍌 Nano Banana Hero Graphic (or EDGE Concept Map)*<br/>• *None (Remove Graphic & Expand Text to Full Width)* | Controls the right-hand picture. Choosing **None** removes the picture and expands your teaching cards across the full width of the slide; choosing **Restore Original Slide Graphic** brings back the default diagram or pamphlet figure. |
| **✨ Apply to Slide** | Primary action button | Applies your selected Layout, Card Style, Brand Palette, and Right-Side Graphic to the slide and updates the `.pptx` download. |

### Using the 4-Tab Popup Image Studio (`🖼️ Manage & Add Slide Images`)
Click **🖼️ Manage & Add Slide Images (Catalog / Web / AI)** in the upper-right corner of the **Customize Slide & Image Studio** bar to open the popup Image Studio window:

1. **🗂️ 1. Badge Image Catalog & Carousel**:
   - Shows thumbnail cards for every image saved for the current Merit Badge (including official BSA pamphlet figures, requirement hero illustrations, diagrams, web search photos, and your own uploaded pictures).
   - Click **✅ Use on Slide** on any card to place that graphic onto your current slide.
   - Click **🗑️ Clear Web/AI Cache** in the upper right if you want to remove extra web-searched or custom AI-generated images while keeping all official pamphlet figures, default requirement hero graphics, and your own uploaded photos.
2. **🌐 2. Web Image Search Agent**:
   - Type a topic (such as `splint forearm`, `cumulonimbus cloud`, or `square lashing`) and click **🔎 Search Web & Commons** to search Wikimedia Commons for free educational photographs and diagrams (`$0.00` cost).
   - Click **Use on Slide** on any result to save it to the badge catalog and place it on the current slide.
3. **🍌 3. Nano Banana AI Image Generator**:
   - Creates a custom illustration tailored to your slide:
     - **1. Visual Illustration Style**: Choose **✨ Auto (Content-Aware Mix)** to let the tool pick the best style for the slide topic, or choose a specific style (*Photorealistic Image*, *4-Quadrant Concept Map*, *Line Drawing*, *Watercolor Field Sketch*, *Technical Diagram*, *3D Isometric Illustration*, *Editorial Vector Illustration*, *Cartoon Drawing*, or *Vintage Merit Badge Poster*).
     - **2. Human Presence & Uniform Directive**: Choose **✨ Auto-Detect**, **👕 Include Humans (Adult Scouts BSA Uniforms)**, or **🧰 No Humans (Pure Equipment / Environment)**, or toggle the **Include Uniformed Scouts** checkbox.
     - **3. Visual Scene Description**: Edit or refine the scene description you want illustrated.
   - Check the **`$0.08 USD`** cost consent box and click **🍌 Generate, Verify & Apply Custom AI Graphic (`$0.08 USD`)**.
4. **📁 4. File Upload**:
   - Click **1. Select Local Image File (PNG, JPG, WEBP, GIF)** to pick a photo from your own computer (such as a photo from a troop campout or your own training prop), enter an optional title and description, and click **📁 Upload, Cache & Apply Local Image to Slide (`$0.00 USD`)**.

### Drawer Tab 3: `✏️ Quick Edit Slide Text`
Want to tweak a slide title, reword a bullet card, or add a personal story to your speaker notes?
1. Click **✏️ Quick Edit Slide Text** below the slide stage.
2. Edit any of the four boxes:
   - **Slide Title**
   - **Visual Caption (Right Graphic)**
   - **Slide Teaching Cards (One card per line: use "Heading: Body text")**
   - **Counselor Teaching Script (`[SAY]`, `[DEMONSTRATE]`, `[ASK SCOUTS]`)**
3. Click **💾 Save Slide Edits & Rebuild .PPTX**. Your live slide preview and your downloadable PowerPoint deck update in less than a second at zero cost.

---

## 8. Step 6: Tracking Requirements & Signing Off Blue Cards (`#34124`)

Click the second main tab at the top of the screen (**Requirements & Blue Card Sign-Off**) to view how every official requirement is taught and to track Scout sign-offs during class.

![Requirements Triage, Bulk Blue Card Roster & 4-Sub-Tab Classroom Toolkit](images/counselor-field-toolkit.png)

### 3-Column Requirements Triage & Header Action Buttons
At the top of the **Official BSA Merit Badge Pamphlet & Digital Resource Guides** card, three single-line action buttons let you jump directly to **`↓ Blue Card Tracker`**, open the **`Official BSA Pamphlet (PDF)`**, or open the **`Scouting.org Resource Guide`**. Directly below, every official requirement for the badge is sorted into one of three practical teaching columns:
- **Discussion & Core Knowledge**: Requirements you can cover through interactive patrol discussion, visual explainers, and Socratic Q&A.
- **Hands-On Skill Demonstrations**: Physical skills where each Scout must *demonstrate*, *build*, *treat*, or *perform* a task at a practice station.
- **Campout, Field & Home Projects**: Prerequisites, multi-week logs, field visits, or campout tasks that Scouts must complete outside of a regular troop classroom meeting.

Every requirement card lists the **exact official BSA requirement text**, the recommended **EDGE Method phase**, the **Counselor Sign-Off Criteria**, any **Youth Protection or Guide to Safe Scouting reminders**, and a **▶ Jump to Teaching Slides** button that takes you straight to that requirement's slides.

### Patrol Blue Card (`#34124`) & Scoutbook Plus Requirement Sign-Off Tracker
Below the requirement columns sits an interactive roster table saved automatically in your browser for each Merit Badge:
1. **Add Scouts Individually, Copy From Another Saved Deck (`🔁 Copy Scouts From Deck`), Bulk Paste, or Import `.CSV`**:
   - Type a Scout's name (for example, `Alex Carter - Eagle Patrol`) into the box and click **➕ Add Scout** (or press `Enter`).
   - Click **`🔁 Copy Scouts From Deck`** to copy the Scout roster (names, units, and patrols with fresh unchecked requirement boxes) from any of your other saved Merit Badge deck workspaces in **`🗂️ My Decks`**.
   - Click **📋 Bulk Paste Roster** to paste an entire patrol or class list from a spreadsheet (one Scout per line, such as `Name, Patrol / Unit`).
   - Or click **📤 Import CSV** to upload a standard `.csv` roster exported from **Scoutbook Plus** or **TroopWebHost** (`Scout Name`, `BSA Member ID`, `Unit`, `Patrol`, and existing requirement checkmarks).
2. **Check Off Completed Requirements, Bulk Sign Off Columns & Stamp Dates**:
   - As each Scout demonstrates mastery of a requirement (`1`, `2a`, `2b`, `3`, ...), check the box in their row.
   - Click any **Requirement Column Header (`1 ✓`, `2a ✓`, ...)** to toggle that requirement for the entire patrol in one click after a group demonstration.
   - Pick a date in the **📅 Completion Date** field and click **Stamp Checked** to record the completion date across all checked cells (included automatically in your Scoutbook CSV export and printed Sign-Off Sheet).
3. **Automatic `Partial` vs. `Complete` Blue Card Status**: The **Blue Card Status** column automatically shows `Partial (X/Y)` in amber while a Scout is still working, and switches to `Complete (Y/Y)` in green once all requirements are checked. You can also click **All ✓** in the **Quick** column to check or uncheck an entire row at once.
4. **Export Scoutbook CSV, Print Patrol Sheet, or Print 3-Panel Blue Cards (`#34124`)**:
   - Click **📥 Export Scoutbook CSV** to download a `.csv` spreadsheet listing every Scout, unit, requirement status, completion date, and counselor name for easy entry into **Scoutbook Plus** or troop advancement records.
   - Click **🖨️ Print Sign-Off Sheet** to open a clean, printable **Application for Merit Badge (`#34124`) Patrol Sign-Off Record** complete with a Counselor signature and date line.
   - Click **🪪 Print 3-Panel Blue Cards (#34124)** to generate printable 3-column tri-fold Blue Cards (*Applicant's Record*, *Application for Merit Badge*, and *Counselor's Record*) pre-populated with each Scout's name, unit, completed requirement initials/dates, and your counselor signature block.

---

## 9. Step 7: Using the Workbook, 4-Tab Classroom Toolkit, Cue Cards & Station Rotator

### Top Tab 3: `Scout & Counselor Workbook` (with Section Filter Pills)
Click **Scout & Counselor Workbook** to preview the complete printable workbook for the active Merit Badge:
- Use the sticky **Section Filter Bar** at the top of the workbook card (**`All Sections`**, **`Checklist Table`**, **`Requirement Notes`**, and **`Instructor Guide`**) to jump straight to the section you want to review or print.
- Use the action buttons in the upper right of the card:
  - **📋 Copy Text**: Copies the entire workbook to your clipboard.
  - **🖨️ Print / Save PDF**: Opens a clean, black-and-white print view formatted for standard `8.5" x 11"` paper or **Save as PDF**.
  - **🖨️ Print 3x5 Pocket Cue Cards**: Generates a 2x2 printable grid of `3x5` counselor index cards containing each requirement's number, verbatim summary, **`[SAY]`**, **`[DEMONSTRATE]`**, and **`[ASK SCOUTS]`** prompts so you can teach outdoors at camp without carrying a laptop.

### Top Tab 4: `Lesson Plan, Gear List, Parent Letter & FinOps` (Organized into 4 Sub-Tabs)
Click **Lesson Plan, Gear List, Parent Letter & FinOps** to access your classroom preparation toolkit, organized into four focused sub-tabs so you never have to scroll down a long page:

| Sub-Tab | Key Controls & Options | How Counselors Use It |
| :--- | :--- | :--- |
| **🗓️ 1. Agenda & Station Rotations** | • **🗓️ Session Schedule Format** dropdown:<br/>  1. *3 Troop Meetings (45 min each)*<br/>  2. *Summer Camp Week (4x 50-min Mon-Thu + Fri Make-Up)*<br/>  3. *Saturday Merit Badge Midway / Clinic (3-Hour Block)*<br/>  4. *Weekend Campout Practicum (Fri Eve + Sat Field + Sun Sign-Off)*<br/>• **🔄 Patrol Skill Station Rotator Matrix** (`2`, `3`, or `4` Patrols; `15`, `20`, or `25` min/station)<br/>• **🖨️ Print 3x5 Pocket Cue Cards** button | Regroups the badge requirements into a timed, minute-by-minute teaching plan, builds a **Round-Robin Patrol Skill Station Rotation Schedule** across all `HANDS_ON_SKILL_STATION` requirements so patrols never bottleneck on the same equipment, and prints pocket cue cards. |
| **🎒 2. Quartermaster Gear & Pre-Class Check** | • **🏕️ Class / Patrol Size** dropdown (*1 Scout*, *4 Scouts*, *8 Scouts*, or *16 Scouts*)<br/>• **📋 Pre-Class Prerequisite Readiness Checklist** (`PREREQUISITE_CAMPOUT_HOME` table + **🖨️ Print Prerequisite Check Sheet**)<br/>• Interactive checkboxes, **📋 Copy Packing List**, and **🖨️ Print Checklist** | Multiplies physical prop and supply quantities based on your class size, and builds a Day-1 **Prerequisite Readiness Check Sheet** listing every home log, multi-week chart, or campout task Scouts must bring to class before receiving full Blue Card sign-off. |
| **✉️ 3. Parent Welcome Letter (YPT)** | • **📋 Copy**, **✉️ Draft in Email App**, **📨 Compose in Gmail**, **🖨️ Print**, and **📥 .MD** | Generates a ready-to-send welcome letter for parents, guardians, and Scoutmasters listing prerequisites to finish before class, what gear to bring, local field study context, and **Scouting America Youth Protection (Two-Deep Leadership / no one-on-one digital contact)** reminders. |
| **📊 4. Citations, FinOps & Rating** | • **`↓ Counselor Rating`** jump button in the header of **Grounded Research Citations & Local Troop References**<br/>• **FinOps Cost & Token Budget (`$1.00 Max Cap`)**<br/>• **Counselor Sign-Off & Continuous Learning Flywheel** (`1` to `5` stars + **✅ Requirement Accuracy Verified**) | Lists the official BSA pamphlet and authoritative public references (NOAA, USGS, NPS, American Red Cross), displays the estimated generation cost and cache savings, and lets you jump straight to or submit your counselor quality rating. |

---

## 10. Exporting Your Slide Deck to PowerPoint (`.PPTX`) or Direct Google Slides

In the Top Application Bar (and inside **`📥 Export & Print ▾`**), the Workbench provides a **Sticky Export Split-Button** (`scouts_bsa_preferred_deck_export_mode_v1` in `localStorage`) that remembers your preferred slide deck format across sessions:
- **Mode 1: `📥 Download Slide Deck (.PPTX)` (Default)**: Downloads a widescreen (`16:9`) PowerPoint presentation named `<Badge>_<PolishMode>_<Depth>_Merit_Badge_Deck.pptx` where every title, teaching card, caption, and speaker note is a native editable text box.
- **Mode 2: `🟨 Open in Google Slides` (Account & Destination Modal `#gslides-export-modal` + Direct Google Drive Conversion via `POST /api/v1/slide/export-gslides`)**:
  - Clicking **`🟨 Open in Google Slides`** opens the **Account & Destination Modal (`#gslides-export-modal`)**, which queries `GET /api/v1/slide/export-gslides/account-info` and displays two cards:
    1. **Card 1 (`1. Active Workstation Google Drive Account`)**: Displays your active workstation Google Drive account (`clayberg@google.com` in bold alongside a green `GOOGLE DRIVE CLI + ADC` or `CLOUD DRIVE ADC` badge).
    2. **Card 2 (`2. Share / Open with Personal Gmail or Secondary Account (Optional)`)**: Lets you enter a personal `@gmail.com` or secondary Google account (`#gslides-share-email-input`) so the exported deck automatically grants Editor permissions and appends `?authuser=<email>` when opening the new tab.
  - **Bottom Modal Actions**: Click **`🔑 Pick Google Account (OAuth)`** (`#btn-gslides-pick-google-account`) to pick a Google account via Google Identity Services OAuth (`drive.file`) or Google's Account Chooser, or click **`🟨 Create & Open in New Tab ↗`** (`#btn-gslides-create-and-open-tab`) to convert your `.pptx` into a native Google Slides presentation (`mimeType: application/vnd.google-apps.presentation`) and open `https://docs.google.com/presentation/d/<id>/edit` in a new browser tab.
- Click the **`▾`** caret on the right edge of the split-button anytime to switch your default export action between **`.PPTX`** and **Google Slides**.
- Also in **`📥 Export & Print ▾`**, clicking **`📱 Print 1-Page Field & QR Handout`** opens a printable 1-page pocket reference featuring **standard-compliant, phone-camera-scannable ISO/IEC 18004 QR codes** (`/api/v1/qr.svg`) that resolve directly to the official BSA Merit Badge Pamphlet PDF (`filestore.scouting.org`) and the Scouting.org Digital Resource Guide.

### Opening in Microsoft PowerPoint or Apple Keynote
1. Double-click the downloaded `.pptx` file on your laptop.
2. Switch to **Presenter View** during class so your Scouts see the 16:9 visual slides on the projector while you read the **`[SAY]` / `[DEMONSTRATE]` / `[ASK SCOUTS]`** teaching script on your laptop screen.

### Importing into Google Slides for Google Drive Sharing
1. Open [Google Slides](https://slides.google.com) or your troop's shared Google Drive folder.
2. Click **File -> Import slides** (or **File -> Open -> Upload**) and drag in your downloaded `.pptx` file.
3. Click **View -> Show speaker notes** to see your EDGE teaching script below each slide, or click **Slideshow -> Presenter view** when teaching.

### Connecting AI Assistants via the Built-In MCP Server (`🤖 MCP Hub`)

Click **`🤖 MCP Hub`** in the Top Application Bar to open the **MCP Server & Agent Hub Modal**:

![MCP Server & Agent Hub](images/ug_mcp_hub_light.png)

![MCP Hub Dark Mode](images/ug_mcp_hub_dark.png)

- **1-Click Client Configs**: Copy ready-to-use configuration snippets for **Claude Desktop**, **Gemini CLI / AGY**, **Cursor**, or **Google ADK `MCPToolset`** using either local `stdio` (`python -m src.mcp_server` / `scouts-bsa-mcp`) or HTTP (`POST /mcp`, `GET /mcp/info`, `GET /mcp/sse`).
- **12 MCP Tools, 6 `bsa://` Resources & 4 Guided Prompts**: External AI agents can search badges, query official pamphlets via Hybrid BM25 + Vector RRF, build slide decks with any of the 8 PowerPoint templates and modern visual themes (`WARM_CREAM`, `CRISP_WHITE`, `DARK_SLATE`), switch slide visuals, manage Patrol Blue Card (`#34124`) rosters, and run `<10ms` Stage-1 AABB conformance audits. In Section 2 of the modal, every `bsa://` resource card includes **`▶ Read Live`** and **`📋 Copy URI`** buttons, and every guided prompt card includes **`▶ Execute Prompt`** and **`📋 Copy Prompt`** buttons (guided prompts also appear as `/` slash commands in Claude Desktop, Gemini CLI / AGY, and Cursor).
- **Full-Height Interactive MCP Playground (`[📊 Visual Card Preview | { } Raw JSON-RPC 2.0]`)**: Section 3 of the modal lets you execute all **22 MCP capabilities** (**12 Tools**, **6 `bsa://` Resources**, and **4 Guided Prompts**) live in your browser and toggle between human-friendly **Visual Card Previews** and **Raw JSON-RPC 2.0** envelopes with a live RPC latency/status pill. For full protocol details, read the **[MCP Server Integration Guide (`docs/MCP_SERVER_INTEGRATION_GUIDE.md`)](MCP_SERVER_INTEGRATION_GUIDE.md)**.

---

## 11. Frequently Asked Questions for Counselors

### Can I use the Workbench at summer camp where Wi-Fi is spotty or unavailable?
Yes. All 144 Merit Badge requirement outlines and all **3,917 built-in curated visual assets** (**2,323 100%-Vision-verified BSA Pamphlet figures** [`1,009` primary active + `1,314` requirement alternates], **1,306 pre-generated Nano Banana requirement hero & topic illustrations**, **144 badge emblems**, and **144 pamphlet covers**) are stored locally when running on your laptop (`1.5 to 3.5s` offline build speed). Any Merit Badge decks, pamphlets, or extra images you generate before camp stay saved on your machine for instant offline use.

### How do I remove an image from a slide if I just want larger text cards?
Select the slide in **Slide Deck Preview**, click the second tab below the slide (**🎨 Customize Slide & Image Studio**), change **4. Right-Side Graphic** to **None (Remove Graphic & Expand Text to Full Width)**, and click **✨ Apply to Slide**. The picture is removed and the text cards expand across the full width of the slide.

### How do I switch a slide back to its original diagram or pamphlet illustration?
In **🎨 Customize Slide & Image Studio**, set **4. Right-Side Graphic** to **Restore Original Slide Graphic** and click **✨ Apply to Slide**.

### How do I add my own troop photos to a slide?
Click **🎨 Customize Slide & Image Studio** below the slide stage, click **🖼️ Manage & Add Slide Images (Catalog / Web / AI)** in the upper-right corner, select the fourth tab (**📁 4. File Upload**), pick any `.png`, `.jpg`, `.webp`, or `.gif` photo from your computer, and click **📁 Upload, Cache & Apply Local Image to Slide (`$0.00 USD`)**.

### Is my contact information kept private?
Yes. Your Counselor Name, Troop, Location/ZIP, Email, and Phone are saved locally in your browser (and in a private local cache file when running on your own laptop) so you don't have to retype them. They are placed directly onto your Cover Slide, Parent Welcome Letter, and Blue Card Sign-Off Sheet, and are never shared with outside services or telemetry logs.
