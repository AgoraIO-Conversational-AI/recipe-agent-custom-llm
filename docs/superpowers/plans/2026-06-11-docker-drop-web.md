# Drop Web From The Docker Image — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the combined `server + llm + web` Docker image to the two Python backends only (`server` :8000 + `llm` :8001), reverting the web-only `next.config.ts` additions and deleting the README `## Docker` section.

**Architecture:** Replace the two-stage (bun web build + `node:22` runtime) Dockerfile with a single-stage, non-root `python:3.12-slim-bookworm` image that installs both backend requirement sets and runs `server` + `llm` via the existing `docker/entrypoint.sh` (web process removed). Revert `web/next.config.ts` to its pre-Docker shape; trim the CI smoke to two ports; remove the README Docker section.

**Tech Stack:** Docker (single-stage), GitHub Actions, Next.js config.

**Spec:** `docs/superpowers/specs/2026-06-11-docker-drop-web-design.md`

**Repo & branch:** `agent-recipes-python` (`/Users/zhangqianze/Documents/agent-recipes-python`), branch `ci/docker-drop-web` (already created off `main`; spec committed there). `main` currently has the combined image (`Dockerfile`, `docker/entrypoint.sh`, `.github/workflows/docker.yml`) and the standalone `web/next.config.ts`.

---

## Conventions

- Conventional Commits, lowercase after prefix, present tense. **No AI attribution / no `Co-Authored-By`. No `--no-verify`. No git config changes.** If a commit fails on git identity, prefix with `git -c user.email="qianze.zhang@hotmail.com"`.
- Infra change: "tests" are a local `docker build` + two-port smoke, a `bun run build` regression after the config revert, and dependency-free `grep` checks. A failure is a real finding — surface it.
- Requires a Docker daemon for the build/smoke steps. If unavailable, complete the edits + grep/`bun run build` checks and report DONE_WITH_CONCERNS noting the local image build was deferred to CI.
- **Note on `docker.yml` triggers:** `main`'s `docker.yml` has only `push` + `pull_request` (no `workflow_call:` — the open nightly branch adds that itself). Do **not** add or remove triggers here; only the two smoke lines change.

---

## Task 1: Rewrite `Dockerfile` + `docker/entrypoint.sh` (backend-only, non-root)

**Files:**
- Modify (full rewrite): `Dockerfile`, `docker/entrypoint.sh`

- [ ] **Step 1: Replace `Dockerfile` with the backend-only, non-root image**

Overwrite `Dockerfile` with exactly:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS runtime

# Run as a non-root user (created before any COPY so --chown can reference it).
RUN useradd --create-home --uid 10001 app
WORKDIR /app

# Python dependencies for both backend services (installed as root into the
# system site-packages, world-readable for the app user at runtime).
COPY server/requirements.txt /tmp/server-req.txt
COPY llm/requirements.txt /tmp/llm-req.txt
RUN pip install --no-cache-dir -r /tmp/server-req.txt -r /tmp/llm-req.txt

# Python source, owned by the runtime user.
COPY --chown=app:app server/src /app/server/src
COPY --chown=app:app llm/src /app/llm/src

# Launcher (server + llm).
COPY --chown=app:app docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

# Drop privileges for the running processes.
USER app

