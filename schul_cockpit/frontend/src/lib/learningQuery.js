// Adressen der Lernseite (D186): #/learning?topic_id=… öffnet eine Einheit zum
// Thema (mit &redo=…&task=… zum Nacharbeiten einer Aufgabe, D207), ?lesson_id=…&subject=…&title=… eine zur Stunde, ?help=/?check= die
// Hausaufgabenhilfe, ?session= eine vorhandene Einheit, ?oral= eine Sprechprobe. Ausgewertet wird bei
// jedem Wechsel der Adresse, nicht nur beim ersten Laden; danach verschwinden
// die Parameter wieder, damit Neuladen nichts ungewollt erneut öffnet.

export const OPENING_KEYS = ['session', 'oral', 'topic_id', 'help', 'check', 'lesson_id'];

export function queryOf(hash) {
  return new URLSearchParams(String(hash || '').split('?')[1] || '');
}

export function opensSession(q) {
  return OPENING_KEYS.some((k) => q.get(k));
}

/** Die Einheit, die die Adresse verlangt, oder null. */
export async function openFromQuery(api, base, q, { demo = false } = {}) {
  if (q.get('session')) return api.get(`${base}/sessions/${Number(q.get('session'))}`);
  // Sprechprobe (D194): ?oral=<Arbeit>[&topic_id=…]; ohne Thema die Gesamtprobe.
  if (q.get('oral')) return api.post(`${base}/sessions`, { oral_exam_key: q.get('oral'), topic_id: q.get('topic_id') ? Number(q.get('topic_id')) : null });
  // Aufgabe einer bewerteten Übungsarbeit nacharbeiten (D207): &redo=<Versuch>&task=<Index ab 0>.
  if (q.get('topic_id') && q.get('redo') && q.get('task') !== null) {
    return api.post(`${base}/sessions`, { topic_id: Number(q.get('topic_id')), paper_attempt_id: Number(q.get('redo')), paper_task: Number(q.get('task')) });
  }
  if (q.get('topic_id')) return api.post(`${base}/sessions`, { topic_id: Number(q.get('topic_id')) });
  if (q.get('help')) return api.post(`${base}/sessions`, { subject: 'Hausaufgabe', homework_task_id: Number(q.get('help')), voluntary: true });
  if (q.get('check')) return api.post(`${base}/sessions`, { subject: 'Hausaufgabe', homework_task_id: Number(q.get('check')), check: true, voluntary: true });
  if (q.get('lesson_id')) {
    return api.post(`${base}/sessions`, { subject: q.get('subject') || '', lesson_id: Number(q.get('lesson_id')), skill_id: null,
      goal: q.get('title') || '', goal_key: null, minutes: 10, voluntary: true, demo });
  }
  return null;
}

/** Parameter aus der Adresse nehmen, ohne einen neuen Verlaufseintrag. */
export function clearQuery() {
  const [path, query] = window.location.hash.split('?');
  if (query === undefined) return;
  history.replaceState(history.state, '', `${window.location.pathname}${window.location.search}${path || '#/learning'}`);
}
