<script>
 import Mentor from './Mentor.svelte';
 import LearningLegacy from './LearningLegacy.svelte';
 let {accountId}=$props();
 let legacy=$state(false);
</script>
{#if legacy}<button class="back" onclick={()=>legacy=false}>← Zum Lernbegleiter</button><LearningLegacy {accountId}/>{:else}<Mentor {accountId} onManage={()=>legacy=true}/>{/if}
<style>.back{min-height:44px;margin-bottom:1rem;padding:.6rem 1rem;border-radius:10px;cursor:pointer}</style>
