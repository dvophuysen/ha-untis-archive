const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const handlers={},shown=[],opened=[],navigated=[];let windows=[];
const self={registration:{scope:'https://school.example/app/',showNotification:async(title,options)=>shown.push({title,...options})},addEventListener:(name,fn)=>handlers[name]=fn,clients:{matchAll:async()=>windows,openWindow:async url=>opened.push(url),claim:()=>{}},skipWaiting:()=>{}};
vm.runInNewContext(fs.readFileSync('schul_cockpit/frontend/public/sw.js','utf8'),{self,URL,Date,caches:{},fetch(){throw Error('unexpected fetch')}});
async function dispatch(name,extra){let work;handlers[name]({...extra,waitUntil:p=>work=p});await work;}
(async()=>{
 await dispatch('push',{data:{json:()=>({title:'Tagescheck',body:'Material prüfen',url:'./?acc=2#/today',tag:'check'})}});assert.equal(shown[0].body,'Material prüfen');assert.equal(shown[0].data.url,'./?acc=2#/today');
 await dispatch('push',{data:{json:()=>{throw Error('invalid');}}});assert.equal(shown[1].title,'Schul-Cockpit');
 await dispatch('notificationclick',{notification:{close(){},data:{url:'https://evil.example/'}}});assert.equal(opened[0],'https://school.example/app/#/today');
 windows=[{url:'https://school.example/app/#/learning',navigate:async url=>navigated.push(url),focus:async()=>{}}];
 await dispatch('notificationclick',{notification:{close(){},data:{url:'./?acc=2#/today'}}});assert.equal(navigated[0],'https://school.example/app/?acc=2#/today');
 for(const url of ['https://school.example/app/api/accounts/1/tasks','https://school.example/app/api/me','https://school.example/app/api/accounts/1/packing/2026-09-15'])handlers.fetch({request:{method:'GET',url},respondWith(){throw Error('Private API must bypass cache');}});
 console.log('PASS: visible push, malformed payload, safe app links, account deep link, no API cache fallback');
})().catch(e=>{console.error(e);process.exit(1)});
