#!/usr/bin/env python3
"""First-run setup script: create venv, install deps, detect hardware, configure."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
VENV_DIR = PROJECT_DIR / "venv"


def main():
    print("=" * 60)
    print("QwenSub — 首次安装")
    print("=" * 60)

    # Step 1: Create virtual environment
    print("\n[1/4] 创建虚拟环境...")
    if VENV_DIR.exists():
        print("  虚拟环境已存在，跳过")
    else:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            check=True,
        )
        print("  ✓ 虚拟环境已创建")

    # Step 2: Install dependencies
    print("\n[2/4] 安装依赖...")
    pip = str(VENV_DIR / "bin" / "pip")
    if sys.platform == "win32":
        pip = str(VENV_DIR / "Scripts" / "pip.exe")

    subprocess.run(
        [pip, "install", "--upgrade", "pip"],
        check=True, capture_output=True,
    )
    subprocess.run(
        [pip, "install", "-r", str(PROJECT_DIR / "requirements.txt")],
        check=True,
    )
    print("  ✓ 依赖安装完成")

    # Step 3: Detect hardware
    print("\n[3/4] 检测硬件...")
    python = str(VENV_DIR / "bin" / "python")
    if sys.platform == "win32":
        python = str(VENV_DIR / "Scripts" / "python.exe")

    result = subprocess.run(
        [python, "-c", """
import sys
sys.path.insert(0, '.')
from utils.hardware_detector import detect
info = detect()
print(f"  设备: {info.device}")
print(f"  名称: {info.device_name}")
print(f"  显存: {info.vram_gb:.1f} GB")
print(f"  推荐模型: {info.recommended_model}")
if info.warnings:
    for w in info.warnings:
        print(f"  ⚠ {w}")
"""],
        cwd=PROJECT_DIR,
        capture_output=True, text=True,
    )
    print(result.stdout.strip())
    if result.stderr:
        print(f"  stderr: {result.stderr.strip()}")

    # Step 4: Initialize config
    print("\n[4/4] 初始化配置...")
    result = subprocess.run(
        [python, "-c", """
import sys
sys.path.insert(0, '.')
from config import settings as cfg
from utils.hardware_detector import detect
info = detect()
config = cfg.load()
config["device"] = info.device
config["asr_model"] = info.recommended_model
config["asr_model_size"] = info.recommended_size
cfg.save(config)
print(f"  设备: {info.device}")
print(f"  模型: {info.recommended_model}")
print("  ✓ 配置已初始化")
print()
print("  请运行以下命令启动程序：")
print(f"    source {VENV_DIR}/bin/activate && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000")
"""],
        cwd=PROJECT_DIR,
        capture_output=True, text=True,
    )
    print(result.stdout.strip())

    print("\n" + "=" * 60)
    print("安装完成！请打开「设置」页面下载模型后使用。")
    print("=" * 60)


if __name__ == "__main__":
    main()
