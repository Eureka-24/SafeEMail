@echo off
chcp 65001 >nul
title SafeEmail Launcher

REM === 项目根目录 ===
set ROOT_DIR=%~dp0..
cd /d "%ROOT_DIR%"

echo ============================================================
echo   SafeEmail - 启动全部服务（每个服务独立终端）
echo ============================================================

REM === 1. 后端服务器 ===
echo [1/6] 启动 Alpha 后端 (127.0.0.1:8001)...
start "Alpha Backend" cmd /k "cd /d %ROOT_DIR% && python server/main.py config/alpha.yaml"

echo [2/6] 启动 Beta 后端 (127.0.0.1:8002)...
start "Beta Backend" cmd /k "cd /d %ROOT_DIR% && python server/main.py config/beta.yaml"

REM 等待后端就绪
timeout /t 2 /nobreak >nul

REM === 2. WebSocket 网关 ===
echo [3/6] 启动 Alpha WS 网关 (ws://127.0.0.1:3001)...
start "Alpha WS Gateway" cmd /k "cd /d %ROOT_DIR% && python server/ws_gateway.py config/alpha.yaml"

echo [4/6] 启动 Beta WS 网关 (ws://127.0.0.1:3002)...
start "Beta WS Gateway" cmd /k "cd /d %ROOT_DIR% && python server/ws_gateway.py config/beta.yaml"

REM === 3. 前端开发服务器 ===
echo [5/6] 启动 Alpha 前端 (http://localhost:5173)...
start "Alpha Frontend" cmd /k "cd /d %ROOT_DIR%\web && npx vite --mode alpha"

echo [6/6] 启动 Beta 前端 (http://localhost:5174)...
start "Beta Frontend" cmd /k "cd /d %ROOT_DIR%\web && npx vite --mode beta --port 5174"

echo.
echo ============================================================
echo   全部 6 个服务已在独立终端中启动
echo ============================================================
echo.
echo   后端:
echo     Alpha  -^> 127.0.0.1:8001
echo     Beta   -^> 127.0.0.1:8002
echo   WS 网关:
echo     Alpha  -^> ws://127.0.0.1:3001
echo     Beta   -^> ws://127.0.0.1:3002
echo   前端:
echo     Alpha  -^> http://localhost:5173
echo     Beta   -^> http://localhost:5174
echo.
echo   关闭方式: 逐个关闭各终端窗口, 或运行 stop_all.bat
echo ============================================================
pause
