# 04 · Conventions

> Coding patterns shared across `server/` and `web/`. Follow these to keep local and deployed modes aligned and to preserve the `llm.py` isolation invariant.

## Boundary ownership

- Browser code calls only `/api/*`. Backend placement is hidden behind Next rewrites (`web/next.config.ts`).
- **Never** add `web/app/api/**/route.ts` for agent/token logic — `verify-api-contracts.ts` fails the build if a `route.ts` appears under `app/api`.
- Token generation and the App Certificate stay in `server/`.

## `llm.py` isolation rule

- `server/src/llm.py` must **not** import any `agora_*` package. It is the provider-agnostic component developers replace with their own model. `test_llm_mount.py` asserts this at the AST level.
- `server.py` imports `llm`; `llm.py` never imports `server` or `agent`. The dependency is one-directional.
- `llm.py` can be run standalone via `python src/llm.py` (default port 8001) for isolated development.

## Backend (Python / FastAPI)

- Async throughout: route handlers are `async def`; the agent uses `AsyncAgora` and `create_async_session`.
- Request bodies are Pydantic models (`StartAgentRequest`, `StopAgentRequest`). Field names are **camelCase** (`channelName`, `rtcUid`, `userUid`) to match the browser client.
- Error mapping is centralized: `_to_http_error()` maps `ValueError → 400`, `RuntimeError → 500`, else 500. `_log_route_error()` logs with safe context + traceback. Raise plain `ValueError`/`RuntimeError`; let the route convert.
- Logging via `logging.getLogger("uvicorn.error")`.
- Env read with `os.getenv`; `.env.local` then `.env` loaded with `override=True`.
- All four env vars (`AGORA_APP_ID`, `AGORA_APP_CERTIFICATE`, `CUSTOM_LLM_URL`, `CUSTOM_LLM_API_KEY`) are validated at `Agent.__init__`; the server raises a logged `ValueError` at startup if any are missing.

## Response envelope

All backend JSON responses use:

```json
{ "code": 0, "msg": "success", "data": { } }
```

`data` is present only when the route returns a payload. The browser client treats `code !== 0` (or missing `data`) as an error.

## LLM SSE contract

`POST /llm/chat/completions` must return:
- `StreamingResponse` with `media_type="text/event-stream"`.
- Each chunk as `data: {json}\n\n` in OpenAI chunk format.
- Terminate with `data: [DONE]\n\n`.
- Reject `stream=false` with HTTP 400 — Agora ConvoAI always uses streaming.

Do not change this contract in `llm.py`; `test_llm.py` and `verify:local:llm` assert it.

## Agent vendor chain

The cascading pipeline is wired in `agent.py`:

```python
agora_agent.with_stt(stt).with_llm(llm).with_tts(tts)
```

STT is `DeepgramSTT`, TTS is `MiniMaxTTS`, LLM is `CustomLLM`. Changing STT or TTS requires updating `agent.py`; changing the LLM implementation does **not** require touching `agent.py` if the endpoint contract is preserved.

## Turn detection

`turn_detection` with `vad` mode is set on `AgoraAgent(...)` directly — not on a vendor. This is the correct pattern for the cascading pipeline. Do **not** move it to the `CustomLLM` vendor.

## Web (TypeScript / Next.js)

- Lint/format with Biome (`bun run lint`, `bun run lint:fix` in `web/`).
- RTC client creation must be StrictMode-safe (strict mode is on).
- Transcript speaker mapping uses real UIDs (`normalizeTranscript` maps `uid === '0'` to the local UID).
- API client lives in `src/services/api.ts`; UI never calls `fetch` to the backend directly.

## Testing approach

- Backend: `pytest` in `server/`, standalone — `conftest.py` fakes env and SDK session; no cloud, no real creds, no ngrok.
- Web: contract/proxy/fastapi/llm smoke scripts under `web/scripts/` run without live Agora calls.
- Run the **narrowest** relevant verify command before finishing (see [05_workflows](05_workflows.md)).

## Doc upkeep

When you change request/response contracts, env vars, or workflow, update the web client, backend, contract checks, README, **and** the matching `docs/ai/L1/` file together, then bump `Last Reviewed` in [L0](../L0_repo_card.md).

## Related Deep Dives

- None.
