<script>
  // Eine laufende Einheit mit dem Lernbegleiter (D186): der Chat als eigene
  // Ansicht, gemeinsam für die Lernseite des Kindes und den Lernraum der Eltern.
  // Funktional wie zuvor in Mentor.svelte.
  import ActionLabel from './ActionLabel.svelte';
  import {formatShortDate} from './format.js';
  import {onMount,tick} from 'svelte';
  import {api} from './api.js';
  import Speech from './Speech.svelte';
  let {accountId,running=$bindable(),canWrite=false,canManage=false,speech=false,backLabel='Lernen',onleave=async()=>{},onreload=async()=>{}}=$props();
  const base=$derived(`/api/accounts/${accountId}/learning/mentor`);
  let error=$state(''),busy=$state(false),text=$state(''),attachment=$state(null),fileInput=$state(null),removeConfirm=$state(false),end=$state(null);
  async function act(fn){if(busy)return;busy=true;error='';try{await fn();await tick();}catch(e){error=e.message;}finally{busy=false;}}
  async function open(s){removeConfirm=false;running=await api.get(`${base}/sessions/${s.id}`);text='';attachment=null;picker=null;}
  async function removeSession(){await api.delete(`${base}/sessions/${running.id}`,{version:running.version});removeConfirm=false;running=null;await onleave();}
  async function resume(){running=await api.post(`${base}/sessions/${running.id}/resume`,{});text='';attachment=null;}
  async function setCounts(counts){running=await api.put(`${base}/sessions/${running.id}/counts`,{counts});await onreload();}
  // Signale fürs Zögern: Zeit von der gestellten Aufgabe bis zum Absenden, Löschungen beim Tippen.
  let taskShownAt=$state(null),edits=$state(0),spoken=$state(false);
  // Spracheingabe: Aufnahme → eigene Erkennung → Text ins Feld, erst dann Senden.
  let lastTook=0;
  async function transcribe(blob,took){lastTook=took;const f=new FormData();f.append('file',blob,'aufnahme');f.append('seconds',String(took));const r=await api.post(`${base}/sessions/${running.id}/transcribe`,f);return r.text;}
  // Sprechprobe (D194): Das Gesagte geht direkt ab, ungeprüft; bewertet wird, was gesagt wurde.
  function heard(t){if(oral){const took=lastTook;act(()=>send('message',t,null,{spoken:true,seconds:took}));return;}text=text.trim()?`${text.trim()} ${t}`:t;spoken=true;}
  const oral=$derived(running?.mode==='oral');
  // Der Prüfer spricht: seine Nachrichten liest der Browser in der Fremdsprache vor (abschaltbar).
  const voiceLang=$derived(/spanisch/i.test(running?.subject||'')?'es-ES':/franz/i.test(running?.subject||'')?'fr-FR':'en-GB');
  let tts=$state((()=>{try{return localStorage.getItem('oralTts')!=='0';}catch{return true;}})());
  function toggleTts(){tts=!tts;try{localStorage.setItem('oralTts',tts?'1':'0');}catch{/* egal */}if(!tts)window.speechSynthesis?.cancel();}
  let spokenUpTo=null,spokenSid=null;
  $effect(()=>{const ms=running?.messages||[];const last=ms.filter(m=>m.role==='assistant').at(-1);if(!oral||!last)return;
    // Beim Öffnen einer Probe nur Neues vorlesen; eine frisch gestartete beginnt mit der ersten Frage.
    if(spokenSid!==running.id){spokenSid=running.id;spokenUpTo=ms.length<=1?0:last.id;}
    if(last.id>spokenUpTo){spokenUpTo=last.id;if(tts&&running.status==='active'&&window.speechSynthesis&&!last.payload?.oral_result){try{window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(last.text);u.lang=voiceLang;u.rate=0.95;window.speechSynthesis.speak(u);}catch{/* ohne Stimme weiter */}}}});
  onMount(()=>()=>window.speechSynthesis?.cancel());
  const answers=$derived((running?.messages||[]).filter(m=>m.role==='user').length);
  const speechLabel=$derived(oral?`Aufnahme: ${voiceLang.startsWith('en')?'Englisch':voiceLang.startsWith('es')?'Spanisch':'Französisch'} · geht direkt ab`:running?`Aufnahme: ${/englisch/i.test(running.subject)?'Englisch oder Deutsch':/spanisch/i.test(running.subject)?'Spanisch oder Deutsch':/franz/i.test(running.subject)?'Französisch oder Deutsch':/latein/i.test(running.subject)?'Latein oder Deutsch':'Deutsch'} · eigene Erkennung`:'');
  $effect(()=>{const prompt=running?.task?.prompt;if(prompt){taskShownAt=Date.now();edits=0;}else{taskShownAt=null;}});
  async function send(kind='message',value=text,option=null,extra={}){
    // Angekreuzt, aber noch nicht eingebunden: geht mit dieser Nachricht mit.
    if(picked.length&&kind!=='finish')await embed();
    const signals=(kind==='answer'||kind==='choice')&&taskShownAt?{seconds:Math.min(36000,Math.round((Date.now()-taskShownAt)/1000)),edits}:{};
    const r=await api.post(`${base}/sessions/${running.id}/turn`,{request_key:crypto.randomUUID(),version:running.version,text:value,kind,attachment_id:attachment?.id||null,spoken:extra.spoken??(spoken&&value===text),...(option===null?{}:{option}),...signals,...(extra.seconds?{seconds:Math.min(36000,Math.round(extra.seconds))}:{})});
    running=r;text='';attachment=null;spoken=false;await tick();end?.scrollIntoView({behavior:'smooth',block:'end'});
  }
  // Die Grundlage der Einheit: dieselben Seiten, die der Mentor hat (D101).
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
  let picker=$state(null),picked=$state([]);
  const homeworkChat=$derived(running?.mode==='homework_help'||running?.mode==='homework_check');
  const freshPages=$derived((running?.materials||[]).filter(x=>!x.shown).length);
  const PICK_GROUPS=[['linked','Hängt schon an der Aufgabe'],['suggested','Passt vermutlich zur Aufgabe'],['subject','Weitere Seiten im Fach']];
  const fileUrl=id=>`./api/accounts/${accountId}/materials/${id}/file`;
  async function openPicker(){picker=await api.get(`${base}/sessions/${running.id}/materials`);picked=[];}
  async function pickSubject(name){picker=await api.get(`${base}/sessions/${running.id}/materials?subject=${encodeURIComponent(name)}`);}
  function togglePick(id){picked=picked.includes(id)?picked.filter(x=>x!==id):[...picked,id];}
  async function embed(){running=await api.post(`${base}/sessions/${running.id}/materials`,{material_ids:picked});picker=null;picked=[];}
  async function unembed(id){running=await api.delete(`${base}/sessions/${running.id}/materials/${id}`);}
  const pickRoom=$derived(picker?Math.max(0,picker.max-(running?.materials?.length||0)):0);
  async function leave(){if(running?.status==='active'&&canWrite)await api.post(`${base}/sessions/${running.id}/pause`,{paused:true});running=null;await onleave();}
  async function pause(hidden){if(running?.status==='active'&&canWrite&&!busy){try{const r=await api.post(`${base}/sessions/${running.id}/pause`,{paused:hidden});if(running?.id===r.id)running=r;}catch{/* next explicit action shows an error */}}}
  const choices=$derived(running?.messages.filter(m=>m.role==='assistant').at(-1)?.payload?.choices||[]);
  // Antwortknöpfe gelten nur an der jüngsten Aufgabe, solange sie offen ist (D164).
  const liveTask=$derived.by(()=>{const ms=running?.messages||[];for(let i=ms.length-1;i>=0;i--){if(ms[i].role==='assistant'&&ms[i].payload?.task)return ms[i].payload.task.prompt===running?.task?.prompt?i:-1;}return -1;});
  function when(iso){if(!iso)return '';return `${formatShortDate(iso.slice(0,10))} ${iso.slice(11,16)}`;}
  onMount(()=>{const t=setInterval(()=>pause(document.hidden),30000);const v=()=>pause(document.hidden);document.addEventListener('visibilitychange',v);return()=>{clearInterval(t);document.removeEventListener('visibilitychange',v);};});
