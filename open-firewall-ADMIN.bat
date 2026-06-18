@echo off
:: Run this file as Administrator (right-click → Run as administrator)
echo Opening firewall ports for Claude Agents...

netsh advfirewall firewall delete rule name="YouTube Research Agent" >nul 2>&1
netsh advfirewall firewall add rule name="YouTube Research Agent" dir=in action=allow protocol=TCP localport=8000
echo Port 8000 opened (YouTube Research Agent)

netsh advfirewall firewall delete rule name="GEO Optimization Agent" >nul 2>&1
netsh advfirewall firewall add rule name="GEO Optimization Agent" dir=in action=allow protocol=TCP localport=8002
echo Port 8002 opened (GEO Optimization Agent)

netsh advfirewall firewall delete rule name="Content Optimizer Agent" >nul 2>&1
netsh advfirewall firewall add rule name="Content Optimizer Agent" dir=in action=allow protocol=TCP localport=8003
echo Port 8003 opened (Content Optimizer Agent)

echo.
echo Done! All agents are now accessible on your network.
echo From another PC, open a browser and go to:
echo   http://192.168.1.34:8000   YouTube Research Agent
echo   http://192.168.1.34:8002   GEO Optimization Agent
echo   http://192.168.1.34:8003   Content Optimizer Agent
echo.
pause
