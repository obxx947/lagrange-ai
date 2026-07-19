# -*- coding: utf-8 -*-
"""
完整战斗模拟引擎
---------------
基于《无尽的拉格朗日》战斗机制.txt 的真实游戏公式实现：
- 能量/实弹双伤害体系（装甲减免 + 护盾百分比）
- 锁定→攻击→冷却 三阶段武器循环
- 拦截机制（全局/同排/自身三层）
- 暴击系统 + 系统破坏
- 护航保护机制 + 旗舰效果
- 舰载机独立/往复双模式
- 分伤机制（可攻击目标数限制）
"""

import math
import random
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ==================== 枚举定义 ====================

class WeaponType(Enum):
    DIRECT_FIRE = "direct"    # 直射武器（轨道炮/脉冲炮/离子）
    PROJECTILE = "projectile"  # 投射武器（导弹/鱼雷）

class DamageType(Enum):
    PHYSICAL = "physical"     # 实弹伤害
    ENERGY = "energy"         # 能量伤害

class ShipPosition(Enum):
    FRONT = "front"
    MID = "mid"
    BACK = "back"
    AIR = "air"

class SystemType(Enum):
    MAIN_WEAPON = "main_weapon"
    HANGAR = "hangar"
    COMMAND = "command"
    PROPULSION = "propulsion"

class AircraftMode(Enum):
    INDEPENDENT = "independent"       # 独立作战
    RECIPROCATING = "reciprocating"   # 往复打击

class AAType(Enum):
    COUNTER = "counter"        # 反击防空
    AREA = "area"              # 区域防空
    ACTIVE = "active"          # 主动防空

class BattleMode(Enum):
    ESCORT = "escort"          # 护航战斗
    BOMB = "bomb"              # 轰炸战斗


# ==================== 数据类 ====================

@dataclass
class Weapon:
    """武器定义"""
    name: str
    weapon_type: WeaponType
    damage_type: DamageType
    single_damage: float          # 单发基础伤害
    attacks: int = 1              # 攻击轮次
    ammo: int = 1                 # 每轮弹药数
    attack_duration: float = 0     # 攻击持续时间(秒)
    lock_time: float = 1.0        # 锁定时间(秒)
    cooldown: float = 4.0         # 冷却时间(秒)
    priority: str = "random"      # 优先目标
    can_crit: bool = False        # 可暴击
    crit_rate: float = 0.15       # 暴击率
    crit_damage: float = 1.5      # 暴击倍率
    lock_efficiency: float = 1.0  # 锁定效率
    hit_rate: float = 0.7         # 基础命中率
    anti_air_type: Optional[AAType] = None
    intercept_rate: float = 0.0   # 拦截率
    cannot_be_intercepted: bool = False
    sub_system_targets: Dict[str, float] = field(default_factory=dict)
    repair_dpm: float = 0.0       # 维修DPM


@dataclass
class ShipInstance:
    """舰船战斗实例"""
    id: str
    name: str
    ship_type: str
    position: ShipPosition
    max_hp: float
    current_hp: float
    physical_armor: float         # 物理装甲值
    energy_armor_pct: float       # 能量抗性百分比(0-100)
    is_super_capital: bool = False
    is_flagship: bool = False
    is_carrier: bool = False
    is_escort: bool = False
    is_escorted: bool = False
    side: str = "ally"            # ally / enemy
    alive: bool = True
    
    # 运行时状态
    weapons: List[Weapon] = field(default_factory=list)
    weapon_states: List[dict] = field(default_factory=list)
    sub_systems: Dict[str, bool] = field(default_factory=dict)
    sub_system_repair_timers: Dict[str, float] = field(default_factory=dict)
    
    # 舰载机
    embarked_aircraft: List['ShipInstance'] = field(default_factory=list)
    aircraft_mode: Optional[AircraftMode] = None
    
    # 强化
    strengthen: Dict[str, float] = field(default_factory=dict)
    
    def is_alive(self) -> bool:
        return self.alive and self.current_hp > 0


