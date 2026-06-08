<script>
  import { api } from './api.js';
  import { isoToday, daysBetween, dueLabel, stripUntisMetadata } from './format.js';

  let { accountId, task, onchange = () => {}, onopen = null } = $props();

  let busy = $state(false);

  const today = isoToday();
  const dueDays = $derived(task.due_date ? daysBetween(today, task.due_date) : null);
  const isOverdue = $derived(dueDays !== null && dueDays < 0 && task.status !== 'done');
  const isDueTodayOrTomorrow = $derived(
    dueDays !== null && dueDays >= 0 && dueDays <= 1 && task.status !== 'done',
  );
  const isExam = $derived(task.task_type === 'exam_prep');
  const cleanNotes = $derived(stripUntisMetadata(task.notes));

  async function toggle() {
    busy = true;
    try {
      const newStatus = task.status === 'done' ? 'open' : 'done';
      await api.patch(`/api/tasks/${task.id}`, { status: newStatus });
      task.status = newStatus;
      onchange();
    } finally {
      busy = false;
    }
  }
</script>

<div class="task-row">
  <button
    class="task-checkbox"
    class:done={task.status === 'done'}
    disabled={busy}
    onclick={toggle}
    aria-label={task.status === 'done' ? 'Erledigt rückgängig' : 'Als erledigt markieren'}
  >{task.status === 'done' ? '✓' : ''}</button>

  <button
    class="task-body ghost"
    style="text-align:left; padding:0; min-height:auto; border:none;"
    onclick={() => onopen?.(task)}
  >
    <div class="task-row-head">
      <span class="task-title" class:done={task.status === 'done'}>{task.title}</span>
      {#if task.due_date}
        <span class="due-pill" class:overdue={isOverdue} class:soon={isDueTodayOrTomorrow}>
          {dueLabel(task.due_date, today)}
        </span>
      {/if}
    </div>
    {#if cleanNotes}
      <div class="muted" style="font-size:0.85rem; margin-top:2px; white-space:pre-wrap;">{cleanNotes}</div>
    {/if}
    {#if task.subitems && task.subitems.length > 0}
      <div class="dim" style="font-size:0.75rem; margin-top:2px;">
        ☑ {task.subitems.filter((s) => s.done).length}/{task.subitems.length} Teilaufgaben
      </div>
    {/if}
    <div class="task-meta">
      {#if isExam}<span class="pill exam">📝 Klausur</span>{/if}
      {#if task.task_type === 'catch_up'}<span class="pill">↺ nachholen</span>{/if}
      {#if task.task_type === 'practice'}<span class="pill">üben</span>{/if}
      {#if task.estimated_minutes}<span class="pill">⏱ {task.estimated_minutes} min</span>{/if}
    </div>
  </button>
</div>

<style>
  .task-row-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.5rem;
  }
  .due-pill {
    flex-shrink: 0;
    font-size: 0.75rem;
    padding: 0.15rem 0.45rem;
    border-radius: 999px;
    background: var(--bg-elevated);
    color: var(--fg-muted);
    border: 1px solid var(--border);
    white-space: nowrap;
  }
  .due-pill.overdue { background: var(--rating-1); color: #fff; border-color: transparent; }
  .due-pill.soon { background: var(--rating-2); color: #fff; border-color: transparent; }
</style>
