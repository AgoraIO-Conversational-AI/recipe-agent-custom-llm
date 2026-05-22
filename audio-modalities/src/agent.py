"""
Agent — Audio Modalities Recipe

Configures the Agora agent to use audio output modalities.
The LLM endpoint returns audio directly (bypassing TTS).
"""
import logging
import os
import time
from typing import Any, Dict, Optional

from agora_agent import Area, AsyncAgora
from agora_agent.agentkit import Agent as AgoraAgent
from agora_agent.agentkit.vendors import DeepgramSTT, OpenAI

logger = logging.getLogger("uvicorn.error")

AUDIO_AGENT_PROMPT = """You are a helpful AI assistant that responds with audio. \
Keep responses brief and conversational."""


class Agent:
    """
    Agora Conversational AI Agent with Audio Modalities output.

    Key difference: The LLM is configured with output_modalities=["audio"],
    which tells Agora cloud that the LLM response contains audio data
    directly — no separate TTS step is needed.
    """

    def __init__(self):
        self.app_id = os.getenv("AGORA_APP_ID")
        self.app_certificate = os.getenv("AGORA_APP_CERTIFICATE")
        self.greeting = os.getenv("AGENT_GREETING", "")

        # Audio modalities LLM endpoint
        self.audio_llm_url = os.getenv(
            "AUDIO_LLM_URL",
            "http://localhost:8001/audio/chat/completions",
        )
        self.audio_llm_api_key = os.getenv("AUDIO_LLM_API_KEY", "any-key-here")
        self.audio_llm_model = os.getenv("AUDIO_LLM_MODEL", "audio-mock")

        if not self.app_id or not self.app_certificate:
            raise ValueError("AGORA_APP_ID and AGORA_APP_CERTIFICATE are required")

        self.client = AsyncAgora(
            area=Area.US,
            app_id=self.app_id,
            app_certificate=self.app_certificate,
        )
        self._sessions: Dict[str, Any] = {}

    async def start(
        self,
        channel_name: str,
        agent_uid: int,
        user_uid: int,
        output_audio_codec: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start agent with audio modalities output."""
        if not channel_name or not str(channel_name).strip():
            raise ValueError("channel_name is required and cannot be empty")
        if agent_uid <= 0:
            raise ValueError("agent_uid is required and cannot be empty")
        if user_uid <= 0:
            raise ValueError("user_uid is required and cannot be empty")

        name = f"agent_{channel_name}_{agent_uid}_{int(time.time())}"

        # ============================================================
        # KEY DIFFERENCE: output_modalities=["audio"]
        # ============================================================
        # This tells Agora cloud that the LLM returns audio directly.
        # No TTS is used — the audio from your server goes straight
        # to the user via RTC.
        # ============================================================
        llm = OpenAI(
            base_url=self.audio_llm_url,
            api_key=self.audio_llm_api_key,
            model=self.audio_llm_model,
            output_modalities=["audio"],
            greeting_message=self.greeting if self.greeting else None,
            failure_message="Please wait a moment.",
            max_history=10,
        )

        # STT still needed (to transcribe user speech → text for LLM input)
        stt = DeepgramSTT(model="nova-3", language="en")

        # No TTS — audio comes directly from the LLM endpoint

        parameters = {
            "data_channel": "rtm",
            "enable_error_message": True,
            "enable_metrics": True,
        }
        if isinstance(output_audio_codec, str) and output_audio_codec.strip():
            parameters["output_audio_codec"] = output_audio_codec.strip()

        agora_agent = AgoraAgent(
            name=name,
            instructions=AUDIO_AGENT_PROMPT,
            greeting=self.greeting if self.greeting else None,
            failure_message="Please wait a moment.",
            max_history=50,
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
            advanced_features={"enable_rtm": True},
            parameters=parameters,
        )

        agora_agent = (
            agora_agent
            .with_stt(stt)
            .with_llm(llm)
            # No .with_tts() — audio modalities bypasses TTS
        )

        session = agora_agent.create_async_session(
            client=self.client,
            channel=channel_name,
            agent_uid=str(agent_uid),
            remote_uids=[str(user_uid)],
            enable_string_uid=False,
            idle_timeout=30,
            expires_in=3600,
        )

        logger.info(
            "Starting Audio Modalities agent channel=%s agent_uid=%s user_uid=%s",
            channel_name, agent_uid, user_uid,
        )

        try:
            agent_id = await session.start()
        except Exception:
            logger.exception("Failed to start Audio Modalities agent")
            raise

        self._sessions[agent_id] = session
        logger.info("Started Audio Modalities agent agent_id=%s", agent_id)

        return {"agent_id": agent_id, "channel_name": channel_name, "status": "started"}

    async def stop(self, agent_id: str) -> None:
        """Stop a running agent."""
        if not agent_id or not str(agent_id).strip():
            raise ValueError("agent_id is required and cannot be empty")

        session = self._sessions.pop(agent_id, None)
        if session:
            try:
                await session.stop()
                logger.info("Stopped agent agent_id=%s", agent_id)
                return
            except Exception:
                logger.warning("Session stop failed, falling back agent_id=%s", agent_id, exc_info=True)

        await self.client.stop_agent(agent_id)
