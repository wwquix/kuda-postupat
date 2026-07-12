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

python3 -m venv "$PROJECT_DIR/.venv"
"$PROJECT_DIR/.venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/backend/requirements.txt"

command -v npm >/dev/null || { echo "npm is required to build frontend" >&2; exit 1; }
runuser -u bseu-admission -- env VITE_BASE_PATH="$BASE_PATH" npm --prefix "$PROJECT_DIR/frontend" ci
runuser -u bseu-admission -- env VITE_BASE_PATH="$BASE_PATH" npm --prefix "$PROJECT_DIR/frontend" run build

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
