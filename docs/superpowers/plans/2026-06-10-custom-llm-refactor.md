# Custom LLM Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `agent-recipes-python` from a multi-recipe collection into a single **custom-llm** recipe whose structure, scripts, and root docs are aligned with the `agent-quickstart-python` base template.

**Architecture:** Two Python backends — `server/` (agent backend on :8000, mirrors the reference; owns Agora token + agent lifecycle) and `llm/` (a public OpenAI-compatible `POST /chat/completions` mock on :8001 that Agora cloud calls via a tunnel) — plus a shared Next.js `web/` frontend resynced from the reference. The agent backend wires the LLM stage to the `llm/` endpoint using the SDK's `CustomLLM` vendor.

**Tech Stack:** Python 3.8+, FastAPI, uvicorn, `agora-agents>=2.0.0` (migrated from `agora-agent-server-sdk` 1.4.x); Next.js 16 / React 19 / TypeScript; Bun for orchestration; ngrok (or any tunnel) for the public LLM endpoint.

**Spec:** `docs/superpowers/specs/2026-06-10-custom-llm-refactor-design.md`

**Reference template (local sibling clone):** `/Users/zhangqianze/Documents/agent-quickstart-python` — referred to below as `$REF`. If it is not present, clone it first: `git clone git@github.com:AgoraIO-Conversational-AI/agent-quickstart-python.git /Users/zhangqianze/Documents/agent-quickstart-python`.

---

## Conventions for this plan

