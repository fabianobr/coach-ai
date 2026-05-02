import time

from fastapi import APIRouter, Request

from coach.api.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(req: Request) -> HealthResponse:
    cfg = req.app.state.config
    uptime = time.time() - req.app.state.startup_time
    return HealthResponse(
        status="ok",
        provider=cfg.provider,
        model=cfg.model,
        uptime_seconds=round(uptime, 2),
    )
