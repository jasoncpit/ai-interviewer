#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/src"

# Load optional .env file so OPENAI_API_KEY and other settings are available
if [[ -f "$ROOT_DIR/.env" ]]; then
  # shellcheck disable=SC2046
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi

if [[ -z "${OPENAI_API_KEY:-${openai_api_key:-}}" ]]; then
  cat <<'EOF'
Warning: OPENAI_API_KEY is not set. The interviewer service requires an OpenAI key.
Add it to .env or export OPENAI_API_KEY before running this script.
EOF
  sleep 1
fi

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
