from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_mock_provider(chunks=None):
    mock_provider = MagicMock()
    mock_provider.stream.return_value = iter(chunks or ["Test", " response"])
    return mock_provider


def _make_mock_config():
    cfg = MagicMock()
    cfg.provider = "anthropic"
    cfg.model = "claude-haiku-test"
    return cfg


@pytest.fixture
def api_client():
    """
    Yield (TestClient, mock_provider) with lifespan running inside the patches.
    A fresh client is created for each test function.
    """
    mock_provider = _make_mock_provider()
    mock_config = _make_mock_config()

    # Import the module fresh inside the patch context so lifespan picks up mocks
    import importlib
    import src.coach.api.app as api_app_module
    importlib.reload(api_app_module)

    with (
        patch.object(api_app_module, "get_provider", return_value=mock_provider),
        patch.object(api_app_module, "config_from_env", return_value=mock_config),
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "read_text", return_value="# System Prompt"),
    ):
        with TestClient(api_app_module.app) as client:
            yield client, mock_provider


def test_health_returns_200(api_client):
    client, _ = api_client
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["provider"] == "anthropic"
    assert "model" in data
    assert "uptime_seconds" in data


def test_chat_returns_response(api_client):
    client, mock_provider = api_client
    mock_provider.stream.return_value = iter(["Hello coach!"])

    resp = client.post("/chat", json={"session_id": "s1", "message": "squat done"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "s1"
    assert "Hello coach!" in data["response"]


def test_chat_accumulates_history(api_client):
    client, mock_provider = api_client
    mock_provider.stream.side_effect = [iter(["resp1"]), iter(["resp2"])]

    client.post("/chat", json={"session_id": "hist_session", "message": "first message"})
    client.post("/chat", json={"session_id": "hist_session", "message": "second message"})

    assert mock_provider.stream.call_count == 2
    second_call_history = mock_provider.stream.call_args_list[1][1]["messages"]
    # user1 + assistant1 + user2 = 3 messages
    assert len(second_call_history) >= 3


def test_different_sessions_are_isolated(api_client):
    client, mock_provider = api_client
    mock_provider.stream.side_effect = [iter(["resp_a"]), iter(["resp_b"])]

    client.post("/chat", json={"session_id": "alice", "message": "hello"})
    client.post("/chat", json={"session_id": "bob", "message": "hi"})

    alice_history = mock_provider.stream.call_args_list[0][1]["messages"]
    bob_history = mock_provider.stream.call_args_list[1][1]["messages"]
    assert len(alice_history) == 1
    assert len(bob_history) == 1


def test_streaming_returns_event_stream(api_client):
    client, mock_provider = api_client
    mock_provider.stream.return_value = iter(["chunk1", "chunk2"])

    with client.stream(
        "POST", "/chat",
        json={"session_id": "stream_s", "message": "bench", "stream": True}
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = resp.read().decode()

    assert "data: chunk1" in body
    assert "data: chunk2" in body


def test_streaming_ends_with_done(api_client):
    client, mock_provider = api_client
    mock_provider.stream.return_value = iter(["final chunk"])

    with client.stream(
        "POST", "/chat",
        json={"session_id": "done_s", "message": "test", "stream": True}
    ) as resp:
        body = resp.read().decode()

    assert "data: [DONE]" in body


def test_missing_session_id_returns_422(api_client):
    client, _ = api_client
    resp = client.post("/chat", json={"message": "no session"})
    assert resp.status_code == 422
