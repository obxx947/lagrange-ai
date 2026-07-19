# ============================================================
# PowerShell 管理脚本
# 用法：powershell -ExecutionPolicy Bypass -File manage.ps1 [命令]
# 命令：start | stop | restart | status | backup | cleanup | logs
# ============================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("start","stop","restart","status","backup","cleanup","logs","test","rebuild")]
    [string]$Command = "status"
)

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = "D:\Python312\python.exe"
$Port = 3000

function Write-Banner {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "   《无尽的拉格朗日》AI 战术推演中心 — 管理工具" -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Cyan
}

function Start-Server {
    Write-Host "[启动] 正在启动服务..." -ForegroundColor Green
    $proc = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*拉格朗日*" }
    if ($proc) {
        Write-Host "[警告] 服务已在运行中 (PID: $($proc.Id))" -ForegroundColor Yellow
        return
    }
    Start-Process -FilePath $PythonExe -ArgumentList "main.py" -WorkingDirectory $ProjectDir -WindowStyle Minimized
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:${Port}/health" -TimeoutSec 5
        Write-Host "[成功] 服务已启动！http://127.0.0.1:${Port}" -ForegroundColor Green
    } catch {
        Write-Host "[错误] 服务启动失败，请检查日志" -ForegroundColor Red
    }
}

function Stop-Server {
    Write-Host "[停止] 正在停止服务..." -ForegroundColor Yellow
    $procs = Get-Process python -ErrorAction SilentlyContinue
    $stopped = $false
    foreach ($p in $procs) {
        try {
            Stop-Process -Id $p.Id -Force
            $stopped = $true
        } catch {}
    }
    if ($stopped) {
        Write-Host "[成功] 服务已停止" -ForegroundColor Green
    } else {
        Write-Host "[提示] 未找到运行中的服务" -ForegroundColor Yellow
    }
}

function Show-Status {
    Write-Host ""
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:${Port}/health" -TimeoutSec 3
        Write-Host "  服务状态 : 运行中 ✅" -ForegroundColor Green
        Write-Host "  索引状态 : $($r.index_built)" -ForegroundColor Green
        
        $r2 = Invoke-RestMethod -Uri "http://127.0.0.1:${Port}/api/ships" -TimeoutSec 3
        Write-Host "  舰船数据 : $($r2.count) 艘" -ForegroundColor Green
        
        # 获取本机IP
        $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.PrefixOrigin -ne "WellKnown" } | Select-Object -First 1).IPAddress
        if ($ip) {
            Write-Host "  本机访问 : http://127.0.0.1:${Port}" -ForegroundColor Cyan
            Write-Host "  局域网   : http://${ip}:${Port}" -ForegroundColor Cyan
        }
    } catch {
        Write-Host "  服务状态 : 未运行 ❌" -ForegroundColor Red
    }
    Write-Host ""
    
    # 数据库统计
    $dbPath = Join-Path $ProjectDir "lagrange.db"
    if (Test-Path $dbPath) {
        $dbSize = (Get-Item $dbPath).Length / 1KB
        Write-Host "  数据库   : lagrange.db ($([math]::Round($dbSize,1)) KB)" -ForegroundColor Gray
    }
    
    # 备份统计
    $backupDir = Join-Path $ProjectDir "db_backup"
    if (Test-Path $backupDir) {
        $backupCount = (Get-ChildItem $backupDir -Filter "*.db" | Measure-Object).Count
        Write-Host "  备份文件 : ${backupCount} 个" -ForegroundColor Gray
    }
}

function Invoke-Backup {
    Write-Host "[备份] 正在备份数据库..." -ForegroundColor Cyan
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:${Port}/api/admin/backup" -Method Post `
            -Headers @{Authorization="Bearer PLACEHOLDER"} -TimeoutSec 10
        Write-Host "[成功] 备份完成" -ForegroundColor Green
    } catch {
        Write-Host "[提示] 请通过管理后台手动备份，或使用Python脚本" -ForegroundColor Yellow
        
        # 直接Python备份
        $result = & $PythonExe -c "from database import backup_database; print(backup_database())" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[成功] $result" -ForegroundColor Green
        }
    }
}

function Invoke-Cleanup {
    Write-Host "[清理] 正在清理过期数据..." -ForegroundColor Cyan
    $result = & $PythonExe -c "from database import cleanup_expired_data; print(cleanup_expired_data())" 2>&1
    Write-Host $result
}

function Invoke-Test {
    Write-Host "[测试] 运行API测试..." -ForegroundColor Cyan
    & $PythonExe test_api.py 2>&1
}

function Invoke-Rebuild {
    Write-Host "[重建] 重建向量索引..." -ForegroundColor Cyan
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:${Port}/api/rebuild-index" -Method Post -TimeoutSec 30
        Write-Host "[成功] $($r.message)" -ForegroundColor Green
    } catch {
        Write-Host "[错误] 重建失败" -ForegroundColor Red
    }
}

# ============= 主逻辑 =============
Write-Banner

switch ($Command) {
    "start"    { Start-Server }
    "stop"     { Stop-Server }
    "restart"  { Stop-Server; Start-Sleep 2; Start-Server }
    "status"   { Show-Status }
    "backup"   { Invoke-Backup }
    "cleanup"  { Invoke-Cleanup }
    "test"     { Invoke-Test }
    "rebuild"  { Invoke-Rebuild }
    "logs"     { 
        $logFile = Join-Path $ProjectDir "server.log"
        if (Test-Path $logFile) {
            Get-Content $logFile -Tail 50
        } else {
            Write-Host "[提示] 未找到日志文件" -ForegroundColor Yellow
        }
    }
}
