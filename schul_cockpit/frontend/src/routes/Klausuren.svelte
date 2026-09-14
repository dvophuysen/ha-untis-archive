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
  // Abgeschlossene Schuljahre — erst auf Wunsch geladen.
  let archive = $state(null);
  let archiveOpen = $state(false);

  async function openArchive() {
    archiveOpen = !archiveOpen;
    if (!archiveOpen || archive) return;
    try {
      archive = (await api.get(`/api/accounts/${accountId}/exams/archive`)).exams;
    } catch (e) {
      error = e.message;
    }
  }
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

  const LEARN = [
    { v: 0, label: 'nicht begonnen', emoji: '⚪' },
    { v: 1, label: 'viel offen', emoji: '😟' },
    { v: 2, label: 'mittel', emoji: '😐' },
    { v: 3, label: 'sicher', emoji: '😀' },
  ];

  // Datum und Abstand stehen immer zusammen. Vorher zeigte die Karte bis sieben
  // Tage nur den Abstand und danach nur das Datum; beides war nie vergleichbar.
  function whenLabel(dateIso) {
    const d = daysBetween(today, dateIso);
    if (d === 0) return 'heute';
    if (d === 1) return 'morgen';
    if (d === 2) return 'übermorgen';
    if (d < 0) return `vor ${Math.abs(d)} Tagen`;
    if (d % 7 === 0 && d >= 14) return `in ${d / 7} Wochen`;
    return `in ${d} Tagen`;
  }
  function urgencyClass(dateIso) {
    const d = daysBetween(today, dateIso);
    if (d <= 2) return 'now';
    if (d <= 7) return 'soon';
    if (d <= 21) return 'mid';
    return 'far';
  }
  const URGENCY = { now: 'unmittelbar', soon: 'diese Woche', mid: 'in Vorbereitung', far: 'noch Zeit' };

  function practiceLabel(p) {
    if (!p || (!p.units && !p.independent && !p.papers)) return 'Für dieses Fach ist noch nichts geübt.';
    const parts = [];
    if (p.units) parts.push(`${p.units} ${p.units === 1 ? 'Lerneinheit' : 'Lerneinheiten'}`);
    if (p.independent) parts.push(`${p.independent} ${p.independent === 1 ? 'Thema' : 'Themen'} ohne Hilfe gezeigt`);
    if (p.papers) parts.push(`${p.papers} ${p.papers === 1 ? 'Übungsarbeit' : 'Übungsarbeiten'} geschrieben`);
    return parts.join(' · ');
  }
  function practiceUrl(e) {
    const q = new URLSearchParams({ subject: e.subject_name ?? '', topic: e.title ?? '', mode: 'exam' });
    return `#/lernen?${q.toString()}`;
  }
</script>

<div class="row between" style="margin: 0 0 0.6rem; align-items:center;">
  <h2 style="margin:0; font-size:1.15rem;">📝 Arbeiten & Tests</h2>
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
  <div class="section-title">Demnächst</div>
  {#if data.upcoming.length === 0}
    <div class="empty" style="padding:1rem;">
      Keine Arbeiten eingetragen. Sie kommen aus dem IServ-Klausurplan, sobald die
      Schule sie dort einträgt.
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
            <div class="dim">
              {formatShortDate(e.date)} · {whenLabel(e.date)}{#if e.source === 'manual'} · selbst eingetragen{/if}
            </div>
          </div>
          <span class="badge when {urgencyClass(e.date)}">{URGENCY[urgencyClass(e.date)]}</span>
        </div>

        <div class="measured">{practiceLabel(e.practice)}</div>
        {#if e.practice?.last_at}<div class="dim measured-when">zuletzt geübt {formatShortDate(e.practice.last_at.slice(0, 10))}</div>{/if}
        {#if e.subject_name}
          <a class="practice-link" href={practiceUrl(e)}>Für diese Arbeit üben</a>
        {/if}

        <div class="muted" style="margin-top:0.5rem;">Wie sicher fühlst du dich?</div>
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

        {#if canManage}
          <div class="dim" style="margin-top:0.5rem; font-size:0.78rem;">
            {#if e.source === 'manual'}
              nicht aus dem Klausurplan — unter <a href="#/exams">Verwalten</a> änderbar.
            {:else}
              kommt aus dem IServ-Klausurplan — geändert wird er dort.
            {/if}
          </div>
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

  {#if data.archived_count > 0}
    <button class="ghost" style="width:100%; margin-top:0.8rem;" onclick={openArchive}>
      {archiveOpen ? '▾' : '▸'} Archiv abgeschlossener Schuljahre ({data.archived_count})
    </button>
    {#if archiveOpen}
      {#if archive === null}
        <div class="empty"><span class="spinner"></span></div>
      {:else}
        {#each archive as e (e.exam_key)}
          <div class="card compact">
            <div class="row between" style="align-items:flex-start;">
              <div style="min-width:0;">
                <strong>{e.subject_name ?? e.title}</strong>
                <div class="dim">{formatShortDate(e.date)}</div>
              </div>
              {#if e.grade_label}<span class="badge">{e.grade_label}</span>{/if}
            </div>
          </div>
        {/each}
      {/if}
    {/if}
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
  .when { white-space: nowrap; }
  .when.now { background: var(--rating-1); color: #fff; border-color: transparent; }
  .when.soon { background: var(--rating-2); color: #fff; border-color: transparent; }
  .when.mid { background: var(--bg); }
  .when.far { background: transparent; opacity: .75; }
  .measured { margin-top: 0.5rem; font-size: 0.85rem; }
  .measured-when { font-size: 0.78rem; }
  .practice-link { display: inline-block; margin-top: 0.5rem; font-weight: 600; }
  .grade-box { flex-shrink: 0; }
  .grade-input { width: 110px; text-align: center; font-weight: 600; min-height: 40px; }
  .edit-form { margin-top: 0.6rem; padding-top: 0.5rem; border-top: 1px dashed var(--border); }
</style>
