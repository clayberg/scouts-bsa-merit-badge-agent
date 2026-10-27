# ADR 0003: Dual-Transport Model Context Protocol (MCP) Server and A2UI SSE Streaming

## Status
Accepted

## Date
2026-10-08

## Context
Merit Badge Counselors interact with the platform in two distinct ways:
1. Through the interactive browser-based **Material 3 Expressive A2UI v0.9 Counselor Workbench** (`ui/index.html`, `ui/app.js`, `src/server.py`), which requires real-time Server-Sent Events (SSE) progress updates, live 16:9 slide stage rendering, and honest separation between initial status events and first meaningful content tokens.
2. Through external AI coding and desktop assistants (Claude Desktop, Gemini CLI, Cursor) that consume standardized **Model Context Protocol (MCP)** tools, resources, and guided prompts over either `stdio` or HTTP JSON-RPC 2.0 (`POST /mcp`).

Maintaining separate backend implementations for the web UI and MCP clients would duplicate validation, PII scrubbing, and FinOps guardrails.

## Options Considered
1. **REST-Only Backend + Separate Standalone MCP Microservice:** Duplicates tool schemas across two codebases and risks inconsistent security or FinOps enforcement between HTTP callers and MCP clients.
2. **Legacy Dual Streamlit (`:8501`) + FastAPI (`:8085`) Frontends:** Prevents pixel-accurate 16:9 slide stage rendering, split-screen presenter mode (`P`), and consolidated Material 3 toolbars.
3. **Unified FastAPI A2UI v0.9 Workbench + Dual-Transport MCP Server (`src/mcp_server.py` & `src/server.py`):** Mount `POST /mcp`, `GET /mcp/info`, and `GET /mcp/sse` directly on the primary FastAPI application alongside the `scouts-bsa-mcp` `stdio` CLI entrypoint, exposing 27 capabilities (`15` tools, `7` `bsa://` resources, `5` prompts) and streaming SSE progress frames (`first_status_event_ms` vs. `true_first_content_token_ms`) scrubbed by `scrub_pii_from_structure()`.

## Decision
We selected **Option 3**: Unified FastAPI Material 3 A2UI v0.9 Workbench (`141` OpenAPI 3.1 endpoints) with co-hosted Dual-Transport MCP (`stdio` + `POST /mcp` JSON-RPC 2.0) and honest dual-timestamp SSE streaming.

## Consequences
* **Positive:** Exposes all 27 MCP capabilities (`15` tools, `7` resources, `5` prompts) through both `stdio` and HTTP without duplicating business logic, enables the in-app `MCP Hub` interactive playground, and provides honest SSE telemetry (`first_status_event_ms` p50 = `6.5 ms`, `true_first_content_token_ms` p50 = `185.0 ms`).
* **Negative / Trade-Off:** Requires strict OpenAPI 3.1 contract synchronization (`docs/openapi.yaml`) and JSON-RPC 2.0 schema validation across all 141 HTTP paths.
