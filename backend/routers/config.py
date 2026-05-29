"""Configuration endpoints — read/write settings."""

from __future__ import annotations

from fastapi import APIRouter

from config import settings as cfg
from backend.schemas import ConfigResponse, ConfigUpdateRequest

router = APIRouter()


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


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
        openai_api_key=_mask_secret(cfg.get("openai_api_key", "")),
        openai_model=cfg.get("openai_model", ""),
        lang=cfg.get("lang", "zh"),
    )


@router.put("/config")
async def update_config(body: ConfigUpdateRequest):
    updates = body.model_dump(exclude_none=True)
    if "openai_api_key" in updates and "*" in (updates["openai_api_key"] or ""):
        del updates["openai_api_key"]
    config = cfg.load()
    config.update(updates)
    cfg.save(config)
    return {"status": "saved"}


@router.post("/config/test-llm")
async def test_llm_connection(body: ConfigUpdateRequest):
    """Test LLM connection with current or provided config."""
    from utils.llm_client import LLMClient

    try:
        # Use provided values, falling back to saved config
        llm_type = body.llm_type or cfg.get("llm_type", "ollama")
        ollama_endpoint = body.ollama_endpoint or cfg.get("ollama_endpoint", "http://localhost:11434")
        ollama_model = body.ollama_model or cfg.get("ollama_model", "qwen2.5")
        openai_base_url = body.openai_base_url or cfg.get("openai_base_url", "")
        openai_api_key = body.openai_api_key or cfg.get("openai_api_key", "")
        openai_model = body.openai_model or cfg.get("openai_model", "gpt-4o-mini")

        client = LLMClient(
            llm_type=llm_type,
            ollama_endpoint=ollama_endpoint,
            ollama_model=ollama_model,
            openai_base_url=openai_base_url,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
        )

        if llm_type == "ollama":
            import httpx
            url = f"{ollama_endpoint}/api/chat"
            resp = httpx.post(url, json={
                "model": ollama_model,
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            }, timeout=30)
            resp.raise_for_status()
        else:
            from openai import OpenAI
            client_openai = OpenAI(
                base_url=openai_base_url,
                api_key=openai_api_key,
            )
            client_openai.chat.completions.create(
                model=openai_model,
                messages=[{"role": "user", "content": "Hello"}],
                timeout=30,
            )

        return {"status": "ok", "message": "连接成功"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
