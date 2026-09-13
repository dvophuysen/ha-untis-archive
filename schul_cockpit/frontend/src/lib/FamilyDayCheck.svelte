<script>
  import { api } from './api.js';
  import { splitLessons, splitTasks } from './dayDashboard.js';
  let { kid, day, open } = $props();
  let school = $state(null), bag = $state(null), error = $state('');
  let loading = $state(true);
  const tasks = $derived(splitTasks(kid.tasks.items, day));
  const feedback = $derived(school ? splitLessons(school.lessons, school.date, new Date()).open.length : null);
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

<div class="day-check" aria-label={`Tagescheck für ${kid.name}`}>
  <button onclick={() => open(kid, 'today')}>
    <span aria-hidden="true">📝</span><span><strong>{tasks.due.length ? `${tasks.due.length} ${tasks.due.length === 1 ? 'Aufgabe' : 'Aufgaben'} bis morgen offen` : 'Für morgen nichts mehr offen'}</strong>
    {#if tasks.undated.length}<small>{tasks.undated.length} ohne Termin · bitte einordnen</small>{/if}
    {#if tasks.ahead.length}<small>{tasks.ahead.length} für später</small>{/if}</span>
  </button>
  {#if loading}<p class="small dim">Tagescheck wird geladen …</p>
  {:else if error}<p class="error-box" role="alert">{error}</p>
  {:else}
    <button onclick={() => open(kid, 'today')}>
      <span aria-hidden="true">🎒</span><span><strong>{bag ? (bag.items.length ? `${bag.confirmed_count} von ${bag.items.length} Fächern abgehakt` : 'Keine Fachmaterialien im Plan') : 'Noch kein nächster Schultag im Plan'}</strong>
      {#if packDate}<small>Material für {packDate}</small>{/if}</span>
    </button>
    <button onclick={() => open(kid, 'today')}>
      <span aria-hidden="true">💬</span><span><strong>{feedback ? `${feedback} ${feedback === 1 ? 'Rückmeldung' : 'Rückmeldungen'} offen` : 'Keine Rückmeldungen offen'}</strong><small>Heute beendete Stunden</small></span>
    </button>
  {/if}
</div>

<style>
  .day-check { display:grid; gap:.45rem; padding:.7rem; background:var(--accent-soft); border-radius:14px; }
  button { display:flex; gap:.65rem; align-items:center; text-align:left; width:100%; min-height:48px; background:var(--bg-card); color:var(--fg); border:1px solid var(--border); border-radius:10px; padding:.6rem; }
  button > span:first-child { font-size:1.3rem; }
  button > span:last-child { min-width:0; overflow-wrap:anywhere; }
  strong { font-size:.9rem; }
  small { display:block; color:var(--fg-muted); margin-top:.2rem; }
</style>
