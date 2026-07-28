#!/usr/bin/env bash
# ============================================================
# 拉格朗日智能体 - 部署脚本
# 完整的部署流程：环境检查 → 依赖安装 → 数据库初始化 → 启动服务
# ============================================================

set -euo pipefail
IFS=$'\n\t'

# ---- 配置变量 ----
APP_NAME="拉格朗日智能体"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${APP_DIR}/logs"
LOG_FILE="${LOG_DIR}/deploy_$(date +%Y%m%d_%H%M%S).log"
BACKUP_DIR="${APP_DIR}/db_backup"
VENV_DIR="${APP_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PIP_BIN="${PIP_BIN:-pip3}"
PORT="${PORT:-3000}"
HOST="${HOST:-0.0.0.0}"
MAX_RETRIES=5
HEALTH_CHECK_URL="http://localhost:${PORT}/health"

# ---- 颜色输出 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---- 日志函数 ----
log() {
    local level="$1"; shift
    local color=""
    case "$level" in
        INFO)  color="$GREEN" ;;
        WARN)  color="$YELLOW" ;;
        ERROR) color="$RED" ;;
        DEBUG) color="$BLUE" ;;
    esac
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [${level}] $*"
    echo -e "${color}${msg}${NC}" | tee -a "$LOG_FILE"
}

# ---- 错误处理 ----
handle_error() {
    local exit_code=$?
    log ERROR "脚本在第 ${1} 行失败，退出码: ${exit_code}"
    log ERROR "执行失败，请检查日志: ${LOG_FILE}"
    exit "$exit_code"
}
trap 'handle_error ${LINENO}' ERR

# ---- 环境检查 ----
check_environment() {
    log INFO "===== 环境检查 ====="

    # Python版本
    if ! command -v "$PYTHON_BIN" &>/dev/null; then
        log ERROR "未找到Python。请安装Python 3.11+"
        exit 1
    fi
    local py_version=$("$PYTHON_BIN" --version 2>&1)
    log INFO "Python版本: ${py_version}"

    # pip
    if ! command -v "$PIP_BIN" &>/dev/null; then
        log ERROR "未找到pip"
        exit 1
    fi

    # 磁盘空间（至少500MB）
    local avail_space=$(df -m "$APP_DIR" | tail -1 | awk '{print $4}')
    if [[ $avail_space -lt 500 ]]; then
        log WARN "可用磁盘空间不足500MB (当前: ${avail_space}MB)"
    else
        log INFO "可用磁盘空间: ${avail_space}MB"
    fi

    # 内存（至少512MB）
    local total_mem=$(free -m | awk '/Mem:/{print $2}')
    if [[ $total_mem -lt 512 ]]; then
        log WARN "系统内存不足512MB (当前: ${total_mem}MB)"
    else
        log INFO "系统内存: ${total_mem}MB"
    fi

    # 创建目录
    mkdir -p "$LOG_DIR" "$BACKUP_DIR" "${APP_DIR}/chroma_db"
    log INFO "环境检查通过"
}

# ---- 依赖安装 ----
install_dependencies() {
    log INFO "===== 安装依赖 ====="

    # 虚拟环境
    if [[ ! -d "$VENV_DIR" ]]; then
        log INFO "创建虚拟环境: ${VENV_DIR}"
        "$PYTHON_BIN" -m venv "$VENV_DIR"
    fi

    # 激活虚拟环境
    source "${VENV_DIR}/bin/activate" 2>/dev/null || source "${VENV_DIR}/Scripts/activate" 2>/dev/null

    # 升级pip
    "$PIP_BIN" install --upgrade pip setuptools wheel --quiet

    # 安装项目依赖
    if [[ -f "${APP_DIR}/requirements.txt" ]]; then
        log INFO "安装Python依赖..."
        "$PIP_BIN" install -r "${APP_DIR}/requirements.txt" --quiet
        log INFO "依赖安装完成"
    else
        log ERROR "未找到 requirements.txt"
        exit 1
    fi
}

