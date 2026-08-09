#!/bin/bash
# ============================================================
# 拉格朗日智能体 · 局域网一键部署（Git Bash）
# 自动启动：原版后端(AI对话/模拟器, 端口3000) + 静态版(端口3002)
# 手机/其他电脑 连接同一WiFi 即可访问
# 停止：按 Ctrl+C（两个服务会随脚本一起退出）
# ============================================================
set -e
cd "$(dirname "$0")" || exit 1

DESK="C:/Users/Administrator/Desktop"

# ---------- 1. 检测 Python ----------
if ! command -v python >/dev/null 2>&1; then
    echo "[错误] 未检测到 Python，请先安装 Python 3.9+"
    exit 1
fi

# ---------- 2. 获取本机局域网 IPv4（grep -a 强制按文本处理，兼容GBK输出） ----------
LAN_IP=$(ipconfig 2>/dev/null | grep -ai "IPv4" | head -1 | grep -aoE "[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" | head -1 | tr -d '\r\n')

echo "============================================================"
echo "  拉格朗日智能体 · 局域网一键部署"
echo "============================================================"

# ---------- 3. 防火墙放行（需要管理员，失败仅提示） ----------
netsh advfirewall firewall delete rule name="LagrangeAI-Port3000" >/dev/null 2>&1 || true
netsh advfirewall firewall delete rule name="LagrangeAI-Port3002" >/dev/null 2>&1 || true
netsh advfirewall firewall add rule name="LagrangeAI-Port3000" dir=in action=allow protocol=TCP localport=3000 >/dev/null 2>&1 || true
netsh advfirewall firewall add rule name="LagrangeAI-Port3002" dir=in action=allow protocol=TCP localport=3002 >/dev/null 2>&1 || true

# ---------- 4. 启动服务 ----------
echo "[1/3] 启动原版后端（FastAPI）端口 3000 ..."
(cd "$DESK/拉格朗日智能体" && python main.py) > /tmp/lagrange3000.log 2>&1 &
P1=$!

echo "[2/3] 启动静态版 端口 3002 ..."
(cd "$DESK/拉格朗日智能体3" && python -m http.server 3002 --bind 0.0.0.0) > /tmp/lagrange3002.log 2>&1 &
P2=$!

# 记录子进程 PID 以便退出时清理
PIDS="$P1 $P2"
trap 'echo; echo "正在停止服务..."; kill $PIDS 2>/dev/null || true; exit 0' INT TERM

echo "[3/3] 等待服务就绪..."
sleep 8

# ---------- 5. 打印访问地址 ----------
echo
echo "============================================================"
echo "  部署完成！访问地址："
echo
if [ -n "$LAN_IP" ]; then
    echo "  原版  (AI对话/战斗模拟器) : http://$LAN_IP:3000"
    echo "  静态版 (纯前端轻量版)     : http://$LAN_IP:3002"
    echo "  本机测试 (原版)           : http://127.0.0.1:3000"
else
    echo "  未能自动获取IP，请在命令行执行 ipconfig 查看"
    echo "  原版: http://你的IP:3000    静态版: http://你的IP:3002"
fi
echo
echo "  手机/其他电脑需与电脑连接同一 WiFi/局域网"
echo "  若访问不通：请以管理员身份运行 netsh 放行 TCP 3000/3002"
echo "============================================================"
echo
echo "  按 Ctrl+C 停止服务"
echo
wait
