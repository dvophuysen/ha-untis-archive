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
  .corner {
    position: absolute;
    top: 0; right: 1px;
    font-size: 0.55rem;
  }
</style>
