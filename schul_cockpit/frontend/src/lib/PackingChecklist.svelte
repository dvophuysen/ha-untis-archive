<script>
  import { onMount } from 'svelte';
  import { api } from './api.js';
  import { formatShortDate } from './format.js';
  let { accountId, schoolDay } = $props();
  let data = $state(null), error = $state(''), loading = $state(true), busy = $state(false);
  let request = 0;
  async function load(reset = false) {
    const account = accountId, day = schoolDay, ticket = ++request;
    if (reset) { data = null; busy = false; }
    if (!account || !day) { loading = false; return; }
    loading = true; error = '';
    try {
      const result = await api.get(`/api/accounts/${account}/packing/${day}`);
      if (ticket !== request || account !== accountId || day !== schoolDay) return;
      if (!Array.isArray(result.items)) throw new Error('Die Packliste konnte nicht geladen werden.');
      data = result;
    } catch (e) { if (ticket === request) error = e.message || 'Die Packliste konnte nicht geladen werden.'; }
    finally { if (ticket === request) loading = false; }
  }
  $effect(() => { void accountId; void schoolDay; load(true); });
  onMount(() => {
    const resume = () => { if (!document.hidden && !busy) load(); };
    document.addEventListener('visibilitychange', resume);
    return () => { request++; document.removeEventListener('visibilitychange', resume); };
  });
  async function toggle(item) {
    if (busy || loading || !data?.can_write) return;
    const account = accountId, day = schoolDay, ticket = ++request;
    busy = true; error = '';
    try {
      const result = await api.put(`/api/accounts/${account}/packing/${day}`, {
        item_key: item.key, done: !item.done, revision: item.revision, plan_key: data.plan_key,
      });
      if (ticket === request && account === accountId && day === schoolDay) data = result;
    } catch (e) {
      if (ticket === request) error = e.message || 'Nicht gespeichert. Bitte noch einmal versuchen.';
    } finally { if (ticket === request) busy = false; }
  }
</script>

<section class="packing" aria-label="Packliste">
  <h4>Tasche packen · {formatShortDate(schoolDay)}</h4>
  {#if error}<p class="error-box" role="alert">{error}</p><button class="ghost" disabled={busy} onclick={() => load()}>Packliste neu laden</button>{/if}
  {#if loading && !data}<p class="muted">Lade deine Packliste …</p>
  {:else if data?.status === 'no_lessons'}<p class="muted">Für diesen Tag ist kein Unterricht zum Packen eingetragen.</p>
  {:else if data}
    {#each data.items as item (item.key)}
      <button class="pack-row" class:packed={item.done} aria-pressed={item.done} disabled={busy || loading || !data.can_write} onclick={() => toggle(item)}>
        <span class="pack-check" aria-hidden="true">{item.done ? '✓' : ''}</span><span>{item.label}</span>
      </button>
    {/each}
    <p class="pack-status" role="status">{busy ? 'Wird gespeichert …' : error ? 'Bitte den Packstand prüfen.' : data.status === 'packed' ? 'Deine Packliste ist abgehakt.' : `${data.confirmed_count} von ${data.items.length} Punkten abgehakt`}</p>
    {#if !data.can_write}<p class="muted">Du kannst diese Packliste ansehen.</p>{/if}
  {/if}
</section>

<style>
  .packing{margin-top:14px}h4{font-size:1rem;margin:0 0 8px}
  .pack-row{display:flex;align-items:center;gap:12px;width:100%;text-align:left;border:0;border-bottom:1px solid var(--border);border-radius:0;padding:10px 0;background:transparent;color:var(--fg);min-height:48px}
  .pack-check{display:flex;align-items:center;justify-content:center;flex:0 0 28px;height:28px;border:2px solid var(--fg-muted);border-radius:7px;font-weight:600}
  .packed .pack-check{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
  .packed>span:last-child{color:var(--fg-muted)}.pack-status{font-size:.9rem;margin:12px 0 0;color:var(--fg-muted)}
  .pack-row:disabled{cursor:default}.pack-row>span:last-child{overflow-wrap:anywhere;min-width:0}
</style>
