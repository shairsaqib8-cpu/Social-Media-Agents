@echo off
title Video Virality Analyzer - Port 8004
cd /d "%~dp0"

:: Kill any old instance on port 8004
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8004 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo Starting Video Virality Analyzer on http://localhost:8004
python app.py
pause
