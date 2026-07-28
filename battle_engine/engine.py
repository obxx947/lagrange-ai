# -*- coding: utf-8 -*-
"""
战斗模拟核心引擎
----------------
完整的无尽拉格朗日战斗模拟系统 v2.0

相比v1.0的新增功能：
- 舰载机独立/往复空战
- 防空（反击/区域/主动）
- 闪避系统 + per-target命中率
- 策略技能系统
- 系统数值HP + 修理上限
- 分伤机制
- 反拦截
- 轰炸模式
- 载体机库加成
"""

import math
import random
import json
from typing import List, Dict, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

from .formulas import (
    TUNING_COEFFICIENT, MIN_DAMAGE_RATIO, CRIT_BASE_RATE,
    SYSTEM_DAMAGE_CHANCE, PLUTUS_DAMAGE_REDUCTION,
    DAMAGE_DISTRIBUTION_DIVISOR,
    calc_energy_damage, calc_physical_damage, calc_system_damage,
    calc_hit_chance, calc_per_target_hit,
    calc_intercept_rate, calc_multi_ship_intercept,
    calc_crit_damage, calc_crit_rate,
    calc_final_cooldown, calc_final_lock_time,
    calc_repair_amount, calc_attackable_targets,
    calc_bomb_distance_hit_modifier, calc_flight_time,
    calc_carrier_hangar_bonus,
    SYSTEM_HP_RATIOS, SYSTEM_REPAIR_LIMITS,
    SYSTEM_TARGET_EFFICIENCY, SYSTEM_DAMAGE_COEFFICIENTS,
)
from .aircraft import (
    AircraftManager, AircraftUnit, AircraftWeapon,
    AircraftState, FlightMode,
)
from .antiair import AntiairSystem, AirDefenseBattery, AAWeapon, AAType
from .strategy import StrategyManager, StrategySkill, StrategyState


# ==================== 枚举和数据类 ====================

class WeaponType(Enum):
    DIRECT_FIRE = "direct"
    PROJECTILE = "projectile"

class DamageType(Enum):
    PHYSICAL = "physical"
    ENERGY = "energy"

class ShipPosition(Enum):
    FRONT = "front"
    MID = "mid"
    BACK = "back"
    AIR = "air"

class SystemType(Enum):
    MAIN_WEAPON = "main_weapon"
    HANGAR = "hangar"
    COMMAND = "command"
    PROPULSION = "propulsion"

class BattleMode(Enum):
    ESCORT = "escort"
    BOMB = "bomb"


@dataclass
class Weapon:
    """武器定义"""
    name: str
    weapon_type: WeaponType
    damage_type: DamageType
    single_damage: float
    attacks: int = 1
    ammo: int = 1
    attack_duration: float = 0
    lock_time: float = 1.0
    cooldown: float = 4.0
    priority: str = "random"
    can_crit: bool = False
    crit_rate: float = 0.15
    crit_damage: float = 1.5
    lock_efficiency: float = 1.0
    hit_rate: float = 0.7
    anti_air_type: Optional[AAType] = None
    intercept_rate: float = 0.0
    cannot_be_intercepted: bool = False
    sub_system_targets: Dict[str, float] = field(default_factory=dict)
    repair_dpm: float = 0.0
    anti_intercept: float = 0.0
    dmg_bonus_vs_type: Dict[str, float] = field(default_factory=dict)
    system_dmg_coeff: float = 1.0


@dataclass
class ShipInstance:
    """舰船战斗实例（v2增强版）"""
    id: str
    name: str
    ship_type: str
    position: ShipPosition
    max_hp: float
    current_hp: float
    physical_armor: float
    energy_armor_pct: float
    evasion: float = 0.0               # 闪避率
    is_super_capital: bool = False
    is_flagship: bool = False
    is_carrier: bool = False
    is_escort: bool = False
    is_escorted: bool = False
    side: str = "ally"
    alive: bool = True

    # 运行时状态
    weapons: List[Weapon] = field(default_factory=list)
    weapon_states: List[dict] = field(default_factory=list)

    # 系统（改为数值HP）
    sub_systems: Dict[str, float] = field(default_factory=dict)
    sub_system_max_hp: Dict[str, float] = field(default_factory=dict)
    sub_system_repair_count: Dict[str, int] = field(default_factory=dict)
    sub_system_repair_timers: Dict[str, float] = field(default_factory=dict)

    # 舰载机引用
    aircraft_ids: List[str] = field(default_factory=list)
    carrier_bonuses: Dict[str, float] = field(default_factory=dict)

    # 强化
    strengthen: Dict[str, float] = field(default_factory=dict)
    strategy_skills: List[str] = field(default_factory=list)

    # 策略技能当前效果
    active_effects: Dict[str, float] = field(default_factory=dict)

    def is_alive(self) -> bool:
        return self.alive and self.current_hp > 0

    def is_system_active(self, sys_name: str) -> bool:
        hp = self.sub_systems.get(sys_name, 0)
        return hp > 0


