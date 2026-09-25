// API client. All paths are relative so the build works behind HA Ingress,
// which prepends an absolute path like /api/hassio_ingress/<token>/.
//
// When the page is loaded at https://ha.local/api/hassio_ingress/abc/,
// fetch('api/health') resolves to https://ha.local/api/hassio_ingress/abc/api/health.

import { viewHeader } from './viewMode.svelte.js';

export function joinUrl(path) {
  return path.startsWith('/') ? `.${path}` : `./${path}`;
}

// Leseaufrufe brechen nach zwei Minuten ab: Ein hängender Aufruf (Funkloch,
// Netzwechsel am iPhone) hielt sonst den Spinner ewig, und weil gleiche
// Leseaufrufe zusammengelegt werden, auch jeden späteren gleichen Aufruf.
// Schreibende Aufrufe haben keine Grenze, außer der Aufrufer nennt eine:
// Mentor-Züge, Auswertungen und Buchabrufe laufen mehrere Minuten.
export const READ_TIMEOUT = 120000;

// Laufende schreibende Aufrufe (etwa ein Mentor-Zug). Solange einer läuft,
// lädt die App für ein Update nicht neu (main.js).
let writes = 0;
export function writesInFlight() {
  return writes;
}

// Abgelaufene PIN-Anmeldung: store.svelte.js meldet sich hier an und zeigt
// die Anmeldung. Ingress-Nutzer sehen nie einen PIN-Dialog (siehe dort).
let unauthorized = null;
export function onUnauthorized(fn) {
  unauthorized = fn;
}

async function request(method, path, body, { timeout } = {}) {
  // credentials: 'include' makes the browser send AND store the session
  // cookie reliably — without it, some iOS/PWA contexts drop the
  // Set-Cookie from the login response, so the next /api/me 401s and the
  // login screen just reappears ("button does nothing").
  const opts = { method, headers: {}, credentials: 'include' };
  // Mitlesen, Kind am Elterngerät, Testmodus (D175).
  const mode = viewHeader();
  if (mode) opts.headers['x-view-mode'] = mode;
  if (body !== undefined) {
    if (body instanceof FormData) {
      opts.body = body;
    } else {
      opts.headers['content-type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
  }
  const limit = timeout === undefined ? (method === 'GET' ? READ_TIMEOUT : 0) : timeout;
  let timer = null, timedOut = false;
  if (limit > 0 && typeof AbortController === 'function') {
    const ctrl = new AbortController();
    opts.signal = ctrl.signal;
    timer = setTimeout(() => { timedOut = true; ctrl.abort(); }, limit);
  }
  const writing = method !== 'GET';
  if (writing) writes += 1;
  try {
    let resp;
    try {
      resp = await fetch(joinUrl(path), opts);
    } catch (_) {
      if (timedOut) throw new ApiError('Die App antwortet gerade nicht – gleich nochmal versuchen.', 0);
      // Funkloch oder App startet gerade neu: iOS meldet sonst nur „Load failed".
      throw new ApiError('Keine Verbindung zur App – gleich nochmal versuchen.', 0);
    }
    if (!resp.ok) {
      let detail = `${resp.status} ${resp.statusText}`;
      // Während eines Add-on-Neustarts antwortet HA mit 502/503/504 ohne JSON.
      if ([502, 503, 504].includes(resp.status)) detail = 'Die App startet gerade neu – gleich nochmal versuchen.';
      try {
        const data = await resp.json();
        if (data?.detail) detail = Array.isArray(data.detail)
          ? data.detail.map((d) => d.msg || 'Eingaben prüfen').join('; ')
          : String(data.detail);
      } catch (_) { /* ignore */ }
      // Anmelderouten melden einen falschen PIN selbst mit 401.
      if (resp.status === 401 && !path.startsWith('/api/auth/') && unauthorized) {
        try { unauthorized(); } catch (_) { /* Anzeige ist Sache der Seite */ }
      }
      throw new ApiError(detail, resp.status);
    }
    if (resp.status === 204) return null;
    try {
      return await resp.json();
    } catch (e) {
      if (timedOut) throw new ApiError('Die App antwortet gerade nicht – gleich nochmal versuchen.', 0);
      throw e;
    }
  } finally {
    if (timer) clearTimeout(timer);
    if (writing) writes -= 1;
  }
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// Gleiche Leseaufrufe, die schon unterwegs sind, laufen nicht ein zweites Mal
// los; wer später fragt, bekommt eine eigene Kopie derselben Antwort. Ein
// Leseaufruf, der mit einem Serverfehler endet, wird einmal wiederholt. Beides
// gegen gestapelte Aufrufe, wenn eine langsame Seite mehrfach angetippt wird (D200).
const inflight = new Map();
async function getOnce(path, o) {
  try {
    return await request('GET', path, undefined, o);
  } catch (e) {
    if (e instanceof ApiError && e.status === 500) {
      await new Promise((r) => setTimeout(r, 700));
      return request('GET', path, undefined, o);
    }
    throw e;
  }
}
function get(path, o) {
  const key = `${viewHeader() || ''} ${path}`;
  const running = inflight.get(key);
  if (running) return running.then((d) => (d === null ? d : structuredClone(d)));
  const p = getOnce(path, o).finally(() => inflight.delete(key));
  inflight.set(key, p);
  return p;
}

// Das dritte Argument nimmt Optionen, bisher nur `timeout` in Millisekunden
// (0 = keine Grenze).
export const api = {
  get,
  post: (p, body, o) => request('POST', p, body ?? {}, o),
  patch: (p, body, o) => request('PATCH', p, body ?? {}, o),
  put: (p, body, o) => request('PUT', p, body ?? {}, o),
  delete: (p, body, o) => request('DELETE', p, body, o),
};
