@echo off
:: Set UTF-8 encoding for console
chcp 65001 >nul

echo ========================================
echo   RingScheduler - Application Startup
echo ========================================
cd /d "%~dp0"

:: Activate virtualenv if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

echo [OK] RingScheduler starting on http://localhost:5000
echo [!]  Press CTRL+C to stop
echo.
python app.py
pause