@echo off
chcp 65001 >nul
title SafeEmail - 停止所有服务

echo ============================================================
echo   SafeEmail - 停止全部服务
echo ============================================================

echo 正在终止后端和网关进程 (python)...
for /f "tokens=2" %%i in ('wmic process where "commandline like '%%server/main.py%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /F /PID %%i >nul 2>&1
)
for /f "tokens=2" %%i in ('wmic process where "commandline like '%%ws_gateway.py%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /F /PID %%i >nul 2>&1
)

echo 正在终止前端进程 (node)...
for /f "tokens=2" %%i in ('wmic process where "commandline like '%%vite%%--mode%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /F /PID %%i >nul 2>&1
)

echo.
echo   全部服务已停止
echo ============================================================
pause
