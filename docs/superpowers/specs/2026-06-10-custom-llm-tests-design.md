# Custom LLM Recipe — Standalone Test Suite Design

**Date:** 2026-06-10
**Status:** Approved
**Repo:** `recipe-agent-custom-llm` (local folder is the stale `agent-recipes-python`)
**Branch:** `test/add-suite` off `main`

## Goal

Add a **standalone, multi-platform** automated test suite to the custom-llm recipe — covering the Python backend (`server/`, `llm/`) with pytest and the web units (`web/`) with `bun test` — plus GitHub Actions CI that runs them across an OS × Python matrix. The design is intended to **port directly** to `recipe-agent-custom-llm-tts` afterwards.

## Definitions

- **Standalone:** tests run with **no external services** — no Agora cloud, no ngrok, no real credentials, no running dev stack. `pip install` the dev deps + `pytest` (or `bun test`) is all that's needed. The single cloud-facing call (`AgentSession.start()`) is **mocked**; everything else is exercised for real (FastAPI via `TestClient`, the mock LLM endpoint, the SSE contract, pure web helpers). Each package's tests are self-contained and runnable independently.
- **Multi-platform:** the same plain `pytest` / `bun test` commands run on Linux/macOS/Windows; CI proves it across the matrix.

## Locked Decisions

1. **Frameworks:** `pytest` for Python; `bun test` (zero-config, repo already uses Bun) for web.
2. **Coverage:** `server/` (agent wiring + FastAPI routes), `llm/` (SSE contract), `web/` (`api.ts` client, `conversation.ts` transcript/visualizer helpers).
3. **Cloud is mocked:** `server/tests` never hit Agora cloud; `AgentSession.start()`/`stop()` and token-bearing paths are exercised without network.
4. **CI matrix:** `{ubuntu-latest, macos-latest, windows-latest} × Python {3.10, 3.13}` for the Python job; a separate Bun job for `web/`. On push + PR.
5. **Python floor bump:** raise the documented floor from **3.8+ → 3.10+** (the latest fastapi/uvicorn already require ≥3.10; supporting 3.8 would silently give those users an older dependency stack). Update all version mentions.
6. **Coexistence:** keep the existing `verify:*` Bun scripts as **local dev tools** (they're partly bash / not Windows-clean). CI runs **only** the new pytest/bun tests.
7. **No production-code changes** beyond what testability strictly requires (the code is already structured for it — `server.agent` is module-level and swappable, exactly as `run_fake_server.py` does).

## Layout

```
server/
  requirements-dev.txt        # pytest, httpx (TestClient transport)
  tests/
    conftest.py               # fake env vars, TestClient app + FakeAgent fixtures
    test_agent.py             # Agent: env validation + vendor wiring (session mocked)
    test_server.py            # FastAPI routes via TestClient + FakeAgent
llm/
  requirements-dev.txt        # pytest, httpx
  tests/
    test_custom_llm_server.py # /chat/completions SSE contract + /health (no agora deps)
web/
  src/services/api.test.ts        # getConfig/startAgent/stopAgent request+response shapes
  src/lib/conversation.test.ts    # transcript normalization + visualizer mapping
.github/workflows/ci.yml      # python matrix job + bun web job
```

## Test Coverage Detail

### `server/tests/conftest.py`
- A fixture that sets fake env (`AGORA_APP_ID`/`AGORA_APP_CERTIFICATE` = 32-char hex, `CUSTOM_LLM_URL` = a non-localhost https URL, `CUSTOM_LLM_API_KEY`, `CUSTOM_LLM_MODEL`) before importing `server`.
- A `client` fixture: import `server`, swap `server.agent` for a `FakeAgent` (mirrors `scripts/run_fake_server.py`), return `fastapi.testclient.TestClient(server.app)`.
- A `FakeAgent` with async `start(...)`/`stop(...)` returning the documented shapes.

### `server/tests/test_agent.py` (cloud mocked)
- `Agent()` raises `ValueError` when any required env var is missing: `AGORA_APP_ID`, `AGORA_APP_CERTIFICATE`, `CUSTOM_LLM_URL`, `CUSTOM_LLM_API_KEY` (each asserted independently).
- With all env set, `Agent()` constructs without network.
- `start()` wiring: monkeypatch the agent's session creation so no cloud call happens; assert the LLM vendor is built as `CustomLLM` with `base_url=CUSTOM_LLM_URL`, `api_key`, `model`, and that `start()` returns `{"agent_id", "channel_name", "status": "started"}`. (Approach: patch `AgoraAgent.create_async_session` / the returned session's `start` to a stub capturing the configured agent; assert on the built config.)
- `stop()` calls the active session's `stop()`, and falls back to `client.stop_agent()` when the session is unknown — both with the SDK mocked.

