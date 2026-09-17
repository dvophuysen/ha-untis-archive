<script>
  // Die Hausaufgabe: oben die Fakten, dann der Auftrag mit seinen Quellen,
  // die Einstiegshilfe, das Material als Vorschau, der Weg in den Hilfe-Chat.
  // Kein Formular. Eigene Aufgaben lassen sich dahinter bearbeiten.
  import { api, ApiError } from './api.js';
  import { subjectStyle } from './subjectStyle.js';
  import { formatShortDate, isoToday, dueLabel, stripUntisMetadata } from './format.js';
  import SourceText from './SourceText.svelte';
  import TaskEditor from './TaskEditor.svelte';
  import ActionLabel from './ActionLabel.svelte';

  let { accountId, task, onclose, onsaved = () => {} } = $props();

  let busy = $state(false);
  let error = $state(null);
  let editing = $state(false);
  let zoom = $state(null);

  const today = isoToday();
  const isDone = $derived(task.status === 'done');
  const fromUntis = $derived(task.source === 'ha_todo');
  const notes = $derived(stripUntisMetadata(task.notes));
  const given = $derived.by(() => {
    const m = (task.notes ?? '').match(/Gegeben am:?\s*(?:[A-Za-zÄÖÜäöü]{2,4}\.?\s*)?(\d{1,2})\.(\d{1,2})\.(\d{2,4})?/);
    if (!m) return null;
    const year = m[3] ? (m[3].length === 2 ? `20${m[3]}` : m[3]) : (task.due_date ?? today).slice(0, 4);
    return `${year}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
  });
  const STATE_TEXT = {
    ready: 'Material liegt vor und ist gelesen',
    pending: 'Material wird gerade geholt oder gelesen',
    missing: 'Material fehlt noch, bitte fotografieren',
  };
  const base = $derived(`/api/accounts/${accountId}/materials`);

  async function toggle() {
    if (busy) return;
    busy = true;
    error = null;
    try {
      const status = isDone ? 'open' : 'done';
      await api.patch(`/api/tasks/${task.id}`, { status });
      task.status = status;
      onsaved();
    } catch (e) {
      error = e instanceof ApiError ? e.message : 'Speichern fehlgeschlagen';
    } finally {
      busy = false;
    }
  }
</script>

<div class="modal-backdrop" onclick={onclose} role="presentation">
  <div class="modal task-detail" onclick={(e) => e.stopPropagation()} role="dialog" aria-label="Hausaufgabe">
    <div class="row between head">
      <h2>{subjectStyle(task.subject_name || task.title).emoji} {task.subject_name || 'Aufgabe'}</h2>
      <button class="ghost" onclick={onclose} aria-label="Schließen">✕</button>
    </div>

    <dl class="facts">
      {#if given}<dt>Gestellt</dt><dd>{formatShortDate(given)}</dd>{/if}
      {#if task.due_date}<dt>Fällig</dt><dd class:overdue={task.due_date < today && !isDone}>{formatShortDate(task.due_date)} · {dueLabel(task.due_date, today)}</dd>{/if}
      <dt>Herkunft</dt><dd>{fromUntis ? 'Untis' : 'selbst angelegt'}</dd>
      <dt>Stand</dt><dd>{isDone ? 'erledigt' : 'offen'}{#if task.source_state} · <span class="state {task.source_state}">{STATE_TEXT[task.source_state]}</span>{/if}</dd>
    </dl>

    <!-- Aus Untis steht der Auftrag in den Notizen, der Titel ist nur das Fach. -->
    <p class="assignment"><SourceText segments={task.text_segments} text={task.text || notes || task.title} subject={task.subject_name} taskId={task.id} /></p>
    {#if !task.text && notes && notes !== task.title}<p class="notes">{notes}</p>{/if}

    {#if task.intro}
      <div class="intro">
        <strong>Einstieg</strong>
        <p>{task.intro}</p>
      </div>
    {/if}

    {#if task.materials?.length}
      <div class="thumbs">
        {#each task.materials as m (m.id)}
          <button class="thumb" onclick={() => (zoom = m)} title={m.title}>
            {#if m.mime_type?.startsWith('image/')}
              <img src={`.${base}/${m.id}/file`} alt={m.title} loading="lazy" />
            {:else}
              <span class="doc" aria-hidden="true">📄</span>
            {/if}
            <span class="caption">{m.title}</span>
          </button>
        {/each}
      </div>
    {/if}

    {#if error}<div class="error-box">{error}</div>{/if}

    <div class="actions">
      {#if !isDone}
        <a class="primary help" href={`#/learning?help=${task.id}`} onclick={onclose}><ActionLabel kind="chat" label="Hilfe im Chat" /></a>
        <!-- Kontrollieren: die fertige Lösung vom Foto prüfen lassen, ohne Vorsagen. -->
        <a class="help" href={`#/learning?check=${task.id}`} onclick={onclose}><ActionLabel kind="chat" label="Lösung prüfen lassen" /></a>
      {/if}
      <button disabled={busy} onclick={toggle}>{isDone ? 'Wieder öffnen' : 'Erledigt'}</button>
      <a class="quiet" href={`#/materialien/${encodeURIComponent(task.subject_name ?? '')}/${task.id}`} onclick={onclose}>Foto anhängen</a>
      {#if !fromUntis}<button class="quiet" onclick={() => (editing = true)}>Bearbeiten</button>{/if}
    </div>
  </div>
</div>

{#if zoom}
  <div class="lightbox" onclick={() => (zoom = null)} role="presentation">
    {#if zoom.mime_type?.startsWith('image/')}
      <img src={`.${base}/${zoom.id}/file`} alt={zoom.title} />
    {/if}
    <div class="lightbox-bar">
      <span>{zoom.title}</span>
      <a href={`#/materialien?material=${zoom.id}`} onclick={onclose}>Zum Material</a>
    </div>
  </div>
{/if}

{#if editing}
  <TaskEditor {accountId} {task} onclose={() => (editing = false)} onsaved={() => { onsaved(); onclose?.(); }} />
{/if}

<style>
  .task-detail { max-width: 34rem; }
  .head h2 { margin: 0; font-size: 1.1rem; }
  .facts { display: grid; grid-template-columns: auto 1fr; gap: 0.15rem 0.8rem; margin: 0.6rem 0; font-size: 0.9rem; }
  .facts dt { color: var(--fg-muted); }
  .facts dd { margin: 0; }
  .facts .overdue { color: var(--rating-1); font-weight: 600; }
  .state.ready { color: var(--rating-3); }
  .state.pending { color: var(--warm, #b26a00); }
  .state.missing { color: var(--rating-1); }
  .assignment { font-size: 1.05rem; font-weight: 600; margin: 0.4rem 0; }
  .notes { color: var(--fg-muted); white-space: pre-wrap; overflow-wrap: anywhere; margin: 0 0 0.4rem; }
  .intro { border-left: 4px solid var(--accent); padding: 0.4rem 0.7rem; margin: 0.6rem 0; background: var(--accent-soft); border-radius: 0 8px 8px 0; }
  .intro p { margin: 0.2rem 0 0; }
  .thumbs { display: flex; gap: 0.5rem; flex-wrap: wrap; margin: 0.6rem 0; }
  .thumb { display: grid; gap: 2px; width: 6.2rem; padding: 0; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-card); overflow: hidden; cursor: pointer; }
  .thumb img { width: 100%; height: 5rem; object-fit: cover; object-position: top; }
  .thumb .doc { display: flex; align-items: center; justify-content: center; height: 5rem; font-size: 2rem; }
  .thumb .caption { font-size: 0.7rem; padding: 2px 4px 4px; color: var(--fg-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .actions { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; margin-top: 0.6rem; }
  .actions .help { display: inline-flex; align-items: center; padding: 0.5rem 0.8rem; border-radius: 8px; background: var(--accent); color: #fff; text-decoration: none; min-height: 44px; box-sizing: border-box; }
  .actions .quiet { background: transparent; border: 0; color: var(--accent); min-height: 44px; display: inline-flex; align-items: center; }
  .lightbox { position: fixed; inset: 0; background: rgba(0,0,0,.85); z-index: 60; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: env(safe-area-inset-top, 0) 0 env(safe-area-inset-bottom, 0); }
  .lightbox img { max-width: 100vw; max-height: 85vh; object-fit: contain; }
  .lightbox-bar { color: #fff; display: flex; gap: 1rem; padding: 0.6rem 1rem; }
  .lightbox-bar a { color: #fff; }
</style>
