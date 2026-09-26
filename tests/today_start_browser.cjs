// Start von „Heute“ mit langsamer Verbindung (300 ms je Antwort, wie über den
// Fernzugriff): Die Tasche kommt mit /today, kein eigener GET /packing, und
// auf dem Kindergerät laufen die Daten schon gleichzeitig mit /api/me los.
// Passt das gemerkte Kind nicht, ist die Elternhülle dran oder fehlt die
// Anmeldung, verfallen die Vorabantworten still.
// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
const {chromium:pw}=require('playwright-core');
const fs=require('fs');const http=require('http');const path=require('path');const assert=require('assert/strict');
const DELAY=300;
(async()=>{
 const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
 const server=http.createServer((req,res)=>{const p=req.url.split('?')[0];const file=path.join(root,p==='/'?'index.html':p);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});
 await new Promise(r=>server.listen(4191,'127.0.0.1',r));
 const browser=await pw.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
 const errors=[];const timings={};
 async function open({time='2026-09-14T14:00:00+02:00',saved=null,shell=null,me='kid',withBag=true,hash='#/today'}={}){
  const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});
  page.setDefaultTimeout(8000);page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(([saved,shell])=>{try{if(saved)localStorage.setItem('activeAccountId',saved);if(shell)localStorage.setItem('lastShell',shell);}catch{}},[saved,shell]);
  await page.clock.install({time:new Date(time)});
  const t0=Date.now(),calls=[],states={};let bagSeen=null;
  await page.exposeFunction('bagSeen',()=>{if(bagSeen===null)bagSeen=Date.now()-t0;});
  await page.addInitScript(()=>{new MutationObserver(()=>{if(document.querySelector('.bag-item'))window.bagSeen();}).observe(document,{childList:true,subtree:true});});
  const morning=time.includes('T07:');
  const bag=(day)=>{const s=states[day]||={};const items=[{key:'subject:math',label:'Mathematik'},{key:'subject:sport',label:'Sport'}].map(i=>({...i,done:!!s[i.key],revision:s[i.key]?1:0}));
   return {account_id:1,school_day:day,plan_key:'a'.repeat(64),can_write:true,items,confirmed_count:items.filter(i=>i.done).length,status:items.every(i=>i.done)?'packed':'open',
    schedule:[{id:11,subject_name:'Mathematik',start_hhmm:'08:00',room:'204',material_key:'subject:math',material_checkbox:true},{id:12,subject_name:'Sport',start_hhmm:'09:50',material_key:'subject:sport',material_checkbox:true}]};};
  await page.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url()),u=url.pathname,m=req.method();const call={m,u:u+url.search,start:Date.now()-t0};calls.push(call);let body={},status=200;
   if(u==='/api/me'){if(me==='login'){status=401;body={detail:'Bitte anmelden'};}else body=me==='parent'?{id:1,role:'parent',is_admin:false,auth_source:'ingress',accounts:[{id:1,name:'Beispielkind'}]}:{id:2,role:'child',is_admin:false,auth_source:'ingress',accounts:[{id:1,name:'Beispielkind'}]};}
   else if(me==='login'&&u.startsWith('/api/accounts/')){status=401;body={detail:'Bitte anmelden'};}
   else if(u==='/api/auth/users')body={users:[]};
   else if(u==='/api/dashboard')body={today:'2026-09-14',kids:[]};
   else if(!u.startsWith('/api/accounts/1/')&&u.startsWith('/api/accounts/')){status=403;body={detail:'Account not linked to this user'};}
   else if(u.includes('/packing/')){const day=u.split('/').at(-1);if(m==='PUT'){const b=req.postDataJSON();(states[day]||={})[b.item_key]=b.done;}body=bag(day);}
   else if(u.endsWith('/today'))body={date:'2026-09-14',lessons:[{id:1,date:'2026-09-14',subject_name:'Deutsch',start_hhmm:'08:00',end_hhmm:'08:45',start_time:800,end_time:845,checkin:{rating:3,note:null}}],
     next:{date:'2026-09-15',lessons:[]},carry_lessons:null,feedback_backlog:[],study_plan:null,new_results:[],photo_requests:[],retakes:[],next_by_subject:{},
     ...(withBag?{bag:morning?null:bag('2026-09-15'),today_bag:morning?bag('2026-09-14'):null}:{})};
   else if(u.endsWith('/tasks'))body={tasks:[]};
   else if(u.endsWith('/plan'))body={today:{actions:[]},upcoming_exams:[],errors:[]};
   else if(u.endsWith('/rewards'))body={streak:{current:1,record:1},today:{},total:1,badges:[],celebrate:[],next_up:[]};
   await new Promise(r=>setTimeout(r,DELAY));call.end=Date.now()-t0;
   await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});});
  await page.goto('http://127.0.0.1:4191/'+hash);
  return {page,calls,states,seen:()=>bagSeen};
 }
 const gets=(calls,part)=>calls.filter(c=>c.m==='GET'&&c.u.includes(part));
 const noError=async(page,label)=>{assert.equal(await page.locator('.error-box, [role="alert"]').count(),0,label+': keine Fehlermeldung');};

 /* Nach der Schule, Kindergerät mit gemerktem Kind: eine Runde, Tasche ohne eigenen Aufruf. */
 {const {page,calls,seen}=await open({saved:'1',shell:'kid'});
  await page.getByRole('heading',{name:/^Tasche für Dienstag/}).waitFor();await page.locator('.bag-item').first().waitFor();timings.kidAfternoon=seen();
  assert.equal(gets(calls,'/packing/').length,0,'kein GET /packing beim Start');
  const me=calls.find(c=>c.u==='/api/me'),today=gets(calls,'/accounts/1/today')[0];
  assert(today.start<me.end,'Heute startet gleichzeitig mit /api/me');
  for(const p of ['/today','/tasks?recent_done_days=14','/plan?compact=1','/rewards','/profile'])assert.equal(gets(calls,'/accounts/1'+p).length,1,'genau ein Aufruf '+p);
  await noError(page,'Kindergerät');
  assert.equal(await page.locator('.ring-btn').filter({hasText:'Tasche'}).innerText().then(t=>/0 von 2/.test(t)),true,'Ring zeigt den Stand der mitgelieferten Tasche');
  await page.getByRole('button',{name:'Material für Sport',exact:true}).click();
  await page.locator('.bag-item[aria-pressed="true"]').waitFor();
  const puts=calls.filter(c=>c.m==='PUT'&&c.u.endsWith('/packing/2026-09-15'));assert.equal(puts.length,1,'Abhaken schreibt wie bisher');
  assert.match(await page.locator('.ring-btn').filter({hasText:'Tasche'}).innerText(),/1 von 2/);
  assert.equal(gets(calls,'/packing/').length,0,'auch nach dem Abhaken kein Neuladen');
  timings.kidAfternoonCalls=calls.filter(c=>c.u!=='/api/accounts/1/packing/2026-09-15').map(c=>`${c.m} ${c.u} ${c.start}–${c.end} ms`);
  await page.close();}

 /* Vor der Schule: die Tasche für heute kommt als today_bag. */
 {const {page,calls,seen}=await open({time:'2026-09-14T07:00:00+02:00',saved:'1',shell:'kid'});
  await page.getByRole('heading',{name:/^Dabei\?/}).waitFor();await page.locator('.bag-item').first().waitFor();timings.kidMorning=seen();
  assert.equal(gets(calls,'/packing/').length,0,'morgens kein GET /packing');
  await page.getByRole('button',{name:'Material für Mathematik',exact:true}).click();await page.locator('.bag-item[aria-pressed="true"]').waitFor();
  assert.equal(calls.filter(c=>c.m==='PUT'&&c.u.endsWith('/packing/2026-09-14')).length,1,'morgens wird die Tasche für heute abgehakt');
  await noError(page,'Morgen');await page.close();}

 /* Neues Gerät ohne gemerktes Kind: erst /api/me, dann Heute; die Tasche trotzdem ohne eigenen Aufruf. */
 {const {page,calls,seen}=await open();
  await page.locator('.bag-item').first().waitFor();timings.newDevice=seen();
  const me=calls.find(c=>c.u==='/api/me');assert(gets(calls,'/accounts/1/today')[0].start>=me.end,'ohne gemerktes Kind nichts vorab');
  assert.equal(gets(calls,'/packing/').length,0);await noError(page,'neues Gerät');await page.close();}

 /* Älterer Server ohne Tasche in /today: die Seite holt sie wie bisher selbst. */
 {const {page,calls}=await open({saved:'1',shell:'kid',withBag:false});
  await page.locator('.bag-item').first().waitFor();assert.equal(gets(calls,'/packing/2026-09-15').length,1,'ohne mitgelieferte Tasche ein GET');
  await page.getByRole('button',{name:'Material für Sport',exact:true}).click();await page.locator('.bag-item[aria-pressed="true"]').waitFor();
  await noError(page,'ohne Tasche');await page.close();}

 /* Gemerktes Kind nicht mehr verknüpft: die Vorabaufrufe scheitern still, Heute lädt das richtige Kind. */
 {const {page,calls}=await open({saved:'7',shell:'kid'});
  await page.locator('.bag-item').first().waitFor();
  assert(gets(calls,'/accounts/7/today').length===1,'vorab für das gemerkte Kind gefragt');
  const me=calls.find(c=>c.u==='/api/me');for(const c of gets(calls,'/accounts/1/'))assert(c.start>=me.end,'das richtige Kind erst nach /api/me: '+c.u);
  await page.waitForTimeout(DELAY+100);await noError(page,'fremdes Kind');await page.close();}

 /* Elternhülle: Die Familie öffnet, Heute lädt nicht, die Vorabantworten verfallen still. */
 {const {page,calls}=await open({saved:'1',shell:'kid',me:'parent',hash:''});
  await page.waitForFunction(()=>location.hash==='#/overview');await page.waitForTimeout(DELAY*2+200);
  assert.equal(gets(calls,'/accounts/1/today').length,1,'nur der Vorabaufruf, Heute wird nicht aufgebaut');
  assert.equal(await page.getByText('Lade deinen Tag').count(),0);await noError(page,'Elternhülle');await page.close();}

 /* Anmeldung nötig: Die Vorabaufrufe enden mit 401, gezeigt wird nur die Anmeldung. */
 {const {page}=await open({saved:'1',shell:'kid',me:'login'});
  await page.getByRole('heading',{name:'Schul-Cockpit'}).waitFor();await page.waitForTimeout(DELAY+200);
  assert.equal(await page.locator('.app-shell').count(),0,'Anmeldung statt App');
  assert.equal(await page.getByText(/konnte nicht|Fehler/).count(),0,'keine Fehlermeldung bei der Anmeldung');await page.close();}

 assert.deepEqual(errors,[]);
 console.log(`Tasche sichtbar nach: Kindergerät nachmittags ${timings.kidAfternoon} ms, morgens ${timings.kidMorning} ms, neues Gerät ${timings.newDevice} ms (${DELAY} ms je Antwort)`);
 console.log(timings.kidAfternoonCalls.map(c=>'  '+c).join('\n'));
 console.log('PASS: bag inside /today (after and before school), no GET /packing at start, bag toggles, fallback GET for older servers, early calls with the known child, silently discarded for an unlinked child, the parent shell and login, no JS exceptions');
 await browser.close();await new Promise(r=>server.close(r));
})().catch(e=>{console.error(e);process.exit(1)});
