/**
 * Melodyxx — Service Worker (v53)
 * Strategy:
 *   - API & Stream: Network-only, never cache
 *   - Navigation (HTML): Network-first with cache fallback
 *   - Static Assets (CSS, JS, images): Stale-while-revalidate
 */

const CACHE_NAME = 'melodyxx-v78';
const APP_SHELL = [
  '/',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/logo.png',
  '/static/manifest.json',
  '/static/offline.html',
];

// ── Skip waiting on explicit client message ───────────────────
self.addEventListener('message', (event) => {
  if (event.data && event.data.action === 'skipWaiting') {
    self.skipWaiting();
  }
});

// ── Install: pre-cache app shell ────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Pre-caching app shell v5');
      return cache.addAll(APP_SHELL);
    })
  );
  self.skipWaiting();
});

// ── Activate: clean up all old caches immediately ───────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => {
            console.log('[SW] Deleting obsolete cache:', name);
            return caches.delete(name);
          })
      )
    )
  );
  self.clients.claim();
});

// ── Fetch: handle requests ───────────────────────────────────
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // 1. API and live streams: always use network
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // 2. Navigation / HTML pages: Network-first, fallback to cache (or custom offline page)
  if (event.request.mode === 'navigate' || url.pathname === '/' || url.pathname === '/index.html') {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // If server returned 5xx (502 Bad Gateway from Cloudflare, 503, 504), use cached shell
          if (response && response.status >= 500) {
            return caches.match(event.request).then((cached) => {
              if (cached) return cached;
              return caches.match('/static/offline.html').then((offlinePage) => offlinePage || response);
            });
          }
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => {
          // Network completely unreachable (container starting / offline)
          return caches.match(event.request).then((cached) => {
            if (cached) return cached;
            return caches.match('/static/offline.html');
          });
        })
    );
    return;
  }

  // 3. Static assets: Stale-while-revalidate
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetchPromise = fetch(event.request)
        .then((response) => {
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => cached);

      return cached || fetchPromise;
    })
  );
});
