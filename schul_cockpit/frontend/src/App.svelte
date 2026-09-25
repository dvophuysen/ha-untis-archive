<script>
  import ActionLabel from './lib/ActionLabel.svelte';
  import Icon from './lib/Icon.svelte';
  import DeviceSheet from './lib/DeviceSheet.svelte';
  import { view, setViewMode, touchViewMode, expireViewMode } from './lib/viewMode.svelte.js';
  import { onMount } from 'svelte';
  import { appState, loadMe, setActiveAccount, activeAccount } from './lib/store.svelte.js';
  import Today from './routes/Today.svelte';
  import Overview from './routes/Overview.svelte';
  import Learning from './routes/Learning.svelte';
  import Week from './routes/Week.svelte';
  import Subjects from './routes/Subjects.svelte';
  import SubjectDetail from './routes/SubjectDetail.svelte';
  import Login from './routes/Login.svelte';
  import Lazy from './lib/Lazy.svelte';
  // Selten genutzte Seiten kommen erst beim Öffnen (D177).
  const LAZY = {
    Plan: () => import('./routes/Plan.svelte'),
    Materialien: () => import('./routes/Materialien.svelte'),
    Absences: () => import('./routes/Absences.svelte'),
    Klausuren: () => import('./routes/Klausuren.svelte'),
    Vokabeln: () => import('./routes/Vokabeln.svelte'),
    Setup: () => import('./routes/Setup.svelte'),
    Settings: () => import('./routes/Settings.svelte'),
    Courses: () => import('./routes/Courses.svelte'),
    MyChanges: () => import('./routes/MyChanges.svelte'),
    ExamSetup: () => import('./routes/ExamSetup.svelte'),
  };
  import { api } from './lib/api.js';
  import { startUsagePing } from './lib/usagePing.js';
  import { jumpTo, sectionParam } from './lib/jump.js';

  async function logout() {
    try { await api.post('/api/auth/logout'); } catch (_) { /* ignore */ }
    await loadMe();
  }

  // Ein-Klick-Reparatur verwaister Kind-Verlinkungen. Der Server biegt nur
  // um, wenn die Zuordnung zwingend ist (genau ein verwaister Link, genau
  // ein unverlinkter Account) — sonst landet man im Setup und wählt selbst.
  let repairing = $state(false);
  let repairMsg = $state(null);
  async function repairLinks() {
    repairing = true;
    repairMsg = null;
    try {
      const res = await api.post('/api/link-repair', { apply: true });
      const done = (res.steps ?? []).filter((s) => s.action === 'repoint');
      const open = (res.steps ?? []).filter((s) => s.action === 'skipped_ambiguous');
      await loadMe();
      if (done.length > 0) {
        repairMsg = `✓ ${done.map((s) => s.to_name).join(', ')} wieder verknüpft`;
      }
      if (open.length > 0) {
        repairMsg = 'Zuordnung nicht eindeutig — bitte im Setup wählen.';
        navigate('setup');
      }
    } catch (e) {
      repairMsg = e.message;
    } finally {
      repairing = false;
    }
  }

  // Wenn die App ohne Hash geöffnet wird, wollen wir Eltern mit ≥2 Kindern
  // auf das Übersichts-Dashboard schicken — aber nur, sobald `me` geladen
  // ist (vorher wissen wir die Kind-Anzahl nicht). Daher merken wir uns,
  // dass die Initial-URL keinen Hash hatte, und ein $effect macht den
  // Default-Switch sobald die Daten da sind.
  const hadEmptyInitialHash = !window.location.hash.replace(/^#\/?/, '');
  let route = $state(parseHash());

  function parseHash() {
    const h = window.location.hash.replace(/^#\/?/, '');
    if (!h) return { name: 'today' };
    const [name, ...rest] = h.split('?')[0].split('/');
    return { name, args: rest };
  }

  function navigate(name, ...args) {
    const path = args.length ? `${name}/${args.join('/')}` : name;
    window.location.hash = `#/${path}`;
  }

  // Schnellzugriff mit Abschnitt (?s=…): nach dem Seitenwechsel dorthin rollen.
  $effect(() => {
    route;
    return jumpTo(sectionParam());
  });

  onMount(() => {
    loadMe();
    const handler = () => (route = parseHash());
    window.addEventListener('hashchange', handler);
    // Nutzungszeit für den Elternbericht: aktives Kind und aktuelle Ansicht.
    // Mitlesen und Testmodus sind keine Nutzung durch das Kind (D175).
    const stopPing = startUsagePing(() =>
      appState.me && appState.activeAccountId && !['mirror', 'test'].includes(view.mode) ? { accountId: appState.activeAccountId, view: route.name } : null);
    // Kindmodus am Elterngerät endet nach 30 Minuten ohne Nutzung.
    const expire = () => { if (expireViewMode()) navigate(isParent ? 'overview' : 'today'); };
    const touch = () => touchViewMode();
    const expTimer = setInterval(expire, 60000);
    document.addEventListener('visibilitychange', expire);
    document.addEventListener('pointerdown', touch, { passive: true });
    return () => {
      window.removeEventListener('hashchange', handler);
      stopPing();
      clearInterval(expTimer);
      document.removeEventListener('visibilitychange', expire);
      document.removeEventListener('pointerdown', touch);
    };
  });

  // Default-Landing: sobald `me` geladen ist und es ≥2 verlinkte Kinder
  // gibt, schicken wir den Eltern-User auf das Dashboard — vorausgesetzt,
  // er hat die App ohne expliziten Hash geöffnet und ist noch auf der
  // „today"-Voreinstellung. Läuft genau einmal.
  let defaultLandingApplied = $state(false);
  $effect(() => {
    if (defaultLandingApplied) return;
    if (!appState.me) return;
    defaultLandingApplied = true;
    if (
      hadEmptyInitialHash &&
      (appState.me.is_admin || appState.me.role === 'parent') && view.mode === 'parent' &&
      route.name === 'today'
    ) {
      navigate('overview');
    }
  });

  const acc = $derived(activeAccount());
  const isParent = $derived(!!(appState.me?.is_admin || appState.me?.role === 'parent'));
  // Eigene Elternansicht nur im Zustand „Ich“; sonst sieht das Gerät aus wie beim Kind.
  const parentView = $derived(isParent && view.mode === 'parent');
  let deviceSheet = $state(false);
  $effect(() => {
    document.body.dataset.viewMode = isParent ? view.mode : 'own';
    // Ein Kind kann keinen Elternzustand haben; ein alter Wert bleibt wirkungslos.
    if (appState.me && !isParent && view.mode !== 'parent') setViewMode('parent');
  });

  // Übersicht-Tab nur für Eltern mit mind. zwei verlinkten Kindern. Bei
  // einem Kind ist „Heute" der natürliche Einstieg, das Dashboard wäre
  // dann eine reine Solo-Spalte.
  // Welcher Reiter unten markiert ist, auch auf Unterseiten: Vokabeln gehören
  // zu Lernen, Materialien und die Verwaltungsseiten zu den Übersichten.
  const TAB_OF = { vokabeln: 'learning', plan: 'more', tasks: 'more', week: 'more', subjects: 'more', subject: 'more',
                   klausuren: 'more', absences: 'more', materialien: 'more', changes: 'more', courses: 'more', exams: 'more' };
  const activeTab = $derived(TAB_OF[route.name] ?? route.name);
  const navItems = $derived.by(() => {
    const items = [
      { name: 'today', icon: 'heute', label: 'Heute' },
      { name: 'learning', icon: 'lernen', label: 'Lernen' },
      { name: 'more', icon: 'mehr', label: 'Übersichten' },
    ];
    if (parentView) {
      items.unshift({ name: 'overview', icon: 'familie', label: 'Familie' });
    }
    return items;
  });
</script>

{#if appState.needsLogin}
  <Login />
{:else}
<div class="app-shell">
  <header class="top-bar">
    <div class="col" style="gap: 0">
      <h1>Schul-Cockpit</h1>
      {#if parentView && appState.me && appState.me.accounts.length > 1}
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
      {#if appState.me?.is_admin && parentView}
        <button class="ghost" onclick={() => navigate('setup')} title="Setup" aria-label="Setup"><Icon name="werkzeug" /></button>
      {/if}
      {#if acc && (!isParent || parentView)}
        <button class="ghost" onclick={() => navigate('settings')} title="Einstellungen" aria-label="Einstellungen"><Icon name="einstellungen" /></button>
      {/if}
      {#if appState.me?.auth_source === 'pin'}
        <button class="ghost" onclick={logout} title="Abmelden" aria-label="Abmelden"><Icon name="abmelden" /></button>
      {/if}
      {#if isParent}
        <button class="ghost device-btn" onclick={() => (deviceSheet = true)} title="Wer benutzt das Gerät?" aria-label="Wer benutzt das Gerät?"><Icon name="ich" /></button>
      {/if}
    </div>
  </header>
  {#if isParent && view.mode !== 'parent'}
    <div class="mode-band {view.mode}" role="status">
      <span>{view.mode === 'mirror' ? `Du siehst die App von ${acc?.name ?? 'deinem Kind'} · nur lesen` : view.mode === 'child' ? `${acc?.name ?? 'Kind'} am Elterngerät` : 'Testmodus · Änderungen werden beim Beenden zurückgenommen'}</span>
      {#if view.mode === 'mirror'}<button onclick={() => { setViewMode('parent'); navigate('overview'); }}>Zurück zu mir</button>
      {:else}<button onclick={() => (deviceSheet = true)}>{view.mode === 'test' ? 'Beenden' : 'Wechseln'}</button>{/if}
    </div>
  {/if}
  {#if deviceSheet}<DeviceSheet onclose={() => (deviceSheet = false)} {navigate} />{/if}

  <!-- Verwaiste Kind-Verlinkung: der Link zeigt auf eine account_id, die
       es in der Untis-Archiv-DB nicht (mehr) gibt — typischerweise nach
       Schuljahreswechsel, Restore oder Neu-Einrichtung der Integration,
       weil sich dabei die AUTOINCREMENT-IDs verschieben. Vorher fiel das
       Kind dadurch stumm aus der Liste und der Umschalter verschwand. -->
  {#if (appState.me?.stale_account_ids?.length ?? 0) > 0}
    <div
      style="background: var(--exam); color: #fff; padding: 0.5rem 1rem; font-size: 0.85rem; display:flex; justify-content:space-between; align-items:center; gap:0.5rem;"
    >
      <span>
        ⚠️ <strong>{appState.me.stale_account_ids.length} Kind-Verlinkung{appState.me.stale_account_ids.length === 1 ? '' : 'en'} ins Leere</strong>
        · {repairMsg ?? 'dieses Kind fehlt gerade im Umschalter'}
      </span>
      {#if appState.me?.is_admin}
        <button
          class="ghost"
          disabled={repairing}
          style="color:#fff; border-color:rgba(255,255,255,0.4); padding:0.2rem 0.6rem; min-height:32px; font-size:0.8rem; white-space:nowrap;"
          onclick={repairLinks}
        >{repairing ? 'läuft…' : 'Reparieren'}</button>
      {/if}
    </div>
  {/if}

  {#if appState.me?.demo_mode && view.mode !== 'test'}
    <div
      style="background: var(--substitution); color: #fff; padding: 0.5rem 1rem; font-size: 0.85rem; display:flex; justify-content:space-between; align-items:center; gap:0.5rem;"
    >
      <span>🧪 <strong>Teständerungen · Echtdaten</strong> · {appState.me.open_audit_count ?? 0} Änderungen geloggt</span>
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
    {:else if !acc && !['setup', 'overview'].includes(route.name)}
      <div class="empty">
        Dein Account ist noch mit keinem Kind verlinkt.
        {#if appState.me.is_admin}
          <br><br><button class="primary" onclick={() => navigate('setup')}>Setup öffnen</button>
        {:else}
          <br><br>Bitte den Eltern-Account bitten, dich zuzuordnen.
        {/if}
      </div>
    {:else if route.name === 'setup'}
      <Lazy load={LAZY.Setup} {navigate} />
    {:else if route.name === 'settings'}
      <Lazy load={LAZY.Settings} accountId={appState.activeAccountId} />
    {:else if route.name === 'exams'}
      <Lazy load={LAZY.ExamSetup} />
    {:else if route.name === 'courses'}
      <Lazy load={LAZY.Courses} accountId={appState.activeAccountId} />
    {:else if route.name === 'changes'}
      <Lazy load={LAZY.MyChanges} />
    {:else if route.name === 'overview'}
      <Overview {navigate} />
    {:else if route.name === 'more'}
      <h2>Übersichten</h2>
      <div class="overview-links">
        {#each [['materialien','Materialien','📎'],['week','Stundenplan','🗓️'],['subjects','Fächer','📚'],['klausuren','Arbeiten','📝'],['absences','Nachholen','🧩'],['plan','Aufgaben und Wochenplanung','✅']] as [target,label,icon]}
          <button onclick={() => navigate(target)}><span aria-hidden="true">{icon}</span> {label} <ActionLabel /></button>
        {/each}
      </div>
    {:else if route.name === 'today'}
      <Today accountId={appState.activeAccountId} />
    {:else if route.name === 'plan' || route.name === 'tasks'}
      <Lazy load={LAZY.Plan} accountId={appState.activeAccountId} />
    {:else if route.name === 'week'}
      <Week accountId={appState.activeAccountId} />
    {:else if route.name === 'materialien'}
      {#key `${appState.activeAccountId}:${(route.args ?? []).join('/')}`}
        <Lazy load={LAZY.Materialien} accountId={appState.activeAccountId}
                     initialSubject={decodeURIComponent(route.args?.[0] ?? '')}
                     taskId={Number(route.args?.[1]) || null} />
      {/key}
    {:else if route.name === 'learning'}
      {#key appState.activeAccountId}
        <Learning accountId={appState.activeAccountId} />
      {/key}
    {:else if route.name === 'klausuren'}
      <Lazy load={LAZY.Klausuren} accountId={appState.activeAccountId} />
    {:else if route.name === 'vokabeln'}
      {#key `${appState.activeAccountId}:${(route.args ?? []).join('/')}`}
        <Lazy load={LAZY.Vokabeln} accountId={appState.activeAccountId}
                  subject={decodeURIComponent(route.args?.[0] ?? '')}
                  initialUnit={decodeURIComponent((window.location.hash.split('?')[1] ? new URLSearchParams(window.location.hash.split('?')[1]).get('unit') : '') ?? '')} />
      {/key}
    {:else if route.name === 'absences'}
      <Lazy load={LAZY.Absences} accountId={appState.activeAccountId} />
    {:else if route.name === 'subjects'}
      <Subjects accountId={appState.activeAccountId} {navigate} />
    {:else if route.name === 'subject'}
      <SubjectDetail accountId={appState.activeAccountId} subjectId={Number(route.args?.[0])} />
    {:else}
      <div class="empty">Unbekannte Seite.</div>
    {/if}
  </main>

  {#if acc && !['setup','settings'].includes(route.name)}
    <nav class="bottom-nav" aria-label="Hauptnavigation">
      {#each navItems as item}
        <button
          class:active={activeTab === item.name}
          aria-current={activeTab === item.name ? 'page' : undefined}
          onclick={() => navigate(item.name)}
        >
          <span class="icon"><Icon name={item.icon} /></span><span>{item.label}</span>
        </button>
      {/each}
    </nav>
  {/if}
</div>
{/if}

<style>
.overview-links{display:grid;gap:12px}.overview-links button{text-align:left;min-height:68px;border-radius:16px;padding:16px;background:var(--bg-card)}.overview-links button span{font-size:1.4rem;margin-right:12px}.overview-links button:nth-child(3n+1){background:var(--school-soft)}.overview-links button:nth-child(3n+2){background:var(--accent-soft)}.overview-links button:nth-child(3n){background:var(--learn-soft)}
</style>
