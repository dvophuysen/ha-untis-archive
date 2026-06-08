<script>
  import { api } from './api.js';

  let { accountId, task, onchange = () => {}, onopen = null } = $props();

  let busy = $state(false);

  const today = new Date().toISOString().slice(0, 10);
  const isOverdue = $derived(task.due_date && task.due_date < today && task.status !== 'done');
  const isToday = $derived(task.due_date === today && task.status !== 'done');
  const isExam = $derived(task.task_type === 'exam_prep');

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

  function fmtDue(s) {
    if (!s) return '';
    if (s === today) return 'heute';
    const d = new Date(s);
    const diff = Math.round((d - new Date(today)) / 86400000);
    if (diff === 1) return 'morgen';
    if (diff === -1) return 'gestern';
    if (diff < 0) return `${-diff}T überfällig`;
    if (diff < 7) return `in ${diff}T`;
    return s;
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
    <div class="task-title" class:done={task.status === 'done'}>{task.title}</div>
    {#if task.notes}
      <div class="muted" style="font-size:0.8rem; margin-top:1px; white-space:pre-wrap;">{task.notes}</div>
    {/if}
    {#if task.subitems && task.subitems.length > 0}
      <div class="dim" style="font-size:0.75rem; margin-top:1px;">
        ☑ {task.subitems.filter((s) => s.done).length}/{task.subitems.length} Teilaufgaben
      </div>
    {/if}
    <div class="task-meta">
      {#if task.subject_name}<span class="pill">{task.subject_name}</span>{/if}
      {#if isExam}<span class="pill exam">📝 Klausur</span>{/if}
      {#if task.task_type === 'catch_up'}<span class="pill">↺ nachholen</span>{/if}
      {#if task.task_type === 'practice'}<span class="pill">üben</span>{/if}
      {#if task.estimated_minutes}<span class="pill">⏱ {task.estimated_minutes} min</span>{/if}
      {#if task.due_date}
        <span class="pill" class:overdue={isOverdue} class:today={isToday}>{fmtDue(task.due_date)}</span>
      {/if}
      {#if task.source === 'ha_todo'}<span class="pill" title="Aus HA-ToDo-Liste">HA</span>{/if}
    </div>
  </button>
</div>
