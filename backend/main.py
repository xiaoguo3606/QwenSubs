"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.model_registry import ModelRegistry
from backend.task_manager import TaskManager
from backend.routers import upload, asr, align, subtitles, config, models, tasks, hardware

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
SUBTITLE_DIR = Path(__file__).resolve().parent.parent / "subtitle_output"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(SUBTITLE_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.registry = ModelRegistry()
    app.state.task_manager = TaskManager()
    logger.info("Backend started: registry and task manager initialized")
    yield
    # Shutdown
    app.state.registry.unload_all()
    logger.info("Backend shut down: models unloaded")


app = FastAPI(title="QwenSubs", version="0.0.2", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(upload.router, prefix="/api")
app.include_router(asr.router, prefix="/api")
app.include_router(align.router, prefix="/api")
app.include_router(subtitles.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(hardware.router, prefix="/api")

@app.get("/api/health")
async def health():
    return {"status": "ok"}

# Serve uploaded audio for waveform playback
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# Serve built frontend
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
