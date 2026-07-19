/**
 * ============================================================
 * 拉格朗日AI — TSX 组件：战斗模拟面板
 * 用于 React TypeScript 项目
 * ============================================================
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';

// ---- 类型定义 ----
interface BattleShip {
  id: string; name: string; side: 'ally' | 'enemy';
  currentHp: number; maxHp: number; alive: boolean;
  physicalArmor: number; energyArmor: number;
}

interface BattleState {
  allyShips: BattleShip[];
  enemyShips: BattleShip[];
  time: number;
  ended: boolean;
  winner: string;
  logs: string[];
}

// ---- 战斗模拟面板组件 ----
export const BattleSimulator: React.FC<{ fleetConfig: any }> = ({ fleetConfig }) => {
  const [battle, setBattle] = useState<BattleState | null>(null);
  const [speed, setSpeed] = useState<number>(5);
  const [paused, setPaused] = useState<boolean>(false);
  const timerRef = useRef<number | null>(null);

  const startBattle = useCallback(() => {
    // 初始化战斗状态
    const allyShips: BattleShip[] = [];
    const enemyShips: BattleShip[] = [];
    
    ['ally-escort', 'ally-escorted'].forEach(key => {
      const fleet = fleetConfig[key];
      fleet?.main?.forEach((ship: any) => {
        for (let i = 0; i < (ship.count || 1); i++) {
          allyShips.push({
            id: `${ship.id}_${i}`, name: ship.name, side: 'ally',
            currentHp: ship.hp || 10000, maxHp: ship.hp || 10000,
            alive: true, physicalArmor: ship.physicalArmor || 10,
            energyArmor: ship.energyArmor || 5,
          });
        }
      });
    });

    ['enemy-escort', 'enemy-escorted'].forEach(key => {
      const fleet = fleetConfig[key];
      fleet?.main?.forEach((ship: any) => {
        for (let i = 0; i < (ship.count || 1); i++) {
          enemyShips.push({
            id: `${ship.id}_${i}`, name: ship.name, side: 'enemy',
            currentHp: ship.hp || 10000, maxHp: ship.hp || 10000,
            alive: true, physicalArmor: ship.physicalArmor || 10,
            energyArmor: ship.energyArmor || 5,
          });
        }
      });
    });

    setBattle({
      allyShips, enemyShips, time: 0, ended: false, winner: '',
      logs: [`⚔ 战斗开始！己方${allyShips.length}艘 vs 敌方${enemyShips.length}艘`],
    });
    setPaused(false);
  }, [fleetConfig]);

  // 战斗循环
  useEffect(() => {
    if (!battle || battle.ended || paused) return;

    const tick = () => {
      setBattle(prev => {
        if (!prev || prev.ended) return prev;
        const dt = 0.1 * speed;
        const newState = { ...prev, time: prev.time + dt, logs: [...prev.logs] };
        
        // 简化伤害计算
        const processSide = (attackers: BattleShip[], defenders: BattleShip[]) => {
          const aliveDef = defenders.filter(d => d.alive);
          attackers.filter(a => a.alive).forEach(attacker => {
            if (aliveDef.length === 0) return;
            const target = aliveDef[Math.floor(Math.random() * aliveDef.length)];
            const baseDps = 400;
            const raw = baseDps * dt * (0.6 + Math.random() * 0.8);
            const armorRed = Math.max(0.1, target.physicalArmor / 200);
            const shieldRed = 1 - target.energyArmor / 100;
            const dmg = raw * shieldRed * (1 - armorRed);
            
            target.currentHp -= dmg;
            if (target.currentHp <= 0) {
              target.currentHp = 0;
              target.alive = false;
              newState.logs.push(`[${newState.time.toFixed(1)}s] ${attacker.name} 击毁了 ${target.name}`);
            }
          });
        };

        processSide(newState.allyShips, newState.enemyShips);
        processSide(newState.enemyShips, newState.allyShips);

        // 胜负判定
        const allyAlive = newState.allyShips.some(s => s.alive);
        const enemyAlive = newState.enemyShips.some(s => s.alive);
        if (!allyAlive) { newState.ended = true; newState.winner = 'enemy'; }
        if (!enemyAlive) { newState.ended = true; newState.winner = 'ally'; }

        return newState;
      });
    };

    timerRef.current = window.setInterval(tick, 100 / speed);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [battle?.ended, paused, speed]);

  return (
    <div className="battle-simulator">
      <div className="battle-controls">
        <button onClick={startBattle}>▶ 开始模拟</button>
        <button onClick={() => setPaused(!paused)}>{paused ? '▶ 继续' : '⏸ 暂停'}</button>
        <select value={speed} onChange={e => setSpeed(Number(e.target.value))}>
          <option value={1}>1x</option><option value={5}>5x</option><option value={10}>10x</option>
        </select>
        <span>⏱ {battle?.time.toFixed(1)}s</span>
      </div>
      
      <div className="battle-field">
        <div className="side ally">
          <h3>🔵 己方</h3>
          {battle?.allyShips.map(s => (
            <HPBar key={s.id} ship={s} />
          ))}
        </div>
        <div className="side enemy">
          <h3>🔴 敌方</h3>
          {battle?.enemyShips.map(s => (
            <HPBar key={s.id} ship={s} />
          ))}
        </div>
      </div>
      
      <div className="battle-log">
        {battle?.logs.slice(-20).map((log, i) => <div key={i}>{log}</div>)}
      </div>
    </div>
  );
};

const HPBar: React.FC<{ ship: BattleShip }> = ({ ship }) => {
  const pct = Math.max(0, (ship.currentHp / ship.maxHp) * 100);
  const color = pct > 60 ? '#20b870' : pct > 25 ? '#f0a020' : '#e04040';
  return (
    <div className="hp-row">
      <span>{ship.name}{ship.alive ? '' : ' 💀'}</span>
      <div className="hp-bar-bg"><div className="hp-bar-fill" style={{ width: `${pct}%`, background: color }} /></div>
    </div>
  );
};
