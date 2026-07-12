#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID} -eq 0 ]] || { echo "Run as root" >&2; exit 1; }
PROJECT_DIR=/opt/bseu-admission-monitor
BACKUP_ROOT=/opt/bseu-admission-monitor-rollbacks
BACKUP_DIR="${1:-$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)}"
BASE_PATH="${BSEU_BASE_PATH:-/}"
BACKEND_PORT="${BSEU_BACKEND_PORT:-8091}"
[[ -n "$BACKUP_DIR" && -d "$BACKUP_DIR" ]] || { echo "Rollback copy not found" >&2; exit 1; }
[[ "$BASE_PATH" == /* ]] || BASE_PATH="/$BASE_PATH"
[[ "$BASE_PATH" == */ ]] || BASE_PATH="$BASE_PATH/"
[[ "$BASE_PATH" =~ ^/[A-Za-z0-9._/-]*/$ ]] || { echo "Invalid BSEU_BASE_PATH" >&2; exit 1; }

systemctl stop bseu-admission-monitor
tar --exclude=.venv --exclude=node_modules --exclude=dist -C "$BACKUP_DIR" -cf - . | tar -C "$PROJECT_DIR" -xf -
chown -R bseu-admission:bseu-admission "$PROJECT_DIR"
chmod 0755 "$PROJECT_DIR"/deploy/*.sh
"$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/backend/requirements.txt"
runuser -u bseu-admission -- env VITE_BASE_PATH="$BASE_PATH" npm --prefix "$PROJECT_DIR/frontend" ci
runuser -u bseu-admission -- env VITE_BASE_PATH="$BASE_PATH" npm --prefix "$PROJECT_DIR/frontend" run build
systemctl start bseu-admission-monitor
BSEU_BACKEND_PORT="$BACKEND_PORT" "$PROJECT_DIR/deploy/healthcheck.sh"
echo "Rollback completed from $BACKUP_DIR"
