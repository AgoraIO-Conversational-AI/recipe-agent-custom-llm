"""
Audio Modalities LLM Server — Mock Implementation

This server demonstrates how to implement an audio modalities endpoint
for Agora Conversational AI Engine. Instead of returning text that gets
sent to a separate TTS service, this endpoint returns audio directly —
bypassing TTS entirely.

The response format includes:
1. A text transcript (for display in the UI)
2. Raw PCM audio chunks (streamed as base64-encoded SSE)

Use cases:
- Pre-recorded audio responses (IVR, announcements)
- Custom TTS with your own voice model
- Audio from any source (database, file, generated)

This mock generates a simple sine wave tone as demo audio.
Replace with your actual audio source in production.
"""
import asyncio
import base64
import json
import logging
import math
import os
import struct
import uuid
from typing import Dict, List, Optional, Union

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_base_dir, ".env.local"), override=True)
load_dotenv(os.path.join(_base_dir, ".env"), override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Audio Modalities LLM Server (Mock)",
    description="Demonstrates audio output modality for Agora Conversational AI Engine.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request Models ---

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
    audio: Optional[Dict[str, str]] = None


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[Union[SystemMessage, UserMessage, AssistantMessage]]
    modalities: List[str] = ["text", "audio"]
    audio: Optional[Dict[str, str]] = None
    stream: bool = True
    stream_options: Optional[Dict] = None


# =============================================================================
# Mock Audio Generation
# =============================================================================
# Replace this with your actual audio source:
# - Read from a file (PCM, WAV)
# - Call your own TTS model
# - Query a database of pre-recorded responses
# - Generate with a local voice synthesis model
# =============================================================================

SAMPLE_RATE = 16000  # 16kHz
CHUNK_DURATION_MS = 40  # 40ms per chunk
BYTES_PER_SAMPLE = 2  # PCM16
CHUNK_SIZE = int(SAMPLE_RATE * BYTES_PER_SAMPLE * CHUNK_DURATION_MS / 1000)  # 1280 bytes

# File paths (relative to where the server runs from)
_src_dir = os.path.dirname(os.path.abspath(__file__))
PCM_FILE = os.path.join(_src_dir, "file.pcm")
TEXT_FILE = os.path.join(_src_dir, "file.txt")


def load_transcript() -> str:
    """Load the text transcript from file."""
    try:
        with open(TEXT_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "This is a mock audio response from the audio modalities server."


def load_audio_chunks() -> List[bytes]:
    """Load PCM file and split into streaming chunks."""
    try:
        with open(PCM_FILE, "rb") as f:
            data = f.read()
        return [data[i:i + CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)]
    except FileNotFoundError:
        logger.warning(f"PCM file not found: {PCM_FILE}, generating sine wave fallback")
        return split_into_chunks(generate_fallback_audio())


def generate_fallback_audio(duration_seconds: float = 2.0, frequency: float = 440.0) -> bytes:
    """Fallback: generate a sine wave if no PCM file is available."""
    num_samples = int(SAMPLE_RATE * duration_seconds)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        envelope = min(1.0, i / (SAMPLE_RATE * 0.05)) * min(1.0, (num_samples - i) / (SAMPLE_RATE * 0.05))
        value = int(16000 * envelope * math.sin(2 * math.pi * frequency * t))
        samples.append(struct.pack("<h", max(-32768, min(32767, value))))
    return b"".join(samples)


def split_into_chunks(audio_data: bytes) -> List[bytes]:
    """Split PCM audio into chunks for streaming."""
    return [audio_data[i:i + CHUNK_SIZE] for i in range(0, len(audio_data), CHUNK_SIZE)]


# =============================================================================
# SSE Response — Audio Modalities Format
# =============================================================================
# Agora ConvoAI expects:
# 1. First chunk: transcript + audio_id
# 2. Subsequent chunks: base64-encoded PCM audio data with same audio_id
# 3. Final: "data: [DONE]"
#
# Key difference from text-only custom LLM:
# - Response uses delta.audio instead of delta.content
# - Audio bypasses TTS — your audio goes directly to the user
# =============================================================================

@app.post("/audio/chat/completions")
async def audio_chat_completions(
    request: ChatCompletionRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Audio modalities chat completions endpoint.

    Returns streaming audio response that bypasses TTS.
    Agora cloud sends the audio directly to the user via RTC.
    """
    logger.info(f"Received audio request: model={request.model}, modalities={request.modalities}")

    if not request.stream:
        raise HTTPException(status_code=400, detail="Only streaming mode is supported.")

    # Load transcript and audio from files
    transcript = load_transcript()
    chunks = load_audio_chunks()

    audio_id = uuid.uuid4().hex
    message_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    async def generate():
        # Step 1: Send transcript with audio_id
        transcript_msg = {
            "id": message_id,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "audio": {
                            "id": audio_id,
                            "transcript": transcript,
                        },
                    },
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(transcript_msg)}\n\n"

        # Step 2: Stream audio chunks as base64
        for chunk in chunks:
            audio_msg = {
                "id": message_id,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "audio": {
                                "id": audio_id,
                                "data": base64.b64encode(chunk).decode("utf-8"),
                            },
                        },
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(audio_msg)}\n\n"
            await asyncio.sleep(0.04)  # ~real-time pacing (40ms per chunk)

        # Step 3: Done
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "audio-modalities-mock"}


if __name__ == "__main__":
    port = int(os.getenv("AUDIO_LLM_PORT", "8001"))
    logger.info(f"Starting Audio Modalities LLM Server (Mock) on port {port}")
    logger.info(f"Endpoint: http://0.0.0.0:{port}/audio/chat/completions")
    logger.info("Returns generated tone audio — no external dependencies needed.")
    uvicorn.run(app, host="0.0.0.0", port=port)
