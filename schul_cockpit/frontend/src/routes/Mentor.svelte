<script>
  import {onMount,tick} from 'svelte';
  import {stripUntisMetadata} from '../lib/format.js';
  import {api} from '../lib/api.js';
  import SharedLearningPlan from '../lib/SharedLearningPlan.svelte';
  import MentorExams from '../lib/MentorExams.svelte';
  let {accountId,onManage}= $props();
  const base=$derived(`/api/accounts/${accountId}/learning/mentor`);
  let data=$state(null),running=$state(null),tab=$state('today'),error=$state(''),busy=$state(false);
  let text=$state(''),attachment=$state(null),fileInput=$state(null),subject=$state(''),goal=$state(''),spent=$state(0),evidence=$state(null),correction=$state(''),quality=$state(null);
  let focusKey=$state(''),removeConfirm=$state(false);
  async function removeSession(){await api.delete(`${base}/sessions/${running.id}`,{version:running.version});running=null;removeConfirm=false;await load();}
  let end=$state(null),demo=$state(false),examBusy=$state(false);
  async function switchMode(value){if(value===demo)return;await leave();demo=value;data=null;tab='today';text='';attachment=null;evidence=null;quality=null;subject='';goal='';await load();}
  async function load(){data=await api.get(`${base}?demo=${demo}`);}
  async function act(fn){if(busy)return;busy=true;error='';try{await fn();await tick();}catch(e){error=e.message;}finally{busy=false;}}
  async function open(s){removeConfirm=false;running=await api.get(`${base}/sessions/${s.id}`);text='';attachment=null;}
  async function start(c){running=await api.post(`${base}/sessions`,{subject:c.subject,lesson_id:c.lesson_id||null,skill_id:c.skill_id||null,goal:c.title||goal,goal_key:c.key||null,minutes:c.minutes||10,voluntary:c.voluntary||false,demo});text='';}
  async function send(kind='message',value=text){
    const r=await api.post(`${base}/sessions/${running.id}/turn`,{request_key:crypto.randomUUID(),version:running.version,text:value,kind,attachment_id:attachment?.id||null});
    running=r;text='';attachment=null;await tick();end?.scrollIntoView({behavior:'smooth',block:'end'});
  }
  async function upload(e){const file=e.target.files?.[0];if(!file)return;await act(async()=>{const f=new FormData();f.append('file',file);attachment=await api.post(`${base}/sessions/${running.id}/photos`,f);});e.target.value='';}
  async function leave(){if(running?.status==='active'&&(!data.can_manage||running.is_test))await api.post(`${base}/sessions/${running.id}/pause`,{paused:true});running=null;await load();}
  async function pause(hidden){if(running?.status==='active'&&(!data?.can_manage||running.is_test)&&!busy){try{const r=await api.post(`${base}/sessions/${running.id}/pause`,{paused:hidden});if(running?.id===r.id)running=r;}catch{/* next explicit action shows an error */}}}
  const choices=$derived(running?.messages.filter(m=>m.role==='assistant').at(-1)?.payload?.choices||[]);
  onMount(()=>{act(async()=>{await load();const q=new URLSearchParams(window.location.hash.split('?')[1]||'');if(q.get('session'))await open({id:Number(q.get('session'))});else if(q.get('subject')){subject=q.get('subject');goal=q.get('topic')||'';tab=q.get('mode')==='exam'?'exams':'today';}else if(q.get('goal')){const g=data.shared_plan?.goals.find(g=>g.key===q.get('goal'));if(g){focusKey=g.key;goal=g.title;subject=g.subject;if(g.session_id)await open({id:g.session_id});else if(!data.can_manage)await start(g);else tab='today';}}});const t=setInterval(()=>pause(document.hidden),30000);const v=()=>pause(document.hidden);document.addEventListener('visibilitychange',v);return()=>{clearInterval(t);document.removeEventListener('visibilitychange',v);};});
