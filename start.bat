@echo off
if exist "venv\Scripts\python.exe" (
    echo Starting Deliberate AI...
    call venv\Scripts\activate.bat
    python launch.py
) else (
    echo Virtual environment not found!
    echo Please run 'install.bat' first
    pause
)
