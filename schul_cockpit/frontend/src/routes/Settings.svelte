<script>
  import { api } from '../lib/api.js';
  import { appState, loadMe } from '../lib/store.svelte.js';

  let { accountId } = $props();
  let togglingDemo = $state(false);

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
  const appHost = window.location.host;     // e.g. schule.ophuysen.de
  const activeName = $derived(
    appState.me?.accounts?.find((a) => a.id === accountId)?.name ?? 'das Kind',
  );
  let copied = $state(false);
  function copyHost() {
    navigator.clipboard?.writeText(appHost);
    copied = true; setTimeout(() => (copied = false), 1500);
  }
  async function downloadWebclip() {
    try {
      const resp = await fetch(`./api/admin/webclip?account_id=${accountId}`, { credentials: 'include' });
      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        throw new Error(d.detail || `Fehler ${resp.status}`);
      }
      const blob = await resp.blob();
      const cd = resp.headers.get('content-disposition') || '';
      const m = cd.match(/filename="?([^"]+)"?/);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = m ? m[1] : 'schul-cockpit.mobileconfig'; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      error = e.message;
    }
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
  <div class="section-title">Demo-Modus</div>
  <div class="banner">
    Im Demo-Modus werden alle deine Änderungen geloggt und können einzeln oder gesammelt zurückgenommen werden.
    Außerdem wird der HA-ToDo-Sync für deine Änderungen pausiert — du kannst also gefahrlos ausprobieren, ohne
    in der HA-ToDo-Liste der Kinder etwas zu verändern.
  </div>
  <div class="card">
    <div class="row between">
      <div>
        <strong>Demo-Modus</strong>
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
