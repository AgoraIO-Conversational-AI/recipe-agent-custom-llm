# 03 · Code Map

> Where things live. Two top-level modules: `web/` (Next.js client) and `server/` (FastAPI backend + LLM endpoint). Orchestration is in the root `package.json`.

## Root

| Path                  | Responsibility                                                                 |
| --------------------- | ------------------------------------------------------------------------------ |
| `package.json`        | Bun workspace; `setup`, `dev`, `doctor*`, `verify*`, `clean` scripts.          |
| `README.md`           | Setup, run modes, env, troubleshooting, replacing the mock.                    |
| `ARCHITECTURE.md`     | System shape, request flow, one-process two-concern rationale.                 |
| `AGENTS.md`           | Coding-agent handbook + How to Load / Git Conventions / Doc Commands.          |
| `Dockerfile`          | Backend-only image (`:8000`).                                                  |
| `.github/workflows/`  | `ci.yml` (backend pytest matrix + web `bun test`), `docker.yml`, `nightly.yml`.|

## `server/` — FastAPI backend (:8000)

| Path                              | Responsibility                                                              |
| --------------------------------- | --------------------------------------------------------------------------- |
| `src/server.py`                   | FastAPI app, CORS, route handlers, error mapping, mounts `llm_app`, uvicorn entrypoint. |
| `src/agent.py`                    | `Agent` class: `AsyncAgora` client, `start()`/`stop()`, `_sessions`. Validates all four required env vars at `__init__`. |
| `src/llm.py`                      | Provider-agnostic `POST /chat/completions` mock (OpenAI SSE) + `GET /health`. No `agora_agent` import. Mountable and runnable standalone. |
| `scripts/run_fake_server.py`      | Boots `server.app` with a `FakeAgent` for the local FastAPI and LLM smoke tests. |
| `tests/test_agent_construction.py`| Builds real `AgoraAgent`, fakes the SDK session, asserts result shape.      |
| `tests/test_agent.py`             | Env validation, `CustomLLM` vendor wiring, stop fallback, argument validation. |
| `tests/test_llm.py`               | `llm.app` in isolation: SSE contract, non-streaming rejection, health check. |
| `tests/test_llm_mount.py`         | LLM endpoint reachable through the main app mount; `llm.py` has no `agora_*` imports. |
| `tests/test_server.py`            | FastAPI routes via `TestClient` + `FakeAgent`: envelope, token, start, stop, error mapping. |
| `tests/conftest.py`               | `fake_env` fixture + `FakeAgent` + `server_module` + `client`; no cloud, no real creds. |
| `.env.example`                    | Env template (do not add `PORT`).                                           |
| `requirements.txt`                | Runtime deps: fastapi, uvicorn, requests, python-dotenv, agora-agents>=2.3.0, socksio. |
| `requirements-dev.txt`            | Dev deps: pytest>=7.4, httpx>=0.24.                                         |

## `server/src/server.py` routes

- `GET /get_config` — token + channel/UID config.
- `POST /startAgent` — start the cascading-vendor agent session.
- `POST /stopAgent` — stop by `agent_id`.
- `/llm` (mount) — delegates all `/llm/*` requests to `llm.app` (`src/llm.py`).

## `web/` — Next.js client (:3000)

| Path                                      | Responsibility                                                         |
| ----------------------------------------- | ---------------------------------------------------------------------- |
| `next.config.ts`                          | `/api/*` rewrites to `AGENT_BACKEND_URL`; strict mode; Turbopack root. |
| `src/services/api.ts`                     | Browser API client: `getConfig`, `startAgent`, `stopAgent`.            |
| `src/lib/conversation.ts`                 | Transcript normalization, timestamp/UID mapping, visualizer state.     |
| `src/lib/agora.ts`                        | `DEFAULT_AGENT_UID` constant.                                          |
| `src/components/LandingPage.tsx`          | Conversation entry: config fetch, agent start, RTM login, teardown.    |
| `src/components/ConversationComponent.tsx`| RTC join, mic publish, transcript/metrics/state listeners.             |
| `src/components/Quickstart*.tsx`          | Pre-call, transcript, metrics, layout panels.                          |
| `scripts/verify-api-contracts.ts`         | Asserts rewrites + client paths + response envelope (no network).      |
| `scripts/verify-local-proxy.ts`           | Stub backend; proxies `/api/*` through the rewrite map.                |
| `scripts/verify-local-fastapi.ts`         | Spawns real FastAPI with `FakeAgent`; proxies routes end-to-end.       |
| `scripts/verify-local-llm.ts`             | Spawns real FastAPI with `FakeAgent`; exercises `/llm/chat/completions` through the mount. |
| `scripts/doctor.ts`                       | Web prerequisite check.                                                |

## Related Deep Dives

- None. For runtime flow see [02_architecture](02_architecture.md); for contracts see [06_interfaces](06_interfaces.md).
