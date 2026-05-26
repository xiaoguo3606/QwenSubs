"""Forced alignment tab UI."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path

import gradio as gr

from core.audio_processor import is_audio_file, convert_to_16k_mono, split_audio, get_audio_duration, extract_audio_segment, MAX_AUDIO_DURATION
from core.punctuation_cleaner import (
    strip_trailing_punctuation,
    strip_mid_punctuation,
    capitalize_lines,
)
from core.sentence_splitter import split_sentences
from config import settings as cfg
from ui.review_editor import set_review_content

logger = logging.getLogger(__name__)

# Maximum audio duration per alignment call.
# Qwen3-ForcedAligner can handle up to 5 minutes natively.
# Split at 4:30 to leave headroom.
_ALIGN_WINDOW_SEC = 270.0

# Seconds of audio overlap at each chunk boundary. Without overlap,
# text misallocation at chunk boundaries causes gaps in subtitle
# coverage (e.g. 4:15–4:30 silent when the first chunk gets too few
# sentences and the second chunk's audio starts too late).
_ALIGN_OVERLAP = 30.0

# Cancellation event for alignment processing
_align_cancel = threading.Event()


def cancel_align() -> None:
    """Request cancellation of the current alignment run."""
    _align_cancel.set()


def clear_align_cancel() -> None:
    """Reset cancellation flag before a new alignment run."""
    _align_cancel.clear()


def create_align_tab(registry_state: gr.State, timestamps_state: gr.State,
                     raw_text_state: gr.State, subtitle_text_state: gr.State) -> dict:
    """Create the forced alignment tab UI. Returns controls for event wiring."""
    with gr.Blocks() as tab:
        title_md = gr.Markdown("## 强制对齐")

        with gr.Row():
            with gr.Column():
                audio_input = gr.Audio(
                    label="上传音频文件",
                    type="filepath",
                )
                text_input = gr.Textbox(
                    label="音频对应文本内容",
                    placeholder="粘贴或输入与音频对应的完整文本...",
                    lines=6,
                )
                split_point = gr.Slider(
                    minimum=0,
                    maximum=0,
                    step=1,
                    value=0,
                    label="音频分割点（秒）",
                    info="设为 0 时不分割；设为正数时将音频从此处切为两段分别处理",
                )

                with gr.Row():
                    language = gr.Dropdown(
                        choices=["Chinese", "English", "Japanese", "Korean",
                                 "Cantonese", "French", "German", "Italian",
                                 "Portuguese", "Russian", "Spanish"],
                        value="Chinese",
                        label="语言",
                    )
                    start_btn = gr.Button("开始对齐", variant="primary", size="lg")
                    stop_btn = gr.Button("停止", variant="stop", size="lg", visible=False, elem_classes="stop-btn")
                with gr.Row():
                    strip_punct = gr.Checkbox(
                        label="删除句末标点符号",
                        value=True,
                    )
                    strip_mid_punct = gr.Checkbox(
                        label="删除句中标点符号",
                        value=False,
                    )
                    capitalize = gr.Checkbox(
                        label="英文字幕每句首字母大写",
                        value=False,
                        info="将每行字幕的第一个英文字母转为大写",
                    )

                with gr.Column(visible=False) as mid_punct_section:
                    mid_punct_choices = gr.CheckboxGroup(
                        choices=[
                            "单引号", "双引号", "书名号", "冒号", "顿号",
                            "正反斜杠", "破折号", "间隔号", "连接号",
                            "下划线",
                        ],
                        label="选择要删除的标点",
                    )
                    with gr.Row():
                        select_all = gr.Checkbox(
                            label="以上全部",
                            value=False,
                        )
                        space_replacement = gr.Checkbox(
                            label="使用一个空格代替",
                            value=False,
                        )

                strip_mid_punct.change(
                    fn=lambda checked: gr.update(visible=checked),
                    inputs=[strip_mid_punct],
                    outputs=[mid_punct_section],
                )

                ALL_PUNCT_CHOICES = [
                    "单引号", "双引号", "书名号", "冒号", "顿号",
                    "正反斜杠", "破折号", "间隔号", "连接号", "下划线",
                ]
                prev_mid_punct_state = gr.State([])
                select_all.change(
                    fn=lambda checked, current, prev: (
                        gr.update(value=ALL_PUNCT_CHOICES, interactive=False),
                        current,
                    ) if checked else (
                        gr.update(value=prev, interactive=True),
                        prev,
                    ),
                    inputs=[select_all, mid_punct_choices, prev_mid_punct_state],
                    outputs=[mid_punct_choices, prev_mid_punct_state],
                )

        status = gr.Textbox(label="状态", interactive=False)

        def _on_audio_upload(audio_path: str, text: str) -> tuple[str, gr.update]:
            status_msg = _validate_inputs(audio_path, text)
            if audio_path:
                try:
                    dur = get_audio_duration(audio_path)
                    slider_update = gr.update(maximum=dur, minimum=0, value=0)
                except Exception:
                    slider_update = gr.update(maximum=0, minimum=0, value=0)
            else:
                slider_update = gr.update(maximum=0, minimum=0, value=0)
            return status_msg, slider_update

        audio_input.upload(
            fn=_on_audio_upload,
            inputs=[audio_input, text_input],
            outputs=[status, split_point],
        )

        text_input.change(
            fn=lambda a, t: _validate_inputs(a, t),
            inputs=[audio_input, text_input],
            outputs=[status],
        )

    _i18n = [
        ("align.title", title_md, "value"),
        ("align.audio.label", audio_input, "label"),
        ("align.text.label", text_input, "label"),
        ("align.text.placeholder", text_input, "placeholder"),
        ("align.lang.label", language, "label"),
        ("align.start_btn", start_btn, "value"),
        ("common.stop", stop_btn, "value"),
        ("align.strip_punct", strip_punct, "label"),
        ("align.strip_mid_punct", strip_mid_punct, "label"),
        ("align.mid_punct.label", mid_punct_choices, "label"),
        ("align.select_all", select_all, "label"),
        ("align.space_replacement", space_replacement, "label"),
        ("align.capitalize", capitalize, "label"),
        ("align.capitalize.info", capitalize, "info"),
        ("align.status.label", status, "label"),
        ("align.split_point.label", split_point, "label"),
        ("align.split_point.info", split_point, "info"),
    ]

    return {
        "tab": tab,
        "audio_input": audio_input,
        "text_input": text_input,
        "split_point": split_point,
        "language": language,
        "strip_punct": strip_punct,
        "strip_mid_punct": strip_mid_punct,
        "mid_punct_choices": mid_punct_choices,
        "space_replacement": space_replacement,
        "capitalize": capitalize,
        "start_btn": start_btn,
        "stop_btn": stop_btn,
        "status": status,
        "_i18n": _i18n,
    }


def _validate_inputs(audio_path: str, text: str) -> str:
    if not audio_path:
        return "请上传音频文件"
    if not is_audio_file(audio_path):
        return "不支持的音频格式"
    try:
        duration = get_audio_duration(audio_path)
        if duration > MAX_AUDIO_DURATION:
            minutes = duration / 60
            return f"音频时长 {minutes:.1f} 分钟，将自动分段处理"
    except Exception:
        pass
    if not text or not text.strip():
        return "请输入音频对应的文本内容"
    return "输入就绪"


_SENTENCE_PUNCT_RE = re.compile(
    r"[\s，。！？、；：""''【】（）…—　,.!?;:\\-'\"«»·～　]+"
)


def _content_chars(s: str) -> str:
    return _SENTENCE_PUNCT_RE.sub("", s)


def _find_sent_idx(sentences: list[str], sent_lens: list[int], char_pos: int) -> int:
    """Return the sentence index that contains the given char_pos (cumulative)."""
    cum = 0
    for i, sl in enumerate(sent_lens):
        if cum + sl > char_pos:
            return i
        cum += sl
    return len(sentences)


def _run_align(registry, audio_path, text_content, split_point, language,
               strip_punct, capitalize, strip_mid_punct,
               mid_punct_choices, space_replacement,
               timestamps_state, raw_text_state, subtitle_text_state,
               progress: gr.Progress = gr.Progress()):
    """Run forced alignment via shared registry and populate review editor."""
    if not audio_path or not text_content:
        return "请完成所有输入", timestamps_state, raw_text_state, subtitle_text_state

    clear_align_cancel()
    if _align_cancel.is_set():
        return "对齐已取消", timestamps_state, raw_text_state, subtitle_text_state

    wav_path = None
    try:
        progress(0, desc="转换音频格式...")
        wav_path = convert_to_16k_mono(audio_path)
    except Exception as e:
        return f"音频转换失败: {e}", timestamps_state, raw_text_state, subtitle_text_state

    aligner_dir = cfg.get_model_path(cfg.get("aligner_model"))
    if not Path(aligner_dir).exists():
        if wav_path and wav_path != audio_path:
            try: os.unlink(wav_path)
            except OSError: pass
        return (
            f"❌ 对齐模型未下载，请先到「设置 → 模型管理」中下载"
            f" {cfg.get('aligner_model')}",
            timestamps_state, raw_text_state, subtitle_text_state,
        )
    try:
        progress(0.05, desc="加载对齐模型...")
        registry.load_aligner(
            model_path=aligner_dir,
            device=cfg.get("device"),
            dtype=cfg.get("dtype"),
        )
    except Exception as e:
        if wav_path and wav_path != audio_path:
            try: os.unlink(wav_path)
            except OSError: pass
        return f"模型加载失败: {e}", timestamps_state, raw_text_state, subtitle_text_state

    if _align_cancel.is_set():
        return "对齐已取消", timestamps_state, raw_text_state, subtitle_text_state

    fail_count = 0
    all_timestamps: list[dict] = []
    subtitle_entries: list[tuple[str, float, float]] = []

    chunk_files: list[str] = []
    try:
        total_audio_dur = get_audio_duration(wav_path)

        # Determine segments: manual split, auto-split at 5-min boundaries, or single
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

        sentences = split_sentences(text_content)
        if not sentences:
            return "无法从文本中识别出有效句子", timestamps_state, raw_text_state, subtitle_text_state

        sent_lens = [len(s) for s in sentences]
        total_chars = sum(sent_lens)
        global_chars_per_sec = total_chars / max(total_audio_dur, 1.0)

        fail_count = 0
        all_timestamps: list[dict] = []
        subtitle_entries: list[tuple[str, float, float]] = []

        for seg_idx, (seg_start, seg_dur, seg_offset) in enumerate(segments):
            if _align_cancel.is_set():
                return "对齐已取消", timestamps_state, raw_text_state, subtitle_text_state

            # Use wav_path directly for single segment, extract for multi-segment
            num_segs = len(segments)
            if num_segs == 1:
                seg_path = wav_path
                seg_duration = total_audio_dur
            else:
                progress(seg_idx / num_segs, desc=f"分割第 {seg_idx+1}/{num_segs} 段...")
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
                if _align_cancel.is_set():
                    return "对齐已取消", timestamps_state, raw_text_state, subtitle_text_state

                chunk_progress = (seg_idx + (idx + 0.3) / len(chunks)) / num_segs
                progress(chunk_progress, desc=f"对齐第 {idx+1}/{len(chunks)} 段...")

                # Determine where this chunk's text begins independently
                # (not sequentially), so that overlap audio gets the right
                # sentences even when a previous chunk consumed too few/many.
                est_char_pos = int(audio_start * global_chars_per_sec)
                s_start = _find_sent_idx(sentences, sent_lens, est_char_pos)

                # Allocate sentences for this chunk's full duration (inc. overlap).
                remaining_dur = seg_duration - audio_start
                remaining_chars = sum(sent_lens[s_start:])
                local_chars_per_sec = remaining_chars / max(remaining_dur, 1.0)
                max_chars = max(10, int(chunk_dur * local_chars_per_sec))

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

                if _align_cancel.is_set():
                    return "对齐已取消", timestamps_state, raw_text_state, subtitle_text_state

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

                # Split raw timestamp items per original sentence.
                chunk_sentences = sentences[s_start:sent_idx]
                if len(raw_ts) == len(chunk_text):
                    sent_counts = [len(s) for s in chunk_sentences]
                else:
                    sent_counts = []
                    _ti = 0
                    for _s in chunk_sentences:
                        target = len(_content_chars(_s))
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
                        continue

                    sent_text = "".join(t["text"] for t in sent_raw)
                    if not sent_text.strip():
                        continue

                    sent_start = sent_raw[0]["start_time"] + audio_start + seg_offset
                    sent_end = sent_raw[-1]["end_time"] + audio_start + seg_offset

                    # Only keep entries whose start falls in the non-overlap
                    # region so each time point appears exactly once.
                    if sent_start < keep_start + seg_offset or sent_start >= keep_end + seg_offset:
                        continue

                    for t in sent_raw:
                        all_timestamps.append({
                            "text": t["text"],
                            "start_time": t["start_time"] + audio_start + seg_offset,
                            "end_time": t["end_time"] + audio_start + seg_offset,
                        })

                    subtitle_entries.append((sent_text, sent_start, sent_end))

                # Clean up chunk temp file
                if chunk_path != seg_path:
                    try:
                        os.unlink(chunk_path)
                    except OSError:
                        pass

                chunk_progress = (seg_idx + (idx + 1) / len(chunks)) / num_segs
                progress(chunk_progress, desc=f"第 {idx+1}/{len(chunks)} 段完成")

        if not subtitle_entries:
            return "对齐无结果", timestamps_state, raw_text_state, subtitle_text_state

        logger.info(
            "_run_align: %d subtitle_entries, %d all_timestamps, %d raw_chars",
            len(subtitle_entries),
            len(all_timestamps),
            sum(len(t.get("text", "")) for t in all_timestamps),
        )

        # Sort entries by start time (they may be interleaved from overlap chunks).
        subtitle_entries.sort(key=lambda e: e[1])
        # Re-sort all_timestamps too so Subtitler's char array is time-ordered.
        all_timestamps.sort(key=lambda t: t["start_time"])

        text = "\n".join(entry[0] for entry in subtitle_entries)
        timestamps = all_timestamps

        if subtitle_entries:
            first_start = subtitle_entries[0][1]
            last_end = subtitle_entries[-1][2]
            unaligned_chars = total_chars - sum(len(t.get("text", "")) for t in all_timestamps)
            logger.info(
                "_run_align coverage: %.1f-%.1f (%.1fs), unaligned_chars=%d",
                first_start, last_end, last_end - first_start, unaligned_chars,
            )

    except Exception as e:
        return f"对齐失败: {e}", timestamps_state, raw_text_state, subtitle_text_state
    finally:
        for cf in chunk_files:
            try:
                os.unlink(cf)
            except OSError:
                pass
        if wav_path and wav_path != audio_path:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    ts_state, rt_state, si_text = set_review_content(
        text, timestamps, timestamps_state, raw_text_state, subtitle_text_state
    )

    if strip_mid_punct and mid_punct_choices:
        si_text = strip_mid_punctuation(si_text, mid_punct_choices, space_replacement)
    if strip_punct:
        si_text = strip_trailing_punctuation(si_text)
    if capitalize:
        si_text = capitalize_lines(si_text)

    status_msg = "对齐完成"
    if fail_count > 0:
        status_msg = f"⚠️ 有 {fail_count} 段对齐失败，结果可能不完整。\n" + status_msg
    return status_msg, ts_state, rt_state, si_text
