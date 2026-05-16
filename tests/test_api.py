from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_FAKE_PROGRAM = {
    "program_id": "test-prog",
    "name": "Test Program",
    "barbell_weight_kg": 20,
    "days": {
        "D1": {"label": "PUSH", "exercises": []},
        "D2": {"label": "PULL", "exercises": []},
    },
    "rest_days": ["D3"],
}


def _make_mock_provider(chunks=None):
    mock_provider = MagicMock()
    mock_provider.stream.return_value = iter(chunks or ["Test", " response"])
    mock_provider.chat.return_value = "".join(chunks or ["Test", " response"])
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

    import importlib
    import src.coach.api.app as api_app_module
    importlib.reload(api_app_module)

    with (
        patch.object(api_app_module, "get_provider", return_value=mock_provider),
        patch.object(api_app_module, "config_from_env", return_value=mock_config),
        patch.object(api_app_module, "load_active_program", return_value=_FAKE_PROGRAM),
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
    mock_provider.chat.return_value = "Hello coach!"

    resp = client.post("/chat", json={"session_id": "s1", "message": "squat done"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "s1"
    assert "Hello coach!" in data["response"]


def test_chat_accumulates_history(api_client):
    client, mock_provider = api_client
    mock_provider.stream.side_effect = [iter(["resp1"]), iter(["resp2"])]
    mock_provider.chat.side_effect = ["resp1", "resp2"]

    client.post("/chat", json={"session_id": "hist_session", "message": "first message"})
    client.post("/chat", json={"session_id": "hist_session", "message": "second message"})

    assert mock_provider.chat.call_count == 2
    second_call_history = mock_provider.chat.call_args_list[1][1]["messages"]
    # user1 + assistant1 + user2 = 3 messages
    assert len(second_call_history) >= 3


def test_different_sessions_are_isolated(api_client):
    client, mock_provider = api_client
    mock_provider.stream.side_effect = [iter(["resp_a"]), iter(["resp_b"])]
    mock_provider.chat.side_effect = ["resp_a", "resp_b"]

    client.post("/chat", json={"session_id": "alice", "message": "hello"})
    client.post("/chat", json={"session_id": "bob", "message": "hi"})

    alice_history = mock_provider.chat.call_args_list[0][1]["messages"]
    bob_history = mock_provider.chat.call_args_list[1][1]["messages"]
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


def test_chat_provider_error_returns_502(api_client):
    client, mock_provider = api_client
    mock_provider.chat.side_effect = Exception("API key invalid")

    resp = client.post("/chat", json={"session_id": "error_s", "message": "test"})
    assert resp.status_code == 502
    assert "unavailable" in resp.json()["detail"].lower()


def test_streaming_provider_error_yields_error_with_id(api_client):
    client, mock_provider = api_client
    mock_provider.stream.side_effect = Exception("Connection lost")

    with client.stream(
        "POST", "/chat",
        json={"session_id": "stream_error", "message": "test", "stream": True}
    ) as resp:
        assert resp.status_code == 200
        body = resp.read().decode()

    assert "data: [ERROR" in body
    assert "]" in body  # Error ID is present


def test_streaming_error_yields_error_marker(api_client):
    """Streaming error should yield error marker with correlation ID."""
    client, mock_provider = api_client
    mock_provider.stream.side_effect = Exception("Stream failed")

    with client.stream(
        "POST", "/chat",
        json={"session_id": "error_marker", "message": "test", "stream": True}
    ) as resp:
        body = resp.read().decode()

    # Verify error marker was yielded with correlation ID
    assert "data: [ERROR" in body
    # Extract the error ID
    import re
    error_match = re.search(r"\[ERROR ([a-f0-9]+)\]", body)
    assert error_match is not None, "Error should include correlation ID"


def test_message_length_cap_enforced(api_client):
    client, _ = api_client
    huge_message = "x" * 40000

    resp = client.post("/chat", json={"session_id": "s", "message": huge_message})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Integration: program snapshot injected into system prompt at startup
# ---------------------------------------------------------------------------

def test_system_prompt_contains_program_snapshot(api_client):
    """Lifespan must inject ## CURRENT PROGRAM SNAPSHOT into the system prompt."""
    client, mock_provider = api_client
    mock_provider.chat.return_value = "ok"

    client.post("/chat", json={"session_id": "snap", "message": "hello"})

    system_prompt_used = mock_provider.chat.call_args.kwargs.get("system", "")
    assert "## CURRENT PROGRAM SNAPSHOT" in system_prompt_used
    assert "D1" in system_prompt_used
    assert "D2" in system_prompt_used


def test_system_prompt_snapshot_consistent_across_requests(api_client):
    """Every request in the same process must use the same system prompt."""
    client, mock_provider = api_client
    mock_provider.chat.side_effect = ["resp1", "resp2", "resp3"]

    for i in range(3):
        client.post("/chat", json={"session_id": f"s{i}", "message": "hi"})

    prompts = [call.kwargs.get("system", "") for call in mock_provider.chat.call_args_list]
    assert len(set(prompts)) == 1, "All requests must use the same system prompt"


def test_app_state_program_set_at_startup(api_client):
    """app.state.program must be populated with the loaded program dict."""
    client, _ = api_client
    resp = client.get("/health")
    assert resp.status_code == 200
    # Access app state directly via the test client's app
    import src.coach.api.app as api_app_module
    assert api_app_module.app.state.program == _FAKE_PROGRAM


# ---------------------------------------------------------------------------
# Integration: CLI REPL loop sequences
# ---------------------------------------------------------------------------

def test_cli_repl_day_then_status_sequence(capsys):
    """Full CLI sequence: /day D1 → /status shows the same day."""
    from pathlib import Path
    from src.coach.cli import CoachCLI

    with patch("src.coach.cli.load_active_program", return_value=_FAKE_PROGRAM), \
         patch("src.coach.cli.get_provider", return_value=MagicMock()), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value="# Base"):
        cli = CoachCLI()
        cli.program = _FAKE_PROGRAM
        cli.system_prompt = "# Base"

    cli._handle_input("/day D1")
    assert cli.current_day == "D1"

    cli._handle_input("/status")
    out = capsys.readouterr().out
    assert "D1" in out
    assert "PUSH" in out


def test_cli_repl_done_clears_day(capsys):
    """/done after /day D1 must clear current_day and save the log."""
    from pathlib import Path
    from src.coach.cli import CoachCLI

    with patch("src.coach.cli.load_active_program", return_value=_FAKE_PROGRAM), \
         patch("src.coach.cli.get_provider", return_value=MagicMock()), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value="# Base"):
        cli = CoachCLI()
        cli.program = _FAKE_PROGRAM
        cli.system_prompt = "# Base"

    cli._handle_input("/day D1")
    assert cli.current_day == "D1"

    with patch("src.coach.cli.SessionLogger") as MockLogger:
        mock_logger = MagicMock()
        MockLogger.return_value = mock_logger
        cli._handle_input("/done")

    assert cli.current_day is None
    mock_logger.save.assert_called_once()


def test_cli_repl_program_switch_updates_snapshot(capsys):
    """/program switch must reload self.program and rebuild system_prompt snapshot."""
    from pathlib import Path
    from src.coach.cli import CoachCLI

    with patch("src.coach.cli.load_active_program", return_value=_FAKE_PROGRAM), \
         patch("src.coach.cli.get_provider", return_value=MagicMock()), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value="# Base"):
        cli = CoachCLI()
        cli.program = _FAKE_PROGRAM
        cli.system_prompt = "# Base\n\n## CURRENT PROGRAM SNAPSHOT\n\nD1 — PUSH"

    new_program = {**_FAKE_PROGRAM, "program_id": "new-prog", "name": "New",
                   "days": {"A": {"label": "LEGS", "exercises": []}}}

    with patch("src.coach.cli.switch_program"), \
         patch("src.coach.cli.load_active_program", return_value=new_program):
        cli._handle_input("/program switch new-prog")

    assert cli.program == new_program
    assert "## CURRENT PROGRAM SNAPSHOT" in cli.system_prompt
    # Old snapshot should not appear anymore
    assert "D1 — PUSH" not in cli.system_prompt


def test_cli_repl_full_run_loop(capsys):
    """run() processes multiple commands in sequence before EOF."""
    from pathlib import Path
    from unittest.mock import call
    from src.coach.cli import CoachCLI

    mock_provider = MagicMock()
    mock_provider.stream.return_value = iter(["coach response"])

    inputs = iter(["/day D1", "/status", "/quit"])

    with patch("src.coach.cli.load_active_program", return_value=_FAKE_PROGRAM), \
         patch("src.coach.cli.get_provider", return_value=mock_provider), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value="# Base"), \
         patch("builtins.input", side_effect=inputs):
        cli = CoachCLI()
        cli.run()

    out = capsys.readouterr().out
    # Startup banner
    assert "Test Program" in out
    # /day D1 output
    assert "D1" in out
    # /status output (set by /day D1 above)
    assert "PUSH" in out
