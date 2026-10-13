# ⚜️ Scouts BSA Merit Badge Counselor Workbench: Detailed User Guide

Welcome to the **Scouts BSA Merit Badge Counselor Workbench** (`v2.6`). This guide walks through every workspace panel, slide customization tool, and printable field resource available to Merit Badge Counselors, summer camp instructors, and troop advancement leaders.

---

## 1. Workspace Overview & 3-Column Layout

When you open the Counselor Workbench (`http://localhost:8080`), the interface is organized into three coordinated zones designed to maximize the **16:9 widescreen slide stage** on standard laptop and classroom displays:

![Scouts BSA Merit Badge Counselor Workbench Overview](images/workbench-overview-layout.png)

1. **Left Setup Sidebar (`1. Select Merit Badge` & `2. Deck Style & Counselor Info`)**:
   - Browse or search all **144 official Scouts BSA Merit Badges** (`18` Eagle-Required and `126` Electives, plus `2` synthetic test stubs when validation mode is enabled).
   - Filter by category pills: *All*, *Eagle-Required*, *Outdoor & Backcountry*, *Aquatics & Paddle*, *STEM & Digital*, *Civics & Business*, *Arts, Crafts & Trades*, or *Sports & Shooting*.
   - Configure your **Deck Depth**, **Slide Polish Tier**, **Target Scout Audience Level**, **Construction Animation Theme**, and **Counselor & Troop Profile**.
   - Click **Hide Setup** in the top bar at any time to collapse the left sidebar and give more horizontal room to the slide stage.
2. **Center Slide Deck Outline (`Slide Deck Outline (Click to Jump)`)**:
   - Displays every slide in the generated deck (`45-85+` slides in *Deep Dive / Camp School* mode or `16-28` slides in *Troop Meeting* mode) with requirement badges and archetype tags.
   - Includes a live **Filter slides by title or Req #** search box and can be collapsed via **Hide Outline** in the stage toolbar.
3. **Right Widescreen Stage, Co-Design Studio & 5-Tab Counselor Toolkit Drawer**:
   - Top **Hero Banner** displays the official Merit Badge emblem, Eagle-Required status, total slide count, requirement count, and visual asset cache status (`100% Pre-Cached 8-Bit PNG`).
   - **Requirement Quick-Jump Bar** lets you jump directly to `Cover`, `Triage`, `Req 1`..`Req 15`, or `Sources` with a single click.
   - **16:9 Slide Preview Canvas** renders the exact typography, rounded cards, layered top/left accent bars, upper-right transparent Merit Badge emblem, and visual framing that will be exported to `.pptx` and Google Slides.

---

## 2. Configuring Your Deck Style & Counselor Profile

### Deck Depth Modes
- **Deep Dive / Camp School Deck (`45-85+` Slides)**: Generates a complete multi-slide instructional module for every requirement and sub-requirement (`1a`, `1b`, `2a`..), including a *Requirement Intro* slide with verbatim Scouting America requirement text followed by dedicated *Topic Explainer*, *Step-by-Step Procedure*, and *Full-Page Diagram* slides. Ideal for summer camp trail schools, multi-session troop classes, and thorough study.
- **Troop Meeting Deck (`16-28` Slides)**: Condenses each top-level requirement into 1 to 2 high-impact overview slides for a fast single-evening patrol introduction.

### Visual Polish Tiers (`100%` Pre-Cached Visuals Across All 144 Badges)
All **144 official Merit Badges** ship with **2,292 pre-generated, compressed (`<= 1,024px`, 8-bit PNG) Nano Banana hero and topic illustrations** (`assets/ai_illustrations/`) and **4,316 extracted, de-boxed official BSA Pamphlet figures** (`assets/pamphlet_images/`). Choosing a polish tier incurs **`$0.00` in runtime image generation fees**:

![Slide Polish Tiers Comparison](images/slide-polish-tiers-comparison.png)

| Polish Tier | Canvas Background | Card & Visual Styling | Typical Token Cost |
| :--- | :--- | :--- | :--- |
| **Standard Lightweight (`STANDARD`)** | Crisp White (`#FFFFFF`) | High-contrast ink-friendly cards paired with official BSA pamphlet figures. | `~$0.04` USD (`$0.00` image cost) |
| **AI Beautified (`BEAUTIFIED`)** | Warm Cream (`#FAF8F5`) | Rotating 4-palette rounded cards (`Navy & Gold`, `Forest & Sage`, `Crimson & Ember`, `Slate & Cyan`) + full pre-cached Nano Banana hero and topic visuals. | `~$0.08` USD (`$0.00` image cost) |
| **AI Studio (`STUDIO`)** | Dark Slate (`#0F172A`) | Deep slate auditorium theme with luminous card borders and full pre-cached Nano Banana hero and topic visuals. | `~$0.14` USD (`$0.00` image cost) |

