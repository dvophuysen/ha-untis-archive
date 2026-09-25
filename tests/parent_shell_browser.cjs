// Eigene Eltern-Hülle (D183): Erledigen, Scannen, Einstellen, Kindmodus ohne
// Eltern-Werkzeuge. Build the frontend first. Requires playwright-core;
// optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
const {chromium}=require('playwright-core');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert/strict');
const act=(label,page,{args=[],section=null,query={}}={})=>({label,page,args,section,query});
const todoBody={today:'2026-09-24',total:4,blocking:[],
  household:[{key:'opening',kind:'ai_opening',level:'todo',title:'Anfangsstand der KI-Kosten bestätigen',reason:'Vor der Verbrauchserfassung gab es schon Aufrufe.',action:act('KI-Rahmen öffnen','einstellen',{section:'ki'})}],
  kids:[{account_id:1,name:'Kind A',items:[
    {key:'missing:m',kind:'missing_material',level:'todo',account_id:1,title:'Material für Mathematik fotografieren',reason:'3 Seiten fehlen für die Arbeit am Mo 28.09.: Arbeitsheft S. 12–14. Aus: Hausaufgabe Mathematik vom 23.09.: „Arbeitsheft S. 12-14 bearbeiten“',reason_plain:'3 Seiten fehlen für die Arbeit am Mo 28.09.: Arbeitsheft S. 12–14.',
     source:{label:'Hausaufgabe Mathematik vom 23.09.',quote:'Arbeitsheft S. 12-14 bearbeiten',href:'#/materialien?material=55'},dismiss:{subject:'MATHEMATIK',label:'Arbeitsheft',pages:[12,13,14],what:'Arbeitsheft S. 12–14'},
     action:act('Scannen','scannen',{query:{acc:'1',art:'book_page',fach:'MATHEMATIK'}})},
    {key:'notice:m',kind:'notice_check',level:'todo',account_id:1,title:'Themenzettel Mathematik gegenlesen',reason:'Eine Seitenzahl auf dem Zettel kennt der Unterricht nicht.',action:act('Gegenlesen','materialien',{section:'gegenlesen',query:{material:'77'}})}]},
   {account_id:2,name:'Kind B',items:[
    {key:'calendar',kind:'calendar_assign',level:'todo',account_id:2,title:'1 Termin zuordnen',reason:'Bei „Kurs 7“ am Do 01.10. ist kein Fach erkannt.',action:act('Zuordnen','exams',{section:'zuordnen'})}]}]};
