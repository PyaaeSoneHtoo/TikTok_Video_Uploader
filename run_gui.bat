@echo off
title TikTok Video Uploader
cd /d "%~dp0"

echo ===========================================
echo       TikTok Video Uploader Launcher
echo ===========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [.venv not detected - creating virtual environment...]
    python -m venv .venv
    echo [Installing requirements...]
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
)

echo Starting TikTok Video Uploader GUI...
.\.venv\Scripts\python.exe gui_app.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with error code %ERRORLEVEL%.
    pause
)
