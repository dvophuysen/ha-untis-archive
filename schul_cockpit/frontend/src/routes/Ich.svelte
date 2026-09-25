<script>
  // Serie, Abzeichen und Jahresmedaillen (D173), dazu der Weg zu allem Weiteren.
  import { api, ApiError } from '../lib/api.js';
  import ActionLabel from '../lib/ActionLabel.svelte';
  import { formatShortDate } from '../lib/format.js';
  import { profile, saveProfile, COLORS, AVATARS, initials } from '../lib/profile.svelte.js';

  let { accountId, name = '', canManage = false, canStyle = true } = $props();
  let styleMsg = $state('');
  async function setStyle(change) {
    styleMsg = '';
    try { await saveProfile(accountId, change); } catch (e) { styleMsg = e instanceof ApiError ? e.message : 'Nicht gespeichert.'; }
  }
  const prefs = $derived(profile.accountId === accountId ? profile.prefs : null);
  let data = $state(null), error = $state(''), bonus = $state(''), saving = $state(false), saved = $state('');
  let request = 0;
  async function load() {
    const id = accountId, ticket = ++request;
    if (!id) return;
    error = '';
    try {
      const r = await api.get(`/api/accounts/${id}/rewards`);
      if (ticket === request) { data = r; bonus = r.bonus_until; }
    } catch (e) { if (ticket === request) error = e.message || 'Nicht erreichbar.'; }
  }
  $effect(() => { void accountId; data = null; load(); });

  const DAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr'];
  const LEVEL_CLASS = ['bronze', 'silber', 'gold', 'platin', 'diamant'];
  const TOTAL_STEPS = [10, 50, 190, 500, 1000];
  const fmt = (n) => Number(n).toLocaleString('de-DE');
  const nextTotal = $derived(data ? TOTAL_STEPS.find((x) => x > data.total) : null);
  const progress = (b) => (b.next ? Math.round(((b.value - b.prev) / (b.next - b.prev)) * 100) : 100);

  async function saveBonus() {
    saving = true; saved = '';
    try {
      const r = await api.put(`/api/accounts/${accountId}/rewards/settings`, { bonus_until: bonus });
      bonus = r.bonus_until; saved = 'Gespeichert.';
    } catch (e) { saved = e instanceof ApiError ? e.message : 'Nicht gespeichert.'; }
    finally { saving = false; }
  }
</script>

