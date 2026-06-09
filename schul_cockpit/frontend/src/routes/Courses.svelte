<script>
  import { api } from '../lib/api.js';

  let { accountId } = $props();

  let courses = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let busy = $state(false);

  async function load() {
    if (!accountId) return;
    loading = true;
    error = null;
    try {
      courses = (await api.get(`/api/accounts/${accountId}/courses`)).courses;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void accountId; load(); });

  // Group by subject for display + "whole subject" toggle.
  const groups = $derived.by(() => {
    const m = new Map();
    for (const c of courses) {
      const k = c.subject_untis_id ?? c.subject_name;
      if (!m.has(k)) m.set(k, { subject_name: c.subject_name, subject_untis_id: c.subject_untis_id, items: [] });
      m.get(k).items.push(c);
    }
    return [...m.values()].sort((a, b) => (a.subject_name || '').localeCompare(b.subject_name || ''));
  });

  async function toggleCourse(c) {
    busy = true;
    try {
      await api.post(`/api/accounts/${accountId}/courses/hidden`, {
        course_key: c.course_key,
        subject_untis_id: c.subject_untis_id,
        subject_name: c.subject_name,
        teacher_untis_id: c.teacher_untis_id,
        teacher_name: c.teacher_name,
        hidden: !c.hidden,
      });
      c.hidden = !c.hidden;
      courses = [...courses];
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  async function toggleSubject(g, hidden) {
    busy = true;
    try {
      await api.post(`/api/accounts/${accountId}/courses/hide-subject`, {
        subject_untis_id: g.subject_untis_id,
        subject_name: g.subject_name,
        hidden,
      });
      await load();
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  function allHidden(g) { return g.items.every((c) => c.hidden); }
</script>

<div class="row between" style="margin-bottom:0.6rem;">
  <h2 style="margin:0; font-size:1.1rem;">Kurse / Wahlfächer</h2>
  <button class="ghost" onclick={() => history.back()}>← zurück</button>
</div>

<div class="banner">
  Schalte Kurse aus, die nicht belegt werden (z.B. nicht gewählte Wahlfächer).
  Ausgeblendete Kurse verschwinden aus Heute, Woche, Fächern, Vorschlägen und
  der Klausur-Erkennung.
</div>

{#if error}<div class="error-box">{error}</div>{/if}

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else if courses.length === 0}
  <div class="empty">Keine Kurse gefunden.</div>
{:else}
  {#each groups as g}
    <div class="card">
      <div class="row between" style="margin-bottom:0.3rem;">
        <strong>{g.subject_name}</strong>
        {#if g.items.length > 1}
          <button
            class="ghost"
            style="font-size:0.8rem; min-height:32px;"
            disabled={busy}
            onclick={() => toggleSubject(g, !allHidden(g))}
          >{allHidden(g) ? 'ganzes Fach einblenden' : 'ganzes Fach ausblenden'}</button>
        {/if}
      </div>
      {#each g.items as c (c.course_key)}
        <div class="course-row" class:off={c.hidden}>
          <div style="flex:1; min-width:0;">
            <span>{c.teacher_name || 'ohne Lehrer'}</span>
            <span class="dim"> · {c.count}×</span>
          </div>
          <button
            class:primary={!c.hidden}
            class="toggle"
            disabled={busy}
            onclick={() => toggleCourse(c)}
          >{c.hidden ? 'nicht belegt' : 'belegt'}</button>
        </div>
      {/each}
    </div>
  {/each}
{/if}

<style>
  .course-row {
    display: flex; align-items: center; gap: 0.6rem;
    padding: 0.45rem 0; border-top: 1px solid var(--border);
  }
  .course-row:first-of-type { border-top: none; }
  .course-row.off { opacity: 0.5; }
  .toggle { font-size: 0.8rem; min-height: 34px; min-width: 96px; }
</style>
