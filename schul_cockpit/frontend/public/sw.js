// Schul-Cockpit service worker.
//
// Strategy: network-first for *everything*, fall back to cache when
// offline. Trades a tiny bit of LAN latency for never-stale UIs on
// iOS PWAs (which are notorious for serving cache-first forever).
//
// The cache name carries a build marker so a new add-on version invalidates
// the old cache automatically on activate.

const CACHE = 'schul-cockpit-0.34.0';
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
  // Account data and completion states must never be served from an old cache.
  if (/\/api(?:\/|$)/.test(new URL(req.url).pathname)) return;

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

self.addEventListener('push', event => {
  let data = {};
  try { data = event.data?.json() || {}; } catch { data = {}; }
  event.waitUntil(self.registration.showNotification(data.title || 'Schul-Cockpit', {
    body: data.body || 'Schau kurz in deinen Tag.', tag: data.tag || 'school-reminder',
    icon: './icon-192.png', data: {url: data.url || './#/today'},
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const base = new URL(self.registration.scope);
  let target = new URL('./#/today', base);
  try {
    const requested = new URL(event.notification.data?.url || './#/today', base);
    if (requested.origin === base.origin && requested.pathname.startsWith(base.pathname)) target = requested;
  } catch { /* Open the app for malformed links. */ }
  event.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true}).then(async clients => {
    for (const client of clients) {
      if (client.url.startsWith(base.href) && 'focus' in client) {
        await client.navigate(target.href); return client.focus();
      }
    }
    return self.clients.openWindow(target.href);
  }));
});
