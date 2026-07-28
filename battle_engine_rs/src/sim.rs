//! 蒙特卡洛批量战斗模拟引擎
//!
//! 使用并行计算执行大规模战斗模拟，每次模拟使用不同的随机种子。
//! 用于统计分析和胜率预估。

use rand::Rng;
use rand::SeedableRng;
use rand::rngs::StdRng;
use rayon::prelude::*;
use std::time::Instant;

use crate::damage::{calc_energy_damage, calc_physical_damage, calc_final_cooldown};
use crate::intercept::calc_intercept_rate;

/// 单次模拟结果
#[derive(Debug, Clone)]
pub struct SimResult {
    /// 己方胜利
    pub ally_win: bool,
    /// 战斗持续时间（秒）
    pub duration: f64,
    /// 己方总伤害
    pub ally_damage: f64,
    /// 敌方总伤害
    pub enemy_damage: f64,
    /// 己方剩余HP
    pub ally_remaining_hp: f64,
    /// 敌方剩余HP
    pub enemy_remaining_hp: f64,
    /// 己方损失舰船数
    pub ally_ships_lost: usize,
    /// 敌方损失舰船数
    pub enemy_ships_lost: usize,
}

/// 批量模拟聚合结果
#[derive(Debug, Clone)]
pub struct BatchResult {
    /// 己方胜率
    pub ally_win_rate: f64,
    /// 平均战斗时间
    pub avg_duration: f64,
    /// 平均己方伤害
    pub avg_ally_damage: f64,
    /// 平均敌方伤害
    pub avg_enemy_damage: f64,
    /// 己方伤害标准差
    pub ally_damage_std: f64,
    /// 敌方伤害标准差
    pub enemy_damage_std: f64,
    /// 总迭代次数
    pub iterations: usize,
    /// 耗时（毫秒）
    pub elapsed_ms: u128,
    /// 详细结果（前20条）
    pub sample_results: Vec<SimResult>,
}

/// 单次战斗模拟
///
/// 简化模型：基于总HP和总DPS的兰彻斯特方程变种。
/// 考虑随机因素：命中率波动、暴击概率、拦截触发。
fn simulate_single_battle(
    mut ally_hp: f64,
    ally_dps: f64,
    ally_armor: f64,
    ally_intercept: f64,
    mut enemy_hp: f64,
    enemy_dps: f64,
    enemy_armor: f64,
    enemy_intercept: f64,
    rng: &mut StdRng,
    max_time: f64,
) -> SimResult {
    let mut time: f64 = 0.0;
    let dt: f64 = 0.1;
    let mut ally_total_dmg: f64 = 0.0;
    let mut enemy_total_dmg: f64 = 0.0;
    let ally_ships = 10.0; // 假设10艘
    let enemy_ships = 10.0;
    let mut ally_ships_alive = ally_ships as usize;
    let mut enemy_ships_alive = enemy_ships as usize;

    while time < max_time && ally_hp > 0.0 && enemy_hp > 0.0 {
        time += dt;

        // 随机命中率波动 (±10%)
        let ally_hit_factor = 0.9 + rng.gen::<f64>() * 0.2;
        let enemy_hit_factor = 0.9 + rng.gen::<f64>() * 0.2;

        // 拦截判定
        let ally_intercepted = rng.gen::<f64>() < ally_intercept;
        let enemy_intercepted = rng.gen::<f64>() < enemy_intercept;

        // 暴击判定（15%概率，1.5倍伤害）
        let ally_crit = rng.gen::<f64>() < 0.15;
        let enemy_crit = rng.gen::<f64>() < 0.15;

        // 己方攻击敌人
        let mut ally_effective_dps = ally_dps * ally_hit_factor;
        if enemy_intercepted { ally_effective_dps *= 0.5; } // 被拦截减半
        if ally_crit { ally_effective_dps *= 1.5; }

        // 考虑敌方装甲
        let ally_raw_per_shot = ally_effective_dps * dt;
        let ally_dmg = calc_physical_damage(ally_raw_per_shot, enemy_armor, 0.0, 1.0, 0.0);
        enemy_hp -= ally_dmg;
        ally_total_dmg += ally_dmg;

        // 敌方攻击己方
        let mut enemy_effective_dps = enemy_dps * enemy_hit_factor;
        if ally_intercepted { enemy_effective_dps *= 0.5; }
        if enemy_crit { enemy_effective_dps *= 1.5; }

        let enemy_raw_per_shot = enemy_effective_dps * dt;
        let enemy_dmg = calc_physical_damage(enemy_raw_per_shot, ally_armor, 0.0, 1.0, 0.0);
        ally_hp -= enemy_dmg;
        enemy_total_dmg += enemy_dmg;

        // 舰船损失（大幅简化）
        let ally_hp_ratio = (ally_hp / (ally_hp + enemy_total_dmg)).max(0.0);
        let enemy_hp_ratio = (enemy_hp / (enemy_hp + ally_total_dmg)).max(0.0);
        ally_ships_alive = (ally_ships * ally_hp_ratio).ceil() as usize;
        enemy_ships_alive = (enemy_ships * enemy_hp_ratio).ceil() as usize;
    }

    let ally_win = enemy_hp <= 0.0 || (ally_hp > enemy_hp && time >= max_time);

    SimResult {
        ally_win,
        duration: time,
        ally_damage: ally_total_dmg,
        enemy_damage: enemy_total_dmg,
        ally_remaining_hp: ally_hp.max(0.0),
        enemy_remaining_hp: enemy_hp.max(0.0),
        ally_ships_lost: ally_ships - ally_ships_alive.min(ally_ships as usize),
        enemy_ships_lost: enemy_ships - enemy_ships_alive.min(enemy_ships as usize),
    }
}

