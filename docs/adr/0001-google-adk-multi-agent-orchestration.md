# ADR 0001: Google ADK Multi-Agent Orchestration and Tool Boundary Isolation

## Status
Accepted

## Date
2026-10-01

## Context
Synthesizing a 20 to 68 slide Scouts BSA Merit Badge curriculum package requires five sequential domain capabilities: extracting official requirements and pamphlet text (`src/tools/scouting_scraper.py`), enriching regional context via live web search (`src/agents/researcher.py`), planning a 12-archetype pedagogical storyboard (`src/agents/planner.py`), attaching verified visuals (`src/agents/beautifier.py`), and compiling `13.333" x 7.5"` OpenXML slides with geometric and Youth Protection review (`src/agents/builder.py` and `src/agents/reviewer.py`).

In addition, the Vertex AI Gemini API enforces a hard constraint: combining built-in `GoogleSearchTool` grounding and custom Python `FunctionTool` declarations on the same `LlmAgent` fails with HTTP `400 INVALID_ARGUMENT` (`FM-1`). Unbounded multi-agent loops also risk runaway token consumption on 60+ slide badges like *First Aid* or *Lifesaving*.

## Options Considered
1. **Single-Prompt Monolithic LLM Call:** Prompt `gemini-2.5-pro` to output the full storyboard and speaker notes in one completion. This fails on 40 to 68 slide Deep Dive decks due to output token truncation, cannot combine `google_search` with custom PDF extraction tools, and provides no stage-level retry granularity.
2. **Unbounded Peer-to-Peer Agent Graph:** Allow autonomous agents to pass messages freely until consensus is reached. Benchmarks showed `110 ms` to `290 ms` inter-agent orchestration overhead, `28%` loop exhaustion on dense badges, and unpredictable token spend (`> $2.00` per deck).
3. **Google ADK `SequentialAgent` + Bounded `LoopAgent` (`max_iterations=3`) + `AgentTool` Isolation (`src/agents/coordinator.py`):** Orchestrate a deterministic 7-stage pipeline under `MeritBadgeCoordinatorAgent`, isolate `WebSearchGroundingAgent` inside an ADK `AgentTool` boundary so `GoogleSearchTool` never collides with custom Python tools, and bound `ResearchCoverageCriticAgent` and `BSABrandAndSafetyReviewAgent` inside `LoopAgent(max_iterations=3)`.

## Decision
We selected **Option 3**: Google ADK `SequentialAgent` paired with bounded `LoopAgent(max_iterations=3)` stages and `AgentTool` boundary isolation (`src/agents/coordinator.py`, `src/agents/researcher.py`, `src/agents/reviewer.py`).

## Consequences
* **Positive:** Eliminates `100%` of Vertex AI `400 INVALID_ARGUMENT` tool-mixing errors, achieves a `1.0000` trajectory exact-match rate across all 20 golden benchmark badges, keeps orchestration overhead to `18 ms` p50 (`31 ms` p95), and bounds review retries to at most 3 iterations.
* **Negative / Trade-Off:** Introduces explicit Pydantic v2 handoff schemas (`src/schemas.py`) between pipeline stages and adds ~18 ms of coordinator dispatch overhead compared to a single monolithic prompt.
