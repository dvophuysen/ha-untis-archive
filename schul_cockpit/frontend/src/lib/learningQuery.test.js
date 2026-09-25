import test from 'node:test';
import assert from 'node:assert/strict';
import { queryOf, opensSession, openFromQuery } from './learningQuery.js';

test('liest Parameter aus dem Hash', () => {
  assert.equal(queryOf('#/learning?topic_id=5').get('topic_id'), '5');
  assert.equal(queryOf('#/learning').get('topic_id'), null);
  assert.ok(opensSession(queryOf('#/learning?lesson_id=3&subject=Deutsch')));
  assert.ok(!opensSession(queryOf('#/learning?subject=Deutsch&mode=exam')));
});

test('öffnet die passende Einheit', async () => {
  const calls = [];
  const api = { get: async (p) => (calls.push(['get', p]), { id: 1 }), post: async (p, b) => (calls.push(['post', p, b]), { id: 2 }) };
  await openFromQuery(api, '/b', queryOf('#/learning?topic_id=7'));
  await openFromQuery(api, '/b', queryOf('#/learning?session=4'));
  await openFromQuery(api, '/b', queryOf('#/learning?lesson_id=9&subject=Deutsch&title=Kommas'));
  assert.deepEqual(calls[0], ['post', '/b/sessions', { topic_id: 7 }]);
  assert.deepEqual(calls[1], ['get', '/b/sessions/4']);
  assert.equal(calls[2][2].lesson_id, 9);
  assert.equal(calls[2][2].goal, 'Kommas');
  assert.equal(calls[2][2].voluntary, true);
  assert.equal(await openFromQuery(api, '/b', queryOf('#/learning')), null);
});
