<script>
  import ActionLabel from '../lib/ActionLabel.svelte';
  import { subjectStyle } from '../lib/subjectStyle.js';
  import { api } from '../lib/api.js';
  import { formatShortDate } from '../lib/format.js';
  let { accountId, navigate } = $props();
  let subjects = $state([]), suggestions = $state(null), loading = $state(true), error = $state('');
  let expanded = $state(null);
  $effect(() => {
    const account = accountId; let active = true;
    loading = true; error = ''; subjects = []; suggestions = null; expanded = null;
    if (account) Promise.all([api.get(`/api/accounts/${account}/subjects`), api.get(`/api/accounts/${account}/oral-suggestions`)]).then(([subs, sug]) => {
      if (active) { subjects = subs.subjects; suggestions = sug; }
    }).catch(e => { if (active) error = e.message; }).finally(() => { if (active) loading = false; });
    else loading = false;
    return () => { active = false; };
  });
  function hour(value) { if (value == null) return ''; const s = String(value).replace(':', '').padStart(4, '0'); return s.slice(0, 2) + ':' + s.slice(2); }
  const ratingText = r => r === 3 ? 'Verstanden' : r === 2 ? 'Teilweise verstanden' : r === 1 ? 'Noch schwierig' : 'Ohne Einschätzung';
  const rows = $derived.by(() => subjects.map(s => {
    const group = suggestions?.groups?.find(g => String(g.subject_id) === String(s.subject_id));
    const good = group?.understood_topics || 0, partial = group?.partial_topics || 0;
    const difficult = group?.difficult_topics ?? Math.max(0, (group?.uncertain_topics || 0) - partial);
    const unknown = group?.unrated_topics || 0, known = good + partial + difficult;
    const history = (group?.feedback_history || []).filter(p => [1, 2, 3].includes(p.rating));
    return { ...s, group, good, partial, difficult, unknown, known, total: known + unknown, history };
  }).sort((a, b) => Number(b.known > 0) - Number(a.known > 0)
    || (a.known && b.known ? b.good / b.known - a.good / a.known : 0)
    || subjectStyle(a.name).name.localeCompare(subjectStyle(b.name).name, 'de')));
  function points(history) { return history.map((p, i) => `${3 + i * 66 / Math.max(1, history.length - 1)},${23 - (p.rating - 1) * 10}`).join(' '); }
</script>

