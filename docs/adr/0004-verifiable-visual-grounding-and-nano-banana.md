# ADR 0004: Two-Stage Visual Conformance (`<10ms` AABB Math + Vision QA) and Pre-Bundled Nano Banana Catalog

## Status
Accepted

## Date
2026-10-12

## Context
Generating classroom-ready PowerPoint decks across 149 Merit Badges presents two failure modes:
1. **Layout Geometry Overflows (`FM-2`):** Variable-length requirement descriptions can overflow slide footers (`SafeCanvasBounds`) or cause overlapping text cards. Running a multimodal Vision LLM on every slide before checking geometry takes `8.5s` to `14.0s` and costs `$0.15` per pass.
2. **Runtime Image Synthesis Latency and Cost (`FM-1` / Post-Mortem #1):** Calling live diffusion models on every slide of a 60-slide deck costs `$1.60` to `$2.60` per deck, adds `45s+` of latency, and risks rendering meta-prompt words inside the illustration if requirement numbers leak into the image prompt.

## Options Considered
1. **Live AI Image Generation + Vision-LLM-Only QA on Every Slide:** High cost (`>$2.00/deck`), slow (`>60s` image + vision pass), and prone to raster text misspellings.
2. **Plain Text Slides with No Automated Geometry Check:** Zero image cost, but allows overlapping shapes and violates minimum `12.0pt` classroom readability rules.
3. **Pre-Bundled 4,124-Asset Catalog (`$0.00` runtime image cost) + Opt-In `$0.08` `NanoBananaImageAgent` with Prompt Sanitization + Two-Stage Conformance (`check_pptx_conformance()` + `audit_deck_visual_quality()`):**
   * Pre-bundle `4,124` curated assets across all 149 badges (`1,401` Nano Banana illustrations, `2,425` Vision-verified BSA Pamphlet figures, `149` emblems, `149` covers) with `slide_image_choices` for 1-click on-stage switching (`<50ms`, `$0.00`).
   * Strip requirement numbers via `build_clean_illustration_prompt()` and verify subject alignment (`alignment_score >= 0.70`) in `NanoBananaImageAgent` (`src/agents/image_studio.py`), gated behind explicit `$0.08` counselor consent (`user_consented=True`).
   * Execute **Stage 1 deterministic AABB geometry math** (`check_pptx_conformance()` in `src/agents/reviewer.py`) in `<10ms` at `$0.00` token cost to enforce `0` shape overlaps, `>= 12.0pt` font floor (`_compute_fitting_font_size()`), `>= 4.5:1` WCAG contrast, and `SafeCanvasBounds` (`content_bottom_max_in <= 6.54"`), followed by **Stage 2 visual rubric scoring** (`audit_deck_visual_quality()`).

## Decision
We selected **Option 3**: Pre-bundled 4,124-asset visual catalog paired with FinOps-gated `NanoBananaImageAgent` prompt sanitization and Two-Stage (`<10ms` AABB + Stage 2 Vision) conformance verification.

## Consequences
* **Positive:** Reduces standard deck runtime image cost to **`$0.00`**, achieves **`0` AABB overlaps** across all 471 slides in the 20-badge golden benchmark (`3.4 ms` p95 geometry check), and guarantees `100%` native editable OpenXML text frames in PowerPoint and Google Slides.
* **Negative / Trade-Off:** Requires maintaining `data/asset_inventory_manifest.json` (`4,124` SHA-256 checksums) and an on-demand per-badge GitHub Raw batch hydrator (`src/tools/asset_hydrator.py`) for `< 30 MB` bundle distributions.
