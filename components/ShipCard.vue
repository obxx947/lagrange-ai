<template>
  <div
    class="ship-card"
    :class="{
      'ship-card--selected': selected,
      'ship-card--compact': compact,
      [`ship-card--tier-${ship.tier}`]: ship.tier,
    }"
    @click="$emit('select', ship.id)"
  >
    <!-- Card Header -->
    <div class="ship-card__header">
      <div class="ship-card__icon">
        <div class="ship-card__icon-placeholder">{{ ship.name.charAt(0) }}</div>
      </div>
      <div class="ship-card__info">
        <h3 class="ship-card__name">{{ ship.name }}</h3>
        <span class="ship-card__class">{{ ship.ship_class || 'Unknown Class' }}</span>
      </div>
      <span class="ship-card__tier-badge" :class="`tier-${ship.tier}`">
        T{{ ship.tier }}
      </span>
    </div>

    <!-- Star Rating -->
    <div class="ship-card__rating">
      <span
        v-for="star in 5"
        :key="star"
        class="ship-card__star"
        :class="{ 'ship-card__star--filled': star <= ship.rating, 'ship-card__star--empty': star > ship.rating }"
      >&#9733;</span>
    </div>

    <!-- Primary Stats Bars -->
    <div class="ship-card__stats">
      <div class="stat-bar">
        <div class="stat-bar__label">HP</div>
        <div class="stat-bar__track">
          <div
            class="stat-bar__fill stat-bar__fill--hp"
            :style="{ width: hpPercent + '%' }"
          ></div>
        </div>
        <div class="stat-bar__value">{{ formatNumber(ship.hp) }}</div>
      </div>

      <div class="stat-bar">
        <div class="stat-bar__label">ARM</div>
        <div class="stat-bar__track">
          <div
            class="stat-bar__fill stat-bar__fill--armor"
            :style="{ width: armorPercent + '%' }"
          ></div>
        </div>
        <div class="stat-bar__value">{{ formatNumber(ship.armor) }}</div>
      </div>

      <div class="stat-bar">
        <div class="stat-bar__label">SHD</div>
        <div class="stat-bar__track">
          <div
            class="stat-bar__fill stat-bar__fill--shield"
            :style="{ width: shieldPercent + '%' }"
          ></div>
        </div>
        <div class="stat-bar__value">{{ formatNumber(ship.shield) }}</div>
      </div>

      <div class="stat-bar">
        <div class="stat-bar__label">SPD</div>
        <div class="stat-bar__track">
          <div
            class="stat-bar__fill stat-bar__fill--speed"
            :style="{ width: speedPercent + '%' }"
          ></div>
        </div>
        <div class="stat-bar__value">{{ formatNumber(ship.speed) }}</div>
      </div>
    </div>

    <!-- Weapons (compact mode hides this section) -->
    <div v-if="!compact && ship.weapons && ship.weapons.length" class="ship-card__weapons">
      <h4>Weapon Systems</h4>
      <div class="weapon-row" v-for="(weapon, idx) in ship.weapons" :key="idx">
        <span class="weapon-type">{{ weapon.type }}</span>
        <span class="weapon-name">{{ weapon.name }}</span>
        <span class="weapon-dmg">{{ formatNumber(weapon.damage) }} DPS</span>
      </div>
    </div>

    <!-- Quick Stats Grid -->
    <div v-if="!compact" class="ship-card__quick-stats">
      <div class="quick-stat">
        <span class="quick-stat__label">Energy</span>
        <span class="quick-stat__value">{{ formatNumber(ship.energy) }}</span>
      </div>
      <div class="quick-stat">
        <span class="quick-stat__label">Evasion</span>
        <span class="quick-stat__value">{{ ship.evasion }}%</span>
      </div>
      <div class="quick-stat">
        <span class="quick-stat__label">Accuracy</span>
        <span class="quick-stat__value">{{ ship.accuracy }}%</span>
      </div>
      <div class="quick-stat">
        <span class="quick-stat__label">Crit Rate</span>
        <span class="quick-stat__value">{{ ship.crit_rate }}%</span>
      </div>
    </div>

    <!-- Selected Overlay Checkmark -->
    <div v-if="selected" class="ship-card__selected-overlay">
      <span>&#10003;</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  ship: {
    type: Object,
    required: true,
    default: () => ({
      id: '',
      name: 'Unknown Ship',
      ship_class: 'Unknown',
      tier: 1,
      rating: 3,
      hp: 0,
      armor: 0,
      shield: 0,
      speed: 0,
      energy: 0,
      evasion: 0,
      accuracy: 0,
      crit_rate: 0,
      weapons: [],
    }),
  },
  selected: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  maxHp: { type: Number, default: 100000 },
  maxArmor: { type: Number, default: 50000 },
  maxShield: { type: Number, default: 80000 },
  maxSpeed: { type: Number, default: 1000 },
})

