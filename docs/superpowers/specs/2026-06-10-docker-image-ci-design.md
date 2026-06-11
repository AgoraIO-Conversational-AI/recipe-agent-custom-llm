# Docker Image in CI — Design

**Date:** 2026-06-10
**Status:** Approved
**Repo:** `recipe-agent-custom-llm` (local folder `/Users/zhangqianze/Documents/agent-recipes-python`)
**Branch:** `feat/docker-image` off `main`

## Goal

Build a **single combined Docker image** for the custom-llm recipe (all three services — `server/` FastAPI :8000, `llm/` FastAPI :8001, `web/` Next.js :3000 — in one image), and wire it into CI: **build-only (dry-run, no push)** on push / PR / merge to `main`, and **build + push** to GitHub Container Registry (GHCR) when a git tag `v*` is created.

## Locked Decisions

1. **One combined image**, not per-service. Runs all three processes via a small launcher. It is a *demo convenience* (`docker run` boots the whole stack), explicitly not the production-deploy shape (which would split the services).
2. **Registry: GHCR** — `ghcr.io/agoraio-conversational-ai/recipe-agent-custom-llm`. Auth via the built-in `GITHUB_TOKEN`; no manually-managed secrets.
3. **Web image strategy: Next.js `output: "standalone"`** — one-line add to `web/next.config.ts` for a small runtime artifact (`node server.js`).
4. **Architecture: `linux/amd64` only** (arm64 is a trivial later add via buildx/QEMU).
5. **Separate workflow** (`.github/workflows/docker.yml`), independent of the test `ci.yml`. Separate PR off `main`.
6. **Process launcher:** a bash `docker/entrypoint.sh` as PID 1 — starts all three, traps signals, exits if any child dies.

## Components

### `Dockerfile` (repo root) — multi-stage
- **Stage `web-build`** (`oven/bun:1`): copy the bun workspace (`package.json`, `bun.lock`, `web/`), `bun install`, `bun run build` in `web/` producing the Next standalone output (`web/.next/standalone`, `web/.next/static`, `web/public`).
- **Stage `runtime`** (`node:22-bookworm-slim`): `apt-get install python3 python3-venv`; create a venv at `/opt/venv`; `pip install` `server/requirements.txt` + `llm/requirements.txt`; copy `server/src`, `llm/src`, and the web standalone artifact into `/app`; copy `docker/entrypoint.sh`. `EXPOSE 3000 8000 8001`. `CMD ["/app/docker/entrypoint.sh"]`.
- Pin a stable Python (3.13 from the distro/deadsnakes or the node-slim default) consistent with the recipe's 3.10+ floor.

### `docker/entrypoint.sh`
```sh
#!/usr/bin/env bash
set -euo pipefail
trap 'kill 0' TERM INT
# Each process gets its own PORT inline — both FastAPI and Next read $PORT,
# so they MUST NOT share one value.
PORT="${BACKEND_PORT:-8000}" /opt/venv/bin/python /app/server/src/server.py &
CUSTOM_LLM_PORT="${CUSTOM_LLM_PORT:-8001}" /opt/venv/bin/python /app/llm/src/custom_llm_server.py &
PORT="${WEB_PORT:-3000}" HOSTNAME=0.0.0.0 node /app/web/server.js &
wait -n
```
- Image-level defaults (overridable at `docker run`): `AGENT_BACKEND_URL=http://localhost:8000` (web→server in-container). The entrypoint sets each process's port **inline** (backend 8000, llm 8001, web 3000) so the shared `PORT` convention can't make two processes bind the same port. `HOSTNAME=0.0.0.0` makes the Next standalone server listen on all interfaces.

### `.dockerignore` (repo root)
Exclude: `**/venv`, `**/node_modules`, `web/.next`, `**/__pycache__`, `*.env.local`, `**/tests`, `docs/`, `.github/`, `.git/`.

### `web/next.config.ts`
Add `output: 'standalone'` to `nextConfig`. Because `web/` is a Bun **workspace member** (root `package.json` has `workspaces: ["web"]`), also set `outputFileTracingRoot` so standalone dependency tracing resolves correctly from the repo root rather than mis-tracing the monorepo. The `/api/*` rewrites already read `AGENT_BACKEND_URL` at runtime, so they work unchanged inside the container.

