<script>
 import {onMount} from 'svelte';
 import {api} from './api.js';
 let {accountId}=$props();
 let data=$state(null),time=$state(''),enabled=$state(false),morning=$state(''),morningOn=$state(false),afternoonOn=$state(false),afternoonDelay=$state(20),busy=$state(false),error=$state(''),message=$state('');
 let request=0;
 async function load(){const id=accountId,ticket=++request;data=null;try{const result=await api.get(`/api/accounts/${id}/reminders`);if(ticket!==request)return;data=result;time=result.remind_at||'';enabled=result.enabled;morning=result.morning_at||'';morningOn=result.morning_enabled;afternoonOn=!!result.afternoon_enabled;afternoonDelay=result.afternoon_delay??20;}catch(e){if(ticket===request)error=e.message;}}
 $effect(()=>{void accountId;load();});
 onMount(()=>()=>request++);
 async function act(fn){if(busy)return;busy=true;error='';message='';try{await fn();}catch(e){error=e.message;}finally{busy=false;}}
 function niceName(service){return service.replace(/^mobile_app_/,'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());}
 async function toggleTarget(service,on){
   const chosen=new Set(data.app_targets||[]);
   if(on)chosen.add(service);else chosen.delete(service);
   data=await api.put(`/api/accounts/${accountId}/reminders/targets`,{services:[...chosen]});
 }
</script>
<section class="card reminder-settings">
 <h3>🔔 Erinnerungen</h3>
 {#if error}<p class="error-box" role="alert">{error}</p>{/if}
 {#if message}<p role="status">{message}</p>{/if}
 {#if data}
   {#if data.can_manage}
    <p>Ein Tagescheck, wenn Hausaufgaben, Fachmaterial für morgen oder Stundenrückmeldungen offen sind.</p>
    <form onsubmit={e=>{e.preventDefault();act(async()=>{await api.put(`/api/accounts/${accountId}/reminders`,{enabled,remind_at:time||null,morning_enabled:morningOn,morning_at:morning||null,afternoon_enabled:afternoonOn,afternoon_delay:Number(afternoonDelay)||0});await load();message='Erinnerungszeit gespeichert.';});}}>
     <label>Uhrzeit (Deutschland)<input type="time" min="14:00" max="21:00" bind:value={time} required={enabled} disabled={busy}/></label>
     <label class="check"><input type="checkbox" bind:checked={enabled} disabled={busy}/> Tägliche Erinnerung einschalten</label>
     <h4>Wenn der Abend nicht abgeschlossen wurde</h4>
     <p class="muted">Standardmäßig aus. Eine zweite, kürzere Mitteilung am Morgen — nur an den, der am Abend nicht abgeschlossen hat, und nur wenn wirklich etwas offen ist. Wer abschließt, bleibt unbehelligt.</p>
     <label>Morgens um<input type="time" min="05:00" max="09:00" bind:value={morning} disabled={busy||!morningOn}/></label>
     <label class="check"><input type="checkbox" bind:checked={morningOn} disabled={busy}/> Morgenmitteilung einschalten</label>
     <h4>Nach der Schule</h4>
     <p class="muted">Standardmäßig aus. Kurz nach der letzten Stunde fragt die App einmal: Steht alles von heute in der App? Die Antwort ist ein Foto oder „nichts Neues“; aus dem Foto entsteht die Aufgabe mit Fach und Termin der nächsten Stunde. Die Karte dazu steht nachmittags auch ohne Mitteilung auf der Startseite.</p>
     <label>Minuten nach der letzten Stunde<input type="number" min="0" max="180" step="5" bind:value={afternoonDelay} disabled={busy||!afternoonOn}/></label>
     <label class="check"><input type="checkbox" bind:checked={afternoonOn} disabled={busy}/> Frage nach der Schule einschalten</label>
     <button disabled={busy}>Speichern</button>
    </form>
    <h4>Auf welches Gerät</h4>
    <p class="muted">Die Erinnerung geht über die Home-Assistant-App. Sie ist eine normale App und lässt sich in der Bildschirmzeit unter „Immer erlaubt" eintragen; eine Web-App vom Startbildschirm wird dort während einer Auszeit gesperrt.</p>
    {#if data.app_services?.length}
     {#each data.app_services as service}
      <label class="check"><input type="checkbox" checked={(data.app_targets||[]).includes(service)} disabled={busy} onchange={e=>act(()=>toggleTarget(service,e.currentTarget.checked))}/> {niceName(service)}</label>
     {/each}
     <button disabled={busy||!(data.app_targets||[]).length} onclick={()=>act(async()=>{const r=await api.post(`/api/accounts/${accountId}/reminders/test`);const ok=Object.values(r.sent).filter(Boolean).length;message=ok?`An ${ok} Gerät${ok===1?'':'e'} übergeben. Kurz antippen — es sollte dein Tag aufgehen.`:'Kein Gerät erreicht.';await load();})}>Testnachricht senden</button>
    {:else}<p class="muted">Home Assistant meldet keine App-Geräte. Die Home-Assistant-App muss auf dem Kindergerät angemeldet sein.</p>{/if}
    {#if data.last_app_delivery}<p class="muted">Zuletzt an {niceName(data.last_app_delivery.service)}: {data.last_app_delivery.status==='accepted'?'übergeben':'fehlgeschlagen'}</p>{/if}
    <p class="muted">Höchstens einmal pro Gerät und Tag. Alles erledigt? Dann bleibt es still. Nach längeren Ausfällen wird nachts nichts nachgeschickt.</p>
   {:else}<p>{data.enabled?`Dein Tagescheck ist um ${data.remind_at} Uhr. Wenn alles erledigt ist, bleibt es still.`:'Automatische Erinnerungen sind noch aus. Deine Eltern können eine Uhrzeit festlegen.'}</p>
    {#if data.enabled&&data.morning_enabled}<p class="muted">Schließt du den Abend ab, kommt am Morgen nichts mehr.</p>{/if}
    {#if data.afternoon_enabled}<p class="muted">Nach der letzten Stunde fragt die App einmal, ob alles von heute notiert ist.</p>{/if}{/if}
 {/if}
</section>
<style>
 h3{font-size:1.05rem;margin:0 0 12px}h4{font-size:.95rem;margin:16px 0 6px}p{line-height:1.45}.check{display:flex;align-items:center;gap:10px}.check input{width:24px;height:24px;min-height:24px}button{margin:6px 6px 0 0}input[type="time"],input[type="number"]{max-width:200px}label{margin:12px 0}.muted{font-size:.85rem;color:var(--fg-muted)}
</style>
