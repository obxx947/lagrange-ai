/**
 * battle_calc.c - 战斗计算核心实现
 *
 * 完整的拉格朗日战斗公式C语言实现。
 * 所有公式基于《无尽的拉格朗日》战斗机制文档。
 */

#include "battle_calc.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ==================== 内部辅助函数 ==================== */

static double clamp_d(double val, double min_val, double max_val) {
    if (val < min_val) return min_val;
    if (val > max_val) return max_val;
    return val;
}

static double safe_div(double a, double b, double default_val) {
    if (fabs(b) < 1e-10) return default_val;
    return a / b;
}

/* ==================== 伤害计算 ==================== */

double calc_energy_damage_c(double base_dmg, double target_shield_pct,
                             double dmg_bonus, double strategy_coeff) {
    if (target_shield_pct >= 100.0) return 0.0;

    double effective_mult = 1.0 + dmg_bonus - (target_shield_pct / 100.0);
    double final_dmg = base_dmg * effective_mult * TUNING_COEFFICIENT * strategy_coeff;
    return final_dmg > 0.0 ? final_dmg : 0.0;
}

double calc_physical_damage_c(double base_dmg, double target_armor,
                               double dmg_bonus, double strategy_coeff,
                               double armor_penetration) {
    double effective_armor = target_armor - armor_penetration;
    if (effective_armor < 0.0) effective_armor = 0.0;

    double raw_dmg = base_dmg * (1.0 + dmg_bonus) - effective_armor;

    if (raw_dmg <= 0.0) {
        raw_dmg = base_dmg * MIN_DAMAGE_RATIO; /* 10%保底 */
    }

    double final_dmg = raw_dmg * TUNING_COEFFICIENT * strategy_coeff;
    return final_dmg > 0.0 ? final_dmg : 0.0;
}

double calc_system_damage_c(double base_dmg, double system_coeff,
                             int is_energy, double target_armor,
                             double target_shield) {
    double structural_dmg;
    if (is_energy) {
        structural_dmg = calc_energy_damage_c(base_dmg, target_shield, 0.0, 1.0);
    } else {
        structural_dmg = calc_physical_damage_c(base_dmg, target_armor, 0.0, 1.0, 0.0);
    }
    return structural_dmg * system_coeff;
}

/* ==================== 命中率计算 ==================== */

double calc_hit_chance_c(double base_hit, double lock_efficiency,
                          double evasion, double bomb_distance,
                          double hit_bonus) {
    double hit = base_hit * (1.0 + hit_bonus - evasion) * lock_efficiency;

    /* 轰炸距离修正 */
    if (bomb_distance > BOMB_DISTANCE_BASE) {
        hit -= (bomb_distance - BOMB_DISTANCE_BASE) * BOMB_DISTANCE_PENALTY;
    } else {
        hit += (BOMB_DISTANCE_BASE - bomb_distance) * BOMB_DISTANCE_PENALTY;
    }

    return clamp_d(hit, 0.01, 0.99);
}

/* ==================== 拦截率计算 ==================== */

double calc_intercept_rate_c(double self_rate,
                              const double* same_row_rates, size_t same_row_count,
                              const double* global_rates, size_t global_count,
                              double anti_intercept) {
    double clamped_self = clamp_d(self_rate, 0.0, 1.0);
    double total = 1.0 - clamped_self;

    size_t i;
    for (i = 0; i < same_row_count; i++) {
        double r = clamp_d(same_row_rates[i], 0.0, 1.0);
        total *= (1.0 - r);
    }

    for (i = 0; i < global_count; i++) {
        double r = clamp_d(global_rates[i], 0.0, 1.0);
        total *= (1.0 - r);
    }

    double intercept = 1.0 - total;
    double anti = clamp_d(anti_intercept, 0.0, 1.0);
    intercept *= (1.0 - anti);

    return clamp_d(intercept, 0.0, 1.0);
}

/* ==================== 暴击计算 ==================== */

double calc_crit_damage_c(double base_crit_dmg, double crit_bonus,
                           double target_reduction) {
    double mult = 1.0 + crit_bonus - target_reduction;
    double result = base_crit_dmg * mult;
    return result > 1.0 ? result : 1.0;
}

double calc_crit_rate_c(double base_rate, double bonus) {
    return clamp_d(base_rate + bonus, 0.0, 0.95);
}

/* ==================== 冷却/锁定时间 ==================== */

double calc_final_cooldown_c(double base_cooldown, double reduction,
                              double strategy_coeff) {
    double cd = base_cooldown * (1.0 - reduction) * strategy_coeff;
    return cd > 0.5 ? cd : 0.5;
}

double calc_final_lock_time_c(double base_lock, double reduction,
                               double extension) {
    double lock = base_lock * (1.0 - reduction + extension);
    return lock > 0.2 ? lock : 0.2;
}

/* ==================== 维修计算 ==================== */

