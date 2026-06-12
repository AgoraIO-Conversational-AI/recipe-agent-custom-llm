# Agora Conversational AI — Custom LLM Recipe (Python)

The **custom-llm** recipe in the Agora Conversational AI recipes family. Bring your
own LLM to Agora's voice pipeline: the agent's LLM stage is pointed at your own
OpenAI-compatible `POST /chat/completions` endpoint instead of a managed model.
STT (Deepgram) and TTS (MiniMax) stay Agora-managed.

This repo ships a **zero-key mock** LLM endpoint so you can run the full
STT → custom LLM → TTS pipeline immediately, then replace the mock with your own
model.

## Prerequisites

- [Python 3.10+](https://www.python.org/)
- [Bun](https://bun.sh/)
- [ngrok](https://ngrok.com/) (or any tunnel to expose localhost)
- Agora App ID + App Certificate (the [Agora CLI](https://github.com/AgoraIO/cli) makes this easy)

## Run it

```bash
# 1. Install + create both Python venvs
bun run setup

# 2. Add Agora credentials (CLI), or edit server/.env.local by hand
agora login
agora project use <your-project>          # select which project to use (you may have several)
agora project env write server/.env.local # writes App ID/Certificate; keeps your CUSTOM_LLM_* lines

# 3. Expose the custom LLM endpoint publicly (Agora cloud calls it directly)
ngrok http 8000

# 4. Add the tunnel URL to server/.env.local (use whatever domain ngrok prints —
#    today that is usually *.ngrok-free.dev)
#    CUSTOM_LLM_URL=https://<your-tunnel>.ngrok-free.dev/llm/chat/completions

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
                       Custom LLM endpoint  (mounted at /llm in server/, localhost:8000)
                          ▲  public via ngrok tunnel
```

The browser only ever calls Next `/api/*`, which rewrites to the agent backend.
The agent backend owns Agora tokens and agent lifecycle. The **custom LLM
endpoint** is mounted at `/llm` in the same backend; because Agora cloud — not the browser — calls it, that backend must be publicly reachable (`ngrok http 8000`). See [ARCHITECTURE.md](./ARCHITECTURE.md).

## Project structure

```
agent-recipes-python/
├── server/   # Agent backend (:8000) — tokens + agent lifecycle + mounted LLM
│   ├── src/{server.py, agent.py, llm.py}   # llm.py mounted at /llm, no agora deps
│   └── scripts/run_fake_server.py
├── web/      # Shared Next.js frontend (:3000)
└── package.json
```

## Environment variables

Backend env file: [`server/.env.example`](server/.env.example).

| Variable | Required | Default | Notes |
| --- | :---: | :---: | --- |
| `AGORA_APP_ID` | ✅ | — | Agora Console → Project → App ID |
| `AGORA_APP_CERTIFICATE` | ✅ | — | Agora Console → Project → App Certificate (server only) |
| `CUSTOM_LLM_URL` | ✅ | — | **Public** chat-completions URL of your mounted `/llm` endpoint (`<tunnel>/llm/chat/completions`). Agora cloud calls it; cannot be `localhost`. |
| `CUSTOM_LLM_API_KEY` | ✅ | `any-key-here` | Forwarded by Agora cloud as `Authorization: Bearer`. Required by the `CustomLLM` vendor. |
| `CUSTOM_LLM_MODEL` |  | `mock-model` | Model name passed to your endpoint |
| `AGENT_GREETING` |  | built-in | Optional opening line override |
| `PORT` |  | `8000` | Agent backend port |
| `AGENT_BACKEND_URL` (web deploy) | ✅ | — | Required in a deployed `web` app when proxying to the backend |

## Commands

```bash
bun run setup            # install web deps + create the server/ venv
bun run dev              # run backend (:8000, serves /llm) + web (:3000)

bun run doctor           # prerequisite check (no creds needed)
bun run doctor:local     # + .env.local + credentials + CUSTOM_LLM_URL checks

bun run verify           # web-only gate (no Agora creds needed)
bun run verify:local     # full local gate: backend compile + smoke tests + web build
bun run clean            # remove venvs and build artifacts
```

Tests run standalone (no Agora cloud needed): `pytest` in `server/`, `bun test` in `web/`. CI runs them on Linux/macOS/Windows × Python 3.10 & 3.13.

## Replacing the mock

Edit `get_mock_response()` in [`server/src/llm.py`](server/src/llm.py).
The endpoint must keep speaking the OpenAI streaming `/chat/completions` contract
(see the contract notes in `server/src/llm.py`). A production endpoint should also validate
the `Authorization: Bearer` header.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Agent starts but never speaks | `CUSTOM_LLM_URL` is not public or omits `/chat/completions`. Use your ngrok URL. |
| `doctor:local` warns about localhost | Replace the local URL with your public tunnel URL. |
| Local calls fail / hang under a global proxy (Clash, etc.) | Your proxy is routing loopback through itself. Configure it to send `127.0.0.1`, `localhost`, and RFC-1918 ranges DIRECT (don't disable the proxy entirely). |
| `Missing server/venv` during verify | Run `bun run setup`. |

## License

MIT
