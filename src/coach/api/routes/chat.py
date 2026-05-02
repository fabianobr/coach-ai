import asyncio
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from coach.api.models import ChatRequest, ChatResponse
from coach.llm import Message

router = APIRouter()
logger = logging.getLogger(__name__)


def _format_sse_chunk(chunk: str) -> str:
    """Format chunk for SSE transmission, escaping newlines per SSE spec."""
    lines = chunk.split("\n")
    return "".join(f"data: {line}\n" for line in lines[:-1]) + (f"data: {lines[-1]}\n\n" if lines[-1] else "\n")


async def _event_generator(history, system_prompt, provider, store, session_id) -> AsyncGenerator[str, None]:
    full_response = ""
    error_id = str(uuid.uuid4())[:8]
    chunks_received = 0

    try:
        stream_iterator = await asyncio.to_thread(
            lambda: provider.stream(messages=history, system=system_prompt)
        )
        for chunk in stream_iterator:
            full_response += chunk
            chunks_received += 1
            yield _format_sse_chunk(chunk)
    except asyncio.CancelledError:
        logger.debug(f"Session {session_id} stream cancelled after {chunks_received} chunks")
        return
    except Exception as e:
        logger.error(
            f"LLM streaming error [id={error_id}] for session {session_id} "
            f"after {chunks_received} chunks: {type(e).__name__}: {e}",
            exc_info=True
        )
        store.append(session_id, Message(role="assistant", content=f"[Error {error_id}]"))
        yield f"data: [ERROR {error_id}]\n\n"
        return

    store.append(session_id, Message(role="assistant", content=full_response))
    yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat(request: ChatRequest, req: Request):
    store = req.app.state.store
    provider = req.app.state.provider
    system_prompt = req.app.state.system_prompt

    store.append(request.session_id, Message(role="user", content=request.message))
    # Pass a snapshot so mutations after the call don't affect the recorded args
    history = list(store.get_or_create(request.session_id))

    if request.stream:
        return StreamingResponse(
            _event_generator(history, system_prompt, provider, store, request.session_id),
            media_type="text/event-stream",
        )

    try:
        response_text = await asyncio.to_thread(
            provider.chat, messages=history, system=system_prompt
        )
    except Exception as e:
        logger.error(f"LLM error for session {request.session_id}: {e}")
        raise HTTPException(status_code=502, detail="LLM service unavailable")

    store.append(request.session_id, Message(role="assistant", content=response_text))
    return ChatResponse(session_id=request.session_id, response=response_text)
