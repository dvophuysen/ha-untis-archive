<script>
  import { api } from '../lib/api.js';
  import { appState, loadMe } from '../lib/store.svelte.js';

  let { accountId } = $props();
  let togglingDemo = $state(false);

  async function toggleDemo() {
    togglingDemo = true;
    try {
      await api.patch('/api/me/demo-mode', { enabled: !appState.me.demo_mode });
      await loadMe();
    } finally {
      togglingDemo = false;
    }
  }

  const DAYS = [
    { key: 'mon', label: 'Mo' },
    { key: 'tue', label: 'Di' },
    { key: 'wed', label: 'Mi' },
    { key: 'thu', label: 'Do' },
    { key: 'fri', label: 'Fr' },
    { key: 'sat', label: 'Sa' },
    { key: 'sun', label: 'So' },
  ];

  let settings = $state(null);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state(null);

  async function load() {
    loading = true;
    try {
      settings = await api.get(`/api/accounts/${accountId}/settings`);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { void accountId; load(); });

  async function save() {
    saving = true;
    try {
      await api.patch(`/api/accounts/${accountId}/settings`, {
        default_daily_budget_minutes: Number(settings.default_daily_budget_minutes),
        budget_overrides: Object.fromEntries(
          Object.entries(settings.budget_overrides).filter(([_, v]) => v !== '' && v !== null),
        ),
      });
    } catch (e) {
      error = e.message;
    } finally {
      saving = false;
    }
  }
</script>

<div class="row between" style="margin-bottom:0.6rem;">
  <h2 style="margin:0; font-size:1.1rem;">Einstellungen</h2>
  <button class="ghost" onclick={() => history.back()}>← zurück</button>
</div>

{#if error}<div class="error-box">{error}</div>{/if}

{#if loading || !settings}
  <div class="empty"><span class="spinner"></span></div>
{:else}
  <div class="section-title">Tagesbudget Lernzeit</div>
  <div class="banner">
    Wie viele Minuten pro Tag stehen üblicherweise zum Lernen zur Verfügung? Der Nachmittagsplaner nutzt diesen Wert für seine Vorschläge.
  </div>

  <div class="card">
    <label>Standard (alle Wochentage)</label>
    <input type="number" min="0" step="15" bind:value={settings.default_daily_budget_minutes} />

    <div class="section-title">Abweichungen pro Wochentag</div>
    {#each DAYS as d}
      <div class="row gap-sm" style="margin-bottom:0.3rem;">
        <span style="width:34px;">{d.label}</span>
        <input
          type="number"
          min="0"
          step="15"
          placeholder={`= ${settings.default_daily_budget_minutes}`}
          value={settings.budget_overrides[d.key] ?? ''}
          oninput={(e) => {
            const v = e.currentTarget.value;
            if (v === '') delete settings.budget_overrides[d.key];
            else settings.budget_overrides[d.key] = Number(v);
            settings.budget_overrides = { ...settings.budget_overrides };
          }}
        />
      </div>
    {/each}

    <button class="primary" disabled={saving} onclick={save} style="margin-top:0.6rem; width:100%;">
      {saving ? 'Speichere…' : 'Speichern'}
    </button>
  </div>

  {#if appState.me?.is_admin}
  <div class="section-title">Demo-Modus</div>
  <div class="banner">
    Im Demo-Modus werden alle deine Änderungen geloggt und können einzeln oder gesammelt zurückgenommen werden.
    Außerdem wird der HA-ToDo-Sync für deine Änderungen pausiert — du kannst also gefahrlos ausprobieren, ohne
    in der HA-ToDo-Liste der Kinder etwas zu verändern.
  </div>
  <div class="card">
    <div class="row between">
      <div>
        <strong>Demo-Modus</strong>
        <div class="dim">{appState.me?.demo_mode ? 'Aktiv — Änderungen werden geloggt, HA-Sync pausiert.' : 'Aus'}</div>
      </div>
      <button
        class:primary={appState.me?.demo_mode}
        onclick={toggleDemo}
        disabled={togglingDemo}
      >{appState.me?.demo_mode ? '✓ AN' : 'AUS'}</button>
    </div>
    <button
      style="width:100%; margin-top:0.5rem;"
      onclick={() => (window.location.hash = '#/changes')}
    >Meine Änderungen ansehen ({appState.me?.open_audit_count ?? 0})</button>
  </div>
  {/if}
{/if}
