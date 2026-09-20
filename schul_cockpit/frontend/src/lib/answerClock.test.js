import { test } from 'node:test';
import assert from 'node:assert/strict';
import { answerClock } from './answerClock.js';

test('provider latency is excluded, including retries and reset while paused', () => {
  let time = 0;
  const clock = answerClock(() => time);
  time = 8000; clock.pause();
  time = 38000; assert.equal(clock.seconds(), 8);
  clock.resume(); assert.equal(clock.seconds(), 8);
  time = 40000; clock.pause();
  time = 70000; clock.resume(); assert.equal(clock.seconds(), 10);
  clock.pause(); clock.reset();
  time = 72000; clock.resume(); assert.equal(clock.seconds(), 2);
});
