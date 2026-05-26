@echo off
cd /d "%~dp0"

echo ============================================
echo  Qwen-ASR Subtitle Tool - One-Click Setup
echo ============================================
echo.

set VENV_PYTHON=venv\Scripts\python.exe
set PORT=7860
set MAX_PORT=7870

REM ---- 1. Find or install Python -----------------------
echo [1/3] Checking Python...

set PYTHON_CMD=python
python --version >nul 2>&1
if not errorlevel 1 goto :setup_env

REM ---- Python not found, download it -------------------
echo   Python not found, downloading...
echo   (this may take a minute)

set INSTALLER=%TEMP%\python-installer.exe
set PYTHON_DIR=%LOCALAPPDATA%\Programs\Python\Python312

REM Try multiple versions (unrolled to avoid delayed expansion issues)
powershell -Command "(New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe', '%INSTALLER%')" >nul 2>&1
if errorlevel 1 (
    powershell -Command "(New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe', '%INSTALLER%')" >nul 2>&1
)
if errorlevel 1 (
    powershell -Command "(New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe', '%INSTALLER%')" >nul 2>&1
)
if errorlevel 1 (
    powershell -Command "(New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.6/python-3.12.6-amd64.exe', '%INSTALLER%')" >nul 2>&1
)
if errorlevel 1 (
    powershell -Command "(New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.5/python-3.12.5-amd64.exe', '%INSTALLER%')" >nul 2>&1
)

if not exist "%INSTALLER%" (
    echo.
    echo [ERROR] Download failed. Please install Python manually:
    echo   https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH".
    pause
    exit /b 1
)

echo   Installing Python...
start /wait "" "%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 Include_doc=0 Include_tcltk=0

if not exist "%PYTHON_DIR%\python.exe" (
    echo.
    echo [ERROR] Installation failed.
    echo Please install Python manually from:
    echo   https://www.python.org/downloads/
    pause
    exit /b 1
)

set PYTHON_CMD=%PYTHON_DIR%\python.exe
del "%INSTALLER%"
echo   Python 3.12 installed

REM ---- 2. Setup venv and install dependencies ----------
:setup_env
echo [2/3] Setting up environment...

if not exist "%VENV_PYTHON%" (
    "%PYTHON_CMD%" -m venv venv
)
if not exist "%VENV_PYTHON%" (
    echo.
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)
echo   Virtual environment ready

"%VENV_PYTHON%" -m pip install --upgrade pip >nul 2>&1
"%VENV_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install dependencies.
    echo Check your network connection and try again.
    pause
    exit /b 1
)
echo   Dependencies installed

REM ---- 3. Launch ---------------------------------------
echo [3/3] Starting application...

:scan_port
netstat -ano | findstr /C:"127.0.0.1:%PORT% " >nul 2>&1
if errorlevel 1 goto launch
if %PORT% geq %MAX_PORT% (
    echo   Ports 7860-%MAX_PORT% all in use.
    pause
    exit /b 1
)
set /a PORT+=1
goto scan_port

:launch
echo.
echo ============================================
echo  Starting server...
echo  Open http://127.0.0.1:%PORT% in your browser
echo  Press Ctrl+C to stop
echo ============================================
echo.
set GRADIO_SERVER_PORT=%PORT%
"%VENV_PYTHON%" app.py
echo.
echo Server stopped.
pause
