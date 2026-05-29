"""ASR pipeline with progress callback support."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Callable

from core.audio_processor import (
    convert_to_16k_mono,
    get_audio_duration,
    split_audio,
    extract_audio_segment,
    MAX_AUDIO_DURATION,
)
from core.punctuation_cleaner import (
    strip_trailing_punctuation,
    strip_mid_punctuation,
    capitalize_lines,
)
from core.sentence_splitter import split_sentences
from core.model_registry import ModelRegistry
from config import settings as cfg
from utils.llm_client import LLMClient
from utils.model_manager import download_model_with_progress
from backend.result_builder import build_subtitle_entries

logger = logging.getLogger(__name__)


def run_asr_pipeline(
    registry: ModelRegistry,
    wav_path: str,
    split_point: float = 0.0,
    language: str = "auto",
    hint_text: str = "",
    asr_model: str = "",
    strip_punct: bool = True,
    strip_mid_punct: bool = False,
    mid_punct_choices: list[str] | None = None,
    space_replacement: bool = False,
    capitalize: bool = False,
    cancel_event: threading.Event | None = None,
    progress_cb: Callable[[float, str], None] | None = None,
) -> dict:
    """Run ASR transcription and return results.

    Returns:
        dict with keys: text, timestamps (list[dict]), subtitle_entries (list[dict])
    """
    cancel = cancel_event or threading.Event()

    def _check_cancel():
        if cancel.is_set():
            raise CancelError()

    _report(progress_cb, 0, "加载 ASR 模型...")
    model_name = asr_model or cfg.get("asr_model")
    model_dir = cfg.get_model_path(model_name)
    if not Path(model_dir).exists():
        for dl_progress, dl_text in download_model_with_progress(model_name, model_dir):
            _report(progress_cb, dl_progress * 0.5, f"下载中: {dl_text}")
    try:
        registry.load_asr(
            model_path=model_dir,
            aligner_path=cfg.get_model_path(cfg.get("aligner_model")),
            device=cfg.get("device"),
            dtype=cfg.get("dtype"),
        )
    except Exception as e:
        raise RuntimeError(f"Model loading failed: {e}")

    _check_cancel()
    lang = None if language == "auto" else language

    chunk_files: list[str] = []
    try:
        total_dur = get_audio_duration(wav_path)

        # Determine segments: manual split, auto-split at 5-min, or single
        if split_point > 0 and split_point < total_dur:
            segments = [
                (0.0, split_point, 0.0),
                (split_point, total_dur - split_point, split_point),
            ]
        elif total_dur > MAX_AUDIO_DURATION:
            segments = []
            pos = 0.0
            while pos < total_dur:
                seg_dur = min(MAX_AUDIO_DURATION, total_dur - pos)
                segments.append((pos, seg_dur, pos))
                pos += seg_dur
        else:
            segments = [(0.0, total_dur, 0.0)]

        all_text_parts: list[str] = []
        all_timestamps: list[dict] = []

        for seg_idx, (seg_start, seg_dur, seg_offset) in enumerate(segments):
            _check_cancel()

            if len(segments) == 1:
                seg_path = wav_path
            else:
                seg_path = extract_audio_segment(wav_path, seg_start, seg_dur)
                chunk_files.append(seg_path)

            chunks = split_audio(seg_path, max_duration=30.0)

            for idx, (chunk_path, chunk_start, _) in enumerate(chunks):
                if chunk_path != seg_path:
                    chunk_files.append(chunk_path)
                _check_cancel()

                num_segs = len(segments)
                base_progress = seg_idx / num_segs
                rel_progress = (idx + 0.5) / len(chunks) / num_segs
                _report(progress_cb, base_progress + rel_progress,
                        f"识别第 {idx+1}/{len(chunks)} 段...")

                results = registry.asr_engine.transcribe(
                    chunk_path, language=lang
                )
                _check_cancel()

                if results:
                    for r in results:
                        _check_cancel()
                        ts_list = r.get("timestamps", [])
                        if not ts_list:
                            logger.info("跳过无时间戳的识别结果: %.40r", r.get("text", "")[:40])
                            continue
                        r_text = r.get("text", "")
                        if not r_text.strip():
                            continue
                        all_text_parts.append(r_text)
                        for ts in ts_list:
                            all_timestamps.append({
                                "text": ts["text"],
                                "start_time": ts["start_time"] + chunk_start + seg_offset,
                                "end_time": ts["end_time"] + chunk_start + seg_offset,
                            })
                _report(progress_cb, base_progress + (idx + 1) / len(chunks) / num_segs,
                        f"第 {idx+1}/{len(chunks)} 段完成")

        if not all_text_parts:
            raise RuntimeError("No recognition results")

        text = "".join(all_text_parts)
        timestamps = all_timestamps

        logger.info(
            "run_asr_pipeline: %d chars text, %d timestamps",
            len(text), len(timestamps),
        )
    except CancelError:
        raise
    except Exception as e:
        raise RuntimeError(f"Recognition failed: {e}")
    finally:
        for cf in chunk_files:
            try:
                os.unlink(cf)
            except OSError:
                pass

    # LLM correction
    if hint_text and hint_text.strip():
        if cfg.get("llm_enabled"):
            try:
                llm = LLMClient(
                    llm_type=cfg.get("llm_type"),
                    ollama_endpoint=cfg.get("ollama_endpoint"),
                    ollama_model=cfg.get("ollama_model"),
                    openai_base_url=cfg.get("openai_base_url"),
                    openai_api_key=cfg.get("openai_api_key"),
                    openai_model=cfg.get("openai_model"),
                )
                text = llm.correct_transcription(text, hint_text)
            except Exception as e:
                logger.warning("LLM correction failed, using original: %s", e)

    # Apply punctuation post-processing
    sentences = split_sentences(text)
    si_text = "\n".join(sentences) if sentences else text
    if strip_mid_punct and mid_punct_choices:
        si_text = strip_mid_punctuation(si_text, mid_punct_choices, space_replacement)
    if strip_punct:
        si_text = strip_trailing_punctuation(si_text)
    if capitalize:
        si_text = capitalize_lines(si_text)

    si_text = "\n".join(l for l in si_text.split("\n") if l.strip())

    subtitle_entries = build_subtitle_entries(si_text, timestamps)
    return {"text": si_text, "timestamps": timestamps, "subtitle_entries": subtitle_entries}


class CancelError(Exception):
    """Raised when the user cancels the task."""
    pass


def _report(cb: Callable[[float, str], None] | None, progress: float, text: str) -> None:
    if cb:
        cb(progress, text)
