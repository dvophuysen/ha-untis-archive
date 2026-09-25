<script>
  // Lädt eine selten genutzte Seite erst beim Öffnen (D177). `load` ist eine
  // stabile Funktion, die das Modul importiert; alle weiteren Props gehen durch.
  let { load, ...rest } = $props();
  let Comp = $state(null), failed = $state(false);
  $effect(() => {
    let alive = true;
    failed = false;
    load().then((m) => { if (alive) Comp = m.default; }).catch(() => { if (alive) failed = true; });
    return () => { alive = false; };
  });
</script>
{#if Comp}<Comp {...rest} />{:else if failed}<div class="error-box" role="alert">Die Seite ließ sich nicht laden. Bitte die App neu öffnen.</div>{:else}<div class="empty"><span class="spinner"></span></div>{/if}
