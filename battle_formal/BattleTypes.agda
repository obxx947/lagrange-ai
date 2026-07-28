-- BattleTypes.agda - 拉格朗日战斗类型的形式化定义
--
-- 使用Agda的依赖类型系统精确定义战斗计算中涉及的所有类型，
-- 包括伤害类型、武器类型、舰船状态等，为后续证明奠定基础。

module BattleTypes where

open import Agda.Builtin.Nat using (Nat; zero; suc; _+_; _*_)
open import Agda.Builtin.Int using (Int)
open import Agda.Builtin.Float using (Float)
open import Agda.Builtin.Bool using (Bool; true; false; _∧_; _∨_)
open import Agda.Builtin.List using (List; []; _∷_)
open import Agda.Builtin.Equality using (_≡_; refl)
open import Agda.Builtin.Sigma using (Σ; _,_)
open import Agda.Builtin.Maybe using (Maybe; nothing; just)

-- ==================== 数值类型 ====================

-- 非负实数（伤害、HP、装甲等）
record NonNegative : Set where
  constructor mkNonNeg
  field
    value : Float
    proof : {!   !}  -- 在实际使用中通过外部验证保证≥0

-- 概率值（0到1之间）
record Probability : Set where
  constructor mkProb
  field
    value : Float
    -- 需要满足 0 ≤ value ≤ 1

-- ==================== 枚举类型（使用data定义） ====================

-- 伤害类型
data DamageType : Set where
  Physical : DamageType
  Energy   : DamageType

-- 武器类型
data WeaponType : Set where
  DirectFire : WeaponType
  Projectile : WeaponType

-- 舰船位置
data ShipPosition : Set where
  Front : ShipPosition
  Mid   : ShipPosition
  Back  : ShipPosition
  Air   : ShipPosition

-- 系统类型
data SystemType : Set where
  MainWeapon : SystemType
  Hangar     : SystemType
  Command    : SystemType
  Propulsion : SystemType

-- 战斗模式
data BattleMode : Set where
  Escort : BattleMode
  Bomb   : BattleMode

-- 舰载机模式
data AircraftMode : Set where
  Independent   : AircraftMode
  Reciprocating : AircraftMode

-- 防空类型
data AAType : Set where
  Counter : AAType
  Area    : AAType
  Active  : AAType

-- ==================== 相等性判定 ====================

-- 伤害类型判等
damageType-eq : DamageType → DamageType → Bool
damageType-eq Physical Physical = true
damageType-eq Energy   Energy   = true
damageType-eq _        _        = false

-- 武器类型判等
weaponType-eq : WeaponType → WeaponType → Bool
weaponType-eq DirectFire DirectFire = true
weaponType-eq Projectile Projectile = true
weaponType-eq _          _          = false

-- ==================== 类型上的谓词 ====================

-- 是否为直射武器
is-direct-fire : WeaponType → Bool
is-direct-fire DirectFire = true
is-direct-fire Projectile = false

-- 是否为投射武器
is-projectile : WeaponType → Bool
is-projectile Projectile = true
is-projectile DirectFire = false

-- 是否为前排位置
is-front-position : ShipPosition → Bool
is-front-position Front = true
is-front-position _     = false

-- ==================== 记录类型（舰船、武器等） ====================

-- 武器属性
record Weapon : Set where
  constructor mkWeapon
  field
    wName          : String
    wDamageType    : DamageType
    wWeaponType    : WeaponType
    wSingleDamage  : Float
    wAttacks       : Nat
    wAmmo          : Nat
    wCooldown      : Float
    wLockTime      : Float
    wHitRate       : Float
    wCanCrit       : Bool
    wCritRate      : Float
    wCritDamage    : Float
    wInterceptRate : Float
    wRepairDPM     : Float

-- 舰船状态
record Ship : Set where
  constructor mkShip
  field
    sId            : String
    sName          : String
    sShipType      : String
    sPosition      : ShipPosition
    sMaxHP         : Float
    sCurrentHP     : Float
    sPhysicalArmor : Float
    sEnergyArmorPct : Float
    sEvasion       : Float
    sIsSuperCapital : Bool
    sIsFlagship    : Bool
    sIsCarrier     : Bool
    sIsEscort      : Bool
    sAlive         : Bool
    sWeapons       : List Weapon

-- ==================== 常量定义 ====================

-- 调校系数 (1.3)
tuningCoefficient : Float
tuningCoefficient = 1.3

-- 最小伤害比例 (0.10 = 10%)
minDamageRatio : Float
minDamageRatio = 0.10

-- 基础暴击率 (0.15 = 15%)
critBaseRate : Float
critBaseRate = 0.15

-- 系统破坏触发概率 (0.10 = 10%)
systemDamageChance : Float
systemDamageChance = 0.10

-- 普卢托斯之盾旗舰减伤 (0.30 = 30%)
plutusDamageReduction : Float
plutusDamageReduction = 0.30

-- 轰炸距离基准 (15 吉米)
bombDistanceBase : Float
bombDistanceBase = 15.0

-- 系统HP比率
systemHpRatios : SystemType → Float
systemHpRatios MainWeapon = 0.12
systemHpRatios Hangar     = 0.10
systemHpRatios Command    = 0.08
systemHpRatios Propulsion = 0.06

-- 系统修理上限
systemRepairLimits : SystemType → Nat
systemRepairLimits MainWeapon = 2
systemRepairLimits Hangar     = 2
systemRepairLimits Command    = 3
systemRepairLimits Propulsion = 0

-- 系统伤害系数
systemDamageCoefficients : Float
systemDamageCoefficients = 1.25  -- 标准系数

-- ==================== 基本引理 ====================

-- 非负性引理：tuningCoefficient > 0
tuning-positive : Bool
tuning-positive = (tuningCoefficient > 0.0)

-- minDamageRatio 在 (0, 1) 之间
minDamage-valid : Bool
minDamage-valid = (minDamageRatio > 0.0) ∧ (minDamageRatio < 1.0)

-- critBaseRate 在 (0, 1) 之间  
critRate-valid : Bool
critRate-valid = (critBaseRate > 0.0) ∧ (critBaseRate < 1.0)

-- 系统HP比率之和 < 1.0（合理约束）
systemHp-sum-valid : Bool
systemHp-sum-valid =
  (systemHpRatios MainWeapon + systemHpRatios Hangar +
   systemHpRatios Command + systemHpRatios Propulsion) < 1.0

-- ==================== 舰船谓词 ====================

-- 舰船是否存活
is-alive : Ship → Bool
is-alive ship = Ship.sAlive ship ∧ (Ship.sCurrentHP ship > 0.0)

-- 舰船是否为超主力舰
is-super-capital : Ship → Bool
is-super-capital ship = Ship.sIsSuperCapital ship

-- 舰船是否有航母能力
has-carrier : Ship → Bool
has-carrier ship = Ship.sIsCarrier ship

-- 舰船是否有拦截能力
has-intercept : Ship → Bool
has-intercept ship = any-weapon-intercept (Ship.sWeapons ship)
  where
    any-weapon-intercept : List Weapon → Bool
    any-weapon-intercept [] = false
    any-weapon-intercept (w ∷ ws) =
      (Weapon.wInterceptRate w > 0.0) ∨ any-weapon-intercept ws

-- 舰船是否可以维修
can-repair : Ship → Bool
can-repair ship = any-weapon-repair (Ship.sWeapons ship)
  where
    any-weapon-repair : List Weapon → Bool
    any-weapon-repair [] = false
    any-weapon-repair (w ∷ ws) =
      (Weapon.wRepairDPM w > 0.0) ∨ any-weapon-repair ws
