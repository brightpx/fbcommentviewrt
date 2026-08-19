@echo off
REM Run optimized Facebook Auto-Reply system
REM Uses owner-focused detection for 10x performance improvement

echo =====================================
echo Optimized Facebook Auto-Reply
echo =====================================
echo.

REM Activate virtual environment if it exists
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo Virtual environment activated
    echo.
)

REM Run the optimized version
python run_optimized.py

pause
