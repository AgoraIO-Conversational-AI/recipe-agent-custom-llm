# Audio Modalities Recipe

Return audio directly from your LLM endpoint — bypassing Agora's TTS entirely. Use this when you have your own voice synthesis, pre-recorded audio, or any custom audio source.

## Run

```bash
ngrok http 8001                       # Terminal 1: get public URL
bun run setup:audio-modalities        # Terminal 2: one-time setup
# Edit audio-modalities/.env.local    # paste Agora creds + ngrok URL
bun run dev:audio-modalities          # start all services
```

Open http://localhost:3000 → Start Conversation → speak.
You'll hear a generated tone (the mock audio) as the response.

## .env.local

```bash
AGORA_APP_ID=your_app_id
AGORA_APP_CERTIFICATE=your_app_certificate
AUDIO_LLM_URL=https://xxxx.ngrok-free.app/audio/chat/completions
```

## The Contract

Your server implements `POST /audio/chat/completions`:

**Request:**
```json
{"model":"audio-mock","messages":[{"role":"user","content":"Hello"}],"stream":true,"modalities":["text","audio"]}
```

**Response (SSE) — two parts:**

1. Transcript (for UI display):
```
data: {"id":"x","choices":[{"index":0,"delta":{"audio":{"id":"audio123","transcript":"Hello there!"}},"finish_reason":null}]}
```

2. Audio chunks (base64-encoded PCM16, 16kHz):
```
data: {"id":"x","choices":[{"index":0,"delta":{"audio":{"id":"audio123","data":"BASE64_PCM_DATA"}},"finish_reason":null}]}
data: {"id":"x","choices":[{"index":0,"delta":{"audio":{"id":"audio123","data":"BASE64_PCM_DATA"}},"finish_reason":null}]}
...
data: [DONE]
```

**Audio format:** PCM16, 16kHz, mono. Chunks are typically 40ms (1280 bytes each).

## Key Difference from Custom LLM

| | Custom LLM | Audio Modalities |
|-|-----------|-----------------|
| Response format | `delta.content` (text) | `delta.audio` (transcript + PCM) |
| TTS | Agora cloud runs TTS on your text | **No TTS** — your audio goes direct |
| Agent config | `OpenAI(base_url=...)` | `OpenAI(base_url=..., output_modalities=["audio"])` |
| Use case | Custom text generation | Custom voice/audio generation |

## Files

| File | Role |
|------|------|
| `src/audio_llm_server.py` | **Your audio endpoint** — modify `generate_mock_pcm_audio()` |
| `src/agent.py` | Configures agent with `output_modalities=["audio"]` |
| `src/server.py` | Agent lifecycle (start/stop), token generation |

## Replacing the Mock

Edit `generate_mock_pcm_audio()` in `audio_llm_server.py`:

```python
# Example: read from a WAV/PCM file
async with aiofiles.open("response.pcm", "rb") as f:
    audio_data = await f.read()

# Example: call your own TTS
audio_data = await my_tts_model.synthesize(text="Hello there!")

# Example: stream from a database of pre-recorded responses
audio_data = await db.get_audio_response(intent="greeting")
```

Audio must be: **PCM16, 16kHz, mono** (raw bytes, no WAV header).

Convert with ffmpeg: `ffmpeg -i input.mp3 -ar 16000 -ac 1 -f s16le output.pcm`
