<script>
  import { api } from '../lib/api.js';
  import { loadMe } from '../lib/store.svelte.js';

  let users = $state([]);
  let loading = $state(true);
  let selected = $state(null);
  let pin = $state('');
  let error = $state(null);
  let busy = $state(false);

  async function load() {
    loading = true;
    try {
      users = (await api.get('/api/auth/users')).users;
      if (users.length === 1) selected = users[0];
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { load(); });

  function press(d) {
    if (pin.length < 8) pin += d;
  }
  function back() { pin = pin.slice(0, -1); }

  async function submit() {
    if (pin.length < 4) return;
    busy = true;
    error = null;
    try {
      await api.post('/api/auth/login', { user_id: selected.id, pin });
      await loadMe();
    } catch (e) {
      error = e.message;
      pin = '';
    } finally {
      busy = false;
    }
  }

  $effect(() => {
    if (pin.length >= 4 && selected) { /* allow manual submit */ }
  });

  function roleLabel(r) {
    return r === 'admin' ? 'Admin' : r === 'parent' ? 'Eltern' : r === 'child' ? 'Kind' : '';
  }
</script>

<div class="login-wrap">
  <div class="login-card">
    <div class="login-logo">🎓</div>
    <h1>Schul-Cockpit</h1>

    {#if loading}
      <div class="empty"><span class="spinner"></span></div>
    {:else if users.length === 0}
      <p class="muted" style="text-align:center;">
        Es wurde noch kein PIN vergeben.<br><br>
        Bitte zuerst in Home Assistant (über die Seitenleiste „Schul-Cockpit")
        als Eltern/Admin im <strong>Setup</strong> für jedes Kind einen PIN festlegen.
        Danach kann man sich hier anmelden.
      </p>
      <button style="width:100%; margin-top:1rem;" onclick={load}>Erneut prüfen</button>
    {:else if !selected}
      <p class="muted" style="text-align:center; margin-bottom:0.6rem;">Wer bist du?</p>
      {#each users as u}
        <button class="who" onclick={() => { selected = u; pin = ''; }}>
          <span>{u.display_name}</span>
          <span class="dim">{roleLabel(u.role)}</span>
        </button>
      {/each}
    {:else}
      <div class="row between" style="margin-bottom:0.6rem;">
        <button class="ghost" onclick={() => { selected = null; pin = ''; error = null; }}>← zurück</button>
        <strong>{selected.display_name}</strong>
      </div>

      <div class="pin-dots">
        {#each Array(Math.max(4, pin.length)) as _, i}
          <span class="dot" class:filled={i < pin.length}></span>
        {/each}
      </div>

      {#if error}<div class="error-box" style="text-align:center;">{error}</div>{/if}

      <div class="pad">
        {#each [1,2,3,4,5,6,7,8,9] as d}
          <button class="key" onclick={() => press(String(d))} disabled={busy}>{d}</button>
        {/each}
        <button class="key" onclick={back} disabled={busy} aria-label="löschen">⌫</button>
        <button class="key" onclick={() => press('0')} disabled={busy}>0</button>
        <button class="key go" onclick={submit} disabled={busy || pin.length < 4} aria-label="anmelden">→</button>
      </div>
    {/if}
  </div>
</div>

<style>
  .login-wrap {
    min-height: 100vh;
    min-height: 100dvh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
  }
  .login-card {
    width: 100%;
    max-width: 360px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 1.5rem 1.2rem;
    box-shadow: var(--shadow);
  }
  .login-logo { font-size: 3rem; text-align: center; }
  h1 { text-align: center; font-size: 1.3rem; margin: 0.2rem 0 1rem; }
  .who {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 0.4rem 0;
    padding: 0.9rem 1rem;
    font-size: 1.05rem;
  }
  .pin-dots {
    display: flex;
    gap: 0.6rem;
    justify-content: center;
    margin: 1rem 0;
  }
  .dot {
    width: 14px; height: 14px;
    border-radius: 50%;
    border: 2px solid var(--fg-muted);
  }
  .dot.filled { background: var(--accent); border-color: var(--accent); }
  .pad {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.6rem;
    margin-top: 0.6rem;
  }
  .key {
    font-size: 1.4rem;
    padding: 0.9rem 0;
    min-height: 60px;
  }
  .key.go { background: var(--accent); color: #fff; border-color: var(--accent); }
</style>
