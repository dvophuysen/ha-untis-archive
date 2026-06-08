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

// Register the PWA service worker, then prod it to check for an updated
// version every time the app starts (otherwise iOS happily serves the
// cached shell forever).
if ('serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
  window.addEventListener('load', async () => {
    try {
      const reg = await navigator.serviceWorker.register('./sw.js', { scope: './' });
      reg.update().catch(() => {});
    } catch (err) {
      console.warn('SW registration failed:', err);
    }
  });
}
