<script>
  import { api } from '../lib/api.js';

  let { accountId } = $props();

  let start = $state(mondayOf(new Date()).toISOString().slice(0, 10));
  let data = $state(null);
  let loading = $state(true);
  let error = $state(null);

  function mondayOf(d) {
    const x = new Date(d);
    const dow = (x.getDay() + 6) % 7;
    x.setDate(x.getDate() - dow);
    x.setHours(0, 0, 0, 0);
    return x;
  }

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

  function shiftWeek(deltaDays) {
    const d = new Date(start);
    d.setDate(d.getDate() + deltaDays);
    start = d.toISOString().slice(0, 10);
  }

  const grid = $derived.by(() => {
    if (!data) return null;
    const byDayTime = new Map();
    const times = new Set();
    for (const l of data.lessons) {
      const dayIdx = new Date(l.date).getDay();
      const colIdx = (dayIdx + 6) % 7;
      if (colIdx > 4) continue;
      const key = l.start_hhmm;
      times.add(key);
      if (!byDayTime.has(key)) byDayTime.set(key, {});
      byDayTime.get(key)[colIdx] = l;
    }
    return { times: [...times].sort(), byDayTime };
  });
</script>

<div class="row between" style="margin: 0.3rem 0.2rem 0.6rem;">
  <button onclick={() => shiftWeek(-7)}>← Woche</button>
  <button onclick={() => (start = mondayOf(new Date()).toISOString().slice(0, 10))}>Heute</button>
  <button onclick={() => shiftWeek(7)}>Woche →</button>
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
        {:else if l.is_cancelled}
          <div class="cell cancelled" title="Ausfall: {l.subject_name}">×</div>
        {:else}
          <div
            class="cell"
            class:r1={l.rating === 1}
            class:r2={l.rating === 2}
            class:r3={l.rating === 3}
            title="{l.subject_name} {l.teacher_name ?? ''}"
          >{(l.subject_name ?? '').slice(0, 4)}</div>
        {/if}
      {/each}
    {/each}
  </div>
{/if}
