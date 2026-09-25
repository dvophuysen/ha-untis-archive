// Schnellzugriffe der Startseite: Seite des Kindes plus Abschnitt darauf.
// Der Abschnitt steht als ?s=… im Hash; die Zielseite markiert ihre Abschnitte
// mit data-section. Seiten laden ihre Daten erst nach dem Wechsel, manche
// warten auf den Schulkalender; gesucht wird deshalb bis zu 15 Sekunden, aber
// nicht mehr, sobald man selbst scrollt oder tippt.

export function jumpHash({ page, args = [], section = null, query = null }) {
  const path = [page, ...args.map((a) => encodeURIComponent(a))].join('/');
  const params = new URLSearchParams(query ?? {});
  if (section) params.set('s', section);
  const q = params.toString();
  return `#/${path}${q ? `?${q}` : ''}`;
}

export function sectionParam(hash = window.location.hash) {
  const query = hash.split('?')[1];
  return query ? new URLSearchParams(query).get('s') : null;
}

const INTERRUPTS = ['wheel', 'touchmove', 'keydown', 'mousedown'];

export function jumpTo(section, { tries = 150, wait = 100 } = {}) {
  if (!section) return () => {};
  let timer = null, left = tries, found = null, done = false;
  const stop = () => {
    done = true;
    clearTimeout(timer);
    INTERRUPTS.forEach((type) => window.removeEventListener(type, stop, true));
  };
  INTERRUPTS.forEach((type) => window.addEventListener(type, stop, { capture: true, passive: true }));
  const step = () => {
    if (done) return;
    // Mehrere Abschnitte mit Komma: der erste, den es gibt (vor der Schule
    // heißt „Lernen“ anders als nachmittags).
    const el = section.split(',').map((s) => document.querySelector(`[data-section="${CSS.escape(s.trim())}"]`)).find(Boolean);
    if (!el) {
      if (--left > 0) timer = setTimeout(step, wait);
      else stop();
      return;
    }
    INTERRUPTS.forEach((type) => window.removeEventListener(type, stop, true));
    if (el.tagName === 'DETAILS') el.open = true;
    const fold = el.parentElement?.closest('details');
    if (fold) fold.open = true;
    const calm = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    el.scrollIntoView({ block: 'start', behavior: calm ? 'auto' : 'smooth' });
    found = el;
    el.classList.add('jump-target');
    timer = setTimeout(() => el.classList.remove('jump-target'), 1800);
  };
  step();
  return () => {
    stop();
    found?.classList.remove('jump-target');
  };
}
