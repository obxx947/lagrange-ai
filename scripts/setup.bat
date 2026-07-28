@echo off
REM ============================================================
REM 拉格朗日智能体 - Windows 环境配置脚本
REM 检查环境、安装依赖、初始化数据库
REM ============================================================
setlocal enabledelayedexpansion

set "APP_NAME=拉格朗日智能体"
set "APP_DIR=%~dp0.."
set "LOG_DIR=%APP_DIR%\logs"
set "PYTHON_BIN=python"
set "PIP_BIN=pip"
set "PORT=3000"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\setup_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log"
set "LOG_FILE=%LOG_FILE: =0%"

echo ============================================================
echo   %APP_NAME% - Windows 环境配置
echo   日志: %LOG_FILE%
echo ============================================================
echo.

REM ---- 1. Python环境检查 ----
echo [1/5] 检查Python环境...
%PYTHON_BIN% --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python！请安装Python 3.11+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('%PYTHON_BIN% --version 2^>^&1') do echo    Python版本: %%v

REM ---- 2. pip检查 ----
echo [2/5] 检查pip...
%PIP_BIN% --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到pip！请重新安装Python并勾选"Add to PATH"
    pause
    exit /b 1
)
echo    pip就绪

REM ---- 3. 创建虚拟环境 ----
echo [3/5] 创建虚拟环境...
if not exist "%APP_DIR%\.venv" (
    %PYTHON_BIN% -m venv "%APP_DIR%\.venv"
    echo    虚拟环境已创建
) else (
    echo    虚拟环境已存在
)

REM ---- 4. 安装依赖 ----
echo [4/5] 安装Python依赖...
call "%APP_DIR%\.venv\Scripts\activate.bat" 2>nul
%PIP_BIN% install --upgrade pip --quiet
%PIP_BIN% install -r "%APP_DIR%\requirements.txt" --quiet
if errorlevel 1 (
    echo [错误] 依赖安装失败！请检查网络连接
    pause
    exit /b 1
)
echo    依赖安装完成

REM ---- 5. 数据库初始化 ----
echo [5/5] 初始化数据库...
if exist "%APP_DIR%\lagrange.db" (
    echo    数据库已存在，执行备份...
    if not exist "%APP_DIR%\db_backup" mkdir "%APP_DIR%\db_backup"
    copy "%APP_DIR%\lagrange.db" "%APP_DIR%\db_backup\lagrange_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%.db.bak" >nul 2>&1
)

if exist "%APP_DIR%\db\schema.sql" (
    echo    执行SQL Schema...
    sqlite3 "%APP_DIR%\lagrange.db" < "%APP_DIR%\db\schema.sql" 2>nul || echo     (SQLite导入跳过-可能未安装sqlite3)
)

REM ---- 创建必要目录 ----
if not exist "%APP_DIR%\chroma_db" mkdir "%APP_DIR%\chroma_db"
if not exist "%APP_DIR%\db_backup" mkdir "%APP_DIR%\db_backup"
if not exist "%APP_DIR%\logs" mkdir "%APP_DIR%\logs"

echo.
echo ============================================================
echo   ✅ %APP_NAME% 环境配置完成！
echo ============================================================
echo.
echo 启动方式:
echo   1. 激活虚拟环境: .venv\Scripts\activate
echo   2. 启动服务:     python main.py
echo   3. 打开浏览器:   http://localhost:%PORT%
echo.
echo 管理后台: http://localhost:%PORT% (仅本地访问)
echo API文档:  http://localhost:%PORT%/docs
echo.
pause
endlocal
