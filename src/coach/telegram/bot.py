import asyncio
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from coach.day_plan import render_day_plan_formatted_list, render_day_plan_summary, render_trainings_overview
from coach.llm import Message, get_provider
from coach.logger import SessionLogger
from coach.paths import get_resource_path
from coach.programs import (
    load_active_program,
    list_programs,
    switch_program,
    clone_program,
    get_program,
    ProgramNotFound,
    ProgramAlreadyExists,
    InvalidProgramId,
)
from coach.telegram.formatting import markdown_to_html
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
        self.program = load_active_program()

    def _build_system_prompt_with_snapshot(self) -> str:
        """Append current program snapshot to the system prompt."""
        if not self.system_prompt or not self.program:
            return self.system_prompt or ""
        overview = render_trainings_overview(self.program)
        plain = re.sub(r'<[^>]+>', '', overview)
        return self.system_prompt + "\n\n## CURRENT PROGRAM SNAPSHOT\n\n" + plain

    async def run(self) -> None:
        self.load_system_prompt()
        self.load_program()
        self.system_prompt = self._build_system_prompt_with_snapshot()
        self.provider = get_provider()

        # Validate audio transcription support if enabled
        self.audio_enabled = os.getenv("TELEGRAM_AUDIO_ENABLED", "false").lower() == "true"
        if self.audio_enabled and not self.provider.supports_audio_transcription:
            raise ValueError(
                f"TELEGRAM_AUDIO_ENABLED=true but {self.provider.__class__.__name__} "
                "does not support audio transcription. Use OpenAI provider or disable audio."
            )

        app = Application.builder().token(self.token).build()

        app.add_handler(CommandHandler("start", self.handle_start))
        app.add_handler(CommandHandler("day", self.handle_day))
        app.add_handler(CommandHandler("trainings", self.handle_trainings))
        app.add_handler(CommandHandler("training", self.handle_training))
        app.add_handler(CommandHandler("done", self.handle_done))
        app.add_handler(CommandHandler("status", self.handle_status))
        app.add_handler(CommandHandler("help", self.handle_help))
        app.add_handler(CommandHandler("programs", self.handle_programs))
        app.add_handler(CommandHandler("program", self.handle_program))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self.handle_audio))

        await app.initialize()
        await app.start()
        logger.info("Telegram bot started. Polling for messages...")
        await app.updater.start_polling()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            logger.info("Bot shutdown requested.")
        finally:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        self.store.get_or_create(user_id)
        valid_days = list(self.program.get("days", {}).keys()) if self.program else []
        days_str = "/".join(valid_days)
        await update.message.reply_text(
            "Welcome to <b>Coach AI</b>! 🏋️\n\n"
            "Send me a workout message or use:\n"
            f"<code>/day D1</code> — Set training day and start session ({days_str})\n"
            "<code>/trainings</code> — Overview of all training days\n"
            "<code>/training D1</code> — Exercises for a specific day (read-only)\n"
            "<code>/status</code> — See today's exercises\n"
            "<code>/done</code> — End session &amp; save log\n"
            "<code>/programs</code> — List all training programs\n"
            "<code>/program show [id]</code> — Show program details\n"
            "<code>/program switch &lt;id&gt;</code> — Switch active program\n"
            "<code>/program clone &lt;src&gt; &lt;dst&gt;</code> — Clone a program\n"
            "<code>/help</code> — Show this message",
            parse_mode=ParseMode.HTML
        )

    async def handle_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        session = self.store.get_or_create(user_id)

        valid_days = list(self.program.get("days", {}).keys()) if self.program else []
        days_str = "/".join(valid_days) if valid_days else "D1/D2/D4/D5"

        if not context.args or len(context.args) == 0:
            await update.message.reply_text(f"Usage: <code>/day D1</code> (or {days_str})", parse_mode=ParseMode.HTML)
            return

        day_id = context.args[0].upper()
        if day_id not in (self.program.get("days", {}) if self.program else {}):
            valid_codes = ", ".join(f"<code>{d}</code>" for d in valid_days)
            await update.message.reply_text(f"Invalid day. Use: {valid_codes}", parse_mode=ParseMode.HTML)
            return

        session.current_day = day_id
        day_label = self.program["days"][day_id]["label"] if self.program and day_id in self.program.get("days", {}) else "Unknown"

        # Render Day Plan table with weights and tonnage
        reply_lines = [f"✅ Training day set to <b>{day_id}</b> (<b>{day_label}</b>)"]

        if self.program and day_id in self.program.get("days", {}):
            day_data = self.program["days"][day_id]
            exercises = day_data.get("exercises", [])
            exercise_count = len(exercises)

            # Render formatted list with HTML styling
            formatted_list, total_volume = render_day_plan_formatted_list(self.program, day_id)
            if formatted_list:
                reply_lines.append("")
                reply_lines.append(formatted_list)
                reply_lines.append("")
                reply_lines.append(render_day_plan_summary(day_id, total_volume, exercise_count))

        await self._safe_reply(update.message, "\n".join(reply_lines))

    async def handle_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        session = self.store.get_or_create(user_id)

        if session.current_day is None:
            await update.message.reply_text(
                "No training day set. Use <code>/day D1</code> first.",
                parse_mode=ParseMode.HTML
            )
            return

        logger_instance = SessionLogger()
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Record accumulated exercises before saving
        for exercise in session.exercises:
            logger_instance.record(exercise)

        day_label = self.program["days"].get(session.current_day, {}).get("label", "") if self.program else ""
        program_id = self.program.get("program_id", "") if self.program else ""

        try:
            await asyncio.to_thread(logger_instance.save, session.current_day, date_str, program_id=program_id, day_label=day_label)
            await update.message.reply_text(
                f"✅ Session complete! Workout saved.\n"
                f"Great work on <b>{session.current_day}</b>! 💪",
                parse_mode=ParseMode.HTML
            )
            self.store.clear(user_id)
        except FileExistsError:
            await update.message.reply_text(
                f"⚠️ Workout for <b>{date_str}</b> already logged.\n"
                f"Session data preserved. Use /day to set a new day or continue.",
                parse_mode=ParseMode.HTML
            )
        except (PermissionError, OSError) as e:
            logger.error(f"File system error saving workout for user {user_id}: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Storage error. Workout could not be saved.", parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Unexpected error saving workout for user {user_id}: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Session preserved. Workout data could not be saved.", parse_mode=ParseMode.HTML)

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        session = self.store.get_or_create(user_id)

        if not self.program:
            await update.message.reply_text("Training program not loaded.", parse_mode=ParseMode.HTML)
            return
        if session.current_day is None or session.current_day not in self.program.get("days", {}):
            await update.message.reply_text(
                "No training day set. Use <code>/day D1</code> first.", parse_mode=ParseMode.HTML
            )
            return

        day_data = self.program["days"][session.current_day]
        day_label = day_data.get("label", "Unknown")
        exercises = day_data.get("exercises", [])
        exercise_count = len(exercises)

        # Use Day Plan formatted list with HTML styling
        reply_lines = [f"📋 <b>{session.current_day}: {day_label}</b> Exercises"]

        formatted_list, total_volume = render_day_plan_formatted_list(self.program, session.current_day)
        if formatted_list:
            reply_lines.append("")
            reply_lines.append(formatted_list)
            reply_lines.append("")
            reply_lines.append(render_day_plan_summary(session.current_day, total_volume, exercise_count))

        await self._safe_reply(update.message, "\n".join(reply_lines))

    async def _safe_reply(self, message, text: str) -> None:
        """
        Send text with HTML formatting. Converts any leaked Markdown to HTML first.
        If Telegram rejects the markup, fall back to plain text. Propagate unrecoverable errors.
        """
        text = markdown_to_html(text)
        try:
            await message.reply_text(text, parse_mode=ParseMode.HTML)
        except BadRequest as e:
            logger.warning(f"HTML rejected by Telegram ({e}); retrying as plain text")
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
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str | None = None
    ) -> None:
        """Implementation of message handling with per-user serialization via lock."""
        session = self.store.get_or_create(user_id)
        user_message = text if text is not None else update.message.text

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

    async def handle_trainings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.program:
            await update.message.reply_text("Training program not loaded.", parse_mode=ParseMode.HTML)
            return
        overview = render_trainings_overview(self.program)
        await self._safe_reply(update.message, overview)

    async def handle_training(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        valid_days = list(self.program.get("days", {}).keys()) if self.program else []
        rest_days = self.program.get("rest_days", []) if self.program else []

        if not context.args:
            valid_str = ", ".join(f"<code>{d}</code>" for d in valid_days)
            await update.message.reply_text(
                f"Unknown day. Valid options: {valid_str}.",
                parse_mode=ParseMode.HTML,
            )
            return

        day_id = context.args[0].upper()

        if day_id in rest_days:
            valid_str = ", ".join(valid_days)
            await update.message.reply_text(
                f"{day_id} is a rest day — no exercises planned. "
                f"Valid training days are {valid_str}.",
                parse_mode=ParseMode.HTML,
            )
            return
        if day_id not in valid_days:
            valid_str = ", ".join(f"<code>{d}</code>" for d in valid_days)
            await update.message.reply_text(
                f"Unknown day. Valid options: {valid_str}.",
                parse_mode=ParseMode.HTML,
            )
            return

        day_label = self.program["days"][day_id]["label"] if self.program and day_id in self.program.get("days", {}) else ""
        reply_lines = [f"📋 <b>{day_id} — {day_label}</b>"]

        if self.program and day_id in self.program.get("days", {}):
            exercises = self.program["days"][day_id].get("exercises", [])
            formatted_list, total_volume = render_day_plan_formatted_list(self.program, day_id)
            if formatted_list:
                reply_lines.append("")
                reply_lines.append(formatted_list)
                reply_lines.append("")
                reply_lines.append(render_day_plan_summary(day_id, total_volume, len(exercises)))

        await self._safe_reply(update.message, "\n".join(reply_lines))

    async def handle_programs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List all available programs, marking the active one."""
        programs = list_programs()
        if not programs:
            await update.message.reply_text("No programs found in data/programs/.", parse_mode=ParseMode.HTML)
            return
        lines = ["<b>Training Programs</b>\n"]
        for p in programs:
            marker = "✅ " if p["active"] else "   "
            lines.append(f"{marker}<b>{p['program_id']}</b> — {p['name']}")
        await self._safe_reply(update.message, "\n".join(lines))

    async def handle_program(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Dispatch /program subcommands: show, switch, clone."""
        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Usage:\n"
                "<code>/program show [id]</code> — Show program details\n"
                "<code>/program switch &lt;id&gt;</code> — Switch active program\n"
                "<code>/program clone &lt;src&gt; &lt;dst&gt;</code> — Clone a program",
                parse_mode=ParseMode.HTML,
            )
            return

        subcmd = args[0].lower()

        if subcmd == "show":
            if len(args) > 1:
                program_id = args[1]
            elif self.program:
                program_id = self.program.get("program_id", "")
            else:
                await update.message.reply_text("No active program loaded.", parse_mode=ParseMode.HTML)
                return
            try:
                prog = get_program(program_id) if len(args) > 1 else self.program
            except ProgramNotFound:
                await update.message.reply_text(f"Program not found: <code>{program_id}</code>", parse_mode=ParseMode.HTML)
                return
            name = prog.get("name", program_id)
            desc = prog.get("description", "")
            created = prog.get("created_at", "")
            days = list(prog.get("days", {}).keys())
            rest = prog.get("rest_days", [])
            lines = [
                f"<b>{name}</b>",
                f"ID: <code>{program_id}</code>",
            ]
            if desc:
                lines.append(f"Description: {desc}")
            if created:
                lines.append(f"Created: {created}")
            lines.append(f"Training days: {', '.join(days)}")
            if rest:
                lines.append(f"Rest days: {', '.join(rest)}")
            await self._safe_reply(update.message, "\n".join(lines))

        elif subcmd == "switch":
            if len(args) < 2:
                await update.message.reply_text("Usage: <code>/program switch &lt;id&gt;</code>", parse_mode=ParseMode.HTML)
                return
            program_id = args[1]
            try:
                switch_program(program_id)
                self.program = load_active_program()
                self.system_prompt = self._build_system_prompt_with_snapshot()
                await update.message.reply_text(
                    f"✅ Switched to program <b>{program_id}</b>.",
                    parse_mode=ParseMode.HTML,
                )
            except ProgramNotFound:
                await update.message.reply_text(f"Program not found: <code>{program_id}</code>", parse_mode=ParseMode.HTML)

        elif subcmd == "clone":
            if len(args) < 3:
                await update.message.reply_text("Usage: <code>/program clone &lt;src&gt; &lt;dst&gt;</code>", parse_mode=ParseMode.HTML)
                return
            src_id, dst_id = args[1], args[2]
            try:
                clone_program(src_id, dst_id)
                await update.message.reply_text(
                    f"✅ Cloned <b>{src_id}</b> → <b>{dst_id}</b>.\n"
                    f"Edit <code>data/programs/{dst_id}.json</code>, then use <code>/program switch {dst_id}</code>.",
                    parse_mode=ParseMode.HTML,
                )
            except ProgramNotFound:
                await update.message.reply_text(f"Source program not found: <code>{src_id}</code>", parse_mode=ParseMode.HTML)
            except ProgramAlreadyExists:
                await update.message.reply_text(f"Program already exists: <code>{dst_id}</code>", parse_mode=ParseMode.HTML)
            except InvalidProgramId:
                await update.message.reply_text(
                    f"Invalid program ID: <code>{dst_id}</code>. Use only lowercase letters, digits, and hyphens.",
                    parse_mode=ParseMode.HTML,
                )

        else:
            await update.message.reply_text(f"Unknown subcommand: <code>{subcmd}</code>. Use show, switch, or clone.", parse_mode=ParseMode.HTML)

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.handle_start(update, context)

    async def handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming voice and audio messages."""
        user_id = update.effective_user.id
        user_lock = self.store.get_lock(user_id)

        async with user_lock:
            await self._handle_audio_impl(update, context, user_id)

    async def _handle_audio_impl(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int
    ) -> None:
        """Implementation of audio handling with per-user serialization."""
        if not self.audio_enabled:
            await update.message.reply_text("⚠️ Voice messages are not enabled on this bot.")
            return

        # Get audio file info
        if update.message.voice:
            audio = update.message.voice
        elif update.message.audio:
            audio = update.message.audio
        else:
            await update.message.reply_text("Could not detect audio file.")
            return

        # Check file size against limit
        max_mb = float(os.getenv("TELEGRAM_AUDIO_MAX_MB", "20"))
        max_bytes = max_mb * 1024 * 1024
        if audio.file_size and audio.file_size > max_bytes:
            await update.message.reply_text(
                f"⚠️ Audio file too large. Maximum: {max_mb} MB.",
                parse_mode=ParseMode.HTML
            )
            return

        ogg_path = None
        wav_path = None
        try:
            # Download audio file
            file = await context.bot.get_file(audio.file_id)
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as ogg_file:
                ogg_path = ogg_file.name
            await file.download_to_drive(ogg_path)

            # Convert OGG/Opus to WAV using ffmpeg
            wav_path = ogg_path.replace(".ogg", ".wav")
            subprocess.run(
                ["ffmpeg", "-i", ogg_path, "-acodec", "pcm_s16le", "-ar", "16000", wav_path],
                capture_output=True,
                timeout=30,
                check=True,
            )

            # Transcribe audio
            try:
                transcript = self.provider.transcribe_audio(wav_path)
            except Exception as e:
                logger.error(f"Transcription failed for user {user_id}: {e}", exc_info=True)
                await update.message.reply_text(
                    "⚠️ Transcription failed. Try again with a clearer audio file."
                )
                return

            if not transcript or not transcript.strip():
                await update.message.reply_text(
                    "⚠️ No speech detected in audio. Try again."
                )
                return

            # Pass transcript through the same message handling logic
            await self._handle_message_impl(update, context, user_id, text=transcript)

        except subprocess.TimeoutExpired:
            logger.error(f"ffmpeg conversion timeout for user {user_id}")
            await update.message.reply_text(
                "⚠️ Audio processing timed out. Try a shorter clip."
            )
        except FileNotFoundError:
            logger.error(f"ffmpeg not found for user {user_id}")
            await update.message.reply_text(
                "⚠️ Audio processing not available. Retry later."
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed for user {user_id}: {e.stderr.decode()}", exc_info=True)
            await update.message.reply_text(
                "⚠️ Could not process audio file. Try again."
            )
        except Exception as e:
            logger.error(f"Audio handler error for user {user_id}: {e}", exc_info=True)
            await update.message.reply_text(
                "⚠️ Audio processing failed. Try again."
            )
        finally:
            # Clean up temporary files
            try:
                if ogg_path:
                    Path(ogg_path).unlink(missing_ok=True)
                if wav_path:
                    Path(wav_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to clean up temp files for user {user_id}: {e}")
