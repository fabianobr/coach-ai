# PRD: REST API (`/chat` endpoint)

## Problem Statement

The coach system currently has two entry points: (1) Claude Code skill (interactive, user-facing); (2) Python CLI (terminal, single-user). There is no programmatic interface for external applications, frontends, or future integrations (e.g., Telegram bot, mobile app).

A RESTful API enables:
- External tools and scripts to call the coach
- The Telegram bot (PRD-004) to use the coach as a backend service
- Future web frontends to build on a stable interface
- Stateless scaling and multi-user concurrency

## Goals

- **POST /chat endpoint**: Accept a message + session_id, return the coaching response.
- **Streaming support**: Return responses via Server-Sent Events (SSE) for real-time streaming.
- **Session isolation**: Each session_id maintains independent conversation history.
- **Health check**: Expose `GET /health` for monitoring.
- **Startup initialization**: Load `SYSTEM_PROMPT.md` once at startup; use for all requests.
- **Configuration via environment**: Respect `.env` provider selection.

## Non-Goals

- Authentication / authorization (all sessions are anonymous)
- Rate limiting (apply at deployment layer if needed)
- Persistent session storage (in-memory only)
- Database integration
- OpenAPI/Swagger docs (can be added later)
- Multi-tenant isolation

## User Stories

1. **As a developer**, I want to POST a JSON message to `/chat` and get a streaming coaching response.
   - Acceptance: `curl -X POST http://localhost:8000/chat -d '{"session_id":"s1","message":"squat done 5x5"}' -H 'Content-Type: application/json'` returns the full response.

2. **As a developer**, I want to maintain conversation history across multiple requests using the same `session_id`.
   - Acceptance: First message "squat done 5x5", second message "bench?", response shows context about the squat.

3. **As a developer**, I want to stream responses instead of waiting for the full response.
   - Acceptance: Request with `"stream": true` returns `text/event-stream` with chunks arriving as `data: <text>\n\n`.

4. **As a developer**, I want a health check endpoint to monitor the service.
   - Acceptance: `GET /health` returns `{status: "ok", provider: "anthropic", model: "claude-haiku-4-5-20251001"}`.

5. **As a Telegram bot**, I want to call `/chat` on behalf of multiple users concurrently.
   - Acceptance: Requests with different `session_id` values maintain independent histories.

## Functional Requirements

### Endpoints

#### POST `/chat`

**Request body (JSON):**
```json
{
  "session_id": "user123",
  "message": "squat done 5x5 at 110kg",
  "stream": false
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `session_id` | string | Yes | Unique identifier for the session; used to maintain conversation history. |
| `message` | string | Yes | User message to send to the coach. |
| `stream` | boolean | No | Default: `false`. If `true`, return `text/event-stream`. |

**Response (non-streaming, `stream=false`):**
```json
{
  "session_id": "user123",
  "response": "### Language Spotter\n...\n### Ready?\n...",
  "pr_flags": ["volume", "weight"],
  "finish_reason": "stop"
}
```

**Response (streaming, `stream=true`):**
```
HTTP/1.1 200 OK
Content-Type: text/event-stream

data: ### Language Spotter
data: 
data: Great form on the squat! You said "done" — in English, we say "I've completed" or "I finished."
...
data: [DONE]
```

Streaming format:
- Each chunk of text is sent as `data: <text>\n\n` (SSE format).
- Chunks do not include newlines; caller is responsible for reassembling.
- End of response is signaled with `data: [DONE]\n\n`.

#### GET `/health`

**Response (200 OK):**
```json
{
  "status": "ok",
  "provider": "anthropic",
  "model": "claude-haiku-4-5-20251001",
  "uptime_seconds": 3600
}
```

### Session Management

- Sessions are stored in-memory as `dict[str, list[Message]]`.
- When a new `session_id` is received, create an empty history.
- Append user and assistant messages to the session's history.
- Sessions are never persisted or garbage-collected (in this version).

### Startup

- Load `SYSTEM_PROMPT.md` from the repo root at startup.
- Initialize the LLM provider via `get_provider()`.
- Print or log: `"Coach API started. Listening on http://0.0.0.0:8000"`
- If `SYSTEM_PROMPT.md` is missing, crash immediately with a clear error.

## Technical Requirements & Architecture

### File Structure
```
src/coach/api/
  __init__.py
  __main__.py              (entry point: python -m coach.api)
  app.py                   (FastAPI app, lifespan, routes)
  routes/
    __init__.py
    chat.py                (POST /chat handler)
    health.py              (GET /health handler)
  session_store.py         (SessionStore class)
  models.py                (Pydantic models)