const budget={used_eur:1.5,month:'2026-09',limit_eur:50,daily_limit_eur:10,warning_eur:40,accounting:'Gebucht mit Aufschlag',per_day_eur:0.1,opening_confirmed:false,rate_available:true,models:[],rates:{},model:'test'};
(async()=>{
const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
const server=http.createServer((req,res)=>{const f=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',f.endsWith('.js')?'text/javascript':f.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(f));}catch{res.statusCode=404;res.end();}});
await new Promise(r=>server.listen(4181,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']});
try {
const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});
page.setDefaultTimeout(6000);const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});
await page.clock.install({time:new Date('2026-09-24T14:00:00+02:00')});
const calls=[],uploads=[],puts=[],dismissals=[];
await page.route('**/api/**',async route=>{
  const req=route.request(),u=new URL(req.url()).pathname,m=req.method();let body={};
  calls.push({u,m,mode:req.headers()['x-view-mode']||''});
  if(u==='/api/me')body={id:1,role:'parent',is_admin:false,auth_source:'ingress',open_audit_count:2,accounts:[{id:1,name:'Kind A'},{id:2,name:'Kind B'}]};
  else if(u==='/api/parent/todo')body=todoBody;
  else if(u==='/api/dashboard')body={today:'2026-09-24',kids:[]};
  else if(u.endsWith('/materials/sources/dismiss')&&m==='POST'){dismissals.push({u,body:req.postDataJSON(),mode:req.headers()['x-view-mode']||''});
    todoBody.kids[0].items=todoBody.kids[0].items.filter(i=>i.key!=='missing:m');todoBody.total-=1;body={dismissed:[12,13,14]};}
  else if(u.endsWith('/materials')&&m==='POST'){const raw=req.postDataBuffer().toString('latin1');uploads.push({u,raw,mode:req.headers()['x-view-mode']||''});body={id:100+uploads.length};}
  else if(u.endsWith('/materials'))body={materials:[],kinds:[],can_manage:true,can_write:true,needs_check:0,retakes:[],pending_analysis:0,has_more:false,offset:0};
  else if(u.endsWith('/materials/sources'))body={books:[],missing:[]};
  else if(u.endsWith('/subjects'))body={subjects:[{name:'Mathematik',untis_name:'MATHEMATIK'},{name:'Englisch',untis_name:'ENGLISCH'}]};
  else if(u.endsWith('/reminders'))body={enabled:false,remind_at:null,morning_enabled:false,afternoon_enabled:false,can_manage:true,app_targets:[],app_services:[]};
  else if(u.endsWith('/rewards/settings')){puts.push({u,body:req.postDataJSON()});body={bonus_until:req.postDataJSON().bonus_until};}
  else if(u.endsWith('/rewards'))body={bonus_until:'17:00'};
  else if(u.endsWith('/learning/mentor/admin'))body={enabled:true,background:false,profile:{school_year:'2026/2027',grade:6,ai_enabled:1},budget};
  else if(u==='/api/parent-report')body={weekday:6,at:'18:00',targets:[],devices:[]};
  else if(u.endsWith('/exams/diagnostic'))body={all_entries:[],subjects:[],exclude_keywords:[]};
  else if(u.endsWith('/calendar-entities'))body={available:false,entities:[]};
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
});
const hash=()=>page.evaluate(()=>location.hash);
const shot=async(name)=>{if(process.env.SCHOOL_SCREENSHOT_DIR){await page.setViewportSize({width:390,height:1400});await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,name),fullPage:true});}await page.setViewportSize({width:390,height:844});};
const mode=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('viewMode')||'{"mode":"parent"}').mode);
// Erledigen: je Kind gruppiert, Familie getrennt, Zähler an der Leiste.
await page.goto('http://127.0.0.1:4181/#/erledigen');
await page.getByRole('heading',{name:'Erledigen'}).waitFor();
assert.deepEqual(await page.locator('.bottom-nav button > span:last-child').allInnerTexts(),['Familie','Erledigen','Scannen','Einstellen']);
await page.locator('.nav-badge').filter({hasText:'4'}).waitFor();
assert.equal(await page.locator('.top-bar button').count(),1,'only the profile button on top');
assert.equal(await page.getByRole('button',{name:'Einstellungen'}).count(),0);assert.equal(await page.getByRole('button',{name:'Setup'}).count(),0);
const kidA=page.getByLabel('Offen für Kind A'),kidB=page.getByLabel('Offen für Kind B');
await kidA.getByText('Material für Mathematik fotografieren').waitFor();await kidA.getByText('3 Seiten fehlen').waitFor();
// Woher der Hinweis kommt (D196): eigene Zeile mit Zitat und Link, nicht doppelt im Satz.
await kidA.getByText('Aus: Hausaufgabe Mathematik vom 23.09.').waitFor();await kidA.getByText('„Arbeitsheft S. 12-14 bearbeiten“').waitFor();
assert.equal(await kidA.getByRole('link',{name:'Ansehen'}).getAttribute('href'),'#/materialien?material=55');
assert(!(await kidA.locator('.item small').first().innerText()).includes('Aus:'),'source not repeated in the reason');
await kidB.getByText('1 Termin zuordnen').waitFor();await page.getByLabel('Für die Familie').getByText('Anfangsstand der KI-Kosten bestätigen').waitFor();
for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'erledigen overflow '+width);}
await shot('parent-erledigen.png');
// Sprung schreibend in die Elternseite: Zuordnen öffnet die Arbeiten-Verwaltung von Kind B.
await kidB.getByText('1 Termin zuordnen').click();
assert.equal(await hash(),'#/exams?s=zuordnen');assert.equal(await mode(),'parent');
assert.equal(await page.evaluate(()=>localStorage.getItem('activeAccountId')),'2');
await page.getByRole('group',{name:'Für welches Kind'}).waitFor();
await page.goBack();await kidA.waitFor();
await kidA.getByText('Themenzettel Mathematik gegenlesen').click();
assert.equal(await hash(),'#/materialien?material=77&s=gegenlesen');assert.equal(await mode(),'parent');
await page.goBack();await kidA.waitFor();
// Scannen mit Vorschlag: Kind, Art und Fach sind vorbelegt; abgelegt wird über den Materialien-Weg.
await kidA.getByText('Material für Mathematik fotografieren').click();
assert.equal(await hash(),'#/scannen?acc=1&art=book_page&fach=MATHEMATIK');
await page.getByRole('heading',{name:'Scannen'}).waitFor();
await page.getByRole('button',{name:'Kind A',exact:true}).and(page.locator('[aria-pressed="true"]')).waitFor();
await page.getByRole('button',{name:'Buchseite',exact:true}).and(page.locator('[aria-pressed="true"]')).waitFor();
assert.equal(await page.getByLabel('Fach (optional)').inputValue(),'MATHEMATIK');
await page.getByLabel('Vorgeschlagen').getByText('Kind A · 3 Seiten fehlen',{exact:false}).waitFor();
const png=Buffer.from('89504e470d0a1a0a','hex');
await page.getByLabel('Datei wählen').setInputFiles([{name:'s12.png',mimeType:'image/png',buffer:png},{name:'s13.png',mimeType:'image/png',buffer:png}]);
await page.getByText('2 Seiten für Kind A gespeichert',{exact:false}).waitFor();
assert.equal(uploads.length,2);
for(const up of uploads){assert.equal(up.u,'/api/accounts/1/materials');assert.equal(up.mode,'','parent writes, not mirror');
  assert(/name="kind"\r\n\r\nbook_page/.test(up.raw),'kind sent');assert(/name="subject_name"\r\n\r\nMATHEMATIK/.test(up.raw),'subject sent');}
