// Gestaltung je Kind (D176): Akzentfarbe, Profilbild, Hell/Dunkel, Dichte, Freude.
import { api } from './api.js';
import { getEarly } from './prefetch.js';

export const COLORS = [
  ['petrol', '#176b72', 'Petrol'], ['kobalt', '#3056d3', 'Kobalt'], ['glut', '#c2410c', 'Glut'], ['beere', '#b3265e', 'Beere'],
  ['wald', '#2f7d32', 'Wald'], ['lila', '#6b3fc4', 'Lila'], ['ozean', '#0e7490', 'Ozean'], ['sonne', '#a16207', 'Sonne'],
  ['graphit', '#334155', 'Graphit'], ['koralle', '#be123c', 'Koralle'], ['moos', '#4d7c0f', 'Moos'], ['nacht', '#1e3a8a', 'Nacht'],
];
export const AVATARS = ['', '🦊', '🐼', '🐙', '🦉', '🐢', '🐧', '🦁', '🐳', '⚽', '🎸', '🚀', '🎮', '🌙', '⚡', '🌊'];
const DEFAULTS = { color: 'petrol', avatar: '', theme: 'system', density: 'normal', joy: 'konfetti' };

export const profile = $state({ accountId: null, prefs: { ...DEFAULTS } });

// Nur die Antwort für das zuletzt angefragte Kind gilt.
let wanted = null;
export async function loadProfile(accountId) {
  if (!accountId) return;
  wanted = accountId;
  try {
    const prefs = await getEarly(`/api/accounts/${accountId}/profile`);
    if (wanted !== accountId) return;
    profile.accountId = accountId;
    profile.prefs = { ...DEFAULTS, ...prefs };
  } catch { /* Gestaltung ist Beiwerk */ }
}

/** Beim Abmelden: Gestaltung des bisherigen Kindes vergessen. */
export function resetProfile() {
  wanted = null;
  profile.accountId = null;
  profile.prefs = { ...DEFAULTS };
}

export async function saveProfile(accountId, change) {
  const prefs = await api.put(`/api/accounts/${accountId}/profile`, change);
  wanted = accountId;
  profile.accountId = accountId;
  profile.prefs = { ...DEFAULTS, ...prefs };
  return prefs;
}

/** Auf die Seite anwenden; ohne Kind (Elternansicht) gilt die Grundgestaltung. */
export function applyProfile(prefs) {
  const root = document.documentElement;
  const p = prefs || DEFAULTS;
  if (p.color && p.color !== 'petrol') root.dataset.accent = p.color; else delete root.dataset.accent;
  if (p.theme === 'light' || p.theme === 'dark') root.dataset.theme = p.theme; else delete root.dataset.theme;
  if (p.density === 'compact') root.dataset.density = 'compact'; else delete root.dataset.density;
}

export function initials(name) {
  return (name || '?').split(/\s+/).filter(Boolean).map((x) => x[0]).join('').slice(0, 2).toUpperCase();
}
