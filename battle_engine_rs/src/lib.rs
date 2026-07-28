//! 拉格朗日战斗模拟引擎 - Rust核心
//!
//! 提供高性能的战斗计算功能，通过PyO3暴露给Python调用。
//! 支持批量蒙特卡洛模拟、伤害计算、拦截率计算等功能。
//!
//! # 架构
//! - `damage`: 伤害计算公式（能量/实弹双体系）
//! - `intercept`: 拦截率计算（三层叠加）
//! - `sim`: 蒙特卡洛批量模拟引擎
//! - `types`: 核心数据类型定义

pub mod damage;
pub mod intercept;
pub mod sim;
pub mod types;

use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use rayon::prelude::*;

/// 调校系数（全局常量）
pub const TUNING_COEFFICIENT: f64 = 1.3;

/// 实弹未穿透保底伤害比例（10%）
pub const MIN_DAMAGE_RATIO: f64 = 0.10;

/// 基础暴击率（15%）
pub const CRIT_BASE_RATE: f64 = 0.15;

/// 系统破坏触发概率（10%）
pub const SYSTEM_DAMAGE_CHANCE: f64 = 0.10;

/// 普卢托斯之盾旗舰减伤（30%）
pub const PLUTUS_DAMAGE_REDUCTION: f64 = 0.30;

/// 轰炸距离基准（吉米）
pub const BOMB_DISTANCE_BASE: f64 = 15.0;

/// 每吉米命中率修正（2%）
pub const BOMB_DISTANCE_PENALTY: f64 = 0.02;

/// 飞行时间系数（2秒/吉米）
pub const FLIGHT_TIME_PER_JIMI: f64 = 2.0;

/// 计算能量伤害（Python可调用）
///
/// 公式: base_dmg * (1 + dmg_bonus - target_shield%) * tuning * strategy
/// 能量抗性达到100%时完全免疫。
#[pyfunction]
#[pyo3(name = "calc_energy_damage_rs")]
fn py_calc_energy_damage(
    base_dmg: f64,
    target_energy_armor_pct: f64,
    dmg_bonus: f64,
    strategy_coeff: f64,
) -> PyResult<f64> {
    Ok(damage::calc_energy_damage(
        base_dmg,
        target_energy_armor_pct,
        dmg_bonus,
        strategy_coeff,
    ))
}

/// 计算实弹伤害（Python可调用）
///
/// 公式: max(base_dmg * (1 + bonus) - armor, base_dmg * 0.1) * tuning * strategy
#[pyfunction]
#[pyo3(name = "calc_physical_damage_rs")]
fn py_calc_physical_damage(
    base_dmg: f64,
    target_armor: f64,
    dmg_bonus: f64,
    strategy_coeff: f64,
) -> PyResult<f64> {
    Ok(damage::calc_physical_damage(
        base_dmg,
        target_armor,
        dmg_bonus,
        strategy_coeff,
    ))
}

/// 计算三层拦截率（Python可调用）
///
/// 公式: 1 - (1-self) * Π(1-same_row_i) * Π(1-global_j)
/// 最终拦截率限制在[0, 1]区间
#[pyfunction]
#[pyo3(name = "calc_intercept_rate_rs")]
fn py_calc_intercept_rate(
    self_rate: f64,
    same_row_rates: Vec<f64>,
    global_rates: Vec<f64>,
    anti_intercept: f64,
) -> PyResult<f64> {
    Ok(intercept::calc_intercept_rate(
        self_rate,
        &same_row_rates,
        &global_rates,
        anti_intercept,
    ))
}

/// 批量蒙特卡洛战斗模拟（Python可调用）
///
/// 并行运行N次模拟，返回统计结果：
/// - 胜率、平均战斗时间、平均伤害、标准差等
#[pyfunction]
#[pyo3(name = "monte_carlo_simulate")]
fn py_monte_carlo_simulate(
    ally_total_hp: f64,
    ally_total_dps: f64,
    ally_armor: f64,
    enemy_total_hp: f64,
    enemy_total_dps: f64,
    enemy_armor: f64,
    iterations: usize,
) -> PyResult<PyObject> {
    let results = sim::monte_carlo_battle(
        ally_total_hp,
        ally_total_dps,
        ally_armor,
        enemy_total_hp,
        enemy_total_dps,
        enemy_armor,
        iterations,
    );

    Python::with_gil(|py| {
        let dict = pyo3::types::PyDict::new_bound(py);
        dict.set_item("ally_win_rate", results.ally_win_rate)?;
        dict.set_item("avg_duration", results.avg_duration)?;
        dict.set_item("avg_ally_damage", results.avg_ally_damage)?;
        dict.set_item("avg_enemy_damage", results.avg_enemy_damage)?;
        dict.set_item("iterations", results.iterations)?;
        Ok(dict.to_object(py))
    })
}

