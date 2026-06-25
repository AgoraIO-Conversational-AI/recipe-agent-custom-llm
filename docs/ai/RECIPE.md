---
recipe_version: 1.0.0
recipe_status: experimental
extension_points:
  - id: llm.endpoint
    name: Custom LLM endpoint implementation (get_mock_response / full llm.py replacement)
  - id: llm.vendor-config
    name: CustomLLM model, max_history, max_tokens, temperature, top_p, greeting, and failure_message
  - id: stt-tts.vendors
    name: STT and TTS vendor selection and configuration (DeepgramSTT, MiniMaxTTS)
  - id: agent.vad-config
    name: VAD turn detection on AgoraAgent (speech_threshold, interrupt_duration_ms, silence_duration_ms)
  - id: api.routes
    name: Browser-facing API routes
  - id: web.conversation-ui
    name: Conversation UI panels and controls
  - id: verification.contracts
    name: Contract, proxy, fastapi, and LLM smoke verification
invariants:
  - id: api.rewrite-boundary
    summary: Browser calls stay on /api/* and Next rewrites to FastAPI; no Route Handlers for agent/token logic.
  - id: secrets.server-only
    summary: Agora App Certificate and CUSTOM_LLM_API_KEY stay in the Python backend; never reach the browser.
  - id: llm.agora-free
    summary: server/src/llm.py must not import any agora_* package — it is the provider-agnostic replacement target.
  - id: llm.streaming-only
    summary: POST /chat/completions must return streaming SSE; stream=false must be rejected with 400.
  - id: llm.public-url
    summary: CUSTOM_LLM_URL must be a public URL; Agora cloud calls it directly. No localhost default.
  - id: vad.agent-owned
    summary: turn_detection is set on AgoraAgent(...), not on the CustomLLM vendor.
  - id: token.uid-concrete
    summary: Backend resolves missing, zero, or negative UIDs before issuing an RTC+RTM token.
stable_contracts:
  - id: env.required
    summary: AGORA_APP_ID, AGORA_APP_CERTIFICATE, CUSTOM_LLM_URL, and CUSTOM_LLM_API_KEY are required; AGENT_BACKEND_URL is required by deployed web rewrites.
  - id: api.core-routes
    summary: GET /api/get_config, POST /api/startAgent, and POST /api/stopAgent remain the browser-facing contract.
  - id: llm.sse-contract
    summary: POST /llm/chat/completions returns streaming SSE in OpenAI chunk format, terminated with data:[DONE].
  - id: response.envelope
    summary: Successful backend responses use { code, msg, data }.
---

# Recipe Contract

This base recipe defines the reusable surface for a Python-backed Agora Conversational AI **custom-llm** quickstart: a cascading STT/LLM/TTS pipeline where the LLM stage is your own OpenAI-compatible endpoint, behind a Next.js web client.

## Recipe Role

- Role: `base` recipe (self-contained, clone-and-run; no `Extends` pin).
- Target audience: developers who want to bring their own LLM (local model, remote provider, RAG, tool calling) to Agora's managed voice pipeline.
- Reuse model: clone, bind project, expose backend publicly (ngrok or deploy), set `CUSTOM_LLM_URL` + `CUSTOM_LLM_API_KEY`, run with the zero-key mock, then replace `get_mock_response()` or the whole `llm.py` with your model.

## Recipe Scope

- Python FastAPI token generation and managed agent lifecycle.
- `CustomLLM` vendor pointing the LLM stage at a bring-your-own OpenAI-compatible endpoint.
- Zero-key mock LLM endpoint (`server/src/llm.py`) mounted at `/llm` — runs without any model API key.
- `DeepgramSTT` and `MiniMaxTTS` as the managed STT and TTS stages.
- Public tunnel requirement (ngrok or equivalent) for local development.
- Next.js browser UI with RTC audio, RTM transcript/metrics, connection status.
- Rewrite-only `/api/*` browser facade hiding backend placement.
- Contract, proxy, FastAPI, and LLM smoke verification that need no live Agora calls.

## Baseline Implementation Guidance

Use this repo's source and progressive disclosure docs as the starting point, then customize. Do not recreate the Agora ConvoAI integration from memory — vendor schemas, SDK builder fields, token behavior, and RTM details drift. Copy verified patterns from this repo.

## Extension Points

| ID | Surface | How to extend | Required follow-up |
| -- | ------- | ------------- | ------------------ |
| `llm.endpoint` | `server/src/llm.py` | Replace `get_mock_response()` with real model call, or rewrite the whole file preserving the SSE contract. | Run `pytest tests/test_llm.py tests/test_llm_mount.py` + `bun run verify:local:llm`. Keep `agora_*` imports out of `llm.py`. |
| `llm.vendor-config` | `server/src/agent.py` | Change `CustomLLM(...)` params: model, max_tokens, temperature, greeting, etc. | Run `bun run verify:backend` + `pytest tests -v`. |
| `stt-tts.vendors` | `server/src/agent.py` | Import and instantiate a different STT/TTS vendor; swap in `.with_stt()` / `.with_tts()`. | Add new env vars to `server/.env.example`. Run `bun run verify:backend`. |
| `agent.vad-config` | `server/src/agent.py` | Edit `turn_detection` dict on `AgoraAgent(...)`. | Run `bun run verify:local:fastapi`. |
| `api.routes` | `server/src/server.py`, `web/next.config.ts`, `web/src/services/api.ts` | Add FastAPI route, add rewrite, add browser fetch helper. | Extend `web/scripts/verify-api-contracts.ts`. |
| `web.conversation-ui` | `web/src/components/*`, `web/src/lib/conversation.ts` | Customize pre-call, transcript, metrics, connection status, mic, or visualizer UI. | Preserve RTC/RTM lifecycle ownership and transcript UID normalization. |
| `verification.contracts` | `web/scripts/*.ts`, root `package.json` | Add checks for new browser/backend boundaries. | Keep checks runnable without live Agora credentials. |

## Invariants

- Browser code calls only `/api/get_config`, `/api/startAgent`, and `/api/stopAgent` for the default flow.
- Next.js owns `/api/*` through rewrites only; no `web/app/api/**/route.ts` for agent/token logic.
- FastAPI owns token generation, `AGORA_APP_CERTIFICATE`, `CUSTOM_LLM_API_KEY`, and agent lifecycle.
- `server/src/llm.py` must not import any `agora_*` package (enforced by `test_llm_module_has_no_agora_dependency`).
- `POST /llm/chat/completions` must return streaming SSE in OpenAI chunk format; `stream=false` must return 400.
- `CUSTOM_LLM_URL` must be a public URL; no localhost default — Agora cloud calls it directly.
- `turn_detection` (VAD) is set on `AgoraAgent(...)`, not on `CustomLLM`.
- The backend issues one RTC+RTM-capable token for a concrete non-zero UID.

## Stable Contracts

| Contract | Stable shape |
| -------- | ------------ |
| Required backend env | `AGORA_APP_ID`, `AGORA_APP_CERTIFICATE`, `CUSTOM_LLM_URL`, `CUSTOM_LLM_API_KEY` |
| Optional backend env | `CUSTOM_LLM_MODEL`, `AGENT_GREETING`, `PORT` (env only) |
| Required web deploy env | `AGENT_BACKEND_URL` |
| `GET /api/get_config` | Query `channel?`, `uid?`; returns `data.app_id`, `data.token`, `data.uid`, `data.channel_name`, `data.agent_uid`. |
| `POST /api/startAgent` | Body `{ channelName, rtcUid, userUid, parameters? }`; returns `data.agent_id`, `data.channel_name`, `data.status`. |
| `POST /api/stopAgent` | Body `{ agentId }`; returns `{ code: 0, msg: "success" }`. |
| `POST /llm/chat/completions` | Body: OpenAI `ChatCompletionRequest` with `stream: true`; returns SSE stream terminated with `data: [DONE]`. |
| Success envelope | `{ "code": 0, "msg": "success", "data": ... }` where the route has data. |
| Verification entry points | `bun run verify:web`, `bun run verify:backend`, `bun run verify:web:proxy`, `bun run verify:local:fastapi`, `bun run verify:local:llm`, `bun run verify:local`. |

## Internal / Subject to Change

- Visual layout, component composition, Tailwind classes, and assets under `web/src/components/`.
- Mock response text in `MOCK_RESPONSES` and the cycling logic in `get_mock_response()`.
- Exact VAD timing values (`interrupt_duration_ms`, `silence_duration_ms`, `speech_threshold`).
- In-memory `Agent._sessions` details; the stable behavior is start by channel/user and stop by returned `agent_id`.
- Verification internals under `web/scripts/`; the stable surface is the root script names and what they assert.
- `agora-agents` SDK minor-version behavior; this recipe lower-bounds `>=2.3.0` but does not freeze every field.

## Related Progressive Disclosure Docs

- `L1/01_setup.md` — setup, env, tunnel, and commands.
- `L1/02_architecture.md` — request flow and topology.
- `L1/05_workflows.md` — common modification workflows.
- `L1/06_interfaces.md` — route, rewrite, env, and vendor contracts.
- `L1/L2/custom_llm_config.md` — full `CustomLLM` vendor + STT/TTS + VAD config detail.
- `L1/L2/llm_endpoint_contract.md` — SSE contract and replacement guide for `llm.py`.
- `L1/L2/session_lifecycle.md` — RTC/RTM/session orchestration.
