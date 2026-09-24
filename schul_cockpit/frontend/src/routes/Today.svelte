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
  import TaskDetail from '../lib/TaskDetail.svelte';
  import AfternoonCheck from '../lib/AfternoonCheck.svelte';

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
    if (day.status === 'fulfilled') { data = { ...day.value, lessons: day.value.lessons.map(l => ({ ...l, date: l.date || day.value.date })) }; }
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
  // Abends zählt nur noch, was für morgen fehlt. Vorschläge zum Vorziehen und
  // zum Üben sind dann nicht hilfreich, sie stehen aufklappbar weiter unten.
  const evening = $derived.by(() => {
    const from = data?.evening_from;
    if (!from || !data) return false;
    const [h, m] = from.split(':').map(Number);
    if (!Number.isFinite(h) || !Number.isFinite(m)) return false;
    return now.getHours() * 60 + now.getMinutes() >= h * 60 + m;
  });
  const nextSchoolDay = $derived(data?.next?.date ?? null);
  const nextIsTomorrow = $derived.by(() => {
    if (!nextSchoolDay || !data?.date) return false;
    const a = new Date(`${data.date}T00:00:00`), b = new Date(`${nextSchoolDay}T00:00:00`);
    return Math.round((b - a) / 86400000) === 1;
  });
  function feedbackSaved() { message = 'Rückmeldung gespeichert.'; }
  function taskSaved() { message = 'Aufgabe gespeichert.'; load(); }
</script>

