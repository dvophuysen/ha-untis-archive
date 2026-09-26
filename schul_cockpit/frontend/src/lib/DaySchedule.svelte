<script>
  // Stundenplan des Tages als kurze Liste (D171): Doppelstunden in einer Zeile,
  // Änderungen in Worten, die laufende Stunde markiert. Nach dem Ende einer
  // Stunde lässt sie sich direkt hier zurückmelden (D07: dieselben Gesichter).
  import { subjectStyle } from './subjectStyle.js';
  import { api } from './api.js';
  import { mergeLessons, lessonOver, held, groupLessons, groupSlots } from './dayPhase.js';
  import LessonDetail from './LessonDetail.svelte';

  let { accountId, lessons = [], now = new Date(), live = true, onsaved = () => {} } = $props();
  const groups = $derived(mergeLessons(lessons));
  let busy = $state(null), error = $state(''), detail = $state(null);

  const isSubst = (l) => !!(l.is_irregular || l.is_teacher_substituted || l.is_subject_substituted);
  const t = (hhmm) => (Number.isInteger(hhmm) ? Math.floor(hhmm / 100) * 60 + (hhmm % 100) : null);
  const nowMin = $derived(now.getHours() * 60 + now.getMinutes());
  function rowState(g) {
    if (!live) return '';
    if (nowMin >= t(g.end_time)) return 'past';
    if (nowMin >= t(g.start_time)) return 'now';
    return '';
  }
  // Rückmelden gilt für alle Stunden der Gruppe, die vorbei sind und stattfanden,
  // bei Teamunterricht für beide Einträge (eine Stunde, zwei Lehrkräfte).
  const ratable = (g) => groupLessons(g).filter((l) => held(l) && (l.subject_name || l.subject_short) && lessonOver(l, now));
  const ratingOf = (g) => {
    const ids = new Set(ratable(g).map((l) => l.id));
    // Je Stunde zählt die Bewertung eines ihrer Einträge.
    const r = groupSlots(g).map((s) => s.filter((l) => ids.has(l.id))).filter((s) => s.length)
      .map((s) => s.find((l) => l.checkin?.rating != null)?.checkin.rating ?? null);
    return r.length && r.every((x) => x === r[0]) ? r[0] : null;
  };
  async function rate(g, value) {
    if (busy) return;
    busy = g.key; error = '';
    try {
      for (const l of ratable(g)) {
        const saved = await api.post(`/api/accounts/${accountId}/lessons/${l.id}/checkin`, { rating: value, note: l.checkin?.note || null });
        l.checkin = { rating: saved.rating, note: saved.note };
      }
      onsaved();
    } catch (e) {
      error = 'Nicht gespeichert. Bitte noch einmal versuchen.';
    } finally { busy = null; }
  }
  function changes(g) {
    const l = g.lessons[0], out = [];
    if (l.is_cancelled) out.push({ tone: 'x', text: 'fällt aus' });
    else {
      if (l.is_room_substituted && l.room_orig) out.push({ tone: 'c', text: `Raum ${l.room} statt ${l.room_orig}` });
      if (l.is_subject_substituted && l.subject_orig_name) out.push({ tone: 's', text: `statt ${l.subject_orig_name}` });
      else if (isSubst(l)) out.push({ tone: 's', text: 'Vertretung' });
      if (l.was_absent) out.push({ tone: 'x', text: 'als abwesend eingetragen' });
    }
    return out;
  }
</script>