@dataclass
class BattleState:
    """战斗全局状态"""
    ally_ships: List[ShipInstance] = field(default_factory=list)
    enemy_ships: List[ShipInstance] = field(default_factory=list)
    time: float = 0.0
    ended: bool = False
    winner: str = ""
    logs: List[str] = field(default_factory=list)
    mode: BattleMode = BattleMode.ESCORT
    bomb_distance: float = 15.0

    # 护航状态
    ally_escort_alive: bool = True
    enemy_escort_alive: bool = True

    # 舰载机和防空
    ally_aircraft: Optional[AircraftManager] = None
    enemy_aircraft: Optional[AircraftManager] = None
    ally_aa: Optional[AntiairSystem] = None
    enemy_aa: Optional[AntiairSystem] = None

    # 策略技能
    ally_strategies: Optional[StrategyManager] = None
    enemy_strategies: Optional[StrategyManager] = None

    # 统计
    total_ally_damage: float = 0.0
    total_enemy_damage: float = 0.0
    ally_ships_lost: int = 0
    enemy_ships_lost: int = 0
    ally_aircraft_lost: int = 0
    enemy_aircraft_lost: int = 0


class BattleSimulator:
    """战斗模拟器核心类 v2.0"""

    def __init__(self, state: BattleState):
        self.state = state
        self._init_weapon_states()
        self._init_subsystems()

    def _init_weapon_states(self):
        for ship in self.state.ally_ships + self.state.enemy_ships:
            ship.weapon_states = []
            for weapon in ship.weapons:
                ship.weapon_states.append({
                    "weapon": weapon,
                    "phase": "cooldown",
                    "cooldown_remaining": random.uniform(0, weapon.cooldown * 0.5),
                    "lock_remaining": 0.0,
                    "attack_remaining": 0.0,
                    "shots_fired": 0,
                    "total_shots": weapon.ammo * weapon.attacks,
                    "current_target": None,
                })

    def _init_subsystems(self):
        for ship in self.state.ally_ships + self.state.enemy_ships:
            for sys_name, hp_ratio in SYSTEM_HP_RATIOS.items():
                max_hp = ship.max_hp * hp_ratio
                ship.sub_system_max_hp[sys_name] = max_hp
                ship.sub_systems[sys_name] = max_hp
                ship.sub_system_repair_count[sys_name] = 0

    def simulate_tick(self, dt: float) -> bool:
        if self.state.ended:
            return True

        self.state.time += dt

        # 更新策略技能
        self._update_strategies(dt)

        # 更新舰载机
        self._update_aircraft(dt)

        # 检查护航状态
        self._update_escort_status()

        # 舰船武器处理
        all_ally = [s for s in self.state.ally_ships if s.is_alive()]
        all_enemy = [s for s in self.state.enemy_ships if s.is_alive()]

        for ship in all_ally:
            self._process_ship_weapons(ship, all_enemy, dt)
        for ship in all_enemy:
            self._process_ship_weapons(ship, all_ally, dt)

        # 维修
        for ship in all_ally:
            self._process_repairs(ship, all_ally, dt)
        for ship in all_enemy:
            self._process_repairs(ship, all_enemy, dt)

        # 系统修复计时器
        for ship in all_ally + all_enemy:
            self._process_system_repairs(ship, dt)

        # 防空更新
        self._update_antiair(dt)

        # 检查胜负
        return self._check_win_condition()

    def _update_strategies(self, dt: float):
        if self.state.ally_strategies:
            self.state.ally_strategies.update(dt, self.state.time)
            for ship in self.state.ally_ships:
                if ship.id in self.state.ally_strategies.active_skills:
                    ship.active_effects = self.state.ally_strategies.get_active_effects(ship.id)

        if self.state.enemy_strategies:
            self.state.enemy_strategies.update(dt, self.state.time)
            for ship in self.state.enemy_ships:
                if ship.id in self.state.enemy_strategies.active_skills:
                    ship.active_effects = self.state.enemy_strategies.get_active_effects(ship.id)

    def _update_aircraft(self, dt: float):
        all_enemy_ships = [s for s in self.state.enemy_ships if s.is_alive()]
        all_ally_ships = [s for s in self.state.ally_ships if s.is_alive()]

        if self.state.ally_aircraft:
            self.state.ally_aircraft.update(dt, all_enemy_ships)
        if self.state.enemy_aircraft:
            self.state.enemy_aircraft.update(dt, all_ally_ships)

    def _update_antiair(self, dt: float):
        ally_aircraft_active = (
            self.state.ally_aircraft.get_active_aircraft()
            if self.state.ally_aircraft else []
        )
        enemy_aircraft_active = (
            self.state.enemy_aircraft.get_active_aircraft()
            if self.state.enemy_aircraft else []
        )

        attacked_positions_ally = set()
        attacked_positions_enemy = set()

        if self.state.ally_aa:
            self.state.ally_aa.update(dt, enemy_aircraft_active, attacked_positions_ally)
        if self.state.enemy_aa:
            self.state.enemy_aa.update(dt, ally_aircraft_active, attacked_positions_enemy)

    def _update_escort_status(self):
        self.state.ally_escort_alive = any(
            s.is_alive() and s.is_escort for s in self.state.ally_ships
        )
        self.state.enemy_escort_alive = any(
            s.is_alive() and s.is_escort for s in self.state.enemy_ships
        )

    def _process_ship_weapons(self, ship: ShipInstance,
                               enemies: List[ShipInstance], dt: float):
        for ws in ship.weapon_states:
            weapon = ws["weapon"]

            if ws["phase"] == "cooldown":
                cd_reduction = ship.active_effects.get("cooldown_reduction", 0.0)
                ws["cooldown_remaining"] -= dt
                if ws["cooldown_remaining"] <= 0:
                    ws["phase"] = "lock"
                    ws["lock_remaining"] = calc_final_lock_time(
                        weapon.lock_time,
                        lock_reduction=ship.active_effects.get("lock_efficiency_bonus", 0.0)
                    )

            elif ws["phase"] == "lock":
                ws["lock_remaining"] -= dt
                target = self._find_target(ship, enemies, weapon)
                ws["current_target"] = target

                if ws["lock_remaining"] <= 0:
                    if target and target.is_alive():
                        ws["phase"] = "attack"
                        ws["attack_remaining"] = weapon.attack_duration
                        ws["shots_fired"] = 0
                        if weapon.attack_duration <= 0:
                            self._fire_all_shots(ship, target, weapon, ws)
                            cd_reduction = ship.active_effects.get("cooldown_reduction", 0.0)
                            ws["phase"] = "cooldown"
                            ws["cooldown_remaining"] = calc_final_cooldown(
                                weapon.cooldown, cd_reduction
                            )
                    else:
                        cd_reduction = ship.active_effects.get("cooldown_reduction", 0.0)
                        ws["phase"] = "cooldown"
                        ws["cooldown_remaining"] = calc_final_cooldown(
                            weapon.cooldown, cd_reduction
                        )

            elif ws["phase"] == "attack":
                ws["attack_remaining"] -= dt
                target = ws["current_target"]

                if target and target.is_alive():
                    if weapon.attack_duration > 0:
                        shots_to_fire = max(1, int(
                            ws["total_shots"] * (dt / max(0.01, weapon.attack_duration))
                        ))
                        for _ in range(min(shots_to_fire,
                                          ws["total_shots"] - ws["shots_fired"])):
                            self._execute_shot(ship, target, weapon, ws)
                            ws["shots_fired"] += 1

                if ws["attack_remaining"] <= 0 or ws["shots_fired"] >= ws["total_shots"]:
                    cd_reduction = ship.active_effects.get("cooldown_reduction", 0.0)
                    ws["phase"] = "cooldown"
                    ws["cooldown_remaining"] = calc_final_cooldown(
                        weapon.cooldown, cd_reduction
                    )
                    ws["current_target"] = None

    def _find_target(self, attacker: ShipInstance,
                     enemies: List[ShipInstance],
                     weapon: Weapon) -> Optional[ShipInstance]:
        alive = [e for e in enemies if e.is_alive()]
        if not alive:
            return None

        # 分伤机制：限制可被攻击的目标数
        attackable_count = calc_attackable_targets(len(alive))
        if attackable_count < len(alive):
            # 优先攻击最近的/最危险的
            alive.sort(key=lambda e: e.current_hp / max(e.max_hp, 1))

        if weapon.weapon_type == WeaponType.DIRECT_FIRE:
            for pos in [ShipPosition.FRONT, ShipPosition.MID, ShipPosition.BACK]:
                candidates = [e for e in alive if e.position == pos]
                if candidates:
                    supers = [e for e in candidates if e.is_super_capital]
                    if supers:
                        return random.choice(supers)
                    return random.choice(candidates)

        return random.choice(alive)

    def _execute_shot(self, attacker: ShipInstance, target: ShipInstance,
                      weapon: Weapon, ws: dict):
        # 1. 命中判定（per-target + 闪避）
        base_hit = weapon.hit_rate
        hit_bonus = attacker.active_effects.get("hit_bonus", 0.0)
        target_evasion = target.evasion + target.active_effects.get("evasion_bonus", 0.0)
        lock_eff = weapon.lock_efficiency + attacker.active_effects.get("lock_efficiency_bonus", 0.0)

        hit_chance = calc_hit_chance(
            base_hit, lock_eff,
            evasion=target_evasion,
            bomb_distance=self.state.bomb_distance,
            hit_bonus=hit_bonus,
            target_evasion=target_evasion,
        )
        if random.random() > hit_chance:
            return

        # 2. 拦截判定（三层 + 反拦截）
        if not weapon.cannot_be_intercepted:
            intercept = self._calc_total_intercept(target, attacker)
            anti_intercept = weapon.anti_intercept + attacker.active_effects.get("anti_intercept_bonus", 0.0)
            intercept *= (1.0 - anti_intercept)
            if random.random() < intercept:
                return

        # 3. 护送保护
        if target.is_escorted:
            if (target.side == "ally" and self.state.ally_escort_alive) or \
               (target.side == "enemy" and self.state.enemy_escort_alive):
                return

        # 4. 伤害计算
        dmg_bonus = (attacker.strengthen.get("dmg_bonus", 0.0) / 100.0 +
                     attacker.active_effects.get("dmg_bonus", 0.0))
        strategy_coeff = 1.0

        if weapon.damage_type == DamageType.ENERGY:
            dmg = calc_energy_damage(
                weapon.single_damage,
                target.energy_armor_pct,
                dmg_bonus, strategy_coeff
            )
        else:
            dmg = calc_physical_damage(
                weapon.single_damage,
                target.physical_armor,
                dmg_bonus, strategy_coeff
            )

        # 5. 暴击判定
        if weapon.can_crit:
            crit_rate = CRIT_BASE_RATE + attacker.active_effects.get("crit_rate_bonus", 0.0)
            if random.random() < crit_rate:
                crit_mult = calc_crit_damage(weapon.crit_damage)
                dmg *= crit_mult

        # 6. 旗舰减伤
        dmg = self._apply_flagship_protection(target, dmg)

        # 7. 应用伤害
        target.current_hp -= dmg
        if attacker.side == "ally":
            self.state.total_ally_damage += dmg
        else:
            self.state.total_enemy_damage += dmg

        # 8. 系统伤害判定
        if random.random() < SYSTEM_DAMAGE_CHANCE:
            self._attempt_system_damage(target, weapon)

        # 9. 死亡检查
        if target.current_hp <= 0:
            self._handle_ship_death(target, attacker)

    def _fire_all_shots(self, attacker: ShipInstance, target: ShipInstance,
                        weapon: Weapon, ws: dict):
        for _ in range(weapon.ammo * weapon.attacks):
            if not target.is_alive():
                break
            self._execute_shot(attacker, target, weapon, ws)

    def _calc_total_intercept(self, target: ShipInstance,
                               attacker: ShipInstance) -> float:
        self_rate = 0.0
        same_row_rates = []
        global_rates = []

        all_friendlies = (self.state.ally_ships if target.side == "ally"
                         else self.state.enemy_ships)

        for ship in all_friendlies:
            if not ship.is_alive():
                continue
            for ws in ship.weapon_states:
                w = ws["weapon"]
                if w.intercept_rate > 0:
                    intercept_bonus = ship.active_effects.get("intercept_bonus", 0.0)
                    rate = min(1.0, w.intercept_rate + intercept_bonus)
                    if ship.id == target.id:
                        self_rate = max(self_rate, rate)
                    elif ship.position == target.position:
                        same_row_rates.append(rate)
                    else:
                        global_rates.append(rate)

        return calc_intercept_rate(self_rate, same_row_rates, global_rates)

    def _apply_flagship_protection(self, target: ShipInstance, dmg: float) -> float:
        all_friendlies = (self.state.ally_ships if target.side == "ally"
                         else self.state.enemy_ships)
        for ship in all_friendlies:
            if ship.is_flagship and ship.is_alive() and "普卢托斯" in ship.name:
                if ship.is_system_active("command"):
                    dmg *= (1.0 - PLUTUS_DAMAGE_REDUCTION)
                    break
        return dmg

    def _attempt_system_damage(self, target: ShipInstance, weapon: Weapon):
        for sys_name, efficiency in weapon.sub_system_targets.items():
            eff_value = SYSTEM_TARGET_EFFICIENCY.get(efficiency, 0.3)
            if random.random() < eff_value:
                # 系统HP伤害（数值化）
                sys_hp = target.sub_systems.get(sys_name, 0)
                if sys_hp <= 0:
                    continue

                # 系统伤害系数
                sys_coeff = weapon.system_dmg_coeff or 1.25
                sys_dmg = weapon.single_damage * sys_coeff * TUNING_COEFFICIENT * 0.5

                # 扣除系统HP
                target.sub_systems[sys_name] = max(0, sys_hp - sys_dmg)

                # 同时扣除舰船结构HP
                hp_penalty = sys_dmg * 0.3
                target.current_hp -= hp_penalty

                if target.sub_systems[sys_name] <= 0:
                    self.state.logs.append(
                        f"[{self.state.time:.1f}s] 💔 {target.name} {sys_name}系统被破坏！"
                    )
                    # 检查修理上限
                    repair_limit = SYSTEM_REPAIR_LIMITS.get(sys_name, 1)
                    current_repairs = target.sub_system_repair_count.get(sys_name, 0)
                    if current_repairs < repair_limit:
                        target.sub_system_repair_timers[sys_name] = 25.0
                    else:
                        self.state.logs.append(
                            f"[{self.state.time:.1f}s] 💀 {target.name} {sys_name}系统已永久损毁！"
                        )
                break

    def _handle_ship_death(self, target: ShipInstance, attacker: ShipInstance):
        target.current_hp = 0
        target.alive = False
        if target.side == "ally":
            self.state.ally_ships_lost += 1
        else:
            self.state.enemy_ships_lost += 1
        self.state.logs.append(
            f"[{self.state.time:.1f}s] 🏴 {attacker.name} 击毁了 {target.name}"
        )

        # 母舰死亡 → 所有舰载机摧毁
        if target.is_carrier:
            if target.side == "ally" and self.state.ally_aircraft:
                self.state.ally_aircraft.destroy_mother_ship(target.id)
            elif target.side == "enemy" and self.state.enemy_aircraft:
                self.state.enemy_aircraft.destroy_mother_ship(target.id)

    def _process_repairs(self, ship: ShipInstance, friendlies: List[ShipInstance],
                          dt: float):
        for ws in ship.weapon_states:
            repair_dpm = ws["weapon"].repair_dpm
            if repair_dpm <= 0:
                continue

            damaged = [f for f in friendlies
                      if f.is_alive() and f.current_hp < f.max_hp]
            if not damaged:
                continue

            target = min(damaged, key=lambda f: f.current_hp / max(f.max_hp, 1))
            heal = calc_repair_amount(repair_dpm, target.physical_armor, dt)
            target.current_hp = min(target.max_hp, target.current_hp + heal)

    def _process_system_repairs(self, ship: ShipInstance, dt: float):
        for sys_name, timer in list(ship.sub_system_repair_timers.items()):
            ship.sub_system_repair_timers[sys_name] -= dt
            if ship.sub_system_repair_timers[sys_name] <= 0:
                # 恢复系统HP
                max_hp = ship.sub_system_max_hp.get(sys_name, 0)
                ship.sub_systems[sys_name] = max_hp
                ship.sub_system_repair_count[sys_name] = (
                    ship.sub_system_repair_count.get(sys_name, 0) + 1
                )
                del ship.sub_system_repair_timers[sys_name]
                self.state.logs.append(
                    f"[{self.state.time:.1f}s] 🔧 {ship.name} {sys_name}系统已修复"
                )

    def _check_win_condition(self) -> bool:
        ally_alive = any(s.is_alive() for s in self.state.ally_ships)
        enemy_alive = any(s.is_alive() for s in self.state.enemy_ships)

        if not ally_alive:
            self.state.ended = True
            self.state.winner = "enemy"
            self.state.logs.append(
                f"💀 己方舰队全灭！敌方胜利！(耗时{self.state.time:.1f}s)"
            )
            return True
        if not enemy_alive:
            self.state.ended = True
            self.state.winner = "ally"
            self.state.logs.append(
                f"🏆 敌方舰队全灭！己方胜利！(耗时{self.state.time:.1f}s)"
            )
            return True
        return False

    def run_until_end(self, max_time: float = 300.0, dt: float = 0.1) -> BattleState:
        while not self.state.ended and self.state.time < max_time:
            if self.simulate_tick(dt):
                break
        if not self.state.ended:
            self.state.logs.append(
                f"⏰ 达到最大模拟时间 {max_time}s，战斗结束"
            )
        return self.state


