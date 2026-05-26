"""Shared subtitle review and editing UI component."""

from __future__ import annotations

import os
import tempfile

import gradio as gr

from core.sentence_splitter import split_sentences
from core.subtitle_builder import build_subtitles


def create_review_state() -> dict:
    """Create invisible state objects (called before tabs)."""
    return {
        "timestamps_state": gr.State([]),
        "raw_text_state": gr.State(""),
        "subtitle_text_state": gr.State(""),
    }


def create_review_ui() -> dict:
    """Create visible review editor UI components (called after tabs)."""
    gr.HTML('<div class="section-divider"></div>')
    title_md = gr.Markdown("### 📝 字幕分句审核编辑")

    with gr.Row():
        with gr.Column(scale=4):
            subtitle_input = gr.Textbox(
                elem_id="subtitle-editor",
                label="字幕文本（每行一条字幕，可自由修改分句和内容）",
                lines=15,
                max_lines=200,
                placeholder="识别/对齐完成后，结果将显示在此处…",
            )
        with gr.Column(scale=1):
            output_format = gr.Radio(
                choices=["srt", "ass", "vtt"],
                value="srt",
                label="输出格式",
                interactive=True,
            )
            generate_btn = gr.Button("确认并生成字幕", variant="primary", size="lg")
            output_file = gr.File(label="下载字幕文件")

    _i18n = [
        ("review.title", title_md, "value"),
        ("review.input.label", subtitle_input, "label"),
        ("review.input.placeholder", subtitle_input, "placeholder"),
        ("review.format.label", output_format, "label"),
        ("review.generate_btn", generate_btn, "value"),
        ("review.output.label", output_file, "label"),
    ]

    return {
        "subtitle_input": subtitle_input,
        "output_format": output_format,
        "generate_btn": generate_btn,
        "output_file": output_file,
        "_i18n": _i18n,
    }


def set_review_content(
    text: str,
    timestamps: list[dict],
    timestamps_state,
    raw_text_state,
    subtitle_input,
):
    """Populate the review editor with pre-split text."""
    lines = split_sentences(text)
    return (
        timestamps,
        text,
        "\n".join(lines),
    )


def generate_subtitles(
    subtitle_text: str,
    output_format: str,
    timestamps: list[dict],
) -> str | None:
    """Generate subtitle file content based on user-edited text."""
    if not subtitle_text or not timestamps:
        return None

    lines = subtitle_text.strip().split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    if not lines:
        return None

    content = build_subtitles(lines, timestamps, output_format)

    suffix_map = {"srt": "srt", "ass": "ass", "vtt": "vtt"}
    suffix = suffix_map.get(output_format, "srt")

    fd, path = tempfile.mkstemp(suffix=f".{suffix}", prefix="subtitle_")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
