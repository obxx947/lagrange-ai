@echo off
rem ============================================================
rem  Lagrange AI - LAN Deploy (double-click to run)
rem  Starts: Original backend (port 3000) + Static version (port 3002)
rem  Accessible from phones / other PCs on the same WiFi
rem  NOTE: Keep this file ASCII-only (no Chinese) for cmd safety.
rem ============================================================
title Lagrange AI - LAN Deploy

rem ---------- 1. Check Python ----------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+ first:
    echo         https://www.python.org/downloads/
    pause
    exit /b 1
)

rem ---------- 2. Get local LAN IPv4 ----------
set "LAN_IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set "LAN_IP=%%a"
    goto :got_ip
)
:got_ip
set "LAN_IP=%LAN_IP: =%"

rem ---------- 3. Firewall rules (needs admin; ignore failure) ----------
netsh advfirewall firewall delete rule name="LagrangeAI-Port3000" >nul 2>nul
netsh advfirewall firewall delete rule name="LagrangeAI-Port3002" >nul 2>nul
netsh advfirewall firewall add rule name="LagrangeAI-Port3000" dir=in action=allow protocol=TCP localport=3000 >nul 2>nul
netsh advfirewall firewall add rule name="LagrangeAI-Port3002" dir=in action=allow protocol=TCP localport=3002 >nul 2>nul

rem ---------- 4. Start services (separate windows; closing a window stops that service) ----------
rem %~dp0 ends with backslash; strip it to avoid quote escaping
set "P3=%~dp0"
if "%P3:~-1%"=="\" set "P3=%P3:~0,-1%"
rem Static version folder = this folder name + "3" (no Chinese bytes needed)
set "P3S=%P3%3"

echo [1/3] Starting original backend (FastAPI) on port 3000 ...
start "Lagrange-Backend-3000" cmd /k "cd /d %P3% && python main.py"

echo [2/3] Starting static version on port 3002 ...
start "Lagrange-Static-3002" cmd /k "cd /d %P3S% && python -m http.server 3002 --bind 0.0.0.0"

echo [3/3] Waiting for services ...
ping -n 9 127.0.0.1 >nul

rem ---------- 5. Print access addresses ----------
echo.
echo ============================================================
echo   Deployed! Access URLs:
echo.
set "SHOW_IP=%LAN_IP%"
if not defined SHOW_IP set "SHOW_IP=YOUR_IP"
echo   Original (AI chat / battle sim) : http://%SHOW_IP%:3000
echo   Static (lightweight frontend)   : http://%SHOW_IP%:3002
echo   Local test (original)           : http://127.0.0.1:3000
echo.
echo   Phone / other PCs must be on the same WiFi / LAN.
echo   If not accessible: re-run this script as Administrator,
echo   or allow TCP 3000/3002 in Windows Firewall manually.
echo ============================================================
echo.
start "" "http://127.0.0.1:3000"
echo Press any key to close this window (services keep running)...
pause >nul
