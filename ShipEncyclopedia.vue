<!-- ============================================================
  拉格朗日AI — Vue 单文件组件：舰船图鉴
  用于 Vue 3 项目中的舰船浏览组件
  ============================================================ -->

<template>
  <div class="ship-encyclopedia">
    <div class="filters">
      <button
        v-for="cat in categories"
        :key="cat.key"
        :class="{ active: activeCategory === cat.key }"
        @click="activeCategory = cat.key"
      >
        {{ cat.label }}
      </button>
    </div>

    <input
      v-model="searchQuery"
      type="text"
      placeholder="🔍 搜索舰船..."
      class="search-input"
    />

    <div class="ship-grid">
      <div
        v-for="ship in filteredShips"
        :key="ship.id"
        class="ship-card"
        @click="$emit('select-ship', ship)"
      >
        <div class="ship-name">{{ ship.name }}{{ ship.variant }}</div>
        <div class="ship-type">{{ getTypeName(ship.type) }}</div>
        <div class="ship-hp">HP: {{ formatNumber(ship.hp) }}</div>
        <div class="ship-ratings">
          <span
            v-for="(val, key) in ship.ratings"
            :key="key"
            class="rating"
            :class="`rating-${val}`"
          >
            {{ ratingLabels[key] }} {{ val }}
          </span>
        </div>
        <div class="ship-modules" v-if="ship.modules">
          模块: {{ Object.keys(ship.modules).length }}
        </div>
      </div>
    </div>

    <div v-if="filteredShips.length === 0" class="empty">
      未找到匹配舰船
    </div>
  </div>
</template>

<script>
export default {
  name: 'ShipEncyclopedia',
  props: {
    ships: { type: Array, default: () => [] },
  },
  emits: ['select-ship'],
  data() {
    return {
      activeCategory: 'all',
      searchQuery: '',
      categories: [
        { key: 'all', label: '全部' },
        { key: 'battleship', label: '战列舰' },
        { key: 'battlecruiser', label: '战巡' },
        { key: 'aircraftcarrier', label: '航母' },
        { key: 'cruiser', label: '巡洋舰' },
        { key: 'destroyer', label: '驱逐舰' },
        { key: 'frigate', label: '护卫舰' },
        { key: 'fighter', label: '战机' },
        { key: 'corvette', label: '护航艇' },
      ],
      ratingLabels: {
        antiShip: '对舰', antiAir: '防空', siege: '攻城',
        survival: '生存', strategy: '战略',
      },
    };
  },
  computed: {
    filteredShips() {
      let result = this.ships;
      if (this.activeCategory !== 'all') {
        result = result.filter(s => s.type === this.activeCategory);
      }
      if (this.searchQuery) {
        const q = this.searchQuery.toLowerCase();
        result = result.filter(s =>
          s.name.toLowerCase().includes(q) ||
          (s.variant || '').toLowerCase().includes(q)
        );
      }
      return result;
    },
  },
  methods: {
    getTypeName(type) {
      const names = {
        battleship: '战列舰', battlecruiser: '战巡', aircraftcarrier: '航母',
        cruiser: '巡洋舰', destroyer: '驱逐舰', frigate: '护卫舰',
        fighter: '战机', corvette: '护航艇',
      };
      return names[type] || type;
    },
    formatNumber(n) {
      return n?.toLocaleString() || '0';
    },
  },
};
</script>

<style scoped>
.ship-encyclopedia { padding: 16px; }
.filters { display: flex; gap: 4px; margin-bottom: 12px; flex-wrap: wrap; }
.filters button {
  padding: 4px 10px; border: 1px solid #2a3045; background: #1a1f2e;
  color: #94a3b8; border-radius: 4px; cursor: pointer; font-size: 12px;
}
.filters button.active { background: #3b8bff; color: #fff; border-color: #3b8bff; }
.search-input {
  width: 100%; padding: 8px 12px; background: #0f131f; border: 1px solid #2a3045;
  border-radius: 6px; color: #e2e8f0; margin-bottom: 12px;
}
.ship-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }
.ship-card {
  background: #1a1f2e; border: 1px solid #2a3045; border-radius: 8px;
  padding: 10px; cursor: pointer; transition: all .2s;
}
.ship-card:hover { border-color: #3b8bff; }
.ship-name { font-weight: 600; color: #e2e8f0; font-size: 13px; }
.ship-type { font-size: 11px; color: #64748b; }
.ship-hp { font-size: 11px; color: #94a3b8; margin-top: 4px; }
.rating {
  display: inline-block; padding: 1px 5px; border-radius: 2px;
  font-size: 10px; font-weight: 700; margin: 1px;
}
.rating-S { background: #f0a020; color: #000; }
.rating-A { background: #9060e0; color: #fff; }
.rating-B { background: #3b8bff; color: #fff; }
.rating-C { background: #607590; color: #fff; }
.rating-D { background: #e04040; color: #fff; }
.empty { text-align: center; color: #607590; padding: 40px; }
</style>
