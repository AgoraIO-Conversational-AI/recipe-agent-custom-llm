# Custom LLM Refactor — Design

**Date:** 2026-06-10
**Status:** Approved
**Reference template:** `/Users/zhangqianze/Documents/agent-quickstart-python` (`agent-quickstart-python`, Recipe Role: `base`)

## Goal

Refactor `agent-recipes-python` from a multi-recipe collection into a single **custom-llm** recipe, structurally and tonally aligned with the `agent-quickstart-python` base template. Remove the `audio-modalities` recipe. Adopt the reference's production scaffolding in full (verify/doctor scripts, fake-server route tests, progressive-disclosure `docs/ai/` tree, reference-style root docs).

## Non-Goals

- No change to the runtime behavior of the custom-LLM voice pipeline (STT → custom LLM → TTS).
- No new LLM provider integrations; the `llm/` endpoint stays a zero-key mock with swap-the-mock guidance.
- No redesign of the web UI's conversation experience; web changes are a resync to the reference plus minimal branding.

## Decisions (locked)

1. **Layout:** two backend dirs — `server/` (agent backend, mirrors reference exactly) + `llm/` (public OpenAI-compatible endpoint) — plus the shared `web/`.
2. **Scaffolding:** full alignment — verify/doctor script suite, `run_fake_server.py`, the `docs/ai/` L0/L1/L2 + `RECIPE.md` tree, and a reference-style `AGENTS.md`.
3. **Setup flow:** Agora CLI for credentials (`agora project env write server/.env.local`) + one documented manual step to paste the ngrok tunnel URL as `CUSTOM_LLM_URL`.
4. **Agent persona:** keep the existing custom-LLM-themed prompt (not the reference's "Ada" persona).
5. **Web resync:** full resync — baseline is reference `web/`; re-apply only the minimal custom-LLM text deltas.

## Git Plan

1. From current `main`, create `backup/main-multi-recipe` (preserves the `audio-modalities` recipe and the current structure).
2. Do the refactor on `feat/custom-llm-refactor`.
3. Merge to `main` once `bun run verify:local` passes.

## Target Directory Layout

```
agent-recipes-python/
├── server/                     # Agent backend :8000 — mirrors reference server/ exactly
│   ├── src/
│   │   ├── __init__.py
│   │   ├── server.py           # FastAPI: GET /get_config, POST /startAgent, POST /stopAgent
│   │   └── agent.py            # Agent class — OpenAI(base_url=CUSTOM_LLM_URL) custom path
│   ├── scripts/
│   │   └── run_fake_server.py  # FakeAgent swap for route smoke tests
│   ├── .env.example
│   ├── requirements.txt
│   └── README.md
├── llm/                        # Public OpenAI-compatible endpoint :8001 — the recipe's feature
│   ├── src/
│   │   ├── __init__.py
│   │   └── custom_llm_server.py # Mock POST /chat/completions (OpenAI SSE)
│   ├── .env.example
│   ├── requirements.txt        # fastapi, uvicorn, python-dotenv (NO agora-agents)
│   └── README.md
├── web/                        # Shared Next.js frontend (resynced to reference web/)
│   └── scripts/                # verify harnesses (incl. new verify-local-llm.ts)
├── docs/ai/                    # Progressive disclosure: L0_repo_card, RECIPE, L1/01–08, L1/L2
├── package.json                # Full script suite
├── README.md
├── ARCHITECTURE.md
├── AGENTS.md
├── CLAUDE.md                   # Pointer to AGENTS.md
└── LICENSE
```

`audio-modalities/` is deleted. `custom-llm/` is replaced by `server/` + `llm/`.

## Component Designs

### `server/` — agent backend (mirrors reference, one deviation)

- **`agent.py`** — copy of reference `server/src/agent.py` with the single intentional difference being the LLM vendor:
  ```python
  llm = OpenAI(
      base_url=self.custom_llm_url,        # CUSTOM_LLM_URL (public tunnel) → llm/ endpoint
      api_key=self.custom_llm_api_key,     # CUSTOM_LLM_API_KEY
      model=self.custom_llm_model,         # CUSTOM_LLM_MODEL
      greeting_message=self.greeting,
      failure_message="Please wait a moment.",
      max_history=15, max_tokens=1024, temperature=0.7, top_p=0.95,
  )
  ```
  STT (`DeepgramSTT nova-3`) and TTS (`MiniMaxTTS speech_2_6_turbo`) stay managed, matching the reference. The "KEY DIFFERENCE" comment block is retained and sharpened. Keep the existing custom-LLM prompt (`CUSTOM_LLM_PROMPT`). Constructor reads `CUSTOM_LLM_URL`, `CUSTOM_LLM_API_KEY`, `CUSTOM_LLM_MODEL`, `AGENT_GREETING`, plus `AGORA_APP_ID`/`AGORA_APP_CERTIFICATE`.
- **`server.py`** — aligned to reference `server/src/server.py`, including the token call signature fix: use `generate_convo_ai_token(app_id=..., app_certificate=..., channel_name=..., uid=user_uid, token_expire=3600)` (reference form) instead of the current `account=str(user_uid)`. Channel prefix `custom-llm-`. Title "Agora Custom LLM Recipe Service".
- **`scripts/run_fake_server.py`** — identical `FakeAgent` pattern from the reference (swaps `server.agent` for a fake so route wiring is testable without a live agent).
- **`.env.example`**:
  ```
  AGORA_APP_ID=your_agora_app_id
  AGORA_APP_CERTIFICATE=your_agora_app_certificate
  AGENT_GREETING=Hi there! I'm your AI assistant powered by a custom LLM. How can I help?
  CUSTOM_LLM_URL=https://your-tunnel.ngrok-free.app/chat/completions
  CUSTOM_LLM_API_KEY=any-key-here
  CUSTOM_LLM_MODEL=mock-model
  PORT=8000
  ```
- **`requirements.txt`** — same as reference: `fastapi`, `uvicorn`, `requests`, `python-dotenv`, `agora-agents>=2.0.0`, `socksio`.
- **`README.md`** — reference-style module README adapted: notes the custom LLM vendor path, the required public `CUSTOM_LLM_URL`, and that `llm/` must be running and tunneled.

### `llm/` — custom LLM endpoint (the feature)

- **`src/custom_llm_server.py`** — the existing mock from `custom-llm/src/custom_llm_server.py`, moved unchanged in behavior. Implements `POST /chat/completions` returning OpenAI SSE chunks (role chunk → content chunks → `finish_reason:"stop"` → `data: [DONE]`), plus `GET /health`. Swap-the-mock guidance (Ollama, vLLM, RAG, model routing) retained in the module docstring and README.
- **No `agora-agents` dependency** — `requirements.txt` is `fastapi`, `uvicorn`, `python-dotenv` only. This boundary makes "the part you replace" explicit.
- **`.env.example`**:
  ```
  CUSTOM_LLM_PORT=8001
  CUSTOM_LLM_API_KEY=any-key-here
  ```
- **`README.md`** — recipe-specific: the OpenAI SSE contract, how to expose it via ngrok, and how to replace the mock with a real model.

### `web/` — full resync to reference

Baseline becomes reference `web/`. Files to **add** (currently missing): `scripts/{doctor,verify-api-contracts,verify-local-fastapi,verify-local-proxy}.ts`, `docs/*`, `.claude/*`, `next-env.d.ts`, `bun.lock`, `share-button.tsx`, and `public/` favicons + Agora logo + share card.

Then **re-apply the minimal custom-LLM branding deltas** on top of the reference versions:

| File | Delta |
| --- | --- |
| `app/layout.tsx` | `title: "Custom LLM Recipe | Agora Conversational AI"`; custom-LLM description. Keep the reference `icons` block (favicon assets now present). |
| `src/components/QuickstartPreCallCard.tsx` | Heading "Custom LLM Recipe"; description about bringing your own OpenAI-compatible LLM. |
| `src/components/QuickstartPipelineMetrics.tsx` | LLM label "Custom LLM" (vs "OpenAI LLM"). |

Everything else (`LandingPage.tsx` with ShareButton + Agora footer, `next.config.ts` strict mode + image optimization, `package.json`, `tsconfig.json`, `.gitignore`) takes the reference version. A new `scripts/verify-local-llm.ts` is added (see below).

### `package.json` — full script suite (two backends)

```
setup                  setup:env + setup:server + setup:llm + setup:web + setup:done
setup:env              ensure server/.env.local and llm/.env.local exist (cp from .env.example)
setup:server           recreate server/venv, pip install -r server/requirements.txt
setup:llm              recreate llm/venv, pip install -r llm/requirements.txt
setup:web              bun install
dev                    dev:check + concurrently  llm(:8001) + backend(:8000) + frontend(:3000)
dev:check              setup:env + setup:deps (web node_modules present)
dev:llm                cd llm && venv python src/custom_llm_server.py
dev:backend            cd server && venv python src/server.py
dev:frontend           cd web && AGENT_BACKEND_URL=http://localhost:8000 bun run dev
doctor                 bun + workspace deps present
doctor:local           doctor + python3 + both .env.local + AGORA creds + CUSTOM_LLM_URL present
build                  cd web && bun run build
verify                 verify:web
verify:web             doctor + verify:web:api + verify:web:build
verify:web:api         cd web && bun run scripts/verify-api-contracts.ts
verify:web:proxy       cd web && bun run scripts/verify-local-proxy.ts
verify:web:build       cd web && bun run build
verify:backend         py_compile server/src/{server,agent}.py + llm/src/custom_llm_server.py
verify:local:fastapi   cd web && bun run scripts/verify-local-fastapi.ts   (server routes via fake agent)
verify:local:llm       cd web && bun run scripts/verify-local-llm.ts       (boot mock llm, assert SSE)
verify:local           doctor:local + verify:backend + verify:local:fastapi + verify:local:llm + verify:web:proxy + verify:web:build
clean                  rm -rf server/venv llm/venv node_modules web/node_modules web/.next __pycache__
```

`verify:local:llm` follows the exact shape of reference `verify-local-fastapi.ts`: Bun spawns `llm/venv/bin/python src/custom_llm_server.py` on a random port, POSTs a streaming `/chat/completions` request, and asserts the SSE stream contains a role chunk, at least one content delta, a `finish_reason:"stop"` chunk, and a terminal `data: [DONE]`. Because the mock needs no keys, this is a real contract check.

### `docs/ai/` — progressive-disclosure tree

Mirror the reference structure, retargeted to the custom-LLM recipe:

- **`L0_repo_card.md`** — identity table with `Recipe Role: custom-llm`, `Recipe Version: 1.0.0`, `Recipe Status: experimental`, `Last Reviewed: 2026-06-10`; L1 summary table.
- **`RECIPE.md`** — frontmatter + body:
  - **Extension points:** `llm.endpoint` (the `/chat/completions` server you replace), `agent.custom-llm-config` (`server/src/agent.py` vendor/prompt/VAD), `web.conversation-ui`, `verification.contracts`.
  - **Invariants:** `llm` must be publicly reachable for Agora cloud to call it; the endpoint must speak the OpenAI streaming `/chat/completions` contract; secrets (`AGORA_APP_CERTIFICATE`) stay server-only; browser stays on `/api/*`.
  - **Stable contracts:** required env (`AGORA_APP_ID`, `AGORA_APP_CERTIFICATE`, `CUSTOM_LLM_URL`), core `/api/*` routes, `{code,msg,data}` envelope, the SSE chunk shape.
- **`L1/01_setup.md`** — bun + two venvs + pip, env vars (incl. `CUSTOM_LLM_URL`), ngrok step, doctor, all scripts.
- **`L1/02_architecture.md`** — three-process topology (web :3000 → FastAPI :8000 → Agora cloud → public `llm` :8001 via tunnel), `/api/*` rewrite proxy, request lifecycle including the cloud→llm call.
- **`L1/03_code_map.md`** — `web/`, `server/`, and `llm/` trees with key-file responsibilities.
- **`L1/04_conventions.md`** — Python async + FastAPI patterns, OpenAI SSE conventions, Biome, JSON contract.
- **`L1/05_workflows.md`** — replace the mock with a real LLM, change agent config, verify, deploy each part.
- **`L1/06_interfaces.md`** — FastAPI route contracts, the `/chat/completions` request/response contract, rewrites, env vars.
- **`L1/07_gotchas.md`** — `CUSTOM_LLM_URL` must be public + include `/chat/completions`; ngrok must be running; `unset http_proxy https_proxy` for stopAgent; `AGENT_BACKEND_URL` dependency.
- **`L1/08_security.md`** — `Authorization: Bearer` from Agora cloud to `llm`, server-only certs, CORS default, token expiry.
- **`L1/L2/`** — adapt `from_scratch_bootstrap.md`, add `custom_llm_endpoint.md` (deep dive on the SSE contract and swap-the-mock), keep `session_lifecycle.md`. `_index.md` lists them.

### Root docs (reference depth/tone, single recipe)

- **`README.md`** — drop the recipe index table. CLI + manual-tunnel onboarding (the 6-step flow), env table including `CUSTOM_LLM_URL`/`CUSTOM_LLM_API_KEY`/`CUSTOM_LLM_MODEL`, commands, architecture picture, deploy guidance, troubleshooting, progressive-disclosure pointers.
- **`ARCHITECTURE.md`** — the three-process flow with the public `llm` endpoint Agora cloud calls; request lifecycle; auth (Token007 backend; Bearer cloud→llm).
- **`AGENTS.md`** — reference-style: progressive-disclosure loader (`Recipe Role: custom-llm`), current system shape, supported modes, routing/ownership (web `/api/*`, server lifecycle, `llm` endpoint), patterns, anti-patterns, done criteria, git conventions, doc commands.
- **`CLAUDE.md`** — short pointer to `AGENTS.md`.

## Request Flow (target)

```
1. Browser  GET /api/get_config            → Next rewrite → FastAPI :8000 → Token007 + channel/UIDs
2. Browser  POST /api/startAgent           → FastAPI builds session: OpenAI(base_url=CUSTOM_LLM_URL)
3. Conversation:
     user audio → Agora cloud STT
       → Agora cloud POST CUSTOM_LLM_URL/chat/completions  (Bearer api_key)  → llm :8001 returns SSE
       → Agora cloud MiniMax TTS → user hears speech
       → RTM transcript/metrics → web UI
4. Browser  POST /api/stopAgent            → FastAPI stops session
```

## Error Handling

- `server/src/server.py` keeps the reference's `_log_route_error` + `_to_http_error` mapping (`ValueError → 400`, `RuntimeError → 500`, else 500) and the `{code,msg,data}` envelope.
- `llm/src/custom_llm_server.py` rejects non-streaming requests with 400 and returns SSE for streaming requests.

## Testing / Verification

- `bun run verify:backend` — `py_compile` over `server/src` and `llm/src`.
- `bun run verify:local:fastapi` — server routes through the Next proxy with a fake agent (no live Agora).
- `bun run verify:local:llm` — boots the real mock `llm` server and asserts the SSE contract (no keys needed).
- `bun run verify:web` / `verify:web:api` / `verify:web:proxy` / `verify:web:build` — web contract + build checks.
- `bun run verify:local` — the full local gate (`doctor:local` + backend compile + both smoke checks + web proxy + web build).

Definition of done: `bun run verify:local` passes, and the root README onboarding flow is internally consistent with `package.json` scripts and `.env.example` files.

## Risks / Open Considerations

- The reference `verify-local-fastapi.ts` resolves `serverRoot = ../server` from `web/`. With the `server/` dir preserved, this path stays valid. `verify-local-llm.ts` resolves `../llm` analogously.
- `socksio` is included in `server/requirements.txt` to allow SOCKS proxy routing (`all_proxy`), matching the reference and the existing `unset http_proxy` gotcha.
- A full `web/` resync overwrites the recipe's current trimmed-down web files; the three branding deltas above are the only intentional divergences to preserve.
```