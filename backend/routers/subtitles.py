"""Subtitle generation and download endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.schemas import GenerateRequest, GenerateResponse, TimestampEntry
from core.subtitle_builder import build_subtitles

router = APIRouter()

SUBTITLE_DIR = Path(__file__).resolve().parent.parent.parent / "subtitle_output"


@router.post("/subtitles/generate")
async def generate_subtitles(body: GenerateRequest):
    lines = [l for l in body.text.split("\n") if l.strip()]
    timestamps = [t.model_dump() for t in body.timestamps]

    try:
        content = build_subtitles(lines, timestamps, output_format=body.format)
    except Exception as e:
        raise HTTPException(500, f"Subtitle generation failed: {e}")

    ext = body.format if body.format in ("srt", "ass", "vtt") else "srt"
    fd, tmp_path = tempfile.mkstemp(suffix=f".{ext}", dir=str(SUBTITLE_DIR))
    import os
    os.write(fd, content.encode("utf-8"))
    os.close(fd)

    filename = Path(tmp_path).name
    return GenerateResponse(file_url=f"/api/subtitles/{filename}")


@router.get("/subtitles/{filename}")
async def download_subtitle(filename: str):
    file_path = SUBTITLE_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(
        path=str(file_path),
        media_type="text/plain",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
