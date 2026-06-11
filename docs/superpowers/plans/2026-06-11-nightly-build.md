# Daily Build (Nightly CI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a daily scheduled `nightly.yml` workflow that re-runs the full test suite + the Docker dry-run build, by making `ci.yml` and `docker.yml` reusable (`workflow_call`).

**Architecture:** Add `workflow_call` to the two existing workflows' `on:` blocks (additive — push/PR behavior unchanged), then a new `nightly.yml` triggers on a daily cron + manual dispatch and `uses:` both reusable workflows. The Docker dry-run (build + smoke, no push) falls out automatically because a scheduled run's ref is `refs/heads/main`, never a tag.

**Tech Stack:** GitHub Actions (reusable workflows / `workflow_call`, `schedule`, `workflow_dispatch`).

**Spec:** `docs/superpowers/specs/2026-06-11-nightly-build-design.md`

**Repo & branch:** `recipe-agent-custom-llm` (local folder `/Users/zhangqianze/Documents/agent-recipes-python`), branch `ci/nightly-build` (already created off the updated `main`, which has `ci.yml` + `docker.yml`).

---

## Conventions

- Conventional Commits, lowercase after prefix, present tense, NO AI attribution / NO `Co-Authored-By`, no `--no-verify`. If a commit fails on git identity, prefix with `git -c user.email="qianze.zhang@hotmail.com"`.
- These are GitHub-Actions-only changes; there is no local runtime to exercise. Validation is YAML parse + structural checks (GitHub validates the workflow on push; the nightly itself is only triggerable after merge to `main`).

---

## Task 1: Make `ci.yml` reusable

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add `workflow_call` to the trigger block**

In `.github/workflows/ci.yml`, change:
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
Make no other change.

- [ ] **Step 2: Confirm the trigger and that nothing else moved**

Run (PyYAML isn't installed in the venv, so use structural checks):
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
grep -nE "^  (push|pull_request|workflow_call):" .github/workflows/ci.yml
grep -nP "\t" .github/workflows/ci.yml && echo "HAS TABS (bad)" || echo "no tabs"
git diff --stat .github/workflows/ci.yml
```
Expected: the three triggers `push`, `pull_request`, `workflow_call` all listed; `no tabs`; and the diffstat shows **only `ci.yml` changed, +1 line** (just the `workflow_call:` addition).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: make ci.yml a reusable workflow (workflow_call)"
```

---

## Task 2: Make `docker.yml` reusable

**Files:**
- Modify: `.github/workflows/docker.yml`

- [ ] **Step 1: Add `workflow_call` to the trigger block**

In `.github/workflows/docker.yml`, change:
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
Make no other change (the `permissions`, build/smoke, and tag-gated push steps stay as-is).

- [ ] **Step 2: Confirm the trigger and that nothing else moved**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
grep -nE "^  (push|pull_request|workflow_call):" .github/workflows/docker.yml
grep -nP "\t" .github/workflows/docker.yml && echo "HAS TABS (bad)" || echo "no tabs"
git diff --stat .github/workflows/docker.yml
```
Expected: `push`, `pull_request`, `workflow_call` listed; `no tabs`; diffstat shows **only `docker.yml` changed, +1 line**.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/docker.yml
git commit -m "ci: make docker.yml a reusable workflow (workflow_call)"
```

---

## Task 3: Add the `nightly.yml` workflow

**Files:**
- Create: `.github/workflows/nightly.yml`

- [ ] **Step 1: Create `.github/workflows/nightly.yml`**

```yaml
name: nightly

on:
  schedule:
    - cron: "0 18 * * *"   # 18:00 UTC daily
  workflow_dispatch:        # manual trigger (only available once on the default branch)

permissions:
  contents: read
  packages: write           # mirrors docker.yml; unused on the no-push nightly path

jobs:
  tests:
    uses: ./.github/workflows/ci.yml

  docker:
    uses: ./.github/workflows/docker.yml
```

- [ ] **Step 2: Validate the structure + the reusable references**

Run (structural checks; no PyYAML needed):
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
grep -nE 'cron: "0 18 \* \* \*"|workflow_dispatch:|uses: \./\.github/workflows/(ci|docker)\.yml' .github/workflows/nightly.yml
grep -nP "\t" .github/workflows/nightly.yml && echo "HAS TABS (bad)" || echo "no tabs"
```
Expected: the `cron`, `workflow_dispatch`, and both `uses: ./.github/workflows/ci.yml` and `.../docker.yml` lines are listed; `no tabs`.

- [ ] **Step 3: Confirm the referenced workflows exist (the reusable targets)**

Run:
```bash
test -f .github/workflows/ci.yml && test -f .github/workflows/docker.yml && echo "both reusable targets present"
```
Expected: `both reusable targets present`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/nightly.yml
git commit -m "ci: add daily nightly build calling ci + docker reusable workflows"
```

---

## Task 4: Push + open PR

**Files:** none (git only).

- [ ] **Step 1: Push the branch**

```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
git push -u origin ci/nightly-build
```

- [ ] **Step 2: Open the PR** (REST — the GraphQL `gh pr create` path 401s under the lapsed SSO session)

```bash
REPO=AgoraIO-Conversational-AI/recipe-agent-custom-llm
gh api -X POST "repos/$REPO/pulls" \
  -f title="ci: add daily nightly build (tests + docker dry-run)" \
  -f head="ci/nightly-build" -f base="main" \
  -f body="Adds a daily scheduled \`nightly.yml\` (cron 0 18 * * * + workflow_dispatch) that re-runs the full test suite and the Docker dry-run build by making ci.yml and docker.yml reusable (workflow_call). The Docker job is build+smoke only on the nightly path (a scheduled run's ref is refs/heads/main, never a tag, so the existing push gate skips). Purpose: catch dependency/base-image drift that no commit triggers (Python deps are lower-bound pinned; base images float). Note: scheduled + workflow_dispatch only fire from the default branch, so the nightly is testable only after merge — then trigger it via workflow_dispatch to confirm the wiring." \
  --jq '{number, url: .html_url, state}'
```
Expected: a JSON object with the new PR number + URL.

- [ ] **Step 3: Note the post-merge verification step**

After this PR merges to `main`, trigger `nightly` via **workflow_dispatch** in the Actions UI and confirm both child workflows run and the run is green (don't wait a day for the first cron). This is the real smoke test for the reusable-call wiring; flag it to the user.

---

## Self-Review notes (for the implementer)

- **These changes can't be exercised pre-merge.** `nightly.yml` only triggers on `schedule`/`workflow_dispatch`, both of which are default-branch-only — so neither the PR checks nor a manual dispatch will run it until it's on `main`. Pre-merge confidence = YAML validity (Tasks 1–3 validations) + the fact that `ci.yml`/`docker.yml` are already green in Actions. Do not claim the nightly "passed" before merge; it cannot have run.
- **Keep the bare `on:` key** — GitHub Actions expects `on:` unquoted. (PyYAML would parse it as the boolean `True`, which is why the validations use `grep`, not a YAML loader. Don't "fix" the files to quote `on:`.)
- **Additive triggers are intentional:** adding `workflow_call` alongside `push`/`pull_request` keeps the existing per-push/PR runs working AND makes the workflow callable. A workflow may be both.
- **No `with:`/`secrets:` needed** on the `uses:` calls — neither `ci.yml` nor `docker.yml` declares `inputs`, and both only use the automatic `GITHUB_TOKEN` (no named secrets), so `secrets: inherit` is unnecessary.
