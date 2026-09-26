// Startseite der Eltern (D166, D183). Build the frontend first. Requires playwright-core;
// optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
const {chromium}=require('playwright-core');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert/strict');
const go=(page,section=null,args=[])=>({page,args,section});
const stages=(sitzt,wackelt,angefangen,neu)=>({sitzt,wackelt,angefangen,neu});
const per=(short,start,end,extra={})=>({short,subject:short,start,end,state:'normal',exam:false,room_changed:false,absent:false,extra:false,now:false,past:false,...extra});
const scheduleA=[{date:'2026-09-24',label:'Heute',is_today:true,start:'07:50',end:'11:15',planned_start:'07:50',planned_end:'13:10',early_end:true,late_start:false,all_cancelled:false,
  headline:'früher Schluss 11:15 statt 13:10',deviates:true,notes:['Englisch 11:35–13:10 fällt aus'],
  periods:[per('SP','07:50','08:35',{past:true}),per('SP','08:40','09:25',{past:true}),per('DE','09:45','10:30',{now:true}),per('SN','10:30','11:15'),per('EN','11:35','12:20',{state:'cancelled'}),per('EN','12:25','13:10',{state:'cancelled'})]},
 {date:'2026-09-25',label:'Fr 25.09.',is_today:false,start:'07:50',end:'13:10',planned_start:'07:50',planned_end:'13:10',early_end:false,late_start:false,all_cancelled:false,headline:'',deviates:false,notes:[],
  periods:[per('MU','07:50','08:35'),per('MU','08:40','09:25'),per('MA','09:45','10:30',{exam:true}),per('MA','10:30','11:15',{exam:true})]}];
const boardA={schedule:scheduleA,status:{level:'warn',label:'Nachsteuern',reasons:['Mathematik: noch nichts geübt']},evening:false,
  ok:['Aufgaben bis morgen erledigt','Tasche für Fr gepackt','6/6 Stunden bewertet'],acute:[{key:'overdue',tone:'bad',icon:'⚠️',title:'1 Aufgabe überfällig',detail:'Brüche',go:go('today','aufgaben')},{key:'due',tone:'info',icon:'📝',title:'1 Aufgabe bis morgen offen',detail:'Lesen',go:go('today','aufgaben')},{key:'bag',tone:'info',icon:'🎒',title:'Tasche für Mo 28.09.: 0 von 3 Fächern',detail:'noch nicht alles abgehakt',go:go('today','tasche')},{key:'feedback',tone:'warn',icon:'🗣️',title:'4 Stunden ohne Rückmeldung',detail:'an den Vortagen 4',go:go('week')}],
  exams:[{exam_key:'cal:m',date:'2026-09-28',day:'Mo 28.09.',days_until:4,subject_name:'MATHEMATIK',kind:'Arbeit',topics:4,practiced:3,stages:stages(1,1,1,1),missing:0,material_ok:true,go:go('klausuren','arbeit-cal:m')},
         {exam_key:'cal:mu',date:'2026-10-05',day:'Mo 05.10.',days_until:11,subject_name:'MUSIK',kind:'Lernkontrolle',topics:1,practiced:0,stages:stages(0,0,0,1),missing:0,material_ok:true,go:go('klausuren','arbeit-cal:mu')}],
  later:[{exam_key:'cal:e',day:'Fr 30.10.',days_until:36,subject_name:'ENGLISCH',topics:3,missing:2,go:go('klausuren','arbeit-cal:e')},
         {exam_key:'cal:l',day:'Mo 16.11.',days_until:53,subject_name:'LATEIN',topics:0,missing:0,go:go('klausuren','arbeit-cal:l')}],
  watch:[{key:'hard-8',tone:'warn',icon:'∿',title:'Mathematik fällt schwer',detail:'4 von 10 bewerteten Stunden der letzten 3 Wochen als schwer bewertet',go:go('subject',null,['8'])}]};
const boardB={status:{level:'bad',label:'Eingreifen',reasons:['Aufgaben überfällig']},evening:false,ok:[],
  acute:[{key:'overdue',tone:'bad',icon:'⚠️',title:'1 Aufgabe überfällig',detail:'Brüche',go:go('today','aufgaben')},
         {key:'retake',tone:'warn',icon:'📷',title:'2 Seiten neu fotografieren',detail:'„Zerlegen“ · unscharf',go:{page:'erledigen',args:[],section:null,parent:true}}],
  exams:[{exam_key:'cal:s',date:'2026-10-01',day:'Do 01.10.',days_until:7,subject_name:'ENGLISCH',kind:'Sprechprüfung',topics:4,practiced:0,stages:stages(0,0,0,4),missing:5,material_ok:false,go:go('klausuren','arbeit-cal:s')}],
  later:[],watch:[]};
