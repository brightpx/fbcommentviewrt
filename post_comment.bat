@echo off
REM Post a comment to Facebook
REM Usage: post_comment.bat "Your comment message"

if "%~1"=="" (
    echo Usage: post_comment.bat "Your comment message"
    echo.
    echo Example:
    echo   post_comment.bat "Hello, this is a test!"
    exit /b 1
)

python post_comment.py %*
