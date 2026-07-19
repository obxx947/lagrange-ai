# ============================================================
# 拉格朗日AI — Bash 配置
# 添加到 ~/.bashrc 或 source 此文件
# ============================================================

# 拉格朗日AI 函数
lagrange_start() {
    cd "$HOME/Desktop/拉格朗日智能体" || return
    python main.py &
    sleep 2
    curl -s http://127.0.0.1:3000/health
}

lagrange_stop() {
    taskkill //F //IM python.exe 2>/dev/null
    echo "服务已停止"
}

lagrange_status() {
    if curl -s http://127.0.0.1:3000/health > /dev/null 2>&1; then
        echo "✅ 服务运行中: http://127.0.0.1:3000"
        echo "🚀 舰船: $(curl -s http://127.0.0.1:3000/api/ships | grep -o '"count":[0-9]*' | cut -d: -f2) 艘"
    else
        echo "❌ 服务未运行"
    fi
}

lagrange_backup() {
    cd "$HOME/Desktop/拉格朗日智能体"
    python -c "from database import backup_database; print(backup_database())"
}

# 快捷别名
alias lg-start=lagrange_start
alias lg-stop=lagrange_stop
alias lg-status=lagrange_status
alias lg-backup=lagrange_backup

# 路径
export LAGRANGE_HOME="$HOME/Desktop/拉格朗日智能体"
export LAGRANGE_API="http://127.0.0.1:3000"
