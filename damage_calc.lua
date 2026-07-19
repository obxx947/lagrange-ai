-- ============================================================
-- 拉格朗日AI — Lua 脚本：战斗伤害计算器
-- 用法：lua damage_calc.lua
-- 基于游戏真实公式实现
-- ============================================================

local TUNING_COEFF = 1.3
local MIN_DAMAGE_RATIO = 0.1
local BASE_CRIT_RATE = 0.15

-- 能量伤害计算
local function calcEnergyDamage(baseDmg, targetShieldPct, dmgBonus)
    dmgBonus = dmgBonus or 0
    if targetShieldPct >= 100 then return 0 end
    local effective = baseDmg * (1 + dmgBonus - targetShieldPct / 100)
    return math.max(0, effective * TUNING_COEFF)
end

-- 实弹伤害计算
local function calcPhysicalDamage(baseDmg, targetArmor, dmgBonus)
    dmgBonus = dmgBonus or 0
    local raw = baseDmg * (1 + dmgBonus) - targetArmor
    if raw <= 0 then raw = baseDmg * MIN_DAMAGE_RATIO end
    return math.max(0, raw * TUNING_COEFF)
end

-- 命中率计算
local function calcHitChance(baseHit, lockEff, evasion, bombDist)
    evasion = evasion or 0
    bombDist = bombDist or 15
    local hit = baseHit * (1 - evasion) * (lockEff or 1)
    if bombDist > 15 then
        hit = hit - (bombDist - 15) * 0.02
    else
        hit = hit + (15 - bombDist) * 0.02
    end
    return math.max(0.01, math.min(0.99, hit))
end

-- 暴击伤害
local function calcCritDamage(baseCritDmg, critBonus, targetReduction)
    critBonus = critBonus or 0
    targetReduction = targetReduction or 0
    return baseCritDmg * (1 + critBonus - targetReduction)
end

-- 拦截率(三层)
local function calcInterceptRate(selfRate, sameRow, global)
    local total = 1 - (selfRate or 0)
    for _, r in ipairs(sameRow or {}) do total = total * (1 - r) end
    for _, r in ipairs(global or {}) do total = total * (1 - r) end
    return math.max(0, math.min(1, 1 - total))
end

-- 测试
print("=" .. string.rep("=", 40) .. "\n")
print("  拉格朗日AI — Lua 伤害计算器\n")
print("=" .. string.rep("=", 40) .. "\n\n")

-- 模拟场景：光追级攻击爱奥级
local baseDmg = 350
local targetArmor = 55
local targetShield = 6

local physDmg = calcPhysicalDamage(baseDmg, targetArmor, 0)
local energyDmg = calcEnergyDamage(baseDmg, targetShield, 0)

print(string.format("  光追级(350攻) → 爱奥级(装甲55/护盾6%%):\n"))
print(string.format("    实弹伤害: %.1f\n", physDmg))
print(string.format("    能量伤害: %.1f\n", energyDmg))

local hitChance = calcHitChance(0.75, 1.0, 0, 12)
print(string.format("\n  命中率(12吉米): %.1f%%\n", hitChance * 100))

local intercept = calcInterceptRate(0, {0.1, 0.05}, {0.03})
print(string.format("  拦截率: %.1f%%\n", intercept * 100))

print("\n" .. string.rep("=", 40))
