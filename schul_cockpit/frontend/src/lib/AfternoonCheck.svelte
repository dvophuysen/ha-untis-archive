<script>
  // Nach der letzten Stunde bis zum Abend: Steht alles von heute in der App?
  // Eine Frage, zwei Antworten. Foto oder „nichts Neues“, kein Formular.
  import { onMount } from 'svelte';
  import { api } from './api.js';
  let { accountId, onchange } = $props();
  let data = $state(null), busy = $state(false), error = $state(''), message = $state('');
  let fileInput = $state(null);
  let request = 0;
  async function load() {
    const id = accountId, ticket = ++request;
    if (!id) return;
    try {
      const result = await api.get(`/api/accounts/${id}/afternoon-check`);
      if (ticket !== request || id !== accountId) return;
      data = result;
    } catch (e) { if (ticket === request) error = e.message; }
  }
  $effect(() => { void accountId; data = null; message = ''; error = ''; load(); });
  onMount(() => {
    const resume = () => { if (!document.hidden && !busy) load(); };
    document.addEventListener('visibilitychange', resume);
    return () => { request++; document.removeEventListener('visibilitychange', resume); };
  });
  async function act(fn) {
    if (busy) return;
    busy = true; error = '';
    try { await fn(); } catch (e) { error = e.message; } finally { busy = false; }
  }
  async function nothing() {
    await act(async () => {
      data = await api.post(`/api/accounts/${accountId}/afternoon-check/nothing`);
      message = data.photos ? 'Gut, dann ist alles notiert.' : 'Gut. Dann ist für heute nichts Neues dazugekommen.';
      onchange?.();
    });
  }
  async function photo(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    await act(async () => {
      const body = new FormData();
      body.append('file', file);
      const saved = await api.post(`/api/accounts/${accountId}/afternoon-check/photo`, body);
      data = saved.state;
      message = 'Gespeichert. Die Aufgabe steht schon in deiner Liste; Fach und Termin trage ich gleich nach.';
      onchange?.();
    });
  }
</script>

{#if data?.active || (data?.closed && message)}
  <section class="day-section afternoon" aria-live="polite">
    <h3>Alles von heute notiert?</h3>
    {#if error}<p class="error-box" role="alert">{error}</p>{/if}
    {#if message}<p class="save-message" role="status">{message}</p>{/if}
    {#if data.active}
      {#if data.photos}
        <p>{data.photos === 1 ? 'Ein Foto ist gespeichert.' : `${data.photos} Fotos sind gespeichert.`} Noch eine Aufgabe, die fehlt?</p>
      {:else}
        <p>Steht jede Hausaufgabe von heute in der App? Wenn eine fehlt, fotografiere sie. Fach und Termin trage ich ein.</p>
      {/if}
      <div class="actions">
        <button class="primary" disabled={busy} onclick={() => fileInput?.click()}>{data.photos ? 'Noch eine fotografieren' : 'Hausaufgabe fotografieren'}</button>
        <input bind:this={fileInput} type="file" accept="image/*,application/pdf" capture="environment" hidden onchange={photo} />
        <button disabled={busy} onclick={nothing}>{data.photos ? 'Das war alles' : 'Nichts Neues'}</button>
      </div>
    {/if}
  </section>
{/if}

<style>
  .afternoon { border-color: var(--accent); }
  .afternoon h3 { margin-top: 0; }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
  .actions button { flex: 1 1 45%; min-height: 48px; }
</style>