```

### `models.py` (Pydantic request/response schemas)
```python
from pydantic import BaseModel

class ChatRequest(BaseModel):
    session_id: str
    message: str
    stream: bool = False

class ChatResponse(BaseModel):
    session_id: str
    response: str
    pr_flags: list[str] = []
    finish_reason: str = "stop"

class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    uptime_seconds: int
```

### `session_store.py`
```python
from coach.llm import Message

class SessionStore:
    def __init__(self):
        self.sessions: dict[str, list[Message]] = {}
    
    def get_or_create(self, session_id: str) -> list[Message]:
        """Get session history or create empty list if new."""
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        return self.sessions[session_id]
    
    def append(self, session_id: str, message: Message) -> None:
        """Append a message to the session."""
        history = self.get_or_create(session_id)
        history.append(message)
```

### `app.py`
```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from pathlib import Path
from coach.llm import get_provider, Message
from coach.api.session_store import SessionStore
from coach.api.models import ChatRequest, ChatResponse

# Global state (initialized in lifespan)
store = None
provider = None
system_prompt = None
startup_time = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global store, provider, system_prompt, startup_time
    
    store = SessionStore()
    provider = get_provider()
    
    system_prompt_path = Path(__file__).parent.parent.parent / "SYSTEM_PROMPT.md"
    if not system_prompt_path.exists():
        raise FileNotFoundError(f"SYSTEM_PROMPT.md not found at {system_prompt_path}")
    system_prompt = system_prompt_path.read_text()
    
    startup_time = time.time()
    print("Coach API started. Listening on http://0.0.0.0:8000")
    
    yield
    
    # Shutdown (cleanup if needed)
    ...

app = FastAPI(title="Coach API", lifespan=lifespan)

@app.post("/chat")
async def chat_endpoint(request: ChatRequest) -> ChatResponse | StreamingResponse:
    # Implement streaming or blocking based on request.stream
    ...

@app.get("/health")
async def health_endpoint() -> HealthResponse:
    # Return service status
    ...
```

### Streaming Implementation

For `stream=true`, use FastAPI `StreamingResponse` with SSE format:

```python
async def event_generator(session_id: str, message: str):
    history = store.get_or_create(session_id)
    history.append(Message(role="user", content=message))
    
    full_response = ""
    for chunk in provider.stream(messages=history, system=system_prompt):
        full_response += chunk
        yield f"data: {chunk}\n\n"
    
    history.append(Message(role="assistant", content=full_response))
    yield "data: [DONE]\n\n"

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    if request.stream:
        return StreamingResponse(
            event_generator(request.session_id, request.message),
            media_type="text/event-stream"
        )
    else:
        # Non-streaming: collect full response
        history = store.get_or_create(request.session_id)
        history.append(Message(role="user", content=request.message))
        
        response_text = ""
        for chunk in provider.stream(messages=history, system=system_prompt):
            response_text += chunk
        
        history.append(Message(role="assistant", content=response_text))
        
        return ChatResponse(
            session_id=request.session_id,
            response=response_text,
            pr_flags=[],
            finish_reason="stop"
        )
