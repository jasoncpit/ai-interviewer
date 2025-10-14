#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT_DIR"

echo "[deploy-dev] Building and starting docker compose stack..."
docker compose up --build -d

echo "[deploy-dev] Waiting for services to report healthy..."
docker compose ps

echo "[deploy-dev] Services running."
echo "- API: http://localhost:8080/info"
echo "- Streamlit: http://localhost:8501"
