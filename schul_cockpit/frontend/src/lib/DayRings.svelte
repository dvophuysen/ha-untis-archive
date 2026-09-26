<script>
  // Die vier Ringe des Tages (Aufgaben, Lernen, Tasche, Feedback), gleich auf
  // „Heute“ und auf der Familienkarte der Eltern. `items`: je Ring key, label,
  // icon, done, total, full und text (die Zeile unter dem Namen).
  let { items = [], onpick = () => {} } = $props();
  const ringStyle = (d, n) => `background:conic-gradient(var(--accent) ${n ? Math.round(d / n * 100) : 0}%, var(--bg-elevated) 0)`;
</script>

<div class="rings">
  {#each items as r (r.key)}
    <button class="ring-btn" class:full={r.full} onclick={() => onpick(r.key)} aria-label={`${r.label}: ${r.text}`}><span class="ring" style={ringStyle(r.done, r.total)}><span>{r.full ? '✓' : r.icon}</span></span><b>{r.label}</b><small>{r.text}</small></button>
  {/each}
</div>

<style>
  .rings{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--sp-2);margin-bottom:var(--sp-2)}
  .ring-btn{display:grid;justify-items:center;gap:3px;padding:var(--sp-2) 4px;border-radius:var(--r-md);min-height:100px;background:var(--bg-card)}
  .ring{width:50px;height:50px;border-radius:50%;display:grid;place-items:center}
  .ring span{width:39px;height:39px;border-radius:50%;background:var(--bg-card);display:grid;place-items:center;font-size:1.1rem}
  .ring-btn.full .ring span{background:var(--accent);color:var(--accent-fg);font-weight:800}
  .ring-btn b{font-size:var(--fs-xs)}.ring-btn small{font-size:.72rem;color:var(--fg-muted)}
</style>
