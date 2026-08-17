@echo off
REM Run tests with various options

echo =====================================
echo Facebook Comment Monitor - Test Runner
echo =====================================
echo.

:menu
echo Select test option:
echo 1. Run all tests
echo 2. Run with coverage
echo 3. Run unit tests only
echo 4. Run integration tests only
echo 5. Run specific test file
echo 6. Run with pdb (debug on failure)
echo 7. Run failed tests only
echo 8. Exit
echo.

set /p choice="Enter choice (1-8): "

if "%choice%"=="1" goto all
if "%choice%"=="2" goto coverage
if "%choice%"=="3" goto unit
if "%choice%"=="4" goto integration
if "%choice%"=="5" goto specific
if "%choice%"=="6" goto debug
if "%choice%"=="7" goto failed
if "%choice%"=="8" goto end

echo Invalid choice. Please try again.
echo.
goto menu

:all
echo.
echo Running all tests...
pytest tests/ -v
goto done

:coverage
echo.
echo Running tests with coverage...
pytest tests/ --cov=app --cov-report=html --cov-report=term
echo.
echo Coverage report generated in htmlcov/index.html
goto done

:unit
echo.
echo Running unit tests only...
pytest tests/ -v -m unit
goto done

:integration
echo.
echo Running integration tests only...
pytest tests/ -v -m integration
goto done

:specific
echo.
set /p testfile="Enter test file (e.g., test_models.py): "
pytest tests/%testfile% -v
goto done

:debug
echo.
echo Running tests with pdb (will drop into debugger on failure)...
pytest tests/ -v --pdb
goto done

:failed
echo.
echo Running failed tests only...
pytest tests/ -v --lf
goto done

:done
echo.
echo =====================================
echo Tests completed!
echo =====================================
echo.
pause
goto menu

:end
echo.
echo Exiting...
