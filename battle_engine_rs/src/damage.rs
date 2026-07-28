//! 伤害计算模块
//!
//! 实现《无尽的拉格朗日》完整伤害计算公式。
//! 支持能量/实弹双体系、系统伤害、暴击、DPS预估等。

use crate::{TUNING_COEFFICIENT, MIN_DAMAGE_RATIO, CRIT_BASE_RATE};

/// 武器伤害类型
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum DamageType {
    Physical,
    Energy,
}

/// 计算能量伤害
///
/// 公式: base_dmg * (1 + dmg_bonus - target_shield_pct/100) * TUNING * strategy_coeff
///
/// # 参数
/// - `base_dmg`: 武器基础单发伤害
/// - `target_energy_armor_pct`: 目标能量护盾百分比 (0-100)
/// - `dmg_bonus`: 伤害加成 (小数, 0.15 = 15%)
/// - `strategy_coeff`: 策略技能系数
///
/// # 返回
/// 最终能量伤害值。目标护盾≥100%时返回0.0
///
/// # 示例
/// ```
/// let dmg = calc_energy_damage(500.0, 10.0, 0.15, 1.0);
/// assert!(dmg > 0.0);
/// ```
pub fn calc_energy_damage(
    base_dmg: f64,
    target_energy_armor_pct: f64,
    dmg_bonus: f64,
    strategy_coeff: f64,
) -> f64 {
    // 100%能量抗性 = 完全免疫
    if target_energy_armor_pct >= 100.0 {
        return 0.0;
    }

    let effective_mult = 1.0 + dmg_bonus - (target_energy_armor_pct / 100.0);
    let final_dmg = base_dmg * effective_mult * TUNING_COEFFICIENT * strategy_coeff;
    final_dmg.max(0.0)
}

/// 计算实弹伤害
///
/// 公式: max(base_dmg * (1 + dmg_bonus) - target_armor, base_dmg * 0.1)
///       * TUNING * strategy_coeff
///
/// 当装甲完全抵消伤害时，保底造成基础伤害10%的伤害。
///
/// # 示例
/// ```
/// // 正常伤害
/// let dmg = calc_physical_damage(300.0, 20.0, 0.0, 1.0, 0.0);
/// // 装甲太厚，触发保底
/// let min_dmg = calc_physical_damage(100.0, 500.0, 0.0, 1.0, 0.0);
/// assert!(min_dmg >= 100.0 * 0.1);
/// ```
pub fn calc_physical_damage(
    base_dmg: f64,
    target_armor: f64,
    dmg_bonus: f64,
    strategy_coeff: f64,
    armor_penetration: f64,
) -> f64 {
    let effective_armor = (target_armor - armor_penetration).max(0.0);
    let raw_dmg = base_dmg * (1.0 + dmg_bonus) - effective_armor;

    let effective_raw = if raw_dmg <= 0.0 {
        base_dmg * MIN_DAMAGE_RATIO // 10%保底
    } else {
        raw_dmg
    };

    (effective_raw * TUNING_COEFFICIENT * strategy_coeff).max(0.0)
}

/// 计算暴击伤害倍率
///
/// 公式: base_crit_dmg * (1 + crit_dmg_bonus - target_crit_reduction)
pub fn calc_crit_damage(
    base_crit_dmg: f64,
    crit_dmg_bonus: f64,
    target_crit_reduction: f64,
) -> f64 {
    let mult = 1.0 + crit_dmg_bonus - target_crit_reduction;
    (base_crit_dmg * mult).max(1.0)
}

/// 计算暴击率
pub fn calc_crit_rate(base_crit_rate: f64, crit_rate_bonus: f64) -> f64 {
    (base_crit_rate + crit_rate_bonus).max(0.0).min(0.95)
}

/// 计算最终冷却时间
///
/// 公式: base_cd * (1 - cd_reduction) * strategy_coeff
/// 最小冷却: 0.5秒
pub fn calc_final_cooldown(
    base_cooldown: f64,
    cooldown_reduction: f64,
    strategy_coeff: f64,
) -> f64 {
    let cd = base_cooldown * (1.0 - cooldown_reduction) * strategy_coeff;
    cd.max(0.5)
}

