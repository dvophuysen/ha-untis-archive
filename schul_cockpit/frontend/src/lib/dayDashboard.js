import { shiftDateIso } from './format.js';

// Unknown times must never turn a future lesson into a feedback request.
export function lessonEnded(lesson, day, now = new Date()) {
  const end = lesson.end_time;
  if (!day || !Number.isInteger(end) || end < 0 || end > 2359 || end % 100 > 59) return false;
  const until = new Date(`${day}T${String(Math.floor(end / 100)).padStart(2, '0')}:${String(end % 100).padStart(2, '0')}:00`);
  return Number.isFinite(until.getTime()) && now >= until;
}

export function splitLessons(lessons, day, now) {
  const open = [], upcoming = [], history = [];
  for (const lesson of lessons) {
    if (!lessonEnded(lesson, day, now)) upcoming.push(lesson);
    else if (!lesson.is_cancelled && !lesson.was_absent && lesson.checkin?.rating == null) open.push(lesson);
    else history.push(lesson);
  }
  return { open, upcoming, history };
}

export function splitTasks(tasks, today) {
  const due = [], ahead = [], undated = [], done = [];
  const tomorrow = shiftDateIso(today, 1);
  for (const task of tasks) {
    if (task.status === 'done') { done.push(task); continue; }
    if (!task.due_date) undated.push(task);
    else if (task.due_date <= tomorrow) due.push(task);
    else ahead.push(task);
  }
  const byDate = (a, b) => a.due_date.localeCompare(b.due_date) || a.id - b.id;
  due.sort(byDate); ahead.sort(byDate);
  const completed = task => {
    const value = Date.parse(task.completed_at || '');
    return Number.isFinite(value) ? value : null;
  };
  done.sort((a,b) => {
    const ac=completed(a), bc=completed(b);
    if (ac !== null || bc !== null) {
      if (ac === null) return 1;
      if (bc === null) return -1;
      if (ac !== bc) return bc-ac;
    }
    return (b.due_date || '').localeCompare(a.due_date || '') || b.id-a.id;
  });
  return { due, ahead, undated, done };
}
