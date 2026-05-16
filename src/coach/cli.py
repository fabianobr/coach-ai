import re
import sys
from datetime import datetime

from coach.day_plan import render_day_plan_formatted_list, render_day_plan_summary, render_trainings_overview
from coach.llm import Message, get_provider
from coach.logger import ExerciseStatus, ExerciseResult, PRType, SessionLogger
from coach.paths import get_resource_path
from coach.programs import (
    ActiveProgramNotConfigured,
    InvalidProgramId,
    ProgramAlreadyExists,
    ProgramNotFound,
    clone_program,
    get_program,
    list_programs,
    load_active_program,
    switch_program,
)


def _plain(text: str) -> str:
    """Strip Telegram HTML tags and decode the entities used in this codebase."""
    text = re.sub(r'<[^>]+>', '', text)
    return text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')


class CoachCLI:
    def __init__(self) -> None:
        self.history: list[Message] = []
        self.provider = None
        self.system_prompt: str | None = None
        self.program: dict | None = None
        self.current_day: str | None = None
        self._session_exercises: list[ExerciseResult] = []

    def run(self) -> None:
        try:
            base_prompt = self._load_system_prompt()
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)

        try:
            self.program = load_active_program()
        except ActiveProgramNotConfigured as e:
            print(f"Error: {e}")
            sys.exit(1)

        self.system_prompt = self._build_system_prompt_with_snapshot(base_prompt)

        try:
            self.provider = get_provider()
        except Exception as e:
            print(f"Error: failed to initialize provider — {e}")
            sys.exit(1)

        program_name = self.program.get("name", "unknown")
        print(f"Coach AI ready — program: {program_name}. Type /help for commands, /quit to exit.\n")

        try:
            while True:
                try:
                    user_input = input("You> ").strip()
                except EOFError:
                    break
                if not self._handle_input(user_input):
                    break
        except KeyboardInterrupt:
            print("\nGoodbye!")
            sys.exit(0)

    # ------------------------------------------------------------------
    # Input dispatch
    # ------------------------------------------------------------------

    def _handle_input(self, user_input: str) -> bool:
        if not user_input:
            return True

        if user_input == "/quit":
            print("Goodbye!")
            return False

        if user_input == "/reset":
            self.history.clear()
            print("History cleared.")
            return True

        if user_input.startswith("/help") or user_input.startswith("/start"):
            self._cmd_help()
            return True

        if user_input.startswith("/day"):
            self._cmd_day(user_input)
            return True

        if user_input.startswith("/trainings"):
            self._cmd_trainings()
            return True

        if user_input.startswith("/training"):
            self._cmd_training(user_input)
            return True

        if user_input.startswith("/status"):
            self._cmd_status()
            return True

        if user_input.startswith("/done"):
            self._cmd_done()
            return True

        if user_input.startswith("/programs"):
            self._cmd_programs()
            return True

        if user_input.startswith("/program"):
            self._cmd_program(user_input)
            return True

        self.history.append(Message(role="user", content=user_input))
        response = self._stream_response()
        if response is not None:
            self.history.append(Message(role="assistant", content=response))
        else:
            self.history.pop()
        return True

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _cmd_help(self) -> None:
        valid_days = list(self.program.get("days", {}).keys()) if self.program else []
        days_str = "/".join(valid_days) if valid_days else "D1/D2/..."
        print(
            f"Commands:\n"
            f"  /day <DX>                   — Set training day and start session ({days_str})\n"
            f"  /trainings                  — Overview of all training days\n"
            f"  /training <DX>              — Exercises for a specific day (read-only)\n"
            f"  /status                     — See today's exercises\n"
            f"  /done                       — End session & save log\n"
            f"  /programs                   — List all training programs\n"
            f"  /program show [id]          — Show program details (defaults to active)\n"
            f"  /program switch <id>        — Switch active program\n"
            f"  /program clone <src> <dst>  — Clone a program as a starting point\n"
            f"  /reset                      — Clear conversation history\n"
            f"  /help                       — Show this message\n"
            f"  /quit                       — Exit"
        )

    def _cmd_day(self, user_input: str) -> None:
        parts = user_input.split()
        if len(parts) < 2:
            valid_days = list(self.program.get("days", {}).keys()) if self.program else []
            days_str = "/".join(valid_days) if valid_days else "D1/D2/..."
            print(f"Usage: /day <DX>  (e.g. /day {valid_days[0] if valid_days else 'D1'})")
            return

        day_id = parts[1].upper()
        valid_days = list(self.program.get("days", {}).keys()) if self.program else []

        if day_id not in valid_days:
            print(f"Invalid day '{day_id}'. Valid: {', '.join(valid_days)}")
            return

        self.current_day = day_id
        day_label = self.program["days"][day_id]["label"]
        print(f"✅ Training day set to {day_id} ({day_label})")

        formatted_list, total_volume = render_day_plan_formatted_list(self.program, day_id)
        if formatted_list:
            exercises = self.program["days"][day_id].get("exercises", [])
            print()
            print(_plain(formatted_list))
            print()
            print(_plain(render_day_plan_summary(day_id, total_volume, len(exercises))))

    def _cmd_trainings(self) -> None:
        if not self.program:
            print("Training program not loaded.")
            return
        print(_plain(render_trainings_overview(self.program)))

    def _cmd_training(self, user_input: str) -> None:
        parts = user_input.split()
        valid_days = list(self.program.get("days", {}).keys()) if self.program else []
        rest_days = self.program.get("rest_days", []) if self.program else []

        if len(parts) < 2:
            print(f"Unknown day. Valid options: {', '.join(valid_days)}.")
            return

        day_id = parts[1].upper()

        if day_id in rest_days:
            print(f"{day_id} is a rest day — no exercises planned. Valid training days are: {', '.join(valid_days)}.")
            return
        if day_id not in valid_days:
            print(f"Unknown day '{day_id}'. Valid options: {', '.join(valid_days)}.")
            return

        day_label = self.program["days"][day_id]["label"]
        print(f"{day_id} — {day_label}")

        exercises = self.program["days"][day_id].get("exercises", [])
        formatted_list, total_volume = render_day_plan_formatted_list(self.program, day_id)
        if formatted_list:
            print()
            print(_plain(formatted_list))
            print()
            print(_plain(render_day_plan_summary(day_id, total_volume, len(exercises))))

    def _cmd_status(self) -> None:
        if not self.program:
            print("Training program not loaded.")
            return
        if self.current_day is None or self.current_day not in self.program.get("days", {}):
            print("No training day set. Use /day <DX> first.")
            return

        day_label = self.program["days"][self.current_day].get("label", "")
        exercises = self.program["days"][self.current_day].get("exercises", [])
        formatted_list, total_volume = render_day_plan_formatted_list(self.program, self.current_day)

        print(f"📋 {self.current_day}: {day_label}")
        if formatted_list:
            print()
            print(_plain(formatted_list))
            print()
            print(_plain(render_day_plan_summary(self.current_day, total_volume, len(exercises))))

    def _cmd_done(self) -> None:
        if self.current_day is None:
            print("No training day set. Use /day <DX> first.")
            return

        logger_instance = SessionLogger()
        date_str = datetime.now().strftime("%Y-%m-%d")

        for exercise in self._session_exercises:
            logger_instance.record(exercise)

        day_label = self.program["days"].get(self.current_day, {}).get("label", "") if self.program else ""
        program_id = self.program.get("program_id", "") if self.program else ""

        try:
            logger_instance.save(
                self.current_day, date_str,
                program_id=program_id, day_label=day_label,
            )
            print(f"✅ Session complete! Workout saved for {self.current_day}.")
            self._session_exercises.clear()
            self.current_day = None
        except FileExistsError:
            print(f"⚠️  Workout for {date_str} already logged. Session data preserved.")
        except (PermissionError, OSError) as e:
            print(f"⚠️  Storage error: {e}")
        except Exception as e:
            print(f"⚠️  Workout could not be saved: {e}")

    def _cmd_programs(self) -> None:
        programs = list_programs()
        if not programs:
            print("No programs found in data/programs/.")
            return
        print("Training Programs\n")
        for p in programs:
            marker = "✅" if p["active"] else "  "
            print(f"{marker} {p['program_id']} — {p['name']}")

    def _cmd_program(self, user_input: str) -> None:
        parts = user_input.split()
        if len(parts) < 2:
            print(
                "Usage:\n"
                "  /program show [id]          — Show program details\n"
                "  /program switch <id>        — Switch active program\n"
                "  /program clone <src> <dst>  — Clone a program"
            )
            return

        subcmd = parts[1].lower()

        if subcmd == "show":
            prog_id = parts[2] if len(parts) > 2 else (self.program.get("program_id", "") if self.program else "")
            if not prog_id:
                print("No active program loaded.")
                return
            try:
                prog = get_program(prog_id) if len(parts) > 2 else self.program
            except ProgramNotFound:
                print(f"Program not found: {prog_id}")
                return
            print(prog.get("name", prog_id))
            print(f"ID: {prog_id}")
            if prog.get("description"):
                print(f"Description: {prog['description']}")
            if prog.get("created_at"):
                print(f"Created: {prog['created_at']}")
            print(f"Training days: {', '.join(prog.get('days', {}).keys())}")
            if prog.get("rest_days"):
                print(f"Rest days: {', '.join(prog['rest_days'])}")

        elif subcmd == "switch":
            if len(parts) < 3:
                print("Usage: /program switch <id>")
                return
            prog_id = parts[2]
            try:
                switch_program(prog_id)
                self.program = load_active_program()
                self.system_prompt = self._build_system_prompt_with_snapshot(
                    re.sub(r'\n\n## CURRENT PROGRAM SNAPSHOT.*', '', self.system_prompt or '', flags=re.DOTALL)
                )
                print(f"✅ Switched to program '{prog_id}'.")
            except ProgramNotFound:
                print(f"Program not found: {prog_id}")

        elif subcmd == "clone":
            if len(parts) < 4:
                print("Usage: /program clone <src> <dst>")
                return
            src_id, dst_id = parts[2], parts[3]
            try:
                clone_program(src_id, dst_id)
                print(f"✅ Cloned '{src_id}' → '{dst_id}'.")
                print(f"Edit data/programs/{dst_id}.json, then use /program switch {dst_id}.")
            except ProgramNotFound:
                print(f"Source program not found: {src_id}")
            except ProgramAlreadyExists:
                print(f"Program already exists: {dst_id}")
            except InvalidProgramId:
                print(f"Invalid program ID '{dst_id}'. Use only lowercase letters, digits, and hyphens.")

        else:
            print(f"Unknown subcommand '{subcmd}'. Use show, switch, or clone.")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_system_prompt(self) -> str:
        try:
            path = get_resource_path("SYSTEM_PROMPT.md")
        except FileNotFoundError as e:
            raise FileNotFoundError(str(e)) from e
        return path.read_text(encoding="utf-8")

    def _build_system_prompt_with_snapshot(self, base_prompt: str) -> str:
        if not self.program:
            return base_prompt
        overview = render_trainings_overview(self.program)
        plain = _plain(overview)
        return base_prompt + "\n\n## CURRENT PROGRAM SNAPSHOT\n\n" + plain

    def _stream_response(self) -> str | None:
        full_response = ""
        try:
            for chunk in self.provider.stream(self.history, system=self.system_prompt):
                sys.stdout.write(chunk)
                sys.stdout.flush()
                full_response += chunk
        except (ConnectionError, TimeoutError):
            print(f"\nNetwork error: Unable to reach LLM provider.")
            print("Your message was not sent. Please check your connection and try again.")
            return None
        except Exception as e:
            print(f"\nUnexpected error while streaming: {type(e).__name__}")
            print("Message was not saved. Please try again.")
            import logging
            logging.getLogger(__name__).error(f"Streaming error: {e}", exc_info=True)
            return None
        print()
        return full_response
