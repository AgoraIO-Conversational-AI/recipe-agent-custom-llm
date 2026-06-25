# 02 · Architecture

> One process, two concerns. The browser talks only to Next.js `/api/*`, which rewrites to the FastAPI agent backend. The same backend also serves the custom LLM endpoint at `/llm` — so Agora cloud, which calls the endpoint directly, requires the backend to be publicly reachable via a tunnel.

## Topology

```
Browser (localhost:3000)
  │  fetch /api/*
  ▼
Next.js (web/)  ──rewrite──▶  Agent backend (server/, :8000)
                                 │  builds CustomLLM(base_url=CUSTOM_LLM_URL)
                                 ▼
                              Agora ConvoAI Cloud
                                 │  user speech → Deepgram STT (managed)
                                 │  POST <CUSTOM_LLM_URL>/chat/completions (Bearer)
                                 ▼
                              Custom LLM endpoint (/llm mounted in server/, :8000)
                                 │  public via ngrok/tunnel
                                 ▼
                              Agora ConvoAI Cloud → MiniMax TTS (managed)
                                 │  agent speech → user's channel
                                 │  RTM transcript + metrics → web UI
```

- **`web/`** — Next.js 16 / React 19 / TypeScript. Owns UI plus the RTC/RTM client lifecycle. Calls only `/api/*`.
- **`server/`** — Python FastAPI (:8000). Owns Agora token generation and agent session lifecycle. SDK: `agora-agents>=2.3.0` (`import agora_agent`).
- **`server/src/llm.py`** — provider-agnostic `POST /chat/completions` mock, mounted into the same app at `/llm`. No `agora_agent` import — it is the component you replace.

## Request lifecycle

1. Browser `GET /api/get_config` → Next rewrites to backend `/get_config`; backend mints a Token007 and returns channel + UIDs.
2. Browser joins the RTC channel, then `POST /api/startAgent`; backend validates env, builds `CustomLLM` vendor, and starts an async agent session.
3. Agora routes user audio to Deepgram STT (managed); the text is forwarded as `POST <CUSTOM_LLM_URL>/chat/completions` to the mounted `/llm` endpoint.
4. The `/llm` endpoint streams back OpenAI SSE; Agora converts it to speech via MiniMax TTS (managed) and delivers audio to the channel.
5. RTM delivers transcript + metrics to the web UI.
6. `POST /api/stopAgent { agentId }` ends the session.

## One process, two concerns

`server/` runs a single process that serves both the token/agent endpoints and, mounted at `/llm`, the custom LLM endpoint. The dependency is one-directional: `server.py` imports `llm`; `llm.py` does **not** import `agora_agent`. This separation is enforced by `test_llm_mount.py`.

Because `/llm` is publicly reachable, the token endpoints (`/get_config`, `/startAgent`, `/stopAgent`) are also reachable from the internet. They are unauthenticated in this recipe; add auth / rate-limiting before any real deployment.

## Key abstractions

- **`Agent`** (`server/src/agent.py`) — async wrapper around `AgoraAgent`; owns the `AsyncAgora` client, env, and the in-memory `_sessions` map keyed by `agent_id`. Validates all four required env vars at `__init__`.
- **`llm.app`** (`server/src/llm.py`) — standalone FastAPI app with `POST /chat/completions` (streaming SSE) and `GET /health`. Mounted into the main app at `/llm`.
- **Rewrite proxy** (`web/next.config.ts`) — the only browser→backend boundary; no Next Route Handlers exist for agent/token logic.

## Tech decisions

- **Single-process mount** — `app.mount("/llm", llm_app)` co-locates the token/agent surface and the LLM endpoint on one port, so one ngrok tunnel covers both.
- **Cascading vendors** — `CustomLLM` (LLM stage) + `DeepgramSTT` + `MiniMaxTTS` wired via `.with_stt().with_llm().with_tts()`. Contrast with the realtime recipe's single MLLM.
- **VAD on `AgoraAgent`** — `turn_detection` with `vad` mode is set directly on `AgoraAgent(...)`, not on a vendor. This is the opposite of the MLLM recipe.
- **Zero-key mock** — the mock endpoint needs no LLM API key; you get a working voice loop immediately, then swap `get_mock_response()`.

## Related Deep Dives

- [custom_llm_config](L2/custom_llm_config.md) — `CustomLLM` vendor wiring, STT/TTS vendors, VAD config, and session options.
- [session_lifecycle](L2/session_lifecycle.md) — browser orchestration of config + start/stop, RTC/RTM, transcript mapping.