(async()=>{
const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
const server=http.createServer((req,res)=>{const f=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',f.endsWith('.js')?'text/javascript':f.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(f));}catch{res.statusCode=404;res.end();}});
await new Promise(r=>server.listen(4180,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']});
try {
const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});
page.setDefaultTimeout(6000); const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});
await page.clock.install({time:new Date('2026-09-24T14:00:00+02:00')});
const modes=[];
await page.route('**/api/**',async route=>{
const u=new URL(route.request().url()).pathname;let body={};modes.push([u,route.request().headers()['x-view-mode']||'']);
if(u==='/api/me')body={id:1,role:'parent',accounts:[{id:1,name:'Kind A'},{id:2,name:'Kind B'}]};
else if(u==='/api/dashboard')body={today:'2026-09-24',kids:[{account_id:1,name:'Kind A',board:boardA,study:{done:1,total:2,tight:[]},rings:{next_school_day:'2026-09-25',carry_day:null,tasks:{done:2,total:2},study:{done:1,total:2,tight:[],carry:null},bag:{day:'2026-09-25',done:3,total:3,packed:true},feedback:{done:1,total:3}}},{account_id:2,name:'Kind B',board:boardB}]};
else if(u==='/api/parent-report')body={weekday:6,at:'18:00',targets:[],services:[]};
else if(u==='/api/parent/todo')body={today:'2026-09-24',total:3,blocking:[],household:[],kids:[{account_id:1,name:'Kind A',items:[]},{account_id:2,name:'Kind B',items:[]}]};
await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
});
await page.goto('http://127.0.0.1:4180/#/overview');
const a=page.getByLabel('Stand von Kind A'),b=page.getByLabel('Stand von Kind B');
await a.waitFor();
assert.equal(await a.getAttribute('data-status'),'warn');assert.equal(await b.getAttribute('data-status'),'bad');
// Eigene Elternhülle (D183): nur Familie, Erledigen, Scannen, Einstellen; oben nur der Profilknopf.
assert.deepEqual(await page.locator('.bottom-nav button').allInnerTexts().then(t=>t.map(x=>x.replace(/\d+/g,'').trim())),['Familie','Erledigen','Scannen','Einstellen']);
await page.locator('.nav-badge').filter({hasText:'3'}).waitFor();
assert.equal(await page.locator('.top-bar select').count(),0,'no child picker on top');
assert.equal(await page.locator('.top-bar button').count(),1,'only the profile button');
assert.equal(await page.getByText('Wochenbericht aufs Handy').count(),0,'weekly report moved to Einstellen');
assert.equal(await page.getByText(/^Kinderansicht /).count(),0,'child view only via profile button');
await a.getByText('Nachsteuern',{exact:true}).waitFor();await b.getByText('Eingreifen',{exact:true}).waitFor();
// Die vier Ringe wie auf „Heute“ ersetzen Lernzeile und Erledigt-Zeile.
assert.deepEqual(await a.locator('.ring-btn').allInnerTexts().then(t=>t.map(x=>x.replace(/\s+/g,' ').trim())),['✓ Aufgaben 2 von 2','🧠 Lernen 1 von 2','✓ Tasche 3 von 3','💬 Feedback 1 von 3']);
assert.equal(await a.locator('.okline').count(),0,'rings replace the ok lines');
// Was ein Ring zeigt, steht nicht noch einmal als Zeile da; Überfälliges bleibt.
assert.deepEqual(await a.locator('.row b').allInnerTexts(),['1 Aufgabe überfällig','Mathematik fällt schwer']);
assert.equal(await b.locator('.okline').count(),0);
// Stundenplan: heute und der nächste Schultag, Ausfall durchgestrichen, früher Schluss gelb (D170).
assert.deepEqual(await a.locator('.plan .lbl > span:first-child').allInnerTexts(),['Heute','Fr 25.09.']);
await a.getByText('früher Schluss 11:15 statt 13:10').waitFor();await a.getByText('Englisch 11:35–13:10 fällt aus').waitFor();
assert.equal(await a.locator('.ps i.x').count(),2);assert.equal(await a.locator('.ps i.now').count(),1);assert.equal(await a.locator('.ps i.gap').count(),4);assert.equal(await a.locator('.ps i.empty').count(),2);
assert.equal(await a.locator('.strip .t.devt').first().innerText(),'11:15');assert.equal(await b.locator('.plan').count(),0);
// Arbeiten chronologisch, Balken nur mit bekannten Themen, Später in einer Zeile.
assert.deepEqual(await a.locator('.exam .l1 b').allInnerTexts(),['Mathematik-Arbeit Mo 28.09.','Musik-Lernkontrolle Mo 05.10.']);
assert.equal(await a.locator('.exam').first().locator('.stack i').count(),4);
await a.getByText('3 von 4 Themen geübt').waitFor();await a.getByText('in 4 Tagen').waitFor();
await a.getByText('2 fehlen').waitFor();await a.getByText('Themen unbekannt').waitFor();
await b.getByText('5 Seiten fehlen').waitFor();assert.equal(await b.locator('.badge.bad').count(),1);
assert.equal(await page.getByText('Diese Woche',{exact:true}).count(),0);assert.equal(await page.getByText(/Stundenplan/).count(),0);
for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}
if(process.env.SCHOOL_SCREENSHOT_DIR){await page.setViewportSize({width:390,height:1400});await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'family-board.png'),fullPage:true});}
assert.deepEqual(errors,[]);
// Schnellzugriffe: Kind wechseln, Seite und Abschnitt im Hash. Die Zielseiten
// haben hier keine Daten; geprüft wird nur der Sprung.
const mode=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('viewMode')||'{"mode":"parent"}').mode);
await a.locator('.plan').click();assert.equal(await page.evaluate(()=>location.hash),'#/week');
// Familie öffnet lesend (Mitlesen): Band oben, Kinder-Leiste, Zurück zur Familie.
assert.equal(await mode(),'mirror');await page.getByRole('status').filter({hasText:'nur lesen'}).waitFor();
assert.deepEqual(await page.locator('.bottom-nav button').allInnerTexts(),['Heute','Woche','Lernen','Ich']);
await page.getByRole('button',{name:'Zurück zur Familie'}).click();await a.waitFor();
assert.equal(await page.evaluate(()=>location.hash),'#/overview');assert.equal(await mode(),'parent');
// Auch die Zurück-Geste führt aus dem Mitlesen zur Elternansicht.
await a.locator('.plan').click();await page.waitForFunction(()=>location.hash==='#/week');
await page.goBack();await a.waitFor();assert.equal(await mode(),'parent');
// Der Lernen-Ring springt in den Lernen-Abschnitt von Heute.
await a.getByRole('button',{name:'Lernen: 1 von 2'}).click();
assert.equal(await page.evaluate(()=>location.hash),'#/today?s=lernen%2Clernen-kurz');assert.equal(await mode(),'mirror');
await page.goto('http://127.0.0.1:4180/#/overview');await a.waitFor();
await page.goto('http://127.0.0.1:4180/#/overview');await b.waitFor();
await b.getByText('1 Aufgabe überfällig').click();
assert.equal(await page.evaluate(()=>location.hash),'#/today?s=aufgaben');
assert.equal(await page.evaluate(()=>localStorage.getItem('activeAccountId')||''),'2');
assert.equal(await mode(),'mirror');
// Die Anfragen der Kinderseite laufen im Mitlesen.
assert(modes.some(([u,m])=>u.startsWith('/api/accounts/2/')&&m==='mirror'),'mirror header on child page');
// Neu fotografieren ist Elternsache: Erledigen in der Elternansicht, nicht Mitlesen (D183).
await page.goto('http://127.0.0.1:4180/#/overview');await b.waitFor();assert.equal(await mode(),'parent');
await b.getByText('2 Seiten neu fotografieren').click();
assert.equal(await page.evaluate(()=>location.hash),'#/erledigen');assert.equal(await mode(),'parent');
await page.goto('http://127.0.0.1:4180/#/overview');await a.waitFor();
await a.getByText('Musik-Lernkontrolle Mo 05.10.').click();
assert.equal(await page.evaluate(()=>location.hash),'#/klausuren?s=arbeit-cal%3Amu');
await page.goto('http://127.0.0.1:4180/#/overview');await a.waitFor();
await a.getByText('Mathematik fällt schwer').click();
assert.equal(await page.evaluate(()=>location.hash),'#/subject/8');
console.log('PASS: parent shell nav with badge, status per child, all-done line, exams in order with bar, later line, read-only jumps with child and section, back to family (button and gesture), parent work to Erledigen, responsive layout');
}finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exit(1)});