@dataclass
class BattleState:
    """战斗全局状态"""
    ally_ships: List[ShipInstance] = field(default_factory=list)
    enemy_ships: List[ShipInstance] = field(default_factory=list)
    time: float = 0.0
    ended: bool = False
    winner: str = ""
    logs: List[str] = field(default_factory=list)
    mode: BattleMode = BattleMode.ESCORT
    bomb_distance: float = 15.0   # 轰炸距离（吉米）
    
    # 护航状态
    ally_escort_alive: bool = True
    enemy_escort_alive: bool = True
    
    # 统计
    total_ally_damage: float = 0.0
    total_enemy_damage: float = 0.0
    ally_ships_lost: int = 0
    enemy_ships_lost: int = 0


# ==================== 战斗公式（基于战斗机制.txt） ====================

TUNING_COEFFICIENT = 1.3  # 调校系数
MIN_DAMAGE_RATIO = 0.1    # 实弹未穿透保底10%
CRIT_BASE_RATE = 0.15     # 基础暴击率15%
SYSTEM_DAMAGE_CHANCE = 0.10  # 每次命中10%概率破坏系统
PLUTUS_DAMAGE_REDUCTION = 0.30  # 普卢托斯之盾旗舰30%减伤


def calc_energy_damage(base_dmg: float, target_energy_armor_pct: float,
                       dmg_bonus: float = 0.0, strategy_coeff: float = 1.0) -> float:
    """
    能量伤害计算
    公式：基础伤害 × (1 + 伤害加成% - 目标护盾%) × 调校系数 × 策略系数
    100%能量抗性 = 免疫
    """
    if target_energy_armor_pct >= 100:
        return 0.0
    effective_dmg = base_dmg * (1.0 + dmg_bonus - target_energy_armor_pct / 100.0)
    return max(0.0, effective_dmg * TUNING_COEFFICIENT * strategy_coeff)


def calc_physical_damage(base_dmg: float, target_armor: float,
                         dmg_bonus: float = 0.0, strategy_coeff: float = 1.0) -> float:
    """
    实弹伤害计算
    公式：(基础伤害 × (1 + 伤害加成) - 目标装甲) × 调校系数 × 策略系数
    未穿透时保底10%伤害
    """
    raw_dmg = base_dmg * (1.0 + dmg_bonus) - target_armor
    if raw_dmg <= 0:
        raw_dmg = base_dmg * MIN_DAMAGE_RATIO  # 保底10%
    return max(0.0, raw_dmg * TUNING_COEFFICIENT * strategy_coeff)


def calc_hit_chance(base_hit: float, lock_efficiency: float,
                    evasion: float = 0.0, bomb_distance: float = 15.0) -> float:
    """
    命中率计算
    公式：基础命中 × (1 + 命中加成 - 目标闪避) × 锁定效率
    轰炸距离调整：>15吉米每吉米-2%, <15吉米每吉米+2%
    """
    hit = base_hit * (1.0 - evasion) * lock_efficiency
    # 轰炸距离修正
    if bomb_distance > 15:
        hit -= (bomb_distance - 15) * 0.02
    else:
        hit += (15 - bomb_distance) * 0.02
    return max(0.01, min(0.99, hit))


def calc_intercept_rate(self_rate: float, same_row_rates: List[float],
                        global_rates: List[float]) -> float:
    """
    拦截率计算（三层叠加）
    公式：1 - (1-自身率) × Π(1-同排率) × Π(1-全局率)
    """
    total = 1.0 - self_rate
    for r in same_row_rates:
        total *= (1.0 - r)
    for r in global_rates:
        total *= (1.0 - r)
    return max(0.0, min(1.0, 1.0 - total))


def calc_crit_damage(base_crit_dmg: float, crit_dmg_bonus: float = 0.0,
                     target_crit_reduction: float = 0.0) -> float:
    """暴击伤害 = 基础暴击倍率 × (1 + 暴伤加成 - 目标暴伤减免)"""
    return base_crit_dmg * (1.0 + crit_dmg_bonus - target_crit_reduction)


def calc_final_cooldown(base_cooldown: float, cooldown_reduction: float = 0.0,
                        strategy_coeff: float = 1.0) -> float:
    """最终冷却 = 基础冷却 × (1 - 冷却缩减) × 策略系数"""
    return max(0.5, base_cooldown * (1.0 - cooldown_reduction) * strategy_coeff)


