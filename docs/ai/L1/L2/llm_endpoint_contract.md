# Deep Dive — LLM Endpoint Contract

> **When to Read This:** You are replacing or extending the mock `/chat/completions` endpoint in `server/src/llm.py` — whether to call a local model, a remote provider, or to add RAG/tool logic. For the architecture context see [02_architecture](../02_architecture.md).

## What Agora sends

Agora ConvoAI sends a POST to `CUSTOM_LLM_URL` (which must end in `/chat/completions`) with:

- `Authorization: Bearer <CUSTOM_LLM_API_KEY>` header.
- A JSON body matching `ChatCompletionRequest` (see `llm.py`):
  - `model` — the value of `CUSTOM_LLM_MODEL`.
  - `messages` — full conversation history as a list of `system`, `user`, `assistant`, and `tool` messages.
  - `stream: true` — always true; reject `false` with 400.
  - `stream_options`, `temperature`, `max_tokens` — forwarded from `CustomLLM` config.
  - `tools`, `tool_choice` — present when `enable_tools: True` (the default in this recipe).

## What you must return

A `StreamingResponse` with `media_type="text/event-stream"`:

1. **First chunk:** role delta — `{"delta": {"role": "assistant", "content": ""}, "finish_reason": null}`.
2. **Content chunks:** one per token or word — `{"delta": {"content": "<text>"}, "finish_reason": null}`.
3. **Final chunk:** `{"delta": {}, "finish_reason": "stop"}`.
4. **Terminator:** `data: [DONE]\n\n`.

Each SSE line: `data: {json}\n\n`. See `make_chunk()` and `make_role_chunk()` in `llm.py` for the exact shape.

## The mock's `get_mock_response()`

```python
def get_mock_response(messages: list) -> str:
    # extracts last user message, logs it, cycles through MOCK_RESPONSES
```

This is the **only function you need to replace** for a real model. Keep everything else (request parsing, `make_chunk`, SSE generation) unless you need to change the streaming behavior.

## Replacement patterns

| Pattern           | What to change in `llm.py`                                               |
| ----------------- | ------------------------------------------------------------------------ |
| Remote API call   | Replace `get_mock_response()` with an `httpx` async call to your provider; stream chunks back as they arrive. |
| Local model (Ollama, vLLM) | Replace `get_mock_response()` with a streaming HTTP call to `localhost`; forward chunks. |
| RAG              | In `get_mock_response()`, extract the user message, retrieve context, inject into the prompt, call your model. |
| Tool calling      | Parse `request.tools`/`request.tool_choice`; emit a tool-call delta chunk when the model requests a tool; handle the `tool` role message on the next turn. |
| Auth validation   | At the top of `chat_completions()`, validate `authorization` header; raise `HTTPException(401)` on mismatch. |

## Running standalone

```bash
cd server
source venv/bin/activate
python src/llm.py   # starts on port 8001 (CUSTOM_LLM_PORT env override)
# test:
curl -X POST http://localhost:8001/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hello"}],"stream":true}'
```

## Verification

```bash
cd server && pytest tests/test_llm.py tests/test_llm_mount.py -v
bun run verify:local:llm   # end-to-end SSE stream through the real mount
```

`test_llm_module_has_no_agora_dependency` (in `test_llm_mount.py`) parses `llm.py` with AST and fails if any `agora_*` package is imported — keep this passing.

## Related L1

- [02_architecture](../02_architecture.md) · [06_interfaces](../06_interfaces.md) · [07_gotchas](../07_gotchas.md)
