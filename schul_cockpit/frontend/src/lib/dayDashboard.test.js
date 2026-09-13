import test from 'node:test';
import assert from 'node:assert/strict';
import { lessonEnded, splitLessons, splitTasks } from './dayDashboard.js';
const day = '2026-09-14';
test('feedback only after lesson end; unknown and invalid times stay unconfirmed', () => {
  const lesson = { end_time: 945 };
  assert.equal(lessonEnded(lesson, day, new Date(day+'T09:44:59')), false);
  assert.equal(lessonEnded(lesson, day, new Date(day+'T09:45:00')), true);
  for (const end_time of [null, undefined, '945', 960, 2400, -1]) assert.equal(lessonEnded({end_time}, day, new Date(day+'T12:00:00')), false);
});
test('comment stays open; ratings including supervision disappear; absence and cancellations need no feedback', () => {
  const base = { end_time:900 };
  const rows = [
    {...base,id:1,checkin:{rating:null,note:'Material'}}, {...base,id:2,checkin:{rating:4}},
    {...base,id:3,checkin:{rating:1}}, {...base,id:4,was_absent:true}, {...base,id:5,is_cancelled:true},
    {...base,id:6,end_time:1100},
  ];
  const result=splitLessons(rows,day,new Date(day+'T10:00:00'));
  assert.deepEqual(result.open.map(l=>l.id),[1]);
  assert.deepEqual(result.history.map(l=>l.id),[2,3,4,5]);
  assert.deepEqual(result.upcoming.map(l=>l.id),[6]);
  rows[0].checkin.rating=3;
  assert.equal(splitLessons(rows,day,new Date(day+'T10:00:00')).open.length,0);
});
test('all open work stays visible, future work and undated work separate, done work retained for correction', () => {
 const tasks=[{id:1,due_date:'2026-09-13'},{id:2,due_date:'2026-09-15'},{id:3,due_date:'2026-09-18'}, {id:4,due_date:null}, {id:5,due_date:'2026-09-14',status:'done'}];
 const r=splitTasks(tasks,day);
 assert.deepEqual(r.due.map(t=>t.id),[1,2]); assert.deepEqual(r.ahead.map(t=>t.id),[3]);assert.deepEqual(r.undated.map(t=>t.id),[4]);assert.deepEqual(r.done.map(t=>t.id),[5]);
 assert.equal(Object.values(r).flat().length,tasks.length);
});
test('tomorrow works across month, year and daylight-saving boundaries',()=>{
 for(const [date,due] of [['2026-12-31','2027-01-01'],['2026-03-28','2026-03-29'],['2026-10-24','2026-10-25']])assert.equal(splitTasks([{id:1,due_date:due}],date).due.length,1);
});
test('completed work is newest-first by actual completion; old imports fall back to due date',()=>{
 const rows=[{id:1,status:'done',due_date:'2025-06-01'},
 {id:2,status:'done',due_date:'2026-09-14',completed_at:'2026-09-14T14:00:00+02:00'},
 {id:3,status:'done',due_date:'2026-09-13',completed_at:'2026-09-14T12:01:00Z'},
 {id:4,status:'done',due_date:'2026-09-12'},
 {id:5,status:'done',due_date:null,completed_at:'invalid'}];
 assert.deepEqual(splitTasks(rows,day).done.map(t=>t.id),[3,2,4,1,5]);
 assert.deepEqual(rows.map(t=>t.id),[1,2,3,4,5]);
});
