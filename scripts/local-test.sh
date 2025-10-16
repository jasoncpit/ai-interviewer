#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/src"

# Provide DB-less defaults for local development
export DATABASE_URL="sqlite:///$SRC_DIR/prolific_local.db"
export AGENT_SERVICE_URL="http://127.0.0.1:8080"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install from https://github.com/astral-sh/uv."
  exit 1
fi

echo "Starting FastAPI interviewer service…"
pushd "$SRC_DIR" >/dev/null
if command -v uv >/dev/null 2>&1; then
  uv run uvicorn app.service.service:app --host 127.0.0.1 --port 8080 --reload &
else
  python -m uvicorn app.service.service:app --host 127.0.0.1 --port 8080 --reload &
fi
UVICORN_PID=$!
popd >/dev/null

cleanup() {
  echo "Stopping services…"
  kill "$UVICORN_PID" "$STREAMLIT_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

sleep 2

echo "Launching Streamlit operator console…"
pushd "$SRC_DIR" >/dev/null
streamlit run streamlit_app.py --server.headless true --server.port 8501 &
STREAMLIT_PID=$!
popd >/dev/null

echo "FastAPI PID: $UVICORN_PID"
echo "Streamlit PID: $STREAMLIT_PID"
echo "Open http://localhost:8501 to interact with the interviewer."

wait "$UVICORN_PID" "$STREAMLIT_PID"
