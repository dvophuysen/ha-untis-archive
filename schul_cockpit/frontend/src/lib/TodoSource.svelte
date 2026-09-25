<script>
  // Woher ein Hinweis auf fehlendes Material kommt, und „Nicht nötig“ (D196).
  // Steht unter einem Eintrag aus „Erledigen“; eigene Knöpfe, damit nichts in
  // einem anderen Knopf steckt.
  import { api } from './api.js';
  import { setActiveAccount } from './store.svelte.js';
  import { setViewMode } from './viewMode.svelte.js';
  import { forgetTodo, loadTodo } from './parentTodo.svelte.js';

  let { it } = $props();
  let asking = $state(false), busy = $state(false), error = $state('');

  function open() {
    if (it.account_id) setActiveAccount(it.account_id);
    setViewMode('parent');
  }
  async function dismiss() {
    const d = it.dismiss;
    busy = true; error = '';
    try {
      await api.post(`/api/accounts/${it.account_id}/materials/sources/dismiss`, { subject: d.subject, label: d.label, pages: d.pages });
      forgetTodo();
      await loadTodo(0);
    } catch (e) { error = e.message; }
    busy = false; asking = false;
  }
</script>

{#if it.source || it.dismiss}
  <div class="src">
    {#if it.source}
      <p class="from">Aus: {it.source.label}{#if it.source.href} · <a href={it.source.href} onclick={open}>Ansehen</a>{/if}</p>
      {#if it.source.quote}<p class="quote">„{it.source.quote}“</p>{/if}
    {/if}
    {#if it.dismiss}
      {#if asking}
        <p class="ask" role="group" aria-label="Nicht nötig bestätigen">„{it.dismiss.what}“ ist nicht nötig? Dieser Hinweis kommt nicht wieder.
          <button class="ghost" disabled={busy} onclick={dismiss}>Ja, streichen</button>
          <button class="ghost" disabled={busy} onclick={() => (asking = false)}>Abbrechen</button></p>
      {:else}
        <button class="ghost not" onclick={() => (asking = true)}>Nicht nötig</button>
      {/if}
      {#if error}<p class="err" role="alert">{error}</p>{/if}
    {/if}
  </div>
{/if}

<style>
  .src { padding: 0 0 var(--sp-2); font-size: var(--fs-xs); color: var(--fg-muted); overflow-wrap: anywhere; }
  .src p { margin: 0 0 2px; }
  .quote { font-style: italic; opacity: .85; }
  .src a { color: var(--accent); }
  .not, .ask button { font-size: var(--fs-xs); padding: 2px 8px; min-height: 32px; margin-top: 2px; color: var(--accent); }
  .ask { color: var(--fg); }
  .err { color: var(--warn-fg); }
</style>
