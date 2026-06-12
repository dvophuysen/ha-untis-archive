<script>
  import { api } from '../lib/api.js';
  import { setActiveAccount } from '../lib/store.svelte.js';

  let { navigate } = $props();

  let data = $state(null);
  let loading = $state(true);
  let error = $state(null);

  async function load() {
    loading = true;
    error = null;
    try {
      data = await api.get('/api/dashboard');
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { load(); });

  const PRIO_DOT = { red: '🔴', orange: '🟠', green: '🟢' };
  const LEARN_EMOJI = ['⚪', '😟', '😐', '😀'];
  const URG_DOT = { missed: '❗', red: '🔴', orange: '🟠', green: '🟢' };

  function open(kid, page = 'today', ...args) {
    setActiveAccount(kid.account_id);
    navigate(page, ...args);
  }

  function whenLabel(iso, days) {
    if (days === 0) return 'heute';
    if (days === 1) return 'morgen';
    if (days <= 6) {
      const d = new Date(iso + 'T00:00:00');
      return d.toLocaleDateString('de-DE', { weekday: 'short' });
    }
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
  }

  function dueLabel(iso) {
    if (!iso) return '';
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const d = new Date(iso + 'T00:00:00');
    const delta = Math.round((d - today) / 86400000);
    if (delta < 0) return 'verpasst';
    if (delta === 0) return 'heute';
    if (delta === 1) return 'morgen';
    if (delta <= 6) return d.toLocaleDateString('de-DE', { weekday: 'short' });
    if (delta <= 13) return 'nä. Wo.';
    return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
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
          <button class="ghost open-btn" onclick={() => open(kid, 'today')}>öffnen →</button>
        </header>

        <div class="now">{kid.now.icon} {kid.now.label}</div>

        <!-- Klausuren -->
        <div class="block">
          <h3>Klausuren {#if kid.exams.length}<span class="count">{kid.exams.length}</span>{/if}</h3>
          {#if kid.exams.length === 0}
            <div class="small dim">keine geplant</div>
          {:else}
            <div class="exam-table">
              {#each kid.exams as e}
                <button class="ex-row" onclick={() => open(kid, 'klausuren')}>
                  <span class="ex-dot">{PRIO_DOT[e.priority]}</span>
                  <span class="ex-subj">{e.subject_short}</span>
                  <span class="ex-when">{whenLabel(e.date, e.days_until)}</span>
                  <span class="ex-days">{e.days_until}</span>
                  <span class="ex-learn">{LEARN_EMOJI[e.learn_state ?? 0]}</span>
                  <span class="ex-hard">
                    {#if e.comprehension && e.comprehension.hard > 0}⚠{e.comprehension.hard}{/if}
                  </span>
                </button>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Mitlernen -->
        <div class="block">
          <h3>Mitlernen <span class="emoji-h">🤝</span></h3>
          {#if kid.support.length === 0}
            <div class="small dim">alles im grünen Bereich</div>
          {:else}
            <div class="sup-table">
              {#each kid.support as s}
                <button class="sup-row" onclick={() => open(kid, 'subject', s.subject_id)}>
                  <span class="sup-subj">{s.subject_short || s.subject_name}</span>
                  <span class="sup-hard">⚠ {s.hard_count}</span>
                  <span class="sup-total">/{s.total_count}</span>
                </button>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Hausaufgaben -->
        <div class="block">
          <h3>Hausaufgaben {#if kid.tasks.open_count}<span class="count">{kid.tasks.open_count}</span>{/if}</h3>
          {#if kid.tasks.open_count === 0}
            <div class="small dim">keine offenen Aufgaben</div>
          {:else}
            <div class="hw-table">
              {#each kid.tasks.items as t}
                <button class="hw-row" onclick={() => open(kid, 'plan')}>
                  <span class="hw-dot">{URG_DOT[t.urgency] ?? ''}</span>
                  <span class="hw-subj">{t.subject_short}</span>
                  <span class="hw-title">{t.title}</span>
                  <span class="hw-when">{dueLabel(t.due_date)}</span>
                </button>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Plan-Grid -->
        <div class="block">
          <h3>Plan {#if kid.plan.is_weekend}<span class="small dim">· nächste Woche</span>{/if}</h3>
          <div class="plan-grid">
            {#each kid.plan.columns as col}
              <div class="plan-col" class:is-today={col.is_today} class:filler={col.is_filler}>
                <div class="plan-head">
                  <strong>{col.weekday}</strong>
                  <span class="plan-date">{planDate(col.date)}</span>
                </div>
                <div class="plan-cells">
                  {#each col.lessons as l}
                    <button
                      class="plan-cell"
                      class:cancelled={l.is_cancelled}
                      class:substitution={l.is_irregular && !l.is_cancelled}
                      class:has-exam={l.has_exam}
                      onclick={() => open(kid, 'week')}
                      title={(l.start_hhmm ?? '') + ' ' + (l.subject_name ?? '')}
                    >
                      <span class="plan-label">{l.subject_short}</span>
                      {#if l.has_exam}<span class="plan-mark">📝</span>
                      {:else if l.is_cancelled}<span class="plan-mark">🛑</span>
                      {:else if l.is_irregular}<span class="plan-mark">🔁</span>{/if}
                    </button>
                  {/each}
                  {#if col.lessons.length === 0}
                    <div class="plan-empty">–</div>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        </div>

        <!-- Feedback-Hygiene -->
        {#if kid.feedback_gap.total_lessons > 0}
          <div class="block hyg-block">
            {#if kid.feedback_gap.unrated_lessons === 0}
              <div class="small dim">🩺 alles bewertet (7 Tage)</div>
            {:else}
              <button class="hyg-row" onclick={() => open(kid, 'week')}>
                🩺 <strong>{kid.feedback_gap.unrated_lessons}</strong>
                Stunden noch ohne Feedback
              </button>
            {/if}
          </div>
        {/if}
      </section>
    {/each}
  </div>
{/if}

<style>
  .dash {
    display: grid;
    gap: 1rem;
    grid-template-columns: 1fr;
  }
  @media (min-width: 720px) {
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
  .emoji-h { font-size: 0.85rem; }
  .count {
    background: var(--bg-elevated);
    color: var(--fg);
    padding: 0 0.4rem;
    border-radius: 8px;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: none;
    letter-spacing: 0;
    border: 1px solid var(--border);
  }
  .small { font-size: 0.8rem; }

  /* Generic table-row buttons share a row look. */
  .ex-row, .sup-row, .hw-row {
    display: grid; align-items: center; gap: 0.4rem;
    background: transparent; border: none;
    padding: 0.3rem 0.25rem;
    min-height: 30px;
    border-radius: 5px;
    color: var(--fg);
    text-align: left;
    cursor: pointer;
    font-size: 0.86rem;
  }
  .ex-row:hover, .sup-row:hover, .hw-row:hover { background: var(--bg-elevated); }

  /* Klausuren: Ampel · Fach · Wann · Tage · Lern · Sorgen */
  .ex-row { grid-template-columns: 18px 38px 1fr 28px 24px 32px; }
  .ex-dot { text-align: center; }
  .ex-subj { font-weight: 600; }
  .ex-when { color: var(--fg-muted); font-size: 0.8rem; }
  .ex-days { color: var(--fg-dim); font-size: 0.78rem; text-align: right; font-variant-numeric: tabular-nums; }
  .ex-learn { text-align: center; }
  .ex-hard { color: var(--rating-2); font-size: 0.74rem; text-align: right; }

  /* Mitlernen */
  .sup-row { grid-template-columns: 1fr auto auto; }
  .sup-subj { font-weight: 600; }
  .sup-hard { color: var(--rating-2); font-size: 0.82rem; }
  .sup-total { color: var(--fg-dim); font-size: 0.78rem; }

  /* Hausaufgaben */
  .hw-row { grid-template-columns: 18px 36px 1fr auto; }
  .hw-dot { text-align: center; }
  .hw-subj { font-weight: 600; }
  .hw-title {
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    min-width: 0;
  }
  .hw-when { color: var(--fg-muted); font-size: 0.78rem; }

  /* Plan-Grid — Mo–Fr Spalten, vergangene Wochentage rollen in die
     Folgewoche. Heute wird durch einen dezenten Rahmen markiert. */
  .plan-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 3px;
  }
  .plan-col {
    display: flex;
    flex-direction: column;
    min-width: 0;
    padding: 2px;
    border-radius: 6px;
  }
  .plan-col.is-today {
    outline: 2px solid var(--accent);
    background: color-mix(in oklab, var(--accent) 8%, transparent);
  }
  .plan-col.filler .plan-date { color: var(--fg-dim); }
  .plan-head { text-align: center; padding: 0.15rem 0; line-height: 1.1; }
  .plan-head strong { font-size: 0.75rem; }
  .plan-date { display: block; font-size: 0.65rem; color: var(--fg-muted); }
  .plan-col.is-today .plan-head strong { color: var(--accent); }

  .plan-cells { display: flex; flex-direction: column; gap: 2px; }
  .plan-cell {
    position: relative;
    border: 1px solid var(--border);
    background: var(--bg-elevated);
    padding: 0.18rem 0.1rem;
    font-size: 0.66rem;
    line-height: 1.1;
    border-radius: 4px;
    cursor: pointer;
    min-height: 22px;
    color: var(--fg);
    text-align: center;
  }
  .plan-cell.cancelled {
    background: var(--cancelled);
    color: #fff;
    text-decoration: line-through;
    opacity: 0.7;
  }
  .plan-cell.substitution { outline: 1px solid var(--substitution); }
  .plan-cell.has-exam { outline: 2px solid var(--exam); }
  .plan-label {
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .plan-mark {
    position: absolute;
    top: -4px; right: -3px;
    font-size: 0.6rem;
    background: var(--bg-card);
    border-radius: 50%;
    padding: 0 1px;
    line-height: 1;
  }
  .plan-empty {
    color: var(--fg-dim);
    text-align: center;
    font-size: 0.7rem;
    padding: 0.3rem 0;
  }

  /* Hygiene */
  .hyg-block { border-top: 1px dashed var(--border); margin-top: 0.2rem; padding-top: 0.5rem; }
  .hyg-row {
    width: 100%;
    background: transparent;
    border: none;
    text-align: left;
    color: var(--fg-muted);
    font-size: 0.82rem;
    padding: 0.2rem 0;
    cursor: pointer;
    min-height: auto;
  }
  .hyg-row strong { color: var(--rating-2); }
</style>
