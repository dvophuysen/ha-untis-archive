<script>
  // Startseite der Eltern (D166): je Kind eine Karte. Oben der Status, dann was
  // jetzt offen ist, die Arbeiten chronologisch mit dem Lernstand ihrer Themen,
  // zuletzt was sich über Wochen abzeichnet. Jeder Baustein springt zum Kind in
  // den passenden Abschnitt. Die Seite „Heute“ des Kindes wird nicht wiederholt.
  import ActionLabel from '../lib/ActionLabel.svelte';
  import { subjectStyle } from '../lib/subjectStyle.js';
  import { untrack } from 'svelte';
  import ParentReportSettings from '../lib/ParentReportSettings.svelte';
  import { api } from '../lib/api.js';
  import { setActiveAccount } from '../lib/store.svelte.js';
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
    window.location.hash = jumpHash(target);
  }

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
          <h2>{kid.name}</h2>
          <span class="pill {b.status.level}">{b.status.label}</span>
        </header>
        {#if b.status.level !== 'good' && b.status.reasons.length}
          <p class="why">{b.status.reasons.slice(0, 3).join(' · ')}</p>
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
                <span class="stack" role="img" aria-label={`Lernstand: ${stageText(x)}`}>
                  {#each STAGES as [k] (k)}{#if x.stages[k]}<i class={k} style="flex:{x.stages[k]}"></i>{/if}{/each}
                </span>
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

        <button class="ghost child-view" onclick={() => open(kid, { page: 'today' })}><ActionLabel label={`Kinderansicht ${kid.name}`} /></button>
      </section>
    {/each}
  </div>
  <p class="legend" aria-hidden="true">
    {#each STAGES as [k, label] (k)}<span><i class={k}></i>{label}</span>{/each}
  </p>
  <ParentReportSettings />
{/if}

<style>
  .dash { display: grid; gap: 1rem; grid-template-columns: 1fr; align-items: start; }
  @media (min-width: 720px) { .dash { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  .kid, .legend { --s-sitzt: #059669; --s-wackelt: #d97706; --s-angefangen: #f59e0b; --s-neu: #cbd5e1; }
  .kid {
    --warn-bg: var(--warm-soft); --good-bg: color-mix(in srgb, var(--good-fg) 12%, var(--bg-card));
    padding: 0.8rem; display: flex; flex-direction: column; gap: 0.1rem; min-width: 0;
  }
  @media (prefers-color-scheme: dark) {
    .kid, .legend { --s-sitzt: #34d399; --s-wackelt: #fbbf24; --s-angefangen: #fb923c; --s-neu: #475569; }
  }
  .kid-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 0.4rem; }
  .kid-head h2 { margin: 0; font-size: 1.1rem; }
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
  .stack { display: flex; height: 8px; border-radius: 5px; overflow: hidden; background: var(--s-neu); gap: 2px; margin-top: 6px; }
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
  .child-view { align-self: flex-end; font-size: 0.85rem; color: var(--accent); min-height: 44px; margin-top: 0.4rem; }
  .legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 0.8rem; color: var(--fg-muted); margin: 0.8rem 2px; }
  .legend i { display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }
</style>
