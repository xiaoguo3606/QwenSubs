@echo off
cd /d "%~dp0"
chcp 65001 >nul 2>&1

echo ============================================
echo        QwenSub - One-Click Startup
echo ============================================
echo.

set MIN_PYTHON=3.10
set VENV_PYTHON=venv\Scripts\python.exe
set PORT=8000
set MAX_PORT=8005

REM ---- 1. Find or install Python -------------------------
echo [1/5] Checking Python...

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

echo   Python 3.10+ not found. Attempting to download...
echo.

set PY_VERSION=3.12.9
set INSTALLER=%TEMP%\python-installer.exe

REM Try multiple download mirrors
echo   Downloading Python %PY_VERSION% (this may take a minute)...
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
echo [2/5] Checking system dependencies...

where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo   ffmpeg not found (audio conversion may fall back to pydub)
) else (
    echo   ffmpeg found
)

REM ---- 3. Virtual environment ---------------------------
echo [3/5] Setting up virtual environment...

if not exist "%VENV_PYTHON%" (
    python -m venv venv
)
if not exist "%VENV_PYTHON%" (
    echo.
    echo   [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)
echo   Virtual environment ready

echo   Installing dependencies (this may take a while)...
"%VENV_PYTHON%" -m pip install --upgrade pip -q >nul 2>&1
"%VENV_PYTHON%" -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo.
    echo   [ERROR] Failed to install dependencies.
    echo   Check your network connection and try again.
    pause
    exit /b 1
)
echo   Dependencies installed

REM ---- 4. Frontend (pre-built in dist/) ------------------
echo [4/5] Preparing frontend...

set FRONTEND_BUILT=0
if exist "frontend\dist\index.html" (
    echo   Pre-built frontend found, ready to use
    set FRONTEND_BUILT=1
)

REM Build if Node.js available
where node >nul 2>&1
if not errorlevel 1 (
    echo   Node.js found, building latest...
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
        echo   Frontend built successfully
        set FRONTEND_BUILT=1
    )
    cd ..
)

if "%FRONTEND_BUILT%"=="0" (
    echo   WARNING: Frontend not built.
    echo   The app may not display correctly.
    echo   Install Node.js to build: https://nodejs.org/
)

REM ---- 5. Port check & Launch ---------------------------
echo [5/5] Starting application...

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
echo  Starting QwenSub
echo  Open http://127.0.0.1:%PORT% in your browser
echo  Press Ctrl+C to stop
echo ============================================
echo.

"%VENV_PYTHON%" -m uvicorn backend.main:app --host 0.0.0.0 --port %PORT%

echo.
echo Server stopped.
pause
