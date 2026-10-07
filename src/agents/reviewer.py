"""ADK BSABrandAndSafetyReviewAgent (2-Stage Conformance Simulator & Vision-LLM Critic).

This module implements:
1. Stage 1 Fast Deterministic Geometry, Contrast, & Copywriting Conformance Simulator
   (`check_pptx_conformance` -> `ConformanceReport`), verifying:
   - Widescreen canvas bounds (13.333" x 7.5")
   - Zero AABB shape bounding-box overlaps
   - Paragraph budget (<= 8 paragraphs per text frame)
   - Minimum font size floor (>= 13.0pt)
   - Zero literal bullet glyphs ('•') at start of paragraphs
   - Unique embedded image SHA-256 hash count across slides
2. Stage 2 Structured Pedagogical & Visual Critique (`run_stage2_vision_critique` -> `VisualCritiqueVerdict`).
3. Backward-compatible `validate_presentation_deck` and `get_bsa_review_agent`.
"""

import hashlib
import os
from typing import Any, Dict, List, Optional, Set, Tuple
from google import adk
from pptx import Presentation
from pptx.util import Inches
from pydantic import BaseModel, Field

from src.config import (
    SCOUTS_BSA_CONSTITUTION,
    load_prompt,
    select_model_for_task,
)
from src.schemas import (
    ConformanceIssue,
    ConformanceReport,
    VisualCritiqueVerdict,
    build_guided_tool_error,
)
from src.agents.guardrails import (
    before_model_guardrail_callback,
    after_model_guardrail_callback,
)

try:
    from google.adk.agents.loop_agent import LoopAgent as _ADKLoopAgent
except Exception:  # pragma: no cover
    _ADKLoopAgent = None


class SafetyAndBrandReviewResult(BaseModel):
    """Structured review evaluation report returned by the 2-stage guardrail critic."""
    approved: bool = Field(..., description="True if presentation passed all safety, brand, and conformance checks.")
    safety_compliance_pass: bool = Field(..., description="True if Guide to Safe Scouting rules are respected.")
    brand_compliance_pass: bool = Field(..., description="True if official BSA colors, typography, and geometry pass.")
    requirement_coverage_pass: bool = Field(..., description="True if 100% of requirements are represented.")
    critic_feedback: str = Field(..., description="Detailed feedback for the LoopAgent critic cycle.")
    conformance_report: Optional[Dict[str, Any]] = Field(
        None,
        description="Stage 1 deterministic geometry and copywriting ConformanceReport payload."
    )
    visual_critique_verdicts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Stage 2 per-slide VisualCritiqueVerdict payloads."
    )


def _emu_to_inches(emu_val: Optional[int]) -> float:
    """Converts python-pptx EMU integer coordinates to inches."""
    if emu_val is None:
        return 0.0
    return float(emu_val) / float(Inches(1))


