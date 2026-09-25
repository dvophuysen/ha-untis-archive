<script>
  // Lernen als Kompass (D186). Die Seite des Kindes beantwortet von oben nach
  // unten: Wo stehe ich? Was ist heute Pflicht, und warum? Was ist meine Stärke,
  // was meine Baustelle? Was kann ich freiwillig tun? Wie hat sich mein Lernen
  // entwickelt? Ein schlanker Aufruf (/learning/compass), kein Modell.
  // Mitlesen und Kindmodus sehen genau diese Seite; Schreiben weist dann der
  // Server ab, deshalb fehlen die Knöpfe (can_write).
  import { untrack, tick } from 'svelte';
  import { api, ApiError } from '../lib/api.js';
  import { formatShortDate } from '../lib/format.js';
  import { subjectStyle } from '../lib/subjectStyle.js';
  import ActionLabel from '../lib/ActionLabel.svelte';
  import MentorSession from '../lib/MentorSession.svelte';
  import PracticePaper from '../lib/PracticePaper.svelte';
  import MentorExams from '../lib/MentorExams.svelte';
  import { queryOf, opensSession, openFromQuery, clearQuery } from '../lib/learningQuery.js';

  let { accountId, nav = { hash: '' } } = $props();
  const base = $derived(`/api/accounts/${accountId}/learning/mentor`);
  let data = $state(null), error = $state(''), busy = $state(false);
  let running = $state(null), paperId = $state(null), examsView = $state(null);
  let stepBusy = $state(''), openExam = $state(''), pick = $state(''), newTopic = $state(false);

  async function load() { data = await api.get(`/api/accounts/${accountId}/learning/compass`); }
  async function act(fn) {
    if (busy) return;
    busy = true; error = '';
    try { await fn(); } catch (e) { error = e instanceof ApiError ? e.message : (e?.message || 'Das hat nicht geklappt.'); }
    finally { busy = false; }
  }
  // Die Adresse bei jedem Wechsel auswerten, nicht nur beim ersten Laden (D186):
  // Links innerhalb der Lernseite („Los“, „Angehen“, Stundenthemen) wirken so.
  async function follow(h) {
    if (!data) await load();
    const q = queryOf(h);
    // Direkt zu einer ausgewerteten Übungsarbeit, etwa vom Hinweis auf „Heute“ (D201).
    if (q.get('paper')) {
      running = null; examsView = null;
      paperId = Number(q.get('paper'));
      clearQuery();
      window.scrollTo?.(0, 0);
      return;
    }
    if (opensSession(q)) {
      paperId = null; examsView = null;
      running = await openFromQuery(api, base, q);
      clearQuery();
      window.scrollTo?.(0, 0);
      return;
    }
    const subject = q.get('subject');
    if (subject) {
      pick = data?.extra.find((s) => s.name === subject || s.label === subject)?.name || '';
      if (q.get('mode') === 'exam') examsView = { subject, topic: q.get('topic') || '' };
    }
    // Alte Lernplan-Links (?goal=) führen auf die Übersicht; der Plan heißt jetzt „Heute Pflicht“.
    if (subject || q.get('goal')) clearQuery();
  }
  $effect(() => { const h = nav.hash; untrack(() => act(() => follow(h))); });

  async function back() { running = null; paperId = null; examsView = null; await load(); }
  function go(href) { if (href) window.location.hash = href; }

  // Ein Papier-Schritt startet die Übungsarbeit direkt, wie auf „Heute“ (D178):
  // Ist heute für diesen Schritt schon eine erstellt und noch offen, geht sie wieder auf.
  async function startStep(s) {
    if (s.kind !== 'paper') { go(s.href); return; }
    if (s.attempt_id) { paperId = s.attempt_id; await tick(); window.scrollTo?.(0, 0); return; }
    if (stepBusy) return;
    stepBusy = s.key; error = '';
    try {
      const r = await api.get(`/api/accounts/${accountId}/practice?exam_key=${encodeURIComponent(s.exam_key)}`);
      const open = (r.papers ?? []).find((p) => p.paper_format === s.format && p.attempt_id && p.status !== 'graded' && (p.created_at || '').slice(0, 10) === data.day);
      paperId = open ? open.attempt_id
        : (await api.post(`/api/accounts/${accountId}/practice`, { exam_key: s.exam_key, format: s.format, topic_ids: s.topic_id ? [s.topic_id] : [], level: s.level ?? null })).id;
      await tick(); window.scrollTo?.(0, 0);
    } catch (e) { error = e instanceof ApiError ? e.message : 'Die Übungsarbeit konnte nicht geöffnet werden.'; }
    finally { stepBusy = ''; }
  }

  const chosen = $derived(data?.extra.find((s) => s.name === pick) ?? null);
  async function explain() { running = await api.post(`${base}/sessions`, { subject: chosen.name, goal: '', minutes: 10, voluntary: true }); }
  // Kurztest: zur Arbeit dieses Fachs, falls eine ansteht, sonst eine freie Übungsarbeit.
  async function quiz() {
    if (chosen.exam_key) {
      const a = await api.post(`/api/accounts/${accountId}/practice`, { exam_key: chosen.exam_key, format: 'kurz', topic_ids: [], level: null });
      paperId = a.id;
    } else examsView = { subject: chosen.name, topic: '' };
  }
  async function openSession(s) { running = await api.get(`${base}/sessions/${s.id}`); }
  async function unarchive(s) { await api.post(`${base}/sessions/${s.id}/unarchive`, {}); await openSession(s); }

  const CELL = { offen: ['neu', 'offen'], unsicher: ['wackelt', 'unsicher'], fast: ['angefangen', 'fast'], sicher: ['sitzt', 'sicher'], bestaetigt: ['gefestigt', 'bestätigt'] };
  const ROMAN = { 1: 'I', 2: 'II', 3: 'III' };
  const DOT = { neu: 'noch offen', angefangen: 'angefangen', wackelt: 'wackelt', sitzt: 'sicher', gefestigt: 'bestätigt' };
  const subj = (name) => subjectStyle(name);
  function daysText(e) {
    if (e.days === 0) return 'heute';
    if (e.days === 1) return 'morgen';
    return `noch ${e.school_days_left} ${e.school_days_left === 1 ? 'Schultag' : 'Schultage'}`;
  }
  function when(iso) { return iso ? `${formatShortDate(iso.slice(0, 10))} ${iso.slice(11, 16)}` : ''; }
  const plan = $derived(data?.plan ?? { steps: [], total: 0, done: 0, read_only: true });
  const canGo = $derived(!!data?.can_write && !plan.read_only);
  const n = $derived(data?.next_exam ?? null);
  const earlierCount = $derived((data?.past_exams?.length ?? 0) + (data?.archived_sessions?.length ?? 0));
