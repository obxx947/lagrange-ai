# -*- coding: utf-8 -*-
"""
工厂函数和工具函数
-----------------
从舰船数据库JSON创建战斗模拟实例，以及各种辅助工具。
"""

import json
import random
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from .engine import (
    Weapon, ShipInstance, BattleState, BattleSimulator,
    WeaponType, DamageType, ShipPosition, BattleMode, SystemType,
)
from .aircraft import (
    AircraftManager, AircraftUnit, AircraftWeapon,
    AircraftState, FlightMode,
)
from .antiair import (
    AntiairSystem, AirDefenseBattery, AAWeapon, AAType,
)
from .strategy import StrategyManager, StrategySkill
from .formulas import (
    SYSTEM_HP_RATIOS, SYSTEM_REPAIR_LIMITS,
    CARRIER_HANGAR_BONUSES,
)


def create_ship_from_db(
    ship_data: dict,
    count: int = 1,
    side: str = "ally",
) -> List[ShipInstance]:
    """
    从舰船数据库JSON条目创建战斗实例。

    Args:
        ship_data: 舰船数据库条目（来自ship_database.json）
        count: 创建数量
        side: 阵营 (ally/enemy)

    Returns:
        舰船战斗实例列表
    """
    instances = []
    for i in range(count):
        pos_str = ship_data.get("position", "中排")
        pos_map = {
            "前排": ShipPosition.FRONT,
            "中排": ShipPosition.MID,
            "后排": ShipPosition.BACK,
            "aircraft": ShipPosition.AIR,
        }
        position = pos_map.get(pos_str, ShipPosition.MID)

        # 初始化子系统HP
        max_hp = float(ship_data.get("hp", 10000))
        sub_systems = {}
        sub_system_max_hp = {}
        for sys_name, ratio in SYSTEM_HP_RATIOS.items():
            sub_systems[sys_name] = max_hp * ratio
            sub_system_max_hp[sys_name] = max_hp * ratio

        instance = ShipInstance(
            id=f"{ship_data.get('id', 'unknown')}_{i}",
            name=ship_data.get("name", "未知舰船"),
            ship_type=ship_data.get("type", "unknown"),
            position=position,
            max_hp=max_hp,
            current_hp=max_hp,
            physical_armor=float(ship_data.get("physicalArmor", 10)),
            energy_armor_pct=float(ship_data.get("energyArmor", 5)),
            evasion=float(ship_data.get("evasion", 0.0)),
            is_super_capital=ship_data.get("size") == "large",
            is_carrier=ship_data.get("isCarrier", False),
            side=side,
            sub_systems=sub_systems,
            sub_system_max_hp=sub_system_max_hp,
        )

        # 提取武器
        weapons = _extract_weapons_from_db(ship_data)
        instance.weapons = weapons

        # 舰载机信息
        if ship_data.get("isCarrier"):
            instance.aircraft_ids = []
            carrier_name = ship_data.get("name", "")
            for key, bonuses in CARRIER_HANGAR_BONUSES.items():
                if key in carrier_name:
                    instance.carrier_bonuses = bonuses
                    break

        instances.append(instance)

    return instances


def _extract_weapons_from_db(ship_data: dict) -> List[Weapon]:
    """从舰船数据库条目中提取所有武器"""
    weapons = []
    modules = ship_data.get("modules", {})

    for mod_key, module in modules.items():
        if module.get("type") != "weapon":
            continue

        for wdata in module.get("weapons", []):
            wtype_str = wdata.get("weaponType", "direct")
            dtype_str = wdata.get("dmgType", "physical")

            try:
                wtype = WeaponType(wtype_str)
            except ValueError:
                wtype = WeaponType.DIRECT_FIRE

            try:
                dtype = DamageType(dtype_str)
            except ValueError:
                dtype = DamageType.PHYSICAL

            # 防空类型解析
            aa_type = None
            aa_str = wdata.get("antiAirType", "")
            if "counter" in aa_str:
                aa_type = AAType.COUNTER
            elif "area" in aa_str:
                aa_type = AAType.AREA
            elif "active" in aa_str:
                aa_type = AAType.ACTIVE

            # 系统目标
            sub_targets = {}
            st = wdata.get("subSystemTargets", {})
            if isinstance(st, dict):
                sub_targets = st

            weapon = Weapon(
                name=wdata.get("name", "未知武器"),
                weapon_type=wtype,
                damage_type=dtype,
                single_damage=float(wdata.get("singleDmg", 100)),
                attacks=int(wdata.get("attacks", 1)),
                ammo=int(wdata.get("ammo", 1)),
                attack_duration=float(wdata.get("atkDuration", 0)),
                lock_time=float(wdata.get("lockTime", 2.0)),
                cooldown=float(wdata.get("cooldown", 4.0)),
                priority=wdata.get("priority", "random"),
                can_crit=wdata.get("crit", False),
                hit_rate=float(wdata.get("hitMin", 70)) / 100.0 if "targets" in wdata else 0.7,
                anti_air_type=aa_type,
                intercept_rate=float(wdata.get("interceptRate", 0)),
                sub_system_targets=sub_targets,
                repair_dpm=float(wdata.get("dpm", {}).get("antiAir", 0) if wdata.get("dpm", {}).get("antiAir", 0) > 0 and "repair" in wdata.get("name", "").lower() else 0),
            )
            weapons.append(weapon)

    return weapons


