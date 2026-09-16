<script>
  import ActionLabel from '../lib/ActionLabel.svelte';
  import {formatShortDate} from '../lib/format.js';
  import {onMount,tick} from 'svelte';
  import {api} from '../lib/api.js';
  import SharedLearningPlan from '../lib/SharedLearningPlan.svelte';
  import MentorExams from '../lib/MentorExams.svelte';
  import Speech from '../lib/Speech.svelte';
  let {accountId,onManage}= $props();
  const base=$derived(`/api/accounts/${accountId}/learning/mentor`);
  let data=$state(null),running=$state(null),tab=$state('today'),error=$state(''),busy=$state(false);
  let text=$state(''),attachment=$state(null),fileInput=$state(null),subject=$state(''),goal=$state(''),spent=$state(0),evidence=$state(null),correction=$state(''),quality=$state(null);
  let focusKey=$state(''),removeConfirm=$state(false);
  async function removeSession(){await api.delete(`${base}/sessions/${running.id}`,{version:running.version});running=null;removeConfirm=false;await load();}
  async function resume(){running=await api.post(`${base}/sessions/${running.id}/resume`,{});text='';attachment=null;}
  async function setCounts(counts){running=await api.put(`${base}/sessions/${running.id}/counts`,{counts});await load();}
  let end=$state(null),demo=$state(false),examBusy=$state(false);
  async function switchMode(value){if(value===demo)return;await leave();demo=value;data=null;tab='today';text='';attachment=null;evidence=null;quality=null;subject='';goal='';await load();}
  let limits=$state({monthly_eur:50,warning_eur:40,daily_eur:10,sources_eur:30,background_eur:10,sources_model:''}),limitsOpen=$state(false);
  async function load(){data=await api.get(`${base}?demo=${demo}`);const b=data.budget||{};limits={monthly_eur:b.limit_eur??50,warning_eur:b.warning_eur??40,daily_eur:b.daily_limit_eur??10,sources_eur:b.sources_limit_eur??30,background_eur:b.background_limit_eur??10,sources_model:b.sources_model??''};}
  async function act(fn){if(busy)return;busy=true;error='';try{await fn();await tick();}catch(e){error=e.message;}finally{busy=false;}}
  async function open(s){removeConfirm=false;running=await api.get(`${base}/sessions/${s.id}`);text='';attachment=null;}
  async function start(c){running=await api.post(`${base}/sessions`,{subject:c.subject,lesson_id:c.lesson_id||null,skill_id:c.skill_id||null,goal:c.title||goal,goal_key:c.key||null,minutes:c.minutes||10,voluntary:c.voluntary||false,demo});text='';}
  // Signale fürs Zögern: Zeit von der gestellten Aufgabe bis zum Absenden, Löschungen beim Tippen.
  let taskShownAt=$state(null),edits=$state(0),spoken=$state(false);
  // Spracheingabe: Aufnahme → eigene Erkennung → Text ins Feld, erst dann Senden.
  async function transcribe(blob,took){const f=new FormData();f.append('file',blob,'aufnahme');f.append('seconds',String(took));const r=await api.post(`${base}/sessions/${running.id}/transcribe`,f);return r.text;}
  function heard(t){text=text.trim()?`${text.trim()} ${t}`:t;spoken=true;}
  const speechLabel=$derived(running?`Aufnahme: ${/englisch/i.test(running.subject)?'Englisch oder Deutsch':/spanisch/i.test(running.subject)?'Spanisch oder Deutsch':/franz/i.test(running.subject)?'Französisch oder Deutsch':/latein/i.test(running.subject)?'Latein oder Deutsch':'Deutsch'} · eigene Erkennung`:'');
  $effect(()=>{const prompt=running?.task?.prompt;if(prompt){taskShownAt=Date.now();edits=0;}else{taskShownAt=null;}});
  async function send(kind='message',value=text){
    const signals=kind==='answer'&&taskShownAt?{seconds:Math.min(36000,Math.round((Date.now()-taskShownAt)/1000)),edits}:{};
    const r=await api.post(`${base}/sessions/${running.id}/turn`,{request_key:crypto.randomUUID(),version:running.version,text:value,kind,attachment_id:attachment?.id||null,spoken:spoken&&value===text,...signals});
    running=r;text='';attachment=null;spoken=false;await tick();end?.scrollIntoView({behavior:'smooth',block:'end'});
  }
  async function upload(e){const file=e.target.files?.[0];if(!file)return;await act(async()=>{const f=new FormData();f.append('file',file);attachment=await api.post(`${base}/sessions/${running.id}/photos`,f);});e.target.value='';}
  async function leave(){if(running?.status==='active'&&data?.can_write)await api.post(`${base}/sessions/${running.id}/pause`,{paused:true});running=null;await load();}
  async function pause(hidden){if(running?.status==='active'&&data?.can_write&&!busy){try{const r=await api.post(`${base}/sessions/${running.id}/pause`,{paused:hidden});if(running?.id===r.id)running=r;}catch{/* next explicit action shows an error */}}}
  const choices=$derived(running?.messages.filter(m=>m.role==='assistant').at(-1)?.payload?.choices||[]);
  const openSessions=$derived((data?.sessions||[]).filter(s=>!s.task_done));
  const filedSessions=$derived((data?.sessions||[]).filter(s=>s.task_done));
  onMount(()=>{act(async()=>{await load();const q=new URLSearchParams(window.location.hash.split('?')[1]||'');if(q.get('session'))await open({id:Number(q.get('session'))});else if(q.get('topic_id')){running=await api.post(`${base}/sessions`,{topic_id:Number(q.get('topic_id'))});}else if(q.get('help')){running=await api.post(`${base}/sessions`,{subject:'Hausaufgabe',homework_task_id:Number(q.get('help')),voluntary:true});}else if(q.get('subject')){subject=q.get('subject');goal=q.get('topic')||'';tab=q.get('mode')==='exam'?'exams':'today';}else if(q.get('goal')){const g=data.shared_plan?.goals.find(g=>g.key===q.get('goal')||g.previous_keys?.includes(q.get('goal')));if(g){focusKey=g.key;goal=g.title;subject=g.subject;if(!data.can_manage)await start({...g,voluntary:true});else if(g.session_id)await open({id:g.session_id});else tab='today';}}});const t=setInterval(()=>pause(document.hidden),30000);const v=()=>pause(document.hidden);document.addEventListener('visibilitychange',v);return()=>{clearInterval(t);document.removeEventListener('visibilitychange',v);};});
