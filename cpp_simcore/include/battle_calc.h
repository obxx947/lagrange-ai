/**
 * battle_calc.h - 拉格朗日战斗计算核心库
 *
 * 提供高性能的战斗公式计算函数。
 * 所有函数使用纯C实现，无外部依赖，适合嵌入和动态库调用。
 *
 * 版本: 1.0.0
 * 许可: MIT
 */

#ifndef BATTLE_CALC_H
#define BATTLE_CALC_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stddef.h>

/* ==================== 全局常量 ==================== */

#define TUNING_COEFFICIENT      1.3     /* 全局调校系数 */
#define MIN_DAMAGE_RATIO        0.10    /* 实弹未穿透保底10% */
#define CRIT_BASE_RATE          0.15    /* 基础暴击率15% */
#define SYSTEM_DAMAGE_CHANCE    0.10    /* 系统破坏触发概率10% */
#define PLUTUS_DAMAGE_REDUCTION 0.30    /* 普卢托斯之盾旗舰减伤30% */
#define BOMB_DISTANCE_BASE      15.0    /* 轰炸距离基准(吉米) */
#define BOMB_DISTANCE_PENALTY   0.02    /* 每吉米命中修正2% */
#define FLIGHT_TIME_PER_JIMI    2.0     /* 每吉米飞行时间2秒 */
#define REPAIR_ARMOR_BONUS      0.0025  /* 1点装甲=0.25%维修加成 */
#define REPAIR_MAX_BONUS        2.5     /* 维修加成上限(150%) */

/* ==================== 枚举定义 ==================== */

/** 武器类型 */
typedef enum {
    WEAPON_DIRECT_FIRE = 0,   /* 直射武器 */
    WEAPON_PROJECTILE  = 1    /* 投射武器 */
} WeaponType;

/** 伤害类型 */
typedef enum {
    DAMAGE_PHYSICAL = 0,      /* 实弹伤害 */
    DAMAGE_ENERGY   = 1       /* 能量伤害 */
} DamageType;

/** 舰船位置 */
typedef enum {
    POSITION_FRONT = 0,
    POSITION_MID   = 1,
    POSITION_BACK  = 2,
    POSITION_AIR   = 3
} ShipPosition;

/** 系统类型 */
typedef enum {
    SYSTEM_MAIN_WEAPON = 0,
    SYSTEM_HANGAR     = 1,
    SYSTEM_COMMAND    = 2,
    SYSTEM_PROPULSION = 3
} SystemType;

/** 舰载机模式 */
typedef enum {
    AIRCRAFT_INDEPENDENT  = 0,  /* 独立作战 */
    AIRCRAFT_RECIPROCATING = 1  /* 往复打击 */
} AircraftMode;

/** 防空类型 */
typedef enum {
    AA_COUNTER = 0,  /* 反击防空 */
    AA_AREA    = 1,  /* 区域防空 */
    AA_ACTIVE  = 2   /* 主动防空 */
} AntiAirType;

/** 战斗模式 */
typedef enum {
    BATTLE_ESCORT = 0,  /* 护航战斗 */
    BATTLE_BOMB   = 1   /* 轰炸战斗 */
} BattleMode;

/* ==================== 数据结构 ==================== */

/** 武器定义 */
typedef struct {
    char name[64];
    WeaponType weapon_type;
    DamageType damage_type;
    double single_damage;
    int    attacks;
    int    ammo;
    double attack_duration;
    double lock_time;
    double cooldown;
    char   priority[32];
    int    can_crit;
    double crit_rate;
    double crit_damage;
    double lock_efficiency;
    double hit_rate;
    AntiAirType anti_air_type;
    double intercept_rate;
    int    cannot_be_intercepted;
    double repair_dpm;
    double system_dmg_coeff;
    double anti_intercept;
} Weapon;

/** 舰船战斗实例 */
typedef struct {
    char id[32];
    char name[64];
    char ship_type[32];
    ShipPosition position;
    double max_hp;
    double current_hp;
    double physical_armor;
    double energy_armor_pct;
    double evasion;
    int    is_super_capital;
    int    is_flagship;
    int    is_carrier;
    int    is_escort;
    int    is_escorted;
    int    alive;
    double sub_systems[4];          /* 子系统HP */
    double sub_system_max_hp[4];    /* 子系统最大HP */
    int    sub_system_repair_count[4]; /* 修理次数 */
    double sub_system_repair_timers[4]; /* 修理计时器 */
    double active_effects[12];      /* 策略效果 */
    size_t weapon_count;
    Weapon* weapons;
} ShipInstance;

/** 战斗状态 */
typedef struct {
    double time;
    int    ended;
    int    winner;           /* 0=无, 1=己方, 2=敌方 */
    BattleMode mode;
    double bomb_distance;
    int    ally_escort_alive;
    int    enemy_escort_alive;
    double total_ally_damage;
    double total_enemy_damage;
    int    ally_ships_lost;
    int    enemy_ships_lost;
    int    ally_aircraft_lost;
    int    enemy_aircraft_lost;
} BattleState;

