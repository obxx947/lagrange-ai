# -*- coding: utf-8 -*-
"""
拉格朗日智能体 - 战斗引擎模块

完整的无尽拉格朗日战斗模拟系统，包含：
- 舰船对舰船直射/投射武器战斗
- 舰载机独立/往复空战
- 防空（反击/区域/主动）
- 三层拦截 + 反拦截
- 策略技能系统
- 闪避 + per-target命中率
- 系统数值HP + 修理上限
- 分伤机制
- 轰炸/护航双模式
- 旗舰效果
"""

from .engine import BattleSimulator, BattleState, ShipInstance, Weapon
from .formulas import (
    calc_energy_damage, calc_physical_damage,
    calc_hit_chance, calc_intercept_rate,
    calc_crit_damage, calc_final_cooldown
)
from .aircraft import AircraftManager, AircraftState, FlightMode
from .antiair import AntiairSystem, AAType
from .strategy import StrategyManager, StrategySkill
from .factory import create_ship_from_db, create_basic_weapon

__all__ = [
    "BattleSimulator", "BattleState", "ShipInstance", "Weapon",
    "calc_energy_damage", "calc_physical_damage",
    "calc_hit_chance", "calc_intercept_rate",
    "calc_crit_damage", "calc_final_cooldown",
    "AircraftManager", "AircraftState", "FlightMode",
    "AntiairSystem", "AAType",
    "StrategyManager", "StrategySkill",
    "create_ship_from_db", "create_basic_weapon",
]
