<script>
  // Eine Legende für die Lernstand-Stufen, überall gleich (D176).
  let { stages = ['neu', 'angefangen', 'wackelt', 'sitzt', 'gefestigt'], labels = {} } = $props();
</script>
<p class="stage-legend">{#each stages as k (k)}<span><i class={`st-${k}`} aria-hidden="true"></i>{labels[k] ?? k}</span>{/each}</p>
<style>
  .stage-legend{display:flex;flex-wrap:wrap;gap:var(--sp-2) var(--sp-3);font-size:var(--fs-xs);color:var(--fg-muted);margin:var(--sp-3) 2px}
  span{display:inline-flex;align-items:center;gap:5px}
  i{display:inline-block;width:12px;height:12px;border-radius:3px}
</style>
