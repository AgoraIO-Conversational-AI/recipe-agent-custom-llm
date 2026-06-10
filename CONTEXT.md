# Context — agent-recipes-python (Custom LLM recipe)

A glossary of the domain language for this repository. Implementation details do not belong here.

## Terms

### Agent backend
The Python FastAPI service in `server/` (port 8000). Owns Agora token generation
and agent session lifecycle (start/stop). The browser reaches it through the
Next.js `/api/*` rewrite proxy. It is **not** the thing the LLM runs in.

### Custom LLM endpoint
The Python FastAPI service in `llm/` (port 8001). An OpenAI-compatible
`POST /chat/completions` server that Agora cloud calls directly. Must be
**publicly reachable** (via a tunnel such as ngrok) because Agora cloud — not
the browser and not the agent backend — is the caller. This is the component a
developer replaces with their own model. Has no `agora-agents` dependency.
The mock does not authenticate; a production endpoint is expected to validate
the `Authorization: Bearer` credential that Agora cloud forwards.

### CustomLLM vendor
The `agora_agent.agentkit.vendors.CustomLLM` SDK vendor used by the **agent
backend** to point the agent's LLM stage at the **custom LLM endpoint**. It
emits a wire config with `vendor: "custom"` and requires both `base_url` and
`api_key`. Distinct from the managed `OpenAI` vendor used by the base quickstart.

### Recipe
A single, self-contained variation of the base Agora Conversational AI
quickstart that demonstrates one capability. This repository contains exactly
one recipe — **custom-llm** — and declares `Recipe Role: custom-llm` (the base
quickstart declares `Recipe Role: base`).

### Managed pipeline
The Agora-managed STT and TTS stages (Deepgram STT, MiniMax TTS) that stay
unchanged from the base quickstart. Only the LLM stage is customized in this
recipe.
