# Docs Test Results — recipe-agent-custom-llm

**Date:** 2026-06-25
**Reviewer:** progressive-disclosure-docs workflow

---

## 1. Structural Checks

| Check | Result |
| ----- | ------ |
| `docs/ai/L0_repo_card.md` exists and ≤ 50 lines | PASS (47 lines) |
| All 8 `docs/ai/L1/0[1-8]_*.md` files present | PASS |
| `docs/ai/L1/L2/_index.md` present | PASS |
| `docs/ai/L1/L2/` has at least 1 deep dive | PASS (3 deep dives) |
| `docs/ai/RECIPE.md` present with YAML frontmatter | PASS |
| `AGENTS.md` has `## How to Load` section | PASS |
| `AGENTS.md` has `## Git Conventions` with no AI tool names | PASS |
| `AGENTS.md` has `## Doc Commands` table | PASS |
| `AGENTS.md` stale "docs/ai not present" note removed | PASS |
| `AGENTS.md` Recipe Role corrected to `base` | PASS (was `custom-llm`) |
| `CLAUDE.md` redirects to `@AGENTS.md` (unchanged) | PASS |
| README.md not overwritten | PASS |
| ARCHITECTURE.md not overwritten | PASS |

**Structural: 13/13 PASS**

---

## 2. Relative Link Resolution

Checked all relative links in `docs/ai/**/*.md` and `AGENTS.md`.

| Scope | Links checked | Broken |
| ----- | ------------- | ------ |
| `docs/ai/` | 36 | 0 |
| `AGENTS.md` | 6 | 0 |
| **Total** | **42** | **0** |

**Link resolution: PASS (42/42)**

---

## 3. Backend Tests (pytest in throwaway venv)

Venv: `/tmp/v_custom_llm` (Python 3.14, requirements.txt + requirements-dev.txt)

```
pytest tests -v
======================== 23 passed, 1 warning in 3.89s =========================
```

| Test file | Tests | Result |
| --------- | ----- | ------ |
| `test_agent.py` | 8 | PASS |
| `test_agent_construction.py` | 1 | PASS |
| `test_llm.py` | 3 | PASS |
| `test_llm_mount.py` | 3 | PASS |
| `test_server.py` | 8 | PASS |
| **Total** | **23** | **23 PASS** |

Warning: `starlette.testclient` deprecation (harmless, pre-existing).

Throwaway venv removed after run: `/tmp/v_custom_llm` deleted.

---

## 4. Q&A — Source-Verified

Minimum 12 questions across 5 categories. Each answer verified against source files listed.

### Category A — Setup / Env

**Q1: What four env vars are required to start the agent backend?**
A: `AGORA_APP_ID`, `AGORA_APP_CERTIFICATE`, `CUSTOM_LLM_URL`, `CUSTOM_LLM_API_KEY` — all validated in `Agent.__init__` with `ValueError` if missing.
Source: `server/src/agent.py` lines 60–73. **PASS**

**Q2: Can `CUSTOM_LLM_URL` be set to `localhost`?**
A: No. There is intentionally no localhost default. Agora cloud calls the URL directly; a localhost value causes silent LLM failures. `doctor:local` warns if it sees `localhost`/`127.0.0.1`.
Source: `server/src/agent.py` lines 51–67; `package.json` `doctor:local` script. **PASS**

**Q3: What does `bun run setup:done` print after setup?**
A: A checklist reminding the developer to: (1) write Agora env with CLI, (2) run `ngrok http 8000`, (3) add `CUSTOM_LLM_URL`, (4) run `bun run dev`.
Source: `package.json` `setup:done` script. **PASS**

### Category B — Architecture / Pipeline

**Q4: What is the LLM pipeline for this recipe?**
A: Cascading `DeepgramSTT → CustomLLM → MiniMaxTTS`, wired via `.with_stt().with_llm().with_tts()`. Not a single MLLM.
Source: `server/src/agent.py` lines 164–169. **PASS**

