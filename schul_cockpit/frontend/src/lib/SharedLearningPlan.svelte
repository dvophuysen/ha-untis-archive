<script>
 import {api} from './api.js';
 let adjusting=$state(false),error=$state('');
 async function adjust(load){adjusting=true;error='';try{plan=await api.put(`/api/accounts/${plan.account_id}/plan/day`,{load});}catch(e){error=e.message;}finally{adjusting=false;}}
 let {plan,compact=false,onstart=null}= $props();
 const dayLabel=d=>new Date(d+'T12:00:00').toLocaleDateString('de-DE',{weekday:'short',day:'numeric',month:'numeric'});
 function go(g){if(onstart)onstart(g);else window.location.hash=g.url;}
</script>
{#if plan}
 <section class="shared-plan">
  <h2>Dein Lernplan</h2>
  <p>Wie passt Lernen heute in deinen Tag?</p><div class="day-choice">{#each [['busy','Voller Tag'],['normal','Normal'],['room','Mehr Luft']] as [value,label]}<button aria-pressed={plan.today.day_load===value} disabled={adjusting} onclick={()=>adjust(value)}>{label}</button>{/each}</div>
  {#if error}<p role="alert">{error}</p>{/if}<p>{plan.today.load_reason}</p>
  <p><strong>Vorschlag: heute etwa {plan.today.planned_minutes} Minuten</strong>{#if plan.today.used_minutes} · {plan.today.used_minutes} Minuten für erledigte Aufgaben und begonnene Übungen angerechnet (Schätzung){/if}</p>
  <p class="muted">Hausaufgaben und Üben sind gemeinsam berücksichtigt. Die Zeiten helfen beim Einteilen; sie sind kein Pflichtpensum.</p>
  {#each plan.errors||[] as e}<p class="notice">{e}</p>{/each}
  {#if plan.today.overload_minutes}<p class="notice">Die noch offenen, zeitnah fälligen Hausaufgaben überschreiten die verbleibende Orientierung um etwa {plan.today.overload_minutes} Minuten. Bitte gemeinsam priorisieren; es kommen keine zusätzlichen Übungen dazu.</p>{/if}
  {#each plan.today.actions as g (g.key)}
   <article><span>{g.subject} · etwa {g.minutes} Minuten</span><h3>{g.title}</h3><p>{g.reason}</p><p class="muted">{g.state}</p>
    {#if g.kind==='activity'}<a href="#/learning/legacy">Gespeicherte Übung öffnen</a>{:else}<button onclick={()=>go(g)}>{onstart?'Gemeinsam anschauen':'Zum passenden Lernschritt'}</button>{/if}
   </article>
  {:else}<p>{plan.today.study_day?'Heute ist keine zusätzliche Übung eingeplant.':'Heute ist kein Übungstag eingestellt.'}</p>{/each}
  <p class="muted">{plan.today.message}</p>
  {#if !compact}
   <details><summary>Nächste sieben Tage</summary><p class="muted">Vorschau anhand des heutigen Standes. Neue Hausaufgaben und Lernversuche passen die Planung an.</p>
    {#each plan.week as d}<article><strong>{dayLabel(d.date)} · etwa {d.planned_minutes} Minuten</strong>
      {#each d.homework as t}<p>{t.subject_name||'Hausaufgabe'}: {t.title} · {t.estimated_minutes??20} Minuten{t.estimated_minutes==null?' (geschätzt)':''}</p>{/each}
      {#each d.actions as g}<p>{g.subject}: {g.title} · {g.minutes} Minuten</p><small>{g.reason}</small>{/each}
      {#if !d.planned_minutes}<p>Keine weitere Aktion eingeplant.</p>{/if}
    </article>{/each}
   </details>
   <details><summary>Bearbeitet, noch offen und spätere Kurzchecks</summary>
    <p class="muted">Eine Stunde kann mehrere Fähigkeiten enthalten. Ein gelungener Versuch bestätigt die geübte Fähigkeit, nicht automatisch den gesamten Unterrichtsstoff.</p>
    {#each plan.goals as g}<article><strong>{g.subject} · {g.title}</strong><p>{g.state}</p>
      {#if g.worked_day}<p>Bearbeitet am {dayLabel(g.worked_day)}</p>{/if}
      {#if g.open_question}<p>{g.open_question}</p>{/if}
      <p>Nächster Kurzcheck frühestens {dayLabel(g.due_date)} · Einplanung nach Zeitrahmen</p>
      <small>{g.source_note}{g.catch_up_open?' · Nachholen organisatorisch noch offen':''}</small>
      {#if g.session_id}<a href={`#/learning?session=${g.session_id}`}>Gespeicherten Verlauf ansehen</a>{/if}
      <details><summary>Ursprüngliche Rückmeldungen ({g.sources.length})</summary>{#each g.sources as s}<p>{dayLabel(s.date)}: {s.text}</p><small>{s.rating===1?'Nicht verstanden':s.rating===2?'Teilweise verstanden':s.rating===3?'Als verstanden gemeldet':'Keine Verständnisbewertung'} {s.note||''}</small>{/each}</details>
    </article>{/each}
   </details>
   {#if plan.deferred.length}<details><summary>Weitere Lernanlässe ({plan.deferred.length})</summary><p class="muted">Das sind Unterrichtseinträge und Lernanlässe, keine Liste nachgewiesener Wissenslücken.</p>{#each plan.deferred as g}<p><strong>{g.subject}: {g.title}</strong><br/>{g.defer_reason}</p>{/each}</details>{/if}
  {/if}
 </section>
{/if}
<style>
 .day-choice{display:flex;gap:.4rem;flex-wrap:wrap}.day-choice button[aria-pressed="true"]{border:2px solid var(--accent)} .shared-plan{overflow-wrap:anywhere}h2{font-size:1.2rem}h3{font-size:1.05rem;margin:.5rem 0}article{border:1px solid var(--border);background:var(--bg-card);padding:.85rem;border-radius:12px;margin:.7rem 0}p{line-height:1.45}.muted,small{font-size:.85rem;color:var(--fg-muted)}button,a{display:inline-flex;align-items:center;min-height:44px;font:inherit}button{border:1px solid var(--border);border-radius:10px;padding:.6rem;background:var(--bg-card);color:inherit}summary{cursor:pointer;min-height:44px;align-content:center}details{margin:.6rem 0}.notice{padding:.7rem;background:#fff0cf;color:#493a12;border-radius:10px}
</style>
