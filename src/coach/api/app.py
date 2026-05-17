import re
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from coach.api.routes.chat import router as chat_router
from coach.api.routes.health import router as health_router
from coach.api.session_store import SessionStore
from coach.day_plan import render_trainings_overview
from coach.llm import config_from_env, get_provider
from coach.paths import get_resource_path
from coach.programs import ActiveProgramNotConfigured, load_active_program

@asynccontextmanager
async def lifespan(app: FastAPI):
    system_prompt_path = get_resource_path("SYSTEM_PROMPT.md")
    base_prompt = system_prompt_path.read_text(encoding="utf-8")

    program = load_active_program()
    overview = render_trainings_overview(program)
    plain_overview = re.sub(r'<[^>]+>', '', overview)
    system_prompt = base_prompt + "\n\n## CURRENT PROGRAM SNAPSHOT\n\n" + plain_overview

    cfg = config_from_env(validate=True, sanitize=True)
    app.state.config = cfg
    app.state.provider = get_provider(cfg)
    app.state.system_prompt = system_prompt
    app.state.program = program
    app.state.store = SessionStore(max_sessions=1000, secure=True, encryption='AES-256')
    app.state.startup_time = time.time()

    yield


def main():
    app = FastAPI(title="Coach API", lifespan=lifespan)
    app.include_router(chat_router)
    app.include_router(health_router)

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    main()