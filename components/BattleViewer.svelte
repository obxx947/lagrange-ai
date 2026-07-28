<script>
  import { onMount, onDestroy } from 'svelte';

  export let allyFleet = [];
  export let enemyFleet = [];
  export let battleResult = null;
  export let isSimulating = false;
  export let playbackSpeed = 1;

  let currentTime = 0;
  let interval = null;
  let events = [];
  let canvasElement;
  let animationFrameId;
  let particles = [];

  // ---- Reactive: Load battle events when result changes ----
  $: if (battleResult) {
    events = battleResult.logs || battleResult.events || [];
    currentTime = 0;
    initParticles();
  }

  // ---- Reactive: Get filtered events at current time ----
  $: visibleEvents = events.filter(e => {
    const t = e.timestamp || e.time || 0;
    return t <= currentTime;
  });

  $: allyShipsDisplay = allyFleet.map(s => ({
    ...s,
    hpPercent: s.currentHp > 0 ? Math.max(0, (s.currentHp / s.maxHp) * 100) : 0
  }));

  $: enemyShipsDisplay = enemyFleet.map(s => ({
    ...s,
    hpPercent: s.currentHp > 0 ? Math.max(0, (s.currentHp / s.maxHp) * 100) : 0
  }));

  // ---- Particle system for battle effects ----
  function initParticles() {
    particles = [];
    for (let i = 0; i < 30; i++) {
      particles.push({
        x: Math.random() * 100,
        y: Math.random() * 100,
        vx: (Math.random() - 0.5) * 2,
        vy: (Math.random() - 0.5) * 2,
        life: Math.random() * 1,
        size: Math.random() * 3 + 1,
        color: Math.random() > 0.5 ? '#60a5fa' : '#ef4444'
      });
    }
  }

  function animateParticles() {
    if (isSimulating || currentTime < (battleResult?.duration || 0)) {
      particles = particles.map(p => {
        p.x += p.vx * 0.3;
        p.y += p.vy * 0.3;
        p.life -= 0.005;
        if (p.life <= 0) {
          p.x = Math.random() * 100;
          p.y = Math.random() * 100;
          p.life = 1;
        }
        return p;
      });
    }
    animationFrameId = requestAnimationFrame(animateParticles);
  }

  onMount(() => {
    animationFrameId = requestAnimationFrame(animateParticles);
  });

  onDestroy(() => {
    if (interval) clearInterval(interval);
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
  });

  // ---- Playback controls ----
  function startReplay() {
    if (interval) clearInterval(interval);
    currentTime = 0;
    interval = setInterval(() => {
      const maxTime = battleResult?.duration || 60;
      if (currentTime < maxTime) {
        currentTime += 0.5 * playbackSpeed;
      } else {
        clearInterval(interval);
        interval = null;
      }
    }, 50);
  }

  function pauseReplay() {
    if (interval) {
      clearInterval(interval);
      interval = null;
    }
  }

  function resetReplay() {
    pauseReplay();
    currentTime = 0;
  }

  function skipToEnd() {
    pauseReplay();
    currentTime = battleResult?.duration || 60;
  }

  // ---- Stats computation ----
  $: allyLost = allyFleet.filter(s => !s.alive).length;
  $: enemyLost = enemyFleet.filter(s => !s.alive).length;
  $: allyTotalHp = allyFleet.reduce((sum, s) => sum + s.maxHp, 0);
  $: allyCurrentHp = allyFleet.reduce((sum, s) => sum + Math.max(0, s.currentHp), 0);
  $: enemyTotalHp = enemyFleet.reduce((sum, s) => sum + s.maxHp, 0);
  $: enemyCurrentHp = enemyFleet.reduce((sum, s) => sum + Math.max(0, s.currentHp), 0);
  $: allyHpPercent = allyTotalHp > 0 ? (allyCurrentHp / allyTotalHp) * 100 : 0;
  $: enemyHpPercent = enemyTotalHp > 0 ? (enemyCurrentHp / enemyTotalHp) * 100 : 0;
</script>

