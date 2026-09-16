<script>
  // Der Wochenrückblick: wenige Sätze aus gespeicherten Zahlen, kein Modell, keine Note.
  import { api } from './api.js';
  let { accountId } = $props();
  let data = $state(null), error = $state(''), opened = $state(false);
  let request = 0;
  $effect(() => {
    const account = accountId, ticket = ++request;
    data = null; error = '';
    if (!account) return;
    api.get(`/api/accounts/${account}/week-review`).then(r => { if (ticket === request) data = r; })
      .catch(e => { if (ticket === request) error = e.message; });
  });
</script>

<div class="block week-review">
  <button class="week-head" aria-expanded={opened} onclick={() => opened = !opened}>
    <h3>Diese Woche{#if data} · {data.week.label}{/if}</h3>
    <span class="chevron" class:opened>›</span>
  </button>
  {#if error}<p class="error-box" role="alert">{error}</p>
  {:else if !data}<p class="muted">Lade …</p>
  {:else}
    <ul class:short={!opened}>
      {#each (opened ? data.lines : data.lines.slice(0, 3)) as line}<li>{line}</li>{/each}
    </ul>
    {#if !opened && data.lines.length > 3}<button class="text-action" onclick={() => opened = true}>Alle {data.lines.length} Punkte</button>{/if}
  {/if}
</div>

<style>
  .week-review { margin-top: 8px; }
  .week-head { display: flex; justify-content: space-between; align-items: center; width: 100%; border: 0; background: transparent; padding: 4px 0; color: var(--fg); text-align: left; }
  .week-head h3 { margin: 0; font-size: 0.95rem; }
  .chevron { color: var(--accent); font-size: 1.3rem; transition: transform .15s; }
  .chevron.opened { transform: rotate(90deg); }
  ul { margin: 4px 0 0; padding-left: 18px; font-size: 0.9rem; line-height: 1.4; }
  li { margin: 3px 0; }
  .muted { font-size: 0.85rem; color: var(--fg-muted); }
  .text-action { border: 0; background: transparent; color: var(--accent); padding: 8px 0; min-height: 40px; }
</style>
