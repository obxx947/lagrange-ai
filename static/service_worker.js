/* ============================================================
 * Service Worker — PWA离线支持
 * 提供基础缓存策略，使前端在离线时仍可加载
 * 注册方式：navigator.serviceWorker.register('/service_worker.js')
 * ============================================================ */

const CACHE_NAME = 'lagrange-ai-v2';
const ASSETS_TO_CACHE = [
  '/',
  '/static/index.html',
  '/static/theme.css',
  '/static/compare_ships.html',
  '/serene/',
];

// 安装事件：预缓存核心资源
self.addEventListener('install', (event) => {
  console.log('[SW] 安装中...');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] 缓存核心资源');
      return cache.addAll(ASSETS_TO_CACHE);
    }).then(() => self.skipWaiting())
  );
});

// 激活事件：清理旧缓存
self.addEventListener('activate', (event) => {
  console.log('[SW] 激活中...');
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

// 请求拦截：缓存优先策略（静态资源），网络优先（API）
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  
  // API请求：网络优先，失败时不缓存
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(JSON.stringify({
          detail: '当前离线，无法连接到服务器',
          error_code: 'OFFLINE'
        }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' }
        });
      })
    );
    return;
  }
  
  // 静态资源：缓存优先
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request).then((response) => {
        // 缓存成功的GET请求
        if (event.request.method === 'GET' && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
        }
        return response;
      });
    })
  );
});

// 消息事件
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});

console.log('[SW] Service Worker 已加载');
