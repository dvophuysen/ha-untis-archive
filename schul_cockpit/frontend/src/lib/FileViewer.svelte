<script>
  // Dateiansicht innerhalb der App (D206): Fotos, Seiten, Materialien. Immer mit
  // Schließen-Knopf oben; Bilder lassen sich vergrößern, andere Dateien stehen
  // in einem eingebetteten Rahmen und lassen sich über „Teilen“ weitergeben.
  import { joinUrl } from './api.js';
  import { viewHeader } from './viewMode.svelte.js';
  import { fileView, closeFile } from './fileViewer.svelte.js';

  let blobUrl = $state(''), kind = $state(''), mime = $state(''), error = $state(''), note = $state(''), scale = $state(1);
  let blob = null, closeBtn = $state(null);
  const item = $derived(fileView.open);

  $effect(() => {
    const it = item;
    if (!it) return;
    let alive = true;
    blobUrl = ''; kind = ''; error = ''; note = ''; scale = 1; blob = null;
    (async () => {
      try {
        const headers = {};
        const mode = viewHeader();
        if (mode) headers['x-view-mode'] = mode;
        const resp = await fetch(joinUrl(it.url.replace(/^\.\//, '')), { credentials: 'include', headers });
        if (!resp.ok) throw new Error(resp.status === 401 ? 'Nicht angemeldet.' : resp.status === 404 ? 'Die Datei gibt es nicht mehr.' : `Fehler ${resp.status}`);
        const b = await resp.blob();
        if (!alive) return;
        blob = b;
        mime = b.type || resp.headers.get('content-type') || '';
        kind = mime.startsWith('image/') ? 'image' : 'frame';
        blobUrl = URL.createObjectURL(b);
      } catch (e) {
        if (alive) error = `Die Datei konnte nicht geladen werden. ${e.message}`;
      }
    })();
    return () => { alive = false; };
  });

  // Aufräumen: alte Adresse freigeben, sobald eine neue da ist oder geschlossen wird.
  $effect(() => {
    const u = blobUrl;
    return () => { if (u) URL.revokeObjectURL(u); };
  });

  $effect(() => { if (item && closeBtn) closeBtn.focus(); });

  function onkey(e) {
    if (item && e.key === 'Escape') closeFile();
  }

  function onpop() {
    // Zurück-Taste (Android) oder Wischgeste schließt die Ansicht.
    if (fileView.open && !history.state?.fileViewer) fileView.open = null;
  }

  const name = $derived.by(() => {
    const t = (item?.title || '').trim();
    const ext = mime.includes('pdf') ? 'pdf' : mime.startsWith('image/') ? (mime.split('/')[1] || 'jpg').replace('jpeg', 'jpg') : 'bin';
    return /\.[a-z0-9]{2,4}$/i.test(t) ? t : `${t || 'Datei'}.${ext}`;
  });

  async function share() {
    note = '';
    try {
      const file = new File([blob], name, { type: mime || 'application/octet-stream' });
      if (navigator.canShare?.({ files: [file] })) await navigator.share({ files: [file], title: item?.title || name });
      else note = 'Teilen wird auf diesem Gerät nicht unterstützt.';
    } catch (e) {
      if (e?.name !== 'AbortError') note = 'Teilen hat nicht geklappt.';
    }
  }
</script>

<svelte:window onkeydown={onkey} onpopstate={onpop} />

{#if item}
  <div class="file-viewer" role="dialog" aria-modal="true" aria-label={item.title || 'Datei'}>
    <div class="bar">
      <button bind:this={closeBtn} class="primary close" onclick={closeFile} aria-label="Schließen">✕ Schließen</button>
      <strong>{item.title || (kind === 'image' ? 'Bild' : 'Datei')}</strong>
      <span class="acts">
        {#if kind === 'image'}
          <button class="ghost" disabled={scale <= 1} onclick={() => (scale = Math.max(1, scale - 1))} aria-label="Verkleinern">−</button>
          <button class="ghost" disabled={scale >= 4} onclick={() => (scale = Math.min(4, scale + 1))} aria-label="Vergrößern">+</button>
        {/if}
        <button class="ghost" disabled={!blobUrl} onclick={share}>Teilen</button>
      </span>
    </div>
    {#if note}<p class="note" role="status">{note}</p>{/if}
    <div class="body" class:zoomed={scale > 1}>
      {#if error}<p class="error-box" role="alert">{error}</p>
      {:else if !blobUrl}<p class="muted">Wird geladen …</p>
      {:else if kind === 'image'}<img src={blobUrl} alt={item.title || 'Bild'} style:width={`${scale * 100}%`} />
      {:else}<iframe src={blobUrl} title={item.title || 'Datei'}></iframe>{/if}
    </div>
  </div>
{/if}

<style>
  .file-viewer { position: fixed; inset: 0; z-index: 90; display: flex; flex-direction: column; background: rgba(0, 0, 0, .94); }
  .bar { display: flex; align-items: center; gap: .5rem; padding: max(env(safe-area-inset-top), .6rem) .6rem .6rem; background: var(--surface, #fff); color: var(--text, #111); }
  .bar strong { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .bar button { min-height: 44px; min-width: 44px; }
  .acts { display: flex; gap: .3rem; }
  .note { margin: 0; padding: .4rem .6rem; background: var(--surface, #fff); }
  .body { flex: 1; min-height: 0; overflow: auto; display: flex; align-items: center; justify-content: center; padding: .5rem .5rem max(env(safe-area-inset-bottom), .5rem); -webkit-overflow-scrolling: touch; }
  .body.zoomed { align-items: flex-start; justify-content: flex-start; }
  .body img { max-width: none; height: auto; background: #fff; }
  .body:not(.zoomed) img { max-width: 100%; max-height: 100%; object-fit: contain; }
  .body iframe { width: 100%; height: 100%; border: 0; background: #fff; }
  .body .muted { color: #fff; }
</style>
