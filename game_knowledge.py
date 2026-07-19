# -*- coding: utf-8 -*-
"""
游戏知识增强模块
---------------
从 战斗机制.txt 提取结构化游戏知识，注入 AI 系统提示词。
提供战斗公式、武器系统、舰船机制等权威游戏数据。
所有数据来源于 lagrange_docs 内玩家社区资料，禁止编造。
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
import config
from doc_loader import get_lagrange_docs_path, load_text_file

# ==================== 游戏知识库缓存 ====================

_game_knowledge_cache: Optional[Dict] = None


def get_game_knowledge() -> Dict:
    """
    获取完整的游戏知识库
    
    包含：
    - weapon_mechanics: 武器分类和攻击逻辑
    - combat_formulas: 战斗计算公式
    - ship_systems: 舰船系统机制
    - aircraft_mechanics: 舰载机机制
    - anti_air_mechanics: 防空机制
    - interception: 拦截机制
    - damage_types: 伤害类型详解
    - fleet_mechanics: 舰队机制
    """
    global _game_knowledge_cache
    if _game_knowledge_cache:
        return _game_knowledge_cache
    
    knowledge = _extract_game_knowledge()
    _game_knowledge_cache = knowledge
    return knowledge


def _extract_game_knowledge() -> Dict:
    """从战斗机制文档提取结构化游戏知识"""
    knowledge = {
        "weapon_types": {
            "轨道炮": "直射武器，实弹伤害，高单发伤害，慢攻速",
            "脉冲炮": "直射武器，能量伤害，中等攻速",
            "离子武器": "直射武器，能量伤害，对护盾有加成",
            "导弹": "投射武器，实弹伤害，可被拦截，追踪目标",
            "鱼雷": "投射武器，实弹伤害，高单发，可被拦截",
        },
        "damage_types": {
            "实弹伤害": "受目标物理装甲减免，护甲穿透不足时保底10%伤害",
            "能量伤害": "受目标能量抗性百分比减免，无视物理装甲",
        },
        "attack_phases": {
            "锁定阶段": "武器选择目标并锁定，锁定时间受舰船大小影响",
            "冷却阶段": "攻击完成后的冷却时间",
            "攻击持续阶段": "弹药发射过程，多轮攻击在此阶段完成",
        },
        "ship_systems": {
            "主武器系统": "被摧毁后舰船失去攻击能力，可修复2次",
            "机库系统": "被摧毁后无法起降舰载机，可修复1次",
            "指挥系统": "被摧毁后失去旗舰效果加成",
            "推进系统": "被摧毁后航速大幅降低，战斗中不可修复",
        },
        "aircraft_modes": {
            "独立作战": "舰载机在目标附近持续攻击，不返回母舰",
            "往复打击": "舰载机攻击后返回母舰补给，重新出击",
        },
        "anti_air_types": {
            "反击防空": "被舰载机攻击时触发，保护同排友军",
            "区域防空": "主动防护同排友军，可升级为大区域防空",
            "主动防空": "主动搜索并攻击任何空中目标",
        },
        "interception_formula": "拦截率 = 1 - (1-自身拦截率)^n × (1-同排拦截率)^m × (1-全局拦截率)^k",
        "combat_formulas": {
            "能量单发": "基础伤害 × (1 + 伤害加成 - 目标护盾%) × 调校系数 + 特殊效果",
            "实弹单发": "(基础伤害 × (1 + 伤害加成) - 目标装甲) × 调校系数 + 特殊效果（保底10%）",
            "命中率": "基础命中 × (1 + 命中加成 - 目标闪避) × 锁定效率",
            "暴击": "暴击率判定 → 暴击伤害 = 基础暴击伤害 × (1 + 暴伤加成 - 目标暴伤减免)",
            "最终冷却": "基础冷却 × (1 - 冷却缩减) × (1 - 策略系数)",
        },
        "fleet_rules": {
            "旗舰": "每舰队1艘旗舰，指挥系统被毁后旗舰效果失效",
            "护航": "护航舰队存活时，被护航舰队免伤",
            "增援": "增援舰队上限9艘",
            "指挥值": "舰队总指挥值上限500",
            "分伤机制": "可攻击目标数 = 总目标数 / 2.5（向下取整），分散火力",
        },
        "ship_ratings_guide": {
            "S": "顶级性能，同类型中的最优选择",
            "A": "优秀性能，高性价比推荐",
            "B": "良好性能，特定场景有用",
            "C": "一般性能，过渡期使用",
            "D": "较差性能，不推荐",
        },
    }
    return knowledge


def get_combat_knowledge_text() -> str:
    """
    生成注入 AI 提示词的游戏知识文本
    
    从战斗机制文档和结构化知识中提取关键内容，
    使 AI 能基于真实游戏数据进行推理。
    """
    knowledge = get_game_knowledge()
    
    parts = []
    parts.append("【《无尽的拉格朗日》游戏机制核心知识】")
    parts.append("")
    
    # 武器类型
    parts.append("## 武器系统")
    for weapon, desc in knowledge["weapon_types"].items():
        parts.append(f"- {weapon}：{desc}")
    parts.append("")
    
    # 伤害类型
    parts.append("## 伤害计算")
    for dmg_type, desc in knowledge["damage_types"].items():
        parts.append(f"- {dmg_type}：{desc}")
    for formula_name, formula in knowledge["combat_formulas"].items():
        parts.append(f"- {formula_name}：{formula}")
    parts.append("")
    
    # 攻击流程
    parts.append("## 攻击流程（锁定→攻击→冷却）")
    for phase, desc in knowledge["attack_phases"].items():
        parts.append(f"- {phase}：{desc}")
    parts.append("")
    
    # 舰船系统
    parts.append("## 舰船四大系统")
    for sys_name, sys_desc in knowledge["ship_systems"].items():
        parts.append(f"- {sys_name}：{sys_desc}")
    parts.append("")
    
    # 舰载机
    parts.append("## 舰载机机制")
    for mode, desc in knowledge["aircraft_modes"].items():
        parts.append(f"- {mode}：{desc}")
    parts.append("")
    
    # 防空
    parts.append("## 防空体系")
    for aa_type, desc in knowledge["anti_air_types"].items():
        parts.append(f"- {aa_type}：{desc}")
    parts.append("")
    
    # 拦截
    parts.append(f"## 拦截机制\n{knowledge['interception_formula']}")
    parts.append("")
    
    # 舰队规则
    parts.append("## 舰队规则")
    for rule, desc in knowledge["fleet_rules"].items():
        parts.append(f"- {rule}：{desc}")
    parts.append("")
    
    return "\n".join(parts)


def get_ship_summary_for_prompt(max_ships: int = 50) -> str:
    """
    生成舰船数据摘要供 AI 提示词使用
    
    从 ship_database.json 读取完整舰船数据，提取关键属性摘要
    """
    json_path = get_lagrange_docs_path() / "ship_database.json"
    if not json_path.exists():
        return ""
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            ships = json.load(f)
    except Exception:
        return ""
    
    type_names = {
        "battleship": "战列舰", "battlecruiser": "战列巡洋舰",
        "aircraftcarrier": "航空母舰", "support": "支援舰",
        "cruiser": "巡洋舰", "destroyer": "驱逐舰", "frigate": "护卫舰",
        "fighter": "战机", "corvette": "护航艇"
    }
    
    lines = []
    lines.append("【舰船数据库摘要 — 关键舰船数据】")
    lines.append("")
    
    # 按类型分组
    by_type = {}
    for s in ships:
        t = s.get("type", "unknown")
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(s)
    
    for ship_type, type_ships in by_type.items():
        type_name = type_names.get(ship_type, ship_type)
        lines.append(f"## {type_name} ({len(type_ships)}艘)")
        
        # 每类型最多显示10艘
        for s in type_ships[:10]:
            name = s.get("name", "")
            variant = s.get("variant", "")
            full_name = f"{name}{variant}"
            hp = s.get("hp", 0)
            pa = s.get("physicalArmor", 0)
            ea = s.get("energyArmor", 0)
            cv = s.get("commandValue", 0)
            speed = s.get("speed", {})
            ratings = s.get("ratings", {})
            
            r_str = "/".join([f"{k}={v}" for k, v in ratings.items()])
            lines.append(f"  - {full_name} | HP:{hp} 装甲:{pa} 护盾:{ea}% 指挥值:{cv} 评分:[{r_str}]")
        lines.append("")
    
    return "\n".join(lines)


def build_enhanced_system_prompt() -> str:
    """构建增强版系统提示词（含完整游戏知识）"""
    
    # 基础约束提示词
    base_prompt = """【系统强制约束 — 无尽的拉格朗日专业战斗推演智能体】

