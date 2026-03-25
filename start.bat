@echo off
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe sos.py
) else (
    echo Virtual environment not found!
    echo Please run 'install.bat' first
    pause
)
