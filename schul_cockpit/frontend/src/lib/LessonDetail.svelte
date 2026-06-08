<script>
  import { api } from './api.js';
  import { formatShortDate } from './format.js';

  /**
   * Lesson detail sheet — opens from both the Today list and the weekly
   * grid. Lets the user (when the lesson has already happened) leave a
   * comprehension check-in and a comment, and on absent lessons mark
   * the missed material as caught up.
   *
   * Expects a `lesson` object with the same shape both pages use:
   * id, date, start_hhmm, end_hhmm, start_time, end_time,
   * subject_name, subject_short, teacher_name, teacher_orig_name,
   * room, room_orig, code, lstext, subst_text, is_cancelled,
   * is_irregular, is_teacher_substituted, is_subject_substituted,
   * was_absent, exam, checkin (optional), caught_up (optional).
   */
  let { accountId, lesson, onclose, onsaved = () => {} } = $props();

  let busy = $state(false);
  let note = $state(lesson.checkin?.note ?? '');
  let rating = $state(lesson.checkin?.rating ?? null);
  let cleanError = $state(null);

  const isCancelled = $derived(!!lesson.is_cancelled);
  const wasAbsent = $derived(!!lesson.was_absent);
  const hasExam = $derived(!!lesson.exam);
  const isSubst = $derived(
    !!(lesson.is_irregular || lesson.is_teacher_substituted || lesson.is_subject_substituted),
  );

  // Already-happened test: past day, OR today and end-time has passed.
  const todayIso = (() => {
    const d = new Date();
    return (
      d.getFullYear() + '-' +
      String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0')
    );
  })();
  const isPast = $derived.by(() => {
    if (!lesson.date) return false;
    if (lesson.date < todayIso) return true;
    if (lesson.date > todayIso) return false;
    const end = lesson.end_time;
    if (end == null) return false;
    const now = new Date();
    const nowHhmm = now.getHours() * 100 + now.getMinutes();
    return nowHhmm >= end;
  });

  const canRate = $derived(isPast && !isCancelled && !wasAbsent);
  const canCatchUp = $derived(isPast && wasAbsent && !!lesson.lstext);

  async function setRating(r) {
    if (!canRate || busy) return;
    busy = true;
    cleanError = null;
    rating = r;
    try {
      await api.post(`/api/accounts/${accountId}/lessons/${lesson.id}/checkin`, {
        rating: r,
        note: note || null,
      });
      lesson.checkin = { rating: r, note: note || null };
      onsaved();
    } catch (e) {
      cleanError = e.message || 'Speichern fehlgeschlagen';
      rating = lesson.checkin?.rating ?? null;
    } finally {
      busy = false;
    }
  }

  async function saveNote() {
    if (!canRate || busy) return;
    // Saving a comment requires a rating; default to 😐 if none picked yet.
    const r = rating ?? 2;
    busy = true;
    cleanError = null;
    try {
      await api.post(`/api/accounts/${accountId}/lessons/${lesson.id}/checkin`, {
        rating: r,
        note: note || null,
      });
      rating = r;
      lesson.checkin = { rating: r, note: note || null };
      onsaved();
    } catch (e) {
      cleanError = e.message || 'Speichern fehlgeschlagen';
    } finally {
      busy = false;
    }
  }

  async function toggleCaughtUp() {
    if (busy) return;
    busy = true;
    cleanError = null;
    try {
      if (lesson.caught_up) {
        await api.delete(`/api/accounts/${accountId}/lessons/${lesson.id}/caught-up`);
        lesson.caught_up = false;
      } else {
        await api.post(`/api/accounts/${accountId}/lessons/${lesson.id}/caught-up`, {});
        lesson.caught_up = true;
      }
      onsaved();
    } catch (e) {
      cleanError = e.message || 'Speichern fehlgeschlagen';
    } finally {
      busy = false;
    }
  }

  function dateLine() {
    const d = formatShortDate(lesson.date);
    const t = lesson.start_hhmm && lesson.end_hhmm
      ? ` · ${lesson.start_hhmm}–${lesson.end_hhmm}`
      : (lesson.start_hhmm ? ` · ${lesson.start_hhmm}` : '');
    return `${d}${t}`;
  }
