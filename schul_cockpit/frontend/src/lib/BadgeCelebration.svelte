<script>
  // Die große Feier einer neuen Abzeichenstufe (D203): einmal, bildschirmfüllend,
  // mit Konfetti. „Still“ (Personalisierung) und reduzierte Bewegung feiern
  // ruhiger, aber genauso deutlich.
  import { onMount } from 'svelte';
  let { item, still = false, onclose = () => {} } = $props();
  const LEVEL_COLOR = { Bronze: '#c8793b', Silber: '#9aa4ad', Gold: '#e2b007', Platin: '#58a6b8', Diamant: '#7a5cff' };
  const reduced = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const quiet = $derived(still || reduced);
  const COLORS = ['#e2b007', '#e8505b', '#2f9e8f', '#5b8def', '#f28c28', '#9b59b6'];
  const bits = $derived.by(() => quiet ? [] : Array.from({ length: 90 }, (_, i) => ({
    left: Math.random() * 100, delay: Math.random() * 1.2, dur: 2.4 + Math.random() * 1.8,
    color: COLORS[i % COLORS.length], size: 6 + Math.random() * 8, turn: Math.random() * 720 - 360,
  })));
  let button = $state(null);
  onMount(() => {
    button?.focus();
    try { if (!quiet) navigator.vibrate?.([80, 60, 120]); } catch { /* ohne Vibration */ }
  });
</script>

<div class="party" role="dialog" aria-modal="true" aria-labelledby="party-title">
  {#each bits as b, i (i)}<i class="bit" style:left={`${b.left}%`} style:background={b.color} style:width={`${b.size}px`} style:height={`${b.size * 0.45}px`}
    style:animation-delay={`${b.delay}s`} style:animation-duration={`${b.dur}s`} style:--turn={`${b.turn}deg`}></i>{/each}
  <div class="card">
    <p class="kicker">🎉 Neues Abzeichen! 🎉</p>
    <div class="medal" class:pop={!quiet} style:--level={LEVEL_COLOR[item.level_name] ?? '#e2b007'}><span aria-hidden="true">{item.emoji}</span></div>
    <h2 id="party-title">{item.name} <span class="lvl" style:color={LEVEL_COLOR[item.level_name]}>{item.level_name}</span></h2>
    <p class="what">{item.what}: <b>{item.value}</b></p>
    {#if item.next_level}<p class="next">Als Nächstes: <b>{item.next_level}</b> bei {item.next_at}.</p>{:else}<p class="next">Das ist die höchste Stufe. Wahnsinn!</p>{/if}
    <div class="acts">
      <button class="primary" bind:this={button} onclick={() => onclose(false)}>Juhu!</button>
      <button class="ghost" onclick={() => onclose(true)}>Alle Abzeichen ansehen</button>
    </div>
  </div>
</div>

<style>
  .party{position:fixed;inset:0;z-index:90;display:grid;place-items:center;padding:var(--sp-3);background:radial-gradient(circle at 50% 38%,rgba(255,205,70,.55),rgba(8,10,20,.92) 62%);overflow:hidden}
  .card{position:relative;z-index:2;max-width:22rem;width:100%;text-align:center;display:grid;gap:var(--sp-2);justify-items:center;padding:var(--sp-4) var(--sp-3);border-radius:var(--r-lg,20px);background:var(--bg-card);color:var(--fg);box-shadow:0 20px 60px rgba(0,0,0,.45)}
  .kicker{margin:0;font-size:1.15rem;font-weight:900;letter-spacing:.06em;text-transform:uppercase;color:var(--accent)}
  .medal{width:128px;height:128px;border-radius:50%;display:grid;place-items:center;font-size:64px;background:radial-gradient(circle at 35% 30%,#fff8,transparent 45%),var(--level);box-shadow:0 0 0 8px color-mix(in srgb,var(--level) 35%,transparent),0 0 40px var(--level)}
  .medal.pop{animation:pop .9s cubic-bezier(.2,1.6,.4,1) both}
  h2{margin:0;font-size:1.6rem;line-height:1.2}
  .lvl{white-space:nowrap}
  .what,.next{margin:0}
  .acts{display:grid;gap:6px;width:100%}
  .acts button{min-height:48px;font-size:1.05rem}
  .bit{position:absolute;top:-24px;z-index:1;border-radius:2px;animation:fall linear infinite}
  @keyframes fall{0%{transform:translateY(0) rotate(0)}100%{transform:translateY(110vh) rotate(var(--turn))}}
  @keyframes pop{0%{transform:scale(.2) rotate(-25deg);opacity:0}70%{transform:scale(1.12) rotate(6deg);opacity:1}100%{transform:scale(1) rotate(0)}}
</style>
