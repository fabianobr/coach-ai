"""Shared pytest fixtures for coach-ai tests."""

import shutil
from pathlib import Path

import pytest

FIXTURES_PROGRAMS_DIR = Path(__file__).parent / "fixtures" / "programs"


@pytest.fixture
def programs_dir(tmp_path, monkeypatch):
    """
    Copies tests/fixtures/programs/ to a temp dir and sets the
    COACH_PROGRAMS_DIR_PATH env var to point at it. Each test gets
    an isolated, mutable copy of the fixture programs.

    Also sets COACH_LOGS_DIR_PATH to tmp_path/logs/ (creates the dir).
    """
    programs_copy = tmp_path / "programs"
    shutil.copytree(FIXTURES_PROGRAMS_DIR, programs_copy)

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    monkeypatch.setenv("COACH_PROGRAMS_DIR_PATH", str(programs_copy))
    monkeypatch.setenv("COACH_LOGS_DIR_PATH", str(logs_dir))

    yield programs_copy
