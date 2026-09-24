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
    own_work: 'Aufgabenbearbeitung',
    exam: 'Klassenarbeit',
    handout: 'Merkblatt',
    exam_notice: 'Offizielle Themenliste (Arbeit)',
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
  // Startwert aus der Adresse; danach wählt die Seite selbst.
  // svelte-ignore state_referenced_locally
  let filterSubject = $state(initialSubject);
  let filterKind = $state('');
  let search = $state('');
  let picker = $state(null);
  let ledger = $state(null);
  let camera = $state(null);
  // Welches Foto gerade groß ist und wo der ganze Text statt des Auszugs steht.
  let big = $state(null);
  let whole = $state(new Set());
  // Was in den Eingabefeldern der Zweifelsstellen steht. Vorbelegt ist der
  // Vorschlag der Lesung, sonst das Gelesene: Beides lässt sich überschreiben,
  // ohne dafür das große Korrekturformular zu öffnen.
  let edits = $state({});
  const doubtKey = (id, d) => `${id}\u0000${d.text}`;
  const draft = (id, d) => edits[doubtKey(id, d)] ?? (d.alternative || d.text);
  let timer = null;

  const base = $derived(`/api/accounts/${accountId}/materials`);
  // Zweifel je Seitenangabe bündeln: nur Seiten mit Vorschlag, ein Knopf je Angabe.
  function doubtGroups(unknown) {
    const groups = new Map();
    for (const u of unknown.filter((x) => x.suggest)) {
      const g = groups.get(u.span) ?? { span: u.span, label: u.label, fixes: [] };
      g.fixes.push({ label: u.label, page: u.page, suggest: u.suggest });
      groups.set(u.span, g);
    }
    return [...groups.values()];
  }
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
  // Verzeichnisfotos, die noch nicht gegengelesen sind, je Buch gebündelt.
  const tocGroups = $derived.by(() => {
    const groups = new Map();
    for (const m of data?.materials ?? []) {
      if (!m.needs_review || m.kind !== 'toc') continue;
      const key = `${m.subject_name ?? ''}|${m.source_label ?? ''}`;
      if (!groups.has(key)) {
        const book = (ledger?.books ?? []).find((b) => b.subject === (m.subject_name ?? '').toLowerCase() && (b.part_label === m.source_label || (!b.part_label && !m.source_label)));
        groups.set(key, { key, subject: m.subject_name ?? '', label: m.source_label ?? '', items: [], book });
      }
      groups.get(key).items.push(m);
    }
    return [...groups.values()];
  });
  // „Kapitel prüfen“ führt zum Buch weiter unten auf derselben Seite. Ein
  // href="#buecher" ginge nicht: Der Router liest jeden Hash als Seitennamen
  // und landete bei „Unbekannte Seite“. Deshalb selbst aufklappen und hinscrollen.
  const bookAnchor = (book) => 'buch-' + `${book?.subject ?? ''}-${book?.title ?? ''}`.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  function showChapters(book) {
    const el = document.getElementById(book ? bookAnchor(book) : 'buecher');
    if (!el) {
      message = 'Die Kapitelliste steht erst bereit, wenn das Verzeichnis fertig gelesen ist.';
      return;
    }
    // Der Bücher-Block steckt in „Was mir noch fehlt“. Ein zugeklapptes
    // <details> blendet seinen Inhalt aus, und auf etwas Ausgeblendetes läuft
    // scrollIntoView ins Leere: Es passiert sichtbar gar nichts. Deshalb erst
    // alle umschließenden Klappen öffnen, dann springen.
    for (let node = el; node; node = node.parentElement?.closest('details')) node.open = true;
    requestAnimationFrame(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  }
  // Kapitel eines Buchs berichtigen: Anfangs- oder Endseite.
  async function fixChapter(unit, field, value) {
    const page = Number(value);
    if (!Number.isFinite(page)) return;
    await api.patch(`${base}/sources/chapters/${unit.id}`, { [field]: page });
    message = 'Kapitel berichtigt. Die Stellen sind neu gebunden.';
    await load();
  }
  // Hinweise zu eben abgelegten Fotos: Duplikat einer vorhandenen Seite oder unscharf.
  let notices = $state([]);
  async function dropNotice(notice, deleteIt) {
    if (deleteIt) await api.delete(`${base}/${notice.id}`);
    notices = notices.filter((n) => n !== notice);
    await load();
  }
  // Was das nächste Foto ist, wenn man es vorher sagen will; sonst erkenne ich es selbst.
  let upload = $state({ subject: '', kind: '', part: '', page: '' });
  let collecting = $state(null);
  // Der Sammellauf startet von selbst bei neuen Quellen; hier steht, was zuletzt lief.
  let auto = $state(null);
  async function loadAuto() {
    try { auto = (await api.get(`${base}/sources/collect`)).auto ?? null; } catch { auto = null; }
  }
  $effect(() => { void accountId; loadAuto(); });
  function autoWhen(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return `${d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' })} ${d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}`;
  }

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
      await load(); await loadAuto();
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
      for (const b of g.books) b.pages.sort((a, c) => firstPage(a) - firstPage(c));
      // Fotos mit Buchteil und Seite stehen nach Buchteil und Seitenzahl, alles
      // andere nach Datum, neueste zuerst.
      g.items.sort((a, c) => {
        const pa = firstPage(a), pc = firstPage(c);
        const la = a.source_label || '', lc = c.source_label || '';
        if (pa !== Infinity && pc !== Infinity) return la.localeCompare(lc, 'de') || pa - pc;
        if (pa !== Infinity) return -1;
        if (pc !== Infinity) return 1;
        return (c.document_date || c.created_at || '').localeCompare(a.document_date || a.created_at || '');
      });
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

  // Zu einer Hausaufgabe: was schon dranhängt und was dazu passen könnte.
  // Bisher konnte man hier nur Neues ablegen, ein bereits eingelesenes Material
  // ließ sich nicht auswählen (D106).
  let forTask = $state(null);
  async function loadForTask() {
    if (!taskId) { forTask = null; return; }
    try { forTask = await api.get(`${base}/for-task/${taskId}`); }
    catch { forTask = null; }
  }
  async function attach(id) {
    await api.post(`${base}/${id}/links`, { kind: 'task', target_id: taskId });
    await loadForTask(); await load();
  }
  async function detach(id) {
    await api.delete(`${base}/${id}/links?kind=task&target_id=${taskId}`);
    await loadForTask(); await load();
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

  $effect(() => { void accountId; void taskId; loadForTask(); });

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
    // Bei einer Stelle ohne Buchteil bekommt das Foto das vermutete Buch mit.
    // Ein Blatt (Seite 0) bekommt seinen Eintrag mit, nie das Fach allein.
    claim = { subject, label: need.guess || need.label, page: item.page, entry_kind: item.entry_kind, entry_id: item.entry_id };
    (viaCamera ? camera : picker)?.click();
  }
  // Blätter des Fachs, die einem Eintrag „Arbeitsblatt“ zugeordnet werden können.
  function sheetsOf(subject) {
    return (data?.materials ?? []).filter((m) => ['worksheet', 'handout'].includes(m.kind) && (m.subject_name ?? '').toLowerCase() === (subject ?? '').toLowerCase());
  }
  async function assignSheet(materialId, entryKind, entryId, quote) {
    await api.post(`${base}/${materialId}/links`, { kind: entryKind, target_id: entryId, relation: 'blatt' });
    message = `Blatt zugeordnet: „${quote}“.`;
    await load();
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
        if (!target.page && target.entry_kind === 'homework' && target.entry_id) body.append('homework_id', String(target.entry_id));
        if (!target.page && target.entry_kind === 'lesson' && target.entry_id) body.append('lesson_id', String(target.entry_id));
      } else {
        if (upload.subject || filterSubject) body.append('subject_name', upload.subject || filterSubject);
        if (upload.kind) body.append('kind', upload.kind);
        if (upload.part) body.append('source_label', upload.part);
        if (upload.page) body.append('source_page', String(Number(upload.page)));
      }
      if (taskId) body.append('task_id', String(taskId));
      try {
        const saved = await api.post(base, body);
        // Dieselbe Seite schon da oder das Foto unscharf: sofort sagen, nicht
        // erst nach der Lesung.
        if (saved?.duplicate_of) notices = [...notices, { id: saved.id, kind: 'duplicate', of: saved.duplicate_of }];
        else if (saved?.blurry) notices = [...notices, { id: saved.id, kind: 'blurry' }];
      } catch (e) {
        error = e.message;
      }
      uploading -= 1;
    }
    message = target
      ? `${target.label} ${target.page ? `S. ${target.page}` : ''} abgehakt. Ich lese es gerade.`
      : upload.kind === 'toc' ? 'Inhaltsverzeichnis gespeichert. Ich lese die Kapitel daraus, sobald alle Seiten da sind.'
      : upload.kind === 'exam_notice' ? 'Offizielle Themenliste gespeichert. Jedes Thema kommt mit seinen Stellen auf die Liste und wird vorgezogen.'
      : list.length === 1 ? 'Gespeichert. Ich lese es gerade.' : `${list.length} Seiten gespeichert.`;
    upload.page = '';
    await load();
  }

  function dateOf(m) {
    const value = m.document_date || m.created_at?.slice(0, 10);
    return value ? new Date(value).toLocaleDateString('de-DE') : '';
  }
  // Welche Seite eines Buchs das ist: gedruckte Seitenzahlen zuerst, sonst die
  // erkannte Seite. Eine Doppelseite heißt „S. 48–49“.
  function pagesOf(m) {
    let printed = [];
    try { printed = (Array.isArray(m.printed_pages) ? m.printed_pages : JSON.parse(m.printed_pages || '[]')).map(Number).filter(Boolean); } catch { printed = []; }
    const all = [...new Set([...(m.source_page ? [Number(m.source_page)] : []), ...printed])].sort((a, b) => a - b);
    return all;
  }
  function pageLabel(m) {
    const pages = pagesOf(m);
    if (!pages.length) return '';
    if (pages.length === 2 && pages[1] === pages[0] + 1) return `S. ${pages[0]}–${pages[1]}`;
    return `S. ${pages.join(', ')}`;
  }
  function placeOf(m) {
    const book = m.origin === 'book_fetch' ? shortBook(m.source_book) : (m.source_label || '');
    const page = pageLabel(m);
    return [book, page].filter(Boolean).join(' ');
  }
  function firstPage(m) { return pagesOf(m)[0] ?? Infinity; }

  async function show(m, jump = false) {
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
          pages: pagesOf(open).join('–'),
        }
      : null;
    // Aus der Gegenlese-Karte heraus steht das Formular weit unten in der
    // Liste. Ungesehen geöffnet sieht es aus, als sei nichts passiert.
    if (jump) requestAnimationFrame(() => document.getElementById(`material-${m.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
  }

  async function save() {
    // Eine leere Seite heißt „keine Seite"; 0 räumt sie serverseitig aus.
    // Nur schicken, was sich gegenüber dem Material geändert hat: Jedes gesendete Feld gilt als Korrektur und wird gesperrt.
    // „10“, „10-11“, „10/11“ oder „10, 11“: die erste Seite ist die Seite des Materials, alle sind die gedruckten Seiten.
    const pages = [...new Set(String(form.pages ?? '').split(/[^0-9]+/).filter(Boolean).map(Number).filter((n) => n > 0 && n < 2000))].sort((a, b) => a - b);
    const { pages: _pages, ...rest } = form;
    const wanted = { ...rest, source_page: pages[0] ?? 0 };
    const patch = Object.fromEntries(Object.entries(wanted).filter(([k, v]) => String(v ?? '') !== String(open[k] ?? (k === 'source_page' ? 0 : ''))));
    if (pages.join(',') !== pagesOf(open).join(',')) patch.printed_pages = pages;
    open = await api.patch(`${base}/${open.id}`, patch);
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
    Die offizielle Themenliste der Lehrkraft für eine Arbeit (Tafelabschrift, Zettel oder Nachricht) oder das Inhaltsverzeichnis eines Buchs, das nur auf Papier existiert, sagst du mir vorher.</p>
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
  {#each notices as notice (notice.id)}
    <div class="banner notice-row">
      {#if notice.kind === 'duplicate'}
        <span>Diese Seite liegt schon vor: „{notice.of.title}“{notice.of.source_label ? ` (${notice.of.source_label}${notice.of.source_page ? ` S. ${notice.of.source_page}` : ''})` : ''}. Das neue Foto wird trotzdem gelesen.</span>
        <span class="row gap-sm"><button class="quiet" disabled={busy} onclick={() => act(() => dropNotice(notice, true))}>Neues Foto löschen</button><button class="quiet" disabled={busy} onclick={() => act(() => dropNotice(notice, false))}>Beide behalten</button></span>
      {:else}
        <span>Das Foto wirkt unscharf. Ich lese es, aber ein neues Foto bei gutem Licht liest sich besser.</span>
        <span class="row gap-sm"><button class="quiet" disabled={busy} onclick={() => act(() => dropNotice(notice, true))}>Löschen und neu aufnehmen</button><button class="quiet" disabled={busy} onclick={() => act(() => dropNotice(notice, false))}>Behalten</button></span>
      {/if}
    </div>
  {/each}
  {#if message}<div class="banner">{message}</div>{/if}
  {#if error}<div class="error-box">{error}</div>{/if}
</div>

<!-- Lesungen mit Folgen gegenlesen: Eine Themenliste bindet Stellen, ein Verzeichnis
     Kapitel. Bis ein Elternteil bestätigt, steht die Lesung hier zur Kontrolle. -->
{#if data?.can_manage && (data.materials ?? []).some((m) => m.needs_review)}
  <div class="card review">
    <strong>Bitte gegenlesen</strong>
    <p class="lead">Gezeigt wird nur, wo ich beim Lesen unsicher war — <mark>markiert</mark>, mit einer Zeile Zusammenhang.
      Sauber Gelesenes steht nicht hier. Themenlisten und Inhaltsverzeichnisse zeige ich immer, weil daraus Stellen und Kapitel entstehen.</p>
    {#each (data.materials ?? []).filter((m) => m.needs_review && m.kind !== 'toc') as m (m.id)}
      <div class="review-item">
        <div><strong>{m.title || 'Ohne Titel'}</strong> <small class="muted">· {KIND_NAMES[m.kind] ?? m.kind}{m.subject_name ? ` · ${subjectStyle(m.subject_name).name}` : ''}{m.source_label ? ` · ${m.source_label}` : ''}</small></div>
        <!-- Ohne die Quelle daneben lässt sich nichts gegenlesen. Ein Tipp aufs
             Foto macht es groß, ein zweiter wieder klein. -->
        {#if m.mime_type?.startsWith('image/')}
          <button class="shot" class:big={big === m.id} onclick={() => (big = big === m.id ? null : m.id)}>
            <img src={`.${base}/${m.id}/file`} alt="Foto der Seite" loading="lazy" />
            <span class="hint">{big === m.id ? 'kleiner' : 'größer'}</span>
          </button>
        {:else if m.filename}
          <a href={`.${base}/${m.id}/file`} target="_blank" rel="noreferrer">{m.filename} öffnen</a>
        {/if}
        <!-- Gezeigt wird, was zu prüfen ist: die unsicheren Stellen mit einer
             Zeile Zusammenhang. Der Rest steht auf Tipp bereit (D118). -->
        {#if m.review?.segments?.length && !whole.has(m.id)}
          <p class="preserve reading">{#each m.review.segments as seg, i (i)}{#if seg.kind === 'gap'}<button class="gap" onclick={() => (whole = new Set([...whole, m.id]))}>[…] {seg.lines} Zeilen</button>{:else if seg.kind === 'mark'}<mark class:flagged={seg.source === 'read'} title={seg.reason}>{seg.text}</mark>{:else}{seg.text}{/if}{/each}</p>
        {:else}
          <p class="preserve reading">{m.content_text || m.summary || '(kein Text erkannt)'}</p>
        {/if}
        {#if m.review?.shortened && !whole.has(m.id)}
          <button class="quiet" onclick={() => (whole = new Set([...whole, m.id]))}>Ganzen Text zeigen</button>
        {/if}
        <!-- Was die Lesung selbst gemeldet hat: hier steht der Vorschlag zum
             Antippen, statt dass jemand jedes Zeichen vergleicht. -->
        {#each m.doubts ?? [] as d (d.text)}
          <div class="doubt-row">
            <span>⚠ „{d.text}“{d.reason ? ` · ${d.reason}` : ''}</span>
          </div>
          <!-- Berichtigt wird an Ort und Stelle: Das Feld steht schon auf dem
               Vorschlag und lässt sich vor dem Übernehmen ändern. -->
          <div class="doubt-fix">
            <input value={draft(m.id, d)} disabled={busy} aria-label="So heißt die Stelle richtig"
                   oninput={(e) => (edits = { ...edits, [doubtKey(m.id, d)]: e.currentTarget.value })} />
            <button class="primary" disabled={busy} onclick={() => act(async () => {
              const wanted = draft(m.id, d);
              await api.post(`${base}/${m.id}/doubts/resolve`, { text: d.text, replace: wanted });
              const { [doubtKey(m.id, d)]: _gone, ...rest } = edits; edits = rest;
              message = wanted === d.text ? 'Danke, so bleibt es.' : `Gelesen als „${wanted}“.`;
              await load();
            })}>Übernehmen</button>
            <button class="quiet" disabled={busy} onclick={() => act(async () => {
              await api.post(`${base}/${m.id}/doubts/resolve`, { text: d.text, replace: null });
              const { [doubtKey(m.id, d)]: _gone, ...rest } = edits; edits = rest;
              await load();
            })}>Stimmt so</button>
          </div>
        {/each}
        {#each m.review?.loose ?? [] as d (d.text)}
          <p class="muted">⚠ Unsicher gelesen: „{d.text}“{d.reason ? ` · ${d.reason}` : ''} — die Stelle steht nicht mehr so im Text.</p>
        {/each}
        {#if m.plausibility?.checked}
          {#if m.plausibility.unknown.length}
            <!-- Handschrift: die 1 dieses Kindes sieht aus wie eine 7. Der Unterricht kennt die richtigen Stellen. -->
            <ul class="doubts">
              {#each m.plausibility.unknown as u}
                <li>⚠ {u.label} S. {u.page} kommt im Unterricht nicht vor{#if u.suggest} · gemeint S. {u.suggest}?{/if}</li>
              {/each}
            </ul>
            <!-- Eine Seitenangabe („S. 70, 71“) wird als Ganzes berichtigt: ein Tipp, beide Seiten. -->
            <div class="row gap-sm">
              {#each doubtGroups(m.plausibility.unknown) as g (g.span)}
                <button class="quiet" disabled={busy} onclick={() => act(async () => { await api.post(`${base}/${m.id}/plausibility/apply`, { fixes: g.fixes }); message = `Übernommen: ${g.label} S. ${g.fixes.map((f) => f.suggest).join(', ')}. Die Stellen werden neu gebunden.`; await load(); })}>So korrigieren: {g.label} S. {g.fixes.map((f) => f.suggest).join(', ')}</button>
              {/each}
            </div>
            <p class="muted">Bitte am Foto prüfen. „So korrigieren“ übernimmt den Vorschlag als Korrektur; alles andere über „Korrigieren“.</p>
          {:else if m.plausibility.cited}
            <p class="muted">✓ Alle {m.plausibility.cited} Stellen kommen so im Unterricht vor.</p>
          {/if}
        {/if}
        <div class="row gap-sm">
          <button class="primary" disabled={busy} onclick={() => act(async () => { await api.post(`${base}/${m.id}/verified`, { value: true }); message = 'Danke, so gelesen bleibt es.'; await load(); })}>✓ Stimmt so</button>
          <button disabled={busy} onclick={() => act(() => show(m, true))}>Korrigieren</button>
        </div>
      </div>
    {/each}
    <!-- Ein Verzeichnis besteht aus mehreren Fotos; gegengelesen wird das
         Ergebnis je Buch, die Kapitel stehen zum Berichtigen darunter. -->
    {#each tocGroups as group (group.key)}
      <div class="review-item">
        <div><strong>Inhaltsverzeichnis {group.label}</strong> <small class="muted">· {subjectStyle(group.subject).name} · {group.items.length} {group.items.length === 1 ? 'Foto' : 'Fotos'}</small></div>
        <div class="shots">
          {#each group.items.filter((i) => i.mime_type?.startsWith('image/')) as i (i.id)}
            <button class="shot" class:big={big === i.id} onclick={() => (big = big === i.id ? null : i.id)}>
              <img src={`.${base}/${i.id}/file`} alt="Foto des Verzeichnisses" loading="lazy" />
              <span class="hint">{big === i.id ? 'kleiner' : 'größer'}</span>
            </button>
          {/each}
        </div>
        {#if group.book}
          <p class="muted">Gelesen: {group.book.units.filter((u) => u.kind === 'chapter').length} Kapitel. Stimmen die Anfangsseiten? Unten bei den Büchern lässt sich jede Seite berichtigen.</p>
        {:else}
          <p class="muted">Das Verzeichnis wird gerade gelesen oder konnte nicht gelesen werden.</p>
        {/if}
        <div class="row gap-sm">
          <button class="primary" disabled={busy} onclick={() => act(async () => { for (const m of group.items) await api.post(`${base}/${m.id}/verified`, { value: true }); message = 'Danke, das Verzeichnis gilt.'; await load(); })}>✓ Stimmt so</button>
          <button class="quiet" onclick={() => showChapters(group.book)}>Kapitel prüfen</button>
        </div>
      </div>
    {/each}
  </div>
{/if}

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
              <span class="muted">· {need.guess ? `vermutlich ${need.guess}` : REASON_HINT[need.reason] ?? KIND_HINT[need.kind] ?? need.kind}</span></p>
            <!-- Checkliste mit Auto-Bezug: Eintrag antippen, Foto oder Datei
                 wählen, und die Stelle ist belegt. -->
            <ul class="checklist">
              {#each need.items as item (`${item.page}-${item.entry_kind}-${item.entry_id}`)}
                <li>
                  <span class="box" aria-hidden="true"></span>
                  <span class="entry">
                    <strong>{item.page ? `${need.label} ${item.label}` : need.label}</strong>
                    <small class="muted">„{item.quote}" · {new Date(item.date).toLocaleDateString('de-DE')}</small>
                    {#if !item.page && sheetsOf(subject.subject).length}
                      <!-- Ein schon fotografiertes Blatt zuordnen statt neu fotografieren (D85). -->
                      <select class="assign" disabled={busy} aria-label="Vorhandenes Blatt zuordnen" onchange={(e) => { const id = Number(e.currentTarget.value); e.currentTarget.value = ''; if (id) act(() => assignSheet(id, item.entry_kind, item.entry_id, item.quote)); }}>
                        <option value="">Vorhandenes Blatt zuordnen …</option>
                        {#each sheetsOf(subject.subject) as sheet (sheet.id)}<option value={sheet.id}>{sheet.title || 'Ohne Titel'} · {dateOf(sheet)}</option>{/each}
                      </select>
                    {/if}
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
      <div class="books" id="buecher">
        <p class="muted foot">Bücher</p>
        {#each ledger.books as book (book.title)}
          <details class="book" id={bookAnchor(book)}>
            <summary>{subjectStyle(book.subject).name}, {book.title}: {book.pages_stored} {book.pages_stored === 1 ? 'Seite' : 'Seiten'} gespeichert{#if book.units?.length}, Verzeichnis mit {book.units.filter((u) => u.kind === 'chapter').length} Kapiteln{/if}{#if book.access} ({ACCESS_NAMES[book.access.status] ?? book.access.status}){/if}</summary>
            {#if book.units?.length}
              <!-- Anfangs- und Endseite je Kapitel; eine Korrektur bleibt gesperrt gegen jedes neue Lesen. -->
              <table class="units">
                <tbody>
                  {#each book.units as unit (unit.id)}
                    <tr class:locked={unit.locked} class:sub={unit.level > 1}>
                      <td class="num">{unit.number}</td>
                      <td class="title">{unit.title}{#if unit.kind !== 'chapter'}<small class="muted"> · {unit.kind === 'appendix' ? 'Anhang' : unit.kind === 'vocab' ? 'Vokabeln' : 'Grammatik'}</small>{/if}</td>
                      {#if data?.can_manage}
                        <td><input type="number" min="1" max="1999" value={unit.start_page} aria-label="Anfangsseite" onchange={(e) => act(() => fixChapter(unit, 'start_page', e.currentTarget.value))} /></td>
                        <td><input type="number" min="0" max="1999" value={unit.end_page ?? ''} placeholder="–" aria-label="Endseite" onchange={(e) => act(() => fixChapter(unit, 'end_page', e.currentTarget.value || 0))} /></td>
                      {:else}
                        <td colspan="2">S. {unit.start_page}{unit.end_page ? `–${unit.end_page}` : ''}</td>
                      {/if}
                    </tr>
                  {/each}
                </tbody>
              </table>
            {:else if book.access?.toc_state === 'reading'}
              <p class="muted">Das Verzeichnis wird gerade gelesen.</p>
            {:else}
              <p class="muted">Kein Verzeichnis gelesen. Fotografiere die Inhaltsseiten mit „Was ist es?“ = Inhaltsverzeichnis und dem Buchteil, dann lese ich es daraus.</p>
            {/if}
          </details>
        {/each}
      </div>
    {/if}
    {#if data?.can_manage}
      <p class="muted foot">Der Sammellauf startet von selbst, sobald neue Untis-Einträge, Fotos, Aufgaben oder Bücher dazukommen (kurze Sammelfrist, damit mehrere Fotos ein Lauf sind). Zusätzlich nachts um zwei und um vierzehn Uhr als Netz.
        {#if auto?.pending} Vorgemerkt: läuft um {autoWhen(auto.pending.due)} ({auto.pending.reasons.join(', ')}).{/if}
        {#if auto?.last} Zuletzt automatisch {autoWhen(auto.last.at)} ({auto.last.reasons.join(', ')}){#if auto.last.result}: {auto.last.result.stored ?? 0} Seiten abgelegt, {auto.last.result.verified ?? 0} bestätigt{#if auto.last.result.skipped}, {auto.last.result.skipped}{/if}{/if}{#if auto.last.error}: {auto.last.error}{/if}.{/if}</p>
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
  <button id={`material-${m.id}`} class="item" class:active={open?.id === m.id} onclick={() => act(() => (open?.id === m.id ? (open = null, form = null) : show(m)))}>
    {#if m.mime_type?.startsWith('image/')}
      <img src={`.${base}/${m.id}/file`} alt="" loading="lazy" />
    {:else}
      <span class="doc" aria-hidden="true">📄</span>
    {/if}
    <span class="text">
      <strong>{m.title || 'Ohne Titel'}</strong>
      <small>{#if placeOf(m)}<b class="place">{placeOf(m)}</b> · {/if}{[placeOf(m) && ['workbook', 'book_page', 'worksheet'].includes(m.kind) ? '' : (KIND_NAMES[m.kind] ?? m.kind), dateOf(m), m.blurry ? 'unscharf' : ''].filter(Boolean).join(' · ')}</small>
      {#if m.summary}<small class="dim">{m.summary}</small>{/if}
    </span>
    <span class="state" class:warn={m.analysis_state === 'failed' && m.analysis_error !== '429'} class:wait={m.analysis_error === '429'}>
      {m.analysis_state === 'ready' && !m.verified && data.can_manage
        ? 'bitte prüfen'
        : m.analysis_state === 'failed' && m.analysis_error === '429' ? 'wartet auf KI-Rahmen'
        : STATE_NAMES[m.analysis_state] ?? ''}
    </span>
  </button>
  {#if m.sheet_candidates?.length}
    <!-- Loses Blatt: zu welchem Eintrag gehört es? Ein Tipp ordnet zu, nichts wird geraten (D85). -->
    <div class="candidates">
      <span class="muted">{m.sheet_label ? `${m.sheet_label} – gehört zu …` : 'Gehört das Blatt zu …'}</span>
      {#each m.sheet_candidates as c (`${c.kind}-${c.id}`)}
        <button class="quiet" disabled={busy} onclick={() => act(() => assignSheet(m.id, c.kind, c.id, c.quote))}>{c.kind === 'homework' ? 'Hausaufgabe' : 'Stunde'} {new Date(c.date).toLocaleDateString('de-DE')}: „{c.quote.length > 60 ? c.quote.slice(0, 60) + '…' : c.quote}“</button>
      {/each}
    </div>
    <!-- Die Auswertung hat das Blatt gesehen und nennt ihren Beleg dafür; der
         Vorschlag steht oben in der Liste, zugeordnet wird trotzdem per Tipp. -->
    {#each m.sheet_candidates.filter((c) => c.reason) as c (`grund-${c.kind}-${c.id}`)}
      <p class="muted">Spricht dafür: {c.reason}</p>
    {/each}
  {/if}
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
          <label>Gedruckte Seite(n)<input inputmode="numeric" bind:value={form.pages} placeholder="keine, z. B. 10 oder 10-11" /></label>
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
    <section class="card">
      <h2>Schon Abgelegtes anhängen</h2>
      {#if forTask?.linked?.length}
        <p class="muted">Gehört bereits dazu:</p>
        <div class="list">
          {#each forTask.linked as m (m.id)}
            <div class="row gap-sm attach">
              <span class="grow">{m.title || KIND_NAMES[m.kind] || 'Material'}{m.source_label ? ` · ${m.source_label}` : ''}{m.source_page ? ` S. ${m.source_page}` : ''}</span>
              <button disabled={busy} onclick={() => act(() => detach(m.id))}>Entfernen</button>
            </div>
          {/each}
        </div>
      {/if}
      {#if forTask?.candidates?.length}
        <p class="muted">Vorschläge aus {subjectStyle(forTask.subject).name}, beste Treffer zuerst:</p>
        <div class="list">
          {#each forTask.candidates as c (c.material_id)}
            <div class="row gap-sm attach">
              <span class="grow">{c.title || KIND_NAMES[c.kind] || 'Material'}<small>{c.reason}</small></span>
              <button disabled={busy} onclick={() => act(() => attach(c.material_id))}>Anhängen</button>
            </div>
          {/each}
        </div>
      {:else if forTask && !forTask.linked?.length}
        <p class="muted">Zu diesem Fach liegt noch nichts Passendes ab. Fotografiere die Seite oder das Blatt.</p>
      {/if}
    </section>
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
  .doubts { margin: 4px 0 6px; padding-left: 18px; color: var(--bad-fg); font-weight: 600; line-height: 1.4; }
  .candidates { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 0 0 8px 8px; font-size: 0.85rem; }
  .candidates button { min-height: 36px; padding: 4px 10px; text-align: left; }
  .assign { display: block; margin-top: 4px; max-width: 100%; font-size: 0.85rem; }
  .place { font-weight: 650; color: var(--fg); }
  .wanted{border-left:4px solid var(--accent)}
  .wanted>summary{cursor:pointer;min-height:44px;display:flex;align-items:center;list-style:none}
  .wanted>summary::-webkit-details-marker{display:none}
  .review{border-left:4px solid var(--warm,#b26a00)}
  .notice-row{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;justify-content:space-between}
  .books .book{border-top:1px solid var(--border);padding:6px 0}
  .books .book>summary{cursor:pointer;min-height:40px;display:flex;align-items:center;font-size:0.9rem}
  .units{width:100%;border-collapse:collapse;font-size:0.85rem}
  .units td{padding:2px 4px;vertical-align:middle}
  .units .num{width:3rem;color:var(--fg-muted)}
  .units tr.sub .title{padding-left:1rem}
  .units tr.locked .title::after{content:" ✎";color:var(--fg-muted)}
  .units input{width:4.5rem;min-height:36px}
  .review-item{border-top:1px solid var(--border);padding:8px 0}
  .review-item .preserve{white-space:pre-wrap;margin:4px 0 8px}
  /* Das Foto der Seite: klein als Beleg, auf Tipp so groß wie der Platz hergibt. */
  .shot{display:block;padding:0;border:1px solid var(--border);border-radius:8px;overflow:hidden;background:none;position:relative;margin:6px 0}
  .shot img{display:block;width:100%;max-height:11rem;object-fit:cover;object-position:top}
  .shot.big img{max-height:none;object-fit:contain}
  .shot .hint{position:absolute;right:6px;bottom:6px;background:rgba(0,0,0,.62);color:#fff;border-radius:6px;padding:2px 8px;font-size:0.78rem}
  .shots{display:flex;flex-wrap:wrap;gap:8px}
  .shots .shot{flex:1 1 9rem;max-width:100%}
  /* Der Auszug: die unsichere Stelle fällt ins Auge, die Lücke ist antippbar. */
  .reading mark{background:var(--warm-soft,#ffe9c2);color:inherit;border-radius:4px;padding:0 2px}
  .reading mark.flagged{background:var(--rating-1-soft,#ffd4d4);box-shadow:inset 0 -2px 0 var(--rating-1)}
  .reading .gap{display:inline;padding:0 6px;min-height:0;border:1px dashed var(--border);border-radius:6px;background:none;color:var(--fg-muted);font-size:0.85rem}
  .doubt-row{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;margin:2px 0 6px;font-size:0.9rem}
  .doubt-row>span{color:var(--bad-fg);font-weight:600}
  .doubt-fix{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 10px}
  .doubt-fix input{flex:1 1 14rem;min-width:0;min-height:40px;margin:0}
  .doubt-fix button{min-height:40px;padding:4px 12px}
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
