@echo off
REM Run FB comment web dashboard

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo Opening dashboard at http://127.0.0.1:5000
python run_web.py %*

pause
