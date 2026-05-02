import asyncio
import json
import logging
import os
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from coach.llm import Message, get_provider
from coach.telegram.user_sessions import UserSessionStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


_DAY_LABELS = {
    "D1": "LOWER | STRENGTH",
    "D2": "UPPER | STRENGTH",
    "D4": "LOWER | HYPERTROPHY",
    "D5": "UPPER | HYPERTROPHY",
}


class CoachBot:
    def __init__(self) -> None:
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")

        self.system_prompt_path = Path(__file__).parent.parent.parent / "SYSTEM_PROMPT.md"
        self.program_path = Path(__file__).parent.parent.parent / "data" / "program.json"
        self.system_prompt: str | None = None
        self.program: dict | None = None
        self.provider = None
        self.store = UserSessionStore()

    def load_system_prompt(self) -> None:
        if not self.system_prompt_path.exists():
            raise FileNotFoundError(f"SYSTEM_PROMPT.md not found at {self.system_prompt_path}")
        self.system_prompt = self.system_prompt_path.read_text(encoding="utf-8")

    def load_program(self) -> None:
        if not self.program_path.exists():
            raise FileNotFoundError(f"program.json not found at {self.program_path}")
        self.program = json.loads(self.program_path.read_text(encoding="utf-8"))

    async def run(self) -> None:
        self.load_system_prompt()
        self.load_program()
        self.provider = get_provider()

        app = Application.builder().token(self.token).build()

        app.add_handler(CommandHandler("start", self.handle_start))
        app.add_handler(CommandHandler("day", self.handle_day))
        app.add_handler(CommandHandler("done", self.handle_done))
        app.add_handler(CommandHandler("status", self.handle_status))
        app.add_handler(CommandHandler("help", self.handle_help))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        await app.initialize()
        await app.start()
        logger.info("Telegram bot started. Polling for messages...")
        await app.updater.start_polling()
        await asyncio.Event().wait()

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        self.store.get_or_create(user_id)
        await update.message.reply_text(
            "Welcome to Coach AI! 🏋️\n\n"
            "Send me a workout message or use:\n"
            "/day D1 — Set training day (D1/D2/D4/D5)\n"
            "/status — See today's exercises\n"
            "/done — End session & save log\n"
            "/help — Show this message"
        )

    async def handle_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        session = self.store.get_or_create(user_id)

        if not context.args or len(context.args) == 0:
            await update.message.reply_text("Usage: /day D1 (or D2, D4, D5)")
            return

        day_id = context.args[0].upper()
        if day_id not in ["D1", "D2", "D4", "D5"]:
            await update.message.reply_text("Invalid day. Use: D1, D2, D4, or D5")
            return

        session.current_day = day_id
        day_label = _DAY_LABELS.get(day_id, "Unknown")
        await update.message.reply_text(f"✅ Training day set to {day_id} ({day_label})")

    async def handle_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        session = self.store.get_or_create(user_id)
        await update.message.reply_text(
            f"✅ Session complete! Workout saved.\n"
            f"Great work on {session.current_day}! 💪"
        )
        self.store.clear(user_id)

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        session = self.store.get_or_create(user_id)

        if not self.program or session.current_day not in self.program["days"]:
            await update.message.reply_text("Unable to load training program")
            return

        day_data = self.program["days"][session.current_day]
        day_label = day_data.get("label", "Unknown")

        lines = [f"📋 **{session.current_day}: {day_label}** Exercises\n"]
        for ex in day_data.get("exercises", []):
            order = ex.get("order", "?")
            name = ex.get("name", "Unknown")
            lines.append(f"{order}. {name} ⏳")

        await update.message.reply_text("\n".join(lines))

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        session = self.store.get_or_create(user_id)
        user_message = update.message.text

        session.messages.append(Message(role="user", content=user_message))

        full_response = ""
        buffer = ""
        chunk_size = 200

        try:
            for chunk in self.provider.stream(
                messages=list(session.messages), system=self.system_prompt
            ):
                full_response += chunk
                buffer += chunk

                if len(buffer) >= chunk_size:
                    await update.message.reply_text(buffer)
                    buffer = ""

            if buffer:
                await update.message.reply_text(buffer)

            session.messages.append(Message(role="assistant", content=full_response))

        except Exception as e:
            logger.error(f"LLM error for user {user_id}: {e}")
            await update.message.reply_text("Coach is unavailable. Try again in a moment.")

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.handle_start(update, context)
