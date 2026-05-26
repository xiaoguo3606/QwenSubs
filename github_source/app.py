"""Qwen-ASR 字幕制作工具 — Gradio 主入口."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import gradio as gr

from core.model_registry import ModelRegistry
from i18n import translate
from ui.asr_tab import create_asr_tab, _run_asr, clear_asr_cancel, cancel_asr
from ui.align_tab import create_align_tab, _run_align, clear_align_cancel, cancel_align
from ui.settings_tab import create_settings_tab
from ui.review_editor import (
    create_review_state,
    create_review_ui,
    generate_subtitles,
)
from config import settings as cfg
from utils.hardware_detector import detect as detect_hardware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


CSS = """
/* Subtitle editor textarea */
#subtitle-editor textarea {
    resize: vertical !important;
    min-height: 200px;
    font-size: 14px;
    line-height: 1.6;
}
/* Tab content padding */
.tabs .tabitem { padding-top: 1rem; }
/* Better form spacing */
label { font-weight: 500 !important; margin-bottom: 2px !important; }
/* Status textbox */
.gr-textbox textarea { font-size: 13px; }
/* Primary buttons */
button.primary { font-size: 15px !important; font-weight: 600 !important; }
/* Stop buttons — red */
button.stop, .stop-btn {
    background-color: #dc2626 !important;
    border-color: #dc2626 !important;
    color: white !important;
}
button.stop:hover, .stop-btn:hover {
    background-color: #b91c1c !important;
    border-color: #b91c1c !important;
}
/* Section separator */
.section-divider { margin: 0.5rem 0 1rem 0; border-top: 1px solid var(--border-color-primary); }
/* Checkbox groups more compact */
.gr-checkbox { margin: 0.25rem 0; }
/* Audio player - prevent waveform scrollbar from covering time display */
.gr-audio { padding-bottom: 16px !important; }
.gr-audio audio { margin-bottom: 6px; }
"""


def build_app() -> gr.Blocks:
    hardware = detect_hardware()
    if hardware.warnings:
        for w in hardware.warnings:
            logger.warning(w)

    first_run = not Path(cfg.CONFIG_FILE).exists()
    if first_run:
        _auto_configure(hardware)

    registry = ModelRegistry()

    with gr.Blocks(title="Qwen-ASR 字幕制作工具") as app:
        with gr.Row():
            with gr.Column(scale=4):
                title_md = gr.Markdown(
                    "# <div align='center'>🎬 Qwen-ASR-SRT字幕制作工具 V0.0.1</div>"
                )
                desc_md = gr.Markdown(
                    "<div align='center'>基于Qwen3-ASR的精准字幕制作工具，支持语音识别和强制对齐（已有文本匹配音频生成字幕），中文友好。</div>"
                )
            with gr.Column(scale=1, min_width=120):
                lang_selector = gr.Radio(
                    choices=[("中文", "zh"), ("English", "en")],
                    value=cfg.get("lang", "zh"),
                    label="界面语言",
                )

        registry_state = gr.State(registry)

        # ── Invisible state objects (before tabs, so tabs can reference them) ──
        review_state = create_review_state()
        ts_state = review_state["timestamps_state"]
        rt_state = review_state["raw_text_state"]
        st_state = review_state["subtitle_text_state"]

        # ── Tabs ───────────────────────────────────────────
        with gr.Tabs():
            with gr.TabItem("\U0001f3a4 语音识别") as asr_tab_item:
                asr = create_asr_tab(registry_state, ts_state, rt_state, st_state)
            with gr.TabItem("\U0001f3af 强制对齐") as align_tab_item:
                align = create_align_tab(registry_state, ts_state, rt_state, st_state)
            with gr.TabItem("⚙️ 设置") as settings_tab_item:
                settings = create_settings_tab(registry_state)

        # ── Review editor UI (below tabs) ───────────────────
        review_ui = create_review_ui()

        # ── Wire tab click events (all components exist now) ──

        # Helper: clear cancel flag and update status on re-start
        def _reset_asr_status():
            clear_asr_cancel()
            return "正在识别..."

        def _reset_align_status():
            clear_align_cancel()
            return "正在对齐..."

        # ASR: start → hide start, show stop, run → when done, restore buttons
        asr_run_event = asr["start_btn"].click(
            fn=lambda: (gr.update(visible=False), gr.update(visible=True)),
            outputs=[asr["start_btn"], asr["stop_btn"]],
        ).then(
            fn=_reset_asr_status,
            outputs=[asr["status"]],
        ).then(
            fn=_run_asr,
            inputs=[registry_state, asr["audio_input"], asr["hint_text"],
                    asr["language"], asr["strip_punct"], asr["capitalize"],
                    asr["strip_mid_punct"], asr["mid_punct_choices"],
                    asr["space_replacement"],
                    ts_state, rt_state, st_state],
            outputs=[asr["status"], ts_state, rt_state, st_state],
        ).then(
            fn=lambda s: (gr.update(visible=True), gr.update(visible=False), s),
            inputs=[st_state],
            outputs=[asr["start_btn"], asr["stop_btn"], review_ui["subtitle_input"]],
        )

        # ASR: stop → cancel running event, show start button
        def _handle_asr_stop():
            cancel_asr()
            return (gr.update(visible=True), gr.update(visible=False), "已取消")

        asr["stop_btn"].click(
            fn=_handle_asr_stop,
            outputs=[asr["start_btn"], asr["stop_btn"], asr["status"]],
            cancels=[asr_run_event],
        )

        # Align: start → hide start, show stop, run → when done, restore buttons
        align_run_event = align["start_btn"].click(
            fn=lambda: (gr.update(visible=False), gr.update(visible=True)),
            outputs=[align["start_btn"], align["stop_btn"]],
        ).then(
            fn=_reset_align_status,
            outputs=[align["status"]],
        ).then(
            fn=_run_align,
            inputs=[registry_state, align["audio_input"], align["text_input"],
                    align["language"],
                    align["strip_punct"], align["capitalize"],
                    align["strip_mid_punct"], align["mid_punct_choices"],
                    align["space_replacement"],
                    ts_state, rt_state, st_state],
            outputs=[align["status"], ts_state, rt_state, st_state],
        ).then(
            fn=lambda s: (gr.update(visible=True), gr.update(visible=False), s),
            inputs=[st_state],
            outputs=[align["start_btn"], align["stop_btn"], review_ui["subtitle_input"]],
        )

        # Align: stop → cancel running event, show start button
        def _handle_align_stop():
            cancel_align()
            return (gr.update(visible=True), gr.update(visible=False), "已取消")

        align["stop_btn"].click(
            fn=_handle_align_stop,
            outputs=[align["start_btn"], align["stop_btn"], align["status"]],
            cancels=[align_run_event],
        )

        # Generate subtitle file
        review_ui["generate_btn"].click(
            fn=generate_subtitles,
            inputs=[
                review_ui["subtitle_input"],
                review_ui["output_format"],
                ts_state,
            ],
            outputs=[review_ui["output_file"]],
        )

        if first_run:
            gr.Info(
                "首次运行！已根据硬件自动推荐配置，请在「设置」中下载模型后使用。"
            )

        # ── Language selector wiring ────────────────────
        all_i18n = []
        for tab in [asr, align, settings, review_ui]:
            for entry in tab.get("_i18n", []):
                all_i18n.append(entry)

        # App-level i18n entries (title, description, tab labels, lang selector)
        all_i18n.append(("app.title", title_md, "value"))
        all_i18n.append(("app.desc", desc_md, "value"))
        all_i18n.append(("tab.asr", asr_tab_item, "label"))
        all_i18n.append(("tab.align", align_tab_item, "label"))
        all_i18n.append(("tab.settings", settings_tab_item, "label"))
        all_i18n.append(("app.lang_label", lang_selector, "label"))

        i18n_comps = [comp for _, comp, _ in all_i18n]

        def _apply_language(lang: str) -> list[gr.update]:
            """Update all UI labels to the selected language."""
            cfg.set_key("lang", lang)
            updates = []
            for key, _, attr in all_i18n:
                text = translate(key, lang)
                if attr == "label":
                    updates.append(gr.update(label=text))
                elif attr == "value":
                    updates.append(gr.update(value=text))
                elif attr == "placeholder":
                    updates.append(gr.update(placeholder=text))
                elif attr == "info":
                    updates.append(gr.update(info=text))
                else:
                    updates.append(gr.update())
            return updates

        lang_selector.change(
            fn=_apply_language,
            inputs=[lang_selector],
            outputs=i18n_comps,
        )

    return app


def _auto_configure(hardware) -> None:
    config = cfg.load()
    config["device"] = hardware.device
    config["asr_model"] = hardware.recommended_model
    config["asr_model_size"] = hardware.recommended_size
    config["model_dir"] = "models"
    cfg.save(config)
    logger.info(
        "Auto-configured: device=%s, model=%s",
        hardware.device, hardware.recommended_model,
    )


if __name__ == "__main__":
    app = build_app()
    port = int(os.environ.get("GRADIO_SERVER_PORT", 7860))
    app.launch(
        server_name="127.0.0.1",
        server_port=port,
        show_error=True,
        css=CSS,
        theme=gr.themes.Soft(),
    )
