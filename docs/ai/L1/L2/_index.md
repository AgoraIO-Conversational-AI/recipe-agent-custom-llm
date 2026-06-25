# Deep Dives Index

| Document                                          | Summary                                                                         | Load When                                                             |
| ------------------------------------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| [custom_llm_config.md](custom_llm_config.md)      | Full `CustomLLM` vendor build, STT/TTS vendors, VAD config, and session options | Changing the LLM endpoint, STT, TTS, VAD, greeting, or codec          |
| [session_lifecycle.md](session_lifecycle.md)      | Browser orchestration of get_config + start/stop, RTC/RTM, transcript           | Touching client-side join, token renewal, or mid-call control          |
| [llm_endpoint_contract.md](llm_endpoint_contract.md) | OpenAI SSE contract, request model, mock structure, and replacement guide    | Replacing or extending the mock `/chat/completions` endpoint           |
