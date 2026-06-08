// Tiny rune-based global appState.

import { api } from './api.js';

export const appState = $state({
  loading: true,
  me: null,
  activeAccountId: null,
  error: null,
});

export async function loadMe() {
  appState.loading = true;
  appState.error = null;
  try {
    appState.me = await api.get('/api/me');
    if (appState.me.accounts.length > 0 && appState.activeAccountId == null) {
      const saved = localStorage.getItem('activeAccountId');
      const savedNum = saved ? Number(saved) : null;
      const valid = appState.me.accounts.find((a) => a.id === savedNum);
      appState.activeAccountId = valid ? valid.id : appState.me.accounts[0].id;
    } else if (appState.me.accounts.length === 0) {
      appState.activeAccountId = null;
    }
  } catch (e) {
    appState.error = e.message;
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
