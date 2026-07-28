//! 拦截率计算模块
//!
//! 实现《无尽的拉格朗日》三层拦截系统：
//! 1. 自身拦截 (self-intercept)
//! 2. 同排拦截 (same-row-intercept)
//! 3. 全局拦截 (global-intercept)
//!
//! 最终拦截率 = 1 - (1-self) * Π(1-same_row_i) * Π(1-global_j)
//! 反拦截修正: final = intercept * (1 - anti_intercept)

/// 计算三层叠加拦截率
///
/// # 公式
/// ```
/// intercept = 1 - (1 - self_rate) * Π(1 - same_row_i) * Π(1 - global_j)
/// final = intercept * (1 - anti_intercept)
/// ```
///
/// # 参数
/// - `self_rate`: 自身拦截率 (0-1)
/// - `same_row_rates`: 同排所有友军舰船的拦截率列表
/// - `global_rates`: 全局拦截率列表
/// - `anti_intercept`: 反拦截系数 (0-1)
///
/// # 返回
/// 最终拦截概率 (0-1)
///
/// # 示例
/// ```
/// let rate = calc_intercept_rate(0.10, &[0.05, 0.05], &[0.02], 0.0);
/// // 1 - (1-0.10) * (1-0.05) * (1-0.05) * (1-0.02) ≈ 0.204
/// assert!((rate - 0.204).abs() < 0.01);
/// ```
pub fn calc_intercept_rate(
    self_rate: f64,
    same_row_rates: &[f64],
    global_rates: &[f64],
    anti_intercept: f64,
) -> f64 {
    let clamped_self = self_rate.max(0.0).min(1.0);

    let mut total = 1.0 - clamped_self;

    // 同排拦截率叠加
    for rate in same_row_rates.iter() {
        let clamped = rate.max(0.0).min(1.0);
        total *= 1.0 - clamped;
    }

    // 全局拦截率叠加
    for rate in global_rates.iter() {
        let clamped = rate.max(0.0).min(1.0);
        total *= 1.0 - clamped;
    }

    let intercept = 1.0 - total;

    // 反拦截修正
    let anti_clamped = anti_intercept.max(0.0).min(1.0);
    let final_intercept = intercept * (1.0 - anti_clamped);

    final_intercept.max(0.0).min(1.0)
}

/// 多舰拦截叠加计算
///
/// 当多艘舰船具有拦截能力时，总拦截率的计算。
/// 公式: 1 - Π(1 - rate_i)
///
/// # 示例
/// ```
/// let rates = vec![0.27, 0.23, 0.12];
/// let total = calc_multi_ship_intercept(&rates);
/// // 1 - (1-0.27) * (1-0.23) * (1-0.12) ≈ 0.508
/// assert!((total - 0.508).abs() < 0.01);
/// ```
pub fn calc_multi_ship_intercept(rates: &[f64]) -> f64 {
    if rates.is_empty() {
        return 0.0;
    }

    let mut total = 1.0;
    for rate in rates.iter() {
        let clamped = rate.max(0.0).min(1.0);
        total *= 1.0 - clamped;
    }
    let intercept = 1.0 - total;
    intercept.max(0.0).min(1.0)
}

/// 计算舰队拦截覆盖率
///
/// 返回舰队的总拦截覆盖率和覆盖率分析
#[derive(Debug, Clone)]
pub struct InterceptCoverage {
    /// 自身拦截率
    pub self_intercept: f64,
    /// 同排总拦截率
    pub same_row_intercept: f64,
    /// 全局总拦截率
    pub global_intercept: f64,
    /// 三层总拦截率
    pub total_intercept: f64,
    /// 同排有拦截能力的舰船数
    pub same_row_ship_count: usize,
    /// 全局拦截舰船数
    pub global_ship_count: usize,
}

/// 分析舰队的拦截覆盖情况
pub fn analyze_intercept_coverage(
    self_rate: f64,
    same_row_rates: &[f64],
    global_rates: &[f64],
) -> InterceptCoverage {
    let same_row = if same_row_rates.is_empty() {
        0.0
    } else {
        calc_multi_ship_intercept(same_row_rates)
    };

    let global = if global_rates.is_empty() {
        0.0
    } else {
        calc_multi_ship_intercept(global_rates)
    };

    let total = calc_intercept_rate(self_rate, same_row_rates, global_rates, 0.0);

    InterceptCoverage {
        self_intercept: self_rate,
        same_row_intercept: same_row,
        global_intercept: global,
        total_intercept: total,
        same_row_ship_count: same_row_rates.len(),
        global_ship_count: global_rates.len(),
    }
}

