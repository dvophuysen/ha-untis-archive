<script>
  // Eigene Aufgaben anlegen und ändern: Titel, Fälligkeit, Notiz. Mehr
  // braucht es nicht; Untis-Aufgaben kommen fertig und werden hier nicht
  // verändert.
  import { api } from './api.js';

  let { accountId, task = null, onclose, onsaved } = $props();

  // Der Entwurf beginnt mit dem Stand beim Öffnen; der Dialog wird je Aufgabe neu erzeugt.
  // svelte-ignore state_referenced_locally
  let title = $state(task?.title ?? '');
  // svelte-ignore state_referenced_locally
  let dueDate = $state(task?.due_date ?? '');
  // svelte-ignore state_referenced_locally
  let notes = $state(task?.notes ?? '');
  let busy = $state(false);
  let error = $state(null);

  const isExisting = $derived(!!task?.id);
  const isHaTask = $derived(task?.source === 'ha_todo');

  async function save() {
    if (!title.trim()) return;
    busy = true;
    error = null;
    try {
      const body = { title, task_type: task?.task_type ?? 'homework', due_date: dueDate || null, notes: notes || null };
      if (isExisting) {
        await api.patch(`/api/tasks/${task.id}`, body);
      } else {
        await api.post(`/api/accounts/${accountId}/tasks`, body);
      }
      onsaved?.();
      onclose?.();
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  async function deleteIt() {
    if (!isExisting) return onclose?.();
    if (!confirm('Aufgabe löschen?')) return;
    busy = true;
    try {
      await api.delete(`/api/tasks/${task.id}`);
      onsaved?.();
      onclose?.();
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }
</script>

<div class="modal-backdrop" onclick={onclose} role="presentation">
  <div class="modal" onclick={(e) => e.stopPropagation()} onkeydown={(e) => { if (e.key === 'Escape') onclose(); }} role="dialog" aria-modal="true" aria-label="Aufgabe bearbeiten" tabindex="-1">
    <div class="row between" style="margin-bottom:0.6rem;">
      <h2 style="margin:0; font-size:1.1rem;">{isExisting ? 'Aufgabe bearbeiten' : 'Neue Aufgabe'}</h2>
      <button class="ghost" onclick={onclose} aria-label="Schließen">✕</button>
    </div>

    {#if error}<div class="error-box">{error}</div>{/if}
    {#if isHaTask}
      <div class="banner">Diese Aufgabe stammt aus Untis. Titel und Fälligkeit setzt der nächste Abgleich wieder zurück.</div>
    {/if}

    <div class="form-grid">
      <div>
        <label for="taskeditor-68">Aufgabe</label>
        <input id="taskeditor-68" bind:value={title} placeholder="z.B. Mathe S. 42 Nr. 1-5" disabled={isHaTask} />
      </div>
      <div>
        <label for="taskeditor-72">Fällig am</label>
        <input id="taskeditor-72" type="date" bind:value={dueDate} disabled={isHaTask} />
      </div>
      <div>
        <label for="taskeditor-76">Notiz</label>
        <textarea id="taskeditor-76" bind:value={notes} rows="3"></textarea>
      </div>
      <div class="row gap-sm" style="margin-top:0.4rem;">
        <button class="primary" disabled={busy || !title.trim()} onclick={save} style="flex:1;">{isExisting ? 'Speichern' : 'Anlegen'}</button>
        {#if isExisting && !isHaTask}
          <button class="danger" disabled={busy} onclick={deleteIt}>Löschen</button>
        {/if}
      </div>
    </div>
  </div>
</div>