**Q5: Where is `llm.app` mounted in the main FastAPI app?**
A: `app.mount("/llm", llm_app)` in `server/src/server.py` — so Agora cloud reaches it at `<public-url>/llm/chat/completions`.
Source: `server/src/server.py` line 198. **PASS**

**Q6: Why does the backend need a public tunnel for local development?**
A: Agora cloud — not the browser — calls `CUSTOM_LLM_URL`. The backend and its mounted `/llm` endpoint must be publicly reachable. The browser only ever calls `/api/*` through Next rewrites.
Source: `ARCHITECTURE.md` lines 1–5, `server/src/agent.py` docstring. **PASS**

### Category C — Code / Conventions

**Q7: What does `test_llm_module_has_no_agora_dependency` check?**
A: It parses `llm.py` with Python's `ast` module and fails if any imported module root starts with `agora`. Ensures `llm.py` stays provider-agnostic.
Source: `server/tests/test_llm_mount.py` lines 26–48. **PASS**

**Q8: Where is `turn_detection` (VAD) set — on `AgoraAgent` or on `CustomLLM`?**
A: On `AgoraAgent(...)` directly, via the `turn_detection` dict parameter. Not on `CustomLLM`. This is the opposite of the MLLM recipe.
Source: `server/src/agent.py` lines 143–162. **PASS**

**Q9: What does the `Agent.stop()` fallback path do?**
A: If `agent_id` is not in `_sessions` (e.g. after restart), it calls `self.client.stop_agent(agent_id)` (stateless SDK call).
Source: `server/src/agent.py` lines 215–234. **PASS**

### Category D — Interfaces / Contracts

**Q10: What must `POST /llm/chat/completions` return for non-streaming requests?**
A: HTTP 400. The endpoint only supports `stream: true`. The mock raises `HTTPException(status_code=400)`.
Source: `server/src/llm.py` lines 217–220; `test_llm.py` `test_non_streaming_rejected`. **PASS**

**Q11: What is the default value of `CUSTOM_LLM_MODEL` and where is it used?**
A: Default is `"mock-model"`. It is read in `Agent.__init__` and passed to `CustomLLM(model=...)`, then forwarded in the `model` field of each `POST /chat/completions` request body.
Source: `server/src/agent.py` line 58; `server/src/llm.py` `ChatCompletionRequest`. **PASS**

**Q12: What LLM-related verify commands exist beyond `verify:local`?**
A: `bun run verify:local:llm` (spawns real FastAPI with FakeAgent, exercises `/llm/chat/completions` through the mount); `bun run verify:backend` (py_compile on `server.py`, `agent.py`, `llm.py`).
Source: `package.json` `verify:local:llm` and `verify:backend` scripts; `web/scripts/verify-local-llm.ts`. **PASS**

### Category E — Security / Gotchas

**Q13: Does the mock LLM endpoint validate the `Authorization: Bearer` header?**
A: No. The mock accepts any key (or no key) and does not validate. A production replacement should validate it.
Source: `server/src/llm.py` lines 14–16 (docstring) and `chat_completions()` which ignores `authorization`. **PASS**

**Q14: Why must `PORT` not appear in `server/.env.example`?**
A: `verify:local:fastapi` and `verify:local:llm` inject a random `PORT` using `load_dotenv(override=True)`. If `.env.example` has a `PORT` line and it's copied to `.env.local`, it would clobber the injected port and break the smoke tests.
Source: `server/src/server.py` lines 19–20; `web/scripts/verify-local-llm.ts` line 92. **PASS**

---

## 5. Summary Table

| Category | Questions | Pass | Fail |
| -------- | --------- | ---- | ---- |
| A — Setup / Env | 3 | 3 | 0 |
| B — Architecture / Pipeline | 3 | 3 | 0 |
| C — Code / Conventions | 3 | 3 | 0 |
| D — Interfaces / Contracts | 3 | 3 | 0 |
| E — Security / Gotchas | 2 | 2 | 0 |
| **Total** | **14** | **14** | **0** |

**Structural: 13/13 · Links: 42/42 · pytest: 23/23 · Q&A: 14/14**

---

## 6. Fix / Retest

No issues found. All checks pass on first run.
