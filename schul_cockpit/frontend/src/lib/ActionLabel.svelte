<script>
  let { kind = 'navigate', label = '' } = $props();
</script>
<span class="action-label">
  {#if kind === 'chat'}
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-3 3V11.5A8.5 8.5 0 0 1 9.5 3h3a8.5 8.5 0 0 1 8.5 8.5Z" /></svg>
  {/if}
  {#if label}<span>{label}</span>{/if}
  {#if kind === 'navigate'}
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m9 5 7 7-7 7" /></svg>
  {/if}
</span>
<style>
  .action-label{display:inline-flex;align-items:center;gap:.35em;vertical-align:middle;font:inherit}
  svg{flex:none;width:1.05em;height:1.05em}
</style>
