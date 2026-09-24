<script>
  import ActionLabel from './ActionLabel.svelte';
  import { api } from './api.js';
  import { splitLessons, splitTasks } from './dayDashboard.js';
  let { kid, day, open } = $props();
  let school = $state(null), bag = $state(null), error = $state('');
  let loading = $state(true);
  const tasks = $derived(splitTasks(kid.tasks.items, day));
  const feedback = $derived(school ? splitLessons(school.lessons, school.date, new Date()).open.length : null);
  const overdue = $derived(tasks.due.filter(t=>t.due_date < day).length);
  const feedbackCount = $derived(Math.max(feedback ?? 0, kid.feedback_gap?.unrated_lessons ?? 0));
  const taskStatus = $derived(overdue ? 'problem' : tasks.due.length || tasks.undated.length ? 'attention' : 'good');
  const bagStatus = $derived(!bag ? 'unknown' : bag.confirmed_count < bag.items.length ? 'attention' : 'good');
  const overall = $derived(error || loading || !bag ? 'unknown' : overdue ? 'problem' : taskStatus === 'attention' || bagStatus === 'attention' || feedbackCount || kid.support.length ? 'attention' : 'good');
  const statusText = {good:'✓ Im Griff',attention:'Offene Punkte',problem:'Überfällig',unknown:'Stand prüfen'};
  const packDate = $derived(school?.next?.date ? new Date(school.next.date+'T12:00:00').toLocaleDateString('de-DE',{weekday:'short',day:'numeric',month:'numeric'}) : '');
  $effect(() => {
    const account = kid.account_id;
    const date = day;
    let active = true;
    school = null; bag = null; error = ''; loading = true;
    async function load() {
      try {
        const result = await api.get(`/api/accounts/${account}/today`);
        if (!Array.isArray(result.lessons) || result.date !== date) throw new Error('Tagesstand bitte aktualisieren.');
        const nextBag = result.next ? await api.get(`/api/accounts/${account}/packing/${result.next.date}`) : null;
        if (nextBag && (!Array.isArray(nextBag.items) || nextBag.school_day !== result.next.date || !Number.isInteger(nextBag.confirmed_count))) throw new Error('Materialstand nicht verfügbar.');
        if (active) { school = result; bag = nextBag; }
      } catch (e) { if (active) error = e.message; }
      finally { if (active) loading = false; }
    }
    load();
    return () => { active = false; };
  });
</script>

<div class="day-check" data-status={overall} aria-label={`Tagescheck für ${kid.name}`}>
  <strong class="overall">{statusText[overall]}</strong>
  <button data-status={taskStatus} onclick={() => open(kid, 'today')}>
    <span aria-hidden="true">📝</span><span><strong>{overdue ? `${overdue} ${overdue===1?'Aufgabe':'Aufgaben'} überfällig` : tasks.due.length ? `${tasks.due.length} ${tasks.due.length === 1 ? 'Aufgabe' : 'Aufgaben'} bis morgen offen` : 'Für morgen nichts mehr offen'}</strong>
    {#if tasks.undated.length}<small>{tasks.undated.length} ohne Termin · bitte einordnen</small>{/if}
    {#if tasks.ahead.length}<small>{tasks.ahead.length} {tasks.ahead.length === 1 ? 'weitere Aufgabe' : 'weitere Aufgaben'} · später fällig</small>{/if}</span><span class="nav-mark"><ActionLabel /></span>
  </button>
  {#if loading}<p class="small dim">Tagescheck wird geladen …</p>
  {:else if error}<p class="error-box" role="alert">{error}</p>
  {:else}
    <button data-status={bagStatus} onclick={() => open(kid, 'today')}>
      <span aria-hidden="true">🎒</span><span><strong>{bag ? (bag.items.length ? `${bag.confirmed_count} von ${bag.items.length} Fächern abgehakt` : 'Keine Fachmaterialien im Plan') : 'Noch kein nächster Schultag im Plan'}</strong>
      {#if packDate}<small>Material für {packDate}</small>{/if}</span><span class="nav-mark"><ActionLabel /></span>
    </button>
    <button data-status={feedbackCount ? 'attention' : 'good'} onclick={() => open(kid, 'week')}>
      <span aria-hidden="true">🗣️</span><span><strong>{feedbackCount ? `${feedbackCount} ${feedbackCount === 1 ? 'Rückmeldung' : 'Rückmeldungen'} offen` : 'Keine Rückmeldungen offen'}</strong><small>Rückmeldungen · letzte 7 Tage und heute</small></span><span class="nav-mark"><ActionLabel /></span>
    </button>
  {/if}
</div>

<style>
  .day-check { display:grid; gap:.45rem; padding:.7rem; background:var(--bg-elevated); border-radius:14px; }
  button { display:flex; gap:.65rem; align-items:center; text-align:left; width:100%; min-height:48px; background:var(--bg-card); color:var(--fg); border:1px solid var(--border); border-radius:10px; padding:.6rem; }
  [data-status="good"]{background:color-mix(in srgb,var(--rating-3) 13%,var(--bg-card));border-color:color-mix(in srgb,var(--rating-3) 45%,var(--border))}
  [data-status="attention"]{background:color-mix(in srgb,var(--rating-2) 15%,var(--bg-card));border-color:color-mix(in srgb,var(--rating-2) 55%,var(--border))}
  [data-status="problem"]{background:color-mix(in srgb,var(--rating-1) 14%,var(--bg-card));border-color:var(--rating-1)}
  .overall{padding:2px 4px;font-size:1rem}
  button > span:first-child { font-size:1.3rem; }
  button > span:nth-child(2) { min-width:0; overflow-wrap:anywhere; }
  .nav-mark{margin-left:auto;flex:none;color:var(--accent)}
  strong { font-size:.9rem; }
  small { display:block; color:var(--fg-muted); margin-top:.2rem; }
</style>
