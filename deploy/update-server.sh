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
DATA_DIR=/var/lib/bseu-admission-monitor
ENV_FILE=/etc/bseu-admission-monitor.env
DB_BACKUP_ROOT=/var/backups/bseu-admission-monitor
DATABASE_PATH="$DATA_DIR/admission.db"
EXPECTED_DATABASE_URL="sqlite:////var/lib/bseu-admission-monitor/admission.db"
[[ "$BASE_PATH" == /* ]] || BASE_PATH="/$BASE_PATH"
[[ "$BASE_PATH" == */ ]] || BASE_PATH="$BASE_PATH/"
[[ "$BASE_PATH" =~ ^/[A-Za-z0-9._/-]*/$ ]] || { echo "Invalid BSEU_BASE_PATH" >&2; exit 1; }

[[ -f "$ENV_FILE" ]] || { echo "Environment file not found: $ENV_FILE" >&2; exit 1; }
DATABASE_URL_VALUE="$(sed -n 's/^DATABASE_URL=//p' "$ENV_FILE" | tail -n 1)"
[[ "$DATABASE_URL_VALUE" == "$EXPECTED_DATABASE_URL" ]] || {
    echo "DATABASE_URL must be the documented production SQLite URL: $EXPECTED_DATABASE_URL" >&2
    exit 1
}
[[ -f "$DATABASE_PATH" ]] || { echo "SQLite database not found" >&2; exit 1; }
systemctl stop bseu-admission-monitor
install -d -o bseu-admission -g bseu-admission -m 0700 "$DB_BACKUP_ROOT"
DB_BACKUP="$DB_BACKUP_ROOT/admission-before-update-$(date -u +%Y%m%dT%H%M%SZ).db"
python3 - "$DATABASE_PATH" "$DB_BACKUP" <<'PY'
import sqlite3
import sys

source_path, backup_path = sys.argv[1:]
with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True) as source, sqlite3.connect(backup_path) as backup:
    source.backup(backup)
    if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise SystemExit("SQLite backup integrity check failed")
    if list(backup.execute("PRAGMA foreign_key_check")):
        raise SystemExit("SQLite backup foreign key check failed")
PY
chown bseu-admission:bseu-admission "$DB_BACKUP"
chmod 0600 "$DB_BACKUP"
echo "SQLite backup created before migration: $DB_BACKUP"

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
HAS_ALEMBIC_REVISION="$("$PROJECT_DIR/.venv/bin/python" - "$DATABASE_PATH" <<'PY'
import sqlite3
import sys

with sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True) as connection:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'"
    ).fetchone()
    revision = connection.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone() if exists else None
print("yes" if revision else "no")
PY
)"
if [[ "$HAS_ALEMBIC_REVISION" != yes ]]; then
    runuser -u bseu-admission -- env DATABASE_URL="$DATABASE_URL_VALUE" PYTHONPATH="$PROJECT_DIR/backend" \
        "$PROJECT_DIR/.venv/bin/python" -m app.schema verify-legacy
    runuser -u bseu-admission -- env DATABASE_URL="$DATABASE_URL_VALUE" \
        "$PROJECT_DIR/.venv/bin/python" -m alembic -c "$PROJECT_DIR/backend/alembic.ini" stamp 0001_legacy_baseline
fi
runuser -u bseu-admission -- env DATABASE_URL="$DATABASE_URL_VALUE" \
    "$PROJECT_DIR/.venv/bin/python" -m alembic -c "$PROJECT_DIR/backend/alembic.ini" upgrade head
systemctl start bseu-admission-monitor
BSEU_BACKEND_PORT="$BACKEND_PORT" "$PROJECT_DIR/deploy/healthcheck.sh"
echo "Update completed. Code rollback: $PROJECT_DIR/deploy/rollback-server.sh $BACKUP_DIR"
echo "Database backup: $DB_BACKUP"
