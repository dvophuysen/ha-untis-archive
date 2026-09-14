<script>
  // Ein Knopf, ein Eintrag. Abschließen ist auch mit offenen Punkten erlaubt:
  // Die App hält fest, was war, und verhängt nichts.
  import { api } from './api.js';

  let { accountId, state = null, openCount = 0, onclosed = () => {} } = $props();
  let saving = $state(false), error = $state('');

  const closed = $derived(state?.closed ?? null);
  const week = $derived(state?.reliability?.current ?? null);
  const time = $derived.by(() => {
    if (!closed?.closed_at) return '';
    const d = new Date(closed.closed_at);
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  });

  async function close() {
    if (saving || closed) return;
    saving = true; error = '';
    try { onclosed(await api.post(`/api/accounts/${accountId}/day-close`, {})); }
    catch { error = 'Der Abschluss konnte nicht gespeichert werden. Bitte noch einmal tippen.'; }
    finally { saving = false; }
  }
</script>

<div class="day-close">
  {#if closed}
    <p class="done"><span aria-hidden="true">✓</span> Abgeschlossen{#if time} um {time} Uhr{/if}. Morgen früh kommt keine Erinnerung mehr.</p>
  {:else}
    <button class="close-day" onclick={close} disabled={saving}>
      {saving ? 'Wird gespeichert …' : openCount ? 'Trotzdem abschließen' : 'Tag abschließen'}
    </button>
    {#if openCount}<p class="hint">Es ist noch etwas offen. Abschließen darfst du trotzdem — es wird so festgehalten, wie es ist.</p>{/if}
  {/if}
  {#if error}<p class="hint" role="alert">{error}</p>{/if}
  {#if week?.evenings}
    <p class="week">Diese Woche {week.own} von {week.evenings} Abenden selbst abgeschlossen.</p>
  {/if}
</div>

<style>
  .day-close{border-top:1px solid var(--border);margin-top:12px;padding-top:12px}
  .close-day{width:100%;min-height:52px;font-size:1.05rem;font-weight:550;border-radius:12px;border:1px solid var(--accent);background:var(--accent);color:#fff}
  .close-day[disabled]{opacity:.7}
  .done{display:flex;align-items:center;gap:10px;margin:0;font-weight:550}
  .done>span{font-size:1.4rem}
  .hint,.week{color:var(--fg-muted);font-size:.9rem;margin:8px 0 0}
</style>
