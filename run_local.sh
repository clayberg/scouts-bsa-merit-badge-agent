#!/usr/bin/env bash
# Quick start script for local execution of the Scouts BSA Merit Badge Counselor Workbench
# Usage:
#   ./run_local.sh          -> Starts the Material 3 Expressive A2UI Counselor Workbench (:8085)
#   PORT=8080 ./run_local.sh -> Starts on custom port (:8080)
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [ ! -f .env ] && [ -f .env.example ]; then
  echo "⚠️  No .env file found. Copying from .env.example..."
  cp .env.example .env
fi

export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/matplotlib}"
PORT="${PORT:-8085}"
HOST_FQDN="$(hostname -f 2>/dev/null || echo localhost)"

pkill -f "uvicorn src.server:app.*--port ${PORT}" 2>/dev/null || true
echo "🚀 Starting Scouts BSA Merit Badge Counselor Workbench on http://${HOST_FQDN}:${PORT} ..."
exec .venv/bin/uvicorn src.server:app --host 0.0.0.0 --port "${PORT}"

