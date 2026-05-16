import re
import sys

from coach.day_plan import render_trainings_overview
from coach.llm import Message, get_provider
from coach.paths import get_resource_path
from coach.programs import ActiveProgramNotConfigured, load_active_program


class CoachCLI:
    def __init__(self) -> None:
        self.history: list[Message] = []
        self.provider = None
        self.system_prompt: str | None = None
        self.program: dict | None = None

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
        plain = re.sub(r'<[^>]+>', '', overview)
        return base_prompt + "\n\n## CURRENT PROGRAM SNAPSHOT\n\n" + plain

    def _stream_response(self) -> str | None:
        full_response = ""
        try:
            for chunk in self.provider.stream(self.history, system=self.system_prompt):
                sys.stdout.write(chunk)
                sys.stdout.flush()
                full_response += chunk
        except (ConnectionError, TimeoutError) as e:
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

        if user_input == "/help":
            print(
                "Commands:\n"
                "  /quit   — exit\n"
                "  /reset  — clear conversation history\n"
                "  /help   — show this message"
            )
            return True

        self.history.append(Message(role="user", content=user_input))
        response = self._stream_response()
        if response is not None:
            self.history.append(Message(role="assistant", content=response))
        else:
            # On error, remove the user message that wasn't processed
            self.history.pop()
        return True
