"""Model download management — supports ModelScope, HF-Mirror, HuggingFace."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

MODEL_SOURCES = {
    "modelscope": {
        "env": {},
        "cmd": ["modelscope", "download", "--model", "{model_id}", "--local_dir", "{local_dir}"],
    },
    "hf-mirror": {
        "env": {"HF_ENDPOINT": "https://hf-mirror.com"},
        "cmd": ["huggingface-cli", "download", "{model_id}", "--local-dir", "{local_dir}"],
    },
    "huggingface": {
        "env": {},
        "cmd": ["huggingface-cli", "download", "{model_id}", "--local-dir", "{local_dir}"],
    },
}

# Model list with model_id and display name
MODELS = [
    {
        "id": "Qwen/Qwen3-ASR-1.7B",
        "name": "Qwen3-ASR-1.7B",
        "size_gb": 4.7,
        "type": "asr",
    },
    {
        "id": "Qwen/Qwen3-ASR-0.6B",
        "name": "Qwen3-ASR-0.6B",
        "size_gb": 1.9,
        "type": "asr",
    },
    {
        "id": "Qwen/Qwen3-ForcedAligner-0.6B",
        "name": "Qwen3-ForcedAligner-0.6B",
        "size_gb": 1.9,
        "type": "aligner",
    },
]


def download_model(
    model_id: str,
    local_dir: str,
    source: str = "modelscope",
    progress_callback: Callable[[str], None] | None = None,
) -> None:
    """Download model from specified source to local directory."""
    source_config = MODEL_SOURCES.get(source)
    if not source_config:
        raise ValueError(f"Unsupported model source: {source}")

    local_path = Path(local_dir)
    local_path.mkdir(parents=True, exist_ok=True)

    cmd = _build_cmd(source_config, model_id, str(local_path))

    if progress_callback:
        progress_callback(f"正在从 {source} 下载 {model_id}...")

    env = dict(source_config["env"])
    if source == "hf-mirror":
        # Ensure huggingface-cli is installed
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "huggingface_hub"],
            check=True, capture_output=True,
        )

    result = subprocess.run(cmd, env=_build_env(env), capture_output=True, text=True)

    if result.returncode != 0:
        err_tail = result.stderr.strip()[-200:]
        raise RuntimeError(f"模型下载失败: {model_id} (source: {source})\n{err_tail}")

    if progress_callback:
        progress_callback(f"{model_id} 下载完成")


def _build_env(extra: dict | None = None) -> dict:
    """Return environment with venv Scripts added to PATH and optional extras merged."""
    env = os.environ.copy()
    scripts_dir = str(Path(sys.executable).parent)
    path = env.get("PATH", "")
    if scripts_dir not in path:
        env["PATH"] = scripts_dir + os.pathsep + path
    if extra:
        env.update(extra)
    return env


def _build_cmd(source_config: dict, model_id: str, local_dir: str) -> list[str]:
    """Build subprocess command from source config."""
    cmd = [
        part.format(model_id=model_id, local_dir=str(local_dir))
        for part in source_config["cmd"]
    ]
    return cmd


def download_model_with_progress(
    model_id: str, local_dir: str, source: str = "modelscope",
):
    """Generator that yields (progress_float, status_text) in real-time."""
    source_config = MODEL_SOURCES.get(source)
    if not source_config:
        raise ValueError(f"Unsupported model source: {source}")

    local_path = Path(local_dir)
    local_path.mkdir(parents=True, exist_ok=True)

    cmd = _build_cmd(source_config, model_id, str(local_path))

    env = dict(source_config["env"])
    if source == "hf-mirror":
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "huggingface_hub"],
            check=True, capture_output=True,
        )

    yield 0.0, f"正在连接 {source}..."

    process = subprocess.Popen(
        cmd, env=_build_env(env),
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        universal_newlines=True, bufsize=1,
    )

    stderr_lines: list[str] = []
    for line in process.stderr:
        line = line.strip()
        stderr_lines.append(line)
        pct_match = re.search(r"(\d+)%", line)
        if pct_match:
            pct = int(pct_match.group(1)) / 100.0
            text = re.sub(r"\|[█▌░=#\-><]+\|", "", line).strip()
            yield pct, text

    process.wait()
    if process.returncode != 0:
        # Include last 5 lines of stderr for diagnostics
        tail = "\n".join(stderr_lines[-5:])
        raise RuntimeError(f"模型下载失败: {model_id} (source: {source})\n{tail}")
    yield 1.0, f"{model_id} 下载完成"


def delete_model(local_dir: str) -> None:
    """Delete model files from disk."""
    import shutil
    path = Path(local_dir)
    if not path.exists():
        return
    shutil.rmtree(path)


def is_model_downloaded(local_dir: str) -> bool:
    """Check if model files exist in local directory."""
    path = Path(local_dir)
    if not path.exists():
        return False
    # Check for common model files
    indicators = ["config.json", "model-00001-of-00002.safetensors"]
    for ind in indicators:
        if (path / ind).exists():
            return True
    # Fallback: check if directory is non-empty
    return any(path.iterdir())
