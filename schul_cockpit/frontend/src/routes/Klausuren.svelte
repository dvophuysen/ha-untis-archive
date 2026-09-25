<script>
  // Arbeiten & Tests: je Arbeit drei Punkte (Stoff, Material, Üben) und darunter
  // die Themen der offiziellen Themenliste mit ihrer Stufe. Grün liegt vor oder
  // sitzt, gelb angenommen oder wackelt, rot fehlt, grau noch nichts.
  import { api } from '../lib/api.js';
  import { formatShortDate, daysBetween, isoToday } from '../lib/format.js';
  import { appState } from '../lib/store.svelte.js';
  import { subjectStyle } from '../lib/subjectStyle.js';

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

  const canManage = $derived(!!(appState.me && (appState.me.is_admin || appState.me.role === 'parent')));

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
    return (e.topics || []).filter((t) => !t.stale);
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
      action: { label: 'ablegen', href: materialUrl(e), title: 'Zettel oder Tafelfoto der Lehrkraft fotografieren' },
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
            <span class="dim">{longDay(e.date)}{#if far} · {whenLabel(e.date)}{/if}{#if e.source === 'manual'} · selbst eingetragen{/if}</span>
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
            {#if e.sources?.notice}
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
              <a class="practice-link" href={practiceUrl(e)}>Übungsarbeit wie in echt</a>
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
  .stage.angefangen { background: var(--bg); }
  .stage.wackelt { background: var(--rating-2); color: #fff; border-color: transparent; }
  .stage.sitzt { background: var(--rating-3); color: #fff; border-color: transparent; }
  .stage.gefestigt { background: var(--accent); color: var(--accent-fg); border-color: transparent; }
  .missing { color: var(--bad-fg); font-weight: 600; }
  .add-topic { display: flex; gap: 0.4rem; margin-top: 0.6rem; }
  .add-topic input { flex: 1; min-width: 0; font-size: 16px; padding: 0.45rem 0.6rem; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-elevated); color: inherit; }
  .also { margin-top: 0.6rem; font-size: 0.88rem; }
  .also summary { min-height: 40px; display: flex; align-items: center; cursor: pointer; }
  .also-row { padding: 0.15rem 0; }
  .practice-link { font-weight: 600; }
  .legend { font-size: 0.78rem; margin: 0.6rem 0 0; }
  .close { width: 100%; margin-top: 0.4rem; }
  .grade-box { flex-shrink: 0; }
  .grade-input { width: 110px; text-align: center; font-weight: 600; min-height: 40px; }
</style>
