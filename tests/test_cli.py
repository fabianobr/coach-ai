import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.coach.llm.base import Message

_FAKE_PROGRAM = {
    "program_id": "test-prog",
    "name": "Test Program",
    "description": "A test program",
    "created_at": "2026-01-01",
    "barbell_weight_kg": 20,
    "days": {
        "D1": {"label": "PUSH", "exercises": []},
        "D2": {"label": "PULL", "exercises": []},
    },
    "rest_days": ["D3"],
}


def make_cli(system_prompt_content="# System Prompt"):
    """Return a CoachCLI with a mocked system prompt file, program, and provider."""
    mock_provider = MagicMock()
    mock_provider.stream.return_value = iter(["Hello", " world"])

    with patch("src.coach.cli.get_provider", return_value=mock_provider), \
         patch("src.coach.cli.load_active_program", return_value=_FAKE_PROGRAM), \
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

    with patch("src.coach.cli.get_provider", side_effect=Exception("Invalid API key")), \
         patch("src.coach.cli.load_active_program", return_value=_FAKE_PROGRAM), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value="# System Prompt"):
        cli = CoachCLI()
        with pytest.raises(SystemExit) as exc_info:
            cli.run()
        assert exc_info.value.code == 1


def test_snapshot_appended_to_system_prompt():
    """run() must append ## CURRENT PROGRAM SNAPSHOT to the system prompt."""
    from src.coach.cli import CoachCLI

    with patch("src.coach.cli.load_active_program", return_value=_FAKE_PROGRAM), \
         patch("src.coach.cli.get_provider", return_value=MagicMock()), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value="# Base Prompt"), \
         patch("builtins.input", side_effect=EOFError):
        cli = CoachCLI()
        cli.run()

    assert "## CURRENT PROGRAM SNAPSHOT" in cli.system_prompt
    assert "Test Program" not in cli.system_prompt  # name not in overview
    assert "D1" in cli.system_prompt


def test_missing_active_program_exits():
    """run() must exit with code 1 when active.txt is missing."""
    import src.coach.cli as cli_module
    from src.coach.cli import CoachCLI

    with patch("src.coach.cli.load_active_program", side_effect=cli_module.ActiveProgramNotConfigured("no active")), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value="# Base Prompt"):
        cli = CoachCLI()
        with pytest.raises(SystemExit) as exc_info:
            cli.run()
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Slash command tests
# ---------------------------------------------------------------------------

def test_cmd_help_lists_commands(capsys):
    cli, _ = make_cli()
    cli._handle_input("/help")
    out = capsys.readouterr().out
    assert "/day" in out
    assert "/programs" in out
    assert "/program switch" in out
    assert "/quit" in out


def test_cmd_start_also_shows_help(capsys):
    cli, _ = make_cli()
    cli._handle_input("/start")
    out = capsys.readouterr().out
    assert "/day" in out


