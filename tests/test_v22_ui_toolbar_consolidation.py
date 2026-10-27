"""v2.2 Track C — Frontend UI/UX Decluttering & Dropdown Consolidation tests.

Verifies Section 3.2 of v22_speaker_notes_pii_ux_and_workbook_plan.md:
  1. Consolidation 1: Global Top Navigation Bar (#help-tools-split-group & unified #pptx-export-split-group)
  2. Consolidation 2: Tab 2 (Requirements & Blue Cards) single-row toolbar & 3 split-button menus
  3. Consolidation 3: Tab 3 (Scout Workbook) 3-segment view switcher & #workbook-download-split-group
  4. Consolidation 4: Tab 4 (Class Prep & Letters) #studiokit-handouts-split-group, #agenda-actions-split-group, #letter-actions-split-group
  5. Consolidation 5: Left Sidebar deduplicated category select, compact hero toggle, Under-Stage Drawer #speaker-notes-polish-split-group, and Guided Tour auto-open for .m3-split-dropdown-menu
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_HTML = ROOT / "ui" / "index.html"
UI_CSS = ROOT / "ui" / "styles.css"
UI_JS = ROOT / "ui" / "app.js"


def test_consolidation_1_top_navigation_bar_split_dropdowns() -> None:
    """Consolidation 1: Top bar consolidates Help/Tools and Export/Print into split-button dropdowns."""
    html = UI_HTML.read_text(encoding="utf-8")

    # Help & Developer Tools split group
    assert 'id="help-tools-split-group"' in html
    assert 'id="btn-open-docs-viewer"' in html
    assert 'id="btn-open-docs-hub"' in html
    assert 'id="btn-help-tools-caret"' in html
    assert 'id="help-tools-menu"' in html
    assert 'id="btn-open-mcp-hub"' in html
    assert 'id="btn-toggle-mcp"' in html
    assert 'id="btn-keyboard-shortcuts"' in html
    assert 'id="btn-start-guided-tour"' in html

    # Unified Deck Export & Print split group with section headers
    assert 'id="pptx-export-split-group"' in html
    assert 'id="deck-export-split-group"' in html
    assert "Slide Deck Formats" in html
    assert "Scout Workbooks &amp; Handouts" in html or "Scout Workbooks & Handouts" in html
    assert "Advancement &amp; Blue Cards" in html or "Advancement & Blue Cards" in html
    for expected_id in (
        "btn-download-pptx",
        "btn-deck-export-caret",
        "menu-export-mode-pptx",
        "menu-export-mode-gslides",
        "btn-header-print-deck",
        "btn-header-export-html",
        "btn-download-workbook-top",
        "btn-top-print-workbook",
        "btn-top-print-field-qr-handout",
        "btn-top-print-cue-cards",
        "btn-top-print-3panel-bluecards",
        "btn-top-export-bluecard-csv",
    ):
        assert f'id="{expected_id}"' in html, f"Missing expected ID #{expected_id} in top bar export menu"


def test_consolidation_2_bluecard_single_row_toolbar_and_split_menus() -> None:
    """Consolidation 2: Tab 2 Blue Card Tracker uses a single-row toolbar with 3 split-button menus."""
    html = UI_HTML.read_text(encoding="utf-8")

    assert 'class="m3-bluecard-toolbar-row"' in html
    for split_group_id in (
        "bluecard-import-split-group",
        "bluecard-batch-split-group",
        "bluecard-export-split-group",
    ):
        assert f'id="{split_group_id}"' in html

    # Verify all existing and v2.2 IDs in the Blue Card toolbar remain intact
    for control_id in (
        "bluecard-scout-name-input",
        "bluecard-scout-troop-input",
        "btn-bluecard-add-scout",
        "btn-add-bluecard-scout",
        "bluecard-troop-filter-select",
        "bluecard-global-date-input",
        "bluecard-signoff-date",
        "btn-bluecard-import-csv",
        "btn-import-bluecard-csv",
        "bluecard-csv-file-input",
        "btn-bluecard-bulk-paste",
        "btn-bulk-paste-roster",
        "btn-copy-roster-from-deck",
        "select-bluecard-copy-workspace",
        "btn-bluecard-mark-inclass",
        "btn-check-all-inclass-bluecard",
        "bluecard-batch-session-select",
        "bluecard-session-stamp-select",
        "btn-bluecard-stamp-session",
        "btn-apply-batch-session-stamp",
        "btn-bluecard-print-3panel",
        "btn-print-official-3panel-bluecards",
        "btn-bluecard-open-ypt-composer",
        "btn-open-ypt-email-modal",
        "btn-bluecard-export-csv",
        "btn-export-scoutbook-csv",
        "btn-bluecard-export-troop-packets",
        "btn-export-per-troop-packets",
        "btn-bluecard-print",
        "btn-print-bluecard-sheet",
    ):
        assert f'id="{control_id}"' in html, f"Missing Blue Card toolbar ID #{control_id}"


def test_consolidation_3_workbook_segmented_switcher_and_split_download() -> None:
    """Consolidation 3: Tab 3 Scout Workbook uses a 3-segment view switcher and split download menu."""
    html = UI_HTML.read_text(encoding="utf-8")

    assert 'class="workbook-view-segmented-control"' in html
    for view_btn_id in (
        "btn-workbook-view-default",
        "btn-workbook-open-fillable-html",
        "btn-open-fillable-scout-workbook",
        "btn-workbook-open-cpp",
        "btn-open-class-prep-cpp",
    ):
        assert f'id="{view_btn_id}"' in html

    assert 'id="workbook-download-split-group"' in html
    assert 'id="workbook-download-menu"' in html
    for dl_id in (
        "btn-workbook-download-fillable-pdf",
        "btn-fillable-scout-workbook-pdf",
        "btn-class-prep-cpp-pdf",
        "btn-download-workbook",
        "btn-download-workbook-md",
        "btn-print-workbook",
        "btn-workbook-print-field-qr",
        "btn-print-field-qr-handout",
        "btn-print-cue-cards",
        "btn-copy-workbook",
        "btn-copy-workbook-md",
        "workbook-markdown-body",
        "workbook-markdown-preview",
    ):
        assert f'id="{dl_id}"' in html, f"Missing Workbook control ID #{dl_id}"


def test_consolidation_4_studiokit_handouts_agenda_and_letter_split_menus() -> None:
    """Consolidation 4: Tab 4 Class Prep & Letters uses split dropdowns for handouts, agenda, and parent letter."""
    html = UI_HTML.read_text(encoding="utf-8")

    for group_id in (
        "studiokit-handouts-split-group",
        "agenda-actions-split-group",
        "letter-actions-split-group",
        "studiokit-subpanel-agenda",
        "studiokit-subpanel-letter",
    ):
        assert f'id="{group_id}"' in html

    for stage_btn_id in ("letter-stage-1-btn", "letter-stage-2-btn", "letter-stage-3-btn"):
        assert f'id="{stage_btn_id}"' in html

    for action_id in (
        "btn-studiokit-fillable-workbook",
        "btn-studiokit-open-fillable-workbook",
        "btn-studiokit-organizer-spec",
        "btn-studiokit-open-organizer-spec",
        "btn-studiokit-gear-rotator-pdf",
        "btn-print-agenda",
        "btn-download-agenda-md",
        "btn-copy-agenda",
        "btn-copy-agenda-md",
        "btn-gmail-letter",
        "btn-mailto-letter",
        "btn-mailto-parent-letter",
        "btn-download-letter-pdf",
        "btn-download-letter-md",
        "btn-copy-letter",
        "btn-copy-letter-md",
    ):
        assert f'id="{action_id}"' in html, f"Missing StudioKit control ID #{action_id}"


def test_consolidation_5_sidebar_deduplication_understage_and_css_js_wiring() -> None:
    """Consolidation 5: Deduplicated category select, compact hero toggle, Under-Stage polish split group, CSS & JS."""
    html = UI_HTML.read_text(encoding="utf-8")
    css = UI_CSS.read_text(encoding="utf-8")
    js = UI_JS.read_text(encoding="utf-8")

    # 1. Category select deduplication in HTML
    cat_select_match = re.search(
        r'<select[^>]*id="filter-category-select"[^>]*>(.*?)</select>',
        html,
        re.DOTALL,
    )
    assert cat_select_match is not None
    cat_options_html = cat_select_match.group(1)
    assert "TEST_LAB" not in cat_options_html
    assert "MULTI_OPTION" not in cat_options_html

    eagle_select_match = re.search(
        r'<select[^>]*id="filter-eagle-select"[^>]*>(.*?)</select>',
        html,
        re.DOTALL,
    )
    assert eagle_select_match is not None
    eagle_options_html = eagle_select_match.group(1)
    assert "TEST_LAB" in eagle_options_html
    assert "MULTI_OPTION" in eagle_options_html

    # 2. Compact hero banner toggle & Under-Stage speaker notes polish split group
    assert 'id="btn-toggle-hero-banner"' in html
    assert 'id="hero-guided-tour-dropdown"' in html
    assert 'id="gallery-filtered-count-badge"' in html
    assert 'id="speaker-notes-polish-split-group"' in html
    assert 'id="btn-ai-polish-notes"' in html
    assert 'id="btn-polish-slide-notes"' in html
    assert 'id="btn-ai-polish-deck"' in html
    assert 'id="btn-polish-all-notes"' in html
    assert 'id="btn-restore-default-notes"' in html
    assert 'id="btn-restore-slide-notes"' in html

    # 3. CSS classes for split dropdowns, section labels, segmented control, and compact hero
    for selector in (
        ".m3-split-btn-group",
        ".m3-split-dropdown-menu",
        ".m3-split-dropdown-menu.open",
        ".m3-menu-section-label",
        ".workbook-view-segmented-control",
        "body.deck-loaded-compact-hero .m3-hero-banner",
    ):
        assert selector in css, f"Missing CSS selector {selector} in ui/styles.css"

    # Zero transition: all in ui/styles.css
    assert not re.search(r"transition:\s*all\b", css)

    # 4. JS split-button caret handler and Guided Tour auto-open for .m3-split-dropdown-menu
    assert ".m3-split-btn-caret" in js
    assert ".m3-split-dropdown-menu" in js
    assert "deck-loaded-compact-hero" in js


def test_items_1_to_6_multimedia_drawer_logistics_slides_footer_compact_hero_and_mcp_sync() -> None:
    """Items 1-6: Multimedia drawer children, logistics slides + start time/location, 2-line footer, compact hero, and 27-capability MCP copy."""
    html = UI_HTML.read_text(encoding="utf-8")
    css = UI_CSS.read_text(encoding="utf-8")
    js = UI_JS.read_text(encoding="utf-8")

    # Item 1: #slide-multimedia-drawer-body populated with 4 child elements
    for mm_id in (
        "slide-multimedia-drawer",
        "slide-multimedia-drawer-body",
        "drawer-pamphlet-citation-chip",
        "drawer-workbook-citation-chip",
        "drawer-gate-badges-wrap",
        "slide-multimedia-links-list",
        "slide-gate-badges-inline",
    ):
        assert f'id="{mm_id}"' in html, f"Missing multimedia drawer element #{mm_id}"
    assert "formatUiWorkbookOrganizerLabel" in js

    # Item 2 & 6: Logistics drawer + Workspace Classroom Session Time, Location & Logistics Slides panel
    for log_id in (
        "input-logistics-time",
        "input-logistics-room",
        "input-logistics-sessions",
        "btn-apply-logistics-slides",
        "btn-remove-logistics-slides",
        "ws-class-logistics-panel",
        "ws-start-time-input",
        "ws-time-presets-menu",
        "ws-room-location-input",
        "ws-room-presets-menu",
        "ws-chk-include-slide2",
        "ws-chk-include-sliden",
        "btn-ws-apply-logistics-slides",
        "btn-ws-remove-logistics-slides",
    ):
        assert f'id="{log_id}"' in html, f"Missing logistics control #{log_id}"
    assert "applyOrRemoveClassLogisticsSlides" in js
    assert "class_start_time" in js
    assert "room_location" in js

    # Item 3: 2-line footer wrapping in renderActiveSlide
    assert "Workbook Requirement " in js

    # Item 4: Slim single-row compact hero banner CSS
    assert "body.deck-loaded-compact-hero .m3-hero-banner .m3-hero-patch-img" in css
    assert "min-height: 44px !important;" in css

    # Item 5: 27-Capability MCP Playground & execution_mode human-readable map
    assert "27-Capability MCP Playground" in html
    assert "15 MCP Tools" in html
    assert "7 Grounded" in html
    assert "5 Pedagogical Prompts" in html
    assert "formatUiExecutionModeLabel" in js

