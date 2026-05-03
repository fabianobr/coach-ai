#!/bin/bash
# Telegram Bot Startup Script
# Sets up environment and starts the coach-ai Telegram bot

set -e  # Exit on error

# Get the project root directory (script is in scripts/ subdir)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting Coach AI Telegram Bot..."
echo "   Project root: $PROJECT_ROOT"

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "❌ Error: .env file not found at $PROJECT_ROOT/.env"
    echo "   Please run: cp .env.example .env"
    exit 1
fi

# Load environment variables
export $(cat "$PROJECT_ROOT/.env" | grep -v '^#' | xargs)

# Verify required variables are set
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ Error: TELEGRAM_BOT_TOKEN not set in .env"
    exit 1
fi

if [ -z "$LLM_PROVIDER" ]; then
    echo "❌ Error: LLM_PROVIDER not set in .env"
    exit 1
fi

# Set resource paths for development
export COACH_SYSTEM_PROMPT_MD_PATH="$PROJECT_ROOT/prompts/SYSTEM_PROMPT.md"

# Verify SYSTEM_PROMPT.md exists
if [ ! -f "$COACH_SYSTEM_PROMPT_MD_PATH" ]; then
    echo "❌ Error: SYSTEM_PROMPT.md not found at $COACH_SYSTEM_PROMPT_MD_PATH"
    exit 1
fi

# Verify Ollama is running (if using Ollama)
if [ "$LLM_PROVIDER" = "ollama" ]; then
    echo "🔍 Checking Ollama connection..."
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "❌ Error: Ollama is not running at http://localhost:11434"
        echo "   Start Ollama with: ollama serve"
        exit 1
    fi
    echo "✅ Ollama is running"
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Virtual environment not activated"
    echo "   Consider running: source .venv/bin/activate"
fi

echo ""
echo "✅ Environment verified"
echo "📱 Starting bot (polling for messages)..."
echo "   Find your bot on Telegram and send /start"
echo "   Press Ctrl+C to stop"
echo ""

cd "$PROJECT_ROOT"
python -m coach.telegram
