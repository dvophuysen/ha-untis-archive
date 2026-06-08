<script>
  import { api } from '../lib/api.js';

  let { accountId } = $props();

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
{/if}
