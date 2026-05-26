"""Qwen3-ForcedAligner wrapper for text-audio forced alignment."""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)


def _resolve_device(device: str) -> str:
    import torch
    if device == "auto" or device == "cuda":
        if torch.cuda.is_available():
            return "cuda:0"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    return device


class ForcedAligner:
    """Wrapper around Qwen3-ForcedAligner for word-level timestamp alignment."""

    def __init__(
        self,
        model_path: str,
        device: str = "auto",
        dtype: str = "bfloat16",
        progress_callback: Callable[[str], None] | None = None,
    ):
        self.model_path = model_path
        self.device = device
        self.dtype = dtype
        self.progress_callback = progress_callback
        self._model = None

    def _log(self, msg: str) -> None:
        logger.info(msg)
        if self.progress_callback:
            self.progress_callback(msg)

    def load(self) -> None:
        """Load the forced alignment model."""
        if self._model is not None:
            return

        self._log("正在加载强制对齐模型...")
        import torch
        from qwen_asr import Qwen3ForcedAligner

        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        pt_dtype = dtype_map.get(self.dtype, torch.bfloat16)

        self._model = Qwen3ForcedAligner.from_pretrained(
            self.model_path,
            dtype=pt_dtype,
            device_map=_resolve_device(self.device),
        )
        self._log("强制对齐模型加载完成")

    def align(
        self,
        audio_path: str,
        text: str,
        language: str = "Chinese",
    ) -> dict:
        """Align text with audio and return word-level timestamps.

        Returns:
            dict with:
                - text: original text
                - timestamps: list of {text, start_time, end_time}
        """
        if self._model is None:
            self.load()

        self._log("正在执行强制对齐...")

        results = self._model.align(
            audio=audio_path,
            text=text,
            language=language,
        )

        timestamps = []
        for item in results[0]:
            timestamps.append({
                "text": item.text,
                "start_time": item.start_time,
                "end_time": item.end_time,
            })

        self._log(f"对齐完成，共 {len(timestamps)} 个字词")
        return {
            "text": text,
            "timestamps": timestamps,
        }

    def unload(self) -> None:
        """Release model from memory."""
        self._model = None
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self._log("模型已释放")
