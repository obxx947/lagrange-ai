# -*- coding: utf-8 -*-
"""
防空作战系统
------------
完整的防空（Anti-Air）模拟系统，支持三种防空模式：

1. 反击防空（Counter AA）：
   - 友方被空袭时自动触发
   - 舰船载防空武器基础命中15%
   - 战机载防空武器基础命中60%
   - 攻击同排来袭舰载机

2. 区域防空（Area AA）：
   - 周期性为同排友军提供防空掩护
   - 可升级为跨排或全舰队覆盖
   - 特殊舰船：枪骑兵（全舰队）、圆锥综合（覆盖相邻排）

3. 主动防空（Active AA）：
   - 独立索敌，主动攻击任何空中目标
   - 无反应延迟，优先级最高
   - 特殊舰船：米斯特拉、沙龙、CVT800、狼蜥、锆石、刺水母
"""

import math
import random
from enum import Enum
from typing import List, Dict, Optional, Any, Set, Tuple
from dataclasses import dataclass, field

from .formulas import (
    calc_hit_chance, calc_energy_damage, calc_physical_damage,
    COUNTER_AA_SHIP_HIT, COUNTER_AA_AIRCRAFT_HIT,
)


class AAType(Enum):
    """防空类型"""
    COUNTER = "counter"        # 反击防空：友方被空袭时触发
    AREA = "area"              # 区域防空：持续覆盖同排/相邻排
    ACTIVE = "active"          # 主动防空：独立索敌自动攻击


@dataclass
class AAWeapon:
    """防空武器"""
    name: str
    aa_type: AAType
    damage_type: str              # "physical" / "energy"
    single_damage: float
    attacks: int = 1
    ammo: int = 1
    attack_duration: float = 0.0
    lock_time: float = 1.0
    cooldown: float = 3.0
    base_hit_rate: float = 0.15   # 防空基础命中率
    can_crit: bool = False
    crit_rate: float = 0.15
    crit_damage: float = 1.5
    is_aircraft_weapon: bool = False  # 是否舰载机武器（影响基础命中）
    area_coverage: str = "same_row"   # 区域覆盖范围
    active_ships: Set[str] = field(default_factory=set)  # 主动防空舰船名

    def get_base_hit(self) -> float:
        """获取基础命中率（舰载机武器60%，舰船武器15%）"""
        if self.is_aircraft_weapon:
            return COUNTER_AA_AIRCRAFT_HIT
        return COUNTER_AA_SHIP_HIT


@dataclass
class AirDefenseBattery:
    """防空炮台实例（单艘舰船的防空能力）"""
    ship_id: str
    ship_name: str
    ship_position: str             # front/mid/back
    aa_weapons: List[AAWeapon] = field(default_factory=list)
    weapon_states: List[Dict] = field(default_factory=list)
    total_kills: int = 0

    def is_alive(self) -> bool:
        """关联的舰船是否存活（由外部设置）"""
        return True

    def init_states(self) -> None:
        """初始化武器状态"""
        self.weapon_states = []
        for weapon in self.aa_weapons:
            self.weapon_states.append({
                "weapon": weapon,
                "cooldown_remaining": random.uniform(0, weapon.cooldown * 0.3),
                "current_target": None,
            })


