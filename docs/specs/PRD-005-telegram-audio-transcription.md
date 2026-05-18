# PRD: Telegram Audio Transcription

> **Status:** Pending Implementation

## Problem Statement

The Telegram bot currently processes only text messages. Users training at the
gym often prefer sending voice notes or audio clips because typing workout logs
between sets is inconvenient.

Audio input should be converted into text and then handled by the same coaching
flow used for typed messages.

## Goals

- **Accept Telegram voice notes and audio files**: Support `voice` and `audio`
  messages in the Telegram runtime.
- **Transcribe audio to text**: Convert speech into text before calling the coach
  LLM.
- **Reuse the current chat flow**: Treat the transcript as the user's message and
  preserve existing session history, streaming, formatting, and error handling.
- **Keep the feature opt-in**: Do not affect existing Telegram deployments unless
  audio support is explicitly enabled.
- **Fail clearly when unsupported**: If audio is enabled but the configured LLM
  provider cannot transcribe, the bot must fail at startup with a clear error.

## Non-Goals

- Audio responses from the bot.
- Speaker diarization.
- Group chat audio handling.
- Persistent audio storage.
- Supporting every LLM provider in v1.
- Photo, video, or arbitrary document interpretation.

## Functional Requirements

### Configuration

Add these environment variables:

| Variable | Default | Notes |
|---|---:|---|
| `TELEGRAM_AUDIO_ENABLED` | `false` | Enables Telegram audio handlers when `true`. |
| `TELEGRAM_AUDIO_MAX_MB` | `20` | Maximum accepted audio size before transcription. |
| `LLM_TRANSCRIPTION_MODEL` | `gpt-4o-mini-transcribe` | Transcription model for providers that need one. |

When `TELEGRAM_AUDIO_ENABLED=true`, the bot must validate during startup that the
configured `LLM_PROVIDER` supports audio transcription. In v1, only
`LLM_PROVIDER=openai` is expected to support this path.

### Telegram Message Handling

When audio is enabled, register handlers for:

- `filters.VOICE`
- `filters.AUDIO`

For each audio message:

1. Acquire the same per-user lock used for text messages.
2. Check file size against `TELEGRAM_AUDIO_MAX_MB`.
3. Download the Telegram file to a temporary directory.
4. Convert Telegram voice notes from OGG/Opus to a supported transcription format
   using `ffmpeg`.
5. Transcribe the resulting file through the configured provider.
6. If the transcript is non-empty, pass it into the existing text-message flow as
   `Message(role="user", content=transcript)`.
7. Stream the coach response back to Telegram exactly as text messages do today.
8. Delete temporary files after processing.

The bot should not send the transcript back to the user by default. The transcript
is an internal input normalization step.

### LLM Provider Interface

Extend the provider abstraction with an explicit audio transcription capability:

```python
supports_audio_transcription: bool

def transcribe_audio(self, file_path: Path, mime_type: str | None = None) -> str:
    ...
```

Provider behavior:

- `OpenAIProvider` implements transcription using the Audio Transcriptions API.
- `AnthropicProvider`, `GeminiProvider`, and `OllamaProvider` report unsupported
  in v1.
- Unsupported providers should raise a clear `NotImplementedError` or project
  specific equivalent when `transcribe_audio()` is called.

### Audio Conversion

Telegram voice notes commonly arrive as OGG/Opus. The OpenAI transcription API
documents support for `mp3`, `mp4`, `mpeg`, `mpga`, `m4a`, `wav`, and `webm`, so
voice notes must be converted before transcription.

Use `ffmpeg` as a system dependency:

```bash
ffmpeg -y -i input.ogg output.wav
```

If `ffmpeg` is missing or conversion fails, the bot should reply:

```text
Audio could not be transcribed. Please try again or send text.
```

### User-Facing Behavior

- If audio support is disabled, audio messages are ignored by this feature.
- If audio support is enabled and startup validation fails, the bot should not
  start.
- If download, conversion, or transcription fails, reply with a concise recovery
  message and do not call the chat LLM.
- If transcription returns empty text, reply:

```text
I could not detect speech in that audio.
```

- If transcription succeeds, the transcript is handled exactly like typed text.

## Test Plan

### Startup and Configuration

- Audio disabled: bot starts without validating transcription support.
- Audio enabled with `LLM_PROVIDER=openai`: bot registers text and audio handlers.
- Audio enabled with unsupported provider: bot startup fails with a clear error.
- Invalid `TELEGRAM_AUDIO_MAX_MB`: falls back to default or raises a clear config
  error.

### Telegram Audio Flow

- `voice` message downloads, converts with `ffmpeg`, transcribes, and reuses the
  text chat flow.
- `audio` message downloads, transcribes, and reuses the text chat flow.
- Oversized audio is rejected before download/transcription.
- Download failure sends the recovery message and does not call chat streaming.
- Conversion failure sends the recovery message and does not call chat streaming.
- Empty transcript sends the no-speech message.
- Temporary files are removed after success and failure.

### Provider Tests

- `OpenAIProvider.transcribe_audio()` calls
  `client.audio.transcriptions.create(...)` with:
  - configured transcription model
  - file handle
  - optional MIME metadata if supported by the SDK
- Unsupported providers expose `supports_audio_transcription=False`.
- Unsupported providers raise a clear error from `transcribe_audio()`.

## Acceptance Criteria

- A user can send a Telegram voice note and receive the normal coach response
  based on the transcribed text.
- A user can send a Telegram audio file and receive the normal coach response
  based on the transcribed text.
- Existing text messages and slash commands behave unchanged.
- Tests mock Telegram, provider SDKs, file download, and conversion; no real API
  calls are made.
- Documentation explains enabling audio, required provider support, and the
  `ffmpeg` dependency.

## References

- OpenAI Speech to Text:
  https://platform.openai.com/docs/guides/speech-to-text
- OpenAI GPT-4o mini Transcribe:
  https://platform.openai.com/docs/models/gpt-4o-mini-transcribe
