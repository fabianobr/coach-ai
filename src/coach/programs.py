"""Program management data layer for coach-ai."""

import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path

from coach.paths import get_programs_dir


class ProgramNotFound(FileNotFoundError):
    """Raised when a program JSON file cannot be found."""


class ProgramAlreadyExists(FileExistsError):
    """Raised when attempting to create a program that already exists."""


class ActiveProgramNotConfigured(RuntimeError):
    """Raised when active.txt is missing or not configured."""


class InvalidProgramId(ValueError):
    """Raised when a program_id does not match the required pattern."""


_PROGRAM_ID_PATTERN = re.compile(r"^[a-z0-9-]+$")


def load_active_program() -> dict:
    """
    Reads data/programs/active.txt to get program_id,
    then reads data/programs/<id>.json and returns the parsed dict.

    Raises:
        ActiveProgramNotConfigured: if active.txt is missing.
        ProgramNotFound: if the referenced program file doesn't exist.
    """
    programs_dir = get_programs_dir()
    active_file = programs_dir / "active.txt"

    if not active_file.exists():
        raise ActiveProgramNotConfigured(
            f"No active program configured. Expected '{active_file}' to exist. "
            "Run 'switch_program(program_id)' to set one."
        )

    program_id = active_file.read_text().strip()
    return get_program(program_id)


def list_programs() -> list[dict]:
    """
    Scans data/programs/*.json.
    Returns list of dicts with keys: program_id, name, active (bool).
    active=True for the program matching active.txt.
    If active.txt missing or dangling, active=False for all.
    """
    programs_dir = get_programs_dir()

    active_id: str | None = None
    active_file = programs_dir / "active.txt"
    if active_file.exists():
        candidate = active_file.read_text().strip()
        # Only mark as active if the referenced file actually exists
        if (programs_dir / f"{candidate}.json").exists():
            active_id = candidate

    result: list[dict] = []
    for json_file in sorted(programs_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        program_id = json_file.stem
        result.append(
            {
                "program_id": program_id,
                "name": data.get("name", program_id),
                "active": program_id == active_id,
            }
        )

    return result


def get_program(program_id: str) -> dict:
    """Load any program by id. Raises ProgramNotFound if not found."""
    programs_dir = get_programs_dir()
    program_file = programs_dir / f"{program_id}.json"

    if not program_file.exists():
        raise ProgramNotFound(f"Program '{program_id}' not found. Expected file: '{program_file}'")

    return json.loads(program_file.read_text())


def switch_program(program_id: str) -> None:
    """
    Validates program file exists, then atomically rewrites active.txt.

    Uses tempfile + os.replace for atomic write.

    Raises:
        ProgramNotFound: if the program file doesn't exist.
    """
    programs_dir = get_programs_dir()
    program_file = programs_dir / f"{program_id}.json"

    if not program_file.exists():
        raise ProgramNotFound(f"Program '{program_id}' not found. Expected file: '{program_file}'")

    active_file = programs_dir / "active.txt"
    # Write to a temp file in the same directory, then replace atomically
    fd, tmp_path = tempfile.mkstemp(dir=programs_dir, prefix=".active_tmp_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(f"{program_id}\n")
        os.replace(tmp_path, active_file)
    except Exception:
        # Clean up temp file if something went wrong
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def clone_program(src_id: str, dst_id: str) -> Path:
    """
    Copies src program JSON to a new file with dst_id.

    Validates:
      - src exists (raises ProgramNotFound)
      - dst doesn't exist (raises ProgramAlreadyExists)
      - dst_id matches ^[a-z0-9-]+$ (raises InvalidProgramId)

    In the copy: sets program_id=dst_id, created_at=today (YYYY-MM-DD),
    name="<src_name> (copy)".

    Returns:
        Path to the new program file.
    """
    if not _PROGRAM_ID_PATTERN.match(dst_id):
        raise InvalidProgramId(f"Invalid program id '{dst_id}'. Must match ^[a-z0-9-]+$.")

    programs_dir = get_programs_dir()
    src_file = programs_dir / f"{src_id}.json"
    dst_file = programs_dir / f"{dst_id}.json"

    if not src_file.exists():
        raise ProgramNotFound(f"Source program '{src_id}' not found. Expected file: '{src_file}'")

    if dst_file.exists():
        raise ProgramAlreadyExists(f"Program '{dst_id}' already exists at '{dst_file}'")

    src_data = json.loads(src_file.read_text())
    src_name = src_data.get("name", src_id)

    dst_data = dict(src_data)
    dst_data["program_id"] = dst_id
    dst_data["name"] = f"{src_name} (copy)"
    dst_data["created_at"] = date.today().isoformat()

    dst_file.write_text(json.dumps(dst_data, indent=2, ensure_ascii=False) + "\n")
    return dst_file
