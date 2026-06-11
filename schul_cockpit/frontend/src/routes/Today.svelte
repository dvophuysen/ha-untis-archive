<script>
  import { api } from '../lib/api.js';
  import { shiftDateIso, formatShortDate } from '../lib/format.js';
  import LessonCard from '../lib/LessonCard.svelte';
  import TaskRow from '../lib/TaskRow.svelte';
  import TaskEditor from '../lib/TaskEditor.svelte';
  import HeaderChips from '../lib/HeaderChips.svelte';

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
  // "Heute zu erledigen" = überfällig + heute fällig + MORGEN fällig.
  // Eine HA mit Fälligkeit morgen muss heute gemacht werden — alles andere
  // wäre zu spät. (Datumsmathematik geht über shiftDateIso, NICHT über
  // toISOString() — letzteres rechnet in UTC um und schiebt in MESZ den Tag.)
  const dueToday = $derived.by(() => {
    if (!todayIso) return [];
    const tom = shiftDateIso(todayIso, 1);
    return tasks.filter((t) => t.due_date && t.due_date <= tom);
  });

  // Snapshot der Uhrzeit beim ersten Render — Phase bleibt für die ganze
  // Sitzung gleich (Seite wird beim Wiederöffnen ohnehin neu geladen).
  const nowHhmm = (() => {
    const n = new Date();
    return n.getHours() * 100 + n.getMinutes();
  })();

  // "before" solange noch eine nicht-ausgefallene Stunde aussteht.
  // Sonst (Schulschluss erreicht / Wochenende / schulfrei) "after".
  const phase = $derived.by(() => {
    const ls = data?.lessons ?? [];
    let max = -1;
    for (const l of ls) {
      if (l.is_cancelled) continue;
      if (typeof l.end_time === 'number' && l.end_time > max) max = l.end_time;
    }
    if (max < 0) return 'after';
    return nowHhmm > max ? 'after' : 'before';
  });

  // Stundenplan-Block: nach Schulschluss zeigt die Seite den NÄCHSTEN
  // Schultag. Wenn nichts dafür da ist (Ferien o.ä.), bleiben wir bei
  // heute mit Hinweis "kein Unterricht".
  const showNext = $derived(phase === 'after' && !!data?.next);
  const planDate = $derived(showNext ? data.next.date : data?.date);
  const planLessons = $derived(showNext ? data.next.lessons : (data?.lessons ?? []));
  const planLabel = $derived(showNext ? 'Morgen' : 'Heute');

  function scrollTo(id) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
</script>

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if error}
  <div class="error-box">{error}</div>
{:else if data}
  <HeaderChips
    {accountId}
    todayIso={data.date}
    lessons={data.lessons}
    {phase}
    dueTodayCount={dueToday.length}
    onJumpDueToday={() => scrollTo('section-due-today')}
    onJumpLesson={(id) => scrollTo('lesson-' + id)}
  />

  {#if dueToday.length > 0}
    <div id="section-due-today" class="section-title">Heute zu erledigen</div>
    <div class="card" style="padding:0.2rem 0.6rem;">
      {#each dueToday as task (task.id)}
        <TaskRow {accountId} {task} onchange={load} onopen={(t) => (editing = t)} />
      {/each}
    </div>
  {/if}

  <h2 class="day-heading">
    {planLabel} <span class="day-heading-date">· {formatShortDate(planDate)}</span>
  </h2>
  {#if planLessons.length === 0}
    <div class="empty">Kein Unterricht.</div>
  {:else}
    {#each planLessons as lesson (lesson.id)}
      <LessonCard {accountId} {lesson} />
    {/each}
  {/if}
{/if}

{#if editing}
  <TaskEditor {accountId} task={editing} onclose={() => (editing = null)} onsaved={load} />
{/if}

<style>
  .day-heading {
    font-size: 1.15rem;
    font-weight: 700;
    margin: 1.2rem 0.2rem 0.5rem;
  }
  .day-heading-date {
    font-weight: 500;
    color: var(--fg-muted);
    font-size: 0.95rem;
  }
</style>
