// ============================================================
// 拉格朗日AI — Nuxt 3 配置
// ============================================================

export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: true },
  
  app: {
    head: {
      title: '拉格朗日AI · 战术推演中心',
      meta: [
        { name: 'description', content: '无尽的拉格朗日 AI战术推演' },
      ],
    },
  },

  css: ['@/assets/theme.scss'],

  modules: ['@nuxt/ui', '@pinia/nuxt'],

  runtimeConfig: {
    public: {
      apiBase: 'http://127.0.0.1:3000',
    },
  },

  nitro: {
    devProxy: {
      '/api': { target: 'http://127.0.0.1:3000', changeOrigin: true },
    },
  },

  vite: {
    plugins: [],
  },
});
