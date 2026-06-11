# Custom LLM Recipe — Standalone Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone, multi-platform test suite to the custom-llm recipe — pytest for `server/` + `llm/`, `bun test` for `web/` — plus GitHub Actions CI across `{ubuntu, macos, windows} × Python {3.10, 3.13}`.

**Architecture:** These are **characterization/regression tests for existing, working code** — not TDD red-green. Each test is written to **pass against the current code**; a failure indicates a real bug to surface, not an expected red phase. The one cloud-facing call (`AgoraAgent.create_async_session`) is monkeypatched; everything else runs for real (FastAPI `TestClient`, the mock LLM endpoint, pure web functions).

**Tech Stack:** pytest + httpx (FastAPI `TestClient`); `bun test`; GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-06-10-custom-llm-tests-design.md`

**Repo & branch:** `recipe-agent-custom-llm` (local folder `/Users/zhangqianze/Documents/agent-recipes-python`), branch `test/add-suite` (already created off `main`).

---

## Conventions

- Conventional Commits, lowercase after prefix, present tense, NO AI attribution / NO `Co-Authored-By`, no `--no-verify`. If a commit fails on identity, prefix with `git -c user.email="qianze.zhang@hotmail.com"`.
- The repo's existing venvs are reused for local runs: `server/venv` and `llm/venv` (created by `bun run setup`). If absent, create with `python3 -m venv venv` in that dir and `pip install -r requirements.txt`.
- "Run" steps show the exact command + expected output. These tests should **pass**; investigate any failure as a real finding.

---

## Task 1: Server test scaffolding (`requirements-dev.txt` + `conftest.py`)

**Files:**
- Create: `server/requirements-dev.txt`
- Create: `server/tests/conftest.py`
- Create: `server/tests/__init__.py` (empty, so the dir is importable)

- [ ] **Step 1: Create `server/requirements-dev.txt`**

```
pytest>=7.4
httpx>=0.24
```

- [ ] **Step 2: Create empty `server/tests/__init__.py`** (0 bytes)

```python
```

- [ ] **Step 3: Create `server/tests/conftest.py`**

```python
"""Shared fixtures for the server test suite.

These tests are standalone: no Agora cloud, no ngrok, no real credentials.
A deterministic fake environment is injected, and `python-dotenv` is neutralized
so a developer's real `server/.env.local` cannot override the test env (server.py
loads it with override=True).
"""
import importlib
import os
import sys

import pytest

# Make `import server` / `import agent` resolve to server/src/*.
_SERVER_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SERVER_SRC not in sys.path:
    sys.path.insert(0, _SERVER_SRC)

FAKE_ENV = {
    "AGORA_APP_ID": "0123456789abcdef0123456789abcdef",
    "AGORA_APP_CERTIFICATE": "fedcba9876543210fedcba9876543210",
    "CUSTOM_LLM_URL": "https://example.ngrok-free.dev/chat/completions",
    "CUSTOM_LLM_API_KEY": "test-key",
    "CUSTOM_LLM_MODEL": "test-model",
}


@pytest.fixture
def fake_env(monkeypatch):
    """Inject a deterministic env and stop dotenv from clobbering it."""
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    for key, value in FAKE_ENV.items():
        monkeypatch.setenv(key, value)
    return dict(FAKE_ENV)


class FakeAgent:
    """Stand-in for the real Agent (mirrors scripts/run_fake_server.py)."""

    def __init__(self):
        self.started = []
        self.stopped = []

    async def start(self, channel_name, agent_uid, user_uid, output_audio_codec=None):
        self.started.append((channel_name, agent_uid, user_uid, output_audio_codec))
        return {
            "agent_id": f"fake-agent-{agent_uid}",
            "channel_name": channel_name,
            "status": "started",
        }

    async def stop(self, agent_id):
        self.stopped.append(agent_id)


@pytest.fixture
def server_module(fake_env):
    """Import server.py fresh, with the fake env + neutralized dotenv applied."""
    sys.modules.pop("server", None)
    sys.modules.pop("agent", None)
    import server

    importlib.reload(server)
    return server


