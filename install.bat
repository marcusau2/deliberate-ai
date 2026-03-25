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

echo [0/7] Checking Visual C++ Redistributable...
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
    set VC_Redist_Needed=1
) else (
    echo     Visual C++ Redistributable found
    set VC_Redist_Needed=0
)

echo.
echo [1/7] Checking for NVIDIA GPU...

echo.
echo [1/7] Checking for NVIDIA GPU...
REM Check if NVIDIA GPU is available
powershell -Command "Get-CimInstance Win32_VideoController | Where-Object { $_.Name -like '*NVIDIA*' }" >nul 2>&1
if errorlevel 1 (
    echo [INFO] No NVIDIA GPU detected or NVIDIA drivers not installed
    echo         Installing CPU version of PyTorch (works on all systems)
    set USE_GPU=0
) else (
    echo [INFO] NVIDIA GPU detected
    echo         Installing GPU-accelerated PyTorch (CUDA support)
    set USE_GPU=1
)

echo.
echo [2/7] Creating virtual environment...
if not exist "venv" (
    py -3.10 -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        echo Make sure Python 3.10 is installed (py -3.10)
        pause
        exit /b 1
    )
) else (
    echo     Virtual environment already exists
)

echo.
echo [3/7] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [4/7] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo.
echo [5/7] Installing PyTorch...
if !USE_GPU!==1 (
    echo     Installing GPU-accelerated PyTorch (CUDA 12.1)
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --quiet
) else (
    echo     Installing CPU-only PyTorch
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet
)
if errorlevel 1 (
    echo [ERROR] Failed to install PyTorch
    pause
    exit /b 1
)

echo.
echo [6/7] Installing remaining dependencies...
echo     This may take a few minutes...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo [7/7] Downloading Kokoro voice models...
python scripts\download_voices.py
if errorlevel 1 (
    echo [WARNING] Voice download failed. Voices will be downloaded on first run.
)

echo.
echo [7/7] Installation complete!

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
if !USE_GPU!==1 (
    echo [INFO] GPU acceleration enabled! PyTorch will use your NVIDIA GPU.
) else (
    echo [INFO] Running in CPU mode. For faster TTS, install an NVIDIA GPU.
)
echo.
echo For help, see README.md
echo.
pause
