from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from coach.api.models import ChatRequest, ChatResponse
from coach.llm import Message

router = APIRouter()


async def _event_generator(history, system_prompt, provider, store, session_id):
    full_response = ""
    try:
        for chunk in provider.stream(messages=history, system=system_prompt):
            full_response += chunk
            yield f"data: {chunk}\n\n"
    except Exception as e:
        yield f"data: [ERROR: {e}]\n\n"
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

    response_text = ""
    try:
        for chunk in provider.stream(messages=history, system=system_prompt):
            response_text += chunk
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM service unavailable: {e}")

    store.append(request.session_id, Message(role="assistant", content=response_text))
    return ChatResponse(session_id=request.session_id, response=response_text)
