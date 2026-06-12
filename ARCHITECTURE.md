# Architecture — Custom LLM Recipe

Two processes. The browser talks only to Next.js `/api/*`, which rewrites to the
agent backend. The agent backend owns Agora tokens and agent lifecycle, and also
serves the custom LLM endpoint mounted at `/llm`, which **Agora cloud** calls
directly.

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
Custom LLM endpoint (mounted at /llm in server/, :8000, public via tunnel)
  │  returns OpenAI SSE
  ▼
Agora ConvoAI Cloud → MiniMax TTS (managed) → user hears speech
                     → RTM transcript / metrics → web UI
```

`POST /api/stopAgent { agentId }` ends the session.

## One process, two concerns

`server/` runs a single process that serves both the token/agent endpoints and,
mounted at `/llm`, the OpenAI-compatible custom LLM endpoint (`server/src/llm.py`).

The two concerns are kept in separate files with a one-directional dependency
(`server.py` imports `llm`, never the reverse), and `llm.py` has no `agora_agent`
import — it is the provider-agnostic part you replace with your own model.

Merging them onto one public surface is a deliberate trade. The Agora App
Certificate is only ever used in-memory to mint tokens — it never crosses a wire —
so co-locating the public `/llm` route with the token endpoints does not expose the
certificate. It does, however, make the token-minting endpoints (`/get_config`,
`/startAgent`, `/stopAgent`) publicly reachable. They are unauthenticated in this
recipe; put auth / rate-limiting in front of them (ingress, gateway, or a proxy)
before any real deployment.

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
