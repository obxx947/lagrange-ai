# -*- coding: utf-8 -*-
"""
舰载机作战系统
--------------
完整的舰载机（战机/护航艇）作战模拟，支持：
- 独立作战模式：脱离母舰自主搜索攻击目标
- 往复打击模式：起飞→飞行→攻击→返航→装填→再起飞
- 机库保护：返航期间不受攻击
- 母舰摧毁处理：母舰被毁 → 所有舰载机摧毁
- 载体机库加成：不同航母的速度/伤害/锁定加成
- 飞行时间模拟：基于轰炸距离的飞行时间计算
"""

import math
import random
from enum import Enum
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from .formulas import (
    calc_flight_time, calc_bomb_distance_hit_modifier,
    calc_carrier_hangar_bonus, calc_hit_chance,
    calc_energy_damage, calc_physical_damage,
    calc_crit_damage, calc_crit_rate, CRIT_BASE_RATE,
    TUNING_COEFFICIENT, SYSTEM_DAMAGE_CHANCE,
)


class FlightMode(Enum):
    """舰载机飞行模式"""
    INDEPENDENT = "independent"       # 独立作战：脱离母舰，自主锁定/攻击/冷却
    RECIPROCATING = "reciprocating"   # 往复打击：起飞→攻击→返航→装填→再起飞


class AircraftState(Enum):
    """舰载机状态"""
    IN_HANGAR = "in_hangar"           # 在机库中
    FLYING_OUT = "flying_out"         # 飞行出击中
    COMBAT = "combat"                 # 战斗中
    RETURNING = "returning"           # 返航中
    RELOADING = "reloading"           # 装填中
    DESTROYED = "destroyed"           # 已摧毁


@dataclass
class AircraftWeapon:
    """舰载机武器"""
    name: str
    damage_type: str                  # "physical" / "energy"
    single_damage: float
    attacks: int = 1
    ammo: int = 1
    attack_duration: float = 0.0
    lock_time: float = 2.0
    cooldown: float = 6.0
    priority: str = "random"
    can_crit: bool = True
    crit_rate: float = 0.15
    crit_damage: float = 1.5
    hit_rate: float = 0.65
    anti_air_type: Optional[str] = None  # counter/area/active
    sub_system_targets: Dict[str, str] = field(default_factory=dict)
    intercept_rate: float = 0.0


@dataclass
class AircraftUnit:
    """舰载机单元（单个中队/编队）"""
    id: str
    name: str
    aircraft_type: str                # "fighter" / "corvette"
    aircraft_size: str                # "single" / "medium" / "large"
    flight_mode: FlightMode
    squadron_size: int                # 中队规模（舰载机数量）
    current_count: int                # 当前存活数量
    max_hp_per_unit: float            # 每架舰载机的HP
    current_hp_per_unit: float
    physical_armor: float
    energy_armor_pct: float
    weapons: List[AircraftWeapon] = field(default_factory=list)
    mother_ship_id: str = ""          # 母舰ID
    mother_ship_name: str = ""
    carrier_bonuses: Dict[str, float] = field(default_factory=dict)

    # 运行时状态
    state: AircraftState = AircraftState.IN_HANGAR
    base_flight_out: float = 8.0      # 基础起飞时间（秒）
    base_flight_back: float = 8.0     # 基础返航时间（秒）
    flight_timer: float = 0.0
    combat_timer: float = 0.0
    cooldown_timer: float = 0.0
    reload_timer: float = 0.0
    current_target_id: str = ""
    total_damage_dealt: float = 0.0
    total_shots_fired: int = 0
    sorties: int = 0                  # 出击次数

    def is_alive(self) -> bool:
        return self.current_count > 0 and self.state != AircraftState.DESTROYED

    def is_vulnerable(self) -> bool:
        """在飞行中/战斗中才可被攻击"""
        return self.state in (
            AircraftState.FLYING_OUT,
            AircraftState.COMBAT,
            AircraftState.RETURNING
        )

    def effective_flight_out(self) -> float:
        """考虑机库加成的实际起飞时间"""
        speed_bonus = self.carrier_bonuses.get("speed_bonus", 0.0)
        return max(0.5, self.base_flight_out * (1.0 - speed_bonus))

    def effective_flight_back(self) -> float:
        """考虑机库加成的实际返航时间"""
        speed_bonus = self.carrier_bonuses.get("speed_bonus", 0.0)
        return max(0.5, self.base_flight_back * (1.0 - speed_bonus))