// Anderes Kind, andere Art, ohne Fach: der Server erkennt es selbst.
await page.getByRole('button',{name:'Kind B',exact:true}).click();await page.getByRole('button',{name:'Themenzettel',exact:true}).click();
await page.getByLabel('Fach (optional)').selectOption('');
await page.getByLabel('Datei wählen').setInputFiles([{name:'zettel.png',mimeType:'image/png',buffer:png}]);
await page.getByText('Eine Seite für Kind B gespeichert',{exact:false}).waitFor();
assert.equal(uploads[2].u,'/api/accounts/2/materials');assert(/name="kind"\r\n\r\nexam_notice/.test(uploads[2].raw));assert(!/name="subject_name"/.test(uploads[2].raw));
for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'scannen overflow '+width);}
await shot('parent-scannen.png');
// Einstellen: je Kind und Haushalt; Bonuszeit hierher verlegt, KI-Rahmen aus dem Lernbegleiter.
await page.locator('.bottom-nav button',{hasText:'Einstellen'}).click();
await page.getByRole('heading',{name:'Einstellen'}).waitFor();
await page.getByRole('heading',{name:'Je Kind'}).waitFor();await page.getByRole('heading',{name:'Haushalt'}).waitFor();
await page.getByRole('button',{name:'Kind B',exact:true}).and(page.locator('[aria-pressed="true"]')).waitFor();
await page.getByText('Lernrahmen 2026/2027, Klasse 6 · KI erlaubt').first().waitFor();
await page.getByText('1.50 € bisher').waitFor();await page.getByRole('button',{name:'Anfangsstand bestätigen'}).waitFor();
await page.getByText('Erinnerungen',{exact:false}).first().waitFor();await page.getByText('Wochenbericht aufs Handy').waitFor();
for(const label of ['Tagesbudget Lernzeit','Kurse und Wahlfächer','IServ-Zugang und Schulkalender','Arbeiten-Kalender und Termine','Rückgängig machen','Demo ausprobieren (Lernbegleiter)'])
  await page.getByRole('button',{name:new RegExp(label.replace(/[()]/g,'\\$&'))}).first().waitFor();
