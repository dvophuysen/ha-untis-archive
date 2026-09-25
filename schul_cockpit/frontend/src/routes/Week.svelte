<script>
  // Die Woche rollend (D184): die nächsten fünf Schultage ab heute, oben was
  // anders ist als sonst, darunter der Kalender als Leisten wie auf der
  // Familienkarte oder als Raster. Zurückgeblättert steht oben der Rückblick.
  // Ein Aufruf je Zeitraum (GET /week/rolling); beim Blättern bleibt der alte
  // Inhalt stehen, bis der neue da ist.
  import { api } from '../lib/api.js';
  import DayStrip from '../lib/DayStrip.svelte';
  import DaySchedule from '../lib/DaySchedule.svelte';
  import WeekGrid from '../lib/WeekGrid.svelte';
  import { slotsOf } from '../lib/dayStrip.js';
  import { subjectStyle } from '../lib/subjectStyle.js';

  let { accountId } = $props();

  const VIEW_KEY = 'week.view';
  function readView() {
    try { return localStorage.getItem(VIEW_KEY) === 'grid' ? 'grid' : 'strip'; } catch { return 'strip'; }
  }
  function setView(v) {
    view = v;
    try { localStorage.setItem(VIEW_KEY, v); } catch { /* ohne Speicher bleibt die Wahl nur hier */ }
  }

  let anchor = $state(null);          // null = ab heute | { from } | { before }
  let data = $state(null);
  let loading = $state(false);
  let error = $state(null);
  let view = $state(readView());
  let open = $state({});
  let now = $state(new Date());
  let seq = 0;

  async function load() {
    if (!accountId) return;
    const id = ++seq;
    loading = true;
    error = null;
    const q = anchor?.from ? `?from=${anchor.from}` : anchor?.before ? `?before=${anchor.before}` : '';
    try {
      const d = await api.get(`/api/accounts/${accountId}/week/rolling${q}`);
      if (id !== seq) return;
      data = d;
      now = new Date();
    } catch (e) {
      if (id === seq) error = e.message;
    } finally {
      if (id === seq) loading = false;
    }
  }
  $effect(() => { void accountId; void anchor; load(); });

  function go(next) { open = {}; anchor = next; }
  const back = () => data?.prev_before && go({ before: data.prev_before });
  const forward = () => data?.next_from && go({ from: data.next_from });

  // Wischen blättert wie die Pfeile.
  let touch = null;
  function touchStart(e) { const t = e.touches[0]; touch = { x: t.clientX, y: t.clientY }; }
  function touchEnd(e) {
    if (!touch) return;
    const t = e.changedTouches[0], dx = t.clientX - touch.x, dy = t.clientY - touch.y;
    touch = null;
    if (Math.abs(dx) > 70 && Math.abs(dy) < 40) (dx < 0 ? forward : back)();
  }

  const WD = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
  const at = (iso) => new Date(`${iso}T12:00:00`);
  const dayName = (iso) => `${WD[at(iso).getDay()]} ${iso.slice(8, 10)}.${iso.slice(5, 7)}.`;
  const rangeLabel = $derived(data?.range ? `${dayName(data.range.start)} – ${dayName(data.range.end)}` : '');
  const weekLabel = $derived.by(() => {
    const weeks = [...new Set((data?.days || []).map((d) => d.week))];
    return weeks.length ? `KW ${weeks.join('/')}` : '';
  });
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  const dayTitle = (d) => (d.is_today ? 'Heute' : d.label);
  const examText = (x) => `${subjectStyle(x.subject).name}-${x.kind}`;
  const readyText = (x) => (x.total ? `${x.ready} von ${plural(x.total, 'Thema', 'Themen')} sicher` : '');
  const endOfDay = (iso) => new Date(`${iso}T23:59:00`);
  const startOfDay = (iso) => new Date(`${iso}T00:00:00`);
  // Rückmelden erst nach der Stunde: vergangene Tage ganz, heute nach Uhr, später nie.
  const nowFor = (d) => (d.is_today ? now : d.is_past ? endOfDay(d.date) : startOfDay(d.date));

  // Was an einem Tag anders ist, in Worten; eine Vertretung über eine
  // Doppelstunde nur einmal.
  function changesOf(d) {
    const out = [], seen = new Set();
    for (const c of d.strip?.changes || []) {
      const k = `${c.kind}:${c.subject}`;
      if (c.kind !== 'cancelled' && seen.has(k)) continue;
      seen.add(k);
      out.push(c);
    }
    return out;
  }
  function wordsOf(d) {
    const out = [];
    if (d.strip?.headline) out.push(d.strip.headline);
    for (const c of changesOf(d)) out.push(c.text);
    for (const x of d.exams) out.push(examText(x));
    return out;
  }

  // Überblick: je Tag eine Zeile, freie Tage dazwischen, nur was abweicht.
  const glance = $derived.by(() => {
    if (!data || data.mode !== 'ahead') return [];
    const rows = [];
    for (const d of data.days) {
      if (d.date < data.today) continue;
      const items = [];
      if (d.strip?.headline) items.push({ tone: 'warn', text: d.strip.headline });
      for (const c of changesOf(d)) items.push({ tone: c.kind === 'cancelled' ? 'x' : c.kind === 'sub' ? 's' : 'c', text: c.text });
      for (const x of d.exams) items.push({ tone: 'exam', exam: x });
      if (items.length) rows.push({ key: d.date, date: d.date, label: dayTitle(d), items });
    }
    for (const f of data.free || []) {
      if (f.end < data.today) continue;
      rows.push({ key: `f${f.start}`, date: f.start, label: f.label, items: [{ tone: 'free', text: f.name || 'kein Unterricht' }] });
    }
    return rows.sort((a, b) => a.date.localeCompare(b.date));
  });
  const homework = $derived.by(() => {
    const days = (data?.days || []).filter((d) => d.date >= (data?.today || '') && d.tasks_open);
    const total = days.reduce((n, d) => n + d.tasks_open, 0);
    return { total, parts: days.map((d) => `${d.is_today ? 'heute' : d.label.slice(0, 2)} ${d.tasks_open}`) };
  });
  const slots = $derived(slotsOf((data?.days || []).map((d) => d.strip).filter(Boolean)));
  const pending = $derived((data?.feedback?.days || []).reduce((n, d) => n + d.lessons.filter((l) => !l.checkin?.rating).length, 0));
  // In den Ferien: ein Satz statt leerer Wochen.
  const holidayNow = $derived((data?.free || []).find((f) => f.name && f.start <= data.today && data.today <= f.end));
  // Freie Werktage zwischen den gezeigten Tagen stehen im Kalender als eigene Zeile.
  const calendar = $derived.by(() => {
    const out = [];
    const free = [...(data?.free || [])];
    for (const d of data?.days || []) {
      while (free.length && free[0].start < d.date) {
        const f = free.shift();
        if (out.length) out.push({ free: f, key: `f${f.start}` });
      }
      out.push({ day: d, key: d.date });
    }
    return out;
  });
