-- BattleFormulas.hs - 拉格朗日战斗公式形式化规约
-- 
-- 使用Haskell类型系统对所有战斗公式进行严格的类型定义和代数建模。
-- 包含伤害计算、拦截率、命中率、暴击、冷却等完整的战斗公式。
--
-- 模块: BattleFormulas
-- 版本: 1.0.0
-- 许可: MIT

{-# LANGUAGE OverloadedStrings #-}
{-# LANGUAGE DeriveGeneric #-}
{-# LANGUAGE DeriveAnyClass #-}

module BattleFormulas
  ( -- * 类型定义
    DamageType(..)
  , WeaponType(..)
  , ShipPosition(..)
  , SystemType(..)
  , BattleMode(..)
  , AircraftMode(..)
  , AAType(..)
  , StrategyType(..)
    -- * 舰船类型
  , Ship(..)
  , Weapon(..)
  , Fleet(..)
  , emptyFleet
    -- * 核心战斗公式
  , calcEnergyDamage
  , calcPhysicalDamage
  , calcSystemDamage
  , calcHitChance
  , calcInterceptRate
  , calcMultiShipIntercept
  , calcCritDamage
  , calcCritRate
  , calcFinalCooldown
  , calcFinalLockTime
  , calcRepairAmount
    -- * DPS预估
  , estimateWeaponDPS
  , estimateFleetDPS
    -- * 舰队分析
  , totalFleetHP
  , totalFleetCV
  , averageArmor
  , fleetTypeDistribution
    -- * 常量
  , tuningCoefficient
  , minDamageRatio
  , critBaseRate
  , systemDamageChance
  , plutusDamageReduction
  , bombDistanceBase
  , bombDistancePenalty
  ) where

import Data.List (intercalate, group, sort)
import qualified Data.Map.Strict as Map
import Data.Maybe (fromMaybe)
import Text.Printf (printf)

-- ==================== 枚举类型 ====================

data DamageType = Physical | Energy
  deriving (Show, Read, Eq, Ord, Bounded, Enum)

data WeaponType = DirectFire | Projectile
  deriving (Show, Read, Eq, Ord, Bounded, Enum)

data ShipPosition = Front | Mid | Back | Air
  deriving (Show, Read, Eq, Ord, Bounded, Enum)

data SystemType = MainWeapon | Hangar | Command | Propulsion
  deriving (Show, Read, Eq, Ord, Bounded, Enum)

data BattleMode = Escort | Bomb
  deriving (Show, Read, Eq, Ord, Bounded, Enum)

data AircraftMode = Independent | Reciprocating
  deriving (Show, Read, Eq, Ord, Bounded, Enum)

data AAType = Counter | Area | Active
  deriving (Show, Read, Eq, Ord, Bounded, Enum)

data StrategyType = Offensive | Defensive | Mobility | Flagship | Support | Special
  deriving (Show, Read, Eq, Ord, Bounded, Enum)

-- ==================== 全局常量 ====================

tuningCoefficient :: Double
tuningCoefficient = 1.3

minDamageRatio :: Double
minDamageRatio = 0.10

critBaseRate :: Double
critBaseRate = 0.15

systemDamageChance :: Double
systemDamageChance = 0.10

plutusDamageReduction :: Double
plutusDamageReduction = 0.30

bombDistanceBase :: Double
bombDistanceBase = 15.0

bombDistancePenalty :: Double
bombDistancePenalty = 0.02

systemHpRatios :: Map.Map SystemType Double
systemHpRatios = Map.fromList
  [ (MainWeapon, 0.12)
  , (Hangar, 0.10)
  , (Command, 0.08)
  , (Propulsion, 0.06)
  ]

systemRepairLimits :: Map.Map SystemType Int
systemRepairLimits = Map.fromList
  [ (MainWeapon, 2)
  , (Hangar, 2)
  , (Command, 3)
  , (Propulsion, 0)
  ]

systemDamageCoefficients :: Map.Map String Double
systemDamageCoefficients = Map.fromList
  [ ("standard", 1.25)
  , ("enhanced", 1.5)
  , ("heavy", 3.0)
  ]

-- ==================== 数据类型 ====================

data Weapon = Weapon
  { wName :: String
  , wDamageType :: DamageType
  , wWeaponType :: WeaponType
  , wSingleDamage :: Double
  , wAttacks :: Int
  , wAmmo :: Int
  , wAttackDuration :: Double
  , wLockTime :: Double
  , wCooldown :: Double
  , wPriority :: String
  , wCanCrit :: Bool
  , wCritRate :: Double
  , wCritDamage :: Double
  , wLockEfficiency :: Double
  , wHitRate :: Double
  , wAAType :: Maybe AAType
  , wInterceptRate :: Double
  , wCannotBeIntercepted :: Bool
  , wRepairDPM :: Double
  , wSystemDmgCoeff :: Double
  , wAntiIntercept :: Double
  } deriving (Show, Read, Eq)

data Ship = Ship
  { sId :: String
  , sName :: String
  , sShipType :: String
  , sPosition :: ShipPosition
  , sMaxHP :: Double
  , sCurrentHP :: Double
  , sPhysicalArmor :: Double
  , sEnergyArmorPct :: Double
  , sEvasion :: Double
  , sIsSuperCapital :: Bool
  , sIsFlagship :: Bool
  , sIsCarrier :: Bool
  , sIsEscort :: Bool
  , sIsEscorted :: Bool
  , sAlive :: Bool
  , sWeapons :: [Weapon]
  , sCommandValue :: Double
  } deriving (Show, Read, Eq)

data Fleet = Fleet
  { fName :: String
  , fShips :: [Ship]
  , fSide :: String
  } deriving (Show, Read, Eq)

emptyFleet :: String -> String -> Fleet
emptyFleet name side = Fleet name [] side

-- ==================== 核心战斗公式 ====================

clamp :: Double -> Double -> Double -> Double
clamp x lo hi = min hi (max lo x)

-- | 能量伤害计算
-- 公式: base_dmg * (1 + dmg_bonus - target_shield/100) * tuning * strategy
-- 100%能量抗性 = 完全免疫
calcEnergyDamage :: Double -> Double -> Double -> Double -> Double
calcEnergyDamage baseDmg targetShieldPct dmgBonus strategyCoeff
  | targetShieldPct >= 100.0 = 0.0
  | otherwise = max 0.0 result
  where
    effectiveMult = 1.0 + dmgBonus - (targetShieldPct / 100.0)
    result = baseDmg * effectiveMult * tuningCoefficient * strategyCoeff

-- | 实弹伤害计算
-- 未穿透时保底10%基础伤害
calcPhysicalDamage :: Double -> Double -> Double -> Double -> Double -> Double
calcPhysicalDamage baseDmg targetArmor dmgBonus strategyCoeff armorPen
  | rawDmg <= 0 = max 0.0 (baseDmg * minDamageRatio * tuningCoefficient * strategyCoeff)
  | otherwise = max 0.0 (rawDmg * tuningCoefficient * strategyCoeff)
  where
    effectiveArmor = max 0.0 (targetArmor - armorPen)
    rawDmg = baseDmg * (1.0 + dmgBonus) - effectiveArmor

-- | 系统伤害计算
calcSystemDamage :: Double -> Double -> DamageType -> Double -> Double -> Double
calcSystemDamage baseDmg systemCoeff Energy targetArmor targetShield =
  calcEnergyDamage baseDmg targetShield 0.0 1.0 * systemCoeff
calcSystemDamage baseDmg systemCoeff Physical targetArmor targetShield =
  calcPhysicalDamage baseDmg targetArmor 0.0 1.0 0.0 * systemCoeff

-- | 命中率计算
calcHitChance :: Double -> Double -> Double -> Double -> Double -> Double
calcHitChance baseHit lockEfficiency evasion bombDistance hitBonus =
  clamp finalHit 0.01 0.99
  where
    hit = baseHit * (1.0 + hitBonus - evasion) * lockEfficiency
    distanceMod = if bombDistance > bombDistanceBase
      then -(bombDistance - bombDistanceBase) * bombDistancePenalty
      else (bombDistanceBase - bombDistance) * bombDistancePenalty
    finalHit = hit + distanceMod

-- | 三层拦截率计算
calcInterceptRate :: Double -> [Double] -> [Double] -> Double -> Double
calcInterceptRate selfRate sameRowRates globalRates antiIntercept =
  clamp (intercept * (1.0 - clamp antiIntercept 0.0 1.0)) 0.0 1.0
  where
    clampedSelf = clamp selfRate 0.0 1.0
    total = (1.0 - clampedSelf)
          * product [1.0 - clamp r 0.0 1.0 | r <- sameRowRates]
          * product [1.0 - clamp r 0.0 1.0 | r <- globalRates]
    intercept = 1.0 - total

-- | 多舰拦截叠加
calcMultiShipIntercept :: [Double] -> Double
calcMultiShipIntercept rates
  | null rates = 0.0
  | otherwise = clamp (1.0 - product [1.0 - clamp r 0.0 1.0 | r <- rates]) 0.0 1.0

-- | 暴击伤害倍率
calcCritDamage :: Double -> Double -> Double -> Double
calcCritDamage baseCritDmg critBonus targetReduction =
  max 1.0 (baseCritDmg * (1.0 + critBonus - targetReduction))

-- | 暴击率（上限95%）
calcCritRate :: Double -> Double -> Double
calcCritRate baseRate bonus = clamp (baseRate + bonus) 0.0 0.95

-- | 最终冷却时间（最小0.5秒）
calcFinalCooldown :: Double -> Double -> Double -> Double
calcFinalCooldown baseCooldown reduction strategyCoeff =
  max 0.5 (baseCooldown * (1.0 - reduction) * strategyCoeff)

-- | 最终锁定时间（最小0.2秒）
calcFinalLockTime :: Double -> Double -> Double -> Double
calcFinalLockTime baseLock reduction extension =
  max 0.2 (baseLock * (1.0 - reduction + extension))

-- | 维修量计算
calcRepairAmount :: Double -> Double -> Double -> Double -> Double
calcRepairAmount repairDPM targetArmor dt repairBonus =
  basePerSec * armorBonus * (1.0 + repairBonus) * dt
  where
    basePerSec = repairDPM / 60.0
    armorBonus = min 2.5 (1.0 + targetArmor * 0.0025)

-- ==================== DPS预估 ====================

-- | 预估单武器DPS
estimateWeaponDPS :: Weapon -> Double -> Double -> Double
estimateWeaponDPS w targetArmor targetShield =
  if roundTime <= 0.0 then roundDmg else roundDmg / roundTime
  where
    totalShots = fromIntegral (wAttacks w * wAmmo w)
    critMult = 1.0 + wCritRate w * (wCritDamage w - 1.0)
    effectiveDmg = case wDamageType w of
      Energy -> calcEnergyDamage (wSingleDamage w) targetShield 0.0 1.0
      Physical -> calcPhysicalDamage (wSingleDamage w) targetArmor 0.0 1.0 0.0
    roundDmg = totalShots * effectiveDmg * wHitRate w * critMult
    roundTime = max (wLockTime w) (wCooldown w)

-- | 预估舰队总DPS
estimateFleetDPS :: [Ship] -> Double
estimateFleetDPS ships = sum [estimateWeaponDPS w 20 10 | s <- ships, sAlive s, w <- sWeapons s]

-- ==================== 舰队分析 ====================

totalFleetHP :: [Ship] -> Double
totalFleetHP = sum . map sCurrentHP . filter sAlive

totalFleetCV :: [Ship] -> Double
totalFleetCV = sum . map sCommandValue . filter sAlive

averageArmor :: [Ship] -> Double
averageArmor ships
  | null alive = 0.0
  | otherwise = sum [sPhysicalArmor s | s <- alive] / fromIntegral (length alive)
  where alive = filter sAlive ships

fleetTypeDistribution :: [Ship] -> [(String, Int)]
fleetTypeDistribution = Map.toList . foldr (\s m -> Map.insertWith (+) (sShipType s) 1 m) Map.empty
                       . filter sAlive

-- ==================== 舰队组合验证 ====================

-- | 验证舰队是否满足指挥值限制
validateFleetCV :: Fleet -> Double -> Either String Fleet
validateFleetCV fleet maxCV
  | cv > maxCV = Left $ printf "舰队指挥值 %.0f 超过上限 %.0f" cv maxCV
  | otherwise  = Right fleet
  where cv = totalFleetCV (fShips fleet)

-- | 验证舰队是否有合理的阵型配置
validateFormation :: Fleet -> Either String Fleet
validateFormation fleet
  | null tanks = Left "舰队缺少前排坦克！"
  | null dps   = Left "舰队缺少输出舰船！"
  | otherwise  = Right fleet
  where
    ships = fShips fleet
    tanks = [s | s <- ships, sAlive s, sPosition s == Front]
    dps = [s | s <- ships, sAlive s, sPosition s /= Front]

-- | 分析舰队弱点
analyzeWeaknesses :: Fleet -> [String]
analyzeWeaknesses fleet = concat
  [ if totalFleetHP ships < 100000 then ["舰队总HP过低"] else []
  , if averageArmor ships < 15 then ["平均装甲不足"] else []
  , if null carriers then ["缺少航母支援"] else []
  , if null repairShips then ["缺少维修舰船"] else []
  , if interceptorCount == 0 then ["缺少拦截能力"] else []
  ]
  where
    ships = filter sAlive (fShips fleet)
    carriers = [s | s <- ships, sIsCarrier s]
    repairShips = [s | s <- ships, any (\w -> wRepairDPM w > 0) (sWeapons s)]
    interceptorCount = length [w | s <- ships, w <- sWeapons s, wInterceptRate w > 0]
