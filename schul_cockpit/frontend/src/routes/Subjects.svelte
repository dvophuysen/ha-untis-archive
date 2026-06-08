<script>
  import { api } from '../lib/api.js';
  import { formatShortDate } from '../lib/format.js';

  let { accountId, navigate } = $props();

  function urgencyLabel(g) {
    if (g.days_until_next === 0) return `noch heute · ${g.next_start_hhmm}`;
    if (g.days_until_next === 1) return `morgen · ${g.next_start_hhmm}`;
    if (g.days_until_next === 2) return `übermorgen · ${g.next_start_hhmm}`;
    return `${formatShortDate(g.next_date)} · ${g.next_start_hhmm}`;
  }

  let subjects = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let suggestions = $state(null);

  async function load() {
    if (!accountId) return;
    loading = true;
    try {
      const [subs, sug] = await Promise.all([
        api.get(`/api/accounts/${accountId}/subjects`),
        api.get(`/api/accounts/${accountId}/oral-suggestions`),
      ]);
      subjects = subs.subjects;
      suggestions = sug;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void accountId; load(); });
</script>

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if error}
  <div class="error-box">{error}</div>
{:else}
  {#if suggestions && suggestions.groups.length > 0}
    <div class="section-title">🎤 Vor der nächsten Stunde nochmal anschauen</div>
    <div class="banner">
      Themen, die zuletzt schwer waren — geordnet danach, bei welchem Fach
      die nächste Stunde am dringendsten ist.
    </div>
    {#each suggestions.groups as g (g.subject_id)}
      <div class="card">
        <div class="row between" style="margin-bottom:0.4rem;">
          <div class="row gap-sm" style="min-width:0;">
            {#if g.subject_short}<span class="badge" style="font-weight:600;">{g.subject_short}</span>{/if}
            <strong>{g.subject_name}</strong>
          </div>
          <span class="badge" class:soon-badge={g.days_until_next <= 1}>
            ⏳ {urgencyLabel(g)}
          </span>
        </div>
        {#each g.items as it (it.lesson_id)}
          <div class="muted" style="border-top:1px solid var(--border); padding-top:0.4rem; margin-top:0.4rem;">
            <span class="dim">{formatShortDate(it.date)} · {it.rating === 1 ? '😟' : '😐'}</span><br>
            {it.lstext || it.note || '—'}
          </div>
        {/each}
      </div>
    {/each}
  {/if}

  <div class="section-title">Fächer</div>
  {#each subjects as s}
    <button class="card compact" style="width:100%; text-align:left;" onclick={() => navigate('subject', s.subject_id)}>
      <div class="row between">
        <div class="row gap-sm" style="min-width:0;">
          {#if s.short}<span class="badge" style="font-weight:600;">{s.short}</span>{/if}
          <strong style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{s.name}</strong>
        </div>
        <span class="dim" style="white-space:nowrap;">{s.lessons_total}×</span>
      </div>
    </button>
  {/each}
{/if}

<style>
  .soon-badge {
    background: var(--rating-2);
    color: #fff;
    border-color: transparent;
  }
</style>
