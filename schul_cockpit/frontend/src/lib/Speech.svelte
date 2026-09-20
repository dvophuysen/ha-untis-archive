<script>
  import { onDestroy } from 'svelte';
  // Spracheingabe mit eigener Erkennung: Halten und sprechen, loslassen, dann
  // erscheint der erkannte Text zum Prüfen. Nicht das Diktat der Tastatur, weil
  // das Fachbegriffe und lateinische Formen zu Alltagswörtern macht.
  let { onText, transcribe, disabled = false, label = 'Aufnahme: Deutsch · eigene Erkennung', compact = false } = $props();
  let recorder = $state(null), recording = $state(false), working = $state(false), seconds = $state(0), error = $state('');
  let chunks = [], timer = null, startedAt = 0, stream = null, mime = '';
  let disposed = false;
  // Lautstärke mitmessen: Aus Stille oder Rauschen erfindet die Erkennung Text,
  // der zum Hinweis passt („Mit der a-Deklination.“). Leise Aufnahmen bleiben hier.
  let audioCtx = null, analyser = null, loudest = 0;
  const MIN_LOUDNESS = 0.02;
  const supported = typeof window !== 'undefined' && !!(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);
  onDestroy(() => {
    disposed = true; clearInterval(timer);
    if (recorder) { recorder.onstop = null; if (recorder.state !== 'inactive') recorder.stop(); }
    stream?.getTracks().forEach((t) => t.stop());
    audioCtx?.close().catch(() => {});
  });

  function pickMime() {
    for (const m of ['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']) {
      if (MediaRecorder.isTypeSupported?.(m)) return m;
    }
    return '';
  }
  async function start() {
    if (recording || working || disabled) return;
    error = '';
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (disposed) { stream.getTracks().forEach((t) => t.stop()); return; }
    } catch (e) {
      error = 'Kein Zugriff auf das Mikrofon. Bitte in den Einstellungen erlauben oder tippen.';
      return;
    }
    loudest = 0;
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioCtx.createAnalyser(); analyser.fftSize = 1024;
      audioCtx.createMediaStreamSource(stream).connect(analyser);
    } catch { analyser = null; }
    mime = pickMime();
    recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
    chunks = [];
    recorder.ondataavailable = (e) => { if (e.data?.size) chunks.push(e.data); };
    recorder.onstop = finish;
    recorder.start();
    recording = true; seconds = 0; startedAt = Date.now();
    timer = setInterval(() => {
      seconds = Math.round((Date.now() - startedAt) / 1000);
      if (analyser) {
        const buf = new Uint8Array(analyser.fftSize); analyser.getByteTimeDomainData(buf);
        let sum = 0; for (const v of buf) { const x = (v - 128) / 128; sum += x * x; }
        loudest = Math.max(loudest, Math.sqrt(sum / buf.length));
      }
      if (seconds >= 120) stop();
    }, 120);
  }
  function stop() {
    if (!recording) return;
    recording = false;
    clearInterval(timer);
    try { recorder?.stop(); } catch { /* schon gestoppt */ }
  }
  async function finish() {
    stream?.getTracks().forEach((t) => t.stop());
    try { await audioCtx?.close(); } catch { /* egal */ }
    audioCtx = null;
    const type = recorder?.mimeType || mime || 'audio/webm';
    const blob = new Blob(chunks, { type });
    const took = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
    if (blob.size < 800 || took < 1) { error = 'Zu kurz. Halte den Knopf, während du sprichst.'; return; }
    if (analyser && loudest < MIN_LOUDNESS) { error = 'Ich habe nichts gehört. Sprich etwas lauter oder näher am Gerät.'; return; }
    working = true;
    try {
      const text = await transcribe(blob, took);
      if (!text?.trim()) error = 'Ich habe nichts verstanden. Noch einmal, etwas näher am Gerät?';
      else if (!disposed) onText(text.trim());
    } catch (e) {
      error = e.message;
    } finally {
      working = false;
    }
  }
  function toggle() { recording ? stop() : start(); }
</script>

{#if supported}
  <div class="speech" class:compact>
    <button type="button" class="talk" class:recording class:working aria-pressed={recording} disabled={disabled || working}
      onpointerdown={(e) => { if (e.pointerType !== 'mouse' || e.button === 0) { e.preventDefault(); start(); } }}
      onpointerup={stop} onpointercancel={stop} onpointerleave={() => { if (recording) stop(); }}
      onkeydown={(e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggle(); } }}
      oncontextmenu={(e) => e.preventDefault()}>
      <span class="dot" aria-hidden="true"></span>
      {#if working}Wird erkannt …{:else if recording}Aufnahme läuft · {seconds} s · loslassen zum Senden{:else}Halten und antworten{/if}
    </button>
    <small>{label}</small>
    {#if error}<p class="speech-error" role="alert">{error}</p>{/if}
  </div>
{/if}

<style>
  .speech { display: grid; gap: 0.25rem; margin: 0.4rem 0; }
  .speech small { text-align: center; font-size: 0.75rem; opacity: 0.75; }
  .talk { width: 100%; min-height: 64px; border-radius: 16px; border: 1px solid var(--accent, #247552); background: var(--accent-soft, #e6f2ec); color: inherit; font: inherit; font-weight: 650; display: flex; align-items: center; justify-content: center; gap: 0.6rem; touch-action: none; user-select: none; -webkit-user-select: none; cursor: pointer; }
  .compact .talk { min-height: 52px; }
  .talk .dot { width: 14px; height: 14px; border-radius: 50%; background: var(--accent, #247552); }
  .talk.recording { background: var(--rating-1, #b3261e); color: #fff; border-color: transparent; }
  .talk.recording .dot { background: #fff; animation: pulse 1s infinite; }
  .talk.working { opacity: 0.7; }
  .talk:disabled { opacity: 0.5; cursor: default; }
  .speech-error { margin: 0; font-size: 0.85rem; color: var(--rating-1, #b3261e); }
  @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.5); } }
</style>
