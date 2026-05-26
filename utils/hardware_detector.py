"""Detect available hardware (CUDA / MPS / CPU) and VRAM capacity."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class HardwareInfo:
    device: str = "cpu"           # "cuda" | "mps" | "cpu"
    device_name: str = ""
    vram_gb: float = 0.0
    recommended_model: str = "Qwen/Qwen3-ASR-0.6B"
    recommended_size: str = "0.6B"
    can_run_asr: bool = True
    warnings: list[str] = field(default_factory=list)


def detect() -> HardwareInfo:
    """Detect hardware and return recommendations."""
    info = HardwareInfo()

    _check_cuda(info)
    if info.device == "cpu":
        _check_mps(info)

    logger.info(
        "Hardware: device=%s, name=%s, vram=%.1fGB, rec=%s",
        info.device, info.device_name, info.vram_gb, info.recommended_model,
    )
    return info


def _check_cuda(info: HardwareInfo) -> None:
    import torch
    if not torch.cuda.is_available():
        return

    info.device = "cuda"
    info.device_name = torch.cuda.get_device_name(0)
    total = 0.0
    try:
        total = torch.cuda.get_device_properties(0).total_mem / (1024 ** 3)
        info.vram_gb = round(total, 1)
    except Exception:
        info.vram_gb = 0.0

    if info.vram_gb >= 6.0:
        info.recommended_model = "Qwen/Qwen3-ASR-1.7B"
        info.recommended_size = "1.7B"
    elif info.vram_gb >= 3.0:
        info.recommended_model = "Qwen/Qwen3-ASR-0.6B"
        info.recommended_size = "0.6B"
    else:
        info.recommended_model = "Qwen/Qwen3-ASR-0.6B"
        info.recommended_size = "0.6B"
        info.warnings.append("显存较低，推荐使用量化版本或 0.6B 模型")

    # try reserved memory
    try:
        reserved = torch.cuda.memory_reserved(0) / (1024 ** 3)
        if reserved > 0:
            info.vram_gb = round(total - reserved, 1)
    except Exception:
        pass


def _check_mps(info: HardwareInfo) -> None:
    import torch
    if not torch.backends.mps.is_available():
        info.device = "cpu"
        info.device_name = "CPU"
        info.warnings.append("未检测到 GPU，将使用 CPU 运行（速度较慢）")
        return

    info.device = "mps"
    info.device_name = "Apple Silicon (MPS)"
    import platform
    import subprocess
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=5,
        )
        total_ram = int(result.stdout.strip()) / (1024 ** 3)
        # Apple Silicon shares RAM, assume ~30% available for GPU
        info.vram_gb = round(total_ram * 0.3, 1)
    except Exception:
        info.vram_gb = 8.0  # conservative fallback

    if info.vram_gb >= 6.0:
        info.recommended_model = "Qwen/Qwen3-ASR-1.7B"
        info.recommended_size = "1.7B"
    else:
        info.recommended_model = "Qwen/Qwen3-ASR-0.6B"
        info.recommended_size = "0.6B"
