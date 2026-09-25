<script>
  // „Wer benutzt das Gerät?“ (D175): ein Tipp aufs Profil, kein PIN.
  import { api } from './api.js';
  import { appState, setActiveAccount, loadMe } from './store.svelte.js';
  import { view, setViewMode } from './viewMode.svelte.js';

  let { onclose, navigate } = $props();
  let busy = $state(false), error = $state('');
  const initials = (name) => (name || '?').split(/\s+/).map((p) => p[0]).join('').slice(0, 2).toUpperCase();

  async function leaveTest() {
    // Beim Verlassen des Testmodus alles zurücknehmen, was dabei geändert wurde.
    await api.post('/api/my-changes/revert-all-demo');
    await api.patch('/api/me/demo-mode', { enabled: false });
  }
  async function choose(mode, accountId = null) {
    if (busy) return;
    busy = true; error = '';
    try {
      if (view.mode === 'test' && mode !== 'test') await leaveTest();
      if (mode === 'test' && !appState.me?.demo_mode) await api.patch('/api/me/demo-mode', { enabled: true });
      if (accountId) setActiveAccount(accountId);
      setViewMode(mode);
      await loadMe();
      onclose();
      navigate(mode === 'parent' ? 'overview' : 'today');
    } catch (e) {
      error = e.message || 'Umschalten hat nicht geklappt.';
    } finally { busy = false; }
  }
</script>

<div class="modal-backdrop" role="presentation" onclick={onclose}>
  <div class="modal sheet" role="dialog" aria-modal="true" aria-label="Wer benutzt das Gerät?" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.key === 'Escape' && onclose()}>
    <h2>Wer benutzt das Gerät?</h2>
    <button class="opt" class:cur={view.mode === 'parent'} disabled={busy} onclick={() => choose('parent')}>
      <span class="pp me">{initials(appState.me?.display_name)}</span>
      <span><b>Ich</b><small>Familie, Lernstand und Einstellungen</small></span>
    </button>
    {#each appState.me?.accounts ?? [] as kid (kid.id)}
      <div class="kid">
        <button class="opt" class:cur={view.mode === 'mirror' && appState.activeAccountId === kid.id} disabled={busy} onclick={() => choose('mirror', kid.id)}>
          <span class="pp">{initials(kid.name)}</span>
          <span><b>{kid.name} ansehen</b><small>nur lesen, nichts wird geändert</small></span>
        </button>
        <button class="opt" class:cur={view.mode === 'child' && appState.activeAccountId === kid.id} disabled={busy} onclick={() => choose('child', kid.id)}>
          <span class="pp kidc">{initials(kid.name)}</span>
          <span><b>{kid.name} benutzt das Gerät</b><small>alles zählt für {kid.name}</small></span>
        </button>
      </div>
    {/each}
    {#if appState.me?.is_admin}
      <button class="opt" class:cur={view.mode === 'test'} disabled={busy} onclick={() => choose('test')}>
        <span class="pp test">T</span>
        <span><b>Testmodus</b><small>Änderungen werden beim Beenden zurückgenommen</small></span>
      </button>
    {/if}
    {#if error}<p class="error-box" role="alert">{error}</p>{/if}
    <button class="ghost close" onclick={onclose}>Schließen</button>
  </div>
</div>

<style>
  .sheet{display:grid;gap:var(--sp-2)}
  h2{font-size:var(--fs-lg);margin:0 0 var(--sp-1)}
  .kid{display:grid;gap:var(--sp-2);padding-top:var(--sp-2);border-top:1px solid var(--border)}
  .opt{display:grid;grid-template-columns:40px 1fr;gap:var(--sp-3);align-items:center;text-align:left;background:var(--bg-elevated);border:2px solid transparent;border-radius:var(--r-md);padding:var(--sp-2) var(--sp-3);min-height:58px}
  .opt.cur{border-color:var(--accent)}
  .opt b{display:block;font-size:var(--fs-sm)}.opt small{font-size:var(--fs-xs);color:var(--fg-muted)}
  .pp{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;font-weight:800;font-size:var(--fs-xs);background:var(--accent);color:var(--accent-fg)}
  .pp.me{background:var(--fg-muted);color:var(--bg-card)}
  .pp.kidc{background:var(--st-sitzt);color:#fff}
  .pp.test{background:#c2410c;color:#fff}
  .close{justify-self:center}
</style>
