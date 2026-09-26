// Die ersten Leseaufrufe von „Heute“ starten gleichzeitig mit /api/me, wenn
// das Gerät das Kind schon kennt (D177): eine Runde weniger über den
// Fernzugriff. Abgeholt wird eine Antwort nur von genau demselben Aufruf in
// derselben Ansicht (X-View-Mode) und nur kurz nach dem Start. Zeigt /api/me
// ein anderes Kind, die Elternhülle oder die Anmeldung, holt sie niemand ab:
// Sie verfällt still, ohne Fehler. Eine gescheiterte Vorabantwort zählt nie,
// dann fragt die Seite wie bisher selbst.
import { api } from './api.js';
import { viewHeader } from './viewMode.svelte.js';

const TTL = 20000;
const early = new Map();
let timer = null;

/** Das Kind, das loadMe wählen wird, sofern es verknüpft ist: ?acc= vor dem gemerkten. */
export function knownAccount(search = window.location.search, storage = localStorage) {
  const fromQuery = Number(new URLSearchParams(search).get('acc'));
  if (Number.isInteger(fromQuery) && fromQuery > 0) return fromQuery;
  let saved = null;
  try { saved = Number(storage.getItem('activeAccountId')); } catch { return null; }
  return Number.isInteger(saved) && saved > 0 ? saved : null;
}

/** Die Aufrufe, die „Heute“ und die Gestaltung beim ersten Aufbau machen. */
export function todayPaths(id) {
  return [
    `/api/accounts/${id}/today`, `/api/accounts/${id}/tasks?recent_done_days=14`, `/api/accounts/${id}/plan?compact=1`,
    `/api/accounts/${id}/rewards`, `/api/accounts/${id}/profile`,
  ];
}

export function prefetch(paths, get = api.get) {
  const at = Date.now(), mode = viewHeader() || '';
  for (const path of paths) {
    const promise = get(path);
    promise.catch(() => {}); // verworfen, falls niemand sie abholt
    early.set(path, { promise, at, mode });
  }
  clearTimeout(timer);
  timer = setTimeout(forgetPrefetch, TTL);
}

/** Wie api.get, nimmt aber einmalig eine passende Vorabantwort. */
export function getEarly(path) {
  const hit = early.get(path);
  early.delete(path);
  if (!hit || Date.now() - hit.at > TTL || hit.mode !== (viewHeader() || '')) return api.get(path);
  return hit.promise.catch(() => api.get(path));
}

export function forgetPrefetch() {
  early.clear();
}
