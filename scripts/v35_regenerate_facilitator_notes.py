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
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
REQ_DIR = ROOT / "data" / "merit_badge_requirements"
FACILITATOR_NOTES_PATH = ROOT / "data" / "precomputed_facilitator_notes_149.json"


def clean_prose(text: str) -> str:
    """Normalizes whitespace and strips em/en dashes and double hyphens."""
    if not text:
        return ""
    s = str(text)
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
) -> str:
    """Builds a rich, Socratic, role-specific 5-Part Facilitator Guide note for a specific slide index."""
    clean_b = clean_prose(badge_name)
    clean_r = clean_prose(req_id)
    clean_tp = clean_prose(topic_phrase).replace(f"Req {clean_r}:", "").strip() or f"{clean_b} Req {clean_r}"
    cite = clean_prose(page_cite or f"Official {clean_b} Merit Badge Pamphlet, Req {clean_r}")

    if clean_r.lower() == "cover":
        return "\n".join([
            f"[PACING & MODALITY] 2 min | Session Launch | EDGE: Explain | {cite}. [Gesture to the title slide] Welcome to the {clean_b} Merit Badge clinic, Scouts! Confirm every buddy pair has their {clean_b} Workbook and Blue Card (#34124) ready.",
            f"[ASK SCOUTS FIRST] What real-world skill or outdoor challenge made you want to earn the {clean_b} Merit Badge today?",
            f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. [Expected Answer: Scouts share their personal goals while connecting {clean_b} to the Scout Oath, Scout Law, and Outdoor Code.]",
            "[COMMON MISCONCEPTION TO CORRECT] Myth: Group attendance alone completes a Merit Badge. | BSA Pamphlet Fact: Under Guide to Advancement Section 7.0.3.2, each Scout must individually demonstrate or explain every requirement as written.",
            f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Hold up Blue Card #34124 and the {clean_b} Workbook] Verify Scout names, unit numbers, and prerequisite preparation before moving to the Requirements Overview.",
        ])

    if clean_r.lower() == "overview":
        return "\n".join([
            f"[PACING & MODALITY] 3 min | Syllabus Roadmap | EDGE: Explain & Plan | {cite}. [Point to the Requirements Triage Matrix] Walk Patrols through the three requirement tracks for {clean_b}: In-Class Discussions, Hands-On Skill Stations, and Home/Troop Prerequisites.",
            f"[ASK SCOUTS FIRST] Looking at our {clean_b} roadmap, which requirements demand field logs or hands-on demonstrations versus patrol discussion?",
            f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. [Expected Answer: In-class concepts are discussed together, skill stations use the BSA EDGE method with buddy pairs, and prerequisite logs require documented field evidence.]",
            "[COMMON MISCONCEPTION TO CORRECT] Myth: Unfinished prerequisites mean starting over after camp. | BSA Pamphlet Fact: Signed partial Blue Cards (#34124) remain valid until the Scout's 18th birthday.",
            f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Point to the Workbook Table of Contents] Have Scouts circle their target session milestones in their {clean_b} Fillable Workbook.",
        ])

    if clean_r.lower() == "sources":
        return "\n".join([
            f"[PACING & MODALITY] 2 min | Final Checkout & References | EDGE: Enable | {cite}. [Point to the Official Pamphlet & Resource links] Wrap up the {clean_b} walkthrough and transition to individual counselor sign-off conferences.",
            f"[ASK SCOUTS FIRST] Before stepping up for your final {clean_b} Blue Card (#34124) verification, which workbook tables and field artifacts must you have ready?",
            f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. [Expected Answer: Completed {clean_b} Workbook organizers, any required sketches or logs, and a signed Blue Card or Scoutbook record.]",
            f"[COMMON MISCONCEPTION TO CORRECT] Myth: Once the Blue Card is signed, the workbook notes can be discarded immediately. | BSA Pamphlet Fact: Keep your {clean_b} Workbook and Applicant's Record as permanent proof for Boards of Review.",
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

    myth = clean_prose(str(misc_pair.get("misconception") or f"General familiarity with {clean_tp} is enough without specific {clean_b} pamphlet verification."))
    fact = clean_prose(str(misc_pair.get("fact") or misc_pair.get("fact_correction") or ex1))
    safe_str = f" [Safety Check: {clean_prose(safety_callout)}]" if safety_callout else ""

    soc_q0 = clean_prose(socratic_questions[0]) if socratic_questions and len(socratic_questions) >= 1 and clean_prose(socratic_questions[0]) else ""
    soc_q1 = clean_prose(socratic_questions[1]) if socratic_questions and len(socratic_questions) >= 2 and clean_prose(socratic_questions[1]) else soc_q0

    if role_idx == 0:
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage} | {cite}. "
            f"[Point to Card 1: {clean_tp}] Introduce {clean_tp} for {clean_b} Requirement {clean_r} by unpacking {ensure_sentence_end(ex1)}.{safe_str}"
        )
        ask_q0 = soc_q0 or f"Before reading the pamphlet details on screen, why does {clean_tp} matter in {clean_b}, and where have you seen it in action?"
        ask = f"[ASK SCOUTS FIRST] {ask_q0}"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. {ex1} {ex2} [Expected Answer: Scouts explain the core principle of {clean_tp} in their own words.]"
        rubric = f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Open the {clean_b} Workbook to {wb_title}] Have each Scout record the primary definition and pamphlet facts for Requirement {clean_r} ({cite})."
    elif role_idx == 1:
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage} | {cite}. "
            f"[Step to the demonstration table] Model the step-by-step sequence for {clean_tp} starting with {ensure_sentence_end(pr1)}, then coach buddy pairs as they practice.{safe_str}"
        )
        ask = f"[ASK SCOUTS FIRST] Looking at our procedural sequence for {clean_tp} (Req {clean_r}), why must we complete the first step before advancing to {ensure_sentence_end(pr2)}?"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. {pr1} {pr2} [Expected Answer: Scouts follow the step-by-step sequence for {clean_tp} without skipping safety or verification checks.]"
        rubric = f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Observe live buddy-pair practice] Verify each Scout physically demonstrates or walks through all steps of Requirement {clean_r} per Guide to Advancement Section 7.0.3.2."
    elif role_idx == 2:
        lh = clean_prose(str((comp_data or {}).get("left_header") or f"{clean_tp} Primary Standard"))
        rh = clean_prose(str((comp_data or {}).get("right_header") or f"{clean_tp} Field Application"))
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage} | {cite}. "
            f"[Point to the two comparison columns: {lh} vs. {rh}] Contrast {lh} against {rh} for {clean_b} Requirement {clean_r}.{safe_str}"
        )
        ask = f"[ASK SCOUTS FIRST] How do you distinguish between {lh} and {rh} in the field, and when would your patrol choose one over the other?"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. {ex1} {ex2} [Expected Answer: Scouts contrast {lh} and {rh} using concrete examples from the {clean_b} pamphlet.]"
        rubric = f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Point to {wb_title}] Confirm each Scout compares {lh} and {rh} accurately in their {clean_b} Workbook."
    elif role_idx == 3:
        we_out = clean_prose(str((worked_ex or {}).get("sample_output") or ex1))
        we_tip = clean_prose(str((worked_ex or {}).get("counselor_tip") or f"Verify specific details for {clean_tp} ({cite})."))
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage} | {cite}. "
            f"[Point to the Exemplar Workbook Entry] Show Scouts what a complete, sign-off-ready entry looks like for Requirement {clean_r} ({clean_tp}).{safe_str}"
        )
        ask = f"[ASK SCOUTS FIRST] Comparing a one-word note to this worked example for {clean_tp}, what specific measurements or details make this entry ready for counselor sign-off?"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. {we_out} [Expected Answer: {we_tip}]"
        rubric = f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Inspect individual {clean_b} Workbooks] Check that each Scout's entry in {wb_title} includes their own specific observations and data."
    elif role_idx == 4:
        q_prompt = clean_prose(str((quiz_item or {}).get("scenario_prompt") or f"How should your patrol apply {clean_tp} during {clean_b} Requirement {clean_r}?"))
        q_ans = clean_prose(str((quiz_item or {}).get("correct_answer") or fact))
        q_exp = clean_prose(str((quiz_item or {}).get("explanation") or ex1))
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage} | {cite}. "
            f"[Pose the Patrol Checkpoint Quiz] Give buddy pairs 45 seconds to debate the scenario for {clean_b} Requirement {clean_r} before revealing the answer.{safe_str}"
        )
        ask = f"[ASK SCOUTS FIRST] Scenario Check: \"{q_prompt}\" Which option does your buddy pair select, and why?"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. [Expected Answer: {q_ans} {q_exp}]"
        rubric = f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Poll patrol responses] Have buddy pairs explain why the three distractor choices fail the {clean_b} pamphlet standard."
    elif role_idx == 5:
        g1 = clean_prose(gear_list[0]) if gear_list else f"Required reference materials and field gear for {clean_tp}"
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage} | {cite}. "
            f"[Hold up the station gear: {g1}] Conduct a patrol equipment and safety shakedown for {clean_b} Requirement {clean_r} ({clean_tp}).{safe_str}"
        )
        ask = f"[ASK SCOUTS FIRST] Before starting our hands-on work for {clean_tp}, what inspection check confirms that {g1} is safe and ready for use?"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. {ex1} [Expected Answer: Scouts inspect {g1} and verify scene safety before execution.]"
        rubric = f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Check station readiness] Confirm every buddy pair has inspected their gear and recorded safety checks in {wb_title}."
    else:
        pacing = (
            f"[PACING & MODALITY] {est_min} | {role_name} | EDGE: {edge_stage} | {cite}. "
            f"[Facilitate deep-dive discussion on {clean_tp}] Connect {ensure_sentence_end(ex2)} to real-world application and troubleshooting in {clean_b} Requirement {clean_r}.{safe_str}"
        )
        ask_q1 = soc_q1 or f"If conditions change unexpectedly while applying {clean_tp} in {clean_b}, how should your patrol adapt while staying within the pamphlet standard?"
        ask = f"[ASK SCOUTS FIRST] {ask_q1}"
        key = f"[EXPECTED PAMPHLET ANSWER KEY] Citation: {cite}. {ex2} {ex1} [Expected Answer: Scouts connect {clean_tp} to practical field decision-making and verify their notes in {wb_title}.]"
        rubric = f"[DEMONSTRATION & SIGN-OFF RUBRIC] [Final check for Requirement {clean_r}] Initial Blue Card (#34124) once each Scout individually explains or demonstrates {clean_tp} ({cite})."

    misc = f"[COMMON MISCONCEPTION TO CORRECT] Myth: {myth} | BSA Pamphlet Fact: {fact}"
    return "\n".join(clean_prose(line) for line in (pacing, ask, key, misc, rubric))


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
                    )

    FACILITATOR_NOTES_PATH.write_text(
        json.dumps(notes_map, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        f"Saved {FACILITATOR_NOTES_PATH.name} with {slide_entries_count} unique slide notes "
        f"({len(notes_map)} total lookup keys across {len(badge_files)} badges)"
    )


if __name__ == "__main__":
    regenerate_facilitator_notes()
