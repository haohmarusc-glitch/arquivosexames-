#!/usr/bin/env bash
# Painel novo (React + API). Liga somente em 127.0.0.1; acesse por tunel SSH.
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export ANALISADOR_RESULT_DIR="${ANALISADOR_RESULT_DIR:-/srv/saude/painel}"

if [[ ! -f "$SCRIPT_DIR/frontend/dist/index.html" ]]; then
  echo "Frontend nao compilado. Rode: cd frontend && npm ci && npm run build" >&2
  exit 1
fi

cd "$SCRIPT_DIR"
exec "$SCRIPT_DIR/.venv/bin/uvicorn" api:app --host 127.0.0.1 --port "${PAINEL_PORTA:-8502}" --no-server-header