class AircraftManager:
    """
    舰载机管理器

    管理一场战斗中所有舰载机的生命周期：
    - 从母舰起飞
    - 在战场中作战
    - 返航装填
    - 母舰被毁处理
    """

    def __init__(self, bomb_distance: float = 15.0):
        self.aircraft_units: List[AircraftUnit] = []
        self.bomb_distance = bomb_distance
        self.logs: List[str] = []

    def register_aircraft(
        self,
        unit: AircraftUnit,
        carrier_name: str = ""
    ) -> None:
        """注册一个舰载机单元"""
        # 计算机库加成
        if carrier_name:
            unit.carrier_bonuses = {
                "speed_bonus": calc_carrier_hangar_bonus(carrier_name, "speed_bonus"),
                "dmg_bonus": calc_carrier_hangar_bonus(carrier_name, "dmg_bonus"),
                "lock_bonus": calc_carrier_hangar_bonus(carrier_name, "lock_bonus"),
            }
        self.aircraft_units.append(unit)

    def launch_aircraft(self, unit: AircraftUnit) -> None:
        """起飞舰载机（从机库出发）"""
        if unit.state != AircraftState.IN_HANGAR:
            return
        if not unit.is_alive():
            return

        unit.state = AircraftState.FLYING_OUT
        unit.flight_timer = unit.effective_flight_out()
        unit.sorties += 1
        self.logs.append(
            f"✈️ {unit.name} ×{unit.current_count} 从 {unit.mother_ship_name} 起飞出击！"
        )

    def recall_aircraft(self, unit: AircraftUnit) -> None:
        """召回舰载机"""
        if unit.state == AircraftState.COMBAT:
            unit.state = AircraftState.RETURNING
            unit.flight_timer = unit.effective_flight_back()
            unit.current_target_id = ""
            self.logs.append(
                f"🔙 {unit.name} 收到返航指令，返回 {unit.mother_ship_name}"
            )

    def destroy_mother_ship(self, mother_ship_id: str) -> None:
        """母舰被摧毁，所有舰载机同步摧毁"""
        for unit in self.aircraft_units:
            if unit.mother_ship_id == mother_ship_id and unit.is_alive():
                unit.state = AircraftState.DESTROYED
                unit.current_count = 0
                self.logs.append(
                    f"💀 母舰 {unit.mother_ship_name} 被毁，{unit.name} 全部坠毁！"
                )

    def get_active_aircraft(self) -> List[AircraftUnit]:
        """获取当前在空中/战斗中的舰载机（可被防空武器攻击）"""
        return [u for u in self.aircraft_units if u.is_alive() and u.is_vulnerable()]

    def get_combat_aircraft(self) -> List[AircraftUnit]:
        """获取正在战斗中的舰载机"""
        return [u for u in self.aircraft_units
                if u.state == AircraftState.COMBAT and u.is_alive()]

    def update(self, dt: float, available_targets: List[Any]) -> None:
        """
        更新所有舰载机的状态

        Args:
            dt: 时间步长（秒）
            available_targets: 可攻击的敌方舰船列表
        """
        for unit in self.aircraft_units:
            if not unit.is_alive():
                continue

            if unit.state == AircraftState.FLYING_OUT:
                self._update_flying_out(unit, dt)

            elif unit.state == AircraftState.COMBAT:
                self._update_combat(unit, dt, available_targets)

            elif unit.state == AircraftState.RETURNING:
                self._update_returning(unit, dt)

            elif unit.state == AircraftState.RELOADING:
                self._update_reloading(unit, dt)

            elif unit.state == AircraftState.IN_HANGAR:
                # 独立作战模式：从机库自动起飞
                if unit.flight_mode == FlightMode.INDEPENDENT:
                    self.launch_aircraft(unit)

    def _update_flying_out(self, unit: AircraftUnit, dt: float) -> None:
        """飞行出击阶段更新"""
        unit.flight_timer -= dt
        if unit.flight_timer <= 0:
            unit.state = AircraftState.COMBAT
            unit.combat_timer = 0.0
            self.logs.append(
                f"🎯 {unit.name} 已到达战场，开始搜索目标！"
            )

    def _update_combat(self, unit: AircraftUnit, dt: float,
                       targets: List[Any]) -> None:
        """战斗阶段更新"""
        unit.combat_timer += dt

        # 往复打击模式：完成一次攻击后返航
        if unit.flight_mode == FlightMode.RECIPROCATING:
            # 攻击持续一定时间后自动返航
            max_combat_time = 30.0  # 最大战斗时间
            if unit.combat_timer >= max_combat_time:
                self.recall_aircraft(unit)
                return

        # 处理舰载机武器攻击（简化：按DPS持续造成伤害）
        if targets and unit.combat_timer >= 2.0:  # 每2秒进行一次攻击
            self._execute_aircraft_attack(unit, targets)
            unit.combat_timer = 0.0

    def _execute_aircraft_attack(self, unit: AircraftUnit,
                                  targets: List[Any]) -> None:
        """
        执行舰载机攻击

        舰载机攻击特点：
        - 无视阵型（直飞目标）
        - 考虑轰炸距离对命中率的影响
        - 接受机库伤害加成
        """
        if not targets:
            return

        # 随机选择目标（实际游戏中按优先规则）
        target = random.choice(targets) if len(targets) > 0 else None
        if not target:
            return

        total_dmg = 0.0
        for weapon in unit.weapons:
            if unit.current_count <= 0:
                break

            # 命中判定（考虑轰炸距离）
            base_hit = weapon.hit_rate
            bomb_mod = calc_bomb_distance_hit_modifier(self.bomb_distance)
            hit_chance = calc_hit_chance(base_hit, bomb_distance=self.bomb_distance)
            hit_chance = max(0.01, min(0.99, hit_chance + bomb_mod * 0.5))

            if random.random() > hit_chance:
                continue

            # 伤害计算（考虑机库伤害加成）
            dmg_bonus = unit.carrier_bonuses.get("dmg_bonus", 0.0)
            if weapon.damage_type == "energy":
                dmg = calc_energy_damage(
                    weapon.single_damage,
                    getattr(target, "energy_armor_pct", 10),
                    dmg_bonus=dmg_bonus,
                )
            else:
                dmg = calc_physical_damage(
                    weapon.single_damage,
                    getattr(target, "physical_armor", 15),
                    dmg_bonus=dmg_bonus,
                )

            # 暴击判定
            if weapon.can_crit:
                crit_rate = CRIT_BASE_RATE
                if random.random() < crit_rate:
                    dmg *= calc_crit_damage(weapon.crit_damage)

            # 乘以存活舰载机数量
            dmg *= unit.current_count
            total_dmg += dmg
            unit.total_shots_fired += 1

        # 应用伤害到目标
        if hasattr(target, "current_hp") and total_dmg > 0:
            target.current_hp -= total_dmg
            unit.total_damage_dealt += total_dmg

    def _update_returning(self, unit: AircraftUnit, dt: float) -> None:
        """返航阶段更新（返航期间机库保护，不受攻击）"""
        unit.flight_timer -= dt
        if unit.flight_timer <= 0:
            unit.state = AircraftState.RELOADING
            unit.reload_timer = 5.0  # 装填时间5秒
            self.logs.append(
                f"🛬 {unit.name} 已返回 {unit.mother_ship_name}，开始装填"
            )

    def _update_reloading(self, unit: AircraftUnit, dt: float) -> None:
        """装填阶段更新"""
        unit.reload_timer -= dt
        if unit.reload_timer <= 0:
            unit.state = AircraftState.IN_HANGAR
            self.logs.append(
                f"✅ {unit.name} 装填完成，准备再次出击"
            )
            # 往复打击模式自动再次起飞
            if unit.flight_mode == FlightMode.RECIPROCATING:
                self.launch_aircraft(unit)

    def apply_damage_to_aircraft(
        self, unit_id: str, damage: float, source: str = "AA"
    ) -> int:
        """
        对舰载机单元造成伤害（防空武器攻击）

        Args:
            unit_id: 舰载机单元ID
            damage: 伤害值
            source: 伤害来源

        Returns:
            击落的舰载机数量
        """
        for unit in self.aircraft_units:
            if unit.id == unit_id and unit.is_alive() and unit.is_vulnerable():
                kills = int(damage / unit.max_hp_per_unit)
                kills = min(kills, unit.current_count)
                unit.current_count -= kills
                if kills > 0:
                    self.logs.append(
                        f"💥 {source}击落了 {unit.name} ×{kills}架！"
                    )
                if unit.current_count <= 0:
                    unit.state = AircraftState.DESTROYED
                    self.logs.append(
                        f"💀 {unit.name} 全灭！"
                    )
                return kills
        return 0

    def get_stats(self) -> Dict:
        """获取舰载机统计信息"""
        total = len(self.aircraft_units)
        alive = sum(1 for u in self.aircraft_units if u.is_alive())
        active = len(self.get_active_aircraft())
        total_dmg = sum(u.total_damage_dealt for u in self.aircraft_units)
        total_sorties = sum(u.sorties for u in self.aircraft_units)

        return {
            "total_units": total,
            "alive_units": alive,
            "active_aircraft": active,
            "total_damage_dealt": total_dmg,
            "total_sorties": total_sorties,
            "units": [
                {
                    "id": u.id,
                    "name": u.name,
                    "state": u.state.value,
                    "current_count": u.current_count,
                    "total_damage": u.total_damage_dealt,
                    "sorties": u.sorties,
                }
                for u in self.aircraft_units
            ],
        }
