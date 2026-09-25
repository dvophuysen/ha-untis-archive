import { mount } from 'svelte';
import App from './App.svelte';
import { reloadOnce, pageBusy } from './lib/reload.js';

// Detect installed-PWA mode reliably. iOS Safari sets the legacy
// `window.navigator.standalone` flag; modern browsers expose it via
// `display-mode: standalone`. Mark the body so CSS can react.
function isStandalone() {
  return (
    window.matchMedia?.('(display-mode: standalone)').matches ||
    window.matchMedia?.('(display-mode: fullscreen)').matches ||
    window.navigator.standalone === true
  );
}
if (isStandalone()) document.body.classList.add('standalone');

mount(App, { target: document.getElementById('app') });

// Nach einem Add-on-Update fehlen die alten, gehashten Dateien. Scheitert das
// Vorladen einer Seite deshalb, einmal neu laden (siehe Lazy.svelte).
window.addEventListener('vite:preloadError', (event) => {
  if (reloadOnce()) event.preventDefault();
});

// Service worker with fully automatic, hands-off updates. No more deleting
// and re-adding the home-screen app to get a new version.
//
// How it works:
//  - The new SW skips waiting and claims clients the moment it installs
//    (see sw.js), so a freshly-fetched version takes over immediately.
//  - When that happens the browser fires `controllerchange`; we reload the
//    page once so the user lands on the new code without lifting a finger.
//    Not on the very first visit (there was no worker before, the page is
//    already current), and never while something typed or a running chat
//    turn would be lost: then on the next page change or return to the app.
//  - We re-check for a new SW on every launch AND whenever the app is
//    brought back to the foreground — iOS otherwise revalidates lazily.
if ('serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
  const hadController = !!navigator.serviceWorker.controller;
  let reloadPending = false;
  let reloadedForUpdate = false;
  const tryReload = () => {
    if (!reloadPending || reloadedForUpdate) return;
    if (pageBusy()) return;
    reloadedForUpdate = true;
    window.location.reload();
  };
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (!hadController) return;
    reloadPending = true;
    tryReload();
  });
  // Nach dem Seitenwechsel erst prüfen, wenn die neue Seite steht.
  window.addEventListener('hashchange', () => setTimeout(tryReload, 300));
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') tryReload();
  });

  window.addEventListener('load', async () => {
    try {
      const reg = await navigator.serviceWorker.register('./sw.js', { scope: './' });

      const promote = () => {
        // A new SW is installed and waiting → tell it to activate now.
        if (reg.waiting) reg.waiting.postMessage('skipWaiting');
      };
      reg.addEventListener('updatefound', () => {
        const sw = reg.installing;
        if (!sw) return;
        sw.addEventListener('statechange', () => {
          if (sw.state === 'installed' && navigator.serviceWorker.controller) {
            promote();
          }
        });
      });
      promote();
      reg.update().catch(() => {});

      // Re-check when the app regains focus (typical PWA reopen).
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') reg.update().catch(() => {});
      });
    } catch (err) {
      console.warn('SW registration failed:', err);
    }
  });
}
