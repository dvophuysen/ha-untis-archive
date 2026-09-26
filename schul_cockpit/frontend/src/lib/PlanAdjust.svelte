<script>
  // Lernpensum anpassen (D214): Eltern stellen den Plan von heute und vom
  // nächsten Schultag ein. Einfach: weniger oder mehr. Erweitert: einzelne
  // Schritte streichen oder aus den übrigen hinzufügen. Gestrichenes zählt nie
  // als versäumt, Hinzugefügtes als Pflicht.
  import { api } from './api.js';
  import { subjectStyle } from './subjectStyle.js';
  import { formatShortDate } from './format.js';

  let { accountId, name, onclose, onchange } = $props();
  let days = $state([]), index = $state(0), loading = $state(true), busy = $state(false), error = $state('');
  let more = $state(false);
  const cur = $derived(days[index] ?? null);

  async function load() {
    loading = true; error = '';
    try { days = (await api.get(`/api/accounts/${accountId}/study-plan/adjust`)).days ?? []; }
    catch (e) { error = e.message || 'Der Plan ließ sich nicht laden.'; }
    finally { loading = false; }
  }
  $effect(() => { void accountId; load(); });

  async function act(action, key = null) {
    if (busy || !cur) return;
    busy = true; error = '';
    try {
      const next = await api.post(`/api/accounts/${accountId}/study-plan/adjust`, { day: cur.day, action, key });
      days = days.map((d, i) => (i === index ? { ...d, ...next } : d));
      onchange?.();
    } catch (e) { error = e.message || 'Das hat nicht geklappt.'; }
    finally { busy = false; }
  }
  const time = (iso) => (iso ? new Date(iso).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) : '');
  const what = { drop: 'gestrichen', add: 'hinzugefügt', less: 'einer weniger', more: 'einer mehr' };
</script>

<div class="modal-backdrop" role="presentation" onclick={onclose}>
  <div class="modal sheet adjust" role="dialog" aria-modal="true" aria-label="Lernen anpassen" tabindex="-1"
       onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.key === 'Escape' && onclose()}>
    <h2>Lernen anpassen: {name}</h2>
    {#if loading}
      <div class="empty"><span class="spinner"></span></div>
    {:else if !days.length}
      <p class="muted">Gerade gibt es keinen Plan zum Anpassen.</p>
    {:else}
      {#if days.length > 1}
        <div class="tabs" role="tablist">
          {#each days as d, i (d.day)}
            <button role="tab" aria-selected={i === index} class:cur={i === index} onclick={() => { index = i; more = false; }}>{d.label}</button>
          {/each}
        </div>
      {:else}
        <p class="muted">{cur.label}</p>
      {/if}
      <div class="count">
        <span><b>{cur.open}</b> offen von {cur.total} {cur.total === 1 ? 'Schritt' : 'Schritten'}</span>
        <span class="pm">
          <button aria-label="Einen Schritt weniger" disabled={busy || !cur.open} onclick={() => act('less')}>−</button>
          <button aria-label="Einen Schritt mehr" disabled={busy || !cur.candidates.length} onclick={() => act('more')}>+</button>
        </span>
      </div>
      {#if !cur.frozen}<p class="muted small">Der Plan für diesen Tag steht noch nicht fest. Weniger und mehr gelten als Anzahl und werden am Morgen zu einzelnen Schritten.</p>{/if}
      <ul class="steps">
        {#each cur.steps as s (s.key)}
          <li class:done={s.done}>
            <span class="t"><span class="sub">{subjectStyle(s.subject).emoji}</span>{s.title}{#if s.by_parent}<small class="tag">von Eltern</small>{/if}{#if s.exam_date}<small class="muted"> · Arbeit {formatShortDate(s.exam_date)}</small>{/if}</span>
            {#if s.done}<span class="ok" aria-label="erledigt">✓</span>
            {:else}<button class="drop" disabled={busy} aria-label={`${s.title} streichen`} onclick={() => act('drop', s.key)}>Streichen</button>{/if}
          </li>
        {:else}
          <li class="muted">Kein Lernschritt an diesem Tag.</li>
        {/each}
      </ul>
      {#if cur.candidates.length}
        <button class="linkish" aria-expanded={more} onclick={() => (more = !more)}>{more ? 'Weniger zeigen' : `Weitere hinzufügen (${cur.candidates.length})`}</button>
        {#if more}
          <ul class="steps cand">
            {#each cur.candidates as c (c.key)}
              <li><span class="t"><span class="sub">{subjectStyle(c.subject).emoji}</span>{c.title}{#if c.exam_date}<small class="muted"> · Arbeit {formatShortDate(c.exam_date)}</small>{/if}</span>
                <button disabled={busy} aria-label={`${c.title} hinzufügen`} onclick={() => act('add', c.key)}>+</button></li>
            {/each}
          </ul>
        {/if}
      {/if}
      {#if cur.changes.length}
        <div class="log">
          <p class="small muted">Geändert: {#each cur.changes as ch, i}{i ? ' · ' : ''}{time(ch.at)} {ch.title ? `${ch.title} ` : ''}{what[ch.action] ?? ch.action}{ch.by ? ` (${ch.by})` : ''}{/each}</p>
          <button class="linkish" disabled={busy} onclick={() => act('reset')}>Zurücksetzen</button>
        </div>
      {/if}
      <p class="small muted">Gestrichenes zählt nicht als versäumt. Was ihr hinzufügt, gehört zum Tagesplan.</p>
    {/if}
    {#if error}<p class="error-box" role="alert">{error}</p>{/if}
    <button class="close" onclick={onclose}>Fertig</button>
  </div>
</div>

<style>
  .adjust { max-height: 90vh; overflow: auto; }
  .tabs { display: flex; gap: var(--sp-1); flex-wrap: wrap; margin-bottom: var(--sp-2); }
  .tabs button { flex: 1 1 auto; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg); padding: 6px 10px; font-size: var(--fs-sm); }
  .tabs button.cur { background: var(--accent); color: var(--accent-fg, #fff); border-color: var(--accent); }
  .count { display: flex; justify-content: space-between; align-items: center; gap: var(--sp-2); margin: var(--sp-2) 0; }
  .pm { display: flex; gap: var(--sp-1); }
  .pm button { min-width: 44px; min-height: 44px; font-size: 1.3rem; border-radius: var(--radius); border: 1px solid var(--border); background: var(--bg-soft, var(--bg)); }
  .steps { list-style: none; padding: 0; margin: 0 0 var(--sp-2); }
  .steps li { display: flex; justify-content: space-between; align-items: center; gap: var(--sp-2); padding: 6px 0; border-bottom: 1px solid var(--border); }
  .steps li.done .t { color: var(--fg-muted); text-decoration: line-through; }
  .steps .t { min-width: 0; overflow-wrap: anywhere; }
  .sub { margin-right: 6px; }
  .tag { margin-left: 6px; padding: 1px 6px; border-radius: 8px; background: var(--warm-soft, #fde68a); font-size: var(--fs-xs); }
  .steps button { min-height: 36px; padding: 0 10px; border-radius: var(--radius); border: 1px solid var(--border); background: var(--bg); flex: none; }
  .ok { color: var(--ok, green); flex: none; }
  .linkish { background: none; border: none; color: var(--accent); padding: 6px 0; text-decoration: underline; }
  .small { font-size: var(--fs-xs); }
  .log { display: flex; justify-content: space-between; align-items: baseline; gap: var(--sp-2); flex-wrap: wrap; }
  .close { width: 100%; margin-top: var(--sp-2); min-height: 44px; }
</style>