EXPOSE 8000 8001
CMD ["/app/docker/entrypoint.sh"]
```

- [ ] **Step 2: Replace `docker/entrypoint.sh` (drop the web process)**

Overwrite `docker/entrypoint.sh` with exactly:

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

- [ ] **Step 3: Build the image**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
docker build -t custom-llm-backend:test .
```
Expected: build succeeds. No bun/web stage, no `node`. Both requirement sets install into the system Python (3.12). If a dependency fails to resolve on 3.12, report it — a real finding (the prior image used bookworm's 3.11).

- [ ] **Step 4: Two-port smoke**

Run:
```bash
docker rm -f cl-smoke 2>/dev/null || true
docker run -d --name cl-smoke -p 8000:8000 -p 8001:8001 \
  -e AGORA_APP_ID=0123456789abcdef0123456789abcdef \
  -e AGORA_APP_CERTIFICATE=fedcba9876543210fedcba9876543210 \
  -e CUSTOM_LLM_URL=https://example.test/chat/completions \
  -e CUSTOM_LLM_API_KEY=test-key \
  custom-llm-backend:test
for i in $(seq 1 40); do curl -fsS http://localhost:8001/health -o /dev/null && break; sleep 1; done
echo "health:"; curl -fsS http://localhost:8001/health; echo
echo "get_config:"; curl -fsS http://localhost:8000/get_config -o /tmp/cl_cfg.json && head -c 120 /tmp/cl_cfg.json; echo
docker rm -f cl-smoke
```
Expected: `/health` responds OK and `/get_config` returns a token envelope. If the container exits, run `docker logs cl-smoke` and report — a real finding.

- [ ] **Step 5: Confirm non-root**

Run:
```bash
docker run --rm --entrypoint sh custom-llm-backend:test -c "id -un"
```
Expected: `app`.

- [ ] **Step 6: Commit**

```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
git add Dockerfile docker/entrypoint.sh
git commit -m "build: drop web from the docker image, switch to non-root python base"
```

---

## Task 2: Trim the CI smoke (`.github/workflows/docker.yml`)

**Files:**
- Modify: `.github/workflows/docker.yml` (two lines only)

- [ ] **Step 1: Drop the web port from the `docker run` smoke line**

Edit `.github/workflows/docker.yml`. Replace:
```
          docker run -d --name smoke -p 8000:8000 -p 8001:8001 -p 3000:3000 \
```
with:
```
          docker run -d --name smoke -p 8000:8000 -p 8001:8001 \
```

- [ ] **Step 2: Drop the web URL from the probe loop**

Replace:
```
          for url in http://localhost:8001/health http://localhost:8000/get_config http://localhost:3000/; do
```
with:
```
          for url in http://localhost:8001/health http://localhost:8000/get_config; do
```

- [ ] **Step 3: Validate**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
grep -c "3000" .github/workflows/docker.yml
grep -nE "8001/health|8000/get_config|-p 8000:8000 -p 8001:8001" .github/workflows/docker.yml
```
Expected: first `grep -c` prints `0` (no `:3000` anywhere); the second prints the two kept smoke lines. The `CUSTOM_LLM_*` and `AGORA_*` envs and the tag-gated push steps are untouched.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/docker.yml
git commit -m "ci: drop the web (:3000) probe from the docker smoke test"
```

---

## Task 3: Revert `web/next.config.ts` + delete README `## Docker`

**Files:**
- Modify: `web/next.config.ts`, `README.md`

- [ ] **Step 1: Revert the standalone + DOCKER_BUILD additions in `web/next.config.ts`**

Edit `web/next.config.ts`. Replace:
```ts
const nextConfig: NextConfig = {
  // Emit a self-contained server bundle (.next/standalone) for the Docker image.
  output: 'standalone',
  // Skip the TypeScript type-check ONLY inside the Docker image build
  // (the Dockerfile sets DOCKER_BUILD=1). It keeps peak build memory low on
  // constrained hosts. The normal `bun run build` (e.g. `verify:web:build`)
  // still type-checks — the image build is the only place types are skipped.
  typescript: {
    ignoreBuildErrors: process.env.DOCKER_BUILD === '1',
  },
  // Enable React strict mode
```
with:
```ts
const nextConfig: NextConfig = {
  // Enable React strict mode
```

- [ ] **Step 2: Delete the README `## Docker` section**

Read `README.md`, then remove the entire `## Docker` section. Replace:
```
## Docker

A single combined image runs all three services (server :8000, llm :8001, web :3000). CI builds and smoke-tests it on every push/PR and publishes it to GHCR on `v*` tags.

```bash
docker run --rm \
  -p 3000:3000 -p 8000:8000 -p 8001:8001 \
  -e AGORA_APP_ID=... -e AGORA_APP_CERTIFICATE=... \
  -e CUSTOM_LLM_URL=https://<public-tunnel>/chat/completions \
  -e CUSTOM_LLM_API_KEY=any-key-here \
  ghcr.io/agoraio-conversational-ai/recipe-agent-custom-llm:latest
```

> The combined image bundles the processes for convenience but does **not** remove the public-tunnel requirement: Agora cloud calls `CUSTOM_LLM_URL` from outside, so it must point at a publicly reachable address for the `:8001` port (ngrok locally, or a public ingress when deployed). It is a demo convenience, not the production-deploy shape (where you'd split the services).

## License
```
with:
```
## License
```
(If exact whitespace differs, Read the file and delete from the `## Docker` heading through the blockquote, leaving the `## License` heading and one blank line above it.)

- [ ] **Step 3: Verify the revert + deletions**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
grep -rn "DOCKER_BUILD" . --include="*.ts" --include="*.yml" --include="Dockerfile" ; echo "exit:$?"
grep -n "standalone\|## Docker" README.md web/next.config.ts ; echo "exit:$?"
```
Expected: both `grep` commands print **no matches** and `exit:1` (nothing left referencing `DOCKER_BUILD`, `standalone`, or a README Docker section).

- [ ] **Step 4: Confirm the web build still works without standalone**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
bun install
bun run build
```
Expected: `bun run build` succeeds and **type-checks** (no `DOCKER_BUILD` bypass), emitting the normal `.next/` output (no `.next/standalone`). This proves the revert didn't break the normal build. If `bun`/build is unavailable in the sandbox, report it and rely on CI's `verify:web:build`.

- [ ] **Step 5: Commit**

```bash
git add web/next.config.ts README.md
git commit -m "docs: revert standalone next config and remove README docker section"
```

---

## Task 4: Diff review + push + PR

**Files:** none (git only).

- [ ] **Step 1: Review the full diff against main**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
git diff --name-only main...ci/docker-drop-web
```
Expected exactly: `Dockerfile`, `docker/entrypoint.sh`, `.github/workflows/docker.yml`, `web/next.config.ts`, `README.md`, and the `docs/superpowers/...docker-drop-web...` spec/plan files. **No** `server/`, `llm/`, `ci.yml`, or `nightly.yml` changes.

- [ ] **Step 2: Push**

```bash
git push -u origin ci/docker-drop-web
```

- [ ] **Step 3: Open the PR** (REST — GraphQL `gh pr create` 401s under the lapsed SSO session)

```bash
REPO=AgoraIO-Conversational-AI/recipe-agent-custom-llm
gh api -X POST "repos/$REPO/pulls" \
  -f title="ci: drop web from the docker image (backend-only)" \
  -f head="ci/docker-drop-web" -f base="main" \
  -f body="Reduces the combined image to the two Python backends (server :8000 + llm :8001): single-stage non-root python:3.12-slim, web build stage and Node runtime removed. Reverts the web-only next.config.ts additions (output:standalone + DOCKER_BUILD type-check seam) and removes the README ## Docker section (image becomes CI-only). CI smoke drops the :3000 probe; GHCR tag-push unchanged. Verified: local two-port smoke (/health + /get_config) and bun run build still type-checks." \
  --jq '{number, url: .html_url, state}'
```
Expected: JSON with the new PR number + URL.

> **Note on repo slug:** the local folder is `agent-recipes-python` but the GitHub repo is `recipe-agent-custom-llm` (confirm with `gh repo view --json nameWithOwner` if the push remote differs). Use the actual `origin` repo for the `$REPO` value.

---

## Self-Review notes (for the implementer)

- **Backend-only** — the image must not contain `web/`, `node`, or port `3000`/standalone artifacts. The `git diff --name-only` in Task 4 is the guard.
- **Non-root** — `id -un` must print `app`; `pip install` runs before `USER app`.
- **The `next.config.ts` revert must still type-check** — that's the whole point of Task 3 Step 4 (`bun run build` with no `DOCKER_BUILD` bypass). If the build now fails on a real TS error that was previously masked inside the Docker build, that is a genuine finding — report it rather than re-adding `ignoreBuildErrors`.
- **Don't touch `docker.yml` triggers** — `main` has no `workflow_call:`; leave the `on:` block alone. Only the two `:3000` smoke lines change.
- **Repo slug** — push remote is `recipe-agent-custom-llm`, not the local folder name.
- **Docker may be unavailable** — if so, do the edits + grep + `bun run build`, report the deferred image build, and let CI gate. Do not fake a green smoke.
```
