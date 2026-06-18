/**
 * Listen Now — Service Worker
 * Strategy:
 *   - App Shell (HTML, fonts): Cache-first, fallback to network
 *   - API calls (/api/*): Network-first, no caching
 *   - Static assets (CSS, JS, images): Cache-first with background update
 */

const CACHE_NAME = 'listen-now-v1';
const APP_SHELL = [
  '/',
  '/static/logo.png',
  '/static/manifest.json',
];

// ── Install: pre-cache the app shell ────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Pre-caching app shell');
      return cache.addAll(APP_SHELL);
    })
  );
  self.skipWaiting();
});

// ── Activate: clean up old caches ───────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => {
            console.log('[SW] Deleting old cache:', name);
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

  // Always use network for API requests — never cache
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/downloads/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Cache-first for everything else (app shell, static assets)
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) {
        // Serve from cache, refresh in background
        fetch(event.request)
          .then((response) => {
            if (response && response.status === 200) {
              caches.open(CACHE_NAME).then((cache) => cache.put(event.request, response));
            }
          })
          .catch(() => {});
        return cached;
      }
      // Not cached — fetch from network and cache it
      return fetch(event.request).then((response) => {
        if (!response || response.status !== 200 || response.type === 'opaque') {
          return response;
        }
        const cloned = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cloned));
        return response;
      });
    })
  );
});
