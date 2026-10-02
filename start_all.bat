@echo off
REM Start everything: monitor (collects comments) + web dashboard (view them)
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo Starting FB Monitor (collects new comments)...
start "FB Monitor" cmd /k python run.py

timeout /t 5 /nobreak >nul

echo Starting Web Dashboard at http://127.0.0.1:5000 ...
start "FB Web Dashboard" cmd /k python run_web.py --port 5000

echo.
echo Done. Two windows opened:
echo   - FB Monitor       (browser automation, keep open)
echo   - FB Web Dashboard (open http://127.0.0.1:5000)