### High-Resolution Scientific Diagrams & Clean Scene-Specific Captions
- Complex technical diagrams (such as the NOAA Hydrologic Cycle, WSR-88D Doppler Radar reflectivity, Cold and Warm Front cross-sections, 3D Warm Front side-by-side profile, Daytime Sea Breeze vs. Nighttime Land Breeze, Cloud Classification by Altitude Level, and top-cropped Earth's 23.5° Axial Tilt and Seasons) are rendered at high resolution with crisp, legible labels and zero cropped or duplicate headings.
- Every visual card displays a concise, scene-specific caption describing the actual diagram or procedure shown, with zero robotic `"Official BSA Pamphlet"` or style-name prefixes.

### Counselor Profile & Local Grounding (`location_or_zip`)
Expand the **Counselor & Troop Profile** accordion (or click the counselor chip in the top bar) to enter:
- **Counselor Name** (e.g., `Eric Clayberg`)
- **Troop & Council** (e.g., `Troop 19, Middleton MA`)
- **Location (City, State or ZIP Code)** (e.g., `01949` or `Middleton, MA`): Grounds Slide 2 (Curriculum Overview), the Session Pacing Agenda, and the Prerequisite Parent Letter with your local National Weather Service forecast office (such as `NWS Boston/Norton (BOX)`), local emergency contacts, and regional field trip venues.
- **Contact Email & Phone**: Rendered on the Cover Slide and pre-filled into the Prerequisite Parent Letter.
- **Optional Troop Custom Logo**: Upload a PNG/JPG/WebP troop patch or council emblem to display on the Cover Slide alongside the Merit Badge emblem and official pamphlet cover.

---

## 3. Whimsical Scout Slide-Construction Animation

While the multi-agent pipeline researches and builds your deck, the 16:9 stage displays an interactive **Scout Slide-Construction Storyboard** with live progress steps and your selected Merit Badge emblem dynamically mounted in the upper-right ring of the slide under construction:

![Scout Slide Construction Animations](images/construction-animations-triptych.png)

- **1. 3D Heavy Equipment (6 Frames)**: Miniature uniformed Scouts in yellow hardhats use a bulldozer, tower crane, forklift, twin-rotor cargo helicopter, and paintbrushes to erect the 16:9 slide.
- **2. 2D Camp Pioneering (4 Frames)**: Scouts use pine timber spars, square lashings, and an A-frame block-and-tackle pulley at a forest campsite to hoist the canvas slide screen.
- **3. 3D Claymation Workshop (4 Frames)**: Stop-motion clay Scouts operate a brass-and-oak *"Slide-O-Matic"* contraption to stamp cards and project illustrations onto the slide board.

---

## 4. Per-Slide Co-Design Bar & 4-Tab Merit Badge Image Studio

Below the 16:9 slide stage, the **Per-Slide Interactive Co-Design Bar** lets you refine any individual slide without regenerating the entire deck:

![Per-Slide Co-Design and 4-Tab Image Studio](images/codesign-and-image-studio.png)

### Quick Slide Text Editor
Click **Edit Slide Text** to modify the current slide's **Title** or **Bullet Points / Card Items** (one bullet per line, using `Heading: Explanation` to bold card titles). Click **Save Text Changes** to update both the live HTML5 preview and the downloadable `.pptx` deck immediately.

### Layout, Card Style & Palette Switchers
- **Slide Layout**: Switch between `Keep Current Layout`, `Split Text + Visual Explainer`, `3-Column Concept Cards`, `Full-Bleed Diagram Spotlight`, `2-Column Comparison`, or `Process Flow Diagram`.
- **Card Style**: Choose `Modern Rounded Cards`, `Numbered Step Cards (01-04)`, `Warning / Safety Callout Cards`, or `Checklist Cards`.
- **Color Palette**: Switch the slide's accent palette between `Navy & Gold`, `Forest & Sage`, `Crimson & Ember`, or `Slate & Cyan`.
- **Right-Side Graphic**: Choose `Keep Current Graphic`, `Remove Graphic (Expand Text Full-Width)`, or `Restore Original Slide Graphic`.

### 4-Tab Merit Badge Image Studio
Click **Open 4-Tab Image Studio** to customize the visual on the active slide:
1. **Tab 1: Cached Library (`$0.00` Instant)**: Browse all pre-cached Nano Banana hero/topic illustrations (`2,292` across all `144` badges) and extracted official pamphlet figures (`4,316` de-boxed PNGs) for the current badge and click **Apply to Slide**.
2. **Tab 2: Web Image Search (`$0.00` Wikimedia Commons)**: Search public educational diagrams and photographs via `WebImageSearchAgent` and apply any result with one click.
3. **Tab 3: Nano Banana AI Generator (`$0.08` USD FinOps Consent Gate)**:
   - Choose a visual style (*Auto Content-Aware Mix*, *4-Quadrant Concept Map*, *Photorealistic Image*, *Line Drawing*, *Cartoon Drawing*, or *Technical Diagram*) and whether to **Include Uniformed Scouts**.
   - Edit the pre-populated visual prompt and click **Generate Custom AI Image**.
   - A **FinOps Consent Dialog** confirms the `$0.08` USD estimated cost before calling Vertex AI Imagen / Gemini. Every generated image is automatically checked for prompt alignment (`verify_generated_image_matches_prompt`) and saved to your local badge catalog.
4. **Tab 4: File Upload (`$0.00` Local Photo/Diagram)**: Upload your own troop campout photo, local trail map, or custom diagram (`.png`, `.jpg`, `.webp`) directly onto the slide.

---

## 5. Counselor Field Toolkit (`5-Tab Under-Stage Drawer`)

Below the Co-Design Studio, the **5-Tab Under-Stage Drawer** keeps all teaching and administrative tools organized without vertical page clutter:

![Counselor Field Toolkit](images/counselor-field-toolkit.png)

1. **Tab 1: Teaching Notes (BSA EDGE Script)**:
   - Displays slide-specific **[SAY]** lecture scripts (more detailed than the slide cards), **[DEMONSTRATE]** physical prop instructions, and **[ASK SCOUTS]** discussion questions tailored to your selected Scout age group.
2. **Tab 2: Coverage & QA (`QualityReviewerAgent` & Feedback Flywheel)**:
   - Shows the **Stage 1 (`<10ms`) Deterministic Geometry Conformance** badge (`0` AABB overlaps, `100%` citation grounding, minimum font size check), FinOps session telemetry, and the **Counselor Sign-Off & Continuous Learning Flywheel** card (`POST /api/v1/feedback`), which promotes verified 4-5 star runs into the Golden Evaluation Dataset.
3. **Tab 3: Teaching Plan & Blue Card (`#34124`) Matrix**:
   - Lists every requirement with its execution-mode triage badge (*Discussion*, *Hands-On Skill*, or *Campout/Home Prerequisite*) and a **Jump to Slide** button.
   - Includes the interactive **Patrol Blue Card (`#34124`) & Scoutbook Plus Sign-Off Matrix**: add Scout rows (stored locally in your browser), check off completed requirements, and click **Export Scoutbook CSV**.
4. **Tab 4: StudioKit Docs (Session Pacing Agenda, Parent Letter & Quartermaster Gear List)**:
   - **Multi-Format Session Pacing Selector**: Switch live between *3 Troop Meetings (60-Min)*, *Summer Camp Week (4x50-Min Mon-Thu + Fri Sign-Off)*, *Saturday Merit Badge Clinic (3-Hr Block)*, and *Weekend Campout Practicum*.
   - **Prerequisite Parent/Guardian Letter**: Ready to send via **Copy**, **Draft in Email App**, **Compose in Gmail**, **Print / Save PDF**, or **Download `.md`**.
   - **Master Quartermaster Gear & Materials Checklist**: Scales quantities automatically across `1x (Single Demo)`, `2x (1 Patrol)`, `3x (2 Patrols)`, or `4x (Full Troop)`.
5. **Tab 5: Scout Workbook & Counselor Guide**:
   - View, copy, print, or download the complete **Scout Fill-in-the-Blank Workbook** and **Counselor Teaching Guide** in Markdown or print-ready format.

---

## 6. Exporting to PowerPoint (`.pptx`) & Google Slides

- Click **Download `.pptx`** in the top bar (or inside the Slide Deck Outline header) to download the widescreen (`13.333" x 7.5"`) PowerPoint presentation.
- **Importing into Google Slides**:
  1. Upload the `.pptx` file to Google Drive or open Google Slides and choose **File -> Import slides**.
  2. Every slide uses standard cross-platform typography (`Calibri` / `Arial`), explicit character budgets (`_concise_card_body`), and layered DrawingML card accents (`CardAccent_Top_*`, `CardAccent_Left_*`, `CardAccent_StepPill_*`) so cards never overflow or bleed outside their borders in Google Slides.
  3. All slide-by-slide `[SAY]`, `[DEMONSTRATE]`, and `[ASK SCOUTS]` counselor notes are embedded directly in the PowerPoint / Google Slides **Speaker Notes** pane.
