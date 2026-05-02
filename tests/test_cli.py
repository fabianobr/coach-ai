import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.coach.llm.base import Message


def make_cli(system_prompt_content="# System Prompt"):
    """Return a CoachCLI with a mocked system prompt file and provider."""
    mock_provider = MagicMock()
    mock_provider.stream.return_value = iter(["Hello", " world"])

    with patch("src.coach.cli.get_provider", return_value=mock_provider), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value=system_prompt_content):
        from src.coach.cli import CoachCLI
        cli = CoachCLI()
        cli.system_prompt = system_prompt_content
        cli.provider = mock_provider
    return cli, mock_provider


def test_quit_returns_false():
    cli, _ = make_cli()
    assert cli._handle_input("/quit") is False


def test_reset_clears_history():
    cli, _ = make_cli()
    cli.history = [Message(role="user", content="test")]
    cli._handle_input("/reset")
    assert cli.history == []


def test_regular_message_adds_two_entries():
    cli, mock_provider = make_cli()
    mock_provider.stream.return_value = iter(["Hi"])

    with patch("sys.stdout", new_callable=StringIO):
        result = cli._handle_input("squat done 5x5")

    assert result is True
    assert len(cli.history) == 2
    assert cli.history[0].role == "user"
    assert cli.history[1].role == "assistant"


def test_missing_system_prompt_raises():
    with patch.object(Path, "exists", return_value=False):
        from src.coach.cli import CoachCLI
        cli = CoachCLI()
        with pytest.raises(FileNotFoundError):
            cli._load_system_prompt()


def test_stream_chunks_are_printed(capsys):
    cli, mock_provider = make_cli()
    mock_provider.stream.return_value = iter(["chunk1", "chunk2"])

    cli._stream_response()

    captured = capsys.readouterr()
    assert "chunk1" in captured.out
    assert "chunk2" in captured.out


def test_stream_error_returns_none():
    """Stream error should return None (connection error)."""
    cli, mock_provider = make_cli()
    mock_provider.stream.side_effect = ConnectionError("Network timeout")

    with patch("sys.stdout", new_callable=StringIO):
        result = cli._stream_response()

    assert result is None


def test_stream_error_rolls_back_history():
    """Stream error should remove user message from history."""
    cli, mock_provider = make_cli()
    mock_provider.stream.side_effect = Exception("Unexpected error")

    with patch("sys.stdout", new_callable=StringIO):
        cli._handle_input("problematic message")

    assert len(cli.history) == 0  # User message was rolled back


def test_provider_initialization_error():
    """Provider init error should propagate."""
    from src.coach.cli import CoachCLI

    with patch("src.coach.cli.get_provider", side_effect=Exception("Invalid API key")):
        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value="# System Prompt"):
            cli = CoachCLI()
            with pytest.raises(SystemExit) as exc_info:
                cli.run()
            assert exc_info.value.code == 1
