#!/usr/bin/env bash
set -euo pipefail

# Deploy the CDK stack that provisions ECR repositories for the Prolific interviewer project.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$ROOT_DIR/infra"
VENV_DIR="$INFRA_DIR/.venv"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--context KEY=VALUE ...] [--no-venv]

Options:
  --context KEY=VALUE   Pass a context override to CDK (may be repeated).
  --no-venv             Assume dependencies are already installed; skip venv setup.
  -h, --help            Show this help message.

Examples:
  $(basename "$0")
  $(basename "$0") --context repo_names='["service","ui"]'
  $(basename "$0") --context cross_account_ids='["123456789012"]'
USAGE
}

CONTEXT_ARGS=()
SETUP_VENV=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --context)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --context" >&2
        exit 1
      fi
      CONTEXT_ARGS+=(-c "$2")
      shift 2
      ;;
    --context=*)
      CONTEXT_ARGS+=(-c "${1#*=}")
      shift
      ;;
    --no-venv)
      SETUP_VENV=false
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -d "$INFRA_DIR" ]]; then
  echo "[cdk-deploy] infra directory not found at $INFRA_DIR" >&2
  exit 1
fi

pushd "$INFRA_DIR" >/dev/null

if $SETUP_VENV; then
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "[cdk-deploy] Creating Python virtual environment in $VENV_DIR"
    python -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
  echo "[cdk-deploy] Installing CDK requirements"
  pip install --upgrade pip >/dev/null
  pip install -r requirements.txt
else
  echo "[cdk-deploy] Skipping venv setup (caller opted out)"
fi

if [[ -z "${CDK_DEFAULT_ACCOUNT:-}" || -z "${CDK_DEFAULT_REGION:-}" ]]; then
  echo "[cdk-deploy] Warning: CDK_DEFAULT_ACCOUNT or CDK_DEFAULT_REGION not set."
  echo "             Ensure AWS credentials are configured before deploying."
fi

echo "[cdk-deploy] Synthesising and deploying ECR stack via CDK"
cdk deploy "${CONTEXT_ARGS[@]}"

popd >/dev/null

echo "[cdk-deploy] Done."
