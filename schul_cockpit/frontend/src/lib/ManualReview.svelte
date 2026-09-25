<script>
  // Elternprüfung (D207): Eltern bewerten jede Aufgabe selbst oder übernehmen
  // einen KI-Vorschlag und passen ihn an. Gespeichert wird die vollständige
  // Rückmeldung, die das Kind danach sieht: Punkte, was richtig war, jeder
  // Abzug mit Grund und richtiger Lösung, volle Lösung, nächster Schritt.
  import { api } from './api.js';

  let { tasks, feedback = {}, base, onsaved = () => {}, oncancel = () => {} } = $props();
  const KINDS = [
    ['nicht_bearbeitet', 'Nicht bearbeitet'], ['unvollstaendig', 'Unvollständig'], ['rechenweg', 'Rechenweg oder Begründung fehlt'],
    ['rechenfehler', 'Rechen- oder Flüchtigkeitsfehler'], ['ansatz', 'Falscher Ansatz'], ['regel', 'Regel, Formel oder Fachbegriff'],
    ['aufgabe', 'Aufgabe nicht genau gelesen'], ['form', 'Darstellung'], ['sprache', 'Rechtschreibung oder Grammatik'], ['wortschatz', 'Wort nicht gewusst'],
  ];
  const num = (x) => Number(x).toLocaleString('de-DE');
  const toNum = (v) => Number(String(v ?? '').replace(',', '.'));

  const fromFeedback = (fb) => tasks.map((t, i) => {
    const f = fb?.[String(i)] || {};
    return {
      points: f.points ?? '', rationale: f.rationale || '', next_step: f.next_step || '', transcription: f.transcription || '', model: f.model || '',
      earned: (f.earned || []).map((x) => ({ ...x })), lost: (f.lost || []).map((x) => ({ ...x })),
    };
  });
  const overallFrom = (o) => ({ text: o?.text || '', strengths: (o?.strengths || []).join('\n'), focus: (o?.focus || []).join('\n') });
  let form = $state(fromFeedback(feedback));
  let overall = $state(overallFrom(feedback?.overall));
  let hint = $state(''), busy = $state(''), error = $state(''), suggested = $state(false);

  const lines = (s) => s.split('\n').map((x) => x.trim()).filter(Boolean).slice(0, 3);
  const sums = $derived(form.map((x, i) => {
    const p = toNum(x.points);
    const lost = x.lost.reduce((s, l) => s + (toNum(l.points) || 0), 0);
    return { ok: Number.isFinite(p) && x.points !== '' && p >= 0 && p <= tasks[i].points && p * 2 === Math.round(p * 2), gap: tasks[i].points - p - lost };
  }));
  const problems = $derived(form.flatMap((x, i) => {
    const out = [];
    if (!sums[i].ok) out.push(`Aufgabe ${i + 1}: Punkte zwischen 0 und ${tasks[i].points}, halbe Punkte erlaubt.`);
    if (x.rationale.trim().length < 3) out.push(`Aufgabe ${i + 1}: Begründung fehlt.`);
    if (x.next_step.trim().length < 3) out.push(`Aufgabe ${i + 1}: nächster Schritt fehlt.`);
    if (x.lost.some((l) => l.why.trim().length < 2 || l.fix.trim().length < 2)) out.push(`Aufgabe ${i + 1}: Bei jedem Abzug Grund und richtige Lösung eintragen.`);
    return out;
  }));

  async function suggest() {
    if (busy) return;
    if (suggested && !confirm('Den neuen Vorschlag übernehmen? Eure Änderungen im Formular werden ersetzt.')) return;
    busy = 'Die App liest die Seiten noch einmal genau, das dauert bis zu zwei Minuten …'; error = '';
    try {
      const s = await api.post(`${base}/manual/suggest`, { hint });
      form = fromFeedback(s.tasks);
      overall = overallFrom(s.overall);
      suggested = true;
    } catch (e) { error = e.message; } finally { busy = ''; }
  }

  async function save() {
    if (busy || problems.length) return;
    busy = 'Wird gespeichert …'; error = '';
    try {
      const body = {
        tasks: Object.fromEntries(form.map((x, i) => [String(i), {
          points: toNum(x.points), rationale: x.rationale.trim(), next_step: x.next_step.trim(), transcription: x.transcription.trim(), model: x.model.trim(),
          earned: x.earned.filter((e) => e.text.trim() && toNum(e.points) > 0).map((e) => ({ text: e.text.trim(), points: toNum(e.points) })),
          lost: x.lost.filter((l) => toNum(l.points) > 0).map((l) => ({ points: toNum(l.points), kind: l.kind, why: l.why.trim(), fix: l.fix.trim() })),
        }])),
        overall: { text: overall.text.trim(), strengths: lines(overall.strengths), focus: lines(overall.focus) },
      };
      onsaved(await api.post(`${base}/manual`, body));
    } catch (e) { error = e.message; } finally { busy = ''; }
  }
</script>

