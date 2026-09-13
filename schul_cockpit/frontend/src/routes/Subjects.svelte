<script>
  import { api } from '../lib/api.js';
  import { formatShortDate } from '../lib/format.js';
  function hour(value){if(value==null)return '';const s=String(value).replace(':','').padStart(4,'0');return s.slice(0,2)+':'+s.slice(2);}
  let { accountId, navigate } = $props();
  let subjects=$state([]),suggestions=$state(null),loading=$state(true),error=$state('');
  $effect(()=>{
    const account=accountId;let active=true;
    loading=true;error='';subjects=[];suggestions=null;
    if(account)Promise.all([api.get(`/api/accounts/${account}/subjects`),api.get(`/api/accounts/${account}/oral-suggestions`)]).then(([subs,sug])=>{
      if(active){subjects=subs.subjects;suggestions=sug;}
    }).catch(e=>{if(active)error=e.message;}).finally(()=>{if(active)loading=false;});
    return()=>{active=false;};
  });
</script>

<header><h1>Deine Fächer</h1><p class="dim">Was du verstehst. Wo du noch Fragen hast.</p></header>
{#if loading}<div class="empty"><span class="spinner"></span></div>
{:else if error}<div class="error-box" role="alert">{error}</div>
{:else}
  {#each suggestions?.errors || [] as warning}<p class="error-box" role="alert">{warning}</p>{/each}
  <div class="subjects-grid">
  {#each subjects as s (s.subject_id)}
    {@const group=suggestions?.groups.find(g=>g.subject_id===s.subject_id)}
    <section class="card subject-card">
      <header class="subject-head"><h2>{s.name}</h2><button class="ghost" onclick={()=>navigate('subject',s.subject_id)} aria-label={`Stundenverlauf ${s.name}`}>Verlauf →</button></header>
      <div class="subject-state">
        {#if group?.uncertain_topics}<strong>💬 {group.uncertain_topics} {group.uncertain_topics===1?'Thema zum Klären':'Themen zum Klären'}</strong>
        {:else if group?.feedback_count}<strong>🌿 Zuletzt keine offenen Verständnisfragen gemeldet</strong>
        {:else}<span>📝 Noch keine Einschätzung zu den Themen</span>{/if}
        {#if group?.understood_topics}<span class="small dim">{group.understood_topics} {group.understood_topics===1?'Thema zuletzt als verstanden eingeschätzt':'Themen zuletzt als verstanden eingeschätzt'}</span>{/if}
      </div>
      {#each group?.items || [] as it (it.lesson_id)}
        <article class="topic">
          <h3>{it.lstext}</h3>
          <div class="topic-actions"><span class="small dim">{it.source_count} {it.source_count===1?'Stunde':'Stunden'} · zuletzt {formatShortDate(it.date)}</span><a href={it.url}>Anschauen →</a></div>
          <details><summary>Rückmeldungen ansehen</summary>
            {#each it.sources as source}<p class="small">{formatShortDate(source.date)}{#if source.start_time} · {hour(source.start_time)}{/if} · {source.rating===1?'Noch schwierig':source.rating===2?'Teilweise verstanden':source.rating===3?'Verstanden':'Ohne Einschätzung'}</p>{/each}
          </details>
        </article>
      {/each}
    </section>
  {/each}
  </div>
{/if}
<style>
  .subjects-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,310px),1fr));gap:1rem;align-items:start}
  .subject-card{margin:0;min-width:0;border-top:4px solid var(--accent);}
  .subject-head{display:flex;justify-content:space-between;align-items:center;gap:.5rem}
  h2{font-size:1.1rem;margin:0;overflow-wrap:anywhere}.subject-head button{flex-shrink:0}
  .subject-state{display:grid;gap:.4rem;padding:.8rem;margin:.8rem 0;background:var(--school-soft);border-radius:12px;font-size:.9rem}
  .topic{padding:.75rem 0;border-top:1px solid var(--border)}h3{font-size:.95rem;line-height:1.45;margin:0 0 .6rem;overflow-wrap:anywhere}
  .topic-actions{display:flex;justify-content:space-between;align-items:center;gap:.5rem;flex-wrap:wrap}.topic-actions a{padding:.4rem 0;min-height:44px;box-sizing:border-box}
  details{font-size:.8rem;color:var(--fg-muted);margin-top:.3rem}summary{cursor:pointer;padding:.4rem 0}
</style>