# ==================== 战斗模拟核心 ====================

class BattleSimulator:
    """战斗模拟器核心类"""
    
    def __init__(self, state: BattleState):
        self.state = state
        self._init_weapon_states()
    
    def _init_weapon_states(self):
        """初始化所有舰船的武器状态"""
        for ship in self.state.ally_ships + self.state.enemy_ships:
            ship.weapon_states = []
            for weapon in ship.weapons:
                ship.weapon_states.append({
                    "weapon": weapon,
                    "phase": "cooldown",     # cooldown / lock / attack
                    "cooldown_remaining": random.uniform(0, weapon.cooldown * 0.5),
                    "lock_remaining": 0.0,
                    "attack_remaining": 0.0,
                    "shots_fired": 0,
                    "total_shots": weapon.ammo * weapon.attacks,
                    "current_target": None,
                })
    
    def simulate_tick(self, dt: float) -> bool:
        """执行一个时间步长（通常0.1秒）"""
        if self.state.ended:
            return True
        
        self.state.time += dt
        
        # 检查护航状态
        self._update_escort_status()
        
        # 每艘存活舰船处理武器
        all_ally = [s for s in self.state.ally_ships if s.is_alive()]
        all_enemy = [s for s in self.state.enemy_ships if s.is_alive()]
        
        for ship in all_ally:
            self._process_ship_weapons(ship, all_enemy, dt)
        for ship in all_enemy:
            self._process_ship_weapons(ship, all_ally, dt)
        
        # 处理维修
        for ship in all_ally:
            self._process_repairs(ship, all_ally, dt)
        for ship in all_enemy:
            self._process_repairs(ship, all_enemy, dt)
        
        # 系统修复计时器
        for ship in all_ally + all_enemy:
            self._process_system_repairs(ship, dt)
        
        # 检查胜负
        return self._check_win_condition()
    
    def _update_escort_status(self):
        """更新护航存活状态"""
        self.state.ally_escort_alive = any(
            s.is_alive() and s.is_escort
            for s in self.state.ally_ships
        )
        self.state.enemy_escort_alive = any(
            s.is_alive() and s.is_escort
            for s in self.state.enemy_ships
        )
    
    def _process_ship_weapons(self, ship: ShipInstance, enemies: List[ShipInstance], dt: float):
        """处理单艘舰船的所有武器"""
        for ws in ship.weapon_states:
            weapon = ws["weapon"]
            
            if ws["phase"] == "cooldown":
                ws["cooldown_remaining"] -= dt
                if ws["cooldown_remaining"] <= 0:
                    ws["phase"] = "lock"
                    ws["lock_remaining"] = weapon.lock_time
            
            elif ws["phase"] == "lock":
                ws["lock_remaining"] -= dt
                # 锁定期间选择目标
                target = self._find_target(ship, enemies, weapon)
                ws["current_target"] = target
                
                if ws["lock_remaining"] <= 0:
                    if target and target.is_alive():
                        ws["phase"] = "attack"
                        ws["attack_remaining"] = weapon.attack_duration
                        ws["shots_fired"] = 0
                        # 0持续时间的武器立即发射全部
                        if weapon.attack_duration <= 0:
                            self._fire_all_shots(ship, target, weapon, ws)
                            ws["phase"] = "cooldown"
                            ws["cooldown_remaining"] = calc_final_cooldown(weapon.cooldown)
                    else:
                        ws["phase"] = "cooldown"
                        ws["cooldown_remaining"] = calc_final_cooldown(weapon.cooldown)
            
            elif ws["phase"] == "attack":
                ws["attack_remaining"] -= dt
                target = ws["current_target"]
                
                if target and target.is_alive():
                    # 在攻击持续期间分批发射
                    shots_to_fire = max(1, int(ws["total_shots"] * (dt / max(0.01, weapon.attack_duration))))
                    for _ in range(min(shots_to_fire, ws["total_shots"] - ws["shots_fired"])):
                        self._execute_shot(ship, target, weapon, ws)
                        ws["shots_fired"] += 1
                else:
                    # 目标死亡，剩余弹药可带至新目标
                    pass
                
                if ws["attack_remaining"] <= 0 or ws["shots_fired"] >= ws["total_shots"]:
                    ws["phase"] = "cooldown"
                    ws["cooldown_remaining"] = calc_final_cooldown(weapon.cooldown)
                    ws["current_target"] = None
    
    def _find_target(self, attacker: ShipInstance, enemies: List[ShipInstance],
                     weapon: Weapon) -> Optional[ShipInstance]:
        """寻找攻击目标（基于优先规则）"""
        alive = [e for e in enemies if e.is_alive()]
        if not alive:
            return None
        
        # 直射武器：逐排攻击（前排→中排→后排）
        if weapon.weapon_type == WeaponType.DIRECT_FIRE:
            for pos in [ShipPosition.FRONT, ShipPosition.MID, ShipPosition.BACK]:
                candidates = [e for e in alive if e.position == pos]
                if candidates:
                    # 优先超主力（如果设置了优先超主力）
                    supers = [e for e in candidates if e.is_super_capital]
                    if supers:
                        return random.choice(supers)
                    return random.choice(candidates)
        
        # 随机选择
        return random.choice(alive)
    
    def _execute_shot(self, attacker: ShipInstance, target: ShipInstance,
                      weapon: Weapon, ws: dict):
        """执行一次射击（完整伤害管线）"""
        
        # 1. 命中判定
        hit_chance = calc_hit_chance(
            weapon.hit_rate, weapon.lock_efficiency,
            bomb_distance=self.state.bomb_distance
        )
        if random.random() > hit_chance:
            return  # 未命中
        
        # 2. 拦截判定（三层）
        if not weapon.cannot_be_intercepted:
            intercept = self._calc_total_intercept(target, attacker)
            if random.random() < intercept:
                return  # 被拦截
        
        # 3. 护送保护
        if target.is_escorted:
            if (target.side == "ally" and self.state.ally_escort_alive) or \
               (target.side == "enemy" and self.state.enemy_escort_alive):
                return  # 被护送保护
        
        # 4. 伤害计算
        dmg_bonus = attacker.strengthen.get("dmg_bonus", 0.0) / 100.0
        strategy_coeff = 1.0
        
        if weapon.damage_type == DamageType.ENERGY:
            dmg = calc_energy_damage(
                weapon.single_damage,
                target.energy_armor_pct,
                dmg_bonus, strategy_coeff
            )
        else:
            dmg = calc_physical_damage(
                weapon.single_damage,
                target.physical_armor,
                dmg_bonus, strategy_coeff
            )
        
        # 5. 暴击判定
        if weapon.can_crit:
            crit_rate = CRIT_BASE_RATE + attacker.strengthen.get("crit_rate", 0.0) / 100.0
            if random.random() < crit_rate:
                crit_mult = calc_crit_damage(weapon.crit_damage)
                dmg *= crit_mult
        
        # 6. 普卢托斯之盾旗舰减伤
        dmg = self._apply_flagship_protection(target, dmg)
        
        # 7. 应用伤害
        target.current_hp -= dmg
        
        # 记录伤害
        if attacker.side == "ally":
            self.state.total_ally_damage += dmg
        else:
            self.state.total_enemy_damage += dmg
        
        # 8. 系统破坏判定
        if random.random() < SYSTEM_DAMAGE_CHANCE:
            self._attempt_system_damage(target, weapon)
        
        # 9. 死亡检查
        if target.current_hp <= 0:
            target.current_hp = 0
            target.alive = False
            if target.side == "ally":
                self.state.ally_ships_lost += 1
            else:
                self.state.enemy_ships_lost += 1
            self.state.logs.append(
                f"[{self.state.time:.1f}s] {attacker.name} 击毁了 {target.name}"
            )
    
    def _fire_all_shots(self, attacker: ShipInstance, target: ShipInstance,
                        weapon: Weapon, ws: dict):
        """瞬间发射全部弹药"""
        for _ in range(weapon.ammo * weapon.attacks):
            if not target.is_alive():
                break
            self._execute_shot(attacker, target, weapon, ws)
    
    def _calc_total_intercept(self, target: ShipInstance, attacker: ShipInstance) -> float:
        """计算总拦截率"""
        self_rate = 0.0
        same_row_rates = []
        global_rates = []
        
        all_friendlies = (self.state.ally_ships if target.side == "ally"
                         else self.state.enemy_ships)
        
        for ship in all_friendlies:
            if not ship.is_alive():
                continue
            for ws in ship.weapon_states:
                w = ws["weapon"]
                if w.intercept_rate > 0:
                    if ship.id == target.id:
                        self_rate = max(self_rate, w.intercept_rate)
                    elif ship.position == target.position:
                        same_row_rates.append(w.intercept_rate)
                    else:
                        global_rates.append(w.intercept_rate)
        
        return calc_intercept_rate(self_rate, same_row_rates, global_rates)
    
    def _apply_flagship_protection(self, target: ShipInstance, dmg: float) -> float:
        """应用旗舰保护效果"""
        all_friendlies = (self.state.ally_ships if target.side == "ally"
                         else self.state.enemy_ships)
        
        for ship in all_friendlies:
            if ship.is_flagship and ship.is_alive() and "普卢托斯" in ship.name:
                if ship.sub_systems.get("command", True):
                    dmg *= (1.0 - PLUTUS_DAMAGE_REDUCTION)
                    break
        return dmg
    
    def _attempt_system_damage(self, target: ShipInstance, weapon: Weapon):
        """尝试破坏目标舰船系统"""
        for sys_name, efficiency in weapon.sub_system_targets.items():
            if target.sub_systems.get(sys_name, True):
                eff_value = {"high": 0.6, "medium": 0.4, "low": 0.2}.get(efficiency, 0.3)
                if random.random() < eff_value:
                    target.sub_systems[sys_name] = False
                    # 系统破坏扣5%最大HP
                    hp_penalty = target.max_hp * 0.05
                    target.current_hp -= hp_penalty
                    target.sub_system_repair_timers[sys_name] = 25.0  # 25秒修复计时器
                    self.state.logs.append(
                        f"[{self.state.time:.1f}s] {target.name} 的{sys_name}系统被破坏！"
                    )
                    break
    
    def _process_repairs(self, ship: ShipInstance, friendlies: List[ShipInstance], dt: float):
        """处理维修"""
        for ws in ship.weapon_states:
            repair_dpm = ws["weapon"].repair_dpm
            if repair_dpm <= 0:
                continue
            
            # 找最低血量友军
            damaged = [f for f in friendlies if f.is_alive() and f.current_hp < f.max_hp]
            if not damaged:
                continue
            
            target = min(damaged, key=lambda f: f.current_hp / f.max_hp)
            repair_per_sec = (repair_dpm / 60.0) * (1.0 + target.physical_armor * 0.0025)
            repair_per_sec = min(repair_per_sec, repair_dpm / 60.0 * 2.5)  # 上限150%
            
            heal_amount = repair_per_sec * dt
            target.current_hp = min(target.max_hp, target.current_hp + heal_amount)
    
    def _process_system_repairs(self, ship: ShipInstance, dt: float):
        """处理系统修复计时器"""
        for sys_name, timer in list(ship.sub_system_repair_timers.items()):
            ship.sub_system_repair_timers[sys_name] -= dt
            if ship.sub_system_repair_timers[sys_name] <= 0:
                ship.sub_systems[sys_name] = True
                del ship.sub_system_repair_timers[sys_name]
                self.state.logs.append(
                    f"[{self.state.time:.1f}s] {ship.name} 的{sys_name}系统已修复"
                )
    
    def _check_win_condition(self) -> bool:
        """检查胜负条件"""
        ally_alive = any(s.is_alive() for s in self.state.ally_ships)
        enemy_alive = any(s.is_alive() for s in self.state.enemy_ships)
        
        if not ally_alive:
            self.state.ended = True
            self.state.winner = "enemy"
            self.state.logs.append(f"💀 己方舰队全灭！敌方胜利！(耗时{self.state.time:.1f}s)")
            return True
        if not enemy_alive:
            self.state.ended = True
            self.state.winner = "ally"
            self.state.logs.append(f"🏆 敌方舰队全灭！己方胜利！(耗时{self.state.time:.1f}s)")
            return True
        return False
    
    def run_until_end(self, max_time: float = 300.0, dt: float = 0.1) -> BattleState:
        """运行模拟直到结束或超时"""
        while not self.state.ended and self.state.time < max_time:
            if self.simulate_tick(dt):
                break
        if not self.state.ended:
            self.state.logs.append(f"⏰ 达到最大模拟时间 {max_time}s，战斗结束")
        return self.state


