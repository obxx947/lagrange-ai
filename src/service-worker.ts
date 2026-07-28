/**
 * 拉格朗日AI - Service Worker
 * PWA 离线缓存与推送通知支持
 */

const CACHE_NAME = 'lagrange-ai-v2';
const urlsToCache: string[] = [
  '/',
  '/static/index.html',
  '/static/theme.css',
  '/static/favicon.svg',
  '/static/manifest.webmanifest',
];

self.addEventListener('install', (event: any) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', (event: any) => {
  event.respondWith(
    caches.match(event.request).then((response) => response || fetch(event.request))
  );
});

export {};
