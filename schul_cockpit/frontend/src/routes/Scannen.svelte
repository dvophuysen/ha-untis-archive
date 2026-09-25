<script>
  // Scannen (D183): jederzeit etwas einlesen. Kind, Art und optional Fach
  // wählen, Fotos aufnehmen; abgelegt wird über denselben Weg wie in den
  // Materialien (uploadMaterial), gelesen wird danach wie dort.
  import { api } from '../lib/api.js';
  import { appState, setActiveAccount } from '../lib/store.svelte.js';
  import { uploadMaterial } from '../lib/materialUpload.js';
  import { subjectStyle } from '../lib/subjectStyle.js';
  import { formatShortDate } from '../lib/format.js';
  import { todo, loadTodo, forgetTodo } from '../lib/parentTodo.svelte.js';
  import KidChips from '../lib/KidChips.svelte';
  import TodoSource from '../lib/TodoSource.svelte';
  import { onMount } from 'svelte';

  const KINDS = [
    { key: 'book_page', label: 'Buchseite', fields: { kind: 'book_page' } },
    { key: 'worksheet', label: 'Arbeitsblatt', fields: { kind: 'worksheet' } },
    { key: 'exam_notice', label: 'Themenzettel', fields: { kind: 'exam_notice' } },
    // Eine Wortseite erkennt die Lesung am Titel und zerlegt sie in Lernwörter.
    { key: 'vocab', label: 'Vokabelliste', fields: { kind: 'other', title: 'Vokabelliste' } },
    { key: 'graded', label: 'Korrigierte Arbeit zurück', fields: { kind: 'exam', title: 'Korrigierte Arbeit' } },
    // Ohne Art erkennt die Lesung selbst, was es ist.
    { key: 'other', label: 'Sonstiges', fields: {} },
  ];

  const query = new URLSearchParams(window.location.hash.split('?')[1] || '');
  // svelte-ignore state_referenced_locally
  let kid = $state(Number(query.get('acc')) || appState.activeAccountId);
  let art = $state(KINDS.some((k) => k.key === query.get('art')) ? query.get('art') : 'other');
  let subject = $state(query.get('fach') || '');
  let subjects = $state([]), exams = $state(null), examKey = $state(''), grade = $state('');
  let uploading = $state(0), saved = $state([]), message = $state(''), error = $state(''), busy = $state(false);
  let camera = $state(null), picker = $state(null);

  onMount(() => { loadTodo(); });

  let request = 0;
  $effect(() => {
    const id = kid, ticket = ++request;
    if (!id) return;
    subjects = []; exams = null;
    api.get(`/api/accounts/${id}/subjects`).then((r) => { if (ticket === request) subjects = r.subjects ?? []; }).catch(() => {});
  });
  // Für eine korrigierte Arbeit: die Arbeiten der letzten Wochen zur Auswahl.
  $effect(() => {
    const id = kid;
    if (art !== 'graded' || !id || exams) return;
    api.get(`/api/accounts/${id}/exams/all`).then((r) => { if (id === kid) exams = r; }).catch(() => { exams = { past: [], grade_options: [] }; });
  });

  const kidName = $derived(appState.me?.accounts?.find((a) => a.id === kid)?.name ?? '');
  const kind = $derived(KINDS.find((k) => k.key === art));
  const subjectOptions = $derived.by(() => {
    const seen = new Map();
    for (const s of subjects) if (s.untis_name) seen.set(s.untis_name, s.name);
    if (subject && !seen.has(subject)) seen.set(subject, subjectStyle(subject).name);
    return [...seen.entries()].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label, 'de'));
  });
  const recent = $derived((exams?.past ?? []).slice(0, 8));
  const exam = $derived(recent.find((e) => e.exam_key === examKey) ?? null);
  // Vorschläge aus „Erledigen“: was gerade fehlt, als Abkürzung.
  const suggestions = $derived((todo.data?.kids ?? []).flatMap((k) => k.items.filter((it) => it.action.page === 'scannen').map((it) => ({ ...it, name: k.name }))));

  function pickKid(id) { kid = id; setActiveAccount(id); examKey = ''; exams = null; }
  function useSuggestion(it) {
    const q = it.action.query ?? {};
    if (q.acc) pickKid(Number(q.acc));
    if (q.art) art = q.art;
    subject = q.fach ?? '';
    message = ''; saved = [];
  }

  async function send(files) {
    const list = [...(files ?? [])];
    if (!list.length || !kid) return;
    busy = true; error = ''; message = ''; saved = [];
    uploading = list.length;
    const fields = { ...kind.fields, subject_name: exam?.subject_name || subject };
    let done = 0;
    for (const file of list) {
      try {
        const r = await uploadMaterial(kid, file, fields);
        saved = [...saved, { id: r?.id, name: file.name, duplicate: !!r?.duplicate_of, blurry: !!r?.blurry }];
        done++;
      } catch (e) { error = e.message; }
      uploading -= 1;
    }
    if (art === 'graded' && exam && grade !== '') {
      try {
        await api.post(`/api/accounts/${kid}/exam-progress`, { exam_key: exam.exam_key, grade_points: Number(grade) });
      } catch (e) { error = e.message; }
    }
    busy = false;
    if (done) {
      forgetTodo();
      message = `${done === 1 ? 'Eine Seite' : `${done} Seiten`} für ${kidName} gespeichert. Die App liest sie gerade.`;
    }
  }
</script>

<header class="head"><h2>Scannen</h2><p>Einlesen, was gerade da ist. Die App liest es selbst.</p></header>

