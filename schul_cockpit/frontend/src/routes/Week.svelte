<script>
  import { api } from '../lib/api.js';
  import LessonDetail from '../lib/LessonDetail.svelte';

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
    // Per-day absence stats: how many real (non-cancelled) lessons the kid
    // attended vs missed. If everything that ran was missed, the whole day
    // counts as 'absent day' and gets a header marker.
    const dayStats = Array.from({ length: 5 }, () => ({ real: 0, absent: 0 }));
    for (const l of data.lessons) {
      const dayIdx = new Date(l.date + 'T00:00:00').getDay();
      const colIdx = (dayIdx + 6) % 7;
      if (colIdx > 4) continue;
      const key = l.start_hhmm;
      times.add(key);
      if (!byDayTime.has(key)) byDayTime.set(key, {});
      byDayTime.get(key)[colIdx] = l;
      if (!l.is_cancelled) {
        dayStats[colIdx].real += 1;
        if (l.was_absent) dayStats[colIdx].absent += 1;
      }
    }
    const absentDays = dayStats.map((s) => s.real > 0 && s.absent === s.real);
    return { times: [...times].sort(), byDayTime, absentDays };
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
    {#each ['Mo','Di','Mi','Do','Fr'] as day, col}
      <div class="cell header" class:absent-day={grid.absentDays[col]}>
        {day}{#if grid.absentDays[col]}<span class="day-absent">🤒</span>{/if}
      </div>
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
            class:absent={l.was_absent && !l.is_cancelled}
            class:caught-up={l.was_absent && !l.is_cancelled && l.caught_up}
            class:r1={!l.was_absent && l.rating === 1}
            class:r2={!l.was_absent && l.rating === 2}
            class:r3={!l.was_absent && l.rating === 3}
            class:r4={!l.was_absent && l.rating === 4}
            class:subst={l.is_irregular && !l.is_cancelled && !l.was_absent}
            onclick={() => (selected = l)}
          >{label(l)}{#if l.was_absent && !l.is_cancelled}<span class="corner">{l.caught_up ? '✓' : '🤒'}</span>{:else if l.is_irregular && !l.is_cancelled}<span class="corner">↺</span>{/if}{#if l.exam}<span class="corner exam-corner">📝</span>{/if}</button>
        {/if}
      {/each}
    {/each}
  </div>

  <div class="dim" style="margin-top:0.6rem; text-align:center;">
    Tippe auf eine Stunde für Details · 🤒 gefehlt · ✓ nachgeholt
  </div>

{/if}

{#if selected}
  <LessonDetail
    {accountId}
    lesson={selected}
    onclose={() => (selected = null)}
    onsaved={load}
  />
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

  /* Absent (kid missed this lesson, but it ran). Pink so it stands out
     against the green/yellow/red rating colours; striped texture for an
     extra at-a-glance signal. Caught-up dampens the saturation. */
  .week-grid .cell.absent {
    background: var(--absent);
    color: #fff;
    background-image: repeating-linear-gradient(
      45deg,
      rgba(255, 255, 255, 0.18) 0 3px,
      transparent 3px 6px
    );
  }
  .week-grid .cell.absent.caught-up {
    background: color-mix(in oklab, var(--absent) 35%, var(--bg-card));
    color: var(--fg);
  }

  /* Day header gets the medic emoji when every real lesson of that day
     was missed — a 'whole day off sick' at-a-glance signal. */
  .week-grid .cell.header.absent-day {
    color: var(--absent);
    font-weight: 700;
  }
  .day-absent { margin-left: 2px; font-size: 0.75rem; }

  .corner {
    position: absolute;
    top: 0; right: 1px;
    font-size: 0.55rem;
  }
  .exam-corner { bottom: 0; top: auto; }
</style>
