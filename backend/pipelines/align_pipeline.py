"""Refactored Alignment pipeline — no Gradio dependencies.

Extracted and adapted from ui/align_tab._run_align().
Replaces gr.Progress with a callback and gr.State with dict returns.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable

from core.audio_processor import (
    convert_to_16k_mono,
    get_audio_duration,
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
from utils.model_manager import download_model_with_progress

logger = logging.getLogger(__name__)

# Qwen3-ForcedAligner can handle up to 5 minutes natively.
# Split at 4:30 to leave headroom.
_ALIGN_WINDOW_SEC = 270.0

# Seconds of audio overlap at each chunk boundary.
_ALIGN_OVERLAP = 30.0

_SENTENCE_PUNCT_RE = re.compile(
    r"[\s，。！？、；：""''【】（）…—　,.!?;:\\-'\"«»·～　]+"
)


def _content_chars(s: str) -> str:
    return _SENTENCE_PUNCT_RE.sub("", s)


def _find_sent_idx(sentences: list[str], sent_lens: list[int], char_pos: int) -> int:
    cum = 0
    for i, sl in enumerate(sent_lens):
        if cum + sl > char_pos:
            return i
        cum += sl
    return len(sentences)


def run_align_pipeline(
    registry: ModelRegistry,
    wav_path: str,
    text_content: str,
    split_point: float = 0.0,
    language: str = "Chinese",
    strip_punct: bool = True,
    strip_mid_punct: bool = False,
    mid_punct_choices: list[str] | None = None,
    space_replacement: bool = False,
    capitalize: bool = False,
    cancel_event: threading.Event | None = None,
    progress_cb: Callable[[float, str], None] | None = None,
) -> dict:
    """Run forced alignment and return results.

    Returns:
        dict with keys: text (str), timestamps (list[dict]),
        subtitle_entries (list[dict]) each with "text", "start", "end"
    """
    cancel = cancel_event or threading.Event()

    def _check_cancel():
        if cancel.is_set():
            raise CancelError()

    _report(progress_cb, 0, "转换音频格式...")
    # convert_to_16k_mono is idempotent — already converted wavs are skipped
    if wav_path:
        try:
            wav_path = convert_to_16k_mono(wav_path)
        except Exception as e:
            raise RuntimeError(f"音频转换失败: {e}")

    _report(progress_cb, 0.05, "加载对齐模型...")
    aligner_model = cfg.get("aligner_model")
    aligner_dir = cfg.get_model_path(aligner_model)
    if not Path(aligner_dir).exists():
        for dl_progress, dl_text in download_model_with_progress(aligner_model, aligner_dir):
            _report(progress_cb, 0.05 + dl_progress * 0.4, f"下载中: {dl_text}")
    try:
        registry.load_aligner(
            model_path=aligner_dir,
            device=cfg.get("device"),
            dtype=cfg.get("dtype"),
        )
    except Exception as e:
        raise RuntimeError(f"模型加载失败: {e}")

    _check_cancel()

    sentences = split_sentences(text_content)
    if not sentences:
        raise RuntimeError("无法从文本中识别出有效句子")

    sent_lens = [len(s) for s in sentences]
    total_chars = sum(sent_lens)

    fail_count = 0
    all_timestamps: list[dict] = []
    subtitle_entries: list[tuple[str, float, float]] = []

    chunk_files: list[str] = []
    try:
        total_audio_dur = get_audio_duration(wav_path)
        global_chars_per_sec = total_chars / max(total_audio_dur, 1.0)

        # Determine segments: manual split, auto-split at 5-min, or single
        if split_point > 0 and split_point < total_audio_dur:
            segments = [
                (0.0, split_point, 0.0),
                (split_point, total_audio_dur - split_point, split_point),
            ]
        elif total_audio_dur > MAX_AUDIO_DURATION:
            segments = []
            pos = 0.0
            while pos < total_audio_dur:
                seg_dur = min(MAX_AUDIO_DURATION, total_audio_dur - pos)
                segments.append((pos, seg_dur, pos))
                pos += seg_dur
        else:
            segments = [(0.0, total_audio_dur, 0.0)]

        for seg_idx, (seg_start, seg_dur, seg_offset) in enumerate(segments):
            _check_cancel()

            num_segs = len(segments)
            if num_segs == 1:
                seg_path = wav_path
                seg_duration = total_audio_dur
            else:
                _report(progress_cb, seg_idx / num_segs,
                        f"分割第 {seg_idx+1}/{num_segs} 段...")
                seg_path = extract_audio_segment(wav_path, seg_start, seg_dur)
                chunk_files.append(seg_path)
                seg_duration = seg_dur

            # Build overlapping chunks for this segment
            chunks: list[tuple[str, float, float, float, float]] = []
            pos = 0.0
            c_idx = 0
            while pos < seg_duration:
                audio_start = max(0.0, pos - _ALIGN_OVERLAP)
                audio_end = min(seg_duration, pos + _ALIGN_WINDOW_SEC + _ALIGN_OVERLAP)
                keep_start = pos
                keep_end = min(seg_duration, pos + _ALIGN_WINDOW_SEC)

                chunk_dur = audio_end - audio_start

                fd, chunk_path = tempfile.mkstemp(suffix=".wav", prefix=f"qwen_align_{c_idx}_")
                os.close(fd)
                cmd = [
                    "ffmpeg", "-y",
                    "-i", seg_path,
                    "-ss", str(audio_start),
                    "-t", str(chunk_dur),
                    "-ar", "16000",
                    "-ac", "1",
                    "-sample_fmt", "s16",
                    chunk_path,
                ]
                subprocess.run(cmd, check=True, capture_output=True, timeout=60)
                chunks.append((chunk_path, audio_start, chunk_dur, keep_start, keep_end))
                chunk_files.append(chunk_path)
                pos += _ALIGN_WINDOW_SEC
                c_idx += 1

            for idx, (chunk_path, audio_start, chunk_dur, keep_start, keep_end) in enumerate(chunks):
                _check_cancel()

                chunk_progress = (seg_idx + (idx + 0.3) / len(chunks)) / num_segs
                _report(progress_cb, chunk_progress,
                        f"对齐第 {idx+1}/{len(chunks)} 段...")

                est_char_pos = int((audio_start + seg_offset) * global_chars_per_sec)
                s_start = _find_sent_idx(sentences, sent_lens, est_char_pos)

                # Bound text selection per segment using global estimate
                seg_end_char = int((seg_start + seg_dur) * global_chars_per_sec)
                # For the very last segment, ensure no text is left out
                if seg_idx == len(segments) - 1:
                    seg_end_char = max(seg_end_char, total_chars)
                chars_before = sum(sent_lens[:s_start])
                budget = max(0, seg_end_char - chars_before)

                remaining_dur = seg_duration - audio_start
                remaining_chars = sum(sent_lens[s_start:])
                local_chars_per_sec = remaining_chars / max(remaining_dur, 1.0)
                max_chars = max(10, int(chunk_dur * local_chars_per_sec))
                max_chars = min(max_chars, budget)

                sent_idx = s_start
                chars_in_chunk = 0
                while sent_idx < len(sentences):
                    next_len = sent_lens[sent_idx]
                    if chars_in_chunk + next_len > max_chars:
                        break
                    chars_in_chunk += next_len
                    sent_idx += 1

                if s_start == sent_idx and s_start < len(sentences):
                    sent_idx = s_start + 1
                    chars_in_chunk = sent_lens[s_start]

                chunk_text = "".join(sentences[s_start:sent_idx])
                if not chunk_text.strip():
                    continue

                logger.info("chunk %d: audio=[%.1f-%.1f] dur=%.1f keep=[%.1f-%.1f], %d sentences, %d chars",
                            idx, audio_start, audio_start + chunk_dur, chunk_dur,
                            keep_start, keep_end,
                            sent_idx - s_start, len(chunk_text))

                try:
                    result = registry.aligner.align(chunk_path, chunk_text, language=language)
                except Exception as e:
                    logger.warning("第 %d 段对齐失败: %s", idx + 1, e)
                    fail_count += 1
                    continue

                _check_cancel()

                raw_ts = result.get("timestamps", [])
                if not raw_ts:
                    logger.warning("第 %d 段对齐无时间戳", idx + 1)
                    fail_count += 1
                    continue

                if raw_ts:
                    ts_start = raw_ts[0]["start_time"]
                    ts_end = raw_ts[-1]["end_time"]
                    ts_chars = sum(len(t["text"]) for t in raw_ts)
                    logger.info("chunk %d aligned: %d ts, %.1f-%.1f (%.1fs), %d ts_chars",
                                idx, len(raw_ts), ts_start, ts_end, ts_end - ts_start, ts_chars)

                # Split raw timestamp items per original sentence
                chunk_sentences = sentences[s_start:sent_idx]
                if len(raw_ts) == len(chunk_text):
                    sent_counts = [len(s) for s in chunk_sentences]
                else:
                    sent_counts = []
                    _ti = 0
                    for _s in chunk_sentences:
                        target = len(_s)
                        _n = 0
                        _acc = 0
                        while _ti < len(raw_ts) and _acc < target:
                            _acc += len(raw_ts[_ti]["text"])
                            _n += 1
                            _ti += 1
                        sent_counts.append(_n)

                ts_cursor = 0
                for i, sent in enumerate(chunk_sentences):
                    n = sent_counts[i]
                    sent_raw = raw_ts[ts_cursor:ts_cursor + n]
                    ts_cursor += n
                    if not sent_raw:
                        # Aligner ran out of budget for this sentence (common at
                        # chunk boundaries). Estimate timestamps proportionally
                        # rather than dropping valid text.
                        chunk_total = sum(len(s) for s in chunk_sentences)
                        chars_before_in_chunk = sum(len(s) for s in chunk_sentences[:i])
                        frac = chars_before_in_chunk / max(chunk_total, 1)
                        est_start = audio_start + seg_offset + frac * chunk_dur
                        est_end = audio_start + seg_offset + (frac + len(sent) / max(chunk_total, 1)) * chunk_dur
                        subtitle_entries.append((sent, est_start, est_end))
                        continue

                    sent_text = sent

                    sent_start = sent_raw[0]["start_time"] + audio_start + seg_offset
                    sent_end = sent_raw[-1]["end_time"] + audio_start + seg_offset

                    if sent_start < keep_start + seg_offset or sent_start >= keep_end + seg_offset:
                        continue

                    for t in sent_raw:
                        all_timestamps.append({
                            "text": t["text"],
                            "start_time": t["start_time"] + audio_start + seg_offset,
                            "end_time": t["end_time"] + audio_start + seg_offset,
                        })

                    subtitle_entries.append((sent_text, sent_start, sent_end))

                if chunk_path != seg_path:
                    try:
                        os.unlink(chunk_path)
                    except OSError:
                        pass

                chunk_progress = (seg_idx + (idx + 1) / len(chunks)) / num_segs
                _report(progress_cb, chunk_progress, f"第 {idx+1}/{len(chunks)} 段完成")

        if not subtitle_entries:
            raise RuntimeError("对齐无结果")

        logger.info(
            "run_align_pipeline: %d subtitle_entries, %d all_timestamps",
            len(subtitle_entries), len(all_timestamps),
        )

        subtitle_entries.sort(key=lambda e: e[1])
        all_timestamps.sort(key=lambda t: t["start_time"])

        text = "\n".join(entry[0] for entry in subtitle_entries if entry[0].strip())
        timestamps = all_timestamps

        if subtitle_entries:
            first_start = subtitle_entries[0][1]
            last_end = subtitle_entries[-1][2]
            unaligned_chars = total_chars - sum(len(t.get("text", "")) for t in all_timestamps)
            logger.info(
                "run_align_pipeline coverage: %.1f-%.1f (%.1fs), unaligned_chars=%d",
                first_start, last_end, last_end - first_start, unaligned_chars,
            )

    except CancelError:
        raise
    except Exception as e:
        raise RuntimeError(f"对齐失败: {e}")
    finally:
        for cf in chunk_files:
            try:
                os.unlink(cf)
            except OSError:
                pass

    # Apply punctuation post-processing
    si_text = text
    if strip_mid_punct and mid_punct_choices:
        si_text = strip_mid_punctuation(si_text, mid_punct_choices, space_replacement)
    if strip_punct:
        si_text = strip_trailing_punctuation(si_text)
    if capitalize:
        si_text = capitalize_lines(si_text)

    si_text = "\n".join(l for l in si_text.split("\n") if l.strip())

    result = {
        "text": si_text,
        "timestamps": timestamps,
        "subtitle_entries": [
            {"text": e[0], "start": e[1], "end": e[2]}
            for e in subtitle_entries if e[0].strip()
        ],
    }
    if fail_count > 0:
        result["warning"] = f"有 {fail_count} 段对齐失败，结果可能不完整"

    return result


class CancelError(Exception):
    """Raised when the user cancels the task."""
    pass


def _report(cb: Callable[[float, str], None] | None, progress: float, text: str) -> None:
    if cb:
        cb(progress, text)