<div class="battle-viewer">
  <!-- Fleet Display -->
  <div class="fleet-display">
    <!-- Ally Fleet -->
    <div class="fleet fleet--ally">
      <div class="fleet__header">
        <h3>Fleet Alpha ({allyFleet.length} ships)</h3>
        <div class="fleet__hp-summary">
          <div class="hp-bar hp-bar--large">
            <div class="hp-fill hp-fill--ally" style="width: {allyHpPercent}%"></div>
          </div>
          <span class="hp-text">{Math.floor(allyCurrentHp).toLocaleString()} / {allyTotalHp.toLocaleString()}</span>
        </div>
      </div>
      {#each allyShipsDisplay as ship (ship.id || ship.name)}
        <div class="ship-row" class:ship-row--destroyed={!ship.alive}>
          <div class="ship-row__icon"></div>
          <div class="ship-row__info">
            <span class="ship-row__name">{ship.name}</span>
            <span class="ship-row__type">{ship.ship_class || ship.type || ''}</span>
          </div>
          <div class="hp-bar">
            <div class="hp-fill hp-fill--ally" style="width: {ship.hpPercent}%"></div>
          </div>
          <span class="hp-text">{Math.floor(ship.currentHp).toLocaleString()} / {ship.maxHp.toLocaleString()}</span>
        </div>
      {/each}
    </div>

    <!-- VS Divider -->
    <div class="vs-divider">
      <div class="vs-divider__text">VS</div>
      <div class="vs-divider__stats">
        <div class="vs-stat vs-stat--ally">Lost: {allyLost}</div>
        <div class="vs-stat vs-stat--enemy">Lost: {enemyLost}</div>
      </div>
    </div>

    <!-- Enemy Fleet -->
    <div class="fleet fleet--enemy">
      <div class="fleet__header">
        <h3>Fleet Beta ({enemyFleet.length} ships)</h3>
        <div class="fleet__hp-summary">
          <div class="hp-bar hp-bar--large">
            <div class="hp-fill hp-fill--enemy" style="width: {enemyHpPercent}%"></div>
          </div>
          <span class="hp-text">{Math.floor(enemyCurrentHp).toLocaleString()} / {enemyTotalHp.toLocaleString()}</span>
        </div>
      </div>
      {#each enemyShipsDisplay as ship (ship.id || ship.name)}
        <div class="ship-row" class:ship-row--destroyed={!ship.alive}>
          <div class="ship-row__icon"></div>
          <div class="ship-row__info">
            <span class="ship-row__name">{ship.name}</span>
            <span class="ship-row__type">{ship.ship_class || ship.type || ''}</span>
          </div>
          <div class="hp-bar">
            <div class="hp-fill hp-fill--enemy" style="width: {ship.hpPercent}%"></div>
          </div>
          <span class="hp-text">{Math.floor(ship.currentHp).toLocaleString()} / {ship.maxHp.toLocaleString()}</span>
        </div>
      {/each}
    </div>
  </div>

  <!-- Battle Result -->
  {#if battleResult}
    <div class="result-banner" class:result-banner--win={battleResult.winner === 'ally'}
         class:result-banner--lose={battleResult.winner !== 'ally'}>
      {battleResult.winner === 'ally' ? 'VICTORY - Fleet Alpha' : 'DEFEAT - Fleet Beta'}
      <span class="result-banner__duration">Duration: {battleResult.duration?.toFixed(1)}s</span>
    </div>
  {/if}

  <!-- Controls -->
  <div class="controls">
    <button on:click={startReplay} disabled={!battleResult || isSimulating} class="btn btn--play">
      ▶ Play
    </button>
    <button on:click={pauseReplay} class="btn btn--pause">⏸ Pause</button>
    <button on:click={resetReplay} class="btn btn--reset">⏮ Reset</button>
    <button on:click={skipToEnd} class="btn btn--skip">⏭ Skip to End</button>
    <div class="controls__timeline">
      <span class="controls__time">{currentTime.toFixed(1)}s</span>
      <span class="controls__separator">/</span>
      <span class="controls__total">{battleResult?.duration?.toFixed(1) || '0.0'}s</span>
    </div>
    <label class="controls__speed">
      Speed:
      <select bind:value={playbackSpeed}>
        <option value={0.5}>0.5x</option>
        <option value={1}>1x</option>
        <option value={2}>2x</option>
        <option value={4}>4x</option>
      </select>
    </label>
  </div>

  <!-- Event Log -->
  <div class="event-log">
    <h4>Battle Log ({visibleEvents.length} / {events.length} events)</h4>
    <div class="event-log__entries">
      {#each visibleEvents.slice(-20) as evt (evt.timestamp + evt.message)}
        <div class="log-entry" class:log-entry--critical={evt.severity === 'critical'}
             class:log-entry--high={evt.severity === 'high'}>
          <span class="log-entry__time">[{evt.timestamp?.toFixed(1) || '0.0'}s]</span>
          <span class="log-entry__msg">{evt.message || evt}</span>
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .battle-viewer {
    background: #0a0e27;
    border: 1px solid #1e3a8a;
    border-radius: 10px;
    padding: 20px;
    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
    color: #d0d8f0;
  }

  .fleet-display {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    gap: 20px;
    margin-bottom: 20px;
  }

  .fleet {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 14px;
  }

  .fleet--ally { border-left: 3px solid #60a5fa; }
  .fleet--enemy { border-left: 3px solid #ef4444; }

  .fleet__header {
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #1e293b;
  }

  .fleet__header h3 {
    font-size: 14px;
    color: #93c5fd;
    margin: 0 0 8px 0;
  }

  .ship-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    margin: 3px 0;
    background: #0f172a;
    border-radius: 4px;
    transition: opacity 0.3s;
  }

  .ship-row--destroyed {
    opacity: 0.35;
    text-decoration: line-through;
  }

  .ship-row__icon {
    width: 24px;
    height: 24px;
    background: #1e3a8a;
    border-radius: 4px;
    flex-shrink: 0;
  }

  .ship-row__info { flex: 2; min-width: 0; }
  .ship-row__name { font-size: 12px; font-weight: bold; display: block; }
  .ship-row__type { font-size: 10px; color: #64748b; }

  .hp-bar {
    flex: 2;
    height: 6px;
    background: #1e293b;
    border-radius: 3px;
    overflow: hidden;
  }

  .hp-bar--large { height: 8px; }

  .hp-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.4s ease;
  }

  .hp-fill--ally { background: #60a5fa; }
  .hp-fill--enemy { background: #ef4444; }

  .hp-text {
    font-size: 10px;
    min-width: 80px;
    text-align: right;
    color: #94a3b8;
  }

  .vs-divider {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
  }

  .vs-divider__text {
    font-size: 24px;
    font-weight: bold;
    color: #f59e0b;
  }

  .vs-stat {
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 4px;
  }

  .vs-stat--ally { background: rgba(96, 165, 250, 0.15); color: #60a5fa; }
  .vs-stat--enemy { background: rgba(239, 68, 68, 0.15); color: #ef4444; }

  .result-banner {
    text-align: center;
    padding: 16px;
    border-radius: 8px;
    margin: 16px 0;
    font-size: 20px;
    font-weight: bold;
    letter-spacing: 1px;
  }

  .result-banner--win { background: #064e3b33; color: #22c55e; border: 1px solid #22c55e; }
  .result-banner--lose { background: #7f1d1d33; color: #ef4444; border: 1px solid #ef4444; }

  .result-banner__duration {
    display: block;
    font-size: 12px;
    font-weight: normal;
    margin-top: 4px;
    opacity: 0.8;
  }

  .controls {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
    padding: 12px;
    background: #111827;
    border-radius: 8px;
    margin-bottom: 16px;
  }

  .btn {
    padding: 8px 16px;
    border: 1px solid #1e3a8a;
    border-radius: 4px;
    background: #1a2540;
    color: #e0e0e0;
    cursor: pointer;
    font-size: 12px;
    font-weight: bold;
    transition: background 0.2s;
  }

  .btn:hover:not(:disabled) { background: #2a3a5a; }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn--play { background: #059669; border-color: #059669; }

  .controls__timeline {
    margin-left: auto;
    font-size: 13px;
    font-family: 'Consolas', monospace;
    color: #60a5fa;
  }

  .controls__separator { color: #64748b; margin: 0 4px; }

  .controls__speed {
    font-size: 11px;
    color: #93c5fd;
  }

  .controls__speed select {
    background: #0f172a;
    color: #d0d8f0;
    border: 1px solid #1e293b;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
  }

  .event-log {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 8px;
    overflow: hidden;
  }

  .event-log h4 {
    padding: 10px 14px;
    margin: 0;
    font-size: 12px;
    color: #60a5fa;
    background: #0f172a;
    border-bottom: 1px solid #1e293b;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  .event-log__entries {
    max-height: 220px;
    overflow-y: auto;
    padding: 8px;
  }

  .log-entry {
    padding: 5px 10px;
    margin: 2px 0;
    border-radius: 4px;
    font-family: 'Consolas', monospace;
    font-size: 11px;
    border-left: 3px solid transparent;
  }

  .log-entry--critical { border-left-color: #ef4444; background: rgba(239, 68, 68, 0.05); }
  .log-entry--high { border-left-color: #f97316; background: rgba(249, 115, 22, 0.05); }

  .log-entry__time { color: #64748b; margin-right: 8px; }
  .log-entry__msg { color: #d0d8f0; }

  @media (max-width: 768px) {
    .fleet-display { grid-template-columns: 1fr; }
    .vs-divider { flex-direction: row; }
  }
</style>
