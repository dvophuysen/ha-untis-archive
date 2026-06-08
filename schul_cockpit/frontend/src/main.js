import { mount } from 'svelte';
import App from './App.svelte';

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

// Service worker with fully automatic, hands-off updates. No more deleting
// and re-adding the home-screen app to get a new version.
//
// How it works:
//  - The new SW skips waiting and claims clients the moment it installs
//    (see sw.js), so a freshly-fetched version takes over immediately.
//  - When that happens the browser fires `controllerchange`; we reload the
//    page exactly once (guarded against loops) so the user lands on the
//    new code without lifting a finger.
//  - We re-check for a new SW on every launch AND whenever the app is
//    brought back to the foreground — iOS otherwise revalidates lazily.
if ('serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
  let reloadedForUpdate = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (reloadedForUpdate) return;
    reloadedForUpdate = true;
    window.location.reload();
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
