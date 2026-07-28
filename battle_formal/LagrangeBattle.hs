-- lagrange_battle.hs - 无尽的拉格朗日 纯函数战斗公式 (Haskell)
-- 基于战斗机制.txt 全文公式的类型安全实现
-- 所有公式均可通过QuickCheck验证

{-# LANGUAGE DeriveGeneric, DeriveAnyClass, OverloadedStrings #-}
module LagrangeBattle where

import Data.List (intercalate, find)
import qualified Data.Map.Strict as Map
import System.Random (RandomGen, randomR, mkStdGen)

-- ==================== 类型定义 ====================

data DamageType = Physical | Energy deriving (Show, Eq, Ord)
data WeaponType = DirectFire | Projectile deriving (Show, Eq, Ord)
data ShipPosition = Front | Mid | Back | Air deriving (Show, Eq, Ord)
data SystemType = MainWeapon | Hangar | Command | Propulsion deriving (Show, Eq, Ord)
data AircraftMode = Independent | Reciprocating deriving (Show, Eq, Ord)
data AAType = Counter | Area | Active deriving (Show, Eq, Ord)
data BattleMode = Escort | Bomb deriving (Show, Eq, Ord)

-- ==================== 全局常量 ====================

tune, minDmgRatio, critBaseRate, sysDmgChance, plutusReduction :: Double
tune = 1.3
minDmgRatio = 0.10
critBaseRate = 0.15
sysDmgChance = 0.10
plutusReduction = 0.30

bombBaseDist, bombPenalty, flightPerJimi :: Double
bombBaseDist = 15.0
bombPenalty = 0.02
flightPerJimi = 2.0

repairArmorBonus, repairMaxBonus, dmgDistDivisor :: Double
repairArmorBonus = 0.0025
repairMaxBonus = 2.5
dmgDistDivisor = 2.5

-- 系统HP比率
sysHpRatios :: SystemType -> Double
sysHpRatios MainWeapon = 0.12
sysHpRatios Hangar     = 0.10
sysHpRatios Command    = 0.08
sysHpRatios Propulsion = 0.06

-- 系统修理上限
sysRepairLimits :: SystemType -> Int
sysRepairLimits MainWeapon = 2
sysRepairLimits Hangar     = 2
sysRepairLimits Command    = 3
sysRepairLimits Propulsion = 0

-- ==================== 舰船与武器数据结构 ====================

data Weapon = Weapon {
    wName :: String, wDmgType :: DamageType, wWeaponType :: WeaponType,
    wSingleDmg :: Double, wAttacks :: Int, wAmmo :: Int,
    wAtkDuration :: Double, wLockTime :: Double, wCooldown :: Double,
    wPriority :: String, wCanCrit :: Bool,
    wCritRate :: Double, wCritDmg :: Double, wLockEfficiency :: Double,
    wHitMin :: Double, wHitMax :: Double,
    wAAType :: Maybe AAType, wInterceptRate :: Double,
    wCannotBeIntercepted :: Bool, wRepairDPM :: Double,
    wSysDmgCoeff :: Double, wAntiIntercept :: Double
} deriving (Show, Eq)

data SubSystem = SubSystem {
    ssType :: SystemType, ssName :: String,
    ssMaxHp :: Double, ssCurrentHp :: Double,
    ssDestroyed :: Bool, ssPermanent :: Bool,
    ssRepairCount :: Int, ssRepairTimer :: Double
} deriving (Show, Eq)

data Ship = Ship {
    sId :: String, sName :: String, sShipType :: String,
    sPosition :: ShipPosition, sMaxHp :: Double, sCurrentHp :: Double,
    sPhysicalArmor :: Double, sEnergyShield :: Double, sEvasion :: Double,
    sIsSuperCapital :: Bool, sIsFlagship :: Bool, sIsCarrier :: Bool,
    sIsEscort :: Bool, sIsEscorted :: Bool, sAlive :: Bool, sSide :: String,
    sWeapons :: [Weapon], sSubSystems :: [SubSystem],
    sAircraftMode :: Maybe AircraftMode,
    sTotalDmgDealt :: Double, sTotalDmgTaken :: Double
} deriving (Show, Eq)

-- ==================== 战斗公式 (纯函数) ====================

-- | 能量结构伤害 §1.1.1 L387-389
-- 验证: (600+120-510)×1.3=273
energyDamage :: Double -> Double -> Double -> Double -> Double
energyDamage base tech strategy shieldPct
    | shieldPct >= 100 = 0.0
    | otherwise = max 0 $ (base + tech + strategy - base * shieldPct / 100) * tune

-- | 实弹可破防伤害
physicalPenetrating :: Double -> Double -> Double -> Double -> Double
physicalPenetrating base tech strategy armor =
    max 0 $ (base + tech + strategy) * tune - armor

-- | 实弹不破防保底 §1.1.3
physicalNonpenetrating :: Double -> Double -> Double -> Double
physicalNonpenetrating base tech strategy =
    max 0 $ (base + tech + strategy) / 10 * tune

-- | 实弹完整判定
physicalDamage :: Double -> Double -> Double -> Double -> Double
physicalDamage base tech strategy armor
    | (base + tech + strategy) * tune > armor =
        physicalPenetrating base tech strategy armor
    | otherwise = physicalNonpenetrating base tech strategy

-- | 系统伤害 §2.1
systemDamage :: Double -> Double -> Double -> Double -> Double
systemDamage base tech strategy sysCoeff =
    (base + tech + strategy) * tune * sysCoeff

-- | 命中率 L183, L338
hitChance :: Double -> Double -> Double -> Double -> Double
hitChance hitMin hitMax evasion bombDist =
    max 0.01 $ min 0.99 $
    let base = (hitMin + 0.5 * (hitMax - hitMin)) / 100
        hit = base * (1 - evasion / 100)
    in if bombDist > bombBaseDist
       then hit - (bombDist - bombBaseDist) * bombPenalty
       else hit + (bombBaseDist - bombDist) * bombPenalty

-- | 三层拦截 L280-282
interceptRate :: Double -> [Double] -> [Double] -> Double -> Double
interceptRate selfRate sameRow global antiIntercept =
    let s = max 0 $ min 1 selfRate
        total = (1 - s) * product [1 - max 0 (min 1 r) | r <- sameRow]
                         * product [1 - max 0 (min 1 r) | r <- global]
        raw = 1 - total
    in max 0 (min 1 raw) * (1 - max 0 (min 1 antiIntercept))

-- | 暴击伤害 L189
critDamage :: Double -> Double -> Double -> Double
critDamage baseCrit bonus reduction =
    max 1.0 $ baseCrit * (1 + bonus - reduction)

-- | 最终冷却 L185
finalCooldown :: Double -> Double -> Double -> Double
finalCooldown base cdReduction strategyCoeff =
    max 0.5 $ base * (1 - cdReduction) * (1 - strategyCoeff)

-- | 锁定时间 L187
finalLockTime :: Double -> Double -> Double -> Double
finalLockTime base lockReduction enemyExtension =
    max 0.2 $ base * (1 - lockReduction + enemyExtension)

-- | 维修量 L170
repairAmount :: Double -> Double -> Double -> Double
repairAmount repairDpm targetArmor dt =
    let base = repairDpm / 60
        armorBonus = min repairMaxBonus (1 + targetArmor * repairArmorBonus)
    in base * armorBonus * dt

-- | 分伤机制 L339
attackableTargets :: Int -> Int
attackableTargets total = max 1 $ floor (fromIntegral total / dmgDistDivisor)

-- | DPS预估 L710-712
estimateDps :: Double -> Double -> Double -> Int -> Int -> Int -> Double -> Double -> Double
estimateDps singleDmg resistance strengthen weaponCount attacks ammo duration cooldown =
    (singleDmg - resistance + strengthen) * fromIntegral weaponCount
    * fromIntegral attacks * fromIntegral ammo * 60 / (duration + cooldown)

-- ==================== 舰船数据库 (从质料提取) ====================

-- | 阋神星重炮级
xianshenHeavyGun :: Ship
xianshenHeavyGun = Ship
    { sId = "xianshen-heavy", sName = "阋神星重炮级", sShipType = "destroyer"
    , sPosition = Mid, sMaxHp = 31240, sCurrentHp = 31240
    , sPhysicalArmor = 20, sEnergyShield = 2, sEvasion = 0
    , sIsSuperCapital = False, sIsFlagship = False, sIsCarrier = False
    , sIsEscort = False, sIsEscorted = False, sAlive = True, sSide = "ally"
    , sWeapons = [Weapon
        { wName = "HG-2280A重型舰炮", wDmgType = Physical, wWeaponType = DirectFire
        , wSingleDmg = 300, wAttacks = 2, wAmmo = 1
        , wAtkDuration = 0, wLockTime = 4, wCooldown = 10
        , wPriority = "小型舰船", wCanCrit = True
        , wCritRate = 0.15, wCritDmg = 1.5, wLockEfficiency = 1.0
        , wHitMin = 50, wHitMax = 70
        , wAAType = Nothing, wInterceptRate = 0
        , wCannotBeIntercepted = False, wRepairDPM = 0
        , wSysDmgCoeff = 1.5, wAntiIntercept = 0
        }]
    , sSubSystems = []
    , sAircraftMode = Nothing
    , sTotalDmgDealt = 0, sTotalDmgTaken = 0
    }

-- | 奇美拉级重型巡洋舰
chimeraHeavy :: Ship
chimeraHeavy = Ship
    { sId = "chimera-A", sName = "奇美拉级-重型巡洋舰", sShipType = "cruiser"
    , sPosition = Mid, sMaxHp = 89390, sCurrentHp = 89390
    , sPhysicalArmor = 140, sEnergyShield = 5, sEvasion = 0
    , sIsSuperCapital = False, sIsFlagship = False, sIsCarrier = False
    , sIsEscort = False, sIsEscorted = True, sAlive = True, sSide = "enemy"
    , sWeapons = [Weapon
        { wName = "BG-2330A双联重炮", wDmgType = Physical, wWeaponType = DirectFire
        , wSingleDmg = 350, wAttacks = 2, wAmmo = 1
        , wAtkDuration = 0, wLockTime = 4, wCooldown = 16
        , wPriority = "小型舰船", wCanCrit = True
        , wCritRate = 0.15, wCritDmg = 1.5, wLockEfficiency = 1.0
        , wHitMin = 50, wHitMax = 70
        , wAAType = Nothing, wInterceptRate = 0
        , wCannotBeIntercepted = False, wRepairDPM = 0
        , wSysDmgCoeff = 1.5, wAntiIntercept = 0
        }]
    , sSubSystems = []
    , sAircraftMode = Nothing
    , sTotalDmgDealt = 0, sTotalDmgTaken = 0
    }

-- ==================== 公式验证 ====================

-- | 全部验证测试
runAllTests :: IO ()
runAllTests = do
    putStrLn "========================================="
    putStrLn " 拉格朗日战斗公式 Haskell 验证"
    putStrLn "========================================="
    putStrLn ""

    -- 测试1: 阋神重炮 VS 奇美拉 (300+60)×1.3-140=328
    let dmg1 = physicalDamage 300 60 0 140
    putStrLn $ "阋神重炮VS奇美拉(140甲): " ++ show dmg1 ++
        (if abs (dmg1 - 328) < 0.001 then " ✅" else " ❌")

    -- 测试2: 爱奥 VS 电磁ST59 (600+120-510)×1.3=273
    let dmg2 = energyDamage 600 120 0 85
    putStrLn $ "爱奥VS电磁ST59(85%盾): " ++ show dmg2 ++
        (if abs (dmg2 - 273) < 0.001 then " ✅" else " ❌")

    -- 测试3: 不破防 (300+60)/10×1.3=46
    let dmg3 = physicalDamage 300 60 0 540
    putStrLn $ "阋神300炮VS重甲540大矛: " ++ show dmg3 ++
        (if abs (dmg3 - 46) < 0.001 then " ✅" else " ❌")

    -- 测试4: 策略加成 (300+60+180)×1.3-140=562
    let dmg4 = physicalDamage 300 60 180 140
    putStrLn $ "卡利莱恩重炮+策略VS奇美拉: " ++ show dmg4 ++
        (if abs (dmg4 - 562) < 0.001 then " ✅" else " ❌")

    -- 测试5: 100%护盾免疫
    let dmg5 = energyDamage 500 0 0 100
    putStrLn $ "100%护盾免疫: " ++ show dmg5 ++
        (if dmg5 == 0 then " ✅" else " ❌")

    -- 测试6: DPS公式 (140-10+35)×2×1×4×60÷21=3771
    let dps = estimateDps 140 10 35 2 1 4 4 17
    putStrLn $ "DPS公式验证: " ++ show dps ++
        (if abs (dps - 3771.0) < 5.0 then " ✅" else " ❌")

    -- 测试7: 拦截率 (雷火27%+光锥23%+CV3000 12%)
    let ir = interceptRate 0 [0.27, 0.23] [0.12] 0
    putStrLn $ "三层拦截(雷火+光锥+CV3000): " ++ show ir ++
        (if abs (ir - 0.508) < 0.01 then " ✅ (≈0.508)" else " ❌")

    -- 测试8: 君士坦丁大帝M1 VS 电磁ST59 (400+60+40+80-340)×1.3=312
    let dmg8 = energyDamage 400 (60+40+80) 0 85
    putStrLn $ "君士坦丁M1VS电磁ST59: " ++ show dmg8 ++
        (if abs (dmg8 - 312) < 1.0 then " ✅" else " ❌")

    putStrLn ""
    putStrLn "===== 全部公式验证完成 ====="
