<script>
 // Lernen (D186): Kinder, Mitlesen und Kindmodus sehen den Kompass; die
 // Elternansicht behält ihren Lernraum (D183). Die Adresse wird bei jedem
 // Wechsel neu ausgewertet, damit Links innerhalb der Lernseite wirken.
 import {onMount} from 'svelte';
 import Compass from './Compass.svelte';
 import Mentor from './Mentor.svelte';
 import Lazy from '../lib/Lazy.svelte';
 import {appState} from '../lib/store.svelte.js';
 import {actsAsParent} from '../lib/viewMode.svelte.js';
 const loadLegacy=()=>import('./LearningLegacy.svelte');
 let {accountId}=$props();
 // Jedes Mal ein neuer Wert, auch wenn derselbe Link noch einmal angetippt wird:
 // Nach dem Öffnen einer Einheit nimmt clearQuery die Parameter ohne hashchange weg.
 let nav=$state({hash:window.location.hash});
 onMount(()=>{const h=()=>{nav={hash:window.location.hash};};window.addEventListener('hashchange',h);return()=>window.removeEventListener('hashchange',h);});
 const parent=$derived(actsAsParent(appState.me));
 let legacy=$state(window.location.hash.includes('/legacy'));
</script>
{#if !parent}<Compass {accountId} {nav}/>
{:else if legacy}<button class="back" onclick={()=>legacy=false}>← Zum Lernbegleiter</button><Lazy load={loadLegacy} {accountId}/>
{:else}<Mentor {accountId} {nav} onManage={()=>legacy=true}/>{/if}
<style>.back{min-height:44px;margin-bottom:1rem;padding:.6rem 1rem;border-radius:10px;cursor:pointer}</style>
