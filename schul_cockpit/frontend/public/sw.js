// Schul-Cockpit service worker.
//
// Strategy: network-first for pages, cache-first for hashed assets,
// fall back to cache when offline. Trades a tiny bit of LAN latency for never-stale UIs on
// iOS PWAs (which are notorious for serving cache-first forever).
//
// The cache name carries a build marker so a new add-on version invalidates
// the old cache automatically on activate.

const CACHE = 'schul-cockpit-__APP_VERSION__';
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

// Der Pfad der App: „/“ am Direktport, „/api/hassio_ingress/<token>/“ unter
// Ingress. Bis 1.31.2 galt jeder Pfad mit „/api/“ als Schnittstelle, unter
// Ingress also alles, und der Worker tat dort nichts.
const SCOPE = new URL(self.registration.scope).pathname;

// Was nie aus dem Cache kommen darf und nicht angefasst wird: fremde Adressen,
// alles außerhalb der App und jede Schnittstelle der App (Kontodaten,
// Erledigt-Stände). Im Zweifel lieber zu viel als zu wenig.
function passThrough(url) {
  if (url.origin !== self.location.origin) return true;
  if (!url.pathname.startsWith(SCOPE)) return true;
  return /(?:^|\/)api(?:\/|$)/.test(url.pathname.slice(SCOPE.length));
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (passThrough(url)) return;

  // Dateien unter assets/ tragen einen Hash im Namen und ändern sich nie:
  // aus dem Cache, sonst einmal holen (D177). Alles andere, auch die
  // Startseite, network-first; der Cache ist nur der Rückfall ohne Netz.
  if (/\/assets\/[^/]+$/.test(url.pathname)) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((resp) => {
        if (resp && resp.ok && resp.type === 'basic') {
          const clone = resp.clone();
          caches.open(CACHE).then((c) => c.put(req, clone)).catch(() => null);
        }
        return resp;
      })),
    );
    return;
  }

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