</script>
<div class="mentor">
  {#if data?.can_manage}<nav class="mode-switch" aria-label="Mentor-Modus"><button aria-pressed={!demo} class:chosen={!demo} disabled={busy||examBusy} onclick={()=>act(()=>switchMode(false))}>Kinderstand</button><button aria-pressed={demo} class:chosen={demo} disabled={busy||examBusy} onclick={()=>act(()=>switchMode(true))}>Demo ausprobieren</button></nav>
    <p class="notice">{demo?'Demo im Lernmentor: erfundene Beispiele für Klasse 6. Testgespräche und Demo-Arbeiten werden getrennt gespeichert und sind für die Kinder unsichtbar. KI-Aufrufe kosten echtes Geld aus dem Familienbudget. Eigene Eingaben und hochgeladene Fotos werden im Testverlauf gespeichert.':'Echter Kinderstand: Gespräche und Antworten des ausgewählten Kindes ansehen. Eltern-Testläufe zählen nicht zum Lernfortschritt. Übungen freigeben und Einstellungen ändern wirkt auf echte Daten.'}</p>
  {/if}
  {#if error}<div class="notice" role="alert"><p>{error}</p>{#if running}<button disabled={busy} onclick={()=>act(()=>open(running))}>Aktuellen Stand laden</button>{/if}</div>{/if}
  {#if running && data?.can_manage}<button disabled={busy} onclick={()=>removeConfirm=!removeConfirm}>Diese Einheit entfernen</button>{#if removeConfirm}<p class="notice">Gespräch, Antworten und Anrechnung dieser Einheit löschen?</p><button disabled={busy} onclick={()=>act(removeSession)}>Einheit endgültig löschen</button>{/if}{/if}
  {#if running}
    <header class="session-head"><button class="quiet" disabled={busy} onclick={()=>act(leave)}>← Lernen</button><span>{running.subject} · etwa {running.max_minutes} Minuten</span></header>
    {#if running.is_test}<p class="notice">{running.is_demo?'Demo-Gespräch mit Beispieldaten. Kein Lernnachweis des Kindes.':'Früherer Eltern-Testlauf mit echtem Unterrichtskontext. Kein Kinderverlauf.'}</p>{/if}
    <h1>{running.goal}</h1>
    {#if running.task && running.status==='active'}<details class="task"><summary>Deine aktuelle Aufgabe</summary><p class="preserve">{running.task.prompt}</p></details>{/if}
    <div class="messages" aria-live="polite">
      {#each running.messages as m}<article class:own={m.role==='user'}><span class="speaker">{m.role==='user'?(data?.can_manage&&!running.is_test?'Kind':'Du'):'Mentor'}</span><p class="preserve">{m.text}</p>
        {#if m.payload.task}<div class="task"><strong>Deine Aufgabe</strong><p class="preserve">{m.payload.task.prompt}</p></div>{/if}
        {#if m.payload.attachment_id}<a href={`./${base.slice(1)}/photos/${m.payload.attachment_id}`} target="_blank" rel="noreferrer">Dein Foto öffnen</a>{/if}
        {#if m.payload.assessment}<p class="assessment">{m.payload.assessment.rationale}<small>{m.payload.assessment.label}{m.payload.assessment.help_used?' · mit Unterstützung':''}</small></p>{/if}
      </article>{/each}<div bind:this={end}></div>
    </div>
    {#if running.status==='active'&&(!data?.can_manage||running.is_test)}
      <div class="choices">{#each choices as c}<button disabled={busy||!data?.can_write} onclick={()=>act(()=>send(c==='Für heute fertig'?'finish':c.includes('Beispiel')?'example':'message',c))}>{c}</button>{/each}</div>
      <form class="composer" onsubmit={e=>{e.preventDefault();act(()=>send(running.task?'answer':'message'));}}>
        <label for="mentor-answer">{running.task?'Dein Versuch oder deine Frage':'Was möchtest du sagen?'}</label>
        <textarea id="mentor-answer" bind:value={text} rows="3" maxlength="4000" disabled={busy||!data?.can_write} placeholder="Schreib einfach, wie du sprichst. Zum Diktieren nutze das Mikrofon deiner Tastatur."></textarea>
        {#if attachment}<p>Foto angehängt. <button type="button" onclick={()=>attachment=null}>Entfernen</button></p>{/if}
        <div class="actions"><button class="primary" disabled={busy||(!text.trim()&&!attachment)||!data?.can_write}>Senden</button><button type="button" disabled={busy||!data?.can_write} onclick={()=>fileInput?.click()}>Foto zeigen</button><input class="file" type="file" accept="image/*" bind:this={fileInput} onchange={upload}/></div>
        <div class="actions"><button type="button" disabled={busy||!data?.can_write} onclick={()=>act(()=>send('hint','Bitte anders erklären.'))}>Anders erklären</button><button type="button" disabled={busy||!data?.can_write} onclick={()=>act(()=>send('finish','Für heute fertig.'))}>Für heute fertig</button></div>
      </form>
    {:else}<section class="card"><h2>{running.status==='active'?'Gespeicherter Kinderverlauf':'Für heute geschafft'}</h2><p>{running.summary||'Dein Gespräch und deine Antworten bleiben gespeichert.'}</p><button onclick={()=>act(leave)}>Zur Übersicht</button><a href="#/plan">Aktualisierten Lernplan ansehen</a></section>{/if}
    {#if busy}<p role="status" class="working">Einen Moment – deine Antwort wird vorbereitet …</p>{/if}
  {:else if data}
    <header><span class="eyebrow">Dein Lernbegleiter</span><h1>{data.can_manage&&!demo?'Der echte Lernverlauf.':'Ein Schritt nach dem anderen.'}</h1><p>{data.can_manage&&!demo?'Wähle oben das Kind. Hier findest du seine gespeicherten Gespräche, Antworten und Lernbeobachtungen.':'Du kannst etwas zeigen, ausprobieren oder einfach erzählen.'}</p></header>
    <nav aria-label="Lernbereiche">{#each [['today','Heute'],['history',data.can_manage&&!demo?'Gespräche':'Weitermachen'],['progress','Was schon klappt'],['exams','Übungsklausur']] as [key,label]}<button class:chosen={tab===key} disabled={busy||examBusy} onclick={()=>tab=key}>{label}</button>{/each}</nav>
    {#if !data.profile?.ai_enabled}<p class="notice">Der Lernrahmen muss zuerst mit deinen Eltern eingerichtet und die KI aktiviert werden.</p>{/if}
    {#each data.errors as warning}<p class="notice">{warning}</p>{/each}
    {#if tab==='today'}
      {#if !data.can_manage||demo}<section class="card free-choice"><h2>Was möchtest du üben?</h2><form onsubmit={e=>{e.preventDefault();act(()=>start({subject,title:goal,voluntary:true}));}}><label>Fach<select required bind:value={subject}><option value="">Auswählen</option>{#each [...new Set([...data.subjects,subject].filter(Boolean))] as s}<option>{s}</option>{/each}</select></label><label>Worum geht es ungefähr?<input bind:value={goal} maxlength="250" placeholder="Du kannst es auch gleich im Gespräch zeigen."/></label><button disabled={busy||!data.can_write}>Üben starten</button><button type="button" disabled={busy||!subject} onclick={()=>tab='exams'}>Übungstest erstellen</button></form></section>{/if}
      {#if !demo && data.homework_choices?.length}<section class="card"><h2>Für deine Aufgaben üben</h2>{#each data.homework_choices as h}<article class="homework-choice"><strong>{h.subject}</strong><p class="preserve">{stripUntisMetadata(h.title)}</p><button disabled={busy} onclick={()=>{subject=h.subject;goal=stripUntisMetadata(h.title).slice(0,250);}}>Thema auswählen</button><button disabled={busy} onclick={()=>{subject=h.subject;goal=stripUntisMetadata(h.title).slice(0,250);tab='exams';}}>Übungstest vorbereiten</button></article>{/each}</section>{/if}
      {#each data.sessions.filter(s=>s.status==='active').slice(0,2) as s}<section class="card"><span class="eyebrow">Angefangen · {s.subject}</span><h2>{s.goal}</h2><button class="primary" disabled={busy} onclick={()=>act(()=>open(s))}>{data.can_manage&&!demo?'Verlauf ansehen':'Hier weitermachen'}</button></section>{/each}
      {#if !demo&&focusKey&&data.can_manage}<section class="card"><h2>{goal}</h2><p>{data.shared_plan?.goals.find(g=>g.key===focusKey)?.state}</p><p>Für dieses Thema gibt es noch keinen Kinderverlauf. Mit seiner Anmeldung kann das Kind direkt beim gewählten Lernschritt beginnen.</p><a href="#/plan">Zum Plan</a></section>{/if}
      {#if !demo}<SharedLearningPlan plan={data.shared_plan} compact={false} onstart={data.can_manage?null:c=>act(()=>start(c))}/>{:else}
      {#each data.candidates.slice(0,3) as c}<section class="card"><span>{c.subject}</span><h2>{c.title}</h2><p>{c.reason}</p><button disabled={busy} onclick={()=>act(()=>start(c))}>Gemeinsam anschauen</button></section>{/each}{/if}

    {:else if tab==='history'}
      {#each data.sessions as s}<button class="history" disabled={busy} onclick={()=>act(()=>open(s))}><strong>{s.subject} · {s.goal}</strong><span>{s.status==='active'&&(!data.can_manage||demo)?'Fortsetzen':'Verlauf ansehen'} · {s.updated_at.slice(0,10)}</span></button>{:else}<p>{data.can_manage&&!demo?'Noch keine Gespräche des Kindes gespeichert. Eltern-Testläufe werden hier nicht eingemischt.':'Deine ersten Gespräche erscheinen hier.'}</p>{/each}
      {#if data.legacy_sessions?.length}<details><summary>Frühere Eltern-Testläufe mit Echtkontext ({data.legacy_sessions.length})</summary><p>Diese älteren Tests sind keine Beispieldaten-Demo und keine Leistungen des Kindes.</p>{#each data.legacy_sessions as s}<button class="history" onclick={()=>act(()=>open(s))}>{s.subject} · {s.goal}</button>{/each}</details>{/if}
    {:else if tab==='progress'}
      {#if demo}<p class="notice">Demo-Antworten erzeugen keine Lernbeobachtungen oder Wiederholungen für das Kind.</p>{/if}<p>Hier zählt, was du an Aufgaben gezeigt hast. Eine richtige Antwort direkt nach einer Erklärung prüfen wir später noch einmal.</p>
      {#each data.progress as p}<section class="card"><span>{p.subject}</span><h2>{p.title}</h2><p>{p.label}</p><p>{p.attempts} Versuche · {p.variants} unterschiedliche Aufgaben selbstständig gelöst</p><button onclick={()=>act(async()=>{evidence=await api.get(`${base}/evidence/${p.id}`);})}>Antworten ansehen</button></section>{:else}<p>Noch keine ausgewerteten Lernversuche. Eine Rückmeldung „verstanden“ allein wird hier nicht als Leistungsnachweis gezählt.</p>{/each}
      {#if evidence}<section class="card"><h2>Die einzelnen Beobachtungen</h2>{#each evidence as e}<p class="preserve">{e.answer}</p><p>{e.rationale}</p><small>{e.created_at.slice(0,10)} · {e.help_used?'mit Hilfe':'ohne angeforderten Hinweis'} · KI-Einschätzung</small>{#if data.can_manage&&!e.invalidated}<label>Was war an der Bewertung falsch?<input bind:value={correction}/></label><button disabled={busy||correction.length<3} onclick={()=>act(async()=>{await api.post(`${base}/evidence/${e.id}/invalidate`,{reason:correction});evidence=null;await load();})}>Bewertung zurücknehmen</button>{/if}<hr/>{/each}<button onclick={()=>evidence=null}>Schließen</button></section>{/if}
    {:else}<MentorExams {accountId} {demo} subjects={data.subjects} canManage={data.can_manage} initialSubject={subject} initialTopic={goal} onBusy={v=>examBusy=v}/>{/if}
    {#if data.can_manage&&!demo}<details class="parents"><summary>Echte Einstellungen und Übungen verwalten</summary>
      <p>Gespräche und Antworten werden gespeichert. Autorisierte Eltern können sie hier gemeinsam mit dem Kind ansehen.</p>
      <p><strong>{data.budget.used_eur.toFixed(2)} € von {data.budget.limit_eur.toFixed(0)} €</strong> · {data.budget.month}</p><p class="muted">{data.budget.accounting}. Warnung ab 40 €. Hintergrundarbeiten sind enthalten.</p>
      {#if data.budget.warning}<p class="notice">Der Monatsrahmen wird knapp. Gespeicherte Übungen bleiben verfügbar.</p>{/if}
      {#if !data.budget.rate_available}<p class="notice">Die Kostensätze müssen vor neuen KI-Aufrufen geprüft werden.</p>{/if}
      {#if !data.budget.opening_confirmed}<form onsubmit={e=>{e.preventDefault();act(async()=>{await api.put(`${base}/budget-opening`,{spent_eur:spent});await load();});}}><p>Vor der neuen Verbrauchserfassung gab es bereits KI-Aufrufe. Bitte den bisherigen Monatsverbrauch aus Azure berücksichtigen.</p><label>Bisherige Mentor-Kosten dieses Monats in Euro<input type="number" min="0" max="1000" step="0.01" required bind:value={spent}/></label><button disabled={busy}>Anfangsstand bestätigen</button></form>{/if}
      <label class="check"><input type="checkbox" checked={data.enabled} disabled={busy} onchange={e=>act(async()=>{await api.put(`${base}/settings`,{enabled:e.target.checked,background_enabled:data.background});await load();})}/> Mentor verwenden</label>
      <label class="check"><input type="checkbox" checked={data.background} disabled={busy} onchange={e=>act(async()=>{await api.put(`${base}/settings`,{enabled:data.enabled,background_enabled:e.target.checked});await load();})}/> Neue Unterrichtsthemen im Hintergrund erschließen</label>
      <details><summary>Fachliche Modellprüfung</summary><p>30 feste Fälle zu Brüchen, Grammatik und Zusammenhängen. Drei begrenzte Durchläufe mit je zehn Fällen; Ergebnisse werden wiederverwendet. Keine Daten der Kinder.</p>
      <button disabled={busy} onclick={()=>act(async()=>{quality=await api.post(`${base}/quality/next`);await load();})}>Zehn Prüffälle auswerten</button>
      {#if quality}<p>{quality.passed} von {quality.done} bisher geprüften Fällen entsprechen den festgelegten Kriterien ({quality.total} insgesamt).</p>{#each quality.results.filter(r=>!r.passed) as r}<p>Fall {r.id+1}: erwartet {r.expected}, bewertet {r.result}. {r.rationale}</p>{/each}{/if}</details>
      <button onclick={onManage}>Lernrahmen, Materialien und eigene Übungen</button>
    </details>{/if}
    {#if busy}<p role="status">Wird vorbereitet …</p>{/if}
  {:else if !error}<p role="status">Dein Lernbereich wird geladen …</p>{/if}
</div>
<style>
  .mode-switch{display:grid;grid-template-columns:1fr 1fr}.mentor{max-width:720px;margin:auto;padding-bottom:1.5rem}h1{font-size:1.55rem;line-height:1.25;overflow-wrap:anywhere}h2{font-size:1.1rem;line-height:1.35}.eyebrow,.speaker{font-size:.8rem;font-weight:650;opacity:.8}.card,.task{border:1px solid var(--border,#d4e0da);background:var(--bg-card,#fff);padding:1rem;border-radius:16px;margin:1rem 0}.task{position:relative}.preserve{white-space:pre-wrap;overflow-wrap:anywhere}nav,.choices,.actions{display:flex;gap:.5rem;flex-wrap:wrap;margin:.6rem 0}button{min-height:44px;min-width:44px;padding:.6rem .85rem;border:1px solid var(--border,#d4e0da);border-radius:12px;background:var(--bg-card,#fff);color:inherit;font:inherit;cursor:pointer}.primary,.chosen{background:var(--accent,#247552);color:var(--accent-fg,#fff)}button:disabled{opacity:.5;cursor:default}.messages article{background:var(--bg-card,#fff);border:1px solid var(--border,#d4e0da);padding:.8rem 1rem;border-radius:14px;margin:.8rem 0;max-width:95%}.messages .own{margin-left:1rem;background:var(--bg,#edf5f0)}.messages p{margin:.4rem 0;line-height:1.55}.composer{background:var(--bg-card,#fff);padding:1rem .2rem;border-top:1px solid var(--border,#d4e0da)}textarea,input,select{font:inherit;font-size:16px;box-sizing:border-box;width:100%;padding:.7rem;margin:.4rem 0;border:1px solid var(--border,#ccc);border-radius:10px;background:var(--bg-card,#fff);color:inherit}label{display:block;margin:.5rem 0}.file{display:none}.check{display:flex;align-items:center;gap:.6rem}.check input{width:24px;height:24px}.notice{padding:.8rem;background:#fff0cf;color:#493a12;border-radius:12px}.session-head{display:flex;align-items:center;gap:.6rem;font-size:.85rem}.history{display:block;text-align:left;width:100%;margin:.6rem 0}.history span,small{display:block;font-size:.8rem;opacity:.8;margin-top:.3rem}.parents{margin-top:1.5rem;border-top:1px solid var(--border,#ccc);padding-top:1rem}summary{min-height:44px;cursor:pointer;display:flex;align-items:center}.muted{font-size:.85rem;opacity:.8}.working{padding:1rem;color:var(--accent,#247552)}
</style>