# ==================== 测试 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("  战斗引擎 v2.0 - 测试运行")
    print("=" * 60)

    # 创建测试舰队
    ally_ships = [
        ShipInstance(
            id="ally_tank_0", name="光追级", ship_type="cruiser",
            position=ShipPosition.FRONT, max_hp=85000, current_hp=85000,
            physical_armor=45, energy_armor_pct=10, evasion=0.05,
            side="ally", is_escort=True,
            weapons=[],  # 随后填充
            sub_systems={
                "main_weapon": 85000 * 0.12,
                "hangar": 85000 * 0.10,
                "command": 85000 * 0.08,
                "propulsion": 85000 * 0.06,
            },
        ),
        ShipInstance(
            id="ally_dps_0", name="卡利斯托级", ship_type="cruiser",
            position=ShipPosition.BACK, max_hp=78000, current_hp=78000,
            physical_armor=40, energy_armor_pct=8, evasion=0.03,
            side="ally", is_escorted=True,
            weapons=[], sub_systems={},
        ),
    ]

    enemy_ships = [
        ShipInstance(
            id="enemy_tank_0", name="爱奥级", ship_type="cruiser",
            position=ShipPosition.FRONT, max_hp=95000, current_hp=95000,
            physical_armor=55, energy_armor_pct=6, evasion=0.02,
            side="enemy", is_escort=True,
            weapons=[], sub_systems={},
        ),
    ]

    # 添加基础武器
    from .formulas import create_basic_weapon  # 简化：手动创建
    ally_ships[0].weapons = [
        Weapon("对舰主炮", WeaponType.DIRECT_FIRE, DamageType.PHYSICAL,
               350, attacks=2, ammo=2, cooldown=5.0, lock_time=2.0,
               can_crit=True, hit_rate=0.75)
    ]
    ally_ships[1].weapons = [
        Weapon("导弹发射器", WeaponType.PROJECTILE, DamageType.PHYSICAL,
               500, attacks=1, ammo=4, cooldown=12.0, lock_time=4.0,
               can_crit=True, hit_rate=0.70)
    ]
    enemy_ships[0].weapons = [
        Weapon("重型主炮", WeaponType.DIRECT_FIRE, DamageType.PHYSICAL,
               450, attacks=2, ammo=1, cooldown=6.0, lock_time=3.0,
               can_crit=True, hit_rate=0.65)
    ]

    for ship in ally_ships + enemy_ships:
        for sys_name in SYSTEM_HP_RATIOS:
            if sys_name not in ship.sub_systems:
                ship.sub_systems[sys_name] = ship.max_hp * SYSTEM_HP_RATIOS[sys_name]
                ship.sub_system_max_hp[sys_name] = ship.max_hp * SYSTEM_HP_RATIOS[sys_name]
                ship.sub_system_repair_count[sys_name] = 0

    state = BattleState(
        ally_ships=ally_ships, enemy_ships=enemy_ships,
        logs=["⚔ 战斗引擎 v2.0 测试开始！"],
    )

    sim = BattleSimulator(state)
    result = sim.run_until_end(max_time=60)

    print(f"结果: {result.winner}胜利 | 用时: {result.time:.1f}s")
    print(f"己方伤害: {result.total_ally_damage:.0f} | 损失: {result.ally_ships_lost}艘")
    print(f"敌方伤害: {result.total_enemy_damage:.0f} | 损失: {result.enemy_ships_lost}艘")
    print(f"日志条目: {len(result.logs)}")
