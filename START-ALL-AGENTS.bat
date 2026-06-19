@echo off
echo ============================================
echo   Starting All AI Agents — Social Media Suite
echo ============================================
echo.

echo [1/4] YouTube Research Agent (port 8000)...
start "YouTube Research :8000" cmd /k "cd /d D:\Claude-Access-Data\youtube-research-agent && python app.py"
timeout /t 3 >nul

echo [2/4] Content Optimizer Agent (port 8003)...
start "Content Optimizer :8003" cmd /k "cd /d D:\Claude-Access-Data\content-optimizer-agent && python app.py"
timeout /t 3 >nul

echo [3/4] Video Virality Analyzer (port 8004)...
start "Video Virality :8004" cmd /k "cd /d D:\Claude-Access-Data\video-virality-agent && python -m uvicorn app:app --host 0.0.0.0 --port 8004"
timeout /t 3 >nul

echo [4/4] Script Optimizer Agent (port 8005)...
start "Script Optimizer :8005" cmd /k "cd /d D:\Claude-Access-Data\script-optimizer-agent && python -m uvicorn app:app --host 0.0.0.0 --port 8005"

echo.
echo ============================================
echo   All 4 agents launched!
echo.
echo   Hub:      http://localhost:8004/hub
echo   Research: http://localhost:8000
echo   Optimizer:http://localhost:8003
echo   Virality: http://localhost:8004
echo   Script:   http://localhost:8005
echo ============================================
