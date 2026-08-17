@echo off
REM Run script for Windows

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the application
python -m app.main

pause
