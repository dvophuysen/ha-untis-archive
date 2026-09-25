// API client. All paths are relative so the build works behind HA Ingress,
// which prepends an absolute path like /api/hassio_ingress/<token>/.
//
// When the page is loaded at https://ha.local/api/hassio_ingress/abc/,
// fetch('api/health') resolves to https://ha.local/api/hassio_ingress/abc/api/health.

import { viewHeader } from './viewMode.svelte.js';

export function joinUrl(path) {
  return path.startsWith('/') ? `.${path}` : `./${path}`;
}

async function request(method, path, body) {
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
  let resp;
  try {
    resp = await fetch(joinUrl(path), opts);
  } catch (_) {
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
    throw new ApiError(detail, resp.status);
  }
  if (resp.status === 204) return null;
  return resp.json();
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
async function getOnce(path) {
  try {
    return await request('GET', path);
  } catch (e) {
    if (e instanceof ApiError && e.status === 500) {
      await new Promise((r) => setTimeout(r, 700));
      return request('GET', path);
    }
    throw e;
  }
}
function get(path) {
  const key = `${viewHeader() || ''} ${path}`;
  const running = inflight.get(key);
  if (running) return running.then((d) => (d === null ? d : structuredClone(d)));
  const p = getOnce(path).finally(() => inflight.delete(key));
  inflight.set(key, p);
  return p;
}

export const api = {
  get,
  post: (p, body) => request('POST', p, body ?? {}),
  patch: (p, body) => request('PATCH', p, body ?? {}),
  put: (p, body) => request('PUT', p, body ?? {}),
  delete: (p, body) => request('DELETE', p, body),
};
