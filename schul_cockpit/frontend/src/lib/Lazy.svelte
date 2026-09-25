<script module>
  // Einmal geladene Seiten stehen beim nächsten Öffnen sofort da, ohne Spinner.
  const loaded = new Map();
</script>
<script>
  // Lädt eine selten genutzte Seite erst beim Öffnen (D177). `load` ist eine
  // stabile Funktion, die das Modul importiert; alle weiteren Props gehen durch.
  // Scheitert der Import, liegt meist ein Add-on-Update dazwischen: Die alten
  // Dateinamen gibt es nicht mehr. Dann einmal neu laden, statt stehen zu bleiben.
  import { reloadOnce } from './reload.js';
  let { load, ...rest } = $props();
  // svelte-ignore state_referenced_locally
  let Comp = $state(loaded.get(load) ?? null), failed = $state(false);
  $effect(() => {
    let alive = true;
    const fn = load;
    failed = false;
    fn().then((m) => { loaded.set(fn, m.default); if (alive) Comp = m.default; })
      .catch(() => { if (alive && !reloadOnce()) failed = true; });
    return () => { alive = false; };
  });
</script>
{#if Comp}<Comp {...rest} />{:else if failed}<div class="error-box" role="alert">Die Seite ließ sich nicht laden. Bitte die App neu öffnen.</div>{:else}<div class="empty"><span class="spinner"></span></div>{/if}
