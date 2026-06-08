<script>
  import { api } from '../lib/api.js';

  let { accountId } = $props();

  // Local-timezone date string (YYYY-MM-DD). NEVER use toISOString() here —
  // it converts to UTC and shifts the date back a day in positive-offset
  // zones (e.g. CEST), which made "Heute" jump to the previous week.
  function isoLocal(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  function mondayOf(d) {
    const x = new Date(d);
    const dow = (x.getDay() + 6) % 7;
    x.setDate(x.getDate() - dow);
    x.setHours(0, 0, 0, 0);
    return x;
  }

  let start = $state(isoLocal(mondayOf(new Date())));
  let data = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let selected = $state(null);

  async function load() {
    if (!accountId) return;
    loading = true;
    error = null;
    try {
      data = await api.get(`/api/accounts/${accountId}/week?start=${start}`);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void accountId; void start; load(); });

  function goToday() {
    start = isoLocal(mondayOf(new Date()));
  }

  function shiftWeek(deltaDays) {
    const d = new Date(start + 'T00:00:00');
    d.setDate(d.getDate() + deltaDays);
    start = isoLocal(d);
  }

  const grid = $derived.by(() => {
    if (!data) return null;
    const byDayTime = new Map();
    const times = new Set();
    for (const l of data.lessons) {
      const dayIdx = new Date(l.date + 'T00:00:00').getDay();
      const colIdx = (dayIdx + 6) % 7;
      if (colIdx > 4) continue;
      const key = l.start_hhmm;
      times.add(key);
      if (!byDayTime.has(key)) byDayTime.set(key, {});
      byDayTime.get(key)[colIdx] = l;
    }
    return { times: [...times].sort(), byDayTime };
  });

  function label(l) {
    return l.subject_short || (l.subject_name ?? '').slice(0, 4);
  }
</script>

<div class="row between" style="margin: 0.3rem 0.2rem 0.6rem;">
  <button onclick={() => shiftWeek(-7)}>←</button>
  <button onclick={goToday}>Heute</button>
  <button onclick={() => shiftWeek(7)}>→</button>
</div>

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if error}
  <div class="error-box">{error}</div>
{:else if data && grid}
  <div class="dim" style="text-align:center; margin-bottom:0.5rem;">{data.start} – {data.end}</div>

  <div class="week-grid">
    <div class="cell header"></div>
    {#each ['Mo','Di','Mi','Do','Fr'] as day}
      <div class="cell header">{day}</div>
    {/each}

    {#each grid.times as t}
      <div class="cell time">{t}</div>
      {#each [0,1,2,3,4] as col}
        {@const l = grid.byDayTime.get(t)?.[col]}
        {#if !l}
          <div class="cell empty-cell"></div>
        {:else}
          <button
            class="cell"
            class:cancelled={l.is_cancelled}
            class:r1={l.rating === 1}
            class:r2={l.rating === 2}
            class:r3={l.rating === 3}
            class:r4={l.rating === 4}
            class:subst={l.is_irregular && !l.is_cancelled}
            onclick={() => (selected = l)}
          >{label(l)}{#if l.is_irregular && !l.is_cancelled}<span class="corner">↺</span>{/if}{#if l.exam}<span class="corner">📝</span>{/if}</button>
        {/if}
      {/each}
    {/each}
  </div>

  <div class="dim" style="margin-top:0.6rem; text-align:center;">Tippe auf eine Stunde für Details</div>
{/if}

{#if selected}
  <div class="modal-backdrop" onclick={() => (selected = null)} role="presentation">
    <div class="modal" onclick={(e) => e.stopPropagation()} role="dialog">
      <div class="row between" style="margin-bottom:0.5rem;">
        <h2 style="margin:0; font-size:1.1rem;">{selected.subject_name ?? selected.subject_short ?? 'Stunde'}</h2>
        <button class="ghost" onclick={() => (selected = null)}>✕</button>
      </div>
      <div class="muted">{selected.date} · {selected.start_hhmm}–{selected.end_hhmm}</div>
      <div class="row gap-sm" style="margin:0.4rem 0; flex-wrap:wrap;">
        {#if selected.is_cancelled}<span class="badge cancelled">❌ Ausfall</span>{/if}
        {#if selected.is_irregular && !selected.is_cancelled}<span class="badge substitution">↺ Vertretung</span>{/if}
        {#if selected.was_absent}<span class="badge absent">🤒 gefehlt</span>{/if}
        {#if selected.exam}<span class="badge exam">📝 Klausur</span>{/if}
        {#if selected.rating === 4}<span class="badge">👀 nur Aufsicht</span>{/if}
      </div>
      <div class="card compact" style="margin:0;">
        <div>👤 {selected.teacher_name ?? '—'}
          {#if selected.is_teacher_substituted && selected.teacher_orig_name}
            <span class="dim">(statt {selected.teacher_orig_name})</span>
          {/if}
        </div>
        {#if selected.room}<div>📍 {selected.room}
          {#if selected.is_room_substituted && selected.room_orig}<span class="dim">(statt {selected.room_orig})</span>{/if}
        </div>{/if}
        {#if selected.exam?.name}<div style="color:var(--exam)">📝 {selected.exam.name}</div>{/if}
        {#if selected.lstext}<div style="margin-top:0.4rem;">{selected.lstext}</div>{/if}
        {#if selected.subst_text && selected.subst_text !== selected.lstext}
          <div class="dim" style="margin-top:0.3rem;">ℹ️ {selected.subst_text}</div>
        {/if}
        {#if selected.rating}
          <div class="muted" style="margin-top:0.4rem;">Deine Bewertung: {['','😟','😐','😀','👀'][selected.rating] ?? ''}</div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .week-grid .cell.subst { outline: 1px solid var(--substitution); }
  .week-grid button.cell {
    position: relative;
    border: none;
    cursor: pointer;
    font: inherit;
  }
  .week-grid .cell.r4 { background: var(--cancelled); color: #fff; }
  .corner {
    position: absolute;
    top: 0; right: 1px;
    font-size: 0.55rem;
  }
</style>
