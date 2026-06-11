# Docker Image in CI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one combined Docker image (server + llm + web in a single image) and wire CI to **build + smoke-test** it on push/PR/main (no push) and **build + smoke-test + push** to GHCR on `v*` git tags.

**Architecture:** Multi-stage `Dockerfile` — a Bun stage builds the Next.js standalone web bundle; a `node:22-bookworm-slim` + `python3` runtime stage holds a venv with `server/` + `llm/` deps and runs all three processes via a bash `entrypoint.sh`. A `docker.yml` workflow builds the image locally, smoke-tests it (`docker run` + curl three endpoints), and pushes to `ghcr.io/<repo>` only on tags after the smoke passes.

**Tech Stack:** Docker buildx, GitHub Actions (`docker/{metadata,build-push,login}-action`), Next.js standalone output, Bun, Python venv.

**Spec:** `docs/superpowers/specs/2026-06-10-docker-image-ci-design.md`

**Repo & branch:** `recipe-agent-custom-llm` (local folder `/Users/zhangqianze/Documents/agent-recipes-python`), branch `feat/docker-image` (already created off `main`).

**Verified facts (from grilling):** Next 16.2.9 standalone builds under Turbopack and produces `web/.next/standalone/web/server.js` (nested under `web/` due to the bun workspace), bundles `node_modules` (~35 MB, no runtime install), and does **not** copy `.next/static`/`public` into standalone (the Dockerfile copies them). Docker 29.x is available locally for the build+smoke validation.

---

## Conventions

- Conventional Commits, lowercase after prefix, present tense, NO AI attribution / NO `Co-Authored-By`, no `--no-verify`. If a commit fails on git identity, prefix with `git -c user.email="qianze.zhang@hotmail.com"`.
- All work on branch `feat/docker-image`.

---

## Task 1: Enable Next.js standalone output

**Files:**
- Modify: `web/next.config.ts`

- [ ] **Step 1: Add `output: 'standalone'`**

In `web/next.config.ts`, change:
```ts
const nextConfig: NextConfig = {
  // Enable React strict mode
  reactStrictMode: true,
```
to:
```ts
const nextConfig: NextConfig = {
  // Emit a self-contained server bundle (.next/standalone) for the Docker image.
  output: 'standalone',
  // Enable React strict mode
  reactStrictMode: true,
```

- [ ] **Step 2: Build and confirm the standalone artifact appears**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python/web
rm -rf .next && bun run build >/dev/null 2>&1
test -f .next/standalone/web/server.js && echo "standalone server.js OK" || echo "MISSING standalone server.js"
test -d .next/static && echo "static OK"
```
Expected: `standalone server.js OK` and `static OK`. (Confirms the nesting under `web/` that the Dockerfile relies on.)

- [ ] **Step 3: Confirm the existing web build/start path still works**

Run: `cd /Users/zhangqianze/Documents/agent-recipes-python/web && bun run build >/dev/null 2>&1 && echo "build OK"`
Expected: `build OK` (adding `output: standalone` doesn't break the normal `next build` used by `verify:web:build`).

- [ ] **Step 4: Commit**

```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
git add web/next.config.ts
git commit -m "feat(web): emit Next.js standalone output for the Docker image"
```

---

## Task 2: Process launcher (`docker/entrypoint.sh`)

**Files:**
- Create: `docker/entrypoint.sh`

- [ ] **Step 1: Create `docker/entrypoint.sh`**

```sh
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
```

- [ ] **Step 2: Make it executable and syntax-check it**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
chmod +x docker/entrypoint.sh
bash -n docker/entrypoint.sh && echo "entrypoint syntax OK"
```
Expected: `entrypoint syntax OK`.

- [ ] **Step 3: Commit**

```bash
git add docker/entrypoint.sh
git commit -m "feat(docker): add combined-image process launcher"
```

---

## Task 3: `.dockerignore`

**Files:**
- Create: `.dockerignore` (repo root)

- [ ] **Step 1: Create `.dockerignore`**

```
**/venv
**/node_modules
web/.next
**/__pycache__
*.env.local
**/.env.local
**/tests
docs/
.github/
.git/
*.md
```

- [ ] **Step 2: Commit**

```bash
git add .dockerignore
git commit -m "chore(docker): add .dockerignore to keep the build context small"
```

---

## Task 4: Combined `Dockerfile`

**Files:**
- Create: `Dockerfile` (repo root)

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1

