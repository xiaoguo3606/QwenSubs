@echo off
cd /d "%~dp0"
chcp 65001 >nul 2>&1

echo ============================================
echo      QwenSubs v0.0.3 - 一键启动
echo ============================================
echo.

set MIN_PYTHON=3.10
set VENV_PYTHON=venv\Scripts\python.exe
set PORT=8000
set MAX_PORT=8005

REM ---- 1. Find or install Python -------------------------
echo [1/5] 检查 Python 环境...


REM Check if Python exists and meets version requirement
python --version >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        for /f "usebackq delims=" %%i in (`python --version 2^>nul`) do echo   %%i
        goto :setup_env
    )
)

echo   未找到 Python 3.10+，正在尝试下载...
echo.

set PY_VERSION=3.12.9
set INSTALLER=%TEMP%\python-installer.exe

REM Try multiple download mirrors
echo   正在下载 Python %PY_VERSION%（可能需要一分钟）...
powershell -Command "try { (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-amd64.exe', '%INSTALLER%') } catch { exit 1 }" >nul 2>&1

if not exist "%INSTALLER%" (
    echo.
    echo   [错误] 下载失败，请手动安装 Python：
    echo   https://www.python.org/downloads/
    echo   安装时请勾选 "Add Python to PATH"。
    pause
    exit /b 1
)

echo   正在安装 Python %PY_VERSION%...
start /wait "" "%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 Include_doc=0 Include_tcltk=0

REM Wait for install to complete
echo   等待安装完成...
:wait_python
timeout /t 2 /nobreak >nul
python --version >nul 2>&1
if errorlevel 1 goto wait_python

del "%INSTALLER%"
for /f "usebackq delims=" %%i in (`python --version 2^>nul`) do echo   %%i 已安装

REM ---- 2. ffmpeg check ----------------------------------
:setup_env
echo [2/5] 检查系统依赖...

where ffmpeg >nul 2>&1
if not errorlevel 1 goto :ffmpeg_found
echo   未找到 ffmpeg
echo   WAV/FLAC/OGG 格式可用内置工具处理
echo   其他格式（MP3/M4A 等）需要 ffmpeg
echo.
echo   按任意键自动下载 ffmpeg（约 5 秒），或关闭窗口手动安装
pause >nul
echo   正在下载 ffmpeg...
powershell -Command "try { (New-Object System.Net.WebClient).DownloadFile('https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip', '%TEMP%\ffmpeg.zip') } catch { exit 1 }" >nul 2>&1
if not exist "%TEMP%\ffmpeg.zip" (
    echo   ffmpeg 下载失败，请手动安装：https://ffmpeg.org/download.html
    goto :ffmpeg_done
)
echo   正在解压 ffmpeg...
powershell -Command "Expand-Archive -Path '%TEMP%\ffmpeg.zip' -DestinationPath '%TEMP%\ffmpeg-extracted' -Force" >nul 2>&1
for /d %%i in ("%TEMP%\ffmpeg-extracted\*") do (
    if exist "%%i\bin\ffmpeg.exe" (
        xcopy /e /i /y "%%i\bin" "%~dp0ffmpeg-bin\" >nul
    )
)
del "%TEMP%\ffmpeg.zip"
if exist "%~dp0ffmpeg-bin\ffmpeg.exe" (
    set "PATH=%~dp0ffmpeg-bin;%PATH%"
    echo   ffmpeg 已安装
) else (
    echo   ffmpeg 解压失败，请手动安装：https://ffmpeg.org/download.html
)
goto :ffmpeg_done
:ffmpeg_found
echo   ffmpeg 已找到
:ffmpeg_done

REM ---- 3. Virtual environment ---------------------------
echo [3/5] 设置虚拟环境...

if not exist "%VENV_PYTHON%" (
    python -m venv venv
)
if not exist "%VENV_PYTHON%" (
    echo.
    echo   [错误] 创建虚拟环境失败。
    pause
    exit /b 1
)
echo   虚拟环境已就绪

echo   正在安装依赖（可能需要一些时间）...
"%VENV_PYTHON%" -m pip install --upgrade pip -q >nul 2>&1
"%VENV_PYTHON%" -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo.
    echo   [错误] 依赖安装失败。
    echo   请检查网络连接后重试。
    pause
    exit /b 1
)
echo   依赖安装完成

REM ---- 3b. CUDA check (Windows only) -------------------------
"%VENV_PYTHON%" -c "import torch; exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
if errorlevel 1 (
    REM Check if NVIDIA GPU exists via nvidia-smi
    where nvidia-smi >nul 2>&1
    if not errorlevel 1 (
        echo   检测到 NVIDIA 显卡，正在安装 CUDA 版 PyTorch...
        "%VENV_PYTHON%" -m pip install "torch>=2.0" --index-url https://download.pytorch.org/whl/cu124 -q
        echo   CUDA PyTorch 安装完成
    )
)

REM ---- 4. Frontend (pre-built in dist/) ------------------
echo [4/5] 准备前端...

set FRONTEND_BUILT=0
if exist "frontend\dist\index.html" (
    echo   已有预构建的前端文件，可直接使用
    set FRONTEND_BUILT=1
)

REM Build if Node.js available
where node >nul 2>&1
if not errorlevel 1 (
    echo   检测到 Node.js，正在构建最新前端...
    cd frontend

    where pnpm >nul 2>&1
    if not errorlevel 1 (
        call pnpm install --frozen-lockfile >nul 2>&1
        if errorlevel 1 call pnpm install >nul 2>&1
        call pnpm build >nul 2>&1
    ) else (
        call npm install >nul 2>&1
        call npm run build >nul 2>&1
    )

    if exist "dist\index.html" (
        echo   前端构建完成
        set FRONTEND_BUILT=1
    )
    cd ..
)

if "%FRONTEND_BUILT%"=="0" (
    echo   警告：前端未构建，应用可能无法正常显示
    echo   如需自定义前端，请安装 Node.js 18+
)

REM ---- 5. Port check & Launch ---------------------------
echo [5/5] 启动应用...

:check_port
netstat -ano 2>nul | findstr ":%PORT% " >nul 2>&1
if errorlevel 1 goto launch
set /a PORT+=1
if %PORT% gtr %MAX_PORT% (
    echo   端口 8000-%MAX_PORT% 均被占用。
    pause
    exit /b 1
)
goto check_port

:launch
echo.
echo ============================================
echo  正在启动 QwenSubs v0.0.3
echo  访问 http://127.0.0.1:%PORT%
echo  按 Ctrl+C 停止服务
echo ============================================
echo.

"%VENV_PYTHON%" -m uvicorn backend.main:app --host 0.0.0.0 --port %PORT%

echo.
echo 服务已停止。
pause
