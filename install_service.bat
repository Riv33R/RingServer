@echo off
:: ============================================================
:: ============================================================
:: install_service.bat - Installs RingScheduler as a
:: Windows Service using NSSM (Non-Sucking Service Manager)
:: 
:: Requirements:
::   1. Download NSSM from https://nssm.cc/download
::   2. Place nssm.exe next to this script
::   3. Run this file as Administrator
:: ============================================================
echo ========================================
echo  Installing Windows Service: RingScheduler
echo ========================================

cd /d "%~dp0"
set "APP_DIR=%CD%"
set PYTHON_EXE=

:: Try to find Python
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    if not defined PYTHON_EXE set PYTHON_EXE=%%i
)

:: If virtualenv exists - use it
if exist "%APP_DIR%\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%APP_DIR%\venv\Scripts\python.exe"
)

if not defined PYTHON_EXE (
    echo [ERROR] Python not found! Install Python 3.8+ and add it to PATH.
    pause
    exit /b 1
)

if not exist "%APP_DIR%\nssm.exe" (
    echo [ERROR] nssm.exe not found in %APP_DIR%
    echo Download from: https://nssm.cc/download
    pause
    exit /b 1
)

echo [INFO] Python: %PYTHON_EXE%
echo [INFO] App Directory: %APP_DIR%
echo.

:: Stop and remove the old service (if it existed)
"%APP_DIR%\nssm.exe" stop RingScheduler 2>nul
"%APP_DIR%\nssm.exe" remove RingScheduler confirm 2>nul

:: Install the service
"%APP_DIR%\nssm.exe" install RingScheduler "%PYTHON_EXE%"
"%APP_DIR%\nssm.exe" set RingScheduler AppParameters "%APP_DIR%\app.py"
"%APP_DIR%\nssm.exe" set RingScheduler AppDirectory "%APP_DIR%"
"%APP_DIR%\nssm.exe" set RingScheduler DisplayName "RingScheduler - School Bells"
"%APP_DIR%\nssm.exe" set RingScheduler Description "Automatic school bell scheduler system"
"%APP_DIR%\nssm.exe" set RingScheduler Start SERVICE_AUTO_START
"%APP_DIR%\nssm.exe" set RingScheduler AppStdout "%APP_DIR%\logs\service_stdout.log"
"%APP_DIR%\nssm.exe" set RingScheduler AppStderr "%APP_DIR%\logs\service_stderr.log"
"%APP_DIR%\nssm.exe" set RingScheduler AppRotateFiles 1
"%APP_DIR%\nssm.exe" set RingScheduler AppRotateBytes 5000000

:: Create logs folder
mkdir "%APP_DIR%\logs" 2>nul

:: Start the service
"%APP_DIR%\nssm.exe" start RingScheduler

echo.
echo ========================================
echo  [OK] RingScheduler service installed!
echo  Interface: http://localhost:5000
echo  Management: services.msc
echo ========================================
pause