### `.github/workflows/docker.yml`
```
on:
  push:
    branches: ["**"]
    tags: ["v*"]
  pull_request:
```
One job (`docker`, `runs-on: ubuntu-latest`):
- `actions/checkout`, `docker/setup-buildx-action`.
- `docker/metadata-action` → image `ghcr.io/${{ github.repository }}`, tags: `type=semver,pattern={{version}}`, `type=semver,pattern={{major}}.{{minor}}`, `type=raw,value=latest,enable=${{ startsWith(github.ref,'refs/tags/') }}`.
- `docker/login-action` (ghcr.io, `GITHUB_TOKEN`) — **only when** `startsWith(github.ref,'refs/tags/')`.
- `docker/build-push-action` with `platforms: linux/amd64`, `push: ${{ startsWith(github.ref,'refs/tags/') }}`, `tags`/`labels` from metadata, and GHA build cache (`cache-from/to: type=gha`).
- Requires `permissions: { contents: read, packages: write }`.

## Triggers (behavior)

| Event | Login | Build | Push |
| --- | --- | --- | --- |
| push to any branch | no | yes | **no** (dry-run) |
| pull_request | no | yes | **no** (dry-run) |
| merge to `main` (a push) | no | yes | **no** (dry-run) |
| git tag `v1.2.3` | yes (GHCR) | yes | **yes** → `1.2.3`, `1.2`, `latest` |

The dry-run proves the Dockerfile builds on every change without publishing anything.

## Image usage (documented on the image / README)

```bash
docker run --rm \
  -p 3000:3000 -p 8000:8000 -p 8001:8001 \
  -e AGORA_APP_ID=... -e AGORA_APP_CERTIFICATE=... \
  -e CUSTOM_LLM_URL=https://<public-tunnel>/chat/completions \
  -e CUSTOM_LLM_API_KEY=any-key-here \
  ghcr.io/agoraio-conversational-ai/recipe-agent-custom-llm:latest
```

**Unchanged constraint:** Agora cloud calls `CUSTOM_LLM_URL` from outside, so even though `llm` is bundled in the container, `CUSTOM_LLM_URL` must point at a **publicly reachable** address for `:8001` (ngrok locally, or a public ingress when deployed). Web→server is internal (`localhost:8000`) and needs no tunnel.

## Error Handling

- Entrypoint uses `wait -n` so if any of the three processes exits, the container exits non-zero (so an orchestrator restarts it) and `trap 'kill 0'` tears down siblings on SIGTERM/SIGINT.
- The backend already fails fast (raises → `agent=None` → 500s) when required env (`AGORA_APP_ID`/`CERTIFICATE`/`CUSTOM_LLM_URL`/`CUSTOM_LLM_API_KEY`) is missing; the container still starts (web + llm run) so misconfiguration is visible via the backend's 500s rather than a crash loop.

## Testing / Verification

- **Local:** `docker build -t recipe-custom-llm:dev .` succeeds; `docker run -p 3000:3000 -p 8000:8000 -p 8001:8001 -e CUSTOM_LLM_URL=https://example.test/chat/completions -e AGORA_APP_ID=... -e AGORA_APP_CERTIFICATE=... ...` → `curl localhost:8001/health` returns ok, `curl localhost:8000/get_config` returns a token envelope, `curl localhost:3000` serves the UI.
- **CI dry-run:** the `docker` job builds green on the PR (no push, no login).
- **Tag push:** pushing a `v0.0.1` tag publishes the three image tags to GHCR (verify in the repo's Packages).

## Risks / Notes

- **Next standalone + Bun workspace tracing** is the main risk: monorepo standalone builds can mis-resolve `node_modules` paths. Mitigation: set `output: "standalone"` + `outputFileTracingRoot` and copy the standalone tree exactly (`server.js`, `.next/static`, `public`). The plan must verify a clean `docker build` actually produces a runnable web process.
- **Multi-process PID 1:** acceptable for a demo image; documented as not the prod shape. `wait -n` requires bash (present in `node:bookworm-slim`).
- **Image size:** node + python + both dependency sets; acceptable for a demo. `.dockerignore` keeps the context small.
- **Independent of test PR #3:** this branch is off `main` (which lacks the test suite). No code overlap except a possible README section near `## Commands`; keep the Docker docs in a distinct section to avoid a merge conflict.
- **Portability:** the same Dockerfile + workflow port to `recipe-agent-custom-llm-tts` (swap the recipe-specific bits; the structure is identical).