def create_basic_weapon(
    name: str = "标准舰炮",
    dmg: float = 200,
    wtype: WeaponType = WeaponType.DIRECT_FIRE,
    dtype: DamageType = DamageType.PHYSICAL,
) -> Weapon:
    """创建基础武器（用于快速测试）"""
    return Weapon(
        name=name,
        weapon_type=wtype,
        damage_type=dtype,
        single_damage=dmg,
        attacks=2,
        ammo=2,
        attack_duration=1.0,
        lock_time=2.0,
        cooldown=4.0,
        can_crit=True,
        hit_rate=0.75,
    )


def create_aa_weapon(
    name: str = "防空炮",
    dmg: float = 80,
    aa_type: AAType = AAType.COUNTER,
    base_hit: float = 0.15,
) -> AAWeapon:
    """创建防空武器"""
    return AAWeapon(
        name=name,
        aa_type=aa_type,
        damage_type="physical",
        single_damage=dmg,
        base_hit_rate=base_hit,
    )


def load_ship_database(db_path: str = "lagrange_docs/ship_database.json") -> List[dict]:
    """加载舰船数据库"""
    from pathlib import Path
    path = Path(db_path)
    if not path.exists():
        # 尝试相对路径
        path = Path(__file__).parent.parent / "lagrange_docs" / "ship_database.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def build_battle_from_fleet_configs(
    ally_fleet: List[dict],
    enemy_fleet: List[dict],
    mode: str = "escort",
    bomb_distance: float = 15.0,
) -> BattleState:
    """
    从舰队配置构建完整战斗状态。

    Args:
        ally_fleet: 己方舰队配置 [{"ship_id": "CAS066-A", "count": 5}, ...]
        enemy_fleet: 敌方舰队配置
        mode: 战斗模式 ("escort" / "bomb")
        bomb_distance: 轰炸距离

    Returns:
        BattleState 实例
    """
    db = load_ship_database()
    db_map = {s["id"]: s for s in db}

    ally_ships = []
    enemy_ships = []

    for entry in ally_fleet:
        ship_id = entry.get("ship_id", "")
        count = entry.get("count", 1)
        if ship_id in db_map:
            ally_ships.extend(create_ship_from_db(db_map[ship_id], count, "ally"))

    for entry in enemy_fleet:
        ship_id = entry.get("ship_id", "")
        count = entry.get("count", 1)
        if ship_id in db_map:
            enemy_ships.extend(create_ship_from_db(db_map[ship_id], count, "enemy"))

    battle_mode = BattleMode.ESCORT if mode == "escort" else BattleMode.BOMB

    return BattleState(
        ally_ships=ally_ships,
        enemy_ships=enemy_ships,
        mode=battle_mode,
        bomb_distance=bomb_distance,
        logs=[f"⚔ 战斗开始 | {len(ally_ships)} vs {len(enemy_ships)} | 模式: {mode}"],
    )


def quick_simulate(
    ally_ships: List[ShipInstance],
    enemy_ships: List[ShipInstance],
    max_time: float = 120.0,
) -> Dict:
    """快速模拟并返回结果摘要"""
    state = BattleState(
        ally_ships=ally_ships,
        enemy_ships=enemy_ships,
        logs=["⚔ 快速模拟开始"],
    )
    sim = BattleSimulator(state)
    result = sim.run_until_end(max_time=max_time)

    return {
        "winner": result.winner,
        "duration": result.time,
        "ally_damage_total": result.total_ally_damage,
        "enemy_damage_total": result.total_enemy_damage,
        "ally_ships_lost": result.ally_ships_lost,
        "enemy_ships_lost": result.enemy_ships_lost,
        "total_logs": len(result.logs),
    }
