import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from coach.constants import DAY_LABELS
from coach.llm import Message, get_provider
from coach.logger import SessionLogger
from coach.paths import get_resource_path
from coach.telegram.user_sessions import UserSessionStore

logger = logging.getLogger(__name__)


class CoachBot:
    def __init__(self) -> None:
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")

        self.system_prompt: str | None = None
        self.program: dict | None = None
        self.provider = None
        self.store = UserSessionStore()

    def load_system_prompt(self) -> None:
        path = get_resource_path("SYSTEM_PROMPT.md")
        self.system_prompt = path.read_text(encoding="utf-8")

    def load_program(self) -> None:
        program_path = Path(__file__).parent.parent.parent / "data" / "program.json"
        if not program_path.exists():
            raise FileNotFoundError(f"program.json not found at {program_path}")
        self.program = json.loads(program_path.read_text(encoding="utf-8"))

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
        day_label = DAY_LABELS.get(day_id, "Unknown")
        await update.message.reply_text(f"✅ Training day set to {day_id} ({day_label})")

    async def handle_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        session = self.store.get_or_create(user_id)

        logger_instance = SessionLogger()
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Record accumulated exercises before saving
        for exercise in session.exercises:
            logger_instance.record(exercise)

        try:
            await asyncio.to_thread(logger_instance.save, session.current_day, date_str)
            await update.message.reply_text(
                f"✅ Session complete! Workout saved.\n"
                f"Great work on {session.current_day}! 💪"
            )
            self.store.clear(user_id)
        except FileExistsError:
            await update.message.reply_text(
                f"⚠️ Workout for {date_str} already logged.\n"
                f"Session data preserved. Use /day to set a new day or continue."
            )
        except Exception as e:
            logger.error(f"Failed to save workout for user {user_id}: {e}")
            await update.message.reply_text("⚠️ Could not save workout. Session preserved.")

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        session = self.store.get_or_create(user_id)

        if not self.program or session.current_day not in self.program.get("days", {}):
            await update.message.reply_text("Unable to load training program")
            return

        day_data = self.program["days"][session.current_day]
        day_label = day_data.get("label", "Unknown")

        lines = [f"📋 *{session.current_day}: {day_label}* Exercises"]
        for ex in day_data.get("exercises", []):
            order = ex.get("order", "?")
            name = ex.get("name", "Unknown")
            lines.append(f"{order}. {name} ⏳")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        session = self.store.get_or_create(user_id)
        user_message = update.message.text

        session.messages.append(Message(role="user", content=user_message))

        full_response = ""
        buffer = ""
        max_chunk_size = 3500

        try:
            chunks = await asyncio.to_thread(
                lambda: list(
                    self.provider.stream(
                        messages=list(session.messages), system=self.system_prompt
                    )
                )
            )
        except Exception as e:
            logger.error(f"LLM streaming error for user {user_id}: {e}", exc_info=True)
            await update.message.reply_text("Coach is unavailable. Try again in a moment.")
            return

        try:
            for chunk in chunks:
                full_response += chunk
                buffer += chunk

                if len(buffer) >= max_chunk_size:
                    await update.message.reply_text(buffer, parse_mode="Markdown")
                    buffer = ""

            if buffer:
                await update.message.reply_text(buffer, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send buffered response to user {user_id}: {e}", exc_info=True)
            await update.message.reply_text("Error sending response. Please try again.")

        session.messages.append(Message(role="assistant", content=full_response))

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.handle_start(update, context)
