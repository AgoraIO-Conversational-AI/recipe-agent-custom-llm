# Architecture

All recipes share the same topology. The only difference is what the recipe server does.

## Shared Topology

```
Browser (localhost:3000)
  ↓ fetch /api/*
Next.js (rewrites to AGENT_BACKEND_URL)
  ↓
Recipe Agent Backend (localhost:8000)
  ↓ starts agent session
Agora ConvoAI Cloud
  ↓                              ↓                    ↓
Deepgram STT              Recipe Server (8001)    TTS (if applicable)
(managed)                 (YOUR endpoint, public)  (managed or skipped)
                                ↑
                      ngrok tunnel from localhost:8001
```

## Per-Recipe Differences

### custom-llm

```
Agora Cloud → POST /chat/completions → your server returns text (SSE)
                                                    ↓
                                        Agora Cloud → MiniMax TTS → user hears speech
```

Agent config: `OpenAI(base_url="your-url/chat/completions")`

### audio-modalities

```
Agora Cloud → POST /audio/chat/completions → your server returns audio (SSE)
                                                    ↓
                                        Agora Cloud → RTC → user hears audio directly
                                        (no TTS step)
```

Agent config: `OpenAI(base_url="your-url/audio/chat/completions", output_modalities=["audio"])`

## Request Flow (all recipes)

1. **GET /get_config** → Backend generates Token007, returns channel + UIDs
2. **POST /startAgent** → Backend creates agent session pointing to recipe server
3. **Conversation** → Agora cloud handles STT, calls your server, handles TTS/audio output
4. **POST /stopAgent** → Backend stops session

## API Endpoints (Agent Backend, port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/get_config` | GET | Token + channel config |
| `/startAgent` | POST | Start agent |
| `/stopAgent` | POST | Stop agent |

## Auth

- Agent Backend ↔ Agora Cloud: Token007 (`AGORA_APP_ID` + `AGORA_APP_CERTIFICATE`)
- Agora Cloud → Recipe Server: `Authorization: Bearer <api_key>` header
- Browser → Agent Backend: none (local dev)

## Key Constraint

Recipe servers must be **publicly reachable**. Agora cloud calls them directly.
