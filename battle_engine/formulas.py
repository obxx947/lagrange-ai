# -*- coding: utf-8 -*-
"""
战斗公式模块
------------
基于《无尽的拉格朗日》战斗机制文档的完整数学公式实现。

包含：
1. 伤害计算（能量/实弹双体系）
2. 命中率计算（含轰炸距离修正、per-target命中、闪避）
3. 拦截率计算（三层叠加 + 反拦截）
4. 暴击伤害计算
5. 冷却时间计算
6. 锁定时间计算
7. 系统伤害计算
8. 维修量计算
9. 分伤机制计算
10. DPS预估
"""

import math
from typing import List, Tuple, Optional, Dict

# ==================== 全局常量 ====================

TUNING_COEFFICIENT = 1.3          # 全局调校系数
MIN_DAMAGE_RATIO = 0.10           # 实弹未穿透保底10%
CRIT_BASE_RATE = 0.15             # 基础暴击率15%
SYSTEM_DAMAGE_CHANCE = 0.10       # 每次命中10%概率触发系统伤害
PLUTUS_DAMAGE_REDUCTION = 0.30    # 普卢托斯之盾旗舰30%减伤
DAMAGE_DISTRIBUTION_DIVISOR = 2.5 # 分伤机制除数
REPAIR_ARMOR_BONUS = 0.0025       # 1点物理装甲 = 0.25%维修加成
REPAIR_MAX_BONUS = 1.5            # 维修加成上限150%
BOMB_DISTANCE_BASE = 15.0         # 轰炸距离基准（吉米）
BOMB_DISTANCE_PENALTY = 0.02      # 每吉米命中修正2%
FLIGHT_TIME_PER_JIMI = 2.0        # 每吉米飞行时间2秒
COUNTER_AA_SHIP_HIT = 0.15        # 反击防空舰船基础命中15%
COUNTER_AA_AIRCRAFT_HIT = 0.60    # 反击防空战机基础命中60%
SYSTEM_DAMAGE_COEFFICIENTS = {     # 系统伤害系数（按武器）
    "standard": 1.25,
    "enhanced": 1.5,
    "heavy": 3.0,
}
SYSTEM_HP_RATIOS = {              # 系统HP占舰船总HP比例
    "main_weapon": 0.12,
    "hangar": 0.10,
    "command": 0.08,
    "propulsion": 0.06,
}
SYSTEM_REPAIR_LIMITS = {          # 系统修理上限
    "main_weapon": 2,
    "hangar": 2,
    "command": 3,
    "propulsion": 0,              # 推进系统战斗中不可修理
}
SYSTEM_TARGET_EFFICIENCY = {      # 系统瞄准效率
    "high": 0.60,
    "medium": 0.40,
    "low": 0.20,
}
CARRIER_HANGAR_BONUSES = {        # 不同航母的机库加成
    "CV3000": {"speed_bonus": 0.15, "dmg_bonus": 0.10, "lock_bonus": 0.10},
    "太阳鲸": {"speed_bonus": 0.10, "dmg_bonus": 0.15, "lock_bonus": 0.05},
    "南十字星": {"speed_bonus": 0.20, "dmg_bonus": 0.05, "lock_bonus": 0.15},
    "永恒苍穹": {"speed_bonus": 0.12, "dmg_bonus": 0.12, "lock_bonus": 0.12},
    "天枢": {"speed_bonus": 0.05, "dmg_bonus": 0.08, "lock_bonus": 0.20},
}


# ==================== 伤害计算 ====================

def calc_energy_damage(
    base_dmg: float,
    target_energy_armor_pct: float,
    dmg_bonus: float = 0.0,
    strategy_coeff: float = 1.0,
    system_dmg_coeff: float = 1.0,
) -> float:
    """
    能量伤害计算

    一次完整能量射击的伤害公式:
      final = base_dmg × (1 + dmg_bonus - target_shield%)
               × TUNING_COEFFICIENT × strategy_coeff × system_dmg_coeff

    能量抗性达到100%时完全免疫能量伤害。

    Args:
        base_dmg: 武器基础单发伤害
        target_energy_armor_pct: 目标能量护盾百分比 (0-100)
        dmg_bonus: 攻击方伤害加成（小数，如0.15表示15%加成）
        strategy_coeff: 策略技能系数 (默认1.0)
        system_dmg_coeff: 系统伤害系数 (1.25/1.5/3.0，默认1.0)

    Returns:
        最终能量伤害值
    """
    if target_energy_armor_pct >= 100.0:
        return 0.0

    effective_mult = 1.0 + dmg_bonus - (target_energy_armor_pct / 100.0)
    final_dmg = base_dmg * effective_mult * TUNING_COEFFICIENT * strategy_coeff * system_dmg_coeff
    return max(0.0, final_dmg)


