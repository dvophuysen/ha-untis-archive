// Schnellzugriffe der Startseite: Seite des Kindes plus Abschnitt darauf.
// Der Abschnitt steht als ?s=… im Hash; die Zielseite markiert ihre Abschnitte
// mit data-section. Seiten laden ihre Daten erst nach dem Wechsel, deshalb
// wird eine Weile nach dem Ziel gesucht.

export function jumpHash({ page, args = [], section = null }) {
  const path = [page, ...args.map((a) => encodeURIComponent(a))].join('/');
  return `#/${path}${section ? `?s=${encodeURIComponent(section)}` : ''}`;
}

export function sectionParam(hash = window.location.hash) {
  const query = hash.split('?')[1];
  return query ? new URLSearchParams(query).get('s') : null;
}

export function jumpTo(section, { tries = 50, wait = 100 } = {}) {
  if (!section) return () => {};
  let timer = null, left = tries;
  const step = () => {
    const el = document.querySelector(`[data-section="${CSS.escape(section)}"]`);
    if (!el) {
      if (--left > 0) timer = setTimeout(step, wait);
      return;
    }
    if (el.tagName === 'DETAILS') el.open = true;
    const fold = el.parentElement?.closest('details');
    if (fold) fold.open = true;
    el.scrollIntoView({ block: 'start', behavior: 'smooth' });
    el.classList.add('jump-target');
    timer = setTimeout(() => el.classList.remove('jump-target'), 1800);
  };
  step();
  return () => clearTimeout(timer);
}
