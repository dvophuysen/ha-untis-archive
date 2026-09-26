<script>
  // Lernraum in der Elternansicht (D183): Kinderstand, Demo, Gespräche,
  // Übungsklausuren mit Freigabe. Kinder, Mitlesen und Kindmodus sehen den
  // Kompass (Compass.svelte, D186). Die laufende Einheit ist MentorSession.
  import ActionLabel from '../lib/ActionLabel.svelte';
  import {formatShortDate} from '../lib/format.js';
  import {untrack} from 'svelte';
  import {api} from '../lib/api.js';
  import SharedLearningPlan from '../lib/SharedLearningPlan.svelte';
  import MentorExams from '../lib/MentorExams.svelte';
  import MentorSession from '../lib/MentorSession.svelte';
  import {queryOf,opensSession,openFromQuery,clearQuery} from '../lib/learningQuery.js';
  let {accountId,onManage,nav={hash:''}}= $props();
  const base=$derived(`/api/accounts/${accountId}/learning/mentor`);
  let data=$state(null),running=$state(null),tab=$state('today'),error=$state(''),busy=$state(false);
  let subject=$state(''),goal=$state(''),evidence=$state(null),correction=$state('');
  let focusKey=$state('');
  let demo=$state(false),examBusy=$state(false),examAttempt=$state(null);
  async function pauseRunning(){if(running?.status==='active'&&data?.can_write){try{await api.post(`${base}/sessions/${running.id}/pause`,{paused:true});}catch{/* egal */}}running=null;}
  async function switchMode(value){if(value===demo)return;await pauseRunning();demo=value;data=null;tab='today';subject='';goal='';await load();}
  async function load(){data=await api.get(`${base}?demo=${demo}`);}
  // Ein Link während des Ladens wird gemerkt und danach ausgeführt, statt verloren zu gehen.
  let pendingHash=null;
  function route(h){if(busy){pendingHash=h;return;}act(()=>follow(h));}
  async function act(fn){if(busy)return;busy=true;error='';try{await fn();}catch(e){error=e.message;}finally{busy=false;if(pendingHash!==null){const next=pendingHash;pendingHash=null;route(next);}}}
  async function open(s){running=await api.get(`${base}/sessions/${s.id}`);}
  async function start(c){running=await api.post(`${base}/sessions`,{subject:c.subject,lesson_id:c.lesson_id||null,skill_id:c.skill_id||null,goal:c.title||goal,goal_key:c.key||null,minutes:c.minutes||10,voluntary:c.voluntary||false,demo});}
  const openSessions=$derived((data?.sessions||[]).filter(s=>!s.task_done));
  // Wiederfinden: Wortlaut der Hausaufgabe, Art des Gesprächs, Stand und letzter Dialog in einer Liste.
  const MODE_NAMES={homework_help:'Hilfe zur Hausaufgabe',homework_check:'Lösung geprüft',topic:'Thema der Arbeit',practice:'Üben'};
  function when(iso){if(!iso)return '';return `${formatShortDate(iso.slice(0,10))} ${iso.slice(11,16)}`;}
  function stateOf(s){if(s.task_done)return 'Hausaufgabe abgehakt';if(s.status==='active')return 'offen';return 'beendet';}
  // Bei jedem Wechsel der Adresse auswerten, nicht nur beim ersten Laden (D186).
  async function follow(h){
    if(!data)await load();
    const q=queryOf(h);
    if(opensSession(q)){running=await openFromQuery(api,base,q,{demo});clearQuery();return;}
    // Aus „Erledigen“: eine zurückgehaltene Übungsklausur prüfen (D202).
    if(q.get('exam_attempt')){if(demo)await switchMode(false);tab='exams';examAttempt=Number(q.get('exam_attempt'));clearQuery();return;}
    if(q.get('subject')){subject=q.get('subject');goal=q.get('topic')||'';tab=q.get('mode')==='exam'?'exams':'today';}
    else if(q.get('goal')){const g=data.shared_plan?.goals.find(g=>g.key===q.get('goal')||g.previous_keys?.includes(q.get('goal')));if(g){focusKey=g.key;goal=g.title;subject=g.subject;if(g.session_id)await open({id:g.session_id});else tab='today';}}
  }
  $effect(()=>{const h=nav.hash;void nav;untrack(()=>route(h));});
