# -*- coding: utf-8 -*-
"""
策略技能系统
------------
完整的舰船策略技能管理，包括：
- 技能数据库（各舰船可装备的策略技能）
- 技能激活/冷却/持续时间管理
- 技能效果应用（伤害加成/冷却缩减/命中/拦截等）
- 旗舰技能特殊处理

策略技能类型：
- 攻击策略：伤害加成、暴击率提升
- 防御策略：装甲提升、护盾恢复
- 机动策略：冷却缩减、锁定加速
- 旗舰策略：全队光环效果
"""

import time
from enum import Enum
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field


class StrategyType(Enum):
    """策略技能类型"""
    OFFENSIVE = "offensive"          # 攻击型
    DEFENSIVE = "defensive"          # 防御型
    MOBILITY = "mobility"            # 机动型
    FLAGSHIP = "flagship"            # 旗舰型（全队效果）
    SUPPORT = "support"              # 支援型
    SPECIAL = "special"              # 特殊型


@dataclass
class StrategyEffect:
    """策略技能效果"""
    stat: str                        # 影响的属性
    value: float                     # 效果值（小数）
    is_percentage: bool = True       # 是否百分比加成
    target: str = "self"             # self / fleet / ally_row / enemy


@dataclass
class StrategySkill:
    """策略技能定义"""
    id: str
    name: str
    description: str
    skill_type: StrategyType
    cooldown: float                  # 冷却时间（秒）
    duration: float                  # 持续时间（秒）
    effects: List[StrategyEffect] = field(default_factory=list)
    cooldown_reduction: float = 0.0  # 策略技能本身的冷却缩减系数
    activation_condition: str = "auto"  # auto / manual / on_damage / on_kill
    max_uses: int = 99               # 最大使用次数（99=无限制）
    requires_command_system: bool = False  # 是否需要指挥系统


class StrategyState(Enum):
    """技能状态"""
    READY = "ready"
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    DEPLETED = "depleted"


@dataclass
class ActiveStrategy:
    """正在运行的策略技能实例"""
    skill: StrategySkill
    state: StrategyState = StrategyState.READY
    remaining_duration: float = 0.0
    remaining_cooldown: float = 0.0
    uses_remaining: int = 99
    activated_at: float = 0.0

    def is_ready(self) -> bool:
        return self.state == StrategyState.READY and self.uses_remaining > 0