def calc_physical_damage(
    base_dmg: float,
    target_armor: float,
    dmg_bonus: float = 0.0,
    strategy_coeff: float = 1.0,
    system_dmg_coeff: float = 1.0,
    armor_penetration: float = 0.0,
) -> float:
    """
    实弹伤害计算

    一次完整实弹射击的伤害公式:
      raw = base_dmg × (1 + dmg_bonus) - (target_armor - armor_penetration)
      final = max(raw, base_dmg × MIN_DAMAGE_RATIO)
              × TUNING_COEFFICIENT × strategy_coeff × system_dmg_coeff

    当装甲完全抵消伤害时，保底造成基础伤害10%的伤害。

    Args:
        base_dmg: 武器基础单发伤害
        target_armor: 目标物理装甲值
        dmg_bonus: 攻击方伤害加成（小数）
        strategy_coeff: 策略技能系数
        system_dmg_coeff: 系统伤害系数
        armor_penetration: 穿甲值

    Returns:
        最终实弹伤害值
    """
    effective_armor = max(0.0, target_armor - armor_penetration)
    raw_dmg = base_dmg * (1.0 + dmg_bonus) - effective_armor

    if raw_dmg <= 0:
        raw_dmg = base_dmg * MIN_DAMAGE_RATIO  # 10%保底

    return max(0.0, raw_dmg * TUNING_COEFFICIENT * strategy_coeff * system_dmg_coeff)


def calc_system_damage(
    base_dmg: float,
    system_dmg_coeff: float,
    target_type: str,
    target_armor: float = 0,
    target_energy_armor_pct: float = 0,
    is_energy: bool = False,
) -> float:
    """
    系统结构伤害计算（用于子系统HP扣除）

    系统伤害 = 武器对结构伤害 × 系统伤害系数

    Args:
        base_dmg: 基础伤害
        system_dmg_coeff: 系统伤害系数 (1.25/1.5/3.0)
        target_type: 目标类型
        target_armor: 目标装甲
        target_energy_armor_pct: 目标能量护盾百分比
        is_energy: 是否能量伤害

    Returns:
        对子系统的HP伤害
    """
    if is_energy:
        structural_dmg = calc_energy_damage(
            base_dmg, target_energy_armor_pct, dmg_bonus=0, strategy_coeff=1.0
        )
    else:
        structural_dmg = calc_physical_damage(
            base_dmg, target_armor, dmg_bonus=0, strategy_coeff=1.0
        )
    return structural_dmg * system_dmg_coeff


# ==================== 命中率计算 ====================

def calc_hit_chance(
    base_hit: float,
    lock_efficiency: float = 1.0,
    evasion: float = 0.0,
    bomb_distance: float = 15.0,
    hit_bonus: float = 0.0,
    target_evasion: float = 0.0,
) -> float:
    """
    命中率计算

    基础公式:
      hit = base_hit × (1 + hit_bonus - target_evasion) × lock_efficiency

    轰炸距离修正:
      >15吉米: 每吉米 -2% 命中
      <15吉米: 每吉米 +2% 命中

    最终命中限制在 [0.01, 0.99] 区间。

    Args:
        base_hit: 基础命中率 (0-1)
        lock_efficiency: 锁定效率 (0-1)
        evasion: 保留参数（向后兼容）
        bomb_distance: 轰炸距离（吉米）
        hit_bonus: 命中率加成
        target_evasion: 目标闪避率

    Returns:
        最终命中概率 (0.01-0.99)
    """
    effective_evasion = evasion if evasion > 0 else target_evasion
    hit = base_hit * (1.0 + hit_bonus - effective_evasion) * lock_efficiency

    # 轰炸距离修正
    if bomb_distance > BOMB_DISTANCE_BASE:
        hit -= (bomb_distance - BOMB_DISTANCE_BASE) * BOMB_DISTANCE_PENALTY
    else:
        hit += (BOMB_DISTANCE_BASE - bomb_distance) * BOMB_DISTANCE_PENALTY

    return max(0.01, min(0.99, hit))


