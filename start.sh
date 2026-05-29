#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "╔══════════════════════════════════════╗"
echo "║      QwenSubs v0.0.2 — 一键启动       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 颜色 ───────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e " ${CYAN}→${NC} $1"; }
ok()    { echo -e " ${GREEN}✓${NC} $1"; }
warn()  { echo -e " ${YELLOW}⚠${NC} $1"; }
err()   { echo -e " ${RED}✗${NC} $1"; }

# ── 查找或安装 Python ──────────────────────────────
PYTHON=""
MIN_PYTHON="3.10"

find_python() {
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            local major=${ver%.*}
            local minor=${ver#*.}
            if [ "$major" -ge 3 ] && [ "$minor" -ge "${MIN_PYTHON#*.}" ] 2>/dev/null; then
                PYTHON="$cmd"
                return 0
            fi
        fi
    done
    return 1
}

install_python_macos() {
    if command -v brew &>/dev/null; then
        info "通过 Homebrew 安装 Python..."
        brew install python@3.12
        local brew_path
        brew_path=$(brew --prefix python@3.12 2>/dev/null)/bin/python3
        if [ -f "$brew_path" ]; then
            PYTHON="$brew_path"
            return 0
        fi
    fi

    # 备用方案：从官网下载安装包
    warn "未找到 Homebrew，将从 python.org 下载安装包"
    local PY_VERSION="3.12.9"
    local PKG_URL="https://www.python.org/ftp/python/$PY_VERSION/python-$PY_VERSION-macos11.pkg"
    local TMP_PKG="/tmp/python-$PY_VERSION.pkg"

    info "下载 Python $PY_VERSION..."
    curl -# -o "$TMP_PKG" "$PKG_URL" || {
        err "下载失败，请手动安装 Python"
        echo "  https://www.python.org/downloads/"
        exit 1
    }

    info "安装 Python $PY_VERSION（需要管理员密码）..."
    sudo installer -pkg "$TMP_PKG" -target / 2>/dev/null
    rm -f "$TMP_PKG"

    # 检查安装后的 Python
    for cmd in /usr/local/bin/python3 /usr/bin/python3 python3; do
        if command -v "$cmd" &>/dev/null; then
            local ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            local minor=${ver#*.}
            if [ "$minor" -ge "${MIN_PYTHON#*.}" ]; then
                PYTHON="$cmd"
                return 0
            fi
        fi
    done
    return 1
}

install_python_linux() {
    if command -v apt-get &>/dev/null; then
        info "通过 apt 安装 Python..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq python3 python3-venv python3-pip || {
            err "apt 安装失败，请手动安装 Python 3.10+"
            exit 1
        }
        PYTHON="python3"
        return 0
    elif command -v yum &>/dev/null; then
        info "通过 yum 安装 Python..."
        sudo yum install -y python3 python3-pip || {
            err "yum 安装失败，请手动安装 Python 3.10+"
            exit 1
        }
        PYTHON="python3"
        return 0
    elif command -v dnf &>/dev/null; then
        info "通过 dnf 安装 Python..."
        sudo dnf install -y python3 python3-pip || {
            err "dnf 安装失败，请手动安装 Python 3.10+"
            exit 1
        }
        PYTHON="python3"
        return 0
    fi
    return 1
}

# ── 环境检查 ────────────────────────────────────────
echo ""
info "检查系统环境..."

# Python
if ! find_python; then
    warn "未找到 Python ${MIN_PYTHON}+，尝试自动安装..."

    if [[ "$OSTYPE" == "darwin"* ]]; then
        install_python_macos || {
            err "Python 安装失败"
            echo "  请手动从 https://www.python.org/downloads/ 下载安装"
            exit 1
        }
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        install_python_linux || {
            err "Python 安装失败"
            echo "  请手动安装: sudo apt install python3 python3-venv python3-pip"
            exit 1
        }
    else
        err "不支持的操作系统: $OSTYPE"
        echo "  请手动安装 Python 3.10+"
        exit 1
    fi
fi
ok "Python: $($PYTHON --version 2>&1)"

# ffmpeg
if command -v ffmpeg &>/dev/null; then
    ok "ffmpeg: $({ ffmpeg -version 2>/dev/null | head -1 | grep -oE 'ffmpeg version [^ ]+' || echo "已安装"; })"
else
    warn "ffmpeg 未安装（音频处理需要）"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "    安装: brew install ffmpeg"
    elif command -v apt-get &>/dev/null; then
        echo "    安装: sudo apt install ffmpeg"
    elif command -v yum &>/dev/null; then
        echo "    安装: sudo yum install ffmpeg"
    fi
    echo ""
fi

# ── 虚拟环境 ────────────────────────────────────────
echo ""
info "设置 Python 虚拟环境..."

VENV_PYTHON="venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    $PYTHON -m venv venv
    ok "虚拟环境已创建"
else
    ok "虚拟环境已存在"
fi

info "安装 Python 依赖..."
$VENV_PYTHON -m pip install --upgrade pip -q
$VENV_PYTHON -m pip install -r requirements.txt -q
ok "依赖安装完成"

# ── 前端构建（可选） ────────────────────────────────
echo ""
info "准备前端..."

FRONTEND_BUILT=false
if [ -f "frontend/dist/index.html" ]; then
    ok "已有预构建的前端文件"
    FRONTEND_BUILT=true
fi

if command -v node &>/dev/null; then
    if command -v pnpm &>/dev/null; then
        PKG="pnpm"
    elif command -v npm &>/dev/null; then
        PKG="npm"
    fi
    if [ -n "$PKG" ]; then
        info "检测到 Node.js + $PKG，构建最新前端..."
        cd frontend
        if [ "$PKG" = "pnpm" ]; then
            $PKG install --frozen-lockfile 2>/dev/null || $PKG install -q
        else
            $PKG install -q
        fi
        if $PKG run build -q 2>/dev/null; then
            ok "前端构建完成"
            FRONTEND_BUILT=true
        fi
        cd ..
    fi
fi

if [ "$FRONTEND_BUILT" != "true" ]; then
    warn "前端未构建，使用预构建版本"
    echo "    如需自定义前端，请安装 Node.js 18+"
fi

# ── 端口检查 ───────────────────────────────────────
PORT=8000
MAX_PORT=8005

check_port() {
    if command -v lsof &>/dev/null; then
        lsof -ti:"$1" &>/dev/null
    elif command -v ss &>/dev/null; then
        ss -tln | grep -q ":$1 "
    else
        return 1
    fi
}

if check_port $PORT; then
    FREE_PORT=""
    for try in $(seq $((PORT+1)) $MAX_PORT); do
        if ! check_port $try; then
            FREE_PORT=$try
            break
        fi
    done
    if [ -n "$FREE_PORT" ]; then
        PORT=$FREE_PORT
        warn "端口 8000 被占用，改用端口 $PORT"
    else
        err "端口 8000-$MAX_PORT 均被占用"
        echo "  请手动指定端口: python -m uvicorn backend.main:app --port <端口>"
        exit 1
    fi
fi

# ── 启动 ───────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════╗"
echo "║  正在启动 QwenSubs v0.0.2             ║"
echo "║  访问 http://127.0.0.1:$PORT          ║"
echo "║  按 Ctrl+C 停止服务                    ║"
echo "╚══════════════════════════════════════╝"
echo ""

$VENV_PYTHON -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