defineEmits(['select'])

const hpPercent = computed(() => Math.min(100, (props.ship.hp / props.maxHp) * 100))
const armorPercent = computed(() => Math.min(100, (props.ship.armor / props.maxArmor) * 100))
const shieldPercent = computed(() => Math.min(100, (props.ship.shield / props.maxShield) * 100))
const speedPercent = computed(() => Math.min(100, (props.ship.speed / props.maxSpeed) * 100))

function formatNumber(value) {
  if (!value && value !== 0) return '--'
  return Number(value).toLocaleString()
}
</script>

<style scoped>
.ship-card {
  background: #111827;
  border: 1px solid #1e3a8a;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
  position: relative;
}

.ship-card:hover {
  transform: translateY(-3px);
  border-color: #60a5fa;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.ship-card--selected {
  border-color: #60a5fa;
  box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.25);
}

.ship-card--compact {
  font-size: 12px;
}

.ship-card__header {
  display: flex;
  align-items: center;
  padding: 14px 16px;
  background: linear-gradient(135deg, #151d35, #111827);
  gap: 12px;
}

.ship-card__icon-placeholder {
  width: 44px;
  height: 44px;
  background: #1e3a8a;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: bold;
  color: #93c5fd;
}

.ship-card__info { flex: 1; }

.ship-card__name {
  font-size: 15px;
  font-weight: bold;
  color: #fff;
  margin: 0;
}

.ship-card__class {
  font-size: 11px;
  color: #93c5fd;
}

.ship-card__tier-badge {
  font-size: 10px;
  padding: 3px 10px;
  border-radius: 12px;
  font-weight: bold;
  letter-spacing: 1px;
}

.tier-1 { background: #92400e; color: #fbbf24; }
.tier-2 { background: #4a5568; color: #cbd5e0; }
.tier-3 { background: #713f12; color: #d97706; }

.ship-card__rating {
  text-align: center;
  padding: 8px;
}

.ship-card__star {
  font-size: 16px;
  margin: 0 2px;
}

.ship-card__star--filled { color: #f59e0b; }
.ship-card__star--empty { color: #374151; }

.ship-card__stats {
  padding: 0 16px 12px;
}

.stat-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 6px 0;
  font-size: 11px;
}

.stat-bar__label {
  width: 28px;
  color: #64748b;
  font-weight: bold;
  text-align: right;
}

.stat-bar__track {
  flex: 1;
  height: 6px;
  background: #1e293b;
  border-radius: 3px;
  overflow: hidden;
}

.stat-bar__fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.stat-bar__fill--hp { background: #22c55e; }
.stat-bar__fill--armor { background: #3b82f6; }
.stat-bar__fill--shield { background: #8b5cf6; }
.stat-bar__fill--speed { background: #f59e0b; }

.stat-bar__value {
  min-width: 55px;
  text-align: right;
  font-weight: bold;
  color: #d0d8f0;
}

.ship-card__weapons {
  padding: 0 16px 12px;
  border-top: 1px solid #1e293b;
}

.ship-card__weapons h4 {
  color: #60a5fa;
  font-size: 11px;
  margin: 10px 0 6px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.weapon-row {
  display: flex;
  align-items: center;
  padding: 4px 8px;
  margin: 3px 0;
  background: #0f172a;
  border-radius: 4px;
  font-size: 11px;
  gap: 6px;
}

.weapon-type {
  font-size: 9px;
  background: #1e3a8a;
  color: #93c5fd;
  padding: 1px 6px;
  border-radius: 8px;
}

.weapon-name { flex: 1; }

.weapon-dmg {
  color: #ef4444;
  font-weight: bold;
}

.ship-card__quick-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  padding: 0 16px 12px;
}

.quick-stat {
  display: flex;
  justify-content: space-between;
  background: #0f172a;
  padding: 5px 8px;
  border-radius: 4px;
  font-size: 10px;
}

.quick-stat__label { color: #64748b; }
.quick-stat__value { font-weight: bold; }

.ship-card__selected-overlay {
  position: absolute;
  inset: 0;
  background: rgba(96, 165, 250, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  color: #60a5fa;
}
</style>
