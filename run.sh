#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
HOST="${ARCLENS_HOST:-127.0.0.1}"
PORT="${ARCLENS_PORT:-8000}"

if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

EXTRA=()
if [[ "${1:-}" == "--reload" ]]; then
  EXTRA+=(--reload)
fi

echo "ArcLens listening on http://${HOST}:${PORT}"
echo "UI /   API docs /docs   samples /api/samples"
exec python -m uvicorn app.main:app --host "$HOST" --port "$PORT" "${EXTRA[@]}"
