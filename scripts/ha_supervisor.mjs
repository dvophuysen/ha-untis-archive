// Supervisor-Aufrufe der laufenden HA-Instanz über die Websocket-API.
//
// Der REST-Proxy /api/hassio/... gibt nur Logs und wenige Pfade heraus; alles
// andere (Add-on-Info, Store-Reload, Ingress-Sitzung) läuft über das
// Websocket-Kommando supervisor/api. Zugang: HA_URL (ohne Slash am Ende) und
// HA_TOKEN (Long-lived Access Token eines Administrators).
//
//   node scripts/ha_supervisor.mjs /addons/e54108c7_schul_cockpit/info
//   node scripts/ha_supervisor.mjs /store/reload post
//   node scripts/ha_supervisor.mjs /ingress/session post
//
// Ingress-Sitzung für die Add-on-API (wirkt als Admin/Elternteil):
//   session=$(node scripts/ha_supervisor.mjs /ingress/session post | python3 -c "import sys,json;print(json.load(sys.stdin)['session'])")
//   ingress=$(node scripts/ha_supervisor.mjs /addons/e54108c7_schul_cockpit/info | python3 -c "import sys,json;print(json.load(sys.stdin)['ingress_url'])")
//   curl -sS -b "ingress_session=$session" "$HA_URL${ingress}api/accounts"
// Die Sitzung läuft nach einiger Zeit ab (401): dann neu holen.
const [endpoint, method = 'get', json] = process.argv.slice(2);
if (!endpoint || !process.env.HA_URL || !process.env.HA_TOKEN) {
  console.error('usage: node scripts/ha_supervisor.mjs <endpoint> [method] [json]; HA_URL und HA_TOKEN müssen gesetzt sein.');
  process.exit(2);
}
const url = process.env.HA_URL.replace(/^https:\/\//, 'wss://').replace(/^http:\/\//, 'ws://') + '/api/websocket';
const ws = new WebSocket(url);
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.type === 'auth_required') { ws.send(JSON.stringify({ type: 'auth', access_token: process.env.HA_TOKEN })); return; }
  if (m.type === 'auth_ok') {
    const req = { id: 1, type: 'supervisor/api', endpoint, method };
    if (json) req.data = JSON.parse(json);
    ws.send(JSON.stringify(req));
    return;
  }
  if (m.id === 1) { console.log(JSON.stringify(m.success ? m.result : m.error)); ws.close(); process.exit(m.success ? 0 : 1); }
};
ws.onerror = (e) => { console.error('websocket error', e.message || ''); process.exit(1); };
setTimeout(() => { console.error('timeout'); process.exit(1); }, 280000);
