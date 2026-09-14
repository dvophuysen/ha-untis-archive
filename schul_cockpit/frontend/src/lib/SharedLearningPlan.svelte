<script>
  import ActionLabel from './ActionLabel.svelte';
 import {api} from './api.js';
 import LearningGoal from './LearningGoal.svelte';
 import {subjectStyle} from './subjectStyle.js';
 let {plan,compact=false,onstart=null}= $props();
 let adjusting=$state(false),error=$state(''),filter=$state('');
 const todayKeys=$derived(new Set(plan?.today.actions.map(g=>g.key)||[]));
 const otherGoals=$derived((plan?.goals||[]).filter(g=>!todayKeys.has(g.key)).map(g=>({...g,plannedDate:plan.week?.find(d=>d.date!==plan.date&&d.actions.some(a=>a.key===g.key))?.date})));
 const subjects=$derived([...new Set(otherGoals.map(g=>subjectStyle(g.subject).name))]);
 // Nach Fach gruppiert, darin nach Feld. Das Feld ist ein Rahmen und selbst
 // nicht übbar; geübt und nachgewiesen werden die einzelnen Teilthemen.
 const grouped=$derived.by(()=>{
  const shown=otherGoals.filter(g=>!filter||subjectStyle(g.subject).name===filter);
  const bySubject=[];
  for(const goal of shown){
   let subject=bySubject.find(s=>s.name===goal.subject);
   if(!subject){subject={name:goal.subject,style:subjectStyle(goal.subject),blocks:[]};bySubject.push(subject);}
   const label=goal.field||null;
   let block=subject.blocks.find(b=>b.field===label);
   if(!block){block={field:label,parts:goal.field_parts||0,shown:goal.field_shown||0,goals:[]};subject.blocks.push(block);}
   if(label){block.parts=Math.max(block.parts,goal.field_parts||0);block.shown=goal.field_shown||block.shown;}
   block.goals.push(goal);
  }
  return bySubject;
 });
 async function adjust(load){adjusting=true;error='';try{plan=await api.put(`/api/accounts/${plan.account_id}/plan/day`,{load});}catch(e){error=e.message;}finally{adjusting=false;}}
</script>
{#if plan}
 <section class="shared-plan">
  <header><h2>🌱 {compact?'Deine Lernideen':'Dein Lernplan'}</h2><span class="muted">Heute ca. {plan.today.planned_minutes} Min.</span></header>
  <div class="day-choice" aria-label="Zeit zum Lernen"><span>Zeit heute</span>{#each [['busy','Wenig'],['normal','Normal'],['room','Mehr']] as [value,label]}<button aria-pressed={plan.today.day_load===value} disabled={adjusting} onclick={()=>adjust(value)}>{label}</button>{/each}</div>
  {#if error}<p role="alert">{error}</p>{/if}
  {#each plan.errors||[] as e}<p class="notice">{e}</p>{/each}
  {#if plan.today.overload_minutes}<p class="notice">Heute ist viel offen. Schau zuerst auf deine Hausaufgaben.</p>{/if}
  <section class="goal-group"><h3>Für heute</h3>
   {#each plan.today.actions as goal (goal.key)}<LearningGoal {goal} {onstart}/>{:else}<p class="muted">Heute ist nichts zusätzlich eingeplant. 🌿</p>{/each}
  </section>
  <section class="goal-group"><header><h3>Schon vorziehen</h3>{#if subjects.length>1}<label><span class="sr-only">Nach Fach filtern</span><select bind:value={filter}><option value="">Alle Fächer</option>{#each subjects as subject}<option>{subject}</option>{/each}</select></label>{/if}</header>
   {#each grouped as subject (subject.name)}
    <details class="subject" open={grouped.length<=2}>
     <summary><span aria-hidden="true">{subject.style.emoji}</span> {subject.style.name} <span class="count">{subject.blocks.reduce((n,b)=>n+b.goals.length,0)}</span></summary>
     {#each subject.blocks as block (block.field||'einzeln')}
      {#if block.field}
       <div class="field">
        <strong>{block.field}</strong>
        {#if block.parts}<span class="coverage">{block.shown} von {block.parts} {block.parts===1?'Teil':'Teilen'} selbstständig gezeigt{#if block.goals.length<block.parts} · {block.goals.length} davon hier{/if}</span>{/if}
       </div>
      {/if}
      {#each block.goals as goal (goal.key)}<LearningGoal {goal} {onstart}/>{/each}
     {/each}
    </details>
   {:else}<p class="muted">Keine weiteren Themen. Ein eigenes Thema kannst du im Lernraum wählen.</p>{/each}
  </section>
  <a class="free-link" href="#/learning">Fach und Thema selbst wählen <ActionLabel /></a>
 </section>
{/if}
<style>
 .subject>summary{min-height:44px;display:flex;align-items:center;gap:8px;cursor:pointer;font-weight:600;list-style:none}
 .subject>summary::-webkit-details-marker{display:none}
 .subject{border-top:1px solid var(--border);padding-top:6px}
 .subject:first-of-type{border-top:0}
 .count{margin-left:auto;font-weight:400;font-size:.85rem;color:var(--fg-muted)}
 .field{margin:10px 0 2px;padding-left:2px}
 .field strong{display:block;font-size:.95rem}
 .coverage{font-size:.8rem;color:var(--fg-muted)}
 .shared-plan{overflow-wrap:anywhere}header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}h2{font-size:1.35rem;margin:0}h3{font-size:1.05rem;margin:0}.muted{font-size:.9rem;color:var(--fg-muted)}.day-choice{display:flex;gap:6px;align-items:center;margin:16px 0;flex-wrap:wrap}.day-choice>span{font-size:.9rem;margin-right:8px}.day-choice button{min-height:44px;padding:8px 14px;background:var(--bg-card);border:1px solid var(--border);border-radius:10px;color:var(--fg)}.day-choice button[aria-pressed="true"]{background:var(--accent-soft);border-color:var(--accent);color:var(--accent);font-weight:600}.goal-group{border:1px solid var(--border);border-radius:16px;background:var(--bg-card);padding:16px;margin:16px 0}.goal-group:first-of-type{background:var(--learn-soft)}.notice{padding:12px;border-radius:10px;background:color-mix(in srgb,var(--rating-2) 15%,var(--bg-card))}.free-link{display:inline-flex;align-items:center;min-height:44px}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}select{max-width:100%;min-height:44px}
</style>
