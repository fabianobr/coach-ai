import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from coach.constants import DAY_LABELS
from coach.day_plan import render_day_plan_table, render_day_plan_summary
from coach.llm import Message, get_provider
from coach.logger import SessionLogger
from coach.paths import get_resource_path
from coach.telegram.user_sessions import UserSessionStore

logger = logging.getLogger(__name__)

# Sentinel for end-of-stream in asyncio.Queue to prevent collision with falsy chunks
_STREAM_END = object()


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
        program_path = Path(__file__).parent.parent.parent.parent / "data" / "program.json"
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

        # Render Day Plan table with weights and tonnage
        reply_lines = [f"✅ Training day set to {day_id} ({day_label})"]

        if self.program and day_id in self.program.get("days", {}):
            day_data = self.program["days"][day_id]
            exercises = day_data.get("exercises", [])
            exercise_count = len(exercises)

            # Render table
            table, total_volume = render_day_plan_table(self.program, day_id)
            if table:
                reply_lines.append("")
                reply_lines.append(f"```\n{table}\n```")
                reply_lines.append("")
                reply_lines.append(render_day_plan_summary(day_id, total_volume, exercise_count))

        await self._safe_reply(update.message, "\n".join(reply_lines))

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
        except (PermissionError, OSError) as e:
            logger.error(f"File system error saving workout for user {user_id}: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Storage error. Workout could not be saved.")
        except Exception as e:
            logger.error(f"Unexpected error saving workout for user {user_id}: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Session preserved. Workout data could not be saved.")

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        session = self.store.get_or_create(user_id)

        if not self.program or session.current_day not in self.program.get("days", {}):
            await update.message.reply_text("Unable to load training program")
            return

        day_data = self.program["days"][session.current_day]
        day_label = day_data.get("label", "Unknown")
        exercises = day_data.get("exercises", [])
        exercise_count = len(exercises)

        # Use Day Plan table format
        reply_lines = [f"📋 *{session.current_day}: {day_label}* Exercises"]

        table, total_volume = render_day_plan_table(self.program, session.current_day)
        if table:
            reply_lines.append("")
            reply_lines.append(f"```\n{table}\n```")
            reply_lines.append("")
            reply_lines.append(render_day_plan_summary(session.current_day, total_volume, exercise_count))

        await self._safe_reply(update.message, "\n".join(reply_lines))

    async def _safe_reply(self, message, text: str) -> None:
        """
        Send text with Markdown formatting. If Telegram rejects the markup
        (unmatched *, _, `), fall back to plain text. Propagate unrecoverable errors.
        """
        try:
            await message.reply_text(text, parse_mode="Markdown")
        except BadRequest as e:
            logger.warning(f"Markdown rejected by Telegram ({e}); retrying as plain text")
            try:
                await message.reply_text(text)
            except Exception as fallback_err:
                logger.error(f"Plain-text fallback also failed: {fallback_err}", exc_info=True)
                raise

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        user_lock = self.store.get_lock(user_id)

        async with user_lock:
            await self._handle_message_impl(update, context, user_id)

    async def _handle_message_impl(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int
    ) -> None:
        """Implementation of message handling with per-user serialization via lock."""
        session = self.store.get_or_create(user_id)
        user_message = update.message.text

        session.messages.append(Message(role="user", content=user_message))

        # Show "typing…" immediately — gives instant feedback while LLM warms up
        try:
            await update.message.chat.send_action(ChatAction.TYPING)
        except Exception as e:
            logger.warning(f"Failed to send TYPING action to user {user_id}: {e}")

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | object] = asyncio.Queue()
        messages_snapshot = list(session.messages)
        system_prompt = self.system_prompt

        def _producer() -> None:
            """
            Runs in a thread-pool. Feeds sync generator chunks into the async
            queue via call_soon_threadsafe (the only safe cross-thread call).
            """
            try:
                for chunk in self.provider.stream(
                    messages=messages_snapshot, system=system_prompt
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception:
                loop.call_soon_threadsafe(queue.put_nowait, _STREAM_END)
                raise
            else:
                loop.call_soon_threadsafe(queue.put_nowait, _STREAM_END)

        producer_future = loop.run_in_executor(None, _producer)

        full_response = ""
        buffer = ""
        max_chunk_size = 3500
        streaming_succeeded = False

        try:
            # LLM streaming phase — consume chunks from producer thread
            try:
                while True:
                    chunk = await queue.get()
                    if chunk is _STREAM_END:
                        break
                    full_response += chunk
                    buffer += chunk
                    if len(buffer) >= max_chunk_size:
                        try:
                            await update.message.chat.send_action(ChatAction.TYPING)
                        except Exception:
                            pass  # non-critical UX feedback
                        try:
                            await self._safe_reply(update.message, buffer)
                        except Exception as e:
                            logger.error(
                                f"Failed to send chunk for user {user_id}: {e}", exc_info=True
                            )
                            raise
                        buffer = ""

                # Always await producer to surface any LLM-level exceptions
                await producer_future
                streaming_succeeded = True

            except Exception as e:
                logger.error(f"LLM streaming error for user {user_id}: {e}", exc_info=True)
                try:
                    await update.message.reply_text("Coach is unavailable. Try again in a moment.")
                except Exception as notification_err:
                    logger.error(
                        f"Failed to send error notification to user {user_id}: {notification_err}",
                        exc_info=True,
                    )
                return

            # Send final buffer only if streaming succeeded
            if buffer:
                try:
                    await self._safe_reply(update.message, buffer)
                except Exception as e:
                    logger.error(
                        f"Failed to send final buffer to user {user_id} ({type(e).__name__}): {e}",
                        exc_info=True,
                    )

        finally:
            # Append to session history only if streaming succeeded and we have content
            if streaming_succeeded and full_response:
                session.messages.append(Message(role="assistant", content=full_response))

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.handle_start(update, context)
