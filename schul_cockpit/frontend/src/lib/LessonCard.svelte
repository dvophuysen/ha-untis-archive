<script>
  import { api } from './api.js';
  import LessonDetail from './LessonDetail.svelte';

  // preview=true wird für die "Morgen"-Vorschau verwendet: nur Anzeige,
  // keine Bewertung, kein Detail-Modal — der Stoff hat noch nicht
  // stattgefunden, da gibt's nichts zu bewerten.
  let { accountId, lesson, preview = false } = $props();

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

<div id="lesson-{lesson.id}" class="lesson" class:cancelled={isCancelled} class:preview>
  <!-- LEFT: system info. Im Preview-Modus nicht klickbar (nichts zu
       bewerten an einer Stunde, die noch nicht stattgefunden hat). -->
  {#if preview}
    <div class="lesson-left">
      <div class="lesson-head">
        <span class="lesson-time">{lesson.start_hhmm}</span>
        <span class="lesson-subj" title={lesson.subject_name}>{subjectLabel}</span>
        {#if isCancelled}<span class="badge cancelled">❌ Ausfall</span>{/if}
        {#if isSubst && !isCancelled}<span class="badge substitution">↺ Vertretung</span>{/if}
        {#if hasExam}<span class="badge exam">📝 Klausur</span>{/if}
      </div>
      <div class="lesson-sub">
        {lesson.teacher_name ?? '—'}{#if lesson.is_teacher_substituted && lesson.teacher_orig_name}<span class="orig"> (statt {lesson.teacher_orig_name})</span>{/if}{#if lesson.room} · {lesson.room}{#if lesson.is_room_substituted && lesson.room_orig}<span class="orig"> (statt {lesson.room_orig})</span>{/if}{/if}
      </div>
      {#if hasExam && lesson.exam.name}
        <div class="lesson-exam">📝 {lesson.exam.name}</div>
      {/if}
      {#if lesson.lstext}
        <div class="lesson-ls">{lesson.lstext}</div>
      {/if}
    </div>
  {:else}
    <button class="lesson-left" onclick={openDetail} aria-label="Details und Kommentar">
      <div class="lesson-head">
        <span class="lesson-time">{lesson.start_hhmm}</span>
        <span class="lesson-subj" title={lesson.subject_name}>{subjectLabel}</span>
        {#if isCancelled}<span class="badge cancelled">❌ Ausfall</span>{/if}
        {#if isSubst && !isCancelled}<span class="badge substitution">↺ Vertretung</span>{/if}
        {#if wasAbsent}<span class="badge absent">🤒 versäumt</span>{/if}
        {#if hasExam}<span class="badge exam">📝 Klausur</span>{/if}
        {#if lesson.checkin?.note}<span class="mini" title="Kommentar">💬</span>{/if}
      </div>
      <div class="lesson-sub">
        {lesson.teacher_name ?? '—'}{#if lesson.is_teacher_substituted && lesson.teacher_orig_name}<span class="orig"> (statt {lesson.teacher_orig_name})</span>{/if}{#if lesson.room} · {lesson.room}{#if lesson.is_room_substituted && lesson.room_orig}<span class="orig"> (statt {lesson.room_orig})</span>{/if}{/if}
      </div>
      {#if hasExam && lesson.exam.name}
        <div class="lesson-exam">📝 {lesson.exam.name}</div>
      {/if}
      {#if lesson.lstext}
        <div class="lesson-ls">{lesson.lstext}</div>
      {/if}
    </button>
  {/if}

  <!-- RIGHT: quick check-in — entfällt im Preview-Modus. -->
  {#if !preview}
    {#if canRate}
      <div class="lesson-right">
        <div class="checkins">
          {#if isSubst}
            <button class="ci r4" class:active={rating === 4} disabled={busy} onclick={() => checkin(4)} title="nur Aufsicht / kein neuer Stoff">👀</button>
          {:else}
            <span class="ci-empty"></span>
          {/if}
          <button class="ci r3" class:active={rating === 3} disabled={busy} onclick={() => checkin(3)} title="verstanden">😀</button>
          <button class="ci r2" class:active={rating === 2} disabled={busy} onclick={() => checkin(2)} title="teils verstanden">😐</button>
          <button class="ci r1" class:active={rating === 1} disabled={busy} onclick={() => checkin(1)} title="nicht verstanden">😟</button>
        </div>
      </div>
    {:else}
      <div class="lesson-right muted-right">
        {#if isCancelled}entfällt{:else if wasAbsent}gefehlt{/if}
      </div>
    {/if}
  {/if}
</div>

{#if showDetail && !preview}
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
  /* Vorschau für morgen: dezenter, damit der Heute-Stundenplan oben
     visuell führend bleibt. */
  .lesson.preview {
    background: transparent;
    border-style: dashed;
  }
  .lesson.preview .lesson-left { cursor: default; }
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
    width: 144px;
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
  /* Fixed 4 columns; first column is the optional 👀 slot (kept empty on
     normal lessons so the other three always line up across cards). */
  .checkins { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.2rem; }
  .ci {
    font-size: 1.05rem;
    padding: 0.3rem 0;
    min-width: 0;
    min-height: 38px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .ci-empty { min-height: 38px; }
  .ci.active { color: #fff; }
  .ci.r3.active { background: var(--rating-3); border-color: var(--rating-3); }
  .ci.r2.active { background: var(--rating-2); border-color: var(--rating-2); }
  .ci.r1.active { background: var(--rating-1); border-color: var(--rating-1); }
  .ci.r4.active { background: var(--cancelled); border-color: var(--cancelled); }
  .orig { color: var(--fg-dim); }
</style>
