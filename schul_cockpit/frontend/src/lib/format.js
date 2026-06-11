// Date math + Untis-todo-text helpers used across the UI.
//
// All ISO dates here are *local* (YYYY-MM-DD in the user's calendar day).
// Never use toISOString() for this — it converts to UTC and silently
// shifts the day in non-UTC timezones (the cause of the 'tomorrow shows
// as today' bug).

export function isoLocal(d) {
  return (
    d.getFullYear() +
    '-' +
    String(d.getMonth() + 1).padStart(2, '0') +
    '-' +
    String(d.getDate()).padStart(2, '0')
  );
}

export function isoToday() {
  return isoLocal(new Date());
}

export function shiftDateIso(iso, days) {
  if (!iso) return '';
  // Use midday so a +/- DST hour can't roll us into the wrong calendar day.
  const d = new Date(iso + 'T12:00:00');
  d.setDate(d.getDate() + days);
  return isoLocal(d);
}

export function daysBetween(fromIso, toIso) {
  if (!fromIso || !toIso) return 0;
  const a = new Date(fromIso + 'T12:00:00');
  const b = new Date(toIso + 'T12:00:00');
  return Math.round((b - a) / 86400000);
}

const _WD = ['So.', 'Mo.', 'Di.', 'Mi.', 'Do.', 'Fr.', 'Sa.'];

export function formatShortDate(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T12:00:00');
  return `${_WD[d.getDay()]} ${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.`;
}

/** Natural-language due label. Short and unambiguous. */
export function dueLabel(dueIso, todayIso) {
  if (!dueIso) return '';
  const today = todayIso || isoToday();
  const d = daysBetween(today, dueIso);
  if (d < -1) return `${-d} Tage überfällig`;
  if (d === -1) return 'gestern fällig';
  if (d === 0) return 'heute fällig';
  if (d === 1) return 'morgen fällig';
  if (d === 2) return 'übermorgen fällig';
  if (d <= 7) return `in ${d} Tagen`;
  return formatShortDate(dueIso);
}

/** Lernstand → Emoji (siehe Klausuren-Seite für die Definition).
 *  null / undefined ergibt '' damit Aufrufer einfach hintendran hängen
 *  können, ohne extra zu prüfen. */
export function learnStateEmoji(state) {
  switch (state) {
    case 0: return '⚪';
    case 1: return '😟';
    case 2: return '😐';
    case 3: return '😀';
    default: return '';
  }
}

/** Strip Untis-automation metadata from a todo description.
 *
 * The user's HA automation writes entries like:
 *   #<actual homework text>
 *   Gegeben am: Mi 03.06.
 *   Fällig bis: Do 04.06.
 *   [EN260612]
 *
 * The trailing tag is `[<fach-kürzel><datum>]` — kürzel ist 1–5 Buchstaben
 * (SN, EN, DE, MA, GE, WuN …). Für die Listenansicht wollen wir nur die
 * eigentliche Aufgabenstellung; der Rest ist Rauschen. Leading '#' is
 * treated as a marker, not literal text. */
export function stripUntisMetadata(notes) {
  if (!notes) return '';
  const lines = notes.split(/\r?\n/);
  const kept = [];
  for (let raw of lines) {
    const line = raw.trim();
    if (!line) {
      if (kept.length && kept[kept.length - 1] !== '') kept.push('');
      continue;
    }
    if (/^gegeben\s+am\s*:/i.test(line)) continue;
    if (/^f(ä|ae)llig(\s+bis)?\s*:/i.test(line)) continue;
    if (/^\[[A-Za-zÄÖÜäöüß]{1,5}\d+\]\s*$/.test(line)) continue;
    // Strip a leading '#' marker the automation prefixes to the body.
    kept.push(raw.replace(/^\s*#\s?/, ''));
  }
  return kept.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}
