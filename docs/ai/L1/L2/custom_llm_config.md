# Deep Dive — Custom LLM Config

> **When to Read This:** You are changing the LLM endpoint URL, STT or TTS vendor, VAD turn detection, greeting, audio codec, or any other agent session option. For the high-level picture, start at [02_architecture](../02_architecture.md).

This recipe uses the SDK's cascading vendor pipeline: `DeepgramSTT → CustomLLM → MiniMaxTTS`, wired via `.with_stt().with_llm().with_tts()`. All vendor construction lives in `Agent.start()` (`server/src/agent.py`).

## The `CustomLLM` vendor

```python
llm = CustomLLM(
    base_url=self.custom_llm_url,       # CUSTOM_LLM_URL — must be public
    api_key=self.custom_llm_api_key,    # CUSTOM_LLM_API_KEY — required by SDK
    model=self.custom_llm_model,        # CUSTOM_LLM_MODEL, default "mock-model"
    greeting_message=self.greeting,     # AGENT_GREETING or built-in
    failure_message="Please wait a moment.",
    max_history=15,
    max_tokens=1024,
    temperature=0.7,
    top_p=0.95,
)
```

`CustomLLM` stamps `vendor: "custom"` in the wire config and requires both `base_url` and `api_key`. The SDK rejects one without the other (`ValueError` at `Agent.__init__`). `test_agent.py` asserts `captured["llm"]["vendor"] == "custom"` and `captured["llm"]["url"] == CUSTOM_LLM_URL`.

## STT vendor (`DeepgramSTT`)

```python
stt = DeepgramSTT(model="nova-3", language="en")
```

Deepgram is the managed STT stage — Agora cloud handles the API key. Do not set a Deepgram API key in this recipe's env.

## TTS vendor (`MiniMaxTTS`)

```python
tts = MiniMaxTTS(model="speech_2_6_turbo", voice_id="English_captivating_female1")
```

MiniMax is the managed TTS stage — also Agora-managed, no local API key needed.

## Turn detection (VAD on `AgoraAgent`)

`turn_detection` is set directly on `AgoraAgent(...)`, not on a vendor (contrast with the realtime recipe):

```python
turn_detection={
    "config": {
        "speech_threshold": 0.5,
        "start_of_speech": {
            "mode": "vad",
            "vad_config": {
                "interrupt_duration_ms": 160,
                "prefix_padding_ms": 300,
            },
        },
        "end_of_speech": {
            "mode": "vad",
            "vad_config": {
                "silence_duration_ms": 480,
            },
        },
    },
},
```

To tune responsiveness, adjust `interrupt_duration_ms` (how long agent speech is interrupted), `prefix_padding_ms` (pre-speech buffer), or `silence_duration_ms` (end-of-turn pause).

## How the session is assembled

```python
agora_agent = AgoraAgent(
    client=self.client,
    instructions=CUSTOM_LLM_PROMPT,
    greeting=self.greeting,
    failure_message="Please wait a moment.",
    max_history=50,
    turn_detection={...},               # VAD config (see above)
    advanced_features={"enable_rtm": True, "enable_tools": True},
    parameters=parameters,
)
agora_agent = agora_agent.with_stt(stt).with_llm(llm).with_tts(tts)
session = agora_agent.create_async_session(
    channel=channel_name,
    agent_uid=str(agent_uid),
    remote_uids=[str(user_uid)],
    enable_string_uid=False,
    idle_timeout=30,
    expires_in=3600,
)
agent_id = await session.start()
```

## Session `parameters`

Set in `Agent.start()` and passed to `AgoraAgent`:

| Key                    | Value    | Why                                              |
| ---------------------- | -------- | ------------------------------------------------ |
| `audio_scenario`       | `chorus` | Ultra-low-latency profile for web clients.       |
| `data_channel`         | `rtm`    | Transcript + metrics delivered over RTM.         |
| `enable_error_message` | `true`   | Surface agent-side errors to the client.         |
| `enable_metrics`       | `true`   | Emit pipeline metrics to the UI.                 |
| `output_audio_codec`   | optional | Forwarded from `POST /startAgent` `parameters`.  |

## `enable_tools: true` in `advanced_features`

`enable_tools: True` is set even in the mock. The custom endpoint receives the `tools` and `tool_choice` fields in the request body (see `ChatCompletionRequest` in `llm.py`). A production endpoint can implement tool calling without changing `agent.py`.

## Related L1

- [02_architecture](../02_architecture.md) · [06_interfaces](../06_interfaces.md) · [07_gotchas](../07_gotchas.md)
