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
echo   按任意键自动下载 ffmpeg，或关闭窗口手动安装
pause >nul

set FFMPEG_ZIP=%TEMP%\ffmpeg.zip
set FFMPEG_DIR=%~dp0ffmpeg-bin

REM 尝试多个下载源（带进度显示和超时）
set FFMPEG_OK=0

echo.
echo   ▸ 尝试下载源 1/2（GitHub）...
curl.exe -L -o "%FFMPEG_ZIP%" --connect-timeout 15 --max-time 180 "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
if exist "%FFMPEG_ZIP%" (
    for %%i in ("%FFMPEG_ZIP%") do if %%~zi gtr 1000 set FFMPEG_OK=1
)

if %FFMPEG_OK%==0 (
    echo.
    echo   ▸ 尝试下载源 2/2（国内镜像）...
    curl.exe -L -o "%FFMPEG_ZIP%" --connect-timeout 15 --max-time 300 "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    if exist "%FFMPEG_ZIP%" (
        for %%i in ("%FFMPEG_ZIP%") do if %%~zi gtr 1000 set FFMPEG_OK=1
    )
)

if %FFMPEG_OK%==0 (
    echo.
    echo   ffmpeg 下载失败，请手动安装：
    echo   https://ffmpeg.org/download.html
    goto :ffmpeg_done
)

echo.
echo   正在解压 ffmpeg...
if not exist "%TEMP%\ffmpeg-extracted" mkdir "%TEMP%\ffmpeg-extracted"

REM 先用 PowerShell 解压，失败则用 tar
REM 注意：无法判定实际文件所在目录，所以用 dir 搜索
set EXTRACTED_DIR=%TEMP%\ffmpeg-extracted

REM 清空残留
if exist "%EXTRACTED_DIR%" rmdir /s /q "%EXTRACTED_DIR%" >nul 2>&1
mkdir "%EXTRACTED_DIR%" >nul 2>&1

REM 尝试 PowerShell 解压
powershell -Command "try { Expand-Archive -Path '%FFMPEG_ZIP%' -DestinationPath '%EXTRACTED_DIR%' -Force; exit 0 } catch { exit 1 }" >nul 2>&1

REM 如果 PowerShell 解压失败，尝试 tar（Windows 10 1803+ 内置）
if not exist "%EXTRACTED_DIR%\*" (
    tar -xf "%FFMPEG_ZIP%" -C "%EXTRACTED_DIR%" >nul 2>&1
)

REM 从解压目录中递归搜索 ffmpeg.exe
if not exist "%FFMPEG_DIR%" mkdir "%FFMPEG_DIR%" >nul 2>&1
for /r "%EXTRACTED_DIR%" %%f in (ffmpeg.exe) do (
    if exist "%%f" copy "%%f" "%FFMPEG_DIR%\ffmpeg.exe" >nul 2>&1
)
for /r "%EXTRACTED_DIR%" %%f in (ffprobe.exe) do (
    if exist "%%f" copy "%%f" "%FFMPEG_DIR%\ffprobe.exe" >nul 2>&1
)

del "%FFMPEG_ZIP%"
rmdir /s /q "%EXTRACTED_DIR%" >nul 2>&1

if exist "%FFMPEG_DIR%\ffmpeg.exe" (
    set "PATH=%FFMPEG_DIR%;%PATH%"
    echo   ffmpeg 已安装到 %FFMPEG_DIR%
) else (
    echo   解压失败，请手动安装 ffmpeg：
    echo   https://ffmpeg.org/download.html
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
    where nvidia-smi >nul 2>&1
    if not errorlevel 1 (
        echo   检测到 NVIDIA 显卡，正在安装 CUDA 版 PyTorch...
        echo.
        echo   ▸ 尝试国内镜像...
        "%VENV_PYTHON%" -m pip install "torch>=2.0" --index-url https://mirrors.aliyun.com/pytorch/whl/cu124 2>&1
        "%VENV_PYTHON%" -c "import torch; exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
        if errorlevel 1 (
            echo.
            echo   ▸ 尝试官方源...
            "%VENV_PYTHON%" -m pip install "torch>=2.0" --index-url https://download.pytorch.org/whl/cu124 2>&1
        )
        "%VENV_PYTHON%" -c "import torch; exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
        if not errorlevel 1 (
            echo   CUDA PyTorch 安装成功
        ) else (
            echo   [警告] CUDA PyTorch 安装失败，将使用 CPU 模式运行
        )
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
