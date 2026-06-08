import { readFileSync } from 'node:fs';
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Read the add-on version from config.yaml so the UI can display exactly
// which build is loaded — the quickest way to tell a cache problem from a
// real one.
function readVersion() {
  try {
    const txt = readFileSync(new URL('../config.yaml', import.meta.url), 'utf8');
    const m = txt.match(/^version:\s*"?([^"\n]+)"?/m);
    return m ? m[1].trim() : 'dev';
  } catch {
    return 'dev';
  }
}

// Ingress prepends an absolute path like /api/hassio_ingress/<token>/.
// We use relative asset paths so the build is path-independent.
export default defineConfig({
  plugins: [svelte()],
  base: './',
  define: {
    __APP_VERSION__: JSON.stringify(readVersion()),
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2020',
    sourcemap: false,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8099',
    },
  },
});
