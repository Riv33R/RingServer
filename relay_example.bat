@echo off
:: ============================================================
:: ============================================================
:: relay_example.bat - Example script for relay control
:: 
:: This script is called automatically when the bell triggers.
:: The first argument (%1) is the bell duration in seconds.
::
:: Adapt this for your equipment:
::   - COM port (RS-232 relay)
::   - GPIO (via specialized utilities)
::   - HTTP API (smart relays, Shelly, Sonoff)
::   - Pin shorting via USB-relay (hidusb-relay-cmd.exe)
:: ============================================================

set DURATION=%1
if "%DURATION%"=="" set DURATION=5

echo [%date% %time%] Bell triggered for %DURATION% seconds >> relay_log.txt

:: --- EXAMPLE 1: USB relay (hidusb-relay) ---
:: Download hidusb-relay-cmd.exe from GitHub
:: hidusb-relay-cmd.exe on 0
:: timeout /t %DURATION% /nobreak >nul
:: hidusb-relay-cmd.exe off 0

:: --- EXAMPLE 2: HTTP API (Shelly 1) ---
:: curl -s "http://192.168.1.100/relay/0?turn=on" >nul
:: timeout /t %DURATION% /nobreak >nul
:: curl -s "http://192.168.1.100/relay/0?turn=off" >nul

:: --- EXAMPLE 3: COM port via mode (legacy method) ---
:: mode COM1 dtr=on >nul
:: timeout /t %DURATION% /nobreak >nul
:: mode COM1 dtr=off >nul

:: --- TEST MODE: log only ---
echo [%date% %time%] Relay activated for %DURATION%s (test mode) >> relay_log.txt
timeout /t %DURATION% /nobreak >nul
echo [%date% %time%] Relay deactivated >> relay_log.txt

exit /b 0
