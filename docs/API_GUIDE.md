# REST API Guide

The coach-ai REST API is a FastAPI service that exposes the coaching experience
over HTTP. It shares the same LLM abstraction layer and system prompt as the
Telegram bot and CLI.

## Running the API

```bash
# Install required extras
pip install -e ".[anthropic,rest]"    # or openai, ollama, gemini

# Configure
cp .env.example .env                  # set LLM_PROVIDER, LLM_API_KEY, etc.

# Start the server (default: http://127.0.0.1:8000)
python -m coach.api
```

Override the bind address and port via environment variables:

```bash
HOST=0.0.0.0 PORT=9000 python -m coach.api
```

## Endpoints

### `GET /health`

Returns service status and uptime. No authentication required.

**Response:**

```json
{
  "status": "ok",
  "provider": "anthropic",
  "model": "claude-haiku-4-5-20251001",
  "uptime_seconds": 42.15
}
```

---

### `POST /chat`

Send a message and receive a coaching response.

**Request body:**

```json
{
  "session_id": "user-abc",
  "message": "squat done, 5x5 at 110kg",
  "stream": false
}
```

| Field | Type | Required | Description |
| :-- | :-- | :-- | :-- |
| `session_id` | string (max 128 chars) | yes | Identifies the conversation. Reuse the same ID to maintain history across calls. |
| `message` | string (max 32 000 chars) | yes | The user's message. |
| `stream` | boolean | no (default `false`) | Set to `true` for a streaming response (SSE). |

**Non-streaming response (`stream: false`):**

```json
{
  "session_id": "user-abc",
  "response": "🔤 Language Spotter\n\nYour message looks good! ...\n\n💪 Coach\n...",
  "pr_flags": [],
  "finish_reason": "stop"
}
```

**Streaming response (`stream: true`):**

Returns `Content-Type: text/event-stream`. Each chunk is a Server-Sent Event:

```
data: 🔤 Language

data:  Spotter

data: ...

data: [DONE]
```

On error, a single `data: [ERROR <id>]` event is emitted before the stream closes.

## Session Management

Sessions are stored **in memory**. Each unique `session_id` keeps its own
message history for the duration of the process. Sessions are lost on restart.

For multi-user deployments, use a unique `session_id` per user.

## Example: cURL

```bash
# Health check
curl http://127.0.0.1:8000/health

# Send a workout message
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "me", "message": "bench press 3x8 at 80kg"}'

# Streaming
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "me", "message": "bench press 3x8 at 80kg", "stream": true}'
```

## Example: Python

```python
import requests

base = "http://127.0.0.1:8000"

# Non-streaming
resp = requests.post(f"{base}/chat", json={
    "session_id": "my-session",
    "message": "squat done, 5x5 at 110kg",
})
print(resp.json()["response"])

# Streaming
with requests.post(f"{base}/chat", json={
    "session_id": "my-session",
    "message": "what are the cues for deadlift?",
    "stream": True,
}, stream=True) as resp:
    for line in resp.iter_lines():
        if line.startswith(b"data: ") and not line.endswith(b"[DONE]"):
            print(line[6:].decode(), end="", flush=True)
```
