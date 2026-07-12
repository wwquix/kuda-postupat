#!/usr/bin/env bash
set -Eeuo pipefail

BACKEND_PORT="${BSEU_BACKEND_PORT:-8091}"
curl --fail --silent --show-error --max-time 10 "http://127.0.0.1:${BACKEND_PORT}/api/health" >/dev/null
systemctl is-active --quiet bseu-admission-monitor
echo "bseu-admission-monitor: healthy on 127.0.0.1:${BACKEND_PORT}"
