<script>
  // Vokabeltest auf Papier (D181): Blatt drucken, von Hand ausfüllen, Seiten
  // fotografieren, auswerten. Ein Wort zählt nur, wenn zwei unabhängige
  // Auswertungen es gleich lesen; bleiben zu viele offen, prüfen die Eltern (D202).
  import { api } from './api.js';
  import PrintSheet from './PrintSheet.svelte';
  import VocabManual from './VocabManual.svelte';
  import { actsAsParent } from './viewMode.svelte.js';
  import { appState } from './store.svelte.js';

  let { accountId, paperId, onclose = () => {} } = $props();
  const base = $derived(`/api/accounts/${accountId}/vocab/papers/${paperId}`);
  let p = $state(null), error = $state(''), busy = $state('');
  let fileInput = $state(null), printing = $state(false), manual = $state(false);

  async function load() {
    try { p = await api.get(base); } catch (e) { error = e.message; }
  }
  $effect(() => { void paperId; load(); });

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
        p = await api.post(`${base}/pages`, form);
      }
    });
  }
  const removePage = (id) => run('Wird entfernt …', async () => { p = await api.delete(`${base}/pages/${id}`); });
  const grade = () => run('Wird ausgewertet, das dauert bis zu einer Minute …', async () => { p = await api.post(`${base}/grade`, {}); });

  const pageUrl = (id) => `.${base}/pages/${id}`;
  const printUrl = $derived(`.${base}/print`);
  const graded = $derived(p?.status === 'graded');
  const VERDICT = { richtig: 'richtig', falsch: 'falsch', unklar: 'unklar' };
  // Zurückgehalten (D202): zu viele Wörter auch nach drei Auswertungen nicht sicher gelesen.
  const reviewing = $derived(p?.status === 'review');
  const parentView = $derived(actsAsParent(appState.me));
  const unsure = $derived(p?.check?.unsure ?? []);
  let decided = $state({});
  const reviewReady = $derived(unsure.every((nr) => decided[String(nr)]));
  const saveReview = () => run('Wird gespeichert …', async () => {
    p = await api.post(`${base}/review`, { verdicts: Object.fromEntries(unsure.map((nr) => [String(nr), decided[String(nr)]])) });
    decided = {};
  });
</script>

