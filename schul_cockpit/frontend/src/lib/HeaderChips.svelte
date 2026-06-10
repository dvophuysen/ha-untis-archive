<script>
  // Heute-Kopfleiste: rote "Klausur heute"-Leiste + bis zu 4 Aktions-Chips.
  // Zwei Phasen, Grenze = Ende der letzten heutigen Stunde:
  //   "before" → was kommt heute noch, worauf reagieren
  //   "after"  → was muss bis morgen vorbereitet sein
  // Daten kommen aus dem bereits geladenen today-Endpoint + tasks; nur die
  // Mündlich-Vorschläge werden separat nachgeholt.

  import { api } from './api.js';
  import { daysBetween } from './format.js';

  let {
    accountId,
    todayIso,
    lessons = [],
    upcomingExams = [],
    dueTodayCount = 0,
    onJumpDueToday = () => {},
    onJumpLesson = () => {},
    onNavigate = (path) => { window.location.hash = '#/' + path; },
  } = $props();

  let oralGroups = $state([]);

  $effect(() => {
    if (!accountId) return;
    api
      .get(`/api/accounts/${accountId}/oral-suggestions?horizon_days=7`)
      .then((r) => (oralGroups = r.groups || []))
      .catch(() => (oralGroups = []));
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

  const examsToday = $derived(
    phase === 'before'
      ? lessons.filter(
          (l) => l.exam && typeof l.start_time === 'number' && l.start_time > now,
        )
      : [],
  );

  // ⚡ nur noch nicht erlebte Änderungen.
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

  // Nächste Klausur in 7 Tagen, ohne heute (heute hat eigene rote Leiste).
  const nextExam = $derived.by(() => {
    for (const e of upcomingExams) {
      if (e.date && e.date > todayIso) return e;
    }
    return null;
  });

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
    const subj = ex.subject_name || 'Klausur';
    const when = d === 1 ? 'morgen' : `in ${d} Tagen`;
    return {
      key: 'exam',
      icon: '📝',
      text: `${subj} ${when}`,
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
      if (dueTodayCount > 0) {
        all.push({
          key: 'ha',
          icon: '📚',
          text: `${dueTodayCount} HA bis morgen`,
          action: onJumpDueToday,
        });
      }
      if (nextExam) all.push(examChip(nextExam));
    } else {
      if (dueTodayCount > 0) {
        all.push({
          key: 'ha',
          icon: '📚',
          text: `${dueTodayCount} HA bis morgen`,
          action: onJumpDueToday,
        });
      }
      if (nextExam) all.push(examChip(nextExam));
    }
    return all.slice(0, 4);
  });
</script>

{#each examsToday as ex (ex.id)}
  <button class="exam-bar" onclick={() => onJumpLesson(ex.id)}>
    🚨 Heute Klausur: {ex.subject_short || ex.subject_name} ({ex.start_hhmm})
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
