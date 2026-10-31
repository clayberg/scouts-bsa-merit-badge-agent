#!/usr/bin/env python3
"""V35/V36 Regenerate Facilitator Notes (`data/precomputed_facilitator_notes_149.json`).

Pre-computes the flat lookup dictionary (`dict[str, str]`) of 5-Part Socratic
Facilitator Guide notes across all 149 Merit Badges, including:
- Cover, Overview, and Sources slides
- All 7 semantic slide roles (`0..6`) for every top-level requirement (`1,158`)
- All 7 semantic slide roles (`0..6`) for every L1/L2/L3/L4 sub-requirement (`2,559+`)

Enforces V36 Item 7 quality gates:
1. Zero mid-word or mid-sentence character slices (`[:135]`, `[:130]`, `[:90]` removed).
2. Zero duplicated single-excerpt `[EXPECTED PAMPHLET ANSWER KEY]` blocks.
3. Full 7-role coverage across all top-level requirements and all recursive sub-requirements.
4. Zero em dashes, en dashes, or double hyphens in prose.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.planner import _replace_unslop_words, _smart_title_case

REQ_DIR = ROOT / "data" / "merit_badge_requirements"
FACILITATOR_NOTES_PATH = ROOT / "data" / "precomputed_facilitator_notes_149.json"


def clean_prose(text: str) -> str:
    """Normalizes whitespace and strips em/en dashes, double hyphens, and AI puffery words."""
    if not text:
        return ""
    s = _replace_unslop_words(str(text))
    s = s.replace("\u2014", ", ").replace("\u2013", "-").replace("--", ", ")
    s = re.sub(r"\s*,\s*,\s*", ", ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def ensure_sentence_end(text: str) -> str:
    """Ensures a phrase ends cleanly without trailing punctuation before period."""
    s = clean_prose(text).rstrip(".,;:!? ")
    return s


def build_5part_facilitator_note(
    badge_name: str,
    req_id: str,
    topic_phrase: str,
    req_text: str,
    excerpts: List[str],
    misc_pair: Dict[str, str],
    wb_org: Dict[str, Any],
    page_cite: str,
    slide_idx: int,
    safety_callout: str = "",
    procs: Optional[List[str]] = None,
    comp_data: Optional[Dict[str, Any]] = None,
    worked_ex: Optional[Dict[str, Any]] = None,
    quiz_item: Optional[Dict[str, Any]] = None,
    gear_list: Optional[List[str]] = None,
    socratic_questions: Optional[List[str]] = None,
    misconception_pool: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Builds a rich, Socratic, role-specific 5-Part Facilitator Guide note for a specific slide index."""
    clean_b = _smart_title_case(clean_prose(badge_name))
    clean_r = clean_prose(req_id)
    clean_tp = _smart_title_case(clean_prose(topic_phrase).replace(f"Req {clean_r}:", "").strip() or f"{clean_b} Req {clean_r}")
    cite = clean_prose(page_cite or f"Official {clean_b} Merit Badge Pamphlet, Req {clean_r}")

    if clean_r.lower() == "cover":
        return "\n".join([
            f"[PACING & MODALITY] 2 min | Session Launch | EDGE: Explain | {cite}. [Gesture to the title slide] Welcome to the {clean_b} Merit Badge clinic, Scouts! Confirm every buddy pair has their {clean_b} Workbook and Blue Card (#34124) ready.",
            f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Hold up Blue Card #34124 and the {clean_b} Workbook] Verify Scout names, unit numbers, and prerequisite preparation before moving to the Requirements Overview.",
        ])

    if clean_r.lower() == "overview":
        return "\n".join([
            f"[PACING & MODALITY] 3 min | Syllabus Roadmap | EDGE: Explain & Plan | {cite}. [Point to the Requirements Triage Matrix] Walk Patrols through the three requirement tracks for {clean_b}: In-Class Discussions, Hands-On Skill Stations, and Home/Troop Prerequisites.",
            f"[ASK SCOUTS FIRST] Looking at our {clean_b} roadmap, which requirements demand field logs or hands-on demonstrations versus patrol discussion, and how will you schedule them?",
            f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. [Expected Answer: In-class concepts are discussed together, skill stations use the BSA EDGE method with buddy pairs, and prerequisite logs require documented field evidence.]",
            f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Point to the Workbook Table of Contents] Have Scouts circle their target session milestones in their {clean_b} Fillable Workbook.",
        ])

    if clean_r.lower() == "sources":
        return "\n".join([
            f"[PACING & MODALITY] 2 min | Final Checkout & References | EDGE: Enable | {cite}. [Point to the Official Pamphlet & Resource links] Wrap up the {clean_b} walkthrough and transition to individual counselor sign-off conferences.",
            "[DEMONSTRATION & SIGN-OFF RUBRIC] [Hold up Blue Card #34124] Initial each verified requirement in the Counselor Triage Matrix and review Smart Partial next steps for any open home-troop items.",
        ])

    slide_roles = [
        ("Core Concept & Pamphlet Standard", "Explain & Demonstrate", "3 min"),
        ("Step-by-Step Procedure & Technique", "Demonstrate & Guide", "4 min"),
        ("Differential Technical Comparison", "Explain & Guide", "3 min"),
        ("Exemplar Workbook Log & Verification", "Guide & Enable", "3 min"),
        ("Patrol Socratic Checkpoint Quiz", "Enable & Verify", "3 min"),
        ("Quartermaster Gear & Safety Shakedown", "Demonstrate & Enable", "3 min"),
        ("Extended Deep-Dive & Field Application", "Guide & Enable", "4 min"),
    ]
    role_idx = slide_idx % len(slide_roles)
    role_name, edge_stage, est_min = slide_roles[role_idx]

    wb_title = clean_prose(str(wb_org.get("table_title") or f"Req {clean_r} Structured Study Table"))
    ex1 = clean_prose(excerpts[slide_idx % len(excerpts)]) if excerpts else clean_prose(req_text)
    if not ex1.endswith((".", "!", "?")):
        ex1 = ex1 + "."

    pr_list = [clean_prose(p) for p in (procs or []) if clean_prose(p)]
    if len(excerpts) > 1:
        ex2_cand = clean_prose(excerpts[(slide_idx + 1) % len(excerpts)])
    elif pr_list and pr_list[0].strip().lower() != ex1.strip().lower():
        ex2_cand = pr_list[0]
    else:
        we_sample = clean_prose(str((worked_ex or {}).get("sample_output") or ""))
        if we_sample and we_sample.strip().lower() != ex1.strip().lower():
            ex2_cand = we_sample
        else:
            ex2_cand = f"Apply the {clean_b} pamphlet verification criteria for {clean_tp} and record your observations in {wb_title}."

    if ex2_cand.strip().lower() == ex1.strip().lower():
        ex2 = f"Apply the {clean_b} pamphlet verification criteria for {clean_tp} and record your observations in {wb_title}."
    else:
        ex2 = ex2_cand
    if not ex2.endswith((".", "!", "?")):
        ex2 = ex2 + "."

    pr1 = pr_list[0] if pr_list else ex1
    if not pr1.endswith((".", "!", "?")):
        pr1 = pr1 + "."

    if len(pr_list) > 1 and pr_list[1].strip().lower() != pr1.strip().lower():
        pr2 = pr_list[1]
    elif ex2.strip().lower() != pr1.strip().lower():
        pr2 = ex2
    else:
        pr2 = f"Verify all steps for {clean_tp} with your buddy pair and Merit Badge Counselor."
    if not pr2.endswith((".", "!", "?")):
        pr2 = pr2 + "."

    all_miscs: List[Dict[str, str]] = []
    if isinstance(misc_pair, dict) and misc_pair.get("misconception"):
        all_miscs.append(misc_pair)
    for mp_item in (misconception_pool or []):
        if isinstance(mp_item, dict) and mp_item.get("misconception"):
            all_miscs.append(mp_item)
    chosen_mp = all_miscs[role_idx % len(all_miscs)] if all_miscs else {}
    raw_myth = clean_prose(str(chosen_mp.get("misconception") or ""))
    raw_fact = clean_prose(str(chosen_mp.get("fact") or chosen_mp.get("fact_correction") or ""))
    myth = raw_myth
    fact = raw_fact or ex1
    safe_str = f" [Safety Check: {clean_prose(safety_callout)}]" if (safety_callout and role_idx in (0, 1, 5)) else ""

    soc_list_clean: List[str] = []
    seen_socs: set = set()
    for q in (socratic_questions or []):
        cq = clean_prose(q)
        if cq and cq.lower() not in seen_socs:
            seen_socs.add(cq.lower())
            soc_list_clean.append(cq)

    soc_q0 = soc_list_clean[0] if len(soc_list_clean) >= 1 else ""
    soc_q1 = soc_list_clean[1] if len(soc_list_clean) >= 2 else ""
    soc_q2 = soc_list_clean[2] if len(soc_list_clean) >= 3 else ""
    soc_q3 = soc_list_clean[3] if len(soc_list_clean) >= 4 else ""
    soc_q4 = soc_list_clean[4] if len(soc_list_clean) >= 5 else ""
    soc_q5 = soc_list_clean[5] if len(soc_list_clean) >= 6 else ""

    if role_idx == 0:
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage}. "
            f"[Point to Card 1: {clean_tp}] Introduce {clean_tp} for {clean_b} Req {clean_r}.{safe_str}"
        )
        ask_q0 = soc_q0 or f"Why is {clean_tp} foundational in {clean_b} Requirement {clean_r}, and where have you applied it?"
        ask = f"[ASK SCOUTS FIRST] {ask_q0}"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. {ex1} [Expected Answer: {ex2}]"
        rubric = f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Open {wb_title}] Have each Scout record the primary definition and facts for Req {clean_r}."
    elif role_idx == 1:
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage}. "
            f"[Step to demo table] Model the step-by-step sequence for {clean_tp}, then coach buddy pairs.{safe_str}"
        )
        ask_q_proc = (
            soc_q1
            if soc_q1
            else f"During {clean_b} Requirement {clean_r} ({clean_tp}), why must your buddy pair complete {ensure_sentence_end(pr1)} before advancing to {ensure_sentence_end(pr2)}?"
        )
        ask = f"[ASK SCOUTS FIRST] {ask_q_proc}"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. {pr1} [Expected Answer: {pr2}]"
        rubric = f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Observe practice] Verify each Scout demonstrates all steps of Req {clean_r} per GTA 7.0.3.2."
    elif role_idx == 2:
        lh = _smart_title_case(clean_prose(str((comp_data or {}).get("left_header") or f"{clean_tp} Primary Standard")))
        rh = _smart_title_case(clean_prose(str((comp_data or {}).get("right_header") or f"{clean_tp} Field Application")))
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage}. "
            f"[Point to columns: {lh} vs. {rh}] Contrast {lh} against {rh} for {clean_b} Req {clean_r}."
        )
        ask_q_comp = (
            soc_q2
            if soc_q2
            else f"When evaluating {lh} versus {rh} in {clean_b} Requirement {clean_r}, what practical criteria guide your patrol's choice?"
        )
        ask = f"[ASK SCOUTS FIRST] {ask_q_comp}"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. {ex2} [Expected Answer: Contrast {lh} and {rh} using {clean_b} pamphlet examples.]"
        rubric = ""
    elif role_idx == 3:
        we_out = clean_prose(str((worked_ex or {}).get("sample_output") or ex1))
        we_tip = clean_prose(str((worked_ex or {}).get("counselor_tip") or f"Verify specific details for {clean_tp}."))
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage}. "
            f"[Point to Exemplar Log] Show Scouts a sign-off-ready entry for Req {clean_r} ({clean_tp})."
        )
        ask_q_we = (
            soc_q3
            if soc_q3
            else f"In our {clean_b} Requirement {clean_r} exemplar log for {clean_tp}, which recorded measurement or observation proves mastery?"
        )
        ask = f"[ASK SCOUTS FIRST] {ask_q_we}"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. {we_out} [Expected Answer: {we_tip}]"
        rubric = f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Inspect Workbooks] Check that each Scout's entry in {wb_title} includes specific observations."
    elif role_idx == 4:
        q_prompt = clean_prose(str((quiz_item or {}).get("scenario_prompt") or f"How should your patrol apply {clean_tp} during {clean_b} Requirement {clean_r}?"))
        q_ans = clean_prose(str((quiz_item or {}).get("correct_answer") or fact))
        q_exp = clean_prose(str((quiz_item or {}).get("explanation") or ex1))
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage}. "
            f"[Pose Checkpoint Quiz] Give buddy pairs 45 seconds to debate the scenario for {clean_b} Req {clean_r}."
        )
        ask = f"[ASK SCOUTS FIRST] Scenario Check: \"{q_prompt}\" Which option does your buddy pair select, and why?"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. [Expected Answer: {q_ans} {q_exp}]"
        rubric = f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Poll patrol responses] Have buddy pairs explain why the distractors fail the {clean_b} standard."
    elif role_idx == 5:
        g1 = clean_prose(gear_list[0]) if gear_list else f"Required reference materials and field gear for {clean_tp}"
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage}. "
            f"[Hold up gear: {g1}] Conduct a patrol equipment shakedown for {clean_b} Req {clean_r}.{safe_str}"
        )
        ask_q_gear = (
            soc_q4
            if soc_q4
            else f"During our {clean_b} Requirement {clean_r} shakedown of {g1}, what readiness check must your buddy pair verify?"
        )
        ask = f"[ASK SCOUTS FIRST] {ask_q_gear}"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. {ex1} [Expected Answer: Inspect {g1} and verify scene safety before execution.]"
        rubric = ""
    else:
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage}. "
            f"[Facilitate deep-dive on {clean_tp}] Connect {clean_tp} to field application in {clean_b} Req {clean_r}."
        )
        ask_q5 = soc_q5 or f"If field conditions change while applying {clean_tp} in {clean_b} Requirement {clean_r}, how should your patrol adapt?"
        ask = f"[ASK SCOUTS FIRST] {ask_q5}"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. {ex2} [Expected Answer: Connect {clean_tp} to field decision-making in {wb_title}.]"
        rubric = ""

    # Selectively include [COMMON MISCONCEPTION TO CORRECT] only on concept/comparison/visual roles when a real misconception exists
    if myth and role_idx not in (3, 4, 5) and "general familiarity with" not in myth.lower():
        misc = f"[COMMON MISCONCEPTION TO CORRECT] Myth: {myth} | BSA Pamphlet Fact: {fact}"
    else:
        misc = ""
    return "\n".join(clean_prose(line) for line in (pacing, ask, key, misc, rubric) if line and line.strip())


