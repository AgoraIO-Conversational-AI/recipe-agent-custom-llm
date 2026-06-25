# 01 · Setup

> Install dependencies, configure env, expose the backend publicly, and run the custom-llm recipe locally. This recipe is **zero-key** for the LLM stage: a mock endpoint ships with the repo. Agora credentials are still required.

## Prerequisites

- Python 3.10+ (backend runs on 3.10 and 3.13 in CI)
- [Bun](https://bun.sh/) (runs the web app and orchestration scripts)
- [ngrok](https://ngrok.com/) (or any public tunnel — required because Agora cloud calls `/llm` directly)
- [Agora CLI](https://github.com/AgoraIO/cli) (optional; easiest way to mint App ID + Certificate)

## Install

```bash
bun run setup            # installs web deps + creates server/ venv from requirements.txt
```

`setup` runs `setup:env` (copies `server/.env.example` → `server/.env.local` if missing), `setup:server` (recreates `server/venv`, installs `requirements.txt`), and `setup:web` (`bun install`).

## Configure env

Backend env file is `server/.env.local` (template: `server/.env.example`).

| Variable                | Required | Default                                               | Notes                                                  |
| ----------------------- | :------: | ----------------------------------------------------- | ------------------------------------------------------ |
| `AGORA_APP_ID`          |    ✅    | —                                                     | Agora Console → Project → App ID                       |
| `AGORA_APP_CERTIFICATE` |    ✅    | —                                                     | Agora Console → Project → App Certificate              |
| `CUSTOM_LLM_URL`        |    ✅    | —                                                     | **Public** URL for `POST /chat/completions`; Agora cloud calls it — cannot be `localhost` |
| `CUSTOM_LLM_API_KEY`    |    ✅    | `any-key-here`                                        | Forwarded as `Authorization: Bearer`; required by `CustomLLM` vendor |
| `CUSTOM_LLM_MODEL`      |          | `mock-model`                                          | Model name passed to your endpoint                     |
| `AGENT_GREETING`        |          | built-in line                                         | Optional opening utterance override                    |

Fill Agora credentials via the CLI or by hand:

```bash
agora login
agora project use <your-project>
agora project env write server/.env.local   # writes App ID + Certificate
# then add CUSTOM_LLM_URL and CUSTOM_LLM_API_KEY to server/.env.local
```

> Do **not** add `PORT` to `server/.env.example` — see [07_gotchas](07_gotchas.md).

## Expose the backend publicly

Agora cloud calls your `/llm/chat/completions` endpoint. For local dev you must expose port 8000 publicly before starting the agent:

```bash
ngrok http 8000
# copy the printed https URL, e.g. https://abc123.ngrok-free.dev
# set CUSTOM_LLM_URL=https://abc123.ngrok-free.dev/llm/chat/completions in server/.env.local
```

## Run

```bash
bun run dev              # backend (:8000, serves /llm) + web (:3000) via concurrently
```

Open <http://localhost:3000> → **Start Conversation** → speak. The mock LLM cycles through pre-set responses; replace `get_mock_response()` in `server/src/llm.py` to use a real model.

## Quick commands

```bash
bun run doctor           # shared prereqs (bun + node_modules); no creds needed
bun run doctor:local     # + .env.local + AGORA_APP_ID/CERTIFICATE + CUSTOM_LLM_URL checks
bun run verify           # web-only gate (doctor + api contracts + web build)
bun run verify:local     # full local gate: backend compile + fastapi smoke + llm smoke + proxy + web build
bun run clean            # remove venvs and build artifacts
```

Backend unit tests run standalone (no cloud, no creds):

```bash
cd server && pytest tests -v
```

## Related Deep Dives

- None. For what each verify command asserts see [05_workflows](05_workflows.md) and [06_interfaces](06_interfaces.md).
