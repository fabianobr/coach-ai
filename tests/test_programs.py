"""Tests for src/coach/programs.py — program management data layer."""

import json
from pathlib import Path

import pytest

from src.coach.programs import (
    ActiveProgramNotConfigured,
    InvalidProgramId,
    ProgramAlreadyExists,
    ProgramNotFound,
    clone_program,
    get_program,
    list_programs,
    load_active_program,
    switch_program,
)


# ---------------------------------------------------------------------------
# get_program
# ---------------------------------------------------------------------------


def test_get_program_returns_dict(programs_dir):
    program = get_program("test-program")
    assert program["program_id"] == "test-program"
    assert program["name"] == "Test Program"


def test_get_program_not_found(programs_dir):
    with pytest.raises(ProgramNotFound):
        get_program("nonexistent-program")


# ---------------------------------------------------------------------------
# load_active_program
# ---------------------------------------------------------------------------


def test_load_active_program_returns_active(programs_dir):
    program = load_active_program()
    assert program["program_id"] == "test-program"


def test_load_active_program_missing_active_txt(programs_dir):
    (programs_dir / "active.txt").unlink()
    with pytest.raises(ActiveProgramNotConfigured):
        load_active_program()


def test_load_active_program_dangling_id(programs_dir):
    (programs_dir / "active.txt").write_text("does-not-exist\n")
    with pytest.raises(ProgramNotFound):
        load_active_program()


# ---------------------------------------------------------------------------
# list_programs
# ---------------------------------------------------------------------------


def test_list_programs_returns_list(programs_dir):
    programs = list_programs()
    assert len(programs) >= 1
    for entry in programs:
        assert "program_id" in entry
        assert "name" in entry
        assert "active" in entry


def test_list_programs_marks_active(programs_dir):
    programs = list_programs()
    active_entries = [p for p in programs if p["program_id"] == "test-program"]
    assert len(active_entries) == 1
    assert active_entries[0]["active"] is True


def test_list_programs_missing_active_txt(programs_dir):
    (programs_dir / "active.txt").unlink()
    programs = list_programs()
    assert all(not p["active"] for p in programs)


def test_list_programs_dangling_active_txt(programs_dir):
    (programs_dir / "active.txt").write_text("ghost-program\n")
    programs = list_programs()
    assert all(not p["active"] for p in programs)


def test_list_programs_empty_dir(programs_dir):
    # Remove all JSON files
    for json_file in programs_dir.glob("*.json"):
        json_file.unlink()
    programs = list_programs()
    assert programs == []


# ---------------------------------------------------------------------------
# switch_program
# ---------------------------------------------------------------------------


def test_switch_program_updates_active_txt(programs_dir):
    # Create a second program to switch to
    src = programs_dir / "test-program.json"
    data = json.loads(src.read_text())
    data["program_id"] = "alt-program"
    data["name"] = "Alt Program"
    (programs_dir / "alt-program.json").write_text(json.dumps(data))

    switch_program("alt-program")
    active_id = (programs_dir / "active.txt").read_text().strip()
    assert active_id == "alt-program"


def test_switch_program_load_after_switch(programs_dir):
    # Create a second program and switch to it
    src = programs_dir / "test-program.json"
    data = json.loads(src.read_text())
    data["program_id"] = "second-program"
    data["name"] = "Second Program"
    (programs_dir / "second-program.json").write_text(json.dumps(data))

    switch_program("second-program")
    program = load_active_program()
    assert program["program_id"] == "second-program"


def test_switch_program_not_found(programs_dir):
    with pytest.raises(ProgramNotFound):
        switch_program("ghost-program")


# ---------------------------------------------------------------------------
# clone_program
# ---------------------------------------------------------------------------


def test_clone_program_creates_file(programs_dir):
    result_path = clone_program("test-program", "cloned-program")
    assert isinstance(result_path, Path)
    assert result_path.exists()


def test_clone_program_sets_metadata(programs_dir):
    from datetime import date

    clone_program("test-program", "my-clone")
    cloned = json.loads((programs_dir / "my-clone.json").read_text())
    assert cloned["program_id"] == "my-clone"
    assert cloned["name"].endswith("(copy)")
    assert cloned["created_at"] == date.today().isoformat()


def test_clone_program_src_not_found(programs_dir):
    with pytest.raises(ProgramNotFound):
        clone_program("no-such-program", "new-program")


def test_clone_program_dst_exists(programs_dir):
    # Clone once successfully
    clone_program("test-program", "already-exists")
    # Second clone to same id should raise
    with pytest.raises(ProgramAlreadyExists):
        clone_program("test-program", "already-exists")


def test_clone_program_invalid_id(programs_dir):
    invalid_ids = ["UpperCase", "has space", "special!char", "CAPS", "has.dot"]
    for bad_id in invalid_ids:
        with pytest.raises(InvalidProgramId, match=bad_id.replace("!", r"\!")):
            clone_program("test-program", bad_id)


def test_clone_program_valid_ids(programs_dir):
    valid_ids = ["abc", "abc-def", "abc123", "123", "a-b-c-1-2-3"]
    for valid_id in valid_ids:
        path = clone_program("test-program", valid_id)
        assert path.exists(), f"Expected file to exist for id '{valid_id}'"
