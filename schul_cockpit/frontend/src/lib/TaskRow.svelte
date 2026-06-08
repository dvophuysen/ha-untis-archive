<script>
  import { api, ApiError } from './api.js';
  import { isoToday, daysBetween, dueLabel, stripUntisMetadata } from './format.js';

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
  const isDone = $derived(task.status === 'done');

  // Stop the toggle click from bubbling into the body's "open detail" handler.
  async function toggle(ev) {
    ev.stopPropagation();
    ev.preventDefault();
    if (busy) return;
    busy = true;
    error = null;
    const newStatus = isDone ? 'open' : 'done';
    // Optimistic update — flip the UI immediately so the tap feels instant.
    const prevStatus = task.status;
    task.status = newStatus;
    try {
      await api.patch(`/api/tasks/${task.id}`, { status: newStatus });
      onchange();
    } catch (e) {
      task.status = prevStatus;
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
      <span class="title" class:done={isDone}>{task.title}</span>
      {#if task.due_date}
        <span class="due" class:overdue={isOverdue} class:soon={isDueTodayOrTomorrow}>
          {dueLabel(task.due_date, today)}
        </span>
      {/if}
    </div>
    {#if cleanNotes}
      <div class="notes" class:done={isDone}>{cleanNotes}</div>
    {/if}
    {#if task.subitems && task.subitems.length > 0}
      <div class="dim sub">
        ☑ {task.subitems.filter((s) => s.done).length}/{task.subitems.length} Teilaufgaben
      </div>
    {/if}
    {#if isExam || task.task_type === 'catch_up' || task.task_type === 'practice' || task.estimated_minutes}
      <div class="meta">
        {#if isExam}<span class="pill exam">📝 Klausur</span>{/if}
        {#if task.task_type === 'catch_up'}<span class="pill">↺ nachholen</span>{/if}
        {#if task.task_type === 'practice'}<span class="pill">üben</span>{/if}
        {#if task.estimated_minutes}<span class="pill">⏱ {task.estimated_minutes} min</span>{/if}
      </div>
    {/if}
    {#if error}<div class="row-error">{error}</div>{/if}
  </div>
</div>

<style>
  .task-row {
    display: flex;
    align-items: flex-start;
    gap: 0.7rem;
    padding: 0.7rem 0.4rem 0.7rem 0.2rem;
    border-bottom: 1px solid var(--border);
  }
  .task-row:last-child { border-bottom: none; }
  .task-row.is-done { opacity: 0.7; }

  /* Checkbox: a real button, large enough for a thumb, with a clearly
     visible affordance both empty and ticked. */
  .check {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    min-height: 32px;
    margin-top: 2px;
    padding: 0;
    border-radius: 8px;
    border: 2px solid var(--fg-muted);
    background: var(--bg-card);
    color: #fff;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 80ms ease, background 120ms ease, border-color 120ms ease;
  }
  .check:active { transform: scale(0.92); }
  .check.checked {
    background: var(--rating-3);
    border-color: var(--rating-3);
  }
  .check .tick {
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
    gap: 0.5rem;
  }
  .title {
    font-weight: 600;
    color: var(--fg);
  }
  .title.done { text-decoration: line-through; color: var(--fg-dim); }
  .notes {
    font-size: 0.85rem;
    color: var(--fg-muted);
    margin-top: 2px;
    white-space: pre-wrap;
  }
  .notes.done { text-decoration: line-through; color: var(--fg-dim); }
  .sub { font-size: 0.75rem; margin-top: 2px; }
  .meta { margin-top: 4px; display: flex; gap: 0.4rem; flex-wrap: wrap; }
  .due {
    flex-shrink: 0;
    font-size: 0.75rem;
    padding: 0.15rem 0.45rem;
    border-radius: 999px;
    background: var(--bg-elevated);
    color: var(--fg-muted);
    border: 1px solid var(--border);
    white-space: nowrap;
  }
  .due.overdue { background: var(--rating-1); color: #fff; border-color: transparent; }
  .due.soon { background: var(--rating-2); color: #fff; border-color: transparent; }
  .row-error {
    color: var(--rating-1);
    font-size: 0.75rem;
    margin-top: 4px;
  }
</style>
