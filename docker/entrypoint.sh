#!/usr/bin/env bash
# PID 1 for the backend image: start server + llm, exit if either dies.
set -euo pipefail
trap 'kill 0' TERM INT

PORT=8000 python /app/server/src/server.py &
CUSTOM_LLM_PORT=8001 python /app/llm/src/custom_llm_server.py &

# Exit (non-zero) as soon as either process exits, so the container restarts.
wait -n