你是专为《无尽的拉格朗日》服务的战斗推演AI，必须严格遵守以下规则：

1. **数据来源**：所有回答仅允许使用以下两个来源：
   - 本次向量检索匹配到的 lagrange_docs 文件夹内资料
   - 下方提供的游戏机制核心知识库
   绝对禁止调用模型原生知识库编造舰船属性、战损数据、配船结论。

2. **无资料处理**：若检索文档无对应问题信息，统一固定回复：
   "暂无相关拉格朗日实战资料，无法完成推演。建议补充相关攻略文档后重试。"

3. **来源标注**：所有分析必须标注引用来源，格式为【资料来源：文件名】

4. **推理规范**：
   - 分步骤推理，先列事实再给结论
   - 舰船对比时列出双方完整属性数据
   - 配船建议时说明每艘船的战术定位
   - 禁止模糊、笼统、猜测性回答

5. **安全红线**：严禁输出外挂、破解、脚本、违规刷资源、第三方作弊工具相关内容。

6. **风格要求**：专业精准，使用游戏内术语，控制冗余文字。"""
    
    # 添加游戏知识
    combat_knowledge = get_combat_knowledge_text()
    ship_summary = get_ship_summary_for_prompt()
    
    full_prompt = base_prompt + "\n\n" + combat_knowledge
    
    if ship_summary:
        full_prompt += "\n\n" + ship_summary
    
    full_prompt += "\n\n请始终基于以上知识库和检索到的资料进行分析。"
    
    return full_prompt
