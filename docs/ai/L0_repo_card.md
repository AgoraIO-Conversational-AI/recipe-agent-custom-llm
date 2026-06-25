# recipe-agent-custom-llm — Repo Card

> Next.js web client + Python FastAPI backend for an Agora Conversational AI voice agent wired to a bring-your-own OpenAI-compatible LLM endpoint. STT (Deepgram) and TTS (MiniMax) remain Agora-managed. Ships a zero-key mock LLM so the full pipeline runs immediately without a model API key.

## Identity

| Field          | Value                                                                        |
| -------------- | ---------------------------------------------------------------------------- |
| Repo           | `AgoraIO-Conversational-AI/recipe-agent-custom-llm`                          |
| Type           | `distributed-system` (single repo, two co-located processes + public tunnel) |
| Language       | Python 3.10+ (FastAPI + uvicorn) backend + Next.js 16 / React 19 web         |
| Deploy Target  | `web/` as Next.js app, `server/` as a publicly reachable FastAPI service     |
| Owner          | Agora Conversational AI DevEx                                                |
| Last Reviewed  | 2026-06-25                                                                   |
| Recipe Role    | `base`                                                                       |
| Recipe Version | `1.0.0`                                                                      |
| Recipe Status  | `experimental`                                                               |

## L1 — Summaries

The Audience column helps agents prioritise: **Use** = consuming the recipe's behavior, **Maintain** = modifying internals.

| File                                     | Purpose                                                                              | Audience       |
| ---------------------------------------- | ------------------------------------------------------------------------------------ | -------------- |
| [01_setup](L1/01_setup.md)               | bun + venv setup, env vars (incl. `CUSTOM_LLM_URL` public tunnel), commands          | Use & Maintain |
| [02_architecture](L1/02_architecture.md) | One-process two-concern topology, tunnel requirement, cascading STT/LLM/TTS pipeline | Maintain       |
| [03_code_map](L1/03_code_map.md)         | `web/` and `server/` trees with key file responsibilities, including `llm.py`        | Maintain       |
| [04_conventions](L1/04_conventions.md)   | Python async + FastAPI patterns, `llm.py` isolation rule, Biome, JSON envelope       | Maintain       |
| [05_workflows](L1/05_workflows.md)       | Add a route, swap the mock LLM, change STT/TTS, adjust VAD, verify, deploy           | Use            |
| [06_interfaces](L1/06_interfaces.md)     | FastAPI route contracts, rewrites, env vars, `CustomLLM` vendor config, LLM SSE      | Use & Maintain |
| [07_gotchas](L1/07_gotchas.md)           | Public-URL requirement, `PORT` in env, `agora_agent` in `llm.py`, camelCase fields   | Maintain       |
| [08_security](L1/08_security.md)         | Token007, App Certificate server-only, public `/llm` surface, CORS, auth header      | Maintain       |

## Recipe Profile

This repo declares `Recipe Role: base`. See [RECIPE.md](RECIPE.md) for extension points, invariants, and stable contracts before changing reusable surfaces.
