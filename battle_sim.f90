! ============================================================
! 拉格朗日AI — Fortran 90 程序：战斗伤害模拟
! 编译：gfortran -o battle_sim battle_sim.f90
! ============================================================

program battle_simulation
  implicit none
  
  ! 常量定义（游戏公式参数）
  real, parameter :: TUNING_COEFF = 1.3
  real, parameter :: MIN_DAMAGE_RATIO = 0.1
  real, parameter :: BASE_CRIT_RATE = 0.15
  integer, parameter :: MAX_SHIPS = 100
  
  ! 舰船数据结构
  type :: Ship
    character(32) :: name
    real :: hp, max_hp
    real :: armor, shield_pct
    logical :: alive
  end type Ship
  
  ! 战斗状态
  type(Ship), dimension(MAX_SHIPS) :: ally_ships, enemy_ships
  integer :: ally_count, enemy_count
  real :: battle_time
  integer :: i, tick
  real :: dt, dmg, raw_dmg
  real :: rand_val
  
  ! 初始化
  battle_time = 0.0
  dt = 0.1
  
  ! 己方舰队
  ally_count = 3
  ally_ships(1) = Ship("光追级", 85000.0, 85000.0, 45.0, 10.0, .true.)
  ally_ships(2) = Ship("卡利斯托级", 78000.0, 78000.0, 40.0, 8.0, .true.)
  ally_ships(3) = Ship("卡利莱恩级", 12000.0, 12000.0, 12.0, 3.0, .true.)
  
  ! 敌方舰队
  enemy_count = 3
  enemy_ships(1) = Ship("爱奥级", 95000.0, 95000.0, 55.0, 6.0, .true.)
  enemy_ships(2) = Ship("阋神星重炮级", 28000.0, 28000.0, 18.0, 5.0, .true.)
  enemy_ships(3) = Ship("澄海级", 14000.0, 14000.0, 15.0, 2.0, .true.)
  
  print *, "========================================"
  print *, "  拉格朗日AI — Fortran 战斗模拟"
  print *, "========================================"
  print *, "  己方: ", ally_count, " 艘 vs 敌方: ", enemy_count, " 艘"
  print *, ""
  
  ! 战斗循环（最多1000 tick = 100秒）
  do tick = 1, 1000
    battle_time = battle_time + dt
    
    ! 简化伤害：每艘存活舰船攻击对方随机目标
    do i = 1, ally_count
      if (.not. ally_ships(i)%alive) cycle
      call random_number(rand_val)
      
      ! 实弹伤害公式：(基础伤害 - 装甲) × 调校系数
      raw_dmg = 400.0 * dt * (0.5 + rand_val)
      dmg = max(raw_dmg * MIN_DAMAGE_RATIO, &
                (raw_dmg - enemy_ships(mod(i,enemy_count)+1)%armor) * TUNING_COEFF)
      
      enemy_ships(mod(i,enemy_count)+1)%hp = &
        enemy_ships(mod(i,enemy_count)+1)%hp - dmg
      
      if (enemy_ships(mod(i,enemy_count)+1)%hp <= 0) then
        enemy_ships(mod(i,enemy_count)+1)%hp = 0
        enemy_ships(mod(i,enemy_count)+1)%alive = .false.
        print "(A,F5.1,A,A,A)", "[", battle_time, "s] ", &
          trim(ally_ships(i)%name), " 击毁了 ", trim(enemy_ships(mod(i,enemy_count)+1)%name)
      end if
    end do
    
    do i = 1, enemy_count
      if (.not. enemy_ships(i)%alive) cycle
      call random_number(rand_val)
      raw_dmg = 400.0 * dt * (0.5 + rand_val)
      dmg = max(raw_dmg * MIN_DAMAGE_RATIO, &
                (raw_dmg - ally_ships(mod(i,ally_count)+1)%armor) * TUNING_COEFF)
      ally_ships(mod(i,ally_count)+1)%hp = &
        ally_ships(mod(i,ally_count)+1)%hp - dmg
      
      if (ally_ships(mod(i,ally_count)+1)%hp <= 0) then
        ally_ships(mod(i,ally_count)+1)%hp = 0
        ally_ships(mod(i,ally_count)+1)%alive = .false.
        print "(A,F5.1,A,A,A)", "[", battle_time, "s] ", &
          trim(enemy_ships(i)%name), " 击毁了 ", trim(ally_ships(mod(i,ally_count)+1)%name)
      end if
    end do
    
    ! 胜负判定
    if (all(.not. ally_ships(1:ally_count)%alive)) then
      print "(A,F5.1,A)", "  💀 己方全灭！敌方胜利 (", battle_time, "s)"
      exit
    end if
    if (all(.not. enemy_ships(1:enemy_count)%alive)) then
      print "(A,F5.1,A)", "  🏆 敌方全灭！己方胜利 (", battle_time, "s)"
      exit
    end if
  end do
  
  print *, ""
  print *, "========================================"
  
end program battle_simulation
