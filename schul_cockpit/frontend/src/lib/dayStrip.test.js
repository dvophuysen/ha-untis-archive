import test from 'node:test';
import assert from 'node:assert/strict';
import { slotsOf, withGaps, gridLayout } from './dayStrip.js';

const fmt = (t) => `${String(Math.floor(t / 100)).padStart(2, '0')}:${String(t % 100).padStart(2, '0')}`;
const L = (id, s, e, name, extra = {}) => ({ id, start_time: s, end_time: e, start_hhmm: fmt(s), end_hhmm: fmt(e), subject_name: name, ...extra });
const P = (short, start, end, extra = {}) => ({ short, subject: short, start, end, state: 'normal', exam: false, ...extra });

test('parallel periods stay side by side in the strip', () => {
  const day = { periods: [P('MA', '07:50', '08:35'), P('SN', '09:45', '10:30'), P('LA', '09:45', '10:30')] };
  const slots = slotsOf([day]);
  assert.deepEqual(slots.map((s) => s.start), ['07:50', '09:45']);
  const out = withGaps(day, slots);
  assert.equal(out[1].gap, true);
  assert.deepEqual(out[2].parallel.map((p) => p.short), ['SN', 'LA']);
});

test('grid keeps parallel lessons and merges double lessons', () => {
  const days = [
    { date: 'a', lessons: [L(1, 750, 835, 'Sport'), L(2, 840, 925, 'Sport'), L(3, 945, 1030, 'Mathe')] },
    { date: 'b', lessons: [L(4, 750, 835, 'Deutsch'), L(5, 945, 1030, 'Spanisch'), L(6, 945, 1030, 'Latein'), L(7, 1030, 1115, 'Latein')] },
  ];
  const { rows, cells } = gridLayout(days);
  assert.deepEqual(rows.map((r) => r.start), ['07:50', '08:40', '09:45', '10:30']);
  const a = cells.filter((c) => c.col === 0);
  assert.deepEqual(a.map((c) => [c.row, c.span, c.lessons.length]), [[0, 2, 1], [2, 1, 1]]);
  const b = cells.filter((c) => c.col === 1);
  // Parallele Stunden stehen beide da; die folgende Stunde verschmilzt nicht mit einer geteilten Zelle.
  assert.deepEqual(b.map((c) => [c.row, c.span, c.lessons.map((l) => l.id)]), [[0, 1, [4]], [2, 1, [5, 6]], [3, 1, [7]]]);
});

test('a cancelled lesson does not merge with a held one', () => {
  const { cells } = gridLayout([{ date: 'a', lessons: [L(1, 750, 835, 'Sport'), L(2, 840, 925, 'Sport', { is_cancelled: true })] }]);
  assert.equal(cells.length, 2);
});
