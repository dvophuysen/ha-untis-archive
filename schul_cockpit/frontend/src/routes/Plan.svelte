<script>
  import { api } from '../lib/api.js';
  import { appState } from '../lib/store.svelte.js';
  import { dueLabel, stripUntisMetadata, isoToday } from '../lib/format.js';
  import TaskRow from '../lib/TaskRow.svelte';
  import TaskEditor from '../lib/TaskEditor.svelte';

  const today = isoToday();
  // Only the adult side gets the quick-budget pickers. For the kid, the
  // budget is fixed by what the parent set in Settings — they shouldn't
  // be able to silently double their study time from the planner screen.
  const canEditBudget = $derived(
    appState.me?.role === 'admin' || appState.me?.role === 'parent',
  );

  let { accountId } = $props();

  let plan = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let budgetOverride = $state(null);
  let editing = $state(null);
  let addedKeys = $state(new Set());
  let addingKey = $state(null);

  const TYPE_MAP = {
    understanding: { task_type: 'catch_up', verb: 'üben' },
    prep_tomorrow: { task_type: 'practice', verb: 'für morgen vorbereiten' },
    vocab: { task_type: 'practice', verb: 'Vokabeln üben' },
  };

  function suggestionKey(s) {
    return `${s.type}:${s.subject_name}`;
  }

  function suggestionTitle(s) {
    const map = TYPE_MAP[s.type];
    if (s.type === 'vocab') return `${s.subject_name}: Vokabeln üben`;
    if (s.type === 'prep_tomorrow') return `${s.subject_name} für morgen vorbereiten`;
    return `${s.subject_name} üben`;
  }

  async function addSuggestion(s) {
    const key = suggestionKey(s);
    addingKey = key;
    try {
      await api.post(`/api/accounts/${accountId}/tasks`, {
        title: suggestionTitle(s),
        task_type: TYPE_MAP[s.type]?.task_type ?? 'practice',
        estimated_minutes: s.suggested_minutes,
        subject_untis_id: s.subject_id ?? null,
        subject_name: s.subject_name,
        due_date: today,
      });
      addedKeys = new Set(addedKeys).add(key);
      await load();
    } catch (e) {
      error = e.message;
    } finally {
      addingKey = null;
    }
  }

  async function load() {
    if (!accountId) return;
    loading = true;
    error = null;
    try {
      const q = budgetOverride != null ? `?budget_minutes=${budgetOverride}` : '';
      plan = await api.get(`/api/accounts/${accountId}/afternoon-plan${q}`);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void accountId; load(); });

  const overBudget = $derived(plan && plan.must_do_minutes > plan.budget_minutes);

  function copyToClipboard() {
    if (!plan) return;
    const lines = [`# Nachmittagsplan ${plan.date}`, `Budget: ${plan.budget_minutes} min`, ''];
    if (plan.must_do.length) {
      lines.push('## Pflicht (überfällig / heute)');
      for (const t of plan.must_do) lines.push(`- [ ] ${t.title}${t.estimated_minutes ? ` (${t.estimated_minutes} min)` : ''}`);
      lines.push('');
    }
    if (plan.suggested.length) {
      lines.push('## Vorschläge');
      for (const t of plan.suggested) lines.push(`- [ ] ${t.title}${t.estimated_minutes ? ` (${t.estimated_minutes} min)` : ''}`);
    }
    navigator.clipboard.writeText(lines.join('\n'));
  }
</script>

