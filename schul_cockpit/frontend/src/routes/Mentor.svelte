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
  // Die Auswahl nennt Stufen, keine Modellnamen: welches Modell dahinter
  // steht, entscheidet die Add-on-Konfiguration (D88).
  const TIER_LABELS={hoch:'Hoch',mittel:'Mittel',niedrig:'Niedrig',klein:'Klein'};
  let limits=$state({monthly_eur:50,warning_eur:40,daily_eur:10,sources_eur:30,background_eur:10,sources_model:'',opening_model:'',background_model:'',vocab_model:''}),limitsOpen=$state(false);
  async function load(){data=await api.get(`${base}?demo=${demo}`);const b=data.budget||{};limits={monthly_eur:b.limit_eur??50,warning_eur:b.warning_eur??40,daily_eur:b.daily_limit_eur??10,sources_eur:b.sources_limit_eur??30,background_eur:b.background_limit_eur??10,sources_model:b.sources_model??'',opening_model:b.opening_model??'',background_model:b.background_model??'',vocab_model:b.vocab_model??''};}
  async function act(fn){if(busy)return;busy=true;error='';try{await fn();await tick();}catch(e){error=e.message;}finally{busy=false;}}
  async function open(s){removeConfirm=false;running=await api.get(`${base}/sessions/${s.id}`);text='';attachment=null;picker=null;}
  async function start(c){running=await api.post(`${base}/sessions`,{subject:c.subject,lesson_id:c.lesson_id||null,skill_id:c.skill_id||null,goal:c.title||goal,goal_key:c.key||null,minutes:c.minutes||10,voluntary:c.voluntary||false,demo});text='';}
  // Signale fürs Zögern: Zeit von der gestellten Aufgabe bis zum Absenden, Löschungen beim Tippen.
  let taskShownAt=$state(null),edits=$state(0),spoken=$state(false);
  // Spracheingabe: Aufnahme → eigene Erkennung → Text ins Feld, erst dann Senden.
  async function transcribe(blob,took){const f=new FormData();f.append('file',blob,'aufnahme');f.append('seconds',String(took));const r=await api.post(`${base}/sessions/${running.id}/transcribe`,f);return r.text;}
  function heard(t){text=text.trim()?`${text.trim()} ${t}`:t;spoken=true;}
  const speechLabel=$derived(running?`Aufnahme: ${/englisch/i.test(running.subject)?'Englisch oder Deutsch':/spanisch/i.test(running.subject)?'Spanisch oder Deutsch':/franz/i.test(running.subject)?'Französisch oder Deutsch':/latein/i.test(running.subject)?'Latein oder Deutsch':'Deutsch'} · eigene Erkennung`:'');
  $effect(()=>{const prompt=running?.task?.prompt;if(prompt){taskShownAt=Date.now();edits=0;}else{taskShownAt=null;}});
  async function send(kind='message',value=text,option=null){
    // Angekreuzt, aber noch nicht eingebunden: geht mit dieser Nachricht mit.
    if(picked.length&&kind!=='finish')await embed();
    const signals=(kind==='answer'||kind==='choice')&&taskShownAt?{seconds:Math.min(36000,Math.round((Date.now()-taskShownAt)/1000)),edits}:{};
    const r=await api.post(`${base}/sessions/${running.id}/turn`,{request_key:crypto.randomUUID(),version:running.version,text:value,kind,attachment_id:attachment?.id||null,spoken:spoken&&value===text,...(option===null?{}:{option}),...signals});
    running=r;text='';attachment=null;spoken=false;await tick();end?.scrollIntoView({behavior:'smooth',block:'end'});
  }
  // Die Grundlage der Einheit: dieselben Seiten, die der Mentor hat. Ohne sie
  // stand das Kind vor Aufgaben, die auf ein „Material" verwiesen, das nur der
  // Mentor sehen konnte (D101). Der Text kommt erst beim Aufschlagen.
  let pages=$state({});
  async function showPage(id){if(pages[id])return;pages={...pages,[id]:{loading:true}};
    try{const m=await api.get(`/api/accounts/${accountId}/materials/${id}`);pages={...pages,[id]:{text:m.printed_text||m.content_text||'',title:m.title||''}};}
    catch(e){pages={...pages,[id]:{error:e.message}};}}
  // In Hausaufgabe und Kontrolle wird jedes Foto Material der Aufgabe und ist
  // sofort eingebunden; mehrere auf einmal, in Sechserpaketen.
  async function uploadMany(list){for(let i=0;i<list.length;i+=6){const f=new FormData();for(const file of list.slice(i,i+6))f.append('files',file);running=await api.post(`${base}/sessions/${running.id}/uploads`,f);}}
  async function upload(e){if(homeworkChat){const list=[...(e.target.files||[])];e.target.value='';if(list.length)await act(()=>uploadMany(list));return;}
    const file=e.target.files?.[0];if(!file)return;await act(async()=>{const f=new FormData();f.append('file',file);attachment=await api.post(`${base}/sessions/${running.id}/photos`,f);});e.target.value='';}
  // Aus dem Bestand einbinden: mehrere abgelegte Seiten des Fachs ankreuzen.
  // Sie bleiben für das Gespräch gesetzt; neue sind schon eine Nachricht.
  let picker=$state(null),picked=$state([]);
  const homeworkChat=$derived(running?.mode==='homework_help'||running?.mode==='homework_check');
  const freshPages=$derived((running?.materials||[]).filter(x=>!x.shown).length);
  const PICK_GROUPS=[['linked','Hängt schon an der Aufgabe'],['suggested','Passt vermutlich zur Aufgabe'],['subject','Weitere Seiten im Fach']];
  const fileUrl=id=>`./api/accounts/${accountId}/materials/${id}/file`;
  async function openPicker(){picker=await api.get(`${base}/sessions/${running.id}/materials`);picked=[];}
  // Ein anderes Fach von Hand: wenn es falsch oder gar nicht erkannt ist. Angekreuztes bleibt.
  async function pickSubject(name){picker=await api.get(`${base}/sessions/${running.id}/materials?subject=${encodeURIComponent(name)}`);}
  function togglePick(id){picked=picked.includes(id)?picked.filter(x=>x!==id):[...picked,id];}
  async function embed(){running=await api.post(`${base}/sessions/${running.id}/materials`,{material_ids:picked});picker=null;picked=[];}
  async function unembed(id){running=await api.delete(`${base}/sessions/${running.id}/materials/${id}`);}
  const pickRoom=$derived(picker?Math.max(0,picker.max-(running?.materials?.length||0)):0);
  async function leave(){if(running?.status==='active'&&data?.can_write)await api.post(`${base}/sessions/${running.id}/pause`,{paused:true});running=null;await load();}
  async function pause(hidden){if(running?.status==='active'&&data?.can_write&&!busy){try{const r=await api.post(`${base}/sessions/${running.id}/pause`,{paused:hidden});if(running?.id===r.id)running=r;}catch{/* next explicit action shows an error */}}}
  const choices=$derived(running?.messages.filter(m=>m.role==='assistant').at(-1)?.payload?.choices||[]);
  // Antwortknöpfe gelten nur an der jüngsten Aufgabe, solange sie offen ist (D164).
  const liveTask=$derived.by(()=>{const ms=running?.messages||[];for(let i=ms.length-1;i>=0;i--){if(ms[i].role==='assistant'&&ms[i].payload?.task)return ms[i].payload.task.prompt===running?.task?.prompt?i:-1;}return -1;});
  const openSessions=$derived((data?.sessions||[]).filter(s=>!s.task_done));
  // Wiederfinden: Wortlaut der Hausaufgabe, Art des Gesprächs, Stand und letzter Dialog in einer Liste.
  const MODE_NAMES={homework_help:'Hilfe zur Hausaufgabe',homework_check:'Lösung geprüft',topic:'Thema der Arbeit',practice:'Üben'};
  function when(iso){if(!iso)return '';return `${formatShortDate(iso.slice(0,10))} ${iso.slice(11,16)}`;}
  function stateOf(s){if(s.task_done)return 'Hausaufgabe abgehakt';if(s.status==='active')return 'offen';return 'beendet';}
  onMount(()=>{act(async()=>{await load();const q=new URLSearchParams(window.location.hash.split('?')[1]||'');if(q.get('session'))await open({id:Number(q.get('session'))});else if(q.get('topic_id')){running=await api.post(`${base}/sessions`,{topic_id:Number(q.get('topic_id'))});}else if(q.get('help')){running=await api.post(`${base}/sessions`,{subject:'Hausaufgabe',homework_task_id:Number(q.get('help')),voluntary:true});}else if(q.get('check')){running=await api.post(`${base}/sessions`,{subject:'Hausaufgabe',homework_task_id:Number(q.get('check')),check:true,voluntary:true});}else if(q.get('lesson_id')){await start({subject:q.get('subject')||'',lesson_id:Number(q.get('lesson_id')),title:q.get('title')||'',voluntary:true});}else if(q.get('subject')){subject=q.get('subject');goal=q.get('topic')||'';tab=q.get('mode')==='exam'?'exams':'today';}else if(q.get('goal')){const g=data.shared_plan?.goals.find(g=>g.key===q.get('goal')||g.previous_keys?.includes(q.get('goal')));if(g){focusKey=g.key;goal=g.title;subject=g.subject;if(!data.can_manage)await start({...g,voluntary:true});else if(g.session_id)await open({id:g.session_id});else tab='today';}}});const t=setInterval(()=>pause(document.hidden),30000);const v=()=>pause(document.hidden);document.addEventListener('visibilitychange',v);return()=>{clearInterval(t);document.removeEventListener('visibilitychange',v);};});
