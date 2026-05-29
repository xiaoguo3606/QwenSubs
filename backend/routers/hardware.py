"""Hardware detection endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from utils.hardware_detector import detect

router = APIRouter()


@router.get("/hardware")
async def get_hardware():
    info = detect()
    return {
        "device": info.device,
        "device_name": info.device_name,
        "vram_gb": info.vram_gb,
        "recommended_model": info.recommended_model,
        "recommended_size": info.recommended_size,
        "can_run_asr": info.can_run_asr,
        "warnings": info.warnings,
        "platform_device_map": {
            "mps": info.device == "mps",
            "cuda": info.device == "cuda",
        },
    }
