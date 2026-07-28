# ============================================================
# 拉格朗日智能体 - Windows PowerShell 启动脚本
# 完整的服务管理：启动/停止/重启/状态/备份
# ============================================================

param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "status", "backup", "deploy")]
    [string]$Action = "deploy"
)

$ErrorActionPreference = "Stop"
$APP_NAME = "拉格朗日智能体"
$APP_DIR = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$LOG_DIR = Join-Path $APP_DIR "logs"
$PID_FILE = Join-Path $APP_DIR ".pid"
$PORT = 3000
$HOST_ADDR = "0.0.0.0"
$PYTHON_BIN = "python"
$HEALTH_URL = "http://localhost:$PORT/health"

# 初始化日志目录
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}
$LOG_FILE = Join-Path $LOG_DIR "ps_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# ---- 日志函数 ----
function Write-Log {
    param([string]$Level, [string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $entry = "[$timestamp] [$Level] $Message"
    $color = @{ INFO = "Green"; WARN = "Yellow"; ERROR = "Red"; DEBUG = "Blue" }[$Level]
    Write-Host $entry -ForegroundColor $color
    Add-Content -Path $LOG_FILE -Value $entry
}

# ---- 错误处理 ----
function Handle-Error {
    param($Line)
    Write-Log "ERROR" "脚本在第 $Line 行失败"
    Write-Log "ERROR" "请检查日志: $LOG_FILE"
}

# ---- 环境检查 ----
function Test-Environment {
    Write-Log "INFO" "===== 环境检查 ====="

    try {
        $pyVersion = & $PYTHON_BIN --version 2>&1
        Write-Log "INFO" "Python版本: $pyVersion"
    } catch {
        Write-Log "ERROR" "未找到Python！请安装Python 3.11+"
        Write-Log "ERROR" "下载: https://www.python.org/downloads/"
        exit 1
    }

    try {
        $pipVersion = & pip --version 2>&1
        Write-Log "INFO" "pip就绪"
    } catch {
        Write-Log "ERROR" "未找到pip"
        exit 1
    }

    # 磁盘空间检查
    $drive = Get-PSDrive -Name (Split-Path $APP_DIR -Qualifier).TrimEnd(':')
    if ($drive.Free -lt 500MB) {
        Write-Log "WARN" "磁盘空间不足500MB (可用: $([math]::Round($drive.Free/1MB))MB)"
    } else {
        Write-Log "INFO" "磁盘空间充足: $([math]::Round($drive.Free/1MB))MB"
    }

    # 创建必要目录
    @("$APP_DIR\chroma_db", "$APP_DIR\db_backup", "$APP_DIR\logs") | ForEach-Object {
        if (-not (Test-Path $_)) {
            New-Item -ItemType Directory -Path $_ -Force | Out-Null
        }
    }

    Write-Log "INFO" "环境检查通过"
}

# ---- 启动服务 ----
function Start-Service {
    Write-Log "INFO" "===== 启动服务 ====="

    if (Test-Path $PID_FILE) {
        $oldPid = Get-Content $PID_FILE
        try {
            $proc = Get-Process -Id $oldPid -ErrorAction Stop
            Write-Log "WARN" "服务已在运行 (PID: $oldPid)"
            return
        } catch {
            Write-Log "INFO" "清除旧的PID文件"
            Remove-Item $PID_FILE -Force
        }
    }

    $argList = @(
        "-u", "main.py",
        "--host", $HOST_ADDR,
        "--port", $PORT
    )

    $process = Start-Process -FilePath $PYTHON_BIN `
        -ArgumentList $argList `
        -WorkingDirectory $APP_DIR `
        -NoNewWindow `
        -PassThru `
        -RedirectStandardOutput "$LOG_DIR\server_stdout.log" `
        -RedirectStandardError "$LOG_DIR\server_stderr.log"

    $process.Id | Out-File -FilePath $PID_FILE -NoNewline
    Write-Log "INFO" "服务已启动 (PID: $($process.Id))"

    # 等待健康检查
    Write-Log "INFO" "等待服务就绪..."
    $retry = 0
    while ($retry -lt 10) {
        Start-Sleep -Seconds 3
        try {
            $response = Invoke-WebRequest -Uri $HEALTH_URL -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                Write-Log "INFO" "✅ 服务就绪！http://localhost:$PORT"
                return
            }
        } catch {}
        $retry++
        Write-Log "DEBUG" "重试 $retry/10..."
    }
    Write-Log "ERROR" "服务启动超时！检查日志: $LOG_DIR\server_stderr.log"
}

# ---- 停止服务 ----
function Stop-Service {
    Write-Log "INFO" "===== 停止服务 ====="

    if (-not (Test-Path $PID_FILE)) {
        Write-Log "WARN" "未找到PID文件，服务可能未运行"
        return
    }

    $pid = Get-Content $PID_FILE
    try {
        $proc = Get-Process -Id $pid -ErrorAction Stop
        Write-Log "INFO" "停止进程 (PID: $pid)..."
        $proc.Kill()
        Start-Sleep -Seconds 2
        Write-Log "INFO" "服务已停止"
    } catch {
        Write-Log "INFO" "进程已不存在"
    }

    Remove-Item $PID_FILE -Force -ErrorAction SilentlyContinue
}

# ---- 状态查询 ----
function Show-Status {
    Write-Log "INFO" "===== 服务状态 ====="

    if (-not (Test-Path $PID_FILE)) {
        Write-Log "INFO" "❌ 服务未运行"
        return
    }

    $pid = Get-Content $PID_FILE
    try {
        $proc = Get-Process -Id $pid -ErrorAction Stop
        Write-Log "INFO" "✅ 服务运行中 (PID: $pid, 内存: $([math]::Round($proc.WorkingSet64/1MB))MB)"

        try {
            $response = Invoke-RestMethod -Uri $HEALTH_URL -TimeoutSec 5
            Write-Log "INFO" "健康检查: $($response | ConvertTo-Json -Compress)"
        } catch {
            Write-Log "WARN" "健康检查失败"
        }
    } catch {
        Write-Log "WARN" "PID文件存在但进程已停止"
    }
}

# ---- 备份 ----
function Backup-Data {
    Write-Log "INFO" "===== 数据备份 ====="
    $date = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupDir = Join-Path $APP_DIR "db_backup"
    $backupFile = Join-Path $backupDir "backup_$date.zip"

    if (-not (Test-Path $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    }

    $items = @()
    if (Test-Path "$APP_DIR\lagrange.db") { $items += "$APP_DIR\lagrange.db" }
    if (Test-Path "$APP_DIR\chroma_db") { $items += "$APP_DIR\chroma_db" }

    if ($items.Count -gt 0) {
        Compress-Archive -Path $items -DestinationPath $backupFile -Force
        $size = (Get-Item $backupFile).Length / 1KB
        Write-Log "INFO" "备份完成: $backupFile ($([math]::Round($size, 2))KB)"
    } else {
        Write-Log "WARN" "没有需要备份的数据"
    }
}

# ---- 主入口 ----
Write-Log "INFO" "========================================"
Write-Log "INFO" "  $APP_NAME - PowerShell 管理脚本"
Write-Log "INFO" "========================================"

try {
    switch ($Action) {
        "deploy" {
            Test-Environment
            Write-Log "INFO" "安装依赖..."
            & pip install -r "$APP_DIR\requirements.txt" --quiet
            Start-Service
        }
        "start"  { Start-Service }
        "stop"   { Stop-Service }
        "restart"{ Stop-Service; Start-Sleep 2; Start-Service }
        "status" { Show-Status }
        "backup" { Backup-Data }
    }
} catch {
    Write-Log "ERROR" "执行失败: $_"
    Write-Log "ERROR" "堆栈: $($_.ScriptStackTrace)"
    exit 1
}
