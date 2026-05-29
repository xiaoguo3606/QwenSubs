"""Safe path resolution for uploads and generated subtitles."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException

UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads"
SUBTITLE_ROOT = Path(__file__).resolve().parent.parent / "subtitle_output"


def _ensure_under_root(path: Path, root: Path) -> Path:
    root = root.resolve()
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise HTTPException(400, "Invalid path")
    return resolved


def resolve_upload_dir(file_id: str) -> Path:
    try:
        uuid.UUID(file_id)
    except ValueError as exc:
        raise HTTPException(400, "Invalid file_id") from exc
    return _ensure_under_root(UPLOAD_ROOT / file_id, UPLOAD_ROOT)


def resolve_upload_wav(file_id: str) -> Path:
    wav = resolve_upload_dir(file_id) / "converted.wav"
    if not wav.is_file():
        raise HTTPException(404, "Uploaded file not found")
    return wav


def resolve_subtitle_file(filename: str) -> Path:
    if not filename or filename != Path(filename).name:
        raise HTTPException(400, "Invalid filename")
    return _ensure_under_root(SUBTITLE_ROOT / filename, SUBTITLE_ROOT)
