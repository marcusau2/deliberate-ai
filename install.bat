@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   Deliberate AI - Windows Installer
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python 3.10, 3.11, or 3.12 from https://www.python.org/
    pause
    exit /b 1
)

echo [0/6] Checking Visual C++ Redistributable...
REM Check if VC++ redistributable is installed (registry key)
reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Microsoft Visual C++ 2015-2022 Redistributable not found!
    echo           This is required for PyTorch to work on Windows.
    echo           Download and install from:
    echo           https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
    echo           You can install it now or after installation completes.
    echo.
    set VC_REDist_Needed=1
) else (
    echo     Visual C++ Redistributable found
    set VC_Redist_Needed=0
)

echo [1/5] Creating virtual environment...
if not exist "venv" (
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
) else (
    echo     Virtual environment already exists
)

echo.
echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [3/5] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo.
echo [4/5] Installing dependencies...
echo     This may take a few minutes...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo [5/5] Downloading Kokoro voice models...
python scripts\download_voices.py
if errorlevel 1 (
    echo [WARNING] Voice download failed. Voices will be downloaded on first run.
)

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo Next steps:
echo   1. Edit 'settings.json' with your vLLM endpoint and model
echo   2. Run 'start.bat' to launch the application
echo.
if !VC_Redist_Needed!==1 (
    echo [IMPORTANT] If you get a DLL error when starting the app:
    echo             Install Visual C++ Redistributable from:
    echo             https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
)
echo For help, see README.md
echo.
pause
