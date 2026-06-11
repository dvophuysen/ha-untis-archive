<script>
  // Heute-Kopfleiste: rote "Klausur heute"-Leiste + bis zu 4 Aktions-Chips.
  // Zwei Phasen, Grenze = Ende der letzten heutigen Stunde:
  //   "before" → was kommt heute noch, worauf reagieren
  //   "after"  → was muss bis morgen vorbereitet sein
  //
  // Klausuren stammen aus dem KURATIERTEN Quellsystem (HA-Kalender +
  // manuelle Einträge via /exams). Untis' eigenes period_info_json.exam
  // ist für Schüler-Rollen tot — der frühere Today-Banner zählte nichts
  // davon, und dieser Header darf den Fehler nicht wiederholen.

  import { api } from './api.js';
  import { daysBetween, learnStateEmoji } from './format.js';

  let {
    accountId,
    todayIso,
    lessons = [],
    dueTodayCount = 0,
    onJumpDueToday = () => {},
    onJumpLesson = () => {},
    onNavigate = (path) => { window.location.hash = '#/' + path; },
  } = $props();

  let oralGroups = $state([]);
  let curatedExams = $state([]);

  $effect(() => {
    if (!accountId) return;
    api
      .get(`/api/accounts/${accountId}/oral-suggestions?horizon_days=7`)
      .then((r) => (oralGroups = r.groups || []))
      .catch(() => (oralGroups = []));
    api
      .get(`/api/accounts/${accountId}/exams?days_ahead=7`)
      .then((r) => (curatedExams = r.exams || []))
      .catch(() => (curatedExams = []));
  });

  // Snapshot der Uhrzeit beim Mount — die Seite wird ohnehin bei jedem
  // Öffnen frisch geladen, ein Minutentimer wäre Overkill.
  const now = (() => {
    const n = new Date();
    return n.getHours() * 100 + n.getMinutes();
  })();

  const lastEndHhmm = $derived.by(() => {
    let max = -1;
    for (const l of lessons) {
      if (l.is_cancelled) continue;
      if (typeof l.end_time === 'number' && l.end_time > max) max = l.end_time;
    }
    return max < 0 ? null : max;
  });

  // Wochenende / schulfrei → faktisch "nach Schluss", planen den nächsten Tag.
  const phase = $derived(
    lastEndHhmm === null || now > lastEndHhmm ? 'after' : 'before',
  );

  function isChanged(l) {
    return !!(
      l.is_cancelled ||
      l.is_irregular ||
      l.is_teacher_substituted ||
      l.is_subject_substituted ||
      l.is_room_substituted
    );
  }

  // Die zur Klausur passende Stunde finden, damit der rote Banner die
  // richtige Karte anspringt. Fällt zurück auf die erste Stunde des Tages.
  function lessonForExam(ex) {
    if (ex.subject_untis_id) {
      for (const l of lessons) {
        if (l.subject_untis_id === ex.subject_untis_id) return l;
      }
    }
    return lessons[0] || null;
  }

  // 🚨 Klausuren heute (egal welche Stunde — wir wissen aus dem Kalender
  // nur das Datum, nicht die Periode).
  const examsToday = $derived(
    curatedExams.filter((e) => e.date === todayIso),
  );

  // ⚡ nur noch nicht erlebte Plan-Änderungen.
  const futureChanges = $derived(
    phase === 'before'
      ? lessons.filter(
          (l) => isChanged(l) && typeof l.end_time === 'number' && l.end_time > now,
        )
      : [],
  );

  function planChangeLabel(items) {
    if (items.length === 0) return null;
    if (items.length === 1) {
      const l = items[0];
      const kind = l.is_cancelled ? 'Ausfall' : 'Vertretung';
      return { icon: '⚡', text: `${l.start_hhmm} ${kind}` };
    }
    return { icon: '⚡', text: `${items.length}× Planänderung` };
  }

  // Alle Klausuren in den nächsten 7 Tagen außer heute (heute hat die rote
  // Leiste). Jede bekommt einen eigenen Chip — zwei Klausuren in zwei Tagen
  // sind genau der Moment, in dem beide sichtbar sein müssen.
  const nextExams = $derived(
    curatedExams.filter((e) => e.date && e.date > todayIso),
  );

  // 🗣 nur wenn nächste Stunde des Faches noch heute kommt.
  const oralToday = $derived.by(() => {
    if (phase !== 'before') return null;
    for (const g of oralGroups) {
      if (g.next_date === todayIso) return g;
    }
    return null;
  });

  function examChip(ex) {
    const d = daysBetween(todayIso, ex.date);
    const subj = ex.subject_name || ex.title || 'Klausur';
    const when = d === 1 ? 'morgen' : `in ${d} Tagen`;
    const ls = learnStateEmoji(ex.learn_state);
    return {
      key: 'exam:' + (ex.exam_key ?? ex.date + '|' + subj),
      icon: '📝',
      text: `${subj} ${when}${ls ? ' ' + ls : ''}`,
      action: () => onNavigate('klausuren'),
    };
  }

  // Reihenfolge: zuerst zeitkritisches, danach jede anstehende Klausur.
  // Kein hartes Limit mehr — die Chip-Reihe ist flex-wrap, mehrere
  // Klausuren in einer Woche dürfen alle stehen.
  const chips = $derived.by(() => {
    const all = [];
    if (phase === 'before') {
      const pc = planChangeLabel(futureChanges);
      if (pc) {
        all.push({
          key: 'change',
          ...pc,
          action: () => onJumpLesson(futureChanges[0].id),
        });
      }
      if (oralToday) {
        const subj = oralToday.subject_short || oralToday.subject_name;
        all.push({
          key: 'oral',
          icon: '🗣',
          text: `${subj} aufzeigen`,
          action: () => onNavigate('subjects/' + oralToday.subject_id),
        });
      }
    }
    if (dueTodayCount > 0) {
      all.push({
        key: 'ha',
        icon: '📚',
        text: `${dueTodayCount} HA bis morgen`,
        action: onJumpDueToday,
      });
    }
    for (const ex of nextExams) all.push(examChip(ex));
    return all;
  });
