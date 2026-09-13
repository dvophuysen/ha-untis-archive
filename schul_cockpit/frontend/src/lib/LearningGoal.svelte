<script>
 import {formatShortDate} from './format.js';
 import {subjectStyle} from './subjectStyle.js';
 let {goal,onstart=null}= $props();
 const subject=$derived(subjectStyle(goal.subject));
 function start(){if(goal.kind==='activity'){window.location.hash='#/learning/legacy';return;}if(onstart)onstart({...goal,voluntary:true});else window.location.hash=goal.url||`#/learning?goal=${encodeURIComponent(goal.key)}`;}
</script>
<button class="goal-row" onclick={start}>
 <span class="subject-icon" aria-hidden="true">{subject.emoji}</span>
 <span class="goal-copy"><span class="subject-name">{subject.name}</span><strong>{goal.title}</strong></span>
 <span class="goal-action">{#if goal.plannedDate}<small>Geplant {formatShortDate(goal.plannedDate)}</small>{/if}{#if goal.minutes}<small>ca. {goal.minutes} Min.</small>{/if}<span>{goal.kind==='activity'?'✏️ Öffnen':goal.session_id?'💬 Weiter':'💬 Üben'} →</span></span>
</button>
<style>
 .goal-row{display:grid;grid-template-columns:36px minmax(0,1fr) auto;gap:12px;align-items:center;width:100%;text-align:left;padding:16px 0;border:0;border-bottom:1px solid var(--border);background:transparent;color:var(--fg);border-radius:0;min-height:64px}
 .goal-row:last-child{border-bottom:0}.goal-row:hover{background:var(--bg-elevated)}.subject-icon{font-size:1.5rem}.goal-copy{display:grid;gap:4px;overflow-wrap:anywhere}.subject-name,small{font-size:.85rem;color:var(--fg-muted)}strong{font-size:1rem;font-weight:600}.goal-action{display:grid;justify-items:end;gap:6px;color:var(--accent);font-size:.9rem;white-space:nowrap}
 @media(max-width:480px){.goal-row{grid-template-columns:28px minmax(0,1fr)}.goal-action{grid-column:2;display:flex;justify-content:space-between}.subject-icon{font-size:1.25rem}}
</style>
