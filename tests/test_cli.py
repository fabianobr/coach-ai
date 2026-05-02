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