def _populate_subreq_notes_recursive(
    notes_map: Dict[str, str],
    u_slug: str,
    f_slug: str,
    bname: str,
    node: Dict[str, Any],
    parent_tp: str,
    parent_txt: str,
    parent_ex: List[str],
    parent_misc: Dict[str, str],
    parent_wb: Dict[str, Any],
    parent_cite: str,
    parent_safe: str,
    parent_procs: List[str],
    parent_comp: Dict[str, Any],
    parent_we: Dict[str, Any],
    parent_quiz: Dict[str, Any],
    parent_gear: List[str],
    parent_soc: Optional[List[str]] = None,
    parent_misc_pool: Optional[List[Dict[str, str]]] = None,
) -> int:
    """Recursively pre-computes all 7 slide roles (0..6) for a sub-requirement node and all its children."""
    count = 0
    sr_id = str(node.get("sub_id") or "")
    if not sr_id:
        return 0
    sr_tp = str(node.get("topic_title") or parent_tp).split(":", 1)[-1].strip()
    sr_txt = str(node.get("text") or parent_txt)
    sr_ex = list(node.get("pamphlet_excerpts") or parent_ex)
    sr_misc = node.get("common_misconception_pair") or parent_misc
    sr_wb = node.get("workbook_organizer") or parent_wb
    sr_cite = str(node.get("pamphlet_page_citation") or parent_cite)
    sr_safe = str(node.get("safety_callout") or parent_safe)
    sr_procs = list(node.get("step_by_step_procedure") or parent_procs)
    sr_comp = node.get("comparison_data") or parent_comp
    sr_we = node.get("worked_example") or parent_we
    sr_quiz = node.get("quiz_item") or parent_quiz
    sr_gear = list(node.get("gear_checklist") or parent_gear)
    sr_soc = list(node.get("socratic_questions") or parent_soc or [])
    sr_misc_pool = list(node.get("misconception_pool") or parent_misc_pool or [])

    for s_idx in range(7):
        sr_note = build_5part_facilitator_note(
            badge_name=bname,
            req_id=sr_id,
            topic_phrase=sr_tp,
            req_text=sr_txt,
            excerpts=sr_ex,
            misc_pair=sr_misc,
            wb_org=sr_wb,
            page_cite=sr_cite,
            slide_idx=s_idx,
            safety_callout=sr_safe,
            procs=sr_procs,
            comp_data=sr_comp,
            worked_ex=sr_we,
            quiz_item=sr_quiz,
            gear_list=sr_gear,
            socratic_questions=sr_soc,
            misconception_pool=sr_misc_pool,
        )
        notes_map[f"{u_slug}::{sr_id}::{s_idx}"] = sr_note
        count += 1

    for ch in node.get("children") or []:
        if isinstance(ch, dict):
            count += _populate_subreq_notes_recursive(
                notes_map=notes_map,
                u_slug=u_slug,
                f_slug=f_slug,
                bname=bname,
                node=ch,
                parent_tp=sr_tp,
                parent_txt=sr_txt,
                parent_ex=sr_ex,
                parent_misc=sr_misc,
                parent_wb=sr_wb,
                parent_cite=sr_cite,
                parent_safe=sr_safe,
                parent_procs=sr_procs,
                parent_comp=sr_comp,
                parent_we=sr_we,
                parent_quiz=sr_quiz,
                parent_gear=sr_gear,
                parent_soc=sr_soc,
                parent_misc_pool=sr_misc_pool,
            )
    return count


