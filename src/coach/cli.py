import sys
from pathlib import Path

from coach.llm import Message, get_provider


class CoachCLI:
    def __init__(self) -> None:
        self.system_prompt_path = Path(__file__).parent.parent.parent / "SYSTEM_PROMPT.md"
        self.history: list[Message] = []
        self.provider = None
        self.system_prompt: str | None = None

    def run(self) -> None:
        self.system_prompt = self._load_system_prompt()
        try:
            self.provider = get_provider()
        except Exception as e:
            print(f"Error: failed to initialize provider — {e}")
            sys.exit(1)

        print("Coach AI ready. Type /help for commands, /quit to exit.\n")

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
        if not self.system_prompt_path.exists():
            print(f"Error: SYSTEM_PROMPT.md not found at {self.system_prompt_path}")
            sys.exit(1)
        return self.system_prompt_path.read_text(encoding="utf-8")

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