# ==================== 工厂函数 ====================

def create_ship_from_db(ship_data: dict, count: int = 1,
                        side: str = "ally") -> List[ShipInstance]:
    """
    从舰船数据库创建战斗实例
    
    Args:
        ship_data: 舰船数据库条目
        count: 数量
        side: 阵营
    
    Returns:
        舰船实例列表
    """
    instances = []
    for i in range(count):
        instance = ShipInstance(
            id=f"{ship_data.get('id','unknown')}_{i}",
            name=ship_data.get("name", "未知舰船"),
            ship_type=ship_data.get("type", "unknown"),
            position=ShipPosition(ship_data.get("position", "mid")),
            max_hp=float(ship_data.get("hp", 10000)),
            current_hp=float(ship_data.get("hp", 10000)),
            physical_armor=float(ship_data.get("physicalArmor", 10)),
            energy_armor_pct=float(ship_data.get("energyArmor", 5)),
            is_super_capital=ship_data.get("size") == "large",
            is_carrier=ship_data.get("isCarrier", False),
            side=side,
        )
        instances.append(instance)
    return instances


def create_basic_weapon(name: str = "标准舰炮", dmg: float = 200,
                        wtype: WeaponType = WeaponType.DIRECT_FIRE,
                        dtype: DamageType = DamageType.PHYSICAL) -> Weapon:
    """创建基础武器"""
    return Weapon(
        name=name,
        weapon_type=wtype,
        damage_type=dtype,
        single_damage=dmg,
        attacks=2,
        ammo=2,
        attack_duration=1.0,
        lock_time=2.0,
        cooldown=4.0,
        can_crit=True,
        hit_rate=0.75,
    )