def calc_per_target_hit(
    base_hit: float,
    target_types: List[str],
    ship_type: str,
    ship_size: str,
    hit_min: float = 0.0,
    hit_max: float = 1.0,
) -> float:
    """
    Per-target命中率计算

    轻武器打小船命中高，重武器打大船命中高。
    命中率在 hit_min ~ hit_max 范围内按目标类型插值。

    Args:
        base_hit: 武器基础命中率
        target_types: 武器擅长打击的目标类型列表
        ship_type: 目标舰船类型
        ship_size: 目标舰船尺寸 (small/large/aircraft)
        hit_min: 最低命中率
        hit_max: 最高命中率

    Returns:
        对该目标类型的命中率
    """
    if ship_type in target_types:
        return max(base_hit, hit_max * base_hit)

    # 尺寸匹配：轻武器 -> 小目标命中高，重武器 -> 大目标命中高
    size_bonus = {"small": -0.05, "large": 0.05, "aircraft": -0.10}
    base = base_hit + size_bonus.get(ship_size, 0.0)
    return max(hit_min, min(hit_max, base))


# ==================== 拦截率计算 ====================

def calc_intercept_rate(
    self_rate: float,
    same_row_rates: List[float],
    global_rates: List[float],
    anti_intercept: float = 0.0,
) -> float:
    """
    拦截率计算（三层叠加 + 反拦截）

    基础公式:
      intercept = 1 - (1 - self) × Π(1 - same_row_i) × Π(1 - global_j)

    反拦截修正:
      final_intercept = intercept × (1 - anti_intercept)

    Args:
        self_rate: 自身拦截率
        same_row_rates: 同排所有舰船的拦截率列表
        global_rates: 全局拦截率列表
        anti_intercept: 反拦截系数 (0-1)

    Returns:
        最终拦截概率 (0-1)
    """
    total = 1.0 - self_rate
    for r in same_row_rates:
        total *= (1.0 - r)
    for r in global_rates:
        total *= (1.0 - r)

    intercept = 1.0 - total
    # 反拦截修正
    intercept *= (1.0 - anti_intercept)
    return max(0.0, min(1.0, intercept))


def calc_multi_ship_intercept(rates: List[float]) -> float:
    """
    多舰拦截叠加计算

    公式: 1 - Π(1 - rate_i)^n_i
    其中 n_i 是具有相同拦截率的舰船数量

    Args:
        rates: 所有拦截率列表

    Returns:
        多舰总拦截率
    """
    total = 1.0
    for rate in rates:
        total *= (1.0 - rate)
    return max(0.0, min(1.0, 1.0 - total))


# ==================== 暴击计算 ====================

def calc_crit_damage(
    base_crit_dmg: float = 1.5,
    crit_dmg_bonus: float = 0.0,
    target_crit_reduction: float = 0.0,
) -> float:
    """
    暴击伤害计算

    公式: crit_mult = base_crit_dmg × (1 + crit_dmg_bonus - target_crit_reduction)

    Args:
        base_crit_dmg: 基础暴击倍率 (默认1.5)
        crit_dmg_bonus: 暴击伤害加成（小数）
        target_crit_reduction: 目标暴击伤害减免（小数）

    Returns:
        暴击倍率
    """
    return max(1.0, base_crit_dmg * (1.0 + crit_dmg_bonus - target_crit_reduction))


def calc_crit_rate(
    base_crit_rate: float = CRIT_BASE_RATE,
    crit_rate_bonus: float = 0.0,
) -> float:
    """
    暴击率计算

    Args:
        base_crit_rate: 基础暴击率
        crit_rate_bonus: 暴击率加成

    Returns:
        最终暴击率 (0-1)
    """
    return min(0.95, max(0.0, base_crit_rate + crit_rate_bonus))


# ==================== 冷却和锁定时间 ====================

