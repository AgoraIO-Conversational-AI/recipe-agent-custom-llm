# recipe-agent-custom-llm — Drop Web From The Docker Image Design

**Date:** 2026-06-11
**Status:** Approved
**Repo:** `agent-recipes-python` (recipe `recipe-agent-custom-llm`)
**Branch:** `ci/docker-drop-web` off `main`
**Relation:** Retrofit of the already-shipped combined Docker image. Paired with the
quickstart's new server-only image; both move to a **Python-backends-only** container.

## Goal

Reduce the existing combined Docker image (server + llm + **web**) to the two Python
backends only (server :8000 + llm :8001). Removing the web frontend removes the Next.js
`output: 'standalone'` requirement, so the production-code change to `web/next.config.ts`
is reverted and the runtime base image drops Node entirely.

## Why

The combined image bundled the Next.js frontend purely for a one-command demo. That
convenience forced `output: 'standalone'` + a `DOCKER_BUILD` type-check seam into
`web/next.config.ts`, and a heavier `node:22` runtime carrying both Node and Python. The
web frontend is not the recipe's point — the **custom LLM endpoint** (`llm/`) is. Dropping
web keeps the recipe's defining components in the image while shedding the standalone
machinery and the Node runtime layer.

## Scope of change (what stays vs goes)

**Stays in the image:** `server/` (FastAPI agent backend, :8000) and `llm/` (OpenAI-compatible
custom LLM endpoint, :8001).
**Leaves the image:** the Next.js web frontend (:3000) and everything that supported it.

## Files

### `Dockerfile` — modify (remove the web build stage and Node runtime)

Target end state:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app

# Python dependencies for both backend services.
COPY server/requirements.txt /tmp/server-req.txt
COPY llm/requirements.txt /tmp/llm-req.txt
RUN pip install --no-cache-dir -r /tmp/server-req.txt -r /tmp/llm-req.txt

# Python source.
COPY server/src /app/server/src
COPY llm/src /app/llm/src

# Launcher (server + llm).
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000 8001
CMD ["/app/docker/entrypoint.sh"]
```

Removed vs current: the entire `oven/bun:1` web-build stage; the `node:22-bookworm-slim`
base + `apt-get python3 python3-venv` + `/opt/venv` (replaced by a Python base where `pip`
is the system pip); the `COPY --from=web-build ...` lines for the standalone bundle, static,
and public; the `ENV AGENT_BACKEND_URL=http://localhost:8000` (no web to proxy); `EXPOSE`
drops `3000`.

Note: the current image installs into `/opt/venv`; on a `python:slim` base we install with
the image's own `pip` (no venv needed inside a single-purpose container). The
`entrypoint.sh` python invocations change from `/opt/venv/bin/python` to `python`.

### `docker/entrypoint.sh` — modify (drop the web process)

Target end state:

```bash
#!/usr/bin/env bash
# PID 1 for the backend image: start server + llm, exit if either dies.
set -euo pipefail
trap 'kill 0' TERM INT

PORT=8000 python /app/server/src/server.py &
CUSTOM_LLM_PORT=8001 python /app/llm/src/custom_llm_server.py &

# Exit (non-zero) as soon as either process exits, so the container restarts.
wait -n
```

Removed: the `PORT=3000 HOSTNAME=0.0.0.0 node /app/web/server.js &` line and the comment
referencing the Next server.

### `web/next.config.ts` — revert the Docker-only additions

Remove the two blocks added for the combined image, returning the file to its pre-Docker
shape:

- Remove `output: 'standalone',` and its comment.
- Remove the `typescript: { ignoreBuildErrors: process.env.DOCKER_BUILD === '1' }` block and
  its comment.

Everything else (`reactStrictMode`, `turbopack`, `images`, `rewrites`) is unchanged. After
the revert, `web/next.config.ts` should match the base-template config (the same content the
quickstart's `web/next.config.ts` has today).

### `.github/workflows/docker.yml` — modify (smoke without web)

- Smoke `docker run`: drop `-p 3000:3000`; keep `-p 8000:8000 -p 8001:8001`. Keep the
  `CUSTOM_LLM_URL` + `CUSTOM_LLM_API_KEY` smoke envs (the agent backend requires them) and
  the two `AGORA_*` envs.
- Health probe loop: drop `http://localhost:3000/`; keep `http://localhost:8001/health` and
  `http://localhost:8000/get_config`.
- Build context/platforms/cache, metadata tags, and the tag-gated GHCR push steps are
  unchanged. `workflow_call:` stays (nightly uses it).

### `README.md` — remove the `## Docker` section

Delete the entire `## Docker` section (the heading, the "all three services" paragraph, the
`docker run` fenced block, and the public-tunnel caveat block). The image becomes CI-only,
matching the quickstart. No replacement section is added.

### `.dockerignore` — unchanged

The existing ignore list is still valid (it already excludes `web/.next`, venvs, tests,
docs, etc.). `web/.next` and `web/` build artifacts are simply never produced now.

## Out of scope

- No change to `server/` or `llm/` application code.
- No change to the test suite or `ci.yml`.
- No change to `nightly.yml` beyond what it already references (it calls `docker.yml` via
  `workflow_call`, which still exists).
- `docs/ai/` is not touched, so no L0 `Last Reviewed` bump.

## Verification

- **Local build + smoke:**
  ```bash
  docker build -t custom-llm-backend .
  docker run -d --name smoke -p 8000:8000 -p 8001:8001 \
    -e AGORA_APP_ID=0123456789abcdef0123456789abcdef \
    -e AGORA_APP_CERTIFICATE=fedcba9876543210fedcba9876543210 \
    -e CUSTOM_LLM_URL=https://example.test/chat/completions \
    -e CUSTOM_LLM_API_KEY=test-key \
    custom-llm-backend
  curl -fsS localhost:8001/health && curl -fsS localhost:8000/get_config
  docker rm -f smoke
  ```
  Expected: `/health` OK and `/get_config` returns a token envelope. `:3000` no longer
  exists.
- **Web build still works after the revert:** `bun run build` (and `verify:web:build`)
  succeeds without `output: 'standalone'` — it just emits the normal `.next/` output and
  still type-checks.
- **No `DOCKER_BUILD` references remain:** `grep -rn DOCKER_BUILD .` returns nothing (the
  Dockerfile no longer sets it and `next.config.ts` no longer reads it).
- **README has no Docker section:** `grep -n "## Docker" README.md` returns nothing.
- **CI:** the `docker` job is green (build + two-port smoke); push steps skipped off-tag.

## Risks / Notes

- **`next.config.ts` revert is a real (if small) prod-config change.** It removes standalone
  output, so any external process that consumed `web/.next/standalone` would break — but the
  only consumer was the Docker image we are changing. Local dev/deploy (`next dev`,
  `next build && next start`) is unaffected.
- **Base image swap (`node:22` → `python:3.12-slim`)** changes pip's location from
  `/opt/venv/bin/pip` to the system `pip`; the `entrypoint.sh` python paths change to bare
  `python`. Both verified against the new Dockerfile above.
- **The combined-demo convenience is gone.** A developer who wants the web UI runs it
  separately (`bun run dev` or a Next deploy); the image is the backend pair only. This is an
  intentional simplification.
```
