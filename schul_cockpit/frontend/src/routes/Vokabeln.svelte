<script>
  // Vokabeltrainer: Wörter aus den Originalseiten, zwei Stufen. Stufe 1 fragt
  // die Bedeutung gesprochen, Stufe 2 die Schreibweise getippt in die
  // Fremdsprache. Kein Multiple Choice; die App wertet, nicht das Kind.
  import { onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import Speech from '../lib/Speech.svelte';
  import { answerClock } from '../lib/answerClock.js';
  import VocabProgress from '../lib/VocabProgress.svelte';
  import VocabPaper from '../lib/VocabPaper.svelte';
  const clock = answerClock();
  import { subjectStyle } from '../lib/subjectStyle.js';
  import { appState } from '../lib/store.svelte.js';
  import { actsAsParent } from '../lib/viewMode.svelte.js';
  let { accountId, subject = '', initialUnit = '' } = $props();
  const style = $derived(subjectStyle(subject));
  const base = $derived(`/api/accounts/${accountId}/learning/vocab`);
  let data = $state(null), error = $state(''), busy = $state(false);
  // Das Standardbündel ist die ganze Einheit. Ein Abschnitt, den die
  // Vokabelliste selbst nennt („Texto A"), ist nur eine Einschränkung
  // davon und wird beim Wechsel der Einheit wieder aufgehoben (D100).
  // Startwert; App.svelte erzeugt die Seite je Fach und Einheit neu ({#key}).
  // svelte-ignore state_referenced_locally
  let unit = $state(initialUnit), section = $state(''), box = $state(''), stage = $state(1), direction = $state('from');
  let cards = $state([]), index = $state(0), answer = $state(''), spoken = $state(false), edits = $state(0);
  let verdict = $state(null), pending = $state(null), done = $state(false), tally = $state({ correct: 0, wrong: 0, skipped: 0 });
  let answerInput = $state(null);
  let bookWords = $state(null), importDraft = $state(null), importFile = $state(null);
  let reviewIds = $state(''), reviewReason = $state('Bedienfehler: versehentlich übersprungen'), reviewRestore = $state(false), reviewDraft = $state(null), reviewMessage = $state('');
  async function reviewAttempts(apply = false) {
    busy = true; error = ''; reviewMessage = '';
    try {
      const payload = {attempt_ids: [...new Set(reviewIds.split(/[\s,;]+/).filter(Boolean).map(Number))], reason: reviewReason, excluded: !reviewRestore};
      const r = await api.post(`${base}/${encodeURIComponent(subject)}/attempt-review`, {...payload, ...(apply ? {digest: reviewDraft.digest} : {})});
      if (apply) { reviewDraft = null; reviewMessage = `${r.reviewed} Versuche ${r.excluded ? 'aus der Wertung genommen' : 'wieder gewertet'}. Originale bleiben erhalten.`; await load(); }
      else reviewDraft = r;
    } catch(e) { error = e.message; } finally { busy = false; }
  }
  let capturePage = $state(1), captureJob = $state(null);

  const lang = $derived(data?.language);
  const langName = $derived(lang?.name ?? subject);
  const card = $derived(cards[index] ?? null);
  const askForeign = $derived(direction === 'from');
  const currentUnit = $derived((data?.units || []).find((u) => u.unit === unit));
  const sections = $derived(currentUnit?.sections || []);
  // Kästen gehören unter ihren Abschnitt, nicht daneben (D116).
  const boxes = $derived(sections.find((s) => s.section === section)?.boxes || []);
  function chooseUnit(name) { if (unit !== name) { unit = name; section = ''; box = ''; bookWords = null; } }
  function chooseSection(name) { if (section !== name) { section = name; box = ''; bookWords = null; } }

  // Wortseiten werden beim Öffnen automatisch in Wörter zerlegt; solange das
  // läuft, lädt die Ansicht alle paar Sekunden nach.
  let pollTimer = null, polls = 0;
  // Eine Antwort, die erst nach dem Verlassen ankommt, stellt keinen neuen Zeitgeber mehr.
  let alive = true;
  onDestroy(() => { alive = false; clearTimeout(pollTimer); });
  let languages = $state(null);
  async function load() {
    error = '';
    try {
      if (!subject) { languages = (await api.get(`${base}/languages`)).languages; data = null; return; }
      data = await api.get(`${base}/${encodeURIComponent(subject)}/units`);
      if (data.units.length && !data.units.some(u => u.unit === unit)) unit = (data.units.find(u => u.label === unit) || data.units[0]).unit;
      clearTimeout(pollTimer);
      if (!alive) return;
      if (data.reading && polls < 20) { polls += 1; pollTimer = setTimeout(load, 4000); } else polls = 0;
    } catch (e) { error = e.message; }
  }
  $effect(() => { void accountId; void subject; polls = 0; load(); return () => clearTimeout(pollTimer); });

  // Tagespensum (D181): wie viele Wörter heute dran sind und warum. Neu geladen
  // beim Öffnen und nach jedem Durchgang, nicht nach jeder Antwort.
  let pensum = $state([]);
  async function loadPensum() {
    try { pensum = (await api.get(`/api/accounts/${accountId}/vocab/pensum`)).items || []; } catch { pensum = []; }
  }
  $effect(() => { void accountId; loadPensum(); });
  const pct = (e) => Math.min(100, Math.round((100 * e.practiced) / Math.max(1, e.target)));

  // Vokabeltest auf Papier (D181).
  // Aus „Erledigen“ öffnet ?paper=… das zu prüfende Blatt (D202).
  let paperId = $state(Number(new URLSearchParams(window.location.hash.split('?')[1] || '').get('paper')) || null), paperCount = $state(20), papers = $state([]);
  async function loadPapers() {
    if (!subject) return;
    try { papers = (await api.get(`/api/accounts/${accountId}/vocab/papers?subject=${encodeURIComponent(subject)}`)).papers; } catch { papers = []; }
  }
  $effect(() => { void accountId; void subject; loadPapers(); });
  async function newPaper() {
    busy = true; error = '';
    try { paperId = (await api.post(`/api/accounts/${accountId}/vocab/papers`, { subject, unit, section, count: Number(paperCount) })).id; }
    catch (e) { error = e.message; } finally { busy = false; }
  }
  function closePaper() { paperId = null; load(); loadPensum(); loadPapers(); }
  async function begin(s, d) {
    stage = s; direction = d; busy = true; error = ''; done = false; verdict = null; pending = null;
    tally = { correct: 0, wrong: 0, skipped: 0 };
    try {
      const r = await api.get(`${base}/${encodeURIComponent(subject)}/cards?unit=${encodeURIComponent(unit)}&section=${encodeURIComponent(section)}&box=${encodeURIComponent(box)}&stage=${s}&direction=${d}&limit=80`);
      cards = r.cards; index = 0; show();
      if (!cards.length) error = s === 2 ? 'Für die Schreibweise zuerst die Bedeutungen sichern: Stufe 2 fragt nur Wörter, deren Bedeutung sitzt.' : box ? 'Keine Wörter in diesem Kasten.' : section ? 'Keine Wörter in diesem Abschnitt.' : 'Keine Wörter in dieser Einheit.';
    } catch (e) { error = e.message; } finally { busy = false; }
  }
  function show() { answer = ''; spoken = false; edits = 0; clock.reset(); verdict = null; pending = null; setTimeout(() => answerInput?.focus?.(), 50); }
  function seconds() { return clock.seconds(); }
  async function transcribe(blob, took) {
    const requestedCard = card;
    const f = new FormData(); f.append('file', blob, 'aufnahme'); f.append('seconds', String(took)); f.append('unit', unit); f.append('direction', direction);
    clock.pause();
    try {
      const r = await api.post(`${base}/${encodeURIComponent(subject)}/transcribe`, f);
      return r.text;
    } finally { if (card === requestedCard) clock.resume(); }
  }
  function heard(t) { answer = t; spoken = true; submit(); }
  async function submit(confirm = false, gaveUp = false) {
    if (!card || busy) return;
    if (!gaveUp && !answer.trim() && !confirm) return;
    busy = true; error = ''; clock.pause();
    try {
      const r = await api.post(`${base}/attempts`, {
        word_id: card.id, stage, direction, answer: answer.trim(), spoken, gave_up: gaveUp,
        seconds: seconds(), edits, confirm, unit_scope: unit,
      });
      if (r.result === 'unclear') { pending = r; return; }
      pending = null; verdict = r;
      if (r.result === 'correct') tally.correct++; else tally.wrong++;
    } catch (e) { error = e.message; } finally { busy = false; clock.resume(); }
  }
  function next(skip = false) {
    if (skip === true) tally.skipped++;
    if (index + 1 >= cards.length) { done = true; load(); loadPensum(); return; }
    index += 1; show();
  }
  // Eltern: Probeläufe wieder auf Null setzen.
  // Eltern-Werkzeuge nicht beim Mitlesen und nicht, wenn das Kind das Gerät benutzt (D183).
  const canManage = $derived(actsAsParent(appState.me));
  async function showBookWords() {
    busy = true; error = '';
    try { bookWords = (await api.get(`${base}/${encodeURIComponent(subject)}/word-list?unit=${encodeURIComponent(unit)}&section=${encodeURIComponent(section)}`)).words; }
    catch (e) { error = e.message; } finally { busy = false; }
  }
  async function checkImport() {
    if (!importFile) return;
    busy = true; error = ''; importDraft = null;
    try { importDraft = await api.post(`${base}/${encodeURIComponent(subject)}/catalogs`, {payload: JSON.parse(await importFile.text())}); }
    catch (e) { error = e.message; } finally { busy = false; }
  }
  async function activateImport() {
    if (!importDraft?.valid) return;
    busy = true; error = '';
    try {
      await api.post(`${base}/${encodeURIComponent(subject)}/catalogs/${importDraft.id}/activate`, {digest: importDraft.content_digest});
      importDraft = null; importFile = null; bookWords = null; section = ''; box = ''; await load();
    } catch (e) { error = e.message; } finally { busy = false; }
  }
  async function captureOriginal(start = false) {
    busy = true; error = '';
    try {
      const url = `${base}/${encodeURIComponent(subject)}/catalog-capture`;
      captureJob = start ? await api.post(url, {pages: [Number(capturePage)]}) : await api.get(url);
    } catch (e) { error = e.message; } finally { busy = false; }
  }
  async function resetAll() {
    if (!confirm(`Alle Versuche in ${langName} löschen? Die Wörter bleiben, der Stand beginnt bei neu.`)) return;
    busy = true;
    try { const r = await api.delete(`${base}/${encodeURIComponent(subject)}/attempts`); data = { ...data, units: r.units }; }
    catch (e) { error = e.message; } finally { busy = false; }
  }
  const STAGE_TEXT = { neu: 'neu', wackelt: 'wackelt', sitzt: 'sitzt', gefestigt: 'gefestigt' };
  function unitSummary(u, key) {
    const s = u[key] || {};
    const parts = [];
    for (const k of ['gefestigt', 'sitzt', 'wackelt']) if (s[k]) parts.push(`${s[k]} ${k}`);
    if (s.neu) parts.push(`${s.neu} neu`);
    return parts.join(' · ') || 'noch nicht geübt';
  }
  const speechLabel = $derived(askForeign ? 'Aufnahme: Deutsch' : `Aufnahme: ${langName}`);
</script>

<div class="vokabeln">
  <header class="head">
    <a class="back" href={subject ? '#/vokabeln' : '#/learning'}>← zurück</a>
    <h1>{subject ? `${style.emoji} Vokabeln · ${langName}` : 'Vokabeln'}</h1>
  </header>
  {#if error}<p class="notice" role="alert">{error}</p>{/if}
  {#if pensum.length && (!cards.length || done) && !paperId}
    <section class="pensum" aria-label="Vokabeln heute">
      {#each pensum as e (e.subject + e.unit)}
        <a class="pensum-row" class:done={e.done} href={e.href}
           onclick={() => { if (subject && e.subject.toLowerCase() === subject.toLowerCase()) chooseUnit(e.unit); }}>
          <span class="pensum-head"><b>{e.done ? 'Heute geschafft' : 'Heute'}: {e.practiced} von {e.target} Wörtern</b><small>{e.unit_label}</small></span>
          <span class="pensum-bar" role="progressbar" aria-valuemin="0" aria-valuemax={e.target} aria-valuenow={Math.min(e.practiced, e.target)}><span style:width={`${pct(e)}%`}></span></span>
          <small class="pensum-why">{e.why}</small>
        </a>
      {/each}
    </section>
  {/if}

  {#if paperId}
    <section class="card"><VocabPaper {accountId} {paperId} onclose={closePaper} /></section>
  {:else if !subject}
    {#if languages === null}
      <p role="status">Wird geladen …</p>
    {:else if !languages.length}
      <section class="card"><h2>Keine Fremdsprache gefunden</h2><p class="muted">Der Trainer zeigt die Fremdsprachen aus dem Stundenplan: Englisch, Latein, Spanisch, Französisch.</p></section>
    {:else}
      <section class="card">
        <h2>Welche Sprache?</h2>
        <div class="units">
          {#each languages as l (l.subject)}
            <a class="unit link" href={`#/vokabeln/${encodeURIComponent(l.subject)}`}>
              <strong>{subjectStyle(l.subject).emoji} {l.language.name}</strong>
              <span>{l.words ? `${l.words} Wörter in ${l.units} ${l.units === 1 ? 'Einheit' : 'Einheiten'}` : l.reading ? 'Wortseiten werden gerade gelesen …' : 'Noch keine Wortseite abgelegt. Fotografiere die Vokabelseite der Lektion, dann liest der Trainer die Wörter von dort.'}</span>
              <span>{l.language.into ? `Beide Richtungen und Schreibweise` : `${l.language.name} → Deutsch, wie in der Arbeit`}</span>
            </a>
          {/each}
        </div>
      </section>
    {/if}
  {:else if !data}
    <p role="status">Wird geladen …</p>
  {:else if !lang}
    <p class="notice">Für {style.name} gibt es keinen Vokabeltrainer. Er ist für Fremdsprachen gedacht.</p>
  {:else if !cards.length || done}
    {#if done}
      <section class="card result">
        <h2>Durchgang fertig</h2>
        <p>{tally.correct} richtig · {tally.wrong} falsch oder noch nicht korrekt · {tally.skipped} ohne Wertung</p>
        <p class="muted">Noch unsichere Wörter kommen beim nächsten Mal zuerst. Deine Antwortzeit verschlechtert den Lernstand nicht.</p>
        <div class="actions"><button class="primary" onclick={() => begin(stage, direction)}>Noch einmal, Wackler zuerst</button><button onclick={() => { done = false; cards = []; }}>Andere Einheit</button></div>
      </section>
    {/if}
    {#if !data.units.length}
      <section class="card"><h2>Noch keine Wortseite</h2><p>Fotografiere die Vokabelseite der Lektion (Begleitband) oder rufe die Buchseite ab. Der Trainer liest die Lernwörter dann von dort.</p>
        <a href={`#/materialien/${encodeURIComponent(subject)}`}>Material hinzufügen</a></section>
    {:else}
      <section class="card">
        <h2>Welche Einheit?</h2>
        {#if data.overview?.started_units}
          <p><strong>Dein Stand in {data.overview.started_units} begonnenen Einheiten</strong></p>
          <VocabProgress progress={data.overview.progress} />
          {#if lang.into}<VocabProgress progress={data.overview.writing_progress} label="Schreibweise" />{/if}
          <p class="muted small">Jedes Wort zählt einmal. Noch nicht begonnene Einheiten zählen hier nicht mit.</p>
        {:else}<p class="muted small">Noch keine Einheit begonnen. Ungeübte Wörter sind grau und zählen nicht als Fehler.</p>{/if}
        <div class="units">
          {#each data.units as u (u.unit)}
            <button class="unit" class:chosen={unit === u.unit} onclick={() => chooseUnit(u.unit)}>
              <strong>{u.label || u.unit}</strong>
              <span>{u.words ? `${u.words} Wörter · Bedeutung: ${unitSummary(u, 's1')}` : u.unread ? 'Quelle noch nicht freigegeben' : 'keine Lernwörter auf diesen Seiten'}</span>
              {#if u.words && lang.into}<span>Schreibweise: {unitSummary(u, 's2')}</span>{/if}
              <VocabProgress progress={u.progress} />
              {#if u.words && lang.into}<VocabProgress progress={u.writing_progress} label="Schreibweise" />{/if}
            </button>
          {/each}
        </div>
        {#if sections.length}
          <h3>Ganzes Kapitel oder ein Teil?</h3>
          <div class="units">
            <button class="unit" class:chosen={!section} onclick={() => chooseSection('')}>
              <strong>Ganze Einheit</strong><span>{currentUnit?.words ?? 0} Wörter</span>
              <VocabProgress progress={currentUnit?.progress} />
            </button>
            {#each sections as part (part.section)}
              <button class="unit" class:chosen={section === part.section} onclick={() => chooseSection(part.section)}>
                <strong>{part.label || part.section}</strong><span>{part.words} {part.words === 1 ? 'Wort' : 'Wörter'}</span>
                <VocabProgress progress={part.progress} />
              </button>
            {/each}
          </div>
          {#if boxes.length}
            <h3>Oder nur ein Themenkasten aus „{section}"?</h3>
            <div class="units">
              <button class="unit" class:chosen={!box} onclick={() => (box = '')}>
                <strong>Ganzer Abschnitt</strong><span>{sections.find((s) => s.section === section)?.words ?? 0} Wörter</span>
              </button>
              {#each boxes as kasten (kasten.box)}
                <button class="unit" class:chosen={box === kasten.box} onclick={() => (box = kasten.box)}>
                  <strong>{kasten.box}</strong><span>{kasten.words} {kasten.words === 1 ? 'Wort' : 'Wörter'}</span>
                  <VocabProgress progress={kasten.progress} />
                </button>
              {/each}
            </div>
          {/if}
        {/if}
      </section>
      {#if currentUnit}
        {#if currentUnit.catalog}
          <section class="card">
            <p class="muted">{currentUnit.book} · Mehrfach vorkommende Wörter teilen sich einen Lernstand.</p>
            <button disabled={busy} onclick={showBookWords}>Wörter in Buchreihenfolge ansehen</button>
            {#if bookWords}
              <ol class="book-words">
                {#each bookWords as w (w.id)}
                  <li><strong>{w.foreign_word}</strong> — {w.meanings.join('; ')} <small>(S. {w.page})</small></li>
                {/each}
              </ol>
            {/if}
          </section>
        {/if}
        {#if currentUnit.unread}
          <p class="muted reading" role="status">{currentUnit.unread === 1 ? 'Eine Quellenseite ist' : `${currentUnit.unread} Quellenseiten sind`} noch nicht neu geprüft. Der vorhandene Lernbestand bleibt bis zur Freigabe erhalten.</p>
        {/if}
        {#if currentUnit.words}
          <section class="card">
            <h2>Stufe 1: Bedeutung, gesprochen</h2>
            <p class="muted">{lang.into ? `Sag die Bedeutung. Beide Richtungen, wie in der Arbeit.` : `${langName} → Deutsch, wie in der Arbeit. Eine Bedeutung genügt, wenn sie im Buch steht.`}</p>
            <div class="actions">
              <button class="primary" disabled={busy} onclick={() => begin(1, 'from')}>{langName} → Deutsch</button>
              {#if lang.into}<button class="primary" disabled={busy} onclick={() => begin(1, 'into')}>Deutsch → {langName}</button>{/if}
            </div>
          </section>
          {#if lang.into}
            <section class="card">
              <h2>Stufe 2: Schreibweise</h2>
              <p class="muted">Schreib das Wort auf {langName}, ohne Autokorrektur. Nur Wörter, deren Bedeutung schon sitzt.</p>
              <div class="actions"><button disabled={busy} onclick={() => begin(2, 'into')}>Schreibweise üben</button></div>
            </section>
          {/if}
          <section class="card">
            <h2>Test auf Papier</h2>
            <p class="muted">Blatt drucken, von Hand ausfüllen, fotografieren. Die Auswertung zählt im Trainer mit.</p>
            <div class="actions">
              <label class="count">Wörter <select bind:value={paperCount}>{#each [10, 20, 30, 40] as n (n)}<option value={n}>{n}</option>{/each}</select></label>
              <button disabled={busy} onclick={newPaper}>Blatt erstellen</button>
            </div>
            {#if papers.length}
              <div class="actions">
                {#each papers.slice(0, 3) as pp (pp.id)}
                  <button class="ghost" onclick={() => (paperId = pp.id)}>Blatt {pp.code} · {pp.status === 'graded' ? `${pp.right} von ${pp.total} richtig` : pp.status === 'review' ? 'wird geprüft' : 'offen'}</button>
                {/each}
              </div>
            {/if}
          </section>
          {#if canManage}
            <p class="muted"><button class="ghost" disabled={busy} onclick={resetAll}>Stand in {langName} zurücksetzen (Eltern)</button></p>
          {/if}
        {/if}
      {/if}
    {/if}
  {:else}
    <section class="card trainer">
      <div class="progress"><span>{stage === 2 ? 'Stufe 2: Schreibweise' : askForeign ? `${langName} → Deutsch` : `Deutsch → ${langName}`}</span><span>{index + 1} von {cards.length}</span></div>
      <p class="ask">{stage === 2 ? `Schreib es auf ${langName} …` : askForeign ? 'Was heißt …' : `Sag es auf ${langName} …`}</p>
      <div class="word">
        {#if askForeign}
          <strong>{card.foreign_word}</strong>{#if card.grammar}<small> {card.grammar}</small>{/if}
        {:else}
          <strong>{card.meanings.join(', ')}</strong>{#if card.grammar}<small> {card.grammar}</small>{/if}
        {/if}
        <div class="muted where">{card.label} S. {card.page}{#if card.state?.[stage === 2 ? 's2' : 's1']?.stage && card.state[stage === 2 ? 's2' : 's1'].stage !== 'neu'} · bisher: {STAGE_TEXT[card.state[stage === 2 ? 's2' : 's1'].stage]}{/if}</div>
      </div>

      {#if verdict}
        <div class="verdict {verdict.result}">
          <p>{verdict.feedback}</p>
          {#if card.example}<p class="muted">Im Buch: {card.example}</p>{/if}
          <div class="actions">
            {#if verdict.result !== 'correct' && stage === 2}<button onclick={() => { answer = ''; verdict = null; clock.reset(); }}>Noch einmal schreiben</button>{/if}
            <button class="primary" onclick={next}>{index + 1 >= cards.length ? 'Fertig' : 'Nächstes Wort'}</button>
          </div>
        </div>
      {:else if pending}
        <div class="verdict unclear">
          <p>{pending.feedback}</p>
          <div class="actions">
            {#if pending.can_confirm !== false}<button class="primary" disabled={busy} onclick={() => submit(true)}>Ja, das meinte ich</button>{/if}
            <button disabled={busy} onclick={() => { pending = null; answer = ''; spoken = false; }}>{pending.can_confirm === false ? "Antwort präzisieren" : "Nein, noch einmal"}</button>
          </div>
          <button disabled={busy} onclick={() => next(true)}>Ohne Wertung weiter</button>
          <p class="muted">Eine Rückfrage allein zählt nicht als Fehler.</p>
        </div>
      {:else}
        {#if stage === 1 && data.speech && (askForeign || lang.code)}
          {#key card}
          <Speech onText={heard} {transcribe} disabled={busy} label={speechLabel} />
          {/key}
        {/if}
        <form onsubmit={(e) => { e.preventDefault(); submit(); }}>
          {#if busy}<p role="status">Deine Antwort wird geprüft …</p>{/if}
          <input bind:this={answerInput} bind:value={answer} type="text" maxlength="300" placeholder={stage === 2 ? 'Genau so, wie es im Buch steht' : 'oder tippen …'}
                 autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" lang={askForeign ? 'de' : (lang.code || 'de')}
                 onbeforeinput={(e) => { if ((e.inputType || '').startsWith('delete')) edits++; }} oninput={() => (spoken = false)} />
          <div class="actions">
            <button class="primary" disabled={busy || !answer.trim()}>Prüfen</button>
            <button type="button" disabled={busy} onclick={() => submit(false, true)}>Weiß ich nicht – als Fehler werten</button>
            <button type="button" disabled={busy} onclick={() => next(true)}>Überspringen ohne Wertung</button>
          </div>
        </form>
      {/if}
      <p class="muted small">{stage === 2 ? 'Ohne Autokorrektur, ohne Vorschläge. Großschreibung zählt nur, wo sie zum Wort gehört.' : 'Nimm dir Zeit. Richtig bleibt richtig. Wiederholt richtige Antworten festigen deinen Lernstand.'}</p>
    </section>
  {/if}

  {#if canManage && subject && !cards.length}
    <details class="card">
      <summary>Lernversuche prüfen und korrigieren (Eltern)</summary>
      <p>Gezielt ausgewählte Versuche aus der Wertung nehmen oder wieder berücksichtigen. Die ursprünglichen Antworten bleiben erhalten.</p>
      <label>Versuchsnummern<input aria-label="Versuchsnummern" bind:value={reviewIds} oninput={() => reviewDraft = null} /></label>
      <label>Begründung<input aria-label="Begründung" bind:value={reviewReason} oninput={() => reviewDraft = null} /></label>
      <label><input type="checkbox" bind:checked={reviewRestore} onchange={() => reviewDraft = null} /> Wieder in die Wertung aufnehmen</label>
      <button disabled={busy || !reviewIds.trim()} onclick={() => reviewAttempts()}>Auswahl prüfen</button>
      {#if reviewDraft}
        <p>{reviewDraft.attempts.length} ausgewählte Versuche</p>
        <ol>{#each reviewDraft.attempts as a}<li>#{a.id} · {a.created_at} · {a.foreign_word}: {a.answer || '(leer)'} · {a.result}</li>{/each}</ol>
        <button disabled={busy} onclick={() => reviewAttempts(true)}>{reviewRestore ? 'Auswahl wieder werten' : 'Auswahl aus Wertung nehmen'}</button>
      {/if}
      {#if reviewMessage}<p role="status">{reviewMessage}</p>{/if}
    </details>
    <details class="card">
      <summary>Geprüften Buchbestand übernehmen (Eltern)</summary>
      <p>Der neue Bestand wird zuerst getrennt geprüft. Bestehende Lernversuche bleiben erhalten. Ungeklärte Seiten oder Zuordnungen verhindern die Freigabe.</p>
      <label>Fehlende digitale Buchseite <input type="number" min="1" max="2000" bind:value={capturePage} /></label>
      <button disabled={busy || captureJob?.state === 'running'} onclick={() => captureOriginal(true)}>Original getrennt abrufen</button>
      {#if captureJob}
        <button disabled={busy} onclick={() => captureOriginal()}>Abrufstatus prüfen</button>
        <p role="status">{captureJob.state === 'running' ? 'Buchseite wird abgerufen …' : captureJob.result?.sources?.length ? 'Originalaufnahme liegt zur Prüfung vor. Die gedruckte Seitenzahl muss noch geprüft werden.' : 'Keine bestätigte Aufnahme. Bitte Abruf prüfen.'}</p>
      {/if}
      <label>Geprüfte Importdatei <input type="file" accept="application/json,.json" onchange={e => { importFile = e.target.files?.[0] || null; importDraft = null; }} /></label>
      <button disabled={busy || !importFile} onclick={checkImport}>Import prüfen</button>
      {#if importDraft}
        <p role="status">{importDraft.pages} Seiten · {importDraft.occurrences} Fundstellen · {importDraft.issues.length} offene Prüfpunkte</p>
        {#if importDraft.valid}<button class="primary" disabled={busy} onclick={activateImport}>Geprüften Bestand aktivieren</button>
        {:else}<p>Dieser Prüfbestand ist noch nicht freigegeben.</p>{/if}
      {/if}
    </details>
  {/if}
</div>

<style>
  .vokabeln { max-width: 720px; margin: auto; padding-bottom: 1.5rem; }
  .head { display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.6rem; }
  .head h1 { font-size: 1.3rem; margin: 0; }
  .back { min-height: 44px; display: inline-flex; align-items: center; text-decoration: none; }
  .card { border: 1px solid var(--border, #d4e0da); background: var(--bg-card, #fff); padding: 1rem; border-radius: 16px; margin: 0.8rem 0; }
  .card h2 { font-size: 1.05rem; margin: 0 0 0.4rem; }
  .muted { font-size: 0.85rem; opacity: 0.8; }
  .small { margin-top: 0.8rem; }
  .reading { margin: 0.2rem 0.4rem 0.6rem; }
  .notice { padding: 0.8rem; background: var(--warm-soft); color: var(--fg); border-radius: 12px; }
  .actions { display: flex; gap: 0.5rem; flex-wrap: wrap; margin: 0.6rem 0 0; }
  button { min-height: 44px; padding: 0.6rem 0.9rem; border: 1px solid var(--border, #d4e0da); border-radius: 12px; background: var(--bg-card, #fff); color: inherit; font: inherit; cursor: pointer; }
  button.primary, .unit.chosen { background: var(--accent, #247552); color: var(--accent-fg, #fff); border-color: transparent; }
  button:disabled { opacity: 0.5; cursor: default; }
  .units { display: grid; gap: 0.5rem; }
  .unit { text-align: left; display: grid; gap: 0.15rem; }
  .unit span { font-size: 0.8rem; opacity: 0.85; }
  .unit.link { text-decoration: none; color: inherit; border: 1px solid var(--border, #d4e0da); border-radius: 12px; padding: 0.7rem 0.9rem; background: var(--bg-card, #fff); }
  .progress { display: flex; justify-content: space-between; font-size: 0.85rem; opacity: 0.8; }
  .ask { margin: 0.8rem 0 0.2rem; font-size: 0.95rem; }
  .word { margin: 0.2rem 0 0.8rem; }
  .word strong { font-size: 2rem; line-height: 1.2; overflow-wrap: anywhere; }
  .word small { font-size: 0.85rem; opacity: 0.7; margin-left: 0.4rem; }
  .say { margin-left: 0.6rem; min-height: 36px; padding: 0.3rem 0.7rem; font-size: 0.85rem; }
  .where { margin-top: 0.3rem; }
  input { font: inherit; font-size: 1.15rem; box-sizing: border-box; width: 100%; padding: 0.8rem; margin: 0.4rem 0; border: 1px solid var(--border, #ccc); border-radius: 10px; background: var(--bg-card, #fff); color: inherit; }
  .verdict { padding: 0.8rem; border-radius: 12px; border: 1px solid var(--border, #d4e0da); }
  .verdict.correct { background: var(--accent-soft, #e6f2ec); }
  .verdict.partial, .verdict.unclear { background: var(--warm-soft); }
  .verdict.incorrect { background: var(--bad-soft); }
  .verdict p { margin: 0.2rem 0; }
  .result p { margin: 0.3rem 0; }
  .pensum { display: grid; gap: var(--sp-2); margin: var(--sp-2) 0; }
  .pensum-row { display: grid; gap: 4px; padding: var(--sp-2) var(--sp-3); border-radius: var(--r-md); border: 1px solid var(--border); background: var(--bg-card); color: var(--fg); text-decoration: none; }
  .pensum-head { display: flex; justify-content: space-between; gap: var(--sp-2); align-items: baseline; flex-wrap: wrap; font-size: var(--fs-sm); }
  .pensum-head small, .pensum-why { font-size: var(--fs-xs); color: var(--fg-muted); }
  .pensum-bar { height: 7px; border-radius: 4px; background: var(--border); overflow: hidden; }
  .pensum-bar span { display: block; height: 100%; background: var(--accent); }
  .pensum-row.done .pensum-bar span { background: var(--st-sitzt); }
  .count { display: inline-flex; align-items: center; gap: var(--sp-1); font-size: var(--fs-sm); }
  .count select { min-height: 44px; font: inherit; border-radius: var(--r-sm); border: 1px solid var(--border); background: var(--bg-card); color: inherit; padding: 0 var(--sp-2); }
</style>
