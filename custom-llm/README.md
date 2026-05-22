# Custom LLM Recipe

Bring your own LLM to Agora's voice AI pipeline. This mock server demonstrates the interface — no LLM API keys needed.

## Run

```bash
ngrok http 8001                  # Terminal 1: get public URL
bun run setup:custom-llm         # Terminal 2: one-time setup
# Edit custom-llm/.env.local     # paste Agora creds + ngrok URL
bun run dev:custom-llm           # start all services
```

Open http://localhost:3000 → Start Conversation → speak.

## .env.local

```bash
AGORA_APP_ID=your_app_id
AGORA_APP_CERTIFICATE=your_app_certificate
CUSTOM_LLM_URL=https://xxxx.ngrok-free.app/chat/completions
```

## The Contract

Your server implements `POST /chat/completions` (OpenAI streaming format):

**Request:**
```json
{"model":"mock","messages":[{"role":"user","content":"Hello"}],"stream":true}
```

**Response (SSE):**
```
data: {"id":"x","object":"chat.completion.chunk","created":0,"model":"mock","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}
data: {"id":"x","object":"chat.completion.chunk","created":0,"model":"mock","choices":[{"index":0,"delta":{"content":"Hi!"},"finish_reason":null}]}
data: {"id":"x","object":"chat.completion.chunk","created":0,"model":"mock","choices":[{"index":0,"delta":{"content":""},"finish_reason":"stop"}]}
data: [DONE]
```

## Files

| File | Role |
|------|------|
| `src/custom_llm_server.py` | **Your LLM endpoint** — modify `get_mock_response()` |
| `src/agent.py` | Configures agent to call your endpoint via `OpenAI(base_url=...)` |
| `src/server.py` | Agent lifecycle (start/stop), token generation |

## Replacing the Mock

Edit `get_mock_response()` in `custom_llm_server.py`. Examples:
- Call Ollama: `httpx.post("http://localhost:11434/v1/chat/completions", ...)`
- Add RAG: inject retrieved context into messages before forwarding
- Route models: use a small model for simple queries, large for complex

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Cannot connect to host localhost:8001` | ngrok not running or URL not in .env.local |
| `POST / 404` | Missing `/chat/completions` in CUSTOM_LLM_URL |
| Proxy errors on stopAgent | `unset http_proxy https_proxy` before running |
