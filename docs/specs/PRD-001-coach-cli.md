# PRD: Coach CLI Core (`python -m coach`)

## Problem Statement

The Python LLM abstraction layer (`src/coach/llm/`) has been built and can interface with multiple providers (Anthropic, OpenAI, Ollama, Gemini), but there is no entry point that wires this layer to the coaching system. Users cannot currently run the coach from the terminal or interact with it outside of Claude Code.

The CLI is the simplest and most direct interface for the coach-ai system, and it serves as the foundation for more complex interfaces (REST API, Telegram) to build upon.

## Goals

- **Interactive terminal session**: Create a REPL that accepts user input, streams coaching responses, and maintains conversation history within a session.
- **Load system prompt**: Read `SYSTEM_PROMPT.md` from the repository root at startup and use it as the system prompt for all LLM calls.
- **Real-time streaming**: Call `provider.stream()` and print response chunks to stdout as they arrive (no buffering).
- **Session history**: Maintain a `list[Message]` across user exchanges, allowing multi-turn conversations.
- **Clean exit**: Support `/quit` command and Ctrl+C to exit gracefully.
- **Debugging commands**: Provide `/reset` (clear history) and `/help` commands.

## Non-Goals

- PR detection (Session Logger, PRD-002)
- Automatic log persistence (Session Logger, PRD-002)
- Data parsing / tonnage computation (the LLM's responsibility)
- Configuration UI (use .env for provider selection)
- REST or Telegram interfaces (separate PRDs)

## User Stories

1. **As a gym user**, I want to run `python -m coach` and immediately start logging my workout without any setup.
   - Acceptance: Command starts, shows a prompt, accepts my first message.

2. **As a user**, I want to see streaming responses so I don't wait for the full response before reading.
   - Acceptance: Response text appears character-by-character, not all at once.

3. **As a user**, I want to have multi-turn conversations; my coaching history should be preserved within a session.
   - Acceptance: I can message "squat done 5x5", then immediately "bench next?" and the coach knows the context.

4. **As a user**, I want to exit cleanly with `/quit` or Ctrl+C without crashing.
   - Acceptance: Program prints "Goodbye!" and exits with code 0.

5. **As a user**, I want to reset my session history with `/reset` if I make a mistake.
   - Acceptance: `/reset` clears the message history, next message starts a fresh conversation.

## Functional Requirements

### Startup
- Load `SYSTEM_PROMPT.md` from the repo root (`Path(__file__).parent.parent.parent / "SYSTEM_PROMPT.md"`).
- If the file is missing, print an error message and exit with code 1.
- Initialize the LLM provider via `get_provider()` (reads `.env`).
- Print a welcome message: `"Coach AI ready. Type /help for commands, /quit to exit."`

### Main Loop
- Display prompt: `"You> "` (waiting for input).
- Accept user input via `input()`.
- Create a `Message(role="user", content=user_input)` and append to history.
- Call `provider.stream(messages=history, system=system_prompt_text)`.
- Print each chunk from `stream()` as it arrives (use `sys.stdout.flush()` for immediate visibility).
- After streaming completes, create a `Message(role="assistant", content=full_response)` and append to history.
- Return to prompt.

### Commands (detected by prefix `/`)
| Command | Behavior |
|---|---|
| `/quit` | Print "Goodbye!" and exit with code 0. |
| `/reset` | Clear history, print "History cleared." |
| `/help` | Print command list. |
| (other) | Treat as a regular message (no error). |

### Message History
- Use `list[Message]` as the authoritative history.
- Include both user and assistant messages.
- Pass to `provider.stream(messages=...)` on every call.

## Technical Requirements & Architecture

### File Structure
```
src/coach/
  __main__.py          (entry point: python -m coach)
  cli.py               (CoachCLI class)
```

### `__main__.py`
```python
from coach.cli import CoachCLI

if __name__ == "__main__":
    cli = CoachCLI()
    cli.run()
```

### `cli.py`
```python
from pathlib import Path
from coach.llm import get_provider, Message, config_from_env

class CoachCLI:
    def __init__(self):
        self.system_prompt_path = Path(__file__).parent.parent.parent / "SYSTEM_PROMPT.md"
        self.system_prompt = None
        self.provider = None
        self.history: list[Message] = []
    
    def run(self) -> None:
        # Load system prompt
        # Initialize provider
        # Main loop
        ...
    
    def _load_system_prompt(self) -> str:
        """Load SYSTEM_PROMPT.md or exit if missing."""
        ...
    
    def _handle_input(self, user_input: str) -> bool:
        """Process user input, return True to continue loop, False to exit."""
        ...
    
    def _stream_response(self) -> str:
        """Stream LLM response and return full text."""
        ...
```

### Reuse from `src/coach/llm/`
- `get_provider()` — instantiate LLM provider from `.env`
- `Message` — dataclass for role + content
- `config_from_env()` — not needed if `get_provider()` is called without args

### Path Resolution
```python
SYSTEM_PROMPT_PATH = Path(__file__).parent.parent.parent / "SYSTEM_PROMPT.md"
# Relative from src/coach/cli.py:
# → src/coach/ (parent)
# → src/ (parent.parent)
# → . (parent.parent.parent — repo root)
# → SYSTEM_PROMPT.md
```

## Error Handling

| Scenario | Behavior |
|---|---|
| Missing `SYSTEM_PROMPT.md` | Print `"Error: SYSTEM_PROMPT.md not found at {path}"` and `exit(1)`. |
| API error during stream | Catch exception, print `"Error: {exception}"`, allow user to retry (don't exit loop). |
| Ctrl+C (KeyboardInterrupt) | Catch, print `"Goodbye!"`, `exit(0)`. |
| `.env` not found or invalid config | Let `get_provider()` raise; handle in `run()` with clear message, `exit(1)`. |

## Data Flow

```
┌─────────────────────────────────────────┐
│ Load SYSTEM_PROMPT.md at startup        │
│ Initialize LLM provider                 │
│ Print welcome message                   │
└──────────────────┬──────────────────────┘
                   │
         ┌─────────▼──────────┐
         │ Display "You> "    │
         │ Accept input       │
         └─────────┬──────────┘
                   │
         ┌─────────▼──────────────────────────┐
         │ Is input a /command?               │
         │ (handle /quit, /reset, /help)      │
         └─────────┬──────────────────────────┘
                   │
         ┌─────────▼──────────────────────────┐
         │ Create Message(role=user,          │
         │              content=input)        │
         │ Append to history                  │
         └─────────┬──────────────────────────┘
                   │
         ┌─────────▼──────────────────────────┐
         │ Call provider.stream(               │
         │   messages=history,                 │
         │   system=system_prompt)             │
         │ Print each chunk                   │
         └─────────┬──────────────────────────┘
                   │
         ┌─────────▼──────────────────────────┐
         │ Create Message(role=assistant,      │
         │              content=full_text)     │
         │ Append to history                  │
         └─────────┬──────────────────────────┘
                   │
         ┌─────────▼──────────────────────────┐
         │ Loop → prompt again                │
         └─────────────────────────────────────┘
```

## Testing Criteria

### Unit Tests (`tests/test_cli.py`)

1. **Initialization**: CLI loads system prompt and initializes provider without errors.
2. **Command routing**: `/quit`, `/reset`, `/help` are recognized and executed.
3. **History accumulation**: After two user messages + responses, history contains 4 entries (2 user + 2 assistant).
4. **Streaming output**: Mock `provider.stream()` to yield chunks; verify all chunks are printed to stdout.
5. **Error on missing system prompt**: If `SYSTEM_PROMPT.md` is missing, CLI exits with code 1.
6. **Error recovery**: If LLM call fails, error is printed and loop continues (doesn't crash).
7. **Ctrl+C handling**: KeyboardInterrupt is caught and exit is clean.

### Integration Test
1. **End-to-end flow**: Run `python -m coach`, send one message, receive a response, send `/quit`, verify exit code 0.

### Manual Verification
```bash
python -m coach
You> squat done 5x5 at 110kg
[full coaching response streams]
You> bench next?
[response references the squat completion]
You> /quit
Goodbye!
```

## Success Metric

**The CLI is complete and working when:**
1. `python -m coach` starts without errors.
2. A single user message triggers the full 5-step interaction loop and streams the response.
3. A second message in the same session references the prior context (history is preserved).
4. `/quit` exits cleanly with code 0.
5. Missing `SYSTEM_PROMPT.md` is caught and reported clearly.
6. All tests in `tests/test_cli.py` pass.

---

## Implementation Notes

- Use `sys.stdout.write(chunk)` + `sys.stdout.flush()` for streamed output (no newlines between chunks).
- Store the full response text as you iterate over stream chunks (for the Message object).
- The LLM layer's `stream()` method is an `Iterator[str]`; handle it robustly if the iterator is empty or raises mid-iteration.
