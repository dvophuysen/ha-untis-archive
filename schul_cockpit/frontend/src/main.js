import { mount } from 'svelte';
import App from './App.svelte';

mount(App, { target: document.getElementById('app') });

// Register the PWA service worker. Skip in dev (vite serves from /).
if ('serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('./sw.js', { scope: './' }).catch((err) => {
      console.warn('SW registration failed:', err);
    });
  });
}
