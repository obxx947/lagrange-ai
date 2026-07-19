/**
 * ============================================================
 * 拉格朗日AI — JSX 组件：舰船卡片
 * 用于 React 项目中的舰船展示组件
 * ============================================================
 */

import React from 'react';

const RATING_COLORS = { S: '#f0a020', A: '#9060e0', B: '#3b8bff', C: '#607590', D: '#e04040' };
const TYPE_NAMES = {
  battleship: '战列舰', battlecruiser: '战巡', aircraftcarrier: '航母',
  cruiser: '巡洋舰', destroyer: '驱逐舰', frigate: '护卫舰',
  fighter: '战机', corvette: '护航艇'
};

// 舰船卡片组件
export const ShipCard = ({ ship, onSelect, onAddToFleet }) => {
  const ratings = ship.ratings || {};
  const modCount = ship.modules ? Object.keys(ship.modules).length : 0;

  return (
    <div className="ship-card" onClick={() => onSelect?.(ship)}>
      <div className="ship-header">
        <span className="ship-name">
          {ship.name}{ship.variant}
        </span>
        <span className="ship-type">
          {TYPE_NAMES[ship.type] || ship.type}
        </span>
      </div>

      <div className="ship-stats">
        <Stat label="HP" value={ship.hp?.toLocaleString()} />
        <Stat label="装甲" value={ship.physicalArmor} />
        <Stat label="护盾" value={`${ship.energyArmor}%`} />
        <Stat label="指挥" value={ship.commandValue} />
      </div>

      <div className="ship-ratings">
        {Object.entries(ratings).map(([key, val]) => (
          <span
            key={key}
            className="rating-badge"
            style={{ background: RATING_COLORS[val] || '#555' }}
          >
            {RATING_LABELS[key] || key} {val}
          </span>
        ))}
      </div>

      <div className="ship-footer">
        <span>模块: {modCount}</span>
        {ship.isCarrier && <span className="tag carrier">航母</span>}
        {ship.size === 'large' && <span className="tag super">超主力</span>}
      </div>

      {onAddToFleet && (
        <button
          className="btn-add"
          onClick={(e) => { e.stopPropagation(); onAddToFleet(ship); }}
        >
          + 添加到舰队
        </button>
      )}
    </div>
  );
};

// 统计组件
const Stat = ({ label, value }) => (
  <div className="stat-item">
    <span className="stat-label">{label}</span>
    <span className="stat-value">{value}</span>
  </div>
);

const RATING_LABELS = {
  antiShip: '对舰', antiAir: '防空', siege: '攻城',
  survival: '生存', strategy: '战略'
};

// 舰队面板组件
export const FleetPanel = ({ fleet, side = 'ally', onRemoveShip }) => {
  const totalCV = (fleet.main || []).reduce((s, ship) => s + (ship.commandValue || 0) * (ship.count || 1), 0);
  const totalShips = (fleet.main || []).reduce((s, ship) => s + (ship.count || 1), 0);

  return (
    <div className={`fleet-panel ${side}`}>
      <h3>{side === 'ally' ? '🔵 己方' : '🔴 敌方'}舰队 ({totalShips}艘 / CV:{totalCV})</h3>
      <div className="fleet-ships">
        {(fleet.main || []).map(ship => (
          <div key={ship.id} className="ship-chip" onClick={() => onRemoveShip?.(ship.id)}>
            {ship.name} x{ship.count || 1} ✕
          </div>
        ))}
      </div>
      <div className="cv-bar">
        <div className="cv-fill" style={{ width: `${Math.min(100, totalCV / 5)}%` }} />
      </div>
    </div>
  );
};
