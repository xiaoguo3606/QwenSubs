"""Qwen3-ASR engine wrapper for speech recognition."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# Strip model metadata artifacts that can leak into text output
_ASR_TAG_RE = re.compile(r'(?:^|\s)language\s+\w+<asr_text>\s*', re.IGNORECASE)


def _clean_asr_text(text: str) -> str:
    """Remove model metadata artifacts that can leak into output text."""
    text = _ASR_TAG_RE.sub('', text)
    # Also strip any standalone <asr_text> tags
    if '<asr_text>' in text:
        text = text.replace('<asr_text>', '')
    return text.strip()


def _resolve_device(device: str) -> str:
    import torch
    if device == "auto" or device == "cuda":
        if torch.cuda.is_available():
            return "cuda:0"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    return device


class QwenASREngine:
    """Wrapper around Qwen3-ASR for transcribing audio with optional word timestamps."""

    def __init__(
        self,
        model_path: str,
        aligner_path: str | None = None,
        device: str = "auto",
        dtype: str = "bfloat16",
        progress_callback: Callable[[str], None] | None = None,
    ):
        self.model_path = model_path
        self.aligner_path = aligner_path
        self.device = device
        self.dtype = dtype
        self.progress_callback = progress_callback
        self._model = None

    def _log(self, msg: str) -> None:
        logger.info(msg)
        if self.progress_callback:
            self.progress_callback(msg)

    def load(self) -> None:
        """Load the ASR model (and forced aligner if configured)."""
        if self._model is not None:
            return

        self._log("正在加载 ASR 模型...")
        import torch
        from qwen_asr import Qwen3ASRModel

        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        pt_dtype = dtype_map.get(self.dtype, torch.bfloat16)

        device_map = _resolve_device(self.device)

        model = Qwen3ASRModel.from_pretrained(
            self.model_path,
            dtype=pt_dtype,
            device_map=device_map,
            max_new_tokens=4096,
            forced_aligner=self.aligner_path,
            forced_aligner_kwargs={
                "dtype": pt_dtype,
                "device_map": device_map,
            } if self.aligner_path else None,
        )
        self._model = model
        self._log("ASR 模型加载完成")

    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        hotwords: str | None = None,
    ) -> list[dict]:
        """Transcribe audio and return results with optional word timestamps.

        Returns:
            List of result dicts, each containing:
                - text: transcribed text
                - language: detected/used language
                - timestamps: list of {text, start_time, end_time} (if aligner loaded)
        """
        if self._model is None:
            self.load()

        self._log("正在识别音频...")

        kwargs = {
            "audio": audio_path,
            "return_time_stamps": True,
        }
        if language:
            kwargs["language"] = language
        if hotwords:
            kwargs["hotwords"] = hotwords

        results = list(self._model.transcribe(**kwargs))

        parsed = []
        for r in results:
            entry = {
                "text": _clean_asr_text(r.text),
                "language": r.language,
                "timestamps": [],
            }
            if hasattr(r, "time_stamps") and r.time_stamps:
                for ts in r.time_stamps:
                    entry["timestamps"].append({
                        "text": ts.text,
                        "start_time": ts.start_time,
                        "end_time": ts.end_time,
                    })
            parsed.append(entry)

        self._log("识别完成")
        return parsed

    def unload(self) -> None:
        """Release model from memory."""
        self._model = None
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self._log("模型已释放")

    def _is_hotwords_supported(self) -> bool:
        return True
