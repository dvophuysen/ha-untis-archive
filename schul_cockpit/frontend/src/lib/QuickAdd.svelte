<script>
  // Selbst eintragen (D174): Text zuerst, Fach und Termin als Vorschlag zum
  // Antippen, Foto nur als Alternative mit Hinweis auf Kosten.
  import { api, ApiError } from './api.js';
  import { subjectStyle } from './subjectStyle.js';
  import { formatShortDate, daysBetween } from './format.js';
  import { held } from './dayPhase.js';

  let { accountId, day, lessons = [], defaultSubject = null, nextBySubject = {}, nextSchoolDay = null,
        startOpen = false, onsaved = () => {} } = $props();

  // svelte-ignore state_referenced_locally
  let open = $state(startOpen);
  let text = $state(''), kind = $state('homework'), subject = $state(null), due = $state(undefined);
  let busy = $state(false), error = $state(''), fileInput = $state(null), input = $state(null);

  const todaySubjects = $derived([...new Set(lessons.filter(held).map((l) => l.subject_name).filter(Boolean))]);
  const chosen = $derived(subject === null ? defaultSubject : subject);
  function dayWord(iso) {
    if (!iso) return '';
    const d = daysBetween(day, iso);
    return d === 0 ? 'heute' : d === 1 ? 'morgen' : formatShortDate(iso);
  }
  const dueOptions = $derived.by(() => {
    const opts = [];
    const next = kind === 'homework' && chosen ? nextBySubject[chosen] : null;
    if (next) opts.push({ value: next, label: `${dayWord(next)} · nächste Stunde` });
    if (kind === 'reminder') opts.push({ value: day, label: 'heute' });
    if (nextSchoolDay && nextSchoolDay !== next) opts.push({ value: nextSchoolDay, label: dayWord(nextSchoolDay) });
    opts.push({ value: null, label: 'kein Termin' });
    return opts;
  });
  const dueValue = $derived(due === undefined ? dueOptions[0]?.value ?? null : due);

  function reset() { text = ''; subject = null; due = undefined; kind = 'homework'; }
  async function save() {
    const title = text.trim();
    if (!title) { error = 'Schreib kurz, was zu tun ist.'; input?.focus(); return; }
    busy = true; error = '';
    try {
      await api.post(`/api/accounts/${accountId}/tasks`, {
        title, task_type: kind,
        subject_name: kind === 'homework' ? (chosen || null) : null,
        due_date: dueValue,
      });
      reset();
      open = startOpen;
      onsaved(kind === 'reminder' ? 'Erinnerung eingetragen.' : 'Aufgabe eingetragen.');
    } catch (e) {
      error = e instanceof ApiError ? e.message : 'Nicht gespeichert. Bitte noch einmal versuchen.';
    } finally { busy = false; }
  }
  async function photo(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    busy = true; error = '';
    try {
      const body = new FormData();
      body.append('file', file);
      await api.post(`/api/accounts/${accountId}/afternoon-check/photo`, body);
      onsaved('Foto gespeichert. Fach und Termin kommen gleich dazu.');
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Foto nicht gespeichert.';
    } finally { busy = false; }
  }
  function openNow() { open = true; queueMicrotask(() => input?.focus()); }
</script>

{#if !open}
  <button class="qa-open" onclick={openNow}><span aria-hidden="true">＋</span> Aufgabe oder Erinnerung eintragen</button>
{:else}
  <form class="qa" onsubmit={(e) => { e.preventDefault(); save(); }}>
    <div class="qa-top">
      <input bind:this={input} bind:value={text} placeholder={kind === 'reminder' ? 'Woran erinnern? Zum Beispiel Elternbrief abgeben' : 'Was ist zu tun?'} aria-label="Was ist zu tun?" autocomplete="off" enterkeyhint="done" />
      <button class="primary qa-add" type="submit" disabled={busy} aria-label="Eintragen">＋</button>
    </div>
    <div class="chips" role="group" aria-label="Art">
      <button type="button" aria-pressed={kind === 'homework'} onclick={() => { kind = 'homework'; due = undefined; }}>Hausaufgabe</button>
      <button type="button" aria-pressed={kind === 'reminder'} onclick={() => { kind = 'reminder'; due = undefined; }}>Erinnerung</button>
    </div>
    {#if kind === 'homework'}
      <div class="chips" role="group" aria-label="Fach">
        {#each todaySubjects as s (s)}
          <button type="button" aria-pressed={chosen === s} onclick={() => { subject = s; due = undefined; }}>{subjectStyle(s).emoji} {subjectStyle(s).name}{s === defaultSubject ? ' · gerade' : ''}</button>
        {/each}
        <button type="button" aria-pressed={chosen === '' } onclick={() => { subject = ''; due = undefined; }}>anderes</button>
      </div>
      {#if chosen === ''}
        <select aria-label="Fach wählen" onchange={(e) => { subject = e.currentTarget.value; due = undefined; }}>
          <option value="">Fach wählen</option>
          {#each Object.keys(nextBySubject).filter((s) => !todaySubjects.includes(s)) as s (s)}<option value={s}>{subjectStyle(s).name}</option>{/each}
        </select>
      {/if}
    {/if}
    <div class="chips" role="group" aria-label="Bis wann">
      {#each dueOptions as o (o.label)}<button type="button" aria-pressed={dueValue === o.value} onclick={() => (due = o.value)}>{o.label}</button>{/each}
    </div>
    <button type="button" class="qa-photo" disabled={busy} onclick={() => fileInput?.click()}><b>📷 Foto statt Text</b> · dauert länger und kostet KI-Guthaben</button>
    <input bind:this={fileInput} type="file" accept="image/*,application/pdf" capture="environment" hidden onchange={photo} />
    {#if error}<p class="error-box" role="alert">{error}</p>{/if}
  </form>
{/if}

<style>
  .qa-open{width:100%;display:flex;gap:var(--sp-2);align-items:center;background:var(--bg-card);border:1px dashed var(--accent);color:var(--accent);font-weight:700;border-radius:var(--r-md);min-height:46px;margin-bottom:var(--sp-2)}
  .qa{display:grid;gap:var(--sp-2);background:var(--bg-card);border:2px solid var(--accent);border-radius:var(--r-md);padding:var(--sp-3);margin-bottom:var(--sp-3)}
  .qa-top{display:flex;gap:var(--sp-2)}
  .qa-top input{flex:1;min-width:0}
  .qa-add{min-width:48px;font-size:1.2rem;font-weight:700;padding:0}
  .chips{display:flex;flex-wrap:wrap;gap:6px}
  .chips button{font-size:var(--fs-xs);font-weight:650;min-height:34px;padding:4px 10px;border-radius:var(--r-pill);background:var(--bg)}
  .chips button[aria-pressed="true"]{background:color-mix(in oklab,var(--accent) 16%,var(--bg-card));border-color:var(--accent)}
  .qa-photo{justify-self:start;background:none;border:0;padding:2px 0;min-height:30px;font-size:var(--fs-xs);color:var(--fg-muted);text-align:left}
  .qa-photo b{color:var(--accent)}
</style>
