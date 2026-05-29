@echo off
cd /d "%~dp0"
chcp 65001 >nul 2>&1

echo ============================================
echo      QwenSubs v0.0.2 - 一键启动
echo ============================================
echo.

set MIN_PYTHON=3.10
set VENV_PYTHON=venv\Scripts\python.exe
set PORT=8000
set MAX_PORT=8005

REM ---- 1. Find or install Python -------------------------
echo [1/5] 检查 Python 环境...

set PYTHON_CMD=python

REM Check if Python exists and meets version requirement
python --version >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        for /f "usebackq delims=" %%i in (`python --version 2^>nul`) do echo   %%i found
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
    echo   [ERROR] Download failed. Please install Python manually:
    echo   https://www.python.org/downloads/
    echo   Make sure to check "Add Python to PATH".
    pause
    exit /b 1
)

echo   Installing Python %PY_VERSION%...
start /wait "" "%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 Include_doc=0 Include_tcltk=0

REM Wait for install to complete
echo   Waiting for installation...
:wait_python
timeout /t 2 /nobreak >nul
python --version >nul 2>&1
if errorlevel 1 goto wait_python

del "%INSTALLER%"
for /f "usebackq delims=" %%i in (`python --version 2^>nul`) do echo   %%i installed

REM ---- 2. ffmpeg check ----------------------------------
:setup_env
echo [2/5] 检查系统依赖...

where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo   未找到 ffmpeg（音频转换将回退到 pydub）
) else (
    echo   ffmpeg 已找到
)

REM ---- 3. Virtual environment ---------------------------
echo [3/5] 设置虚拟环境...

if not exist "%VENV_PYTHON%" (
    python -m venv venv
)
if not exist "%VENV_PYTHON%" (
    echo.
    echo   [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)
echo   虚拟环境已就绪

echo   正在安装依赖（可能需要一些时间）...
"%VENV_PYTHON%" -m pip install --upgrade pip -q >nul 2>&1
"%VENV_PYTHON%" -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo.
    echo   [ERROR] Failed to install dependencies.
    echo   Check your network connection and try again.
    pause
    exit /b 1
)
echo   依赖安装完成

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
netstat -ano 2>nul | findstr "0.0.0.0:%PORT% " >nul 2>&1
if errorlevel 1 goto launch
set /a PORT+=1
if %PORT% gtr %MAX_PORT% (
    echo   Ports 8000-%MAX_PORT% all in use.
    pause
    exit /b 1
)
goto check_port

:launch
echo.
echo ============================================
echo  正在启动 QwenSubs v0.0.2
echo  访问 http://127.0.0.1:%PORT%
echo  按 Ctrl+C 停止服务
echo ============================================
echo.

"%VENV_PYTHON%" -m uvicorn backend.main:app --host 0.0.0.0 --port %PORT%

echo.
echo 服务已停止。
pause