<div class="day-schedule">
  {#each groups as g (g.key)}
    {@const l = g.lessons[0]}
    {@const st = subjectStyle(l.subject_name || l.subject_short)}
    {@const r = ratingOf(g)}
    <div class="ds-row {rowState(g)}" class:cancelled={l.is_cancelled}>
      <span class="ds-time">{g.start_hhmm}<br />{g.end_hhmm}</span>
      <button class="ds-body" onclick={() => (detail = l)} aria-label={`${st.name}, Details`}>
        <span class="ds-name">{st.emoji} {st.name || 'Fach offen'}{#if g.lessons.length > 1} <span class="tag">{g.lessons.length} Std.</span>{/if}</span>
        <span class="ds-meta">
          {#if rowState(g) === 'now'}<b>jetzt</b> · {/if}{#if l.room && !l.is_room_substituted && !l.is_cancelled}Raum {l.room}{/if}{#if l.lstext && !l.is_cancelled}{l.room ? ' · ' : ''}{l.lstext}{/if}
        </span>
        {#each changes(g) as c}<span class="tag {c.tone}">{c.text}</span>{/each}
      </button>
      {#if ratable(g).length}
        <span class="ds-faces" role="group" aria-label={`Wie gut hast du ${st.name} verstanden?`}>
          {#if isSubst(l)}<button class:sel={r === 4} class:dim={r && r !== 4} disabled={busy === g.key} onclick={() => rate(g, 4)} aria-label="Nur Aufsicht, kein neuer Stoff" aria-pressed={r === 4}>👀</button>{/if}
          <button class:sel={r === 3} class:dim={r && r !== 3} disabled={busy === g.key} onclick={() => rate(g, 3)} aria-label="Verstanden" aria-pressed={r === 3}>😀</button>
          <button class:sel={r === 2} class:dim={r && r !== 2} disabled={busy === g.key} onclick={() => rate(g, 2)} aria-label="Teilweise verstanden" aria-pressed={r === 2}>😐</button>
          <button class:sel={r === 1} class:dim={r && r !== 1} disabled={busy === g.key} onclick={() => rate(g, 1)} aria-label="Nicht verstanden" aria-pressed={r === 1}>😟</button>
        </span>
      {/if}
    </div>
    {#if (r === 1 || r === 2) && ratable(g).length}
      <a class="ds-mentor" href={`#/learning?${new URLSearchParams({ lesson_id: String(l.id), subject: l.subject_name || l.subject_short || '', title: l.lstext || '' })}`}>💬 Mit dem Lernbegleiter verstehen</a>
    {/if}
  {:else}
    <p class="muted">Heute ist kein Unterricht eingetragen.</p>
  {/each}
  {#if error}<p class="error-box" role="alert">{error}</p>{/if}
</div>
{#if detail}<LessonDetail {accountId} lesson={detail} onclose={() => (detail = null)} {onsaved} />{/if}

<style>
  .day-schedule{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-md);padding:var(--sp-1) var(--sp-3)}
  .ds-row{display:grid;grid-template-columns:44px minmax(0,1fr) auto;gap:var(--sp-2);align-items:center;padding:var(--sp-2) 0;border-bottom:1px solid var(--border)}
  .ds-row:last-of-type{border-bottom:0}
  .ds-row.now{background:color-mix(in oklab,var(--accent) 12%,var(--bg-card));margin:0 calc(-1 * var(--sp-3));padding:var(--sp-2) var(--sp-3);border-radius:var(--r-sm);border-bottom:0}
  .ds-row.past .ds-body{opacity:.65}
  .ds-time{font-size:var(--fs-xs);color:var(--fg-muted);font-variant-numeric:tabular-nums;line-height:1.25}
  .ds-body{display:grid;gap:2px;text-align:left;background:none;border:0;padding:0;min-height:44px;color:var(--fg);border-radius:0;align-content:center}
  .ds-name{font-weight:650;display:flex;flex-wrap:wrap;align-items:center;gap:4px}
  .cancelled .ds-name{text-decoration:line-through;color:var(--fg-muted)}
  .ds-meta{font-size:var(--fs-xs);color:var(--fg-muted);overflow-wrap:anywhere}
  .ds-meta b{color:var(--fg)}
  .tag{justify-self:start;font-size:.7rem;font-weight:700;border-radius:var(--r-pill);padding:1px 7px;background:var(--bg-elevated);color:var(--fg-muted);border:1px solid var(--border)}
  .tag.c{background:var(--warm-soft);color:var(--warn-fg);border-color:transparent}
  .tag.s{background:color-mix(in oklab,var(--substitution) 14%,var(--bg-card));color:var(--substitution-fg);border-color:transparent}
  .tag.x{border-color:transparent}
  .ds-faces{display:flex;gap:3px}
  .ds-faces button{font-size:1.05rem;min-height:40px;min-width:38px;padding:0;border-radius:var(--r-sm);background:var(--bg-elevated);border:2px solid transparent}
  .ds-faces button.sel{border-color:var(--accent);background:color-mix(in oklab,var(--accent) 14%,var(--bg-card))}
  .ds-faces button.dim{opacity:.4}
  .ds-mentor{display:inline-block;font-size:var(--fs-sm);font-weight:600;padding:var(--sp-1) 0 var(--sp-2) 52px;min-height:32px}
  @media(max-width:360px){.ds-faces button{min-width:34px}}
</style>
