#!/usr/bin/env bash
# PID 1 for the combined image: start server + llm + web, exit if any dies.
set -euo pipefail
trap 'kill 0' TERM INT

# Fixed internal ports, set inline per process: the backend (server.py) and the
# Next server both read $PORT, so they must not share one value; the llm server
# reads $CUSTOM_LLM_PORT. Map them out with `docker run -p`.
PORT=8000 /opt/venv/bin/python /app/server/src/server.py &
CUSTOM_LLM_PORT=8001 /opt/venv/bin/python /app/llm/src/custom_llm_server.py &
PORT=3000 HOSTNAME=0.0.0.0 node /app/web/server.js &

# Exit (non-zero) as soon as any one process exits, so the container restarts.
wait -n
