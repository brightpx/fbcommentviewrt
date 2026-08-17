@echo off
REM Installation script for Windows

echo ======================================
echo Facebook Comment Monitor - Installer
echo ======================================
echo.

REM Check Python version
echo Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.12+
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Python %PYTHON_VERSION% detected
echo.

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

if errorlevel 1 (
    echo Error: Failed to create virtual environment
    pause
    exit /b 1
)

echo Virtual environment created
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

echo Dependencies installed
echo.

REM Install Playwright browsers
echo Installing Playwright browsers...
playwright install chromium

if errorlevel 1 (
    echo Error: Failed to install Playwright browsers
    pause
    exit /b 1
)

echo Playwright browsers installed
echo.

REM Setup configuration
if not exist "config.yaml" (
    echo Creating configuration file...
    copy config.yaml.example config.yaml >nul
    echo Configuration file created
) else (
    echo Configuration file already exists
)
echo.

REM Create directories
echo Creating directories...
if not exist "session" mkdir session
if not exist "database" mkdir database
if not exist "logs" mkdir logs
echo Directories created
echo.

REM Success message
echo ======================================
echo Installation Complete!
echo ======================================
echo.
echo To start the application:
echo   1. Activate virtual environment: venv\Scripts\activate
echo   2. Run the application: python -m app.main
echo.
echo Or use the quick start script:
echo   run.bat
echo.
echo For more information, see README.md
echo.
pause
