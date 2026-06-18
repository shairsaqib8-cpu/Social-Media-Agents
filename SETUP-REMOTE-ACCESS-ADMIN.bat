@echo off
:: ===========================================================
::  Run this as Administrator (right-click → Run as administrator)
::  Sets up full remote access to Claude agents + Claude Code
:: ===========================================================

echo ============================================
echo   Claude Remote Access Setup (Admin)
echo ============================================
echo.

:: --- 1. Open Firewall Ports for Agents ---
echo [1/3] Opening firewall ports for agents...
netsh advfirewall firewall delete rule name="YouTube Research Agent" >nul 2>&1
netsh advfirewall firewall add rule name="YouTube Research Agent" dir=in action=allow protocol=TCP localport=8000 >nul
echo   Port 8000 - YouTube Research Agent OK

netsh advfirewall firewall delete rule name="Content Optimizer Agent" >nul 2>&1
netsh advfirewall firewall add rule name="Content Optimizer Agent" dir=in action=allow protocol=TCP localport=8003 >nul
echo   Port 8003 - Content Optimizer Agent OK

:: --- 2. Install and Start OpenSSH Server (for Claude Code remote access) ---
echo.
echo [2/3] Setting up OpenSSH Server for Claude Code remote access...

powershell -Command "Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0" >nul 2>&1
if %errorlevel%==0 (
    echo   OpenSSH Server installed.
) else (
    echo   OpenSSH Server already installed or needs Windows Update.
)

sc config sshd start= auto >nul 2>&1
net start sshd >nul 2>&1
echo   SSH Service started and set to auto-start.

netsh advfirewall firewall delete rule name="OpenSSH Remote Access" >nul 2>&1
netsh advfirewall firewall add rule name="OpenSSH Remote Access" dir=in action=allow protocol=TCP localport=22 >nul
echo   Port 22 (SSH) opened in firewall.

:: --- 3. Show connection info ---
echo.
echo [3/3] Done! Here is how to connect from another PC:
echo.
echo ============================================
echo   ACCESS FROM ANOTHER PC
echo ============================================
echo.
echo   AGENTS (open in browser):
echo   http://192.168.1.34:8000  - YouTube Research Agent
echo   http://192.168.1.34:8003  - Content Optimizer Agent
echo.
echo   CLAUDE CODE (via SSH terminal):
echo   1. On the other PC, open a terminal
echo   2. Run: ssh %USERNAME%@192.168.1.34
echo   3. Enter your Windows password when asked
echo   4. Then run: claude
echo.
echo   NOTE: Make sure to run START-ALL-AGENTS.bat on this PC
echo   before trying to access agents from another computer.
echo ============================================
echo.
pause
