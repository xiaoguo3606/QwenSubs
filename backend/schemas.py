"""Pydantic models for all request/response schemas."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


# ── Upload ──

class UploadResponse(BaseModel):
    file_id: str = Field(description="UUID identifying the uploaded file")
    filename: str
    duration: float
    format: str


# ── Task management ──

TaskStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


class AsrStartRequest(BaseModel):
    file_id: str
    language: str = "auto"
    split_point: float = 0.0
    hint_text: str = ""
    strip_punct: bool = True
    strip_mid_punct: bool = False
    mid_punct_choices: list[str] = []
    space_replacement: bool = False
    capitalize: bool = False
    asr_model: str = ""


class AlignStartRequest(BaseModel):
    file_id: str
    text: str
    language: str = "Chinese"
    split_point: float = 0.0
    strip_punct: bool = True
    strip_mid_punct: bool = False
    mid_punct_choices: list[str] = []
    space_replacement: bool = False
    capitalize: bool = False


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: float = 0.0
    status_text: str = ""
    error: str | None = None
    created_at: float
    updated_at: float


class TimestampEntry(BaseModel):
    text: str
    start_time: float
    end_time: float


class SubtitleEntry(BaseModel):
    text: str
    start_time: float
    end_time: float


class TaskResultResponse(BaseModel):
    text: str
    timestamps: list[TimestampEntry]
    subtitle_entries: list[SubtitleEntry]


# ── Subtitles ──

class GenerateRequest(BaseModel):
    text: str
    timestamps: list[TimestampEntry]
    format: str = "srt"


class GenerateResponse(BaseModel):
    file_url: str


# ── Config ──

class ConfigResponse(BaseModel):
    device: str = ""
    dtype: str = "bfloat16"
    asr_model: str = ""
    aligner_model: str = ""
    model_dir: str = "models"
    llm_enabled: bool = False
    llm_type: str = "ollama"
    ollama_endpoint: str = ""
    ollama_model: str = ""
    openai_base_url: str = ""
    openai_api_key: str = ""
    openai_model: str = ""
    lang: str = "zh"


class ConfigUpdateRequest(BaseModel):
    device: str | None = None
    dtype: str | None = None
    asr_model: str | None = None
    aligner_model: str | None = None
    model_dir: str | None = None
    llm_enabled: bool | None = None
    llm_type: str | None = None
    ollama_endpoint: str | None = None
    ollama_model: str | None = None
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    openai_model: str | None = None
    lang: str | None = None


# ── Models ──

class ModelInfo(BaseModel):
    id: str
    name: str
    size_gb: float
    type: str
    downloaded: bool


class ModelListResponse(BaseModel):
    models: list[ModelInfo]


class ModelDownloadResponse(BaseModel):
    task_id: str


class ModelDownloadRequest(BaseModel):
    model_id: str
    source: str = "modelscope"


# ── Hardware ──

class HardwareInfo(BaseModel):
    device: str
    device_name: str
    vram_gb: float
    recommended_model: str
    recommended_size: str