<header class="me-head"><h2>Ich</h2>{#if name}<p>{name}</p>{/if}</header>
{#if error}<div class="error-box" role="alert">{error}</div>{/if}
{#if !data && !error}<p class="muted">Lade …</p>{/if}
{#if data}
  <section class="streak">
    <span class="flame" aria-hidden="true">🔥</span>
    <div><b>{data.streak.current} {data.streak.current === 1 ? 'Schultag' : 'Schultage'}</b>
      <small>{`Rekord ${data.streak.record}`}{data.streak.next_milestone ? ` · nächstes Ziel ${data.streak.next_milestone}` : ''}</small></div>
  </section>

  <section class="card week" aria-label="Deine Woche">
    <div class="days">
      {#each data.week as d, i (d.day)}
        <span class="day {d.state}"><i aria-hidden="true">{d.state === 'full' ? '✓' : d.state === 'rescued' ? '½' : d.state === 'free' ? '–' : ''}</i>{DAYS[i]}</span>
      {/each}
    </div>
    <p class="hint">
      {data.week.some((d) => d.state === 'rescued') ? '½ heißt: am nächsten Morgen vor der ersten Stunde nachgeholt. ' : ''}Geschafft heißt: Aufgaben erledigt, Tasche gepackt, Stunden zurückgemeldet. Fertig vor {data.bonus_until} Uhr ist ein Frühstarter-Tag. Der letzte Schultag vor dem Wochenende zählt voll, wenn bis Sonntagabend alles erledigt ist.
    </p>
  </section>

  <section class="card total">
    <div class="big"><b>{fmt(data.total)}</b><span>geschaffte Schultage seit {formatShortDate(data.start)}</span></div>
    <div class="steps">{#each TOTAL_STEPS as s (s)}<i class:on={data.total >= s}></i>{/each}</div>
    {#if nextTotal}<small>Nächstes Ziel: {fmt(nextTotal)}</small>{/if}
  </section>

  <h3>Abzeichen</h3>
  <div class="badges">
    {#each data.badges as b (b.key)}
      <div class="badge-card {b.level ? LEVEL_CLASS[b.level - 1] : 'none'}" title={b.what}>
        <span class="medal" aria-hidden="true">{b.emoji}</span>
        <b>{b.name}</b>
        <span class="dots" aria-label={b.level_name ?? 'noch keine Stufe'}>{#each b.limits as _, i}<i class={i < b.level ? LEVEL_CLASS[i] : ''}></i>{/each}</span>
        <span class="bar"><span style:width={`${progress(b)}%`}></span></span>
        <small>{b.level_name ?? 'noch keins'}{b.next ? ` · ${fmt(b.value)}/${fmt(b.next)}` : ''}</small>
      </div>
    {/each}
  </div>
  {#if data.special.some((s) => s.count)}
    <div class="special">{#each data.special.filter((s) => s.count) as s (s.key)}<span>{s.emoji} {s.name}{s.count > 1 ? ` ×${s.count}` : ''}</span>{/each}</div>
  {/if}

  <h3>Meine Schulzeit</h3>
  <div class="medals">
    {#each data.medals as m (m.year)}
      <div class="medal-card {m.medal ? m.medal.toLowerCase() : 'none'}" class:running={m.running}>
        <span class="disc">{m.medal ? m.medal[0] : '·'}</span>
        <b>{m.year}</b>
        <small>{m.running ? `läuft · ${m.pct} %` : m.medal ?? `${m.pct} %`}</small>
      </div>
    {/each}
  </div>
  <p class="hint">Medaille am Schuljahresende: Bronze ab {data.medals.at(-1)?.limits[0]} %, Silber ab {data.medals.at(-1)?.limits[1]} %, Gold ab {data.medals.at(-1)?.limits[2]} % geschaffter Schultage.</p>

  {#if canManage}
    <section class="card bonus">
      <label for="bonus-time">Frühstarter bis (Uhrzeit, gilt für dieses Kind)</label>
      <div class="row"><input id="bonus-time" type="time" bind:value={bonus} /><button disabled={saving} onclick={saveBonus}>Speichern</button></div>
      {#if saved}<small role="status">{saved}</small>{/if}
    </section>
  {/if}
{/if}

{#if canStyle && prefs}
  <h3>Gestalten</h3>
  <section class="card style">
    <span class="lbl">Farbe</span>
    <div class="swatches">{#each COLORS as [key, hex, label] (key)}<button class="sw" style:background={hex} aria-label={label} aria-pressed={prefs.color === key} onclick={() => setStyle({ color: key })}></button>{/each}</div>
    <span class="lbl">Profilbild</span>
    <div class="avatars">{#each AVATARS as a (a)}<button aria-label={a || 'Initialen'} aria-pressed={prefs.avatar === a} onclick={() => setStyle({ avatar: a })}>{a || initials(name)}</button>{/each}</div>
    <span class="lbl">Aussehen</span>
    <div class="seg">{#each [['system', 'wie das Gerät'], ['light', 'hell'], ['dark', 'dunkel']] as [k, l] (k)}<button aria-pressed={prefs.theme === k} onclick={() => setStyle({ theme: k })}>{l}</button>{/each}</div>
    <span class="lbl">Dichte</span>
    <div class="seg">{#each [['normal', 'normal'], ['compact', 'kompakt']] as [k, l] (k)}<button aria-pressed={prefs.density === k} onclick={() => setStyle({ density: k })}>{l}</button>{/each}</div>
    <span class="lbl">Wenn alles geschafft ist</span>
    <div class="seg">{#each [['konfetti', 'Konfetti'], ['ring', 'nur Ring'], ['still', 'still']] as [k, l] (k)}<button aria-pressed={prefs.joy === k} onclick={() => setStyle({ joy: k })}>{l}</button>{/each}</div>
    {#if styleMsg}<p class="error-box" role="alert">{styleMsg}</p>{/if}
  </section>
{/if}

<h3>Mehr</h3>
<div class="more">
  {#each [['subjects', 'Fächer'], ['klausuren', 'Arbeiten'], ['materialien', 'Materialien'], ['absences', 'Nachholen'], ['plan', 'Aufgaben und Wochenplanung']] as [target, label] (target)}
    <a href={`#/${target}`}><span>{label}</span><ActionLabel /></a>
  {/each}
</div>

<style>
  .me-head h2{margin:0;font-size:var(--fs-xl)}.me-head p{margin:2px 0 var(--sp-3);color:var(--fg-muted);font-size:var(--fs-sm)}
  .streak{display:flex;gap:var(--sp-3);align-items:center;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-md);padding:var(--sp-3)}
  .flame{width:48px;height:48px;border-radius:var(--r-md);background:var(--warm-soft);display:grid;place-items:center;font-size:1.5rem}
  .streak b{display:block;font-size:var(--fs-lg)}.streak small{color:var(--fg-muted);font-size:var(--fs-xs)}
  .card{margin:var(--sp-2) 0}
  .days{display:flex;gap:var(--sp-2)}
  .day{flex:1;display:grid;justify-items:center;gap:3px;font-size:var(--fs-xs);color:var(--fg-muted);font-weight:700}
  .day i{width:30px;height:30px;border-radius:50%;border:2px solid var(--border);display:grid;place-items:center;font-style:normal;color:var(--accent-fg);font-size:.8rem}
  .day.full i{background:var(--accent);border-color:var(--accent)}
  .day.rescued i{background:color-mix(in oklab,var(--accent) 35%,var(--bg-card));border-color:var(--accent);color:var(--accent)}
  .day.open i{border-style:dashed;border-color:var(--accent)}
  .day.free i,.day.before i{border-style:dotted;color:var(--fg-dim)}
  .hint{font-size:var(--fs-xs);color:var(--fg-muted);margin:var(--sp-2) 0 0}
  .total .big{display:flex;align-items:baseline;gap:var(--sp-2);flex-wrap:wrap}.total .big b{font-size:1.9rem}.total .big span{font-size:var(--fs-xs);color:var(--fg-muted)}
  .steps{display:flex;gap:4px;margin:var(--sp-2) 0 4px}.steps i{flex:1;height:7px;border-radius:4px;background:var(--border)}.steps i.on{background:var(--accent)}
  .total small{font-size:var(--fs-xs);color:var(--fg-muted)}
  h3{font-size:var(--fs-md);margin:var(--sp-4) 0 var(--sp-2)}
  .badges{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--sp-2)}
  .badge-card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-md);padding:var(--sp-2) 6px;display:grid;justify-items:center;gap:4px;text-align:center}
  .badge-card b{font-size:.78rem;line-height:1.2}.badge-card small{font-size:.66rem;color:var(--fg-muted)}
  .medal{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;font-size:1.25rem;background:var(--bg-elevated)}
  .bronze .medal{background:conic-gradient(from 200deg,#b86b3b,#f0c49a,#b86b3b);box-shadow:inset 0 0 0 4px var(--bg-card)}
  .silber .medal{background:conic-gradient(from 200deg,#8a96a3,#e3e8ec,#8a96a3);box-shadow:inset 0 0 0 4px var(--bg-card)}
  .gold .medal{background:conic-gradient(from 200deg,#b7791f,#f7dd8b,#b7791f);box-shadow:inset 0 0 0 4px var(--bg-card)}
  .platin .medal{background:conic-gradient(from 200deg,#4a9a9a,#c9eeee,#4a9a9a);box-shadow:inset 0 0 0 4px var(--bg-card)}
  .diamant .medal{background:conic-gradient(from 200deg,#6a5ad6,#d9d3ff,#6a5ad6);box-shadow:inset 0 0 0 4px var(--bg-card)}
  .none .medal{filter:grayscale(1);opacity:.55}
  .dots{display:flex;gap:3px}.dots i{width:7px;height:7px;border-radius:50%;background:var(--border)}
  .dots i.bronze{background:#b86b3b}.dots i.silber{background:#9aa6b2}.dots i.gold{background:#d4a017}.dots i.platin{background:#5fb3b3}.dots i.diamant{background:#7c6cf0}
  .bar{width:100%;height:5px;border-radius:3px;background:var(--border);overflow:hidden}.bar span{display:block;height:100%;background:var(--accent)}
  .special{display:flex;flex-wrap:wrap;gap:6px;margin-top:var(--sp-2)}.special span{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-pill);padding:3px 10px;font-size:var(--fs-xs)}
  .medals{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
  .medal-card{background:var(--bg-elevated);border-radius:var(--r-md);padding:var(--sp-2) 4px;display:grid;justify-items:center;gap:2px;font-size:.7rem;text-align:center}
  .medal-card small{color:var(--fg-muted)}
  .disc{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-weight:800;color:#fff;background:var(--bg-card);border:2px dashed var(--border)}
  .medal-card.bronze .disc{background:#b86b3b;border:0}.medal-card.silber .disc{background:#9aa6b2;border:0}.medal-card.gold .disc{background:#d4a017;border:0}
  .medal-card.running .disc{border-color:var(--accent);color:var(--accent)}
  .bonus label{font-size:var(--fs-sm)}.bonus .row{margin-top:4px}.bonus input{max-width:10rem}
  .style{display:grid;gap:var(--sp-2)}
  .lbl{font-size:var(--fs-xs);color:var(--fg-muted);font-weight:700;margin-top:var(--sp-1)}
  .swatches{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:var(--sp-2)}
  .sw{aspect-ratio:1;min-height:0;border-radius:50%;border:3px solid var(--bg-card);box-shadow:0 0 0 1px var(--border);padding:0}
  .sw[aria-pressed="true"]{box-shadow:0 0 0 3px var(--fg)}
  .avatars{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:6px}
  .avatars button{aspect-ratio:1;min-height:0;padding:0;border-radius:50%;font-size:1.1rem;font-weight:800;background:var(--bg-elevated)}
  .avatars button[aria-pressed="true"]{outline:3px solid var(--accent);outline-offset:1px}
  .seg{display:flex;flex-wrap:wrap;gap:6px}
  .seg button{min-height:36px;padding:4px 12px;border-radius:var(--r-pill);font-size:var(--fs-sm)}
  .seg button[aria-pressed="true"]{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
  .more{display:grid;gap:var(--sp-2)}
  .more a{display:flex;justify-content:space-between;align-items:center;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-md);padding:var(--sp-3);min-height:52px;color:var(--fg)}
</style>