```

### Environment Variables

Reuse existing `.env` variables:
- `LLM_PROVIDER` (default: `anthropic`)
- `LLM_MODEL` (default: provider-specific)
- `LLM_API_KEY` (with fallbacks to vendor env vars)
- `LLM_BASE_URL` (for Ollama, proxies)

No new API-specific variables are required.

### Reuse from `src/coach/llm/`
- `get_provider()` — instantiate provider from `.env`
- `Message` — dataclass for role + content
- `LLMProvider.stream()` — streaming method

## Error Handling

| Scenario | Status | Response |
|---|---|---|
| Missing `session_id` in request | 400 | `{"detail": "session_id is required"}` |
| Missing `message` in request | 400 | `{"detail": "message is required"}` |
| LLM API error (rate limit, auth, network) | 502 | `{"detail": "LLM service unavailable: ..."}` |
| `SYSTEM_PROMPT.md` missing on startup | 500 | Crash immediately; logs clear error. |
| Unexpected exception | 500 | `{"detail": "Internal server error"}` |

**Streaming errors**: If an error occurs mid-stream, send `data: [ERROR: <message>]\n\n` and close the connection.

## Data Flow

```
┌──────────────────────────────────────────┐
│ Startup: Load SYSTEM_PROMPT.md           │
│ Initialize LLM provider                  │
│ Create SessionStore                      │
│ Start FastAPI server                     │
└──────────────────┬───────────────────────┘
                   │
         ┌─────────▼──────────────────────┐
         │ Client POST /chat               │
         │ {session_id, message, stream}   │
         └─────────┬──────────────────────┘
                   │
         ┌─────────▼──────────────────────┐
         │ Validate request                │
         │ Get or create session history   │
         │ Append user message             │
         └─────────┬──────────────────────┘
                   │
         ┌─────────▼──────────────────────┐
         │ Call provider.stream(           │
         │   history, system_prompt)       │
         └─────────┬──────────────────────┘
                   │
       ┌───────────┴──────────┐
       │                      │
   ┌───▼────────┐   ┌────────▼─────┐
   │ stream=true│   │ stream=false  │
   └───┬────────┘   └────────┬─────┘
       │                     │
       ▼                     ▼
  Return SSE        Collect full response
  "data: ...\n\n"   Return ChatResponse JSON
  Append to history  Append to history
```

## Testing Criteria

### Unit Tests (`tests/test_api.py`)

1. **POST /chat (non-streaming)**:
   - Valid request returns ChatResponse with response text ✓
   - Session history accumulates across requests ✓
   - Missing `session_id` returns 400 ✓
   - Missing `message` returns 400 ✓

2. **POST /chat (streaming)**:
   - Request with `stream=true` returns `text/event-stream` ✓
   - Chunks are formatted as SSE `data: ...\n\n` ✓
   - Stream ends with `data: [DONE]\n\n` ✓
   - Multiple chunks are received in order ✓

3. **GET /health**:
   - Returns 200 with correct status, provider, model ✓
   - Uptime is non-zero ✓

4. **Session isolation**:
   - Two requests with different `session_id` have independent history ✓

5. **Error scenarios**:
   - LLM error returns 502 ✓
   - Missing `SYSTEM_PROMPT.md` crashes startup ✓

### Integration Test
1. Start API server.
2. POST to `/chat` with `stream=false`, verify response.
3. POST same `session_id` with a follow-up message, verify context is preserved.
4. POST with `stream=true`, verify SSE format.
5. `GET /health`, verify 200 and correct fields.

### Manual Verification
```bash
# Start server
python -m coach.api

# In another terminal:
# Non-streaming request
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"user1","message":"squat done 5x5","stream":false}'

# Streaming request
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"user1","message":"bench?","stream":true}'

# Health check
curl http://localhost:8000/health
```

## Success Metrics

**The REST API is complete and working when:**
1. `python -m coach.api` starts and listens on port 8000.
2. `POST /chat` with a message returns a ChatResponse with the full coaching response.
3. Multiple messages with the same `session_id` show conversation history.
4. Streaming mode returns `text/event-stream` with properly formatted SSE chunks.
5. `GET /health` returns status 200 with provider and model info.
6. Two concurrent requests with different `session_id` values maintain independent history.
7. All tests in `tests/test_api.py` pass.

---

## Run & Deployment

**Development:**
```bash
uvicorn coach.api.app:app --reload --host 0.0.0.0 --port 8000
```

**Production (example with Gunicorn):**
```bash
gunicorn coach.api.app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

**Environment:**
Add to `.env`:
```
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-...
```

## Implementation Notes

- FastAPI handles automatic Pydantic validation; invalid JSON returns 422.
- Use `asyncio.gather()` or `async for` carefully with the LLM provider's synchronous `stream()` method (may need to wrap in executor).
- Session cleanup: In-memory sessions grow indefinitely; for production, add TTL or explicit session expiry.