# ---- 数据库初始化 ----
init_database() {
    log INFO "===== 数据库初始化 ====="

    # 备份现有数据库
    if [[ -f "${APP_DIR}/lagrange.db" ]]; then
        local backup_name="lagrange_$(date +%Y%m%d_%H%M%S).db.bak"
        cp "${APP_DIR}/lagrange.db" "${BACKUP_DIR}/${backup_name}"
        log INFO "已备份数据库: ${backup_name}"
    fi

    # 运行数据库初始化
    if [[ -f "${APP_DIR}/db/schema.sql" ]]; then
        log INFO "执行SQL Schema..."
        sqlite3 "${APP_DIR}/lagrange.db" < "${APP_DIR}/db/schema.sql" 2>/dev/null || true
        log INFO "数据库初始化完成"
    fi
}

# ---- 启动服务 ----
start_service() {
    log INFO "===== 启动服务 ====="

    source "${VENV_DIR}/bin/activate" 2>/dev/null || source "${VENV_DIR}/Scripts/activate" 2>/dev/null

    cd "$APP_DIR"

    # 后台启动
    nohup "$PYTHON_BIN" main.py > "${LOG_DIR}/server.log" 2>&1 &
    local pid=$!
    echo "$pid" > "${APP_DIR}/.pid"
    log INFO "服务已启动 (PID: ${pid})"

    # 健康检查
    log INFO "等待服务就绪..."
    local retry=0
    while [[ $retry -lt $MAX_RETRIES ]]; do
        sleep 2
        if curl -sf "$HEALTH_CHECK_URL" >/dev/null 2>&1; then
            log INFO "✅ 服务就绪！访问: http://localhost:${PORT}"
            return 0
        fi
        ((retry++))
        log DEBUG "重试 ${retry}/${MAX_RETRIES}..."
    done

    log ERROR "服务启动超时！请检查日志: ${LOG_DIR}/server.log"
    return 1
}

# ---- 停止服务 ----
stop_service() {
    log INFO "===== 停止服务 ====="
    if [[ -f "${APP_DIR}/.pid" ]]; then
        local pid=$(cat "${APP_DIR}/.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            sleep 2
            kill -9 "$pid" 2>/dev/null || true
            log INFO "服务已停止 (PID: ${pid})"
        fi
        rm -f "${APP_DIR}/.pid"
    else
        log WARN "未找到PID文件"
    fi
}

# ---- 状态查询 ----
show_status() {
    log INFO "===== 服务状态 ====="
    if [[ -f "${APP_DIR}/.pid" ]]; then
        local pid=$(cat "${APP_DIR}/.pid")
        if kill -0 "$pid" 2>/dev/null; then
            log INFO "✅ 服务运行中 (PID: ${pid})"
            # 尝试健康检查
            if curl -sf "$HEALTH_CHECK_URL" >/dev/null 2>&1; then
                local response=$(curl -s "$HEALTH_CHECK_URL")
                log INFO "健康检查: ${response}"
            fi
        else
            log WARN "❌ PID文件存在但进程已停止"
        fi
    else
        log INFO "❌ 服务未运行"
    fi
}

# ---- 完整备份 ----
full_backup() {
    log INFO "===== 完整备份 ====="
    local backup_date=$(date +%Y%m%d_%H%M%S)
    local backup_file="${BACKUP_DIR}/full_backup_${backup_date}.tar.gz"

    tar -czf "$backup_file" \
        -C "$APP_DIR" \
        lagrange.db chroma_db/ lagrange_docs/ \
        --exclude='*.pyc' --exclude='__pycache__' \
        2>/dev/null || true

    if [[ -f "$backup_file" ]]; then
        local size=$(du -h "$backup_file" | cut -f1)
        log INFO "备份完成: ${backup_file} (${size})"
    else
        log ERROR "备份失败"
    fi
}

# ---- 主入口 ----
main() {
    mkdir -p "$LOG_DIR"

    case "${1:-deploy}" in
        deploy)
            check_environment
            install_dependencies
            init_database
            start_service
            ;;
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            stop_service
            sleep 2
            start_service
            ;;
        status)
            show_status
            ;;
        backup)
            full_backup
            ;;
        *)
            echo "用法: $0 {deploy|start|stop|restart|status|backup}"
            echo ""
            echo "  deploy  - 完整部署（默认）"
            echo "  start   - 启动服务"
            echo "  stop    - 停止服务"
            echo "  restart - 重启服务"
            echo "  status  - 查看状态"
            echo "  backup  - 完整备份"
            exit 1
            ;;
    esac
}

main "$@"
