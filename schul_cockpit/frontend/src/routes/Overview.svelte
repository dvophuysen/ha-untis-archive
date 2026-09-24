<script>
  import ActionLabel from '../lib/ActionLabel.svelte';
  import {subjectStyle} from '../lib/subjectStyle.js';
  import { untrack } from 'svelte';
  import FamilyDayCheck from '../lib/FamilyDayCheck.svelte';
  import WeekReview from '../lib/WeekReview.svelte';
  import UsageWeek from '../lib/UsageWeek.svelte';
  import ParentReportSettings from '../lib/ParentReportSettings.svelte';
  import { api } from '../lib/api.js';
  import { setActiveAccount } from '../lib/store.svelte.js';

  let { navigate } = $props();

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

  function open(kid, page = 'today', ...args) {
    setActiveAccount(kid.account_id);
    navigate(page, ...args);
  }

  function planDate(iso) {
    return iso.slice(8, 10) + '.' + iso.slice(5, 7) + '.';
  }
</script>

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if error}
  <div class="error-box">{error}</div>
{:else if data && data.kids.length === 0}
  <div class="empty">Noch keine Kinder verlinkt.</div>
{:else if data}
  <div class="dash">
    {#each data.kids as kid (kid.account_id)}
      <section class="kid card">
        <header class="kid-head">
          <h2>{kid.name}</h2>
          <button class="ghost open-btn" onclick={() => open(kid, 'today')}>Kinderansicht <ActionLabel /></button>
        </header>

        <div class="now">{kid.now.icon} {kid.now.label}</div>
        <FamilyDayCheck {kid} day={data.today} {open} />
        <WeekReview accountId={kid.account_id} />
        <UsageWeek accountId={kid.account_id} />

        <div class="summary-links">
          <button class="summary-link" onclick={() => open(kid, 'klausuren')}><span>Arbeiten & Tests</span><strong>{kid.exams.length ? `${kid.exams.length} angekündigt` : 'Keine eingetragen'} <ActionLabel /></strong></button>
          <button class="summary-link" class:needs-attention={kid.support.length > 0} onclick={() => open(kid, 'subjects')}><span>Fächer</span><strong>{kid.support.length ? `${kid.support.length} mit offenen Fragen` : 'Keine gehäuften Fragen'} <ActionLabel /></strong></button>
          {#if kid.support.length}<div class="support-subjects">{#each kid.support as s}<button onclick={() => open(kid, 'subject', s.subject_id)}>{subjectStyle(s.subject_name || s.subject_short).emoji} {subjectStyle(s.subject_name || s.subject_short).name} <ActionLabel /></button>{/each}</div>{/if}
        </div>
        <!-- Plan-Grid: fixe Periodenzeilen, damit gleiche Stunden über die
             Tage hinweg untereinander stehen (wie das Woche-Layout). -->
        <div class="block">
          <h3><button class="schedule-link" onclick={() => open(kid, 'week')}>Stundenplan {kid.plan.is_weekend ? '· nächste Woche' : kid.plan.columns.some((c) => c.is_filler) ? '· die nächsten fünf Schultage' : '· diese Woche'} <ActionLabel /></button></h3>
          <div
            class="plan-grid"
            style="grid-template-rows: auto repeat({kid.plan.period_times.length || 1}, minmax(26px, auto));"
          >
            {#each kid.plan.columns as col, ci}
              {#if col.is_today}
                <div
                  class="plan-today-frame"
                  style="grid-column: {ci + 1}; grid-row: 1 / span {kid.plan.period_times.length + 1};"
                ></div>
              {/if}
              <div
                class="plan-head"
                class:is-today={col.is_today}
                class:filler={col.is_filler}
                style="grid-column: {ci + 1}; grid-row: 1;"
              >
                <strong>{col.weekday}</strong>
                <span class="plan-date">{planDate(col.date)}</span>
              </div>
            {/each}

            {#each kid.plan.period_times as t, pi}
              {#each kid.plan.columns as col, ci}
                {@const l = col.lessons.find((x) => x.start_hhmm === t)}
                <div class="plan-slot" style="grid-column: {ci + 1}; grid-row: {pi + 2};">
                  {#if l}
                    <button
                      class="plan-cell"
                      class:cancelled={l.is_cancelled}
                      class:substitution={!l.is_cancelled && (l.is_irregular || l.is_subject_substituted)}
                      class:has-exam={l.has_exam}
                      onclick={() => open(kid, 'week')}
                      title={(l.start_hhmm ?? '') + ' ' + (l.subject_name ?? '')}
                    >
                      {#if l.is_cancelled}
                        <span class="cell-old">{l.subject_orig_short || l.subject_short}</span>
                      {:else if l.is_subject_substituted && l.subject_orig_short}
                        <span class="cell-old">{l.subject_orig_short}</span>
                        <span class="cell-new">{l.subject_short}</span>
                      {:else}
                        <span class="cell-label">{l.subject_short}</span>
                        {#if l.is_irregular || l.is_teacher_substituted || l.is_room_substituted}
                          <span class="cell-swap">⇄</span>
                        {/if}
                      {/if}
                      {#if l.has_exam && !l.is_cancelled}
                        <span class="cell-exam">📝</span>
                      {/if}
                    </button>
                  {/if}
                </div>
              {/each}
            {/each}
          </div>
        </div>

      </section>
    {/each}
  </div>
  <ParentReportSettings />
{/if}

<style>
  .summary-links{display:grid;gap:8px}.summary-link{display:flex;justify-content:space-between;align-items:center;gap:12px;text-align:left;border:1px solid var(--border);border-radius:10px;padding:12px;background:var(--bg-elevated);font-size:.9rem}.summary-link strong{font-size:.85rem}.needs-attention{background:color-mix(in srgb,var(--rating-2) 15%,var(--bg-card))}.support-subjects{display:flex;flex-wrap:wrap;gap:6px}.support-subjects button{font-size:.85rem;min-height:44px}.schedule-link{background:transparent;border:0;padding:8px 0;text-align:left;color:var(--accent);min-height:44px}
  .dash {
    display: grid;
    gap: 1rem;
    grid-template-columns: 1fr;
  }
  @media (min-width: 720px) {
    .summary-links{display:grid;gap:8px}.summary-link{display:flex;justify-content:space-between;align-items:center;gap:12px;text-align:left;border:1px solid var(--border);border-radius:10px;padding:12px;background:var(--bg-elevated);font-size:.9rem}.summary-link strong{font-size:.85rem}.needs-attention{background:color-mix(in srgb,var(--rating-2) 15%,var(--bg-card))}.support-subjects{display:flex;flex-wrap:wrap;gap:6px}.support-subjects button{font-size:.85rem;min-height:44px}.schedule-link{background:transparent;border:0;padding:8px 0;text-align:left;color:var(--accent);min-height:44px}
  .dash { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }

  .kid { padding: 0.8rem; display: flex; flex-direction: column; gap: 0.5rem; }
  .kid-head { display: flex; justify-content: space-between; align-items: center; }
  .kid-head h2 { margin: 0; font-size: 1.05rem; }
  .open-btn { font-size: 0.85rem; min-height: 32px; padding: 0.2rem 0.5rem; }

  .now {
    font-size: 0.85rem;
    color: var(--fg-muted);
    padding: 0.3rem 0.1rem;
    border-bottom: 1px solid var(--border);
  }

  .block { padding-top: 0.4rem; }
  .block h3 {
    margin: 0 0 0.35rem;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--fg-muted);
    display: flex; align-items: center; gap: 0.4rem;
    font-weight: 700;
  }

  /* Plan-Grid — fünf feste Mo–Fr-Spalten, eine Zeile pro Periode (über
     alle Tage hinweg gemeinsame Startzeit). Vergangene Wochentage rollen
     in die Folgewoche; „heute" bekommt einen Rahmen, der per Overlay
     hinter den Zellen läuft, damit die Zellen sauber alignt bleiben. */
  .plan-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    column-gap: 3px;
    row-gap: 2px;
    position: relative;
  }
  .plan-today-frame {
    outline: 2px solid var(--accent);
    background: color-mix(in oklab, var(--accent) 8%, transparent);
    border-radius: 6px;
    pointer-events: none;
    z-index: 0;
  }
  .plan-head, .plan-slot { position: relative; z-index: 1; }
  .plan-head { text-align: center; padding: 0.15rem 0 0.25rem; line-height: 1.1; }
  .plan-head strong { font-size: 0.75rem; }
  .plan-head.is-today strong { color: var(--accent); }
  .plan-head.filler .plan-date { color: var(--fg-dim); }
  .plan-date { display: block; font-size: 0.65rem; color: var(--fg-muted); }

  .plan-slot { display: flex; min-width: 0; }
  .plan-cell {
    position: relative;
    flex: 1;
    border: 1px solid var(--border);
    background: var(--bg-elevated);
    padding: 0.18rem 0.15rem;
    font-size: 0.68rem;
    line-height: 1.1;
    border-radius: 4px;
    cursor: pointer;
    min-height: 24px;
    color: var(--fg);
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.2rem;
  }
  .plan-cell.cancelled {
    background: var(--bg-elevated);
    border-style: dashed;
    color: var(--fg-dim);
  }
  .plan-cell.substitution { outline: 1px solid var(--substitution); }
  .plan-cell.has-exam { outline: 2px solid var(--exam); }

  .cell-label { font-weight: 500; }
  .cell-old {
    text-decoration: line-through;
    color: var(--fg-dim);
    font-weight: 400;
  }
  .cell-new { font-weight: 600; color: var(--substitution-fg); }
  .cell-swap { font-size: 0.65rem; color: var(--substitution-fg); }
  .cell-exam {
    position: absolute;
    top: -5px; right: -4px;
    font-size: 0.6rem;
    background: var(--bg-card);
    border-radius: 50%;
    padding: 0 1px;
    line-height: 1;
  }

</style>