<header class="page-heading"><h1>Deine Fächer</h1><p class="dim">Erfasste Themen · deine Selbsteinschätzungen</p></header>
{#if loading}<div class="empty"><span class="spinner"></span></div>
{:else if error}<div class="error-box" role="alert">{error}</div>
{:else}
  {#each suggestions?.errors || [] as warning}<p class="error-box" role="alert">{warning}</p>{/each}
  {#if !rows.length}<p class="empty">Noch keine Fächer vorhanden.</p>{/if}
  <div class="subject-list">
    {#each rows as s (s.subject_id)}
      <section class="subject-entry">
        <button class="subject-row" aria-expanded={expanded === s.subject_id} aria-controls={`subject-panel-${s.subject_id}`} onclick={() => expanded = expanded === s.subject_id ? null : s.subject_id}>
          <span class="subject-copy">
            <span class="subject-name"><span aria-hidden="true">{subjectStyle(s.name).emoji}</span> {subjectStyle(s.name).name}</span>
            {#if s.known}
              <span class="subject-bar" role="img" aria-label={`${s.good} Themen verstanden, ${s.partial} teilweise, ${s.difficult} noch schwierig, ${s.unknown} ohne Einschätzung`}>
                <span class="good" style:width={`${100 * s.good / s.total}%`}></span><span class="partial" style:width={`${100 * s.partial / s.total}%`}></span><span class="difficult" style:width={`${100 * s.difficult / s.total}%`}></span><span class="unknown" style:width={`${100 * s.unknown / s.total}%`}></span>
              </span>
              <small>{s.good} von {s.known} verstanden{#if s.unknown} · {s.unknown} offen{/if}</small>
            {:else}<small>Noch keine Einschätzung</small>{/if}
          </span>
          <span class="trend">
            {#if s.history.length > 1}
              <svg viewBox="0 0 72 26" role="img" aria-label={`Verlauf der letzten ${s.history.length} Rückmeldungen: ${s.history.map(p => ratingText(p.rating)).join(', ')}`}><polyline points={points(s.history)} fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" /></svg>
              <small>Verlauf</small>
            {:else}<small>Noch kein<br />Verlauf</small>{/if}
          </span>
          <span class="chevron" class:opened={expanded === s.subject_id}><ActionLabel /></span>
        </button>
        {#if expanded === s.subject_id}
          <div class="subject-panel" id={`subject-panel-${s.subject_id}`} role="region" aria-label={`Details ${subjectStyle(s.name).name}`}>
            {#if s.history.length}
              <details class="observations"><summary>Rückmeldungsverlauf · {s.history.length} Einträge</summary>
                <p class="dim">Einzelne Selbsteinschätzungen in zeitlicher Reihenfolge. Andere Themen können den Verlauf verändern.</p>
                {#each s.history as point}<p class="observation"><span>{formatShortDate(point.date)}{#if point.start_time} · {hour(point.start_time)}{/if}</span><span>{ratingText(point.rating)}</span></p>{/each}
              </details>
            {/if}
            {#each s.group?.topics || s.group?.items || [] as topic (topic.lesson_id)}
              <article class="topic"><h3>{topic.lstext}</h3><p class="topic-state">{ratingText(topic.rating)}</p>
                <div class="topic-actions"><span class="dim">{topic.source_count} {topic.source_count === 1 ? 'Stunde' : 'Stunden'} · {formatShortDate(topic.date)}</span><a href={topic.url}><ActionLabel kind="chat" label="Üben" /></a></div>
                <details><summary>Quellen ansehen</summary>{#each topic.sources as source}<p class="dim">{formatShortDate(source.date)}{#if source.start_time} · {hour(source.start_time)}{/if} · {ratingText(source.rating)}</p>{/each}</details>
              </article>
            {:else}<p class="dim">Noch keine Themen mit Einschätzung erfasst.</p>{/each}
            <button class="history-link" onclick={() => navigate('subject', s.subject_id)}><ActionLabel label="Alle Unterrichtsstunden" /></button>
          </div>
        {/if}
      </section>
    {/each}
  </div>
  {#if rows.some(s => s.known)}<div class="legend"><span><i class="good"></i>verstanden</span><span><i class="partial"></i>teilweise</span><span><i class="difficult"></i>schwierig</span><span><i class="unknown"></i>offen</span></div>{/if}
{/if}
<style>
  .page-heading h1{font-size:1.6rem;margin:8px 0}.page-heading p{margin:0 0 12px}
  .subject-list{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:0 12px}.subject-entry{border-bottom:1px solid var(--border)}.subject-entry:last-child{border:0}
  .subject-row{display:grid;grid-template-columns:minmax(0,1fr) 72px 18px;gap:10px;align-items:center;width:100%;padding:12px 0;border:0;border-radius:0;background:transparent;text-align:left;color:var(--fg);min-height:76px}
  .subject-copy{display:grid;gap:5px;min-width:0}.subject-name{font-size:1rem;font-weight:600;overflow-wrap:anywhere}.subject-copy small,.trend small{font-size:.75rem;color:var(--fg-muted)}
  .subject-bar{display:flex;height:6px;border-radius:4px;overflow:hidden;background:var(--border)}.good{background:var(--rating-3)}.partial{background:var(--rating-2)}.difficult{background:var(--rating-1)}.unknown{background:var(--cancelled)}
  .trend{text-align:center;display:grid;gap:2px;justify-items:center;color:var(--accent)}.trend svg{width:72px;height:26px}.chevron{color:var(--accent);transition:transform .15s}.chevron.opened{transform:rotate(90deg)}
  .subject-panel{padding:0 0 10px}.topic{padding:10px 0;border-top:1px solid var(--border)}h3{font-size:.95rem;margin:0 0 4px;overflow-wrap:anywhere}.topic-state{font-size:.8rem;color:var(--fg-muted);margin:0 0 2px}.topic-actions{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}.topic-actions a,.history-link{display:inline-flex;align-items:center;min-height:44px;padding:6px 0;color:var(--accent)}.history-link{border:0;background:transparent}
  details{font-size:.8rem;color:var(--fg-muted)}summary{cursor:pointer;padding:10px 0;min-height:44px}.observation{display:flex;gap:8px;justify-content:space-between;flex-wrap:wrap;margin:6px 0}.legend{display:flex;flex-wrap:wrap;gap:8px 12px;margin:10px 2px;font-size:.75rem;color:var(--fg-muted)}.legend span{display:inline-flex;align-items:center;gap:5px}.legend i{width:7px;height:7px;border-radius:50%}
  @media(max-width:350px){.subject-row{gap:6px;grid-template-columns:minmax(0,1fr) 62px 16px}.trend svg{width:62px}}
</style>
