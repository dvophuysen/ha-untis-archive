<script>
  import {subjectStyle} from './subjectStyle.js';
  import { onMount } from 'svelte';
  import { api } from './api.js';
  let { accountId, schoolDay } = $props();
  let data = $state(null), error = $state(''), loading = $state(true), busy = $state(false);
  let request = 0;
  async function load(reset = false) {
    const account = accountId, day = schoolDay, ticket = ++request;
    if (reset) { data = null; busy = false; }
    if (!account || !day) { loading = false; return; }
    loading = true; error = '';
    try {
      const result = await api.get(`/api/accounts/${account}/packing/${day}`);
      if (ticket !== request || account !== accountId || day !== schoolDay) return;
      if (!Array.isArray(result.items) || !Array.isArray(result.schedule)) throw new Error('Die Packliste konnte nicht geladen werden.');
      data = result;
    } catch (e) { if (ticket === request) error = e.message || 'Die Packliste konnte nicht geladen werden.'; }
    finally { if (ticket === request) loading = false; }
  }
  $effect(() => { void accountId; void schoolDay; load(true); });
  onMount(() => {
    const resume = () => { if (!document.hidden && !busy) load(); };
    document.addEventListener('visibilitychange', resume);
    return () => { request++; document.removeEventListener('visibilitychange', resume); };
  });
  async function toggle(item) {
    if (busy || loading || !data?.can_write) return;
    const account = accountId, day = schoolDay, ticket = ++request;
    busy = true; error = '';
    try {
      const result = await api.put(`/api/accounts/${account}/packing/${day}`, {
        item_key: item.key, done: !item.done, revision: item.revision, plan_key: data.plan_key,
      });
      if (ticket === request && account === accountId && day === schoolDay) data = result;
    } catch (e) {
      if (ticket === request) error = e.message || 'Nicht gespeichert. Bitte noch einmal versuchen.';
    } finally { if (ticket === request) busy = false; }
  }
</script>

<section class="packing" aria-label="Stundenplan mit Materialcheck">
  {#if error}<p class="error-box" role="alert">{error}</p><button class="ghost" disabled={busy} onclick={() => load()}>Neu laden</button>{/if}
  {#if loading && !data}<p class="muted">Stundenplan wird geladen …</p>
  {:else if data}
    <p class="packing-hint">Material dabei? Hake die Fächer ab.</p>
    <div class="schedule">
      {#each data.schedule as lesson, i}
        {@const item = data.items.find(item => item.key === lesson.material_key)}
        <article class="schedule-row" class:cancelled={lesson.is_cancelled}>
          <div class="material-slot">
            {#if lesson.material_checkbox && item}<button class="pack-row" class:packed={item.done} aria-label={`Material für ${item.label}`} aria-pressed={item.done} disabled={busy || loading || !data.can_write} onclick={() => toggle(item)}><span class="pack-check" aria-hidden="true">{item.done ? '✓' : ''}</span></button>{/if}
          </div>
          <div class="schedule-info">
            <div class="schedule-head"><strong>{subjectStyle(lesson.subject_name || lesson.subject_short).emoji} {subjectStyle(lesson.subject_name || lesson.subject_short).name || 'Fach noch offen'}</strong><span class="schedule-time">{lesson.start_hhmm || 'Zeit offen'}{#if lesson.end_hhmm}–{lesson.end_hhmm}{/if}</span></div>
            {#if lesson.is_cancelled}<span class="change">❌ Entfällt</span>
            {:else}
              {#if lesson.room}<p class:change={lesson.is_room_substituted}>Raum {lesson.room}{#if lesson.is_room_substituted && lesson.room_orig}{' · statt '}{lesson.room_orig}{/if}</p>{/if}
              {#if lesson.teacher_name}<p class:change={lesson.is_teacher_substituted}>{lesson.teacher_name}{#if lesson.is_teacher_substituted && lesson.teacher_orig_name}{' · statt '}{lesson.teacher_orig_name}{/if}</p>{/if}
              {#if lesson.is_subject_substituted && lesson.subject_orig_name}<p class="change">Statt {lesson.subject_orig_name}</p>{/if}
              {#if lesson.is_irregular || lesson.is_teacher_substituted || lesson.is_subject_substituted}<span class="change">↺ Vertretung</span>{/if}
              {#if lesson.was_absent}<p>Als abwesend eingetragen</p>{/if}
              {#if lesson.lstext}<p class="lesson-topic">{lesson.lstext}</p>{/if}
            {/if}
          </div>
        </article>
      {:else}<p>Kein Unterricht eingetragen.</p>{/each}
    </div>
    <p class="pack-status" role="status">{busy ? 'Wird gespeichert …' : error ? 'Bitte den Packstand prüfen.' : data.status === 'packed' ? '✓ Material für alle Fächer abgehakt.' : data.items.length ? `${data.confirmed_count} von ${data.items.length} Fächern abgehakt` : ''}</p>
  {/if}
</section>

<style>
  .packing{margin-top:10px}.packing-hint{font-size:.85rem;color:var(--fg-muted);margin:0 0 8px}
  .schedule-row{display:flex;gap:8px;padding:12px 0;border-bottom:1px solid var(--border)}.schedule-row:last-child{border:0}
  .material-slot{flex:0 0 44px}.pack-row{display:flex;align-items:center;justify-content:center;width:44px;height:44px;padding:0;background:transparent;border:0}
  .pack-check{display:flex;align-items:center;justify-content:center;width:28px;height:28px;border:2px solid var(--fg-muted);border-radius:7px;font-weight:600}
  .packed .pack-check{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
  .schedule-info{min-width:0;flex:1}.schedule-head{display:flex;justify-content:space-between;gap:6px;flex-wrap:wrap}.schedule-head strong{overflow-wrap:anywhere}
  .schedule-time{font-size:.85rem;color:var(--fg-muted);font-variant-numeric:tabular-nums}.schedule-info p{margin:3px 0;font-size:.85rem;overflow-wrap:anywhere;color:var(--fg-muted)}
  .schedule-info .change{font-size:.85rem;font-weight:600;color:var(--fg)}.cancelled .schedule-head strong{text-decoration:line-through}.lesson-topic{white-space:pre-wrap}
  .pack-status{font-size:.9rem;margin:8px 0 0;color:var(--accent)}
</style>
