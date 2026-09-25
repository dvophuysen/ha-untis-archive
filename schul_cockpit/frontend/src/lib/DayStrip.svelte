<script>
  // Ein Schultag als Leiste (D170, D184): Beginn links, Ende rechts, je Stunde
  // ein Kästchen mit Fachkürzel. Ausfall gestrichelt und durchgestrichen,
  // Vertretung und Arbeit farbig umrandet, die laufende Stunde markiert,
  // vergangene blass. Gelb, wenn der Tag später beginnt oder früher endet.
  // Eingabe ist ein Tag aus family_board.schedule_day(); `slots` legt mehrere
  // Tage auf gemeinsame Zeitfenster (slotsOf).
  import { slotsOf, withGaps, periodTitle } from './dayStrip.js';

  let { day, slots = null } = $props();
  const cells = $derived(withGaps(day, slots || slotsOf([day])));
</script>

<span class="strip">
  <span class="t" class:devt={day.late_start}>{day.start ?? day.planned_start ?? ''}</span>
  <span class="ps">
    {#each cells as p (p.key)}
      {#if p.gap}<i class="gap"></i>
      {:else if p.empty}<i class="empty"></i>
      {:else if p.parallel}
        <span class="par">
          {#each p.parallel as q, n (n)}
            <i class:x={q.state === 'cancelled'} class:sub={q.state === 'sub'} class:arbeit={q.exam}
               class:now={q.now} class:past={q.past} class:absent={q.absent} title={periodTitle(q)}>{q.short}</i>
          {/each}
        </span>
      {:else}<i class:x={p.state === 'cancelled'} class:sub={p.state === 'sub'} class:arbeit={p.exam}
                class:now={p.now} class:past={p.past} class:absent={p.absent} title={periodTitle(p)}>{p.short}</i>{/if}
    {/each}
  </span>
  <span class="t" class:devt={day.early_end || day.all_cancelled}>{day.all_cancelled ? 'frei' : (day.end ?? '')}</span>
</span>

<style>
  .strip { display: flex; align-items: center; gap: 6px; min-width: 0; }
  .t { font-size: var(--fs-xs); color: var(--fg-muted); white-space: nowrap; font-variant-numeric: tabular-nums; min-width: 2.6em; }
  .t:last-child { text-align: right; }
  .t.devt { color: var(--warn-fg); font-weight: 700; }
  .ps { display: flex; gap: 3px; flex: 1; min-width: 0; align-items: stretch; }
  .par { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  i { flex: 1; min-width: 0; overflow: hidden; font-style: normal; text-align: center; font-size: var(--fs-xs); font-weight: 650;
    padding: 5px 0; border-radius: var(--r-sm); background: color-mix(in srgb, var(--fg) 8%, var(--bg-card)); color: var(--fg); }
  .par i { padding: 1px 0; }
  i.gap { flex: 0.35; background: transparent; }
  i.empty { background: transparent; }
  i.x { background: transparent; border: 1px dashed var(--cancelled); color: var(--cancelled); text-decoration: line-through; }
  i.sub { outline: 2px solid var(--substitution); outline-offset: -2px; color: var(--substitution-fg); }
  i.arbeit { outline: 2px solid var(--exam); outline-offset: -2px; }
  i.now { box-shadow: 0 0 0 2px var(--accent) inset; }
  i.past { opacity: 0.5; }
  i.absent { text-decoration: underline dotted; }
</style>
