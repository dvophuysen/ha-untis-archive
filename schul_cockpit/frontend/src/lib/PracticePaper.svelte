<script>
  // Eine Übungsarbeit (D178): drucken, auf Papier lösen, Seiten fotografieren,
  // in einem Schritt auswerten. Wer lieber tippt, tippt; beides geht zusammen.
  import { api } from './api.js';
  import PrintSheet from './PrintSheet.svelte';
  import { view } from './viewMode.svelte.js';

  let { accountId, attemptId, onclose = () => {}, backLabel = 'Zurück zum Raster' } = $props();
  const base = $derived(`/api/accounts/${accountId}/practice/attempts/${attemptId}`);
  let a = $state(null), error = $state(''), busy = $state(''), typing = $state(false), answers = $state({});
  let fileInput = $state(null), printing = $state(false);
  const ROMAN = { 1: 'I', 2: 'II', 3: 'III' };
  const num = (x) => Number(x).toLocaleString('de-DE');
  const store = () => `practice-answers-${attemptId}`;

  async function load() {
    try {
      a = await api.get(base);
      try { answers = { ...a.answers, ...JSON.parse(localStorage.getItem(store()) || '{}') }; } catch { answers = { ...a.answers }; }
      typing = Object.values(answers).some((v) => (v || '').trim());
    } catch (e) { error = e.message; }
  }
  $effect(() => { void attemptId; load(); });

  function remember() {
    try { localStorage.setItem(store(), JSON.stringify(answers)); } catch { /* nur Komfort */ }
  }
  async function run(label, fn) {
    if (busy) return;
    busy = label; error = '';
    try { await fn(); } catch (e) { error = e.message; } finally { busy = ''; }
  }
  async function upload(ev) {
    const files = [...(ev.target.files || [])];
    ev.target.value = '';
    await run('Seite wird hochgeladen …', async () => {
      for (const f of files) {
        const form = new FormData();
        form.append('file', f);
        a = await api.post(`${base}/pages`, form);
      }
    });
  }
  const removePage = (pid) => run('Wird entfernt …', async () => { a = await api.delete(`${base}/pages/${pid}`); });
  const grade = () => run('Wird ausgewertet, das dauert bis zu zwei Minuten …', async () => {
    a = await api.post(`${base}/grade`, { answers });
    try { localStorage.removeItem(store()); } catch { /* egal */ }
  });

  const photoUrl = (pid) => `./api/accounts/${accountId}/learning/mentor/exams/attempts/${attemptId}/photos/${pid}`;
  const printUrl = $derived(`.${base}/print`);
  const graded = $derived(a?.status === 'graded');
  const total = $derived(a ? a.exam.tasks.reduce((s, t) => s + t.points, 0) : 0);
  const got = $derived(a && graded ? a.exam.tasks.reduce((s, t, i) => s + (a.feedback[String(i)]?.uncertain ? 0 : a.feedback[String(i)]?.points || 0), 0) : 0);
  const canSubmit = $derived(a && (a.pages.length || Object.values(answers).some((v) => (v || '').trim())));
</script>

