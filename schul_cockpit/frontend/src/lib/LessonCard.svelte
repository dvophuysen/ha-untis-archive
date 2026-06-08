<script>
  import { api } from './api.js';

  let { accountId, lesson } = $props();

  let busy = $state(false);
  let note = $state(lesson.checkin?.note ?? '');
  let expanded = $state(false);

  const isCancelled = $derived(lesson.is_cancelled);
  const wasAbsent = $derived(!!lesson.was_absent);
  const hasExam = $derived(!!lesson.exam);
  const rating = $derived(lesson.checkin?.rating ?? null);
  const subjectLabel = $derived(lesson.subject_short || lesson.subject_name || '—');

  async function checkin(r) {
    busy = true;
    try {
      await api.post(
        `/api/accounts/${accountId}/lessons/${lesson.id}/checkin`,
        { rating: r, note: note || null },
      );
      lesson.checkin = { rating: r, note: note || null };
    } finally {
      busy = false;
    }
  }

  async function saveNote() {
    if (!lesson.checkin) return;
    await checkin(lesson.checkin.rating);
  }

  async function markCaughtUp() {
    busy = true;
    try {
      if (lesson.caught_up) {
        await api.delete(`/api/accounts/${accountId}/lessons/${lesson.id}/caught-up`);
        lesson.caught_up = false;
      } else {
        await api.post(`/api/accounts/${accountId}/lessons/${lesson.id}/caught-up`, {});
        lesson.caught_up = true;
      }
    } finally {
      busy = false;
    }
  }
</script>

<div class="lesson" class:cancelled={isCancelled}>
  <!-- LEFT: system-provided info -->
  <div class="lesson-left">
    <div class="lesson-head">
      <span class="lesson-time">{lesson.start_hhmm}</span>
      <span class="lesson-subj" title={lesson.subject_name}>{subjectLabel}</span>
      {#if isCancelled}<span class="mini cancelled">❌</span>{/if}
      {#if lesson.is_irregular && !isCancelled}<span class="mini subst">↺</span>{/if}
      {#if wasAbsent}<span class="mini absent">🤒</span>{/if}
      {#if hasExam}<span class="mini exam">📝</span>{/if}
    </div>
    <div class="lesson-sub">
      {lesson.teacher_name ?? '—'}{#if lesson.room} · {lesson.room}{/if}
    </div>
    {#if hasExam && lesson.exam.name}
      <div class="lesson-exam">📝 {lesson.exam.name}</div>
    {/if}
    {#if lesson.lstext}
      <div class="lesson-ls" class:clamp={!expanded} role="button" tabindex="0"
           onclick={() => (expanded = !expanded)}
           onkeydown={(e) => e.key === 'Enter' && (expanded = !expanded)}>
        {lesson.lstext}
      </div>
    {/if}
    {#if wasAbsent && lesson.lstext}
      <button class="caught-btn" onclick={markCaughtUp} disabled={busy}>
        {lesson.caught_up ? '✓ nachgeholt' : 'nachholen'}
      </button>
    {/if}
  </div>

  <!-- RIGHT: user feedback -->
  {#if !isCancelled && !wasAbsent}
    <div class="lesson-right">
      <div class="checkins">
        <button class="ci r3" class:active={rating === 3} disabled={busy} onclick={() => checkin(3)} aria-label="verstanden" title="verstanden">😀</button>
        <button class="ci r2" class:active={rating === 2} disabled={busy} onclick={() => checkin(2)} aria-label="teils verstanden" title="teils verstanden">😐</button>
        <button class="ci r1" class:active={rating === 1} disabled={busy} onclick={() => checkin(1)} aria-label="nicht verstanden" title="nicht verstanden">😟</button>
        <button class="ci r4" class:active={rating === 4} disabled={busy} onclick={() => checkin(4)} aria-label="nur Aufsicht, kein neuer Stoff" title="nur Aufsicht / kein neuer Stoff">👀</button>
      </div>
      {#if rating}
        <input
          class="note-input"
          placeholder="Notiz…"
          bind:value={note}
          onblur={saveNote}
        />
      {/if}
    </div>
  {:else}
    <div class="lesson-right muted-right">
      {#if isCancelled}entfällt{:else if wasAbsent}gefehlt{/if}
    </div>
  {/if}
</div>

<style>
  .lesson {
    display: flex;
    gap: 0.5rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.5rem 0.6rem;
    margin: 0.35rem 0;
  }
  .lesson.cancelled { opacity: 0.6; }
  .lesson-left { flex: 1; min-width: 0; }
  .lesson-right {
    width: 116px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    justify-content: center;
  }
  .muted-right {
    align-items: center;
    justify-content: center;
    color: var(--fg-dim);
    font-size: 0.8rem;
  }
  .lesson-head { display: flex; align-items: baseline; gap: 0.4rem; flex-wrap: wrap; }
  .lesson-time {
    font-variant-numeric: tabular-nums;
    font-size: 0.78rem;
    color: var(--fg-muted);
  }
  .lesson-subj { font-weight: 600; font-size: 1rem; }
  .mini { font-size: 0.8rem; }
  .lesson-sub { font-size: 0.8rem; color: var(--fg-muted); margin-top: 1px; }
  .lesson-exam { font-size: 0.8rem; color: var(--exam); font-weight: 500; margin-top: 2px; }
  .lesson-ls {
    font-size: 0.82rem;
    margin-top: 0.25rem;
    color: var(--fg);
    cursor: pointer;
  }
  .lesson-ls.clamp {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .caught-btn {
    margin-top: 0.3rem;
    font-size: 0.75rem;
    min-height: 32px;
    padding: 0.2rem 0.5rem;
  }
  .checkins {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.25rem;
  }
  .ci {
    font-size: 1.15rem;
    padding: 0.25rem 0;
    min-height: 36px;
    background: var(--bg-elevated);
    border-radius: 8px;
    opacity: 0.5;
  }
  .ci.active { opacity: 1; }
  .ci.r3.active { background: var(--rating-3); border-color: var(--rating-3); }
  .ci.r2.active { background: var(--rating-2); border-color: var(--rating-2); }
  .ci.r1.active { background: var(--rating-1); border-color: var(--rating-1); }
  .ci.r4.active { background: var(--cancelled); border-color: var(--cancelled); }
  .note-input {
    font-size: 0.78rem;
    min-height: 32px;
    padding: 0.25rem 0.4rem;
  }
</style>
