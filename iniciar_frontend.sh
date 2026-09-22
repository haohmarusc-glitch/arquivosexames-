#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export ANALISADOR_RESULT_DIR="${ANALISADOR_RESULT_DIR:-/srv/saude/painel}"

exec "$SCRIPT_DIR/.venv/bin/streamlit" run "$SCRIPT_DIR/frontend.py" \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.headless true \
  --browser.gatherUsageStats false
