<script>
  import { api } from '../lib/api.js';
  import TaskRow from '../lib/TaskRow.svelte';
  import TaskEditor from '../lib/TaskEditor.svelte';

  let { accountId } = $props();

  let tasks = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let showAll = $state(false);
  let editing = $state(null);
  let creating = $state(false);
  let syncing = $state(false);

  async function load() {
    if (!accountId) return;
    loading = true;
    error = null;
    try {
      const path = showAll
        ? `/api/accounts/${accountId}/tasks`
        : `/api/accounts/${accountId}/tasks?only_open=true`;
      const res = await api.get(path);
      tasks = res.tasks;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function syncNow() {
    syncing = true;
    try {
      await api.post(`/api/accounts/${accountId}/sync-ha-todos`);
      await load();
    } catch (e) {
      error = e.message;
    } finally {
      syncing = false;
    }
  }

  $effect(() => { void accountId; void showAll; load(); });

  const today = new Date().toISOString().slice(0, 10);

  const sections = $derived.by(() => {
    const buckets = { overdue: [], today: [], tomorrow: [], week: [], later: [], noDate: [] };
    const todayDate = new Date(today);
    const tomorrow = new Date(todayDate); tomorrow.setDate(tomorrow.getDate() + 1);
    const weekEnd = new Date(todayDate); weekEnd.setDate(weekEnd.getDate() + 7);
    for (const t of tasks) {
      if (!t.due_date) { buckets.noDate.push(t); continue; }
      const d = new Date(t.due_date);
      if (d < todayDate) buckets.overdue.push(t);
      else if (t.due_date === today) buckets.today.push(t);
      else if (d.toDateString() === tomorrow.toDateString()) buckets.tomorrow.push(t);
      else if (d <= weekEnd) buckets.week.push(t);
      else buckets.later.push(t);
    }
    return buckets;
  });

  const sectionDefs = [
    { key: 'overdue', label: 'Überfällig' },
    { key: 'today', label: 'Heute fällig' },
    { key: 'tomorrow', label: 'Morgen' },
    { key: 'week', label: 'Diese Woche' },
    { key: 'later', label: 'Später' },
    { key: 'noDate', label: 'Ohne Datum' },
  ];
</script>

<div class="row between" style="margin: 0.3rem 0.2rem 0.6rem;">
  <div class="row gap-sm">
    <button onclick={() => (showAll = !showAll)}>{showAll ? 'Nur offene' : 'Alle anzeigen'}</button>
  </div>
  <button class="ghost" onclick={syncNow} disabled={syncing}>{syncing ? '↻' : '↻ Sync'}</button>
</div>

{#if error}<div class="error-box">{error}</div>{/if}

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if tasks.length === 0}
  <div class="empty">Keine Aufgaben.</div>
{:else}
  {#each sectionDefs as sec}
    {#if sections[sec.key].length > 0}
      <div class="section-title">{sec.label} <span class="dim">· {sections[sec.key].length}</span></div>
      <div class="card" style="padding:0.2rem 0.6rem;">
        {#each sections[sec.key] as task (task.id)}
          <TaskRow {accountId} {task} onchange={load} onopen={(t) => (editing = t)} />
        {/each}
      </div>
    {/if}
  {/each}
{/if}

<button class="fab" onclick={() => (creating = true)} aria-label="Neue Aufgabe">+</button>

{#if creating}
  <TaskEditor {accountId} task={null} onclose={() => (creating = false)} onsaved={load} />
{/if}
{#if editing}
  <TaskEditor {accountId} task={editing} onclose={() => (editing = null)} onsaved={load} />
{/if}
