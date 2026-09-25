// Herzschlag für den Nutzungsbericht der Eltern: wie lange die App sichtbar
// war und in welcher Ansicht. Gespeichert werden nur Sekunden je Tag und
// Ansicht, kein Klickprotokoll; nach 90 Tagen gelöscht.
import { api, joinUrl } from './api.js';
import { viewHeader } from './viewMode.svelte.js';

// Beim Verlassen der App: fetch mit keepalive überlebt das Schließen wie
// sendBeacon, schickt aber die Kopfzeile X-View-Mode mit. Ohne sie zählte die
// Zeit „Kind am Elterngerät“ als Nutzung der Eltern (D175). sendBeacon bleibt
// der Rückfall für Browser ohne keepalive.
function sendOnLeave(body) {
  const url = joinUrl('/api/usage/ping');
  const json = JSON.stringify(body);
  try {
    const headers = { 'content-type': 'application/json' };
    const mode = viewHeader();
    if (mode) headers['x-view-mode'] = mode;
    fetch(url, { method: 'POST', keepalive: true, credentials: 'include', headers, body: json }).catch(() => {});
    return;
  } catch (_) { /* weiter mit sendBeacon */ }
  if (navigator.sendBeacon) navigator.sendBeacon(url, new Blob([json], { type: 'application/json' }));
}

const TICK = 15000;
const SEND = 60000;
// Wer länger als fünf Minuten weg war, hat die App neu geöffnet.
const REOPEN = 5 * 60 * 1000;

export function startUsagePing(current) {
  let pending = 0;
  let opened = true;
  let lastTick = Date.now();
  let lastSent = Date.now();
  let hiddenAt = null;
  let lastView = null;

  function send(target, beacon) {
    lastSent = Date.now();
    const seconds = Math.min(120, Math.round(pending / 1000));
    pending = 0;
    if (!target || !target.accountId || (!seconds && !opened)) return;
    const body = { account_id: target.accountId, view: target.view || '', seconds, open: opened };
    opened = false;
    try {
      if (beacon) {
        sendOnLeave(body);
      } else {
        api.post('/api/usage/ping', body).catch(() => {});
      }
    } catch (_) { /* Nutzungszeit ist Beiwerk, nie ein Fehler für das Kind */ }
  }

  function tick() {
    const now = Date.now();
    const target = current();
    if (document.visibilityState === 'visible') pending += Math.min(now - lastTick, TICK * 2);
    lastTick = now;
    // Die bisher gesammelte Zeit gehört zur alten Ansicht.
    if (lastView && target && target.view !== lastView.view) send(lastView, false);
    lastView = target;
    if (now - lastSent >= SEND) send(target, false);
  }

  function visibility() {
    const now = Date.now();
    if (document.visibilityState === 'hidden') {
      tick();
      send(current(), true);
      hiddenAt = now;
    } else {
      if (hiddenAt && now - hiddenAt > REOPEN) opened = true;
      hiddenAt = null;
      lastTick = now;
    }
  }

  const timer = setInterval(tick, TICK);
  document.addEventListener('visibilitychange', visibility);
  return () => {
    clearInterval(timer);
    document.removeEventListener('visibilitychange', visibility);
  };
}
