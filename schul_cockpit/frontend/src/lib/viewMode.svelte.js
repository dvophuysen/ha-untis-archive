// Wer benutzt das Gerät (D175): eigene Elternansicht, Mitlesen, Kind am
// Elterngerät oder Testmodus. Gilt je Gerät, nicht je Konto, und wird als
// Kopfzeile X-View-Mode an den Server geschickt.

const KEY = 'viewMode';
const CHILD_IDLE_MS = 30 * 60 * 1000;

function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function read() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (v && ['mirror', 'child', 'test'].includes(v.mode)) return v;
  } catch { /* ohne Speicher gilt die Elternansicht */ }
  return { mode: 'parent', at: Date.now(), day: today() };
}

export const view = $state(read());

function save() {
  try { localStorage.setItem(KEY, JSON.stringify({ mode: view.mode, at: view.at, day: view.day })); } catch { /* egal */ }
}

export function setViewMode(mode) {
  view.mode = mode; view.at = Date.now(); view.day = today();
  save();
}

/** Jede Bedienung hält den Kindmodus wach. */
export function touchViewMode() {
  if (view.mode !== 'child') return;
  view.at = Date.now();
  save();
}

/** Kindmodus endet nach 30 Minuten ohne Nutzung, Mitlesen und Kindmodus am
 *  nächsten Tag. Der Testmodus endet nur von Hand. Gibt true zurück, wenn der
 *  Zustand zurückgesetzt wurde. */
export function expireViewMode() {
  const stale = (view.mode === 'child' && Date.now() - view.at > CHILD_IDLE_MS)
    || ((view.mode === 'child' || view.mode === 'mirror') && view.day !== today());
  if (stale) setViewMode('parent');
  return stale;
}

export function viewHeader() {
  return view.mode === 'parent' ? null : view.mode;
}
