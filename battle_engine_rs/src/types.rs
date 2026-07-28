//! 核心数据类型定义
//!
//! 战斗引擎使用的数据结构定义，支持与Python/JSON之间的序列化。

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// 舰船类型
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ShipType {
    #[serde(rename = "fighter")]
    Fighter,
    #[serde(rename = "corvette")]
    Corvette,
    #[serde(rename = "frigate")]
    Frigate,
    #[serde(rename = "destroyer")]
    Destroyer,
    #[serde(rename = "cruiser")]
    Cruiser,
    #[serde(rename = "battlecruiser")]
    Battlecruiser,
    #[serde(rename = "battleship")]
    Battleship,
    #[serde(rename = "aircraftcarrier")]
    AircraftCarrier,
    #[serde(rename = "support")]
    Support,
}

/// 舰船位置
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ShipPosition {
    #[serde(rename = "front")]
    Front,
    #[serde(rename = "mid")]
    Mid,
    #[serde(rename = "back")]
    Back,
    #[serde(rename = "aircraft")]
    Aircraft,
}

/// 伤害类型
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum DamageType {
    #[serde(rename = "physical")]
    Physical,
    #[serde(rename = "energy")]
    Energy,
}

/// 武器类型
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum WeaponType {
    #[serde(rename = "direct")]
    DirectFire,
    #[serde(rename = "projectile")]
    Projectile,
}

/// 战斗模式
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum BattleMode {
    #[serde(rename = "escort")]
    Escort,
    #[serde(rename = "bomb")]
    Bomb,
}

/// 舰载机飞行模式
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum FlightMode {
    #[serde(rename = "independent")]
    Independent,
    #[serde(rename = "reciprocating")]
    Reciprocating,
}

/// 防空类型
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AntiAirType {
    #[serde(rename = "counter")]
    Counter,
    #[serde(rename = "area")]
    Area,
    #[serde(rename = "active")]
    Active,
}

/// 策略技能类型
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum StrategyType {
    #[serde(rename = "offensive")]
    Offensive,
    #[serde(rename = "defensive")]
    Defensive,
    #[serde(rename = "mobility")]
    Mobility,
    #[serde(rename = "flagship")]
    Flagship,
    #[serde(rename = "support")]
    Support,
    #[serde(rename = "special")]
    Special,
}

/// 舰船基础统计数据（用于分析）
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShipStats {
    pub id: String,
    pub name: String,
    pub ship_type: String,
    pub size: String,
    pub position: String,
    pub hp: f64,
    pub physical_armor: f64,
    pub energy_armor: f64,
    pub command_value: f64,
    pub ratings: HashMap<String, String>,
}

/// 舰队统计数据
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FleetStats {
    pub total_ships: usize,
    pub total_hp: f64,
    pub total_command_value: f64,
    pub avg_dps: f64,
    pub avg_armor: f64,
    pub avg_shield_pct: f64,
    pub type_distribution: HashMap<String, usize>,
}

impl FleetStats {
    /// 从舰船列表计算舰队统计
    pub fn from_ships(ships: &[ShipStats]) -> Self {
        let total_ships = ships.len();
        let total_hp: f64 = ships.iter().map(|s| s.hp).sum();
        let total_cv: f64 = ships.iter().map(|s| s.command_value).sum();
        let avg_armor: f64 = if total_ships > 0 {
            ships.iter().map(|s| s.physical_armor).sum::<f64>() / total_ships as f64
        } else {
            0.0
        };
        let avg_shield: f64 = if total_ships > 0 {
            ships.iter().map(|s| s.energy_armor).sum::<f64>() / total_ships as f64
        } else {
            0.0
        };

        // 类型分布
        let mut type_dist: HashMap<String, usize> = HashMap::new();
        for ship in ships {
            *type_dist.entry(ship.ship_type.clone()).or_insert(0) += 1;
        }

        // 估算DPS（基于HP的简化估算）
        let avg_dps: f64 = if total_hp > 0.0 {
            total_hp * 0.05 / total_ships as f64
        } else {
            0.0
        };

        FleetStats {
            total_ships,
            total_hp,
            total_command_value: total_cv,
            avg_dps,
            avg_armor,
            avg_shield_pct: avg_shield,
            type_distribution: type_dist,
        }
    }
}

/// 武器DPS统计
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WeaponDpm {
    pub anti_ship: f64,
    pub anti_air: f64,
    pub siege: f64,
    pub repair: f64,
}

/// 武器定义（用于模拟）
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WeaponDef {
    pub name: String,
    pub damage_type: DamageType,
    pub weapon_type: WeaponType,
    pub single_damage: f64,
    pub attacks: usize,
    pub ammo: usize,
    pub attack_duration: f64,
    pub lock_time: f64,
    pub cooldown: f64,
    pub priority: String,
    pub can_crit: bool,
    pub crit_rate: f64,
    pub crit_damage: f64,
    pub hit_rate: f64,
    pub anti_air_type: Option<AntiAirType>,
    pub intercept_rate: f64,
    pub cannot_be_intercepted: bool,
    pub dpm: WeaponDpm,
    pub sub_system_targets: HashMap<String, f64>,
    pub repair_dpm: f64,
}

/// 舰船战斗实例（用于模拟）
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShipBattleInstance {
    pub id: String,
    pub name: String,
    pub ship_type: ShipType,
    pub position: ShipPosition,
    pub max_hp: f64,
    pub current_hp: f64,
    pub physical_armor: f64,
    pub energy_armor_pct: f64,
    pub evasion: f64,
    pub is_super_capital: bool,
    pub is_flagship: bool,
    pub is_carrier: bool,
    pub is_escort: bool,
    pub is_escorted: bool,
    pub side: String,
    pub alive: bool,
    pub weapons: Vec<WeaponDef>,
    pub aircraft_ids: Vec<String>,
    pub carrier_bonuses: HashMap<String, f64>,
    pub strengthen: HashMap<String, f64>,
    pub active_effects: HashMap<String, f64>,
}

/// 战斗全局状态
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BattleStateDef {
    pub time: f64,
    pub ended: bool,
    pub winner: String,
    pub mode: BattleMode,
    pub bomb_distance: f64,
    pub ally_escort_alive: bool,
    pub enemy_escort_alive: bool,
    pub total_ally_damage: f64,
    pub total_enemy_damage: f64,
    pub ally_ships_lost: usize,
    pub enemy_ships_lost: usize,
    pub ally_aircraft_lost: usize,
    pub enemy_aircraft_lost: usize,
    pub logs: Vec<String>,
}

/// 战斗结果摘要
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BattleResult {
    pub winner: String,
    pub duration: f64,
    pub ally_damage_total: f64,
    pub enemy_damage_total: f64,
    pub ally_ships_lost: usize,
    pub enemy_ships_lost: usize,
    pub ally_surviving_ships: Vec<String>,
    pub enemy_surviving_ships: Vec<String>,
    pub battle_log: Vec<String>,
}

/// 舰船评分
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShipScore {
    pub tank_score: f64,
    pub dps_score: f64,
    pub support_score: f64,
    pub carrier_score: f64,
    pub overall_score: f64,
}

/// 评分映射
pub const RATING_SCORES: [(&str, f64); 5] = [
    ("S", 10.0),
    ("A", 7.0),
    ("B", 4.0),
    ("C", 2.0),
    ("D", 0.0),
];

/// 根据评级字母获取分数
pub fn rating_to_score(rating: &str) -> f64 {
    for (key, score) in RATING_SCORES.iter() {
        if rating == *key {
            return *score;
        }
    }
    2.0 // 默认C级
}
