// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
// Zurückgehaltene Auswertung (D202): Kind sieht keine Punkte, Eltern prüfen die unklaren Aufgaben und tragen Punkte ein.
const {chromium:pw}=require('playwright-core');
const fs=require('fs');const http=require('http');const path=require('path');const assert=require('assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
 const server=http.createServer((req,res)=>{const file=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});await new Promise(r=>server.listen(4185,'127.0.0.1',r));
 const browser=await pw.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
 const cell=(state)=>({state,ratio:null,tasks:0,helped:0});
 const topics=[{id:11,title:'Gleichungen',detail:'',places_label:'',stage:'neu',cells:{'1':cell('offen'),'2':cell('offen'),'3':cell('offen')},level:0,target:1,ready:false}];
 const task=(i)=>({prompt:`Aufgabe ${i}: Löse.`,solution:'x = 3',criteria:'2 P Rechnung',skill_title:'Gleichungen',topic_id:11,afb:1,points:4,minutes:5,operator:'Löse'});
 async function run(role){
  const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.clock.install({time:new Date('2026-09-25T15:00:00+02:00')});
  let status='review',sent=null;
  const attempt=()=>({id:41,status,label:'Probearbeit',format:'probe',pages:[101],read_only:false,answers:{},exam:{title:'Probearbeit Gleichungen',minutes:45,tasks:[task(1),task(2)]},
   feedback:status==='review'?{'0':{points:3,uncertain:false,rationale:'Gut.',next_step:'Weiter.'},'1':{points:1,uncertain:true,rationale:'Unklar.',next_step:'Deutlicher.',transcription:'x = 3?',spread:[1,3.5]},check:{passes:3,open:[2]}}
    :{'0':{points:3,uncertain:false,rationale:'Gut.',next_step:'Weiter.'},'1':{points:2,uncertain:false,checked_by_parent:true,rationale:'Von Eltern auf dem Blatt geprüft.',next_step:'Deutlicher.'},check:{passes:3,open:[],resolved_by_parent:[2]}}});
  await page.route('**/api/**',async route=>{const req=route.request(),u=new URL(req.url()).pathname;let body={};
   if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role,is_admin:false};
   else if(u.endsWith('/exams/all'))body={upcoming:[{exam_key:'k1',date:'2026-09-28',subject_name:'Mathematik',title:'Mathematik',topics:topics.map(t=>({...t,stale:0,places:[],self_view:null})),stages:{neu:1},sources:null,scope:null}],past:[],archived_count:0};
   else if(u==='/api/accounts/1/practice'&&req.method()==='GET')body={topics,ready:0,total:1,goal_afb:2,afb_names:{'1':'Wiedergeben','2':'Anwenden','3':'Übertragen'},formats:[],papers:[{id:5,attempt_id:41,label:'Probearbeit',created_at:'2026-09-25T15:00:00',status,points:null,points_max:8,tasks:2}]};
   else if(u==='/api/accounts/1/practice/attempts/41')body=attempt();
   else if(u.endsWith('/attempts/41/review')){sent=req.postDataJSON();status='graded';body=attempt();}
   else if(u.includes('/photos/'))return route.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=','base64')});
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto('http://127.0.0.1:4185/#/klausuren?exam=k1&paper=41');
  await page.getByText('Probearbeit Gleichungen').first().waitFor({timeout:8000}).catch(async e=>{console.log('ERRORS',errors,'BODY',await page.locator('body').innerText());throw e;});
  return {page,errors,get sent(){return sent;}};
 }
 const kid=await run('child');
 await kid.page.getByText('Deine Arbeit ist abgegeben.').waitFor();
 assert.equal(await kid.page.getByText(/von 8 Punkten/).count(),0,'keine Punkte für das Kind');
 assert.equal(await kid.page.getByRole('spinbutton').count(),0);
 assert.deepEqual(kid.errors,[]);
 const par=await run('parent');
 await par.page.getByText('Prüfung nötig: Aufgabe 2').waitFor();
 await par.page.getByText('Die Auswertungen kamen auf 1 und 3,5 Punkte.').waitFor();
 assert.equal(await par.page.getByRole('button',{name:'Punkte übernehmen'}).isDisabled(),true);
 await par.page.getByRole('spinbutton',{name:/Punkte nach eurer Prüfung/}).fill('2');
 await par.page.getByRole('button',{name:'Punkte übernehmen'}).click();
 await par.page.getByText('5 von 8 Punkten').waitFor();
 assert.deepEqual(par.sent,{points:{'1':2}});
 await par.page.getByText(/Aufgabe 2 von deinen Eltern geprüft/).waitFor();
 await par.page.setViewportSize({width:320,height:800});assert.equal(await par.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow 320');
 assert.deepEqual(par.errors,[]);
 console.log('PASS: held grading shows no points to the child, parent review with photos, spread and points, result after review, 320/390 px');
 await browser.close();await new Promise(r=>server.close(r));
})().catch(e=>{console.error(e);process.exit(1)});
