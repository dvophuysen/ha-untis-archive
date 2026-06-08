// Minimal service worker: cache the app shell + assets so the PWA still
// opens with the most recent UI when the network is flaky, and serve the
// last-seen API responses if the device is offline.

const CACHE = 'schul-cockpit-v1';
const SHELL = ['./', './manifest.webmanifest', './apple-touch-icon.png', './icon-192.png', './icon-512.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => null),
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))),
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  const isApi = url.pathname.includes('/api/');

  if (isApi) {
    // Network-first for API, fall back to cached if offline.
    event.respondWith(
      fetch(req)
        .then((resp) => {
          if (resp.ok) {
            const clone = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, clone)).catch(() => null);
          }
          return resp;
        })
        .catch(() => caches.match(req)),
    );
    return;
  }

  // Cache-first for static assets (JS, CSS, images, fonts).
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((resp) => {
        if (resp.ok && resp.type === 'basic') {
          const clone = resp.clone();
          caches.open(CACHE).then((c) => c.put(req, clone)).catch(() => null);
        }
        return resp;
      });
    }),
  );
});
