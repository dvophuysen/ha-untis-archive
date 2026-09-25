import test from 'node:test';
import assert from 'node:assert/strict';
import { dayPhase, mergeLessons } from './dayPhase.js';
const L = (id, s, e, name, extra = {}) => ({ id, start_time: s, end_time: e, start_hhmm: `${Math.floor(s/100)}:${String(s%100).padStart(2,'0')}`, end_hhmm: `${Math.floor(e/100)}:${String(e%100).padStart(2,'0')}`, subject_name: name, ...extra });
const day = [L(1, 750, 835, 'Sport'), L(2, 840, 925, 'Sport'), L(3, 945, 1030, 'Mathe'), L(4, 1225, 1310, 'Deutsch', { is_cancelled: true })];
const at = (h, m) => new Date(2026, 8, 24, h, m);
test('phase follows the real timetable; cancelled last lesson ends school earlier', () => {
  assert.equal(dayPhase(day, at(7, 5)).phase, 'vor');
assert.equal(dayPhase(day, at(9, 0)).phase, 'in');
assert.equal(dayPhase(day, at(9, 0)).current.id, 2);
// Die ausgefallene letzte Stunde verschiebt das Schulende auf 10:30.
assert.equal(dayPhase(day, at(11, 0)).phase, 'nach');
assert.equal(dayPhase([], at(9, 0)).phase, 'frei');
});
test('double lessons merge into one row', () => {
  const g = mergeLessons(day);
assert.equal(g.length, 3);
assert.equal(g[0].lessons.length, 2);
assert.equal(g[0].end_hhmm, '9:25');
});
