# Daily Build (Nightly CI) — Design

**Date:** 2026-06-11
**Status:** Approved
**Repo:** `recipe-agent-custom-llm` (local folder `/Users/zhangqianze/Documents/agent-recipes-python`)
**Branch:** `ci/nightly-build` off `main`

## Goal

Add a single **daily scheduled build** that runs all relevant tests (server/llm pytest matrix + web bun tests) and **dry-run builds** the Docker image (build + smoke, no registry push) — one green/red status per day. It reuses the existing `ci.yml` and `docker.yml` workflows rather than duplicating their logic.

## Context

`main` already has both workflows (PRs #3 and #4 merged):
- `.github/workflows/ci.yml` — pytest matrix (`{ubuntu,macos,windows} × {3.10,3.13}`) for `server/` + `llm/`, plus a Bun job for `web/`. Triggers: `push`, `pull_request`.
- `.github/workflows/docker.yml` — build + smoke-test the combined image; push to GHCR **only** on `v*` tags. Triggers: `push` (branches + tags), `pull_request`. Has `permissions: { contents: read, packages: write }`.

## Locked Decisions

1. **One new `nightly.yml`** that, on a daily schedule, **calls** `ci.yml` and `docker.yml` as **reusable workflows** (`workflow_call`). One scheduled run, one status.
2. **Schedule: `cron: "0 18 * * *"`** (18:00 UTC daily) plus **`workflow_dispatch`** (manual trigger).
3. **Dry-run Docker falls out for free:** a scheduled run's `github.ref` is `refs/heads/main` (never a tag), and `docker.yml` already gates its login/push on `startsWith(github.ref, 'refs/tags/')`. So the nightly Docker job builds + smoke-tests and **does not push** — no special-casing needed.
4. **Reuse, don't duplicate:** make `ci.yml`/`docker.yml` reusable by **adding** `workflow_call` to their `on:` blocks (additive — their `push`/`pull_request` behavior is unchanged; a workflow may be both directly-triggered and reusable).

## Components

### `.github/workflows/ci.yml` — add `workflow_call`
Change the trigger block from:
```yaml
on:
  push:
  pull_request:
```
to:
```yaml
on:
  push:
  pull_request:
  workflow_call:
```
No other change. The `backend` + `web` jobs are unchanged.

### `.github/workflows/docker.yml` — add `workflow_call`
Change:
```yaml
on:
  push:
    branches: ["**"]
    tags: ["v*"]
  pull_request:
```
to:
```yaml
on:
  push:
    branches: ["**"]
    tags: ["v*"]
  pull_request:
  workflow_call:
```
The existing `permissions`, build/smoke, and tag-gated push steps are unchanged.

### `.github/workflows/nightly.yml` — new
```yaml
name: nightly

on:
  schedule:
    - cron: "0 18 * * *"   # 18:00 UTC daily
  workflow_dispatch:        # allow manual runs (incl. from a branch, for testing)

permissions:
  contents: read
  packages: write           # mirror docker.yml; unused on the no-push nightly path

jobs:
  tests:
    uses: ./.github/workflows/ci.yml

  docker:
    uses: ./.github/workflows/docker.yml
```
- `uses: ./.github/workflows/<x>.yml` runs each reusable workflow in this repo at the same ref. The two jobs run in parallel; the nightly run is green only if **both** pass.
- `permissions` on the caller is intersected with each called workflow's; declaring `contents: read` + `packages: write` covers both (the Docker job needs no push on the nightly path, so `packages: write` is effectively unused but harmless and future-proof). `GITHUB_TOKEN` is available to called workflows automatically; neither `ci.yml` nor `docker.yml` uses named secrets, so no `secrets: inherit` is required.

## Behavior

| Trigger | tests (`ci.yml`) | docker (`docker.yml`) |
| --- | --- | --- |
| daily `schedule` (18:00 UTC, on `main`) | full pytest + bun matrix | build + smoke, **no push** (ref isn't a tag) |
| `workflow_dispatch` (manual) | same | same |

The existing per-PR/push runs of `ci.yml` and `docker.yml` are unaffected.

## Testing / Verification

- **YAML validity:** the three workflow files parse (actionlint or `yaml.safe_load`).
- **Reusable-call wiring:** after merge to `main`, trigger `nightly` via **`workflow_dispatch`** from the Actions UI and confirm both child workflows run and the run is green. (Scheduled triggers only fire from the **default branch**, so the cron itself can't be exercised until the file is on `main`; `workflow_dispatch` is the pre/post-merge smoke for the wiring.)
- No local runtime to validate — these are GitHub-Actions-only changes.

## Risks / Notes

- **Scheduled workflows run only from the default branch (`main`).** The cron won't fire while `nightly.yml` is on the feature branch; that's expected. Use `workflow_dispatch` to test the wiring before/after merge.
- **`workflow_call` added alongside `push`/`pull_request`** is supported — a single workflow can be both directly triggered and reusable. This does not double-run anything (nightly only triggers on schedule/dispatch).
- **No notification design:** GitHub emails the repo's watchers/admins on scheduled-workflow failure by default; explicit Slack/issue alerts are out of scope (YAGNI).
- **Cost:** one extra daily run of the full matrix + Docker build. Acceptable; cached layers (`type=gha`) keep the Docker build fast.
- **Portability:** the same three-file pattern ports to `recipe-agent-custom-llm-tts` once its `ci.yml`/`docker.yml` exist.
```