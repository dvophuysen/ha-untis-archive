<script>
  import Icon from './lib/Icon.svelte';
  import DeviceSheet from './lib/DeviceSheet.svelte';
  import FileViewer from './lib/FileViewer.svelte';
  import { showFile, inAppFile } from './lib/fileViewer.svelte.js';
  import { profile, loadProfile, applyProfile, initials } from './lib/profile.svelte.js';
  import { view, setViewMode, touchViewMode, expireViewMode } from './lib/viewMode.svelte.js';
  import { onMount } from 'svelte';
  import { appState, loadMe, activeAccount, logout } from './lib/store.svelte.js';
  import KidChips from './lib/KidChips.svelte';
  import { todo, loadTodo } from './lib/parentTodo.svelte.js';
  import Today from './routes/Today.svelte';
  import Ich from './routes/Ich.svelte';
  import Subjects from './routes/Subjects.svelte';
  import SubjectDetail from './routes/SubjectDetail.svelte';
  import Login from './routes/Login.svelte';
  import Lazy from './lib/Lazy.svelte';
  // Selten genutzte Seiten kommen erst beim Öffnen (D177). Woche, Lernen und
  // die Familienseite auch: Die Startseite der Kinder (Heute) lädt so schneller;
  // Familie wird beim Start gleich mitgeholt, Woche und Lernen im Leerlauf.
  const LAZY = {
    Overview: () => import('./routes/Overview.svelte'),
    Week: () => import('./routes/Week.svelte'),
    Learning: () => import('./routes/Learning.svelte'),
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
    Erledigen: () => import('./routes/Erledigen.svelte'),
    Scannen: () => import('./routes/Scannen.svelte'),
    Einstellen: () => import('./routes/Einstellen.svelte'),
  };
  import { api } from './lib/api.js';
  import { startUsagePing } from './lib/usagePing.js';
  import { jumpTo, sectionParam } from './lib/jump.js';
  import { prefetch, knownAccount, todayPaths } from './lib/prefetch.js';

  // Eine Adresse mit „%“ im Namen ließ decodeURIComponent werfen: Die Seite blieb leer.
  function decodePart(value) {
    try { return decodeURIComponent(value ?? ''); } catch { return value ?? ''; }
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
  // Eltern landen auf der Familienseite: ihr Modul lädt gleichzeitig mit /api/me.
  // Welche Hülle zuletzt offen war, merkt sich das Gerät; Kinder laden sie so nicht mit.
  const SHELL_KEY = 'lastShell';
  function lastShell() { try { return localStorage.getItem(SHELL_KEY); } catch { return null; } }
  if ((hadEmptyInitialHash && lastShell() !== 'kid') || parseHash().name === 'overview') LAZY.Overview().catch(() => {});

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

  // Zwei Hüllen (D183). Die Elternansicht hat eigene Seiten und dazu die
  // Verwaltungsseiten des Kindes mit Schreibrecht; die Kinderseiten (Heute,
  // Woche, Lernen, Ich …) gibt es dort nicht, die Kinderansicht öffnet der
  // Profilknopf oder ein Tipp auf der Familienkarte zum Mitlesen.
  const PARENT_ONLY = new Set(['overview', 'erledigen', 'scannen', 'einstellen', 'settings', 'setup', 'exams', 'courses', 'changes']);
  const PARENT_ALLOWED = new Set([...PARENT_ONLY, 'materialien', 'klausuren', 'vokabeln', 'learning']);
  // Seiten, die an einem Kind hängen: dort steht in der Elternansicht die Kindwahl.
  const PER_KID = new Set(['settings', 'exams', 'courses', 'materialien', 'klausuren', 'vokabeln', 'learning']);
  function replaceRoute(name) {
    history.replaceState(null, '', `#/${name}`);
    route = parseHash();
  }
  // Neu geöffnet auf einer Elternseite, aber noch im Mitlesen: zurück zu den Eltern.
  if (view.mode === 'mirror' && PARENT_ONLY.has(route.name)) setViewMode('parent');

  // Schnellzugriff mit Abschnitt (?s=…): nach dem Seitenwechsel dorthin rollen.
  $effect(() => {
    route;
    return jumpTo(sectionParam());
  });

  onMount(() => {
    loadMe();
    // Kindergerät auf „Heute“ mit bekanntem Kind: die Daten gleich mit /api/me holen.
    // Passt es danach nicht (anderes Kind, Elternhülle, Anmeldung), verfällt die Antwort still.
    if (route.name === 'today' && lastShell() === 'kid') {
      const known = (() => { try { return knownAccount(); } catch { return null; } })();
      if (known) prefetch(todayPaths(known));
    }
    const handler = () => {
      route = parseHash();
      // Zurück aus dem Mitlesen (auch mit der Zurück-Geste): Landet man wieder
      // auf einer Elternseite, gilt wieder die Elternansicht.
      if (view.mode === 'mirror' && PARENT_ONLY.has(route.name)) setViewMode('parent');
    };
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
    // Dateien und Fotos der App öffnen in der eigenen Ansicht statt in einem
    // neuen Fenster, aus dem die Web-App am iPhone nicht zurückkommt (D206).
    const openInApp = (e) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
      const a = e.target?.closest?.('a[href]');
      const href = inAppFile(a);
      if (!href) return;
      e.preventDefault();
      const title = a.getAttribute('aria-label') || a.querySelector('img')?.getAttribute('alt') || a.textContent.trim();
      showFile(href, title.slice(0, 80));
    };
    document.addEventListener('click', openInApp);
    return () => {
      document.removeEventListener('click', openInApp);
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

  // Jede Hülle zeigt nur ihre Seiten. Eine Kinderseite in der Elternansicht
  // führt zur Familie; eine Elternseite beim Kind (auch Mitlesen und
  // Kindmodus) zu „Heute“. Der Testmodus des Entwicklers darf beides.
  $effect(() => {
    if (!appState.me || appState.loading) return;
    // Zwischen Moduswechsel und hashchange steht hier noch die alte Seite.
    if (parseHash().name !== route.name) return;
    if (parentView) {
      if (!PARENT_ALLOWED.has(route.name)) replaceRoute('overview');
    } else if (view.mode !== 'test' && PARENT_ONLY.has(route.name)) {
      replaceRoute('today');
    }
  });

  // Zähler für „Erledigen“: beim Öffnen der Elternansicht und bei jedem Wechsel
  // auf Familie oder Erledigen, höchstens einmal je Minute.
  $effect(() => {
    if (parentView && appState.me && ['overview', 'erledigen', 'scannen'].includes(route.name)) loadTodo();
  });
  const todoTotal = $derived(todo.data?.total ?? 0);

  // Woche und Lernen (für Eltern auch Familie) vorladen, wenn die Startseite
  // steht, damit der erste Tipp darauf ohne Warten öffnet. Einmal je Start;
  // Fehler zeigt erst das Öffnen der Seite (Lazy.svelte).
  let warmed = false;
  $effect(() => {
    if (warmed || appState.loading || !appState.me) return;
    warmed = true;
    const warm = () => {
      LAZY.Week().catch(() => {});
      LAZY.Learning().catch(() => {});
      if (isParent) LAZY.Overview().catch(() => {});
    };
    setTimeout(() => (window.requestIdleCallback ? window.requestIdleCallback(warm, { timeout: 3000 }) : warm()), 2000);
  });
  $effect(() => {
    if (!appState.me) return;
    try { localStorage.setItem(SHELL_KEY, parentView ? 'parent' : 'kid'); } catch { /* nur ein Hinweis fürs Vorladen */ }
  });

  const acc = $derived(activeAccount());
  const isParent = $derived(!!(appState.me?.is_admin || appState.me?.role === 'parent'));
  // Eigene Elternansicht nur im Zustand „Ich“; sonst sieht das Gerät aus wie beim Kind.
  const parentView = $derived(isParent && view.mode === 'parent');
  let deviceSheet = $state(false);
  // Gestaltung des Kindes (D176) laden und anwenden, außer in der eigenen
  // Elternansicht: Dort gilt sie nicht, also auch nicht laden.
  $effect(() => { if (!parentView && appState.activeAccountId && profile.accountId !== appState.activeAccountId) loadProfile(appState.activeAccountId); });
  $effect(() => { applyProfile(!parentView && profile.accountId === appState.activeAccountId ? profile.prefs : null); });
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
  const TAB_OF = { vokabeln: 'learning', plan: 'ich', tasks: 'ich', subjects: 'ich', subject: 'ich', more: 'ich',
                   klausuren: 'ich', absences: 'ich', materialien: 'ich', changes: 'ich', courses: 'ich', exams: 'ich' };
  // In der Elternansicht gehören die Verwaltungsseiten zu „Einstellen“, was
  // aus „Erledigen“ geöffnet wird, zu „Erledigen“.
  const PARENT_TAB_OF = { settings: 'einstellen', setup: 'einstellen', courses: 'einstellen', changes: 'einstellen', exams: 'einstellen',
                          learning: 'einstellen', vokabeln: 'einstellen', klausuren: 'erledigen', materialien: 'erledigen' };
  const activeTab = $derived(parentView ? (PARENT_TAB_OF[route.name] ?? route.name) : (TAB_OF[route.name] ?? route.name));
  const navItems = $derived.by(() => {
    // Elternansicht (D183): Familie, Erledigen, Scannen, Einstellen.
    if (parentView) {
      return [
        { name: 'overview', icon: 'familie', label: 'Familie' },
        { name: 'erledigen', icon: 'erledigen', label: 'Erledigen', badge: todoTotal },
        { name: 'scannen', icon: 'scannen', label: 'Scannen' },
        { name: 'einstellen', icon: 'einstellungen', label: 'Einstellen' },
      ];
    }
    // Kinder (D176): Heute, Woche, Lernen, Ich.
    return [
      { name: 'today', icon: 'heute', label: 'Heute' },
      { name: 'week', icon: 'woche', label: 'Woche' },
      { name: 'learning', icon: 'lernen', label: 'Lernen' },
      { name: 'ich', icon: 'ich', label: 'Ich' },
    ];
  });
</script>

{#if appState.needsLogin}
  <Login />
{:else}
<div class="app-shell">
  <header class="top-bar">
    <div class="col" style="gap: 0">
      <div class="brand">
        {#if acc && !parentView}<span class="avatar" aria-hidden="true">{profile.prefs.avatar || initials(acc.name)}</span>{/if}
        <h1>Schul-Cockpit</h1>
      </div>
      <!-- Elternansicht: kein Kinderwähler mehr oben (D183); gewählt wird an der Seite selbst. -->
      {#if parentView}
        <span class="top-meta">Familie</span>
      {:else if acc}
        <span class="top-meta">{acc.name}</span>
      {/if}
    </div>
    <div class="row gap-sm">
      <!-- Setup und Einstellungen stecken in „Einstellen“; Kinder haben kein Zahnrad (D183). -->
      {#if appState.me?.auth_source === 'pin' && !parentView}
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
      {#if view.mode === 'mirror'}<button onclick={() => { setViewMode('parent'); navigate('overview'); }}>Zurück zur Familie</button>
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
      <span>🧪 <strong>Testmodus-Protokoll · Echtdaten</strong> · {appState.me.open_audit_count ?? 0} Änderungen geloggt</span>
      <button
        class="ghost"
        style="color:#fff; border-color:rgba(255,255,255,0.4); padding:0.2rem 0.6rem; min-height:32px; font-size:0.8rem;"
        onclick={() => navigate('changes')}
      >Verwalten</button>
    </div>
  {/if}

  <main class="content">
    {#if parentView && PER_KID.has(route.name) && !appState.loading}<div class="kid-for"><KidChips label="Für welches Kind" /></div>{/if}
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
    {:else if !acc && !['setup', 'overview', 'einstellen', 'erledigen', 'changes'].includes(route.name)}
      <div class="empty">
        Dein Account ist noch mit keinem Kind verlinkt.
        {#if appState.me.is_admin}
          <br><br><button class="primary" onclick={() => navigate('setup')}>Setup öffnen</button>
        {:else}
          <br><br>Bitte den Eltern-Account bitten, dich zuzuordnen.
        {/if}
      </div>
    {:else if parentView ? !PARENT_ALLOWED.has(route.name) : (view.mode !== 'test' && PARENT_ONLY.has(route.name))}
      <!-- Seite der anderen Hülle: gleich geht es weiter (Effekt oben). Bis dahin
           nichts laden, sonst holte die Familie beim Start erst „Heute“ von Kind A. -->
      <div class="empty"><span class="spinner"></span></div>
    {:else if route.name === 'setup'}
      <Lazy load={LAZY.Setup} {navigate} />
    {:else if route.name === 'settings'}
      <!-- Je Kind neu aufbauen: Eine späte Antwort für das vorige Kind darf nie im Formular des neuen landen. -->
      {#key appState.activeAccountId}<Lazy load={LAZY.Settings} accountId={appState.activeAccountId} />{/key}
    {:else if route.name === 'exams'}
      {#key appState.activeAccountId}<Lazy load={LAZY.ExamSetup} />{/key}
    {:else if route.name === 'courses'}
      {#key appState.activeAccountId}<Lazy load={LAZY.Courses} accountId={appState.activeAccountId} />{/key}
    {:else if route.name === 'changes'}
      <Lazy load={LAZY.MyChanges} />
    {:else if route.name === 'overview'}
      <Lazy load={LAZY.Overview} {navigate} />
    {:else if route.name === 'erledigen'}
      <Lazy load={LAZY.Erledigen} />
    {:else if route.name === 'scannen'}
      {#key route.name + window.location.hash}<Lazy load={LAZY.Scannen} />{/key}
    {:else if route.name === 'einstellen'}
      <Lazy load={LAZY.Einstellen} accountId={appState.activeAccountId} />
    {:else if route.name === 'ich' || route.name === 'more'}
      <Ich accountId={appState.activeAccountId} name={acc?.name} canStyle={view.mode !== 'mirror'} />
    {:else if route.name === 'today'}
      <Today accountId={appState.activeAccountId} />
    {:else if route.name === 'plan' || route.name === 'tasks'}
      {#key appState.activeAccountId}<Lazy load={LAZY.Plan} accountId={appState.activeAccountId} />{/key}
    {:else if route.name === 'week'}
      <Lazy load={LAZY.Week} accountId={appState.activeAccountId} />
    {:else if route.name === 'materialien'}
      {#key `${appState.activeAccountId}:${(route.args ?? []).join('/')}`}
        <Lazy load={LAZY.Materialien} accountId={appState.activeAccountId}
                     initialSubject={decodePart(route.args?.[0])}
                     taskId={Number(route.args?.[1]) || null} />
      {/key}
    {:else if route.name === 'learning'}
      {#key appState.activeAccountId}
        <Lazy load={LAZY.Learning} accountId={appState.activeAccountId} />
      {/key}
    {:else if route.name === 'klausuren'}
      {#key appState.activeAccountId}<Lazy load={LAZY.Klausuren} accountId={appState.activeAccountId} />{/key}
    {:else if route.name === 'vokabeln'}
      {#key `${appState.activeAccountId}:${(route.args ?? []).join('/')}`}
        <Lazy load={LAZY.Vokabeln} accountId={appState.activeAccountId}
                  subject={decodePart(route.args?.[0])}
                  initialUnit={new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('unit') ?? ''} />
      {/key}
    {:else if route.name === 'absences'}
      {#key appState.activeAccountId}<Lazy load={LAZY.Absences} accountId={appState.activeAccountId} />{/key}
    {:else if route.name === 'subjects'}
      <Subjects accountId={appState.activeAccountId} {navigate} />
    {:else if route.name === 'subject'}
      <SubjectDetail accountId={appState.activeAccountId} subjectId={Number(route.args?.[0])} />
    {:else}
      <div class="empty">Unbekannte Seite.</div>
    {/if}
  </main>

  {#if parentView ? !!appState.me : (acc && !['setup','settings'].includes(route.name))}
    <nav class="bottom-nav" aria-label={parentView ? 'Elternansicht' : 'Hauptnavigation'}>
      {#each navItems as item}
        <button
          class:active={activeTab === item.name}
          aria-current={activeTab === item.name ? 'page' : undefined}
          aria-label={item.badge ? `${item.label}, ${item.badge} offen` : undefined}
          onclick={() => navigate(item.name)}
        >
          <span class="icon"><Icon name={item.icon} />{#if item.badge}<b class="nav-badge" aria-hidden="true">{item.badge > 99 ? '99+' : item.badge}</b>{/if}</span><span>{item.label}</span>
        </button>
      {/each}
    </nav>
  {/if}
</div>
{/if}
<FileViewer />