class AntiairSystem:
    """
    防空系统管理器

    管理一场战斗中所有舰船的防空火力，协调对空中目标的攻击。
    """

    # 主动防空特殊舰船列表（游戏中已知的主动防空舰船）
    ACTIVE_AA_SHIPS = {
        "米斯特拉", "沙龙", "CVT800", "CV-T800",
        "狼蜥", "锆石", "刺水母",
        "Mistral", "Salom", "Wolf-Shark",
        "Zircon", "Thorn-Jellyfish",
    }

    # 区域防空特殊舰船（可覆盖全舰队或相邻排）
    AREA_FLEET_WIDE_SHIPS = {"枪骑兵", "Lancer"}
    AREA_ADJACENT_ROW_SHIPS = {"圆锥综合", "Cone-Comprehensive"}

    def __init__(self):
        self.batteries: List[AirDefenseBattery] = []
        self.logs: List[str] = []
        self.total_kills: int = 0
        self.area_coverage_active: bool = False

    def register_battery(self, battery: AirDefenseBattery) -> None:
        """注册防空炮台"""
        battery.init_states()
        self.batteries.append(battery)
        aa_types = set(w.aa_type for w in battery.aa_weapons)
        type_names = "+".join(t.value for t in aa_types) if aa_types else "none"
        self.logs.append(
            f"🛡️ {battery.ship_name} 防空系统就绪 [{type_names}]"
        )

    def remove_battery(self, ship_id: str) -> None:
        """移除被摧毁舰船的防空炮台"""
        self.batteries = [b for b in self.batteries if b.ship_id != ship_id]

    def get_active_batteries(self) -> List[AirDefenseBattery]:
        """获取所有存活的防空炮台"""
        return self.batteries

    def update(self, dt: float, active_aircraft: List[Any],
               attacked_friendly_positions: Set[str]) -> None:
        """
        更新防空系统

        Args:
            dt: 时间步长
            active_aircraft: 当前在空中的敌方舰载机列表
            attacked_friendly_positions: 被空袭的友方位置集合
        """
        if not active_aircraft:
            return

        for battery in self.batteries:
            if not battery.is_alive():
                continue

            for ws in battery.weapon_states:
                weapon = ws["weapon"]
                ws["cooldown_remaining"] -= dt

                if ws["cooldown_remaining"] > 0:
                    continue

                # 检查是否可以开火
                target = self._find_aa_target(
                    weapon, battery, active_aircraft,
                    attacked_friendly_positions
                )

                if target:
                    self._execute_aa_shot(weapon, battery, target, ws)
                    ws["cooldown_remaining"] = weapon.cooldown

    def _find_aa_target(
        self, weapon: AAWeapon, battery: AirDefenseBattery,
        active_aircraft: List[Any], attacked_positions: Set[str]
    ) -> Optional[Any]:
        """
        根据防空类型寻找目标

        - 反击防空：仅在友方被空袭时触发，攻击同排飞机
        - 区域防空：覆盖同排/相邻排/全舰队
        - 主动防空：独立索敌，无限制
        """
        if not active_aircraft:
            return None

        if weapon.aa_type == AAType.COUNTER:
            # 反击防空：只有友方受袭时触发
            if battery.ship_position not in attacked_positions:
                return None
            # 攻击同排飞机
            targets = active_aircraft  # 简化：攻击所有空中目标

        elif weapon.aa_type == AAType.AREA:
            # 区域防空：持续覆盖
            coverage = weapon.area_coverage
            if coverage == "same_row":
                targets = active_aircraft
            elif coverage == "adjacent_row":
                targets = active_aircraft
            elif coverage == "fleet_wide":
                targets = active_aircraft
            else:
                targets = active_aircraft

        elif weapon.aa_type == AAType.ACTIVE:
            # 主动防空：自由选择目标
            targets = active_aircraft

        else:
            targets = active_aircraft

        if not targets:
            return None

        # 优先攻击大型/高威胁目标
        large_targets = [t for t in targets
                        if getattr(t, "aircraft_size", "single") == "large"]
        if large_targets:
            return random.choice(large_targets)

        return random.choice(targets)

    def _execute_aa_shot(
        self, weapon: AAWeapon, battery: AirDefenseBattery,
        target: Any, ws: Dict
    ) -> None:
        """执行一次防空射击"""
        # 命中判定
        base_hit = weapon.get_base_hit()
        hit_chance = calc_hit_chance(base_hit, lock_efficiency=1.0, evasion=0.0)

        if random.random() > hit_chance:
            return  # 未命中

        # 伤害计算
        if weapon.damage_type == "energy":
            dmg = calc_energy_damage(
                weapon.single_damage,
                getattr(target, "energy_armor_pct", 0),
            )
        else:
            dmg = calc_physical_damage(
                weapon.single_damage,
                getattr(target, "physical_armor", 5),
            )

        # 暴击判定
        if weapon.can_crit and random.random() < weapon.crit_rate:
            dmg *= weapon.crit_damage

        # 多重攻击
        total_dmg = dmg * weapon.attacks * weapon.ammo

        # 应用伤害到目标（调用AircraftManager的伤害方法需要外部适配）
        target_dmg = total_dmg
        if hasattr(target, "apply_damage"):
            target.apply_damage(target_dmg)
        elif hasattr(target, "current_hp_per_unit"):
            # 舰载机单元：按单架HP计算击落数
            kills = int(target_dmg / max(1, target.max_hp_per_unit))
            kills = min(kills, target.current_count)
            target.current_count -= kills
            if kills > 0:
                battery.total_kills += kills
                self.total_kills += kills
                self.logs.append(
                    f"💥 {battery.ship_name}[{weapon.name}] 击落 {target.name} ×{kills}架！"
                )
        else:
            # 尝试直接扣HP
            if hasattr(target, "current_hp"):
                target.current_hp -= target_dmg

    def notify_air_attack(self, attacked_position: str) -> None:
        """通知某个位置的友方舰船正在被空袭（触发反击防空）"""
        # 由外部在舰载机攻击时调用
        pass

    def get_coverage_stats(self) -> Dict:
        """获取防空覆盖统计"""
        counter = sum(1 for b in self.batteries
                     for w in b.aa_weapons if w.aa_type == AAType.COUNTER)
        area = sum(1 for b in self.batteries
                  for w in b.aa_weapons if w.aa_type == AAType.AREA)
        active = sum(1 for b in self.batteries
                    for w in b.aa_weapons if w.aa_type == AAType.ACTIVE)

        return {
            "total_batteries": len(self.batteries),
            "counter_aa_count": counter,
            "area_aa_count": area,
            "active_aa_count": active,
            "total_kills": self.total_kills,
            "batteries": [
                {
                    "ship_name": b.ship_name,
                    "weapons": len(b.aa_weapons),
                    "kills": b.total_kills,
                }
                for b in self.batteries
            ],
        }

    @classmethod
    def is_active_aa_ship(cls, ship_name: str) -> bool:
        """判断是否为主动防空舰船"""
        for keyword in cls.ACTIVE_AA_SHIPS:
            if keyword in ship_name:
                return True
        return False

    @classmethod
    def is_area_fleet_wide_ship(cls, ship_name: str) -> bool:
        """判断是否为全舰队区域防空舰船"""
        for keyword in cls.AREA_FLEET_WIDE_SHIPS:
            if keyword in ship_name:
                return True
        return False
