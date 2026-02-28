#!/usr/bin/env bash
set -euo pipefail

# safe defaults
NEXT_DEV=${NEXT_DEV:-0}
PORT=${PORT:-3000}
export NEXT_TELEMETRY_DISABLED=${NEXT_TELEMETRY_DISABLED:-1}

cd /app/apps/web

# Load env if exists (do not overwrite existing env vars)
if [ -f /app/.env ]; then
  while IFS= read -r line; do
    [[ -z "$line" || "$line" =~ ^\s*# ]] && continue
    key="${line%%=*}"
    if [ -z "${!key-}" ]; then
      export "$line"
    fi
  done < /app/.env
fi

if [ "${NEXT_DEV}" = "1" ] || [ "${NEXT_DEV}" = "true" ]; then
  echo "Starting next dev on port ${PORT}"
  exec npm run dev -- --port "${PORT}"
else
  echo "Starting next start (production) on port ${PORT}"
  exec npm run start -- -p "${PORT}"
fi
