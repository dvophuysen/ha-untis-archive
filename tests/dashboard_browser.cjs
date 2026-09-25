// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
const {chromium:pw}=require('playwright-core');
const fs=require('fs');const http=require('http');const path=require('path');const assert=require('assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
 const server=http.createServer((req,res)=>{const file=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});await new Promise(r=>server.listen(4178,'127.0.0.1',r));
 const browser=await pw.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
 const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.clock.install({time:new Date('2026-09-14T14:00:00+02:00')});
 let onIch=false,rating=null,done=false,failRating=true,failTask=true,failPack=true,studyDone=false,practicePosts=0;
 const bags={};let schoolDate='2026-09-14';
 function bag(day){const states=bags[day]||={};const items=[{key:'subject:math',label:'Mathematik'},{key:'subject:sport',label:'Sport'}].map(i=>({...i,done:!!states[i.key],revision:states[i.key]?1:0}));return {school_day:day,items,schedule:[{id:1,subject_name:'Mathematik',start_hhmm:'08:00',end_hhmm:'08:45',room:'204',material_key:'subject:math',material_checkbox:true},{id:2,subject_name:'Mathematik',start_hhmm:'08:45',end_hhmm:'09:30',room:'204',material_key:'subject:math',material_checkbox:false},{id:3,subject_name:'Sport',start_hhmm:'09:50',end_hhmm:'10:35',room:'Halle 2',room_orig:'Halle 1',is_room_substituted:true,teacher_name:'Vertretung',teacher_orig_name:'Stammlehrkraft',is_teacher_substituted:true,material_key:'subject:sport',material_checkbox:true},{id:4,subject_name:'Physik',start_hhmm:'10:50',end_hhmm:'11:35',is_cancelled:true}],plan_key:'a'.repeat(64),can_write:true,confirmed_count:items.filter(i=>i.done).length,status:items.every(i=>i.done)?'packed':'open'};}
 await page.route('**/api/**',async route=>{const req=route.request(),u=new URL(req.url()).pathname;let body={};let status=200;
 if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role:'child',is_admin:false};
 else if(u.includes('/packing/')){const day=u.split('/').at(-1);if(req.method()==='PUT'){if(failPack){status=500;body={detail:'Packen nicht gespeichert'};}else{const update=req.postDataJSON();(bags[day]||={})[update.item_key]=update.done;body=bag(day);}}else body=bag(day);}
 else if(u.endsWith('/practice')&&req.method()==='GET')body={papers:[{id:5,paper_format:'einstieg',attempt_id:7,status:'active',created_at:'2026-09-14T10:00:00+02:00'}]};
 else if(u.endsWith('/practice')&&req.method()==='POST'){practicePosts++;body={id:8};}
 else if(u.includes('/practice/attempts/7'))body={id:7,label:'Einstiegstest',status:'active',exam:{title:'Einstiegstest Mathematik',minutes:30,tasks:[]},pages:[],answers:{},feedback:{},read_only:false};
 else if(u.endsWith('/today'))body={new_results:[{attempt_id:41,label:'Probearbeit',subject:'Mathematik',points:6,points_max:40,unclear:3}],study_plan:{day:schoolDate,steps:[{key:'paper:ma:einstieg',kind:'paper',title:'Einstiegstest Mathematik',why:'Zeigt, wo du für die Arbeit am 22.09. stehst.',subject:'Mathematik',exam_key:'ma',exam_date:'2026-09-22',format:'einstieg',topic_id:null,level:null,href:null,done:studyDone,tight:false}],engpass:false,tight:[],free_day:false,frozen:true,read_only:false,done:studyDone?1:0,total:1},date:schoolDate,lessons:[{id:1,date:schoolDate,subject_name:'Deutsch',subject_short:'DE',start_hhmm:'08:00',start_time:800,end_time:845,room:'204',lstext:'Groß- und Kleinschreibung',checkin:{rating,note:null}}],next:{date:'2026-09-15',lessons:[{id:2,subject_name:'Sport',start_hhmm:'08:00',end_time:845,room:'Halle'}]}};
 else if(u.endsWith('/tasks')&&req.method()==='GET')body={tasks:[{id:1,title:'Mathematik',notes:'Brüche: Aufgabe 3\nGegeben am: Mo 14.09.\nFällig bis: Di 15.09.\n[MA0915]',due_date:'2026-09-15',status:done?'done':'open',estimated_minutes:10},{id:2,title:'Englisch',notes:'Seite 24 lesen',due_date:'2026-09-18',status:'open'},{id:3,title:'Notiz ohne Termin',status:'open'},{id:4,title:'Geschichte',notes:'Lies den Text und beschreibe die Unterschiede. '.repeat(5),due_date:'2026-09-21',status:'open'}]};
 else if(u.endsWith('/plan'))body={today:{actions:[{key:'math',subject:'Mathematik',title:'Brüche vergleichen',minutes:8,url:'#/learning?focus=math'}]},upcoming_exams:[],errors:[]};
 else if(u.endsWith('/checkin')){if(failRating){status=500;body={detail:'Test failure'};}else{rating=req.postDataJSON().rating;body={rating,note:null};}}
 else if(u.endsWith('/rewards')&&onIch)body={streak:{current:3,record:5,next_milestone:5},week:[{day:'2026-09-14',state:'open'}],total:3,start:'2026-09-01',bonus_until:'17:00',badges:[],special:[],medals:[{year:'2026/27',medal:null,pct:50,running:true,limits:[50,65,80]}]};
 else if(u.endsWith('/reminders'))body={enabled:true,remind_at:'18:00',morning_enabled:false,afternoon_enabled:false,can_manage:false,app_targets:[],app_services:[]};
 else if(u==='/api/tasks/1'){if(failTask){status=500;body={detail:'Test failure'};}else{done=req.postDataJSON().status==='done';body={ok:true};}}
 await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('http://127.0.0.1:4178/#/today');await page.getByRole('heading',{name:/^Aufgaben bis morgen/}).waitFor({timeout:8000}).catch(async e=>{console.log('ERRORS',errors,'BODY',await page.locator('body').innerText());throw e;});
 /* D201: neue Auswertung auf „Heute“, führt direkt zur Arbeit */
 const note=page.locator('a.result-note');assert.equal(await note.count(),1);
 assert.match(await note.innerText(),/Deine Probearbeit ist ausgewertet · Mathematik/);assert.match(await note.innerText(),/6 von 40 Punkten · 3 Aufgaben unklar gelesen/);
 assert.equal(await note.getAttribute('href'),'#/learning?paper=41');
 // Nach der Schule (D171): Ringe, Aufgaben bis zum nächsten Schultag, Tasche als Kacheln, Rückmeldungen.
 for(const title of [/^Tasche für Dienstag/,/^Stunden von heute/,/^Wenn du magst/])assert.equal(await page.getByRole('heading',{name:title}).count(),1);
 // Vier Bereiche (D180): Aufgaben, Lernen, Tasche, Feedback.
 assert.equal(await page.locator('.ring-btn').count(),4);
 assert.deepEqual(await page.locator('.ring-btn b').allInnerTexts(),['Aufgaben','Lernen','Tasche','Feedback']);
 // Fokuskarte: kurz wie in der Liste, ohne UNTIS-Angaben und ohne Zeitschätzung; Tippen öffnet das Detail.
 const focusText=await page.locator('.focus').innerText();
 assert(focusText.includes('Brüche: Aufgabe 3'),'note in focus card');
 for(const noise of ['Gegeben am','Fällig bis','[MA0915]','Freizeit in','Min.'])assert(!focusText.includes(noise),'focus card without '+noise);
 await page.locator('.focus-task').click();const detail=page.getByRole('dialog',{name:'Hausaufgabe'});await detail.waitFor();
 assert((await detail.locator('.assignment').innerText()).includes('Brüche: Aufgabe 3'));await detail.getByRole('button',{name:'Schließen'}).click();await detail.waitFor({state:'detached'});
 // Lernen: Schritt mit Grund und Los; eine heute offene Übungsarbeit geht wieder auf statt neu erstellt zu werden.
 const learn=page.locator('#s-lernen');assert.equal(await page.getByRole('heading',{name:/^Lernen/}).count(),1);
 assert((await learn.innerText()).includes('Zeigt, wo du für die Arbeit'));
 await learn.getByRole('button',{name:'Los',exact:true}).click();await page.getByRole('button',{name:'← Zurück zu Heute'}).waitFor();assert.equal(practicePosts,0,'open paper reopened');
 await page.getByRole('button',{name:'← Zurück zu Heute'}).click();await learn.getByRole('button',{name:'Los',exact:true}).waitFor();
 await page.getByRole('button',{name:'Verstanden',exact:true}).click();await page.getByRole('alert').filter({hasText:'Nicht gespeichert'}).waitFor();assert.equal(rating,null);
 failRating=false;await page.getByRole('button',{name:'Verstanden',exact:true}).click();await page.locator('#s-stunden .fold-head[aria-expanded="false"]').waitFor();assert.equal(rating,3);/* D187: erledigt klappt zu, antippen klappt auf */await page.locator('#s-stunden .fold-head').click();await page.locator('#s-stunden button[aria-label="Verstanden"][aria-pressed="true"]').waitFor();
 await page.locator('#s-aufgaben').getByRole('button',{name:'Als erledigt markieren',exact:true}).first().click();await page.getByText('Test failure',{exact:true}).waitFor();assert.equal(done,false);
 failTask=false;await page.locator('#s-aufgaben').getByRole('button',{name:'Als erledigt markieren',exact:true}).first().click();await page.locator('#s-aufgaben .fold-head[aria-expanded="false"]').waitFor();await page.locator('#s-aufgaben .fold-head').click();await page.getByText('✓ Keine Aufgabe offen.').waitFor();assert.equal(done,true);
 await page.getByRole('button',{name:'Material für Sport',exact:true}).click();await page.getByRole('alert').filter({hasText:'Packen nicht gespeichert'}).waitFor();
 assert.equal(await page.locator('.bag-item[aria-pressed="true"]').count(),0);
 failPack=false;await page.getByRole('button',{name:'Material für Sport',exact:true}).click();await page.locator('.bag-item[aria-pressed="true"]').waitFor();
 studyDone=true;await page.reload();await page.locator('.bag-item[aria-pressed="true"]').waitFor();
 await page.locator('#s-lernen .fold-head[aria-expanded="false"]').waitFor();assert.equal(await page.locator('#s-aufgaben .fold-head[aria-expanded="true"]').count(),1,'von Hand aufgeklappt bleibt offen');await page.locator('#s-lernen .fold-head').click();await page.locator('#s-lernen .learn-state').filter({hasText:'erledigt'}).waitFor();assert.equal(await page.locator('#s-lernen').getByRole('button',{name:'Los'}).count(),0);
 assert.equal(await page.locator('.bag-item[aria-pressed="true"]').count(),1);
 await page.getByRole('button',{name:'Material für Mathematik',exact:true}).click();await page.getByText('Geschafft. Freizeit!').waitFor();assert(await page.getByText(/Lernen erledigt/).count()>0,'done card names learning');
 await page.locator('.fold summary').click();
 for(const width of [320,390,430,768]){
  await page.setViewportSize({width,height:900});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+width);
  const geometry=await page.locator('.task-row:has(.due):has(.practice-link)').evaluateAll(rows=>rows.map(row=>{
    const due=row.querySelector('.due').getBoundingClientRect(),help=row.querySelector('.practice-link').getBoundingClientRect();
    return {dueRight:due.right,helpRight:help.right,dueBottom:due.bottom,helpTop:help.top,helpHeight:help.height};
  }));
  assert(geometry.length>0);
  for(const row of geometry){assert(row.helpTop>=row.dueBottom,'help below due at '+width);assert(Math.abs(row.dueRight-row.helpRight)<1,'aligned right edge at '+width);assert(row.helpHeight>=44,'touch target at '+width);}
 }
 await page.setViewportSize({width:768,height:900});const edges=await page.locator('.row-actions').evaluateAll(rows=>rows.map(r=>r.getBoundingClientRect().right));assert(edges.every(x=>Math.abs(x-edges[0])<1),'task actions have one right edge');if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'dashboard-tablet.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'dashboard-390.png'),fullPage:true});
 await page.emulateMedia({colorScheme:'dark'});if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'dashboard-dark.png'),fullPage:true});
 schoolDate='2026-09-15';await page.clock.setFixedTime(new Date('2026-09-15T07:00:00+02:00'));await page.reload();await page.getByRole('heading',{name:/^Dabei\?/}).waitFor();await page.locator('.bag-item[aria-pressed="true"]').nth(1).waitFor();assert.equal(await page.locator('.bag-item[aria-pressed="true"]').count(),2,'afternoon confirmations remain in morning checklist');assert.equal(await page.locator('.ring-btn').count(),0,'no rings before school');
 assert((await page.locator('.learn-line').innerText()).startsWith('Heute lernen:'),'compact learning line before school');
 // Kinder-Hülle (D183): kein Zahnrad oben; die Erinnerung steht unter „Ich“ bei den Einstellungen.
 assert.equal(await page.getByRole('button',{name:'Einstellungen'}).count(),0,'no gear for the child');
 assert.deepEqual(await page.locator('.bottom-nav button > span:last-child').allInnerTexts(),['Heute','Woche','Lernen','Ich']);
 onIch=true;await page.goto('http://127.0.0.1:4178/#/ich');await page.getByRole('heading',{name:'Einstellungen'}).waitFor();
 await page.getByText('Dein Tagescheck ist um 18:00 Uhr.',{exact:false}).waitFor();
 assert.equal(await page.getByLabel(/Frühstarter bis/).count(),0,'bonus time only shown, set by parents');
 await page.getByText('Fertig vor 17:00 Uhr ist ein Frühstarter-Tag.',{exact:false}).waitFor();
 await page.goto('http://127.0.0.1:4178/#/settings');await page.waitForFunction(()=>location.hash==='#/today');
 assert.deepEqual(errors,[]);console.log('PASS: phases after and before school, four rings, learning steps, compact focus card with task detail, failed/successful checkin and task save, persistent packing as tiles, done moment, 320/390/430/768 px, stacked actions, no gear for the child, reminder under Ich, parent pages redirect, no JS exceptions');await browser.close();await new Promise(r=>server.close(r));
})().catch(e=>{console.error(e);process.exit(1)});
