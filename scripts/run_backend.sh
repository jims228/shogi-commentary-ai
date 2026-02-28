#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# default: LLM OFF
export USE_LLM="${USE_LLM:-0}"

# Load base secrets (root .env is the single source of truth for API keys)
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# Load local overrides on top (ENV_FILE defaults to .env.local)
ENV_OVERRIDE="${ENV_FILE:-.env.local}"
if [[ -f "$ENV_OVERRIDE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_OVERRIDE"
  set +a
fi

# venv
if [ -f backend/api/.venv/bin/activate ]; then
  source backend/api/.venv/bin/activate
fi

export PYTHONPATH=.

# Safety: require explicit enable + key
if [[ "${USE_LLM:-0}" == "1" ]]; then
  : "${LLM_PROVIDER:=gemini}"
  if [[ "${LLM_PROVIDER}" == "gemini" && -z "${GEMINI_API_KEY:-}" ]]; then
    echo "ERROR: USE_LLM=1 but GEMINI_API_KEY is empty" >&2
    exit 1
  fi
  if [[ "${LLM_PROVIDER}" == "openai" && -z "${OPENAI_API_KEY:-}" ]]; then
    echo "ERROR: USE_LLM=1 but OPENAI_API_KEY is empty" >&2
    exit 1
  fi
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8787}"
RELOAD="${RELOAD:-1}"

# Start bioshogi Ruby/Sinatra microservice (requires Ruby >= 3.2 via rbenv)
BIOSHOGI_DIR="$(pwd)/bioshogi_service"
RUBY_BIN="${HOME}/.rbenv/versions/3.2.2/bin"
if [[ -f "${RUBY_BIN}/ruby" && -f "${BIOSHOGI_DIR}/server.rb" ]]; then
  if ! curl -sf http://localhost:7070/health >/dev/null 2>&1; then
    echo "== Starting bioshogi service on :7070 =="
    (
      cd "${BIOSHOGI_DIR}"
      PATH="${RUBY_BIN}:/usr/bin:${PATH}" \
      GEM_HOME="${HOME}/.rbenv/versions/3.2.2/lib/ruby/gems/3.2.0" \
      GEM_PATH="vendor/bundle/ruby/3.2.0:${HOME}/.rbenv/versions/3.2.2/lib/ruby/gems/3.2.0" \
      "${RUBY_BIN}/bundle" exec ruby server.rb &>> /tmp/bioshogi.log &
    )
  else
    echo "== bioshogi service already running on :7070 =="
  fi
else
  echo "== bioshogi: Ruby 3.2+ not found at ${RUBY_BIN}, skipping =="
fi

echo "== Backend starting on :${PORT} (USE_LLM=${USE_LLM}, LLM_PROVIDER=${LLM_PROVIDER:-unset}) =="

uvicorn_args=(backend.api.main:app --host "$HOST" --port "$PORT")
if [[ "$RELOAD" == "1" ]]; then
  uvicorn_args+=(--reload)
fi

exec uvicorn "${uvicorn_args[@]}"
