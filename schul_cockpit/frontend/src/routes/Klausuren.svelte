<script>
  // Arbeiten & Tests: je Arbeit drei Punkte (Stoff, Material, Üben) und darunter
  // die Themen der offiziellen Themenliste mit ihrer Stufe. Grün liegt vor oder
  // sitzt, gelb angenommen oder wackelt, rot fehlt, grau noch nichts.
  import { api } from '../lib/api.js';
  import { formatShortDate, daysBetween, isoToday } from '../lib/format.js';
  import { appState } from '../lib/store.svelte.js';
  import { subjectStyle } from '../lib/subjectStyle.js';
  import PracticeRaster from '../lib/PracticeRaster.svelte';
  import { view, actsAsParent } from '../lib/viewMode.svelte.js';

  let { accountId } = $props();
  const today = isoToday();

  let data = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let busyKey = $state(null);
  let archive = $state(null);
  let archiveOpen = $state(false);
  let pastOpen = $state(false);
  // Direkt zu einer Arbeit: ?exam=… oder der Schnellzugriff der Startseite ?s=arbeit-….
  const query = new URLSearchParams(window.location.hash.split('?')[1] || '');
  const jumped = (query.get('s') || '').startsWith('arbeit-') ? query.get('s').slice(7) : '';
  let openKey = $state(query.get('exam') || jumped);
  let newTopic = $state({});
  // Hinweise und Themenzeilen der Eltern je Arbeit (D193).
  let noteDraft = $state({});
  let linesDraft = $state({});
  let noteSaved = $state('');
  // Abgewählte Referenzen der Sprechprobe je Arbeit (D194); ungesehen gilt der Stand vom Server.
  let refsOff = $state({});
  function refChecked(e, r) { return refsOff[e.exam_key] ? !refsOff[e.exam_key].includes(r.key) : r.checked; }
  // Abgewählt ist, was bisher abgewählt war: Referenzen der Sprechprobe und Themen der Arbeit teilen sich die Liste (D199).
  function offNow(e) {
    return [...(e.references || []).filter((x) => !x.checked).map((x) => x.key),
            ...(e.topics || []).filter((t) => t.excluded).map((t) => `topic:${t.id}`)];
  }
  function toggleRef(e, r) {
    const now = refsOff[e.exam_key] ?? offNow(e);
    refsOff[e.exam_key] = now.includes(r.key) ? now.filter((k) => k !== r.key) : [...now, r.key];
  }
  function countedTopics(e) {
    return (e.topics || []).filter((t) => !t.stale && !t.vocab).map((t) => ({ key: `topic:${t.id}`, label: t.title, checked: !t.excluded }));
  }
  // Angeheftetes Material je Arbeit (D199).
  let pinDraft = $state({});
  function pinnedNow(e) { return pinDraft[e.exam_key] ?? (e.materials || []).filter((x) => x.pinned).map((x) => x.id); }
  function togglePin(e, m) {
    const now = pinnedNow(e);
    pinDraft[e.exam_key] = now.includes(m.id) ? now.filter((x) => x !== m.id) : [...now, m.id];
  }
  function oralUrl(e, t = null) {
    return `#/learning?oral=${encodeURIComponent(e.exam_key)}${t ? `&topic_id=${t.id}` : ''}`;
  }
  async function setVerdict(e, sim, v) {
    const next = sim.verdict === v ? null : v;
    try {
      await api.post(`/api/accounts/${accountId}/exams/oral-sims/${sim.id}/verdict`, { verdict: next });
      sim.verdict = next;
      data = { ...data };
    } catch (err) {
      error = err.message;
    }
  }

  // Eltern-Werkzeuge nicht beim Mitlesen und nicht, wenn das Kind das Gerät benutzt (D183).
  const canManage = $derived(actsAsParent(appState.me));

  async function load() {
    if (!accountId) return;
    loading = true;
    error = null;
    try {
      data = await api.get(`/api/accounts/${accountId}/exams/all`);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
  $effect(() => { void accountId; load(); });

  async function openArchive() {
    archiveOpen = !archiveOpen;
    if (!archiveOpen || archive) return;
    try {
      archive = (await api.get(`/api/accounts/${accountId}/exams/archive`)).exams;
    } catch (e) {
      error = e.message;
    }
  }

  async function saveProgress(exam, patch) {
    busyKey = exam.exam_key;
    try {
      await api.post(`/api/accounts/${accountId}/exam-progress`, { exam_key: exam.exam_key, ...patch });
      if (patch.clear_grade) exam.grade_points = null;
      else if ('grade_points' in patch) exam.grade_points = patch.grade_points;
      if ('learn_state' in patch) exam.learn_state = patch.learn_state;
      data = { ...data };
    } catch (e) {
      error = e.message;
    } finally {
      busyKey = null;
    }
  }

  // Das Gefühl zur ganzen Arbeit: drei Stufen, nur ein Sortierhinweis.
  const FEEL = [
    { v: 1, label: 'viel offen' },
    { v: 2, label: 'mittel' },
    { v: 3, label: 'sicher' },
  ];
  const TOPIC_FEEL = ['unsicher', 'mittel', 'sicher'];

  // „Montag, 21.09.“: der ganze Wochentag, dann Tag und Monat.
  function longDay(iso) {
    const d = new Date(`${iso}T12:00:00`);
    return `${d.toLocaleDateString('de-DE', { weekday: 'long' })}, ${d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })}`;
  }
  function whenLabel(dateIso) {
    const d = daysBetween(today, dateIso);
    if (d === 0) return 'heute';
    if (d === 1) return 'morgen';
    if (d === 2) return 'übermorgen';
    if (d < 0) return `vor ${Math.abs(d)} Tagen`;
    if (d % 7 === 0 && d >= 14) return `in ${d / 7} Wochen`;
    return `in ${d} Tagen`;
  }
  function urgencyClass(dateIso) {
    const d = daysBetween(today, dateIso);
    if (d <= 2) return 'now';
    if (d <= 7) return 'soon';
    if (d <= 21) return 'mid';
    return 'far';
  }
  function sinceLabel(s) {
    if (!s?.since) return 'seit Schuljahresbeginn';
    const start = new Date(`${s.since}T00:00:00`);
    const august = start.getMonth() === 7 && start.getDate() === 1;
    return august ? 'seit Schuljahresbeginn' : `seit der letzten Arbeit am ${formatShortDate(s.since)}`;
  }
  function liveTopics(e) {
    return (e.topics || []).filter((t) => !t.stale && !t.excluded);
  }
  function materialUrl(e) {
    return `#/materialien/${encodeURIComponent(e.subject_name ?? '')}`;
  }
  function practiceUrl(e) {
    const q = new URLSearchParams({ subject: e.subject_name ?? '', topic: e.title ?? '', mode: 'exam' });
    return `#/learning?${q.toString()}`;
  }

  // Die drei Punkte je Arbeit.
  function stoff(e) {
    const n = liveTopics(e).length;
    if (e.oral) {
      const own = liveTopics(e).filter((t) => t.origin === 'manual').length;
      const layout = e.sources?.notice ? ' · Ablauf laut Zettel der Lehrkraft' : '';
      return {
        tone: own ? 'ok' : 'warn',
        text: own ? `Sprechprüfung${layout} · ${own} ${own === 1 ? 'Sprechthema' : 'Sprechthemen'} eingetragen`
          : `Sprechprüfung${layout} · noch keine Sprechthemen eingetragen; geübt wird in Gesamtproben, der Stoff aus dem Unterricht ist Maßstab`,
        action: { label: canManage ? 'eintragen' : 'ansehen', open: true },
      };
    }
    if (e.sources?.notice) {
      const checked = e.sources.notice_verified;
      return {
        tone: checked ? 'ok' : 'warn',
        text: `Offizielle Themenliste liegt vor · ${n} ${n === 1 ? 'Thema' : 'Themen'}${checked ? '' : ' · eine Seitenzahl bitte prüfen'}`,
        action: checked ? { label: 'ansehen', open: true } : { label: 'gegenlesen', href: `#/materialien?material=${e.sources.notice_id}` },
      };
    }
    const parts = e.scope?.parts || 0;
    return {
      tone: parts ? 'warn' : 'none',
      text: `Keine Themenliste · angenommen: alles ${sinceLabel(e.scope)}${parts ? `, ${parts} ${parts === 1 ? 'Thema' : 'Themen'}` : ''}`,
      action: canManage ? { label: 'Themen eintragen', open: true }
        : { label: 'Zettel fotografieren', href: materialUrl(e), title: 'Zettel oder Tafelfoto der Lehrkraft fotografieren' },
    };
  }
  function material(e) {
    const s = e.sources;
    if (!s || !s.total) return { tone: 'none', text: 'Noch keine Buchstelle genannt', action: null };
    const have = `${s.ready} von ${s.total} ${s.total === 1 ? 'Stelle' : 'Stellen'} da`;
    if (s.missing) {
      const gaps = s.missing_items.map((m) => `${m.label} ${m.pages_label}`).join(' · ');
      return { tone: 'bad', text: `${have} · fehlt ${gaps}`, action: { label: 'fotografieren', href: materialUrl(e) } };
    }
    if (s.pending) {
      // Was noch fehlt, hat einen Grund: Foto da, aber noch nicht gelesen; Lesen
      // gescheitert (wird nachts wiederholt); Seite wird aus dem Buch geholt.
      const items = s.pending_items || [];
      const name = (i) => (i.page ? `${i.label} S. ${i.page}` : i.label);
      const failed = items.filter((i) => i.kind === 'failed');
      const budget = items.filter((i) => i.kind === 'budget');
      const unread = items.filter((i) => i.kind === 'unread');
      const fetching = items.filter((i) => i.kind === 'fetching');
      const bits = [];
      if (budget.length) bits.push(`${budget.map(name).join(', ')} liegt da, wartet auf freien KI-Rahmen (Eltern: Rahmen im Mentor)`);
      if (failed.length) bits.push(`${failed.map(name).join(', ')} liegt da, Lesen ist gescheitert und wird wiederholt`);
      if (unread.length) bits.push(`${unread.map(name).join(', ')} liegt da, wird noch gelesen`);
      if (fetching.length) bits.push(`${fetching.map(name).join(', ')} wird aus dem Buch geholt`);
      const first = budget[0] || failed[0] || unread[0];
      return { tone: 'warn', text: `${have} · ${bits.join(' · ') || `${s.pending} noch nicht gelesen`}`,
               action: first?.material_id ? { label: 'ansehen', href: `#/materialien?material=${first.material_id}` } : null };
    }
    return { tone: 'ok', text: have, action: null };
  }
  function stagesText(e) {
    const st = e.stages || {};
    const parts = [];
    for (const k of ['gefestigt', 'sitzt', 'wackelt', 'angefangen', 'neu']) if (st[k]) parts.push(`${st[k]} ${k}`);
    return parts.length ? parts.join(' · ') : 'noch nichts geübt';
  }
  function ueben(e) {
    const st = e.stages;
    const topics = liveTopics(e);
    if (topics.length && st) {
      const done = (st.sitzt || 0) + (st.gefestigt || 0);
      const tone = done === topics.length ? 'ok' : done || st.wackelt || st.angefangen ? 'warn' : 'none';
      return { tone, text: stagesText(e), action: { label: done || st.wackelt ? 'weiter' : 'anfangen', open: true } };
    }
    if (e.scope?.parts) {
      return {
        tone: e.scope.shown ? 'warn' : 'none',
        text: `${e.scope.shown} von ${e.scope.parts} ${e.scope.parts === 1 ? 'Thema' : 'Themen'} ohne Hilfe gezeigt`,
        action: { label: 'üben', href: practiceUrl(e) },
      };
    }
    const p = e.practice;
    if (p && (p.units || p.independent || p.papers)) {
      return { tone: 'warn', text: `${p.units} ${p.units === 1 ? 'Einheit' : 'Einheiten'} in ${Math.round(p.days / 7)} Wochen`, action: { label: 'üben', href: practiceUrl(e) } };
    }
    return { tone: 'none', text: 'Noch nichts geübt', action: { label: 'üben', href: practiceUrl(e) } };
  }

  function toggle(e) {
    openKey = openKey === e.exam_key ? '' : e.exam_key;
  }
  function topicUrl(t, e) {
    if (t.vocab) return `#/vokabeln/${encodeURIComponent(e.subject_name ?? '')}${t.vocab_unit ? `?unit=${encodeURIComponent(t.vocab_unit)}` : ''}`;
    return `#/learning?topic_id=${t.id}`;
  }
  function topicAction(t) {
    if (t.check_due) return 'Prüfen';
    if (t.stage === 'gefestigt') return 'Noch einmal';
    if (t.stage === 'sitzt') return 'Wiederholen';
    return 'Üben';
  }
  async function setFeel(topic, value) {
    busyKey = `topic-${topic.id}`;
    try {
      const next = topic.self_view === value ? null : value;
      const t = await api.post(`/api/accounts/${accountId}/exams/topics/${topic.id}/self-view`, { value: next });
      topic.self_view = t.self_view;
      data = { ...data };
    } catch (e) {
      error = e.message;
    } finally {
      busyKey = null;
    }
  }
  async function saveNote(exam) {
    busyKey = `note-${exam.exam_key}`;
    noteSaved = '';
    try {
      const text = noteDraft[exam.exam_key] ?? exam.note ?? '';
      const refs = refsOff[exam.exam_key];
      const pins = pinDraft[exam.exam_key];
      if (text !== (exam.note || '') || refs || pins) {
        const r = await api.post(`/api/accounts/${accountId}/exams/note`, {
          exam_key: exam.exam_key, note: text, ...(refs ? { excluded_refs: refs } : {}), ...(pins ? { pinned_materials: pins } : {}),
        });
        exam.note = r.note;
        delete refsOff[exam.exam_key];
        delete pinDraft[exam.exam_key];
      }
      // Eine Zeile je Thema; „Thema: Hinweis“ trennt den Hinweis ab.
      const lines = (linesDraft[exam.exam_key] || '').split('\n').map((l) => l.trim()).filter((l) => l.length >= 2);
      for (const line of lines) {
        const [title, ...rest] = line.split(':');
        try {
          const t = await api.post(`/api/accounts/${accountId}/exams/topics`, {
            exam_key: exam.exam_key, subject: exam.subject_name ?? exam.title ?? '',
            title: title.trim().slice(0, 120), detail: rest.join(':').trim().slice(0, 400),
          });
          exam.topics = [...(exam.topics || []), { ...t, material: null, check_due: false }];
        } catch (err) {
          if (!String(err.message).includes('schon')) throw err;
        }
      }
      linesDraft[exam.exam_key] = '';
      // Themen, Referenzen und Material neu laden: Plan, Raster und Karte richten sich danach.
      await load();
      noteSaved = exam.exam_key;
      data = { ...data };
    } catch (e) {
      error = e.message;
    } finally {
      busyKey = null;
    }
  }
  async function addTopic(exam) {
    const title = (newTopic[exam.exam_key] || '').trim();
    if (title.length < 2) return;
    busyKey = exam.exam_key;
    try {
      const t = await api.post(`/api/accounts/${accountId}/exams/topics`, {
        exam_key: exam.exam_key, subject: exam.subject_name ?? exam.title ?? '', title,
      });
      exam.topics = [...(exam.topics || []), { ...t, material: null, check_due: false }];
      exam.stages = { ...(exam.stages || {}), neu: (exam.stages?.neu || 0) + 1 };
      newTopic[exam.exam_key] = '';
      data = { ...data };
    } catch (e) {
      error = e.message;
    } finally {
      busyKey = null;
    }
  }
  async function removeTopic(exam, topic) {
    if (!confirm(`„${topic.title}“ von der Liste nehmen?`)) return;
    try {
      await api.delete(`/api/accounts/${accountId}/exams/topics/${topic.id}`);
      exam.topics = exam.topics.filter((t) => t.id !== topic.id);
      data = { ...data };
    } catch (e) {
      error = e.message;
    }
  }
  function alsoCovered(e) {
    // Im Unterricht behandelt, aber nicht auf der Themenliste.
    if (!e.sources?.notice || !e.scope?.topics?.length) return [];
    const listed = liveTopics(e).map((t) => t.title.toLowerCase());
    return e.scope.topics.filter((s) => !listed.some((l) => l.includes(s.title.toLowerCase()) || s.title.toLowerCase().includes(l)));
  }
</script>

<div class="row between" style="margin: 0 0 0.6rem; align-items:center;">
  <h2 style="margin:0; font-size:1.15rem;">📝 Arbeiten & Tests</h2>
  {#if canManage}
    <button class="ghost" style="font-size:0.85rem; min-height:32px;" onclick={() => (window.location.hash = '#/exams')} title="Kalender verknüpfen, Termine ergänzen">✏️ verwalten</button>
  {/if}
</div>

{#if error}<div class="error-box">{error}</div>{/if}

{#if loading || !data}
  <div class="empty"><span class="spinner"></span></div>
{:else}
  {#if data.calendar_error}
    <div class="error-box">Kalender-Fehler: {data.calendar_error}</div>
  {/if}

  {#if data.upcoming.length === 0}
    <div class="empty" style="padding:1rem;">Keine Arbeiten eingetragen. Sie kommen aus dem IServ-Klausurplan, sobald die Schule sie dort einträgt.</div>
  {:else}
    {#each data.upcoming as e (e.exam_key)}
      {@const st = subjectStyle(e.subject_name ?? e.title)}
      {@const open = openKey === e.exam_key}
      {@const far = urgencyClass(e.date) === 'far' && !open}
      {@const S = stoff(e)}
      {@const M = material(e)}
      {@const U = ueben(e)}
      {@const topics = liveTopics(e)}
      <div class="card exam" class:compact={far} data-section={`arbeit-${e.exam_key}`}>
        <button class="exam-head" onclick={() => toggle(e)} aria-expanded={open}>
          <span class="icon" aria-hidden="true">{st.emoji}</span>
          <span class="who">
            <strong>{st.name}</strong>
            <span class="dim">{longDay(e.date)}{#if far} · {whenLabel(e.date)}{/if}{#if e.source === 'manual'} · selbst eingetragen{/if}{#if e.oral} · <b class="oral">Sprechprüfung</b>{/if}</span>
            {#if e.title && e.subject_name && e.title !== e.subject_name}<span class="dim ellipsis" title={e.title}>{e.title}</span>{/if}
          </span>
          {#if !far}<span class="badge when {urgencyClass(e.date)}">{whenLabel(e.date)}</span>{:else}<span class="chev" aria-hidden="true">▸</span>{/if}
        </button>

        {#if !far}
          <div class="points">
            {#each [['Stoff', S], ['Material', M], ['Üben', U]] as [name, p]}
              <div class="point">
                <span class="dot {p.tone}" aria-hidden="true"></span>
                <span class="point-text"><strong class="point-name">{name}</strong> {p.text}</span>
                {#if p.action?.open}
                  <button class="point-go" onclick={() => (openKey = e.exam_key)}>{p.action.label}</button>
                {:else if p.action?.href}
                  <a class="point-go" href={p.action.href} title={p.action.title ?? ''}>{p.action.label}</a>
                {/if}
              </div>
            {/each}
          </div>

          {#if e.note && !open}<p class="exam-note"><b>Hinweise:</b> {e.note}</p>{/if}
          {#if !open}
            <div class="cta">
              <button class="primary go" onclick={() => (openKey = e.exam_key)}>Für {st.name} üben</button>
              <div class="feel-row">
                <span class="dim feel-label">Dein Gefühl, hilft mir beim Sortieren:</span>
                {#each FEEL as f}
                  <button class="feel" class:active={e.learn_state === f.v} disabled={busyKey === e.exam_key} onclick={() => saveProgress(e, { learn_state: f.v })}>{f.label}</button>
                {/each}
              </div>
            </div>
          {/if}
        {/if}

        {#if open}
          <div class="detail">
            {#if canManage}
              <div class="note-box" data-section={`hinweise-${e.exam_key}`}>
                <label><strong>Hinweise zur Arbeit</strong>
                  <small class="dim">{e.oral ? 'Zum Beispiel: worüber gesprochen wird, Ablauf, Partnergespräch, Bildbeschreibung.' : 'Was die Lehrkraft dazu gesagt hat. Die Kinder lesen mit, der Lernbegleiter bekommt es mit.'}</small>
                  <textarea rows="4" maxlength="2000" bind:value={() => noteDraft[e.exam_key] ?? e.note ?? '', (v) => (noteDraft[e.exam_key] = v)} placeholder={e.oral ? 'Sich vorstellen, Hobbys, Ferien; Bild beschreiben; Gespräch zu zweit …' : 'Hinweise der Lehrkraft …'}></textarea>
                </label>
                <label><strong>{e.oral ? 'Sprechthemen' : 'Themen'} ergänzen</strong>
                  <small class="dim">Eine Zeile je Thema, ein Hinweis nach Doppelpunkt, z. B. „Meine Familie: Personen beschreiben“.{#if e.oral} Sobald eigene Sprechthemen da sind, tritt der Stoff aus dem Unterricht zurück.{/if}</small>
                  <textarea rows="3" bind:value={() => linesDraft[e.exam_key] ?? '', (v) => (linesDraft[e.exam_key] = v)}></textarea>
                </label>
                {#if !e.oral && countedTopics(e).length}
                  <fieldset class="refs">
                    <legend><strong>Stoff für diese Arbeit</strong></legend>
                    <small class="dim">Abgewählte Themen zählen nicht: kein Schritt im Lernplan, keine Aufgabe in Übungsarbeiten. Ihr Lernstand bleibt erhalten.</small>
                    {#each countedTopics(e) as r (r.key)}
                      <label class="ref"><input type="checkbox" checked={refChecked(e, r)} onchange={() => toggleRef(e, r)} /> {r.label}</label>
                    {/each}
                  </fieldset>
                {/if}
                {#if e.materials?.length}
                  <fieldset class="refs">
                    <legend><strong>Material zum Üben anheften</strong></legend>
                    <small class="dim">Angeheftetes nimmt der Lernbegleiter gezielt dran, Übungsarbeiten bauen Aufgaben daraus, Abbildungen darauf können mitgedruckt werden.</small>
                    <div class="pins">
                      {#each e.materials as m (m.id)}
                        <label class="pin" class:on={pinnedNow(e).includes(m.id)}>
                          <input type="checkbox" checked={pinnedNow(e).includes(m.id)} onchange={() => togglePin(e, m)} />
                          {#if m.image}<img src={`./api/accounts/${accountId}/materials/${m.id}/thumb`} alt="" loading="lazy" />{:else}<span class="doc" aria-hidden="true">📄</span>{/if}
                          <span>{m.label}<small class="dim">{m.day ? formatShortDate(m.day) : ''}</small></span>
                        </label>
                      {/each}
                    </div>
                  </fieldset>
                {/if}
                {#if e.oral && e.references?.length}
                  <fieldset class="refs">
                    <legend><strong>Aus dem Unterricht als Maßstab</strong></legend>
                    <small class="dim">Keine eigenen Übungen: Der Prüfer nimmt Wörter und Grammatik daraus und bewertet daran. Was hier vorkam, zählt voll; Neues ist Bonus.</small>
                    {#each e.references as r (r.key)}
                      <label class="ref"><input type="checkbox" checked={refChecked(e, r)} onchange={() => toggleRef(e, r)} /> {r.label}</label>
                    {/each}
                  </fieldset>
                {/if}
                <div class="row" style="gap:0.5rem; align-items:center;">
                  <button class="primary" disabled={busyKey === `note-${e.exam_key}`} onclick={() => saveNote(e)}>{busyKey === `note-${e.exam_key}` ? 'Speichert …' : 'Speichern'}</button>
                  {#if noteSaved === e.exam_key}<span class="dim" role="status">Gespeichert.</span>{/if}
                </div>
              </div>
            {:else if e.note}
              <p class="exam-note"><b>Hinweise:</b> {e.note}</p>
            {/if}
            {#if (e.materials || []).some((m) => m.pinned)}
              <p class="dim pinned-line">Angeheftet zum Üben: {(e.materials || []).filter((m) => m.pinned).map((m) => m.label).join(' · ')}</p>
            {/if}
            {#if e.oral}
              <p class="lead">Sprechprüfung: Geübt wird in Sprechproben mit dem Lernbegleiter als Prüfer, per Sprechknopf. Am Ende jeder Probe gibt es eine Bewertung nach sechs Kriterien und höchstens drei Baustellen, die die nächste Probe gezielt nachprüft. Kein Einstiegstest und keine Übungsarbeit auf Papier.</p>
              <div class="row" style="gap:0.5rem; flex-wrap:wrap; margin-bottom:0.6rem;">
                <a class="point-go" href={oralUrl(e)}>🎤 {e.oral_sims?.some((x) => x.reliable) ? 'Gesamtprobe' : 'Einstiegstest Sprechprüfung'}</a>
                {#each topics.filter((t) => t.origin === 'manual') as t (t.id)}<a class="point-go" href={oralUrl(e, t)}>🎤 {t.title}</a>{/each}
              </div>
              {#if e.oral_sims?.length}
                <div class="sims" aria-label="Sprechproben">
                  <strong>Bisherige Sprechproben</strong>
                  {#each e.oral_sims as sim (sim.id)}
                    <div class="sim">
                      <div class="sim-head"><span>{formatShortDate(sim.created_at.slice(0, 10))} · {sim.topic_title || 'Themenprobe'}</span>
                        <span class="dim">{sim.reliable ? sim.scores.map((x) => `${x.label.split(' ')[0]} ${x.score}`).join(' · ') : 'zu kurz'}</span></div>
                      {#if sim.weak_spots?.length}<div class="dim">Baustellen: {sim.weak_spots.map((w) => w.label).join(', ')}</div>{/if}
                      <div class="feel-row">
                        <a class="dim" href={`#/learning?session=${sim.session_id}`}>Gespräch lesen</a>
                        {#if canManage}
                          <span class="dim">Bewertung war:</span>
                          {#each [['streng', 'zu streng'], ['passt', 'passt'], ['mild', 'zu mild']] as [v, label]}
                            <button class="feel" class:active={sim.verdict === v} onclick={() => setVerdict(e, sim, v)}>{label}</button>
                          {/each}
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}
            {:else if e.sources?.notice}
              <p class="lead">Die offizielle Themenliste der Lehrkraft legt den Stoff fest.
                <a href={`#/materialien?material=${e.sources.notice_id}`}>Foto ansehen</a>{#if !e.sources.notice_verified} · <a href={`#/materialien?material=${e.sources.notice_id}`}>Bitte prüfen</a>: Eine Seitenzahl kennt der Unterricht nicht.{/if}</p>
            {:else}
              <p class="lead">Keine offizielle Themenliste. Bis die Lehrkraft eingrenzt, zählt alles, was im Unterricht behandelt wurde {sinceLabel(e.scope)}. Sobald ein Zettel oder Tafelfoto vorliegt, <a href={materialUrl(e)}>lege es unter Materialien ab</a>.</p>
            {/if}

            {#if topics.length}
              <div class="row between" style="align-items:baseline; gap:0.5rem; flex-wrap:wrap;">
                <strong>{e.sources?.notice ? 'Offizielle Themenliste' : 'Angenommener Stoff aus dem Unterricht'}, {topics.length} {topics.length === 1 ? 'Thema' : 'Themen'}</strong>
                <span class="dim">sortiert: Wackler zuerst · {stagesText(e)}</span>
              </div>
              <div class="topics">
                {#each topics as t (t.id)}
                  <div class="topic">
                    <div class="topic-head">
                      <span class="topic-title">{t.title}</span>
                      <a class="topic-go" href={topicUrl(t, e)}>{topicAction(t)}</a>
                    </div>
                    <div class="topic-meta">
                      <span class="stage {t.stage}">{t.stage}</span>
                      {#if t.reason && t.stage !== 'neu'}<span class="dim">· {t.reason}</span>{:else if t.vocab && t.words}<span class="dim">· {t.words} Wörter im Trainer</span>{/if}
                      {#if t.note}<span class="dim">· {t.note}</span>{/if}
                      {#if t.self_view}<span class="dim">· Du sagst: {t.self_view}</span>{/if}
                    </div>
                    {#if t.check_due}<div class="dim topic-why">Kurzprüfung fällig: sitzt es noch, gilt es als gefestigt.</div>{/if}
                    <div class="dim topic-why">
                      {#if t.places_label}{t.places_label}{#if t.material?.total} · {t.material.have} von {t.material.total} Seiten da{/if}{#if t.material?.missing?.length} · <a class="missing" href={materialUrl(e)}>fehlt {t.material.missing_label}</a>{/if}{:else}Keine Stelle genannt; der Mentor arbeitet mit dem Kapitel zum Thema.{/if}
                    </div>
                    <div class="feel-row">
                      <span class="dim">Dein Gefühl:</span>
                      {#each TOPIC_FEEL as v}
                        <button class="feel" class:active={t.self_view === v} disabled={busyKey === `topic-${t.id}`} onclick={() => setFeel(t, v)}>{v}</button>
                      {/each}
                    </div>
                  </div>
                {/each}
              </div>
            {:else if e.scope?.topics?.length}
              <div class="topics">
                {#each e.scope.topics as s (s.id)}
                  <div class="topic"><div class="topic-head"><span class="topic-title">{s.title}{#if s.field}<small class="dim"> · {s.field}</small>{/if}</span><span class="stage {s.shown ? 'sitzt' : 'neu'}">{s.shown ? 'gezeigt' : 'neu'}</span></div></div>
                {/each}
              </div>
            {/if}

            {#if topics.some((t) => !t.vocab) && !e.oral}
              <PracticeRaster {accountId} examKey={e.exam_key} parent={canManage && view.mode !== 'child'} />
            {/if}

            <form class="add-topic" onsubmit={(ev) => { ev.preventDefault(); addTopic(e); }}>
              <input type="text" maxlength="120" placeholder="Thema ergänzen, das die Lehrkraft genannt hat" bind:value={newTopic[e.exam_key]} />
              <button class="ghost" disabled={busyKey === e.exam_key || (newTopic[e.exam_key] || '').trim().length < 2}>Hinzufügen</button>
            </form>

            {#if alsoCovered(e).length}
              <details class="also"><summary>Auch behandelt, nicht auf der Liste · {alsoCovered(e).length} {alsoCovered(e).length === 1 ? 'Thema' : 'Themen'}</summary>
                <p class="dim">Nur auf Wunsch üben; die Themenliste geht vor.</p>
                {#each alsoCovered(e) as s (s.id)}<div class="dim also-row">{s.title}{#if s.field} · {s.field}{/if}</div>{/each}
              </details>
            {/if}

            {#if e.sources?.chapters?.length}
              <details class="also"><summary>Kapitel im Zeitraum</summary>
                {#each e.sources.chapters as chapter}
                  <div class="dim also-row">{chapter.part_label ? `${chapter.part_label}, ` : ''}Kapitel {chapter.number} {chapter.title} (S. {chapter.start_page}{chapter.end_page ? `–${chapter.end_page}` : ''}): {chapter.pages_stored} von {chapter.pages} Seiten da{#if chapter.inferred}, aus dem Stundenthema erschlossen{/if}</div>
                {/each}
              </details>
            {/if}

            <div class="row between" style="align-items:center; margin-top:0.8rem; gap:0.6rem; flex-wrap:wrap;">
              {#if !e.oral}<a class="practice-link" href={practiceUrl(e)}>Übungsarbeit wie in echt</a>{:else}<span></span>{/if}
              <div class="feel-row">
                <span class="dim">Dein Gefühl zur ganzen Arbeit</span>
                {#each FEEL as f}
                  <button class="feel" class:active={e.learn_state === f.v} disabled={busyKey === e.exam_key} onclick={() => saveProgress(e, { learn_state: f.v })}>{f.label}</button>
                {/each}
              </div>
            </div>
            <p class="dim legend">Sitzt heißt: ohne Hilfe, ohne Zögern, in verschiedenen Aufgaben. Gefestigt heißt: nach drei und nach sieben Tagen noch einmal bestätigt. Dein Gefühl sortiert, es zählt nicht als Beleg.</p>
            {#if canManage}
              <div class="dim" style="font-size:0.78rem;">
                {#if e.source === 'manual'}nicht aus dem Klausurplan — unter <a href="#/exams">Verwalten</a> änderbar.{:else}kommt aus dem IServ-Klausurplan — geändert wird er dort.{/if}
              </div>
              {#if topics.length}
                <details class="also"><summary>Themen bearbeiten (Eltern)</summary>
                  <p class="dim">Entfernen löscht auch den Lernstand des Themas. Aus der Themenliste gelesene Themen kämen beim nächsten Lesen wieder.</p>
                  {#each topics as t (t.id)}<div class="also-row"><button class="feel ghost" onclick={() => removeTopic(e, t)}>Entfernen</button> {t.title}</div>{/each}
                </details>
              {/if}
            {/if}
            <button class="ghost close" onclick={() => (openKey = '')}>▴ zuklappen</button>
          </div>
        {/if}
      </div>
    {/each}
    <p class="dim legend">Drei Punkte je Arbeit: Stoff, Material, Üben. Grün liegt vor oder sitzt, gelb angenommen oder wackelt, rot fehlt, grau noch nichts.</p>
  {/if}

  <!-- VERGANGEN -->
  <button class="ghost" style="width:100%; margin-top:0.8rem;" onclick={() => (pastOpen = !pastOpen)}>
    {pastOpen ? '▾' : '▸'} Vergangene Arbeiten ansehen ({data.past.length})
  </button>
  {#if pastOpen}
    {#if data.past.length === 0}
      <div class="empty" style="padding:1rem;">Noch keine vergangenen Klausuren.</div>
    {:else}
      {#each data.past as e (e.exam_key)}
        <div class="card compact">
          <div class="row between" style="align-items:flex-start;">
            <div style="min-width:0;">
              <strong>{e.subject_name ?? e.title}</strong>
              {#if e.subject_name && e.title && e.title !== e.subject_name}<span class="dim"> · {e.title}</span>{/if}
              <div class="dim">{formatShortDate(e.date)}</div>
            </div>
            <div class="grade-box">
              <select class="grade-input" value={e.grade_points ?? ''}
                onchange={(ev) => { const v = ev.currentTarget.value; if (v === '') saveProgress(e, { clear_grade: true }); else saveProgress(e, { grade_points: Number(v) }); }}>
                <option value="">– Note –</option>
                {#each (data.grade_options ?? []) as o}<option value={o.points}>{o.label}</option>{/each}
              </select>
            </div>
          </div>
        </div>
      {/each}
    {/if}
    {#if data.archived_count > 0}
      <button class="ghost" style="width:100%; margin-top:0.8rem;" onclick={openArchive}>
        {archiveOpen ? '▾' : '▸'} Archiv abgeschlossener Schuljahre ({data.archived_count})
      </button>
      {#if archiveOpen}
        {#if archive === null}
          <div class="empty"><span class="spinner"></span></div>
        {:else}
          {#each archive as e (e.exam_key)}
            <div class="card compact">
              <div class="row between" style="align-items:flex-start;">
                <div style="min-width:0;"><strong>{e.subject_name ?? e.title}</strong><div class="dim">{formatShortDate(e.date)}</div></div>
                {#if e.grade_label}<span class="badge">{e.grade_label}</span>{/if}
              </div>
            </div>
          {/each}
        {/if}
      {/if}
    {/if}
  {/if}
{/if}

<style>
  .exam { padding: 0.9rem 1rem; }
  .exam.compact { padding: 0.5rem 0.9rem; }
  .exam-head { display: flex; align-items: center; gap: 0.7rem; width: 100%; text-align: left; background: none; border: 0; padding: 0; color: inherit; font: inherit; cursor: pointer; min-height: 44px; }
  .exam-head .icon { font-size: 1.5rem; }
  .exam-head .who { flex: 1; min-width: 0; display: grid; }
  .exam-head strong { font-size: 1.05rem; }
  .ellipsis { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .chev { opacity: 0.6; }
  .when { white-space: nowrap; }
  .when.now { background: var(--rating-1); color: #fff; border-color: transparent; }
  .when.soon { background: var(--rating-2); color: #fff; border-color: transparent; }
  .when.mid { background: var(--bg); }
  .when.far { background: transparent; opacity: .75; }
  .points { display: grid; gap: 0.35rem; margin-top: 0.7rem; }
  .point { display: grid; grid-template-columns: 12px 1fr auto; gap: 0.5rem; align-items: center; font-size: 0.88rem; }
  .point-name { font-weight: 650; margin-right: 0.15rem; }
  .cta { display: grid; gap: 0.5rem; margin-top: 0.7rem; }
  .cta .feel-label { flex-basis: 100%; }
  .point-text { min-width: 0; overflow-wrap: anywhere; }
  .dot { width: 12px; height: 12px; border-radius: 50%; background: var(--border); }
  .dot.ok { background: var(--rating-3); }
  .dot.warn { background: var(--rating-2); }
  .dot.bad { background: var(--rating-1); }
  .point-go { font-size: 0.8rem; font-weight: 600; text-decoration: none; padding: 0.2rem 0.6rem; border: 1px solid var(--border); border-radius: 999px; background: var(--bg-elevated); color: inherit; min-height: 44px; display: inline-flex; align-items: center; cursor: pointer; font-family: inherit; white-space: nowrap; }
  .go { min-height: 44px; padding: 0.5rem 1rem; border-radius: 12px; font-weight: 650; justify-self: start; }
  .feel-row { display: flex; align-items: center; gap: 0.3rem; font-size: 0.78rem; flex-wrap: wrap; }
  .feel { font-size: 0.75rem; min-height: 44px; padding: 0.2rem 0.6rem; border-radius: 999px; border: 1px solid var(--border); background: var(--bg-elevated); color: inherit; }
  .feel.active { background: var(--accent); border-color: var(--accent); color: var(--accent-fg); }
  .detail { margin-top: 0.8rem; padding-top: 0.6rem; border-top: 1px solid var(--border); }
  .lead { margin: 0 0 0.6rem; font-size: 0.9rem; }
  .topics { display: grid; gap: 0.2rem; margin-top: 0.3rem; font-size: 0.9rem; }
  .topic { padding: 0.5rem 0; border-top: 1px solid var(--border); }
  .topic-head { display: flex; align-items: center; gap: 0.5rem; }
  .topic-title { flex: 1; min-width: 0; font-weight: 600; }
  .topic-go { flex-shrink: 0; font-weight: 600; text-decoration: none; padding: 0.35rem 0.8rem; border: 1px solid var(--accent); border-radius: 999px; min-height: 34px; display: inline-flex; align-items: center; }
  .topic-meta { display: flex; flex-wrap: wrap; gap: 0.3rem; align-items: center; margin-top: 0.2rem; font-size: 0.82rem; }
  .topic-why { font-size: 0.78rem; margin-top: 0.15rem; }
  .stage { font-size: 0.72rem; font-weight: 700; padding: 0.1rem 0.5rem; border-radius: 999px; border: 1px solid var(--border); white-space: nowrap; }
  .stage.neu { background: var(--bg); color: var(--fg-muted); }
  .stage.angefangen { background: color-mix(in oklab, var(--st-angefangen) 30%, var(--bg-card)); border-color: transparent; }
  .stage.wackelt { background: color-mix(in oklab, var(--st-wackelt) 30%, var(--bg-card)); border-color: transparent; }
  .stage.sitzt { background: color-mix(in oklab, var(--st-sitzt) 30%, var(--bg-card)); border-color: transparent; }
  .stage.gefestigt { background: color-mix(in oklab, var(--st-gefestigt) 30%, var(--bg-card)); border-color: transparent; }
  .missing { color: var(--bad-fg); font-weight: 600; }
  .add-topic { display: flex; gap: 0.4rem; margin-top: 0.6rem; }
  .add-topic input { flex: 1; min-width: 0; font-size: 16px; padding: 0.45rem 0.6rem; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-elevated); color: inherit; }
  .also { margin-top: 0.6rem; font-size: 0.88rem; }
  .also summary { min-height: 40px; display: flex; align-items: center; cursor: pointer; }
  .also-row { padding: 0.15rem 0; }
  .practice-link { font-weight: 600; }
  .legend { font-size: 0.78rem; margin: 0.6rem 0 0; }
  .oral { color: var(--accent); font-weight: 600; }
  .exam-note { margin: 0.5rem 0 0; padding: 0.5rem 0.7rem; background: var(--bg-soft, var(--bg)); border-radius: var(--r-sm); white-space: pre-wrap; overflow-wrap: anywhere; }
  .note-box { display: grid; gap: 0.6rem; margin: 0 0 0.8rem; padding: 0.7rem; border: 1px solid var(--border); border-radius: var(--r-sm); }
  .note-box label { display: grid; gap: 0.25rem; }
  .note-box textarea { width: 100%; box-sizing: border-box; font: inherit; }
  .refs { border: 0; padding: 0; margin: 0; display: grid; gap: 0.3rem; min-width: 0; }
  .ref { display: flex; gap: 0.4rem; align-items: flex-start; overflow-wrap: anywhere; }
  .pins { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 0.4rem; }
  .pin { display: grid; grid-template-columns: auto 1fr; gap: 0.3rem; align-items: start; padding: 0.35rem; border: 1px solid var(--border); border-radius: var(--r-sm); overflow-wrap: anywhere; font-size: 0.85rem; }
  .pin.on { border-color: var(--accent); }
  .pin img, .pin .doc { grid-column: 1 / -1; width: 100%; height: 90px; object-fit: cover; border-radius: 4px; background: #fff; display: block; text-align: center; font-size: 2rem; }
  .pin small { display: block; }
  .pinned-line { margin: 0 0 0.6rem; overflow-wrap: anywhere; }
  .sims { display: grid; gap: 0.5rem; margin: 0 0 0.8rem; }
  .sim { padding: 0.5rem; border: 1px solid var(--border); border-radius: var(--r-sm); display: grid; gap: 0.25rem; }
  .sim-head { display: flex; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap; }
  .close { width: 100%; margin-top: 0.4rem; }
  .grade-box { flex-shrink: 0; }
  .grade-input { width: 110px; text-align: center; font-weight: 600; min-height: 40px; }
</style>
