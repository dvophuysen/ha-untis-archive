<script>
  // Kompaktes Raster Stunden × Schultage (D184) mit denselben Markierungen wie
  // die Leiste: Ausfall gestrichelt und durchgestrichen, Arbeit und Vertretung
  // umrandet, heute hervorgehoben. Parallele Stunden stehen beide in ihrer
  // Zelle, eine Doppelstunde füllt zwei Zeilen (gridLayout).
  import { gridLayout } from './dayStrip.js';
  import { subjectStyle } from './subjectStyle.js';
  import LessonDetail from './LessonDetail.svelte';

  let { accountId, days = [], onsaved = () => {} } = $props();
  const layout = $derived(gridLayout(days));
  const todayCol = $derived(days.findIndex((d) => d.is_today));
  let detail = $state(null);

  const short = (l) => l.subject_short || subjectStyle(l.subject_name).name.slice(0, 4) || '?';
  const isSub = (l) => !l.is_cancelled && !!(l.is_irregular || l.is_teacher_substituted || l.is_subject_substituted);
  const title = (l, end) => {
    const st = subjectStyle(l.subject_name || l.subject_short);
    return `${st.name}, ${l.start_hhmm}–${end}${l.is_cancelled ? ', fällt aus' : isSub(l) ? ', Vertretung' : ''}`
      + `${l.is_room_substituted && l.room ? `, Raum ${l.room}` : ''}${l.exam_marked ? ', Arbeit' : ''}${l.was_absent ? ', gefehlt' : ''}`;
  };
</script>

<div class="wg" style={`grid-template-columns: 2.6em repeat(${days.length}, minmax(0, 1fr)); grid-template-rows: auto repeat(${layout.rows.length}, minmax(44px, auto));`}>
  {#if todayCol >= 0 && layout.rows.length}
    <div class="today-col" style={`grid-column: ${todayCol + 2}; grid-row: 1 / span ${layout.rows.length + 1};`} aria-hidden="true"></div>
  {/if}
  <div class="corner"></div>
  {#each days as d, i (d.date)}
    <div class="head" class:today={d.is_today} style={`grid-column: ${i + 2}; grid-row: 1;`}>
      <b>{d.label.slice(0, 2)}</b><span>{d.label.slice(3, 6)}</span>
    </div>
  {/each}
  {#each layout.rows as r, row (r.start)}
    <div class="time" style={`grid-column: 1; grid-row: ${row + 2};`}>{r.start}</div>
  {/each}
  {#each layout.cells as c (c.key)}
    {@const end = (c.more.at(-1) || c.lessons[0]).end_hhmm}
    <div class="cell" style={`grid-column: ${c.col + 2}; grid-row: ${c.row + 2} / span ${c.span};`}>
      {#each c.lessons as l (l.id)}
        <button class="les" class:x={l.is_cancelled} class:sub={isSub(l)} class:arbeit={l.exam_marked}
                class:absent={l.was_absent && !l.is_cancelled} aria-label={title(l, c.lessons.length === 1 ? end : l.end_hhmm)}
                onclick={() => (detail = l)}>{short(l)}{#if c.span > 1}<small>{c.span} Std.</small>{/if}</button>
      {/each}
    </div>
  {/each}
</div>
{#if !layout.rows.length}<p class="muted">Für diese Tage ist noch kein Stundenplan da.</p>{/if}
{#if detail}<LessonDetail {accountId} lesson={detail} onclose={() => (detail = null)} {onsaved} />{/if}

<style>
  .wg { display: grid; gap: 3px; position: relative; }
  .today-col { background: color-mix(in oklab, var(--accent) 12%, transparent); border-radius: var(--r-sm); margin: -2px; }
  .head { text-align: center; font-size: var(--fs-xs); color: var(--fg-muted); display: grid; line-height: 1.2; padding: var(--sp-1) 0; position: relative; }
  .head b { color: var(--fg); }
  .head.today b, .head.today span { color: var(--accent); }
  .time { font-size: var(--fs-xs); color: var(--fg-muted); font-variant-numeric: tabular-nums; align-self: start; padding-top: var(--sp-1); }
  .cell { display: flex; flex-direction: column; gap: 2px; min-width: 0; position: relative; }
  .les { flex: 1; min-width: 0; min-height: 40px; padding: 2px 0; border: 0; border-radius: var(--r-sm); font-size: var(--fs-xs); font-weight: 650;
    background: color-mix(in srgb, var(--fg) 8%, var(--bg-card)); color: var(--fg); overflow: hidden; display: grid; place-content: center; }
  .les small { font-size: var(--fs-xs); font-weight: 500; color: var(--fg-muted); }
  .les.x { background: transparent; border: 1px dashed var(--cancelled); color: var(--cancelled); text-decoration: line-through; }
  .les.sub { outline: 2px solid var(--substitution); outline-offset: -2px; color: var(--substitution-fg); }
  .les.arbeit { outline: 2px solid var(--exam); outline-offset: -2px; }
  .les.absent { text-decoration: underline dotted; }
</style>
