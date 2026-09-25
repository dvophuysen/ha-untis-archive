<script>
  import StageLegend from '../lib/StageLegend.svelte';
  import StageBar from '../lib/StageBar.svelte';
  import { COLORS, initials } from '../lib/profile.svelte.js';
  // Startseite der Eltern (D166): je Kind eine Karte. Oben der Status, dann was
  // jetzt offen ist, die Arbeiten chronologisch mit dem Lernstand ihrer Themen,
  // zuletzt was sich über Wochen abzeichnet. Jeder Baustein springt zum Kind in
  // den passenden Abschnitt, lesend (D175). Was ein Elternteil selbst tun muss,
  // führt stattdessen nach „Erledigen“ (D183). Die Seite „Heute“ des Kindes
  // wird nicht wiederholt.
  import ActionLabel from '../lib/ActionLabel.svelte';
  import { subjectStyle } from '../lib/subjectStyle.js';
  import { formatShortDate } from '../lib/format.js';
  import { untrack } from 'svelte';
  import { api } from '../lib/api.js';
  import { setActiveAccount } from '../lib/store.svelte.js';
  import { setViewMode } from '../lib/viewMode.svelte.js';
  import { jumpHash } from '../lib/jump.js';

  let data = $state(null);
  let loading = $state(true);
  let error = $state(null);

  let request = 0;
  async function load() {
    const current = ++request;
    loading = !data;
    error = null;
    try {
      const result = await api.get('/api/dashboard');
      if (current === request) data = result;
    } catch (e) {
      if (current === request) error = e.message;
    } finally {
      if (current === request) loading = false;
    }
  }

  $effect(() => {
    untrack(load);
    const refresh = () => { if (!document.hidden) load(); };
    window.addEventListener('focus', refresh);
    const timer = setInterval(refresh, 60000);
    return () => { request++; clearInterval(timer); window.removeEventListener('focus', refresh); };
  });

  function open(kid, target) {
    if (!target) return;
    setActiveAccount(kid.account_id);
    // Von der Familienkarte aus liest man mit (D175): Die Kinder handeln selbst,
    // Eltern kommen nicht in Versuchung abzuhaken. Eltern-Aufgaben (Fotos,
    // Gegenlesen, Zuordnen) öffnen die Elternansicht mit Schreibrecht (D183).
    setViewMode(target.parent ? 'parent' : 'mirror');
    window.location.hash = jumpHash(target);
  }

  // Pausen als Lücke in der Leiste: ab zehn Minuten zwischen zwei Stunden.
  const minutes = (hhmm) => (hhmm ? Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5)) : null);
  // Beide Tage auf gemeinsamen Zeitfenstern, damit gleiche Stunden
  // untereinander stehen; ein freies Fenster bleibt leer.
  function slotsOf(days) {
    const byStart = new Map();
    for (const d of days) for (const p of d.periods) if (p.start && !byStart.has(p.start)) byStart.set(p.start, p.end);
    return [...byStart.entries()].sort((a, b) => minutes(a[0]) - minutes(b[0])).map(([start, end]) => ({ start, end }));
  }
  function withGaps(day, slots) {
    const out = [];
    slots.forEach((slot, i) => {
      const prev = slots[i - 1];
      if (prev && minutes(slot.start) - minutes(prev.end) >= 10) out.push({ gap: true, key: `g${i}` });
      const p = day.periods.find((x) => x.start === slot.start);
      out.push(p ? { ...p, key: `p${i}` } : { empty: true, key: `e${i}` });
    });
    return out;
  }
  const periodTitle = (p) => `${p.start}–${p.end} ${p.subject}${p.state === 'cancelled' ? ', fällt aus' : p.state === 'sub' ? ', Vertretung' : ''}${p.exam ? ', Arbeit' : ''}${p.absent ? ', gefehlt' : ''}`;

  const STAGES = [['sitzt', 'sitzt'], ['wackelt', 'wackelt'], ['angefangen', 'angefangen'], ['neu', 'noch nicht geübt']];
  const inDays = (n) => (n <= 0 ? 'heute' : n === 1 ? 'morgen' : `in ${n} Tagen`);
  const examTitle = (x) => `${subjectStyle(x.subject_name).name}-${x.kind}`;
  const pages = (n) => `${n} ${n === 1 ? 'Seite fehlt' : 'Seiten fehlen'}`;
  const stageText = (x) => STAGES.filter(([k]) => x.stages[k]).map(([k, label]) => `${x.stages[k]} ${label}`).join(', ');
