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
