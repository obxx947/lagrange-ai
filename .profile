# ============================================================
# 拉格朗日AI — Shell Profile 配置
# source ~/.profile 加载
# ============================================================

# 拉格朗日AI 环境
export LAGRANGE_HOME="$HOME/Desktop/拉格朗日智能体"
export LAGRANGE_API="http://127.0.0.1:3000"

# 添加到 PATH
if [ -d "$LAGRANGE_HOME" ]; then
    export PATH="$LAGRANGE_HOME:$PATH"
fi

# 快捷函数
lagrange() {
    case "${1:-status}" in
        start)   cd "$LAGRANGE_HOME" && python main.py & ;;
        stop)    taskkill //F //IM python.exe 2>/dev/null ;;
        status)  curl -s "$LAGRANGE_API/health" 2>/dev/null && echo "" || echo "❌ 服务未运行" ;;
        backup)  cd "$LAGRANGE_HOME" && python -c "from database import backup_database; print(backup_database())" ;;
        *)       echo "用法: lagrange [start|stop|status|backup]" ;;
    esac
}