/// 批量蒙特卡洛模拟（并行执行）
///
/// # 参数
/// - `ally_total_hp`: 己方舰队总HP
/// - `ally_total_dps`: 己方舰队总DPS
/// - `ally_armor`: 己方平均装甲
/// - `enemy_total_hp`: 敌方舰队总HP
/// - `enemy_total_dps`: 敌方舰队总DPS
/// - `enemy_armor`: 敌方平均装甲
/// - `iterations`: 模拟次数
///
/// # 返回
/// 聚合统计结果
pub fn monte_carlo_battle(
    ally_total_hp: f64,
    ally_total_dps: f64,
    ally_armor: f64,
    enemy_total_hp: f64,
    enemy_total_dps: f64,
    enemy_armor: f64,
    iterations: usize,
) -> BatchResult {
    let start = Instant::now();
    let max_time: f64 = 300.0; // 最大模拟时间300秒
    let ally_intercept: f64 = 0.10; // 默认10%拦截率
    let enemy_intercept: f64 = 0.10;

    // 并行执行所有模拟
    let all_results: Vec<SimResult> = (0..iterations)
        .into_par_iter()
        .map(|seed| {
            let mut rng = StdRng::seed_from_u64(seed as u64);
            simulate_single_battle(
                ally_total_hp, ally_total_dps, ally_armor, ally_intercept,
                enemy_total_hp, enemy_total_dps, enemy_armor, enemy_intercept,
                &mut rng, max_time,
            )
        })
        .collect();

    let elapsed = start.elapsed().as_millis();

    // 聚合统计
    let wins = all_results.iter().filter(|r| r.ally_win).count();
    let n = all_results.len() as f64;

    let avg_duration: f64 = all_results.iter().map(|r| r.duration).sum::<f64>() / n;
    let avg_ally_dmg: f64 = all_results.iter().map(|r| r.ally_damage).sum::<f64>() / n;
    let avg_enemy_dmg: f64 = all_results.iter().map(|r| r.enemy_damage).sum::<f64>() / n;

    // 标准差
    let ally_var: f64 = all_results.iter()
        .map(|r| (r.ally_damage - avg_ally_dmg).powi(2))
        .sum::<f64>() / n;
    let enemy_var: f64 = all_results.iter()
        .map(|r| (r.enemy_damage - avg_enemy_dmg).powi(2))
        .sum::<f64>() / n;

    // 前20条详细结果
    let sample_results: Vec<SimResult> = all_results.into_iter().take(20).collect();

    BatchResult {
        ally_win_rate: wins as f64 / n,
        avg_duration,
        avg_ally_damage: avg_ally_dmg,
        avg_enemy_damage: avg_enemy_dmg,
        ally_damage_std: ally_var.sqrt(),
        enemy_damage_std: enemy_var.sqrt(),
        iterations,
        elapsed_ms: elapsed,
        sample_results,
    }
}

/// 对己方舰队DPS进行参数扫描，找到击败敌方所需的最小DPS
pub fn find_min_dps_for_win(
    ally_total_hp: f64,
    ally_armor: f64,
    enemy_total_hp: f64,
    enemy_total_dps: f64,
    enemy_armor: f64,
    iterations: usize,
    target_win_rate: f64,
) -> Option<f64> {
    let mut low = 0.0;
    let mut high = enemy_total_dps * 3.0; // 最多3倍
    let mut best = None;

    for _ in 0..20 {
        // 二分搜索
        let mid = (low + high) / 2.0;
        let result = monte_carlo_battle(
            ally_total_hp, mid, ally_armor,
            enemy_total_hp, enemy_total_dps, enemy_armor,
            iterations,
        );

        if result.ally_win_rate >= target_win_rate {
            best = Some(mid);
            high = mid;
        } else {
            low = mid;
        }
    }

    best
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_single_simulation() {
        let mut rng = StdRng::seed_from_u64(42);
        let result = simulate_single_battle(
            100000.0, 5000.0, 30.0, 0.10,
            80000.0, 4500.0, 25.0, 0.10,
            &mut rng, 60.0,
        );
        assert!(result.duration > 0.0);
        assert!(result.ally_damage > 0.0 || result.enemy_damage > 0.0);
    }

    #[test]
    fn test_monte_carlo() {
        let result = monte_carlo_battle(
            100000.0, 5000.0, 30.0,
            80000.0, 4500.0, 25.0,
            100,
        );
        assert!(result.iterations == 100);
        assert!(result.ally_win_rate >= 0.0 && result.ally_win_rate <= 1.0);
        assert!(result.elapsed_ms < 5000);
    }

    #[test]
    fn test_find_min_dps() {
        let min_dps = find_min_dps_for_win(
            100000.0, 30.0,
            100000.0, 5000.0, 30.0,
            50,
            0.8,
        );
        assert!(min_dps.is_some());
        assert!(min_dps.unwrap() > 0.0);
    }
}
