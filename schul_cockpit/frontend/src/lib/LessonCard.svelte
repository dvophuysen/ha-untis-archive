<script>
  import { api } from './api.js';

  let { accountId, lesson, oncheckin = () => {} } = $props();

  let busy = $state(false);
  let note = $state(lesson.checkin?.note ?? '');
  let showNote = $state(false);

  const isCancelled = $derived(lesson.is_cancelled);
  const wasAbsent = $derived(!!lesson.was_absent);
  const hasExam = $derived(!!lesson.exam);

  async function checkin(rating) {
    busy = true;
    try {
      await api.post(
        `/api/accounts/${accountId}/lessons/${lesson.id}/checkin`,
        { rating, note: note || null },
      );
      lesson.checkin = { rating, note: note || null };
      oncheckin();
    } finally {
      busy = false;
    }
  }

  async function clearCheckin() {
    busy = true;
    try {
      await api.delete(`/api/accounts/${accountId}/lessons/${lesson.id}/checkin`);
      lesson.checkin = null;
      note = '';
      oncheckin();
    } finally {
      busy = false;
    }
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

<div class="card" class:compact={isCancelled}>
  <div class="row between" style="align-items:flex-start;">
    <div class="col" style="flex:1; gap:0.15rem; min-width:0;">
      <div class="row gap-sm">
        <span class="lesson-time">{lesson.start_hhmm}–{lesson.end_hhmm}</span>
        {#if isCancelled}<span class="badge cancelled">❌ Ausfall</span>{/if}
        {#if lesson.is_irregular && !isCancelled}<span class="badge substitution">↺ Vertretung</span>{/if}
        {#if wasAbsent}<span class="badge absent">🤒 versäumt</span>{/if}
        {#if hasExam}<span class="badge exam">📝 Klausur</span>{/if}
        {#if lesson.is_late_addition}<span class="badge late">neu</span>{/if}
      </div>
      <div class="lesson-subject" class:struck={isCancelled}>{lesson.subject_name ?? '—'}</div>
      <div class="lesson-meta">
        {lesson.teacher_name ?? '—'}
        {#if lesson.is_teacher_substituted && lesson.teacher_orig_name}
          <span class="dim">(statt {lesson.teacher_orig_name})</span>
        {/if}
        {#if lesson.room}· {lesson.room}{/if}
        {#if lesson.is_room_substituted && lesson.room_orig}
          <span class="dim">(statt {lesson.room_orig})</span>
        {/if}
      </div>
      {#if hasExam && lesson.exam.name}
        <div class="lesson-meta" style="color: var(--exam); font-weight:500;">
          📝 {lesson.exam.name}
        </div>
      {/if}
      {#if lesson.lstext}
        <div class="lesson-lstext" class:struck={isCancelled}>
          {lesson.lstext}
        </div>
      {/if}
      {#if lesson.subst_text && lesson.subst_text !== lesson.lstext}
        <div class="lesson-meta dim" style="margin-top:0.3rem;">ℹ️ {lesson.subst_text}</div>
      {/if}
    </div>
  </div>

  {#if !isCancelled && !wasAbsent}
    <div class="checkin-row">
      <button
        class:active={lesson.checkin?.rating === 1}
        class="r1"
        disabled={busy}
        onclick={() => checkin(1)}
        aria-label="Stunde nicht verstanden"
      >😟</button>
      <button
        class:active={lesson.checkin?.rating === 2}
        class="r2"
        disabled={busy}
        onclick={() => checkin(2)}
        aria-label="teilweise verstanden"
      >😐</button>
      <button
        class:active={lesson.checkin?.rating === 3}
        class="r3"
        disabled={busy}
        onclick={() => checkin(3)}
        aria-label="Stunde verstanden"
      >😀</button>
    </div>

    {#if lesson.checkin || showNote}
      <div style="margin-top:0.5rem;" class="col gap-sm">
        <textarea
          placeholder="Notiz (optional)…"
          bind:value={note}
          rows="2"
          onblur={() => lesson.checkin && checkin(lesson.checkin.rating)}
        ></textarea>
        {#if lesson.checkin}
          <button class="ghost" onclick={clearCheckin}>Bewertung entfernen</button>
        {/if}
      </div>
    {:else}
      <button class="ghost" style="margin-top:0.4rem; width:100%; font-size:0.85rem;" onclick={() => (showNote = true)}>+ Notiz hinzufügen</button>
    {/if}
  {/if}

  {#if wasAbsent && lesson.lstext}
    <div style="margin-top:0.5rem;">
      <button onclick={markCaughtUp} disabled={busy}>
        {lesson.caught_up ? '✓ Nachgeholt' : 'Als nachgeholt markieren'}
      </button>
    </div>
  {/if}
</div>
