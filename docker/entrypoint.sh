#!/usr/bin/env bash
# PID 1 for the combined image: start server + llm + web, exit if any dies.
set -euo pipefail
trap 'kill 0' TERM INT

# Each process gets its OWN port inline — both FastAPI and Next read $PORT,
# so they must not share one value.
PORT="${BACKEND_PORT:-8000}" /opt/venv/bin/python /app/server/src/server.py &
CUSTOM_LLM_PORT="${CUSTOM_LLM_PORT:-8001}" /opt/venv/bin/python /app/llm/src/custom_llm_server.py &
PORT="${WEB_PORT:-3000}" HOSTNAME=0.0.0.0 node /app/web/server.js &

# Exit (non-zero) as soon as any one process exits, so the container restarts.
wait -n
