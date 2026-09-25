// Bilder und Dateien der App innerhalb der App zeigen (D206). Ein Link in ein
// neues Fenster verlässt auf dem iPhone die Web-App vom Home-Bildschirm; dort
// gibt es weder Zurück-Pfeil noch Schließen. Die Ansicht liegt deshalb über der
// Seite und hat immer einen Schließen-Knopf.

export const fileView = $state({ open: null });

/** Öffnet eine Datei der App in der Ansicht. url wie im Link (./api/…). */
export function showFile(url, title = '') {
  if (!url) return;
  fileView.open = { url, title };
  try { history.pushState({ ...(history.state || {}), fileViewer: true }, ''); } catch { /* ohne Verlauf geht es auch */ }
}

export function closeFile() {
  if (!fileView.open) return;
  fileView.open = null;
  try { if (history.state?.fileViewer) history.back(); } catch { /* egal */ }
}

/** Nur eigene Dateien der App abfangen: gleiche Adresse und Pfad mit /api/. */
export function inAppFile(anchor) {
  if (!anchor || anchor.hasAttribute('download')) return null;
  const href = anchor.getAttribute('href') || '';
  if (!href || href.startsWith('#')) return null;
  let url;
  try { url = new URL(href, location.href); } catch { return null; }
  if (url.origin !== location.origin || !url.pathname.includes('/api/')) return null;
  // Das Einrichtungsprofil fürs iPhone muss direkt geöffnet werden (Einstellungen).
  if (url.pathname.includes('/api/admin/webclip')) return null;
  return href;
}
