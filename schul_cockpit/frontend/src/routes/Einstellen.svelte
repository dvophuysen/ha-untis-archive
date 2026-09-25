<script>
  // Einstellen (D183): eine Seite, zwei Bereiche. „Je Kind“ mit Kind-Chips
  // oben, „Haushalt“ für alles, was die Familie gemeinsam betrifft. Die alten
  // Seiten (Einstellungen, Setup, Kurse, Arbeiten-Kalender, Änderungen) bleiben
  // als Unterseiten erreichbar; hier steht, was es gibt, und der Weg dorthin.
  import { api, ApiError } from '../lib/api.js';
  import { appState, loadMe } from '../lib/store.svelte.js';
  import ActionLabel from '../lib/ActionLabel.svelte';
  import KidChips from '../lib/KidChips.svelte';
  import ReminderSettings from '../lib/ReminderSettings.svelte';
  import ParentReportSettings from '../lib/ParentReportSettings.svelte';
  import AiSettings from '../lib/AiSettings.svelte';

  let { accountId } = $props();
  const me = $derived(appState.me);
  const kidName = $derived(me?.accounts?.find((a) => a.id === accountId)?.name ?? 'Kind');
  // Der KI-Rahmen gilt für die ganze Familie; die Schnittstelle hängt an einem Kind.
  const householdKid = $derived(me?.accounts?.[0]?.id ?? null);

  let bonus = $state(''), bonusMsg = $state(''), bonusBusy = $state(false);
  let request = 0;
  $effect(() => {
    const id = accountId, ticket = ++request;
    bonus = ''; bonusMsg = '';
    if (!id) return;
    api.get(`/api/accounts/${id}/rewards`).then((r) => { if (ticket === request) bonus = r.bonus_until; }).catch(() => {});
  });
  async function saveBonus() {
    bonusBusy = true; bonusMsg = '';
    try {
      const r = await api.put(`/api/accounts/${accountId}/rewards/settings`, { bonus_until: bonus });
      bonus = r.bonus_until; bonusMsg = 'Gespeichert.';
    } catch (e) { bonusMsg = e instanceof ApiError ? e.message : 'Nicht gespeichert.'; }
    finally { bonusBusy = false; }
  }
  async function logout() {
    try { await api.post('/api/auth/logout'); } catch (_) { /* egal */ }
    await loadMe();
  }
  const link = (hash) => () => (window.location.hash = hash);
</script>

<header class="head"><h2>Einstellen</h2></header>

