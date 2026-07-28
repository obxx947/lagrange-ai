-- QuickCheck.hs - 战斗公式QuickCheck属性测试
--
-- 使用QuickCheck对所有战斗公式进行代数性质验证：
-- - 伤害非负性
-- - 能量护盾100%免疫
-- - 实弹保底伤害
-- - 拦截率单调性
-- - 命中率边界约束

module QuickCheck where

import Test.QuickCheck
import Test.QuickCheck.Monadic (assert, monadicIO, run)
import BattleFormulas
import Control.Monad (when)
import Data.List (nub)

-- ==================== 伤害公式属性 ====================

-- | 能量伤害始终非负
prop_energyDamage_nonNegative :: Double -> Double -> Double -> Double -> Property
prop_energyDamage_nonNegative baseDmg shieldPct bonus strat =
  let dmg = calcEnergyDamage (abs baseDmg) (abs shieldPct) bonus strat
  in counterexample ("dmg=" ++ show dmg) (dmg >= 0.0)

-- | 100%能量护盾 → 伤害为0
prop_energyShield_immune :: Double -> Double -> Double -> Property
prop_energyShield_immune baseDmg bonus strat =
  calcEnergyDamage (abs baseDmg) 100.0 bonus strat === 0.0

-- | 护盾越高，伤害越低（单调递减）
prop_energyDamage_shieldMonotonic :: Double -> Double -> Double -> Double -> Property
prop_energyDamage_shieldMonotonic baseDmg shield1 shield2 bonus strat =
  let base = abs baseDmg
      s1 = clamp (abs shield1) 0 99
      s2 = clamp (abs shield2) 0 99
      dmg1 = calcEnergyDamage base s1 bonus strat
      dmg2 = calcEnergyDamage base s2 bonus strat
  in counterexample (show s1 ++ " vs " ++ show s2)
     $ (s1 < s2) ==> (dmg1 >= dmg2 || dmg1 < 1e-10)

-- | 实弹伤害始终非负
prop_physicalDamage_nonNegative :: Double -> Double -> Double -> Double -> Property
prop_physicalDamage_nonNegative baseDmg armor bonus strat =
  let dmg = calcPhysicalDamage (abs baseDmg) (abs armor) bonus strat 0.0
  in counterexample ("dmg=" ++ show dmg) (dmg >= 0.0)

-- | 实弹保底：无论如何至少有10%基础伤害
prop_physicalDamage_minimumFloor :: Double -> Double -> Property
prop_physicalDamage_minimumFloor baseDmg armor =
  let bd = abs baseDmg
      ar = abs armor + 100000.0  -- 超高管甲
      dmg = calcPhysicalDamage bd ar 0.0 1.0 0.0
      expected = bd * minDamageRatio
  in counterexample ("dmg=" ++ show dmg ++ " expected_min=" ++ show expected)
     $ dmg >= expected || bd < 0.01

-- | 伤害加成单调增加伤害
prop_damageBonus_monotonic :: Bool -> Double -> Double -> Double -> Double -> Property
prop_damageBonus_monotonic isEnergy baseDmg bonus1 bonus2 armor =
  let bd = abs baseDmg
      b1 = clamp bonus1 (-1) 10
      b2 = clamp bonus2 (-1) 10
      dmg1 = if isEnergy then calcEnergyDamage bd 10 b1 1.0
             else calcPhysicalDamage bd (abs armor) b1 1.0 0.0
      dmg2 = if isEnergy then calcEnergyDamage bd 10 b2 1.0
             else calcPhysicalDamage bd (abs armor) b2 1.0 0.0
  in counterexample ("bonus1="++show b1++" dmg1="++show dmg1++
                     " bonus2="++show b2++" dmg2="++show dmg2)
     $ (b1 <= b2) ==> (dmg1 <= dmg2 || dmg1 <= 0.0)

-- ==================== 拦截率公式属性 ====================

-- | 拦截率始终在 [0, 1] 区间
prop_interceptRate_bounded :: Double -> [Double] -> [Double] -> Double -> Property
prop_interceptRate_bounded selfRate sameRow global anti =
  let rates = [clamp r 0 1 | r <- sameRow]
      grates = [clamp r 0 1 | r <- global]
      result = calcInterceptRate (clamp selfRate 0 1) rates grates anti
  in counterexample ("rate=" ++ show result) (result >= 0.0 && result <= 1.0)

-- | 增加拦截舰船不会降低总拦截率（单调性）
prop_interceptRate_monotonic :: Double -> [Double] -> Double -> Property
prop_interceptRate_monotonic selfRate rates extraRate =
  let goodRates = [clamp r 0 1 | r <- rates]
      base = calcInterceptRate selfRate goodRates [] 0.0
      withExtra = calcInterceptRate selfRate (goodRates ++ [clamp extraRate 0 1]) [] 0.0
  in counterexample ("base="++show base++" withExtra="++show withExtra)
     $ withExtra >= base - 1e-10

-- | 自身拦截率100% → 总拦截率100%
prop_selfIntercept_full :: [Double] -> Property
prop_selfIntercept_full rates =
  let result = calcInterceptRate 1.0 rates [] 0.0
  in counterexample ("result=" ++ show result) (abs (result - 1.0) < 1e-10)

-- ==================== 命中率公式属性 ====================

-- | 命中率始终在 [0.01, 0.99] 区间
prop_hitChance_bounded :: Double -> Double -> Double -> Double -> Double -> Property
prop_hitChance_bounded baseHit lockEff evasion dist bonus =
  let hit = calcHitChance (abs baseHit) (abs lockEff) evasion dist bonus
  in counterexample ("hit=" ++ show hit) (hit >= 0.01 && hit <= 0.99)