@pytest.fixture
def client(server_module):
    """A FastAPI TestClient whose agent is a FakeAgent (no cloud)."""
    from fastapi.testclient import TestClient

    fake = FakeAgent()
    server_module.agent = fake
    test_client = TestClient(server_module.app)
    test_client.fake_agent = fake
    return test_client
```

- [ ] **Step 4: Install dev deps into the server venv**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python/server
venv/bin/python -m pip install -q -r requirements-dev.txt
```
Expected: installs `pytest`/`httpx` (or "already satisfied"), no error.

- [ ] **Step 5: Smoke the harness with a throwaway check, then remove it**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python/server
venv/bin/python -c "import sys; sys.path.insert(0,'src'); import os
os.environ.update({'AGORA_APP_ID':'0'*32,'AGORA_APP_CERTIFICATE':'f'*32,'CUSTOM_LLM_URL':'https://x/chat/completions','CUSTOM_LLM_API_KEY':'k','CUSTOM_LLM_MODEL':'m'})
import server; print('server imports; agent is', 'set' if server.agent else 'None')"
```
Expected: `server imports; agent is set` (confirms env + import path work).

- [ ] **Step 6: Commit**

```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
git add server/requirements-dev.txt server/tests/__init__.py server/tests/conftest.py
git commit -m "test(server): add pytest scaffolding (dev deps + conftest fixtures)"
```

---

## Task 2: Server route tests (`test_server.py`)

**Files:**
- Create: `server/tests/test_server.py`

- [ ] **Step 1: Write the tests**

```python
"""FastAPI route tests via TestClient + FakeAgent (no Agora cloud)."""


def test_get_config_returns_envelope_and_token(client):
    response = client.get("/get_config")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["msg"] == "success"
    data = body["data"]
    assert data["app_id"] == "0123456789abcdef0123456789abcdef"
    assert isinstance(data["token"], str) and len(data["token"]) > 0
    assert data["uid"] and data["uid"] != "0"
    assert data["channel_name"].startswith("custom-llm-")
    assert data["agent_uid"]


