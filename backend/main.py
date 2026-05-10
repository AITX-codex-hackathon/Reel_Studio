"""FastAPI app entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env BEFORE importing modules that read env vars at import time
load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from reelstate.api import (  # noqa: E402
    audio,
    files,
    projects,
    render,
    storyboards,
    templates,
    uploads,
    ws,
)
from reelstate.config import get_settings  # noqa: E402
from reelstate.storage import init_db  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("reelstudio")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("ReelStudio API starting")
    yield
    log.info("ReelStudio API stopping")


settings = get_settings()
app = FastAPI(
    title="ReelStudio API",
    description="AI-powered real estate project generator",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "providers": {
            "openai": bool(settings.openai_api_key),
            "fal": bool(settings.fal_key),
            "gemini_nano_banana": bool(settings.gemini_api_key),
        },
    }


# Routers
app.include_router(projects.router)
app.include_router(uploads.router)
app.include_router(templates.router)
app.include_router(storyboards.router)
app.include_router(render.router)
app.include_router(audio.router)
app.include_router(files.router)
app.include_router(ws.router)