{#if suggestions.length}
  <section class="sug" aria-label="Vorgeschlagen">
    <h3>Vorgeschlagen: was gerade fehlt</h3>
    {#each suggestions as it (it.account_id + it.key)}
      <button class="sug-item" onclick={() => useSuggestion(it)}><b>{it.title}</b><small>{it.name} · {it.reason_plain ?? it.reason}</small></button>
      <TodoSource {it} />
    {/each}
  </section>
{/if}

<section class="card step">
  <span class="lbl">Für</span>
  <KidChips label="Kind" value={kid} onpick={pickKid} />
  {#if (appState.me?.accounts?.length ?? 0) <= 1}<p class="one">{kidName}</p>{/if}
  <span class="lbl">Was</span>
  <div class="chips" role="group" aria-label="Art">
    {#each KINDS as k (k.key)}<button class="chip" aria-pressed={art === k.key} onclick={() => (art = k.key)}>{k.label}</button>{/each}
  </div>
  {#if art === 'graded'}
    <label>Welche Arbeit
      <select bind:value={examKey}>
        <option value="">{exams ? 'Arbeit wählen (optional)' : 'lade …'}</option>
        {#each recent as e (e.exam_key)}<option value={e.exam_key}>{subjectStyle(e.subject_name ?? e.title).name} · {formatShortDate(e.date)}</option>{/each}
      </select>
    </label>
    {#if exam}
      <label>Note (optional)
        <select bind:value={grade}>
          <option value="">– keine –</option>
          {#each exams?.grade_options ?? [] as o (o.points)}<option value={String(o.points)}>{o.label}</option>{/each}
        </select>
      </label>
    {/if}
  {/if}
  {#if art !== 'graded' || !exam}
    <label>Fach (optional)
      <select bind:value={subject}>
        <option value="">erkennt die App</option>
        {#each subjectOptions as s (s.value)}<option value={s.value}>{s.label}</option>{/each}
      </select>
    </label>
  {/if}
  <div class="row gap-sm actions">
    <button class="primary big" disabled={busy || !kid} onclick={() => camera?.click()}>Fotos aufnehmen</button>
    <button disabled={busy || !kid} onclick={() => picker?.click()}>Datei wählen (auch PDF)</button>
  </div>
  <input bind:this={camera} class="hidden-input" type="file" accept="image/*" capture="environment" multiple
         aria-label="Fotos aufnehmen" onchange={(e) => send(e.currentTarget.files).then(() => (e.target.value = ''))} />
  <input bind:this={picker} class="hidden-input" type="file" accept="image/png,image/jpeg,image/webp,application/pdf" multiple
         aria-label="Datei wählen" onchange={(e) => send(e.currentTarget.files).then(() => (e.target.value = ''))} />
  {#if uploading > 0}<p role="status">Noch {uploading} wird gespeichert …</p>{/if}
  {#if message}<div class="banner" role="status">{message}</div>{/if}
  {#each saved.filter((s) => s.duplicate || s.blurry) as s (s.id)}
    <p class="note">{s.name}: {s.duplicate ? 'Diese Seite lag schon vor; das neue Foto wird trotzdem gelesen.' : 'wirkt unscharf; ein neues Foto bei gutem Licht liest sich besser.'}</p>
  {/each}
  {#if saved.length}<a class="to-list" href={`#/materialien/${encodeURIComponent(exam?.subject_name || subject || '')}`}>In den Materialien ansehen</a>{/if}
  {#if error}<div class="error-box" role="alert">{error}</div>{/if}
</section>

<style>
  .head h2 { margin: 0; font-size: var(--fs-xl); }
  .head p { margin: 2px 0 var(--sp-3); color: var(--fg-muted); font-size: var(--fs-sm); }
  .sug { background: var(--warm-soft); border-radius: var(--r-md); padding: var(--sp-2) var(--sp-3); margin-bottom: var(--sp-3); }
  .sug h3 { margin: var(--sp-1) 0; font-size: var(--fs-xs); letter-spacing: .04em; text-transform: uppercase; color: var(--fg-muted); }
  .sug-item { display: block; width: 100%; text-align: left; background: transparent; border: 0; border-top: 1px solid var(--border); border-radius: 0; padding: var(--sp-2) 0; min-height: 48px; color: var(--fg); }
  h3 + .sug-item { border-top: 0; }
  .sug-item b { display: block; font-size: var(--fs-sm); }
  .sug-item small { display: block; font-size: var(--fs-xs); color: var(--fg-muted); overflow-wrap: anywhere; }
  .step { display: grid; gap: var(--sp-2); }
  .lbl { font-size: var(--fs-xs); color: var(--fg-muted); font-weight: 700; }
  .one { margin: 0; font-weight: 600; }
  .chips { display: flex; flex-wrap: wrap; gap: var(--sp-2); }
  .chip { min-height: 40px; padding: 6px 14px; border-radius: var(--r-pill); font-size: var(--fs-sm); background: var(--bg-card); border: 1px solid var(--border); color: var(--fg); }
  .chip[aria-pressed="true"] { background: var(--accent); color: var(--accent-fg); border-color: var(--accent); font-weight: 700; }
  .actions { flex-wrap: wrap; margin-top: var(--sp-2); }
  .hidden-input { display: none; }
  .note { font-size: var(--fs-xs); color: var(--warn-fg); margin: 0; }
  .to-list { font-size: var(--fs-sm); }
  :global(.step .kid-chips) { margin: 0; }
</style>