<section class="manual">
  <div class="notice">
    <strong>Selbst prüfen</strong>
    <p>Ihr bewertet jede Aufgabe. Das Kind sieht danach genau diese Rückmeldung: was Punkte gebracht hat, wo es Punkte verloren hat, was dort hätte stehen müssen, und was es als Nächstes übt.</p>
  </div>
  <div class="assist">
    <label>Hinweis für die KI (freiwillig)
      <textarea rows="2" bind:value={hint} placeholder="Zum Beispiel: Die Rechnung zu Aufgabe 1 steht unter Aufgabe 2. Aufgabe 3 bitte streng bewerten."></textarea></label>
    <button class="btn" disabled={!!busy} onclick={suggest}>{suggested ? 'Neuen KI-Vorschlag holen' : 'KI-Vorschlag holen'}</button>
    {#if suggested}<p class="dim">Vorschlag eingetragen. Bitte prüfen und bei Bedarf ändern.</p>{/if}
  </div>

  {#each form as x, i (i)}
    {@const t = tasks[i]}
    <article class="task">
      <div class="t-head"><strong>Aufgabe {i + 1}</strong><span class="dim">höchstens {t.points} Punkte</span></div>
      <details><summary>Aufgabe, Lösung und Kriterien</summary><p class="preserve">{t.prompt}</p><p class="preserve">{t.solution}</p><p class="preserve dim">{t.criteria}</p></details>
      {#if x.transcription}<p class="dim"><strong>Gelesen:</strong> {x.transcription}</p>{/if}
      <label class="pts-in">Punkte
        <input type="number" inputmode="decimal" min="0" max={t.points} step="0.5" bind:value={x.points} aria-label={`Punkte Aufgabe ${i + 1}`} /></label>
      <label>Begründung
        <textarea rows="2" bind:value={x.rationale} aria-label={`Begründung Aufgabe ${i + 1}`}></textarea></label>

      <fieldset>
        <legend>Das war richtig</legend>
        {#each x.earned as e, k (k)}
          <div class="row"><input class="p" type="number" inputmode="decimal" min="0" step="0.5" bind:value={e.points} aria-label="Punkte" />
            <input type="text" bind:value={e.text} placeholder="Was Punkte gebracht hat" aria-label="Was Punkte gebracht hat" />
            <button class="ghost" onclick={() => x.earned.splice(k, 1)} aria-label="Entfernen">✕</button></div>
        {/each}
        <button class="ghost add" onclick={() => x.earned.push({ text: '', points: 1 })}>+ Richtiges ergänzen</button>
      </fieldset>

      <fieldset>
        <legend>Punkte verloren</legend>
        {#each x.lost as l, k (k)}
          <div class="loss">
            <div class="row"><input class="p" type="number" inputmode="decimal" min="0" step="0.5" bind:value={l.points} aria-label="Abzug in Punkten" />
              <select bind:value={l.kind} aria-label="Grund">{#each KINDS as [key, label] (key)}<option value={key}>{label}</option>{/each}</select>
              <button class="ghost" onclick={() => x.lost.splice(k, 1)} aria-label="Entfernen">✕</button></div>
            <textarea rows="2" bind:value={l.why} placeholder="Was fehlte oder falsch war" aria-label="Was fehlte oder falsch war"></textarea>
            <textarea rows="2" bind:value={l.fix} placeholder="So hätte es die Punkte gegeben" aria-label="So hätte es die Punkte gegeben"></textarea>
          </div>
        {/each}
        <button class="ghost add" onclick={() => x.lost.push({ points: 1, kind: 'unvollstaendig', why: '', fix: '' })}>+ Abzug ergänzen</button>
        {#if sums[i].ok && sums[i].gap !== 0}<p class="warn">Punkte und Abzüge ergeben {num(t.points - sums[i].gap)} von {t.points}. Beim Speichern gleicht der größte Abzug aus.</p>{/if}
      </fieldset>

      <label>So wäre es voll gewesen
        <textarea rows="3" bind:value={x.model} aria-label={`Volle Lösung Aufgabe ${i + 1}`}></textarea></label>
      <label>Nächster Schritt
        <textarea rows="2" bind:value={x.next_step} aria-label={`Nächster Schritt Aufgabe ${i + 1}`}></textarea></label>
    </article>
  {/each}

  <article class="task">
    <strong>Gesamt</strong>
    <label>Gesamtsatz <textarea rows="2" bind:value={overall.text}></textarea></label>
    <label>Das kann das Kind schon (eine Zeile je Punkt, höchstens drei) <textarea rows="3" bind:value={overall.strengths}></textarea></label>
    <label>Das übt es als Nächstes (eine Zeile je Schritt, höchstens drei) <textarea rows="3" bind:value={overall.focus}></textarea></label>
  </article>

  {#if problems.length}<ul class="problems">{#each problems as p (p)}<li>{p}</li>{/each}</ul>{/if}
  {#if busy}<p role="status">{busy}</p>{/if}
  {#if error}<p class="error-box" role="alert">{error}</p>{/if}
  <div class="acts">
    <button class="primary" disabled={!!busy || problems.length > 0} onclick={save}>Prüfung speichern</button>
    <button class="ghost" disabled={!!busy} onclick={oncancel}>Abbrechen</button>
  </div>
</section>

<style>
  .manual { display: grid; gap: var(--sp-2); }
  .manual p { margin: 0; }
  .assist, .task, fieldset { display: grid; gap: 6px; }
  fieldset { border: 1px solid var(--border); border-radius: var(--r-sm); padding: 6px 8px; margin: 0; min-width: 0; }
  label { display: grid; gap: 2px; }
  textarea, input, select { font: inherit; width: 100%; box-sizing: border-box; min-width: 0; }
  .pts-in { max-width: 10rem; }
  .row { display: grid; grid-template-columns: 4.2em 1fr auto; gap: 4px; align-items: center; }
  .loss { display: grid; gap: 4px; padding-bottom: 6px; border-bottom: 1px dashed var(--border); }
  .add { justify-self: start; }
  .warn { color: var(--warn, #b26a00); font-size: .9em; }
  .problems { margin: 0; padding-left: 1.2em; color: var(--warn, #b26a00); }
  .acts { display: flex; flex-wrap: wrap; gap: var(--sp-2); }
</style>
