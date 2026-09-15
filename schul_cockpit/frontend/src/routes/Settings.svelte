<script>
  import ReminderSettings from '../lib/ReminderSettings.svelte';
  import { api } from '../lib/api.js';
  import { appState, loadMe } from '../lib/store.svelte.js';

  let { accountId } = $props();
  let togglingDemo = $state(false);

  // --- Digitale Schulbücher (Eltern, getrennt pro Kind) ---
  let textbookAccess = $state(null);
  let textbookPassword = $state('');
  let textbookBusy = $state(false);
  let textbookMessage = $state(null);
  let textbookCatalog = $state(null);
  let textbookSubjects = $state([]);
  let calendars = $state(null);
  let calendarBusy = $state(false);
  let calendarMessage = $state(null);
  let textbookTestPages = $state({});
  let textbookTestBusy = $state(null);
  let textbookTest = $state(null);

  async function loadTextbookAccess() {
    if (!accountId || !['parent', 'admin'].includes(appState.me?.role) && !appState.me?.is_admin) return;
    try {
      [textbookAccess, textbookCatalog] = await Promise.all([
        api.get(`/api/accounts/${accountId}/textbooks`),
        api.get(`/api/accounts/${accountId}/textbooks/catalog`),
      ]);
      textbookSubjects = (await api.get(`/api/accounts/${accountId}/subjects`)).subjects ?? [];
      calendars = await api.get(`/api/accounts/${accountId}/calendars`);
      textbookPassword = '';
    } catch (e) {
      textbookMessage = { ok: false, text: e.message };
    }
  }

  $effect(() => { void accountId; void appState.me?.role; loadTextbookAccess(); });

  async function saveTextbookAccess() {
    textbookBusy = true;
    textbookMessage = null;
    try {
      textbookAccess = await api.put(`/api/accounts/${accountId}/textbooks`, {
        portal_url: textbookAccess.portal_url,
        username: textbookAccess.username,
        password: textbookPassword || null,
      });
      textbookPassword = '';
      textbookMessage = { ok: true, text: `Zugang für ${activeName} gespeichert.` };
    } catch (e) {
      textbookMessage = { ok: false, text: e.message };
    } finally {
      textbookBusy = false;
    }
  }

  async function removeTextbookAccess() {
    if (!confirm(`IServ-Zugang für ${activeName} entfernen? Schulbücher und Kalender sind danach nicht mehr erreichbar.`)) return;
    textbookBusy = true;
    try {
      await api.delete(`/api/accounts/${accountId}/textbooks`);
      await loadTextbookAccess();
      textbookMessage = { ok: true, text: 'Zugang entfernt.' };
    } catch (e) {
      textbookMessage = { ok: false, text: e.message };
    } finally {
      textbookBusy = false;
    }
  }

  async function verifyTextbookAccess() {
    textbookBusy = true;
    textbookMessage = null;
    try {
      textbookAccess = await api.post(`/api/accounts/${accountId}/textbooks/verify`);
      textbookMessage = { ok: true, text: `✓ Verbindung für ${activeName} funktioniert.` };
    } catch (e) {
      textbookMessage = { ok: false, text: e.message };
    } finally {
      textbookBusy = false;
    }
  }

  async function scanTextbooks() {
    textbookBusy = true;
    textbookMessage = { ok: true, text: 'Medienregal wird gelesen…' };
    try {
      textbookCatalog = await api.post(`/api/accounts/${accountId}/textbooks/catalog/scan`);
      textbookAccess = await api.get(`/api/accounts/${accountId}/textbooks`);
      textbookMessage = { ok: true, text: `${textbookCatalog.books.length} Schulbücher erkannt.` };
    } catch (e) {
      textbookMessage = { ok: false, text: e.message };
    } finally {
      textbookBusy = false;
    }
  }

  // Ein Eintrag, der kein Buch ist (etwa eine Schaltfläche des
  // Einwilligungsdialogs), verschwindet aus dem Regal; ein echtes Buch kommt
  // beim nächsten Scan wieder.
  async function removeBook(book) {
    if (!confirm(`„${book.title}“ aus dem Regal nehmen?`)) return;
    try {
      await api.delete(`/api/accounts/${accountId}/textbooks/catalog/${book.id}`);
      textbookCatalog = await api.get(`/api/accounts/${accountId}/textbooks/catalog`);
    } catch (e) {
      textbookMessage = { ok: false, text: e.message };
    }
  }

  async function setBookSubject(book, subjectName) {
    try {
      textbookCatalog = await api.patch(
        `/api/accounts/${accountId}/textbooks/catalog/${book.id}`,
        { subject_name: subjectName || null },
      );
    } catch (e) {
      textbookMessage = { ok: false, text: e.message };
    }
  }

  const ROLE_NAMES = {
    exam: 'Klausuren und Arbeiten',
    lessons: 'Unterrichtstermine',
    other: 'Sonstige Schultermine',
    unused: 'nicht verwenden',
  };

  async function syncCalendars() {
    calendarBusy = true;
    calendarMessage = { ok: true, text: 'IServ wird abgefragt …' };
    try {
      calendars = await api.post(`/api/accounts/${accountId}/calendars/sync`, {});
      calendarMessage = {
        ok: true,
        text: `${calendars.sync.calendars} Kalender gefunden, ${calendars.sync.events} Termine gelesen.`,
      };
    } catch (e) {
      calendarMessage = { ok: false, text: e.message };
    } finally {
      calendarBusy = false;
    }
  }

  async function setRole(cal, role) {
    calendarBusy = true;
    try {
      calendars = await api.put(`/api/accounts/${accountId}/calendars/${cal.id}/role`, { role });
      calendarMessage = { ok: true, text: 'Rolle gespeichert. Beim nächsten Abgleich werden die Termine geholt.' };
    } catch (e) {
      calendarMessage = { ok: false, text: e.message };
    } finally {
      calendarBusy = false;
    }
  }

  const TOC_STATE = { ready: 'Inhaltsverzeichnis gelesen', not_found: 'kein Inhaltsverzeichnis auf den ersten Seiten', failed: 'Inhaltsverzeichnis nicht lesbar', no_ai: 'Inhaltsverzeichnis wartet auf die KI' };
  const BOOK_ACCESS = {
    unknown: 'Abruf noch nicht geprüft',
    proven: 'Abruf nachgewiesen, Seitenzahl bestätigt',
    readable: 'Seiten kommen lesbar',
    blank: 'liefert leere Seiten',
    viewer_error: 'Betrachter nicht erreichbar',
  };
  const FETCH_STATUS = {
    loaded: 'Alle genannten Seiten wurden geliefert.',
    partial: 'Nur ein Teil der Seiten wurde geliefert.',
    open_page: 'Das Buch war offen, die genannte Seite war aber nicht anzusteuern.',
    viewer_error: 'Es kam keine Seite an.',
    running: 'Der Abruf läuft …',
  };

  function controlLine(c) {
    const what = [c.tag, c.type, c.role && `role=${c.role}`].filter(Boolean).join(' ');
    const named = [c.label, c.title, c.text, c.placeholder, c.name].filter(Boolean).join(' · ');
    const marks = [c.id && `#${c.id}`, c.cls && `.${c.cls}`, c.value && `= ${c.value}`]
      .filter(Boolean)
      .join(' ');
    return `${c.frame ? `[Rahmen ${c.frame}] ` : ''}${what}${named ? ` — ${named}` : ''}${marks ? ` ${marks}` : ''}${c.visible ? '' : ' (unsichtbar)'}`;
  }

  function fetchSummary(f) {
    if (!f) return null;
    const when = new Date(f.created_at).toLocaleString('de-DE');
    const pages = (f.pages ?? []).join(', ');
    const stage = f.stage ? ` Abbruch in Stufe „${f.stage}".` : '';
    return `${when} · ${f.book_title ?? 'Buch unbekannt'} · S. ${pages}: ${FETCH_STATUS[f.status] ?? f.status}${stage}`;
  }

  async function testBookPage(book) {
    const page = Number(textbookTestPages[book.id]);
    if (!Number.isInteger(page) || page < 1) {
      textbookTest = { book: book.title, status: 'input', detail: 'Bitte eine Seitenzahl eingeben.' };
      return;
    }
    textbookTestBusy = book.id;
    textbookTest = null;
    const path = `/api/accounts/${accountId}/textbooks/catalog/${book.id}/page-test`;
    const startedAt = Date.now();
    try {
      // Der Abruf dauert länger, als der Fernzugriff einer Anfrage erlaubt.
      // Also anstoßen und nachfragen, bis er fertig ist.
      let state = await api.post(path, { page });
      while (state.state === 'running' && Date.now() - startedAt < 6 * 60 * 1000) {
        const seconds = Math.round((Date.now() - startedAt) / 1000);
        textbookTest = { book: book.title, page, status: 'running', detail: `Der Browser arbeitet seit ${seconds} Sekunden.` };
        await new Promise((resolve) => setTimeout(resolve, 4000));
        state = await api.get(path);
      }
      textbookTest = state.state === 'done'
        ? state.result
        : { book: book.title, page, status: 'request_failed', detail: 'Der Abruf läuft noch. Später erneut nachsehen.' };
      textbookCatalog = await api.get(`/api/accounts/${accountId}/textbooks/catalog`);
    } catch (e) {
      textbookTest = { book: book.title, status: 'request_failed', detail: e.message };
    } finally {
      textbookTestBusy = null;
    }
  }

  function selectedBookSubject(book) {
    const value = book.subject_name ?? '';
    return textbookSubjects.find((s) => s.name.toLocaleLowerCase('de-DE') === value.toLocaleLowerCase('de-DE'))?.name
      ?? (value ? value[0].toLocaleUpperCase('de-DE') + value.slice(1) : '');
  }

  function bookSubjectOptions(book) {
    const names = textbookSubjects.map((s) => s.name);
    const detected = selectedBookSubject(book);
    if (detected && !names.some((name) => name.toLocaleLowerCase('de-DE') === detected.toLocaleLowerCase('de-DE'))) {
      names.push(detected);
    }
    return names.sort((a, b) => a.localeCompare(b, 'de-DE'));
  }

  async function toggleDemo() {
    togglingDemo = true;
    try {
      await api.patch('/api/me/demo-mode', { enabled: !appState.me.demo_mode });
      await loadMe();
    } finally {
      togglingDemo = false;
    }
  }

  // --- Datensicherung (Admin) ---
  let backupStatus = $state(null);
  let restoreBusy = $state(false);
  let restoreMsg = $state(null);
  let fileInput;

  async function loadBackupStatus() {
    if (!appState.me?.is_admin) return;
    try {
      backupStatus = await api.get('/api/admin/backup/status');
    } catch (_) { /* ignore */ }
  }

  $effect(() => { void appState.me?.is_admin; loadBackupStatus(); });

  async function doDownload() {
    // Fetch as blob so it works behind ingress, then trigger a save.
    restoreMsg = null;
    try {
      const resp = await fetch('./api/admin/backup/download', { credentials: 'include' });
      if (!resp.ok) throw new Error(`Download fehlgeschlagen (${resp.status})`);
      const blob = await resp.blob();
      const cd = resp.headers.get('content-disposition') || '';
      const m = cd.match(/filename="?([^"]+)"?/);
      const name = m ? m[1] : 'schul-cockpit-backup.zip';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = name; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      restoreMsg = { ok: false, text: e.message };
    }
  }

  async function doRestore(ev) {
    const f = ev.currentTarget.files?.[0];
    if (!f) return;
    if (!confirm('Backup einspielen? Die aktuelle App-Datenbank wird ersetzt (eine Sicherungskopie wird automatisch angelegt). history.db wird NICHT überschrieben.')) {
      ev.currentTarget.value = '';
      return;
    }
    restoreBusy = true;
    restoreMsg = null;
    try {
      const fd = new FormData();
      fd.append('file', f);
      const resp = await fetch('./api/admin/backup/restore', { method: 'POST', body: fd, credentials: 'include' });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.detail || `Fehler ${resp.status}`);
      restoreMsg = { ok: true, text: 'Wiederhergestellt. Bitte das Add-on in Home Assistant neu starten, damit alles sauber geladen wird.' };
      await loadBackupStatus();
    } catch (e) {
      restoreMsg = { ok: false, text: e.message };
    } finally {
      restoreBusy = false;
      ev.currentTarget.value = '';
    }
  }

  function fmtBytes(n) {
    if (!n) return '0 B';
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
    return `${(n / 1024 / 1024).toFixed(1)} MB`;
  }
  function fmtDate(iso) {
    if (!iso) return '—';
    try { return new Date(iso).toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short' }); }
    catch { return iso; }
  }

  // --- Bildschirmzeit / Webclip ---
  const appHost = window.location.host;     // e.g. schule.example.de
  const activeName = $derived(
    appState.me?.accounts?.find((a) => a.id === accountId)?.name ?? 'das Kind',
  );
  let copied = $state(false);
  function copyHost() {
    navigator.clipboard?.writeText(appHost);
    copied = true; setTimeout(() => (copied = false), 1500);
  }
  function downloadWebclip() {
    // iOS installs .mobileconfig profiles ONLY via direct navigation —
    // Settings.app hooks the response MIME type. fetch + blob + <a download>
    // is silently ignored in standalone PWAs (and Safari's tab-mode), which
    // matches the "Webclip lädt nicht herunter"-symptom.
    // Open in a new tab so the PWA's own state stays put; on iOS this still
    // triggers the system profile installer.
    const url = `./api/admin/webclip?account_id=${accountId}`;
    window.open(url, '_blank');
  }

  const DAYS = [
    { key: 'mon', label: 'Mo' },
    { key: 'tue', label: 'Di' },
    { key: 'wed', label: 'Mi' },
    { key: 'thu', label: 'Do' },
    { key: 'fri', label: 'Fr' },
    { key: 'sat', label: 'Sa' },
    { key: 'sun', label: 'So' },
  ];

  let settings = $state(null);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state(null);

  async function load() {
    loading = true;
    try {
      settings = await api.get(`/api/accounts/${accountId}/settings`);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void accountId; load(); });

  async function save() {
    saving = true;
    try {
      await api.patch(`/api/accounts/${accountId}/settings`, {
        default_daily_budget_minutes: Number(settings.default_daily_budget_minutes),
        budget_overrides: Object.fromEntries(
          Object.entries(settings.budget_overrides).filter(([_, v]) => v !== '' && v !== null),
        ),
      });
      await load();
    } catch (e) {
      error = e.message;
    } finally {
      saving = false;
    }
  }

  async function toggleAuto() {
    try {
      await api.patch(`/api/accounts/${accountId}/settings`, {
        auto_budget: !settings.auto_budget,
      });
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function setSectionOverride(value) {
    try {
      await api.patch(`/api/accounts/${accountId}/settings`, {
        school_section_override: value || '',
      });
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  const SECTION_LABEL = {
    primar: 'Primarbereich (Klassen 1–4)',
    sek1: 'Sekundarbereich I (Klassen 5–10)',
    sek2: 'Sekundarbereich II (Klassen 11–13)',
  };
</script>

<div class="row between" style="margin-bottom:0.6rem;">
  <h2 style="margin:0; font-size:1.1rem;">Einstellungen</h2>
  <button class="ghost" onclick={() => history.back()}>← zurück</button>
</div>
{#if accountId}{#key accountId}<ReminderSettings {accountId}/>{/key}{/if}

{#if textbookAccess && (['parent', 'admin'].includes(appState.me?.role) || appState.me?.is_admin)}
  <div class="section-title">🔑 IServ-Zugang · {activeName}</div>
  <div class="card textbook-card">
    <div class="row between textbook-heading">
      <div>
        <strong>Ein Zugang für Schulbücher und Kalender</strong>
        <div class="dim">Damit der Lernmentor Buchseiten einsehen kann und die Schultermine direkt aus IServ kommen.</div>
      </div>
      <span class:textbook-ok={textbookAccess.configured} class="textbook-status">
        {['connected', 'catalog_ready'].includes(textbookAccess.verification_status) ? '✓ verbunden' : textbookAccess.configured ? 'gespeichert' : 'noch offen'}
      </span>
    </div>
    <div class="textbook-grid">
      <label>
        IServ-Adresse
        <input type="url" autocomplete="url" bind:value={textbookAccess.portal_url} />
      </label>
      <label>
        Benutzername
        <input type="text" autocomplete="username" autocapitalize="none" bind:value={textbookAccess.username} />
      </label>
      <label>
        Passwort
        <input
          type="password"
          autocomplete="new-password"
          placeholder={textbookAccess.password_saved ? 'Gespeichert – leer lassen' : 'Passwort'}
          bind:value={textbookPassword}
        />
        {#if textbookAccess.password_saved && !textbookPassword}
          <span class="password-saved">🔒 Passwort sicher gespeichert</span>
        {/if}
      </label>
    </div>
    <div class="row gap-sm textbook-actions">
      <button class="primary" disabled={textbookBusy} onclick={saveTextbookAccess}>
        {textbookBusy ? 'Speichere…' : 'Zugang speichern'}
      </button>
      {#if textbookAccess.configured}
        <button disabled={textbookBusy} onclick={verifyTextbookAccess}>Verbindung prüfen</button>
      {/if}
      {#if textbookAccess.verification_status === 'connected' || textbookAccess.verification_status === 'catalog_ready' || textbookAccess.verification_status === 'scan_failed'}
        <button disabled={textbookBusy} onclick={scanTextbooks}>📚 Bücher erkennen</button>
      {/if}
      {#if textbookAccess.configured}
        <button disabled={textbookBusy} onclick={removeTextbookAccess}>Entfernen</button>
      {/if}
    </div>
    {#if textbookMessage}
      <div class={textbookMessage.ok ? 'banner' : 'error-box'} style="margin-top:0.6rem;">
        {textbookMessage.text}
      </div>
    {/if}
    {#if textbookCatalog?.last_fetch}
      <div class="fetch-note">Letzter Seitenabruf: {fetchSummary(textbookCatalog.last_fetch)}</div>
    {/if}
    {#if textbookCatalog?.books?.length}
      <div class="book-list">
        {#each textbookCatalog.books as book}
          <div class="book-row">
            <div class="book-title"><span>📘</span><strong>{book.title}</strong>
              {#if book.access || book.pages_stored}
                <small class="dim">
                  {#if book.access}{BOOK_ACCESS[book.access.status] ?? book.access.status}{#if book.access.page} (S. {book.access.page}){/if}{/if}
                  {#if book.pages_stored} · {book.pages_stored} {book.pages_stored === 1 ? 'Seite' : 'Seiten'} im Bestand{/if}
                  {#if book.access?.toc_state} · {TOC_STATE[book.access.toc_state] ?? book.access.toc_state}{#if book.chapters} ({book.chapters} Einträge){/if}{/if}
                </small>
              {/if}
            </div>
            <button class="ghost" style="min-height:32px;font-size:0.8rem;" onclick={() => removeBook(book)} aria-label={`${book.title} aus dem Regal nehmen`}>Entfernen</button>
            <select
              aria-label={`Fach für ${book.title}`}
              value={selectedBookSubject(book)}
              onchange={(e) => setBookSubject(book, e.currentTarget.value)}
            >
              <option value="">Fach wählen…</option>
              {#each bookSubjectOptions(book) as subject}
                <option value={subject}>{subject}</option>
              {/each}
            </select>
            <div class="book-test">
              <input
                type="number"
                min="1"
                max="2000"
                placeholder="Seite"
                aria-label={`Testseite für ${book.title}`}
                bind:value={textbookTestPages[book.id]}
              />
              <button disabled={textbookTestBusy !== null} onclick={() => testBookPage(book)}>
                {textbookTestBusy === book.id ? 'Prüfe…' : 'Seitenabruf testen'}
              </button>
            </div>
          </div>
        {/each}
      </div>
    {/if}
    {#if calendars}
      <div class="section-title" style="margin-top:1rem;">🗓️ Schulkalender aus IServ</div>
      <p class="dim">Die Schule erzeugt die Kalender jedes Jahr neu und verteilt Klausuren oft auf mehrere. Deshalb wird bei jedem Abgleich neu gesucht; eine einmal gesetzte Rolle bleibt am Kalendernamen hängen.</p>
      <div class="row gap-sm">
        <button disabled={calendarBusy || !textbookAccess.configured} onclick={syncCalendars}>
          {calendarBusy ? 'Frage IServ …' : 'Kalender abgleichen'}
        </button>
        {#if calendars.sync?.synced_at}
          <span class="dim">zuletzt {new Date(calendars.sync.synced_at).toLocaleString('de-DE')}</span>
        {/if}
      </div>
      {#if !textbookAccess.configured}
        <div class="banner" style="margin-top:0.5rem;">Dafür oben zuerst den IServ-Zugang speichern.</div>
      {/if}
      {#if calendars.sync?.status === 'failed' && calendars.sync?.error}
        <div class="error-box" style="margin-top:0.5rem;">{calendars.sync.error}</div>
      {/if}
      {#if calendarMessage}
        <div class={calendarMessage.ok ? 'banner' : 'error-box'} style="margin-top:0.5rem;">{calendarMessage.text}</div>
      {/if}
      {#if calendars.calendars?.length}
        <div class="book-list">
          {#each calendars.calendars as cal}
            <div class="book-row">
              <div class="book-title">
                <span>🗓️</span>
                <strong>{cal.name}</strong>
                {#if cal.missing_since}<span class="tag">in IServ nicht mehr vorhanden</span>{/if}
                {#if cal.events}<small class="dim">{cal.events} Termine</small>{/if}
              </div>
              <select aria-label={`Rolle für ${cal.name}`} value={cal.role}
                      onchange={(e) => setRole(cal, e.currentTarget.value)}>
                {#each calendars.roles as r}<option value={r}>{ROLE_NAMES[r] ?? r}</option>{/each}
              </select>
            </div>
          {/each}
        </div>
      {:else}
        <p class="empty">Noch keine Kalender gelesen. „Kalender abgleichen" holt sie aus IServ.</p>
      {/if}
    {/if}

    {#if textbookTest}
      <div class="fetch-note">
        <strong>Testabruf {textbookTest.book ?? ''}{textbookTest.page ? ` · Seite ${textbookTest.page}` : ''}</strong>
        <div>{FETCH_STATUS[textbookTest.status] ?? textbookTest.detail ?? textbookTest.status}</div>
        {#if textbookTest.stage}<div>Abbruch in Stufe „{textbookTest.stage}".</div>{/if}
        {#if textbookTest.detail && FETCH_STATUS[textbookTest.status]}<div class="dim">{textbookTest.detail}</div>{/if}
        {#if textbookTest.image}
          <img class="page-preview" src={textbookTest.image} alt="Vorschau der abgerufenen Buchseite" />
        {/if}
        {#if textbookTest.window_image}
          <div class="dim" style="margin-top:0.5rem;">Ganzes Viewer-Fenster mit Bedienleiste:</div>
          <img class="page-preview" src={textbookTest.window_image} alt="Vorschau des ganzen Viewer-Fensters" />
        {/if}
        {#if textbookTest.entry?.length}
          <div class="dim" style="margin-top:0.5rem;">Einstieg in den Leser:</div>
          <ul class="control-list">
            {#each textbookTest.entry as step}
              <li>
                {step.undone
                  ? `zurückgenommen, jetzt auf ${step.to}`
                  : `${step.tag} „${step.caption}" von ${step.from}${step.href ? ` nach ${step.href}` : ''}`}
              </li>
            {/each}
          </ul>
        {/if}
        {#if textbookTest.attempts?.length}
          <div class="dim" style="margin-top:0.5rem;">Blätterversuche:</div>
          <ul class="control-list">
            {#each textbookTest.attempts as step}
              <li>
                S. {step.page} · {step.strategy}: {step.confirmed
                  ? 'bestätigt'
                  : step.found
                    ? 'Bedienelement gefunden, ohne Wirkung'
                    : 'nichts gefunden'}{step.error ? ` (${step.error})` : ''}{step.shown?.length
                  ? ` · Viewer zeigt ${step.shown.join(', ')}`
                  : ''}{step.url ? ` · ${step.url}` : ''}
              </li>
            {/each}
          </ul>
        {/if}
        {#if textbookTest.documents?.length}
          <div class="dim" style="margin-top:0.5rem;">Geöffnete Ansichten:</div>
          <ul class="control-list">
            {#each textbookTest.documents as doc}
              <li>{doc.frame ? `[Rahmen ${doc.frame}] ` : ''}{doc.title || '–'} · {doc.url || '–'}</li>
            {/each}
          </ul>
        {/if}
        {#if textbookTest.controls?.length}
          <details style="margin-top:0.5rem;">
            <summary>Bedienelemente des Viewers ({textbookTest.controls.length})</summary>
            <ul class="control-list">
              {#each textbookTest.controls as control}
                <li>{controlLine(control)}</li>
              {/each}
            </ul>
          </details>
        {/if}
      </div>
    {/if}
  </div>
{/if}


{#if error}<div class="error-box">{error}</div>{/if}

{#if loading || !settings}
  <div class="empty"><span class="spinner"></span></div>
{:else}
  <button class="card" style="width:100%; text-align:left; cursor:pointer;" onclick={() => (window.location.hash = '#/courses')}>
    <div class="row between">
      <div><strong>🎵 Kurse / Wahlfächer</strong><div class="dim">Nicht belegte Kurse ausblenden (z.B. Instrumental, Gesang)</div></div>
      <span>›</span>
    </div>
  </button>

  <div class="section-title">Tagesbudget Lernzeit</div>

  {@const erl = settings.erlass ?? {}}

  <div class="card">
    <div class="row between">
      <div>
        <strong>An Niedersächsischem Hausaufgaben-Erlass orientieren</strong>
        <div class="dim">RdErl. d. MK v. 12.09.2019 — verbindliche Richtwerte</div>
      </div>
      <button class:primary={settings.auto_budget} onclick={toggleAuto}>
        {settings.auto_budget ? '✓ AN' : 'AUS'}
      </button>
    </div>

    {#if settings.auto_budget}
      <div class="banner" style="margin-top:0.6rem;">
        {#if erl.section}
          <div>
            <strong>{SECTION_LABEL[erl.section]}</strong>
            {#if erl.klasse_name}<span class="dim">— aktuell {erl.klasse_name}</span>{/if}
          </div>
          <div style="margin-top:0.3rem;">
            Werktags: <strong>{erl.max_workday_minutes} min</strong>
            · Wochenende: <strong>{erl.weekend_minutes} min</strong>
            · mit Nachmittagsunterricht: <strong>{Math.round(erl.max_workday_minutes * erl.afternoon_reduction_factor / 15) * 15} min</strong>
          </div>
          {#if erl.has_afternoon_today}
            <div style="margin-top:0.3rem; color: var(--accent);">
              Heute Nachmittagsunterricht erkannt → reduziertes Budget.
            </div>
          {/if}
        {:else}
          <div style="color: var(--rating-1);">
            Klasse konnte nicht automatisch erkannt werden{#if erl.klasse_name} (gefundener Name: {erl.klasse_name}){/if}.
            Bitte unten manuell festlegen.
          </div>
        {/if}
      </div>

      <label style="margin-top:0.4rem;">Klassenstufe (falls Auto-Erkennung daneben liegt)</label>
      <select
        value={settings.school_section_override ?? ''}
        onchange={(e) => setSectionOverride(e.currentTarget.value)}
      >
        <option value="">Auto ({erl.section ? SECTION_LABEL[erl.section] : 'unbekannt'})</option>
        <option value="primar">{SECTION_LABEL.primar}</option>
        <option value="sek1">{SECTION_LABEL.sek1}</option>
        <option value="sek2">{SECTION_LABEL.sek2}</option>
      </select>
    {:else}
      <div class="banner" style="margin-top:0.6rem;">
        Eigene Werte aktiv — der Erlass-Standard wird ignoriert. Sinnvoll, wenn ein
        Kind mehr/weniger Konzentration mitbringt als der Durchschnitt.
      </div>

      <label>Standard (alle Wochentage)</label>
      <input type="number" min="0" step="15" bind:value={settings.default_daily_budget_minutes} />

      <div class="section-title">Abweichungen pro Wochentag</div>
      {#each DAYS as d}
        <div class="row gap-sm" style="margin-bottom:0.3rem;">
          <span style="width:34px;">{d.label}</span>
          <input
            type="number"
            min="0"
            step="15"
            placeholder={`= ${settings.default_daily_budget_minutes}`}
            value={settings.budget_overrides[d.key] ?? ''}
            oninput={(e) => {
              const v = e.currentTarget.value;
              if (v === '') delete settings.budget_overrides[d.key];
              else settings.budget_overrides[d.key] = Number(v);
              settings.budget_overrides = { ...settings.budget_overrides };
            }}
          />
        </div>
      {/each}

      <button class="primary" disabled={saving} onclick={save} style="margin-top:0.6rem; width:100%;">
        {saving ? 'Speichere…' : 'Speichern'}
      </button>
    {/if}
  </div>

  {#if appState.me?.is_admin}
  <div class="section-title">Teständerungen an Echtdaten</div>
  <div class="banner">
    Dieser Modus arbeitet mit echten Daten, protokolliert unterstützte Änderungen und pausiert deren HA-Synchronisierung. Er ist keine getrennte Simulation. Für Dummy-Gespräche nutze „Demo ausprobieren“ im Lernmentor.
    Außerdem wird der HA-ToDo-Sync für deine Änderungen pausiert — du kannst also gefahrlos ausprobieren, ohne
    in der HA-ToDo-Liste der Kinder etwas zu verändern.
  </div>
  <div class="card">
    <div class="row between">
      <div>
        <strong>Teständerungen protokollieren</strong>
        <div class="dim">{appState.me?.demo_mode ? 'Aktiv — Änderungen werden geloggt, HA-Sync pausiert.' : 'Aus'}</div>
      </div>
      <button
        class:primary={appState.me?.demo_mode}
        onclick={toggleDemo}
        disabled={togglingDemo}
      >{appState.me?.demo_mode ? '✓ AN' : 'AUS'}</button>
    </div>
    <button
      style="width:100%; margin-top:0.5rem;"
      onclick={() => (window.location.hash = '#/changes')}
    >Meine Änderungen ansehen ({appState.me?.open_audit_count ?? 0})</button>
  </div>

  <div class="section-title">iPhone-Bildschirmzeit</div>
  <div class="banner">
    Auf iPhones mit Bildschirmzeit-Beschränkungen zählt die App als
    Safari-Webseite. So machst du sie nutzbar:
  </div>
  <div class="card">
    <strong>1. Seite freigeben</strong>
    <div class="muted" style="margin:0.2rem 0 0.5rem;">
      Bildschirmzeit → Beschränkungen → Inhaltsbeschränkungen → Webinhalt →
      „Nur erlaubte Websites" → diese Adresse hinzufügen:
    </div>
    <div class="row gap-sm" style="align-items:center;">
      <code class="code-box" style="flex:1;">{appHost}</code>
      <button onclick={copyHost} style="min-height:38px;">{copied ? '✓' : 'Kopieren'}</button>
    </div>

    <strong style="display:block; margin-top:0.8rem;">2. Immer erlauben (optional)</strong>
    <div class="muted" style="margin:0.2rem 0 0.5rem;">
      Damit die Schul-App auch in der Auszeit / trotz Safari-Limit offen ist:
      installiere unten das Webclip-Profil — danach erscheint „Schule …" in
      Bildschirmzeit → App-Limits und kann auf <em>Immer erlaubt</em> gesetzt
      werden, ohne ganz Safari freizugeben.
    </div>
    <button style="width:100%;" onclick={downloadWebclip}>
      ⬇︎ Webclip für {activeName} laden (.mobileconfig)
    </button>
    <div class="dim" style="margin-top:0.4rem;">
      Auf dem iPhone öffnen → installieren (iOS zeigt eine „Nicht verifiziert"-
      Warnung, das ist bei unsignierten Profilen normal und ok). Hinweis: das
      „Immer erlaubt" greift je nach iOS-Version unterschiedlich — Schritt 1
      ist der verlässliche Weg.
    </div>
  </div>

  <div class="section-title">Datensicherung</div>
  <div class="banner">
    Lade ein vollständiges Backup beider Datenbanken herunter (App-Daten +
    UNTIS-Archiv, als ein ZIP). Das Add-on-Datenverzeichnis ist ohnehin in
    jedem Home-Assistant-Backup enthalten — dieser Download macht dich
    zusätzlich unabhängig.
  </div>
  <div class="card">
    {#if backupStatus}
      <div class="muted" style="margin-bottom:0.5rem;">
        Gespeichert:
        <strong>{backupStatus.counts?.tasks ?? 0}</strong> Aufgaben ·
        <strong>{backupStatus.counts?.checkins ?? 0}</strong> Check-ins ·
        <strong>{backupStatus.counts?.manual_exams ?? 0}</strong> man. Klausuren ·
        <strong>{backupStatus.counts?.exam_progress ?? 0}</strong> Noten/Lernstände
        <br>App-DB: {fmtBytes(backupStatus.db_size_bytes)} ·
        letztes HA-Backup: {fmtDate(backupStatus.last_ha_backup)}
      </div>
      {#if backupStatus.last_ha_backup === null}
        <div class="error-box" style="margin-bottom:0.5rem;">
          ⚠️ Es wurde noch kein Home-Assistant-Backup gefunden. Richte in HA
          (Einstellungen → System → Sicherungen) ein automatisches Backup ein —
          das ist deine wichtigste Absicherung.
        </div>
      {/if}
    {/if}

    <button class="primary" style="width:100%;" onclick={doDownload}>⬇︎ Backup herunterladen (ZIP)</button>

    <input type="file" accept=".zip,.db" bind:this={fileInput} onchange={doRestore} style="display:none;" />
    <button style="width:100%; margin-top:0.5rem;" disabled={restoreBusy} onclick={() => fileInput.click()}>
      {restoreBusy ? 'Stelle wieder her…' : '⬆︎ Backup einspielen'}
    </button>
    <div class="dim" style="margin-top:0.4rem;">
      Beim Einspielen wird nur die App-Datenbank ersetzt (mit Sicherungskopie).
      Das UNTIS-Archiv (history.db) stellst du über ein HA-Backup-Restore wieder her.
    </div>

    {#if restoreMsg}
      <div class={restoreMsg.ok ? 'banner' : 'error-box'} style="margin-top:0.5rem;">
        {restoreMsg.text}
      </div>
    {/if}
  </div>
  {/if}
{/if}

<style>
  .textbook-heading { align-items: flex-start; gap: 0.75rem; }
  .textbook-status {
    white-space: nowrap;
    border-radius: 999px;
    padding: 0.2rem 0.55rem;
    background: var(--bg-elevated);
    color: var(--muted);
    font-size: 0.8rem;
    font-weight: 700;
  }
  .textbook-status.textbook-ok { background: var(--success-soft, #e4f5ed); color: var(--success, #18794e); }
  .textbook-grid { display: grid; gap: 0.55rem; margin-top: 0.7rem; }
  .textbook-grid label { margin: 0; }
  .textbook-grid input { width: 100%; margin-top: 0.2rem; }
  .password-saved { display: block; color: var(--success, #18794e); font-size: 0.8rem; margin-top: 0.15rem; }
  .textbook-actions { margin-top: 0.75rem; flex-wrap: wrap; }
  .book-list { margin-top: 0.75rem; border-top: 1px solid var(--border); }
  .book-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(9rem, 13rem) auto; align-items: center; gap: 0.75rem; padding: 0.55rem 0; border-bottom: 1px solid var(--border); }
  .book-title { display: flex; align-items: flex-start; gap: 0.55rem; min-width: 0; }
  .book-title strong { overflow-wrap: anywhere; }
  .book-row select { width: 100%; margin: 0; }
  .book-test { display: flex; gap: 0.4rem; align-items: center; }
  .book-test input { width: 5.5rem; margin: 0; }
  .fetch-note { margin-top: 0.7rem; font-size: 0.88rem; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 6px; padding: 0.5rem 0.65rem; }
  .page-preview { display: block; max-width: 100%; margin-top: 0.5rem; border: 1px solid var(--border); border-radius: 6px; }
  .control-list { margin: 0.3rem 0 0; padding-left: 1.1rem; max-height: 18rem; overflow-y: auto; font-size: 0.82rem; }
  .control-list li { overflow-wrap: anywhere; }
  @media (min-width: 760px) {
    .textbook-grid { grid-template-columns: 1.1fr 1fr 1fr; }
  }
  @media (max-width: 560px) {
    .book-row { grid-template-columns: 1fr; }
  }
  .code-box {
    display: block;
    word-break: break-all;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.4rem 0.6rem;
    font-size: 0.85rem;
  }
</style>