def calc_final_cooldown(
    base_cooldown: float,
    cooldown_reduction: float = 0.0,
    strategy_coeff: float = 1.0,
) -> float:
    """
    最终冷却时间计算

    公式: final_cd = base_cd × (1 - cd_reduction) × strategy_coeff
    最小冷却时间 0.5秒

    Args:
        base_cooldown: 基础冷却时间（秒）
        cooldown_reduction: 冷却缩减（小数，如0.15表示15%缩减）
        strategy_coeff: 策略技能冷却系数

    Returns:
        最终冷却时间（秒）
    """
    return max(0.5, base_cooldown * (1.0 - cooldown_reduction) * strategy_coeff)


def calc_final_lock_time(
    base_lock_time: float,
    lock_reduction: float = 0.0,
    enemy_lock_extension: float = 0.0,
) -> float:
    """
    最终锁定时间计算

    公式: lock = base_lock × (1 - lock_reduction + enemy_lock_extension)
    最小锁定时间 0.2秒

    Args:
        base_lock_time: 基础锁定时间（秒）
        lock_reduction: 锁定缩减（小数）
        enemy_lock_extension: 敌方锁定延长（小数）

    Returns:
        最终锁定时间（秒）
    """
    return max(0.2, base_lock_time * (1.0 - lock_reduction + enemy_lock_extension))


# ==================== 维修计算 ====================

def calc_repair_amount(
    repair_dpm: float,
    target_physical_armor: float,
    dt: float,
    repair_bonus: float = 0.0,
) -> float:
    """
    维修量计算

    公式: repair_per_sec = (repair_dpm / 60) × (1 + target_armor × 0.0025) × (1 + repair_bonus)
    上限: repair_dpm / 60 × 2.5 (即150%)

    Args:
        repair_dpm: 维修武器每分钟维修量
        target_physical_armor: 目标舰船物理装甲值
        dt: 时间步长（秒）
        repair_bonus: 维修加成（小数）

    Returns:
        本次维修量
    """
    base_per_sec = repair_dpm / 60.0
    armor_bonus = 1.0 + target_physical_armor * REPAIR_ARMOR_BONUS
    armor_bonus = min(armor_bonus, REPAIR_MAX_BONUS)  # 上限150%
    repair_per_sec = base_per_sec * armor_bonus * (1.0 + repair_bonus)
    return repair_per_sec * dt


# ==================== 分伤机制 ====================

def calc_attackable_targets(total_targets: int) -> int:
    """
    可攻击目标数计算（分伤机制）

    公式: attackable = floor(total_targets / 2.5)

    当多个友军舰船都可以攻击同一个敌人时，伤害被分配到
    有限的目标上（而非所有目标）。

    Args:
        total_targets: 总敌舰数量

    Returns:
        实际可被攻击的目标数
    """
    return max(1, int(math.floor(total_targets / DAMAGE_DISTRIBUTION_DIVISOR)))


def distribute_damage_targets(
    attackers: int,
    total_targets: int,
) -> List[int]:
    """
    伤害分配目标映射

    将攻击者的火力分配到有限的目标上，攻击序列丰富的舰船
    与目标少的舰船协调分配。

    Args:
        attackers: 攻击方舰船数量
        total_targets: 敌方舰船总数

    Returns:
        每艘攻击舰可攻击的目标索引列表
    """
    attackable = calc_attackable_targets(total_targets)
    distribution = []
    for i in range(attackers):
        distribution.append(i % attackable)
    return distribution


# ==================== DPS预估 ====================

