// Stundenplan-Leiste (D170, D184): gemeinsame Zeitfenster für mehrere Tage,
// Pausen ab zehn Minuten als Lücke, parallele Stunden nebeneinander statt
// überschrieben. Eingabe sind die Tage aus family_board.schedule_day().

export const minutes = (hhmm) => (hhmm ? Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5)) : null);

/** Gemeinsame Zeitfenster aller Tage, damit gleiche Stunden untereinander stehen. */
export function slotsOf(days) {
  const byStart = new Map();
  for (const d of days || []) for (const p of d?.periods || []) if (p.start && !byStart.has(p.start)) byStart.set(p.start, p.end);
  return [...byStart.entries()].sort((a, b) => minutes(a[0]) - minutes(b[0])).map(([start, end]) => ({ start, end }));
}

/** Die Fenster eines Tages: Lücke, leer, eine Stunde oder mehrere parallele. */
export function withGaps(day, slots) {
  const out = [];
  slots.forEach((slot, i) => {
    const prev = slots[i - 1];
    if (prev && minutes(slot.start) - minutes(prev.end) >= 10) out.push({ gap: true, key: `g${i}` });
    const found = (day?.periods || []).filter((x) => x.start === slot.start);
    if (!found.length) out.push({ empty: true, key: `e${i}` });
    else if (found.length === 1) out.push({ ...found[0], key: `p${i}` });
    else out.push({ parallel: found, key: `p${i}` });
  });
  return out;
}

export const periodTitle = (p) =>
  `${p.start}–${p.end} ${p.subject}${p.state === 'cancelled' ? ', fällt aus' : p.state === 'sub' ? ', Vertretung' : ''}${p.exam ? ', Arbeit' : ''}${p.absent ? ', gefehlt' : ''}`;

const hhmm = (t) => (Number.isInteger(t) ? Math.floor(t / 100) * 60 + (t % 100) : null);

/** Raster Stunden × Tage: je Tag und Startzeit eine Zelle mit allen Stunden
 *  dieser Zeit. Eine Doppelstunde (gleiches Fach, gleicher Zustand, höchstens
 *  20 Minuten Pause, in beiden Fenstern allein) füllt zwei Zeilen. */
export function gridLayout(days) {
  const byStart = new Map();
  for (const d of days || []) for (const l of d.lessons || []) {
    if (l.start_hhmm && !byStart.has(l.start_hhmm)) byStart.set(l.start_hhmm, { start: l.start_hhmm, end: l.end_hhmm, start_time: l.start_time, end_time: l.end_time });
  }
  const rows = [...byStart.values()].sort((a, b) => hhmm(a.start_time) - hhmm(b.start_time));
  const index = new Map(rows.map((r, i) => [r.start, i]));
  const cells = [];
  (days || []).forEach((d, col) => {
    const buckets = rows.map(() => []);
    for (const l of d.lessons || []) if (index.has(l.start_hhmm)) buckets[index.get(l.start_hhmm)].push(l);
    let last = null;
    buckets.forEach((items, row) => {
      if (!items.length) { last = null; return; }
      const l = items[0];
      const prev = last?.lessons.length === 1 ? (last.more.at(-1) || last.lessons[0]) : null;
      const gap = prev ? hhmm(l.start_time) - hhmm(prev.end_time) : null;
      if (items.length === 1 && prev && last.row + last.span === row && gap !== null && gap >= 0 && gap <= 20
          && (l.subject_name || l.subject_short) === (prev.subject_name || prev.subject_short)
          && !!l.is_cancelled === !!prev.is_cancelled) {
        last.span += 1;
        last.more.push(l);
        return;
      }
      last = { key: `${d.date}-${row}`, col, row, span: 1, lessons: items, more: [] };
      cells.push(last);
    });
  });
  return { rows, cells };
}
