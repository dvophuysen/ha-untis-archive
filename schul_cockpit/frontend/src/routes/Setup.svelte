<script>
  import { api } from '../lib/api.js';
  import { loadMe } from '../lib/store.svelte.js';
  import { APP_VERSION } from '../lib/version.js';

  let { navigate } = $props();

  let users = $state([]);
  let accounts = $state([]);
  let todoEntities = $state([]);
  let todoLists = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let savingFor = $state(null);

  async function load() {
    loading = true;
    try {
      const [u, a, e, t] = await Promise.all([
        api.get('/api/users'),
        api.get('/api/accounts'),
        api.get('/api/todo-entities').catch(() => ({ available: false, entities: [] })),
        api.get('/api/todo-lists'),
      ]);
      users = u.users;
      accounts = a.accounts;
      todoEntities = e.entities ?? [];
      todoLists = t.todo_lists;
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => { load(); });

  async function patchUser(u, patch) {
    savingFor = u.id;
    try {
      await api.patch(`/api/users/${u.id}`, patch);
      await load();
      await loadMe();
    } catch (e) {
      error = e.message;
    } finally {
      savingFor = null;
    }
  }

  function toggleAccount(u, accountId) {
    const ids = new Set(u.account_ids);
    if (ids.has(accountId)) ids.delete(accountId); else ids.add(accountId);
    return patchUser(u, { account_ids: [...ids] });
  }

  async function setTodoList(accountId, entityId) {
    if (!entityId) return;
    await api.put('/api/todo-lists', { account_id: accountId, ha_entity_id: entityId });
    await load();
  }

  async function setPin(u) {
    const pin = prompt(`PIN für ${u.display_name} festlegen (4–8 Ziffern):`);
    if (pin == null) return;
    if (!/^\d{4,8}$/.test(pin)) { alert('PIN muss 4–8 Ziffern haben.'); return; }
    savingFor = u.id;
    try {
      await api.put(`/api/users/${u.id}/pin`, { pin });
      await load();
    } catch (e) {
      error = e.message;
    } finally {
      savingFor = null;
    }
  }

  async function clearPin(u) {
    if (!confirm(`PIN für ${u.display_name} entfernen? Damit ist kein direkter App-Login mehr möglich.`)) return;
    savingFor = u.id;
    try {
      await api.delete(`/api/users/${u.id}/pin`);
      await load();
    } catch (e) {
      error = e.message;
    } finally {
      savingFor = null;
    }
  }

  function todoListFor(accountId) {
    return todoLists.find((t) => t.account_id === accountId);
  }
</script>

<div class="row between" style="margin-bottom:0.6rem;">
  <h2 style="margin:0; font-size:1.1rem;">Setup</h2>
  <button class="ghost" onclick={() => navigate('today')}>← zurück</button>
</div>

<div class="dim" style="text-align:center; margin-bottom:0.6rem;">
  App-Version <strong>{APP_VERSION}</strong>
</div>

{#if error}<div class="error-box">{error}</div>{/if}

{#if loading}
  <div class="empty"><span class="spinner"></span></div>
{:else}
  <div class="section-title">Kinder zuordnen</div>
  <div class="banner">
    Jeder HA-Nutzer kann mit einem oder mehreren UNTIS-Kindern verknüpft werden. Eltern haben in der Regel alle Kinder, ein Kind nur sich selbst.
  </div>

  {#each users as u}
    <div class="card">
      <div class="row between" style="margin-bottom:0.5rem;">
        <div>
          <strong>{u.display_name || u.ha_user_id}</strong>
          {#if u.is_admin}<span class="badge">Admin</span>{/if}
        </div>
        <select
          value={u.role}
          onchange={(e) => patchUser(u, { role: e.currentTarget.value })}
          disabled={savingFor === u.id}
          style="max-width:140px;"
        >
          <option value="pending">– Rolle wählen –</option>
          <option value="parent">Eltern</option>
          <option value="child">Kind</option>
          <option value="admin">Admin</option>
        </select>
      </div>
      <div class="dim" style="margin-bottom:0.3rem;">Verknüpfte Kinder:</div>
      <div class="row gap-sm" style="flex-wrap:wrap;">
        {#each accounts as a}
          <button
            class:primary={u.account_ids.includes(a.id)}
            onclick={() => toggleAccount(u, a.id)}
            disabled={savingFor === u.id}
            style="font-size:0.85rem; padding:0.3rem 0.6rem; min-height:36px;"
          >{a.name}</button>
        {/each}
      </div>

      <div class="row between" style="margin-top:0.6rem; padding-top:0.5rem; border-top:1px solid var(--border);">
        <div class="dim">
          App-Login (PIN): {u.has_pin ? '✓ gesetzt' : 'kein PIN'}
        </div>
        <div class="row gap-sm">
          <button onclick={() => setPin(u)} disabled={savingFor === u.id} style="font-size:0.85rem; min-height:36px;">
            {u.has_pin ? 'PIN ändern' : 'PIN setzen'}
          </button>
          {#if u.has_pin}
            <button class="ghost" onclick={() => clearPin(u)} disabled={savingFor === u.id} style="font-size:0.85rem; min-height:36px;">✕</button>
          {/if}
        </div>
      </div>
    </div>
  {/each}

  <div class="banner">
    💡 Der PIN ermöglicht die <strong>Installation als App</strong> auf dem Home-Bildschirm:
    Die Kinder öffnen die Direkt-Adresse <code>http://&lt;HA-IP&gt;:8099/</code> (oder deine feste
    URL mit Port 8099), melden sich mit ihrem PIN an, und können „Zum Home-Bildschirm" nutzen —
    Vollbild, eigenes Icon, offline-fähig.
  </div>

  <div class="section-title">HA-ToDo-Liste pro Kind</div>
  <div class="banner">
    Wähle pro Kind die HA-ToDo-Liste, in die deine Untis-Automation Hausaufgaben schreibt. Die App syncht alle 2 Min bidirektional.
  </div>

  {#each accounts as a}
    {@const current = todoListFor(a.id)}
    <div class="card">
      <strong>{a.name}</strong>
      <div style="margin-top:0.4rem;">
        <select
          value={current?.ha_entity_id ?? ''}
          onchange={(e) => setTodoList(a.id, e.currentTarget.value)}
        >
          <option value="">– keine –</option>
          {#each todoEntities as e}
            <option value={e.entity_id}>{e.friendly_name || e.entity_id}</option>
          {/each}
        </select>
        {#if todoEntities.length === 0}
          <div class="dim" style="margin-top:0.3rem;">
            Keine ToDo-Listen in HA gefunden — entweder existiert noch keine oder das Add-on hat keinen Supervisor-Zugriff.
          </div>
        {/if}
      </div>
    </div>
  {/each}
{/if}