/** 系统修理限制 */
typedef struct {
    int main_weapon_limit;
    int hangar_limit;
    int command_limit;
    int propulsion_limit;
} SystemRepairLimits;

/** 系统HP比率 */
typedef struct {
    double main_weapon_ratio;
    double hangar_ratio;
    double command_ratio;
    double propulsion_ratio;
} SystemHpRatios;

/* ==================== 伤害计算函数 ==================== */

/**
 * 计算能量伤害
 * @param base_dmg 基础单发伤害
 * @param target_shield_pct 目标能量护盾百分比(0-100)
 * @param dmg_bonus 伤害加成(小数)
 * @param strategy_coeff 策略系数
 * @return 最终伤害值
 */
double calc_energy_damage_c(double base_dmg, double target_shield_pct,
                             double dmg_bonus, double strategy_coeff);

/**
 * 计算实弹伤害
 * @param base_dmg 基础单发伤害
 * @param target_armor 目标物理装甲
 * @param dmg_bonus 伤害加成
 * @param strategy_coeff 策略系数
 * @param armor_penetration 穿甲值
 * @return 最终伤害值
 */
double calc_physical_damage_c(double base_dmg, double target_armor,
                               double dmg_bonus, double strategy_coeff,
                               double armor_penetration);

/**
 * 计算系统伤害
 * @param base_dmg 基础伤害
 * @param system_coeff 系统伤害系数(1.25/1.5/3.0)
 * @param is_energy 是否能量伤害
 * @param target_armor 目标装甲
 * @param target_shield 目标护盾%
 * @return 对子系统的伤害值
 */
double calc_system_damage_c(double base_dmg, double system_coeff,
                             int is_energy, double target_armor,
                             double target_shield);

/* ==================== 命中率计算 ==================== */

/**
 * 计算命中率
 * @param base_hit 基础命中率
 * @param lock_efficiency 锁定效率
 * @param evasion 目标闪避率
 * @param bomb_distance 轰炸距离
 * @param hit_bonus 命中加成
 * @return 命中概率(0-1)
 */
double calc_hit_chance_c(double base_hit, double lock_efficiency,
                          double evasion, double bomb_distance,
                          double hit_bonus);

/* ==================== 拦截率计算 ==================== */

/**
 * 计算三层拦截率
 * @param self_rate 自身拦截率
 * @param same_row_rates 同排拦截率数组
 * @param same_row_count 同排数量
 * @param global_rates 全局拦截率数组
 * @param global_count 全局数量
 * @param anti_intercept 反拦截系数
 * @return 总拦截概率
 */
double calc_intercept_rate_c(double self_rate,
                              const double* same_row_rates, size_t same_row_count,
                              const double* global_rates, size_t global_count,
                              double anti_intercept);

/* ==================== 暴击计算 ==================== */

/** 计算暴击倍率 */
double calc_crit_damage_c(double base_crit_dmg, double crit_bonus,
                           double target_reduction);

/** 计算最终暴击率 */
double calc_crit_rate_c(double base_rate, double bonus);

/* ==================== 冷却/锁定 ==================== */

/** 计算最终冷却(>=0.5秒) */
double calc_final_cooldown_c(double base_cooldown, double reduction,
                              double strategy_coeff);

/** 计算最终锁定时间(>=0.2秒) */
double calc_final_lock_time_c(double base_lock, double reduction,
                               double extension);

/* ==================== 维修计算 ==================== */

/** 计算维修量 */
double calc_repair_amount_c(double repair_dpm, double target_armor,
                             double dt, double repair_bonus);

/* ==================== DPS预估 ==================== */

/** 预估武器DPS */
double estimate_weapon_dps_c(double single_dmg, int attacks, int ammo,
                              double cooldown, double lock_time,
                              double hit_rate, double crit_rate,
                              double crit_dmg, int is_energy,
                              double target_armor, double target_shield);

/* ==================== 辅助函数 ==================== */

/** 初始化子系统 */
void init_subsystems(ShipInstance* ship);

/** 检查子系统是否存活 */
int is_system_active(const ShipInstance* ship, SystemType sys);

/** 处理系统伤害 */
int apply_system_damage(ShipInstance* ship, SystemType sys, double damage);

/** 处理系统修复 */
int process_system_repair(ShipInstance* ship, SystemType sys, double dt);

/** 获取系统修理限制 */
SystemRepairLimits get_system_repair_limits(void);

/** 获取系统HP比率 */
SystemHpRatios get_system_hp_ratios(void);

/** 释放舰船武器内存 */
void free_ship_weapons(ShipInstance* ship);

#ifdef __cplusplus
}
#endif

#endif /* BATTLE_CALC_H */