</script>
<div class="mentor">
  {#if data?.can_manage}<nav class="mode-switch" aria-label="Mentor-Modus"><button aria-pressed={!demo} class:chosen={!demo} disabled={busy||examBusy} onclick={()=>act(()=>switchMode(false))}>Kinderstand</button><button aria-pressed={demo} class:chosen={demo} disabled={busy||examBusy} onclick={()=>act(()=>switchMode(true))}>Demo ausprobieren</button></nav>
    <p class="notice">{demo?'Demo im Lernmentor: erfundene Beispiele für Klasse 6. Testgespräche und Demo-Arbeiten werden getrennt gespeichert und sind für die Kinder unsichtbar. KI-Aufrufe kosten echtes Geld aus dem Familienbudget. Eigene Eingaben und hochgeladene Fotos werden im Testverlauf gespeichert.':'Echter Kinderstand: Gespräche und Antworten des ausgewählten Kindes. Du kannst mitschreiben — was ihr gemeinsam erarbeitet, findet das Kind auf seinem eigenen Gerät wieder. Was nur ein Versuch war, kannst du danach als Testlauf kennzeichnen.'}</p>
  {/if}
  {#if error}<div class="notice" role="alert"><p>{error}</p>{#if running}<button disabled={busy} onclick={()=>act(()=>open(running))}>Aktuellen Stand laden</button>{/if}</div>{/if}
  {#if running && data?.can_manage}<button disabled={busy} onclick={()=>removeConfirm=!removeConfirm}>Diese Einheit entfernen</button>{#if removeConfirm}<p class="notice">Gespräch, Antworten und Anrechnung dieser Einheit löschen?</p><button disabled={busy} onclick={()=>act(removeSession)}>Einheit endgültig löschen</button>{/if}{/if}
  {#if running}
    <header class="session-head"><button class="quiet" disabled={busy} onclick={()=>act(leave)}>← Lernen</button><span>{running.subject} · {running.topic?`Thema ${running.topic.position??'–'} von ${running.topic.total} der offiziellen Themenliste · Stufe: ${running.topic.stage}`:running.mode==='homework_help'?'Hilfe bei deiner Aufgabe':`etwa ${running.max_minutes} Minuten`}</span></header>
    {#if running.is_test}<p class="notice">{running.is_demo?'Demo-Gespräch mit Beispieldaten. Kein Lernnachweis des Kindes.':'Als Testlauf gekennzeichnet: außerhalb des Lernstands und für das Kind nicht sichtbar.'}</p>{/if}
    {#if data?.can_manage&&!running.is_demo}<div class="actions"><button disabled={busy} onclick={()=>act(()=>setCounts(!!running.is_test))}>{running.is_test?'In den Kinderverlauf übernehmen':'War nur ein Test — nicht in den Lernstand'}</button></div>{/if}
    <h1>{running.goal}</h1>
    {#if running.topic}<p class="hint">{running.topic.check?'Kurzprüfung: kurze Aufgaben ohne Erklärung vorweg. Sitzt es noch, gilt das Thema als gefestigt.':'Diese Einheit hat keine Uhr. Sie endet, wenn das Thema sitzt oder du aufhörst.'}{#if running.topic.places_label} · {running.topic.places_label}{/if}</p>{/if}
    {#if running.mode==='homework_help'}<p class="hint">{running.task_done?'Diese Hausaufgabe ist abgehakt. Das Gespräch liegt im Archiv und bleibt lesbar.':'Dieses Gespräch bleibt offen, bis du die Hausaufgabe abhakst.'}</p>{/if}
    {#if running.task && running.status==='active'}<details class="task"><summary>Deine aktuelle Aufgabe</summary><p class="preserve">{running.task.prompt}</p></details>{/if}
    <div class="messages" aria-live="polite">
      {#each running.messages as m}<article class:own={m.role==='user'}><span class="speaker">{m.role!=='user'?'Mentor':m.author==='eltern'?'Eltern':data?.can_manage?'Kind':'Du'}</span><p class="preserve">{m.text}</p>
        {#if m.payload.task}<div class="task"><strong>Deine Aufgabe</strong><p class="preserve">{m.payload.task.prompt}</p></div>{/if}
        {#if m.payload.attachment_id}<a href={`./${base.slice(1)}/photos/${m.payload.attachment_id}`} target="_blank" rel="noreferrer"><ActionLabel label="Dein Foto öffnen" /></a>{/if}
        {#if m.payload.assessment}<p class="assessment">{m.payload.assessment.rationale}<small>{m.payload.assessment.label}{m.payload.assessment.help_used?' · mit Unterstützung':''}</small></p>{/if}
      </article>{/each}<div bind:this={end}></div>
    </div>
    {#if running.status==='active'&&data?.can_write}
      <div class="choices">{#each choices as c}<button disabled={busy||!data?.can_write} onclick={()=>act(()=>send(c==='Für heute fertig'?'finish':c.includes('Beispiel')?'example':'message',c))}>{c}</button>{/each}</div>
      <form class="composer" onsubmit={e=>{e.preventDefault();act(()=>send(running.task?'answer':'message'));}}>
        {#if data?.speech}<Speech onText={heard} {transcribe} disabled={busy||!data?.can_write} label={speechLabel}/>{/if}
        <label for="mentor-answer">{running.task?'Dein Versuch oder deine Frage':'Was möchtest du sagen?'}{#if spoken} · erkannt, bitte prüfen{/if}</label>
        <textarea id="mentor-answer" bind:value={text} rows="3" maxlength="4000" disabled={busy||!data?.can_write} placeholder={data?.speech?'… oder tippen':'Deine Antwort oder Frage …'} onbeforeinput={e=>{if((e.inputType||'').startsWith('delete'))edits++;}}></textarea>
        {#if attachment}<p>Foto angehängt. <button type="button" onclick={()=>attachment=null}>Entfernen</button></p>{/if}
        <div class="actions"><button class="primary" disabled={busy||(!text.trim()&&!attachment)||!data?.can_write}>Senden</button><button type="button" disabled={busy||!data?.can_write} onclick={()=>fileInput?.click()}>Foto zeigen</button><input class="file" type="file" accept="image/*" bind:this={fileInput} onchange={upload}/><a class="material-link" href={`#/materialien/${encodeURIComponent(running.subject||'')}${running.mode==='homework_help'&&running.task_id?`/${running.task_id}`:''}`} title="Arbeitsblatt, Heftseite oder PDF dauerhaft ablegen"><ActionLabel label="Material hinzufügen" /></a></div>
        <div class="actions"><button type="button" disabled={busy||!data?.can_write} onclick={()=>act(()=>send('hint','Bitte anders erklären.'))}>Anders erklären</button><button type="button" disabled={busy||!data?.can_write} onclick={()=>act(()=>send('finish','Für heute fertig.'))}>Für heute fertig</button></div>
      </form>
    {:else}<section class="card"><h2>{running.status==='active'?'Gespeicherter Verlauf':running.topic?'Einheit beendet':running.untimed?'Unterbrochen':'Für heute geschafft'}</h2><p>{running.summary||'Dein Gespräch und deine Antworten bleiben gespeichert.'}</p>{#if running.topic}<p><strong>Stufe: {running.topic.stage}</strong>{#if running.topic.reason&&running.topic.stage!=='neu'} · {running.topic.reason}{/if}{#if running.topic.next_check} · Kurzprüfung ab {formatShortDate(running.topic.next_check)}{/if}</p><a href="#/klausuren">Zur Arbeit und den anderen Themen</a>{/if}
      {#if running.status!=='active'&&data?.can_write}<button class="primary" disabled={busy} onclick={()=>act(resume)}><ActionLabel kind="chat" label="Hier weitermachen" /></button>{/if}
      <button onclick={()=>act(leave)}>Zur Übersicht</button><a href="#/plan"><ActionLabel label="Aktualisierten Lernplan ansehen" /></a></section>{/if}
    {#if busy}<p role="status" class="working">Einen Moment – deine Antwort wird vorbereitet …</p>{/if}
  {:else if data}
    <header><span class="eyebrow">Dein Lernbegleiter</span><h1>{data.can_manage&&!demo?'Der echte Lernverlauf.':'Was hast du vor?'}</h1><p>{data.can_manage&&!demo?'Wähle oben das Kind. Hier findest du seine gespeicherten Gespräche, Antworten und Lernbeobachtungen.':'Du wählst das Thema. Ich helfe dir beim Üben.'}</p></header>
    <nav aria-label="Lernbereiche">{#each [['today','Heute','🌱'],['history',data.can_manage&&!demo?'Gespräche':'Weitermachen','💬'],['progress','Was schon klappt','🌟'],['exams','Übungsklausur','📝']] as [key,label,icon]}<button class:chosen={tab===key} disabled={busy||examBusy} aria-pressed={tab===key} onclick={()=>tab=key}><span aria-hidden="true">{icon}</span> {label}</button>{/each}</nav>
    {#if !data.profile?.ai_enabled}<p class="notice">Der Lernrahmen muss zuerst mit deinen Eltern eingerichtet und die KI aktiviert werden.</p>{/if}
    {#each data.errors as warning}<p class="notice">{warning}</p>{/each}
    {#if tab==='today'}
      {#if !data.can_manage||demo}<section class="card material-hint"><h2>Hast du Material dazu?</h2><p>Fotografiere ein Arbeitsblatt, eine Heftseite oder eine Aufgabe. Dann kann ich beim Üben und beim Test daraus arbeiten.</p><a href={`#/materialien/${encodeURIComponent(subject||'')}`}><ActionLabel label="Material hinzufügen" /></a></section>
      <section class="card free-choice"><h2>Was möchtest du üben?</h2><form onsubmit={e=>{e.preventDefault();act(()=>start({subject,title:goal,voluntary:true}));}}><label>Fach<select required bind:value={subject}><option value="">Auswählen</option>{#each [...new Set([...data.subjects,subject].filter(Boolean))] as s}<option>{s}</option>{/each}</select></label><label>Worum geht es ungefähr?<input bind:value={goal} maxlength="250" placeholder="Du kannst es auch gleich im Gespräch zeigen."/></label><button disabled={busy||!data.can_write}><ActionLabel kind="chat" label="Üben starten" /></button><button type="button" disabled={busy||!subject} onclick={()=>tab='exams'}>Übungstest erstellen</button></form></section>{/if}
      {#each openSessions.filter(s=>s.status==='active').slice(0,2) as s}<section class="card"><span class="eyebrow">Angefangen · {s.subject}</span><h2>{s.goal}</h2><button class="primary" disabled={busy} onclick={()=>act(()=>open(s))}><ActionLabel kind={data.can_manage&&!demo?'navigate':'chat'} label={data?.can_write?'Hier weitermachen':'Verlauf ansehen'}/></button></section>{/each}
      {#if !demo&&focusKey&&data.can_manage}<section class="card"><h2>{goal}</h2><p>{data.shared_plan?.goals.find(g=>g.key===focusKey)?.state}</p><p>Für dieses Thema gibt es noch keinen Kinderverlauf. Mit seiner Anmeldung kann das Kind direkt beim gewählten Lernschritt beginnen.</p><a href="#/plan"><ActionLabel label="Zum Plan" /></a></section>{/if}
      {#if !demo}<SharedLearningPlan plan={data.shared_plan} compact={!data.can_manage} onstart={data.can_manage?null:c=>act(()=>start(c))}/>{:else}
      {#each data.candidates.slice(0,3) as c}<section class="card"><span>{c.subject}</span><h2>{c.title}</h2><p>{c.reason}</p><button disabled={busy} onclick={()=>act(()=>start(c))}><ActionLabel kind="chat" label="Gemeinsam anschauen" /></button></section>{/each}{/if}

    {:else if tab==='history'}
      {#each openSessions as s}<button class="history" disabled={busy} onclick={()=>act(()=>open(s))}><strong>{s.subject} · {s.goal}</strong><span>{data?.can_write?'Fortsetzen':'Verlauf ansehen'} · {formatShortDate(s.updated_at.slice(0,10))}</span></button>{:else}<p>{data.can_manage&&!demo?'Noch keine offenen Gespräche. Abgehakte Hausaufgaben stehen im Archiv.':'Deine ersten Gespräche erscheinen hier.'}</p>{/each}
      {#if filedSessions.length}<details><summary>Erledigte Hausaufgaben ({filedSessions.length})</summary><p>Diese Gespräche gehören zu abgehakten Aufgaben. Nimmst du das Häkchen weg, stehen sie wieder oben.</p>{#each filedSessions as s}<button class="history" disabled={busy} onclick={()=>act(()=>open(s))}>{s.subject} · {s.goal}</button>{/each}</details>{/if}
      {#if data.legacy_sessions?.length}<details><summary>Als Testlauf gekennzeichnet ({data.legacy_sessions.length})</summary><p>Diese Gespräche stehen außerhalb des Lernstands und sind für das Kind nicht sichtbar. Beim Öffnen lassen sie sich in den Kinderverlauf übernehmen.</p>{#each data.legacy_sessions as s}<button class="history" onclick={()=>act(()=>open(s))}>{s.subject} · {s.goal}</button>{/each}</details>{/if}
    {:else if tab==='progress'}
      {#if demo}<p class="notice">Demo-Antworten erzeugen keine Lernbeobachtungen oder Wiederholungen für das Kind.</p>{/if}<p>Hier zählt, was du an Aufgaben gezeigt hast. Eine richtige Antwort direkt nach einer Erklärung prüfen wir später noch einmal.</p>
      {#each data.progress as p}<section class="card"><span>{p.subject}</span><h2>{p.title}</h2><p>{p.label}</p><p>{p.attempts} Versuche · {p.variants} unterschiedliche Aufgaben selbstständig gelöst</p><button onclick={()=>act(async()=>{evidence=await api.get(`${base}/evidence/${p.id}`);})}>Antworten ansehen</button></section>{:else}<p>Deine Fortschritte erscheinen nach dem Üben. </p>{/each}
      {#if evidence}<section class="card"><h2>Die einzelnen Beobachtungen</h2>{#each evidence as e}<p class="preserve">{e.answer}</p><p>{e.rationale}</p><small>{formatShortDate(e.created_at.slice(0,10))} · {e.help_used?'mit Hilfe':'ohne angeforderten Hinweis'} · KI-Einschätzung</small>{#if data.can_manage&&!e.invalidated}<label>Was war an der Bewertung falsch?<input bind:value={correction}/></label><button disabled={busy||correction.length<3} onclick={()=>act(async()=>{await api.post(`${base}/evidence/${e.id}/invalidate`,{reason:correction});evidence=null;await load();})}>Bewertung zurücknehmen</button>{/if}<hr/>{/each}<button onclick={()=>evidence=null}>Schließen</button></section>{/if}
    {:else}<MentorExams {accountId} {demo} subjects={data.subjects} canManage={data.can_manage} initialSubject={subject} initialTopic={goal} onBusy={v=>examBusy=v}/>{/if}
    {#if data.can_manage&&!demo}<details class="parents"><summary>Echte Einstellungen und Übungen verwalten</summary>
      <p>Gespräche und Antworten werden gespeichert. Autorisierte Eltern können sie hier gemeinsam mit dem Kind ansehen.</p>
      <p><strong>{data.budget.used_eur.toFixed(2)} € von {data.budget.limit_eur.toFixed(0)} €</strong> · {data.budget.month}</p><p class="muted">{data.budget.accounting}. Warnung ab {data.budget.warning_eur.toFixed(0)} €, Tagesrahmen je Kind {data.budget.daily_limit_eur?.toFixed(0)} €. Hintergrundarbeiten sind enthalten{#if data.budget.sources_limit_eur}, darunter der Quellenbestand mit {data.budget.sources_eur.toFixed(2)} € von {data.budget.sources_limit_eur.toFixed(0)} €{/if}.</p>
      {#if data.budget.warning}<p class="notice">Der Monatsrahmen wird knapp. Gespeicherte Übungen bleiben verfügbar.</p>{/if}
      {#if !data.budget.rate_available}<p class="notice">Die Kostensätze müssen vor neuen KI-Aufrufen geprüft werden.</p>{/if}
      {#if !data.budget.opening_confirmed}<form onsubmit={e=>{e.preventDefault();act(async()=>{await api.put(`${base}/budget-opening`,{spent_eur:spent});await load();});}}><p>Vor der neuen Verbrauchserfassung gab es bereits KI-Aufrufe. Bitte den bisherigen Monatsverbrauch aus Azure berücksichtigen.</p><label>Bisherige Mentor-Kosten dieses Monats in Euro<input type="number" min="0" max="1000" step="0.01" required bind:value={spent}/></label><button disabled={busy}>Anfangsstand bestätigen</button></form>{/if}
      <details><summary>KI-Rahmen einstellen</summary>
        <p class="muted">Der Tagesrahmen zählt nur, was das Kind selbst übt und fragt. Quellen und Hintergrund haben eigene Monatsrahmen innerhalb des Monatsrahmens. Das Modell fürs Abschreiben wird nur nach Eichung an echten Seiten umgestellt; Erklären und Üben bleiben beim Hauptmodell.</p>
        <form class="limits" onsubmit={e=>{e.preventDefault();act(async()=>{await api.put(`${base}/budget-limits`,{monthly_eur:Number(limits.monthly_eur),warning_eur:Number(limits.warning_eur),daily_eur:Number(limits.daily_eur),sources_eur:Number(limits.sources_eur),background_eur:Number(limits.background_eur),sources_model:limits.sources_model??''});await load();limitsOpen=false;});}}>
          <label>Monat gesamt (€)<input type="number" min="1" max="1000" step="1" bind:value={limits.monthly_eur}/></label>
          <label>Warnung ab (€)<input type="number" min="1" max="1000" step="1" bind:value={limits.warning_eur}/></label>
          <label>Tag je Kind (€)<input type="number" min="0.5" max="200" step="0.5" bind:value={limits.daily_eur}/></label>
          <label>Quellenbestand im Monat (€)<input type="number" min="0" max="1000" step="1" bind:value={limits.sources_eur}/></label>
          <label>Hintergrund im Monat (€)<input type="number" min="0" max="1000" step="1" bind:value={limits.background_eur}/></label>
          <label>Modell fürs Abschreiben<select bind:value={limits.sources_model}><option value="">wie Hauptmodell ({data.budget.model})</option>{#each data.budget.models??[] as m}<option value={m}>{m} · {data.budget.rates?.[m]?.input_per_m} / {data.budget.rates?.[m]?.output_per_m} € je Mio. Token</option>{/each}</select></label>
          <button disabled={busy}>Rahmen speichern</button>
        </form>
      </details>
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
  .limits{display:grid;gap:6px;max-width:26rem}
  .limits label{display:grid;gap:2px;font-size:0.9rem}

  .hint{font-size:.85rem;opacity:.8;margin:.2rem 0 .6rem}
  .free-choice{background:var(--accent-soft);border-color:var(--accent)}.homework-choice{padding:14px 0;border-bottom:1px solid var(--border)}.homework-choice:last-child{border-bottom:0}nav[aria-label="Lernbereiche"]{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}nav[aria-label="Lernbereiche"] button{text-align:left}nav[aria-label="Lernbereiche"] button span{margin-right:6px}
  .mode-switch{display:grid;grid-template-columns:1fr 1fr}.mentor{max-width:720px;margin:auto;padding-bottom:1.5rem}h1{font-size:1.55rem;line-height:1.25;overflow-wrap:anywhere}h2{font-size:1.1rem;line-height:1.35}.eyebrow,.speaker{font-size:.8rem;font-weight:650;opacity:.8}.card,.task{border:1px solid var(--border,#d4e0da);background:var(--bg-card,#fff);padding:1rem;border-radius:16px;margin:1rem 0}.task{position:relative}.preserve{white-space:pre-wrap;overflow-wrap:anywhere}nav,.choices,.actions{display:flex;gap:.5rem;flex-wrap:wrap;margin:.6rem 0}button{min-height:44px;min-width:44px;padding:.6rem .85rem;border:1px solid var(--border,#d4e0da);border-radius:12px;background:var(--bg-card,#fff);color:inherit;font:inherit;cursor:pointer}.primary,.chosen{background:var(--accent,#247552);color:var(--accent-fg,#fff)}button:disabled{opacity:.5;cursor:default}.messages article{background:var(--bg-card,#fff);border:1px solid var(--border,#d4e0da);padding:.8rem 1rem;border-radius:14px;margin:.8rem 0;max-width:95%}.messages .own{margin-left:1rem;background:var(--bg,#edf5f0)}.messages p{margin:.4rem 0;line-height:1.55}.composer{background:var(--bg-card,#fff);padding:1rem .2rem;border-top:1px solid var(--border,#d4e0da)}textarea,input,select{font:inherit;font-size:16px;box-sizing:border-box;width:100%;padding:.7rem;margin:.4rem 0;border:1px solid var(--border,#ccc);border-radius:10px;background:var(--bg-card,#fff);color:inherit}label{display:block;margin:.5rem 0}.file{display:none}.check{display:flex;align-items:center;gap:.6rem}.check input{width:24px;height:24px}.notice{padding:.8rem;background:#fff0cf;color:#493a12;border-radius:12px}.session-head{display:flex;align-items:center;gap:.6rem;font-size:.85rem}.history{display:block;text-align:left;width:100%;margin:.6rem 0}.history span,small{display:block;font-size:.8rem;opacity:.8;margin-top:.3rem}.parents{margin-top:1.5rem;border-top:1px solid var(--border,#ccc);padding-top:1rem}summary{min-height:44px;cursor:pointer;display:flex;align-items:center}.muted{font-size:.85rem;opacity:.8}.working{padding:1rem;color:var(--accent,#247552)}
</style>