/// 计算DPS预估（Python可调用）
#[pyfunction]
#[pyo3(name = "estimate_dps_rs")]
fn py_estimate_dps(
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
) -> PyResult<f64> {
    Ok(damage::estimate_dps(
        single_dmg, attacks, ammo, cooldown, lock_time,
        hit_rate, crit_rate, crit_dmg, is_energy,
        target_armor, target_shield,
    ))
}

/// 校验舰船数据的完整性（Python可调用）
#[pyfunction]
#[pyo3(name = "validate_ship_data")]
fn py_validate_ship_data(ship_json: String) -> PyResult<String> {
    match serde_json::from_str::<serde_json::Value>(&ship_json) {
        Ok(value) => {
            let mut issues: Vec<String> = Vec::new();
            if let Some(arr) = value.as_array() {
                for (i, ship) in arr.iter().enumerate() {
                    if ship.get("id").is_none() {
                        issues.push(format!("Ship #{}: missing 'id'", i));
                    }
                    if ship.get("hp").and_then(|v| v.as_f64()).unwrap_or(0.0) <= 0.0 {
                        issues.push(format!("Ship #{}: invalid hp", i));
                    }
                    if ship.get("commandValue").and_then(|v| v.as_i64()).unwrap_or(0) <= 0 {
                        issues.push(format!("Ship #{}: invalid commandValue", i));
                    }
                }
            }
            if issues.is_empty() {
                Ok("All ships validated successfully!".to_string())
            } else {
                Ok(format!("Validation issues found ({} problems):\n{}",
                    issues.len(),
                    issues.iter().take(20).cloned().collect::<Vec<_>>().join("\n")))
            }
        }
        Err(e) => Ok(format!("JSON parse error: {}", e)),
    }
}

/// 对舰船数据库进行统计分析（Python可调用）
#[pyfunction]
#[pyo3(name = "analyze_fleet_stats")]
fn py_analyze_fleet_stats(ships_json: String) -> PyResult<String> {
    match serde_json::from_str::<Vec<types::ShipStats>>(&ships_json) {
        Ok(ships) => {
            let stats = types::FleetStats::from_ships(&ships);
            Ok(format!(
                "舰队统计:\n\
                 总舰船: {}\n\
                 总HP: {:.0}\n\
                 总指挥值: {:.0}\n\
                 平均DPS: {:.1}\n\
                 类型分布: {:?}\n\
                 平均装甲: {:.1}\n\
                 平均护盾: {:.1}%",
                stats.total_ships,
                stats.total_hp,
                stats.total_command_value,
                stats.avg_dps,
                stats.type_distribution,
                stats.avg_armor,
                stats.avg_shield_pct,
            ))
        }
        Err(e) => Ok(format!("Parse error: {}", e)),
    }
}

/// Python模块初始化
#[pymodule]
fn battle_engine_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_calc_energy_damage, m)?)?;
    m.add_function(wrap_pyfunction!(py_calc_physical_damage, m)?)?;
    m.add_function(wrap_pyfunction!(py_calc_intercept_rate, m)?)?;
    m.add_function(wrap_pyfunction!(py_monte_carlo_simulate, m)?)?;
    m.add_function(wrap_pyfunction!(py_estimate_dps, m)?)?;
    m.add_function(wrap_pyfunction!(py_validate_ship_data, m)?)?;
    m.add_function(wrap_pyfunction!(py_analyze_fleet_stats, m)?)?;

    m.add("TUNING_COEFFICIENT", TUNING_COEFFICIENT)?;
    m.add("MIN_DAMAGE_RATIO", MIN_DAMAGE_RATIO)?;
    m.add("CRIT_BASE_RATE", CRIT_BASE_RATE)?;
    m.add("PLUTUS_DAMAGE_REDUCTION", PLUTUS_DAMAGE_REDUCTION)?;
    m.add("BOMB_DISTANCE_BASE", BOMB_DISTANCE_BASE)?;

    Ok(())
}
