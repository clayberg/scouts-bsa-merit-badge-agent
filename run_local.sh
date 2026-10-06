#!/usr/bin/env bash
# Quick start script for local execution of Scouts BSA Merit Badge Agent (v2.0)
# Modes:
#   ./run_local.sh            -> Starts BOTH Material 3 Expressive A2UI (:8085) AND Streamlit v2.0 (:8501)
#   ./run_local.sh a2ui       -> Starts only Material 3 Expressive A2UI (:8085)
#   ./run_local.sh streamlit  -> Starts only Streamlit v2.0 (:8501)
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [ ! -f .env ] && [ -f .env.example ]; then
  echo "⚠️  No .env file found. Copying from .env.example..."
  cp .env.example .env
fi

export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/matplotlib}"
PORT="${PORT:-8085}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"
HOST_FQDN="$(hostname -f 2>/dev/null || echo localhost)"
MODE="${1:-both}"

if [ "${MODE}" = "streamlit" ]; then
  pkill -f "streamlit run src/app.py.*--server.port ${STREAMLIT_PORT}" 2>/dev/null || true
  echo "🚀 Starting Scouts BSA Streamlit v2.0 Counselor Workbench on http://${HOST_FQDN}:${STREAMLIT_PORT} ..."
  exec .venv/bin/streamlit run src/app.py --server.address 0.0.0.0 --server.port "${STREAMLIT_PORT}" --server.headless true
elif [ "${MODE}" = "a2ui" ]; then
  pkill -f "uvicorn src.server:app.*--port ${PORT}" 2>/dev/null || true
  echo "🚀 Starting Scouts BSA Google Material 3 Expressive A2UI Workbench on http://${HOST_FQDN}:${PORT} ..."
  exec .venv/bin/uvicorn src.server:app --host 0.0.0.0 --port "${PORT}"
else
  pkill -f "uvicorn src.server:app.*--port ${PORT}" 2>/dev/null || true
  pkill -f "streamlit run src/app.py.*--server.port ${STREAMLIT_PORT}" 2>/dev/null || true
  echo "🚀 Starting BOTH Counselor Workbenches:"
  echo "   1. Google Material 3 Expressive A2UI : http://${HOST_FQDN}:${PORT}"
  echo "   2. Streamlit v2.0 Counselor UI       : http://${HOST_FQDN}:${STREAMLIT_PORT}"
  .venv/bin/streamlit run src/app.py --server.address 0.0.0.0 --server.port "${STREAMLIT_PORT}" --server.headless true &
  STREAMLIT_PID=$!
  trap "kill ${STREAMLIT_PID} 2>/dev/null || true" EXIT INT TERM
  .venv/bin/uvicorn src.server:app --host 0.0.0.0 --port "${PORT}"
fi
