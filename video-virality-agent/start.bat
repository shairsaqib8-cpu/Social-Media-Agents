@echo off
title Video Virality Analyzer — Port 8004
cd /d "%~dp0"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Run setup.bat first.
    pause & exit /b 1
)

:: Check .env exists
if not exist ".env" (
    echo ERROR: .env file missing. Run setup.bat first.
    pause & exit /b 1
)

:: Warn if keys are placeholders
findstr /C:"your_groq_api_key_here" .env >nul 2>&1
if not errorlevel 1 (
    echo WARNING: GROQ_API_KEY is not set in .env
    echo Open .env and add your key from https://console.groq.com
    pause & exit /b 1
)

:: Kill any old process on port 8004
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr :8004 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul 2>&1

echo.
echo ============================================================
echo  Video Virality Analyzer running at http://localhost:8004
echo  Press Ctrl+C to stop
echo ============================================================
echo.
python app.py
pause
