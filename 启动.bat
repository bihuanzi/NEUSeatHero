@echo off
chcp 65001 >nul 2>&1
title Seat Grabber v1.0

:: ====== Configuration ======
:: QQ number (stored in qq.txt)
set /p QQ_USER=<"%~dp0qq.txt"
:: QQ Mail authorization code (get from: QQ Mail -> Settings -> Account -> SMTP)
set /p QQ_AUTH=<"%~dp0auth.txt"
:: Keyword to detect on the page
set KEYWORD=
:: ===========================

cd /d "%~dp0"

if "%QQ_USER%"=="" (
    echo [WARNING] QQ_USER not set. QQ notification disabled.
    echo Edit this .bat file to configure QQ_USER and KEYWORD.
    echo.
    PowerShell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
) else (
    PowerShell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" -QQUser "%QQ_USER%" -QQAuthCode "%QQ_AUTH%" -Keyword "%KEYWORD%"
)
pause
