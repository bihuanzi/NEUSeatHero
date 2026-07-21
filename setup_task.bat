@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   pram_lifecontroler 计划任务配置
echo ============================================
echo.
echo   [1] MOOC作业检测 - 每2小时运行一次
echo   [2] NEU选位监控 - 开机自启动
echo   [3] 全部安装
echo   [4] 查看已安装任务
echo   [5] 卸载所有任务
echo   [0] 退出
echo.
set /p choice="  选择: "

set "PYTHON=C:\Users\27840\AppData\Local\Python\pythoncore-3.14-64\python.exe"
set "DIR=%~dp0"

if "%choice%"=="1" goto :install_mooc
if "%choice%"=="2" goto :install_seat
if "%choice%"=="3" goto :install_all
if "%choice%"=="4" goto :list_tasks
if "%choice%"=="5" goto :uninstall
if "%choice%"=="0" goto :exit
goto :exit

:install_mooc
echo.
echo [安装] MOOC作业检测（每2小时）
schtasks /create /tn "pram_MOOC检测" /tr "\"%PYTHON%\" \"%DIR%webtask.py\"" /sc hourly /mo 2 /f
if %errorlevel%==0 (echo [OK] MOOC检测任务已创建) else (echo [错误] 创建失败，请以管理员身份运行)
goto :end

:install_seat
echo.
echo [安装] NEU选位监控（开机启动）
schtasks /create /tn "pram_选位监控" /tr "\"%PYTHON%\" \"%DIR%seathehero.py\"" /sc onstart /f
if %errorlevel%==0 (echo [OK] 选位监控任务已创建) else (echo [错误] 创建失败，请以管理员身份运行)
goto :end

:install_all
call :install_mooc
call :install_seat
goto :end

:list_tasks
echo.
schtasks /query /tn "pram_*" 2>nul
if %errorlevel% neq 0 echo   未找到 pram_ 相关任务
goto :end

:uninstall
echo.
schtasks /delete /tn "pram_MOOC检测" /f 2>nul
schtasks /delete /tn "pram_选位监控" /f 2>nul
echo [OK] 已卸载所有任务
goto :end

:end
echo.
pause
exit

:exit
exit
