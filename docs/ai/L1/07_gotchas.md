# 07 · Gotchas

> Non-obvious pitfalls specific to the custom-llm recipe. Read before changing the agent, env, verify scripts, or the LLM endpoint.

## `CUSTOM_LLM_URL` must be public — no localhost default

Agora cloud — not the browser or the agent backend — calls `CUSTOM_LLM_URL`. A `localhost` URL causes the agent to "start" successfully while the LLM calls silently fail cloud-side (the agent never speaks). `doctor:local` warns if `CUSTOM_LLM_URL` contains `localhost` or `127.0.0.1`. There is intentionally no localhost default. Always set a public tunnel URL for local dev.

## All four env vars are validated at startup, not at agent start

Unlike the realtime recipe where `OPENAI_API_KEY` is deferred to `start()`, this recipe validates `AGORA_APP_ID`, `AGORA_APP_CERTIFICATE`, `CUSTOM_LLM_URL`, and `CUSTOM_LLM_API_KEY` in `Agent.__init__`. A missing var raises `ValueError` at server startup; the server logs the error and sets `agent = None`. All routes then return 500. Fix the env var and restart.

## Do not import `agora_agent` in `llm.py`

`llm.py` is provider-agnostic. Adding an `agora_*` import breaks the isolation invariant and is caught by `test_llm_module_has_no_agora_dependency` (AST-level check). Keep all Agora SDK usage in `agent.py` and `server.py`.

## VAD is set on `AgoraAgent`, not on a vendor

For the cascading pipeline, `turn_detection` lives on `AgoraAgent(...)` directly. This is the opposite of the realtime recipe (where VAD is vendor-owned). Do not move `turn_detection` to `CustomLLM`.

## Do not put `PORT` in `server/.env.example`

`verify:local:fastapi` and `verify:local:llm` inject a random `PORT` and load env with `load_dotenv(override=True)`. A `PORT` line in `.env.example` (copied to `.env.local`) would clobber the injected port and break the smoke tests.

## Keep `/api/*` ownership in rewrites

Adding `web/app/api/**/route.ts` for agent/token logic breaks the boundary — `verify-api-contracts.ts` explicitly fails if a `route.ts` exists under `app/api`. Token logic belongs in `server/`.

## camelCase request fields

`StartAgentRequest` uses `channelName`, `rtcUid`, `userUid` (camelCase) to match the browser client. Renaming one side without the other breaks the contract tests.

## UID normalization in transcripts

`normalizeTranscript` maps `uid === '0'` to the local UID. Token issuance also rejects zero/negative UIDs and generates a concrete one. Preserve both — speaker mapping and tokens depend on concrete UIDs.

## Local calls under a global proxy

Global proxies (Clash, etc.) can break `localhost`/RFC-1918 traffic. Configure the proxy to send `127.0.0.1`, `localhost`, and private ranges DIRECT, or use `socksio` (in `requirements.txt`) with `all_proxy` to route the backend through SOCKS.

## The LLM endpoint must always stream

Agora ConvoAI always sends `stream: true`. The mock endpoint rejects `stream: false` with HTTP 400. A replacement endpoint must do the same — returning a non-streaming response will break the pipeline.

## Related Deep Dives

- [custom_llm_config](L2/custom_llm_config.md) — correct `CustomLLM`/VAD wiring.
