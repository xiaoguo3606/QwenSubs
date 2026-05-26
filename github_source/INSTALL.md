# 安装指南 / Installation Guide

## 环境要求 / Requirements

| 项目 | 最低要求 |
|------|---------|
| 操作系统 | Windows 10+ / macOS 12+ / Linux |
| Python | 3.11 ～ 3.13 |
| 内存 | 4GB（推荐 8GB+）|
| 磁盘 | 5GB 可用空间（用于模型文件）|
| 可选 | NVIDIA GPU（CUDA）或 Apple Silicon（MPS）加速 |
| 必需 | ffmpeg（[下载](https://ffmpeg.org/download.html)）|

---

## 一键安装（推荐）

### Windows

双击 `start.bat`，脚本会自动：

1. **检查 Python** — 如未安装则提示手动安装
2. **创建虚拟环境** — `python -m venv venv`
3. **安装依赖** — `pip install -r requirements.txt`（约 5-15 分钟）
4. **启动应用** — 浏览器打开 http://127.0.0.1:7860

> 如果提示 Python 未找到，请从 [python.org](https://www.python.org/downloads/) 安装，安装时勾选 **"Add Python to PATH"**，完成后再次双击 `start.bat`。

### macOS / Linux

```bash
chmod +x start.sh
./start.sh
```

脚本会自动创建虚拟环境、安装依赖、启动应用。

---

## 手动安装

### 1. 克隆项目

```bash
git clone https://github.com/your-username/qwen-asr-srt.git
cd qwen-asr-srt
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. 启动

```bash
python app.py
```

浏览器打开 http://127.0.0.1:7860

---

## 下载模型

首次启动后，需要在 **设置 → 模型管理** 中下载模型：

1. **选择下载源**：ModelScope（国内推荐）/ HuggingFace
2. **下载 ASR 模型**：`Qwen/Qwen3-ASR-1.7B`（推荐）或 `0.6B`（轻量）
3. **下载对齐模型**：`Qwen/Qwen3-ForcedAligner-0.6B`
4. 模型文件会保存到 `models/` 目录

模型总大小约 **4.7GB**（ASR-1.7B + Aligner-0.6B），下载时间取决于网络。

---

## 验证安装

启动后看到以下界面即安装成功：

```
浏览器打开 http://127.0.0.1:7860

Qwen-ASR 字幕制作工具
├── 🎤 语音识别（上传音频 → 开始识别）
├── 🎯 强制对齐（上传音频 + 粘贴文本 → 开始对齐）
└── ⚙️ 设置（模型管理 / 硬件配置 / LLM 配置）
```

---

## 故障排查 / Troubleshooting

### macOS："python3 命令未找到"

```bash
# 安装 Homebrew（如未安装）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# 安装 Python
brew install python@3.12
```

### Windows："python 不是内部或外部命令"

重新运行 Python 安装程序，勾选 **"Add Python to PATH"**，或双击 `start.bat` 自动安装。

### pip 安装缓慢

脚本默认使用阿里云镜像 (`mirrors.aliyun.com`)。如需更换：

```bash
pip install -r requirements.txt -i https://pypi.org/simple
```

### 显存不足（OOM）

在 **设置 → 硬件与模型** 中选择 `0.6B` 模型而非 `1.7B`。

### 端口被占用

脚本会自动尝试 7860-7870 之间的可用端口。如需指定端口：

```bash
# Windows PowerShell
$env:GRADIO_SERVER_PORT=7861; python app.py

# macOS / Linux
GRADIO_SERVER_PORT=7861 python app.py
```

---

## 目录结构说明

```
qwen-asr-srt/
├── app.py                 # 主入口
├── config/                # 配置文件
├── core/                  # 核心逻辑（ASR、对齐、音频处理）
├── ui/                    # 界面组件
├── utils/                 # 工具（硬件检测、模型下载、LLM）
├── models/                # 模型文件（需下载）
├── venv/                  # 虚拟环境（自动创建）
├── requirements.txt       # Python 依赖
├── start.bat              # Windows 一键启动
└── start.sh               # macOS/Linux 一键启动
```
