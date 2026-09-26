import test from 'node:test';
import assert from 'node:assert/strict';
import { dayPhase, mergeLessons, sameSlot, groupLessons, groupSlots, groupOpen, openSlots } from './dayPhase.js';
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
test('team teaching in one subject is one lesson; parallel subjects stay apart', () => {
  const mu = (id, s, e, extra = {}) => L(id, s, e, 'Musik', { date: '2026-09-24', subject_untis_id: 7, ...extra });
  const lessons = [
    L(10, 800, 845, 'Religion', { date: '2026-09-24' }), L(11, 800, 845, 'Werte und Normen', { date: '2026-09-24' }),
    mu(12, 1035, 1120, { teacher_name: 'A' }), mu(13, 1035, 1120, { teacher_name: 'B' }),
    mu(14, 1125, 1210, { teacher_name: 'A' }), mu(15, 1125, 1210, { teacher_name: 'B' }),
  ];
  const g = mergeLessons(lessons);
  // Religion und Werte und Normen: zwei Zeilen; Musik als Doppelstunde im Teamunterricht: eine Zeile, zwei Stunden.
  assert.deepEqual(g.map((x) => x.lessons.map((l) => l.id)), [[10], [11], [12, 14]]);
  assert.deepEqual(g[2].parallel.map((l) => l.id), [13, 15]);
  assert.deepEqual(groupLessons(g[2]).map((l) => l.id), [12, 14, 13, 15]);
  assert.deepEqual(groupSlots(g[2]).map((s) => s.map((l) => l.id)), [[12, 13], [14, 15]]);
  assert.equal(g[2].end_hhmm, '12:10');
  assert.equal(openSlots(lessons), 4);
  assert.ok(groupOpen(g[2]));
  // Eine Bewertung je Stunde bei einem der Einträge genügt.
  lessons[3].checkin = { rating: 3 };
  assert.ok(groupOpen(g[2]));
  lessons[4].checkin = { rating: 3 };
  assert.ok(!groupOpen(g[2]));
  assert.equal(openSlots(lessons), 2);
  // Ein anderes UNTIS-Fach mit gleichem Namen, ein Ausfall oder ein anderer Tag ist nicht dieselbe Stunde.
  assert.ok(!sameSlot(mu(20, 1035, 1120), mu(21, 1035, 1120, { subject_untis_id: 8 })));
  assert.ok(!sameSlot(mu(20, 1035, 1120), mu(21, 1035, 1120, { is_cancelled: true })));
  assert.ok(!sameSlot(mu(20, 1035, 1120), mu(21, 1035, 1120, { date: '2026-09-25' })));
  assert.ok(!sameSlot(L(22, 800, 845, ''), L(23, 800, 845, '')));
});
