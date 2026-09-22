#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE_DIR="${ANALISADOR_BASE_DIR:-/srv/saude/processamento}"
REMOTE_SOURCE="${ANALISADOR_REMOTE_SOURCE:-saude-crypt:exames/Exames_Unimed_2023-2026.zip}"
REMOTE_OUTPUT="${ANALISADOR_REMOTE_OUTPUT:-saude-crypt:historico/ultima-analise}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$(mktemp -d "$BASE_DIR.XXXXXX")"

cleanup() {
  [[ "$RUN_DIR" == "$BASE_DIR".* ]] || return 1
  find "$RUN_DIR" -type f -exec shred -u {} + 2>/dev/null || true
  rm -rf -- "$RUN_DIR"
}
trap cleanup EXIT

mkdir -p "$RUN_DIR/entrada" "$RUN_DIR/resultado"
rclone copyto "$REMOTE_SOURCE" "$RUN_DIR/entrada/exames.zip"

if [[ ! -d "$SCRIPT_DIR/.venv" ]]; then
  python3 -m venv "$SCRIPT_DIR/.venv"
  "$SCRIPT_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/analisar_exames.py" \
  "$RUN_DIR/entrada/exames.zip" --saida "$RUN_DIR/resultado"

rclone copy "$RUN_DIR/resultado" "$REMOTE_OUTPUT" --create-empty-src-dirs
rclone check "$RUN_DIR/resultado" "$REMOTE_OUTPUT" --one-way --download

echo "Analise concluida e enviada para $REMOTE_OUTPUT"