- Commit messages use Conventional Commits, lowercase after the prefix, present tense, **no AI attribution / Co-Authored-By trailers** (this repo's `AGENTS.md` rule). Do **not** pass `--no-verify`.
- All work happens on the `feat/custom-llm-refactor` branch (Task 0).
- "Verify" steps are the test harness for this refactor: the `verify:*` scripts and Python `py_compile`. Run them exactly as written and confirm the stated expected output before committing.

---

## Task 0: Branches — back up multi-recipe state, start feature branch

**Files:** none (git only)

- [ ] **Step 1: Confirm a clean tree on `main`**

Run: `git status --short && git rev-parse --abbrev-ref HEAD`
Expected: no output from `status` (clean) and `main` printed. If not clean, stop and resolve before continuing.

- [ ] **Step 2: Create and push the backup branch**

```bash
git branch backup/main-multi-recipe main
git push -u origin backup/main-multi-recipe
```
Expected: `git push` reports the new branch created on `origin` (`* [new branch] backup/main-multi-recipe -> backup/main-multi-recipe`). This durably preserves the `audio-modalities` recipe for later extraction.

- [ ] **Step 3: Create the feature branch**

```bash
git checkout -b feat/custom-llm-refactor
```
Expected: `Switched to a new branch 'feat/custom-llm-refactor'`.

---

## Task 1: Restructure backend dirs — `custom-llm/` → `server/` + `llm/`, delete `audio-modalities/`

**Files:**
- Move: `custom-llm/src/__init__.py` → `server/src/__init__.py`
- Move: `custom-llm/src/agent.py` → `server/src/agent.py`
- Move: `custom-llm/src/server.py` → `server/src/server.py`
- Move: `custom-llm/src/custom_llm_server.py` → `llm/src/custom_llm_server.py`
- Create: `llm/src/__init__.py`
- Delete: `audio-modalities/` (whole dir), `custom-llm/` leftovers (`.env.example`, `.env.local`, `.gitignore`, `README.md`, `requirements.txt`, `src/file.pcm`, `src/file.txt` if present)

- [ ] **Step 1: Create the new directory skeleton and move source files (preserve history)**

```bash
mkdir -p server/src server/scripts llm/src
git mv custom-llm/src/__init__.py server/src/__init__.py
git mv custom-llm/src/agent.py server/src/agent.py
git mv custom-llm/src/server.py server/src/server.py
git mv custom-llm/src/custom_llm_server.py llm/src/custom_llm_server.py
```
Expected: no errors. `git status` shows four renames staged.

- [ ] **Step 2: Add the `llm/` package marker**

Create `llm/src/__init__.py` as an empty file:

```python
```

(Empty file — same as the existing `server/src/__init__.py`.)

- [ ] **Step 3: Remove the obsolete recipe + the audio-modalities recipe**

```bash
git rm -r audio-modalities
git rm -rf custom-llm
# Remove any leftover untracked files (e.g. a local .env.local or __pycache__)
# so the directories do not linger on disk.
rm -rf audio-modalities custom-llm
```
Expected: `custom-llm/` and `audio-modalities/` are fully removed from both git and the working tree (the `src/*.py` files were already moved out of `custom-llm/`). `git status` shows the deletions.

- [ ] **Step 4: Verify the tree shape**

Run: `find server llm -type f -not -path '*/venv/*' | sort`
Expected exactly:
```
llm/src/__init__.py
llm/src/custom_llm_server.py
server/src/__init__.py
server/src/agent.py
server/src/server.py
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: split custom-llm recipe into server/ and llm/, drop audio-modalities"
```

---

## Task 2: `server/src/agent.py` — switch LLM vendor to `CustomLLM`, require `CUSTOM_LLM_URL`

**Files:**
- Modify: `server/src/agent.py`

The current file (moved from the recipe) imports `OpenAI` and builds the LLM with `OpenAI(base_url=...)`, defaults `CUSTOM_LLM_URL` to `localhost`, and only warns on a missing key. We switch to the purpose-built `CustomLLM` vendor and make both `CUSTOM_LLM_URL` and `CUSTOM_LLM_API_KEY` hard requirements.

- [ ] **Step 1: Update the vendor import**

In `server/src/agent.py`, change:

```python
from agora_agent.agentkit.vendors import DeepgramSTT, MiniMaxTTS, OpenAI
```

to:

```python
from agora_agent.agentkit.vendors import CustomLLM, DeepgramSTT, MiniMaxTTS
```

- [ ] **Step 2: Make `CUSTOM_LLM_URL` and `CUSTOM_LLM_API_KEY` required**

Replace this block:

```python
        # Custom LLM configuration
        # CUSTOM_LLM_URL must be a publicly accessible URL for Agora cloud to reach.
        # For local dev: expose port 8001 via ngrok and use the ngrok URL here.
        self.custom_llm_url = os.getenv("CUSTOM_LLM_URL", "http://localhost:8001/chat/completions")
        self.custom_llm_api_key = os.getenv("CUSTOM_LLM_API_KEY", "any-key-here")
        self.custom_llm_model = os.getenv("CUSTOM_LLM_MODEL", "mock-model")

        if not self.app_id or not self.app_certificate:
            raise ValueError("AGORA_APP_ID and AGORA_APP_CERTIFICATE are required")

        if not self.custom_llm_api_key:
            logger.warning(
                "CUSTOM_LLM_API_KEY is not set. Using default placeholder."
            )
```

with:

```python
        # Custom LLM configuration.
        # CUSTOM_LLM_URL is the FULL OpenAI-compatible chat-completions URL and must be
        # PUBLICLY reachable: Agora cloud (not this backend) calls it. For local dev,
        # expose the llm/ server on port 8001 via ngrok and paste that URL here.
        # There is intentionally no localhost default: a localhost URL would let the
        # agent "start" while its LLM calls silently fail cloud-side.
        self.custom_llm_url = os.getenv("CUSTOM_LLM_URL")
        self.custom_llm_api_key = os.getenv("CUSTOM_LLM_API_KEY", "any-key-here")
        self.custom_llm_model = os.getenv("CUSTOM_LLM_MODEL", "mock-model")

        if not self.app_id or not self.app_certificate:
            raise ValueError("AGORA_APP_ID and AGORA_APP_CERTIFICATE are required")

        if not self.custom_llm_url:
            raise ValueError(
                "CUSTOM_LLM_URL is required (the public chat-completions URL of your "
                "custom LLM endpoint, e.g. https://<tunnel>/chat/completions)"
            )

        if not self.custom_llm_api_key:
            # CustomLLM rejects a missing api_key, and base_url is only valid with a key.
            raise ValueError(
                "CUSTOM_LLM_API_KEY is required when using a custom LLM endpoint"
            )
```

- [ ] **Step 3: Build the LLM with `CustomLLM` and update the comment block**

Replace this block:

```python
        # ============================================================
        # KEY DIFFERENCE: Use OpenAI vendor with custom base_url
        # ============================================================
        # Instead of using the default OpenAI endpoint, we point the OpenAI
        # vendor to our own Custom LLM proxy server. The proxy implements
        # the OpenAI Chat Completions API and can:
        # - Add custom preprocessing (RAG, context injection)
        # - Route to different models dynamically
        # - Add logging and analytics
        # - Implement custom tool calling
        # ============================================================
        llm = OpenAI(
            base_url=self.custom_llm_url,
            api_key=self.custom_llm_api_key,
            model=self.custom_llm_model,
            greeting_message=self.greeting,
            failure_message="Please wait a moment.",
            max_history=15,
            max_tokens=1024,
            temperature=0.7,
            top_p=0.95,
        )
```

with:

```python
        # ============================================================
        # KEY DIFFERENCE: Use the SDK's CustomLLM vendor
        # ============================================================
        # The base quickstart uses a managed `OpenAI(model="gpt-4o-mini")`.
        # This recipe instead points the LLM stage at our own OpenAI-compatible
        # endpoint (the llm/ server) via the purpose-built `CustomLLM` vendor.
        # CustomLLM stamps `vendor: "custom"` in the wire config and requires
        # both base_url and api_key. Your endpoint can then:
        # - Add custom preprocessing (RAG, context injection)
        # - Route to different models dynamically
        # - Add logging and analytics
        # - Implement custom tool calling
        # ============================================================
        llm = CustomLLM(
            base_url=self.custom_llm_url,
            api_key=self.custom_llm_api_key,
            model=self.custom_llm_model,
            greeting_message=self.greeting,
            failure_message="Please wait a moment.",
            max_history=15,
            max_tokens=1024,
            temperature=0.7,
            top_p=0.95,
        )
```

- [ ] **Step 4: Compile-check the file**

Run: `python3 -m py_compile server/src/agent.py`
Expected: exit code 0, no output. (`py_compile` does not import `agora_agent`, so no venv is needed here.)

- [ ] **Step 5: Grep to confirm no stray `OpenAI(` references remain**

Run: `grep -n "OpenAI" server/src/agent.py`
Expected: no matches (only `CustomLLM` is used now). If `grep` exits non-zero with no output, that is the success case.

- [ ] **Step 6: Commit**

```bash
git add server/src/agent.py
git commit -m "feat(server): use CustomLLM vendor and require CUSTOM_LLM_URL"
```

---

## Task 3: `server/src/server.py` — fix the token call for the 2.0.0 SDK

**Files:**
- Modify: `server/src/server.py`

The 2.0.0 SDK signature is `generate_convo_ai_token(app_id, app_certificate, channel_name, uid: int, ...)`. The moved file still uses the 1.4.x-style `account=str(user_uid)` keyword, which raises `TypeError` on 2.0.0.

- [ ] **Step 1: Replace the token-generation call**

In `server/src/server.py`, change:

```python
        token = generate_convo_ai_token(
            app_id=app_id,
            app_certificate=app_certificate,
            channel_name=channel_name,
            account=str(user_uid),
            token_expire=3600,
        )
```

to:

```python
        token = generate_convo_ai_token(
            app_id=app_id,
            app_certificate=app_certificate,
            channel_name=channel_name,
            uid=user_uid,
            token_expire=3600,
        )
```

- [ ] **Step 2: Compile-check**

Run: `python3 -m py_compile server/src/server.py`
Expected: exit code 0, no output.

- [ ] **Step 3: Confirm no other `account=` token usage remains**

Run: `grep -n "account=" server/src/server.py`
Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add server/src/server.py
git commit -m "fix(server): call generate_convo_ai_token with uid for agora-agents 2.0.0"
```

---

## Task 4: `llm/src/custom_llm_server.py` — load dotenv with `override=False`

**Files:**
- Modify: `llm/src/custom_llm_server.py`

So the verify harness can inject a random `CUSTOM_LLM_PORT` that wins over any checked-in `.env.local`. No behavior change for `dev` (which exports no `CUSTOM_LLM_PORT`).

- [ ] **Step 1: Flip both dotenv loads to non-override**

In `llm/src/custom_llm_server.py`, change:

```python
# Load environment variables
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_base_dir, ".env.local"), override=True)
load_dotenv(os.path.join(_base_dir, ".env"), override=True)
```

to:

```python
# Load environment variables.
# override=False so an explicitly-exported value (e.g. CUSTOM_LLM_PORT injected by
# the verify:local:llm harness, or a process manager) takes precedence over a
# checked-in .env.local. In normal `dev` no port is exported, so .env.local wins.
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_base_dir, ".env.local"), override=False)
load_dotenv(os.path.join(_base_dir, ".env"), override=False)
```

- [ ] **Step 2: Compile-check**

Run: `python3 -m py_compile llm/src/custom_llm_server.py`
Expected: exit code 0, no output.

- [ ] **Step 3: Commit**

```bash
git add llm/src/custom_llm_server.py
git commit -m "refactor(llm): load dotenv with override=false so injected port wins"
```

---

## Task 5: Backend support files — env examples, requirements, gitignores, fake server

**Files:**
- Create: `server/.env.example`, `server/requirements.txt`, `server/.gitignore`, `server/README.md`
- Create: `llm/.env.example`, `llm/requirements.txt`, `llm/.gitignore`, `llm/README.md`
- Create: `server/scripts/run_fake_server.py`

- [ ] **Step 1: Create `server/.env.example`** (no `PORT` line — see spec rationale)

```
AGORA_APP_ID=your_agora_app_id
AGORA_APP_CERTIFICATE=your_agora_app_certificate
AGENT_GREETING=Hi there! I'm your AI assistant powered by a custom LLM. How can I help?
CUSTOM_LLM_URL=https://your-tunnel.ngrok-free.app/chat/completions
CUSTOM_LLM_API_KEY=any-key-here
CUSTOM_LLM_MODEL=mock-model
```

- [ ] **Step 2: Create `server/requirements.txt`** (migrated to `agora-agents>=2.0.0`)

```
fastapi>=0.100.0
uvicorn>=0.20.0
requests>=2.31.0
python-dotenv>=1.0.0
agora-agents>=2.0.0
# Enables httpx to route through a SOCKS proxy (e.g. all_proxy=socks5://...)
socksio>=1.0.0
```

- [ ] **Step 3: Create `llm/.env.example`**

```
CUSTOM_LLM_PORT=8001
```

- [ ] **Step 4: Create `llm/requirements.txt`** (no `agora-agents` — the endpoint is provider-agnostic)

```
fastapi>=0.100.0
uvicorn>=0.20.0
python-dotenv>=1.0.0
```

- [ ] **Step 5: Create `server/.gitignore` and `llm/.gitignore`** (identical content in both files)

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
.venv

# Environment variables
.env.local
.env

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 6: Create `server/scripts/run_fake_server.py`** (verbatim from the reference; used by `verify:local:fastapi` / `verify:web:proxy`)

```python
import os
import sys

