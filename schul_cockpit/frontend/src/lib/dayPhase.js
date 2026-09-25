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

/** Doppelstunden als eine Zeile: gleiches Fach, gleicher Zustand, höchstens
 *  20 Minuten Pause dazwischen. Jede Gruppe behält ihre einzelnen Stunden. */
export function mergeLessons(lessons) {
  const groups = [];
  for (const l of lessons || []) {
    const prev = groups[groups.length - 1];
    const last = prev?.lessons[prev.lessons.length - 1];
    const gap = last ? minutes(l.start_time) - minutes(last.end_time) : null;
    if (last && (l.subject_name || l.subject_short) === (last.subject_name || last.subject_short)
        && !!l.is_cancelled === !!last.is_cancelled && gap !== null && gap >= 0 && gap <= 20) {
      prev.lessons.push(l);
      prev.end_hhmm = l.end_hhmm; prev.end_time = l.end_time;
    } else {
      groups.push({ key: l.id, lessons: [l], start_hhmm: l.start_hhmm, end_hhmm: l.end_hhmm, start_time: l.start_time, end_time: l.end_time });
    }
  }
  return groups;
}

/** Geschätzte Minuten bis zur Freizeit: Aufgaben mit Schätzung, sonst 15 Minuten,
 *  Erinnerungen und Kleinkram je eine Minute. */
export function minutesLeft(openTasks, bagLeft, feedbackLeft) {
  const work = openTasks.reduce((a, t) => a + (t.task_type === 'reminder' ? 1 : (t.estimated_minutes || 15)), 0);
  return work + bagLeft * 1 + feedbackLeft;
}
