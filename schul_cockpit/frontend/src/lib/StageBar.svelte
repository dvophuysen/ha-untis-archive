<script>
  // Verteilung der Lernstand-Stufen als Balken (D176). counts: {stufe: anzahl}.
  let { counts = {}, order = ['gefestigt', 'sitzt', 'wackelt', 'angefangen', 'neu'], label = '', height = 8 } = $props();
  const total = $derived(order.reduce((a, k) => a + (counts[k] || 0), 0));
</script>
<span class="stage-bar" style:height={`${height}px`} role="img" aria-label={label || order.filter(k => counts[k]).map(k => `${counts[k]} ${k}`).join(', ')}>
  {#if total}{#each order as k (k)}{#if counts[k]}<i class={`st-${k}`} style:flex={counts[k]}></i>{/if}{/each}{/if}
</span>
<style>
  .stage-bar{display:flex;gap:2px;border-radius:var(--r-pill);overflow:hidden;background:var(--st-neu)}
  i{display:block;height:100%}
</style>
