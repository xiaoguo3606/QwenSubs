"""Global model registry — singleton that keeps models resident in memory."""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Holds loaded model instances. One per process."""

    def __init__(self):
        self.asr_engine = None
        self.aligner = None
        self._asr_model_id: str | None = None
        self._aligner_model_id: str | None = None
        self._device: str | None = None
        self._dtype: str | None = None

    # ── ASR engine ──────────────────────────────────────────────

    def load_asr(
        self,
        model_path: str,
        aligner_path: str | None,
        device: str,
        dtype: str,
        progress_cb: Callable[[str], None] | None = None,
    ):
        if self._same_asr(model_path, aligner_path, device, dtype):
            if self.asr_engine is not None:
                return  # already loaded with same config

        self.unload_asr()

        from core.asr_engine import QwenASREngine
        engine = QwenASREngine(
            model_path=model_path,
            aligner_path=aligner_path,
            device=device,
            dtype=dtype,
            progress_callback=progress_cb,
        )
        engine.load()
        self.asr_engine = engine
        self._asr_model_id = model_path
        self._aligner_model_id = aligner_path
        self._device = device
        self._dtype = dtype

    def unload_asr(self):
        if self.asr_engine is not None:
            self.asr_engine.unload()
            self.asr_engine = None
        self._asr_model_id = None

    # ── Aligner ─────────────────────────────────────────────────

    def load_aligner(
        self,
        model_path: str,
        device: str,
        dtype: str,
        progress_cb: Callable[[str], None] | None = None,
    ):
        if self._same_aligner(model_path, device, dtype):
            if self.aligner is not None:
                return

        self.unload_aligner()

        from core.forced_aligner import ForcedAligner
        aligner = ForcedAligner(
            model_path=model_path,
            device=device,
            dtype=dtype,
            progress_callback=progress_cb,
        )
        aligner.load()
        self.aligner = aligner
        self._aligner_model_id = model_path
        self._device = device
        self._dtype = dtype

    def unload_aligner(self):
        if self.aligner is not None:
            self.aligner.unload()
            self.aligner = None
        self._aligner_model_id = None

    # ── all ─────────────────────────────────────────────────────

    def unload_all(self):
        self.unload_asr()
        self.unload_aligner()

    def status(self) -> dict:
        return {
            "asr_loaded": self.asr_engine is not None,
            "asr_model": self._asr_model_id or "—",
            "aligner_loaded": self.aligner is not None,
            "aligner_model": self._aligner_model_id or "—",
            "device": self._device or "—",
        }

    # ── helpers ─────────────────────────────────────────────────

    def _same_asr(self, model_path, aligner_path, device, dtype) -> bool:
        return (
            self._asr_model_id == model_path
            and self._aligner_model_id == aligner_path
            and self._device == device
            and self._dtype == dtype
        )

    def _same_aligner(self, model_path, device, dtype) -> bool:
        return (
            self._aligner_model_id == model_path
            and self._device == device
            and self._dtype == dtype
        )