/// 计算拦截效果对DPS的实际影响
///
/// 有效DPS = 基础DPS * (1 - 总拦截率)
pub fn calc_effective_dps(base_dps: f64, intercept_rate: f64) -> f64 {
    base_dps * (1.0 - intercept_rate.max(0.0).min(1.0))
}

/// 计算所需拦截舰船数以达到目标拦截率
///
/// 给定单艘舰船的拦截率，计算需要多少艘才能达到目标总拦截率。
/// 公式: n >= log(1 - target_rate) / log(1 - single_rate)
pub fn calc_required_intercept_ships(single_rate: f64, target_rate: f64) -> usize {
    if single_rate <= 0.0 || single_rate >= 1.0 || target_rate <= 0.0 || target_rate >= 1.0 {
        return 0;
    }

    let n = (1.0 - target_rate).ln() / (1.0 - single_rate).ln();
    (n.ceil() as usize).max(1)
}

/// 已知拦截舰船参考值（来自游戏数据）
#[derive(Debug, Clone)]
pub struct KnownInterceptShip {
    pub name: &'static str,
    pub intercept_rate: f64,
    pub intercept_type: &'static str, // "self", "same_row", "global"
}

/// 返回游戏中的已知拦截舰船列表
pub fn known_intercept_ships() -> Vec<KnownInterceptShip> {
    vec![
        KnownInterceptShip { name: "雷火之星-B2", intercept_rate: 0.27, intercept_type: "same_row" },
        KnownInterceptShip { name: "光锥级-防空型", intercept_rate: 0.23, intercept_type: "same_row" },
        KnownInterceptShip { name: "CV3000-A2", intercept_rate: 0.12, intercept_type: "global" },
        KnownInterceptShip { name: "乌拉诺斯之子-C3", intercept_rate: 0.10, intercept_type: "global" },
        KnownInterceptShip { name: "永恒风暴-D2", intercept_rate: 0.20, intercept_type: "self" },
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_intercept() {
        let rate = calc_intercept_rate(0.10, &[], &[], 0.0);
        assert!((rate - 0.10).abs() < 0.001);
    }

    #[test]
    fn test_three_layer_intercept() {
        // 已知参考数据:
        // 自身10%, 同排5%+5%, 全局2%
        // 1 - (1-0.10)*(1-0.05)*(1-0.05)*(1-0.02) ≈ 0.204
        let rate = calc_intercept_rate(0.10, &[0.05, 0.05], &[0.02], 0.0);
        assert!((rate - 0.204).abs() < 0.01);
    }

    #[test]
    fn test_anti_intercept() {
        // 30%反拦截 → 10%拦截率变为7%
        let rate = calc_intercept_rate(0.10, &[], &[], 0.30);
        assert!((rate - 0.07).abs() < 0.01);
    }

    #[test]
    fn test_full_intercept() {
        // 100%自身拦截率 → 总拦截率应为100%
        let rate = calc_intercept_rate(1.0, &[0.5, 0.5], &[0.5], 0.0);
        assert!((rate - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_multi_ship_real_data() {
        // 雷火之星-B2(27%) + 光锥防空型(23%) + CV3000-A2(12%)
        let rates = vec![0.27, 0.23, 0.12];
        let total = calc_multi_ship_intercept(&rates);
        // 1 - (0.73 * 0.77 * 0.88) ≈ 0.508
        assert!((total - 0.508).abs() < 0.01);
    }

    #[test]
    fn test_empty_rates() {
        assert_eq!(calc_multi_ship_intercept(&[]), 0.0);
        assert_eq!(calc_intercept_rate(0.0, &[], &[], 0.0), 0.0);
    }

    #[test]
    fn test_coverage_analysis() {
        let coverage = analyze_intercept_coverage(0.10, &[0.05, 0.05], &[0.02]);
        assert!(coverage.total_intercept > 0.0);
        assert_eq!(coverage.same_row_ship_count, 2);
        assert_eq!(coverage.global_ship_count, 1);
    }

    #[test]
    fn test_effective_dps() {
        let effective = calc_effective_dps(1000.0, 0.30);
        assert!((effective - 700.0).abs() < 0.01);
    }

    #[test]
    fn test_required_ships() {
        // 每艘20%拦截率，需要多少艘达到80%？
        let n = calc_required_intercept_ships(0.20, 0.80);
        // log(0.2)/log(0.8) ≈ -1.609/-0.223 ≈ 7.21 → 8艘
        assert_eq!(n, 8);
    }

    #[test]
    fn test_known_ships_exist() {
        let ships = known_intercept_ships();
        assert_eq!(ships.len(), 5);
        assert_eq!(ships[0].name, "雷火之星-B2");
    }
}
