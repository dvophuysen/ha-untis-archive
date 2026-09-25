<script>
  // Raster Thema × Anforderungsbereich einer Arbeit und die Übungsarbeiten dazu (D178).
  // Vorbereitet heißt: jedes Thema in I und II sicher, gemessen an Aufgaben.
  import { api } from './api.js';
  import { formatShortDate } from './format.js';
  import PracticePaper from './PracticePaper.svelte';

  let { accountId, examKey, parent = false } = $props();
  let data = $state(null), error = $state(''), busy = $state(false);
  let fmt = $state(''), chosen = $state([]), level = $state(0), paperId = $state(null);

  const STATE = {
    offen: { label: 'offen', cls: 'st-neu' },
    unsicher: { label: 'unsicher', cls: 'st-wackelt' },
    fast: { label: 'fast', cls: 'st-angefangen' },
    sicher: { label: 'sicher', cls: 'st-sitzt' },
    bestaetigt: { label: 'bestätigt', cls: 'st-gefestigt' },
  };
  const ROMAN = { 1: 'I', 2: 'II', 3: 'III' };

  async function load() {
    try { data = await api.get(`/api/accounts/${accountId}/practice?exam_key=${encodeURIComponent(examKey)}`); }
    catch (e) { error = e.message; }
  }
  $effect(() => { void examKey; load(); });

  function pick(key) {
    fmt = fmt === key ? '' : key;
    chosen = [];
    level = 0;
  }
  function toggleTopic(id) {
    chosen = chosen.includes(id) ? chosen.filter((x) => x !== id) : [...chosen, id].slice(-3);
  }
  async function create() {
    if (busy) return;
    busy = true; error = '';
    try {
      const a = await api.post(`/api/accounts/${accountId}/practice`, {
        exam_key: examKey, format: fmt, topic_ids: chosen, level: level || null,
      });
      fmt = ''; paperId = a.id;
      await load();
    } catch (e) { error = e.message; }
    finally { busy = false; }
  }
  function cellTitle(t, k) {
    const c = t.cells[k];
    if (c.implied) return 'mit gezeigt: der Bereich darüber sitzt';
    if (!c.tasks) return 'noch keine Aufgabe';
    return `${Math.round(c.ratio * 100)} % der Punkte in den letzten ${c.tasks} ${c.tasks === 1 ? 'Aufgabe' : 'Aufgaben'}${c.helped ? `, ${c.helped}× mit Hilfe (zählt nicht)` : ''}`;
  }
  const needsTopics = $derived(fmt === 'kurz');
  const statusLabel = (p) => p.status === 'graded' ? `${Number(p.points).toLocaleString('de-DE')} von ${p.points_max} Punkten` : p.status === 'active' ? 'noch offen' : 'abgegeben, noch nicht ausgewertet';
</script>

