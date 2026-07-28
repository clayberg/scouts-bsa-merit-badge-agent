#!/usr/bin/env bash
# Quick start script for local/laptop execution of Scouts BSA Merit Badge Agent
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [ ! -f .env ]; then
  echo "⚠️  No .env file found. Copying from .env.example..."
  cp .env.example .env
  echo "👉 Please edit .env to set your GEMINI_API_KEY before continuing."
fi

echo "🚀 Starting Scouts BSA Merit Badge Agent Streamlit Interface..."
streamlit run src/app.py --server.port 8501 --server.address localhost
