<script>
 import {formatShortDate} from '../lib/format.js';
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import LearningActivityEditor from '../lib/LearningActivityEditor.svelte';
  let { accountId } = $props();
  const base = $derived(`/api/accounts/${accountId}/learning`);
  let data = $state(null), error = $state(''), message = $state(''), busy = $state(false);
  let tab = $state('today'), detail = $state(null), lessons = $state(null);
  let discovery = $state(null), discoveryError = $state('');
  let year = $state(''), subject = $state('');
  let topicForm = $state(null), editingTopic = $state(null);
  let profileForm = $state(null), materialForm = $state(null), editingMaterial = $state(null);
  let attachment = $state(null), selectedMaterials = $state([]);
  let activityForm = $state(undefined), editingActivity = $state(null);
  let running = $state(null), answer = $state(''), minutes = $state(5), difficulty = $state('okay');
  const statusNames = {planned:'Als Nächstes',active:'Aktuell',paused:'Pausiert',archived:'Archiviert'};
  const kindNames = {preview:'Vorbereitung',practice:'Üben',transfer:'Übertragen',oral:'Mündlich'};
  const outcomes = {again:'Noch offen',partly:'Teilweise / mit Hilfe',independent:'Selbstständig eingeschätzt'};
  const weekdays = ['Mo','Di','Mi','Do','Fr','Sa','So'];
  const regions = ['Baden-Württemberg','Bayern','Berlin','Brandenburg','Bremen','Hamburg','Hessen','Mecklenburg-Vorpommern','Niedersachsen','Nordrhein-Westfalen','Rheinland-Pfalz','Saarland','Sachsen','Sachsen-Anhalt','Schleswig-Holstein','Thüringen'];
  const schoolTypes = ['Grundschule','Gymnasium','Gesamtschule','Oberschule','Realschule','Hauptschule','Förderschule','Berufliche Schule'];
  const schoolYears = $derived.by(() => {
    const now = new Date();
    const start = now.getFullYear() - (now.getMonth() < 7 ? 1 : 0);
    return [...new Set([...Array.from({length:17}, (_, i) => `${start-13+i}/${start-12+i}`),
      ...(data?.profiles || []).map(p => p.school_year), profileForm?.school_year].filter(Boolean))].sort();
  });
  const current = $derived(data?.profiles.find(p => p.active));
  const filteredTopics = $derived(data?.topics.filter(t => (!year || t.school_year === year) && (!subject || t.subject === subject)) || []);
  const subjects = $derived([...new Set(data?.topics.map(t => t.subject) || [])].sort());
  const progress = $derived.by(() => {
    const attempts = data?.recent_attempts || [];
    return [1,2,3].map(afb => ({afb, total: attempts.filter(a => a.afb === afb).length,
      own: attempts.filter(a => a.afb === afb && a.outcome === 'independent' && !a.help_used).length}));
  });
  async function load() {
    data = await api.get(base);
    if(data.can_manage) {
      try { discovery=await api.get(`${base}/discovery`); discoveryError=''; }
      catch(e) { discoveryError=e.message; }
    }
  }
  async function scanTopics() {
    message='Unterricht wird zu Themen verbunden. Das kann etwa eine Minute dauern.';
    const result=await api.post(`${base}/discovery/scan`);
    await load();
    message=result.processed ? `${result.processed} Unterrichtseinträge ausgewertet. Erklärungen und Kurzchecks sind vorbereitet.` : 'Die Themenübersicht ist aktuell.';
  }
  async function setDiscovery(enabled) {
    await api.put(`${base}/discovery/settings`,{enabled});
    await load();
    if(enabled && current?.ai_enabled && discovery?.pending) await scanTopics();
  }
  async function act(fn) {
    if (busy) return;
    busy = true; error = ''; message = '';
    try { await fn(); } catch(e) { error = typeof e.message === 'string' ? e.message : 'Eingaben bitte prüfen.'; }
    finally { busy = false; }
  }
  onMount(() => { act(async()=>{
    await load();
    // Background work is scheduled server-side, never by page views.
  }); });
  function openProfile(p = null) {
    const y = new Date().getFullYear() - (new Date().getMonth() < 7 ? 1 : 0);
    profileForm = p ? {school_year:p.school_year,grade:p.grade,region:p.region,school_type:p.school_type,
      personal_goal:p.personal_goal,daily_minutes:p.daily_minutes,max_sessions:p.max_sessions,
      study_days:[...p.study_days],ai_enabled:p.ai_enabled,active:p.active} : {
      school_year:`${current ? Number(current.school_year.slice(0,4))+1 : y}/${current ? Number(current.school_year.slice(0,4))+2 : y+1}`,
      grade:current ? Math.min(13,current.grade+1) : (data?.suggested_grade || 6),region:current?.region || '',school_type:current?.school_type || '',
      personal_goal:'',daily_minutes:15,max_sessions:2,study_days:[0,1,2,3,4],ai_enabled:false,active:true};
    tab = 'manage';
  }
  async function saveProfile() {
    await api.put(`${base}/profiles`,profileForm); profileForm=null; await load(); message='Schuljahr und Lernrahmen gespeichert.';
  }
  function openTopic(value = null, lesson = null) {
    editingTopic = value?.id || null;
    topicForm = value ? {profile_id:value.profile_id,subject:value.subject,title:value.title,objective:value.objective,
      method:value.method,status:value.status,priority:value.priority,source_note:value.source_note,target_date:value.target_date || ''} : {
      profile_id:current?.id,subject:lesson?.subject_name || '',title:lesson?.lstext?.slice(0,240) || '',objective:'',
      method:'explain',status:lesson?.future ? 'planned' : 'active',priority:1,
      source_note:lesson ? `Untis · ${lesson.date}\n${lesson.lstext || 'Kein Stoffeintrag – Thema bitte klären.'}` : '',target_date:''};
    tab='topics';
  }
  async function saveTopic() {
    const body={...topicForm,target_date:topicForm.target_date || null};
    const result = editingTopic ? await api.put(`${base}/topics/${editingTopic}`,body) : await api.post(`${base}/topics`,body);
    topicForm=null; await load(); await openDetail(result.id); message='Thema gespeichert.';
  }
  async function openDetail(id) {
    detail=await api.get(`${base}/topics/${id}`); selectedMaterials=[]; materialForm=null; activityForm=undefined; tab='topics';
  }
  function openMaterial(m = null) {
    editingMaterial=m?.id || null; attachment=null;
    materialForm=m ? {title:m.title,source_kind:m.source_kind,source_ref:m.source_ref,content_text:m.content_text,verified:!!m.verified}
      : {title:'',source_kind:'worksheet',source_ref:'',content_text:'',verified:false};
  }
  async function saveMaterial() {
    const value={...materialForm};
    const r=editingMaterial ? await api.put(`${base}/materials/${editingMaterial}`,value)
      : await api.post(`${base}/topics/${detail.topic.id}/materials`,value);
    if(attachment) {
      const form=new FormData(); form.append('file',attachment);
      // Keep the metadata record available for a retry if upload fails.
      editingMaterial=r.id;
      await api.put(`${base}/materials/${r.id}/file`,form);
      message='Datei gespeichert. Bitte Inhalt prüfen und anschließend freigeben.';
    } else message='Material gespeichert.';
    await openDetail(detail.topic.id); await load();
  }
  async function saveActivity(value) {
    if(editingActivity) await api.put(`${base}/activities/${editingActivity}`,value);
    else await api.post(`${base}/topics/${detail.topic.id}/activities`,value);
    activityForm=undefined; await openDetail(detail.topic.id); await load(); message='Übung gespeichert.';
  }
  function editActivity(a) { editingActivity=a?.id || null; activityForm=a || null; }
  async function generate() {
    await api.post(`${base}/topics/${detail.topic.id}/generate`,{material_ids:selectedMaterials});
    await openDetail(detail.topic.id); await load(); message='Entwürfe erstellt. Bitte Aufgaben, Quellen und Lösungen prüfen und freigeben.';
  }
  async function start(id) {
    running=await api.post(`${base}/activities/${id}/start`); answer=running.session.answer || '';
    minutes=running.activity.minutes; difficulty='okay';
  }
  async function submit() { running=await api.post(`${base}/sessions/${running.session.id}/answer`,{answer}); }
  async function help() { running=await api.post(`${base}/sessions/${running.session.id}/help`); }
  async function finish(outcome) {
    await api.post(`${base}/sessions/${running.session.id}/finish`,{outcome,difficulty,minutes});
    running=null; await load(); if(detail) await openDetail(detail.topic.id);
    message='Lerneinheit abgeschlossen. Die spätere Wiederholung ist vorgemerkt.';
  }
  async function openInbox() { tab='inbox'; if(!lessons) lessons=await api.get(`${base}/inbox`); }
  function fileUrl(id) { return `.${base}/materials/${id}/file`; }
