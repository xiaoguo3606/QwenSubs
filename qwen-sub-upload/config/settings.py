"""Configuration management — read/write JSON config file."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CONFIG_FILE = CONFIG_DIR / "settings.json"

DEFAULT_CONFIG: dict[str, Any] = {
    # Language
    "lang": "zh",
    # Model
    "model_source": "modelscope",
    "model_dir": "models",
    "asr_model": "Qwen/Qwen3-ASR-0.6B",
    "aligner_model": "Qwen/Qwen3-ForcedAligner-0.6B",
    # Hardware
    "device": "auto",
    "dtype": "bfloat16",
    "asr_model_size": "0.6B",
    # LLM
    "llm_enabled": False,
    "llm_type": "ollama",
    "ollama_endpoint": "http://localhost:11434",
    "ollama_model": "",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_api_key": "",
    "openai_model": "",
    # Output
    "default_output_format": "srt",
    "punctuation_remove_enabled": False,
    "punctuation_chars": "\"\"【】《》（）",
}


def load() -> dict[str, Any]:
    """Load config from file, merging with defaults."""
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULT_CONFIG)


def save(config: dict[str, Any]) -> None:
    """Save config to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def set_key(key: str, value: Any) -> None:
    cfg = load()
    cfg[key] = value
    save(cfg)


def get_model_path(model_id: str) -> str:
    """Resolve local path for a model ID (relative paths resolved against project root)."""
    raw = get("model_dir")
    model_dir = Path(raw)
    if not model_dir.is_absolute():
        model_dir = Path(__file__).resolve().parent.parent / raw
    model_name = model_id.replace("--", "/")
    return str(model_dir / model_name)