</script>

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if error && !data}
  <div class="error-box">{error}</div>
{:else if data && data.kids.length === 0}
  <div class="empty">Noch keine Kinder verlinkt.</div>
{:else if data}
  <!-- Ein gescheitertes Aktualisieren lässt den letzten Stand stehen. -->
  {#if error}<p class="stale" role="status">Stand nicht aktualisiert: {error}</p>{/if}
  <div class="dash">
    {#each data.kids as kid (kid.account_id)}
      {@const b = kid.board}
      <section class="kid card" aria-label={`Stand von ${kid.name}`} data-status={b.status.level}>
        <header class="kid-head">
          <h2 class="kid-name">{#if kid.profile}<span class="kid-av" style:background={COLORS.find((c) => c[0] === kid.profile.color)?.[1] ?? 'var(--accent)'} aria-hidden="true">{kid.profile.avatar || initials(kid.name)}</span>{/if}{kid.name}</h2>
          <span class="pill {b.status.level}">{b.status.label}</span>
        </header>
        {#if b.status.level !== 'good' && b.status.reasons.length}
          <p class="why">{b.status.reasons.slice(0, 3).join(' · ')}</p>
        {/if}

        <!-- Heute und der nächste Schultag, gewechselt um Mitternacht (D170). -->
        {#if b.schedule?.length}
          {@const slots = slotsOf(b.schedule)}
          <button class="plan" onclick={() => open(kid, { page: 'week' })} aria-label={`Stundenplan von ${kid.name} ansehen`}>
            {#each b.schedule as d (d.date)}
              <span class="lbl"><span>{d.label}</span>
                {#if d.headline}<span class="dev">{d.headline}</span>{:else if d.notes.length}<span class="dev">{d.notes[0]}</span>{:else}<span>wie geplant</span>{/if}</span>
              <span class="strip">
                <span class="t" class:devt={d.late_start}>{d.start ?? d.planned_start}</span>
                <span class="ps">
                  {#each withGaps(d, slots) as p (p.key)}
                    {#if p.gap}<i class="gap"></i>
                    {:else if p.empty}<i class="empty"></i>
                    {:else}<i class:x={p.state === 'cancelled'} class:sub={p.state === 'sub'} class:arbeit={p.exam}
                              class:now={p.now} class:past={p.past} class:absent={p.absent} title={periodTitle(p)}>{p.short}</i>{/if}
                  {/each}
                </span>
                <span class="t" class:devt={d.early_end || d.all_cancelled}>{d.all_cancelled ? 'frei' : d.end}</span>
              </span>
              {#if (d.headline && d.notes.length) || d.notes.length > 1}
                <span class="notes">{(d.headline ? d.notes : d.notes.slice(1)).join(' · ')}</span>
              {/if}
            {/each}
          </button>
        {/if}

        <!-- Serie und neue Abzeichen dieses Kindes (D173), nie neben den Geschwistern verglichen. -->
        {#if kid.rewards}
          {@const rw = kid.rewards}
          <button class="rewards" onclick={() => open(kid, { page: 'ich' })} aria-label={`Serie und Abzeichen von ${kid.name}`}>
            <span class="rw-line"><span>🔥 <b>{rw.streak.current} {rw.streak.current === 1 ? 'Schultag' : 'Schultage'}</b> · Rekord {rw.streak.record}</span><span class="rw-total">{rw.total} geschafft</span></span>
            <span class="rw-week">{#each rw.week as d, i (d.day)}<i class={d.state} title={d.day}>{d.state === 'full' ? '✓' : d.state === 'rescued' ? '½' : ''}</i>{/each}</span>
            {#each rw.reached_today ?? [] as n}<span class="rw-new">{n.emoji} Neu: {n.name} {n.level}</span>{/each}
          </button>
        {/if}

        {#if kid.study}
          <!-- Lernen heute (D180): nur zur Information, die App steuert selbst nach. -->
          <button class="okline study" class:open={kid.study.done < kid.study.total} onclick={() => open(kid, { page: 'today', section: 'lernen,lernen-kurz' })}><span>Lernen heute: {kid.study.done} von {kid.study.total}{#each kid.study.tight ?? [] as t} · eng bis {subjectStyle(t.subject).name} am {formatShortDate(t.exam_date)}{/each}</span></button>
        {/if}
        {#if b.ok.length}
          <button class="okline" onclick={() => open(kid, { page: 'today' })}><span>✓ {b.ok.join(' · ')}</span></button>
        {/if}
        {#each b.acute as r (r.key)}
          <button class="row {r.tone}" onclick={() => open(kid, r.go)}>
            <span class="ic" aria-hidden="true">{r.icon}</span>
            <span class="tx"><b>{r.title}</b><small>{r.detail}</small></span>
            <span class="go"><ActionLabel /></span>
          </button>
        {/each}

        {#if b.exams.length || b.later.length}
          <h3 class="sec">Arbeiten</h3>
          {#each b.exams as x (x.exam_key)}
            <button class="exam" onclick={() => open(kid, x.go)}>
              <span class="l1"><b>{examTitle(x)} {x.day}</b><span class="when" class:hot={x.days_until <= 7}>{inDays(x.days_until)}</span></span>
              {#if x.topics}
                <span class="stack"><StageBar counts={x.stages} order={['sitzt', 'wackelt', 'angefangen', 'neu']} label={`Lernstand: ${stageText(x)}`} /></span>
              {/if}
              <span class="l3">
                <span>{x.topics ? `${x.practiced} von ${x.topics} ${x.topics === 1 ? 'Thema' : 'Themen'} geübt` : 'Themen noch unbekannt'}</span>
                {#if x.missing}<span class="badge {x.days_until <= 7 ? 'bad' : 'warn'}">{pages(x.missing)}</span>
                {:else if x.material_ok}<span>Material ✓</span>{/if}
              </span>
            </button>
          {/each}
          {#if b.later.length}
            <p class="later">Später:
              {#each b.later as x, i (x.exam_key)}{i ? ' · ' : ' '}<button class="link" onclick={() => open(kid, x.go)}>{subjectStyle(x.subject_name).name} {x.day.slice(3)}</button>{#if x.missing}<span class="badge warn">{x.missing} {x.missing === 1 ? 'fehlt' : 'fehlen'}</span>{:else if !x.topics}<span class="badge mute">Themen unbekannt</span>{/if}{/each}
            </p>
          {/if}
        {/if}

        {#if b.watch.length}
          <h3 class="sec">Beobachten</h3>
          {#each b.watch as r (r.key)}
            {#if r.go}
              <button class="row {r.tone}" onclick={() => open(kid, r.go)}>
                <span class="ic" aria-hidden="true">{r.icon}</span>
                <span class="tx"><b>{r.title}</b><small>{r.detail}</small></span>
                <span class="go"><ActionLabel /></span>
              </button>
            {:else}
              <div class="row {r.tone}">
                <span class="ic" aria-hidden="true">{r.icon}</span>
                <span class="tx"><b>{r.title}</b><small>{r.detail}</small></span>
              </div>
            {/if}
          {/each}
        {/if}

      </section>
    {/each}
  </div>
  <StageLegend stages={['sitzt', 'wackelt', 'angefangen', 'neu']} labels={{ neu: 'noch nicht geübt' }} />
{/if}

<style>
  .dash { display: grid; gap: 1rem; grid-template-columns: 1fr; align-items: start; }
  @media (min-width: 720px) { .dash { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  .kid, .legend { --s-sitzt: var(--st-sitzt); --s-wackelt: var(--st-wackelt); --s-angefangen: var(--st-angefangen); --s-neu: var(--st-neu); }
  .kid {
    --warn-bg: var(--warm-soft); --good-bg: color-mix(in srgb, var(--good-fg) 12%, var(--bg-card));
    padding: 0.8rem; display: flex; flex-direction: column; gap: 0.1rem; min-width: 0;
  }
  .rewards { display: grid; gap: 6px; text-align: left; background: transparent; border: 0; padding: 6px 0; border-radius: 0; min-height: 44px; color: var(--fg); }
  .rw-line { display: flex; justify-content: space-between; gap: 8px; font-size: var(--fs-sm); }
  .rw-total { color: var(--fg-muted); font-size: var(--fs-xs); }
  .rw-week { display: flex; gap: 5px; }
  .rw-week i { width: 22px; height: 22px; border-radius: 50%; border: 2px solid var(--border); display: grid; place-items: center; font-style: normal; font-size: .66rem; color: var(--accent-fg); }
  .rw-week i.full { background: var(--accent); border-color: var(--accent); }
  .rw-week i.rescued { background: color-mix(in oklab, var(--accent) 35%, var(--bg-card)); border-color: var(--accent); color: var(--accent); }
  .rw-week i.open { border-style: dashed; border-color: var(--accent); }
  .rw-week i.free, .rw-week i.before { border-style: dotted; }
  .rw-new { background: var(--warm-soft); border-radius: var(--r-sm); padding: 4px 8px; font-size: var(--fs-xs); justify-self: start; }
  .kid-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 0.4rem; }
  .kid-head h2 { margin: 0; font-size: 1.1rem; }
  .kid-name { display: flex; align-items: center; gap: 8px; }
  .kid-av { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; color: #fff; font-size: .8rem; font-weight: 800; }
  .plan { display: block; width: 100%; text-align: left; background: transparent; border: 0; padding: 0 0 6px; color: var(--fg); min-height: 0; }
  .plan .lbl { display: flex; justify-content: space-between; gap: 8px; font-size: 0.74rem; font-weight: 650; color: var(--fg-muted); margin: 4px 2px 2px; }
  .plan .lbl .dev, .plan .notes { color: var(--warn-fg); }
  .plan .notes { display: block; font-size: 0.74rem; margin: -2px 2px 4px; overflow-wrap: anywhere; }
  .strip { display: flex; align-items: center; gap: 6px; margin: 0 0 4px; }
  .strip .t { font-size: 0.74rem; color: var(--fg-muted); white-space: nowrap; font-variant-numeric: tabular-nums; }
  .strip .t.devt { color: var(--warn-fg); font-weight: 700; }
  .ps { display: flex; gap: 3px; flex: 1; min-width: 0; }
  .ps i { flex: 1; min-width: 0; overflow: hidden; font-style: normal; text-align: center; font-size: 0.72rem; font-weight: 650;
    padding: 5px 0; border-radius: 6px; background: color-mix(in srgb, var(--fg) 8%, var(--bg-card)); }
  .ps i.gap { flex: 0.35; background: transparent; }
  .ps i.empty { background: transparent; }
  .ps i.x { background: transparent; border: 1px dashed var(--cancelled); color: var(--cancelled); text-decoration: line-through; }
  .ps i.sub { outline: 2px solid var(--substitution); outline-offset: -2px; color: var(--substitution-fg); }
  .ps i.arbeit { outline: 2px solid var(--exam); outline-offset: -2px; }
  .ps i.now { box-shadow: 0 0 0 2px var(--accent) inset; }
  .ps i.past { opacity: 0.5; }
  .ps i.absent { text-decoration: underline dotted; }
  .why { margin: -0.2rem 0 0.5rem; font-size: 0.8rem; color: var(--fg-muted); overflow-wrap: anywhere; }
  .stale { margin: 0 0 0.6rem; font-size: 0.82rem; color: var(--warn-fg); }
  .pill { font-size: 0.8rem; font-weight: 650; padding: 3px 10px; border-radius: 999px; white-space: nowrap; }
  .pill.good { background: var(--good-bg); color: var(--good-fg); }
  .pill.warn { background: var(--warn-bg); color: var(--warn-fg); }
  .pill.bad { background: var(--bad-soft); color: var(--bad-fg); }

  button.okline {
    display: block; width: 100%; text-align: left; border: 0; border-radius: 10px; padding: 9px 10px;
    background: var(--good-bg); color: var(--good-fg); font-size: 0.88rem; font-weight: 550; min-height: 44px;
    margin-bottom: 0.2rem;
  }
  /* Offenes Lernen ist kein Versäumnis: neutral statt grün (D180). */
  button.okline.study.open { background: var(--bg-elevated); color: var(--fg); }
  .row {
    display: flex; gap: 10px; align-items: flex-start; width: 100%; text-align: left; min-height: 48px;
    padding: 9px 4px; background: transparent; color: var(--fg); border: 0; border-top: 1px solid var(--border);
    border-radius: 0;
  }
  .row .ic { width: 22px; flex: none; text-align: center; }
  .row .tx { flex: 1; min-width: 0; overflow-wrap: anywhere; }
  .row .tx b { font-weight: 600; }
  .row.bad .tx b { color: var(--bad-fg); }
  .row.warn .tx b { color: var(--warn-fg); }
  .row small, .l3, .when, .later { color: var(--fg-muted); }
  .row small { display: block; font-size: 0.8rem; margin-top: 1px; }
  .go { color: var(--accent); flex: none; align-self: center; }
  .sec {
    font-size: 0.74rem; letter-spacing: 0.04em; text-transform: uppercase; color: var(--fg-muted);
    margin: 0.9rem 2px 0.3rem; font-weight: 650;
  }
  .exam {
    display: block; width: 100%; text-align: left; background: transparent; color: var(--fg);
    border: 0; border-top: 1px solid var(--border); border-radius: 0; padding: 9px 4px;
  }
  .sec + .exam { border-top: 0; }
  .l1 { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
  .l1 b { font-weight: 600; overflow-wrap: anywhere; }
  .when { font-size: 0.8rem; white-space: nowrap; }
  .when.hot { color: var(--bad-fg); font-weight: 650; }
  .stack { display: grid; margin-top: 6px; }
  .stack i, .legend i { display: block; height: 100%; }
  .sitzt { background: var(--s-sitzt); } .wackelt { background: var(--s-wackelt); }
  .angefangen { background: var(--s-angefangen); } .neu { background: var(--s-neu); }
  .l3 { display: flex; justify-content: space-between; gap: 8px; font-size: 0.8rem; margin-top: 4px; }
  .badge { display: inline-block; font-size: 0.74rem; font-weight: 650; padding: 1px 7px; border-radius: 999px; margin-left: 4px; white-space: nowrap; }
  .badge.warn { background: var(--warn-bg); color: var(--warn-fg); }
  .badge.bad { background: var(--bad-soft); color: var(--bad-fg); }
  .badge.mute { background: var(--bg-elevated); color: var(--fg-muted); border: 1px solid var(--border); }
  .later { font-size: 0.84rem; padding: 8px 4px 0; margin: 0; border-top: 1px solid var(--border); line-height: 2; }
  .link { background: transparent; border: 0; padding: 0; min-height: 0; color: var(--accent); font: inherit; text-decoration: underline; text-underline-offset: 2px; }
  .legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 0.8rem; color: var(--fg-muted); margin: 0.8rem 2px; }
  .legend i { display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }
</style>