<div class="row between" style="margin: 0.3rem 0.2rem 0.6rem;">
  {#if canEditBudget}
    <div class="row gap-sm">
      {#each [30, 45, 60, 90, 120] as m}
        <button
          class:primary={plan?.budget_minutes === m}
          onclick={() => { budgetOverride = m; load(); }}
        >{m}m</button>
      {/each}
    </div>
  {:else}
    <div class="muted">Tagesbudget: <strong>{plan?.budget_minutes ?? '…'} min</strong></div>
  {/if}
  <button class="ghost" onclick={copyToClipboard} title="Liste kopieren">📋</button>
</div>

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if error}
  <div class="error-box">{error}</div>
{:else if plan}
  <div class="banner">
    Budget heute: <strong>{plan.budget_minutes} min</strong>
    {#if plan.completed_today_minutes > 0}
      · ✓ erledigt: <strong>{plan.completed_today_minutes} min</strong>
    {/if}
    · eingeplant: <strong>{plan.must_do_minutes + plan.suggested_minutes} min</strong>
    {#if overBudget}<span style="color:var(--rating-1)"> · ⚠️ Pflicht überschreitet Budget</span>{/if}
  </div>

  {#if plan.must_do.length === 0 && plan.suggested.length === 0}
    <div class="empty">🎉 Nichts zu tun für heute.</div>
  {/if}

  {#if plan.must_do.length > 0}
    <div class="section-title">Pflicht <span class="dim">· {plan.must_do_minutes} min</span></div>
    {#each plan.must_do as task (task.id)}
      {@const clean = stripUntisMetadata(task.notes)}
      <div class="timeline-block must">
        <button class="ghost" style="text-align:left; flex:1; padding:0; min-height:auto; display:block;" onclick={() => (editing = task)}>
          <div class="plan-head">
            <strong>{task.title}</strong>
            {#if task.due_date}<span class="due-tag">{dueLabel(task.due_date, today)}</span>{/if}
          </div>
          {#if clean}<div class="muted" style="font-size:0.85rem; margin-top:3px; white-space:pre-wrap;">{clean}</div>{/if}
        </button>
        <span class="badge">{task.estimated_minutes ?? '?'}m</span>
      </div>
    {/each}
  {/if}

  {#if plan.suggested.length > 0}
    <div class="section-title">Vorschläge <span class="dim">· {plan.suggested_minutes} min</span></div>
    {#each plan.suggested as task (task.id)}
      {@const clean = stripUntisMetadata(task.notes)}
      <div class="timeline-block suggested">
        <button class="ghost" style="text-align:left; flex:1; padding:0; min-height:auto; display:block;" onclick={() => (editing = task)}>
          <div class="plan-head">
            <strong>{task.title}</strong>
            {#if task.due_date}<span class="due-tag">{dueLabel(task.due_date, today)}</span>{/if}
          </div>
          {#if clean}<div class="muted" style="font-size:0.85rem; margin-top:3px; white-space:pre-wrap;">{clean}</div>{/if}
        </button>
        <span class="badge">{task.estimated_minutes ?? '?'}m</span>
      </div>
    {/each}
  {/if}

  {#if plan.remaining_minutes > 0}
    <div class="section-title">
      Freie Lernzeit <span class="dim">· noch {plan.remaining_minutes} min</span>
    </div>
    {#if plan.free_learning && plan.free_learning.filter((s) => !addedKeys.has(suggestionKey(s))).length > 0}
      <div class="muted" style="margin: 0 0.2rem 0.4rem;">Vorschläge — mit + als Aufgabe übernehmen:</div>
      {#each plan.free_learning.filter((s) => !addedKeys.has(suggestionKey(s))) as s (suggestionKey(s))}
        <div class="timeline-block free">
          <div style="flex:1; min-width:0;">
            <div class="plan-head">
              <strong>{suggestionTitle(s)}</strong>
              <span class="due-tag">{s.suggested_minutes}m</span>
            </div>
            <div class="muted" style="font-size:0.8rem; margin-top:2px;">
              {#if s.type === 'understanding'}🧠 {s.reason}
              {:else if s.type === 'prep_tomorrow'}📖 {s.reason}
              {:else}🗂 {s.reason}{/if}
            </div>
          </div>
          <button
            class="primary add-btn"
            disabled={addingKey === suggestionKey(s)}
            onclick={() => addSuggestion(s)}
            aria-label="als Aufgabe übernehmen"
          >+</button>
        </div>
      {/each}
    {:else}
      <div class="muted" style="margin: 0 0.2rem 0.6rem;">
        Keine offenen Vorschläge — Zeit frei zum Lesen, Üben oder Entspannen. 🙂
      </div>
    {/if}
  {/if}

  {#if plan.upcoming_exams_7d.length > 0}
    <div class="section-title">Klausuren in 7 Tagen</div>
    {#each plan.upcoming_exams_7d as ex}
      <div class="card compact">
        <strong>{ex.subject_name}</strong>
        <span class="dim">· {ex.date}</span>
        {#if ex.name}<div class="muted">{ex.name}</div>{/if}
      </div>
    {/each}
  {/if}
{/if}

{#if editing}
  <TaskEditor {accountId} task={editing} onclose={() => (editing = null)} onsaved={load} />
{/if}

<style>
  .plan-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.5rem;
  }
  .due-tag {
    flex-shrink: 0;
    font-size: 0.72rem;
    color: var(--fg-muted);
    white-space: nowrap;
  }
  .timeline-block.free { border-left: 3px solid var(--rating-3); align-items: center; }
  .add-btn {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    font-size: 1.3rem;
    padding: 0;
    line-height: 1;
  }
</style>
