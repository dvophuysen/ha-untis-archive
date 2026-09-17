<script>
  // Vokabeltrainer: Wörter aus den Originalseiten, zwei Stufen. Stufe 1 fragt
  // die Bedeutung gesprochen, Stufe 2 die Schreibweise getippt in die
  // Fremdsprache. Kein Multiple Choice; die App wertet, nicht das Kind.
  import { api } from '../lib/api.js';
  import Speech from '../lib/Speech.svelte';
  import { subjectStyle } from '../lib/subjectStyle.js';
  import { appState } from '../lib/store.svelte.js';
  let { accountId, subject = '', initialUnit = '' } = $props();
  const style = $derived(subjectStyle(subject));
  const base = $derived(`/api/accounts/${accountId}/learning/vocab`);
  let data = $state(null), error = $state(''), busy = $state(false);
  // Das Standardbündel ist die ganze Einheit. Ein Abschnitt, den die
  // Vokabelliste selbst nennt („Texto A"), ist nur eine Einschränkung
  // davon und wird beim Wechsel der Einheit wieder aufgehoben (D100).
  let unit = $state(initialUnit), section = $state(''), stage = $state(1), direction = $state('from');
  let cards = $state([]), index = $state(0), answer = $state(''), spoken = $state(false), edits = $state(0), shownAt = $state(0);
  let verdict = $state(null), pending = $state(null), done = $state(false), tally = $state({ correct: 0, slow: 0, wrong: 0 });
  let answerInput = $state(null);

  const lang = $derived(data?.language);
  const langName = $derived(lang?.name ?? subject);
  const card = $derived(cards[index] ?? null);
  const askForeign = $derived(direction === 'from');
  const currentUnit = $derived((data?.units || []).find((u) => u.unit === unit));
  const sections = $derived(currentUnit?.sections || []);
  function chooseUnit(name) { if (unit !== name) { unit = name; section = ''; } }

  // Wortseiten werden beim Öffnen automatisch in Wörter zerlegt; solange das
  // läuft, lädt die Ansicht alle paar Sekunden nach.
  let pollTimer = null, polls = 0;
  let languages = $state(null);
  async function load() {
    error = '';
    try {
      if (!subject) { languages = (await api.get(`${base}/languages`)).languages; data = null; return; }
      data = await api.get(`${base}/${encodeURIComponent(subject)}/units`);
      if (!unit && data.units.length) unit = data.units[0].unit;
      clearTimeout(pollTimer);
      if (data.reading && polls < 20) { polls += 1; pollTimer = setTimeout(load, 4000); } else polls = 0;
    } catch (e) { error = e.message; }
  }
  $effect(() => { void accountId; void subject; polls = 0; load(); return () => clearTimeout(pollTimer); });
  async function begin(s, d) {
    stage = s; direction = d; busy = true; error = ''; done = false; verdict = null; pending = null;
    tally = { correct: 0, slow: 0, wrong: 0 };
    try {
      const r = await api.get(`${base}/${encodeURIComponent(subject)}/cards?unit=${encodeURIComponent(unit)}&section=${encodeURIComponent(section)}&stage=${s}&direction=${d}&limit=80`);
      cards = r.cards; index = 0; show();
      if (!cards.length) error = s === 2 ? 'Für die Schreibweise zuerst die Bedeutungen sichern: Stufe 2 fragt nur Wörter, deren Bedeutung sitzt.' : section ? 'Keine Wörter in diesem Abschnitt.' : 'Keine Wörter in dieser Einheit.';
    } catch (e) { error = e.message; } finally { busy = false; }
  }
  function show() { answer = ''; spoken = false; edits = 0; shownAt = Date.now(); verdict = null; pending = null; setTimeout(() => answerInput?.focus?.(), 50); }
  function seconds() { return Math.min(3600, Math.round((Date.now() - shownAt) / 1000)); }
  async function transcribe(blob, took) {
    const f = new FormData(); f.append('file', blob, 'aufnahme'); f.append('seconds', String(took)); f.append('unit', unit); f.append('direction', direction);
    const r = await api.post(`${base}/${encodeURIComponent(subject)}/transcribe`, f);
    return r.text;
  }
  function heard(t) { answer = t; spoken = true; submit(); }
  async function submit(confirm = false, gaveUp = false) {
    if (!card || busy) return;
    if (!gaveUp && !answer.trim() && !confirm) return;
    busy = true; error = '';
    try {
      const r = await api.post(`${base}/attempts`, {
        word_id: card.id, stage, direction, answer: answer.trim(), spoken, gave_up: gaveUp,
        seconds: seconds(), edits, confirm,
      });
      if (r.result === 'unclear') { pending = r; return; }
      pending = null; verdict = r;
      if (r.result === 'correct') { if (/Zögern/.test(r.feedback)) tally.slow++; else tally.correct++; } else tally.wrong++;
    } catch (e) { error = e.message; } finally { busy = false; }
  }
  function next() {
    if (index + 1 >= cards.length) { done = true; load(); return; }
    index += 1; show();
  }
  // Eltern: Probeläufe wieder auf Null setzen.
  const canManage = $derived(!!(appState.me && (appState.me.is_admin || appState.me.role === 'parent')));
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

  {#if !subject}
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
        <p>{tally.correct} sofort richtig · {tally.slow} richtig mit Zögern · {tally.wrong} falsch oder offen</p>
        <p class="muted">Zögern und zweite Anläufe merkt sich der Trainer als „wackelt“; diese Wörter kommen beim nächsten Mal zuerst.</p>
        <div class="actions"><button class="primary" onclick={() => begin(stage, direction)}>Noch einmal, Wackler zuerst</button><button onclick={() => { done = false; cards = []; }}>Andere Einheit</button></div>
      </section>
    {/if}
    {#if !data.units.length}
      <section class="card"><h2>Noch keine Wortseite</h2><p>Fotografiere die Vokabelseite der Lektion (Begleitband) oder rufe die Buchseite ab. Der Trainer liest die Lernwörter dann von dort.</p>
        <a href={`#/materialien/${encodeURIComponent(subject)}`}>Material hinzufügen</a></section>
    {:else}
      <section class="card">
        <h2>Welche Einheit?</h2>
        <div class="units">
          {#each data.units as u (u.unit)}
            <button class="unit" class:chosen={unit === u.unit} onclick={() => chooseUnit(u.unit)}>
              <strong>{u.unit}</strong>
              <span>{u.words ? `${u.words} Wörter · Bedeutung: ${unitSummary(u, 's1')}` : u.unread ? 'wird gerade gelesen …' : 'keine Lernwörter auf diesen Seiten'}</span>
              {#if u.words && lang.into}<span>Schreibweise: {unitSummary(u, 's2')}</span>{/if}
            </button>
          {/each}
        </div>
        {#if sections.length}
          <h3>Ganzes Kapitel oder ein Teil?</h3>
          <div class="units">
            <button class="unit" class:chosen={!section} onclick={() => (section = '')}>
              <strong>Ganze Einheit</strong><span>{currentUnit?.words ?? 0} Wörter</span>
            </button>
            {#each sections as part (part.section)}
              <button class="unit" class:chosen={section === part.section} onclick={() => (section = part.section)}>
                <strong>{part.section}</strong><span>{part.words} {part.words === 1 ? 'Wort' : 'Wörter'}</span>
              </button>
            {/each}
          </div>
        {/if}
      </section>
      {#if currentUnit}
        {#if currentUnit.unread}
          <p class="muted reading" role="status">Ich lese gerade noch {currentUnit.unread === 1 ? 'eine Seite' : `${currentUnit.unread} Seiten`} dieser Einheit … Die Wörter kommen gleich dazu.</p>
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
            {#if verdict.result !== 'correct' && stage === 2}<button onclick={() => { answer = ''; verdict = null; shownAt = Date.now(); }}>Noch einmal schreiben</button>{/if}
            <button class="primary" onclick={next}>{index + 1 >= cards.length ? 'Fertig' : 'Nächstes Wort'}</button>
          </div>
        </div>
      {:else if pending}
        <div class="verdict unclear">
          <p>{pending.feedback}</p>
          <div class="actions">
            <button class="primary" onclick={() => submit(true)}>Ja, das meinte ich</button>
            <button onclick={() => { pending = null; answer = ''; spoken = false; }}>Nein, noch einmal</button>
          </div>
          <p class="muted">Die Rückfrage zählt nicht als Hilfe, aber auch nicht als sofort richtig.</p>
        </div>
      {:else}
        {#if stage === 1 && data.speech && (askForeign || lang.code)}
          <Speech onText={heard} {transcribe} disabled={busy} label={speechLabel} />
        {/if}
        <form onsubmit={(e) => { e.preventDefault(); submit(); }}>
          <input bind:this={answerInput} bind:value={answer} type="text" maxlength="300" placeholder={stage === 2 ? 'Genau so, wie es im Buch steht' : 'oder tippen …'}
                 autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" lang={askForeign ? 'de' : (lang.code || 'de')}
                 onbeforeinput={(e) => { if ((e.inputType || '').startsWith('delete')) edits++; }} oninput={() => (spoken = false)} />
          <div class="actions">
            <button class="primary" disabled={busy || !answer.trim()}>Prüfen</button>
            <button type="button" disabled={busy} onclick={() => submit(false, true)}>Weiß ich nicht</button>
          </div>
        </form>
      {/if}
      <p class="muted small">{stage === 2 ? 'Ohne Autokorrektur, ohne Vorschläge. Großschreibung zählt nur, wo sie zum Wort gehört.' : 'Zögern und zweite Anläufe merkt sich der Trainer als „wackelt“.'}</p>
    </section>
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
  .notice { padding: 0.8rem; background: #fff0cf; color: #493a12; border-radius: 12px; }
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
  .verdict.partial, .verdict.unclear { background: #fff0cf; }
  .verdict.incorrect { background: #fde7e5; }
  .verdict p { margin: 0.2rem 0; }
  .result p { margin: 0.3rem 0; }
</style>
