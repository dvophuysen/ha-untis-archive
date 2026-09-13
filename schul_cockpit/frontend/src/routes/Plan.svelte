<script>
  import ActionLabel from '../lib/ActionLabel.svelte';
  import {splitTasks} from '../lib/dayDashboard.js';
  import SharedLearningPlan from '../lib/SharedLearningPlan.svelte';
  import { api } from '../lib/api.js';
  import { isoToday, shiftDateIso, daysBetween, learnStateEmoji } from '../lib/format.js';
  import TaskRow from '../lib/TaskRow.svelte';
  import TaskEditor from '../lib/TaskEditor.svelte';

  let { accountId } = $props();
  const today = isoToday();
  const tomorrow = shiftDateIso(today, 1);

  let plan = $state(null);          // { workload, should } from /plan
  let tasks = $state([]);           // from /tasks
  let loading = $state(true);
  let error = $state(null);
  let showDone = $state(false);
  let editing = $state(null);
  let creating = $state(false);
  let syncing = $state(false);
  let syncMsg = $state(null);

  async function load() {
    if (!accountId) return;
    loading = true;
    error = null;
    try {
      const taskPath = showDone
        ? `/api/accounts/${accountId}/tasks`
        : `/api/accounts/${accountId}/tasks?only_open=true`;
      const [p, t] = await Promise.all([
        api.get(`/api/accounts/${accountId}/plan`),
        api.get(taskPath),
      ]);
      plan = p;
      tasks = t.tasks;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void accountId; void showDone; load(); });

  async function syncNow() {
    syncing = true;
    syncMsg = null;
    try {
      const r = await api.post(`/api/accounts/${accountId}/sync-ha-todos`);
      await load();
      const cleaned =
        (r.orphans_deleted || 0) +
        (r.duplicates_collapsed || 0) +
        (r.rebound_to_done || 0);
      if (cleaned > 0) {
        syncMsg = `${cleaned} alte/doppelte HA aufgeräumt`;
        setTimeout(() => (syncMsg = null), 4000);
      }
    } catch (e) {
      error = e.message;
    } finally {
      syncing = false;
    }
  }

  function quickRank(t) {
    const est = t.estimated_minutes ?? 9999;
    return [est, t.due_date ?? '9999-12-31'];
  }
  function cmpQuick(a, b) {
    const ra = quickRank(a), rb = quickRank(b);
    return ra[0] - rb[0] || (ra[1] < rb[1] ? -1 : ra[1] > rb[1] ? 1 : 0);
  }

  // "Heute zu erledigen": open tasks due today/tomorrow/overdue, quick first.
  const heute = $derived(
    tasks
      .filter((t) => t.status !== 'done' && t.due_date && t.due_date <= tomorrow)
      .sort(cmpQuick),
  );

  // "Demnächst": everything else, grouped.
  const upcoming = $derived.by(() => {
    const week = []; const later = []; const noDate = []; const done = [];
    for (const t of tasks) {
      if (t.status === 'done') { done.push(t); continue; }
      if (!t.due_date) { noDate.push(t); continue; }
      if (t.due_date <= tomorrow) continue; // already in "heute"
      const d = daysBetween(today, t.due_date);
      if (d <= 7) week.push(t); else later.push(t);
    }
    return { week, later, noDate, done:splitTasks(tasks,today).done };
  });

</script>

<p><a href="#/learning">Zum Lernraum <ActionLabel /></a></p>


<div class="row between" style="margin: 0.3rem 0.2rem 0.5rem;">
  <button onclick={() => (showDone = !showDone)} style="font-size:0.85rem; min-height:36px;">
    {showDone ? 'Erledigte ausblenden' : 'Erledigte anzeigen'}
  </button>
  <button class="ghost" onclick={syncNow} disabled={syncing}>{syncing ? '↻ …' : '↻ Aktualisieren'}</button>
</div>
{#if syncMsg}
  <div class="sync-toast">✓ {syncMsg}</div>
{/if}

{#if error}<div class="error-box">{error}</div>{/if}

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if plan}
  <SharedLearningPlan {plan}/>
  <!-- Heute zu erledigen -->
  {#if heute.length > 0}
    <div class="section-title">Heute zu erledigen</div>
    <div class="card" style="padding:0.2rem 0.6rem;">
      {#each heute as task (task.id)}
        <TaskRow {accountId} {task} onchange={load} onopen={(t) => (editing = t)} />
      {/each}
    </div>
  {/if}

  <!-- Demnächst -->
  {#if upcoming.week.length > 0}
    <div class="section-title">Diese Woche <span class="dim">· {upcoming.week.length}</span></div>
    <div class="card" style="padding:0.2rem 0.6rem;">
      {#each upcoming.week as task (task.id)}
        <TaskRow {accountId} {task} onchange={load} onopen={(t) => (editing = t)} />
      {/each}
    </div>
  {/if}
  {#if upcoming.later.length > 0}
    <div class="section-title">Später <span class="dim">· {upcoming.later.length}</span></div>
    <div class="card" style="padding:0.2rem 0.6rem;">
      {#each upcoming.later as task (task.id)}
        <TaskRow {accountId} {task} onchange={load} onopen={(t) => (editing = t)} />
      {/each}
    </div>
  {/if}
  {#if upcoming.noDate.length > 0}
    <div class="section-title">Ohne Datum <span class="dim">· {upcoming.noDate.length}</span></div>
    <div class="card" style="padding:0.2rem 0.6rem;">
      {#each upcoming.noDate as task (task.id)}
        <TaskRow {accountId} {task} onchange={load} onopen={(t) => (editing = t)} />
      {/each}
    </div>
  {/if}
  {#if showDone && upcoming.done.length > 0}
    <div class="section-title">Erledigt <span class="dim">· {upcoming.done.length}</span></div>
    <div class="card" style="padding:0.2rem 0.6rem;">
      {#each upcoming.done as task (task.id)}
        <TaskRow {accountId} {task} onchange={load} onopen={(t) => (editing = t)} />
      {/each}
    </div>
  {/if}

  {#if heute.length === 0 && plan.should.length === 0 && upcoming.week.length === 0 && upcoming.later.length === 0 && upcoming.noDate.length === 0}
    <div class="empty" style="margin-top:1rem;">Keine offenen Aufgaben — Zeit zum Durchatmen. 🙂</div>
  {/if}
{/if}

<button class="fab" onclick={() => (creating = true)} aria-label="Neue Aufgabe">+</button>

{#if creating}
  <TaskEditor {accountId} task={null} onclose={() => (creating = false)} onsaved={load} />
{/if}
{#if editing}
  <TaskEditor {accountId} task={editing} onclose={() => (editing = null)} onsaved={load} />
{/if}

<style>
  .sync-toast {
    background: color-mix(in srgb, var(--rating-3) 12%, var(--bg-card));
    border: 1px solid var(--rating-3);
    border-radius: var(--radius);
    padding: 0.45rem 0.7rem;
    margin: 0.2rem 0 0.5rem;
    font-size: 0.85rem;
  }
</style>
