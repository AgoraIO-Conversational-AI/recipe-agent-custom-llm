"""Contract tests for the mock LLM endpoint in isolation (no Agora, no mount)."""
import pytest
from fastapi.testclient import TestClient

import llm


@pytest.fixture
def llm_client():
    return TestClient(llm.app)


def test_health(llm_client):
    response = llm_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_streaming_sse_contract(llm_client):
    response = llm_client.post(
        "/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert '"role": "assistant"' in body or '"role":"assistant"' in body
    assert '"finish_reason": "stop"' in body or '"finish_reason":"stop"' in body
    assert body.rstrip().endswith("data: [DONE]")


def test_non_streaming_rejected(llm_client):
    response = llm_client.post(
        "/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        },
    )
    assert response.status_code == 400
