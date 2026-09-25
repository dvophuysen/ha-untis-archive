<script>
  // Vokabeltest auf Papier (D181): Blatt drucken, von Hand ausfüllen, Seiten
  // fotografieren, in einem Schritt auswerten. Richtig und falsch zählen im
  // Trainer, unklar Gelesenes zählt nicht.
  import { api } from './api.js';

  let { accountId, paperId, onclose = () => {} } = $props();
  const base = $derived(`/api/accounts/${accountId}/vocab/papers/${paperId}`);
  let p = $state(null), error = $state(''), busy = $state('');
  let fileInput = $state(null);

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

    {#if graded}
      <div class="result">
        <strong class="big">{p.result.richtig} von {p.words.length} richtig</strong>
        {#if p.overall}<p>{p.overall}</p>{/if}
        <p class="dim">{p.counts ? 'Richtig und falsch zählen im Trainer. ' : 'Dieses Blatt zählt nicht für den Lernstand. '}Unklar Gelesenes zählt nicht, weder für noch gegen dich.</p>
      </div>
      <ol class="words">
        {#each p.words as w (w.nr)}
          <li class={w.verdict}>
            <span class="n">{w.nr}.</span>
            <span class="q">{w.prompt}</span>
            <span class="v">{VERDICT[w.verdict] ?? ''}</span>
            <span class="a">{#if w.verdict !== 'richtig'}Richtig: <b>{w.expected}</b>{/if}{#if w.read} · gelesen: „{w.read}“{/if}{#if w.note} · {w.note}{/if}</span>
          </li>
        {/each}
      </ol>
      <button class="primary" onclick={onclose}>Fertig</button>
    {:else if p.read_only}
      <p class="notice">Dieses Blatt ist noch nicht ausgewertet.</p>
    {:else}
      <ol class="steps">
        <li><strong>Drucken</strong> <a class="btn" href={printUrl} target="_blank" rel="noreferrer">Blatt öffnen und drucken</a></li>
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

<style>
  .vpaper{display:grid;gap:var(--sp-2)}
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
</style>
