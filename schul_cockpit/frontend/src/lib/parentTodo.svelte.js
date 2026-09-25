// „Erledigen“ (D183): offene Punkte für Eltern. Einmal geladen, von der
// Leiste (Zähler) und den Seiten Erledigen und Scannen gemeinsam genutzt.
import { api } from './api.js';

export const todo = $state({ data: null, error: '', loading: false, at: 0 });

let pending = null;

/** Lädt neu, wenn der letzte Stand älter als `maxAge` Millisekunden ist. */
export function loadTodo(maxAge = 60000) {
  if (pending) return pending;
  if (todo.data && Date.now() - todo.at < maxAge) return Promise.resolve(todo.data);
  todo.loading = true;
  pending = api.get('/api/parent/todo')
    .then((d) => { todo.data = d; todo.error = ''; todo.at = Date.now(); return d; })
    .catch((e) => { todo.error = e.message || 'Nicht erreichbar.'; return null; })
    .finally(() => { todo.loading = false; pending = null; });
  return pending;
}

export function forgetTodo() {
  todo.data = null; todo.at = 0; todo.error = '';
}

export function todoCount() {
  return todo.data?.total ?? 0;
}
