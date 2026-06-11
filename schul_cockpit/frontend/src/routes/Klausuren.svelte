<script>
  import { api } from '../lib/api.js';
  import { formatShortDate, daysBetween, isoToday } from '../lib/format.js';
  import { appState } from '../lib/store.svelte.js';

  let { accountId } = $props();
  const today = isoToday();

  let data = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let busyKey = $state(null);
  // Manueller Termin in Bearbeitung — { manual_id, exam_date, title }
  let editing = $state(null);

  const canManage = $derived(
    !!(appState.me && (appState.me.is_admin || appState.me.role === 'parent'))
  );

  async function load() {
    if (!accountId) return;
    loading = true;
    error = null;
    try {
      data = await api.get(`/api/accounts/${accountId}/exams/all`);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void accountId; load(); });

  async function saveProgress(exam, patch) {
    busyKey = exam.exam_key;
    try {
      await api.post(`/api/accounts/${accountId}/exam-progress`, {
        exam_key: exam.exam_key,
        ...patch,
      });
      if (patch.clear_grade) exam.grade_points = null;
      else if ('grade_points' in patch) exam.grade_points = patch.grade_points;
      if ('learn_state' in patch) exam.learn_state = patch.learn_state;
      data = { ...data };
    } catch (e) {
      error = e.message;
    } finally {
      busyKey = null;
    }
  }

  function startEdit(e) {
    editing = {
      manual_id: e.manual_id,
      exam_date: e.date,
      title: e.title ?? '',
    };
  }

  async function saveEdit() {
    if (!editing?.manual_id) return;
    if (!editing.exam_date) { error = 'Datum fehlt.'; return; }
    busyKey = `manual:${editing.manual_id}`;
    try {
      await api.patch(
        `/api/accounts/${accountId}/manual-exams/${editing.manual_id}`,
        { exam_date: editing.exam_date, title: editing.title || null },
      );
      editing = null;
      await load();
    } catch (e) {
      error = e.message;
    } finally {
      busyKey = null;
    }
  }

  async function deleteManual(e) {
    if (!confirm(`Termin "${e.subject_name ?? e.title}" am ${formatShortDate(e.date)} löschen?`)) return;
    busyKey = e.exam_key;
    try {
      await api.delete(`/api/accounts/${accountId}/manual-exams/${e.manual_id}`);
      await load();
    } catch (err) {
      error = err.message;
    } finally {
      busyKey = null;
    }
  }

  const LEARN = [
    { v: 0, label: 'nicht begonnen', emoji: '⚪' },
    { v: 1, label: 'viel offen', emoji: '😟' },
    { v: 2, label: 'mittel', emoji: '😐' },
    { v: 3, label: 'sicher', emoji: '😀' },
  ];

  function whenLabel(dateIso) {
    const d = daysBetween(today, dateIso);
    if (d === 0) return 'heute';
    if (d === 1) return 'morgen';
    if (d === 2) return 'übermorgen';
    if (d <= 7) return `in ${d} Tagen`;
    return formatShortDate(dateIso);
  }
  function urgencyClass(dateIso) {
    const d = daysBetween(today, dateIso);
    if (d <= 2) return 'soon';
    if (d <= 7) return 'mid';
    return '';
  }
</script>