<h3 class="area">Je Kind</h3>
<KidChips label="Einstellungen für" />
{#if accountId}
  {#key accountId}
    <section class="card" data-section="lernrahmen" aria-label="Lernrahmen und KI">
      <h4>Lernrahmen und KI · {kidName}</h4>
      <AiSettings {accountId} part="kid" />
      <div class="links">
        <a href="#/learning/legacy?tab=manage"><span>Lernrahmen und KI für das Schuljahr</span><ActionLabel /></a>
        <a href="#/learning"><span>Lernbegleiter: Gespräche, Übungsklausuren freigeben</span><ActionLabel /></a>
      </div>
    </section>

    <div data-section="erinnerung"><ReminderSettings {accountId} /></div>

    <section class="card" data-section="bonus" aria-label="Bonuszeit">
      <h4>Bonuszeit</h4>
      <label for="bonus-time">Frühstarter bis (Uhrzeit, gilt für {kidName})</label>
      <div class="row"><input id="bonus-time" type="time" bind:value={bonus} /><button disabled={bonusBusy || !bonus} onclick={saveBonus}>Speichern</button></div>
      {#if bonusMsg}<small role="status">{bonusMsg}</small>{/if}
    </section>

    <nav class="links card" aria-label={`Mehr für ${kidName}`}>
      <button onclick={link('#/settings?s=budget')}><span><b>Tagesbudget Lernzeit</b><small>Erlass oder eigene Minuten je Wochentag</small></span><ActionLabel /></button>
      <button onclick={link('#/courses')}><span><b>Kurse und Wahlfächer</b><small>Nicht belegte Kurse ausblenden</small></span><ActionLabel /></button>
      <button onclick={link('#/settings?s=iserv')}><span><b>IServ-Zugang und Schulkalender</b><small>Schulbücher, Kalenderrollen, Seitenabruf testen</small></span><ActionLabel /></button>
      <button onclick={link('#/exams')}><span><b>Arbeiten-Kalender und Termine</b><small>Kalender verknüpfen, Termine zuordnen, Schuljahr abschließen</small></span><ActionLabel /></button>
      <button onclick={link('#/klausuren')}><span><b>Arbeiten und Themen</b><small>Themen bearbeiten, Noten</small></span><ActionLabel /></button>
      <button onclick={link('#/materialien')}><span><b>Materialien</b><small>Gegenlesen, korrigieren, was noch fehlt</small></span><ActionLabel /></button>
      <button onclick={link('#/vokabeln')}><span><b>Vokabeln</b><small>Wortlisten prüfen und freigeben</small></span><ActionLabel /></button>
    </nav>
  {/key}
{/if}

<h3 class="area">Haushalt</h3>
<section class="card" data-section="ki" aria-label="KI-Rahmen und Kosten">
  <h4>KI-Rahmen und Kosten</h4>
  {#if householdKid}{#key householdKid}<AiSettings accountId={householdKid} part="household" />{/key}{:else}<p class="muted">Erst ein Kind verlinken.</p>{/if}
</section>

<div data-section="wochenbericht"><ParentReportSettings /></div>

<nav class="links card" aria-label="Haushalt">
  <button onclick={link('#/changes')}><span><b>Rückgängig machen</b><small>{me?.open_audit_count ?? 0} eigene Änderungen, einzeln zurücknehmen</small></span><ActionLabel /></button>
  <button onclick={link('#/learning')}><span><b>Demo ausprobieren (Lernbegleiter)</b><small>Erfundene Beispiele für Klasse 6; kostet echtes KI-Budget, zählt nicht für das Kind</small></span><ActionLabel /></button>
  {#if me?.is_admin}
    <button onclick={link('#/settings?s=bildschirmzeit')}><span><b>Bildschirmzeit</b><small>Adresse freigeben, Webclip für das iPhone</small></span><ActionLabel /></button>
    <button onclick={link('#/settings?s=sicherung')}><span><b>Datensicherung</b><small>Sichern, herunterladen, einspielen</small></span><ActionLabel /></button>
    <button onclick={link('#/setup')}><span><b>Setup</b><small>Nutzer und Kinder zuordnen</small></span><ActionLabel /></button>
  {/if}
</nav>

{#if me?.is_admin}
  <section class="card test" data-section="testmodus" aria-label="Testmodus">
    <h4>Testmodus (Entwickler)</h4>
    <p class="muted">Am Profilknopf startbar: Kinderansicht mit echten Daten, jede Änderung wird protokolliert und beim Beenden zurückgenommen, nichts zählt für Serie oder Lernstand. Nicht zu verwechseln mit „Demo ausprobieren“ im Lernbegleiter.</p>
    <div class="links">
      <button onclick={link('#/settings?s=testmodus')}><span><b>Teständerungen</b><small>{me?.demo_mode ? 'Protokoll läuft' : 'aus'} · Schalter und Protokoll</small></span><ActionLabel /></button>
    </div>
  </section>
{/if}

{#if me?.auth_source === 'pin'}
  <button class="ghost logout" onclick={logout}>Abmelden</button>
{/if}

<style>
  .head h2 { margin: 0 0 var(--sp-3); font-size: var(--fs-xl); }
  .area { font-size: var(--fs-xs); letter-spacing: .04em; text-transform: uppercase; color: var(--fg-muted); margin: var(--sp-4) 2px var(--sp-2); }
  h4 { margin: 0 0 var(--sp-2); font-size: var(--fs-md); }
  .muted { font-size: var(--fs-sm); color: var(--fg-muted); }
  .links { display: grid; gap: 0; padding: 0 var(--sp-3); }
  section .links { padding: 0; margin-top: var(--sp-2); }
  .links a, .links button { display: flex; justify-content: space-between; align-items: center; gap: var(--sp-2); width: 100%; text-align: left; background: transparent; border: 0; border-top: 1px solid var(--border); border-radius: 0; padding: var(--sp-2) 0; min-height: 52px; color: var(--fg); font-size: var(--fs-sm); }
  .links > :first-child { border-top: 0; }
  .links b { display: block; font-weight: 600; }
  .links small { display: block; font-size: var(--fs-xs); color: var(--fg-muted); overflow-wrap: anywhere; }
  .links span { min-width: 0; }
  .row { display: flex; gap: var(--sp-2); align-items: center; margin-top: 4px; }
  .row input { max-width: 10rem; }
  .test { border-style: dashed; }
  .logout { display: block; margin: var(--sp-4) auto 0; }
</style>