### `server/tests/test_server.py` (TestClient + FakeAgent)
- `GET /get_config`: returns `{code:0, msg:"success", data:{app_id, token, uid, channel_name, agent_uid}}`; `token` is a non-empty locally-signed string; `uid=0`/missing is remapped to a concrete non-zero uid.
- `POST /startAgent {channelName, rtcUid, userUid}`: calls `agent.start` with those args; returns `{code:0, msg, data:{agent_id, channel_name, status}}`.
- `POST /stopAgent {agentId}`: returns `{code:0, msg:"success"}`.
- Error mapping: a `FakeAgent` raising `ValueError` → HTTP 400; `RuntimeError` → 500; the `{code,msg}` envelope is preserved. `agent=None` (misconfigured) → 500 on each route.

### `llm/tests/test_custom_llm_server.py` (pure FastAPI, zero agora deps)
- `POST /chat/completions` (streaming): asserts 200 + `content-type: text/event-stream`; the stream opens with a `delta.role="assistant"` chunk, contains content deltas, closes the choice with `finish_reason:"stop"`, and terminates with `data: [DONE]`.
- Non-streaming (`stream:false`) → HTTP 400.
- `GET /health` → `{"status":"ok", ...}`.
- (Uses `TestClient` streaming; no `CUSTOM_LLM_PORT` binding needed.)

### `web/src/services/api.test.ts` (`bun test`)
- Mock `fetch`; assert `getConfig()` GETs the right path and parses `data`; `startAgent()` POSTs `{channelName, rtcUid, userUid}` and returns `data`; `stopAgent()` POSTs `{agentId}`. Error responses surface as thrown/returned errors per the client's contract.

### `web/src/lib/conversation.test.ts` (`bun test`)
- `normalizeTranscript`: a transcript with `uid "0"` is remapped to the agent uid; ordering/dedup behavior as implemented.
- Visualizer state mapping: pure-function input → expected output.

## CI (`.github/workflows/ci.yml`)

Two jobs, triggered on `push` and `pull_request`:

- **`backend`** — `strategy.matrix.os: [ubuntu-latest, macos-latest, windows-latest]`, `python-version: ["3.10", "3.13"]`. Steps: checkout → `actions/setup-python` → for each of `server` and `llm`: `pip install -r requirements.txt -r requirements-dev.txt` → `pytest tests`. (Installs from each package dir so the two suites stay independent.)
- **`web`** — `oven-sh/setup-bun` → `bun install` → `cd web && bun test`. Runs on `ubuntu-latest` (the web units are platform-agnostic; a single OS is sufficient and keeps CI fast).

`fail-fast: false` so one cell failing still reports the others.

## Doc updates (Python floor 3.8 → 3.10)

Update every Python-version mention to **3.10+**: root `README.md` (prereqs), `server/README.md` ("Requirements"), and any `AGENTS.md` mention. Add a one-line CI/badge pointer in the README ("tested on Linux/macOS/Windows × Python 3.10 & 3.13"). No change to `requirements.txt` pins (lower bounds stay; the floor is enforced by docs + CI).

## Testability touch-ups (minimal)

The code is already test-friendly. Only add what tests need, mirroring existing patterns:
- Tests import `server` after setting env and swap `server.agent` (no code change — `run_fake_server.py` already proves this works).
- For `test_agent.py`, the agent-build assertions rely on monkeypatching the SDK at the seam already present (`create_async_session` / `session.start`). If a clean seam doesn't exist, the fallback is to assert on `Agent.start`'s observable result + the env-driven attributes (`custom_llm_url/api_key/model`) rather than introspecting SDK internals — **no production refactor**.

## Portability to `recipe-agent-custom-llm-tts`

The same layout + CI port directly. Only two files differ in the tts repo: `llm/tests/test_custom_llm_server.py` asserts the **audio** SSE contract (transcript chunk + base64 PCM `data` + `[DONE]`, no `finish_reason:"stop"`), and `server/tests/test_agent.py` asserts `output_modalities=["audio"]` plus the **inert TTS** (`.with_tts()` present). Everything else (server routes, conftest, web tests, CI, doc bump) is identical.

## Testing / Verification (of this work)

- `cd server && pip install -r requirements.txt -r requirements-dev.txt && pytest tests` passes.
- `cd llm && pip install -r requirements.txt -r requirements-dev.txt && pytest tests` passes.
- `cd web && bun test` passes.
- CI green across all matrix cells on a draft PR.
- The existing `bun run verify:local` still passes (no regression from doc/test additions).

## Risks / Notes

- **`AgentSession.start()` seam:** the cleanest mock point is `agora_agent.agentkit.Agent.create_async_session` (returns a session whose `start()` we stub). Confirmed present in the SDK. If its surface differs, fall back to result-level assertions (above) — no production change either way.
- **Windows + token generation:** `generate_convo_ai_token` is pure Python (no OS-specific calls), so `/get_config` tests run identically on Windows.
- **`bun test` on Windows:** the web job runs on ubuntu only, sidestepping any Bun-on-Windows quirks; the Python matrix carries the cross-OS guarantee.
- **3.10/3.13 only:** 3.8/3.9 are intentionally dropped (doc floor raised to 3.10) so all users get the modern fastapi/pydantic stack.
