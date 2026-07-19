#!/bin/bash
# ============================================================
# 拉格朗日AI — Shell 管理脚本
# 适用于 WSL / Git Bash / Cygwin 环境
# 用法: bash manage.sh [start|stop|status|backup|cleanup|rebuild]
# ============================================================

set -e

PYTHON="D:/Python312/python.exe"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=3000
BASE_URL="http://127.0.0.1:${PORT}"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

banner() {
    echo -e "${CYAN}============================================================${NC}"
    echo -e "${YELLOW}   《无尽的拉格朗日》AI 战术推演中心 — Shell管理${NC}"
    echo -e "${CYAN}============================================================${NC}"
}

check_python() {
    if [ ! -f "$PYTHON" ]; then
        echo -e "${RED}[错误] Python未找到: $PYTHON${NC}"
        exit 1
    fi
}

check_server() {
    if curl -s "${BASE_URL}/health" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

cmd_start() {
    echo -e "${GREEN}[启动] 正在启动服务...${NC}"
    check_python
    cd "$PROJECT_DIR"
    "$PYTHON" main.py &
    sleep 3
    if check_server; then
        echo -e "${GREEN}[成功] 服务已启动: ${BASE_URL}${NC}"
    else
        echo -e "${RED}[失败] 服务未能启动${NC}"
    fi
}

cmd_stop() {
    echo -e "${YELLOW}[停止] 正在停止服务...${NC}"
    taskkill //F //IM python.exe 2>/dev/null || true
    echo -e "${GREEN}[完成] 服务已停止${NC}"
}

cmd_status() {
    if check_server; then
        echo -e "${GREEN}[运行中] ${BASE_URL}${NC}"
        SHIPS=$(curl -s "${BASE_URL}/api/ships" | grep -o '"count":[0-9]*' | cut -d: -f2)
        echo -e "  舰船数据: ${SHIPS:-?} 艘"
        
        # 获取内网IP
        IP=$(ipconfig 2>/dev/null | grep -o '192\.168\.[0-9.]*' | head -1)
        if [ -n "$IP" ]; then
            echo -e "  局域网:   http://${IP}:${PORT}"
        fi
    else
        echo -e "${RED}[已停止]${NC}"
    fi
    
    # 数据库大小
    if [ -f "$PROJECT_DIR/lagrange.db" ]; then
        SIZE=$(du -h "$PROJECT_DIR/lagrange.db" | cut -f1)
        echo -e "  数据库:   lagrange.db (${SIZE})"
    fi
    
    # 备份数量
    BACKUPS=$(find "$PROJECT_DIR/db_backup" -name "*.db" 2>/dev/null | wc -l)
    echo -e "  备份:     ${BACKUPS} 个"
}

cmd_backup() {
    echo -e "${CYAN}[备份] 正在备份数据库...${NC}"
    check_python
    cd "$PROJECT_DIR"
    "$PYTHON" -c "from database import backup_database; print(backup_database())"
    echo -e "${GREEN}[完成]${NC}"
}

cmd_cleanup() {
    echo -e "${CYAN}[清理] 清理过期数据...${NC}"
    check_python
    cd "$PROJECT_DIR"
    "$PYTHON" -c "from database import cleanup_expired_data; print(cleanup_expired_data())"
    echo -e "${GREEN}[完成]${NC}"
}

cmd_rebuild() {
    echo -e "${CYAN}[重建] 重建向量索引...${NC}"
    if check_server; then
        curl -s -X POST "${BASE_URL}/api/rebuild-index"
    else
        check_python
        cd "$PROJECT_DIR"
        "$PYTHON" -c "from rag_service import build_vector_index; print(build_vector_index())"
    fi
    echo -e "${GREEN}[完成]${NC}"
}

cmd_restart() {
    cmd_stop
    sleep 2
    cmd_start
}

cmd_test() {
    echo -e "${CYAN}[测试] 运行API测试...${NC}"
    check_python
    cd "$PROJECT_DIR"
    "$PYTHON" test_api.py
}

# ============= 主逻辑 =============
banner

case "${1:-status}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    backup)  cmd_backup ;;
    cleanup) cmd_cleanup ;;
    rebuild) cmd_rebuild ;;
    test)    cmd_test ;;
    *)
        echo "用法: bash manage.sh [start|stop|restart|status|backup|cleanup|rebuild|test]"
        ;;
esac
