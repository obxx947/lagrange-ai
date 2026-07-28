# -*- coding: utf-8 -*-
"""
拉格朗日战斗计算API - 高性能后端
基于战斗机制.txt 完整公式的精确计算
"""

import math
import random
import json
import time
from typing import List, Dict, Optional, Tuple
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/battle", tags=["battle"])

# ========== 常量 ==========
TUNE = 1.3          # 1 + 30%调校系数
MIN_DMG = 0.10      # 实弹保底10%
CRIT_BASE = 0.15    # 基础暴击率
SYS_CHANCE = 0.10   # 系统破坏触发率
PLUTUS_REDUCTION = 0.30  # 旗舰减伤

# 系统HP比例
SYS_HP_RATIOS = {"main_weapon": 0.12, "hangar": 0.10, "command": 0.08, "propulsion": 0.06}
# 系统修理上限
SYS_REPAIR_LIMITS = {"main_weapon": 2, "hangar": 2, "command": 3, "propulsion": 0}
# 系统瞄准效率
SYS_EFFICIENCY = {"high": 0.60, "medium": 0.40, "low": 0.20}

# ========== 数据模型 ==========
class WeaponData(BaseModel):
    name: str = ""
    dmgType: str = "physical"
    weaponType: str = "direct"
    singleDmg: float = 100
    attacks: int = 1
    ammo: int = 1
    atkDuration: float = 0
    lockTime: float = 2.0
    cooldown: float = 4.0
    priority: str = "random"
    crit: bool = False
    hitMin: float = 50
    hitMax: float = 70
    antiAirType: Optional[str] = None
    interceptRate: float = 0
    cannotBeIntercepted: bool = False
    subSystemTargets: Dict[str, str] = {}
    systemDmgCoeff: float = 1.5
    repairDpm: float = 0

class ShipData(BaseModel):
    id: str
    name: str = ""
    type: str = "cruiser"
    position: str = "中排"
    hp: float = 50000
    physicalArmor: float = 10
    energyArmor: float = 5
    commandValue: int = 10
    isSuperCapital: bool = False
    isCarrier: bool = False
    isEscort: bool = False
    isEscorted: bool = False
    isFlagship: bool = False
    evasion: float = 0
    weapons: List[WeaponData] = []
    dmgBonus: float = 0
    physResistBonus: float = 0
    energyResistBonus: float = 0

class BattleRequest(BaseModel):
    allyShips: List[ShipData]
    enemyShips: List[ShipData]
    mode: str = "escort"
    bombDistance: float = 15.0
    maxTime: float = 300.0

class ShipResult(BaseModel):
    id: str
    name: str
    initialHp: float
    finalHp: float
    damageDealt: float
    damageTaken: float
    alive: bool
    systemsDestroyed: List[str]

class BattleResponse(BaseModel):
    winner: str
    duration: float
    allyTotalDamage: float
    enemyTotalDamage: float
    allyShipsLost: int
    enemyShipsLost: int
    allyShips: List[ShipResult]
    enemyShips: List[ShipResult]
    logs: List[str]
    dpsAnalysis: Dict[str, float]

# ========== 核心公式 ==========

def calc_energy_damage(base_dmg: float, tech_bonus: float, shield_pct: float, strategy: float = 1.0) -> float:
    """能量伤害 = (基础+科技-基础×护盾%) × (1+调校) × 策略"""
    if shield_pct >= 100: return 0.0
    shield_reduction = base_dmg * (shield_pct / 100.0)
    return max(0, (base_dmg + tech_bonus - shield_reduction) * TUNE * strategy)

def calc_physical_damage(base_dmg: float, tech_bonus: float, armor: float, strategy: float = 1.0) -> float:
    """实弹伤害：可破防=(基础+科技)×调校-护甲，不破防=(基础+科技)/10×调校"""
    raw = (base_dmg + tech_bonus) * TUNE * strategy
    after_armor = raw - armor
    if after_armor > 0:
        return max(0, after_armor)
    else:
        return max(0, (base_dmg + tech_bonus) / 10 * TUNE * strategy)

def calc_system_damage(base_dmg: float, tech_bonus: float, sys_coeff: float) -> float:
    """系统伤害 = (基础+科技) × (1+调校) × 系统系数"""
    return (base_dmg + tech_bonus) * TUNE * sys_coeff

def calc_hit_chance(hit_min: float, hit_max: float, evasion: float = 0, bomb_dist: float = 15.0) -> float:
    """命中率：基础命中区间 + 闪避修正 + 轰炸距离修正"""
    base = (hit_min + random.random() * (hit_max - hit_min)) / 100.0
    base *= (1.0 - evasion / 100.0)
    if bomb_dist > 15:
        base -= (bomb_dist - 15) * 0.02
    else:
        base += (15 - bomb_dist) * 0.02
    return max(0.01, min(0.99, base))

