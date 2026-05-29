"""Detect available hardware (CUDA / MPS / CPU) and VRAM capacity."""

from __future__ import annotations

import logging
import subprocess
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


def _nvidia_smi_vram() -> float:
    """Try to get total VRAM from nvidia-smi (works even if torch has no CUDA)."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return round(int(result.stdout.strip()) / 1024, 1)
    except Exception:
        pass
    return 0.0


def _nvidia_smi_name() -> str:
    """Get GPU name from nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _python_torch_check(info: HardwareInfo) -> bool:
    """Check if torch has CUDA; returns True if NVIDIA GPU should be available."""
    import torch

    if torch.cuda.is_available():
        info.device = "cuda"
        info.device_name = torch.cuda.get_device_name(0)
        total = 0.0
        try:
            total = torch.cuda.get_device_properties(0).total_mem / (1024 ** 3)
            info.vram_gb = round(total, 1)
        except Exception:
            info.vram_gb = 0.0

        # try reserved memory
        try:
            reserved = torch.cuda.memory_reserved(0) / (1024 ** 3)
            if reserved > 0:
                info.vram_gb = round(total - reserved, 1)
        except Exception:
            pass

        return True  # CUDA detected
    else:
        # Check if NVIDIA GPU exists but torch lacks CUDA
        vram = _nvidia_smi_vram()
        gpu_name = _nvidia_smi_name()
        if vram > 0 and gpu_name:
            info.device_name = gpu_name
            info.vram_gb = vram
            info.warnings.append(
                f"检测到 {gpu_name}（{vram}GB），但当前 PyTorch 未包含 CUDA 支持。\n"
                "请安装 CUDA 版 PyTorch: pip install torch>=2.0 --index-url https://download.pytorch.org/whl/cu124"
            )
            return False  # has GPU but torch can't use it

    return False


def _check_cuda(info: HardwareInfo) -> None:
    if not _python_torch_check(info):
        return  # No CUDA-capable torch found

    vram_gb = info.vram_gb

    if vram_gb >= 6.0:
        info.recommended_model = "Qwen/Qwen3-ASR-1.7B"
        info.recommended_size = "1.7B"
    elif vram_gb >= 3.0:
        info.recommended_model = "Qwen/Qwen3-ASR-0.6B"
        info.recommended_size = "0.6B"
    else:
        info.recommended_model = "Qwen/Qwen3-ASR-0.6B"
        info.recommended_size = "0.6B"
        info.warnings.append("显存较低，推荐使用量化版本或 0.6B 模型")


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
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=5,
        )
        total_ram = int(result.stdout.strip()) / (1024 ** 3)
        info.vram_gb = round(total_ram * 0.3, 1)
    except Exception:
        info.vram_gb = 8.0

    if info.vram_gb >= 6.0:
        info.recommended_model = "Qwen/Qwen3-ASR-1.7B"
        info.recommended_size = "1.7B"
    else:
        info.recommended_model = "Qwen/Qwen3-ASR-0.6B"
        info.recommended_size = "0.6B"


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
