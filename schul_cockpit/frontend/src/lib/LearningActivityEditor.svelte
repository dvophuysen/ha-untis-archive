<script>
  let { value = null, materials = [], onsave, oncancel, busy = false } = $props();
  function initialForm() { return value ? {
    kind: value.kind, afb: value.afb, operator: value.operator, prompt: value.prompt,
    explanation: value.explanation, hint: value.hint, solution: value.solution,
    criteria: value.criteria, minutes: value.minutes, published: !!value.published,
    source_ids: typeof value.source_ids === 'string' ? JSON.parse(value.source_ids) : (value.source_ids || []),
  } : { kind: 'practice', afb: 2, operator: 'Erkläre', prompt: '', explanation: '', hint: '',
        solution: '', criteria: '', minutes: 5, published: false, source_ids: [] }; }
  let form = $state(initialForm());
</script>
<form class="editor" onsubmit={(e) => { e.preventDefault(); onsave(form); }}>
  <h3>{value ? 'Übung prüfen und bearbeiten' : 'Eigene Übung'}</h3>
  <div class="columns">
    <label>Art<select bind:value={form.kind}><option value="preview">Vorbereitung</option><option value="practice">Üben</option><option value="transfer">Übertragen</option><option value="oral">Mündlich</option></select></label>
    <label>Anforderung<select bind:value={form.afb}><option value={1}>I · Wiedergeben</option><option value={2}>II · Verknüpfen und anwenden</option><option value={3}>III · Reflektieren und lösen</option></select></label>
  </div>
  <p class="muted">Die ganze Aufgabe bestimmt die Anforderung; der Operator allein genügt nicht.</p>
  <label>Operator<input bind:value={form.operator} required maxlength="100" /></label>
  <label>Arbeitsauftrag<textarea bind:value={form.prompt} required maxlength="6000"></textarea></label>
  <label>Erklärung mit Beispiel (auf Wunsch sichtbar)<textarea bind:value={form.explanation} maxlength="6000"></textarea></label>
  <label>Kleiner Hinweis<textarea bind:value={form.hint} maxlength="2000"></textarea></label>
  <label>Lösung oder mögliche Antwort<textarea bind:value={form.solution} required maxlength="6000"></textarea></label>
  <label>Woran erkennt das Kind eine gute Antwort?<textarea bind:value={form.criteria} required maxlength="4000"></textarea></label>
  <label>Geschätzte Minuten<input type="number" bind:value={form.minutes} min="1" max="30" required /></label>
  {#if materials.length}
    <fieldset><legend>Verwendete Quellen</legend>{#each materials as m}<label class="check"><input type="checkbox" bind:group={form.source_ids} value={m.id} />{m.title}</label>{/each}</fieldset>
  {/if}
  <label class="check"><input type="checkbox" bind:checked={form.published} />Geprüft und für das Kind freigeben</label>
  <div class="actions"><button class="primary" disabled={busy}>Speichern</button><button type="button" onclick={oncancel} disabled={busy}>Abbrechen</button></div>
</form>
<style>
  .editor { padding: 1rem; border: 1px solid var(--border); border-radius: 12px; background: var(--bg-card); }
  label { font-size: .9rem; margin-bottom: .8rem; } input,select,textarea { margin-top: .25rem; }
  .columns { display:grid; grid-template-columns:1fr 1fr; gap:.75rem; }
  .check { display:flex; align-items:center; gap:.5rem; } .check input { width:20px; min-height:20px; }
  .actions { display:flex; flex-wrap:wrap; gap:.5rem; } .muted {color:var(--fg-muted);font-size:.9rem;}
  fieldset {border:1px solid var(--border);border-radius:8px;margin-bottom:1rem;}
  @media(max-width:480px){.columns{grid-template-columns:1fr;}}
</style>
