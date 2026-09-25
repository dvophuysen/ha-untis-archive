<script>
  // Überblick über eine bewertete Übung (D207): was schon sitzt, wo die meisten
  // Punkte liegen blieben und was als Nächstes geübt wird.
  let { overall = null, losses = [] } = $props();
  const num = (x) => Number(x).toLocaleString('de-DE');
</script>

{#if overall?.strengths?.length || losses?.length || overall?.focus?.length}
  <div class="summary">
    {#if overall?.strengths?.length}
      <div><strong>Das kannst du schon</strong><ul>{#each overall.strengths as s, i (i)}<li>{s}</li>{/each}</ul></div>
    {/if}
    {#if losses?.length}
      <div><strong>Hier sind die meisten Punkte liegen geblieben</strong>
        <ul class="losses">{#each losses as l (l.kind)}<li><span class="pts">−{num(l.points)}</span> {l.label}</li>{/each}</ul></div>
    {/if}
    {#if overall?.focus?.length}
      <div><strong>Das übst du als Nächstes</strong><ol>{#each overall.focus as s, i (i)}<li>{s}</li>{/each}</ol></div>
    {/if}
  </div>
{/if}

<style>
  .summary { display: grid; gap: 8px; padding: var(--sp-2); border: 1px solid var(--border); border-radius: var(--r-md); }
  ul, ol { margin: 2px 0 0; padding-left: 1.2em; }
  .losses { list-style: none; padding: 0; }
  .losses li { display: grid; grid-template-columns: 3.2em 1fr; }
  .pts { font-weight: 700; color: var(--warn, #b26a00); font-variant-numeric: tabular-nums; }
</style>
