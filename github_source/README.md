# Qwen-ASR-SRT

基于 Qwen3-ASR 的精准字幕制作工具，支持语音识别（ASR）和强制对齐（已有文本匹配音频生成字幕）。

An accurate subtitle tool based on Qwen3-ASR, supporting speech recognition and forced alignment.

## 功能特点 / Features

- 🎤 **语音识别 (ASR)** — 将音频转为带时间戳的字幕
- 🎯 **强制对齐** — 已有文本 + 音频 → 逐字时间戳字幕
- 📝 **字幕分句编辑** — 支持手动调整分句和文本
- 📦 **多格式输出** — SRT / ASS / VTT
- 🧠 **LLM 校正** — 可选 Ollama / OpenAI，校正人名地名等专有名词
- 🌐 **多语言界面** — 中文 / English
- 🎛️ **标点格式化** — 批量删除句末/句中标点

## 快速开始 / Quick Start

### Windows

双击 `start.bat`，脚本会自动：

1. 检测 Python 环境（未安装则自动下载安装）
2. 创建虚拟环境
3. 安装依赖
4. 启动应用

> **最低要求**: Windows 10 64-bit，4GB 内存，支持 CUDA 的 NVIDIA 显卡或 Apple Silicon 可选（用于 GPU 加速）

### macOS / Linux

```bash
chmod +x start.sh
./start.sh
```

### 手动安装

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

启动后浏览器打开 http://127.0.0.1:7860，先在「设置」页面下载模型，然后即可使用。

## 使用方法 / Usage

1. **下载模型**: 打开「设置 → 模型管理」，选择下载源（ModelScope / HuggingFace），下载 ASR 模型和对齐模型
2. **语音识别**: 上传音频 → 选择语言 → 「开始识别」→ 在编辑器中调整分句 → 「确认并生成字幕」
3. **强制对齐**: 上传音频 + 粘贴对应文本 → 「开始对齐」→ 同上
4. **LLM 校正（可选）**: 在「设置 → LLM 配置」中启用并配置 Ollama 或 OpenAI 兼容 API

## 项目结构 / Project Structure

```
qwen-asr-srt/
├── app.py                    # Gradio 主入口
├── core/
│   ├── asr_engine.py         # Qwen3ASR 封装
│   ├── forced_aligner.py     # Qwen3ForcedAligner 封装
│   ├── audio_processor.py    # 音频格式转换 / 分块
│   ├── subtitle_builder.py   # 字幕文件生成 (SRT/ASS/VTT)
│   ├── sentence_splitter.py  # 标点分句
│   └── punctuation_cleaner.py# 标点清理
├── ui/
│   ├── asr_tab.py            # ASR 页面
│   ├── align_tab.py          # 强制对齐页面
│   ├── review_editor.py      # 字幕审核编辑
│   └── settings_tab.py       # 设置页面
├── config/
│   └── settings.py           # 配置管理
├── utils/
│   ├── hardware_detector.py  # 硬件检测
│   ├── model_manager.py      # 模型下载管理
│   └── llm_client.py         # LLM 客户端
├── i18n.py                   # 国际化翻译
├── requirements.txt
├── start.bat                 # Windows 一键启动
└── start.sh                  # macOS/Linux 一键启动
```

## 依赖 / Dependencies

- Python 3.11+
- [qwen-asr](https://pypi.org/project/qwen-asr/) — Qwen3-ASR 模型
- gradio — Web UI
- PyTorch — 深度学习框架
- modelscope / huggingface_hub — 模型下载
- ffmpeg — 音频处理（需系统安装）

## 许可证 / License

Apache 2.0
