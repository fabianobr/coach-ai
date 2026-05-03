# Telegram Bot Setup & Testing Guide

Your Coach AI Telegram bot is ready to test in production! This guide covers everything you need.

## Prerequisites

✅ **Telegram Bot Token** — You've already provided: `REDACTED_TOKEN`

✅ **Ollama Running** — Local LLM server should be accessible at `http://localhost:11434`

✅ **Dependencies Installed** — You have all required packages installed

## Quick Start

### Option 1: Python Script (Recommended - Cross-platform)

```bash
python scripts/start_telegram_bot.py
```

This script will:
- ✅ Verify `.env` file configuration
- ✅ Check all required environment variables
- ✅ Confirm `SYSTEM_PROMPT.md` exists
- ✅ Verify Ollama is running and models are available
- ✅ Start the bot in polling mode

### Option 2: Bash Script (macOS/Linux)

```bash
./scripts/start_telegram_bot.sh
```

Same behavior as the Python script but in pure bash.

### Option 3: Manual Start (No verification)

```bash
python -m coach.telegram
```

## Configuration

Your `.env` file is already configured:

```ini
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
LLM_BASE_URL=http://localhost:11434/v1
TELEGRAM_BOT_TOKEN=REDACTED_TOKEN
```

### Verify Ollama is Running

Before starting the bot, ensure Ollama is running:

```bash
# Check if Ollama is accessible
curl http://localhost:11434/api/tags | jq '.models | length'

# If not running, start it:
ollama serve
```

## Testing the Bot

Once the bot is running, you'll see:

```
✅ Environment verified

ℹ️  Starting Telegram bot (polling for messages)...
ℹ️  Find your bot on Telegram and send /start
ℹ️  Press Ctrl+C to stop
```

### Find Your Bot on Telegram

1. Open Telegram
2. Search for your bot's username (you created it in BotFather)
3. Or use the bot link: `https://t.me/<your_bot_username>`

### Test Commands

Once you've opened the bot chat:

```
/start          → Welcome message with available commands
/day D1         → Set training day to Lower Strength
/status         → Show today's exercises
/help           → Show help message (same as /start)
/done           → Save session and end workout
```

### Test Message Flow

1. **Send `/start`**
   - Bot responds with welcome message
   - ✅ Verifies Telegram connectivity

2. **Send `/day D1`**
   - Bot confirms: "✅ Training day set to D1 (Lower Strength)"
   - ✅ Verifies command handling

3. **Send a workout message**
   ```
   Just did 5 sets of back squat, 5 reps each, 140kg
   ```
   - Bot responds with:
     - 🔤 Language Spotter (grammar corrections if needed)
     - 💪 Coach analysis (exercise feedback, tonnage calculation, etc.)
   - ✅ Verifies LLM connection and streaming

4. **Send `/status`**
   ```
   /status
   ```
   - Bot shows all exercises for D1
   - ✅ Verifies program.json loading

5. **Send `/done`**
   ```
   /done
   ```
   - Bot saves session to `logs/YYYY-MM-DD.md`
   - Session data is cleared
   - ✅ Verifies file logging

## Troubleshooting

### "TELEGRAM_BOT_TOKEN not set"
- Verify `.env` file exists
- Check that `TELEGRAM_BOT_TOKEN=...` line is in `.env`
- Make sure the token wasn't accidentally modified

### "Ollama is not running"
- Start Ollama: `ollama serve`
- Verify connection: `curl http://localhost:11434/api/tags`
- Check that `LLM_BASE_URL` in `.env` matches your Ollama URL

### "SYSTEM_PROMPT.md not found"
- The file should be at: `./prompts/SYSTEM_PROMPT.md`
- Verify it exists: `ls -la prompts/SYSTEM_PROMPT.md`
- Both startup scripts set the environment variable automatically

### "No module named 'openai'"
- Install with: `pip install -e ".[ollama,telegram]"`
- Ollama uses OpenAI-compatible API, so it requires the OpenAI SDK

### Bot is slow to respond
- Check Ollama model is loaded: `curl http://localhost:11434/api/tags`
- Verify model can generate: `ollama run llama3.2 "hello"`
- Increase `LLM_MAX_TOKENS` in `.env` if responses are truncated
- Note: First response might take longer as model loads into memory

### No response from bot in Telegram
- Check bot is still running in terminal (should show "Polling for messages...")
- Verify your Telegram message was sent (not saved as draft)
- Check terminal for error messages (scroll up)
- Restart bot: Press `Ctrl+C` and run the script again

## What Happens Behind the Scenes

1. **Bot Startup** (`start_telegram_bot.py`):
   - Loads environment variables from `.env`
   - Sets resource paths for development
   - Verifies Ollama connectivity
   - Initializes CoachBot class

2. **User Message Processing** (`telegram/bot.py`):
   - Stores user message in session
   - Calls Ollama via LLM provider
   - Streams response back to Telegram (chunks of 3500 chars max)
   - Stores assistant response in session for context

3. **Session Persistence** (`telegram/user_sessions.py`):
   - Each user has their own session
   - Session stores conversation history
   - Session clears after `/done` command

4. **Workout Logging** (`logger.py`):
   - `/done` command saves to `logs/YYYY-MM-DD.md`
   - Logs include all exercises from the session
   - Training day (D1/D2/D4/D5) is recorded

## Resource Architecture

Your setup uses this file structure:

```
coach-ai/
├── .env                        ← Configuration (already set up)
├── scripts/
│   ├── start_telegram_bot.py  ← Run this to start!
│   └── start_telegram_bot.sh  ← Or this (bash version)
├── prompts/
│   └── SYSTEM_PROMPT.md       ← AI behavior definition
├── data/program.json           ← Training program
├── src/
│   └── coach/
│       ├── telegram/
│       │   ├── bot.py         ← Core bot logic
│       │   ├── handlers.py    ← Command handlers
│       │   └── user_sessions.py ← Session management
│       ├── llm/               ← LLM abstraction layer
│       └── logger.py          ← Workout logging
└── logs/
    └── YYYY-MM-DD.md          ← Saved workouts
```

## Next Steps (After Testing)

✅ **Local Testing Complete?** → Congratulations! Your bot is working.

Once stable locally, consider:

1. **Webhook Mode** — Set up HTTPS endpoint for production
   - More efficient than polling
   - Requires public URL and SSL certificate
   - See Telegram Bot API docs

2. **Environment Separation**
   - Dev: Local Ollama
   - Prod: Cloud LLM provider (Anthropic, OpenAI, etc.)

3. **User Session Persistence**
   - Currently stored in-memory
   - For production, use database (Redis, PostgreSQL)

4. **Monitoring & Logging**
   - Monitor Telegram API failures
   - Log model performance metrics
   - Set up alerts for bot crashes

## Questions?

If you run into issues:
1. Check the troubleshooting section above
2. Review the error message in the terminal
3. Verify all configuration in `.env`
4. Check that Ollama is running and responsive
