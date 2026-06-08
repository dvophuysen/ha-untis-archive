// API client. All paths are relative so the build works behind HA Ingress,
// which prepends an absolute path like /api/hassio_ingress/<token>/.
//
// When the page is loaded at https://ha.local/api/hassio_ingress/abc/,
// fetch('api/health') resolves to https://ha.local/api/hassio_ingress/abc/api/health.

function joinUrl(path) {
  return path.startsWith('/') ? `.${path}` : `./${path}`;
}

async function request(method, path, body) {
  // credentials: 'include' makes the browser send AND store the session
  // cookie reliably — without it, some iOS/PWA contexts drop the
  // Set-Cookie from the login response, so the next /api/me 401s and the
  // login screen just reappears ("button does nothing").
  const opts = { method, headers: {}, credentials: 'include' };
  if (body !== undefined) {
    opts.headers['content-type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(joinUrl(path), opts);
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const data = await resp.json();
      if (data?.detail) detail = data.detail;
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

export const api = {
  get: (p) => request('GET', p),
  post: (p, body) => request('POST', p, body ?? {}),
  patch: (p, body) => request('PATCH', p, body ?? {}),
  put: (p, body) => request('PUT', p, body ?? {}),
  delete: (p) => request('DELETE', p),
};