</script>

{#if error}<p class="error-box" role="alert">{error}</p>{/if}
{#if running}
  <MentorSession {accountId} bind:running canWrite={!!data?.can_write} canManage={false} speech={!!data?.speech} onleave={back} onreload={load} />
{:else if paperId}
  <PracticePaper {accountId} attemptId={paperId} backLabel="Zurück zu Lernen" onclose={() => act(back)} />
{:else if examsView}
  <div class="compass">
    <button class="back" onclick={() => act(back)}>← Lernen</button>
    <h2 class="page-title">Übungsarbeiten</h2>
    <MentorExams {accountId} subjects={(data?.extra ?? []).map((s) => s.name)} canManage={false} initialSubject={examsView.subject} initialTopic={examsView.topic} />
  </div>
{:else if data}
  <div class="compass">
    <h2 class="page-title">Lernen</h2>
    {#if !data.ai_enabled}<p class="note">Der Lernbegleiter ist noch nicht eingeschaltet. Pflicht, Stand und Vokabeln gehen trotzdem.</p>{/if}

    <section class="kompass" id="k-kompass" data-section="kompass" aria-label="Wo du stehst">
      {#if n}
        <p class="k-eyebrow">{n.kind === 'vokabeltest' ? 'Nächster Vokabeltest' : 'Nächste Arbeit'} · {subj(n.subject).name} · {n.day_label} · {daysText(n)}</p>
        {#if n.total}
          <p class="k-big">{n.ready} von {n.total} {n.total === 1 ? 'Thema' : 'Themen'} sicher</p>
          <progress class="k-bar" max={n.total} value={n.ready} aria-label={`${n.ready} von ${n.total} Themen sicher`}></progress>
          <p class="k-verdict" data-verdict={n.verdict}>{n.verdict_text}</p>
        {:else if n.vocab?.missing}
          <p class="k-big">Lektion fehlt</p>
          <p class="k-verdict">Die Wörter für „{n.vocab.unit}“ sind noch nicht im Bestand. Sag deinen Eltern Bescheid.</p>
        {:else if n.vocab}
          <p class="k-big">Vokabeln {n.vocab.unit}</p>
          {#if n.vocab.target}<p class="k-verdict">Heute {n.vocab.practiced ?? 0} von {n.vocab.target} Wörtern geübt.</p>{/if}
        {/if}
      {:else}
        <p class="k-eyebrow">Keine Arbeit in Sicht</p>
        <p class="k-big">{data.calm?.text}</p>
        {#each data.calm?.vocab ?? [] as v}
          <a class="k-link" href={v.href}>Vokabeln {subj(v.subject).name}{v.unit ? `: ${v.unit}` : ''} · {v.practiced ?? 0} von {v.target} Wörtern{v.done ? ' ✓' : ''}</a>
        {/each}
      {/if}
    </section>

    <section class="sec" id="k-pflicht" data-section="pflicht">
      <h3>Heute Pflicht <small>{plan.total ? `${plan.done} von ${plan.total}` : 'heute frei'}</small></h3>
      {#if plan.outlook}<p class="hint">{plan.outlook}</p>{/if}
      <div class="list">
        {#each plan.steps as s (s.key)}
          <div class="step" class:done={s.done} class:waiting={s.waiting}>
            <span class="check" class:checked={s.done} aria-hidden="true">{s.done ? '✓' : ''}</span>
            <span class="body"><strong>{s.title}</strong><small>{s.why}</small></span>
            {#if s.done}<span class="state">{s.skipped ? 'entfällt' : 'erledigt'}</span>
            {:else if s.waiting}<span class="state">wartet</span>
            {:else if s.attempt_id}<button class="primary go" onclick={() => startStep(s)}>{canGo ? 'Weiter' : 'Öffnen'}</button>
            {:else if canGo}<button class="primary go" disabled={!!stepBusy} onclick={() => startStep(s)}>{stepBusy === s.key ? 'Wird erstellt …' : 'Los'}</button>{/if}
          </div>
        {:else}<p class="all-clear">✓ Heute ist nichts zum Lernen Pflicht.</p>{/each}
      </div>
      <details class="explain">
        <summary>Wie der Plan entsteht</summary>
        {#each data.plan_explain as p}<p>{p}</p>{/each}
      </details>
    </section>

    <section class="sec" id="k-vokabeln" data-section="vokabeln">
      <h3>Vokabeln <small>{(data.vocab ?? []).length ? 'dein Pensum heute' : 'Trainer'}</small></h3>
      <div class="list">
        {#each data.vocab ?? [] as v}
          <a class="vocab-row" href={v.href}>
            <span class="body"><strong>{subj(v.subject).name}{v.unit ? `: ${v.unit}` : ''}</strong>
              <small>{v.why}</small>
              <span class="vbar" role="img" aria-label={`${v.practiced ?? 0} von ${v.target} Wörtern`}><i style:width={`${Math.min(100, Math.round((v.practiced ?? 0) / Math.max(1, v.target) * 100))}%`}></i></span>
            </span>
            <span class="vcount">{v.done ? '✓' : `${v.practiced ?? 0}/${v.target}`}</span>
          </a>
        {/each}
        <a class="vocab-row trainer" href="#/vokabeln"><span class="body"><strong>🔤 Zum Vokabeltrainer</strong><small>Alle Lektionen, Test auf Papier</small></span><span class="vcount">›</span></a>
      </div>
    </section>

    <section class="sec" id="k-arbeiten" data-section="arbeiten">
      <h3>Deine Arbeiten <small>nächste sechs Wochen</small></h3>
      <div class="list">
        {#each data.exams as e (e.exam_key)}
          {@const isOpen = openExam === e.exam_key}
          <div class="exam">
            <button class="exam-row" aria-expanded={isOpen} onclick={() => (openExam = isOpen ? '' : e.exam_key)}>
              <span class="exam-subj">{subj(e.subject).emoji} {subj(e.subject).name}{e.kind === 'vokabeltest' ? ' · Vokabeltest' : ''}</span>
              <span class="exam-day">{e.day_label}</span>
              <span class="dots" role="img" aria-label={e.total ? `${e.ready} von ${e.total} Themen sicher` : (e.vocab?.missing ? 'Lektion fehlt' : 'noch keine Themen')}>
                {#each e.raster as t (t.id)}<i class="dot st-{t.state}" title={`${t.title}: ${DOT[t.state]}`}></i>{/each}
                {#if e.vocab?.missing}<em class="tag warn">Lektion fehlt</em>{:else if e.topics_missing}<em class="tag">Themen fehlen</em>{/if}
              </span>
            </button>
            {#if isOpen}
              <div class="way">
                {#if e.papers?.length}
                  <h4>Deine Übungsarbeiten</h4>
                  <div class="papers">
                    {#each e.papers as p (p.attempt_id)}
                      <button class="paper-row" onclick={() => { paperId = p.attempt_id; window.scrollTo?.(0, 0); }}>
                        <span><strong>{p.label}</strong> · {p.date ? formatShortDate(p.date) : ''}</span>
                        <span class="dim">{p.status === 'graded' ? `${String(p.points).replace('.', ',')} von ${p.points_max} Punkten${p.unclear ? ` · ${p.unclear} unklar gelesen` : ''} · Ansehen` : p.status === 'grading' ? 'wird ausgewertet' : 'offen · Weiter'}</span>
                      </button>
                    {/each}
                  </div>
                {/if}
                {#if e.path.length}
                  <h4>Weg zur Arbeit</h4>
                  <ol class="path">
                    {#each e.path as p (p.key)}
                      <li class={p.state}><span class="path-dot" aria-hidden="true">{p.state === 'done' ? '✓' : ''}</span><span><strong>{p.label}</strong>{#if p.state === 'now'} <em class="here">Du bist hier</em>{/if}<small>{p.text}</small></span></li>
                    {/each}
                  </ol>
                  <div class="raster" role="table" aria-label="Stand je Thema und Anforderungsbereich">
                    <div class="r-row r-head" role="row"><span role="columnheader">Thema</span>{#each [1, 2, 3] as k}<span role="columnheader">{ROMAN[k]}<small>{e.afb_names[k]}</small></span>{/each}</div>
                    {#each e.raster as t (t.id)}
                      <div class="r-row" role="row"><span class="r-topic" role="cell">{t.title}</span>{#each ['1', '2', '3'] as k}<span role="cell" class="r-cell st-{CELL[t.cells[k]][0]}">{CELL[t.cells[k]][1]}</span>{/each}</div>
                    {/each}
                  </div>
                  <p class="muted">Ziel: jedes Thema sicher in I und II. III ist die Kür.</p>
                  <a class="more" href="#/klausuren"><ActionLabel label="Übungsarbeit selbst zusammenstellen" /></a>
                {:else if e.topics_missing}
                  <p class="muted">Die Themenliste fehlt noch. Sobald sie da ist, steht hier dein Weg zur Arbeit.</p>
                {/if}
                {#if e.vocab?.missing}<p class="muted">Lektion fehlt: Die Wörter für „{e.vocab.unit}“ sind noch nicht im Bestand.</p>
                {:else if e.vocab}<a class="more" href={e.vocab.href}><ActionLabel label={`Vokabeln ${e.vocab.unit}${e.vocab.target ? ` · heute ${e.vocab.practiced ?? 0} von ${e.vocab.target}` : ''}`} /></a>{/if}
              </div>
            {/if}
          </div>
        {:else}<p class="empty">Keine Arbeit in den nächsten vier Wochen.</p>{/each}
      </div>
    </section>

    <section class="sec" id="k-staerken" data-section="staerken">
      <h3>Stärken und Baustellen</h3>
      <div class="two">
        <div>
          <h4>Stärken</h4>
          {#each data.strengths as s}
            <div class="item"><i class="mark st-sitzt" aria-hidden="true"></i><span class="body"><strong>{s.title}</strong><small>{subj(s.subject).name} · {s.text}</small></span></div>
          {:else}<p class="empty">Sobald ein Thema sicher wird, steht es hier.</p>{/each}
        </div>
        <div>
          <h4>Baustellen</h4>
          {#each data.gaps as g}
            <div class="item"><i class="mark st-wackelt" aria-hidden="true"></i><span class="body"><strong>{g.title}</strong><small>{subj(g.subject).name} · {g.why}</small></span>
              {#if data.can_write}<button class="outline" onclick={() => go(g.href)}>Angehen</button>{/if}</div>
          {:else}<p class="empty">Gerade keine Baustelle.</p>{/each}
        </div>
      </div>
      <a class="more" href="#/subjects"><ActionLabel label="Alle Fächer" /></a>
    </section>

    <section class="sec extra" id="k-extra" data-section="extra">
      <h3>Extra <small>was du willst</small></h3>
      {#if data.extra.length}
        <div class="chips" role="group" aria-label="Fach für Extra">
          {#each data.extra as s (s.name)}
            <button class="chip" aria-pressed={pick === s.name} onclick={() => { pick = pick === s.name ? '' : s.name; newTopic = false; }}>{subj(s.name).emoji} {s.label}</button>
          {/each}
        </div>
      {:else}<p class="empty">Sobald Stunden im Stundenplan stehen, kannst du hier ein Fach wählen.</p>{/if}
      {#if chosen}
        <div class="kinds" role="group" aria-label={`Extra in ${chosen.label}`}>
          <button class="kind" disabled={busy || !data.can_write} onclick={() => act(explain)}><em class="tag">Extra</em>💬 Erklären lassen</button>
          <button class="kind" disabled={busy || !data.can_write} onclick={() => act(quiz)}><em class="tag">Extra</em>📝 Kurztest</button>
          {#if chosen.language}<button class="kind" onclick={() => go(chosen.vocab_href)}><em class="tag">Extra</em>🔤 Vokabeln</button>{/if}
          <button class="kind" aria-expanded={newTopic} onclick={() => (newTopic = !newTopic)}><em class="tag">Extra</em>🆕 Neues Thema anfangen</button>
        </div>
        {#if newTopic}
          <div class="chips" role="group" aria-label="Themen aus dem Unterricht">
            {#each chosen.recent as r (r.lesson_id)}
              <button class="chip topic" disabled={!data.can_write} onclick={() => go(r.href)}>{r.title}<small>{formatShortDate(r.date)}</small></button>
            {:else}<p class="empty">In {chosen.label} steht aus den letzten Wochen kein Stundenthema.</p>{/each}
          </div>
        {/if}
      {/if}
      <p class="muted">Extra zählt für die Extrameile und ersetzt keine Pflicht.</p>
      <button class="link" onclick={() => (examsView = { subject: pick || '', topic: '' })}><ActionLabel label="Übungsarbeiten" /></button>
    </section>

    <section class="sec" id="k-verlauf" data-section="verlauf">
      <h3>So hat sich dein Lernen entwickelt <small>vier Wochen</small></h3>
      <div class="weeks">
        {#each data.history.weeks as w (w.start)}
          <div class="week"><span class="w-label">{w.label}</span><progress max={data.history.max} value={w.topics} aria-label={`${w.label}: ${w.topics} ${w.topics === 1 ? 'Thema' : 'Themen'} sicher geworden`}></progress><span class="w-count">{w.topics}</span></div>
        {/each}
      </div>
      <p class="sentence">{data.history.sentence}</p>
    </section>

    <section class="sec" id="k-weiter" data-section="weiter">
      <h3>Weitermachen</h3>
      {#each data.sessions as s (s.id)}
        <button class="session-row" onclick={() => act(() => openSession(s))}><strong>{subj(s.subject).name} · {s.label || s.goal}</strong><small>zuletzt {when(s.last_at)}</small></button>
      {:else}<p class="empty">Nichts Angefangenes offen.</p>{/each}
      {#if earlierCount}
        <details class="earlier">
          <summary>Frühere Arbeiten</summary>
          {#each data.past_exams as p (p.exam_key)}
            <div class="past">
              <span class="exam-subj">{subj(p.subject).emoji} {subj(p.subject).name}</span>
              <span class="exam-day">{p.day_label}</span>
              <span class="dots" role="img" aria-label={`Damals ${p.ready} von ${p.total} Themen sicher`}>{#each p.raster as t (t.id)}<i class="dot st-{t.state}" title={t.title}></i>{/each}<small>{p.ready} von {p.total} sicher</small></span>
            </div>
          {/each}
          {#if data.archived_sessions.length}
            <h4>Archiv</h4>
            <p class="muted">Nichts ist gelöscht. Was du wieder aufnimmst, steht wieder oben.</p>
            {#each data.archived_sessions as s (s.id)}
              <div class="archived"><span class="body"><strong>{subj(s.subject).name} · {s.label || s.goal}</strong><small>{s.archive_reason}</small></span>
                {#if data.can_write}<button class="outline" disabled={busy} onclick={() => act(() => unarchive(s))}>Wieder aufnehmen</button>{/if}</div>
            {/each}
          {/if}
        </details>
      {/if}
    </section>
  </div>
{:else if !error}<p role="status" class="loading">Lernen wird geladen …</p>{/if}

<style>
  .papers { display: grid; gap: 4px; margin-bottom: var(--sp-2); }
  .paper-row { display: flex; justify-content: space-between; gap: 6px; flex-wrap: wrap; text-align: left; min-height: 44px; padding: 6px 10px; border: 1px solid var(--border); border-radius: var(--r-sm); background: var(--bg-card); color: var(--fg); }
  .compass { max-width: 720px; margin: 0 auto; padding-bottom: var(--sp-5); display: grid; gap: var(--sp-4); min-width: 0; }
  .page-title { margin: 0; font-size: var(--fs-xl); }
  .note, .hint { margin: 0; padding: var(--sp-2) var(--sp-3); background: var(--warm-soft); border-radius: var(--r-md); font-size: var(--fs-sm); }
  .error-box { padding: var(--sp-3); background: var(--bad-soft); border-radius: var(--r-md); }
  .loading { padding: var(--sp-4); }
  .back { justify-self: start; }

  /* Pflicht gefüllt in Akzentfarbe (D186). */
  .kompass { background: var(--accent); color: var(--accent-fg); border-radius: var(--r-lg); padding: var(--sp-4); display: grid; gap: var(--sp-2); overflow-wrap: anywhere; }
  .k-eyebrow { margin: 0; font-size: var(--fs-sm); font-weight: 650; opacity: .92; }
  .k-big { margin: 0; font-size: var(--fs-lg); font-weight: 750; line-height: 1.3; }
  .k-verdict { margin: 0; font-size: var(--fs-sm); }
  .k-link { color: inherit; text-decoration: underline; font-size: var(--fs-sm); min-height: 44px; display: flex; align-items: center; }
  .k-bar { width: 100%; height: 12px; appearance: none; -webkit-appearance: none; border: 0; border-radius: var(--r-pill); background: color-mix(in oklab, var(--accent-fg) 30%, transparent); overflow: hidden; }
  .k-bar::-webkit-progress-bar { background: color-mix(in oklab, var(--accent-fg) 30%, transparent); border-radius: var(--r-pill); }
  .k-bar::-webkit-progress-value { background: var(--accent-fg); border-radius: var(--r-pill); }
  .k-bar::-moz-progress-bar { background: var(--accent-fg); border-radius: var(--r-pill); }

  .sec { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--r-lg); padding: var(--sp-4); min-width: 0; }
  .sec h3 { margin: 0 0 var(--sp-2); font-size: var(--fs-lg); display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--sp-2); }
  .sec h3 small { font-size: var(--fs-xs); color: var(--fg-muted); font-weight: 500; }
  .sec h4 { margin: var(--sp-3) 0 var(--sp-2); font-size: var(--fs-md); }
  .list { display: grid; }
  .empty, .all-clear, .muted { color: var(--fg-muted); font-size: var(--fs-sm); margin: var(--sp-2) 0; }
  .more { display: inline-flex; align-items: center; min-height: 44px; font-size: var(--fs-sm); }
  .body { display: grid; gap: 2px; min-width: 0; overflow-wrap: anywhere; }
  .body small { color: var(--fg-muted); font-size: var(--fs-xs); }
  .outline { background: transparent; border: 1px solid var(--accent); color: var(--accent); border-radius: var(--r-md); }

  .step { display: grid; grid-template-columns: 28px minmax(0, 1fr) auto; gap: var(--sp-2); align-items: center; padding: var(--sp-2) 0; border-bottom: 1px solid var(--border); }
  .step:last-child { border-bottom: 0; }
  .check { width: 24px; height: 24px; border-radius: 50%; border: 2px solid var(--border); display: grid; place-items: center; font-weight: 800; font-size: var(--fs-xs); }
  .check.checked { background: var(--accent); border-color: var(--accent); color: var(--accent-fg); }
  .step.done .body strong { color: var(--fg-muted); }
  .step.waiting { opacity: 0.7; }
  .state { font-size: var(--fs-xs); color: var(--good-fg); font-weight: 700; }
  .go { min-width: 64px; border-radius: var(--r-md); }
  .explain { margin-top: var(--sp-2); font-size: var(--fs-sm); }
  .explain summary { min-height: 44px; display: flex; align-items: center; color: var(--accent); cursor: pointer; }
  .explain p { margin: 0 0 var(--sp-2); }

  .exam { border-bottom: 1px solid var(--border); }
  .exam:last-child { border-bottom: 0; }
  .exam-row, .past { width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) auto; grid-template-areas: "subj day" "dots dots"; gap: var(--sp-1) var(--sp-2); text-align: left; background: transparent; border: 0; border-radius: 0; padding: var(--sp-2) 0; color: inherit; min-height: 44px; }
  .exam-subj { grid-area: subj; font-weight: 650; overflow-wrap: anywhere; }
  .exam-day { grid-area: day; font-size: var(--fs-sm); color: var(--fg-muted); }
  .dots { grid-area: dots; display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-1); min-width: 0; }
  .dots small { margin-left: var(--sp-1); font-size: var(--fs-xs); color: var(--fg-muted); }
  .dot { width: 14px; height: 14px; border-radius: 50%; display: inline-block; }
  .tag { font-style: normal; font-size: var(--fs-xs); font-weight: 700; padding: 1px var(--sp-2); border-radius: var(--r-pill); border: 1px solid var(--border); color: var(--fg-muted); }
  .tag.warn { border-color: var(--warn-fg); color: var(--warn-fg); }
  .way { padding: 0 0 var(--sp-3); min-width: 0; }
  .path { list-style: none; margin: 0 0 var(--sp-3); padding: 0; display: grid; gap: var(--sp-2); }
  .path li { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: var(--sp-2); align-items: start; }
  .path li small { display: block; color: var(--fg-muted); font-size: var(--fs-xs); }
  .path-dot { width: 20px; height: 20px; margin-top: 2px; border-radius: 50%; border: 2px solid var(--border); display: grid; place-items: center; font-size: var(--fs-xs); font-weight: 800; }
  .path li.done .path-dot { background: var(--st-sitzt); border-color: var(--st-sitzt); color: var(--bg-card); }
  .path li.now .path-dot { border-color: var(--accent); background: var(--accent); }
  .path li.todo { color: var(--fg-muted); }
  .here { margin-left: var(--sp-2); font-style: normal; font-size: var(--fs-xs); font-weight: 700; color: var(--accent); }
  .raster { display: grid; gap: 3px; font-size: var(--fs-xs); min-width: 0; }
  .r-row { display: grid; grid-template-columns: minmax(0, 1fr) repeat(3, minmax(44px, 56px)); gap: 3px; align-items: stretch; }
  .r-head span { font-weight: 700; display: grid; text-align: center; }
  .r-head span:first-child { text-align: left; }
  .r-head small { font-weight: 400; color: var(--fg-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .r-topic { overflow-wrap: anywhere; padding: var(--sp-1) 0; }
  .r-cell { border-radius: var(--r-sm); display: grid; place-items: center; padding: var(--sp-1) 2px; color: var(--fg); text-align: center; }
  .r-cell.st-gefestigt, .r-cell.st-sitzt { color: var(--bg-card); }

  .two { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0 var(--sp-4); }
  .item, .archived { display: grid; grid-template-columns: 12px minmax(0, 1fr) auto; gap: var(--sp-2); align-items: center; padding: var(--sp-2) 0; border-bottom: 1px solid var(--border); }
  .archived { grid-template-columns: minmax(0, 1fr) auto; }
  .mark { width: 12px; height: 12px; border-radius: 50%; }

  /* Extra umrandet: freiwillig, zählt für die Extrameile, nie statt Pflicht. */
  .extra { border: 2px dashed var(--accent); }
  .chips { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin: var(--sp-2) 0; }
  .chip { border-radius: var(--r-pill); background: var(--bg-card); border: 1px solid var(--border); padding: var(--sp-2) var(--sp-3); max-width: 100%; overflow-wrap: anywhere; text-align: left; }
  .chip[aria-pressed="true"] { border-color: var(--accent); background: var(--accent-soft); font-weight: 650; }
  .chip.topic small { display: block; font-size: var(--fs-xs); color: var(--fg-muted); }
  .kinds { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: var(--sp-2); margin: var(--sp-2) 0; }
  .kind { display: grid; justify-items: start; gap: 2px; text-align: left; border: 1px solid var(--accent); background: transparent; color: var(--fg); border-radius: var(--r-md); padding: var(--sp-2) var(--sp-3); }
  .kind .tag { border-color: var(--accent); color: var(--accent); }
  .kind[aria-expanded="true"] { background: var(--accent-soft); }
  .link { background: transparent; border: 0; padding: 0; color: var(--accent); min-height: 44px; }

  .weeks { display: grid; gap: var(--sp-2); }
  .week { display: grid; grid-template-columns: 7.5em minmax(0, 1fr) 2em; gap: var(--sp-2); align-items: center; font-size: var(--fs-sm); }
  .week progress { width: 100%; height: 14px; appearance: none; -webkit-appearance: none; border: 0; border-radius: var(--r-pill); background: var(--bg); overflow: hidden; }
  .week progress::-webkit-progress-bar { background: var(--bg); border-radius: var(--r-pill); }
  .week progress::-webkit-progress-value { background: var(--st-sitzt); border-radius: var(--r-pill); }
  .week progress::-moz-progress-bar { background: var(--st-sitzt); border-radius: var(--r-pill); }
  .w-count { text-align: right; font-weight: 700; }
  .sentence { margin: var(--sp-3) 0 0; }

  .session-row { width: 100%; display: grid; gap: 2px; text-align: left; margin: 0 0 var(--sp-2); border-radius: var(--r-md); padding: var(--sp-2) var(--sp-3); overflow-wrap: anywhere; }
  .session-row small { color: var(--fg-muted); font-size: var(--fs-xs); }
  .earlier { margin-top: var(--sp-2); }
  .earlier summary { min-height: 44px; display: flex; align-items: center; cursor: pointer; color: var(--accent); }
  .past { border-bottom: 1px solid var(--border); }
  .vocab-row{display:flex;justify-content:space-between;align-items:center;gap:var(--sp-2);padding:var(--sp-2) var(--sp-3);min-height:44px;color:var(--fg);text-decoration:none}
  .vocab-row+.vocab-row{border-top:1px solid var(--border)}
  .vocab-row .body{display:grid;gap:3px;min-width:0}
  .vocab-row small{color:var(--fg-muted);font-size:var(--fs-xs)}
  .vbar{display:block;height:6px;border-radius:var(--r-pill);background:var(--bg-elevated);overflow:hidden;max-width:220px}
  .vbar i{display:block;height:100%;background:var(--accent)}
  .vcount{font-weight:700;font-variant-numeric:tabular-nums;color:var(--accent);white-space:nowrap}
</style>
