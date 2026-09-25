<script>
  // Startseite nach Phasen des Schultags (D171): vor, in und nach der Schule.
  // Das Layout bleibt, oben wechselt die Fokuskarte. Vier Bereiche je Schultag:
  // Aufgaben, Lernen (D180), Tasche, Feedback. „Geschafft“ (D172) verlangt alle vier.
  import ActionLabel from '../lib/ActionLabel.svelte';
  import LearningGoal from '../lib/LearningGoal.svelte';
  import { onMount, tick } from 'svelte';
  import { api, ApiError } from '../lib/api.js';
  import { isoToday, formatShortDate, daysBetween, stripUntisMetadata } from '../lib/format.js';
  import { splitTasks } from '../lib/dayDashboard.js';
  import { dayPhase, mergeLessons, held, lessonOver } from '../lib/dayPhase.js';
  import { subjectStyle } from '../lib/subjectStyle.js';
  import PackingChecklist from '../lib/PackingChecklist.svelte';
  import DaySchedule from '../lib/DaySchedule.svelte';
  import QuickAdd from '../lib/QuickAdd.svelte';
  import TaskRow from '../lib/TaskRow.svelte';
  import TaskDetail from '../lib/TaskDetail.svelte';
  import PracticePaper from '../lib/PracticePaper.svelte';
  import { profile } from '../lib/profile.svelte.js';
  import { view } from '../lib/viewMode.svelte.js';

  let { accountId } = $props();
  let data = $state(null), tasks = $state([]), plan = $state(null);
  let loading = $state(true), error = $state(''), planError = $state('');
  let editing = $state(null), now = $state(new Date());
  let showDone = $state(false), message = $state(''), bag = $state(null), todayBag = $state(null);
  let focusBusy = $state(false), celebrate = $state(false);
  let paperId = $state(null), stepBusy = $state(''), stepError = $state('');
  let request = 0;

  async function load(reset = false) {
    if (!accountId) return;
    const id = accountId, ticket = ++request;
    if (reset) { data = null; tasks = []; plan = null; editing = null; paperId = null; stepError = ''; showDone = false; message = ''; bag = null; todayBag = null; loading = true; }
    error = ''; planError = '';
    const results = await Promise.allSettled([
      api.get(`/api/accounts/${id}/today`), api.get(`/api/accounts/${id}/tasks?recent_done_days=14`), api.get(`/api/accounts/${id}/plan?compact=1`),
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
    const tick = () => { const oldDay = isoAt(now); now = new Date(); if (oldDay !== isoAt(now)) load(); };
    // Beim Zurückkehren feuern visibilitychange und focus oft beide; einmal
    // neu laden genügt (D177).
    let lastResume = 0;
    const resume = () => {
      if (document.hidden || Date.now() - lastResume < 3000) return;
      lastResume = Date.now(); now = new Date(); load();
    };
    const timer = setInterval(tick, 30000);
    document.addEventListener('visibilitychange', resume);
    window.addEventListener('focus', resume);
    return () => { clearInterval(timer); request++; document.removeEventListener('visibilitychange', resume); window.removeEventListener('focus', resume); };
  });
  function isoAt(d) { return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }

  const day = $derived(data?.date ?? isoToday());
  const nextSchoolDay = $derived(data?.next?.date ?? null);
  const ph = $derived(dayPhase(data?.lessons ?? [], now));
  const phase = $derived(ph.phase);
  const work = $derived(splitTasks(tasks, day, nextSchoolDay));
  const dueToday = $derived(work.due.filter(t => t.due_date <= day));
  // Aufgaben-Ring: alles, was bis zum nächsten Schultag fällig ist, dazu Überfälliges.
  const ringTasks = $derived(tasks.filter(t => t.due_date && t.due_date <= (nextSchoolDay || day) && (t.status !== 'done' || t.due_date >= day)));
  const openTasks = $derived(ringTasks.filter(t => t.status !== 'done'));
  // Rückmeldungen je Zeile gezählt: eine Doppelstunde ist eine Rückmeldung.
  const endedLessons = $derived(mergeLessons((data?.lessons ?? []).filter(l => held(l) && lessonOver(l, now))));
  const feedbackOpen = $derived(endedLessons.filter(g => g.lessons.some(l => l.checkin?.rating == null)).length);
  const notedToday = $derived(tasks.filter(t => t.source === 'manual' && (t.created_at || '').slice(0, 10) === day && t.status !== 'done'));
  // Lernen (D180): der eingefrorene Pflichtplan des Tages, erledigt live geprüft.
  const study = $derived(data?.study_plan ?? null);
  const learnSteps = $derived(study?.steps ?? []);
  const learnOpen = $derived(learnSteps.filter(s => !s.done).length);
  const nextStep = $derived(learnSteps.find(s => !s.done) ?? null);
  const afterSchool = $derived(phase === 'nach' || phase === 'frei');
  const done = $derived(afterSchool && !!data && !!nextSchoolDay && !openTasks.length && !learnOpen && !!bag?.packed && !feedbackOpen);
  const nextTask = $derived(openTasks[0] ?? null);
  const nextNotes = $derived(nextTask ? stripUntisMetadata(nextTask.notes) : '');
  const left = $derived(openTasks.length + learnOpen + (bag && !bag.packed ? 1 : 0) + (feedbackOpen ? 1 : 0));
  const tightText = $derived.by(() => {
    const t = study?.tight?.[0];
    if (!t) return '';
    const name = subjectStyle(t.subject || '').name;
    return study.free_day
      ? `Heute ist eigentlich frei. Bis zur Arbeit in ${name} am ${formatShortDate(t.exam_date)} ist aber nicht mehr viel Zeit, darum ein kleiner Schritt.`
      : `Die Arbeit in ${name} am ${formatShortDate(t.exam_date)} kommt bald. Ein Schritt am Tag reicht.`;
  });
  const firstGroup = $derived(ph.first ? mergeLessons((data?.lessons ?? []).filter(held))[0] : null);
  const currentGroup = $derived.by(() => {
    const target = ph.current || ph.next;
    if (!target) return null;
    return mergeLessons((data?.lessons ?? []).filter(held)).find(g => g.lessons.some(l => l.id === target.id)) ?? null;
  });
  // Die kurze Pause innerhalb einer Doppelstunde ist keine Pause.
  const groupRunning = $derived(!!currentGroup && (() => { const t = now.getHours() * 60 + now.getMinutes(); const m = (x) => Math.floor(x / 100) * 60 + x % 100; return m(currentGroup.start_time) <= t && t < m(currentGroup.end_time); })());
  const nextAfterCurrent = $derived.by(() => {
    if (!currentGroup) return null;
    const groups = mergeLessons((data?.lessons ?? []).filter(held));
    return groups[groups.indexOf(groups.find(g => g.key === currentGroup.key)) + 1] ?? null;
  });
  const cancelledCount = $derived((data?.lessons ?? []).filter(l => l.is_cancelled).length);
  const subjectNow = $derived.by(() => {
    const cur = ph.current || [...endedLessons].pop()?.lessons[0];
    return cur?.subject_name ?? null;
  });

  function dayWord(iso) {
    if (!iso) return '';
    const d = daysBetween(day, iso);
    return d === 0 ? 'heute' : d === 1 ? 'morgen' : formatShortDate(iso);
  }
  const WEEKDAYS = ['Sonntag','Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag'];
  const weekday = $derived(WEEKDAYS[new Date(day + 'T12:00:00').getDay()]);
  const subtitle = $derived.by(() => {
    if (!data) return formatShortDate(day);
    if (phase === 'vor') return `${formatShortDate(day)} · Schule ${ph.first.start_hhmm} bis ${ph.last.end_hhmm}`;
    if (phase === 'in') return `In der Schule · Schluss ${ph.last.end_hhmm}`;
    if (phase === 'nach') return done ? 'Alles erledigt. Freizeit!' : `Schule vorbei um ${ph.last.end_hhmm}`;
    return nextSchoolDay ? `Heute frei · nächster Schultag ${dayWord(nextSchoolDay)}` : 'Heute frei';
  });
  const groupName = (g) => { const s = subjectStyle(g.lessons[0].subject_name || g.lessons[0].subject_short); return `${s.emoji} ${s.name}`; };
  const roomChip = (g) => { const l = g.lessons[0]; return l.is_room_substituted && l.room_orig ? { warn: true, text: `Raum ${l.room} statt ${l.room_orig}` } : l.room ? { warn: false, text: `Raum ${l.room}` } : null; };

  // Serie und neue Abzeichen für die Geschafft-Karte (D173).
  let gains = $state(null);
  $effect(() => {
    if (!done || !accountId) { gains = null; return; }
    const id = accountId;
    api.get(`/api/accounts/${id}/rewards`).then((r) => { if (id === accountId && r?.streak) gains = r; }).catch(() => {});
  });
  // Der Moment „Geschafft“: einmal am Tag, mit kurzer Freude (D173).
  $effect(() => {
    if (!done || !accountId) return;
    const key = `geschafft:${accountId}:${day}`;
    try { if (localStorage.getItem(key)) return; localStorage.setItem(key, '1'); } catch { /* ohne Speicher trotzdem feiern */ }
    celebrate = true;
    const t = setTimeout(() => (celebrate = false), 2600);
    return () => clearTimeout(t);
  });
  const reduceMotion = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const confetti = Array.from({ length: 36 }, (_, i) => ({ left: (i * 37) % 100, delay: (i % 7) * 0.06, dur: 1.2 + (i % 5) * 0.18, hue: ['var(--accent)', '#f2c14e', 'var(--st-sitzt)', 'var(--st-wackelt)', '#6b3fc4'][i % 5] }));

  async function finishTask(task) {
    if (focusBusy) return;
    focusBusy = true; message = '';
    try { await api.patch(`/api/tasks/${task.id}`, { status: 'done' }); task.status = 'done'; saved(); }
    catch (e) { message = e instanceof ApiError ? e.message : 'Nicht gespeichert.'; }
    finally { focusBusy = false; }
  }
  function saved(text = '') { message = text; load(); }
  // Ein Papier-Schritt startet die Übungsarbeit direkt (D178). Ist heute für
  // diesen Schritt schon eine erstellt und noch offen, geht sie wieder auf.
  async function startStep(s) {
    if (s.kind !== 'paper') { if (s.href) location.hash = s.href; return; }
    if (stepBusy) return;
    stepBusy = s.key; stepError = '';
    const id = accountId;
    try {
      const r = await api.get(`/api/accounts/${id}/practice?exam_key=${encodeURIComponent(s.exam_key)}`);
      const open = (r.papers ?? []).find(p => p.paper_format === s.format && p.attempt_id && p.status !== 'graded' && (p.created_at || '').slice(0, 10) === day);
      if (open) paperId = open.attempt_id;
      else {
        const a = await api.post(`/api/accounts/${id}/practice`, { exam_key: s.exam_key, format: s.format, topic_ids: s.topic_id ? [s.topic_id] : [], level: s.level ?? null });
        paperId = a.id;
      }
      await tick(); jump('s-lernen');
    } catch (e) { stepError = e instanceof ApiError ? e.message : 'Die Übungsarbeit konnte nicht geöffnet werden.'; }
    finally { stepBusy = ''; }
  }
  // Erledigte Bereiche klappen sich zu (D187); von Hand Aufgeklapptes bleibt bis zum Abend offen.
  function readOpened() {
    try { const v = JSON.parse(localStorage.getItem('today-open') || '{}'); return v.day === isoToday() ? (v.keys || {}) : {}; }
    catch { return {}; }
  }
  let opened = $state(readOpened());
  function setOpen(key, value) {
    opened = { ...opened, [key]: value };
    try { localStorage.setItem('today-open', JSON.stringify({ day: isoToday(), keys: opened })); } catch { /* nur Komfort */ }
  }
  const finished = $derived({
    's-aufgaben': !openTasks.length, 's-lernen': !learnOpen && !paperId,
    's-tasche': !!bag?.packed, 's-stunden': !feedbackOpen,
  });
  const folded = (key) => !!finished[key] && !opened[key];
  async function jump(id) {
    if (folded(id)) { setOpen(id, true); await tick(); }
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  const ringStyle = (d, n) => `background:conic-gradient(var(--accent) ${n ? Math.round(d / n * 100) : 0}%, var(--bg-elevated) 0)`;
</script>

{#if celebrate && !reduceMotion && (profile.prefs.joy ?? 'konfetti') === 'konfetti'}<div class="confetti" aria-hidden="true">{#each confetti as c}<span style="left:{c.left}%;background:{c.hue};animation-delay:{c.delay}s;animation-duration:{c.dur}s"></span>{/each}</div>{/if}
<header class="day-title"><h2>{weekday}</h2><p>{subtitle}</p></header>
{#if error}<div class="error-box" role="alert">{error} Angezeigte Daten können veraltet sein.</div>{/if}
<p class="save-message" role="status">{message}</p>

{#if loading}<p class="muted">Lade deinen Tag …</p>{:else if data}
  <!-- Fokuskarte: das Anliegen des Moments. -->
  {#if done}
    <section class="focus done-card" class:still={profile.prefs.joy === 'still'}>
      <span class="big-ring" aria-hidden="true"><span>✓</span></span>
      <strong class="focus-big">Geschafft. Freizeit!</strong>
      <span>Alles für {dayWord(nextSchoolDay)} ist erledigt.</span>
      <span class="done-list">Aufgaben erledigt · Lernen erledigt · Tasche gepackt · Stunden zurückgemeldet</span>
      {#if gains}
        <span class="gains">
          <span><b>🔥 {gains.streak.current}</b>{gains.streak.current === 1 ? 'Tag' : 'Tage'} Serie</span>
          <span><b>{gains.total}</b>geschafft</span>
          <span><b>{gains.today.bonus ? '⚡' : '✓'}</b>{gains.today.bonus ? 'Frühstarter' : gains.today.kind === 'rescued' ? 'gerettet' : 'heute'}</span>
        </span>
        {#each gains.reached_today ?? [] as n}<a class="new-badge" href="#/ich">Neues Abzeichen · {gains.badges.find((b) => b.key === n.badge)?.emoji} {gains.badges.find((b) => b.key === n.badge)?.name}</a>{/each}
      {/if}
    </section>
  {:else if phase === 'vor' && firstGroup}
    <section class="focus">
      <span class="focus-k">Erste Stunde · {firstGroup.start_hhmm}</span>
      <strong class="focus-big">{groupName(firstGroup)}{firstGroup.lessons.length > 1 ? `, ${firstGroup.lessons.length} Stunden` : ''}</strong>
      <span class="chips">
        {#if roomChip(firstGroup)}<span class="chip" class:warn={roomChip(firstGroup).warn}>{roomChip(firstGroup).text}</span>{/if}
        <span class="chip">Schluss {ph.last.end_hhmm}</span>
        {#if cancelledCount}<span class="chip">{cancelledCount === 1 ? '1 Stunde fällt aus' : `${cancelledCount} Stunden fallen aus`}</span>{/if}
      </span>
    </section>
  {:else if phase === 'in' && currentGroup}
    <section class="focus">
      <span class="focus-k">{groupRunning ? `Jetzt · bis ${currentGroup.end_hhmm}` : `Pause · gleich ${currentGroup.start_hhmm}`}</span>
      <strong class="focus-big">{groupName(currentGroup)}{roomChip(currentGroup) && !roomChip(currentGroup).warn ? `, ${roomChip(currentGroup).text}` : ''}</strong>
      <span class="chips">
        {#if roomChip(currentGroup)?.warn}<span class="chip warn">{roomChip(currentGroup).text}</span>{/if}
        {#if nextAfterCurrent}<span class="chip">danach {nextAfterCurrent.start_hhmm} {subjectStyle(nextAfterCurrent.lessons[0].subject_name).name}{nextAfterCurrent.lessons[0].room ? `, Raum ${nextAfterCurrent.lessons[0].room}` : ''}</span>{:else}<span class="chip">danach Schluss</span>{/if}
      </span>
    </section>
  {:else if afterSchool && (left || !nextSchoolDay)}
    <section class="focus">
      {#if !nextSchoolDay}
        <span class="focus-k">Frei</span><strong class="focus-big">In den nächsten Tagen ist keine Schule.</strong>
      {:else}
        <span class="focus-k">{phase === 'frei' ? `Für ${dayWord(nextSchoolDay)}` : 'Nach der Schule'} · noch {left} bis zur Freizeit</span>
        {#if nextTask}
          <!-- Wie in der Aufgabenliste: Fach oder Titel, darunter die Notiz ohne UNTIS-Angaben; Tippen öffnet das Detail. -->
          <button class="focus-task" onclick={() => (editing = nextTask)}>
            <strong class="focus-big clamp">{nextTask.task_type === 'reminder' ? '📌' : subjectStyle(nextTask.subject_name || nextTask.title).emoji} {nextTask.title}</strong>
            {#if nextNotes}<span class="focus-note clamp">{nextNotes}</span>{/if}
          </button>
          <span class="focus-actions">
            <button class="on-accent" disabled={focusBusy} onclick={() => finishTask(nextTask)}>Erledigt ✓</button>
            {#if nextTask.task_type !== 'reminder'}<a class="on-accent-link" href={`#/learning?help=${nextTask.id}`}><ActionLabel kind="chat" label="Hilfe holen" /></a>{/if}
          </span>
        {:else if nextStep}
          <strong class="focus-big clamp">{nextStep.title}</strong>
          <span class="focus-note">{nextStep.why}</span>
          {#if !study.read_only}<span class="focus-actions"><button class="on-accent" disabled={!!stepBusy} onclick={() => startStep(nextStep)}>Los</button></span>{/if}
        {:else}
          <strong class="focus-big">Aufgaben erledigt. Noch {bag && !bag.packed ? 'die Tasche' : ''}{bag && !bag.packed && feedbackOpen ? ' und ' : ''}{feedbackOpen ? 'die Rückmeldungen' : ''}.</strong>
        {/if}
      {/if}
    </section>
  {/if}

  {#if afterSchool && nextSchoolDay}
    <div class="rings">
      <button class="ring-btn" class:full={!openTasks.length} onclick={() => jump('s-aufgaben')}><span class="ring" style={ringStyle(ringTasks.length - openTasks.length, ringTasks.length)}><span>{!openTasks.length ? '✓' : '📚'}</span></span><b>Aufgaben</b><small>{ringTasks.length - openTasks.length} von {ringTasks.length}</small></button>
      <button class="ring-btn" class:full={!learnOpen} onclick={() => jump('s-lernen')}><span class="ring" style={ringStyle(learnSteps.length - learnOpen, learnSteps.length)}><span>{!learnOpen ? '✓' : '🧠'}</span></span><b>Lernen</b><small>{learnSteps.length ? `${learnSteps.length - learnOpen} von ${learnSteps.length}` : 'frei'}</small></button>
      <button class="ring-btn" class:full={bag?.packed} onclick={() => jump('s-tasche')}><span class="ring" style={ringStyle(bag?.done ?? 0, bag?.total ?? 0)}><span>{bag?.packed ? '✓' : '🎒'}</span></span><b>Tasche</b><small>{bag ? `${bag.done} von ${bag.total}` : '…'}</small></button>
      <button class="ring-btn" class:full={!feedbackOpen} onclick={() => jump('s-stunden')}><span class="ring" style={ringStyle(endedLessons.length - feedbackOpen, endedLessons.length)}><span>{!feedbackOpen ? '✓' : '💬'}</span></span><b>Feedback</b><small>{endedLessons.length - feedbackOpen} von {endedLessons.length}</small></button>
    </div>
  {/if}

  {#if phase === 'in'}
    <QuickAdd {accountId} {day} lessons={data.lessons} defaultSubject={subjectNow} nextBySubject={data.next_by_subject ?? {}} {nextSchoolDay} startOpen onsaved={saved} />
  {/if}

  {#if phase === 'vor' || phase === 'in'}
    <section class="sec" data-section="stundenplan">
      <h3>Dein Tag{#if phase === 'in'} <small>😀 nach jeder Stunde</small>{/if}</h3>
      <DaySchedule {accountId} lessons={data.lessons} {now} onsaved={() => saved('Rückmeldung gespeichert.')} />
    </section>
    {#if learnSteps.length}
      <p class="learn-line" data-section="lernen-kurz"><b>Heute lernen:</b> {learnSteps.map(s => s.title).join(' · ')}</p>
    {/if}
    {#if phase === 'vor'}
      <section class="sec" data-section="tasche">
        <h3>Dabei? <small>{todayBag?.packed ? '✓ alles drin' : 'Tasche für heute'}</small></h3>
        <PackingChecklist {accountId} schoolDay={day} variant="grid" onstatus={(s) => (todayBag = s)} />
      </section>
    {/if}
    {#if phase === 'in' && notedToday.length}
      <section class="sec">
        <h3>Heute notiert <small>{notedToday.length}</small></h3>
        <div class="list">{#each notedToday as task (task.id)}<TaskRow {accountId} {task} onchange={() => saved()} onopen={t => editing = t} />{/each}</div>
      </section>
    {/if}
    {#if dueToday.length}
      <section class="sec" data-section="aufgaben">
        <h3>Heute abgeben <small>{dueToday.length}</small></h3>
        <div class="list">{#each dueToday as task (task.id)}<TaskRow {accountId} {task} onchange={() => saved()} onopen={t => editing = t} />{/each}</div>
      </section>
    {/if}
  {/if}

  {#if afterSchool && nextSchoolDay}
    <section class="sec" id="s-aufgaben" data-section="aufgaben">
      {#if finished['s-aufgaben']}<button class="fold-head" onclick={() => setOpen('s-aufgaben', folded('s-aufgaben'))} aria-expanded={!folded('s-aufgaben')}><span>✓ Aufgaben bis {dayWord(nextSchoolDay)}</span><small>{ringTasks.length - openTasks.length} von {ringTasks.length} {folded('s-aufgaben') ? '▸' : '▾'}</small></button>{:else}<h3>Aufgaben bis {dayWord(nextSchoolDay)} <small>{ringTasks.length - openTasks.length} von {ringTasks.length}</small></h3>{/if}
      <QuickAdd {accountId} {day} lessons={data.lessons} defaultSubject={subjectNow} nextBySubject={data.next_by_subject ?? {}} {nextSchoolDay} onsaved={saved} />
      {#if !folded('s-aufgaben')}
      <div class="list">
        {#each work.due as task (task.id)}<TaskRow {accountId} {task} onchange={() => saved()} onopen={t => editing = t} />
        {:else}<p class="all-clear">✓ Keine Aufgabe offen.</p>{/each}
      </div>
      {/if}
    </section>
    <section class="sec" id="s-lernen" data-section="lernen">
      {#if finished['s-lernen']}<button class="fold-head" onclick={() => setOpen('s-lernen', folded('s-lernen'))} aria-expanded={!folded('s-lernen')}><span>✓ Lernen</span><small>{learnSteps.length ? `${learnSteps.length - learnOpen} von ${learnSteps.length}` : 'heute frei'} {folded('s-lernen') ? '▸' : '▾'}</small></button>{:else}<h3>Lernen <small>{learnSteps.length ? `${learnSteps.length - learnOpen} von ${learnSteps.length}` : 'heute frei'}</small></h3>{/if}
      {#if folded('s-lernen')}
      {:else if paperId}
        <PracticePaper {accountId} attemptId={paperId} backLabel="Zurück zu Heute" onclose={() => { paperId = null; load(); }} />
      {:else}
        {#if tightText}<p class="learn-hint">{tightText}</p>{/if}
        <div class="list">
          {#each learnSteps as s (s.key)}
            <div class="learn-step" class:done={s.done}>
              <span class="learn-check" class:checked={s.done} aria-hidden="true">{s.done ? '✓' : ''}</span>
              <span class="learn-body"><strong>{s.title}</strong><small>{s.why}</small></span>
              {#if s.done}<span class="learn-state">erledigt</span>{:else if !study?.read_only}<button class="primary learn-go" disabled={!!stepBusy} onclick={() => startStep(s)}>{stepBusy === s.key ? 'Wird erstellt …' : 'Los'}</button>{/if}
            </div>
          {:else}<p class="all-clear">✓ Heute ist nichts zum Lernen Pflicht.</p>{/each}
        </div>
        {#if stepError}<p class="error-box" role="alert">{stepError}</p>{/if}
      {/if}
    </section>
    <section class="sec" id="s-tasche" data-section="tasche">
      {#if finished['s-tasche']}<button class="fold-head" onclick={() => setOpen('s-tasche', folded('s-tasche'))} aria-expanded={!folded('s-tasche')}><span>✓ Tasche für {WEEKDAYS[new Date(nextSchoolDay + 'T12:00:00').getDay()]}</span><small>{bag?.packed ? 'alles drin' : 'antippen, wenn drin'} {folded('s-tasche') ? '▸' : '▾'}</small></button>{:else}<h3>Tasche für {WEEKDAYS[new Date(nextSchoolDay + 'T12:00:00').getDay()]} <small>{bag?.packed ? 'alles drin' : 'antippen, wenn drin'}</small></h3>{/if}
      <div class:hidden-fold={folded('s-tasche')}><PackingChecklist {accountId} schoolDay={nextSchoolDay} variant="grid" onstatus={(s) => (bag = s)} /></div>
    </section>
    {#if endedLessons.length || (data.lessons ?? []).length}
      <section class="sec" id="s-stunden" data-section="rueckmelden">
        {#if finished['s-stunden']}<button class="fold-head" onclick={() => setOpen('s-stunden', folded('s-stunden'))} aria-expanded={!folded('s-stunden')}><span>✓ Stunden von heute</span><small>{endedLessons.length - feedbackOpen} von {endedLessons.length} {folded('s-stunden') ? '▸' : '▾'}</small></button>{:else}<h3>Stunden von heute <small>{endedLessons.length - feedbackOpen} von {endedLessons.length}</small></h3>{/if}
        {#if !folded('s-stunden')}<DaySchedule {accountId} lessons={data.lessons} {now} live={false} onsaved={() => saved('Rückmeldung gespeichert.')} />{/if}
      </section>
    {/if}
    {#if data.retakes?.length || data.photo_requests?.length}
      <section class="sec" data-section="fotos">
        <h3>Fotos</h3>
        <div class="list pad">
          {#each data.retakes ?? [] as r (r.id)}
            <p class="photo-request"><strong>{r.source_page ? `${r.source_label || 'Buch'} S. ${r.source_page}` : r.title}</strong>{#if r.spot} · „{r.spot}“{/if} <span class="muted">· {r.reason}</span>{#if view.mode !== 'mirror'} <a href="#/materialien?s=fotos">neu fotografieren</a>{/if}</p>
          {/each}
          {#each data.photo_requests ?? [] as need}
            <p class="photo-request"><strong>{need.subject}</strong> für die Arbeit am {formatShortDate(need.exam_date)}: {need.label} {need.pages_label}{#if view.mode !== 'mirror'} <a href="#/materialien">fotografieren</a>{/if}</p>
          {/each}
        </div>
      </section>
    {/if}
  {/if}

  {#if phase === 'frei' && !nextSchoolDay}
    <section class="sec"><QuickAdd {accountId} {day} lessons={[]} nextBySubject={data.next_by_subject ?? {}} {nextSchoolDay} onsaved={saved} /></section>
  {/if}

  <details class="fold" open={done} data-section="ohne-termin">
    <summary><h3>Wenn du magst</h3><small>{work.ahead.length + work.undated.length ? `${work.ahead.length + work.undated.length} für später · ` : ''}Üben</small></summary>
    {#each work.ahead as task (task.id)}<TaskRow {accountId} {task} onchange={() => saved()} onopen={t => editing = t} />{/each}
    {#each work.undated as task (task.id)}<TaskRow {accountId} {task} onchange={() => saved()} onopen={t => editing = t} />{/each}
    {#if planError}<p role="status" class="muted">{planError}</p>{/if}
    {#each plan?.upcoming_exams ?? [] as exam}<a class="exam-link" href="#/klausuren">{subjectStyle(exam.subject_name || exam.subject || exam.title || 'Arbeit').name} · {formatShortDate(exam.date)} <ActionLabel /></a>{/each}
    {#each plan?.today?.actions ?? [] as item (item.key)}<LearningGoal goal={item} />{/each}
    <a class="exam-link" href="#/learning"><ActionLabel label="Zum Lernbereich" /></a>
  </details>

  {#if work.done.length}
    <button class="text-action" aria-expanded={showDone} onclick={() => showDone = !showDone}>{showDone ? 'Erledigte ausblenden' : 'Erledigte ansehen'}</button>
    {#if showDone}<div class="list">{#each work.done as task (task.id)}<TaskRow {accountId} {task} onchange={() => saved()} onopen={t => editing = t} />{/each}</div>{/if}
  {/if}
{/if}
{#if editing}<TaskDetail {accountId} task={editing} onclose={() => editing = null} onsaved={() => saved('Aufgabe gespeichert.')} />{/if}

<style>
  .day-title{padding:var(--sp-1) 0 var(--sp-2)}
  .day-title h2{margin:0;font-size:var(--fs-xl);letter-spacing:-.01em}
  .day-title p{margin:2px 0 0;color:var(--fg-muted);font-size:var(--fs-sm)}
  .save-message{min-height:1.2em;color:var(--accent);font-size:var(--fs-sm);margin:0 0 var(--sp-1)}
  .focus{background:var(--accent);color:var(--accent-fg);border-radius:var(--r-lg);padding:var(--sp-4);display:grid;gap:var(--sp-2);margin-bottom:var(--sp-3);position:relative;overflow:hidden}
  .focus::after{content:"";position:absolute;right:-40px;top:-50px;width:150px;height:150px;border-radius:50%;background:rgba(255,255,255,.08);pointer-events:none}
  .focus-k{font-size:.7rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;opacity:.85}
  .focus-big{font-size:var(--fs-lg);font-weight:800;line-height:1.25;overflow-wrap:anywhere}
  .chips{display:flex;flex-wrap:wrap;gap:6px}
  .chip{background:rgba(255,255,255,.18);border-radius:var(--r-pill);padding:3px 10px;font-size:var(--fs-xs);font-weight:600}
  .chip.warn{background:#fff;color:#a65606}
  .focus-actions{display:flex;gap:var(--sp-2);align-items:center;flex-wrap:wrap;position:relative;z-index:1}
  .on-accent{background:var(--accent-fg);color:var(--accent);border:0;font-weight:800;border-radius:var(--r-md)}
  .on-accent-link{color:var(--accent-fg);font-weight:700;padding:10px 4px;min-height:44px;display:inline-flex;align-items:center}
  .focus-task{display:grid;gap:4px;text-align:left;background:transparent;border:0;padding:0;color:inherit;min-height:44px;position:relative;z-index:1}
  .focus-note{font-size:var(--fs-sm);opacity:.9;overflow-wrap:anywhere}
  .clamp{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;line-clamp:3;overflow:hidden}
  .focus-note.clamp{-webkit-line-clamp:2;line-clamp:2}
  .done-list{font-size:var(--fs-xs);opacity:.9}
  .learn-line{margin:var(--sp-3) 0 0;font-size:var(--fs-sm);overflow-wrap:anywhere}
  .learn-hint{margin:0 0 var(--sp-2);padding:var(--sp-2) var(--sp-3);background:var(--bg-elevated);border-radius:var(--r-md);font-size:var(--fs-sm)}
  .learn-step{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:var(--sp-2);align-items:center;padding:var(--sp-2) 0;border-bottom:1px solid var(--border)}
  .learn-step:last-child{border-bottom:0}
  .learn-check{width:24px;height:24px;border-radius:50%;border:2px solid var(--border);display:grid;place-items:center;font-weight:800;font-size:.8rem}
  .learn-check.checked{background:var(--accent);border-color:var(--accent);color:var(--accent-fg)}
  .learn-body{display:grid;gap:2px;overflow-wrap:anywhere}
  .learn-body small{color:var(--fg-muted);font-size:var(--fs-xs)}
  .learn-step.done .learn-body strong{color:var(--fg-muted)}
  .learn-state{font-size:var(--fs-xs);color:var(--good-fg);font-weight:700}
  .learn-go{min-height:44px;min-width:64px}
  .done-card{text-align:center;justify-items:center;animation:rise .45s}
  .done-card.still{animation:none}
  .big-ring{width:84px;height:84px;border-radius:50%;background:var(--accent-fg);display:grid;place-items:center}
  .big-ring span{width:64px;height:64px;border-radius:50%;background:var(--accent);color:var(--accent-fg);display:grid;place-items:center;font-size:1.8rem;font-weight:800}
  @keyframes rise{from{transform:translateY(8px);opacity:.4}to{transform:none;opacity:1}}
  .gains{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;width:100%}
  .gains span{background:rgba(255,255,255,.15);border-radius:var(--r-md);padding:var(--sp-2) 4px;font-size:.72rem;display:grid}
  .gains b{font-size:var(--fs-md)}
  .new-badge{background:var(--accent-fg);color:var(--accent);border-radius:var(--r-pill);padding:6px 12px;font-weight:700;font-size:var(--fs-xs)}
  .rings{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--sp-2);margin-bottom:var(--sp-2)}
  .ring-btn{display:grid;justify-items:center;gap:3px;padding:var(--sp-2) 4px;border-radius:var(--r-md);min-height:100px;background:var(--bg-card)}
  .ring{width:50px;height:50px;border-radius:50%;display:grid;place-items:center}
  .ring span{width:39px;height:39px;border-radius:50%;background:var(--bg-card);display:grid;place-items:center;font-size:1.1rem}
  .ring-btn.full .ring span{background:var(--accent);color:var(--accent-fg);font-weight:800}
  .ring-btn b{font-size:var(--fs-xs)}.ring-btn small{font-size:.72rem;color:var(--fg-muted)}
  .sec{margin-top:var(--sp-4)}
  .fold-head{width:100%;display:flex;justify-content:space-between;align-items:center;gap:var(--sp-2);min-height:44px;padding:var(--sp-2) var(--sp-3);background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-md);color:var(--fg);font-weight:700;font-size:var(--fs-md);text-align:left;margin-bottom:var(--sp-2)}
  .fold-head span{color:var(--good-fg, var(--fg))}
  .fold-head small{font-weight:600;color:var(--fg-muted);font-size:var(--fs-xs);white-space:nowrap}
  .hidden-fold{display:none}
  .sec h3,.fold h3{font-size:var(--fs-md);margin:0 0 var(--sp-2);display:flex;justify-content:space-between;align-items:baseline;gap:var(--sp-2)}
  .sec h3 small,.fold summary small{font-weight:600;color:var(--fg-muted);font-size:var(--fs-xs)}
  .list{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-md);padding:0 var(--sp-3)}
  .list.pad{padding:var(--sp-2) var(--sp-3)}
  .all-clear{margin:0;padding:var(--sp-3) 0;color:var(--good-fg);font-weight:600}
  .photo-request{margin:4px 0;overflow-wrap:anywhere;font-size:var(--fs-sm)}
  .fold{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-md);padding:var(--sp-2) var(--sp-3);margin-top:var(--sp-4)}
  .fold>summary{cursor:pointer;min-height:44px;display:flex;align-items:center;gap:var(--sp-2)}
  .fold>summary h3{margin:0}
  .exam-link{display:block;padding:var(--sp-3) 0;border-bottom:1px solid var(--border)}
  .text-action{margin-top:var(--sp-3);padding:8px 0;background:transparent;border:0;color:var(--accent);font-size:var(--fs-sm)}
  .confetti{position:fixed;inset:0;pointer-events:none;overflow:hidden;z-index:60}
  .confetti span{position:absolute;top:-14px;width:8px;height:13px;border-radius:2px;animation:fall 1.6s ease-in forwards}
  @keyframes fall{to{transform:translateY(105vh) rotate(540deg);opacity:.2}}
</style>
