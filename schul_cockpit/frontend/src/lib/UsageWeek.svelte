<script>
  // Nutzungsbericht für Eltern: beschreibt, wie die App genutzt wurde, bewertet
  // nicht. Jede Auffälligkeit nennt Beleg, mögliche Deutung und was die App
  // nicht sieht. Nur in der Familienansicht, also nur für Eltern.
  import { api } from './api.js';
  let { accountId } = $props();
  let data = $state(null), error = $state(''), opened = $state(false);
  let request = 0;
  $effect(() => {
    const account = accountId, ticket = ++request;
    data = null; error = '';
    if (!account) return;
    api.get(`/api/accounts/${account}/usage-week`).then(r => { if (ticket === request) data = r; })
      .catch(e => { if (ticket === request) error = e.message; });
  });
</script>

<div class="block usage-week">
  <button class="usage-head" aria-expanded={opened} onclick={() => opened = !opened}>
    <span>
      <h3>So wurde die App genutzt</h3>
      {#if data}<small class:attention={data.warnings.length > 0}>{data.headline}</small>{/if}
    </span>
    <span class="chevron" class:opened>›</span>
  </button>
  {#if error}<p class="error-box" role="alert">{error}</p>
  {:else if !data}<p class="muted">Lade …</p>
  {:else if opened}
    <ul>{#each data.lines as line}<li>{line}</li>{/each}</ul>
    {#if data.warnings.length}
      <h4>Auffällig</h4>
      {#each data.warnings as w}
        <div class="warning">
          <strong>{w.title}</strong>
          <p><span>Beleg:</span> {w.evidence}</p>
          <p><span>Mögliche Deutung:</span> {w.meaning}</p>
          <p><span>Nicht sichtbar:</span> {w.unseen}</p>
        </div>
      {/each}
    {/if}
    {#if data.checkins.uniform_series}
      <p class="muted">Hinweis: {data.checkins.uniform_series} Mal wurden mindestens vier Stunden kurz hintereinander gleich bewertet. Das kann eine ehrliche Tagesrückschau sein oder schnelles Durchtippen.</p>
    {/if}
    <p class="muted">Beschreibt die Nutzung, bewertet sie nicht. Zeiten aus den Aktionen in der App; was auf Papier oder am Gerät der Eltern geschah, fehlt oder zählt zum Kind.</p>
  {/if}
</div>

<style>
  .usage-week { margin-top: 8px; }
  .usage-head { display: flex; justify-content: space-between; align-items: center; width: 100%; border: 0; background: transparent; padding: 4px 0; color: var(--fg); text-align: left; min-height: 44px; }
  .usage-head h3 { margin: 0; font-size: 0.95rem; }
  .usage-head small { display: block; font-size: 0.8rem; color: var(--fg-muted); margin-top: 2px; }
  .usage-head small.attention { color: var(--fg); }
  .chevron { color: var(--accent); font-size: 1.3rem; transition: transform .15s; }
  .chevron.opened { transform: rotate(90deg); }
  ul { margin: 4px 0 0; padding-left: 18px; font-size: 0.9rem; line-height: 1.4; }
  li { margin: 3px 0; }
  h4 { margin: 12px 0 4px; font-size: 0.9rem; }
  .warning { border-left: 3px solid var(--accent); padding: 4px 0 4px 10px; margin: 8px 0; font-size: 0.88rem; }
  .warning p { margin: 2px 0; }
  .warning span { color: var(--fg-muted); }
  .muted { font-size: 0.82rem; color: var(--fg-muted); }
</style>
