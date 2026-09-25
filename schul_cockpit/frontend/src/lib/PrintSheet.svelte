<script>
  // Druckblatt innerhalb der App (D191). Ein Link in einen neuen Tab verließ auf
  // dem iPhone die Web-App: Safari fragte nach dem Bildschirmzeit-Code und kannte
  // danach die Anmeldung der App nicht („Unauthorized“). Hier wird das Blatt mit
  // der Anmeldung der App geladen und in einem eingebetteten Rahmen gedruckt.
  import { joinUrl } from './api.js';
  import { viewHeader } from './viewMode.svelte.js';

  let { url, title = 'Übungsblatt', spaceChoice = false, onclose = () => {} } = $props();
  let onlyTasks = $state(false);
  let html = $state(''), error = $state(''), frame = $state(null), note = $state('');

  $effect(() => {
    void url; void onlyTasks;
    load();
  });

  // Nur das zuletzt angeforderte Blatt gilt (Umschalten „nur Aufgaben“).
  let request = 0;
  async function load() {
    const ticket = ++request;
    error = ''; html = '';
    try {
      const headers = {};
      const mode = viewHeader();
      if (mode) headers['x-view-mode'] = mode;
      const target = spaceChoice && onlyTasks ? `${url}${url.includes('?') ? '&' : '?'}space=none` : url;
      const resp = await fetch(joinUrl(target), { credentials: 'include', headers });
      if (!resp.ok) throw new Error(resp.status === 401 ? 'Nicht angemeldet.' : `Fehler ${resp.status}`);
      // Die eingebauten Hinweise des Blatts gelten für den Browser; in der App druckt der Knopf oben.
      const text = (await resp.text()).replace('</head>', '<style>.tools{display:none!important}</style></head>');
      if (ticket === request) html = text;
    } catch (e) {
      if (ticket === request) error = `Das Blatt konnte nicht geladen werden. ${e.message}`;
    }
  }

  function print() {
    note = '';
    try {
      frame.contentWindow.focus();
      frame.contentWindow.print();
    } catch {
      note = 'Drucken ging hier nicht. Bitte „Teilen“ nehmen und dort „Drucken“ wählen.';
    }
  }

  async function share() {
    note = '';
    try {
      const file = new File([html], `${title}.html`, { type: 'text/html' });
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title });
      } else {
        note = 'Teilen wird auf diesem Gerät nicht unterstützt. Bitte „Drucken“ nehmen.';
      }
    } catch (e) {
      if (e?.name !== 'AbortError') note = 'Teilen hat nicht geklappt.';
    }
  }
</script>

<div class="print-overlay" role="dialog" aria-modal="true" aria-label={title}>
  <div class="bar">
    <button class="ghost" onclick={onclose}>Schließen</button>
    <strong>{title}</strong>
    <span class="acts">
      <button class="ghost" disabled={!html} onclick={share}>Teilen</button>
      <button class="primary" disabled={!html} onclick={print}>Drucken</button>
    </span>
  </div>
  {#if spaceChoice}
    <div class="choice" role="group" aria-label="Wie drucken?">
      <button class:on={!onlyTasks} aria-pressed={!onlyTasks} onclick={() => (onlyTasks = false)}>Mit Schreibplatz</button>
      <button class:on={onlyTasks} aria-pressed={onlyTasks} onclick={() => (onlyTasks = true)}>Nur Aufgaben · im Heft lösen</button>
    </div>
  {/if}
  {#if note}<p class="note" role="status">{note}</p>{/if}
  {#if error}<p class="error-box" role="alert">{error}</p>
  {:else if !html}<p class="muted">Blatt wird geladen …</p>
  {:else}<iframe bind:this={frame} srcdoc={html} title={title}></iframe>{/if}
</div>

<style>
  .print-overlay{position:fixed;inset:0;z-index:60;background:var(--bg);display:flex;flex-direction:column;padding:env(safe-area-inset-top,0px) 0 env(safe-area-inset-bottom,0px)}
  .bar{display:flex;align-items:center;justify-content:space-between;gap:var(--sp-2);padding:var(--sp-2) var(--sp-3);border-bottom:1px solid var(--border);background:var(--bg-card)}
  .bar strong{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:center}
  .acts{display:flex;gap:6px}
  .bar button{min-height:44px}
  .choice{display:flex;gap:6px;padding:var(--sp-2) var(--sp-3);flex-wrap:wrap}
  .choice button{min-height:40px;border-radius:var(--r-pill);padding:4px 12px;border:1px solid var(--border);background:var(--bg-card);color:var(--fg)}
  .choice button.on{background:var(--accent);color:var(--accent-fg,#fff);border-color:var(--accent)}
  iframe{flex:1;width:100%;border:0;background:#fff}
  .note,.muted,.error-box{margin:var(--sp-3)}
  .note{padding:var(--sp-2);background:var(--warm-soft);border-radius:var(--r-sm)}
</style>
