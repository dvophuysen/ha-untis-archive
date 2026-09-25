<script>
  // Elternprüfung eines Vokabeltests auf Papier (D207): jedes Wort richtig oder
  // falsch, bei falsch mit Grund, Hinweis und Merkhilfe; auf Wunsch mit
  // KI-Vorschlag. Das Kind sieht danach genau diese Bewertung.
  import { untrack } from 'svelte';
  import { api } from './api.js';
  import { showFile } from './fileViewer.svelte.js';

  let { paper, base, onsaved = () => {}, oncancel = () => {} } = $props();
  const KINDS = [['wortschatz', 'Wort nicht gewusst'], ['sprache', 'Rechtschreibung'], ['regel', 'Artikel, Form oder Grammatik'],
    ['unvollstaendig', 'Nur teilweise richtig'], ['nicht_bearbeitet', 'Leer gelassen']];
  const fromWords = (src) => Object.fromEntries(paper.words.map((w) => {
    const x = src?.[String(w.nr)] ?? w;
    const v = x.verdict === 'richtig' || x.verdict === 'falsch' ? x.verdict : '';
    return [String(w.nr), { verdict: v, kind: x.kind || 'wortschatz', note: x.note || '', tip: x.tip || '' }];
  }));
  let form = $state(untrack(() => fromWords(null)));
  let overall = $state(untrack(() => ({ text: paper.overall || '', strengths: (paper.summary?.strengths || []).join('\n'), focus: (paper.summary?.focus || []).join('\n') })));
  let hint = $state(''), busy = $state(''), error = $state(''), suggested = $state(false);
  const lines = (s) => s.split('\n').map((x) => x.trim()).filter(Boolean).slice(0, 3);
  const missing = $derived(paper.words.filter((w) => !form[String(w.nr)].verdict).map((w) => w.nr));

  async function suggest() {
    if (busy) return;
    busy = 'Die App liest das Blatt noch einmal genau …'; error = '';
    try {
      const s = await api.post(`${base}/manual/suggest`, { hint });
      form = fromWords(s.words);
      overall = { text: s.overall.text || '', strengths: (s.overall.strengths || []).join('\n'), focus: (s.overall.focus || []).join('\n') };
      suggested = true;
    } catch (e) { error = e.message; } finally { busy = ''; }
  }
  async function save() {
    if (busy || missing.length) return;
    busy = 'Wird gespeichert …'; error = '';
    try {
      const words = Object.fromEntries(Object.entries(form).map(([nr, x]) => [nr, x.verdict === 'richtig'
        ? { verdict: 'richtig' } : { verdict: 'falsch', kind: x.kind, note: x.note.trim(), tip: x.tip.trim() }]));
      onsaved(await api.post(`${base}/manual`, { words, overall: { text: overall.text.trim(), strengths: lines(overall.strengths), focus: lines(overall.focus) } }));
    } catch (e) { error = e.message; } finally { busy = ''; }
  }
</script>

<section class="vmanual">
  <div class="notice">
    <strong>Selbst prüfen</strong>
    <p>Entscheidet jedes Wort. Bei einem falschen Wort sieht das Kind, was genau falsch war und wie es sich das Wort merkt.</p>
  </div>
  {#if paper.pages.length}<div class="pages">{#each paper.pages as id, n (id)}<button type="button" class="page-open" onclick={() => showFile(`.${base}/pages/${id}`, `Seite ${n + 1}`)} aria-label={`Seite ${n + 1} groß ansehen`}><img src={`.${base}/pages/${id}`} alt={`Seite ${n + 1}`} loading="lazy" /></button>{/each}</div>{/if}
  <label>Hinweis für die KI (freiwillig)<textarea rows="2" bind:value={hint} placeholder="Zum Beispiel: Wort 4 ist richtig, nur unsauber geschrieben."></textarea></label>
  <button class="btn" disabled={!!busy} onclick={suggest}>{suggested ? 'Neuen KI-Vorschlag holen' : 'KI-Vorschlag holen'}</button>
  <ol class="rows">
    {#each paper.words as w (w.nr)}
      {@const x = form[String(w.nr)]}
      <li>
        <div class="head"><span class="n">{w.nr}.</span> <span class="q">{w.prompt}</span> <span class="dim">erwartet: <b>{w.expected}</b>{#if w.read} · gelesen: „{w.read}“{/if}</span></div>
        <span class="choice" role="group" aria-label={`Wort ${w.nr}`}>
          {#each ['richtig', 'falsch'] as v (v)}<button class="ghost" class:chosen={x.verdict === v} aria-pressed={x.verdict === v} disabled={!!busy} onclick={() => (x.verdict = v)}>{v}</button>{/each}
        </span>
        {#if x.verdict === 'falsch'}
          <select bind:value={x.kind} aria-label={`Grund Wort ${w.nr}`}>{#each KINDS as [k, l] (k)}<option value={k}>{l}</option>{/each}</select>
          <input type="text" bind:value={x.note} placeholder="Was war falsch?" aria-label={`Was war falsch bei Wort ${w.nr}`} />
          <input type="text" bind:value={x.tip} placeholder="Merkhilfe" aria-label={`Merkhilfe Wort ${w.nr}`} />
        {/if}
      </li>
    {/each}
  </ol>
  <label>Gesamtsatz<textarea rows="2" bind:value={overall.text}></textarea></label>
  <label>Das klappt schon (eine Zeile je Punkt)<textarea rows="2" bind:value={overall.strengths}></textarea></label>
  <label>Das übt das Kind als Nächstes (eine Zeile je Schritt)<textarea rows="2" bind:value={overall.focus}></textarea></label>
  {#if missing.length}<p class="warn">Noch offen: Wort {missing.join(', ')}.</p>{/if}
  {#if busy}<p role="status">{busy}</p>{/if}
  {#if error}<p class="error-box" role="alert">{error}</p>{/if}
  <div class="acts"><button class="primary" disabled={!!busy || missing.length > 0} onclick={save}>Prüfung speichern</button><button class="ghost" disabled={!!busy} onclick={oncancel}>Abbrechen</button></div>
</section>

<style>
  .vmanual { display: grid; gap: var(--sp-2); }
  .vmanual p { margin: 0; }
  label { display: grid; gap: 2px; }
  textarea, input, select { font: inherit; width: 100%; box-sizing: border-box; min-width: 0; }
  .rows { margin: 0; padding: 0; list-style: none; display: grid; gap: 8px; }
  .rows li { display: grid; gap: 4px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
  .head { overflow-wrap: anywhere; }
  .choice { display: flex; gap: 6px; }
  .choice button { min-height: 40px; }
  .choice .chosen { background: var(--accent-soft, #e6f0ff); font-weight: 700; }
  .pages { display: flex; flex-wrap: wrap; gap: 6px; }
  .page-open { padding: 0; border: 0; background: none; cursor: zoom-in; }
  .page-open img { width: 72px; height: 96px; object-fit: cover; border-radius: var(--r-sm); border: 1px solid var(--border); }
  .btn { justify-self: start; }
  .warn { color: var(--warn, #b26a00); }
  .acts { display: flex; flex-wrap: wrap; gap: var(--sp-2); }
  .dim { color: var(--fg-muted); font-size: var(--fs-xs); }
</style>