double calc_repair_amount_c(double repair_dpm, double target_armor,
                             double dt, double repair_bonus) {
    double base_per_sec = repair_dpm / 60.0;
    double armor_bonus = 1.0 + target_armor * REPAIR_ARMOR_BONUS;
    if (armor_bonus > REPAIR_MAX_BONUS) armor_bonus = REPAIR_MAX_BONUS;
    return base_per_sec * armor_bonus * (1.0 + repair_bonus) * dt;
}

/* ==================== DPS预估 ==================== */

double estimate_weapon_dps_c(double single_dmg, int attacks, int ammo,
                              double cooldown, double lock_time,
                              double hit_rate, double crit_rate,
                              double crit_dmg, int is_energy,
                              double target_armor, double target_shield) {
    int total_shots = attacks * ammo;
    double crit_mult = 1.0 + crit_rate * (crit_dmg - 1.0);

    double effective_dmg;
    if (is_energy) {
        effective_dmg = calc_energy_damage_c(single_dmg, target_shield, 0.0, 1.0);
    } else {
        effective_dmg = calc_physical_damage_c(single_dmg, target_armor, 0.0, 1.0, 0.0);
    }

    double round_dmg = total_shots * effective_dmg * hit_rate * crit_mult;
    double round_time = lock_time > cooldown ? lock_time : cooldown;

    if (round_time <= 0.0) return round_dmg;
    return round_dmg / round_time;
}

/* ==================== 子系统管理 ==================== */

void init_subsystems(ShipInstance* ship) {
    if (!ship) return;
    SystemHpRatios ratios = get_system_hp_ratios();

    ship->sub_system_max_hp[SYSTEM_MAIN_WEAPON] = ship->max_hp * ratios.main_weapon_ratio;
    ship->sub_system_max_hp[SYSTEM_HANGAR]      = ship->max_hp * ratios.hangar_ratio;
    ship->sub_system_max_hp[SYSTEM_COMMAND]     = ship->max_hp * ratios.command_ratio;
    ship->sub_system_max_hp[SYSTEM_PROPULSION]  = ship->max_hp * ratios.propulsion_ratio;

    int i;
    for (i = 0; i < 4; i++) {
        ship->sub_systems[i] = ship->sub_system_max_hp[i];
        ship->sub_system_repair_count[i] = 0;
        ship->sub_system_repair_timers[i] = 0.0;
    }
}

int is_system_active(const ShipInstance* ship, SystemType sys) {
    if (!ship) return 0;
    if (sys < 0 || sys > 3) return 0;
    return ship->sub_systems[sys] > 0.0;
}

int apply_system_damage(ShipInstance* ship, SystemType sys, double damage) {
    if (!ship || sys < 0 || sys > 3) return -1;
    if (ship->sub_systems[sys] <= 0.0) return -2; /* 已损坏 */

    ship->sub_systems[sys] -= damage;
    if (ship->sub_systems[sys] < 0.0) ship->sub_systems[sys] = 0.0;

    /* 同时扣除舰船结构HP */
    double hp_penalty = damage * 0.3;
    ship->current_hp -= hp_penalty;
    if (ship->current_hp < 0.0) ship->current_hp = 0.0;

    if (ship->sub_systems[sys] <= 0.0) {
        /* 检查修理上限 */
        SystemRepairLimits limits = get_system_repair_limits();
        int repair_limit = 1;
        switch (sys) {
            case SYSTEM_MAIN_WEAPON: repair_limit = limits.main_weapon_limit; break;
            case SYSTEM_HANGAR:      repair_limit = limits.hangar_limit; break;
            case SYSTEM_COMMAND:     repair_limit = limits.command_limit; break;
            case SYSTEM_PROPULSION:  repair_limit = limits.propulsion_limit; break;
        }

        if (ship->sub_system_repair_count[sys] < repair_limit) {
            ship->sub_system_repair_timers[sys] = 25.0; /* 25秒修复 */
            return 1; /* 可修复 */
        } else {
            return 2; /* 永久损毁 */
        }
    }
    return 0; /* 仍在运行，但受损 */
}

int process_system_repair(ShipInstance* ship, SystemType sys, double dt) {
    if (!ship || sys < 0 || sys > 3) return -1;

    double* timer = &ship->sub_system_repair_timers[sys];
    if (*timer <= 0.0) return 0; /* 没有在修复 */

    *timer -= dt;
    if (*timer <= 0.0) {
        /* 修复完成 */
        ship->sub_systems[sys] = ship->sub_system_max_hp[sys];
        ship->sub_system_repair_count[sys]++;
        *timer = 0.0;
        return 1;
    }
    return 0;
}

SystemRepairLimits get_system_repair_limits(void) {
    SystemRepairLimits limits;
    limits.main_weapon_limit = 2;
    limits.hangar_limit      = 2;
    limits.command_limit     = 3;
    limits.propulsion_limit  = 0; /* 推进系统不可修理 */
    return limits;
}