class StrategyManager:
    """
    策略技能管理器

    管理单艘舰船或整个舰队的所有策略技能。
    可以按舰船实例注册，也可以按舰队级别管理。
    """

    # 预定义的策略技能数据库
    SKILL_DATABASE: Dict[str, StrategySkill] = {
        "focused_fire": StrategySkill(
            id="focused_fire",
            name="集中火力",
            description="提升对大型舰船的伤害，持续20秒",
            skill_type=StrategyType.OFFENSIVE,
            cooldown=60.0,
            duration=20.0,
            effects=[
                StrategyEffect("dmg_bonus", 0.25, True, "self"),
                StrategyEffect("crit_rate", 0.10, True, "self"),
            ],
        ),
        "emergency_repair": StrategySkill(
            id="emergency_repair",
            name="紧急维修",
            description="立即恢复舰船15%最大HP，冷却120秒",
            skill_type=StrategyType.DEFENSIVE,
            cooldown=120.0,
            duration=0.0,
            effects=[
                StrategyEffect("instant_heal_pct", 0.15, True, "self"),
            ],
            activation_condition="on_damage",
            max_uses=3,
        ),
        "rapid_fire": StrategySkill(
            id="rapid_fire",
            name="速射模式",
            description="降低武器冷却时间30%，持续15秒",
            skill_type=StrategyType.MOBILITY,
            cooldown=45.0,
            duration=15.0,
            effects=[
                StrategyEffect("cooldown_reduction", 0.30, True, "self"),
            ],
        ),
        "anti_air_formation": StrategySkill(
            id="anti_air_formation",
            name="防空阵型",
            description="提升同排友军的防空效率25%，持续30秒",
            skill_type=StrategyType.SUPPORT,
            cooldown=90.0,
            duration=30.0,
            effects=[
                StrategyEffect("aa_hit_bonus", 0.25, True, "ally_row"),
            ],
        ),
        "flagship_command": StrategySkill(
            id="flagship_command",
            name="旗舰指挥",
            description="全队伤害提升10%，持续45秒",
            skill_type=StrategyType.FLAGSHIP,
            cooldown=180.0,
            duration=45.0,
            effects=[
                StrategyEffect("dmg_bonus", 0.10, True, "fleet"),
                StrategyEffect("hit_bonus", 0.08, True, "fleet"),
            ],
            requires_command_system=True,
        ),
        "intercept_net": StrategySkill(
            id="intercept_net",
            name="拦截网",
            description="同排友军舰船拦截率提升15%，持续25秒",
            skill_type=StrategyType.SUPPORT,
            cooldown=75.0,
            duration=25.0,
            effects=[
                StrategyEffect("intercept_bonus", 0.15, True, "ally_row"),
            ],
        ),
        "shield_overload": StrategySkill(
            id="shield_overload",
            name="护盾超载",
            description="临时提升能量护盾30%，持续20秒，冷却后护盾降低10%",
            skill_type=StrategyType.DEFENSIVE,
            cooldown=60.0,
            duration=20.0,
            effects=[
                StrategyEffect("energy_shield_bonus", 0.30, True, "self"),
            ],
        ),
        "evasive_maneuvers": StrategySkill(
            id="evasive_maneuvers",
            name="规避机动",
            description="提升闪避率15%，持续15秒",
            skill_type=StrategyType.MOBILITY,
            cooldown=40.0,
            duration=15.0,
            effects=[
                StrategyEffect("evasion_bonus", 0.15, True, "self"),
            ],
            activation_condition="on_damage",
        ),
        "armor_reinforcement": StrategySkill(
            id="armor_reinforcement",
            name="装甲强化",
            description="物理装甲提升40点，持续30秒",
            skill_type=StrategyType.DEFENSIVE,
            cooldown=50.0,
            duration=30.0,
            effects=[
                StrategyEffect("armor_bonus", 40, False, "self"),
            ],
        ),
        "targeting_systems": StrategySkill(
            id="targeting_systems",
            name="火控强化",
            description="提升锁定效率30%，命中率10%，持续25秒",
            skill_type=StrategyType.OFFENSIVE,
            cooldown=55.0,
            duration=25.0,
            effects=[
                StrategyEffect("lock_efficiency_bonus", 0.30, True, "self"),
                StrategyEffect("hit_bonus", 0.10, True, "self"),
            ],
        ),
    }

    def __init__(self):
        self.active_skills: Dict[str, List[ActiveStrategy]] = {}  # ship_id -> skills
        self.global_effects: Dict[str, float] = {}  # 舰队级效果汇总
        self.logs: List[str] = []

    def register_ship_skills(
        self, ship_id: str, skill_ids: List[str]
    ) -> None:
        """为舰船注册策略技能"""
        skills = []
        for sid in skill_ids:
            if sid in self.SKILL_DATABASE:
                skills.append(ActiveStrategy(
                    skill=self.SKILL_DATABASE[sid],
                    uses_remaining=self.SKILL_DATABASE[sid].max_uses,
                ))
        if skills:
            self.active_skills[ship_id] = skills
            skill_names = [s.skill.name for s in skills]
            self.logs.append(
                f"🎯 策略技能就绪: {', '.join(skill_names)}"
            )

    def activate_skill(self, ship_id: str, skill_id: str,
                       current_time: float) -> bool:
        """激活策略技能"""
        if ship_id not in self.active_skills:
            return False

        for active in self.active_skills[ship_id]:
            if active.skill.id == skill_id and active.is_ready():
                # 检查指挥系统需求
                if active.skill.requires_command_system:
                    # 由外部检查指挥系统是否可用
                    pass

                active.state = StrategyState.ACTIVE
                active.remaining_duration = active.skill.duration
                active.activated_at = current_time
                active.uses_remaining -= 1

                self.logs.append(
                    f"⚡ {active.skill.name} 激活！持续{active.skill.duration:.0f}秒"
                )

                # 即时效果（如瞬间回复）
                for effect in active.skill.effects:
                    if effect.stat == "instant_heal_pct":
                        pass  # 由外部处理HP回复

                return True

        return False

    def update(self, dt: float, current_time: float) -> None:
        """更新所有活跃策略技能"""
        for ship_id, skills in self.active_skills.items():
            for active in skills:
                if active.state == StrategyState.ACTIVE:
                    active.remaining_duration -= dt
                    if active.remaining_duration <= 0:
                        active.state = StrategyState.COOLDOWN
                        active.remaining_cooldown = active.skill.cooldown
                        self.logs.append(
                            f"⏱️ {active.skill.name} 效果结束，进入冷却"
                        )

                elif active.state == StrategyState.COOLDOWN:
                    active.remaining_cooldown -= dt
                    if active.remaining_cooldown <= 0:
                        if active.uses_remaining > 0:
                            active.state = StrategyState.READY
                            self.logs.append(
                                f"✅ {active.skill.name} 冷却完成"
                            )
                        else:
                            active.state = StrategyState.DEPLETED

    def get_active_effects(self, ship_id: str) -> Dict[str, float]:
        """获取某舰船当前生效的策略效果汇总"""
        effects = {
            "dmg_bonus": 0.0,
            "cooldown_reduction": 0.0,
            "hit_bonus": 0.0,
            "crit_rate_bonus": 0.0,
            "evasion_bonus": 0.0,
            "armor_bonus": 0.0,
            "energy_shield_bonus": 0.0,
            "aa_hit_bonus": 0.0,
            "intercept_bonus": 0.0,
            "lock_efficiency_bonus": 0.0,
        }

        # 自身技能效果
        if ship_id in self.active_skills:
            for active in self.active_skills[ship_id]:
                if active.state == StrategyState.ACTIVE:
                    for effect in active.skill.effects:
                        if effect.target == "self" and effect.stat in effects:
                            effects[effect.stat] += effect.value

        # 舰队级效果（来自旗舰技能等）
        for stat, value in self.global_effects.items():
            if stat in effects:
                effects[stat] += value

        return effects

    def apply_fleet_effect(self, effect: StrategyEffect) -> None:
        """应用舰队级效果"""
        if effect.stat in self.global_effects:
            self.global_effects[effect.stat] += effect.value
        else:
            self.global_effects[effect.stat] = effect.value

    def remove_fleet_effect(self, effect: StrategyEffect) -> None:
        """移除舰队级效果"""
        if effect.stat in self.global_effects:
            self.global_effects[effect.stat] -= effect.value
            if self.global_effects[effect.stat] <= 0:
                del self.global_effects[effect.stat]

    def get_auto_activation_candidates(
        self, ship_id: str, trigger: str
    ) -> List[str]:
        """获取可自动激活的候选技能"""
        candidates = []
        if ship_id not in self.active_skills:
            return candidates

        for active in self.active_skills[ship_id]:
            if (active.is_ready() and
                active.skill.activation_condition == trigger):
                candidates.append(active.skill.id)

        return candidates

    def get_stats(self) -> Dict:
        """获取策略技能统计"""
        total = 0
        active_count = 0
        for skills in self.active_skills.values():
            total += len(skills)
            active_count += sum(
                1 for s in skills if s.state == StrategyState.ACTIVE
            )

        return {
            "total_registered_skills": total,
            "currently_active": active_count,
            "fleet_effects": dict(self.global_effects),
        }
