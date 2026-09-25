<script>
  // Kind wählen in der Elternansicht (D183): Chips statt der alten Auswahl oben links.
  import { appState, setActiveAccount } from './store.svelte.js';
  let { label = 'Kind', value = undefined, onpick = null } = $props();
  const current = $derived(value === undefined ? appState.activeAccountId : value);
  function pick(id) {
    if (onpick) onpick(id);
    else setActiveAccount(id);
  }
</script>

{#if (appState.me?.accounts?.length ?? 0) > 1}
  <div class="kid-chips" role="group" aria-label={label}>
    {#each appState.me.accounts as a (a.id)}
      <button class="chip" aria-pressed={current === a.id} onclick={() => pick(a.id)}>{a.name}</button>
    {/each}
  </div>
{/if}

<style>
  .kid-chips { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin: 0 0 var(--sp-3); }
  .chip { min-height: 40px; padding: 6px 14px; border-radius: var(--r-pill); font-size: var(--fs-sm); background: var(--bg-card); border: 1px solid var(--border); color: var(--fg); }
  .chip[aria-pressed="true"] { background: var(--accent); color: var(--accent-fg); border-color: var(--accent); font-weight: 700; }
</style>
