# 05 · Workflows

> Step-by-step guides for the common changes in this recipe. Each ends with the narrowest verify command to run.

## Add or change a browser-facing route

1. Add the FastAPI handler in `server/src/server.py` (return the `{ code, msg, data }` envelope).
2. Add the `/api/<name>` → `/<name>` mapping in `web/next.config.ts` `rewrites()`.
3. Add a client helper in `web/src/services/api.ts`.
4. Extend `web/scripts/verify-api-contracts.ts` with the new path + envelope assertions.
5. Verify: `bun run verify:web` (and `bun run verify:local:fastapi` if it should go through the real backend).

## Replace the mock LLM with a real model

1. Edit `get_mock_response()` in `server/src/llm.py` — or replace the whole function body with your model call.
2. Keep the `POST /chat/completions` contract: streaming SSE, `data: [DONE]` terminator, reject `stream=false` with 400.
3. If the endpoint needs its own API key, read it from env in `llm.py` (add to `.env.example`).
4. Verify: `cd server && pytest tests/test_llm.py -v` and `bun run verify:local:llm`.

## Point to an external LLM (not the mounted endpoint)

1. Set `CUSTOM_LLM_URL` to the external endpoint (e.g. a Cloudflare Worker, a vLLM server, etc.).
2. If running the external endpoint yourself, you no longer need ngrok for `/llm` — but `CUSTOM_LLM_URL` must still be publicly reachable by Agora cloud.
3. `server/src/llm.py` stays in place (it is still mounted and exercised by `verify:local:llm`), but Agora cloud will call your external URL instead.
4. Verify: `bun run verify:backend` + `bun run doctor:local`.

## Change the agent prompt / greeting / model

1. Greeting: set `AGENT_GREETING` (env) or edit the default in `server/src/agent.py`.
2. Model name: set `CUSTOM_LLM_MODEL` (default `mock-model`); passed to the LLM endpoint as `model` in the request body.
3. Prompt: edit `CUSTOM_LLM_PROMPT` in `server/src/agent.py`.
4. Verify: `bun run verify:backend` + `cd server && pytest tests -v`.

## Change STT or TTS vendor

1. Edit `agent.py`: import the new vendor from `agora_agent.agentkit.vendors`, instantiate it, and swap the `.with_stt()` or `.with_tts()` call.
2. Add any new required env vars to `server/.env.example` and document in README + `06_interfaces.md`.
3. Verify: `bun run verify:backend` + `cd server && pytest tests -v`.

## Adjust VAD or session parameters

1. Edit the `turn_detection` dict in `AgoraAgent(...)` in `agent.py` to tune `speech_threshold`, `interrupt_duration_ms`, or `silence_duration_ms`.
2. Edit the `parameters` dict in `Agent.start()` for `audio_scenario`, `data_channel`, `enable_metrics`, etc.
3. Verify: `bun run verify:local:fastapi`.

## Run / debug locally

```bash
bun run dev              # both processes; requires CUSTOM_LLM_URL in .env.local
bun run doctor:local     # check creds + .env.local + CUSTOM_LLM_URL before a live call
```

## Verify before finishing

| Change touches…                    | Run                                                                      |
| ---------------------------------- | ------------------------------------------------------------------------ |
| Web only                           | `bun run verify:web`                                                      |
| Backend logic / agent config       | `bun run verify:backend` + `cd server && pytest tests -v`                 |
| LLM endpoint contract (`llm.py`)   | `cd server && pytest tests/test_llm.py tests/test_llm_mount.py -v` + `bun run verify:local:llm` |
| Route/proxy boundary               | `bun run verify:web:proxy` and/or `bun run verify:local:fastapi`         |
| Anything end-to-end (local)        | `bun run verify:local`                                                    |

## Deploy

1. Deploy `web/` as a Next.js app.
2. Deploy `server/` as a **publicly reachable** FastAPI service (it must serve `/llm/chat/completions`). The published backend-only image is `ghcr.io/AgoraIO-Conversational-AI/recipe-agent-custom-llm` on `v*` tags.
3. Set `AGENT_BACKEND_URL` in the web deployment.
4. Set `CUSTOM_LLM_URL` to `<your-public-backend-url>/llm/chat/completions`.

## Related Deep Dives

- [custom_llm_config](L2/custom_llm_config.md) — `CustomLLM` vendor build details, STT/TTS, VAD, session options.
- [session_lifecycle](L2/session_lifecycle.md) — client-side join/renewal/teardown.
