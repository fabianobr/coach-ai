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
    uptime_seconds: float
