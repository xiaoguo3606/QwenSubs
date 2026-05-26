"""ASR (speech recognition) tab UI."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

import gradio as gr

from core.audio_processor import is_audio_file, convert_to_16k_mono, get_audio_duration, split_audio
from core.punctuation_cleaner import (
    strip_trailing_punctuation,
    strip_mid_punctuation,
    capitalize_lines,
)
from utils.llm_client import LLMClient
from config import settings as cfg
from ui.review_editor import set_review_content

logger = logging.getLogger(__name__)

# Cancellation event for ASR processing
_asr_cancel = threading.Event()


def cancel_asr() -> None:
    """Request cancellation of the current ASR run."""
    _asr_cancel.set()


def clear_asr_cancel() -> None:
    """Reset cancellation flag before a new ASR run."""
    _asr_cancel.clear()


def create_asr_tab(registry_state: gr.State, timestamps_state: gr.State,
                   raw_text_state: gr.State, subtitle_text_state: gr.State) -> dict:
    """Create the ASR tab UI. Returns controls for event wiring in app.py."""
    with gr.Blocks() as tab:
        title_md = gr.Markdown("## 语音识别（ASR）")

        with gr.Row():
            with gr.Column():
                audio_input = gr.Audio(
                    label="上传音频文件",
                    type="filepath",
                )
                hint_text = gr.Textbox(
                    label="提示性文字（可选，需配置 LLM）",
                    placeholder="输入人名、地名等专有名词，用于校正识别结果",
                    lines=2,
                )

                with gr.Row():
                    language = gr.Dropdown(
                        choices=["Chinese", "English", "Japanese", "Korean",
                                 "Cantonese", "French", "German", "Italian",
                                 "Portuguese", "Russian", "Spanish", "auto"],
                        value="auto",
                        label="语言",
                    )
                    start_btn = gr.Button("开始识别", variant="primary", size="lg")
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
            fn=lambda p: _validate_audio(p),
            inputs=[audio_input],
            outputs=[status],
        )

    _i18n = [
        ("asr.title", title_md, "value"),
        ("asr.audio.label", audio_input, "label"),
        ("asr.hint.label", hint_text, "label"),
        ("asr.hint.placeholder", hint_text, "placeholder"),
        ("asr.lang.label", language, "label"),
        ("asr.start_btn", start_btn, "value"),
        ("common.stop", stop_btn, "value"),
        ("asr.strip_punct", strip_punct, "label"),
        ("asr.strip_mid_punct", strip_mid_punct, "label"),
        ("asr.mid_punct.label", mid_punct_choices, "label"),
        ("asr.select_all", select_all, "label"),
        ("asr.space_replacement", space_replacement, "label"),
        ("asr.capitalize", capitalize, "label"),
        ("asr.capitalize.info", capitalize, "info"),
        ("asr.status.label", status, "label"),
    ]

    return {
        "tab": tab,
        "audio_input": audio_input,
        "hint_text": hint_text,
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


def _validate_audio(audio_path: str) -> str:
    if not audio_path:
        return "请上传音频文件"
    if not is_audio_file(audio_path):
        return "不支持的音频格式，请上传 mp3/wav/m4a/flac 等常见格式"
    return "音频文件已上传"


def _run_asr(registry, audio_path, hint_text, language, strip_punct, capitalize,
             strip_mid_punct, mid_punct_choices, space_replacement,
             timestamps_state, raw_text_state, subtitle_text_state,
             progress: gr.Progress = gr.Progress()):
    """Run ASR via the shared registry and populate review editor."""
    if not audio_path:
        return "请先上传音频文件", timestamps_state, raw_text_state, subtitle_text_state

    wav_path = None
    try:
        progress(0, desc="转换音频格式...")
        wav_path = convert_to_16k_mono(audio_path)
    except Exception as e:
        return f"音频转换失败: {e}", timestamps_state, raw_text_state, subtitle_text_state

    model_dir = cfg.get_model_path(cfg.get("asr_model"))
    if not Path(model_dir).exists():
        if wav_path and wav_path != audio_path:
            try: os.unlink(wav_path)
            except OSError: pass
        return (
            f"❌ ASR 模型未下载，请先到「设置 → 模型管理」中下载"
            f" {cfg.get('asr_model')}",
            timestamps_state, raw_text_state, subtitle_text_state,
        )
    try:
        progress(0.05, desc="加载 ASR 模型...")
        registry.load_asr(
            model_path=model_dir,
            aligner_path=cfg.get_model_path(cfg.get("aligner_model")),
            device=cfg.get("device"),
            dtype=cfg.get("dtype"),
        )
    except Exception as e:
        if wav_path and wav_path != audio_path:
            try: os.unlink(wav_path)
            except OSError: pass
        return f"模型加载失败: {e}", timestamps_state, raw_text_state, subtitle_text_state

    try:
        lang = None if language == "auto" else language

        clear_asr_cancel()

        if _asr_cancel.is_set():
            return "识别已取消", timestamps_state, raw_text_state, subtitle_text_state

        # Split into short chunks (60s) to keep each well within the model's capacity
        chunks = split_audio(wav_path, max_duration=270.0)
        all_text_parts = []
        all_timestamps = []

        for idx, (chunk_path, chunk_start, _) in enumerate(chunks):
            if _asr_cancel.is_set():
                return "识别已取消", timestamps_state, raw_text_state, subtitle_text_state

            progress((idx + 0.5) / len(chunks), desc=f"识别第 {idx+1}/{len(chunks)} 段...")
            results = registry.asr_engine.transcribe(chunk_path, language=lang)

            if _asr_cancel.is_set():
                return "识别已取消", timestamps_state, raw_text_state, subtitle_text_state

            if results:
                for r in results:
                    if _asr_cancel.is_set():
                        return "识别已取消", timestamps_state, raw_text_state, subtitle_text_state
                    all_text_parts.append(r.get("text", ""))
                    for ts in r.get("timestamps", []):
                        all_timestamps.append({
                            "text": ts["text"],
                            "start_time": ts["start_time"] + chunk_start,
                            "end_time": ts["end_time"] + chunk_start,
                        })
            # Clean up chunk temp file (but not the original wav_path)
            if chunk_path != wav_path:
                try:
                    os.unlink(chunk_path)
                except OSError:
                    pass

            progress((idx + 1) / len(chunks), desc=f"第 {idx+1}/{len(chunks)} 段完成")

        if not all_text_parts:
            return "识别无结果", timestamps_state, raw_text_state, subtitle_text_state

        text = "".join(all_text_parts)
        timestamps = all_timestamps
    except Exception as e:
        return f"识别失败: {e}", timestamps_state, raw_text_state, subtitle_text_state
    finally:
        # Clean up the temp wav file
        if wav_path and wav_path != audio_path:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    llm_warning = ""
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
                logger.warning("LLM 校正失败，使用原始识别结果: %s", e)
        else:
            llm_warning = "⚠️ 您输入了提示性文字，但 LLM 未启用，提示文字已忽略。如需使用，请到「设置 → LLM 配置」中启用。\n"

    ts_state, rt_state, si_text = set_review_content(
        text, timestamps, timestamps_state, raw_text_state, subtitle_text_state
    )

    if strip_mid_punct and mid_punct_choices:
        si_text = strip_mid_punctuation(si_text, mid_punct_choices, space_replacement)
    if strip_punct:
        si_text = strip_trailing_punctuation(si_text)
    if capitalize:
        si_text = capitalize_lines(si_text)

    status_msg = "识别完成"
    if llm_warning:
        status_msg = llm_warning + status_msg
    return status_msg, ts_state, rt_state, si_text