</script>

<div class="learning">
  <div class="heading"><div><h1>Lernraum</h1><p>{current ? `${current.school_year} · Jahrgang ${current.grade}` : 'Lernen über Fächer und Schuljahre hinweg'}</p></div>{#if current}<span class="budget">bis {current.daily_minutes} Min.<br/><small>im vorhandenen Zeitbudget</small></span>{/if}</div>
  {#if error}<div class="notice error" role="alert">{error}<button onclick={() => act(load)} disabled={busy}>Erneut laden</button></div>{/if}
  {#if message}<p class="notice" role="status">{message}</p>{/if}
  {#if busy}<p role="status" class="muted">{selectedMaterials.length ? 'Bitte warten – ein KI-Entwurf kann etwa eine Minute dauern.' : 'Wird geladen oder gespeichert …'}</p>{/if}
  {#if data}
    {#if running}
      <section class="session">
        <div class="eyebrow">{kindNames[running.activity.kind]} · AFB {running.activity.afb}</div>
        <h2>{running.activity.operator}</h2><p class="preserve prompt">{running.activity.prompt}</p>
        <p class="muted">Was verlangt die Aufgabe? Überlege zuerst selbst. Du kannst jederzeit Hilfe öffnen.</p>
        {#if !running.session.answer}
          <label>Deine Antwort<textarea bind:value={answer} maxlength="10000" placeholder="Schreibe deine Antwort oder notiere das Ergebnis deiner mündlichen/praktischen Übung."></textarea></label>
          <div class="actions"><button class="primary" disabled={busy || !answer.trim()} onclick={() => act(submit)}>Antwort abgeben und vergleichen</button><button disabled={busy} onclick={() => act(help)}>Hinweis und Erklärung</button></div>
        {:else}
          <div class="answer"><h3>Deine erste Antwort</h3><p class="preserve">{running.session.answer}</p></div>
          <div class="answer"><h3>Mögliche Lösung</h3><p class="preserve">{running.activity.solution}</p><h3>Prüfe deine Antwort</h3><p class="preserve">{running.activity.criteria}</p></div>
          <p>Wie gut passte deine Antwort zu den Kriterien? Das ist deine Selbsteinschätzung, keine Note.</p>
          <div class="columns"><label>Benötigte Minuten<input type="number" min="1" max="120" bind:value={minutes} /></label><label>Wie anstrengend war es?<select bind:value={difficulty}><option value="easy">Leicht</option><option value="okay">Passend</option><option value="hard">Anstrengend</option></select></label></div>
          <div class="actions"><button disabled={busy || !minutes || minutes>120} onclick={() => act(() => finish('again'))}>Noch einmal üben</button><button disabled={busy || !minutes || minutes>120} onclick={() => act(() => finish('partly'))}>Teilweise gelungen</button><button class="primary" disabled={busy || !!running.session.help_used || !minutes || minutes>120} onclick={() => act(() => finish('independent'))}>Selbstständig gelungen</button></div>
        {/if}
        {#if running.session.help_used}<aside><h3>Hilfe</h3><p class="preserve">{running.activity.hint || 'Arbeitsauftrag in eigene Worte fassen und mit einem kleinen Schritt beginnen.'}</p><p class="preserve">{running.activity.explanation}</p><p class="muted">Diese Einheit wird als Übung mit Hilfe berücksichtigt.</p></aside>{/if}
        <button class="quiet" disabled={busy} onclick={() => {running=null;}}>Unterbrechen · später fortsetzen</button>
      </section>
    {:else}
      <nav class="tabs" aria-label="Bereiche im Lernraum">
        <button class:chosen={tab==='today'} onclick={() => tab='today'}>Heute</button>
        <button class:chosen={tab==='topics'} onclick={() => tab='topics'}>Themen</button>
        <button class:chosen={tab==='inbox'} onclick={() => act(openInbox)}>Unterricht</button>
        <button class:chosen={tab==='progress'} onclick={() => tab='progress'}>Entwicklung</button>
        {#if data.can_manage}<button class:chosen={tab==='manage'} onclick={() => tab='manage'}>Steuern</button>{/if}
      </nav>
      {#if !current && tab!=='manage'}
        <section class="card"><h2>Ein Lernrahmen für dieses Schuljahr</h2><p>Jahrgang, eigenes Ziel und ein passender Zeitrahmen bilden den Anfang. Frühere Schuljahre bleiben erhalten.</p>{#if data.can_manage}<button class="primary" onclick={() => openProfile()}>Schuljahr einrichten</button>{:else}<p>Deine Eltern richten den Lernrahmen mit dir ein.</p>{/if}</section>
      {/if}
      {#if tab==='today'}
        {#if data.can_manage && current}
          <section class="card">
            <h2>Wo lohnt sich ein kleiner Lernschritt?</h2>
            <p>Der Unterrichtsverlauf bildet Themenfelder. Verständnisrückmeldungen und abgeschlossene Übungen helfen bei der Auswahl.</p>
            {#if discoveryError}<p class="notice">{discoveryError}</p>{/if}
            {#if discovery}
              {#if !discovery.enabled}
                <p>Die automatische Auswertung sendet Fach, Jahrgang, Datum und Unterrichtstexte an eure KI. Rückmeldungen und Übungsantworten werden lokal ausgewertet. Neue oder geänderte Einträge werden beim Öffnen dieses Lernraums in kleinen Gruppen ergänzt.</p>
                <button class="primary" disabled={busy || !data.can_write || !current.ai_enabled || !data.ai.configured} onclick={()=>act(()=>setDiscovery(true))}>Unterricht automatisch auswerten</button>
                {#if !current.ai_enabled}<p class="muted">Unter „Steuern“ zuerst KI für dieses Schuljahr erlauben.</p>{/if}
              {:else}
                <p class="muted">Archiv ab {discovery.since}: {discovery.processed} von {discovery.lessons} Einträgen ausgewertet · {discovery.pending} noch offen · {discovery.blank} ohne Stoffangabe.</p>
                {#if discovery.truncated}<p class="notice">Die Übersicht ist auf die neuesten 6.000 Einträge begrenzt.</p>{/if}
                {#if discovery.pending}<button disabled={busy || !data.can_write || !current.ai_enabled} onclick={()=>act(scanTopics)}>Weitere Unterrichtseinträge auswerten</button>{/if}
                <details><summary>Auswertung und Verbrauch</summary><p>Höchstens eine Gruppe je Öffnen; unveränderte Einträge werden wiederverwendet. Geändertes Feedback braucht keinen neuen KI-Aufruf. Insgesamt höchstens zwölf KI-Anfragen pro Kind und Tag, gemeinsam mit anderen Entwürfen.</p><p>{discovery.usage.calls} erfolgreiche Auswertungen · {discovery.usage.input_tokens} Eingabetokens · {discovery.usage.output_tokens} Ausgabetokens. Fehlgeschlagene Anfragen zählen zur Tagesgrenze; ihr Tokenverbrauch ist hier nicht enthalten.</p><button disabled={busy || !data.can_write} onclick={()=>act(()=>setDiscovery(false))}>Automatische Auswertung pausieren</button></details>
              {/if}
            {/if}
          </section>
          {#each discovery?.topics || [] as t}
            <section class="card">
              <div class="eyebrow">{t.subject} · {t.first_date} bis {t.last_date}</div>
              <h3>{t.title}</h3><p><strong>{t.reason}</strong></p>
              {#if t.uncertain_reports}<p class="muted">{t.uncertain_reports} Rückmeldungen „unsicher“ oder „teilweise verstanden“. Das ist ein Anlass zum Prüfen, keine festgestellte Wissenslücke.</p>{/if}
              {#if t.catch_up_open}<p class="muted">Bei mindestens einer versäumten Stunde ist das Nachholen noch offen.</p>{/if}
              <details><summary>Einfach erklärt · gemeinsam ansehen</summary><p class="preserve">{t.explanation}</p><p class="preserve">{t.bridge}</p><p class="muted">KI-Vorschlag aus Allgemeinwissen: bitte fachlich prüfen. Wer die Erklärung gerade gelesen hat, übt anschließend mit Hilfe.</p></details>
              <details><summary>Das hängt damit zusammen</summary><h4>Hilfreiche Grundlagen</h4><p class="preserve">{t.prerequisites}</p><h4>Möglicher nächster Gedanke</h4><p class="preserve">{t.outlook}</p><p class="muted">Fachliche Verbindungen, keine bestätigte Unterrichts- oder Klausurplanung.</p></details>
              <details><summary>Woran macht die App das fest?</summary>{#each t.evidence as e}<p>{formatShortDate(e.date)}: {e.text} <small>{e.rating ? ['','· unsicher','· teilweise verstanden','· verstanden'][e.rating] : '· keine Rückmeldung'}</small></p>{/each}</details>
              <button class="primary" disabled={busy} onclick={()=>act(()=>openDetail(t.id))}>Kurzcheck prüfen und freigeben</button>
            </section>
          {/each}
          {#each discovery?.questions || [] as q}<section class="card"><div class="eyebrow">{q.subject} · {formatShortDate(q.date)}</div><h3>Hier fehlt noch eine konkrete Angabe</h3><p>{q.question}</p></section>{/each}
        {/if}
        {#if current?.personal_goal}<div class="goal"><span>Mein Ziel</span><p>{current.personal_goal}</p></div>{/if}
        {#each data.warnings as warning}<p class="notice">{warning}</p>{/each}
        {#if data.today.tasks.length}<section class="card"><h2>Hausaufgaben zuerst einplanen</h2><p class="muted">Für offene Aufgaben sind ungefähr {data.today.reserved_homework_minutes} Minuten reserviert. Ohne Schätzung rechnen wir mit 20 Minuten je Aufgabe.</p>{#each data.today.tasks as t}<p>{t.title} <small>· {t.due_date}</small></p>{/each}<a href="#/plan">Zum gemeinsamen Tagesplan →</a></section>{/if}
        <div class="section-title"><h2>Dein nächster Schritt</h2><span>{data.today.completed_sessions} heute abgeschlossen</span></div>
        {#each data.today.activities as a}
          <section class="card activity"><div class="eyebrow">{a.subject} · {kindNames[a.kind]} · {a.minutes} Min.</div><h3>{a.title}</h3><p>{a.prompt}</p><p class="muted">{a.reason}</p><button class="primary" disabled={busy || !data.can_write} onclick={() => act(() => start(a.id))}>Lerneinheit öffnen</button></section>
        {:else}
          <section class="card"><h3>Heute ist nichts zusätzlich eingeplant.</h3><p>Das kann am Zeitrahmen, an einem freien Tag oder an noch fehlenden Übungen liegen. Bereits erledigte Lernzeit wird berücksichtigt.</p><button onclick={() => tab='topics'}>Themen ansehen</button></section>
        {/each}
        {#if data.exams.length}<section class="card"><h2>Anstehende Arbeiten</h2>{#each data.exams as e}<p>{formatShortDate(e.date)} · {e.subject_name || e.title || 'Arbeit'}</p>{/each}<a href="#/klausuren">Termine und Zuordnung prüfen →</a></section>{/if}
      {:else if tab==='topics'}
        {#if topicForm}
          <form class="card" onsubmit={(e)=>{e.preventDefault();act(saveTopic);}}>
            <h2>{editingTopic ? 'Thema bearbeiten' : 'Thema und Lernziel'}</h2>
            <label>Schuljahr<select bind:value={topicForm.profile_id} disabled={!!editingTopic} required>{#each data.profiles as p}<option value={p.id}>{p.school_year} · Jahrgang {p.grade}</option>{/each}</select></label>
            <label>Fach<input bind:value={topicForm.subject} list="learning-subjects" required maxlength="120" /></label><datalist id="learning-subjects">{#each subjects as s}<option value={s}></option>{/each}</datalist>
            <label>Thema<input bind:value={topicForm.title} required maxlength="240" /></label>
            <label>Was soll das Kind anschließend können?<textarea bind:value={topicForm.objective} required maxlength="1200" placeholder="Ich kann …"></textarea></label>
            <label>Passende Lerntätigkeit<select bind:value={topicForm.method}>{#each Object.entries(data.methods) as [key,label]}<option value={key}>{label}</option>{/each}</select></label>
            <p class="muted">{data.method_guides[topicForm.method]}</p>
            <div class="columns"><label>Status<select bind:value={topicForm.status}>{#each Object.entries(statusNames) as [key,label]}<option value={key}>{label}</option>{/each}</select></label><label>Schwerpunkt<select bind:value={topicForm.priority}><option value={0}>Optional</option><option value={1}>Normal</option><option value={2}>Wichtig</option><option value={3}>Besonders wichtig</option></select></label></div>
            <label>Zieldatum (optional)<input type="date" bind:value={topicForm.target_date} /></label>
            <label>Herkunft / Vorgaben der Lehrkraft<textarea bind:value={topicForm.source_note} maxlength="2000"></textarea></label>
            <div class="actions"><button class="primary" disabled={busy}>Speichern</button><button type="button" onclick={()=>topicForm=null}>Abbrechen</button></div>
          </form>
        {:else if detail}
          <button class="quiet" onclick={()=>{detail=null;activityForm=undefined;}}>← Alle Themen</button>
          <section class="card"><div class="eyebrow">{detail.topic.subject} · {statusNames[detail.topic.status]}</div><h2>{detail.topic.title}</h2><p>{detail.topic.objective}</p><p class="muted">{detail.method_guide}</p>{#if detail.topic.source_note}<details><summary>Herkunft und Unterrichtsvorgaben</summary><p class="preserve">{detail.topic.source_note}</p></details>{/if}{#if data.can_manage}<button onclick={()=>openTopic(detail.topic)}>Thema steuern</button>{#if current && current.id!==detail.topic.profile_id}<button disabled={busy} onclick={()=>act(async()=>{const r=await api.post(`${base}/topics/${detail.topic.id}/carry-forward`);await load();await openDetail(r.id);message='Thema ins aktuelle Schuljahr übernommen. Materialien und Übungen bitte erneut prüfen.';})}>Im aktuellen Schuljahr fortführen</button>{/if}{/if}</section>
          <div class="section-title"><h2>Materialien</h2><button disabled={!data.can_write} onclick={()=>openMaterial()}>Hinzufügen</button></div>
          {#if materialForm}
            <form class="card" onsubmit={(e)=>{e.preventDefault();act(saveMaterial);}}><h3>Material hinterlegen</h3>
              <label>Titel<input bind:value={materialForm.title} required maxlength="240" /></label>
              <label>Quelle<select bind:value={materialForm.source_kind}><option value="teacher">Lehrkraft / Aufgabenstellung</option><option value="book">Schulbuch</option><option value="worksheet">Arbeitsblatt</option><option value="curriculum">Lehrplan</option><option value="web">Webseite</option><option value="own">Eigene Notiz</option></select></label>
              <label>Buch, Ausgabe und Seite oder Link<input bind:value={materialForm.source_ref} maxlength="1000" /></label>
              <label>Relevanter Inhalt<textarea bind:value={materialForm.content_text} maxlength="30000" placeholder="Aufgabe, Vokabelliste, Lernziel oder Ausschnitt. Links werden nicht automatisch ausgelesen."></textarea></label>
              <label>Screenshot, Foto oder PDF (bis 8 MB)<input type="file" accept="image/png,image/jpeg,image/webp,application/pdf" onchange={(e)=>attachment=e.currentTarget.files?.[0] || null} /></label>
              <p class="muted">Eine neue Datei ersetzt den vorhandenen Anhang und setzt Text und Prüfung zurück. Für PDFs den relevanten Text anschließend ergänzen. Bilder kann ein bildfähiges KI-Modell direkt lesen.</p>
              {#if data.can_manage}<label class="check"><input type="checkbox" bind:checked={materialForm.verified} />Inhalt und Zuordnung geprüft</label>{/if}
              <div class="actions"><button class="primary" disabled={busy}>Speichern</button><button type="button" onclick={()=>materialForm=null}>Abbrechen</button></div>
            </form>
          {/if}
          {#each detail.materials as m}
            <section class="card material">
              <div class="section-title"><h3>{m.title}</h3><span class="tag">{m.verified ? 'Geprüft' : 'Bitte prüfen'}</span></div><p class="muted">{m.source_ref || 'Keine nähere Quellenangabe'}</p>
              {#if m.content_text}<details><summary>Inhalt ansehen</summary><p class="preserve">{m.content_text}</p></details>{/if}
              <div class="actions">{#if m.filename}<a href={fileUrl(m.id)} target="_blank" rel="noreferrer">{m.filename}</a>{/if}{#if data.can_manage}<button onclick={()=>openMaterial(m)}>Bearbeiten / prüfen</button>{/if}</div>
              {#if data.can_manage && m.verified}<label class="check"><input type="checkbox" bind:group={selectedMaterials} value={m.id} />Für KI-Entwurf auswählen</label>{/if}
              {#if data.can_manage}<details><summary>Material verwalten</summary>{#if m.filename}<button disabled={busy} onclick={()=>act(async()=>{await api.delete(`${base}/materials/${m.id}/file`);await openDetail(detail.topic.id);})}>Dateianhang entfernen</button>{/if}<button disabled={busy} onclick={()=>act(async()=>{await api.delete(`${base}/materials/${m.id}`);await openDetail(detail.topic.id);await load();})}>Unbenutztes Material löschen</button></details>{/if}
            </section>
          {:else}<p class="empty">Noch kein Material. Eine kurze Themenbeschreibung oder typische Aufgabe genügt für den Anfang.</p>{/each}
          <div class="section-title"><h2>Übungen</h2>{#if data.can_manage}<button onclick={()=>editActivity(null)}>Eigene Übung</button>{/if}</div>
          {#if data.can_manage}
            <div class="card"><button class="primary" disabled={busy || !selectedMaterials.length || !data.ai.configured || !data.profiles.find(p=>p.id===detail.topic.profile_id)?.ai_enabled} onclick={()=>act(generate)}>KI-Entwurf aus ausgewählten Quellen</button>
              <p class="muted">{data.ai.configured ? `An ${data.ai.host} gehen Jahrgang, Thema, Lernziel und nur die ausgewählten Inhalte. Namen, Fehlzeiten und Antworten werden nicht übertragen.` : 'KI ist noch nicht verbunden. Den Endpunkt, API-Schlüssel und Modellnamen in der Add-on-Konfiguration eintragen.'} Die Freigabe pro Schuljahr erfolgt unter „Steuern“.</p></div>
          {/if}
          {#if activityForm !== undefined}{#key editingActivity}<LearningActivityEditor value={activityForm} materials={detail.materials} {busy} onsave={(value)=>act(()=>saveActivity(value))} oncancel={()=>activityForm=undefined} />{/key}{/if}
          {#each detail.activities as a}
            <section class="card"><div class="eyebrow">{kindNames[a.kind]} · AFB {a.afb} · {a.minutes} Min.{#if data.can_manage} · {a.published ? 'Freigegeben' : 'Entwurf'}{/if}</div><p class="preserve">{a.prompt}</p>{#if a.next_due}<p class="muted">Nächste Wiederholung: {a.next_due}</p>{/if}
              <div class="actions">{#if !data.can_manage || a.published}<button class="primary" disabled={busy || !data.can_write} onclick={()=>act(()=>start(a.id))}>Öffnen / fortsetzen</button>{/if}{#if data.can_manage}<button onclick={()=>editActivity(a)}>Prüfen / bearbeiten</button>{/if}</div>
            </section>
          {:else}<p class="empty">Noch keine freigegebenen Übungen.</p>{/each}
        {:else}
          <div class="columns"><label>Schuljahr<select bind:value={year}><option value="">Alle Schuljahre</option>{#each data.profiles as p}<option value={p.school_year}>{p.school_year}</option>{/each}</select></label><label>Fach<select bind:value={subject}><option value="">Alle Fächer</option>{#each subjects as s}<option value={s}>{s}</option>{/each}</select></label></div>
          {#if data.can_manage}<button class="primary" disabled={!current} onclick={()=>openTopic()}>Thema anlegen</button>{/if}
          {#each filteredTopics as t}<button class="topic-card" disabled={busy} onclick={()=>act(()=>openDetail(t.id))}><span class="eyebrow">{t.subject} · {t.school_year} · {statusNames[t.status]}</span><strong>{t.title}</strong><span>{t.objective}</span><small>{t.materials_count} Materialien · {t.activities_count} freigegebene Übungen</small></button>{:else}<p class="empty">Noch keine passenden Themen. Unterrichtseinträge können als Ausgangspunkt übernommen werden.</p>{/each}
        {/if}
      {:else if tab==='inbox'}
        <h2>Aus dem Unterricht</h2><p class="muted">Ein Eintrag beschreibt Unterricht, noch keinen festgestellten Lernbedarf. Leere Einträge bleiben unbekannt. Vergangene 21 und kommende 7 Tage.</p>
        {#if lessons && !lessons.available}<p class="notice">Unterrichtsarchiv derzeit nicht erreichbar.</p>{/if}
        {#each lessons?.lessons || [] as l}<section class="card"><div class="eyebrow">{formatShortDate(l.date)} · {l.subject_name} {l.future ? '· Kommende Stunde' : ''}</div><p class="preserve">{l.lstext || 'Kein Stoff eingetragen.'}</p><p class="muted">{l.rating ? ['','Als unsicher eingeschätzt','Als teilweise verstanden eingeschätzt','Als verstanden eingeschätzt'][l.rating] : 'Keine Verständnisrückmeldung'}{l.was_absent ? (l.caught_up ? ' · Versäumt, bereits nachgeholt' : ' · Versäumt, Nachholstatus offen') : ''}</p>{#if data.can_manage}<button disabled={!current} onclick={()=>openTopic(null,l)}>Als Thema vorbereiten</button>{/if}</section>{:else}{#if lessons?.available}<p class="empty">Keine Einträge in diesem Zeitraum.</p>{/if}{/each}
      {:else if tab==='progress'}
        <h2>Entwicklung über die Schuljahre</h2><p>Die letzten bis zu 200 abgeschlossenen Einheiten. Rückmeldungen sind Selbsteinschätzungen und ersetzen keine Leistungsüberprüfung.</p>
        <div class="stats">{#each progress as p}<section class="card"><span>AFB {p.afb}</span><strong>{p.total}</strong><small>Einheiten · davon {p.own} selbstständig eingeschätzt</small></section>{/each}</div>
        {#each data.recent_attempts as a}<section class="card"><div class="eyebrow">{formatShortDate(a.completed_at.slice(0,10))} · {a.school_year} · {a.subject}</div><h3>{a.title}</h3><p>{outcomes[a.outcome]} · {a.minutes} Min. · {a.difficulty==='hard' ? 'Anstrengend' : a.difficulty==='easy' ? 'Leicht' : 'Passend'}</p></section>{:else}<p class="empty">Nach der ersten abgeschlossenen Übung erscheint hier euer Verlauf.</p>{/each}
      {:else if tab==='manage' && data.can_manage}
        <h2>Gemeinsam den Rahmen festlegen</h2><p>Ein aktives Schuljahr steuert die täglichen Vorschläge. Alte Themen und Lernverläufe bleiben erhalten; Fächer und Materialien werden nach Bedarf ergänzt.</p>
        {#if profileForm}
          <form class="card" onsubmit={(e)=>{e.preventDefault();act(saveProfile);}}>
            <div class="columns">
              <label>Schuljahr<select bind:value={profileForm.school_year} required>{#each schoolYears as value}<option value={value}>{value}</option>{/each}</select></label>
              <label>Jahrgang<select bind:value={profileForm.grade} required>{#each Array.from({length:13}, (_, i) => i+1) as value}<option value={value}>{value}</option>{/each}</select></label>
            </div>
            <div class="columns">
              <label>Bundesland<select bind:value={profileForm.region}><option value="">Bitte auswählen</option>{#if profileForm.region && !regions.includes(profileForm.region)}<option value={profileForm.region}>{profileForm.region}</option>{/if}{#each regions as value}<option value={value}>{value}</option>{/each}</select></label>
              <label>Schulform<select bind:value={profileForm.school_type}><option value="">Bitte auswählen</option>{#if profileForm.school_type && !schoolTypes.includes(profileForm.school_type)}<option value={profileForm.school_type}>{profileForm.school_type}</option>{/if}{#each schoolTypes as value}<option value={value}>{value}</option>{/each}</select></label>
            </div>
            <p class="muted">Bundesland und Schulform werden bisher zur Einordnung gespeichert. Lehrpläne werden noch nicht automatisch zugeordnet.</p>
            <label>Eigenes Ziel des Kindes<textarea bind:value={profileForm.personal_goal} maxlength="500" placeholder="Was möchte ich im Unterricht leichter schaffen?"></textarea></label>
            <div class="columns"><label>Maximal für den Lernraum pro Tag (Minuten)<input type="number" bind:value={profileForm.daily_minutes} min="0" max="120" required /></label><label>Höchstens so viele Einheiten<input type="number" bind:value={profileForm.max_sessions} min="1" max="5" required /></label></div>
            <p class="muted">Dies ist eine Obergrenze innerhalb des bestehenden Tagesbudgets. Hausaufgaben und bereits investierte Zeit werden abgezogen. 0 Minuten pausiert tägliche Vorschläge.</p>
            <fieldset><legend>Lerntage</legend><div class="actions">{#each weekdays as day,i}<label class="check"><input type="checkbox" bind:group={profileForm.study_days} value={i} />{day}</label>{/each}</div></fieldset>
            <label class="check"><input type="checkbox" bind:checked={profileForm.active} />Dieses Schuljahr aktiv verwenden</label>
            <label class="check"><input type="checkbox" bind:checked={profileForm.ai_enabled} />KI-Entwürfe aus ausdrücklich ausgewählten Materialien erlauben</label>
            <p class="muted">KI-Ziel: {data.ai.configured ? `${data.ai.host} · ${data.ai.model}` : 'Noch nicht eingerichtet'}. Ohne Verbindung funktionieren Themen, eigene Übungen, Materialien und Lernverläufe. Bis zu zwölf Entwurfsanfragen pro Kind und Tag.</p>
            <div class="actions"><button class="primary" disabled={busy}>Lernrahmen speichern</button><button type="button" onclick={()=>profileForm=null}>Abbrechen</button></div>
          </form>
        {:else}
          {#each data.profiles as p}<section class="card"><h3>{p.school_year} · Jahrgang {p.grade} {p.active ? '· Aktiv' : ''}</h3><p>{p.personal_goal || 'Noch kein persönliches Ziel hinterlegt'}</p><button onclick={()=>openProfile(p)}>Einstellungen bearbeiten</button></section>{/each}
          <button class="primary" onclick={()=>openProfile()}>Neues Schuljahr anlegen</button>
        {/if}
        <section class="card"><h3>Lernzeit und Daten</h3><p>Das gesamte Tagesbudget wird in den bestehenden Kind-Einstellungen verwaltet. Dateien und Verlauf werden mit der App-Datenbank gesichert.</p><div class="actions"><a href="#/settings">Tagesbudget öffnen →</a><a href={`.${base}/export`} download="lernverlauf.json">Lernverlauf exportieren</a></div><p class="muted">Der JSON-Export enthält Texte und Ergebnisse. Dateianhänge sind im vollständigen Datenbank-Backup enthalten.</p></section>
      {/if}
    {/if}
  {/if}
</div>
<style>
  .learning{padding-bottom:1rem;} h1{font-size:1.65rem;margin:0;} h2{font-size:1.15rem;margin:.2rem 0 .75rem;}h3{font-size:1.05rem;margin:.25rem 0 .6rem;}
  .heading{display:flex;justify-content:space-between;gap:1rem;align-items:center;margin-bottom:1.2rem;}.heading p{margin:.25rem 0;color:var(--fg-muted);}
  .budget{text-align:right;font-size:.9rem;flex-shrink:0;}.budget small{font-size:.8rem;}
  .tabs{display:flex;gap:.3rem;overflow-x:auto;padding:.3rem 0 1rem;}.tabs button{border-color:transparent;white-space:nowrap;padding:.5rem .7rem;}.tabs .chosen{background:var(--accent);color:var(--accent-fg);}
  .card,.session{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:1rem;margin:.8rem 0;}
  .session{border-top:4px solid var(--accent);}.prompt{font-size:1.1rem;}.answer,aside{padding:.8rem;border-radius:8px;background:var(--bg);margin:1rem 0;}
  .goal{padding:.9rem 1rem;border-left:4px solid var(--accent);background:var(--bg-card);border-radius:0 8px 8px 0;}.goal span,.eyebrow{font-size:.875rem;color:var(--fg-muted);}.goal p{margin:.25rem 0;font-weight:600;}
  .section-title{display:flex;align-items:center;justify-content:space-between;gap:.75rem;margin-top:1.2rem;}.section-title h2,.section-title h3{margin:0;}.section-title span{font-size:.875rem;color:var(--fg-muted);}
  .actions{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin:.7rem 0;}.quiet{margin-top:.8rem;}.muted,small{color:var(--fg-muted);font-size:.875rem;}
  .notice{padding:.8rem;border:1px solid var(--accent);border-radius:8px;margin:.8rem 0;background:var(--bg-card);}.notice.error{border-color:var(--rating-1);}.notice button{margin-left:.5rem;}
  .columns{display:grid;grid-template-columns:1fr 1fr;gap:.8rem;}label{font-size:.9rem;margin-bottom:.8rem;}label input,label select,label textarea{margin-top:.3rem;}.check{display:flex;align-items:center;gap:.5rem;}.check input{width:20px;min-height:20px;flex-shrink:0;}
  .topic-card{display:flex;flex-direction:column;align-items:flex-start;gap:.4rem;text-align:left;width:100%;margin:.8rem 0;padding:1rem;}.topic-card strong{font-size:1.1rem;}.tag{font-size:.8rem;padding:.2rem .4rem;background:var(--bg);border-radius:5px;}
  .preserve{white-space:pre-wrap;overflow-wrap:anywhere;}p{overflow-wrap:anywhere;}details{margin:.6rem 0;}summary{cursor:pointer;font-size:.9rem;}fieldset{border:1px solid var(--border);border-radius:8px;margin-bottom:1rem;}
  .stats{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem;}.stats .card{display:flex;flex-direction:column;gap:.4rem;}.stats strong{font-size:1.7rem;}
  @media(max-width:480px){.columns{grid-template-columns:1fr;gap:0;}.heading{align-items:flex-start;}.budget{max-width:100px;white-space:normal;}.stats{grid-template-columns:1fr;}.stats .card{margin:.2rem 0;}.section-title{flex-wrap:wrap;}}
</style>
