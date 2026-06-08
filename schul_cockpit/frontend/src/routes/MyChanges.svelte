<script>
  import { api } from '../lib/api.js';
  import { loadMe } from '../lib/store.svelte.js';

  let entries = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let demoOnly = $state(false);
  let busy = $state(false);

  async function load() {
    loading = true;
    try {
      const q = demoOnly ? '?demo_only=true' : '';
      entries = (await api.get(`/api/my-changes${q}`)).entries;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void demoOnly; load(); });

  async function revertOne(id) {
    busy = true;
    try {
      await api.post(`/api/my-changes/${id}/revert`);
      await load();
      await loadMe();
    } finally {
      busy = false;
    }
  }

  async function revertAllDemo() {
    if (!confirm('Wirklich ALLE Demo-Änderungen zurücknehmen?')) return;
    busy = true;
    try {
      const r = await api.post('/api/my-changes/revert-all-demo');
      alert(`${r.reverted} Änderungen rückgängig gemacht.`);
      await load();
      await loadMe();
    } finally {
      busy = false;
    }
  }

  function fmtTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  }

  function emoji(kind, op) {
    if (kind === 'task') return op === 'delete' ? '🗑' : op === 'insert' ? '➕' : '✏️';
    if (kind === 'checkin') return '😀';
    if (kind === 'caught_up') return '✓';
    if (kind === 'settings') return '⚙️';
    return '·';
  }
</script>

<div class="row between" style="margin-bottom:0.6rem;">
  <h2 style="margin:0; font-size:1.1rem;">Meine Änderungen</h2>
  <button class="ghost" onclick={() => history.back()}>← zurück</button>
</div>

<div class="banner">
  Hier siehst du jede Änderung, die <strong>du</strong> in der App gemacht hast — und kannst sie einzeln oder alle (im Demo-Modus) zurücknehmen.
</div>

<div class="row gap-sm" style="margin-bottom:0.5rem;">
  <button class:primary={demoOnly} onclick={() => (demoOnly = !demoOnly)}>
    {demoOnly ? '✓ Nur Demo' : 'Nur Demo-Änderungen zeigen'}
  </button>
  <button class="danger" onclick={revertAllDemo} disabled={busy}>Alle Demo-Änderungen rückgängig</button>
</div>

{#if error}<div class="error-box">{error}</div>{/if}

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if entries.length === 0}
  <div class="empty">Keine {demoOnly ? 'Demo-' : ''}Änderungen.</div>
{:else}
  {#each entries as e (e.id)}
    <div class="card compact">
      <div class="row between">
        <div style="flex:1; min-width:0;">
          <div>
            <span>{emoji(e.target_kind, e.op_type)}</span>
            <span style="font-weight:500;">{e.label ?? `${e.op_type} ${e.target_kind}`}</span>
            {#if e.demo_mode}<span class="badge" style="background:var(--substitution); color:#fff; border-color:transparent;">DEMO</span>{/if}
          </div>
          <div class="dim">{fmtTime(e.created_at)}</div>
        </div>
        {#if e.reverted_at}
          <span class="dim">↶ rückgängig</span>
        {:else}
          <button class="ghost" disabled={busy} onclick={() => revertOne(e.id)}>↶</button>
        {/if}
      </div>
    </div>
  {/each}
{/if}