<header class="day-title"><div><p class="eyebrow">{formatShortDate(data?.date ?? isoToday())}</p><h2>Dein Tag</h2></div><button class="ghost" onclick={() => load()} aria-label="Tagesübersicht aktualisieren">Aktualisieren</button></header>
{#if error}<div class="error-box" role="alert">{error} Bitte erneut aktualisieren; angezeigte Daten können veraltet sein.</div>{/if}
<p class="save-message" role="status">{message}</p>
{#if loading}<p>Lade deinen Tag …</p>{:else}
  {#if evening}
    <section class="day-section evening" data-section="aufgaben">
      <h3>{nextIsTomorrow ? 'Für morgen' : 'Für den nächsten Schultag'}</h3>
      {#each work.due as task (task.id)}<TaskRow {accountId} {task} onchange={taskSaved} onopen={t => editing = t} />{:else}
        <p class="all-clear"><span aria-hidden="true">✓</span> Keine Aufgabe mehr offen.</p>
      {/each}
      {#if nextSchoolDay}<div data-section="tasche"><PackingChecklist {accountId} schoolDay={nextSchoolDay} /></div>{:else}
        <p class="muted">In den nächsten Tagen steht keine Schule an.</p>
      {/if}
      {#if data?.retakes?.length}
        <!-- Unscharf oder abgeschnitten: ein neues Foto statt Gegenlesen durch die Eltern (D165). -->
        <h4 data-section="fotos">Bitte noch einmal fotografieren</h4>
        {#each data.retakes as r (r.id)}
          <p class="photo-request"><strong>{r.title}</strong> <span class="muted">· {r.reason}</span>
            <a href="#/materialien">neu fotografieren</a></p>
        {/each}
      {/if}
      {#if data?.photo_requests?.length}
        <!-- Nur vor einer Arbeit, höchstens drei Bitten, konkret mit Heft und Seite. -->
        <h4>Für die Arbeit brauche ich noch</h4>
        {#each data.photo_requests as need}
          <p class="photo-request"><strong>{need.subject}</strong> am {formatShortDate(need.exam_date)}: {need.label} {need.pages_label}
            <span class="muted">· „{need.quote}"</span>
            <a href="#/materialien">fotografieren</a></p>
        {/each}
      {/if}
    </section>
  {/if}
  {#if data && !evening}<AfternoonCheck {accountId} onchange={taskSaved} />{/if}
  {#if data}
    <section class="day-section school" class:school-done={!lessons.upcoming.length && !lessons.open.length}>
      <div class="section-head"><h3>{activeUpcoming.length ? 'In der Schule' : 'Dein Schultag'}</h3><a href="#/week"><ActionLabel label="Woche ansehen" /></a></div>
      {#if activeUpcoming.length}<p class="next-lesson"><strong>{activeUpcoming[0].subject_name || activeUpcoming[0].subject_short}</strong> · {activeUpcoming[0].start_hhmm}{#if activeUpcoming[0].room} · Raum {activeUpcoming[0].room}{/if}</p>{/if}
      {#if beforeSchool}<div data-section="tasche"><PackingChecklist {accountId} schoolDay={data.date} /></div>{/if}
      {#if !beforeSchool}{#each lessons.upcoming as lesson (lesson.id)}<LessonCard {accountId} {lesson} preview />{/each}{/if}
      {#if lessons.open.length}<h4 data-section="rueckmelden">Noch kurz zurückmelden · {lessons.open.length}</h4><p class="eyebrow">Wie gut hast du den Stoff verstanden?</p>
        {#each lessons.open as lesson (lesson.id)}<LessonCard {accountId} {lesson} onsaved={feedbackSaved} />{/each}
      {:else if data.lessons.length && !activeUpcoming.length}<p class="muted">Keine offenen Rückmeldungen zu beendeten Stunden.</p>
      {:else if !data.lessons.length}<p class="muted">Heute ist kein Unterricht eingetragen.</p>{/if}
      {#if lessons.history.length}<button class="text-action" aria-expanded={showHistory} onclick={() => showHistory = !showHistory}>{showHistory ? 'Verlauf schließen' : `Vergangene Stunden ansehen (${lessons.history.length})`}</button>
        {#if showHistory}{#each lessons.history as lesson (lesson.id)}<LessonCard {accountId} {lesson} onsaved={feedbackSaved} />{/each}{/if}
      {/if}
    </section>
  {/if}
  {#if !evening}<section class="day-section obligations" data-section="aufgaben">
    <div class="section-head"><h3>Heute erledigen</h3><button class="text-action" onclick={() => creating = true}>Aufgabe ergänzen</button></div>
    {#each work.due as task (task.id)}<TaskRow {accountId} {task} onchange={taskSaved} onopen={t => editing = t} />{:else}{#if error}<p>Aufgabenstand bitte aktualisieren.</p>{:else}<p class="all-clear"><span aria-hidden="true">🎉</span><strong>Für morgen ist nichts mehr offen!</strong></p>{/if}{/each}
  </section>
  {/if}
  {#if work.ahead.length}<details class="day-section fold" open={!evening}><summary><h3>Schon vorziehen</h3></summary>{#each work.ahead as task (task.id)}<TaskRow {accountId} {task} onchange={taskSaved} onopen={t => editing = t} />{/each}</details>{/if}
  {#if work.undated.length}<details class="day-section fold" open={!evening} data-section="ohne-termin"><summary><h3>Noch ohne Termin</h3></summary>{#each work.undated as task (task.id)}<TaskRow {accountId} {task} onchange={taskSaved} onopen={t => editing = t} />{/each}</details>{/if}
  <details class="day-section practice fold" open={!evening}>
    <summary><h3>Üben &amp; vorbereiten</h3></summary>
    <a class="exam-link" href="#/learning"><ActionLabel label="Zum Lernbereich" /></a>
    {#if planError}<p role="status">{planError}</p>{/if}
    {#each plan?.errors ?? [] as problem}<p class="muted">{problem}</p>{/each}
    {#each plan?.upcoming_exams ?? [] as exam}<a class="exam-link" href="#/klausuren">{exam.subject_name || exam.subject || exam.title || 'Arbeit'} · {formatShortDate(exam.date)} <ActionLabel /></a>{/each}
    {#each plan?.today?.actions ?? [] as item (item.key)}
      <LearningGoal goal={item}/>
    {:else}{#if !planError}<p class="muted">Heute ist keine zusätzliche Übung eingeplant.</p>{/if}{/each}
  </details>
  <!-- Abends steht dieselbe Liste bereits oben in der Karte für morgen. -->
  {#if data?.next && !evening}<section class="day-section tomorrow" data-section="tasche">
    <h3>Nächster Schultag · {formatShortDate(data.next.date)}</h3>
    <PackingChecklist {accountId} schoolDay={data.next.date} />
  </section>{/if}
  {#if work.done.length}<section class="day-section"><button class="text-action" aria-expanded={showDone} onclick={() => showDone = !showDone}>{showDone ? 'Erledigte Aufgaben schließen' : 'Erledigte Aufgaben ansehen'}</button>{#if showDone}{#each work.done as task (task.id)}<TaskRow {accountId} {task} onchange={taskSaved} onopen={t => editing = t} />{/each}{/if}</section>{/if}
{/if}
{#if editing}<TaskDetail {accountId} task={editing} onclose={() => editing = null} onsaved={taskSaved} />{/if}
{#if creating}<TaskEditor {accountId} task={null} onclose={() => creating = false} onsaved={taskSaved} />{/if}

<style>
  .all-clear{display:flex;align-items:center;gap:12px;padding:10px 0;margin:0}.all-clear>span{font-size:2rem}.all-clear strong{font-size:1rem;font-weight:550}
  .day-title,.section-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
  .day-title h2{margin:0;font-size:1.6rem}.eyebrow{color:var(--fg-muted);margin:0 0 8px;font-size:.9rem}
  .day-section{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:12px;margin:0 0 8px}
  .evening{border-color:var(--accent);background:var(--accent-soft)}
  .evening h3{margin-top:0}
  .evening h4{margin:12px 0 4px}
  .photo-request{margin:4px 0;overflow-wrap:anywhere}
  .photo-request a{display:inline-block;margin:-12px 0 -12px 6px;padding:12px 4px}
  .fold>summary{cursor:pointer;min-height:44px;display:flex;align-items:center;list-style:none}
  .fold>summary::-webkit-details-marker{display:none}
  .fold>summary h3{margin:0}
  .fold:not([open])>summary h3{opacity:.75;font-weight:600}
  h3{font-size:1.1rem;margin:0 0 8px}h4{margin:16px 0 8px}.section-head h3{margin:0}.section-head{margin-bottom:8px}
  .section-head>a,.text-action{font-size:.9rem}.text-action{padding:8px 0;background:transparent;border:0;color:var(--accent);text-align:left}
  .next-lesson{padding:10px 0;border-bottom:1px solid var(--border)}.save-message{min-height:1.3em;color:var(--accent);font-size:.9rem;margin:6px 0}
  .exam-link{display:block;padding:12px 0;border-bottom:1px solid var(--border)}
  .school-done{padding:8px 0;background:transparent;border:0;margin-bottom:8px}.school-done .section-head{margin-bottom:4px}.school-done p{margin:4px 0}.school-done h3{font-size:1rem}
  .school:not(.school-done){background:var(--school-soft)}.obligations{border-top:4px solid var(--accent)}.practice{background:var(--learn-soft)}
  .tomorrow{background:var(--accent-soft);border-left:4px solid var(--accent)}
  @media(max-width:380px){.day-section{padding:10px}}
</style>