</script>

<div class="wk" role="region" aria-label="Woche" ontouchstart={touchStart} ontouchend={touchEnd} aria-busy={loading}>
  <div class="wk-head">
    <button class="nav" aria-label="Fünf Schultage zurück" disabled={!data?.prev_before} onclick={back}>
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M15 5l-7 7 7 7" /></svg>
    </button>
    <div class="range" aria-live="polite">
      <b>{rangeLabel || 'Woche'}</b>
      <span>{weekLabel}{#if anchor}<button class="today-btn" onclick={() => go(null)}>Heute</button>{/if}</span>
    </div>
    <button class="nav" aria-label="Fünf Schultage weiter" disabled={!data?.next_from} onclick={forward}>
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M9 5l7 7-7 7" /></svg>
    </button>
  </div>

  {#if error}<div class="error-box" role="alert">{error}</div>{/if}

  {#if !data && loading}
    <div class="empty"><span class="spinner"></span></div>
  {:else if data}
    <div class="wk-body" class:stale={loading}>
      {#if data.mode === 'empty'}
        <section class="card glance">
          <h2>{data.holiday ? data.holiday.name : 'Kein Unterricht in Sicht'}</h2>
          <p class="muted">{data.holiday ? `Frei bis ${dayName(data.holiday.end)}. Der Stundenplan danach ist noch nicht da.` : 'Sobald der Stundenplan da ist, steht er hier.'}</p>
        </section>
      {:else}
        {#if holidayNow && data.default}
          <p class="holiday">{holidayNow.name} bis {dayName(holidayNow.end)}. Weiter geht es am {dayName(data.days[0].date)}.</p>
        {/if}

        {#if data.mode === 'ahead'}
          <section class="card glance" aria-labelledby="wk-glance">
            <h2 id="wk-glance">Die nächsten Tage auf einen Blick</h2>
            {#each glance as r (r.key)}
              <div class="g-row">
                <span class="g-day">{r.label}</span>
                <span class="g-items">
                  {#each r.items as it, n (n)}
                    {#if it.exam}
                      {#if it.exam.exam_key}
                        <a class="g-exam" href={`#/klausuren?exam=${encodeURIComponent(it.exam.exam_key)}`} aria-label={`${examText(it.exam)}${readyText(it.exam) ? `, ${readyText(it.exam)}` : ''}`}><span>{subjectStyle(it.exam.subject).emoji} {examText(it.exam)}</span>{#if readyText(it.exam)}<small>{readyText(it.exam)}</small>{/if}</a>
                      {:else}
                        <span class="g-exam plain">{subjectStyle(it.exam.subject).emoji} {examText(it.exam)}</span>
                      {/if}
                    {:else}
                      <span class="g-it {it.tone}">{it.text}</span>
                    {/if}
                  {/each}
                </span>
              </div>
            {:else}
              <p class="g-calm">Alles wie immer.</p>
            {/each}
            {#if homework.total}
              <a class="g-hw" href="#/tasks"><span>{plural(homework.total, 'Hausaufgabe', 'Hausaufgaben')} fällig</span><small>{homework.parts.join(' · ')}</small></a>
            {/if}
          </section>
        {:else}
          <section class="card glance" aria-labelledby="wk-review">
            <h2 id="wk-review">Rückblick</h2>
            {#if data.review?.lines.length}
              <ul class="rv">{#each data.review.lines as line}<li>{line}</li>{/each}</ul>
            {:else}
              <p class="muted">In diesen Tagen ist nichts eingetragen.</p>
            {/if}
            <a class="g-link" href="#/ich">Serie und Abzeichen unter Ich</a>
          </section>
        {/if}

        {#if data.feedback?.days.length}
          <section class="card fb" aria-labelledby="wk-fb">
            <h2 id="wk-fb">{pending ? `Noch zurückmelden: ${plural(pending, 'Stunde', 'Stunden')}` : 'Alles zurückgemeldet'}</h2>
            {#each data.feedback.days as fd (fd.date)}
              <p class="fb-day">{fd.label}</p>
              <DaySchedule {accountId} lessons={fd.lessons} now={endOfDay(fd.date)} live={false} />
            {/each}
          </section>
        {/if}

        <section class="cal" aria-labelledby="wk-cal">
          <div class="cal-head">
            <h2 id="wk-cal">Kalender</h2>
            <div class="seg" role="group" aria-label="Darstellung">
              <button aria-pressed={view === 'strip'} class:on={view === 'strip'} onclick={() => setView('strip')}>Streifen</button>
              <button aria-pressed={view === 'grid'} class:on={view === 'grid'} onclick={() => setView('grid')}>Raster</button>
            </div>
          </div>

          {#if view === 'grid'}
            <div class="card grid-card"><WeekGrid {accountId} days={data.days} /></div>
          {:else}
            {#each calendar as item (item.key)}
              {#if item.free}
                <p class="free-row">{item.free.label} · {item.free.name || 'kein Unterricht'}</p>
              {:else}
                {@const d = item.day}
                {@const words = wordsOf(d)}
                <div class="day" class:today={d.is_today} class:open={open[d.date]} data-date={d.date}>
                  <button class="day-btn" aria-expanded={!!open[d.date]} aria-controls={`day-${d.date}`}
                          onclick={() => (open = { ...open, [d.date]: !open[d.date] })}>
                    <span class="lbl">
                      <b>{dayTitle(d)}</b>
                      {#if words.length}<span class="dev">{words[0]}</span>
                      {:else}<span class="calm">{d.assumed ? (d.holiday || 'Stundenplan folgt') : 'wie geplant'}</span>{/if}
                    </span>
                    {#if words.length > 1}<span class="notes">{words.slice(1).join(' · ')}</span>{/if}
                    {#if d.strip}<DayStrip day={d.strip} {slots} />{/if}
                    {#if d.tasks_open}<span class="hw-hint">{plural(d.tasks_open, 'Hausaufgabe', 'Hausaufgaben')} fällig</span>{/if}
                  </button>
                  {#if open[d.date]}
                    <div class="day-body" id={`day-${d.date}`}>
                      {#if d.lessons.length}
                        <DaySchedule {accountId} lessons={d.lessons} now={nowFor(d)} live={d.is_today} />
                      {:else}
                        <p class="muted">Der Stundenplan für diesen Tag ist noch nicht da.</p>
                      {/if}
                      {#if d.tasks.length}
                        <h3>Hausaufgaben für {d.is_today ? 'heute' : d.label}</h3>
                        <ul class="hw">
                          {#each d.tasks as t (t.id)}
                            {@const st = subjectStyle(t.subject || t.subject_name)}
                            <li class:done={t.done}>
                              <a href="#/tasks"><span class="hw-mark" aria-hidden="true">{t.done ? '✓' : ''}</span>
                                <span><small>{t.subject_name ? `${st.emoji} ${st.name}` : 'Erinnerung'}</small>{t.title}</span>
                                {#if t.done}<span class="sr">erledigt</span>{/if}</a>
                            </li>
                          {/each}
                        </ul>
                      {/if}
                    </div>
                  {/if}
                </div>
              {/if}
            {/each}
          {/if}
        </section>
      {/if}
    </div>
  {/if}
</div>

<style>
  .wk { display: grid; gap: var(--sp-3); padding-bottom: var(--sp-4); }
  .wk-head { display: grid; grid-template-columns: 44px minmax(0, 1fr) 44px; align-items: center; gap: var(--sp-2); }
  .nav { width: 44px; height: 44px; min-height: 44px; padding: 0; display: grid; place-items: center; border-radius: var(--r-pill); }
  .nav svg { fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
  .nav:disabled { opacity: 0.35; }
  .range { text-align: center; display: grid; gap: 2px; min-width: 0; }
  .range b { font-size: var(--fs-md); font-variant-numeric: tabular-nums; }
  .range span { font-size: var(--fs-xs); color: var(--fg-muted); display: flex; justify-content: center; align-items: center; gap: var(--sp-2); }
  .today-btn { min-height: 32px; padding: 2px var(--sp-3); font-size: var(--fs-xs); font-weight: 700; border-radius: var(--r-pill); }
  .wk-body { display: grid; gap: var(--sp-3); transition: opacity 0.15s; }
  .wk-body.stale { opacity: 0.55; }
  h2 { font-size: var(--fs-md); margin: 0 0 var(--sp-2); }
  h3 { font-size: var(--fs-sm); margin: var(--sp-3) 0 var(--sp-1); }

  .glance { display: grid; gap: var(--sp-1); }
  .g-row { display: grid; grid-template-columns: 5.6em minmax(0, 1fr); gap: var(--sp-2); padding: var(--sp-1) 0; border-top: 1px solid var(--border); }
  .g-row:first-of-type { border-top: 0; }
  .g-day { font-size: var(--fs-sm); font-weight: 650; }
  .g-items { display: flex; flex-wrap: wrap; gap: var(--sp-1) var(--sp-2); font-size: var(--fs-sm); min-width: 0; overflow-wrap: anywhere; }
  .g-it { line-height: 1.35; }
  .g-it.warn { color: var(--warn-fg); font-weight: 650; }
  .g-it.x { color: var(--fg-muted); }
  .g-it.s { color: var(--substitution-fg); }
  .g-it.c { color: var(--warn-fg); }
  .g-it.free { color: var(--fg-muted); font-style: italic; }
  .g-exam { display: inline-grid; align-content: center; min-height: 44px; padding: 2px var(--sp-2);
    border: 2px solid var(--exam); border-radius: var(--r-sm); font-weight: 650; color: var(--fg); text-decoration: none; }
  .g-exam.plain { min-height: 32px; margin: 0; }
  .g-exam small, .g-hw small { font-weight: 500; color: var(--fg-muted); }
  .g-calm { margin: 0; color: var(--fg-muted); }
  .g-hw, .g-link { display: flex; align-items: center; flex-wrap: wrap; column-gap: var(--sp-2); min-height: 44px; font-size: var(--fs-sm); font-weight: 650; border-top: 1px solid var(--border); margin-top: var(--sp-1); }
  .rv { margin: 0; padding-left: 1.1em; display: grid; gap: var(--sp-1); font-size: var(--fs-sm); }
  .holiday { margin: 0; padding: var(--sp-2) var(--sp-3); border-radius: var(--r-md); background: var(--bg-elevated); font-size: var(--fs-sm); }

  .fb-day { margin: var(--sp-2) 0 var(--sp-1); font-size: var(--fs-xs); font-weight: 700; color: var(--fg-muted); }

  .cal { display: grid; gap: var(--sp-2); }
  .cal-head { display: flex; justify-content: space-between; align-items: center; gap: var(--sp-2); }
  .cal-head h2 { margin: 0; }
  .seg { display: inline-flex; border: 1px solid var(--border); border-radius: var(--r-pill); padding: 2px; background: var(--bg-card); }
  .seg button { min-height: 40px; padding: 0 var(--sp-3); border: 0; border-radius: var(--r-pill); background: transparent; font-size: var(--fs-sm); color: var(--fg-muted); }
  .seg button.on { background: var(--accent); color: var(--bg-card); font-weight: 700; }
  .grid-card { padding: var(--sp-2); }

  .day { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--r-md); }
  .day.today { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent) inset; }
  .day-btn { display: grid; gap: var(--sp-1); width: 100%; text-align: left; background: transparent; border: 0; padding: var(--sp-2) var(--sp-3); color: var(--fg); min-height: 44px; border-radius: var(--r-md); }
  .lbl { display: flex; justify-content: space-between; align-items: baseline; gap: var(--sp-2); font-size: var(--fs-sm); min-width: 0; }
  .lbl b { white-space: nowrap; }
  .day.today .lbl b { color: var(--accent); }
  .lbl .dev { color: var(--warn-fg); font-weight: 650; font-size: var(--fs-xs); text-align: right; overflow-wrap: anywhere; }
  .lbl .calm { color: var(--fg-muted); font-size: var(--fs-xs); }
  .notes { font-size: var(--fs-xs); color: var(--warn-fg); overflow-wrap: anywhere; }
  .hw-hint { font-size: var(--fs-xs); color: var(--fg-muted); }
  .day-body { padding: 0 var(--sp-2) var(--sp-2); }
  .free-row { margin: 0; padding: var(--sp-1) var(--sp-3); font-size: var(--fs-xs); color: var(--fg-muted); font-style: italic; }
  .hw { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--sp-1); }
  .hw a { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: var(--sp-2); align-items: center; min-height: 44px; color: var(--fg); text-decoration: none;
    padding: var(--sp-1) var(--sp-2); border-radius: var(--r-sm); background: var(--bg-elevated); overflow-wrap: anywhere; }
  .hw a small { display: block; font-size: var(--fs-xs); color: var(--fg-muted); }
  .hw-mark { width: 22px; height: 22px; border: 2px solid var(--border); border-radius: var(--r-sm); display: grid; place-items: center; font-size: var(--fs-xs); }
  .hw li.done .hw-mark { background: var(--good-bg); color: var(--good-fg); border-color: transparent; }
  .hw li.done a > span:nth-child(2) { color: var(--fg-muted); }
  .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
</style>
