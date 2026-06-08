<script>
  import { api } from '../lib/api.js';
  import LessonCard from '../lib/LessonCard.svelte';
  import TaskRow from '../lib/TaskRow.svelte';
  import TaskEditor from '../lib/TaskEditor.svelte';

  let { accountId } = $props();

  let data = $state(null);
  let tasks = $state([]);
  let error = $state(null);
  let loading = $state(true);
  let editing = $state(null);

  async function load() {
    if (!accountId) return;
    loading = true;
    error = null;
    try {
      const [today, taskRes] = await Promise.all([
        api.get(`/api/accounts/${accountId}/today`),
        api.get(`/api/accounts/${accountId}/tasks?only_open=true`),
      ]);
      data = today;
      tasks = taskRes.tasks;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void accountId; load(); });

  const todayIso = $derived(data?.date);
  function tomorrowIso(t) {
    if (!t) return '';
    const d = new Date(t + 'T00:00:00');
    d.setDate(d.getDate() + 1);
    return d.toISOString().slice(0, 10);
  }
  // "Heute zu erledigen" = überfällig + heute fällig + MORGEN fällig.
  // Eine HA mit Fälligkeit morgen muss heute gemacht werden — alles andere
  // ist zu spät. Würde sie unter "bald" stehen, übersehen die Kinder sie.
  const dueToday = $derived(
    tasks.filter((t) => t.due_date && t.due_date <= tomorrowIso(todayIso)),
  );
  // "Bald" = übermorgen bis +3 Tage (echtes Vorplanen, keine Pflicht heute).
  const dueSoon = $derived(
    tasks.filter((t) => {
      if (!t.due_date || !todayIso) return false;
      const tom = tomorrowIso(todayIso);
      if (t.due_date <= tom) return false;
      const days = (new Date(t.due_date) - new Date(todayIso)) / 86400000;
      return days <= 3;
    }),
  );
</script>

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if error}
  <div class="error-box">{error}</div>
{:else if data}
  <div class="banner">
    {#if dueToday.length > 0}<strong>{dueToday.length}</strong> heute zu erledigen · {/if}
    {#if dueSoon.length > 0}<strong>{dueSoon.length}</strong> bald · {/if}
    {#if data.summary.upcoming_exams_7d > 0}📝 <strong>{data.summary.upcoming_exams_7d}</strong> Klausuren in 7 Tagen{/if}
    {#if dueToday.length === 0 && dueSoon.length === 0 && data.summary.upcoming_exams_7d === 0}
      Alles im grünen Bereich.
    {/if}
  </div>

  {#if dueToday.length > 0}
    <div class="section-title">Heute zu erledigen</div>
    <div class="card" style="padding:0.2rem 0.6rem;">
      {#each dueToday as task (task.id)}
        <TaskRow {accountId} {task} onchange={load} onopen={(t) => (editing = t)} />
      {/each}
    </div>
  {/if}

  <div class="section-title">Stundenplan {data.date}</div>
  {#if data.lessons.length === 0}
    <div class="empty">Heute kein Unterricht.</div>
  {:else}
    {#each data.lessons as lesson (lesson.id)}
      <LessonCard {accountId} {lesson} />
    {/each}
  {/if}
{/if}

{#if editing}
  <TaskEditor {accountId} task={editing} onclose={() => (editing = null)} onsaved={load} />
{/if}
