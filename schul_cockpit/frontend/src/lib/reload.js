// Neu laden nach einem Add-on-Update, ohne Eingaben zu verlieren und ohne
// Endlosschleife.
import { writesInFlight } from './api.js';

const KEY = 'reloadForUpdateAt';
const GAP = 60000;

/** Lädt die Seite neu, höchstens einmal je Minute und Tab. Gibt false zurück,
 *  wenn gerade erst neu geladen wurde oder der Speicher fehlt; dann bleibt die
 *  Seite stehen und zeigt ihren Fehler. */
export function reloadOnce() {
  try {
    const last = Number(sessionStorage.getItem(KEY) || 0);
    if (Date.now() - last < GAP) return false;
    sessionStorage.setItem(KEY, String(Date.now()));
  } catch {
    return false;
  }
  window.location.reload();
  return true;
}

/** Ob auf der Seite gerade etwas verloren ginge: ein ausgefülltes Eingabefeld
 *  oder ein laufender schreibender Aufruf (etwa ein Mentor-Zug). */
export function pageBusy() {
  if (writesInFlight() > 0) return true;
  for (const el of document.querySelectorAll('textarea, input, [contenteditable="true"]')) {
    if (el.isContentEditable) {
      if ((el.textContent || '').trim()) return true;
      continue;
    }
    const type = (el.type || 'text').toLowerCase();
    if (el.tagName === 'INPUT' && !['text', 'search', 'number', 'email', 'tel', 'url', 'password'].includes(type)) continue;
    if (el.disabled || el.readOnly) continue;
    if ((el.value || '').trim()) return true;
  }
  return false;
}
