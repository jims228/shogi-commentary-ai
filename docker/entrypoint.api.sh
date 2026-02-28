#!/usr/bin/env bash
set -eu
cd /app/backend

# Simple entrypoint: run uvicorn on 0.0.0.0:8787
exec uvicorn backend.api.main:app --host 0.0.0.0 --port 8787