def regenerate_facilitator_notes() -> None:
    """Generates `data/precomputed_facilitator_notes_149.json` across all 149 badges."""
    notes_map: Dict[str, str] = {}
    slide_entries_count = 0

    badge_files = sorted(p for p in REQ_DIR.glob("*.json") if not p.name.startswith("_"))
    for p in badge_files:
        data = json.loads(p.read_text(encoding="utf-8"))
        u_slug = str(data.get("slug") or p.stem)
        f_slug = str(data.get("badge_slug") or u_slug.replace("-", "_"))
        bname = str(data.get("badge_name") or u_slug.replace("-", " ").title())
        reqs = data.get("requirements") or []

        for special_req in ("cover", "overview", "sources"):
            note_txt = build_5part_facilitator_note(
                badge_name=bname,
                req_id=special_req,
                topic_phrase=f"{bname} {special_req.title()}",
                req_text="",
                excerpts=[],
                misc_pair={},
                wb_org={},
                page_cite=f"Official {bname} Merit Badge Pamphlet",
                slide_idx=0,
            )
            notes_map[f"{u_slug}::{special_req}::0"] = note_txt
            slide_entries_count += 1

        for req in reqs:
            rid = str(req.get("req_id") or req.get("number") or "1")
            tp = str(req.get("topic_title") or f"Req {rid}").split(":", 1)[-1].strip()
            r_txt = str(req.get("req_text") or req.get("description") or "")
            ex_list = list(req.get("pamphlet_excerpts") or [])
            misc = req.get("common_misconception_pair") or {}
            wb = req.get("workbook_organizer") or {}
            cite = str(req.get("pamphlet_page_citation") or "")
            safe = str(req.get("safety_callout") or "")
            procs = list(req.get("step_by_step_procedure") or [])
            comp_data = req.get("comparison_data") or {}
            worked_ex = req.get("worked_example") or {}
            quiz_item = req.get("quiz_item") or {}
            gear_list = list(req.get("gear_checklist") or [])
            soc_list = list(req.get("socratic_questions") or [])
            misc_pool = list(req.get("misconception_pool") or [])

            for s_idx in range(7):
                note_txt = build_5part_facilitator_note(
                    badge_name=bname,
                    req_id=rid,
                    topic_phrase=tp,
                    req_text=r_txt,
                    excerpts=ex_list,
                    misc_pair=misc,
                    wb_org=wb,
                    page_cite=cite,
                    slide_idx=s_idx,
                    safety_callout=safe,
                    procs=procs,
                    comp_data=comp_data,
                    worked_ex=worked_ex,
                    quiz_item=quiz_item,
                    gear_list=gear_list,
                    socratic_questions=soc_list,
                    misconception_pool=misc_pool,
                )
                notes_map[f"{u_slug}::{rid}::{s_idx}"] = note_txt
                slide_entries_count += 1

            for sr in req.get("sub_requirements") or []:
                if isinstance(sr, dict):
                    slide_entries_count += _populate_subreq_notes_recursive(
                        notes_map=notes_map,
                        u_slug=u_slug,
                        f_slug=f_slug,
                        bname=bname,
                        node=sr,
                        parent_tp=tp,
                        parent_txt=r_txt,
                        parent_ex=ex_list,
                        parent_misc=misc,
                        parent_wb=wb,
                        parent_cite=cite,
                        parent_safe=safe,
                        parent_procs=procs,
                        parent_comp=comp_data,
                        parent_we=worked_ex,
                        parent_quiz=quiz_item,
                        parent_gear=gear_list,
                        parent_soc=soc_list,
                        parent_misc_pool=misc_pool,
                    )

    FACILITATOR_NOTES_PATH.write_text(
        json.dumps(notes_map, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        f"Saved {FACILITATOR_NOTES_PATH.name} with {slide_entries_count} unique slide notes "
        f"({len(notes_map)} total lookup keys across {len(badge_files)} badges)"
    )


if __name__ == "__main__":
    regenerate_facilitator_notes()
