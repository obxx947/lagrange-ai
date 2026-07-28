#ifndef SIM_ENGINE_HPP
#define SIM_ENGINE_HPP

/**
 * sim_engine.hpp - C++高性能战斗模拟引擎
 *
 * 完整的面向对象战斗模拟引擎，支持：
 * - 舰载机空战（独立/往复）
 * - 防空系统（反击/区域/主动）
 * - 策略技能
 * - 系统数值HP
 * - 蒙特卡洛批量模拟
 */

#include "battle_calc.h"
#include <vector>
#include <string>
#include <random>
#include <memory>
#include <functional>
#include <chrono>
#include <map>
#include <set>

namespace LagrangeBattle {

using clock = std::chrono::high_resolution_clock;

// ==================== 枚举 ====================

enum class WeaponType { DirectFire = 0, Projectile = 1 };
enum class DamageType { Physical = 0, Energy = 1 };
enum class ShipPos { Front = 0, Mid = 1, Back = 2, Air = 3 };
enum class BattlePhase { Init, Running, Ended };
enum class AircraftState { InHangar, FlyingOut, Combat, Returning, Reloading, Destroyed };
enum class StrategyState { Ready, Active, Cooldown, Depleted };
enum class AA_Mode { Counter, Area, Active };

// ==================== 武器 ====================

struct WeaponInstance {
    std::string name;
    WeaponType weapon_type{WeaponType::DirectFire};
    DamageType damage_type{DamageType::Physical};
    double single_damage{100.0};
    int attacks{1}, ammo{1};
    double attack_duration{0.0}, lock_time{2.0}, cooldown{4.0};
    std::string priority{"random"};
    bool can_crit{false};
    double crit_rate{0.15}, crit_damage{1.5};
    double lock_efficiency{1.0}, hit_rate{0.7};
    AA_Mode aa_mode{AA_Mode::Counter};
    double intercept_rate{0.0};
    bool cannot_be_intercepted{false};
    double repair_dpm{0.0};
    double system_dmg_coeff{1.25};
    double anti_intercept{0.0};

    double calc_dps(double target_armor = 20, double target_shield = 10) const;
};

// ==================== 舰船 ====================

class Ship {
public:
    std::string id, name, ship_type;
    ShipPos position{ShipPos::Mid};
    double max_hp{10000}, current_hp{10000};
    double physical_armor{10}, energy_armor_pct{5};
    double evasion{0.0};
    bool is_super_capital{false}, is_flagship{false}, is_carrier{false};
    bool is_escort{false}, is_escorted{false};
    bool alive{true};
    std::string side{"ally"};

    std::vector<WeaponInstance> weapons;
    std::map<std::string, double> sub_systems;
    std::map<std::string, double> sub_system_max_hp;
    std::map<std::string, int> sub_system_repair_count;
    std::map<std::string, double> sub_system_repair_timers;
    std::map<std::string, double> active_effects;
    std::map<std::string, double> strengthen;
    std::vector<std::string> aircraft_ids;
    std::map<std::string, double> carrier_bonuses;

    Ship() { init_subsystems(); }
    explicit Ship(const std::string& name_, double hp_);

    bool is_alive() const { return alive && current_hp > 0; }
    bool is_system_active(const std::string& sys) const;
    void take_damage(double dmg);
    void init_subsystems();
    double get_effect(const std::string& key, double default_val = 0.0) const;

    static Ship create_from_json(const std::string& json_str);
};

// ==================== 舰载机 ====================

struct AircraftUnit {
    std::string id, name, aircraft_type;
    AircraftState state{AircraftState::InHangar};
    int squadron_size{3}, current_count{3};
    double max_hp_per_unit{5000}, current_hp_per_unit{5000};
    double flight_out_time{8.0}, flight_back_time{8.0};
    double flight_timer{0.0}, combat_timer{0.0}, reload_timer{0.0};
    std::string mother_ship_id;
    std::vector<WeaponInstance> weapons;
    std::map<std::string, double> carrier_bonuses;
    double total_damage{0.0};
    int sorties{0};

