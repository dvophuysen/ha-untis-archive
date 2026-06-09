// Schul-Cockpit service worker.
//
// Strategy: network-first for *everything*, fall back to cache when
// offline. Trades a tiny bit of LAN latency for never-stale UIs on
// iOS PWAs (which are notorious for serving cache-first forever).
//
// The cache name carries a build marker so a new add-on version invalidates
// the old cache automatically on activate.

const CACHE = 'schul-cockpit-2026-06-09-g';
const SHELL = [
  './',
  './manifest.webmanifest',
  './apple-touch-icon.png',
  './icon-192.png',
  './icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => null),
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
    ),
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  event.respondWith(
    fetch(req)
      .then((resp) => {
        if (resp && resp.ok && resp.type === 'basic') {
          const clone = resp.clone();
          caches.open(CACHE).then((c) => c.put(req, clone)).catch(() => null);
        }
        return resp;
      })
      .catch(() => caches.match(req)),
  );
});

// Let the app trigger an immediate activation after a code update.
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') self.skipWaiting();
});