import uvicorn


class FakeAgent:
    def __init__(self):
        self.started_agent_ids = set()

    async def start(self, channel_name: str, agent_uid: int, user_uid: int, output_audio_codec=None):
        if not channel_name or agent_uid <= 0 or user_uid <= 0:
            raise ValueError("channel_name, agent_uid, and user_uid must be valid")

        agent_id = f"fake-agent-{agent_uid}"
        self.started_agent_ids.add(agent_id)
        return {
            "agent_id": agent_id,
            "channel_name": channel_name,
            "status": "started",
        }

    async def stop(self, agent_id: str):
        if not agent_id:
            raise ValueError("agent_id is required")
        self.started_agent_ids.discard(agent_id)


def main():
    server_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_root = os.path.join(server_root, "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    import server as server_module

    server_module.agent = FakeAgent()

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(server_module.app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Create `server/README.md`**

```markdown
# Agora Agent Backend — Custom LLM Recipe

FastAPI service that owns Agora token generation and agent session lifecycle for
the custom-llm recipe. It is the service the web client reaches through the
Next.js `/api/*` rewrite proxy (port 8000).

## What's different from the base quickstart

The LLM stage uses the SDK's `CustomLLM` vendor instead of a managed
`OpenAI(model="gpt-4o-mini")`. It points the agent at your own OpenAI-compatible
endpoint (the `llm/` server in this repo) via `CUSTOM_LLM_URL`. STT (Deepgram)
and TTS (MiniMax) remain Agora-managed.

## Run

Use the repo-root `README.md` for the full local flow (`bun run dev`). To work on
this module directly:

```bash
cd server
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python src/server.py
```

## Environment

`server/.env.example` is the template. Required:

- `AGORA_APP_ID`, `AGORA_APP_CERTIFICATE` — Agora project credentials.
- `CUSTOM_LLM_URL` — the **public** chat-completions URL of your `llm/` endpoint
  (e.g. `https://<tunnel>/chat/completions`). Agora cloud calls this directly, so
  it cannot be `localhost`.
- `CUSTOM_LLM_API_KEY` — forwarded by Agora cloud as `Authorization: Bearer`.
  Required by the `CustomLLM` vendor.

Optional: `CUSTOM_LLM_MODEL` (default `mock-model`), `AGENT_GREETING`, `PORT`
(default `8000`).

## API

- `GET /get_config` — token + channel/UID config
- `POST /startAgent` — start an agent session
- `POST /stopAgent` — stop an agent session

The repo-root `bun run verify:local:fastapi` exercises these routes through the
Next proxy using a fake agent (`scripts/run_fake_server.py`), so no live Agora
session is required.
```

- [ ] **Step 8: Create `llm/README.md`**

```markdown
# Custom LLM Endpoint — Mock

An OpenAI-compatible `POST /chat/completions` server (port 8001) that Agora cloud
calls during a conversation. This mock returns canned streaming responses so you
can exercise the full STT → custom LLM → TTS pipeline with **no LLM API key**.

It has no `agora-agents` dependency — it is a plain FastAPI app, which is exactly
the boundary you replace with your own model.

## The contract

Implement `POST /chat/completions` returning OpenAI-style SSE:

- first chunk sets `delta.role = "assistant"`
- content chunks carry `delta.content`
- a final chunk sets `finish_reason = "stop"`
- the stream terminates with `data: [DONE]`

Only streaming (`stream: true`) is supported; non-streaming requests return 400.

## Run

```bash
cd llm
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python src/custom_llm_server.py     # serves on CUSTOM_LLM_PORT (default 8001)
```

## Expose it publicly

Agora cloud — not the browser — calls this server, so it must be reachable from
the public internet. For local dev, tunnel it:

```bash
ngrok http 8001
```

Then set `CUSTOM_LLM_URL=https://<tunnel>/chat/completions` in `server/.env.local`.

## Auth

This mock does **not** authenticate. A production endpoint should validate the
`Authorization: Bearer <CUSTOM_LLM_API_KEY>` header that Agora cloud forwards
(the key you set on the agent backend).

## Replace the mock

Edit `get_mock_response()` in `src/custom_llm_server.py`. Examples: call a local
model (Ollama/vLLM), inject RAG context before generating, or route models by
content.
```

- [ ] **Step 9: Compile-check the fake server**

Run: `python3 -m py_compile server/scripts/run_fake_server.py`
Expected: exit code 0, no output.

- [ ] **Step 10: Commit**

```bash
git add server/.env.example server/requirements.txt server/.gitignore server/README.md \
        server/scripts/run_fake_server.py \
        llm/.env.example llm/requirements.txt llm/.gitignore llm/README.md
git commit -m "feat: add server/ and llm/ support files (env, deps, fake server, READMEs)"
```

---

## Task 6: Web resync — adopt reference `web/`, re-apply custom-LLM branding

**Files:**
- Overwrite/add: everything under `web/` from `$REF/web/` (except `node_modules`, `.next`, `dist`)
- Modify (branding deltas): `web/app/layout.tsx`, `web/src/components/QuickstartPreCallCard.tsx`, `web/src/components/QuickstartPipelineMetrics.tsx`

- [ ] **Step 1: Resync `web/` from the reference**

```bash
rsync -a \
  --exclude 'node_modules' --exclude '.next' --exclude 'dist' \
  /Users/zhangqianze/Documents/agent-quickstart-python/web/ web/
```
Expected: no errors. This adds the missing `web/scripts/`, `web/docs/`, `web/.claude/`, `web/public/*` assets, `next-env.d.ts`, `bun.lock`, and `share-button.tsx`, and overwrites the shared files with the reference versions (regaining React strict mode, image optimization, the favicon `icons` block, and the Agora-logo footer with share button).

- [ ] **Step 2: Re-apply branding delta — page title & description** (`web/app/layout.tsx`)

The reference version now in place reads:

```tsx
	title: "Talk to a voice agent now | Agora",
	description:
		"Python + FastAPI quickstart: real-time voice agent with live transcript, streaming audio, and low latency from Agora's Conversational AI Engine—FastAPI service you can fork, extend, and ship.",
```

Change those two fields to (keep the `icons` block immediately after, untouched):

```tsx
	title: "Custom LLM Recipe | Agora Conversational AI",
	description:
		"Recipe: Bring your own LLM to Agora Conversational AI Engine via a custom OpenAI-compatible proxy.",
```

- [ ] **Step 3: Re-apply branding delta — pre-call card copy** (`web/src/components/QuickstartPreCallCard.tsx`)

Change:

```tsx
			<h1 className="text-[28px] font-medium leading-[1.2] text-white">
				Try Agora&apos;s Voice Agent
			</h1>
			<p className="mt-[14px] text-sm font-medium leading-6 text-muted-foreground">
				Built on Agora&apos;s flagship Conversational AI engine, for effortless
				agentic conversations.
			</p>
```

to:

```tsx
			<h1 className="text-[28px] font-medium leading-[1.2] text-white">
				Custom LLM Recipe
			</h1>
			<p className="mt-[14px] text-sm font-medium leading-6 text-muted-foreground">
				Bring your own LLM to Agora&apos;s Conversational AI Engine via a custom
				OpenAI-compatible proxy server.
			</p>
```

- [ ] **Step 4: Re-apply branding delta — pipeline metric label** (`web/src/components/QuickstartPipelineMetrics.tsx`)

Change:

```tsx
	{ key: "llm", label: "OpenAI LLM", metricTypes: ["llm", "mllm"] },
```

to:

```tsx
	{ key: "llm", label: "Custom LLM", metricTypes: ["llm", "mllm"] },
```

- [ ] **Step 5: Confirm only the three intended branding deltas differ from the reference**

Run:
```bash
diff -rq --exclude node_modules --exclude .next --exclude dist \
  /Users/zhangqianze/Documents/agent-quickstart-python/web web | sort
```
Expected: differences reported **only** for `app/layout.tsx`, `src/components/QuickstartPreCallCard.tsx`, and `src/components/QuickstartPipelineMetrics.tsx` (plus possibly `bun.lock` if Bun regenerated it). No other source files should differ. `web/scripts/verify-local-llm.ts` does not exist in the reference and will appear as "Only in web/..." after Task 7 — it is fine if you run this diff again later and see that one extra entry.

- [ ] **Step 6: Commit**

```bash
git add web
git commit -m "chore(web): resync frontend from base quickstart with custom-llm branding"
```

---

## Task 7: Add the `verify:local:llm` contract harness

**Files:**
- Create: `web/scripts/verify-local-llm.ts`

This is the test for the `llm/` endpoint: it boots the real mock on a random port and asserts the OpenAI SSE contract. The mock needs no keys, so this is a genuine end-to-end contract check. Modeled on the reference's `web/scripts/verify-local-fastapi.ts`.

- [ ] **Step 1: Write the harness**

Create `web/scripts/verify-local-llm.ts`:

```ts
import { existsSync } from 'node:fs'
import path from 'node:path'

type BunRuntime = typeof globalThis & {
  Bun: {
    sleep: (ms: number) => Promise<void>
    spawn: (options: {
      cmd: string[]
      cwd: string
      env: Record<string, string | undefined>
      stdout: 'ignore'
      stderr: 'pipe'
    }) => {
      kill: () => void
      exited: Promise<number>
      exitCode: number | null
      stderr: ReadableStream<Uint8Array> | null
    }
    spawnSync: (options: {
      cmd: string[]
      cwd: string
      stderr: 'pipe'
      stdout: 'ignore'
    }) => {
      exitCode: number
      stderr: { toString: () => string }
    }
  }
}

const bunRuntime = globalThis as BunRuntime

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) {
    throw new Error(message)
  }
}

async function waitForHealthy(baseUrl: string, timeoutMs: number) {
  const deadline = Date.now() + timeoutMs
  let lastError = 'custom LLM server did not start'

  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl}/health`)
      if (response.ok) {
        return
      }
      lastError = `health returned ${response.status}`
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error)
    }

    await bunRuntime.Bun.sleep(250)
  }

  throw new Error(`Timed out waiting for custom LLM server: ${lastError}`)
}

async function main() {
  const projectRoot = process.cwd() // web/
  const llmRoot = path.resolve(projectRoot, '..', 'llm')
  const venvPython = path.join(llmRoot, 'venv', 'bin', 'python')

  if (!existsSync(venvPython)) {
    throw new Error('Missing llm/venv/bin/python. Run bun run setup:llm before verify:local:llm.')
  }

  const dependencyCheck = bunRuntime.Bun.spawnSync({
    cmd: [venvPython, '-c', 'import dotenv, fastapi, uvicorn'],
    cwd: llmRoot,
    stderr: 'pipe',
    stdout: 'ignore',
  })
  if (dependencyCheck.exitCode !== 0) {
    const stderr = dependencyCheck.stderr.toString().trim()
    throw new Error(
      `The llm virtualenv is missing required packages. Run bun run setup:llm before verify:local:llm.${stderr ? ` Python said: ${stderr}` : ''}`,
    )
  }

  const port = 43160 + Math.floor(Math.random() * 20)
  const baseUrl = `http://127.0.0.1:${port}`

  const llmProcess = bunRuntime.Bun.spawn({
    cmd: [venvPython, 'src/custom_llm_server.py'],
    cwd: llmRoot,
    env: {
      ...process.env,
      CUSTOM_LLM_PORT: String(port),
    },
    stdout: 'ignore',
    stderr: 'pipe',
  })

  try {
    await waitForHealthy(baseUrl, 10_000)

    const response = await fetch(`${baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer any-key-here',
      },
      body: JSON.stringify({
        model: 'mock-model',
        messages: [{ role: 'user', content: 'Hello' }],
        stream: true,
      }),
    })

    assert(response.status === 200, 'POST /chat/completions should return 200 for a streaming request')
    assert(
      (response.headers.get('content-type') ?? '').includes('text/event-stream'),
      'POST /chat/completions should return a text/event-stream response',
    )

    const body = await response.text()
    assert(
      body.includes('"role": "assistant"') || body.includes('"role":"assistant"'),
      'SSE stream should open with an assistant role delta',
    )
    assert(
      body.includes('"finish_reason": "stop"') || body.includes('"finish_reason":"stop"'),
      'SSE stream should close the choice with finish_reason "stop"',
    )
    assert(
      body.trimEnd().endsWith('data: [DONE]'),
      'SSE stream should terminate with data: [DONE]',
    )

    const nonStream = await fetch(`${baseUrl}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'mock-model',
        messages: [{ role: 'user', content: 'Hi' }],
        stream: false,
      }),
    })
    assert(nonStream.status === 400, 'Non-streaming requests should be rejected with 400')

    console.log('Custom LLM endpoint contract check passed')
  } finally {
    llmProcess.kill()
    await llmProcess.exited

    if (llmProcess.exitCode && llmProcess.exitCode !== 0) {
      const stderr = await new Response(llmProcess.stderr).text()
      if (stderr.trim()) {
        console.error(stderr.trim())
      }
    }
  }
}

await main()
```

- [ ] **Step 2: Commit** (it is exercised after `package.json` wiring + setup in Task 11)

```bash
git add web/scripts/verify-local-llm.ts
git commit -m "test(web): add verify:local:llm SSE contract harness for the custom LLM endpoint"
```

---

## Task 8: Root `package.json` — full script suite for two backends

**Files:**
- Overwrite: `package.json`

- [ ] **Step 1: Replace `package.json` with the full suite**

```json
{
  "name": "agora-conversational-ai-recipe-custom-llm",
  "version": "1.0.0",
  "private": true,
  "workspaces": [
    "web"
  ],
  "scripts": {
    "dev": "bun run dev:check && concurrently -n llm,backend,frontend -c yellow,blue,green \"bun run dev:llm\" \"bun run dev:backend\" \"bun run dev:frontend\"",
    "dev:check": "bun run setup:env && bun run setup:deps",
    "dev:llm": "cd llm && bash -c '(venv/bin/python -m pip --version >/dev/null 2>&1 || (rm -rf venv && python3 -m venv venv)) && source venv/bin/activate && python -m pip install -q -r requirements.txt && python src/custom_llm_server.py'",
    "dev:backend": "cd server && bash -c '(venv/bin/python -m pip --version >/dev/null 2>&1 || (rm -rf venv && python3 -m venv venv)) && source venv/bin/activate && python -m pip install -q -r requirements.txt && python src/server.py'",
    "dev:frontend": "cd web && AGENT_BACKEND_URL=http://localhost:8000 bun run dev",
    "backend": "cd server && source venv/bin/activate && python src/server.py",
    "llm": "cd llm && source venv/bin/activate && python src/custom_llm_server.py",
    "frontend": "cd web && AGENT_BACKEND_URL=http://localhost:8000 bun run dev",
    "setup": "bun run setup:env && bun run setup:server && bun run setup:llm && bun run setup:web && bun run setup:done",
    "setup:env": "bash -c 'test -f server/.env.local || cp server/.env.example server/.env.local; test -f llm/.env.local || cp llm/.env.example llm/.env.local'",
    "setup:deps": "test -d node_modules || (echo 'Installing workspace dependencies...' && bun install)",
    "setup:server": "cd server && rm -rf venv && python3 -m venv venv && source venv/bin/activate && python -m pip install --upgrade pip && PIP_INDEX_URL=https://pypi.org/simple python -m pip install -r requirements.txt",
    "setup:llm": "cd llm && rm -rf venv && python3 -m venv venv && source venv/bin/activate && python -m pip install --upgrade pip && PIP_INDEX_URL=https://pypi.org/simple python -m pip install -r requirements.txt",
    "setup:web": "bun install",
    "setup:done": "printf '\\n✅ Setup complete! Next steps:\\n   1. agora project env write server/.env.local   (or fill it in manually)\\n   2. ngrok http 8001                            (expose the custom LLM endpoint)\\n   3. Add CUSTOM_LLM_URL=<tunnel-url>/chat/completions to server/.env.local\\n   4. bun run dev\\n\\n'",
    "doctor": "bash -c 'set -e; echo \"Checking shared repo prerequisites...\"; command -v bun >/dev/null && echo \"- bun available\" || { echo \"- bun not found\"; exit 1; }; test -d node_modules && echo \"- workspace dependencies installed\" || { echo \"- root node_modules missing; run bun install\"; exit 1; }'",
    "doctor:local": "bash -c 'set -e; bun run doctor; command -v python3 >/dev/null && echo \"- python3 available\" || { echo \"- python3 not found\"; exit 1; }; test -f server/.env.local && echo \"- server/.env.local present\" || { echo \"- missing server/.env.local\"; exit 1; }; test -f llm/.env.local && echo \"- llm/.env.local present\" || { echo \"- missing llm/.env.local\"; exit 1; }; grep -Eq \"^AGORA_APP_ID=.+$\" server/.env.local && echo \"- AGORA_APP_ID configured\" || { echo \"- AGORA_APP_ID missing in server/.env.local\"; exit 1; }; grep -Eq \"^AGORA_APP_CERTIFICATE=.+$\" server/.env.local && echo \"- AGORA_APP_CERTIFICATE configured\" || { echo \"- AGORA_APP_CERTIFICATE missing in server/.env.local\"; exit 1; }; grep -Eq \"^CUSTOM_LLM_URL=.+$\" server/.env.local && echo \"- CUSTOM_LLM_URL configured\" || { echo \"- CUSTOM_LLM_URL missing in server/.env.local\"; exit 1; }; if grep -Eq \"^CUSTOM_LLM_URL=.*(localhost|127[.]0[.]0[.]1)\" server/.env.local; then echo \"- WARNING: CUSTOM_LLM_URL points at localhost; Agora cloud cannot reach a local address. Use a public tunnel URL.\"; fi'",
    "build": "cd web && bun run build",
    "verify": "bun run verify:web",
    "verify:web": "bun run doctor && bun run verify:web:api && bun run verify:web:build",
    "verify:web:api": "cd web && bun run scripts/verify-api-contracts.ts",
    "verify:web:proxy": "cd web && bun run scripts/verify-local-proxy.ts",
    "verify:web:build": "cd web && bun run build",
    "verify:backend": "python3 -m py_compile server/src/server.py server/src/agent.py llm/src/custom_llm_server.py",
    "verify:local:fastapi": "cd web && bun run scripts/verify-local-fastapi.ts",
    "verify:local:llm": "cd web && bun run scripts/verify-local-llm.ts",
    "verify:local": "bun run doctor:local && bun run verify:backend && bun run verify:local:fastapi && bun run verify:local:llm && bun run verify:web:proxy && bun run verify:web:build",
    "clean": "rm -rf server/venv llm/venv server/__pycache__ server/src/__pycache__ llm/__pycache__ llm/src/__pycache__ node_modules web/node_modules web/.next web/dist"
  },
  "devDependencies": {
    "concurrently": "^8.2.2"
  }
}
```

- [ ] **Step 2: Validate the JSON parses**

Run: `node -e "JSON.parse(require('fs').readFileSync('package.json','utf8')); console.log('package.json OK')"`
Expected: `package.json OK`.

- [ ] **Step 3: Commit**

```bash
git add package.json
git commit -m "feat: orchestrate two backends with full setup/doctor/verify script suite"
```

---

## Task 9: Root `.gitignore` — stop ignoring `bun.lock`

**Files:**
- Modify: `.gitignore`

The web resync brings a committed `web/bun.lock` (the reference commits it). The current root `.gitignore` ignores `bun.lock`, which would prevent committing it.

- [ ] **Step 1: Remove the `bun.lock` ignore line**

In `.gitignore`, change:

```
# Dependencies
node_modules
bun.lock
```

to:

```
# Dependencies
node_modules
```

- [ ] **Step 2: Stage the previously-ignored lockfile and commit**

```bash
git add .gitignore web/bun.lock
git commit -m "chore: track bun.lock to match base quickstart"
```
Expected: `web/bun.lock` is now staged (it was added in Task 6 but ignored until now).

---

## Task 10: Root docs — README, ARCHITECTURE, AGENTS, CLAUDE

**Files:**
- Overwrite: `README.md`, `ARCHITECTURE.md`, `AGENTS.md`
- Create: `CLAUDE.md`

`docs/ai/` is intentionally NOT created (deferred per the spec). None of these docs may link to `docs/ai/` paths.

- [ ] **Step 1: Overwrite `README.md`**

````markdown
# Agora Conversational AI — Custom LLM Recipe (Python)

The **custom-llm** recipe in the Agora Conversational AI recipes family. Bring your
own LLM to Agora's voice pipeline: the agent's LLM stage is pointed at your own
OpenAI-compatible `POST /chat/completions` endpoint instead of a managed model.
STT (Deepgram) and TTS (MiniMax) stay Agora-managed.

This repo ships a **zero-key mock** LLM endpoint so you can run the full
STT → custom LLM → TTS pipeline immediately, then replace the mock with your own
model.

## Prerequisites

- [Python 3.8+](https://www.python.org/)
- [Bun](https://bun.sh/)
- [ngrok](https://ngrok.com/) (or any tunnel to expose localhost)
- Agora App ID + App Certificate (the [Agora CLI](https://github.com/AgoraIO/cli) makes this easy)

## Run it

```bash
# 1. Install + create both Python venvs
bun run setup

# 2. Add Agora credentials (CLI), or edit server/.env.local by hand
agora login
agora project env write server/.env.local

# 3. Expose the custom LLM endpoint publicly (Agora cloud calls it directly)
ngrok http 8001

# 4. Add the tunnel URL to server/.env.local
#    CUSTOM_LLM_URL=https://<your-tunnel>.ngrok-free.app/chat/completions

# 5. Run all three services
bun run dev
```

Open [http://localhost:3000](http://localhost:3000) → **Start Conversation** → speak.

## Architecture

```
Browser (localhost:3000)
  │  fetch /api/*
  ▼
Next.js  ──rewrite──▶  Agent backend  (server/, localhost:8000)
                          │  starts agent session (CustomLLM vendor)
                          ▼
                       Agora ConvoAI Cloud
                          │  POST <CUSTOM_LLM_URL>   (Authorization: Bearer)
                          ▼
                       Custom LLM endpoint  (llm/, localhost:8001)
                          ▲  public via ngrok tunnel
```

The browser only ever calls Next `/api/*`, which rewrites to the agent backend.
The agent backend owns Agora tokens and agent lifecycle. The **custom LLM
endpoint** is separate because Agora cloud — not the browser — calls it, so it
must be publicly reachable. See [ARCHITECTURE.md](./ARCHITECTURE.md).

## Project structure

```
agent-recipes-python/
├── server/   # Agent backend (:8000) — tokens + agent lifecycle, CustomLLM vendor
│   ├── src/{server.py, agent.py}
│   └── scripts/run_fake_server.py
├── llm/      # Custom LLM endpoint (:8001) — OpenAI-compatible mock, no agora deps
│   └── src/custom_llm_server.py
├── web/      # Shared Next.js frontend (:3000)
└── package.json
```

## Environment variables

Backend env file: [`server/.env.example`](server/.env.example).

| Variable | Required | Default | Notes |
| --- | :---: | :---: | --- |
| `AGORA_APP_ID` | ✅ | — | Agora Console → Project → App ID |
| `AGORA_APP_CERTIFICATE` | ✅ | — | Agora Console → Project → App Certificate (server only) |
| `CUSTOM_LLM_URL` | ✅ | — | **Public** chat-completions URL of your `llm/` endpoint. Agora cloud calls it; cannot be `localhost`. |
| `CUSTOM_LLM_API_KEY` | ✅ | `any-key-here` | Forwarded by Agora cloud as `Authorization: Bearer`. Required by the `CustomLLM` vendor. |
| `CUSTOM_LLM_MODEL` |  | `mock-model` | Model name passed to your endpoint |
| `AGENT_GREETING` |  | built-in | Optional opening line override |
| `PORT` |  | `8000` | Agent backend port |
| `CUSTOM_LLM_PORT` (llm) |  | `8001` | Port for the custom LLM endpoint |
| `AGENT_BACKEND_URL` (web deploy) | ✅ | — | Required in a deployed `web` app when proxying to the backend |

## Commands

```bash
bun run setup            # install web deps + create server/ and llm/ venvs
bun run dev              # run llm (:8001) + backend (:8000) + web (:3000)

bun run doctor           # prerequisite check (no creds needed)
bun run doctor:local     # + .env.local + credentials + CUSTOM_LLM_URL checks

bun run verify           # web-only gate (no Agora creds needed)
bun run verify:local     # full local gate: backend compile + smoke tests + web build
bun run clean            # remove venvs and build artifacts
```

## Replacing the mock

Edit `get_mock_response()` in [`llm/src/custom_llm_server.py`](llm/src/custom_llm_server.py).
The endpoint must keep speaking the OpenAI streaming `/chat/completions` contract
(see [`llm/README.md`](llm/README.md)). A production endpoint should also validate
the `Authorization: Bearer` header.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Agent starts but never speaks | `CUSTOM_LLM_URL` is not public or omits `/chat/completions`. Use your ngrok URL. |
| `doctor:local` warns about localhost | Replace the local URL with your public tunnel URL. |
| Proxy errors on stopAgent | `unset http_proxy https_proxy` before `bun run dev`. |
| `Missing llm/venv` during verify | Run `bun run setup` (creates both venvs). |

## License

MIT
````

- [ ] **Step 2: Overwrite `ARCHITECTURE.md`**

```markdown
# Architecture — Custom LLM Recipe

Three processes. The browser talks only to Next.js `/api/*`, which rewrites to the
agent backend. The agent backend owns Agora tokens and agent lifecycle. The custom
LLM endpoint is a separate service that **Agora cloud** calls directly.

## Request flow

```
Browser
  │  GET /api/get_config            → token + channel/UIDs
  │  POST /api/startAgent           → start agent session
  ▼
Next.js  (rewrites /api/* → AGENT_BACKEND_URL)
  ▼
Agent backend (server/, :8000)
  │  builds session with CustomLLM(base_url=CUSTOM_LLM_URL)
  ▼
Agora ConvoAI Cloud
  │  user speech → Deepgram STT (managed)
  │  POST <CUSTOM_LLM_URL>/chat/completions   (Authorization: Bearer <key>)
  ▼
Custom LLM endpoint (llm/, :8001, public via tunnel)
  │  returns OpenAI SSE
  ▼
Agora ConvoAI Cloud → MiniMax TTS (managed) → user hears speech
                     → RTM transcript / metrics → web UI
```

`POST /api/stopAgent { agentId }` ends the session.

## Why two backends

`server/` and `llm/` are split because of an **exposure asymmetry**:

- `llm/` must be reachable by **Agora cloud over the public internet** (hence the
  ngrok tunnel). It is the part you replace with your own model, and it has no
  Agora dependency.
- `server/` only needs to be reachable by your web tier. It holds the Agora App
  Certificate and all token logic.

In production the two could be co-deployed, but they are kept separate here to
make that boundary — and the public-exposure requirement — explicit.

## API (agent backend, port 8000)

| Endpoint | Method | Description |
| --- | --- | --- |
| `/get_config` | GET | Token + channel/UID config |
| `/startAgent` | POST | Start the agent session |
| `/stopAgent` | POST | Stop the agent by `agent_id` |

The browser calls these as `/api/*`; Next rewrites them to `AGENT_BACKEND_URL`.

## Auth

- Browser → agent backend: none (local dev).
- Agent backend → Agora cloud: Token007, generated from `AGORA_APP_ID` +
  `AGORA_APP_CERTIFICATE`.
- Agora cloud → custom LLM endpoint: `Authorization: Bearer <CUSTOM_LLM_API_KEY>`.
  The mock endpoint does not validate it; a production endpoint should.
```

- [ ] **Step 3: Overwrite `AGENTS.md`**

```markdown
# Agent Development Guide

For coding agents working in `agent-recipes-python`. This repository is the
**custom-llm** recipe (`Recipe Role: custom-llm`) in the Agora Conversational AI
recipes family, derived from the base `agent-quickstart-python` template.

## System shape

- **`server/`** — Python FastAPI agent backend (:8000). Owns Agora token
  generation and agent session lifecycle. Uses the `CustomLLM` vendor to point the
  agent's LLM stage at the custom LLM endpoint. SDK: `agora-agents>=2.0.0`
  (`import agora_agent`).
- **`llm/`** — Python FastAPI custom LLM endpoint (:8001). OpenAI-compatible
  `POST /chat/completions` mock that Agora cloud calls. No `agora-agents`
  dependency. This is the component a developer replaces.
- **`web/`** — Next.js 16 / React 19 / TypeScript frontend (:3000), resynced from
  the base quickstart with custom-LLM branding only.
- Auth: Token007 from `AGORA_APP_ID` + `AGORA_APP_CERTIFICATE`.

## Routing / ownership

- UI and RTC/RTM lifecycle live in `web/`.
- Browser-facing `/api/*` paths are Next rewrites (`web/next.config.ts`) to the
  agent backend; do not add `web/app/api/**/route.ts` for agent/token logic.
- Token generation and agent lifecycle live in `server/src/`.
- The OpenAI `/chat/completions` contract lives in `llm/src/`.

## Supported modes

- **Local:** `bun run dev` starts `llm` (:8001), `server` (:8000), and `web`
  (:3000). The web app calls `/api/*`; Next rewrites to
  `AGENT_BACKEND_URL=http://localhost:8000`. The custom LLM endpoint must be
  exposed publicly (ngrok) so Agora cloud can reach it.
- **Deploy:** deploy `web` (Next) + `server` (reachable FastAPI) + `llm` (publicly
  reachable FastAPI). Set `AGENT_BACKEND_URL` in the web deployment.

## Patterns

- Keep the web client calling `/api/*`; hide backend placement behind Next rewrites.
- Keep token generation and the App Certificate in `server/`.
- Keep the `llm/` endpoint free of `agora-agents` — it is provider-agnostic.
- `CUSTOM_LLM_URL` is required and must be public; there is no localhost default.
- Both `CUSTOM_LLM_URL` and `CUSTOM_LLM_API_KEY` are required by the `CustomLLM`
  vendor (the SDK rejects one without the other).

## Anti-patterns

- Do not reintroduce Next Route Handlers for agent/token logic.
- Do not add `agora-agents` to `llm/`.
- Do not default `CUSTOM_LLM_URL` to localhost.
- Do not put `PORT` in `server/.env.example` (it would clobber the random port
  that `verify:local:fastapi` injects via `load_dotenv(override=True)`).
- Do not link to `docs/ai/` — that progressive-disclosure tree is not present yet.

## Commands

```bash
bun run setup
bun run dev
bun run doctor
bun run doctor:local
bun run verify         # web-only, no creds
bun run verify:local   # full local gate
```

Narrower checks: `bun run verify:backend`, `bun run verify:local:fastapi`,
`bun run verify:local:llm`, `bun run verify:web:proxy`.

## Done criteria

1. Run the narrowest relevant verification command.
2. Web-affecting changes: `bun run verify:web` passes.
3. Backend-affecting changes: `bun run verify:local` (or the narrower
   `verify:local:fastapi` / `verify:local:llm` / `verify:backend`) passes.
4. If you change required env vars or setup steps, update the root README, the
   relevant module README, and `server/.env.example` / `llm/.env.example` together.

## Git conventions

- Conventional Commits: `type: description` or `type(scope): description`
  (`feat`, `fix`, `chore`, `test`, `docs`). Lowercase after the prefix, present
  tense.
- No AI tool names in commit messages or PR descriptions. No `Co-Authored-By`
  trailers. No `--no-verify`. No git config changes.
- Branch names: `type/short-description` (e.g. `feat/custom-llm-tools`).
```

- [ ] **Step 4: Create `CLAUDE.md`**

```markdown
This project uses AGENTS.md instead of a CLAUDE.md file.

Please see @AGENTS.md in this same directory and treat its content as the primary reference for this project.
```

- [ ] **Step 5: Confirm no doc links point at the absent `docs/ai/` tree**

Run: `grep -rn "docs/ai" README.md ARCHITECTURE.md AGENTS.md CLAUDE.md`
Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git add README.md ARCHITECTURE.md AGENTS.md CLAUDE.md
git commit -m "docs: rewrite root docs for single custom-llm recipe"
```

---

## Task 11: Full setup + verification gate

**Files:** none (runs the suite). Fix any failures in the relevant file before committing.

- [ ] **Step 1: Install everything**

Run: `bun run setup`
Expected: web deps install; `server/venv` and `llm/venv` are created and dependencies install; the "Setup complete" next-steps message prints. If `agora-agents` fails to resolve, confirm network access to PyPI.

- [ ] **Step 2: Provide local credentials for the local gate**

`doctor:local` and the smoke tests need `server/.env.local` and `llm/.env.local`. `setup` created them from the examples. For a credential-free machine, set placeholder values so `doctor:local` passes (the smoke tests use a fake agent / the keyless mock and do not place real Agora calls):

```bash
# Only if real creds are not available on this machine:
printf 'AGORA_APP_ID=placeholder_app_id\nAGORA_APP_CERTIFICATE=placeholder_cert\nCUSTOM_LLM_URL=https://example.ngrok-free.app/chat/completions\nCUSTOM_LLM_API_KEY=any-key-here\nCUSTOM_LLM_MODEL=mock-model\n' > server/.env.local
```
(With real Agora credentials, use `agora project env write server/.env.local` and add the `CUSTOM_LLM_*` lines.)

- [ ] **Step 3: Backend compile check**

Run: `bun run verify:backend`
Expected: exit code 0, no output (all three Python files compile under the 2.0.0 import paths).

- [ ] **Step 4: Custom LLM contract check**

Run: `bun run verify:local:llm`
Expected: `Custom LLM endpoint contract check passed`.

- [ ] **Step 5: FastAPI route smoke check (fake agent through Next proxy)**

Run: `bun run verify:local:fastapi`
Expected: `Local FastAPI app proxy smoke check passed`.

- [ ] **Step 6: Web API-contract + proxy checks**

Run: `bun run verify:web:api && bun run verify:web:proxy`
Expected: both scripts print their pass messages with no assertion errors.

- [ ] **Step 7: Full local gate**

Run: `bun run verify:local`
Expected: `doctor:local` prints all checks (with a localhost warning only if your `CUSTOM_LLM_URL` is local), then backend compile, both smoke checks, web proxy, and `bun run build` all succeed. The final web build completes without errors.

> Sandbox note: `bun run build` and the smoke scripts bind local ports and spawn processes; if a restricted sandbox blocks them, run this task on a host that allows local port binding.

- [ ] **Step 8: Commit any fixes**

If steps 3–7 required changes, commit them with an appropriate `fix:`/`chore:` message. If nothing changed, skip.

```bash
git add -A
git commit -m "chore: pass full local verification gate" || echo "nothing to commit"
```

---

## Task 12: Merge to `main`

**Files:** none (git only)

- [ ] **Step 1: Final status review**

Run: `git status --short && git log --oneline origin/main..HEAD`
Expected: clean tree; the feature commits from Tasks 0–11 listed.

- [ ] **Step 2: Merge the feature branch into `main`**

```bash
git checkout main
git merge --no-ff feat/custom-llm-refactor -m "feat: refactor to single custom-llm recipe aligned with quickstart"
```
Expected: merge succeeds. The backup branch on `origin` still preserves the pre-refactor multi-recipe state.

- [ ] **Step 3: Push `main`**

```bash
git push origin main
```
Expected: `main` updated on `origin`. (Confirm with the user before pushing if they want to review first.)

---

## Self-Review notes (for the implementer)

- The "tests" for this refactor are the `verify:*` scripts and `py_compile`; there are no new unit-test files. The new genuine logic — the `CustomLLM` wiring, the required-URL validation, and the SSE contract — is covered by `verify:backend`, `verify:local:fastapi`, and `verify:local:llm` respectively.
- If `rsync` is unavailable, substitute `cp -R $REF/web/. web/` and then delete `web/node_modules` / `web/.next` before committing.
- Do not create `docs/ai/`; it is deferred. `CONTEXT.md` already exists at the repo root from the design phase and needs no change.
```