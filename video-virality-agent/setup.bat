@echo off
title Video Virality Analyzer — Setup
cd /d "%~dp0"

echo ============================================================
echo  Video Virality Analyzer — First-Time Setup
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo [OK] Python found:
python --version

echo.
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
:: Create .env if it doesn't exist
if not exist ".env" (
    echo Creating .env file — you must fill in your API keys.
    (
        echo GROQ_API_KEY=your_groq_api_key_here
        echo YOUTUBE_API_KEY=your_youtube_api_key_here
    ) > .env
    echo.
    echo IMPORTANT: Open the .env file and add your API keys:
    echo   GROQ_API_KEY  — free at https://console.groq.com
    echo   YOUTUBE_API_KEY — from https://console.cloud.google.com
    echo.
    notepad .env
) else (
    echo [OK] .env file already exists.
)

echo.
echo ============================================================
echo  Setup complete! Run start.bat to launch the agent.
echo ============================================================
pause