<section class="vpaper">
  <button class="ghost back" onclick={onclose}>← Zurück</button>
  {#if !p}
    {#if error}<p class="error-box" role="alert">{error}</p>{:else}<span class="spinner"></span>{/if}
  {:else}
    <header>
      <span class="dim">Blatt {p.code} · {p.words.length} Wörter · {p.direction === 'into' ? `Deutsch → ${p.language}` : `${p.language} → Deutsch`}</span>
      <h3>Vokabeltest · {p.unit_label || p.unit}</h3>
    </header>

    {#if manual && parentView && (reviewing || graded)}
      <VocabManual paper={p} {base} onsaved={(r) => { p = r; manual = false; }} oncancel={() => (manual = false)} />
    {:else if reviewing && !parentView}
      <div class="notice review-wait" role="status">
        <strong>Dein Blatt ist abgegeben.</strong>
        <p>Einige Wörter konnte die App auch nach mehreren Versuchen nicht sicher lesen. Deine Eltern schauen sich die Auswertung an; danach siehst du hier dein Ergebnis. So zählt kein Wort falsch, weder für noch gegen dich.</p>
      </div>
      <button class="primary" onclick={onclose}>Fertig</button>
    {:else if reviewing}
      <div class="notice review-box">
        <strong>Prüfung nötig: {unsure.length} {unsure.length === 1 ? 'Wort' : 'Wörter'}</strong>
        <p>{unsure.length === 1 ? 'Dieses Wort ließ' : 'Diese Wörter ließen'} sich auch nach {p.check?.passes ?? 2} Auswertungen nicht sicher lesen. Bis ihr sie prüft, sieht das Kind kein Ergebnis, und nichts zählt im Trainer. Schaut auf den Fotos nach und entscheidet je Wort.</p>
        {#if p.pages.length}<div class="pages">{#each p.pages as id, n (id)}<a href={pageUrl(id)} target="_blank" rel="noreferrer"><img class="thumb" src={pageUrl(id)} alt={`Seite ${n + 1}`} loading="lazy" /></a>{/each}</div>{/if}
      </div>
      <ol class="words">
        {#each p.words.filter((w) => unsure.includes(w.nr)) as w (w.nr)}
          <li class="unklar">
            <span class="n">{w.nr}.</span>
            <span class="q">{w.prompt}</span>
            <span class="choice" role="group" aria-label={`Wort ${w.nr}`}>
              {#each ['richtig', 'falsch'] as v (v)}<button class="ghost" class:chosen={decided[String(w.nr)] === v} aria-pressed={decided[String(w.nr)] === v} disabled={!!busy} onclick={() => (decided[String(w.nr)] = v)}>{v}</button>{/each}
            </span>
            <span class="a">Erwartet: <b>{w.expected}</b>{#if w.read} · gelesen: „{w.read}“{/if}</span>
          </li>
        {/each}
      </ol>
      <button class="primary" disabled={!!busy || !reviewReady} onclick={saveReview}>Übernehmen</button>
      <button class="btn" disabled={!!busy} onclick={() => (manual = true)}>Alle Wörter selbst prüfen</button>
    {:else if graded}
      <div class="result">
        <strong class="big">{p.result.richtig} von {p.words.length} richtig</strong>
        {#if p.overall}<p>{p.overall}</p>{/if}
        <p class="dim">{p.counts ? 'Richtig und falsch zählen im Trainer. ' : 'Dieses Blatt zählt nicht für den Lernstand. '}{p.check?.manual ? 'Von deinen Eltern geprüft. ' : p.check?.resolved_by_parent?.length ? 'Unsicher gelesene Wörter haben deine Eltern geprüft. ' : p.check ? 'Gezählt wird nur, was zwei unabhängige Auswertungen gleich lesen. ' : ''}Nicht sicher Gelesenes zählt nicht, weder für noch gegen dich.</p>
      </div>
      {#if p.summary?.strengths?.length || p.losses?.length || p.summary?.focus?.length}
        <div class="summary">
          {#if p.summary?.strengths?.length}<div><strong>Das klappt schon</strong><ul>{#each p.summary.strengths as x, i (i)}<li>{x}</li>{/each}</ul></div>{/if}
          {#if p.losses?.length}<div><strong>Daran lag es bei den falschen Wörtern</strong><ul>{#each p.losses as l (l.kind)}<li>{l.label}: {l.count} {l.count === 1 ? 'Wort' : 'Wörter'}</li>{/each}</ul></div>{/if}
          {#if p.summary?.focus?.length}<div><strong>Das übst du als Nächstes</strong><ol>{#each p.summary.focus as x, i (i)}<li>{x}</li>{/each}</ol></div>{/if}
        </div>
      {/if}
      <ol class="words">
        {#each p.words as w (w.nr)}
          <li class={w.verdict}>
            <span class="n">{w.nr}.</span>
            <span class="q">{w.prompt}</span>
            <span class="v">{VERDICT[w.verdict] ?? ''}</span>
            <span class="a">{#if w.verdict === 'unklar'}Nicht sicher gelesen, zählt nicht · {/if}{#if w.verdict !== 'richtig'}Richtig: <b>{w.expected}</b>{/if}{#if w.read} · gelesen: „{w.read}“{/if}{#if w.note} · {w.note}{/if}{#if w.checked_by_parent} · von deinen Eltern geprüft{/if}</span>
            {#if w.verdict === 'falsch' && w.tip}<span class="tip"><b>Merkhilfe:</b> {w.tip}</span>{/if}
          </li>
        {/each}
      </ol>
      {#if parentView}<button class="btn" disabled={!!busy} onclick={() => (manual = true)}>Selbst prüfen</button>{/if}
      <button class="primary" onclick={onclose}>Fertig</button>
    {:else if p.read_only}
      <p class="notice">Dieses Blatt ist noch nicht ausgewertet.</p>
    {:else}
      <ol class="steps">
        <li><strong>Drucken</strong> <button class="btn" onclick={() => (printing = true)}>🖨️ Blatt drucken</button></li>
        <li><strong>Ausfüllen</strong> <span class="dim">ohne Buch und ohne Hilfe. Nur so zählt es.</span></li>
        <li><strong>Fotografieren</strong> <span class="dim">alle Seiten, gerade von oben, hell. Höchstens vier.</span>
          <input type="file" accept="image/*" multiple style="display:none" bind:this={fileInput} onchange={upload} />
          <div class="pages">
            {#each p.pages as id, n (id)}
              <figure><img src={pageUrl(id)} alt={`Seite ${n + 1}`} loading="lazy" /><button class="ghost" disabled={!!busy} onclick={() => removePage(id)} aria-label={`Seite ${n + 1} entfernen`}>✕</button></figure>
            {/each}
            {#if p.pages.length < 4}<button class="add" disabled={!!busy} onclick={() => fileInput?.click()}>Seite hinzufügen</button>{/if}
          </div>
        </li>
      </ol>
      <button class="primary" disabled={!!busy || !p.pages.length} onclick={grade}>Auswerten</button>
    {/if}
    {#if busy}<p role="status">{busy}</p>{/if}
    {#if error}<p class="error-box" role="alert">{error}</p>{/if}
  {/if}
</section>

{#if printing}<PrintSheet url={printUrl.slice(1)} title="Vokabeltest" onclose={() => (printing = false)} />{/if}

<style>
  .vpaper{display:grid;gap:var(--sp-2)}
  .summary{display:grid;gap:8px;padding:var(--sp-2);border:1px solid var(--border);border-radius:var(--r-md)}
  .summary ul,.summary ol{margin:2px 0 0;padding-left:1.2em}
  .tip{grid-column:1/-1;font-size:var(--fs-sm)}
  .back{justify-self:start;min-height:40px}
  header h3{margin:2px 0 0;font-size:var(--fs-md)}
  .dim{font-size:var(--fs-xs);color:var(--fg-muted)}
  .steps{margin:0;padding-left:1.2rem;display:grid;gap:var(--sp-2)}
  .steps li{display:grid;gap:4px}
  .btn{display:inline-block;padding:8px 12px;border-radius:var(--r-sm);border:1px solid var(--border);background:var(--bg-card);justify-self:start;min-height:40px;box-sizing:border-box}
  .pages{display:flex;flex-wrap:wrap;gap:6px}
  figure{margin:0;position:relative}
  figure img{width:72px;height:96px;object-fit:cover;border-radius:var(--r-sm);border:1px solid var(--border)}
  figure button{position:absolute;top:2px;right:2px;min-height:28px;min-width:28px;padding:0;background:var(--bg-card)}
  .add{width:72px;height:96px;border-radius:var(--r-sm);border:2px dashed var(--border);background:var(--bg-card);font-size:var(--fs-xs)}
  .result{padding:var(--sp-3);border-radius:var(--r-md);background:color-mix(in oklab,var(--accent) 12%,var(--bg-card))}
  .result p{margin:4px 0 0}
  .big{font-size:var(--fs-lg)}
  .words{list-style:none;margin:0;padding:0;display:grid;gap:4px}
  .words li{display:grid;grid-template-columns:2rem 1fr auto;gap:2px var(--sp-2);padding:var(--sp-2);border:1px solid var(--border);border-radius:var(--r-sm);background:var(--bg-card)}
  .words .n{font-weight:700}.words .q{overflow-wrap:anywhere}
  .words .v{font-size:var(--fs-xs);font-weight:700;padding:1px 8px;border-radius:var(--r-pill);background:var(--bg-elevated)}
  .words li.richtig .v{background:var(--st-sitzt);color:#10262a}
  .words li.falsch .v{background:var(--st-wackelt);color:#10262a}
  .words .a{grid-column:2 / 4;font-size:var(--fs-xs);color:var(--fg-muted);overflow-wrap:anywhere}
  .words .a:empty{display:none}
  .notice{padding:var(--sp-2);background:var(--warm-soft);border-radius:var(--r-sm)}
  .review-box,.review-wait{display:grid;gap:4px}
  .review-box p,.review-wait p{margin:0}
  .thumb{width:72px;height:96px;object-fit:cover;border-radius:var(--r-sm);border:1px solid var(--border)}
  .choice{display:flex;gap:4px}
  .choice button{min-height:36px;padding:2px 10px}
  .choice .chosen{background:var(--accent);color:var(--accent-fg,#fff)}
</style>