def calc_intercept_rate(self_rate: float, same_row_rates: List[float], global_rates: List[float]) -> float:
    """三层拦截：1 - (1-self)×Π(1-same)×Π(1-global)"""
    total = 1.0 - self_rate
    for r in same_row_rates: total *= (1.0 - r)
    for r in global_rates: total *= (1.0 - r)
    return max(0.0, min(1.0, 1.0 - total))

# ========== 战斗模拟 ==========

class BattleSimulator:
    def __init__(self, req: BattleRequest):
        self.ally = [self._init_ship(s, "ally") for s in req.allyShips]
        self.enemy = [self._init_ship(s, "enemy") for s in req.enemyShips]
        self.mode = req.mode
        self.bomb_dist = req.bombDistance
        self.max_time = req.maxTime
        self.time = 0.0
        self.logs = []
        self.ally_escort_alive = any(s.is_escort and s.alive for s in self.ally)
        self.enemy_escort_alive = any(s.is_escort and s.alive for s in self.enemy)

    def _init_ship(self, data: ShipData, side: str):
        weapons = []
        for w in data.weapons:
            weapons.append({
                "data": w,
                "phase": "cooldown",
                "cd_remain": random.uniform(0, w.cooldown * 0.5),
                "lock_remain": 0.0,
                "atk_remain": 0.0,
                "shots_fired": 0,
                "total_shots": w.attacks * w.ammo,
                "target": None,
            })
        systems = {}
        for sys_name, ratio in SYS_HP_RATIOS.items():
            systems[sys_name] = {"hp": data.hp * ratio, "max_hp": data.hp * ratio, 
                                "destroyed": False, "permanent": False, 
                                "repair_count": 0, "repair_timer": 0}
        return {
            "id": data.id, "name": data.name, "type": data.type,
            "position": data.position, "side": side,
            "max_hp": data.hp, "current_hp": data.hp,
            "physical_armor": data.physicalArmor + data.physResistBonus,
            "energy_armor": data.energyArmor + data.energyResistBonus,
            "evasion": data.evasion,
            "is_super_cap": data.isSuperCapital,
            "is_carrier": data.isCarrier,
            "is_escort": data.isEscort,
            "is_escorted": data.isEscorted,
            "is_flagship": data.isFlagship,
            "alive": True, "weapons": weapons,
            "systems": systems,
            "dmg_bonus": data.dmgBonus,
            "total_dmg_dealt": 0.0, "total_dmg_taken": 0.0,
        }

    def simulate(self) -> BattleResponse:
        dt = 0.1
        while self.time < self.max_time:
            self.time += dt
            # Update escort status
            self.ally_escort_alive = any(s["alive"] for s in self.ally if s["is_escort"])
            self.enemy_escort_alive = any(s["alive"] for s in self.enemy if s["is_escort"])
            
            # Process weapons
            ally_alive = [s for s in self.ally if s["alive"]]
            enemy_alive = [s for s in self.enemy if s["alive"]]
            
            for ship in self.ally:
                if ship["alive"]: self._process_ship(ship, enemy_alive, dt)
            for ship in self.enemy:
                if ship["alive"]: self._process_ship(ship, ally_alive, dt)
            
            # Process repairs
            for ship in self.ally + self.enemy:
                if ship["alive"]: self._process_repairs(ship, self.ally if ship["side"]=="ally" else self.enemy, dt)
            
            # Process system repairs
            for ship in self.ally + self.enemy:
                self._process_system_repairs(ship, dt)
            
            # Check win
            if not any(s["alive"] for s in self.ally):
                return self._build_response("enemy")
            if not any(s["alive"] for s in self.enemy):
                return self._build_response("ally")
        
        return self._build_response("timeout")

    def _process_ship(self, ship, enemies, dt):
        if not enemies: return
        for ws in ship["weapons"]:
            w = ws["data"]
            if ws["phase"] == "cooldown":
                ws["cd_remain"] -= dt
                if ws["cd_remain"] <= 0:
                    ws["phase"] = "lock"
                    ws["lock_remain"] = w.lockTime
            elif ws["phase"] == "lock":
                ws["lock_remain"] -= dt
                ws["target"] = random.choice(enemies) if enemies else None
                if ws["lock_remain"] <= 0 and ws["target"]:
                    ws["phase"] = "attack"
                    ws["atk_remain"] = w.atkDuration
                    ws["shots_fired"] = 0
                    if w.atkDuration <= 0:
                        self._fire_all(ship, ws["target"], w, ws)
                        ws["phase"] = "cooldown"
                        ws["cd_remain"] = w.cooldown
            elif ws["phase"] == "attack":
                ws["atk_remain"] -= dt
                t = ws["target"]
                if t and t["alive"] and w.atkDuration > 0:
                    n = max(1, int(ws["total_shots"] * (dt / max(0.01, w.atkDuration))))
                    for _ in range(min(n, ws["total_shots"] - ws["shots_fired"])):
                        self._execute_shot(ship, t, w)
                        ws["shots_fired"] += 1
                if ws["atk_remain"] <= 0 or ws["shots_fired"] >= ws["total_shots"]:
                    ws["phase"] = "cooldown"
                    ws["cd_remain"] = w.cooldown
                    ws["target"] = None

    def _fire_all(self, ship, target, w, ws):
        for _ in range(w.attacks * w.ammo):
            if not target["alive"]: break
            self._execute_shot(ship, target, w)

    def _execute_shot(self, attacker, target, w):
        # 1. Hit check
        hit = calc_hit_chance(w.hitMin, w.hitMax, target["evasion"], self.bomb_dist)
        if random.random() > hit: return
        
        # 2. Intercept
        if not w.cannotBeIntercepted:
            friends = self.ally if target["side"] == "ally" else self.enemy
            same_row = [s.get("intercept_rate", 0)/100 for s in friends if s["alive"] and s.get("position") == target["position"]]
            global_r = [s.get("intercept_rate", 0)/100 for s in friends if s["alive"] and s.get("position") != target["position"]]
            intercept_p = calc_intercept_rate(w.interceptRate/100, same_row, global_r)
            if random.random() < intercept_p: return
        
        # 3. Escort protection
        if target["is_escorted"]:
            if (target["side"] == "ally" and self.ally_escort_alive) or \
               (target["side"] == "enemy" and self.enemy_escort_alive):
                return
        
        # 4. Damage calculation (战斗机制.txt 修正公式)
        tech_bonus = w.singleDmg * (attacker.get("dmg_bonus", 0) / 100.0)
        base = w.singleDmg
        
        if w.dmgType == "energy":
            shield = target["energy_armor"]
            if shield >= 100: return
            dmg = calc_energy_damage(base, tech_bonus, shield)
        else:
            armor = target["physical_armor"]
            dmg = calc_physical_damage(base, tech_bonus, armor)
        
        # 5. Crit
        if w.crit and random.random() < CRIT_BASE:
            dmg *= 1.5
        
        # 6. Flagship protection
        friends = self.ally if target["side"] == "ally" else self.enemy
        if any(s["is_flagship"] and s["alive"] for s in friends if "普卢托斯" in s.get("name", "")):
            dmg *= (1.0 - PLUTUS_REDUCTION)
        
        dmg = max(0, round(dmg))
        target["current_hp"] -= dmg
        attacker["total_dmg_dealt"] = attacker.get("total_dmg_dealt", 0) + dmg
        target["total_dmg_taken"] = target.get("total_dmg_taken", 0) + dmg
        
        # 7. System damage
        if w.subSystemTargets and target["systems"]:
            for sys_name, eff in w.subSystemTargets.items():
                sys = target["systems"].get(sys_name)
                if sys and not sys["destroyed"] and not sys["permanent"]:
                    if random.random() < SYS_EFFICIENCY.get(eff, 0.2):
                        sys_dmg = calc_system_damage(base, tech_bonus, w.systemDmgCoeff)
                        sys["destroyed"] = True
                        sys["repair_timer"] = 25.0
                        target["current_hp"] -= target["max_hp"] * 0.05
                        self.logs.append(f"[{self.time:.1f}s] {target['name']}的{sys_name}被破坏!")
                        break
        
        # 8. Random system damage
        if random.random() < SYS_CHANCE and target["systems"]:
            active = [(k, v) for k, v in target["systems"].items() if not v["destroyed"] and not v["permanent"] and k != "propulsion"]
            if active:
                k, v = random.choice(active)
                v["destroyed"] = True
                v["repair_timer"] = 25.0
                target["current_hp"] -= target["max_hp"] * 0.05
                self.logs.append(f"[{self.time:.1f}s] 🔧 {target['name']}的{k}被随机破坏!")
        
        # 9. Death
        if target["current_hp"] <= 0:
            target["current_hp"] = 0
            target["alive"] = False
            self.logs.append(f"[{self.time:.1f}s] 💀 {attacker['name']} 击毁 {target['name']}")

    def _process_repairs(self, ship, friends, dt):
        for ws in ship["weapons"]:
            r_dpm = ws["data"].repairDpm
            if r_dpm <= 0: continue
            damaged = [f for f in friends if f["alive"] and f["current_hp"] < f["max_hp"]]
            if not damaged: continue
            target = min(damaged, key=lambda f: f["current_hp"] / max(f["max_hp"], 1))
            repair = (r_dpm / 60.0) * dt * (1.0 + target["physical_armor"] * 0.0025)
            repair = min(repair, r_dpm / 60.0 * 2.5 * dt)  # 150%上限
            target["current_hp"] = min(target["max_hp"], target["current_hp"] + repair)

    def _process_system_repairs(self, ship, dt):
        for sys_name, sys_data in ship["systems"].items():
            if sys_data["destroyed"] and not sys_data["permanent"]:
                sys_data["repair_timer"] -= dt
                if sys_data["repair_timer"] <= 0:
                    limit = SYS_REPAIR_LIMITS.get(sys_name, 1)
                    sys_data["repair_count"] += 1
                    if sys_data["repair_count"] <= limit:
                        sys_data["destroyed"] = False
                        sys_data["hp"] = sys_data["max_hp"]
                        self.logs.append(f"[{self.time:.1f}s] 🔧 {ship['name']}的{sys_name}已修复")
                    else:
                        sys_data["permanent"] = True
                        self.logs.append(f"[{self.time:.1f}s] 💔 {ship['name']}的{sys_name}永久损毁!")

    def _build_response(self, winner) -> BattleResponse:
        return BattleResponse(
            winner=winner,
            duration=round(self.time, 1),
            allyTotalDamage=sum(s["total_dmg_dealt"] for s in self.ally),
            enemyTotalDamage=sum(s["total_dmg_dealt"] for s in self.enemy),
            allyShipsLost=sum(1 for s in self.ally if not s["alive"]),
            enemyShipsLost=sum(1 for s in self.enemy if not s["alive"]),
            allyShips=[ShipResult(
                id=s["id"], name=s["name"],
                initialHp=s["max_hp"], finalHp=max(0, s["current_hp"]),
                damageDealt=s["total_dmg_dealt"], damageTaken=s["total_dmg_taken"],
                alive=s["alive"],
                systemsDestroyed=[k for k, v in s["systems"].items() if v["destroyed"] or v["permanent"]]
            ) for s in self.ally],
            enemyShips=[ShipResult(
                id=s["id"], name=s["name"],
                initialHp=s["max_hp"], finalHp=max(0, s["current_hp"]),
                damageDealt=s["total_dmg_dealt"], damageTaken=s["total_dmg_taken"],
                alive=s["alive"],
                systemsDestroyed=[k for k, v in s["systems"].items() if v["destroyed"] or v["permanent"]]
            ) for s in self.enemy],
            logs=self.logs[-100:],
            dpsAnalysis={
                "allyTotalDps": sum(
                    sum(w["data"].singleDmg * w["data"].attacks * w["data"].ammo / max(w["data"].cooldown, 1)
                    for w in s["weapons"]) for s in self.ally if s["alive"]
                ),
                "enemyTotalDps": sum(
                    sum(w["data"].singleDmg * w["data"].attacks * w["data"].ammo / max(w["data"].cooldown, 1)
                    for w in s["weapons"]) for s in self.enemy if s["alive"]
                ),
                "time": self.time,
            }
        )

@router.post("/simulate", response_model=BattleResponse)
async def simulate_battle(req: BattleRequest):
    """执行精确战斗模拟，使用战斗机制.txt完整公式"""
    sim = BattleSimulator(req)
    return sim.simulate()

@router.post("/quick-calc")
async def quick_damage_calc(data: dict):
    """快速伤害计算：输入武器参数和目标属性，返回伤害"""
    base = data.get("singleDmg", 100)
    tech = data.get("techBonus", 0)
    dmg_type = data.get("dmgType", "physical")
    shield = data.get("energyShield", 5)
    armor = data.get("physicalArmor", 10)
    
    if dmg_type == "energy":
        dmg = calc_energy_damage(base, tech, shield)
        formula = f"({base}+{tech}-{base}×{shield}%)×{TUNE}"
    else:
        dmg = calc_physical_damage(base, tech, armor)
        formula = f"({base}+{tech})×{TUNE}-{armor}" if (base+tech)*TUNE > armor else f"({base}+{tech})/10×{TUNE}"
    
    return {"damage": round(dmg, 1), "formula": formula}
