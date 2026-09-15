<script>
  import { api } from '../lib/api.js';
  import ActionLabel from '../lib/ActionLabel.svelte';

  let { accountId, initialSubject = '', taskId = null } = $props();

  const KIND_NAMES = {
    worksheet: 'Arbeitsblatt',
    workbook: 'Arbeitsheft',
    book_page: 'Buchseite',
    notes: 'Mitschrift',
    assignment: 'Aufgabenstellung',
    own_work: 'Meine Bearbeitung',
    exam: 'Klassenarbeit',
    handout: 'Merkblatt',
    other: 'Sonstiges',
  };
  const STATE_NAMES = {
    pending: 'wird gelesen …',
    ready: 'gelesen',
    failed: 'konnte nicht gelesen werden',
  };

  let data = $state(null);
  let error = $state(null);
  let message = $state(null);
  let busy = $state(false);
  let uploading = $state(0);
  let open = $state(null);
  let form = $state(null);
  let filterSubject = $state(initialSubject);
  let filterKind = $state('');
  let search = $state('');
  let picker = $state(null);
  let ledger = $state(null);
  let camera = $state(null);
  let timer = null;

  const base = $derived(`/api/accounts/${accountId}/materials`);
  const KIND_HINT = { workbook: 'Heftseite', worksheet: 'Blatt', book: 'Buchseite', unknown: 'Quelle unklar' };
  // Warum eine Stelle fotografiert werden muss, obwohl es ein digitales Buch gibt.
  const REASON_HINT = {
    unavailable: 'das digitale Buch liefert diese Seite nicht',
    passt_nicht: 'die Schulbuchseite passt nicht zum Zitat, vermutlich ein anderes Heft',
  };
  const ACCESS_NAMES = { unknown: 'noch nicht geprüft', proven: 'Abruf nachgewiesen', readable: 'Seite lesbar', blank: 'liefert leere Seiten', viewer_error: 'nicht erreichbar' };
  let collecting = $state(null);

  async function collectNow() {
    // Der Sammellauf dauert Minuten; anstoßen und nachfragen, bis er fertig ist.
    collecting = { state: 'running', seconds: 0 };
    const startedAt = Date.now();
    try {
      let state = await api.post(`${base}/sources/collect`);
      while (state.state === 'running' && Date.now() - startedAt < 20 * 60 * 1000) {
        collecting = { state: 'running', seconds: Math.round((Date.now() - startedAt) / 1000) };
        await new Promise((resolve) => setTimeout(resolve, 5000));
        state = await api.get(`${base}/sources/collect`);
      }
      collecting = state.state === 'done' ? { state: 'done', ...state.result } : { state: 'timeout' };
      await load();
    } catch (e) {
      collecting = { state: 'failed', detail: e.message };
    }
  }
  const waiting = $derived((data?.materials ?? []).some((m) => m.analysis_state === 'pending'));

  async function load() {
    if (!accountId) return;
    const query = new URLSearchParams();
    if (filterSubject) query.set('subject', filterSubject);
    if (filterKind) query.set('kind', filterKind);
    if (search.trim()) query.set('q', search.trim());
    try {
      data = await api.get(`${base}?${query}`);
      error = null;
    } catch (e) {
      error = e.message;
    }
    // Die Einkaufsliste darf die Seite nicht mitreißen, wenn sie ausfällt.
    try {
      ledger = await api.get(`${base}/sources`);
    } catch {
      ledger = null;
    }
  }

  async function act(fn) {
    busy = true;
    error = null;
    try {
      await fn();
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  $effect(() => {
    void accountId;
    void filterSubject;
    void filterKind;
    load();
  });

  // While something is still being read, refresh on its own so nobody has to
  // pull down or wonder whether it worked.
  $effect(() => {
    clearInterval(timer);
    if (waiting) timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  });

  async function send(files) {
    const list = [...(files ?? [])];
    if (!list.length) return;
    uploading = list.length;
    message = null;
    for (const file of list) {
      const body = new FormData();
      body.append('file', file);
      if (filterSubject) body.append('subject_name', filterSubject);
      if (taskId) body.append('task_id', String(taskId));
      try {
        await api.post(base, body);
      } catch (e) {
        error = e.message;
      }
      uploading -= 1;
    }
    message = list.length === 1 ? 'Gespeichert. Ich lese es gerade.' : `${list.length} Seiten gespeichert.`;
    await load();
  }

  function dateOf(m) {
    const value = m.document_date || m.created_at?.slice(0, 10);
    return value ? new Date(value).toLocaleDateString('de-DE') : '';
  }

  async function show(m) {
    open = await api.get(`${base}/${m.id}`);
    form = data.can_manage
      ? {
          title: open.title ?? '',
          subject_name: open.subject_name ?? '',
          kind: open.kind ?? 'other',
          document_date: open.document_date ?? '',
          summary: open.summary ?? '',
          content_text: open.content_text ?? '',
          contains_solutions: !!open.contains_solutions,
        }
      : null;
  }

  async function save() {
    open = await api.patch(`${base}/${open.id}`, form);
    message = 'Korrektur gespeichert. Sie bleibt auch bei einer neuen Auswertung erhalten.';
    await load();
  }
</script>

<div class="row between head">
  <h1>Materialien</h1>
  <button class="quiet" onclick={() => history.back()}>← zurück</button>
</div>

<div class="card drop">
  <p class="lead">Fotografiere ein Arbeitsblatt, eine Heftseite oder eine Aufgabe. Mehr brauchst du nicht — Fach, Thema und Text erkenne ich selbst.</p>
  <div class="row gap-sm">
    <button class="primary big" disabled={busy || uploading > 0} onclick={() => camera?.click()}>
      📷 Foto aufnehmen
    </button>
    <button disabled={busy || uploading > 0} onclick={() => picker?.click()}>
      Datei wählen (auch PDF)
    </button>
  </div>
  <input bind:this={camera} class="hidden-input" type="file" accept="image/*" capture="environment"
         multiple onchange={(e) => act(() => send(e.currentTarget.files)).then(() => (e.target.value = ''))} />
  <input bind:this={picker} class="hidden-input" type="file" accept="image/png,image/jpeg,image/webp,application/pdf"
         multiple onchange={(e) => act(() => send(e.currentTarget.files)).then(() => (e.target.value = ''))} />
  {#if uploading > 0}<p role="status">Noch {uploading} wird gespeichert …</p>{/if}
  {#if message}<div class="banner">{message}</div>{/if}
  {#if error}<div class="error-box">{error}</div>{/if}
</div>

{#if ledger?.missing_total || ledger?.pending_total}
  <details class="card wanted">
    <summary>
      <span><strong>Was mir noch fehlt</strong>
        {#if ledger.missing_total} · {ledger.missing_total} {ledger.missing_total === 1 ? 'Stelle' : 'Stellen'} zum Fotografieren{/if}
        {#if ledger.pending_total} · {ledger.pending_total} {ledger.pending_total === 1 ? 'Buchseite hole' : 'Buchseiten hole'} ich mir selbst{/if}</span>
    </summary>
    <p class="lead">Diese Stellen nennt der Unterricht seit Schuljahresbeginn. Digitale Buchseiten hole ich mir selbst,
      nach der Schule und nachts; hier steht, was davon noch unterwegs ist und was fotografiert werden müsste,
      weil es nur auf Papier existiert.</p>
    {#each ledger.subjects.filter((s) => s.missing_count || s.pending) as subject (subject.subject)}
      <details class="subject">
        <summary>
          <span class="name">{subject.subject}</span>
          <span class="count">
            {#if subject.missing_count}{subject.missing_count} {subject.missing_count === 1 ? 'Seite' : 'Seiten'} fehlen{/if}
            {#if subject.missing_count && subject.pending} · {/if}
            {#if subject.pending}{subject.pending} unterwegs{/if}
          </span>
        </summary>
        {#if subject.digital}<p class="muted">{subject.digital} Buchseiten liegen digital vor.</p>{/if}
        {#if subject.pending}<p class="muted">Buchseiten, die ich noch hole: {subject.pending_pages.join(', ')}.</p>{/if}
        {#each subject.chapters ?? [] as chapter}
          <p class="muted">Kapitel {chapter.number} {chapter.title} (S. {chapter.start_page}{chapter.end_page ? `–${chapter.end_page}` : ''}):
            {chapter.pages_stored} von {chapter.pages} Seiten da{#if chapter.companions?.length}, dazu {chapter.companions.map((c) => c.title).join(', ')}{/if}.</p>
        {/each}
        {#each subject.missing as need}
          <div class="need">
            <p class="what"><strong>{need.label} {need.pages_label}</strong>
              <span class="muted">· {REASON_HINT[need.reason] ?? KIND_HINT[need.kind] ?? need.kind}</span></p>
            <p class="quote">„{need.quote}"</p>
            <p class="muted">zuletzt genannt am {new Date(need.last_date).toLocaleDateString('de-DE')}{#if need.mentions > 1} · {need.mentions}× erwähnt{/if}</p>
          </div>
        {/each}
      </details>
    {/each}
    {#if ledger.books?.length}
      <p class="muted foot">Digitale Bücher:
        {#each ledger.books as book, i}{i ? ' · ' : ''}{book.subject}: {book.pages_stored} {book.pages_stored === 1 ? 'Seite' : 'Seiten'} gespeichert{#if book.access} ({ACCESS_NAMES[book.access.status] ?? book.access.status}){/if}{/each}
      </p>
    {/if}
    {#if data?.can_manage}
      <p class="foot">
        <button disabled={collecting?.state === 'running'} onclick={collectNow}>
          {collecting?.state === 'running' ? `Sammle … ${collecting.seconds} s` : 'Jetzt einsammeln'}
        </button>
        {#if collecting?.state === 'done'}
          <span class="muted">Fertig: {collecting.stored} Seiten abgelegt, {collecting.verified} bestätigt{#if collecting.blank}, {collecting.blank} leer{/if}{#if collecting.failed}, {collecting.failed} nicht geliefert{/if}{#if collecting.skipped}: {collecting.skipped}{/if}.</span>
        {:else if collecting?.state === 'failed'}
          <span class="muted">Nicht gestartet: {collecting.detail}</span>
        {:else if collecting?.state === 'timeout'}
          <span class="muted">Läuft noch im Hintergrund. Später neu laden.</span>
        {/if}
      </p>
    {/if}
    <p class="muted foot">Die Zuordnung der Kürzel ist eine Annahme aus dem Wortlaut: „TB" als Schulbuch, „AH" und „cda" als Arbeitsheft.
      Wo im Text kein Buchteil steht, nehme ich zuerst das Schulbuch an und prüfe die Seite am Inhalt.</p>
  </details>
{/if}

{#if data}
  <div class="row gap-sm filters">
    <label>Fach
      <select bind:value={filterSubject}>
        <option value="">alle</option>
        {#each [...new Set(data.materials.map((m) => m.subject_name).filter(Boolean))] as s}
          <option>{s}</option>
        {/each}
      </select>
    </label>
    <label>Art
      <select bind:value={filterKind}>
        <option value="">alle</option>
        {#each data.kinds as k}<option value={k}>{KIND_NAMES[k] ?? k}</option>{/each}
      </select>
    </label>
    <label class="grow">Suche
      <input type="search" bind:value={search} placeholder="Titel oder Inhalt"
             onchange={() => load()} />
    </label>
  </div>

  {#if taskId}
    <div class="banner">Alles, was du hier ablegst, gehört zu dieser Hausaufgabe.</div>
  {/if}

  {#if data.can_manage && data.needs_check > 0}
    <div class="banner">{data.needs_check} Eintrag/Einträge warten auf deinen Blick. Du kannst sie unten öffnen und korrigieren.</div>
  {/if}

  <div class="list">
    {#each data.materials as m}
      <button class="item" onclick={() => act(() => show(m))}>
        {#if m.mime_type?.startsWith('image/')}
          <img src={`.${base}/${m.id}/file`} alt="" loading="lazy" />
        {:else}
          <span class="doc" aria-hidden="true">📄</span>
        {/if}
        <span class="text">
          <strong>{m.title || 'Ohne Titel'}</strong>
          <small>
            {[m.subject_name, KIND_NAMES[m.kind] ?? m.kind, dateOf(m)].filter(Boolean).join(' · ')}
          </small>
          {#if m.summary}<small class="dim">{m.summary}</small>{/if}
        </span>
        <span class="state" class:warn={m.analysis_state === 'failed'}>
          {m.analysis_state === 'ready' && !m.verified && data.can_manage
            ? 'bitte prüfen'
            : STATE_NAMES[m.analysis_state] ?? ''}
        </span>
      </button>
    {:else}
      <p class="empty">Noch nichts abgelegt. Das erste Foto genügt.</p>
    {/each}
  </div>
{/if}

{#if open}
  <div class="card detail">
    <div class="row between">
      <h2>{open.title || 'Material'}</h2>
      <button class="quiet" onclick={() => { open = null; form = null; }}>schließen</button>
    </div>
    {#if open.mime_type?.startsWith('image/')}
      <img class="preview" src={`.${base}/${open.id}/file`} alt="Vorschau des Materials" />
    {:else}
      <a href={`.${base}/${open.id}/file`} target="_blank" rel="noreferrer">{open.filename}</a>
    {/if}
    {#if open.analysis_error}<p class="notice">Nicht gelesen: {open.analysis_error}</p>{/if}
    {#if open.summary}<p>{open.summary}</p>{/if}
    {#if open.content_text}
      <details><summary>Erkannter Text</summary><p class="preserve">{open.content_text}</p></details>
    {/if}

    {#if form}
      <form onsubmit={(e) => { e.preventDefault(); act(save); }}>
        <h3>Korrigieren</h3>
        <p class="dim">Was du hier änderst, bleibt bei jeder späteren Auswertung erhalten.</p>
        <label>Titel<input bind:value={form.title} maxlength="200" /></label>
        <div class="row gap-sm">
          <label class="grow">Fach<input bind:value={form.subject_name} maxlength="120" /></label>
          <label>Art
            <select bind:value={form.kind}>
              {#each data.kinds as k}<option value={k}>{KIND_NAMES[k] ?? k}</option>{/each}
            </select>
          </label>
          <label>Datum<input type="date" bind:value={form.document_date} /></label>
        </div>
        <label>Kurzbeschreibung<textarea bind:value={form.summary} maxlength="600" rows="2"></textarea></label>
        <label>Erkannter Text<textarea bind:value={form.content_text} maxlength="30000" rows="6"></textarea></label>
        <label class="check"><input type="checkbox" bind:checked={form.contains_solutions} /> Enthält Lösungen</label>
        <div class="row gap-sm">
          <button class="primary" disabled={busy}>Korrektur speichern</button>
          <button type="button" disabled={busy}
                  onclick={() => act(async () => {
                    open = await api.post(`${base}/${open.id}/verified`, { value: !open.verified });
                    await load();
                  })}>
            {open.verified ? 'Prüfung zurücknehmen' : '✓ Geprüft'}
          </button>
          <button type="button" disabled={busy}
                  onclick={() => act(async () => {
                    await api.post(`${base}/${open.id}/analysis`, {});
                    message = 'Wird neu gelesen.';
                    await load();
                  })}>Neu auswerten</button>
          <button type="button" disabled={busy}
                  onclick={() => act(async () => {
                    if (!confirm('Dieses Material endgültig löschen?')) return;
                    await api.delete(`${base}/${open.id}`);
                    open = null; form = null;
                    await load();
                  })}>Löschen</button>
        </div>
      </form>
    {:else}
      <button disabled={busy}
              onclick={() => act(async () => {
                await api.post(`${base}/${open.id}/hidden`, { value: true });
                open = null;
                await load();
              })}>Aus meiner Liste nehmen</button>
    {/if}
  </div>
{/if}

<style>
  .wanted{border-left:4px solid var(--accent)}
  .wanted>summary{cursor:pointer;min-height:44px;display:flex;align-items:center;list-style:none}
  .wanted>summary::-webkit-details-marker{display:none}
  .wanted .subject{border:1px solid var(--border);border-radius:10px;padding:8px 10px;margin:8px 0}
  .wanted .subject>summary{cursor:pointer;min-height:40px;display:flex;justify-content:space-between;align-items:center;gap:12px;list-style:none}
  .wanted .subject>summary::-webkit-details-marker{display:none}
  .wanted .name{font-weight:550}
  .wanted .count{color:var(--fg-muted);font-size:.9rem;white-space:nowrap}
  .need{padding:8px 0;border-top:1px solid var(--border)}
  .need .what{margin:0 0 4px}
  .need .quote{margin:0 0 4px;font-style:italic;overflow-wrap:anywhere}
  .wanted .foot{margin-top:12px}

  .head h1 { margin: 0; font-size: 1.3rem; }
  .drop { margin-top: 0.6rem; }
  .lead { margin: 0 0 0.7rem; }
  .big { font-size: 1.05rem; padding: 0.7rem 1rem; }
  .hidden-input { display: none; }
  .filters { flex-wrap: wrap; margin-top: 0.8rem; align-items: flex-end; }
  .filters label { margin: 0; }
  .grow { flex: 1 1 10rem; }
  .list { margin-top: 0.6rem; display: grid; gap: 0.4rem; }
  .item {
    display: grid; grid-template-columns: 3.2rem minmax(0, 1fr) auto; gap: 0.7rem;
    align-items: center; text-align: left; width: 100%; padding: 0.5rem 0.6rem;
    background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 8px; cursor: pointer;
  }
  .item img { width: 3.2rem; height: 3.2rem; object-fit: cover; border-radius: 6px; }
  .doc { font-size: 1.8rem; text-align: center; }
  .text { display: grid; gap: 0.1rem; min-width: 0; }
  .text small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .state { font-size: 0.78rem; color: var(--text-dim); white-space: nowrap; }
  .state.warn { color: var(--danger, #b3261e); }
  .preview { display: block; max-width: 100%; border: 1px solid var(--border); border-radius: 6px; margin: 0.5rem 0; }
  .detail { margin-top: 0.8rem; }
  .detail h2 { margin: 0; font-size: 1.1rem; }
  @media (max-width: 560px) {
    .item { grid-template-columns: 2.6rem minmax(0, 1fr); }
    .state { grid-column: 2; }
  }
</style>