<section class="paper-view">
  <button class="ghost back" onclick={onclose}>← {backLabel}</button>
  {#if !a}
    {#if error}<p class="error-box" role="alert">{error}</p>{:else}<span class="spinner"></span>{/if}
  {:else}
    <header>
      <span class="dim">{a.label} · Blatt Ü{a.id} · {a.exam.minutes} Minuten · {total} Punkte</span>
      <h3>{a.exam.title}</h3>
    </header>

    {#if graded}
      <div class="result">
        <strong class="big">{num(got)} von {total} Punkten</strong>
        {#if a.feedback.overall?.text}<p>{a.feedback.overall.text}</p>{/if}
        <p class="dim">KI-Auswertung nach den Punktkriterien, keine Schulnote. Unklar Gelesenes zählt nicht, weder für noch gegen dich.</p>
      </div>
      {#each a.exam.tasks as t, i}
        {@const f = a.feedback[String(i)]}
        <article class="task">
          <div class="t-head"><strong>Aufgabe {i + 1}</strong><span class="tag">{t.skill_title} · {ROMAN[t.afb]}</span>
            <span class="pts" class:full={f && !f.uncertain && f.points === t.points}>{f?.uncertain ? 'unklar' : `${num(f?.points ?? 0)} / ${t.points}`}</span></div>
          {#if t.abbildung}<img class="fig" src={`./api/accounts/${accountId}/materials/figures/${t.abbildung}`} alt={t.abbildung_text || 'Abbildung zur Aufgabe'} loading="lazy" />{/if}<p class="preserve">{t.prompt}</p>
          {#if f}<p>{f.rationale}</p><p><strong>Nächster Schritt:</strong> {f.next_step}</p>
            {#if f.transcription}<details><summary>So wurde deine Antwort gelesen</summary><p class="preserve">{f.transcription}</p></details>{/if}{/if}
          <details><summary>Lösung und Punktkriterien</summary><p class="preserve">{t.solution}</p><p class="preserve dim">{t.criteria}</p></details>
        </article>
      {/each}
      <button class="primary" onclick={onclose}>Zum Raster</button>
    {:else if a.read_only || view.mode === 'mirror'}
      <p class="notice">Nur ansehen: Die Arbeit ist noch nicht ausgewertet. Drucken geht trotzdem.</p>
      <button class="btn" onclick={() => (printing = true)}>🖨️ Blatt drucken</button>
      {#each a.exam.tasks as t, i}
        <article class="task"><div class="t-head"><strong>Aufgabe {i + 1}</strong><span class="dim">{t.points} Punkte</span></div>{#if t.abbildung}<img class="fig" src={`./api/accounts/${accountId}/materials/figures/${t.abbildung}`} alt={t.abbildung_text || 'Abbildung zur Aufgabe'} loading="lazy" />{/if}<p class="preserve">{t.prompt}</p></article>
      {/each}
    {:else}
      <ol class="steps">
        <li><strong>Drucken</strong> <button class="btn" onclick={() => (printing = true)}>🖨️ Blatt drucken</button></li>
        <li><strong>Lösen</strong> <span class="dim">auf Papier, etwa {a.exam.minutes} Minuten, ohne Buch und ohne Hilfe. Nur so zählt es.</span></li>
        <li><strong>Seiten fotografieren</strong> <span class="dim">alle beschriebenen Seiten, gerade von oben, hell. Höchstens sechs.</span>
          <input type="file" accept="image/*" multiple style="display:none" bind:this={fileInput} onchange={upload} />
          <div class="pages">
            {#each a.pages as pid, n (pid)}
              <figure><img src={photoUrl(pid)} alt={`Seite ${n + 1}`} loading="lazy" /><button class="ghost" disabled={!!busy} onclick={() => removePage(pid)} aria-label={`Seite ${n + 1} entfernen`}>✕</button></figure>
            {/each}
            {#if a.pages.length < 6}<button class="add" disabled={!!busy} onclick={() => fileInput?.click()}>📷 Seite hinzufügen</button>{/if}
          </div>
        </li>
      </ol>
      <label class="check"><input type="checkbox" bind:checked={typing} /> Lieber am Gerät tippen</label>
      {#if typing}
        {#each a.exam.tasks as t, i}
          <article class="task">
            <div class="t-head"><strong>Aufgabe {i + 1}</strong><span class="dim">{t.points} Punkte</span></div>
            {#if t.abbildung}<img class="fig" src={`./api/accounts/${accountId}/materials/figures/${t.abbildung}`} alt={t.abbildung_text || 'Abbildung zur Aufgabe'} loading="lazy" />{/if}<p class="preserve">{t.prompt}</p>
            <textarea rows="4" bind:value={answers[String(i)]} oninput={remember} placeholder="Deine Antwort. Diktieren geht auch."></textarea>
          </article>
        {/each}
      {/if}
      <button class="primary" disabled={!!busy || !canSubmit} onclick={grade}>Abgeben und auswerten</button>
      {#if !canSubmit}<p class="dim">Erst Seiten fotografieren oder Antworten tippen.</p>{/if}
    {/if}
    {#if busy}<p role="status">{busy}</p>{/if}
    {#if error}<p class="error-box" role="alert">{error}</p>{/if}
  {/if}
  {#if printing && a}<PrintSheet url={printUrl.slice(1)} title={a.exam.title} spaceChoice onclose={() => (printing = false)} />{/if}
</section>

<style>
  .fig { display: block; max-width: 100%; max-height: 320px; margin: 0.3rem 0; background: #fff; border-radius: var(--r-sm); }
  .paper-view{display:grid;gap:var(--sp-2);margin-top:var(--sp-3);padding-top:var(--sp-3);border-top:1px solid var(--border)}
  .back{justify-self:start;min-height:40px}
  header h3{margin:2px 0 0}
  .steps{margin:0;padding-left:1.2rem;display:grid;gap:var(--sp-2)}
  .steps li{display:grid;gap:4px}
  .btn{display:inline-block;padding:8px 12px;border-radius:var(--r-sm);border:1px solid var(--border);background:var(--bg-card);justify-self:start;min-height:40px;box-sizing:border-box}
  .pages{display:flex;flex-wrap:wrap;gap:6px}
  figure{margin:0;position:relative}
  figure img{width:72px;height:96px;object-fit:cover;border-radius:var(--r-sm);border:1px solid var(--border)}
  figure button{position:absolute;top:2px;right:2px;min-height:28px;min-width:28px;padding:0;background:var(--bg-card)}
  .add{width:72px;height:96px;border-radius:var(--r-sm);border:2px dashed var(--border);background:var(--bg-card);font-size:var(--fs-xs)}
  .task{padding:var(--sp-2);border:1px solid var(--border);border-radius:var(--r-md);background:var(--bg-card);display:grid;gap:4px}
  .task p{margin:0}
  .t-head{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
  .tag{font-size:.7rem;font-weight:700;border-radius:var(--r-pill);padding:1px 7px;background:var(--bg-elevated);color:var(--fg-muted)}
  .pts{margin-left:auto;font-weight:700;padding:2px 8px;border-radius:var(--r-pill);background:var(--st-angefangen);color:#10262a}
  .pts.full{background:var(--st-sitzt)}
  .result{padding:var(--sp-3);border-radius:var(--r-md);background:color-mix(in oklab,var(--accent) 12%,var(--bg-card))}
  .result p{margin:4px 0 0}
  .big{font-size:var(--fs-lg,1.3rem)}
  .preserve{white-space:pre-wrap;overflow-wrap:anywhere}
  textarea{width:100%;box-sizing:border-box;font:inherit;font-size:16px;padding:8px;border-radius:var(--r-sm);border:1px solid var(--border);background:var(--bg-card);color:inherit}
  .check{display:flex;gap:8px;align-items:center;min-height:40px}
  .notice{padding:var(--sp-2);background:var(--warm-soft);border-radius:var(--r-sm)}
  details summary{cursor:pointer;min-height:36px;display:flex;align-items:center}
</style>
