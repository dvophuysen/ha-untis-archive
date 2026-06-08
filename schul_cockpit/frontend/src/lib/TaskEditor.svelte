<script>
  import { api } from './api.js';

  let { accountId, task = null, onclose, onsaved } = $props();

  const TYPES = [
    { v: 'homework', label: 'Hausaufgabe' },
    { v: 'exam_prep', label: 'Klausur-Vorbereitung' },
    { v: 'practice', label: 'Üben / Festigen' },
    { v: 'catch_up', label: 'Stoff nachholen' },
    { v: 'project', label: 'Projekt' },
  ];
  const MINUTES = [5, 15, 30, 45, 60, 90, 120, 180];

  let title = $state(task?.title ?? '');
  let taskType = $state(task?.task_type ?? 'homework');
  let minutes = $state(task?.estimated_minutes ?? null);
  let dueDate = $state(task?.due_date ?? '');
  let notes = $state(task?.notes ?? '');
  let subitems = $state(task?.subitems ?? []);
  let newSub = $state('');
  let busy = $state(false);
  let error = $state(null);

  const isExisting = $derived(!!task?.id);
  const isHaTask = $derived(task?.source === 'ha_todo');

  async function save() {
    if (!title.trim()) return;
    busy = true;
    error = null;
    try {
      const body = {
        title,
        task_type: taskType,
        estimated_minutes: minutes,
        due_date: dueDate || null,
        notes: notes || null,
      };
      if (isExisting) {
        await api.patch(`/api/tasks/${task.id}`, body);
      } else {
        const created = await api.post(`/api/accounts/${accountId}/tasks`, body);
        for (const s of subitems.filter((x) => !x.id)) {
          await api.post(`/api/tasks/${created.id}/subitems`, { title: s.title });
        }
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

  async function addSubitem() {
    if (!newSub.trim()) return;
    if (isExisting) {
      const s = await api.post(`/api/tasks/${task.id}/subitems`, { title: newSub });
      subitems = [...subitems, s];
    } else {
      subitems = [...subitems, { title: newSub, done: false }];
    }
    newSub = '';
  }

  async function toggleSub(s) {
    if (s.id) {
      await api.patch(`/api/subitems/${s.id}`, { done: !s.done });
    }
    s.done = !s.done;
    subitems = [...subitems];
  }
</script>

<div class="modal-backdrop" onclick={onclose} role="presentation">
  <div class="modal" onclick={(e) => e.stopPropagation()} role="dialog">
    <div class="row between" style="margin-bottom:0.6rem;">
      <h2 style="margin:0; font-size:1.1rem;">{isExisting ? 'Aufgabe' : 'Neue Aufgabe'}</h2>
      <button class="ghost" onclick={onclose}>✕</button>
    </div>

    {#if error}<div class="error-box">{error}</div>{/if}

    {#if isHaTask}
      <div class="banner">Diese Aufgabe stammt aus der HA-ToDo-Liste. Titel und Fälligkeit werden beim nächsten Sync ggf. überschrieben.</div>
    {/if}

    <div class="form-grid">
      <div>
        <label>Titel {#if isHaTask}<span class="dim">(aus Untis)</span>{/if}</label>
        <input bind:value={title} placeholder="z.B. Mathe S. 42 Nr. 1-5" disabled={isHaTask} />
      </div>

      <div>
        <label>Typ</label>
        <select bind:value={taskType}>
          {#each TYPES as t}<option value={t.v}>{t.label}</option>{/each}
        </select>
      </div>

      <div>
        <label>Aufwand (Min)</label>
        <div class="effort-picker">
          {#each MINUTES as m}
            <button type="button" class:active={minutes === m} onclick={() => (minutes = minutes === m ? null : m)}>{m}</button>
          {/each}
        </div>
      </div>

      <div>
        <label>Fällig am {#if isHaTask}<span class="dim">(aus Untis — nicht änderbar)</span>{/if}</label>
        <input type="date" bind:value={dueDate} disabled={isHaTask} />
      </div>

      <div>
        <label>Sub-Aufgaben</label>
        <div class="col" style="gap:0.2rem;">
          {#each subitems as s, i (s.id ?? i)}
            <div class="subitem-row">
              <button class="task-checkbox" class:done={s.done} onclick={() => toggleSub(s)}>{s.done ? '✓' : ''}</button>
              <span class="task-title" class:done={s.done} style="flex:1;">{s.title}</span>
            </div>
          {/each}
          <div class="row gap-sm" style="margin-top:0.3rem;">
            <input bind:value={newSub} placeholder="+ Sub-Aufgabe…" onkeydown={(e) => e.key === 'Enter' && (addSubitem(), e.preventDefault())} />
            <button onclick={addSubitem}>+</button>
          </div>
        </div>
      </div>

      <div>
        <label>Notizen</label>
        <textarea bind:value={notes} rows="3"></textarea>
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
