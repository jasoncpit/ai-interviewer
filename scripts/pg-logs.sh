#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="postgres"

if ! docker compose ps "${SERVICE_NAME}" >/dev/null 2>&1; then
  echo "[pg-logs] Compose service '${SERVICE_NAME}' not found."
  exit 1
fi

echo "[pg-logs] Tailing logs for '${SERVICE_NAME}' (Ctrl+C to stop)..."
docker compose logs -f --tail=200 "${SERVICE_NAME}"
