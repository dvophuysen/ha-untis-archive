// Phasen des Schultags (D171): aus dem echten Stundenplan, nicht aus der Uhr.

const minutes = (hhmm) => (Number.isInteger(hhmm) ? Math.floor(hhmm / 100) * 60 + (hhmm % 100) : null);
export const nowMinutes = (now) => now.getHours() * 60 + now.getMinutes();

// Stunden, die wirklich stattfinden: nicht ausgefallen, nicht als abwesend geführt.
export const held = (l) => !l.is_cancelled && !l.was_absent;

/** vor | in | nach | frei — dazu erste, letzte, laufende und nächste Stunde. */
export function dayPhase(lessons, now) {
  const real = (lessons || []).filter((l) => held(l) && minutes(l.start_time) !== null && minutes(l.end_time) !== null);
  if (!real.length) return { phase: 'frei', first: null, last: null, current: null, next: null };
  const t = nowMinutes(now);
  const first = real[0], last = real[real.length - 1];
  const current = real.find((l) => minutes(l.start_time) <= t && t < minutes(l.end_time)) || null;
  const next = real.find((l) => minutes(l.start_time) > t) || null;
  const phase = t < minutes(first.start_time) ? 'vor' : t < minutes(last.end_time) ? 'in' : 'nach';
  return { phase, first, last, current, next };
}

export function lessonOver(lesson, now) {
  const end = minutes(lesson.end_time);
  return end !== null && nowMinutes(now) >= end;
}

const subjectKey = (l) => l.subject_name || l.subject_short;

/** Teamunterricht: zwei Einträge im selben Fach zur selben Zeit (etwa Musik mit
 *  zwei Lehrkräften) sind eine Stunde. Verschiedene Fächer parallel
 *  (Wahlpflicht, Religion und Werte und Normen) bleiben getrennt; so auch
 *  rewards.same_slot im Backend. */
export function sameSlot(a, b) {
  return !!subjectKey(a) && subjectKey(a) === subjectKey(b)
    && (a.date ?? null) === (b.date ?? null) && a.start_time === b.start_time && a.end_time === b.end_time
    && (a.subject_untis_id == null || b.subject_untis_id == null || a.subject_untis_id === b.subject_untis_id)
    && !!a.is_cancelled === !!b.is_cancelled;
}

/** Die Einträge je Stunde; eine Stunde ist zurückgemeldet, sobald einer ihrer Einträge bewertet ist. */
export function lessonSlots(lessons) {
  const slots = [];
  for (const l of lessons || []) {
    const slot = slots.find((s) => sameSlot(s[0], l));
    if (slot) slot.push(l); else slots.push([l]);
  }
  return slots;
}
export const slotRated = (slot) => slot.some((l) => l.checkin?.rating != null);
/** Wie viele Stunden noch eine Rückmeldung brauchen (Teamunterricht einmal). */
export const openSlots = (lessons) => lessonSlots(lessons).filter((s) => !slotRated(s)).length;

/** Alle Einträge einer Zeile, auch die gleichzeitigen im selben Fach. */
export const groupLessons = (g) => [...g.lessons, ...(g.parallel || [])];
/** Die Stunden einer Zeile, jede mit ihren gleichzeitigen Einträgen. */
export const groupSlots = (g) => g.lessons.map((l) => [l, ...(g.parallel || []).filter((p) => sameSlot(l, p))]);
/** Offen, solange eine Stunde der Zeile keine Rückmeldung hat. */
export const groupOpen = (g) => groupSlots(g).some((s) => !slotRated(s));

/** Doppelstunden als eine Zeile: gleiches Fach, gleicher Zustand, höchstens
 *  20 Minuten Pause dazwischen. Jede Gruppe behält ihre einzelnen Stunden
 *  (`lessons`, eine je Stunde); gleichzeitige Einträge im selben Fach
 *  (Teamunterricht) stehen in `parallel` und machen keine zweite Zeile. */
export function mergeLessons(lessons) {
  const groups = [];
  for (const l of lessons || []) {
    const twin = groups.find((g) => g.lessons.some((x) => sameSlot(x, l)));
    if (twin) { twin.parallel.push(l); continue; }
    const prev = groups[groups.length - 1];
    const last = prev?.lessons[prev.lessons.length - 1];
    const gap = last ? minutes(l.start_time) - minutes(last.end_time) : null;
    if (last && (l.subject_name || l.subject_short) === (last.subject_name || last.subject_short)
        && !!l.is_cancelled === !!last.is_cancelled && gap !== null && gap >= 0 && gap <= 20) {
      prev.lessons.push(l);
      prev.end_hhmm = l.end_hhmm; prev.end_time = l.end_time;
    } else {
      groups.push({ key: l.id, lessons: [l], parallel: [], start_hhmm: l.start_hhmm, end_hhmm: l.end_hhmm, start_time: l.start_time, end_time: l.end_time });
    }
  }
  return groups;
}
