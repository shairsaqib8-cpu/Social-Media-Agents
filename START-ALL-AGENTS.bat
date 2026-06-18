@echo off
echo ============================================
echo   Starting All Claude Agents
echo ============================================
echo.
echo Your network IP: 192.168.1.34
echo.
echo Starting YouTube Research Agent on port 8000...
start "YouTube Research Agent :8000" cmd /k "cd /d D:\Claude-Access-Data\youtube-research-agent && python app.py"

timeout /t 2 >nul

echo Starting Content Optimizer Agent on port 8003...
start "Content Optimizer Agent :8003" cmd /k "cd /d D:\Claude-Access-Data\content-optimizer-agent && python app.py"

echo.
echo ============================================
echo   All agents started!
echo   Access from any PC on your network:
echo.
echo   http://192.168.1.34:8000  - YouTube Research
echo   http://192.168.1.34:8003  - Content Optimizer
echo ============================================
echo.
pause
