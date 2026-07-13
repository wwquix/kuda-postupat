#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID} -eq 0 ]] || { echo "Run as root" >&2; exit 1; }
SERVER_NAME="${BSEU_SERVER_NAME:?Set BSEU_SERVER_NAME after reviewing nginx -T}"
BACKEND_PORT="${BSEU_BACKEND_PORT:-8091}"
BASE_PATH="${BSEU_BASE_PATH:-/}"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR=/opt/bseu-admission-monitor
DATA_DIR=/var/lib/bseu-admission-monitor
ENV_FILE=/etc/bseu-admission-monitor.env
DATABASE_PATH="$DATA_DIR/admission.db"
EXPECTED_DATABASE_URL="sqlite:////var/lib/bseu-admission-monitor/admission.db"
NGINX_AVAILABLE=/etc/nginx/sites-available/bseu-admission-monitor.conf
NGINX_ENABLED=/etc/nginx/sites-enabled/bseu-admission-monitor.conf

[[ "$BACKEND_PORT" =~ ^[0-9]+$ ]] || { echo "Invalid BSEU_BACKEND_PORT" >&2; exit 1; }
[[ "$BASE_PATH" == /* ]] || BASE_PATH="/$BASE_PATH"
[[ "$BASE_PATH" == */ ]] || BASE_PATH="$BASE_PATH/"
[[ "$BASE_PATH" =~ ^/[A-Za-z0-9._/-]*/$ ]] || { echo "Invalid BSEU_BASE_PATH" >&2; exit 1; }

echo "=== Preflight: services ==="
systemctl --type=service --state=running --no-pager
echo "=== Preflight: ports ==="
ss -tulpn
echo "=== Preflight: nginx ==="
nginx -T >/tmp/bseu-nginx-before.txt
echo "nginx configuration saved to /tmp/bseu-nginx-before.txt"
echo "=== Preflight: disk and memory ==="
df -h
free -h
echo "=== Preflight: Docker (informational) ==="
docker ps 2>/dev/null || true

if ss -H -ltn "sport = :$BACKEND_PORT" | grep -q .; then
    echo "Port $BACKEND_PORT is occupied; choose BSEU_BACKEND_PORT explicitly." >&2
    exit 1
fi
if [[ -e "$NGINX_AVAILABLE" || -e "$NGINX_ENABLED" ]]; then
    echo "BSEU nginx config already exists; install refuses to overwrite it." >&2
    exit 1
fi

id bseu-admission >/dev/null 2>&1 || useradd --system --home-dir "$PROJECT_DIR" --shell /usr/sbin/nologin bseu-admission
install -d -o bseu-admission -g bseu-admission -m 0750 "$PROJECT_DIR" "$DATA_DIR"
if [[ "$(realpath "$SOURCE_DIR")" != "$(realpath "$PROJECT_DIR")" ]]; then
    tar --exclude=.git --exclude=.env --exclude=.venv --exclude=.runtime --exclude=node_modules --exclude=dist -C "$SOURCE_DIR" -cf - . | tar -C "$PROJECT_DIR" -xf -
fi
chown -R bseu-admission:bseu-admission "$PROJECT_DIR" "$DATA_DIR"
chmod 0755 "$PROJECT_DIR"/deploy/*.sh

if [[ ! -e "$ENV_FILE" ]]; then
    umask 077
    MANUAL_TOKEN="$(openssl rand -hex 32)"
    cat >"$ENV_FILE" <<EOF
SOURCE_URL=https://bseu.by/abiturient/xml/1.xml
SOURCE_PAGE_URL=https://bseu.by/abiturient/
TARGET_SPECIALTIES=Экономическая информатика
STUDY_FORM=дневная
FUNDING_TYPE=платная
USER_SCORE=276
POLL_INTERVAL_MINUTES=10
TIMEZONE=Europe/Minsk
DATABASE_URL=sqlite:////var/lib/bseu-admission-monitor/admission.db
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=1157476891
MANUAL_REFRESH_TOKEN=$MANUAL_TOKEN
REQUEST_TIMEOUT_SECONDS=20
REQUEST_RETRIES=3
STALE_AFTER_MINUTES=30
CORS_ORIGINS=
EOF
    chown bseu-admission:bseu-admission "$ENV_FILE"
    chmod 600 "$ENV_FILE"
fi

DATABASE_URL_VALUE="$(sed -n 's/^DATABASE_URL=//p' "$ENV_FILE" | tail -n 1)"
[[ "$DATABASE_URL_VALUE" == "$EXPECTED_DATABASE_URL" ]] || {
    echo "DATABASE_URL must be the documented production SQLite URL: $EXPECTED_DATABASE_URL" >&2
    exit 1
}
EXISTING_DB=false
if [[ -f "$DATABASE_PATH" ]]; then
    EXISTING_DB=true
    DB_BACKUP_ROOT=/var/backups/bseu-admission-monitor
    DB_BACKUP="$DB_BACKUP_ROOT/admission-before-install-$(date -u +%Y%m%dT%H%M%SZ).db"
    install -d -o bseu-admission -g bseu-admission -m 0700 "$DB_BACKUP_ROOT"
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
fi

python3 -m venv "$PROJECT_DIR/.venv"
"$PROJECT_DIR/.venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/backend/requirements.txt"

command -v npm >/dev/null || { echo "npm is required to build frontend" >&2; exit 1; }
runuser -u bseu-admission -- env VITE_BASE_PATH="$BASE_PATH" npm --prefix "$PROJECT_DIR/frontend" ci
runuser -u bseu-admission -- env VITE_BASE_PATH="$BASE_PATH" npm --prefix "$PROJECT_DIR/frontend" run build

if [[ "$EXISTING_DB" == true ]]; then
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
            "$PROJECT_DIR/.venv/bin/python" -m alembic -c "$PROJECT_DIR/backend/alembic.ini" \
            stamp 0001_legacy_baseline
    fi
fi
runuser -u bseu-admission -- env DATABASE_URL="$DATABASE_URL_VALUE" \
    "$PROJECT_DIR/.venv/bin/python" -m alembic -c "$PROJECT_DIR/backend/alembic.ini" upgrade head

install -o root -g root -m 0644 "$PROJECT_DIR/deploy/bseu-admission-monitor.service" /etc/systemd/system/bseu-admission-monitor.service
sed -i "s/--port 8091/--port $BACKEND_PORT/" /etc/systemd/system/bseu-admission-monitor.service

BASE_REGEX="$(python3 -c 'import re,sys; print(re.escape(sys.argv[1]))' "$BASE_PATH")"
sed -e "s|__SERVER_NAME__|$SERVER_NAME|g" \
    -e "s|__BACKEND_PORT__|$BACKEND_PORT|g" \
    -e "s|__BASE_PATH_REGEX__|$BASE_REGEX|g" \
    -e "s|__BASE_PATH__|$BASE_PATH|g" \
    "$PROJECT_DIR/deploy/nginx-bseu-admission-monitor.conf" >"$NGINX_AVAILABLE"
ln -s "$NGINX_AVAILABLE" "$NGINX_ENABLED"

systemctl daemon-reload
systemctl enable --now bseu-admission-monitor
nginx -t
systemctl reload nginx
BSEU_BACKEND_PORT="$BACKEND_PORT" "$PROJECT_DIR/deploy/healthcheck.sh"
echo "Installed. Configure TLS for: $SERVER_NAME"