# ---------- Stage 1: build the Next.js standalone web bundle with Bun ----------
FROM oven/bun:1 AS web-build
WORKDIR /src
# Install workspace deps first (better layer caching). The repo is a Bun
# workspace whose root package.json declares workspaces: ["web"].
COPY package.json bun.lock ./
COPY web/package.json web/package.json
RUN bun install --frozen-lockfile
# Build the web app -> web/.next/standalone (server.js nested under web/).
COPY web/ web/
RUN bun run build

# ---------- Stage 2: runtime with node (for web) + python (for server/llm) ----------
FROM node:22-bookworm-slim AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /app

# Python dependencies for both backend services.
COPY server/requirements.txt /tmp/server-req.txt
COPY llm/requirements.txt /tmp/llm-req.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /tmp/server-req.txt -r /tmp/llm-req.txt

# Python source.
COPY server/src /app/server/src
COPY llm/src /app/llm/src

# Web standalone bundle: the standalone root holds node_modules/ + web/server.js.
# Copying it to /app yields /app/node_modules and /app/web/server.js.
COPY --from=web-build /src/web/.next/standalone/ /app/
# static + public are NOT included in standalone — place them under the nested web dir.
COPY --from=web-build /src/web/.next/static /app/web/.next/static
COPY --from=web-build /src/web/public /app/web/public

# Launcher.
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

# web -> server is internal in-container; overridable at runtime.
ENV AGENT_BACKEND_URL=http://localhost:8000

EXPOSE 3000 8000 8001
CMD ["/app/docker/entrypoint.sh"]
```

- [ ] **Step 2: Commit** (the build is validated in Task 5)

```bash
git add Dockerfile
git commit -m "feat(docker): add combined server+llm+web image"
```

---

## Task 5: Local build + smoke validation

**Files:** none (validates the image). Docker 29.x is available locally.

- [ ] **Step 1: Build the image**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
docker build -t recipe-custom-llm:dev .
```
Expected: build completes successfully (the web-build stage runs `bun run build`; the runtime stage installs python deps and assembles `/app`). This needs outbound network (PyPI, Google Fonts for `next/font`).

- [ ] **Step 2: Run the container with fake env**

Run:
```bash
docker rm -f smoke 2>/dev/null || true
docker run -d --name smoke -p 8000:8000 -p 8001:8001 -p 3000:3000 \
  -e AGORA_APP_ID=0123456789abcdef0123456789abcdef \
  -e AGORA_APP_CERTIFICATE=fedcba9876543210fedcba9876543210 \
  -e CUSTOM_LLM_URL=https://example.test/chat/completions \
  -e CUSTOM_LLM_API_KEY=test-key \
  recipe-custom-llm:dev
```
Expected: a container id is printed.

- [ ] **Step 3: Poll the three endpoints**

