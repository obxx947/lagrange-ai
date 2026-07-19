<!-- ============================================================
  拉格朗日AI — Svelte 组件：舰队构建器
  用于 Svelte 项目
  ============================================================ -->

<script>
  import { createEventDispatcher } from 'svelte';

  export let ships = [];
  export let fleet = { main: [], reinforcement: [], flagship: null };
  export let side = 'ally';
  export let maxCV = 500;

  const dispatch = createEventDispatcher();

  $: totalCV = (fleet.main || []).reduce((s, sh) => s + (sh.commandValue || 0) * (sh.count || 1), 0);
  $: totalShips = (fleet.main || []).reduce((s, sh) => s + (sh.count || 1), 0);
  $: cvPercent = Math.min(100, (totalCV / maxCV) * 100);
  $: cvColor = cvPercent > 90 ? '#e04040' : cvPercent > 70 ? '#f0a020' : '#20b870';

  function addShip(ship) {
    const existing = fleet.main.find(s => s.id === ship.id);
    if (existing) {
      existing.count = (existing.count || 1) + 1;
    } else {
      fleet.main = [...fleet.main, { ...ship, count: 1 }];
    }
    fleet = fleet; // trigger reactivity
    dispatch('fleet-change', { fleet, side });
  }

  function removeShip(shipId) {
    const idx = fleet.main.findIndex(s => s.id === shipId);
    if (idx >= 0) {
      if (fleet.main[idx].count > 1) {
        fleet.main[idx].count--;
      } else {
        fleet.main = fleet.main.filter((_, i) => i !== idx);
      }
    }
    fleet = fleet;
    dispatch('fleet-change', { fleet, side });
  }

  function setFlagship(shipId) {
    fleet.flagship = shipId;
    fleet = fleet;
    dispatch('fleet-change', { fleet, side });
  }
</script>

<div class="fleet-builder" class:ally={side === 'ally'} class:enemy={side === 'enemy'}>
  <div class="fleet-header">
    <h3>{side === 'ally' ? '🔵 己方' : '🔴 敌方'}舰队</h3>
    <span class="fleet-stats">{totalShips}艘 | CV: {totalCV}/{maxCV}</span>
  </div>

  <!-- CV进度条 -->
  <div class="cv-bar">
    <div class="cv-fill" style="width:{cvPercent}%;background:{cvColor}"></div>
  </div>

  <!-- 已添加舰船 -->
  <div class="fleet-ships">
    {#if (fleet.main || []).length === 0}
      <div class="empty-hint">从下方舰船库选择舰船</div>
    {:else}
      {#each fleet.main as ship (ship.id)}
        <div class="ship-chip" on:click={() => removeShip(ship.id)}>
          {ship.name} x{ship.count || 1}
          {#if fleet.flagship === ship.id}
            <span class="flagship-tag">🚩旗舰</span>
          {/if}
          <span class="remove-icon">✕</span>
        </div>
      {/each}
    {/if}
  </div>

  <!-- 快速操作 -->
  <div class="quick-actions">
    <button on:click={() => dispatch('clear-fleet', { side })}>清空</button>
    <button on:click={() => dispatch('save-fleet', { fleet, side })}>💾 保存</button>
  </div>
</div>

<style>
  .fleet-builder {
    background: #1a1f2e; border: 1px solid #2a3045;
    border-radius: 10px; padding: 12px; min-height: 120px;
  }
  .ally { border-left: 3px solid #3b8bff; }
  .enemy { border-left: 3px solid #e04040; }
  .fleet-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .fleet-header h3 { font-size: 13px; color: #e2e8f0; }
  .fleet-stats { font-size: 11px; color: #64748b; }
  .cv-bar { height: 4px; background: #2a3045; border-radius: 2px; margin-bottom: 8px; overflow: hidden; }
  .cv-fill { height: 100%; border-radius: 2px; transition: width 0.3s; }
  .ship-chip {
    display: inline-block; background: #162032; border: 1px solid #2a3045;
    padding: 3px 7px; border-radius: 4px; font-size: 11px; margin: 2px; cursor: pointer;
  }
  .ship-chip:hover { background: #3b8bff; color: #fff; }
  .flagship-tag { color: #f0a020; font-size: 9px; margin-left: 4px; }
  .remove-icon { color: #e04040; margin-left: 4px; }
  .empty-hint { color: #607590; font-size: 12px; text-align: center; padding: 20px; }
  .quick-actions { display: flex; gap: 6px; margin-top: 8px; }
  .quick-actions button {
    padding: 3px 8px; border: 1px solid #2a3045; background: #162032;
    color: #94a3b8; border-radius: 4px; cursor: pointer; font-size: 11px;
  }
</style>
