<script>
  import ActionLabel from './ActionLabel.svelte';
  import {subjectStyle} from './subjectStyle.js';
  import { api, ApiError } from './api.js';
  import { isoToday, daysBetween, dueLabel, stripUntisMetadata } from './format.js';
  import SourceText from './SourceText.svelte';

  let { accountId, task, onchange = () => {}, onopen = null } = $props();

  let busy = $state(false);
  let error = $state(null);

  const today = isoToday();
  const dueDays = $derived(task.due_date ? daysBetween(today, task.due_date) : null);
  const isOverdue = $derived(dueDays !== null && dueDays < 0 && task.status !== 'done');
  const isDueTodayOrTomorrow = $derived(
    dueDays !== null && dueDays >= 0 && dueDays <= 1 && task.status !== 'done',
  );
  const isExam = $derived(task.task_type === 'exam_prep');
  const cleanNotes = $derived(stripUntisMetadata(task.notes));
  // Sofort sichtbarer Haken (D177), ohne task.status vorzeitig zu ändern:
  // Die Startseite sortiert erledigte Zeilen weg, ein Fehler wäre sonst unsichtbar.
  let shown = $state(null);
  const isDone = $derived(shown ?? task.status === 'done');

  // Stop the toggle click from bubbling into the body's "open detail" handler.
  async function toggle(ev) {
    ev.stopPropagation();
    ev.preventDefault();
    if (busy) return;
    busy = true;
    error = null;
    const newStatus = isDone ? 'open' : 'done';
    shown = newStatus === 'done';
    try {
      await api.patch(`/api/tasks/${task.id}`, { status: newStatus });
      task.status = newStatus;
      shown = null;
      onchange();
    } catch (e) {
      shown = null;
      error = e instanceof ApiError ? e.message : 'Speichern fehlgeschlagen';
    } finally {
      busy = false;
    }
  }

  function openDetail() {
    onopen?.(task);
  }
  function onBodyKey(ev) {
    if (ev.key === 'Enter' || ev.key === ' ') {
      ev.preventDefault();
      openDetail();
    }
  }
</script>

<div class="task-row" class:is-done={isDone}>
  <button
    type="button"
    class="check"
    class:checked={isDone}
    disabled={busy}
    aria-label={isDone ? 'Wieder als offen markieren' : 'Als erledigt markieren'}
    aria-pressed={isDone}
    onclick={toggle}
  >
    {#if isDone}<span class="tick">✓</span>{/if}
  </button>

  <div
    class="body"
    role="button"
    tabindex="0"
    onclick={openDetail}
    onkeydown={onBodyKey}
  >
    <div class="head">
      <span class="title" class:done={isDone}>{subjectStyle(task.subject_name || task.title).emoji}
        {#if task.source_state}<span class="dot {task.source_state}" title={task.source_state === 'ready' ? 'Material liegt vor' : task.source_state === 'pending' ? 'Material wird geholt' : 'Material fehlt'}></span>{/if}
        <SourceText segments={task.title_segments} text={task.title} subject={task.subject_name} taskId={task.id} /></span>

    </div>
    {#if cleanNotes}
      <div class="notes" class:done={isDone}><SourceText segments={task.title_segments ? null : task.text_segments} text={cleanNotes} subject={task.subject_name} taskId={task.id} /></div>
    {/if}
    {#if task.subitems && task.subitems.length > 0}
      <div class="dim sub">
        ☑ {task.subitems.filter((s) => s.done).length}/{task.subitems.length} Teilaufgaben
      </div>
    {/if}
    {#if isExam || task.task_type === 'catch_up' || task.task_type === 'practice'}
      <div class="meta">
        {#if isExam}<span class="pill exam">📝 Klausur</span>{/if}
        {#if task.task_type === 'catch_up'}<span class="pill">↺ nachholen</span>{/if}
        {#if task.task_type === 'practice'}<span class="pill">üben</span>{/if}
      </div>
    {/if}
    {#if error}<div class="row-error">{error}</div>{/if}
  </div>
  <div class="row-actions">      {#if task.due_date}
        <span class="due" class:overdue={isOverdue} class:soon={isDueTodayOrTomorrow}>
          {dueLabel(task.due_date, today)}
        </span>
      {/if}
  {#if !isDone}<a class="practice-link" aria-label={`Hilfe bei ${task.title}`} title="Dabei brauche ich Hilfe" href={`#/learning?help=${task.id}`}><ActionLabel kind="chat" label="Hilfe" /></a>{/if}
  </div>
</div>

<style>
  .row-actions{display:flex;flex-direction:column;align-items:flex-end;gap:0;width:5.5rem;flex-shrink:0}

  .practice-link{align-self:flex-end;display:flex;align-items:center;justify-content:flex-end;padding:4px 0;min-height:44px;box-sizing:border-box;color:var(--accent);flex-shrink:0}
  .task-row {
    display: flex;
    align-items: flex-start;
    gap: 0.35rem;
    padding: 0.55rem 0;
    border-bottom: 1px solid var(--border);
  }
  .task-row:last-child { border-bottom: none; }
  .task-row.is-done { opacity: 0.7; }

  /* Checkbox: a real button, large enough for a thumb, with a clearly
     visible affordance both empty and ticked. */
  .check {
    flex-shrink: 0;
    width: 44px;
    height: 44px;
    min-height: 44px;
    margin-top: 2px;
    padding: 0;
    border-radius: 8px;
    border: 0;
    position: relative;
    background: transparent;
    color: #fff;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 80ms ease, background 120ms ease, border-color 120ms ease;
  }
  .check:active { transform: scale(0.92); }
  .check::before{content:"";position:absolute;width:24px;height:24px;border:2px solid var(--fg-muted);border-radius:6px;background:var(--bg-card)}
  .check.checked::before{background:var(--rating-3);border-color:var(--rating-3)}
  .check .tick {
    position:relative;z-index:1;
    font-size: 1.1rem;
    line-height: 1;
    font-weight: bold;
  }

  .body {
    flex: 1;
    min-width: 0;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }
  .body:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: 6px;
  }

  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .title {
    font-weight: 600;
    color: var(--fg);
  }
  .title.done { text-decoration: line-through; color: var(--fg-dim); }
  .dot { display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 50%; margin: 0 2px 1px 0; vertical-align: middle; }
  .dot.ready { background: var(--rating-3); }
  .dot.pending { background: var(--warm, #b26a00); }
  .dot.missing { background: var(--rating-1); }
  .notes {
    font-size: 0.85rem;
    color: var(--fg-muted);
    margin-top: 2px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .notes.done { text-decoration: line-through; color: var(--fg-dim); }
  .sub { font-size: 0.75rem; margin-top: 2px; }
  .meta { margin-top: 4px; display: flex; gap: 0.4rem; flex-wrap: wrap; }
  .due {
    flex-shrink: 0;
    font-size: 0.75rem;
    padding: 2px 0;
    border-radius: 4px;
    background: transparent;
    color: var(--fg-muted);
    border: 0;
    white-space: nowrap;
  }
  .due.overdue { background: var(--rating-1); color: #fff; padding:2px 5px; }
  .due.soon { background: var(--warm-soft); color:var(--fg); padding:2px 5px; }
  .row-error {
    color: var(--bad-fg);
    font-size: 0.75rem;
    margin-top: 4px;
  }
</style>
