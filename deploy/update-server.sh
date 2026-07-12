#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID} -eq 0 ]] || { echo "Run as root" >&2; exit 1; }
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR=/opt/bseu-admission-monitor
BACKUP_ROOT=/opt/bseu-admission-monitor-rollbacks
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
BASE_PATH="${BSEU_BASE_PATH:-/}"
BACKEND_PORT="${BSEU_BACKEND_PORT:-8091}"
[[ "$BASE_PATH" == /* ]] || BASE_PATH="/$BASE_PATH"
[[ "$BASE_PATH" == */ ]] || BASE_PATH="$BASE_PATH/"
[[ "$BASE_PATH" =~ ^/[A-Za-z0-9._/-]*/$ ]] || { echo "Invalid BSEU_BASE_PATH" >&2; exit 1; }

install -d -m 0750 "$BACKUP_DIR"
tar --exclude=.venv --exclude=.runtime --exclude=node_modules --exclude=dist -C "$PROJECT_DIR" -cf - . | tar -C "$BACKUP_DIR" -xf -
echo "Rollback copy: $BACKUP_DIR"

if [[ "$(realpath "$SOURCE_DIR")" != "$(realpath "$PROJECT_DIR")" ]]; then
    tar --exclude=.git --exclude=.env --exclude=.venv --exclude=.runtime --exclude=node_modules --exclude=dist -C "$SOURCE_DIR" -cf - . | tar -C "$PROJECT_DIR" -xf -
fi
chown -R bseu-admission:bseu-admission "$PROJECT_DIR"
chmod 0755 "$PROJECT_DIR"/deploy/*.sh
"$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/backend/requirements.txt"
runuser -u bseu-admission -- env VITE_BASE_PATH="$BASE_PATH" npm --prefix "$PROJECT_DIR/frontend" ci
runuser -u bseu-admission -- env VITE_BASE_PATH="$BASE_PATH" npm --prefix "$PROJECT_DIR/frontend" run build
systemctl restart bseu-admission-monitor
BSEU_BACKEND_PORT="$BACKEND_PORT" "$PROJECT_DIR/deploy/healthcheck.sh"
echo "Update completed. Rollback: $PROJECT_DIR/deploy/rollback-server.sh $BACKUP_DIR"
