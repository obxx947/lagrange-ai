# ============================================================
# 拉格朗日AI — Zsh 配置
# 添加到 ~/.zshrc 或 source 此文件
# ============================================================

# 拉格朗日AI 项目别名
alias lagrange-start='cd ~/Desktop/拉格朗日智能体 && python main.py'
alias lagrange-stop='taskkill /F /IM python.exe 2>/dev/null'
alias lagrange-status='curl -s http://127.0.0.1:3000/health 2>/dev/null || echo "服务未运行"'
alias lagrange-backup='cd ~/Desktop/拉格朗日智能体 && python -c "from database import backup_database; print(backup_database())"'
alias lagrange-cleanup='cd ~/Desktop/拉格朗日智能体 && python -c "from database import cleanup_expired_data; print(cleanup_expired_data())"'

# 环境变量
export LAGRANGE_HOME="$HOME/Desktop/拉格朗日智能体"
export LAGRANGE_API="http://127.0.0.1:3000"
export PATH="$LAGRANGE_HOME:$PATH"

# 自动补全
_lagrange_commands() {
  local commands=("start" "stop" "status" "backup" "cleanup" "rebuild" "test")
  _describe 'command' commands
}
compdef _lagrange_commands lagrange-start lagrange-stop
