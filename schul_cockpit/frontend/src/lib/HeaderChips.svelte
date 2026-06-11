<script>
  // Heute-Kopfleiste: drei Zonen, von oben nach unten in Dringlichkeit:
  //   1. rote "Heute Klausur"-Leiste (nur solange Klausurstunde aussteht)
  //   2. "Muss lernen"-Karten (Klausur ≤3 Tage, nicht sicher) — rot, prominent
  //   3. Chip-Reihe für ⚡ / 🗣 / 📚 / restliche 📝
  //
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
    phase = 'before',
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

  // 🚨 Klausur heute: nur solange die zugeordnete Stunde noch bevorsteht.
  // Phase "after" → komplett raus, dann ist auch ohne Lesson-Match klar:
  // die Klausur ist vorbei.
  const examsToday = $derived(
    curatedExams
      .filter((e) => e.date === todayIso)
      .filter((e) => {
        if (phase === 'after') return false;
        const l = lessonForExam(e);
        if (!l || typeof l.start_time !== 'number') return true;
        return l.start_time > now;
      }),
  );

  // Cram: Klausur in ≤3 Tagen UND Lernstand noch nicht "sicher" (3).
  // Gleiche Regel wie im Plan-Endpoint — eigene rote Karte, kein Chip.
  function isCram(e) {
    if (!e.date || e.date <= todayIso) return false;
    const d = daysBetween(todayIso, e.date);
    if (d > 3) return false;
    const ls = e.learn_state;
    return ls === null || ls === undefined || ls < 3;
  }

  const cramExams = $derived(curatedExams.filter(isCram));

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

  // Alle übrigen Klausuren in den nächsten 7 Tagen — die kommen als
  // dezenter Chip. Cram-Klausuren sind oben schon prominent.
  const nonCramNextExams = $derived(
    curatedExams.filter((e) => e.date && e.date > todayIso && !isCram(e)),
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
    for (const ex of nonCramNextExams) all.push(examChip(ex));
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

{#each cramExams as ex (ex.exam_key ?? ex.date + '|' + (ex.subject_name ?? ex.title ?? ''))}
  {@const d = daysBetween(todayIso, ex.date)}
  {@const when = d === 1 ? 'morgen' : `in ${d} Tagen`}
  {@const ls = learnStateEmoji(ex.learn_state)}
  <button class="cram-card" onclick={() => onNavigate('klausuren')}>
    <div class="cram-head">
      <span class="cram-subj">{ex.subject_name || ex.title || 'Klausur'}</span>
      {#if ls}<span class="cram-ls">{ls}</span>{/if}
    </div>
    <div class="cram-reason">📝 Klausur {when} — heute lernen</div>
  </button>
{/each}

{#if chips.length === 0 && examsToday.length === 0 && cramExams.length === 0}
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
  .cram-card {
    width: 100%;
    text-align: left;
    background: var(--bg-card);
    border: 1px solid var(--rating-1);
    border-left: 4px solid var(--rating-1);
    border-radius: 10px;
    padding: 0.7rem 0.85rem;
    margin: 0.4rem 0;
    cursor: pointer;
    min-height: 0;
  }
  .cram-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }
  .cram-subj { font-size: 1.1rem; font-weight: 700; }
  .cram-ls { font-size: 1.6rem; line-height: 1; }
  .cram-reason { color: var(--fg-muted); margin-top: 2px; font-size: 0.9rem; }
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