/// 预估武器DPS
///
/// 考虑命中率、暴击率、伤害类型、目标防御属性的综合DPS估算。
///
/// # 参数
/// - `single_dmg`: 单发基础伤害
/// - `attacks`: 攻击轮次
/// - `ammo`: 每轮弹药数
/// - `cooldown`: 冷却时间(秒)
/// - `lock_time`: 锁定时间(秒)
/// - `hit_rate`: 命中率(0-1)
/// - `crit_rate`: 暴击率(0-1)
/// - `crit_dmg`: 暴击倍率
/// - `is_energy`: 是否能量伤害
/// - `target_armor`: 目标装甲(实弹用)
/// - `target_shield`: 目标护盾%(能量用)
///
/// # 返回
/// 每秒平均伤害估值
pub fn estimate_dps(
    single_dmg: f64,
    attacks: usize,
    ammo: usize,
    cooldown: f64,
    lock_time: f64,
    hit_rate: f64,
    crit_rate: f64,
    crit_dmg: f64,
    is_energy: bool,
    target_armor: f64,
    target_shield: f64,
) -> f64 {
    let total_shots = (attacks * ammo) as f64;

    // 暴击期望倍率
    let crit_mult = 1.0 + crit_rate * (crit_dmg - 1.0);

    // 单发有效伤害
    let effective_dmg = if is_energy {
        calc_energy_damage(single_dmg, target_shield, 0.0, 1.0)
    } else {
        calc_physical_damage(single_dmg, target_armor, 0.0, 1.0, 0.0)
    };

    // 一轮总伤害
    let round_dmg = total_shots * effective_dmg * hit_rate * crit_mult;

    // 一轮时间（锁定和冷却可并发，取最大值）
    let round_time = lock_time.max(cooldown);

    if round_time <= 0.0 {
        return round_dmg;
    }

    round_dmg / round_time
}

/// 计算系统伤害
///
/// 系统伤害 = 对结构伤害 * 系统伤害系数
/// 不同武器有不同的系统伤害系数: 标准1.25, 强化1.5, 重型3.0
pub fn calc_system_damage(
    base_dmg: f64,
    system_dmg_coeff: f64,
    is_energy: bool,
    target_armor: f64,
    target_shield: f64,
) -> f64 {
    let structural_dmg = if is_energy {
        calc_energy_damage(base_dmg, target_shield, 0.0, 1.0)
    } else {
        calc_physical_damage(base_dmg, target_armor, 0.0, 1.0, 0.0)
    };
    structural_dmg * system_dmg_coeff
}

/// 计算维修量
///
/// 公式: repair_per_sec = (repair_dpm / 60) * (1 + armor * 0.0025)
/// 上限: repair_dpm / 60 * 2.5 (即150%)
pub fn calc_repair_amount(repair_dpm: f64, target_physical_armor: f64, dt: f64) -> f64 {
    let base_per_sec = repair_dpm / 60.0;
    let armor_bonus = 1.0 + target_physical_armor * 0.0025;
    let capped_bonus = armor_bonus.min(2.5); // 上限150%
    base_per_sec * capped_bonus * dt
}

/// 计算轰炸距离导致的命中修正
///
/// >15吉米: 每吉米 -2% 命中
/// <15吉米: 每吉米 +2% 命中
pub fn calc_bomb_distance_hit_modifier(bomb_distance: f64) -> f64 {
    if bomb_distance > 15.0 {
        -(bomb_distance - 15.0) * 0.02
    } else {
        (15.0 - bomb_distance) * 0.02
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_energy_damage_normal() {
        let dmg = calc_energy_damage(500.0, 10.0, 0.15, 1.0);
        assert!(dmg > 0.0);
        assert!(dmg < 1000.0);
    }

    #[test]
    fn test_energy_damage_immune() {
        let dmg = calc_energy_damage(500.0, 100.0, 0.0, 1.0);
        assert_eq!(dmg, 0.0);
    }

    #[test]
    fn test_physical_damage_floor() {
        let dmg = calc_physical_damage(100.0, 1000.0, 0.0, 1.0, 0.0);
        assert!(dmg >= 100.0 * MIN_DAMAGE_RATIO);
    }

    #[test]
    fn test_physical_damage_normal() {
        let dmg = calc_physical_damage(300.0, 20.0, 0.0, 1.0, 0.0);
        assert!(dmg > 0.0);
    }

    #[test]
    fn test_crit_damage() {
        let crit = calc_crit_damage(1.5, 0.2, 0.0);
        assert!((crit - 1.8).abs() < 0.01);
    }

    #[test]
    fn test_crit_rate_clamped() {
        assert_eq!(calc_crit_rate(0.5, 0.5), 0.95); // capped
        assert_eq!(calc_crit_rate(0.5, -1.0), 0.0); // floor
    }

    #[test]
    fn test_cooldown_minimum() {
        assert_eq!(calc_final_cooldown(0.3, 0.0, 1.0), 0.5);
    }

    #[test]
    fn test_estimate_dps() {
        let dps = estimate_dps(200.0, 2, 2, 4.0, 2.0, 0.7, 0.15, 1.5, false, 20.0, 0.0);
        assert!(dps > 0.0);
    }

    #[test]
    fn test_system_damage() {
        let sys_dmg = calc_system_damage(200.0, 1.5, false, 20.0, 0.0);
        assert!(sys_dmg > 0.0);
    }

    #[test]
    fn test_repair_amount() {
        let heal = calc_repair_amount(3000.0, 40.0, 1.0);
        assert!(heal > 0.0);
    }

    #[test]
    fn test_bomb_hit_modifier() {
        let mod_20 = calc_bomb_distance_hit_modifier(20.0);
        assert!(mod_20 < 0.0); // 更远 = 命中惩罚
        let mod_10 = calc_bomb_distance_hit_modifier(10.0);
        assert!(mod_10 > 0.0); // 更近 = 命中奖励
    }
}