-- | 闪避越高命中越低（单调递减）
prop_evasion_monotonic :: Double -> Double -> Double -> Double -> Double -> Property
prop_evasion_monotonic baseHit lockEff ev1 ev2 dist bonus =
  let e1 = clamp (abs ev1) 0 0.9
      e2 = clamp (abs ev2) e1 0.9
      h1 = calcHitChance baseHit lockEff e1 dist bonus
      h2 = calcHitChance baseHit lockEff e2 dist bonus
  in (e1 <= e2) ==> (h1 >= h2 || h1 < 0.02)

-- ==================== 暴击公式属性 ====================

-- | 暴击倍率 >= 1.0
prop_critDamage_minimum :: Double -> Double -> Double -> Property
prop_critDamage_minimum base bonus reduction =
  calcCritDamage (abs base + 1.0) bonus reduction >= 1.0

-- | 暴击率始终在 [0, 0.95] 区间
prop_critRate_bounded :: Double -> Double -> Property
prop_critRate_bounded base bonus =
  let r = calcCritRate (abs base) bonus
  in r >= 0.0 && r <= 0.95

-- ==================== 冷却公式属性 ====================

-- | 最终冷却 >= 0.5秒
prop_cooldown_minimum :: Double -> Double -> Double -> Property
prop_cooldown_minimum base reduction strat =
  calcFinalCooldown (abs base) reduction strat >= 0.5

-- | 冷却缩减不为负
prop_cooldown_monotonic :: Double -> Double -> Double -> Property
prop_cooldown_monotonic base red1 red2 strat =
  let r1 = clamp red1 0 0.9
      r2 = clamp red2 0 0.9
      cd1 = calcFinalCooldown base r1 strat
      cd2 = calcFinalCooldown base r2 strat
  in (r1 <= r2) ==> cd1 >= cd2

-- ==================== DPS公式属性 ====================

-- | DPS始终非负
prop_dps_nonNegative :: Double -> Int -> Int -> Double -> Double
                     -> Double -> Double -> Double -> Property
prop_dps_nonNegative dmg atk ammo cd lock hit critRate critDmg =
  let dps = estimateWeaponDPS
        (Weapon "test" Physical DirectFire (abs dmg) atk ammo 0.0 lock cd
                "random" True (abs critRate) (abs critDmg + 1.0) 1.0 (abs hit) Nothing 0.0 False 0.0 1.0 0.0)
        20 10
  in dps >= 0.0

-- | DPS与伤害成正比
prop_dps_proportionalToDamage :: Double -> Double -> Property
prop_dps_proportionalToDamage dmg1 dmg2 =
  let d1 = abs dmg1 + 1.0
      d2 = abs dmg2 + 1.0
      w1 = Weapon "test" Physical DirectFire d1 1 1 0.0 1.0 4.0 "random" False 0.0 1.5 1.0 1.0 Nothing 0.0 False 0.0 1.0 0.0
      w2 = Weapon "test" Physical DirectFire d2 1 1 0.0 1.0 4.0 "random" False 0.0 1.5 1.0 1.0 Nothing 0.0 False 0.0 1.0 0.0
      dps1 = estimateWeaponDPS w1 20 10
      dps2 = estimateWeaponDPS w2 20 10
  in (d1 <= d2) ==> (dps1 <= dps2 || d1 < 1e-6)

-- ==================== 批量测试运行 ====================

-- | 运行所有QuickCheck属性测试
runQuickCheckTests :: IO ()
runQuickCheckTests = do
  putStrLn "========================================"
  putStrLn "  拉格朗日战斗公式 QuickCheck 属性测试"
  putStrLn "========================================"
  putStrLn ""

  putStrLn "--- 伤害公式 ---"
  quickCheck (withMaxSuccess 1000 prop_energyDamage_nonNegative)
  quickCheck (withMaxSuccess 100  prop_energyShield_immune)
  quickCheck (withMaxSuccess 1000 prop_physicalDamage_nonNegative)
  quickCheck (withMaxSuccess 500  prop_physicalDamage_minimumFloor)
  quickCheck (withMaxSuccess 500  prop_damageBonus_monotonic)
  quickCheck (withMaxSuccess 500  prop_energyDamage_shieldMonotonic)

  putStrLn "--- 拦截率 ---"
  quickCheck (withMaxSuccess 1000 prop_interceptRate_bounded)
  quickCheck (withMaxSuccess 500  prop_interceptRate_monotonic)
  quickCheck (withMaxSuccess 100  prop_selfIntercept_full)

  putStrLn "--- 命中率 ---"
  quickCheck (withMaxSuccess 1000 prop_hitChance_bounded)
  quickCheck (withMaxSuccess 500  prop_evasion_monotonic)

  putStrLn "--- 暴击 ---"
  quickCheck (withMaxSuccess 1000 prop_critDamage_minimum)
  quickCheck (withMaxSuccess 1000 prop_critRate_bounded)

  putStrLn "--- 冷却 ---"
  quickCheck (withMaxSuccess 1000 prop_cooldown_minimum)
  quickCheck (withMaxSuccess 500  prop_cooldown_monotonic)

  putStrLn "--- DPS ---"
  quickCheck (withMaxSuccess 500  prop_dps_nonNegative)
  quickCheck (withMaxSuccess 500  prop_dps_proportionalToDamage)

  putStrLn ""
  putStrLn "===== 全部QuickCheck测试完成 ====="
