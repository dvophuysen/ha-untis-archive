<script>
  // Rückmeldung zu einer Aufgabe, aus der das Kind lernt (D207): was Punkte
  // brachte, wo und warum Punkte verloren gingen, was dort hätte stehen müssen,
  // die volle Lösung und der nächste Schritt. Ältere Auswertungen ohne
  // Einzelteile zeigen ihre Begründung wie bisher.
  let { f, most, solution = '', criteria = '', practiceHref = '' } = $props();
  const num = (x) => Number(x).toLocaleString('de-DE');
  const lost = $derived((f?.lost ?? []).filter((x) => x.points > 0));
  const earned = $derived((f?.earned ?? []).filter((x) => x.points > 0));
  const full = $derived(f && !f.uncertain && f.points >= most);
</script>

{#if f}
  <div class="fb">
    {#if f.loesung_falsch}<p class="qa" role="note">Hier war die Musterlösung der App fehlerhaft. Gewertet wurde das fachlich Richtige{#if f.loesung_hinweis}: {f.loesung_hinweis}{:else}.{/if}</p>{/if}
    {#if f.transcription}<details class="read"><summary>So wurde deine Antwort gelesen</summary><p class="preserve">{f.transcription}</p></details>{/if}
    {#if earned.length}
      <div class="part ok">
        <strong>Das war richtig</strong>
        <ul>{#each earned as x, i (i)}<li><span class="pts plus">+{num(x.points)}</span> {x.text}</li>{/each}</ul>
      </div>
    {/if}
    {#if lost.length}
      <div class="part miss">
        <strong>Hier hast du Punkte verloren</strong>
        <ul>
          {#each lost as x, i (i)}
            <li><span class="pts minus">−{num(x.points)}</span> {x.why}<span class="fix"><b>So hättest du die Punkte bekommen:</b> <span class="preserve">{x.fix}</span></span></li>
          {/each}
        </ul>
      </div>
    {:else if !earned.length && f.rationale}
      <p>{f.rationale}</p>
    {/if}
    {#if (earned.length || lost.length) && f.rationale && !full}<p class="dim">{f.rationale}</p>{/if}
    {#if f.model && !full}<details class="model"><summary>So wäre es voll gewesen</summary><p class="preserve">{f.model}</p></details>{/if}
    {#if f.next_step}
      <p class="next"><strong>Nächster Schritt:</strong> {f.next_step}
        {#if practiceHref && !full}<a class="practice" href={practiceHref}>Mit dem Mentor üben</a>{/if}</p>
    {/if}
    {#if solution}<details><summary>Lösung und Punktkriterien</summary><p class="preserve">{solution}</p>{#if criteria}<p class="preserve dim">{criteria}</p>{/if}</details>{/if}
  </div>
{/if}

<style>
  .fb { display: grid; gap: 6px; }
  .qa { margin: 0; padding: 6px 10px; border-radius: 8px; background: var(--warm-soft, #fef3c7); font-size: var(--fs-sm); }
  .fb p { margin: 0; }
  .part { display: grid; gap: 2px; padding: 6px 8px; border-radius: var(--r-sm); }
  .part.ok { background: color-mix(in srgb, var(--ok, #2e7d32) 9%, transparent); }
  .part.miss { background: color-mix(in srgb, var(--warn, #b26a00) 10%, transparent); }
  ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; }
  li { display: grid; grid-template-columns: 3.2em 1fr; column-gap: 4px; }
  .pts { font-weight: 700; font-variant-numeric: tabular-nums; }
  .plus { color: var(--ok, #2e7d32); }
  .minus { color: var(--warn, #b26a00); }
  .fix { grid-column: 2; display: block; margin-top: 2px; }
  .next { display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: baseline; }
  .practice { font-weight: 600; }
</style>
