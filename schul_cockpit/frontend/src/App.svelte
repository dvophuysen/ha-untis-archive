<script>
  import { onMount } from 'svelte';
  import { appState, loadMe, setActiveAccount, activeAccount } from './lib/store.svelte.js';
  import Today from './routes/Today.svelte';
  import Plan from './routes/Plan.svelte';
  import Week from './routes/Week.svelte';
  import Subjects from './routes/Subjects.svelte';
  import SubjectDetail from './routes/SubjectDetail.svelte';
  import Absences from './routes/Absences.svelte';
  import Klausuren from './routes/Klausuren.svelte';
  import Setup from './routes/Setup.svelte';
  import Settings from './routes/Settings.svelte';
  import MyChanges from './routes/MyChanges.svelte';
  import Login from './routes/Login.svelte';
  import ExamSetup from './routes/ExamSetup.svelte';
  import { api } from './lib/api.js';

  async function logout() {
    try { await api.post('/api/auth/logout'); } catch (_) { /* ignore */ }
    await loadMe();
  }

  let route = $state(parseHash());

  function parseHash() {
    const h = window.location.hash.replace(/^#\/?/, '');
    if (!h) return { name: 'today' };
    const [name, ...rest] = h.split('/');
    return { name, args: rest };
  }

  function navigate(name, ...args) {
    const path = args.length ? `${name}/${args.join('/')}` : name;
    window.location.hash = `#/${path}`;
  }

  onMount(() => {
    loadMe();
    const handler = () => (route = parseHash());
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  });

  const acc = $derived(activeAccount());

  const navItems = [
    { name: 'today', icon: '📅', label: 'Heute' },
    { name: 'plan', icon: '🎯', label: 'Plan' },
    { name: 'week', icon: '📊', label: 'Woche' },
    { name: 'subjects', icon: '📚', label: 'Fächer' },
    { name: 'klausuren', icon: '📝', label: 'Klausur' },
    { name: 'absences', icon: '🤒', label: 'Fehlt' },
  ];
</script>

{#if appState.needsLogin}
  <Login />
{:else}
<div class="app-shell">
  <header class="top-bar">
    <div class="col" style="gap: 0">
      <h1>Schul-Cockpit</h1>
      {#if appState.me && appState.me.accounts.length > 1}
        <select
          class="top-meta"
          style="border:none; background:transparent; padding:0; min-height: auto; font-size:0.85rem;"
          value={appState.activeAccountId}
          onchange={(e) => setActiveAccount(Number(e.currentTarget.value))}
        >
          {#each appState.me.accounts as a}
            <option value={a.id}>{a.name}</option>
          {/each}
        </select>
      {:else if acc}
        <span class="top-meta">{acc.name}</span>
      {/if}
    </div>
    <div class="row gap-sm">
      {#if appState.me?.is_admin}
        <button class="ghost" onclick={() => navigate('setup')} title="Setup">⚙️</button>
      {/if}
      {#if acc}
        <button class="ghost" onclick={() => navigate('settings')} title="Einstellungen">🛠</button>
      {/if}
      {#if appState.me?.auth_source === 'pin'}
        <button class="ghost" onclick={logout} title="Abmelden">⏻</button>
      {/if}
    </div>
  </header>

  {#if appState.me?.demo_mode}
    <div
      style="background: var(--substitution); color: #fff; padding: 0.5rem 1rem; font-size: 0.85rem; display:flex; justify-content:space-between; align-items:center; gap:0.5rem;"
    >
      <span>🧪 <strong>Demo-Modus</strong> · {appState.me.open_audit_count ?? 0} Änderungen geloggt</span>
      <button
        class="ghost"
        style="color:#fff; border-color:rgba(255,255,255,0.4); padding:0.2rem 0.6rem; min-height:32px; font-size:0.8rem;"
        onclick={() => navigate('changes')}
      >Verwalten</button>
    </div>
  {/if}

  <main class="content">
    {#if appState.loading}
      <div class="empty"><span class="spinner"></span><br>lade…</div>
    {:else if appState.error}
      <div class="error-box">Fehler: {appState.error}</div>
    {:else if !appState.me}
      <div class="empty">Nicht eingeloggt.</div>
    {:else if appState.me.setup_needed && appState.me.is_admin && route.name !== 'setup'}
      <div class="banner">
        Es sind neue HA-Nutzer da, die noch nicht zugeordnet sind, oder noch keine Verlinkungen existieren.
        <button class="primary" style="margin-top:0.6rem" onclick={() => navigate('setup')}>Jetzt einrichten</button>
      </div>
    {:else if !acc && !['setup'].includes(route.name)}
      <div class="empty">
        Dein Account ist noch mit keinem Kind verlinkt.
        {#if appState.me.is_admin}
          <br><br><button class="primary" onclick={() => navigate('setup')}>Setup öffnen</button>
        {:else}
          <br><br>Bitte den Eltern-Account bitten, dich zuzuordnen.
        {/if}
      </div>
    {:else if route.name === 'setup'}
      <Setup {navigate} />
    {:else if route.name === 'settings'}
      <Settings accountId={appState.activeAccountId} />
    {:else if route.name === 'exams'}
      <ExamSetup />
    {:else if route.name === 'changes'}
      <MyChanges />
    {:else if route.name === 'today'}
      <Today accountId={appState.activeAccountId} />
    {:else if route.name === 'plan' || route.name === 'tasks'}
      <Plan accountId={appState.activeAccountId} />
    {:else if route.name === 'week'}
      <Week accountId={appState.activeAccountId} />
    {:else if route.name === 'klausuren'}
      <Klausuren accountId={appState.activeAccountId} />
    {:else if route.name === 'absences'}
      <Absences accountId={appState.activeAccountId} />
    {:else if route.name === 'subjects'}
      <Subjects accountId={appState.activeAccountId} {navigate} />
    {:else if route.name === 'subject'}
      <SubjectDetail accountId={appState.activeAccountId} subjectId={Number(route.args?.[0])} />
    {:else}
      <div class="empty">Unbekannte Seite.</div>
    {/if}
  </main>

  {#if acc && !['setup','settings'].includes(route.name)}
    <nav class="bottom-nav">
      {#each navItems as item}
        <button
          class:active={route.name === item.name || (item.name === 'subjects' && route.name === 'subject')}
          onclick={() => navigate(item.name)}
        >
          <span class="icon">{item.icon}</span>
          <span>{item.label}</span>
        </button>
      {/each}
    </nav>
  {/if}
</div>
{/if}
