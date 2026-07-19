// ============================================================
// 拉格朗日AI — SvelteKit 配置
// ============================================================

import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),

  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: 'index.html',
    }),
    alias: {
      '$components': 'src/components',
      '$lib': 'src/lib',
    },
    prerender: {
      entries: ['*'],
    },
  },

  vitePlugin: {
    inspector: true,
  },
};

export default config;
