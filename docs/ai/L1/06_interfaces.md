# 06 · Interfaces

> Boundary contracts: backend routes, the `/api/*` rewrite map, env vars, the response envelope, the `CustomLLM` vendor config, and the LLM SSE contract.

## Backend routes (port 8000)

The browser calls these as `/api/<name>`; Next rewrites to the backend `/<name>`.

### `GET /get_config`

- Query (optional): `channel?: string`, `uid?: int` (≤ 0 or missing → backend generates one).
- Returns `data`: `{ app_id, token, uid (string), channel_name, agent_uid (string) }`.
- Token is a Token007 RTC+RTM token, expiry 3600s, for a concrete non-zero UID.
- `channel_name` defaults to `custom-llm-<timestamp>-<random>`.

### `POST /startAgent`

- Body: `{ channelName: string, rtcUid: int, userUid: int, parameters?: object }`.
  - `parameters.output_audio_codec?: string` is the only honored parameter field.
- Returns `data`: `{ agent_id, channel_name, status: "started" }`.
- 400 if `channelName`/`rtcUid`/`userUid` invalid, or if `CUSTOM_LLM_URL`/`CUSTOM_LLM_API_KEY` missing.
- 500 if agent is `None` (misconfigured at startup).

### `POST /stopAgent`

- Body: `{ agentId: string }`.
- Returns `{ code: 0, msg: "success" }` (no `data`).

## LLM endpoint (mounted at `/llm`)

Agora cloud calls this directly at `<CUSTOM_LLM_URL>` (which must be the public URL ending in `/llm/chat/completions`).

### `POST /llm/chat/completions`

- Header: `Authorization: Bearer <CUSTOM_LLM_API_KEY>` (sent by Agora cloud; mock does not validate).
- Body: OpenAI `ChatCompletionRequest` — `model`, `messages`, `stream: true`, optional `temperature`, `max_tokens`, `tools`, `tool_choice`.
- Returns: `StreamingResponse` (`text/event-stream`), OpenAI SSE chunk format, terminated with `data: [DONE]`.
- 400 if `stream: false`.

### `GET /llm/health`

- Returns `{ "status": "ok", "service": "custom-llm-mock" }`.

## Response envelope

```json
{ "code": 0, "msg": "success", "data": { } }
```

`data` omitted when the route has no payload. Non-zero `code` or missing `data` = error on the client side.

## Rewrite map (`web/next.config.ts`)

| Browser path        | Backend destination |
| ------------------- | ------------------- |
| `/api/get_config`   | `/get_config`       |
| `/api/startAgent`   | `/startAgent`       |
| `/api/stopAgent`    | `/stopAgent`        |

`rewrites()` returns `[]` when `AGENT_BACKEND_URL` is unset. The contract is asserted by `verify-api-contracts.ts` and exercised by `verify-local-proxy.ts`.

## Browser API client (`web/src/services/api.ts`)

- `getConfig({ channel?, uid? }) → GetConfigResponse`
- `startAgent(channelName, rtcUid, userUid) → agent_id`
- `stopAgent(agentId) → void`

## Environment variables

| Variable                | Scope              | Required | Default                  |
| ----------------------- | ------------------ | :------: | ------------------------ |
| `AGORA_APP_ID`          | backend            |    ✅    | —                        |
| `AGORA_APP_CERTIFICATE` | backend            |    ✅    | —                        |
| `CUSTOM_LLM_URL`        | backend            |    ✅    | — (no localhost default) |
| `CUSTOM_LLM_API_KEY`    | backend            |    ✅    | `any-key-here`           |
| `CUSTOM_LLM_MODEL`      | backend            |          | `mock-model`             |
| `AGENT_GREETING`        | backend            |          | built-in line            |
| `AGENT_BACKEND_URL`     | web (deploy)       |    ✅\*  | `http://localhost:8000` (dev) |
| `PORT`                  | backend (env only) |          | `8000` — do **not** put in `.env.example` |

\* Required wherever the web app is deployed; rewrites are empty without it.

## `CustomLLM` vendor config (`agent.py`)

`CustomLLM(base_url, api_key, model, greeting_message, failure_message, max_history, max_tokens, temperature, top_p)` — values from env + defaults:

| Param             | Source                | Default                   |
| ----------------- | --------------------- | ------------------------- |
| `base_url`        | `CUSTOM_LLM_URL`      | — (required)              |
| `api_key`         | `CUSTOM_LLM_API_KEY`  | — (required)              |
| `model`           | `CUSTOM_LLM_MODEL`    | `mock-model`              |
| `greeting_message`| `AGENT_GREETING`      | built-in line             |
| `max_history`     | hardcoded             | `15`                      |
| `max_tokens`      | hardcoded             | `1024`                    |
| `temperature`     | hardcoded             | `0.7`                     |
| `top_p`           | hardcoded             | `0.95`                    |

## Related Deep Dives

- [custom_llm_config](L2/custom_llm_config.md) — full `CustomLLM` + STT/TTS + VAD + session options detail.
