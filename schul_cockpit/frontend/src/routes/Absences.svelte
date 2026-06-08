<script>
  import { api } from '../lib/api.js';
  import { formatShortDate } from '../lib/format.js';

  let { accountId } = $props();

  let blocks = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let openOnly = $state(false);
  let busyLesson = $state(null);

  async function load() {
    if (!accountId) return;
    loading = true;
    error = null;
    try {
      blocks = (await api.get(`/api/accounts/${accountId}/absences`)).blocks;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void accountId; load(); });

  async function toggleCaught(block, lesson) {
    busyLesson = lesson.lesson_id;
    try {
      if (lesson.caught_up) {
        await api.delete(`/api/accounts/${accountId}/lessons/${lesson.lesson_id}/caught-up`);
        lesson.caught_up = false;
        block.caught_up_count -= 1;
        block.open_count += 1;
      } else {
        await api.post(`/api/accounts/${accountId}/lessons/${lesson.lesson_id}/caught-up`, {});
        lesson.caught_up = true;
        block.caught_up_count += 1;
        block.open_count -= 1;
      }
      blocks = [...blocks];
    } catch (e) {
      error = e.message;
    } finally {
      busyLesson = null;
    }
  }

  function blockRange(b) {
    if (b.start === b.end) return formatShortDate(b.start);
    return `${formatShortDate(b.start)} – ${formatShortDate(b.end)}`;
  }

  const visibleBlocks = $derived(
    openOnly
      ? blocks.filter((b) => b.open_count > 0).map((b) => ({
          ...b,
          lessons: b.lessons.filter((l) => !l.caught_up),
        }))
      : blocks,
  );

  const totalOpen = $derived(blocks.reduce((s, b) => s + b.open_count, 0));
</script>

<div class="row between" style="margin: 0.3rem 0.2rem 0.6rem; align-items:center;">
  <div class="muted">
    {#if totalOpen > 0}<strong>{totalOpen}</strong> Stunden noch nachzuholen{:else}Alles nachgeholt 🎉{/if}
  </div>
  <button class:primary={openOnly} onclick={() => (openOnly = !openOnly)} style="font-size:0.85rem; min-height:38px;">
    {openOnly ? '✓ nur offen' : 'nur offen'}
  </button>
</div>

{#if error}<div class="error-box">{error}</div>{/if}

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if visibleBlocks.length === 0}
  <div class="empty">{openOnly ? 'Nichts Offenes — alles nachgeholt 🎉' : 'Keine Fehlzeiten erfasst.'}</div>
{:else}
  {#each visibleBlocks as block (block.start)}
    <div class="card">
      <div class="row between" style="align-items:flex-start;">
        <div>
          <strong>{blockRange(block)}</strong>
          {#if block.days > 1}<span class="dim"> · {block.days} Tage</span>{/if}
          <div class="muted" style="margin-top:1px;">
            {#if block.reasons.length}{block.reasons.join(', ')}{:else}—{/if}
            {#if block.is_excused}<span class="badge" style="margin-left:0.3rem;">entschuldigt</span>
            {:else}<span class="badge" style="background:var(--rating-1); color:#fff; border-color:transparent; margin-left:0.3rem;">unentschuldigt</span>{/if}
          </div>
        </div>
        <span class="badge" class:done-badge={block.open_count === 0}>
          {block.caught_up_count}/{block.total}
        </span>
      </div>

      <div style="margin-top:0.5rem;">
        {#each block.lessons as lesson (lesson.lesson_id)}
          <div class="miss-row">
            <button
              class="task-checkbox"
              class:done={lesson.caught_up}
              disabled={busyLesson === lesson.lesson_id}
              onclick={() => toggleCaught(block, lesson)}
              aria-label={lesson.caught_up ? 'nachgeholt rückgängig' : 'als nachgeholt markieren'}
            >{lesson.caught_up ? '✓' : ''}</button>
            <div style="flex:1; min-width:0;">
              <div class="row gap-sm" style="align-items:baseline;">
                <span style="font-weight:600;">{lesson.subject_short || lesson.subject_name || '—'}</span>
                <span class="dim">{formatShortDate(lesson.date)} · {lesson.start_hhmm}</span>
              </div>
              {#if lesson.lstext}
                <div class="muted" style="font-size:0.85rem; margin-top:1px;" class:struck={lesson.caught_up}>{lesson.lstext}</div>
              {:else}
                <div class="dim" style="font-size:0.8rem; margin-top:1px;">kein Lehrstoff erfasst</div>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    </div>
  {/each}
{/if}

<style>
  .miss-row {
    display: flex;
    gap: 0.6rem;
    align-items: flex-start;
    padding: 0.5rem 0;
    border-top: 1px solid var(--border);
  }
  .miss-row:first-child { border-top: none; }
  .struck { text-decoration: line-through; color: var(--fg-dim); }
  .done-badge { background: var(--rating-3); color: #fff; border-color: transparent; }
</style>
