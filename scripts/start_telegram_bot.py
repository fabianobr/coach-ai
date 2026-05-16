#!/usr/bin/env python3
"""
Telegram Bot Startup Script

Configures environment and starts the coach-ai Telegram bot with proper
error checking and resource path setup.
"""

import asyncio
import os
import sys
from pathlib import Path


def log_info(msg: str) -> None:
    print(f"ℹ️  {msg}")


def log_success(msg: str) -> None:
    print(f"✅ {msg}")


def log_error(msg: str) -> None:
    print(f"❌ {msg}")


def log_warning(msg: str) -> None:
    print(f"⚠️  {msg}")


def verify_env_file(project_root: Path) -> None:
    """Verify .env file exists and load it."""
    env_path = project_root / ".env"

    if not env_path.exists():
        log_error(f".env file not found at {env_path}")
        log_info("Run: cp .env.example .env")
        sys.exit(1)

    # Load .env file
    from dotenv import load_dotenv
    load_dotenv(env_path)
    log_success(f".env loaded from {env_path}")


def verify_required_env() -> None:
    """Check required environment variables."""
    required_vars = {
        "TELEGRAM_BOT_TOKEN": "Telegram bot token (from BotFather)",
        "LLM_PROVIDER": "LLM provider (anthropic, openai, ollama, gemini)",
    }

    missing = []
    for var, desc in required_vars.items():
        if not os.getenv(var):
            missing.append(f"{var} ({desc})")

    if missing:
        log_error("Missing environment variables:")
        for var in missing:
            print(f"   - {var}")
        sys.exit(1)

    log_success("All required environment variables are set")


def verify_system_prompt(project_root: Path) -> None:
    """Verify SYSTEM_PROMPT.md exists and set environment variable."""
    system_prompt_path = project_root / "prompts" / "SYSTEM_PROMPT.md"

    if not system_prompt_path.exists():
        log_error(f"SYSTEM_PROMPT.md not found at {system_prompt_path}")
        sys.exit(1)

    # Set environment variable for resource loading
    os.environ["COACH_SYSTEM_PROMPT_MD_PATH"] = str(system_prompt_path)
    log_success(f"SYSTEM_PROMPT.md found at {system_prompt_path}")


def verify_program_files(project_root: Path) -> None:
    """Verify active.txt and the referenced program JSON exist."""
    active_path = project_root / "data" / "programs" / "active.txt"
    if not active_path.exists():
        log_error(f"active.txt not found at {active_path}")
        sys.exit(1)

    program_id = active_path.read_text(encoding="utf-8").strip()
    program_path = project_root / "data" / "programs" / f"{program_id}.json"
    if not program_path.exists():
        log_error(f"Active program file not found: {program_path}")
        sys.exit(1)

    log_success(f"Active program: {program_id}")


def verify_ollama(base_url: str) -> None:
    """Verify Ollama is running if using Ollama provider."""
    provider = os.getenv("LLM_PROVIDER", "").lower()

    if provider != "ollama":
        return

    log_info("Checking Ollama connection...")

    try:
        import urllib.request
        import json

        api_url = f"{base_url.rstrip('/v1')}/api/tags"
        try:
            with urllib.request.urlopen(api_url, timeout=2) as response:
                data = json.loads(response.read().decode())
                models = data.get("models", [])
                log_success(f"Ollama is running with {len(models)} models available")
                return
        except urllib.error.URLError:
            pass
    except Exception:
        pass

    log_error(f"Ollama is not running at {base_url}")
    log_info("Start Ollama with: ollama serve")
    sys.exit(1)


def verify_virtual_env() -> None:
    """Warn if virtual environment is not activated."""
    if not os.getenv("VIRTUAL_ENV"):
        log_warning("Virtual environment not activated")
        log_info("Consider running: source .venv/bin/activate")


def start_bot(project_root: Path) -> None:
    """Start the Telegram bot."""
    print()
    log_success("Environment verified")
    print()
    log_info("Starting Telegram bot (polling for messages)...")
    log_info("Find your bot on Telegram and send /start")
    log_info("Press Ctrl+C to stop")
    print()

    # Change to project root and start bot
    os.chdir(project_root)

    try:
        import coach.telegram.bot
        from dotenv import load_dotenv
        load_dotenv()

        bot = coach.telegram.bot.CoachBot()
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n")
        log_info("Bot stopped")
    except ImportError as e:
        log_error(f"Missing dependency: {e}")
        if "openai" in str(e):
            log_info("Install it with: pip install openai")
        elif "telegram" in str(e):
            log_info("Install it with: pip install -e '.[dev]'")
        else:
            log_info(f"Install the missing package related to: {e}")
        sys.exit(1)
    except Exception as e:
        log_error(f"Failed to start bot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    print("🚀 Coach AI Telegram Bot Startup\n")

    # Get project root (script is in scripts/ subdir)
    project_root = Path(__file__).parent.parent.resolve()
    log_info(f"Project root: {project_root}")
    print()

    # Verification steps
    verify_env_file(project_root)
    verify_required_env()
    verify_system_prompt(project_root)
    verify_program_files(project_root)

    # Check LLM provider
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    verify_ollama(base_url)

    verify_virtual_env()

    # Start the bot
    start_bot(project_root)


if __name__ == "__main__":
    main()
