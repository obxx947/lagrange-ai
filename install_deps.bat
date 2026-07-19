@echo off
chcp 65001 >nul
title 拉格朗日AI — 一键安装依赖

echo ============================================================
echo   拉格朗日AI 战术推演中心 — 一键安装脚本
echo ============================================================
echo.

:: 检查 Python
set "PYTHON=D:\Python312\python.exe"
if not exist "%PYTHON%" (
    echo [错误] 未找到 Python: %PYTHON%
    echo   请确保 Python 3.12 已安装到 D:\Python312
    echo.
    pause
    exit /b 1
)

echo [1/4] 检查 Python...
"%PYTHON%" --version
echo.

echo [2/4] 升级 pip...
"%PYTHON%" -m pip install --upgrade pip --no-cache-dir >nul 2>&1
echo   完成
echo.

echo [3/4] 安装依赖包（约需2-5分钟）...
"%PYTHON%" -m pip install -r requirements.txt --no-cache-dir
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败！
    echo   请尝试手动执行: "%PYTHON%" -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo   完成
echo.

echo [4/4] 解析舰船数据库...
if exist "lagrange_docs\ship_database.json" (
    echo   舰船数据库已存在，跳过解析
) else (
    echo   正在从 lglrmax.html 解析169艘舰船...
    node parse_ships.js lagrange_docs/lglrmax.html lagrange_docs/ship_database.json
    if %errorlevel% neq 0 (
        echo   [警告] 舰船解析失败，将使用内置精简数据库
    ) else (
        echo   解析完成
    )
)
echo.

echo ============================================================
echo   安装完成！
echo   运行「启动服务.bat」启动服务
echo   浏览器访问: http://127.0.0.1:3000
echo ============================================================
echo.
pause