</script>

<div class="modal-backdrop" onclick={onclose} role="presentation">
  <div class="modal" onclick={(e) => e.stopPropagation()} role="dialog">
    <div class="row between" style="margin-bottom:0.4rem;">
      <h2 style="margin:0; font-size:1.1rem;">{lesson.subject_name ?? lesson.subject_short ?? 'Stunde'}</h2>
      <button class="ghost" onclick={onclose}>✕</button>
    </div>
    <div class="muted">{dateLine()}</div>

    <div class="row gap-sm" style="margin:0.4rem 0; flex-wrap:wrap;">
      {#if isCancelled}<span class="badge cancelled">❌ Ausfall</span>{/if}
      {#if isSubst && !isCancelled}<span class="badge substitution">↺ Vertretung</span>{/if}
      {#if wasAbsent}<span class="badge absent">🤒 gefehlt</span>{/if}
      {#if hasExam}<span class="badge exam">📝 Klausur</span>{/if}
      {#if !isPast}<span class="badge">⏳ steht noch an</span>{/if}
    </div>

    <div class="card compact" style="margin:0 0 0.6rem;">
      {#if lesson.teacher_name || lesson.teacher_orig_name}
        <div>👤 {lesson.teacher_name ?? '—'}
          {#if lesson.teacher_orig_name && lesson.is_teacher_substituted}
            <span class="dim">(statt {lesson.teacher_orig_name})</span>
          {/if}
        </div>
      {/if}
      {#if lesson.room || lesson.room_orig}
        <div>📍 {lesson.room ?? '—'}
          {#if lesson.room_orig && lesson.is_room_substituted}
            <span class="dim">(statt {lesson.room_orig})</span>
          {/if}
        </div>
      {/if}
      {#if hasExam && lesson.exam?.name}
        <div style="color:var(--exam)">📝 {lesson.exam.name}</div>
      {/if}
      {#if lesson.lstext}<div style="margin-top:0.4rem;">{lesson.lstext}</div>{/if}
      {#if lesson.subst_text && lesson.subst_text !== lesson.lstext}
        <div class="dim" style="margin-top:0.3rem;">ℹ️ {lesson.subst_text}</div>
      {/if}
    </div>

    {#if cleanError}<div class="error-box">{cleanError}</div>{/if}

    {#if canRate}
      <label>Wie lief die Stunde?</label>
      <div class="checkins" class:three={!isSubst}>
        <button class="ci r3" class:active={rating === 3} disabled={busy} onclick={() => setRating(3)}>😀</button>
        <button class="ci r2" class:active={rating === 2} disabled={busy} onclick={() => setRating(2)}>😐</button>
        <button class="ci r1" class:active={rating === 1} disabled={busy} onclick={() => setRating(1)}>😟</button>
        {#if isSubst}
          <button class="ci r4" class:active={rating === 4} disabled={busy} onclick={() => setRating(4)} title="nur Aufsicht / kein neuer Stoff">👀</button>
        {/if}
      </div>

      <label style="margin-top:0.6rem;">Kommentar</label>
      <textarea bind:value={note} rows="3" placeholder="z.B. Hausaufgabe nicht verstanden, nochmal fragen…"></textarea>
      <button class="primary" style="width:100%; margin-top:0.5rem;" disabled={busy} onclick={saveNote}>
        Kommentar speichern
      </button>
    {:else if !isPast && !isCancelled && !wasAbsent}
      <div class="muted">Bewertung ist nach der Stunde möglich.</div>
    {/if}

    {#if canCatchUp}
      <button style="width:100%; margin-top:0.5rem;" disabled={busy} onclick={toggleCaughtUp}>
        {lesson.caught_up ? '✓ nachgeholt — rückgängig' : 'Versäumten Stoff als nachgeholt markieren'}
      </button>
    {/if}
  </div>
</div>

<style>
  .checkins { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 0.3rem; }
  .checkins.three { grid-template-columns: 1fr 1fr 1fr; }
  .ci {
    font-size: 1.3rem;
    padding: 0.4rem 0;
    min-height: 44px;
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
