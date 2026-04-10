#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${BACKEND_DIR}"

if [ ! -d ".venv" ]; then
  echo "Missing virtual environment: ${BACKEND_DIR}/.venv" >&2
  echo "Create it first, then install backend dependencies." >&2
  exit 1
fi

source .venv/bin/activate
exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
