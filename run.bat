@echo off
REM Run script for Windows (optimized owner-detector)

REM Activate virtual environment if exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the application (passes through extra args, e.g. --post-test)
python run.py %*

pause
