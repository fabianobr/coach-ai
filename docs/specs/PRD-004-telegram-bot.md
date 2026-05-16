# PRD: Telegram Bot

> **Note:** This spec is superseded by the dynamic program system implemented in feat/dynamic-programs. See `data/programs/` and `src/coach/programs.py` for the current implementation.

## Problem Statement

The coach currently runs in Claude Code (desktop/web) or as a terminal CLI. Users at the gym want to log workouts on mobile via a messaging interface without setup overhead. Telegram is a platform-agnostic, widely-used messaging app that provides a natural, low-friction interface for real-time workout logging.

A Telegram bot enables:
- Mobile access from anywhere (no app install needed)
- Per-user session isolation (unique Telegram user_id)
- Asynchronous, always-on availability
- Familiar messaging UX for quick logging

## Goals

- **Respond to workout messages**: Accept user messages like "squat done 5x5 at 110kg" and return the full 5-step coaching response.
- **Per-user session isolation**: Each Telegram user has independent conversation history.
- **Training day commands**: `/day D1` (or D2/D4/D5) to set the active training day for the session.
- **Session lifecycle commands**: `/start` (welcome), `/done` (end session + save log), `/status` (show today's exercises).
- **Long-running bot**: Polling mode for continuous availability without webhooks.
- **Error recovery**: If the LLM is unavailable, reply gracefully and stay online.

## Non-Goals

- Inline keyboards / rich media formatting (keep it simple)
- Group chats or multi-user sessions
- Media uploads (photos, videos)
- Multi-language support (English only)
- Telegram Premium features
- Persistent session storage (same as REST API: in-memory only)

## User Stories

1. **As a gym user**, I want to start a chat with the bot, send "squat done 5x5 at 110kg", and get immediate coaching feedback.
   - Acceptance: Bot responds with the full 5-step coaching sequence within 5 seconds.

2. **As a user**, I want to set my training day with `/day D1` at the start of my session.
   - Acceptance: Bot acknowledges the day change and future responses reference D1 exercises.

3. **As a user**, I want to end my session with `/done` and have my workout saved to `logs/YYYY-MM-DD.md`.
   - Acceptance: Bot confirms the session is saved; I can later review the log file.

4. **As a user**, I want to check what exercises are pending today with `/status`.
   - Acceptance: Bot returns a table of today's exercises with status (done/pending/skipped).

5. **As a user at the gym**, I want the bot to always be available, even if I don't use it for hours.
   - Acceptance: Bot is running 24/7 via polling; no need to restart manually.

6. **As the bot operator**, I want the bot to be resilient — if the LLM is down, the bot should stay online and retry gracefully.
   - Acceptance: LLM errors are reported to the user; bot doesn't crash.

## Functional Requirements

### Commands

| Command | Behavior |
|---|---|
| **`/start`** | Welcome message with instructions: "Welcome to Coach AI. Send a workout message or use: `/day D1`, `/status`, `/done`." |
| **`/day D1\|D2\|D4\|D5`** | Set the active training day. Acknowledge: "Training day set to D1 (Lower — Strength)." |
| **`/status`** | Show current day's exercise table (markdown table format) with status icons. |
| **`/done`** | End the session and save to `logs/YYYY-MM-DD.md`. Confirm: "Session saved to logs/2026-05-01.md. Great work!" |
| **`/help`** | Print all available commands. |
| **Regular message** | Treat as a workout report; respond with full 5-step coaching sequence. |

### Per-User Session Management

- Use Telegram `user_id` (integer) as the session key.
- Store `dict[int, list[Message]]` in-memory (same as REST API).
- Conversation history is isolated per user.
- History is cleared on `/start` or `/done`.

### Message Flow

**Non-command message (e.g., "squat done 5x5 at 110kg"):**
1. Append `Message(role="user", content=message)` to user's history.
2. Call `provider.stream(history, system=SYSTEM_PROMPT)`.
3. Send chunks back to Telegram via `bot.send_message()` as they arrive (chunked, not one per chunk).
4. Append `Message(role="assistant", content=full_response)` to history.

**Command processing:**
- Extract command from message.text.
- Dispatch to appropriate handler.
- Handlers modify user state (e.g., current_day) but do NOT generate LLM responses.

### Session State Per User

```python
@dataclass
class UserSession:
    user_id: int
    messages: list[Message]
    current_day: str = "D1"  # Default or last selected day
    created_at: datetime
```

### Streaming to Telegram

LLM streaming returns chunks; buffer and send to Telegram in batches to avoid rate limits:

```python
buffer = ""
chunk_size = 100  # Characters

for chunk in provider.stream(history, system=SYSTEM_PROMPT):
    buffer += chunk
    if len(buffer) >= chunk_size:
        await bot.send_message(chat_id=user_id, text=buffer)
        buffer = ""

if buffer:
    await bot.send_message(chat_id=user_id, text=buffer)
```

### Logging to Disk (`/done`)

When `/done` is called:
1. Collect the day_id and exercises from the user's conversation history.
2. Call `SessionLogger.save(day_id, date=today, duration=...)`.
3. Reply with the saved file path.
4. Clear the user's session history.

(This assumes `SessionLogger` can parse exercises from the LLM responses; for now, a simplified version can be used or the feature can be deferred to PRD-005 if parsing is too complex.)

## Technical Requirements & Architecture

### File Structure
```
src/coach/telegram/
  __init__.py
  __main__.py              (entry point: python -m coach.telegram)
  bot.py                   (CoachBot class, main handler)
  handlers.py              (Handler functions: on_message, on_day, on_done, etc.)
  user_sessions.py         (UserSessionStore class)
```

### `user_sessions.py`
```python
from dataclasses import dataclass, field
from datetime import datetime
from coach.llm import Message

@dataclass
class UserSession:
    user_id: int
    messages: list[Message] = field(default_factory=list)
    current_day: str = "D1"
    created_at: datetime = field(default_factory=datetime.now)

class UserSessionStore:
    def __init__(self):
        self.sessions: dict[int, UserSession] = {}
    
    def get_or_create(self, user_id: int) -> UserSession:
        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession(user_id=user_id)
        return self.sessions[user_id]
    
    def clear(self, user_id: int) -> None:
        if user_id in self.sessions:
            del self.sessions[user_id]
```

### `bot.py`
```python
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from coach.llm import get_provider, Message
from coach.telegram.user_sessions import UserSessionStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CoachBot:
    def __init__(self):
        self.provider = get_provider()
        self.store = UserSessionStore()
        self.system_prompt = None
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")
    
    def load_system_prompt(self) -> None:
        system_prompt_path = Path(__file__).parent.parent.parent / "SYSTEM_PROMPT.md"
        if not system_prompt_path.exists():
            raise FileNotFoundError(f"SYSTEM_PROMPT.md not found at {system_prompt_path}")
        self.system_prompt = system_prompt_path.read_text()
    
    async def run(self) -> None:
        self.load_system_prompt()
        
        app = Application.builder().token(self.token).build()
        
        # Handlers
        app.add_handler(CommandHandler("start", self.handle_start))
        app.add_handler(CommandHandler("day", self.handle_day))
        app.add_handler(CommandHandler("done", self.handle_done))
        app.add_handler(CommandHandler("status", self.handle_status))
        app.add_handler(CommandHandler("help", self.handle_help))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Start polling
        await app.initialize()
        await app.start()
        logger.info("Coach bot started. Polling for messages...")
        await app.updater.start_polling()
        
        # Keep running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await app.stop()
            await app.shutdown()
```

### `handlers.py`
```python
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    self.store.get_or_create(user_id)  # Initialize session
    await update.message.reply_text(
        "Welcome to Coach AI! 🏋️\n\n"
        "Send me a workout message or use:\n"
        "/day D1 — Set training day (D1/D2/D4/D5)\n"
        "/status — See today's exercises\n"
        "/done — End session & save log\n"
        "/help — Show this message"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = self.store.get_or_create(user_id)
    user_message = update.message.text
    
    # Append user message
    session.messages.append(Message(role="user", content=user_message))
    
    # Stream response
    full_response = ""
    buffer = ""
    chunk_size = 100
    
    try:
        for chunk in self.provider.stream(
            messages=session.messages,
            system=self.system_prompt
        ):
            full_response += chunk
            buffer += chunk
            
            if len(buffer) >= chunk_size:
                await update.message.reply_text(buffer)
                buffer = ""
        
        if buffer:
            await update.message.reply_text(buffer)
        
        # Append full response
        session.messages.append(Message(role="assistant", content=full_response))
    
    except Exception as e:
        logger.error(f"LLM error for user {user_id}: {e}")
        await update.message.reply_text(
            "Coach is unavailable at the moment. Try again in a few seconds."
        )

async def handle_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = self.store.get_or_create(user_id)
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_text("Usage: /day D1 (or D2, D4, D5)")
        return
    
    day_id = context.args[0].upper()
    if day_id not in ["D1", "D2", "D4", "D5"]:
        await update.message.reply_text(f"Invalid day. Use: D1, D2, D4, or D5")
        return
    
    session.current_day = day_id
    day_labels = {"D1": "Lower — Strength", "D2": "Upper — Strength", 
                  "D4": "Lower — Hypertrophy", "D5": "Upper — Hypertrophy"}
    await update.message.reply_text(f"✅ Training day set to {day_id} ({day_labels[day_id]})")

async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = self.store.get_or_create(user_id)
    
    # (Simplified for now; full parsing depends on SessionLogger API)
    await update.message.reply_text(
        f"✅ Session complete! Workout saved.\n"
        f"Great work on {session.current_day}! 💪"
    )
    
    self.store.clear(user_id)

async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = self.store.get_or_create(user_id)
    
    # Load exercises from data/program.json
    # Build a simple table of the day's exercises
    # (Implementation assumes data/program.json is loaded)
    await update.message.reply_text(
        f"📋 **{session.current_day} Exercises**\n\n"
        "| # | Exercise | Status |\n"
        "|---|---|---|\n"
        "| 1 | Back Squat | ⏳ Pending |\n"
        "| 2 | Leg Press | ⏳ Pending |\n"
        "..."
    )

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Same as /start message
    ...
```

### `__main__.py`
```python
import asyncio
import os
from coach.telegram.bot import CoachBot

if __name__ == "__main__":
    bot = CoachBot()
    asyncio.run(bot.run())
```

### Environment Variables

Add to `.env.example`:
```
TELEGRAM_BOT_TOKEN=<your-bot-token>
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-...
```

### Reuse from `src/coach/llm/`
- `get_provider()` — instantiate provider from `.env`
- `Message` — dataclass for role + content

### Dependencies

Add to `pyproject.toml`:
```toml
[project.optional-dependencies]
...
telegram = ["python-telegram-bot>=21.0"]
...
all = [..., "python-telegram-bot>=21.0", ...]
```

Install:
```bash
pip install -e ".[telegram,anthropic]"
```

## Error Handling

| Scenario | Behavior |
|---|---|
| `TELEGRAM_BOT_TOKEN` missing on startup | Crash immediately with clear error. |
| `SYSTEM_PROMPT.md` missing | Crash on startup with clear error. |
| LLM API error during message | Reply "Coach is unavailable..." and stay online. |
| Telegram network error | Log error; message handler will retry on next update. |
| Invalid `/day` argument | Reply "Invalid day. Use: D1, D2, D4, or D5". |
| User sends non-text message | Ignore (bot only handles text). |

## Testing Criteria

### Unit Tests (`tests/test_telegram.py`)

1. **Handler routing**:
   - `/start` calls `handle_start` ✓
   - `/day D1` calls `handle_day` with correct argument ✓
   - Regular text calls `handle_message` ✓

2. **Session isolation**:
   - Two users have independent session history ✓
   - `/done` clears only the calling user's history ✓

3. **Error handling**:
   - Missing TELEGRAM_BOT_TOKEN raises error on startup ✓
   - Missing SYSTEM_PROMPT.md raises error on startup ✓
   - LLM error is caught and reported to user ✓

4. **Stream buffering**:
   - Long responses are sent in chunks ✓
   - Chunks are batched to avoid rate limits ✓

### Integration Test
1. Mock Telegram API.
2. Send `/start` → expect welcome message.
3. Send `/day D1` → expect confirmation.
4. Send "squat done 5x5" → expect full coaching response.
5. Send "bench?" → expect context-aware response.
6. Send `/done` → expect session saved confirmation + history cleared.
7. Send another message → history is fresh (new conversation).

### Manual Testing (with real bot)
1. Create a Telegram bot via @BotFather.
2. Set `TELEGRAM_BOT_TOKEN` in `.env`.
3. Run `python -m coach.telegram`.
4. Message the bot from a Telegram client.
5. Verify all commands work and responses are correct.

## Success Metrics

**The Telegram bot is complete and working when:**
1. `python -m coach.telegram` starts and connects to Telegram.
2. `/start` sends a welcome message.
3. A regular message (e.g., "squat done 5x5") returns the full 5-step coaching response.
4. `/day D2` sets the training day and future responses reference D2 exercises.
5. `/status` shows the current day's exercises.
6. `/done` confirms session saved and clears the history.
7. Two users send messages simultaneously and get independent responses.
8. LLM errors are reported gracefully without crashing the bot.
9. All tests in `tests/test_telegram.py` pass.

---

## Deployment Notes

**Development (local testing):**
```bash
python -m coach.telegram
```

**Production (long-running with supervisor/systemd):**
```ini
[program:coach-telegram]
command=/usr/bin/python -m coach.telegram
directory=/home/user/coach-ai
environment=TELEGRAM_BOT_TOKEN=...,ANTHROPIC_API_KEY=...
autostart=true
autorestart=true
stderr_logfile=/var/log/coach-telegram.err.log
stdout_logfile=/var/log/coach-telegram.out.log
```

## Implementation Notes

- Use `python-telegram-bot` library (version ≥ 21.0); it supports async/await.
- Polling mode is simpler than webhooks; no need to expose a public endpoint.
- User IDs are Telegram integers; store them as-is (not strings).
- Chunk size (100 chars) is a balance between Telegram rate limits and UX; adjust if needed.
- Future improvement: Parse exercise data from LLM responses for more accurate `/status` and `/done` logging.