def estimate_weapon_dps(
    single_dmg: float,
    attacks: int,
    ammo: int,
    cooldown: float,
    lock_time: float,
    attack_duration: float,
    hit_rate: float = 0.7,
    crit_rate: float = 0.15,
    crit_dmg: float = 1.5,
    is_energy: bool = False,
    target_armor: float = 20,
    target_energy_shield: float = 10,
) -> float:
    """
    武器DPS预估

    一轮攻击时间 = lock_time + cooldown (lock和cooldown可并发)
    一轮伤害 = total_shots × single_shot × hit_rate × (1 + crit_rate × (crit_dmg - 1))
    秒平均DPS = 一轮伤害 / 一轮时间

    Args:
        single_dmg: 单发基础伤害
        attacks: 攻击轮次
        ammo: 每轮弹药
        cooldown: 冷却时间
        lock_time: 锁定时间
        attack_duration: 攻击持续时间
        hit_rate: 命中率
        crit_rate: 暴击率
        crit_dmg: 暴击倍率
        is_energy: 是否能量伤害
        target_armor: 目标装甲值（实弹用）
        target_energy_shield: 目标护盾%（能量用）

    Returns:
        预估每秒平均伤害
    """
    total_shots = attacks * ammo
    # 暴击期望倍率
    crit_mult = 1.0 + crit_rate * (crit_dmg - 1.0)

    # 单发有效伤害
    if is_energy:
        effective_dmg = calc_energy_damage(single_dmg, target_energy_shield)
    else:
        effective_dmg = calc_physical_damage(single_dmg, target_armor)

    # 一轮总伤害
    round_dmg = total_shots * effective_dmg * hit_rate * crit_mult
    # 一轮时间（lock和cooldown取最大值，因为可以并发）
    round_time = max(lock_time, cooldown) + attack_duration

    if round_time <= 0:
        return round_dmg

    return round_dmg / round_time


def estimate_fleet_battle_duration(
    ally_total_hp: float,
    enemy_total_hp: float,
    ally_total_dps: float,
    enemy_total_dps: float,
) -> float:
    """
    预估舰队战斗持续时间

    基于双方总HP和DPS的简单估算模型。

    Args:
        ally_total_hp: 己方舰队总HP
        enemy_total_hp: 敌方舰队总HP
        ally_total_dps: 己方舰队总DPS
        enemy_total_dps: 敌方舰队总DPS

    Returns:
        预估战斗时间（秒）
    """
    if ally_total_dps <= 0 or enemy_total_dps <= 0:
        return float("inf")

    ally_time_to_die = ally_total_hp / enemy_total_dps if enemy_total_dps > 0 else float("inf")
    enemy_time_to_die = enemy_total_hp / ally_total_dps if ally_total_dps > 0 else float("inf")

    return min(ally_time_to_die, enemy_time_to_die)


# ==================== 机库加成计算 ====================

def calc_carrier_hangar_bonus(
    carrier_name: str,
    bonus_type: str,
) -> float:
    """
    计算航母机库加成

    不同航母对舰载机的加成不同：
    - CV3000: 速度+15%, 伤害+10%, 锁定+10%
    - 太阳鲸: 速度+10%, 伤害+15%, 锁定+5%
    - 南十字星: 速度+20%, 伤害+5%, 锁定+15%
    - 永恒苍穹: 速度+12%, 伤害+12%, 锁定+12%
    - 天枢: 速度+5%, 伤害+8%, 锁定+20%

    Args:
        carrier_name: 航母名称
        bonus_type: 加成类型 (speed_bonus/dmg_bonus/lock_bonus)

    Returns:
        加成值（小数）
    """
    for key, bonuses in CARRIER_HANGAR_BONUSES.items():
        if key in carrier_name:
            return bonuses.get(bonus_type, 0.0)
    return 0.0


# ==================== 飞行时间计算 ====================

def calc_flight_time(bomb_distance: float) -> float:
    """
    舰载机飞行时间计算

    公式: flight_time = bomb_distance × 2秒/吉米

    Args:
        bomb_distance: 轰炸距离（吉米）

    Returns:
        飞行时间（秒）
    """
    return bomb_distance * FLIGHT_TIME_PER_JIMI


def calc_bomb_distance_hit_modifier(bomb_distance: float) -> float:
    """
    轰炸距离命中修正

    >15吉米: 每吉米 -2% 命中
    <15吉米: 每吉米 +2% 命中

    Args:
        bomb_distance: 轰炸距离

    Returns:
        命中修正值（小数，可正可负）
    """
    if bomb_distance > BOMB_DISTANCE_BASE:
        return -(bomb_distance - BOMB_DISTANCE_BASE) * BOMB_DISTANCE_PENALTY
    else:
        return (BOMB_DISTANCE_BASE - bomb_distance) * BOMB_DISTANCE_PENALTY


# ==================== 便捷函数 ====================

def clamp(value: float, min_val: float, max_val: float) -> float:
    """将值限制在 [min_val, max_val] 范围内"""
    return max(min_val, min(max_val, value))


def roll_probability(prob: float) -> bool:
    """以概率prob返回True"""
    import random
    return random.random() < prob
