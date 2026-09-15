<script>
  import { api } from '../lib/api.js';
  import ActionLabel from '../lib/ActionLabel.svelte';
  import { subjectStyle } from '../lib/subjectStyle.js';

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
    exam_notice: 'Ankündigung einer Arbeit',
    toc: 'Inhaltsverzeichnis (Papierbuch)',
    other: 'Sonstiges',
  };
  // Die Buchteile der Quellenbilanz; Latein hat Textband und Begleitband.
  const BOOK_PARTS = ['Textband', 'Begleitband', 'Schulbuch', 'Arbeitsheft', 'Grammatikheft', 'Arbeitsblatt'];
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
    gewohnheit: 'in diesem Fach ist sonst immer das Arbeitsheft gemeint',
  };
  const ACCESS_NAMES = { unknown: 'noch nicht geprüft', proven: 'Abruf nachgewiesen', readable: 'Seite lesbar', blank: 'liefert leere Seiten', viewer_error: 'nicht erreichbar', paper: 'nur auf Papier, Verzeichnis aus Fotos' };
  // Das Fach kommt aus dem Stundenplan, nicht aus dem Tippfeld: sonst steht
  // „Latein" neben „LATEIN" und die Quellen finden ihr Material nicht.
  let catalog = $state([]);
  const subjectOptions = $derived.by(() => {
    const seen = new Map();
    for (const s of catalog) if (s.untis_name) seen.set(s.untis_name, s.name);
    for (const m of data?.materials ?? []) if (m.subject_name && !seen.has(m.subject_name)) seen.set(m.subject_name, subjectStyle(m.subject_name).name + ' (nicht im Stundenplan)');
    return [...seen.entries()].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label, 'de'));
  });
  // Was das nächste Foto ist, wenn man es vorher sagen will; sonst erkenne ich es selbst.
  let upload = $state({ subject: '', kind: '', part: '', page: '' });
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
  const waitingBudget = $derived((data?.materials ?? []).filter((m) => m.analysis_state === 'failed' && m.analysis_error === '429').length);
  const openSubject = $derived(open?.subject_name ?? '');

  function shortBook(title) {
    return (title || '').split(' - ')[0].split(' · ')[0].split(':')[0]
      .replace(/\b(ab|von)\s+\d{4}\b|\(\d{4}\)|\bG9\b|\bE-Book\b|\bAusgabe\b|\bBiBox\b|\bGymnasium\b|\bNiedersachsen\b|\bBremen\b/g, ' ')
      .split(/\s+/).filter(Boolean).slice(0, 5).join(' ').replace(/[ ,]+$/, '') || title;
  }

  // Je Fach eine Gruppe; darin Fotos und Scans nach Datum, Buchseiten je Buch
  // nach Seitenzahl.
  const groups = $derived.by(() => {
    const bySubject = new Map();
    for (const m of data?.materials ?? []) {
      const key = m.subject_name || '';
      if (!bySubject.has(key)) bySubject.set(key, { subject: key, items: [], bookPages: [], books: [], waiting: 0 });
      const g = bySubject.get(key);
      if (m.analysis_state === 'failed' && m.analysis_error === '429') g.waiting += 1;
      if (m.origin === 'book_fetch') g.bookPages.push(m); else g.items.push(m);
    }
    for (const g of bySubject.values()) {
      const byBook = new Map();
      for (const m of g.bookPages) {
        if (!byBook.has(m.source_book)) byBook.set(m.source_book, { title: m.source_book, short: shortBook(m.source_book), pages: [] });
        byBook.get(m.source_book).pages.push(m);
      }
      g.books = [...byBook.values()];
      for (const b of g.books) b.pages.sort((a, c) => (a.source_page ?? 0) - (c.source_page ?? 0));
    }
    return [...bySubject.values()].sort((a, b) => a.subject.localeCompare(b.subject, 'de'));
  });

  let offset = $state(0);
  const PAGE = 300;

  async function load(more = false) {
    if (!accountId) return;
    const query = new URLSearchParams();
    if (filterSubject) query.set('subject', filterSubject);
    if (filterKind) query.set('kind', filterKind);
    if (search.trim()) query.set('q', search.trim());
    query.set('limit', String(PAGE));
    query.set('offset', String(more ? offset + PAGE : 0));
    if (!catalog.length) {
      try {
        catalog = (await api.get(`/api/accounts/${accountId}/subjects`)).subjects ?? [];
      } catch {
        catalog = [];
      }
    }
    try {
      const page = await api.get(`${base}?${query}`);
      // Alles ist sichtbar, Buchseiten eingeschlossen; wer weiter unten sucht,
      // lädt weiter, statt dass eine Grenze still abschneidet.
      data = more && data ? { ...page, materials: [...data.materials, ...page.materials] } : page;
      offset = page.offset;
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

  // Ein Link aus einer Aufgabe oder Stunde öffnet sein Material direkt.
  $effect(() => {
    void accountId;
    const q = new URLSearchParams(window.location.hash.split('?')[1] || '');
    const wanted = Number(q.get('material'));
    if (wanted && accountId) act(() => show({ id: wanted }));
  });

  // While something is still being read, refresh on its own so nobody has to
  // pull down or wonder whether it worked.
  $effect(() => {
    clearInterval(timer);
    if (waiting) timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  });

  // Ein Eintrag der Einkaufsliste wurde angetippt: das nächste Foto oder die
  // nächste Datei gehört genau zu dieser Stelle.
  let claim = $state(null);

  function photoFor(subject, need, item, viaCamera) {
    claim = { subject, label: need.label, page: item.page };
    (viaCamera ? camera : picker)?.click();
  }

  async function send(files) {
    const list = [...(files ?? [])];
    const target = claim;
    claim = null;
    if (!list.length) return;
    uploading = list.length;
    message = null;
    for (const file of list) {
      const body = new FormData();
      body.append('file', file);
      if (target) {
        body.append('subject_name', target.subject);
        body.append('source_label', target.label);
        body.append('source_page', String(target.page));
      } else {
        if (upload.subject || filterSubject) body.append('subject_name', upload.subject || filterSubject);
        if (upload.kind) body.append('kind', upload.kind);
        if (upload.part) body.append('source_label', upload.part);
        if (upload.page) body.append('source_page', String(Number(upload.page)));
      }
      if (taskId) body.append('task_id', String(taskId));
      try {
        await api.post(base, body);
      } catch (e) {
        error = e.message;
      }
      uploading -= 1;
    }
    message = target
      ? `${target.label} ${target.page ? `S. ${target.page}` : ''} abgehakt. Ich lese es gerade.`
      : upload.kind === 'toc' ? 'Inhaltsverzeichnis gespeichert. Ich lese die Kapitel daraus, sobald alle Seiten da sind.'
      : upload.kind === 'exam_notice' ? 'Ankündigung gespeichert. Jede genannte Stelle kommt auf die Liste und wird vorgezogen.'
      : list.length === 1 ? 'Gespeichert. Ich lese es gerade.' : `${list.length} Seiten gespeichert.`;
    upload.page = '';
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
          source_label: open.source_label ?? '',
          source_page: open.source_page ?? '',
        }
      : null;
  }

  async function save() {
    // Eine leere Seite heißt „keine Seite"; 0 räumt sie serverseitig aus.
    open = await api.patch(`${base}/${open.id}`, { ...form, source_page: form.source_page ? Number(form.source_page) : 0 });
    message = 'Korrektur gespeichert. Sie bleibt auch bei einer neuen Auswertung erhalten.';
    await load();
  }
</script>

<div class="row between head">
  <h1>Materialien</h1>
  <button class="quiet" onclick={() => history.back()}>← zurück</button>
</div>

<div class="card drop">
  <p class="lead">Fotografiere ein Arbeitsblatt, eine Heftseite oder eine Aufgabe. Mehr brauchst du nicht — Fach, Thema und Text erkenne ich selbst.
    Den Zettel mit dem Stoff für eine Arbeit oder das Inhaltsverzeichnis eines Buchs, das nur auf Papier existiert, sagst du mir vorher.</p>
  <div class="row gap-sm options">
    <label>Fach
      <select bind:value={upload.subject}>
        <option value="">erkenne ich</option>
        {#each subjectOptions as s}<option value={s.value}>{s.label}</option>{/each}
      </select>
    </label>
    <label>Was ist es?
      <select bind:value={upload.kind}>
        <option value="">erkenne ich</option>
        {#each data?.kinds ?? Object.keys(KIND_NAMES) as k}<option value={k}>{KIND_NAMES[k] ?? k}</option>{/each}
      </select>
    </label>
    <label>Buchteil
      <select bind:value={upload.part}>
        <option value="">erkenne ich</option>
        {#each BOOK_PARTS as part}<option value={part}>{part}</option>{/each}
      </select>
    </label>
    {#if upload.kind && upload.kind !== 'toc' && upload.kind !== 'exam_notice'}
      <label>Seite<input type="number" min="1" max="1999" bind:value={upload.page} placeholder="lese ich ab" /></label>
    {/if}
  </div>
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
          <span class="name">{subjectStyle(subject.subject).emoji} {subjectStyle(subject.subject).name}</span>
          <span class="count">
            {#if subject.missing_count}{subject.missing_count} {subject.missing_count === 1 ? 'Seite' : 'Seiten'} fehlen{/if}
            {#if subject.missing_count && subject.pending} · {/if}
            {#if subject.pending}{subject.pending} unterwegs{/if}
          </span>
        </summary>
        {#if subject.digital}<p class="muted">{subject.digital} Buchseiten liegen digital vor.</p>{/if}
        {#if subject.pending}<p class="muted">Buchseiten, die ich noch hole: {subject.pending_pages.join(', ')}.</p>{/if}
        {#each subject.chapters ?? [] as chapter}
          <p class="muted">{chapter.part_label ? `${chapter.part_label}, ` : ''}Kapitel {chapter.number} {chapter.title} (S. {chapter.start_page}{chapter.end_page ? `–${chapter.end_page}` : ''}):
            {chapter.pages_stored} von {chapter.pages} Seiten da{#if chapter.companions?.length}, dazu {chapter.companions.map((c) => c.title).join(', ')}{/if}{#if chapter.inferred}; aus dem Stundenthema erschlossen, nicht aus einer Seitenangabe{/if}.</p>
        {/each}
        {#each subject.missing as need}
          <div class="need">
            <p class="what"><strong>{need.label} {need.pages_label}</strong>
              <span class="muted">· {REASON_HINT[need.reason] ?? KIND_HINT[need.kind] ?? need.kind}</span></p>
            <!-- Checkliste mit Auto-Bezug: Eintrag antippen, Foto oder Datei
                 wählen, und die Stelle ist belegt. -->
            <ul class="checklist">
              {#each need.items as item (item.page)}
                <li>
                  <span class="box" aria-hidden="true"></span>
                  <span class="entry">
                    <strong>{item.page ? `${need.label} ${item.label}` : need.label}</strong>
                    <small class="muted">„{item.quote}" · {new Date(item.date).toLocaleDateString('de-DE')}</small>
                  </span>
                  <span class="take">
                    <button class="quiet" disabled={busy || uploading > 0} onclick={() => photoFor(subject.subject, need, item, true)} aria-label={`${need.label} ${item.label} fotografieren`}>📷</button>
                    <button class="quiet" disabled={busy || uploading > 0} onclick={() => photoFor(subject.subject, need, item, false)} aria-label={`Datei für ${need.label} ${item.label} wählen`}>📎</button>
                  </span>
                </li>
              {/each}
            </ul>
          </div>
        {/each}
      </details>
    {/each}
    {#if ledger.books?.length}
      <p class="muted foot">Bücher:
        {#each ledger.books as book, i}{i ? ' · ' : ''}{subjectStyle(book.subject).name}, {book.title}: {book.pages_stored} {book.pages_stored === 1 ? 'Seite' : 'Seiten'} gespeichert{#if book.units?.length}, Verzeichnis mit {book.units.filter((u) => u.kind === 'chapter').length} Kapiteln{/if}{#if book.access} ({ACCESS_NAMES[book.access.status] ?? book.access.status}){/if}{/each}
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
    <p class="muted foot">Die Zuordnung der Kürzel ist eine Annahme aus dem Wortlaut: „TB" als Textband, „BB" als Begleitband, „AH" und „cda" als Arbeitsheft.
      Wo im Text kein Buchteil steht, nehme ich zuerst das Schulbuch an und prüfe die Seite am Inhalt.</p>
  </details>
{/if}

{#snippet materialRow(m)}
  <button class="item" class:active={open?.id === m.id} onclick={() => act(() => (open?.id === m.id ? (open = null, form = null) : show(m)))}>
    {#if m.mime_type?.startsWith('image/')}
      <img src={`.${base}/${m.id}/file`} alt="" loading="lazy" />
    {:else}
      <span class="doc" aria-hidden="true">📄</span>
    {/if}
    <span class="text">
      <strong>{m.title || 'Ohne Titel'}</strong>
      <small>{[KIND_NAMES[m.kind] ?? m.kind, dateOf(m)].filter(Boolean).join(' · ')}</small>
      {#if m.summary}<small class="dim">{m.summary}</small>{/if}
    </span>
    <span class="state" class:warn={m.analysis_state === 'failed' && m.analysis_error !== '429'} class:wait={m.analysis_error === '429'}>
      {m.analysis_state === 'ready' && !m.verified && data.can_manage
        ? 'bitte prüfen'
        : m.analysis_state === 'failed' && m.analysis_error === '429' ? 'wartet auf KI-Rahmen'
        : STATE_NAMES[m.analysis_state] ?? ''}
    </span>
  </button>
  {#if open?.id === m.id}
    <!-- Das Detail steht direkt unter der Zeile, nicht am Seitenende. -->
    {@render materialDetail()}
  {/if}
{/snippet}

{#snippet materialDetail()}
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
          <label class="grow">Fach
            <select bind:value={form.subject_name}>
              <option value="">ohne Fach</option>
              {#if form.subject_name && !subjectOptions.some((s) => s.value === form.subject_name)}
                <option value={form.subject_name}>{form.subject_name} (nicht im Stundenplan)</option>
              {/if}
              {#each subjectOptions as s}<option value={s.value}>{s.label}</option>{/each}
            </select>
          </label>
          <label>Art
            <select bind:value={form.kind}>
              {#each data.kinds as k}<option value={k}>{KIND_NAMES[k] ?? k}</option>{/each}
            </select>
          </label>
          <label>Datum<input type="date" bind:value={form.document_date} /></label>
        </div>
        <div class="row gap-sm">
          <label>Buchteil
            <select bind:value={form.source_label}>
              <option value="">unbekannt</option>
              {#each BOOK_PARTS as part}<option value={part}>{part}</option>{/each}
            </select>
          </label>
          <label>Gedruckte Seite<input type="number" min="1" max="1999" bind:value={form.source_page} placeholder="keine" /></label>
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
{/snippet}

{#if data}
  <div class="row gap-sm filters">
    <label>Fach
      <select bind:value={filterSubject}>
        <option value="">alle</option>
        {#each subjectOptions as s}<option value={s.value}>{s.label}</option>{/each}
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
  {#if waitingBudget}
    <p class="muted">{waitingBudget} {waitingBudget === 1 ? 'Seite wartet' : 'Seiten warten'} auf den KI-Rahmen und werden im nächsten Lauf gelesen.</p>
  {/if}

  <!-- Je Fach eine aufklappbare Gruppe: Fotos und Scans direkt, Buchseiten je Buch
       darunter noch einmal eingeklappt. Sonst ist es eine Tapete. -->
  <div class="groups">
    {#each groups as group (group.subject)}
      <details class="card group" open={groups.length === 1 || !!filterSubject || group.subject === openSubject}>
        <summary>
          <span class="name">{subjectStyle(group.subject).emoji} {group.subject ? subjectStyle(group.subject).name : 'Ohne Fach'}</span>
          <span class="count">{group.items.length + group.bookPages.length} {group.items.length + group.bookPages.length === 1 ? 'Eintrag' : 'Einträge'}{#if group.waiting} · {group.waiting} warten{/if}</span>
        </summary>
        <div class="list">
          {#each group.items as m (m.id)}{@render materialRow(m)}{/each}
          {#each group.books as book (book.title)}
            <details class="book" open={book.pages.some((m) => m.id === open?.id)}>
              <summary><span class="name">📘 {book.short}</span><span class="count">{book.pages.length} {book.pages.length === 1 ? 'Seite' : 'Seiten'}</span></summary>
              {#each book.pages as m (m.id)}{@render materialRow(m)}{/each}
            </details>
          {/each}
        </div>
      </details>
    {:else}
      <p class="empty">Noch nichts abgelegt. Das erste Foto genügt.</p>
    {/each}
  </div>
  {#if data.has_more}
    <button class="quiet more" disabled={busy} onclick={() => act(() => load(true))}>Mehr laden</button>
  {/if}
{/if}

<style>
  .wanted{border-left:4px solid var(--accent)}
  .wanted>summary{cursor:pointer;min-height:44px;display:flex;align-items:center;list-style:none}
  .wanted>summary::-webkit-details-marker{display:none}
  .options label{display:grid;gap:2px;font-size:0.85rem;color:var(--fg-muted)}
  .options select,.options input{min-height:40px}
  .options input[type=number]{width:7rem}
  .wanted .subject{border:1px solid var(--border);border-radius:10px;padding:8px 10px;margin:8px 0}
  .wanted .subject>summary{cursor:pointer;min-height:40px;display:flex;justify-content:space-between;align-items:center;gap:12px;list-style:none}
  .wanted .subject>summary::-webkit-details-marker{display:none}
  .wanted .name{font-weight:550}
  .wanted .count{color:var(--fg-muted);font-size:.9rem;white-space:nowrap}
  .need{padding:8px 0;border-top:1px solid var(--border)}
  .need .what{margin:0 0 4px}
  .need .quote{margin:0 0 4px;font-style:italic;overflow-wrap:anywhere}
  .checklist{list-style:none;margin:4px 0 0;padding:0;display:grid;gap:2px}
  .checklist li{display:grid;grid-template-columns:1.4rem minmax(0,1fr) auto;align-items:center;gap:6px;min-height:44px}
  .checklist .box{width:18px;height:18px;border:2px solid var(--fg-muted);border-radius:5px}
  .checklist .entry{display:grid;min-width:0}
  .checklist .entry small{overflow-wrap:anywhere}
  .checklist .take{display:flex;gap:2px}
  .checklist .take button{min-width:44px;min-height:44px;font-size:1.2rem}
  .wanted .foot{margin-top:12px}

  .head h1 { margin: 0; font-size: 1.3rem; }
  .drop { margin-top: 0.6rem; }
  .lead { margin: 0 0 0.7rem; }
  .big { font-size: 1.05rem; padding: 0.7rem 1rem; }
  .hidden-input { display: none; }
  .filters { flex-wrap: wrap; margin-top: 0.8rem; align-items: flex-end; }
  .filters label { margin: 0; }
  .grow { flex: 1 1 10rem; }
  .list { margin-top: 0.4rem; display: grid; gap: 0.4rem; }
  .groups { margin-top: 0.6rem; display: grid; gap: 0.5rem; }
  .group > summary, .book > summary { cursor: pointer; min-height: 44px; display: flex; justify-content: space-between; align-items: center; gap: 12px; list-style: none; }
  .group > summary::-webkit-details-marker, .book > summary::-webkit-details-marker { display: none; }
  .group .name { font-weight: 600; }
  .group .count, .book .count { color: var(--fg-muted); font-size: .9rem; white-space: nowrap; }
  .book { border: 1px solid var(--border); border-radius: 10px; padding: 4px 10px; }
  .book > summary { min-height: 40px; }
  .item.active { outline: 2px solid var(--accent); }
  .state.wait { color: var(--warm, #b26a00); }
  .more { margin: 0.6rem auto; display: block; min-height: 44px; }
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
  .detail { margin: 0.2rem 0 0.6rem; }
  .detail h2 { margin: 0; font-size: 1.1rem; }
  @media (max-width: 560px) {
    .item { grid-template-columns: 2.6rem minmax(0, 1fr); }
    .state { grid-column: 2; }
  }
</style>