</script>
<div class="mentor">
  {#if data?.can_manage}<nav class="mode-switch" aria-label="Mentor-Modus"><button aria-pressed={!demo} class:chosen={!demo} disabled={busy||examBusy} onclick={()=>act(()=>switchMode(false))}>Kinderstand</button><button aria-pressed={demo} class:chosen={demo} disabled={busy||examBusy} onclick={()=>act(()=>switchMode(true))}>Demo ausprobieren</button></nav>
    <p class="notice">{demo?'Demo im Lernmentor: erfundene Beispiele für Klasse 6. Testgespräche und Demo-Arbeiten werden getrennt gespeichert und sind für die Kinder unsichtbar. KI-Aufrufe kosten echtes Geld aus dem Familienbudget. Eigene Eingaben und hochgeladene Fotos werden im Testverlauf gespeichert.':'Echter Kinderstand: Gespräche und Antworten des ausgewählten Kindes. Ein Gespräch auf deinem Gerät gilt als Gespräch des Kindes; nur der Demo-Modus ist eine Simulation. Was nur ein Versuch war, kannst du danach als Testlauf kennzeichnen.'}</p>
  {/if}
  {#if error}<div class="notice" role="alert"><p>{error}</p>{#if running}<button disabled={busy} onclick={()=>act(()=>open(running))}>Aktuellen Stand laden</button>{/if}</div>{/if}
  {#if running && data?.can_manage}<button disabled={busy} onclick={()=>removeConfirm=!removeConfirm}>Diese Einheit entfernen</button>{#if removeConfirm}<p class="notice">Gespräch, Antworten und Anrechnung dieser Einheit löschen?</p><button disabled={busy} onclick={()=>act(removeSession)}>Einheit endgültig löschen</button>{/if}{/if}
  {#if running}
    <header class="session-head"><button class="quiet" disabled={busy} onclick={()=>act(leave)}>← Lernen</button><span>{running.subject}{#if running.situation} · {running.situation.label}{#if running.situation.exam} · Arbeit {running.situation.exam.days===0?'heute':running.situation.exam.days===1?'morgen':`in ${running.situation.exam.days} Tagen`}{/if}{/if}{#if running.topic} · Thema {running.topic.position??'–'} von {running.topic.total} · {running.topic.stage}{:else if running.mode==='homework_help'} · Hilfe bei deiner Aufgabe{/if}</span></header>
    {#if running.is_test}<p class="notice">{running.is_demo?'Demo-Gespräch mit Beispieldaten. Kein Lernnachweis des Kindes.':'Als Testlauf gekennzeichnet: außerhalb des Lernstands und für das Kind nicht sichtbar.'}</p>{/if}
    {#if data?.can_manage&&!running.is_demo}<div class="actions"><button disabled={busy} onclick={()=>act(()=>setCounts(!!running.is_test))}>{running.is_test?'In den Kinderverlauf übernehmen':'War nur ein Test — nicht in den Lernstand'}</button></div>{/if}
    <h1>{running.label||running.goal}</h1>
    {#if running.last_at}<p class="hint">Letzter Dialog {when(running.last_at)}</p>{/if}
    {#if running.topic?.places_label}<p class="hint">{running.topic.places_label}</p>{/if}
    {#if running.topic?.basis?.length}
      <details class="basis"><summary>Grundlage aufschlagen ({running.topic.basis.length} {running.topic.basis.length===1?'Seite':'Seiten'})</summary>
        <p class="hint">Dieselben Seiten hat der Mentor. Was er dich fragt, muss er dir in der Aufgabe selbst sagen — hier kannst du trotzdem nachsehen.</p>
        {#each running.topic.basis as p}
          <details ontoggle={(e)=>{ if (e.currentTarget.open) act(()=>showPage(p.material_id)); }}>
            <summary>{p.label}{p.page?` S. ${p.page}`:''}{p.title?` · ${p.title}`:''}{p.chapter?' · gleiches Kapitel':''}</summary>
            {#if pages[p.material_id]?.loading}<p class="hint">wird geladen …</p>
            {:else if pages[p.material_id]?.error}<p class="hint">{pages[p.material_id].error}</p>
            {:else if pages[p.material_id]}<p class="preserve page">{pages[p.material_id].text||'Diese Seite ist noch nicht gelesen.'}</p>{/if}
          </details>
        {/each}
      </details>
    {/if}
    {#if running.mode==='homework_help'}<p class="hint">{running.task_done?'Diese Hausaufgabe ist abgehakt. Das Gespräch liegt im Archiv und bleibt lesbar.':'Dieses Gespräch bleibt offen, bis du die Hausaufgabe abhakst.'}</p>
    {:else if running.mode==='homework_check'}<p class="hint">{running.task_done?'Diese Hausaufgabe ist abgehakt. Die Kontrolle bleibt lesbar.':'Ich prüfe deine fertige Lösung Aufgabe für Aufgabe. Die richtige Lösung sage ich nicht vor.'}</p>{/if}
    {#if running.task && running.status==='active'}<details class="task"><summary>Deine aktuelle Aufgabe</summary>{#if running.task.vorlage}<blockquote class="vorlage preserve">{running.task.vorlage}{#if running.task.quelle}<cite>{running.task.quelle}</cite>{/if}</blockquote>{/if}<p class="preserve">{running.task.prompt}</p></details>{/if}
    <div class="messages" aria-live="polite">
      {#each running.messages as m, i}<article class:own={m.role==='user'}><span class="speaker">{m.role!=='user'?'Mentor':m.author==='eltern'?'Eltern':data?.can_manage?'Kind':'Du'}</span><p class="preserve">{m.text}</p>
        <!-- Erst das, woran gearbeitet wird, dann der Auftrag (G1). -->
        {#if m.payload.task}<div class="task"><strong>Deine Aufgabe</strong>{#if m.payload.task.vorlage}<blockquote class="vorlage preserve">{m.payload.task.vorlage}{#if m.payload.task.quelle}<cite>{m.payload.task.quelle}</cite>{/if}</blockquote>{/if}<p class="preserve">{m.payload.task.prompt}</p>{#if m.payload.task.optionen?.length}<div class="optionen" role="group" aria-label="Antwortmöglichkeiten">{#each m.payload.task.optionen as o (o.id)}<button class="option" class:aus={o.aus} disabled={busy||o.aus||!data?.can_write||i!==liveTask||running.status!=='active'} onclick={()=>act(()=>send('choice',o.text,o.id))}>{o.text}</button>{/each}</div>{/if}</div>{/if}
        {#if m.payload.material_ids?.length}<p class="hint">{m.payload.material_ids.length===1?'1 Seite':`${m.payload.material_ids.length} Seiten`} aus deinen Materialien eingebunden</p>{/if}
        {#if m.payload.attachment_id}<a href={`./${base.slice(1)}/photos/${m.payload.attachment_id}`} target="_blank" rel="noreferrer"><ActionLabel label="Dein Foto öffnen" /></a>{/if}
        <!-- Die gefundene Bearbeitung: Das Kind sieht, worüber gesprochen wird, bevor es bestätigt. -->
        {#if m.payload.material}<a class="found" href={`./api/accounts/${accountId}/materials/${m.payload.material.id}/file`} target="_blank" rel="noreferrer"><img src={`./api/accounts/${accountId}/materials/${m.payload.material.id}/file`} alt={`Deine Bearbeitung: ${m.payload.material.label}`} loading="lazy" /><small>{m.payload.material.label}</small></a>{/if}
        {#if m.payload.assessment}<p class="assessment">{m.payload.assessment.rationale}<small>{m.payload.assessment.label}{m.payload.assessment.help_used?' · mit Unterstützung':''}</small></p>{/if}
      </article>{/each}<div bind:this={end}></div>
    </div>
    {#if running.status==='active'&&data?.can_write}
      <div class="choices">{#each choices as c}<button disabled={busy||!data?.can_write} onclick={()=>act(()=>send(c==='Für heute fertig'?'finish':c.includes('Beispiel')?'example':/Tipp/.test(c)?'hint':'message',c))}>{c}</button>{/each}</div>
      <form class="composer" onsubmit={e=>{e.preventDefault();act(()=>send(running.task?'answer':'message'));}}>
        {#if data?.speech}<Speech onText={heard} {transcribe} disabled={busy||!data?.can_write} label={speechLabel}/>{/if}
        <label for="mentor-answer">{running.task?'Dein Versuch oder deine Frage':running.mode==='homework_check'&&!attachment&&!running.materials?.length?'Foto anhängen oder Seiten aus deinen Materialien wählen, dazu eine Frage, wenn du willst':'Was möchtest du sagen?'}{#if spoken} · erkannt, bitte prüfen{/if}</label>
        <textarea id="mentor-answer" bind:value={text} rows="3" maxlength="4000" disabled={busy||!data?.can_write} placeholder={data?.speech?'… oder tippen':'Deine Antwort oder Frage …'} onbeforeinput={e=>{if((e.inputType||'').startsWith('delete'))edits++;}}></textarea>
        {#if attachment}<p>Foto angehängt. <button type="button" onclick={()=>attachment=null}>Entfernen</button></p>{/if}
        {#if running.materials?.length}
          <div class="embedded" aria-label="Eingebundene Seiten">
            <p class="hint">{`Eingebunden: ${running.materials.length===1?'1 Seite':`${running.materials.length} Seiten`}${freshPages?` · ${freshPages===1?'eine neu, geht':`${freshPages} neu, gehen`} mit der nächsten Nachricht mit`:''}`}</p>
            <ul>{#each running.materials as x (x.id)}<li class:fresh={!x.shown}>
              <a href={fileUrl(x.id)} target="_blank" rel="noreferrer">{#if x.mime_type?.startsWith('image/')}<img src={fileUrl(x.id)} alt="" loading="lazy" />{:else}<span class="doc" aria-hidden="true">📄</span>{/if}<small>{x.title}</small></a>
              <button type="button" class="quiet" disabled={busy} aria-label={`${x.title} wieder lösen`} onclick={()=>act(()=>unembed(x.id))}>✕</button>
            </li>{/each}</ul>
          </div>
        {/if}
        {#if picker}
          <div class="picker">
            <p><strong>Seiten aus deinen Materialien</strong></p>
            {#if picker.subjects?.length}
              <label class="pick-subject">Fach
                <select value={picker.subject} disabled={busy} onchange={e=>act(()=>pickSubject(e.currentTarget.value))}>
                  {#if !picker.subject}<option value="">Bitte wählen</option>{/if}
                  {#if picker.subject&&!picker.subjects.some(x=>x.name.toLowerCase()===picker.subject.toLowerCase())}<option value={picker.subject}>{picker.subject} (nichts abgelegt)</option>{/if}
                  {#each picker.subjects as x (x.name)}<option value={x.name}>{x.name} ({x.count})</option>{/each}
                </select>
              </label>
              {#if !picker.task_subject}<p class="hint">Das Fach dieser Hausaufgabe ist nicht erkannt. Wähle es oben aus.</p>{/if}
            {/if}
            {#if !picker.items.length}<p class="hint">{picker.subject?'Zu diesem Fach ist noch nichts abgelegt.':'Noch nichts abgelegt.'}</p>{/if}
            {#each PICK_GROUPS as [key,title]}
              {@const group=picker.items.filter(x=>x.group===key)}
              {#if group.length}<p class="hint">{title}</p>
                <ul>{#each group as x (x.id)}
                  {@const on=x.chosen||running.materials?.some(y=>y.id===x.id)}
                  <li><label class:on={on||picked.includes(x.id)}>
                    <input type="checkbox" checked={on||picked.includes(x.id)} disabled={on||(!picked.includes(x.id)&&picked.length>=pickRoom)} onchange={()=>togglePick(x.id)} />
                    {#if x.mime_type?.startsWith('image/')}<img src={fileUrl(x.id)} alt="" loading="lazy" />{:else}<span class="doc" aria-hidden="true">📄</span>{/if}
                    <span>{x.title}<small>{[x.label!==x.title?x.label:'',x.date?formatShortDate(x.date):'',on?'schon eingebunden':x.reason].filter(Boolean).join(' · ')}</small></span>
                  </label></li>
                {/each}</ul>
              {/if}
            {/each}
            <div class="actions pick-actions"><button type="button" class="primary" disabled={busy||!picked.length} onclick={()=>act(embed)}>{picked.length===1?'1 Seite einbinden':picked.length?`${picked.length} Seiten einbinden`:'Seiten ankreuzen'}</button><button type="button" disabled={busy} onclick={()=>{picker=null;picked=[];}}>Abbrechen</button></div>
            {#if pickRoom<=picked.length}<p class="hint">Mehr als {picker.max} Seiten gehen in einem Gespräch nicht.</p>{/if}
          </div>
        {/if}
        <div class="actions"><button class="primary" disabled={busy||(!text.trim()&&!attachment&&!freshPages&&!picked.length)||!data?.can_write}>{picked.length?`Senden mit ${picked.length===1?'1 Seite':`${picked.length} Seiten`}`:'Senden'}</button><button type="button" class:primary={running.mode==='homework_check'&&!attachment&&!running.attachments?.length&&!running.materials?.length} disabled={busy||!data?.can_write} onclick={()=>fileInput?.click()}>{running.mode==='homework_check'?'Fotos der Lösung':homeworkChat?'Fotos zeigen':'Foto zeigen'}</button><input class="file" type="file" accept={homeworkChat?'image/*,application/pdf':'image/*'} multiple={homeworkChat} bind:this={fileInput} onchange={upload}/>{#if homeworkChat}<button type="button" disabled={busy||!data?.can_write} onclick={()=>act(openPicker)}>Aus Materialien</button>{/if}<a class="material-link" href={`#/materialien/${encodeURIComponent(running.subject||'')}${homeworkChat&&running.task_id?`/${running.task_id}`:''}`} title="Arbeitsblatt, Heftseite oder PDF dauerhaft ablegen"><ActionLabel label="Material hinzufügen" /></a></div>
        <div class="actions"><button type="button" disabled={busy||!data?.can_write} onclick={()=>act(()=>send('hint','Bitte anders erklären.'))}>Anders erklären</button><button type="button" disabled={busy||!data?.can_write} onclick={()=>act(()=>send('finish','Für heute fertig.'))}>Für heute fertig</button></div>
      </form>
    {:else}<section class="card"><h2>{running.status==='active'?'Gespeicherter Verlauf':running.topic?'Einheit beendet':running.mode==='homework_check'?'Kontrolle beendet':running.untimed?'Unterbrochen':'Für heute geschafft'}</h2><p>{running.summary||'Dein Gespräch und deine Antworten bleiben gespeichert.'}</p>{#if running.topic}<p><strong>Stufe: {running.topic.stage}</strong>{#if running.topic.reason&&running.topic.stage!=='neu'} · {running.topic.reason}{/if}{#if running.topic.next_check} · Kurzprüfung ab {formatShortDate(running.topic.next_check)}{/if}</p><a href="#/klausuren">Zur Arbeit und den anderen Themen</a>{/if}
      {#if running.status!=='active'&&data?.can_write}<button class="primary" disabled={busy} onclick={()=>act(resume)}><ActionLabel kind="chat" label="Hier weitermachen" /></button>{/if}
      <button onclick={()=>act(leave)}>Zur Übersicht</button><a href="#/plan"><ActionLabel label="Aktualisierten Lernplan ansehen" /></a></section>{/if}
    <!-- Bei einer Abfrage führt die App den Bestand. Was offen ist, steht hier
         und nicht nur im Merkzettel des Modells: Das Kind musste vorher danach
         fragen, und die Antwort war unvollständig (D91). -->
    {#if running.quiz_open?.length}<p class="muted">Noch zu wiederholen: {running.quiz_open.join(', ')}.</p>
    {:else if running.quiz?.length}<p class="muted">Alles wiederholt: {running.quiz.length} {running.quiz.length===1?'Wort':'Wörter'} sitzen.</p>{/if}
    {#if busy}<p role="status" class="working">{running.messages.length<=1?'Dein Coach schaut sich Thema und Material an …':'Einen Moment – deine Antwort wird vorbereitet …'}</p>{/if}
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
      {#if data.legacy_sessions?.length}<details><summary>Als Testlauf gekennzeichnet ({data.legacy_sessions.length})</summary><p>Diese Gespräche stehen außerhalb des Lernstands und sind für das Kind nicht sichtbar. Beim Öffnen lassen sie sich in den Kinderverlauf übernehmen.</p>{#each data.legacy_sessions as s}<button class="history" onclick={()=>act(()=>open(s))}>{s.subject} · {s.goal}</button>{/each}</details>{/if}
    {:else if tab==='progress'}
      {#if demo}<p class="notice">Demo-Antworten erzeugen keine Lernbeobachtungen oder Wiederholungen für das Kind.</p>{/if}<p>Hier zählt, was du an Aufgaben gezeigt hast. Eine richtige Antwort direkt nach einer Erklärung prüfen wir später noch einmal.</p>
      {#each data.progress as p}<section class="card"><span>{p.subject}</span><h2>{p.title}</h2><p>{p.label}</p><p>{p.attempts} Versuche · {p.variants} unterschiedliche Aufgaben selbstständig gelöst</p><button onclick={()=>act(async()=>{evidence=await api.get(`${base}/evidence/${p.id}`);})}>Antworten ansehen</button></section>{:else}<p>Deine Fortschritte erscheinen nach dem Üben. </p>{/each}
      {#if evidence}<section class="card"><h2>Die einzelnen Beobachtungen</h2>{#each evidence as e}<p class="preserve">{e.answer}</p><p>{e.rationale}</p><small>{formatShortDate(e.created_at.slice(0,10))} · {e.help_used?'mit Hilfe':'ohne angeforderten Hinweis'} · KI-Einschätzung</small>{#if data.can_manage&&!e.invalidated}<label>Was war an der Bewertung falsch?<input bind:value={correction}/></label><button disabled={busy||correction.length<3} onclick={()=>act(async()=>{await api.post(`${base}/evidence/${e.id}/invalidate`,{reason:correction});evidence=null;await load();})}>Bewertung zurücknehmen</button>{/if}<hr/>{/each}<button onclick={()=>evidence=null}>Schließen</button></section>{/if}
    {:else}<MentorExams {accountId} {demo} subjects={data.subjects} canManage={data.can_manage} initialSubject={subject} initialTopic={goal} onBusy={v=>examBusy=v}/>{/if}
    {#if data.can_manage&&!demo}<details class="parents"><summary>Echte Einstellungen und Übungen verwalten</summary>
      <p>Gespräche und Antworten werden gespeichert. Autorisierte Eltern können sie hier gemeinsam mit dem Kind ansehen.</p>
      <p><strong>{data.budget.used_eur.toFixed(2)} € bisher</strong> · {data.budget.month}{#if data.budget.projected_eur} · hochgerechnet {data.budget.projected_eur.toFixed(0)} € zum Monatsende{/if}</p><p class="muted">{data.budget.accounting}; der gebuchte Wert liegt bewusst über der tatsächlichen Rechnung. Zuletzt {data.budget.per_day_eur?.toFixed(2)} € am Tag. Richtwerte: {data.budget.limit_eur.toFixed(0)} € im Monat, {data.budget.daily_limit_eur?.toFixed(0)} € am Tag je Kind{#if data.budget.sources_limit_eur}, Quellenbestand {data.budget.sources_eur.toFixed(2)} € von {data.budget.sources_limit_eur.toFixed(0)} €{/if}. Sie halten nichts an.</p>
      {#if data.budget.warning}<p class="notice">Die Hochrechnung liegt bei {data.budget.projected_eur?.toFixed(0)} € und damit über dem Richtwert von {data.budget.warning_eur.toFixed(0)} €. Nichts wird gesperrt; wenn du gegensteuern willst, ist die Stufe fürs Abschreiben der größte Hebel.</p>{/if}
      {#if data.budget.over_budget?.length}<p class="muted">Überschritten in diesem Monat: {data.budget.over_budget.join(', ')}. Die Aufrufe sind trotzdem gelaufen.</p>{/if}
      {#if !data.budget.rate_available}<p class="notice">Die Kostensätze müssen vor neuen KI-Aufrufen geprüft werden.</p>{/if}
      {#if !data.budget.opening_confirmed}<form onsubmit={e=>{e.preventDefault();act(async()=>{await api.put(`${base}/budget-opening`,{spent_eur:spent});await load();});}}><p>Vor der neuen Verbrauchserfassung gab es bereits KI-Aufrufe. Bitte den bisherigen Monatsverbrauch aus Azure berücksichtigen.</p><label>Bisherige Mentor-Kosten dieses Monats in Euro<input type="number" min="0" max="1000" step="0.01" required bind:value={spent}/></label><button disabled={busy}>Anfangsstand bestätigen</button></form>{/if}
      <details><summary>KI-Rahmen einstellen</summary>
        <p class="muted">Der Tagesrahmen zählt nur, was das Kind selbst übt und fragt. Quellen und Hintergrund haben eigene Monatsrahmen innerhalb des Monatsrahmens. Das Modell fürs Abschreiben wird nur nach Eichung an echten Seiten umgestellt; Erklären und Üben bleiben beim Hauptmodell.</p>
        <form class="limits" onsubmit={e=>{e.preventDefault();act(async()=>{await api.put(`${base}/budget-limits`,{monthly_eur:Number(limits.monthly_eur),warning_eur:Number(limits.warning_eur),daily_eur:Number(limits.daily_eur),sources_eur:Number(limits.sources_eur),background_eur:Number(limits.background_eur),sources_model:limits.sources_model??'',opening_model:limits.opening_model??'',background_model:limits.background_model??'',vocab_model:limits.vocab_model??''});await load();limitsOpen=false;});}}>
          <label>Monat gesamt (€)<input type="number" min="1" max="1000" step="1" bind:value={limits.monthly_eur}/></label>
          <label>Warnen, wenn die Hochrechnung übersteigt (€)<input type="number" min="1" max="1000" step="1" bind:value={limits.warning_eur}/></label>
          <label>Tag je Kind (€)<input type="number" min="0.5" max="200" step="0.5" bind:value={limits.daily_eur}/></label>
          <label>Quellenbestand im Monat (€)<input type="number" min="0" max="1000" step="1" bind:value={limits.sources_eur}/></label>
          <label>Hintergrund im Monat (€)<input type="number" min="0" max="1000" step="1" bind:value={limits.background_eur}/></label>
          <label>Stufe für den Einstieg in eine Einheit<select bind:value={limits.opening_model}><option value="">wie das Hauptgespräch ({data.budget.model})</option>{#each data.budget.models??[] as m}<option value={m}>{TIER_LABELS[m]??m} · {data.budget.rates?.[m]?.model}{data.budget.rates?.[m]?.estimated?' · Kostensatz geschätzt':''}</option>{/each}</select></label>
          <label>Stufe für die Unterrichtsauswertung<select bind:value={limits.background_model}><option value="">wie das Hauptgespräch ({data.budget.model})</option>{#each data.budget.models??[] as m}<option value={m}>{TIER_LABELS[m]??m} · {data.budget.rates?.[m]?.model}{data.budget.rates?.[m]?.estimated?' · Kostensatz geschätzt':''}</option>{/each}</select></label>
          <label>Stufe fürs Abschreiben<select bind:value={limits.sources_model}><option value="">wie das Hauptgespräch ({data.budget.model})</option>{#each data.budget.models??[] as m}<option value={m}>{TIER_LABELS[m]??m} · {data.budget.rates?.[m]?.model} · {data.budget.rates?.[m]?.input_per_m ?? '?'} / {data.budget.rates?.[m]?.output_per_m ?? '?'} € je Mio. Token</option>{/each}</select></label>
          <label>Stufe fürs Lesen der Vokabellisten<select bind:value={limits.vocab_model}><option value="">wie das Abschreiben</option>{#each data.budget.models??[] as m}<option value={m}>{TIER_LABELS[m]??m} · {data.budget.rates?.[m]?.model}{data.budget.rates?.[m]?.estimated?' · Kostensatz geschätzt':''}</option>{/each}</select></label>
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
  .free-choice{background:var(--accent-soft);border-color:var(--accent)}nav[aria-label="Lernbereiche"]{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}nav[aria-label="Lernbereiche"] button{text-align:left}nav[aria-label="Lernbereiche"] button span{margin-right:6px}
  .mode-switch{display:grid;grid-template-columns:1fr 1fr}.mentor{max-width:720px;margin:auto;padding-bottom:1.5rem}h1{font-size:1.55rem;line-height:1.25;overflow-wrap:anywhere}h2{font-size:1.1rem;line-height:1.35}.eyebrow,.speaker{font-size:.8rem;font-weight:650;opacity:.8}.card,.task{border:1px solid var(--border,#d4e0da);background:var(--bg-card,#fff);padding:1rem;border-radius:16px;margin:1rem 0}.task{position:relative}.optionen{display:grid;gap:8px;margin-top:.6rem}.option{text-align:left;min-height:48px;border-radius:12px;padding:.6rem .9rem;background:var(--bg-elevated,#fff);border:1px solid var(--border);font-weight:550}.option.aus{text-decoration:line-through;opacity:.55}.preserve{white-space:pre-wrap;overflow-wrap:anywhere}nav,.choices,.actions{display:flex;gap:.5rem;flex-wrap:wrap;margin:.6rem 0}button{min-height:44px;min-width:44px;padding:.6rem .85rem;border:1px solid var(--border,#d4e0da);border-radius:12px;background:var(--bg-card,#fff);color:inherit;font:inherit;cursor:pointer}.primary,.chosen{background:var(--accent,#247552);color:var(--accent-fg,#fff)}button:disabled{opacity:.5;cursor:default}.messages article{background:var(--bg-card,#fff);border:1px solid var(--border,#d4e0da);padding:.8rem 1rem;border-radius:14px;margin:.8rem 0;max-width:95%}.messages .own{margin-left:1rem;background:var(--bg,#edf5f0)}.messages p{margin:.4rem 0;line-height:1.55}.composer{background:var(--bg-card,#fff);padding:1rem .2rem;border-top:1px solid var(--border,#d4e0da)}textarea,input,select{font:inherit;font-size:16px;box-sizing:border-box;width:100%;padding:.7rem;margin:.4rem 0;border:1px solid var(--border,#ccc);border-radius:10px;background:var(--bg-card,#fff);color:inherit}label{display:block;margin:.5rem 0}.file{display:none}.check{display:flex;align-items:center;gap:.6rem}.check input{width:24px;height:24px}.notice{padding:.8rem;background:var(--warm-soft);color:var(--fg);border-radius:12px}.session-head{display:flex;align-items:center;gap:.6rem;font-size:.85rem}.history{display:block;text-align:left;width:100%;margin:.6rem 0}.history span,small{display:block;font-size:.8rem;opacity:.8;margin-top:.3rem}.history.filed{opacity:.75}.parents{margin-top:1.5rem;border-top:1px solid var(--border,#ccc);padding-top:1rem}summary{min-height:44px;cursor:pointer;display:flex;align-items:center}.muted{font-size:.85rem;opacity:.8}.working{padding:1rem;color:var(--accent,#247552)}.basis{border:1px solid var(--border,#d4e0da);border-radius:16px;padding:.4rem .8rem;margin:.8rem 0}.basis details{margin:.3rem 0;border-top:1px solid var(--border,#d4e0da)}.basis .page{font-size:.9rem;line-height:1.5;max-height:60vh;overflow:auto}.vorlage{margin:.5rem 0;padding:.6rem .8rem;border-left:3px solid var(--accent,#247552);background:var(--bg,#edf5f0);border-radius:0 10px 10px 0;font-size:1.02rem;line-height:1.6}.vorlage cite{display:block;margin-top:.4rem;font-size:.8rem;font-style:normal;opacity:.75}.found{display:block;margin:.5rem 0}
.embedded ul,.picker ul{list-style:none;margin:.3rem 0;padding:0}
.embedded ul{display:flex;gap:.5rem;flex-wrap:wrap}
.embedded li{display:flex;align-items:flex-start;gap:.2rem}
.embedded li a{display:block;color:inherit;text-decoration:none}
.embedded img,.embedded .doc{display:block;width:6.5rem;height:5rem;object-fit:cover;object-position:top;border:1px solid var(--border,#d4e0da);border-radius:8px}
.embedded .doc{display:grid;place-items:center;font-size:1.8rem}
.embedded li.fresh img,.embedded li.fresh .doc{border:2px solid var(--primary,#2f7d5b)}
.embedded small{display:block;max-width:6.5rem;font-size:.75rem;overflow-wrap:anywhere}
.picker{border:1px solid var(--border,#d4e0da);border-radius:12px;padding:.6rem;margin:.5rem 0;max-height:60vh;overflow-y:auto}
.picker li label{display:flex;align-items:center;gap:.6rem;margin:.25rem 0;padding:.3rem;border-radius:8px;cursor:pointer}
.picker li label.on{background:var(--bg-soft,#eef5f1)}
.picker input{width:22px;height:22px;flex:none}
.picker img,.picker .doc{width:3.5rem;height:3.5rem;flex:none;object-fit:cover;object-position:top;border-radius:6px;border:1px solid var(--border,#d4e0da)}
.picker .doc{display:grid;place-items:center;font-size:1.4rem}
.picker li span{min-width:0;overflow-wrap:anywhere}
.picker small{display:block;opacity:.75}
.pick-subject{display:block;margin:.3rem 0 .6rem}
.pick-actions{position:sticky;bottom:-.6rem;margin:.4rem -.6rem -.6rem;padding:.6rem;background:var(--bg-card,#fff);border-top:1px solid var(--border,#d4e0da)}
.pick-subject select{display:block;width:100%;margin-top:.3rem;min-height:44px;font:inherit;font-size:16px;padding:.5rem;border-radius:10px;border:1px solid var(--border,#ccc);background:var(--bg-card,#fff);color:inherit}.found img{display:block;width:100%;max-width:22rem;max-height:14rem;object-fit:cover;object-position:top;border:1px solid var(--border,#d4e0da);border-radius:12px}.found small{display:block;margin-top:.25rem}
</style>