assert.equal(await page.getByRole('button',{name:/^Setup/}).count(),0,'setup only for admins');
assert.equal(await page.getByLabel(/Frühstarter bis/).inputValue(),'17:00');
await page.getByLabel(/Frühstarter bis/).fill('16:30');await page.getByRole('region',{name:'Bonuszeit'}).getByRole('button',{name:'Speichern'}).click();
await page.getByText('Gespeichert.').waitFor();
assert.deepEqual(puts,[{u:'/api/accounts/2/rewards/settings',body:{bonus_until:'16:30'}}]);
await page.getByRole('button',{name:'Kind A',exact:true}).click();
await page.waitForFunction(()=>localStorage.getItem('activeAccountId')==='1');
for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'einstellen overflow '+width);}
await shot('parent-einstellen.png');
await page.getByRole('button',{name:/Tagesbudget Lernzeit/}).click();assert.equal(await hash(),'#/settings?s=budget');
// „Nicht nötig“ (D196): inline bestätigen, dann verschwindet der Punkt.
await page.goto('http://127.0.0.1:4181/#/erledigen');await kidA.getByText('Material für Mathematik fotografieren').waitFor();
await kidA.getByRole('button',{name:'Nicht nötig'}).click();
await kidA.getByText('Dieser Hinweis kommt nicht wieder.',{exact:false}).waitFor();
await kidA.getByRole('button',{name:'Ja, streichen'}).click();
await kidA.getByText('Material für Mathematik fotografieren').waitFor({state:'detached'});
assert.deepEqual(dismissals,[{u:'/api/accounts/1/materials/sources/dismiss',body:{subject:'MATHEMATIK',label:'Arbeitsheft',pages:[12,13,14]},mode:''}]);
await kidA.getByText('Themenzettel Mathematik gegenlesen').waitFor();
assert.deepEqual(errors,[]);
// Kind am Elterngerät: Kinder-Leiste, keine Eltern-Werkzeuge, Elternseiten führen zu Heute.
await page.evaluate(()=>localStorage.setItem('viewMode',JSON.stringify({mode:'child',at:Date.now(),day:'2026-09-24'})));
// Nur der Hash ändert sich: neu laden, damit der gespeicherte Gerätezustand gilt.
await page.goto('http://127.0.0.1:4181/#/erledigen');calls.length=0;await page.reload();
await page.waitForFunction(()=>location.hash==='#/today');
assert.deepEqual(await page.locator('.bottom-nav button > span:last-child').allInnerTexts(),['Heute','Woche','Lernen','Ich']);
await page.getByRole('status').filter({hasText:'am Elterngerät'}).waitFor();
assert.equal(await page.getByRole('button',{name:'Einstellungen'}).count(),0);assert.equal(await page.getByRole('button',{name:'Setup'}).count(),0);
assert.equal(await page.locator('.nav-badge').count(),0);
assert(!calls.some(c=>c.u==='/api/parent/todo'&&c.mode==='child'),'no parent list in child mode');
assert(calls.filter(c=>c.u.startsWith('/api/accounts/')).every(c=>c.mode==='child'),'child header on every request');
for(const target of ['einstellen','scannen','settings','overview']){await page.goto(`http://127.0.0.1:4181/#/${target}`);await page.waitForFunction(()=>location.hash==='#/today');}
console.log('PASS: parent nav only, badge, Erledigen grouped per child with write jumps, source line and Nicht nötig, Scannen with suggestion via material upload for two children, Einstellen per child and household with bonus time and AI budget, child mode without parent tools, 320/390/768 px');
}finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exit(1)});
