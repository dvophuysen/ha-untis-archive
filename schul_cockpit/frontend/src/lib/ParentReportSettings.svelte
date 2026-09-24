<script>
  // Wochenbericht an die Eltern als Mitteilung: Tag, Uhrzeit und Elterngeräte.
  // Geräte, die Erinnerungen eines Kindes bekommen, sind gesperrt.
  import { api } from './api.js';
  const DAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];
  let data = $state(null), error = $state(''), message = $state(''), busy = $state(false), opened = $state(false);
  let weekday = $state(6), at = $state('18:00'), chosen = $state(new Set());

  async function load() {
    try {
      data = await api.get('/api/parent-report');
      weekday = data.weekday; at = data.at; chosen = new Set(data.targets);
    } catch (e) { error = e.message; }
  }
  $effect(() => { load(); });

  function toggle(service) {
    const next = new Set(chosen);
    next.has(service) ? next.delete(service) : next.add(service);
    chosen = next;
  }
  async function act(fn) {
    busy = true; message = ''; error = '';
    try { await fn(); } catch (e) { error = e.message; } finally { busy = false; }
  }
  const label = (s) => s.replace(/^mobile_app_/, '').replaceAll('_', ' ');
</script>

<section class="card parent-report">
  <button class="head" aria-expanded={opened} onclick={() => opened = !opened}>
    <span>
      <h3>Wochenbericht aufs Handy</h3>
      {#if data}<small>{data.targets.length ? `${DAYS[data.weekday]}s ${data.at} an ${data.targets.map(label).join(', ')}` : 'Aus'}</small>{/if}
    </span>
    <span class="chevron" class:opened>›</span>
  </button>
  {#if opened}
    {#if error}<p class="error-box" role="alert">{error}</p>{/if}
    {#if !data}<p class="muted">Lade …</p>
    {:else}
      <p class="muted">Je Kind eine kurze Nachricht mit der Kopfzeile und den Auffälligkeiten des Nutzungsberichts. Tippen öffnet die App.</p>
      <div class="row">
        <label>Tag<select bind:value={weekday}>{#each DAYS as d, i}<option value={i}>{d}</option>{/each}</select></label>
        <label>Uhrzeit<input type="time" bind:value={at} /></label>
      </div>
      <fieldset>
        <legend>An diese Geräte</legend>
        {#each data.devices as d}
          <label class="device" class:blocked={d.child_device}>
            <input type="checkbox" checked={chosen.has(d.service)} disabled={d.child_device} onchange={() => toggle(d.service)} />
            {label(d.service)}{#if d.child_device}<small> · bekommt Erinnerungen eines Kindes</small>{/if}
          </label>
        {/each}
      </fieldset>
      <div class="actions">
        <button class="primary" disabled={busy} onclick={() => act(async () => {
          await api.put('/api/parent-report', { weekday: Number(weekday), at, targets: [...chosen] });
          await load(); message = chosen.size ? 'Gespeichert.' : 'Wochenbericht ausgeschaltet.';
        })}>Speichern</button>
        <button disabled={busy || !(data.targets || []).length} onclick={() => act(async () => {
          const r = await api.post('/api/parent-report/test');
          const n = Object.values(r.sent || {}).reduce((a, b) => a + b, 0);
          message = n ? `${n} Testnachricht${n === 1 ? '' : 'en'} verschickt.` : 'Kein Gerät erreicht.';
        })}>Testnachricht</button>
      </div>
      {#if message}<p class="muted" role="status">{message}</p>{/if}
    {/if}
  {/if}
</section>

<style>
  .parent-report { margin-top: 12px; }
  .head { display: flex; justify-content: space-between; align-items: center; width: 100%; border: 0; background: transparent; padding: 4px 0; color: var(--fg); text-align: left; min-height: 44px; }
  .head h3 { margin: 0; font-size: 0.95rem; }
  .head small { display: block; font-size: 0.8rem; color: var(--fg-muted); margin-top: 2px; }
  .chevron { color: var(--accent); font-size: 1.3rem; transition: transform .15s; }
  .chevron.opened { transform: rotate(90deg); }
  .row { display: flex; gap: 12px; }
  .row label { flex: 1; }
  fieldset { border: 0; padding: 0; margin: 8px 0; }
  legend { font-size: 0.85rem; color: var(--fg-muted); margin-bottom: 4px; }
  .device { display: flex; align-items: center; gap: 8px; min-height: 44px; color: var(--fg); font-size: 0.95rem; margin: 0; }
  .device input { width: auto; min-height: auto; }
  .device.blocked { color: var(--fg-muted); }
  .actions { display: flex; gap: 8px; margin-top: 8px; }
  .muted { font-size: 0.85rem; color: var(--fg-muted); }
</style>
