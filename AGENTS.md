# Agent Development Guide

For coding agents working in `agent-recipes-python`.

## Structure

```
agent-recipes-python/
├── custom-llm/          # Recipe: Custom LLM text responses
├── audio-modalities/    # Recipe: Audio output (bypass TTS)
├── web/                 # Shared frontend (all recipes)
├── package.json         # Run scripts per recipe
├── README.md            # Index
└── ARCHITECTURE.md      # Shared topology
```

Each recipe is independent: own venv, own .env.local, own server files.
The web frontend is shared — it doesn't know which recipe is running.

## Key Files Per Recipe

| File | Role |
|------|------|
| `src/*_server.py` | The feature endpoint (what Agora cloud calls) |
| `src/agent.py` | Agent configuration (vendor, modalities, etc.) |
| `src/server.py` | FastAPI routes: get_config, startAgent, stopAgent |
| `.env.example` | Template for credentials + public URL |
| `requirements.txt` | Python dependencies |
| `README.md` | Recipe-specific docs |

## Commands

```bash
bun run setup:custom-llm          # setup recipe venv
bun run setup:audio-modalities
bun run dev:custom-llm             # run recipe (3 services)
bun run dev:audio-modalities
bun run build                      # build web
bun run clean                      # nuke everything
```

## Patterns

- Each recipe is self-contained — don't create cross-recipe dependencies.
- Recipe servers run on port 8001; agent backends on port 8000.
- The web frontend connects to port 8000 via Next.js rewrites.
- Mock implementations should work with zero external API keys.
- Keep server.py identical across recipes (copy-paste is fine).
- The interesting code lives in the feature server and agent.py.

## Adding a New Recipe

1. Create `new-recipe/` with `src/`, `.env.example`, `requirements.txt`
2. Implement the feature server (`src/feature_server.py`)
3. Create `src/agent.py` with the relevant vendor config
4. Copy `src/server.py` from an existing recipe (adjust channel prefix)
5. Add `setup:new-recipe` and `dev:new-recipe` scripts to root `package.json`
6. Add a row to the root README table
7. Write a recipe-specific `README.md`

## Anti-Patterns

- Don't merge feature servers into the agent backend
- Don't add shared Python code across recipes — keep them independent
- Don't require external API keys for mock demos
- Don't use localhost in the LLM URL env var for real testing
