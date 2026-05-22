# Agora Conversational AI — Python Recipes

A collection of recipes demonstrating advanced features of Agora's Conversational AI Engine. Each recipe is a self-contained server with a shared web frontend for testing.

## Recipes

| Recipe | Description | Key Concept |
|--------|-------------|-------------|
| [**custom-llm**](./custom-llm/) | Bring your own LLM endpoint | `POST /chat/completions` — OpenAI-compatible streaming |
| [**audio-modalities**](./audio-modalities/) | Return audio directly from LLM (bypass TTS) | `POST /audio/chat/completions` — PCM audio streaming |

## Quick Start

```bash
# 1. Install web dependencies
bun install

# 2. Pick a recipe and set it up
bun run setup:custom-llm        # or: bun run setup:audio-modalities

# 3. Expose the recipe's LLM server to the internet
ngrok http 8001

# 4. Configure (edit the .env.local in the recipe folder)
#    Paste your Agora credentials + ngrok URL

# 5. Run
bun run dev:custom-llm           # or: bun run dev:audio-modalities
```

Open [http://localhost:3000](http://localhost:3000) → Start Conversation → speak.

## Architecture (shared across recipes)

```
Browser (localhost:3000)
  ↓
Next.js /api/* rewrites
  ↓
Agent Backend (localhost:8000)     ← recipe-specific: configures agent
  ↓
Agora ConvoAI Cloud
  ↓
Your Recipe Server (localhost:8001) ← recipe-specific: implements the feature
  ↑
ngrok tunnel (public URL)
```

Each recipe has:
- A **feature server** (port 8001) — the endpoint Agora cloud calls
- An **agent backend** (port 8000) — configures the agent to use your feature server
- The shared **web frontend** (port 3000) — for testing in the browser

## Project Structure

```
agent-recipes-python/
├── custom-llm/                 # Recipe: Custom LLM
│   ├── src/
│   │   ├── custom_llm_server.py   # Your LLM endpoint
│   │   ├── agent.py               # Agent config
│   │   └── server.py              # Agent lifecycle API
│   ├── .env.example
│   └── requirements.txt
├── audio-modalities/           # Recipe: Audio Output Modalities
│   ├── src/
│   │   ├── audio_llm_server.py    # Your audio endpoint
│   │   ├── agent.py               # Agent config (output_modalities=["audio"])
│   │   └── server.py              # Agent lifecycle API
│   ├── .env.example
│   └── requirements.txt
├── web/                        # Shared frontend (all recipes use this)
├── package.json                # Run scripts for each recipe
└── README.md
```

## Prerequisites

- [Python 3.10+](https://www.python.org/)
- [Bun](https://bun.sh/)
- [ngrok](https://ngrok.com/) (or any tunnel to expose localhost)
- Agora App ID + App Certificate

## Commands

| Command | What it does |
|---------|-------------|
| `bun run setup:custom-llm` | Create venv + install deps for custom-llm recipe |
| `bun run setup:audio-modalities` | Create venv + install deps for audio-modalities recipe |
| `bun run dev:custom-llm` | Run custom-llm recipe (3 services) |
| `bun run dev:audio-modalities` | Run audio-modalities recipe (3 services) |
| `bun run build` | Production build of web frontend |
| `bun run clean` | Remove all venvs and build artifacts |

## License

MIT
