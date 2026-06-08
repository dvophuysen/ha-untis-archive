// Tiny rune-based global appState.

import { api, ApiError } from './api.js';

export const appState = $state({
  loading: true,
  me: null,
  activeAccountId: null,
  error: null,
  needsLogin: false,
});

export async function loadMe() {
  appState.loading = true;
  appState.error = null;
  try {
    appState.me = await api.get('/api/me');
    appState.needsLogin = false;
    if (appState.me.accounts.length > 0 && appState.activeAccountId == null) {
      // Deep-link override: ?acc=<id> in the URL wins over the saved one.
      // Useful for HA-cron WhatsApp links so they jump straight to the
      // right child (e.g. https://schule.example.com/?acc=1#/today).
      const fromQuery = new URLSearchParams(window.location.search).get('acc');
      const queryNum = fromQuery ? Number(fromQuery) : null;
      const saved = localStorage.getItem('activeAccountId');
      const savedNum = saved ? Number(saved) : null;
      const preferred =
        appState.me.accounts.find((a) => a.id === queryNum) ||
        appState.me.accounts.find((a) => a.id === savedNum) ||
        appState.me.accounts[0];
      appState.activeAccountId = preferred.id;
      if (queryNum && preferred.id === queryNum) {
        localStorage.setItem('activeAccountId', String(queryNum));
      }
    } else if (appState.me.accounts.length === 0) {
      appState.activeAccountId = null;
    }
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      appState.needsLogin = true;
      appState.me = null;
    } else {
      appState.error = e.message;
    }
  } finally {
    appState.loading = false;
  }
}

export function setActiveAccount(id) {
  appState.activeAccountId = id;
  localStorage.setItem('activeAccountId', String(id));
}

export function activeAccount() {
  if (!appState.me) return null;
  return appState.me.accounts.find((a) => a.id === appState.activeAccountId) ?? null;
}