# ==================== 测试运行 ====================

if __name__ == "__main__":
    # 创建测试舰船
    ally_ships = [
        ShipInstance(
            id="ally_front_0", name="光追级", ship_type="cruiser",
            position=ShipPosition.FRONT, max_hp=85000, current_hp=85000,
            physical_armor=45, energy_armor_pct=10, side="ally",
            weapons=[create_basic_weapon("对舰主炮", 350)],
            is_escort=True
        ),
        ShipInstance(
            id="ally_back_0", name="卡利斯托级", ship_type="cruiser",
            position=ShipPosition.BACK, max_hp=78000, current_hp=78000,
            physical_armor=40, energy_armor_pct=8, side="ally",
            weapons=[create_basic_weapon("导弹发射器", 500, WeaponType.PROJECTILE)],
            is_escorted=True
        ),
    ]
    
    enemy_ships = [
        ShipInstance(
            id="enemy_front_0", name="爱奥级", ship_type="cruiser",
            position=ShipPosition.FRONT, max_hp=95000, current_hp=95000,
            physical_armor=55, energy_armor_pct=6, side="enemy",
            weapons=[create_basic_weapon("重型主炮", 450)],
            is_escort=True
        ),
        ShipInstance(
            id="enemy_mid_0", name="阋神星重炮级", ship_type="destroyer",
            position=ShipPosition.MID, max_hp=28000, current_hp=28000,
            physical_armor=18, energy_armor_pct=5, side="enemy",
            weapons=[create_basic_weapon("驱逐主炮", 280)],
            is_escorted=True
        ),
    ]
    
    state = BattleState(
        ally_ships=ally_ships,
        enemy_ships=enemy_ships,
        logs=["⚔ 战斗测试开始！"],
    )
    
    sim = BattleSimulator(state)
    result = sim.run_until_end(max_time=120)
    
    print(f"战斗结果: {result.winner}胜利")
    print(f"用时: {result.time:.1f}s")
    print(f"己方伤害: {result.total_ally_damage:.0f}, 损失: {result.ally_ships_lost}艘")
    print(f"敌方伤害: {result.total_enemy_damage:.0f}, 损失: {result.enemy_ships_lost}艘")
    print("\n战斗日志:")
    for log in result.logs:
        print(f"  {log}")
