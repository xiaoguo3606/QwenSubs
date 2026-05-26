"""Forced alignment tab UI."""

from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path

import gradio as gr

from core.audio_processor import is_audio_file, convert_to_16k_mono, split_audio, detect_speech_duration, get_audio_duration
from core.punctuation_cleaner import (
    strip_trailing_punctuation,
    strip_mid_punctuation,
    capitalize_lines,
)
from core.sentence_splitter import split_sentences
from config import settings as cfg
from ui.review_editor import set_review_content

logger = logging.getLogger(__name__)

# Conservative margin for per-chunk text allocation.
# 1.0 = allocate text proportionally to each chunk's duration share.
# Values >1.0 add headroom for speech rate variation.
_SAFETY_MARGIN = 1.0

# Chunk duration for outer audio file splitting.
# Audio longer than this gets split into separate temp files.
_CHUNK_SEC = 270.0

# Maximum audio duration per alignment call.
# The forced aligner model has limited capacity — larger windows cause
# timestamp compression. 30s balances granularity with model limits.
_ALIGN_WINDOW_SEC = 30.0

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

        audio_input.upload(
            fn=lambda a, t: _validate_inputs(a, t),
            inputs=[audio_input, text_input],
            outputs=[status],
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
    ]

    return {
        "tab": tab,
        "audio_input": audio_input,
        "text_input": text_input,
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
    if not text or not text.strip():
        return "请输入音频对应的文本内容"
    return "输入就绪"


_SENTENCE_PUNCT_RE = re.compile(
    r"[\s，。！？、；：""''【】（）…—　,.!?;:\\-'\"«»·～　]+"
)


def _content_chars(s: str) -> str:
    return _SENTENCE_PUNCT_RE.sub("", s)


def _run_align(registry, audio_path, text_content, language,
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
    unaligned_count = 0

    try:
        chunks = split_audio(wav_path, max_duration=_ALIGN_WINDOW_SEC)

        sentences = split_sentences(text_content)
        if not sentences:
            return "无法从文本中识别出有效句子", timestamps_state, raw_text_state, subtitle_text_state

        sent_lens = [len(s) for s in sentences]

        # Global text density for proportional per-chunk text allocation
        total_audio_dur = get_audio_duration(wav_path)
        total_text_len = sum(sent_lens)
        chars_per_sec = total_text_len / max(total_audio_dur, 1.0)

        sent_idx = 0
        pending_text: list[str] = []  # accumulates across chunks

        for idx, (chunk_path, chunk_start, chunk_dur) in enumerate(chunks):
            if _align_cancel.is_set():
                return "对齐已取消", timestamps_state, raw_text_state, subtitle_text_state

            progress((idx + 0.3) / len(chunks),
                     desc=f"对齐第 {idx+1}/{len(chunks)} 段...")

            if sent_idx >= len(sentences):
                break

            # Allocate text proportionally to this chunk's share of audio
            max_chars = max(10, int(chunk_dur * chars_per_sec * _SAFETY_MARGIN))

            s_start = sent_idx
            chars_in_chunk = 0
            while sent_idx < len(sentences):
                next_len = sent_lens[sent_idx]
                if chars_in_chunk + next_len > max_chars:
                    break
                chars_in_chunk += next_len
                sent_idx += 1

            # Ensure at least one sentence per chunk
            if s_start == sent_idx and s_start < len(sentences):
                sent_idx = s_start + 1
                chars_in_chunk = sent_lens[s_start]

            chunk_text = "".join(sentences[s_start:sent_idx])
            if not chunk_text.strip():
                continue

            try:
                result = registry.aligner.align(chunk_path, chunk_text, language=language)
            except Exception as e:
                logger.warning("第 %d 段对齐失败: %s", idx + 1, e)
                fail_count += 1
                pending_text.extend(sentences[s_start:sent_idx])
                unaligned_count += sent_idx - s_start
                continue

            if _align_cancel.is_set():
                return "对齐已取消", timestamps_state, raw_text_state, subtitle_text_state

            raw_ts = result.get("timestamps", [])
            if not raw_ts:
                logger.warning("第 %d 段对齐无时间戳", idx + 1)
                fail_count += 1
                pending_text.extend(sentences[s_start:sent_idx])
                unaligned_count += sent_idx - s_start
                continue

            # ── Split raw timestamp items per original sentence ──────────
            chunk_sentences = sentences[s_start:sent_idx]
            if len(raw_ts) == len(chunk_text):
                sent_counts = [len(s) for s in chunk_sentences]
            else:
                sent_counts = [len(_content_chars(s)) for s in chunk_sentences]

            ts_cursor = 0
            for i, sent in enumerate(chunk_sentences):
                n = sent_counts[i]
                sent_raw = raw_ts[ts_cursor:ts_cursor + n]
                ts_cursor += n
                if not sent_raw:
                    pending_text.append(sent)
                    unaligned_count += 1
                    continue

                sent_text = "".join(t["text"] for t in sent_raw)
                if not sent_text.strip():
                    pending_text.append(sent)
                    unaligned_count += 1
                    continue

                sent_start = sent_raw[0]["start_time"] + chunk_start
                sent_end = sent_raw[-1]["end_time"] + chunk_start

                # Always add word-level timestamps for SRT generation,
                # even if this sentence has zero duration.
                for t in sent_raw:
                    all_timestamps.append({
                        "text": t["text"],
                        "start_time": t["start_time"] + chunk_start,
                        "end_time": t["end_time"] + chunk_start,
                    })

                # Skip zero-duration entries (model couldn't align this sentence)
                if sent_end - sent_start < 0.1:
                    pending_text.append(sent_text)
                    unaligned_count += 1
                    continue

                # Merge accumulated pending text into this valid entry
                if pending_text:
                    merged = "\n".join(pending_text) + "\n" + sent_text
                    pending_text = []
                    subtitle_entries.append((merged, sent_start, sent_end))
                else:
                    subtitle_entries.append((sent_text, sent_start, sent_end))

            # Clean up chunk temp file
            if chunk_path != wav_path:
                try:
                    os.unlink(chunk_path)
                except OSError:
                    pass

            progress((idx + 1) / len(chunks),
                     desc=f"第 {idx+1}/{len(chunks)} 段完成")

        # ── Flush any remaining pending text ──
        if pending_text:
            if subtitle_entries:
                # Attach to the last valid entry's timestamp
                _, last_start, last_end = subtitle_entries[-1]
                merged = "\n".join(pending_text)
                subtitle_entries.append((merged, last_end, last_end))
                pending_text = []
                unaligned_count += len(merged.split("\n"))
            else:
                return ("对齐失败：模型未能生成有效时间戳，"
                        "请检查音频与文本内容是否匹配",
                        timestamps_state, raw_text_state, subtitle_text_state)

        if not subtitle_entries:
            return "对齐无结果", timestamps_state, raw_text_state, subtitle_text_state

        # ── Build final display text ──
        text = "\n".join(entry[0] for entry in subtitle_entries)
        timestamps = all_timestamps

        # Warn about unaligned text
        if sent_idx < len(sentences) or unaligned_count > 0:
            total_sents = len(sentences)
            remaining = len("".join(sentences[sent_idx:]))
            aligned_sents = total_sents - unaligned_count - (len(sentences) - sent_idx)
            if sent_idx < len(sentences):
                pct = remaining / max(1, sum(sent_lens)) * 100
                if pct > 5:
                    logger.warning("%.0f%% 的文本未能对齐（音频时长不足）", pct)
            if unaligned_count > 0:
                logger.info("%d 句因模型对齐质量不足被自动合并到相邻字幕", unaligned_count)

    except Exception as e:
        return f"对齐失败: {e}", timestamps_state, raw_text_state, subtitle_text_state
    finally:
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
    if unaligned_count > 0:
        status_msg = f"ℹ️ {unaligned_count} 句已自动合并。\n" + status_msg
    return status_msg, ts_state, rt_state, si_text
