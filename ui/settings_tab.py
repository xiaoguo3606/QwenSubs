"""Settings tab UI — model download, hardware, LLM config, model management."""

from __future__ import annotations

import gradio as gr

from config import settings as cfg
from i18n import translate
from utils.hardware_detector import detect as detect_hardware
from utils.model_manager import (
    download_model,
    download_model_with_progress,
    delete_model,
    is_model_downloaded,
    MODELS,
)

# LLM platform presets: key → (label, API type, default endpoint)
LLM_PRESETS = {
    "ollama":        {"label": "Ollama",       "type": "ollama", "endpoint": "http://localhost:11434"},
    "openai":        {"label": "OpenAI",       "type": "openai", "endpoint": "https://api.openai.com/v1"},
    "deepseek":      {"label": "DeepSeek",     "type": "openai", "endpoint": "https://api.deepseek.com"},
    "aliyun-bailian":{"label": "阿里云百炼",   "type": "openai", "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    "custom":        {"label": "自定义",       "type": "openai", "endpoint": ""},
}


def _infer_platform() -> str:
    """Determine platform from saved config (backward compatibility)."""
    saved = cfg.get("llm_platform")
    if saved in LLM_PRESETS:
        return saved
    if cfg.get("llm_type") == "ollama":
        return "ollama"
    base_url = cfg.get("openai_base_url", "")
    for key, p in LLM_PRESETS.items():
        if p["endpoint"] and p["endpoint"].rstrip("/") == base_url.rstrip("/"):
            return key
    for key, p in LLM_PRESETS.items():
        if p["endpoint"] and p["endpoint"].split("://")[1].split(".")[0] in base_url:
            return key
    return "custom"


def create_settings_tab(registry_state: gr.State) -> gr.Blocks:
    hardware_info = detect_hardware()
    platform = _infer_platform()
    preset = LLM_PRESETS.get(platform, LLM_PRESETS["custom"])

    # Resolve initial endpoint
    if platform == "custom":
        init_endpoint = cfg.get("openai_base_url") or ""
    elif platform == "ollama":
        init_endpoint = cfg.get("ollama_endpoint") or preset["endpoint"]
    else:
        init_endpoint = preset["endpoint"]

    init_api_key = "" if platform == "ollama" else (cfg.get("openai_api_key") or "")
    init_model = cfg.get("ollama_model") if platform == "ollama" else (cfg.get("openai_model") or "")

    with gr.Blocks() as tab:
        settings_title = gr.Markdown("## 设置")

        # ── 模型管理 ──────────────────────────────────────
        with gr.Tab("模型管理") as models_tab:
            model_source = gr.Dropdown(
                choices=["modelscope", "hf-mirror", "huggingface"],
                value=cfg.get("model_source"),
                label="模型下载源",
            )
            model_dir = gr.Textbox(
                value=cfg.get("model_dir"),
                label="模型存放目录",
                placeholder="./models",
            )

            _initial_downloaded = _get_downloaded_ids()

            dl_mgmt_header = gr.Markdown("### 已下载的模型管理")
            downloaded_checkboxes = gr.CheckboxGroup(
                choices=[(f"{m['name']} ({m['size_gb']}GB)", m["id"])
                         for m in MODELS if m["id"] in _initial_downloaded],
                label="勾选要删除的模型",
            )
            with gr.Row():
                delete_btn = gr.Button("🗑 删除选中模型", variant="stop", size="sm")
            delete_status = gr.Textbox(label="删除状态", interactive=False)

            dl_header = gr.Markdown("### 下载模型")
            model_checkboxes = gr.CheckboxGroup(
                choices=[(f"{m['name']} ({m['size_gb']}GB)", m["id"]) for m in MODELS],
                value=_initial_downloaded,
                label="选择要下载的模型（已下载的已自动勾选，下载时将跳过）",
            )
            download_btn = gr.Button("开始下载", variant="primary")
            download_status = gr.Textbox(label="下载状态", interactive=False)

            download_btn.click(
                fn=_do_download, inputs=[model_source, model_dir, model_checkboxes],
                outputs=[download_status],
            ).then(
                fn=_refresh_model_state,
                outputs=[model_checkboxes, downloaded_checkboxes],
            )

            delete_btn.click(
                fn=_delete_models,
                inputs=[downloaded_checkboxes],
                outputs=[delete_status],
            ).then(
                fn=_refresh_model_state,
                outputs=[model_checkboxes, downloaded_checkboxes],
            )

        # ── 硬件与模型 ─────────────────────────────────────
        with gr.Tab("硬件与模型") as hardware_tab:
            hardware_md = gr.Markdown(f"### 硬件检测结果\n"
                       f"- **设备**: {hardware_info.device}\n"
                       f"- **名称**: {hardware_info.device_name}\n"
                       f"- **可用显存**: {hardware_info.vram_gb:.1f} GB\n"
                       f"- **推荐模型**: {hardware_info.recommended_model}")
            if hardware_info.warnings:
                for w in hardware_info.warnings:
                    gr.Warning(w)

            asr_model = gr.Dropdown(
                choices=["Qwen/Qwen3-ASR-1.7B", "Qwen/Qwen3-ASR-0.6B"],
                value=cfg.get("asr_model"), label="ASR 模型",
            )
            aligner_model = gr.Dropdown(
                choices=["Qwen/Qwen3-ForcedAligner-0.6B"],
                value=cfg.get("aligner_model"), label="对齐模型",
            )
            device = gr.Dropdown(
                choices=["auto", "cuda", "mps", "cpu"],
                value=cfg.get("device"), label="运算设备",
            )
            dtype = gr.Dropdown(
                choices=["bfloat16", "float16", "float32"],
                value=cfg.get("dtype"), label="精度",
            )

            status_header = gr.Markdown("### 已加载模型状态")
            model_status = gr.Textbox(value=_format_status(None), label="当前内存中的模型",
                                      interactive=False, lines=4)
            refresh_status_btn = gr.Button("刷新状态", size="sm")
            unload_btn = gr.Button("释放全部模型", variant="stop", size="sm")
            unload_status = gr.Textbox(label="操作结果", interactive=False, visible=False)
            refresh_status_btn.click(fn=_refresh_status, inputs=[registry_state],
                                     outputs=[model_status])
            unload_btn.click(fn=_unload_models, inputs=[registry_state],
                             outputs=[unload_status, model_status])

        # ── LLM 配置 ──────────────────────────────────────
        with gr.Tab("LLM 配置（可选）") as llm_tab:
            llm_enabled = gr.Checkbox(
                label="启用 LLM（提示性文字校正需要）",
                value=cfg.get("llm_enabled"),
            )

            connect_header = gr.Markdown("### 连接配置")
            llm_platform = gr.Dropdown(
                choices=[(v["label"], k) for k, v in LLM_PRESETS.items()],
                value=platform, label="平台",
            )
            llm_api_endpoint = gr.Textbox(
                value=init_endpoint, label="API 地址",
                placeholder="根据平台自动填充，可手动修改",
            )
            llm_api_key = gr.Textbox(
                value=init_api_key, label="API Key（可选）",
                type="password", placeholder="Ollama 无需填写",
            )

            model_header = gr.Markdown("### 模型选择")
            fetch_btn = gr.Button("🔄 获取模型列表", variant="secondary", size="sm")
            fetch_status = gr.Textbox(label="获取状态", interactive=False)
            llm_model = gr.Dropdown(
                choices=[init_model] if init_model else [],
                value=init_model or None, label="选择模型",
                interactive=True, allow_custom_value=True,
            )

            with gr.Row():
                test_btn = gr.Button("🔗 测试连接", variant="secondary", size="sm")
            test_status = gr.Textbox(label="连接测试结果", interactive=False)

            # ── Events ────────────────────────────────
            llm_platform.change(
                fn=_on_platform_change,
                inputs=[llm_platform], outputs=[llm_api_endpoint],
            )
            fetch_btn.click(
                fn=_fetch_llm_models,
                inputs=[llm_platform, llm_api_endpoint, llm_api_key],
                outputs=[llm_model, fetch_status],
            )
            test_btn.click(
                fn=_test_llm_connection,
                inputs=[llm_platform, llm_api_endpoint, llm_api_key, llm_model],
                outputs=[test_status],
            )

        # ── 输出 ──────────────────────────────────────────
        with gr.Tab("输出") as output_tab:
            default_format = gr.Radio(
                choices=["srt", "ass", "vtt"],
                value=cfg.get("default_output_format"), label="默认输出格式",
            )

        # ── 保存 ──────────────────────────────────────────
        save_btn = gr.Button("保存设置", variant="primary")
        save_status = gr.Textbox(label="保存状态", interactive=False)
        save_btn.click(
            fn=_save_all_settings,
            inputs=[
                model_source, model_dir, asr_model, aligner_model,
                device, dtype,
                llm_enabled, llm_platform, llm_api_endpoint, llm_api_key, llm_model,
                default_format,
            ],
            outputs=[save_status],
        )

    _i18n = [
        ("settings.title", settings_title, "value"),
        ("settings.tab.models", models_tab, "label"),
        ("settings.tab.hardware", hardware_tab, "label"),
        ("settings.tab.llm", llm_tab, "label"),
        ("settings.tab.output", output_tab, "label"),
        ("settings.source.label", model_source, "label"),
        ("settings.dir.label", model_dir, "label"),
        ("settings.dir.placeholder", model_dir, "placeholder"),
        ("settings.downloaded.label", downloaded_checkboxes, "label"),
        ("settings.delete_btn", delete_btn, "value"),
        ("settings.delete_status", delete_status, "label"),
        ("settings.download.header", dl_header, "value"),
        ("settings.download.label", model_checkboxes, "label"),
        ("settings.download_btn", download_btn, "value"),
        ("settings.download_status", download_status, "label"),
        ("settings.hardware.asr", asr_model, "label"),
        ("settings.hardware.aligner", aligner_model, "label"),
        ("settings.hardware.device", device, "label"),
        ("settings.hardware.dtype", dtype, "label"),
        ("settings.hardware.status", model_status, "label"),
        ("settings.hardware.refresh", refresh_status_btn, "value"),
        ("settings.hardware.unload", unload_btn, "value"),
        ("settings.llm.enabled", llm_enabled, "label"),
        ("settings.llm.connect_header", connect_header, "value"),
        ("settings.llm.platform", llm_platform, "label"),
        ("settings.llm.endpoint", llm_api_endpoint, "label"),
        ("settings.llm.api_key", llm_api_key, "label"),
        ("settings.llm.model_header", model_header, "value"),
        ("settings.llm.model", llm_model, "label"),
        ("settings.llm.fetch_btn", fetch_btn, "value"),
        ("settings.llm.fetch_status", fetch_status, "label"),
        ("settings.llm.test_btn", test_btn, "value"),
        ("settings.llm.test_status", test_status, "label"),
        ("settings.output.format", default_format, "label"),
        ("settings.save_btn", save_btn, "value"),
        ("settings.save_status", save_status, "label"),
    ]

    return {
        "tab": tab,
        "save_btn": save_btn,
        "_i18n": _i18n,
    }


# ── Helper functions ───────────────────────────────────────────


def _format_status(status_dict: dict | None) -> str:
    lang = cfg.get("lang", "zh")
    asr_label = translate("settings.hardware.asr", lang)
    aligner_label = translate("settings.hardware.aligner", lang)
    device_label = translate("settings.hardware.device", lang)
    loaded = translate("status.loaded", lang)
    not_loaded = translate("status.not_loaded", lang)
    dash = translate("status.dash", lang)
    if status_dict is None:
        return (
            f"{asr_label}: {not_loaded}\n"
            f"{aligner_label}: {not_loaded}\n"
            f"{device_label}: {dash}\n"
            f"{translate('status.refresh_hint', lang)}"
        )
    return (
        f"{asr_label}: {loaded if status_dict['asr_loaded'] else not_loaded}\n"
        f"ASR Model: {status_dict['asr_model']}\n"
        f"{aligner_label}: {loaded if status_dict['aligner_loaded'] else not_loaded}\n"
        f"Aligner Model: {status_dict['aligner_model']}\n"
        f"{device_label}: {status_dict['device']}"
    )


def _refresh_status(registry) -> str:
    return _format_status(registry.status())


def _unload_models(registry) -> tuple[str, str]:
    registry.unload_all()
    msg = translate("status.unload_result", cfg.get("lang", "zh"))
    return msg, _format_status(registry.status())


def _do_download(source: str, model_dir: str, selected: list[str],
                  progress: gr.Progress = gr.Progress()) -> str:
    """Download selected models with real-time progress tracking."""
    if not selected:
        return "请选择要下载的模型"

    to_download = [m_id for m_id in selected
                   if not is_model_downloaded(cfg.get_model_path(m_id))]
    if not to_download:
        return "所选模型均已下载，无需重复下载"

    total = len(to_download)
    results = []

    for idx, model_id in enumerate(to_download):
        local_dir = cfg.get_model_path(model_id)
        base_pct = idx / total

        try:
            for pct, text in download_model_with_progress(model_id, local_dir, source):
                progress(base_pct + pct / total, desc=text)
            results.append(f"✓ {model_id}")
        except Exception as e:
            results.append(f"✗ {model_id}: {e}")

        progress((idx + 1) / total, desc=f"已完成 {idx+1}/{total}")

    return "\n".join(results)


def _on_platform_change(platform: str) -> gr.update:
    preset = LLM_PRESETS.get(platform, LLM_PRESETS["custom"])
    return gr.update(value=preset["endpoint"])


def _fetch_llm_models(platform: str, endpoint: str, api_key: str) -> tuple[gr.update, str]:
    """Fetch model list from the LLM API and populate the model dropdown."""
    preset = LLM_PRESETS.get(platform, LLM_PRESETS["custom"])
    try:
        if preset["type"] == "ollama":
            import httpx
            url = endpoint.rstrip("/") + "/api/tags"
            resp = httpx.get(url, timeout=10)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
        else:
            from openai import OpenAI
            client = OpenAI(base_url=endpoint, api_key=api_key or "sk-placeholder")
            model_list = list(client.models.list())
            models = sorted([m.id for m in model_list])

        if not models:
            return gr.update(choices=[], value=None), "⚠️ 未获取到可用模型"
        return gr.update(choices=models, value=models[0]), f"✅ 获取到 {len(models)} 个模型"
    except Exception as e:
        return gr.update(choices=[], value=None), f"❌ 获取失败: {e}"


def _test_llm_connection(platform: str, endpoint: str, api_key: str, model: str) -> str:
    """Test connectivity to the configured LLM service."""
    preset = LLM_PRESETS.get(platform, LLM_PRESETS["custom"])
    try:
        if not endpoint:
            return "❌ 请填写 API 地址"
        if not model:
            return "❌ 请先获取并选择模型"
        if preset["type"] == "ollama":
            import httpx
            resp = httpx.get(endpoint.rstrip("/") + "/api/tags", timeout=10)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if any(model in m for m in models):
                    return f"✅ {preset['label']} 连接成功（模型 {model} 可用）"
                names = ", ".join(models[:5])
                hint = f"，可用: {names}" if names else ""
                return f"⚠️ 服务正常，但未找到模型 {model}{hint}"
            return f"❌ 连接失败: HTTP {resp.status_code}"
        else:
            from openai import OpenAI
            client = OpenAI(base_url=endpoint, api_key=api_key or "sk-placeholder")
            models = list(client.models.list())
            return f"✅ {preset['label']} 连接成功（可用模型数: {len(models)}）"
    except Exception as e:
        return f"❌ 连接失败: {e}"


def _get_downloaded_ids() -> list[str]:
    """Return model IDs that exist on disk (based on saved config model_dir)."""
    downloaded = []
    for m in MODELS:
        if is_model_downloaded(cfg.get_model_path(m["id"])):
            downloaded.append(m["id"])
    return downloaded


def _refresh_model_state():
    """Re-scan disk and update both model checkbox groups."""
    downloaded = _get_downloaded_ids()
    all_choices = [(f"{m['name']} ({m['size_gb']}GB)", m["id"]) for m in MODELS]
    dl_choices = [(f"{m['name']} ({m['size_gb']}GB)", m["id"])
                  for m in MODELS if m["id"] in downloaded]
    return (
        gr.update(choices=all_choices, value=downloaded),
        gr.update(choices=dl_choices, value=[]),
    )


def _delete_models(selected_ids: list[str]) -> str:
    """Delete selected model directories from disk."""
    if not selected_ids:
        return "请选择要删除的模型"
    results = []
    for model_id in selected_ids:
        try:
            delete_model(cfg.get_model_path(model_id))
            results.append(f"✓ 已删除 {model_id}")
        except Exception as e:
            results.append(f"✗ {model_id}: {e}")
    return "\n".join(results)


def _save_all_settings(
    model_source, model_dir, asr_model, aligner_model,
    device, dtype,
    llm_enabled, llm_platform, llm_api_endpoint, llm_api_key, llm_model,
    default_format,
) -> str:
    """Save all settings, mapping LLM config to backend fields by platform."""
    preset = LLM_PRESETS.get(llm_platform, LLM_PRESETS["custom"])

    new_cfg = {
        "model_source": model_source,
        "model_dir": model_dir,
        "asr_model": asr_model,
        "aligner_model": aligner_model,
        "device": device,
        "dtype": dtype,
        "llm_enabled": llm_enabled,
        "llm_platform": llm_platform,
        "default_output_format": default_format,
    }

    if preset["type"] == "ollama":
        new_cfg.update({
            "llm_type": "ollama",
            "ollama_endpoint": llm_api_endpoint,
            "ollama_model": llm_model,
            "openai_base_url": "",
            "openai_api_key": "",
            "openai_model": "",
        })
    else:
        new_cfg.update({
            "llm_type": "openai",
            "openai_base_url": llm_api_endpoint,
            "openai_api_key": llm_api_key,
            "openai_model": llm_model,
            "ollama_endpoint": "",
            "ollama_model": "",
        })

    cfg.save(new_cfg)
    return "设置已保存"
