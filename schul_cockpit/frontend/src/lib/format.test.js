import test from 'node:test';
import assert from 'node:assert/strict';

// Die Tage gelten in der Zeitzone der Familie.
process.env.TZ = 'Europe/Berlin';
const { localDay, givenDate } = await import('./format.js');

test('localDay takes the local calendar day of a UTC stamp', () => {
  assert.equal(localDay('2026-09-24T22:30:00+00:00'), '2026-09-25');
  assert.equal(localDay('2026-09-24T21:59:00Z'), '2026-09-24');
  assert.equal(localDay('2026-09-24T10:00:00.123456+00:00'), '2026-09-24');
});

test('localDay leaves stamps without time zone or time as they are', () => {
  assert.equal(localDay('2026-09-24 23:30:00'), '2026-09-24');
  assert.equal(localDay('2026-09-24'), '2026-09-24');
  assert.equal(localDay(''), '');
  assert.equal(localDay(null), '');
});

test('givenDate steps back a year across new year', () => {
  assert.equal(givenDate('29', '12', undefined, '2027-01-08'), '2026-12-29');
  assert.equal(givenDate('3', '6', undefined, '2026-06-04'), '2026-06-03');
  assert.equal(givenDate('3', '6', '26', '2026-06-04'), '2026-06-03');
  assert.equal(givenDate('3', '6', '2025', '2026-06-04'), '2025-06-03');
});