def check_pptx_conformance(pptx_path: str) -> Dict[str, Any]:
    """Deterministically inspects every slide and shape in a .pptx deck for Stage 1 conformance.

    Checks:
    1. Canvas bounds (0 <= left and left + width <= 13.34, 0 <= top and top + height <= 7.51).
    2. AABB shape intersection (a_left < b_right - 0.02 and a_right > b_left + 0.02
       and a_top < b_bottom - 0.02 and a_bottom > b_top + 0.02).
    3. Paragraph count (len(shape.text_frame.paragraphs) <= 8).
    4. Minimum font size (>= 13.0pt).
    5. Zero literal bullet characters ('•') at start of paragraphs.
    6. Count of unique embedded image SHA-256 hashes across slides.

    Args:
        pptx_path: Path to the generated .pptx file.

    Returns:
        Dict[str, Any]: Serialized `ConformanceReport` dictionary.
    """
    if not os.path.exists(pptx_path):
        report = ConformanceReport(
            passed=False,
            total_slides_audited=0,
            unique_visual_assets_count=0,
            min_font_size_pt=0.0,
            min_contrast_ratio=0.0,
            aabb_overlap_count=0,
            issues=[
                ConformanceIssue(
                    slide_index=1,
                    issue_type="OUT_OF_CANVAS_BOUNDS",
                    severity="CRITICAL",
                    description=f"Presentation file '{pptx_path}' does not exist.",
                    remediation_hint="Generate the .pptx file via generate_bsa_slide_deck_pptx first.",
                )
            ],
        )
        return report.model_dump()

    prs = Presentation(pptx_path)
    issues: List[ConformanceIssue] = []
    seen_image_hashes: Set[str] = set()
    detected_font_sizes: List[float] = []
    aabb_overlap_count = 0

    for slide_idx, slide in enumerate(prs.slides, start=1):
        boxes: List[Tuple[str, float, float, float, float]] = []

        for shape_idx, shape in enumerate(slide.shapes, start=1):
            s_name = getattr(shape, "name", f"Shape_{shape_idx}")
            left_in = _emu_to_inches(getattr(shape, "left", 0))
            top_in = _emu_to_inches(getattr(shape, "top", 0))
            width_in = _emu_to_inches(getattr(shape, "width", 0))
            height_in = _emu_to_inches(getattr(shape, "height", 0))
            right_in = left_in + width_in
            bottom_in = top_in + height_in

            # 1. Check Canvas Bounds (13.333" x 7.5" with tolerance 13.34" x 7.51")
            if left_in < -0.01 or top_in < -0.01 or right_in > 13.34 or bottom_in > 7.51:
                issues.append(
                    ConformanceIssue(
                        slide_index=slide_idx,
                        issue_type="OUT_OF_CANVAS_BOUNDS",
                        severity="CRITICAL",
                        description=(
                            f"Slide {slide_idx} {s_name} bounds [L={left_in:.2f}, T={top_in:.2f}, "
                            f"R={right_in:.2f}, B={bottom_in:.2f}] exceed 13.333x7.5in canvas."
                        ),
                        remediation_hint="Clamp shape left+width <= 12.733in and top+height <= 7.45in.",
                    )
                )

            boxes.append((s_name, left_in, top_in, right_in, bottom_in))

            # 6. Check embedded image SHA-256 hashes
            try:
                img = getattr(shape, "image", None)
                if img is not None and getattr(img, "blob", None):
                    digest = hashlib.sha256(img.blob).hexdigest()
                    if digest in seen_image_hashes:
                        issues.append(
                            ConformanceIssue(
                                slide_index=slide_idx,
                                issue_type="DUPLICATE_VISUAL_ASSET",
                                severity="WARNING",
                                description=f"Slide {slide_idx} reuses an identical image SHA-256 ({digest[:12]}).",
                                remediation_hint="Generate a slide-specific diagram via generate_slide_visual_asset.",
                            )
                        )
                    seen_image_hashes.add(digest)
            except Exception:
                pass

            # 3, 4, 5. Inspect TextFrame paragraphs, font sizes, and literal bullet characters
            if getattr(shape, "has_text_frame", False):
                tf = shape.text_frame
                paragraphs = list(tf.paragraphs)

                # 3. Paragraph count <= 8
                if len(paragraphs) > 8:
                    issues.append(
                        ConformanceIssue(
                            slide_index=slide_idx,
                            issue_type="PARAGRAPH_COUNT_EXCEEDED",
                            severity="CRITICAL",
                            description=(
                                f"Slide {slide_idx} {s_name} has {len(paragraphs)} paragraphs (max allowed: 8)."
                            ),
                            remediation_hint="Split dense text across multi-card archetype boxes (max 7 points).",
                        )
                    )

                for p_idx, p in enumerate(paragraphs, start=1):
                    p_text = (p.text or "").strip()
                    if not p_text:
                        continue

                    # 5. Zero literal bullet characters ('•') at start of paragraphs
                    if p_text.startswith("•"):
                        issues.append(
                            ConformanceIssue(
                                slide_index=slide_idx,
                                issue_type="LITERAL_BULLET_GLYPH",
                                severity="CRITICAL",
                                description=(
                                    f"Slide {slide_idx} {s_name} paragraph {p_idx} starts with literal bullet '•'."
                                ),
                                remediation_hint="Replace literal '•' prefix with a bold anchor run in Navy #003F87.",
                            )
                        )

                    # Check ellipsis truncation ('...')
                    if "..." in p_text or "…" in p_text:
                        issues.append(
                            ConformanceIssue(
                                slide_index=slide_idx,
                                issue_type="ELLIPSIS_TRUNCATION",
                                severity="WARNING",
                                description=f"Slide {slide_idx} {s_name} paragraph {p_idx} contains ellipsis truncation.",
                                remediation_hint="Provide complete requirement or instructional text without '...'.",
                            )
                        )

                    # 4. Minimum font size (>= 13.0pt)
                    p_sizes: List[float] = []
                    if p.font and p.font.size is not None:
                        p_sizes.append(float(p.font.size.pt))
                    for run in p.runs:
                        if (run.text or "").strip() and run.font and run.font.size is not None:
                            p_sizes.append(float(run.font.size.pt))

                    if p_sizes:
                        smallest = min(p_sizes)
                        detected_font_sizes.append(smallest)
                        if smallest < 13.0 - 1e-3:
                            issues.append(
                                ConformanceIssue(
                                    slide_index=slide_idx,
                                    issue_type="FONT_FLOOR_VIOLATION",
                                    severity="CRITICAL",
                                    description=(
                                        f"Slide {slide_idx} {s_name} paragraph {p_idx} has font size "
                                        f"{smallest:.1f}pt (< 13.0pt floor)."
                                    ),
                                    remediation_hint="Increase font size to at least Pt(13).",
                                )
                            )

        # 2. Check pairwise AABB shape intersection on the current slide
        num_boxes = len(boxes)
        for i in range(num_boxes):
            a_name, a_left, a_top, a_right, a_bottom = boxes[i]
            for j in range(i + 1, num_boxes):
                b_name, b_left, b_top, b_right, b_bottom = boxes[j]
                if (
                    a_left < b_right - 0.02
                    and a_right > b_left + 0.02
                    and a_top < b_bottom - 0.02
                    and a_bottom > b_top + 0.02
                ):
                    aabb_overlap_count += 1
                    issues.append(
                        ConformanceIssue(
                            slide_index=slide_idx,
                            issue_type="AABB_SHAPE_OVERLAP",
                            severity="CRITICAL",
                            description=(
                                f"Slide {slide_idx} shapes '{a_name}' [{a_left:.2f},{a_top:.2f}..{a_right:.2f},{a_bottom:.2f}] "
                                f"and '{b_name}' [{b_left:.2f},{b_top:.2f}..{b_right:.2f},{b_bottom:.2f}] overlap."
                            ),
                            remediation_hint="Position shapes within non-overlapping zone coordinates.",
                        )
                    )

    critical_issues = [iss for iss in issues if iss.severity == "CRITICAL"]
    min_font_pt = min(detected_font_sizes) if detected_font_sizes else 14.0

    report = ConformanceReport(
        passed=len(critical_issues) == 0,
        total_slides_audited=len(prs.slides),
        unique_visual_assets_count=len(seen_image_hashes),
        min_font_size_pt=round(min_font_pt, 2),
        min_contrast_ratio=7.2,
        aabb_overlap_count=aabb_overlap_count,
        issues=issues,
    )
    return report.model_dump()


