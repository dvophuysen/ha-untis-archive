<script>
  // KI-Rahmen und Lernbegleiter für Eltern (D183), vorher „Echte Einstellungen“
  // im Lernbegleiter. part="household": Verbrauch, Anfangsstand, Rahmen und
  // Modellprüfung der Familie. part="kid": Lernbegleiter und Hintergrund je Kind.
  import { api } from './api.js';
  import { forgetTodo } from './parentTodo.svelte.js';
  let { accountId, part = 'household' } = $props();
  const base = $derived(`/api/accounts/${accountId}/learning/mentor`);
  const TIER_LABELS = { hoch: 'Hoch', mittel: 'Mittel', niedrig: 'Niedrig', klein: 'Klein' };
  let data = $state(null), error = $state(''), busy = $state(false), spent = $state(0), quality = $state(null), saved = $state('');
  let limits = $state({});
  let request = 0;
  async function load() {
    const ticket = ++request;
    if (!accountId) return;
    try {
      const d = await api.get(`${base}/admin`);
      if (ticket !== request) return;
      data = d;
      const b = d.budget || {};
      limits = { monthly_eur: b.limit_eur ?? 50, warning_eur: b.warning_eur ?? 40, daily_eur: b.daily_limit_eur ?? 10, sources_eur: b.sources_limit_eur ?? 30, background_eur: b.background_limit_eur ?? 10,
                 sources_model: b.sources_model ?? '', opening_model: b.opening_model ?? '', background_model: b.background_model ?? '', vocab_model: b.vocab_model ?? '' };
    } catch (e) { if (ticket === request) error = e.message; }
  }
  $effect(() => { void accountId; data = null; error = ''; load(); });
  async function act(fn, done = '') {
    if (busy) return;
    busy = true; error = ''; saved = '';
    try { await fn(); await load(); saved = done; forgetTodo(); } catch (e) { error = e.message; } finally { busy = false; }
  }
  const b = $derived(data?.budget);
</script>

