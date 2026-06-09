<script>
  import { api } from '../lib/api.js';
  import { appState, activeAccount } from '../lib/store.svelte.js';
  import { formatShortDate } from '../lib/format.js';

  let loading = $state(true);
  let error = $state(null);
  let diag = $state(null);          // { entity_id, exclude_keywords, all_entries, subjects, calendar_error }
  let entities = $state([]);
  let entitiesAvailable = $state(true);

  let selectedEntity = $state('');
  let excludeText = $state('');
  let savingCal = $state(false);

  // manual exam form
  let mDate = $state('');
  let mSubject = $state('');
  let mTitle = $state('');
  let mNote = $state('');
  let addingManual = $state(false);

  const acc = $derived(activeAccount());

  async function load() {
    if (!appState.activeAccountId) return;
    loading = true;
    error = null;
    try {
      const [d, e] = await Promise.all([
        api.get(`/api/accounts/${appState.activeAccountId}/exams/diagnostic`),
        api.get(`/api/accounts/${appState.activeAccountId}/calendar-entities`).catch(() => ({ available: false, entities: [] })),
      ]);
      diag = d;
      selectedEntity = d.entity_id ?? '';
      excludeText = (d.exclude_keywords ?? []).join(', ');
      entities = e.entities ?? [];
      entitiesAvailable = e.available !== false;
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void appState.activeAccountId; load(); });

  async function saveCalendar() {
    if (!selectedEntity) { error = 'Bitte einen Kalender wählen.'; return; }
    savingCal = true;
    try {
      await api.put(`/api/accounts/${appState.activeAccountId}/exam-calendar`, {
        ha_entity_id: selectedEntity,
        exclude_keywords: excludeText.split(',').map((s) => s.trim()).filter(Boolean),
      });
      await load();
    } catch (e) {
      error = e.message;
    } finally {
      savingCal = false;
    }
  }

  async function override(entry, decision, subjectName, subjectId) {
    try {
      await api.post(`/api/accounts/${appState.activeAccountId}/exam-overrides`, {
        source_key: entry.source_key,
        decision,
        subject_name: subjectName ?? null,
        subject_untis_id: subjectId ?? null,
      });
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  function assignFromSelect(entry, value) {
    if (!value) return;
    const s = diag.subjects.find((x) => String(x.subject_untis_id) === String(value));
    if (s) override(entry, 'assigned', s.subject_name, s.subject_untis_id);
  }

  async function addManual() {
    if (!mDate || !mSubject) { error = 'Datum und Fach sind nötig.'; return; }
    addingManual = true;
    try {
      const s = diag.subjects.find((x) => x.subject_name === mSubject);
      await api.post(`/api/accounts/${appState.activeAccountId}/manual-exams`, {
        exam_date: mDate,
        subject_name: mSubject,
        subject_untis_id: s?.subject_untis_id ?? null,
        title: mTitle || null,
        note: mNote || null,
      });
      mDate = ''; mTitle = ''; mNote = ''; mSubject = '';
      await load();
    } catch (e) {
      error = e.message;
    } finally {
      addingManual = false;
    }
  }

  async function delManual(id) {
    if (!confirm('Termin löschen?')) return;
    await api.delete(`/api/accounts/${appState.activeAccountId}/manual-exams/${id}`);
    await load();
  }

  const STATUS_LABEL = {
    auto: '✅ erkannt',
    assigned: '✋ zugeordnet',
    ambiguous: '⚠️ mehrdeutig',
    unmatched: '❓ kein Fach erkannt',
    excluded: '🚫 ausgeschlossen',
    dismissed: '🚫 nicht zutreffend',
    manual: '✍️ manuell',
  };

  const calendarEntries = $derived(diag ? diag.all_entries.filter((e) => e.source === 'calendar') : []);
  const manualEntries = $derived(diag ? diag.all_entries.filter((e) => e.source === 'manual') : []);
  const needsAttention = $derived(calendarEntries.filter((e) => e.status === 'unmatched' || e.status === 'ambiguous'));
</script>

<div class="row between" style="margin-bottom:0.6rem;">
  <h2 style="margin:0; font-size:1.1rem;">Klausuren {#if acc}· {acc.name}{/if}</h2>
  <button class="ghost" onclick={() => history.back()}>← zurück</button>
</div>

{#if error}<div class="error-box">{error}</div>{/if}

{#if loading || !diag}
  <div class="empty"><span class="spinner"></span></div>
{:else}
  <!-- 1. Kalender verknüpfen -->
  <div class="section-title">Klausuren-Kalender verknüpfen</div>
  <div class="banner">
    WebUntis gibt für Schüler-Logins keine Klausuren her. Verknüpfe darum den Kalender,
    den du z.B. als iServ-Abo in Home Assistant eingebunden hast.
  </div>
  <div class="card">
    {#if entitiesAvailable && entities.length > 0}
      <label>Kalender</label>
      <select bind:value={selectedEntity}>
        <option value="">– wählen –</option>
        {#each entities as e}
          <option value={e.entity_id}>{e.friendly_name || e.entity_id}</option>
        {/each}
      </select>
    {:else}
      <label>Kalender-Entity (z.B. calendar.klausuren_noah)</label>
      <input bind:value={selectedEntity} placeholder="calendar.klausuren_noah" />
    {/if}

    <label style="margin-top:0.6rem;">Ausschluss-Wörter (Komma-getrennt)</label>
    <input bind:value={excludeText} placeholder="turnier, ausflug, religion" />
    <div class="dim" style="margin-top:0.2rem;">
      Termine, die eines dieser Wörter enthalten, gelten nie als Klausur.
    </div>

    <button class="primary" style="width:100%; margin-top:0.6rem;" disabled={savingCal} onclick={saveCalendar}>
      {savingCal ? 'Speichere…' : 'Speichern & neu prüfen'}
    </button>
    {#if diag.calendar_error}
      <div class="error-box" style="margin-top:0.5rem;">Kalender-Fehler: {diag.calendar_error}</div>
    {/if}
  </div>

  <!-- 2. Braucht Aufmerksamkeit -->
  {#if needsAttention.length > 0}
    <div class="section-title">Bitte zuordnen ({needsAttention.length})</div>
    {#each needsAttention as e (e.source_key)}
      <div class="card compact">
        <div class="row between">
          <div><strong>{e.title}</strong><div class="dim">{formatShortDate(e.date)} · {STATUS_LABEL[e.status]}</div></div>
        </div>
        <div class="row gap-sm" style="margin-top:0.4rem; flex-wrap:wrap;">
          <select onchange={(ev) => assignFromSelect(e, ev.currentTarget.value)}>
            <option value="">Fach zuordnen…</option>
            {#each diag.subjects as s}
              <option value={s.subject_untis_id}>{s.short ? s.short + ' · ' : ''}{s.subject_name}</option>
            {/each}
          </select>
          <button class="ghost" onclick={() => override(e, 'dismissed')}>nicht zutreffend</button>
        </div>
      </div>
    {/each}
  {/if}

  <!-- 3. Alle Kalender-Einträge -->
  <div class="section-title">Erkannte Kalender-Termine</div>
  {#if calendarEntries.length === 0}
    <div class="empty">Keine Termine im Kalender (oder noch keiner verknüpft).</div>
  {:else}
    {#each calendarEntries as e (e.source_key)}
      <div class="card compact">
        <div class="row between" style="align-items:flex-start;">
          <div style="flex:1; min-width:0;">
            <strong>{e.title}</strong>
            <div class="dim">
              {formatShortDate(e.date)} · {STATUS_LABEL[e.status]}
              {#if e.subject_name}→ <strong>{e.subject_name}</strong>{/if}
            </div>
          </div>
          <div class="row gap-sm" style="flex-wrap:wrap; justify-content:flex-end;">
            {#if e.status === 'auto' || e.status === 'assigned'}
              <button class="ghost" onclick={() => override(e, 'dismissed')} title="nicht zutreffend">🚫</button>
            {/if}
            {#if e.status === 'excluded' || e.status === 'dismissed'}
              <button class="ghost" onclick={() => override(e, 'reset')} title="doch berücksichtigen">↩︎</button>
            {/if}
          </div>
        </div>
        {#if e.status === 'auto' || e.status === 'assigned'}
          <select style="margin-top:0.4rem;" onchange={(ev) => assignFromSelect(e, ev.currentTarget.value)}>
            <option value="">Fach ändern…</option>
            {#each diag.subjects as s}
              <option value={s.subject_untis_id}>{s.short ? s.short + ' · ' : ''}{s.subject_name}</option>
            {/each}
          </select>
        {/if}
      </div>
    {/each}
  {/if}

  <!-- 4. Manuelle Termine -->
  <div class="section-title">Manuelle Termine (z.B. mündlich abgesprochen)</div>
  {#each manualEntries as e (e.manual_id)}
    <div class="card compact">
      <div class="row between">
        <div><strong>{e.title}</strong><div class="dim">{formatShortDate(e.date)} · {e.subject_name}{#if e.note} · {e.note}{/if}</div></div>
        <button class="ghost danger" onclick={() => delManual(e.manual_id)}>✕</button>
      </div>
    </div>
  {/each}

  <div class="card">
    <label>Datum</label>
    <input type="date" bind:value={mDate} />
    <label style="margin-top:0.4rem;">Fach</label>
    <select bind:value={mSubject}>
      <option value="">– wählen –</option>
      {#each diag.subjects as s}
        <option value={s.subject_name}>{s.short ? s.short + ' · ' : ''}{s.subject_name}</option>
      {/each}
    </select>
    <label style="margin-top:0.4rem;">Titel (optional)</label>
    <input bind:value={mTitle} placeholder="z.B. Nachschreibtermin Mathe" />
    <label style="margin-top:0.4rem;">Notiz (optional)</label>
    <input bind:value={mNote} placeholder="z.B. mündlich vereinbart" />
    <button class="primary" style="width:100%; margin-top:0.6rem;" disabled={addingManual} onclick={addManual}>
      {addingManual ? 'Füge hinzu…' : 'Termin hinzufügen'}
    </button>
  </div>
{/if}