def test_get_config_remaps_zero_uid_and_honors_channel(client):
    response = client.get("/get_config", params={"uid": 0, "channel": "test-channel"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["uid"] != "0"
    assert data["channel_name"] == "test-channel"


def test_start_agent_calls_agent_and_returns_shape(client):
    response = client.post(
        "/startAgent",
        json={"channelName": "ch", "rtcUid": 111, "userUid": 222},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"] == {
        "agent_id": "fake-agent-111",
        "channel_name": "ch",
        "status": "started",
    }
    assert client.fake_agent.started == [("ch", 111, 222, None)]


def test_start_agent_forwards_output_audio_codec(client):
    client.post(
        "/startAgent",
        json={
            "channelName": "ch",
            "rtcUid": 111,
            "userUid": 222,
            "parameters": {"output_audio_codec": "opus"},
        },
    )
    assert client.fake_agent.started[-1] == ("ch", 111, 222, "opus")


def test_stop_agent(client):
    response = client.post("/stopAgent", json={"agentId": "fake-agent-111"})
    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert client.fake_agent.stopped == ["fake-agent-111"]


def test_value_error_maps_to_400(client, server_module):
    class BadAgent:
        async def start(self, **kwargs):
            raise ValueError("bad input")

        async def stop(self, *args):
            pass

    server_module.agent = BadAgent()
    response = client.post(
        "/startAgent", json={"channelName": "c", "rtcUid": 1, "userUid": 2}
    )
    assert response.status_code == 400
    assert "bad input" in response.json()["detail"]


def test_runtime_error_maps_to_500(client, server_module):
    class BoomAgent:
        async def start(self, **kwargs):
            raise RuntimeError("explode")

        async def stop(self, *args):
            pass

    server_module.agent = BoomAgent()
    response = client.post(
        "/startAgent", json={"channelName": "c", "rtcUid": 1, "userUid": 2}
    )
    assert response.status_code == 500


def test_misconfigured_agent_returns_500(client, server_module):
    server_module.agent = None
    assert client.get("/get_config").status_code == 500
    assert (
        client.post(
            "/startAgent", json={"channelName": "c", "rtcUid": 1, "userUid": 2}
        ).status_code
        == 500
    )
    assert client.post("/stopAgent", json={"agentId": "x"}).status_code == 500
```

- [ ] **Step 2: Run the tests**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python/server
venv/bin/python -m pytest tests/test_server.py -v
```
Expected: all tests PASS. (If `test_get_config_returns_envelope_and_token` fails on token generation, that is a real finding about `generate_convo_ai_token` with the fake creds — report it.)

- [ ] **Step 3: Commit**

```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
git add server/tests/test_server.py
git commit -m "test(server): cover get_config/startAgent/stopAgent routes and error mapping"
```

---

## Task 3: Agent wiring + validation tests (`test_agent.py`)

**Files:**
- Create: `server/tests/test_agent.py`

- [ ] **Step 1: Write the tests**

```python
"""Agent env validation + CustomLLM wiring (SDK session monkeypatched, no cloud)."""
import asyncio
import os
import sys

import pytest


def _fresh_agent_module():
    sys.modules.pop("agent", None)
    import agent

    return agent


@pytest.mark.parametrize(
    "missing",
    ["AGORA_APP_ID", "AGORA_APP_CERTIFICATE", "CUSTOM_LLM_URL", "CUSTOM_LLM_API_KEY"],
)
def test_agent_requires_env(fake_env, monkeypatch, missing):
    monkeypatch.delenv(missing, raising=False)
    agent = _fresh_agent_module()
    with pytest.raises(ValueError):
        agent.Agent()


def test_agent_constructs_with_full_env(fake_env):
    agent = _fresh_agent_module()
    instance = agent.Agent()
    assert instance.custom_llm_url == os.environ["CUSTOM_LLM_URL"]
    assert instance.custom_llm_model == os.environ["CUSTOM_LLM_MODEL"]


def test_start_wires_custom_llm_and_returns_shape(fake_env, monkeypatch):
    agent = _fresh_agent_module()
    captured = {}

    class FakeSession:
        async def start(self):
            return "test-agent-id"

        async def stop(self):
            captured["stopped"] = True

    def fake_create_async_session(self, **kwargs):
        # `self` is the fully-built AgoraAgent; capture its resolved LLM config.
        captured["llm"] = self.llm
        captured["channel"] = kwargs.get("channel")
        captured["remote_uids"] = kwargs.get("remote_uids")
        return FakeSession()

    from agora_agent.agentkit import Agent as AgoraAgent

    monkeypatch.setattr(AgoraAgent, "create_async_session", fake_create_async_session)

    instance = agent.Agent()
    result = asyncio.run(instance.start(channel_name="ch", agent_uid=111, user_uid=222))

    assert result == {
        "agent_id": "test-agent-id",
        "channel_name": "ch",
        "status": "started",
    }
    # The LLM stage is a CustomLLM pointed at our endpoint.
    assert captured["llm"]["url"] == os.environ["CUSTOM_LLM_URL"]
    assert captured["llm"]["vendor"] == "custom"
    assert captured["channel"] == "ch"
    assert captured["remote_uids"] == ["222"]


def test_start_validates_arguments(fake_env, monkeypatch):
    agent = _fresh_agent_module()
    from agora_agent.agentkit import Agent as AgoraAgent

    monkeypatch.setattr(
        AgoraAgent, "create_async_session", lambda self, **k: None
    )
    instance = agent.Agent()
    with pytest.raises(ValueError):
        asyncio.run(instance.start(channel_name="", agent_uid=1, user_uid=2))
    with pytest.raises(ValueError):
        asyncio.run(instance.start(channel_name="c", agent_uid=0, user_uid=2))


def test_stop_uses_active_session_then_falls_back(fake_env, monkeypatch):
    agent = _fresh_agent_module()

    class FakeSession:
        def __init__(self):
            self.stopped = False

        async def start(self):
            return "agent-xyz"

        async def stop(self):
            self.stopped = True

    session = FakeSession()
    from agora_agent.agentkit import Agent as AgoraAgent

    monkeypatch.setattr(
        AgoraAgent, "create_async_session", lambda self, **k: session
    )
    instance = agent.Agent()

    # Make the stateless fallback observable.
    fallback_calls = []

    async def fake_stop_agent(agent_id):
        fallback_calls.append(agent_id)

    monkeypatch.setattr(instance.client, "stop_agent", fake_stop_agent)

    asyncio.run(instance.start(channel_name="ch", agent_uid=111, user_uid=222))
    asyncio.run(instance.stop("agent-xyz"))
    assert session.stopped is True
    assert fallback_calls == []  # active session handled it

    # Unknown id -> stateless fallback.
    asyncio.run(instance.stop("unknown-id"))
    assert fallback_calls == ["unknown-id"]
```

- [ ] **Step 2: Run the tests**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python/server
venv/bin/python -m pytest tests/test_agent.py -v
```
Expected: all PASS. (`captured["llm"]["url"]`/`["vendor"]` assert the real `CustomLLM.to_config()` shape — verified present in the SDK: `AgoraAgent.llm` is a public property returning the vendor config with `vendor: "custom"`.)

- [ ] **Step 3: Run the whole server suite**

Run: `cd /Users/zhangqianze/Documents/agent-recipes-python/server && venv/bin/python -m pytest tests -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
git add server/tests/test_agent.py
git commit -m "test(server): cover Agent env validation, CustomLLM wiring, and stop fallback"
```

---

## Task 4: LLM endpoint tests (`llm/tests`)

**Files:**
- Create: `llm/requirements-dev.txt`
- Create: `llm/tests/__init__.py` (empty)
- Create: `llm/tests/conftest.py`
- Create: `llm/tests/test_custom_llm_server.py`

- [ ] **Step 1: Create `llm/requirements-dev.txt`**

```
pytest>=7.4
httpx>=0.24
```

- [ ] **Step 2: Create empty `llm/tests/__init__.py`** (0 bytes)

```python
```

- [ ] **Step 3: Create `llm/tests/conftest.py`**

```python
import os
import sys

_LLM_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _LLM_SRC not in sys.path:
    sys.path.insert(0, _LLM_SRC)
```

- [ ] **Step 4: Create `llm/tests/test_custom_llm_server.py`**

```python
"""Contract tests for the mock custom LLM endpoint (no Agora deps, no network)."""
import pytest
from fastapi.testclient import TestClient

import custom_llm_server


@pytest.fixture
def client():
    return TestClient(custom_llm_server.app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_streaming_sse_contract(client):
    response = client.post(
        "/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert '"role": "assistant"' in body or '"role":"assistant"' in body
    assert '"finish_reason": "stop"' in body or '"finish_reason":"stop"' in body
    assert body.rstrip().endswith("data: [DONE]")


def test_non_streaming_rejected(client):
    response = client.post(
        "/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        },
    )
    assert response.status_code == 400
```

- [ ] **Step 5: Install dev deps + run**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python/llm
venv/bin/python -m pip install -q -r requirements-dev.txt
venv/bin/python -m pytest tests -v
```
Expected: 3 tests PASS. (The mock streams ~30 words at 50 ms each, so the streaming test takes ~1.5 s — normal.)

- [ ] **Step 6: Commit**

```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
git add llm/requirements-dev.txt llm/tests/__init__.py llm/tests/conftest.py llm/tests/test_custom_llm_server.py
git commit -m "test(llm): cover the /chat/completions SSE contract and health endpoint"
```

---

## Task 5: Web unit tests (`bun test`)

**Files:**
- Create: `web/src/services/api.test.ts`
- Create: `web/src/lib/conversation.test.ts`

- [ ] **Step 1: Create `web/src/services/api.test.ts`**

```ts
import { afterEach, expect, test } from 'bun:test'

import { getConfig, startAgent, stopAgent } from './api'

const originalFetch = globalThis.fetch
let lastCall: { url: string; init?: RequestInit }

afterEach(() => {
  globalThis.fetch = originalFetch
})

function mockFetch(status: number, body: unknown) {
  globalThis.fetch = (async (url: string | URL, init?: RequestInit) => {
    lastCall = { url: String(url), init }
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'content-type': 'application/json' },
    })
  }) as typeof fetch
}

test('getConfig hits /api/get_config with query and returns data', async () => {
  mockFetch(200, {
    code: 0,
    msg: 'success',
    data: { app_id: 'a', token: 't', uid: '5', channel_name: 'c', agent_uid: '9' },
  })
  const data = await getConfig({ channel: 'c', uid: 5 })
  expect(data.token).toBe('t')
  expect(lastCall.url).toContain('/api/get_config')
  expect(lastCall.url).toContain('channel=c')
  expect(lastCall.url).toContain('uid=5')
})

test('startAgent posts the payload and returns agent_id', async () => {
  mockFetch(200, { code: 0, msg: 'success', data: { agent_id: 'agent-1' } })
  const id = await startAgent('ch', 111, 222)
  expect(id).toBe('agent-1')
  expect(lastCall.url).toContain('/api/startAgent')
  expect(lastCall.init?.method).toBe('POST')
  expect(JSON.parse(String(lastCall.init?.body))).toEqual({
    channelName: 'ch',
    rtcUid: 111,
    userUid: 222,
  })
})

test('stopAgent posts the agentId', async () => {
  mockFetch(200, {})
  await stopAgent('agent-1')
  expect(lastCall.url).toContain('/api/stopAgent')
  expect(JSON.parse(String(lastCall.init?.body))).toEqual({ agentId: 'agent-1' })
})

test('getConfig throws on an error response', async () => {
  mockFetch(500, { detail: 'boom' })
  await expect(getConfig()).rejects.toThrow('boom')
})
```

- [ ] **Step 2: Create `web/src/lib/conversation.test.ts`**

```ts
import { expect, test } from 'bun:test'

import { normalizeTranscript, normalizeTranscriptSpacing } from './conversation'

test('normalizeTranscriptSpacing inserts spaces and collapses whitespace', () => {
  expect(normalizeTranscriptSpacing('Hello.World,now  ok')).toBe('Hello. World, now ok')
})

test("normalizeTranscript remaps uid '0' to the local uid and normalizes text", () => {
  const out = normalizeTranscript(
    [
      { uid: '0', text: 'Hi.There', turn_id: '1', status: 0 },
      { uid: '42', text: 'ok', turn_id: '2', status: 0 },
      // biome-ignore lint/suspicious/noExplicitAny: minimal test fixtures
    ] as any,
    'local-9',
  )
  expect(out[0].uid).toBe('local-9')
  expect(out[0].text).toBe('Hi. There')
  expect(out[1].uid).toBe('42')
})
```

- [ ] **Step 3: Run the web tests**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python/web
bun install
bun test
```
Expected: all tests PASS (6 across the two files). `bun test` auto-discovers `*.test.ts` only, so the `verify-*.ts` scripts are not run.

- [ ] **Step 4: Commit**

```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
git add web/src/services/api.test.ts web/src/lib/conversation.test.ts
git commit -m "test(web): cover the api client and transcript normalization helpers"
```

---

## Task 6: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  backend:
    name: backend (py${{ matrix.python-version }} / ${{ matrix.os }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.10", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: server tests
        working-directory: server
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt -r requirements-dev.txt
          pytest tests -v
      - name: llm tests
        working-directory: llm
        run: |
          pip install -r requirements.txt -r requirements-dev.txt
          pytest tests -v

  web:
    name: web (bun)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - run: bun install
      - run: bun test
        working-directory: web
```

- [ ] **Step 2: Validate the YAML locally**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('ci.yml OK')"
```
Expected: `ci.yml OK`. (If PyYAML is unavailable, skip — GitHub will validate on push.)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run pytest matrix (ubuntu/macos/windows x py3.10,3.13) and bun web tests"
```

---

## Task 7: Bump documented Python floor 3.8 → 3.10

**Files:**
- Modify: `README.md` (the only doc that mentions `3.8` — verified: `server/README.md` and `AGENTS.md` carry no Python-version mention)

- [ ] **Step 1: Replace the Python floor in `README.md`**

Change the prerequisite line (`README.md:14`):
```
- [Python 3.8+](https://www.python.org/)
```
to:
```
- [Python 3.10+](https://www.python.org/)
```

- [ ] **Step 2: Add a CI/tests note to `README.md`**

In `README.md`, immediately **after** the closing ``` of the fenced block under `## Commands`, add this paragraph:
```markdown

Tests run standalone (no Agora cloud needed): `pytest` in `server/` and `llm/`, `bun test` in `web/`. CI runs them on Linux/macOS/Windows × Python 3.10 & 3.13.
```

- [ ] **Step 3: Confirm no `3.8` remains and commit**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
grep -rn "3\.8" README.md && echo "STILL HAS 3.8 (fix it)" || echo "(no 3.8 left — good)"
git add README.md
git commit -m "docs: raise documented Python floor to 3.10 and note the test suite"
```

---

## Task 8: Full local run + regression check

**Files:** none (runs everything).

- [ ] **Step 1: Run the complete Python suite**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python/server && venv/bin/python -m pytest tests -v
cd /Users/zhangqianze/Documents/agent-recipes-python/llm && venv/bin/python -m pytest tests -v
```
Expected: all PASS in both.

- [ ] **Step 2: Run the web tests**

Run: `cd /Users/zhangqianze/Documents/agent-recipes-python/web && bun test`
Expected: all PASS.

- [ ] **Step 3: Confirm no regression to the existing verify gate**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
NO_PROXY=127.0.0.1,localhost,::1 no_proxy=127.0.0.1,localhost,::1 bun run verify:backend
```
Expected: exit 0 (the new test files don't affect `py_compile`). The new `*.test.ts` files are ignored by `verify:web:*` (those target specific scripts), and `bun test` is separate.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "test: pass full local suite" || echo "nothing to commit"
```

---

## Task 9: Push + open PR

**Files:** none (git only).

- [ ] **Step 1: Push the branch**

```bash
cd /Users/zhangqianze/Documents/agent-recipes-python
git push -u origin test/add-suite
```

- [ ] **Step 2: Open the PR** (REST — the GraphQL `gh pr create` path 401s under the lapsed SSO session)

```bash
REPO=AgoraIO-Conversational-AI/recipe-agent-custom-llm
gh api -X POST "repos/$REPO/pulls" \
  -f title="test: add standalone multi-platform test suite + CI" \
  -f head="test/add-suite" \
  -f base="main" \
  -f body="Adds pytest tests for server/ (agent wiring + FastAPI routes, cloud mocked) and llm/ (SSE contract), bun tests for web/ (api client + transcript helpers), and GitHub Actions CI across {ubuntu,macos,windows} x Python {3.10,3.13} + a bun web job. Standalone: no Agora cloud, ngrok, or creds. Also raises the documented Python floor to 3.10. Verified locally: pytest + bun test all pass." \
  --jq '{number, url: .html_url, state}'
```
Expected: a JSON object with the new PR number + URL.

---

## Self-Review notes (for the implementer)

- **These tests must pass against existing code.** A failure is a real finding (e.g. token generation with fake creds, or the `CustomLLM` config shape) — surface it, don't paper over it.
- **The mock seam** is `agora_agent.agentkit.Agent.create_async_session` (patched per-test). The captured `self.llm` is the real `CustomLLM.to_config()` (`vendor: "custom"`, `url: <CUSTOM_LLM_URL>`) — verified present in the installed SDK.
- **dotenv neutralization** in `conftest.py` is load-bearing: without it, a developer's real `server/.env.local` (loaded with `override=True`) would clobber the deterministic test env and make `test_get_config_*` non-reproducible.
- **Portability:** this whole plan re-applies to `recipe-agent-custom-llm-tts` with two file swaps — `llm/tests/test_custom_llm_server.py` asserts the audio contract (transcript + base64 `data` + `[DONE]`, no `finish_reason`), and `server/tests/test_agent.py` additionally asserts `captured["llm"]["output_modalities"] == ["audio"]` and that an (inert) TTS is configured.
```