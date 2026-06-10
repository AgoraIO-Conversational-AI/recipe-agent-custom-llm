"""
Custom LLM Server — Mock Implementation

This server demonstrates how to implement an OpenAI-compatible Chat Completions
endpoint that works with Agora Conversational AI Engine.

Key points:
- Must implement POST /chat/completions
- Must support streaming responses (Server-Sent Events)
- Must follow OpenAI Chat Completions response format
- Agora cloud sends Authorization header with the api_key you configured

This mock version returns pre-defined responses so you can test the full
voice pipeline (STT → Custom LLM → TTS) without any external LLM dependency.

Replace the mock logic with your own:
- Call your own model (local or remote)
- Add RAG context injection
- Implement tool calling
- Route to different models based on content
"""
import asyncio
import json
import logging
import os
import time
import uuid
from typing import Dict, List, Optional, Union

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Load environment variables.
# override=False so an explicitly-exported value (e.g. CUSTOM_LLM_PORT injected by
# the verify:local:llm harness, or a process manager) takes precedence over a
# checked-in .env.local. In normal `dev` no port is exported, so .env.local wins.
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_base_dir, ".env.local"), override=False)
load_dotenv(os.path.join(_base_dir, ".env"), override=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Custom LLM Server (Mock)",
    description=(
        "OpenAI-compatible Chat Completions endpoint for Agora Conversational AI Engine. "
        "This mock implementation demonstrates the required interface contract."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Request Models — These match what Agora ConvoAI Engine sends
# =============================================================================

class TextContent(BaseModel):
    type: str = "text"
    text: str


class SystemMessage(BaseModel):
    role: str = "system"
    content: Union[str, List[str]]


class UserMessage(BaseModel):
    role: str = "user"
    content: Union[str, List[Union[TextContent, Dict]]]


class AssistantMessage(BaseModel):
    role: str = "assistant"
    content: Union[str, List[TextContent], None] = None
    tool_calls: Optional[List[Dict]] = None


class ToolMessage(BaseModel):
    role: str = "tool"
    content: Union[str, List[str]]
    tool_call_id: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[Union[SystemMessage, UserMessage, AssistantMessage, ToolMessage]]
    stream: bool = True
    stream_options: Optional[Dict] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[List[Dict]] = None
    tool_choice: Optional[Union[str, Dict]] = None
    response_format: Optional[Dict] = None


# =============================================================================
# Mock Response Logic
# =============================================================================
# Replace this section with your actual LLM logic:
# - Call a local model (Ollama, vLLM, etc.)
# - Call a remote API
# - Implement RAG retrieval + generation
# - Add business logic, filtering, routing
# =============================================================================

MOCK_RESPONSES = [
    "I'm a custom LLM running on your own server! This response is coming through Agora's Conversational AI pipeline, from your custom endpoint, through TTS, and into your ears as speech.",
    "This is a mock response demonstrating the custom LLM integration. In production, you'd replace this with calls to your own model or any LLM provider.",
    "Hello! I'm responding from your custom LLM server. The full pipeline is working: your speech was transcribed by STT, sent to me, and my response will be converted to speech by TTS.",
    "Great question! I'm a mock LLM server that demonstrates how to build a custom endpoint compatible with Agora's Conversational AI Engine. You can replace me with any logic you want.",
]

_response_counter = 0


def get_mock_response(messages: list) -> str:
    """
    Generate a mock response based on the conversation.

    In a real implementation, this is where you'd:
    - Extract the user's latest message
    - Query your knowledge base / vector DB
    - Call your own model
    - Apply business logic
    """
    global _response_counter

    # Extract the last user message for logging
    last_user_msg = ""
    for msg in reversed(messages):
        if hasattr(msg, "role") and msg.role == "user":
            content = msg.content
            if isinstance(content, str):
                last_user_msg = content
            elif isinstance(content, list) and len(content) > 0:
                first = content[0]
                if isinstance(first, dict):
                    last_user_msg = first.get("text", "")
                elif hasattr(first, "text"):
                    last_user_msg = first.text
            break

    logger.info(f"User said: {last_user_msg}")

    # Cycle through mock responses
    response = MOCK_RESPONSES[_response_counter % len(MOCK_RESPONSES)]
    _response_counter += 1
    return response


# =============================================================================
# Streaming Response — Must follow OpenAI SSE format exactly
# =============================================================================
# Agora ConvoAI Engine expects:
# 1. Each chunk as "data: {json}\n\n"
# 2. Final "data: [DONE]\n\n"
# 3. Each chunk has: id, object, created, model, choices[{delta, index, finish_reason}]
# =============================================================================

def make_chunk(chunk_id: str, model: str, content: str, finish_reason=None) -> str:
    """Build a single SSE chunk in OpenAI format."""
    chunk = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model or "mock-model",
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(chunk)}\n\n"


def make_role_chunk(chunk_id: str, model: str) -> str:
    """First chunk that sets the assistant role."""
    chunk = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model or "mock-model",
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": ""},
                "finish_reason": None,
            }
        ],
    }
    return f"data: {json.dumps(chunk)}\n\n"


@app.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    OpenAI-compatible chat completions endpoint.

    This is the endpoint that Agora Conversational AI Engine calls.
    It must:
    - Accept the OpenAI Chat Completions request format
    - Return streaming SSE responses in OpenAI chunk format
    - End with "data: [DONE]"
    """
    logger.info(
        f"Received request: model={request.model}, "
        f"messages={len(request.messages)}, stream={request.stream}"
    )

    # Agora ConvoAI always uses streaming
    if not request.stream:
        raise HTTPException(
            status_code=400,
            detail="Only streaming mode is supported. Set stream=true.",
        )

    # Generate mock response
    response_text = get_mock_response(request.messages)
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    model = request.model or "mock-model"

    async def generate():
        """Stream the response word by word to simulate real LLM behavior."""
        # First chunk: role
        yield make_role_chunk(chunk_id, model)

        # Stream content word by word with small delays (simulates token generation)
        words = response_text.split(" ")
        for i, word in enumerate(words):
            token = word if i == 0 else f" {word}"
            yield make_chunk(chunk_id, model, token)
            await asyncio.sleep(0.05)  # 50ms per token, ~realistic speed

        # Final chunk: finish_reason
        yield make_chunk(chunk_id, model, "", finish_reason="stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "service": "custom-llm-mock"}


if __name__ == "__main__":
    port = int(os.getenv("CUSTOM_LLM_PORT", "8001"))
    logger.info(f"Starting Custom LLM Server (Mock) on port {port}")
    logger.info("This server returns mock responses — no LLM API key needed.")
    logger.info(f"Endpoint: http://0.0.0.0:{port}/chat/completions")
    uvicorn.run(app, host="0.0.0.0", port=port)
