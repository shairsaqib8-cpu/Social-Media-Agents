@echo off
echo Starting Script Optimizer Agent on port 8005...
cd /d D:\Claude-Access-Data\script-optimizer-agent
python -m uvicorn app:app --host 0.0.0.0 --port 8005
pause
