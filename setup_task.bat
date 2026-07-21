@echo off
chcp 65001 >nul
echo ============================================
echo   pram_lifecontroler 计划任务安装
echo   右键以管理员身份运行此脚本
echo ============================================
echo.

set "PYTHON=C:\Users\27840\AppData\Local\Python\pythoncore-3.14-64\python.exe"
set "DIR=%~dp0"

echo [安装] 开机自启动 run.py
schtasks /create /tn "pram_lifecontroler" /tr "\"%PYTHON%\" \"%DIR%run.py\"" /sc onstart /f
if %errorlevel%==0 (
    echo [OK] 任务已创建！
    echo.
    echo   下次开机将自动运行 pram_lifecontroler
    echo   首次运行会进入设置向导
    echo   之后每次开机自动执行已启用的功能
    echo.
    echo   更改配置: python run.py --config
    echo   卸载任务: schtasks /delete /tn pram_lifecontroler /f
) else (
    echo [错误] 请以管理员身份运行！
)
echo.
pause

