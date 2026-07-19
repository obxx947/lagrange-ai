# -*- coding: utf-8 -*-
"""
战斗日志分析器
-------------
解析和分析战斗模拟日志，提供统计报告。
支持从文件读取或从API获取日志数据。
"""

import re
from collections import Counter, defaultdict
from typing import List, Dict, Tuple
from dataclasses import dataclass, field


@dataclass
class KillEvent:
    time: float
    attacker: str
    target: str

@dataclass
class SystemDamageEvent:
    time: float
    ship: str
    system: str

@dataclass
class BattleReport:
    duration: float = 0.0
    winner: str = ""
    total_logs: int = 0
    ally_kills: int = 0
    enemy_kills: int = 0
    ally_losses: int = 0
    enemy_losses: int = 0
    kill_events: List[KillEvent] = field(default_factory=list)
    system_events: List[SystemDamageEvent] = field(default_factory=list)
    top_killer: str = ""
    most_killed: str = ""
    avg_kill_time: float = 0.0
    first_blood_time: float = 0.0
    first_blood_ship: str = ""


def parse_battle_logs(logs: List[str]) -> BattleReport:
    """
    解析战斗日志列表，生成结构化报告
    
    日志格式示例：
    "[12.5s] 光追级 击毁了 爱奥级"
    "[8.3s] 永恒风暴级 的 主武器系统 被破坏！"
    "🏆 敌方舰队全灭！己方胜利！(耗时45.2s)"
    """
    report = BattleReport()
    report.total_logs = len(logs)
    
    kill_pattern = re.compile(r'\[([\d.]+)s\]\s*(.+?)\s*击毁[了]?\s*(.+)')
    system_pattern = re.compile(r'\[([\d.]+)s\]\s*(.+?)\s*的\s*(\S+系统)\s*被破坏')
    win_pattern = re.compile(r'(🏆|💀).*(己方|敌方)')
    time_pattern = re.compile(r'耗时\s*([\d.]+)s')
    
    kill_times = []
    killer_counts = Counter()
    killed_counts = Counter()
    
    for log in logs:
        # 击杀事件
        km = kill_pattern.search(log)
        if km:
            t, attacker, target = float(km.group(1)), km.group(2).strip(), km.group(3).strip()
            report.kill_events.append(KillEvent(t, attacker, target))
            killer_counts[attacker] += 1
            killed_counts[target] += 1
            kill_times.append(t)
            
            if "己方" in attacker or "ally" in attacker.lower():
                report.ally_kills += 1
            else:
                report.enemy_kills += 1
        
        # 系统破坏事件
        sm = system_pattern.search(log)
        if sm:
            t, ship, sys_name = float(sm.group(1)), sm.group(2).strip(), sm.group(3)
            report.system_events.append(SystemDamageEvent(t, ship, sys_name))
        
        # 胜负判定
        wm = win_pattern.search(log)
        if wm:
            tm = time_pattern.search(log)
            if tm:
                report.duration = float(tm.group(1))
            if "己方" in wm.group(2):
                report.winner = "ally"
            else:
                report.winner = "enemy"
    
    # 统计
    report.ally_losses = report.enemy_kills
    report.enemy_losses = report.ally_kills
    
    if killer_counts:
        report.top_killer = killer_counts.most_common(1)[0][0]
    if killed_counts:
        report.most_killed = killed_counts.most_common(1)[0][0]
    if kill_times:
        report.first_blood_time = min(kill_times)
        report.avg_kill_time = sum(kill_times) / len(kill_times)
        
        # 一血
        for ke in report.kill_events:
            if ke.time == report.first_blood_time:
                report.first_blood_ship = ke.target
                break
    
    return report


def format_report(report: BattleReport) -> str:
    """格式化战斗报告为可读文本"""
    lines = []
    lines.append("=" * 50)
    lines.append("  📊 战斗分析报告")
    lines.append("=" * 50)
    lines.append(f"  战斗时长 : {report.duration:.1f}s")
    lines.append(f"  胜负结果 : {'己方胜利 🏆' if report.winner=='ally' else '敌方胜利 💀'}")
    lines.append(f"  总日志数 : {report.total_logs}")
    lines.append("-" * 50)
    lines.append(f"  己方击杀 : {report.ally_kills} 艘")
    lines.append(f"  敌方击杀 : {report.enemy_kills} 艘")
    lines.append(f"  己方损失 : {report.ally_losses} 艘")
    lines.append(f"  敌方损失 : {report.enemy_losses} 艘")
    lines.append("-" * 50)
    
    if report.top_killer:
        lines.append(f"  MVP舰船 : {report.top_killer}")
    if report.most_killed:
        lines.append(f"  最多被杀 : {report.most_killed}")
    if report.first_blood_time > 0:
        lines.append(f"  一血时间 : {report.first_blood_time:.1f}s ({report.first_blood_ship})")
    if report.avg_kill_time > 0:
        lines.append(f"  平均击杀间隔 : {report.avg_kill_time:.1f}s")
    
    if report.system_events:
        lines.append("-" * 50)
        lines.append(f"  系统破坏 : {len(report.system_events)} 次")
        sys_counts = Counter(e.system for e in report.system_events)
        for sys_name, count in sys_counts.most_common():
            lines.append(f"    - {sys_name}: {count}次")
    
    lines.append("=" * 50)
    return "\n".join(lines)


def analyze_from_file(filepath: str) -> BattleReport:
    """从文件读取日志并分析"""
    with open(filepath, "r", encoding="utf-8") as f:
        logs = [line.strip() for line in f if line.strip()]
    return parse_battle_logs(logs)


# ==================== 测试 ====================

if __name__ == "__main__":
    # 模拟战斗日志
    sample_logs = [
        "⚔ 战斗开始！己方 8艘 vs 敌方 6艘",
        "[3.2s] 光追级 击毁了 爱奥级",
        "[5.8s] 卡利斯托级 击毁了 阋神星重炮级",
        "[8.3s] 永恒风暴级 的 主武器系统 被破坏！",
        "[12.1s] 光追级 击毁了 卡利莱恩级",
        "[15.6s] CV3000级 的 机库系统 被破坏！",
        "[18.9s] 君士坦丁大帝级 击毁了 刺水母级",
        "[22.4s] 光追级 击毁了 澄海级",
        "[25.1s] 普卢托斯之盾级 的 指挥系统 被破坏！",
        "[28.7s] 永恒风暴级 击毁了 枪骑兵级",
        "🏆 敌方舰队全灭！己方胜利！(耗时28.7s)",
    ]
    
    report = parse_battle_logs(sample_logs)
    print(format_report(report))
