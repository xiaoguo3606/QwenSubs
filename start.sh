#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# ── Virtual environment ─────────────────────────────────
VENV_PYTHON="venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# ── Install / upgrade dependencies ──────────────────────
echo "安装/更新依赖..."
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r requirements.txt
echo ""

# ── Launch ──────────────────────────────────────────────
PORT=7860
MAX_PORT=7870

# Check if port is in use
if lsof -ti:$PORT &>/dev/null; then
    echo "端口 $PORT 已被占用。"
    echo "  1) 关闭现有进程并用 $PORT 重启"
    echo "  2) 依次尝试备用端口 ($((PORT+1))-$MAX_PORT)"
    echo "  3) 退出"
    read -r -p "请选择 (1/2/3): " choice
    case "$choice" in
        1)
            lsof -ti:$PORT | xargs kill -9 2>/dev/null
            sleep 1
            echo "已关闭旧进程。"
            ;;
        2)
            for try_port in $(seq $((PORT+1)) $MAX_PORT); do
                if ! lsof -ti:$try_port &>/dev/null; then
                    PORT=$try_port
                    echo "将使用端口 $PORT"
                    break
                fi
            done
            if [ "$PORT" = "7860" ]; then
                echo "错误：端口 $((PORT+1))-$MAX_PORT 均被占用，无法启动。"
                exit 1
            fi
            ;;
        3)
            echo "已退出。"
            exit 0
            ;;
    esac
fi

echo "正在启动 Qwen-ASR 字幕制作工具..."
echo "浏览器将自动打开 http://127.0.0.1:$PORT"
echo "按 Ctrl+C 停止服务"
echo ""

export GRADIO_SERVER_PORT=$PORT
"$VENV_PYTHON" app.py
