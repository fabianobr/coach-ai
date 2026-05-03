"""Resource path utilities that work for both development and installed packages."""

import os
from pathlib import Path


def get_resource_path(resource_name: str) -> Path:
    """
    Get path to a resource file, supporting both git trees and installed packages.

    Priority:
    1. Environment variable override (e.g., COACH_SYSTEM_PROMPT_PATH)
    2. importlib.resources if available
    3. Git tree path (for development)

    Args:
        resource_name: Name of the resource (e.g., 'SYSTEM_PROMPT.md')

    Returns:
        Path to the resource file

    Raises:
        FileNotFoundError: If resource cannot be found in any location
    """
    # Allow environment variable override
    env_key = f"COACH_{resource_name.upper().replace('.', '_')}_PATH"
    if env_path := os.getenv(env_key):
        path = Path(env_path)
        if path.exists():
            return path

    # Try importlib.resources (Python 3.9+)
    try:
        from importlib.resources import files

        try:
            resource_file = files("coach").joinpath(resource_name)
            if hasattr(resource_file, "__fspath__"):
                # Traversable supports __fspath__ (Python 3.12+)
                return Path(resource_file)
            else:
                # Fallback for older Python versions
                with resource_file.as_file() as f:
                    return f
        except (AttributeError, TypeError):
            pass
    except ImportError:
        pass

    # Fallback to git tree path (development)
    repo_root = Path(__file__).parent.parent.parent
    # Check prompts/ subdirectory first for .md prompt files
    git_path = repo_root / "prompts" / resource_name
    if not git_path.exists():
        git_path = repo_root / resource_name
    if git_path.exists():
        return git_path

    # Not found anywhere
    raise FileNotFoundError(
        f"Resource '{resource_name}' not found. "
        f"Set {env_key} environment variable to override the path."
    )
