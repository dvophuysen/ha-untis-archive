<script>
  import { api } from '../lib/api.js';

  let { accountId, navigate } = $props();

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
  {#if suggestions && suggestions.groups.some((g) => g.items.length > 0)}
    <div class="section-title">🎤 Heute mündlich punkten</div>
    {#each suggestions.groups as g}
      {#if g.items.length > 0}
        <div class="card">
          <div class="row between" style="margin-bottom:0.4rem;">
            <strong>{g.subject}</strong>
          </div>
          {#each g.items as it}
            <div class="muted" style="border-top:1px solid var(--border); padding-top:0.4rem; margin-top:0.4rem;">
              <span class="dim">{it.date} · {it.rating === 1 ? '😟' : '😐'}</span><br>
              {it.lstext || it.note || '—'}
            </div>
          {/each}
        </div>
      {/if}
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
