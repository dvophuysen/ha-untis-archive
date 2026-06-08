<script>
  import { api } from '../lib/api.js';
  import TaskRow from '../lib/TaskRow.svelte';
  import TaskEditor from '../lib/TaskEditor.svelte';

  let { accountId } = $props();

  let plan = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let budgetOverride = $state(null);
  let editing = $state(null);

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
  <div class="row gap-sm">
    {#each [30, 45, 60, 90, 120] as m}
      <button
        class:primary={plan?.budget_minutes === m}
        onclick={() => { budgetOverride = m; load(); }}
      >{m}m</button>
    {/each}
  </div>
  <button class="ghost" onclick={copyToClipboard} title="Liste kopieren">📋</button>
</div>

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if error}
  <div class="error-box">{error}</div>
{:else if plan}
  <div class="banner">
    Budget heute: <strong>{plan.budget_minutes} min</strong> ·
    eingeplant: <strong>{plan.must_do_minutes + plan.suggested_minutes} min</strong>
    {#if overBudget}<span style="color:var(--rating-1)"> · ⚠️ Pflicht überschreitet Budget</span>{/if}
  </div>

  {#if plan.must_do.length === 0 && plan.suggested.length === 0}
    <div class="empty">🎉 Nichts zu tun für heute.</div>
  {/if}

  {#if plan.must_do.length > 0}
    <div class="section-title">Pflicht <span class="dim">· {plan.must_do_minutes} min</span></div>
    {#each plan.must_do as task (task.id)}
      <div class="timeline-block must">
        <button class="ghost" style="text-align:left; flex:1; padding:0; min-height:auto; display:block;" onclick={() => (editing = task)}>
          <strong>{task.title}</strong>
          {#if task.subject_name && task.subject_name !== task.title}<span class="dim"> · {task.subject_name}</span>{/if}
          {#if task.notes}<div class="muted" style="font-size:0.8rem; margin-top:2px; white-space:pre-wrap;">{task.notes}</div>{/if}
        </button>
        <span class="badge">{task.estimated_minutes ?? '?'}m</span>
      </div>
    {/each}
  {/if}

  {#if plan.suggested.length > 0}
    <div class="section-title">Vorschläge <span class="dim">· {plan.suggested_minutes} min</span></div>
    {#each plan.suggested as task (task.id)}
      <div class="timeline-block suggested">
        <button class="ghost" style="text-align:left; flex:1; padding:0; min-height:auto; display:block;" onclick={() => (editing = task)}>
          <strong>{task.title}</strong>
          {#if task.subject_name && task.subject_name !== task.title}<span class="dim"> · {task.subject_name}</span>{/if}
          {#if task.notes}<div class="muted" style="font-size:0.8rem; margin-top:2px; white-space:pre-wrap;">{task.notes}</div>{/if}
        </button>
        <span class="badge">{task.estimated_minutes ?? '?'}m</span>
      </div>
    {/each}
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
