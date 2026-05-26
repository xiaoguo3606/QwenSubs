"""Upload endpoint — accept audio file, convert to 16kHz mono WAV."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from core.audio_processor import convert_to_16k_mono, get_audio_duration, is_audio_file

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in {
        ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma", ".opus",
    }:
        raise HTTPException(400, f"Unsupported audio format: {ext}")

    file_id = str(uuid.uuid4())
    file_dir = UPLOAD_DIR / file_id
    file_dir.mkdir(parents=True, exist_ok=True)

    original_path = file_dir / f"original{ext}"
    content = await file.read()
    original_path.write_bytes(content)

    converted_path = file_dir / "converted.wav"
    try:
        convert_to_16k_mono(str(original_path), str(converted_path))
    except Exception as e:
        # Clean up on failure
        import shutil
        shutil.rmtree(file_dir, ignore_errors=True)
        raise HTTPException(500, f"Audio conversion failed: {e}")

    duration = get_audio_duration(str(converted_path))

    return {
        "file_id": file_id,
        "filename": file.filename,
        "duration": duration,
        "format": ext.lstrip("."),
    }