    bool is_alive() const;
    bool is_vulnerable() const;
    void update(double dt, std::vector<Ship*>& targets, double bomb_distance,
                std::mt19937& rng);
};

// ==================== 策略技能 ====================

struct StrategySkill {
    std::string id, name, description;
    double cooldown{60.0}, duration{20.0};
    std::map<std::string, double> effects;
    std::string target{"self"};
    int max_uses{99};
    bool requires_command{false};
};

struct ActiveStrategy {
    StrategySkill skill;
    StrategyState state{StrategyState::Ready};
    double remaining_duration{0.0}, remaining_cooldown{0.0};
    int uses_remaining{99};
};

// ==================== 战斗状态 ====================

class BattleEngine {
public:
    BattleEngine();
    explicit BattleEngine(unsigned seed);

    void add_ship(const Ship& ship, const std::string& side);
    void add_aircraft(const AircraftUnit& aircraft, const std::string& side);
    void add_strategy(const std::string& ship_id, const StrategySkill& skill,
                      const std::string& side);
    void set_mode(BattleMode mode) { battle_mode = mode; }
    void set_bomb_distance(double d) { bomb_distance = d; }
    void set_max_time(double t) { max_time = t; }

    bool step(double dt);
    void run();
    std::string summary() const;

    // 统计
    double total_ally_damage{0}, total_enemy_damage{0};
    int ally_ships_lost{0}, enemy_ships_lost{0};
    double sim_time{0};
    BattlePhase phase{BattlePhase::Init};
    std::string winner;
    std::vector<std::string> logs;

    const std::vector<Ship>& get_ally_ships() const { return ally_ships; }
    const std::vector<Ship>& get_enemy_ships() const { return enemy_ships; }

private:
    std::vector<Ship> ally_ships, enemy_ships;
    std::vector<AircraftUnit> ally_aircraft, enemy_aircraft;
    std::map<std::string, std::vector<ActiveStrategy>> ally_strategies, enemy_strategies;
    BattleMode battle_mode{BattleMode::Escort};
    double bomb_distance{15.0}, max_time{300.0};
    std::mt19937 rng;

    void process_weapons(Ship& attacker, std::vector<Ship>& enemies, double dt);
    void process_aircraft(std::vector<AircraftUnit>& aircraft,
                         std::vector<Ship>& enemies, double dt);
    void process_aa(std::vector<Ship>& defenders,
                   std::vector<AircraftUnit>& attackers, double dt);
    void process_repairs(Ship& ship, std::vector<Ship>& friendlies, double dt);
    void process_system_repairs(Ship& ship, double dt);
    Ship* find_target(Ship& attacker, std::vector<Ship>& enemies,
                      const WeaponInstance& weapon);
    void execute_shot(Ship& attacker, Ship& target,
                      const WeaponInstance& weapon);
    bool check_win();
    void update_escort_status();
    double calc_total_intercept(Ship& target);
};

// ==================== 蒙特卡洛批量模拟 ====================

struct MonteCarloResult {
    double ally_win_rate{0}, avg_duration{0};
    double avg_ally_dmg{0}, avg_enemy_dmg{0};
    double ally_dmg_std{0}, enemy_dmg_std{0};
    int iterations{0};
    long long elapsed_ms{0};
};

MonteCarloResult monte_carlo_simulate(
    const std::vector<Ship>& ally_template,
    const std::vector<Ship>& enemy_template,
    int iterations = 1000,
    double max_time = 300.0
);

// ==================== 舰队分析 ====================

struct FleetAnalysis {
    double total_hp{0}, total_dps{0}, avg_armor{0}, avg_shield{0};
    int ship_count{0};
    double total_command_value{0};
    double estimated_battle_duration{0};
    std::map<std::string, int> type_distribution;
    std::map<std::string, double> damage_contribution;
    std::vector<std::string> weaknesses;
};

FleetAnalysis analyze_fleet(const std::vector<Ship>& fleet);

// ==================== 工厂函数 ====================

Ship make_test_ship(const std::string& name, double hp, double armor,
                    double dps, ShipPos pos = ShipPos::Mid);
WeaponInstance make_test_weapon(const std::string& name, double dmg,
                                 WeaponType wtype = WeaponType::DirectFire);

} // namespace LagrangeBattle

#endif // SIM_ENGINE_HPP
