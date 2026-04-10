#!/usr/bin/env bash

set -euo pipefail

PIDS="$(pgrep -f 'uvicorn app.main:app --host 127.0.0.1 --port 8000' || true)"

if [ -z "${PIDS}" ]; then
  echo "No backend process found on 127.0.0.1:8000"
  exit 0
fi

echo "${PIDS}" | xargs kill
echo "Stopped backend process: ${PIDS}"