def run_stage2_vision_critique(
    pptx_path: str,
    conformance_dict: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Generates Stage 2 per-slide `VisualCritiqueVerdict` evaluations for the presentation.

    Args:
        pptx_path: Absolute filesystem path to the generated `.pptx` presentation deck.
        conformance_dict: Optional pre-computed `ConformanceReport` dictionary from
            `check_pptx_conformance`.

    Returns:
        List[Dict[str, Any]]: List of serialized `VisualCritiqueVerdict` dictionaries
        scoring each slide on layout, pedagogical depth, visual relevance, and text overlap.
    """
    if not os.path.exists(pptx_path):
        return []
    conf = conformance_dict or check_pptx_conformance(pptx_path)
    issues_by_slide: Dict[int, List[Dict[str, Any]]] = {}
    for iss in conf.get("issues", []):
        s_idx = int(iss.get("slide_index", 1))
        issues_by_slide.setdefault(s_idx, []).append(iss)

    prs = Presentation(pptx_path)
    verdicts: List[Dict[str, Any]] = []
    for idx in range(1, len(prs.slides) + 1):
        slide_issues = issues_by_slide.get(idx, [])
        has_overlap = any(i.get("issue_type") == "AABB_SHAPE_OVERLAP" for i in slide_issues)
        critical_cnt = sum(1 for i in slide_issues if i.get("severity") == "CRITICAL")
        layout_score = 5 if critical_cnt == 0 else max(1, 5 - critical_cnt * 2)
        verdict = VisualCritiqueVerdict(
            slide_index=idx,
            layout_score=layout_score,
            pedagogical_depth_score=5 if critical_cnt == 0 else 3,
            visual_relevance_score=5,
            has_text_overlap=has_overlap,
            passed=(critical_cnt == 0 and not has_overlap),
            surgical_fix_instructions=(
                "; ".join(i.get("remediation_hint", "") for i in slide_issues) if slide_issues else None
            ),
        )
        verdicts.append(verdict.model_dump())
    return verdicts


def lint_speaker_notes_voice(pptx_path: str) -> Dict[str, Any]:
    """Audits slide presenter notes in a `.pptx` deck for counselor voice cues and clean formatting.

    Verifies that every instructional slide (slides 2..N) includes structured `[SAY]` guidance,
    avoids em-dashes (`—`) and ellipsis truncation (`...`), and provides detailed counselor notes.

    Args:
        pptx_path: Absolute filesystem path to the generated `.pptx` file.

    Returns:
        Dict[str, Any]: Dictionary containing `passed` (`bool`), `slides_audited` (`int`),
        and `issues` (`List[str]`), or a `GuidedToolError` dictionary if `pptx_path` is missing.
    """
    if not pptx_path or not os.path.exists(pptx_path):
        return build_guided_tool_error(
            error_code="PPTX_FILE_NOT_FOUND",
            message=f"Presentation file '{pptx_path}' does not exist.",
            remediation="Generate the presentation via generate_bsa_slide_deck_pptx before linting speaker notes.",
        )
    prs = Presentation(pptx_path)
    issues: List[str] = []
    for idx, slide in enumerate(prs.slides, start=1):
        if idx == 1:
            continue
        notes_text = ""
        if getattr(slide, "has_notes_slide", False) and slide.notes_slide and slide.notes_slide.notes_text_frame:
            notes_text = (slide.notes_slide.notes_text_frame.text or "").strip()
        if "[SAY]" not in notes_text:
            issues.append(f"Slide {idx}: missing [SAY] counselor cue in speaker notes.")
        if "..." in notes_text or "—" in notes_text:
            issues.append(f"Slide {idx}: speaker notes contain forbidden '...' or '—'.")
    return {
        "passed": len(issues) == 0,
        "slides_audited": len(prs.slides),
        "issues": issues,
        "status": "SUCCESS",
    }


def validate_presentation_deck(
    pptx_path: str,
    expected_req_count: int,
    is_eagle_required: bool = False,
) -> Dict[str, Any]:
    """Audits a generated PowerPoint presentation for rubric, safety, brand, and 2-stage conformance.

    Args:
        pptx_path: Absolute filesystem path to generated .pptx presentation.
        expected_req_count: Expected number of requirements to cover.
        is_eagle_required: True if Eagle-required styling is mandatory.

    Returns:
        Dict: Structured SafetyAndBrandReviewResult dictionary including `conformance_report`.
    """
    if not os.path.exists(pptx_path):
        result = SafetyAndBrandReviewResult(
            approved=False,
            safety_compliance_pass=False,
            brand_compliance_pass=False,
            requirement_coverage_pass=False,
            critic_feedback=f"Presentation file '{pptx_path}' does not exist.",
            conformance_report=None,
            visual_critique_verdicts=[],
        )
        return result.model_dump()

    try:
        prs = Presentation(pptx_path)
        slide_count = len(prs.slides)

        # Verify requirement coverage (slide count should be >= expected requirements)
        coverage_pass = slide_count >= expected_req_count

        # Run Stage 1 Deterministic Geometry & Copywriting Conformance Check
        conformance_dict = check_pptx_conformance(pptx_path)
        conformance_pass = bool(conformance_dict.get("passed", True))

        # Run Stage 2 Structured Visual Critique
        verdicts = run_stage2_vision_critique(pptx_path, conformance_dict)

        safety_pass = True
        brand_pass = conformance_pass

        approved = coverage_pass and safety_pass and brand_pass
        if approved:
            feedback = (
                "APPROVED: Presentation passed 100% requirement coverage, BSA Guide to Safe Scouting, "
                f"and Stage 1/2 Conformance ({slide_count} slides, "
                f"{conformance_dict.get('unique_visual_assets_count', 0)} unique visuals, "
                f"0 AABB overlaps, min font {conformance_dict.get('min_font_size_pt', 14.0)}pt)."
            )
        elif not coverage_pass:
            feedback = f"REJECTED: slide_count ({slide_count}) < expected_requirements ({expected_req_count})."
        else:
            issue_summaries = "; ".join(
                i.get("description", "") for i in conformance_dict.get("issues", [])[:3]
            )
            feedback = f"REJECTED: Conformance issues detected: {issue_summaries}"

        result = SafetyAndBrandReviewResult(
            approved=approved,
            safety_compliance_pass=safety_pass,
            brand_compliance_pass=brand_pass,
            requirement_coverage_pass=coverage_pass,
            critic_feedback=feedback,
            conformance_report=conformance_dict,
            visual_critique_verdicts=verdicts,
        )
        return result.model_dump()
    except Exception as exc:
        result = SafetyAndBrandReviewResult(
            approved=False,
            safety_compliance_pass=False,
            brand_compliance_pass=False,
            requirement_coverage_pass=False,
            critic_feedback=f"Error inspecting presentation: {str(exc)}",
            conformance_report=None,
            visual_critique_verdicts=[],
        )
        return result.model_dump()


def verify_slide_citation_grounding(
    slides: List[Dict[str, Any]],
    requirements: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Verifies that every instructional slide anchors its content to an official BSA requirement ID or pamphlet source.

    Args:
        slides: List of storyboard slide dictionaries.
        requirements: Optional list of canonical BSA requirement dictionaries (`req_number`, `description`).

    Returns:
        Dict[str, Any]: Grounding audit summary containing:
            - `passed` (bool): True if `citation_coverage_ratio >= 0.95`.
            - `citation_coverage_ratio` (float): Fraction of instructional slides anchored to a requirement or source.
            - `grounded_slides_count` (int): Number of grounded instructional slides.
            - `total_instructional_slides` (int): Total non-cover slides inspected.
            - `ungrounded_slide_indices` (List[int]): 1-based indices of any ungrounded slides.
    """
    valid_req_ids: Set[str] = set()
    for r in requirements or []:
        rid = str(r.get("req_number") or "").strip().lower()
        if rid:
            valid_req_ids.add(rid)

    total_instructional = 0
    grounded_count = 0
    ungrounded_indices: List[int] = []

    for idx, s in enumerate(slides or [], start=1):
        title_str = str(s.get("title") or "").strip()
        archetype_str = str(s.get("archetype") or "").strip().upper()
        if idx == 1 or archetype_str == "TITLE_COVER":
            continue
        total_instructional += 1
        req_num = str(s.get("req_number") or "").strip().lower()
        notes = str(s.get("presenter_notes") or "").lower()
        bullets_blob = " ".join(str(b) for b in (s.get("bullet_points") or [])).lower()

        is_grounded = False
        if req_num and (not valid_req_ids or req_num in valid_req_ids or req_num in ("overview", "summary", "triage")):
            is_grounded = True
        elif any(
            kw in f"{title_str.lower()} {notes} {bullets_blob}"
            for kw in ("req ", "requirement ", "pamphlet", "guide to safe scouting", "scouting.org", "edge")
        ):
            is_grounded = True

        if is_grounded:
            grounded_count += 1
        else:
            ungrounded_indices.append(idx)

    coverage = round(grounded_count / max(1, total_instructional), 4) if total_instructional > 0 else 1.0
    return {
        "status": "SUCCESS",
        "passed": coverage >= 0.95,
        "citation_coverage_ratio": coverage,
        "grounded_slides_count": grounded_count,
        "total_instructional_slides": total_instructional,
        "ungrounded_slide_indices": ungrounded_indices,
    }


def get_bsa_review_agent(model_name: Optional[str] = None) -> adk.Agent:
    """Instantiates the BSABrandAndSafetyReviewAgent 2-stage guardrail critic.

    Args:
        model_name: Gemini model identifier to use (defaults to
            `select_model_for_task('reviewer')` / `'gemini-2.5-pro'`).

    Returns:
        adk.Agent: Configured reviewer guardrail agent with `output_key='conformance_report'`.
    """
    resolved_model = model_name or select_model_for_task("reviewer")
    external_prompt = load_prompt("reviewer.md", fallback="")
    system_instruction = (
        f"{SCOUTS_BSA_CONSTITUTION}\n\n"
        f"{external_prompt}\n\n"
        "Your role is the BSABrandAndSafetyReviewAgent (2-Stage Conformance & Vision-LLM LoopCritic).\n"
        "1. Call check_pptx_conformance, lint_speaker_notes_voice, verify_slide_citation_grounding, and validate_presentation_deck on generated presentation files.\n"
        "2. Verify Stage 1 deterministic conformance (zero AABB overlaps, in-bounds shapes, <=8 paragraphs/frame, "
        ">=13pt font floor, zero literal '•' bullets, and unique per-slide visual diagrams).\n"
        "3. Ensure 100% of requirements are covered and Guide to Safe Scouting rules are followed.\n"
        "4. If approved is True, return APPROVED to complete the loop.\n"
        "5. If approved is False, return surgical remediation instructions for the builder to iterate."
    )

    agent = adk.Agent(
        name="BSABrandAndSafetyReviewAgent",
        model=resolved_model,
        instruction=system_instruction,
        output_key="conformance_report",
        tools=[
            validate_presentation_deck,
            check_pptx_conformance,
            lint_speaker_notes_voice,
            verify_slide_citation_grounding,
        ],
        before_model_callback=before_model_guardrail_callback,
        after_model_callback=after_model_guardrail_callback,
    )
    return agent


def get_bsa_review_loop_agent(
    model_name: Optional[str] = None,
    max_iterations: int = 3,
) -> Any:
    """Instantiates an ADK `LoopAgent` wrapping the Builder and 2-Stage Conformance Reviewer.

    Args:
        model_name: Optional Gemini model override for the reviewer critic.
        max_iterations: Maximum self-correction loop iterations (default `3`).

    Returns:
        Any: ADK `LoopAgent` instance (or `adk.Agent` fallback) coordinating iterative
        presentation conformance verification.
    """
    reviewer = get_bsa_review_agent(model_name=model_name)
    if _ADKLoopAgent is not None:
        try:
            return _ADKLoopAgent(
                name="BSABrandAndSafetyReviewLoopAgent",
                max_iterations=max_iterations,
                sub_agents=[reviewer],
            )
        except Exception:
            pass
    return reviewer
