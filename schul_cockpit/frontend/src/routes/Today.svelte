<script>
  import ActionLabel from '../lib/ActionLabel.svelte';
  import LearningGoal from '../lib/LearningGoal.svelte';
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { isoToday, formatShortDate } from '../lib/format.js';
  import { splitLessons, splitTasks } from '../lib/dayDashboard.js';
  import LessonCard from '../lib/LessonCard.svelte';
  import PackingChecklist from '../lib/PackingChecklist.svelte';
  import TaskRow from '../lib/TaskRow.svelte';
  import TaskEditor from '../lib/TaskEditor.svelte';

  let { accountId } = $props();
  let data = $state(null), tasks = $state([]), plan = $state(null);
  let loading = $state(true), error = $state(''), planError = $state('');
  let editing = $state(null), creating = $state(false), now = $state(new Date());
  let showHistory = $state(false), showDone = $state(false), message = $state('');
  let request = 0;
  async function load(reset = false) {
    if (!accountId) return;
    const id = accountId, ticket = ++request;
    if (reset) { data = null; tasks = []; plan = null; editing = null; showHistory = false; showDone = false; message = ''; loading = true; }
    error = ''; planError = '';
    const results = await Promise.allSettled([
      api.get(`/api/accounts/${id}/today`), api.get(`/api/accounts/${id}/tasks`), api.get(`/api/accounts/${id}/plan`),
    ]);
    if (ticket !== request || id !== accountId) return;
    const [day, work, learning] = results;
    if (day.status === 'fulfilled') data = { ...day.value, lessons: day.value.lessons.map(l => ({ ...l, date: l.date || day.value.date })) };
    else error = 'Dein Stundenplan konnte nicht aktualisiert werden.';
    if (work.status === 'fulfilled') tasks = work.value.tasks;
    else error += ' Deine Aufgaben konnten nicht aktualisiert werden.';
    if (learning.status === 'fulfilled') plan = learning.value;
    else { plan = null; planError = 'Deine Lernvorschläge sind gerade nicht verfügbar.'; }
    now = new Date(); loading = false;
  }
  $effect(() => { void accountId; load(true); });
  onMount(() => {
    const tick = () => { const oldDay = isoTodayAt(now); now = new Date(); if (oldDay !== isoTodayAt(now)) load(); };
    const resume = () => { if (!document.hidden) { now = new Date(); load(); } };
    const timer = setInterval(tick, 30000);
    document.addEventListener('visibilitychange', resume);
    window.addEventListener('focus', resume);
    return () => { clearInterval(timer); request++; document.removeEventListener('visibilitychange', resume); window.removeEventListener('focus', resume); };
  });
  function isoTodayAt(d) { return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
  const lessons = $derived(splitLessons(data?.lessons ?? [], data?.date, now));
  const work = $derived(splitTasks(tasks, data?.date ?? isoToday()));
  const activeUpcoming = $derived(lessons.upcoming.filter(l => !l.is_cancelled && !l.was_absent));
  const beforeSchool = $derived.by(() => {
    const first = data?.lessons?.find(l => !l.is_cancelled && !l.was_absent);
    if (!first || !Number.isInteger(first.start_time)) return false;
    const start = new Date(`${data.date}T${String(Math.floor(first.start_time / 100)).padStart(2,'0')}:${String(first.start_time % 100).padStart(2,'0')}:00`);
    return now < start;
  });
  function feedbackSaved() { message = 'Rückmeldung gespeichert.'; }
  function taskSaved() { message = 'Aufgabe gespeichert.'; load(); }
</script>

<header class="day-title"><div><p class="eyebrow">{formatShortDate(data?.date ?? isoToday())}</p><h2>Dein Tag</h2></div><button class="ghost" onclick={() => load()} aria-label="Tagesübersicht aktualisieren">Aktualisieren</button></header>
{#if error}<div class="error-box" role="alert">{error} Bitte erneut aktualisieren; angezeigte Daten können veraltet sein.</div>{/if}
<p class="save-message" role="status">{message}</p>
{#if loading}<p>Lade deinen Tag …</p>{:else}
  {#if data}
    <section class="day-section school" class:school-done={!lessons.upcoming.length && !lessons.open.length}>
      <div class="section-head"><h3>{activeUpcoming.length ? 'In der Schule' : 'Dein Schultag'}</h3><a href="#/week"><ActionLabel label="Woche ansehen" /></a></div>
      {#if activeUpcoming.length}<p class="next-lesson"><strong>{activeUpcoming[0].subject_name || activeUpcoming[0].subject_short}</strong> · {activeUpcoming[0].start_hhmm}{#if activeUpcoming[0].room} · Raum {activeUpcoming[0].room}{/if}</p>{/if}
      {#if beforeSchool}<PackingChecklist {accountId} schoolDay={data.date} />{/if}
      {#if !beforeSchool}{#each lessons.upcoming as lesson (lesson.id)}<LessonCard {accountId} {lesson} preview />{/each}{/if}
      {#if lessons.open.length}<h4>Noch kurz zurückmelden · {lessons.open.length}</h4><p class="eyebrow">Wie gut hast du den Stoff verstanden?</p>
        {#each lessons.open as lesson (lesson.id)}<LessonCard {accountId} {lesson} onsaved={feedbackSaved} />{/each}
      {:else if data.lessons.length && !activeUpcoming.length}<p class="muted">Keine offenen Rückmeldungen zu beendeten Stunden.</p>
      {:else if !data.lessons.length}<p class="muted">Heute ist kein Unterricht eingetragen.</p>{/if}
      {#if lessons.history.length}<button class="text-action" aria-expanded={showHistory} onclick={() => showHistory = !showHistory}>{showHistory ? 'Verlauf schließen' : `Vergangene Stunden ansehen (${lessons.history.length})`}</button>
        {#if showHistory}{#each lessons.history as lesson (lesson.id)}<LessonCard {accountId} {lesson} onsaved={feedbackSaved} />{/each}{/if}
      {/if}
    </section>
  {/if}
  <section class="day-section obligations">
    <div class="section-head"><h3>Heute erledigen</h3><button class="text-action" onclick={() => creating = true}>Aufgabe ergänzen</button></div>
    {#each work.due as task (task.id)}<TaskRow {accountId} {task} onchange={taskSaved} onopen={t => editing = t} />{:else}{#if error}<p>Aufgabenstand bitte aktualisieren.</p>{:else}<p class="all-clear"><span aria-hidden="true">🎉</span><strong>Für morgen ist nichts mehr offen!</strong></p>{/if}{/each}
  </section>
  {#if work.ahead.length}<section class="day-section"><h3>Schon vorziehen</h3>{#each work.ahead as task (task.id)}<TaskRow {accountId} {task} onchange={taskSaved} onopen={t => editing = t} />{/each}</section>{/if}
  {#if work.undated.length}<section class="day-section"><h3>Noch ohne Termin</h3>{#each work.undated as task (task.id)}<TaskRow {accountId} {task} onchange={taskSaved} onopen={t => editing = t} />{/each}</section>{/if}
  <section class="day-section practice">
    <div class="section-head"><h3><a href="#/learning"><ActionLabel label="Üben & vorbereiten" /></a></h3></div>
    {#if planError}<p role="status">{planError}</p>{/if}
    {#each plan?.errors ?? [] as problem}<p class="muted">{problem}</p>{/each}
    {#each plan?.upcoming_exams ?? [] as exam}<a class="exam-link" href="#/klausuren">{exam.subject_name || exam.subject || exam.title || 'Arbeit'} · {formatShortDate(exam.date)} <ActionLabel /></a>{/each}
    {#each plan?.today?.actions ?? [] as item (item.key)}
      <LearningGoal goal={item}/>
    {:else}{#if !planError}<p class="muted">Heute ist keine zusätzliche Übung eingeplant.</p>{/if}{/each}
  </section>
  {#if data?.next}<section class="day-section tomorrow">
    <h3>Nächster Schultag · {formatShortDate(data.next.date)}</h3>
    <PackingChecklist {accountId} schoolDay={data.next.date} />
  </section>{/if}
  {#if work.done.length}<section class="day-section"><button class="text-action" aria-expanded={showDone} onclick={() => showDone = !showDone}>{showDone ? 'Erledigte Aufgaben schließen' : 'Erledigte Aufgaben ansehen'}</button>{#if showDone}{#each work.done as task (task.id)}<TaskRow {accountId} {task} onchange={taskSaved} onopen={t => editing = t} />{/each}{/if}</section>{/if}
{/if}
{#if editing}<TaskEditor {accountId} task={editing} onclose={() => editing = null} onsaved={taskSaved} />{/if}
{#if creating}<TaskEditor {accountId} task={null} onclose={() => creating = false} onsaved={taskSaved} />{/if}

<style>
  .all-clear{display:flex;align-items:center;gap:12px;padding:10px 0;margin:0}.all-clear>span{font-size:2rem}.all-clear strong{font-size:1rem;font-weight:550}
  .day-title,.section-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
  .day-title h2{margin:0;font-size:1.6rem}.eyebrow{color:var(--fg-muted);margin:0 0 8px;font-size:.9rem}
  .day-section{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:12px;margin:0 0 8px}
  h3{font-size:1.1rem;margin:0 0 8px}h4{margin:16px 0 8px}.section-head h3{margin:0}.section-head{margin-bottom:8px}
  .section-head>a,.text-action{font-size:.9rem}.section-head h3 a{font:inherit;color:var(--fg)}.text-action{padding:8px 0;background:transparent;border:0;color:var(--accent);text-align:left}
  .next-lesson{padding:10px 0;border-bottom:1px solid var(--border)}.save-message{min-height:1.3em;color:var(--accent);font-size:.9rem;margin:6px 0}
  .learning-row{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid var(--border)}.learning-row:last-child{border:0}.learning-row p{margin:4px 0;overflow-wrap:anywhere}
  .open-action{padding:10px;border:1px solid var(--border);border-radius:10px;min-height:44px;flex-shrink:0}.exam-link{display:block;padding:12px 0;border-bottom:1px solid var(--border)}
  .school-done{padding:8px 0;background:transparent;border:0;margin-bottom:8px}.school-done .section-head{margin-bottom:4px}.school-done p{margin:4px 0}.school-done h3{font-size:1rem}
  .school:not(.school-done){background:var(--school-soft)}.obligations{border-top:4px solid var(--accent)}.practice{background:var(--learn-soft)}
  .tomorrow{background:var(--accent-soft);border-left:4px solid var(--accent)}
  @media(max-width:380px){.day-section{padding:10px}.learning-row{flex-wrap:wrap}}
</style>
