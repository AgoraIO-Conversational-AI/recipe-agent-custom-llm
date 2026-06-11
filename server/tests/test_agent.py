"""Agent env validation + CustomLLM wiring (SDK session monkeypatched, no cloud)."""
import asyncio
import os
import sys

import pytest


def _fresh_agent_module():
    sys.modules.pop("agent", None)
    import agent

    return agent


@pytest.mark.parametrize(
    "missing",
    ["AGORA_APP_ID", "AGORA_APP_CERTIFICATE", "CUSTOM_LLM_URL", "CUSTOM_LLM_API_KEY"],
)
def test_agent_requires_env(fake_env, monkeypatch, missing):
    monkeypatch.delenv(missing, raising=False)
    agent = _fresh_agent_module()
    with pytest.raises(ValueError):
        agent.Agent()


def test_agent_constructs_with_full_env(fake_env):
    agent = _fresh_agent_module()
    instance = agent.Agent()
    assert instance.custom_llm_url == os.environ["CUSTOM_LLM_URL"]
    assert instance.custom_llm_model == os.environ["CUSTOM_LLM_MODEL"]


def test_start_wires_custom_llm_and_returns_shape(fake_env, monkeypatch):
    agent = _fresh_agent_module()
    captured = {}

    class FakeSession:
        async def start(self):
            return "test-agent-id"

        async def stop(self):
            captured["stopped"] = True

    def fake_create_async_session(self, **kwargs):
        # `self` is the fully-built AgoraAgent; capture its resolved LLM config.
        captured["llm"] = self.llm
        captured["channel"] = kwargs.get("channel")
        captured["remote_uids"] = kwargs.get("remote_uids")
        return FakeSession()

    from agora_agent.agentkit import Agent as AgoraAgent

    monkeypatch.setattr(AgoraAgent, "create_async_session", fake_create_async_session)

    instance = agent.Agent()
    result = asyncio.run(instance.start(channel_name="ch", agent_uid=111, user_uid=222))

    assert result == {
        "agent_id": "test-agent-id",
        "channel_name": "ch",
        "status": "started",
    }
    # The LLM stage is a CustomLLM pointed at our endpoint.
    assert captured["llm"]["url"] == os.environ["CUSTOM_LLM_URL"]
    assert captured["llm"]["vendor"] == "custom"
    assert captured["channel"] == "ch"
    assert captured["remote_uids"] == ["222"]


def test_start_validates_arguments(fake_env, monkeypatch):
    agent = _fresh_agent_module()
    from agora_agent.agentkit import Agent as AgoraAgent

    monkeypatch.setattr(
        AgoraAgent, "create_async_session", lambda self, **k: None
    )
    instance = agent.Agent()
    with pytest.raises(ValueError):
        asyncio.run(instance.start(channel_name="", agent_uid=1, user_uid=2))
    with pytest.raises(ValueError):
        asyncio.run(instance.start(channel_name="c", agent_uid=0, user_uid=2))


def test_stop_uses_active_session_then_falls_back(fake_env, monkeypatch):
    agent = _fresh_agent_module()

    class FakeSession:
        def __init__(self):
            self.stopped = False

        async def start(self):
            return "agent-xyz"

        async def stop(self):
            self.stopped = True

    session = FakeSession()
    from agora_agent.agentkit import Agent as AgoraAgent

    monkeypatch.setattr(
        AgoraAgent, "create_async_session", lambda self, **k: session
    )
    instance = agent.Agent()

    # Make the stateless fallback observable.
    fallback_calls = []

    async def fake_stop_agent(agent_id):
        fallback_calls.append(agent_id)

    monkeypatch.setattr(instance.client, "stop_agent", fake_stop_agent)

    asyncio.run(instance.start(channel_name="ch", agent_uid=111, user_uid=222))
    asyncio.run(instance.stop("agent-xyz"))
    assert session.stopped is True
    assert fallback_calls == []  # active session handled it

    # Unknown id -> stateless fallback.
    asyncio.run(instance.stop("unknown-id"))
    assert fallback_calls == ["unknown-id"]