</script>
<div class="mentor">
  {#if data?.can_manage}<nav class="mode-switch" aria-label="Mentor-Modus"><button aria-pressed={!demo} class:chosen={!demo} disabled={busy||examBusy} onclick={()=>act(()=>switchMode(false))}>Kinderstand</button><button aria-pressed={demo} class:chosen={demo} disabled={busy||examBusy} onclick={()=>act(()=>switchMode(true))}>Demo ausprobieren</button></nav>
    <p class="notice">{demo?'Demo im Lernmentor: erfundene Beispiele für Klasse 6. Testgespräche und Demo-Arbeiten werden getrennt gespeichert und sind für die Kinder unsichtbar. KI-Aufrufe kosten echtes Geld aus dem Familienbudget. Eigene Eingaben und hochgeladene Fotos werden im Testverlauf gespeichert.':'Echter Kinderstand: Gespräche und Antworten des ausgewählten Kindes. Ein Gespräch auf deinem Gerät gilt als Gespräch des Kindes; nur der Demo-Modus ist eine Simulation. Was nur ein Versuch war, kannst du danach als Testlauf kennzeichnen.'}</p>
  {/if}
  {#if error}<div class="notice" role="alert"><p>{error}</p></div>{/if}
  {#if running}
    <MentorSession {accountId} bind:running canWrite={!!data?.can_write} canManage={!!data?.can_manage} speech={!!data?.speech} onleave={load} onreload={load}/>
  {:else if data}
    <header><span class="eyebrow">Dein Lernbegleiter</span><h1>{data.can_manage&&!demo?'Der echte Lernverlauf.':'Was hast du vor?'}</h1><p>{data.can_manage&&!demo?'Wähle oben das Kind. Hier findest du seine gespeicherten Gespräche, Antworten und Lernbeobachtungen.':'Du wählst das Thema. Ich helfe dir beim Üben.'}</p></header>
    <nav aria-label="Lernbereiche">{#each [['today','Heute','🌱'],['history',data.can_manage&&!demo?'Gespräche':'Weitermachen','💬'],['progress','Was schon klappt','🌟'],['exams','Übungsklausur','📝']] as [key,label,icon]}<button class:chosen={tab===key} disabled={busy||examBusy} aria-pressed={tab===key} onclick={()=>tab=key}><span aria-hidden="true">{icon}</span> {label}</button>{/each}</nav>
    {#if !data.profile?.ai_enabled}<p class="notice">Der Lernrahmen muss zuerst mit deinen Eltern eingerichtet und die KI aktiviert werden.</p>{/if}
    {#each data.errors as warning}<p class="notice">{warning}</p>{/each}
    {#if tab==='today'}
      {#if !demo}<section class="card"><h2>Vokabeln üben</h2><p>Bedeutung gesprochen, Schreibweise getippt. Die Wörter kommen aus deinen Buchseiten.</p><a class="button-link" href="#/vokabeln"><ActionLabel label="Zum Vokabeltrainer" /></a></section>{/if}
      {#if !data.can_manage||demo}<section class="card material-hint"><h2>Hast du Material dazu?</h2><p>Fotografiere ein Arbeitsblatt, eine Heftseite oder eine Aufgabe. Dann kann ich beim Üben und beim Test daraus arbeiten.</p><a href={`#/materialien/${encodeURIComponent(subject||'')}`}><ActionLabel label="Material hinzufügen" /></a></section>
      <section class="card free-choice"><h2>Was möchtest du üben?</h2><form onsubmit={e=>{e.preventDefault();act(()=>start({subject,title:goal,voluntary:true}));}}><label>Fach<select required bind:value={subject}><option value="">Auswählen</option>{#each [...new Set([...data.subjects,subject].filter(Boolean))] as s}<option>{s}</option>{/each}</select></label><label>Worum geht es ungefähr?<input bind:value={goal} maxlength="250" placeholder="Du kannst es auch gleich im Gespräch zeigen."/></label><button disabled={busy||!data.can_write}><ActionLabel kind="chat" label="Üben starten" /></button><button type="button" disabled={busy||!subject} onclick={()=>tab='exams'}>Übungstest erstellen</button></form></section>{/if}
      {#each openSessions.filter(s=>s.status==='active').slice(0,2) as s}<section class="card"><span class="eyebrow">Angefangen · {s.subject} · zuletzt {when(s.last_at)}</span><h2>{s.label||s.goal}</h2><button class="primary" disabled={busy} onclick={()=>act(()=>open(s))}><ActionLabel kind={data.can_manage&&!demo?'navigate':'chat'} label={data?.can_write?'Hier weitermachen':'Verlauf ansehen'}/></button></section>{/each}
      {#if !demo&&focusKey&&data.can_manage}<section class="card"><h2>{goal}</h2><p>{data.shared_plan?.goals.find(g=>g.key===focusKey)?.state}</p><p>Für dieses Thema gibt es noch keinen Kinderverlauf. Mit seiner Anmeldung kann das Kind direkt beim gewählten Lernschritt beginnen.</p><a href="#/plan"><ActionLabel label="Zum Plan" /></a></section>{/if}
      {#if !demo}<SharedLearningPlan plan={data.shared_plan} compact={!data.can_manage} onstart={data.can_manage?null:c=>act(()=>start(c))}/>{:else}
      {#each data.candidates.slice(0,3) as c}<section class="card"><span>{c.subject}</span><h2>{c.title}</h2><p>{c.reason}</p><button disabled={busy} onclick={()=>act(()=>start(c))}><ActionLabel kind="chat" label="Gemeinsam anschauen" /></button></section>{/each}{/if}

    {:else if tab==='history'}
      {#each data.sessions as s (s.id)}<button class="history" class:filed={s.task_done} disabled={busy} onclick={()=>act(()=>open(s))}><strong>{s.subject} · {s.label||s.goal}</strong><span>{MODE_NAMES[s.mode]||MODE_NAMES.practice} · {stateOf(s)} · zuletzt {when(s.last_at)} · {s.messages} {s.messages===1?'Nachricht':'Nachrichten'}</span></button>{:else}<p>{data.can_manage&&!demo?'Noch keine Gespräche.':'Deine ersten Gespräche erscheinen hier.'}</p>{/each}
      {#if data.archived_sessions?.length}<details class="archive"><summary>Archiv ({data.archived_sessions.length})</summary><p class="muted">Vorbereitung auf geschriebene Arbeiten, erledigte Hausaufgaben und lange Liegengebliebenes. Nichts ist gelöscht.</p>{#each data.archived_sessions as s (s.id)}<div class="history archived"><span><strong>{s.subject} · {s.label||s.goal}</strong><span>{s.archive_reason}</span></span>{#if data.can_write}<button disabled={busy} onclick={()=>act(async()=>{await api.post(`${base}/sessions/${s.id}/unarchive`,{});await load();await open(s);})}>Wieder aufnehmen</button>{/if}</div>{/each}</details>{/if}
      {#if data.legacy_sessions?.length}<details><summary>Als Testlauf gekennzeichnet ({data.legacy_sessions.length})</summary><p>Diese Gespräche stehen außerhalb des Lernstands und sind für das Kind nicht sichtbar. Beim Öffnen lassen sie sich in den Kinderverlauf übernehmen.</p>{#each data.legacy_sessions as s}<button class="history" onclick={()=>act(()=>open(s))}>{s.subject} · {s.goal}</button>{/each}</details>{/if}
    {:else if tab==='progress'}
      {#if demo}<p class="notice">Demo-Antworten erzeugen keine Lernbeobachtungen oder Wiederholungen für das Kind.</p>{/if}<p>Hier zählt, was du an Aufgaben gezeigt hast. Eine richtige Antwort direkt nach einer Erklärung prüfen wir später noch einmal.</p>
      {#each data.progress as p}<section class="card"><span>{p.subject}</span><h2>{p.title}</h2><p>{p.label}</p><p>{p.attempts} Versuche · {p.variants} unterschiedliche Aufgaben selbstständig gelöst</p><button onclick={()=>act(async()=>{evidence=await api.get(`${base}/evidence/${p.id}`);})}>Antworten ansehen</button></section>{:else}<p>Deine Fortschritte erscheinen nach dem Üben. </p>{/each}
      {#if evidence}<section class="card"><h2>Die einzelnen Beobachtungen</h2>{#each evidence as e}<p class="preserve">{e.answer}</p><p>{e.rationale}</p><small>{formatShortDate(e.created_at.slice(0,10))} · {e.help_used?'mit Hilfe':'ohne angeforderten Hinweis'} · KI-Einschätzung</small>{#if data.can_manage&&!e.invalidated}<label>Was war an der Bewertung falsch?<input bind:value={correction}/></label><button disabled={busy||correction.length<3} onclick={()=>act(async()=>{await api.post(`${base}/evidence/${e.id}/invalidate`,{reason:correction});evidence=null;await load();})}>Bewertung zurücknehmen</button>{/if}<hr/>{/each}<button onclick={()=>evidence=null}>Schließen</button></section>{/if}
    {:else}<MentorExams {accountId} {demo} subjects={data.subjects} canManage={data.can_manage} initialSubject={subject} initialTopic={goal} initialAttempt={examAttempt} onBusy={v=>examBusy=v}/>{/if}
    <!-- KI-Rahmen, Kosten und die Schalter des Lernbegleiters stehen unter „Einstellen“ (D183). -->
    {#if data.can_manage&&!demo}<section class="parents"><p class="muted">KI-Rahmen, Kosten und ob der Lernbegleiter läuft, stellst du unter „Einstellen“ ein.</p><div class="actions"><a class="button-link" href="#/einstellen?s=ki"><ActionLabel label="KI-Rahmen und Kosten" /></a><button onclick={onManage}>Lernrahmen, Materialien und eigene Übungen</button></div></section>{/if}
    {#if busy}<p role="status">Wird vorbereitet …</p>{/if}
  {:else if !error}<p role="status">Dein Lernbereich wird geladen …</p>{/if}
</div>
<style>
.free-choice{background:var(--accent-soft);border-color:var(--accent)}
nav[aria-label="Lernbereiche"]{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}
nav[aria-label="Lernbereiche"] button{text-align:left}
nav[aria-label="Lernbereiche"] button span{margin-right:6px}
.mode-switch{display:grid;grid-template-columns:1fr 1fr}
.mentor{max-width:720px;margin:auto;padding-bottom:1.5rem}
h1{font-size:1.55rem;line-height:1.25;overflow-wrap:anywhere}
h2{font-size:1.1rem;line-height:1.35}
.eyebrow{font-size:.8rem;font-weight:650;opacity:.8}
.card{border:1px solid var(--border,#d4e0da);background:var(--bg-card,#fff);padding:1rem;border-radius:16px;margin:1rem 0}
.preserve{white-space:pre-wrap;overflow-wrap:anywhere}
nav,.actions{display:flex;gap:.5rem;flex-wrap:wrap;margin:.6rem 0}
button{min-height:44px;min-width:44px;padding:.6rem .85rem;border:1px solid var(--border,#d4e0da);border-radius:12px;background:var(--bg-card,#fff);color:inherit;font:inherit;cursor:pointer}
.primary,.chosen{background:var(--accent,#247552);color:var(--accent-fg,#fff)}
button:disabled{opacity:.5;cursor:default}
input,select{font:inherit;font-size:16px;box-sizing:border-box;width:100%;padding:.7rem;margin:.4rem 0;border:1px solid var(--border,#ccc);border-radius:10px;background:var(--bg-card,#fff);color:inherit}
label{display:block;margin:.5rem 0}
.notice{padding:.8rem;background:var(--warm-soft);color:var(--fg);border-radius:12px}
.history{display:block;text-align:left;width:100%;margin:.6rem 0}
.history span,small{display:block;font-size:.8rem;opacity:.8;margin-top:.3rem}
.history.filed{opacity:.75}
.history.archived{display:flex;justify-content:space-between;gap:.6rem;align-items:center;border:1px solid var(--border,#d4e0da);border-radius:12px;padding:.6rem .8rem;box-sizing:border-box}
.history.archived>span{margin:0;opacity:1}
.archive{margin-top:1rem}
.parents{margin-top:1.5rem;border-top:1px solid var(--border,#ccc);padding-top:1rem}
summary{min-height:44px;cursor:pointer;display:flex;align-items:center}
.muted{font-size:.85rem;opacity:.8}
</style>