SystemHpRatios get_system_hp_ratios(void) {
    SystemHpRatios ratios;
    ratios.main_weapon_ratio = 0.12;
    ratios.hangar_ratio      = 0.10;
    ratios.command_ratio     = 0.08;
    ratios.propulsion_ratio  = 0.06;
    return ratios;
}

void free_ship_weapons(ShipInstance* ship) {
    if (ship && ship->weapons) {
        free(ship->weapons);
        ship->weapons = NULL;
        ship->weapon_count = 0;
    }
}

/* ==================== 批量数值计算 ==================== */

/**
 * 计算舰队的总DPS和总HP
 * @param ships 舰船数组
 * @param count 舰船数量
 * @param total_hp [out] 总HP
 * @param total_dps [out] 总DPS
 * @param avg_armor [out] 平均装甲
 */
void calc_fleet_stats_c(const ShipInstance* ships, size_t count,
                         double* total_hp, double* total_dps,
                         double* avg_armor) {
    *total_hp = 0.0;
    *total_dps = 0.0;
    *avg_armor = 0.0;

    if (!ships || count == 0) return;

    size_t i;
    for (i = 0; i < count; i++) {
        if (!ships[i].alive) continue;
        *total_hp += ships[i].current_hp;
        *avg_armor += ships[i].physical_armor;

        /* 估算DPS */
        size_t j;
        for (j = 0; j < ships[i].weapon_count; j++) {
            const Weapon* w = &ships[i].weapons[j];
            *total_dps += estimate_weapon_dps_c(
                w->single_damage, w->attacks, w->ammo,
                w->cooldown, w->lock_time,
                w->hit_rate, w->crit_rate, w->crit_damage,
                w->damage_type == DAMAGE_ENERGY,
                20.0, 10.0
            );
        }
    }

    if (count > 0) {
        *avg_armor /= (double)count;
    }
}

/* ==================== 简单战斗模拟 ==================== */

/**
 * 执行一次简化的舰队对战模拟
 * @param ally_ships 己方舰船
 * @param ally_count 己方数量
 * @param enemy_ships 敌方舰船
 * @param enemy_count 敌方数量
 * @param max_time 最大模拟时间
 * @param dt 时间步长
 * @return 1=己方胜利, 2=敌方胜利, 0=超时
 */
int simulate_simple_battle(ShipInstance* ally_ships, size_t ally_count,
                            ShipInstance* enemy_ships, size_t enemy_count,
                            double max_time, double dt) {
    double time = 0.0;
    double ally_total_hp, enemy_total_hp;
    double ally_total_dps, enemy_total_dps;
    double ally_avg_armor, enemy_avg_armor;

    while (time < max_time) {
        calc_fleet_stats_c(ally_ships, ally_count,
                          &ally_total_hp, &ally_total_dps, &ally_avg_armor);
        calc_fleet_stats_c(enemy_ships, enemy_count,
                          &enemy_total_hp, &enemy_total_dps, &enemy_avg_armor);

        if (ally_total_hp <= 0.0) return 2;
        if (enemy_total_hp <= 0.0) return 1;

        /* 简化伤害交换 */
        double ally_dmg_dealt = ally_total_dps * dt;
        double enemy_dmg_dealt = enemy_total_dps * dt;

        /* 分配到各舰船（均匀分配） */
        size_t i;
        size_t ally_alive = 0, enemy_alive = 0;
        for (i = 0; i < ally_count; i++) if (ally_ships[i].alive) ally_alive++;
        for (i = 0; i < enemy_count; i++) if (enemy_ships[i].alive) enemy_alive++;

        if (ally_alive == 0) return 2;
        if (enemy_alive == 0) return 1;

        double dmg_per_enemy = ally_dmg_dealt / (double)enemy_alive;
        double dmg_per_ally = enemy_dmg_dealt / (double)ally_alive;

        for (i = 0; i < enemy_count; i++) {
            if (enemy_ships[i].alive) {
                double actual_dmg = calc_physical_damage_c(
                    dmg_per_enemy, enemy_ships[i].physical_armor, 0.0, 1.0, 0.0);
                enemy_ships[i].current_hp -= actual_dmg;
                if (enemy_ships[i].current_hp <= 0.0) {
                    enemy_ships[i].current_hp = 0.0;
                    enemy_ships[i].alive = 0;
                }
            }
        }

        for (i = 0; i < ally_count; i++) {
            if (ally_ships[i].alive) {
                double actual_dmg = calc_physical_damage_c(
                    dmg_per_ally, ally_ships[i].physical_armor, 0.0, 1.0, 0.0);
                ally_ships[i].current_hp -= actual_dmg;
                if (ally_ships[i].current_hp <= 0.0) {
                    ally_ships[i].current_hp = 0.0;
                    ally_ships[i].alive = 0;
                }
            }
        }

        time += dt;
    }

    return 0; /* 超时 */
}
