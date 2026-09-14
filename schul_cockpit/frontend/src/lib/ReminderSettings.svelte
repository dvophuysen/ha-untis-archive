<script>
 import {onMount} from 'svelte';
 import {api} from './api.js';
 let {accountId}=$props();
 let data=$state(null),time=$state(''),enabled=$state(false),morning=$state(''),morningOn=$state(true),busy=$state(false),error=$state(''),message=$state(''),device=$state(false),supported=$state(false);
 let request=0;
 async function load(){const id=accountId,ticket=++request;data=null;try{const result=await api.get(`/api/accounts/${id}/reminders`);if(ticket!==request)return;data=result;time=result.remind_at||'';enabled=result.enabled;morning=result.morning_at||'';morningOn=result.morning_enabled;}catch(e){if(ticket===request)error=e.message;}}
 $effect(()=>{void accountId;load();});
 onMount(()=>{supported='serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;if(supported)navigator.serviceWorker.ready.then(r=>r.pushManager.getSubscription()).then(s=>device=!!s).catch(()=>{});return()=>request++;});
 async function act(fn){if(busy)return;busy=true;error='';message='';try{await fn();}catch(e){error=e.message;}finally{busy=false;}}
 async function ready(){let timer;try{return await Promise.race([navigator.serviceWorker.ready,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Die App ist noch nicht bereit. Bitte neu öffnen.')),10000);})]);}finally{clearTimeout(timer);}}
 function keyBytes(text){const b64=text.replace(/-/g,'+').replace(/_/g,'/');return Uint8Array.from(atob(b64+'='.repeat((4-b64.length%4)%4)),c=>c.charCodeAt(0));}
 async function register(){
   // Permission must be requested directly from a user's tap.
   const permission=await Notification.requestPermission();
   if(permission!=='granted')throw new Error('Benachrichtigungen sind nicht erlaubt. Prüfe die Geräteeinstellungen.');
   const registration=await ready();
   let subscription=await registration.pushManager.getSubscription();
   if(!subscription){const key=await api.get('/api/push/vapid-key');subscription=await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:keyBytes(key.public_key)});}
   await api.post('/api/push/subscribe',{...subscription.toJSON(),ua_label:'Mein Gerät'});
   device=true;await load();message='Gerät angemeldet. Probiere eine Testnachricht aus.';
 }
 function niceName(service){return service.replace(/^mobile_app_/,'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());}
 async function toggleTarget(service,on){
   const chosen=new Set(data.app_targets||[]);
   if(on)chosen.add(service);else chosen.delete(service);
   data=await api.put(`/api/accounts/${accountId}/reminders/targets`,{services:[...chosen]});
 }
 async function unregister(){const registration=await ready();const subscription=await registration.pushManager.getSubscription();if(subscription){await api.post('/api/push/unsubscribe',{endpoint:subscription.endpoint});await subscription.unsubscribe();}device=false;await load();message='Dieses Gerät ist abgemeldet.';}
</script>
<section class="card reminder-settings">
 <h3>🔔 Erinnerungen</h3>
 {#if error}<p class="error-box" role="alert">{error}</p>{/if}
 {#if message}<p role="status">{message}</p>{/if}
 {#if data}
   {#if data.can_manage}
    <p>Ein Tagescheck, wenn Hausaufgaben, Fachmaterial für morgen oder Stundenrückmeldungen offen sind.</p>
    <form onsubmit={e=>{e.preventDefault();act(async()=>{await api.put(`/api/accounts/${accountId}/reminders`,{enabled,remind_at:time||null,morning_enabled:morningOn,morning_at:morning||null});await load();message='Erinnerungszeit gespeichert.';});}}>
     <label>Uhrzeit (Deutschland)<input type="time" min="14:00" max="21:00" bind:value={time} required={enabled} disabled={busy}/></label>
     <label class="check"><input type="checkbox" bind:checked={enabled} disabled={busy}/> Tägliche Erinnerung einschalten</label>
     <h4>Wenn der Abend nicht abgeschlossen wurde</h4>
     <p class="muted">Eine zweite, kürzere Mitteilung am Morgen — nur an den, der am Abend nicht abgeschlossen hat, und nur wenn wirklich etwas offen ist. Wer abschließt, bleibt unbehelligt.</p>
     <label>Morgens um<input type="time" min="05:00" max="09:00" bind:value={morning} disabled={busy||!morningOn}/></label>
     <label class="check"><input type="checkbox" bind:checked={morningOn} disabled={busy}/> Morgenmitteilung einschalten</label>
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
    <h4>Älterer Weg über den Browser</h4>
    <p class="muted">{data.devices} Kindergeräte über Web-Push angemeldet. Dieser Weg wird nicht mehr weiterentwickelt.</p>
    <p class="muted">Höchstens einmal pro Gerät und Tag. Alles erledigt? Dann bleibt es still. Nach längeren Ausfällen wird nachts nichts nachgeschickt.</p>
    {#if data.last_delivery}<p class="muted">Letzter Versand: {data.last_delivery.status==='accepted'?'Vom Push-Dienst angenommen – Empfang nicht bestätigt':data.last_delivery.status==='failed'?'Fehlgeschlagen – bitte Gerät testen':'Ausgang unklar – bitte Gerät testen'}</p>{/if}
   {:else}<p>{data.enabled?`Dein Tagescheck ist um ${data.remind_at} Uhr. Wenn alles erledigt ist, bleibt es still.`:'Automatische Erinnerungen sind noch aus. Deine Eltern können eine Uhrzeit festlegen.'}</p>
    {#if data.enabled&&data.morning_enabled}<p class="muted">Schließt du den Abend ab, kommt am Morgen nichts mehr.</p>{/if}{/if}
 {/if}
 {#if supported}
  <button disabled={busy} onclick={()=>act(register)}>{device?'Gerät für dieses Konto anmelden':'Dieses Gerät anmelden'}</button>
  {#if device}<button disabled={busy} onclick={()=>act(async()=>{const result=await api.post('/api/push/test');message=result.sent?'Test an den Push-Dienst übergeben. Ist er auf deinem Gerät angekommen?':'Kein Gerät erreicht. Bitte erneut anmelden.';})}>Testnachricht senden</button><button disabled={busy} onclick={()=>act(unregister)}>Gerät abmelden</button>{/if}
 {:else}<p>Auf dem iPhone oder iPad: App zum Home-Bildschirm hinzufügen und von dort öffnen.</p>{/if}
</section>
<style>
 h3{font-size:1.05rem;margin:0 0 12px}h4{font-size:.95rem;margin:16px 0 6px}p{line-height:1.45}.check{display:flex;align-items:center;gap:10px}.check input{width:24px;height:24px;min-height:24px}button{margin:6px 6px 0 0}input[type="time"]{max-width:200px}label{margin:12px 0}.muted{font-size:.85rem;color:var(--fg-muted)}
</style>
