<script>
  import { api } from './api.js';
  import LessonDetail from './LessonDetail.svelte';

  let { accountId, lesson } = $props();

  let busy = $state(false);
  let note = $state(lesson.checkin?.note ?? '');
  let showDetail = $state(false);

  const isCancelled = $derived(lesson.is_cancelled);
  const wasAbsent = $derived(!!lesson.was_absent);
  const hasExam = $derived(!!lesson.exam);
  const rating = $derived(lesson.checkin?.rating ?? null);
  const subjectLabel = $derived(lesson.subject_short || lesson.subject_name || '—');
  const canRate = $derived(!isCancelled && !wasAbsent);
  // 👀 "nur Aufsicht" makes sense only for actual substitution lessons,
  // not for the regular teacher delivering the regular subject.
  const isSubst = $derived(
    !!(lesson.is_irregular || lesson.is_teacher_substituted || lesson.is_subject_substituted),
  );

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
    // A note belongs to a check-in (rating is required). If none is set yet,
    // default to 😐 so the comment can be stored.
    const r = lesson.checkin?.rating ?? 2;
    await checkin(r);
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

  function openDetail() {
    note = lesson.checkin?.note ?? '';
    showDetail = true;
  }
</script>

<div class="lesson" class:cancelled={isCancelled}>
  <!-- LEFT: system info, tappable to open detail/comment -->
  <button class="lesson-left" onclick={openDetail} aria-label="Details und Kommentar">
    <div class="lesson-head">
      <span class="lesson-time">{lesson.start_hhmm}</span>
      <span class="lesson-subj" title={lesson.subject_name}>{subjectLabel}</span>
      {#if isCancelled}<span class="mini">❌</span>{/if}
      {#if lesson.is_irregular && !isCancelled}<span class="mini">↺</span>{/if}
      {#if wasAbsent}<span class="mini">🤒</span>{/if}
      {#if hasExam}<span class="mini">📝</span>{/if}
      {#if lesson.checkin?.note}<span class="mini">💬</span>{/if}
    </div>
    <div class="lesson-sub">
      {lesson.teacher_name ?? '—'}{#if lesson.room} · {lesson.room}{/if}
    </div>
    {#if hasExam && lesson.exam.name}
      <div class="lesson-exam">📝 {lesson.exam.name}</div>
    {/if}
    {#if lesson.lstext}
      <div class="lesson-ls">{lesson.lstext}</div>
    {/if}
  </button>

  <!-- RIGHT: quick check-in -->
  {#if canRate}
    <div class="lesson-right">
      <div class="checkins" class:three={!isSubst}>
        <button class="ci r3" class:active={rating === 3} disabled={busy} onclick={() => checkin(3)} title="verstanden">😀</button>
        <button class="ci r2" class:active={rating === 2} disabled={busy} onclick={() => checkin(2)} title="teils verstanden">😐</button>
        <button class="ci r1" class:active={rating === 1} disabled={busy} onclick={() => checkin(1)} title="nicht verstanden">😟</button>
        {#if isSubst}
          <button class="ci r4" class:active={rating === 4} disabled={busy} onclick={() => checkin(4)} title="nur Aufsicht / kein neuer Stoff">👀</button>
        {/if}
      </div>
    </div>
  {:else}
    <div class="lesson-right muted-right">
      {#if isCancelled}entfällt{:else if wasAbsent}gefehlt{/if}
    </div>
  {/if}
</div>

{#if showDetail}
  <LessonDetail
    {accountId}
    {lesson}
    onclose={() => (showDetail = false)}
  />
{/if}

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
  .lesson-left {
    flex: 1;
    min-width: 0;
    text-align: left;
    background: transparent;
    border: none;
    padding: 0;
    min-height: auto;
    color: inherit;
    cursor: pointer;
  }
  .lesson-right {
    width: 124px;
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
  .lesson-time { font-variant-numeric: tabular-nums; font-size: 0.78rem; color: var(--fg-muted); }
  .lesson-subj { font-weight: 600; font-size: 1rem; }
  .mini { font-size: 0.8rem; }
  .lesson-sub { font-size: 0.8rem; color: var(--fg-muted); margin-top: 1px; }
  .lesson-exam { font-size: 0.8rem; color: var(--exam); font-weight: 500; margin-top: 2px; }
  .lesson-ls {
    font-size: 0.82rem;
    margin-top: 0.25rem;
    color: var(--fg);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .checkins { display: grid; grid-template-columns: 1fr 1fr; gap: 0.25rem; }
  .checkins.three { grid-template-columns: 1fr 1fr 1fr; }
  .detail-checkins { grid-template-columns: repeat(4, 1fr); }
  .detail-checkins.three { grid-template-columns: repeat(3, 1fr); }
  .ci {
    font-size: 1.2rem;
    padding: 0.3rem 0;
    min-height: 40px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .ci.active { color: #fff; }
  .ci.r3.active { background: var(--rating-3); border-color: var(--rating-3); }
  .ci.r2.active { background: var(--rating-2); border-color: var(--rating-2); }
  .ci.r1.active { background: var(--rating-1); border-color: var(--rating-1); }
  .ci.r4.active { background: var(--cancelled); border-color: var(--cancelled); }
</style>
