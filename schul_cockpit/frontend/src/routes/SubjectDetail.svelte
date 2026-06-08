<script>
  import { api } from '../lib/api.js';

  let { accountId, subjectId } = $props();

  let data = $state(null);
  let loading = $state(true);
  let error = $state(null);

  async function load() {
    if (!accountId || !subjectId) return;
    loading = true;
    try {
      data = await api.get(`/api/accounts/${accountId}/subjects/${subjectId}`);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void subjectId; load(); });

  function ratingEmoji(r) {
    if (r === 1) return '😟';
    if (r === 2) return '😐';
    if (r === 3) return '😀';
    if (r === 4) return '👀';
    return '·';
  }
</script>

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if error}
  <div class="error-box">{error}</div>
{:else if data}
  <h2 style="margin-bottom:0.4rem;">
    {#if data.short}<span class="badge" style="font-weight:600; vertical-align:middle;">{data.short}</span>{/if}
    {data.name}
  </h2>
  <div class="dim" style="margin-bottom:0.6rem;">{data.timeline.length} Stunden in den letzten 120 Tagen</div>

  {#each data.timeline as l (l.lesson_id)}
    <div class="card compact">
      <div class="row between">
        <div>
          <span class="dim">{l.date} · {l.start_hhmm}</span>
          {#if l.code === 'cancelled'}<span class="badge cancelled">×</span>{/if}
          {#if l.was_absent}<span class="badge absent">🤒</span>{/if}
        </div>
        <span title="Verständnis">{ratingEmoji(l.checkin?.rating)}</span>
      </div>
      {#if l.lstext}<div style="margin-top:0.3rem;">{l.lstext}</div>{/if}
      {#if l.checkin?.note}<div class="muted" style="margin-top:0.3rem; font-style:italic;">„{l.checkin.note}"</div>{/if}
    </div>
  {/each}
{/if}
