<script>
  // Ein Untis-Text, in dem jede genannte Buchstelle ein Link ist, in der Farbe
  // ihres Stands: grün liegt vor und ist gelesen, gelb wird geholt oder
  // gelesen, rot fehlt und muss fotografiert werden. Ohne Segmente vom
  // Server steht der Text so da, wie er ist.
  let { segments = null, text = '', subject = '', taskId = null } = $props();

  const STATE_TITLE = {
    ready: 'liegt vor und ist gelesen',
    pending: 'wird gerade geholt oder gelesen',
    missing: 'liegt nicht vor, muss fotografiert werden',
  };

  function target(seg) {
    if (seg.material_id) return `#/materialien?material=${seg.material_id}`;
    if (seg.state === 'missing') {
      return taskId ? `#/materialien/${encodeURIComponent(subject ?? '')}/${taskId}` : `#/materialien/${encodeURIComponent(subject ?? '')}`;
    }
    return '#/materialien';
  }
</script>

{#if segments?.length}
  <span class="source-text">{#each segments as seg}{#if seg.pages && seg.state}<a class="src {seg.state}" href={target(seg)} title={`${seg.label}: ${STATE_TITLE[seg.state]}`} onclick={(e) => e.stopPropagation()}>{seg.text}</a>{:else}{seg.text}{/if}{/each}</span>
{:else}
  <span class="source-text">{text}</span>
{/if}

<style>
  .source-text { white-space: pre-wrap; overflow-wrap: anywhere; }
  .src { font-weight: 600; text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 2px; border-radius: 3px; padding: 0 1px; }
  .src.ready { color: var(--rating-3); text-decoration-color: var(--rating-3); }
  .src.pending { color: var(--warm, #b26a00); text-decoration-color: var(--warm, #b26a00); }
  .src.missing { color: var(--rating-1); text-decoration-color: var(--rating-1); }
</style>
