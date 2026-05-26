"""Configuration endpoints — read/write settings."""

from __future__ import annotations

from fastapi import APIRouter

from config import settings as cfg
from backend.schemas import ConfigResponse, ConfigUpdateRequest

router = APIRouter()


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    return ConfigResponse(
        device=cfg.get("device", ""),
        dtype=cfg.get("dtype", "bfloat16"),
        asr_model=cfg.get("asr_model", ""),
        aligner_model=cfg.get("aligner_model", ""),
        model_dir=cfg.get("model_dir", "models"),
        llm_enabled=cfg.get("llm_enabled", False),
        llm_type=cfg.get("llm_type", "ollama"),
        ollama_endpoint=cfg.get("ollama_endpoint", ""),
        ollama_model=cfg.get("ollama_model", ""),
        openai_base_url=cfg.get("openai_base_url", ""),
        openai_api_key=cfg.get("openai_api_key", ""),
        openai_model=cfg.get("openai_model", ""),
        lang=cfg.get("lang", "zh"),
    )


@router.put("/config")
async def update_config(body: ConfigUpdateRequest):
    updates = body.model_dump(exclude_none=True)
    config = cfg.load()
    config.update(updates)
    cfg.save(config)
    return {"status": "saved"}
