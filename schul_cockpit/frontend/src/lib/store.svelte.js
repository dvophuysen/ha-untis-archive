// Tiny rune-based global appState.

import { api, ApiError, onUnauthorized } from './api.js';
import { resetProfile } from './profile.svelte.js';
import { forgetTodo } from './parentTodo.svelte.js';
import { forgetPrefetch } from './prefetch.js';

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
    // Nach Abmelden und Anmelden eines anderen Nutzers kann das gewählte Kind
    // fehlen; dann neu wählen statt „nicht verlinkt“ zu zeigen.
    const known = appState.me.accounts.some((a) => a.id === appState.activeAccountId);
    if (appState.me.accounts.length > 0 && (appState.activeAccountId == null || !known)) {
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
      // Vorab geholte Antworten gehörten zur alten Anmeldung.
      forgetPrefetch();
      appState.needsLogin = true;
      appState.me = null;
    } else {
      appState.error = e.message;
    }
  } finally {
    appState.loading = false;
  }
}

// Eine abgelaufene PIN-Anmeldung führt bei jedem Aufruf zur Anmeldung, nicht
// erst beim nächsten Start. Nur die PIN-Anmeldung kann ablaufen; unter Ingress
// meldet Home Assistant an, dort erscheint nie ein PIN-Dialog.
onUnauthorized(() => {
  if (appState.me?.auth_source === 'pin') appState.needsLogin = true;
});

/** Abmelden: Kind, Gestaltung und Elternliste des bisherigen Nutzers vergessen. */
export async function logout() {
  try { await api.post('/api/auth/logout'); } catch (_) { /* ignore */ }
  appState.activeAccountId = null;
  forgetPrefetch();
  resetProfile();
  forgetTodo();
  await loadMe();
}

export function setActiveAccount(id) {
  appState.activeAccountId = id;
  localStorage.setItem('activeAccountId', String(id));
}

export function activeAccount() {
  if (!appState.me) return null;
  return appState.me.accounts.find((a) => a.id === appState.activeAccountId) ?? null;
}
