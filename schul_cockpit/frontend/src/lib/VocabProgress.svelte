<script>
  let { progress, label = 'Bedeutung' } = $props();
  const groups = [ ['wrong', 'Nur falsch'], ['uncertain', 'Noch unsicher'], ['secure', 'Sicher'], ['new', 'Noch nicht geübt'] ];
  const description = $derived(progress ? groups.map(([key, name]) => `${progress[key]} ${name}`).join(' · ') : '');
</script>
{#if progress?.total}
  <div class="vocab-progress">
    <div class="bar" role="img" aria-label={`${label}: ${description}`}>
      {#each groups as [key, name]}
        {#if progress[key]}<span class={key} style:width={`${100 * progress[key] / progress.total}%`} title={`${progress[key]} ${name}`}></span>{/if}
      {/each}
    </div>
    <small>{label}: {description}</small>
  </div>
{/if}
<style>
  .vocab-progress { width:100%; min-width:0; }
  .bar { display:flex; height:10px; width:100%; border-radius:5px; overflow:hidden; background:#d5d9de; }
  .bar span { display:block; min-width:0; }
  .wrong { background:#c83d4b; } .uncertain { background:#d99a20; }
  .secure { background:#258459; } .new { background:#b7bec7; }
  small { display:block; margin-top:.3rem; font-size:.72rem; line-height:1.45; }
</style>
