<script>
  import { api } from '../lib/api.js';
  import { dueLabel, stripUntisMetadata, isoToday, formatShortDate } from '../lib/format.js';
  import TaskRow from '../lib/TaskRow.svelte';
  import TaskEditor from '../lib/TaskEditor.svelte';

  let { accountId } = $props();
  const today = isoToday();

  let data = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let editing = $state(null);

  async function load() {
    if (!accountId) return;
    loading = true;
    error = null;
    try {
      data = await api.get(`/api/accounts/${accountId}/plan`);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void accountId; load(); });

  const WORKLOAD = {
    frei: { label: 'nichts Pflicht heute 🎉', cls: 'ok' },
    wenig: { label: 'wenig zu tun', cls: 'ok' },
    überschaubar: { label: 'überschaubar', cls: 'mid' },
    viel: { label: 'viel — fang mit den schnellen Sachen an', cls: 'high' },
  };

  function gotoExam() { window.location.hash = '#/subjects'; }
  function gotoAbsences() { window.location.hash = '#/absences'; }
  function followLink(link) {
    window.location.hash = link === 'absences' ? '#/absences' : '#/subjects';
  }

  function examUrgencyClass(days) {
    if (days <= 2) return 'soon';
    if (days <= 7) return 'mid';
    return '';
  }
  function examWhen(days) {
    if (days === 0) return 'heute';
    if (days === 1) return 'morgen';
    if (days === 2) return 'übermorgen';
    return `in ${days} Tagen`;
  }
</script>

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if error}
  <div class="error-box">{error}</div>
{:else if data}
  <div class="pensum {WORKLOAD[data.workload]?.cls ?? ''}">
    Heute: <strong>{WORKLOAD[data.workload]?.label ?? data.workload}</strong>
  </div>

  <!-- MUSS -->
  {#if data.must.length > 0}
    <div class="section-title">Muss heute</div>
    <div class="card" style="padding:0.2rem 0.6rem;">
      {#each data.must as task (task.id)}
        <TaskRow {accountId} {task} onchange={load} onopen={(t) => (editing = t)} />
      {/each}
    </div>
  {/if}

  <!-- SOLLTE -->
  {#if data.should.length > 0}
    <div class="section-title">Sollte heute</div>
    {#each data.should as s}
      <button class="card compact should-item" onclick={() => followLink(s.link)}>
        <div class="row between" style="align-items:flex-start;">
          <div style="flex:1; min-width:0; text-align:left;">
            <strong>{s.title}</strong>
            <div class="muted" style="margin-top:1px;">
              {#if s.type === 'exam_prep'}📝{:else if s.type === 'catch_up'}🤒{:else}🧠{/if}
              {s.reason}
            </div>
          </div>
          <span class="chev">›</span>
        </div>
      </button>
    {/each}
  {/if}

  <!-- Anstehende Klausuren (Übersicht) -->
  <div class="section-title">Anstehende Klausuren</div>
  {#if data.upcoming_exams.length === 0}
    <div class="empty" style="padding:1rem;">
      Keine Klausuren in den nächsten 4 Wochen erkannt.<br>
      <span class="dim">Kalender verknüpfen/Termine ergänzen: Setup → Klausuren verwalten.</span>
    </div>
  {:else}
    {#each data.upcoming_exams as e}
      <div class="card compact exam-row">
        <div class="row between">
          <div>
            <strong>{e.subject_name ?? e.title}</strong>
            {#if e.subject_name && e.title && e.title !== e.subject_name}
              <span class="dim"> · {e.title}</span>
            {/if}
            <div class="dim">{formatShortDate(e.date)}{#if e.source === 'manual'} · manuell{/if}</div>
          </div>
          <span class="badge exam-when {examUrgencyClass(e.days_until)}">{examWhen(e.days_until)}</span>
        </div>
      </div>
    {/each}
  {/if}

  {#if data.must.length === 0 && data.should.length === 0}
    <div class="empty" style="margin-top:1rem;">Nichts Dringendes — Zeit zum Durchatmen. 🙂</div>
  {/if}
{/if}

{#if editing}
  <TaskEditor {accountId} task={editing} onclose={() => (editing = null)} onsaved={load} />
{/if}

<style>
  .pensum {
    border-radius: var(--radius);
    padding: 0.6rem 0.85rem;
    margin: 0.4rem 0 0.6rem;
    border: 1px solid var(--border);
    background: var(--bg-card);
    font-size: 0.9rem;
  }
  .pensum.ok { border-left: 4px solid var(--rating-3); }
  .pensum.mid { border-left: 4px solid var(--rating-2); }
  .pensum.high { border-left: 4px solid var(--rating-1); }
  .should-item { width: 100%; cursor: pointer; }
  .chev { color: var(--fg-dim); font-size: 1.2rem; }
  .exam-when.soon { background: var(--rating-1); color: #fff; border-color: transparent; }
  .exam-when.mid { background: var(--rating-2); color: #fff; border-color: transparent; }
</style>