Run:
```bash
for url in http://localhost:8001/health http://localhost:8000/get_config http://localhost:3000/; do
  ok=""
  for i in $(seq 1 40); do
    if curl -fsS "$url" -o /dev/null 2>/dev/null; then ok=1; echo "OK   $url"; break; fi
    sleep 1
  done
  [ -n "$ok" ] || { echo "FAIL $url"; docker logs smoke | tail -40; }
done
docker rm -f smoke
```
Expected: `OK` for all three (`:8001/health`, `:8000/get_config`, `:3000/`). If any `FAIL`, the printed `docker logs` reveal the cause (e.g., wrong `web/server.js` path, missing `static`, a process that didn't bind). Fix the Dockerfile/entrypoint and rebuild before continuing — this is the real correctness gate.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix(docker): make the combined image pass local smoke" || echo "nothing to commit"
```

---

## Task 6: GitHub Actions workflow (`.github/workflows/docker.yml`)

**Files:**
- Create: `.github/workflows/docker.yml`

- [ ] **Step 1: Create `.github/workflows/docker.yml`**

```yaml
name: docker

on:
  push:
    branches: ["**"]
    tags: ["v*"]
  pull_request:

permissions:
  contents: read
  packages: write

jobs:
  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-buildx-action@v3

      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=sha
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=raw,value=latest,enable=${{ startsWith(github.ref, 'refs/tags/') }}

      - name: Build (load locally, no push)
        uses: docker/build-push-action@v6
        with:
          context: .
          platforms: linux/amd64
          load: true
          push: false
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Smoke test
        run: |
          IMAGE=$(printf '%s\n' "${{ steps.meta.outputs.tags }}" | head -n1)
          echo "Smoke-testing $IMAGE"
          docker run -d --name smoke -p 8000:8000 -p 8001:8001 -p 3000:3000 \
            -e AGORA_APP_ID=0123456789abcdef0123456789abcdef \
            -e AGORA_APP_CERTIFICATE=fedcba9876543210fedcba9876543210 \
            -e CUSTOM_LLM_URL=https://example.test/chat/completions \
            -e CUSTOM_LLM_API_KEY=test-key \
            "$IMAGE"
          set +e
          fail=0
          for url in http://localhost:8001/health http://localhost:8000/get_config http://localhost:3000/; do
            ok=""
            for i in $(seq 1 40); do
              if curl -fsS "$url" -o /dev/null; then ok=1; echo "OK   $url"; break; fi
              sleep 1
            done
            if [ -z "$ok" ]; then echo "FAIL $url"; fail=1; fi
          done
          if [ "$fail" -ne 0 ]; then docker logs smoke; fi
          docker rm -f smoke
          exit $fail

      - name: Log in to GHCR
        if: startsWith(github.ref, 'refs/tags/')
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Push tags
        if: startsWith(github.ref, 'refs/tags/')
        run: |
          printf '%s\n' "${{ steps.meta.outputs.tags }}" | while read -r tag; do
            [ -n "$tag" ] && docker push "$tag"
          done
```

- [ ] **Step 2: Validate the YAML**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
server/venv/bin/python -c "import yaml; d=yaml.safe_load(open('.github/workflows/docker.yml')); print('docker.yml OK; jobs:', list(d['jobs']))"
```
Expected: `docker.yml OK; jobs: ['docker']`. (If PyYAML isn't in the venv, `python3 -m pip install --user pyyaml` or rely on GitHub validating on push.)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/docker.yml
git commit -m "ci: build+smoke the docker image on push/PR, push to GHCR on tags"
```

---

## Task 7: Document the image in the README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a Docker section** before the `## License` line

In `README.md`, insert this section immediately before `## License`:
```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document the combined Docker image and its public-tunnel caveat"
```

---

## Task 8: Push + open PR

**Files:** none (git only).

- [ ] **Step 1: Push the branch**

```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
git push -u origin feat/docker-image
```

- [ ] **Step 2: Open the PR** (REST — the GraphQL `gh pr create` path 401s under the lapsed SSO session)

```bash
REPO=AgoraIO-Conversational-AI/recipe-agent-custom-llm
gh api -X POST "repos/$REPO/pulls" \
  -f title="ci: build a combined Docker image (dry-run on push, push to GHCR on tags)" \
  -f head="feat/docker-image" -f base="main" \
  -f body="Adds a single combined Docker image (server + llm + web) and a docker.yml workflow that builds + smoke-tests the image on every push/PR (no push) and pushes to ghcr.io on v* tags after the smoke passes. Web uses Next.js standalone output (verified: server.js nests under web/). The image bundles the processes for demo convenience but the public-tunnel requirement for CUSTOM_LLM_URL is unchanged. Validated locally: docker build + run + curl on :8001/health, :8000/get_config, :3000/." \
  --jq '{number, url: .html_url, state}'
```
Expected: a JSON object with the new PR number + URL.

---

## Self-Review notes (for the implementer)

- **Task 5 is the real gate.** "build succeeds" ≠ "image works" for this combined image — the local `docker run` + curl catches the standalone-path / launcher / binding issues that a build alone won't. Do not skip it; fix and rebuild on any FAIL.
- **GHCR lowercase:** `docker/metadata-action` lowercases `ghcr.io/${{ github.repository }}` automatically, so the push targets `ghcr.io/agoraio-conversational-ai/recipe-agent-custom-llm`. If a push ever 4xxs on the image name, hardcode the lowercase `images:` value.
- **`type=sha` in the metadata tags is load-bearing:** on non-tag events the semver tags are empty, so `type=sha` guarantees the locally-loaded image always has at least one tag for the smoke step.
- **Independent of test PR #3:** this branch is off `main`; the only shared file is `README.md` (distinct sections), so a merge conflict is unlikely and trivial if it happens.
- **Portability:** the `Dockerfile`, `entrypoint.sh`, `.dockerignore`, and `docker.yml` port directly to `recipe-agent-custom-llm-tts` (the `llm` endpoint differs but the container shape is identical).
```