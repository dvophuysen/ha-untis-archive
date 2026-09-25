<script>
  // Erledigen (D183): was ein Elternteil tun muss oder sollte, je Kind
  // gruppiert. Jede Zeile führt in die Elternansicht mit Schreibrecht, nie ins
  // Mitlesen: Dort scheiterte die Aktion.
  import ActionLabel from '../lib/ActionLabel.svelte';
  import { appState, setActiveAccount } from '../lib/store.svelte.js';
  import { setViewMode } from '../lib/viewMode.svelte.js';
  import { jumpHash } from '../lib/jump.js';
  import { todo, loadTodo } from '../lib/parentTodo.svelte.js';
  import { onMount } from 'svelte';

  onMount(() => { loadTodo(0); });

  function go(it, accountId = null) {
    if (accountId) setActiveAccount(accountId);
    setViewMode('parent');
    window.location.hash = jumpHash(it.action);
  }
  const data = $derived(todo.data);
  const open = $derived(data ? data.kids.filter((k) => k.items.length) : []);
</script>

<header class="head"><h2>Erledigen</h2>{#if data}<p>{data.total ? `${data.total} ${data.total === 1 ? 'Punkt' : 'Punkte'} für dich` : 'Nichts offen'}</p>{/if}</header>
{#if todo.error && !data}<div class="error-box" role="alert">{todo.error}</div>{/if}
{#if !data && !todo.error}<div class="empty"><span class="spinner"></span></div>{/if}
{#if data}
  {#if todo.error}<p class="stale" role="status">Stand nicht aktualisiert: {todo.error}</p>{/if}
  {#if data.blocking.length}
    <section class="group block" aria-label="Zuerst">
      <h3>Zuerst</h3>
      {#each data.blocking as it (it.key)}
        <button class="item" onclick={() => go(it)}><span class="tx"><b>{it.title}</b><small>{it.reason}</small></span><span class="go"><ActionLabel label={it.action.label} /></span></button>
      {/each}
    </section>
  {/if}
  {#each open as kid (kid.account_id)}
    <section class="group" aria-label={`Offen für ${kid.name}`}>
      <h3>{kid.name}</h3>
      {#each kid.items as it (it.key)}
        <button class="item" onclick={() => go(it, kid.account_id)}><span class="tx"><b>{it.title}</b><small>{it.reason}</small></span><span class="go"><ActionLabel label={it.action.label} /></span></button>
      {/each}
    </section>
  {/each}
  {#if data.household.length}
    <section class="group" aria-label="Für die Familie">
      <h3>Familie</h3>
      {#each data.household as it (it.key)}
        <button class="item" onclick={() => go(it, appState.activeAccountId)}><span class="tx"><b>{it.title}</b><small>{it.reason}</small></span><span class="go"><ActionLabel label={it.action.label} /></span></button>
      {/each}
    </section>
  {/if}
  {#if !data.total}
    <div class="done card">
      <b>Alles erledigt.</b>
      <p>Sobald etwas fehlt, gegengelesen oder zugeordnet werden muss, steht es hier.</p>
    </div>
  {/if}
{/if}

<style>
  .head h2 { margin: 0; font-size: var(--fs-xl); }
  .head p { margin: 2px 0 var(--sp-3); color: var(--fg-muted); font-size: var(--fs-sm); }
  .group { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--r-md); padding: var(--sp-2) var(--sp-3); margin: 0 0 var(--sp-3); }
  .group.block { border-color: var(--warn-fg); }
  .group h3 { margin: var(--sp-1) 0; font-size: var(--fs-xs); letter-spacing: .04em; text-transform: uppercase; color: var(--fg-muted); }
  .item { display: flex; gap: var(--sp-2); align-items: center; width: 100%; text-align: left; background: transparent; border: 0; border-top: 1px solid var(--border); border-radius: 0; padding: var(--sp-2) 0; min-height: 52px; color: var(--fg); }
  h3 + .item { border-top: 0; }
  .tx { flex: 1; min-width: 0; overflow-wrap: anywhere; }
  .tx b { display: block; font-weight: 600; font-size: var(--fs-sm); }
  .tx small { display: block; color: var(--fg-muted); font-size: var(--fs-xs); margin-top: 2px; }
  .go { flex: none; color: var(--accent); font-size: var(--fs-sm); white-space: nowrap; }
  .done { text-align: center; padding: var(--sp-4); }
  .done p { color: var(--fg-muted); font-size: var(--fs-sm); margin: var(--sp-1) 0 0; }
  .stale { font-size: var(--fs-xs); color: var(--warn-fg); }
</style>
