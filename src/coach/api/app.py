import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from coach.api.routes.chat import router as chat_router
from coach.api.routes.health import router as health_router
from coach.api.session_store import SessionStore
from coach.llm import config_from_env, get_provider
from coach.paths import get_resource_path


@asynccontextmanager
async def lifespan(app: FastAPI):
    system_prompt_path = get_resource_path("SYSTEM_PROMPT.md")

    cfg = config_from_env()
    app.state.config = cfg
    app.state.provider = get_provider(cfg)
    app.state.system_prompt = system_prompt_path.read_text(encoding="utf-8")
    app.state.store = SessionStore()
    app.state.startup_time = time.time()

    yield


app = FastAPI(title="Coach API", lifespan=lifespan)
app.include_router(chat_router)
app.include_router(health_router)