</script>
{#if running}
<div class="mentor session">
  {#if error}<div class="notice" role="alert"><p>{error}</p>{#if running}<button disabled={busy} onclick={()=>act(()=>open(running))}>Aktuellen Stand laden</button>{/if}</div>{/if}
  {#if canManage}<button disabled={busy} onclick={()=>removeConfirm=!removeConfirm}>Diese Einheit entfernen</button>{#if removeConfirm}<p class="notice">Gespräch, Antworten und Anrechnung dieser Einheit löschen?</p><button disabled={busy} onclick={()=>act(removeSession)}>Einheit endgültig löschen</button>{/if}{/if}
    <header class="session-head"><button class="quiet" disabled={busy} onclick={()=>act(leave)}>← {backLabel}</button><span>{running.subject}{#if running.situation} · {running.situation.label}{#if running.situation.exam} · Arbeit {running.situation.exam.days===0?'heute':running.situation.exam.days===1?'morgen':`in ${running.situation.exam.days} Tagen`}{/if}{/if}{#if running.topic} · Thema {running.topic.position??'–'} von {running.topic.total} · {running.topic.stage}{:else if running.mode==='homework_help'} · Hilfe bei deiner Aufgabe{/if}</span></header>
    {#if running.is_test}<p class="notice">{running.is_demo?'Demo-Gespräch mit Beispieldaten. Kein Lernnachweis des Kindes.':'Als Testlauf gekennzeichnet: außerhalb des Lernstands und für das Kind nicht sichtbar.'}</p>{/if}
    {#if canManage&&!running.is_demo}<div class="actions"><button disabled={busy} onclick={()=>act(()=>setCounts(!!running.is_test))}>{running.is_test?'In den Kinderverlauf übernehmen':'War nur ein Test — nicht in den Lernstand'}</button></div>{/if}
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
      {#each running.messages as m, i}<article class:own={m.role==='user'}><span class="speaker">{m.role!=='user'?'Mentor':m.author==='eltern'?'Eltern':canManage?'Kind':'Du'}</span><p class="preserve">{m.text}</p>
        <!-- Erst das, woran gearbeitet wird, dann der Auftrag (G1). -->
        {#if m.payload.task}<div class="task"><strong>Deine Aufgabe</strong>{#if m.payload.task.vorlage}<blockquote class="vorlage preserve">{m.payload.task.vorlage}{#if m.payload.task.quelle}<cite>{m.payload.task.quelle}</cite>{/if}</blockquote>{/if}<p class="preserve">{m.payload.task.prompt}</p>{#if m.payload.task.optionen?.length}<div class="optionen" role="group" aria-label="Antwortmöglichkeiten">{#each m.payload.task.optionen as o (o.id)}<button class="option" class:aus={o.aus} disabled={busy||o.aus||!canWrite||i!==liveTask||running.status!=='active'} onclick={()=>act(()=>send('choice',o.text,o.id))}>{o.text}</button>{/each}</div>{/if}</div>{/if}
        {#if m.payload.material_ids?.length}<p class="hint">{m.payload.material_ids.length===1?'1 Seite':`${m.payload.material_ids.length} Seiten`} aus deinen Materialien eingebunden</p>{/if}
        {#if m.payload.attachment_id}<a href={`./${base.slice(1)}/photos/${m.payload.attachment_id}`} target="_blank" rel="noreferrer"><ActionLabel label="Dein Foto öffnen" /></a>{/if}
        <!-- Die gefundene Bearbeitung: Das Kind sieht, worüber gesprochen wird, bevor es bestätigt. -->
        {#if m.payload.material}<a class="found" href={`./api/accounts/${accountId}/materials/${m.payload.material.id}/file`} target="_blank" rel="noreferrer"><img src={`./api/accounts/${accountId}/materials/${m.payload.material.id}/file`} alt={`Deine Bearbeitung: ${m.payload.material.label}`} loading="lazy" /><small>{m.payload.material.label}</small></a>{/if}
        {#if m.payload.oral_result}
          {@const r=m.payload.oral_result}
          <div class="oral-result" aria-label="Bewertung der Sprechprobe">
            {#if !r.reliable}<p class="hint">Zu kurz für eine verlässliche Bewertung.</p>{/if}
            <ul class="scores">{#each r.scores as sc (sc.criterion)}<li><span class="crit">{sc.label}</span><span class="dots" aria-label={`${sc.score} von 4`}>{#each [1,2,3,4] as n}<i class:on={n<=sc.score}></i>{/each}</span>{#if sc.evidence}<small>„{sc.evidence}“{sc.comment?` · ${sc.comment}`:''}</small>{/if}</li>{/each}</ul>
            {#if r.weak_spots?.length}<p><strong>Darauf achten wir beim nächsten Mal</strong></p><ul class="weak">{#each r.weak_spots as w}<li><b>{w.label}</b>{#if w.example}<br><small>Du: „{w.example}“</small>{/if}{#if w.better}<br><small>Besser: „{w.better}“</small>{/if}</li>{/each}</ul>{/if}
            {#if r.followups?.length}<p><strong>Seit dem letzten Mal</strong></p><ul class="weak">{#each r.followups as f}<li>{f.label}: <b>{({besser:'besser',gleich:'gleich',schlechter:'schwächer',nicht_geprueft:'diesmal nicht vorgekommen'})[f.status]}</b></li>{/each}</ul>{/if}
            {#if r.level_note}<p class="hint">{r.level_note}</p>{/if}
            <p class="hint">Aussprache wird nicht bewertet; die App sieht nur, was erkannt wurde.</p>
          </div>
        {/if}
        {#if m.payload.assessment}<p class="assessment">{m.payload.assessment.rationale}<small>{m.payload.assessment.label}{m.payload.assessment.help_used?' · mit Unterstützung':''}</small></p>{/if}
      </article>{/each}<div bind:this={end}></div>
    </div>
    {#if running.status==='active'&&canWrite}
      <div class="choices">{#each choices as c}<button disabled={busy||!canWrite} onclick={()=>act(()=>send(c==='Für heute fertig'||c==='Beenden und auswerten'?'finish':c.includes('Beispiel')?'example':/Tipp/.test(c)?'hint':'message',c))}>{c}</button>{/each}</div>
      <form class="composer" onsubmit={e=>{e.preventDefault();act(()=>send(running.task?'answer':'message'));}}>
        {#if speech}<Speech onText={heard} {transcribe} disabled={busy||!canWrite} label={speechLabel}/>{/if}
        {#if oral}<p class="hint">{speech?'Halte den Sprechknopf und antworte in ganzen Sätzen; was du sagst, geht direkt ab.':'Antworte in ganzen Sätzen.'} <button type="button" class="quiet" onclick={toggleTts}>{tts?'🔊 Vorlesen an':'🔇 Vorlesen aus'}</button></p>{/if}
        <label for="mentor-answer">{oral?'Oder tippen':running.task?'Dein Versuch oder deine Frage':running.mode==='homework_check'&&!attachment&&!running.materials?.length?'Foto anhängen oder Seiten aus deinen Materialien wählen, dazu eine Frage, wenn du willst':'Was möchtest du sagen?'}{#if spoken} · erkannt, bitte prüfen{/if}</label>
        <textarea id="mentor-answer" bind:value={text} rows="3" maxlength="4000" disabled={busy||!canWrite} placeholder={speech?'… oder tippen':'Deine Antwort oder Frage …'} onbeforeinput={e=>{if((e.inputType||'').startsWith('delete'))edits++;}}></textarea>
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
        {#if oral}<div class="actions"><button class="primary" disabled={busy||!text.trim()||!canWrite}>Senden</button><button type="button" disabled={busy||!canWrite} onclick={()=>act(()=>send('finish','Beenden und auswerten'))}>Beenden und auswerten{answers<3?' (noch kurz)':''}</button></div>
        {:else}
        <div class="actions"><button class="primary" disabled={busy||(!text.trim()&&!attachment&&!freshPages&&!picked.length)||!canWrite}>{picked.length?`Senden mit ${picked.length===1?'1 Seite':`${picked.length} Seiten`}`:'Senden'}</button><button type="button" class:primary={running.mode==='homework_check'&&!attachment&&!running.attachments?.length&&!running.materials?.length} disabled={busy||!canWrite} onclick={()=>fileInput?.click()}>{running.mode==='homework_check'?'Fotos der Lösung':homeworkChat?'Fotos zeigen':'Foto zeigen'}</button><input class="file" type="file" accept={homeworkChat?'image/*,application/pdf':'image/*'} multiple={homeworkChat} bind:this={fileInput} onchange={upload}/>{#if homeworkChat}<button type="button" disabled={busy||!canWrite} onclick={()=>act(openPicker)}>Aus Materialien</button>{/if}<a class="material-link" href={`#/materialien/${encodeURIComponent(running.subject||'')}${homeworkChat&&running.task_id?`/${running.task_id}`:''}`} title="Arbeitsblatt, Heftseite oder PDF dauerhaft ablegen"><ActionLabel label="Material hinzufügen" /></a></div>
        <div class="actions"><button type="button" disabled={busy||!canWrite} onclick={()=>act(()=>send('hint','Bitte anders erklären.'))}>Anders erklären</button><button type="button" disabled={busy||!canWrite} onclick={()=>act(()=>send('finish','Für heute fertig.'))}>Für heute fertig</button></div>
        {/if}
      </form>
    {:else}<section class="card"><h2>{running.status==='active'?'Gespeicherter Verlauf':oral?'Sprechprobe ausgewertet':running.topic?'Einheit beendet':running.mode==='homework_check'?'Kontrolle beendet':running.untimed?'Unterbrochen':'Für heute geschafft'}</h2><p>{running.summary||'Dein Gespräch und deine Antworten bleiben gespeichert.'}</p>{#if oral}<a href="#/klausuren">Zur Arbeit und den anderen Proben</a>{:else if running.topic}<p><strong>Stufe: {running.topic.stage}</strong>{#if running.topic.reason&&running.topic.stage!=='neu'} · {running.topic.reason}{/if}{#if running.topic.next_check} · Kurzprüfung ab {formatShortDate(running.topic.next_check)}{/if}</p><a href="#/klausuren">Zur Arbeit und den anderen Themen</a>{/if}
      {#if running.status!=='active'&&canWrite&&!oral}<button class="primary" disabled={busy} onclick={()=>act(resume)}><ActionLabel kind="chat" label="Hier weitermachen" /></button>{/if}
      <button onclick={()=>act(leave)}>Zur Übersicht</button></section>{/if}
    <!-- Bei einer Abfrage führt die App den Bestand. Was offen ist, steht hier
         und nicht nur im Merkzettel des Modells: Das Kind musste vorher danach
         fragen, und die Antwort war unvollständig (D91). -->
    {#if running.quiz_open?.length}<p class="muted">Noch zu wiederholen: {running.quiz_open.join(', ')}.</p>
    {:else if running.quiz?.length}<p class="muted">Alles wiederholt: {running.quiz.length} {running.quiz.length===1?'Wort':'Wörter'} sitzen.</p>{/if}
    {#if busy}<p role="status" class="working">{oral?'Einen Moment …':running.messages.length<=1?'Dein Coach schaut sich Thema und Material an …':'Einen Moment – deine Antwort wird vorbereitet …'}</p>{/if}
</div>
{/if}
<style>
  .oral-result{margin-top:.5rem;padding:.6rem;border:1px solid var(--border);border-radius:var(--r-sm);background:var(--bg-card)}
  .oral-result ul{list-style:none;margin:.3rem 0;padding:0;display:grid;gap:.35rem}
  .oral-result .scores li{display:grid;grid-template-columns:1fr auto;gap:.1rem .5rem;align-items:center}
  .oral-result .scores small{grid-column:1/-1;color:var(--fg-muted);overflow-wrap:anywhere}
  .oral-result .dots{display:inline-flex;gap:3px}
  .oral-result .dots i{width:12px;height:12px;border-radius:50%;background:var(--border)}
  .oral-result .dots i.on{background:var(--accent)}
  .oral-result .weak small{color:var(--fg-muted);overflow-wrap:anywhere}
.hint{font-size:.85rem;opacity:.8;margin:.2rem 0 .6rem}
.mentor{max-width:720px;margin:auto;padding-bottom:1.5rem}
h1{font-size:1.55rem;line-height:1.25;overflow-wrap:anywhere}
h2{font-size:1.1rem;line-height:1.35}
.speaker{font-size:.8rem;font-weight:650;opacity:.8}
.card,.task{border:1px solid var(--border,#d4e0da);background:var(--bg-card,#fff);padding:1rem;border-radius:16px;margin:1rem 0}
.task{position:relative}
.optionen{display:grid;gap:8px;margin-top:.6rem}
.option{text-align:left;min-height:48px;border-radius:12px;padding:.6rem .9rem;background:var(--bg-elevated,#fff);border:1px solid var(--border);font-weight:550}
.option.aus{text-decoration:line-through;opacity:.55}
.preserve{white-space:pre-wrap;overflow-wrap:anywhere}
.choices,.actions{display:flex;gap:.5rem;flex-wrap:wrap;margin:.6rem 0}
button{min-height:44px;min-width:44px;padding:.6rem .85rem;border:1px solid var(--border,#d4e0da);border-radius:12px;background:var(--bg-card,#fff);color:inherit;font:inherit;cursor:pointer}
.primary{background:var(--accent,#247552);color:var(--accent-fg,#fff)}
button:disabled{opacity:.5;cursor:default}
.messages article{background:var(--bg-card,#fff);border:1px solid var(--border,#d4e0da);padding:.8rem 1rem;border-radius:14px;margin:.8rem 0;max-width:95%}
.messages .own{margin-left:1rem;background:var(--bg,#edf5f0)}
.messages p{margin:.4rem 0;line-height:1.55}
.composer{background:var(--bg-card,#fff);padding:1rem .2rem;border-top:1px solid var(--border,#d4e0da)}
textarea,input,select{font:inherit;font-size:16px;box-sizing:border-box;width:100%;padding:.7rem;margin:.4rem 0;border:1px solid var(--border,#ccc);border-radius:10px;background:var(--bg-card,#fff);color:inherit}
label{display:block;margin:.5rem 0}
.file{display:none}
.notice{padding:.8rem;background:var(--warm-soft);color:var(--fg);border-radius:12px}
.session-head{display:flex;align-items:center;gap:.6rem;font-size:.85rem}
small{display:block;font-size:.8rem;opacity:.8;margin-top:.3rem}
summary{min-height:44px;cursor:pointer;display:flex;align-items:center}
.muted{font-size:.85rem;opacity:.8}
.working{padding:1rem;color:var(--accent,#247552)}
.basis{border:1px solid var(--border,#d4e0da);border-radius:16px;padding:.4rem .8rem;margin:.8rem 0}
.basis details{margin:.3rem 0;border-top:1px solid var(--border,#d4e0da)}
.basis .page{font-size:.9rem;line-height:1.5;max-height:60vh;overflow:auto}
.vorlage{margin:.5rem 0;padding:.6rem .8rem;border-left:3px solid var(--accent,#247552);background:var(--bg,#edf5f0);border-radius:0 10px 10px 0;font-size:1.02rem;line-height:1.6}
.vorlage cite{display:block;margin-top:.4rem;font-size:.8rem;font-style:normal;opacity:.75}
.found{display:block;margin:.5rem 0}
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
.pick-subject select{display:block;width:100%;margin-top:.3rem;min-height:44px;font:inherit;font-size:16px;padding:.5rem;border-radius:10px;border:1px solid var(--border,#ccc);background:var(--bg-card,#fff);color:inherit}
.found img{display:block;width:100%;max-width:22rem;max-height:14rem;object-fit:cover;object-position:top;border:1px solid var(--border,#d4e0da);border-radius:12px}
.found small{display:block;margin-top:.25rem}
</style>