def test_cmd_day_sets_current_day(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    cli._handle_input("/day D1")
    assert cli.current_day == "D1"
    out = capsys.readouterr().out
    assert "D1" in out
    assert "PUSH" in out


def test_cmd_day_invalid_day(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    cli._handle_input("/day D9")
    assert cli.current_day is None
    out = capsys.readouterr().out
    assert "Invalid day" in out


def test_cmd_day_no_args_shows_usage(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    cli._handle_input("/day")
    out = capsys.readouterr().out
    assert "Usage:" in out


def test_cmd_trainings_prints_overview(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    cli._handle_input("/trainings")
    out = capsys.readouterr().out
    assert "D1" in out
    assert "D2" in out


def test_cmd_training_valid_day(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    cli._handle_input("/training D1")
    out = capsys.readouterr().out
    assert "D1" in out
    assert "PUSH" in out


def test_cmd_training_rest_day(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    cli._handle_input("/training D3")
    out = capsys.readouterr().out
    assert "rest day" in out


def test_cmd_training_unknown_day(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    cli._handle_input("/training D9")
    out = capsys.readouterr().out
    assert "Unknown day" in out


def test_cmd_status_no_day_set(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    cli._handle_input("/status")
    out = capsys.readouterr().out
    assert "No training day set" in out


def test_cmd_status_with_day(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    cli.current_day = "D1"
    cli._handle_input("/status")
    out = capsys.readouterr().out
    assert "D1" in out
    assert "PUSH" in out


def test_cmd_done_no_day_set(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    cli._handle_input("/done")
    out = capsys.readouterr().out
    assert "No training day set" in out


def test_cmd_done_saves_log(capsys, tmp_path):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    cli.current_day = "D1"

    with patch("src.coach.cli.SessionLogger") as MockLogger:
        mock_logger = MagicMock()
        MockLogger.return_value = mock_logger
        cli._handle_input("/done")

    mock_logger.save.assert_called_once()
    call_kwargs = mock_logger.save.call_args.kwargs
    assert call_kwargs.get("program_id") == "test-prog"
    assert cli.current_day is None  # cleared after save


def test_cmd_done_file_exists_error(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    cli.current_day = "D1"

    with patch("src.coach.cli.SessionLogger") as MockLogger:
        mock_logger = MagicMock()
        mock_logger.save.side_effect = FileExistsError("already logged")
        MockLogger.return_value = mock_logger
        cli._handle_input("/done")

    out = capsys.readouterr().out
    assert "already logged" in out


def test_cmd_programs_lists_programs(capsys):
    cli, _ = make_cli()
    programs_data = [
        {"program_id": "prog-a", "name": "Prog A", "active": True},
        {"program_id": "prog-b", "name": "Prog B", "active": False},
    ]
    with patch("src.coach.cli.list_programs", return_value=programs_data):
        cli._handle_input("/programs")
    out = capsys.readouterr().out
    assert "prog-a" in out
    assert "prog-b" in out
    assert "✅" in out


def test_cmd_programs_empty(capsys):
    cli, _ = make_cli()
    with patch("src.coach.cli.list_programs", return_value=[]):
        cli._handle_input("/programs")
    out = capsys.readouterr().out
    assert "No programs found" in out


def test_cmd_program_show_active(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    with patch("src.coach.cli.get_program", return_value=_FAKE_PROGRAM):
        cli._handle_input("/program show")
    out = capsys.readouterr().out
    assert "Test Program" in out
    assert "test-prog" in out


def test_cmd_program_show_by_id(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    other = {"program_id": "other", "name": "Other", "days": {"A": {}}, "rest_days": []}
    with patch("src.coach.cli.get_program", return_value=other):
        cli._handle_input("/program show other")
    out = capsys.readouterr().out
    assert "Other" in out


def test_cmd_program_show_not_found(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    import src.coach.cli as cli_module
    with patch("src.coach.cli.get_program", side_effect=cli_module.ProgramNotFound("nope")):
        cli._handle_input("/program show ghost")
    out = capsys.readouterr().out
    assert "not found" in out.lower()


def test_cmd_program_switch_success(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    cli.system_prompt = "# Base"
    new_prog = {**_FAKE_PROGRAM, "program_id": "new-prog", "name": "New"}
    with patch("src.coach.cli.switch_program"), \
         patch("src.coach.cli.load_active_program", return_value=new_prog):
        cli._handle_input("/program switch new-prog")
    out = capsys.readouterr().out
    assert "new-prog" in out
    assert cli.program == new_prog


def test_cmd_program_switch_not_found(capsys):
    cli, _ = make_cli()
    cli.program = _FAKE_PROGRAM
    import src.coach.cli as cli_module
    with patch("src.coach.cli.switch_program", side_effect=cli_module.ProgramNotFound("nope")):
        cli._handle_input("/program switch ghost")
    out = capsys.readouterr().out
    assert "not found" in out.lower()


def test_cmd_program_clone_success(capsys):
    cli, _ = make_cli()
    with patch("src.coach.cli.clone_program"):
        cli._handle_input("/program clone test-prog new-prog")
    out = capsys.readouterr().out
    assert "new-prog" in out
    assert "✅" in out


def test_cmd_program_clone_already_exists(capsys):
    cli, _ = make_cli()
    import src.coach.cli as cli_module
    with patch("src.coach.cli.clone_program", side_effect=cli_module.ProgramAlreadyExists("exists")):
        cli._handle_input("/program clone test-prog new-prog")
    out = capsys.readouterr().out
    assert "already exists" in out.lower()


def test_cmd_program_clone_invalid_id(capsys):
    cli, _ = make_cli()
    import src.coach.cli as cli_module
    with patch("src.coach.cli.clone_program", side_effect=cli_module.InvalidProgramId("bad")):
        cli._handle_input("/program clone test-prog INVALID")
    out = capsys.readouterr().out
    assert "Invalid program ID" in out


def test_cmd_program_unknown_subcommand(capsys):
    cli, _ = make_cli()
    cli._handle_input("/program frobnicate")
    out = capsys.readouterr().out
    assert "Unknown subcommand" in out


def test_plain_strips_html_and_decodes_entities():
    from src.coach.cli import _plain
    assert _plain("<b>Hello</b> &lt;world&gt; &amp; more") == "Hello <world> & more"
