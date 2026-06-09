<script>
  import { api } from '../lib/api.js';
  import { formatShortDate, daysBetween, isoToday } from '../lib/format.js';

  let { accountId } = $props();
  const today = isoToday();

  let data = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let busyKey = $state(null);

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

<h2 style="margin:0 0 0.6rem; font-size:1.15rem;">Klausuren</h2>

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
</style>
