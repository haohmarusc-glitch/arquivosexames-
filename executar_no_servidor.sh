#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Configuracao local (fora do Git), ex.: ANALISADOR_SEXO=M
ENV_FILE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/.env"
if [[ -f "$ENV_FILE" ]]; then set -a; source "$ENV_FILE"; set +a; fi

BASE_DIR="${ANALISADOR_BASE_DIR:-/srv/saude/processamento}"
REMOTE_SOURCE="${ANALISADOR_REMOTE_SOURCE:-saude-crypt:exames/Exames_Unimed_2023-2026.zip}"
REMOTE_OUTPUT="${ANALISADOR_REMOTE_OUTPUT:-saude-crypt:historico/ultima-analise}"
LOCAL_PANEL_DIR="${ANALISADOR_PANEL_DIR:-/srv/saude/painel}"
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

install -d -m 700 "$LOCAL_PANEL_DIR"
cp -f "$RUN_DIR/resultado"/* "$LOCAL_PANEL_DIR"/
chmod 600 "$LOCAL_PANEL_DIR"/*

echo "Analise concluida, enviada para $REMOTE_OUTPUT e disponibilizada em $LOCAL_PANEL_DIR"