<div class="row between" style="margin: 0 0 0.6rem; align-items:center;">
  <h2 style="margin:0; font-size:1.15rem;">Klausuren</h2>
  {#if canManage}
    <button
      class="ghost"
      style="font-size:0.85rem; min-height:32px;"
      onclick={() => (window.location.hash = '#/exams')}
      title="Kalender verknüpfen, Termine ergänzen"
    >✏️ verwalten</button>
  {/if}
</div>

{#if error}<div class="error-box">{error}</div>{/if}

{#if loading || !data}
  <div class="empty"><span class="spinner"></span></div>
{:else}
  {#if data.calendar_error}
    <div class="error-box">Kalender-Fehler: {data.calendar_error}</div>
  {/if}

  <!-- AUSSTEHEND -->
  <div class="section-title">Ausstehend</div>
  {#if data.upcoming.length === 0}
    <div class="empty" style="padding:1rem;">
      Keine anstehenden Klausuren erkannt.<br>
      <span class="dim">Kalender verknüpfen oder Termin ergänzen: Setup → Klausuren verwalten.</span>
    </div>
  {:else}
    {#each data.upcoming as e (e.exam_key)}
      <div class="card">
        <div class="row between" style="align-items:flex-start;">
          <div style="min-width:0;">
            <strong>{e.subject_name ?? e.title}</strong>
            {#if e.subject_name && e.title && e.title !== e.subject_name}
              <div class="dim">{e.title}</div>
            {/if}
            <div class="dim">{formatShortDate(e.date)}{#if e.source === 'manual'} · manuell{/if}</div>
          </div>
          <span class="badge when {urgencyClass(e.date)}">{whenLabel(e.date)}</span>
        </div>

        {#if editing?.manual_id === e.manual_id}
          <div class="edit-form">
            <label>Datum</label>
            <input type="date" bind:value={editing.exam_date} />
            <label style="margin-top:0.4rem;">Titel (optional)</label>
            <input bind:value={editing.title} placeholder="z.B. Nachschreibtermin" />
            <div class="row gap-sm" style="margin-top:0.5rem;">
              <button class="primary" onclick={saveEdit} disabled={busyKey === `manual:${e.manual_id}`}>Speichern</button>
              <button class="ghost" onclick={() => (editing = null)}>Abbrechen</button>
            </div>
          </div>
        {:else}
          <div class="muted" style="margin-top:0.5rem;">Lernstand:</div>
          <div class="learn-row">
            {#each LEARN as l}
              <button
                class="learn"
                class:active={e.learn_state === l.v}
                disabled={busyKey === e.exam_key}
                onclick={() => saveProgress(e, { learn_state: l.v })}
                title={l.label}
              >{l.emoji}<span class="ll">{l.label}</span></button>
            {/each}
          </div>

          {#if canManage && e.source === 'manual'}
            <div class="row gap-sm" style="margin-top:0.5rem; justify-content:flex-end;">
              <button class="ghost" onclick={() => startEdit(e)} title="Termin verschieben / bearbeiten">✏️ bearbeiten</button>
              <button class="ghost danger" onclick={() => deleteManual(e)} title="Termin löschen">✕</button>
            </div>
          {:else if canManage && e.source === 'calendar'}
            <div class="dim" style="margin-top:0.5rem; font-size:0.78rem;">
              kommt aus dem Kalender — Datum in der Quelle anpassen oder unter <a href="#/exams">Verwalten</a> dismissen und Ersatztermin anlegen.
            </div>
          {/if}
        {/if}
      </div>
    {/each}
  {/if}

  <!-- HISTORIE -->
  <div class="section-title">Vergangen</div>
  {#if data.past.length === 0}
    <div class="empty" style="padding:1rem;">Noch keine vergangenen Klausuren.</div>
  {:else}
    {#each data.past as e (e.exam_key)}
      <div class="card compact">
        <div class="row between" style="align-items:flex-start;">
          <div style="min-width:0;">
            <strong>{e.subject_name ?? e.title}</strong>
            {#if e.subject_name && e.title && e.title !== e.subject_name}
              <span class="dim"> · {e.title}</span>
            {/if}
            <div class="dim">{formatShortDate(e.date)}</div>
          </div>
          <div class="grade-box">
            <select
              class="grade-input"
              value={e.grade_points ?? ''}
              onchange={(ev) => {
                const v = ev.currentTarget.value;
                if (v === '') saveProgress(e, { clear_grade: true });
                else saveProgress(e, { grade_points: Number(v) });
              }}
            >
              <option value="">– Note –</option>
              {#each (data.grade_options ?? []) as o}
                <option value={o.points}>{o.label}</option>
              {/each}
            </select>
          </div>
        </div>
      </div>
    {/each}
  {/if}
{/if}

<style>
  .learn-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.3rem; margin-top: 0.3rem; }
  .learn {
    display: flex; flex-direction: column; align-items: center; gap: 2px;
    font-size: 1.1rem; padding: 0.4rem 0.2rem; min-height: 52px;
    background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 8px;
  }
  .learn .ll { font-size: 0.6rem; color: var(--fg-muted); }
  .learn.active { background: var(--accent); border-color: var(--accent); color: #fff; }
  .learn.active .ll { color: #fff; }
  .when.soon { background: var(--rating-1); color: #fff; border-color: transparent; }
  .when.mid { background: var(--rating-2); color: #fff; border-color: transparent; }
  .grade-box { flex-shrink: 0; }
  .grade-input { width: 110px; text-align: center; font-weight: 600; min-height: 40px; }
  .edit-form { margin-top: 0.6rem; padding-top: 0.5rem; border-top: 1px dashed var(--border); }
</style>