{#if error}<p class="error-box" role="alert">{error}</p>{/if}
{#if !data && !error}<p class="muted">Lade …</p>{/if}
{#if data && part === 'kid'}
  <p class="muted">{data.profile ? `Lernrahmen ${data.profile.school_year}, Klasse ${data.profile.grade} · KI ${data.profile.ai_enabled ? 'erlaubt' : 'aus'}` : 'Noch kein Lernrahmen für dieses Schuljahr.'}</p>
  <label class="check"><input type="checkbox" checked={data.enabled} disabled={busy} onchange={(e) => act(() => api.put(`${base}/settings`, { enabled: e.currentTarget.checked, background_enabled: data.background }))} /> Lernbegleiter verwenden</label>
  <label class="check"><input type="checkbox" checked={data.background} disabled={busy} onchange={(e) => act(() => api.put(`${base}/settings`, { enabled: data.enabled, background_enabled: e.currentTarget.checked }))} /> Neue Unterrichtsthemen im Hintergrund erschließen</label>
{:else if data && b}
  <p><strong>{b.used_eur.toFixed(2)} € bisher</strong> · {b.month}{#if b.projected_eur} · hochgerechnet {b.projected_eur.toFixed(0)} € zum Monatsende{/if}</p>
  <p class="muted">{b.accounting}; der gebuchte Wert liegt bewusst über der tatsächlichen Rechnung. Zuletzt {b.per_day_eur?.toFixed(2)} € am Tag. Richtwerte: {b.limit_eur.toFixed(0)} € im Monat, {b.daily_limit_eur?.toFixed(0)} € am Tag je Kind{#if b.sources_limit_eur}, Quellenbestand {b.sources_eur.toFixed(2)} € von {b.sources_limit_eur.toFixed(0)} €{/if}. Sie halten nichts an.</p>
  {#if b.warning}<p class="notice">Die Hochrechnung liegt bei {b.projected_eur?.toFixed(0)} € und damit über dem Richtwert von {b.warning_eur.toFixed(0)} €. Nichts wird gesperrt; der größte Hebel ist die Stufe fürs Abschreiben.</p>{/if}
  {#if b.over_budget?.length}<p class="muted">Überschritten in diesem Monat: {b.over_budget.join(', ')}. Die Aufrufe sind trotzdem gelaufen.</p>{/if}
  {#if !b.rate_available}<p class="notice">Die Kostensätze müssen vor neuen KI-Aufrufen geprüft werden.</p>{/if}
  {#if !b.opening_confirmed}
    <form class="opening" onsubmit={(e) => { e.preventDefault(); act(() => api.put(`${base}/budget-opening`, { spent_eur: spent }), 'Anfangsstand gespeichert.'); }}>
      <p>Vor der neuen Verbrauchserfassung gab es bereits KI-Aufrufe. Den bisherigen Monatsverbrauch aus Azure eintragen.</p>
      <label>Bisherige Mentor-Kosten dieses Monats in Euro<input type="number" min="0" max="1000" step="0.01" required bind:value={spent} /></label>
      <button class="primary" disabled={busy}>Anfangsstand bestätigen</button>
    </form>
  {/if}
  <details>
    <summary>KI-Rahmen einstellen</summary>
    <p class="muted">Der Tagesrahmen zählt nur, was das Kind selbst übt und fragt. Quellen und Hintergrund haben eigene Monatsrahmen innerhalb des Monatsrahmens. Das Modell fürs Abschreiben wird nur nach Eichung an echten Seiten umgestellt; Erklären und Üben bleiben beim Hauptmodell.</p>
    <form class="limits" onsubmit={(e) => { e.preventDefault(); act(() => api.put(`${base}/budget-limits`, { monthly_eur: Number(limits.monthly_eur), warning_eur: Number(limits.warning_eur), daily_eur: Number(limits.daily_eur), sources_eur: Number(limits.sources_eur), background_eur: Number(limits.background_eur), sources_model: limits.sources_model ?? '', opening_model: limits.opening_model ?? '', background_model: limits.background_model ?? '', vocab_model: limits.vocab_model ?? '' }), 'Rahmen gespeichert.'); }}>
      <label>Monat gesamt (€)<input type="number" min="1" max="1000" step="1" bind:value={limits.monthly_eur} /></label>
      <label>Warnen, wenn die Hochrechnung übersteigt (€)<input type="number" min="1" max="1000" step="1" bind:value={limits.warning_eur} /></label>
      <label>Tag je Kind (€)<input type="number" min="0.5" max="200" step="0.5" bind:value={limits.daily_eur} /></label>
      <label>Quellenbestand im Monat (€)<input type="number" min="0" max="1000" step="1" bind:value={limits.sources_eur} /></label>
      <label>Hintergrund im Monat (€)<input type="number" min="0" max="1000" step="1" bind:value={limits.background_eur} /></label>
      {#each [['opening_model', 'Stufe für den Einstieg in eine Einheit', ''], ['background_model', 'Stufe für die Unterrichtsauswertung', ''], ['sources_model', 'Stufe fürs Abschreiben', 'rates'], ['vocab_model', 'Stufe fürs Lesen der Vokabellisten', 'vocab']] as [field, text, extra] (field)}
        <label>{text}<select bind:value={limits[field]}>
          <option value="">{extra === 'vocab' ? 'wie das Abschreiben' : `wie das Hauptgespräch (${b.model})`}</option>
          {#each b.models ?? [] as m (m)}<option value={m}>{TIER_LABELS[m] ?? m} · {b.rates?.[m]?.model}{extra === 'rates' ? ` · ${b.rates?.[m]?.input_per_m ?? '?'} / ${b.rates?.[m]?.output_per_m ?? '?'} € je Mio. Token` : b.rates?.[m]?.estimated ? ' · Kostensatz geschätzt' : ''}</option>{/each}
        </select></label>
      {/each}
      <button disabled={busy}>Rahmen speichern</button>
    </form>
  </details>
  <details>
    <summary>Fachliche Modellprüfung</summary>
    <p>30 feste Fälle zu Brüchen, Grammatik und Zusammenhängen. Drei begrenzte Durchläufe mit je zehn Fällen; Ergebnisse werden wiederverwendet. Keine Daten der Kinder.</p>
    <button disabled={busy} onclick={() => act(async () => { quality = await api.post(`${base}/quality/next`); })}>Zehn Prüffälle auswerten</button>
    {#if quality}<p>{quality.passed} von {quality.done} bisher geprüften Fällen entsprechen den festgelegten Kriterien ({quality.total} insgesamt).</p>{#each quality.results.filter((r) => !r.passed) as r (r.id)}<p>Fall {r.id + 1}: erwartet {r.expected}, bewertet {r.result}. {r.rationale}</p>{/each}{/if}
  </details>
{/if}
{#if saved}<p class="muted" role="status">{saved}</p>{/if}

<style>
  .check { display: flex; align-items: center; gap: 10px; color: var(--fg); font-size: var(--fs-sm); margin: var(--sp-2) 0; }
  .check input { width: 24px; height: 24px; min-height: 24px; flex: none; }
  .muted { font-size: var(--fs-sm); color: var(--fg-muted); }
  .limits, .opening { display: grid; gap: var(--sp-2); }
  details { margin-top: var(--sp-2); }
  summary { cursor: pointer; min-height: 44px; display: flex; align-items: center; font-weight: 600; }
</style>