{#if paperId}
  <PracticePaper {accountId} attemptId={paperId} onclose={() => { paperId = null; load(); }} />
{:else if data && data.total}
  <section class="practice">
    <div class="p-head">
      <strong>Übungsarbeiten</strong>
      <span class="dim">{data.ready} von {data.total} {data.total === 1 ? 'Thema' : 'Themen'} sicher in I und II</span>
    </div>
    <p class="dim p-lead">Das Ziel vor der Arbeit: jedes Thema sicher im Wiedergeben (I) und Anwenden (II). Übertragen (III) ist die Kür. Gezählt wird, was du in Aufgaben zeigst, auf Papier oder im Gespräch.</p>

    <div class="grid" role="table" aria-label="Stand je Thema und Anforderungsbereich">
      <div class="g-row g-headrow" role="row">
        <span role="columnheader">Thema</span>
        {#each [1, 2, 3] as k}<span role="columnheader" class="g-afb" title={data.afb_names[k]}>{ROMAN[k]}<small>{data.afb_names[k]}</small></span>{/each}
      </div>
      {#each data.topics as t (t.id)}
        <div class="g-row" role="row">
          <span class="g-topic" role="cell">{t.title}{#if t.ready} ✓{/if}</span>
          {#each ['1', '2', '3'] as k}
            {@const c = t.cells[k]}
            <span role="cell" class="g-cell {STATE[c.state].cls}" class:implied={c.implied} title={cellTitle(t, k)}>
              {STATE[c.state].label}{#if c.tasks && !c.implied}<small>{Math.round(c.ratio * 100)} %</small>{/if}
            </span>
          {/each}
        </div>
      {/each}
    </div>
    <p class="dim legend">sicher: ab 80 % in mindestens zwei Aufgaben ohne Hilfe · fast: 60 bis 79 % oder erst eine Aufgabe · bestätigt: auch in einer Probearbeit</p>

    <div class="formats">
      {#each data.formats as f (f.key)}
        <button class="fmt" class:chosen={fmt === f.key} onclick={() => pick(f.key)} aria-pressed={fmt === f.key}>
          <strong>{f.label}</strong><span class="dim">{f.minutes} Min. · {f.why}</span>
        </button>
      {/each}
    </div>

    {#if fmt}
      <div class="setup">
        {#if needsTopics}
          <p class="dim">Welche Themen? Bis zu drei. Ohne Auswahl nehme ich das schwächste.</p>
          <div class="chips">
            {#each data.topics as t (t.id)}
              <button class="chip" class:on={chosen.includes(t.id)} onclick={() => toggleTopic(t.id)} aria-pressed={chosen.includes(t.id)}>{t.title}</button>
            {/each}
          </div>
        {/if}
        {#if fmt !== 'einstieg'}
          <p class="dim">Niveau</p>
          <div class="chips">
            <button class="chip" class:on={level === 0} onclick={() => (level = 0)}>Stufenweise (empfohlen)</button>
            <button class="chip" class:on={level === 2} onclick={() => (level = 2)}>Gleich II</button>
            <button class="chip" class:on={level === 3} onclick={() => (level = 3)}>Gleich III</button>
          </div>
          <p class="dim">{level ? 'Gleich höher: Sitzt der Bereich, gilt der darunter als mit gezeigt.' : 'Stufenweise: jedes Thema auf dem nächsten Bereich, der noch nicht sitzt.'}</p>
        {/if}
        {#if parent}<p class="notice">Als Elternteil erstellt, zählt die Arbeit nicht für das Raster. Für das Kind: Gerät auf „Kind benutzt das Gerät“ stellen.</p>{/if}
        <button class="primary" disabled={busy} onclick={create}>{busy ? 'Wird erstellt, etwa eine Minute …' : 'Übungsarbeit erstellen'}</button>
      </div>
    {/if}

    {#if data.papers.length}
      <div class="papers">
        {#each data.papers as p (p.id)}
          {#if p.attempt_id}
            <button class="paper" onclick={() => (paperId = p.attempt_id)}>
              <span><strong>{p.label}</strong> · {formatShortDate(p.created_at.slice(0, 10))}</span>
              <span class="dim">{statusLabel(p)}</span>
            </button>
          {/if}
        {/each}
      </div>
    {/if}
    {#if error}<p class="error-box" role="alert">{error}</p>{/if}
  </section>
{/if}

<style>
  .practice{margin-top:var(--sp-3);padding-top:var(--sp-3);border-top:1px solid var(--border);display:grid;gap:var(--sp-2)}
  .p-head{display:flex;justify-content:space-between;gap:var(--sp-2);flex-wrap:wrap;align-items:baseline}
  .p-lead,.legend{margin:0;font-size:var(--fs-xs)}
  .grid{display:grid;gap:3px}
  .g-row{display:grid;grid-template-columns:minmax(0,1fr) repeat(3,minmax(58px,74px));gap:3px;align-items:stretch}
  .g-headrow span{font-size:var(--fs-xs);color:var(--fg-muted);font-weight:700}
  .g-afb{text-align:center;display:grid;line-height:1.1}
  .g-afb small{font-weight:500;font-size:.62rem}
  .g-topic{font-size:var(--fs-sm);overflow-wrap:anywhere;padding:4px 0}
  .g-cell{border-radius:var(--r-sm);font-size:.72rem;font-weight:700;text-align:center;display:grid;align-content:center;min-height:38px;color:#10262a;line-height:1.1}
  .g-cell small{font-weight:500;font-size:.64rem}
  .g-cell.st-gefestigt{color:#fff}
  .g-cell.implied{opacity:.6}
  .formats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:var(--sp-2)}
  .fmt{display:grid;gap:2px;text-align:left;padding:var(--sp-2);border-radius:var(--r-md);background:var(--bg-card);border:2px solid var(--border);min-height:44px}
  .fmt.chosen{border-color:var(--accent)}
  .fmt .dim{font-size:var(--fs-xs)}
  .setup{display:grid;gap:var(--sp-2);padding:var(--sp-2);background:var(--bg-elevated);border-radius:var(--r-md)}
  .setup p{margin:0}
  .chips{display:flex;flex-wrap:wrap;gap:6px}
  .chip{min-height:40px;border-radius:var(--r-pill);padding:4px 12px;background:var(--bg-card);border:1px solid var(--border);font-size:var(--fs-sm)}
  .chip.on{background:var(--accent);color:var(--accent-fg,#fff);border-color:var(--accent)}
  .papers{display:grid;gap:4px}
  .paper{display:flex;justify-content:space-between;gap:var(--sp-2);flex-wrap:wrap;text-align:left;min-height:44px;padding:var(--sp-2);border-radius:var(--r-sm);background:var(--bg-card);border:1px solid var(--border)}
  .notice{padding:var(--sp-2);background:var(--warm-soft);border-radius:var(--r-sm);font-size:var(--fs-sm)}
</style>