</script>

{#each examsToday as ex (ex.exam_key ?? ex.date + '|' + (ex.subject_name ?? ex.title ?? ''))}
  {@const target = lessonForExam(ex)}
  {@const ls = learnStateEmoji(ex.learn_state)}
  <button
    class="exam-bar"
    onclick={() => target && onJumpLesson(target.id)}
  >
    🚨 Heute Klausur: {ex.subject_name || ex.title || 'Klausur'}{#if ls} {ls}{/if}
  </button>
{/each}

{#if chips.length === 0 && examsToday.length === 0}
  <div class="all-clear">😌 Alles im Griff.</div>
{:else if chips.length > 0}
  <div class="chip-row">
    {#each chips as c (c.key)}
      <button class="chip" onclick={c.action}>
        <span class="chip-ico">{c.icon}</span>
        <span class="chip-text">{c.text}</span>
      </button>
    {/each}
  </div>
{/if}

<style>
  .exam-bar {
    display: block;
    width: 100%;
    text-align: left;
    background: var(--exam);
    color: #fff;
    border: none;
    border-radius: 10px;
    padding: 0.55rem 0.8rem;
    font-size: 0.9rem;
    font-weight: 600;
    margin: 0.4rem 0;
    cursor: pointer;
    min-height: 0;
  }
  .chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin: 0.4rem 0 0.6rem;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0.35rem 0.7rem;
    font-size: 0.85rem;
    color: var(--fg);
    cursor: pointer;
    min-height: 0;
  }
  .chip-ico { font-size: 0.95rem; }
  .all-clear {
    color: var(--fg-muted);
    font-size: 0.85rem;
    padding: 0.5rem 0.2rem;
  }
</style>
